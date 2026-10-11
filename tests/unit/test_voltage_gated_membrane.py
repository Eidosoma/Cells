"""CORE-007: independent physical equations and shared-engine contracts."""

import copy
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec, parse_batch, plan_batch, run_batch
from cells.core.batch_windows import iter_batch_windows, plan_batch_windows
from cells.core.errors import NumericalError
from cells.core.resources import trace_bytes
from cells.core.runner import branch_checkpoint, run, timeline, validate_checkpoint
from cells.core.schedule import VoltageGatedControl, control_values
from cells.core.specs import ChannelChange, ConfigError, parse_spec
from cells.core.state import initialise
from cells.core.windows import WindowPolicy, iter_windows, plan_windows
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import multispecies_membrane as ionic
from cells.models import voltage_gated_membrane as model
from cells.numerics.fixed_step import rk4_checked_step
from cells.processes.voltage_gates import kinetics
from tests import reference_voltage_gated_channel as reference
from tests import voltage_gated_numerical_checks as checks
from tests.reference_voltage_gated_dynamics import load_panel, sample_record
from tests.voltage_gated_fixtures import canonical_values, definition, spec_for

ROOT = Path(__file__).resolve().parents[2]
PLAN, CASES = load_panel()
REFERENCE = ROOT / "runs/num-007-2026-09-09/reference-01"


def case_named(name="divalent_depolarized", end=0.005):
    case = next(c for c in CASES if c.id == name)
    return replace(case, horizon_s=end, controls=(case.controls[0],))


@pytest.fixture
def data():
    return definition(case_named())


@pytest.mark.parametrize("name", ["mono_baseline", "divalent_depolarized"])
def test_roundtrip_numeric_axes_and_complete_ownership(name):
    spec = spec_for(case_named(name), capacity=4, membrane_capacity=3, channel_capacity=2)
    assert parse_spec(spec.to_dict()) == spec
    state, layout = model.initial_values(spec)
    assert state.gate.shape == (2, 2) and state.channel_transferred.shape == (2,)
    assert state.amount.shape == (len(spec.model.species_ids), 4)
    assert state.leak_transferred.shape == (len(spec.model.species_ids), 3)
    assert all(v.dtype == np.float64 for v in state)
    assert len(set(state._fields + layout._fields)) == len(state) + len(layout)
    assert all(
        v.dtype == np.int64
        for v in (
            layout.channel_ids,
            layout.channel_laws,
            layout.channel_membranes,
            layout.channel_species,
        )
    )
    np.testing.assert_array_equal(state.gate[:, 0], spec.model.channel.initial_gate)
    assert np.all(state.gate[:, 1:] == 0)
    np.testing.assert_array_equal(layout.amount_reference, state.amount)


@pytest.mark.parametrize(
    "path,value",
    [
        (("model", "id"), "multispecies_membrane@1"),
        (("model", "channel", "id"), "cell_0"),
        (("model", "channel", "id"), "bad/path"),
        (("model", "channel", "membrane_id"), "unknown"),
        (("model", "channel", "species_id"), "Ca"),
        (("model", "channel", "species_id"), "Cl"),
        (("model", "channel", "species_id"), "missing"),
        (("model", "channel", "kinetic_law"), "custom"),
        (("model", "channel", "initial_gate"), {"m": 0.5}),
        (("model", "channel", "initial_gate", "m"), -0.01),
        (("model", "channel", "initial_gate", "h"), 1.01),
        (("model", "channel", "initial_gate", "m"), True),
        (("model", "channel", "initial_gate", "h"), float("nan")),
        (("model", "channel", "initial_gate", "equilibrium"), True),
        (("model", "channel", "max_permeability_m_per_s"), -1),
        (("model", "channel", "max_permeability_m_per_s"), 1e308),
        (("model", "channel", "abundance"), False),
        (("model", "channel", "abundance"), float("inf")),
        (("model", "bath", "temperature_K"), 300),
        (("execution", "channel_capacity"), 0),
        (("execution", "channel_capacity"), True),
        (("execution", "edge_capacity"), 1),
        (("execution", "backend"), "gpu"),
        (("experiment", "channel_controls", "channel_id"), "missing"),
        (("experiment", "channel_controls", "schedule"), []),
        (("experiment", "channel_controls", "schedule", 0, "time"), 0.001),
        (("experiment", "channel_controls", "schedule", 0, "availability"), 1.1),
        (("experiment", "channel_controls", "schedule", 0, "availability"), True),
    ],
)
def test_invalid_schema_is_refused(data, path, value):
    node = data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(ConfigError):
        parse_spec(data)


