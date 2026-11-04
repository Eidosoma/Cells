"""Plain numeric diagnostics; no native evaluators or positive source path."""

import math

import pytest

from cells.processes import betse_native_init_short_history_diagnostics as stage


def inputs():
    return dict(
        cells=((1.0, 2.0), (3.0, 4.0)),
        environment=((5.0, 6.0), (7.0, 8.0)),
        cell_volumes=(2.0, 3.0),
        ecm_volumes=4.0,
        voltage=(-0.05, -0.06),
        charges=(1, -1),
        faraday=2.0,
    )


def test_short_diagnostics_amounts_keep_original_scalar_volume_and_no_admission():
    raw = inputs()
    value = stage.amounts(**raw)
    assert value.intracellular == (8.0, 18.0)
    assert value.environmental == (44.0, 60.0)
    assert value.combined == (52.0, 78.0) and value.ionic_charge == -52.0
    assert value.volume_modes == ("original_vector", "original_scalar_per_element")
    assert value.finite_concentrations and value.finite_positive_volumes
    assert value.finite_voltage and not value.physical_or_conservation_admission
    assert raw == inputs()


@pytest.mark.parametrize("value", (float("nan"), float("inf"), -float("inf"), -1.0))
def test_short_diagnostics_invalid_concentrations_are_retained_not_clipped(value):
    raw = inputs()
    source = ((value, 2.0), (3.0, 4.0))
    raw["cells"] = source
    result = stage.amounts(**raw)
    assert raw["cells"] is source and raw["cells"][0][0] is value
    assert not result.nonnegative_concentrations
    assert result.finite_concentrations is math.isfinite(value)
    assert not result.physical_or_conservation_admission
    if not math.isfinite(value):
        assert result.intracellular[0] is result.combined[0] is result.ionic_charge is None


@pytest.mark.parametrize("value", (0.0, -1.0, float("nan"), float("inf")))
def test_short_diagnostics_invalid_geometry_volume_does_not_become_a_repair(value):
    raw = inputs()
    raw["ecm_volumes"] = value
    result = stage.amounts(**raw)
    assert not result.finite_positive_volumes
    assert raw["ecm_volumes"] is value


@pytest.mark.parametrize("fault", ("species", "cell_shape", "env_shape", "volumes", "boolean"))
def test_short_diagnostics_shape_and_numeric_schema_refuse_ambiguity(fault):
    raw = inputs()
    raw[
        {
            "species": "charges",
            "cell_shape": "cells",
            "env_shape": "environment",
            "volumes": "cell_volumes",
            "boolean": "voltage",
        }[fault]
    ] = {
        "species": (1,),
        "cell_shape": ((1.0,), (2.0, 3.0)),
        "env_shape": ((1.0,), (2.0, 3.0)),
        "volumes": (1.0,),
        "boolean": (True,),
    }[fault]
    with pytest.raises((ValueError, TypeError)):
        stage.amounts(**raw)


def test_short_diagnostics_conservation_requires_explicit_boundary_reaction_budget():
    raw = inputs()
    before = stage.amounts(**raw)
    raw["cells"] = ((2.0, 2.0), (3.0, 4.0))
    after = stage.amounts(**raw)
    missing = stage.amount_change(before, after)
    assert missing["amount_change"] == (2.0, 0.0)
    assert missing["residual"] is None and missing["conservation_passed"] is None
    explicit = stage.amount_change(before, after, expected_exchange=(2.0, 0.0))
    assert explicit["residual"] == (0.0, 0.0) and explicit["conservation_passed"] is None
    assert not explicit["physical_admission"]


def test_short_diagnostics_calendar_labels_remain_separate_from_native_update_dt():
    labels = (0.0, 0.015, 0.03)
    result = stage.clock_record(labels=labels, dt=0.01, sampled=(0.015,), completed=2)
    assert result["labels"] == labels and result["label_differences"] == (0.015, 0.015)
    assert result["dt"] == 0.01 and result["completed_labels"] == (0.0, 0.015)
    assert result["completed_sampled_labels"] == (0.015,)
    assert not result["source_labels_are_numerical_dt"]
    assert result["native_calendar_unchanged"]
