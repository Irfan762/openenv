"""
Tests for the DataCleaning OpenEnv environment.
Run: pytest tests/
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from openenv_datacleaning import DataCleaningEnv
from openenv_datacleaning.models import Action


class TestTask1BasicFormatFix:
    def setup_method(self):
        self.env = DataCleaningEnv(task_id="basic_format_fix")

    def test_reset_returns_observation(self):
        obs = self.env.reset()
        assert obs.task_id == "basic_format_fix"
        assert len(obs.dataset) == 10
        assert len(obs.validation_errors) > 0

    def test_initial_has_errors(self):
        obs = self.env.reset()
        assert obs.progress.errors_remaining > 0

    def test_bulk_transform_strips_whitespace(self):
        self.env.reset()
        action = Action(type="bulk_transform", column_name="product_name", transform="strip_title")
        result = self.env.step(action)
        assert not result.observation.dataset[0]["product_name"].startswith(" ")

    def test_normalize_date_converts_format(self):
        self.env.reset()
        action = Action(type="bulk_transform", column_name="date_added", transform="normalize_date")
        result = self.env.step(action)
        for row in result.observation.dataset:
            import re
            assert re.match(r"\d{4}-\d{2}-\d{2}", str(row["date_added"])), f"Bad date: {row['date_added']}"

    def test_to_bool_converts_strings(self):
        self.env.reset()
        action = Action(type="bulk_transform", column_name="in_stock", transform="to_bool")
        result = self.env.step(action)
        for row in result.observation.dataset:
            assert isinstance(row["in_stock"], bool), f"Expected bool, got {type(row['in_stock'])}"

    def test_noop_gives_step_penalty(self):
        self.env.reset()
        result = self.env.step(Action(type="noop"))
        assert result.reward.value < 0.55

    def test_set_value(self):
        self.env.reset()
        action = Action(type="set_value", row_index=0, column="category", value="Electronics")
        result = self.env.step(action)
        assert result.observation.dataset[0]["category"] == "Electronics"

    def test_delete_row(self):
        self.env.reset()
        action = Action(type="delete_row", row_index=0)
        result = self.env.step(action)
        assert len(result.observation.dataset) == 9

    def test_state_returns_dict(self):
        self.env.reset()
        state = self.env.state()
        assert "dataset" in state
        assert "score" in state
        assert "step" in state


class TestTask2SchemaValidation:
    def setup_method(self):
        self.env = DataCleaningEnv(task_id="schema_validation")

    def test_reset(self):
        obs = self.env.reset()
        assert len(obs.dataset) == 15
        assert len(obs.validation_errors) > 0

    def test_fixing_boolean_reduces_errors(self):
        obs = self.env.reset()
        initial = obs.progress.errors_remaining
        result = self.env.step(Action(type="bulk_transform", column_name="is_active", transform="to_bool"))
        assert result.observation.progress.errors_remaining < initial


class TestTask3Deduplication:
    def setup_method(self):
        self.env = DataCleaningEnv(task_id="deduplication_and_merge")

    def test_reset(self):
        obs = self.env.reset()
        assert len(obs.dataset) == 16
        assert obs.progress.duplicate_groups > 0

    def test_merge_rows(self):
        self.env.reset()
        action = Action(type="merge_rows", rows_indices=[0, 1, 2], target_value="CUST00001")
        result = self.env.step(action)
        assert len(result.observation.dataset) == 14

    def test_max_steps_ends_episode(self):
        self.env.reset()
        for _ in range(50):
            result = self.env.step(Action(type="noop"))
            if result.done:
                break
        assert result.done


class TestGraders:
    def test_task1_perfect_score(self):
        from openenv_datacleaning.tasks import TASKS, TASK1_CLEAN
        grade_fn = TASKS["basic_format_fix"]["grade_fn"]
        score, _ = grade_fn(TASK1_CLEAN)
        assert score >= 0.99

    def test_task1_dirty_score(self):
        from openenv_datacleaning.tasks import TASKS, TASK1_DIRTY
        grade_fn = TASKS["basic_format_fix"]["grade_fn"]
        score, _ = grade_fn(TASK1_DIRTY)
        assert score < 0.8

    def test_task2_empty_dataset_scores_zero(self):
        from openenv_datacleaning.tasks import TASKS
        grade_fn = TASKS["schema_validation"]["grade_fn"]
        score, _ = grade_fn([])
        assert score == 0.0

    def test_task3_dedup_improves_score(self):
        from openenv_datacleaning.tasks import TASKS, TASK3_DIRTY
        import copy
        grade_fn = TASKS["deduplication_and_merge"]["grade_fn"]
        dirty = copy.deepcopy(TASK3_DIRTY)
        dirty_score, _ = grade_fn(dirty)
        
        merged = [row for i, row in enumerate(dirty) if i not in [1, 2, 4, 6, 9, 12, 15]]
        merged_score, _ = grade_fn(merged)
        assert merged_score > dirty_score
