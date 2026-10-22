"""Combined ordinary controls against observed/bare pinned BETSE trajectories."""

import copy
import json
import time
import zipfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import jax
import numpy as np
import pytest

from cells.batch_io import load_batch_snapshot, write_batch_snapshot
from cells.core.batch import BatchSpec, WorldSpec, plan_batch, run_batch
from cells.core.batch_windows import iter_batch_windows, plan_batch_windows
from cells.core.betse_junction_spec import definition_arrays
from cells.core.resources import trace_bytes
from cells.core.runner import branch_checkpoint, run, timeline, validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, parse_spec
from cells.core.windows import WindowPolicy, iter_windows
from cells.io import load_snapshot, write_snapshot
from cells.models import betse_junction as model
from cells.numerics import betse_junction as kernel
from tests.unit import test_betse_junction_runtime as previous
from tests.unit.test_windows import assert_windows
from validation.betse.spatial_active import (
    gate_roundoff,
    junction_reference,
    junction_runtime,
    junctions,
    refinement,
)
from validation.betse.spatial_active import mixed_interventions as mixed
from validation.betse.spatial_active import mixed_reference as independent

PROTOCOL = mixed.protocol()
CASES = [(c["id"], i) for c in PROTOCOL["cases"] for i in range(3)]
common = previous.common
BACKEND, EVIDENCE = common.BACKEND, common.EVIDENCE


def definition(case="coupled_block", index=0):
    return mixed.definition(case, index, backend=BACKEND)


def batch_spec():
    rule = PROTOCOL["world_checks"]
    specs = [
        parse_spec(definition(c, i))
        for c, i in zip(rule["cases"], rule["step_indices"], strict=True)
    ]
    for index, duration in enumerate(rule["durations_s"]):
        raw = specs[index].to_dict()
        dt = raw["execution"]["dt"]
        count = round(duration / dt)
        raw["experiment"].update(
            end_time=count * dt,
            observation_times=[i * dt for i in range(count + 1)],
            changes=[c for c in raw["experiment"]["changes"] if c["time"] <= count * dt],
        )
        if rule["cases"][index] == "sham":
            del raw["experiment"]["changes"]
        specs[index] = parse_spec(raw)
    return BatchSpec(
        tuple(WorldSpec(i + 10, s) for i, s in enumerate(specs)),
        4,
        4096,
        PROTOCOL["resources"]["batch_max_working_bytes"],
    )


