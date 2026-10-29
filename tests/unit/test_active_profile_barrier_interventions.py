"""Complete ionic physics with both stage schedules and untouched histories."""

import json
import os
import subprocess
import sys
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from cells.core import active_profile_barrier_preparation as preparation
from cells.core import surface_active_profile_barrier_interventions_spec as schema
from cells.core import tissue_profile_preparation as profiles
from cells.core.errors import NumericalError
from cells.core.grid import EventGrid
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, digest, parse_spec
from cells.core.state import initialise
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_active_profile_barrier_interventions as model
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_step
from cells.processes import betse_tissue_profiles as native
from validation.transport import active_profile_barrier_interventions_fixtures as fixtures
from validation.transport import active_profile_barrier_interventions_reference as reference


def evidence(name, record, arrays=None):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(folder) / "active-profile-barriers"
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + ".json")).write_text(
            json.dumps(record, indent=2, allow_nan=False, default=lambda v: np.asarray(v).tolist())
            + "\n"
        )
        if arrays is not None:
            np.savez_compressed(root / (name + ".npz"), **arrays)


@lru_cache
def prepared(case="joint", permuted=False, padded=True):
    values = fixtures.inputs(case, permuted=permuted, padded=padded)
    raw = deepcopy(values["profile_request"])
    geometry = raw.pop("geometry")
    layout = geometry.pop("layout")
    layout["cell_centres_m"] = np.asarray(layout["cell_centres_m"])
    direct = profiles.prepare(
        raw["definition"],
        profiles.Geometry(native.Layout(**layout), **geometry),
        profiles._decode_profile(raw["default"]),
        [profiles._decode_profile(row) for row in raw["profiles"]],
        ion_enabled=raw["ion_enabled"],
        enabled=raw["enabled"],
        is_ecm=raw["is_ecm"],
    )
    pair = dict(definition=direct.definition, provenance=direct.provenance)
    request = fixtures.preparation_request(values, pair)
    result = preparation.prepare(request)
    return values, request, result


@lru_cache
def initialized(case="joint", permuted=False, padded=True):
    values, request, result = prepared(case, permuted, padded)
    raw = fixtures.definition(values, result)
    spec = schema.parse(raw)
    state, layout = model.initial_values(spec)
    return raw, spec, state, layout, request


def control(spec, time):
    table = control_values(schema.owner_spec(spec), [time])
    return type(table)(*(v[0] for v in table))


def copy_state(state):
    return type(state)(*(np.array(v, copy=True) for v in state))


def rate_budget(c, target):
    return reference.flatten(
        c, {k: np.full(s, 3e-23 if k.endswith("_C") else 3e-12) for k, s in c["shapes"].items()}
    ) + 3e-10 * np.abs(target)


def test_complete_preparation_and_parent_initialization():
    raw, spec, state, p, request = initialized()
    source = profiles.replay(request["profile_preparation"]["provenance"])
    ordinary = schema.owner_spec(spec)
    before, before_layout = model.base.initial_values(ordinary)
    assert len(state) == 20 and len(before) == 19
    assert type(model.parent_layout(p)) is model.base.LAYOUT_TYPE
    assert len(spec.model.channels) == 63 and set(p.channel_laws[p.channel_active]) == set(
        range(56)
    )
    for a, b in zip(model.parent_state(state), before, strict=True):
        np.testing.assert_array_equal(a, b)
    for key in before_layout._fields:
        np.testing.assert_array_equal(getattr(p, key), getattr(before_layout, key))
    np.testing.assert_array_equal(state.phase_clock_s, [0.0])
    recovered = deepcopy(ordinary.to_dict())
    original = source.definition
    old_faces = {f["id"]: f for f in original["model"]["faces"]}
    for face in recovered["model"]["faces"]:
        face["diffusivity_m2_per_s"] = old_faces[face["id"]]["diffusivity_m2_per_s"]
    assert recovered == original
    assert schema.to_dict(spec) == raw
    assert schema.replay(schema.artifact(spec)) == spec
    model.check_values(state, spec)
    evidence(
        "complete-owner",
        dict(
            definition=raw,
            preparation_request=request,
            all19_parent_state_arrays_exact=True,
            complete_parent_layout_exact=True,
            all_controls_retained=True,
            distinct_laws=56,
            populations=63,
        ),
    )


