#!/usr/bin/env python3
"""
rating-automation.py

Reads an Excel sheet that contains:
  Prompt,
  checkpoint1, rating1,
  checkpoint2, rating2,
  checkpoint3, rating3

For each row, sends (Prompt, checkpointX) to xAI Grok (grok-4-1-fast-reasoning)
to evaluate alignment of output to prompt, and writes results back to Excel.

Robustness features:
- Keeps rating1/2/3 as NUMERIC overall scores (easy to sort/filter)
- Stores full JSON in rating_json1/2/3 (text columns)
- Works even if rating columns are empty and inferred as float
- API key read from .env (XAI_API_KEY=...)

Usage:
  pip install pandas openpyxl python-dotenv requests
  python rating-automation.py --in ratings.xlsx --out ratings_scored.xlsx

Optional:
  --overwrite-existing        # re-score even if rating exists
  --max-rows 100              # only first N rows
  --sleep 0.2                 # delay between calls
"""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any, Dict

import pandas as pd
import requests
from dotenv import load_dotenv

# xAI OpenAI-compatible API base
XAI_BASE_URL = "https://api.x.ai"
XAI_CHAT_COMPLETIONS_ENDPOINT = f"{XAI_BASE_URL}/v1/chat/completions"

# Latest 4.1 reasoning model (per xAI naming)
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
  "reasons": [string, ...],          // 1-5 short bullet-like reasons
  "axis_scores": {
    "adherence": integer 0-100,
    "relevance": integer 0-100,
    "style": integer 0-100,
    "coherence": integer 0-100,
    "safety": integer 0-100
  },
  "minimal_fix": string              // one-sentence suggestion to improve the output
}

Verdict rule:
- pass: score >= 75
- borderline: 60-74
- fail: < 60
"""

USER_TEMPLATE = """Prompt:
{prompt}

Candidate output:
{output}
"""


def is_empty_cell(x: Any) -> bool:
    """True if x should be treated as empty/missing."""
    if x is None:
        return True
    if isinstance(x, float) and pd.isna(x):
        return True
    if isinstance(x, str) and x.strip() == "":
        return True
    return False


def call_grok_validate(api_key: str, prompt: str, output: str, timeout_s: int = 60) -> Dict[str, Any]:
    """Call xAI chat completions and parse strict JSON response."""
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
    data = resp.json()

    content = data["choices"][0]["message"]["content"]

    # Expect strict JSON; parse it. If the model wraps text, try extracting the first {...}.
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError(f"Model did not return JSON. Raw content: {content[:500]}")
        return json.loads(content[start : end + 1])


def ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure required input columns exist, and add/prepare output columns:
      rating_json1/2/3 as object dtype (strings)
      rating1/2/3 left as-is (numeric-friendly); we write numeric scores into them.
    """
    required = ["Prompt", "checkpoint1", "rating1", "checkpoint2", "rating2", "checkpoint3", "rating3"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}. Found columns: {list(df.columns)}")

    # Add JSON columns if absent
    for k in (1, 2, 3):
        jcol = f"rating_json{k}"
        if jcol not in df.columns:
            df[jcol] = ""

    # Force JSON columns to object dtype (strings)
    for col in ["rating_json1", "rating_json2", "rating_json3"]:
        df[col] = df[col].astype("object")

    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, help="Input .xlsx (e.g. ratings.xlsx)")
    ap.add_argument("--out", dest="out_path", required=True, help="Output .xlsx (e.g. ratings_scored.xlsx)")
    ap.add_argument("--sleep", type=float, default=0.2, help="Seconds to sleep between API calls")
    ap.add_argument("--max-rows", type=int, default=0, help="If >0, only process first N rows")
    ap.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Re-score even if rating cell is non-empty",
    )
    args = ap.parse_args()

    load_dotenv()
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing XAI_API_KEY. Put it in a .env file or export it in your shell environment.")

    df = pd.read_excel(args.in_path)
    df = ensure_columns(df)

    n = len(df) if args.max_rows <= 0 else min(len(df), args.max_rows)

    for i in range(n):
        prompt_val = df.at[i, "Prompt"]
        prompt = "" if is_empty_cell(prompt_val) else str(prompt_val)

        for k in (1, 2, 3):
            out_col = f"checkpoint{k}"
            score_col = f"rating{k}"         # numeric score
            json_col = f"rating_json{k}"     # full JSON text

            output_val = df.at[i, out_col]
            if is_empty_cell(output_val):
                continue

            existing_score = df.at[i, score_col]
            existing_json = df.at[i, json_col]

            # Skip if we already have something unless overwrite requested.
            if not args.overwrite_existing:
                # If either numeric score exists or JSON exists, treat as already scored
                if (not is_empty_cell(existing_score)) or (not is_empty_cell(existing_json)):
                    continue

            try:
                result = call_grok_validate(api_key=api_key, prompt=prompt, output=str(output_val))

                # Write numeric score for easy filtering/sorting
                df.at[i, score_col] = result.get("score", None)

                # Write full JSON to text column
                df.at[i, json_col] = json.dumps(result, ensure_ascii=False)

            except Exception as e:
                # Keep sheet consistent even on error
                df.at[i, score_col] = None
                df.at[i, json_col] = json.dumps(
                    {
                        "score": None,
                        "verdict": "error",
                        "reasons": [str(e)[:300]],
                        "axis_scores": {},
                        "minimal_fix": "",
                    },
                    ensure_ascii=False,
                )

            time.sleep(args.sleep)

    df.to_excel(args.out_path, index=False)
    print(f"Done. Wrote: {args.out_path}")


if __name__ == "__main__":
    main()
