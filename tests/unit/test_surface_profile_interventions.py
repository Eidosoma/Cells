"""Scheduled four-ion fields, complete ledgers, phase scope and CPU JAX."""

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
from scipy.integrate import solve_ivp

from cells.core import surface_profile_interventions_spec as definition
from cells.core import tissue_profile_preparation as static
from cells.core.runner import branch_checkpoint, run
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, digest, parse_spec
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_profile_interventions as model
from cells.models import surface_tissue as parent
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_checked_step, rk4_step
from cells.processes import betse_tissue_profiles as native
from validation.topology import surface_profile_interventions_fixtures as fixtures
from validation.topology import surface_profile_interventions_reference as reference

ROOT = Path(os.environ.get("CELLS_COMPONENT_SOURCE_ROOT", Path(__file__).resolve().parents[2]))


def evidence(name, record, arrays=None):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(folder)
        root.mkdir(parents=True, exist_ok=True)
        if arrays is not None:
            np.savez_compressed(root / ("scheduled-profiles-" + name + ".npz"), **arrays)
        (root / ("scheduled-profiles-" + name + ".json")).write_text(
            json.dumps(
                dict(record, status="passed"),
                indent=2,
                allow_nan=False,
                default=lambda v: v.tolist(),
            )
            + "\n"
        )


