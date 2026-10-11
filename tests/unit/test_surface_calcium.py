"""Closed resolved calcium: independent physics, owned inventories and replay."""

import copy
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.assembly_cell.io import flatten, load_checkpoint, write_checkpoint
from cells.assembly_cluster import engine as assembly
from cells.assembly_cluster.spec import parse_spec as parse_assembly
from cells.batch_io import load_batch_snapshot, write_batch_snapshot
from cells.core.batch import BatchSpec, WorldSpec, run_batch
from cells.core.batch_windows import iter_batch_windows
from cells.core.errors import NumericalError
from cells.core.runner import branch_checkpoint, run, timeline
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.windows import WindowPolicy, iter_windows
from cells.ensemble import ionic
from cells.ensemble.plan import jupiter_plan, plan
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import surface_calcium as model
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_checked_step
from tests.unit.test_assembly_cluster import ensemble_definition, event_histories, same
from tests.unit.test_spatial_calcium import same as same_pool
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.tissue import surface_calcium_fixtures as fixtures
from validation.tissue import surface_calcium_reference as reference

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")
ARMS = fixtures.ARMS


def evidence(name, value, arrays=None):
    if EVIDENCE:
        path = Path(EVIDENCE) / BACKEND
        path.mkdir(parents=True, exist_ok=True)
        (path / (name + ".json")).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
        if arrays is not None:
            np.savez_compressed(path / (name + ".npz"), **arrays)