@pytest.mark.parametrize("case", fixtures.CASES)
@pytest.mark.parametrize("changed", [False, True])
def test_both_stage_coefficients_full_rhs_field_and_energy(case, changed):
    raw, spec, initial, p, _ = initialized(case, permuted=changed)
    c = reference.bind(raw)
    reports = []
    arrays = {}
    for n, time in enumerate(
        (0.0, 1e-6, 2e-6, 3e-6, 3.3e-6, 4.5e-6, 7.7e-6, spec.experiment.end_time)
    ):
        state = copy_state(initial)._replace(phase_clock_s=np.asarray([time]))
        if changed:
            k = spec.model.species_ids.index("K")
            a, b = p.membrane_cell[0], p.membrane_outside[0]
            state.amount_increment[k, a] -= 1e-5
            state.extracellular_amount_increment[k, b] += 1e-5
            state.membrane_transferred[k, 0] += 1e-5
        assert model.domain_valid(state, p, p.active, xp=np)
        target, phi, proof = reference.evaluate(c, reference.flatten(c, state._asdict()), time)
        derivative = model.rhs(state, control(spec, time), p, p.active, xp=np)
        actual = reference.flatten(c, derivative._asdict())
        budget = rate_budget(c, target)
        field = model.field_values(state, control(spec, time), p, xp=np)
        observed_phi = np.r_[
            field.potential_V[: p.active.size][p.active],
            field.potential_V[p.active.size :][p.outside_active],
        ]
        ratio = float(np.max(np.abs(actual - target) / budget, initial=0))
        signal = model.signal_values(state, p, xp=np)
        np.testing.assert_allclose(
            signal.membrane.scheduled,
            proof["membrane_coefficients"]["scheduled_m2_s"],
            rtol=5e-14,
            atol=2e-30,
        )
        target_faces = [
            [proof["barrier_coefficients"]["face_m2_s"][sid][f.id] for f in spec.model.faces]
            for sid in spec.model.species_ids
        ]
        np.testing.assert_allclose(
            signal.barrier.face_diffusivity[:, p.face_active], target_faces, rtol=5e-14, atol=2e-26
        )
        reports.append(
            dict(
                time_s=time,
                error_over_budget=ratio,
                independent=proof,
                production_energy_residual_pJ_s=float(field.energy_balance_pJ_s),
            )
        )
        arrays.update(
            {
                f"{n}-{key}": v
                for key, v in dict(
                    actual=actual,
                    reference=target,
                    budget=budget,
                    state=reference.flatten(c, state._asdict()),
                    potential=observed_phi,
                    reference_potential=phi,
                ).items()
            }
        )
        evidence(
            f"stages-{case}-{changed}",
            dict(definition=raw, changed_state=changed, comparisons=reports),
            arrays,
        )
        assert ratio <= 1 and field.converged
        assert abs(proof["physical_energy_balance_pJ_s"]) <= 1e-10
        assert abs(field.energy_balance_pJ_s) <= 1e-10
        assert (
            proof["max_charge_residual_C"] <= 3e-25
            and proof["max_component_current_residual_A"] <= 1e-23
        )
        np.testing.assert_allclose(observed_phi, phi, rtol=3e-10, atol=3e-13)


@pytest.mark.parametrize("case", ["INIT", "disabled"])
def test_disabled_schedules_match_complete_parent_bitwise(case):
    _, spec, state, p, _ = initialized(case)
    state = state._replace(phase_clock_s=np.asarray([4.5e-6]))
    u = control(spec, 4.5e-6)
    actual = model.rhs(state, u, p, p.active, xp=np)
    target = model.base.rhs(model.parent_state(state), u, model.parent_layout(p), p.active, xp=np)
    for a, b in zip(model.parent_state(actual), target, strict=True):
        np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("case", ["joint", "closed"])
