"""Full56 scheduled ECM stages, exact owners and persistent closed-face history."""

import importlib
import json
import os
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from cells.core import environment_barrier_composition_preparation as bridge
from cells.core.errors import NumericalError
from cells.core.grid import EventGrid
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, digest, parse_spec
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_step
from validation.transport import owned_barrier_interventions_fixtures as fixtures
from validation.transport import owned_barrier_interventions_reference as reference

MODULES = dict(ionic="active", calcium="calcium", energy="calcium_energy")


def modules(family):
    name = "surface_" + MODULES[family] + "_barrier_interventions"
    return (
        importlib.import_module("cells.core." + name + "_spec"),
        importlib.import_module("cells.models." + name),
    )


def evidence(name, record, arrays=None):
    if root := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        destination = Path(root) / "complete-scheduled-barriers"
        destination.mkdir(parents=True, exist_ok=True)
        (destination / (name + ".json")).write_text(
            json.dumps(record, indent=2, allow_nan=False, default=lambda v: np.asarray(v).tolist())
            + "\n"
        )
        if arrays is not None:
            np.savez_compressed(destination / (name + ".npz"), **arrays)


@lru_cache
def initialized(family="energy", case="partial", *, permuted=False, padded=True):
    values = fixtures.inputs(family, case, permuted=permuted, padded=padded)
    prepared = bridge.prepare(values["request"])
    raw = fixtures.assemble(values, prepared)
    schema, model = modules(family)
    spec = schema.parse(raw)
    state, layout = model.initial_values(spec)
    return raw, spec, state, layout


def control(spec, time):
    table = control_values(spec, [time])
    return type(table)(*(v[0] for v in table))


def budgets(context, target):
    return reference.flatten(
        context,
        {k: np.full(s, 3e-23 if k.endswith("_C") else 3e-12) for k, s in context["shapes"].items()},
    ) + 3e-10 * np.abs(target)


def copied(state):
    return type(state)(*(np.array(v, copy=True) for v in state))


