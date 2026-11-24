"""Transformation of telemetry events into weekly business KPIs per location.

Pure Pandas functions: the same input always gives the same output and nothing
here touches the database. KPI definitions come from the company BRIEFING
(see data/pipelines/PIPELINE_DESIGN.md, sections 2.2 and 2.5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pandas as pd

KPI_EVENT_TYPES = [
    "inbound_order_created",
    "stock_waste_registered",
    "stock_threshold_triggered",
    "ingredient_price_variance_detected",
]
# outbound_order_created is extracted only as operating context (silence checks).
SOURCE_EVENT_TYPES = [*KPI_EVENT_TYPES, "outbound_order_created"]
DEFAULT_LOOKBACK_WEEKS = 4

# Field of tags that identifies the business fact behind each event (deduplication).
BUSINESS_KEY_FIELD = {
    "inbound_order_created": "inbound_order_id",
    "ingredient_price_variance_detected": "inbound_order_id",
    "stock_waste_registered": "outbound_order_id",
    "outbound_order_created": "outbound_order_id",
    "stock_threshold_triggered": "triggering_outbound_order_id",
}

EVENT_COLUMNS = ["id", "timestamp", "event_type", "tags"]
OUTPUT_COLUMNS = [
    "location_id",
    "country",
    "week_start",
    "total_purchase_cost",
    "total_waste_cost",
    "waste_ratio",
    "stockout_events_count",
    "price_alert_events_count",
    "currency",
]
COMPARED_COLUMNS = [
    "country",
    "total_purchase_cost",
    "total_waste_cost",
    "waste_ratio",
    "stockout_events_count",
    "price_alert_events_count",
    "currency",
]


@dataclass
class TransformResult:
    weekly: pd.DataFrame
    stats: dict[str, Any] = field(default_factory=dict)


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def compute_window(
    reference_date: date | None = None,
    lookback_weeks: int = DEFAULT_LOOKBACK_WEEKS,
) -> tuple[date, date]:
    """ISO weeks to recompute: the reference week and the previous ones.

    window_start is the Monday of the oldest week (inclusive); window_end is the
    Monday after the reference week (exclusive). All dates are UTC.
    """
    if lookback_weeks < 1:
        raise ValueError("lookback_weeks debe ser al menos 1.")
    reference = reference_date or datetime.now(timezone.utc).date()
    current_monday = monday_of(reference)
    return (
        current_monday - timedelta(weeks=lookback_weeks - 1),
        current_monday + timedelta(days=7),
    )


def week_starts(window_start: date, window_end: date) -> list[date]:
    """Mondays of every ISO week in [window_start, window_end)."""
    return [
        day.date()
        for day in pd.date_range(window_start, window_end, freq="7D", inclusive="left")
    ]


def _text_id(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    numeric = numeric.where(numeric.mod(1).eq(0))
    return numeric.astype("Int64").astype("string")


def _business_keys(events: pd.DataFrame) -> pd.Series:
    keys = pd.Series(pd.NA, index=events.index, dtype="object")
    for event_type, field_name in BUSINESS_KEY_FIELD.items():
        keys = keys.mask(
            events["event_type"].eq(event_type),
            events["tags"].str.get(field_name),
        )
    return keys


def prepare_events(events: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Clean and type the raw events: dedupe, flatten tags, derive the ISO week."""
    frame = events.reindex(columns=EVENT_COLUMNS).copy()
    stats = {"events_in": int(len(frame))}
    frame["tags"] = frame["tags"].astype("object")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.sort_values(["timestamp", "id"]).drop_duplicates(subset="id")
    stats["duplicate_ids_dropped"] = stats["events_in"] - int(len(frame))

    tags = frame["tags"]
    frame["location_id"] = _text_id(tags.str.get("location_id"))
    frame["currency"] = tags.str.get("currency")
    frame["quantity"] = pd.to_numeric(tags.str.get("quantity"), errors="coerce")
    frame["unit_cost"] = pd.to_numeric(tags.str.get("unit_cost"), errors="coerce")
    frame["business_key"] = _business_keys(frame)

    keyed = frame["business_key"].notna()
    repeated = keyed & frame.duplicated(subset=["event_type", "business_key"], keep="first")
    stats["duplicate_facts_dropped"] = int(repeated.sum())
    frame = frame[~repeated].copy()

    frame["week_start"] = (
        frame["timestamp"].dt.normalize()
        - pd.to_timedelta(frame["timestamp"].dt.day_of_week, unit="D")
    ).dt.date
    return frame, stats


