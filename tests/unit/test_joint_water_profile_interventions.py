"""Scheduled background D preserves the complete full56 water/repair owners."""

import ast
import hashlib
import json
import os
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cells.core import surface_calcium_energy_water_profile_interventions_spec as water_spec
from cells.core import surface_calcium_energy_water_repair_profile_interventions_spec as repair_spec
from cells.core import tissue_profile_composition_preparation as composed
from cells.core import tissue_profile_preparation as direct
from cells.core.errors import NumericalError
from cells.core.grid import EventGrid
from cells.core.schedule import control_values
from cells.core.specs import ConfigError
from cells.models import surface_calcium_energy as fuel
from cells.models import surface_calcium_energy_water_hcn_extra as water_parent
from cells.models import surface_calcium_energy_water_profile_interventions as water
from cells.models import surface_calcium_energy_water_repair_hcn_extra as repair_parent
from cells.models import surface_calcium_energy_water_repair_profile_interventions as repair
from cells.numerics.fixed_step import rk4_step
from cells.processes import betse_tissue_profiles as native
from tests.owned_joint_water_hcn_helpers import changed
from validation.topology import joint_water_profile_interventions_fixtures as fixtures
from validation.topology import joint_water_profile_interventions_reference as reference

ROOT = Path(os.environ.get("CELLS_COMPONENT_SOURCE_ROOT", Path(__file__).resolve().parents[2]))
OWNERS = {
    "water": (water_spec, water, water_parent),
    "repair": (repair_spec, repair, repair_parent),
}


def evidence(name, value, arrays=None):
    if not (destination := os.environ.get("CELLS_COMPONENT_EVIDENCE")):
        return
    path = Path(destination) / ("joint-water-profiles-" + name)
    path.parent.mkdir(parents=True, exist_ok=True)
    if arrays is not None:
        np.savez_compressed(path.with_suffix(".npz"), **arrays)
        value = dict(value, arrays_file=path.with_suffix(".npz").name)
    path.with_suffix(".json").write_text(
        json.dumps(
            dict(value, status=value.get("status", "passed")),
            indent=2,
            allow_nan=False,
            default=lambda v: v.tolist(),
        )
        + "\n"
    )


def build(raw, family):
    raw = deepcopy(raw)
    geometry = raw["geometry"]
    layout = geometry.pop("layout")
    prepared = composed.prepare(
        raw["definition"],
        composed.Geometry(native.Layout(**layout), **geometry),
        direct._decode_profile(raw["default"]),
        [direct._decode_profile(p) for p in raw["profiles"]],
        ion_enabled=raw["ion_enabled"],
        enabled=raw["enabled"],
        is_ecm=raw["is_ecm"],
    )
    schema = OWNERS[family][0]
    result = deepcopy(prepared.definition)
    result["model"].update(
        id=schema.MODEL_ID,
        profile_preparation=dict(definition=prepared.definition, provenance=prepared.provenance),
        interventions=raw["interventions"],
        phase=raw["phase"],
        timing_policy=schema.TIMING_POLICY,
        reset_policy=schema.RESET_POLICY,
    )
    result["execution"].update(
        intervention_capacity=raw["intervention_capacity"],
        intervention_target_capacity=raw["intervention_target_capacity"],
    )
    return result


@lru_cache
def initialized(family="water", case="SIM", padded=True):
    raw = build(fixtures.inputs(family, case, padded=padded), family)
    schema, model, _ = OWNERS[family]
    spec = schema.parse(raw)
    state, p = model.initial_values(spec)
    return schema.to_dict(spec), spec, state, p


def control(spec, time):
    table = control_values(spec, [time])
    return type(table)(*(v[0] for v in table))


def score(context, actual, expected, *, rhs=False):
    process = context["process"]
    floors = {
        key: np.full(
            shape, (3e-23 if rhs else 3e-25) if key.endswith("_C") else (3e-12 if rhs else 2e-11)
        )
        for key, shape in context["parent"]["shapes"].items()
    }
    budget = np.r_[process.flatten(context["parent"], floors), 3e-12 if rhs else 2e-11]
    budget = budget + (3e-10 if rhs else 3e-9) * np.abs(expected)
    return float(np.max(np.abs(actual - expected) / budget, initial=0))


