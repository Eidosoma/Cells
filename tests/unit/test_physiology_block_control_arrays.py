"""Complete blocker array frames, host/reference agreement and batch isolation."""

import json
import os
from dataclasses import replace
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core import physiology_tissue_binding as units
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.models import physiology_block_control_view as host
from cells.numerics import physiology_block_control_arrays as arrays
from cells.processes import betse_global_controls as setters
from tests.unit.test_physiology_block_control_view import fixture, plain
from tests.unit.test_physiology_permeability_view import KINDS, exact_tree
from tests.unit.test_physiology_tissue_binding import arguments
from validation.tissue import physiology_block_control_reference as reference

EPS = np.finfo(np.float64).eps


def evidence(name, record, payload=None):
    if root := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        directory = Path(root) / "block-arrays"
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / (name + ".json")).open("x") as stream:
            json.dump(
                record,
                stream,
                indent=2,
                sort_keys=True,
                allow_nan=False,
                default=lambda x: np.asarray(x).tolist(),
            )
            stream.write("\n")
        if payload is not None:
            np.savez_compressed(directory / (name + ".npz"), **payload)


def flatten(value, prefix):
    if hasattr(value, "_asdict"):
        return {
            name: item
            for key, child in value._asdict().items()
            for name, item in flatten(child, prefix + "__" + key).items()
        }
    return {prefix: np.asarray(value)}


def independent(spec, binding, state, base, time, enabled, actual):
    args = dict(
        raw=spec.to_dict(),
        program=setters.record(binding.program),
        pairs=binding.junction_membranes,
        block_state=plain(state),
        base_control=plain(base),
        time_s=float(time),
        events_enabled=bool(enabled),
    )
    block, control = reference.prepare(**args)
    values = dict(
        block_state=plain(actual.block_state), effective_control=plain(actual.effective_control)
    )
    target = dict(block_state=block, effective_control=control)
    maximum, scalars = 0.0, 0
    for key in target:
        for field, value in target[key].items():
            a, b = np.asarray(values[key][field]), np.asarray(value)
            error = np.max(abs(a - b) / (64 * EPS * np.maximum(1, abs(b))), initial=0)
            assert error <= 1
            maximum = max(maximum, float(error))
            scalars += b.size
    return dict(
        parameters=args,
        actual=values,
        reference=target,
        maximum_error_fraction=maximum,
        scalar_comparisons=scalars,
    )


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("padded", (False, True))
def test_numpy_complete_control_frames_match_host_and_decimal(kind, padded):
    spec, tissue, _, _, _, _, base, binding, state = fixture(kind, padded=padded)
    kernel = arrays.compile_kernel(spec, tissue, binding)
    assert all(not leaf.flags.writeable for leaf in jax.tree.leaves(kernel))
    state = state._replace(
        junction_available=state.junction_available * 0.83,
        pump_available=np.asarray(1.0 if kind == "passive" else 0.72),
    )
    cases = []
    for time, enabled in ((0.4, True), (0.9, False), (1.5, True)):
        before = {**flatten(state, "state"), **flatten(base, "base"), **flatten(kernel, "kernel")}
        before = {k: v.tobytes() for k, v in before.items()}
        actual = arrays.apply(state, base, kernel, np.asarray(time), enabled, xp=np)
        expected = host.prepare(
            spec, tissue, binding, state, base, time_s=time, events_enabled=enabled
        )
        assert actual.valid and all(actual.checks.values())
        exact_tree(actual.block_state, expected.block_state)
        exact_tree(actual.effective_control, expected.effective_control)
        exact_tree(actual.source_values, expected.source_values)
        for name in base._fields:
            if name not in ("junction", "pump"):
                np.testing.assert_array_equal(
                    getattr(actual.effective_control, name), getattr(base, name)
                )
        inactive = ~kernel.junction_active
        np.testing.assert_array_equal(
            actual.effective_control.junction[inactive], base.junction[inactive]
        )
        after = {**flatten(state, "state"), **flatten(base, "base"), **flatten(kernel, "kernel")}
        assert {k: v.tobytes() for k, v in after.items()} == before
        repeated = arrays.apply(actual.block_state, base, kernel, np.asarray(time), enabled, xp=np)
        exact_tree(repeated.effective_control, actual.effective_control)
        cases.append(independent(spec, binding, state, base, time, enabled, actual))
        state = actual.block_state
    evidence(
        f"numpy-{kind}-{padded}",
        dict(
            cases=cases, host_controls_exact=True, input_arrays_unchanged=True, biological_cases=0
        ),
    )