@lru_cache
def raw_definition(case="SIM"):
    raw = fixtures.inputs(case)
    g = deepcopy(raw["geometry"])
    layout = g.pop("layout")
    view = static.Geometry(native.Layout(**layout), **g)
    prepared = static.prepare(
        raw["definition"],
        view,
        static._decode_profile(raw["default"]),
        [static._decode_profile(row) for row in raw["profiles"]],
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
    raw = raw_definition(case)
    spec = parse_spec(raw)
    state, p = model.initial_values(spec)
    return raw, spec, state, p


def control(spec, time):
    table = control_values(spec, [time])
    return type(table)(*(v[0] for v in table))


def score(c, actual, expected, *, rtol=3e-10, atol=3e-12, charge_atol=3e-23):
    observed = reference.flatten(c, actual._asdict())
    shape = c["parent"]["shapes"]
    budget = np.r_[
        reference.passive.flatten(
            c["parent"],
            {
                key: np.full(s, charge_atol if key.endswith("_C") else atol)
                for key, s in shape.items()
            },
        ),
        atol,
    ] + rtol * np.abs(expected)
    ratio = float(np.max(np.abs(observed - expected) / budget, initial=0))
    assert ratio <= 1, ratio
    return ratio


@pytest.mark.parametrize("case", fixtures.CASES)
def test_complete_field_rhs_ledgers_and_pulses_across_phases(case):
    raw, spec, state, p = initialized(case)
    c = reference.bind(raw)
    proofs = []
    for time in (0.0, 1e-6, 2e-6, 4e-6, 5e-6, 6e-6, 8e-6, 10e-6):
        trial = state._replace(phase_clock_s=np.asarray([time]))
        u = control(spec, time)
        value = model.readouts(trial, u, p, xp=np)
        expected, phi, proof = reference.evaluate(c, reference.flatten(c, trial._asdict()))
        ratio = score(c, value.derivative, expected)
        np.testing.assert_allclose(
            value.signal.scheduled, proof["events"]["scheduled_m2_s"], rtol=8e-12, atol=3e-30
        )
        n = p.active.size
        potential = np.r_[
            value.field.potential_V[:n][p.active], value.field.potential_V[n:][p.outside_active]
        ]
        np.testing.assert_allclose(potential, phi, rtol=3e-10, atol=3e-13)
        assert bool(value.valid) and bool(model.control_domain_valid(trial, u, p, p.active, xp=np))
        assert abs(value.field.energy_balance_pJ_s) < 1e-10
        d = value.derivative
        mass = (
            d.amount_increment.sum(axis=1)
            + d.extracellular_amount_increment.sum(axis=1)
            - d.reservoir_supplied.sum(axis=1)
        )
        np.testing.assert_allclose(mass, 0, rtol=0, atol=3e-14)
        proofs.append(
            dict(
                time_s=time,
                max_error_over_budget=ratio,
                independent=proof,
                potential_V=potential,
                energy_balance_pJ_s=float(value.field.energy_balance_pJ_s),
                material_residual_fmol_s=mass,
                permeability=value.signal.permeability,
            )
        )
    source_state, _ = parent.initial_values(definition.base_spec(spec))
    for a, b in zip(model.base_state(state), source_state, strict=True):
        np.testing.assert_array_equal(a, b)
    assert model.check_values(state, spec)["max_energy_balance_error_pJ"] == 0
    evidence(
        "phases-" + case,
        dict(
            inputs=raw,
            comparisons=proofs,
            all_parent_ledgers_preserved=True,
            phase_clock_rhs_s_s=1.0,
        ),
    )


def test_default_Dm_duplicate_last_assignment_and_ion_guards():
    raw, spec, state, p = initialized("guards")
    trial = state._replace(phase_clock_s=np.asarray([4e-6]))
    signal = model.signal_values(trial, p, xp=np)
    view, bound, events, _, _, _ = definition.bindings(spec.model, spec.execution)
    baseline = model.base_layout(p).membrane_permeability
    for ion in ("Cl", "Ca"):
        i = spec.model.species_ids.index(ion)
        np.testing.assert_array_equal(signal.permeability[i], baseline[i])
    assert np.any(signal.permeability[0] != baseline[0]) and np.any(
        signal.permeability[1] != baseline[1]
    )
    target = next(
        target
        for name, target in zip(events.names, events.targets, strict=True)
        if name == "event-Na_mem"
    )
    assert len(set(target.ids)) < len(target.ids)
    expected, proof = reference.permeability(raw, 4e-6)
    np.testing.assert_allclose(signal.scheduled, proof["scheduled_m2_s"], rtol=8e-12, atol=3e-30)
    # The same source operator from a zero phase buffer and from previous
    # scheduled writes agrees: all supported targets are overwritten every time.
    buffers = model.native_state(p, xp=np)
    for time in (0.0, 1e-6, 4e-6, 8e-6):
        carry = native.apply_interventions(
            time, buffers, events.kernel, p.intervention_dynamic_factor, xp=np
        )
        fresh = native.apply_interventions(
            time, model.native_state(p, xp=np), events.kernel, p.intervention_dynamic_factor, xp=np
        )
        np.testing.assert_array_equal(carry.membrane_total_m2_s, fresh.membrane_total_m2_s)
        buffers = carry.state
    evidence(
        "default-duplicate-guards",
        dict(
            Na_K_unguarded_when_flags_false=True,
            Cl_Ca_guarded=True,
            duplicate_last_and_default_Dm_reference=proof,
            zero_phase_buffer_equivalent_to_supported_carry=True,
        ),
    )


def test_init_is_inactive_and_parent_rhs_is_exact():
    _, spec, state, p = initialized("INIT")
    t = 4e-6
    trial = state._replace(phase_clock_s=np.asarray([t]))
    u = control(spec, t)
    actual = model.rhs(trial, u, p, p.active, xp=np)
    expected = parent.rhs(model.base_state(trial), u, model.base_layout(p), p.active, xp=np)
    for a, b in zip(model.base_state(actual), expected, strict=True):
        np.testing.assert_array_equal(a, b)
    np.testing.assert_array_equal(model.signal_values(trial, p, xp=np).scheduled, 0)
    np.testing.assert_array_equal(actual.phase_clock_s, [1.0])
    evidence("INIT-exact-parent", dict(no_event_firing=True, parent_derivatives_exact=True))


def test_temporarily_closed_routes_retain_earlier_transfer_ledgers():
    _, spec, state, p = initialized("transient-zero")
    trial = state._replace(phase_clock_s=np.asarray([1.5e-6]))
    u = control(spec, 1.5e-6)
    evolved = rk4_step(lambda y, *a: model.rhs(y, *a, xp=np), trial, 1e-12, u, p, p.active)
    closed = evolved._replace(phase_clock_s=np.asarray([8e-6]))
    signal = model.signal_values(closed, p, xp=np)
    na = spec.model.species_ids.index("Na")
    assert np.any(closed.membrane_transferred[na] != 0)
    np.testing.assert_array_equal(signal.permeability[na], 0)
    assert not parent.domain_valid(model.base_state(closed), model.base_layout(p), p.active, xp=np)
    assert model.domain_valid(closed, p, p.active, xp=np)
    assert model.check_values(closed, spec)["max_energy_balance_error_pJ"] < parent.ENERGY_ATOL_PJ
    evidence(
        "closed-route-ledger",
        dict(
            current_Na_P_zero=True,
            earlier_transfer_retained=True,
            union_used_only_for_accounting=True,
        ),
    )


def test_model_spec_full_recipe_roundtrip_and_registry():
    raw, spec, _, _ = initialized()
    assert get_model(spec.model) is model
    assert parse_spec(spec.to_dict()) == spec
    assert spec.fingerprint == digest(spec.to_dict())
    record = definition.artifact(spec)
    assert definition.replay(json.loads(json.dumps(record))) == spec
    for fault in ("identity", "events"):
        changed = deepcopy(record)
        if fault == "identity":
            changed["identity"] = "0" * 64
        else:
            changed["interventions"]["kernel"]["amplitude"][0] *= 2
            changed.pop("identity")
            changed["identity"] = digest(changed)
        with pytest.raises(ConfigError):
            definition.replay(changed)
    evidence("recipe-replay", dict(inputs=raw, artifact=record, full_roundtrip=True))


@pytest.mark.parametrize(
    "fault",
    [
        "pressure",
        "ecm",
        "reversed",
        "zero-ramp",
        "negative-P",
        "duplicate-kind",
        "unknown-profile",
        "unsampled-callback",
        "wrong-spatial-axis",
        "nonfinite",
        "boolean-factor",
        "source-cut",
        "changed-parent",
        "phase",
        "reset-policy",
        "timing-policy",
        "capacity",
        "clock-field",
    ],
)
def test_definition_refusals(fault):
    raw = deepcopy(raw_definition())
    m = raw["model"]
    event = m["interventions"][0]
    if fault == "pressure":
        event["kind"] = "pressure"
    if fault == "ecm":
        event["kind"] = "ecmJ"
    if fault == "reversed":
        event["on_s"], event["off_s"] = event["off_s"], event["on_s"]
    if fault == "zero-ramp":
        event["change_s"] = 0
    if fault == "negative-P":
        event["amplitude"] = -1e9
    if fault == "duplicate-kind":
        m["interventions"][1]["kind"] = event["kind"]
    if fault == "unknown-profile":
        event["profiles"] = ["lost-owner"]
    if fault == "unsampled-callback":
        event["source_function"] = "callback"
        event["spatial"] = None
    if fault == "wrong-spatial-axis":
        event["spatial"] = dict(values=[1.0], axis="cell")
    if fault == "nonfinite":
        event["amplitude"] = float("nan")
    if fault == "boolean-factor":
        event["dynamic_factor"] = True
    if fault == "source-cut":
        m["profile_preparation"]["definition"]["model"]["id"] = "resolved_tissue_excision@1"
    if fault == "changed-parent":
        m["cells"][0]["initial_amount_fmol"]["Na"] *= 1.001
    if fault == "phase":
        m["phase"] = "RESTART"
    if fault == "reset-policy":
        m["reset_policy"] = "carry_native_SIM_buffer"
    if fault == "timing-policy":
        m["timing_policy"] = "native_solver_loop"
    if fault == "capacity":
        raw["execution"]["intervention_target_capacity"] = 1
    if fault == "clock-field":
        m["epoch_start_time"] = 1.0
    with pytest.raises((ConfigError, ValueError, TypeError)):
        parse_spec(raw)
    evidence("refused-" + fault, dict(fault=fault, refused=True))


def test_runtime_negative_P_and_invalid_clock_refuse_without_clipping():
    _, spec, state, p = initialized()
    u = control(spec, 4e-6)
    state = state._replace(phase_clock_s=np.asarray([4e-6]))
    amplitude = np.array(p.intervention_amplitude)
    amplitude[:] = -1e9
    bad = p._replace(intervention_amplitude=amplitude)
    assert np.min(model.signal_values(state, bad, xp=np).permeability) < 0
    assert not model.control_domain_valid(state, u, bad, p.active, xp=np)
    assert not model.domain_valid(
        state._replace(phase_clock_s=np.asarray([-1e-9])), p, p.active, xp=np
    )
    changed, ok = rk4_checked_step(
        model.rhs,
        model.domain_valid,
        jax.tree.map(jnp.asarray, state),
        jnp.asarray(1e-9),
        jax.tree.map(jnp.asarray, u),
        jax.tree.map(jnp.asarray, bad),
        jnp.asarray(p.active),
    )
    assert not ok
    for a, b in zip(changed, state, strict=True):
        np.testing.assert_array_equal(a, b)
    evidence(
        "runtime-refusal",
        dict(
            negative_P_retained_and_refused=True,
            no_invalid_step_accepted=True,
            no_state_clipping=True,
        ),
    )


def test_transition_resolution_and_checkpoint_clock_refuse():
    _, spec, state, p = initialized()
    with pytest.raises(ConfigError):
        model.check_steps(spec, np.asarray([1e-6]), control_values(spec, [0.0]))
    from cells.core.state import initialise

    cp = initialise(spec)
    with pytest.raises(ConfigError):
        model.check_checkpoint(
            spec, replace(cp, state=state._replace(phase_clock_s=np.asarray([1e-7])))
        )
    evidence(
        "time-refusals",
        dict(coarse_transition_step_refused=True, checkpoint_clock_mismatch_refused=True),
    )


def test_short_numpy_RK_trajectory_against_independent_adaptive_reference():
    raw, spec, state, p = initialized()
    c = reference.bind(raw)
    initial = reference.initial(c)
    expected = initial.copy()
    for start, stop in ((0.0, 5e-6), (5e-6, 10e-6)):
        solution = solve_ivp(
            lambda t, y, held=start: reference.evaluate(c, y, held_time=held)[0],
            (start, stop),
            expected,
            method="DOP853",
            rtol=2e-11,
            atol=1e-25 * np.ones(initial.size),
            max_step=0.125e-6,
        )
        assert solution.success
        expected = solution.y[:, -1]
    results = []
    for dt in (0.125e-6, 0.0625e-6):
        current = state
        for start, stop in ((0.0, 5e-6), (5e-6, 10e-6)):
            count = round((stop - start) / dt)
            actual_dt = (stop - start) / count
            u = control(spec, start)
            for _ in range(count):
                current = rk4_step(
                    lambda y, *a: model.rhs(y, *a, xp=np), current, actual_dt, u, p, p.active
                )
        ratio = score(c, current, expected, rtol=3e-8, atol=2e-11, charge_atol=3e-25)
        diagnostics = model.check_values(current, spec)
        error = float(np.max(np.abs(reference.flatten(c, current._asdict()) - expected)))
        results.append(dict(dt_s=dt, error=error, error_over_budget=ratio, diagnostics=diagnostics))
    assert results[-1]["error"] <= max(results[0]["error"] * 0.2, 3e-13)
    evidence(
        "short-trajectory",
        dict(
            duration_s=spec.experiment.end_time,
            independent_method="DOP853, held controls on exact segments",
            refinements=results,
        ),
        dict(expected=expected, actual=reference.flatten(c, current._asdict())),
    )


@pytest.mark.skipif(
    os.environ.get("CELLS_COMPONENT_PHASE") != "jax", reason="separate bounded CPU JAX phase"
)
def test_cpu_jax_complete_rhs_batch_isolation_and_pulse_gradients():
    raw, spec, state, p = initialized()
    u = control(spec, 4e-6)
    y = jax.tree.map(jnp.asarray, state)
    q = jax.tree.map(jnp.asarray, p)
    control_jax = jax.tree.map(jnp.asarray, u)
    function = jax.jit(
        lambda t: model.rhs(y._replace(phase_clock_s=t[None]), control_jax, q, q.active)
    )
    actual = function(jnp.asarray(4e-6))
    reference_np = model.rhs(
        state._replace(phase_clock_s=np.asarray([4e-6])), u, p, p.active, xp=np
    )
    for a, b in zip(actual, reference_np, strict=True):
        np.testing.assert_allclose(
            a,
            b,
            rtol=3e-10,
            atol=3e-23 if a.dtype.kind == "f" and np.max(np.abs(b), initial=0) < 1e-15 else 3e-12,
        )
    batched = jax.jit(jax.vmap(function))(jnp.asarray([1e-6, -1e-6, 4e-6]))
    for value in batched:
        assert np.isnan(np.asarray(value)[1]).all() and np.isfinite(np.asarray(value)[[0, 2]]).all()
    gradient = jax.jit(
        jax.grad(
            lambda t: model.signal_values(y._replace(phase_clock_s=t[None]), q).scheduled[0, 0]
        )
    )(jnp.asarray(2e-6))
    assert np.isfinite(gradient)
    evidence(
        "cpu-jax-rhs",
        dict(
            full_rhs_parity=True,
            invalid_world_isolated=True,
            scheduled_Dm_time_derivative=float(gradient),
        ),
    )


@pytest.mark.skipif(
    os.environ.get("CELLS_COMPONENT_PHASE") != "public", reason="separate bounded public CPU phase"
)
def test_public_short_execution_snapshot_resume_and_phase_branch_refusal(tmp_path):
    raw = deepcopy(raw_definition())
    raw["experiment"].update(end_time=4e-9, observation_times=[0.0, 2e-9, 4e-9])
    for family in ("membrane_controls", "junction_controls"):
        for row in raw["experiment"][family]:
            row["schedule"] = row["schedule"][:1]
    raw["execution"].update(dt=1e-9, jit=False, max_steps=8)
    for row in raw["model"]["interventions"]:
        row.update(on_s=1e-9, off_s=3e-9, change_s=8e-9)
    spec = parse_spec(raw)
    complete = run(spec)
    cp = complete.checkpoint_at(2e-9)
    path = write_snapshot(tmp_path / "snapshot", spec, cp)
    loaded = load_snapshot(path)
    continued = run(loaded.spec, loaded.checkpoint)
    for a, b in zip(continued.final.state, complete.final.state, strict=True):
        np.testing.assert_array_equal(a, b)
    altered = deepcopy(raw)
    altered["model"]["phase"] = "INIT"
    with pytest.raises(ConfigError):
        branch_checkpoint(spec, cp, parse_spec(altered))
    np.testing.assert_allclose(
        complete.history.phase_clock_s[:, 0],
        complete.times,
        rtol=0,
        atol=64 * np.finfo(float).eps * spec.experiment.end_time,
    )
    evidence(
        "public-replay",
        dict(
            duration_s=4e-9,
            steps=4,
            snapshot_resume_exact=True,
            phase_change_branch_refused=True,
            compiled_trajectory=False,
            diagnostics=complete.diagnostics,
        ),
    )


def test_nominal_transition_ceiling_accepts_clock_subtraction_roundoff_only():
    _, spec, _, _ = initialized()
    ceiling = min(row.change_s / 8 for row in spec.model.interventions)
    assert spec.execution.dt == ceiling
    points = np.arange(81, dtype=np.float64) * spec.execution.dt
    steps = np.diff(points)
    assert np.max(steps) > ceiling * (1 + 16 * np.finfo(float).eps)
    model.check_steps(spec, steps, control_values(spec, points[:-1]))
    oversized = ceiling + 16 * np.spacing(spec.experiment.end_time)
    with pytest.raises(ConfigError):
        model.check_steps(spec, np.asarray([oversized]), control_values(spec, [0.0]))
    nominal_refusals = []
    for horizon in (spec.experiment.end_time, 1e9):
        bounded = replace(
            spec,
            experiment=replace(spec.experiment, end_time=horizon, observation_times=(0.0, horizon)),
            execution=replace(spec.execution, max_steps=10**18),
        )
        controls = control_values(bounded, [0.0])
        model.check_steps(bounded, np.asarray([ceiling]), controls)
        bad = replace(bounded, execution=replace(bounded.execution, dt=2 * ceiling))
        with pytest.raises(ConfigError, match="nominal execution.dt"):
            model.check_steps(bad, np.asarray([bad.execution.dt]), controls)
        nominal_refusals.append(
            dict(
                horizon_s=horizon,
                declared_dt_s=bad.execution.dt,
                clock_allowance_s=2 * float(np.spacing(horizon)),
                valid_nominal_baseline_passed=True,
                oversized_nominal_refused=True,
            )
        )
    assert nominal_refusals[-1]["clock_allowance_s"] > ceiling
    evidence(
        "clock-subtraction-boundary",
        dict(
            dt_s=spec.execution.dt,
            transition_time_s=8 * ceiling,
            max_nominal_step_s=float(np.max(steps)),
            horizon_ulp_s=float(np.spacing(spec.experiment.end_time)),
            refused_oversized_step_s=float(oversized),
            nominal_refusals=nominal_refusals,
            physical_times_unchanged=True,
        ),
    )


def test_complete_geometry_profile_source_chain_is_retained():
    path = Path(
        os.environ.get(
            "CELLS_SCHEDULED_JOINED_SOURCE",
            "/mnt/workspaces/Cells/geometry-profile-preparation-handoff-20261029-01/examples/overlap",
        )
    )
    source = {
        name: json.loads((path / (name + ".json")).read_text())
        for name in ("definition", "provenance")
    }
    raw = deepcopy(source["definition"])
    event = deepcopy(raw_definition()["model"]["interventions"][1])
    event.update(profiles=["Region"], spatial=None, source_function="None")
    raw["model"].update(
        id=definition.MODEL_ID,
        profile_preparation=source,
        interventions=[event],
        phase="SIM",
        timing_policy=definition.TIMING_POLICY,
        reset_policy=definition.RESET_POLICY,
    )
    raw["execution"].update(
        dt=0.125e-6, max_steps=128, intervention_capacity=1, intervention_target_capacity=64
    )
    spec = parse_spec(raw)
    state, p = model.initial_values(spec)
    trial = state._replace(phase_clock_s=np.asarray([4e-6]))
    c = reference.bind(raw)
    value = model.readouts(trial, control(spec, 4e-6), p, xp=np)
    expected, phi, proof = reference.evaluate(c, reference.flatten(c, trial._asdict()))
    ratio = score(c, value.derivative, expected)
    assert value.valid
    assert spec.to_dict()["model"]["profile_preparation"] == source
    assert definition.replay(definition.artifact(spec)) == spec
    evidence(
        "joined-source",
        dict(
            inputs=raw,
            artifact=definition.artifact(spec),
            source_identity=source["provenance"]["identity"],
            full_geometry_profile_chain_retained=True,
            independent_error_over_budget=ratio,
            independent_proof=proof,
        ),
    )


def test_qualified_sources_native_phase_scope_and_reference_independence():
    protocol = json.loads(
        (ROOT / "validation/topology/surface_profile_interventions_protocol.json").read_text()
    )
    for name, expected in protocol["readonly_source_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    source = protocol["native_phase_scope"]
    content = Path(source["path"]).read_bytes()
    assert hashlib.sha256(content).hexdigest() == source["sha256"]
    tree = ast.parse(content)
    for name, expected in source["body_ast_sha256"].items():
        node = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
        )
        assert (
            hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
            == expected
        ), name
    for module in (fixtures, reference):
        for node in ast.walk(ast.parse(Path(module.__file__).read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(("cells", "jax"))
    evidence(
        "source-contract",
        dict(
            readonly_sources=protocol["readonly_source_sha256"],
            native_phase_scope=source,
            independent_references=True,
        ),
    )
