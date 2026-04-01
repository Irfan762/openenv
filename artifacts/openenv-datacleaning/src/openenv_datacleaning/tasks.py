"""
Task definitions: dataset generators, schema definitions, and graders.
Each task has:
  - generate_dataset() -> list of row dicts (the messy input)
  - schema_definition: dict mapping column -> {type, nullable, format, ...}
  - grade(current_dataset) -> float (0.0-1.0)
"""

from __future__ import annotations

import re
import copy
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _is_valid_email(v: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(v)))


def _is_valid_phone(v: str) -> bool:
    digits = re.sub(r"\D", "", str(v))
    return len(digits) == 10


def _normalize_phone(v: str) -> str:
    digits = re.sub(r"\D", "", str(v))
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return v


def _is_valid_date(v: str, fmt: str = "%Y-%m-%d") -> bool:
    try:
        datetime.strptime(str(v), fmt)
        return True
    except (ValueError, TypeError):
        return False


def _jaccard_similarity(a: str, b: str) -> float:
    sa = set(a.lower().split())
    sb = set(b.lower().split())
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


# ---------------------------------------------------------------------------
# Task 1: Basic Format Correction (easy)
# ---------------------------------------------------------------------------

TASK1_SCHEMA: Dict[str, Any] = {
    "id": {"type": "integer", "nullable": False},
    "product_name": {"type": "string", "nullable": False, "transform": "strip+title"},
    "category": {"type": "string", "nullable": False, "values": ["Electronics", "Clothing", "Food", "Books", "Sports"]},
    "price": {"type": "float", "nullable": False, "min": 0.01},
    "quantity": {"type": "integer", "nullable": False, "min": 0},
    "date_added": {"type": "date", "nullable": False, "format": "%Y-%m-%d"},
    "in_stock": {"type": "boolean", "nullable": False},
}

TASK1_DIRTY: List[Dict[str, Any]] = [
    {"id": 1,  "product_name": "  laptop  ",     "category": "electronics", "price": "999.99",  "quantity": 5,   "date_added": "01/15/2024",   "in_stock": "yes"},
    {"id": 2,  "product_name": "Running SHOES",  "category": "Sports",      "price": 79.99,     "quantity": "3", "date_added": "2024-02-10",   "in_stock": True},
    {"id": 3,  "product_name": "Python Cookbook","category": "books",       "price": "29.99",   "quantity": 12,  "date_added": "03/22/2024",   "in_stock": "true"},
    {"id": 4,  "product_name": " T-SHIRT  ",     "category": "Clothing",    "price": "  19.99", "quantity": "8", "date_added": "2024-04-01",   "in_stock": "no"},
    {"id": 5,  "product_name": "apple",          "category": "food",        "price": 1.5,       "quantity": 100, "date_added": "2024/05/12",   "in_stock": "YES"},
    {"id": 6,  "product_name": "Tablet ",        "category": "Electronics", "price": "349.0",   "quantity": 7,   "date_added": "Jun 01 2024",  "in_stock": "1"},
    {"id": 7,  "product_name": "soccer ball",    "category": "Sports",      "price": 24.99,     "quantity": "2", "date_added": "2024-07-08",   "in_stock": "false"},
    {"id": 8,  "product_name": "  HEADPHONES",   "category": "electronics", "price": "149.99",  "quantity": 6,   "date_added": "08/30/2024",   "in_stock": "True"},
    {"id": 9,  "product_name": "cookbook",       "category": "books",       "price": "18.5",    "quantity": "15","date_added": "2024-09-14",   "in_stock": "0"},
    {"id": 10, "product_name": "yoga mat ",      "category": "sports",      "price": 39.99,     "quantity": 4,   "date_added": "10/01/2024",   "in_stock": "yes"},
]

