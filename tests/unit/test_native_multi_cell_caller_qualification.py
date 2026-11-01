"""Stdlib orchestration checks; no scientific fixture or native entry."""

import importlib.abc
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from validation.betse import native_multi_cell_caller_qualification as runner


@pytest.fixture(autouse=True)
def no_science():
    attempts = []

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {
                "cells",
                "betse",
                "numpy",
                "scipy",
                "PIL",
                "jax",
                "jaxlib",
            }:
                attempts.append(fullname)
                raise AssertionError("Scientific import forbidden: " + fullname)

    block = Block()
    sys.meta_path.insert(0, block)
    try:
        yield
    finally:
        sys.meta_path.remove(block)
    assert attempts == []


@pytest.fixture
def packet(tmp_path, monkeypatch):
    repository, base = tmp_path / "repo", tmp_path / "outputs"
    repository.mkdir()
    base.mkdir()
    native = base / "native"
    native.mkdir()
    defaults = native / "defaults.yaml"
    defaults.write_text("# synthetic defaults: metadata only\n")
    originals = []
    files = {runner.OWN: "# synthetic runner source\n", runner.TEST: "# software controls\n"}
    for i, (name, prefix) in enumerate(runner.SOURCE_TABLES):
        original = native / prefix / (str(i) + ".py")
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_text("raise AssertionError('native import forbidden')\n")
        originals.append(original)
        files[name] = "NATIVE_PINS = " + repr(
            {original.name: runner.shared.pin(original)["sha256"]}
        )
    names = [*files, runner.shared.CLOSURE]
    files[runner.shared.CLOSURE] = (
        "def closure(root, starts):\n    return {name: '' for name in " + repr(names) + "}\n"
    )
    for name, text in files.items():
        path = repository / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "-c",
            "user.name=Control",
            "-c",
            "user.email=control@invalid",
            "commit",
            "-qm",
            "synthetic source",
        ],
        check=True,
    )
    monkeypatch.setattr(runner.shared, "BASE", base)
    monkeypatch.setattr(runner.shared, "NATIVE", native)
    monkeypatch.setattr(runner.shared, "DEFAULTS", defaults)
    monkeypatch.setattr(runner.shared, "DEFAULTS_SHA256", runner.shared.pin(defaults)["sha256"])
    cpu = next(iter(runner.os.sched_getaffinity(0)))
    monkeypatch.setattr(runner.os, "sched_getaffinity", lambda pid: {cpu})
    prepared = base / "prepared"
    plan = runner.prepare(prepared, repository=repository, cpu=cpu)
    sha = runner.shared.pin(prepared / "plan.json")["sha256"]
    review = base / "review.json"
    runner.shared.write(review, dict(scope="synthetic metadata only"))
    release = base / "release.json"
    runner.shared.write(
        release,
        dict(
            kind=runner.KINDS[1],
            plan_sha256=sha,
            snapshot_sha256=plan["snapshot_sha256"],
            case=runner.CASES[0],
            stop_after=runner.ENDPOINT,
            allow_actual_source_diagnostic=True,
            scientific_qualification=False,
            source_review=runner.shared.pin(review),
        ),
    )
    return SimpleNamespace(
        root=base,
        repository=repository,
        native=originals,
        defaults=defaults,
        prepared=prepared,
        plan=plan,
        sha=sha,
        cpu=cpu,
        review=review,
        release=release,
    )


def test_preparation_has_complete_source_provenance_and_no_release(packet):
    assert runner.verify_plan(packet.prepared, packet.sha) == packet.plan
    assert packet.plan["cases"] == list(runner.CASES)
    assert packet.plan["execution_stages"] == list(runner.STAGES)
    assert packet.plan["configuration"] == runner.configuration()
    assert packet.plan["git_revision"]
    assert len(packet.plan["external_inputs"]) == 4
    assert not (packet.prepared / "release.json").exists()
    assert not (packet.prepared / "source" / runner.OWN).stat().st_mode & 0o222
    assert (
        runner.verify_release(packet.prepared, packet.sha, packet.release, runner.CASES[0])
        == packet.plan
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("cases", ["caller-square-two-steps"]),
        ("stop_after", "makeECM"),
        ("fixture_controls", dict(runner.CONTROLS, single_cell=True)),
        ("configuration", {}),
        ("execution_stages", list(runner.STAGES[:-1])),
        ("scientific_qualification", True),
        ("physical_geometry_admitted", True),
        ("automatic_retry", True),
        ("limits", {**runner.shared.LIMITS, "timeout": 481}),
    ],
)
def test_changed_plan_scope_is_rejected_even_with_new_plan_hash(packet, field, value):
    plan = runner.shared.read(packet.prepared / "plan.json")
    plan[field] = value
    path = packet.prepared / "plan.json"
    path.chmod(0o644)
    path.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="Incomplete|widened"):
        runner.verify_plan(packet.prepared, runner.shared.pin(path)["sha256"])


