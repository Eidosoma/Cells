"""Native-blocked orchestration controls for the fresh ordinary diagnostic."""

import copy
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from validation.betse import native_multi_cell_environment_qualification as q


def chain(fail=None):
    calls, seen = [], {}
    initial_request, clip_request, life_request = object(), object(), object()
    initial_state = NS(status="source_completed_unqualified")
    clip_state = NS(status="source_clipped_rebuilt_unqualified")
    life_state = NS(status="source_lifecycle_completed_unqualified")
    ordinary = NS(caller_request=object())
    caller = NS(trial=NS(source_completed=True))
    env_request = object()
    environment = NS(trial=NS(source_completed=True))

    def call(name, result):
        def action(*args, **kwargs):
            calls.append(name)
            seen[name] = (args, kwargs)
            if fail == name:
                raise ValueError("original " + name)
            return result

        return action

    def forbidden(*a, **k):
        raise AssertionError("Legacy scalar-only caller request forbidden")

    raw = dict(lifecycle_case=q.CASES[0], native_option_recipe=None, controls=q.CONTROLS)
    modules = dict(
        fixtures=NS(declaration=call("fixture", (initial_request, raw))),
        initial=NS(prepare=call("initial", initial_state)),
        clipped=NS(
            from_initial_mesh=call("clip_request", clip_request), prepare=call("clip", clip_state)
        ),
        lifecycle=NS(
            from_clipped=call("lifecycle_request", life_request),
            prepare=call("lifecycle", life_state),
        ),
        multi=NS(from_lifecycle=forbidden, prepare=call("caller", caller)),
        environment=NS(
            LAW_ID="synthetic ordinary",
            from_lifecycle=call("ordinary_request", ordinary),
            from_caller=call("continuation_request", env_request),
            prepare_continuation=call("ordinary", environment),
        ),
    )
    return (
        modules,
        calls,
        seen,
        NS(life=life_state, request=ordinary, caller=caller, env=environment),
    )


def test_fresh_descriptor_request_precedes_actual_caller_and_same_owner_continuation(tmp_path):
    modules, calls, seen, objects = chain()
    steps = q._pipeline(q.CASES[0], tmp_path, **modules)
    results = [action() for _, action in steps]
    assert [name for name, _ in steps] == list(q.STAGES)
    assert calls == [
        "fixture",
        "initial",
        "clip_request",
        "clip",
        "lifecycle_request",
        "lifecycle",
        "ordinary_request",
        "caller",
        "continuation_request",
        "ordinary",
    ]
    assert results[0]["configuration"] == q.configuration()
    assert seen["ordinary_request"][0][1] is objects.life
    assert seen["ordinary_request"][0][2] == q.configuration()
    assert seen["caller"][0] == (objects.request.caller_request,)
    assert seen["continuation_request"][0] == (objects.caller,)
    assert results[-1] is objects.env.trial


@pytest.mark.parametrize(
    "stage", ["initial", "clip", "lifecycle", "ordinary_request", "caller", "ordinary"]
)
def test_original_stage_refusal_stops_without_later_delegate(tmp_path, stage):
    modules, calls, _, _ = chain(stage)
    for _, action in q._pipeline(q.CASES[0], tmp_path, **modules):
        try:
            action()
        except ValueError as error:
            assert str(error) == "original " + stage
            break
    else:
        raise AssertionError("Expected source refusal")
    assert calls[-1] == stage and calls.count(stage) == 1


@pytest.mark.parametrize("which", ["caller", "env"])
def test_partial_trial_never_becomes_completed(tmp_path, which):
    modules, calls, _, objects = chain()
    getattr(objects, which).trial.source_completed = False
    with pytest.raises(q.prior.PrerequisiteRejected) as caught:
        for _, action in q._pipeline(q.CASES[0], tmp_path, **modules):
            action()
    assert caught.value.trial is getattr(objects, which).trial
    assert calls[-1] == ("caller" if which == "caller" else "ordinary")


