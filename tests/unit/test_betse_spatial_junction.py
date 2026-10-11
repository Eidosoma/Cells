"""Dynamic junctions with spatial pumps/channels: native, device and replay checks."""

import copy
import json
import os
import subprocess
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.core.betse_spatial_spec import definition_arrays
from cells.core.specs import parse_spec
from cells.numerics import betse_active as active
from cells.numerics import betse_junction as model
from cells.processes import junction_gate
from tests.unit import test_betse_spatial_active as previous
from tests.unit.test_betse_tissue_contact import load_capture
from validation.betse.junction_gate.reference import rates as decimal_rates
from validation.betse.spatial_active import junction_reference as independent
from validation.betse.spatial_active import junctions

common = previous.short
BACKEND, EVIDENCE = common.BACKEND, common.EVIDENCE
PROTOCOL, TOL = junctions.protocol(), previous.TOL
CASES = [(c["id"], i) for c in PROTOCOL["cases"] for i in (0, 1)]
RUN, MAPPED = jax.jit(model.trajectory), jax.jit(model.trajectories)


@pytest.fixture(scope="module")
def prior():
    return junctions.baseline()


def test_junction_prerequisite(prior):
    common.evidence("junction-prerequisite", prior)


@pytest.fixture(scope="module")
def device():
    jax.config.update("jax_enable_x64", True)
    return jax.devices(BACKEND)[0]


@pytest.fixture(scope="module")
def example():
    data = json.loads((junctions.ROOT / "configs/betse_spatial_active.json").read_text())
    initial, p = definition_arrays(parse_spec(data).model)
    ones = np.ones_like(p.pump_available)
    layout = model.validate_layout(
        model.Layout(
            p,
            junction_gate.Parameters(
                ones * PROTOCOL["junction"]["threshold_voltage_V"],
                ones * PROTOCOL["junction"]["minimum_open_fraction"],
            ),
            p.tissue.junction_open.copy(),
            np.flatnonzero(p.tissue.moving),
        )
    )
    return model.initial_state(initial, layout, ones * PROTOCOL["junction"]["initial_open"]), layout


def test_host_junction_protocol_and_resources(example):
    assert PROTOCOL["tolerances"] == previous.PROTOCOL["tolerances"]
    assert PROTOCOL["native_update_tolerances"] == previous.PROTOCOL["native_update_tolerances"]
    assert PROTOCOL["duration_s"] == 64e-6 and PROTOCOL["native_steps_s"] == [1e-6, 0.5e-6]
    assert not PROTOCOL["automatic_followup"] and len(CASES) == 12
    initial, layout = example
    patches = layout.junction_block.size
    control = model.Control(*(np.ones(patches) for _ in range(3)))
    _, rates, valid = model.step(initial, layout, 1e-6, control, xp=np)
    assert valid
    fields = common.model.field(initial.active.tissue, layout.active.tissue, xp=np)
    retained_per_step = sum(v.nbytes for v in jax.tree.leaves((initial, rates, fields)))
    plans = []
    for case in PROTOCOL["cases"]:
        for dt in PROTOCOL["native_steps_s"]:
            steps = round(PROTOCOL["duration_s"] / dt)
            controls = junctions.controls(case, dt, steps, patches)
            assert all(v.shape == (steps, patches) for v in controls)
            # States, rates, field readouts and controls, with three host/device copies.
            estimate = 3 * ((steps + 1) * retained_per_step + sum(v.nbytes for v in controls))
            plans.append(
                dict(case=case["id"], dt_s=dt, steps=steps, estimated_array_bytes=estimate)
            )
    total = sum(p["estimated_array_bytes"] for p in plans)
    assert total < PROTOCOL["resources"]["max_retained_array_estimate_bytes"]
    common.evidence(
        "junction-resources",
        dict(
            status="passed",
            plans=plans,
            total_array_estimate_bytes=total,
            scope="Retained-array estimate; compiler/process memory is bounded separately",
        ),
    )


