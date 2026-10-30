"""Complete physical rates with source blockers and explicit contact ownership."""

import json
import os
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.core import physiology_random_streams as streams
from cells.core import physiology_tissue_binding as units
from cells.core.schedule import control_values
from cells.core.specs import parse_spec
from cells.models import physiology_block_control_view as blocks
from cells.numerics.fixed_step import rk4_step
from cells.processes import betse_global_controls as setters
from tests.unit.test_physiology_permeability_view import (
    KINDS,
    case,
    exact_tree,
    fingerprints,
    readouts,
)
from tests.unit.test_physiology_tissue_binding import arguments, definition
from validation.perturbations import global_controls_native as native
from validation.tissue import physiology_block_control_reference as reference


def fixture(kind="passive", *, padded=True, enabled_program=True):
    spec, tissue, component, implementation, state, layout, control = case(kind, padded=padded)
    pairs = {
        edge.id: tuple(
            next(m.id for m in spec.model.membranes if m.inside == cell)
            for cell in (edge.sender, edge.receiver)
        )
        for edge in spec.model.junctions
    }
    targets = tuple(name for pair in pairs.values() for name in pair)
    events = [setters.Event("junction_block", 0.2, 1.2, 0.3, target_ids=targets)]
    if kind != "passive":
        events.append(setters.Event("pump_block", 0.25, 1.1, 0.4))
    program = setters.bind(
        membrane_ids=tissue.component.membrane_ids,
        events=events if enabled_program else (),
        provenance="Explicit paired contact blockers for numerical comparison",
    )
    binding = blocks.bind(
        spec,
        tissue,
        program,
        junction_membrane_ids=pairs,
        provenance="Synthetic named contact pairs, matched sender/receiver owners",
    )
    global_state = blocks.BlockState(np.ones(len(program.membrane_ids)), np.asarray(1.0))
    return spec, tissue, component, implementation, state, layout, control, binding, global_state


def plain(value):
    return {k: np.asarray(v).tolist() for k, v in value._asdict().items()}


