"""
Full model: Physics-Informed Multi-Anchor GNN STA (v3.0).

v3.0 changes:
  - PVTEncoder: separable additive P/V/T conditioning (z_pvt = e_p + e_v + e_t)
  - DualEdgeHead: separate cell/net MLPs (eliminates gradient interference)
  - Global token: mean-pool → shared projection in GNN (long-range context)
  - z_t (concat) kept for node input; z_pvt (additive) used for conditioning

Architecture:
  process_embed: Embedding(3, 8)         [node input]
  pvt_encoder:   PVTEncoder(3 → 16)      [conditioning]
  gnn:           GraphSAGEEncoder(26 → 128, 3 layers, optional global token)
  edge_head:     DualEdgeHead(cell: 726→192→128, net: 726→128→128)
  anchor_head:   MultiAnchorHead(144 → d_hat[E,4])
  sta:           LevelwiseSTA (no learnable params)
  endpoint_res:  EndpointResidualHead(144 → delta_slack[M,2])
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import torch
import torch.nn as nn

from models.gnn import GraphSAGEEncoder
from models.edge_head import EdgeHead, DualEdgeHead
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
    delta_slack: Optional[torch.Tensor] = None  # [M, 2] endpoint residual


class PVTEncoder(nn.Module):
    """Separable PVT condition encoder.

    Produces z_pvt = e_p + e_v + e_t via additive decomposition, enforcing
    the physical prior that process, voltage, and temperature effects on
    delay are approximately separable.  Improves generalization to unseen
    PVT combinations compared to flat concatenation.
    """

    def __init__(self, num_processes: int = 3, pvt_dim: int = 16):
        super().__init__()
        self.pvt_dim = pvt_dim
        self.proc_embed = nn.Embedding(num_processes, pvt_dim)
        self.v_proj = nn.Linear(1, pvt_dim)
        self.t_proj = nn.Linear(1, pvt_dim)

    def forward(self, process_id: torch.Tensor,
                v_norm: torch.Tensor, t_norm: torch.Tensor) -> torch.Tensor:
        """
        Args:
            process_id: scalar or [1] long (0=ff, 1=tt, 2=ss)
            v_norm:     scalar float (normalized voltage)
            t_norm:     scalar float (normalized temperature)
        Returns:
            z_pvt: [pvt_dim] float
        """
        process_id = process_id.long()
        if process_id.dim() == 0:
            process_id = process_id.unsqueeze(0)
        e_p = self.proc_embed(process_id)[0]      # [pvt_dim]
        e_v = self.v_proj(v_norm.float().view(1))  # [pvt_dim]
        e_t = self.t_proj(t_norm.float().view(1))  # [pvt_dim]
        return e_p + e_v + e_t                     # [pvt_dim]


class EndpointResidualHead(nn.Module):
    """Lightweight MLP that predicts a per-endpoint slack correction.

    Zero-initialized output layer so the residual starts at 0, letting the
    physics-based STA dominate early training.  Only endpoints with persistent
    systematic bias (deep-graph error accumulation) will develop non-zero
    corrections over time.
    """

    def __init__(self, hidden_dim: int, cond_dim: int, dropout: float = 0.0):
        super().__init__()
        self.mlp = nn.Sequential(
            nn.Linear(hidden_dim + cond_dim, hidden_dim // 2),
            nn.LayerNorm(hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout) if dropout > 0 else nn.Identity(),
            nn.Linear(hidden_dim // 2, 2),
        )
        nn.init.zeros_(self.mlp[-1].weight)
        nn.init.zeros_(self.mlp[-1].bias)

    def forward(self, h_nodes: torch.Tensor, endpoint_ids: torch.Tensor,
                z_t: torch.Tensor) -> torch.Tensor:
        h_ep = h_nodes[endpoint_ids]
        z_ep = z_t.unsqueeze(0).expand(h_ep.size(0), -1)
        return self.mlp(torch.cat([h_ep, z_ep], dim=-1))


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
        tf_interval: int = 20,
        dropout: float = 0.0,
        gnn_dropout: float = None,
        residual_alpha: float = 0.5,
        d_floor: float = 0.0,
        # FiLM parameters
        use_film: bool = False,
        film_hidden: int = 128,
        film_gamma_scale: float = 0.5,
        # Endpoint residual head
        use_endpoint_residual: bool = False,
        # v9: PVT separable conditioning
        pvt_dim: int = 16,
        # v9: Cell/Net dual edge head
        use_dual_edge_head: bool = False,
        cell_mlp_hidden: int = 192,
        net_mlp_hidden: int = 128,
        # v9: Global token
        use_global_token: bool = False,
    ):
        super().__init__()
        self.K = num_anchors
        self.pin_dyn_dim = pin_dyn_dim
        self.d_floor = d_floor
        self.use_film = use_film

        # Process embedding (for node input concatenation — unchanged)
        self.process_embed = nn.Embedding(num_process_classes, process_embed_dim)
        node_cond_dim = process_embed_dim + z_cont_dim  # 8 + 4 = 12

        # PVT separable encoder (for conditioning: gates, FiLM, residual head)
        self.pvt_encoder = PVTEncoder(num_process_classes, pvt_dim)
        cond_dim = pvt_dim  # conditioning dimension for downstream modules

        # Node input dim (uses node_cond_dim, NOT pvt_dim)
        node_input_dim = pin_static_dim + num_anchors * pin_dyn_dim + node_cond_dim

        gnn_drop = gnn_dropout if gnn_dropout is not None else dropout

        # 1. GNN (FiLM layers live inside GNN when use_film=True)
        self.gnn = GraphSAGEEncoder(
            input_dim=node_input_dim,
            hidden_dim=hidden_dim,
            num_layers=gnn_layers,
            tau=tau_sage,
            dropout=gnn_drop,
            residual_alpha=residual_alpha,
            cond_dim=cond_dim if use_film else 0,
            use_film=use_film,
            film_hidden=film_hidden,
            film_gamma_scale=film_gamma_scale,
            use_global_token=use_global_token,
        )

        # 2. Edge head (dual or single)
        if use_dual_edge_head:
            self.edge_head = DualEdgeHead(
                node_dim=hidden_dim,
                num_cell_types=num_cell_types,
                num_pin_roles=num_pin_roles,
                cell_mlp_hidden=cell_mlp_hidden,
                net_mlp_hidden=net_mlp_hidden,
                edge_embed_dim=hidden_dim,
                cat_embed_dim=16,
                num_scalars=6,
                dropout=dropout,
            )
        else:
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

        # 3. Multi-anchor head (uses pvt cond_dim)
        self.anchor_head = MultiAnchorHead(
            edge_dim=hidden_dim,
            cond_dim=cond_dim,
            num_anchors=num_anchors,
            num_channels=4,
            beta=beta,
            scale_clamp=scale_clamp,
        )

        # 4. STA
        self.sta = LevelwiseSTA(tau_sta=tau_sta, tf_interval=tf_interval)

        # 5. Endpoint residual head (uses pvt cond_dim)
        if use_endpoint_residual:
            self.endpoint_residual = EndpointResidualHead(
                hidden_dim, cond_dim, dropout=dropout,
            )
        else:
            self.endpoint_residual = None

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
        at_true: Optional[torch.Tensor] = None,
        tf_ratio: float = 0.0,
    ) -> ModelOutput:

        N = pin_static.shape[0]
        E = edge_src.shape[0]
        device = pin_static.device

        # ---- #2: Condition vectors ----
        process_id = process_id.long()
        if process_id.dim() == 0:
            process_id = process_id.unsqueeze(0)
        proc_emb = self.process_embed(process_id)[0]  # [embed_dim=8]

        z_cont = z_cont.float()
        if z_cont.dim() == 2:
            assert z_cont.size(0) == 1, f"Expected z_cont batch=1, got {z_cont.shape}"
            z_cont = z_cont[0]

        # z_t: flat concat for node input (backward-compatible structure)
        z_t = torch.cat([proc_emb, z_cont], dim=-1)  # [node_cond_dim=12]

        # z_pvt: separable additive encoding for conditioning (gates, FiLM, residual)
        v_norm = z_cont[2]   # voltage_norm
        t_norm = z_cont[3]   # temp_norm
        z_pvt = self.pvt_encoder(process_id, v_norm, t_norm)  # [pvt_dim]

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
        h_nodes = self.gnn(node_input, edge_src, edge_dst, cond=z_pvt)

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
            h_edges = self.film_edge(h_edges, z_pvt)

        # ---- Multi-anchor delay prediction ----
        d_hat, g_e, gG, s_hat, log_scale = self.anchor_head(h_edges, z_pvt, d_anchor)

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

        at_all, at_ep, slack_sta = self.sta(
            d_sta, sta_mask, edge_src, edge_dst,
            input_arrival, endpoint_ids, rat_true,
            node_level, edge_level, max_level,
            at_true=at_true, tf_ratio=tf_ratio,
        )

        # Endpoint residual correction (absorbs deep-graph systematic bias)
        delta_slack = None
        if self.endpoint_residual is not None:
            delta_slack = self.endpoint_residual(h_nodes, endpoint_ids, z_pvt)
            slack_hat = slack_sta + delta_slack
        else:
            slack_hat = slack_sta

        return ModelOutput(
            d_hat=d_hat, at_all=at_all, at_ep=at_ep, slack_hat=slack_hat,
            g_e=g_e, gG=gG, s_hat=s_hat, log_scale=log_scale,
            delta_slack=delta_slack,
        )
