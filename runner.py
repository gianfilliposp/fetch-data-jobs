#!/usr/bin/env python3
import argparse
import csv
import json
import math
import os
import subprocess
import sys
import time
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


def read_ceps_from_csv(csv_file='ceps.csv'):
    """Gera CEPs do arquivo CSV um por vez (generator)"""
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                cep = row.get('cep', '').strip()
                if cep:
                    yield cep
    except FileNotFoundError:
        print(f"Erro: Arquivo {csv_file} não encontrado", file=sys.stderr)
        return
    except Exception as e:
        print(f"Erro ao ler arquivo {csv_file}: {e}", file=sys.stderr)
        return


def run_execution(args, cep, execution_dir=None):
    """Run parallel executions of script.py for a single CEP, splitting pages across num_exec processes"""
    # Calculate total pages to process
    total_pages = args.max_page - args.initial_page + 1
    ranges = split_ranges(total_pages, args.num_exec, args.initial_page)
    
    # Create subdirectory for this CEP
    cep_dir = execution_dir / f"cep_{cep.replace('-', '_')}"
    cep_dir.mkdir(parents=True, exist_ok=True)

    procs = []
    for idx, (start, end) in enumerate(ranges, start=1):
        log_path = cep_dir / f"job_{idx:03d}_{start}-{end}.log"
        cmd = [
            args.python, "-u", args.script,  # -u for unbuffered output
            f"--max-distance={args.max_distance}",
            f"--cep={cep}",
            f"--initial-page={start}",
            f"--max-page={end}",
            f"--instancia={args.instancia}",
        ]
        # Add age list if provided
        if args.min_max_age_list:
            cmd.append(f"--min-max-age-list={args.min_max_age_list}")
        elif args.age_min is not None or args.age_max is not None:
            # Single age range
            if args.age_min is not None:
                cmd.append(f"--age-min={args.age_min}")
            if args.age_max is not None:
                cmd.append(f"--age-max={args.age_max}")
        
        log_f = open(log_path, "w", encoding="utf-8", buffering=1)  # Line buffering for real-time logs
        print(f"[{idx}/{len(ranges)}] CEP {cep} - pages {start}-{end} -> {log_path}")
        procs.append((subprocess.Popen(cmd, stdout=log_f, stderr=subprocess.STDOUT, bufsize=1), log_f, cmd))

    # Wait all
    failed = []
    for proc, log_f, cmd in procs:
        rc = proc.wait()
        log_f.close()
        if rc != 0:
            failed.append((rc, cmd))

    if failed:
        print(f"\n  ✗ CEP {cep}: {len(failed)} job(s) falharam:")
        for rc, cmd in failed:
            print(f"    rc={rc} cmd={' '.join(cmd)}")
        return False
    
    return True


def main():
    p = argparse.ArgumentParser(
        description="Run script.py in parallel for each CEP, auto-splitting page ranges."
    )
    p.add_argument("--cep", type=str, default=None, help="Single CEP to process (optional, if not provided reads from ceps.csv)")
    p.add_argument("--ceps-file", type=str, default="ceps.csv", help="CSV file with CEPs (default: ceps.csv)")
    p.add_argument("--total-pages", type=int, required=True, help="Total pages count (e.g., 101 => pages 0..100)")
    p.add_argument("--num-exec", type=int, required=True, help="Number of parallel executions (also parallelism)")
    p.add_argument("--initial-page", type=int, default=0, help="Initial page to start from (default: 0)")
    p.add_argument("--max-distance", type=int, required=True, help="--max-distance value for script.py")
    p.add_argument("--script", default="script.py", help="Path to your python script (default: script.py)")
    p.add_argument("--python", default=sys.executable, help="Python executable to use (default: current)")
    p.add_argument("--logs-dir", default="logs", help="Directory to store logs (default: logs)")
    p.add_argument("--instancia", required=True, help="Instancia para passar ao script.py")
    p.add_argument("--age-min", type=int, default=None, help="--age-min value for script.py (optional)")
    p.add_argument("--age-max", type=int, default=None, help="--age-max value for script.py (optional)")
    p.add_argument("--min-max-age-list", type=str, default=None, 
                   help='JSON list of age ranges, e.g., [{"min": 1, "max": 18}, {"min": 18, "max": 20}]')
    args = p.parse_args()
    
    # Calculate max_page from total_pages and initial_page
    args.max_page = args.initial_page + args.total_pages - 1

    # Create timestamp-based execution directory
    now = datetime.now()
    timestamp_dir = now.strftime("%Y-%m-%d_%H-%M-%S")  # YYYY-MM-DD_HH-MM-SS
    execution_dir = Path(args.logs_dir) / timestamp_dir
    execution_dir.mkdir(parents=True, exist_ok=True)

    # Validate age list if provided
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

    # Get CEPs to process
    if args.cep:
        # Single CEP provided
        ceps_to_process = [args.cep]
        print(f"Processando CEP único: {args.cep}")
    else:
        # Read CEPs from CSV file
        print(f"Lendo CEPs do arquivo {args.ceps_file}")
        ceps_to_process = list(read_ceps_from_csv(args.ceps_file))
        if not ceps_to_process:
            print("Nenhum CEP encontrado. Encerrando.", file=sys.stderr)
            sys.exit(1)
        print(f"Encontrados {len(ceps_to_process)} CEPs para processar")

    print(f"\n{'='*70}")
    print(f"INICIANDO PROCESSAMENTO")
    print(f"CEPs a processar: {len(ceps_to_process)}")
    print(f"Páginas por CEP: {args.total_pages} (de {args.initial_page} a {args.max_page})")
    print(f"Execuções paralelas por CEP: {args.num_exec}")
    if args.min_max_age_list:
        age_ranges = json.loads(args.min_max_age_list)
        print(f"Faixas etárias por CEP: {len(age_ranges)}")
    print(f"{'='*70}\n")

    total_start_time = time.time()
    total_ceps_processed = 0
    failed_ceps = []

    # Process each CEP sequentially
    for cep_idx, cep in enumerate(ceps_to_process, 1):
        print(f"\n{'='*70}")
        print(f"CEP {cep_idx}/{len(ceps_to_process)}: {cep}")
        print(f"{'='*70}")
        
        # Run parallel executions for this CEP (script.py will process all age ranges)
        success = run_execution(args, cep, execution_dir=execution_dir)
        
        if success:
            total_ceps_processed += 1
            print(f"\n✓ CEP {cep} completamente processado ({args.num_exec} execuções paralelas)")
        else:
            failed_ceps.append(cep)
            print(f"\n✗ CEP {cep} falhou")
        
        print(f"{'='*70}\n")

    total_end_time = time.time()
    total_execution_time = total_end_time - total_start_time

    print(f"\n{'='*70}")
    print(f"PROCESSAMENTO COMPLETO")
    print(f"CEPs processados com sucesso: {total_ceps_processed}/{len(ceps_to_process)}")
    if failed_ceps:
        print(f"CEPs com falhas: {len(failed_ceps)}")
        for cep in failed_ceps:
            print(f"  - {cep}")
    print(f"Tempo total: {total_execution_time:.2f}s")
    print(f"Logs em: {execution_dir.resolve()}")
    print(f"{'='*70}")

    if failed_ceps:
        sys.exit(1)


if __name__ == "__main__":
    main()

