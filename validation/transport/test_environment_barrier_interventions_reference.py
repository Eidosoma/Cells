"""Independent pulse/coefficient/owner checks and bounded instantaneous stages.

No trajectories are run here. The root component round owns the complete
production-versus-DOP853 transient and its retained full-state arrays.
"""

import ast
import json
import math
import os
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from validation.transport import environment_barrier_interventions_reference as oracle
from validation.transport.environment_barrier_interventions_fixtures import CASES, inputs
from validation.transport.environment_barrier_preparation_reference import prepare


def raw_input(case="partial", *, permuted=False, padded=False):
    """Reference-only physical fixture, not a production provenance admission."""
    declarations = inputs(case, permuted=permuted, padded=padded)
    prepared = prepare(declarations["request"])
    raw = deepcopy(prepared["definition"])
    raw["model"].update(
        id=oracle.MODEL_ID,
        barrier_preparation={
            "definition": deepcopy(prepared["definition"]),
            "provenance": {
                "request": deepcopy(declarations["request"]),
                "coefficients": deepcopy(prepared["coefficients"]),
            },
        },
        intervention=declarations["intervention"],
        phase=declarations["phase"],
        timing_policy=declarations["timing_policy"],
    )
    raw["execution"]["barrier_target_capacity"] = declarations["barrier_target_capacity"]
    return raw


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("permuted,padded", [(False, False), (True, True)])
def test_complete_fixture_clock_and_coefficient_axes(case, permuted, padded):
    declaration = inputs(case, permuted=permuted, padded=padded)
    raw = raw_input(case, permuted=permuted, padded=padded)
    context = oracle.bind(raw)
    assert len(context["shapes"]) == 13 and context["shapes"]["phase_clock_s"] == (1,)
    assert oracle.unpack(context, oracle.initial(context))["phase_clock_s"].tolist() == [0.0]
    experiment = raw["experiment"]
    carrier = next(
        r for r in experiment["membrane_controls"] if r["membrane_id"] == "membrane_0_sw"
    )
    assert [r["time"] for r in carrier["schedule"]] == experiment["observation_times"]
    assert all(
        r["availability"] == (0.7 if r["time"] >= 3.3e-6 else 1.0) for r in carrier["schedule"]
    )
    if declaration["intervention"] is not None:
        event = declaration["intervention"]
        assert raw["execution"]["dt"] <= event["change_s"] / 8
        assert event["on_s"] in experiment["observation_times"]
        assert event["off_s"] in experiment["observation_times"]
    before = deepcopy(raw)
    for time in (0.0, 2e-6, 4e-6, 7e-6, experiment["end_time"]):
        value = oracle.coefficients(context, time)
        assert 0 <= value["effect"] <= 1
        assert set(value["face_m2_s"]) == set(context["request"]["grid"]["species_ids"])
        for row in value["face_m2_s"].values():
            assert set(row) == set(context["request"]["grid"]["internal_face_ids"])
            assert all(math.isfinite(v) and v >= 0 for v in row.values())
    assert raw == before


def test_native_logistic_has_smooth_nonzero_tails_and_symmetric_transitions():
    on, off, change = 2e-6, 7e-6, 1e-6
    assert 0 < oracle.pulse(0.0, on, off, change) < 1e-8
    assert 0 < oracle.pulse(10e-6, on, off, change) < 1e-12
    assert oracle.pulse(on, on, off, change) == oracle.pulse(off, on, off, change)
    assert 0.99 < oracle.pulse((on + off) / 2, on, off, change) < 1.0
    for displacement in (0.1e-6, 0.5e-6, 1e-6):
        assert oracle.pulse(on - displacement, on, off, change) == pytest.approx(
            oracle.pulse(off + displacement, on, off, change), rel=2e-14, abs=1e-18
        )


def test_selected_sites_interpolate_from_baseline_then_apply_modulators():
    context = oracle.bind(raw_input("asymmetric_modulators"))
    result = oracle.coefficients(context, 4.5e-6)
    effect = result["effect"]
    assert 0.64 < effect < 0.65
    # se is a tight boundary; its Na base=1e-13, free=1e-12, modulator=3.
    target = 1e-13 * (1 - effect) + 1e-12 * effect
    assert result["site_updated_m2_s"]["Na"]["se"] == pytest.approx(target, rel=2e-16)
    assert result["site_effective_m2_s"]["Na"]["se"] == pytest.approx(3 * target, rel=3e-16)
    # sw is not targeted: a post-barrier modulator .3 remains in force.
    assert result["site_updated_m2_s"]["Na"]["sw"] == 2.5e-13
    assert result["site_effective_m2_s"]["Na"]["sw"] == 7.5e-14
    assert result["sodium_weight"]["se"] == pytest.approx(0.1 * (1 - effect) + effect)
    assert result["sodium_weight"]["sw"] == 0.25
    expected_face = 2 / (1 / 7.5e-14 + 1 / (3 * target))
    assert result["face_m2_s"]["Na"]["face_sw_se"] == pytest.approx(expected_face, rel=4e-16)