def test_python_types_are_not_silently_dropped():
    spec = spec_for(case_named())
    bad = [
        replace(spec, model=replace(spec.model, channel={"m": 0.5})),
        replace(
            spec,
            model=replace(spec.model, channel=replace(spec.model.channel, initial_gate=[0.5, 0.5])),
        ),
        replace(spec, experiment=replace(spec.experiment, channel=(ChannelChange(0, 2),))),
        replace(spec, execution=replace(spec.execution, channel_capacity=0)),
    ]
    for changed in bad:
        with pytest.raises(ConfigError):
            run(changed)


@pytest.mark.parametrize("voltage", np.linspace(-0.12, 0.06, 19))
def test_pure_kinetics_matches_independent_scalar(voltage):
    initialise(spec_for(case_named()))  # Establish the same CPU/float64 runtime as a run.
    expected = reference.kinetics(float(voltage))
    for xp in (np, jnp):
        target, tau = kinetics(xp.array([voltage]), xp=xp)
        np.testing.assert_allclose(
            target[:, 0], (expected.m_inf, expected.h_inf), atol=2e-16, rtol=2e-15
        )
        np.testing.assert_allclose(
            tau[:, 0], (expected.tau_m_s, expected.tau_h_s), atol=1e-16, rtol=2e-15
        )


@pytest.mark.parametrize("index", [1, 6, 10, 11, 12, 13])
def test_complete_rhs_matches_independent_physics(index):
    case = CASES[index]
    spec = spec_for(case, capacity=3, membrane_capacity=2, channel_capacity=4)
    state, layout = model.initial_values(spec)
    control = VoltageGatedControl(*(v[0] for v in control_values(spec, [0])))
    expected = reference.evaluate(
        reference.Resolved(case.parameters, case.channel),
        leak_control=case.controls[0].leak,
        pump_control=case.controls[0].pump,
        availability=case.controls[0].availability,
    )
    actual = model.rhs(state, control, layout, layout.active, xp=np)
    np.testing.assert_allclose(
        actual.amount[:, 0], expected.amount_rate_fmol_per_s, atol=2e-15, rtol=2e-13
    )
    np.testing.assert_allclose(actual.gate[:, 0], expected.gate_rate_per_s, atol=2e-14, rtol=2e-14)
    assert actual.channel_transferred[0] == pytest.approx(
        expected.channel_flux_fmol_per_s, rel=2e-13, abs=2e-15
    )
    assert actual.dissipated_energy_pJ[0] == pytest.approx(
        expected.ionic_dissipation_rate_pJ_per_s, rel=2e-13, abs=2e-14
    )
    for value in actual:
        assert np.all(value[..., 1:] == 0)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_all_frozen_cases_against_saved_implicit_reference(case):
    with np.load(REFERENCE / case.id / "refined.npz", allow_pickle=False) as values:
        oracle = dict(values)
    result = run(spec_for(case, samples=oracle["sample_times_s"]))
    for times, state in (
        (result.times, result.history),
        (result.observations.times, result.observations),
    ):
        actual = canonical_values(case, state)
        wanted = sample_record(case, oracle, "Radau", times)
        assert checks.errors(case.definition(), actual, wanted, PLAN["trajectory_limits"])["pass"]
        assert checks.inspect_samples(case.definition(), times, actual, PLAN["accounting_limits"])[
            "pass"
        ]
        checks.control_checks(case.definition(), times, actual, PLAN["trajectory_limits"]["gate"])


def test_eager_jit_padding_and_observation_noninterference():
    case = case_named()
    observations = [0, 0.0001, 0.001, 0.00137, 0.005]
    eager = run(spec_for(case, jit=False, samples=observations))
    compiled = run(spec_for(case, samples=observations))
    padded = run(
        spec_for(case, capacity=3, membrane_capacity=2, channel_capacity=4, samples=observations)
    )
    sparse = run(spec_for(case, samples=[0.005]))
    for a, b, c, d in zip(
        eager.history, compiled.history, padded.history, sparse.history, strict=True
    ):
        np.testing.assert_allclose(a, b, atol=2e-13, rtol=2e-13)
        np.testing.assert_array_equal(b, c[..., :1])
        np.testing.assert_array_equal(b, d)
        assert np.all(c[..., 1:] == 0)
    np.testing.assert_array_equal(compiled.observations.gate[2], compiled.history.gate[2])


def test_ids_bind_roles_without_species_name_or_position_dispatch(data):
    base = run(parse_spec(data))
    other = copy.deepcopy(data)
    other["model"]["species"] = [data["model"]["species"][i] for i in (3, 2, 0, 1)]
    permuted = run(parse_spec(other))
    np.testing.assert_allclose(
        permuted.history.amount, base.history.amount[:, (3, 2, 0, 1)], atol=3e-13, rtol=0
    )
    np.testing.assert_allclose(permuted.history.gate, base.history.gate, atol=3e-13, rtol=0)
    renamed = run(parse_spec(json.loads(json.dumps(data).replace('"K"', '"cation_role"'))))
    for a, b in zip(base.history, renamed.history, strict=True):
        np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("disabled", ["availability", "abundance", "max_permeability_m_per_s"])
