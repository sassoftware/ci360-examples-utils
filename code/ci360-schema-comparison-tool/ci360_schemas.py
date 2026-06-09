#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "PyJWT",
#   "requests",
# ]
# ///
"""
SAS CI 360 — Download schemas and compare detail versions.

Steps:
  1. Download schemas for all datamarts (detail, dbtReport, identity, snapshot)
     and versions 1-20 from the CI 360 Discover API.
  2. Compare all detail schema versions and write a change-log CSV.
  3. Export raw JSON schemas to CSV under schemas/csv_schemas/.

Usage:
  python ci360_schemas.py                  # download + compare
  python ci360_schemas.py --download-only  # skip compare
  python ci360_schemas.py --compare-only   # skip download (use existing files)
  python ci360_schemas.py --csv-only       # export JSON schemas to CSV

Requires dsccnfg/config.txt with:
  agentName = <your agent name>
  tenantId  = <your tenant id>
  secret    = <your secret>
  baseUrl   = https://extapigwservice-<server>/marketingGateway/discoverService/dataDownload/eventData/
"""

import argparse
import base64
import csv
import json
import os
import re
import time
from datetime import datetime, timezone

import jwt
import requests

# ── Constants ─────────────────────────────────────────────────────────────────

BASE_DIR     = os.path.dirname(__file__)
CONFIG_FILE  = os.path.join(BASE_DIR, "dsccnfg", "config.txt")
SCHEMAS_DIR  = os.path.join(BASE_DIR, "schemas", "raw")
CSV_DIR      = os.path.join(BASE_DIR, "schemas", "csv_schemas")
COMPARE_DIR  = os.path.join(BASE_DIR, "output")

DATAMARTS       = ["detail", "dbtReport", "cdm"]
SCHEMA_VERSIONS = range(1, 31)
RANGE_START     = "2015-01-01T00:00:00.000"

MART_ENDPOINT = {
    "detail":    "detail/partitionedData",
    "dbtReport": "dbtReport",
    "cdm":       "detail/nonPartitionedData",
}

MART_PARAMS: dict[str, dict] = {
    "cdm": {"category": "cdm"},
}

TRACKED_FIELDS = [
    "Column_label", "column_sequence", "data_type",
    "data_length", "column_type", "categories",
]

# ── Download helpers ─────────────────────────────────────────────────────────

def read_config(path: str) -> dict:
    cfg = {}
    with open(path) as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            cfg[key.strip()] = val.strip()
    return cfg


def make_token(cfg: dict) -> str:
    encoded_secret = base64.b64encode(cfg["secret"].encode())
    token = jwt.encode({"clientID": cfg["tenantId"]}, encoded_secret, algorithm="HS256")
    return token if isinstance(token, str) else token.decode()


def api_headers(token: str) -> dict:
    return {"authorization": f"Bearer {token}", "cache-control": "no-cache"}


def range_end_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000")


