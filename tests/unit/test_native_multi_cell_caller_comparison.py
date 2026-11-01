"""Metadata and synthetic runner contracts; every real scientific entry is blocked."""

import copy
import importlib.abc
import json
import sys
from pathlib import Path

import pytest

from tests.unit import test_native_multi_cell_caller_compare as examples
from validation.betse import native_multi_cell_caller_comparison as runner


@pytest.fixture(autouse=True)
def no_science(monkeypatch):
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

    def forbidden(*args, **kwargs):
        raise AssertionError("Real source or dependency initialization forbidden")

    guard = Block()
    sys.meta_path.insert(0, guard)
    monkeypatch.setattr(runner.native, "evaluate", forbidden)
    monkeypatch.setattr(runner.runtime, "preflight", forbidden)
    monkeypatch.setattr(runner.shared.guard, "run_bounded", forbidden)
    try:
        yield
    finally:
        sys.meta_path.remove(guard)
    assert attempts == []


@pytest.fixture
def context(tmp_path, monkeypatch):
    monkeypatch.setattr(runner.shared, "BASE", tmp_path)
    monkeypatch.setattr(runner.os, "sched_getaffinity", lambda pid: {3})
    prepared, diagnostic, parent = (tmp_path / n for n in ("prepared", "diagnostic", "parent"))
    for p in (prepared, prepared / "source", diagnostic, parent):
        p.mkdir(exist_ok=True)
    captures = []
    for index, label in enumerate(runner.parent_runner.STAGES):
        path = diagnostic / f"capture-{index:04d}.json"
        path.write_text(json.dumps({"synthetic_capture": index}) + "\n")
        captures.append(
            dict(
                label=label,
                path=path.name,
                sha256=runner.shared.pin(path)["sha256"],
                status="saved",
            )
        )
    capture_pins = [
        dict(label=row["label"], **runner.shared.pin(diagnostic / row["path"])) for row in captures
    ]
    required = [runner.shared.pin(diagnostic / row["path"]) for row in captures]
    saved = dict(
        case=runner.parent_runner.CASES[0],
        parent_plan={"runtime_paths": []},
        captures=captures,
        raw={"synthetic": True},
        configuration=runner.parent_runner.configuration(),
        owned_trial={"synthetic": True},
    )
    sites = {"synthetic_site": {"first_line": 1, "last_line": 2, "ast_sha256": "c" * 64}}
    plan = dict(
        kind=runner.KINDS[0],
        purpose=runner.PURPOSE,
        case=saved["case"],
        stop_after=runner.ENDPOINT,
        parent_diagnostic=str(diagnostic),
        parent_prepared=str(parent),
        input_capture=required[0],
        owned_trial=required[-1],
        saved_captures=capture_pins,
        configuration=saved["configuration"],
        snapshot_sha256="a" * 64,
        git_revision="b" * 40,
        external_inputs=required,
        native_source_root=str(runner.shared.NATIVE),
        original_source_sites=sites,
        runtime_paths=[],
        runtime_inventory={"files": []},
        interpreter=str(Path(sys.executable).absolute()),
        cpu=3,
        limits=runner.shared.LIMITS,
        comparison="exact_final_three_caches_two_MT_streams_five_alias_observations",
        native_executions=1,
        cells_replays=0,
        automatic_retry=False,
        native_package_imports=[],
        normalized_parameters_phase_callbacks_only=True,
        capture_transport=runner.payload.KIND,
        capture_read_policy=runner.inputs.CAPTURE_READ_POLICY,
        **runner.NO_CREDIT,
    )
    monkeypatch.setattr(runner.source_snapshot, "verify", lambda *a, **k: {})
    monkeypatch.setattr(runner.runtime, "verify_inventory", lambda value: None)
    monkeypatch.setattr(runner.inputs, "saved_caller", lambda *a: copy.deepcopy(saved))
    monkeypatch.setattr(runner, "_saved_bindings", lambda *a: copy.deepcopy(required))
    monkeypatch.setattr(runner.original, "source_nodes", lambda *a: ([], copy.deepcopy(sites)))
    return dict(
        prepared=prepared,
        diagnostic=diagnostic,
        parent=parent,
        plan=plan,
        saved=saved,
        required=required,
        sites=sites,
        base=tmp_path,
    )


