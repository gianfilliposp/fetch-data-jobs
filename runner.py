#!/usr/bin/env python3
import argparse
import json
import math
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def split_ranges(total_pages: int, num_exec: int, initial_page: int = 1):
    """
    Split pages [initial_page..initial_page+total_pages_1] into num_exec contiguous ranges as evenly as possible.
    Returns list of (start, end) inclusive.
    """
    if total_pages <= 0:
        raise ValueError("total_pages must be > 0")
    if num_exec <= 0:
        raise ValueError("num_exec must be > 0")

    base = total_pages // num_exec
    extra = total_pages % num_exec  # first 'extra' ranges get +1

    ranges = []
    start = initial_page
    for i in range(num_exec):
        size = base + (1 if i < extra else 0)
        if size == 0:
            break
        end = start + size - 1
        ranges.append((start, end))
        start = end + 1
        if start >= initial_page + total_pages:
            break
    return ranges


def run_execution(args, age_min=None, age_max=None, execution_dir=None, age_range_idx=None):
    """Run a single execution with given age filters"""
    ranges = split_ranges(args.total_pages, args.num_exec, args.initial_page)
    
    # Create subdirectory for age range if provided
    if age_range_idx is not None:
        age_dir = execution_dir / f"age_range_{age_range_idx:02d}_min{age_min}_max{age_max}"
        age_dir.mkdir(parents=True, exist_ok=True)
        log_base_dir = age_dir
    else:
        log_base_dir = execution_dir

    procs = []
    for idx, (start, end) in enumerate(ranges, start=1):
        log_path = log_base_dir / f"job_{idx:03d}_{start}-{end}.log"
        cmd = [
            args.python, "-u", args.script,  # -u for unbuffered output
            f"--max-distance={args.max_distance}",
            f"--cep={args.cep}",
            f"--initial-page={start}",
            f"--max-page={end}",
            f"--instancia={args.instancia}",
        ]
        # Add age filters only if provided
        if age_min is not None:
            cmd.append(f"--age-min={age_min}")
        if age_max is not None:
            cmd.append(f"--age-max={age_max}")
        log_f = open(log_path, "w", encoding="utf-8", buffering=1)  # Line buffering for real-time logs
        age_info = f" (age {age_min}-{age_max})" if age_min is not None and age_max is not None else ""
        print(f"[{idx}/{len(ranges)}] pages {start}-{end}{age_info} -> {log_path}")
        procs.append((subprocess.Popen(cmd, stdout=log_f, stderr=subprocess.STDOUT, bufsize=1), log_f, cmd))

    # Wait all
    failed = []
    for proc, log_f, cmd in procs:
        rc = proc.wait()
        log_f.close()
        if rc != 0:
            failed.append((rc, cmd))

    if failed:
        print("\nSome jobs failed:")
        for rc, cmd in failed:
            print(f"  rc={rc} cmd={' '.join(cmd)}")
        return False
    
    return True


def main():
    p = argparse.ArgumentParser(
        description="Run script.py in parallel, auto-splitting page ranges."
    )
    p.add_argument("--cep", required=True, help="CEP to pass to script.py")
    p.add_argument("--total-pages", type=int, required=True, help="Total pages count (e.g., 73 => pages 0..72)")
    p.add_argument("--num-exec", type=int, required=True, help="Number of executions (also parallelism)")
    p.add_argument("--initial-page", type=int, default=1, help="Initial page to start from (default: 1)")
    p.add_argument("--max-distance", type=int, default=1, help="--max-distance value for script.py")
    p.add_argument("--script", default="script.py", help="Path to your python script (default: script.py)")
    p.add_argument("--python", default=sys.executable, help="Python executable to use (default: current)")
    p.add_argument("--logs-dir", default="logs", help="Directory to store logs (default: logs)")
    p.add_argument("--instancia", required=True, help="Instancia para passar ao script.py")
    p.add_argument("--age-min", type=int, default=None, help="--age-min value for script.py (optional)")
    p.add_argument("--age-max", type=int, default=None, help="--age-max value for script.py (optional)")
    p.add_argument("--min-max-age-list", type=str, default=None, 
                   help='JSON list of age ranges, e.g., [{"min": 1, "max": 18}, {"min": 18, "max": 20}]')
    args = p.parse_args()

    # Create timestamp-based execution directory
    now = datetime.now()
    timestamp_dir = now.strftime("%Y-%m-%d_%H-%M-%S")  # YYYY-MM-DD_HH-MM-SS
    execution_dir = Path(args.logs_dir) / timestamp_dir
    execution_dir.mkdir(parents=True, exist_ok=True)

    # Parse age range list if provided
    age_ranges = None
    if args.min_max_age_list:
        try:
            age_ranges = json.loads(args.min_max_age_list)
            if not isinstance(age_ranges, list):
                print("Error: --min-max-age-list must be a JSON array")
                sys.exit(1)
            # Validate each range
            for i, age_range in enumerate(age_ranges):
                if not isinstance(age_range, dict):
                    print(f"Error: Age range {i} must be a JSON object")
                    sys.exit(1)
                if 'min' not in age_range or 'max' not in age_range:
                    print(f"Error: Age range {i} must have 'min' and 'max' keys")
                    sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in --min-max-age-list: {e}")
            sys.exit(1)

    # If age range list is provided, process each range sequentially
    if age_ranges:
        print(f"\n{'='*60}")
        print(f"Processing {len(age_ranges)} age range(s)")
        print(f"{'='*60}\n")
        
        all_success = True
        for idx, age_range in enumerate(age_ranges, start=1):
            age_min = age_range['min']
            age_max = age_range['max']
            print(f"\n{'='*60}")
            print(f"Age Range {idx}/{len(age_ranges)}: {age_min}-{age_max}")
            print(f"{'='*60}\n")
            
            success = run_execution(args, age_min=age_min, age_max=age_max, 
                                   execution_dir=execution_dir, age_range_idx=idx)
            if not success:
                all_success = False
                print(f"\n⚠️  Age range {idx} ({age_min}-{age_max}) had failures")
            else:
                print(f"\n✓ Age range {idx} ({age_min}-{age_max}) completed successfully")
        
        if not all_success:
            print("\n⚠️  Some age ranges had failures")
            sys.exit(1)
        
        print(f"\n{'='*60}")
        print(f"✅ All age ranges completed. Logs in: {execution_dir.resolve()}")
        print(f"{'='*60}")
    else:
        # Single execution with optional age filters
        success = run_execution(args, age_min=args.age_min, age_max=args.age_max, 
                               execution_dir=execution_dir)
        if not success:
            sys.exit(1)
        print(f"\nAll done. Logs in: {execution_dir.resolve()}")


if __name__ == "__main__":
    main()

