#!/usr/bin/env python3
"""
Evaluation script for Physics-Informed Multi-Anchor GNN STA (v2.5).

v2.5 fixes:
  - torch.device() + CUDA availability check
  - Vocab sizes from checkpoint/config (not inferred from test set)
  - --strict flag for state_dict loading
  - GPU-side aggregation (CPU only for JSON / final metrics)
  - Per-sample stats: M, E, valid_ratio for debugging
  - Output path with mkdir
"""

import argparse
import json
import sys
from pathlib import Path

import torch
from torch.utils.data import DataLoader
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.seed import seed_everything
from utils.sanity_checks import run_all_checks
from utils.metrics import (
    slack_metrics, edge_delay_metrics, slack_scale_p95,
    normalized_slack_mae, compute_eval_report,
)
from data.dataset import STADataset
from data.collate import collate_sta
from data.normalization import FeatureNormalizer
from models.full_model import MultiAnchorSTAModel
from train import _forward_sample, load_config


@torch.no_grad()
def evaluate_test(model, loader, normalizer, device):
    """Evaluate on test set. Returns (per_sample_list, aggregate_dict)."""
    model.eval()
    per_sample = []
    all_sp, all_st, all_dp, all_dt, all_mk = [], [], [], [], []

    for sample in tqdm(loader, desc="[test]", leave=False):
        out = _forward_sample(model, sample, normalizer, device)

        # Keep on device for aggregation; CPU for per-sample JSON
        sp = out.slack_hat
        st = sample.slack_true.to(device)
        dp = out.d_hat
        dt = sample.d_target_true.to(device)
        mk = sample.mask.to(device)

        sp_cpu = sp.detach().cpu()
        st_cpu = st.detach().cpu()
        sm = slack_metrics(sp_cpu, st_cpu)
        em = edge_delay_metrics(dp.detach().cpu(), dt.detach().cpu(), mk.detach().cpu())

        valid_count = ((mk > 0.5) & (sample.edge_valid.to(device).unsqueeze(-1) > 0.5)).sum().item()
        total_channels = mk.numel()

        scale = slack_scale_p95(st_cpu)
        per_sample.append({
            "benchmark": sample.benchmark,
            "corner": sample.target_corner,
            "num_endpoints": int(sample.endpoint_ids.shape[0]),
            "num_edges": int(sample.edge_src_id.shape[0]),
            "valid_ratio": valid_count / max(total_channels, 1),
            "slack_scale": scale,
            "slack_norm_mae": normalized_slack_mae(sp_cpu, st_cpu, scale),
            **sm, **em,
        })

        all_sp.append(sp)
        all_st.append(st)
        all_dp.append(dp)
        all_dt.append(dt)
        all_mk.append(mk)

    # Aggregate (one-shot CPU transfer at the end)
    agg = {}
    if all_sp:
        agg.update(slack_metrics(torch.cat(all_sp).cpu(), torch.cat(all_st).cpu()))
    if all_dp:
        agg.update(edge_delay_metrics(
            torch.cat(all_dp).cpu(), torch.cat(all_dt).cpu(), torch.cat(all_mk).cpu()
        ))

    report = compute_eval_report(per_sample)
    agg.update(report)

    return per_sample, agg


