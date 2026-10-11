"""Long prescribed interventions, common-time refinement and ordinary replay."""

import copy
import os
import subprocess
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.batch_io import load_batch_snapshot, write_batch_snapshot
from cells.core.batch import BatchSpec, WorldSpec, plan_batch, run_batch
from cells.core.batch_windows import iter_batch_windows, plan_batch_windows
from cells.core.betse_spatial_spec import definition_arrays
from cells.core.errors import NumericalError
from cells.core.runner import branch_checkpoint, run, timeline
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, parse_spec
from cells.core.windows import WindowPolicy, iter_windows
from cells.io import load_snapshot, write_snapshot
from cells.models import betse_spatial as model
from cells.numerics import betse_active as active
from tests.unit import test_betse_spatial_active_refinement as temporal
from tests.unit import test_betse_spatial_interventions as short
from tests.unit.test_betse_tissue_contact import load_capture
from tests.unit.test_windows import assert_windows
from validation.betse.spatial_active import fixtures, refinement
from validation.betse.spatial_active import intervention_reference as independent
from validation.betse.spatial_active import intervention_refinement as long

common, active_tests = short.common, short.short
BACKEND, EVIDENCE = short.BACKEND, short.EVIDENCE
PROTOCOL = long.protocol()
CASES = [(c["id"], i) for c in PROTOCOL["cases"] for i in range(3)]
WORLD_CASES = (("coupled_block", 0), ("regional", 1), ("staggered", 2))


def replay_batch(specs):
    return BatchSpec(
        worlds=tuple(WorldSpec(i + 10, spec) for i, spec in enumerate(specs)),
        max_worlds=4,
        max_padded_steps=4096,
        max_working_bytes=PROTOCOL["resources"]["batch_max_working_bytes"],
    )


@pytest.fixture(scope="module")
def prior():
    return long.baseline()


def test_long_intervention_prerequisite(prior):
    common.evidence("long-intervention-prerequisite", prior)


