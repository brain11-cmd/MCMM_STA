"""
Dataset for Physics-Informed Multi-Anchor GNN STA.

One sample = (benchmark, target_corner).
Loads static graph once per benchmark (cached), then per-corner dynamic data.

KEY RULES (v2 — precision-first):
  - Only Late(R/F) columns used for arrival/slew (cols 2,3). Early NEVER used.
  - process_id is an integer for embedding, NOT a continuous float.
  - z_cont = [voltage, temp, voltage_norm, temp_norm] (4 continuous dims).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
from torch.utils.data import Dataset

from utils.io import (
    read_graph_edges,
    read_node_static,
    read_node_id_map,
    read_arc_delay_json,
    read_arrival,
    read_slew,
    read_pin_cap,
    read_endpoints_csv,
    parse_corner_name,
)


# ---------------------------------------------------------------------------
# Corner condition vector (v2: separate process_id for embedding)
# ---------------------------------------------------------------------------

PROCESS_TO_ID = {"ff": 0, "tt": 1, "ss": 2}


def corner_to_condition(corner_name: str) -> Tuple[torch.Tensor, int]:
    """
    Encode corner name into:
      z_cont:     [4] float tensor  [voltage, temp, voltage_norm, temp_norm]
      process_id: int               (0=ff, 1=tt, 2=ss) for nn.Embedding
    """
    info = parse_corner_name(corner_name)
    proc_id = PROCESS_TO_ID[info["process"]]
    volt = info["voltage"]
    temp = info["temp"]
    volt_norm = (volt - 0.85) / 0.2
    temp_norm = (temp - 25.0) / 80.0
    z_cont = torch.tensor([volt, temp, volt_norm, temp_norm], dtype=torch.float32)
    return z_cont, proc_id


# ---------------------------------------------------------------------------
# Cached static data per benchmark
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkStatic:
    """Immutable static data for one benchmark (shared across corners)."""
    name: str
    num_nodes: int
    num_edges: int

    edge_src_id: np.ndarray    # [E] int
    edge_dst_id: np.ndarray    # [E] int
    edge_type: np.ndarray      # [E] int — 0=cell, 1=net

    fanin: np.ndarray          # [N]
    fanout: np.ndarray         # [N]
    cell_type_id: np.ndarray   # [N] int
    pin_role_id: np.ndarray    # [N] int

    pin_name_to_id: Dict[str, int]
    cell_type_vocab: Dict[str, int]
    pin_role_vocab: Dict[str, int]

    topo_order: np.ndarray     # [N] int
    source_mask: np.ndarray    # [N] bool — True for nodes with in-degree 0
    node_level: np.ndarray     # [N] int — topological depth (sources=0)
    sta_edge_keep: np.ndarray  # [E] bool — edges safe for STA (back edges cut for cycles)


def _build_vocab(values) -> Dict[str, int]:
    vocab = {"<UNK>": 0}
    for v in sorted(set(values)):
        if v not in vocab:
            vocab[v] = len(vocab)
    return vocab


def load_benchmark_static(
    data_root: Path,
    benchmark: str,
    topo_order: Optional[np.ndarray] = None,
) -> BenchmarkStatic:
    bm_dir = data_root / benchmark
    static_dir = bm_dir / "static"

    edge_ids, src_pins, dst_pins, edge_type = read_graph_edges(
        static_dir / "graph_edges.csv"
    )
    E = len(edge_ids)

    node_data = read_node_static(static_dir / "node_static.csv")
    pin_name_to_id = read_node_id_map(static_dir / "node_id_map.json")
    N = len(pin_name_to_id)

    cell_types = [node_data[p]["cell_type"] for p in sorted(
        node_data.keys(), key=lambda x: node_data[x]["node_id"])]
    pin_roles = [node_data[p]["pin_role"] for p in sorted(
        node_data.keys(), key=lambda x: node_data[x]["node_id"])]
    ct_vocab = _build_vocab(cell_types)
    pr_vocab = _build_vocab(pin_roles)

    fanin = np.zeros(N, dtype=np.float32)
    fanout = np.zeros(N, dtype=np.float32)
    ct_ids = np.zeros(N, dtype=np.int64)
    pr_ids = np.zeros(N, dtype=np.int64)

    for pin_name, info in node_data.items():
        nid = info["node_id"]
        if nid >= N:
            continue
        fanin[nid] = info["fanin"]
        fanout[nid] = info["fanout"]
        ct_ids[nid] = ct_vocab.get(info["cell_type"], 0)
        pr_ids[nid] = pr_vocab.get(info["pin_role"], 0)

    edge_src_id = np.array(
        [pin_name_to_id.get(p, -1) for p in src_pins], dtype=np.int64
    )
    edge_dst_id = np.array(
        [pin_name_to_id.get(p, -1) for p in dst_pins], dtype=np.int64
    )

    # Compute topo order + handle cycles (e.g. FIFO feedback)
    from utils.sanity_checks import compute_topo_order_with_dag_mask
    if topo_order is None:
        topo_order, sta_edge_keep = compute_topo_order_with_dag_mask(
            N, edge_src_id, edge_dst_id, edge_type=edge_type,
        )
    else:
        # topo_order provided (from sanity checks) — check if DAG with all edges
        try:
            from utils.sanity_checks import _kahn_topo
            _kahn_topo(N, edge_src_id, edge_dst_id)
            sta_edge_keep = np.ones(E, dtype=bool)
        except RuntimeError:
            topo_order, sta_edge_keep = compute_topo_order_with_dag_mask(
                N, edge_src_id, edge_dst_id, edge_type=edge_type,
            )

    # Compute source mask (nodes with in-degree == 0, using STA-valid edges only)
    kept_dst = edge_dst_id[sta_edge_keep]
    valid_dst = kept_dst[kept_dst >= 0]
    has_incoming = np.zeros(N, dtype=bool)
    if len(valid_dst) > 0:
        has_incoming[valid_dst] = True
    source_mask = ~has_incoming

    # Compute node_level on the DAG (using only STA-valid edges)
    from collections import defaultdict as _defaultdict
    in_adj = _defaultdict(list)
    for eidx in range(E):
        if not sta_edge_keep[eidx]:
            continue
        s, d = int(edge_src_id[eidx]), int(edge_dst_id[eidx])
        if s >= 0 and d >= 0:
            in_adj[d].append(s)
    node_level = np.zeros(N, dtype=np.int64)
    for v in topo_order:
        v = int(v)
        for u in in_adj.get(v, []):
            node_level[v] = max(node_level[v], node_level[u] + 1)

    return BenchmarkStatic(
        name=benchmark, num_nodes=N, num_edges=E,
        edge_src_id=edge_src_id, edge_dst_id=edge_dst_id, edge_type=edge_type,
        fanin=fanin, fanout=fanout,
        cell_type_id=ct_ids, pin_role_id=pr_ids,
        pin_name_to_id=pin_name_to_id,
        cell_type_vocab=ct_vocab, pin_role_vocab=pr_vocab,
        topo_order=topo_order,
        source_mask=source_mask,
        node_level=node_level,
        sta_edge_keep=sta_edge_keep,
    )


# ---------------------------------------------------------------------------
# Per-corner dynamic data loading
# ---------------------------------------------------------------------------

def _pin_dict_to_array(
    pin_dict: Dict[str, np.ndarray],
    pin_name_to_id: Dict[str, int],
    num_nodes: int,
    cols: int = 4,
) -> np.ndarray:
    arr = np.zeros((num_nodes, cols), dtype=np.float32)
    for pin_name, vals in pin_dict.items():
        nid = pin_name_to_id.get(pin_name, -1)
        if 0 <= nid < num_nodes:
            arr[nid, :len(vals)] = vals[:cols]
    return arr


def load_corner_data(
    corners_dir: Path,
    corner_name: str,
    pin_name_to_id: Dict[str, int],
    num_nodes: int,
    num_edges: int,
) -> Dict[str, np.ndarray]:
    cdir = corners_dir / corner_name
    result = {}

    for key, reader in [("arrival", read_arrival), ("slew", read_slew),
                         ("pin_cap", read_pin_cap)]:
        fpath = cdir / f"{key}.txt"
        if key == "pin_cap":
            fpath = cdir / "pin_cap.txt"
        if fpath.exists():
            result[key] = _pin_dict_to_array(
                reader(fpath), pin_name_to_id, num_nodes
            )
        else:
            result[key] = np.zeros((num_nodes, 4), dtype=np.float32)

    ad_path = cdir / "arc_delay.json"
    if ad_path.exists():
        delays, masks, ev = read_arc_delay_json(ad_path)
        result["arc_delay"] = delays
        result["mask"] = masks
        result["edge_valid"] = ev
    else:
        result["arc_delay"] = np.zeros((num_edges, 4), dtype=np.float32)
        result["mask"] = np.zeros((num_edges, 4), dtype=np.int32)
        result["edge_valid"] = np.zeros(num_edges, dtype=np.int32)

    return result


def load_endpoint_labels(
    corners_dir: Path,
    corner_name: str,
    pin_name_to_id: Dict[str, int],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Returns:
        endpoint_ids:  [M]
        slack_true:    [M, 2] (LateR, LateF) — for assertion only
        rat_true:      [M, 2] (LateR, LateF) — used as label
    """
    cdir = corners_dir / corner_name
    ep_path = cdir / "endpoints.csv"

    if not ep_path.exists():
        return np.array([], dtype=np.int64), np.zeros((0, 2)), np.zeros((0, 2))

    rows = read_endpoints_csv(ep_path)
    pin_data: Dict[str, Dict[str, float]] = {}
    for r in rows:
        if r["valid"] != 1:
            continue
        pin = r["endpoint_pin"]
        if pin not in pin_data:
            pin_data[pin] = {}
        rf = r["rf"]
        pin_data[pin][f"slack_{rf}"] = r["slack_late"]
        pin_data[pin][f"rat_{rf}"] = r["required_late"]

    ep_ids, slacks, rats = [], [], []
    for pin, d in sorted(pin_data.items()):
        nid = pin_name_to_id.get(pin, -1)
        if nid < 0:
            continue
        if "slack_R" in d and "slack_F" in d:
            ep_ids.append(nid)
            slacks.append([d["slack_R"], d["slack_F"]])
            rats.append([d["rat_R"], d["rat_F"]])

    return (
        np.array(ep_ids, dtype=np.int64),
        np.array(slacks, dtype=np.float32) if slacks else np.zeros((0, 2), np.float32),
        np.array(rats, dtype=np.float32) if rats else np.zeros((0, 2), np.float32),
    )


