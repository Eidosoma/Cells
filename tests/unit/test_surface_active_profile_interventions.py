"""All-law scheduled active fields, actual historical closure, clocks and replay."""

import ast
import hashlib
import json
import os
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core import surface_active_profile_interventions_spec as definition
from cells.core import tissue_profile_preparation as static
from cells.core.errors import NumericalError
from cells.core.grid import EventGrid
from cells.core.runner import branch_checkpoint, run, validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, digest, parse_spec
from cells.core.state import Checkpoint
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_active_profile_interventions as model
from cells.models import surface_hcn_extra as parent
from cells.numerics.fixed_step import rk4_checked_step, rk4_step
from cells.processes import betse_tissue_profiles as native
from cells.processes import hcn_extra_catalog
from validation.topology import surface_active_profile_interventions_fixtures as fixtures
from validation.topology import surface_active_profile_interventions_reference as reference

ROOT = Path(os.environ.get("CELLS_COMPONENT_SOURCE_ROOT", Path(__file__).resolve().parents[2]))
PROTOCOL = ROOT / "validation/topology/surface_active_profile_interventions_protocol.json"


def evidence(name, value):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        (path / ("active-profiles-" + name + ".json")).write_text(
            json.dumps(
                dict(value, status="passed"),
                indent=2,
                allow_nan=False,
                default=lambda v: v.tolist(),
            )
            + "\n"
        )


def build(raw):
    raw = deepcopy(raw)
    geometry = raw["geometry"]
    layout = geometry.pop("layout")
    prepared = static.prepare(
        raw["definition"],
        static.Geometry(native.Layout(**layout), **geometry),
        static._decode_profile(raw["default"]),
        [static._decode_profile(p) for p in raw["profiles"]],
        ion_enabled=raw["ion_enabled"],
        enabled=raw["enabled"],
        is_ecm=raw["is_ecm"],
    )
    result = deepcopy(prepared.definition)
    result["model"].update(
        id=definition.MODEL_ID,
        profile_preparation=dict(definition=prepared.definition, provenance=prepared.provenance),
        interventions=raw["interventions"],
        phase=raw["phase"],
        timing_policy=definition.TIMING_POLICY,
        reset_policy=definition.RESET_POLICY,
    )
    result["execution"].update(
        intervention_capacity=raw["intervention_capacity"],
        intervention_target_capacity=raw["intervention_target_capacity"],
    )
    return result


@lru_cache
def initialized(case="SIM"):
    raw = build(fixtures.inputs(case))
    spec = parse_spec(raw)
    state, p = model.initial_values(spec)
    return raw, spec, state, p


def control(spec, time):
    table = control_values(spec, [time])
    return type(table)(*(v[0] for v in table))


def score(context, actual, expected, *, rtol=3e-10, atol=3e-12, charge_atol=3e-23):
    observed = reference.flatten(context, actual._asdict())
    budget = np.r_[
        reference.active.flatten(
            context["parent"],
            {
                k: np.full(shape, charge_atol if k.endswith("_C") else atol)
                for k, shape in context["parent"]["shapes"].items()
            },
        ),
        atol,
    ] + rtol * np.abs(expected)
    ratio = float(np.max(np.abs(observed - expected) / budget, initial=0))
    assert ratio <= 1, ratio
    return ratio


