"""New held active policy, complete rates/owners and original-history separation."""

import json
import os
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.core import physiology_active_temperature as contract
from cells.core import physiology_random_streams as streams
from cells.core import physiology_temperature as original
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, digest, parse_spec
from cells.models import physiology_active_temperature_view as view
from cells.models import surface_calcium_energy as fuel
from cells.numerics.fixed_step import rk4_step
from cells.processes import betse_global_controls as setters
from cells.processes.mass_action import reversible_flux
from tests.unit.test_physiology_permeability_view import exact_tree
from tests.unit.test_physiology_temperature import setup as original_setup
from validation.tissue import physiology_active_temperature_reference as reference
from validation.tissue import surface_kinetic_reference as catalog

KINDS = ("ionic", "calcium", "fuel", "open-calcium", "open-fuel")


def setup(kind="ionic", *, padded=True, temperature_K=310.15, all_laws=True, empty=False):
    source = original_setup(kind, padded=padded)[0].to_dict()
    ion = source["model"].get("ionic", source["model"])
    if all_laws:
        channels = []
        for i, (law, routes) in enumerate(catalog.CATALOG_V5_PERMEABILITIES.items()):
            gates = (
                [] if law in (catalog.CALCIUM_ACTIVATED_LAW, catalog.HCN_LEAK_LAW) else [0.23, 0.68]
            )
            if law in catalog.MORRIS_LECAR_LAWS:
                gates = [0.23] if law in catalog.ML_DYNAMIC_LAWS else []
            channels.append(
                dict(
                    id=f"all-law-{i}",
                    membrane_id=ion["membranes"][i % len(ion["membranes"])]["id"],
                    kinetic_law=law,
                    initial_gate=gates,
                    max_permeability_m_per_s=1e-14,
                    abundance=0.3,
                    permeant_ions=[
                        dict(species_id=name, relative_permeability=weight)
                        for name, weight in routes
                    ],
                )
            )
        ion["channels"] = channels
        source["execution"]["channel_capacity"] = len(channels) + int(padded)
        source["experiment"]["channel_controls"] = [
            dict(channel_id=row["id"], schedule=[dict(time=0.0, availability=0.67)])
            for row in channels
        ]
    spec = parse_spec(source)
    implementation = view.IMPLEMENTATIONS[type(spec.model)]
    state, layout = implementation.initial_values(spec)
    table = control_values(spec, [0.0])
    held = type(table)(*(value[0] * 0.71 for value in table))
    program = setters.bind(
        membrane_ids=tuple(row.id for row in spec.model.membranes),
        events=() if empty else (setters.Event("temperature", 0.2, 1.2, 0.3, amplitude=0.05),),
        provenance="Declared held active test; no biological thermal calibration",
    )
    binding = contract.bind(
        spec,
        program,
        owners={key: ids[::-1] for key, ids in original.actual_owners(spec).items()},
        policy=contract.POLICY,
        provenance="Every actual physical active-temperature owner is explicit",
    )
    return (
        spec,
        implementation,
        state,
        layout,
        held,
        binding,
        contract.TemperatureMemory(np.asarray(temperature_K)),
    )


def evaluate(case, *, enabled=False, step_s=None):
    spec, _, state, layout, held, binding, memory = case
    return view.evaluate(
        spec,
        state,
        layout,
        held,
        binding,
        memory,
        time_s=0.4,
        events_enabled=enabled,
        step_s=spec.execution.dt / 16 if step_s is None else step_s,
    )


def serial(state):
    return {key: value.tolist() for key, value in state._asdict().items()}


def evidence(name, record, arrays=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(directory) / "active-temperature"
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / (name + ".json")).open("x") as handle:
            json.dump(
                record,
                handle,
                indent=2,
                allow_nan=False,
                default=lambda value: np.asarray(value).tolist(),
            )
            handle.write("\n")
        if arrays is not None:
            np.savez_compressed(folder / (name + ".npz"), **arrays)


