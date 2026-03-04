"""
Differentiable STA (v2.3 — GPU-friendly, AMP-safe, vectorized).

Two implementations:
  - LevelwiseSTA:       GPU-friendly, loops over topological levels (recommended)
  - DifferentiableSTA:  Original per-node loop version (CPU fallback / reference)

v2.3 fixes over v2.2:
  - scatter_smoothmax: fp32 internal + bincount for no-candidate detection
  - LevelwiseSTA: removed torch.maximum (was implicit self-loop / hard max);
    now direct torch.where assignment per level
  - LevelwiseSTA: precompute edge indices per level (avoid O(E) scan each level)
  - LevelwiseSTA: vectorized candidate construction (less kernel fragmentation)

Channel convention (MUST match arc_delay.json):
    [0]=RR: rise_input -> rise_output
    [1]=RF: rise_input -> fall_output
    [2]=FR: fall_input -> rise_output
    [3]=FF: fall_input -> fall_output

STA propagation:
    AT[v, Rise] = smoothmax over e=(u->v):  { AT[u,R]+d[RR],  AT[u,F]+d[FR] }
    AT[v, Fall] = smoothmax over e=(u->v):  { AT[u,R]+d[RF],  AT[u,F]+d[FF] }
"""

from typing import Tuple, Dict, List
from collections import defaultdict

import torch
import torch.nn as nn

# Sentinel for "not reachable" — large negative but not -inf (avoids NaN in exp)
NEG_INF = -1e30


# ---------------------------------------------------------------------------
# STA mask builder (shared by both implementations)
# ---------------------------------------------------------------------------

def build_sta_mask(
    data_mask: torch.Tensor,
    edge_type: torch.Tensor,
    edge_valid: torch.Tensor,
    sta_edge_keep: torch.Tensor = None,
) -> torch.Tensor:
    """
    Build the STA propagation mask.

    Execution order:
      Step 1: Start from data_mask
      Step 2: Zero out channels where edge_valid=0 AND edge is a cell arc
      Step 3: ALL net arcs -> force [1,0,0,1]
      Step 4: Zero out back edges (cycle cuts) via sta_edge_keep mask

    Args:
        sta_edge_keep: [E] bool — False for back edges cut to break cycles.
                       These edges are excluded from STA but kept in edge loss.

    Returns: [E, 4] float mask
    """
    sta_mask = data_mask.clone().float()

    is_net = (edge_type == 1)
    is_cell = ~is_net
    invalid = (edge_valid < 0.5)

    # Step 2: edge_valid=0 zeroes ONLY cell arcs (not net arcs)
    cell_invalid = is_cell & invalid
    sta_mask[cell_invalid] = 0.0

    # Step 3: ALL net arcs -> force [1,0,0,1] (wire: same-polarity passthrough)
    sta_mask[is_net, 0] = 1.0   # RR
    sta_mask[is_net, 1] = 0.0   # RF
    sta_mask[is_net, 2] = 0.0   # FR
    sta_mask[is_net, 3] = 1.0   # FF

    # Step 4: Zero out back edges (cycle cuts) — excluded from STA propagation
    if sta_edge_keep is not None:
        cut_edges = ~sta_edge_keep.bool()
        if cut_edges.any():
            sta_mask[cut_edges] = 0.0

    return sta_mask


# ---------------------------------------------------------------------------
# scatter_smoothmax (for LevelwiseSTA) — AMP-safe, fp32 internal
# ---------------------------------------------------------------------------