def compare_stage(raw, spec, state, p, time):
    context = reference.bind(raw)
    trial = state._replace(phase_clock_s=np.asarray([time]))
    value = model.readouts(trial, control(spec, time), p, xp=np)
    flat = reference.flatten(context, trial._asdict())
    slope, phi, proof = reference.evaluate(context, flat)
    ratio = score(context, value.derivative, slope)
    n = p.active.size
    observed = np.r_[
        value.field.potential_V[:n][p.active], value.field.potential_V[n:][p.outside_active]
    ]
    np.testing.assert_allclose(observed, phi, rtol=3e-10, atol=3e-13)
    expected = reference.field_observables(context, flat, slope, phi)
    actual = {
        k: getattr(value.field, k)
        for k in (
            "membrane_voltage_rate_V_s",
            "electrode_current_A",
            "chemical_energy_rate_pJ_s",
            "capacitor_energy_rate_pJ_s",
            "dissipation_pJ_s",
            "reservoir_power_pJ_s",
            "electrode_power_pJ_s",
            "energy_balance_pJ_s",
        )
    }
    for k in (
        "membrane_flux_fmol_s",
        "membrane_current_A",
        "membrane_voltage_V",
        "junction_voltage_V",
        "membrane_dissipation_pJ_s",
        "junction_dissipation_pJ_s",
        "face_dissipation_pJ_s",
    ):
        a = getattr(value.field.rates, k)
        actual[k] = (
            a[..., : len(expected[k])]
            if np.asarray(expected[k]).ndim == 1
            else a[..., : expected[k].shape[-1]]
        )
    actual.update(
        channel_flux_fmol_s=value.parent.channel_flux_fmol_s[:, : len(spec.model.channels)],
        pump_cycles=value.derivative.pump_cycles[: len(spec.model.membranes)],
        metabolic_power_pJ_s=float(np.sum(value.derivative.metabolic_work_pJ)),
    )
    actual["membrane_voltage_rate_V_s"] = actual["membrane_voltage_rate_V_s"][
        : len(spec.model.membranes)
    ]
    actual["electrode_current_A"] = actual["electrode_current_A"][: len(spec.model.extracellular)]
    for k, a in actual.items():
        atol = (
            3e-23
            if k.endswith("_A")
            else 3e-13
            if k.endswith("_V")
            else 3e-8
            if k.endswith("_V_s")
            else 3e-10
        )
        np.testing.assert_allclose(a, expected[k], rtol=3e-10, atol=atol, err_msg=k)
    assert bool(value.valid) and abs(value.field.energy_balance_pJ_s) < 1e-10
    return dict(
        time_s=time,
        error_over_budget=ratio,
        independent=proof,
        independent_field_keys=list(expected),
        field_energy_residual_pJ_s=float(value.field.energy_balance_pJ_s),
    )


@pytest.mark.parametrize("case", fixtures.CASES)
def test_all_56_laws_full_fields_rhs_and_preserved_actual_initial_state(case):
    raw, spec, state, p = initialized(case)
    assert type(model.parent_layout(p)) is parent.LAYOUT_TYPE
    assert len(spec.model.channels) == 56
    assert set(p.channel_laws[p.channel_active]) == set(range(56))
    assert {c.kinetic_law for c in spec.model.channels} == set(hcn_extra_catalog.LAW_CODES)
    original, original_p = parent.initial_values(definition.active_spec(spec))
    for a, b in zip(model.parent_state(state), original, strict=True):
        assert a.dtype == b.dtype and a.tobytes() == b.tobytes()
    for a, b in zip(model.parent_layout(p), original_p, strict=True):
        np.testing.assert_array_equal(a, b)
    stages = [
        compare_stage(raw, spec, state, p, t)
        for t in (0.0, 1e-6, 2e-6, 3e-6, 4e-6, 5e-6, 6e-6, 8e-6)
    ]
    assert model.check_values(state, spec)["max_energy_balance_error_pJ"] == 0
    evidence(
        "all-laws-" + case,
        dict(
            inputs=raw,
            stages=stages,
            law_count=56,
            parent_state_and_layout_exact=True,
            actual_gates_and_pumps_retained=True,
        ),
    )