def test_host_design():
    sources = mixed.source_changes()
    prior_root = Path(PROTOCOL["prior_binding"]["root"])
    accepted = json.loads((prior_root / "component-protocol.json").read_text())
    assert PROTOCOL["prefix_duration_s"] == accepted["duration_s"] == 64e-6
    assert PROTOCOL["duration_s"] == 8 * accepted["duration_s"] == 512e-6
    assert PROTOCOL["native_steps_s"] == accepted["native_steps_s"]
    assert PROTOCOL["template_sha256"] == accepted["template_sha256"]
    assert PROTOCOL["tolerances"] == accepted["tolerances"]
    assert PROTOCOL["gate_comparison"]["policy"] == gate_roundoff.POLICY
    assert PROTOCOL["gate_comparison"]["acceptance_criteria_changed"] is True
    assert PROTOCOL["gate_comparison"]["independent_kinetic_replay_required"] is True
    for current, previous_case in zip(PROTOCOL["cases"], accepted["cases"], strict=True):
        expected = copy.deepcopy(previous_case)
        for name in ("interventions", "junction_changes"):
            expected[name][-1]["time_s"] = PROTOCOL["duration_s"]
        assert current == expected
    assert (
        refinement.digest(mixed.ROOT / PROTOCOL["source_protocol"])
        == PROTOCOL["source_protocol_sha256"]
    )
    old = json.loads((mixed.ROOT / PROTOCOL["source_protocol"]).read_text())
    for key in (
        "species",
        "base_concentration_mM",
        "concentration_gradient_mM",
        "outside_mM",
        "gj_surface_fraction",
        "initial_voltage_extent_V",
        "native_update_tolerances",
        "tolerances",
        "temperature_K",
        "initial_gate",
        "pump_parameters",
        "junction",
    ):
        assert PROTOCOL[key] == old[key], key
    anchor = next(c for c in old["cases"] if c["id"] == "coupled")
    for case in PROTOCOL["cases"]:
        for name in set(case) - {"id", "interventions", "junction_changes"}:
            assert case[name] == anchor[name], name
    retained = transient = native_bytes = 0
    for case, index in CASES:
        spec = parse_spec(definition(case, index))
        assert parse_spec(spec.to_dict()) == spec
        initial, p = definition_arrays(spec.model)
        flat, layout = model.initial_values(spec)
        common.bits(model.unflatten(flat), initial)
        common.bits(model.parameters(spec, layout), p)
        assert len(flat) == 14
        assert model.check_values(flat, spec)["max_material_error_over_budget"] == 0
        grid = timeline(spec)
        values = control_values(spec, grid)
        events = next(c for c in PROTOCOL["cases"] if c["id"] == case)["interventions"]
        for step in range(len(grid)):
            selected = max(
                i for i, e in enumerate(events) if round(e["time_s"] / spec.execution.dt) <= step
            )
            event = events[selected]
            assert event_index(spec, grid[step]) == selected
            owners = p.active.tissue.cell_owner
            for route in ("pump", "channel"):
                expected = [
                    event[route + "_fraction"]
                    if event["target_cells"] == "all" or owner in event["target_cells"]
                    else 1
                    for owner in owners
                ]
                np.testing.assert_array_equal(getattr(values, route)[step], expected)
            np.testing.assert_array_equal(
                values.junction[step], np.full(30, event["junction_fraction"])
            )
            np.testing.assert_array_equal(
                values.junction[step], values.junction[step, p.active.tissue.partner]
            )
        assert np.all(
            values.pump[-1] == 0
        )  # Terminal input exists but has no integration interval.
        retained += 4 * len(grid) * sum(v.nbytes for v in flat)
        transient = max(transient, trace_bytes(spec, len(grid) - 1))
        assert transient <= spec.execution.max_trace_bytes
        path = prior_root / f"evidence/cpu/mixed-native/{case}/step-{index}/observed/trace.npz"
        with zipfile.ZipFile(path) as saved:
            native_bytes = max(native_bytes, 16 * sum(v.file_size for v in saved.infolist()))
    batch = batch_spec()
    planning = [
        plan_batch(batch),
        plan_batch_windows(batch, WindowPolicy(PROTOCOL["world_checks"]["window_steps"])),
    ]
    assert max(p.estimated_working_bytes for p in planning) < batch.max_working_bytes
    assert (
        retained + transient + native_bytes
        < PROTOCOL["resources"]["max_retained_array_estimate_bytes"]
    )
    common.evidence(
        "mixed-design",
        dict(
            status="passed",
            histories=len(CASES),
            timesteps_s=PROTOCOL["native_steps_s"],
            duration_s=PROTOCOL["duration_s"],
            physical_inputs_and_tolerances_unchanged=True,
            retained_state_and_rate_estimate_bytes=retained,
            scalar_working_bytes=transient,
            native_target_and_comparison_estimate_bytes=native_bytes,
            source_checks=sources,
            batch_working_bytes=[p.estimated_working_bytes for p in planning],
            fractional_junction_blocking="per native gate update; dt-dependent inhibition",
        ),
    )