def test_duplicate_occurrences_are_idempotent_but_retained():
    ordinary = oracle.bind(raw_input("partial"))
    duplicate = oracle.bind(raw_input("duplicate"))
    for time in (0.0, 2e-6, 4.5e-6, 7e-6, 9e-6):
        a, b = oracle.coefficients(ordinary, time), oracle.coefficients(duplicate, time)
        assert b["target_site_occurrences"] == ["se", "nw", "se", "nw"]
        assert a["target_site_occurrences"] == ["se", "nw"]
        for key in (
            "effect",
            "sodium_weight",
            "site_updated_m2_s",
            "site_effective_m2_s",
            "face_m2_s",
        ):
            assert a[key] == b[key]


@pytest.mark.parametrize("case", ["init", "none", "blocked", "unit_factors"])
def test_inactive_or_uniform_coefficients_reduce_to_independent_static_values(case):
    context = oracle.bind(raw_input(case))
    for time in (0.0, 2e-6, 4.5e-6, 7e-6, 10e-6):
        value = oracle.coefficients(context, time)
        assert value["face_m2_s"] == context["static"]["coefficients"]["face_m2_s"]
        assert (
            value["site_effective_m2_s"] == context["static"]["coefficients"]["site_effective_m2_s"]
        )
        if case != "unit_factors":
            assert value["effect"] == 0.0


def test_zero_free_species_and_zero_modulator_remain_zero_through_opening():
    context = oracle.bind(raw_input("zero_species"))
    for time in (0.0, 2e-6, 4.5e-6, 10e-6):
        value = oracle.coefficients(context, time)
        assert all(v == 0 for v in value["site_effective_m2_s"]["Cl"].values())
        assert all(v == 0 for v in value["face_m2_s"]["Cl"].values())
    declaration = inputs("open")
    declaration["request"]["ion_modulators"]["K"]["se"] = 0.0
    prepared = prepare(declaration["request"])
    raw = raw_input("open")
    raw["model"].update(prepared["definition"]["model"])
    raw["model"]["id"] = oracle.MODEL_ID
    raw["model"]["barrier_preparation"] = {
        "definition": prepared["definition"],
        "provenance": {"request": declaration["request"]},
    }
    context = oracle.bind(raw)
    value = oracle.coefficients(context, 4.5e-6)
    assert value["site_updated_m2_s"]["K"]["se"] > 0
    assert value["site_effective_m2_s"]["K"]["se"] == 0
    assert value["face_m2_s"]["K"]["face_sw_se"] == 0
    assert value["face_m2_s"]["K"]["face_se_ne"] == 0


@pytest.mark.parametrize("case", CASES)
def test_maps_ignore_definition_order_and_face_orientation(case):
    a, b = (oracle.bind(raw_input(case, permuted=p, padded=p)) for p in (False, True))
    for time in (0.0, 4.5e-6, 9e-6):
        av, bv = oracle.coefficients(a, time), oracle.coefficients(b, time)
        for key in ("sodium_weight", "site_updated_m2_s", "site_effective_m2_s", "face_m2_s"):
            assert av[key] == bv[key]


def test_oracle_recomputes_recipe_instead_of_using_prepared_coefficient_claims():
    raw = raw_input()
    baseline = oracle.coefficients(oracle.bind(raw), 4e-6)
    raw["model"]["barrier_preparation"]["provenance"]["coefficients"] = {"invented": 999}
    assert oracle.coefficients(oracle.bind(raw), 4e-6) == baseline
    # Mutating an actual owner is different: that must fail correspondence.
    raw["model"]["cells"][0]["volume_pL"] *= 2
    with pytest.raises(ValueError, match="exactly match"):
        oracle.bind(raw)


