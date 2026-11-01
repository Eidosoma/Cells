"""No actual caller/source operations: immutable metadata and API order only."""

from contextlib import nullcontext
from types import SimpleNamespace as NS
from typing import NamedTuple

import pytest

from validation.betse import native_tissue_to_grid_qualification as q


def test_fixed_plan_binds_world_prerequisites_probe_policy_and_original_limits():
    value = q._fixed()
    assert value["world_owner_prerequisites"] == ["poisson", "six_store_data_tail"]
    assert value["probe_policy"]["names"] == ["grid_1d", "grid_2d", "points_1d", "points_2d"]
    assert value["limits"] == dict(timeout=480, max_rss_bytes=2**30, min_available_bytes=8 * 2**30)
    assert value["execution_stages"] == list(q.STAGES)
    assert len(q.STAGES) == 11 and value["scientific_qualification"] is False


@pytest.mark.parametrize(
    "changed", ["probe_policy", "execution_stages", "world_owner_prerequisites", "limits"]
)
def test_widened_or_relabelled_plan_refuses_before_source(monkeypatch, tmp_path, changed):
    plan = dict(q._fixed(), cpu=6)
    plan[changed] = []
    monkeypatch.setattr(q.shared, "output_path", lambda p: tmp_path)
    monkeypatch.setattr(q.source_snapshot, "digest", lambda p: "digest")
    monkeypatch.setattr(q.shared, "read", lambda p: plan)
    with pytest.raises(ValueError, match="plan"):
        q.verify_plan(tmp_path, "digest")


def api_chain(monkeypatch, fail=None):
    calls = []
    streams = dict(identity="actual typed synthetic MT")
    env_owner = NS(trial=NS(cache="actual prior cache", source_completed=True))
    poisson_owner = NS(trial=NS(source_completed=True))
    tail_owner = NS(trial=NS(source_completed=True, stream_after=streams))
    caller = NS(cell_i=[0, 1], X=object(), Y=object())
    prefix = NS(caller=caller, rng=object())
    parent = NS(trial=tail_owner.trial)
    result = NS(trial=NS(source_completed=True))

    def point(name, value):
        calls.append(name)
        if fail == name:
            raise ValueError("synthetic failure " + name)
        return value

    env = NS(prepare_continuation=lambda request: point("environment", env_owner))

    def pipeline(*a, environment, **k):
        return tuple(
            (name, lambda name=name: point(name, None)) for name in q.prefix.STAGES[:8]
        ) + ((q.prefix.STAGES[8], lambda: environment.prepare_continuation(object()).trial),)

    monkeypatch.setattr(q.prefix, "_pipeline", pipeline)

    def op_from(owner, **k):
        assert owner is env_owner
        return point("poisson_request", object())

    poisson = NS(
        LAW_ID="poisson",
        from_environment=op_from,
        prepare_continuation=lambda request: point("poisson", poisson_owner),
    )

    def tail_from(owner, **k):
        assert owner is poisson_owner
        return point("tail_request", object())

    world = NS(
        LAW_ID="tail",
        from_poisson=tail_from,
        prepare_continuation=lambda request: point("tail", tail_owner),
        _authority=lambda owner: parent if owner is tail_owner else None,
        _prefix=lambda context: prefix,
    )

    def from_world(owner, probes, **k):
        assert owner is tail_owner and [p.name for p in probes] == q.native.PROBE_POLICY["names"]
        assert probes[2].target_points[0] is caller.X
        return point("mapping_request", object())

    mapping = NS(
        LAW_ID="mapping",
        Probe=lambda **kw: NS(**kw),
        from_world=from_world,
        prepare=lambda request: point("mapping", result),
        _authority=lambda owner: NS(input_cache="retained input"),
        _request_record=lambda request: dict(actual_request=True),
        core=NS(initial=NS(_rng_stream=lambda rng: streams)),
    )
    actions = q._pipeline(
        "case",
        None,
        fixtures=None,
        initial=None,
        clipped=None,
        lifecycle=None,
        multi=None,
        environment=env,
        poisson=poisson,
        world=world,
        mapping=mapping,
    )
    return NS(
        calls=calls,
        actions=actions,
        stream=streams,
        world=world,
        poisson_trial=poisson_owner.trial,
        tail_trial=tail_owner.trial,
    )


