"""
Inference Script — DataCleaning OpenEnv
=======================================
Uses DataCleaningClient (HTTPEnvClient) instead of raw requests calls.

MANDATORY environment variables:
  API_BASE_URL   OpenAI-compatible endpoint (e.g. https://router.huggingface.co/v1)
  MODEL_NAME     Model identifier (e.g. meta-llama/Llama-3.1-8B-Instruct)
  HF_TOKEN       HuggingFace API token (used as the API key)

Optional:
  DATACLEANING_URL  URL of the running env server (default: http://localhost:8000)

Run:
  python inference.py
"""

import json
import os
import textwrap
from typing import Any, Dict, List, Optional

from openai import OpenAI

from openenv_datacleaning import DataCleaningClient, Observation

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE_URL: str = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
API_KEY: Optional[str] = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
MODEL_NAME: Optional[str] = os.getenv("MODEL_NAME")
ENV_URL: str = os.getenv("DATACLEANING_URL", "http://localhost:8000").rstrip("/")

MAX_STEPS = 50
TEMPERATURE = 0.1
MAX_TOKENS = 512
FALLBACK_ACTION: Dict[str, Any] = {"type": "noop"}

TASK_IDS = ["basic_format_fix", "schema_validation", "deduplication_and_merge"]

SYSTEM_PROMPT = textwrap.dedent("""
You are a data cleaning agent. Your job is to fix errors in a dataset by
issuing exactly one JSON action per turn.

Available action types:
- {"type": "set_value", "row_index": N, "column": "col", "value": <new_value>}
- {"type": "delete_row", "row_index": N}
- {"type": "bulk_transform", "column_name": "col",
   "transform": "strip|lower|upper|title|strip_title|to_bool|to_int|to_float|normalize_phone|normalize_date"}
- {"type": "regex_replace", "column_name": "col", "pattern": "regex", "replacement": "str"}
- {"type": "merge_rows", "rows_indices": [i, j, ...], "target_value": "optional_id"}
- {"type": "noop"}

Rules:
1. Reply with ONLY a valid JSON object — no explanation, no markdown.
2. Choose the most impactful action to fix as many errors as possible at once.
3. Prefer bulk_transform for column-wide issues before fixing individual cells.
4. When all errors are fixed, use noop to signal completion.
""").strip()


# ── Prompt helpers ─────────────────────────────────────────────────────────────

def build_user_prompt(obs: Observation) -> str:
    errors = obs.validation_errors[:10]
    error_lines = "\n".join(
        f"  Row {e.row_index}, col '{e.column}': {e.error_type} — {e.message}"
        for e in errors
    )
    dataset_preview = json.dumps(obs.dataset[:5], indent=2)
    return textwrap.dedent(f"""
        Step {obs.step}. Task: {obs.task_id}

        Progress: {obs.progress.valid_rows}/{obs.progress.total_rows} valid rows,
        {obs.progress.errors_remaining} errors remaining.

        First 5 rows (current state):
        {dataset_preview}

        Current validation errors (showing first 10):
        {error_lines or '  (none — all rows are valid!)'}

        Issue the single best action to make progress. Reply with JSON only.
    """).strip()


def parse_action(text: str) -> Dict[str, Any]:
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        return FALLBACK_ACTION
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        return FALLBACK_ACTION


# ── LLM policy ────────────────────────────────────────────────────────────────

def llm_policy(llm: OpenAI, obs: Observation) -> Dict[str, Any]:
    """Call the LLM and return a parsed action dict."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(obs)},
    ]
    try:
        completion = llm.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            stream=False,
        )
        return parse_action(completion.choices[0].message.content or "")
    except Exception as exc:
        print(f"    LLM error ({exc}) — using noop")
        return FALLBACK_ACTION


# ── Episode runner ─────────────────────────────────────────────────────────────

def run_task(env: DataCleaningClient, llm: OpenAI, task_id: str) -> float:
    """Run one full episode using the LLM policy. Returns final score."""
    print(f"\n{'='*60}")
    print(f"  Task: {task_id}")
    print(f"{'='*60}")

    def policy(obs: Observation) -> Dict[str, Any]:
        action = llm_policy(llm, obs)
        print(f"  Step {obs.step:>2}: {action}")
        return action

    result = env.run_episode(
        task_id=task_id,
        policy=policy,
        max_steps=MAX_STEPS,
        verbose=True,
    )

    print(f"\n  Final score : {result['score']:.4f}")
    print(f"  Steps taken : {result['steps']}")
    print(f"  Avg reward  : {sum(result['rewards'])/max(len(result['rewards']),1):.4f}")
    return result["score"]


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    if not API_KEY:
        raise EnvironmentError("HF_TOKEN or API_KEY environment variable is required")
    if not MODEL_NAME:
        raise EnvironmentError("MODEL_NAME environment variable is required")

    print(f"Model      : {MODEL_NAME}")
    print(f"API base   : {API_BASE_URL}")
    print(f"Env server : {ENV_URL}")

    env = DataCleaningClient(base_url=ENV_URL)

    try:
        health = env.health()
        print(f"Server health: {health}")
    except Exception as exc:
        print(f"ERROR: Cannot reach env server at {ENV_URL}: {exc}")
        print("Start it with: uvicorn openenv_datacleaning.server:app --port 8000")
        return

    print("\nAvailable tasks:")
    for t in env.tasks():
        print(f"  [{t['difficulty']}] {t['task_id']} — {t['description'][:60]}")

    llm = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    scores: Dict[str, float] = {}
    for task_id in TASK_IDS:
        try:
            scores[task_id] = run_task(env, llm, task_id)
        except Exception as exc:
            print(f"  ERROR on task {task_id}: {exc}")
            scores[task_id] = 0.0

    print(f"\n{'='*60}")
    print("  BASELINE SCORES")
    print(f"{'='*60}")
    for tid, score in scores.items():
        print(f"  {tid:<35} {score:.4f}")
    avg = sum(scores.values()) / len(scores)
    print(f"  {'AVERAGE':<35} {avg:.4f}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
