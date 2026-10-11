"""CORE-006 production assembly: independent physics, guards and engine contracts."""

import copy
import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec, parse_batch, run_batch
from cells.core.batch_windows import iter_batch_windows
from cells.core.errors import NumericalError
from cells.core.resources import trace_bytes
from cells.core.runner import branch_checkpoint, run, timeline, validate_checkpoint
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, PumpChange, parse_spec
from cells.core.state import initialise
from cells.core.windows import WindowPolicy, iter_windows
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import bioelectric_cell as old_model
from cells.models import multispecies_membrane as model
from cells.numerics.fixed_step import rk4_checked_step
from cells.processes.electrochemistry import F, R, ghk_leak
from tests import multispecies_numerical_checks as checks
from tests import reference_multispecies as reference
from tests.multispecies_fixtures import canonical_values, definition, spec_for
from tests.reference_multispecies_dynamics import (
    integrate_reference,
    load_panel,
    sample_record,
)

ROOT = Path(__file__).resolve().parents[2]
PLAN, CASES = load_panel()
REFERENCE = ROOT / "runs/num-006-2026-09-09/reference-01"


def short_case(index=7, end=0.04):
    return replace(CASES[index], horizon_s=end, controls=(CASES[index].controls[0],))


@pytest.fixture
def data():
    return definition(short_case())


@pytest.mark.parametrize("index", [0, 7])
def test_schema_roundtrip_and_complete_array_ownership(index):
    spec = spec_for(short_case(index), capacity=4, membrane_capacity=3)
    assert parse_spec(spec.to_dict()) == spec
    cp = initialise(spec)
    count = len(spec.model.species_ids)
    assert cp.state.amount.shape == (count, 4)
    assert cp.state.leak_transferred.shape == (count, 3)
    assert cp.state.dissipated_energy_pJ.shape == (3,)
    assert all(v.dtype == np.float64 for v in cp.state)
    assert cp.layout.valence.dtype == cp.layout.stoichiometry.dtype == np.int64
    np.testing.assert_array_equal(cp.layout.amount_reference, cp.state.amount)
    assert float(cp.layout.fixed_charge_equivalent[0]) == spec.model.fixed_charge_equivalent_fmol
    assert float(cp.layout.bath_background_charge[0]) == spec.model.bath_background_charge_mM
    assert len(set(cp.state._fields + cp.layout._fields)) == len(cp.state) + len(cp.layout)
    assert model.batch_signature(spec.model) == (count,)


@pytest.mark.parametrize(
    "path,value",
    [
        (("model", "id"), "cells.multispecies_membrane_reference@1"),
        (("model", "species"), []),
        (("model", "species", 3, "id"), "Na"),
        (("model", "species", 3, "id"), []),
        (("model", "species", 3, "id"), "bad/name"),
        (("model", "species", 3, "valence"), 0),
        (("model", "species", 3, "valence"), 4),
        (("model", "species", 3, "valence"), True),
        (("model", "species", 3, "valence"), 2.0),
        (("model", "cell", "id"), "bath_0"),
        (("model", "cell", "initial_amount_fmol", "Ca"), 0),
        (("model", "cell", "initial_amount_fmol", "Ca"), -1),
        (("model", "cell", "initial_amount_fmol", "Ca"), True),
        (("model", "cell", "initial_amount_fmol", "Ca"), 1e308),
        (("model", "cell", "initial_amount_fmol", "unknown"), 1),
        (("model", "cell", "volume_pL"), 0),
        (("model", "cell", "volume_pL"), 1e-320),
        (("model", "cell", "fixed_charge_equivalent_fmol"), -142),
        (("model", "cell", "fixed_charge_equivalent_fmol"), float("nan")),
        (("model", "cell", "initial_voltage_V"), 0),
        (("model", "bath", "concentration_mM", "Ca"), 0),
        (("model", "bath", "background_charge_mM"), 0),
        (("model", "bath", "background_charge_mM"), False),
        (("model", "bath", "temperature_K"), 1e308),
        (("model", "membrane", "inside"), "missing"),
        (("model", "membrane", "outside"), "missing"),
        (("model", "membrane", "area_m2"), 1e-320),
        (("model", "membrane", "specific_capacitance_F_per_m2"), -1),
        (("model", "membrane", "passive", "law"), "arbitrary_expression"),
        (("model", "membrane", "passive", "permeability_m_per_s", "Ca"), -1),
        (("model", "membrane", "passive", "permeability_m_per_s", "Na"), float("inf")),
        (("model", "membrane", "pump", "id"), "cell_0"),
        (("model", "membrane", "pump", "law"), "generic_atpase"),
        (("model", "membrane", "pump", "roles", "sodium"), "Ca"),
        (("model", "membrane", "pump", "roles", "potassium"), "Na"),
        (("model", "membrane", "pump", "stoichiometry", "Na"), -2),
        (("model", "membrane", "pump", "stoichiometry", "Na"), -3.0),
        (("model", "membrane", "pump", "stoichiometry", "Ca"), 0),
        (("model", "membrane", "pump", "capacity_fmol_per_s"), 1e308),
        (("experiment", "membrane_controls", "membrane_id"), "wrong"),
        (("experiment", "membrane_controls", "leak"), []),
        (("experiment", "membrane_controls", "pump", 0, "time"), 0.001),
        (("experiment", "membrane_controls", "pump", 0, "multiplier"), 2),
        (("experiment", "membrane_controls", "leak", 0, "multipliers", "Ca"), False),
        (("experiment", "observation_times"), [0.02, 0]),
        (("experiment", "observation_times"), []),
        (("execution", "capacity"), 0),
        (("execution", "membrane_capacity"), 0),
        (("execution", "edge_capacity"), 1),
        (("execution", "material_balance_atol_fmol", "Ca"), 0),
        (("execution", "material_balance_atol_fmol", "extra"), 1e-10),
        (("execution", "backend"), "gpu"),
        (("execution", "precision"), "float32"),
        (("execution", "solver"), "radau"),
        (("execution", "jit"), 1),
    ],
)
def test_invalid_definition_is_refused(data, path, value):
    node = data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(ConfigError):
        parse_spec(data)