def test_pipeline_keeps_same_fresh_owners_and_both_trials_through_eleven_phases(monkeypatch):
    h = api_chain(monkeypatch)
    results = [action() for _, action in h.actions]
    assert [name for name, _ in h.actions] == list(q.STAGES)
    assert h.calls[-7:] == [
        "environment",
        "poisson_request",
        "poisson",
        "tail_request",
        "tail",
        "mapping_request",
        "mapping",
    ]
    assert results[-1]["stream_before"] is h.stream and results[-1]["stream_after"] is h.stream
    assert results[-1]["kind"] == q.RESULT_KIND
    assert results[-2]["poisson"] is h.poisson_trial and results[-2]["tail"] is h.tail_trial


@pytest.mark.parametrize("failure", ["environment", "poisson", "tail", "mapping"])
def test_pipeline_failure_stops_before_any_later_owner_or_probe(monkeypatch, failure):
    h = api_chain(monkeypatch, failure)
    with pytest.raises(ValueError) as caught:
        for _, action in h.actions:
            action()
    assert h.calls[-1] == failure
    if failure == "tail":
        assert caught.value.source_error is caught.value.__cause__
        assert caught.value.upstream_trial is h.poisson_trial
    else:
        assert failure in str(caught.value)


def test_private_timing_extension_does_not_change_root_stage_roster(tmp_path):
    before = tuple(q.prefix.STAGES)
    work = NS(failure=None, phase=None)
    timer = q.StageTimings(tmp_path, work)
    assert timer.run("mapping_probes", "action", lambda: object()) is not None
    assert q.prefix.STAGES == before and "mapping_probes" not in q.prefix.STAGES


def test_worker_rejects_before_any_production_import_or_source(monkeypatch, tmp_path):
    primary = ValueError("release missing")

    def refuse(*a, **k):
        raise primary

    monkeypatch.setattr(q, "verify_release", refuse)
    monkeypatch.setattr(q, "_steps", lambda *a: pytest.fail("source entered"))
    with pytest.raises(ValueError) as caught:
        q.worker(tmp_path, "bad", tmp_path / "release", "case", tmp_path)
    assert caught.value is primary


def test_actual_worklog_accepts_mapping_phase_roster_without_bypassing_its_limit(tmp_path):
    recorder = q.shared.WorkLog(tmp_path, tmp_path / "source", phases=q.STAGES)
    assert recorder.phases == ("imports", *q.STAGES)
    assert len(q.STAGES) == len(q.shared.stage_names("lapENV_P_inv"))
    with pytest.raises(ValueError, match="work phases"):
        q.shared.WorkLog(tmp_path, tmp_path / "source", phases=(*q.STAGES, "extra"))


@pytest.mark.parametrize("falsey", [False, True])
def test_compound_phase_keeps_completed_poisson_and_original_tail_cause(monkeypatch, falsey):
    h = api_chain(monkeypatch)

    class Primary(ValueError):
        def __bool__(self):
            return not falsey

    original, cause = Primary("original tail failure"), RuntimeError("original tail cause")

    def reject(request):
        raise original from cause

    h.world.prepare_continuation = reject
    for _, action in h.actions[:9]:
        action()
    with pytest.raises(q.WorldDataContinuationRejected) as caught:
        h.actions[9][1]()
    assert caught.value.source_error is caught.value.__cause__ is original
    assert original.__cause__ is cause and caught.value.upstream_trial is h.poisson_trial
    assert caught.value.partial["completed_poisson_trial"] is h.poisson_trial
    assert caught.value.partial["usable_world_child_available"] is False
    assert "mapping" not in h.calls


