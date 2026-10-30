"""Captured global setter arithmetic, independent expressions and device batches."""

import copy
import json
import os
from dataclasses import replace
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.processes import betse_global_controls as controls
from validation.perturbations import global_controls_native as native
from validation.perturbations import global_controls_reference as reference

TIMES = [-0.1, 0.0, 0.2, 0.6, 1.2, 1.7]
NAMES = (
    "all",
    "temperature",
    "cooling",
    "nonphysical",
    "junction",
    "empty",
    "pump",
    "voltage",
    "same",
    "equal",
)


def program(name="all", positive="top", negative="bottom"):
    rows = [
        controls.Event("temperature", 0.2, 1.2, 0.3, amplitude=0.15),
        controls.Event("junction_block", 0.2, 1.2, 0.3, target_ids=("m2", "m0")),
        controls.Event("pump_block", 0.2, 1.2, 0.3),
        controls.Event(
            "voltage",
            0.2,
            1.2,
            0.3,
            amplitude=-0.08,
            positive_boundary=positive,
            negative_boundary=negative,
        ),
    ]
    if name in ("temperature", "cooling", "nonphysical"):
        rows = [
            replace(
                rows[0],
                amplitude={"temperature": 0.15, "cooling": -0.25, "nonphysical": -3.0}[name],
            )
        ]
    elif name in ("junction", "empty"):
        rows = [replace(rows[1], target_ids=() if name == "empty" else rows[1].target_ids)]
    elif name == "pump":
        rows = [rows[2]]
    elif name in ("voltage", "same", "equal"):
        rows = [
            replace(
                rows[3],
                negative_boundary=positive if name == "same" else negative,
                off_s=0.2 if name == "equal" else 1.2,
            )
        ]
    return controls.bind(
        membrane_ids=("m0", "m1", "m2"),
        events=tuple(reversed(rows)),
        provenance="Manufactured explicit controls; no heat or electrode-work law",
    )


def state():
    return controls.State(
        np.asarray(307.0),
        np.array([0.4, 0.7, 0.9]),
        np.asarray(0.6),
        np.array([0.02, -0.03, 0.01, -0.01]),
    )


def plain(state):
    return {k: np.asarray(v).tolist() for k, v in state._asdict().items()}


def evidence(name, value):
    if path := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(path) / "global-controls"
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / (name + ".json")).open("x") as stream:
            json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")


def compare(actual, expected):
    maximum = 0.0
    for key, value in actual._asdict().items():
        wanted = np.asarray(expected[key])
        scale = np.maximum(1.0, np.abs(wanted))
        maximum = max(
            maximum,
            float(
                np.max(
                    np.abs(np.asarray(value) - wanted) / (64 * np.finfo(float).eps * scale),
                    initial=0,
                )
            ),
        )
    assert maximum <= 1, maximum
    return maximum


def one(prepared, current, time, base=293.0, enabled=True, *, output=None):
    saved, initial = controls.record(prepared), plain(current)
    answer = (
        controls.apply(
            current,
            controls.compile_program(prepared),
            np.asarray(time),
            np.asarray(base),
            enabled,
            xp=np,
        )
        if output is None
        else output
    )
    wanted = reference.evaluate(saved, initial, time, base, events_enabled=enabled)
    source = native.evaluate(saved, initial, time, base, events_enabled=enabled)
    if output is None:
        for key, value in answer.state._asdict().items():
            np.testing.assert_array_equal(value, source[key])
    assert answer.finite
    return dict(
        parameters=saved,
        initial=initial,
        time_s=time,
        original_temperature_K=base,
        events_enabled=enabled,
        actual=plain(answer.state),
        reference=wanted,
        source=source,
        maximum_error_fraction=compare(answer.state, wanted),
        physical_domain=bool(answer.physical_domain),
    )


@pytest.mark.parametrize("name", NAMES)
def test_exact_native_setters_and_independent_expressions(name):
    prepared = program(name)
    records = [one(prepared, state(), time) for time in TIMES]
    evidence(name, dict(records=records, source_sha256=native.PINNED, biological_cases=0))
    if name == "nonphysical":
        assert not records[3]["physical_domain"] and records[3]["actual"]["temperature_K"] < 0
    if name == "equal":
        assert records[3]["actual"]["boundary_voltage_V"][:2] == [0.0, 0.0]