@pytest.mark.parametrize("case", ["INIT", "empty-events"])
def test_inactive_scheduling_is_bitwise_complete_active_parent(case):
    _, spec, state, p = initialized(case)
    time = 4e-6
    u = control(spec, time)
    trial = state._replace(phase_clock_s=np.asarray([time]))
    actual = model.rhs(trial, u, p, p.active, xp=np)
    expected = parent.rhs(model.parent_state(trial), u, model.parent_layout(p), p.active, xp=np)
    for a, b in zip(model.parent_state(actual), expected, strict=True):
        np.testing.assert_array_equal(a, b)
    np.testing.assert_array_equal(actual.phase_clock_s, [1.0])
    evidence("inactive-" + case, dict(all_19_parent_derivatives_bitwise=True, phase_clock_rhs=1.0))


def test_ion_flags_and_background_pulses_leave_actual_channel_and_pump_owners():
    _, spec, state, p = initialized("ion-flags")
    time = 5e-6
    u = control(spec, time)
    trial = state._replace(phase_clock_s=np.asarray([time]))
    value = model.readouts(trial, u, p, xp=np)
    baseline = model.parent_layout(p).membrane_permeability
    for ion in ("Cl", "Ca"):
        i = spec.model.species_ids.index(ion)
        np.testing.assert_array_equal(value.signal.permeability[i], baseline[i])
        assert np.any(value.derivative.channel_transferred[i] != 0)
    for ion in ("Na", "K"):
        i = spec.model.species_ids.index(ion)
        assert np.any(value.signal.permeability[i] != baseline[i])
    unchanged = parent.readouts(model.parent_state(trial), u, model.parent_layout(p), xp=np)
    for name in (
        "channel_gate",
        "junction_gate",
        "channel_transferred",
        "pump_cycles",
        "metabolic_work_pJ",
    ):
        np.testing.assert_array_equal(
            getattr(value.derivative, name), getattr(unchanged.derivative, name)
        )
    blocked = u._replace(channel=np.zeros_like(u.channel), pump=np.zeros_like(u.pump))
    shut = model.readouts(trial, blocked, p, xp=np)
    np.testing.assert_array_equal(shut.derivative.channel_gate, value.derivative.channel_gate)
    assert np.any(shut.derivative.channel_gate != 0)
    np.testing.assert_array_equal(shut.derivative.channel_transferred, 0)
    np.testing.assert_array_equal(shut.derivative.pump_cycles, 0)
    evidence(
        "flags-and-clocks",
        dict(
            Na_K_unguarded=True,
            Cl_Ca_guarded_background_only=True,
            actual_channel_and_pump_owners_unchanged=True,
            blocked_channels_keep_intrinsic_clocks=True,
        ),
    )


@lru_cache
def trajectory(case="SIM", refinement=1):
    raw, original, _, _ = initialized(case)
    spec = replace(
        original, execution=replace(original.execution, dt=original.execution.dt / refinement)
    )
    state, p = model.initial_values(spec)
    grid = EventGrid(spec)
    times = np.asarray(list(grid))
    table = control_values(spec, times[:-1])
    model.check_steps(spec, np.diff(times), table)
    history = [state]
    for i, h in enumerate(np.diff(times)):
        u = type(table)(*(v[i] for v in table))
        state = rk4_step(lambda y, *args: model.rhs(y, *args, xp=np), state, h, u, p, p.active)
        history.append(state)
    return spec, p, times, STATE_HISTORY(history), model.check_values(STATE_HISTORY(history), spec)


def STATE_HISTORY(states):
    return model.STATE_TYPE(*(np.stack(v) for v in zip(*states, strict=True)))