@pytest.mark.parametrize("block", [0.0, 0.5, 1.0])
def test_host_junction_decimal_clock_and_block(block):
    voltage = np.array([-0.12, -0.04, 0.0, 0.04, 0.12])
    parameters = junction_gate.Parameters(np.full(5, 0.015), np.full(5, 0.1))
    a, b = decimal_rates(voltage, 0.015)
    expected = np.full(5, 0.35)
    actual = expected.copy()
    dt = 1e-6
    first = None
    for _ in range(3):
        expected = block * ((expected + dt * (a + 0.1 * b)) / (1 + dt * (a + b)))
        actual = model.gate_step(actual, voltage, block, dt, parameters, xp=np)
        np.testing.assert_allclose(actual, expected, atol=TOL["gate_atol"], rtol=TOL["gate_rtol"])
        if first is None:
            first = actual.copy()
    if block:
        assert np.max(abs(actual - first)) > 1e-7
    else:
        np.testing.assert_array_equal(actual, 0)


@pytest.mark.parametrize(
    "fault",
    [
        "duplicate",
        "missing",
        "float_order",
        "threshold",
        "minimum",
        "block",
        "asymmetric",
        "fractional_mask",
    ],
)
def test_host_junction_bad_layout(example, fault):
    _, layout = copy.deepcopy(example)
    if fault == "duplicate":
        layout.moving_order[1] = layout.moving_order[0]
    elif fault == "missing":
        layout = layout._replace(moving_order=layout.moving_order[:-1])
    elif fault == "float_order":
        layout = layout._replace(moving_order=layout.moving_order.astype(float))
    elif fault in ("threshold", "minimum"):
        layout.junction[0 if fault == "threshold" else 1][0] = -0.1
    elif fault == "block":
        layout.junction_block[0] = np.nan
    elif fault == "asymmetric":
        i = np.flatnonzero(layout.active.tissue.partner != np.arange(layout.junction_block.size))[0]
        layout.junction_block[i] = 0.25
    else:
        layout.active.tissue.junction_open[:] = 0.5
    with pytest.raises(ValueError):
        model.validate_layout(layout)


@pytest.mark.parametrize(
    "fault",
    [
        "negative_gate",
        "nan_gate",
        "above_one",
        "asymmetric_gate",
        "bad_control",
        "asymmetric_control",
        "negative_dt",
        "voltage",
    ],
)
def test_host_junction_invalid_trial_retains_state(example, fault):
    state, p = copy.deepcopy(example)
    control = model.Control(*(np.ones(p.junction_block.size) for _ in range(3)))
    dt = 1e-6
    if fault in ("negative_gate", "nan_gate", "above_one"):
        state.junction_open[0] = {"negative_gate": -0.1, "nan_gate": np.nan, "above_one": 1.1}[
            fault
        ]
    elif fault in ("asymmetric_gate", "asymmetric_control"):
        i = np.flatnonzero(p.active.tissue.partner != np.arange(p.junction_block.size))[0]
        (state.junction_open if fault == "asymmetric_gate" else control.junction)[i] = 0.25
    elif fault == "bad_control":
        control.junction[:] = -0.5
    elif fault == "negative_dt":
        dt = -dt
    else:
        # Opposing large surface potentials exceed the declared transjunction domain.
        p.active.tissue.boundary_values[:, 0] = -1
        p.active.tissue.boundary_values[:, -1] = 1
    result, _, valid = model.step(state, p, dt, control, xp=np)
    assert not valid
    common.bits(result, state)


