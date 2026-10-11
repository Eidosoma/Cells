"""CORE-009 finite ownership, independent equations and shared-engine contracts."""

import copy
from dataclasses import replace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec, parse_batch, plan_batch, run_batch
from cells.core.errors import NumericalError
from cells.core.resources import trace_bytes
from cells.core.runner import branch_checkpoint, run, timeline, validate_checkpoint
from cells.core.schedule import PhysicalIonicGraphControl, control_values
from cells.core.specs import ConfigError, ContactChange, parse_spec
from cells.core.state import initialise
from cells.core.windows import WindowPolicy, iter_windows
from cells.io import load_snapshot, write_snapshot
from cells.models import finite_extracellular as model
from cells.models import multispecies_membrane as ionic
from cells.models import voltage_gated_membrane as gated
from cells.numerics.fixed_step import rk4_checked_step
from tests import finite_extracellular_numerical_checks as checks
from tests import finite_extracellular_numerical_data as graph_data
from tests import reference_finite_extracellular as reference
from tests.finite_extracellular_fixtures import (
    REFERENCE,
    canonical,
    definition,
    load_cases,
    spec_for,
)

PLAN, CASES = load_cases()


def short(name="star_divalent", end=0.004):
    c = next(c for c in CASES if c.id == name)
    return replace(c, horizon_s=end, controls=(c.controls[0],))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_strict_roundtrip_and_independent_complete_stage(case):
    spec = spec_for(case)
    assert parse_spec(spec.to_dict()) == spec
    state, layout = model.initial_values(spec)
    assert len(state) == 10 and all(v.dtype == np.float64 for v in state)
    assert len(set(state._fields + layout._fields)) == len(state) + len(layout)
    assert state.amount_increment.shape == (len(case.world.species_ids), 4)
    assert state.leak_transferred.shape[-1] == 5
    assert state.gate.shape == (2, 3) and state.junction_gate.shape == (4,)
    initialise(spec)
    control = PhysicalIonicGraphControl(*(v[0] for v in control_values(spec, [0])))
    expected = case.layout.pack(
        reference.evaluate(
            case.world, reference.initial_state(case.world), case.controls[0].value
        ).rate
    )
    for xp in (np, jnp):
        current, parameters, held = (
            jax.device_put((state, layout, control)) if xp is jnp else (state, layout, control)
        )
        rate = model.rhs(current, held, parameters, parameters.active, xp=xp)
        np.testing.assert_allclose(
            canonical(case, rate._asdict(), derivative=True), expected, atol=2e-13, rtol=3e-12
        )
        assert model.domain_valid(current, parameters, parameters.active, xp=xp)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_frozen_full_trajectories_match_saved_reference(case):
    with np.load(REFERENCE / case.id / "refined.npz", allow_pickle=False) as saved:
        oracle = dict(saved)
    result = run(spec_for(case, samples=oracle["sample_times_s"]))
    values = canonical(case, vars(result.observations))
    assert checks.errors(
        case.definition(), values, oracle["sample_state"], PLAN["trajectory_limits"]
    )["pass"]
    assert checks.inspect_samples(
        case.definition(),
        result.times,
        canonical(case, result.history._asdict()),
        PLAN["accounting_limits"],
    )["pass"]


