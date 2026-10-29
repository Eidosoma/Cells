"""Complete calcium/fuel state crosses an explicit epoch without rebasing."""

import json
import os
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from cells.core import joint_water_profile_phase_handoff as bridge
from cells.core import surface_calcium_energy_water_profile_epoch_spec as water_spec
from cells.core import surface_calcium_energy_water_repair_profile_epoch_spec as repair_spec
from cells.core.errors import NumericalError
from cells.core.grid import EventGrid
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, digest, parse_spec
from cells.core.state import Checkpoint, initialise
from cells.models import surface_calcium_energy_water_profile_epoch as water
from cells.models import surface_calcium_energy_water_repair_profile_epoch as repair
from cells.numerics.fixed_step import rk4_step
from tests.unit.test_joint_water_profile_interventions import OWNERS as PROFILES
from tests.unit.test_joint_water_profile_interventions import build
from validation.topology import joint_water_profile_phase_handoff_fixtures as fixtures
from validation.topology import joint_water_profile_phase_handoff_reference as reference

OWNERS = {"water": (water_spec, water), "repair": (repair_spec, repair)}


def evidence(name, value, arrays=None):
    directory = os.environ.get("CELLS_COMPONENT_EVIDENCE")
    if not directory:
        return
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    stem = root / ("joint-water-epoch-" + name)
    if arrays is not None:
        np.savez_compressed(stem.with_suffix(".npz"), **arrays)
        value = dict(value, arrays_file=stem.with_suffix(".npz").name)
    stem.with_suffix(".json").write_text(
        json.dumps(
            dict(value, status=value.get("status", "passed")),
            indent=2,
            allow_nan=False,
            default=lambda v: v.tolist(),
        )
        + "\n"
    )


def control(spec, time):
    table = control_values(spec, [time])
    return type(table)(*(v[0] for v in table))


def integrate_host(spec, model):
    state, layout = model.initial_values(spec)
    times = np.asarray(list(EventGrid(spec)))
    table = control_values(spec, times[:-1])
    model.check_steps(spec, np.diff(times), table)
    values = [state]
    for i, step in enumerate(np.diff(times)):
        u = type(table)(*(v[i] for v in table))
        state = rk4_step(
            lambda y, *args: model.rhs(y, *args, xp=np), state, step, u, layout, layout.active
        )
        values.append(state)
    history = model.STATE_TYPE(*(np.stack(v) for v in zip(*values, strict=True)))
    return times, history, layout, model.check_values(history, spec)


@lru_cache
def source_raw(family):
    raw = build(fixtures.inputs(family), family)
    return fixtures.definitions(raw)[0]


@lru_cache
def source_run(family, refinement=1):
    definition, model, _ = PROFILES[family]
    original = definition.parse(source_raw(family))
    spec = replace(
        original, execution=replace(original.execution, dt=original.execution.dt / refinement)
    )
    return spec, integrate_host(spec, model)


def source_checkpoint(family, time=fixtures.INIT_END):
    source, (times, history, layout, _) = source_run(family)
    i = EventGrid(source).exact_index(time)
    model = PROFILES[family][1]
    state = model.STATE_TYPE(*(v[i] for v in history))
    return source, Checkpoint(
        state, layout, float(times[i]), i, event_index(source, float(times[i]))
    )


@lru_cache
def prepared(family, case="changed-controls", time=fixtures.INIT_END):
    source, checkpoint = source_checkpoint(family, time)
    _, target = fixtures.definitions(source_raw(family), case)
    definition, model = OWNERS[family]
    request = dict(
        kind=bridge.REQUEST_KIND,
        policies=deepcopy(definition.POLICIES),
        source=bridge.capture_source(source, checkpoint),
        simulation=target,
    )
    artifact = bridge.prepare(request)
    spec = definition.parse(artifact.definition)
    return request, artifact, spec, source, checkpoint


def compare(context, actual, expected, *, rhs=False):
    process = context["process"]
    budget = np.r_[
        process.flatten(
            context["parent"],
            {
                key: np.full(
                    shape,
                    (3e-23 if rhs else 3e-25) if key.endswith("_C") else (3e-12 if rhs else 2e-11),
                )
                for key, shape in context["parent"]["shapes"].items()
            },
        ),
        3e-12 if rhs else 2e-11,
    ]
    budget = budget + (3e-10 if rhs else 3e-9) * np.abs(expected)
    error = float(np.max(np.abs(actual - expected) / budget, initial=0))
    assert error <= 1, error
    return error


