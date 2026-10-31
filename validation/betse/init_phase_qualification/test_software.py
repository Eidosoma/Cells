"""Synthetic runner/release controls; no INIT, native or reference evaluation."""

import ast
import hashlib
import json
import stat
import subprocess
import sys
from types import SimpleNamespace

import pytest

from validation import source_snapshot
from validation.betse.init_phase_qualification import prepare


def store(path, value):
    path.write_text(json.dumps(value, sort_keys=True))


@pytest.fixture
def modules(monkeypatch):
    common = prepare.load("_test_init_common", prepare.ROOT / prepare.OWNED / "common.py")
    contracts = prepare.contracts(prepare.ROOT)
    monkeypatch.setitem(sys.modules, "common", common)
    monkeypatch.setitem(sys.modules, "contracts", contracts)
    monkeypatch.setitem(sys.modules, "source_snapshot", source_snapshot)
    controller = prepare.load(
        "_test_init_controller", prepare.ROOT / prepare.OWNED / "controller.py"
    )
    supervisor = prepare.load(
        "_test_init_supervisor", prepare.ROOT / prepare.OWNED / "supervise.py"
    )
    return SimpleNamespace(
        common=common, contracts=contracts, controller=controller, supervisor=supervisor
    )


@pytest.fixture
def synthetic_runner(tmp_path, monkeypatch, modules):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "common.py").write_text("synthetic_inert_producer = True\n")
    source_snapshot.git(repo, "add", "common.py")
    source_snapshot.git(
        repo, "-c", "user.name=Test", "-c", "user.email=test@invalid", "commit", "-qm", "synthetic"
    )
    snapshot = tmp_path / "checkout"
    source_snapshot.freeze(repo, snapshot, {"common.py": "common.py"})
    root = tmp_path / "runner"
    root.mkdir()
    (root / "common.py").write_bytes((snapshot / "common.py").read_bytes())
    store(root / "source-resource-contract.json", {"synthetic": True})
    store(root / "expected-evidence.json", {"synthetic": True})
    plan = dict(
        status="sealed_held",
        reference_successor_reviewed=True,
        checkout_snapshot=str(snapshot),
        checkout_snapshot_sha256=prepare.sha(snapshot / "SNAPSHOT.json"),
        runner_checkout_bindings={"common.py": "common.py"},
        runner_sha256={"common.py": prepare.sha(root / "common.py")},
        pins={},
        cpu=4,
        source_resource_contract_sha256=prepare.sha(root / "source-resource-contract.json"),
        evidence_contract_sha256=prepare.sha(root / "expected-evidence.json"),
    )
    store(root / "plan.json", plan)
    seal = {p.name: prepare.sha(p) for p in root.iterdir() if p.is_file()}
    store(root / "seal.json", dict(files=seal))
    store(
        tmp_path / "preparation.json",
        dict(
            status="held_prepared_from_checkout_no_scientific_execution",
            runner_plan_sha256=prepare.sha(root / "plan.json"),
            runner_seal_sha256=prepare.sha(root / "seal.json"),
        ),
    )
    release = dict(
        authorized=True,
        requested_round=True,
        cpu_coordinated=True,
        source_and_runner_accepted_by_root=True,
        cpu=4,
        plan_sha256=prepare.sha(root / "plan.json"),
        seal_sha256=prepare.sha(root / "seal.json"),
        authorization_note="Synthetic metadata control only; never execute a worker",
    )
    monkeypatch.delenv("CELLS_INIT_RELEASE_FILE", raising=False)
    return SimpleNamespace(root=root, release=release, path=tmp_path / "release.json", plan=plan)


def test_synthetic_complete_release_binds_snapshot_without_worker(modules, synthetic_runner):
    case = synthetic_runner
    store(case.path, case.release)
    assert modules.common.verify_release(case.root) == case.plan


@pytest.mark.parametrize(
    "key",
    ["authorized", "requested_round", "cpu_coordinated", "source_and_runner_accepted_by_root"],
)
def test_each_release_authority_is_required(key, modules, synthetic_runner):
    case = synthetic_runner
    case.release[key] = False
    store(case.path, case.release)
    with pytest.raises(ValueError, match="Explicit matching Root release"):
        modules.common.verify_release(case.root)