@pytest.mark.parametrize(
    "path,value",
    [
        (("model", "id"), "voltage_gated_membrane@1"),
        (("model", "cells"), []),
        (("model", "cells", 1, "cell", "id"), "cell_0"),
        (("model", "cells", 1, "membrane", "id"), "membrane_0"),
        (("model", "cells", 2, "channel"), {}),
        (("model", "junctions", 0, "id"), "channel_0"),
        (("model", "junctions", 0, "from_cell"), "missing"),
        (("model", "junctions", 0, "to_cell"), "cell_0"),
        (("model", "junctions", 0, "area_m2"), 0),
        (("model", "junctions", 0, "area_m2"), 1e308),
        (("model", "junctions", 0, "permeability_m_per_s", "Ca"), -1),
        (("model", "junctions", 0, "residual_fraction", "Ca"), 1.01),
        (("model", "junctions", 0, "residual_fraction", "K"), True),
        (("model", "junctions", 0, "gate", "law"), "other"),
        (("model", "junctions", 0, "gate", "tau_s"), 0),
        (("model", "junctions", 0, "gate", "tau_s"), 1e-320),
        (("model", "junctions", 0, "gate", "sensitivity_per_V"), 1.79e308),
        (("model", "junctions", 0, "gate", "initial_gate"), 1.01),
        (("model", "junctions", 0, "gate", "initial_gate"), float("nan")),
        (("model", "junctions", 0, "gate", "repair"), True),
        (("execution", "capacity"), 2),
        (("execution", "membrane_capacity"), 2),
        (("execution", "channel_capacity"), 1),
        (("execution", "edge_capacity"), 1),
        (("execution", "edge_capacity"), True),
        (("execution", "backend"), "gpu"),
        (("execution", "extracellular_capacity"), 0),
        (("model", "extracellular", "volume_pL"), 0),
        (("model", "extracellular", "initial_amount_fmol", "Ca"), 0),
        (("model", "extracellular", "fixed_charge_equivalent_fmol"), 1000),
        (("experiment", "junction_controls"), []),
        (("experiment", "channel_controls"), []),
        (("experiment", "membrane_controls"), []),
        (("experiment", "junction_controls", 0, "junction_id"), "missing"),
        (("experiment", "junction_controls", 0, "schedule"), []),
        (("experiment", "junction_controls", 0, "schedule", 0, "time"), 0.001),
        (("experiment", "junction_controls", 0, "schedule", 0, "open_fraction"), 1.1),
        (("experiment", "junction_controls", 0, "schedule", 0, "open_fraction"), False),
    ],
)
def test_invalid_definition_refused(path, value):
    raw = definition(short())
    node = raw
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(ConfigError):
        parse_spec(raw)


def test_duplicate_edges_and_schedules_refused():
    for group in ("junctions", "junction_controls", "channel_controls", "membrane_controls"):
        raw = definition(short())
        target = raw["model"] if group == "junctions" else raw["experiment"]
        duplicate = copy.deepcopy(target[group][0])
        if group == "junctions":
            duplicate["id"] = "new_edge"
            duplicate["from_cell"], duplicate["to_cell"] = (
                duplicate["to_cell"],
                duplicate["from_cell"],
            )
        target[group].append(duplicate)
        with pytest.raises(ConfigError):
            parse_spec(raw)


@pytest.mark.parametrize("padded", [False, True])
def test_absent_channels_edges_and_pumps_are_supported(padded):
    raw = definition(short("single_mono"))
    raw["model"]["cells"][0]["channel"] = None
    raw["model"]["cells"][0]["membrane"]["pump"] = None
    raw["experiment"]["channel_controls"] = []
    raw["execution"].update(channel_capacity=2 if padded else 0, edge_capacity=2 if padded else 0)
    result = run(parse_spec(raw))
    assert np.all(result.history.gate == 0) and np.all(result.history.junction_gate == 0)
    assert np.all(result.history.pump_cycles == 0)


def test_edge_orientation_and_order_preserve_amount_rates():
    case = short()
    original = spec_for(case)
    state, layout = model.initial_values(original)
    held = PhysicalIonicGraphControl(*(v[0] for v in control_values(original, [0])))
    a = model.rhs(state, held, layout, layout.active, xp=np)
    raw = original.to_dict()
    raw["model"]["junctions"].reverse()
    for c in raw["model"]["junctions"]:
        c["from_cell"], c["to_cell"] = c["to_cell"], c["from_cell"]
    changed = parse_spec(raw)
    y, g = model.initial_values(changed)
    u = PhysicalIonicGraphControl(*(v[0] for v in control_values(changed, [0])))
    b = model.rhs(y, u, g, g.active, xp=np)
    np.testing.assert_allclose(a.amount_increment, b.amount_increment, atol=1e-16, rtol=1e-14)
    np.testing.assert_allclose(
        a.junction_transferred[:, :2], -b.junction_transferred[:, 1::-1], atol=1e-16
    )
    np.testing.assert_array_equal(a.junction_gate[:2], b.junction_gate[1::-1])