def save_plan(context):
    path = context["prepared"] / "plan.json"
    path.write_text(json.dumps(context["plan"]) + "\n")
    return runner.shared.pin(path)["sha256"]


def save_release(context, digest):
    review = context["base"] / "source-review.json"
    review.write_text('{"synthetic_review": true}\n')
    grant = dict(
        kind=runner.KINDS[1],
        plan_sha256=digest,
        snapshot_sha256=context["plan"]["snapshot_sha256"],
        case=context["plan"]["case"],
        stop_after=runner.ENDPOINT,
        allow_one_native_reference=True,
        source_review=runner.shared.pin(review),
        **runner.NO_CREDIT,
    )
    path = context["base"] / "release.json"
    path.write_text(json.dumps(grant) + "\n")
    return path


def test_metadata_plan_verifies_without_scientific_import(context):
    digest = save_plan(context)
    assert runner.verify_plan(context["prepared"], digest) == context["plan"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("native_executions", True),
        ("native_executions", 2),
        ("cells_replays", False),
        ("cells_replays", 1),
        ("automatic_retry", True),
        ("native_package_imports", ["betse"]),
        ("scientific_qualification", True),
        ("physical_geometry_admitted", 0),
        ("ordinary_checkpoint_admitted", True),
        ("case", "unknown"),
        ("cpu", True),
        ("stop_after", "make_world"),
        ("native_source_root", "/unknown"),
        ("normalized_parameters_phase_callbacks_only", False),
    ],
)
def test_widened_plan_refuses_before_any_execution(context, field, value):
    context["plan"][field] = value
    digest = save_plan(context)
    with pytest.raises(ValueError, match="plan"):
        runner.verify_plan(context["prepared"], digest)


@pytest.mark.parametrize(
    "target",
    [
        "configuration",
        "capture_order",
        "input_capture",
        "owned_trial",
        "runtime_paths",
        "required_pin",
        "source_site",
    ],
)
def test_changed_saved_binding_refuses(context, target):
    plan = context["plan"]
    if target == "configuration":
        plan["configuration"] = {}
    elif target == "capture_order":
        plan["saved_captures"] = list(reversed(plan["saved_captures"]))
    elif target == "input_capture":
        plan["input_capture"] = plan["owned_trial"]
    elif target == "owned_trial":
        plan["owned_trial"] = plan["input_capture"]
    elif target == "runtime_paths":
        plan["runtime_paths"] = ["/new-overlay"]
    elif target == "required_pin":
        plan["external_inputs"] = plan["external_inputs"][:-1]
    else:
        plan["original_source_sites"] = {}
    digest = save_plan(context)
    with pytest.raises(ValueError):
        runner.verify_plan(context["prepared"], digest)


def test_changed_large_legacy_capture_policy_refuses(context):
    policy = dict(context["plan"]["capture_read_policy"])
    policy["legacy_multi_cell_request_bytes"] += 1
    context["plan"]["capture_read_policy"] = policy
    digest = save_plan(context)
    with pytest.raises(ValueError, match="plan"):
        runner.verify_plan(context["prepared"], digest)


def test_hash_or_preparation_failure_refuses(context):
    digest = save_plan(context)
    with pytest.raises(ValueError, match="Changed"):
        runner.verify_plan(context["prepared"], "f" * 64)
    (context["prepared"] / "preparation-failure.json").write_text("{}")
    with pytest.raises(ValueError, match="plan"):
        runner.verify_plan(context["prepared"], digest)


@pytest.mark.parametrize(
    "field,value",
    [
        ("allow_one_native_reference", 1),
        ("allow_one_native_reference", False),
        ("case", "caller-hex-core"),
        ("plan_sha256", "d" * 64),
        ("snapshot_sha256", "e" * 64),
        ("stop_after", "near_neigh"),
        ("scientific_qualification", True),
        ("source_review", None),
    ],
)
def test_exact_release_required(context, field, value):
    digest = save_plan(context)
    release = save_release(context, digest)
    grant = json.loads(release.read_text())
    grant[field] = value
    release.write_text(json.dumps(grant))
    with pytest.raises(ValueError, match="release"):
        runner.verify(context["prepared"], digest, release)


