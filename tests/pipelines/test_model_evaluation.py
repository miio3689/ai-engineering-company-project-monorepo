"""Tests of the formal evaluation: temporal CV keeps the chronological order and
does not leak lag / rolling features across fold boundaries.

Uses the in-memory TEST series of test_sales_forecast.py (same shape as
data/raw/brasaland_sales.csv); the evaluation of the deliverable runs on the CSV.

    uv run --group test python -m pytest tests/pipelines/test_model_evaluation.py
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from test_sales_forecast import sales_fixture

from data.process import model_evaluation as me
from data.process import sales_forecast as sf
from scripts import evaluate_sales_forecast


@pytest.fixture
def train():
    return sf.split_train_test(sf.clean_sales(sales_fixture())[0])[0]


@pytest.fixture
def n_samples(train):
    return len(train) - sf.MIN_HISTORY


# ------------------------------------------------------- chronological order

def test_folds_preserve_the_chronological_order(n_samples):
    folds = me.time_series_folds(n_samples)
    assert len(folds) >= 5

    previous_validation_end = -1
    for fit_idx, val_idx in folds:
        # Inside each fold nothing is shuffled: contiguous, increasing indices.
        assert np.array_equal(fit_idx, np.arange(fit_idx[0], fit_idx[-1] + 1))
        assert np.array_equal(val_idx, np.arange(val_idx[0], val_idx[-1] + 1))
        # Training is strictly before validation.
        assert fit_idx.max() < val_idx.min()
        assert len(val_idx) == me.CV_VALIDATION_MONTHS
        # No index of a later fold appears before one of an earlier fold.
        assert val_idx.min() > previous_validation_end
        previous_validation_end = val_idx.max()

    # Expanding window: each fold trains on everything before its validation window.
    for fit_idx, val_idx in folds:
        assert fit_idx[0] == 0 and fit_idx[-1] == val_idx[0] - 1
    assert folds[-1][1][-1] == n_samples - 1


def test_fold_months_are_in_time_order(train):
    folds = me.cross_validate(train, recursive=False)["folds"]
    previous_end = pd.Timestamp.min
    for fold in folds:
        train_from, train_to = map(pd.Timestamp, fold["train_months"])
        val_from, val_to = map(pd.Timestamp, fold["validation_months"])
        assert train_from <= train_to < val_from <= val_to
        assert val_from == train_to + pd.DateOffset(months=1)
        assert val_from > previous_end
        previous_end = val_to
    assert previous_end <= train["month"].max()


# ------------------------------------------------- no leakage between folds

def test_fold_features_ignore_every_month_after_the_fold(train, n_samples):
    fit_idx, val_idx = me.time_series_folds(n_samples)[1]
    end = int(val_idx.max()) + 1
    X, y, months, _ = me.fold_features(train, end)

    tampered = train.copy()
    tampered.loc[sf.MIN_HISTORY + end :, sf.TARGET] *= 10  # months after the fold
    X_2, y_2, months_2, _ = me.fold_features(tampered, end)

    pd.testing.assert_frame_equal(X, X_2)
    pd.testing.assert_series_equal(y, y_2)
    assert months.max() < tampered["month"].iloc[sf.MIN_HISTORY + end]


def test_training_rows_of_a_fold_never_see_its_validation_months(train, n_samples):
    fit_idx, val_idx = me.time_series_folds(n_samples)[2]
    end = int(val_idx.max()) + 1
    X, y, _, _ = me.fold_features(train, end)

    tampered = train.copy()
    first_validation_position = sf.MIN_HISTORY + int(val_idx[0])
    tampered.loc[first_validation_position:, sf.TARGET] *= 10  # validation months and later
    X_2, y_2, _, _ = me.fold_features(tampered, end)

    pd.testing.assert_frame_equal(X.iloc[fit_idx], X_2.iloc[fit_idx])
    pd.testing.assert_series_equal(y.iloc[fit_idx], y_2.iloc[fit_idx])


def test_fold_features_match_the_features_of_the_whole_training_series(train, n_samples):
    """Rebuilding per fold gives the same rows as building once: lags only look back."""
    X_all, y_all, _ = sf.training_set(train)
    _, val_idx = me.time_series_folds(n_samples)[0]
    X, y, _, _ = me.fold_features(train, int(val_idx.max()) + 1)
    pd.testing.assert_frame_equal(X, X_all.iloc[: len(X)])
    pd.testing.assert_series_equal(y, y_all.iloc[: len(y)])


def test_scores_of_a_fold_do_not_change_when_later_months_change(train):
    first = me.cross_validate(train, recursive=False)["folds"][0]
    tampered = train.copy()
    last_position = sf.MIN_HISTORY + me.time_series_folds(len(train) - sf.MIN_HISTORY)[0][1][-1]
    tampered.loc[last_position + 1 :, sf.TARGET] *= 3
    assert me.cross_validate(tampered, recursive=False)["folds"][0] == first


# ------------------------------------------------------------ summary / curve

def test_cv_reports_mean_and_std_of_mae_and_rmse(train):
    result = me.cross_validate(train)
    for part in ("train", "validation", "validation_recursive"):
        for metric in ("mae_usd", "rmse_usd"):
            values = [fold[part][metric] for fold in result["folds"]]
            assert result["summary"][part][metric]["mean"] == pytest.approx(np.mean(values))
            assert result["summary"][part][metric]["std"] == pytest.approx(np.std(values, ddof=1))


def test_learning_curve_scores_every_size_on_the_same_folds(train):
    curve = me.learning_curve(train, sizes=(12, 24, 36))
    assert curve.sizes == [12, 24, 36]
    assert len(set(curve.folds_per_size)) == 1 and curve.folds_per_size[0] >= 2
    for values in (curve.train_rmse, curve.validation_rmse, curve.train_mae, curve.validation_mae):
        assert len(values) == 3 and all(mean > 0 and std >= 0 for mean, std in values)


def test_evaluation_script_writes_curves_and_metrics(tmp_path, monkeypatch):
    monkeypatch.setattr(me, "LEAF_CANDIDATES", (3, me.PROPOSED_MIN_SAMPLES_LEAF))
    data = tmp_path / "brasaland_sales.csv"
    sales_fixture().to_csv(data, index=False)
    out = tmp_path / "eval"
    assert evaluate_sales_forecast.main(["--data", str(data), "--out", str(out)]) == 0

    report = json.loads((out / "evaluation_metrics.json").read_text(encoding="utf-8"))
    assert len(report["cross_validation"]["folds"]) == me.CV_SPLITS
    assert report["train_months"] == ["2016-01-01", "2023-12-01"]  # the test years are never used
    for name in ("learning_curve.png", "regularization_curve.png"):
        assert (out / name).stat().st_size > 10_000
