"""Bounded adapter, mapping, reference and real-runner checks before capture."""

import copy

import pilot_compare as compare
import pilot_context as ctx
import pilot_job as job
import pilot_mapping as mapping
import pilot_reference as reference
import pytest
from pilot_math import Ledger, contraction


@pytest.fixture(scope="module")
def setup():
    return dict(
        protocol=ctx.c.read(ctx.PROTOCOL),
        cases=ctx.cases(),
        rows=ctx.native_rows(),
        previous=ctx.c.read(ctx.CAPTURE / "registration.json"),
    )


def test_prerequisite_identity():
    assert ctx.prior()["audit_completion_sha256"] == ctx.AUDIT_SHA


def test_protocol_counts(setup):
    job.validate_protocol(setup["protocol"])
    assert setup["protocol"]["native_runs"] == 36


@pytest.mark.parametrize("key", ["duration_s", "native_runs", "automatic_retry"])
def test_protocol_changes_rejected(setup, key):
    plan = copy.deepcopy(setup["protocol"])
    plan[key] = 99
    with pytest.raises(ValueError):
        job.validate_protocol(plan)


@pytest.mark.parametrize("index", range(6))
def test_native_mapping_schema_and_measured_charge(setup, index):
    from cells.core.specs import parse_spec

    case = list(setup["cases"].values())[index]
    data = ctx.definition(case, 5e-5)
    spec = parse_spec(data)
    assert spec.to_dict() == data
    assert data["model"]["extracellular"]["volume_pL"] == 6.75
    row = setup["rows"][case["id"] + "/observed"]
    assert case["area_m2"] == row["geometry"]["cell_areas_m2"]
    assert case["initial_voltage_V"] == ctx.owners(
        row["trace"]["initial"]["physical"]["voltage_V"], row["geometry"]
    )


def test_mask_changes_transport_not_capacitance(setup):
    opened, closed = (setup["cases"][key] for key in ("pump_leak", "closed_boundary"))
    assert (
        opened["area_m2"] == closed["area_m2"]
        and opened["specific_capacitance_F_m2"] == closed["specific_capacitance_F_m2"]
    )
    assert (
        any(f < 1 for f in closed["active_area_fraction"])
        and closed["active_area_fraction"][-1] == 1
    )
    for i, fraction in enumerate(closed["active_area_fraction"]):
        assert closed["alpha_mol_m2_s"][i] == opened["alpha_mol_m2_s"][i] * fraction


def test_nonuniform_faces_are_not_silently_averaged(setup):
    row = copy.deepcopy(setup["rows"]["pump_leak/observed"])
    row["trace"]["initial"]["physical"]["at_membrane_mM"][0][0] += 1
    with pytest.raises(ValueError, match="nonuniform"):
        ctx.case_for(row, setup["previous"]["protocol"]["variants"][0])


@pytest.fixture(scope="module")
def compiled():
    import jax

    from cells.models import kinetic_finite_extracellular as model

    assert jax.config.x64_enabled and jax.default_backend() == "cpu"
    return jax.jit(model.rhs)


@pytest.mark.parametrize("index", range(6))
def test_three_backend_initial_contact(setup, compiled, index):
    variant = setup["previous"]["protocol"]["variants"][index]
    ledger = Ledger()
    record = mapping.check_held(
        setup["rows"][variant["id"] + "/observed"], variant, 0, compiled, ledger
    )
    assert len(record["backends"]) == 3 and ledger.comparisons == 270


def test_later_masked_state_contact(setup, compiled):
    variant = setup["previous"]["protocol"]["variants"][-1]
    assert (
        len(
            mapping.check_held(
                setup["rows"]["closed_boundary/observed"], variant, 7, compiled, Ledger()
            )["backends"]
        )
        == 3
    )


@pytest.mark.parametrize("index", range(6))
def test_existing_saved_native_points(setup, index):
    variant = setup["previous"]["protocol"]["variants"][index]
    p = copy.deepcopy(setup["protocol"])
    p["duration_s"] = 0.0002
    rows = setup["rows"]
    r = dict(
        protocol=p,
        cases=setup["cases"],
        native_geometry=rows["pump_leak/observed"]["geometry"],
        native_initial={
            v: rows[v + "/observed"]["trace"]["initial"]["physical"] for v in p["variants"]
        },
    )
    points, diagnostics = compare.native_points(
        r, rows[variant["id"] + "/observed"], variant, Ledger()
    )
    assert len(points["states"]) == 9 and len(points["states"][0]) == 59
    assert diagnostics["material_fmol"] < 2e-12


def test_refined_independent_reference_smoke(setup):
    p = copy.deepcopy(setup["protocol"])
    p["duration_s"] = 5e-5
    records = [
        reference.integrate(setup["cases"]["pump_leak"], setting, p)
        for setting in p["reference"]["solves"]
    ]
    for row in records:
        assert len(row["states"]) == 9
        Ledger().compare("reference_smoke", row["states"], records[1]["states"], 1e-11)


@pytest.mark.parametrize(
    "errors,floor,valid",
    [
        ([4.0, 2.0, 1.0], 0.001, True),
        ([1e-12, 2e-12, 1e-12], 1e-10, True),
        ([1.0, 0.99, 0.98], 1e-10, False),
        ([1.0, float("nan"), 0.1], 1e-10, False),
    ],
)
def test_refinement_policy(errors, floor, valid):
    if valid:
        assert contraction(errors, floor, 0.8)["errors"] == errors
    else:
        with pytest.raises(ValueError):
            contraction(errors, floor, 0.8)


@pytest.mark.parametrize("phase", job.PHASES)
def test_incomplete_phase_stops_campaign(phase):
    with pytest.raises((ValueError, KeyError)):
        job.phase_gate(phase, {"status": "failed"})


def test_unregistered_observation_grid_rejected():
    with pytest.raises(ValueError):
        compare.selected(dict(times_s=[0.0], states=[[0.0]], voltage_V=[[0.0]]), [1.0])


def test_public_compiled_runner_and_complete_restart_smoke(setup, tmp_path):
    import numpy as np

    from cells.core.runner import run
    from cells.core.specs import parse_spec
    from cells.io import load_snapshot, write_run

    case = copy.deepcopy(setup["cases"]["closed_boundary"])
    case["end_time_s"] = 5e-5
    spec = parse_spec(ctx.definition(case, 2.5e-5, times=[0.0, 2.5e-5, 5e-5]))
    result = run(spec)
    write_run(tmp_path / "run", result, checkpoint_times=(2.5e-5,))
    saved = load_snapshot(tmp_path / "run/snapshots/step-000001")
    resumed = run(saved.spec, saved.checkpoint)
    assert all(
        np.array_equal(np.asarray(a)[1:], np.asarray(b))
        for a, b in zip(result.history, resumed.history, strict=True)
    )
    assert result.diagnostics["max_energy_balance_error_pJ"] < 2e-8