# ---------------------------------------------------------------------------
# STASample dataclass
# ---------------------------------------------------------------------------

@dataclass
class STASample:
    """One training / evaluation sample (v2)."""
    benchmark: str
    target_corner: str

    num_nodes: int
    num_edges: int
    edge_src_id: torch.Tensor      # [E] long
    edge_dst_id: torch.Tensor      # [E] long
    edge_type: torch.Tensor        # [E] long
    topo_order: torch.Tensor       # [N] long
    source_mask: torch.Tensor      # [N] bool — True for source nodes
    node_level: torch.Tensor       # [N] long — topological depth (sources=0)
    sta_edge_keep: torch.Tensor    # [E] bool — edges safe for STA (back edges cut)

    pin_static: torch.Tensor       # [N, 2]

    # Anchor dynamic: ONLY Late(R,F) arrival + slew
    pin_dyn_anchor: torch.Tensor   # [K, N, 4]  (arr_LR, arr_LF, slew_LR, slew_LF)
    d_anchor: torch.Tensor         # [K, E, 4]

    # Target labels
    d_target_true: torch.Tensor    # [E, 4]
    mask: torch.Tensor             # [E, 4]
    edge_valid: torch.Tensor       # [E]

    endpoint_ids: torch.Tensor     # [M] long
    slack_true: torch.Tensor       # [M, 2]  — for assertion only
    rat_true: torch.Tensor         # [M, 2]  — primary label
    arrival_ep_true: torch.Tensor  # [M, 2]  — Late(R,F) arrival at endpoints (for consistency check)

    # Full-node arrival (for AT supervision — denser than endpoint-only slack)
    at_true: torch.Tensor          # [N, 2] Late(R,F) arrival at ALL nodes

    # Condition (v2: separate process_id for embedding)
    z_cont: torch.Tensor           # [4] continuous condition
    process_id: torch.Tensor       # [] long scalar

    # Per-edge static features
    edge_cell_type_src: torch.Tensor
    edge_cell_type_dst: torch.Tensor
    edge_pin_role_src: torch.Tensor
    edge_pin_role_dst: torch.Tensor
    edge_fanin_src: torch.Tensor
    edge_fanout_src: torch.Tensor
    edge_fanin_dst: torch.Tensor
    edge_fanout_dst: torch.Tensor
    edge_cap_src: torch.Tensor
    edge_cap_dst: torch.Tensor


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class STADataset(Dataset):
    def __init__(
        self,
        data_root: Path,
        benchmarks: List[str],
        target_corners: List[str],
        anchors: List[str],
        topo_orders: Dict[str, np.ndarray],
    ):
        self.data_root = Path(data_root)
        self.anchors = anchors
        self.K = len(anchors)

        self.samples: List[Tuple[str, str]] = []
        for bm in benchmarks:
            corners_dir = self.data_root / bm / "corners"
            for tc in target_corners:
                if (corners_dir / tc).exists():
                    self.samples.append((bm, tc))

        self._static_cache: Dict[str, BenchmarkStatic] = {}
        for bm in benchmarks:
            self._static_cache[bm] = load_benchmark_static(
                self.data_root, bm, topo_orders.get(bm)
            )

        self._anchor_cache: Dict[Tuple[str, str], Dict] = {}
        for bm in benchmarks:
            bs = self._static_cache[bm]
            corners_dir = self.data_root / bm / "corners"
            for anc in anchors:
                self._anchor_cache[(bm, anc)] = load_corner_data(
                    corners_dir, anc, bs.pin_name_to_id, bs.num_nodes, bs.num_edges
                )

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> STASample:
        bm, tc = self.samples[idx]
        bs = self._static_cache[bm]
        corners_dir = self.data_root / bm / "corners"

        # ---- anchor data (ONLY Late columns: index 2=LR, 3=LF) ----
        pin_dyn_list = []
        d_anchor_list = []
        for anc in self.anchors:
            acd = self._anchor_cache[(bm, anc)]
            arr_late = acd["arrival"][:, 2:4]   # [N,2] Late(R,F) ONLY
            slew_late = acd["slew"][:, 2:4]     # [N,2] Late(R,F) ONLY
            pin_dyn = np.concatenate([arr_late, slew_late], axis=1)  # [N,4]
            pin_dyn_list.append(pin_dyn)
            d_anchor_list.append(acd["arc_delay"])

        pin_dyn_anchor = np.stack(pin_dyn_list, axis=0)  # [K, N, 4]
        d_anchor = np.stack(d_anchor_list, axis=0)

        # ---- target data ----
        tgt = load_corner_data(
            corners_dir, tc, bs.pin_name_to_id, bs.num_nodes, bs.num_edges
        )
        ep_ids, slack_true, rat_true = load_endpoint_labels(
            corners_dir, tc, bs.pin_name_to_id
        )

        # ---- endpoint arrival (for slack consistency check) ----
        if len(ep_ids) > 0:
            arrival_ep = tgt["arrival"][ep_ids, 2:4].astype(np.float32)  # [M, 2]
        else:
            arrival_ep = np.zeros((0, 2), dtype=np.float32)

        # ---- pin static ----
        pin_static = np.stack([
            np.log1p(bs.fanin),
            np.log1p(bs.fanout),
        ], axis=1).astype(np.float32)

        # ---- per-edge static ----
        src_id_c = np.clip(bs.edge_src_id, 0, bs.num_nodes - 1)
        dst_id_c = np.clip(bs.edge_dst_id, 0, bs.num_nodes - 1)

        anc0 = self._anchor_cache[(bm, self.anchors[0])]
        cap_arr = anc0["pin_cap"][:, 2]  # Late Rise cap

        # ---- condition (v2) ----
        z_cont, proc_id = corner_to_condition(tc)

        return STASample(
            benchmark=bm, target_corner=tc,
            num_nodes=bs.num_nodes, num_edges=bs.num_edges,
            edge_src_id=torch.from_numpy(bs.edge_src_id),
            edge_dst_id=torch.from_numpy(bs.edge_dst_id),
            edge_type=torch.from_numpy(bs.edge_type),
            topo_order=torch.from_numpy(bs.topo_order),
            source_mask=torch.from_numpy(bs.source_mask),
            node_level=torch.from_numpy(bs.node_level),
            sta_edge_keep=torch.from_numpy(bs.sta_edge_keep),
            pin_static=torch.from_numpy(pin_static),
            pin_dyn_anchor=torch.from_numpy(pin_dyn_anchor),
            d_anchor=torch.from_numpy(d_anchor),
            d_target_true=torch.from_numpy(tgt["arc_delay"]),
            mask=torch.from_numpy(tgt["mask"].astype(np.float32)),
            edge_valid=torch.from_numpy(tgt["edge_valid"].astype(np.float32)),
            endpoint_ids=torch.from_numpy(ep_ids),
            slack_true=torch.from_numpy(slack_true),
            rat_true=torch.from_numpy(rat_true),
            arrival_ep_true=torch.from_numpy(arrival_ep),
            at_true=torch.from_numpy(tgt["arrival"][:, 2:4].astype(np.float32)),
            z_cont=z_cont,
            process_id=torch.tensor(proc_id, dtype=torch.long),
            edge_cell_type_src=torch.from_numpy(bs.cell_type_id[src_id_c]),
            edge_cell_type_dst=torch.from_numpy(bs.cell_type_id[dst_id_c]),
            edge_pin_role_src=torch.from_numpy(bs.pin_role_id[src_id_c]),
            edge_pin_role_dst=torch.from_numpy(bs.pin_role_id[dst_id_c]),
            edge_fanin_src=torch.from_numpy(bs.fanin[src_id_c]),
            edge_fanout_src=torch.from_numpy(bs.fanout[src_id_c]),
            edge_fanin_dst=torch.from_numpy(bs.fanin[dst_id_c]),
            edge_fanout_dst=torch.from_numpy(bs.fanout[dst_id_c]),
            edge_cap_src=torch.from_numpy(cap_arr[src_id_c]),
            edge_cap_dst=torch.from_numpy(cap_arr[dst_id_c]),
        )