def test_failed_capture_stops_before_next_source_and_keeps_completed_work():
    calls = []
    evidence = NS(rows=[], save=lambda label, value: False, failure=lambda error: None)
    work = NS(phase=None, count=1, failure=None)
    result = q.shared.run_stages(
        (("first", lambda: calls.append("first")), ("second", lambda: calls.append("second"))),
        evidence,
        work,
    )
    assert calls == ["first"] and result["failed_stage"] == "first:capture"
    assert result["source_error"] is None and result["accepted_cases"] == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("stop_after", "lapENV_P_inv"),
        ("allow_actual_source_diagnostic", False),
        ("scientific_qualification", True),
        ("kind", q.prior.KINDS[1]),
    ],
)
def test_release_cannot_widen_endpoint_or_reuse_legacy_grant(monkeypatch, field, value):
    plan = dict(cpu=6, snapshot_sha256="a" * 64)
    grant = dict(
        kind=q.KINDS[1],
        plan_sha256="b" * 64,
        snapshot_sha256="a" * 64,
        case=q.CASES[0],
        stop_after=q.ENDPOINT,
        allow_actual_source_diagnostic=True,
        scientific_qualification=False,
        source_review=dict(path="/no/source", sha256="c" * 64),
    )
    grant[field] = value
    monkeypatch.setattr(q, "verify_plan", lambda *a: plan)
    monkeypatch.setattr(q.shared, "read", lambda p: grant)
    monkeypatch.setattr(
        q.shared, "verify_pins", lambda p: (_ for _ in ()).throw(AssertionError("No file reads"))
    )
    with pytest.raises(ValueError, match="release"):
        q.verify_release("unused", "b" * 64, "unused", q.CASES[0])


def test_default_grid_and_method_sequence_are_not_postcut_or_poisson():
    assert q.configuration()["general options"] == {"comp grid size": 25}
    assert q.native.METHODS == (
        "cellVerts",
        "cellMatrices",
        "cell_vols",
        "mem_processing",
        "near_neigh",
        "makeECM",
        "environment",
        "assign_grid_len",
        "make_maskM",
    )
    assert "intra_updater" not in q.native.METHODS
    assert q.shared.LIMITS == dict(timeout=480, max_rss_bytes=2**30, min_available_bytes=8 * 2**30)


def repair_c5_worker(tmp_path, monkeypatch, where, source_kind="complete"):
    from validation.betse import native_multi_cell_environment_compare as comparator

    source = tmp_path / "prepared/source"
    source.mkdir(parents=True)
    output = tmp_path / "output"
    output.mkdir()
    rows = [
        dict(label=stage, path=f"capture-{i:04d}.json", status="saved", sha256="a" * 64)
        for i, stage in enumerate(q.STAGES)
    ]
    baseline = dict(
        status="source_completed_unqualified",
        completed_stages=list(q.STAGES),
        failed_stage=None,
        source_error=None,
        observer_error=None,
        interrupted_exception_graph=None,
        captures=copy.deepcopy(rows),
        observed_source_entry_attempts=9,
        accepted_cases=0,
        **q.shared.NO_CREDIT,
    )
    if source_kind != "complete":
        baseline.update(
            status="diagnostic_failed",
            failed_stage="cell_index",
            completed_stages=list(q.STAGES[:7]),
        )
        error = ValueError("original source failure")
        error.__cause__ = RuntimeError("original source cause")
        graph = q.shared.exception_record(error)
        if source_kind == "source":
            baseline["source_error"] = graph
        else:
            baseline["observer_error"] = graph
            baseline["interrupted_exception_graph"] = graph

    class Evidence:
        def __init__(self, *a, **k):
            self.rows = copy.deepcopy(rows)

        def failure(self, error):
            self.rows.append(dict(label="metadata_failure_capture", status="saved"))
            if where == "runtime_capture":
                raise OSError("secondary failure recording")

    class Work:
        def __init__(self, *a, **k):
            self.phase = q.STAGES[-1]
            self.count = 9
            self.failure = None

        def active(self):
            return nullcontext()

    plan = dict(interpreter=str(Path(q.sys.executable).absolute()), runtime_paths=[])
    monkeypatch.setattr(q, "ROOT", source)
    monkeypatch.setattr(q, "verify_release", lambda *a: plan)
    monkeypatch.setattr(q.resource, "setrlimit", lambda *a: None)
    monkeypatch.setattr(q.shared, "execution_output", lambda *a: output)
    monkeypatch.setattr(q.shared, "Evidence", Evidence)
    monkeypatch.setattr(q.shared, "WorkLog", Work)
    monkeypatch.setattr(q, "_steps", lambda *a: ())

    def stages(*args):
        if where == "source_execution":
            raise ValueError("source execution exception") from RuntimeError(
                "source execution cause"
            )
        return copy.deepcopy(baseline)

    monkeypatch.setattr(q.shared, "run_stages", stages)
    monkeypatch.setattr(q.payload, "read", lambda *a: dict(cache={"synthetic": "cache"}))

    def domain(*args):
        if where == "diagnostics":
            raise OSError("post-source diagnostics failure")
        return dict(domain_gate_passed=False)

    monkeypatch.setattr(comparator, "diagnostics_from_cache", domain)

    def runtime(*args):
        if where.startswith("runtime"):
            raise OSError("post-source runtime failure")
        return {}

    monkeypatch.setattr(q.shared, "runtime_inventory", runtime)

    def verify(*args):
        if where == "pins":
            raise OSError("post-source pin failure")
        return plan

    monkeypatch.setattr(q, "verify_plan", verify)
    return source.parent, output, baseline