def test_disabled_current_retains_evolving_gates_and_ionic_ledgers(data, disabled):
    if disabled == "availability":
        data["experiment"]["channel_controls"]["schedule"][0][disabled] = 0
    else:
        data["model"]["channel"][disabled] = 0
    spec = parse_spec(data)
    result = run(spec)
    assert np.all(result.history.channel_transferred == 0)
    assert np.all(result.observations.channel_flux_fmol_per_s == 0)
    assert not np.array_equal(result.history.gate[-1], result.history.gate[0])
    old = copy.deepcopy(data)
    old["model"]["id"] = "multispecies_membrane@1"
    del (
        old["model"]["channel"],
        old["experiment"]["channel_controls"],
        old["execution"]["channel_capacity"],
    )
    reduced = run(parse_spec(old))
    for a, b in zip(result.history[:4], reduced.history, strict=True):
        np.testing.assert_array_equal(a, b)
    state, layout = model.initial_values(spec)
    state.gate[0, 0] = 1.01
    assert not model.domain_valid(state, layout, layout.active, xp=np)


@pytest.mark.parametrize("jit", [False, True])
def test_rejected_real_stage_does_not_advance_or_clip(jit):
    spec = spec_for(case_named("mono_gates_only"))
    cp = initialise(spec)
    control = VoltageGatedControl(*(v[0] for v in control_values(spec, [0])))

    def step(state):
        return rk4_checked_step(
            model.rhs, model.domain_valid, state, 0.002, control, cp.layout, cp.layout.active
        )

    result, ok = jax.jit(step)(cp.state) if jit else step(cp.state)
    assert not bool(ok)
    for a, b in zip(result, cp.state, strict=True):
        np.testing.assert_array_equal(a, b)
    with pytest.raises(ConfigError, match="0.0005"):
        run(replace(spec, execution=replace(spec.execution, dt=0.001)))
    assert ionic.MAX_STEP == 0.01


@pytest.mark.parametrize("kind", ["gate", "voltage"])
def test_unsampled_cubic_interior_is_checked(kind):
    state, layout = model.initial_values(spec_for(case_named()))
    history = model.STATE_TYPE(*(np.stack((v, v)) for v in state))
    slope = model.STATE_TYPE(*(np.zeros_like(v)[None] for v in state))
    if kind == "gate":
        slope.gate[0, 0, 0] = 10
    else:
        slope.amount[0, 0, 0] = 1
    right = model.STATE_TYPE(*(-v for v in slope))
    with pytest.raises(NumericalError, match="Cubic interior"):
        model.check_interpolants(np.array([0.0, 1.0]), history, slope, right, layout)


@pytest.mark.parametrize("field", model.STATE_TYPE._fields)
def test_corrupt_padding_is_refused(field):
    spec = spec_for(case_named(), capacity=3, membrane_capacity=2, channel_capacity=4)
    cp = initialise(spec)
    values = np.array(getattr(cp.state, field))
    values.flat[-1] = 1
    with pytest.raises(NumericalError):
        validate_checkpoint(spec, replace(cp, state=cp.state._replace(**{field: values})))


@pytest.mark.parametrize(
    "field",
    [
        "channel_ids",
        "channel_active",
        "channel_membranes",
        "channel_species",
        "channel_laws",
        "channel_permeability",
        "channel_abundance",
    ],
)
def test_corrupt_channel_binding_or_parameters_are_refused(field):
    spec = spec_for(case_named())
    cp = initialise(spec)
    values = np.array(getattr(cp.layout, field))
    values.flat[0] = 0 if values.dtype == bool else values.flat[0] + 1
    with pytest.raises(ConfigError, match="layout"):
        validate_checkpoint(spec, replace(cp, layout=cp.layout._replace(**{field: values})))


@pytest.mark.parametrize("path", ["scalar", "window", "batch", "batch_window"])
def test_channel_capacity_budget_precedes_allocation(monkeypatch, path):
    spec = spec_for(case_named())
    assert trace_bytes(
        replace(spec, execution=replace(spec.execution, channel_capacity=10)), 10
    ) > trace_bytes(spec, 10)
    huge = replace(
        spec, execution=replace(spec.execution, channel_capacity=2**30, max_trace_bytes=100)
    )

    def forbidden(_):
        raise AssertionError("Capacity allocation before memory refusal")

    monkeypatch.setattr(model, "initial_values", forbidden)
    batch = BatchSpec((WorldSpec(1, huge),), 1, 100, 100)
    with pytest.raises(ConfigError, match="storage|working|memory|budget"):
        if path == "scalar":
            timeline(huge)
        elif path == "window":
            plan_windows(huge, WindowPolicy(2))
        elif path == "batch":
            plan_batch(batch)
        else:
            plan_batch_windows(batch, WindowPolicy(2))