def qualify(case, name, *, enabled=False):
    spec, _, state, layout, held, binding, memory = case
    before = [
        (value.dtype.str, value.shape, value.tobytes())
        for value in (*state, *layout, *held, *memory)
    ]
    definition = spec.to_dict()
    actual = evaluate(case, enabled=enabled)
    inputs = dict(
        raw=definition,
        fields=serial(state),
        binding_record=contract.record(binding),
        current_temperature_K=float(memory.temperature_K),
        held_control=serial(held),
        time_s=0.4,
        events_enabled=enabled,
    )
    context, target, phi, proof = reference.evaluate(**inputs)
    packed = reference.flatten(context, actual.derivative._asdict())
    absolute = reference.flatten(
        context,
        {
            key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
            for key, shape in context["shapes"].items()
        },
    )
    budget = absolute + 3e-10 * abs(target)
    rate_error = float(np.max(abs(packed - target) / budget, initial=0))
    p = actual.runtime_layout
    potential = np.r_[
        actual.field.potential_V[: p.active.size][p.active],
        actual.field.potential_V[p.active.size :][p.outside_active],
    ]
    phi_budget = 3e-13 + 3e-10 * abs(phi)
    phi_error = float(np.max(abs(potential - phi) / phi_budget, initial=0))
    finite = hasattr(p, "energy_initial_amount_fmol")
    stage = fuel.stage_layout(state, p, xp=np) if finite else p
    cache = np.asarray(proof["stage_pump_drive_J_mol"])
    cache_error = float(
        np.max(
            abs(stage.pump_drive[: cache.size] - cache) / (3e-10 + 3e-10 * abs(cache)), initial=0
        )
    )
    field_error, saved_fields = 0.0, {}
    n, o = (
        context["shapes"]["amount_increment"][-1],
        context["shapes"]["extracellular_amount_increment"][-1],
    )
    for key, column in proof["physical_field_columns"].items():
        value = actual.field
        for part in key.split("."):
            value = getattr(value, part)
        value, expected = np.asarray(value), np.asarray(column["value"])
        if key in ("capacitor_node_charge_C", "charge_residual_C"):
            value = np.r_[value[:n], value[p.active.size : p.active.size + o]]
        elif expected.ndim:
            value = value[tuple(slice(0, size) for size in expected.shape)]
        saved_fields["field__" + key.replace(".", "__")] = value
        field_error = max(
            field_error,
            float(
                np.max(
                    abs(value - expected) / (column["atol"] + column["rtol"] * abs(expected)),
                    initial=0,
                )
            ),
        )
    evidence(
        name,
        dict(
            inputs=inputs,
            reference=proof,
            maximum_rate_error_fraction=rate_error,
            maximum_potential_error_fraction=phi_error,
            maximum_stage_drive_error_fraction=cache_error,
            maximum_physical_field_error_fraction=field_error,
            physical_field_columns=len(proof["physical_field_columns"]),
            stage_energy_residual_pJ_s=float(actual.field.energy_balance_pJ_s),
            actual_temperature_K=float(actual.preparation.state.temperature_K),
            policy=contract.POLICY,
            channel_laws=[row.kinetic_law for row in spec.model.channels],
            accepted_thermal_transition=False,
        ),
        dict(
            actual_rate=packed,
            expected_rate=target,
            rate_budget=budget,
            actual_phi=potential,
            expected_phi=phi,
            phi_budget=phi_budget,
            stage_pump_drive_J_mol=stage.pump_drive[: cache.size],
            expected_stage_pump_drive_J_mol=cache,
            **saved_fields,
        ),
    )
    assert max(rate_error, phi_error, cache_error, field_error) <= 1
    assert abs(float(actual.field.energy_balance_pJ_s)) <= 1e-10
    if "physical_energy_balance_pJ_s" in proof:
        assert abs(proof["physical_energy_balance_pJ_s"]) <= 1e-10
    assert spec.to_dict() == definition
    assert before == [
        (value.dtype.str, value.shape, value.tobytes())
        for value in (*state, *layout, *held, *memory)
    ]
    for key in layout._fields:
        if key not in view.PROJECTED_FIELDS:
            np.testing.assert_array_equal(getattr(p, key), getattr(layout, key), strict=True)
    if hasattr(p, "er_standard_mu_RT"):
        np.testing.assert_allclose(
            p.er_standard_mu_RT * p.er_temperature[:, None],
            layout.er_standard_mu_RT * layout.er_temperature[:, None],
            atol=3e-14,
            rtol=3e-14,
        )
        np.testing.assert_array_equal(p.er_forward_rate, layout.er_forward_rate)
    assert not actual.admission["checkpoint_admission"]
    assert actual.thermodynamic_assumptions["accepted_heat_pJ"] is None
    assert not actual.thermodynamic_assumptions["accepted_thermal_transition"]
    return actual


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("padded", (False, True))
@pytest.mark.parametrize("temperature_K", (273.15, 310.15))
def test_full56_complete_initial_and_original_evolved_active_rates(kind, padded, temperature_K):
    case = setup(kind, padded=padded, temperature_K=temperature_K)
    spec, model, state, layout, held, binding, memory = case
    assert len(spec.model.channels) == 56
    assert contract.restore(json.loads(json.dumps(contract.record(binding))), spec) == binding
    for stage in range(2):
        qualify(
            (spec, model, state, layout, held, binding, memory),
            f"full56-{kind}-{padded}-{temperature_K}-{stage}",
        )
        if stage == 0:
            state = rk4_step(
                lambda y, u, p, a: model.rhs(y, u, p, a, xp=np),
                state,
                spec.execution.dt / 16,
                held,
                layout,
                layout.active,
            )
            model.check_values(state, spec)


