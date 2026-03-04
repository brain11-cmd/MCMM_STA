"""Evaluation metrics for STA prediction (v4 — normalized, grouped)."""

from typing import Dict, List
import torch
import numpy as np


# ── Benchmark size groups ──

SMALL_BENCHMARKS = {"spi", "gcd", "uart"}
MEDIUM_BENCHMARKS = {"chameleon", "aes"}
LARGE_BENCHMARKS = {"mock-alu", "fifo", "dynamic_node", "jpeg"}

GROUP_MAP = {}
for _b in SMALL_BENCHMARKS:
    GROUP_MAP[_b] = "small"
for _b in MEDIUM_BENCHMARKS:
    GROUP_MAP[_b] = "medium"
for _b in LARGE_BENCHMARKS:
    GROUP_MAP[_b] = "large"


def _corner_family(corner: str) -> str:
    """Map a corner name to its process family (ff / tt / ss)."""
    c = corner.lower()
    if c.startswith("ff"):
        return "ff"
    elif c.startswith("ss"):
        return "ss"
    else:
        return "tt"


# ── Low-level metric helpers ──

def masked_mae(pred: torch.Tensor, target: torch.Tensor,
               mask: torch.Tensor) -> torch.Tensor:
    valid = mask.bool()
    if valid.sum() == 0:
        return torch.tensor(0.0, device=pred.device)
    return (pred[valid] - target[valid]).abs().mean()


def masked_rmse(pred: torch.Tensor, target: torch.Tensor,
                mask: torch.Tensor) -> torch.Tensor:
    valid = mask.bool()
    if valid.sum() == 0:
        return torch.tensor(0.0, device=pred.device)
    return ((pred[valid] - target[valid]) ** 2).mean().sqrt()


def masked_mape(pred: torch.Tensor, target: torch.Tensor,
                mask: torch.Tensor, eps: float = 1e-9) -> torch.Tensor:
    valid = mask.bool() & (target.abs() > eps)
    if valid.sum() == 0:
        return torch.tensor(0.0, device=pred.device)
    return ((pred[valid] - target[valid]).abs() /
            target[valid].abs()).mean() * 100.0


def slack_metrics(slack_pred: torch.Tensor,
                  slack_true: torch.Tensor,
                  min_ss_tot: float = 1e-6) -> Dict[str, float]:
    """MAE / RMSE / R² for endpoint slack (R²-stable)."""
    diff = slack_pred - slack_true
    mae = diff.abs().mean().item()
    rmse = (diff ** 2).mean().sqrt().item()

    ss_res = (diff ** 2).sum().item()
    mean_true = slack_true.mean()
    ss_tot = ((slack_true - mean_true) ** 2).sum().item()

    if ss_tot < min_ss_tot:
        r2 = float("nan")
    else:
        r2 = 1.0 - ss_res / (ss_tot + 1e-12)

    return {"slack_mae": mae, "slack_rmse": rmse, "slack_r2": r2}


def edge_delay_metrics(d_pred: torch.Tensor, d_true: torch.Tensor,
                       mask: torch.Tensor) -> Dict[str, float]:
    return {
        "edge_mae": masked_mae(d_pred, d_true, mask).item(),
        "edge_rmse": masked_rmse(d_pred, d_true, mask).item(),
    }


def slack_scale_p95(slack_true: torch.Tensor, floor: float = 0.1) -> float:
    """Robust per-sample slack scale = P95(|slack_gt|), clamped."""
    if slack_true.numel() == 0:
        return floor
    return max(torch.quantile(slack_true.abs().flatten(), 0.95).item(), floor)


# ── Normalized per-sample metrics ──

def normalized_slack_mae(slack_pred: torch.Tensor, slack_true: torch.Tensor,
                         scale: float) -> float:
    """MAE / scale — comparable across benchmarks."""
    if slack_pred.numel() == 0:
        return 0.0
    return ((slack_pred - slack_true).abs() / max(scale, 1e-6)).mean().item()


# ── Macro-averaged evaluation report ──

def compute_eval_report(per_sample: List[Dict]) -> Dict[str, float]:
    """Build the full multi-level evaluation report from per-sample dicts.

    Each element in *per_sample* must contain at least:
        benchmark, corner, slack_mae, slack_norm_mae, edge_mae

    Returns a flat dict with keys like:
        macro_norm_mae, small_norm_mae, large_norm_mae,
        ff_norm_mae, ss_norm_mae, fifo_norm_mae, fifo_abs_mae, ...
    """
    report: Dict[str, float] = {}

    # ── per-benchmark aggregation ──
    bm_norm: Dict[str, List[float]] = {}
    bm_abs: Dict[str, List[float]] = {}
    bm_edge: Dict[str, List[float]] = {}
    corner_norm: Dict[str, List[float]] = {}

    for s in per_sample:
        bm = s["benchmark"]
        nm = s.get("slack_norm_mae", 0.0)
        am = s.get("slack_mae", 0.0)
        em = s.get("edge_mae", 0.0)
        cf = _corner_family(s.get("corner", ""))

        bm_norm.setdefault(bm, []).append(nm)
        bm_abs.setdefault(bm, []).append(am)
        bm_edge.setdefault(bm, []).append(em)
        corner_norm.setdefault(cf, []).append(nm)

    # Per-benchmark averages
    bm_avg_norm = {bm: np.mean(v) for bm, v in bm_norm.items()}
    bm_avg_abs = {bm: np.mean(v) for bm, v in bm_abs.items()}

    # ── 1) Overall MacroMAE_norm ──
    if bm_avg_norm:
        report["macro_norm_mae"] = float(np.mean(list(bm_avg_norm.values())))
    else:
        report["macro_norm_mae"] = 0.0

    # ── 2) Group metrics ──
    for grp in ("small", "medium", "large"):
        vals = [bm_avg_norm[bm] for bm in bm_avg_norm if GROUP_MAP.get(bm) == grp]
        report[f"{grp}_norm_mae"] = float(np.mean(vals)) if vals else 0.0

    # ── 3) Big-benchmark individual report ──
    for bm in sorted(LARGE_BENCHMARKS | MEDIUM_BENCHMARKS):
        if bm in bm_avg_norm:
            report[f"{bm}_norm_mae"] = bm_avg_norm[bm]
            report[f"{bm}_abs_mae"] = bm_avg_abs.get(bm, 0.0)

    # ── 4) Corner-family breakdown ──
    for cf in ("ff", "tt", "ss"):
        vals = corner_norm.get(cf, [])
        report[f"{cf}_norm_mae"] = float(np.mean(vals)) if vals else 0.0

    # Large-group SS (the "disaster metric")
    large_ss = [
        s.get("slack_norm_mae", 0.0)
        for s in per_sample
        if GROUP_MAP.get(s["benchmark"]) == "large"
        and _corner_family(s.get("corner", "")) == "ss"
    ]
    report["large_ss_norm_mae"] = float(np.mean(large_ss)) if large_ss else 0.0

    return report
