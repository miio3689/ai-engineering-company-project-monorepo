"""Pure-function tests for weekly location performance transformations."""

from datetime import date, datetime, timezone
import unittest

import pandas as pd

from data.process import weekly_location_performance as process


WINDOW_START = date(2026, 11, 9)
WINDOW_END = date(2026, 11, 23)
LOCATION_DIM = pd.DataFrame(
    [
        {"location_id": "1", "country": "CO", "currency": "COP"},
        {"location_id": "2", "country": "US", "currency": "USD"},
    ]
)


def event(event_type, day, tags, event_id=None):
    return {
        "id": event_id or f"id-{len(tags)}-{day}-{event_type}-{tags.get('quantity', 0)}",
        "timestamp": day,
        "event_type": event_type,
        "tags": tags,
    }


def tags(location=1, currency="COP", quantity=1, **extra):
    return {
        "location_id": location,
        "country": "US" if currency == "USD" else "CO",
        "currency": currency,
        "quantity": quantity,
        **extra,
    }


def frame(events):
    return pd.DataFrame(events, columns=["id", "timestamp", "event_type", "tags"])


class WeeklyPerformanceTransformTests(unittest.TestCase):
    def test_computes_weekly_kpis_per_location(self):
        events = frame(
            [
                event("inbound_order_created", "2026-11-09T12:00:00Z", tags(quantity=2, unit_cost=10, inbound_order_id=1)),
                event("inbound_order_created", "2026-11-10T12:00:00Z", tags(quantity=3, unit_cost=20, inbound_order_id=2)),
                event("stock_waste_registered", "2026-11-11T12:00:00Z", tags(quantity=2, unit_cost=5, outbound_order_id=3)),
                event("stock_threshold_triggered", "2026-11-12T12:00:00Z", tags(triggering_outbound_order_id=4)),
                event("ingredient_price_variance_detected", "2026-11-13T12:00:00Z", tags(inbound_order_id=5)),
                event("inbound_order_created", "2026-11-10T12:00:00Z", tags(location=2, currency="USD", quantity=1, unit_cost=7, inbound_order_id=6)),
            ]
        )
        result = process.transform_weekly_metrics(
            events, LOCATION_DIM, WINDOW_START, WINDOW_END
        )
        first = result.weekly[
            (result.weekly.location_id == "1")
            & (result.weekly.week_start == WINDOW_START)
        ].iloc[0]
        self.assertEqual(first.total_purchase_cost, 80)
        self.assertEqual(first.total_waste_cost, 10)
        self.assertEqual(first.waste_ratio, 0.125)
        self.assertEqual(first.stockout_events_count, 1)
        self.assertEqual(first.price_alert_events_count, 1)
        second = result.weekly[
            (result.weekly.location_id == "2")
            & (result.weekly.week_start == WINDOW_START)
        ].iloc[0]
        self.assertEqual(second.currency, "USD")
        self.assertEqual(second.total_purchase_cost, 7)

    def test_ratio_is_zero_without_purchase_even_when_waste_exists(self):
        events = frame(
            [event("stock_waste_registered", "2026-11-10T00:00:00Z", tags(unit_cost=8, outbound_order_id=1))]
        )
        result = process.transform_weekly_metrics(
            events, LOCATION_DIM.iloc[:1], WINDOW_START, WINDOW_END
        )
        self.assertEqual(result.weekly.iloc[0].total_waste_cost, 8)
        self.assertEqual(result.weekly.iloc[0].waste_ratio, 0)

    def test_complete_location_week_grid_contains_explicit_zeros(self):
        result = process.transform_weekly_metrics(
            frame([]), LOCATION_DIM, WINDOW_START, WINDOW_END
        )
        self.assertEqual(len(result.weekly), 4)
        self.assertEqual(set(result.weekly.location_id), {"1", "2"})
        self.assertEqual(set(result.weekly.week_start), {WINDOW_START, date(2026, 11, 16)})
        self.assertTrue(
            (result.weekly[["total_purchase_cost", "total_waste_cost", "waste_ratio"]] == 0)
            .all()
            .all()
        )

    def test_deduplicates_event_ids_and_business_facts(self):
        duplicated = event(
            "inbound_order_created",
            "2026-11-10T00:00:00Z",
            tags(quantity=2, unit_cost=3, inbound_order_id=11),
            "same-id",
        )
        same_fact = event(
            "inbound_order_created",
            "2026-11-10T01:00:00Z",
            tags(quantity=2, unit_cost=3, inbound_order_id=11),
            "different-id",
        )
        facts, stats = process.prepare_events(frame([duplicated, duplicated, same_fact]))
        self.assertEqual(len(facts), 1)
        self.assertEqual(stats["duplicate_ids_dropped"], 1)
        self.assertEqual(stats["duplicate_facts_dropped"], 1)

    def test_rejects_unknown_locations_and_currency_mismatches(self):
        events = frame(
            [
                event("inbound_order_created", "2026-11-10T00:00:00Z", tags(currency="USD", unit_cost=99, inbound_order_id=1), "currency-mismatch"),
                event("inbound_order_created", "2026-11-10T00:00:00Z", tags(location=9, unit_cost=99, inbound_order_id=2), "unknown-location"),
            ]
        )
        result = process.transform_weekly_metrics(
            events, LOCATION_DIM.iloc[:1], WINDOW_START, WINDOW_END
        )
        self.assertEqual(result.stats["rejected_currency_mismatch"], 1)
        self.assertEqual(result.stats["rejected_unknown_location"], 1)
        self.assertEqual(result.stats["rows_rejected"], 2)
        self.assertEqual(result.weekly.total_purchase_cost.sum(), 0)

    def test_missing_unit_cost_is_zero_and_counted(self):
        events = frame(
            [event("inbound_order_created", "2026-11-10T00:00:00Z", tags(inbound_order_id=1))]
        )
        result = process.transform_weekly_metrics(
            events, LOCATION_DIM.iloc[:1], WINDOW_START, WINDOW_END
        )
        self.assertEqual(result.stats["events_without_cost"], 1)
        self.assertEqual(result.weekly.total_purchase_cost.sum(), 0)

    def test_utc_week_boundaries_and_window_helpers(self):
        sunday = datetime.fromisoformat("2026-11-15T23:59:59+00:00")
        monday = datetime.fromisoformat("2026-11-16T00:00:00+00:00")
        facts, _ = process.prepare_events(
            frame(
                [
                    event("stock_threshold_triggered", sunday, tags(), "sunday"),
                    event("stock_threshold_triggered", monday, tags(), "monday"),
                ]
            )
        )
        self.assertEqual(facts.set_index("id").loc["sunday", "week_start"], date(2026, 11, 9))
        self.assertEqual(facts.set_index("id").loc["monday", "week_start"], date(2026, 11, 16))
        self.assertEqual(process.compute_window(date(2026, 11, 18), 1), (date(2026, 11, 16), date(2026, 11, 23)))
        self.assertEqual(process.compute_window(date(2026, 11, 18), 4), (date(2026, 10, 26), date(2026, 11, 23)))
        self.assertEqual(process.week_starts(date(2026, 11, 9), date(2026, 11, 23)), [date(2026, 11, 9), date(2026, 11, 16)])
        self.assertEqual(process.monday_of(date(2026, 11, 18)), date(2026, 11, 16))
        with self.assertRaises(ValueError):
            process.compute_window(date(2026, 11, 18), 0)
        self.assertEqual(process.DEFAULT_LOOKBACK_WEEKS, 4)

    def test_timestamp_types_output_columns_and_determinism(self):
        rows = [
            event("inbound_order_created", "2026-11-10T00:00:00Z", tags(quantity=2, unit_cost=4, inbound_order_id=1), "one"),
            event("stock_threshold_triggered", "2026-11-11T00:00:00Z", tags(triggering_outbound_order_id=2), "two"),
        ]
        string_result = process.transform_weekly_metrics(
            frame(rows), LOCATION_DIM.iloc[:1], WINDOW_START, WINDOW_END
        )
        datetime_rows = [dict(row, timestamp=datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))) for row in rows]
        datetime_result = process.transform_weekly_metrics(
            frame(datetime_rows), LOCATION_DIM.iloc[:1], WINDOW_START, WINDOW_END
        )
        pd.testing.assert_frame_equal(string_result.weekly, datetime_result.weekly)
        pd.testing.assert_frame_equal(
            string_result.weekly,
            process.transform_weekly_metrics(frame(rows), LOCATION_DIM.iloc[:1], WINDOW_START, WINDOW_END).weekly,
        )
        self.assertEqual(list(string_result.weekly.columns), process.OUTPUT_COLUMNS)
        self.assertIsInstance(string_result.weekly.iloc[0].week_start, date)
        self.assertTrue(pd.api.types.is_integer_dtype(string_result.weekly.stockout_events_count))
        self.assertTrue(pd.api.types.is_integer_dtype(string_result.weekly.price_alert_events_count))

    def test_empty_input_is_full_zero_grid(self):
        result = process.transform_weekly_metrics(
            frame([]), LOCATION_DIM, WINDOW_START, WINDOW_END
        )
        self.assertEqual(len(result.weekly), len(LOCATION_DIM) * 2)
        self.assertEqual(result.stats["events_in"], 0)
        self.assertTrue(
            (result.weekly[["total_purchase_cost", "total_waste_cost", "waste_ratio"]] == 0)
            .all()
            .all()
        )

    def test_classifies_inserted_updated_and_unchanged_rows(self):
        base = {
            "location_id": "1",
            "country": "CO",
            "week_start": WINDOW_START,
            "total_purchase_cost": 10,
            "total_waste_cost": 2,
            "waste_ratio": 0.2,
            "stockout_events_count": 1,
            "price_alert_events_count": 0,
            "currency": "COP",
        }
        new_rows = pd.DataFrame(
            [
                base,
                {**base, "location_id": "2", "week_start": date(2026, 11, 16)},
                {**base, "location_id": "3", "total_purchase_cost": 20},
            ]
        )
        existing = pd.DataFrame(
            [
                base,
                {**base, "location_id": "3"},
            ]
        )
        to_write, counts = process.classify_rows(new_rows, existing)
        self.assertEqual(counts, {
            "rows_inserted": 1,
            "rows_updated": 1,
            "rows_unchanged": 1,
            "weeks_revised": [str(WINDOW_START)],
        })
        self.assertEqual({row["location_id"] for row in to_write}, {"2", "3"})

    def test_finds_silent_locations_and_reconciles_domain_counts(self):
        events = frame(
            [
                event("inbound_order_created", "2026-11-09T00:00:00Z", tags(inbound_order_id=1), "a"),
                event("stock_waste_registered", "2026-11-09T00:00:00Z", tags(outbound_order_id=2), "b"),
            ]
        )
        facts, _ = process.prepare_events(events)
        self.assertEqual(
            process.find_silent_locations(facts, WINDOW_START, WINDOW_END), ["1"]
        )
        entries = pd.DataFrame({"created_at": ["2026-11-09T00:00:00Z", "2026-11-10T00:00:00Z"]})
        waste = pd.DataFrame({"created_at": ["2026-11-09T00:00:00Z"]})
        differences = process.reconcile_with_domain(facts, entries, waste)
        self.assertEqual(differences, [{
            "kind": "inbound",
            "week_start": "2026-11-09",
            "telemetry_events": 1,
            "domain_rows": 2,
        }])


if __name__ == "__main__":
    unittest.main()