@pytest.mark.parametrize("case", ["SIM", "close-reopen"])
def test_short_complete_active_trajectory_and_adequate_refinement(case):
    raw, _, _, _ = initialized(case)
    context = reference.bind(raw)
    expected, proof = reference.integrate(raw)
    rows = []
    for refinement in (1, 2):
        spec, _, _, history, diagnostics = trajectory(case, refinement)
        final = model.STATE_TYPE(*(v[-1] for v in history))
        ratio = score(context, final, expected, rtol=3e-9, atol=2e-11, charge_atol=3e-25)
        flat = reference.flatten(context, final._asdict())
        conservation = reference.conservation(context, flat)
        for key in ("local_residual_fmol", "outside_residual_fmol", "global_residual_fmol"):
            np.testing.assert_allclose(conservation[key], 0, rtol=0, atol=3e-14)
        assert abs(conservation["energy_residual_pJ"]) < 1e-10
        rows.append(
            dict(
                dt_s=spec.execution.dt,
                error_over_budget=ratio,
                max_error=float(np.max(np.abs(flat - expected))),
                diagnostics=diagnostics,
                independent_full_history=conservation,
            )
        )
    assert rows[-1]["max_error"] <= max(rows[0]["max_error"] * 0.3, 3e-12)
    assert np.any(final.pump_cycles != 0) and np.sum(final.metabolic_work_pJ) > 0
    evidence(
        "trajectory-" + case,
        dict(
            duration_s=8e-6,
            independent=proof,
            refinements=rows,
            all_20_state_fields_compared=True,
            maintained_fuel_and_actual_history=True,
        ),
    )


def test_closed_route_projection_cannot_affect_physics_and_never_hides_conservation():
    raw, _, _, _ = initialized("close-reopen")
    spec, p, times, history, diagnostics = trajectory("close-reopen")
    original_bytes = [v.tobytes() for v in history]
    comparisons = []
    numeric_leaves = 0
    for time in (2e-6, 4e-6, 5e-6, 8e-6):
        i = int(np.flatnonzero(times == time)[0])
        state = model.STATE_TYPE(*(v[i] for v in history))
        signal = model.signal_values(state, p, xp=np)
        current = model.parent_layout(p)._replace(membrane_permeability=signal.permeability)
        untouched = parent.readouts(model.parent_state(state), control(spec, time), current, xp=np)
        projected = parent.readouts(
            model.readout_state(state, signal.permeability, xp=np),
            control(spec, time),
            current,
            xp=np,
        )
        for a, b in zip(jax.tree.leaves(untouched), jax.tree.leaves(projected), strict=True):
            if np.asarray(a).dtype.kind != "b":
                np.testing.assert_array_equal(a, b)
                numeric_leaves += 1
        comparisons.append(compare_stage(raw, spec, state, p, time))
        if time in (4e-6, 5e-6):
            na = spec.model.species_ids.index("Na")
            closed = signal.permeability[na] == 0
            assert np.any(closed) and np.any(state.membrane_transferred[na, closed] != 0)
            assert (
                not untouched.valid
                and projected.valid
                and model.readouts(state, control(spec, time), p, xp=np).valid
            )
        if time == 8e-6:
            assert np.all(
                signal.permeability[spec.model.species_ids.index("Na"), p.membrane_active] > 0
            )
    observed = model.observe_history(times, history, p, [4e-6, 5e-6, 8e-6], spec)
    indices = [int(np.flatnonzero(times == t)[0]) for t in (4e-6, 5e-6, 8e-6)]
    for name in parent.STATE_TYPE._fields:
        np.testing.assert_array_equal(getattr(observed, name), getattr(history, name)[indices])
    assert [v.tobytes() for v in history] == original_bytes
    bad = np.array(history.membrane_transferred)
    bad[indices[0], 0, 0] += 1e-3
    corrupt = history._replace(membrane_transferred=bad)
    with pytest.raises(NumericalError):
        model.check_values(corrupt, spec)
    with pytest.raises(NumericalError):
        model.observe_history(times, corrupt, p, [4e-6], spec)
    evidence(
        "closure-proof",
        dict(
            comparisons=comparisons,
            all_parent_numeric_leaf_comparisons=numeric_leaves,
            unmodified_vs_projected_physics_bitwise=True,
            all_actual_observed_history_exact=True,
            actual_material_failure_refused=True,
            actual_diagnostics=diagnostics,
            input_state_unmodified=True,
            closed_and_reopened=True,
        ),
    )