def test_release_source_pin_and_cpu_must_match(context, monkeypatch):
    digest = save_plan(context)
    release = save_release(context, digest)
    assert runner.verify(context["prepared"], digest, release) == context["plan"]
    monkeypatch.setattr(runner.os, "sched_getaffinity", lambda pid: {4})
    with pytest.raises(ValueError, match="CPU"):
        runner.verify(context["prepared"], digest, release)
    monkeypatch.setattr(runner.os, "sched_getaffinity", lambda pid: {3})
    (context["base"] / "source-review.json").write_text("{}")
    with pytest.raises(ValueError, match="Changed external"):
        runner.verify(context["prepared"], digest, release)


def test_one_shot_claim_binds_release_output_and_survives_failed_start(context):
    digest = save_plan(context)
    release = save_release(context, digest)
    output = context["base"] / "output"
    receipt = runner.claim(context["prepared"], digest, release, output)
    assert runner.verify_claim(context["prepared"], digest, release, output) == receipt
    with pytest.raises(FileExistsError):
        runner.claim(context["prepared"], digest, release, context["base"] / "another")
    with pytest.raises(ValueError, match="claim"):
        runner.verify_claim(context["prepared"], digest, release, context["base"] / "another")
    release.write_text(release.read_text() + " ")
    with pytest.raises(ValueError, match="claim"):
        runner.verify_claim(context["prepared"], digest, release, output)


@pytest.mark.parametrize(
    "name", ["cells", "cells.processes.a", "betse", "betse.util.type.types", "jax", "jaxlib.x"]
)
def test_no_model_or_native_package_import_exception(name):
    attempted = []
    with pytest.raises(ImportError):
        runner.import_guard(attempted)("import", (name,))
    assert attempted == [name]
    with pytest.raises(ValueError, match="prohibited"):
        runner.verify_imports({name: object()})


def test_numerical_and_normalized_private_names_are_not_model_imports():
    attempted = []
    for name in (
        "numpy",
        "scipy.spatial",
        "PIL.Image",
        "validation.betse.native_multi_cell_caller_native",
    ):
        runner.import_guard(attempted)("import", (name,))
    runner.verify_imports(
        {"numpy": object(), "validation.betse.native_multi_cell_caller_native": object()}
    )
    assert attempted == []


def test_output_cannot_overlap_saved_inputs_or_runtime(context):
    plan = context["plan"]
    library = context["base"] / "runtime" / "library.so"
    plan["runtime_inventory"]["files"] = [dict(path=str(library), sha256="1" * 64, size_bytes=1)]
    for output in (
        context["diagnostic"],
        context["parent"],
        context["base"] / "runtime",
        library,
        context["prepared"],
        context["base"],
    ):
        with pytest.raises(ValueError):
            runner.protected_output(output, context["prepared"], plan)
    assert (
        runner.protected_output(context["base"] / "out", context["prepared"], plan)
        == context["base"] / "out"
    )


def test_external_pin_conflict_refuses():
    first = dict(path="/data/a", sha256="a" * 64)
    assert runner.unique_pins([first, first]) == [first]
    with pytest.raises(ValueError, match="Conflicting"):
        runner.unique_pins([first, dict(path="/data/a", sha256="b" * 64)])
    with pytest.raises(ValueError, match="exact"):
        runner.unique_pins([dict(first, extra=True)])


