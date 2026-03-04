"""
STA Loss (v5 — scale-matched L_at, disjoint L_slack/L_worst).

Components:
  L_slack:  Per-sample-normalized Huber on non-worst endpoints
  L_worst:  Per-sample-normalized Huber on top-k worst endpoints (disjoint from L_slack)
  L_edge:   asinh-Huber on valid CELL arcs only (net arcs excluded)
  L_KL:     KL divergence of per-edge gates from global gate
  L_ent:    Low-entropy penalty on global gate (annealed)
  L_scale:  L2 on raw log_scale
  L_neg:    Squared penalty for d_hat < -d_floor
  L_at:     Per-sample-normalized arrival time supervision (dense signal)

v5 changes over v4:
  - L_at now uses per-sample P95 normalization (same philosophy as L_slack),
    preventing arrival-time gradients from dominating when AT range >> slack range.
  - L_slack and L_worst are disjoint: L_slack = mean(non-top-k), L_worst = mean(top-k).
    No endpoint gets double-counted. lambda_worst directly controls the extra
    weight on worst endpoints, making tuning more predictable.
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
        d_floor: float = 0.1,
        asinh_scale: float = 1.0,
        lambda_neg: float = 1e-4,
        lambda_at: float = 0.05,
        lambda_worst: float = 0.3,
        worst_frac: float = 0.2,
        worst_warmup_ratio: float = 0.3,
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
        self.lambda_worst = lambda_worst
        self.worst_frac = worst_frac
        self.worst_warmup_ratio = worst_warmup_ratio

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

        # ---- 1. Disjoint slack / worst losses (per-sample normalized Huber) ----
        #
        # Split endpoints into two disjoint sets:
        #   top-k (by error magnitude) → L_worst
        #   remaining                  → L_slack
        # This prevents double-counting and makes lambda_worst a clean knob:
        #   effective weight on worst endpoints = lambda_worst
        #   effective weight on normal endpoints = 1.0
        if slack_hat.numel() > 0:
            slack_scale = torch.quantile(
                slack_true.abs().flatten(), 0.95
            ).clamp(min=0.1).detach()

            per_ep_err = F.huber_loss(
                slack_hat / slack_scale, slack_true / slack_scale,
                delta=self.huber_delta, reduction="none",
            ).mean(dim=-1)  # [M]

            M = per_ep_err.numel()
            k = max(1, int(M * self.worst_frac))
            k = min(k, M)

            _, topk_idx = torch.topk(per_ep_err, k=k, largest=True)

            if self.lambda_worst > 0 and k < M:
                topk_mask = torch.zeros(M, dtype=torch.bool, device=device)
                topk_mask[topk_idx] = True

                L_slack = per_ep_err[~topk_mask].mean()
                L_worst_raw = per_ep_err[topk_mask].mean()

                warmup_steps = max(int(total_epochs * self.worst_warmup_ratio), 1)
                warm = min(max((epoch + 1) / warmup_steps, 0.0), 1.0)
                L_worst = L_worst_raw * warm
            else:
                L_slack = per_ep_err.mean()
                L_worst = torch.tensor(0.0, device=device)
        else:
            slack_scale = torch.tensor(1.0, device=device)
            L_slack = torch.tensor(0.0, device=device)
            L_worst = torch.tensor(0.0, device=device)

        losses["L_slack"] = L_slack
        losses["L_worst"] = L_worst
        losses["slack_scale"] = slack_scale.detach()

        # ---- 2. Edge delay loss (asinh-Huber, cell arcs only) ----
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
        g_e_safe = g_e.clamp_min(eps)
        g_e_safe = g_e_safe / g_e_safe.sum(dim=-1, keepdim=True)
        gG_safe = gG.clamp_min(eps)
        gG_safe = gG_safe / gG_safe.sum()

        log_g_e = torch.log(g_e_safe)
        log_gG = torch.log(gG_safe).unsqueeze(0)
        L_kl = (g_e_safe * (log_g_e - log_gG)).sum(dim=-1).mean()
        losses["L_KL"] = L_kl

        # ---- 4. Low-entropy penalty (annealed) ----
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

        # ---- 7. Arrival time supervision (per-sample normalized) ----
        # Same normalization philosophy as L_slack: use P95(|at_true|) as scale
        # to keep L_at in the same magnitude band as L_slack (~0.x).
        # Without this, raw AT values (0~100+ns) after asinh produce L_at >> L_slack
        # and AT gradients dominate the training signal.
        if self.lambda_at > 0 and at_all is not None and at_true is not None:
            at_valid = (at_all > -1e29) & (at_true.abs() > 1e-6)  # [N, 2]
            at_valid_count = at_valid.sum()
            if at_valid_count > 0:
                at_scale = torch.quantile(
                    at_true[at_valid].abs(), 0.95
                ).clamp(min=0.1).detach()

                at_hat_norm = at_all[at_valid] / at_scale
                at_true_norm = at_true[at_valid] / at_scale
                L_at = F.huber_loss(at_hat_norm, at_true_norm, delta=self.huber_delta)
            else:
                at_scale = torch.tensor(1.0, device=device)
                L_at = torch.tensor(0.0, device=device)
        else:
            at_scale = torch.tensor(1.0, device=device)
            L_at = torch.tensor(0.0, device=device)
        losses["L_at"] = L_at
        losses["at_scale"] = at_scale.detach() if isinstance(at_scale, torch.Tensor) else torch.tensor(at_scale, device=device)

        # ---- Total ----
        total = (
            L_slack
            + self.lambda_edge * L_edge
            + self.lambda_kl * L_kl
            + self.lambda_ent * ent_decay * L_ent
            + self.lambda_scale * L_scale
            + self.lambda_neg * L_neg
            + self.lambda_at * L_at
            + self.lambda_worst * L_worst
        )
        losses["total"] = total

        return losses