@pytest.mark.parametrize(
    "fault",
    [
        "pressure",
        "ecm",
        "negative-P",
        "changed-gate",
        "changed-pump",
        "changed-owner",
        "changed-species",
        "profile-owner",
        "parent-family",
        "phase",
        "reset",
        "callback",
        "capacity",
    ],
)
def test_unsupported_definition_or_owner_refused(fault):
    raw = deepcopy(initialized()[0])
    m = raw["model"]
    event = m["interventions"][0]
    if fault == "pressure":
        event["kind"] = "pressure"
    if fault == "ecm":
        event["kind"] = "ecmJ"
    if fault == "negative-P":
        event["amplitude"] = -1e9
    if fault == "changed-gate":
        m["channels"][0]["initial_gate"][0] *= 0.9
    if fault == "changed-pump":
        m["membranes"][0]["pump"]["capacity_fmol_per_s"] *= 1.1
    if fault == "changed-owner":
        m["channels"][0]["membrane_id"] = m["membranes"][-1]["id"]
    if fault == "changed-species":
        m["species"][0]["valence"] = -m["species"][0]["valence"]
    if fault == "profile-owner":
        m["profile_preparation"]["provenance"]["geometry"]["layout"]["membrane_cell_ids"][0] = (
            "lost"
        )
    if fault == "parent-family":
        m["profile_preparation"]["definition"]["model"]["id"] = "resolved_calcium@11"
    if fault == "phase":
        m["phase"] = "auto_INIT_to_SIM"
    if fault == "reset":
        m["reset_policy"] = "reset_gates_and_ledgers"
    if fault == "callback":
        event.update(source_function="callback", spatial=None)
    if fault == "capacity":
        raw["execution"]["intervention_target_capacity"] = 1
    with pytest.raises((ConfigError, ValueError, TypeError)):
        parse_spec(raw)
    evidence("refused-" + fault, dict(fault=fault, refused=True))


@pytest.mark.parametrize(
    "fault", ["channel-route", "pump-history", "gate", "clock", "negative-stage-P"]
)
def test_actual_history_runtime_domain_refusals_and_atomic_checked_step(fault):
    _, spec, state, p = initialized()
    bad = state
    layout = p
    if fault == "channel-route":
        value = np.array(state.channel_transferred)
        route = p.channel_relative_permeability == 0
        i, j = np.argwhere(route & p.channel_active)[0]
        value[i, j] = 1e-3
        bad = state._replace(channel_transferred=value)
    if fault == "pump-history":
        value = np.array(state.metabolic_work_pJ)
        value[0] = 1e-3
        bad = state._replace(metabolic_work_pJ=value)
    if fault == "gate":
        bad = state._replace(channel_gate=np.ones_like(state.channel_gate) * 1.1)
    if fault == "clock":
        bad = state._replace(phase_clock_s=np.asarray([-1e-9]))
    if fault == "negative-stage-P":
        amplitude = np.array(p.intervention_amplitude)
        amplitude[:] = -1e12
        layout = p._replace(intervention_amplitude=amplitude)
        bad = state._replace(phase_clock_s=np.asarray([4e-6]))
    if fault == "negative-stage-P":
        assert np.min(model.signal_values(bad, layout, xp=np).permeability) < 0
        assert not model.control_domain_valid(bad, control(spec, 4e-6), layout, p.active, xp=np)
        changed, ok = rk4_checked_step(
            model.rhs,
            model.domain_valid,
            jax.tree.map(jnp.asarray, bad),
            jnp.asarray(1e-9),
            jax.tree.map(jnp.asarray, control(spec, 4e-6)),
            jax.tree.map(jnp.asarray, layout),
            jnp.asarray(p.active),
        )
        assert not ok
        for a, b in zip(changed, bad, strict=True):
            np.testing.assert_array_equal(a, b)
    else:
        with pytest.raises(NumericalError):
            model.check_values(bad, spec)
    evidence(
        "runtime-" + fault,
        dict(fault=fault, actual_history_or_domain_refused=True, no_clipping=True),
    )


