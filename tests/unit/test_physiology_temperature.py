"""Planned held-T qualification; numerical execution waits for CPU5 release."""

import json
import os
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.core import physiology_random_streams as streams
from cells.core import physiology_temperature as temperature
from cells.core.schedule import control_values
from cells.core.specs import digest, parse_spec
from cells.models import physiology_temperature_view as view
from cells.numerics.fixed_step import rk4_step
from cells.processes import betse_global_controls as setters
from tests.unit.test_physiology_boundary_voltage import fixture as open_fixture
from tests.unit.test_physiology_permeability_view import exact_tree, readouts
from tests.unit.test_physiology_tissue_binding import definition
from validation.perturbations import global_controls_native as native
from validation.tissue import physiology_temperature_reference as reference
from validation.tissue import surface_dynamics_fixtures as passive


def setup(
    kind="passive", *, padded=True, open_world=False, amplitude=0.05, empty=False, scenario="normal"
):
    if kind == "passive":
        raw = passive.definition("open" if open_world else "closed", padded=padded)
        if not padded:
            for key in ("cells", "extracellular", "membranes", "species"):
                raw["model"][key].reverse()
        spec = parse_spec(raw)
    elif kind.startswith("open-"):
        spec = open_fixture("fuel" if kind == "open-fuel" else "calcium", padded=padded)[0]
    else:
        spec = parse_spec(definition(kind, padded=padded, reorder=not padded))
    if scenario == "empty-channels":
        raw = spec.to_dict()
        raw["model"].get("ionic", raw["model"])["channels"] = []
        raw["experiment"]["channel_controls"] = []
        spec = parse_spec(raw)
    implementation = view.IMPLEMENTATIONS[type(spec.model)]
    state, layout = implementation.initial_values(spec)
    table = control_values(spec, [0.0])
    held = type(table)(*(value[0] * 0.67 for value in table))
    if scenario == "blocked":
        held = type(held)(*(np.zeros_like(value) for value in held))
    program = setters.bind(
        membrane_ids=tuple(row.id for row in spec.model.membranes),
        events=() if empty else (setters.Event("temperature", 0.2, 1.2, 0.3, amplitude=amplitude),),
        provenance="Synthetic Kelvin setter; no caloric or biological calibration",
    )
    owners = {key: ids[::-1] for key, ids in temperature.actual_owners(spec).items()}
    binding = temperature.bind(
        spec, program, owners=owners, provenance="Explicit uniform-temperature physical owners"
    )
    current = temperature.TemperatureState(np.asarray(spec.model.temperature_K))
    return spec, implementation, state, layout, held, binding, current