def main():
    parser = argparse.ArgumentParser(description="Evaluate Multi-Anchor GNN STA")
    parser.add_argument("--config", type=str, default="configs/base.yaml")
    parser.add_argument("--checkpoint", type=str, required=True)
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--output", type=str, default=None, help="JSON output path")
    parser.add_argument("--strict", action="store_true", help="Strict state_dict loading")
    parser.add_argument("--skip-checks", action="store_true",
                        help="Skip startup sanity checks (faster launch when data is known-good)")
    parser.add_argument("--test-set", type=str, default="test_targets",
                        choices=["test_targets", "test_extra_targets"],
                        help="Which test split to evaluate (default: test_targets)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but not available")
    seed_everything(cfg.get("seed", 42))

    data_root = Path(cfg["data_root"])
    data_cfg = cfg.get("data", {})
    clamp_negative_delay = data_cfg.get("clamp_negative_delay", True)
    delay_floor = float(data_cfg.get("delay_floor", 0.0))
    benchmarks = cfg["benchmarks"]
    anchors = cfg["anchors"]
    model_cfg = cfg.get("model", {})
    loss_cfg = cfg.get("loss", {})

    print(f"Data root:   {data_root}")
    print(f"Benchmarks:  {benchmarks}")
    print(f"Checkpoint:  {args.checkpoint}")
    print(f"Device:      {device}")
    print(f"Delay clamp: clamp_negative_delay={clamp_negative_delay}, delay_floor={delay_floor}")

    if args.skip_checks:
        print("[INFO] Skipping sanity checks (--skip-checks)")
        topo_orders = {}
    else:
        topo_orders = run_all_checks(data_root, benchmarks, anchors)

    # Test targets
    from utils.io import read_splits
    test_split_key = args.test_set
    test_targets = []
    for bm in benchmarks:
        sp = data_root / bm / "splits.json"
        if sp.exists():
            splits = read_splits(sp)
            test_targets.extend(splits.get(test_split_key, []))
    test_targets = sorted(set(test_targets))
    if not test_targets:
        print(f"[ERROR] No corners found for split key '{test_split_key}'")
        sys.exit(1)
    print(f"Test targets [{test_split_key}] ({len(test_targets)}): {test_targets}")

    test_ds = STADataset(
        data_root, benchmarks, test_targets, anchors, topo_orders,
        clamp_negative_delay=clamp_negative_delay,
        delay_floor=delay_floor,
    )
    test_loader = DataLoader(test_ds, batch_size=1, shuffle=False,
                             collate_fn=collate_sta, num_workers=0)

    # Load checkpoint first to get training-time vocab sizes
    ckpt = torch.load(str(args.checkpoint), map_location=device, weights_only=False)

    # Vocab sizes: prefer checkpoint > config > test-set fallback
    ds_max_ct = max(len(bs.cell_type_vocab) for bs in test_ds._static_cache.values())
    ds_max_pr = max(len(bs.pin_role_vocab) for bs in test_ds._static_cache.values())
    num_cell_types = (ckpt.get("num_cell_types")
                      or model_cfg.get("num_cell_types")
                      or ds_max_ct + 1)
    num_pin_roles = (ckpt.get("num_pin_roles")
                     or model_cfg.get("num_pin_roles")
                     or ds_max_pr + 1)
    print(f"Vocab: num_cell_types={num_cell_types}, num_pin_roles={num_pin_roles}")

    # Model
    use_film = model_cfg.get("use_film", False)
    model = MultiAnchorSTAModel(
        num_anchors=len(anchors),
        pin_static_dim=2, pin_dyn_dim=4, z_cont_dim=4,
        process_embed_dim=model_cfg.get("process_embed_dim", 8),
        num_process_classes=3,
        hidden_dim=model_cfg.get("hidden_dim", 128),
        gnn_layers=model_cfg.get("gnn_layers", 3),
        tau_sage=model_cfg.get("tau_sage", 1.0),
        edge_mlp_hidden=model_cfg.get("edge_mlp_hidden", 256),
        edge_mlp_layers=model_cfg.get("edge_mlp_layers", 3),
        num_cell_types=num_cell_types,
        num_pin_roles=num_pin_roles,
        beta=model_cfg.get("beta", 1.0),
        scale_clamp=model_cfg.get("scale_clamp", 3.0),
        tau_sta=model_cfg.get("tau_sta", 0.07),
        tf_interval=cfg.get("training", {}).get("tf_interval", 20),
        dropout=0.0,
        residual_alpha=model_cfg.get("residual_alpha", 0.5),
        d_floor=loss_cfg.get("d_floor", 0.0),
        use_film=use_film,
        film_hidden=model_cfg.get("film_hidden", 128),
        film_gamma_scale=model_cfg.get("film_gamma_scale", 0.5),
        use_endpoint_residual=model_cfg.get("use_endpoint_residual", True),
    ).to(device)

    # Load weights
    missing, unexpected = model.load_state_dict(ckpt["model_state_dict"], strict=args.strict)
    if missing or unexpected:
        print(f"  [LOAD] missing={len(missing)} unexpected={len(unexpected)}")
        if missing:
            print(f"    missing (first 20): {missing[:20]}")
        if unexpected:
            print(f"    unexpected (first 20): {unexpected[:20]}")
        if args.strict:
            raise RuntimeError("State dict mismatch under --strict")
    else:
        print("  [LOAD] All parameters loaded perfectly")

    # Normalizer
    normalizer = FeatureNormalizer()
    if "norm_stats" in ckpt:
        normalizer.load_state_dict(ckpt["norm_stats"])

    num_params = sum(p.numel() for p in model.parameters())
    print(f"Model parameters: {num_params:,}")

    # Evaluate
    per_sample, agg = evaluate_test(model, test_loader, normalizer, device)

    print(f"\n{'='*50}")
    print("Aggregate results:")
    for k, v in sorted(agg.items()):
        print(f"  {k}: {v:.6f}")
    print(f"{'='*50}")

    # Save
    results = {"per_sample": per_sample, "aggregate": agg}
    out_path = (Path(args.output) if args.output
                else Path(f"results_test_{('film' if use_film else 'no_film')}.json"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