@pytest.mark.parametrize(
    "fault",
    [
        "duplicate_capacity",
        "negative_amplitude",
        "amplification",
        "zero_change",
        "reverse_time",
        "end",
        "unknown_site",
        "empty_sites",
        "large_dt",
        "phase",
        "policy",
    ],
)
def test_invalid_dynamic_contract_refuses(fault):
    raw = raw_input("duplicate")
    event = raw["model"]["intervention"]
    if fault == "duplicate_capacity":
        raw["execution"]["barrier_target_capacity"] = 2
    elif fault == "negative_amplitude":
        event["amplitude"] = -0.1
    elif fault == "amplification":
        event["amplitude"] = 1.1
    elif fault == "zero_change":
        event["change_s"] = 0.0
    elif fault == "reverse_time":
        event["off_s"] = event["on_s"]
    elif fault == "end":
        event["off_s"] = 2 * raw["experiment"]["end_time"]
    elif fault == "unknown_site":
        event["site_ids"] = ["absent"]
    elif fault == "empty_sites":
        event["site_ids"] = []
    elif fault == "large_dt":
        raw["execution"]["dt"] = event["change_s"] / 4
    elif fault == "phase":
        raw["model"]["phase"] = "OTHER"
    elif fault == "policy":
        raw["model"]["timing_policy"] = "left_frozen_pulse"
    with pytest.raises(ValueError):
        oracle.bind(raw)


@pytest.mark.parametrize("manufactured", [False, True])
def test_complete_stage_charge_material_energy_and_clock(manufactured):
    context = oracle.bind(raw_input())
    values = oracle.unpack(context, oracle.initial(context))
    time = 4e-6 if manufactured else 0.0
    values["phase_clock_s"][0] = time
    if manufactured:
        values["amount_increment"][[0, 2], 0] = -1e-5
        values["extracellular_amount_increment"][[0, 2], 0] = 1e-5
        values["membrane_transferred"][[0, 2], 0] = 1e-5
    state = oracle.flatten(context, values)
    slope, phi, proof = oracle.evaluate(context, state, time)
    assert slope.shape == state.shape and np.isfinite(slope).all() and np.isfinite(phi).all()
    assert oracle.unpack(context, slope)["phase_clock_s"].tolist() == [1.0]
    assert max(map(abs, proof["material_rate_balance_fmol_s"])) < 3e-14
    assert abs(proof["charge_rate_balance_C_s"]) < 3e-25
    assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-9
    assert proof["barrier_parameter_work_pJ_s"] == 0
    assert proof["dissipation_pJ_s"] >= 0
    assert np.array_equal(state, oracle.flatten(context, values))
    if destination := os.environ.get("CELLS_BARRIER_REFERENCE_EVIDENCE"):
        path = Path(destination) / (
            "manufactured-stage.json" if manufactured else "initial-stage.json"
        )
        path.write_text(
            json.dumps(
                {
                    "scope": "manufactured instantaneous stage, not an evolved ledger history"
                    if manufactured
                    else "initial instantaneous stage",
                    "inputs": context["definition"],
                    "time_s": time,
                    "shapes": context["shapes"],
                    "state": values,
                    "slope": oracle.unpack(context, slope),
                    "potential_V": phi,
                    "proof": proof,
                },
                indent=2,
                allow_nan=False,
                default=lambda v: v.tolist(),
            )
            + "\n"
        )


def test_phase_clock_refuses_a_stale_or_invalid_complete_state():
    context = oracle.bind(raw_input())
    state = oracle.initial(context)
    with pytest.raises(ValueError, match="does not match"):
        oracle.evaluate(context, state, 2e-6)
    state[-1] = -1e-6
    with pytest.raises(ValueError):
        oracle.evaluate(context, state, 0.0)


def test_stage_clock_and_left_held_membrane_control_have_distinct_roles():
    context = oracle.bind(raw_input())
    state = oracle.initial(context)
    state[-1] = 4e-6
    right, _, right_proof = oracle.evaluate(context, state, 4e-6)
    held, _, held_proof = oracle.evaluate(context, state, 4e-6, held_control_time=0.0)
    assert right_proof["effect"] == held_proof["effect"] > 0.6
    assert not np.array_equal(right, held)
    assert right[-1] == held[-1] == 1.0


def test_new_reference_and_fixture_have_no_direct_production_imports():
    for filename in (
        "environment_barrier_interventions_reference.py",
        "environment_barrier_interventions_fixtures.py",
    ):
        for node in ast.walk(ast.parse(Path(__file__).with_name(filename).read_text())):
            modules = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            assert all(module.split(".")[0] not in ("cells", "jax") for module in modules)