def test_compiled_junction_smoke_and_static_transport_limit(example, device):
    state, p = example
    case = PROTOCOL["cases"][0]
    controls = junctions.controls(case, 1e-6, 4, p.junction_block.size)
    expected = state
    for i in range(4):
        expected, _, valid = model.step(
            expected, p, 1e-6, jax.tree.map(lambda v, i=i: v[i], controls), xp=np
        )
        assert valid
    final, (_, _, accepted), valid = common.selected(
        RUN, (state, p, np.asarray(1e-6), controls), device
    )
    assert valid and accepted.all()
    for a, b in zip(jax.tree.leaves(final), jax.tree.leaves(expected), strict=True):
        np.testing.assert_allclose(a, b, atol=2e-12, rtol=2e-12)
    blocked = p.active._replace(
        tissue=p.active.tissue._replace(
            junction_permeability=np.zeros_like(p.active.tissue.junction_permeability)
        )
    )
    controls = model.Control(*(np.ones(p.junction_block.size) for _ in range(3)))
    previous_state, _, good = active.step(state.active, blocked, 1e-6, xp=np)
    actual, _, valid = model.step(state, p._replace(active=blocked), 1e-6, controls, xp=np)
    assert valid and good
    common.bits(actual.active, previous_state)


@pytest.fixture(scope="module")
def captured(prior, tmp_path_factory):
    assert prior["status"] == "passed"
    if BACKEND == "gpu":
        assert EVIDENCE
        path = Path(EVIDENCE) / "cpu/junction-native"
    else:
        root = Path(EVIDENCE) / "cpu" if EVIDENCE else tmp_path_factory.mktemp("junction-native")
        root.mkdir(parents=True, exist_ok=True)
        path = root / "junction-native"
        with (
            (root / "junction-native.stdout.log").open("x") as out,
            (root / "junction-native.stderr.log").open("x") as err,
        ):
            subprocess.run(
                [
                    "/mnt/workspaces/Cells/venv-betse/bin/python",
                    "-B",
                    str(junctions.PROTOCOL_PATH.with_name("junction_native.py")),
                    "--output",
                    str(path),
                    "--protocol",
                    str(junctions.PROTOCOL_PATH),
                ],
                check=True,
                timeout=PROTOCOL["resources"]["native_timeout_seconds"],
                stdout=out,
                stderr=err,
                env=dict(
                    os.environ, MPLBACKEND="Agg", MPLCONFIGDIR=str(root / "matplotlib-junction")
                ),
            )
    rows = load_capture(path, PROTOCOL)
    for case, index in CASES:
        row, trace = rows[f"{case}/step-{index}/observed"]
        bare, _ = rows[f"{case}/step-{index}/bare"]
        for key in (
            "case",
            "dt_s",
            "steps",
            "fixture",
            "geometry",
            "parameters",
            "arrays",
            "species",
            "final",
        ):
            assert row[key] == bare[key], key
        assert trace is not None
        independent.inputs(row, PROTOCOL)
    return rows


@pytest.fixture(scope="module")
def computed(captured, device):
    values = {}
    for case, index in CASES:
        row, trace = captured[f"{case}/step-{index}/observed"]
        initial, layout = junctions.prepare(row, trace, PROTOCOL)
        controls = junctions.controls(
            row["case"], row["dt_s"], row["steps"], layout.junction_block.size
        )
        final, (states, rates, accepted), valid = common.selected(
            RUN, (initial, layout, np.asarray(row["dt_s"]), controls), device
        )
        assert valid and accepted.all()
        fields = common.selected(
            common.FIELDS, (states.active.tissue, layout.active.tissue), device
        )
        observed = common.observed_history(
            states.active.tissue, rates.active.ordinary, fields, layout.active.tissue
        )
        values[(case, index)] = dict(
            row=row,
            trace=trace,
            initial=initial,
            layout=layout,
            controls=controls,
            final=final,
            states=states,
            rates=rates,
            observed=observed,
        )
    return values


def compare(value, states=None):
    states = value["states"] if states is None else states
    return independent.compare(
        value["row"],
        value["trace"],
        TOL,
        states.active.tissue._asdict(),
        {k: v for k, v in states.active._asdict().items() if k != "tissue"},
        {k: v for k, v in value["rates"].active._asdict().items() if k != "ordinary"},
        value["observed"],
        states.junction_open,
        value["rates"].junction_after_ion,
    )