DEFECTS = {
    "negative_state": "initial_block_domain",
    "nan_state": "initial_block_domain",
    "base": "original_control_domain",
    "label": "finite_event_label",
    "asymmetric": "symmetric_contact_factors",
    "index": "junction_indices",
    "owner": "junction_owners",
    "reused": "exclusive_contact_membranes",
    "no_owner": "actual_nak_owners",
    "temperature_program": "block_only_program",
}


def bad_inputs(defect, state, base, kernel):
    state, base, kernel = jax.tree.map(lambda x: np.asarray(x).copy(), (state, base, kernel))
    time = np.asarray(0.4)
    if defect == "negative_state":
        state.junction_available[:] = -0.1
    elif defect == "nan_state":
        state.pump_available[...] = np.nan
    elif defect == "base":
        base.membrane[0] = 1.1
    elif defect == "label":
        time[...] = np.inf
    elif defect == "asymmetric":
        kernel.setters.junction_mask[:] = False
        kernel.setters.junction_mask[kernel.junction_sender_membrane[0]] = True
    elif defect == "index":
        kernel.junction_sender_membrane[0] = -1
    elif defect == "owner":
        kernel.membrane_cell[kernel.junction_sender_membrane[0]] = kernel.junction_receiver_cell[0]
    elif defect == "reused":
        fields = dict(kernel._asdict())
        for key in (
            "junction_sender_membrane",
            "junction_receiver_membrane",
            "junction_sender_cell",
            "junction_receiver_cell",
            "junction_active",
        ):
            fields[key] = np.repeat(fields[key][:1], 2)
        base = base._replace(junction=np.repeat(base.junction[:1], 2))
        fields["control_template"] = fields["control_template"]._replace(junction=np.zeros(2))
        kernel = arrays.Kernel(**fields)
    elif defect == "no_owner":
        kernel.has_nak_owners[...] = False
    else:
        kernel.setters.enabled[0] = True
    return state, base, kernel, time


@pytest.mark.parametrize("defect", DEFECTS)
def test_invalid_numeric_trials_retain_raw_values_and_diagnostics(defect):
    spec, tissue, _, _, _, _, base, binding, state = fixture("ionic")
    kernel = arrays.compile_kernel(spec, tissue, binding)
    state, base, kernel, time = bad_inputs(defect, state, base, kernel)
    payload = {
        **flatten(state, "state"),
        **flatten(base, "base"),
        **flatten(kernel, "kernel"),
        "time": time,
    }
    before = {k: v.tobytes() for k, v in payload.items()}
    with np.errstate(all="ignore"):
        result = arrays.apply(state, base, kernel, time, True, xp=np)
    assert not result.valid and not result.checks[DEFECTS[defect]]
    assert {k: v.tobytes() for k, v in payload.items()} == before
    evidence(
        "invalid-" + defect,
        dict(
            expected_refusal=DEFECTS[defect],
            checks={k: bool(v) for k, v in result.checks.items()},
            raw_inputs_preserved=True,
            physical_frame_provenance=host.record(binding),
        ),
        payload
        | flatten(result.source_values, "source_trial")
        | flatten(result.effective_control, "control_trial"),
    )


