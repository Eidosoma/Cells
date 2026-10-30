"""Prepared combined-view qualification; execution waits for Chief's CPU release."""

import json
import os
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import jax
import numpy as np
import pytest

from cells import io as numeric_io
from cells.core import physiology_active_temperature as active_contract
from cells.core import physiology_boundary_voltage as boundary
from cells.core import physiology_global_control_view as controls
from cells.core import physiology_random_streams as streams
from cells.core import physiology_temperature as thermal
from cells.core import physiology_tissue_binding as units
from cells.core.grid import checked_grid
from cells.core.runner import validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, digest, parse_spec
from cells.core.state import Checkpoint
from cells.models import physiology_active_temperature_view as active_view
from cells.models import physiology_block_control_view as blocks
from cells.models import physiology_boundary_voltage_view as voltage_view
from cells.models import physiology_global_control_view as view
from cells.models import physiology_temperature_view as thermal_view
from cells.numerics.fixed_step import rk4_step
from cells.processes import betse_global_controls as setters
from tests.unit.test_physiology_active_temperature import setup as active_setup
from tests.unit.test_physiology_boundary_voltage import fixture as voltage_fixture
from tests.unit.test_physiology_permeability_view import exact_tree
from tests.unit.test_physiology_tissue_binding import arguments
from validation.perturbations import global_controls_native as native
from validation.tissue import physiology_global_control_view_reference as reference

KINDS = ("passive", "ionic", "calcium", "fuel", "open-calcium", "open-fuel")
VOLTAGE_KINDS = ("passive", "ionic", "open-calcium", "open-fuel")


def fixture(
    kind="ionic", *, padded=True, only=None, force_voltage=False, asymmetric=False, same_side=False
):
    if kind == "passive":
        spec = voltage_fixture("passive", padded=padded)[0]
    else:
        spec = active_setup(kind, padded=padded)[0]
        if kind == "ionic":
            raw = spec.to_dict()
            ion = raw["model"]
            initial = dict(
                zip(
                    ("outside_0", "outside_1", "outside_2", "outside_3"),
                    (0.001, -0.002, 0.0005, -0.00075),
                    strict=True,
                )
            )
            for row in ion["extracellular"]:
                row["reservoir"] = row["id"] in initial
                row["boundary_potential_V"] = initial.get(row["id"], 0.0)
            ion["closure"]["gauge_reference"] = None
            spec = parse_spec(raw)
    implementation = view.IMPLEMENTATIONS[type(spec.model)]
    state, layout = implementation.initial_values(spec)
    packet = control_values(spec, [0.0])
    base = type(packet)(*(value[0] * 0.71 for value in packet))
    checkpoint = Checkpoint(state, layout, 0.0, 0, 0)
    available = {
        cell.id: [mem.id for mem in spec.model.membranes if mem.inside == cell.id]
        for cell in spec.model.cells
    }
    pairs = {}
    for edge in spec.model.junctions:
        pairs[edge.id] = (available[edge.sender].pop(0), available[edge.receiver].pop(0))
    targets = tuple(name for pair in pairs.values() for name in pair)
    if asymmetric:
        targets = targets[:1]
    events = [
        setters.Event("temperature", 0.2, 1.2, 0.3, amplitude=0.025),
        setters.Event("junction_block", 0.6, 1.1, 0.35, target_ids=targets),
    ]
    if kind != "passive":
        events.append(setters.Event("pump_block", 0.7, 1.05, 0.4))
    has_voltage = kind in VOLTAGE_KINDS or force_voltage
    sides = {name: () for name in setters.SIDES}
    if has_voltage:
        if kind in VOLTAGE_KINDS:
            sides = {side: ("outside_" + str(i),) for i, side in enumerate(setters.SIDES)}
        events.append(
            setters.Event(
                "voltage",
                0.3,
                1.4,
                0.25,
                amplitude=0.0015,
                positive_boundary="top",
                negative_boundary="top" if same_side else "bottom",
            )
        )
    if only is not None:
        events = [event for event in events if event.kind in only]
    # Deliberately reverse declarations: the source establishes canonical order.
    program = setters.bind(
        membrane_ids=tuple(row.id for row in spec.model.membranes),
        events=tuple(events[::-1]),
        provenance="Synthetic simultaneous source controls; no thermal/voltage transition",
    )
    binding = controls.bind(
        spec,
        program,
        owners={name: ids[::-1] for name, ids in thermal.actual_owners(spec).items()},
        boundary_reservoir_ids=sides,
        junction_membrane_ids=pairs,
        policy=controls.POLICY,
        provenance="Declared actual thermostat, reservoir sides and exclusive contacts",
    )
    memory = controls.initial_memory(spec, binding)
    return spec, implementation, checkpoint, base, binding, memory