@pytest.mark.parametrize("failure", [None, "freeze", "input_drift", "runtime"])
def test_preparation_is_metadata_only_and_preserves_incomplete_failure(
    context, monkeypatch, failure
):
    repository = context["base"] / "checkout"
    for relative in (runner.OWN, runner.shared.CLOSURE):
        path = repository / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Synthetic snapshot input; no execution\n")
    monkeypatch.setattr(runner, "ROOT", repository)
    monkeypatch.setattr(runner.runtime, "prepare_inventory", lambda paths: {"files": []})
    monkeypatch.setattr(
        runner.runpy,
        "run_path",
        lambda path: {"closure": lambda root, starts: {runner.OWN: "metadata"}},
    )
    touched = []

    def freeze(root, destination, files):
        touched.append("freeze")
        if failure == "freeze":
            raise ValueError("synthetic incomplete snapshot")
        destination.mkdir()
        (destination / "SNAPSHOT.json").write_text('{"synthetic_snapshot": true}\n')
        if failure == "input_drift":
            Path(context["required"][0]["path"]).write_text("{}")
        return {"git_revision": "c" * 40}

    monkeypatch.setattr(runner.source_snapshot, "freeze", freeze)
    monkeypatch.setattr(
        runner.source_snapshot,
        "assert_checkout_unchanged",
        lambda path: touched.append("postcheck"),
    )
    if failure == "runtime":

        def changed(value):
            raise ValueError("synthetic runtime file changed")

        monkeypatch.setattr(runner.runtime, "verify_inventory", changed)
    destination = context["base"] / "new-preparation"
    if failure:
        with pytest.raises(ValueError):
            runner.prepare(destination, context["diagnostic"], context["parent"])
        assert (destination / "preparation-failure.json").is_file()
        assert not (destination / "plan.json").exists()
    else:
        plan = runner.prepare(destination, context["diagnostic"], context["parent"])
        assert touched == ["freeze", "postcheck"]
        assert plan["native_executions"] == 1 and plan["cells_replays"] == 0
        assert plan["saved_captures"][0]["label"] == runner.parent_runner.STAGES[0]
        assert plan["owned_trial"] == context["required"][-1]
        assert plan["runtime_inventory"] == {"files": []}
        assert (destination / "plan.json").stat().st_mode & 0o222 == 0


def synthetic_worker(context, monkeypatch):
    digest = save_plan(context)
    release = save_release(context, digest)
    output = context["base"] / "worker-output"
    output.mkdir()
    runner.claim(context["prepared"], digest, release, output)
    monkeypatch.setattr(runner, "ROOT", context["prepared"] / "source")
    monkeypatch.setattr(runner, "verify", lambda *a: context["plan"])
    monkeypatch.setattr(runner.resource, "setrlimit", lambda *a: None)
    hooks, calls = [], []
    monkeypatch.setattr(runner.sys, "addaudithook", hooks.append)
    owned, reference = examples.inputs()
    reference.update(
        source_body_completed=True,
        original_source_unchanged=True,
        capture_errors=[],
        actual_source_executions=1,
        failed_stage=None,
        forensic_marker={"not_in_comparison_view": True},
    )
    Path(context["plan"]["owned_trial"]["path"]).write_text(json.dumps(owned))
    monkeypatch.setattr(runner.runtime, "preflight", lambda *a: {"synthetic_import_only": True})
    monkeypatch.setattr(runner.runtime, "finish", lambda *a: {"synthetic_runtime_complete": True})
    monkeypatch.setattr(
        runner.shared,
        "runtime_inventory",
        lambda *a: {"synthetic_producer": {"path": "/synthetic", "sha256": "a" * 64}},
    )

    def evaluate(*args, **kwargs):
        calls.append("reference")
        return copy.deepcopy(reference)

    monkeypatch.setattr(runner.native, "evaluate", evaluate)
    return digest, release, output, reference, calls, hooks


def test_synthetic_worker_saves_full_before_exact_comparison_and_is_one_shot(context, monkeypatch):
    digest, release, output, _, calls, _ = synthetic_worker(context, monkeypatch)
    assert runner.worker(context["prepared"], digest, release, output) == 0
    full = runner.payload.read(output / "native-full.json")
    selected = runner.payload.read(output / "native-comparison.json")
    assert "forensic_marker" in full and "forensic_marker" not in selected
    assert tuple(selected) == tuple(sorted(runner.native.NATIVE_FIELDS))
    result = runner.shared.read(output / "worker-result.json")
    assert result["status"] == "exact_source_match" and result["accepted_source_comparisons"] == 1
    assert result["scientific_qualification"] is False and calls == ["reference"]
    assert runner.shared.read(output / "comparison.json")["exact_match"] is True
    with pytest.raises(FileExistsError):
        runner.worker(context["prepared"], digest, release, output)
    assert calls == ["reference"]


