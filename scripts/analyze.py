#!/usr/bin/env python3
"""Validate and summarize Brasaland incident CSV files."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


Record = Mapping[str, Any]


def read_records(csv_path: str | Path) -> list[dict[str, str]]:
    """Load incident rows from a UTF-8 CSV file with a header row."""
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as csv_file:
        return [dict(row) for row in csv.DictReader(csv_file)]


def validate_record(record: Record) -> tuple[bool, list[str]]:
    """Return whether one record is valid and the IDs of any failed rules.

    This function has no I/O and does not rely on module-level business data,
    so it can be imported and reused independently.
    """
    allowed_locations = {
        *(f"COL-{number:02d}" for number in range(1, 11)),
        *(f"FLA-{number:02d}" for number in range(1, 5)),
    }
    allowed_categories = {
        "CUSTOMER_COMPLAINT",
        "EQUIPMENT",
        "SUPPLY",
        "FOOD_QUALITY",
        "STAFF",
    }

    def value(field: str) -> str:
        raw = record.get(field, "")
        return "" if raw is None else str(raw).strip()

    failures: list[str] = []

    location_id = value("location_id")
    if not location_id or location_id not in allowed_locations:
        failures.append("missing_or_invalid_location_id")

    category = value("category")
    if not category or category not in allowed_categories:
        failures.append("missing_or_invalid_category")

    description = value("description")
    if len(description) < 5:
        failures.append("empty_or_short_description")

    if not value("reporter_id"):
        failures.append("missing_reporter_id")

    status = value("status")
    score_text = value("satisfaction_score")
    if status == "CLOSED" and not score_text:
        failures.append("closed_without_satisfaction_score")

    if score_text:
        try:
            score = int(score_text)
        except ValueError:
            score = None
        if score is None or str(score) != score_text or not 1 <= score <= 5:
            failures.append("satisfaction_score_out_of_range")

    return not failures, failures


def calculate_metrics(records: Sequence[Record]) -> dict[str, Any]:
    """Calculate incident metrics without I/O; only valid rows feed breakdowns."""
    categories = (
        "CUSTOMER_COMPLAINT",
        "EQUIPMENT",
        "SUPPLY",
        "FOOD_QUALITY",
        "STAFF",
    )
    statuses = ("OPEN", "CLOSED", "DISCARDED")
    score_values = (1, 2, 3, 4, 5)
    error_names = (
        "missing_or_invalid_location_id",
        "missing_or_invalid_category",
        "empty_or_short_description",
        "missing_reporter_id",
        "closed_without_satisfaction_score",
        "satisfaction_score_out_of_range",
    )

    valid_records: list[Record] = []
    invalid_by_rule: Counter[str] = Counter()
    for record in records:
        is_valid, failures = validate_record(record)
        if is_valid:
            valid_records.append(record)
        else:
            invalid_by_rule.update(failures)

    category_counts = Counter(str(record.get("category", "")).strip() for record in valid_records)
    status_counts = Counter(str(record.get("status", "")).strip() for record in valid_records)

    scored_closed_cases: list[int] = []
    for record in valid_records:
        if str(record.get("status", "")).strip() != "CLOSED":
            continue
        raw_score = str(record.get("satisfaction_score", "")).strip()
        if raw_score:
            scored_closed_cases.append(int(raw_score))

    total = len(records)
    valid_total = len(valid_records)
    closed_total = status_counts["CLOSED"]
    score_counts = Counter(scored_closed_cases)

    return {
        "total_records": total,
        "valid_records": valid_total,
        "invalid_records": total - valid_total,
        "invalid_by_rule": {name: invalid_by_rule[name] for name in error_names},
        "category_counts": {name: category_counts[name] for name in categories},
        "category_percentages": {
            name: (category_counts[name] / valid_total * 100 if valid_total else 0.0)
            for name in categories
        },
        "status_counts": {name: status_counts[name] for name in statuses},
        "status_percentages": {
            name: (status_counts[name] / valid_total * 100 if valid_total else 0.0)
            for name in statuses
        },
        "closed_records": closed_total,
        "scored_closed_cases": len(scored_closed_cases),
        "average_satisfaction": (
            sum(scored_closed_cases) / len(scored_closed_cases) if scored_closed_cases else None
        ),
        "satisfaction_counts": {score: score_counts[score] for score in score_values},
    }


def print_report(metrics: Mapping[str, Any], source_path: str | Path) -> None:
    """Print a human-readable summary in the briefing's report style."""
    line = "=" * 60
    rule_labels = (
        ("missing_or_invalid_location_id", "Missing location_id"),
        ("missing_or_invalid_category", "Invalid or missing category"),
        ("empty_or_short_description", "Empty description"),
        ("missing_reporter_id", "Missing reporter_id"),
        ("closed_without_satisfaction_score", "Closed case, no score"),
        ("satisfaction_score_out_of_range", "Score outside 1–5"),
    )
    satisfaction_labels = {
        1: "Very dissatisfied",
        2: "Dissatisfied",
        3: "Neutral",
        4: "Satisfied",
        5: "Very satisfied",
    }

    print(line)
    print("  BRASALAND — INCIDENT REPORT ANALYSIS")
    print(f"  Source file: {Path(source_path).name}")
    print(line)
    print()
    print(f"TOTAL RECORDS IN FILE .......... {metrics['total_records']}")
    print(f"  ├─ Valid records ................ {metrics['valid_records']}")
    print(f"  └─ Invalid / incomplete .......... {metrics['invalid_records']}")
    print()
    print("INVALID RECORDS BREAKDOWN")
    displayed_rules = [
        (rule, label)
        for rule, label in rule_labels
        if metrics["invalid_by_rule"][rule] > 0
    ]
    for index, (rule, label) in enumerate(displayed_rules):
        branch = "└─" if index == len(displayed_rules) - 1 else "├─"
        print(f"  {branch} {label:<31} {metrics['invalid_by_rule'][rule]}")
    print()
    print("BREAKDOWN BY CATEGORY (valid records)")
    category_items = list(metrics["category_counts"].items())
    for index, (category, count) in enumerate(category_items):
        branch = "└─" if index == len(category_items) - 1 else "├─"
        percentage = metrics["category_percentages"][category]
        print(f"  {branch} {category:<26} {count:>3}  ({percentage:.1f}%)")
    print()
    print("BREAKDOWN BY STATUS (valid records)")
    status_items = list(metrics["status_counts"].items())
    for index, (status, count) in enumerate(status_items):
        branch = "└─" if index == len(status_items) - 1 else "├─"
        percentage = metrics["status_percentages"][status]
        print(f"  {branch} {status:<26} {count:>3}  ({percentage:.1f}%)")
    print()
    print("SATISFACTION INDEX (closed cases)")
    print(f"  Scored cases: {metrics['scored_closed_cases']} of {metrics['closed_records']}")
    average = metrics["average_satisfaction"]
    average_text = "N/A" if average is None else f"{average:.2f}"
    print(f"  Average score: {average_text} / 5.00")
    for index, score in enumerate((1, 2, 3, 4, 5)):
        branch = "└─" if score == 5 else "├─"
        label = satisfaction_labels[score]
        print(f"  {branch} Score {score} ({label}) ... {metrics['satisfaction_counts'][score]}")
    print()
    print(line)