def plain(value):
    return {key: np.asarray(array).tolist() for key, array in value._asdict().items()}


def evidence(name, record, columns=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(directory) / "global-control-view"
        root.mkdir(parents=True, exist_ok=True)
        with (root / (name + ".json")).open("x") as handle:
            json.dump(
                record,
                handle,
                indent=2,
                allow_nan=False,
                default=lambda value: np.asarray(value).tolist(),
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if columns is not None:
            np.savez_compressed(root / (name + ".npz"), **columns)


def evaluate(case, *, event_time_s=0.4, enabled=True):
    spec, _, checkpoint, base, binding, memory = case
    return view.evaluate(
        spec,
        checkpoint,
        base,
        binding,
        memory,
        event_time_s=event_time_s,
        events_enabled=enabled,
        step_s=spec.execution.dt / 16,
    )


def qualify(case, name, *, event_time_s=0.4, enabled=True):
    spec, _, checkpoint, base, binding, memory = case
    before = (
        spec.fingerprint,
        tuple(
            (np.asarray(value).dtype.str, np.asarray(value).shape, np.asarray(value).tobytes())
            for value in (*checkpoint.state, *checkpoint.layout, *base, *memory)
        ),
        checkpoint.time,
        checkpoint.step_index,
        checkpoint.event_index,
    )
    actual = evaluate(case, event_time_s=event_time_s, enabled=enabled)
    inputs = dict(
        raw=spec.to_dict(),
        fields=plain(checkpoint.state),
        binding_record=controls.record(binding),
        memory=plain(memory),
        base_control=plain(base),
        event_time_s=event_time_s,
        events_enabled=enabled,
        physical_clock=dict(
            time=checkpoint.time,
            step_index=checkpoint.step_index,
            event_index=checkpoint.event_index,
        ),
    )
    context, target, phi, proof = reference.evaluate(**inputs)
    rate = reference.flatten(context, actual.derivative._asdict())
    absolute = reference.flatten(
        context,
        {
            key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
            for key, shape in context["shapes"].items()
        },
    )
    budget = absolute + 3e-10 * abs(target)
    rate_error = float(np.max(abs(rate - target) / budget, initial=0))
    p, field = actual.runtime_layout, actual.field
    n, o = (
        context["shapes"]["amount_increment"][-1],
        context["shapes"]["extracellular_amount_increment"][-1],
    )
    potential = np.r_[field.potential_V[:n], field.potential_V[p.active.size : p.active.size + o]]
    phi_budget = 3e-13 + 3e-10 * abs(phi)
    phi_error = float(np.max(abs(potential - phi) / phi_budget, initial=0))
    field_error, saved = 0.0, {}
    for key, column in proof["physical_field_columns"].items():
        value = field
        for part in key.split("."):
            value = getattr(value, part)
        value, expected = np.asarray(value), np.asarray(column["value"])
        if key in ("capacitor_node_charge_C", "charge_residual_C"):
            value = np.r_[value[:n], value[p.active.size : p.active.size + o]]
        elif expected.ndim:
            value = value[tuple(slice(0, size) for size in expected.shape)]
        saved["field__" + key.replace(".", "__")] = value
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
            rate_error_fraction=rate_error,
            potential_error_fraction=phi_error,
            physical_field_error_fraction=field_error,
            stage_energy_residual_pJ_s=float(field.energy_balance_pJ_s),
            accepted_stepping=False,
        ),
        dict(
            actual_rate=rate,
            expected_rate=target,
            rate_budget=budget,
            actual_phi=potential,
            expected_phi=phi,
            phi_budget=phi_budget,
            **saved,
        ),
    )
    assert max(rate_error, phi_error, field_error) <= 1
    assert abs(float(field.energy_balance_pJ_s)) <= 1e-10
    if "physical_energy_balance_pJ_s" in proof:
        assert abs(proof["physical_energy_balance_pJ_s"]) <= 1e-10
    assert actual.original_clock == (checkpoint.time, checkpoint.step_index, checkpoint.event_index)
    assert actual.admission["native_event_time_s"] == event_time_s
    assert not actual.admission["accepted_stepping"]
    assert actual.assumptions["accepted_heat_pJ"] is None
    allowed = active_view.PROJECTED_FIELDS | {"boundary_V"}
    for key in checkpoint.layout._fields:
        if key not in allowed:
            np.testing.assert_array_equal(
                getattr(p, key), np.asarray(getattr(checkpoint.layout, key)), strict=True
            )
    after = (
        spec.fingerprint,
        tuple(
            (np.asarray(value).dtype.str, np.asarray(value).shape, np.asarray(value).tobytes())
            for value in (*checkpoint.state, *checkpoint.layout, *base, *memory)
        ),
        checkpoint.time,
        checkpoint.step_index,
        checkpoint.event_index,
    )
    assert before == after
    return actual


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("padded", (False, True))
def test_simultaneous_complete_six_family_initial_and_original_evolved_views(kind, padded):
    case = fixture(kind, padded=padded)
    spec, model, checkpoint, base, binding, memory = case
    assert controls.restore(json.loads(json.dumps(controls.record(binding))), spec) == binding
    assert [event.kind for event in binding.program.events] == [
        kind for kind in controls.ORDER if any(row.kind == kind for row in binding.program.events)
    ]
    for stage in range(2):
        for time in (0.4, 0.8):
            qualify(
                (spec, model, checkpoint, base, binding, memory),
                f"simultaneous-{kind}-{padded}-{stage}-{time}",
                event_time_s=time,
            )
        if stage == 0:
            grid = checked_grid(spec)
            control_table = control_values(spec, [0.0])
            scheduled = type(control_table)(*(value[0] for value in control_table))
            state = rk4_step(
                lambda y, u, p, a: model.rhs(y, u, p, a, xp=np),
                checkpoint.state,
                float(grid[1]),
                scheduled,
                checkpoint.layout,
                checkpoint.layout.active,
            )
            checkpoint = Checkpoint(
                state, checkpoint.layout, float(grid[1]), 1, event_index(spec, float(grid[1]))
            )
            validate_checkpoint(spec, checkpoint)


