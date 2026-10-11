"""Resolved evolving tissue: independent trajectories and complete ordinary replay."""

import json
import os
import subprocess
import sys
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.batch_io import load_batch_snapshot, write_batch_snapshot
from cells.core.batch import BatchSpec, WorldSpec, parse_batch, run_batch
from cells.core.batch_windows import iter_batch_windows
from cells.core.errors import NumericalError
from cells.core.runner import branch_checkpoint, run, timeline
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.windows import WindowPolicy, iter_windows
from cells.ensemble import ionic
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import surface_tissue as model
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_checked_step
from validation.tissue import surface_dynamics_fixtures as fixtures
from validation.tissue import surface_dynamics_reference as reference

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")
ARMS = fixtures.ARMS


def evidence(name, value):
    if EVIDENCE:
        path = Path(EVIDENCE) / BACKEND
        path.mkdir(parents=True, exist_ok=True)
        (path / (name + ".json")).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def initial(raw=None):
    spec = parse_spec(fixtures.definition() if raw is None else raw)
    state, layout = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    return spec, state, layout, type(controls)(*(v[0] for v in controls))


def exact(a, b):
    for x, y in zip(a, b, strict=True):
        np.testing.assert_array_equal(x, y)


def assert_states(c, actual, expected, *, atol=2e-11, charge_atol=3e-25, rtol=3e-9):
    budgets = reference.flatten(
        c,
        {k: np.full(v, charge_atol if k.endswith("_C") else atol) for k, v in c["shapes"].items()},
    )
    ratio = np.abs(actual - expected) / (budgets + rtol * np.abs(expected))
    assert np.max(ratio, initial=0) <= 1
    return float(np.max(ratio, initial=0))


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_registered_roundtrip_and_ensemble(backend):
    raw = fixtures.definition(backend=backend)
    spec = parse_spec(raw)
    assert parse_spec(spec.to_dict()) == spec
    assert get_model(spec.model) is model
    assert (
        ionic.parse_spec(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation == spec
    )


@pytest.mark.parametrize("arm", ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_independent_stage_rates_and_accounting(arm, padded):
    raw = fixtures.definition(arm, padded=padded)
    spec, state, p, control = initial(raw)
    actual = model.rhs(state, control, p, p.active, xp=np)
    c = reference.bind(raw)
    target, phi, proof = reference.evaluate(c, reference.initial(c), 0.0)
    ratio = assert_states(
        c, reference.flatten(c, actual._asdict()), target, atol=3e-12, charge_atol=3e-23, rtol=3e-10
    )
    v = model.field_values(state, control, p, xp=np)
    np.testing.assert_allclose(
        np.r_[v.potential_V[:2], v.potential_V[p.active.size : p.active.size + 5]],
        phi,
        rtol=3e-10,
        atol=3e-13,
    )
    assert v.converged and abs(v.energy_balance_pJ_s) < 1e-10
    assert model.check_values(state, spec)["max_energy_balance_error_pJ"] == 0
    evidence(
        f"resolved-stage-{arm}-{'padded' if padded else 'compact'}",
        dict(status="passed", inputs=raw, max_error_over_budget=ratio, independent_root=proof),
    )


@pytest.mark.parametrize(
    "fault",
    [
        "unknown",
        "owner",
        "charge",
        "anchor",
        "reservoir",
        "boundary",
        "gauge",
        "duplicate",
        "disconnected",
        "solver",
        "valence",
        "control",
        "capacity",
        "off_grid",
    ],
)
def test_inconsistent_definitions_are_rejected(fault):
    raw = fixtures.definition()
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    if fault == "unknown":
        m["water"] = "implicit"
    elif fault == "owner":
        m["membranes"][0]["outside"] = "missing"
    elif fault == "charge":
        m["cells"][0]["fixed_charge_equivalent_fmol"] += 0.01
    elif fault == "anchor":
        m["cells"][0]["initial_charge_C"] += 1e-17
        m["cells"][0]["fixed_charge_equivalent_fmol"] += 1e-17 / model.CHARGE_PER_FMOL
    elif fault == "reservoir":
        m["extracellular"][-1]["reservoir"] = 1
    elif fault == "boundary":
        m["extracellular"][0]["boundary_potential_V"] = 0.01
    elif fault == "gauge":
        m["closure"]["gauge_reference"] = "outside_0"
    elif fault == "duplicate":
        m["faces"][0]["id"] = "cell_0"
    elif fault == "disconnected":
        m["faces"] = []
    elif fault == "solver":
        x["field_solver"] = "gauged_dense_kirchhoff@1"
    elif fault == "valence":
        m["species"][0]["valence"] = True
    elif fault == "control":
        e["membrane_controls"][0]["schedule"][0]["availability"] = 1.01
    elif fault == "capacity":
        x["extracellular_capacity"] = 256
    else:
        e["observation_times"] = [0.0, 0.000073, 0.002]
    with pytest.raises(ConfigError):
        timeline(parse_spec(raw))


@pytest.mark.parametrize("name", model.STATE_TYPE._fields)
def test_corrupt_complete_ledgers_or_inventories_are_rejected(name):
    spec, state, _, _ = initial(fixtures.definition("clamped"))
    wrong = getattr(state, name).copy()
    # Perturb a real reservoir for its source histories, not inactive padding.
    index = (
        1
        if name
        in (
            "reservoir_supplied",
            "electrode_charge_transferred_C",
            "reservoir_work_pJ",
            "electrode_work_pJ",
        )
        else 0
    )
    wrong[..., index] += 1e-16 if name.endswith("_C") else 0.01
    with pytest.raises(NumericalError):
        model.check_values(state._replace(**{name: wrong}), spec)


def test_actual_control_changes_field_and_failed_roots_are_rejected(monkeypatch):
    _, state, p, control = initial()
    blocked = control._replace(junction=np.zeros_like(control.junction))
    opened = model.field_values(state, control, p, xp=np)
    shut = model.field_values(state, blocked, p, xp=np)
    assert np.max(np.abs(opened.potential_V - shut.potential_V)) > 1e-6
    assert not np.any(shut.rates.junction_flux_fmol_s)
    original = model.field.solve
    monkeypatch.setattr(
        model.field, "solve", lambda *a, **k: original(*a, **k)._replace(converged=False)
    )
    assert not model.control_domain_valid(state, control, p, p.active, xp=np)
    assert all(np.isnan(v).all() for v in model.rhs(state, control, p, p.active, xp=np))


def test_compiled_guard_rejects_actual_invalid_control_without_changing_state():
    _, state, p, control = initial()
    device = jax.devices(BACKEND)[0]
    state, p, control = jax.device_put(
        (state, p, control._replace(junction=np.full_like(control.junction, 1.01))), device
    )
    compute = jax.jit(
        lambda y, c, dt: rk4_checked_step(model.rhs, model.domain_valid, y, dt, c, p, p.active)
    )
    kept, valid = compute(state, control, 0.0001)
    assert not valid
    exact(kept, state)
    # The initial state/control is valid here; an unresolved physical trial
    # exceeds the voltage/inventory domain. The complete state must be retained.
    valid_control = control._replace(junction=jax.numpy.zeros_like(control.junction))
    kept, valid = compute(state, valid_control, 1e6)
    assert not valid
    exact(kept, state)


@pytest.fixture(scope="module")
def trajectories(tmp_path_factory):
    directory = tmp_path_factory.mktemp("resolved-trajectories")
    values = {}
    for arm in ARMS:
        value = run(parse_spec(fixtures.definition(arm, backend=BACKEND)))
        assert all(v.device.platform == BACKEND for v in value.final.state)
        write_run(directory / arm, value, checkpoint_times=(0.001,))
        if EVIDENCE:
            target = Path(EVIDENCE) / BACKEND
            target.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(
                target / ("resolved-trajectory-" + arm + ".npz"),
                **{k: np.asarray(v) for k, v in value.history._asdict().items()},
                **{"observed_" + k: v for k, v in vars(value.observations).items()},
            )
        values[arm] = value
    return values


@pytest.fixture(scope="module")
def references():
    return {arm: reference.integrate(fixtures.definition(arm)) for arm in ARMS}


@pytest.mark.parametrize("arm", ARMS)
def test_independent_trajectories_and_boundary_accounting(arm, trajectories, references):
    value, expected = trajectories[arm], references[arm]
    c = reference.bind(value.spec.to_dict())
    ratio = assert_states(
        c, reference.flatten(c, vars(value.observations)), np.asarray(expected["state"])
    )
    actual_phi = np.c_[
        value.observations.cell_potential_V[:, :2],
        value.observations.extracellular_potential_V[:, :5],
    ]
    np.testing.assert_allclose(actual_phi, expected["potential_V"], rtol=3e-9, atol=2e-8)
    assert value.diagnostics["max_energy_balance_error_pJ"] <= 2e-8
    reservoir = np.asarray(value.final.layout.reservoir)
    assert not np.any(value.history.extracellular_amount_increment[..., reservoir])
    assert not np.any(value.history.reservoir_supplied[..., ~reservoir])
    if arm == "closed":
        assert not np.any(value.history.reservoir_supplied)
        assert not np.any(value.history.electrode_charge_transferred_C)
    if arm in ("clamped", "release"):
        assert np.max(np.abs(value.history.electrode_charge_transferred_C)) > 1e-18
        assert np.max(np.abs(value.history.electrode_work_pJ)) > 1e-8
    if arm == "release":
        before = value.times <= 0.00073
        assert not np.any(value.history.junction_transferred[before])
        at = value.observations.times == 0.00073
        assert np.any(value.observations.junction_flux_fmol_s[at])
        assert not np.any(
            value.observations.membrane_flux_fmol_s[value.observations.times >= 0.001, :, 1]
        )
    evidence(
        "resolved-trajectory-" + arm,
        dict(
            status="passed",
            inputs=value.spec.to_dict(),
            max_state_error_over_budget=ratio,
            independent_reference=expected,
            diagnostics=value.diagnostics,
        ),
    )


def test_timestep_refinement(trajectories, references):
    raw = trajectories["clamped"].spec.to_dict()
    c, expected = reference.bind(raw), np.asarray(references["clamped"]["state"])
    errors, charge_errors = [], []
    for dt in (0.0001, 0.00005, 0.000025):
        raw["execution"]["dt"] = dt
        value = trajectories["clamped"] if dt == 0.0001 else run(parse_spec(raw))
        actual = reference.flatten(c, vars(value.observations))
        assert_states(c, actual, expected)
        diff = reference.unpack(c, actual - expected)
        errors.append(
            max(
                float(np.max(np.abs(v), initial=0)) for k, v in diff.items() if not k.endswith("_C")
            )
        )
        charge_errors.append(float(np.max(np.abs(diff["electrode_charge_transferred_C"]))))
    assert errors[-1] <= max(errors[0] * 0.2, 3e-13)
    assert charge_errors[-1] <= max(charge_errors[0] * 0.2, 3e-27)
    evidence(
        "resolved-refinement",
        dict(
            status="passed",
            dt_s=[0.0001, 0.00005, 0.000025],
            amount_energy_max_errors=errors,
            electrode_charge_max_errors_C=charge_errors,
            roundoff_floors=[3e-13, 3e-27],
        ),
    )


def test_complete_disk_fresh_process_restart_branch_and_windows(trajectories, tmp_path):
    value = trajectories["clamped"]
    checkpoint = value.checkpoint_at(0.001)
    write_snapshot(tmp_path / "checkpoint", value.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    exact(loaded.checkpoint.state, checkpoint.state)
    resumed = run(loaded.spec, loaded.checkpoint)
    exact(resumed.history, tuple(v[checkpoint.step_index :] for v in value.history))
    terminal = run(value.spec, value.final)
    exact(tuple(v[0] for v in terminal.history), value.final.state)
    raw = value.spec.to_dict()
    raw["experiment"]["junction_controls"][0]["schedule"].append(dict(time=0.001, availability=0.0))
    branch_spec = parse_spec(raw)
    changed = run(branch_spec, branch_checkpoint(value.spec, checkpoint, branch_spec))
    exact(tuple(v[0] for v in changed.history), checkpoint.state)
    np.testing.assert_array_equal(
        changed.history.junction_transferred[-1], checkpoint.state.junction_transferred
    )
    parts = list(iter_windows(value.spec, WindowPolicy(7, "full"), checkpoint))
    merged = tuple(
        np.concatenate([getattr(w.history, k)[0 if i == 0 else 1 :] for i, w in enumerate(parts)])
        for k in model.STATE_TYPE._fields
    )
    exact(merged, resumed.history)
    process = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "cells",
            "resume",
            str(tmp_path / "checkpoint"),
            "--output",
            str(tmp_path / "fresh"),
        ],
        capture_output=True,
        text=True,
        timeout=600,
    )
    (tmp_path / "fresh.stdout.log").write_text(process.stdout)
    (tmp_path / "fresh.stderr.log").write_text(process.stderr)
    process.check_returncode()
    exact(load_snapshot(tmp_path / "fresh/checkpoint_final").checkpoint.state, resumed.final.state)
    evidence(
        "resolved-restart",
        dict(
            status="passed",
            state_fields=list(model.STATE_TYPE._fields),
            comparison="bitwise",
            disk=True,
            fresh_process=True,
            terminal=True,
            future_branch=True,
            changed_windows=True,
        ),
    )


def test_world_partition_reorder_and_independent_restart(trajectories, tmp_path):
    expected = [trajectories[a] for a in ("clamped", "release")]
    batch = BatchSpec(
        tuple(WorldSpec(i + 10, v.spec) for i, v in enumerate(expected)), 2, 80, 2**29
    )
    result = run_batch(batch)
    for identity, value in result.worlds.items():
        exact(value.history, expected[identity - 10].history)
    reordered = run_batch(BatchSpec(tuple(reversed(batch.worlds)), 2, 80, 2**29))
    for identity in (10, 11):
        exact(reordered.worlds[identity].history, result.worlds[identity].history)
        single = BatchSpec((batch.worlds[identity - 10],), 1, 40, 2**29)
        exact(run_batch(single).worlds[identity].history, result.worlds[identity].history)
    checkpoints = result.checkpoint_at({10: 0.001, 11: 0.002})
    write_batch_snapshot(tmp_path / "batch", batch, checkpoints)
    loaded = load_batch_snapshot(tmp_path / "batch")
    parts = list(iter_batch_windows(loaded.spec, WindowPolicy(7, "full"), loaded.checkpoints))
    for identity in (10, 11):
        rows = [p.worlds[identity] for p in parts if identity in p.worlds]
        merged = tuple(
            np.concatenate(
                [getattr(w.history, k)[0 if i == 0 else 1 :] for i, w in enumerate(rows)]
            )
            for k in model.STATE_TYPE._fields
        )
        exact(
            merged,
            tuple(v[checkpoints[identity].step_index :] for v in result.worlds[identity].history),
        )
    evidence(
        "resolved-partition",
        dict(
            status="passed",
            world_ids=[10, 11],
            comparison="bitwise",
            independent_restart_times=[0.001, 0.002],
            reordered=True,
        ),
    )


def test_mismatched_reduced_topology_is_rejected():
    a, b = [parse_spec(fixtures.definition(arm)) for arm in ("open", "clamped")]
    with pytest.raises(ConfigError, match="matching model array axes"):
        parse_batch(BatchSpec((WorldSpec(1, a), WorldSpec(2, b)), 2, 80, 2**29).to_dict())


def test_ensemble_endpoint_reports_real_patch_voltages_and_complete_state(trajectories):
    raw = trajectories["clamped"].spec.to_dict()
    spec = ionic.parse_spec(dict(model="ionic_worlds@1", simulation=raw, worlds=1, window_steps=7))
    checkpoints, report = ionic.run(spec, backend=BACKEND)
    exact(checkpoints[1].state, trajectories["clamped"].final.state)
    assert report["final_voltage_axis"] == "membrane_patch"
    np.testing.assert_allclose(
        report["final_voltage_V"][0],
        trajectories["clamped"].observations.membrane_voltage_V[-1, :4],
        rtol=0,
        atol=0,
    )
    evidence("resolved-ensemble", dict(status="passed", report=report))


def test_previous_kinetic_tissue_ensemble_keeps_its_voltage_and_state_contract():
    from cells.models import tissue as previous
    from validation.tissue.dynamics_fixtures import definition

    raw = definition(end=0.0002, backend=BACKEND)
    scalar = run(parse_spec(raw))
    spec = ionic.parse_spec(dict(model="ionic_worlds@1", simulation=raw, worlds=1, window_steps=2))
    checkpoints, report = ionic.run(spec, backend=BACKEND)
    exact(checkpoints[1].state, scalar.final.state)
    expected = previous.cell_voltage(
        np.asarray(scalar.final.state.amount_increment),
        previous.LAYOUT_TYPE(*(np.asarray(v) for v in scalar.final.layout)),
        xp=np,
    )[:2]
    np.testing.assert_array_equal(report["final_voltage_V"][0], expected)
    assert "final_voltage_axis" not in report
    evidence("resolved-prior-family", dict(status="passed", inputs=raw, report=report))


def test_cpu_gpu_complete_saved_states_and_observations(trajectories):
    if BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved CPU trajectories")
    assert EVIDENCE
    count = 0
    for arm, value in trajectories.items():
        actual = {
            **value.history._asdict(),
            **{"observed_" + k: v for k, v in vars(value.observations).items()},
        }
        with np.load(
            Path(EVIDENCE) / "cpu" / ("resolved-trajectory-" + arm + ".npz"), allow_pickle=False
        ) as saved:
            assert set(actual) == set(saved.files)
            for name, values in actual.items():
                # Coulomb and ampere fields must never inherit fmol/pJ tolerances.
                atol = (
                    3e-25
                    if name.endswith("_C")
                    else (
                        3e-23 if name.endswith("_A") else (3e-11 if name.endswith("_V") else 3e-13)
                    )
                )
                np.testing.assert_allclose(values, saved[name], rtol=3e-10, atol=atol)
                count += values.size
    evidence(
        "resolved-cpu-gpu",
        dict(
            status="passed",
            physical_scalars=count,
            rtol=3e-10,
            amount_energy_atol=3e-13,
            charge_atol_C=3e-25,
            current_atol_A=3e-23,
            voltage_atol_V=3e-11,
        ),
    )