def test_host_long_protocol_preserves_physics_and_criteria():
    for name in (
        "cases",
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
    assert PROTOCOL["refinement"]["required_resolved_final_fields"] == {
        c["id"]: ["vm", "m_gate"] for c in PROTOCOL["cases"]
    }
    assert not PROTOCOL["allowed_prior_source_changes"]
    assert PROTOCOL["automatic_followup"] is False
    assert len(CASES) == 18


@pytest.mark.parametrize("case,index", CASES)
def test_host_long_definitions_and_event_clocks(case, index):
    raw = long.definition(case, index, backend=BACKEND)
    base = short.interventions.definition(case, 0, backend=BACKEND)
    assert raw["model"] == base["model"]
    assert raw["experiment"]["changes"] == base["experiment"]["changes"]
    spec = parse_spec(raw)
    assert parse_spec(spec.to_dict()) == spec
    times = timeline(spec)
    assert len(times) == round(256e-6 / spec.execution.dt) + 1
    np.testing.assert_array_equal(spec.experiment.observation_times, times)
    np.testing.assert_array_equal(
        model.integration_steps(spec, times), np.full(len(times) - 1, spec.execution.dt)
    )
    controls = control_values(spec, times)
    for i, event in enumerate(spec.experiment.changes):
        step = round(event.time / spec.execution.dt)
        assert event_index(spec, times[step]) == i
        assert event_index(spec, times[step + 1]) == i
        for name in ("pump", "channel"):
            np.testing.assert_array_equal(getattr(controls, name)[step], getattr(event, name))
            if i:
                assert event_index(spec, times[step - 1]) == i - 1
                np.testing.assert_array_equal(
                    getattr(controls, name)[step - 1], getattr(spec.experiment.changes[i - 1], name)
                )


def test_host_long_batch_resource_plans():
    batch = replay_batch(
        [parse_spec(long.definition(case, index, backend=BACKEND)) for case, index in WORLD_CASES]
    )
    # Reserve at least half of the existing worker RSS ceiling for other live
    # reference histories, compiler work and process overhead.
    assert batch.max_working_bytes <= PROTOCOL["resources"]["max_worker_rss_bytes"] // 2
    with pytest.raises(ConfigError, match="Estimated aggregate arrays"):
        plan_batch(replace(batch, max_working_bytes=1024**3))
    variants = {
        "full": batch,
        "reordered": replace(batch, worlds=tuple(reversed(batch.worlds))),
        **{f"world-{w.world_id}": replace(batch, worlds=(w,)) for w in batch.worlds},
    }
    plans = {}
    for name, candidate in variants.items():
        full = plan_batch(candidate)
        windows = plan_batch_windows(candidate, WindowPolicy(97))
        assert full.estimated_working_bytes <= candidate.max_working_bytes
        assert windows.estimated_working_bytes <= candidate.max_working_bytes
        assert full.padded_step_bound <= candidate.max_padded_steps
        assert windows.padded_step_bound <= candidate.max_padded_steps
        plans[name] = dict(
            full_working_bytes=full.estimated_working_bytes,
            window_working_bytes=windows.estimated_working_bytes,
            padded_step_bound=full.padded_step_bound,
            window_padded_step_bound=windows.padded_step_bound,
            accepted_steps=[len(grid) - 1 for grid in full.grids],
        )
    assert plans["full"]["full_working_bytes"] == plans["reordered"]["full_working_bytes"]
    common.evidence(
        "long-intervention-resource-plan",
        dict(
            status="passed",
            backend=BACKEND,
            batch_max_working_bytes=batch.max_working_bytes,
            worker_rss_limit_bytes=PROTOCOL["resources"]["max_worker_rss_bytes"],
            previous_1_GiB_budget_rejected=True,
            window_steps=97,
            plans=plans,
            scope="Host estimates before integration; measured process/device usage is separate",
        ),
    )


def test_compiled_quarter_step_intervention_smoke():
    raw = long.definition("coupled_block", 2, backend=BACKEND)
    raw["experiment"] = dict(
        end_time=6e-6,
        observation_times=[0, 2e-6, 4e-6, 6e-6],
        changes=[
            dict(c, time=t)
            for c, t in zip(raw["experiment"]["changes"], (0, 2e-6, 4e-6), strict=True)
        ],
    )
    spec = parse_spec(raw)
    result = run(spec)
    assert all(v.device.platform == BACKEND for v in result.final.state)
    state, p = definition_arrays(spec.model)
    for step in range(24):
        enabled = 0.0 if 8 <= step < 16 else 1.0
        state, _, valid = active.step(
            state,
            p._replace(
                pump_available=p.pump_available * enabled,
                channel_permeability=p.channel_permeability * enabled,
            ),
            spec.execution.dt,
            xp=np,
        )
        assert valid
    active_tests.compare_cpu_gpu_arrays(
        short.previous.state_arrays(result.final.state),
        short.previous.state_arrays(model.flatten(state)),
        p.tissue.membrane_area,
    )
    suffix = run(spec, result.checkpoint_at(result.times[16]))
    common.bits(suffix.history, model.STATE_TYPE(*(v[16:] for v in result.history)))


@pytest.fixture(scope="module")
def captured(prior, tmp_path_factory):
    assert prior["status"] == "passed"
    if BACKEND == "gpu":
        assert EVIDENCE
        path = Path(EVIDENCE) / "cpu/long-intervention-native"
    else:
        root = Path(EVIDENCE) / "cpu" if EVIDENCE else tmp_path_factory.mktemp("long-intervention")
        root.mkdir(parents=True, exist_ok=True)
        path = root / "long-intervention-native"
        with (
            (root / "long-intervention-native.stdout.log").open("x") as out,
            (root / "long-intervention-native.stderr.log").open("x") as err,
        ):
            subprocess.run(
                [
                    "/mnt/workspaces/Cells/venv-betse/bin/python",
                    "-B",
                    str(long.PROTOCOL_PATH.with_name("intervention_native.py")),
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
                    os.environ, MPLBACKEND="Agg", MPLCONFIGDIR=str(root / "matplotlib-long-inputs")
                ),
            )
    rows = load_capture(path, PROTOCOL)
    for case, index in CASES:
        row, trace = rows[f"{case}/step-{index}/observed"]
        bare, _ = rows[f"{case}/step-{index}/bare"]
        for name in (
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
            assert row[name] == bare[name], name
        assert trace is not None
        assert row["steps"] == round(PROTOCOL["duration_s"] / row["dt_s"])
        independent.step_rows(row)
    return rows


@pytest.fixture(scope="module")
def computed(captured):
    values = {}
    for case, index in CASES:
        row, trace = captured[f"{case}/step-{index}/observed"]
        spec = parse_spec(long.definition(case, index, backend=BACKEND))
        values[(case, index)] = short.simulate(row, trace, spec, PROTOCOL)
    return values


@pytest.mark.parametrize("case,index", CASES)
def test_long_intervention_native_trajectory(case, index, computed):
    value = computed[(case, index)]
    native = independent.native_check(value["row"], value["trace"], PROTOCOL)
    report = short.compare(value)
    report.update(
        backend=BACKEND,
        observer_neutrality="bitwise",
        controlled_steps=value["row"]["steps"],
        native_max_errors=native["max_errors"],
        native_pump_error_fmol_s=native["max_pump_error_fmol_s"],
        diagnostics=value["result"].diagnostics,
    )
    common.evidence(
        f"long-intervention-native-{case}-{index}",
        report,
        fixtures.arrays(value["states"], value["rates"], value["observed"]),
    )


def test_long_intervention_original_prefixes(prior, computed):
    root = Path(prior["root"])
    old = load_capture(root / "evidence/cpu/intervention-native", short.PROTOCOL)
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
            before = row["fixture"]["interventions"]["steps"]
            assert value["row"]["fixture"]["interventions"]["steps"][: len(before)] == before
            control_steps += len(before)
            path = root / f"evidence/{BACKEND}/intervention-native-{case}-{index}.npz"
            actual = fixtures.arrays(value["states"], value["rates"], value["observed"])
            with np.load(path, allow_pickle=False) as saved:
                assert set(saved) == set(actual)
                for name in saved:
                    if not name.startswith("observed__"):
                        common.bits(actual[name][: len(saved[name])], saved[name])
                        state_count += saved[name].size
                names = [n for n in saved if n.startswith("observed__")]
                readout_count += active_tests.compare_cpu_gpu_arrays(
                    {n: actual[n][: len(saved[n])] for n in names},
                    {n: saved[n] for n in names},
                    value["layout"].tissue.membrane_area,
                )
    common.evidence(
        "long-intervention-prefix",
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


@pytest.mark.parametrize("case", [c["id"] for c in PROTOCOL["cases"]])
def test_long_intervention_temporal_refinement(case, computed):
    values = [computed[(case, i)] for i in range(3)]
    for value in values[1:]:
        common.bits(value["layout"], values[0]["layout"])
        common.bits(
            model.STATE_TYPE(*(v[0] for v in value["result"].history)),
            model.STATE_TYPE(*(v[0] for v in values[0]["result"].history)),
        )
    area = values[0]["layout"].tissue.membrane_area
    report = refinement.check(case, [temporal.series(v) for v in values], area, PROTOCOL)
    report["native"] = refinement.check(
        case, [refinement.native_series(v["row"], v["trace"]) for v in values], area, PROTOCOL
    )
    report["backend"] = BACKEND
    common.evidence("long-intervention-refinement-" + case, report)


def test_long_intervention_disk_and_windows(computed, tmp_path):
    full = computed[("staggered", 2)]["result"]
    cuts = sorted(
        {
            round(c.time / full.spec.execution.dt) + d
            for c in full.spec.experiment.changes[1:]
            for d in (-1, 0, 1)
        }
        | {513}
    )
    for cut in cuts:
        path = tmp_path / str(cut)
        write_snapshot(path, full.spec, full.checkpoint_at(full.times[cut]))
        saved = load_snapshot(path)
        suffix = run(saved.spec, saved.checkpoint)
        common.bits(suffix.history, model.STATE_TYPE(*(v[cut:] for v in full.history)))
    assert_windows(list(iter_windows(full.spec, WindowPolicy(97))), full)
    at_release = full.checkpoint_at(full.times[160])
    assert_windows(
        list(iter_windows(full.spec, WindowPolicy(131), at_release)), run(full.spec, at_release)
    )
    common.bits(run(full.spec, full.final).final.state, full.final.state)
    common.evidence(
        "long-intervention-replay",
        dict(
            status="passed",
            state_arrays=13,
            comparison="bitwise",
            checkpoint_steps=cuts,
            windows=[97, 131],
            terminal=True,
            completed_duration_s=256e-6,
        ),
    )


def test_long_intervention_worlds(computed, tmp_path):
    values = [computed[k]["result"] for k in WORLD_CASES]
    batch = replay_batch([value.spec for value in values])
    full = run_batch(batch)
    for i, value in enumerate(values):
        common.bits(full.worlds[i + 10].history, value.history)
    reverse = run_batch(replace(batch, worlds=tuple(reversed(batch.worlds))))
    for key in full.worlds:
        common.bits(full.worlds[key].history, reverse.worlds[key].history)
    for world in batch.worlds:
        alone = run_batch(replace(batch, worlds=(world,)))
        common.bits(alone.worlds[world.world_id].history, full.worlds[world.world_id].history)
    rounds = list(iter_batch_windows(batch, WindowPolicy(97)))
    for key in full.worlds:
        assert_windows([r.worlds[key] for r in rounds if key in r.worlds], full.worlds[key])
    cuts = {10: 16, 11: 80, 12: 1024}
    checkpoints = full.checkpoint_at(
        {key: full.worlds[key].times[step] for key, step in cuts.items()}
    )
    write_batch_snapshot(tmp_path / "worlds", batch, checkpoints)
    saved = load_batch_snapshot(tmp_path / "worlds")
    resumed = run_batch(saved.spec, saved.checkpoints)
    for key, value in resumed.worlds.items():
        common.bits(
            value.history, model.STATE_TYPE(*(v[cuts[key] :] for v in full.worlds[key].history))
        )
    common.evidence(
        "long-intervention-worlds",
        dict(
            status="passed",
            worlds=3,
            comparison="bitwise",
            independent_clocks=True,
            reordered=True,
            partitions=True,
            disk=True,
            window_steps=97,
            completed_world=True,
            full_batch_resources=full.resources,
            resumed_batch_resources=resumed.resources,
        ),
    )


def test_long_intervention_horizon_extension(computed, tmp_path):
    full = computed[("regional", 2)]["result"]
    raw = full.spec.to_dict()
    raw["experiment"]["end_time"] = 64e-6
    raw["experiment"]["observation_times"] = full.times[:257].tolist()
    before = parse_spec(raw)
    prefix = run(before)
    common.bits(prefix.history, model.STATE_TYPE(*(v[:257] for v in full.history)))
    write_snapshot(tmp_path / "short", before, prefix.final)
    saved = load_snapshot(tmp_path / "short")
    checkpoint = branch_checkpoint(saved.spec, saved.checkpoint, full.spec)
    suffix = run(full.spec, checkpoint)
    common.bits(suffix.history, model.STATE_TYPE(*(v[256:] for v in full.history)))
    common.evidence(
        "long-intervention-horizon",
        dict(
            status="passed",
            comparison="bitwise",
            previous_duration_s=64e-6,
            extended_duration_s=256e-6,
            dt_s=0.25e-6,
            state_arrays=13,
            disk=True,
        ),
    )


def test_long_intervention_effects(computed):
    effects = {}
    for (case, index), value in computed.items():
        result, controls, rates = value["result"], value["controls"], value["rates"]
        assert np.all(rates.pump_cycles_fmol_s[controls.pump == 0] == 0)
        assert np.all(rates.channel_inward_fmol_s[controls.channel == 0] == 0)
        if case == "sham":
            continue
        before = round(16e-6 / result.spec.execution.dt) + 1
        neutral = computed[("sham", index)]
        common.bits(
            model.STATE_TYPE(*(v[:before] for v in result.history)),
            model.STATE_TYPE(*(v[:before] for v in neutral["result"].history)),
        )
        released = result.times[:-1] >= result.spec.experiment.changes[-1].time
        assert np.any(abs(rates.pump_cycles_fmol_s[released]) > 0)
        assert np.any(abs(rates.channel_inward_fmol_s[released]) > 0)
        blocked = controls.channel == 0
        if blocked.any():
            assert np.any(np.diff(result.history.m_gate, axis=0)[blocked] != 0)
        difference = float(np.max(abs(value["observed"]["vm"] - neutral["observed"]["vm"])))
        assert difference > PROTOCOL["tolerances"]["voltage_atol_V"]
        effects[f"{case}-{index}"] = difference
    common.evidence(
        "long-intervention-effects",
        dict(
            status="passed",
            max_voltage_difference_V=effects,
            blocked_transport_zero=True,
            intrinsic_gates_continue=True,
            transport_restored=True,
            scope="Synthetic input response through 256 us, not biological recovery",
        ),
    )


def test_long_intervention_negative_controls(computed):
    value = computed[("regional", 2)]
    row = copy.deepcopy(value["row"])
    row["fixture"]["interventions"]["steps"][160]["event_index"] = 1
    with pytest.raises(AssertionError):
        independent.step_rows(row)
    state = model.STATE_TYPE(*(np.asarray(v).copy() for v in value["result"].final.state))
    state.channel_inward_fmol[0] += 1e-6
    with pytest.raises(NumericalError, match="material"):
        model.check_values(state, value["result"].spec)
    gates = value["states"].m_gate.copy()
    gates[-1, 0] += 1e-4
    with pytest.raises(AssertionError):
        short.compare(value, value["states"]._replace(m_gate=gates))
    common.evidence(
        "long-intervention-negative-controls",
        dict(
            status="passed",
            stale_native_control_rejected=True,
            late_channel_material_corruption_fmol=1e-6,
            late_gate_corruption_rejected=True,
        ),
    )


def test_long_intervention_cpu_gpu(computed):
    if BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved long scheduled CPU histories")
    assert EVIDENCE
    count = 0
    for (case, index), value in computed.items():
        actual = fixtures.arrays(value["states"], value["rates"], value["observed"])
        path = Path(EVIDENCE) / "cpu" / f"long-intervention-native-{case}-{index}.npz"
        with np.load(path, allow_pickle=False) as saved:
            count += active_tests.compare_cpu_gpu_arrays(
                actual, saved, value["layout"].tissue.membrane_area
            )
    common.evidence("long-intervention-cpu-gpu", dict(status="passed", compared_scalars=count))


def test_active_refinement_resolves_gate_and_flux_units():
    temporal.test_active_refinement_resolves_gate_and_flux_units()


@pytest.mark.parametrize(
    "fault",
    (
        "missing_gate",
        "unresolved_gate",
        "gate_nonfinite",
        "wrong_order",
        "worse",
        "truncated",
        "zero_time",
        "off_grid",
        "wrong_steps",
        "shape",
    ),
)
def test_active_refinement_rejects_false_claims(fault):
    temporal.test_active_refinement_rejects_false_claims(fault)
