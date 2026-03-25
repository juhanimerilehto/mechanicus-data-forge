#!/usr/bin/env python3
"""
Strip scaffolded dataset into plain prompt+response training data.

Input:
  mechanicus_prayers_dataset_haiku_strong1/all_prayers.json

Output (created if missing):
  mechanicus_prayers_dataset_haiku_strong2/
    all_prayers_plain.json        # list[{"prompt","prayer","format_type"}]
    all_prayers_plain.jsonl       # one json per line (optional for HF)
    training_data.txt             # <|user|>...<|end|>\n<|assistant|>...<|end|>\n

Goal:
  - Remove training_prompt scaffolding entirely.
  - Use human-ish prompt (prefer user_request) + prayer.
  - Keep format_type for analysis (optional).
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SRC_DIR = Path("mechanicus_prayers_dataset_haiku_strong")
DST_DIR = Path("mechanicus_prayers_dataset_haiku_strong2")
SRC_FILE = SRC_DIR / "all_prayers.json"

# ----------------------------
# Cleaning helpers
# ----------------------------

END_TOKEN = "<|end|>"

def norm_ws(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    # Trim trailing spaces on each line
    s = "\n".join(line.rstrip() for line in s.splitlines())
    return s.strip()

def strip_end_tokens(s: str) -> str:
    return s.replace(END_TOKEN, "").strip()

def extract_plain_prompt(row: Dict[str, Any]) -> Optional[str]:
    """
    Prefer the original natural language user_request.
    Fall back to extracting from training_prompt's ### REQUEST section.
    Fall back to any 'prompt' field if present.
    """
    if isinstance(row.get("user_request"), str) and row["user_request"].strip():
        return norm_ws(row["user_request"])

    if isinstance(row.get("prompt"), str) and row["prompt"].strip():
        return norm_ws(row["prompt"])

    tp = row.get("training_prompt")
    if isinstance(tp, str) and tp.strip():
        tp = tp.replace("\r\n", "\n")
        if "### REQUEST" in tp:
            after = tp.split("### REQUEST", 1)[1].lstrip()
            # Cut at next header if present
            m = re.search(r"\n### [A-Z_ ]+\n", after)
            req = (after[:m.start()] if m else after).strip()
            if req:
                return norm_ws(req)

        # If no REQUEST header, remove any lines starting with ### and keep remaining
        lines = []
        for line in tp.splitlines():
            if line.strip().startswith("###"):
                continue
            if line.strip():
                lines.append(line)
        maybe = "\n".join(lines).strip()
        if maybe:
            return norm_ws(maybe)

    return None

def extract_plain_prayer(row: Dict[str, Any]) -> Optional[str]:
    """
    Prayer should be the assistant output only.
    Remove any lingering scaffold blocks, and <|end|> tokens if present.
    """
    p = row.get("prayer")
    if not isinstance(p, str) or not p.strip():
        return None

    p = strip_end_tokens(p)
    p = p.replace("\r\n", "\n").replace("\r", "\n")

    # If the prayer accidentally contains scaffold headers, cut them out.
    if "### " in p:
        # If it contains a PRAYER header, keep only what follows (if any).
        if "### PRAYER" in p:
            after = p.split("### PRAYER", 1)[1].lstrip()
            if after and not after.startswith(END_TOKEN):
                p = after
            else:
                p = p.split("###", 1)[0]
        else:
            p = p.split("###", 1)[0]

    p = norm_ws(p)
    if len(p) < 20:
        return None
    return p

def should_keep(row: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Conservative filtering:
      - keep if validation.ok == True when present
      - otherwise keep, but you can flip default to False if you want strict
    """
    v = row.get("validation")
    if isinstance(v, dict) and "ok" in v:
        return (bool(v["ok"]), "validation_ok_false" if not v["ok"] else "")
    return (True, "")  # permissive default

# ----------------------------
# Main conversion
# ----------------------------

def main():
    if not SRC_FILE.exists():
        raise SystemExit(f"Missing input file: {SRC_FILE}")

    DST_DIR.mkdir(parents=True, exist_ok=True)

    data = json.loads(SRC_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("Expected all_prayers.json to be a JSON list.")

    out_rows: List[Dict[str, str]] = []
    drop_counts: Dict[str, int] = {}

    for row in data:
        if not isinstance(row, dict):
            drop_counts["not_a_dict"] = drop_counts.get("not_a_dict", 0) + 1
            continue

        keep, reason = should_keep(row)
        if not keep:
            drop_counts[reason or "validation_failed"] = drop_counts.get(reason or "validation_failed", 0) + 1
            continue

        prompt = extract_plain_prompt(row)
        prayer = extract_plain_prayer(row)
        if not prompt:
            drop_counts["missing_prompt"] = drop_counts.get("missing_prompt", 0) + 1
            continue
        if not prayer:
            drop_counts["missing_prayer"] = drop_counts.get("missing_prayer", 0) + 1
            continue

        fmt = row.get("format") or row.get("format_type") or "unknown"
        if not isinstance(fmt, str) or not fmt.strip():
            fmt = "unknown"

        out_rows.append({
            "prompt": prompt,
            "prayer": prayer,
            "format_type": fmt.strip(),
        })

    # Write JSON + JSONL
    (DST_DIR / "all_prayers_plain.json").write_text(
        json.dumps(out_rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    with (DST_DIR / "all_prayers_plain.jsonl").open("w", encoding="utf-8") as f:
        for r in out_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Write training_data.txt in your original simple dialogue format
    training_path = DST_DIR / "training_data.txt"
    with training_path.open("w", encoding="utf-8") as f:
        for r in out_rows:
            # Guarantee no stray end tokens in either side
            p = strip_end_tokens(r["prompt"])
            a = strip_end_tokens(r["prayer"])
            f.write(f"<|user|>{p}<|end|>\n")
            f.write(f"<|assistant|>{a}<|end|>\n\n")

    print("✅ Done.")
    print(f"  Input rows:   {len(data)}")
    print(f"  Output rows:  {len(out_rows)}")
    if drop_counts:
        print("  Dropped:")
        for k, v in sorted(drop_counts.items(), key=lambda x: -x[1]):
            print(f"    {k}: {v}")
    print(f"  Wrote: {DST_DIR / 'all_prayers_plain.json'}")
    print(f"  Wrote: {DST_DIR / 'all_prayers_plain.jsonl'}")
    print(f"  Wrote: {training_path}")

if __name__ == "__main__":
    main()