def discover_schema_urls(cfg: dict, token: str, mart: str, schema_ver: int) -> list[str]:
    base = cfg["baseUrl"].rstrip("/") + "/"
    url  = base + MART_ENDPOINT[mart]
    params = {
        "agentName":               cfg["agentName"],
        "schemaVersion":           str(schema_ver),
        "limit":                   "1",
        "dataRangeStartTimeStamp": RANGE_START,
        "dataRangeEndTimeStamp":   range_end_now(),
        **MART_PARAMS.get(mart, {}),
    }
    resp = requests.get(url, headers=api_headers(token), params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return list({item["schemaUrl"] for item in data.get("items", []) if item.get("schemaUrl")})


def fetch_schema(schema_url: str) -> list:
    resp = requests.get(schema_url, timeout=60)
    resp.raise_for_status()
    return resp.json()


# ── Compare helpers ───────────────────────────────────────────────────────────

def load_schemas(schema_type: str) -> dict[int, dict]:
    directory = os.path.join(SCHEMAS_DIR, schema_type)
    pattern = re.compile(rf"{re.escape(schema_type)}_schema_v(\d+)\.json$", re.IGNORECASE)
    schemas: dict[int, dict] = {}
    if not os.path.isdir(directory):
        return schemas
    for fname in os.listdir(directory):
        m = pattern.match(fname)
        if not m:
            continue
        ver = int(m.group(1))
        with open(os.path.join(directory, fname), encoding="utf-8") as fh:
            rows = json.load(fh)
        schemas[ver] = {(r["table_name"], r["column_name"]): r for r in rows}
    return schemas


def collect_categories(schemas: dict[int, dict]) -> list[str]:
    cats: set[str] = set()
    for snap in schemas.values():
        for row in snap.values():
            for c in (row.get("categories") or []):
                cats.add(c)
    return sorted(cats)


def expand_categories(event: dict, all_categories: list[str]) -> dict:
    cats_set = set(event.pop("categories") or [])
    for cat in all_categories:
        event[f"cat_{cat}"] = "1" if cat in cats_set else ""
    return event


def normalise(row: dict | None) -> dict:
    if row is None:
        return {f: None for f in TRACKED_FIELDS}
    return {f: row.get(f) for f in TRACKED_FIELDS}


def build_event(table, column, change_type, schema_ver, current_row, prev_row=None) -> dict:
    nr = normalise(current_row)
    if change_type == "modified" and prev_row is not None:
        pr = normalise(prev_row)
        modified_fields    = "; ".join(f for f in TRACKED_FIELDS if pr[f] != nr[f])
        modification_detail = "; ".join(
            f"{f}: {pr[f]!r} → {nr[f]!r}" for f in TRACKED_FIELDS if pr[f] != nr[f]
        )
    else:
        modified_fields     = ""
        modification_detail = ""
    return {
        "table_name":          table,
        "column_name":         column,
        "change_type":         change_type,
        "schema_version":      f"v{schema_ver}",
        "column_label":        nr["Column_label"],
        "column_sequence":     nr["column_sequence"],
        "data_type":           nr["data_type"],
        "data_length":         nr["data_length"],
        "column_type":         nr["column_type"],
        "primary_key":         current_row.get("primary_key"),
        "foreign_key":         current_row.get("foreign_key"),
        "categories":          nr["categories"],
        "modified_fields":     modified_fields,
        "modification_detail": modification_detail,
    }


# ── Steps ─────────────────────────────────────────────────────────────────────

def step_csv(marts: list[str]) -> None:
    converted = 0
    errors = 0
    for mart in marts:
        mart_dir = os.path.join(SCHEMAS_DIR, mart)
        if not os.path.isdir(mart_dir):
            print(f"[{mart}] no schema directory found — skipping")
            continue
        out_dir = os.path.join(CSV_DIR, mart)
        os.makedirs(out_dir, exist_ok=True)
        for fname in sorted(os.listdir(mart_dir)):
            if not fname.endswith(".json"):
                continue
            json_path = os.path.join(mart_dir, fname)
            csv_path  = os.path.join(out_dir, fname.replace(".json", ".csv"))
            try:
                with open(json_path, encoding="utf-8") as fh:
                    data = json.load(fh)
                if not isinstance(data, list) or not data:
                    raise ValueError("expected a non-empty JSON array")
                fieldnames = list(data[0].keys())
                with open(csv_path, "w", newline="", encoding="utf-8") as fh:
                    writer = csv.DictWriter(fh, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(data)
                print(f"  {os.path.relpath(json_path, BASE_DIR)}  ->  {os.path.relpath(csv_path, BASE_DIR)}")
                converted += 1
            except Exception as exc:
                print(f"  SKIP  {fname}: {exc}")
                errors += 1
    print(f"\nCSV export complete — converted: {converted}, skipped: {errors}")


def step_download(marts: list[str]) -> None:
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(
            f"Config not found: {CONFIG_FILE}\n"
            "Create dsccnfg/config.txt with agentName, tenantId, secret, baseUrl."
        )

    cfg   = read_config(CONFIG_FILE)
    token = make_token(cfg)
    print(f"Authenticated as agent '{cfg['agentName']}' on tenant '{cfg['tenantId']}'")

    results = {"downloaded": 0, "skipped": 0, "errors": 0}

    for mart in marts:
        mart_dir = os.path.join(SCHEMAS_DIR, mart)
        os.makedirs(mart_dir, exist_ok=True)

        for ver in SCHEMA_VERSIONS:
            tag = f"{mart}/v{ver}"
            try:
                schema_urls = discover_schema_urls(cfg, token, mart, ver)
                if not schema_urls:
                    print(f"  [{tag}] no schema URL — skipping")
                    results["skipped"] += 1
                    continue
                for idx, surl in enumerate(schema_urls):
                    schema_data = fetch_schema(surl)
                    suffix   = "" if len(schema_urls) == 1 else f"_{idx}"
                    out_path = os.path.join(mart_dir, f"{mart}_schema_v{ver}{suffix}.json")
                    with open(out_path, "w", encoding="utf-8") as fh:
                        json.dump(schema_data, fh, indent=2)
                    print(f"  [{tag}] saved → {out_path}  ({len(schema_data)} entries)")
                    results["downloaded"] += 1
            except requests.HTTPError as exc:
                print(f"  [{tag}] HTTP {exc.response.status_code}: {exc}")
                results["errors"] += 1
            except Exception as exc:
                print(f"  [{tag}] error: {exc}")
                results["errors"] += 1

            time.sleep(0.2)

    print(
        f"\nDownload complete — downloaded: {results['downloaded']}, "
        f"skipped: {results['skipped']}, errors: {results['errors']}"
    )


def step_compare(marts: list[str]) -> None:
    for schema_type in marts:
        schemas = load_schemas(schema_type)
        if not schemas:
            print(f"[{schema_type}] no schema files found — skipping")
            continue

        all_categories = collect_categories(schemas)
        versions = sorted(schemas.keys())
        print(f"\n[{schema_type}] versions: {versions}")
        print(f"[{schema_type}] categories: {all_categories}")

        events: list[dict] = []
        all_keys: set[tuple] = set()
        for snap in schemas.values():
            all_keys.update(snap.keys())

        for table, column in sorted(all_keys):
            prev_row: dict | None = None
            for ver in versions:
                curr_row = schemas[ver].get((table, column))
                if prev_row is None and curr_row is not None:
                    events.append(build_event(table, column, "added", ver, curr_row))
                elif prev_row is not None and curr_row is None:
                    events.append(build_event(table, column, "removed", ver, prev_row))
                elif prev_row is not None and curr_row is not None:
                    if any(prev_row.get(f) != curr_row.get(f) for f in TRACKED_FIELDS):
                        events.append(build_event(table, column, "modified", ver, curr_row, prev_row))
                prev_row = curr_row

        ever_pk: set[tuple] = set()
        ever_fk: set[tuple] = set()
        for snap in schemas.values():
            for (table, column), row in snap.items():
                if row.get("primary_key"):
                    ever_pk.add((table, column))
                if row.get("foreign_key"):
                    ever_fk.add((table, column))
        for e in events:
            key = (e["table_name"], e["column_name"])
            e["primary_key"] = key in ever_pk
            e["foreign_key"] = key in ever_fk

        cat_columns = [f"cat_{c}" for c in all_categories]
        fieldnames = [
            "table_name", "column_name", "change_type", "schema_version",
            "column_label", "column_sequence", "data_type", "data_length",
            "column_type", "primary_key", "foreign_key", *cat_columns, "modified_fields", "modification_detail",
        ]
        expanded = [expand_categories(e, all_categories) for e in events]
        os.makedirs(COMPARE_DIR, exist_ok=True)
        out_path = os.path.join(COMPARE_DIR, f"{schema_type}_schema_changes.csv")
        with open(out_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(expanded)

        added    = sum(1 for e in expanded if e["change_type"] == "added")
        removed  = sum(1 for e in expanded if e["change_type"] == "removed")
        modified = sum(1 for e in expanded if e["change_type"] == "modified")
        print(f"  Wrote {len(expanded)} rows to {out_path}")
        print(f"  added: {added}  |  removed: {removed}  |  modified: {modified}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="CI 360 schema downloader and comparator")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--download-only", action="store_true", help="Only download schemas")
    group.add_argument("--compare-only",  action="store_true", help="Only compare existing schemas")
    group.add_argument("--csv-only",      action="store_true", help="Only export JSON schemas to CSV")
    parser.add_argument(
        "--marts", nargs="+", choices=DATAMARTS, default=DATAMARTS,
        metavar="MART", help=f"Marts to process (default: all). Choices: {', '.join(DATAMARTS)}"
    )
    args = parser.parse_args()

    if args.compare_only:
        step_compare(args.marts)
    elif args.download_only:
        step_download(args.marts)
    elif args.csv_only:
        step_csv(args.marts)
    else:
        step_download(args.marts)
        print()
        step_csv(args.marts)
        print()
        step_compare(args.marts)


if __name__ == "__main__":
    main()
