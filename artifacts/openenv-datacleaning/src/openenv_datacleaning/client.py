"""
HTTPEnvClient — OpenEnv-compliant client for the DataCleaning environment.

Usage
-----
from openenv_datacleaning.client import DataCleaningClient

env = DataCleaningClient()                        # defaults to localhost:8000
obs = env.reset("basic_format_fix")               # start an episode
print(obs.progress.errors_remaining)

result = env.step({"type": "bulk_transform",
                   "column_name": "category",
                   "transform": "title"})
print(result.reward.value, result.reward.explanation)

state = env.state()
print(state["score"])
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import requests

from .models import Action, Observation, Reward, StepResult


class DataCleaningClient:
    """
    HTTP client for the DataCleaning OpenEnv environment server.

    Mirrors the OpenEnv HTTPEnvClient interface:
        env.reset(task_id)  →  Observation
        env.step(action)    →  StepResult
        env.state()         →  dict  (score, grade_detail, …)
        env.tasks()         →  list[dict]
        env.health()        →  dict

    Parameters
    ----------
    base_url : str
        Root URL of the running FastAPI server.
        Default: ``http://localhost:8000``
    timeout : int
        Seconds to wait for each HTTP request.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    # ------------------------------------------------------------------
    # Core OpenEnv interface
    # ------------------------------------------------------------------

    def reset(self, task_id: str) -> Observation:
        """
        Start a new episode for *task_id*.

        Returns
        -------
        Observation
            The initial observation of the dirty dataset.
        """
        data = self._post("/reset", {"task_id": task_id})
        return Observation(**data["observation"])

    def step(self, action: Dict[str, Any] | Action) -> StepResult:
        """
        Apply *action* to the current dataset state.

        Parameters
        ----------
        action : dict or Action
            Any of the 6 supported action types::

                {"type": "bulk_transform", "column_name": "col", "transform": "lower"}
                {"type": "set_value", "row_index": 0, "column": "col", "value": "new"}
                {"type": "delete_row", "row_index": N}
                {"type": "regex_replace", "column_name": "col",
                 "pattern": "regex", "replacement": "str"}
                {"type": "merge_rows", "rows_indices": [i, j]}
                {"type": "noop"}

        Returns
        -------
        StepResult
            observation, reward (0.0–1.0), done flag, info dict.
        """
        if isinstance(action, Action):
            payload = {"action": action.model_dump(exclude_none=True)}
        else:
            payload = {"action": action}
        data = self._post("/step", payload)
        return StepResult(
            observation=Observation(**data["observation"]),
            reward=Reward(**data["reward"]),
            done=data["done"],
            info=data.get("info", {}),
        )

    def state(self) -> Dict[str, Any]:
        """
        Return current episode state (score, step, done, grade_detail).
        Does NOT advance the episode.
        """
        return self._get("/state")

    # ------------------------------------------------------------------
    # Discovery helpers
    # ------------------------------------------------------------------

    def tasks(self) -> List[Dict[str, Any]]:
        """List all available task IDs with descriptions and difficulty."""
        data = self._get("/tasks")
        # Server returns {"tasks": [...]} with items keyed "id"
        items = data.get("tasks", data) if isinstance(data, dict) else data
        # Normalise key to "task_id" for a consistent API
        result = []
        for item in items:
            entry = dict(item)
            if "id" in entry and "task_id" not in entry:
                entry["task_id"] = entry["id"]
            result.append(entry)
        return result

    def health(self) -> Dict[str, Any]:
        """Check server liveness."""
        return self._get("/healthz")

    # ------------------------------------------------------------------
    # Convenience: run a full episode with a given policy function
    # ------------------------------------------------------------------

    def run_episode(
        self,
        task_id: str,
        policy,
        max_steps: int = 50,
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """
        Run a complete episode using *policy*.

        Parameters
        ----------
        task_id : str
            One of the task identifiers returned by :meth:`tasks`.
        policy : callable
            ``policy(observation: Observation) -> dict``
            Receives the current :class:`Observation` and returns an
            action dict.
        max_steps : int
            Hard cap on episode length (default 50, same as the server).
        verbose : bool
            Print step-by-step reward info.

        Returns
        -------
        dict
            ``{"score": float, "steps": int, "rewards": list[float]}``
        """
        obs = self.reset(task_id)
        rewards: List[float] = []

        for step_num in range(1, max_steps + 1):
            if obs.done:
                break

            action = policy(obs)
            result = self.step(action)
            rewards.append(result.reward.value)

            if verbose:
                print(
                    f"  step {step_num:>2} | action={action.get('type','?'):<18}"
                    f" | reward={result.reward.value:.4f}"
                    f" | errors={result.observation.progress.errors_remaining}"
                )

            obs = result.observation
            if result.done:
                break

        final = self.state()
        return {
            "score": final.get("score", 0.0),
            "steps": len(rewards),
            "rewards": rewards,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, path: str) -> Any:
        resp = self._session.get(f"{self.base_url}{path}", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, payload: Dict[str, Any]) -> Any:
        resp = self._session.post(
            f"{self.base_url}{path}",
            data=json.dumps(payload),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def __repr__(self) -> str:
        return f"DataCleaningClient(base_url={self.base_url!r})"
