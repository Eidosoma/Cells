"""Full physical stages and history-preserving dynamic extracellular barriers."""

import json
import os
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from cells.core import environment_barrier_interventions_spec as schema
from cells.core.grid import EventGrid
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, digest, parse_spec
from cells.core.state import initialise
from cells.ensemble.ionic import parse_spec as parse_worlds
from cells.io import load_snapshot, write_snapshot
from cells.models import environment_barrier_interventions as model
from cells.models import surface_tissue as parent
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_step
from tests.environment_barrier_fixtures import definition
from validation.transport import environment_barrier_interventions_fixtures as fixtures
from validation.transport import environment_barrier_interventions_reference as reference


def evidence(name, report, arrays=None):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(folder) / "environment-barrier-interventions"
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + ".json")).write_text(
            json.dumps(report, indent=2, allow_nan=False, default=lambda v: np.asarray(v).tolist())
            + "\n"
        )
        if arrays is not None:
            np.savez_compressed(root / (name + ".npz"), **arrays)


@lru_cache
def initialized(case="partial", *, permuted=False, padded=True):
    raw = definition(case, permuted=permuted, padded=padded)
    spec = parse_spec(raw)
    state, layout = model.initial_values(spec)
    return raw, spec, state, layout


def control(spec, time):
    table = control_values(spec, [time])
    return type(table)(*(v[0] for v in table))


def budgets(c, target, *, rate=False):
    shapes = c["parent"]["shapes"]
    absolute = reference.passive.flatten(
        c["parent"],
        {
            k: np.full(
                s, (3e-23 if rate else 3e-25) if k.endswith("_C") else (3e-12 if rate else 2e-11)
            )
            for k, s in shapes.items()
        },
    )
    return np.r_[absolute, 3e-12 if rate else 1e-17] + (3e-10 if rate else 3e-9) * np.abs(target)


@pytest.mark.parametrize("case", fixtures.CASES)
@pytest.mark.parametrize("manufactured", [False, True])
def test_full_stage_field_material_and_energy_against_independent_reference(case, manufactured):
    raw, spec, initial, p = initialized(case, permuted=manufactured)
    context = reference.bind(raw)
    proofs, actual_rows, target_rows, budget_rows = [], [], [], []
    clocks = (0.0, 2e-6, 4.5e-6, 7e-6, 10e-6)
    for time in clocks:
        state = model.STATE_TYPE(*(np.array(v, copy=True) for v in initial))
        state = state._replace(phase_clock_s=np.asarray([time]))
        if manufactured:
            species = spec.model.species_ids.index("K")
            inside, outside = p.membrane_cell[0], p.membrane_outside[0]
            state.amount_increment[species, inside] -= 1e-5
            state.extracellular_amount_increment[species, outside] += 1e-5
            state.membrane_transferred[species, 0] += 1e-5
        assert model.domain_valid(state, p, p.active, xp=np)
        target, phi, proof = reference.evaluate(
            context, reference.flatten(context, state._asdict()), time
        )
        actual_state = model.rhs(state, control(spec, time), p, p.active, xp=np)
        actual = reference.flatten(context, actual_state._asdict())
        budget = budgets(context, target, rate=True)
        ratio = float(np.max(np.abs(actual - target) / budget))
        field = model.field_values(state, control(spec, time), p, xp=np)
        count, nout = len(spec.model.cells), len(spec.model.extracellular)
        actual_phi = np.r_[
            field.potential_V[:count], field.potential_V[p.active.size : p.active.size + nout]
        ]
        proofs.append(
            dict(
                time_s=time,
                error_over_budget=ratio,
                field=proof,
                energy_residual_pJ_s=float(field.energy_balance_pJ_s),
            )
        )
        actual_rows.append(actual)
        target_rows.append(target)
        budget_rows.append(budget)
        evidence(
            "stage-" + case + "-" + str(manufactured),
            dict(definition=raw, manufactured=manufactured, comparisons=proofs),
            dict(actual=actual_rows, reference=target_rows, budgets=budget_rows),
        )
        assert ratio <= 1
        assert field.converged and abs(field.energy_balance_pJ_s) < 1e-10
        np.testing.assert_allclose(actual_phi, phi, rtol=3e-10, atol=3e-13)


