#!/usr/bin/env python3

import os
import sys
import json
import time
import requests
from typing import Dict, List, Any, Optional

# For Windows consoles that default to CP1252, force UTF-8 for stdout/stderr
import io
try:
    os.environ.setdefault("PYTHONUTF8", "1")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Supabase Configuration
SUPABASE_URL = 'https://dtktqviwceofwtuxlojs.supabase.co'
SUPABASE_SERVICE_ROLE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR0a3Rxdml3Y2VvZnd0dXhsb2pzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjA2MjA4NTEsImV4cCI6MjA3NjE5Njg1MX0.pEQVTEz3tXSDzcsfAbN9KXvwh6K8crLvwy2P436v7L4'

# Webhook URL
WEBHOOK_URL = 'https://n8n.tntfit.fun/webhook/62456e45-d8c8-48c3-94be-226c1dda1f84'

# Batch size for processing (default: 300, max: 5000)
BATCH_SIZE = 100

# Starting offset for pagination (0 = start from beginning)
START_OFFSET = 0

# Constants
BATCH_SIZE_MAX = 5000

# ============================================================================
# FUNCTIONS
# ============================================================================

def post_with_retry(payload: Dict[str, Any], attempts: int = 3, backoff_ms: int = 1000) -> None:
    """
    Post payload to webhook with exponential backoff retry logic.
    
    Args:
        payload: Data to send to webhook
        attempts: Number of retry attempts
        backoff_ms: Initial backoff delay in milliseconds
    """
    last_err = None
    
    for i in range(attempts):
        try:
            response = requests.post(
                WEBHOOK_URL,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            response.raise_for_status()
            print(f"Webhook posted successfully (attempt {i + 1})")
            return
        except Exception as e:
            last_err = e
            print(f"Webhook attempt {i + 1} failed: {e}", file=sys.stderr)
            if i < attempts - 1:  # Don't sleep on last attempt
                time.sleep(backoff_ms * (i + 1) / 1000.0)  # Convert ms to seconds
    
    raise Exception(f"All webhook attempts failed. Last error: {last_err}")


def process_batch(batch_size: int, offset: int = 0) -> Optional[int]:
    """
    Process a single batch of records from Supabase using OFFSET pagination.
    
    Args:
        batch_size: Number of records to fetch per batch
        offset: Number of records to skip (for pagination)
        
    Returns:
        Next offset if more records exist, None otherwise
    """
    # Ensure batch_size is within limits
    batch_size = min(max(batch_size, 1), BATCH_SIZE_MAX)
    
    # Build REST API URL with OFFSET pagination
    rest_url = f"{SUPABASE_URL}/rest/v1/base_catho_tnt_backup"
    params = {
        'select': '*',
        'limit': batch_size,
        'offset': offset,
        'name': "not.eq.",
        'phone': 'not.eq.'
    }
    
    headers = {
        'apikey': SUPABASE_SERVICE_ROLE_KEY,
        'Authorization': f'Bearer {SUPABASE_SERVICE_ROLE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    }
    
    try:
        response = requests.get(rest_url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"REST fetch failed: {e}", file=sys.stderr)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_text = e.response.text
                print(f"Response: {error_text}", file=sys.stderr)
            except:
                pass
        return None
    
    try:
        rows: List[Dict[str, Any]] = response.json()
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON response: {e}", file=sys.stderr)
        return None
    
    if not isinstance(rows, list) or len(rows) == 0:
        print("All done. No more rows.")
        return None
    
    print(f"Fetched {len(rows)} rows (offset: {offset}, batch_size: {batch_size})")
    
    # Deliver to webhook
    payload = {
        'rows': rows,
        'offset': offset,
        'batch_size': batch_size
    }
    
    try:
        post_with_retry(payload)
    except Exception as e:
        print(f"Failed to post to webhook: {e}", file=sys.stderr)
        return None
    
    # Calculate next offset
    next_offset = offset + len(rows)
    print(f"Scheduling next batch (next_offset: {next_offset}, batch_size: {batch_size})")
    
    # If we got fewer rows than requested, we've reached the end
    if len(rows) < batch_size:
        return None
    
    return next_offset


def process_all_batches() -> None:
    """
    Process all batches until no more rows are available.
    Uses configuration from constants defined at the top of the file.
    """
    # Validate and clamp batch size
    batch_size = min(max(BATCH_SIZE, 1), BATCH_SIZE_MAX)
    offset = START_OFFSET
    batch_count = 0
    
    print("=" * 60)
    print("Starting batch processing")
    print(f"Batch size: {batch_size}")
    print(f"Starting offset: {offset}")
    print(f"Webhook URL: {WEBHOOK_URL}")
    print(f"Supabase URL: {SUPABASE_URL}")
    print("=" * 60)
    
    while True:
        batch_count += 1
        print(f"\n--- Processing batch {batch_count} ---")
        
        next_offset = process_batch(batch_size, offset)
        
        if next_offset is None:
            print(f"\nProcessing complete. Processed {batch_count} batch(es).")
            break
        
        offset = next_offset
        
        # Small delay to avoid overwhelming the API
        time.sleep(0.1)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    # Validate configuration
    if BATCH_SIZE < 1 or BATCH_SIZE > BATCH_SIZE_MAX:
        print(f"Error: BATCH_SIZE must be between 1 and {BATCH_SIZE_MAX}", file=sys.stderr)
        sys.exit(1)
    
    try:
        process_all_batches()
    except KeyboardInterrupt:
        print("\n\nProcessing interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nFatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

