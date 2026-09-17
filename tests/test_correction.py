import pytest

from opaque_housing.metrics.correction import (
    binary_sens_spec,
    bootstrap_mean_interval,
    corrected_prevalence,
    rogan_gladen,
)


def test_rogan_gladen_identity_when_perfect() -> None:
    assert rogan_gladen(0.4, 1.0, 1.0) == pytest.approx(0.4)


def test_rogan_gladen_unidentified() -> None:
    assert rogan_gladen(0.4, 0.5, 0.5) is None


def test_sens_spec_and_correction_from_labels() -> None:
    y_true = [True, True, False, False]
    y_pred = [True, False, False, False]
    sens, spec = binary_sens_spec(y_true, y_pred)
    assert sens == 0.5
    assert spec == 1.0
    result = corrected_prevalence(0.25, y_true, y_pred)
    assert result["corrected"] == rogan_gladen(0.25, 0.5, 1.0)


def test_bootstrap_interval_covers_mean() -> None:
    mean, lo, hi = bootstrap_mean_interval([0.0, 1.0, 1.0, 0.0], n_boot=200, seed=1)
    assert lo <= mean <= hi


def test_bootstrap_corrected_covers_point() -> None:
    from opaque_housing.metrics.correction import bootstrap_corrected_prevalence

    y_true = [True, True, False, False, True, False]
    y_pred = [True, False, False, False, True, False]
    result = bootstrap_corrected_prevalence(0.3, y_true, y_pred, n_boot=200, seed=1)
    assert result["corrected"] is not None
    assert result["corrected_lo"] is not None
    assert result["corrected_hi"] is not None
    assert result["corrected_lo"] <= result["corrected"] <= result["corrected_hi"]
