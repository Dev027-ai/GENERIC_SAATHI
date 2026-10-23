#!/usr/bin/env python3
"""Import a CSV downloaded from the official PMBI/Jan Aushadhi product list.

This script does not scrape or invent prices. The operator must download the CSV
from the official portal, inspect it, and pass the official page URL and check date.
It writes a normalized evidence file used by integration status reporting.
"""
import argparse, csv, re, sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_PREFIX = "https://janaushadhi.gov.in/"

def norm(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").casefold())

def choose(headers, *candidates):
    by_norm = {norm(h): h for h in headers}
    for c in candidates:
        if norm(c) in by_norm:
            return by_norm[norm(c)]
    return None

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv_file", help="Path to CSV downloaded from the official PMBI product list")
    ap.add_argument("--source-url", required=True, help="Official Janaushadhi.gov.in product-list page URL")
    ap.add_argument("--checked-on", required=True, help="Date checked in YYYY-MM-DD format")
    args = ap.parse_args()
    if not args.source_url.startswith(OFFICIAL_PREFIX):
        sys.exit("Refusing import: --source-url must start with https://janaushadhi.gov.in/")
    try: date.fromisoformat(args.checked_on)
    except ValueError: sys.exit("--checked-on must be YYYY-MM-DD")
    src = Path(args.csv_file)
    if not src.is_file(): sys.exit(f"CSV not found: {src}")
    with src.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        headers = reader.fieldnames or []
    if not rows: sys.exit("CSV has no data rows; no prices imported.")
    name_col = choose(headers, "generic_name", "product name", "medicine name", "name", "product")
    code_col = choose(headers, "drug_code", "master drug code", "product code", "code")
    strength_col = choose(headers, "strength", "composition", "salt and strength")
    pack_col = choose(headers, "pack_size", "pack", "pack size", "unit size", "pack quantity")
    price_col = choose(headers, "mrp", "price", "mrp (inr)", "price inr", "maximum retail price")
    missing = [label for label, col in [("product name",name_col),("strength/composition",strength_col),("pack size",pack_col),("MRP",price_col)] if not col]
    if missing:
        sys.exit("Could not safely identify required columns: " + ", ".join(missing) + ". Headers were: " + ", ".join(headers))
    output = ROOT / "data" / "input" / "jan_aushadhi_official_verified.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    out_rows=[]
    for r in rows:
        name=(r.get(name_col) or "").strip(); strength=(r.get(strength_col) or "").strip()
        pack=(r.get(pack_col) or "").strip(); raw_price=(r.get(price_col) or "").strip().replace(",", "").replace("₹", "")
        try: price=float(raw_price)
        except ValueError: continue
        if not name or not strength or not pack or price <= 0: continue
        out_rows.append({"drug_code":(r.get(code_col) or "").strip() if code_col else "", "generic_name":name, "strength":strength, "pack_size":pack, "mrp_inr":f"{price:.2f}", "source_url":args.source_url, "source_name":"Official PMBI/Jan Aushadhi product list (operator-imported CSV)", "checked_on":args.checked_on, "verification_status":"verified", "reviewer":"operator-import", "reviewer_notes":"Imported from operator-provided official CSV; verify matching to branded records separately."})
    if not out_rows: sys.exit("No rows passed validation; output not written.")
    fields=["drug_code","generic_name","strength","pack_size","mrp_inr","source_url","source_name","checked_on","verification_status","reviewer","reviewer_notes"]
    with output.open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader(); writer.writerows(out_rows)
    print(f"Imported {len(out_rows)} official-source rows to {output}")
    print("Important: this verifies source provenance/date only. It does NOT prove branded medicine equivalence or enable savings unless strength, form and pack match exactly.")

if __name__ == "__main__": main()
