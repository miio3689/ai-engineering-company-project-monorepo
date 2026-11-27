"""Formal evaluation of the sales forecast (data/process/sales_forecast.py).

Pure functions for the evaluation ticket: time-ordered cross-validation on the
TRAINING years only (2016-2023), a learning curve, MAE / RMSE on training and
validation, and the comparison of candidate corrective actions. The 2024-2025
test years are never used here: they stay untouched for the final check of
the forecast milestone.

Leak-free folds
---------------
* Folds come from sklearn's TimeSeriesSplit (no shuffling): each validation
  window is the 12 samples right after its training window, and every
  training index is earlier than every validation index.
* Features are rebuilt INSIDE each fold from the revenue series truncated at
  the end of that fold's validation window (``fold_features``). A lag or a
  rolling statistic of a fold therefore cannot see a month after the fold,
  and the training rows of a fold cannot see its validation months (all
  features only look backwards: see ``sales_forecast.feature_row``).
* The scaler lives inside the model pipeline, so it is fitted on the fold's
  training rows only.

Validation is one step ahead (each month predicted with the actual months
before it), the standard set-up to diagnose bias and variance. The recursive
12-month forecast of each validation window is also reported, because the
deliverable forecasts 24 months recursively and errors accumulate there.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline

from data.process import sales_forecast as sf

CV_SPLITS = 5
CV_VALIDATION_MONTHS = 12  # one full seasonal cycle per validation window
# Up to 47 samples: the training window of the last 3 folds (validation 2021, 2022, 2023).
LEARNING_CURVE_SIZES = (12, 18, 24, 30, 36, 42, 47)
# Regularisation candidates (min_samples_leaf of the forest) compared by CV.
LEAF_CANDIDATES = (3, 6, 10, 15, 20, 25, 30)
PROPOSED_MIN_SAMPLES_LEAF = 20


def model_with_leaf(min_samples_leaf: int) -> ModelFactory:
    """Factory of the forecast model with another min_samples_leaf (everything else equal)."""

    def make() -> Pipeline:
        model = sf.build_model()
        model.named_steps["forest"].set_params(min_samples_leaf=min_samples_leaf)
        return model

    return make

ModelFactory = Callable[[], Pipeline]


# ------------------------------------------------------------------ folds

def time_series_folds(
    n_samples: int, n_splits: int = CV_SPLITS, validation_months: int = CV_VALIDATION_MONTHS
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Expanding-window folds over the training samples, in chronological order."""
    splitter = TimeSeriesSplit(n_splits=n_splits, test_size=validation_months)
    return [(train_idx, val_idx) for train_idx, val_idx in splitter.split(np.arange(n_samples))]


def fold_features(train: pd.DataFrame, end_sample: int) -> tuple[pd.DataFrame, pd.Series, pd.DatetimeIndex, np.ndarray]:
    """X, y, months and lag_12 of the samples [0, end_sample), rebuilt from the
    revenue series truncated right after sample `end_sample - 1`.

    Sample i is the month at position MIN_HISTORY + i of `train`. Nothing after
    the fold's last month exists when its features are computed.
    """
    truncated = train.iloc[: sf.MIN_HISTORY + end_sample].reset_index(drop=True)
    X, y, months = sf.training_set(truncated)
    return X, y, months, X["lag_12"].to_numpy()