def test_full_artifact_roundtrip_clock_guards_and_no_implicit_phase_transition():
    raw, spec, state, p = initialized()
    record = definition.artifact(spec)
    assert definition.replay(json.loads(json.dumps(record))) == spec
    assert parse_spec(spec.to_dict()) == spec
    for fault in ("identity", "kernel"):
        bad = deepcopy(record)
        if fault == "identity":
            bad["identity"] = "0" * 64
        else:
            bad["interventions"]["kernel"]["amplitude"][0] *= 2
            bad.pop("identity")
            bad["identity"] = digest(bad)
        with pytest.raises(ConfigError):
            definition.replay(bad)
    grid = EventGrid(spec)
    points = np.asarray(list(grid))
    model.check_steps(spec, np.diff(points), control_values(spec, points[:-1]))
    with pytest.raises(ConfigError):
        model.check_steps(
            replace(spec, execution=replace(spec.execution, dt=1e-6)),
            np.asarray([1e-9]),
            control_values(spec, [0.0]),
        )
    cp = Checkpoint(state, p, 0.0, 0, event_index(spec, 0.0))
    validate_checkpoint(spec, cp)
    altered = deepcopy(raw)
    altered["model"]["phase"] = "INIT"
    with pytest.raises(ConfigError):
        branch_checkpoint(spec, cp, parse_spec(altered))
    with pytest.raises(ConfigError):
        model.check_checkpoint(
            spec, replace(cp, state=state._replace(phase_clock_s=np.asarray([1e-9])))
        )
    evidence(
        "recipe-replay",
        dict(
            inputs=raw,
            artifact=record,
            full_roundtrip=True,
            native_transition_guard_passed=True,
            implicit_phase_transition_refused=True,
        ),
    )


@pytest.mark.skipif(
    os.environ.get("CELLS_COMPONENT_PHASE") != "jax", reason="separate bounded CPU JAX process"
)
def test_cpu_jax_eager_complete_56_law_rhs_trace_and_native_pulse_gradient():
    _, spec, state, p = initialized()
    trial = state._replace(phase_clock_s=np.asarray([5e-6]))
    u = control(spec, 5e-6)
    y, q = jax.tree.map(jnp.asarray, trial), jax.tree.map(jnp.asarray, p)
    v = jax.tree.map(jnp.asarray, u)
    actual = model.rhs(y, v, q, q.active)
    expected = model.rhs(trial, u, p, p.active, xp=np)
    for name, a, b in zip(model.STATE_TYPE._fields, actual, expected, strict=True):
        np.testing.assert_allclose(a, b, rtol=3e-10, atol=3e-23 if name.endswith("_C") else 3e-12)
    shaped = jax.eval_shape(lambda s: model.rhs(s, v, q, q.active), y)
    assert type(shaped) is model.STATE_TYPE and [v.shape for v in shaped] == [v.shape for v in y]
    derivative = jax.grad(
        lambda t: model.signal_values(y._replace(phase_clock_s=t[None]), q).scheduled[0, 0]
    )(jnp.asarray(2e-6))
    assert np.isfinite(derivative)
    evidence(
        "cpu-jax-eager",
        dict(
            all_56_laws_and_20_fields=True,
            full_rhs_parity=True,
            JAX_trace_preserves_state_types=True,
            pulse_time_derivative=float(derivative),
            compiled_trajectory=False,
        ),
    )


