#!/usr/bin/env python3
"""
rating.py

Scans a directory for JSONL generation files and produces a side-by-side
Excel spreadsheet for manual or automated scoring.

Each JSONL file represents one checkpoint/model run. The script discovers
all *.jsonl files in the directory automatically — no hardcoded filenames.
Column names are derived from the JSONL filenames.

Usage:
  python rating.py --gen-dir path/to/generations --out ratings.xlsx

Input JSONL schema (one object per line):
  {"user_prompt": "...", "completion_only": "..."}

Output Excel columns:
  Prompt | <name1> | rating_<name1> | <name2> | rating_<name2> | ...

where <name> is the stem of each discovered JSONL file.
"""
import argparse
import json
import string
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build rating spreadsheet from JSONL generation files")
    ap.add_argument("--gen-dir", required=True, help="Directory containing *.jsonl generation files")
    ap.add_argument("--out", required=True, help="Output Excel file (e.g. ratings.xlsx)")
    return ap.parse_args()


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"Bad JSON at {path}:{line_no}: {e}") from e
    return rows


def build_map(rows: list[dict]) -> dict[str, str]:
    """Map user_prompt -> completion_only."""
    out = {}
    for item in rows:
        if "user_prompt" not in item:
            raise KeyError(f"Expected key 'user_prompt' missing. Keys: {list(item.keys())}")
        if "completion_only" not in item:
            raise KeyError(f"Expected key 'completion_only' missing. Keys: {list(item.keys())}")
        prompt = (item["user_prompt"] or "").strip()
        completion = (item["completion_only"] or "").strip()
        out[prompt] = completion
    return out


def col_letter(index: int) -> str:
    """Return Excel column letter for zero-based column index (A, B, ..., Z, AA, ...)."""
    result = ""
    index += 1
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        result = string.ascii_uppercase[remainder] + result
    return result


def main():
    args = parse_args()
    gen_dir = Path(args.gen_dir)

    if not gen_dir.is_dir():
        raise SystemExit(f"[!] Directory not found: {gen_dir}")

    jsonl_files = sorted(gen_dir.glob("*.jsonl"))
    if not jsonl_files:
        raise SystemExit(f"[!] No *.jsonl files found in: {gen_dir}")

    print(f"[+] Found {len(jsonl_files)} JSONL file(s) in '{gen_dir}':")
    for f in jsonl_files:
        print(f"    {f.name}")

    # Load all files; column name = filename stem
    maps = {}
    all_prompts: set[str] = set()
    for path in jsonl_files:
        name = path.stem
        rows = read_jsonl(path)
        m = build_map(rows)
        maps[name] = m
        all_prompts.update(m.keys())
        print(f"    [{name}] {len(rows)} rows loaded")

    prompts_sorted = sorted(all_prompts)
    names = list(maps.keys())  # preserves sorted file order

    # Build DataFrame dynamically
    data: dict[str, list] = {"Prompt": prompts_sorted}
    for name in names:
        data[name] = [maps[name].get(p, "") for p in prompts_sorted]
        data[f"rating_{name}"] = [""] * len(prompts_sorted)

    df = pd.DataFrame(data)

    # Write Excel
    out_path = Path(args.out)
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="ratings")

        ws = writer.sheets["ratings"]
        ws.freeze_panes = "B2"

        # Column layout: A=Prompt, then alternating output/rating pairs
        from openpyxl.styles import Alignment
        wrap = Alignment(wrap_text=True, vertical="top")

        ws.column_dimensions["A"].width = 45
        wrap_cols = ["A"]

        for i, name in enumerate(names):
            out_col = col_letter(1 + i * 2)       # B, D, F, ...
            rating_col = col_letter(1 + i * 2 + 1) # C, E, G, ...
            ws.column_dimensions[out_col].width = 65
            ws.column_dimensions[rating_col].width = 12
            wrap_cols.append(out_col)

        for col in wrap_cols:
            for row in range(2, 2 + len(df)):
                ws[f"{col}{row}"].alignment = wrap

    print(f"[ok] Wrote: {out_path.resolve()}")
    print(f"     {len(prompts_sorted)} prompts × {len(names)} checkpoints")


if __name__ == "__main__":
    main()
