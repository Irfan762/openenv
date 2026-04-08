"""
Inference Script — DataCleaning OpenEnv
========================================

MANDATORY — Uses OpenAI-compatible API with environment variables:
  - HF_TOKEN or API_KEY: The API authentication token
  - API_BASE_URL: The LLM endpoint (default: https://router.huggingface.co/v1)
  - MODEL_NAME: The model identifier (e.g., meta-llama/Llama-3.1-8B-Instruct)

STDOUT FORMAT — Exactly as specified:
  [START] task=<task_name> env=<benchmark> model=<model_name>
  [STEP] step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
  [END] success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>

All fields on single lines. Rewards to 2 decimal places. done/success lowercase booleans.
"""

import json
import os
import sys
import textwrap
import time
from typing import Any, Dict, List, Optional

# Delay import to allow env vars to be set before module loads
def get_openai_client():
    from openai import OpenAI
    api_base_url = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
    api_key = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
    if not api_key:
        raise EnvironmentError("HF_TOKEN or API_KEY environment variable is required")
    return OpenAI(base_url=api_base_url, api_key=api_key)


def get_datacleaning_client():
    from openenv_datacleaning import DataCleaningClient
    env_url = os.getenv("DATACLEANING_URL", "http://localhost:8000").rstrip("/")
    return DataCleaningClient(base_url=env_url)


# ── Configuration ─────────────────────────────────────────────────────────────

API_BASE_URL: str = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME: str = os.getenv("MODEL_NAME", "meta-llama/Llama-3.1-8B-Instruct")
ENV_URL: str = os.getenv("DATACLEANING_URL", "http://localhost:8000").rstrip("/")

MAX_STEPS = 50
TEMPERATURE = 0.1
MAX_TOKENS = 512
MAX_RETRIES = 2

TASK_IDS = ["basic_format_fix", "schema_validation", "deduplication_and_merge"]

SYSTEM_PROMPT = textwrap.dedent("""
You are a data cleaning agent. Your job is to fix errors in a dataset by issuing
exactly one valid JSON action per turn. Respond with ONLY a JSON object — no explanation.

Available action types:
- {"type": "set_value", "row_index": N, "column": "col", "value": <value>}
- {"type": "delete_row", "row_index": N}
- {"type": "bulk_transform", "column_name": "col", "transform": "strip|lower|upper|title|..."}
- {"type": "regex_replace", "column_name": "col", "pattern": "regex", "replacement": "str"}
- {"type": "merge_rows", "rows_indices": [i, j, ...], "target_value": "optional"}
- {"type": "noop"}

Rules:
1. Reply ONLY with valid JSON object.
2. Choose impactful bulk operations before individual tweaks.
3. When all errors are fixed, use noop.
""").strip()


# ── Prompt builders ────────────────────────────────────────────────────────────

def build_user_prompt(obs: Any) -> str:
    """Build a prompt from the current observation."""
    errors = obs.validation_errors[:10]
    error_lines = "\n".join(
        f"  Row {e.row_index}, col '{e.column}': {e.error_type} — {e.message}"
        for e in errors
    )
    dataset_preview = json.dumps(obs.dataset[:5], indent=2)
    return textwrap.dedent(f"""
        Step {obs.step}: Task {obs.task_id}

        Progress: {obs.progress.valid_rows}/{obs.progress.total_rows} valid,
        {obs.progress.errors_remaining} errors remaining.

        First 5 rows (current):
        {dataset_preview}

        Validation errors (first 10):
        {error_lines or '  (none — all rows valid!)'}

        Issue the best single action as JSON only:
    """).strip()


def parse_action(text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON action from LLM response, return None if parse fails."""
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        return None
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        return None


# ── LLM policy ────────────────────────────────────────────────────────────────

def llm_policy(llm: Any, obs: Any) -> Optional[Dict[str, Any]]:
    """Call LLM and return parsed action, or None on failure."""
    for attempt in range(MAX_RETRIES):
        try:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(obs)},
            ]
            completion = llm.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                stream=False,
            )
            action = parse_action(completion.choices[0].message.content or "")
            if action:
                return action
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(1)  # Brief backoff before retry
            continue
    return None


# ── Episode runner ────────────────────────────────────────────────────────────

def run_task_with_logging(
    env: Any,
    llm: Any,
    task_id: str,
    model_name: str,
    benchmark_name: str = "data-cleaning-env",
) -> Dict[str, Any]:
    """
    Run one episode and emit mandatory [START]/[STEP]/[END] format to stdout.
    
    Returns: {success, steps, score, rewards[]}
    """
    success = False
    steps_taken = 0
    rewards_list: List[float] = []
    final_score = 0.0
    
    try:
        # [START]
        print(f"[START] task={task_id} env={benchmark_name} model={model_name}")
        sys.stdout.flush()
        
        obs = env.reset(task_id)
        
        for step_num in range(1, MAX_STEPS + 1):
            if obs.done:
                break
            
            action = llm_policy(llm, obs)
            if action is None:
                action = {"type": "noop"}
                error_msg = "LLM failed to produce action"
            else:
                error_msg = None
            
            result = env.step(action)
            reward = result.reward.value
            rewards_list.append(reward)
            steps_taken += 1
            
            # [STEP]
            action_str = json.dumps(action, separators=(",", ":"))
            done_str = "true" if result.done else "false"
            error_str = error_msg if error_msg else "null"
            print(
                f"[STEP] step={step_num} action={action_str} reward={reward:.2f} "
                f"done={done_str} error={error_str}"
            )
            sys.stdout.flush()
            
            obs = result.observation
            if result.done:
                break
        
        final_state = env.state()
        final_score = final_state.get("score", 0.0)
        success = final_score > 0.0
        
    except Exception as e:
        success = False
        final_score = 0.0
    
    # [END] — emitted regardless of success
    rewards_str = ",".join(f"{r:.2f}" for r in rewards_list)
    success_str = "true" if success else "false"
    print(
        f"[END] success={success_str} steps={steps_taken} score={final_score:.2f} "
        f"rewards={rewards_str}"
    )
    sys.stdout.flush()
    
    return {
        "success": success,
        "steps": steps_taken,
        "score": final_score,
        "rewards": rewards_list,
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    """Run baseline agent on all 3 tasks."""
    
    # Validate environment
    api_key = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
    if not api_key:
        raise EnvironmentError("HF_TOKEN or API_KEY environment variable required")
    
    if not MODEL_NAME:
        raise EnvironmentError("MODEL_NAME environment variable required")
    
    try:
        llm = get_openai_client()
        env = get_datacleaning_client()
    except Exception as e:
        print(f"Failed to initialize: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Verify server is reachable
    try:
        env.health()
    except Exception as e:
        print(
            f"ERROR: Cannot reach env server at {ENV_URL}: {e}",
            file=sys.stderr,
        )
        sys.exit(1)
    
    results = {}
    for task_id in TASK_IDS:
        try:
            results[task_id] = run_task_with_logging(
                env=env,
                llm=llm,
                task_id=task_id,
                model_name=MODEL_NAME,
                benchmark_name="data-cleaning-env",
            )
        except Exception as e:
            print(f"ERROR on task {task_id}: {e}", file=sys.stderr)
            results[task_id] = {
                "success": False,
                "steps": 0,
                "score": 0.0,
                "rewards": [],
            }


if __name__ == "__main__":
    main()