SINGLE = [
    (kind, control)
    for kind in KINDS
    for control in controls.ORDER
    if not (kind == "passive" and control == "pump_block")
    and not (kind not in VOLTAGE_KINDS and control == "voltage")
]


@pytest.mark.parametrize("kind,control_kind", SINGLE)
def test_single_control_reductions_match_independent_full_physics_and_existing_views(
    kind, control_kind
):
    case = fixture(kind, only=(control_kind,))
    spec, model, checkpoint, base, binding, memory = case
    actual = qualify(case, "single-" + kind + "-" + control_kind)
    if control_kind == "temperature":
        if kind == "passive":
            thermal_binding = thermal.bind(
                spec, binding.program, owners=dict(binding.owners), provenance=binding.provenance
            )
            expected = thermal_view.evaluate(
                spec,
                checkpoint.state,
                checkpoint.layout,
                base,
                thermal_binding,
                thermal.TemperatureState(memory.temperature_K),
                time_s=0.4,
                events_enabled=True,
                step_s=spec.execution.dt / 16,
            )
        else:
            thermal_binding = active_contract.bind(
                spec,
                binding.program,
                owners=dict(binding.owners),
                policy=controls.POLICY,
                provenance=binding.provenance,
            )
            expected = active_view.evaluate(
                spec,
                checkpoint.state,
                checkpoint.layout,
                base,
                thermal_binding,
                active_contract.TemperatureMemory(memory.temperature_K),
                time_s=0.4,
                events_enabled=True,
                step_s=spec.execution.dt / 16,
            )
        exact_tree(actual.readouts, expected.readouts)
    elif control_kind == "voltage":
        vb = boundary.bind(
            spec,
            binding.program,
            boundary_reservoir_ids=dict(binding.boundary_reservoir_ids),
            provenance=binding.provenance,
        )
        expected = voltage_view.evaluate(
            spec,
            checkpoint.state,
            checkpoint.layout,
            base,
            vb,
            boundary.BoundaryState(memory.boundary_voltage_V),
            time_s=0.4,
            events_enabled=True,
            step_s=spec.execution.dt / 16,
        )
        exact_tree(actual.readouts, expected.readouts)
    elif kind in ("passive", "ionic", "calcium", "fuel"):
        tissue = units.bind_tissue(spec, **arguments(spec))
        block_binding = blocks.bind(
            spec,
            tissue,
            binding.program,
            junction_membrane_ids={name: (a, b) for name, a, b in binding.junction_membranes},
            provenance=binding.provenance,
        )
        expected = blocks.prepare(
            spec,
            tissue,
            block_binding,
            blocks.BlockState(memory.junction_available, memory.pump_available),
            base,
            time_s=0.4,
            events_enabled=True,
        )
        exact_tree(actual.preparation.effective_control, expected.effective_control)
        values = (
            model.field_values(
                checkpoint.state, expected.effective_control, checkpoint.layout, xp=np
            )
            if kind == "passive"
            else model.readouts(
                checkpoint.state, expected.effective_control, checkpoint.layout, xp=np
            )
        )
        exact_tree(actual.readouts, values)


