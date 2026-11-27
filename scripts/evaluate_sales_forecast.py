"""Formal evaluation of the Brasaland sales forecast (Random Forest).

Works ONLY on the training years (2016-2023) of data/raw/brasaland_sales.csv:
the 2024-2025 test years stay untouched. Writes to data/eval/:

* learning_curve.png               train vs validation RMSE and MAE as the training window grows
* regularization_curve.png         validation error by min_samples_leaf (the corrective action)
* evaluation_metrics.json          5-fold temporal CV (mean ± std), learning curve, candidates

    uv run python scripts/evaluate_sales_forecast.py

The diagnosis and the corrective action are written in data/eval/evaluation_report.md.
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
from matplotlib.ticker import FuncFormatter  # noqa: E402

from data.process import model_evaluation as me  # noqa: E402
from data.process import sales_forecast as sf  # noqa: E402

DEFAULT_DATA = REPOSITORY_ROOT / "data" / "raw" / "brasaland_sales.csv"
DEFAULT_OUT = REPOSITORY_ROOT / "data" / "eval"
TRAIN_COLOR, VALIDATION_COLOR, NAIVE_COLOR = "#2a78d6", "#eb6834", "#6b6a63"
USD_K = FuncFormatter(lambda value, _: f"${value / 1e3:,.0f} k")


def _band(ax, sizes, values, color, style, label):
    mean = np.array([m for m, _ in values])
    std = np.array([s for _, s in values])
    ax.plot(sizes, mean, color=color, ls=style, lw=2, marker="o", ms=5, label=label)
    if style == "-":
        ax.fill_between(sizes, mean - std, mean + std, color=color, alpha=0.12, lw=0)


def plot_learning_curve(current: me.LearningCurve, proposed: me.LearningCurve, path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharex=True)
    for ax, metric in zip(axes, ("rmse", "mae")):
        _band(ax, current.sizes, getattr(current, f"train_{metric}"), TRAIN_COLOR, "-", "Entrenamiento (modelo actual, hoja mín. 3)")
        _band(ax, current.sizes, getattr(current, f"validation_{metric}"), VALIDATION_COLOR, "-", "Validación (modelo actual, hoja mín. 3)")
        _band(ax, proposed.sizes, getattr(proposed, f"train_{metric}"), TRAIN_COLOR, "--", f"Entrenamiento (propuesto, hoja mín. {me.PROPOSED_MIN_SAMPLES_LEAF})")
        _band(ax, proposed.sizes, getattr(proposed, f"validation_{metric}"), VALIDATION_COLOR, "--", f"Validación (propuesto, hoja mín. {me.PROPOSED_MIN_SAMPLES_LEAF})")
        ax.set_title(f"{metric.upper()} mensual (USD)", fontsize=11)
        ax.set_xlabel("Meses de entrenamiento (ventana justo antes de la validación)")
        ax.yaxis.set_major_formatter(USD_K)
        ax.set_ylim(bottom=0)
        ax.grid(alpha=0.25)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    axes[0].legend(loc="lower right", fontsize=8.5)
    fig.suptitle(
        "Curva de aprendizaje del pronóstico de ventas de Brasaland (validación un mes vista; folds 2021, 2022 y 2023)\n"
        "Banda: ± 1 desviación estándar entre folds",
        fontsize=11,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_regularization(candidates: dict[int, dict], naive: dict, path: Path) -> None:
    leaves = sorted(candidates)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for part, color, label in (("train", TRAIN_COLOR, "Entrenamiento"), ("validation", VALIDATION_COLOR, "Validación (5 folds)")):
        mean = np.array([candidates[leaf][part]["rmse_usd"]["mean"] for leaf in leaves])
        std = np.array([candidates[leaf][part]["rmse_usd"]["std"] for leaf in leaves])
        ax.plot(leaves, mean, color=color, lw=2, marker="o", ms=5, label=label)
        ax.fill_between(leaves, mean - std, mean + std, color=color, alpha=0.12, lw=0)
    ax.axhline(naive["validation"]["rmse_usd"]["mean"], color=NAIVE_COLOR, ls=":", lw=1.5, label="Línea base estacional (validación)")
    ax.axvline(me.PROPOSED_MIN_SAMPLES_LEAF, color=NAIVE_COLOR, ls="--", lw=1)
    ax.text(me.PROPOSED_MIN_SAMPLES_LEAF, ax.get_ylim()[1] * 0.97, "  propuesto", va="top", fontsize=9, color=NAIVE_COLOR)
    ax.set_xlabel("min_samples_leaf (meses mínimos por hoja)")
    ax.set_ylabel("RMSE mensual (USD)")
    ax.yaxis.set_major_formatter(USD_K)
    ax.set_ylim(bottom=0)
    ax.set_title("Regularización: error por tamaño mínimo de hoja (validación cruzada temporal 2016-2023)", fontsize=11)
    ax.grid(alpha=0.25)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(loc="lower right", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _fmt(stat: dict) -> str:
    return f"{stat['mean']:,.2f} ± {stat['std']:,.2f}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluación técnica del pronóstico de ventas de Brasaland.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    full, _ = sf.load_sales(args.data)
    train, _ = sf.split_train_test(full)  # the test years are discarded here on purpose

    current = me.cross_validate(train)
    naive = me.seasonal_naive_cv(train)
    candidates = {leaf: me.cross_validate(train, me.model_with_leaf(leaf))["summary"] for leaf in me.LEAF_CANDIDATES}
    curve_current = me.learning_curve(train)
    curve_proposed = me.learning_curve(train, me.model_with_leaf(me.PROPOSED_MIN_SAMPLES_LEAF))

    report = {
        "dataset": "data/raw/brasaland_sales.csv (market = consolidated), training years only",
        "train_months": [str(train["month"].min().date()), str(train["month"].max().date())],
        "cross_validation": {
            "strategy": f"TimeSeriesSplit(n_splits={me.CV_SPLITS}, test_size={me.CV_VALIDATION_MONTHS}), no shuffling",
            "model": "current: min_samples_leaf=3",
            **current,
        },
        "seasonal_naive_reference": naive["summary"],
        "regularization_candidates": {str(leaf): summary for leaf, summary in candidates.items()},
        "learning_curve": {
            "validation_folds": "2021, 2022, 2023 (the 3 folds whose training window holds 47 samples)",
            "current": curve_current.__dict__,
            "proposed": curve_proposed.__dict__,
        },
        "proposed_min_samples_leaf": me.PROPOSED_MIN_SAMPLES_LEAF,
    }

    args.out.mkdir(parents=True, exist_ok=True)
    plot_learning_curve(curve_current, curve_proposed, args.out / "learning_curve.png")
    plot_regularization(candidates, naive["summary"], args.out / "regularization_curve.png")
    (args.out / "evaluation_metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    summary = current["summary"]
    print(f"Validación cruzada temporal ({me.CV_SPLITS} folds de {me.CV_VALIDATION_MONTHS} meses, 2016-2023), media ± desviación:")
    for part in ("train", "validation", "validation_recursive"):
        print(f"  {part:22s} " + "  ".join(f"{name} {_fmt(summary[part][name])}" for name in ("mae_usd", "rmse_usd", "mape_pct")))
    print(f"  {'seasonal naive':22s} " + "  ".join(f"{name} {_fmt(naive['summary']['validation'][name])}" for name in ("mae_usd", "rmse_usd", "mape_pct")))
    print("Regularización (min_samples_leaf): RMSE validación")
    for leaf, cand in candidates.items():
        print(f"  {leaf:3d}  train {cand['train']['rmse_usd']['mean']:>10,.0f}  validation {_fmt(cand['validation']['rmse_usd'])}  MAPE {_fmt(cand['validation']['mape_pct'])}")
    print(f"Gráficas y métricas en {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