def scatter_smoothmax(
    values: torch.Tensor,
    index: torch.Tensor,
    dim_size: int,
    tau: float,
) -> torch.Tensor:
    """
    GPU-friendly smoothmax via scatter LogSumExp (AMP-safe).

    All internal accumulation is done in fp32 to avoid fp16 overflow.
    Returns NEG_INF for nodes with no candidates.

    Args:
        values: [M] candidate arrival times
        index:  [M] destination node id for each candidate (must be torch.long)
        dim_size: total number of nodes N
        tau:    smoothmax temperature

    Returns:
        out: [dim_size] smoothmax per node (same dtype as values)
    """
    assert index.dtype == torch.long, f"index must be torch.long, got {index.dtype}"
    orig_dtype = values.dtype
    device = values.device

    # Force fp32 for stability
    v = values.float()

    # max per group
    max_val = torch.full((dim_size,), NEG_INF, device=device, dtype=torch.float32)
    max_val.scatter_reduce_(0, index, v, reduce="amax", include_self=False)

    # exp((x - max) / tau) sum
    expv = torch.exp((v - max_val.index_select(0, index)) / float(tau))
    sum_exp = torch.zeros(dim_size, device=device, dtype=torch.float32)
    sum_exp.scatter_add_(0, index, expv)

    # out = max + tau * log(sum_exp)
    out = max_val + float(tau) * torch.log(sum_exp.clamp_min(1e-30))

    # No-candidate detection via bincount (robust, not threshold-based)
    has_candidate = torch.bincount(index, minlength=dim_size) > 0
    out = torch.where(has_candidate, out, torch.full_like(out, NEG_INF))

    return out.to(dtype=orig_dtype)


# ---------------------------------------------------------------------------
# LevelwiseSTA (recommended — GPU-friendly, vectorized)
# ---------------------------------------------------------------------------