TASK1_CLEAN: List[Dict[str, Any]] = [
    {"id": 1,  "product_name": "Laptop",          "category": "Electronics", "price": 999.99, "quantity": 5,   "date_added": "2024-01-15", "in_stock": True},
    {"id": 2,  "product_name": "Running Shoes",   "category": "Sports",      "price": 79.99,  "quantity": 3,   "date_added": "2024-02-10", "in_stock": True},
    {"id": 3,  "product_name": "Python Cookbook", "category": "Books",       "price": 29.99,  "quantity": 12,  "date_added": "2024-03-22", "in_stock": True},
    {"id": 4,  "product_name": "T-Shirt",         "category": "Clothing",    "price": 19.99,  "quantity": 8,   "date_added": "2024-04-01", "in_stock": False},
    {"id": 5,  "product_name": "Apple",           "category": "Food",        "price": 1.5,    "quantity": 100, "date_added": "2024-05-12", "in_stock": True},
    {"id": 6,  "product_name": "Tablet",          "category": "Electronics", "price": 349.0,  "quantity": 7,   "date_added": "2024-06-01", "in_stock": True},
    {"id": 7,  "product_name": "Soccer Ball",     "category": "Sports",      "price": 24.99,  "quantity": 2,   "date_added": "2024-07-08", "in_stock": False},
    {"id": 8,  "product_name": "Headphones",      "category": "Electronics", "price": 149.99, "quantity": 6,   "date_added": "2024-08-30", "in_stock": True},
    {"id": 9,  "product_name": "Cookbook",        "category": "Books",       "price": 18.5,   "quantity": 15,  "date_added": "2024-09-14", "in_stock": False},
    {"id": 10, "product_name": "Yoga Mat",        "category": "Sports",      "price": 39.99,  "quantity": 4,   "date_added": "2024-10-01", "in_stock": True},
]

TASK1_DESCRIPTION = """Fix formatting errors in a product inventory CSV dataset.

Target schema:
- id: integer
- product_name: string, stripped of whitespace, title-cased
- category: string, must be one of: Electronics, Clothing, Food, Books, Sports (title-cased)
- price: float (currently stored as strings with whitespace)
- quantity: integer (currently sometimes strings)
- date_added: date in YYYY-MM-DD format (currently in various formats)
- in_stock: boolean (currently "yes"/"no"/"true"/"false"/"1"/"0")

Fix all 10 rows so they conform to the schema."""


def _grade_task1(dataset: List[Dict[str, Any]]) -> Tuple[float, str]:
    if not dataset:
        return 0.0, "Empty dataset"
    correct = 0
    total_checks = 0
    for i, (row, ref) in enumerate(zip(dataset, TASK1_CLEAN)):
        for col, expected in ref.items():
            total_checks += 1
            got = row.get(col)
            if col == "price":
                try:
                    if abs(float(got) - float(expected)) < 0.001:
                        correct += 1
                except (TypeError, ValueError):
                    pass
            elif col == "quantity":
                try:
                    if int(got) == int(expected):
                        correct += 1
                except (TypeError, ValueError):
                    pass
            elif col == "in_stock":
                if isinstance(got, bool) and got == expected:
                    correct += 1
                elif isinstance(got, str) and got.lower() in ("true", "yes", "1") and expected is True:
                    correct += 1
                elif isinstance(got, str) and got.lower() in ("false", "no", "0") and expected is False:
                    correct += 1
            elif col == "date_added":
                if str(got) == str(expected):
                    correct += 1
            else:
                if str(got).strip() == str(expected).strip():
                    correct += 1
    score = correct / total_checks if total_checks > 0 else 0.0
    return round(score, 4), f"{correct}/{total_checks} field checks passed"


# ---------------------------------------------------------------------------
# Task 2: Schema Validation and Repair (medium)
# ---------------------------------------------------------------------------

TASK2_SCHEMA: Dict[str, Any] = {
    "employee_id": {"type": "string", "nullable": False, "pattern": r"^EMP\d{4}$"},
    "full_name": {"type": "string", "nullable": False},
    "email": {"type": "string", "nullable": False, "format": "email"},
    "phone": {"type": "string", "nullable": True, "format": "us_phone"},
    "department": {"type": "string", "nullable": False, "values": ["Engineering", "Sales", "HR", "Finance", "Marketing"]},
    "salary": {"type": "float", "nullable": False, "min": 30000, "max": 500000},
    "hire_date": {"type": "date", "nullable": False, "format": "%Y-%m-%d"},
    "is_active": {"type": "boolean", "nullable": False},
}