def test_release_cannot_be_written_into_immutable_runner(monkeypatch, modules, synthetic_runner):
    case = synthetic_runner
    monkeypatch.setenv("CELLS_INIT_RELEASE_FILE", str(case.root / "release.json"))
    with pytest.raises(ValueError, match="outside immutable"):
        modules.common.verify_release(case.root)


def test_wrong_plan_or_seal_release_refuses(modules, synthetic_runner):
    case = synthetic_runner
    case.release["plan_sha256"] = "0" * 64
    store(case.path, case.release)
    with pytest.raises(ValueError, match="Explicit matching Root release"):
        modules.common.verify_release(case.root)


def test_missing_release_refuses(modules, synthetic_runner):
    with pytest.raises(ValueError, match="Regular metadata"):
        modules.common.verify_release(synthetic_runner.root)


def test_checkout_alias_is_not_a_source_authority(modules):
    proof = {"files": {"canonical.py": dict(checkout_path="canonical.py", sha256="a" * 64)}}
    with pytest.raises(ValueError, match="differs from checkout snapshot"):
        modules.common.checkout_binding(proof, {"common.py": "other.py"}, {"common.py": "a" * 64})


def test_incomplete_preparation_is_not_releaseable(modules, synthetic_runner):
    case = synthetic_runner
    store(case.path, case.release)
    store(case.root.parent / "FAILURE.json", dict(status="incomplete_preparation"))
    with pytest.raises(ValueError, match="Complete matching checkout preparation"):
        modules.common.verify_release(case.root)


def test_exact_62_declarations_preserve_1298_archive_paths(modules):
    inputs = prepare.read(prepare.PRIOR_PACKET / "inputs.json")
    evidence = prepare.read(prepare.PRIOR_RUNNER / "expected-evidence.json")
    groups = inputs["groups"]
    declared = {name: modules.contracts.declaration(spec) for name, spec in groups.items()}
    assert declared == evidence["groups"]
    assert len(groups) == len({n for g in groups.values() for n in g["node_ids"]}) == 62
    assert sum(g["accepted_calls"] for g in groups.values()) == 61
    assert sum(g["independent_forms"] for g in groups.values()) == 986
    assert sum(len(g["typed_archives"]) for g in declared.values()) == 1298
    assert sum(g["native_case"] is not None for g in declared.values()) == 29


def test_missing_release_stops_launcher_before_any_process(monkeypatch, tmp_path, modules):
    attempted = []

    def forbidden(*args, **kwargs):
        attempted.append(True)
        raise AssertionError("Synthetic launch refusal must not start a process")

    def no_release():
        raise ValueError("synthetic missing Root release")

    monkeypatch.setattr(modules.supervisor, "LAUNCH", tmp_path / "launch")
    monkeypatch.setattr(modules.supervisor, "verify_plan", no_release)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    with pytest.raises(ValueError, match="missing Root release"):
        modules.supervisor.launch()
    assert attempted == []
    assert json.loads((tmp_path / "launch/launch-failure.json").read_text())["child_pid"] is None


def test_original_reader_and_contract_predicates_preserved():
    for name in ("read_evidence.py", "contracts.py", "archive_binding.py", "capture_binding.py"):
        old = prepare.PRIOR_RUNNER / name
        if not old.exists():
            old = prepare.PRIOR_PACKET / "tools" / name
        new = prepare.ROOT / prepare.OWNED / name
        assert ast.dump(ast.parse(old.read_bytes()), include_attributes=False) == ast.dump(
            ast.parse(new.read_bytes()), include_attributes=False
        )


def test_shared_helpers_use_exact_canonical_producers():
    for target in ("resource_guard.py", "runtime_inventory.py", "qualification_inventory.py"):
        canonical = prepare.ROOT / prepare.RUNNER_FILES[target]
        assert prepare.sha(canonical) == prepare.sha(prepare.PRIOR_RUNNER / target)
    canonical = prepare.ROOT / prepare.TOOL_FILES["tools/qualification_typed_evidence.py"]
    assert prepare.sha(canonical) == prepare.sha(prepare.PRIOR_PACKET / "tools" / canonical.name)


