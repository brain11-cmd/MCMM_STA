"""
I/O helpers — read the data files produced by the export pipeline.

Supported formats:
  - graph_edges.csv   (edge_id, src, dst, edge_type)
  - node_static.csv   (node_id, pin_name, fanin, fanout, cell_type, pin_role)
  - node_id_map.json  (pin_name -> node_id)
  - arc_delay.json    (corner, time_unit, arcs[])
  - arrival.txt / slew.txt / pin_cap.txt  (header + E/R E/F L/R L/F Pin)
  - endpoints.csv     (endpoint_pin, rf, slack_late, arrival_late, required_late, valid)
  - splits.json       (anchors, train_targets, val_targets, test_targets)
"""

import csv
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional

import numpy as np


# ---- corner name parsing ----

_CORNER_RE = re.compile(
    r"^(?P<process>ff|ss|tt)"
    r"(?P<voltage>\d+p\d+)"
    r"v"
    r"(?P<temp>n?\d+)"
    r"c$"
)


def parse_corner_name(corner: str) -> Dict[str, float]:
    """
    Parse corner name into (process_str, voltage, temperature).
    e.g. 'ff0p85vn40c' -> {'process': 'ff', 'voltage': 0.85, 'temp': -40.0}
    """
    m = _CORNER_RE.match(corner)
    if m is None:
        raise ValueError(f"Cannot parse corner name: {corner}")
    proc = m.group("process")
    volt_str = m.group("voltage").replace("p", ".")
    temp_str = m.group("temp").replace("n", "-")
    return {
        "process": proc,
        "voltage": float(volt_str),
        "temp": float(temp_str),
    }


# ---- file readers ----

def read_splits(path: Path) -> Dict:
    """Read splits.json."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_node_id_map(path: Path) -> Dict[str, int]:
    """Read node_id_map.json: pin_name -> node_id."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_graph_edges(path: Path) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Read graph_edges.csv.
    
    Returns:
        edge_ids:  [E] int
        src_pins:  [E] str  (pin name)
        dst_pins:  [E] str
        edge_type: [E] int  (0=cell, 1=net)
    """
    edge_ids, srcs, dsts, etypes = [], [], [], []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            edge_ids.append(int(row["edge_id"]))
            srcs.append(row["src"])
            dsts.append(row["dst"])
            etypes.append(int(row["edge_type"]))
    return (
        np.array(edge_ids, dtype=np.int64),
        np.array(srcs),
        np.array(dsts),
        np.array(etypes, dtype=np.int64),
    )


def read_node_static(path: Path) -> Dict[str, Dict]:
    """
    Read node_static.csv.
    Returns dict: pin_name -> {node_id, fanin, fanout, cell_type, pin_role}
    """
    data = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            data[row["pin_name"]] = {
                "node_id": int(row["node_id"]),
                "fanin": int(row["fanin"]),
                "fanout": int(row["fanout"]),
                "cell_type": row["cell_type"],
                "pin_role": row["pin_role"],
            }
    return data


def read_arc_delay_json(path: Path) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Read arc_delay.json.
    
    Returns:
        delays: [E, 4]  float32  (dRR, dRF, dFR, dFF)
        masks:  [E, 4]  int32    (maskRR, maskRF, maskFR, maskFF)
        edge_valid: [E]  int32
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    arcs = data["arcs"]
    E = len(arcs)
    delays = np.zeros((E, 4), dtype=np.float32)
    masks = np.zeros((E, 4), dtype=np.int32)
    edge_valid = np.zeros(E, dtype=np.int32)

    for arc in arcs:
        eid = arc["edge_id"]
        d = arc["delay"]
        m = arc["mask"]
        delays[eid] = [d["dRR"], d["dRF"], d["dFR"], d["dFF"]]
        masks[eid] = [m["maskRR"], m["maskRF"], m["maskFR"], m["maskFF"]]
        edge_valid[eid] = arc.get("edge_valid", 1 if sum(masks[eid]) > 0 else 0)

    return delays, masks, edge_valid


def _read_pin_txt(path: Path) -> Dict[str, np.ndarray]:
    """
    Generic reader for arrival.txt / slew.txt / pin_cap.txt / rat.txt / slack.txt.
    Format: header lines, then  E/R  E/F  L/R  L/F  Pin
    
    Returns: pin_name -> np.array([ER, EF, LR, LF], dtype=float32)
    """
    data = {}
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("-"):
                continue
            # skip header-like lines
            if "E/R" in line and "Pin" in line:
                continue
            # skip title lines (e.g. "Arrival time [pins:877]")
            if "[" in line and "]" in line:
                continue
            parts = line.split()
            if len(parts) < 5:
                continue
            try:
                vals = list(map(float, parts[:4]))
                pin_name = parts[-1]
                data[pin_name] = np.array(vals, dtype=np.float32)
            except ValueError:
                continue
    return data


def read_arrival(path: Path) -> Dict[str, np.ndarray]:
    return _read_pin_txt(path)


def read_slew(path: Path) -> Dict[str, np.ndarray]:
    return _read_pin_txt(path)


def read_pin_cap(path: Path) -> Dict[str, np.ndarray]:
    return _read_pin_txt(path)


def read_rat(path: Path) -> Dict[str, np.ndarray]:
    return _read_pin_txt(path)


def read_slack(path: Path) -> Dict[str, np.ndarray]:
    return _read_pin_txt(path)


def read_endpoints_csv(path: Path) -> List[Dict]:
    """
    Read endpoints.csv.
    Returns list of dicts with keys:
      endpoint_pin, rf, slack_late, arrival_late, required_late, valid
    """
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "endpoint_pin": row["endpoint_pin"],
                "rf": row["rf"],
                "slack_late": float(row["slack_late"]),
                "arrival_late": float(row["arrival_late"]),
                "required_late": float(row["required_late"]),
                "valid": int(row["valid"]),
            })
    return rows




















