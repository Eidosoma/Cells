"""D037 short engineering fixtures; no long RK4 study or production integration."""

import copy
import inspect
import json
import math
import subprocess
from time import perf_counter

import numpy as np
import pytest

from scripts import audit_graph_candidate as audit
from scripts import profile_graph_candidate as profile
from tests import reference_candidate_comparison as compare
from tests import reference_graph_candidate as candidate
from tests import reference_source_pair_numerics as legacy

ref, prep = candidate.ref, compare.prep


@pytest.fixture
def protocol():
    return profile.campaign.frozen.load_protocol()


@pytest.fixture
def model():
    return prep.graph.Model(prep.preparations()["E"])


def arguments(tmp_path, protocol, width=2, end=0.037):
    return {
        "step": 0.01,
        "end": end,
        "numerics": protocol["numerics"],
        "resources": protocol["resources"] | {"window_steps": width},
        "identity": {"fixture": "short_fixed_graph_float64"},
        "artifact_root": tmp_path,
    }


def collect(folder):
    windows = [data for _, data in compare.chunks(folder)]
    return {
        "times": np.r_[windows[0]["times"][0], *[w["times"][1:] for w in windows]],
        "increments": np.vstack(
            [windows[0]["increments"][0], *[w["increments"][1:] for w in windows]]
        ),
        "coefficients": np.concatenate([w["coefficients"] for w in windows]),
        "slopes": np.concatenate([w["slopes"] for w in windows]),
    }


@pytest.mark.parametrize(
    "step,end", [(0.01, 0.037), (0.1, 0.3), (0.1, np.nextafter(0.3, 1)), (1, 0.07), (0.01, 5.12)]
)
def test_global_grid_has_exact_final_clock_and_no_window_reset(step, end):
    grid = candidate.Grid(step, end)
    points = list(grid.points())
    assert points[0] == 0 and points[-1] == end and len(points) == 2 * grid.count + 1
    assert np.all(np.diff(points) > 0)
    np.testing.assert_array_equal(points[::2], [min(i * step, end) for i in range(grid.count + 1)])
    assert points[2:] == list(grid.points(1))


@pytest.mark.parametrize(
    "step,end",
    [(0, 1), (-1, 1), (True, 1), (1, False), (np.nan, 1), (1, np.inf), (1, 0), (1e-300, 1)],
)
def test_invalid_or_unrepresentable_grid_refused(step, end):
    with pytest.raises(ValueError, match="grid"):
        candidate.Grid(step, end)


def test_grid_is_lazy_and_rejects_invalid_ticks():
    grid = candidate.Grid(0.01, 1000)
    assert inspect.isgenerator(grid.points())
    with pytest.raises(ValueError, match="tick"):
        grid.time(1.0)
    with pytest.raises(ValueError, match="tick"):
        grid.time(-1)


def test_analytic_rk4_fourth_order_and_nonautonomous_stage_clocks():
    errors = []
    for h in (0.2, 0.1, 0.05):
        y = np.array([1.0])
        for i in range(round(1 / h)):
            y, _, _ = candidate.rk4_step(lambda t, v: v, i * h, (i + 1) * h, y)
        errors.append(abs(y[0] - math.e))
    assert 14 < errors[0] / errors[1] < 17 and 14 < errors[1] / errors[2] < 17
    clocks = []

    def rhs(t, y):
        clocks.append(t)
        return np.full_like(y, t**3)

    result, slopes, c = candidate.rk4_step(rhs, 0, 1, np.array([0.0]))
    np.testing.assert_array_equal(clocks, [0, 0.5, 0.5, 1, 1])
    assert result[0] == 0.25 and slopes.shape == (5, 1)
    assert c[0, 0] == 0 and c[:, 0].sum() == 0.25
    with pytest.raises(ValueError, match="interval"):
        candidate.rk4_step(rhs, 1, 1, result)