def test_compound_failure_uses_existing_forensic_capture_for_completed_trial(tmp_path):
    class Trial(NamedTuple):
        identity: str
        source_completed: bool

    actual = Trial("a" * 64, True)
    original = ValueError("original tail failure")
    error = q.WorldDataContinuationRejected(original, actual)
    evidence = q.shared.Evidence(tmp_path, sidecars=True, capture_writer=q.prefix._write_capture)
    evidence.failure(error)
    rows = [row for row in evidence.rows if row["label"].endswith(".upstream_trial")]
    assert len(rows) == 1 and rows[0]["status"] == "saved"
    assert q.payload.read(tmp_path / rows[0]["path"]) == actual._asdict()
    assert error.source_error is original


@pytest.mark.parametrize("wall", [480, 1800])
def test_diagnostic_wall_modes_change_only_time_and_preserve_software_default(wall):
    limits = q._fixed(wall)["limits"]
    assert limits == dict(timeout=wall, max_rss_bytes=2**30, min_available_bytes=8 * 2**30)
    assert q._fixed()["limits"]["timeout"] == 480


@pytest.mark.parametrize("wall", [True, 480.0, 0, 479, 481, 1799, 1801, "1800", None])
def test_unknown_wall_modes_refuse_before_preparation(wall):
    with pytest.raises(ValueError, match="diagnostic wall allowance"):
        q._fixed(wall)


@pytest.mark.parametrize("changed", ["max_rss_bytes", "min_available_bytes", "extra"])
def test_valid_long_wall_cannot_widen_other_limits(tmp_path, monkeypatch, changed):
    plan = dict(q._fixed(1800), cpu=6)
    plan["limits"][changed] = 0
    monkeypatch.setattr(q.shared, "output_path", lambda p: tmp_path)
    monkeypatch.setattr(q.source_snapshot, "digest", lambda p: "digest")
    monkeypatch.setattr(q.shared, "read", lambda p: plan)
    with pytest.raises(ValueError, match="mapping plan"):
        q.verify_plan(tmp_path, "digest")


@pytest.mark.parametrize("late", [False, True])
def test_supervisor_retains_own_controller_primary_and_cause(tmp_path, monkeypatch, late):
    output = tmp_path / "supervised"
    plan = dict(runtime_paths=[])
    original, cause = ValueError("controller original"), RuntimeError("controller cause")
    monkeypatch.setattr(q, "verify_plan", lambda *a: plan)
    monkeypatch.setattr(q.shared, "execution_output", lambda *a: output)

    def reject(*a):
        if late:
            output.mkdir()
        raise original from cause

    monkeypatch.setattr(q, "launch", reject)
    monkeypatch.setattr(q.prefix, "launch", lambda *a: pytest.fail("Root launcher entered"))
    with pytest.raises(ValueError) as caught:
        q.supervised_launch("prepared", "sha", "release", "case", output)
    assert caught.value is original and original.__cause__ is cause
    record = q.shared.read(output / "controller-failure.json")
    assert record["stage"] == "controller" and record["automatic_retry"] is False


def test_supervisor_preserves_success_and_refuses_existing_output(tmp_path, monkeypatch):
    output = tmp_path / "supervised"
    result = {"actual": "same return"}
    monkeypatch.setattr(q, "verify_plan", lambda *a: dict(runtime_paths=[]))
    monkeypatch.setattr(q.shared, "execution_output", lambda *a: output)
    monkeypatch.setattr(q, "launch", lambda *a: result)
    assert q.supervised_launch("prepared", "sha", "release", "case", output) is result
    output.mkdir()
    with pytest.raises(ValueError, match="fresh supervised"):
        q.supervised_launch("prepared", "sha", "release", "case", output)


