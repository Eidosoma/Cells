"""Longer assembly/injury composition, with matched-world sampled recovery controls."""

import json
from dataclasses import dataclass, replace
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.assembly.spec import AssemblyError
from cells.assembly_cell.io import flatten, load_checkpoint, write_checkpoint
from cells.assembly_cell.spec import tick_at
from cells.assembly_cluster import controls, engine
from cells.assembly_cluster.spec import parse_spec
from cells.ensemble.families import bind_definition
from cells.ensemble.plan import jupiter_plan, plan
from cells.models import surface_repair as model
from tests.unit.test_assembly_cluster import ensemble_definition, event_histories, same
from tests.unit.test_surface_calcium import BACKEND, EVIDENCE, evidence
from tests.unit.test_surface_kinetic import assert_states
from tests.unit.test_surface_repair_full import compare_backend
from validation.tissue import assembly_repair_recovery as fixtures
from validation.tissue import surface_repair_reference as reference

PREFIX = "assembly-repair-recovery"
REFERENCE = dict(rtol=1e-13, atol=1e-16, charge_atol=5e-32)


@dataclass
class Captured:
    spec: object
    final: object
    report: dict
    observed: dict
    snapshots: list


def collect(name, spec, *, state=None, until=None):
    initial = engine.initial_state(spec) if state is None else state
    snapshots = [jax.tree.map(lambda v: np.asarray(v).copy(), initial)]
    requested = {tick_at(spec, t) for t in spec.ionic.experiment.observation_times}
    requested.add(spec.ticks if until is None else tick_at(spec, until))
    last = snapshots[0]

    def capture(_, current):
        nonlocal last
        last = current
        if int(current.tick[0]) in requested:
            snapshots.append(jax.tree.map(lambda v: v.copy(), current))

    def save(status, **details):
        rows = [flatten(s) for s in snapshots]
        observed = {k: np.stack([r[k] for r in rows]) for k in rows[0]}
        evidence(
            PREFIX + "-" + name + "-states",
            dict(status=status, inputs=spec.to_dict(), **details),
            observed,
        )
        return observed

    evidence(PREFIX + "-" + name + "-inputs", dict(inputs=spec.to_dict()))
    try:
        final, report = engine.run(
            spec, backend=BACKEND, state=state, until=until, callback=capture
        )
    except BaseException as exc:
        save("failed", error=repr(exc))
        evidence(PREFIX + "-" + name + "-last", dict(status="failed"), flatten(last))
        raise
    observed = save("captured", report=report)
    evidence(
        PREFIX + "-" + name + "-final",
        dict(status="captured", inputs=spec.to_dict(), report=report),
        flatten(final),
    )
    return Captured(spec, final, report, observed, snapshots)


def serial(value):
    return json.loads(json.dumps(value, default=lambda v: np.asarray(v).tolist()))


def independent(arm, value, world):
    spec = value.spec
    events = event_histories(spec, value.final, world)
    segments = fixtures.segments(spec, events)
    assert len(segments) > 1 and len({tuple(v) for _, v in segments}) > 1
    name = PREFIX + f"-reference-{arm}-world-{spec.pool.world_id_start + world}"
    inputs = dict(
        inputs=fixtures.normalized(spec.to_dict()),
        settings=REFERENCE,
        world_id=spec.pool.world_id_start + world,
        events=serial(events),
        channel_segments=serial(segments),
    )
    directory = Path(EVIDENCE) / "cpu" if EVIDENCE else None
    if directory and (directory / (name + ".json")).exists():
        receipt = json.loads((directory / (name + ".json")).read_text())
        assert receipt["status"] == "passed"
        assert all(receipt[k] == v for k, v in inputs.items())
        with np.load(directory / (name + ".npz"), allow_pickle=False) as archive:
            data = {k: archive[k].copy() for k in archive.files}
        assert data["state"].shape[0] == len(spec.ionic.experiment.observation_times)
        if BACKEND == "gpu":
            evidence(name, receipt | dict(reused_cpu_reference=True), data)
        return data, inputs
    assert BACKEND == "cpu", "Require completed CPU references with matching event histories"
    raw = spec.ionic.to_dict()
    result = reference.integrate(raw, channel_segments=segments, **REFERENCE)
    data = dict(
        state=result["state"],
        exposure_s=fixtures.exposure(result["times"], segments),
        **reference.measurements(raw, result["state"], channel_segments=segments),
    )
    evidence(
        name,
        inputs | dict(status="passed", method=result["method"], evaluations=result["evaluations"]),
        data,
    )
    return data, inputs


