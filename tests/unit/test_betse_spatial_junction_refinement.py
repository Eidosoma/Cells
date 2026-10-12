"""Long native junction trajectories, refinement and complete array replay."""

import copy
import os
import subprocess
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.numerics import betse_junction as model
from cells.processes import junction_gate
from tests.unit import test_betse_spatial_active_refinement as temporal
from tests.unit import test_betse_spatial_junction as short
from tests.unit.test_betse_tissue_contact import load_capture
from validation.betse.junction_gate.reference import rates as decimal_rates
from validation.betse.spatial_active import junction_reference as independent
from validation.betse.spatial_active import junction_refinement as long
from validation.betse.spatial_active import junctions

common, previous = short.common, short.previous
BACKEND, EVIDENCE, TOL = short.BACKEND, short.EVIDENCE, short.TOL
PROTOCOL = long.protocol()
CASES = [(c["id"], i) for c in PROTOCOL["cases"] for i in range(3)]
RUN, MAPPED = short.RUN, short.MAPPED
device, example = short.device, short.example


@pytest.fixture(scope="module")
def prior():
    return long.baseline()


def test_long_junction_prerequisite(prior):
    common.evidence("long-junction-prerequisite", prior)


def test_host_long_junction_protocol_and_resources(example):
    for name in (
        "cases",
        "junction",
        "tolerances",
        "native_update_tolerances",
        "species",
        "initial_gate",
        "pump_parameters",
        "temperature_K",
        "gj_surface_fraction",
        "initial_voltage_extent_V",
        "base_concentration_mM",
        "outside_mM",
        "concentration_gradient_mM",
    ):
        assert PROTOCOL[name] == short.PROTOCOL[name], name
    assert PROTOCOL["duration_s"] == 4 * short.PROTOCOL["duration_s"] == 256e-6
    assert PROTOCOL["native_steps_s"] == [1e-6, 0.5e-6, 0.25e-6]
    for name in ("resolved_error_multiple", "ratio_min", "ratio_max"):
        assert PROTOCOL["refinement"][name] == temporal.PROTOCOL["refinement"][name]
    eligible = [c["id"] for c in PROTOCOL["cases"] if c["id"] != "half_block"]
    assert PROTOCOL["refinement"]["cases"] == eligible
    assert PROTOCOL["refinement"]["required_resolved_final_fields"] == {
        c: ["vm", "m_gate"] for c in eligible
    }
    assert PROTOCOL["refinement"]["required_resolved_junction_cases"] == [
        c for c in eligible if c != "disconnected"
    ]
    assert PROTOCOL["step_sensitivity"]["cases"] == ["half_block"]
    assert PROTOCOL["step_sensitivity"]["updates_per_outer_step"] == 3
    assert not PROTOCOL["allowed_prior_source_changes"]
    assert PROTOCOL["automatic_followup"] is False and len(CASES) == 18
    initial, layout = example
    patches = layout.junction_block.size
    control = model.Control(*(np.ones(patches) for _ in range(3)))
    _, rates, valid = model.step(initial, layout, 0.25e-6, control, xp=np)
    assert valid
    fields = common.model.field(initial.active.tissue, layout.active.tissue, xp=np)
    retained_per_step = sum(v.nbytes for v in jax.tree.leaves((initial, rates, fields)))
    plans = []
    for case in PROTOCOL["cases"]:
        for dt in PROTOCOL["native_steps_s"]:
            steps = round(PROTOCOL["duration_s"] / dt)
            controls = junctions.controls(case, dt, steps, patches)
            assert all(v.shape == (steps, patches) for v in controls)
            estimate = 3 * ((steps + 1) * retained_per_step + sum(v.nbytes for v in controls))
            plans.append(
                dict(case=case["id"], dt_s=dt, steps=steps, estimated_array_bytes=estimate)
            )
    total = sum(p["estimated_array_bytes"] for p in plans)
    limit = PROTOCOL["resources"]["max_retained_array_estimate_bytes"]
    assert total < limit <= PROTOCOL["resources"]["max_worker_rss_bytes"] // 2
    common.evidence(
        "long-junction-resources",
        dict(
            status="passed",
            plans=plans,
            total_array_estimate_bytes=total,
            scope="Retained-array estimate; compiler/process memory is bounded separately",
        ),
    )


