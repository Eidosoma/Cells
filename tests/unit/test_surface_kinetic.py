"""Resolved kinetic tissue: independent trajectories and complete ordinary replay."""

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
from cells.models import surface_kinetic as model
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_checked_step
from validation.tissue import surface_kinetic_fixtures as fixtures
from validation.tissue import surface_kinetic_reference as reference

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
        f"resolved-kinetic-stage-{arm}-{'padded' if padded else 'compact'}",
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
    wrong[..., index] += (
        1.1
        if name in ("channel_gate", "junction_gate")
        else (1e-16 if name.endswith("_C") else 0.01)
    )
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


@pytest.mark.parametrize(
    "fault",
    [
        "temperature",
        "channel_owner",
        "channel_role",
        "channel_gate",
        "channel_law",
        "channel_control",
        "pump_role",
        "pump_stoichiometry",
        "pump_pool",
        "pump_control",
        "junction_gate",
        "junction_law",
        "identity",
        "channel_capacity",
    ],
)
def test_kinetic_definition_errors_reject(fault):
    raw = fixtures.definition()
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    if fault == "temperature":
        m["temperature_K"] = 310.0
    elif fault == "channel_owner":
        m["channels"][0]["membrane_id"] = "cell_0"
    elif fault == "channel_role":
        m["channels"][0]["species_id"] = "Cl"
    elif fault == "channel_gate":
        m["channels"][0]["initial_gate"] = [0.2, 1.01]
    elif fault == "channel_law":
        m["channels"][0]["kinetic_law"] = "equilibrate_implicitly"
    elif fault == "channel_control":
        e["channel_controls"][0]["schedule"][0]["availability"] = 1.01
    elif fault == "pump_role":
        m["membranes"][0]["pump"]["roles"]["sodium"] = "Cl"
    elif fault == "pump_stoichiometry":
        m["membranes"][0]["pump"]["stoichiometry"]["Na"] = -2
    elif fault == "pump_pool":
        m["membranes"][0]["pump"]["metabolism"]["atp_mM"] = 0.0
    elif fault == "pump_control":
        e["pump_controls"].pop()
    elif fault == "junction_gate":
        m["junctions"][0]["gate"]["initial_gate"] = 0.01
    elif fault == "junction_law":
        m["junctions"][0]["gate"]["law"] = "stored_state_block"
    elif fault == "identity":
        m["channels"][0]["id"] = "pump_0"
    else:
        x["channel_capacity"] = 1
    with pytest.raises(ConfigError):
        parse_spec(raw)