def initial(raw=None):
    spec = parse_spec(fixtures.definition() if raw is None else raw)
    state, p = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    return spec, state, p, type(controls)(*(v[0] for v in controls))


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_registered_roundtrip_and_ensemble(backend):
    raw = fixtures.definition(backend=backend)
    spec = parse_spec(raw)
    assert parse_spec(spec.to_dict()) == spec
    assert get_model(spec.model) is model
    assert (
        ionic.parse_spec(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation == spec
    )
    for dt in (2.5e-5, 1.25e-5, 6.25e-6):
        timeline(parse_spec(raw | {"execution": raw["execution"] | {"dt": dt}}))
    assert len(model.STATE_TYPE._fields) == 34


@pytest.mark.parametrize("arm", ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_independent_stage_rates_and_accounting(arm, padded):
    raw = fixtures.definition(arm, padded=padded)
    spec, state, p, control = initial(raw)
    actual = model.readouts(state, control, p, xp=np)
    c = reference.bind(spec.to_dict())
    target, phi, proof = reference.evaluate(c, reference.initial(c), 0.0)
    ratio = assert_states(
        c,
        reference.flatten(c, actual.derivative._asdict()),
        target,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    np.testing.assert_allclose(
        np.r_[
            actual.field.potential_V[:2],
            actual.field.potential_V[p.active.size : p.active.size + 5],
        ],
        phi,
        rtol=3e-10,
        atol=3e-13,
    )
    assert actual.valid and abs(actual.field.energy_balance_pJ_s) < 1e-10
    assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-10
    assert model.check_values(state, spec)["max_energy_error"] == 0
    evidence(
        f"resolved-calcium-stage-{arm}-{'padded' if padded else 'compact'}",
        dict(
            status="passed",
            inputs=spec.to_dict(),
            max_error_over_budget=ratio,
            independent_root=proof,
        ),
    )


@pytest.mark.parametrize("kind", ["binding", "er_transfer", "ip3_binding"])
def test_internal_chemistry_uses_free_ions_without_charging_plasma(kind):
    spec, state, p, control = initial()
    changed = model.STATE_TYPE(*(np.array(v) for v in state))
    names = [s.id for s in spec.model.stores[0].species]
    cy, er = int(p.er_cytosol[0]), int(p.er_er[0])
    ca = names.index("Ca")
    if kind == "binding":
        indices = [names.index(k) for k in ("Ca", "B", "CaB")]
        changed.chemical_amount_increment[0, indices, cy] += 1e-4 * np.array([-1, -1, 1])
    elif kind == "er_transfer":
        changed.chemical_amount_increment[0, ca, [cy, er]] += 1e-4 * np.array([-1, 1])
    else:
        indices = [names.index(k) for k in ("IP3", "IP3_buffer", "IP3_bound")]
        changed.chemical_amount_increment[0, indices, cy] += (
            p.er_initial_amount[0, indices[0], cy] / 4 * np.array([-1, -1, 1])
        )
    assert model.domain_valid(changed, p, p.active, xp=np)
    np.testing.assert_array_equal(
        model.ensemble_voltage(state, p, spec, 0), model.ensemble_voltage(changed, p, spec, 0)
    )
    before, after = (model.readouts(s, control, p, xp=np) for s in (state, changed))
    if kind == "ip3_binding":
        assert (
            after.derivative.er_release_transferred[0, 0]
            != before.derivative.er_release_transferred[0, 0]
        )
        np.testing.assert_array_equal(
            after.derivative.er_release_transferred[1], before.derivative.er_release_transferred[1]
        )
    else:
        assert np.any(
            after.derivative.calcium_channel_transferred
            != before.derivative.calcium_channel_transferred
        )
        assert np.any(
            after.field.rates.junction_flux_fmol_s != before.field.rates.junction_flux_fmol_s
        )
    c = reference.bind(spec.to_dict())
    expected, _, proof = reference.evaluate(c, reference.flatten(c, changed._asdict()), 0.0)
    assert_states(
        c,
        reference.flatten(c, after.derivative._asdict()),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-10
    duplicate = changed._replace(amount_increment=np.array(changed.amount_increment))
    duplicate.amount_increment[int(p.plasma_ca), 0] += 1e-4
    assert not model.domain_valid(duplicate, p, p.active, xp=np)


@pytest.mark.parametrize("name", model.STATE_TYPE._fields)
def test_corrupt_complete_ledgers_or_inventories_are_rejected(name):
    spec, state, _, _ = initial()
    wrong = getattr(state, name).copy()
    wrong.flat[0] += 1.1 if name.endswith("gate") else (1e-16 if name.endswith("_C") else 0.01)
    with pytest.raises(NumericalError):
        model.check_values(state._replace(**{name: wrong}), spec)


@pytest.mark.parametrize(
    "fault",
    [
        "reservoir",
        "owner",
        "free_amount",
        "volume",
        "valence",
        "ip3",
        "cav",
        "plasma",
        "off_grid",
        "large_step",
    ],
)
def test_inconsistent_definitions_reject(fault):
    raw = fixtures.definition()
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    if fault == "reservoir":
        m["ionic"]["extracellular"][-1]["reservoir"] = True
        m["ionic"]["closure"]["gauge_reference"] = None
    elif fault == "owner":
        m["stores"][1]["cell_id"] = "cell_0"
    elif fault == "free_amount":
        m["stores"][0]["model"]["compartments"][0]["initial_amount_fmol"]["Ca"] *= 2
    elif fault == "volume":
        m["stores"][0]["model"]["compartments"][0]["volume_pL"] *= 2
    elif fault == "valence":
        m["plasma_transport"]["sodium_species"] = "Cl"
    elif fault == "ip3":
        m["ip3_release"][0]["species_id"] = "IP3_bound"
    elif fault == "cav":
        m["calcium_channels"][0]["initial_gate"]["h"] = 1.01
    elif fault == "plasma":
        m["plasma_transport"]["membranes"][0]["exchanger"]["law"] = "native_NCX"
    elif fault == "off_grid":
        e["observation_times"].insert(1, 0.000037)
    else:
        x["dt"] = 0.0001
    with pytest.raises(ConfigError):
        timeline(parse_spec(raw))


def test_failed_field_and_actual_controls_reject(monkeypatch):
    _, state, p, control = initial()
    bad = control._replace(calcium_channel=np.full_like(control.calcium_channel, 1.01))
    assert not model.control_domain_valid(state, bad, p, p.active, xp=np)
    original = model.field.solve
    monkeypatch.setattr(
        model.field, "solve", lambda *a, **k: original(*a, **k)._replace(converged=False)
    )
    assert not model.control_domain_valid(state, control, p, p.active, xp=np)
    assert all(np.isnan(v).all() for v in model.rhs(state, control, p, p.active, xp=np))


def test_chemical_event_is_an_accepted_observation_boundary():
    raw = fixtures.definition()
    raw["experiment"]["observation_times"].insert(1, 0.000037)
    changes = raw["experiment"]["store_controls"][0]["controls"]
    control = copy.deepcopy(changes[0]) | {"time": 0.000037}
    control["reactions"]["ip3_binding"] = 0.0
    changes.append(control)
    assert 0.000037 in timeline(parse_spec(raw))


def test_existing_resolved_kinetics_preserve_rates_and_energy():
    from tests.unit import test_surface_kinetic as previous

    for arm in previous.ARMS:
        previous.test_independent_stage_rates_and_accounting(arm, True)


@pytest.mark.parametrize("arm", ARMS)
def test_evolved_stage_preserves_owned_charge_and_independent_rates(arm):
    spec, y, p, control = initial(fixtures.definition(arm))
    h = spec.execution.dt
    for _ in range(3):

        def slope(state):
            assert model.control_domain_valid(state, control, p, p.active, xp=np)
            return model.rhs(state, control, p, p.active, xp=np)

        def increment(rate, factor, state=y):
            return model.STATE_TYPE(*(v + factor * h * d for v, d in zip(state, rate, strict=True)))

        a = slope(y)
        b = slope(increment(a, 0.5))
        c = slope(increment(b, 0.5))
        d = slope(increment(c, 1.0))
        y = model.STATE_TYPE(
            *(
                v + h / 6 * (a + 2 * b + 2 * c + d)
                for v, a, b, c, d in zip(y, a, b, c, d, strict=True)
            )
        )
        assert model.control_domain_valid(y, control, p, p.active, xp=np)
    context = reference.bind(spec.to_dict())
    expected, _, proof = reference.evaluate(context, reference.flatten(context, y._asdict()), 3 * h)
    actual = model.rhs(y, control, p, p.active, xp=np)
    ratio = assert_states(
        context,
        reference.flatten(context, actual._asdict()),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-10
    evidence(
        "resolved-calcium-evolved-stage-" + arm,
        dict(
            status="passed",
            checks=model.check_values(y, spec),
            max_error_over_budget=ratio,
            independent_root=proof,
        ),
    )


def test_new_model_rejects_held_bath_with_explicit_scope():
    raw = fixtures.definition()
    raw["model"]["ionic"]["extracellular"][-1]["reservoir"] = True
    raw["model"]["ionic"]["closure"]["gauge_reference"] = None
    with pytest.raises(ConfigError, match="finite outside inventories"):
        parse_spec(raw)


def test_absent_routes_and_zero_reaction_capacity_keep_zero_ledgers():
    raw = fixtures.definition()
    for store, control in zip(
        raw["model"]["stores"], raw["experiment"]["store_controls"], strict=True
    ):
        store["model"]["reactions"] = []
        store["model"]["membrane"]["pump"] = None
        control["controls"][0]["reactions"] = {}
    raw["execution"]["reaction_capacity"] = 0
    for route in raw["model"]["plasma_transport"]["membranes"]:
        route["pump"], route["exchanger"] = None, None
    for channel in raw["model"]["calcium_channels"]:
        channel["max_permeability_m_per_s"] = 0.0
    spec, state, p, control = initial(raw)
    rates = model.rhs(state, control, p, p.active, xp=np)
    for k in (
        "reaction_extent",
        "reaction_dissipated_energy_pJ",
        "er_pump_transferred",
        "er_metabolic_work_pJ",
        "plasma_pump_cycles",
        "plasma_exchange_cycles",
        "plasma_metabolic_work_pJ",
        "calcium_channel_transferred",
    ):
        assert not np.any(getattr(rates, k))
    c = reference.bind(spec.to_dict())
    expected, _, _ = reference.evaluate(c, reference.initial(c), 0.0)
    assert_states(
        c,
        reference.flatten(c, rates._asdict()),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )


@pytest.fixture(scope="module")
def trajectories(tmp_path_factory):
    directory = tmp_path_factory.mktemp("resolved-calcium-trajectories")
    values = {}
    for arm in ARMS:
        value = run(parse_spec(fixtures.definition(arm, backend=BACKEND)))
        assert all(v.device.platform == BACKEND for v in value.final.state)
        write_run(directory / arm, value, checkpoint_times=(0.001,))
        evidence(
            "resolved-calcium-saved-" + arm,
            dict(status="passed", inputs=value.spec.to_dict(), diagnostics=value.diagnostics),
            {
                **{k: np.asarray(v) for k, v in value.history._asdict().items()},
                **{"observed_" + k: v for k, v in vars(value.observations).items()},
            },
        )
        values[arm] = value
    return values


@pytest.fixture(scope="module")
def references():
    return {arm: reference.integrate(fixtures.definition(arm)) for arm in ARMS}


@pytest.mark.parametrize("arm", ARMS)
def test_independent_trajectories_and_complete_accounting(arm, trajectories, references):
    value, expected = trajectories[arm], references[arm]
    c = reference.bind(value.spec.to_dict())
    ratio = assert_states(
        c, reference.flatten(c, vars(value.observations)), np.asarray(expected["state"]), atol=2e-11
    )
    np.testing.assert_allclose(
        np.c_[
            value.observations.cell_potential_V[:, :2],
            value.observations.extracellular_potential_V[:, :5],
        ],
        expected["potential_V"],
        rtol=3e-9,
        atol=2e-8,
    )
    assert value.diagnostics["max_energy_error"] < model.ENERGY_ATOL_PJ
    assert not np.any(value.history.reservoir_supplied)
    assert not np.any(value.history.electrode_charge_transferred_C)
    if arm in ("blocked", "release"):
        before = (
            value.times <= 0.00073 if arm == "release" else np.ones(len(value.times), dtype=bool)
        )
        for k in (
            "junction_transferred",
            "channel_transferred",
            "pump_cycles",
            "calcium_channel_transferred",
            "plasma_pump_cycles",
            "plasma_exchange_cycles",
            "er_release_transferred",
        ):
            assert not np.any(getattr(value.history, k)[before])
        assert np.any(value.history.calcium_gate[before][-1] != value.history.calcium_gate[0])
    evidence(
        "resolved-calcium-trajectory-" + arm,
        dict(
            status="passed",
            max_state_error_over_budget=ratio,
            independent_reference=expected,
            diagnostics=value.diagnostics,
        ),
    )


def test_timestep_refinement(trajectories, references):
    raw = trajectories["baseline"].spec.to_dict()
    c = reference.bind(raw)
    expected = np.asarray(references["baseline"]["state"])
    errors = []
    for dt in (2.5e-5, 1.25e-5, 6.25e-6):
        raw["execution"]["dt"] = dt
        value = trajectories["baseline"] if dt == 2.5e-5 else run(parse_spec(raw))
        actual = reference.flatten(c, vars(value.observations))
        assert_states(c, actual, expected)
        errors.append(float(np.max(np.abs(actual - expected))))
    assert errors[-1] <= max(errors[0] * 0.2, 3e-13)
    evidence(
        "resolved-calcium-refinement",
        dict(
            status="passed",
            dt_s=[2.5e-5, 1.25e-5, 6.25e-6],
            max_errors=errors,
            roundoff_floor=3e-13,
        ),
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
    kept, valid = compute(state, control, 0.000025)
    assert not valid
    exact(kept, state)
    # The initial state/control is valid here; an unresolved physical trial
    # exceeds the voltage/inventory domain. The complete state must be retained.
    valid_control = control._replace(junction=jax.numpy.zeros_like(control.junction))
    kept, valid = compute(state, valid_control, 1e6)
    assert not valid
    exact(kept, state)


def test_complete_disk_fresh_process_restart_branch_and_windows(trajectories, tmp_path):
    value = trajectories["baseline"]
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
    for group in raw["experiment"]["calcium_channel_controls"]:
        group["schedule"].append(dict(time=0.001, availability=0.0))
    for group in raw["experiment"]["plasma_controls"]:
        group["schedule"].append(dict(time=0.001, pump=0.0, exchanger=0.0))
    for group in raw["experiment"]["store_controls"]:
        group["controls"].append(
            copy.deepcopy(group["controls"][0]) | dict(time=0.001, release=0.0)
        )
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
    for name in (
        "calcium_channel_transferred",
        "plasma_pump_cycles",
        "plasma_exchange_cycles",
        "er_release_transferred",
    ):
        np.testing.assert_array_equal(
            getattr(changed.history, name)[-1], getattr(checkpoint.state, name)
        )
    assert np.any(changed.history.channel_gate[-1] != checkpoint.state.channel_gate)
    assert np.any(changed.history.junction_gate[-1] != checkpoint.state.junction_gate)
    assert np.any(changed.history.calcium_gate[-1] != checkpoint.state.calcium_gate)
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
        timeout=1800,
    )
    (tmp_path / "fresh.stdout.log").write_text(process.stdout)
    (tmp_path / "fresh.stderr.log").write_text(process.stderr)
    process.check_returncode()
    exact(load_snapshot(tmp_path / "fresh/checkpoint_final").checkpoint.state, resumed.final.state)
    evidence(
        "resolved-calcium-restart",
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
    expected = [trajectories[a] for a in ("baseline", "release")]
    batch = BatchSpec(
        tuple(WorldSpec(i + 10, v.spec) for i, v in enumerate(expected)), 2, 200, 2**29
    )
    result = run_batch(batch)
    for identity, value in result.worlds.items():
        exact(value.history, expected[identity - 10].history)
    reordered = run_batch(BatchSpec(tuple(reversed(batch.worlds)), 2, 200, 2**29))
    for identity in (10, 11):
        exact(reordered.worlds[identity].history, result.worlds[identity].history)
        single = BatchSpec((batch.worlds[identity - 10],), 1, 100, 2**29)
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
        "resolved-calcium-partition",
        dict(
            status="passed",
            world_ids=[10, 11],
            comparison="bitwise",
            independent_restart_times=[0.001, 0.002],
            reordered=True,
        ),
    )


def test_ensemble_endpoint_reports_real_patch_voltages_and_complete_state(trajectories):
    raw = trajectories["baseline"].spec.to_dict()
    spec = ionic.parse_spec(
        dict(
            model="ionic_worlds@1", simulation=raw, worlds=1, window_steps=7, max_wall_seconds=2400
        )
    )
    checkpoints, report = ionic.run(spec, backend=BACKEND)
    exact(checkpoints[1].state, trajectories["baseline"].final.state)
    assert report["final_voltage_axis"] == "membrane_patch"
    np.testing.assert_allclose(
        report["final_voltage_V"][0],
        trajectories["baseline"].observations.membrane_voltage_V[-1, :4],
        rtol=0,
        atol=3e-13,
    )
    evidence("resolved-calcium-ensemble", dict(status="passed", report=report))


def test_cpu_gpu_complete_saved_states_and_observations(trajectories, coupled):
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
            Path(EVIDENCE) / "cpu" / ("resolved-calcium-saved-" + arm + ".npz"),
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
    with np.load(Path(EVIDENCE) / "cpu/resolved-calcium-assembly.npz", allow_pickle=False) as saved:
        arrays = flatten(coupled[1])
        assert set(arrays) == set(saved.files)
        for name, value in arrays.items():
            if np.asarray(value).dtype.kind in "bui":
                np.testing.assert_array_equal(value, saved[name], err_msg=name)
            else:
                atol = 3e-25 if name.endswith("_C") else 3e-13
                np.testing.assert_allclose(value, saved[name], rtol=3e-10, atol=atol, err_msg=name)
            count += value.size
    evidence(
        "resolved-calcium-cpu-gpu",
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


@pytest.fixture(scope="module")
def coupled():
    spec = parse_assembly(fixtures.assembly_definition(backend=BACKEND))
    state, report = assembly.run(spec, backend=BACKEND)
    evidence("resolved-calcium-assembly", report | {"status": "passed"}, flatten(state))
    return spec, state, report


def test_assembly_event_reference(coupled):
    spec, state, report = coupled
    events = event_histories(spec, state, 0)
    times = sorted({0.0, *(e[0] for rows in events.values() for e in rows)})
    segments = []
    for time in times:
        levels = []
        for binding in spec.pools:
            past = [e for e in events[binding.cell_id] if e[0] <= time]
            mask, bonds = (
                past[-1][1:3] if past else (binding.pool.initial_mask, binding.pool.initial_bonds)
            )
            levels.append(
                binding.active_availability
                if bonds.bit_count() >= mask.bit_count()
                else binding.inactive_availability
            )
        segments.append((time, levels))
    assert len(segments) > 1 and len({tuple(v) for _, v in segments}) > 1
    raw = spec.ionic.to_dict()
    raw["experiment"]["observation_times"] = [spec.pool.end_time_s]
    expected = reference.integrate(raw, channel_segments=segments)
    c = reference.bind(raw)
    ratio = assert_states(
        c,
        reference.flatten(c, {k: np.asarray(v)[0:1] for k, v in state.ionic._asdict().items()}),
        np.asarray(expected["state"]),
    )
    assert report["final_voltage_axis"] == "membrane_patch"
    assert np.asarray(report["final_voltage_V"]).shape == (spec.pool.worlds, 4)
    assert len(report["calcium_channels"]["gate"][0][0]) == 4
    evidence(
        "resolved-calcium-assembly-reference",
        dict(
            status="passed",
            max_state_error_over_budget=ratio,
            segments=segments,
            independent_reference=expected,
        ),
    )


def test_assembly_restart_partition_and_ligand_response(coupled, tmp_path):
    spec, state, _ = coupled
    half, _ = assembly.run(spec, backend=BACKEND, until=0.001)
    write_checkpoint(tmp_path / "assembly", spec, half, backend=BACKEND)
    saved, checkpoint, _ = load_checkpoint(tmp_path / "assembly", backend=BACKEND)
    continued, _ = assembly.run(replace(saved, window_ticks=23), backend=BACKEND, state=checkpoint)
    same(continued, state)
    for i in range(spec.pool.worlds):
        raw = spec.to_dict()
        for binding in raw["pools"]:
            binding["pool"].update(worlds=1, world_id_start=spec.pool.world_id_start + i)
        partition, _ = assembly.run(parse_assembly(raw), backend=BACKEND)
        same(partition, jax.tree.map(lambda v, i=i: np.asarray(v)[i : i + 1], state))
    raw = spec.to_dict()
    for binding in raw["ionic"]["model"]["ip3_release"]:
        binding["activation_mM"] *= 10
    reduced, _ = assembly.run(parse_assembly(raw), backend=BACKEND)
    same_pool(reduced.pool, state.pool)
    ca = [s.id for s in spec.ionic.model.stores[0].species].index("Ca")
    difference = float(
        np.max(
            np.abs(
                reduced.ionic.chemical_amount_increment[:, :, ca, :]
                - state.ionic.chemical_amount_increment[:, :, ca, :]
            )
        )
    )
    assert difference > 1e-10
    evidence(
        "resolved-calcium-assembly-replay",
        {
            "status": "passed",
            "comparison": "bitwise",
            "calcium_response_fmol": difference,
            "unchanged_random_events": True,
        },
    )


def test_sixteen_gpu_planning_keeps_worlds_and_model():
    raw = ensemble_definition()
    raw["arms"][0]["definition"] = fixtures.assembly_definition()
    for binding in raw["arms"][0]["definition"]["pools"]:
        for key in ("worlds", "world_id_start", "seed"):
            binding["pool"].pop(key, None)
    local, future = plan(raw, 1), jupiter_plan(raw, 4)
    assert local["tasks"] == future["tasks"]
    assert future["deployment"]["maximum_target_gpus"] == 16
    assert not future["deployment"]["remote_execution_qualified"]
    assert all(
        t["definition"]["ionic"]["model"]["id"] == "resolved_calcium@1" for t in future["tasks"]
    )


def test_assembly_aggregation_retains_owned_ligand(coupled):
    from cells.ensemble.cluster import aggregate

    _, _, report = coupled
    row = report | {"arm": "tissue", "wall_start": 0.0, "wall_end": 1.0}
    result = aggregate([row, row])["tissue"]
    assert result["physical_model"] == "resolved_calcium@1"
    for k in ("cytosol_mM", "release_fraction"):
        np.testing.assert_array_equal(
            result["ip3"][k + "_sum_over_worlds"], 2 * np.sum(report["ip3"][k], axis=0)
        )
    missing = dict(row)
    missing.pop("ip3")
    with pytest.raises(ValueError, match="IP3"):
        aggregate([row, missing])