def evidence(name, record, arrays=None):
    if path := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(path) / "block-control-view"
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / (name + ".json")).open("x") as stream:
            json.dump(
                record,
                stream,
                indent=2,
                sort_keys=True,
                allow_nan=False,
                default=lambda x: np.asarray(x).tolist(),
            )
            stream.write("\n")
        if arrays is not None:
            np.savez_compressed(folder / (name + ".npz"), **arrays)


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("padded", (False, True))
def test_complete_initial_and_evolved_rates_match_independent_control_and_physics(kind, padded):
    spec, tissue, component, implementation, state, layout, base, binding, global_state = fixture(
        kind, padded=padded
    )
    saved = blocks.record(binding)
    assert blocks.restore(json.loads(json.dumps(saved)), spec, tissue) == binding
    step = spec.execution.dt / 16
    for stage, time in enumerate((0.4, 1.5)):
        before = fingerprints(spec, state, layout, component)
        actual = blocks.evaluate(
            spec,
            state,
            layout,
            base,
            tissue,
            component,
            binding,
            global_state,
            time_s=time,
            events_enabled=True,
            step_s=step,
        )
        args = dict(
            raw=spec.to_dict(),
            fields=state._asdict(),
            binding_record=units.binding_record(tissue),
            current_diffusion_m2_s=component.diffusion.current_m2_s,
            block_binding=saved,
            block_state=plain(global_state),
            base_control=plain(base),
            time_s=time,
            events_enabled=True,
        )
        context, target, phi, proof = reference.evaluate(**args)
        oracle = reference.physical.ORACLES[spec.to_dict()["model"]["id"]]
        packed = oracle.flatten(context, actual.physical.derivative._asdict())
        atol = oracle.flatten(
            context,
            {
                k: np.full(s, 3e-23 if k.endswith("_C") else 3e-12)
                for k, s in context["shapes"].items()
            },
        )
        budget = atol + 3e-10 * np.abs(target)
        error = float(np.max(abs(packed - target) / budget, initial=0))
        runtime = actual.physical.runtime_layout
        voltage = actual.physical.field.potential_V
        potential = np.r_[
            voltage[: runtime.active.size][runtime.active],
            voltage[runtime.active.size :][runtime.outside_active],
        ]
        phi_budget = 3e-13 + 3e-10 * np.abs(phi)
        phi_error = float(np.max(abs(potential - phi) / phi_budget, initial=0))
        assert max(error, phi_error) <= 1
        source_state = dict(
            temperature_K=spec.model.temperature_K,
            boundary_voltage_V=[0.0] * 4,
            **plain(global_state),
        )
        source = native.evaluate(
            setters.record(binding.program), source_state, time, spec.model.temperature_K
        )
        for key, value in actual.preparation.block_state._asdict().items():
            np.testing.assert_array_equal(value, source[key])
        for name, values in actual.preparation.effective_control._asdict().items():
            np.testing.assert_allclose(
                values, proof["effective_control"][name], rtol=3e-14, atol=3e-15
            )
            if name not in ("junction", "pump"):
                np.testing.assert_array_equal(values, getattr(base, name))
        expected, derivative = readouts(
            implementation, state, actual.preparation.effective_control, runtime
        )
        exact_tree(actual.physical.readouts, expected)
        exact_tree(actual.physical.derivative, derivative)
        assert abs(float(actual.physical.field.energy_balance_pJ_s)) <= 1e-10
        assert fingerprints(spec, state, layout, component) == before
        name = f"stage-{kind}-{padded}-{stage}"
        evidence(
            name,
            dict(
                parameters=args,
                max_rate_error_fraction=error,
                max_potential_error_fraction=phi_error,
                actual_block_state=plain(actual.preparation.block_state),
                actual_control=plain(actual.preparation.effective_control),
                reference=proof,
                native=source,
                native_source_sha256=native.PINNED,
                passive_fraction=actual.physical.admission["passive_fraction"],
                fuel_fraction=actual.physical.admission["fuel_fraction"],
                field_energy_residual_pJ_s=float(actual.physical.field.energy_balance_pJ_s),
                scope=(
                    "Initial/evolved readout panel; no accepted event trajectory "
                    "or time synchronization"
                ),
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
        if stage == 0:
            state = rk4_step(
                lambda y, u, p, a: implementation.rhs(y, u, p, a, xp=np),
                state,
                step,
                actual.preparation.effective_control,
                runtime,
                runtime.active,
            )
            global_state = actual.preparation.block_state


@pytest.mark.parametrize("kind", KINDS)
def test_disabled_events_and_empty_program_keep_original_controls_and_do_not_draw(
    kind, monkeypatch
):
    spec, tissue, component, _, state, layout, base, binding, current = fixture(kind)

    def forbidden(*args, **kwargs):
        pytest.fail("Block control view sampled a random stream")

    monkeypatch.setattr(streams, "draw", forbidden)
    prepared = blocks.prepare(
        spec, tissue, binding, current, base, time_s=0.4, events_enabled=False
    )
    exact_tree(prepared.effective_control, base)
    prepared_again = blocks.prepare(
        spec, tissue, binding, current, base, time_s=0.4, events_enabled=True
    )
    twice = blocks.prepare(
        spec, tissue, binding, prepared_again.block_state, base, time_s=0.4, events_enabled=True
    )
    exact_tree(twice.effective_control, prepared_again.effective_control)
    assert all(not a.flags.writeable for a in twice.effective_control)
    empty = setters.bind(
        membrane_ids=binding.program.membrane_ids, events=(), provenance="Explicit empty program"
    )
    empty_binding = blocks.bind(
        spec,
        tissue,
        empty,
        junction_membrane_ids={j: (a, b) for j, a, b in binding.junction_membranes},
        provenance=binding.provenance,
    )
    unchanged = blocks.prepare(
        spec, tissue, empty_binding, current, base, time_s=0.4, events_enabled=True
    )
    exact_tree(unchanged.effective_control, base)


@pytest.mark.parametrize(
    "defect", ("missing", "unknown", "same", "reversed", "axis", "source", "seal")
)
def test_binding_rejects_wrong_contact_owners_or_original_association(defect):
    spec, tissue, _, _, _, _, _, binding, _ = fixture()
    pairs = {j: (a, b) for j, a, b in binding.junction_membranes}
    key = next(iter(pairs))
    program = binding.program
    if defect == "missing":
        pairs = {}
    elif defect == "unknown":
        pairs[key] = ("unknown", pairs[key][1])
    elif defect == "same":
        pairs[key] = (pairs[key][0],) * 2
    elif defect == "reversed":
        pairs[key] = pairs[key][::-1]
    elif defect == "axis":
        program = setters.bind(
            membrane_ids=program.membrane_ids[::-1],
            events=program.events,
            provenance=program.provenance,
        )
    else:
        saved = blocks.record(binding)
        if defect == "source":
            saved["source_definition_sha256"] = "0" * 64
        else:
            saved["identity"] = "0" * 64
        with pytest.raises(ValueError):
            blocks.restore(saved, spec, tissue)
        return
    with pytest.raises(ValueError):
        blocks.bind(
            spec, tissue, program, junction_membrane_ids=pairs, provenance=binding.provenance
        )


def test_asymmetric_native_membrane_block_refuses_without_averaging_or_mutation():
    spec, tissue, _, _, _, _, base, binding, current = fixture()
    pair = binding.junction_membranes[0][1:]
    event = replace(binding.program.events[0], target_ids=(pair[0],))
    program = setters.bind(
        membrane_ids=binding.program.membrane_ids,
        events=(event,),
        provenance=binding.program.provenance,
    )
    binding = blocks.bind(
        spec,
        tissue,
        program,
        junction_membrane_ids={j: (a, b) for j, a, b in binding.junction_membranes},
        provenance=binding.provenance,
    )
    original = plain(current)
    with pytest.raises(blocks.BlockControlRejected, match="Opposite membrane") as caught:
        blocks.prepare(spec, tissue, binding, current, base, time_s=0.4, events_enabled=True)
    assert plain(current) == original and caught.value.trial.physical_domain
    evidence(
        "asymmetric-refusal",
        dict(
            binding=blocks.record(binding),
            source_state=original,
            refused_trial=plain(caught.value.trial.state),
            reason=str(caught.value),
            physical_edge_averaging=False,
        ),
    )


@pytest.mark.parametrize("kind", ("temperature", "voltage", "pump_block"))
def test_unsupported_temperature_voltage_or_absent_pump_owners_refuse(kind):
    spec, tissue, _, _, _, _, _, binding, _ = fixture()
    kw = (
        dict(amplitude=0.1, positive_boundary="top", negative_boundary="bottom")
        if kind == "voltage"
        else {}
    )
    program = setters.bind(
        membrane_ids=binding.program.membrane_ids,
        events=(setters.Event(kind, 0.2, 1.2, 0.3, **kw),),
        provenance="Unsupported physical change",
    )
    with pytest.raises(ValueError):
        blocks.bind(
            spec,
            tissue,
            program,
            junction_membrane_ids={j: (a, b) for j, a, b in binding.junction_membranes},
            provenance=binding.provenance,
        )


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("enabled", (False, True))
def test_carried_pump_factor_requires_actual_nak_owners_in_every_family(kind, enabled):
    raw = definition(kind)
    model = raw["model"].get("ionic", raw["model"])
    for membrane in model["membranes"]:
        if "pump" in membrane:
            membrane["pump"] = None
    if kind != "passive":
        raw["experiment"]["pump_controls"] = []
    spec = parse_spec(raw)
    tissue = units.bind_tissue(spec, **arguments(spec, reverse=True))
    program = setters.bind(
        membrane_ids=tissue.component.membrane_ids, events=(), provenance="No Na/K owners"
    )
    pairs = {
        edge.id: tuple(
            next(m.id for m in spec.model.membranes if m.inside == cell)
            for cell in (edge.sender, edge.receiver)
        )
        for edge in spec.model.junctions
    }
    binding = blocks.bind(
        spec, tissue, program, junction_membrane_ids=pairs, provenance="Actual pump-free model"
    )
    table = control_values(spec, [0.0])
    base = type(table)(*(value[0] * 0.67 for value in table))
    current = blocks.BlockState(np.ones(len(program.membrane_ids)), np.asarray(1.0))
    result = blocks.prepare(
        spec, tissue, binding, current, base, time_s=0.4, events_enabled=enabled
    )
    exact_tree(result.effective_control, base)
    current = current._replace(pump_available=np.asarray(0.5))
    with pytest.raises(blocks.BlockControlRejected, match="No physical Na/K owners") as caught:
        blocks.prepare(spec, tissue, binding, current, base, time_s=0.4, events_enabled=enabled)
    assert caught.value.trial.physical_domain
    np.testing.assert_array_equal(current.pump_available, 0.5)
    with pytest.raises(ValueError, match="no actual Na/K owners"):
        reference.prepare(
            spec.to_dict(), setters.record(program), binding.junction_membranes,
            plain(current), plain(base), 0.4, enabled,
        )
    pump_program = setters.bind(
        membrane_ids=program.membrane_ids,
        events=(setters.Event("pump_block", 0.2, 1.2, 0.3),),
        provenance=program.provenance,
    )
    with pytest.raises(ValueError, match="actual Na/K pump owners"):
        blocks.bind(
            spec, tissue, pump_program, junction_membrane_ids=pairs, provenance=binding.provenance
        )
    evidence(
        f"ownerless-pump-{kind}-{enabled}",
        dict(definition=spec.to_dict(), binding=blocks.record(binding),
             original_state=plain(current), base_control=plain(base), time_s=0.4,
             source_valid_trial=plain(caught.value.trial.state),
             reason=str(caught.value), events_enabled=enabled,
             independent_reference_refused=True, input_unchanged=True),
    )


@pytest.mark.parametrize("defect", ("negative", "nan", "float32", "shape", "clock", "enabled"))
def test_incomplete_state_or_implicit_control_metadata_refuses(defect):
    spec, tissue, _, _, _, _, base, binding, current = fixture()
    clock, enabled = 0.4, True
    if defect == "negative":
        current = current._replace(junction_available=-current.junction_available)
    elif defect == "nan":
        current = current._replace(pump_available=np.asarray(np.nan))
    elif defect == "float32":
        current = current._replace(junction_available=current.junction_available.astype(np.float32))
    elif defect == "shape":
        current = current._replace(junction_available=np.ones(1))
    elif defect == "clock":
        clock = float("inf")
    else:
        enabled = 1
    with pytest.raises(ValueError):
        blocks.prepare(spec, tissue, binding, current, base, time_s=clock, events_enabled=enabled)