def test_host_input_known_answers(monkeypatch):
    monkeypatch.syspath_prepend(str(mixed.ROOT / "validation/betse/channel_loop_preparation"))
    from validation.betse.spatial_active import mixed_native

    owners = np.array([0, 0, 1, 2, 3, 3, 4, 5, 6])
    base_pump = np.linspace(0.2, 1, len(owners))
    for case in PROTOCOL["cases"]:
        for dt in PROTOCOL["native_steps_s"]:
            channel = SimpleNamespace(maxDm=None)
            phase = SimpleNamespace(
                cells=SimpleNamespace(mem_to_cells=owners),
                p=SimpleNamespace(dt=dt, tm=5e-9, init_tsteps=round(PROTOCOL["duration_s"] / dt)),
                sim=SimpleNamespace(
                    molecules=SimpleNamespace(
                        core=SimpleNamespace(channels={"Kv1p5_spatial": channel})
                    )
                ),
            )
            dynamic = dict(
                clock="one_outer_dt_per_moving_ion",
                blocking="multiply_stored_opening_after_each_implicit_update",
                calls_per_step=3,
                base_block=np.ones(len(owners)).tolist(),
                threshold_voltage_V=0.015,
                minimum_open_fraction=0.1,
                native_source_sha256=PROTOCOL["junction"]["native_source_sha256"],
            )
            applied = dict(
                active=dict(pump_availability=base_pump.tolist(), channel_permeability_m_s=2e-8),
                dynamic_junction=dynamic,
            )
            hook = mixed_native.hook(
                phase, Path("/native/science"), None, None, PROTOCOL, case, applied
            )
            for step in range(phase.p.init_tsteps):
                hook.completed = step
                hook.apply()
                entry = applied["interventions"]["steps"][-1]
                np.testing.assert_array_equal(phase.sim.NaKATP_block, entry["pump_available"])
                np.testing.assert_array_equal(
                    channel.maxDm, phase.p.tm * np.asarray(entry["channel_permeability_m_s"])
                )
            row = dict(
                case=case,
                fixture=applied,
                dt_s=dt,
                steps=phase.p.init_tsteps,
                geometry=dict(mem_to_cells=owners.tolist()),
            )
            rows, blocks = independent.inputs(row, PROTOCOL)
            assert len(rows) == len(blocks) == phase.p.init_tsteps
            assert (
                applied["interventions"]["steps"][-1]["event_index"]
                == len(case["interventions"]) - 2
            )
            for record, key in (
                ("interventions", "event_index"),
                ("interventions", "pump_available"),
                ("interventions", "channel_permeability_m_s"),
                ("junction_inputs", "block"),
                ("junction_inputs", "before_elapsed_s"),
            ):
                bad = copy.deepcopy(row)
                entry = bad["fixture"][record]["steps"][round(16e-6 / dt)]
                if isinstance(entry[key], list):
                    entry[key][0] += 1
                else:
                    entry[key] += 1
                with pytest.raises(AssertionError):
                    independent.inputs(bad, PROTOCOL)
    common.evidence(
        "mixed-input-known-answers",
        dict(
            status="passed",
            schedules=18,
            synthetic_cells=7,
            all_routes=True,
            terminal_input_not_applied=True,
            corrupt_records_rejected=90,
            scope=(
                "Input callback and independent reconstruction; "
                "full lifecycle checked by observed/bare capture"
            ),
        ),
    )


def test_compiled_smoke():
    raw = definition()
    raw["experiment"] = dict(
        end_time=6e-6,
        observation_times=[i * 1e-6 for i in range(7)],
        changes=[dict(c, time=i * 2e-6) for i, c in enumerate(raw["experiment"]["changes"][:3])],
    )
    spec = parse_spec(raw)
    result = run(spec)
    assert all(v.device.platform == BACKEND for v in result.final.state)
    state, p = definition_arrays(spec.model)
    for control in zip(*control_values(spec, result.times[:-1]), strict=True):
        state, _, valid = kernel.step(state, p, spec.execution.dt, kernel.Control(*control), xp=np)
        assert valid
    previous.short.compare_cpu_gpu_arrays(
        previous.previous.state_arrays(model.active_state(result.final.state)),
        previous.previous.state_arrays(model.active_state(model.flatten(state))),
        p.active.tissue.membrane_area,
    )
    np.testing.assert_allclose(
        result.final.state.junction_open,
        state.junction_open,
        atol=PROTOCOL["tolerances"]["gate_atol"],
        rtol=PROTOCOL["tolerances"]["gate_rtol"],
    )


@pytest.fixture(scope="module")
def prior():
    result = mixed.baseline()
    common.evidence("mixed-prerequisite", result)
    return result


@pytest.fixture(scope="module")
def captured(prior):
    assert prior["status"] == "passed"
    path, rows = mixed.native_capture()
    common.evidence(
        "mixed-native-capture",
        dict(
            status="passed",
            root=str(path),
            observed_bare_pairs=len(CASES),
            rows=len(rows),
            completion_sha256=refinement.digest(path / "completion.json"),
            observer_neutrality="bitwise",
            reused_from_failed_comparison=True,
            native_inputs_unchanged=True,
            binding=PROTOCOL["native_capture_binding"],
        ),
    )
    return path, rows


def _rate(state, control, p, dt):
    return kernel.step(model.unflatten(state), p, dt, control)[1]


