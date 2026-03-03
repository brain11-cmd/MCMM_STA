#!/usr/bin/env python3
import argparse
import re
from typing import List, Set, Tuple

ASSIGN_RE = re.compile(r"^\s*assign\s+(?P<lhs>.+?)\s*=\s*(?P<rhs>.+?)\s*;\s*$")

ISOLAND_RE = re.compile(
    r"ISOLANDX1_RVT\s+(\w+)\s*\(\s*\n\s*\.D\(([^)]+)\),\s*\n\s*\.ISO\(([^)]+)\),\s*\n\s*\.Q\(([^)]+)\)\s*\n\s*\);",
    re.MULTILINE,
)
ISOLOR_RE = re.compile(
    r"ISOLORX1_RVT\s+(\w+)\s*\(\s*\n\s*\.D\(([^)]+)\),\s*\n\s*\.ISO\(([^)]+)\),\s*\n\s*\.Q\(([^)]+)\)\s*\n\s*\);",
    re.MULTILINE,
)

PRINT_BLOCK_RE = re.compile(
    r"^\s*\\\$print\s*#\(.*?\)\s*\w+\s*\(.*?\);\s*$",
    re.DOTALL | re.MULTILINE,
)

CONST_RE = re.compile(r"^(\d+)'b([01]+)$")
SINGLE_CONST_RE = re.compile(r"^1'b([01])$")


def split_concat(expr: str) -> List[str]:
    expr = expr.strip()
    if not expr.startswith("{"):
        return [expr]
    if not expr.endswith("}"):
        return [expr]
    inner = expr[1:-1].strip()
    if not inner:
        return []
    items = [item.strip() for item in inner.split(",")]
    return items


def expand_constant(expr: str, width: int) -> List[str]:
    expr = expr.strip()
    match = CONST_RE.match(expr)
    if match:
        bit_width = int(match.group(1))
        bits = match.group(2)
        if bit_width != len(bits):
            return []
        if width != bit_width:
            return []
        return [f"1'b{bit}" for bit in bits]
    match = SINGLE_CONST_RE.match(expr)
    if match and width == 1:
        return [f"1'b{match.group(1)}"]
    return []


def expand_concat_constants(items: List[str]) -> List[str]:
    expanded: List[str] = []
    for item in items:
        item = item.strip()
        match = CONST_RE.match(item)
        if match:
            bits = match.group(2)
            expanded.extend([f"1'b{bit}" for bit in bits])
            continue
        expanded.append(item)
    return expanded


def _next_available_name(prefix: str, index: int, existing: Set[str]) -> Tuple[str, int]:
    while True:
        name = f"{prefix}{index}_"
        if name not in existing:
            existing.add(name)
            return name, index + 1
        index += 1


def convert_assigns(
    lines: List[str], cell_index_start: int, existing_names: Set[str]
) -> Tuple[List[str], int]:
    new_lines: List[str] = []
    cell_index = cell_index_start

    for line in lines:
        match = ASSIGN_RE.match(line)
        if not match:
            new_lines.append(line)
            continue

        lhs_expr = match.group("lhs").strip()
        rhs_expr = match.group("rhs").strip()
        lhs_items = split_concat(lhs_expr)
        rhs_items = split_concat(rhs_expr)
        rhs_items = expand_concat_constants(rhs_items)

        if len(lhs_items) != 1 and len(rhs_items) == 1:
            const_bits = expand_constant(rhs_items[0], len(lhs_items))
            if const_bits:
                rhs_items = const_bits
        if len(lhs_items) == 1 and len(rhs_items) != 1:
            const_bits = expand_constant(lhs_items[0], len(rhs_items))
            if const_bits:
                lhs_items = const_bits

        if len(lhs_items) != len(rhs_items):
            new_lines.append(line)
            continue

        for lhs, rhs in zip(lhs_items, rhs_items):
            lhs = lhs.strip()
            rhs = rhs.strip()
            if SINGLE_CONST_RE.match(rhs):
                const_val = SINGLE_CONST_RE.match(rhs).group(1)
                cell_name, cell_index = _next_available_name(
                    "_assign_tie_", cell_index, existing_names
                )
                cell_type = "TIEH_RVT" if const_val == "1" else "TIEL_RVT"
                new_lines.append(
                    f"  {cell_type} {cell_name} (\n    .Y({lhs})\n  );\n"
                )
                continue
            cell_name, cell_index = _next_available_name(
                "_assign_buf_", cell_index, existing_names
            )
            new_lines.append(
                f"  IBUFFX2_RVT {cell_name} (\n    .A({rhs}),\n    .Y({lhs})\n  );\n"
            )

    return new_lines, cell_index


def replace_isolation_cells(content: str) -> str:
    def replace_isoland(match):
        instance = match.group(1)
        d_pin = match.group(2).strip()
        iso_pin = match.group(3).strip()
        q_pin = match.group(4).strip()
        return (
            f"AND2X1_RVT {instance} (\n"
            f"  .A1({d_pin}),\n"
            f"  .A2({iso_pin}),\n"
            f"  .Y({q_pin})\n"
            f");"
        )

    def replace_isolor(match):
        instance = match.group(1)
        d_pin = match.group(2).strip()
        iso_pin = match.group(3).strip()
        q_pin = match.group(4).strip()
        return (
            f"OR2X1_RVT {instance} (\n"
            f"  .A1({d_pin}),\n"
            f"  .A2({iso_pin}),\n"
            f"  .Y({q_pin})\n"
            f");"
        )

    content = ISOLAND_RE.sub(replace_isoland, content)
    content = ISOLOR_RE.sub(replace_isolor, content)
    return content


def remove_print_blocks(content: str) -> str:
    return PRINT_BLOCK_RE.sub("", content)


def _extract_existing_names(content: str) -> Set[str]:
    names = set()
    for match in re.finditer(r"^\s*\w+\s+(\w+)\s*\(", content, re.MULTILINE):
        names.add(match.group(1))
    return names


def _next_assign_index(content: str) -> int:
    indices = []
    for match in re.finditer(r"_assign_(?:buf|tie)_(\d+)_", content):
        indices.append(int(match.group(1)))
    return max(indices) + 1 if indices else 0


def process_netlist(path: str, remove_print: bool, fix_isolation: bool) -> None:
    with open(path, "r", encoding="utf-8") as file:
        content = file.read()

    if remove_print:
        content = remove_print_blocks(content)

    if fix_isolation:
        content = replace_isolation_cells(content)

    existing_names = _extract_existing_names(content)
    next_index = _next_assign_index(content)
    lines = content.splitlines(keepends=True)
    new_lines, _ = convert_assigns(lines, next_index, existing_names)
    content = "".join(new_lines)

    with open(path, "w", encoding="utf-8") as file:
        file.write(content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--remove-print", action="store_true")
    parser.add_argument("--fix-isolation", action="store_true")
    args = parser.parse_args()

    process_netlist(args.path, args.remove_print, args.fix_isolation)