TASK2_DIRTY: List[Dict[str, Any]] = [
    {"employee_id": "EMP0001", "full_name": "Alice Johnson",   "email": "alice@corp.com",          "phone": "555-123-4567", "department": "Engineering", "salary": 95000,   "hire_date": "2020-03-15", "is_active": True},
    {"employee_id": "EMP0002", "full_name": "Bob Smith",       "email": "bob.smith",               "phone": "5551234568",   "department": "Sales",       "salary": 62000,   "hire_date": "2019-07-01", "is_active": True},
    {"employee_id": "EMP0003", "full_name": "Carol White",     "email": "carol@corp.com",          "phone": None,           "department": "HR",          "salary": 55000,   "hire_date": "2021-11-20", "is_active": "yes"},
    {"employee_id": "EMP004",  "full_name": "Dan Brown",       "email": "dan@corp.com",            "phone": "(555)234-5679","department": "Finance",     "salary": 78000,   "hire_date": "2018-06-10", "is_active": True},
    {"employee_id": "EMP0005", "full_name": "Eva Green",       "email": "eva@corp.com",            "phone": "5552345670",   "department": "Marketing",   "salary": -5000,   "hire_date": "2022-01-05", "is_active": False},
    {"employee_id": "EMP0006", "full_name": "Frank Miller",    "email": "frank@corp.com",          "phone": "5553456781",   "department": "R&D",         "salary": 88000,   "hire_date": "2017-09-30", "is_active": True},
    {"employee_id": "EMP0007", "full_name": "Grace Lee",       "email": "grace@corp.com",          "phone": "5554567892",   "department": "Engineering", "salary": 105000,  "hire_date": "23-03-2023", "is_active": "1"},
    {"employee_id": "EMP0008", "full_name": "Hank Jones",      "email": "hank jones@corp.com",     "phone": "5555678903",   "department": "Sales",       "salary": 59000,   "hire_date": "2020-12-11", "is_active": False},
    {"employee_id": "EMP0009", "full_name": "Iris Clark",      "email": "iris@corp.com",           "phone": "555-678-9014", "department": "HR",          "salary": 52000,   "hire_date": "2021-05-25", "is_active": True},
    {"employee_id": "EMP0010", "full_name": "Jack Davis",      "email": "jack@corp.com",           "phone": "5557890125",   "department": "Finance",     "salary": 91000,   "hire_date": "2016-08-14", "is_active": "no"},
    {"employee_id": "EMP0011", "full_name": "Karen Wilson",    "email": "",                        "phone": "5558901236",   "department": "Marketing",   "salary": 67000,   "hire_date": "2022-10-03", "is_active": True},
    {"employee_id": "EMP0012", "full_name": "Leo Martinez",   "email": "leo@corp.com",            "phone": "5559012347",   "department": "Engineering", "salary": 1200000, "hire_date": "2023-02-18", "is_active": True},
    {"employee_id": "EMP0013", "full_name": "Mia Thompson",   "email": "mia@corp.com",            "phone": "5550123458",   "department": "Sales",       "salary": 71000,   "hire_date": "2019-04-22", "is_active": True},
    {"employee_id": "EMP0014", "full_name": "Nate Robinson",  "email": "nate@corp.com",           "phone": "555-123-4569", "department": "HR",          "salary": 57000,   "hire_date": "2020-07-07", "is_active": True},
    {"employee_id": "EMP0015", "full_name": "Olivia Harris",  "email": "olivia@corp.com",         "phone": None,           "department": "Finance",     "salary": 83000,   "hire_date": "2018-01-30", "is_active": False},
]

TASK2_DESCRIPTION = """Clean and validate an employee HR dataset.

Schema requirements:
- employee_id: string matching pattern EMP + 4 digits (e.g. EMP0001)
- full_name: non-empty string
- email: valid email address (must contain @ and domain)
- phone: US phone number in (XXX) XXX-XXXX format, or null
- department: one of Engineering, Sales, HR, Finance, Marketing
- salary: float between 30000 and 500000
- hire_date: date in YYYY-MM-DD format
- is_active: boolean

Errors include: invalid emails, wrong employee_id format, invalid department names,
out-of-range salaries, wrong date formats, boolean stored as strings, and spaces in emails.

For irreparable rows (e.g. missing email with no recoverable value), you may delete the row.
For fixable errors, repair the value in place."""

