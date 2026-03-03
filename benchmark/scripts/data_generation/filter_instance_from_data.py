#!/usr/bin/env python3
"""Filter __INSTANCE__ nodes from all data files for training."""
import json
import csv
import sys
from pathlib import Path
from typing import Set

def load_train_nodes(csv_file: Path) -> Set[str]:
    """Load pin names from training node set."""
    pins = set()
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pins.add(row['pin_name'])
    return pins

def filter_arc_delay_json(input_file: Path, output_file: Path, train_nodes: Set[str]):
    """Filter arcs that reference __INSTANCE__ nodes."""
    print(f"\nFiltering: {input_file.name}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    arcs = data.get('arcs', [])
    print(f"  Input arcs: {len(arcs)}")
    
    filtered_arcs = []
    removed_count = 0
    
    for arc in arcs:
        src = arc.get('src', '')
        dst = arc.get('dst', '')
        
        # Filter out arcs that reference __INSTANCE__ nodes
        if src in train_nodes and dst in train_nodes:
            # Renumber edge_id
            arc['edge_id'] = len(filtered_arcs)
            filtered_arcs.append(arc)
        else:
            removed_count += 1
            if removed_count <= 5:
                print(f"    Removed: {src} -> {dst}")
    
    print(f"  Output arcs: {len(filtered_arcs)}")
    print(f"  Removed: {removed_count}")
    
    data['arcs'] = filtered_arcs
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    
    print(f"  Wrote: {output_file.name}")

def filter_arrival_txt(input_file: Path, output_file: Path, train_nodes: Set[str]):
    """Filter arrival.txt to only include training nodes."""
    print(f"\nFiltering: {input_file.name}")
    
    lines_kept = 0
    lines_removed = 0
    
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as f_in:
        with open(output_file, 'w', encoding='utf-8') as f_out:
            for line in f_in:
                # Keep header and separator lines
                if line.startswith('Arrival') or line.startswith('-') or not line.strip():
                    f_out.write(line)
                    continue
                
                parts = line.split()
                if len(parts) >= 5:
                    pin_name = parts[-1]
                    if pin_name.lower() in ['pin', 'e/r', 'e/f', 'l/r', 'l/f']:
                        f_out.write(line)
                        continue
                    
                    if pin_name in train_nodes:
                        f_out.write(line)
                        lines_kept += 1
                    else:
                        lines_removed += 1
                else:
                    f_out.write(line)
    
    print(f"  Lines kept: {lines_kept}")
    print(f"  Lines removed: {lines_removed}")
    print(f"  Wrote: {output_file.name}")

def filter_slew_txt(input_file: Path, output_file: Path, train_nodes: Set[str]):
    """Filter slew.txt to only include training nodes."""
    print(f"\nFiltering: {input_file.name}")
    
    lines_kept = 0
    lines_removed = 0
    
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as f_in:
        with open(output_file, 'w', encoding='utf-8') as f_out:
            for line in f_in:
                # Keep header and separator lines
                if line.startswith('Slew') or line.startswith('-') or not line.strip():
                    f_out.write(line)
                    continue
                
                parts = line.split()
                if len(parts) >= 5:
                    pin_name = parts[-1]
                    if pin_name.lower() in ['pin', 'e/r', 'e/f', 'l/r', 'l/f']:
                        f_out.write(line)
                        continue
                    
                    if pin_name in train_nodes:
                        f_out.write(line)
                        lines_kept += 1
                    else:
                        lines_removed += 1
                else:
                    f_out.write(line)
    
    print(f"  Lines kept: {lines_kept}")
    print(f"  Lines removed: {lines_removed}")
    print(f"  Wrote: {output_file.name}")

def filter_pin_cap_txt(input_file: Path, output_file: Path, train_nodes: Set[str]):
    """Filter pin_cap.txt to only include training nodes."""
    print(f"\nFiltering: {input_file.name}")
    
    lines_kept = 0
    lines_removed = 0
    
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as f_in:
        with open(output_file, 'w', encoding='utf-8') as f_out:
            for line in f_in:
                # Keep header and separator lines
                if line.startswith('Pin') or line.startswith('-') or not line.strip():
                    f_out.write(line)
                    continue
                
                # Parse format: "  _387_:CLK           0.123"
                # Pin name is the first non-empty part
                parts = line.split()
                if len(parts) >= 2:
                    # Try to find pin name (first part that's not a number)
                    pin_name = None
                    for part in parts:
                        if not part.replace('.', '').replace('-', '').isdigit():
                            pin_name = part
                            break
                    
                    if pin_name and pin_name.lower() not in ['pin', 'capacitance']:
                        if pin_name in train_nodes:
                            f_out.write(line)
                            lines_kept += 1
                        else:
                            lines_removed += 1
                    else:
                        f_out.write(line)
                else:
                    f_out.write(line)
    
    print(f"  Lines kept: {lines_kept}")
    print(f"  Lines removed: {lines_removed}")
    print(f"  Wrote: {output_file.name}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python filter_instance_from_data.py <benchmark_dir>")
        print("  Example: python filter_instance_from_data.py test_output/gcd")
        sys.exit(1)
    
    benchmark_dir = Path(sys.argv[1])
    static_dir = benchmark_dir / "static"
    anchor_dir = benchmark_dir / "anchor_corners" / "tt0p85v25c"
    
    # Load training node set
    train_csv = static_dir / "node_static_train.csv"
    if not train_csv.exists():
        print(f"Error: {train_csv} not found")
        print("  Run filter_instance_nodes.py first")
        sys.exit(1)
    
    print(f"Loading training node set: {train_csv}")
    train_nodes = load_train_nodes(train_csv)
    print(f"  Training nodes: {len(train_nodes)}")
    
    # Create train subdirectory
    train_dir = anchor_dir / "train"
    train_dir.mkdir(exist_ok=True)
    
    # Filter each file
    if (anchor_dir / "arc_delay.json").exists():
        filter_arc_delay_json(
            anchor_dir / "arc_delay.json",
            train_dir / "arc_delay.json",
            train_nodes
        )
    
    if (anchor_dir / "arrival.txt").exists():
        filter_arrival_txt(
            anchor_dir / "arrival.txt",
            train_dir / "arrival.txt",
            train_nodes
        )
    
    if (anchor_dir / "slew.txt").exists():
        filter_slew_txt(
            anchor_dir / "slew.txt",
            train_dir / "slew.txt",
            train_nodes
        )
    
    if (anchor_dir / "pin_cap.txt").exists():
        filter_pin_cap_txt(
            anchor_dir / "pin_cap.txt",
            train_dir / "pin_cap.txt",
            train_nodes
        )
    
    print("\n" + "="*60)
    print("Filtering complete!")
    print(f"  Training data saved to: {train_dir}")
    print("  Original data preserved in: {anchor_dir}")

if __name__ == "__main__":
    main()