def test_patch_gates_blocking_and_same_patch_addition():
    from cells.processes import voltage_gates

    raw = fixtures.definition("clamped")
    # Two independently gated populations on one physical patch must add.
    ch = dict(raw["model"]["channels"][1], id="extra_channel", initial_gate=[0.5, 0.9])
    raw["model"]["channels"].append(ch)
    raw["experiment"]["channel_controls"].append(
        dict(channel_id=ch["id"], schedule=[dict(time=0.0, availability=0.6)])
    )
    raw["execution"]["channel_capacity"] = 6
    spec, state, p, control = initial(raw)
    value = model.readouts(state, control, p, xp=np)
    assert (
        abs(value.field.rates.membrane_voltage_V[0] - value.field.rates.membrane_voltage_V[1])
        > 1e-4
    )
    target, tau = voltage_gates.kinetics(
        value.field.rates.membrane_voltage_V[p.channel_membranes], xp=np
    )
    np.testing.assert_allclose(
        value.derivative.channel_gate[:, p.channel_active],
        ((target - state.channel_gate) / tau)[:, p.channel_active],
        rtol=0,
        atol=0,
    )
    c = reference.bind(raw)
    expected = reference.evaluate(c, reference.initial(c), 0.0)[0]
    assert_states(
        c,
        reference.flatten(c, value.derivative._asdict()),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    blocked = control._replace(
        channel=np.zeros_like(control.channel),
        pump=np.zeros_like(control.pump),
        junction=np.zeros_like(control.junction),
    )
    shut = model.readouts(state, blocked, p, xp=np)
    assert shut.valid
    assert not np.any(shut.derivative.channel_transferred)
    assert not np.any(shut.derivative.pump_cycles)
    assert not np.any(shut.derivative.junction_transferred)
    assert np.any(shut.derivative.channel_gate) and np.any(shut.derivative.junction_gate)
    # Patch voltages follow capacitor charge; the floating cell potentials move
    # when junction availability changes. Channel kinetics remain patch-local.
    np.testing.assert_allclose(
        shut.derivative.channel_gate, value.derivative.channel_gate, rtol=3e-13, atol=3e-13
    )
    assert np.max(np.abs(shut.field.potential_V - value.field.potential_V)) > 1e-6
    bad = state._replace(channel_gate=state.channel_gate * -1)
    assert not model.control_domain_valid(bad, blocked, p, p.active, xp=np)
    evidence(
        "resolved-kinetic-patch-gates",
        dict(status="passed", inputs=raw, shared_patch=True, blocked_gates_keep_evolving=True),
    )


@pytest.mark.parametrize("reverse", [False, True])
def test_pump_charge_and_three_energy_sources(reverse):
    raw = fixtures.definition("clamped")
    if reverse:
        for membrane in raw["model"]["membranes"]:
            membrane["pump"]["metabolism"]["delta_g0_J_per_mol"] = 12000.0
    spec, state, p, control = initial(raw)
    control = control._replace(channel=np.zeros_like(control.channel))
    value = model.readouts(state, control, p, xp=np)
    passive = model.readouts(state, control._replace(pump=np.zeros_like(control.pump)), p, xp=np)
    assert value.valid and passive.valid
    np.testing.assert_array_equal(value.field.potential_V, passive.field.potential_V)
    cycles = value.derivative.pump_cycles[p.pump_present]
    assert np.all(cycles < 0 if reverse else cycles > 0)
    assert np.all(value.derivative.pump_dissipated_energy_pJ >= 0)
    np.testing.assert_allclose(
        value.derivative.metabolic_work_pJ,
        -1e-3 * p.pump_drive * value.derivative.pump_cycles,
        rtol=3e-14,
        atol=3e-14,
    )
    assert (
        np.max(np.abs(value.field.electrode_current_A - passive.field.electrode_current_A)) > 1e-15
    )
    assert abs(value.field.energy_balance_pJ_s) < 1e-10
    # Missing metabolic input or reusing the passive electrode work is detectable.
    assert abs(np.sum(value.derivative.metabolic_work_pJ)) > 1e-4
    assert abs(value.field.electrode_power_pJ_s - passive.field.electrode_power_pJ_s) > 1e-6
    c = reference.bind(raw)
    for group in c["raw"]["experiment"]["channel_controls"]:
        group["schedule"][0]["availability"] = 0.0
    target = reference.evaluate(c, reference.initial(c), 0.0)[0]
    ratio = assert_states(
        c,
        reference.flatten(c, value.derivative._asdict()),
        target,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    evidence(
        "resolved-kinetic-pump-" + ("reverse" if reverse else "forward"),
        dict(
            status="passed",
            inputs=c["raw"],
            max_error_over_budget=ratio,
            energy_residual_pJ_s=float(value.field.energy_balance_pJ_s),
        ),
    )


def test_passive_reduction_and_absent_routes():
    from cells.core.surface_kinetic_spec import passive_spec
    from cells.models import surface_tissue

    raw = fixtures.definition("clamped")
    raw["model"]["channels"] = []
    raw["experiment"]["channel_controls"] = []
    raw["experiment"]["pump_controls"] = []
    raw["execution"]["channel_capacity"] = 0
    for p in raw["model"]["membranes"]:
        p["pump"] = None
    for p in raw["model"]["junctions"]:
        p["gate"].update(minimum_open_fraction=1.0, initial_gate=1.0)
    spec, state, layout, control = initial(raw)
    old = passive_spec(spec)
    assert get_model(old.model) is surface_tissue
    assert parse_spec(spec.to_dict()) == spec
    old_state, old_layout = surface_tissue.initial_values(old)
    controls = control_values(old, [0.0])
    old_control = type(controls)(*(v[0] for v in controls))
    derivative = model.rhs(state, control, layout, layout.active, xp=np)
    expected = surface_tissue.rhs(old_state, old_control, old_layout, old_layout.active, xp=np)
    for name, a in expected._asdict().items():
        np.testing.assert_allclose(
            getattr(derivative, name), a, rtol=3e-13, atol=3e-25 if name.endswith("_C") else 3e-13
        )
    assert not np.any(derivative.junction_gate)
    evidence(
        "resolved-kinetic-passive-reduction",
        dict(status="passed", inputs=raw, original_fields=list(expected._fields)),
    )


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
    directory = tmp_path_factory.mktemp("resolved-kinetic-trajectories")
    values = {}
    for arm in ARMS:
        value = run(parse_spec(fixtures.definition(arm, backend=BACKEND)))
        assert all(v.device.platform == BACKEND for v in value.final.state)
        write_run(directory / arm, value, checkpoint_times=(0.001,))
        if EVIDENCE:
            target = Path(EVIDENCE) / BACKEND
            target.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(
                target / ("resolved-kinetic-trajectory-" + arm + ".npz"),
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
        assert not np.any(value.history.channel_transferred[before])
        assert not np.any(value.history.pump_cycles[before])
        assert np.any(value.observations.channel_flux_fmol_s[at])
        assert np.any(value.observations.pump_cycle_rate_fmol_s[at])
        assert np.any(value.history.channel_gate[before][-1] != value.history.channel_gate[0])
        assert np.any(value.history.junction_gate[before][-1] != value.history.junction_gate[0])
        after = value.times >= 0.001
        assert np.max(np.ptp(value.history.membrane_transferred[after, :, 1], axis=0)) == 0
    evidence(
        "resolved-kinetic-trajectory-" + arm,
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
        "resolved-kinetic-refinement",
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
    for kind in ("channel", "pump"):
        for group in raw["experiment"][kind + "_controls"]:
            group["schedule"].append(dict(time=0.001, availability=0.0))
    branch_spec = parse_spec(raw)
    changed = run(branch_spec, branch_checkpoint(value.spec, checkpoint, branch_spec))
    exact(tuple(v[0] for v in changed.history), checkpoint.state)
    np.testing.assert_array_equal(
        changed.history.junction_transferred[-1], checkpoint.state.junction_transferred
    )
    np.testing.assert_array_equal(
        changed.history.channel_transferred[-1], checkpoint.state.channel_transferred
    )
    np.testing.assert_array_equal(changed.history.pump_cycles[-1], checkpoint.state.pump_cycles)
    assert np.any(changed.history.channel_gate[-1] != checkpoint.state.channel_gate)
    assert np.any(changed.history.junction_gate[-1] != checkpoint.state.junction_gate)
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
        "resolved-kinetic-restart",
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
        "resolved-kinetic-partition",
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
    evidence("resolved-kinetic-ensemble", dict(status="passed", report=report))


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
            Path(EVIDENCE) / "cpu" / ("resolved-kinetic-trajectory-" + arm + ".npz"),
            allow_pickle=False,
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
        "resolved-kinetic-cpu-gpu",
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
