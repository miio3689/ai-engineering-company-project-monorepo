"""Monthly sales forecast of Brasaland (consolidated revenue_usd).

Pure functions: loading and cleaning the provided dataset, the 8-year / 2-year
split, causal features, the Random Forest model, the recursive 24-month
forecast with its variability band, and the evaluation metrics. Nothing here
touches the database. Dataset and patterns: BRIEFING "Modelo de pronóstico de
series de tiempo para predicción de ventas" (data/raw/brasaland_sales.csv).

Why Random Forest and not XGBoost
---------------------------------
* Data size: 120 monthly rows, of which 83 are usable training samples once 13
  months of history are needed for the lags. XGBoost's advantage shows with
  large data and careful tuning; on ~80 rows its boosting rounds overfit
  easily and its learning rate / depth / rounds would have to be tuned with
  only a handful of validation folds.
* Explainability: the stakeholders are Finance, the CEO and Operations. A
  forest is an average of many independent trees, easy to explain ("500
  experts each give a figure; we report the average and the spread"), and
  its feature importances are stable.
* Variability band for free: every tree gives its own forecast, so the spread
  across trees is the band the ticket asks for, without an extra model.
* Tuning time: Random Forest works well with near-default parameters; we fix
  a few conservative ones (min_samples_leaf, max_features) and the seed.

Trees cannot extrapolate: revenue grows 3-7 % a year, so the 2024-2025 levels
are above anything seen in training. The model therefore predicts the
year-over-year ratio revenue_t / revenue_(t-12), which is stationary (growth
times seasonal noise), and the forecast is ratio × revenue of 12 months
earlier. The 24 test months are forecast recursively from 2023-12: the model
never sees a test-year value, not even as a lag.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

RANDOM_STATE = 42
TRAIN_YEARS = 8
TEST_YEARS = 2
MIN_HISTORY = 13  # lag_12 and the year-over-year growth of the last month need 13 months
DATA_COLUMNS = ["month", "revenue_usd", "covers_served", "avg_ticket_usd", "market"]
TARGET = "revenue_usd"
MAIN_MARKET = "consolidated"

FEATURES = [
    "lag_1",
    "lag_2",
    "lag_3",
    "lag_12",
    "rolling_mean_3",
    "rolling_mean_12",
    "rolling_std_12",
    "lag_1_vs_rolling_12",
    "yoy_growth_lag_1",
    "yoy_growth_rolling_3",
    "month_sin",
    "month_cos",
    "is_january",
    "is_december",
]
# Features in USD: on a very different scale from ratios and flags.
SCALED_FEATURES = ["lag_1", "lag_2", "lag_3", "lag_12", "rolling_mean_3", "rolling_mean_12", "rolling_std_12"]


# ---------------------------------------------------------------- loading

@dataclass
class CleaningReport:
    rows_in: int
    rows_other_markets: int
    months_added: int  # missing months inserted as nulls
    values_imputed: dict[str, int] = field(default_factory=dict)


def load_sales(path: str | Path) -> tuple[pd.DataFrame, CleaningReport]:
    """Load data/raw/brasaland_sales.csv and return the clean consolidated series.

    * Validates the columns of the BRIEFING.
    * Keeps the market == "consolidated" rows (the model target).
    * Rebuilds a complete monthly index: a missing month becomes a null row.
    * Nulls, and revenue_usd <= 0 (revenue must be positive), are imputed with
      the previous month's value (forward fill): it only uses the past, so it
      cannot leak future information into the training rows.
    """
    raw = pd.read_csv(path)
    missing = set(DATA_COLUMNS) - set(raw.columns)
    if missing:
        raise ValueError(f"{path}: faltan las columnas {sorted(missing)} del BRIEFING.")
    return clean_sales(raw)


def clean_sales(raw: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
    market = raw["market"].astype(str).str.strip().str.lower()
    frame = raw.loc[market.eq(MAIN_MARKET), DATA_COLUMNS[:-1]].copy()
    report = CleaningReport(rows_in=len(raw), rows_other_markets=int((~market.eq(MAIN_MARKET)).sum()), months_added=0)
    if frame.empty:
        raise ValueError("El dataset no tiene filas con market = 'consolidated'.")

    frame["month"] = pd.to_datetime(frame["month"], errors="coerce").dt.to_period("M").dt.to_timestamp()
    frame = frame.dropna(subset=["month"]).drop_duplicates(subset="month", keep="last")
    for column in ("revenue_usd", "covers_served", "avg_ticket_usd"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame.loc[frame["revenue_usd"] <= 0, "revenue_usd"] = np.nan

    full_index = pd.date_range(frame["month"].min(), frame["month"].max(), freq="MS")
    report.months_added = len(full_index) - len(frame)
    frame = frame.set_index("month").reindex(full_index)
    frame.index.name = "month"

    for column in ("revenue_usd", "covers_served", "avg_ticket_usd"):
        nulls = int(frame[column].isna().sum())
        if nulls:
            report.values_imputed[column] = nulls
            frame[column] = frame[column].ffill().bfill()  # bfill only for a leading gap
    return frame.reset_index(), report


# ------------------------------------------------------------------ split

def split_train_test(
    frame: pd.DataFrame,
    train_years: int = TRAIN_YEARS,
    test_years: int = TEST_YEARS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """First `train_years` calendar years for training, the last `test_years` for testing.

    The split is by date and the two sets never overlap: every training month
    is strictly earlier than every test month.
    """
    months = pd.DatetimeIndex(frame["month"]).sort_values()
    expected = (train_years + test_years) * 12
    if len(months) != expected or months.has_duplicates:
        raise ValueError(f"Se esperaban {expected} meses consecutivos y hay {len(months)}.")
    if not months.equals(pd.date_range(months[0], periods=expected, freq="MS")):
        raise ValueError("Faltan meses en el rango del dataset.")
    test_start = months[0] + pd.DateOffset(years=train_years)
    ordered = frame.sort_values("month").reset_index(drop=True)
    train = ordered[ordered["month"] < test_start].reset_index(drop=True)
    test = ordered[ordered["month"] >= test_start].reset_index(drop=True)
    return train, test


# --------------------------------------------------------------- features

def feature_row(history: np.ndarray, month: pd.Timestamp) -> dict[str, float]:
    """Features of `month` computed ONLY from `history`, the revenue of the months before it.

    `history` must end with the month right before `month` (history[-1] is lag_1).
    """
    if len(history) < MIN_HISTORY:
        raise ValueError(f"Se necesitan {MIN_HISTORY} meses de historia y hay {len(history)}.")
    last_12 = history[-12:]
    lag_1, lag_13 = history[-1], history[-13]
    angle = 2 * np.pi * (month.month - 1) / 12
    return {
        "lag_1": lag_1,
        "lag_2": history[-2],
        "lag_3": history[-3],
        "lag_12": history[-12],
        "rolling_mean_3": history[-3:].mean(),
        "rolling_mean_12": last_12.mean(),
        "rolling_std_12": last_12.std(ddof=0),
        "lag_1_vs_rolling_12": lag_1 / last_12.mean(),
        "yoy_growth_lag_1": lag_1 / lag_13,
        "yoy_growth_rolling_3": history[-3:].sum() / history[-15:-12].sum() if len(history) >= 15 else lag_1 / lag_13,
        "month_sin": np.sin(angle),
        "month_cos": np.cos(angle),
        "is_january": float(month.month == 1),
        "is_december": float(month.month == 12),
    }


def training_set(train: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.DatetimeIndex]:
    """X, y and months of the training rows, built from the training years only.

    y is the year-over-year ratio revenue_t / revenue_(t-12) (see module docstring).
    """
    revenue = train[TARGET].to_numpy(dtype=float)
    months = pd.DatetimeIndex(train["month"])
    rows, targets = [], []
    for position in range(MIN_HISTORY, len(train)):
        history = revenue[:position]  # strictly before this month
        rows.append(feature_row(history, months[position]))
        targets.append(revenue[position] / history[-12])
    return pd.DataFrame(rows, columns=FEATURES), pd.Series(targets, name="yoy_ratio"), months[MIN_HISTORY:]


# ------------------------------------------------------------------ model

def build_model(n_estimators: int = 500, random_state: int = RANDOM_STATE) -> Pipeline:
    """StandardScaler (on the USD features) + Random Forest, with a fixed seed.

    Trees do not need scaling to split; the USD features are scaled anyway so
    no feature dominates by magnitude when comparing importances, and because
    the scaler is fitted inside the pipeline it only learns from training rows.
    """
    from sklearn.compose import ColumnTransformer

    scaler = ColumnTransformer(
        [("usd", StandardScaler(), SCALED_FEATURES)],
        remainder="passthrough",
        verbose_feature_names_out=False,
    )
    forest = RandomForestRegressor(
        n_estimators=n_estimators,
        min_samples_leaf=3,  # no leaf for a single month: avoids memorising noise
        max_features=0.6,
        random_state=random_state,
        n_jobs=1,  # parallel averaging changes the float summation order: keep it bit-for-bit reproducible
    )
    return Pipeline([("scale", scaler), ("forest", forest)]).set_output(transform="pandas")


def train_model(train: pd.DataFrame, random_state: int = RANDOM_STATE) -> Pipeline:
    X, y, _ = training_set(train)
    return build_model(random_state=random_state).fit(X, y)


@dataclass
class Forecast:
    months: pd.DatetimeIndex
    point: np.ndarray  # forest recursion
    trajectories: np.ndarray  # (n_trees, horizon): one recursive path per tree

    def band(self, lower: float, upper: float) -> tuple[np.ndarray, np.ndarray]:
        return (
            np.percentile(self.trajectories, lower, axis=0),
            np.percentile(self.trajectories, upper, axis=0),
        )


def recursive_forecast(model: Pipeline, train: pd.DataFrame, horizon: int = TEST_YEARS * 12) -> Forecast:
    """Forecast `horizon` months after the last training month, using ONLY `train`.

    Each predicted month is appended to the history and feeds the lags of the
    next one, as it would in production. Besides the forest's forecast, every
    tree runs its own recursion: the spread of those paths is the variability
    band, and it widens with the horizon because errors accumulate.
    """
    start = pd.Timestamp(train["month"].max()) + pd.DateOffset(months=1)
    months = pd.date_range(start, periods=horizon, freq="MS")
    base = train[TARGET].to_numpy(dtype=float)
    scaler = model.named_steps["scale"]
    trees = model.named_steps["forest"].estimators_

    point_history = list(base)
    tree_histories = np.tile(base, (len(trees), 1)).tolist()
    point = np.empty(horizon)
    trajectories = np.empty((len(trees), horizon))

    for step, month in enumerate(months):
        X = scaler.transform(pd.DataFrame([feature_row(np.asarray(point_history), month)], columns=FEATURES))
        point[step] = model.named_steps["forest"].predict(X)[0] * point_history[-12]
        point_history.append(point[step])

        tree_rows = pd.DataFrame(
            [feature_row(np.asarray(history), month) for history in tree_histories], columns=FEATURES
        )
        scaled = scaler.transform(tree_rows).to_numpy()
        for index, tree in enumerate(trees):
            value = tree.predict(scaled[index : index + 1])[0] * tree_histories[index][-12]
            trajectories[index, step] = value
            tree_histories[index].append(value)
    return Forecast(months=months, point=point, trajectories=trajectories)


# ---------------------------------------------------------------- metrics

def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 5) -> float:
    """Population Stability Index of `actual` against `expected`.

    Bins are the quantiles of `expected` (training); a small epsilon avoids
    log(0) in empty bins. Rule of thumb: < 0.10 stable, 0.10-0.25 moderate
    change, > 0.25 significant change.
    """
    expected = np.asarray(expected, dtype=float)
    actual = np.asarray(actual, dtype=float)
    edges = np.unique(np.quantile(expected, np.linspace(0, 1, bins + 1)))
    edges[0], edges[-1] = -np.inf, np.inf
    expected_share = np.histogram(expected, edges)[0] / len(expected)
    actual_share = np.histogram(actual, edges)[0] / len(actual)
    epsilon = 1e-4
    expected_share = np.clip(expected_share, epsilon, None)
    actual_share = np.clip(actual_share, epsilon, None)
    return float(np.sum((actual_share - expected_share) * np.log(actual_share / expected_share)))


def _gini(actual: np.ndarray, predicted: np.ndarray) -> float:
    order = np.lexsort((np.arange(len(actual)), -np.asarray(predicted)))
    sorted_actual = np.asarray(actual, dtype=float)[order]
    cumulative = np.cumsum(sorted_actual) / sorted_actual.sum()
    return float(cumulative.sum() / len(actual) - (len(actual) + 1) / (2 * len(actual)))


def normalized_gini(actual: np.ndarray, predicted: np.ndarray) -> float:
    """How well the forecast ORDERS the months, from 1 (perfect order) to ~0 (random).

    Gini of the actual values sorted by the prediction, divided by the Gini of
    the perfect order: it ignores the size of the error and only checks that
    the months the model expects to be weak are the weak ones.
    """
    return _gini(actual, predicted) / _gini(actual, actual)


def evaluate(
    actual: np.ndarray,
    forecast: Forecast,
    train_target: np.ndarray,
    test_target: np.ndarray,
    train_revenue: np.ndarray,
    test_revenue: np.ndarray,
) -> dict[str, Any]:
    """The four metrics of the ticket, on the TEST years, plus the ones Finance reads."""
    actual = np.asarray(actual, dtype=float)
    point = forecast.point
    low_80, high_80 = forecast.band(10, 90)
    low_95, high_95 = forecast.band(2.5, 97.5)
    mse = mean_squared_error(actual, point)
    return {
        "mse_usd2": float(mse),
        "rmse_usd": float(np.sqrt(mse)),
        "mae_usd": float(mean_absolute_error(actual, point)),
        "mape_pct": float(np.mean(np.abs(actual - point) / actual) * 100),
        "max_abs_pct_error": float(np.max(np.abs(actual - point) / actual) * 100),
        "k2_score_r2": float(r2_score(actual, point)),
        "gini_normalized": normalized_gini(actual, point),
        "psi_yoy_ratio_train_vs_test": psi(train_target, test_target),
        "psi_revenue_train_vs_test": psi(train_revenue, test_revenue),
        "psi_forecast_vs_actual": psi(actual, point),
        "band_80_coverage_pct": float(np.mean((actual >= low_80) & (actual <= high_80)) * 100),
        "band_95_coverage_pct": float(np.mean((actual >= low_95) & (actual <= high_95)) * 100),
    }


def seasonal_naive_forecast(train: pd.DataFrame, horizon: int = TEST_YEARS * 12) -> np.ndarray:
    """Baseline: same month of the last training year × the mean yearly growth of training.

    The reference the model has to beat: if it does not, it adds nothing.
    """
    revenue = train[TARGET].to_numpy(dtype=float)
    growth = float(np.mean(revenue[12:] / revenue[:-12]))
    last_year = revenue[-12:]
    return np.array([last_year[step % 12] * growth ** (step // 12 + 1) for step in range(horizon)])


def one_step_ahead_forecast(model: Pipeline, train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    """Next-month forecast as Finance would use it: each month is predicted at the
    end of the previous one, with the ACTUAL past months as lags.

    The model is the one trained on the training years only; the test months
    are never used to fit it, only as already-known history once they happened.
    """
    revenue = np.concatenate([train[TARGET].to_numpy(dtype=float), test[TARGET].to_numpy(dtype=float)])
    months = pd.DatetimeIndex(test["month"])
    start = len(train)
    rows = [feature_row(revenue[: start + step], month) for step, month in enumerate(months)]
    ratios = model.predict(pd.DataFrame(rows, columns=FEATURES))
    return ratios * np.array([revenue[start + step - 12] for step in range(len(months))])


def yoy_ratios(frame: pd.DataFrame) -> np.ndarray:
    """revenue_t / revenue_(t-12) of every month that has 12 months before it in `frame`."""
    revenue = frame[TARGET].to_numpy(dtype=float)
    return revenue[12:] / revenue[:-12]
