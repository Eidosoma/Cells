"""Physical held clamps, independent full rates and explicit transition limits."""

import json
import os
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.core import physiology_boundary_voltage as voltage
from cells.core import physiology_random_streams as streams
from cells.core.errors import NumericalError
from cells.core.runner import validate_checkpoint
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, digest, parse_spec
from cells.core.state import Checkpoint
from cells.models import physiology_boundary_voltage_view as view
from cells.numerics.fixed_step import rk4_step
from cells.processes import betse_global_controls as setters
from tests.unit.test_physiology_permeability_view import KINDS, exact_tree, readouts
from tests.unit.test_physiology_tissue_binding import definition
from validation.perturbations import global_controls_native as native
from validation.tissue import open_calcium_fixtures as open_fixtures
from validation.tissue import physiology_boundary_voltage_reference as reference

SIDES = ("top", "bottom", "left", "right")


def plain(value):
    return {key: np.asarray(array).tolist() for key, array in value._asdict().items()}


def evidence(name, record, arrays=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(directory) / "boundary-voltage"
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / (name + ".json")).open("x") as handle:
            json.dump(
                record,
                handle,
                indent=2,
                sort_keys=True,
                allow_nan=False,
                default=lambda value: np.asarray(value).tolist(),
            )
            handle.write("\n")
        if arrays is not None:
            np.savez_compressed(folder / (name + ".npz"), **arrays)


def fixture(kind="passive", *, padded=True, positive="top", negative="bottom", empty=False):
    if kind in ("calcium", "fuel"):
        raw = open_fixtures.definition(
            "energy" if kind == "fuel" else "calcium",
            "all" if padded else "permuted",
            padded=padded,
            depleted=kind == "fuel",
        )
    else:
        raw = definition(kind, padded=padded, reorder=not padded)
    model = raw["model"].get("ionic", raw["model"])
    for row in model["extracellular"]:
        row["reservoir"] = row["id"] != "outside_4"
        row["boundary_potential_V"] = {
            "outside_0": 0.001,
            "outside_1": -0.002,
            "outside_2": 0.0005,
            "outside_3": -0.00075,
            "outside_4": 0.0,
        }[row["id"]]
    model["closure"]["gauge_reference"] = None
    spec = parse_spec(raw)
    program = setters.bind(
        membrane_ids=tuple(row.id for row in spec.model.membranes),
        events=()
        if empty
        else (
            setters.Event(
                "voltage",
                0.2,
                1.2,
                0.3,
                amplitude=0.007,
                positive_boundary=positive,
                negative_boundary=negative,
            ),
        ),
        provenance="Synthetic four-side native voltage program; no biological calibration",
    )
    mapping = dict(
        zip(SIDES, (("outside_0",), ("outside_1",), ("outside_2",), ("outside_3",)), strict=True)
    )
    binding = voltage.bind(
        spec,
        program,
        boundary_reservoir_ids=mapping,
        provenance="Explicit synthetic side labels on actual reservoir owners",
    )
    implementation = view.IMPLEMENTATIONS[type(spec.model)]
    state, layout = implementation.initial_values(spec)
    table = control_values(spec, [0.0])
    held = type(table)(*(array[0] * 0.67 for array in table))
    return spec, implementation, state, layout, held, binding, voltage.initial_state(spec, binding)


def fingerprints(spec, state, layout, control, boundary_state):
    return (
        spec.fingerprint,
        tuple(
            (a.dtype.str, a.shape, a.tobytes(), a.flags.writeable)
            for a in (*state, *layout, *control)
        ),
        boundary_state.boundary_voltage_V.tobytes(),
    )


