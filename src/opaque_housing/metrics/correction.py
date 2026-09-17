"""Misclassification correction. Pure math; no I/O."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence


def rogan_gladen(p_hat: float, sensitivity: float, specificity: float) -> float | None:
    """Correct a binary prevalence estimate. Returns None if unidentified."""
    denom = sensitivity + specificity - 1.0
    if abs(denom) < 1e-12:
        return None
    return (p_hat + specificity - 1.0) / denom


def binary_sens_spec(
    y_true: Sequence[bool],
    y_pred: Sequence[bool],
) -> tuple[float, float]:
    tp = fp = tn = fn = 0
    for truth, pred in zip(y_true, y_pred, strict=True):
        if truth and pred:
            tp += 1
        elif not truth and pred:
            fp += 1
        elif not truth and not pred:
            tn += 1
        else:
            fn += 1
    sens = tp / (tp + fn) if (tp + fn) else 0.0
    spec = tn / (tn + fp) if (tn + fp) else 0.0
    return sens, spec


def corrected_prevalence(
    p_hat: float,
    y_true: Sequence[bool],
    y_pred: Sequence[bool],
) -> dict[str, float | None]:
    sensitivity, specificity = binary_sens_spec(y_true, y_pred)
    return {
        "observed": p_hat,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "n_labeled": float(len(list(y_true))),
        "corrected": rogan_gladen(p_hat, sensitivity, specificity),
    }


def bootstrap_mean_interval(
    values: Sequence[float],
    n_boot: int = 1000,
    seed: int = 0,
    alpha: float = 0.05,
) -> tuple[float, float, float]:
    """Return mean and percentile interval from resampling ``values``."""
    if not values:
        return 0.0, 0.0, 0.0
    rng = random.Random(seed)
    n = len(values)
    means: list[float] = []
    for _ in range(n_boot):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(math.floor(alpha / 2 * n_boot))]
    hi = means[min(n_boot - 1, int(math.ceil((1 - alpha / 2) * n_boot)) - 1)]
    return sum(values) / n, lo, hi