@pytest.mark.parametrize("kind", KINDS)
def test_actual_pump_free_models_reject_nonunit_carried_factor_even_when_disabled(kind):
    spec, _, _, _, _, _, _, _, _ = fixture(kind)
    raw = spec.to_dict()
    model = raw["model"].get("ionic", raw["model"])
    for m in model["membranes"]:
        if "pump" in m:
            m["pump"] = None
    if kind != "passive":
        raw["experiment"]["pump_controls"] = []
    spec = parse_spec(raw)
    tissue = units.bind_tissue(spec, **arguments(spec, reverse=True))
    program = setters.bind(
        membrane_ids=tissue.component.membrane_ids, events=(), provenance="No NaK owners"
    )
    pairs = {
        j.id: tuple(
            next(m.id for m in spec.model.membranes if m.inside == cell)
            for cell in (j.sender, j.receiver)
        )
        for j in spec.model.junctions
    }
    binding = host.bind(
        spec, tissue, program, junction_membrane_ids=pairs, provenance="Actual empty pump family"
    )
    kernel = arrays.compile_kernel(spec, tissue, binding)
    table = control_values(spec, [0.0])
    base = type(table)(*(v[0] for v in table))
    state = host.BlockState(np.ones(len(program.membrane_ids)), np.asarray(1.0))
    valid = arrays.apply(state, base, kernel, np.asarray(0.4), False, xp=np)
    assert valid.valid
    bad = state._replace(pump_available=np.asarray(0.5))
    refused = arrays.apply(bad, base, kernel, np.asarray(0.4), False, xp=np)
    assert not refused.valid and not refused.checks["actual_nak_owners"]
    with pytest.raises(host.BlockControlRejected):
        host.prepare(spec, tissue, binding, bad, base, time_s=0.4, events_enabled=False)
    with pytest.raises(ValueError):
        reference.prepare(
            raw,
            setters.record(program),
            binding.junction_membranes,
            plain(bad),
            plain(base),
            0.4,
            False,
        )


@pytest.mark.parametrize(
    "defect",
    (
        "state_dtype",
        "control_dtype",
        "shape",
        "time_dtype",
        "enable_dtype",
        "owner_dtype",
        "control_type",
        "binding",
    ),
)
def test_incomplete_types_precision_and_host_association_refuse(defect):
    spec, tissue, _, _, _, _, base, binding, state = fixture()
    kernel = arrays.compile_kernel(spec, tissue, binding)
    time, enabled = np.asarray(0.4), True
    if defect == "state_dtype":
        state = state._replace(junction_available=state.junction_available.astype(np.float32))
    elif defect == "control_dtype":
        base = base._replace(membrane=base.membrane.astype(np.float32))
    elif defect == "shape":
        state = state._replace(junction_available=np.ones((1, 1)))
    elif defect == "time_dtype":
        time = np.asarray(0.4, dtype=np.float32)
    elif defect == "enable_dtype":
        enabled = np.asarray(1)
    elif defect == "owner_dtype":
        kernel = kernel._replace(membrane_cell=kernel.membrane_cell.astype(np.float64))
    elif defect == "control_type":
        base = tuple(base)
    else:
        with pytest.raises(ValueError):
            arrays.compile_kernel(spec, tissue, replace(binding, identity="0" * 64))
        return
    with pytest.raises(ValueError):
        arrays.apply(state, base, kernel, time, enabled, xp=np)


