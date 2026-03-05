"""
Edge-aware Head (v2.2 — checkpoint-compatible, AMP-safe).

For each edge e = (u -> v), constructs a rich feature vector from:
  - Node interactions: [h_u, h_v, h_u*h_v, |h_u-h_v|, h_v-h_u]  (5 * node_dim)
  - Categorical embeddings: edge_type, cell_type_{s,d}, pin_role_{s,d}  (5 * embed_dim)
  - Edge scalar features: z-score normalized [fanin/fanout/cap at src/dst]  (6)

Total input = 5*128 + 5*16 + 6 = 726  (matches checkpoint)

v2.2 changes:
  - 5-component node interaction (signed diff h_v-h_u for directional info)
  - Defensive clamp on categorical IDs (prevents OOV crashes)
  - MLP with LayerNorm + Dropout (matches checkpoint layer indices)
  - Accepts pre-normalized edge_scalars (z-scored in train.py)
"""

import torch
import torch.nn as nn


class EdgeHead(nn.Module):
    """
    Edge feature constructor + MLP.

    Output: h_e [E, edge_embed_dim]
    """

    def __init__(
        self,
        node_dim: int,
        num_edge_types: int = 2,
        num_cell_types: int = 256,
        num_pin_roles: int = 64,
        mlp_hidden: int = 256,
        mlp_layers: int = 3,
        edge_embed_dim: int = 128,
        cat_embed_dim: int = 16,
        num_scalars: int = 6,
        dropout: float = 0.0,
    ):
        super().__init__()

        # Categorical embeddings (UNK = 0 reserved in vocab)
        self.emb_edge_type = nn.Embedding(num_edge_types, cat_embed_dim)
        self.emb_cell_type = nn.Embedding(num_cell_types, cat_embed_dim)
        self.emb_pin_role = nn.Embedding(num_pin_roles, cat_embed_dim)

        # Input: [h_u, h_v, h_u*h_v, |h_u-h_v|, h_v-h_u] + embeddings + scalars
        #      = 5*node_dim + 5*cat_embed_dim + num_scalars
        self.input_dim = 5 * node_dim + 5 * cat_embed_dim + num_scalars

        # MLP: (Linear + LayerNorm + ReLU + Dropout) × (layers-1) + Linear
        # Checkpoint indices: 0(L),1(LN),2(ReLU),3(Drop/Id), 4(L),5(LN),6(ReLU),7(Drop/Id), 8(L)
        layers = []
        in_d = self.input_dim
        for _ in range(mlp_layers - 1):
            layers.append(nn.Linear(in_d, mlp_hidden))
            layers.append(nn.LayerNorm(mlp_hidden))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(dropout) if dropout > 0 else nn.Identity())
            in_d = mlp_hidden
        layers.append(nn.Linear(in_d, edge_embed_dim))
        self.mlp = nn.Sequential(*layers)

    @staticmethod
    def _oov_to_unk(x: torch.Tensor, num_embeddings: int) -> torch.Tensor:
        """Map out-of-vocabulary IDs to UNK=0 (not clamp to last ID)."""
        return torch.where((x >= 0) & (x < num_embeddings), x, torch.zeros_like(x))

    def forward(
        self,
        h_nodes: torch.Tensor,          # [N, node_dim]
        edge_src: torch.Tensor,          # [E] long
        edge_dst: torch.Tensor,          # [E] long
        edge_type: torch.Tensor,         # [E] long
        cell_type_src: torch.Tensor,     # [E] long
        cell_type_dst: torch.Tensor,     # [E] long
        pin_role_src: torch.Tensor,      # [E] long
        pin_role_dst: torch.Tensor,      # [E] long
        edge_scalars: torch.Tensor,      # [E, 6] z-score normalized (or log1p)
    ) -> torch.Tensor:
        """Returns edge embeddings [E, edge_embed_dim]."""

        h_u = h_nodes[edge_src]   # [E, D]
        h_v = h_nodes[edge_dst]   # [E, D]
        dtype = h_u.dtype          # for AMP dtype alignment

        # 5-component node interaction
        h_prod = h_u * h_v                  # element-wise product
        h_abs_diff = (h_u - h_v).abs()       # magnitude of difference
        h_signed_diff = h_v - h_u            # directional: dst - src (STA flow)

        # OOV → UNK(0) (not clamp to last ID — that would pollute the last embedding)
        edge_type = self._oov_to_unk(edge_type, self.emb_edge_type.num_embeddings)
        cell_type_src = self._oov_to_unk(cell_type_src, self.emb_cell_type.num_embeddings)
        cell_type_dst = self._oov_to_unk(cell_type_dst, self.emb_cell_type.num_embeddings)
        pin_role_src = self._oov_to_unk(pin_role_src, self.emb_pin_role.num_embeddings)
        pin_role_dst = self._oov_to_unk(pin_role_dst, self.emb_pin_role.num_embeddings)

        # Categorical embeddings (cast to h_u dtype for AMP compatibility)
        e_et = self.emb_edge_type(edge_type).to(dtype)
        e_ct_s = self.emb_cell_type(cell_type_src).to(dtype)
        e_ct_d = self.emb_cell_type(cell_type_dst).to(dtype)
        e_pr_s = self.emb_pin_role(pin_role_src).to(dtype)
        e_pr_d = self.emb_pin_role(pin_role_dst).to(dtype)

        # Clamp extreme scalar values (long-tail cap/load can blow up MLP)
        edge_scalars = edge_scalars.to(dtype).clamp(-10.0, 10.0)

        # Concatenate: 5*node_dim + 5*emb_dim + num_scalars
        feat = torch.cat([
            h_u, h_v, h_prod, h_abs_diff, h_signed_diff,
            e_et, e_ct_s, e_ct_d, e_pr_s, e_pr_d,
            edge_scalars,
        ], dim=-1)   # [E, input_dim]

        assert feat.shape[-1] == self.input_dim, (
            f"EdgeHead input dim mismatch: got {feat.shape[-1]}, expected {self.input_dim}"
        )

        return self.mlp(feat)   # [E, edge_embed_dim]


