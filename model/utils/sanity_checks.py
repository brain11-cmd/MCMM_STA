"""
Startup sanity checks — run before training to catch data issues early.

Checks:
  1. graph_edges edge count == arc_delay edge count (per corner)
  2. Net arcs have RF/FR mask == 0
  3. Topological order exists (DAG check)
  4. Anchor corners all present
  5. Channel semantic verification (RR=rise→rise, RF=rise→fall, etc.)
  6. Late arrival/slew statistics (min/max/mean print)
"""

from pathlib import Path
from typing import List, Dict
from collections import deque

import numpy as np

from utils.io import (
    read_graph_edges,
    read_arc_delay_json,
    read_node_id_map,
    read_splits,
    read_arrival,
    read_slew,
)


# ---- channel semantic constants ----
# Authoritative channel order.  arc_delay.json must match this.
CHANNEL_ORDER = ["RR", "RF", "FR", "FF"]
CHANNEL_SEMANTICS = {
    "RR": "rise_input → rise_output",
    "RF": "rise_input → fall_output",
    "FR": "fall_input → rise_output",
    "FF": "fall_input → fall_output",
}


def check_channel_semantics(corner_dir: Path, corner: str) -> None:
    """
    Verify arc_delay.json channel order matches CHANNEL_ORDER.
    If the file contains a 'channel_order' meta field, assert it;
    otherwise print a warning.
    """
    import json
    ad_path = corner_dir / "arc_delay.json"
    if not ad_path.exists():
        return
    with open(ad_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    file_order = data.get("channel_order")
    if file_order is not None:
        assert file_order == CHANNEL_ORDER, (
            f"Channel order mismatch in {corner}: "
            f"file={file_order}, expected={CHANNEL_ORDER}"
        )
        print(f"  [OK] {corner}: channel_order verified {CHANNEL_ORDER}")
    else:
        print(f"  [WARN] {corner}: arc_delay.json missing 'channel_order' meta. "
              f"Assuming {CHANNEL_ORDER} — add this field to be safe!")


def check_edge_count(static_dir: Path, corner_dir: Path, corner: str) -> None:
    """Assert arc_delay has same #edges as graph_edges."""
    ge_path = static_dir / "graph_edges.csv"
    ad_path = corner_dir / "arc_delay.json"
    if not ad_path.exists():
        print(f"  [SKIP] {corner}: arc_delay.json not found")
        return
    eids, _, _, _ = read_graph_edges(ge_path)
    delays, _, _ = read_arc_delay_json(ad_path)
    assert len(eids) == delays.shape[0], (
        f"Edge count mismatch for {corner}: "
        f"graph_edges={len(eids)}, arc_delay={delays.shape[0]}"
    )
    print(f"  [OK] {corner}: {len(eids)} edges consistent")


def check_net_mask(static_dir: Path, corner_dir: Path, corner: str) -> None:
    """Verify net arcs have maskRF=0 and maskFR=0."""
    ge_path = static_dir / "graph_edges.csv"
    ad_path = corner_dir / "arc_delay.json"
    if not ad_path.exists():
        return
    _, _, _, etypes = read_graph_edges(ge_path)
    _, masks, _ = read_arc_delay_json(ad_path)
    net_idx = np.where(etypes == 1)[0]
    if len(net_idx) == 0:
        return
    net_masks = masks[net_idx]
    bad_rf = (net_masks[:, 1] != 0).sum()
    bad_fr = (net_masks[:, 2] != 0).sum()
    if bad_rf > 0 or bad_fr > 0:
        print(f"  [WARN] {corner}: net arcs with RF={bad_rf} / FR={bad_fr} != 0")
    else:
        print(f"  [OK] {corner}: net arc mask rule correct")


def print_corner_stats(corner_dir: Path, corner: str, nid_map: Dict) -> None:
    """Print Late arrival/slew statistics for a corner (sanity)."""
    arr_path = corner_dir / "arrival.txt"
    slew_path = corner_dir / "slew.txt"
    if arr_path.exists():
        arr = read_arrival(arr_path)
        if arr:
            late_r = [v[2] for v in arr.values()]  # L/R
            late_f = [v[3] for v in arr.values()]  # L/F
            print(f"    arrival Late R: min={min(late_r):.4f} max={max(late_r):.4f} "
                  f"mean={np.mean(late_r):.4f}  ({len(late_r)} pins)")
            print(f"    arrival Late F: min={min(late_f):.4f} max={max(late_f):.4f} "
                  f"mean={np.mean(late_f):.4f}")
    if slew_path.exists():
        slw = read_slew(slew_path)
        if slw:
            late_r = [v[2] for v in slw.values()]
            late_f = [v[3] for v in slw.values()]
            print(f"    slew    Late R: min={min(late_r):.4f} max={max(late_r):.4f} "
                  f"mean={np.mean(late_r):.4f}")


def _kahn_topo(num_nodes: int, edge_src: List[int], edge_dst: List[int]):
    """Kahn's algorithm. Returns (order, success)."""
    adj: Dict[int, List[int]] = {i: [] for i in range(num_nodes)}
    in_deg = np.zeros(num_nodes, dtype=np.int64)
    for s, d in zip(edge_src, edge_dst):
        if s == d or s < 0 or d < 0:
            continue
        adj[s].append(d)
        in_deg[d] += 1
    queue = deque()
    for i in range(num_nodes):
        if in_deg[i] == 0:
            queue.append(i)
    order = []
    while queue:
        u = queue.popleft()
        order.append(u)
        for v in adj[u]:
            in_deg[v] -= 1
            if in_deg[v] == 0:
                queue.append(v)

    if len(order) != num_nodes:
        raise RuntimeError(
            f"Graph has a cycle! Sorted {len(order)}/{num_nodes} nodes. "
            f"Cannot perform topological STA propagation."
        )
    return np.array(order, dtype=np.int64)


def compute_topo_order(num_nodes, edge_src, edge_dst):
    """Public wrapper for _kahn_topo."""
    return _kahn_topo(num_nodes, edge_src, edge_dst)


def compute_topo_order_with_dag_mask(num_nodes, edge_src, edge_dst, edge_type=None):
    """
    Compute topological order, handling cycles by cutting back edges via DFS.

    For acyclic graphs: returns (topo_order, all-True mask).
    For cyclic graphs (e.g. FIFO with feedback):
      - Uses iterative DFS to identify back edges
      - Prefers cutting net arcs (edge_type=1) over cell arcs
      - Returns (topo_order_of_DAG, sta_edge_keep mask)

    Cut edges are removed from STA propagation only — edge loss still uses them.

    Returns:
        topo_order:    [N] int64
        sta_edge_keep: [E] bool — True for edges safe for STA
    """
    E = len(edge_src)
    sta_edge_keep = np.ones(E, dtype=bool)

    # First try: is it already a DAG?
    try:
        topo = _kahn_topo(num_nodes, edge_src, edge_dst)
        return topo, sta_edge_keep
    except RuntimeError:
        pass

    # Has cycles — use iterative DFS to find and cut back edges
    print(f"    [CYCLE] Graph has cycles — running DFS back-edge detection ...")

    # Build adjacency: src → [(dst, edge_idx), ...]
    adj = [[] for _ in range(num_nodes)]
    for eidx in range(E):
        s, d = int(edge_src[eidx]), int(edge_dst[eidx])
        if s >= 0 and d >= 0 and s != d:
            adj[s].append((d, eidx))

    WHITE, GRAY, BLACK = 0, 1, 2
    color = np.zeros(num_nodes, dtype=np.int32)
    topo_order = []
    back_edges = []

    # Iterative DFS (no recursion limit)
    for start in range(num_nodes):
        if color[start] != WHITE:
            continue
        stack = [(start, 0)]
        color[start] = GRAY

        while stack:
            u, idx = stack[-1]
            if idx < len(adj[u]):
                stack[-1] = (u, idx + 1)
                v, eidx = adj[u][idx]
                if color[v] == GRAY:
                    # Back edge → cycle! Mark for cutting
                    back_edges.append(eidx)
                elif color[v] == WHITE:
                    color[v] = GRAY
                    stack.append((v, 0))
            else:
                color[u] = BLACK
                topo_order.append(u)
                stack.pop()

    topo_order.reverse()

    # Prefer cutting net arcs over cell arcs
    if edge_type is not None:
        net_back = [e for e in back_edges if edge_type[e] == 1]
        cell_back = [e for e in back_edges if edge_type[e] == 0]
    else:
        net_back = back_edges
        cell_back = []

    for eidx in back_edges:
        sta_edge_keep[eidx] = False

    n_cut = len(back_edges)
    n_net = len(net_back)
    print(f"    [CYCLE] Cut {n_cut} back edges ({n_net} net + {n_cut - n_net} cell)")
    print(f"    [CYCLE] STA will use {sta_edge_keep.sum()}/{E} edges")

    # Verify the result is a DAG
    kept_src = edge_src[sta_edge_keep]
    kept_dst = edge_dst[sta_edge_keep]
    try:
        topo_verified = _kahn_topo(num_nodes, kept_src, kept_dst)
        print(f"    [CYCLE] DAG verified: {num_nodes} nodes in topo order")
        return topo_verified, sta_edge_keep
    except RuntimeError as e:
        # Fallback: shouldn't happen, but if DFS missed some cycles
        print(f"    [WARN] DAG verification failed after cutting: {e}")
        print(f"    [WARN] Using DFS topo order (approximate)")
        return np.array(topo_order, dtype=np.int64), sta_edge_keep


def check_topo_order(static_dir: Path) -> np.ndarray:
    """Compute and validate topological order from graph_edges.csv.

    Handles cycles gracefully via DFS back-edge cutting.
    """
    ge_path = static_dir / "graph_edges.csv"
    nid_path = static_dir / "node_id_map.json"

    _, src_pins, dst_pins, edge_type = read_graph_edges(ge_path)
    nid_map = read_node_id_map(nid_path)
    num_nodes = len(nid_map)

    src_ids = np.array([nid_map.get(p, -1) for p in src_pins], dtype=np.int64)
    dst_ids = np.array([nid_map.get(p, -1) for p in dst_pins], dtype=np.int64)
    min_len = min(len(src_ids), len(dst_ids))
    src_ids, dst_ids = src_ids[:min_len], dst_ids[:min_len]
    edge_type_arr = edge_type[:min_len]

    topo, sta_keep = compute_topo_order_with_dag_mask(
        num_nodes, src_ids, dst_ids, edge_type=edge_type_arr,
    )
    n_keep = int(sta_keep.sum())
    n_total = len(sta_keep)
    n_sources = np.sum(np.isin(np.arange(num_nodes),
                               np.setdiff1d(np.arange(num_nodes),
                                            np.unique(dst_ids[dst_ids >= 0]))))
    if n_keep == n_total:
        print(f"  [OK] Topological order: {num_nodes} nodes, ~{n_sources} sources (DAG)")
    else:
        print(f"  [OK] Topological order: {num_nodes} nodes, ~{n_sources} sources "
              f"({n_total - n_keep} back edges cut for DAG)")
    return topo


def run_all_checks(
    data_root: Path,
    benchmarks: List[str],
    anchors: List[str],
) -> Dict[str, np.ndarray]:
    """Run all sanity checks. Returns {benchmark: topo_order}."""
    print("=" * 60)
    print("Running sanity checks …")
    print("=" * 60)

    topo_orders = {}

    for bm in benchmarks:
        bm_dir = data_root / bm
        static_dir = bm_dir / "static"
        nid_map = read_node_id_map(static_dir / "node_id_map.json")
        print(f"\n[{bm}]")

        # 1. Topological order
        topo = check_topo_order(static_dir)
        topo_orders[bm] = topo

        # 2. Per-corner checks
        corners_dir = bm_dir / "corners"
        if not corners_dir.exists():
            print(f"  [SKIP] corners/ not found")
            continue

        for corner_path in sorted(corners_dir.iterdir()):
            if not corner_path.is_dir():
                continue
            cn = corner_path.name
            check_edge_count(static_dir, corner_path, cn)
            check_net_mask(static_dir, corner_path, cn)
            check_channel_semantics(corner_path, cn)  # NEW: channel check
            print_corner_stats(corner_path, cn, nid_map)  # NEW: stats

        # 3. Anchor presence
        for anc in anchors:
            anc_dir = corners_dir / anc
            if not anc_dir.exists():
                print(f"  [ERROR] Anchor corner missing: {anc}")
            elif not (anc_dir / "arc_delay.json").exists():
                print(f"  [ERROR] Anchor {anc} missing arc_delay.json")
            else:
                print(f"  [OK] Anchor present: {anc}")

    print("\n" + "=" * 60)
    print("Sanity checks complete.")
    print("=" * 60)
    return topo_orders