@pytest.mark.parametrize("kind", ["source", "native", "default", "missing_pin", "incomplete"])
def test_source_or_authority_drift_refuses_before_execution(packet, kind):
    if kind == "source":
        path = packet.prepared / "source" / runner.OWN
        path.chmod(0o644)
        path.write_text("# drift\n")
    elif kind in {"native", "default"}:
        path = packet.native[2] if kind == "native" else packet.defaults
        path.write_text("# drift\n")
    elif kind == "incomplete":
        (packet.prepared / "preparation-failure.json").write_text("{}")
    else:
        plan = runner.shared.read(packet.prepared / "plan.json")
        plan["external_inputs"] = plan["external_inputs"][:-1]
        path = packet.prepared / "plan.json"
        path.chmod(0o644)
        path.write_text(json.dumps(plan))
        packet.sha = runner.shared.pin(path)["sha256"]
    with pytest.raises(ValueError):
        runner.verify_plan(packet.prepared, packet.sha)


@pytest.mark.parametrize(
    "field,value",
    [
        ("kind", runner.shared.KINDS[1]),
        ("case", runner.CASES[1]),
        ("stop_after", "makeECM"),
        ("snapshot_sha256", "wrong"),
        ("allow_actual_source_diagnostic", False),
        ("scientific_qualification", True),
    ],
)
def test_release_is_exact_case_source_and_endpoint(packet, field, value):
    release = runner.shared.read(packet.release)
    release[field] = value
    packet.release.write_text(json.dumps(release))
    with pytest.raises(ValueError, match="release"):
        runner.verify_release(packet.prepared, packet.sha, packet.release, runner.CASES[0])


def test_review_and_cpu_remain_required(packet, monkeypatch):
    monkeypatch.setattr(runner.os, "sched_getaffinity", lambda pid: {packet.cpu, packet.cpu + 1})
    with pytest.raises(ValueError, match="single CPU"):
        runner.verify_release(packet.prepared, packet.sha, packet.release, runner.CASES[0])
    monkeypatch.setattr(runner.os, "sched_getaffinity", lambda pid: {packet.cpu})
    packet.review.write_text("{}")
    with pytest.raises(ValueError, match="external"):
        runner.verify_release(packet.prepared, packet.sha, packet.release, runner.CASES[0])


def pipeline(output, case=runner.CASES[0], failure=None, failed_state=None, control_change=None):
    calls, returned = [], {}
    cause = ValueError("original synthetic source cause")
    source_error = RuntimeError("original synthetic source error")
    source_error.__cause__ = cause

    def run(stage, value):
        calls.append(stage)
        if stage == failure:
            raise source_error
        returned[stage] = value
        return value

    raw = dict(lifecycle_case=case, native_option_recipe=None, controls=dict(runner.CONTROLS))
    if control_change:
        raw["controls"].update(control_change)
    states = {
        runner.STAGES[1]: SimpleNamespace(status="source_completed_unqualified"),
        runner.STAGES[3]: SimpleNamespace(status="source_clipped_rebuilt_unqualified"),
        runner.STAGES[5]: SimpleNamespace(status="source_lifecycle_completed_unqualified"),
    }
    if failed_state in states:
        states[failed_state].status = "retained_failure"
    requests = {
        name: object()
        for name in (runner.STAGES[0], runner.STAGES[2], runner.STAGES[4], runner.STAGES[6])
    }

    def single(stage):
        def invoke(request):
            assert request is returned[runner.STAGES[runner.STAGES.index(stage) - 1]]
            return run(stage, states[stage])

        return invoke

    def pair(stage):
        def invoke(request, state, *args, **kwargs):
            index = runner.STAGES.index(stage)
            assert request is returned[runner.STAGES[index - 2]]
            assert state is returned[runner.STAGES[index - 1]]
            if stage == runner.STAGES[6]:
                assert args == (runner.configuration(),) and kwargs == {"law_id": "synthetic-law"}
            return run(stage, requests[stage])

        return invoke

    def fixture(case_id, path):
        assert case_id == case and path == output
        return run(runner.STAGES[0], requests[runner.STAGES[0]]), raw

    final = SimpleNamespace(source_completed=failed_state != runner.STAGES[-1])

    def caller(request):
        assert request is requests[runner.STAGES[6]]
        run(runner.STAGES[7], final)
        return SimpleNamespace(trial=final)

    steps = runner._pipeline(
        case,
        output,
        fixtures=SimpleNamespace(declaration=fixture),
        initial=SimpleNamespace(prepare=single(runner.STAGES[1])),
        clipped=SimpleNamespace(
            from_initial_mesh=pair(runner.STAGES[2]), prepare=single(runner.STAGES[3])
        ),
        lifecycle=SimpleNamespace(
            from_clipped=pair(runner.STAGES[4]), prepare=single(runner.STAGES[5])
        ),
        multi=SimpleNamespace(
            from_lifecycle=pair(runner.STAGES[6]), prepare=caller, LAW_ID="synthetic-law"
        ),
    )
    return SimpleNamespace(
        steps=steps,
        calls=calls,
        returned=returned,
        source_error=source_error,
        cause=cause,
        states=states,
        requests=requests,
        final=final,
    )