def reference_stability(arm, value, world, ordinary, inputs):
    name = PREFIX + f"-reference-stability-{arm}-world-{inputs['world_id']}"
    settings = {k: v / 4 for k, v in REFERENCE.items()}
    if BACKEND == "gpu":
        saved = json.loads((Path(EVIDENCE) / "cpu" / (name + ".json")).read_text())
        assert saved["status"] == "passed" and saved["tighter_settings"] == settings
        assert all(saved[k] == v for k, v in inputs.items())
        evidence(name, saved | dict(reused_cpu_reference=True))
        return
    raw, segments = value.spec.ionic.to_dict(), inputs["channel_segments"]
    tight = reference.integrate(raw, channel_segments=segments, **settings)["state"]
    measured = reference.measurements(raw, tight, channel_segments=segments)
    evidence(
        name + "-arrays",
        inputs | dict(tighter_settings=settings),
        dict(
            reference=ordinary["state"],
            tighter=tight,
            signed_error=ordinary["state"] - tight,
            **{"tighter_" + k: v for k, v in measured.items()},
        ),
    )
    for k, v in reference.unpack(reference.bind(raw), ordinary["state"] - tight).items():
        assert np.max(np.abs(v), initial=0) <= (3e-28 if k.endswith("_C") else 3e-14), k
    for k, v in measured.items():
        assert np.max(np.abs(ordinary[k] - v)) <= fixtures.READOUT_ATOL[k] / 10, k
    evidence(
        name,
        inputs
        | dict(
            status="passed",
            tighter_settings=settings,
            state_floor=3e-14,
            charge_floor_C=3e-28,
            readout_floors={k: v / 10 for k, v in fixtures.READOUT_ATOL.items()},
        ),
    )


def test_long_definitions_observation_clocks_and_limits():
    rows = []
    for arm in fixtures.ARMS:
        for dt in fixtures.STEPS:
            spec = parse_spec(fixtures.definition(arm, backend=BACKEND, dt=dt))
            assert parse_spec(spec.to_dict()).fingerprint == spec.fingerprint
            assert spec.pool.end_time_s == 0.002 and controls.extra_boundaries(spec.ionic) == 2
            assert len(spec.ionic.experiment.observation_times) == 85
            times = np.array(spec.ionic.experiment.observation_times)
            assert 5.3e-6 not in times and 15.3e-6 not in times
            assert times[np.searchsorted(times, 5.3e-6)] == 9 * fixtures.STEPS[0]
            assert times[np.searchsorted(times, 15.3e-6)] == 25 * fixtures.STEPS[0]
            assert [p.time for p in spec.ionic.experiment.changes] == [0.0, 5.3e-6, 15.3e-6]
            assert all(tick_at(spec, float(t)) * dt == t for t in times)
            rows.append(
                dict(
                    arm=arm,
                    dt_s=dt,
                    ticks=spec.ticks,
                    working_bytes=spec.working_bytes,
                    output_bound=spec.output_bound,
                )
            )
    raw = fixtures.definition()
    raw["ionic"]["execution"]["max_steps"] = 3201
    with pytest.raises(AssemblyError, match="budget"):
        parse_spec(raw)
    raw = fixtures.definition()
    raw["ionic"]["experiment"]["observation_times"].append(15.3e-6)
    raw["ionic"]["experiment"]["observation_times"].sort()
    with pytest.raises(AssemblyError, match="grid"):
        parse_spec(raw)
    root = Path(__file__).resolve().parents[2]
    assert json.loads(
        (root / "configs/assembly_resolved_repair_recovery_tissue.json").read_text()
    ) == fixtures.definition(backend="gpu")
    evidence(
        PREFIX + "-clocks",
        dict(
            status="passed",
            cases=rows,
            physical_intervention_times_s=[5.3e-6, 15.3e-6],
            first_observed_after_events_s=[9 * fixtures.STEPS[0], 25 * fixtures.STEPS[0]],
        ),
    )


