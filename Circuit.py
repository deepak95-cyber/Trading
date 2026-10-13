#!/usr/bin/env python3
"""Poll NSE symbols and live exchange-mandated circuit limits by automatically downloading 
today's official price band list from NSE archives, maintain JSON snapshots, and ensure single execution per day."""

import argparse
import csv
import glob
import json
import os
import shutil
import sys
import warnings
from datetime import datetime

# Suppress warnings
warnings.simplefilter(action="ignore", category=FutureWarning)

import requests
import yfinance as yf


def download_latest_nse_band_file():
    """Dynamically construct today's date URL, download the official NSE CSV file, and save it locally."""
    today_str = datetime.now().strftime("%d%m%Y")
    filename = f"sec_list_{today_str}.csv"
    
    # If today's file is already downloaded, use it directly
    if os.path.exists(filename):
        return filename

    # Construct official NSE archive URL dynamically for today
    url = f"https://nsearchives.nseindia.com/content/equities/sec_list_{today_str}.csv"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.nseindia.com/",
        "Connection": "keep-alive"
    }

    try:
        session = requests.Session()
        # Hit homepage first to acquire valid session cookies for Cloudflare/Akamai bypass
        session.get("https://www.nseindia.com", headers=headers, timeout=10)
        
        resp = session.get(url, headers=headers, timeout=10)
        if resp.status_code == 200 and "Symbol" in resp.text:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(resp.text)
            print(f"Successfully downloaded fresh NSE band file: {filename}")
            return filename
    except Exception as e:
        print(f"Automated download notice: {e}")
        
    return None


def load_bands_from_downloaded_csvs():
    """Automatically download today's file or scan directory for any available NSE master lists and extract bands."""
    bands_map = {}
    
    # Try downloading today's official file automatically
    download_latest_nse_band_file()
    
    # Scan all local CSV files in the folder (handles today's file or any manual backups)
    csv_files = glob.glob('*.csv')
    
    for filename in csv_files:
        if filename.lower() == 'surveillance_bands.csv':
            continue
            
        try:
            with open(filename, mode='r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                headers = [h.strip().upper() for h in reader.fieldnames or []]
                
                # Case 1: Master List (e.g., sec_list_*.csv with 'SYMBOL' and 'BAND')
                if 'SYMBOL' in headers and 'BAND' in headers:
                    for row in reader:
                        sym = row.get('Symbol', row.get('SYMBOL', '')).strip().upper()
                        band_val = row.get('Band', row.get('BAND', '')).strip()
                        if sym and band_val:
                            try:
                                clean_band = float(''.join(c for c in band_val if c.isdigit() or c == '.'))
                                bands_map[sym] = clean_band
                            except ValueError:
                                continue
                
                # Case 2: Band Changes Report (e.g., eq_band_changes_*.csv with 'SYMBOL' and 'TO')
                elif 'SYMBOL' in headers and 'TO' in headers:
                    for row in reader:
                        sym = row.get('Symbol', row.get('SYMBOL', '')).strip().upper()
                        band_val = row.get('To', row.get('TO', '')).strip()
                        if sym and band_val:
                            try:
                                clean_band = float(''.join(c for c in band_val if c.isdigit() or c == '.'))
                                bands_map[sym] = clean_band
                            except ValueError:
                                continue
        except Exception:
            pass
            
    return bands_map


def fetch_quote_and_bands(symbol):
    """Fetch live quote and compute exact circuit bounds using official exchange bands."""
    last_price = 0.0
    prev_close = 0.0

    # Load official exchange bands from local or dynamically downloaded CSVs
    nse_bands = load_bands_from_downloaded_csvs()
    symbol_upper = symbol.strip().upper()
    
    # Default to 20.0% if not found in the CSV report
    band_pct = nse_bands.get(symbol_upper, 20.0)

    try:
        yf_sym = f"{symbol}.NS"
        df = yf.download(yf_sym, period="5d", progress=False)
        if df is not None and not df.empty:
            if hasattr(df.columns, "levels"):
                df.columns = df.columns.get_level_values(0)

            if "Close" in df.columns:
                closes = df["Close"].dropna()
                if len(closes) >= 1:
                    last_price = float(closes.iloc[-1])
                    prev_close = float(closes.iloc[-2]) if len(closes) >= 2 else last_price
    except Exception:
        pass

    if prev_close == 0.0:
        prev_close = last_price if last_price > 0.0 else 1.0
    if last_price == 0.0:
        last_price = prev_close

    # Calculate exact circuit limits using the official exchange band percentage
    upper_circuit = round(prev_close * (1 + band_pct / 100.0), 2)
    lower_circuit = round(prev_close * (1 - band_pct / 100.0), 2)

    return {
        "band_pct": float(band_pct),
        "upper_circuit": upper_circuit,
        "lower_circuit": lower_circuit,
        "last_price": round(last_price, 2),
        "prev_close": round(prev_close, 2),
    }


def fetch_quotes_bulk(symbols):
    """Fetch latest quotes and dynamic circuit limits for all given symbols."""
    quotes = {}
    print("Fetching exchange quotes and mapping official bands...")
    
    for symbol in symbols:
        symbol = symbol.strip().upper()
        quote_data = fetch_quote_and_bands(symbol)
        if quote_data:
            quotes[symbol] = quote_data
            
    return quotes


def load_snapshot(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        except Exception:
            return {}
    return {}


def dump_snapshot(path, quotes):
    """Write snapshot JSON file."""
    timestamp = datetime.now().isoformat(timespec="seconds")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"generated_at": timestamp, "symbols": quotes}, f, indent=2)


