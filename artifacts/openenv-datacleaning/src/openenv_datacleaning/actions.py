"""
Action executor: applies an Action to the dataset and returns a (new_dataset, message) tuple.
Actions are stateless transformations; the environment manages state.
"""

from __future__ import annotations

import re
import copy
from typing import Any, Dict, List, Optional, Tuple

from .models import Action


AVAILABLE_ACTIONS = [
    {
        "type": "set_value",
        "description": "Set a specific cell to a new value",
        "parameters": {
            "row_index": {"type": "integer", "description": "Row index (0-based)"},
            "column": {"type": "string", "description": "Column name"},
            "value": {"description": "New value to set (any type)"},
        },
    },
    {
        "type": "delete_row",
        "description": "Remove a row from the dataset entirely",
        "parameters": {
            "row_index": {"type": "integer", "description": "Row index (0-based)"},
        },
    },
    {
        "type": "bulk_transform",
        "description": "Apply a named string transform to all values in a column",
        "parameters": {
            "column_name": {"type": "string", "description": "Column to transform"},
            "transform": {
                "type": "string",
                "description": "One of: strip, lower, upper, title, strip_lower, strip_title, to_bool, to_int, to_float, normalize_phone, normalize_date",
            },
        },
    },
    {
        "type": "regex_replace",
        "description": "Apply a regex find-replace across all values in a column",
        "parameters": {
            "column_name": {"type": "string", "description": "Column to process"},
            "pattern": {"type": "string", "description": "Regex pattern to find"},
            "replacement": {"type": "string", "description": "Replacement string"},
        },
    },
    {
        "type": "merge_rows",
        "description": "Merge multiple rows into one canonical record (for deduplication)",
        "parameters": {
            "rows_indices": {"type": "array", "items": {"type": "integer"}, "description": "Row indices to merge (keep first, delete rest)"},
            "target_value": {"type": "string", "description": "Optional: preferred customer_id/value to keep for the merged row"},
        },
    },
    {
        "type": "noop",
        "description": "Do nothing (skip this step)",
        "parameters": {},
    },
]


def _to_bool(v: Any) -> Any:
    if isinstance(v, bool):
        return v
    sv = str(v).strip().lower()
    if sv in ("true", "yes", "1", "y", "on"):
        return True
    if sv in ("false", "no", "0", "n", "off"):
        return False
    return v


def _normalize_phone(v: Any) -> Any:
    if v is None:
        return None
    digits = re.sub(r"\D", "", str(v))
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return v


def _normalize_date(v: Any) -> Any:
    from datetime import datetime
    sv = str(v).strip()
    formats = [
        "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d",
        "%b %d %Y", "%B %d %Y", "%d-%m-%Y",
        "%m-%d-%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(sv, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return v


TRANSFORM_FNS = {
    "strip": lambda v: str(v).strip() if v is not None else v,
    "lower": lambda v: str(v).strip().lower() if v is not None else v,
    "upper": lambda v: str(v).strip().upper() if v is not None else v,
    "title": lambda v: str(v).strip().title() if v is not None else v,
    "strip_lower": lambda v: str(v).strip().lower() if v is not None else v,
    "strip_title": lambda v: str(v).strip().title() if v is not None else v,
    "to_bool": _to_bool,
    "to_int": lambda v: int(v) if v is not None else v,
    "to_float": lambda v: float(str(v).strip()) if v is not None else v,
    "normalize_phone": _normalize_phone,
    "normalize_date": _normalize_date,
}


def apply_action(
    dataset: List[Dict[str, Any]],
    action: Action,
) -> Tuple[List[Dict[str, Any]], str]:
    ds = copy.deepcopy(dataset)
    n = len(ds)

    if action.type == "noop":
        return ds, "No operation performed."

    elif action.type == "set_value":
        idx = action.row_index
        col = action.column
        if idx is None or col is None:
            return ds, "ERROR: set_value requires row_index and column"
        if not (0 <= idx < n):
            return ds, f"ERROR: row_index {idx} out of range (dataset has {n} rows)"
        if col not in ds[idx]:
            return ds, f"ERROR: column '{col}' not found in row {idx}"
        ds[idx][col] = action.value
        return ds, f"Set row {idx} column '{col}' to {action.value!r}"

    elif action.type == "delete_row":
        idx = action.row_index
        if idx is None:
            return ds, "ERROR: delete_row requires row_index"
        if not (0 <= idx < n):
            return ds, f"ERROR: row_index {idx} out of range (dataset has {n} rows)"
        removed = ds.pop(idx)
        return ds, f"Deleted row {idx} (was: {removed})"

    elif action.type == "bulk_transform":
        col = action.column_name
        transform = action.transform
        if col is None or transform is None:
            return ds, "ERROR: bulk_transform requires column_name and transform"
        fn = TRANSFORM_FNS.get(transform)
        if fn is None:
            return ds, f"ERROR: unknown transform '{transform}'. Use one of: {list(TRANSFORM_FNS.keys())}"
        count = 0
        for row in ds:
            if col in row:
                try:
                    row[col] = fn(row[col])
                    count += 1
                except Exception as e:
                    pass
        return ds, f"Applied '{transform}' to column '{col}' across {count} rows"

    elif action.type == "regex_replace":
        col = action.column_name
        pattern = action.pattern
        replacement = action.replacement
        if col is None or pattern is None or replacement is None:
            return ds, "ERROR: regex_replace requires column_name, pattern, and replacement"
        count = 0
        for row in ds:
            if col in row and row[col] is not None:
                try:
                    new_val = re.sub(pattern, replacement, str(row[col]))
                    if new_val != str(row[col]):
                        row[col] = new_val
                        count += 1
                except Exception as e:
                    return ds, f"ERROR: invalid regex pattern: {e}"
        return ds, f"Regex replaced {count} values in column '{col}'"

    elif action.type == "merge_rows":
        indices = action.rows_indices
        if not indices or len(indices) < 2:
            return ds, "ERROR: merge_rows requires at least 2 row indices"
        valid_indices = [i for i in indices if 0 <= i < n]
        if len(valid_indices) < 2:
            return ds, f"ERROR: fewer than 2 valid indices provided: {indices}"
        
        primary = ds[valid_indices[0]]
        for i in valid_indices[1:]:
            for col, val in ds[i].items():
                if primary.get(col) is None and val is not None:
                    primary[col] = val
        
        if action.target_value:
            primary["customer_id"] = action.target_value

        to_delete = sorted(valid_indices[1:], reverse=True)
        for i in to_delete:
            ds.pop(i)
        
        return ds, f"Merged rows {valid_indices} into row {valid_indices[0]}, deleted {len(valid_indices)-1} duplicates"

    else:
        return ds, f"ERROR: unknown action type '{action.type}'"
