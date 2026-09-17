"""Classifier evaluation. Pure functions."""

from __future__ import annotations

from collections.abc import Sequence

from opaque_housing.schema import OwnerClass

LABELS = [c.value for c in OwnerClass]


def confusion_counts(
    y_true: Sequence[str],
    y_pred: Sequence[str],
    labels: Sequence[str] = LABELS,
) -> list[list[int]]:
    index = {label: i for i, label in enumerate(labels)}
    matrix = [[0] * len(labels) for _ in labels]
    for truth, pred in zip(y_true, y_pred, strict=True):
        if truth not in index or pred not in index:
            continue
        matrix[index[truth]][index[pred]] += 1
    return matrix


def per_class_f1(matrix: list[list[int]]) -> list[float]:
    scores: list[float] = []
    n = len(matrix)
    for i in range(n):
        tp = matrix[i][i]
        fp = sum(matrix[j][i] for j in range(n) if j != i)
        fn = sum(matrix[i][j] for j in range(n) if j != i)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        scores.append(0.0 if (prec + rec) == 0 else 2 * prec * rec / (prec + rec))
    return scores


def macro_f1(matrix: list[list[int]]) -> float:
    present = [i for i, row in enumerate(matrix) if sum(row) > 0]
    if not present:
        return 0.0
    scores = per_class_f1(matrix)
    return sum(scores[i] for i in present) / len(present)


def evaluation_report(
    y_true: Sequence[str],
    y_pred: Sequence[str],
    labels: Sequence[str] = LABELS,
) -> dict[str, object]:
    matrix = confusion_counts(y_true, y_pred, labels)
    scores = per_class_f1(matrix)
    return {
        "n": len(y_true),
        "labels": list(labels),
        "confusion": matrix,
        "per_class_f1": dict(zip(labels, scores, strict=True)),
        "macro_f1": macro_f1(matrix),
    }
