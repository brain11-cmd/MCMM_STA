"""
Feature normalization utilities.

Computes running mean/std from training data, applies z-score normalization,
and saves/loads stats to/from checkpoint.
"""

from typing import Dict, Optional, Tuple
import torch
import numpy as np


class FeatureNormalizer:
    """
    Accumulates mean/std over training set, then normalizes features.
    
    Usage:
        norm = FeatureNormalizer()
        # Pass 1: accumulate
        for batch in train_loader:
            norm.accumulate("pin_static", batch.pin_static)
            norm.accumulate("pin_dyn", batch.pin_dyn_anchor.reshape(-1, D))
        norm.finalize()
        # Pass 2 (or runtime): normalize
        x = norm.normalize("pin_static", batch.pin_static)
    """

    def __init__(self):
        self._accum: Dict[str, Dict] = {}   # key -> {sum, sq_sum, count}
        self._stats: Dict[str, Dict[str, torch.Tensor]] = {}  # key -> {mean, std}
        self._finalized = False

    def accumulate(self, key: str, x: torch.Tensor) -> None:
        """Accumulate a batch of feature vectors (any shape, last dim = feature)."""
        assert not self._finalized, "Already finalized"
        x = x.detach().float()
        flat = x.reshape(-1, x.shape[-1])  # [N, D]
        if key not in self._accum:
            D = flat.shape[-1]
            self._accum[key] = {
                "sum": torch.zeros(D, dtype=torch.float64),
                "sq_sum": torch.zeros(D, dtype=torch.float64),
                "count": 0,
            }
        acc = self._accum[key]
        acc["sum"] += flat.sum(dim=0).double()
        acc["sq_sum"] += (flat ** 2).sum(dim=0).double()
        acc["count"] += flat.shape[0]

    def finalize(self) -> None:
        """Compute mean/std from accumulated statistics."""
        for key, acc in self._accum.items():
            n = acc["count"]
            mean = (acc["sum"] / n).float()
            var = (acc["sq_sum"] / n - mean.double() ** 2).clamp(min=0).float()
            std = var.sqrt().clamp(min=1e-6)
            self._stats[key] = {"mean": mean, "std": std}
        self._finalized = True

    def normalize(self, key: str, x: torch.Tensor) -> torch.Tensor:
        """Apply z-score normalization: (x - mean) / std."""
        assert self._finalized, "Call finalize() first"
        s = self._stats[key]
        mean = s["mean"].to(x.device)
        std = s["std"].to(x.device)
        return (x - mean) / std

    def state_dict(self) -> Dict[str, Dict[str, torch.Tensor]]:
        return {k: {kk: vv.cpu() for kk, vv in v.items()}
                for k, v in self._stats.items()}

    def load_state_dict(self, sd: Dict[str, Dict[str, torch.Tensor]]) -> None:
        self._stats = sd
        self._finalized = True

    @property
    def is_ready(self) -> bool:
        return self._finalized




