@pytest.mark.parametrize("field", model.STATE_TYPE._fields)
def test_every_padding_state_leaf_is_guarded(field):
    spec = spec_for(short())
    state, layout = model.initial_values(spec)
    getattr(state, field).flat[-1] = 1
    assert not model.domain_valid(state, layout, layout.active, xp=np)
    with pytest.raises(NumericalError):
        model.check_values(state, spec)


@pytest.mark.parametrize("field", ["gate", "junction_gate", "amount_increment"])
def test_invalid_real_state_cannot_be_accepted(field):
    spec = spec_for(short())
    cp = initialise(spec)
    state = model.STATE_TYPE(*(np.asarray(v).copy() for v in cp.state))
    getattr(state, field).flat[0] = -1
    with pytest.raises(NumericalError):
        validate_checkpoint(spec, replace(cp, state=state))


def test_independent_controls_and_all_off_gates():
    case = next(c for c in CASES if c.id == "star_mono_block_release")
    spec = spec_for(case)
    u = control_values(spec, [0.0137, 0.0271, 0.0679, 0.113, 0.3])
    assert u.junction[0, 0] == 0 and u.junction[0, 1] == 1
    assert u.channel[1, 1] == 0
    state, layout = model.initial_values(spec)
    rate = model.rhs(
        state, PhysicalIonicGraphControl(*(v[2] for v in u)), layout, layout.active, xp=np
    )
    for field in (
        "amount_increment",
        "leak_transferred",
        "pump_cycles",
        "dissipated_energy_pJ",
        "channel_transferred",
        "junction_transferred",
        "junction_dissipated_energy_pJ",
    ):
        assert np.all(getattr(rate, field) == 0)
    assert np.any(rate.gate != 0) and np.any(rate.junction_gate != 0)


def test_full_state_restart_branch_windows_and_eager(tmp_path):
    case = short("star_mono", end=0.008)
    spec = spec_for(case, samples=[0, 0.0013, 0.002, 0.0051, 0.008])
    result = run(spec)
    cp = result.checkpoint_at(0.002)
    write_snapshot(tmp_path / "snapshot", spec, cp)
    saved = load_snapshot(tmp_path / "snapshot")
    resumed = run(saved.spec, saved.checkpoint)
    for a, b in zip(result.history, resumed.history, strict=True):
        np.testing.assert_array_equal(a[2:], b)
    future = (ContactChange(0, 1), ContactChange(0.002, 0))
    changed = replace(
        spec, experiment=replace(spec.experiment, junctions=(future, spec.experiment.junctions[1]))
    )
    branched = run(changed, branch_checkpoint(spec, cp, changed))
    for a, b in zip(cp.state, branched.history, strict=True):
        np.testing.assert_array_equal(a, b[0])
    assert not np.array_equal(
        branched.history.amount_increment[-1], result.history.amount_increment[-1]
    )
    eager = run(replace(spec, execution=replace(spec.execution, jit=False)))
    for a, b in zip(result.history, eager.history, strict=True):
        np.testing.assert_allclose(a, b, atol=1e-12, rtol=1e-11)
    windows = list(iter_windows(spec, WindowPolicy(2, "full")))
    for field in model.STATE_TYPE._fields:
        merged = np.concatenate(
            [getattr(w.history, field)[0 if i == 0 else 1 :] for i, w in enumerate(windows)]
        )
        np.testing.assert_array_equal(merged, getattr(result.history, field))