@pytest.mark.parametrize("kind", KINDS)
def test_disabled_and_empty_programs_are_exact_identity_without_rng_or_clock_updates(
    kind, monkeypatch
):
    case = fixture(kind)
    spec, model, checkpoint, base, binding, memory = case
    monkeypatch.setattr(
        streams, "draw", lambda *a, **k: pytest.fail("Global held view consumed a random stream")
    )
    actual = qualify(case, "disabled-" + kind, enabled=False, event_time_s=-12.0)
    expected = (
        model.field_values(checkpoint.state, base, checkpoint.layout, xp=np)
        if kind == "passive"
        else model.readouts(checkpoint.state, base, checkpoint.layout, xp=np)
    )
    exact_tree(actual.readouts, expected)
    empty = fixture(kind, only=())
    exact_tree(evaluate(empty).readouts, expected)


def test_combined_source_order_and_same_native_side_negative_write_match_pinned_native():
    case = fixture("ionic", same_side=True)
    spec, _, _, base, binding, memory = case
    actual = controls.prepare(spec, binding, memory, base, event_time_s=0.8, events_enabled=True)
    expected = native.evaluate(
        setters.record(binding.program), plain(memory), 0.8, spec.model.temperature_K
    )
    for key, value in actual.source_values.state._asdict().items():
        np.testing.assert_array_equal(value, expected[key])
    assert actual.source_values.state.boundary_voltage_V[0] < 0


@pytest.mark.parametrize("kind", ("calcium", "fuel"))
def test_finite_family_voltage_declarations_and_carried_unmapped_memory_refuse(kind):
    with pytest.raises(ValueError):
        fixture(kind, force_voltage=True)
    case = fixture(kind)
    spec, _, _, base, binding, memory = case
    changed = memory._replace(boundary_voltage_V=np.asarray([0.01, 0.0, 0.0, 0.0]))
    with pytest.raises(controls.GlobalControlRejected) as failure:
        controls.prepare(spec, binding, changed, base, event_time_s=0.4, events_enabled=False)
    np.testing.assert_array_equal(
        failure.value.trial["source_values"].state.boundary_voltage_V, changed.boundary_voltage_V
    )


