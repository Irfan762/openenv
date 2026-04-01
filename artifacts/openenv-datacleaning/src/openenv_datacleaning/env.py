"""
DataCleaningEnv: main OpenEnv environment implementation.

Implements: reset(), step(), state()
"""

from __future__ import annotations

import copy
import time
from typing import Any, Dict, List, Optional

from .models import (
    Observation, Action, Reward, StepResult,
    ProgressMetrics, ActionSchema,
)
from .tasks import TASKS
from .validator import validate_dataset
from .actions import apply_action, AVAILABLE_ACTIONS

MAX_STEPS = 50
STEP_PENALTY = 0.005
IRREVERSIBLE_PENALTY = 0.02


class DataCleaningEnv:
    """
    An OpenEnv environment for data cleaning and validation tasks.

    Three tasks with increasing difficulty:
      1. basic_format_fix   (easy)   — 10-row product CSV, simple type/format fixes
      2. schema_validation  (medium) — 15-row HR dataset, schema repair
      3. deduplication_and_merge (hard) — 16-row customer DB, dedup + repair
    """

    def __init__(self, task_id: str = "basic_format_fix"):
        if task_id not in TASKS:
            raise ValueError(f"Unknown task_id: {task_id!r}. Choose from {list(TASKS.keys())}")
        self._task_id = task_id
        self._task_cfg = TASKS[task_id]
        self._dataset: List[Dict[str, Any]] = []
        self._step: int = 0
        self._done: bool = False
        self._initial_error_count: int = 0
        self._errors_fixed_total: int = 0
        self._last_message: Optional[str] = None
        self._episode_start: float = 0.0

    # ------------------------------------------------------------------
    # Core OpenEnv API
    # ------------------------------------------------------------------

    def reset(self) -> Observation:
        """Reset to a fresh episode and return the initial observation."""
        self._dataset = copy.deepcopy(self._task_cfg["dirty_data"])
        self._step = 0
        self._done = False
        self._episode_start = time.time()
        self._last_message = "Episode started. Dataset loaded with errors. Begin cleaning."

        errors = validate_dataset(self._dataset, self._task_cfg["schema"])
        self._initial_error_count = len(errors)
        self._errors_fixed_total = 0

        return self._build_observation(errors)

    def step(self, action: Action) -> StepResult:
        """
        Apply an action and advance one step.

        Returns: StepResult(observation, reward, done, info)
        """
        if self._done:
            obs = self._build_observation(
                validate_dataset(self._dataset, self._task_cfg["schema"])
            )
            return StepResult(
                observation=obs,
                reward=Reward(value=0.0, explanation="Episode is already done"),
                done=True,
                info={"warning": "Episode already ended. Call reset() to start a new one."},
            )

        prev_errors = validate_dataset(self._dataset, self._task_cfg["schema"])
        prev_error_count = len(prev_errors)
        prev_score, _ = self._task_cfg["grade_fn"](self._dataset)

        new_dataset, message = apply_action(self._dataset, action)
        self._dataset = new_dataset
        self._step += 1
        self._last_message = message

        cur_errors = validate_dataset(self._dataset, self._task_cfg["schema"])
        cur_error_count = len(cur_errors)
        cur_score, grade_detail = self._task_cfg["grade_fn"](self._dataset)

        errors_fixed_this_step = max(0, prev_error_count - cur_error_count)
        self._errors_fixed_total += errors_fixed_this_step

        reward = self._compute_reward(
            prev_score=prev_score,
            cur_score=cur_score,
            errors_fixed_this_step=errors_fixed_this_step,
            action_type=action.type,
            error_message=message if message.startswith("ERROR") else None,
        )

        done = (
            cur_error_count == 0
            or self._step >= MAX_STEPS
            or cur_score >= 0.99
        )
        self._done = done

        obs = self._build_observation(cur_errors)
        if done:
            obs.done = True
            obs.message = (
                f"Episode complete! Final score: {cur_score:.4f}. {grade_detail}. "
                f"Steps used: {self._step}/{MAX_STEPS}."
            )

        return StepResult(
            observation=obs,
            reward=reward,
            done=done,
            info={
                "step": self._step,
                "score": cur_score,
                "grade_detail": grade_detail,
                "errors_fixed_this_step": errors_fixed_this_step,
                "errors_remaining": cur_error_count,
                "elapsed_seconds": round(time.time() - self._episode_start, 2),
            },
        )

    def state(self) -> Dict[str, Any]:
        """Return the current environment state (for inspection/serialization)."""
        errors = validate_dataset(self._dataset, self._task_cfg["schema"])
        score, grade_detail = self._task_cfg["grade_fn"](self._dataset)
        return {
            "task_id": self._task_id,
            "step": self._step,
            "done": self._done,
            "dataset": copy.deepcopy(self._dataset),
            "row_count": len(self._dataset),
            "validation_errors": [e.model_dump() for e in errors],
            "error_count": len(errors),
            "score": score,
            "grade_detail": grade_detail,
            "errors_fixed_total": self._errors_fixed_total,
            "initial_error_count": self._initial_error_count,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_reward(
        self,
        prev_score: float,
        cur_score: float,
        errors_fixed_this_step: int,
        action_type: str,
        error_message: Optional[str],
    ) -> Reward:
        breakdown: Dict[str, float] = {}

        score_delta = cur_score - prev_score
        breakdown["score_improvement"] = round(score_delta, 4)

        immediate = errors_fixed_this_step * 0.02
        breakdown["errors_fixed_bonus"] = round(immediate, 4)

        step_cost = STEP_PENALTY
        breakdown["step_penalty"] = round(-step_cost, 4)

        action_penalty = 0.0
        if error_message:
            action_penalty = 0.01
            breakdown["invalid_action_penalty"] = round(-action_penalty, 4)

        completion_bonus = 0.0
        if cur_score >= 0.99:
            steps_remaining = MAX_STEPS - self._step
            efficiency = steps_remaining / MAX_STEPS
            completion_bonus = 0.10 + 0.05 * efficiency
            breakdown["completion_bonus"] = round(completion_bonus, 4)

        raw = score_delta + immediate - step_cost - action_penalty + completion_bonus
        value = max(0.0, min(1.0, raw + 0.5))
        value = round(value, 4)

        explanation = (
            f"score Δ={score_delta:+.4f}, "
            f"+{immediate:.3f} for {errors_fixed_this_step} errors fixed, "
            f"-{step_cost:.3f} step cost"
        )
        if action_penalty:
            explanation += f", -{action_penalty:.3f} invalid action"
        if completion_bonus:
            explanation += f", +{completion_bonus:.3f} completion bonus"

        return Reward(value=value, breakdown=breakdown, explanation=explanation)

    def _build_observation(self, errors) -> Observation:
        task_cfg = self._task_cfg
        dup_groups = 0
        dups_resolved = 0

        if self._task_id == "deduplication_and_merge":
            from .tasks import TASK3_DUPLICATE_GROUPS
            current_ids = [str(row.get("customer_id", "")) for row in self._dataset]
            dup_groups = len(TASK3_DUPLICATE_GROUPS)
            for group in TASK3_DUPLICATE_GROUPS:
                ids_in_result = [cid for cid in current_ids if cid in group]
                if len(ids_in_result) <= 1:
                    dups_resolved += 1

        progress = ProgressMetrics(
            total_rows=len(self._dataset),
            valid_rows=sum(
                1 for row_idx in range(len(self._dataset))
                if not any(e.row_index == row_idx for e in errors)
            ),
            errors_remaining=len(errors),
            errors_fixed=self._errors_fixed_total,
            duplicate_groups=dup_groups,
            duplicates_resolved=dups_resolved,
        )

        return Observation(
            task_id=self._task_id,
            task_description=task_cfg["description"],
            schema_definition=task_cfg["schema"],
            dataset=copy.deepcopy(self._dataset),
            validation_errors=errors,
            progress=progress,
            available_actions=[ActionSchema(**a) for a in AVAILABLE_ACTIONS],
            step=self._step,
            done=self._done,
            message=self._last_message,
        )