def test_heterogeneous_worlds_equal_capacity_and_resources():
    specs = [spec_for(short(name)) for name in ("single_mono", "disconnected_mono", "star_mono")]
    batch = BatchSpec(tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs)), 3, 1000, 2**28)
    result = run_batch(batch)
    for w in result.worlds.values():
        scalar = run(w.spec)
        for a, b in zip(w.history, scalar.history, strict=True):
            np.testing.assert_array_equal(a, b)
    raw = batch.to_dict()
    raw["worlds"][1]["simulation"]["execution"]["channel_capacity"] = 5
    with pytest.raises(ConfigError, match="channel_capacity"):
        parse_batch(raw)
    with pytest.raises(ConfigError):
        plan_batch(replace(batch, max_working_bytes=1))
    spec = specs[0]
    assert trace_bytes(
        replace(spec, execution=replace(spec.execution, edge_capacity=100)), 1
    ) > trace_bytes(spec, 1)
    with pytest.raises(ConfigError, match="storage"):
        timeline(replace(spec, execution=replace(spec.execution, capacity=10**8)))
    with pytest.raises(ConfigError, match="0.001"):
        timeline(replace(spec, execution=replace(spec.execution, dt=0.004)))
    assert ionic.MAX_STEP == 0.01 and gated.MAX_STEP == 0.0005


def test_trial_and_cubic_gate_rejection():
    spec = spec_for(short())
    cp = initialise(spec)
    u = PhysicalIonicGraphControl(*(v[0] for v in control_values(spec, [0])))
    _, valid = rk4_checked_step(
        model.rhs, model.domain_valid, cp.state, 5.0, u, cp.layout, cp.layout.active
    )
    assert not bool(valid)
    y, layout = model.initial_values(spec)
    history = model.STATE_TYPE(*(np.stack((v, v)) for v in y))
    f0 = model.STATE_TYPE(*(np.zeros_like(v[:1]) for v in history))
    f1 = model.STATE_TYPE(*(np.zeros_like(v[:1]) for v in history))
    f0.junction_gate[0, 0], f1.junction_gate[0, 0] = 10, -10
    with pytest.raises(NumericalError, match="unit gate"):
        model.check_interpolants(np.array([0.0, 1.0]), history, f0, f1, layout)


def test_internal_transfer_never_touches_outside_and_weighted_charge():
    case = short("star_mono_internal")
    result = run(spec_for(case))
    assert np.all(result.history.extracellular_amount_increment == 0)
    assert np.any(result.history.junction_transferred[-1] != 0)
    np.testing.assert_allclose(
        np.sum(result.history.amount_increment, axis=-1),
        np.broadcast_to(
            np.sum(result.history.amount_increment[0], axis=-1),
            result.history.amount_increment.shape[:-1],
        ),
        atol=2e-13,
        rtol=0,
    )
    # Heterogeneous diagonal capacitance conserves weighted voltage, not raw voltage sum.
    voltage = result.observations.voltage_V[:, :3]
    cap = np.asarray(result.final.layout.capacitance[:3])
    assert abs(np.sum(cap * (voltage[-1] - voltage[0]))) < 1e-21
    assert abs(np.sum(voltage[-1] - voltage[0])) > 1e-8


@pytest.mark.parametrize("which", ["membrane", "junction"])
def test_statically_absent_routes_cannot_hold_dissipation(which):
    raw = definition(short("star_mono"))
    if which == "junction":
        raw["model"]["junctions"][0]["permeability_m_per_s"] = {s: 0 for s in ("Na", "K", "Cl")}
    else:
        cell = raw["model"]["cells"][2]
        cell["membrane"]["pump"] = None
        cell["membrane"]["passive"]["permeability_m_per_s"] = {s: 0 for s in ("Na", "K", "Cl")}
    spec = parse_spec(raw)
    state, layout = model.initial_values(spec)
    d = state.junction_dissipated_energy_pJ if which == "junction" else state.dissipated_energy_pJ
    d[0 if which == "junction" else 2] = 1e-12
    assert not model.domain_valid(state, layout, layout.active, xp=np)