def test_event_restart_future_branch_and_fresh_process(tmp_path):
    case = next(c for c in CASES if c.id == "divalent_short_pulse")
    spec = spec_for(case, samples=[0, 0.0203, 0.02035, 0.0204, 0.1, 0.2])
    full = run(spec)
    cp = full.checkpoint_at(0.0203)
    write_snapshot(tmp_path / "snapshot", spec, cp)
    saved = load_snapshot(tmp_path / "snapshot")
    resumed = run(saved.spec, saved.checkpoint)
    start = np.flatnonzero(full.times == cp.time)[0]
    for a, b in zip(resumed.history, full.history, strict=True):
        np.testing.assert_array_equal(a, b[start:])
    changed = replace(
        spec,
        experiment=replace(
            spec.experiment,
            channel=(
                ChannelChange(0, 0),
                ChannelChange(0.0203, 0),
                ChannelChange(0.0204, 0),
                ChannelChange(0.2, 1),
            ),
        ),
    )
    branched = run(changed, branch_checkpoint(spec, cp, changed))
    direct = run(changed)
    for a, b in zip(branched.history, direct.history, strict=True):
        np.testing.assert_array_equal(a, b[start:])
    assert np.all(branched.history.channel_transferred == 0)
    for a, b in zip(branched.final.layout, cp.layout, strict=True):
        np.testing.assert_array_equal(a, b)
    bad = replace(changed, experiment=replace(changed.experiment, channel=(ChannelChange(0, 1),)))
    with pytest.raises(ConfigError, match="before"):
        branch_checkpoint(spec, cp, bad)
    terminal = run(spec, full.final)
    assert len(terminal.times) == len(terminal.observations.times) == 1
    worker = subprocess.run(
        [
            sys.executable,
            "-m",
            "cells",
            "resume",
            str(tmp_path / "snapshot"),
            "--output",
            str(tmp_path / "resumed"),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert worker.returncode == 0, worker.stderr
    with np.load(tmp_path / "resumed/trajectory.npz", allow_pickle=False) as data:
        for field in model.STATE_TYPE._fields:
            np.testing.assert_array_equal(getattr(resumed.history, field), data[field])
    write_run(tmp_path / "full", full)
    assert saved.spec.model.channel.initial_gate == (
        case.channel.initial_gate.m,
        case.channel.initial_gate.h,
    )


def test_scalar_windows_batches_and_unequal_clock_cohorts():
    specs = [
        spec_for(
            case_named(end=end),
            capacity=3,
            membrane_capacity=2,
            channel_capacity=4,
            samples=[0, 0.00137, end],
        )
        for end in (0.005, 0.003)
    ]
    batch = BatchSpec(tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs)), 2, 100, 2**26)
    scalar = [run(s) for s in specs]
    batched = run_batch(batch)
    for i, (spec, result) in enumerate(zip(specs, scalar, strict=True)):
        for a, b in zip(batched.worlds[i + 1].history, result.history, strict=True):
            np.testing.assert_array_equal(a, b)
        parts = list(iter_windows(spec, WindowPolicy(3)))
        for field in model.STATE_TYPE._fields:
            joined = np.concatenate(
                [getattr(p.history, field)[int(j > 0) :] for j, p in enumerate(parts)]
            )
            np.testing.assert_array_equal(joined, getattr(result.history, field))
        for field in vars(result.observations):
            joined = np.concatenate([getattr(p.observations, field) for p in parts])
            np.testing.assert_array_equal(joined, getattr(result.observations, field))
    rounds = list(iter_batch_windows(batch, WindowPolicy(3)))
    for i, result in enumerate(scalar, 1):
        parts = [r.worlds[i] for r in rounds if i in r.worlds]
        for field in model.STATE_TYPE._fields:
            joined = np.concatenate(
                [getattr(p.history, field)[int(j > 0) :] for j, p in enumerate(parts)]
            )
            np.testing.assert_array_equal(joined, getattr(result.history, field))
    bad = replace(
        batch,
        worlds=(
            batch.worlds[0],
            WorldSpec(
                2, replace(specs[1], execution=replace(specs[1].execution, channel_capacity=2))
            ),
        ),
    )
    with pytest.raises(ConfigError, match="channel_capacity"):
        parse_batch(bad.to_dict())
