#!/usr/bin/env python3
import argparse
import math
import os
import subprocess
import sys
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


def main():
    p = argparse.ArgumentParser(
        description="Run script.py in parallel, auto-splitting page ranges."
    )
    p.add_argument("--cep", required=True, help="CEP to pass to script.py")
    p.add_argument("--total-pages", type=int, required=True, help="Total pages count (e.g., 73 => pages 0..72)")
    p.add_argument("--num-exec", type=int, required=True, help="Number of executions (also parallelism)")
    p.add_argument("--initial-page", type=int, default=-1, help="Initial page to start from (default: 1)")
    p.add_argument("--max-distance", type=int, default=1, help="--max-distance value for script.py")
    p.add_argument("--script", default="script.py", help="Path to your python script (default: script.py)")
    p.add_argument("--python", default=sys.executable, help="Python executable to use (default: current)")
    p.add_argument("--logs-dir", default="logs", help="Directory to store logs (default: logs)")
    args = p.parse_args()

    ranges = split_ranges(args.total_pages, args.num_exec, args.initial_page)
    logs_dir = Path(args.logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    procs = []
    for idx, (start, end) in enumerate(ranges, start=1):
        log_path = logs_dir / f"job_{idx:03d}_{start}-{end}.log"
        cmd = [
            args.python, "-u", args.script,  # -u for unbuffered output
            f"--max-distance={args.max_distance}",
            f"--cep={args.cep}",
            f"--initial-page={start}",
            f"--max-page={end}",
        ]
        log_f = open(log_path, "w", encoding="utf-8", buffering=1)  # Line buffering for real-time logs
        print(f"[{idx}/{len(ranges)}] pages {start}-{end} -> {log_path}")
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
        sys.exit(1)

    print(f"\nAll done. Logs in: {logs_dir.resolve()}")


if __name__ == "__main__":
    main()

