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

```bash
python rating.py            # generate Excel rating sheet from model outputs
python rating-automation.py # automated scoring (object consistency, format)
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
| `rating.py` | Generate Excel rating sheet from model outputs |
| `rating-automation.py` | Automated quality scoring |
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