@pytest.mark.parametrize("width", [1, 2, 3, 16, 256])
def test_short_graph_matches_original_rk4_arithmetic_and_cubic(tmp_path, model, protocol, width):
    args = arguments(tmp_path, protocol, width)
    report = candidate.integrate(model, tmp_path / "candidate", **args)

    class Adapter:
        end, starts = args["end"], [0]

        def initial(self):
            return np.zeros(model.coordinates.size)

        def slot(self, time):
            return 0

        def derivative(self, value, slot):
            return model.derivative(value, increments=True)

    times, values, slopes, _ = legacy.integrate_rk4(Adapter(), args["step"])
    data = collect(tmp_path / "candidate")
    np.testing.assert_array_equal(data["times"], times)
    np.testing.assert_array_equal(data["increments"], values)
    np.testing.assert_array_equal(data["slopes"][:, [0, 4]], slopes)
    np.testing.assert_array_equal(
        data["coefficients"], legacy.cubic_coefficients(times, values, slopes)
    )
    assert report["steps"] == 4 and report["rhs_calls"] == 20
    assert report["chunks"] == math.ceil(4 / width)
    expected = candidate.contract(
        model, candidate.Grid(args["step"], args["end"]), args["numerics"], args["identity"]
    )
    checked = audit.audit_trajectory(
        tmp_path / "candidate", expected, args["resources"], model.panel, perf_counter() + 60
    )
    assert checked["steps"] == 4 and checked["maximum_accounting_residual"] < 2e-9


def test_complete_checkpoint_restart_changes_only_recording_windows(tmp_path, model, protocol):
    args = arguments(tmp_path, protocol, width=2, end=0.071)
    candidate.integrate(model, tmp_path / "parent", **args)
    contract = candidate.contract(
        model, candidate.Grid(args["step"], args["end"]), args["numerics"], args["identity"]
    )
    carry = candidate.load_checkpoint(tmp_path / "parent", 0, contract)
    assert carry["tick"] == 2 and carry["time"] == 0.02
    resumed = args | {"resources": args["resources"] | {"window_steps": 3}, "initial": carry}
    candidate.integrate(model, tmp_path / "resumed", **resumed)
    a, b = collect(tmp_path / "parent"), collect(tmp_path / "resumed")
    for name in a:
        np.testing.assert_array_equal(a[name][2:], b[name])
    checked = audit.audit_trajectory(
        tmp_path / "resumed", contract, resumed["resources"], model.panel, perf_counter() + 60
    )
    assert checked["steps"] == 6
    changed = copy.deepcopy(carry)
    changed["increments"][0] += 1
    with pytest.raises(ValueError, match="carry was changed"):
        candidate.integrate(model, tmp_path / "tampered", **(resumed | {"initial": changed}))
    with pytest.raises(ValueError, match="identity differs"):
        candidate.load_checkpoint(tmp_path / "parent", 0, contract | {"step": 0.02})
    with pytest.raises(ValueError, match="recorded boundary"):
        candidate.load_checkpoint(tmp_path / "parent", 99, contract)


@pytest.mark.parametrize(
    "case",
    [
        "E_to_M/active",
        "M_to_E/active",
        "E_to_M/one_neighbor",
        "M_to_E/one_neighbor",
        "M_to_E/blocked",
    ],
)
def test_graph_stage_and_cubic_audit_covers_edges_and_complete_typed_histories(
    tmp_path, protocol, case
):
    registered = ref.read_json(profile.PANEL / "registration.json")
    model = prep.graph.Model(registered["cases"][case])
    args = arguments(tmp_path, protocol, width=2)
    candidate.integrate(model, tmp_path / "candidate", **args)
    expected = candidate.contract(
        model, candidate.Grid(args["step"], args["end"]), args["numerics"], args["identity"]
    )
    checked = audit.audit_trajectory(
        tmp_path / "candidate", expected, args["resources"], model.panel, perf_counter() + 60
    )
    assert checked["steps"] == 4 and checked["maximum_accounting_residual"] < 2e-9


def test_candidate_samples_copy_exact_endpoints_and_match_legacy(tmp_path, model, protocol):
    args = arguments(tmp_path, protocol, width=16)
    candidate.integrate(model, tmp_path / "candidate", **args)
    data = collect(tmp_path / "candidate")
    times = np.unique(np.r_[data["times"], [0.003, 0.014, 0.028, 0.035]])
    expected = legacy.sample_cubic(data["times"], data["increments"], data["coefficients"], times)
    np.testing.assert_array_equal(candidate.sample_window(data, times), expected)
    np.testing.assert_array_equal(candidate.sample_window(data, data["times"]), data["increments"])
    assert candidate.sample_window(data, []).shape == (0, model.coordinates.size)
    for bad in ([-0.001], [0.038], [0.02, 0.01], [np.nan], [[0.01]]):
        with pytest.raises(ValueError, match="sample outside"):
            candidate.sample_window(data, bad)