def stage(raw, spec, state, p, family, time):
    model = OWNERS[family][1]
    context = reference.bind(raw)
    y = state._replace(phase_clock_s=np.asarray([time]))
    before = [v.tobytes() for v in y]
    actual = model.readouts(y, control(spec, time), p, xp=np)
    expected, phi, proof = reference.evaluate(context, reference.flatten(context, y._asdict()))
    ratio = score(
        context, reference.flatten(context, actual.derivative._asdict()), expected, rhs=True
    )
    assert ratio <= 1, ratio
    n = p.active.size
    np.testing.assert_allclose(
        np.r_[
            actual.field.potential_V[:n][p.active], actual.field.potential_V[n:][p.outside_active]
        ],
        phi,
        rtol=3e-10,
        atol=3e-13,
    )
    assert actual.valid and abs(actual.field.energy_balance_pJ_s) < 1e-10
    assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-10
    assert before == [v.tobytes() for v in y]
    return dict(
        time_s=time,
        error_over_budget=ratio,
        independent=proof,
        energy_rate_residual_pJ_s=float(actual.field.energy_balance_pJ_s),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", fixtures.CASES)
def test_complete_physical_owner_and_initial_manufactured_stages(family, case):
    raw, spec, state, p = initialized(family, case)
    schema, model, parent = OWNERS[family]
    original, layout = parent.initial_values(schema.owner_spec(spec))
    source = spec.model.profile_preparation["provenance"]["source_definition"]
    before, _ = parent.initial_values(schema.parent.parse(source))
    assert type(model.parent_layout(p)) is parent.LAYOUT_TYPE
    assert len(state) == (44 if family == "water" else 49)
    assert len(spec.model.channels) == 63 and set(p.channel_laws[p.channel_active]) == set(
        range(56)
    )
    for a, b, c in zip(model.parent_state(state), original, before, strict=True):
        assert a.shape == b.shape == c.shape and a.dtype == b.dtype == c.dtype
        assert a.tobytes() == b.tobytes() == c.tobytes()
    for a, b in zip(model.parent_layout(p), layout, strict=True):
        np.testing.assert_array_equal(a, b)
    records = [
        stage(raw, spec, y, p, family, t)
        for y in (state, changed(spec, state, p))
        for t in (0.0, 1e-6, 1.125e-6, 2e-6, 3.125e-6)
    ]
    model.check_values(state, spec)
    evidence(
        "stages-" + family + "-" + case,
        dict(
            inputs=raw,
            stages=records,
            complete_fields=len(state),
            exact_typed_physical_initial_state=True,
            water_fuel_and_repair_declarations_preserved=True,
            manufactured_stage_is_not_integrated_history=True,
            padding_checked=True,
        ),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", ["INIT", "empty-events"])
def test_inactive_schedule_is_bitwise_complete_parent(family, case):
    _, spec, state, p = initialized(family, case)
    _, model, parent = OWNERS[family]
    y = changed(spec, state, p)._replace(phase_clock_s=np.asarray([2e-6]))
    u = control(spec, 2e-6)
    actual = model.rhs(y, u, p, p.active, xp=np)
    expected = parent.rhs(model.parent_state(y), u, model.parent_layout(p), p.active, xp=np)
    for a, b in zip(model.parent_state(actual), expected, strict=True):
        np.testing.assert_array_equal(a, b)
    np.testing.assert_array_equal(actual.phase_clock_s, [1.0])
    evidence(
        "inactive-" + family + "-" + case,
        dict(all_parent_rates_bitwise=True, actual_volume_fuel_and_damage_preserved=True),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_live_current_volume_feeds_three_pumps_and_neutral_particles_once(family):
    _, spec, state, p = initialized(family)
    _, model, _ = OWNERS[family]
    y = changed(spec, state, p)._replace(phase_clock_s=np.asarray([1.125e-6]))
    signal = model.signal_values(y, p, xp=np)
    current = model.parent_layout(p)._replace(membrane_permeability=signal.permeability)
    stage_layout = water_parent.effective_layout(y, model.water_layout(current))
    assert type(stage_layout) is fuel.HCN_EXTRA_LAYOUT_TYPE
    actual = fuel.stage_layout(water_parent.prior_state(y), stage_layout, xp=np)
    amount = fuel.energy_amounts(y, p)
    concentration = amount / stage_layout.volume
    for prefix, owners in (
        ("pump_", p.membrane_cell),
        ("pmca_", p.membrane_cell),
        ("er_pump_", np.arange(p.er_pump_present.size)),
    ):
        present = getattr(p, prefix + "present")
        for i, name in enumerate(("atp", "adp", "pi")):
            key = prefix + name + ("_mM" if prefix == "pump_" else "")
            np.testing.assert_array_equal(
                getattr(actual, key)[present], concentration[i, owners[present]]
            )
    particles = water_parent.osmolyte_amounts(y, p)
    np.testing.assert_array_equal(particles[-3:, : p.active.size], amount)
    assert np.all(particles[-3:, p.active.size :] == 0)
    mask = p.cytosol_selector.astype(bool)
    np.testing.assert_array_equal(stage_layout.er_volume[~mask], p.er_volume[~mask])
    evidence(
        "moving-owners-" + family,
        dict(current_volume_actual_pools_all_pumps=True, fuel_particles_once=True, fixed_er=True),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_closed_background_view_leaves_all_physical_owners_and_rates_actual(family):
    raw, spec, state, p = initialized(family, "close-reopen")
    _, model, parent = OWNERS[family]
    y = changed(spec, state, p)._replace(phase_clock_s=np.asarray([2e-6]))
    signal = model.signal_values(y, p, xp=np)
    closed = (signal.permeability == 0) & (
        model.accounting_layout(p, xp=np).membrane_permeability > 0
    )
    assert np.any(closed)
    y.membrane_transferred[closed] = 1e-14
    before = [v.tobytes() for v in y]
    view = model.readout_state(y, signal.permeability, xp=np)
    for key in parent.STATE_TYPE._fields:
        if key != "membrane_transferred":
            np.testing.assert_array_equal(getattr(view, key), getattr(y, key))
    assert np.all(view.membrane_transferred[closed] == 0)
    assert model.domain_valid(y, p, p.active, xp=np)
    stage(raw, spec, y, p, family, 2e-6)
    assert before == [v.tobytes() for v in y]
    evidence(
        "closed-view-" + family,
        dict(
            temporary_background_marker_only=True,
            actual_water_fuel_repair_and_other_ledgers_unchanged=True,
            independent_full_rhs=True,
        ),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_sealed_artifact_replay_preserves_full_physical_owner(family):
    _, spec, _, _ = initialized(family)
    schema = OWNERS[family][0]
    record = schema.artifact(spec)
    assert record["kind"] == "cells.scheduled_joint_water_membranes@1"
    assert schema.replay(record) == spec
    broken = deepcopy(record)
    broken["definition"]["model"]["water_compartments"][0]["minimum_volume_pL"] *= 0.9
    with pytest.raises(ConfigError):
        schema.replay(broken)
    evidence(
        "artifact-" + family,
        dict(exact_full_owner_replay=True, unsealed_water_owner_edit_refused=True),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize(
    "fault", ["water", "pool", "store", "clock-policy", "unsupported-event", "wrong-parent"]
)
def test_cannot_silently_change_prepared_physics_or_native_contract(family, fault):
    raw, _, _, _ = initialized(family)
    schema = OWNERS[family][0]
    value = deepcopy(raw)
    m = value["model"]
    if fault == "water":
        m["water_compartments"][0]["minimum_volume_pL"] *= 0.9
    elif fault == "pool":
        m["energy_pools"][0]["initial_amount_fmol"]["ATP"] *= 0.9
    elif fault == "store":
        m["stores"][0]["model"]["compartments"][0]["volume_pL"] *= 0.9
    elif fault == "clock-policy":
        m["reset_policy"] = "carry_buffers_implicitly"
    elif fault == "unsupported-event":
        m["interventions"][0]["kind"] = "pressure"
    else:
        m["profile_preparation"]["definition"]["model"]["id"] = "resolved_calcium_energy_water@1"
    with pytest.raises(ConfigError):
        schema.parse(value)
    evidence("definition-refusal-" + family + "-" + fault, dict(refused=True, fault=fault))


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize(
    "fault", ["clock-negative", "clock-nan", "clock-end", "volume", "fuel", "padding"]
)
def test_invalid_actual_state_refuses_without_reset_or_repair(family, fault):
    _, spec, state, p = initialized(family)
    _, model, _ = OWNERS[family]
    y = type(state)(*(v.copy() for v in state))
    if fault.startswith("clock"):
        y.phase_clock_s[0] = {
            "clock-negative": -1e-9,
            "clock-nan": np.nan,
            "clock-end": 2 * spec.experiment.end_time,
        }[fault]
    elif fault == "volume":
        y.volume_increment_pL[0] = -p.volume[0]
    elif fault == "fuel":
        y.energy_amount_increment_fmol[0, 0] = -p.energy_initial_amount_fmol[0, 0]
    else:
        y.volume_increment_pL[-1] = 1e-3
    before = [v.tobytes() for v in y]
    u = control(spec, 0.0)
    with np.errstate(all="ignore"):
        assert not model.control_domain_valid(y, u, p, p.active, xp=np)
        with pytest.raises(NumericalError):
            model.check_values(y, spec)
    assert before == [v.tobytes() for v in y]
    evidence(
        "state-refusal-" + family + "-" + fault,
        dict(refused=True, fault=fault, input_unchanged=True),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_checkpoint_phase_clock_is_explicit_and_cannot_reset(family):
    _, spec, state, _ = initialized(family)
    model = OWNERS[family][1]
    model.check_checkpoint(spec, SimpleNamespace(state=state, time=0.0))
    with pytest.raises(ConfigError):
        model.check_checkpoint(spec, SimpleNamespace(state=state, time=1e-6))
    evidence(
        "checkpoint-clock-" + family,
        dict(accepted_clock_preserved=True, implicit_clock_reset_refused=True),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_parent_minimum_volume_bounds_and_native_ramp_resolution_are_retained(family):
    _, spec, _, _ = initialized(family)
    model = OWNERS[family][1]
    times = np.asarray(list(EventGrid(spec)))
    model.check_steps(spec, np.diff(times), control_values(spec, times[:-1]))
    unresolved = replace(spec, execution=replace(spec.execution, dt=0.0625e-6))
    times = np.asarray(list(EventGrid(unresolved)))
    with pytest.raises(ConfigError, match="transition time/8"):
        model.check_steps(unresolved, np.diff(times), control_values(unresolved, times[:-1]))
    evidence(
        "step-admission-" + family,
        dict(
            safe_steps_accepted=True,
            unresolved_native_ramp_refused=True,
            all_parent_water_fuel_chemical_and_damage_checks_retained=True,
        ),
    )


def integrate(spec, family, case, factor):
    model = OWNERS[family][1]
    state, p = model.initial_values(spec)
    times = np.asarray(list(EventGrid(spec)))
    table = control_values(spec, times[:-1])
    model.check_steps(spec, np.diff(times), table)
    values = [state]
    try:
        for i, h in enumerate(np.diff(times)):
            u = type(table)(*(v[i] for v in table))
            state = rk4_step(lambda y, *args: model.rhs(y, *args, xp=np), state, h, u, p, p.active)
            values.append(state)
        history = model.STATE_TYPE(*(np.stack(v) for v in zip(*values, strict=True)))
        diagnostics = model.check_values(history, spec)
    except Exception as error:
        evidence(
            "integration-failure-" + family + "-" + case + "-" + str(factor),
            dict(status="failed", error=str(error), inputs=OWNERS[family][0].to_dict(spec)),
            dict(
                times_s=times[: len(values)],
                **{k: np.stack([getattr(v, k) for v in values]) for k in model.STATE_TYPE._fields},
            ),
        )
        raise
    return times, history, p, diagnostics


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", ["SIM", "close-reopen"])
def test_full_transient_trajectory_at_every_observation_and_control_boundary(family, case):
    raw, spec, _, _ = initialized(family, case, False)
    _, model, _ = OWNERS[family]
    context = reference.bind(raw)
    exact_times, expected, proof = reference.integrate(raw)
    arrays = dict(
        times_s=exact_times,
        reference_flat=expected,
        state_fields=np.asarray(model.STATE_TYPE._fields),
        reference_shapes_json=np.asarray(json.dumps(context["parent"]["shapes"])),
    )
    rows = []
    name = "trajectory-" + family + "-" + case
    transfer_indexes = reference.flatten(
        context,
        {
            k: np.ones_like(v) if k == "membrane_transferred" else np.zeros_like(v)
            for k, v in model.initial_values(spec)[0]._asdict().items()
        },
    ).astype(bool)
    for factor in (1, 2):
        current = replace(spec, execution=replace(spec.execution, dt=spec.execution.dt / factor))
        times, history, p, diagnostics = integrate(current, family, case, factor)
        indexes = [EventGrid(current).exact_index(t) for t in exact_times]
        observed = np.stack(
            [
                reference.flatten(context, model.STATE_TYPE(*(v[i] for v in history))._asdict())
                for i in indexes
            ]
        )
        arrays["production_flat_" + str(factor)] = observed
        arrays.update(
            {
                str(factor) + "__" + key: np.asarray(getattr(history, key))[indexes]
                for key in model.STATE_TYPE._fields
            }
        )
        energy_residual = []
        for vector in observed:
            d = context["process"].unpack(context["parent"], vector[:-1])
            residual = reference.free_energy_change(context, vector)
            residual += sum(np.sum(v) for k, v in d.items() if k.endswith("_dissipated_energy_pJ"))
            residual -= sum(
                np.sum(d[k])
                for k in ("regeneration_supplied_work_pJ", "reservoir_work_pJ", "electrode_work_pJ")
            )
            energy_residual.append(float(residual))
        ratio = score(context, observed, expected)
        row = dict(
            dt_s=current.execution.dt,
            error_over_budget=ratio,
            max_error=float(np.max(np.abs(observed - expected))),
            background_transfer_error_fmol=float(
                np.max(np.abs(observed[:, transfer_indexes] - expected[:, transfer_indexes]))
            ),
            independent_energy_residual_pJ=energy_residual,
            diagnostics=diagnostics,
        )
        rows.append(row)
        if ratio > 1 or max(map(abs, energy_residual)) > 1e-9:
            evidence(
                name, dict(status="failed", inputs=raw, reference=proof, refinements=rows), arrays
            )
        assert ratio <= 1, ratio
        assert max(map(abs, energy_residual)) <= 1e-9
        observed_records = model.observe_history(times, history, p, exact_times, current)
        for key in model.STATE_TYPE._fields:
            np.testing.assert_array_equal(
                getattr(observed_records, key), getattr(history, key)[indexes]
            )
        for j, i in enumerate(indexes):
            actual = model.parent_state(model.STATE_TYPE(*(v[i] for v in history)))
            balance = OWNERS[family][2].balances(actual, model.accounting_layout(p, xp=np))
            np.testing.assert_array_equal(
                observed_records.energy_balance_pJ[j], np.atleast_1d(balance["energy"])
            )
            np.testing.assert_array_equal(
                observed_records.pool_internal_transfer_balance_pJ[j], balance["pool_energy"]
            )
    coarse, fine = [r["background_transfer_error_fmol"] for r in rows]
    resolved = coarse > 1e-20 and fine <= 0.35 * coarse + 1e-22
    if not resolved:
        evidence(
            name,
            dict(
                status="failed",
                inputs=raw,
                reference=proof,
                refinements=rows,
                reason="transient background transfer refinement not resolved",
            ),
            arrays,
        )
    assert resolved, (coarse, fine)
    evidence(
        name,
        dict(
            inputs=raw,
            reference=proof,
            refinements=rows,
            all_observations_compared=True,
            observation_times_s=exact_times.tolist(),
            full_state_fields=len(model.STATE_TYPE._fields),
            trajectory_layout="compact; padding qualified separately at stages",
            original_material_and_work_ledgers=True,
            reported_state_and_balances_from_actual_history=True,
            resolved_background_transfer_refinement=True,
            endpoint_only_claim=False,
            convergence_order_claim=False,
        ),
        arrays,
    )


def test_reference_is_independent_and_frozen_dependencies_unchanged():
    for module in (reference, reference.water, reference.repair):
        for node in ast.walk(ast.parse(Path(module.__file__).read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(("cells", "jax"))
            elif isinstance(node, ast.Import):
                assert not any(n.name.startswith(("cells", "jax")) for n in node.names)
    protocol = json.loads(
        (ROOT / "validation/topology/joint_water_profile_interventions_protocol.json").read_text()
    )
    for name, expected in protocol["readonly_source_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    evidence(
        "reference-manifest",
        dict(no_production_or_jax_reference_import=True, frozen_sources_verified=True),
    )