def _count_task2_errors(dataset: List[Dict[str, Any]]) -> int:
    errors = 0
    valid_depts = {"Engineering", "Sales", "HR", "Finance", "Marketing"}
    for row in dataset:
        eid = str(row.get("employee_id", ""))
        if not re.match(r"^EMP\d{4}$", eid):
            errors += 1
        email = str(row.get("email", ""))
        if not _is_valid_email(email):
            errors += 1
        phone = row.get("phone")
        if phone is not None:
            if not _is_valid_phone(str(phone)):
                errors += 1
        dept = str(row.get("department", ""))
        if dept not in valid_depts:
            errors += 1
        try:
            sal = float(row.get("salary", 0))
            if not (30000 <= sal <= 500000):
                errors += 1
        except (TypeError, ValueError):
            errors += 1
        hd = str(row.get("hire_date", ""))
        if not _is_valid_date(hd):
            errors += 1
        active = row.get("is_active")
        if not isinstance(active, bool):
            errors += 1
    return errors


def _grade_task2(dataset: List[Dict[str, Any]]) -> Tuple[float, str]:
    if not dataset:
        return 0.0, "Empty dataset (deleted all rows — keep valid ones)"
    
    initial_errors = _count_task2_errors(TASK2_DIRTY)
    current_errors = _count_task2_errors(dataset)
    
    errors_fixed = max(0, initial_errors - current_errors)
    base_score = errors_fixed / initial_errors if initial_errors > 0 else 1.0
    
    retained_valid = sum(
        1 for row in dataset
        if re.match(r"^EMP\d{4}$", str(row.get("employee_id", "")))
        and _is_valid_email(str(row.get("email", "")))
        and isinstance(row.get("is_active"), bool)
    )
    
    coverage_score = min(1.0, retained_valid / 13)
    final = 0.65 * base_score + 0.35 * coverage_score
    return round(final, 4), f"{current_errors} errors remaining (was {initial_errors}), {retained_valid} valid rows retained"


# ---------------------------------------------------------------------------
# Task 3: Deduplication and Conflict Resolution (hard)
# ---------------------------------------------------------------------------

TASK3_SCHEMA: Dict[str, Any] = {
    "customer_id": {"type": "string", "nullable": False, "pattern": r"^CUST\d{5}$"},
    "full_name": {"type": "string", "nullable": False},
    "email": {"type": "string", "nullable": False, "format": "email"},
    "phone": {"type": "string", "nullable": True, "format": "us_phone"},
    "city": {"type": "string", "nullable": True},
    "state": {"type": "string", "nullable": True, "pattern": r"^[A-Z]{2}$"},
    "account_balance": {"type": "float", "nullable": False, "min": 0},
    "total_orders": {"type": "integer", "nullable": False, "min": 0},
    "created_date": {"type": "date", "nullable": False, "format": "%Y-%m-%d"},
    "tier": {"type": "string", "nullable": False, "values": ["Bronze", "Silver", "Gold", "Platinum"]},
}