def test_four_step_conservation_and_closed_reopened_actual_history(case):
    raw, spec, state, p, _ = initialized(case)
    times = np.asarray(list(EventGrid(spec)))[:5]
    table = control_values(schema.owner_spec(spec), times[:-1])
    model.check_steps(spec, np.diff(times), table)
    states = [state]
    for i, step in enumerate(np.diff(times)):
        u = type(table)(*(v[i] for v in table))
        state = rk4_step(lambda y, u=u: model.rhs(y, u, p, p.active, xp=np), state, step)
        assert model.domain_valid(state, p, p.active, xp=np)
        states.append(state)
    history = model.STATE_TYPE(*(np.stack(v) for v in zip(*states, strict=True)))
    diagnostics = model.check_values(history, spec)
    c = reference.bind(raw)
    balances = [reference.conservation(c, reference.flatten(c, s._asdict())) for s in states]
    for row in balances:
        for key, value in row.items():
            assert abs(value) <= (1e-9 if key == "energy_pJ" else 2e-11)
    trials = {}
    for clock in (2.5e-6, spec.experiment.end_time):
        probe = copy_state(state)._replace(phase_clock_s=np.asarray([clock]))
        signal = model.signal_values(probe, p, xp=np)
        if case == "closed" and clock == spec.experiment.end_time:
            sodium = spec.model.species_ids.index("Na")
            membrane = (signal.membrane.permeability[sodium] == 0) & (
                model.accounting_layout(p, xp=np).membrane_permeability[sodium] > 0
            )
            faces = (signal.barrier.face_factor[sodium] == 0) & (p.barrier_union_factor[sodium] > 0)
            assert np.any(membrane & (probe.membrane_transferred[sodium] != 0))
            assert np.any(faces & (probe.face_transferred[sodium] != 0))
        model.check_values(probe, spec)
        observed = model.observe_history(
            np.asarray([clock]), model.STATE_TYPE(*(v[None] for v in probe)), p, [clock], spec
        )
        for key in model.base.STATE_TYPE._fields:
            np.testing.assert_array_equal(getattr(observed, key)[0], getattr(probe, key))
        target, _, _ = reference.evaluate(c, reference.flatten(c, probe._asdict()), clock)
        actual = reference.flatten(
            c, model.rhs(probe, control(spec, clock), p, p.active, xp=np)._asdict()
        )
        assert np.max(np.abs(actual - target) / rate_budget(c, target)) <= 1
        trials[str(clock)] = {k: np.asarray(v).tolist() for k, v in probe._asdict().items()}
    evidence(
        "conservation-history-" + case,
        dict(
            definition=raw,
            diagnostics=diagnostics,
            independent_conservation=balances,
            clock_probes=trials,
            scope="four accepted steps plus manufactured clock probes; no10us trajectory claim",
        ),
        {"times_s": times} | {"state-" + k: v for k, v in history._asdict().items()},
    )


@pytest.mark.parametrize("phase", ["INIT", "joint"])
def test_portable_typed_snapshot_fresh_process_and_full_controls(phase, tmp_path):
    raw, spec, state, p, _ = initialized(phase)
    assert parse_spec(raw) == spec and get_model(spec.model) is model
    assert spec.fingerprint == digest(raw)
    checkpoint = initialise(spec)
    path = write_snapshot(tmp_path / "snapshot", spec, checkpoint)
    restored = load_snapshot(path)
    assert restored.spec == spec and type(restored.checkpoint.state) is model.STATE_TYPE
    for a, b in zip(
        checkpoint.state + checkpoint.layout,
        restored.checkpoint.state + restored.checkpoint.layout,
        strict=True,
    ):
        np.testing.assert_array_equal(a, b)
    code = (
        "from cells.io import load_snapshot; "
        "from cells.models.surface_active_profile_barrier_interventions import STATE_TYPE; "
        "import sys; r=load_snapshot(sys.argv[1]); "
        "assert type(r.checkpoint.state) is STATE_TYPE; assert len(r.checkpoint.state)==20"
    )
    subprocess.run([sys.executable, "-B", "-c", code, str(path)], check=True, timeout=45)
    for time in (0.0, 3.3e-6, 7.7e-6):
        full = control_values(spec, [time])
        parent = control_values(schema.owner_spec(spec), [time])
        for a, b in zip(full, parent, strict=True):
            np.testing.assert_array_equal(a, b)
    evidence(
        "portable-" + phase,
        dict(definition=raw, typed_fresh_process_snapshot=True, all_controls_exact=True),
    )


@pytest.mark.parametrize(
    "fault", ["order", "mismatched_owner", "mismatched_controls", "changed_recipe", "wrong_kind"]
)
def test_combined_preparation_refuses_mismatched_static_owners(fault):
    _, request, _ = prepared()
    raw = deepcopy(request)
    if fault == "order":
        raw["order"] = "barriers_first"
    if fault == "mismatched_owner":
        raw["barrier_request"]["definition"]["model"]["cells"][0]["volume_pL"] *= 2
    if fault == "mismatched_controls":
        raw["barrier_request"]["definition"]["experiment"]["channel_controls"][0]["schedule"][0][
            "availability"
        ] *= 0.5
    if fault == "changed_recipe":
        raw["profile_preparation"]["provenance"]["profile_declarations"]["default"][
            "diffusivity_m2_s"
        ][0] *= 2
    if fault == "wrong_kind":
        raw["kind"] = "implicit_combination"
    with pytest.raises(ConfigError):
        preparation.prepare(raw)