@pytest.mark.parametrize(
    "setting,value,match",
    [
        ("window_steps", 0, "width"),
        ("window_steps", 257, "width"),
        ("window_steps", True, "width"),
        ("max_steps_per_trajectory", 1, "step budget"),
        ("estimated_array_budget_bytes", 1, "array estimate"),
        ("worker_timeout_seconds", -1, "wall budget"),
        ("artifact_budget_bytes", 100, "budget"),
    ],
)
def test_budget_refusals_retain_failure_without_retry(
    tmp_path, model, protocol, setting, value, match
):
    args = arguments(tmp_path, protocol)
    args["resources"][setting] = value
    with pytest.raises((ValueError, ref.BudgetExceeded), match=match):
        candidate.integrate(model, tmp_path / "refused", **args)
    failed = ref.read_json(tmp_path / "refused/failure.json")
    assert failed["steps"] == 0 and not failed["long_time_step_selected"]
    assert not (tmp_path / "refused/trajectory.json").exists()


def test_bad_second_step_keeps_first_accepted_carry_and_failing_input(
    tmp_path, model, protocol, monkeypatch
):
    original = model.derivative
    calls = 0

    def broken(value, *, increments):
        nonlocal calls
        calls += 1
        return np.full_like(value, np.nan) if calls == 7 else original(value, increments=increments)

    monkeypatch.setattr(model, "derivative", broken)
    with pytest.raises(ValueError, match="Nonfinite"):
        candidate.integrate(model, tmp_path / "failed", **arguments(tmp_path, protocol, width=16))
    failed = ref.read_json(tmp_path / "failed/failure.json")
    assert failed["accepted_tick"] == 1 and failed["steps"] == 1 and failed["completed_chunks"] == 1
    _, data = next(compare.chunks(tmp_path / "failed"))
    with np.load(tmp_path / "failed/last-evaluation.npz", allow_pickle=False) as saved:
        assert saved["accepted_time"] == 0.01 and saved["time"] == 0.015
        np.testing.assert_array_equal(saved["accepted_increments"], data["increments"][-1])
        assert not np.array_equal(saved["increments"], saved["accepted_increments"])


def test_exclusive_output_and_payload_tamper(tmp_path, model, protocol):
    args = arguments(tmp_path, protocol)
    candidate.integrate(model, tmp_path / "candidate", **args)
    hashes = profile.previous.payload_hashes(tmp_path / "candidate")
    with pytest.raises(FileExistsError):
        candidate.integrate(model, tmp_path / "candidate", **args)
    assert hashes == profile.previous.payload_hashes(tmp_path / "candidate")
    (tmp_path / "candidate/chunk-000000.npz").write_bytes(b"corrupted fixture")
    with pytest.raises(ValueError, match="chunk identity"):
        list(compare.chunks(tmp_path / "candidate"))


def test_whole_curve_overshoot_and_blocked_histories_are_checked(model):
    curve = np.zeros((3, model.coordinates.size))
    curve[1, [0, model.coordinates.leak.start]] = -60
    curve[2, [0, model.coordinates.leak.start]] = 60
    candidate.check_state(model, curve[0], 2e-9)
    candidate.check_state(model, curve.sum(axis=0), 2e-9)
    with pytest.raises(ValueError):
        ref.check_curve(model, curve)
    with pytest.raises(ValueError, match="domain"):
        audit.old.check_coefficients(curve, model.case, model.panel)
    case = copy.deepcopy(model.case)
    case["controls"]["leak"][0][0] = 0
    blocked = prep.graph.Model(case)
    value = np.zeros(blocked.coordinates.size)
    value[[0, 2, blocked.coordinates.leak.start, blocked.coordinates.leak.start + 2]] = 1
    with pytest.raises(ValueError, match="Blocked"):
        candidate.check_state(blocked, value, 2e-9)


@pytest.fixture(scope="module")
def short_references(tmp_path_factory):
    root = tmp_path_factory.mktemp("candidate-references")
    protocol = profile.campaign.frozen.load_protocol()
    case = prep.preparations()["E"]
    selected = {
        "case": case,
        "duration": 0.08,
        "methods": {k: list(v) for k, v in profile.campaign.METHODS.items()},
        "numerics": protocol["numerics"],
    }
    directories = {}
    for key, (method, refinement) in selected["methods"].items():
        directories[key] = root / key
        candidate.paths.integrate(
            prep.graph.Model(case),
            root / key,
            method=method,
            refinement=refinement,
            duration=selected["duration"],
            numerics=selected["numerics"],
            resources=protocol["resources"] | {"window_steps": 2},
            artifact_root=root,
        )
    return directories, selected


