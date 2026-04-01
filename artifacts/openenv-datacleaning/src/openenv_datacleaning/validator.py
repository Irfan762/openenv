"""
Validator: checks a dataset against a schema definition and returns ValidationErrors.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List

from .models import ValidationError


def _is_valid_email(v: Any) -> bool:
    if v is None or str(v).strip() == "":
        return False
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(v).strip()))


def _is_valid_us_phone(v: Any) -> bool:
    if v is None:
        return True
    digits = re.sub(r"\D", "", str(v))
    return len(digits) == 10


def _is_valid_date(v: Any, fmt: str = "%Y-%m-%d") -> bool:
    try:
        datetime.strptime(str(v).strip(), fmt)
        return True
    except (ValueError, TypeError):
        return False


def validate_dataset(
    dataset: List[Dict[str, Any]],
    schema: Dict[str, Any],
) -> List[ValidationError]:
    errors: List[ValidationError] = []

    for row_idx, row in enumerate(dataset):
        for col, rules in schema.items():
            value = row.get(col)
            col_type = rules.get("type")
            nullable = rules.get("nullable", True)
            fmt = rules.get("format")
            pattern = rules.get("pattern")
            allowed_values = rules.get("values")
            min_val = rules.get("min")
            max_val = rules.get("max")

            if value is None or (isinstance(value, str) and value.strip() == ""):
                if not nullable:
                    errors.append(ValidationError(
                        row_index=row_idx,
                        column=col,
                        error_type="missing",
                        message=f"Column '{col}' is required but missing/empty",
                        current_value=value,
                    ))
                continue

            if col_type == "integer":
                try:
                    int(value)
                    if not isinstance(value, (int, bool)):
                        errors.append(ValidationError(
                            row_index=row_idx,
                            column=col,
                            error_type="wrong_type",
                            message=f"'{col}' should be an integer, got {type(value).__name__}",
                            current_value=value,
                        ))
                except (ValueError, TypeError):
                    errors.append(ValidationError(
                        row_index=row_idx,
                        column=col,
                        error_type="wrong_type",
                        message=f"'{col}' cannot be converted to integer: {value!r}",
                        current_value=value,
                    ))

            elif col_type == "float":
                try:
                    fv = float(value)
                    if not isinstance(value, (int, float)):
                        errors.append(ValidationError(
                            row_index=row_idx,
                            column=col,
                            error_type="wrong_type",
                            message=f"'{col}' should be a float, got {type(value).__name__}",
                            current_value=value,
                        ))
                    else:
                        if min_val is not None and fv < min_val:
                            errors.append(ValidationError(
                                row_index=row_idx,
                                column=col,
                                error_type="out_of_range",
                                message=f"'{col}' value {fv} is below minimum {min_val}",
                                current_value=value,
                            ))
                        if max_val is not None and fv > max_val:
                            errors.append(ValidationError(
                                row_index=row_idx,
                                column=col,
                                error_type="out_of_range",
                                message=f"'{col}' value {fv} exceeds maximum {max_val}",
                                current_value=value,
                            ))
                except (ValueError, TypeError):
                    errors.append(ValidationError(
                        row_index=row_idx,
                        column=col,
                        error_type="wrong_type",
                        message=f"'{col}' cannot be converted to float: {value!r}",
                        current_value=value,
                    ))

            elif col_type == "boolean":
                if not isinstance(value, bool):
                    errors.append(ValidationError(
                        row_index=row_idx,
                        column=col,
                        error_type="wrong_type",
                        message=f"'{col}' should be boolean True/False, got {value!r}",
                        current_value=value,
                    ))

            elif col_type == "date":
                if not _is_valid_date(value):
                    errors.append(ValidationError(
                        row_index=row_idx,
                        column=col,
                        error_type="format",
                        message=f"'{col}' is not a valid YYYY-MM-DD date: {value!r}",
                        current_value=value,
                    ))

            elif col_type == "string":
                sval = str(value)
                if fmt == "email" and not _is_valid_email(sval):
                    errors.append(ValidationError(
                        row_index=row_idx,
                        column=col,
                        error_type="format",
                        message=f"'{col}' is not a valid email: {sval!r}",
                        current_value=value,
                    ))
                elif fmt == "us_phone" and not _is_valid_us_phone(sval):
                    errors.append(ValidationError(
                        row_index=row_idx,
                        column=col,
                        error_type="format",
                        message=f"'{col}' is not a valid 10-digit US phone: {sval!r}",
                        current_value=value,
                    ))
                if pattern and not re.match(pattern, sval):
                    errors.append(ValidationError(
                        row_index=row_idx,
                        column=col,
                        error_type="pattern",
                        message=f"'{col}' doesn't match required pattern {pattern!r}: {sval!r}",
                        current_value=value,
                    ))
                if allowed_values and sval not in allowed_values:
                    errors.append(ValidationError(
                        row_index=row_idx,
                        column=col,
                        error_type="invalid_value",
                        message=f"'{col}' must be one of {allowed_values}, got {sval!r}",
                        current_value=value,
                    ))

    return errors
