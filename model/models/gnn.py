"""
GraphSAGE with LogSumExp aggregation (v2.4 — AMP-safe + FiLM modes).

Each layer:
  1. Aggregate neighbor features using numerically-stable LogSumExp
  2. Concatenate [self_feat, agg_feat]
  3. Linear + LayerNorm + ReLU + Dropout
  4. (Optional) FiLM modulation: h = h * (1 + α·γ(z)) + α·β(z)

v2.4 changes:
  - film_mode parameter: "full" (FiLM on input + every layer) or
    "head_only" (no FiLM inside GNN — keeps backbone corner-agnostic)
  - Strength parameter forwarded to FiLM layers (for warmup)
  - Backward-compatible: cond=None or use_film=False disables FiLM
"""

from typing import Optional

import torch
import torch.nn as nn

from models.film import FiLMLayer


def scatter_logsumexp(
    src: torch.Tensor,
    index: torch.Tensor,
    dim_size: int,
    tau: float = 1.0,
    eps: float = 1e-30,
    normalize_by_degree: bool = False,
) -> torch.Tensor:
    """
    Numerically-stable LogSumExp scatter aggregation (pure PyTorch, AMP-safe).

    All internal accumulation is done in fp32 for numerical stability.

    Args:
        src:      [E, D]  feature of each neighbor occurrence
        index:    [E]     target node index (must be torch.long)
        dim_size: number of target nodes (N)
        tau:      temperature (default 1.0)
        eps:      clamp floor for log (default 1e-30)
        normalize_by_degree: if True, use logmeanexp (subtract tau*log(deg))

    Returns:
        out: [dim_size, D]  (same dtype as src)
    """
    assert index.dtype == torch.long, f"index must be torch.long, got {index.dtype}"
    assert src.dim() == 2 and index.dim() == 1 and src.size(0) == index.size(0)

    orig_dtype = src.dtype
    N, D = dim_size, src.size(1)
    device = src.device

    # contiguous() prevents hidden copies from non-contiguous views
    src = src.contiguous()
    index = index.contiguous()

    scaled = src.float() / float(tau)
    idx_exp = index.unsqueeze(-1).expand(-1, D)

    max_val = torch.full((N, D), float("-inf"), device=device, dtype=torch.float32)
    max_val.scatter_reduce_(0, idx_exp, scaled, reduce="amax", include_self=False)

    exp_val = torch.exp(scaled - max_val[index])

    sum_exp = torch.zeros((N, D), device=device, dtype=torch.float32)
    sum_exp.scatter_add_(0, idx_exp, exp_val)

    out = float(tau) * (max_val + torch.log(sum_exp.clamp_min(eps)))

    if normalize_by_degree:
        deg = torch.bincount(index, minlength=N).float().to(device)
        out = out - float(tau) * torch.log(deg.clamp_min(1.0)).unsqueeze(-1)

    has_nbr = torch.bincount(index, minlength=N) > 0
    out[~has_nbr] = 0.0

    return out.to(dtype=orig_dtype)


class GraphSAGELayer(nn.Module):
    """
    One GraphSAGE layer with LogSumExp aggregation.
    h_v^{l+1} = ReLU( LN( W * [h_v^l || LSE_agg(h_u^l)] ) )
    """

    def __init__(self, in_dim: int, out_dim: int, tau: float = 1.0, dropout: float = 0.0):
        super().__init__()
        self.tau = tau
        self.linear = nn.Linear(2 * in_dim, out_dim)
        self.norm = nn.LayerNorm(out_dim)
        self.drop = nn.Dropout(dropout) if dropout > 0 else nn.Identity()

    def forward(self, x: torch.Tensor, edge_src: torch.Tensor, edge_dst: torch.Tensor) -> torch.Tensor:
        N = x.shape[0]
        src_feat = x[edge_src]
        agg = scatter_logsumexp(src_feat, edge_dst, dim_size=N, tau=self.tau)
        h = torch.cat([x, agg], dim=-1)
        h = self.linear(h)
        h = self.norm(h)
        h = torch.relu(h)
        h = self.drop(h)
        return h


class GraphSAGEEncoder(nn.Module):
    """
    Multi-layer GraphSAGE encoder with residual connections and optional FiLM.

    film_mode controls where FiLM is applied:
      "full":      FiLM on input_proj + after each GNN layer (original behavior)
      "head_only": No FiLM inside GNN — backbone stays corner-agnostic.
                   FiLM is only used externally (e.g. on edge head output).

    When use_film=False or cond=None: pure GraphSAGE (backward-compatible).
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 128,
        num_layers: int = 3,
        tau: float = 1.0,
        dropout: float = 0.0,
        residual_alpha: float = 0.5,
        # FiLM parameters
        cond_dim: int = 0,
        use_film: bool = False,
        film_mode: str = "full",
        film_hidden: int = 128,
        film_gamma_scale: float = 0.5,
        # Global token
        use_global_token: bool = False,
    ):
        super().__init__()
        self.input_proj = nn.Linear(input_dim, hidden_dim)
        self.residual_alpha = residual_alpha
        self.use_film = use_film
        self.film_mode = film_mode

        self.layers = nn.ModuleList([
            GraphSAGELayer(hidden_dim, hidden_dim, tau=tau, dropout=dropout)
            for _ in range(num_layers)
        ])

        # FiLM layers: only created when use_film=True AND film_mode="full"
        gnn_needs_film = use_film and cond_dim > 0 and film_mode == "full"
        if gnn_needs_film:
            self.film_in = FiLMLayer(cond_dim, hidden_dim, film_hidden, film_gamma_scale)
            self.film_layers = nn.ModuleList([
                FiLMLayer(cond_dim, hidden_dim, film_hidden, film_gamma_scale)
                for _ in range(num_layers)
            ])
        else:
            self.film_in = None
            self.film_layers = None

        # Global token: mean-pool → shared projection → add back (zero-init for safe startup)
        if use_global_token:
            self.global_proj = nn.Linear(hidden_dim, hidden_dim, bias=False)
            nn.init.zeros_(self.global_proj.weight)
        else:
            self.global_proj = None

    def forward(
        self,
        x: torch.Tensor,
        edge_src: torch.Tensor,
        edge_dst: torch.Tensor,
        cond: Optional[torch.Tensor] = None,
        film_strength: float = 1.0,
    ) -> torch.Tensor:
        """
        Args:
            x:             [N, input_dim]
            edge_src:      [E]
            edge_dst:      [E]
            cond:          [cond_dim] condition vector for FiLM (optional)
            film_strength: scalar in [0, 1] for FiLM warmup
        Returns:
            h: [N, hidden_dim]
        """
        h = self.input_proj(x)

        # Align cond dtype/device (defense in depth — FiLMLayer also does this)
        if cond is not None:
            cond = cond.to(device=h.device, dtype=h.dtype)

        # FiLM on input projection (only in "full" mode)
        if self.film_in is not None and cond is not None:
            h = self.film_in(h, cond, strength=film_strength)

        alpha = min(max(float(self.residual_alpha), 0.0), 1.0)
        for i, layer in enumerate(self.layers):
            h_new = layer(h, edge_src, edge_dst)
            h = alpha * h + (1.0 - alpha) * h_new

            # FiLM after residual (only in "full" mode)
            if self.film_layers is not None and cond is not None:
                h = self.film_layers[i](h, cond, strength=film_strength)

            # Global token: broadcast graph-level summary to all nodes
            if self.global_proj is not None:
                g = h.mean(dim=0, keepdim=True)   # [1, D]
                h = h + self.global_proj(g)        # [N, D]

        return h