def test_initial_readouts_and_independent_availability_integral():
    spec = parse_spec(fixtures.definition())
    state = engine.initial_state(spec)
    observed = {k: v[None] for k, v in flatten(state).items()}
    raw = spec.ionic.to_dict()
    raw["experiment"]["observation_times"] = [0.0]
    c = reference.bind(raw)
    segments = fixtures.segments(spec, {b.cell_id: [] for b in spec.pools})
    expected = reference.measurements(raw, reference.initial(c)[None], channel_segments=segments)
    for world in range(spec.pool.worlds):
        actual = fixtures.measurements(spec, observed, world)
        for k in fixtures.BANDS:
            np.testing.assert_allclose(actual[k], expected[k], rtol=3e-12, atol=3e-13)
    sample = fixtures.exposure([0.0, 0.1, 0.3, 0.4], [(0.0, [1.0, 0.0]), (0.2, [0.0, 0.5])])
    np.testing.assert_allclose(
        sample, [[0, 0], [0.1, 0], [0.2, 0.05], [0.2, 0.1]], rtol=0, atol=1e-16
    )
    evidence(
        PREFIX + "-owners",
        dict(
            status="passed",
            free_ion_owners=True,
            padding_excluded=True,
            independently_integrated_availability=True,
        ),
    )


def test_long_one_to_sixteen_gpu_planning():
    raw = ensemble_definition()
    definition = fixtures.definition(backend="gpu")
    for binding in definition["pools"]:
        for key in ("worlds", "world_id_start", "seed"):
            binding["pool"].pop(key)
    raw["arms"][0]["definition"] = definition
    local, future = plan(raw, 1), jupiter_plan(raw, 4)
    assert local["tasks"] == future["tasks"]
    assert future["deployment"]["maximum_target_gpus"] == 16
    assert not future["deployment"]["remote_execution_qualified"]
    ids = []
    for task in future["tasks"]:
        spec = parse_spec(task["definition"])
        assert spec.pool.end_time_s == 0.002 and controls.extra_boundaries(spec.ionic) == 2
        ids.extend(range(spec.pool.world_id_start, spec.pool.world_id_start + spec.pool.worlds))
    assert sorted(ids) == list(range(64))
    evidence(
        PREFIX + "-planning",
        dict(status="passed", world_ids=sorted(ids), maximum_target_gpus=16, gpu_execution=False),
    )


@pytest.fixture(scope="module")
def histories():
    return {
        arm: collect(arm, parse_spec(fixtures.definition(arm, backend=BACKEND)))
        for arm in fixtures.ARMS
    }


@pytest.mark.parametrize("arm", fixtures.ARMS)
def test_long_coupled_trajectory_all_worlds_against_reference(histories, arm):
    value = histories[arm]
    spec, observed = value.spec, value.observed
    np.testing.assert_array_equal(
        observed["pool_time_s"],
        np.broadcast_to(
            np.asarray(spec.ionic.experiment.observation_times)[:, None, None],
            observed["pool_time_s"].shape,
        ),
    )
    for state in value.snapshots:
        engine.validate_state(spec, state)
    rows = []
    c = reference.bind(spec.ionic.to_dict())
    for world in range(spec.pool.worlds):
        expected, inputs = independent(arm, value, world)
        actual = reference.flatten(
            c, {k: observed["ionic_" + k][:, world] for k in model.STATE_TYPE._fields}
        )
        measured = fixtures.measurements(spec, observed, world)
        evidence(
            PREFIX + f"-errors-{arm}-world-{inputs['world_id']}",
            inputs,
            dict(
                actual=actual,
                reference=expected["state"],
                signed_error=actual - expected["state"],
                **{"measured_" + k: v for k, v in measured.items()},
                **{"readout_error_" + k: v - expected[k] for k, v in measured.items()},
            ),
        )
        ratio = assert_states(c, actual, expected["state"])
        for k, v in measured.items():
            np.testing.assert_allclose(
                v, expected[k], rtol=0, atol=fixtures.READOUT_ATOL[k], err_msg=k
            )
        np.testing.assert_allclose(
            observed["availability_exposure_s"][:, world],
            expected["exposure_s"],
            rtol=0,
            atol=2e-14,
        )
        model.check_values(
            model.STATE_TYPE(*(observed["ionic_" + k][:, world] for k in model.STATE_TYPE._fields)),
            spec.ionic,
        )
        if arm in ("held", "resealing"):
            reference_stability(arm, value, world, expected, inputs)
        rows.append(
            dict(
                world_id=inputs["world_id"],
                max_error_over_budget=ratio,
                assembly_events={k: len(v) for k, v in inputs["events"].items()},
            )
        )
    evidence(
        PREFIX + "-trajectory-" + arm,
        dict(
            status="passed",
            worlds=rows,
            observations=len(spec.ionic.experiment.observation_times),
            report=value.report,
        ),
    )