def test_archive_site_rebinding_requires_same_ast(tmp_path):
    source = tmp_path / "writer.py"
    source.write_text("\n\ndef writer():\n    archive(value)\n")
    call = next(n for n in ast.walk(ast.parse(source.read_text())) if isinstance(n, ast.Call))
    row = dict(
        module="writer.py",
        callee="archive",
        line=1,
        AST_sha256=hashlib.sha256(ast.dump(call, include_attributes=False).encode()).hexdigest(),
    )
    assert prepare.call_sites([row], tmp_path) == [dict(row, line=4)]
    source.write_text("def writer():\n    archive(other)\n")
    with pytest.raises(ValueError, match="Missing/ambiguous original archive call"):
        prepare.call_sites([row], tmp_path)


def test_historical_producer_paths_rebind_only_to_current_source(tmp_path):
    (tmp_path / "tests").mkdir()
    current = tmp_path / "tests/writer.py"
    current.write_text("current_checkout_writer = True\n")
    table = {"/mnt/workspaces/Cells/old/source/tests/writer.py": "old_source_digest"}
    assert prepare.refresh_pins(table, tmp_path) == {"source/tests/writer.py": prepare.sha(current)}
    assert prepare.canonical_producer("/usr/lib/python3.13/zipfile/__init__.py") is None


def test_controller_copies_readonly_code_without_overwrite(tmp_path, modules):
    packet, output = tmp_path / "packet", tmp_path / "output"
    (packet / "source").mkdir(parents=True)
    output.mkdir()
    code = packet / "source/inert.py"
    code.write_text("synthetic_source = True\n")
    code.chmod(0o444)
    manifest = dict(files={"source/inert.py": prepare.sha(code)})
    store(packet / "MANIFEST.json", manifest)
    modules.controller.copy_packet(packet, output, manifest)
    assert (output / "source/inert.py").read_bytes() == code.read_bytes()
    assert stat.S_IMODE((output / "source/inert.py").stat().st_mode) & 0o222 == 0
    assert stat.S_IMODE((output / "source").stat().st_mode) & 0o222 == 0
    with pytest.raises(FileExistsError):
        modules.controller.copy_packet(packet, output, manifest)


def test_reviewed_baseline_or_successor_only():
    old = {"producer.py": "baseline"}
    review = {"producer.py": dict(old_sha256="baseline", checkout_sha256="reviewed")}
    assert prepare.reviewed_versions(old, {"producer.py": "baseline"}, review) == (
        [],
        ["producer.py"],
    )
    assert prepare.reviewed_versions(old, {"producer.py": "reviewed"}, review) == (
        ["producer.py"],
        [],
    )
    with pytest.raises(ValueError, match="Reviewed source delta changed"):
        prepare.reviewed_versions(old, {"producer.py": "unknown"}, review)