@pytest.mark.parametrize(
    "where,stage",
    [
        ("diagnostics", "postprocessing.saved_geometry_diagnostics"),
        ("runtime", "postprocessing.runtime_inventory"),
        ("pins", "postprocessing.end_pin_verification"),
    ],
)
def test_repair_c5_postprocessing_failure_preserves_completed_source_and_zero_credit(
    tmp_path, monkeypatch, where, stage
):
    prepared, output, baseline = repair_c5_worker(tmp_path, monkeypatch, where)
    assert q.worker(prepared, "synthetic_plan", "synthetic_release", q.CASES[0], output) == 1
    result = q.shared.read(output / "diagnostic.json")
    assert result["status"] == "diagnostic_failed" and result["accepted_cases"] == 0
    assert result["source_error"] is None and result["observer_error"] is None
    assert result["completed_stages"] == list(q.STAGES) and result["failed_stage"] == stage
    assert result["postprocessing_stage"] == stage and result["postprocessing_error"]["nodes"]
    assert result["prior_result"]["status"] == "source_completed_unqualified"
    assert result["prior_result"]["captures"] == baseline["captures"]
    assert len(result["captures"]) == len(baseline["captures"]) + 1


@pytest.mark.parametrize("source_kind", ["source", "observer"])
def test_repair_c5_metadata_failure_never_erases_an_existing_primary(
    tmp_path, monkeypatch, source_kind
):
    prepared, output, baseline = repair_c5_worker(tmp_path, monkeypatch, "runtime", source_kind)
    assert q.worker(prepared, "synthetic_plan", "synthetic_release", q.CASES[0], output) == 1
    result = q.shared.read(output / "diagnostic.json")
    for field in (
        "source_error",
        "observer_error",
        "interrupted_exception_graph",
        "completed_stages",
        "failed_stage",
    ):
        assert result[field] == baseline[field]
    assert result["postprocessing_stage"] == "postprocessing.runtime_inventory"
    assert (
        result["postprocessing_error"] is not None
        and result["prior_result"]["status"] == "diagnostic_failed"
    )


def test_repair_c5_secondary_failure_recording_has_separate_error(tmp_path, monkeypatch):
    prepared, output, baseline = repair_c5_worker(
        tmp_path, monkeypatch, "runtime_capture", "source"
    )
    assert q.worker(prepared, "synthetic_plan", "synthetic_release", q.CASES[0], output) == 1
    result = q.shared.read(output / "diagnostic.json")
    assert result["source_error"] == baseline["source_error"]
    assert (
        result["postprocessing_error"] is not None and result["failure_capture_error"] is not None
    )


def test_repair_c5_actual_source_exception_stays_a_source_error(tmp_path, monkeypatch):
    prepared, output, _ = repair_c5_worker(tmp_path, monkeypatch, "source_execution")
    assert q.worker(prepared, "synthetic_plan", "synthetic_release", q.CASES[0], output) == 1
    result = q.shared.read(output / "diagnostic.json")
    assert result["source_error"]["nodes"][0]["message"] == "source execution exception"
    assert result["source_error"]["nodes"][1]["message"] == "source execution cause"
    assert "postprocessing_error" not in result