@pytest.mark.parametrize("case", ["init", "none", "blocked"])
def test_disabled_events_preserve_exact_parent_rates(case):
    _, spec, initial, p = initialized(case)
    state = initial._replace(phase_clock_s=np.asarray([4.5e-6]))
    u = control(spec, 4.5e-6)
    actual = model.rhs(state, u, p, p.active, xp=np)
    expected = parent.rhs(model.base_state(state), u, model.base_layout(p), p.active, xp=np)
    for a, b in zip(model.base_state(actual), expected, strict=True):
        np.testing.assert_array_equal(a, b)
    np.testing.assert_array_equal(actual.phase_clock_s, [1.0])


def test_duplicate_occurrences_do_not_multiply_opening():
    _, _, state, first = initialized("partial")
    _, _, _, repeated = initialized("duplicate")
    state = state._replace(phase_clock_s=np.asarray([4.5e-6]))
    a, b = model.signal_values(state, first, xp=np), model.signal_values(state, repeated, xp=np)
    for x, y in zip(a, b, strict=True):
        np.testing.assert_array_equal(x, y)


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_public_dispatch_and_world_admission(backend):
    raw = deepcopy(definition("partial", padded=True))
    raw["execution"]["backend"] = backend
    spec = parse_spec(raw)
    assert get_model(spec.model) is model
    assert parse_spec(spec.to_dict()) == spec
    assert spec.fingerprint == digest(spec.to_dict())
    assert parse_worlds(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation == spec
    state, layout = model.initial_values(spec)
    assert len(state) == 13
    evidence(
        "public-admission-" + backend,
        dict(
            definition=raw,
            state_fields=list(state._fields),
            layout_fields=list(layout._fields),
            scope="Input admission and NumPy preparation only; no GPU execution",
        ),
    )


def test_public_cpu_snapshot_preserves_complete_layout_and_state(tmp_path):
    spec = parse_spec(definition("partial", padded=True))
    checkpoint = initialise(spec)
    restored = load_snapshot(write_snapshot(tmp_path / "snapshot", spec, checkpoint))
    assert restored.spec == spec
    assert type(restored.checkpoint.state) is model.STATE_TYPE
    assert len(restored.checkpoint.state) == 13
    for a, b in zip(
        checkpoint.state + checkpoint.layout,
        restored.checkpoint.state + restored.checkpoint.layout,
        strict=True,
    ):
        np.testing.assert_array_equal(a, b)
    evidence("public-snapshot", dict(complete_initial_state_and_layout_exact=True))


@pytest.mark.parametrize(
    "fault",
    [
        "changed_parent",
        "changed_recipe",
        "changed_coefficients",
        "unknown_site",
        "empty_sites",
        "negative_amplitude",
        "excess_amplitude",
        "boolean_amplitude",
        "nonfinite",
        "reversed",
        "zero_transition",
        "outside_horizon",
        "capacity",
        "phase",
        "policy",
        "unknown_field",
        "schema_bool",
        "list_events",
        "implicit_capacity",
    ],
)
def test_invalid_owner_recipe_timing_and_domain_refused(fault):
    raw = deepcopy(definition())
    m, event = raw["model"], raw["model"]["intervention"]
    if fault == "changed_parent":
        m["faces"][0]["area_m2"] *= 2
    if fault == "changed_recipe":
        m["barrier_preparation"]["provenance"]["request"]["tight_factor"] *= 2
    if fault == "changed_coefficients":
        m["barrier_preparation"]["definition"]["model"]["faces"][0]["length_m"] *= 2
    if fault == "unknown_site":
        event["site_ids"] = ["missing"]
    if fault == "empty_sites":
        event["site_ids"] = []
    if fault == "negative_amplitude":
        event["amplitude"] = -0.1
    if fault == "excess_amplitude":
        event["amplitude"] = 1.1
    if fault == "boolean_amplitude":
        event["amplitude"] = True
    if fault == "nonfinite":
        event["change_s"] = float("nan")
    if fault == "reversed":
        event["on_s"], event["off_s"] = event["off_s"], event["on_s"]
    if fault == "zero_transition":
        event["change_s"] = 0
    if fault == "outside_horizon":
        event["off_s"] = 1
    if fault == "capacity":
        raw["execution"]["barrier_target_capacity"] = 0
    if fault == "phase":
        m["phase"] = "carry"
    if fault == "policy":
        m["timing_policy"] = "native_solver_loop"
    if fault == "unknown_field":
        event["dynamic_factor"] = 1
    if fault == "schema_bool":
        raw["schema_version"] = True
    if fault == "list_events":
        m["intervention"] = [event]
    if fault == "implicit_capacity":
        raw["execution"].pop("barrier_target_capacity")
    with pytest.raises(ConfigError):
        parse_spec(raw)


def test_transition_clock_and_runtime_factor_refusals():
    _, spec, state, p = initialized()
    u = control(spec, 0)
    with pytest.raises(ConfigError):
        model.check_steps(spec, np.asarray([1e-6]), control_values(spec, [0]))
    bad_clock = state._replace(phase_clock_s=np.asarray([-1e-6]))
    assert not model.domain_valid(bad_clock, p, p.active, xp=np)
    bad_layout = p._replace(barrier_amplitude=np.asarray([1.1]))
    assert not model.control_domain_valid(state, u, bad_layout, p.active, xp=np)
    assert all(np.isnan(v).all() for v in model.rhs(state, u, bad_layout, p.active, xp=np))
    checkpoint = initialise(spec)
    with pytest.raises(ConfigError):
        model.check_checkpoint(spec, replace(checkpoint, state=bad_clock))


def test_closed_barrier_retains_transfers_from_earlier_opening():
    raw = deepcopy(definition("reseal"))
    # A zero site modulator is an actually sealed species boundary; opening
    # cannot bypass it. Use a zero native tight factor to allow true reopening.
    from cells.core import environment_barrier_preparation as preparation

    request = deepcopy(raw["model"]["barrier_preparation"]["provenance"]["request"])
    request["tight_factor"] = 0.0
    request["regions"]["boundary_cell_sites"] = ["se"]
    request["regions"]["boundary_membrane_sites"] = []
    request["regions"]["neighbor_membrane_sites"] = []
    prepared = preparation.prepare(request)
    extra = {k: raw["model"][k] for k in ("intervention", "phase", "timing_policy")}
    raw["model"] = deepcopy(prepared.definition["model"])
    raw["model"].update(
        id=schema.MODEL_ID,
        **extra,
        barrier_preparation=dict(definition=prepared.definition, provenance=prepared.provenance),
    )
    spec = parse_spec(raw)
    initial, p = model.initial_values(spec)
    state = initial._replace(phase_clock_s=np.asarray([3e-6]))
    state = rk4_step(
        lambda y, *a: model.rhs(y, *a, xp=np), state, 1e-11, control(spec, 3e-6), p, p.active
    )
    closed = state._replace(phase_clock_s=np.asarray([1e-5]))
    signal = model.signal_values(closed, p, xp=np)
    sealed = p.face_factor == 0
    assert np.any(np.abs(closed.face_transferred[sealed]) > 0)
    np.testing.assert_array_equal(signal.face_factor[sealed], 0)
    assert not parent.domain_valid(model.base_state(closed), model.base_layout(p), p.active, xp=np)
    assert model.domain_valid(closed, p, p.active, xp=np)
    assert model.check_values(closed, spec)["max_energy_balance_error_pJ"] < parent.ENERGY_ATOL_PJ
    evidence("resealed-history", dict(prior_transfers_preserved=True, current_closed=True))


def test_observation_grid_contains_every_requested_boundary():
    _, spec, _, _ = initialized()
    grid = EventGrid(spec)
    for time in spec.experiment.observation_times:
        assert grid[grid.exact_index(time)] == time


@pytest.mark.parametrize("case", fixtures.CASES)
def test_independent_site_face_and_sodium_weight_diagnostics(case):
    raw, spec, state, p = initialized(case, permuted=True)
    context = reference.bind(raw)
    sites = raw["model"]["barrier_preparation"]["provenance"]["request"]["grid"]["site_ids"]
    for time in (0.0, 4.5e-6, 1e-5):
        actual = model.signal_values(state._replace(phase_clock_s=np.asarray([time])), p, xp=np)
        expected = reference.coefficients(context, time)
        target = [
            [expected["site_effective_m2_s"][s][name] for name in sites]
            for s in spec.model.species_ids
        ]
        faces = [
            [expected["face_m2_s"][s][f.id] for f in spec.model.faces]
            for s in spec.model.species_ids
        ]
        np.testing.assert_allclose(actual.site_diffusivity, target, rtol=5e-14, atol=1e-30)
        np.testing.assert_allclose(
            actual.face_diffusivity[:, p.face_active], faces, rtol=5e-14, atol=1e-30
        )
        np.testing.assert_allclose(
            actual.sodium_weight,
            [expected["sodium_weight"][name] for name in sites],
            rtol=5e-14,
            atol=1e-16,
        )
        np.testing.assert_allclose(actual.pulse, [expected["pulse"]], rtol=1e-9, atol=1e-16)


@pytest.mark.parametrize("case", ["partial", "reseal"])
def test_full_opening_resealing_history_and_refinement(case):
    raw, spec, _, _ = initialized(case, padded=False)
    context = reference.bind(raw)
    target = reference.integrate(raw)
    requested = np.asarray(target["times"])
    arrays = dict(
        times=requested, independent=target["state"], independent_potential=target["potential_V"]
    )
    records = []
    for refinement in (1, 2):
        current_spec = replace(
            spec, execution=replace(spec.execution, dt=spec.execution.dt / refinement)
        )
        grid = EventGrid(current_spec)
        times = np.asarray([grid[i] for i in range(len(grid))])
        state, p = model.initial_values(current_spec)
        controls = control_values(current_spec, times[:-1])
        model.check_steps(current_spec, np.diff(times), controls)
        history = [state]
        for i, step in enumerate(np.diff(times)):
            u = type(controls)(*(v[i] for v in controls))
            state = rk4_step(lambda y, *a: model.rhs(y, *a, xp=np), state, step, u, p, p.active)
            history.append(state)
        stacked = model.STATE_TYPE(*(np.stack(v) for v in zip(*history, strict=True)))
        selected = [grid.exact_index(float(t)) for t in requested]
        observed = np.stack([reference.flatten(context, history[i]._asdict()) for i in selected])
        bound = budgets(context, target["state"])
        ratio = float(np.max(np.abs(observed - target["state"]) / bound))
        physical_energy = []
        for time, flat, index in zip(requested, observed, selected, strict=True):
            row = history[index]
            energy = reference.free_energy_change(context, flat, float(time))
            energy += sum(
                float(np.sum(getattr(row, k)))
                for k in (
                    "membrane_dissipated_energy_pJ",
                    "junction_dissipated_energy_pJ",
                    "face_dissipated_energy_pJ",
                )
            )
            energy -= float(np.sum(row.reservoir_work_pJ) + np.sum(row.electrode_work_pJ))
            physical_energy.append(energy)
        prefix = "step" + str(refinement) + "__"
        arrays.update({prefix + k: v for k, v in stacked._asdict().items()})
        arrays.update(
            {
                prefix + "times": times,
                prefix + "observed": observed,
                prefix + "budgets": bound,
                prefix + "independent_energy_residual": physical_energy,
            }
        )
        records.append(
            dict(
                dt_s=current_spec.execution.dt,
                steps=len(times) - 1,
                error_over_budget=ratio,
                max_independent_energy_residual_pJ=max(map(abs, physical_energy)),
            )
        )
        evidence(
            "trajectory-" + case,
            dict(
                definition=raw,
                reference={k: v for k, v in target.items() if k not in ("state", "potential_V")},
                refinements=records,
                scope="Manufactured 10-us opening/resealing; no tissue equilibration "
                "or native full-loop parity",
            ),
            arrays,
        )
        assert ratio <= 1
        assert max(map(abs, physical_energy)) <= 1e-9
        diagnostics = model.check_values(stacked, current_spec)
        records[-1]["accounting"] = diagnostics
        observations = model.observe_history(times, stacked, p, requested, current_spec)
        arrays.update({prefix + "observation__" + k: v for k, v in vars(observations).items()})
    assert records[-1]["error_over_budget"] <= max(0.01, records[0]["error_over_budget"] * 0.25)
    evidence(
        "trajectory-" + case,
        dict(
            definition=raw,
            refinements=records,
            independent_method=target["method"],
            observations=len(requested),
            state_fields=13,
            energy_budget_pJ=1e-9,
            convergence_order_claim=False,
        ),
        arrays,
    )
