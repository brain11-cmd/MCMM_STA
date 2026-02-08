#!/usr/bin/env python3
"""
Training script for Physics-Informed Multi-Anchor GNN STA (v2).

v2 changes:
  - process_id embedding (separate from z_cont)
  - Physics-consistent source initialization (no learned input_arrival_head)
  - edge_valid=0 excluded from STA propagation
  - Scale L2 reg, entropy annealing
  - Slack consistency assertion on first batch
"""

import argparse
import math
import sys
import time
from pathlib import Path
from typing import Dict, Optional

import yaml
import numpy as np
import torch
from torch.utils.data import DataLoader
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.seed import seed_everything
from utils.checkpoint import save_checkpoint, load_checkpoint
from utils.metrics import slack_metrics, edge_delay_metrics
from utils.sanity_checks import run_all_checks
from data.dataset import STADataset, STASample
from data.collate import collate_sta
from data.normalization import FeatureNormalizer
from models.full_model import MultiAnchorSTAModel, ModelOutput
from losses.losses import STALoss


def load_config(config_path: str, overrides: Optional[Dict] = None) -> Dict:
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if overrides:
        for k, v in overrides.items():
            if v is not None:
                keys = k.split(".")
                d = cfg
                for kk in keys[:-1]:
                    d = d.setdefault(kk, {})
                d[keys[-1]] = v
    return cfg


# ============================================================================
# Forward helper (v2: new interface)
# ============================================================================

def _build_edge_scalars(sample: STASample) -> torch.Tensor:
    """Stack the 6 per-edge scalar features and apply log1p(clamp(min=0)).

    Returns: [E, 6] float tensor (same device as sample tensors).
    """
    return torch.stack([
        torch.log1p(sample.edge_fanin_src.float().clamp(min=0)),
        torch.log1p(sample.edge_fanout_src.float().clamp(min=0)),
        torch.log1p(sample.edge_fanin_dst.float().clamp(min=0)),
        torch.log1p(sample.edge_fanout_dst.float().clamp(min=0)),
        torch.log1p(sample.edge_cap_src.float().clamp(min=0)),
        torch.log1p(sample.edge_cap_dst.float().clamp(min=0)),
    ], dim=-1)  # [E, 6]


def _forward_sample(
    model: MultiAnchorSTAModel,
    sample: STASample,
    normalizer: FeatureNormalizer,
    device: str,
) -> ModelOutput:
    pin_static = sample.pin_static.to(device)
    if normalizer.is_ready:
        pin_static = normalizer.normalize("pin_static", pin_static)

    # ---- Edge scalar normalization (v2: z-score after log1p) ----
    edge_scalars = _build_edge_scalars(sample).to(device)
    edge_scalars_normed = None
    if normalizer.is_ready and "edge_scalars" in normalizer._stats:
        edge_scalars_normed = normalizer.normalize("edge_scalars", edge_scalars)

    # ---- Force index tensors to long (prevents embedding / scatter errors) ----
    return model(
        pin_static=pin_static,
        pin_dyn_anchor=sample.pin_dyn_anchor.to(device),
        d_anchor=sample.d_anchor.to(device),
        edge_src=sample.edge_src_id.long().to(device),
        edge_dst=sample.edge_dst_id.long().to(device),
        edge_type=sample.edge_type.long().to(device),
        topo_order=sample.topo_order.long().to(device),
        node_level=sample.node_level.long().to(device),
        data_mask=sample.mask.to(device),
        edge_valid=sample.edge_valid.to(device),
        source_mask=sample.source_mask.to(device),
        endpoint_ids=sample.endpoint_ids.long().to(device),
        rat_true=sample.rat_true.to(device),
        z_cont=sample.z_cont.to(device),
        process_id=sample.process_id.long().to(device),
        edge_cell_type_src=sample.edge_cell_type_src.long().to(device),
        edge_cell_type_dst=sample.edge_cell_type_dst.long().to(device),
        edge_pin_role_src=sample.edge_pin_role_src.long().to(device),
        edge_pin_role_dst=sample.edge_pin_role_dst.long().to(device),
        edge_fanin_src=sample.edge_fanin_src.to(device),
        edge_fanout_src=sample.edge_fanout_src.to(device),
        edge_fanin_dst=sample.edge_fanin_dst.to(device),
        edge_fanout_dst=sample.edge_fanout_dst.to(device),
        edge_cap_src=sample.edge_cap_src.to(device),
        edge_cap_dst=sample.edge_cap_dst.to(device),
        edge_scalars_normed=edge_scalars_normed,
        sta_edge_keep=sample.sta_edge_keep.to(device),
    )