def test_no_silent_drop_in_python_schema():
    spec = spec_for(short_case())
    for changed in (
        replace(spec.model, stoichiometry=(-3, 2, 0, 1)),
        replace(spec.model, species_ids=("Na", "Na", "Cl", "Ca")),
        replace(spec.model, species_ids=([], "K", "Cl", "Ca")),
        replace(spec.model, pump_id=None),
    ):
        with pytest.raises(ConfigError):
            run(replace(spec, model=changed))
    with pytest.raises(ConfigError):
        run(replace(spec, experiment=replace(spec.experiment, leak=(PumpChange(0, 1),))))


@pytest.mark.parametrize("index", [0, 7])
@pytest.mark.parametrize("leak,pump", [(1.0, 1.0), (0.0, 0.0), (0.3, 0.7), (1.0, 0.0)])
def test_instantaneous_kernel_matches_independent_scalar_reference(index, leak, pump):
    case = short_case(index)
    spec = spec_for(case, capacity=3, membrane_capacity=2)
    state, layout = model.initial_values(spec)
    control = control_values(spec, [0])[0]
    control[:-1, 0], control[-1, 0] = leak, pump
    expected = reference.evaluate(
        case.parameters, leak_control=(leak,) * case.species_count, pump_control=pump
    )
    rhs = model.rhs(state, control, layout, layout.active, xp=np)
    np.testing.assert_allclose(
        rhs.amount[:, 0], expected.amount_rate_fmol_per_s, rtol=3e-12, atol=1e-14
    )
    np.testing.assert_allclose(
        rhs.leak_transferred[:, 0], expected.passive_fmol_per_s, rtol=3e-12, atol=1e-14
    )
    assert rhs.pump_cycles[0] == pytest.approx(
        expected.pump_cycles_fmol_per_s, rel=3e-12, abs=1e-14
    )
    assert rhs.dissipated_energy_pJ[0] == pytest.approx(
        1e12 * (sum(expected.passive_dissipation_W) + expected.pump_dissipation_W),
        rel=3e-12,
        abs=1e-11,
    )
    for v in rhs:
        assert np.all(v[..., 1:] == 0)
    device = initialise(spec)
    compiled = jax.jit(model.rhs)(device.state, control, device.layout, device.layout.active)
    for a, b in zip(compiled, rhs, strict=True):
        np.testing.assert_allclose(a, b, rtol=3e-12, atol=1e-14)