def evaluate(case, *, time=0.4, enabled=True, step=None):
    spec, _, state, layout, held, binding, current = case
    return view.evaluate(
        spec,
        state,
        layout,
        held,
        binding,
        current,
        time_s=time,
        events_enabled=enabled,
        step_s=spec.execution.dt / 16 if step is None else step,
    )


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("padded", (False, True))
def test_complete_initial_and_evolved_held_rates_match_named_owner_reference(kind, padded):
    case = fixture(kind, padded=padded)
    spec, implementation, state, layout, held, binding, current = case
    saved = voltage.record(binding)
    assert voltage.restore(json.loads(json.dumps(saved)), spec) == binding
    for stage, time in enumerate((0.4, 1.5)):
        before = fingerprints(spec, state, layout, held, current)
        actual = evaluate((spec, implementation, state, layout, held, binding, current), time=time)
        inputs = dict(
            raw=spec.to_dict(),
            fields=plain(state),
            binding_record=saved,
            boundary_state=plain(current),
            held_control=plain(held),
            time_s=time,
            events_enabled=True,
        )
        context, target, phi, proof = reference.evaluate(**inputs)
        oracle = reference.ORACLES[spec.to_dict()["model"]["id"]]
        packed = oracle.flatten(context, actual.derivative._asdict())
        atol = oracle.flatten(
            context,
            {
                key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
                for key, shape in context["shapes"].items()
            },
        )
        budget = atol + 3e-10 * np.abs(target)
        error = float(np.max(abs(packed - target) / budget, initial=0))
        runtime = actual.runtime_layout
        potential = np.r_[
            actual.field.potential_V[: runtime.active.size][runtime.active],
            actual.field.potential_V[runtime.active.size :][runtime.outside_active],
        ]
        phi_budget = 3e-13 + 3e-10 * np.abs(phi)
        phi_error = float(np.max(abs(potential - phi) / phi_budget, initial=0))
        change_error = 0.0
        for key, expected in proof["capacitor_change"].items():
            value = np.asarray(actual.capacitor_change[key])
            target_value = np.asarray(expected)
            if key == "electrode_charge_change_C":
                value = value[runtime.outside_active]
                absolute = 3e-25
            elif key == "membrane_voltage_change_V":
                value = value[runtime.membrane_active]
                absolute = 3e-13
            else:
                absolute = 3e-14
            change_error = max(
                change_error,
                float(
                    np.max(
                        abs(value - target_value) / (absolute + 3e-10 * abs(target_value)),
                        initial=0,
                    )
                ),
            )
        source_state = dict(
            temperature_K=spec.model.temperature_K,
            junction_available=[1.0] * len(binding.program.membrane_ids),
            pump_available=1.0,
            **plain(current),
        )
        source = native.evaluate(
            setters.record(binding.program),
            source_state,
            time,
            spec.model.temperature_K,
        )
        expected, derivative = readouts(implementation, state, held, runtime)
        exact_tree(actual.readouts, expected)
        exact_tree(actual.derivative, derivative)
        for name in layout._fields:
            if name != "boundary_V":
                np.testing.assert_array_equal(
                    getattr(runtime, name), getattr(layout, name), strict=True
                )
        assert fingerprints(spec, state, layout, held, current) == before
        assert len(context["shapes"]) == len(state)
        evidence(
            f"stage-{kind}-{padded}-{stage}",
            dict(
                inputs=inputs,
                reference=proof,
                native=source,
                native_source_sha256=native.PINNED,
                max_rate_error_fraction=error,
                max_potential_error_fraction=phi_error,
                max_capacitor_error_fraction=change_error,
                stage_energy_residual_pJ_s=float(actual.field.energy_balance_pJ_s),
                passive_fraction=actual.admission["passive_fraction"],
                fuel_fraction=actual.admission["fuel_fraction"],
                fields=len(state),
                accepted_stepping=False,
                biological_cases=0,
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
        np.testing.assert_array_equal(
            actual.preparation.boundary_state.boundary_voltage_V, source["boundary_voltage_V"]
        )
        assert max(error, phi_error, change_error) <= 1
        assert abs(float(actual.field.energy_balance_pJ_s)) <= 1e-10
        assert abs(actual.capacitor_change["conditional_work_residual_pJ"]) <= 3e-14
        assert actual.admission["accepted_stepping"] is False
        if stage == 0:
            # Prepare a source-valid evolved parent under its ORIGINAL held clamps.
            # This is not an integration under the voltage intervention.
            state = rk4_step(
                lambda y, u, p, a: implementation.rhs(y, u, p, a, xp=np),
                state,
                spec.execution.dt / 16,
                held,
                layout,
                layout.active,
            )
            implementation.check_values(state, spec)


@pytest.mark.parametrize("kind", KINDS)
def test_disabled_and_empty_program_are_exact_original_readouts_with_no_draw(kind, monkeypatch):
    case = fixture(kind)
    spec, implementation, state, layout, held, binding, current = case

    def forbidden(*args, **kwargs):
        pytest.fail("A held boundary-voltage view sampled a random stream")

    monkeypatch.setattr(streams, "draw", forbidden)
    actual = evaluate(case, enabled=False)
    expected, derivative = readouts(implementation, state, held, layout)
    exact_tree(actual.readouts, expected)
    exact_tree(actual.derivative, derivative)
    exact_tree(actual.runtime_layout, layout)
    for key, value in actual.capacitor_change.items():
        if key != "scope":
            np.testing.assert_array_equal(value, np.zeros_like(value))
    empty = setters.bind(
        membrane_ids=binding.program.membrane_ids,
        events=(),
        provenance="Explicit empty setters",
    )
    empty_binding = voltage.bind(
        spec,
        empty,
        boundary_reservoir_ids=dict(binding.boundary_reservoir_ids),
        provenance=binding.provenance,
    )
    again = evaluate((*case[:5], empty_binding, current))
    exact_tree(again.readouts, expected)
    assert all(not array.flags.writeable for array in actual.runtime_layout)
    assert all(not array.flags.writeable for array in actual.derivative)
    with pytest.raises(TypeError):
        actual.admission["accepted_stepping"] = True


@pytest.mark.parametrize("positive", SIDES)
@pytest.mark.parametrize("negative", SIDES)
def test_native_all_side_pairs_preserve_ordered_same_side_negative_write(positive, negative):
    spec, _, _, _, _, binding, current = fixture(positive=positive, negative=negative)
    actual = voltage.prepare(spec, binding, current, time_s=0.4, events_enabled=True)
    initial = dict(
        temperature_K=spec.model.temperature_K,
        junction_available=[1.0] * len(binding.program.membrane_ids),
        pump_available=1.0,
        **plain(current),
    )
    expected = native.evaluate(
        setters.record(binding.program), initial, 0.4, spec.model.temperature_K
    )
    np.testing.assert_array_equal(
        actual.boundary_state.boundary_voltage_V, expected["boundary_voltage_V"]
    )
    for index, (_, owners) in enumerate(binding.boundary_reservoir_ids):
        for owner in owners:
            j = [row.id for row in spec.model.extracellular].index(owner)
            assert actual.boundary_V[j] == expected["boundary_voltage_V"][index]
    evidence(
        f"native-{positive}-{negative}",
        dict(
            program=setters.record(binding.program),
            initial=initial,
            native=expected,
            actual=plain(actual.boundary_state),
            time_s=0.4,
            native_source_sha256=native.PINNED,
        ),
    )


def test_shared_corner_conflict_retains_raw_source_proposal_and_parent():
    spec, _, state, layout, held, binding, current = fixture()
    mapping = dict(binding.boundary_reservoir_ids)
    mapping["left"] = ("outside_0", "outside_2")
    binding = voltage.bind(
        spec, binding.program, boundary_reservoir_ids=mapping, provenance="Corner"
    )
    # Explicit source memory keeps the two initial sides consistent at this corner.
    memory = current.boundary_voltage_V.copy()
    memory[2] = memory[0]
    current = voltage.BoundaryState(memory)
    before = fingerprints(spec, state, layout, held, current)
    with pytest.raises(voltage.BoundaryVoltageRejected, match="corner") as caught:
        voltage.prepare(spec, binding, current, time_s=0.4, events_enabled=True)
    trial = caught.value.trial
    assert trial["conflicting_owners"] == (("outside_0", "top", "left"),)
    assert trial["source_values"].state.boundary_voltage_V[0] != memory[0]
    assert not trial["boundary_V"].flags.writeable
    assert fingerprints(spec, state, layout, held, current) == before
    evidence(
        "refused-corner",
        dict(
            binding=voltage.record(binding),
            parent=plain(current),
            proposed_native=plain(
                voltage.BoundaryState(trial["source_values"].state.boundary_voltage_V)
            ),
            proposed_boundary=trial["boundary_V"],
            conflicts=trial["conflicting_owners"],
            parent_unchanged=True,
            accepted_stepping=False,
        ),
    )


def test_equal_corner_and_multiple_owner_sides_apply_once_by_actual_ID():
    spec, _, _, _, _, binding, current = fixture(empty=True)
    mapping = dict(binding.boundary_reservoir_ids)
    mapping["top"] = ("outside_0", "outside_2")
    mapping["left"] = ("outside_0",)
    binding = voltage.bind(
        spec, binding.program, boundary_reservoir_ids=mapping, provenance="Equal corner"
    )
    memory = np.asarray([0.003, -0.002, 0.003, -0.00075])
    current = voltage.BoundaryState(memory)
    actual = voltage.prepare(spec, binding, current, time_s=0.4, events_enabled=True)
    for i, row in enumerate(spec.model.extracellular):
        target = 0.003 if row.id in ("outside_0", "outside_2") else row.boundary_potential_V
        assert actual.boundary_V[i] == target


@pytest.mark.parametrize(
    "bad",
    (
        "finite",
        "gauge",
        "unknown",
        "duplicate",
        "missing",
        "extra",
        "empty-driven",
        "nonvoltage",
        "membrane-order",
    ),
)
def test_owner_and_program_preflight_refuses_unphysical_or_ambiguous_declarations(bad):
    spec, _, _, _, _, binding, _ = fixture()
    program = binding.program
    mapping = dict(binding.boundary_reservoir_ids)
    if bad == "finite":
        mapping["top"] = ("outside_4",)
    elif bad == "gauge":
        spec = parse_spec(definition("passive"))
        mapping["top"] = ("outside_4",)
    elif bad == "unknown":
        mapping["top"] = ("padding-or-guessed-owner",)
    elif bad == "duplicate":
        mapping["top"] = ("outside_0", "outside_0")
    elif bad == "missing":
        mapping.pop("right")
    elif bad == "extra":
        mapping["centre"] = ()
    elif bad == "empty-driven":
        mapping["top"] = ()
    elif bad == "nonvoltage":
        program = setters.bind(
            membrane_ids=program.membrane_ids,
            events=(setters.Event("temperature", 0, 1, 1, amplitude=1),),
            provenance="Unrelated thermal setter",
        )
    else:
        program = setters.bind(
            membrane_ids=program.membrane_ids[::-1],
            events=program.events,
            provenance=program.provenance,
        )
    with pytest.raises(ValueError):
        voltage.bind(
            spec, program, boundary_reservoir_ids=mapping, provenance="Invalid declaration"
        )


def test_closed_gauge_identity_allows_no_electrode_reinterpretation():
    spec = parse_spec(definition("passive"))
    implementation = view.ordinary.passive
    state, layout = implementation.initial_values(spec)
    program = setters.bind(
        membrane_ids=tuple(row.id for row in spec.model.membranes),
        events=(),
        provenance="Closed no-event",
    )
    binding = voltage.bind(
        spec,
        program,
        boundary_reservoir_ids=dict.fromkeys(SIDES, ()),
        provenance="No electrodes",
    )
    table = control_values(spec, [0.0])
    held = type(table)(*(array[0] for array in table))
    current = voltage.initial_state(spec, binding)
    actual = evaluate((spec, implementation, state, layout, held, binding, current))
    expected, derivative = readouts(implementation, state, held, layout)
    exact_tree(actual.readouts, expected)
    exact_tree(actual.derivative, derivative)


@pytest.mark.parametrize("kind", ("calcium", "fuel"))
def test_finite_only_calcium_fuel_keep_original_gauge_and_refuse_clamp_owners(kind):
    spec = parse_spec(definition(kind))
    implementation = view.IMPLEMENTATIONS[type(spec.model)]
    state, layout = implementation.initial_values(spec)
    program = setters.bind(
        membrane_ids=tuple(row.id for row in spec.model.membranes),
        events=(),
        provenance="Finite-only family has no physical voltage electrodes",
    )
    mapping = dict.fromkeys(SIDES, ())
    binding = voltage.bind(
        spec,
        program,
        boundary_reservoir_ids=mapping,
        provenance="No electrode substitution",
    )
    table = control_values(spec, [0.0])
    held = type(table)(*(array[0] for array in table))
    current = voltage.initial_state(spec, binding)
    actual = evaluate((spec, implementation, state, layout, held, binding, current))
    expected, derivative = readouts(implementation, state, held, layout)
    exact_tree(actual.readouts, expected)
    exact_tree(actual.derivative, derivative)
    mapping["top"] = (spec.model.gauge_reference,)
    with pytest.raises(ValueError, match="gauges"):
        voltage.bind(
            spec, program, boundary_reservoir_ids=mapping, provenance="Invalid gauge clamp"
        )
    evidence(
        "finite-refusal-" + kind,
        dict(
            model_id=spec.to_dict()["model"]["id"],
            gauge_owner=spec.model.gauge_reference,
            no_event_identity=True,
            reservoir_reinterpretation_refused=True,
            changed_clamp_coverage=False,
        ),
    )


@pytest.mark.parametrize("corruption", ("identity", "source", "owner", "program", "extra", "order"))
def test_complete_binding_restore_refuses_stale_corrupt_or_resealed_records(corruption):
    spec, _, _, _, _, binding, _ = fixture()
    saved = deepcopy(voltage.record(binding))
    if corruption == "identity":
        saved["identity"] = "0" * 64
    elif corruption == "source":
        saved["source_definition_sha256"] = "0" * 64
    elif corruption == "owner":
        saved["boundary_reservoir_ids"][0][1] = ["outside_4"]
    elif corruption == "program":
        saved["program"]["events"][0]["amplitude"] *= 2
    elif corruption == "extra":
        saved["invented"] = True
    else:
        saved["boundary_reservoir_ids"].reverse()
    if corruption != "identity":
        saved["identity"] = digest({k: v for k, v in saved.items() if k != "identity"})
    with pytest.raises(ValueError):
        voltage.restore(saved, spec)


@pytest.mark.parametrize("kind", KINDS)
def test_original_anchors_and_history_are_checked_before_changed_voltage_readouts(kind):
    case = fixture(kind)
    spec, implementation, state, layout, held, binding, current = case
    anchor = layout.initial_membrane_voltage_V.copy()
    anchor[0] += 1e-4
    with pytest.raises(ValueError, match="anchor|parameter"):
        evaluate(
            (
                spec,
                implementation,
                state,
                layout._replace(initial_membrane_voltage_V=anchor),
                held,
                binding,
                current,
            )
        )
    damaged = state.reservoir_work_pJ.copy()
    damaged[0] = 1.0
    with pytest.raises((NumericalError, ConfigError)):
        evaluate(
            (
                spec,
                implementation,
                state._replace(reservoir_work_pJ=damaged),
                layout,
                held,
                binding,
                current,
            )
        )
    actual = evaluate(case)
    checkpoint = Checkpoint(state, actual.runtime_layout, 0.0, 0, 0)
    with pytest.raises(ConfigError, match="layout"):
        validate_checkpoint(spec, checkpoint)


@pytest.mark.parametrize(
    "value",
    (
        np.zeros(3),
        np.zeros(4, dtype=np.float32),
        np.full(4, np.nan),
        np.full(4, np.inf),
        np.zeros((1, 4)),
    ),
)
def test_invalid_native_boundary_memory_refuses_before_sampling(value):
    spec, _, _, _, _, binding, _ = fixture()
    with pytest.raises(ValueError, match="float64"):
        voltage.prepare(
            spec, binding, voltage.BoundaryState(value), time_s=0.4, events_enabled=True
        )


@pytest.mark.parametrize("step", (0.0, -1.0, True, float("nan"), float("inf"), 1.0))
def test_invalid_or_excessive_proposed_step_refuses(step):
    with pytest.raises(ValueError):
        evaluate(fixture(), step=step)


@pytest.mark.parametrize("kind", KINDS)
def test_unphysical_field_proposal_retains_raw_diagnostics_and_unchanged_parent(kind):
    case = fixture(kind)
    spec, implementation, state, layout, held, binding, current = case
    event = replace(binding.program.events[0], amplitude=1e4)
    program = setters.bind(
        membrane_ids=binding.program.membrane_ids,
        events=(event,),
        provenance="Extreme refused voltage",
    )
    binding = voltage.bind(
        spec,
        program,
        boundary_reservoir_ids=dict(binding.boundary_reservoir_ids),
        provenance=binding.provenance,
    )
    before = fingerprints(spec, state, layout, held, current)
    with np.errstate(over="ignore", invalid="ignore", under="ignore", divide="ignore"):
        with pytest.raises(voltage.BoundaryVoltageRejected) as caught:
            evaluate((spec, implementation, state, layout, held, binding, current))
    assert fingerprints(spec, state, layout, held, current) == before
    trial = caught.value.trial
    assert trial["preparation"].boundary_state.boundary_voltage_V[0] > 1000
    raw_arrays = {"parent_" + key: value for key, value in state._asdict().items()}
    raw_arrays.update(
        {"trial_" + key: value for key, value in trial.get("derivative", state)._asdict().items()}
    )
    if "readouts" in trial:
        raw = trial["readouts"]
        field = raw.field if hasattr(raw, "field") else raw
        raw_arrays.update(
            {"field_" + key: value for key, value in field._asdict().items() if key != "rates"}
        )
    evidence(
        "refused-field-" + kind,
        dict(
            binding=voltage.record(binding),
            reason=str(caught.value),
            parent_unchanged=True,
            trial_native=plain(trial["preparation"].boundary_state),
            accepted_stepping=False,
        ),
        raw_arrays,
    )


@pytest.mark.parametrize("kind", KINDS)
def test_frozen_capacitive_work_is_separate_from_held_endpoint_power_and_no_step_is_accepted(kind):
    case = fixture(kind)
    spec, _, state, layout, held, _, current = case
    before = fingerprints(spec, state, layout, held, current)
    actual = evaluate(case)
    change = actual.capacitor_change
    dq = change["electrode_charge_change_C"]
    assert np.max(abs(dq)) > 1e-15
    # Fixed final-V work cannot replace ramp work or repair historical ledgers.
    final_voltage_work = 1e12 * np.sum(actual.runtime_layout.boundary_V * dq)
    difference = final_voltage_work - change["capacitor_energy_change_pJ"]
    assert abs(difference) > 1e-8
    assert abs(change["conditional_work_residual_pJ"]) <= 3e-14
    assert actual.admission["accepted_stepping"] is False
    assert fingerprints(spec, state, layout, held, current) == before
    evidence(
        "transition-limit-" + kind,
        dict(
            capacitor_change={k: v for k, v in change.items() if k != "scope"},
            fixed_endpoint_voltage_work_pJ=final_voltage_work,
            endpoint_work_difference_pJ=difference,
            parent_unchanged=True,
            accepted_stepping=False,
            adopted_transition_law=False,
            invented_heat=False,
        ),
    )