class DualEdgeHead(nn.Module):
    """
    Dual-branch edge head: separate MLPs for cell arcs and net arcs.

    Cell arcs (combinational/sequential logic delay) have 4 active channels
    (RR/RF/FR/FF) and receive direct supervision via L_edge.
    Net arcs (wire delay) only use RR/FF and are supervised indirectly
    through STA propagation losses (L_slack, L_at).

    Splitting eliminates gradient interference between these fundamentally
    different delay distributions.  Categorical embeddings are shared.
    """

    def __init__(
        self,
        node_dim: int,
        num_edge_types: int = 2,
        num_cell_types: int = 256,
        num_pin_roles: int = 64,
        cell_mlp_hidden: int = 192,
        net_mlp_hidden: int = 128,
        edge_embed_dim: int = 128,
        cat_embed_dim: int = 16,
        num_scalars: int = 6,
        dropout: float = 0.0,
    ):
        super().__init__()
        self.edge_embed_dim = edge_embed_dim

        self.emb_edge_type = nn.Embedding(num_edge_types, cat_embed_dim)
        self.emb_cell_type = nn.Embedding(num_cell_types, cat_embed_dim)
        self.emb_pin_role = nn.Embedding(num_pin_roles, cat_embed_dim)

        self.input_dim = 5 * node_dim + 5 * cat_embed_dim + num_scalars

        self.cell_mlp = nn.Sequential(
            nn.Linear(self.input_dim, cell_mlp_hidden),
            nn.LayerNorm(cell_mlp_hidden),
            nn.ReLU(),
            nn.Dropout(dropout) if dropout > 0 else nn.Identity(),
            nn.Linear(cell_mlp_hidden, edge_embed_dim),
        )

        self.net_mlp = nn.Sequential(
            nn.Linear(self.input_dim, net_mlp_hidden),
            nn.LayerNorm(net_mlp_hidden),
            nn.ReLU(),
            nn.Dropout(dropout) if dropout > 0 else nn.Identity(),
            nn.Linear(net_mlp_hidden, edge_embed_dim),
        )

    @staticmethod
    def _oov_to_unk(x: torch.Tensor, num_embeddings: int) -> torch.Tensor:
        return torch.where((x >= 0) & (x < num_embeddings), x, torch.zeros_like(x))

    def forward(
        self,
        h_nodes: torch.Tensor,
        edge_src: torch.Tensor,
        edge_dst: torch.Tensor,
        edge_type: torch.Tensor,
        cell_type_src: torch.Tensor,
        cell_type_dst: torch.Tensor,
        pin_role_src: torch.Tensor,
        pin_role_dst: torch.Tensor,
        edge_scalars: torch.Tensor,
    ) -> torch.Tensor:
        h_u = h_nodes[edge_src]
        h_v = h_nodes[edge_dst]
        dtype = h_u.dtype

        h_prod = h_u * h_v
        h_abs_diff = (h_u - h_v).abs()
        h_signed_diff = h_v - h_u

        edge_type_safe = self._oov_to_unk(edge_type, self.emb_edge_type.num_embeddings)
        cell_type_src = self._oov_to_unk(cell_type_src, self.emb_cell_type.num_embeddings)
        cell_type_dst = self._oov_to_unk(cell_type_dst, self.emb_cell_type.num_embeddings)
        pin_role_src = self._oov_to_unk(pin_role_src, self.emb_pin_role.num_embeddings)
        pin_role_dst = self._oov_to_unk(pin_role_dst, self.emb_pin_role.num_embeddings)

        e_et = self.emb_edge_type(edge_type_safe).to(dtype)
        e_ct_s = self.emb_cell_type(cell_type_src).to(dtype)
        e_ct_d = self.emb_cell_type(cell_type_dst).to(dtype)
        e_pr_s = self.emb_pin_role(pin_role_src).to(dtype)
        e_pr_d = self.emb_pin_role(pin_role_dst).to(dtype)

        edge_scalars = edge_scalars.to(dtype).clamp(-10.0, 10.0)

        feat = torch.cat([
            h_u, h_v, h_prod, h_abs_diff, h_signed_diff,
            e_et, e_ct_s, e_ct_d, e_pr_s, e_pr_d,
            edge_scalars,
        ], dim=-1)

        cell_mask = (edge_type == 0)
        net_mask = (edge_type == 1)

        h_edges = torch.zeros(feat.shape[0], self.edge_embed_dim,
                              device=feat.device, dtype=dtype)

        if cell_mask.any():
            h_edges[cell_mask] = self.cell_mlp(feat[cell_mask])
        if net_mask.any():
            h_edges[net_mask] = self.net_mlp(feat[net_mask])

        return h_edges