@pytest.mark.parametrize("case,index", CASES)
def test_junction_native_trajectory(case, index, computed):
    value = computed[(case, index)]
    native = independent.native_check(value["row"], value["trace"], PROTOCOL)
    report = compare(value)
    report.update(backend=BACKEND, observer_neutrality="bitwise", native_updates=native)
    common.evidence(
        f"junction-native-{case}-{index}",
        report,
        junctions.arrays(value["states"], value["rates"], value["observed"]),
    )


def test_junction_disk_and_windows(computed, device, tmp_path):
    v = computed[("block_release", 1)]
    cuts = [1, 31, 32, 33, 79, 80, 81, 128]
    for cut in cuts:
        state = jax.tree.map(lambda a, cut=cut: a[cut - 1], v["states"])
        leaves, structure = jax.tree.flatten(state)
        path = tmp_path / f"state-{cut}.npz"
        np.savez_compressed(path, **{f"state_{i}": a for i, a in enumerate(leaves)})
        with np.load(path, allow_pickle=False) as saved:
            restored = jax.tree.unflatten(
                structure, [saved[f"state_{i}"] for i in range(len(leaves))]
            )
        common.bits(restored, state)
        final, (suffix, _, accepted), valid = common.selected(
            RUN,
            (
                restored,
                v["layout"],
                np.asarray(v["row"]["dt_s"]),
                jax.tree.map(lambda a, cut=cut: a[cut:], v["controls"]),
            ),
            device,
        )
        assert valid and accepted.all()
        common.bits(final, v["final"])
        common.bits(suffix, jax.tree.map(lambda a, cut=cut: a[cut:], v["states"]))
    for begin, width in ((0, 13), (32, 37)):
        state = (
            v["initial"]
            if begin == 0
            else jax.tree.map(lambda a, begin=begin: a[begin - 1], v["states"])
        )
        for lo in range(begin, 128, width):
            hi = min(lo + width, 128)
            state, (piece, _, accepted), valid = common.selected(
                RUN,
                (
                    state,
                    v["layout"],
                    np.asarray(v["row"]["dt_s"]),
                    jax.tree.map(lambda a, lo=lo, hi=hi: a[lo:hi], v["controls"]),
                ),
                device,
            )
            assert valid and accepted.all()
            common.bits(piece, jax.tree.map(lambda a, lo=lo, hi=hi: a[lo:hi], v["states"]))
        common.bits(state, v["final"])
    common.evidence(
        "junction-replay",
        dict(
            status="passed",
            state_arrays=14,
            comparison="bitwise",
            checkpoint_steps=cuts,
            windows=[13, 37],
            terminal=True,
            scope="Complete numerical state; ordinary registry integration is separate",
        ),
    )


def test_junction_worlds(computed, device):
    keys = [("coupled", 1), ("half_block", 1), ("block_release", 1)]

    def execute(selected):
        values = [computed[k] for k in selected]
        batch = [
            jax.tree.map(lambda *a: np.stack(a), *(v[name] for v in values))
            for name in ("initial", "layout", "controls")
        ]
        return common.selected(MAPPED, (batch[0], batch[1], np.asarray(0.5e-6), batch[2]), device)

    full = execute(keys)
    assert full[2].all() and full[1][2].all()
    for i, key in enumerate(keys):
        common.bits(jax.tree.map(lambda a, i=i: a[i], full[0]), computed[key]["final"])
        common.bits(jax.tree.map(lambda a, i=i: a[i], full[1][0]), computed[key]["states"])
    reverse = execute(keys[::-1])
    common.bits(jax.tree.map(lambda a: a[::-1], reverse), full)
    for i, key in enumerate(keys):
        single = execute([key])
        common.bits(jax.tree.map(lambda a: a[0], single), jax.tree.map(lambda a, i=i: a[i], full))
    common.evidence(
        "junction-worlds",
        dict(
            status="passed",
            worlds=3,
            comparison="bitwise",
            reordered=True,
            partitioned=True,
            distinct_input_schedules=True,
        ),
    )


