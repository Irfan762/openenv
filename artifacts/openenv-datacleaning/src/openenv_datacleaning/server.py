"""
FastAPI server exposing the DataCleaning OpenEnv environment as an HTTP API.
Endpoints:
  POST /reset       — start a new episode
  POST /step        — apply an action
  GET  /state       — inspect current state
  GET  /tasks       — list available tasks
  GET  /healthz     — health check
"""

from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .env import DataCleaningEnv
from .models import Action, Observation, Reward, StepResult

ROOT_PATH = os.environ.get("ROOT_PATH", "")

app = FastAPI(
    title="DataCleaning OpenEnv",
    description=(
        "A real-world data cleaning and validation environment for AI agents. "
        "Implements the OpenEnv step()/reset()/state() API.\n\n"
        "**3 tasks:** basic_format_fix (easy) → schema_validation (medium) → deduplication_and_merge (hard)\n\n"
        "**Workflow:** POST /reset → POST /step (repeat) → GET /state"
    ),
    version="1.0.0",
    root_path=ROOT_PATH if ROOT_PATH else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_env: DataCleaningEnv = DataCleaningEnv(task_id="basic_format_fix")


class ResetRequest(BaseModel):
    task_id: str = "basic_format_fix"


class StepRequest(BaseModel):
    action: Action


class ResetResponse(BaseModel):
    observation: Observation
    task_id: str


@app.get("/healthz")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/tasks")
def list_tasks() -> Dict[str, Any]:
    from .tasks import TASKS
    return {
        "tasks": [
            {
                "id": tid,
                "description": cfg["description"].strip()[:200] + "...",
                "difficulty": cfg["difficulty"],
            }
            for tid, cfg in TASKS.items()
        ]
    }


@app.post("/reset")
def reset(request: ResetRequest = ResetRequest()) -> ResetResponse:
    global _env
    task_id = request.task_id if request.task_id else "basic_format_fix"
    from .tasks import TASKS
    if task_id not in TASKS:
        raise HTTPException(status_code=400, detail=f"Unknown task_id: {task_id!r}. Choose from {list(TASKS.keys())}")
    _env = DataCleaningEnv(task_id=task_id)
    obs = _env.reset()
    return ResetResponse(observation=obs, task_id=task_id)


@app.post("/step")
def step(request: StepRequest) -> StepResult:
    result = _env.step(request.action)
    return result


@app.get("/state")
def state() -> Dict[str, Any]:
    return _env.state()


def main() -> None:
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("openenv_datacleaning.server:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