GROUP_KEYS = ["location_id", "week_start"]
KPI_FACT_COLUMNS = ["location_id", "week_start", "event_type", "cost"]


def _dimension(location_dim: pd.DataFrame) -> pd.DataFrame:
    missing = {"location_id", "country", "currency"} - set(location_dim.columns)
    if missing:
        raise ValueError(f"location_dim no tiene las columnas {sorted(missing)}.")
    dim = location_dim[["location_id", "country", "currency"]].copy()
    dim["location_id"] = dim["location_id"].astype("string")
    return dim


def _require_kpi_facts(facts: pd.DataFrame) -> None:
    """Defensive check shared by the KPI functions: fail loudly on a malformed input."""
    if not isinstance(facts, pd.DataFrame):
        raise TypeError(
            f"Se esperaba un DataFrame de hechos de KPI, no {type(facts).__name__}."
        )
    missing = set(KPI_FACT_COLUMNS) - set(facts.columns)
    if missing:
        raise ValueError(f"A los hechos de KPI les faltan las columnas {sorted(missing)}.")


def prepare_kpi_facts(
    events: pd.DataFrame,
    location_dim: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Clean events, set aside the ones that cannot be reported and price each movement.

    Currencies are never mixed: events of unknown locations, or whose currency is
    not the location's currency, are rejected and counted. The cost of a movement
    is quantity × unit_cost; a cost event whose cost is unknown (null or
    non-numeric quantity or unit_cost) gets cost NaN and is counted in
    events_without_cost, so it never inflates a KPI.
    """
    facts, stats = prepare_events(events)
    dim_currency = _dimension(location_dim).set_index("location_id")["currency"]

    known = facts["location_id"].isin(dim_currency.index)
    mismatch = known & facts["currency"].ne(facts["location_id"].map(dim_currency))
    stats["rejected_unknown_location"] = int((~known).sum())
    stats["rejected_currency_mismatch"] = int(mismatch.sum())
    stats["rows_rejected"] = (
        stats["rejected_unknown_location"] + stats["rejected_currency_mismatch"]
    )
    facts = facts[known & ~mismatch].copy()

    is_cost_event = facts["event_type"].isin(
        ["inbound_order_created", "stock_waste_registered"]
    )
    facts["cost"] = (facts["quantity"] * facts["unit_cost"]).where(is_cost_event)
    stats["events_without_cost"] = int((is_cost_event & facts["cost"].isna()).sum())
    stats["events_used"] = int(len(facts))
    stats["events_by_type"] = {
        str(name): int(count) for name, count in facts["event_type"].value_counts().items()
    }
    stats["locations_with_events"] = int(facts["location_id"].nunique())
    return facts, stats


def _sum_cost(facts: pd.DataFrame, event_type: str, column: str) -> pd.DataFrame:
    _require_kpi_facts(facts)
    rows = facts.loc[facts["event_type"].eq(event_type), GROUP_KEYS + ["cost"]]
    rows = rows.assign(cost=pd.to_numeric(rows["cost"], errors="coerce").fillna(0))
    return (
        rows.groupby(GROUP_KEYS, as_index=False)["cost"]
        .sum()
        .rename(columns={"cost": column})
    )


def _count_events(facts: pd.DataFrame, event_type: str, column: str) -> pd.DataFrame:
    _require_kpi_facts(facts)
    rows = facts.loc[facts["event_type"].eq(event_type), GROUP_KEYS]
    return rows.groupby(GROUP_KEYS, as_index=False).size().rename(columns={"size": column})


def calculate_purchase_cost(facts: pd.DataFrame) -> pd.DataFrame:
    """KPI "Costo de compra por local": sum of quantity × unit_cost of inbound_order_created."""
    return _sum_cost(facts, "inbound_order_created", "total_purchase_cost")


def calculate_waste_cost(facts: pd.DataFrame) -> pd.DataFrame:
    """KPI "Costo de merma por local": sum of quantity × unit_cost of stock_waste_registered."""
    return _sum_cost(facts, "stock_waste_registered", "total_waste_cost")


def count_stockout_events(facts: pd.DataFrame) -> pd.DataFrame:
    """KPI "Frecuencia de quiebre de stock": count of stock_threshold_triggered."""
    return _count_events(facts, "stock_threshold_triggered", "stockout_events_count")


def count_price_alert_events(facts: pd.DataFrame) -> pd.DataFrame:
    """KPI "Frecuencia de alertas de precio": count of ingredient_price_variance_detected."""
    return _count_events(
        facts, "ingredient_price_variance_detected", "price_alert_events_count"
    )


def calculate_waste_ratio(
    total_purchase_cost: pd.Series,
    total_waste_cost: pd.Series,
) -> pd.Series:
    """KPI "Ratio de merma": total_waste_cost / total_purchase_cost, 0 without purchases.

    A week without purchases (0, negative or unknown purchase cost) has ratio 0,
    never infinity or NaN, as the BRIEFING defines.
    """
    purchase = pd.to_numeric(total_purchase_cost, errors="coerce")
    waste = pd.to_numeric(total_waste_cost, errors="coerce").fillna(0)
    ratio = waste / purchase.where(purchase > 0)
    return ratio.fillna(0).round(4)


def assemble_weekly_location_performance(
    location_dim: pd.DataFrame,
    window_start: date,
    window_end: date,
    purchase_cost: pd.DataFrame,
    waste_cost: pd.DataFrame,
    stockout_events: pd.DataFrame,
    price_alert_events: pd.DataFrame,
) -> pd.DataFrame:
    """One row per known location and ISO week; "no activity" is an explicit zero."""
    dim = _dimension(location_dim)
    weeks = pd.DataFrame({"week_start": week_starts(window_start, window_end)})
    result = dim.merge(weeks, how="cross")
    for kpi in (purchase_cost, waste_cost, stockout_events, price_alert_events):
        kpi = kpi.assign(location_id=kpi["location_id"].astype("string"))
        result = result.merge(kpi, on=GROUP_KEYS, how="left")
    for column in ("total_purchase_cost", "total_waste_cost"):
        result[column] = result[column].fillna(0).astype(float).round(2)
    for column in ("stockout_events_count", "price_alert_events_count"):
        result[column] = result[column].fillna(0).astype(int)
    result["waste_ratio"] = calculate_waste_ratio(
        result["total_purchase_cost"], result["total_waste_cost"]
    )
    result["_order"] = result["location_id"].astype(int)
    result = result.sort_values(["week_start", "_order"]).reset_index(drop=True)
    return result[OUTPUT_COLUMNS]


def transform_weekly_metrics(
    events: pd.DataFrame,
    location_dim: pd.DataFrame,
    window_start: date,
    window_end: date,
) -> TransformResult:
    """One row per location and ISO week with the five business KPIs.

    The same composition that the Prefect subflow transform_weekly_location_kpis
    runs task by task; kept as a single pure function for direct use.
    """
    facts, stats = prepare_kpi_facts(events, location_dim)
    weekly = assemble_weekly_location_performance(
        location_dim,
        window_start,
        window_end,
        calculate_purchase_cost(facts),
        calculate_waste_cost(facts),
        count_stockout_events(facts),
        count_price_alert_events(facts),
    )
    return TransformResult(weekly=weekly, stats=stats)


def find_silent_locations(
    facts: pd.DataFrame,
    window_start: date,
    window_end: date,
) -> list[str]:
    """Locations with events in earlier weeks of the window but none in the last week."""
    weeks = week_starts(window_start, window_end)
    if len(weeks) < 2:
        return []
    last_week = weeks[-1]
    before = set(facts.loc[facts["week_start"] < last_week, "location_id"].dropna())
    latest = set(facts.loc[facts["week_start"] == last_week, "location_id"].dropna())
    return sorted(before - latest, key=int)


def _weekly_counts(timestamps: pd.Series) -> pd.Series:
    converted = pd.to_datetime(timestamps, utc=True)
    weeks = (
        converted.dt.normalize() - pd.to_timedelta(converted.dt.day_of_week, unit="D")
    ).dt.date
    return weeks.value_counts()


def _differences(
    kind: str,
    telemetry_counts: pd.Series,
    domain_counts: pd.Series,
) -> list[dict[str, Any]]:
    table = (
        pd.concat({"telemetry_events": telemetry_counts, "domain_rows": domain_counts}, axis=1)
        .fillna(0)
        .astype(int)
    )
    differing = table[table["telemetry_events"] != table["domain_rows"]]
    return [
        {
            "kind": kind,
            "week_start": str(week),
            "telemetry_events": int(row["telemetry_events"]),
            "domain_rows": int(row["domain_rows"]),
        }
        for week, row in differing.iterrows()
    ]


def reconcile_with_domain(
    facts: pd.DataFrame,
    entries: pd.DataFrame,
    waste_exits: pd.DataFrame,
) -> list[dict[str, Any]]:
    """Weeks where the telemetry lost (or duplicated) events compared with the domain tables."""
    inbound = facts.loc[facts["event_type"].eq("inbound_order_created"), "week_start"]
    waste = facts.loc[facts["event_type"].eq("stock_waste_registered"), "week_start"]
    differences = _differences(
        "inbound",
        inbound.value_counts(),
        _weekly_counts(entries["created_at"]),
    )
    differences += _differences(
        "waste",
        waste.value_counts(),
        _weekly_counts(waste_exits["created_at"]),
    )
    return differences


def _normalize_rows(rows: pd.DataFrame) -> pd.DataFrame:
    rows = rows.reindex(columns=OUTPUT_COLUMNS).copy()
    rows["location_id"] = rows["location_id"].astype(str)
    rows["week_start"] = pd.to_datetime(rows["week_start"]).dt.date
    for column in ("total_purchase_cost", "total_waste_cost"):
        rows[column] = pd.to_numeric(rows[column]).round(2)
    rows["waste_ratio"] = pd.to_numeric(rows["waste_ratio"]).round(4)
    for column in ("stockout_events_count", "price_alert_events_count"):
        rows[column] = pd.to_numeric(rows[column]).astype(int)
    return rows


def classify_rows(
    new_rows: pd.DataFrame,
    existing_rows: pd.DataFrame,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Split the new weekly rows into inserted, updated and unchanged.

    Only inserted and updated rows need to be written, which makes a re-run on
    the same data a no-op. Returns the rows to write and the counters.
    """
    new = _normalize_rows(new_rows)
    old = _normalize_rows(existing_rows)
    merged = new.merge(
        old,
        on=["location_id", "week_start"],
        how="left",
        suffixes=("", "_old"),
        indicator=True,
    )
    is_new = merged["_merge"].eq("left_only")
    changed = pd.Series(False, index=merged.index)
    for column in COMPARED_COLUMNS:
        changed = changed | merged[column].ne(merged[f"{column}_old"])
    changed = changed & ~is_new

    to_write = merged.loc[is_new | changed, OUTPUT_COLUMNS]
    revised_weeks = sorted({str(week) for week in merged.loc[changed, "week_start"]})
    counts = {
        "rows_inserted": int(is_new.sum()),
        "rows_updated": int(changed.sum()),
        "rows_unchanged": int((~is_new & ~changed).sum()),
        "weeks_revised": revised_weeks,
    }
    return to_write.to_dict(orient="records"), counts