def evidence(name, record, arrays=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(directory) / "temperature"
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


def evaluate(case, *, time_s=0.4, events_enabled=True):
    spec, _, state, layout, held, binding, current = case
    return view.evaluate(
        spec,
        state,
        layout,
        held,
        binding,
        current,
        time_s=time_s,
        events_enabled=events_enabled,
        step_s=spec.execution.dt / 16,
    )


@pytest.mark.parametrize("padded", (False, True))
@pytest.mark.parametrize("open_world", (False, True))
@pytest.mark.parametrize("amplitude", (-0.04, 0.05))
def test_complete_passive_initial_and_evolved_fields_rates_native_T_and_functional(
    padded, open_world, amplitude
):
    case = setup(padded=padded, open_world=open_world, amplitude=amplitude)
    spec, model, state, layout, held, binding, current = case
    saved = temperature.record(binding)
    assert temperature.restore(json.loads(json.dumps(saved)), spec) == binding
    for stage in range(2):
        before = (
            json.dumps(spec.to_dict(), sort_keys=True),
            [(value.dtype.str, value.shape, value.tobytes()) for value in (*state, *layout, *held)],
            current.temperature_K.tobytes(),
        )
        actual = evaluate((spec, model, state, layout, held, binding, current))
        inputs = dict(
            raw=spec.to_dict(),
            fields={key: value.tolist() for key, value in state._asdict().items()},
            binding_record=saved,
            current_temperature_K=float(current.temperature_K),
            held_control={key: value.tolist() for key, value in held._asdict().items()},
            time_s=0.4,
            events_enabled=True,
        )
        context, target, phi, proof = reference.evaluate(**inputs)
        oracle = reference.ORACLES[spec.to_dict()["model"]["id"]]
        packed = oracle.flatten(context, actual.derivative._asdict())
        absolute = oracle.flatten(
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
        shift = actual.thermodynamic_assumptions["finite_owner_mixing_functional_shift_pJ"]
        functional_error = abs(shift - proof["finite_owner_mixing_functional_shift_pJ"]) / (
            3e-14 + 3e-10 * abs(proof["finite_owner_mixing_functional_shift_pJ"])
        )
        source_state = dict(
            temperature_K=float(current.temperature_K),
            junction_available=[1.0] * len(binding.program.membrane_ids),
            pump_available=1.0,
            boundary_voltage_V=[0.0] * 4,
        )
        expected_T = native.evaluate(
            setters.record(binding.program), source_state, 0.4, spec.model.temperature_K
        )
        evidence(
            f"passive-{padded}-{open_world}-{amplitude}-{stage}",
            dict(
                inputs=inputs,
                reference=proof,
                native=expected_T,
                max_rate_error_fraction=rate_error,
                max_potential_error_fraction=phi_error,
                max_functional_error_fraction=functional_error,
                stage_energy_residual_pJ_s=float(actual.field.energy_balance_pJ_s),
                accepted_thermal_transition=False,
            ),
            dict(
                actual_rate=packed,
                expected_rate=target,
                rate_budget=budget,
                actual_phi=potential,
                expected_phi=phi,
                phi_budget=phi_budget,
            ),
        )
        assert max(rate_error, phi_error, functional_error) <= 1
        assert float(actual.preparation.state.temperature_K) == expected_T["temperature_K"]
        assert abs(float(actual.field.energy_balance_pJ_s)) <= 1e-10
        for key in layout._fields:
            if key != "temperature":
                np.testing.assert_array_equal(
                    getattr(actual.runtime_layout, key), getattr(layout, key), strict=True
                )
        after = (
            json.dumps(spec.to_dict(), sort_keys=True),
            [(value.dtype.str, value.shape, value.tobytes()) for value in (*state, *layout, *held)],
            current.temperature_K.tobytes(),
        )
        assert before == after
        assert actual.thermodynamic_assumptions["accepted_heat_pJ"] is None
        assert actual.admission["accepted_thermal_stepping"] is False
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


@pytest.mark.parametrize(
    "kind", ("passive", "ionic", "calcium", "fuel", "open-calcium", "open-fuel")
)
def test_disabled_empty_and_enabled_zero_amplitude_keep_exact_complete_original_readouts(
    kind, monkeypatch
):
    case = setup(kind, amplitude=0.0)
    spec, model, state, layout, held, binding, current = case
    state = rk4_step(
        lambda y, u, p, a: model.rhs(y, u, p, a, xp=np),
        state,
        spec.execution.dt / 16,
        held,
        layout,
        layout.active,
    )
    model.check_values(state, spec)
    case = (spec, model, state, layout, held, binding, current)

    def forbidden(*args, **kwargs):
        pytest.fail("A held-T view consumed a random stream")

    monkeypatch.setattr(streams, "draw", forbidden)
    expected, derivative = readouts(model, state, held, layout)
    for enabled in (False, True):
        actual = evaluate(case, events_enabled=enabled)
        exact_tree(actual.readouts, expected)
        exact_tree(actual.derivative, derivative)
        exact_tree(actual.runtime_layout, layout)
        assert actual.thermodynamic_assumptions["finite_owner_mixing_functional_shift_pJ"] == 0
    inputs = dict(
        raw=spec.to_dict(),
        fields={key: value.tolist() for key, value in state._asdict().items()},
        binding_record=temperature.record(binding),
        current_temperature_K=float(current.temperature_K),
        held_control={key: value.tolist() for key, value in held._asdict().items()},
        time_s=0.4,
        events_enabled=True,
    )
    context, target, phi, proof = reference.evaluate(**inputs)
    oracle = reference.ORACLES[spec.to_dict()["model"]["id"]]
    packed = oracle.flatten(context, actual.derivative._asdict())
    absolute = oracle.flatten(
        context,
        {
            key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
            for key, shape in context["shapes"].items()
        },
    )
    budget = absolute + 3e-10 * abs(target)
    error = float(np.max(abs(packed - target) / budget, initial=0))
    potential = np.r_[
        actual.field.potential_V[: layout.active.size][layout.active],
        actual.field.potential_V[layout.active.size :][layout.outside_active],
    ]
    phi_budget = 3e-13 + 3e-10 * abs(phi)
    phi_error = float(np.max(abs(potential - phi) / phi_budget, initial=0))
    evidence(
        "identity-" + kind,
        dict(
            inputs=inputs,
            reference=proof,
            max_rate_error_fraction=error,
            max_potential_error_fraction=phi_error,
            max_functional_error_fraction=0.0,
            stage_energy_residual_pJ_s=float(actual.field.energy_balance_pJ_s),
            exact_evolved_identity=True,
            accepted_thermal_transition=False,
        ),
        dict(
            actual_rate=packed,
            expected_rate=target,
            rate_budget=budget,
            actual_phi=potential,
            expected_phi=phi,
            phi_budget=phi_budget,
        ),
    )
    assert max(error, phi_error) <= 1
    empty = setters.bind(
        membrane_ids=binding.program.membrane_ids, events=(), provenance="Explicit empty T program"
    )
    empty_binding = temperature.bind(
        spec, empty, owners=dict(binding.owners), provenance=binding.provenance
    )
    actual = evaluate((*case[:5], empty_binding, current))
    exact_tree(actual.readouts, expected)


@pytest.mark.parametrize("kind", ("ionic", "calcium", "fuel", "open-calcium", "open-fuel"))
@pytest.mark.parametrize("scenario", ("normal", "blocked", "empty-channels"))
def test_changed_active_T_refuses_with_full_native_proposal_without_reinterpreting_catalog(
    kind, scenario
):
    case = setup(kind, scenario=scenario)
    spec, _, state, layout, held, binding, current = case
    before = [value.tobytes() for value in (*state, *layout, *held)]
    with pytest.raises(temperature.TemperatureRejected, match="298.15") as caught:
        evaluate(case)
    assert (
        float(caught.value.trial["source_values"].state.temperature_K) != spec.model.temperature_K
    )
    assert before == [value.tobytes() for value in (*state, *layout, *held)]
    evidence(
        "active-refusal-" + kind + "-" + scenario,
        dict(
            model_id=spec.to_dict()["model"]["id"],
            proposed_temperature_K=float(caught.value.trial["source_values"].state.temperature_K),
            parent_unchanged=True,
            changed_temperature_coverage=False,
        ),
    )


@pytest.mark.parametrize("corruption", ("owner", "source", "units", "program", "extra"))
def test_resealed_owner_source_unit_and_program_corruption_refuses(corruption):
    spec, _, _, _, _, binding, _ = setup()
    saved = deepcopy(temperature.record(binding))
    if corruption == "owner":
        saved["owners"][0][1] = ["invented-cell"]
    elif corruption == "source":
        saved["source_definition_sha256"] = "0" * 64
    elif corruption == "units":
        saved["units"]["temperature"] = "degrees_Celsius"
    elif corruption == "program":
        saved["program"]["events"][0]["kind"] = "voltage"
    else:
        saved["extra"] = True
    saved["identity"] = digest({key: value for key, value in saved.items() if key != "identity"})
    with pytest.raises(ValueError):
        temperature.restore(saved, spec)


@pytest.mark.parametrize("amplitude", (-3.0, -4.0))
def test_nonpositive_native_T_retains_raw_invalid_trial(amplitude):
    case = setup(amplitude=amplitude)
    with pytest.raises(temperature.TemperatureRejected, match="nonphysical") as caught:
        evaluate(case)
    assert float(caught.value.trial["source_values"].state.temperature_K) <= 0
    spec, _, _, _, _, binding, current = case
    source_state = dict(
        temperature_K=float(current.temperature_K),
        pump_available=1.0,
        junction_available=[1.0] * len(binding.program.membrane_ids),
        boundary_voltage_V=[0.0] * 4,
    )
    expected = native.evaluate(
        setters.record(binding.program),
        source_state,
        0.4,
        spec.model.temperature_K,
    )
    assert (
        float(caught.value.trial["source_values"].state.temperature_K) == expected["temperature_K"]
    )
    evidence(
        "nonpositive-" + str(amplitude),
        dict(
            native=expected,
            raw_temperature_K=float(caught.value.trial["source_values"].state.temperature_K),
            physical_admission=False,
        ),
    )


def test_inventory_retains_matching_store_and_pool_owners_and_original_T_restriction():
    spec, *_ = setup("fuel")
    inventory = temperature.inventory(spec)
    assert inventory["changed_temperature_supported"] is False
    assert set(inventory["owners"]["stores"]) == set(inventory["owners"]["cells"])
    assert len(inventory["owners"]["fuel_pools"]) == len(inventory["owners"]["cells"])
    assert any("er_temperature" in row["fields"] for row in inventory["roles"])
    assert any("energy_delta_g0_J_mol" in row["fields"] for row in inventory["roles"])
    assert inventory["heat_capacity_defined"] is False


def test_forged_active_source_temperature_cannot_become_a_new_held_domain():
    spec, _, _, _, _, binding, _ = setup("ionic")
    changed = replace(spec, model=replace(spec.model, temperature_K=310.0))
    with pytest.raises(ValueError, match="298.15"):
        temperature.bind(
            changed,
            binding.program,
            owners=dict(binding.owners),
            provenance="Resealed attempt to bypass the source model domain",
        )