TASK3_DIRTY: List[Dict[str, Any]] = [
    {"customer_id": "CUST00001", "full_name": "James Anderson",    "email": "james.anderson@email.com",  "phone": "5550001111", "city": "New York",    "state": "NY", "account_balance": 1250.00, "total_orders": 15, "created_date": "2020-01-15", "tier": "Gold"},
    {"customer_id": "CUST00002", "full_name": "James E. Anderson",  "email": "j.anderson@email.com",      "phone": "5550001111", "city": "New York",    "state": "NY", "account_balance": 1250.00, "total_orders": 15, "created_date": "2020-01-15", "tier": "Gold"},
    {"customer_id": "CUST00003", "full_name": "James Anderson",    "email": "james.anderson@email.com",  "phone": "5550001112", "city": "New York",    "state": "NY", "account_balance": 1250.50, "total_orders": 16, "created_date": "2020-01-15", "tier": "Gold"},
    {"customer_id": "CUST00004", "full_name": "Sarah Williams",    "email": "sarah@williams.net",         "phone": "5550002222", "city": "Chicago",     "state": "IL", "account_balance": 320.50, "total_orders": 4,  "created_date": "2021-06-20", "tier": "Bronze"},
    {"customer_id": "CUST00005", "full_name": "Sarah A. Williams", "email": "sarah@williams.net",         "phone": "5550002222", "city": "Chicago",     "state": "IL", "account_balance": 320.50, "total_orders": 4,  "created_date": "2021-06-20", "tier": "Bronze"},
    {"customer_id": "CUST00006", "full_name": "Robert Garcia",     "email": "robert.garcia@biz.com",      "phone": "5550003333", "city": "Los Angeles", "state": "CA", "account_balance": 5890.00, "total_orders": 67, "created_date": "2018-11-03", "tier": "Platinum"},
    {"customer_id": "CUST00007", "full_name": "Robert Garcia",     "email": "rgarcia@biz.com",            "phone": "5550003333", "city": "Los Angeles", "state": "ca", "account_balance": 5890.00, "total_orders": 67, "created_date": "2018-11-03", "tier": "Platinum"},
    {"customer_id": "CUST00008", "full_name": "Linda Chen",        "email": "linda.chen@outlook.com",     "phone": "5550004444", "city": "Seattle",     "state": "WA", "account_balance": -150.00, "total_orders": 22, "created_date": "2019-08-17", "tier": "Silver"},
    {"customer_id": "CUST00009", "full_name": "David Miller",      "email": "david.miller@corp.org",      "phone": "5550005555", "city": "Houston",     "state": "TX", "account_balance": 780.25, "total_orders": 11, "created_date": "2022-03-09", "tier": "Silver"},
    {"customer_id": "CUST00010", "full_name": "David Miller",      "email": "dmiller@corp.org",           "phone": "5550005556", "city": "Houston",     "state": "TX", "account_balance": 780.25, "total_orders": 11, "created_date": "2022-03-09", "tier": "Silver"},
    {"customer_id": "CUST00011", "full_name": "Maria Rodriguez",   "email": "maria@rodriguez.io",         "phone": "5550006666", "city": "Miami",       "state": "FL", "account_balance": 2100.00, "total_orders": 31, "created_date": "2020-09-25", "tier": "Gold"},
    {"customer_id": "CUST00012", "full_name": "Thomas Jackson",    "email": "thomas.j@example.com",       "phone": "5550007777", "city": "Phoenix",     "state": "AZ", "account_balance": 95.00,  "total_orders": 2,  "created_date": "2023-01-12", "tier": "Bronze"},
    {"customer_id": "CUST00013", "full_name": "Thomas Jackson",    "email": "thomas.j@example.com",       "phone": "5550007777", "city": "Phoenix",     "state": "AZ", "account_balance": 95.00,  "total_orders": 2,  "created_date": "2023-01-12", "tier": "bronze"},
    {"customer_id": "CUST00014", "full_name": "Nancy White",       "email": "nancy.white@mail.com",       "phone": "5550008888", "city": "Denver",      "state": "CO", "account_balance": 430.75, "total_orders": 8,  "created_date": "2021-12-05", "tier": "Bronze"},
    {"customer_id": "CUST00015", "full_name": "Kevin Brown",       "email": "kevin.brown@net.com",        "phone": "5550009999", "city": "Atlanta",     "state": "GA", "account_balance": 1680.00, "total_orders": 19, "created_date": "2020-05-14", "tier": "Silver"},
    {"customer_id": "CUST00016", "full_name": "Kevin Brown",       "email": "kbrown@net.com",             "phone": "5550009999", "city": "Atlanta",     "state": "GA", "account_balance": 1680.00, "total_orders": 20, "created_date": "2020-05-14", "tier": "Silver"},
]

