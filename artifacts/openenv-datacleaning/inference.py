"""
Inference Script — DataCleaning OpenEnv
=======================================
MANDATORY environment variables:
  API_BASE_URL   The OpenAI-compatible API endpoint (e.g. https://router.huggingface.co/v1)
  MODEL_NAME     Model identifier (e.g. meta-llama/Llama-3.1-8B-Instruct)
  HF_TOKEN       Your HuggingFace API token (used as the API key)

Optional:
  DATACLEANING_URL  URL of the running env server (default: http://localhost:7860)

Run:
  python inference.py
"""

import os
import json
import textwrap
from typing import Any, Dict, List, Optional

import requests
from openai import OpenAI

API_BASE_URL: str = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
API_KEY: Optional[str] = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
MODEL_NAME: Optional[str] = os.getenv("MODEL_NAME")
ENV_URL: str = os.getenv("DATACLEANING_URL", "http://localhost:7860").rstrip("/")

MAX_STEPS = 50
TEMPERATURE = 0.1
MAX_TOKENS = 512
FALLBACK_ACTION = {"type": "noop"}

TASK_IDS = ["basic_format_fix", "schema_validation", "deduplication_and_merge"]

SYSTEM_PROMPT = textwrap.dedent("""
You are a data cleaning agent. Your job is to fix errors in a dataset by
issuing exactly one JSON action per turn.

Available action types:
- {"type": "set_value", "row_index": N, "column": "col", "value": <new_value>}
- {"type": "delete_row", "row_index": N}
- {"type": "bulk_transform", "column_name": "col", "transform": "strip|lower|upper|title|strip_title|to_bool|to_int|to_float|normalize_phone|normalize_date"}
- {"type": "regex_replace", "column_name": "col", "pattern": "regex", "replacement": "str"}
- {"type": "merge_rows", "rows_indices": [i, j, ...], "target_value": "optional_id"}
- {"type": "noop"}

Rules:
1. Reply with ONLY a valid JSON object — no explanation, no markdown.
2. Choose the most impactful action to fix as many errors as possible at once.
3. Prefer bulk_transform for column-wide issues before fixing individual cells.
4. When all errors are fixed, use noop to signal completion.
""").strip()


def build_user_prompt(obs: Dict[str, Any], step: int) -> str:
    errors = obs.get("validation_errors", [])[:10]
    progress = obs.get("progress", {})
    
    error_lines = "\n".join(
        f"  Row {e['row_index']}, col '{e['column']}': {e['error_type']} — {e['message']}"
        for e in errors
    )
    
    dataset_preview = json.dumps(obs.get("dataset", [])[:5], indent=2)
    
    return textwrap.dedent(f"""
        Step {step}. Task: {obs.get('task_id')}
        
        Progress: {progress.get('valid_rows', 0)}/{progress.get('total_rows', 0)} valid rows, 
        {progress.get('errors_remaining', 0)} errors remaining.
        
        First 5 rows (current state):
        {dataset_preview}
        
        Current validation errors (showing first 10):
        {error_lines or '  (none — all rows are valid!)'}
        
        Issue the single best action to make progress. Reply with JSON only.
    """).strip()


def call_env(method: str, endpoint: str, payload: Optional[Dict] = None) -> Dict:
    url = f"{ENV_URL}{endpoint}"
    if method == "GET":
        resp = requests.get(url, timeout=30)
    else:
        resp = requests.post(url, json=payload or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


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


def run_task(client: OpenAI, task_id: str) -> float:
    print(f"\n{'='*60}")
    print(f"  Task: {task_id}")
    print(f"{'='*60}")

    obs_resp = call_env("POST", "/reset", {"task_id": task_id})
    obs = obs_resp["observation"]

    for step in range(1, MAX_STEPS + 1):
        if obs.get("done"):
            print(f"  Done at step {step - 1}")
            break

        user_prompt = build_user_prompt(obs, step)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                stream=False,
            )
            response_text = completion.choices[0].message.content or ""
        except Exception as exc:
            print(f"  Step {step}: LLM error ({exc}) — using noop")
            response_text = json.dumps(FALLBACK_ACTION)

        action = parse_action(response_text)
        print(f"  Step {step}: action={action}")

        result = call_env("POST", "/step", {"action": action})
        obs = result["observation"]
        reward = result["reward"]
        
        print(f"    reward={reward['value']:.4f} | {reward['explanation'][:80]}")

        if result.get("done"):
            break

    state = call_env("GET", "/state")
    score = state.get("score", 0.0)
    print(f"\n  Final score: {score:.4f} | {state.get('grade_detail', '')}")
    return score


def main() -> None:
    if not API_KEY:
        raise EnvironmentError("HF_TOKEN or API_KEY environment variable is required")
    if not MODEL_NAME:
        raise EnvironmentError("MODEL_NAME environment variable is required")

    print(f"Model: {MODEL_NAME}")
    print(f"API: {API_BASE_URL}")
    print(f"Env server: {ENV_URL}")

    try:
        health = call_env("GET", "/healthz")
        print(f"Server health: {health}")
    except Exception as exc:
        print(f"ERROR: Cannot reach env server at {ENV_URL}: {exc}")
        print("Start the server first: uvicorn openenv_datacleaning.server:app --port 7860")
        return

    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    scores: Dict[str, float] = {}
    for task_id in TASK_IDS:
        try:
            scores[task_id] = run_task(client, task_id)
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