class LevelwiseSTA(nn.Module):
    """
    GPU-friendly differentiable STA via level-wise scatter smoothmax.

    Instead of looping over every node (O(N) Python iterations), loops over
    topological levels (typically 20-100 levels << N nodes).  Within each
    level, all operations are batched GPU tensor ops.

    v2.3 improvements:
      - Direct assignment (no torch.maximum — was implicit self-loop)
      - Precomputed edge indices per level (O(E_l) per level, not O(E))
      - Vectorized candidate construction (one cat + mask, not conditional appends)

    Requires precomputed static tensors:
      node_level: [N] int64 — topological depth (sources=0)
      edge_level: [E] int64 — node_level[edge_dst] (which level each edge feeds)
      max_level:  int        — max(node_level)
    """

    def __init__(self, tau_sta: float = 0.07, tf_interval: int = 20):
        super().__init__()
        self.tau_sta = tau_sta
        self.tf_interval = tf_interval
        self._lvl_cache: Dict[tuple, tuple] = {}

    def forward(
        self,
        d_hat: torch.Tensor,            # [E, 4]
        sta_mask: torch.Tensor,          # [E, 4]
        edge_src: torch.Tensor,          # [E] long
        edge_dst: torch.Tensor,          # [E] long
        input_arrival: torch.Tensor,     # [N, 2] sources=fused, else NEG_INF
        endpoint_ids: torch.Tensor,      # [M] long
        rat_true: torch.Tensor,          # [M, 2]
        node_level: torch.Tensor,        # [N] long (static, precomputed)
        edge_level: torch.Tensor,        # [E] long (static, precomputed)
        max_level: int,                  # python int (static)
        at_true: torch.Tensor = None,    # [N, 2] ground-truth arrival (for TF)
        tf_ratio: float = 0.0,           # teacher forcing blend (0=off)
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Returns:
            at_all:    [N, 2]  arrival times at all nodes
            at_ep:     [M, 2]  arrival times at endpoints
            slack_hat: [M, 2]  = RAT_true - AT_hat
        """
        tau = self.tau_sta
        N = input_arrival.shape[0]

        d = d_hat * sta_mask  # [E, 4] masked delays

        at_r = input_arrival[:, 0].clone()  # [N]
        at_f = input_arrival[:, 1].clone()  # [N]

        use_tf = (tf_ratio > 0 and at_true is not None
                  and self.training and self.tf_interval > 0)
        if use_tf:
            gt_r = at_true[:, 0].detach()
            gt_f = at_true[:, 1].detach()
            gt_valid = at_true.abs().sum(dim=1) > 1e-6

        # --- Level grouping (cached per unique graph) ---
        # Key includes edge_level.data_ptr() to guarantee collision-free caching
        # even if two benchmarks happen to share (N, E, max_level).
        E = edge_level.shape[0]
        _key = (N, E, max_level, edge_level.data_ptr())
        if _key in self._lvl_cache:
            order, counts_cpu, offsets_cpu = self._lvl_cache[_key]
            if order.device != d_hat.device:
                order = order.to(d_hat.device)
                self._lvl_cache[_key] = (order, counts_cpu, offsets_cpu)
        else:
            order = torch.argsort(edge_level)
            level_counts = torch.bincount(edge_level, minlength=max_level + 1)
            level_offsets = torch.zeros_like(level_counts)
            level_offsets[1:] = level_counts[:-1].cumsum(0)
            counts_cpu = level_counts.cpu().long()
            offsets_cpu = level_offsets.cpu().long()
            self._lvl_cache[_key] = (order, counts_cpu, offsets_cpu)

        # --- Level-wise propagation ---
        for lvl in range(1, max_level + 1):
            cnt = int(counts_cpu[lvl])
            if cnt == 0:
                continue
            eidx = order[int(offsets_cpu[lvl]):int(offsets_cpu[lvl]) + cnt]
            vmask = (node_level == lvl)

            es = edge_src[eidx]
            ed = edge_dst[eidx]
            de = d[eidx]
            me = sta_mask[eidx]

            ur = at_r.index_select(0, es)
            uf = at_f.index_select(0, es)

            # ---- Rise candidates ----
            rise_vals = torch.cat([ur + de[:, 0], uf + de[:, 2]])
            rise_idx = torch.cat([ed, ed])
            rise_valid = torch.cat([me[:, 0] > 0.5, me[:, 2] > 0.5])

            if rise_valid.any():
                upd_r = scatter_smoothmax(
                    rise_vals[rise_valid], rise_idx[rise_valid], N, tau
                )
                at_r = torch.where(vmask, upd_r, at_r)

            # ---- Fall candidates ----
            fall_vals = torch.cat([ur + de[:, 1], uf + de[:, 3]])
            fall_idx = torch.cat([ed, ed])
            fall_valid = torch.cat([me[:, 1] > 0.5, me[:, 3] > 0.5])

            if fall_valid.any():
                upd_f = scatter_smoothmax(
                    fall_vals[fall_valid], fall_idx[fall_valid], N, tau
                )
                at_f = torch.where(vmask, upd_f, at_f)

            # ---- Teacher forcing: blend every tf_interval levels ----
            if use_tf and lvl % self.tf_interval == 0:
                reachable = (at_r > (NEG_INF + 1)) | (at_f > (NEG_INF + 1))
                blend_mask = vmask & gt_valid & reachable
                if blend_mask.any():
                    at_r = torch.where(
                        blend_mask,
                        (1.0 - tf_ratio) * at_r + tf_ratio * gt_r,
                        at_r,
                    )
                    at_f = torch.where(
                        blend_mask,
                        (1.0 - tf_ratio) * at_f + tf_ratio * gt_f,
                        at_f,
                    )

        # Stack into [N, 2]
        at_all = torch.stack([at_r, at_f], dim=1)

        # Endpoint arrival
        at_ep = at_all.index_select(0, endpoint_ids)  # [M, 2]

        # Guard: unreachable endpoints (still NEG_INF) -> fallback to 0
        reachable = at_ep > (NEG_INF + 1)
        at_ep_safe = torch.where(reachable, at_ep, torch.zeros_like(at_ep))
        slack_hat = rat_true - at_ep_safe

        return at_all, at_ep_safe, slack_hat


# ---------------------------------------------------------------------------
# smoothmax scalar helper (for DifferentiableSTA fallback)
# ---------------------------------------------------------------------------

def smoothmax(values: torch.Tensor, tau: float = 0.07) -> torch.Tensor:
    """
    Numerically-stable smooth maximum via LogSumExp.
    Returns NEG_INF if no valid candidates (not 0!).
    """
    if values.numel() == 0:
        return torch.tensor(NEG_INF, device=values.device, dtype=values.dtype)
    if values.numel() == 1:
        return values.squeeze()
    m = values.max()
    return m + tau * torch.log(torch.exp((values - m) / tau).sum() + 1e-30)


# ---------------------------------------------------------------------------
# DifferentiableSTA (original per-node loop — CPU reference / fallback)
# ---------------------------------------------------------------------------

class DifferentiableSTA(nn.Module):
    """
    Original per-node STA (v2.1).  Kept as reference / CPU fallback.

    Loops over every node in topological order — slow on GPU but correct.
    Prefer LevelwiseSTA for training.
    """

    def __init__(self, tau_sta: float = 0.07):
        super().__init__()
        self.tau_sta = tau_sta

    def forward(
        self,
        d_hat: torch.Tensor,            # [E, 4]
        sta_mask: torch.Tensor,          # [E, 4]
        edge_src: torch.Tensor,          # [E] long
        edge_dst: torch.Tensor,          # [E] long
        topo_order: torch.Tensor,        # [N] long
        input_arrival: torch.Tensor,     # [N, 2]
        endpoint_ids: torch.Tensor,      # [M] long
        rat_true: torch.Tensor,          # [M, 2]
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Returns:
            at_all:    [N, 2]
            at_ep:     [M, 2]
            slack_hat: [M, 2] = RAT_true - AT_hat
        """
        N = topo_order.shape[0]
        E = d_hat.shape[0]
        tau = self.tau_sta

        d_masked = d_hat * sta_mask

        # Build adjacency: dst -> list of edge indices (CPU, one-time)
        dst_to_edges: Dict[int, List[int]] = defaultdict(list)
        dst_np = edge_dst.cpu().numpy()
        for eidx in range(E):
            d = int(dst_np[eidx])
            if d >= 0:
                dst_to_edges[d].append(eidx)

        # Per-node arrival as separate tensor elements (preserves autograd)
        at_r: List[torch.Tensor] = [input_arrival[i, 0] for i in range(N)]
        at_f: List[torch.Tensor] = [input_arrival[i, 1] for i in range(N)]

        topo_np = topo_order.cpu().numpy()
        src_np = edge_src.cpu().numpy()

        for v_int in topo_np:
            v = int(v_int)
            incoming = dst_to_edges.get(v, [])
            if not incoming:
                continue

            cand_rise: List[torch.Tensor] = []
            cand_fall: List[torch.Tensor] = []

            for eidx in incoming:
                m_e = sta_mask[eidx]
                if m_e.sum() < 0.5:
                    continue

                u = int(src_np[eidx])
                if u < 0:
                    continue

                d_e = d_masked[eidx]
                u_r = at_r[u]
                u_f = at_f[u]

                if m_e[0] > 0.5 and u_r.item() > NEG_INF + 1:  # RR
                    cand_rise.append(u_r + d_e[0])
                if m_e[2] > 0.5 and u_f.item() > NEG_INF + 1:  # FR
                    cand_rise.append(u_f + d_e[2])
                if m_e[1] > 0.5 and u_r.item() > NEG_INF + 1:  # RF
                    cand_fall.append(u_r + d_e[1])
                if m_e[3] > 0.5 and u_f.item() > NEG_INF + 1:  # FF
                    cand_fall.append(u_f + d_e[3])

            if cand_rise:
                at_r[v] = smoothmax(torch.stack(cand_rise), tau)
            if cand_fall:
                at_f[v] = smoothmax(torch.stack(cand_fall), tau)

        at_all = torch.stack([torch.stack(at_r), torch.stack(at_f)], dim=1)
        at_ep = at_all[endpoint_ids]

        reachable = at_ep > (NEG_INF + 1)
        at_ep_safe = torch.where(reachable, at_ep, torch.zeros_like(at_ep))
        slack_hat = rat_true - at_ep_safe

        return at_all, at_ep_safe, slack_hat