# ============================================================================
# Slack consistency assertion (run once on first batch)
# ============================================================================

def assert_slack_consistency(
    sample: STASample,
    atol: float = 0.001,
    rtol: float = 0.01,
) -> None:
    """
    Assert: slack_true ≈ rat_true - arrival_ep_true.
    This catches channel/label misalignment (RR/RF/FR/FF or LateR/LateF) early.

    Uses combined absolute + relative tolerance:
        pass iff  |diff| <= atol + rtol * |slack_true|   (element-wise)
    """
    s = sample.slack_true
    r = sample.rat_true
    a = sample.arrival_ep_true

    if s.numel() == 0 or r.numel() == 0:
        print("  [ASSERT] No endpoint data — skipping slack consistency check")
        return

    # Basic sanity
    assert torch.isfinite(s).all(), "slack_true contains non-finite values!"
    assert torch.isfinite(r).all(), "rat_true contains non-finite values!"
    assert s.shape == r.shape, f"Shape mismatch: slack={s.shape}, rat={r.shape}"

    if a.numel() == 0 or a.shape != s.shape:
        print(f"  [ASSERT] arrival_ep_true unavailable or shape mismatch "
              f"(a={a.shape}, s={s.shape}) — falling back to basic check")
        print(f"  [ASSERT] slack_true: mean={s.mean():.4f}, rat_true: mean={r.mean():.4f}")
        return

    assert torch.isfinite(a).all(), "arrival_ep_true contains non-finite values!"

    # Real consistency: slack ≈ rat - arrival
    computed_slack = r - a
    diff = (s - computed_slack).abs()
    max_diff = diff.max().item()
    mean_diff = diff.mean().item()

    # Combined tolerance: atol + rtol * |slack_true|
    tol_per_elem = atol + rtol * s.abs()
    violations = (diff > tol_per_elem).sum().item()
    total_elems = diff.numel()

    print(f"  [ASSERT] slack_true: mean={s.mean():.4f}, rat_true: mean={r.mean():.4f}, "
          f"arrival_ep: mean={a.mean():.4f}")
    print(f"  [ASSERT] slack vs (RAT-AT): max_diff={max_diff:.6f}, mean_diff={mean_diff:.6f}")
    print(f"  [ASSERT] tolerance: atol={atol}, rtol={rtol}, "
          f"violations={violations}/{total_elems}")

    if violations > 0:
        print(f"  [WARN] Slack consistency check FAILED "
              f"({violations}/{total_elems} elements exceed tolerance)")
        print(f"         This may indicate channel/label misalignment!")
    else:
        print(f"  [ASSERT] Slack consistency check PASSED (all elements within tolerance)")


# ============================================================================
# Training / Evaluation
# ============================================================================

def train_one_epoch(
    model, loader, criterion, optimizer, normalizer,
    device, grad_clip, epoch, total_epochs,
) -> Dict[str, float]:
    model.train()
    total_losses = {}
    count = 0
    # Running slack MAE for metric fallback when no val set
    running_slack_mae = 0.0
    slack_count = 0

    pbar = tqdm(loader, desc=f"Epoch {epoch} [train]", leave=False)
    for sample in pbar:
        optimizer.zero_grad()
        out = _forward_sample(model, sample, normalizer, device)

        losses = criterion(
            slack_hat=out.slack_hat,
            slack_true=sample.slack_true.to(device),
            d_hat=out.d_hat,
            d_true=sample.d_target_true.to(device),
            mask=sample.mask.to(device),
            edge_valid=sample.edge_valid.to(device),
            edge_type=sample.edge_type.long().to(device),
            g_e=out.g_e, gG=out.gG,
            log_scale=out.log_scale,
            at_all=out.at_all,
            at_true=sample.at_true.to(device),
            epoch=epoch, total_epochs=total_epochs,
        )

        loss = losses["total"]
        if torch.isnan(loss) or torch.isinf(loss):
            print(f"  [WARN] NaN/Inf loss at epoch {epoch}, skipping")
            continue

        loss.backward()
        if grad_clip > 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
        optimizer.step()

        for k, v in losses.items():
            if isinstance(v, torch.Tensor):
                total_losses[k] = total_losses.get(k, 0.0) + v.item()
        count += 1

        # Track slack MAE (lightweight, no extra backward graph)
        if out.slack_hat.numel() > 0:
            with torch.no_grad():
                running_slack_mae += (
                    out.slack_hat - sample.slack_true.to(device)
                ).abs().mean().item()
                slack_count += 1

        pbar.set_postfix(loss=f"{loss.item():.4f}")

    if count > 0:
        for k in total_losses:
            total_losses[k] /= count
    if slack_count > 0:
        total_losses["slack_mae"] = running_slack_mae / slack_count
    return total_losses


