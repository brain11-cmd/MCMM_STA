"""
STA Loss (v2.5 — negative-delay-aware, cell-arc-only edge loss).

Components:
  L_slack:  Huber(slack_hat - slack_true)
  L_edge:   asinh-Huber on valid CELL arcs only (net arcs excluded — consistent with STA mask)
  L_KL:     KL divergence of per-edge gates from global gate
  L_ent:    Low-entropy penalty on global gate (annealed)
  L_scale:  L2 on raw log_scale
  L_neg:    Squared penalty for d_hat < -d_floor (stronger barrier than linear)

v2.5 fixes over v2.4:
  - Edge loss only monitors cell arcs (net arcs excluded — matches STA mask semantics)
  - L_ent rewritten as 1-ent/max_ent (positive, more readable)
  - L_neg uses squared penalty (stronger barrier for extreme negatives)
  - g_e/gG clamp+renorm for numerical safety
  - Removed explicit expand_as (use broadcasting)
"""

import math
import torch
import torch.nn.functional as F
from typing import Dict


class STALoss:
    def __init__(
        self,
        huber_delta: float = 1.0,
        lambda_edge: float = 0.3,
        lambda_kl: float = 0.01,
        lambda_ent: float = 0.001,
        lambda_scale: float = 0.0001,
        # Negative delay parameters
        d_floor: float = 0.1,
        asinh_scale: float = 1.0,
        lambda_neg: float = 1e-4,
        lambda_at: float = 0.1,
    ):
        self.huber_delta = huber_delta
        self.lambda_edge = lambda_edge
        self.lambda_kl = lambda_kl
        self.lambda_ent = lambda_ent
        self.lambda_scale = lambda_scale
        self.d_floor = d_floor
        self.asinh_scale = asinh_scale
        self.lambda_neg = lambda_neg
        self.lambda_at = lambda_at

    def __call__(
        self,
        slack_hat: torch.Tensor,     # [M, 2]
        slack_true: torch.Tensor,    # [M, 2]
        d_hat: torch.Tensor,         # [E, 4]
        d_true: torch.Tensor,        # [E, 4]
        mask: torch.Tensor,          # [E, 4]
        edge_valid: torch.Tensor,    # [E]
        edge_type: torch.Tensor,     # [E] long — 0=cell, 1=net
        g_e: torch.Tensor,           # [E, K]
        gG: torch.Tensor,            # [K]
        log_scale: torch.Tensor,     # [E, K, 4]
        at_all: torch.Tensor = None, # [N, 2] predicted arrival (from STA)
        at_true: torch.Tensor = None, # [N, 2] ground truth arrival (Late R/F)
        epoch: int = 0,
        total_epochs: int = 200,
    ) -> Dict[str, torch.Tensor]:

        device = d_hat.device
        eps = 1e-8
        losses = {}

        # ---- 1. Slack loss (Huber) ----
        if slack_hat.numel() > 0:
            L_slack = F.huber_loss(slack_hat, slack_true, delta=self.huber_delta)
        else:
            L_slack = torch.tensor(0.0, device=device)
        losses["L_slack"] = L_slack

        # ---- 2. Edge delay loss (asinh-Huber, cell arcs only) ----
        # valid = mask>0 AND edge_valid>0 AND cell arc (not net)
        # Net arcs excluded from edge loss — consistent with STA mask semantics:
        #   STA forces net arcs to [1,0,0,1] regardless; edge loss shouldn't supervise them.
        is_cell = (edge_type == 0).unsqueeze(-1)   # [E, 1] broadcast
        valid = (mask > 0.5) & (edge_valid.unsqueeze(-1) > 0.5) & is_cell
        valid_count = valid.sum()

        if valid_count > 0:
            s = self.asinh_scale
            phi_hat = torch.asinh(d_hat / s)
            phi_true = torch.asinh(d_true / s)
            L_edge = F.huber_loss(phi_hat[valid], phi_true[valid], delta=self.huber_delta)
        else:
            L_edge = torch.tensor(0.0, device=device)
        losses["L_edge"] = L_edge
        losses["valid_count"] = valid_count

        # ---- 3. KL divergence (per-edge gates vs global gate) ----
        # Defensive: clamp + renormalize to ensure valid probabilities
        g_e_safe = g_e.clamp_min(eps)
        g_e_safe = g_e_safe / g_e_safe.sum(dim=-1, keepdim=True)
        gG_safe = gG.clamp_min(eps)
        gG_safe = gG_safe / gG_safe.sum()

        log_g_e = torch.log(g_e_safe)
        log_gG = torch.log(gG_safe).unsqueeze(0)
        L_kl = (g_e_safe * (log_g_e - log_gG)).sum(dim=-1).mean()
        losses["L_KL"] = L_kl

        # ---- 4. Low-entropy penalty (annealed) ----
        # L_ent = 1 - H(gG)/H_max  ∈ [0, 1]
        # Minimizing L_ent → maximizes entropy → encourages exploration
        # Decay: early epochs get full penalty, late epochs relax
        ent = -(gG_safe * torch.log(gG_safe)).sum()
        max_ent = math.log(gG.shape[0])
        ent_decay = max(1.0 - epoch / max(total_epochs * 0.8, 1), 0.0)
        L_ent = 1.0 - ent / (max_ent + eps)
        losses["L_ent"] = L_ent
        losses["ent_decay"] = torch.tensor(ent_decay, device=device)

        # ---- 5. Scale L2 regularization ----
        L_scale = (log_scale ** 2).mean()
        losses["L_scale"] = L_scale

        # ---- 6. Negative delay penalty (squared — stronger barrier) ----
        if self.lambda_neg > 0 and valid_count > 0:
            excess_neg = torch.relu(-(d_hat + self.d_floor))
            L_neg = (excess_neg[valid] ** 2).mean()
        else:
            L_neg = torch.tensor(0.0, device=device)
        losses["L_neg"] = L_neg

        # ---- 7. Arrival time supervision (non-source reachable nodes — dense signal) ----
        # Only supervise nodes where:
        #   - at_all > NEG_INF (reachable via STA propagation)
        #   - at_true has non-zero value (excludes sources / undriven pins)
        # Uses asinh-Huber (same as edge loss) to handle large-scale variance
        if self.lambda_at > 0 and at_all is not None and at_true is not None:
            at_valid = (at_all > -1e29) & (at_true.abs() > 1e-6)  # [N, 2]
            at_valid_count = at_valid.sum()
            if at_valid_count > 0:
                s = self.asinh_scale
                phi_at_hat = torch.asinh(at_all[at_valid] / s)
                phi_at_true = torch.asinh(at_true[at_valid] / s)
                L_at = F.huber_loss(phi_at_hat, phi_at_true, delta=self.huber_delta)
            else:
                L_at = torch.tensor(0.0, device=device)
        else:
            L_at = torch.tensor(0.0, device=device)
        losses["L_at"] = L_at

        # ---- Total ----
        total = (
            L_slack
            + self.lambda_edge * L_edge
            + self.lambda_kl * L_kl
            + self.lambda_ent * ent_decay * L_ent
            + self.lambda_scale * L_scale
            + self.lambda_neg * L_neg
            + self.lambda_at * L_at
        )
        losses["total"] = total

        return losses