@pytest.mark.parametrize("kind", ("ionic", "fuel", "open-fuel"))
@pytest.mark.parametrize("amplitude", (-4.0, 1e308))
def test_rejected_raw_temperature_proposals_remain_available_without_parent_mutation(
    kind, amplitude
):
    case = fixture(kind, only=("temperature",))
    spec, model, checkpoint, base, binding, memory = case
    program = setters.bind(
        membrane_ids=binding.program.membrane_ids,
        events=(replace(binding.program.events[0], amplitude=amplitude),),
        provenance=binding.program.provenance,
    )
    changed = controls.bind(
        spec,
        program,
        owners=dict(binding.owners),
        boundary_reservoir_ids=dict(binding.boundary_reservoir_ids),
        junction_membrane_ids={name: (a, b) for name, a, b in binding.junction_membranes},
        policy=controls.POLICY,
        provenance=binding.provenance,
    )
    with pytest.raises(controls.GlobalControlRejected) as failure:
        evaluate((spec, model, checkpoint, base, changed, memory), event_time_s=0.8)
    proposed = failure.value.trial["source_values"].state
    assert proposed.temperature_K <= 0 or not np.isfinite(proposed.temperature_K)
    assert float(memory.temperature_K) == spec.model.temperature_K
    evidence(
        f"rejected-T-{kind}-{amplitude}",
        dict(kind="raw_rejected_source", raw_buffers_preserved=True),
        {key: np.asarray(value) for key, value in proposed._asdict().items()},
    )


def test_asymmetric_contacts_and_conflicting_corner_writes_retain_raw_setter_proposals():
    case = fixture("ionic", asymmetric=True)
    spec, _, _, base, binding, memory = case
    with pytest.raises(controls.GlobalControlRejected) as failure:
        controls.prepare(spec, binding, memory, base, event_time_s=0.8, events_enabled=True)
    assert failure.value.trial["conflicts"]
    regular = fixture("ionic")
    spec, _, _, base, binding, memory = regular
    sides = dict(binding.boundary_reservoir_ids)
    sides["bottom"] = sides["top"]
    corner = controls.bind(
        spec,
        binding.program,
        owners=dict(binding.owners),
        boundary_reservoir_ids=sides,
        junction_membrane_ids={name: (a, b) for name, a, b in binding.junction_membranes},
        policy=controls.POLICY,
        provenance=binding.provenance,
    )
    corner_memory = controls.initial_memory(spec, corner)
    with pytest.raises(controls.GlobalControlRejected) as failure:
        controls.prepare(spec, corner, corner_memory, base, event_time_s=0.8, events_enabled=True)
    assert (
        failure.value.trial["source_values"].state.boundary_voltage_V[0]
        != failure.value.trial["source_values"].state.boundary_voltage_V[1]
    )


@pytest.mark.parametrize(
    "field",
    (
        "policy",
        "source_order",
        "units",
        "baseline_policy",
        "clock_policy",
        "source_definition_sha256",
    ),
)
def test_resealed_source_order_policy_and_owner_claims_are_reconstructed(field):
    spec, _, _, _, binding, _ = fixture("ionic")
    saved = deepcopy(controls.record(binding))
    saved[field] = "unreviewed"
    saved["identity"] = digest({key: value for key, value in saved.items() if key != "identity"})
    with pytest.raises(ValueError):
        controls.restore(saved, spec)


def test_physical_checkpoint_clock_cannot_be_replaced_by_native_event_label():
    case = fixture("ionic")
    spec, model, checkpoint, base, binding, memory = case
    with pytest.raises(ConfigError):
        evaluate((spec, model, replace(checkpoint, time=0.4), base, binding, memory))
    actual = evaluate(case, event_time_s=0.8)
    assert actual.original_clock == (0.0, 0, 0)
    assert actual.preparation.event_time_s == 0.8


@pytest.mark.parametrize("kind", KINDS)
def test_ordinary_snapshot_device_arrays_are_normalized_with_exact_original_anchors(kind, tmp_path):
    case = fixture(kind)
    spec, model, checkpoint, base, binding, memory = case
    saved = numeric_io.write_snapshot(tmp_path / "original", spec, checkpoint)
    restored = numeric_io.load_snapshot(saved)
    assert all(
        isinstance(value, jax.Array)
        for value in (*restored.checkpoint.state, *restored.checkpoint.layout)
    )
    actual = qualify(
        (restored.spec, model, restored.checkpoint, base, binding, memory), "restored-" + kind
    )
    assert all(
        type(value) is np.ndarray and not value.flags.writeable for value in actual.runtime_layout
    )