def test_full_comparison_short_prefix_grid_observers_scores_and_width_identity(
    tmp_path, model, protocol, short_references
):
    directories, selected = short_references
    checked = []
    for width in (1, 3, 16):
        args = arguments(tmp_path, protocol, width, end=0.057)
        output = tmp_path / str(width)
        observations = [0, 0.013, 0.031, 0.057]
        consumer = compare.Comparison(
            directories, selected, output, tmp_path, args["resources"], observations
        )
        result = candidate.integrate(model, output, comparison=consumer, **args)
        assert (
            result["comparison"]["status"] == "pass"
            and result["comparison"]["observer_samples"] == 4
        )
        assert all(reader._iterator.gi_frame is None for reader in consumer.readers.values())
        checked.append(
            audit.audit_samples(
                output, directories, selected, observations, args["resources"], perf_counter() + 60
            )
        )
    assert len({r["ordered_sample_arrays_sha256"] for r in checked}) == 1
    assert len({r["samples"] for r in checked}) == 1


def test_comparison_refuses_wrong_full_reference_identity(
    tmp_path, model, protocol, short_references
):
    directories, selected = short_references
    args = arguments(tmp_path, protocol)
    consumer = compare.Comparison(
        directories,
        selected | {"duration": 0.07},
        tmp_path / "bad",
        tmp_path,
        args["resources"],
        [0, 0.037],
    )
    with pytest.raises(ValueError, match="trajectory identity differs"):
        candidate.integrate(model, tmp_path / "bad", comparison=consumer, **args)
    assert ref.read_json(tmp_path / "bad/failure.json")["steps"] == 0


def test_comparison_failure_closes_streams_and_keeps_accepted_chunk(
    tmp_path, model, protocol, short_references, monkeypatch
):
    directories, selected = short_references
    args = arguments(tmp_path, protocol)
    consumer = compare.Comparison(
        directories, selected, tmp_path / "bad", tmp_path, args["resources"], [0, 0.037]
    )
    monkeypatch.setattr(compare.prep, "comparison_scores", lambda *args: {"ionic_state": np.nan})
    with pytest.raises(ValueError, match="Nonfinite candidate comparison"):
        candidate.integrate(model, tmp_path / "bad", comparison=consumer, **args)
    assert all(reader._iterator.gi_frame is None for reader in consumer.readers.values())
    failed = ref.read_json(tmp_path / "bad/failure.json")
    assert failed["steps"] == 2 and failed["completed_chunks"] == 1


def test_failed_accuracy_stops_without_step_refinement(
    tmp_path, model, protocol, short_references, monkeypatch
):
    directories, selected = short_references
    args = arguments(tmp_path, protocol)
    consumer = compare.Comparison(
        directories, selected, tmp_path / "bad", tmp_path, args["resources"], [0, 0.037]
    )
    monkeypatch.setattr(compare.prep, "comparison_scores", lambda *args: {"ionic_state": 2.0})
    with pytest.raises(ValueError, match="reference disagreement"):
        candidate.integrate(model, tmp_path / "bad", comparison=consumer, **args)
    result = ref.read_json(tmp_path / "bad/comparison/comparison.json")
    assert result["status"] == "disagreement" and result["maximum_score"] == 2
    assert not (tmp_path / "bad/trajectory.json").exists()


def test_real_preregistered_scope_selected_trios_and_aggregate_budget():
    r = profile.specification(profile.OUTPUT_PARENT / "engineering-01")
    assert len(r["planned_attempts"]) == 12 and r["plan"]["duration"] == 5.12
    assert r["plan"]["steps_per_profile"] == 512 and not r["plan"]["long_study_run"]
    assert r["storage_budget"]["prior_bytes"] == 762443122
    assert r["storage_budget"]["new_root_limit_bytes"] == 311298702
    assert len(r["production_source_hashes"]) == 39 and len(profile.SOURCES) == 48
    for case, value in r["cases"].items():
        assert value["selected"]["duration"] == (500 if case.startswith("prepare_") else 1000)
        assert len(value["trajectories"]) == 3
    assert "bdf_tight" in r["cases"]["M_to_E/one_neighbor"]["trajectories"]
    assert "bdf" in r["cases"]["M_to_E/active"]["trajectories"]
    assert r["observation_times"] == [0, 0.113, 0.613, 1, 2, 3, 4, 5, 5.12]


def test_prior_closeout_tamper_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(profile, "ROOT", tmp_path)
    (tmp_path / "reports").mkdir()
    ref.write_json(tmp_path / profile.CLOSEOUT, {"status": "pass"})
    with pytest.raises(ValueError, match="Frozen input changed"):
        profile.evidence()


