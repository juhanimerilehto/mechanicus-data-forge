#!/usr/bin/env python3
import json
from pathlib import Path

import pandas as pd

GEN_DIR = Path("generations3")

FILES = {
    "checkpoint1": GEN_DIR / "checkpoints_checkpoint_best_100.jsonl",
    "checkpoint2": GEN_DIR / "checkpoints2_checkpoint_best_100.jsonl",
    "checkpoint3": GEN_DIR / "checkpoints3_checkpoint_best_100.jsonl",
    "checkpoint4": GEN_DIR / "checkpoints_strong1_checkpoint_best_100.jsonl",
    "checkpoint5": GEN_DIR / "checkpoints_grok_data_checkpoint_best_100.jsonl",
}

OUT_XLSX = Path("ratings3.xlsx")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
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
    """Map user_prompt -> completion_only"""
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


def main():
    maps = {}
    all_prompts = set()

    for label, path in FILES.items():
        rows = read_jsonl(path)
        m = build_map(rows)
        maps[label] = m
        all_prompts.update(m.keys())

    prompts_sorted = sorted(all_prompts)

    df = pd.DataFrame({
        "Prompt": prompts_sorted,
        "checkpoint1": [maps["checkpoint1"].get(p, "") for p in prompts_sorted],
        "rating1": [""] * len(prompts_sorted),
        "checkpoint2": [maps["checkpoint2"].get(p, "") for p in prompts_sorted],
        "rating2": [""] * len(prompts_sorted),
        "checkpoint3": [maps["checkpoint3"].get(p, "") for p in prompts_sorted],
        "rating3": [""] * len(prompts_sorted),
        "checkpoint4": [maps["checkpoint4"].get(p, "") for p in prompts_sorted],
        "rating4": [""] * len(prompts_sorted),
        "checkpoint5": [maps["checkpoint5"].get(p, "") for p in prompts_sorted],
        "rating4": [""] * len(prompts_sorted),
    })

    # Write Excel
    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="ratings")

        # Basic formatting
        ws = writer.sheets["ratings"]
        ws.freeze_panes = "B2"  # freeze header + Prompt column
        ws.column_dimensions["A"].width = 45
        ws.column_dimensions["B"].width = 65
        ws.column_dimensions["C"].width = 10
        ws.column_dimensions["D"].width = 65
        ws.column_dimensions["E"].width = 10
        ws.column_dimensions["F"].width = 65
        ws.column_dimensions["G"].width = 10
        ws.column_dimensions["H"].width = 65
        ws.column_dimensions["I"].width = 10
        ws.column_dimensions["J"].width = 65
        ws.column_dimensions["K"].width = 10

        # Wrap text in response columns
        from openpyxl.styles import Alignment
        wrap = Alignment(wrap_text=True, vertical="top")
        for col in ["A", "B", "D", "F", "H", "J"]:
            for row in range(2, 2 + len(df)):
                ws[f"{col}{row}"].alignment = wrap

    print(f"[ok] wrote: {OUT_XLSX.resolve()}")


if __name__ == "__main__":
    main()
