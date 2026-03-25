# Sacred Texts Forge
### *Mechanicus Training Dataset Generator*

> *"Data is the currency of the Omnissiah. Gather it without mercy."*

The complete pipeline for generating, curating, and processing Adeptus Mechanicus prayer training data. Supports three API backends: xAI Grok, Google Gemini, and Anthropic Claude Haiku.

---

## What This Is

This repo contains all the tools used to generate the **3,972-example dataset** that trained [mechanicus-prayer-gpt2](https://huggingface.co/merileijona/mechanicus-prayer-gpt2). It is not the training code (see [mechanicus-gpt-trainer](../mechanicus-gpt-trainer)) nor the running model.

Dataset published at: **[merileijona/mechanicus-prayers-dataset](https://huggingface.co/datasets/merileijona/mechanicus-prayers-dataset)**

---

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Fill in your API keys in .env
```

### API Keys Required

| Generator | API Key Variable | Source |
|-----------|-----------------|--------|
| `dataset_gen_grok.py` / `generate_grok_data_large.py` | `XAI_API_KEY` | [console.x.ai](https://console.x.ai) |
| `generator.py` / `generator_smaler_batches.py` | `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) |
| `prayer_generator_haiku*.py` | `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) |

---

## Usage

### Generate Dataset (Grok — Recommended)

The Grok pipeline produced the final training dataset. Best quality/cost ratio.

```bash
# Large-scale generation from Excel component list
python generate_grok_data_large.py

# Focused single-component generation
python dataset_gen_grok.py

# Generate 100 examples per component
python generate_100_each.py
```

### Generate Dataset (Claude Haiku)

```bash
python prayer_generator_haiku.py         # base version
python prayer_generator_haiku_2.py       # improved prompting
python prayer_generator_haiku_3.py       # format refinements
python prayer_generator_haiku-strong.py  # high-quality focused run
```

### Generate Dataset (Gemini)

```bash
python generator.py                    # original implementation
python generator_smaler_batches.py     # smaller batches (rate limit friendly)
```

### Merge Datasets

After generating from multiple sources:

```bash
python merge_data.py
```

### Clean / Normalize

Remove scaffolding and normalize to prompt+prayer format:

```bash
python strip_dataset.py
```

### Rate & Evaluate Quality

```bash
# Generate rating spreadsheet from model outputs
python rating.py

# Automate scoring (object consistency, format quality)
python rating-automation.py
```

---

## Dataset Format

All datasets use this JSON schema:

```json
{
  "prompt": "Prayer for activating a plasma reactor.",
  "prayer": "Approach the plasma reactor with sanctified oil...",
  "format_type": "natural"
}
```

Datasets are stored as JSON files in `datasets/`.

---

## Datasets Included

| Directory | Source | Examples | Notes |
|-----------|--------|----------|-------|
| `datasets/mechanicus_dataset_grok/` | xAI Grok | ~4,000 | **Final training dataset** |
| `datasets/final_mechanicus_dataset/` | Merged | ~4,462 | Merged from all sources |
| `datasets/mechanicus_prayers_dataset_haiku1-4/` | Claude Haiku | Various | Iterative generation runs |
| `datasets/mechanicus_prayers_dataset_haiku_strong/` | Claude Haiku | High-quality | Focused quality run |
| `datasets/1st_training_dataset/` | Gemini | Initial | First generation attempt |
| `datasets/2nd_training_dataset/` | Gemini | Second | Improved prompting |

---

## Component Configuration

`mechanicus_components.xlsx` is the master list of:
- **Components** (73): cogitator, plasma reactor, lascannon, Land Raider, etc.
- **Operations** (24): activation, blessing, repair, emergency procedure, etc.
- **Pair Log**: tracks which (component, operation) pairs have been generated

Generators read from this file to determine what prayers to create.

---

## Quality Metrics (Final Dataset)

| Metric | Value |
|--------|-------|
| Total examples | 3,972 |
| Format consistency | 100% |
| Object consistency | 86% |
| Duplicate rate | 0% |
| Prose format | 100% natural prose |

---

## Files Reference

**Grok Generators:**
- `dataset_gen_grok.py` — single focused generation
- `generate_grok_data_large.py` — large-scale from Excel, parallel batches
- `generate_100_each.py` — 100 examples per component

**Haiku Generators:**
- `prayer_generator.py` — base Haiku generator
- `prayer_generator_haiku.py` — v1
- `prayer_generator_haiku_2.py` — v2 (improved)
- `prayer_generator_haiku_3.py` — v3 (format refinements)
- `prayer_generator_haiku-strong.py` — high-quality focused

**Gemini Generators:**
- `generator.py` — original Gemini pipeline
- `generator_smaler_batches.py` — batch-optimized variant

**Pipeline:**
- `merge_data.py` — combine multiple JSON datasets
- `strip_dataset.py` — clean and normalize dataset format
- `rating.py` — create Excel rating sheets from outputs
- `rating-automation.py` — automate quality scoring
- `gen_strategies.py.py` — generation strategy experiments

---

## Tech Stack

- [xAI SDK](https://docs.x.ai/) — Grok API
- [Anthropic SDK](https://docs.anthropic.com/) — Claude Haiku API
- [Google Generative AI](https://ai.google.dev/) — Gemini API
- [openpyxl](https://openpyxl.readthedocs.io/) — Excel component list processing
- [pandas](https://pandas.pydata.org/) — data manipulation

---

## License

**Code:** [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)

**Warhammer 40,000 IP:** All Warhammer 40,000 content is © Games Workshop Limited. Unofficial non-commercial fan project.

---

*"Knowledge is power. Guard it well."*
