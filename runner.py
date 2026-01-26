#!/usr/bin/env python3
import argparse
import csv
import importlib.util
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


def get_ceps_count(csv_file='ceps.csv'):
    """Obtém o número de CEPs no arquivo CSV"""
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            ceps_count = len(list(reader))
            print(f"Encontrados {ceps_count} CEPs no arquivo {csv_file}")
            reader = None
            return ceps_count
    except FileNotFoundError:
        print(f"Erro: Arquivo {csv_file} não encontrado", file=sys.stderr)
        return 0



def read_cep_row_n_from_csv(csv_file='ceps.csv', n=0):
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i == n:
                    return row.get('cep')
    except FileNotFoundError:
        print(f"Erro: Arquivo {csv_file} não encontrado", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Erro ao ler arquivo {csv_file}: {e}", file=sys.stderr)
        return None

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


def run_execution(args, cep, execution_dir=None, use_age_filters=True, total_pages=None, max_page=None, age_range_key=None, single_age_range=None):
    """
    Run parallel executions of script.py for a single CEP, splitting pages across num_exec processes
    
    Args:
        args: Command line arguments
        cep: CEP to process
        execution_dir: Directory for logs
        use_age_filters: If False, age filters will not be passed to script.py
        total_pages: Total number of pages to process (if None, will be calculated from args)
        max_page: Maximum page number (if None, will be calculated from args)
        age_range_key: Key for age range (e.g., "18-20") for log directory naming
        single_age_range: Dict with 'min' and 'max' for single age range processing
    """
    # Use provided total_pages and max_page, or calculate from args
    if total_pages is None:
        # Calculate from max_page if provided, otherwise use a default
        if hasattr(args, 'max_page') and args.max_page:
            total_pages = args.max_page - args.initial_page + 1
        else:
            raise ValueError("total_pages must be provided or calculable from max_page")
    if max_page is None:
        max_page = args.initial_page + total_pages - 1
    
    # Debug: print which total_pages we're using
    if age_range_key:
        print(f"  [DEBUG] run_execution chamado com total_pages={total_pages}, max_page={max_page} para faixa {age_range_key}")
    
    # Split pages using the provided total_pages (which should be age-specific if processing separately)
    ranges = split_ranges(total_pages, args.num_exec, args.initial_page)
    if age_range_key:
        print(f"  [DEBUG] Ranges calculados: {ranges} (baseado em total_pages={total_pages})")
    
    # Create subdirectory for this CEP, with age range subdirectory if provided
    cep_dir = execution_dir / f"cep_{cep.replace('-', '_')}"
    if age_range_key:
        # Create age range subdirectory for log separation
        cep_dir = cep_dir / f"age_{age_range_key.replace('-', '_')}"
    cep_dir.mkdir(parents=True, exist_ok=True)

    procs = []
    for idx, (start, end) in enumerate(ranges, start=1):
        # Cap end to max_page to ensure we don't exceed the calculated limit
        actual_end = min(end, max_page)
        log_path = cep_dir / f"job_{idx:03d}_{start}-{actual_end}.log"
        cmd = [
            args.python, "-u", args.script,  # -u for unbuffered output
            f"--max-distance={args.max_distance}",
            f"--cep={cep}",
            f"--initial-page={start}",
            f"--max-page={actual_end}",
            f"--instancia={args.instancia}",
        ]
        # Add age filters if provided AND use_age_filters is True
        if use_age_filters:
            if single_age_range:
                # Process single age range
                if single_age_range['min'] is not None:
                    cmd.append(f"--age-min={single_age_range['min']}")
                if single_age_range['max'] is not None:
                    cmd.append(f"--age-max={single_age_range['max']}")
            elif args.min_max_age_list:
                cmd.append(f"--min-max-age-list={args.min_max_age_list}")
            elif args.age_min is not None or args.age_max is not None:
                # Single age range from args
                if args.age_min is not None:
                    cmd.append(f"--age-min={args.age_min}")
                if args.age_max is not None:
                    cmd.append(f"--age-max={args.age_max}")
        
        log_f = open(log_path, "w", encoding="utf-8", buffering=1)  # Line buffering for real-time logs
        
        env = os.environ.copy()
        
        print(f"[{idx}/{len(ranges)}] CEP {cep} - pages {start}-{end} -> {log_path}")
        procs.append((subprocess.Popen(cmd, stdout=log_f, stderr=subprocess.STDOUT, bufsize=1, env=env), log_f, cmd))

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
    p.add_argument("--total-pages", type=int, default=None, help="Total pages count (optional, will be calculated from total candidates if not provided)")
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
    p.add_argument("--exclude-ceps-list", type=str, default=None, help="CSV file with CEPs to exclude (default: None)")
    args = p.parse_args()

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
        ceps_count = get_ceps_count(args.ceps_file)
        current_cep = read_cep_row_n_from_csv(args.ceps_file, n=0)
        if not current_cep:
            print("Nenhum CEP encontrado. Encerrando.", file=sys.stderr)
            sys.exit(1)
        print(f"Encontrados {ceps_count} CEPs para processar")

    print(f"\n{'='*70}")
    print(f"INICIANDO PROCESSAMENTO")
    print(f"CEPs a processar: {ceps_count}")
    if args.total_pages:
        print(f"Páginas fixas por CEP: {args.total_pages} (de {args.initial_page} a {args.initial_page + args.total_pages - 1})")
    else:
        print(f"Páginas serão calculadas dinamicamente baseadas no total de candidatos (100 candidatos por página)")
    print(f"Execuções paralelas por CEP: {args.num_exec}")
    if args.min_max_age_list:
        age_ranges = json.loads(args.min_max_age_list)
        print(f"Faixas etárias por CEP: {len(age_ranges)}")
    print(f"{'='*70}\n")

    total_start_time = time.time()
    total_ceps_processed = 0
    failed_ceps = []

    # Process each CEP sequentially
    for cep_idx in range(ceps_count):
        # Read current CEP (first one was already read, but we read it again for consistency)
        current_cep = read_cep_row_n_from_csv(args.ceps_file, n=cep_idx)
        if not current_cep:
            continue
        
        # Check exclude list
        if args.exclude_ceps_list:
            if current_cep in json.loads(args.exclude_ceps_list):
                print(f"CEP {current_cep} está na lista de CEPs a excluir. Pulando...")
                continue

        print(f"\n{'='*70}")
        print(f"CEP {cep_idx+1}/{ceps_count}: {current_cep}")
        print(f"{'='*70}")
        
        # Check total candidates and decide whether to use age filters, and calculate total pages
        use_age_filters = True
        total_pages = args.total_pages  # Use provided total_pages if available
        age_range_total_pages = {}  # Map age ranges to their total_pages
        
        try:
            # Import the function from script.py
            spec = importlib.util.spec_from_file_location("script_module", args.script)
            script_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(script_module)
            
            # Get total candidates without age filters first
            total_candidates = script_module.get_total_candidades_from_filters(current_cep, age_min=None, age_max=None)
            
            if total_candidates is not None:
                print(f"Total de candidatos para CEP {current_cep}: {total_candidates:,}")
                
                # Calculate total pages from total candidates (100 candidates per page)
                PAGE_SIZE = 100  # From script.py
                if total_pages is None:
                    total_pages = math.ceil(total_candidates / PAGE_SIZE)
                    print(f"Total de páginas calculado: {total_pages} (baseado em {total_candidates:,} candidatos / {PAGE_SIZE} por página)")
                
                # If total_pages > 100 and min-max-age-list is provided, calculate total_pages for each age range
                if total_pages > 100 and args.min_max_age_list:
                    try:
                        age_ranges = json.loads(args.min_max_age_list)
                        print(f"\nTotal de páginas > 100. Calculando total de páginas para cada faixa etária:")
                        
                        for age_range in age_ranges:
                            age_min = age_range['min']
                            age_max = age_range['max']
                            
                            # Get total candidates for this specific age range
                            age_total_candidates = script_module.get_total_candidades_from_filters(
                                current_cep, age_min=age_min, age_max=age_max
                            )
                            
                            if age_total_candidates is not None:
                                age_total_pages = math.ceil(age_total_candidates / PAGE_SIZE)
                                age_range_total_pages[f"{age_min}-{age_max}"] = age_total_pages
                                print(f"  Faixa {age_min}-{age_max}: {age_total_candidates:,} candidatos = {age_total_pages} páginas")
                            else:
                                # Fallback to overall total_pages if can't get specific count
                                age_range_total_pages[f"{age_min}-{age_max}"] = total_pages
                                print(f"  Faixa {age_min}-{age_max}: não foi possível obter total, usando {total_pages} páginas")
                    except Exception as e:
                        print(f"Erro ao calcular total de páginas por faixa etária: {e}", file=sys.stderr)
                        age_range_total_pages = {}
                
                # Decide whether to use age filters
                if total_candidates < 10000:
                    print(f"Total < 10.000 candidatos. Processando sem filtros de idade.")
                    use_age_filters = False
                else:
                    print(f"Total >= 10.000 candidatos. Processando com filtros de idade.")
            else:
                print(f"Não foi possível obter o total de candidatos.")
                if total_pages is None:
                    print(f"Erro: --total-pages é obrigatório quando não é possível obter o total de candidatos.", file=sys.stderr)
                    failed_ceps.append(current_cep)
                    continue
                print(f"Usando total-pages fornecido: {total_pages}")
        except Exception as e:
            print(f"Erro ao verificar total de candidatos: {e}", file=sys.stderr)
            if total_pages is None:
                print(f"Erro: --total-pages é obrigatório quando há erro ao obter total de candidatos.", file=sys.stderr)
                failed_ceps.append(current_cep)
                continue
            print(f"Usando total-pages fornecido: {total_pages}")
        
        # If total_pages > 10,000 and age_range_total_pages exists, process each age range separately
        should_process_separately = (
            total_pages > 100 and 
            age_range_total_pages and 
            len(age_range_total_pages) > 0 and 
            args.min_max_age_list
        )

        if should_process_separately:
            try:
                age_ranges = json.loads(args.min_max_age_list)
                print(f"\n{'='*70}")
                print(f"Total de páginas ({total_pages}) > 100 e min-max-age-list fornecido.")
                print(f"Processando cada faixa etária separadamente com seus próprios total de páginas:")
                print(f"{'='*70}")
                
                all_success = True
                for age_range in age_ranges:
                    age_min = age_range['min']
                    age_max = age_range['max']
                    age_key = f"{age_min}-{age_max}"
                    
                    # Get total_pages for this specific age range
                    if age_key in age_range_total_pages:
                        age_total_pages = age_range_total_pages[age_key]
                        age_max_page = args.initial_page + age_total_pages - 1
                        print(f"\n{'='*70}")
                        print(f"Processando faixa {age_min}-{age_max}")
                        print(f"  Total de páginas para esta faixa: {age_total_pages}")
                        print(f"  Max page calculado: {age_max_page} (initial: {args.initial_page})")
                        print(f"{'='*70}")
                        
                        # Create separate execution for this age range
                        success = run_execution(
                            args, current_cep, execution_dir=execution_dir,
                            use_age_filters=True,
                            total_pages=age_total_pages,  # Use age-specific total_pages
                            max_page=age_max_page,  # Use age-specific max_page
                            age_range_key=age_key,
                            single_age_range={'min': age_min, 'max': age_max}
                        )
                        if not success:
                            all_success = False
                    else:
                        print(f"  Aviso: Total de páginas não encontrado para faixa {age_key}, pulando...")
                        all_success = False
                
                success = all_success
            except Exception as e:
                print(f"Erro ao processar faixas etárias separadamente: {e}", file=sys.stderr)
                # Fallback to normal execution
                max_page = args.initial_page + total_pages - 1
                success = run_execution(
                    args, current_cep, execution_dir=execution_dir,
                    use_age_filters=use_age_filters,
                    total_pages=total_pages,
                    max_page=max_page
                )
        else:
            # Normal execution: use overall total_pages
            max_page = args.initial_page + total_pages - 1
            success = run_execution(
                args, current_cep, execution_dir=execution_dir,
                use_age_filters=use_age_filters,
                total_pages=total_pages,
                max_page=max_page
            )
        if success:
            total_ceps_processed += 1
            print(f"\n✓ CEP {current_cep} completamente processado ({args.num_exec} execuções paralelas)")
        else:
            failed_ceps.append(current_cep)
            print(f"\n✗ CEP {current_cep} falhou")
        
        print(f"{'='*70}\n")

    total_end_time = time.time()
    total_execution_time = total_end_time - total_start_time

    print(f"\n{'='*70}")
    print(f"PROCESSAMENTO COMPLETO")
    print(f"CEPs processados com sucesso: {total_ceps_processed}/{ceps_count}")
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