@pytest.mark.parametrize("name", ["single_mono", "star_divalent"])
def test_terminal_and_empty_observation_continuations(name):
    spec = spec_for(short(name), samples=[0, 0.001])
    result = run(spec)
    resumed = run(spec, result.final)
    assert len(resumed.times) == 1 and len(resumed.observations.times) == 0
    for field in model.STATE_TYPE._fields:
        np.testing.assert_array_equal(
            getattr(resumed.history, field)[0], getattr(result.final.state, field)
        )


def test_whole_cubic_junction_voltage_catches_hidden_excursion():
    raw = definition(short("star_mono"))
    for cell in raw["model"]["cells"]:
        cell["channel"] = None
    raw["experiment"]["channel_controls"] = []
    spec = parse_spec(raw)
    state, layout = model.initial_values(spec)
    history = model.STATE_TYPE(*(np.stack((v, v)) for v in state))
    f0 = model.STATE_TYPE(*(np.zeros_like(v[:1]) for v in history))
    f1 = model.STATE_TYPE(*(np.zeros_like(v[:1]) for v in history))
    # Both cell voltage cubics stay within |F V/RT| <= 50, but their difference does not.
    for cell, sign in ((0, 1), (2, -1)):
        rate = sign * 4 * layout.capacitance[cell] / graph_data.QF
        f0.amount_increment[0, 0, cell], f1.amount_increment[0, 0, cell] = rate, -rate
    with pytest.raises(NumericalError, match="junction voltage"):
        model.check_interpolants(np.array([0.0, 1.0]), history, f0, f1, layout)


def test_outside_is_shared_even_for_disconnected_cells():
    spec = spec_for(short("disconnected_mono"))
    y, layout = model.initial_values(spec)
    u = PhysicalIonicGraphControl(*(v[0] for v in control_values(spec, [0])))
    original = model.readouts(y, u.membrane, layout, xp=np)[1]
    # Electrically neutral outside NaCl perturbation is visible to every membrane.
    y.extracellular_amount_increment[0, 0] = 1e-4
    y.extracellular_amount_increment[2, 0] = 1e-4
    assert model.domain_valid(y, layout, layout.active, xp=np)
    changed = model.readouts(y, u.membrane, layout, xp=np)[1]
    assert np.all(changed[0, :3] != original[0, :3])
    assert not any("bath" in name for name in layout._fields)
    rate = model.rhs(y, u, layout, layout.active, xp=np)
    np.testing.assert_allclose(
        np.sum(rate.amount_increment, axis=-1),
        -np.sum(rate.extracellular_amount_increment, axis=-1),
        atol=1e-16,
        rtol=1e-14,
    )


@pytest.mark.parametrize("outside", [False, True])
def test_countercharge_at_actual_stages_not_only_endpoints(outside):
    spec = spec_for(short())
    cp = initialise(spec)
    y = model.STATE_TYPE(*(np.asarray(v).copy() for v in cp.state))
    field = y.extracellular_amount_increment if outside else y.amount_increment
    field[0, 0] = 1e-7
    for xp in (np, jnp):
        state, layout = jax.device_put((y, cp.layout)) if xp is jnp else (y, cp.layout)
        assert not model.domain_valid(state, layout, layout.active, xp=xp)


@pytest.mark.parametrize("kind", ["outside_depletion", "outside_charge"])
def test_whole_cubic_outside_domains_catch_hidden_excursions(kind):
    spec = spec_for(short("single_mono_small"))
    y, layout = model.initial_values(spec)
    history = model.STATE_TYPE(*(np.stack((v, v)) for v in y))
    f0 = model.STATE_TYPE(*(np.zeros_like(v[:1]) for v in history))
    f1 = model.STATE_TYPE(*(np.zeros_like(v[:1]) for v in history))
    rate = -8 * layout.extracellular_amount_reference[0, 0] if kind == "outside_depletion" else 1e-7
    f0.extracellular_amount_increment[0, 0, 0] = rate
    f1.extracellular_amount_increment[0, 0, 0] = -rate
    with pytest.raises(NumericalError, match="finite inventory|countercharge"):
        model.check_interpolants(np.array([0.0, 1.0]), history, f0, f1, layout)


