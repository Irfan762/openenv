"""
Typed Pydantic models for the DataCleaning OpenEnv environment.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ValidationError(BaseModel):
    row_index: int = Field(..., description="0-based index of the problematic row")
    column: str = Field(..., description="Name of the column with the error")
    error_type: str = Field(..., description="Category of error (e.g. 'wrong_type', 'missing', 'format')")
    message: str = Field(..., description="Human-readable description of the error")
    current_value: Optional[Any] = Field(None, description="The current (bad) value")


class ProgressMetrics(BaseModel):
    total_rows: int = Field(..., description="Total rows in the dataset")
    valid_rows: int = Field(..., description="Rows currently passing all checks")
    errors_remaining: int = Field(..., description="Number of validation errors still present")
    errors_fixed: int = Field(..., description="Number of errors fixed so far this episode")
    duplicate_groups: int = Field(0, description="Number of duplicate groups detected (hard task)")
    duplicates_resolved: int = Field(0, description="Number of duplicate groups resolved (hard task)")


class ActionSchema(BaseModel):
    type: str = Field(..., description="Action type identifier")
    description: str = Field(..., description="What this action does")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="JSON schema for parameters")


class Observation(BaseModel):
    task_id: str = Field(..., description="Current task identifier")
    task_description: str = Field(..., description="Natural language description of what to accomplish")
    schema_definition: Dict[str, Any] = Field(..., description="Target schema: column -> {type, nullable, format}")
    dataset: List[Dict[str, Any]] = Field(..., description="Current state of the dataset (list of row dicts)")
    validation_errors: List[ValidationError] = Field(default_factory=list, description="Current validation errors")
    progress: ProgressMetrics = Field(..., description="Progress metrics for the current episode")
    available_actions: List[ActionSchema] = Field(..., description="Actions valid in the current state")
    step: int = Field(..., description="Current step number (0-indexed)")
    done: bool = Field(False, description="Whether the episode has ended")
    message: Optional[str] = Field(None, description="Optional message from the last action")


class Action(BaseModel):
    type: str = Field(..., description="Action type (see observation.available_actions)")
    row_index: Optional[int] = Field(None, description="Target row index (0-based)")
    column: Optional[str] = Field(None, description="Target column name")
    value: Optional[Any] = Field(None, description="New value to set")
    rows_indices: Optional[List[int]] = Field(None, description="Multiple row indices (for bulk or merge)")
    target_value: Optional[str] = Field(None, description="Target canonical value (for merge/dedup)")
    pattern: Optional[str] = Field(None, description="Regex pattern for find-replace operations")
    replacement: Optional[str] = Field(None, description="Replacement string")
    column_name: Optional[str] = Field(None, description="Column to apply bulk transformation to")
    transform: Optional[str] = Field(None, description="Named transform to apply (e.g. 'strip', 'lower', 'upper', 'title')")
    threshold: Optional[float] = Field(None, description="Similarity threshold for fuzzy matching (0.0-1.0)")


class Reward(BaseModel):
    value: float = Field(..., ge=0.0, le=1.0, description="Reward for this step (0.0-1.0)")
    breakdown: Dict[str, float] = Field(default_factory=dict, description="Named components of the reward")
    explanation: str = Field(..., description="Human-readable reward explanation")


class StepResult(BaseModel):
    observation: Observation
    reward: Reward
    done: bool
    info: Dict[str, Any] = Field(default_factory=dict)
