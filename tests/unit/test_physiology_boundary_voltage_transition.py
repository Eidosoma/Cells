"""Ideal ramp histories, independent owner algebra and durable complete restart."""

import json
import math
import os
import shutil
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells import physiology_boundary_voltage_transition_io as storage
from cells.core import physiology_boundary_voltage as boundary
from cells.core import physiology_boundary_voltage_transition as ramps
from cells.core import physiology_random_streams as streams
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, digest, parse_spec
from cells.core.state import Checkpoint
from cells.numerics.fixed_step import rk4_step
from cells.processes import betse_global_controls as setters
from tests.unit.test_physiology_boundary_voltage import KINDS, SIDES, fixture, plain
from tests.unit.test_physiology_tissue_binding import definition
from validation.tissue import physiology_boundary_voltage_transition_reference as reference


def evidence(name, record, arrays=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(directory) / "boundary-voltage-transition"
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


def setup(kind="passive", *, padded=True, evolved=False, capacity=16, binding_override=None):
    spec, model, state, layout, _, binding, _ = fixture(kind, padded=padded)
    if binding_override is not None:
        binding = binding_override(spec, binding)
    table = control_values(spec, [0.0])
    control = type(table)(*(value[0] for value in table))
    time = 0.0
    index = 0
    if evolved:
        state = rk4_step(
            lambda y, u, p, a: model.rhs(y, u, p, a, xp=np),
            state,
            spec.execution.dt,
            control,
            layout,
            layout.active,
        )
        model.check_values(state, spec)
        time, index = spec.execution.dt, 1
    numeric = Checkpoint(state, layout, time, index, event_index(spec, time))
    point = ramps.initialise(
        spec,
        numeric,
        binding,
        capacity=capacity,
        provenance="Manufactured ideal capacitor-only path; no biological calibration",
    )
    return spec, model, point


def declaration(values, provenance="Explicit reversible capacitive path"):
    return ramps.declare(
        target_boundary_voltage_V=dict(zip(SIDES, values, strict=True)), provenance=provenance
    )


def parent_arrays(point):
    return dict(numeric=ramps.record(point)["numeric"], control=ramps.record(point)["control"])


def paths(point):
    origin = point.origin_boundary_state.boundary_voltage_V
    forward = origin.copy()
    forward[0] += 0.006
    forward[1] -= 0.004
    first = origin.copy()
    first[0] += 0.004
    second = first.copy()
    second[1] += 0.003
    third = origin.copy()
    third[1] += 0.003
    return [declaration(value) for value in (forward, origin, first, second, third, origin)]


def compact_change(change, layout):
    result = {}
    for name in storage.ARRAY_FIELDS:
        value = np.asarray(getattr(change, name))
        if name == "delta_membrane_voltage_V":
            value = value[layout.membrane_active]
        elif name == "node_charge_change_C":
            value = np.r_[
                value[: layout.active.size][layout.active],
                value[layout.active.size :][layout.outside_active],
            ]
        else:
            value = value[layout.outside_active]
        result[name] = value.tolist()
    result.update(
        capacitor_energy_change_pJ=change.capacitor_energy_change_pJ,
        work_residual_pJ=change.work_residual_pJ,
    )
    return result


def compact_point(point):
    return dict(
        segments=[compact_change(row.change, point.numeric.layout) for row in point.segments],
        cumulative_electrode_charge_C=point.cumulative_electrode_charge_C[
            point.numeric.layout.outside_active
        ].tolist(),
        cumulative_external_work_pJ=point.cumulative_external_work_pJ[
            point.numeric.layout.outside_active
        ].tolist(),
        cumulative_capacitor_energy_pJ=point.cumulative_capacitor_energy_pJ,
    )


def inputs(spec, point):
    return dict(
        raw=spec.to_dict(),
        fields=plain(point.numeric.state),
        binding_record=boundary.record(point.binding),
        held_control=plain(point.control),
        numeric_time_s=point.numeric.time,
        declarations=[ramps.declaration_record(row.declaration) for row in point.segments],
    )


def comparison(actual, expected):
    maximum = 0.0

    def compare(name, value, target):
        nonlocal maximum
        value, target = np.asarray(value), np.asarray(target)
        if name.endswith("_C"):
            absolute, relative = 3e-25, 2e-12
        elif name.endswith("_V"):
            absolute, relative = 3e-13, 3e-10
        else:
            absolute, relative = 3e-14, 3e-10
        maximum = max(
            maximum,
            float(np.max(abs(value - target) / (absolute + relative * abs(target)), initial=0)),
        )

    for left, right in zip(actual["segments"], expected["segments"], strict=True):
        for key, value in left.items():
            compare(key, value, right[key])
    for key in (
        "cumulative_electrode_charge_C",
        "cumulative_external_work_pJ",
        "cumulative_capacitor_energy_pJ",
    ):
        compare(key, actual[key], expected[key])
    return maximum


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("padded", (False, True))
@pytest.mark.parametrize("evolved", (False, True))
def test_full_owner_forward_reverse_and_rectangular_cycles_match_independent_reference(
    kind, padded, evolved
):
    spec, _, point = setup(kind, padded=padded, evolved=evolved)
    origin = point
    parent = parent_arrays(point)
    for number, ramp in enumerate(paths(point)):
        result = ramps.advance(spec, point, ramp)
        assert parent_arrays(result.checkpoint) == parent
        assert result.admission["ionic_evolution"] is False
        assert result.admission["native_transition_claim"] is False
        assert result.admission["heat_added"] is False
        assert result.checkpoint.numeric.time == origin.numeric.time
        point = result.checkpoint
        assert len(point.segments) == number + 1
    recorded = inputs(spec, point)
    expected = reference.evaluate(**recorded)
    actual = compact_point(point)
    error = comparison(actual, expected)
    oracle = reference.held.ORACLES[spec.to_dict()["model"]["id"]]
    context = oracle.bind(spec.to_dict())
    rate = oracle.flatten(context, result.after.derivative._asdict())
    target = np.asarray(expected["final_rate"])
    atol = oracle.flatten(
        context,
        {
            key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
            for key, shape in context["shapes"].items()
        },
    )
    rate_budget = atol + 3e-10 * abs(target)
    rate_error = float(np.max(abs(rate - target) / rate_budget, initial=0))
    p = point.numeric.layout
    phi = np.r_[
        result.after.field.potential_V[: p.active.size][p.active],
        result.after.field.potential_V[p.active.size :][p.outside_active],
    ]
    target_phi = np.asarray(expected["final_phi"])
    phi_budget = 3e-13 + 3e-10 * abs(target_phi)
    phi_error = float(np.max(abs(phi - target_phi) / phi_budget, initial=0))
    evidence(
        f"history-{kind}-{padded}-{evolved}",
        dict(
            inputs=recorded,
            actual=actual,
            reference=expected,
            max_algebra_error_fraction=error,
            max_rate_error_fraction=rate_error,
            max_potential_error_fraction=phi_error,
            original_ordinary_history_unchanged=True,
            accepted_segments=6,
            native_transition_claim=False,
            stage_energy_residual_pJ_s=float(result.after.field.energy_balance_pJ_s),
            path_scope="ideal capacitor-only operator; no ionic trajectory or biological case",
        ),
        dict(
            actual_rate=rate,
            expected_rate=target,
            rate_budget=rate_budget,
            actual_phi=phi,
            expected_phi=target_phi,
            phi_budget=phi_budget,
        ),
    )
    assert max(error, rate_error, phi_error) <= 1
    assert max(abs(point.cumulative_electrode_charge_C)) <= 3e-25
    assert abs(point.cumulative_capacitor_energy_pJ) <= 3e-14
    # The rectangular cycle transfers work between electrodes. Keep each owner.
    assert max(abs(point.cumulative_external_work_pJ)) > 1e-8
    assert abs(math.fsum(point.cumulative_external_work_pJ)) <= 3e-14
    assert len(point.segments) == 6
    assert parent_arrays(point) == parent


@pytest.mark.parametrize("kind", KINDS)
def test_corner_refusal_retains_complete_parent_and_declaration_then_equal_corner_admits(kind):
    def corner(spec, binding):
        mapping = dict(binding.boundary_reservoir_ids)
        mapping["left"] = ("outside_0",)
        return boundary.bind(
            spec,
            binding.program,
            boundary_reservoir_ids=mapping,
            provenance="Explicit shared corner",
        )

    spec, _, point = setup(kind, binding_override=corner)
    original = ramps.record(point)
    target = point.boundary_state.boundary_voltage_V.copy()
    target[0] += 0.004
    ramp = declaration(target)
    with pytest.raises(ramps.TransitionRejected) as caught:
        ramps.advance(spec, point, ramp)
    error = caught.value
    assert error.source is point and error.declaration is ramp
    assert error.stage == "held_endpoint" and "held_refusal" in error.trial
    assert ramps.record(point) == original
    target[2] = target[0]
    accepted = ramps.advance(spec, point, declaration(target))
    assert accepted.segment.change.valid
    evidence(
        "corner-" + kind,
        dict(
            parent=original,
            declaration=ramps.declaration_record(ramp),
            stage=error.stage,
            conflicting_owners=error.trial["held_refusal"]["conflicting_owners"],
            parent_unchanged=True,
        ),
    )


@pytest.mark.parametrize(
    "corruption",
    (
        "numeric-state",
        "numeric-clock",
        "layout",
        "control",
        "current",
        "history-array",
        "cumulative-work",
        "capacity",
        "binding",
    ),
)
def test_resealed_malformed_parents_cannot_bypass_complete_source_and_path_laws(corruption):
    spec, _, point = setup()
    point = ramps.advance(spec, point, paths(point)[0]).checkpoint
    original = ramps.record(point)
    changed = point
    if corruption == "numeric-state":
        value = point.numeric.state.amount_increment.copy()
        value[0, 0] += 1.0
        changed = replace(
            point,
            numeric=replace(
                point.numeric, state=point.numeric.state._replace(amount_increment=value)
            ),
        )
    elif corruption == "numeric-clock":
        changed = replace(point, numeric=replace(point.numeric, time=spec.execution.dt / 2))
    elif corruption == "layout":
        value = point.numeric.layout.initial_membrane_voltage_V.copy()
        value[0] += 0.001
        changed = replace(
            point,
            numeric=replace(
                point.numeric,
                layout=point.numeric.layout._replace(initial_membrane_voltage_V=value),
            ),
        )
    elif corruption == "control":
        changed = replace(
            point, control=point.control._replace(membrane=point.control.membrane * 0.9)
        )
    elif corruption == "current":
        value = point.boundary_state.boundary_voltage_V.copy()
        value[0] += 0.001
        changed = replace(point, boundary_state=boundary.BoundaryState(value))
    elif corruption == "history-array":
        segment = point.segments[0]
        value = segment.change.externally_supplied_work_pJ.copy()
        value[0] += 0.01
        changed = replace(
            point,
            segments=(
                replace(segment, change=replace(segment.change, externally_supplied_work_pJ=value)),
            ),
        )
    elif corruption == "cumulative-work":
        changed = replace(
            point, cumulative_external_work_pJ=point.cumulative_external_work_pJ + 0.01
        )
    elif corruption == "capacity":
        changed = replace(point, capacity=0)
    else:
        binding = replace(point.binding, source_definition_sha256="0" * 64)
        binding = replace(binding, identity=boundary.record(binding)["identity"])
        changed = replace(point, binding=binding)
    changed = ramps._seal(changed)
    ramp = paths(point)[1]
    with pytest.raises(ramps.TransitionRejected) as caught:
        ramps.advance(spec, changed, ramp)
    assert caught.value.source is changed and caught.value.declaration is ramp
    assert caught.value.stage == "parent_admission"
    assert ramps.record(point) == original


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("evolved", (False, True))
def test_complete_durable_restart_reproduces_next_transition_and_all_owner_histories(
    kind, evolved, tmp_path
):
    spec, _, point = setup(kind, evolved=evolved)
    sequence = paths(point)
    for ramp in (sequence[0], sequence[2]):
        point = ramps.advance(spec, point, ramp).checkpoint
    original = ramps.record(point)
    source = storage.write_transition_checkpoint(tmp_path / "saved", spec, point)
    loaded = storage.load_transition_checkpoint(source)
    assert ramps.record(loaded.checkpoint) == original
    # Ordinary snapshot IO produces JAX buffers; the host-only transition must
    # restore immutable host buffers without changing any recorded numeric bit.
    for values in (loaded.checkpoint.numeric.state, loaded.checkpoint.numeric.layout):
        assert all(type(value) is np.ndarray and not value.flags.writeable for value in values)
    expected = ramps.advance(spec, point, sequence[3])
    actual = storage.advance_transition_checkpoint(source, tmp_path / "next", sequence[3])
    assert ramps.record(actual.checkpoint) == ramps.record(expected.checkpoint)
    again = storage.load_transition_checkpoint(tmp_path / "next")
    assert ramps.record(again.checkpoint) == ramps.record(expected.checkpoint)
    assert loaded.checkpoint.numeric.time == point.numeric.time
    assert all(not array.flags.writeable for array in loaded.checkpoint.control)
    assert not loaded.checkpoint.cumulative_external_work_pJ.flags.writeable
    with pytest.raises(FileExistsError):
        storage.write_transition_checkpoint(source, spec, point)
    evidence(
        f"restart-{kind}-{evolved}",
        dict(
            model_id=spec.to_dict()["model"]["id"],
            saved_association=original,
            next_identity=actual.checkpoint.identity,
            complete_next_transition_exact=True,
            ordinary_time_unchanged=True,
            immutable_host_numeric_buffers=True,
        ),
    )


def reseal_archive(path):
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["files"] = {name: storage.durable._sha(path / name) for name in storage.FILES}
    manifest["identity"] = digest(
        {key: value for key, value in manifest.items() if key != "identity"}
    )
    (path / "manifest.json").write_text(json.dumps(manifest))


@pytest.mark.parametrize(
    "corruption", ("outer", "payload", "missing-array", "extra-array", "history-scalar", "source")
)
def test_durable_refuses_corrupt_extended_resealed_or_source_changed_archives(
    corruption, tmp_path, monkeypatch
):
    spec, _, point = setup()
    point = ramps.advance(spec, point, paths(point)[0]).checkpoint
    original = storage.write_transition_checkpoint(tmp_path / "original", spec, point)
    path = tmp_path / "changed"
    shutil.copytree(original, path)
    if corruption == "outer":
        manifest = json.loads((path / "manifest.json").read_text())
        manifest["complete"] = False
        (path / "manifest.json").write_text(json.dumps(manifest))
    elif corruption == "payload":
        with (path / "transition.npz").open("ab") as handle:
            handle.write(b"changed")
    elif corruption in ("missing-array", "extra-array"):
        with np.load(path / "transition.npz", allow_pickle=False) as saved:
            arrays = {key: saved[key].copy() for key in saved.files}
        if corruption == "missing-array":
            arrays.pop("cumulative_external_work_pJ")
        else:
            arrays["invented_heat"] = np.asarray(1.0)
        np.savez_compressed(path / "transition.npz", **arrays)
        reseal_archive(path)
    elif corruption == "history-scalar":
        saved = json.loads((path / "transition.json").read_text())
        saved["changes"][0]["capacitor_energy_change_pJ"] += 0.01
        (path / "transition.json").write_text(json.dumps(saved))
        reseal_archive(path)
    else:
        changed = storage.numeric_io.source_hashes() | {"invented-source.py": "0" * 64}
        monkeypatch.setattr(storage.numeric_io, "source_hashes", lambda: changed)
    with pytest.raises((ConfigError, ValueError)):
        storage.load_transition_checkpoint(path)


def test_publication_source_race_retains_failed_payload_and_cannot_restore(tmp_path, monkeypatch):
    spec, _, point = setup()
    original = storage.numeric_io.source_hashes
    count = 0

    def changing():
        nonlocal count
        count += 1
        result = original()
        return result if count == 1 else result | {"changed-source.py": "0" * 64}

    monkeypatch.setattr(storage.numeric_io, "source_hashes", changing)
    with pytest.raises(ConfigError, match="changed"):
        storage.write_transition_checkpoint(tmp_path / "failed", spec, point)
    assert (tmp_path / "failed/failure.json").is_file()
    assert not (tmp_path / "failed/manifest.json").exists()
    assert (tmp_path / "failed/numeric/state.npz").is_file()
    with pytest.raises(ConfigError, match="Failed"):
        storage.load_transition_checkpoint(tmp_path / "failed")


@pytest.mark.parametrize("kind", KINDS)
def test_single_ulp_ramps_keep_nonzero_incremental_charge_and_segment_work(kind):
    spec, _, point = setup(kind)
    target = point.boundary_state.boundary_voltage_V.copy()
    target[0] = np.nextafter(target[0], np.inf)
    result = ramps.advance(spec, point, declaration(target))
    change = result.segment.change
    assert max(abs(change.electrode_charge_change_C)) > 0
    assert max(abs(change.externally_supplied_work_pJ)) > 0
    assert np.max(abs(change.electrode_charge_change_C)) < 1e-25
    recorded = inputs(spec, result.checkpoint)
    expected = reference.evaluate(**recorded)
    actual = compact_point(result.checkpoint)
    error = comparison(actual, expected)
    evidence(
        "tiny-" + kind,
        dict(
            inputs=recorded,
            actual=actual,
            reference=expected,
            max_algebra_error_fraction=error,
            incremental_charge_nonzero=True,
            difference_of_absolute_charge_not_used=True,
        ),
    )
    assert error <= 1


@pytest.mark.parametrize(
    "bad", ("missing", "extra", "boolean", "nan", "infinity", "law", "provenance", "sequence")
)
def test_declaration_refuses_unsupported_or_noncanonical_physical_paths(bad):
    target = dict.fromkeys(SIDES, 0.0)
    kwargs = dict(target_boundary_voltage_V=target, provenance="Declared path")
    if bad == "missing":
        target.pop("right")
    elif bad == "extra":
        target["centre"] = 0.0
    elif bad == "boolean":
        target["top"] = True
    elif bad == "nan":
        target["top"] = float("nan")
    elif bad == "infinity":
        target["top"] = float("inf")
    elif bad == "law":
        kwargs["law"] = "instantaneous_step_with_unspecified_heat"
    elif bad == "provenance":
        kwargs["provenance"] = ""
    else:
        kwargs["target_boundary_voltage_V"] = [0.0] * 4
    with pytest.raises(ValueError):
        ramps.declare(**kwargs)


def test_capacity_refusal_and_rng_guard_preserve_complete_parent_and_pending_declaration(
    monkeypatch,
):
    spec, _, point = setup(capacity=1)

    def forbidden(*args, **kwargs):
        pytest.fail("An ideal capacitor ramp consumed a random stream")

    monkeypatch.setattr(streams, "draw", forbidden)
    sequence = paths(point)
    point = ramps.advance(spec, point, sequence[0]).checkpoint
    before = ramps.record(point)
    with pytest.raises(ramps.TransitionRejected, match="capacity") as caught:
        ramps.advance(spec, point, sequence[1])
    assert caught.value.source is point and caught.value.declaration is sequence[1]
    assert ramps.record(point) == before


@pytest.mark.parametrize("kind", ("calcium", "fuel"))
def test_finite_only_families_keep_identity_and_refuse_electrode_substitution(kind):
    spec = parse_spec(definition(kind))
    model = storage.transition.held.IMPLEMENTATIONS[type(spec.model)]
    state, layout = model.initial_values(spec)
    program = setters.bind(
        membrane_ids=tuple(row.id for row in spec.model.membranes),
        events=(),
        provenance="No physical electrodes",
    )
    mapping = dict.fromkeys(SIDES, ())
    binding = boundary.bind(
        spec, program, boundary_reservoir_ids=mapping, provenance="Finite-only gauge"
    )
    point = ramps.initialise(
        spec, Checkpoint(state, layout, 0.0, 0, 0), binding, provenance="Identity only"
    )
    result = ramps.advance(spec, point, declaration(point.boundary_state.boundary_voltage_V))
    assert not np.any(result.segment.change.electrode_charge_change_C)
    assert not np.any(result.segment.change.externally_supplied_work_pJ)
    mapping["top"] = (spec.model.gauge_reference,)
    with pytest.raises(ValueError, match="gauges"):
        boundary.bind(spec, program, boundary_reservoir_ids=mapping, provenance="Invalid electrode")