@pytest.mark.parametrize("positive", controls.SIDES)
@pytest.mark.parametrize("negative", controls.SIDES)
def test_voltage_all_boundary_pairs_and_ordered_same_side_write(positive, negative):
    prepared = program("voltage", positive, negative)
    row = one(prepared, state(), 0.6)
    if positive == negative:
        assert row["actual"]["boundary_voltage_V"][controls.SIDES.index(positive)] > 0
    evidence(
        "boundaries-" + positive + "-" + negative, dict(records=[row], source_sha256=native.PINNED)
    )


def test_disabled_call_and_disabled_events_preserve_complete_state_without_draws(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Global setter sampled randomness")

    monkeypatch.setattr(np.random, "random", forbidden)
    result = one(program(), state(), 0.6, enabled=False)
    assert result["actual"] == result["initial"]
    empty = controls.bind(membrane_ids=(), events=(), provenance="Empty control program")
    current = state()._replace(junction_available=np.empty(0))
    output = controls.apply(
        current, controls.compile_program(empty), np.asarray(0.6), np.asarray(293.0), True, xp=np
    )
    assert plain(output.state) == plain(current) and output.physical_domain


def test_carried_state_and_saved_program_use_original_temperature_without_accumulation():
    prepared, current = program(), state()
    restored = controls.restore(
        json.loads(json.dumps(controls.record(prepared))), expected_identity=prepared.identity
    )
    records = []
    for time in TIMES:
        row = one(restored, current, time)
        records.append(row)
        current = controls.State(
            *(np.asarray(row["actual"][key]) for key in controls.State._fields)
        )
    repeated = one(restored, current, TIMES[-1])
    assert repeated["actual"] == records[-1]["actual"]
    assert all(row["actual"]["junction_available"][1] == 0.7 for row in records)
    evidence(
        "carried-controls",
        dict(
            records=records,
            source_sha256=native.PINNED,
            scope="Setter history only; no tissue integration",
        ),
    )


@pytest.mark.parametrize(
    "defect", ("owner", "target", "time", "amplitude", "boundary", "identity", "missing", "extra")
)
def test_saved_control_program_cannot_be_reassociated(defect):
    prepared = program()
    saved = copy.deepcopy(controls.record(prepared))
    if defect == "owner":
        saved["membrane_ids"][0] = "other"
    elif defect == "target":
        saved["events"][1]["target_ids"] = ["m1"]
    elif defect == "time":
        saved["events"][0]["off_s"] += 1.0
    elif defect == "amplitude":
        saved["events"][0]["amplitude"] += 1.0
    elif defect == "boundary":
        saved["events"][-1]["positive_boundary"] = "left"
    elif defect == "identity":
        saved["identity"] = "0" * 64
    elif defect == "missing":
        saved.pop("events")
    else:
        saved["implicit_phase"] = "SIM"
    with pytest.raises(ValueError):
        controls.restore(saved, expected_identity=prepared.identity)


@pytest.mark.parametrize(
    "defect",
    (
        "width_zero",
        "width_negative",
        "times",
        "unknown_target",
        "unused_amplitude",
        "side",
        "duplicate",
    ),
)
def test_binding_refuses_undefined_or_ambiguous_programs(defect):
    prepared = program()
    rows = list(prepared.events)
    if defect == "width_zero":
        rows[0] = replace(rows[0], change_s=0.0)
    elif defect == "width_negative":
        rows[0] = replace(rows[0], change_s=-1.0)
    elif defect == "times":
        rows[0] = replace(rows[0], on_s=2.0)
    elif defect == "unknown_target":
        rows[1] = replace(rows[1], target_ids=("missing",))
    elif defect == "unused_amplitude":
        rows[2] = replace(rows[2], amplitude=2.0)
    elif defect == "side":
        rows[3] = replace(rows[3], positive_boundary="TOP")
    else:
        rows = [rows[0], rows[0]]
    with pytest.raises(ValueError):
        controls.bind(
            membrane_ids=prepared.membrane_ids, events=rows, provenance=prepared.provenance
        )


def test_actual_voltage_constructor_retains_native_setup_failure():
    saved = controls.record(program("voltage"))
    saved["events"][0]["change_s"] = 0.0
    with pytest.raises(ZeroDivisionError):
        native.evaluate(saved, plain(state()), 0.6, 293.0)
    saved["events"][0].update(change_s=0.3, on_s=2.0)
    with pytest.raises(native.NativeEventError):
        native.evaluate(saved, plain(state()), 0.6, 293.0)
    evidence(
        "native-setup-failures",
        dict(
            zero_width="ZeroDivisionError at fire",
            reversed_times="NativeEventError at initialization",
            source_sha256=native.PINNED,
        ),
    )


def test_saturated_exponent_is_distinct_from_nonfinite_argument_or_bad_domain():
    prepared = program()
    kernel = controls.compile_program(prepared)
    with np.errstate(all="ignore"):
        saturated = controls.apply(
            state(), kernel, np.asarray(-1000.0), np.asarray(293.0), True, xp=np
        )
        bad = controls.apply(state(), kernel, np.asarray(np.inf), np.asarray(293.0), True, xp=np)
        baseline = controls.apply(
            state(),
            kernel._replace(temperature_multiplier=np.asarray(-3.0)),
            np.asarray(0.6),
            np.asarray(-293.0),
            True,
            xp=np,
        )
    assert saturated.finite and saturated.exponential_saturated.all()
    assert not bad.finite and not bad.physical_domain
    assert baseline.finite and baseline.state.temperature_K > 0 and not baseline.physical_domain


@pytest.mark.parametrize("dtype", (np.float32, np.int64, np.bool_))
def test_requires_explicit_float64(dtype):
    with pytest.raises(ValueError, match="float64"):
        controls.apply(
            state(),
            controls.compile_program(program()),
            np.asarray(1, dtype=dtype),
            np.asarray(293.0),
            True,
            xp=np,
        )


@pytest.mark.parametrize("defect", ("side", "mask", "state_axis", "enabled"))
def test_kernel_axes_and_dynamic_index_diagnostics(defect):
    kernel, current, enabled = controls.compile_program(program()), state(), True
    if defect == "side":
        kernel = kernel._replace(positive_index=np.asarray(8, dtype=np.int64))
        result = controls.apply(current, kernel, np.asarray(0.6), np.asarray(293.0), enabled, xp=np)
        assert not result.finite
        return
    if defect == "mask":
        kernel = kernel._replace(junction_mask=np.ones(3, dtype=np.int64))
    elif defect == "state_axis":
        current = current._replace(boundary_voltage_V=np.zeros(3))
    else:
        enabled = 1
    with pytest.raises(ValueError):
        controls.apply(current, kernel, np.asarray(0.6), np.asarray(293.0), enabled, xp=np)


def test_cpu_jax_full_setter_batches_and_invalid_world_isolation():
    assert jax.default_backend() == "cpu" and jax.config.jax_enable_x64
    programs = [program(), program("same")]

    def stacked(*items):
        return jax.tree.map(lambda *values: jnp.stack(values), *items)

    states = stacked(state(), state())
    kernels = stacked(*(controls.compile_program(p) for p in programs))
    run = jax.jit(jax.vmap(controls.apply))
    times, base, enabled = jnp.array([0.4, 0.7]), jnp.array([293.0, 300.0]), jnp.array([True, True])
    outputs = run(states, kernels, times, base, enabled)
    records = []
    for i, prepared in enumerate(programs):
        output = jax.tree.map(lambda a, index=i: np.asarray(a[index]), outputs)
        records.append(one(prepared, state(), float(times[i]), float(base[i]), output=output))
    invalid = run(states, kernels, times.at[0].set(jnp.inf), base, enabled)
    np.testing.assert_array_equal(invalid.finite, [False, True])
    for a, b in zip(invalid.state, outputs.state, strict=True):
        np.testing.assert_array_equal(a[1], b[1])
    evidence(
        "cpu-jax-batch",
        dict(
            records=records,
            source_sha256=native.PINNED,
            invalid_world_isolated=True,
            biological_cases=0,
        ),
    )


def test_cpu_jax_disabled_call_ignores_unused_bad_parameters():
    kernel = controls.compile_program(program())
    kernel = kernel._replace(change_s=jnp.zeros(4), positive_index=jnp.asarray(99, dtype=jnp.int64))
    run = jax.jit(controls.apply)
    output = run(state(), kernel, jnp.asarray(jnp.inf), jnp.asarray(jnp.nan), False)
    assert output.finite and output.physical_domain
    assert plain(output.state) == plain(state())