@pytest.mark.parametrize("valence", [-3, -2, -1, 1, 2, 3])
def test_signed_valence_law_has_correct_limits_and_orientation(valence):
    for x in (-40.0, -1.0, -1e-8, 0.0, 1e-8, 1.0, 40.0):
        v = x * R * 298.15 / (valence * F)
        expected = reference.passive_flux(valence, 0.001, 2.0, v, 298.15, 1e-9, 1e-10)
        result = ghk_leak(0.001, 2.0, v, valence, 298.15, 1e-9, 1e-10, 1.0, xp=np)
        assert result == pytest.approx(expected, rel=3e-12, abs=1e-14)
        reverse = ghk_leak(2.0, 0.001, -v, valence, 298.15, 1e-9, 1e-10, 1.0, xp=np)
        assert result == -reverse


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_complete_panel_against_frozen_independent_refined_reference(case):
    payload = REFERENCE / case.id / "refined.npz"
    if payload.exists():
        receipt = json.loads((REFERENCE / "verification.json").read_text())
        assert (
            hashlib.sha256(payload.read_bytes()).hexdigest()
            == receipt["files_sha256"][f"{case.id}/refined.npz"]
        )
        with np.load(payload, allow_pickle=False) as saved:
            oracle = dict(saved)
    else:
        oracle, _ = integrate_reference(case, PLAN["references"][-1])
        oracle["sample_times_s"] = np.unique(
            np.r_[timeline(spec_for(case)), np.linspace(0, case.horizon_s, 251)]
        )
        oracle["sample_state"] = sample_record(case, oracle, "Radau", oracle["sample_times_s"])
    result = run(spec_for(case, samples=oracle["sample_times_s"]))
    record = case.definition()
    for times, state in (
        (result.times, result.history),
        (result.observations.times, result.observations),
    ):
        actual = canonical_values(case, state)
        expected = sample_record(case, oracle, "Radau", times)
        assert checks.errors(record, actual, expected, PLAN["trajectory_limits"])["pass"]
        assert checks.inspect_samples(record, times, actual, PLAN["accounting_limits"])["pass"]
        checks.control_checks(record, times, actual)
    obs = result.observations
    assert np.all(obs.dissipation_rate_pJ_per_s >= -1e-12)
    np.testing.assert_allclose(
        obs.bath_exchange_fmol[:, :, 0],
        -(obs.leak_transferred[:, :, 0] + obs.pump_cycles[:, :1] * case.parameters.stoichiometry),
        atol=0,
        rtol=0,
    )


@pytest.mark.parametrize("index", [0, 7])
def test_eager_jit_padding_and_read_only_observations(index):
    case = short_case(index)
    a = run(spec_for(case, jit=False, samples=[0.0, 0.003, 0.01, 0.017, 0.04]))
    b = run(spec_for(case, jit=True, samples=a.observations.times))
    padded = run(spec_for(case, capacity=4, membrane_capacity=3, samples=a.observations.times))
    for left, right, extra in zip(a.history, b.history, padded.history, strict=True):
        np.testing.assert_allclose(left, right, rtol=1e-12, atol=1e-12)
        np.testing.assert_array_equal(right, extra[..., :1])
        assert np.all(extra[..., 1:] == 0)
    sparse = run(spec_for(case, samples=[case.horizon_s]))
    for left, right in zip(b.history, sparse.history, strict=True):
        np.testing.assert_array_equal(left, right)
    assert np.array_equal(a.observations.amount[2], a.history.amount[1])


def test_species_permutation_and_renaming_are_not_chemical_selectors(data):
    base = run(parse_spec(data))
    permuted = copy.deepcopy(data)
    permuted["model"]["species"] = [data["model"]["species"][i] for i in (3, 1, 0, 2)]
    other = run(parse_spec(permuted))
    np.testing.assert_allclose(
        base.history.amount[:, (3, 1, 0, 2)], other.history.amount, atol=3e-13, rtol=0
    )
    renamed = json.loads(
        json.dumps(data).replace('"Na"', '"sodium_role"').replace('"Ca"', '"divalent_tracer"')
    )
    renamed_result = run(parse_spec(renamed))
    for a, b in zip(base.history, renamed_result.history, strict=True):
        np.testing.assert_array_equal(a, b)
    assert renamed_result.spec.execution.material_balance_atol_fmol[-1] == 1e-12