@pytest.mark.parametrize(
    "where",
    [
        "preflight",
        "source",
        "capture",
        "comparison_projection",
        "runtime_finish",
        "runtime_inventory",
    ],
)
def test_worker_failures_keep_zero_credit_and_prior_evidence(context, monkeypatch, where):
    digest, release, output, reference, calls, _ = synthetic_worker(context, monkeypatch)

    def failure(*args, **kwargs):
        raise ValueError("original " + where) from RuntimeError("original cause")

    if where == "preflight":
        monkeypatch.setattr(runner.runtime, "preflight", failure)
    elif where == "source":
        monkeypatch.setattr(runner.native, "evaluate", failure)
    elif where == "capture":
        monkeypatch.setattr(runner.shared.archive, "snapshot", failure)
    elif where == "comparison_projection":
        reference["original_source_unchanged"] = False
    elif where == "runtime_finish":
        monkeypatch.setattr(runner.runtime, "finish", failure)
    else:
        monkeypatch.setattr(runner.shared, "runtime_inventory", failure)
    assert runner.worker(context["prepared"], digest, release, output) == 1
    result = runner.shared.read(output / "worker-result.json")
    assert result["status"] == "failed" and result["accepted_source_comparisons"] == 0
    assert result["reference_calls_attempted"] == (0 if where == "preflight" else 1)
    if where == "capture":
        assert (output / "source-summary.json").is_file() and not (
            output / "native-full.json"
        ).exists()
    if where in ("runtime_finish", "runtime_inventory"):
        assert (output / "native-full.json").is_file() and (output / "comparison.json").is_file()
        assert "runtime_capture_error" in result
    if where == "source":
        graph = result["error"]
        first = graph["nodes"][graph["root"]]
        assert graph["nodes"][first["cause"]]["message"] == "original cause"


def test_failed_native_source_keeps_complete_record_without_match(context, monkeypatch):
    digest, release, output, reference, _, _ = synthetic_worker(context, monkeypatch)
    reference.update(
        status="source_failed",
        source_body_completed=False,
        source_error={"original_source_failure": "preserved"},
        failed_stage="clip_and_refine",
    )
    assert runner.worker(context["prepared"], digest, release, output) == 1
    assert (
        runner.payload.read(output / "native-full.json")["source_error"]
        == reference["source_error"]
    )
    assert not (output / "comparison.json").exists()
    assert runner.shared.read(output / "worker-result.json")["accepted_source_comparisons"] == 0


@pytest.mark.parametrize("failure", ["source", "capture"])
def test_incomplete_native_capture_keeps_primary_before_strict_comparator(
    context, monkeypatch, failure
):
    digest, release, output, reference, _, _ = synthetic_worker(context, monkeypatch)
    reference.update(status="source_failed", aliases=None, failed_stage="Cells_lattice")
    if failure == "source":
        reference.update(source_body_completed=False, source_error={"primary": "original cause"})
    else:
        reference.update(
            capture_error={"secondary": "capture cause"}, capture_errors=[{"retained": True}]
        )

    def forbidden(*args, **kwargs):
        raise AssertionError("Incomplete capture must not enter comparison projection")

    monkeypatch.setattr(runner.native, "comparison_record", forbidden)
    assert runner.worker(context["prepared"], digest, release, output) == 1
    result = runner.shared.read(output / "worker-result.json")
    full = runner.payload.read(output / "native-full.json")
    assert full["aliases"] is None and full["failed_stage"] == "Cells_lattice"
    assert result["source_summary"][failure + "_error"] == reference[failure + "_error"]
    assert "Original source or capture failed" in result["error"]["nodes"][0]["message"]
    assert result["accepted_source_comparisons"] == 0
    assert not (output / "native-comparison.json").exists()
    assert not (output / "comparison.json").exists()