def test_matched_assembly_functional_report_and_one_way_controls(histories):
    baseline = histories["uninjured"]
    for name, value in baseline.observed.items():
        np.testing.assert_array_equal(value, histories["sham"].observed[name], err_msg=name)
    reports = {}
    for world in range(baseline.spec.pool.worlds):
        base, base_inputs = independent("uninjured", baseline, world)
        for arm, value in histories.items():
            expected, inputs = independent(arm, value, world)
            assert inputs["events"] == base_inputs["events"]
            for name in value.observed:
                if name.startswith("pool_") or name == "availability_exposure_s":
                    np.testing.assert_array_equal(
                        value.observed[name], baseline.observed[name], err_msg=name
                    )
            measured = fixtures.measurements(value.spec, value.observed, world)
            base_readouts = {k: base[k] for k in fixtures.BANDS}
            times = value.spec.ionic.experiment.observation_times
            actual_label = fixtures.assess(times, measured, base_readouts)
            expected_label = fixtures.assess(
                times, {k: expected[k] for k in fixtures.BANDS}, base_readouts
            )
            reports[f"{arm}-world-{inputs['world_id']}"] = dict(
                observed=actual_label,
                independent_reference=expected_label,
                final_damage=value.observed["ionic_damage"][-1, world, :4].tolist(),
            )
    evidence(
        PREFIX + "-functional",
        dict(
            status="captured",
            results=reports,
            bands=fixtures.BANDS,
            uncertainty=fixtures.UNCERTAINTY,
            settings=fixtures.SETTINGS,
        ),
    )
    for name, result in reports.items():
        a, b = result["observed"], result["independent_reference"]
        assert a["classification"] == b["classification"]
        for key in fixtures.BANDS:
            assert a["metrics"][key]["classification"] == b["metrics"][key]["classification"]
        if name.startswith(("uninjured-", "sham-")):
            assert a["classification"] == "no_resolved_departure"
        else:
            assert a["first_resolved_departure_s"] is not None
    evidence(
        PREFIX + "-functional",
        dict(
            status="passed",
            results=reports,
            bands=fixtures.BANDS,
            uncertainty=fixtures.UNCERTAINTY,
            settings=fixtures.SETTINGS,
            same_assembly_paths_across_arms=True,
            positive_recovery_required=False,
        ),
    )


@pytest.mark.parametrize("arm", ("held", "resealing"))
def test_long_assembly_coupled_timestep_refinement(arm):
    baseline = collect(
        "refinement-" + arm + "-0", parse_spec(fixtures.definition(arm, backend=BACKEND))
    )
    refs = [independent(arm, baseline, w)[0] for w in range(baseline.spec.pool.worlds)]
    c = reference.bind(baseline.spec.ionic.to_dict())
    errors, charges, ratios = [], [], []
    for index, dt in enumerate(fixtures.STEPS):
        value = (
            baseline
            if index == 0
            else collect(
                f"refinement-{arm}-{index}",
                parse_spec(fixtures.definition(arm, backend=BACKEND, dt=dt)),
            )
        )
        for name in value.observed:
            if name.startswith("pool_"):
                np.testing.assert_array_equal(
                    value.observed[name], baseline.observed[name], err_msg=name
                )
        local_errors, local_charges, local_ratios = [], [], []
        for world, expected in enumerate(refs):
            actual = reference.flatten(
                c, {k: value.observed["ionic_" + k][:, world] for k in model.STATE_TYPE._fields}
            )
            evidence(
                PREFIX + f"-refinement-errors-{arm}-{index}-world-{world}",
                dict(inputs=value.spec.to_dict()),
                dict(
                    actual=actual,
                    reference=expected["state"],
                    signed_error=actual - expected["state"],
                ),
            )
            local_ratios.append(assert_states(c, actual, expected["state"]))
            diff = reference.unpack(c, actual - expected["state"])
            local_errors.append(
                max(float(np.max(np.abs(v))) for k, v in diff.items() if not k.endswith("_C"))
            )
            local_charges.append(
                max(float(np.max(np.abs(v))) for k, v in diff.items() if k.endswith("_C"))
            )
            for name, measured in fixtures.measurements(value.spec, value.observed, world).items():
                np.testing.assert_allclose(
                    measured, expected[name], rtol=0, atol=fixtures.READOUT_ATOL[name]
                )
        errors.append(local_errors)
        charges.append(local_charges)
        ratios.append(local_ratios)
    assert np.all(np.asarray(errors[-1]) <= np.maximum(np.asarray(errors[0]) * 0.2, 3e-13))
    assert np.all(np.asarray(charges[-1]) <= np.maximum(np.asarray(charges[0]) * 0.2, 3e-27))
    evidence(
        PREFIX + "-refinement-" + arm,
        dict(
            status="passed",
            steps_s=fixtures.STEPS,
            max_error_over_budget=ratios,
            noncharge_max_errors=errors,
            charge_max_errors_C=charges,
        ),
    )