@torch.no_grad()
def evaluate(model, loader, criterion, normalizer, device, epoch=0, total_epochs=200):
    model.eval()
    all_sp, all_st, all_dp, all_dt, all_mk = [], [], [], [], []
    total_losses = {}
    count = 0

    for sample in tqdm(loader, desc="[eval]", leave=False):
        out = _forward_sample(model, sample, normalizer, device)

        losses = criterion(
            slack_hat=out.slack_hat,
            slack_true=sample.slack_true.to(device),
            d_hat=out.d_hat,
            d_true=sample.d_target_true.to(device),
            mask=sample.mask.to(device),
            edge_valid=sample.edge_valid.to(device),
            edge_type=sample.edge_type.long().to(device),
            g_e=out.g_e, gG=out.gG,
            log_scale=out.log_scale,
            at_all=out.at_all,
            at_true=sample.at_true.to(device),
            epoch=epoch, total_epochs=total_epochs,
        )
        for k, v in losses.items():
            if isinstance(v, torch.Tensor):
                total_losses[k] = total_losses.get(k, 0.0) + v.item()
        count += 1

        all_sp.append(out.slack_hat.cpu())
        all_st.append(sample.slack_true.cpu())
        all_dp.append(out.d_hat.cpu())
        all_dt.append(sample.d_target_true.cpu())
        all_mk.append(sample.mask.cpu())

    if count > 0:
        for k in total_losses:
            total_losses[k] /= count

    metrics = dict(total_losses)
    if all_sp:
        metrics.update(slack_metrics(torch.cat(all_sp), torch.cat(all_st)))
    if all_dp:
        metrics.update(edge_delay_metrics(torch.cat(all_dp), torch.cat(all_dt), torch.cat(all_mk)))
    return metrics