def test_first_evidence_write_failure_preserves_returned_source_error(context, monkeypatch):
    digest, release, output, reference, _, _ = synthetic_worker(context, monkeypatch)
    reference.update(
        status="source_failed",
        source_body_completed=False,
        source_error={"original_source_failure": "keep this primary"},
        capture_error={"original_capture_failure": "keep this too"},
        failed_stage="clip_and_refine",
    )
    write = runner.shared.write

    def reject_summary(path, value):
        if Path(path).name == "source-summary.json":
            raise OSError("first evidence write failed")
        return write(path, value)

    monkeypatch.setattr(runner.shared, "write", reject_summary)
    assert runner.worker(context["prepared"], digest, release, output) == 1
    result = runner.shared.read(output / "worker-result.json")
    assert result["source_summary"]["source_error"] == reference["source_error"]
    assert result["source_summary"]["capture_error"] == reference["capture_error"]
    assert (
        result["source_summary_capture_error"]["nodes"][0]["message"]
        == "first evidence write failed"
    )
    assert (
        runner.payload.read(output / "native-full.json")["source_error"]
        == reference["source_error"]
    )
    assert not (output / "comparison.json").exists() and result["accepted_source_comparisons"] == 0


@pytest.mark.parametrize("phase", ["preflight", "finish"])
def test_runtime_refusal_keeps_original_partial_observation(context, monkeypatch, phase):
    digest, release, output, _, _, _ = synthetic_worker(context, monkeypatch)
    partial = dict(status="refused", phase=phase, successfully_pinned=[{"path": "/synthetic"}])

    def refused(*args, **kwargs):
        raise runner.runtime.RuntimeInventoryError("original runtime refusal", partial)

    monkeypatch.setattr(runner.runtime, phase, refused)
    assert runner.worker(context["prepared"], digest, release, output) == 1
    assert runner.shared.read(output / "runtime-refusal.json") == partial
    result = runner.shared.read(output / "worker-result.json")
    assert result["accepted_source_comparisons"] == 0
    assert result["reference_calls_attempted"] == (0 if phase == "preflight" else 1)


def test_caught_prohibited_import_attempt_still_prevents_match(context, monkeypatch):
    digest, release, output, reference, _, hooks = synthetic_worker(context, monkeypatch)

    def forbidden_then_return(*args, **kwargs):
        with pytest.raises(ImportError):
            hooks[0]("import", ("betse.science.cells",))
        return copy.deepcopy(reference)

    monkeypatch.setattr(runner.native, "evaluate", forbidden_then_return)
    assert runner.worker(context["prepared"], digest, release, output) == 1
    result = runner.shared.read(output / "worker-result.json")
    assert result["attempted_prohibited_imports"] == ["betse.science.cells"]
    assert result["accepted_source_comparisons"] == 0


def test_partial_transport_failure_preserves_primary_and_raw_file_pin(context, monkeypatch):
    digest, release, output, _, _, _ = synthetic_worker(context, monkeypatch)
    original = runner.payload.write

    def partial(path, value):
        if Path(path).name == "native-comparison.json":
            Path(path).write_text('{"unfinished":')
            raise OSError("original transport write")
        return original(path, value)

    monkeypatch.setattr(runner.payload, "write", partial)
    assert runner.worker(context["prepared"], digest, release, output) == 1
    result = runner.shared.read(output / "worker-result.json")
    assert result["error"]["nodes"][0]["message"] == "original transport write"
    assert result["artifact_capture_errors"][0]["raw_unvalidated_file"] == runner.shared.pin(
        output / "native-comparison.json"
    )
    assert (output / "native-full.json").is_file() and result["accepted_source_comparisons"] == 0


def test_worker_terminal_write_failure_retains_primary_in_guard_stderr(
    context, monkeypatch, capsys
):
    digest, release, output, _, _, _ = synthetic_worker(context, monkeypatch)
    write = runner.shared.write

    def failed_source(*args, **kwargs):
        raise ValueError("original source error") from RuntimeError("original source cause")

    def failed_terminal(path, value):
        if Path(path).name == "worker-result.json":
            raise OSError("terminal persistence error")
        return write(path, value)

    monkeypatch.setattr(runner.native, "evaluate", failed_source)
    monkeypatch.setattr(runner.shared, "write", failed_terminal)
    assert runner.worker(context["prepared"], digest, release, output) == 1
    fallback = json.loads(capsys.readouterr().err.split("CELLS_TERMINAL_CAPTURE_FAILURE ")[-1])
    outcome = fallback["outcome"]
    assert outcome["error"]["nodes"][0]["message"] == "original source error"
    assert outcome["error"]["nodes"][1]["message"] == "original source cause"
    assert outcome["terminal_capture_error"]["nodes"][0]["message"] == "terminal persistence error"
    assert outcome["status"] == "failed" and outcome["accepted_source_comparisons"] == 0
    assert not (output / "worker-result.json").exists()