@pytest.mark.parametrize("kind", KINDS)
def test_cpu_jax_complete_world_batches_preserve_invalid_world_isolation(kind):
    spec, tissue, _, _, _, _, base, binding, state = fixture(kind)
    kernel = arrays.compile_kernel(spec, tissue, binding)
    worlds = []
    defects = (
        "negative_state",
        "nan_state",
        "base",
        "label",
        "asymmetric",
        "index",
        "owner",
        "temperature_program",
    )
    for i in range(32):
        if i < 24:
            scale = 0.4 + 0.6 * i / 23
            held = type(base)(*(v * scale for v in base))
            worlds.append((state, held, kernel, np.asarray(-0.2 + 0.1 * i), np.asarray(i % 5 != 0)))
        else:
            s, b, k, t = bad_inputs(defects[i - 24], state, base, kernel)
            worlds.append((s, b, k, t, np.asarray(True)))
    batch = jax.tree.map(lambda *values: jnp.asarray(np.stack(values)), *worlds)
    run = jax.jit(jax.vmap(arrays.apply))
    actual = jax.tree.map(lambda v: np.asarray(v.block_until_ready()), run(*batch))
    np.testing.assert_array_equal(
        actual.valid, np.r_[np.ones(24, dtype=bool), np.zeros(8, dtype=bool)]
    )
    cases = []
    for i, (s, b, k, t, e) in enumerate(worlds):
        row = jax.tree.map(lambda v, i=i: v[i], actual)
        with np.errstate(all="ignore"):
            expected = arrays.apply(s, b, k, t, e, xp=np)
        assert {n: bool(v) for n, v in row.checks.items()} == {
            n: bool(v) for n, v in expected.checks.items()
        }
        for a, b in zip(jax.tree.leaves(row), jax.tree.leaves(expected), strict=True):
            np.testing.assert_allclose(a, b, rtol=64 * EPS, atol=64 * EPS, equal_nan=True)
        if i < 24:
            cases.append(independent(spec, binding, s, worlds[i][1], t, e, row))
    shared = jax.jit(jax.vmap(lambda s, b, t, e: arrays.apply(s, b, kernel, t, e)))
    s, b, _, t, e = jax.tree.map(lambda v: v[:24], batch)
    same_map = jax.tree.map(lambda v: np.asarray(v.block_until_ready()), shared(s, b, t, e))
    for a, b in zip(jax.tree.leaves(same_map), jax.tree.leaves(actual), strict=True):
        np.testing.assert_allclose(a, b[:24], rtol=64 * EPS, atol=64 * EPS, equal_nan=True)
    evidence(
        "cpu-jax-" + kind,
        dict(
            cases=cases,
            compiled_worlds=32,
            valid_worlds=24,
            refused_worlds=8,
            shared_host_kernel_compiled=True,
            shared_map_worlds=24,
            independent_world_isolation=True,
            backend="cpu_jax",
            biological_cases=0,
        ),
        {
            "valid": actual.valid,
            **flatten(actual.source_values, "source_trial"),
            **flatten(actual.effective_control, "control_trial"),
        },
    )


@pytest.mark.parametrize("topology", ("empty", "self_contact"))
def test_empty_contacts_and_source_self_contact_refusal(topology):
    spec, _, _, _, _, _, _, _, _ = fixture()
    raw = spec.to_dict()
    if topology == "empty":
        raw["model"]["junctions"] = []
        raw["experiment"]["junction_controls"] = []
    else:
        edge = raw["model"]["junctions"][0]
        edge["receiver"] = edge["sender"]
    if topology == "self_contact":
        with pytest.raises(ConfigError, match="join an owner to itself"):
            parse_spec(raw)
        # Bypassing the ordinary parser must not bypass array compilation's
        # explicit physical-owner check either.
        spec = replace(
            spec,
            model=replace(
                spec.model,
                junctions=tuple(
                    replace(edge, receiver=edge.sender) for edge in spec.model.junctions
                ),
            ),
        )
    else:
        spec = parse_spec(raw)
    tissue = units.bind_tissue(spec, **arguments(spec, reverse=True))
    program = setters.bind(
        membrane_ids=tissue.component.membrane_ids,
        events=(),
        provenance="Existing host graph domain, no event program",
    )
    pairs = {
        edge.id: tuple(m.id for m in spec.model.membranes if m.inside == edge.sender)[:2]
        for edge in spec.model.junctions
    }
    binding = host.bind(
        spec, tissue, program, junction_membrane_ids=pairs, provenance="Named host contact domain"
    )
    if topology == "self_contact":
        with pytest.raises(ValueError, match="join a cell to itself"):
            arrays.compile_kernel(spec, tissue, binding)
        evidence(
            "topology-self-refusal",
            dict(
                source_parser_refused=True,
                compiled_owner_admission_refused=True,
                source_definition=raw,
                biological_cases=0,
            ),
        )
        return
    table = control_values(spec, [0.0])
    base = type(table)(*(v[0] for v in table))
    state = host.BlockState(np.full(len(program.membrane_ids), 0.83), np.asarray(1.0))
    kernel = arrays.compile_kernel(spec, tissue, binding)
    actual = arrays.apply(state, base, kernel, np.asarray(0.4), True, xp=np)
    expected = host.prepare(spec, tissue, binding, state, base, time_s=0.4, events_enabled=True)
    assert actual.valid
    exact_tree(actual.effective_control, expected.effective_control)
    record = independent(spec, binding, state, base, 0.4, True, actual)
    evidence(
        "topology-" + topology, dict(cases=[record], host_controls_exact=True, biological_cases=0)
    )