@pytest.mark.skipif(
    os.environ.get("CELLS_COMPONENT_PHASE") != "public", reason="separate bounded public process"
)
def test_public_short_all_law_execution_snapshot_resume_and_observations(tmp_path):
    raw = build(fixtures.public_inputs())
    spec = parse_spec(raw)
    complete = run(spec)
    snapshot = write_snapshot(tmp_path / "snapshot", spec, complete.checkpoint_at(1e-9))
    loaded = load_snapshot(snapshot)
    resumed = run(loaded.spec, loaded.checkpoint)
    for a, b in zip(complete.final.state, resumed.final.state, strict=True):
        np.testing.assert_array_equal(a, b)
    assert len(spec.model.channels) == 56 and np.any(
        complete.final.state.channel_gate != complete.history.channel_gate[0]
    )
    assert (
        np.any(complete.final.state.pump_cycles != 0)
        and np.sum(complete.final.state.metabolic_work_pJ) > 0
    )
    for name in model.STATE_TYPE._fields:
        np.testing.assert_array_equal(
            getattr(complete.observations, name), getattr(complete.history, name)
        )
    np.testing.assert_allclose(
        complete.history.phase_clock_s[:, 0], complete.times, rtol=0, atol=1e-23
    )
    evidence(
        "public-replay",
        dict(
            inputs=raw,
            artifact=definition.artifact(spec),
            steps=2,
            all_56_laws=True,
            all_actual_history_observed=True,
            snapshot_resume_exact=True,
            actual_gates_pumps_metabolic_work=True,
            compiled_trajectory=False,
            diagnostics=complete.diagnostics,
        ),
    )


def test_parent_call_graph_excludes_projected_history_from_all_physical_outputs():
    protocol = json.loads(PROTOCOL.read_text())
    for name, expected in protocol["readonly_source_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    functions = {}
    for row in protocol["history_projection_call_graph"]:
        data = (ROOT / row["path"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == row["sha256"]
        tree = ast.parse(data)
        for name, expected in row["body_ast_sha256"].items():
            node = next(
                n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name
            )
            assert (
                hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
                == expected
            )
            functions[row["path"] + ":" + name] = node
    kinetic = functions["src/cells/models/surface_kinetic.py:readouts"]
    assert {
        n.attr
        for n in ast.walk(kinetic)
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "state"
    } == {"junction_gate", "channel_gate"}
    parents = {child: node for node in ast.walk(kinetic) for child in ast.iter_child_nodes(node)}
    calls = set()
    for node in ast.walk(kinetic):
        if isinstance(node, ast.Name) and node.id == "state" and isinstance(node.ctx, ast.Load):
            owner = parents[node]
            if isinstance(owner, ast.Call):
                calls.add(ast.unparse(owner.func))
            else:
                assert isinstance(owner, ast.Attribute)
    assert calls == {"base.field_values", "physical_amounts", "domain_valid"}
    for name in ("physical_amounts", "charge_increment"):
        node = functions["src/cells/models/surface_tissue.py:" + name]
        assert {
            n.attr
            for n in ast.walk(node)
            if isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Name)
            and n.value.id == "state"
        } <= {"amount_increment", "extracellular_amount_increment"}
    field = functions["src/cells/models/surface_tissue.py:field_values"]
    assert not any(
        isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "state"
        for n in ast.walk(field)
    )
    assert {
        ast.unparse(n.func)
        for n in ast.walk(field)
        if isinstance(n, ast.Call)
        and any(isinstance(a, ast.Name) and a.id == "state" for a in n.args)
    } == {"physical_amounts", "charge_increment"}
    for module in (fixtures, reference):
        for node in ast.walk(ast.parse(Path(module.__file__).read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(("cells", "jax"))
    evidence(
        "call-graph",
        dict(
            parent_functions_sha256=protocol["history_projection_call_graph"],
            projected_integral_only_reaches_fixed_route_validity=True,
            physical_amounts_charge_fields_fluxes_all_derivatives_unaffected=True,
            actual_history_drives_conservation_and_observations=True,
            independent_reference=True,
        ),
    )
