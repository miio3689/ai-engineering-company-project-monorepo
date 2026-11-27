"""Tests of the sales forecast: 8-year / 2-year split, no data leakage, metrics.

The fixture below is an in-memory TEST series with the shape of
data/raw/brasaland_sales.csv (10 years, 2016-01 .. 2025-12). It is only used to
check the code; the model of the deliverable is trained on the provided CSV.

    uv run --group test python -m pytest tests/pipelines/test_sales_forecast.py
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from data.process import sales_forecast as sf
from scripts import train_sales_forecast


def sales_fixture(seed: int = 7) -> pd.DataFrame:
    """Test-only monthly series: yearly growth 3 %/7 %, January dip, December peak."""
    rng = np.random.default_rng(seed)
    months = pd.date_range("2016-01-01", "2025-12-01", freq="MS")
    level, rows = 1_500_000.0, []
    for year in range(2016, 2026):
        level *= 1.07 if year % 2 else 1.03
        for month in months[months.year == year]:
            season = {1: 0.85, 12: 1.25}.get(month.month, 1 + rng.uniform(-0.05, 0.05))
            revenue = level * season
            covers = int(revenue / 38)
            rows.append([month.strftime("%Y-%m-01"), revenue, covers, revenue / covers, "consolidated"])
    return pd.DataFrame(rows, columns=sf.DATA_COLUMNS)


@pytest.fixture
def full():
    return sf.clean_sales(sales_fixture())[0]


# ------------------------------------------------------------ 8 / 2 split

def test_split_uses_the_first_8_years_to_train_and_the_last_2_to_test(full):
    train, test = sf.split_train_test(full)

    assert len(train) == 96 and len(test) == 24
    assert train["month"].min() == pd.Timestamp("2016-01-01")
    assert train["month"].max() == pd.Timestamp("2023-12-01")
    assert test["month"].min() == pd.Timestamp("2024-01-01")
    assert test["month"].max() == pd.Timestamp("2025-12-01")
    assert sorted(train["month"].dt.year.unique()) == list(range(2016, 2024))
    assert sorted(test["month"].dt.year.unique()) == [2024, 2025]


def test_split_has_no_overlap_and_keeps_every_month(full):
    train, test = sf.split_train_test(full)

    assert set(train["month"]).isdisjoint(set(test["month"]))
    assert train["month"].max() < test["month"].min()  # strictly in time order
    together = pd.concat([train, test])["month"].sort_values().reset_index(drop=True)
    assert together.equals(full["month"].sort_values().reset_index(drop=True))


def test_split_rejects_a_dataset_that_is_not_10_complete_years(full):
    with pytest.raises(ValueError, match="120"):
        sf.split_train_test(full.iloc[:-1])
    with pytest.raises(ValueError):
        sf.split_train_test(full.drop(index=40).reset_index(drop=True))


# ----------------------------------------------------------- data leakage

def test_training_set_only_contains_training_months_and_targets(full):
    train, test = sf.split_train_test(full)
    X, y, months = sf.training_set(train)

    assert months.max() < test["month"].min()
    assert len(X) == len(y) == len(train) - sf.MIN_HISTORY
    expected = train.set_index("month").loc[months, sf.TARGET].to_numpy() / X["lag_12"].to_numpy()
    np.testing.assert_allclose(y.to_numpy(), expected)


def test_features_of_a_month_never_use_that_month_or_later_ones(full):
    revenue = full[sf.TARGET].to_numpy()
    month_index = 60
    month = full["month"][month_index]
    before = sf.feature_row(revenue[:month_index], month)

    changed = revenue.copy()
    changed[month_index:] *= 10  # tamper with the month itself and everything after it
    after = sf.feature_row(changed[:month_index], month)
    assert before == after
    assert before["lag_1"] == revenue[month_index - 1]
    assert before["lag_12"] == revenue[month_index - 12]


def test_test_years_never_reach_the_model_nor_the_forecast(full):
    train, test = sf.split_train_test(full)
    model = sf.train_model(train)
    forecast = sf.recursive_forecast(model, train, horizon=24)

    tampered = full.copy()
    tampered.loc[tampered["month"] >= "2024-01-01", sf.TARGET] *= 3
    train_2, _ = sf.split_train_test(tampered)
    forecast_2 = sf.recursive_forecast(sf.train_model(train_2), train_2, horizon=24)

    np.testing.assert_array_equal(forecast.point, forecast_2.point)
    assert list(forecast.months) == list(test["month"])


def test_scaler_is_fitted_on_training_rows_only(full):
    train, _ = sf.split_train_test(full)
    model = sf.train_model(train)
    X, _, _ = sf.training_set(train)
    scaler = model.named_steps["scale"].named_transformers_["usd"]
    np.testing.assert_allclose(scaler.mean_, X[sf.SCALED_FEATURES].mean().to_numpy())


# ------------------------------------------------------------ reproducibility

def test_fixed_seed_makes_the_experiment_reproducible(full):
    train, _ = sf.split_train_test(full)
    first = sf.recursive_forecast(sf.train_model(train), train)
    second = sf.recursive_forecast(sf.train_model(train), train)
    np.testing.assert_array_equal(first.point, second.point)
    np.testing.assert_array_equal(first.trajectories, second.trajectories)


def test_band_contains_the_forecast_and_widens_with_the_horizon(full):
    train, _ = sf.split_train_test(full)
    forecast = sf.recursive_forecast(sf.train_model(train), train)
    low, high = forecast.band(10, 90)
    assert np.all(low <= high)
    assert (high - low)[12:].mean() > (high - low)[:12].mean()


# ------------------------------------------------------------- cleaning

def test_cleaning_keeps_consolidated_rows_and_imputes_gaps_with_the_past():
    raw = sales_fixture()
    raw = pd.concat([raw, raw.head(3).assign(market="florida")], ignore_index=True)
    raw.loc[5, "revenue_usd"] = np.nan
    raw.loc[6, "revenue_usd"] = -10  # revenue must be positive
    raw = raw.drop(index=8)  # a missing month

    clean, report = sf.clean_sales(raw)

    assert len(clean) == 120 and clean[sf.TARGET].notna().all()
    assert report.rows_other_markets == 3 and report.months_added == 1
    assert clean.loc[5, sf.TARGET] == clean.loc[4, sf.TARGET]  # forward fill: only the past
    assert clean.loc[8, sf.TARGET] == clean.loc[7, sf.TARGET]


def test_loading_rejects_columns_that_differ_from_the_briefing(tmp_path):
    path = tmp_path / "sales.csv"
    sales_fixture().rename(columns={"revenue_usd": "revenue"}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="revenue_usd"):
        sf.load_sales(path)


# --------------------------------------------------------------- metrics

def test_gini_psi_and_k2_behave_as_documented():
    actual = np.array([10.0, 20, 30, 40, 50])
    assert sf.normalized_gini(actual, actual) == pytest.approx(1.0)
    assert sf.normalized_gini(actual, actual * 2 + 5) == pytest.approx(1.0)  # only the order matters
    assert sf.normalized_gini(actual, -actual) < 0

    rng = np.random.default_rng(0)
    same = rng.normal(size=2000)
    assert sf.psi(same[:1000], same[1000:]) < 0.05
    assert sf.psi(same[:1000], same[1000:] + 3) > 0.25


def test_training_script_writes_metrics_and_plot(tmp_path):
    data = tmp_path / "brasaland_sales.csv"
    sales_fixture().to_csv(data, index=False)
    assert train_sales_forecast.main(["--data", str(data), "--out", str(tmp_path / "eval")]) == 0

    report = json.loads((tmp_path / "eval" / "sales_forecast_metrics.json").read_text(encoding="utf-8"))
    for metric in ("mse_usd2", "psi_yoy_ratio_train_vs_test", "gini_normalized", "k2_score_r2", "mape_pct"):
        assert metric in report["metrics_test"]
    assert report["test"] == {"from": "2024-01-01", "to": "2025-12-01", "months": 24}
    assert (tmp_path / "eval" / "sales_forecast.png").stat().st_size > 10_000