def manufactured(state, p, spec):
    value = copied(state)
    species, membrane = spec.model.species_ids.index("K"), 0
    amount = 1e-5
    inside, outside = p.membrane_cell[membrane], p.membrane_outside[membrane]
    value.amount_increment[species, inside] -= amount
    value.extracellular_amount_increment[species, outside] += amount
    value.membrane_transferred[species, membrane] += amount
    if hasattr(value, "chemical_amount_increment"):
        value.chemical_amount_increment[inside] -= (
            amount * p.free_ion_selector[:, species, None] * p.cytosol_selector[inside]
        )
    # A distinct state of every live fuel pool prevents initial-pool proxies.
    if hasattr(value, "energy_amount_increment_fmol"):
        value.energy_amount_increment_fmol[0, p.active] -= 2e-4
        value.energy_amount_increment_fmol[1, p.active] += 2e-4
        value.energy_amount_increment_fmol[2, p.active] += 2e-4
    return value


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_exact_parent_initialization_serialization_and_catalog(family):
    schema, model = modules(family)
    raw, spec, state, p = initialized(family, permuted=True)
    parent = schema.owner_spec(spec)
    original, original_layout = model.base.initial_values(parent)
    assert type(parent.model) is type(spec.model).__bases__[0]
    assert parent.to_dict()["model"]["id"] == fixtures.PARENT_IDS[family]
    assert len(state) == dict(ionic=20, calcium=35, energy=39)[family]
    assert type(model.parent_layout(p)) is model.base.LAYOUT_TYPE
    for key in original._fields:
        np.testing.assert_array_equal(getattr(state, key), getattr(original, key))
    for key in original_layout._fields:
        np.testing.assert_array_equal(getattr(p, key), getattr(original_layout, key))
    assert set(p.channel_laws[p.channel_active]) == set(range(56))
    assert len(spec.model.channels) == 63
    np.testing.assert_array_equal(state.phase_clock_s, [0.0])
    serialized = schema.to_dict(spec)
    assert serialized == raw
    assert parse_spec(serialized) == spec
    assert get_model(spec.model) is model
    assert spec.fingerprint == digest(serialized)
    sealed = schema.artifact(spec)
    assert schema.replay(sealed) == spec
    model.check_values(state, spec)
    evidence(
        "exact-owner-" + family,
        dict(
            definition=serialized,
            state_fields=list(state._fields),
            parent_model_id=parent.to_dict()["model"]["id"],
            complete_initial_state_exact=True,
            complete_initial_layout_exact=True,
            distinct_channel_laws=56,
            populations=63,
            artifact=sealed,
        ),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", ("partial", "asymmetric", "reseal"))
@pytest.mark.parametrize("changed", (False, True))
def test_complete_stage_field_rhs_energy_and_coefficients(family, case, changed):
    _, model = modules(family)
    raw, spec, initial, p = initialized(family, case, permuted=changed)
    context = reference.bind(raw)
    proofs, arrays = [], {}
    clocks = (0.0, 2e-6, 4.5e-6, 7e-6, spec.experiment.end_time)
    for index, time in enumerate(clocks):
        state = manufactured(initial, p, spec) if changed else copied(initial)
        state = state._replace(phase_clock_s=np.asarray([time]))
        assert model.domain_valid(state, p, p.active, xp=np)
        target, potential, proof = reference.evaluate(
            context, reference.flatten(context, state._asdict()), time
        )
        actual_state = model.rhs(state, control(spec, time), p, p.active, xp=np)
        actual = reference.flatten(context, actual_state._asdict())
        budget = budgets(context, target)
        field = model.field_values(state, control(spec, time), p, xp=np)
        n = p.active.size
        observed_phi = np.r_[
            field.potential_V[:n][p.active], field.potential_V[n:][p.outside_active]
        ]
        signal, coefficients = model.signal_values(state, p, xp=np), proof["ecm_coefficients"]
        species = spec.model.species_ids
        sites = raw["model"]["barrier_preparation"]["provenance"]["request"]["grid"]["site_ids"]
        expected_sites = [
            [coefficients["site_effective_m2_s"][s][k] for k in sites] for s in species
        ]
        expected_faces = [
            [coefficients["face_m2_s"][s][f.id] for f in spec.model.faces] for s in species
        ]
        np.testing.assert_allclose(signal.site_diffusivity, expected_sites, rtol=5e-14, atol=2e-26)
        np.testing.assert_allclose(
            signal.face_diffusivity[:, p.face_active], expected_faces, rtol=5e-14, atol=2e-26
        )
        np.testing.assert_allclose(signal.pulse, coefficients["pulse"], rtol=5e-14, atol=5e-16)
        np.testing.assert_allclose(
            signal.sodium_weight,
            [coefficients["sodium_weight"][s] for s in sites],
            rtol=5e-14,
            atol=5e-16,
        )
        ratio = float(np.max(np.abs(actual - target) / budget, initial=0))
        proofs.append(
            dict(
                time_s=time,
                error_over_budget=ratio,
                independent=proof,
                energy_residual_pJ_s=float(field.energy_balance_pJ_s),
            )
        )
        arrays.update(
            {
                f"{index}-{key}": value
                for key, value in dict(
                    state=reference.flatten(context, state._asdict()),
                    actual=actual,
                    reference=target,
                    budget=budget,
                    potential=observed_phi,
                    reference_potential=potential,
                ).items()
            }
        )
        evidence(
            f"stages-{family}-{case}-{changed}",
            dict(definition=raw, changed=changed, comparisons=proofs),
            arrays,
        )
        assert ratio <= 1
        assert field.converged and abs(field.energy_balance_pJ_s) <= 1e-10
        assert abs(proof["physical_energy_balance_pJ_s"]) <= 1e-10
        assert proof["max_charge_residual_C"] <= 3e-25
        assert proof["max_component_current_residual_A"] <= 1e-23
        np.testing.assert_allclose(observed_phi, potential, rtol=3e-10, atol=3e-13)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", ("init", "none", "blocked"))
def test_disabled_opening_has_bitwise_exact_full_parent_rhs(family, case):
    _, model = modules(family)
    _, spec, state, p = initialized(family, case)
    state = manufactured(state, p, spec)._replace(phase_clock_s=np.asarray([4.5e-6]))
    u = control(spec, 4.5e-6)
    actual = model.rhs(state, u, p, p.active, xp=np)
    expected = model.base.rhs(model.parent_state(state), u, model.parent_layout(p), p.active, xp=np)
    for key in model.base.STATE_TYPE._fields:
        np.testing.assert_array_equal(getattr(actual, key), getattr(expected, key))
    np.testing.assert_array_equal(actual.phase_clock_s, [1.0])
    evidence(f"disabled-{family}-{case}", dict(all_parent_derivatives_bitwise_exact=True))


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_duplicate_occurrences_preserve_single_opening(family):
    _, model = modules(family)
    _, _, state, first = initialized(family)
    _, _, _, repeated = initialized(family, "duplicate")
    state = state._replace(phase_clock_s=np.asarray([4.5e-6]))
    for a, b in zip(
        model.signal_values(state, first, xp=np),
        model.signal_values(state, repeated, xp=np),
        strict=True,
    ):
        np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_closed_face_keeps_actual_history_and_observations(family):
    _, model = modules(family)
    raw, spec, initial, p = initialized(family, "reseal")
    state = copied(initial)._replace(phase_clock_s=np.asarray([spec.experiment.end_time]))
    signal = model.signal_values(state, p, xp=np)
    species, face = np.argwhere((p.barrier_union_factor > 0) & (signal.face_factor == 0))[0]
    amount = 1e-12
    sender, receiver = p.face_sender[face], p.face_receiver[face]
    state.face_transferred[species, face] = amount
    state.extracellular_amount_increment[species, sender] -= amount
    state.extracellular_amount_increment[species, receiver] += amount
    before = copied(state)
    assert model.domain_valid(state, p, p.active, xp=np)
    assert not model.base.domain_valid(
        model.parent_state(state),
        model.parent_layout(p)._replace(face_factor=signal.face_factor),
        p.active,
        xp=np,
    )
    diagnostics = model.check_values(state, spec)
    field = model.field_values(state, control(spec, spec.experiment.end_time), p, xp=np)
    assert field.converged
    context = reference.bind(raw)
    target, _, proof = reference.evaluate(
        context, reference.flatten(context, state._asdict()), spec.experiment.end_time
    )
    actual = reference.flatten(
        context,
        model.rhs(state, control(spec, spec.experiment.end_time), p, p.active, xp=np)._asdict(),
    )
    assert np.max(np.abs(actual - target) / budgets(context, target)) <= 1
    times = np.asarray([spec.experiment.end_time])
    observed = model.observe_history(
        times, model.STATE_TYPE(*(v[None] for v in state)), p, times, spec
    )
    for key in model.base.STATE_TYPE._fields:
        np.testing.assert_array_equal(getattr(observed, key)[0], getattr(state, key))
    for a, b in zip(state, before, strict=True):
        np.testing.assert_array_equal(a, b)
    evidence(
        "closed-history-" + family,
        dict(
            definition=raw,
            species=int(species),
            face=int(face),
            diagnostics=diagnostics,
            independent=proof,
            all_history_exact=True,
        ),
        {"state-" + k: v for k, v in state._asdict().items()}
        | {"observed-" + k: v for k, v in vars(observed).items()},
    )


@pytest.mark.parametrize(
    "fault",
    (
        "physical_owner",
        "recipe",
        "coefficient",
        "parent_identity",
        "unknown_site",
        "empty_sites",
        "negative",
        "excess",
        "boolean",
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
    ),
)
def test_invalid_full_owner_recipe_and_event_refused(fault):
    schema, _ = modules("energy")
    raw = deepcopy(initialized()[0])
    model, event = raw["model"], raw["model"]["intervention"]
    if fault == "physical_owner":
        model["energy_pools"][0]["initial_amount_fmol"]["ATP"] *= 2
    if fault == "recipe":
        model["barrier_preparation"]["provenance"]["request"]["tight_factor"] *= 2
    if fault == "coefficient":
        model["barrier_preparation"]["definition"]["model"]["ionic"]["faces"][0]["area_m2"] *= 2
    if fault == "parent_identity":
        model["barrier_preparation"]["definition"]["model"]["id"] = "resolved_calcium_energy@4"
    if fault == "unknown_site":
        event["site_ids"] = ["unowned"]
    if fault == "empty_sites":
        event["site_ids"] = []
    if fault == "negative":
        event["amplitude"] = -0.1
    if fault == "excess":
        event["amplitude"] = 1.1
    if fault == "boolean":
        event["amplitude"] = True
    if fault == "nonfinite":
        event["change_s"] = float("inf")
    if fault == "reversed":
        event["off_s"] = event["on_s"]
    if fault == "zero_transition":
        event["change_s"] = 0.0
    if fault == "outside_horizon":
        event["off_s"] = 2 * raw["experiment"]["end_time"]
    if fault == "capacity":
        raw["execution"]["barrier_target_capacity"] = 1
    if fault == "phase":
        model["phase"] = "INHERITED"
    if fault == "policy":
        model["timing_policy"] = "frozen_clock"
    if fault == "unknown_field":
        event["rate_scale"] = 0.1
    if fault == "schema_bool":
        raw["schema_version"] = True
    if fault == "list_events":
        model["intervention"] = [event]
    if fault == "implicit_capacity":
        raw["execution"].pop("barrier_target_capacity")
    with pytest.raises(ConfigError):
        schema.parse(raw)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_full_step_and_actual_history_admission(family):
    _, model = modules(family)
    _, spec, state, p = initialized(family, "reseal")
    times = np.asarray(list(EventGrid(spec)))
    table = control_values(spec, times[:-1])
    model.check_steps(spec, np.diff(times), table)
    with pytest.raises(ConfigError):
        model.check_steps(spec, np.asarray([spec.model.intervention.change_s]), table)
    for name in ("amount_increment", "channel_gate", "face_transferred", "phase_clock_s"):
        invalid = copied(state)
        getattr(invalid, name).flat[0] = np.nan
        assert not model.domain_valid(invalid, p, p.active, xp=np)
        with pytest.raises(NumericalError):
            model.check_values(invalid, spec)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_short_rk4_uses_stage_clock_with_every_parent_field(family):
    _, model = modules(family)
    raw, spec, state, p = initialized(family)
    # Four accepted steps are a stage-coupling smoke, not a transient claim.
    times = np.asarray(list(EventGrid(spec)))[:5]
    table = control_values(spec, times[:-1])
    model.check_steps(spec, np.diff(times), table)
    states = [state]
    for i, step in enumerate(np.diff(times)):
        u = type(table)(*(v[i] for v in table))

        def checked_rhs(trial, u=u):
            assert model.control_domain_valid(trial, u, p, p.active, xp=np)
            return model.rhs(trial, u, p, p.active, xp=np)

        state = rk4_step(checked_rhs, state, step)
        assert model.domain_valid(state, p, p.active, xp=np)
        states.append(state)
    history = model.STATE_TYPE(*(np.stack(v) for v in zip(*states, strict=True)))
    diagnostics = model.check_values(history, spec)
    np.testing.assert_allclose(
        history.phase_clock_s[:, 0], times, rtol=0, atol=p.phase_clock_atol_s
    )
    evidence(
        "short-rk4-" + family,
        dict(
            definition=raw,
            diagnostics=diagnostics,
            scope="four-step full-owner stage smoke; no transient/refinement credit",
        ),
        {"times": times} | {"state-" + k: v for k, v in history._asdict().items()},
    )