def test_launcher_pin_and_terminal_failure_retains_guard_error(context, monkeypatch, capsys):
    digest = save_plan(context)
    release = save_release(context, digest)
    output = context["base"] / "late-failure"
    write, pin = runner.shared.write, runner.shared.pin
    monkeypatch.setattr(runner.shared.guard, "memory_available", lambda: 20 * 2**30)

    def failed_guard(*args, **kwargs):
        write(output / "worker-result.json", {"status": "failed"})
        raise RuntimeError("original guard error") from ValueError("guard cause")

    def failed_pin(path):
        if Path(path) == output / "worker-result.json":
            raise OSError("late worker pin error")
        return pin(path)

    def failed_terminal(path, value):
        if Path(path) == output / "failure.json":
            raise OSError("outer terminal persistence error")
        return write(path, value)

    monkeypatch.setattr(runner.shared.guard, "run_bounded", failed_guard)
    monkeypatch.setattr(runner.shared, "pin", failed_pin)
    monkeypatch.setattr(runner.shared, "write", failed_terminal)
    assert runner.launch(context["prepared"], digest, release, output) == 1
    fallback = json.loads(capsys.readouterr().err.split("CELLS_TERMINAL_CAPTURE_FAILURE ")[-1])
    outcome = fallback["outcome"]
    assert outcome["error"]["nodes"][0]["message"] == "original guard error"
    assert (
        outcome["terminal_input_capture_errors"][0]["error"]["nodes"][0]["message"]
        == "late worker pin error"
    )
    assert (
        outcome["terminal_capture_error"]["nodes"][0]["message"]
        == "outer terminal persistence error"
    )
    assert outcome["accepted_scientific_cases"] == 0 and outcome["status"] == "failed"


@pytest.mark.parametrize(
    "failure", [None, "low_memory", "guard_failure", "mismatch", "false_credit", "false_attempt"]
)
def test_launch_is_bounded_one_attempt_and_retains_terminal(context, monkeypatch, failure):
    digest = save_plan(context)
    release = save_release(context, digest)
    output = context["base"] / "launch-output"
    calls = []
    monkeypatch.setattr(
        runner.shared.guard,
        "memory_available",
        lambda: (1 if failure == "low_memory" else 20) * 2**30,
    )

    def bounded(command, **kwargs):
        calls.append((command, kwargs))
        assert kwargs["cwd"] == context["prepared"] / "source"
        assert {k: kwargs[k] for k in runner.shared.LIMITS} == runner.shared.LIMITS
        for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
            assert kwargs["env"][name] == "1"
        if failure == "guard_failure":
            raise RuntimeError("synthetic resource refusal")
        child = dict(
            status="source_mismatch" if failure == "mismatch" else "exact_source_match",
            accepted_source_comparisons=True if failure == "false_credit" else 1,
            reference_calls_attempted=True if failure == "false_attempt" else 1,
            attempted_prohibited_imports=[],
            **runner.NO_CREDIT,
        )
        runner.shared.write(output / "worker-result.json", child)
        return {"returncode": 0}

    monkeypatch.setattr(runner.shared.guard, "run_bounded", bounded)
    assert runner.launch(context["prepared"], digest, release, output) == int(failure is not None)
    terminal = runner.shared.read(output / ("result.json" if failure is None else "failure.json"))
    assert terminal["automatic_retry"] is False and terminal["accepted_scientific_cases"] == 0
    assert len(calls) == (0 if failure == "low_memory" else 1)
    assert (context["prepared"] / "reference-claim.json").is_file()
    assert (
        runner.launch(context["prepared"], digest, release, context["base"] / "retry-output") == 1
    )
    assert len(calls) == (0 if failure == "low_memory" else 1)
