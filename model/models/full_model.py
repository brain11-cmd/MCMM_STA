"""
Full model: Physics-Informed Multi-Anchor GNN STA (v2.4 — FiLM).

FiLM conditioning (use_film=true):
  - GNN: per-layer FiLM + input_proj FiLM (inside GraphSAGEEncoder)
  - EdgeHead output: FiLM modulation (film_edge in full_model)
  All FiLM layers use tanh-bounded gamma for stability.
  Initialized to identity (zero-init) — safe to load from non-FiLM checkpoint.

Architecture:
  process_embed: Embedding(3, 8)
  gnn:          GraphSAGEEncoder(26 -> 128, 3 layers, optional FiLM per layer)
  film_edge:    FiLMLayer(12 -> gamma[128]+beta[128])  [only if use_film]
  edge_head:    EdgeHead(726 -> 256 -> 256 -> 128)
  anchor_head:  MultiAnchorHead(140 -> d_hat[E,4])
  sta:          LevelwiseSTA (no learnable params)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import torch
import torch.nn as nn

from models.gnn import GraphSAGEEncoder
from models.edge_head import EdgeHead
from models.multi_anchor import MultiAnchorHead
from models.film import FiLMLayer
from models.sta import LevelwiseSTA, build_sta_mask, NEG_INF


@dataclass
class ModelOutput:
    """All outputs from the full model forward pass."""
    d_hat: torch.Tensor        # [E, 4]
    at_all: torch.Tensor       # [N, 2]
    at_ep: torch.Tensor        # [M, 2]
    slack_hat: torch.Tensor    # [M, 2]
    g_e: torch.Tensor          # [E, K]
    gG: torch.Tensor           # [K]
    s_hat: torch.Tensor        # [E, K, 4]
    log_scale: torch.Tensor    # [E, K, 4]


class MultiAnchorSTAModel(nn.Module):
    def __init__(
        self,
        num_anchors: int = 3,
        pin_static_dim: int = 2,
        pin_dyn_dim: int = 4,
        z_cont_dim: int = 4,
        process_embed_dim: int = 8,
        num_process_classes: int = 3,
        hidden_dim: int = 128,
        gnn_layers: int = 3,
        tau_sage: float = 1.0,
        edge_mlp_hidden: int = 256,
        edge_mlp_layers: int = 3,
        num_cell_types: int = 256,
        num_pin_roles: int = 64,
        beta: float = 1.0,
        scale_clamp: float = 3.0,
        tau_sta: float = 0.07,
        dropout: float = 0.0,
        residual_alpha: float = 0.5,
        d_floor: float = 0.0,
        # FiLM parameters
        use_film: bool = False,
        film_hidden: int = 128,
        film_gamma_scale: float = 0.5,
    ):
        super().__init__()
        self.K = num_anchors
        self.pin_dyn_dim = pin_dyn_dim
        self.d_floor = d_floor
        self.use_film = use_film

        # Process embedding
        self.process_embed = nn.Embedding(num_process_classes, process_embed_dim)
        cond_dim = process_embed_dim + z_cont_dim  # 8 + 4 = 12

        # Node input dim
        node_input_dim = pin_static_dim + num_anchors * pin_dyn_dim + cond_dim

        # 1. GNN (FiLM layers live inside GNN when use_film=True)
        self.gnn = GraphSAGEEncoder(
            input_dim=node_input_dim,
            hidden_dim=hidden_dim,
            num_layers=gnn_layers,
            tau=tau_sage,
            dropout=dropout,
            residual_alpha=residual_alpha,
            cond_dim=cond_dim if use_film else 0,
            use_film=use_film,
            film_hidden=film_hidden,
            film_gamma_scale=film_gamma_scale,
        )

        # 2. Edge head
        self.edge_head = EdgeHead(
            node_dim=hidden_dim,
            num_edge_types=2,
            num_cell_types=num_cell_types,
            num_pin_roles=num_pin_roles,
            mlp_hidden=edge_mlp_hidden,
            mlp_layers=edge_mlp_layers,
            edge_embed_dim=hidden_dim,
            cat_embed_dim=16,
            num_scalars=6,
            dropout=dropout,
        )

        # 2b. FiLM on EdgeHead output (modulate h_e before anchor_head)
        if use_film:
            self.film_edge = FiLMLayer(cond_dim, hidden_dim, film_hidden, film_gamma_scale)
        else:
            self.film_edge = None

        # 3. Multi-anchor head
        self.anchor_head = MultiAnchorHead(
            edge_dim=hidden_dim,
            cond_dim=cond_dim,
            num_anchors=num_anchors,
            num_channels=4,
            beta=beta,
            scale_clamp=scale_clamp,
        )

        # 4. STA
        self.sta = LevelwiseSTA(tau_sta=tau_sta)

    def forward(
        self,
        pin_static: torch.Tensor,
        pin_dyn_anchor: torch.Tensor,
        d_anchor: torch.Tensor,
        edge_src: torch.Tensor,
        edge_dst: torch.Tensor,
        edge_type: torch.Tensor,
        topo_order: torch.Tensor,
        node_level: torch.Tensor,
        data_mask: torch.Tensor,
        edge_valid: torch.Tensor,
        source_mask: torch.Tensor,
        endpoint_ids: torch.Tensor,
        rat_true: torch.Tensor,
        z_cont: torch.Tensor,
        process_id: torch.Tensor,
        edge_cell_type_src: torch.Tensor,
        edge_cell_type_dst: torch.Tensor,
        edge_pin_role_src: torch.Tensor,
        edge_pin_role_dst: torch.Tensor,
        edge_fanin_src: torch.Tensor,
        edge_fanout_src: torch.Tensor,
        edge_fanin_dst: torch.Tensor,
        edge_fanout_dst: torch.Tensor,
        edge_cap_src: torch.Tensor,
        edge_cap_dst: torch.Tensor,
        edge_scalars_normed: Optional[torch.Tensor] = None,
        sta_edge_keep: Optional[torch.Tensor] = None,  # [E] bool — cycle cuts
        at_true: Optional[torch.Tensor] = None,         # [N, 2] for teacher forcing
        tf_ratio: float = 0.0,                           # teacher forcing blend (0=off)
    ) -> ModelOutput:

        N = pin_static.shape[0]
        E = edge_src.shape[0]
        device = pin_static.device

        # ---- #2: Condition vector z_t (robust process_id + z_cont handling) ----
        process_id = process_id.long()
        if process_id.dim() == 0:
            process_id = process_id.unsqueeze(0)
        proc_emb = self.process_embed(process_id)[0]  # [embed_dim]

        z_cont = z_cont.float()
        if z_cont.dim() == 2:
            assert z_cont.size(0) == 1, f"Expected z_cont batch=1, got {z_cont.shape}"
            z_cont = z_cont[0]
        z_t = torch.cat([proc_emb, z_cont], dim=-1)  # [cond_dim=12]

        # ---- #4: Node input features (with shape checks) ----
        K = pin_dyn_anchor.shape[0]
        assert pin_dyn_anchor.dim() == 3 and pin_dyn_anchor.size(1) == N, (
            f"pin_dyn_anchor shape mismatch: {pin_dyn_anchor.shape}, expected [K, {N}, >=4]"
        )
        pin_dyn_flat = pin_dyn_anchor.permute(1, 0, 2).reshape(N, K * self.pin_dyn_dim)
        z_t_node = z_t.unsqueeze(0).expand(N, -1)
        # #1: z_t concatenated here (required for checkpoint 26-dim input_proj)
        #     FiLM provides additional adaptive modulation on top
        node_input = torch.cat([pin_static, pin_dyn_flat, z_t_node], dim=-1)

        # ---- GNN (FiLM applied internally when use_film=True) ----
        h_nodes = self.gnn(node_input, edge_src, edge_dst, cond=z_t)

        # ---- #9: Edge scalars (z-scored required, no silent fallback) ----
        if edge_scalars_normed is not None:
            edge_scalars = edge_scalars_normed
        else:
            import warnings
            warnings.warn(
                "edge_scalars_normed is None — using raw log1p (not z-scored). "
                "This may degrade accuracy if model was trained with z-scored scalars.",
                stacklevel=2,
            )
            edge_scalars = torch.stack([
                torch.log1p(edge_fanin_src.float().clamp(min=0)),
                torch.log1p(edge_fanout_src.float().clamp(min=0)),
                torch.log1p(edge_fanin_dst.float().clamp(min=0)),
                torch.log1p(edge_fanout_dst.float().clamp(min=0)),
                torch.log1p(edge_cap_src.float().clamp(min=0)),
                torch.log1p(edge_cap_dst.float().clamp(min=0)),
            ], dim=-1)

        # ---- Edge head ----
        h_edges = self.edge_head(
            h_nodes, edge_src, edge_dst, edge_type,
            edge_cell_type_src, edge_cell_type_dst,
            edge_pin_role_src, edge_pin_role_dst,
            edge_scalars,
        )

        # ---- FiLM on edge embeddings ----
        if self.film_edge is not None:
            h_edges = self.film_edge(h_edges, z_t)

        # ---- Multi-anchor delay prediction ----
        d_hat, g_e, gG, s_hat, log_scale = self.anchor_head(h_edges, z_t, d_anchor)

        # ---- #5: Physics-consistent input arrival ----
        source_mask = source_mask.bool()
        assert source_mask.shape == (N,), f"source_mask shape {source_mask.shape} != ({N},)"

        anchor_arrivals = pin_dyn_anchor[:, :, :2]
        gG_w = gG.view(K, 1, 1)
        fused_arrival = (gG_w * anchor_arrivals).sum(dim=0)

        input_arrival = torch.full((N, 2), NEG_INF, device=device)
        input_arrival[source_mask] = fused_arrival[source_mask]

        # ---- #7: STA mask (with shape check) ----
        assert data_mask.shape == (E, 4), f"data_mask shape {data_mask.shape} != ({E}, 4)"
        sta_mask = build_sta_mask(data_mask, edge_type, edge_valid, sta_edge_keep)

        # ---- #8: STA propagation (d_floor=0 → no clamp, rely on L_neg soft constraint) ----
        # Only hard-clamp when d_floor > 0 AND you see numerical instability.
        # Otherwise L_neg in loss provides differentiable constraint (gradients not truncated).
        d_sta = d_hat.clamp(min=-self.d_floor) if self.d_floor > 0 else d_hat

        # ---- Level-wise STA ----
        edge_level = node_level[edge_dst]
        max_level = int(node_level.max().item())

        at_all, at_ep, slack_hat = self.sta(
            d_sta, sta_mask, edge_src, edge_dst,
            input_arrival, endpoint_ids, rat_true,
            node_level, edge_level, max_level,
            at_true=at_true, tf_ratio=tf_ratio,
        )

        return ModelOutput(
            d_hat=d_hat, at_all=at_all, at_ep=at_ep, slack_hat=slack_hat,
            g_e=g_e, gG=gG, s_hat=s_hat, log_scale=log_scale,
        )