@pytest.mark.parametrize("kind", KINDS)
def test_reference_temperature_identity_disabled_empty_zero_setter_and_no_random_draw(
    kind, monkeypatch
):
    case = setup(kind, temperature_K=298.15)
    spec, model, state, layout, held, binding, memory = case
    state = rk4_step(
        lambda y, u, p, a: model.rhs(y, u, p, a, xp=np),
        state,
        spec.execution.dt / 16,
        held,
        layout,
        layout.active,
    )
    case = (spec, model, state, layout, held, binding, memory)
    monkeypatch.setattr(
        streams, "draw", lambda *a, **k: pytest.fail("Held active rates consumed RNG")
    )
    actual = qualify(case, "identity-" + kind)
    exact_tree(actual.readouts, model.readouts(state, held, layout, xp=np))
    exact_tree(actual.runtime_layout, layout)
    program = setters.bind(
        membrane_ids=binding.original_binding.program.membrane_ids,
        events=(),
        provenance="Empty temperature source",
    )
    empty = contract.bind(
        spec,
        program,
        owners=original.actual_owners(spec),
        policy=contract.POLICY,
        provenance="Empty source with actual owners",
    )
    actual_empty = evaluate((spec, model, state, layout, held, empty, memory), enabled=True)
    exact_tree(actual_empty.readouts, actual.readouts)
    zero_program = setters.bind(
        membrane_ids=program.membrane_ids,
        events=(setters.Event("temperature", 0.2, 1.2, 0.3, amplitude=0.0),),
        provenance="Zero amplitude temperature source",
    )
    zero = contract.bind(
        spec,
        zero_program,
        owners=original.actual_owners(spec),
        policy=contract.POLICY,
        provenance="Explicit zero-amplitude owners",
    )
    exact_tree(
        evaluate((spec, model, state, layout, held, zero, memory), enabled=True).readouts,
        actual.readouts,
    )


@pytest.mark.parametrize("kind", KINDS)
def test_enabled_native_setter_changed_T_has_full_independent_owner_rates(kind):
    qualify(setup(kind, temperature_K=298.15), "setter-" + kind, enabled=True)


@pytest.mark.parametrize("kind", KINDS)
def test_old_model_and_adapter_guards_remain_and_runtime_layout_is_not_source_checkpoint(kind):
    case = setup(kind, all_laws=False)
    spec, model, state, layout, held, binding, memory = case
    raw = spec.to_dict()
    raw["model"].get("ionic", raw["model"])["temperature_K"] = 310.15
    for store in raw["model"].get("stores", []):
        store["model"]["temperature_K"] = 310.15
    with pytest.raises((ConfigError, ValueError)):
        parse_spec(raw)
    with pytest.raises(original.TemperatureRejected):
        original.prepare(
            spec,
            binding.original_binding,
            original.TemperatureState(np.asarray(310.15)),
            time_s=0.4,
            events_enabled=False,
        )
    actual = evaluate(case)
    with pytest.raises(ValueError, match="layout"):
        evaluate((spec, model, state, actual.runtime_layout, held, binding, memory))
    changed_source = replace(spec, model=replace(spec.model, temperature_K=310.15))
    with pytest.raises(ValueError, match="298.15"):
        contract.restore(contract.record(binding), changed_source)


@pytest.mark.parametrize("temperature_K", (0.0, -1.0, 199.99, 400.01, float("nan"), float("inf")))
def test_invalid_memory_is_refused_without_material_or_history_mutation(temperature_K):
    case = setup(all_laws=False, temperature_K=temperature_K)
    with pytest.raises(ValueError):
        evaluate(case)


@pytest.mark.parametrize(
    "key",
    (
        "policy",
        "standard_energy_policy",
        "finite_calcium_standard",
        "kinetics",
        "native_compatibility",
        "reference_temperature_K",
    ),
)
def test_resealed_policy_changes_are_refused(key):
    spec, _, _, _, _, binding, _ = setup(all_laws=False)
    saved = deepcopy(contract.record(binding))
    saved[key] = "unreviewed"
    saved["identity"] = digest({name: value for name, value in saved.items() if name != "identity"})
    with pytest.raises(ValueError):
        contract.restore(saved, spec)


@pytest.mark.parametrize("temperature_K", (200.0, 400.0))
def test_fixed_J_ER_coefficients_have_detailed_balance_with_fixed_forward_rates(temperature_K):
    case = setup("calcium", all_laws=False, temperature_K=temperature_K)
    spec, model, _, layout, _, _, _ = case
    runtime, _, _ = view._runtime(spec, layout, model, np.asarray(temperature_K))
    for i in range(runtime.er_temperature.size):
        p = model.store_layout(runtime, i)
        activities = np.broadcast_to(np.exp(-p.standard_mu_RT[:, None]), p.reactants.shape)
        flux, affinity = reversible_flux(
            activities, p.reactants, p.products, p.delta_mu_RT, p.forward_rate, xp=np
        )
        assert np.max(abs(flux), initial=0) <= 3e-12
        assert np.max(abs(affinity), initial=0) <= 3e-12
        np.testing.assert_array_equal(runtime.er_forward_rate, layout.er_forward_rate)


def test_explicit_policy_and_actual_owner_association_are_required():
    spec, _, _, _, _, binding, _ = setup(all_laws=False)
    owners = original.actual_owners(spec)
    program = binding.original_binding.program
    with pytest.raises(ValueError):
        contract.bind(spec, program, owners=owners, policy="implicit", provenance="x")
    owners["fuel_pools"] = ("invented",)
    with pytest.raises(ValueError):
        contract.bind(spec, program, owners=owners, policy=contract.POLICY, provenance="x")