RATES = jax.jit(jax.vmap(_rate, in_axes=(0, 0, None, None)))
UNFLATTEN = jax.jit(jax.vmap(model.unflatten))


def compute(spec):
    device = jax.devices(BACKEND)[0]
    start = time.perf_counter()
    result = run(spec)
    for leaf in result.final.state:
        assert leaf.device.platform == BACKEND
    _, p = definition_arrays(result.spec.model)
    before = model.STATE_TYPE(*(v[:-1] for v in result.history))
    after = model.STATE_TYPE(*(v[1:] for v in result.history))
    controls = control_values(result.spec, result.times[:-1])
    rates = common.selected(
        RATES, (before, controls, p, np.asarray(result.spec.execution.dt)), device
    )
    states = common.selected(UNFLATTEN, (after,), device)
    fields = common.selected(common.FIELDS, (states.active.tissue, p.active.tissue), device)
    observed = common.observed_history(
        states.active.tissue, rates.active.ordinary, fields, p.active.tissue
    )
    return dict(
        result=result,
        states=states,
        rates=rates,
        observed=observed,
        controls=controls,
        layout=p,
        wall_seconds=time.perf_counter() - start,
    )


@pytest.fixture(scope="module")
def computed(prior):
    assert prior["status"] == "passed"
    return {(c, i): compute(parse_spec(definition(c, i))) for c, i in CASES}


def saved_arrays(value):
    return previous.arrays(value["result"]) | {
        "rate__pump": value["rates"].active.pump_cycles_fmol_s,
        "rate__channel": value["rates"].active.channel_inward_fmol_s,
        "rate__junction_after_ion": value["rates"].junction_after_ion,
    }


def compare_saved(actual, expected, area):
    assert set(actual) == set(expected)
    ordinary = {k: v for k, v in actual.items() if not k.startswith("rate__")}
    count = previous.compare(ordinary, {k: expected[k] for k in ordinary}, area)
    tol = PROTOCOL["tolerances"]
    for name in ("rate__pump", "rate__channel", "rate__junction_after_ion"):
        atol = tol["gate_atol"] if name.endswith("after_ion") else tol["flux_atol_fmol_s"]
        assert actual[name].shape == expected[name].shape
        assert actual[name].dtype == expected[name].dtype
        assert np.isfinite(actual[name]).all() and np.isfinite(expected[name]).all()
        np.testing.assert_allclose(
            actual[name], expected[name], atol=atol, rtol=tol["cpu_gpu_rtol"]
        )
        count += actual[name].size
    return count


@pytest.mark.parametrize("case,index", CASES)
def test_native(case, index, captured, computed):
    path, rows = captured
    key = f"{case}/step-{index}/observed"
    row = rows[key]
    with np.load(path / key / "trace.npz", allow_pickle=False) as saved:
        trace = dict(saved)
    value = computed[(case, index)]
    result, states, rates = value["result"], value["states"], value["rates"]
    initial, layout = junctions.prepare(row, trace, PROTOCOL)
    exported, p = definition_arrays(result.spec.model)
    common.bits(initial, exported)
    common.bits(layout, p)
    actual = previous.arrays(result)
    allowance, gate_report, gate_arrays = gate_roundoff.check(
        row, trace, actual, PROTOCOL["tolerances"]
    )
    if EVIDENCE:
        gate_path = Path(EVIDENCE) / BACKEND / f"mixed-native-{case}-{index}-gates.npz"
        np.savez_compressed(gate_path, **gate_arrays)
        gate_report["arrays_file"] = gate_path.name
        gate_report["arrays_sha256"] = refinement.digest(gate_path)
    direct = junction_runtime.compare_native(
        {k: v[1:] for k, v in actual.items()}, row, trace, gate_allowance=allowance
    )
    comparison = junction_reference.compare(
        row,
        trace,
        PROTOCOL["tolerances"],
        states.active.tissue._asdict(),
        {k: v for k, v in states.active._asdict().items() if k != "tissue"},
        {k: v for k, v in rates.active._asdict().items() if k != "ordinary"},
        value["observed"],
        states.junction_open,
        rates.junction_after_ion,
        gate_allowance=allowance,
    )
    if BACKEND == "cpu":
        updates = independent.native_check(row, trace, PROTOCOL)
    else:
        report = json.loads(
            (Path(EVIDENCE) / "cpu" / f"mixed-native-{case}-{index}.json").read_text()
        )
        assert report["status"] == "passed" and report["native_trace_sha256"] == row["trace_sha256"]
        independent.inputs(row, PROTOCOL)
        updates = report["native_updates"]
    common.evidence(
        f"mixed-native-{case}-{index}",
        dict(
            status="passed",
            native_trace_sha256=row["trace_sha256"],
            native_updates=updates,
            native_comparison=direct,
            rate_and_field_comparison=comparison,
            gate_comparison=gate_report,
            diagnostics=result.diagnostics,
            state_arrays=14,
            fields=7,
            wall_seconds=value["wall_seconds"],
            native_evolving_values_used_as_inputs=False,
            duration_s=PROTOCOL["duration_s"],
        ),
        saved_arrays(value),
    )