def test_long_complete_restart_windows_and_pending_events(histories, tmp_path):
    value = histories["resealing"]
    index = list(value.spec.ionic.experiment.observation_times).index(0.001)
    middle = value.snapshots[index]
    write_checkpoint(tmp_path / "checkpoint", value.spec, middle, backend=BACKEND)
    spec, saved, _ = load_checkpoint(tmp_path / "checkpoint", backend=BACKEND)
    same(middle, saved)
    resumed = collect("resumed", replace(spec, window_ticks=17), state=saved)
    same(value.final, resumed.final)
    for actual, expected in zip(resumed.snapshots, value.snapshots[index:], strict=True):
        same(actual, expected)
    evidence(
        PREFIX + "-replay",
        dict(
            status="passed",
            complete_sampled_histories_bitwise=True,
            checkpoint_s=0.001,
            changed_window_ticks=17,
            pending_events_preserved=True,
        ),
    )


def test_long_complete_world_partition_and_reverse_merge(histories):
    value = histories["resealing"]
    parts = []
    for world in reversed(range(value.spec.pool.worlds)):
        raw = bind_definition(
            value.spec.to_dict(), worlds=1, world_id_start=world, seed=value.spec.pool.seed
        )
        part = collect(f"world-{world}", parse_spec(raw))
        parts.append((world, part))
    ordered = [p for _, p in sorted(parts)]
    merged = jax.tree.map(lambda *v: np.concatenate(v), *(p.final for p in ordered))
    same(value.final, merged)
    assert all(len(p.snapshots) == len(value.snapshots) for p in ordered)
    for i, expected in enumerate(value.snapshots):
        joined = jax.tree.map(lambda *v: np.concatenate(v), *(p.snapshots[i] for p in ordered))
        same(expected, joined)
    evidence(
        PREFIX + "-worlds",
        dict(
            status="passed",
            complete_sampled_histories_bitwise=True,
            world_ids=[0, 1],
            executed_in_reverse_order=True,
        ),
    )


def test_long_cpu_gpu_coupled_snapshots_and_functional_labels(histories):
    if BACKEND == "cpu":
        pytest.skip("Requires complete CPU references before the L4 phase")
    count = 0
    for arm, value in histories.items():
        directory = Path(EVIDENCE) / "cpu"
        assert (
            json.loads((directory / (PREFIX + "-trajectory-" + arm + ".json")).read_text())[
                "status"
            ]
            == "passed"
        )
        for suffix, actual in (("states", value.observed), ("final", flatten(value.final))):
            name = PREFIX + "-" + arm + "-" + suffix
            receipt = json.loads((directory / (name + ".json")).read_text())
            assert receipt["inputs"] == fixtures.normalized(value.spec.to_dict())
            with np.load(directory / (name + ".npz"), allow_pickle=False) as archive:
                count += compare_backend(actual, archive)
        for world in range(value.spec.pool.worlds):
            name = PREFIX + f"-errors-{arm}-world-{value.spec.pool.world_id_start + world}"
            actual = fixtures.measurements(value.spec, value.observed, world)
            with np.load(directory / (name + ".npz"), allow_pickle=False) as archive:
                saved = {k: archive["measured_" + k] for k in actual}
                count += compare_backend(actual, saved)
    cpu = json.loads((Path(EVIDENCE) / "cpu" / (PREFIX + "-functional.json")).read_text())
    gpu = json.loads((Path(EVIDENCE) / "gpu" / (PREFIX + "-functional.json")).read_text())
    assert cpu["status"] == gpu["status"] == "passed"
    for name in cpu["results"]:
        assert (
            cpu["results"][name]["observed"]["classification"]
            == gpu["results"][name]["observed"]["classification"]
        )
    evidence(
        PREFIX + "-cpu-gpu",
        dict(
            status="passed",
            scalar_values=count,
            recovery_labels_identical=True,
            unit_specific_tolerances_unchanged=True,
        ),
    )
