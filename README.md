# Sacred Texts Forge
### *Mechanicus Training Dataset Generator*

> *"Data is the currency of the Omnissiah. Gather it without mercy."*

The pipeline used to generate the **3,972-example dataset** that trained [mechanicus-prayer-gpt2](https://huggingface.co/merileijona/mechanicus-prayer-gpt2). Powered by xAI Grok.

Dataset published at: **[merileijona/mechanicus-prayers-dataset](https://huggingface.co/datasets/merileijona/mechanicus-prayers-dataset)**

---

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Add your XAI_API_KEY to .env
```

Get a Grok API key at [console.x.ai](https://console.x.ai).

---

## Usage

### Generate Dataset

```bash
python generate_dataset.py
```

Reads components and operations from `mechanicus_components.xlsx`, generates prayers for all enabled pairs, tracks progress, and writes batch JSON files to `datasets/mechanicus_dataset_grok/`.

- Skips pairs already at `TARGET_PER_PAIR` — safe to interrupt and resume
- Updates the `Pair Log` sheet in the Excel file after each run
- Deduplicates via hashing

### Merge + Normalize

After generation:

```bash
python merge_data.py    # combine batch JSON files into one
python strip_dataset.py # normalize to clean prompt+prayer format
```

### Rate Output Quality

These tools are for comparing outputs across multiple model checkpoints —
useful when you have run generation on several checkpoints and want to
evaluate which performs best.

```bash
# Step 1 — build side-by-side spreadsheet from a folder of JSONL files
#   (one JSONL per checkpoint; column names come from the filenames)
python rating.py --gen-dir path/to/generations --out ratings.xlsx

# Step 2 — auto-score via Grok (reads the sheet from Step 1)
python rating-automation.py --in ratings.xlsx --out ratings_scored.xlsx
```

`rating.py` scans `--gen-dir` for all `*.jsonl` files and builds an Excel
sheet with alternating output/rating columns — one pair per file found.
No filenames are hardcoded; the script works with any number of checkpoints.

`rating-automation.py` reads that sheet, discovers checkpoint columns
automatically, and calls Grok to score each (prompt, output) pair.
Numeric scores and full JSON diagnostics are written back to `--out`.

**Input JSONL format** (one object per line):
```json
{"user_prompt": "Prayer for activating a plasma reactor.", "completion_only": "Approach the plasma reactor..."}
```

---

## Configuration

`mechanicus_components.xlsx` controls everything:

| Sheet | Purpose |
|-------|---------|
| `Components` | 73 components with enable/disable flags |
| `Operations` | 24 operations with enable/disable flags |
| `Pair Log` | Auto-updated coverage tracker |

Key settings at the top of `generate_dataset.py`:

```python
TARGET_PER_PAIR = 2      # examples per (component, operation) pair
BATCH_SIZE      = 10     # items per API call
TEMPERATURE     = 0.8
MODEL           = "grok-4-1-fast-reasoning"
```

---

## Dataset

`datasets/mechanicus_dataset_grok/` — the final training dataset used to produce the published model.

**Schema:**
```json
{
  "prompt": "Prayer for activating a plasma reactor.",
  "prayer": "Approach the plasma reactor with sanctified oil...",
  "format_type": "natural"
}
```

**Stats:**

| Metric | Value |
|--------|-------|
| Examples | 3,972 |
| Format consistency | 100% |
| Object consistency | 86% |
| Duplicate rate | 0% |
| Prose format | 100% natural prose |

---

## Files

| File | Purpose |
|------|---------|
| `generate_dataset.py` | Main generator — reads Excel, calls Grok, writes batches |
| `merge_data.py` | Combine batch JSON files into one dataset file |
| `strip_dataset.py` | Normalize dataset to clean prompt+prayer format |
| `rating.py` | Build side-by-side Excel sheet from any number of JSONL files (`--gen-dir`, `--out`) |
| `rating-automation.py` | Auto-score discovered checkpoint columns via Grok (`--in`, `--out`) |
| `mechanicus_components.xlsx` | Master component/operation config |
| `datasets/mechanicus_dataset_grok/` | Final training dataset |
| `.env.example` | API key template |

---

## Tech Stack

- [xAI Grok](https://docs.x.ai/) via OpenAI-compatible API (`grok-4-1-fast-reasoning`)
- [openpyxl](https://openpyxl.readthedocs.io/) — Excel component list
- [pandas](https://pandas.pydata.org/)
- [python-dotenv](https://pypi.org/project/python-dotenv/)

---

## License

**Code:** [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)

**Warhammer 40,000 IP:** All Warhammer 40,000 content is © Games Workshop Limited. Unofficial non-commercial fan project.

---

*"Knowledge is power. Guard it well."*