@pytest.mark.parametrize(
    "fault",
    [
        "physical_owner",
        "static_definition",
        "stale_identity",
        "phase",
        "timing",
        "reset",
        "missing_membrane_capacity",
        "missing_barrier_capacity",
        "small_membrane_capacity",
        "small_barrier_capacity",
        "negative_membrane",
        "excess_barrier",
        "unknown_site",
        "wrong_membrane_kind",
        "list_barriers",
        "schema_bool",
    ],
)
def test_invalid_combined_schedule_refused(fault):
    raw = deepcopy(initialized()[0])
    m = raw["model"]
    if fault == "physical_owner":
        m["channels"][0]["abundance"] *= 2
    if fault == "static_definition":
        m["coupled_preparation"]["definition"]["model"]["faces"][0]["area_m2"] *= 2
    if fault == "stale_identity":
        m["coupled_preparation"]["provenance"]["identity"] = "stale"
    if fault == "phase":
        m["phase"] = "INHERITED"
    if fault == "timing":
        m["timing_policy"] = "frozen_clock"
    if fault == "reset":
        m["reset_policy"] = "rebase"
    if fault == "missing_membrane_capacity":
        raw["execution"].pop("intervention_capacity")
    if fault == "missing_barrier_capacity":
        raw["execution"].pop("barrier_target_capacity")
    if fault == "small_membrane_capacity":
        raw["execution"]["intervention_target_capacity"] = 1
    if fault == "small_barrier_capacity":
        raw["execution"]["barrier_target_capacity"] = 0
    if fault == "negative_membrane":
        m["membrane_interventions"][0]["amplitude"] = -1000.0
    if fault == "excess_barrier":
        m["barrier_intervention"]["amplitude"] = 1.1
    if fault == "unknown_site":
        m["barrier_intervention"]["site_ids"] = ["unowned"]
    if fault == "wrong_membrane_kind":
        m["membrane_interventions"][0]["kind"] = "ecmJ"
    if fault == "list_barriers":
        m["barrier_intervention"] = [m["barrier_intervention"]]
    if fault == "schema_bool":
        raw["schema_version"] = True
    with pytest.raises(ConfigError):
        schema.parse(raw)


def test_both_ramp_bounds_and_actual_history_domain_refuse():
    _, spec, state, p, _ = initialized()
    grid = np.asarray(list(EventGrid(spec)))
    table = control_values(spec, grid[:-1])
    model.check_steps(spec, np.diff(grid), table)
    with pytest.raises(ConfigError):
        model.check_steps(spec, np.asarray([1e-6]), table)
    for name in (
        "amount_increment",
        "membrane_transferred",
        "face_transferred",
        "channel_gate",
        "phase_clock_s",
    ):
        invalid = copy_state(state)
        getattr(invalid, name).flat[0] = np.nan
        assert not model.domain_valid(invalid, p, p.active, xp=np)
        with pytest.raises(NumericalError):
            model.check_values(invalid, spec)


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_explicit_backend_input_admission_without_accelerator_execution(backend):
    raw = deepcopy(initialized()[0])
    raw["execution"]["backend"] = backend
    spec = schema.parse(raw)
    assert parse_spec(raw) == spec and get_model(spec.model) is model
    assert schema.to_dict(spec) == raw
    evidence(
        "backend-input-" + backend,
        dict(definition=raw, scope="input and NumPy admission only; no accelerator execution"),
    )


@pytest.mark.parametrize("history_name", ["membrane_transferred", "face_transferred"])
def test_closed_route_view_cannot_hide_invalid_actual_history(history_name):
    _, spec, state, p, _ = initialized("closed")
    state = copy_state(state)._replace(phase_clock_s=np.asarray([spec.experiment.end_time]))
    signal = model.signal_values(state, p, xp=np)
    sodium = spec.model.species_ids.index("Na")
    coefficient = (
        signal.membrane.permeability
        if history_name == "membrane_transferred"
        else signal.barrier.face_factor
    )
    union = model.accounting_layout(p, xp=np)
    support = (
        union.membrane_permeability if history_name == "membrane_transferred" else union.face_factor
    )
    route = np.flatnonzero((coefficient[sodium] == 0) & (support[sodium] > 0))[0]
    getattr(state, history_name)[sodium, route] = np.nan
    assert not model.domain_valid(state, p, p.active, xp=np)
    value = model.readouts(state, control(spec, spec.experiment.end_time), p, xp=np)
    assert not value.valid
    with pytest.raises(NumericalError):
        model.check_values(state, spec)