def test_host_fractional_block_clock_has_dt_dependent_physical_rate():
    rule, parameters = PROTOCOL["step_sensitivity"], PROTOCOL["junction"]
    voltage = np.asarray([rule["fixed_voltage_V"]])
    alpha, beta = decimal_rates(voltage, parameters["threshold_voltage_V"])
    minimum = parameters["minimum_open_fraction"]
    layout = junction_gate.Parameters(
        np.asarray([parameters["threshold_voltage_V"]]), np.asarray([minimum])
    )
    records = []
    for block in (0.0, rule["block_fraction"], 1.0):
        for dt in PROTOCOL["native_steps_s"]:
            count = rule["updates_per_outer_step"] * round(rule["duration_s"] / dt)
            multiplier = block / (1 + dt * (alpha + beta))
            fixed_point = (
                block * dt * (alpha + minimum * beta) / ((1 - block) + dt * (alpha + beta))
            )
            closed_form = (
                fixed_point + (parameters["initial_open"] - fixed_point) * multiplier**count
            )
            actual = np.asarray([parameters["initial_open"]])
            for _ in range(count):
                actual = model.gate_step(actual, voltage, block, dt, layout, xp=np)
            np.testing.assert_allclose(
                actual, closed_form, atol=TOL["gate_atol"], rtol=TOL["gate_rtol"]
            )
            records.append(dict(block=block, dt_s=dt, updates=count, final_open=float(actual[0])))
    partial = [r["final_open"] for r in records if r["block"] == rule["block_fraction"]]
    assert partial[0] > partial[1] > partial[2] > 0
    assert rule["block_fraction"] == 0.5
    common.evidence(
        "long-junction-fixed-voltage-block-clock",
        dict(
            status="passed",
            records=records,
            recurrence=(
                "g_next = block * (g + dt * (alpha + minimum * beta)) / (1 + dt * (alpha + beta))"
            ),
            pure_block_decay_rate_per_s=[3 * np.log(2) / dt for dt in PROTOCOL["native_steps_s"]],
            scope="Constant-voltage closed-form recurrence; partial block is prescribed per update",
        ),
    )


def synthetic_series():
    rule, values = temporal.synthetic_series()
    rule["refinement"].update(cases=["coupled"], required_resolved_junction_cases=["coupled"])
    for dt, value in zip(rule["native_steps_s"], values, strict=True):
        value["junction_open"] = np.full((round(rule["duration_s"] / dt), 2), 0.2 + 0.01 * dt)
    return rule, values


def test_host_junction_refinement_resolves_shared_state():
    rule, values = synthetic_series()
    report = long.check("coupled", values, np.ones(2), rule)
    for checkpoint in report["checkpoints"]:
        assert all(
            v["first_order_resolved"] and v["ratio"] == pytest.approx(2)
            for v in checkpoint["fields"].values()
        )


@pytest.mark.parametrize(
    "fault",
    [
        "fractional_block",
        "unresolved",
        "nonfinite",
        "wrong_order",
        "worse",
        "truncated",
        "shape",
        "domain",
    ],
)
def test_host_junction_refinement_rejects_false_claims(fault):
    rule, values = synthetic_series()
    case = "coupled"
    if fault == "fractional_block":
        case = "half_block"
    elif fault == "unresolved":
        for value in values:
            value["junction_open"][:] = 0.2
    elif fault == "nonfinite":
        values[2]["junction_open"][-1, 0] = np.nan
    elif fault == "wrong_order":
        values[2]["junction_open"][:] = 0.201
    elif fault == "worse":
        values[2]["junction_open"][:] = 0.5
    elif fault == "truncated":
        values[2]["junction_open"] = values[2]["junction_open"][:-1]
    elif fault == "shape":
        values[2]["junction_open"] = values[2]["junction_open"][:, :1]
    else:
        values[2]["junction_open"][0, 0] = -0.1
    with pytest.raises(AssertionError):
        long.check(case, values, np.ones(2), rule)