def _errors(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    error = np.asarray(predicted, dtype=float) - np.asarray(actual, dtype=float)
    return {
        "mae_usd": float(np.mean(np.abs(error))),
        "rmse_usd": float(np.sqrt(np.mean(error**2))),
        "mape_pct": float(np.mean(np.abs(error) / actual) * 100),
        "bias_pct": float(np.mean(error / actual) * 100),
    }


def _fit_and_score(
    factory: ModelFactory, train: pd.DataFrame, fit_idx: np.ndarray, val_idx: np.ndarray, recursive: bool
) -> dict:
    X, y, months, lag_12 = fold_features(train, int(val_idx.max()) + 1)
    model = factory().fit(X.iloc[fit_idx], y.iloc[fit_idx])
    revenue = y.to_numpy() * lag_12  # actual revenue of every sample

    result = {
        "train": _errors(revenue[fit_idx], model.predict(X.iloc[fit_idx]) * lag_12[fit_idx]),
        "validation": _errors(revenue[val_idx], model.predict(X.iloc[val_idx]) * lag_12[val_idx]),
        "train_samples": len(fit_idx),
        "train_months": [str(months[fit_idx[0]].date()), str(months[fit_idx[-1]].date())],
        "validation_months": [str(months[val_idx[0]].date()), str(months[val_idx[-1]].date())],
    }
    if recursive:
        # Recursive forecast of the validation window from the month before it,
        # with the history known at that point only (the series up to it).
        history = train[sf.TARGET].to_numpy(dtype=float)[: sf.MIN_HISTORY + int(val_idx[0])]
        point = recursive_point_forecast(model, history, months[val_idx])
        result["validation_recursive"] = _errors(revenue[val_idx], point)
    return result


def recursive_point_forecast(model: Pipeline, history: np.ndarray, months: pd.DatetimeIndex) -> np.ndarray:
    """Point forecast of `months`, each predicted month feeding the next one's lags.

    Same recursion as ``sales_forecast.recursive_forecast`` without the per-tree
    band (not needed to score a fold, and 500 times cheaper).
    """
    path = list(np.asarray(history, dtype=float))
    point = np.empty(len(months))
    for step, month in enumerate(months):
        row = pd.DataFrame([sf.feature_row(np.asarray(path), month)], columns=sf.FEATURES)
        point[step] = model.predict(row)[0] * path[-12]
        path.append(point[step])
    return point


def cross_validate(
    train: pd.DataFrame,
    factory: ModelFactory = sf.build_model,
    n_splits: int = CV_SPLITS,
    validation_months: int = CV_VALIDATION_MONTHS,
    recursive: bool = True,
) -> dict:
    """Time-ordered cross-validation on the training years; mean ± std across folds."""
    n_samples = len(train) - sf.MIN_HISTORY
    folds = [
        _fit_and_score(factory, train, fit_idx, val_idx, recursive)
        for fit_idx, val_idx in time_series_folds(n_samples, n_splits, validation_months)
    ]
    return {"folds": folds, "summary": summarize(folds)}


def seasonal_naive_cv(
    train: pd.DataFrame, n_splits: int = CV_SPLITS, validation_months: int = CV_VALIDATION_MONTHS
) -> dict:
    """Reference on the same folds: same month of last year × mean yearly growth so far.

    One step ahead like the model's validation (last year's month is known), and
    the growth is computed only with the months before the validation window.
    """
    revenue = train[sf.TARGET].to_numpy(dtype=float)
    folds = []
    for _, val_idx in time_series_folds(len(train) - sf.MIN_HISTORY, n_splits, validation_months):
        positions = sf.MIN_HISTORY + val_idx
        history = revenue[: positions[0]]
        growth = float(np.mean(history[12:] / history[:-12]))
        folds.append({"validation": _errors(revenue[positions], revenue[positions - 12] * growth)})
    return {"folds": folds, "summary": summarize(folds)}


def summarize(folds: list[dict]) -> dict:
    summary = {}
    for part in ("train", "validation", "validation_recursive"):
        if part not in folds[0]:
            continue
        summary[part] = {
            metric: {
                "mean": float(np.mean([fold[part][metric] for fold in folds])),
                "std": float(np.std([fold[part][metric] for fold in folds], ddof=1)),
            }
            for metric in folds[0][part]
        }
    return summary


# --------------------------------------------------------- learning curve

@dataclass
class LearningCurve:
    sizes: list[int]
    train_rmse: list[tuple[float, float]]  # (mean, std) across folds
    validation_rmse: list[tuple[float, float]]
    train_mae: list[tuple[float, float]]
    validation_mae: list[tuple[float, float]]
    folds_per_size: list[int]


def learning_curve(
    train: pd.DataFrame,
    factory: ModelFactory = sf.build_model,
    sizes: tuple[int, ...] = LEARNING_CURVE_SIZES,
    n_splits: int = CV_SPLITS,
    validation_months: int = CV_VALIDATION_MONTHS,
) -> LearningCurve:
    """Training and validation error as the training window grows.

    Only the CV folds whose training window holds the largest size are used,
    so EVERY size is scored on the same validation windows and the curve only
    reflects the amount of training data. For each size n the model is fitted
    on the n samples RIGHT BEFORE the fold's validation window (same horizon
    for every size); averaging over folds smooths the effect of one year.
    """
    n_samples = len(train) - sf.MIN_HISTORY
    folds = [
        (fit_idx, val_idx)
        for fit_idx, val_idx in time_series_folds(n_samples, n_splits, validation_months)
        if len(fit_idx) >= max(sizes)
    ]
    if not folds:
        raise ValueError(f"Ningún fold tiene {max(sizes)} muestras de entrenamiento.")
    curve = LearningCurve([], [], [], [], [], [])
    for size in sizes:
        scores = [_fit_and_score(factory, train, fit_idx[-size:], val_idx, recursive=False) for fit_idx, val_idx in folds]
        curve.sizes.append(size)
        curve.folds_per_size.append(len(scores))
        for attribute, part, metric in (
            ("train_rmse", "train", "rmse_usd"),
            ("validation_rmse", "validation", "rmse_usd"),
            ("train_mae", "train", "mae_usd"),
            ("validation_mae", "validation", "mae_usd"),
        ):
            values = [score[part][metric] for score in scores]
            getattr(curve, attribute).append((float(np.mean(values)), float(np.std(values))))
    return curve