def test_repeated_archive_ast_keeps_function_occurrence(tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    before.mkdir()
    after.mkdir()
    code = "def writer():\n    archive(value)\n    archive(value)\n"
    (before / "writer.py").write_text(code)
    (after / "writer.py").write_text("\n\n" + code)
    calls = sorted(
        (n for n in ast.walk(ast.parse(code)) if isinstance(n, ast.Call)), key=lambda n: n.lineno
    )
    rows = [
        dict(
            module="writer.py",
            callee="archive",
            line=n.lineno,
            AST_sha256=hashlib.sha256(ast.dump(n, include_attributes=False).encode()).hexdigest(),
        )
        for n in calls
    ]
    updated = prepare.call_sites(rows, after, baseline=before)
    assert [n["line"] for n in updated] == [4, 5]
    assert [n["AST_sha256"] for n in updated] == [n["AST_sha256"] for n in rows]


@pytest.fixture
def failure_writer(tmp_path, monkeypatch):
    path = tmp_path / prepare.TEST
    path.parent.mkdir(parents=True)
    baseline = "def test_init_raw_refusal():\n    archive(parent)\n"
    path.write_text(baseline)
    parent_sha = prepare.sha(path)
    monkeypatch.setattr(prepare, "NORMALIZED_TEST_SHA256", parent_sha)
    node = next(n for n in ast.walk(ast.parse(baseline)) if isinstance(n, ast.Call))
    original = dict(
        module=prepare.TEST,
        callee="archive",
        line=node.lineno,
        AST_sha256=hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
    )
    path.write_text(baseline + "    archive(returned)\n")
    calls = [n for n in ast.walk(ast.parse(path.read_text())) if isinstance(n, ast.Call)]
    added = dict(
        module=prepare.TEST,
        callee="archive",
        line=calls[-1].lineno,
        AST_sha256=hashlib.sha256(
            ast.dump(calls[-1], include_attributes=False).encode()
        ).hexdigest(),
        containing_function="test_init_raw_refusal",
        source_sha256=prepare.sha(path),
        role="unexpected_success_failure_only",
    )
    review = dict(
        normalized_test_parent_sha256=parent_sha,
        changed_files={prepare.TEST: dict(checkout_sha256=prepare.sha(path))},
        additional_failure_archive_sites=[added],
    )
    return SimpleNamespace(
        root=tmp_path, path=path, original=original, added=added, review=review, baseline=baseline
    )


def test_reviewed_failure_capture_preserves_original_writer(failure_writer):
    case = failure_writer
    additions = prepare.reviewed_writer_additions(case.review, case.root)
    originals = prepare.call_sites([case.original], case.root)
    assert originals == [case.original] and additions == [case.added]
    prepare.verify_test_writer_roster(originals + additions, case.root)


def test_legacy_comparator_source_needs_no_added_writer(failure_writer):
    case = failure_writer
    case.path.write_text(case.baseline)
    assert prepare.reviewed_writer_additions({}, case.root) == []
    prepare.verify_test_writer_roster([case.original], case.root)


@pytest.mark.parametrize(
    "key,value",
    [
        ("module", "other.py"),
        ("callee", "other_archive"),
        ("containing_function", "test_positive"),
        ("source_sha256", "unreviewed"),
        ("role", "accepted_positive_evidence"),
        ("AST_sha256", "unreviewed"),
        ("line", 99),
    ],
)
def test_failure_capture_rejects_changed_authority(key, value, failure_writer):
    case = failure_writer
    case.added[key] = value
    with pytest.raises(ValueError):
        prepare.reviewed_writer_additions(case.review, case.root)


def test_new_capture_cannot_use_old_review_or_unknown_test_bytes(failure_writer):
    case = failure_writer
    with pytest.raises(ValueError, match="requires a reviewed failure writer"):
        prepare.reviewed_writer_additions({}, case.root)
    case.path.write_text(case.path.read_text() + "unreviewed = True\n")
    with pytest.raises(ValueError, match="exact reviewed INIT failure writer successor"):
        prepare.reviewed_writer_additions(case.review, case.root)


@pytest.mark.parametrize("change", ["extra", "missing", "duplicate"])
def test_writer_roster_refuses_unaccounted_capture(change, failure_writer):
    case = failure_writer
    rows = [case.original, case.added]
    if change == "extra":
        case.path.write_text(case.path.read_text() + "    archive(unreviewed)\n")
    elif change == "missing":
        rows.pop(0)
    else:
        rows.append(case.original)
    with pytest.raises(ValueError, match="Exact INIT capture writer roster"):
        prepare.verify_test_writer_roster(rows, case.root)


def test_metadata_cpu_is_explicit_and_single(monkeypatch):
    monkeypatch.setattr(prepare.os, "sched_getaffinity", lambda pid: {3})
    assert prepare.require_cpu(3) == 3
    for invalid in (6, True, -1, "3"):
        with pytest.raises(ValueError, match="explicitly selected single CPU"):
            prepare.require_cpu(invalid)
    monkeypatch.setattr(prepare.os, "sched_getaffinity", lambda pid: {3, 6})
    with pytest.raises(ValueError, match="explicitly selected single CPU"):
        prepare.require_cpu(3)


def test_completion_review_records_bind_exact_files_without_duplicates(tmp_path):
    paths = [tmp_path / name for name in ("failed.json", "repair.json")]
    for path in paths:
        path.write_text('{"scientific_acceptance": false}\n')
    rows = [dict(path=str(path), sha256=prepare.sha(path)) for path in paths]
    assert prepare.completion_review_pins(rows) == {r["path"]: r["sha256"] for r in rows}
    assert prepare.completion_review_pins([]) == {}
    with pytest.raises(ValueError, match="Duplicated or changed"):
        prepare.completion_review_pins(rows + [rows[0]])
    paths[0].write_text('{"scientific_acceptance": true}\n')
    with pytest.raises(ValueError, match="Duplicated or changed"):
        prepare.completion_review_pins(rows)
