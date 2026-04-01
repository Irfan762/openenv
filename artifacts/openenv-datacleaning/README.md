# DataCleaning OpenEnv

A real-world **data cleaning and validation** environment for training and evaluating AI agents. Implements the full [OpenEnv](https://github.com/openenv/openenv-core) interface.

---

## What Is This?

Data cleaning is one of the most common and time-consuming tasks in data engineering. This environment simulates three progressively harder cleaning challenges, each with:

- A **messy dataset** generated to reflect real-world data quality issues
- A **target schema** defining correct types, formats, and value constraints
- A **programmatic grader** scoring agent performance 0.0–1.0

---

## Motivation

Existing agent benchmarks focus on code, math, and web navigation. Data quality work — fixing malformed CSVs, resolving duplicates, repairing schema violations — is underrepresented despite being a daily activity for millions of data professionals. This environment fills that gap.

---

## Tasks

| Task ID | Difficulty | Description |
|---|---|---|
| `basic_format_fix` | **Easy** | Fix type/format errors in a 10-row product inventory CSV (dates, booleans, numeric strings, category casing, whitespace) |
| `schema_validation` | **Medium** | Repair a 15-row HR employee dataset: fix invalid emails, phone formats, bad employee IDs, out-of-range salaries, date formats, and string-encoded booleans |
| `deduplication_and_merge` | **Hard** | Deduplicate a 16-row customer database with 6 duplicate groups, conflicting field values, negative balances, bad state codes, and case-inconsistent tier names |

---

## Action Space

Each action is a JSON object with a `type` field. Valid actions:

| Type | Parameters | Description |
|---|---|---|
| `set_value` | `row_index`, `column`, `value` | Set a specific cell to a new value |
| `delete_row` | `row_index` | Remove a row from the dataset |
| `bulk_transform` | `column_name`, `transform` | Apply a transform to all values in a column |
| `regex_replace` | `column_name`, `pattern`, `replacement` | Regex find-replace across a column |
| `merge_rows` | `rows_indices`, `target_value?` | Merge duplicate rows into one canonical record |
| `noop` | — | Skip this step |

Available transforms for `bulk_transform`: `strip`, `lower`, `upper`, `title`, `strip_title`, `to_bool`, `to_int`, `to_float`, `normalize_phone`, `normalize_date`

---

## Observation Space

Each observation includes:

```json
{
  "task_id": "basic_format_fix",
  "task_description": "...",
  "schema_definition": { "column": { "type": "...", "nullable": false, ... } },
  "dataset": [ { "id": 1, "product_name": "  laptop  ", ... }, ... ],
  "validation_errors": [
    { "row_index": 0, "column": "date_added", "error_type": "format", "message": "...", "current_value": "01/15/2024" }
  ],
  "progress": {
    "total_rows": 10,
    "valid_rows": 3,
    "errors_remaining": 18,
    "errors_fixed": 5,
    "duplicate_groups": 0,
    "duplicates_resolved": 0
  },
  "available_actions": [...],
  "step": 2,
  "done": false
}
```

---

## Reward Function

Rewards are shaped for partial progress — agents receive signal at every step, not just at episode end:

| Component | Value |
|---|---|
| Score improvement | Proportional to grade score delta |
| Errors fixed bonus | +0.02 per validation error fixed this step |
| Step penalty | −0.005 per step (encourages efficiency) |
| Invalid action penalty | −0.01 for malformed actions |
| Completion bonus | +0.10–0.15 when score ≥ 0.99 (efficiency-adjusted) |

Final reward is clipped to [0.0, 1.0].

---

## Graders

Each grader is deterministic and reproducible:

- **Task 1**: Field-level comparison against a known clean ground truth. Score = fraction of fields correct across all rows.
- **Task 2**: Counts remaining schema violations; weights by coverage of valid retained rows.
- **Task 3**: 50% deduplication score (duplicate groups resolved), 40% schema repair score, penalty for too many remaining rows.

---

## Setup & Usage

### Local (Python)

```bash
pip install -e ".[dev]"

# Start the environment server
uvicorn openenv_datacleaning.server:app --port 7860

# In another terminal, run the baseline inference script
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=meta-llama/Llama-3.1-8B-Instruct
export HF_TOKEN=your_token_here
python inference.py
```

### Docker

```bash
docker build -t datacleaning-env .
docker run -p 7860:7860 \
  -e API_BASE_URL=https://router.huggingface.co/v1 \
  -e MODEL_NAME=meta-llama/Llama-3.1-8B-Instruct \
  -e HF_TOKEN=your_token_here \
  datacleaning-env
```

### API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/healthz` | Health check |
| `GET` | `/tasks` | List all tasks |
| `POST` | `/reset` | Start a new episode (`{"task_id": "basic_format_fix"}`) |
| `POST` | `/step` | Apply an action (`{"action": {...}}`) |
| `GET` | `/state` | Inspect current state |

---

## OpenEnv Validation

```bash
pip install openenv-core
openenv validate
```

---

## Baseline Scores

Scores obtained with `meta-llama/Llama-3.1-8B-Instruct` via HuggingFace Inference:

| Task | Score |
|---|---|
| basic_format_fix | ~0.72 |
| schema_validation | ~0.58 |
| deduplication_and_merge | ~0.31 |
| **Average** | **~0.54** |

---

## Environment Design

- **Episode length**: 50 steps max
- **State management**: Full dataset copy at each step — no partial views, no hidden state
- **Reproducibility**: `reset()` always reloads the same dirty dataset; graders are deterministic
- **Hard task challenge**: The deduplication task requires multi-step planning (first identify groups, then merge, then fix remaining schema issues) — this is genuinely hard for frontier models without tool use

---

## Project Structure

```
artifacts/openenv-datacleaning/
├── src/openenv_datacleaning/
│   ├── __init__.py       # Public API
│   ├── models.py         # Pydantic models (Observation, Action, Reward, StepResult)
│   ├── env.py            # DataCleaningEnv (reset/step/state)
│   ├── tasks.py          # Task definitions, datasets, graders
│   ├── validator.py      # Schema validation logic
│   ├── actions.py        # Action executor
│   └── server.py         # FastAPI HTTP server
├── tests/
│   └── test_env.py       # Pytest tests
├── inference.py          # Baseline inference script (OpenAI client)
├── openenv.yaml          # OpenEnv metadata
├── Dockerfile            # Container definition
├── pyproject.toml        # Python package config
└── README.md
```