def test_static_compatibility(computed):
    for index in range(3):
        for case in ("sham", "junction_only"):
            raw = definition(case, index)
            if case == "sham":
                del raw["experiment"]["changes"]
            else:
                raw["experiment"][
                    "changes"
                ].pop()  # Same junction-only schedule without terminal input.
            result = run(parse_spec(raw))
            common.bits(result.history, computed[(case, index)]["result"].history)
    common.evidence(
        "mixed-static-compatibility",
        dict(
            status="passed",
            histories=6,
            comparison="bitwise",
            static_sham=True,
            terminal_event_does_not_integrate=True,
            junction_only_anchor=True,
        ),
    )


def test_prefixes(computed, captured):
    root = Path(PROTOCOL["prior_binding"]["root"])
    native_root, rows = captured
    scalars = native_scalars = 0
    differences = {}
    for (case, index), value in computed.items():
        actual = saved_arrays(value)
        with np.load(
            root / f"evidence/{BACKEND}/mixed-native-{case}-{index}.npz", allow_pickle=False
        ) as saved:
            expected = dict(saved)
        prefix = {k: v[: len(expected[k])] for k, v in actual.items()}
        scalars += compare_saved(prefix, expected, value["layout"].active.tissue.membrane_area)
        differences[f"{case}-{index}"] = {
            k: float(np.max(abs(prefix[k] - expected[k])))
            for k in prefix
            if not np.array_equal(prefix[k], expected[k])
        }
        key = f"{case}/step-{index}/observed"
        old = root / "evidence/cpu/mixed-native" / key
        old_row = json.loads((old / "result.json").read_text())
        with (
            np.load(old / "trace.npz", allow_pickle=False) as before,
            np.load(native_root / key / "trace.npz", allow_pickle=False) as after,
        ):
            assert set(before) == set(after)
            for name in before:
                if name == "raw_label_s":
                    continue  # BETSE's inclusive printed labels depend on total duration.
                expected = before[name]
                common.bits(
                    after[name] if name.startswith("initial_") else after[name][: len(expected)],
                    expected,
                )
                native_scalars += expected.size
        for name in ("interventions", "junction_inputs"):
            assert (
                rows[key]["fixture"][name]["steps"][: old_row["steps"]]
                == old_row["fixture"][name]["steps"]
            )
    common.evidence(
        "mixed-prefixes",
        dict(
            status="passed",
            histories=len(CASES),
            prefix_duration_s=PROTOCOL["prefix_duration_s"],
            compared_scalars=scalars,
            native_compared_scalars=native_scalars,
            native_prefixes_bitwise=True,
            native_raw_labels_excluded=True,
            cells_prefixes_all_bitwise=not any(differences.values()),
            nonbitwise_fields=differences,
            comparison="Inherited tolerances, with exact differences reported separately",
        ),
    )