def test_junction_effects(computed):
    for index in (0, 1):
        value = computed[("block_release", index)]
        controls = value["controls"].junction
        zero = controls[:, 0] == 0
        assert zero.any()
        np.testing.assert_array_equal(value["states"].junction_open[zero], 0)
        np.testing.assert_array_equal(
            value["rates"].active.ordinary.junction_outward_fmol_s[zero], 0
        )
        release = round(40e-6 / value["row"]["dt_s"])
        assert np.any(value["states"].junction_open[release] > 0)
        assert np.any(value["rates"].active.ordinary.junction_outward_fmol_s[release] != 0)
        isolated = computed[("disconnected", index)]
        np.testing.assert_array_equal(isolated["states"].junction_open, 0)
        np.testing.assert_array_equal(isolated["rates"].active.ordinary.junction_outward_fmol_s, 0)
        coupled = computed[("coupled", index)]
        half = computed[("half_block", index)]
        assert np.max(half["states"].junction_open[-1]) < np.max(
            coupled["states"].junction_open[-1]
        )
        reversed_case = computed[("reversed", index)]
        assert not np.array_equal(
            coupled["rates"].active.ordinary.junction_outward_fmol_s[0],
            reversed_case["rates"].active.ordinary.junction_outward_fmol_s[0],
        )
        single = computed[("single_pair", index)]
        blocked = single["layout"].junction_block == 0
        np.testing.assert_array_equal(
            single["rates"].active.ordinary.junction_outward_fmol_s[:, :, blocked], 0
        )
    common.evidence(
        "junction-effects",
        dict(
            status="passed",
            blocked_transport_zero=True,
            blocking_changes_stored_gate=True,
            release_evolves_from_zero=True,
            ion_order_changes_transport=True,
            isolated_and_single_pair_controls=True,
            scope="Native source semantics; not a physical-time or biological recovery claim",
        ),
    )


def test_junction_negative_controls(computed):
    value = computed[("block_release", 1)]
    row = copy.deepcopy(value["row"])
    row["fixture"]["junction_inputs"]["steps"][32]["event_index"] = 0
    with pytest.raises(AssertionError):
        independent.inputs(row, PROTOCOL)
    corrupt = jax.tree.map(np.copy, value["states"])
    corrupt.junction_open[-1, 0] += 1e-4
    with pytest.raises(AssertionError):
        compare(value, corrupt)
    corrupt = jax.tree.map(np.copy, value["states"])
    corrupt.active.tissue.junction_outward_fmol[-1, 0, 0] += 1e-6
    with pytest.raises(AssertionError):
        compare(value, corrupt)
    trace = {k: v.copy() for k, v in value["trace"].items()}
    first = np.flatnonzero((trace["method"] == 0) & trace["after"])[0]
    trace["gjopen"][first] = trace["gjopen"][first - 1]
    with pytest.raises(AssertionError):
        independent.native_check(value["row"], trace, PROTOCOL)
    common.evidence(
        "junction-negative-controls",
        dict(
            status="passed",
            stale_input_rejected=True,
            missing_per_ion_gate_update_rejected=True,
            gate_corruption_rejected=True,
            material_corruption_fmol=1e-6,
        ),
    )


def test_junction_cpu_gpu(computed):
    if BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved dynamic junction CPU histories")
    count = 0
    for (case, index), value in computed.items():
        actual = junctions.arrays(value["states"], value["rates"], value["observed"])
        with np.load(
            Path(EVIDENCE) / f"cpu/junction-native-{case}-{index}.npz", allow_pickle=False
        ) as saved:
            assert set(actual) == set(saved)
            ordinary = {k: v for k, v in actual.items() if not k.startswith("junction__")}
            count += previous.compare_cpu_gpu_arrays(
                ordinary,
                {k: saved[k] for k in ordinary},
                value["layout"].active.tissue.membrane_area,
            )
            for name in ("junction__open", "junction__after_ion"):
                assert actual[name].shape == saved[name].shape
                np.testing.assert_allclose(
                    actual[name], saved[name], atol=TOL["gate_atol"], rtol=TOL["gate_rtol"]
                )
                count += actual[name].size
    common.evidence("junction-cpu-gpu", dict(status="passed", compared_scalars=count))