def test_absent_pump_and_inactive_species_keep_charge(data):
    data["model"]["membrane"]["pump"] = None
    data["model"]["membrane"]["passive"]["permeability_m_per_s"]["Ca"] = 0.0
    result = run(parse_spec(data))
    assert np.all(result.history.pump_cycles == 0)
    assert np.all(result.history.leak_transferred[:, 3] == 0)
    assert np.all(result.history.amount[:, 3] == 0.001)
    state = result.final.state._replace(pump_cycles=np.array([1.0]))
    with pytest.raises(NumericalError):
        model.check_values(state, result.spec)
    empty = copy.deepcopy(data)
    del empty["model"]["cell"]["initial_amount_fmol"]["Ca"]
    with pytest.raises(ConfigError):
        parse_spec(empty)


@pytest.mark.parametrize("jit", [False, True])
def test_trial_refusal_does_not_repair_or_advance_state(data, jit):
    data["model"]["membrane"]["passive"]["permeability_m_per_s"]["Na"] = 1e-3
    spec = parse_spec(data)
    cp = initialise(spec)

    def step(state):
        return rk4_checked_step(
            model.rhs,
            model.domain_valid,
            state,
            0.01,
            control_values(spec, [0])[0],
            cp.layout,
            cp.layout.active,
        )

    result, ok = jax.jit(step)(cp.state) if jit else step(cp.state)
    assert not bool(ok)
    for a, b in zip(result, cp.state, strict=True):
        np.testing.assert_array_equal(a, b)
    with pytest.raises(NumericalError):
        run(replace(spec, execution=replace(spec.execution, jit=jit)))


def test_blocked_divalent_is_still_subject_to_domain(data):
    data["experiment"]["membrane_controls"]["leak"][0]["multipliers"]["Ca"] = 0
    spec = parse_spec(data)
    state, layout = model.initial_values(spec)
    state.amount[3, 0] = 0
    assert not model.domain_valid(state, layout, layout.active, xp=np)
    with pytest.raises(NumericalError):
        model.check_values(state, spec)
    state, layout = model.initial_values(spec)
    # At 30 RT/F a monovalent species is within the bound, but +2 is not.
    layout = layout._replace(voltage_reference=np.array([30 * R * 298.15 / F]))
    assert not model.domain_valid(state, layout, layout.active, xp=np)


def test_cubic_domain_inspects_unsampled_interior():
    spec = spec_for(short_case())
    state, layout = model.initial_values(spec)
    history = model.STATE_TYPE(*(np.stack((v, v)) for v in state))
    slope = model.STATE_TYPE(*(np.zeros_like(v) for v in state))
    slope.amount[3, 0] = -0.1
    left = model.STATE_TYPE(*(v[None] for v in slope))
    right = model.STATE_TYPE(*(-v for v in left))
    with pytest.raises(NumericalError, match="Cubic interior"):
        model.check_interpolants(np.array([0.0, 1.0]), history, left, right, layout)


@pytest.mark.parametrize("field", model.STATE_TYPE._fields)
def test_corrupt_state_and_padding_are_refused(field):
    spec = spec_for(short_case(), capacity=3, membrane_capacity=2)
    cp = initialise(spec)
    values = np.array(getattr(cp.state, field))
    values.flat[-1] = 1.0
    with pytest.raises(NumericalError):
        validate_checkpoint(spec, replace(cp, state=cp.state._replace(**{field: values})))


@pytest.mark.parametrize(
    "field",
    [
        "amount_reference",
        "voltage_reference",
        "fixed_charge_equivalent",
        "valence",
        "stoichiometry",
        "bath_background_charge",
        "species_codes",
    ],
)
def test_corrupt_immutable_layout_is_refused(field):
    spec = spec_for(short_case())
    cp = initialise(spec)
    values = np.array(getattr(cp.layout, field))
    values.flat[0] += 1
    with pytest.raises(ConfigError, match="layout"):
        validate_checkpoint(spec, replace(cp, layout=cp.layout._replace(**{field: values})))


def test_resource_estimates_scale_before_allocating(data, monkeypatch):
    mono, divalent = spec_for(short_case(0)), parse_spec(data)
    assert trace_bytes(divalent, 10) > trace_bytes(mono, 10)
    assert old_model.MAX_STEP == 0.005
    with pytest.raises(ConfigError, match="0.01"):
        timeline(replace(divalent, execution=replace(divalent.execution, dt=0.02)))

    def forbidden(_):
        raise AssertionError("Capacity allocation occurred before budget check")

    monkeypatch.setattr(model, "initial_values", forbidden)
    enormous = replace(
        divalent, execution=replace(divalent.execution, capacity=2**30, max_trace_bytes=100)
    )
    with pytest.raises(ConfigError, match="storage"):
        timeline(enormous)