def sampled(spec, times, history, observations, context):
    indices = [EventGrid(spec).exact_index(t) for t in observations]
    model = OWNERS["repair" if "damage" in history._fields else "water"][1]
    actual = np.stack(
        [
            reference.scheduled.flatten(
                context, model.STATE_TYPE(*(v[i] for v in history))._asdict()
            )
            for i in indices
        ]
    )
    fields = {name: np.asarray(getattr(history, name))[indices] for name in history._fields}
    np.testing.assert_allclose(times[indices], observations, rtol=0, atol=0)
    return actual, fields


def save_refinement(family, phase, raw, initial=None, original=None, case=None):
    context = reference.scheduled.bind(raw)
    _, proof = reference.integrate(raw, initial_state=initial)
    expected = proof["observations"]
    observations = proof["observation_times_s"]
    outcomes = []
    arrays = dict(
        reference_flat=expected,
        times_s=np.asarray(observations),
        state_fields=np.asarray([*context["parent"]["shapes"], "phase_clock_s"]),
        reference_shapes_json=np.asarray(json.dumps(context["parent"]["shapes"])),
        phase_initial_flat=(reference.scheduled.initial(context) if initial is None else initial),
    )
    transport_errors = []
    name = phase + "-refinement-" + family + ("-" + case if case else "")
    for refinement in (1, 2):
        if phase == "INIT":
            spec, (times, history, layout, diagnostics) = source_run(family, refinement)
            model = PROFILES[family][1]
        else:
            spec = replace(
                original,
                execution=replace(original.execution, dt=original.execution.dt / refinement),
            )
            model = OWNERS[family][1]
            times, history, layout, diagnostics = integrate_host(spec, model)
        actual, fields = sampled(spec, times, history, observations, context)
        arrays["production_flat_" + str(refinement)] = actual
        arrays.update({str(refinement) + "__" + k: v for k, v in fields.items()})
        try:
            score = compare(context, actual, expected)
        except AssertionError as error:
            evidence(
                name + "-failure",
                dict(
                    status="failed",
                    reason="full-state accuracy budget",
                    error=str(error),
                    dt_s=spec.execution.dt,
                    source_or_target_definition=raw,
                    epoch_definition=None
                    if phase == "INIT"
                    else OWNERS[family][0].to_dict(original),
                ),
                arrays,
            )
            raise
        # Resolve the transient membrane-transfer component separately from
        # the bulk gate/amount precision floor. Reference flattening selects
        # the same physical routes for both complete owner families.
        selector = {k: np.zeros(shape) for k, shape in context["parent"]["shapes"].items()}
        selector["membrane_transferred"] = np.ones_like(selector["membrane_transferred"])
        mask = np.r_[context["process"].flatten(context["parent"], selector), 0].astype(bool)
        transport_error = float(np.max(np.abs(actual[:, mask] - expected[:, mask])))
        transport_errors.append(transport_error)
        outcomes.append(
            dict(
                dt_s=spec.execution.dt,
                error_over_budget=score,
                max_error=float(np.max(np.abs(actual - expected))),
                transient_background_transfer_error_fmol=transport_error,
                diagnostics=diagnostics,
            )
        )
        if phase == "SIM":
            observed = model.observe_history(times, history, layout, observations, spec)
            for key in history._fields:
                np.testing.assert_array_equal(getattr(observed, key), fields[key])
            np.testing.assert_allclose(
                observed.elapsed_time_s[:, 0],
                np.asarray(observations)
                + json.loads(original.model.handoff_json)["clocks"]["init_checkpoint_time_s"],
                rtol=0,
                atol=1e-20,
            )
            np.testing.assert_array_equal(
                observed.init_phase_clock_s,
                np.full_like(
                    observed.phase_clock_s,
                    json.loads(original.model.handoff_json)["clocks"]["init_phase_clock_s"],
                ),
            )
            if case == "close-reopen":
                sodium = spec.model.species_ids.index("Na")
                midpoint = EventGrid(spec).exact_index(0.125e-6)
                closed_state = model.STATE_TYPE(*(v[midpoint] for v in history))
                signal = model.signal_values(closed_state, layout, xp=np)
                closed = signal.permeability[sodium] == 0
                assert np.any(closed) and np.any(
                    closed_state.membrane_transferred[sodium, closed] != 0
                )
    if phase == "SIM":
        if not (
            transport_errors[0] > 1e-20 and transport_errors[1] <= 0.3 * transport_errors[0] + 1e-22
        ):
            evidence(
                name + "-failure",
                dict(
                    status="failed",
                    reason="transient transfer refinement",
                    transport_errors_fmol=transport_errors,
                    source_or_target_definition=raw,
                    epoch_definition=OWNERS[family][0].to_dict(original),
                ),
                arrays,
            )
        assert transport_errors[0] > 1e-20, transport_errors
        assert transport_errors[1] <= 0.3 * transport_errors[0] + 1e-22, transport_errors
    evidence(
        name,
        dict(
            phase=phase,
            family=family,
            complete_state_fields=44 if family == "water" else 49,
            observations_compared=observations,
            independent={k: v for k, v in proof.items() if k != "observations"},
            refinements=outcomes,
            transient_transfer_refines=phase == "SIM",
            original_accounting_origin=True,
            all_actual_state_arrays_retained=True,
            source_or_target_definition=raw,
            epoch_definition=None if phase == "INIT" else OWNERS[family][0].to_dict(original),
        ),
        arrays,
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_complete_INIT_at_every_observation_and_control_boundary(family):
    save_refinement(family, "INIT", source_raw(family))


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", fixtures.CASES)
def test_complete_owner_arrays_layout_and_both_clocks_survive(family, case):
    request, result, spec, source, checkpoint = prepared(family, case)
    definition, model = OWNERS[family]
    old = PROFILES[family][1]
    state, layout = model.initial_values(spec)
    for a, b in zip(old.parent_state(checkpoint.state), old.parent_state(state), strict=True):
        assert a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()
    for a, b in zip(old.parent_layout(checkpoint.layout), old.parent_layout(layout), strict=True):
        np.testing.assert_array_equal(a, b)
    np.testing.assert_array_equal(state.phase_clock_s, [0.0])
    assert result.provenance["clocks"]["init_checkpoint_time_s"] == checkpoint.time
    assert spec.model.phase == "SIM" and source.model.phase == "INIT"
    assert type(state) is model.STATE_TYPE and type(layout) is model.LAYOUT_TYPE
    assert type(state) is not type(checkpoint.state)
    for key in (
        "chemical_amount_increment",
        "channel_transferred",
        "pump_cycles",
        "plasma_pump_cycles",
        "er_pump_transferred",
        "plasma_metabolic_work_pJ",
        "er_metabolic_work_pJ",
    ):
        assert np.any(getattr(state, key) != 0), key
    if family in fixtures.FAMILIES:
        assert np.any(state.energy_amount_increment_fmol != 0)
    for key in (
        "volume_increment_pL",
        "extracellular_volume_increment_pL",
        "water_transferred_pL",
        "water_dissipated_energy_pJ",
        "pool_volume_work_pJ",
    ):
        assert np.any(getattr(state, key) != 0), key
    if family == "repair":
        for key in (
            "damage",
            "damage_opened",
            "damage_closed",
            "injury_transferred",
            "injury_dissipated_energy_pJ",
        ):
            assert np.any(getattr(state, key) != 0), key
    evidence(
        "preservation-" + family + "-" + case,
        dict(
            request=request,
            preparation=result.provenance,
            source_state_sha256=digest(bridge.encode_arrays(checkpoint.state)),
            exact_all_parent_arrays=True,
            exact_original_physical_layout=True,
            clock_only_reset=True,
            actual_stores_gates_fuel_and_ledgers=True,
            actual_moving_volume_water_work_and_repair_ledgers=True,
        ),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", fixtures.CASES)
def test_complete_SIM_stage_fields_and_rhs_from_actual_INIT(family, case):
    request, _, spec, _, _ = prepared(family, case)
    model = OWNERS[family][1]
    state, layout = model.initial_values(spec)
    context = reference.scheduled.bind(request["simulation"])
    stages = []
    for time in spec.experiment.observation_times:
        trial = state._replace(phase_clock_s=np.asarray([time]))
        value = model.readouts(trial, control(spec, time), layout, xp=np)
        flat = reference.scheduled.flatten(context, trial._asdict())
        slope, phi, proof = reference.scheduled.evaluate(context, flat)
        ratio = compare(
            context,
            reference.scheduled.flatten(context, value.derivative._asdict()),
            slope,
            rhs=True,
        )
        n = layout.active.size
        observed_phi = np.r_[
            value.field.potential_V[:n][layout.active],
            value.field.potential_V[n:][layout.outside_active],
        ]
        np.testing.assert_allclose(observed_phi, phi, rtol=3e-10, atol=3e-13)
        rhs = model.rhs(trial, control(spec, time), layout, layout.active, xp=np)
        assert type(rhs) is model.STATE_TYPE and value.valid
        assert abs(value.field.energy_balance_pJ_s) < 1e-10
        assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-10
        stages.append(dict(time_s=time, error_over_budget=ratio, independent=proof))
    evidence(
        "SIM-stages-" + family + "-" + case,
        dict(stages=stages, complete_state_fields=len(state), actual_carried_calcium_and_fuel=True),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", ["changed-controls", "close-reopen"])
def test_carried_SIM_every_observation_refines_and_preserves_accounting(family, case):
    request, _, spec, _, _ = prepared(family, case)
    _, initial = reference.initial(request)
    save_refinement(family, "SIM", request["simulation"], initial, spec, case)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_interior_checkpoint_artifact_and_original_typed_replay(family, tmp_path):
    request, prepared_result, spec, _, _ = prepared(family, time=0.125e-6)
    path = bridge.write_preparation(tmp_path / "epoch", prepared_result)
    assert bridge.read_preparation(path) == prepared_result
    assert bridge.replay(json.loads(json.dumps(prepared_result.provenance))) == prepared_result
    assert OWNERS[family][0].parse(OWNERS[family][0].to_dict(spec)) == spec
    assert parse_spec(OWNERS[family][0].to_dict(spec)) == spec
    point = initialise(spec)
    np.testing.assert_array_equal(point.state.phase_clock_s, [0.0])
    assert point.time == 0.0 and type(point.state) is OWNERS[family][1].STATE_TYPE
    with pytest.raises(ConfigError):
        bridge.write_preparation(path, prepared_result)
    evidence(
        "portable-" + family,
        dict(
            source_time_s=0.125e-6,
            artifact=prepared_result.provenance,
            exact_typed_replay=True,
            overwrite_refused=True,
            public_initial_type=True,
            actual_water_fuel_repair_history=True,
        ),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize(
    "fault",
    [
        "time",
        "index",
        "event",
        "clock",
        "precision",
        "chemical",
        "history",
        "pool",
        "layout",
        "source-SIM",
        "water",
        "water-history",
        "repair-history",
    ],
)
def test_full_source_checkpoint_owner_history_pool_and_clock_refusals(family, fault):
    source, point = source_checkpoint(family)
    if fault == "time":
        point = replace(point, time=point.time / 3)
    if fault == "index":
        point = replace(point, step_index=0)
    if fault == "event":
        point = replace(point, event_index=point.event_index + 1)
    if fault == "clock":
        point = replace(point, state=point.state._replace(phase_clock_s=np.zeros(1)))
    if fault == "precision":
        point = replace(
            point,
            state=point.state._replace(channel_gate=point.state.channel_gate.astype(np.float32)),
        )
    if fault in ("chemical", "history", "pool"):
        key = (
            "chemical_amount_increment"
            if fault == "chemical"
            else (
                "energy_amount_increment_fmol"
                if fault == "pool" and family in fixtures.FAMILIES
                else "membrane_transferred"
            )
        )
        array = np.array(getattr(point.state, key))
        array.flat[0] += 1e-3
        point = replace(point, state=point.state._replace(**{key: array}))
    if fault in ("water", "water-history", "repair-history"):
        key = (
            "volume_increment_pL"
            if fault == "water"
            else "water_transferred_pL"
            if fault == "water-history"
            else "injury_transferred"
            if family == "repair"
            else "pool_volume_work_pJ"
        )
        array = np.array(getattr(point.state, key))
        array.flat[0] += 1e-3
        point = replace(point, state=point.state._replace(**{key: array}))
    if fault == "layout":
        point = replace(point, layout=point.layout._replace(volume=point.layout.volume * 2))
    if fault == "source-SIM":
        source = replace(source, model=replace(source.model, phase="SIM"))
    with pytest.raises((ConfigError, NumericalError, ValueError)):
        bridge.capture_source(source, point)
    evidence("source-refusal-" + family + "-" + fault, dict(fault=fault, refused=True))


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize(
    "fault",
    [
        "capacity",
        "static",
        "phase",
        "policy",
        "source-seal",
        "clock-record",
        "buffer-record",
        "water-anchor",
        "fuel-anchor",
        "repair-anchor",
    ],
)
def test_full_request_cannot_remap_rebase_or_silently_reset(family, fault):
    request, result, spec, _, _ = prepared(family)
    raw = deepcopy(request)
    if fault == "capacity":
        raw["simulation"]["execution"]["capacity"] += 1
    if fault == "static":
        raw["simulation"]["model"]["ionic"]["temperature_K"] *= 1.01
    if fault in ("water-anchor", "fuel-anchor", "repair-anchor"):
        if fault == "water-anchor":
            raw["simulation"]["model"]["water_compartments"][0]["reference_volume_pL"] *= 1.01
        elif fault == "fuel-anchor":
            raw["simulation"]["model"]["energy_pools"][0]["initial_amount_fmol"]["ATP"] *= 1.01
        elif family == "repair":
            raw["simulation"]["model"]["injury_patches"][0]["initial_damage"] *= 0.5
        else:
            raw["simulation"]["model"]["chemical_osmotic_coupling"] = "rebase_current_water"
    if fault == "phase":
        raw["simulation"]["model"]["phase"] = "INIT"
    if fault == "policy":
        raw["policies"]["state_policy"] = "rebase_current_pools"
    if fault == "source-seal":
        raw["source"]["identity"] = "bad"
    if fault in ("clock-record", "buffer-record"):
        modified = deepcopy(result.definition)
        record = modified["model"]["handoff"]
        if fault == "clock-record":
            record["clocks"]["sim_epoch_time_s"] = 1.0
        else:
            record["buffer_reset"]["scheduled_buffer_m2_s"][0][0] = 1.0
        with pytest.raises(ConfigError):
            OWNERS[family][0].parse(modified)
    else:
        with pytest.raises((ConfigError, NumericalError, ValueError)):
            bridge.prepare(raw)
    evidence("target-refusal-" + family + "-" + fault, dict(fault=fault, refused=True))


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_exact_scheduled_source_owner_excludes_physical_parents_and_existing_epochs(family):
    _, result, spec, source, _ = prepared(family)
    assert bridge.owner(source).runtime is PROFILES[family][1]
    for value in (
        PROFILES[family][0].owner_spec(source),
        spec,
        result.definition,
        {"model": {"id": "resolved_calcium_energy_membrane_profiles@1"}},
    ):
        with pytest.raises(ConfigError):
            bridge.owner(value)
    evidence("exact-source-owner-" + family, dict(no_silent_parent_or_epoch_admission=True))


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_bounded_epoch_steps_preserve_physical_ledgers_and_actual_readouts(family):
    _, _, spec, _, point = prepared(family)
    model = OWNERS[family][1]
    times, history, layout, diagnostics = integrate_host(spec, model)
    for key in PROFILES[family][2].STATE_TYPE._fields:
        np.testing.assert_array_equal(getattr(history, key)[0], getattr(point.state, key))
    observed = model.observe_history(times, history, layout, times, spec)
    for key in model.STATE_TYPE._fields:
        np.testing.assert_array_equal(getattr(observed, key), getattr(history, key))
    np.testing.assert_array_equal(
        observed.init_phase_clock_s, np.full_like(history.phase_clock_s, point.time)
    )
    np.testing.assert_allclose(
        observed.elapsed_time_s[:, 0], point.time + times, rtol=0, atol=1e-20
    )
    evidence(
        "bounded-SIM-" + family,
        dict(
            duration_s=spec.experiment.end_time,
            actual_evolved_checkpoint=True,
            full_original_ledger_checks=True,
            diagnostics=diagnostics,
            long_trajectory_or_convergence_claim=False,
        ),
        dict(
            times_s=times, **{k: np.asarray(getattr(history, k)) for k in model.STATE_TYPE._fields}
        ),
    )


def test_independent_dependency_manifest_captures_legacy_assertion_helpers():
    root = Path(__file__).resolve().parents[2]
    manifest = reference.dependency_manifest(root)
    assert "validation/betse/contact.py" in manifest
    evidence("reference-dependencies", dict(source_sha256=manifest, complete_reference=True))


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_carried_initial_turnover_at_actual_water_volume_agrees_with_independent_rates(family):
    request, _, spec, _, _ = prepared(family)
    _, initial = reference.initial(request)
    expected, rows = reference.carried_fuel_turnover(request["simulation"], initial)
    model = OWNERS[family][1]
    actual = model.check_carried_pool_turnover(spec, spec.execution.dt)
    np.testing.assert_allclose(actual, expected, rtol=3e-11, atol=3e-15)
    assert expected > 0
    with pytest.raises(ConfigError):
        model.check_carried_pool_turnover(spec, 0.05 / expected * 1.01)
    evidence(
        "carried-fuel-turnover-" + family,
        dict(
            independent=rows,
            maximum_fractional_rate_s=actual,
            actual_carried_pools=True,
            gross_turnover_limit=0.05,
            excessive_step_refused=True,
        ),
    )