TASK3_DESCRIPTION = """Deduplicate and repair a customer master database.

The dataset contains 16 records but many are duplicates with conflicting information.
Your goals:
1. Identify duplicate customer groups (same person, different records)
2. Merge each duplicate group into a single canonical record
3. Fix schema violations in remaining records:
   - account_balance must be >= 0 (fix negative balances to 0)
   - state must be 2-letter uppercase code
   - tier must be one of: Bronze, Silver, Gold, Platinum (properly cased)
   - customer_id must match CUST + 5 digits

Duplicate detection signals: same phone, same/similar name, same email domain, same city+state.
When merging, prefer the most complete/accurate values (e.g., highest total_orders, non-negative balance).

Expected final dataset: ~10 unique customers, each schema-valid."""

TASK3_DUPLICATE_GROUPS = [
    ["CUST00001", "CUST00002", "CUST00003"],
    ["CUST00004", "CUST00005"],
    ["CUST00006", "CUST00007"],
    ["CUST00009", "CUST00010"],
    ["CUST00012", "CUST00013"],
    ["CUST00015", "CUST00016"],
]

TASK3_SINGLE_CUSTOMERS = ["CUST00008", "CUST00011", "CUST00014"]


def _count_task3_errors(dataset: List[Dict[str, Any]]) -> int:
    errors = 0
    valid_tiers = {"Bronze", "Silver", "Gold", "Platinum"}
    for row in dataset:
        cid = str(row.get("customer_id", ""))
        if not re.match(r"^CUST\d{5}$", cid):
            errors += 1
        email = str(row.get("email", ""))
        if not _is_valid_email(email):
            errors += 1
        try:
            bal = float(row.get("account_balance", 0))
            if bal < 0:
                errors += 1
        except (TypeError, ValueError):
            errors += 1
        state = str(row.get("state", ""))
        if state and not re.match(r"^[A-Z]{2}$", state):
            errors += 1
        tier = str(row.get("tier", ""))
        if tier not in valid_tiers:
            errors += 1
    return errors


def _grade_task3(dataset: List[Dict[str, Any]]) -> Tuple[float, str]:
    if not dataset:
        return 0.0, "Empty dataset"

    all_orig_ids = {row["customer_id"] for row in TASK3_DIRTY}
    current_ids = [str(row.get("customer_id", "")) for row in dataset]

    resolved_groups = 0
    for group in TASK3_DUPLICATE_GROUPS:
        group_ids_in_result = [cid for cid in current_ids if cid in group]
        if len(group_ids_in_result) <= 1:
            resolved_groups += 1

    dedup_score = resolved_groups / len(TASK3_DUPLICATE_GROUPS)

    schema_errors = _count_task3_errors(dataset)
    max_errors_expected = _count_task3_errors(TASK3_DIRTY)
    errors_fixed = max(0, max_errors_expected - schema_errors)
    repair_score = errors_fixed / max_errors_expected if max_errors_expected > 0 else 1.0

    expected_count = len(TASK3_SINGLE_CUSTOMERS) + len(TASK3_DUPLICATE_GROUPS)
    size_penalty = 0.0
    if len(dataset) > expected_count + 3:
        size_penalty = min(0.3, (len(dataset) - expected_count - 3) * 0.05)

    final = 0.5 * dedup_score + 0.4 * repair_score - size_penalty
    final = max(0.0, min(1.0, final))
    return round(final, 4), (
        f"{resolved_groups}/{len(TASK3_DUPLICATE_GROUPS)} dup groups resolved, "
        f"{schema_errors} schema errors remaining, "
        f"{len(dataset)} rows (expected ~{expected_count})"
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TASKS = {
    "basic_format_fix": {
        "description": TASK1_DESCRIPTION,
        "schema": TASK1_SCHEMA,
        "dirty_data": TASK1_DIRTY,
        "grade_fn": _grade_task1,
        "difficulty": "easy",
    },
    "schema_validation": {
        "description": TASK2_DESCRIPTION,
        "schema": TASK2_SCHEMA,
        "dirty_data": TASK2_DIRTY,
        "grade_fn": _grade_task2,
        "difficulty": "medium",
    },
    "deduplication_and_merge": {
        "description": TASK3_DESCRIPTION,
        "schema": TASK3_SCHEMA,
        "dirty_data": TASK3_DIRTY,
        "grade_fn": _grade_task3,
        "difficulty": "hard",
    },
}