def check_already_run_today(current_path):
    """Check if the current snapshot file was already generated today."""
    if not os.path.exists(current_path):
        return False
    
    data = load_snapshot(current_path)
    generated_at = data.get("generated_at")
    if not generated_at:
        return False

    try:
        file_date = datetime.fromisoformat(generated_at).date()
        today_date = datetime.now().date()
        return file_date == today_date
    except Exception:
        return False


def empty_output_files(current_path, new_path):
    """Clear the content of output files without deleting them."""
    for path in [current_path, new_path]:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"generated_at": "", "symbols": {}}, f, indent=2)
        print(f"Emptied content of file: {path}")


def run_once(symbols, current_path, new_path, force=False):
    if not force and check_already_run_today(current_path):
        print(f"Skipping: Snapshot '{current_path}' was already generated today. Use --force to override.")
        if os.path.exists(current_path) and not os.path.exists(new_path):
            shutil.copy(current_path, new_path)
        return

    timestamp = datetime.now().isoformat(timespec="seconds")
    print(f"[{timestamp}] Processing {len(symbols)} symbol(s)...")

    new_quotes = fetch_quotes_bulk(symbols)
    dump_snapshot(new_path, new_quotes)
    print(f"New snapshot successfully saved to: {new_path}")

    old_symbols_data = load_snapshot(current_path).get("symbols", {})

    for symbol, quote in new_quotes.items():
        new_band = quote["band_pct"]
        old_quote = old_symbols_data.get(symbol, {})
        old_band = old_quote.get("band_pct")

        changed = old_band is not None and old_band != new_band

        if changed:
            print(
                f"[{timestamp}] ALERT {symbol}: circuit band changed "
                f"{old_band}% -> {new_band}%"
            )
        else:
            print(
                f"[{timestamp}] {symbol}: band={new_band}% "
                f"LTP={quote['last_price']} "
                f"CP={quote['lower_circuit']}/{quote['upper_circuit']}"
            )

    shutil.copy(new_path, current_path)
    print(f"Current snapshot updated to: {current_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "symbols", nargs="?", default=None,
        help="Comma-separated NSE symbols, e.g. RELIANCE,TCS,HFCL. Omit when using --empty.",
    )
    parser.add_argument(
        "--empty", action="store_true",
        help="Clear content of output JSON files without deleting them.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Bypass the once-per-day check and force execution.",
    )
    parser.add_argument(
        "--current", default="nse_circuit_snapshot_current.json",
        help="Path for current snapshot JSON file.",
    )
    parser.add_argument(
        "--new", default="nse_circuit_snapshot_new.json",
        help="Path for new snapshot JSON file.",
    )
    args = parser.parse_args()

    if args.empty:
        empty_output_files(args.current, args.new)
        sys.exit(0)

    if not args.symbols:
        print("Provide a symbol list or use --empty.", file=sys.stderr)
        sys.exit(1)

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    run_once(symbols, args.current, args.new, force=args.force)
    print("Done. Exiting.")


if __name__ == "__main__":
    main()