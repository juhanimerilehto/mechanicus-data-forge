#!/usr/bin/env python3
"""
rating-automation.py

Reads an Excel sheet produced by rating.py and auto-scores each checkpoint
output using xAI Grok as an automated evaluator.

Checkpoint columns are discovered automatically from the sheet — any column
that is not 'Prompt' and does not start with 'rating_' is treated as a
checkpoint output column, with a corresponding 'rating_<name>' column.

Usage:
  python rating-automation.py --in ratings.xlsx --out ratings_scored.xlsx

Optional:
  --overwrite-existing        re-score rows that already have a score
  --max-rows 100              only process first N rows
  --sleep 0.2                 delay between API calls (default: 0.2s)

Requires XAI_API_KEY in .env or environment.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from typing import Any, Dict, List, Tuple

import pandas as pd
import requests
from dotenv import load_dotenv

XAI_BASE_URL = "https://api.x.ai"
XAI_CHAT_COMPLETIONS_ENDPOINT = f"{XAI_BASE_URL}/v1/chat/completions"
MODEL = "grok-4-1-fast-reasoning"

VALIDATION_SYSTEM_INSTRUCTION = """You are a strict validator for model outputs.

Task:
Given (1) an input prompt and (2) a candidate model output, judge how well the output matches the prompt-call intent.

You MUST evaluate along these axes:
1) Prompt adherence (does it actually answer the requested blessing/prayer topic?)
2) Relevance & specificity (mentions the correct object/fault; avoids unrelated content)
3) Format & style (reads like a blessing/prayer; avoids meta commentary, roleplay labels, or QA scaffolding)
4) Coherence & quality (clear, consistent, not contradictory; no obvious truncation)
5) Safety/appropriateness (no hateful/sexual/graphic content; no disallowed instructions)

Return STRICT JSON ONLY (no markdown, no extra keys) with this schema:
{
  "score": integer 0-100,
  "verdict": "pass" | "borderline" | "fail",
  "reasons": [string, ...],
  "axis_scores": {
    "adherence": integer 0-100,
    "relevance": integer 0-100,
    "style": integer 0-100,
    "coherence": integer 0-100,
    "safety": integer 0-100
  },
  "minimal_fix": string
}

Verdict rule: pass >= 75, borderline 60-74, fail < 60
"""

USER_TEMPLATE = """Prompt:
{prompt}

Candidate output:
{output}
"""


def is_empty(x: Any) -> bool:
    if x is None:
        return True
    if isinstance(x, float) and pd.isna(x):
        return True
    if isinstance(x, str) and x.strip() == "":
        return True
    return False


def discover_checkpoints(df: pd.DataFrame) -> List[Tuple[str, str, str]]:
    """
    Return list of (output_col, score_col, json_col) for each checkpoint found.

    A checkpoint output column is any column that:
    - is not 'Prompt'
    - does not start with 'rating_'
    The corresponding score column is 'rating_<name>'.
    """
    checkpoints = []
    for col in df.columns:
        if col == "Prompt" or col.startswith("rating_"):
            continue
        score_col = f"rating_{col}"
        json_col = f"rating_json_{col}"
        if score_col not in df.columns:
            print(f"  [!] No score column '{score_col}' for output column '{col}' — skipping")
            continue
        checkpoints.append((col, score_col, json_col))
    return checkpoints


def prepare_json_columns(df: pd.DataFrame, checkpoints: List[Tuple[str, str, str]]) -> pd.DataFrame:
    for _, _, json_col in checkpoints:
        if json_col not in df.columns:
            df[json_col] = ""
        df[json_col] = df[json_col].astype("object")
    return df


def call_grok(api_key: str, prompt: str, output: str, timeout_s: int = 60) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": VALIDATION_SYSTEM_INSTRUCTION},
            {"role": "user", "content": USER_TEMPLATE.format(prompt=prompt, output=output)},
        ],
        "temperature": 0.0,
    }
    resp = requests.post(XAI_CHAT_COMPLETIONS_ENDPOINT, headers=headers, json=payload, timeout=timeout_s)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        if start == -1 or end <= start:
            raise ValueError(f"Model did not return JSON. Raw: {content[:500]}")
        return json.loads(content[start:end + 1])


def main() -> None:
    ap = argparse.ArgumentParser(description="Auto-score rating spreadsheet via Grok")
    ap.add_argument("--in", dest="in_path", required=True, help="Input .xlsx (produced by rating.py)")
    ap.add_argument("--out", dest="out_path", required=True, help="Output .xlsx with scores written in")
    ap.add_argument("--sleep", type=float, default=0.2, help="Seconds between API calls (default: 0.2)")
    ap.add_argument("--max-rows", type=int, default=0, help="If >0, only process first N rows")
    ap.add_argument("--overwrite-existing", action="store_true", help="Re-score even if score already exists")
    args = ap.parse_args()

    load_dotenv()
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        raise SystemExit("[!] Missing XAI_API_KEY. Add it to .env or export it in your shell.")

    df = pd.read_excel(args.in_path)

    if "Prompt" not in df.columns:
        raise SystemExit(f"[!] No 'Prompt' column found. Columns: {list(df.columns)}")

    checkpoints = discover_checkpoints(df)
    if not checkpoints:
        raise SystemExit("[!] No checkpoint output columns found in the sheet.")

    print(f"[+] Discovered {len(checkpoints)} checkpoint(s):")
    for out_col, score_col, json_col in checkpoints:
        print(f"    {out_col} -> {score_col}")

    df = prepare_json_columns(df, checkpoints)

    n = len(df) if args.max_rows <= 0 else min(len(df), args.max_rows)

    for i in range(n):
        prompt = df.at[i, "Prompt"]
        prompt = "" if is_empty(prompt) else str(prompt)

        for out_col, score_col, json_col in checkpoints:
            output_val = df.at[i, out_col]
            if is_empty(output_val):
                continue

            existing_score = df.at[i, score_col]
            existing_json = df.at[i, json_col]
            if not args.overwrite_existing:
                if not is_empty(existing_score) or not is_empty(existing_json):
                    continue

            try:
                result = call_grok(api_key, prompt, str(output_val))
                df.at[i, score_col] = result.get("score", None)
                df.at[i, json_col] = json.dumps(result, ensure_ascii=False)
            except Exception as e:
                df.at[i, score_col] = None
                df.at[i, json_col] = json.dumps({
                    "score": None, "verdict": "error",
                    "reasons": [str(e)[:300]],
                    "axis_scores": {}, "minimal_fix": "",
                }, ensure_ascii=False)

            time.sleep(args.sleep)

        if (i + 1) % 10 == 0:
            print(f"  [{i + 1}/{n}] rows processed")

    df.to_excel(args.out_path, index=False)
    print(f"[ok] Wrote: {args.out_path}")


if __name__ == "__main__":
    main()