def results_rows(metrics: Mapping[str, Any]) -> list[tuple[str, Any, Any]]:
    """Build the metric rows used by both CSV export interfaces."""
    rows: list[tuple[str, Any, Any]] = [
        ("total_records", metrics["total_records"], ""),
        ("valid_records", metrics["valid_records"], ""),
        ("invalid_records", metrics["invalid_records"], ""),
    ]
    rows.extend((f"invalid_{rule}", count, "") for rule, count in metrics["invalid_by_rule"].items())
    rows.extend(
        (f"category_{category}", count, f"{metrics['category_percentages'][category]:.1f}")
        for category, count in metrics["category_counts"].items()
    )
    rows.extend(
        (f"status_{status}", count, f"{metrics['status_percentages'][status]:.1f}")
        for status, count in metrics["status_counts"].items()
    )
    rows.extend(
        (f"satisfaction_score_{score}", count, "")
        for score, count in metrics["satisfaction_counts"].items()
    )
    rows.extend(
        [
            ("closed_records", metrics["closed_records"], ""),
            ("scored_closed_cases", metrics["scored_closed_cases"], ""),
            (
                "average_satisfaction",
                "" if metrics["average_satisfaction"] is None else f"{metrics['average_satisfaction']:.2f}",
                "",
            ),
        ]
    )
    return rows


def export_results(metrics: Mapping[str, Any], output_path: str | Path = "results.csv") -> None:
    """Export one row per metric to a spreadsheet-friendly CSV."""
    with Path(output_path).open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(("metric", "value", "percentage"))
        writer.writerows(results_rows(metrics))


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a Brasaland incidents CSV file.")
    parser.add_argument("csv_path", help="Path to the incident CSV file")
    args = parser.parse_args()

    records = read_records(args.csv_path)
    metrics = calculate_metrics(records)
    print_report(metrics, args.csv_path)
    answer = input("¿Deseas exportar los resultados a CSV? [s / n] ").strip().lower()
    if answer == "s":
        export_results(metrics)
        print("Results exported to results.csv")


if __name__ == "__main__":
    main()