def test_supervisor_capture_failure_does_not_replace_controller_primary(tmp_path, monkeypatch):
    output = tmp_path / "supervised"
    primary, capture = ValueError("original"), OSError("failure archive full")
    monkeypatch.setattr(q, "verify_plan", lambda *a: dict(runtime_paths=[]))
    monkeypatch.setattr(q.shared, "execution_output", lambda *a: output)

    def reject(*a):
        raise primary

    def failed_write(*a):
        raise capture

    monkeypatch.setattr(q, "launch", reject)
    with monkeypatch.context() as failure_patch:
        failure_patch.setattr(q.shared, "write", failed_write)
        with pytest.raises(ValueError) as caught:
            q.supervised_launch("prepared", "sha", "release", "case", output)
    assert caught.value is primary and primary.controller_capture_error is capture


def test_supervisor_checks_output_domain_before_creating_failure_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr(q, "verify_plan", lambda *a: dict(runtime_paths=[]))
    primary = ValueError("unsafe output domain")

    def reject(*a):
        raise primary

    monkeypatch.setattr(q.shared, "execution_output", reject)
    monkeypatch.setattr(q, "launch", lambda *a: pytest.fail("controller launched"))
    with monkeypatch.context() as failure_patch:
        failure_patch.setattr(
            q.shared, "write", lambda *a: pytest.fail("failure output preceded domain check")
        )
        with pytest.raises(ValueError) as caught:
            q.supervised_launch("prepared", "sha", "release", "case", tmp_path)
    assert caught.value is primary


@pytest.mark.parametrize("failure", ["runtime", "end_pin"])
def test_postprocessing_failure_retains_completed_source_without_relabelling(
    tmp_path, monkeypatch, failure
):
    from validation.betse import native_tissue_to_grid_compare as compare

    source = tmp_path / "prepared/source"
    source.mkdir(parents=True)
    output = tmp_path / "output"
    output.mkdir()
    plan = dict(interpreter=str(q.sys.executable))
    monkeypatch.setattr(q, "ROOT", source)
    monkeypatch.setattr(q, "verify_release", lambda *a: plan)
    monkeypatch.setattr(q.shared, "execution_output", lambda *a: output)
    monkeypatch.setattr(
        q, "resource", NS(RLIMIT_AS=q.resource.RLIMIT_AS, setrlimit=lambda *a: None)
    )

    class Work:
        phase = "mapping_probes"
        failure = None
        count = 7

        def __init__(self, *a, **k):
            pass

        def active(self):
            return nullcontext()

    monkeypatch.setattr(q.shared, "WorkLog", Work)
    monkeypatch.setattr(q, "StageTimings", lambda *a: NS(steps=lambda steps: steps, failures=[]))
    monkeypatch.setattr(q.shared, "Evidence", lambda *a, **k: None)
    evidence = NS(
        rows=[dict(path="capture.json", label="mapping_probes")], failure=lambda error: None
    )
    monkeypatch.setattr(q, "TimedEvidence", lambda *a: evidence)
    monkeypatch.setattr(q, "_steps", lambda *a: ())
    primary = dict(
        status="source_completed_unqualified",
        completed_stages=list(q.STAGES),
        failed_stage=None,
        source_error=None,
        observer_error=None,
        captures=evidence.rows,
    )
    monkeypatch.setattr(q.shared, "run_stages", lambda *a: dict(primary))
    monkeypatch.setattr(q.prefix, "read_capture", lambda *a: {"retained": "metadata"})
    monkeypatch.setattr(compare, "diagnostics", lambda *a: {"domain_gate": False})

    def refuse(*a):
        raise OSError("postprocessing " + failure)

    monkeypatch.setattr(
        q.shared, "runtime_inventory", refuse if failure == "runtime" else lambda *a: {}
    )
    monkeypatch.setattr(q, "verify_plan", refuse if failure == "end_pin" else lambda *a: plan)
    assert q.worker(source.parent, "digest", output / "release", "case", output) == 1
    saved = q.shared.read(output / "diagnostic.json")
    assert saved["source_error"] is None and saved["postprocessing_error"] is not None
    assert saved["completed_stages"] == list(q.STAGES)
    assert saved["prior_result"]["status"] == "source_completed_unqualified"
    assert saved["accepted_cases"] == 0