def compute_normalization(loader, device):
    normalizer = FeatureNormalizer()
    print("Computing normalization statistics ...")
    for sample in tqdm(loader, desc="[norm]", leave=False):
        normalizer.accumulate("pin_static", sample.pin_static)
        # Edge scalars: log1p-transformed (must match _build_edge_scalars)
        edge_scalars = _build_edge_scalars(sample)
        normalizer.accumulate("edge_scalars", edge_scalars)
    normalizer.finalize()
    print("  [OK] Normalization stats computed (pin_static + edge_scalars)")
    return normalizer


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Train Multi-Anchor GNN STA (v2)")
    parser.add_argument("--config", type=str, default="configs/base.yaml")
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument("--data_root", type=str, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--resume", type=str, default=None)
    args = parser.parse_args()

    overrides = {}
    if args.epochs: overrides["training.epochs"] = args.epochs
    if args.lr: overrides["training.lr"] = args.lr
    if args.data_root: overrides["data_root"] = args.data_root
    if args.seed: overrides["seed"] = args.seed

    cfg = load_config(args.config, overrides)
    device = args.device
    seed_everything(cfg.get("seed", 42))

    data_root = Path(cfg["data_root"])
    benchmarks = cfg["benchmarks"]
    anchors = cfg["anchors"]
    # Auto-name checkpoint dir: checkpoints/{benchmarks}_{film|no_film}/
    model_cfg = cfg.get("model", {})
    use_film = model_cfg.get("use_film", True)
    ckpt_base = Path(cfg.get("checkpoint_dir", "checkpoints"))
    bm_tag = "_".join(benchmarks)
    film_tag = "film" if use_film else "no_film"
    ckpt_dir = ckpt_base / f"{bm_tag}_{film_tag}_v2"
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    print(f"Data root:   {data_root}")
    print(f"Benchmarks:  {benchmarks}")
    print(f"Anchors:     {anchors}")
    print(f"Device:      {device}")

    # Sanity checks
    topo_orders = run_all_checks(data_root, benchmarks, anchors)

    # Splits
    from utils.io import read_splits
    train_targets, val_targets = [], []
    for bm in benchmarks:
        sp = data_root / bm / "splits.json"
        if sp.exists():
            splits = read_splits(sp)
            train_targets.extend(splits.get("train_targets", []))
            val_targets.extend(splits.get("val_targets", []))
    train_targets = sorted(set(train_targets))
    val_targets = sorted(set(val_targets))
    print(f"\nTrain targets ({len(train_targets)}): {train_targets}")
    print(f"Val targets ({len(val_targets)}):   {val_targets}")

    # Datasets
    train_ds = STADataset(data_root, benchmarks, train_targets, anchors, topo_orders)
    val_ds = STADataset(data_root, benchmarks, val_targets, anchors, topo_orders)
    print(f"\nTrain samples: {len(train_ds)}")
    print(f"Val samples:   {len(val_ds)}")

    if len(train_ds) == 0:
        print("[ERROR] No training samples. Export target corners first.")
        sys.exit(1)

    bs = cfg["training"].get("batch_size", 1)
    train_loader = DataLoader(train_ds, batch_size=bs, shuffle=True,
                              collate_fn=collate_sta, num_workers=cfg.get("num_workers", 0))
    val_loader = DataLoader(val_ds, batch_size=1, shuffle=False,
                            collate_fn=collate_sta, num_workers=cfg.get("num_workers", 0))

    # Normalization (use bs=1, no-shuffle for clean per-sample statistics)
    norm_loader = DataLoader(train_ds, batch_size=1, shuffle=False,
                             collate_fn=collate_sta, num_workers=0)
    normalizer = compute_normalization(norm_loader, device)
    del norm_loader

    # Slack consistency assertion (on first training sample)
    if len(train_ds) > 0:
        print("\nRunning slack consistency assertion ...")
        assert_slack_consistency(train_ds[0])

    # Model (v2.4) — vocab sizes from union of all benchmarks
    loss_cfg = cfg.get("loss", {})
    max_cell_types = max(len(bs.cell_type_vocab) for bs in train_ds._static_cache.values())
    max_pin_roles = max(len(bs.pin_role_vocab) for bs in train_ds._static_cache.values())
    model = MultiAnchorSTAModel(
        num_anchors=len(anchors),
        pin_static_dim=2,
        pin_dyn_dim=4,
        z_cont_dim=4,
        process_embed_dim=model_cfg.get("process_embed_dim", 8),
        num_process_classes=3,
        hidden_dim=model_cfg.get("hidden_dim", 128),
        gnn_layers=model_cfg.get("gnn_layers", 3),
        tau_sage=model_cfg.get("tau_sage", 1.0),
        edge_mlp_hidden=model_cfg.get("edge_mlp_hidden", 256),
        edge_mlp_layers=model_cfg.get("edge_mlp_layers", 3),
        num_cell_types=max_cell_types + 1,
        num_pin_roles=max_pin_roles + 1,
        beta=model_cfg.get("beta", 1.0),
        scale_clamp=model_cfg.get("scale_clamp", 3.0),
        tau_sta=model_cfg.get("tau_sta", 0.07),
        dropout=model_cfg.get("dropout", 0.0),
        residual_alpha=model_cfg.get("residual_alpha", 0.5),
        d_floor=loss_cfg.get("d_floor", 0.0),
        use_film=use_film,
        film_hidden=model_cfg.get("film_hidden", 128),
        film_gamma_scale=model_cfg.get("film_gamma_scale", 0.5),
    ).to(device)

    num_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"\nModel parameters: {num_params:,}")

    # Optimizer & Scheduler
    train_cfg = cfg["training"]
    epochs = train_cfg.get("epochs", 200)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=train_cfg.get("lr", 3e-4),
        weight_decay=train_cfg.get("weight_decay", 1e-5),
    )

    warmup = train_cfg.get("warmup_epochs", 5)
    base_lr = train_cfg.get("lr", 3e-4)
    scheduler = None
    sched_type = train_cfg.get("scheduler", "cosine")
    if sched_type == "cosine":
        # Real warmup: linear 0→base_lr for first `warmup` epochs, then cosine decay
        def lr_lambda(epoch):
            if warmup > 0 and epoch < warmup:
                return max((epoch + 1) / warmup, 1e-6 / base_lr)
            progress = (epoch - warmup) / max(epochs - warmup, 1)
            cosine_decay = 0.5 * (1.0 + math.cos(math.pi * progress))
            return max(cosine_decay, 1e-6 / base_lr)
        scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)
    elif sched_type == "step":
        scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=50, gamma=0.5)

    # Loss (v2.4: with scale reg + neg delay)
    criterion = STALoss(
        huber_delta=loss_cfg.get("huber_delta", 1.0),
        lambda_edge=loss_cfg.get("lambda_edge", 0.3),
        lambda_kl=loss_cfg.get("lambda_kl", 0.01),
        lambda_ent=loss_cfg.get("lambda_ent", 0.001),
        lambda_scale=loss_cfg.get("lambda_scale", 0.0001),
        d_floor=loss_cfg.get("d_floor", 0.1),
        asinh_scale=loss_cfg.get("asinh_scale", 1.0),
        lambda_neg=loss_cfg.get("lambda_neg", 1e-4),
        lambda_at=loss_cfg.get("lambda_at", 0.1),
    )

    # Resume (strict=False to support adding FiLM to non-FiLM checkpoint)
    start_epoch = 0
    best_metric = float("inf")
    if args.resume:
        ckpt_data = torch.load(str(args.resume), map_location=device, weights_only=False)
        missing, unexpected = model.load_state_dict(ckpt_data["model_state_dict"], strict=False)
        if missing:
            print(f"  [INFO] {len(missing)} missing keys (new FiLM layers)")
        if unexpected:
            print(f"  [WARN] {len(unexpected)} unexpected keys")
        if "optimizer_state_dict" in ckpt_data and not missing:
            optimizer.load_state_dict(ckpt_data["optimizer_state_dict"])
        start_epoch = ckpt_data.get("epoch", 0) + 1
        best_metric = ckpt_data.get("best_metric", float("inf"))
        if "norm_stats" in ckpt_data:
            normalizer.load_state_dict(ckpt_data["norm_stats"])
        print(f"  Resumed at epoch {start_epoch}, best_metric={best_metric:.6f}")

    # Training loop
    patience = train_cfg.get("patience", 30)
    patience_counter = 0
    grad_clip = train_cfg.get("grad_clip", 5.0)

    print(f"\n{'='*70}")
    print(f"Starting training: {epochs} epochs, lr={train_cfg.get('lr', 3e-4)}")
    print(f"{'='*70}\n")

    for epoch in range(start_epoch, epochs):
        t0 = time.time()

        train_losses = train_one_epoch(
            model, train_loader, criterion, optimizer,
            normalizer, device, grad_clip, epoch, epochs,
        )

        val_metrics = {}
        if len(val_ds) > 0:
            val_metrics = evaluate(model, val_loader, criterion, normalizer,
                                   device, epoch, epochs)

        if scheduler is not None:
            scheduler.step()

        lr_now = optimizer.param_groups[0]["lr"]
        elapsed = time.time() - t0

        print(
            f"Epoch {epoch:3d} | "
            f"train_loss={train_losses.get('total', 0):.5f} "
            f"(slack={train_losses.get('L_slack', 0):.5f} "
            f"edge={train_losses.get('L_edge', 0):.5f} "
            f"scale={train_losses.get('L_scale', 0):.5f}) | "
            f"val_slack_mae={val_metrics.get('slack_mae', -1):.5f} "
            f"val_edge_mae={val_metrics.get('edge_mae', -1):.5f} "
            f"ent_decay={train_losses.get('ent_decay', 1):.2f} | "
            f"lr={lr_now:.2e} | {elapsed:.1f}s"
        )

        # Consistent metric: always prefer slack_mae (from val or train)
        if len(val_ds) > 0 and "slack_mae" in val_metrics:
            current_metric = val_metrics["slack_mae"]
        elif "slack_mae" in train_losses:
            current_metric = train_losses["slack_mae"]
        else:
            current_metric = train_losses.get("total", float("inf"))
        if current_metric < best_metric:
            best_metric = current_metric
            patience_counter = 0
            save_checkpoint(ckpt_dir / "best.pt", model, optimizer, epoch,
                            best_metric, norm_stats=normalizer.state_dict())
            print(f"  >> New best: slack_mae={best_metric:.6f}")
        else:
            patience_counter += 1

        if (epoch + 1) % 10 == 0:
            save_checkpoint(ckpt_dir / "latest.pt", model, optimizer, epoch,
                            best_metric, norm_stats=normalizer.state_dict())

        if patience > 0 and patience_counter >= patience:
            print(f"\nEarly stopping at epoch {epoch}")
            break

    print(f"\n{'='*70}")
    print(f"Training complete. Best slack_mae: {best_metric:.6f}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