def test_horizon_continuations(computed, tmp_path):
    rule = PROTOCOL["replay"]
    full = computed[(rule["continuation_case"], rule["continuation_step_index"])]["result"]
    for duration in rule["continuation_horizons_s"]:
        raw = full.spec.to_dict()
        cut = round(duration / full.spec.execution.dt)
        raw["experiment"].update(
            end_time=cut * full.spec.execution.dt,
            observation_times=raw["experiment"]["observation_times"][: cut + 1],
            changes=[c for c in raw["experiment"]["changes"] if c["time"] < duration],
        )
        raw["experiment"]["changes"].append(
            dict(
                time=cut * full.spec.execution.dt,
                pump=[0.0] * 30,
                channel=[0.0] * 30,
                junction=[0.0] * 30,
            )
        )
        short = run(parse_spec(raw))
        common.bits(short.history, model.STATE_TYPE(*(v[: cut + 1] for v in full.history)))
        path = tmp_path / f"terminal-{cut}"
        write_snapshot(path, short.spec, short.final)
        saved = load_snapshot(path)
        checkpoint = branch_checkpoint(saved.spec, saved.checkpoint, full.spec)
        resumed = run(full.spec, checkpoint)
        common.bits(resumed.history, model.STATE_TYPE(*(v[cut:] for v in full.history)))
    common.evidence(
        "mixed-horizon-continuations",
        dict(
            status="passed",
            from_horizons_s=rule["continuation_horizons_s"],
            to_horizon_s=PROTOCOL["duration_s"],
            state_arrays=14,
            comparison="bitwise",
            disk=True,
            unexecuted_terminal_controls_replaced=True,
            execution_budget_reserved_before_checkpoint=True,
        ),
    )


def test_effects(computed):
    effects = {}
    for (case, index), value in computed.items():
        result, controls, rates = value["result"], value["controls"], value["rates"]
        for route, field in (("pump", "pump_cycles_fmol_s"), ("channel", "channel_inward_fmol_s")):
            np.testing.assert_array_equal(
                getattr(rates.active, field)[getattr(controls, route) == 0], 0
            )
            released = result.times[:-1] >= 48e-6
            assert np.any(abs(getattr(rates.active, field)[released]) > 0)
        blocked = np.all(controls.junction == 0, axis=1)
        np.testing.assert_array_equal(rates.junction_after_ion[blocked], 0)
        np.testing.assert_array_equal(rates.active.ordinary.junction_outward_fmol_s[blocked], 0)
        if np.any(controls.channel == 0):
            assert np.any(
                np.diff(np.asarray(result.history.m_gate), axis=0)[controls.channel == 0] != 0
            )
        sham = computed[("sham", index)]["result"]
        first = round((8e-6 if case == "staggered" else 16e-6) / result.spec.execution.dt)
        common.bits(
            model.STATE_TYPE(*(v[: first + 1] for v in result.history)),
            model.STATE_TYPE(*(v[: first + 1] for v in sham.history)),
        )
        difference = float(
            np.max(
                abs(result.observations.membrane_voltage_V - sham.observations.membrane_voltage_V)
            )
        )
        if case != "sham":
            assert difference > PROTOCOL["tolerances"]["voltage_atol_V"]
        effects[f"{case}-{index}"] = difference
    common.evidence(
        "mixed-effects",
        dict(
            status="passed",
            max_voltage_difference_V=effects,
            blocked_routes_zero=True,
            intrinsic_gates_continue=True,
            transport_restored=True,
            scope="Synthetic input response through 512 us; no biological recovery claim",
        ),
    )


def test_replay(computed, tmp_path):
    rule = PROTOCOL["replay"]
    cuts = rule["checkpoint_steps"]
    for case in rule["cases"]:
        full = computed[(case, 0)]["result"]
        for cut in cuts:
            path = tmp_path / f"{case}-{cut}"
            write_snapshot(path, full.spec, full.checkpoint_at(full.times[cut]))
            saved = load_snapshot(path)
            suffix = run(saved.spec, saved.checkpoint)
            common.bits(suffix.history, model.STATE_TYPE(*(v[cut:] for v in full.history)))
        assert_windows(list(iter_windows(full.spec, WindowPolicy(rule["window_steps"][0]))), full)
        checkpoint = full.checkpoint_at(full.times[64])
        assert_windows(
            list(iter_windows(full.spec, WindowPolicy(rule["window_steps"][1]), checkpoint)),
            run(full.spec, checkpoint),
        )
        common.bits(run(full.spec, full.final).final.state, full.final.state)
    common.evidence(
        "mixed-replay",
        dict(
            status="passed",
            cases=rule["cases"],
            cuts=cuts,
            window_steps=rule["window_steps"],
            comparison="bitwise",
            state_arrays=14,
            disk=True,
        ),
    )


