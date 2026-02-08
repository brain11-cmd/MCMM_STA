"""Evaluation metrics for STA prediction."""

from typing import Dict
import torch
import numpy as np


def masked_mae(pred: torch.Tensor, target: torch.Tensor,
               mask: torch.Tensor) -> torch.Tensor:
    """MAE over valid (mask=1) entries."""
    valid = mask.bool()
    if valid.sum() == 0:
        return torch.tensor(0.0, device=pred.device)
    return (pred[valid] - target[valid]).abs().mean()


def masked_rmse(pred: torch.Tensor, target: torch.Tensor,
                mask: torch.Tensor) -> torch.Tensor:
    """RMSE over valid entries."""
    valid = mask.bool()
    if valid.sum() == 0:
        return torch.tensor(0.0, device=pred.device)
    return ((pred[valid] - target[valid]) ** 2).mean().sqrt()


def masked_mape(pred: torch.Tensor, target: torch.Tensor,
                mask: torch.Tensor, eps: float = 1e-9) -> torch.Tensor:
    """MAPE (%) over valid entries where |target| > eps."""
    valid = mask.bool() & (target.abs() > eps)
    if valid.sum() == 0:
        return torch.tensor(0.0, device=pred.device)
    return ((pred[valid] - target[valid]).abs() /
            target[valid].abs()).mean() * 100.0


def slack_metrics(slack_pred: torch.Tensor,
                  slack_true: torch.Tensor) -> Dict[str, float]:
    """
    Compute MAE / RMSE / R² for endpoint slack.
    
    Args:
        slack_pred: [M, 2] predicted (LateR, LateF)
        slack_true: [M, 2] ground-truth
    Returns:
        dict with slack_mae, slack_rmse, slack_r2
    """
    diff = slack_pred - slack_true
    mae = diff.abs().mean().item()
    rmse = (diff ** 2).mean().sqrt().item()

    # R² (coefficient of determination)
    ss_res = (diff ** 2).sum().item()
    mean_true = slack_true.mean()
    ss_tot = ((slack_true - mean_true) ** 2).sum().item()
    r2 = 1.0 - ss_res / (ss_tot + 1e-12)

    return {"slack_mae": mae, "slack_rmse": rmse, "slack_r2": r2}


def edge_delay_metrics(d_pred: torch.Tensor, d_true: torch.Tensor,
                       mask: torch.Tensor) -> Dict[str, float]:
    """
    Compute edge-delay MAE / RMSE over valid channels.
    
    Args:
        d_pred, d_true: [E, 4]
        mask: [E, 4]
    """
    return {
        "edge_mae": masked_mae(d_pred, d_true, mask).item(),
        "edge_rmse": masked_rmse(d_pred, d_true, mask).item(),
    }