def test_compiled_quarter_step_junction_smoke(example, device):
    state, layout = example
    case = dict(
        PROTOCOL["cases"][0],
        junction_changes=[
            dict(time_s=0.0, fraction=1.0),
            dict(time_s=2e-6, fraction=0.0),
            dict(time_s=4e-6, fraction=1.0),
        ],
    )
    dt = 0.25e-6
    controls = junctions.controls(case, dt, 24, layout.junction_block.size)
    expected = state
    for i in range(24):
        expected, _, valid = model.step(
            expected, layout, dt, jax.tree.map(lambda a, i=i: a[i], controls), xp=np
        )
        assert valid
    final, (states, rates, accepted), valid = common.selected(
        RUN, (state, layout, np.asarray(dt), controls), device
    )
    assert valid and accepted.all()
    for a, b in zip(jax.tree.leaves(final), jax.tree.leaves(expected), strict=True):
        np.testing.assert_allclose(a, b, atol=2e-12, rtol=2e-12)
    np.testing.assert_array_equal(states.junction_open[8:16], 0)
    np.testing.assert_array_equal(rates.active.ordinary.junction_outward_fmol_s[8:16], 0)
    assert np.any(states.junction_open[16] > 0)


@pytest.fixture(scope="module")
def captured(prior, tmp_path_factory):
    assert prior["status"] == "passed"
    if BACKEND == "gpu":
        assert EVIDENCE
        path = Path(EVIDENCE) / "cpu/long-junction-native"
    else:
        root = (
            Path(EVIDENCE) / "cpu" if EVIDENCE else tmp_path_factory.mktemp("long-junction-native")
        )
        root.mkdir(parents=True, exist_ok=True)
        path = root / "long-junction-native"
        with (
            (root / "long-junction-native.stdout.log").open("x") as out,
            (root / "long-junction-native.stderr.log").open("x") as err,
        ):
            subprocess.run(
                [
                    "/mnt/workspaces/Cells/venv-betse/bin/python",
                    "-B",
                    str(long.PROTOCOL_PATH.with_name("junction_native.py")),
                    "--output",
                    str(path),
                    "--protocol",
                    str(long.PROTOCOL_PATH),
                ],
                check=True,
                timeout=PROTOCOL["resources"]["native_timeout_seconds"],
                stdout=out,
                stderr=err,
                env=dict(
                    os.environ,
                    MPLBACKEND="Agg",
                    MPLCONFIGDIR=str(root / "matplotlib-long-junction"),
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
        assert row["steps"] == round(PROTOCOL["duration_s"] / row["dt_s"])
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


@pytest.mark.parametrize("case,index", CASES)
def test_long_junction_native_trajectory(case, index, computed):
    value = computed[(case, index)]
    native = independent.native_check(value["row"], value["trace"], PROTOCOL)
    report = short.compare(value)
    report.update(backend=BACKEND, observer_neutrality="bitwise", native_updates=native)
    common.evidence(
        f"long-junction-native-{case}-{index}",
        report,
        junctions.arrays(value["states"], value["rates"], value["observed"]),
    )


def test_long_junction_original_prefixes(prior, computed):
    assert prior["status"] == "passed"
    root = Path(PROTOCOL["prefix_binding"]["root"])
    old = load_capture(root / "evidence/cpu/junction-native", short.PROTOCOL)
    native_count = state_count = readout_count = control_steps = 0
    for case in (c["id"] for c in PROTOCOL["cases"]):
        for index in (0, 1):
            value = computed[(case, index)]
            row, trace = old[f"{case}/step-{index}/observed"]
            assert set(trace) == set(value["trace"])
            for name, expected in trace.items():
                if name == "raw_label_s":
                    continue
                actual = value["trace"][name]
                common.bits(
                    actual if name.startswith("initial_") else actual[: len(expected)], expected
                )
                native_count += expected.size
            before = row["fixture"]["junction_inputs"]["steps"]
            assert value["row"]["fixture"]["junction_inputs"]["steps"][: len(before)] == before
            control_steps += len(before)
            path = root / f"evidence/{BACKEND}/junction-native-{case}-{index}.npz"
            actual = junctions.arrays(value["states"], value["rates"], value["observed"])
            with np.load(path, allow_pickle=False) as saved:
                assert set(saved) == set(actual)
                for name in saved:
                    if not name.startswith("observed__"):
                        common.bits(actual[name][: len(saved[name])], saved[name])
                        state_count += saved[name].size
                names = [n for n in saved if n.startswith("observed__")]
                readout_count += previous.compare_cpu_gpu_arrays(
                    {n: actual[n][: len(saved[n])] for n in names},
                    {n: saved[n] for n in names},
                    value["layout"].active.tissue.membrane_area,
                )
    common.evidence(
        "long-junction-prefix",
        dict(
            status="passed",
            native_scalars=native_count,
            cells_state_and_rate_scalars=state_count,
            derived_readout_scalars=readout_count,
            native_control_steps=control_steps,
            native_and_cells_state_comparison="bitwise",
            raw_linspace_labels_excluded=True,
            derived_readout_comparison="registered_CPU_GPU_tolerances",
            completed_duration_s=64e-6,
        ),
    )


def series(value):
    return temporal.series(
        dict(states=value["states"].active, rates=value["rates"].active, observed=value["observed"])
    ) | {"junction_open": value["states"].junction_open}


@pytest.mark.parametrize("case", PROTOCOL["refinement"]["cases"])
def test_long_junction_temporal_refinement(case, computed):
    values = [computed[(case, i)] for i in range(3)]
    for value in values[1:]:
        common.bits(value["layout"], values[0]["layout"])
        common.bits(value["initial"], values[0]["initial"])
    area = values[0]["layout"].active.tissue.membrane_area
    report = long.check(case, [series(v) for v in values], area, PROTOCOL)
    report["native"] = long.check(
        case, [long.native_series(v["row"], v["trace"]) for v in values], area, PROTOCOL
    )
    report["backend"] = BACKEND
    common.evidence("long-junction-refinement-" + case, report)


def test_long_junction_half_block_step_sensitivity(computed):
    values = [computed[("half_block", i)] for i in range(3)]
    records = {}
    for label, histories in (
        ("cells", [series(v) for v in values]),
        ("native", [long.native_series(v["row"], v["trace"]) for v in values]),
    ):
        records[label] = []
        for time in PROTOCOL["refinement"]["common_completed_times_s"]:
            indices = [round(time / dt) - 1 for dt in PROTOCOL["native_steps_s"]]
            row = dict(completed_time_s=time, fields={})
            for section, name in (
                (None, "junction_open"),
                ("observed", "vm"),
                ("states", "junction_outward_fmol"),
            ):
                arrays = [
                    (history[name] if section is None else history[section][name])[i]
                    for history, i in zip(histories, indices, strict=True)
                ]
                assert len({a.shape for a in arrays}) == 1 and all(
                    np.isfinite(a).all() for a in arrays
                )
                row["fields"][name] = dict(
                    maxima=[float(np.max(abs(a))) for a in arrays],
                    max_absolute_differences=[
                        float(np.max(abs(a - b)))
                        for a, b in zip(arrays[:-1], arrays[1:], strict=True)
                    ],
                )
            records[label].append(row)
        # Persistent step dependence must be visible, independently in both
        # implementations. This is intentionally not a convergence-order test.
        opening = [float(np.max(h["junction_open"][-1])) for h in histories]
        assert opening[0] > opening[1] > opening[2] > 0
    common.evidence(
        "long-junction-step-sensitivity-half_block",
        dict(
            status="passed",
            backend=BACKEND,
            records=records,
            fixed_physical_law_refinement_claim=False,
            scope=PROTOCOL["step_sensitivity"]["claim"],
        ),
    )


def test_long_junction_disk_and_windows(computed, device, tmp_path):
    v = computed[("block_release", 2)]
    cuts = [1, 63, 64, 65, 159, 160, 161, 513, 1024]
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
    for begin, width in ((0, 97), (160, 131)):
        state = (
            v["initial"]
            if begin == 0
            else jax.tree.map(lambda a, begin=begin: a[begin - 1], v["states"])
        )
        for lo in range(begin, 1024, width):
            hi = min(lo + width, 1024)
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
        "long-junction-replay",
        dict(
            status="passed",
            state_arrays=14,
            comparison="bitwise",
            checkpoint_steps=cuts,
            windows=[97, 131],
            terminal=True,
            scope="Complete array state to 256 us; ordinary runtime remains qualified to 64 us",
        ),
    )


def test_long_junction_worlds(computed, device):
    keys = [("coupled", 2), ("half_block", 2), ("block_release", 2)]

    def execute(selected):
        values = [computed[k] for k in selected]
        batch = [
            jax.tree.map(lambda *a: np.stack(a), *(v[name] for v in values))
            for name in ("initial", "layout", "controls")
        ]
        return common.selected(MAPPED, (batch[0], batch[1], np.asarray(0.25e-6), batch[2]), device)

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
        "long-junction-worlds",
        dict(
            status="passed",
            worlds=3,
            comparison="bitwise",
            reordered=True,
            partitioned=True,
            distinct_input_schedules=True,
        ),
    )