def test_storage_refuses_sibling_links_and_no_quota_reset(tmp_path, monkeypatch):
    parent = tmp_path / "profiles"
    monkeypatch.setattr(profile, "OUTPUT_PARENT", parent)
    monkeypatch.setattr(profile, "ROOT", tmp_path)
    monkeypatch.setattr(profile, "PRIOR_ROOTS", [])
    output = parent / "only"
    assert profile.storage(output, 100, 10_000_000)["new_root_limit_bytes"] == 9_999_900
    with pytest.raises(ref.BudgetExceeded, match="Aggregate"):
        profile.storage(output, 100, candidate.paths.TAIL_RESERVE)
    parent.mkdir()
    (parent / "unexpected").mkdir()
    with pytest.raises(ValueError, match="Unexpected"):
        profile.storage(output, 100, 10_000_000)


def test_candidate_audit_does_not_recompute_rhs_or_use_online_curve_sampler():
    source = inspect.getsource(audit)
    assert ".derivative(" not in source and ".evaluate(" not in source
    assert "candidate.rk4_step(" not in source and "candidate.sample_window(" not in source
    assert "ref.check_curve(" not in source
    assert "old.check_coefficients(" in source


@pytest.mark.parametrize("field", ["slopes", "coefficients", "increments", "ticks", "context"])
def test_independent_audit_rejects_rehashed_numerical_tamper(tmp_path, model, protocol, field):
    args = arguments(tmp_path, protocol)
    folder = tmp_path / "candidate"
    candidate.integrate(model, folder, **args)
    _, data = next(compare.chunks(folder))
    data[field].flat[-1] += 1
    # Deliberately forge the local checksums: the algebra/clock/context audit
    # must catch this separately from the real campaign's immutable root hashes.
    with (folder / "chunk-000000.npz").open("wb") as handle:
        np.savez_compressed(handle, **data)
    index = [json.loads(line) for line in (folder / "chunks.jsonl").read_text().splitlines()]
    index[0]["sha256"] = ref.sha(folder / "chunk-000000.npz")
    (folder / "chunks.jsonl").write_text("".join(json.dumps(entry) + "\n" for entry in index))
    report = ref.read_json(folder / "trajectory.json")
    report["index_sha256"] = ref.sha(folder / "chunks.jsonl")
    (folder / "trajectory.json").write_text(json.dumps(report))
    expected = candidate.contract(
        model, candidate.Grid(args["step"], args["end"]), args["numerics"], args["identity"]
    )
    with pytest.raises((ValueError, AssertionError)):
        audit.audit_trajectory(
            folder, expected, args["resources"], model.panel, perf_counter() + 60
        )


@pytest.fixture
def registration_fixture(tmp_path, monkeypatch, protocol):
    source = tmp_path / "fixture.txt"
    source.write_text("immutable fixture source\n")
    spec = {
        "resources": protocol["resources"],
        "runtime": prep.runtime(),
        "planned_attempts": ["first/window-016", "second/window-016"],
    }
    monkeypatch.setattr(profile, "ROOT", tmp_path)
    monkeypatch.setattr(profile, "SOURCES", ["fixture.txt"])
    monkeypatch.setattr(profile, "specification", lambda output: copy.deepcopy(spec))
    for key, value in profile.campaign.THREADS.items():
        monkeypatch.setenv(key, value)
    return tmp_path / "new", source


def test_registration_roundtrip_archive_identity_and_exclusivity(registration_fixture):
    output, source = registration_fixture
    registered = profile.register(output)
    assert profile.check_registration(output) == registered
    with pytest.raises(FileExistsError):
        profile.register(output)
    source.write_text("changed fixture source\n")
    with pytest.raises(ValueError, match="source identity"):
        profile.check_registration(output)


@pytest.mark.parametrize("timeout", [False, True])
def test_orchestrator_stops_first_failure_or_timeout_without_retry(
    registration_fixture, monkeypatch, timeout
):
    output, _ = registration_fixture
    called = []

    def run(command, **kwargs):
        called.append(command)
        if timeout:
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(profile.subprocess, "run", run)
    with pytest.raises((ValueError, subprocess.TimeoutExpired)):
        profile.run(output)
    failed = ref.read_json(output / "failure.json")
    assert len(called) == 1 and failed["not_started"] == ["second/window-016"]
    assert failed["no_automatic_retry"] and not failed["long_study_run"]
    assert not (output / "verification.json").exists()
    with pytest.raises(ValueError, match="Closed engineering session"):
        profile.worker(output, "second/window-016")
