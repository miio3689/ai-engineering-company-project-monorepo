"""Train and evaluate the Brasaland monthly sales forecast (Random Forest).

Loads data/raw/brasaland_sales.csv (row market = "consolidated"), trains on the
first 8 years (2016-2023), forecasts the 2 most recent years (2024-2025)
recursively without ever seeing them, and writes to data/eval/:

* sales_forecast.png           forecast, 80 % and 95 % variability bands and actual values
* sales_forecast_metrics.json  MSE, PSI, Gini, K2 Score (R2), MAPE... on the test years

    uv run python scripts/train_sales_forecast.py
    uv run python scripts/train_sales_forecast.py --data data/raw/brasaland_sales.csv

The algorithm choice and the meaning of each metric are documented in
data/process/sales_forecast.py and docs/sales-forecast/README.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from data.process import sales_forecast as sf  # noqa: E402

DEFAULT_DATA = REPOSITORY_ROOT / "data" / "raw" / "brasaland_sales.csv"
DEFAULT_OUT = REPOSITORY_ROOT / "data" / "eval"


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return str(path)


def plot_forecast(full: pd.DataFrame, test: pd.DataFrame, forecast: sf.Forecast, metrics: dict, path: Path) -> None:
    low_80, high_80 = forecast.band(10, 90)
    low_95, high_95 = forecast.band(2.5, 97.5)
    history = full[full["month"] >= forecast.months[0] - pd.DateOffset(years=3)]

    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.plot(history["month"], history[sf.TARGET], color="#9ca3af", lw=1.5, label="Real (entrenamiento, 2021-2023)")
    ax.fill_between(forecast.months, low_95, high_95, color="#fdba74", alpha=0.35, label="Rango de variabilidad 95 %")
    ax.fill_between(forecast.months, low_80, high_80, color="#f97316", alpha=0.35, label="Rango de variabilidad 80 %")
    ax.plot(forecast.months, forecast.point, color="#c2410c", lw=2.2, label="Predicción (Random Forest)")
    ax.plot(test["month"], test[sf.TARGET], color="#111827", lw=2, marker="o", ms=3.5, label="Real (prueba, 2024-2025)")
    ax.axvline(forecast.months[0], color="#374151", ls="--", lw=1)
    ax.text(forecast.months[0], ax.get_ylim()[1], "  inicio de la prueba", va="top", fontsize=9, color="#374151")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"${value / 1e6:,.1f} M"))
    ax.set_ylabel("Ventas mensuales consolidadas (USD)")
    ax.set_title(
        "Brasaland: predicción de ventas 2024-2025 (sin ver esos años) frente a las ventas reales\n"
        f"Error porcentual medio (MAPE) {metrics['mape_pct']:.1f} %  ·  K2 Score (R²) {metrics['k2_score_r2']:.2f}"
        f"  ·  {metrics['band_80_coverage_pct']:.0f} % de los meses dentro del rango del 80 %",
        fontsize=11,
    )
    ax.grid(alpha=0.25)
    ax.legend(loc="upper left", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Modelo de predicción de ventas de Brasaland.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    full, cleaning = sf.load_sales(args.data)
    train, test = sf.split_train_test(full)
    model = sf.train_model(train)
    forecast = sf.recursive_forecast(model, train, horizon=len(test))

    full_ratios = pd.Series(sf.yoy_ratios(full), index=full["month"].iloc[12:].to_numpy())
    metrics = sf.evaluate(
        actual=test[sf.TARGET].to_numpy(),
        forecast=forecast,
        train_target=full_ratios[full_ratios.index < test["month"].min()].to_numpy(),
        test_target=full_ratios[full_ratios.index >= test["month"].min()].to_numpy(),
        train_revenue=train[sf.TARGET].to_numpy(),
        test_revenue=test[sf.TARGET].to_numpy(),
    )

    # In-sample fit, only to show the gap: a model that memorised the past would
    # have a near-zero training error and a much larger test error.
    X_train, y_train, _ = sf.training_set(train)
    fitted = model.predict(X_train) * X_train["lag_12"].to_numpy()
    actual_train = y_train.to_numpy() * X_train["lag_12"].to_numpy()
    metrics["train_in_sample_mape_pct"] = float(np.mean(np.abs(actual_train - fitted) / actual_train) * 100)

    # References to judge the result honestly (they do not change the model).
    actual = test[sf.TARGET].to_numpy()

    def mape(predicted: np.ndarray) -> float:
        return float(np.mean(np.abs(actual - predicted) / actual) * 100)

    metrics["bias_pct"] = float(np.mean(forecast.point / actual - 1) * 100)
    metrics["mape_year_1_pct"] = mape(np.r_[forecast.point[:12], actual[12:]]) * 2
    metrics["mape_year_2_pct"] = mape(np.r_[actual[:12], forecast.point[12:]]) * 2
    metrics["baseline_seasonal_naive_mape_pct"] = mape(sf.seasonal_naive_forecast(train, len(test)))
    metrics["one_step_ahead_mape_pct"] = mape(sf.one_step_ahead_forecast(model, train, test))

    importances = pd.Series(
        model.named_steps["forest"].feature_importances_, index=model.named_steps["scale"].get_feature_names_out()
    ).sort_values(ascending=False)
    low_80, high_80 = forecast.band(10, 90)
    report = {
        "dataset": _display_path(args.data),
        "cleaning": cleaning.__dict__,
        "train": {"from": str(train["month"].min().date()), "to": str(train["month"].max().date()), "months": len(train), "samples": len(X_train)},
        "test": {"from": str(test["month"].min().date()), "to": str(test["month"].max().date()), "months": len(test)},
        "model": "RandomForestRegressor(n_estimators=500, min_samples_leaf=3, max_features=0.6, random_state=42)",
        "metrics_test": metrics,
        "feature_importance": importances.round(4).to_dict(),
        "forecast": [
            {"month": str(month.date()), "actual": float(actual), "forecast": float(point), "p10": float(low), "p90": float(high)}
            for month, actual, point, low, high in zip(forecast.months, test[sf.TARGET], forecast.point, low_80, high_80)
        ],
    }

    args.out.mkdir(parents=True, exist_ok=True)
    plot_forecast(full, test, forecast, metrics, args.out / "sales_forecast.png")
    (args.out / "sales_forecast_metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Train {report['train']['from']} .. {report['train']['to']} ({len(train)} meses)  |  "
          f"Test {report['test']['from']} .. {report['test']['to']} ({len(test)} meses)")
    for name, value in metrics.items():
        print(f"  {name:32s} {value:,.4f}")
    print(f"Gráfica y métricas en {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