def test_long_junction_effects(computed):
    for index in (0, 1, 2):
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
        "long-junction-effects",
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


def test_long_junction_negative_controls(computed):
    value = computed[("block_release", 2)]
    row = copy.deepcopy(value["row"])
    row["fixture"]["junction_inputs"]["steps"][64]["event_index"] = 0
    with pytest.raises(AssertionError):
        independent.inputs(row, PROTOCOL)
    corrupt = jax.tree.map(np.copy, value["states"])
    corrupt.junction_open[-1, 0] += 1e-4
    with pytest.raises(AssertionError):
        short.compare(value, corrupt)
    corrupt = jax.tree.map(np.copy, value["states"])
    corrupt.active.tissue.junction_outward_fmol[-1, 0, 0] += 1e-6
    with pytest.raises(AssertionError):
        short.compare(value, corrupt)
    trace = {k: v.copy() for k, v in value["trace"].items()}
    first = np.flatnonzero((trace["method"] == 0) & trace["after"])[0]
    trace["gjopen"][first] = trace["gjopen"][first - 1]
    with pytest.raises(AssertionError):
        independent.native_check(value["row"], trace, PROTOCOL)
    common.evidence(
        "long-junction-negative-controls",
        dict(
            status="passed",
            stale_input_rejected=True,
            missing_per_ion_gate_update_rejected=True,
            gate_corruption_rejected=True,
            material_corruption_fmol=1e-6,
        ),
    )


def test_long_junction_cpu_gpu(computed):
    if BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved dynamic junction CPU histories")
    count = 0
    for (case, index), value in computed.items():
        actual = junctions.arrays(value["states"], value["rates"], value["observed"])
        with np.load(
            Path(EVIDENCE) / f"cpu/long-junction-native-{case}-{index}.npz", allow_pickle=False
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
    common.evidence("long-junction-cpu-gpu", dict(status="passed", compared_scalars=count))