def test_explicit_outside_budget_and_independent_world_inventory():
    a = spec_for(short("single_mono_small"))
    b = spec_for(short("single_mono_large"))
    batch = BatchSpec((WorldSpec(1, a), WorldSpec(2, b)), 2, 1000, 2**28)
    results = run_batch(batch)
    for world in results.worlds.values():
        scalar = run(world.spec)
        for actual, expected in zip(world.history, scalar.history, strict=True):
            np.testing.assert_array_equal(actual, expected)
    assert not np.array_equal(
        results.worlds[1].history.extracellular_amount_increment[-1],
        results.worlds[2].history.extracellular_amount_increment[-1],
    )
    raw = batch.to_dict()
    raw["worlds"][1]["simulation"]["execution"]["extracellular_capacity"] = 3
    with pytest.raises(ConfigError, match="extracellular_capacity"):
        parse_batch(raw)
    assert trace_bytes(
        replace(a, execution=replace(a.execution, extracellular_capacity=100)), 1
    ) > trace_bytes(a, 1)
    with pytest.raises(ConfigError, match="storage"):
        timeline(replace(a, execution=replace(a.execution, extracellular_capacity=10**8)))


def test_increment_voltage_does_not_subtract_large_absolute_inventories():
    spec = spec_for(short("single_mono"))
    y, layout = model.initial_values(spec)
    delta = 1e-16
    y.amount_increment[0, 0], y.extracellular_amount_increment[0, 0] = delta, -delta
    assert layout.amount_reference[0, 0] + delta == layout.amount_reference[0, 0]
    expected = layout.voltage_reference[0] + graph_data.QF / layout.capacitance[0] * delta
    assert model.cell_voltage(y.amount_increment, layout, xp=np)[0] == expected
    assert expected != layout.voltage_reference[0]


def test_hidden_cycle_ledger_and_outside_state_survive_checkpoint(tmp_path):
    case = short("star_mono")
    w = case.world
    edge = replace(w.junctions[0], id="cycle_tail", from_cell=w.cells[0].id, to_cell=w.cells[1].id)
    world = replace(w, junctions=(*w.junctions, edge))
    case = replace(
        case, world=world, controls=(graph_data.Control(0, reference.graph.enabled(world)),)
    )
    spec = spec_for(case)
    cp = replace(initialise(spec), time=0.002, step_index=2)
    y = model.STATE_TYPE(*(np.asarray(v).copy() for v in cp.state))
    _, layout = model.initial_values(spec)
    incidence = np.zeros((3, 3))
    for e, (a, b) in enumerate(zip(layout.senders[:3], layout.receivers[:3], strict=True)):
        incidence[a, e], incidence[b, e] = -1, 1
    _, _, vh = np.linalg.svd(incidence)
    y.junction_transferred[0, :3] = 1e-5 * vh[-1]
    validate_checkpoint(spec, replace(cp, state=y))
    write_snapshot(tmp_path / "cycle", spec, replace(cp, state=y))
    loaded = load_snapshot(tmp_path / "cycle")
    for actual, expected in zip(loaded.checkpoint.state, y, strict=True):
        np.testing.assert_array_equal(actual, expected)


def test_python_objects_cannot_drop_owners_or_mutable_collections():
    spec = spec_for(short())
    invalid = [
        replace(spec.model, cells=list(spec.model.cells)),
        replace(spec.model, channels=spec.model.channels[::-1]),
        replace(
            spec.model,
            extracellular=replace(spec.model.extracellular, initial_amount_fmol=[1, 2, 3, 4]),
        ),
        replace(
            spec.model,
            membranes=(
                replace(spec.model.membranes[0], outside="private_bath"),
                *spec.model.membranes[1:],
            ),
        ),
    ]
    for model_spec in invalid:
        with pytest.raises(ConfigError):
            run(replace(spec, model=model_spec))