def test_complete_restart_branch_and_terminal_observation(tmp_path):
    spec = spec_for(CASES[13], samples=[0, 0.203, 0.2035, 0.204, 0.4, 1.0])
    full = run(spec)
    write_run(tmp_path / "full", full, checkpoint_times=(0.203,))
    cp = full.checkpoint_at(0.203)
    write_snapshot(tmp_path / "checkpoint", spec, cp)
    saved = load_snapshot(tmp_path / "checkpoint")
    resumed = run(saved.spec, saved.checkpoint)
    start = np.flatnonzero(full.times == cp.time)[0]
    for a, b in zip(resumed.history, full.history, strict=True):
        np.testing.assert_array_equal(a, b[start:])
    changes = tuple(p for p in spec.experiment.pump if p.time < 0.203) + (PumpChange(0.203, 0.0),)
    changed = replace(spec, experiment=replace(spec.experiment, pump=changes))
    branched_cp = branch_checkpoint(spec, cp, changed)
    branched, uninterrupted = run(changed, branched_cp), run(changed)
    for a, b in zip(branched.history, uninterrupted.history, strict=True):
        np.testing.assert_array_equal(a, b[start:])
    for a, b in zip(branched.final.layout, cp.layout, strict=True):
        np.testing.assert_array_equal(a, b)
    assert np.all(branched.history.pump_cycles == cp.state.pump_cycles)
    terminal = run(spec, full.final)
    assert len(terminal.times) == len(terminal.observations.times) == 1
    for changed_model in (
        replace(spec.model, cell_id="new_cell"),
        replace(spec.model, valence=(1, 1, -1, -2)),
    ):
        with pytest.raises(ConfigError):
            branch_checkpoint(spec, cp, replace(spec, model=changed_model))
    worker = subprocess.run(
        [
            sys.executable,
            "-m",
            "cells",
            "resume",
            str(tmp_path / "checkpoint"),
            "--output",
            str(tmp_path / "resumed"),
        ],
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert worker.returncode == 0, worker.stderr
    with np.load(tmp_path / "resumed/trajectory.npz", allow_pickle=False) as values:
        for field, a in zip(resumed.history._fields, resumed.history, strict=True):
            np.testing.assert_array_equal(a, values[field])


def test_scalar_windows_and_independent_worlds_reuse_the_same_contract():
    specs = [
        spec_for(short_case(7, end), capacity=3, membrane_capacity=2, samples=[0.0, 0.013, end])
        for end in (0.04, 0.03)
    ]
    batch = BatchSpec(tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs)), 2, 100, 2**26)
    full = [run(s) for s in specs]
    batched = run_batch(batch)
    for i, (spec, expected) in enumerate(zip(specs, full, strict=True)):
        for a, b in zip(batched.worlds[i + 1].history, expected.history, strict=True):
            np.testing.assert_array_equal(a, b)
        parts = list(iter_windows(spec, WindowPolicy(2)))
        for field, values in zip(expected.history._fields, expected.history, strict=True):
            joined = np.concatenate(
                [getattr(p.history, field)[int(j > 0) :] for j, p in enumerate(parts)]
            )
            np.testing.assert_array_equal(joined, values)
    rounds = list(iter_batch_windows(batch, WindowPolicy(2)))
    assert len(rounds) == 2
    for world_id in (1, 2):
        for field in model.STATE_TYPE._fields:
            joined = np.concatenate(
                [
                    getattr(r.worlds[world_id].history, field)[int(i > 0) :]
                    for i, r in enumerate(rounds)
                    if world_id in r.worlds
                ]
            )
            np.testing.assert_array_equal(joined, getattr(full[world_id - 1].history, field))
    mixed = replace(
        batch,
        worlds=(
            batch.worlds[0],
            WorldSpec(2, spec_for(short_case(0), capacity=3, membrane_capacity=2)),
        ),
    )
    with pytest.raises(ConfigError, match="array axes"):
        parse_batch(mixed.to_dict())
