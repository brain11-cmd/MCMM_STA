"""
Multi-Anchor delay generation with two-level gating (v2.2).

v2.2 changes (checkpoint-compatible):
  - scale_mlp: added LayerNorm after each hidden Linear (matches checkpoint)
  - No clamp on d_anchor: d_hat can be negative (bounded STA handles it)
  - Returns raw log_scale for L2 regularization
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class MultiAnchorHead(nn.Module):
    def __init__(
        self,
        edge_dim: int = 128,
        cond_dim: int = 12,
        num_anchors: int = 3,
        num_channels: int = 4,
        beta: float = 1.0,
        scale_clamp: float = 3.0,
    ):
        super().__init__()
        self.K = num_anchors
        self.C = num_channels
        self.beta = beta
        self.scale_clamp = scale_clamp

        # Scale MLP with LayerNorm (matches checkpoint structure)
        # Checkpoint: 0(L),1(LN),2(ReLU),3(L),4(LN),5(ReLU),6(L)
        self.scale_mlp = nn.Sequential(
            nn.Linear(edge_dim + cond_dim, 256),
            nn.LayerNorm(256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.LayerNorm(128),
            nn.ReLU(),
            nn.Linear(128, num_anchors * num_channels),
        )

        # Global gate: condition-only (no LayerNorm — matches checkpoint)
        self.global_gate = nn.Sequential(
            nn.Linear(cond_dim, 64),
            nn.ReLU(),
            nn.Linear(64, num_anchors),
        )

        # Local gate: edge+condition (no LayerNorm — matches checkpoint)
        self.local_gate = nn.Sequential(
            nn.Linear(edge_dim + cond_dim, 128),
            nn.ReLU(),
            nn.Linear(128, num_anchors),
        )

    def forward(
        self,
        h_e: torch.Tensor,       # [E, edge_dim]
        z_t: torch.Tensor,       # [cond_dim]
        d_anchor: torch.Tensor,  # [K, E, 4]
    ) -> tuple:
        """
        Returns:
            d_hat:     [E, 4]  — predicted delay (can be negative)
            g_e:       [E, K]  — per-edge gate weights
            gG:        [K]     — global gate weights
            s_hat:     [E, K, 4] — scale factors (always positive)
            log_scale: [E, K, 4] — raw log-scale before exp (for L2 reg)
        """
        E = h_e.shape[0]
        eps = 1e-8

        if z_t.dim() == 2:
            z_t = z_t.squeeze(0)

        z_t_exp = z_t.unsqueeze(0).expand(E, -1)       # [E, cond_dim]
        he_zt = torch.cat([h_e, z_t_exp], dim=-1)      # [E, edge_dim + cond_dim]

        # Scale prediction: s_hat = exp(clamp(log_scale))
        # s_hat is always positive; d_anchor can be negative → d_hat can be negative
        log_scale = self.scale_mlp(he_zt).view(E, self.K, self.C)
        log_scale = log_scale.clamp(-self.scale_clamp, self.scale_clamp)
        s_hat = torch.exp(log_scale)

        # Two-level gating
        gG_logits = self.global_gate(z_t)               # [K]
        gG = F.softmax(gG_logits, dim=-1)               # [K]

        lL = self.local_gate(he_zt)                     # [E, K]

        log_gG = torch.log(gG + eps)                    # [K]
        gate_logits = log_gG.unsqueeze(0) + self.beta * lL  # [E, K]
        g_e = F.softmax(gate_logits, dim=-1)            # [E, K]

        # Fusion: d_hat = sum_k g_e[k] * s_hat[k] * d_anchor[k]
        # No clamp on d_anchor — negative delays are preserved
        d_anc = d_anchor.permute(1, 0, 2)               # [E, K, 4]
        scaled = s_hat * d_anc                           # [E, K, 4]
        g_e_exp = g_e.unsqueeze(-1)                      # [E, K, 1]
        d_hat = (g_e_exp * scaled).sum(dim=1)            # [E, 4]

        return d_hat, g_e, gG, s_hat, log_scale