def test_branches(computed):
    full = computed[("coupled_block", 0)]["result"]
    checkpoint = full.checkpoint_at(full.times[16])
    raw = full.spec.to_dict()
    for name, fraction in (("pump", 0.5), ("channel", 0.25), ("junction", 0.5)):
        raw["experiment"]["changes"][1][name] = [fraction] * 30
    changed = parse_spec(raw)
    suffix = run(changed, branch_checkpoint(full.spec, checkpoint, changed))
    whole = run(changed)
    common.bits(suffix.history, model.STATE_TYPE(*(v[16:] for v in whole.history)))
    common.bits(
        model.STATE_TYPE(*(v[:17] for v in full.history)),
        model.STATE_TYPE(*(v[:17] for v in whole.history)),
    )
    raw["experiment"]["changes"][0]["pump"][0] = 0.5
    with pytest.raises(ConfigError, match="rewrite"):
        branch_checkpoint(full.spec, checkpoint, parse_spec(raw))
    with pytest.raises(ConfigError, match="event position"):
        validate_checkpoint(full.spec, replace(checkpoint, event_index=0))
    common.evidence(
        "mixed-branches",
        dict(
            status="passed",
            all_routes_changed=True,
            future_suffix_bitwise=True,
            past_and_stale_cursor_rejected=True,
        ),
    )


def test_worlds(tmp_path):
    rule = PROTOCOL["world_checks"]
    batch = batch_spec()
    full = run_batch(batch)
    reverse = run_batch(replace(batch, worlds=tuple(reversed(batch.worlds))))
    for world in batch.worlds:
        target = full.worlds[world.world_id].history
        common.bits(target, run(world.simulation).history)
        common.bits(target, reverse.worlds[world.world_id].history)
        common.bits(
            target, run_batch(replace(batch, worlds=(world,))).worlds[world.world_id].history
        )
    rounds = list(iter_batch_windows(batch, WindowPolicy(rule["window_steps"])))
    for key, value in full.worlds.items():
        assert_windows([r.worlds[key] for r in rounds if key in r.worlds], value)
    checkpoints = full.checkpoint_at(
        {i + 10: full.worlds[i + 10].times[step] for i, step in enumerate(rule["checkpoint_steps"])}
    )
    write_batch_snapshot(tmp_path / "worlds", batch, checkpoints)
    saved = load_batch_snapshot(tmp_path / "worlds")
    resumed = run_batch(saved.spec, saved.checkpoints)
    for key, value in resumed.worlds.items():
        common.bits(
            value.history,
            model.STATE_TYPE(*(v[checkpoints[key].step_index :] for v in full.worlds[key].history)),
        )
    common.evidence(
        "mixed-worlds",
        dict(
            status="passed",
            worlds=3,
            comparison="bitwise",
            independent_clocks=True,
            reordered=True,
            partitioned=True,
            disk=True,
            completed_world=True,
            durations_s=rule["durations_s"],
            checkpoint_steps=rule["checkpoint_steps"],
        ),
    )


def test_negative_controls(captured, computed):
    path, rows = captured
    key = "coupled_block/step-0/observed"
    row = rows[key]
    with np.load(path / key / "trace.npz", allow_pickle=False) as trace:
        actual = {
            k: np.asarray(v[1:])
            for k, v in previous.arrays(computed[("coupled_block", 0)]["result"]).items()
        }
        faults = {
            "state__cell_concentration": 1e-5,
            "state__membrane_inward_fmol": 1e-5,
            "state__elapsed_s": 1e-6,
            "junction__open": 1e-3,
            "observed__vm": 1e-5,
        }
        for name, error in faults.items():
            bad = dict(actual)
            bad[name] = bad[name].copy()
            bad[name].flat[-1] += error
            with pytest.raises(AssertionError):
                junction_runtime.compare_native(bad, row, trace)
    common.evidence(
        "mixed-negative-controls",
        dict(status="passed", rejected=list(faults), tolerances_unchanged=True),
    )


def test_cpu_gpu(computed):
    if BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved CPU histories")
    count = 0
    for (case, index), value in computed.items():
        actual = saved_arrays(value)
        with np.load(
            Path(EVIDENCE) / "cpu" / f"mixed-native-{case}-{index}.npz", allow_pickle=False
        ) as saved:
            count += compare_saved(actual, dict(saved), value["layout"].active.tissue.membrane_area)
    common.evidence(
        "mixed-cpu-gpu",
        dict(
            status="passed", compared_scalars=count, histories=len(CASES), state_arrays=14, fields=7
        ),
    )
