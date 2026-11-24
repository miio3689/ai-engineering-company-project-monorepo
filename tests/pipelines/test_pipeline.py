"""Unit tests of the KPI transformation tasks of the business performance pipeline.

They exercise the Prefect tasks of data/pipelines/pipeline.py that compute the
five KPIs of the Brasaland BRIEFING ("Reporte Semanal de Costo y Merma por
Local"), each in isolation through `task.fn`: no database, no API and no
Prefect server. Inputs are in-memory rows with the shape of telemetry_events
(id, timestamp, event_type, tags), where tags carries the event properties.

Run from the repository root:

    uv run --group test python -m pytest tests/pipelines/test_pipeline.py
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pandas as pd
import pytest

from data.pipelines import pipeline

WEEK = date(2026, 11, 16)  # Monday of the ISO week under test
NEXT_WEEK = date(2026, 11, 23)
WINDOW_START, WINDOW_END = WEEK, NEXT_WEEK  # one ISO week

LOCATION_DIM = pd.DataFrame(
    [
        {"location_id": "1", "country": "CO", "currency": "COP"},
        {"location_id": "2", "country": "US", "currency": "USD"},
        {"location_id": "3", "country": "CO", "currency": "COP"},
    ]
)


def telemetry_event(event_type: str, day: int, hour: int = 12, **tags) -> dict:
    """One telemetry_events row; `tags` are the event properties (as stored in jsonb)."""
    return {
        "id": str(uuid.uuid4()),
        "timestamp": datetime(2026, 11, day, hour, tzinfo=timezone.utc),
        "event_type": event_type,
        "tags": {"schema_version": "1.1.0", "session_id": "s-1", **tags},
    }


def inbound(day, location, currency, quantity, unit_cost, order_id):
    return telemetry_event(
        "inbound_order_created",
        day,
        location_id=location,
        currency=currency,
        quantity=quantity,
        unit_cost=unit_cost,
        inbound_order_id=order_id,
    )


def waste(day, location, currency, quantity, unit_cost, order_id):
    return telemetry_event(
        "stock_waste_registered",
        day,
        location_id=location,
        currency=currency,
        quantity=quantity,
        unit_cost=unit_cost,
        outbound_order_id=order_id,
    )


def stockout(day, location, currency, order_id):
    return telemetry_event(
        "stock_threshold_triggered",
        day,
        location_id=location,
        currency=currency,
        triggering_outbound_order_id=order_id,
    )


def price_alert(day, location, currency, order_id):
    return telemetry_event(
        "ingredient_price_variance_detected",
        day,
        location_id=location,
        currency=currency,
        inbound_order_id=order_id,
    )


def kpi_facts(rows: list[dict]) -> pd.DataFrame:
    """Run the preparation task (dedupe, rejections, cost per movement) on the rows."""
    return pipeline.prepare_kpi_facts.fn(pd.DataFrame(rows), LOCATION_DIM)["facts"]


def value_for(kpi: pd.DataFrame, column: str, location: str, week: date = WEEK):
    match = kpi[(kpi["location_id"] == location) & (kpi["week_start"] == week)]
    return match[column].iloc[0] if len(match) else 0


@pytest.fixture
def week_of_location_1():
    """A week of Local 1 (COP) and Local 2 (USD), with values easy to compute by hand."""
    return [
        inbound(16, 1, "COP", quantity=10, unit_cost=4000, order_id=101),  # 40.000 COP
        inbound(17, 1, "COP", quantity=5, unit_cost=2000, order_id=102),  # 10.000 COP
        waste(18, 1, "COP", quantity=2, unit_cost=4000, order_id=201),  # 8.000 COP
        waste(19, 1, "COP", quantity=1, unit_cost=2000, order_id=202),  # 2.000 COP
        stockout(18, 1, "COP", order_id=201),
        stockout(19, 1, "COP", order_id=202),
        price_alert(17, 1, "COP", order_id=102),
        inbound(18, 2, "USD", quantity=3, unit_cost=12.5, order_id=301),  # 37,50 USD
    ]


# ------------------------------------------------ KPI: Costo de compra por local

def test_purchase_cost_per_location_sums_quantity_times_unit_cost(week_of_location_1):
    kpi = pipeline.calculate_purchase_cost_per_location.fn(kpi_facts(week_of_location_1))

    assert value_for(kpi, "total_purchase_cost", "1") == 50_000  # 10×4.000 + 5×2.000
    assert value_for(kpi, "total_purchase_cost", "2") == 37.5  # 3×12,50, in USD
    assert value_for(kpi, "total_purchase_cost", "3") == 0  # no purchases


def test_purchase_cost_counts_a_repeated_inbound_order_once(week_of_location_1):
    resent = dict(week_of_location_1[0], id=str(uuid.uuid4()))  # same order 101, new event id
    kpi = pipeline.calculate_purchase_cost_per_location.fn(
        kpi_facts([*week_of_location_1, resent])
    )

    assert value_for(kpi, "total_purchase_cost", "1") == 50_000


# ------------------------------------------------- KPI: Costo de merma por local

def test_waste_cost_per_location_sums_only_stock_waste_registered(week_of_location_1):
    kpi = pipeline.calculate_waste_cost_per_location.fn(kpi_facts(week_of_location_1))

    assert value_for(kpi, "total_waste_cost", "1") == 10_000  # 2×4.000 + 1×2.000
    assert value_for(kpi, "total_waste_cost", "2") == 0


# ---------------------------------------- KPI: Frecuencia de quiebre de stock

def test_stockout_events_count_per_location_and_week(week_of_location_1):
    next_week_stockout = stockout(23, 1, "COP", order_id=203)
    kpi = pipeline.count_stockout_events_per_location.fn(
        kpi_facts([*week_of_location_1, next_week_stockout])
    )

    assert value_for(kpi, "stockout_events_count", "1") == 2
    assert value_for(kpi, "stockout_events_count", "1", NEXT_WEEK) == 1  # its own ISO week
    assert value_for(kpi, "stockout_events_count", "2") == 0


# ---------------------------------------- KPI: Frecuencia de alertas de precio

def test_price_alert_events_count_per_location(week_of_location_1):
    kpi = pipeline.count_price_alert_events_per_location.fn(kpi_facts(week_of_location_1))

    assert value_for(kpi, "price_alert_events_count", "1") == 1
    assert value_for(kpi, "price_alert_events_count", "2") == 0


# --------------------------------------------------------- KPI: Ratio de merma

def weekly_report(rows: list[dict]) -> pd.DataFrame:
    facts = kpi_facts(rows)
    return pipeline.calculate_waste_ratio_per_location.fn(
        LOCATION_DIM,
        WINDOW_START,
        WINDOW_END,
        pipeline.calculate_purchase_cost_per_location.fn(facts),
        pipeline.calculate_waste_cost_per_location.fn(facts),
        pipeline.count_stockout_events_per_location.fn(facts),
        pipeline.count_price_alert_events_per_location.fn(facts),
    ).set_index("location_id")


def test_weekly_report_matches_briefing_definitions_computed_by_hand(week_of_location_1):
    """Local 1, week of 2026-11-16, computed by hand from the BRIEFING definitions.

    Costo de compra = 10 × 4.000 + 5 × 2.000 = 50.000 COP
    Costo de merma  =  2 × 4.000 + 1 × 2.000 = 10.000 COP
    Ratio de merma  = 10.000 / 50.000         = 0,2
    Quiebres de stock = 2, alertas de precio = 1
    """
    report = weekly_report(week_of_location_1)

    local_1 = report.loc["1"]
    assert local_1["total_purchase_cost"] == 50_000
    assert local_1["total_waste_cost"] == 10_000
    assert local_1["waste_ratio"] == 0.2
    assert local_1["stockout_events_count"] == 2
    assert local_1["price_alert_events_count"] == 1
    assert local_1["currency"] == "COP"
    assert local_1["country"] == "CO"
    assert local_1["week_start"] == WEEK


def test_weekly_report_has_every_location_and_never_mixes_currencies(week_of_location_1):
    report = weekly_report(week_of_location_1)

    assert list(report.index) == ["1", "2", "3"]  # one row per location, even without activity
    assert report.loc["2", "currency"] == "USD"
    assert report.loc["2", "total_purchase_cost"] == 37.5  # never converted nor added to COP
    assert report.loc["3"][
        ["total_purchase_cost", "total_waste_cost", "waste_ratio", "stockout_events_count"]
    ].tolist() == [0, 0, 0, 0]
    assert list(report.reset_index().columns) == pipeline.process.OUTPUT_COLUMNS


def test_waste_ratio_is_zero_when_a_location_had_waste_but_no_purchases():
    report = weekly_report([waste(18, 3, "COP", quantity=4, unit_cost=1000, order_id=401)])

    assert report.loc["3", "total_waste_cost"] == 4000
    assert report.loc["3", "waste_ratio"] == 0  # BRIEFING: 0 if there were no purchases, not ∞


# ------------------------------------------------- defensive behaviour (invalid input)

def test_cost_event_with_null_or_non_numeric_cost_adds_nothing_and_is_counted():
    rows = [
        inbound(16, 1, "COP", quantity=10, unit_cost=4000, order_id=101),
        inbound(17, 1, "COP", quantity=5, unit_cost=None, order_id=102),  # null unit_cost
        inbound(17, 1, "COP", quantity="cinco", unit_cost=2000, order_id=103),  # wrong type
    ]
    prepared = pipeline.prepare_kpi_facts.fn(pd.DataFrame(rows), LOCATION_DIM)
    kpi = pipeline.calculate_purchase_cost_per_location.fn(prepared["facts"])

    assert value_for(kpi, "total_purchase_cost", "1") == 40_000  # only the valid movement
    assert prepared["stats"]["events_without_cost"] == 2


def test_events_with_malformed_tags_unknown_location_or_wrong_currency_are_rejected():
    rows = [
        inbound(16, 1, "COP", quantity=1, unit_cost=1000, order_id=101),  # valid
        inbound(16, 99, "COP", quantity=1, unit_cost=1000, order_id=102),  # unknown location
        inbound(16, 1, "USD", quantity=1, unit_cost=1000, order_id=103),  # currency mismatch
        {**inbound(16, 1, "COP", 1, 1000, 104), "tags": None},  # tags missing
        {**inbound(16, 1, "COP", 1, 1000, 105), "tags": "not-a-json-object"},  # wrong type
    ]
    prepared = pipeline.prepare_kpi_facts.fn(pd.DataFrame(rows), LOCATION_DIM)
    kpi = pipeline.calculate_purchase_cost_per_location.fn(prepared["facts"])

    assert value_for(kpi, "total_purchase_cost", "1") == 1000
    assert prepared["stats"]["rejected_currency_mismatch"] == 1
    assert prepared["stats"]["rejected_unknown_location"] == 3
    assert prepared["stats"]["rows_rejected"] == 4


@pytest.mark.parametrize(
    "task",
    [
        pipeline.calculate_purchase_cost_per_location,
        pipeline.calculate_waste_cost_per_location,
        pipeline.count_stockout_events_per_location,
        pipeline.count_price_alert_events_per_location,
    ],
    ids=lambda task: task.name,
)
def test_kpi_tasks_reject_a_malformed_facts_input(task):
    with pytest.raises(TypeError, match="DataFrame"):
        task.fn([{"location_id": "1", "cost": 10}])  # a list, not a DataFrame
    with pytest.raises(ValueError, match="cost"):
        task.fn(pd.DataFrame({"location_id": ["1"], "week_start": [WEEK], "event_type": ["x"]}))


def test_empty_week_gives_explicit_zero_for_every_location():
    report = weekly_report([])

    assert len(report) == len(LOCATION_DIM)
    assert report[["total_purchase_cost", "total_waste_cost", "waste_ratio"]].sum().sum() == 0