class Capture:
    def __init__(self, calls, fail=None):
        self.calls, self.fail, self.rows, self.errors = calls, fail, [], []

    def save(self, stage, value):
        # No next numerical action may happen before the current capture.
        assert self.calls[-1] == stage
        self.rows.append(dict(stage=stage, value=value))
        return stage != self.fail

    def failure(self, error):
        self.errors.append(error)


@pytest.mark.parametrize("case", runner.CASES)
def test_same_typed_parent_objects_flow_through_all_eight_stages(tmp_path, case):
    p = pipeline(tmp_path, case)
    captures = Capture(p.calls)
    report = runner.shared.run_stages(p.steps, captures, SimpleNamespace(count=0, failure=None))
    assert p.calls == list(runner.STAGES)
    assert report["completed_stages"] == list(runner.STAGES)
    assert captures.rows[-1]["value"] is p.final
    assert report["status"] == "source_completed_unqualified"
    assert report["accepted_cases"] == 0 and not report["scientific_qualification"]


@pytest.mark.parametrize("stage", runner.STAGES)
def test_each_source_failure_stops_with_original_error_and_no_downstream_work(tmp_path, stage):
    p = pipeline(tmp_path, failure=stage)
    captures = Capture(p.calls)
    report = runner.shared.run_stages(p.steps, captures, SimpleNamespace(count=0, failure=None))
    assert p.calls == list(runner.STAGES[: runner.STAGES.index(stage) + 1])
    assert report["failed_stage"] == stage
    assert captures.errors == [p.source_error]
    assert captures.errors[0].__cause__ is p.cause
    assert len(captures.rows) == runner.STAGES.index(stage)


@pytest.mark.parametrize("stage", runner.STAGES)
def test_each_capture_failure_stops_before_the_next_source_call(tmp_path, stage):
    p = pipeline(tmp_path)
    report = runner.shared.run_stages(
        p.steps, Capture(p.calls, fail=stage), SimpleNamespace(count=0, failure=None)
    )
    assert p.calls == list(runner.STAGES[: runner.STAGES.index(stage) + 1])
    assert report["failed_stage"] == stage + ":capture"
    assert report["completed_stages"] == list(runner.STAGES[: runner.STAGES.index(stage)])


@pytest.mark.parametrize(
    "stage", (runner.STAGES[1], runner.STAGES[3], runner.STAGES[5], runner.STAGES[7])
)
def test_failed_returned_prerequisite_is_preserved_and_not_consumed(tmp_path, stage):
    p = pipeline(tmp_path, failed_state=stage)
    captures = Capture(p.calls)
    report = runner.shared.run_stages(p.steps, captures, SimpleNamespace(count=0, failure=None))
    assert report["failed_stage"] == stage
    error = captures.errors[0]
    assert error.trial is (p.final if stage == runner.STAGES[7] else p.states[stage])
    assert error.request is p.requests[runner.STAGES[runner.STAGES.index(stage) - 1]]
    assert p.calls[-1] == stage


@pytest.mark.parametrize(
    "change",
    [
        dict(single_cell=True),
        dict(single_cell=0),
        dict(svg_override=True),
        dict(use_centroids=False),
        dict(refine_mesh=True),
        dict(maximum_voronoi_steps=10),
        dict(voronoi_convergence=2.5),
    ],
)
def test_declared_controls_cannot_silently_change_or_use_native_defaults(tmp_path, change):
    p = pipeline(tmp_path, control_change=change)
    report = runner.shared.run_stages(
        p.steps, Capture(p.calls), SimpleNamespace(count=0, failure=None)
    )
    assert report["failed_stage"] == runner.STAGES[0]
    assert p.calls == [runner.STAGES[0]]


def test_unknown_native_option_or_single_cell_case_refuses_without_fixture_work(tmp_path):
    with pytest.raises(ValueError, match="Unknown"):
        runner._pipeline(
            "caller-single-square-cache",
            tmp_path,
            fixtures=None,
            initial=None,
            clipped=None,
            lifecycle=None,
            multi=None,
        )
    raw = dict(
        lifecycle_case=runner.CASES[0], controls=dict(runner.CONTROLS), native_option_recipe={}
    )
    with pytest.raises(ValueError, match="declared"):
        runner._declaration(runner.CASES[0], raw)


def test_launch_failure_is_durable_without_starting_worker(packet, monkeypatch):
    monkeypatch.setattr(runner.shared.guard, "memory_available", lambda: 11 * 2**30)
    attempts = []
    monkeypatch.setattr(runner.shared.guard, "run_bounded", lambda *a, **k: attempts.append((a, k)))
    output = packet.root / "failed-launch"
    result = runner.launch(packet.prepared, packet.sha, packet.release, runner.CASES[0], output)
    assert result["status"] == "failed" and attempts == []
    assert (output / "failure.json").exists() and (output / "inputs.json").exists()
    assert result["accepted_cases"] == 0 and not result["automatic_retry"]


def test_worker_never_runs_from_live_checkout(packet):
    with pytest.raises(ValueError, match="immutable source"):
        runner.worker(
            packet.prepared, packet.sha, packet.release, runner.CASES[0], packet.root / "worker"
        )
