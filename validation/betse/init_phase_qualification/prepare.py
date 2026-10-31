"""Prepare a held INIT62 execution packet from canonical checkout bytes only."""

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
import resource
import shutil
import sys
import traceback
from pathlib import Path

from validation import source_snapshot

ROOT = Path(__file__).resolve().parents[3]
OWNED = "validation/betse/init_phase_qualification"
BASE = Path("/mnt/workspaces/Cells")
PRIOR_PACKET = BASE / "betse-normal-ecm-init-phase-prepared-20261031-06"
PRIOR_RUNNER = BASE / "betse-normal-ecm-init-phase-launch-preparation-20261031-06"
FAILURE_REVIEW = BASE / "ecm-init06-failure-review-20261031-01/REVIEW.json"
CLOSURE_REVIEW = BASE / "init-checkout-qualification-20261031-01/closure-review.json"
TEST = "tests/unit/test_betse_normal_ecm_init_phase.py"
REFERENCE = "validation/betse/betse_normal_ecm_init_phase_reference.py"
DRIVER = "agent-work/cells-worker-01/workfiles/betse_normal_ecm_init_phase_driver.py"
RESOURCES = "agent-work/cells-worker-01/workfiles/betse_normal_ecm_reviewed_successors_resources.py"
RUNNER_FILES = {
    **{
        name + ".py": OWNED + "/" + name + ".py"
        for name in (
            "common",
            "contracts",
            "controller",
            "read_evidence",
            "init_runtime_plugin",
            "supervise",
            "bootstrap_probe",
        )
    },
    "resource_guard.py": "validation/betse/betse_mesh_lifecycle_preparation_guard.py",
    "qualification_inventory.py": "validation/geometry/qualification_inventory.py",
    "runtime_inventory.py": "validation/betse/betse_normal_channel_join_runtime.py",
    "source_snapshot.py": "validation/source_snapshot.py",
}
TOOL_FILES = {
    "tools/archive_binding.py": OWNED + "/archive_binding.py",
    "tools/capture_binding.py": OWNED + "/capture_binding.py",
    "tools/qualification_typed_evidence.py": "validation/geometry/qualification_typed_evidence.py",
}
ADDED_REFERENCES = {
    "validation/betse/betse_ecm_sodium_reference.py",
    "validation/betse/betse_ecm_cal2_reference.py",
    "validation/betse/betse_ecm_reference_failure.py",
}
NORMALIZED_TEST_SHA256 = "38d891600524119e359c34aea701071e5158d83c03fbfa0c2e7c8c2e4c8d1bce"


def sha(path):
    return source_snapshot.digest(path)


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    source_snapshot.write_json(Path(path), value)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def contracts(repository):
    common = load("_init_common_preparation", repository / OWNED / "common.py")
    previous = sys.modules.get("common")
    sys.modules["common"] = common
    try:
        return load("_init_contract_preparation", repository / OWNED / "contracts.py")
    finally:
        if previous is None:
            sys.modules.pop("common", None)
        else:
            sys.modules["common"] = previous


def reviewed_versions(old, current, changes):
    """Bind current bytes to the retained baseline or its reviewed successor."""
    actual_changed = {name for name in old if old[name] != current[name]}
    if not actual_changed <= set(changes):
        raise ValueError("Checkout differs from independent closure review")
    baseline = []
    for name, row in changes.items():
        if old[name] != row["old_sha256"] or current[name] not in {
            row["old_sha256"],
            row["checkout_sha256"],
        }:
            raise ValueError("Reviewed source delta changed: " + name)
        if current[name] == row["old_sha256"]:
            baseline.append(name)
    return sorted(actual_changed), sorted(baseline)


def closure(repository, previous_contract, previous_plan, review_path):
    utility = load("_init_source_resources_only", repository / RESOURCES)
    found = utility.audit(repository, "betse_normal_ecm_init_phase")
    manual = utility.manual_review(found)
    scoped_outputs = {
        (TEST, "references", "output.read_text()"),
        (REFERENCE, "file_record", "path.open('rb')"),
    }
    for row in manual["pending_manual_reads"]:
        key = (row["module"], row["containing_function"], row["expression"])
        if key not in scoped_outputs:
            raise ValueError("Unresolved INIT source input: " + repr(key))
        # Both reads concern files written in the current worker: the returned
        # reference JSON and hash records of retained raw failure sidecars.
        old = ast.parse((PRIOR_PACKET / "source" / row["module"]).read_bytes())
        new = ast.parse((repository / row["module"]).read_bytes())
        name = row["containing_function"]
        before = [n for n in ast.walk(old) if isinstance(n, ast.FunctionDef) and n.name == name]
        after = [n for n in ast.walk(new) if isinstance(n, ast.FunctionDef) and n.name == name]
        if (
            len(before) != 1
            or len(after) != 1
            or ast.dump(before[0], include_attributes=False)
            != ast.dump(after[0], include_attributes=False)
        ):
            raise ValueError("Changed reviewed generated-output reader: " + name)
        row.update(classification="current_worker_generated_reference_output", input_resource=False)
    manual["scoped_generated_output_reads"] = manual["pending_manual_reads"]
    manual["pending_manual_reads"] = []
    runtime = found["scientific_import_closure"]
    references = found["reference_closure"]
    resources = manual["resource_sha256"]
    old_refs = previous_plan["reference_runtime_source_sha256"]
    if (
        len(runtime) != 124
        or set(references) != set(old_refs) | ADDED_REFERENCES
        or len(references) != 27
        or set(resources) != set(previous_contract["required_resource_sha256"])
        or len(resources) != 28
    ):
        raise ValueError("INIT closure/resource membership changed outside the reviewed scope")
    pins = runtime | references | resources
    review = read(review_path)
    if review["blockers"] or review["scientific_acceptance"] is not False:
        raise ValueError("Independent closure review unavailable or outside source scope")
    changed = review["changed_files"]
    old = {
        name: digest
        for name, digest in previous_contract["source_file_sha256"].items()
        if name in pins and name not in ADDED_REFERENCES
    }
    # The old contract records the full source tree; compare precisely its
    # reviewed runtime/reference/resource union, never the unused tree.
    old_union = set(runtime) | set(old_refs) | set(resources)
    if set(old) != old_union or len(old_union) != 173 or len(pins) != 176:
        raise ValueError("Exact reviewed source union is incomplete")
    actual_changed, baseline = reviewed_versions(old, pins, changed)
    for row in review["additional_reference_closure"]:
        if row["path"] not in ADDED_REFERENCES or pins[row["path"]] != row["sha256"]:
            raise ValueError("Reviewed unconditional reference import changed")
    if sha(repository / TEST) != NORMALIZED_TEST_SHA256:
        raise ValueError("Require the reviewed test-only calcium comparator normalization")
    return dict(
        runtime=runtime,
        references=references,
        resources=resources,
        pins=pins,
        literal_resource_audit=found["literal_resource_audit"],
        manual_review=manual,
        review_path=str(review_path),
        review_sha256=sha(review_path),
        changed_source_paths=actual_changed,
        reviewed_successor_paths_currently_at_retained_baseline=baseline,
    )


def call_sites(rows, source, *, baseline=None):
    parsed, result = {}, []
    for original in rows:
        row = dict(original)
        name = row["module"]
        if name not in parsed:
            parsed[name] = ast.parse((source / name).read_bytes())
        candidates = [
            node
            for node in ast.walk(parsed[name])
            if isinstance(node, ast.Call)
            and ast.unparse(node.func) == row["callee"]
            and hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
            == row["AST_sha256"]
        ]
        exact = [n for n in candidates if n.lineno == row["line"]]
        if len(exact) == 1:
            node = exact[0]
        elif len(candidates) == 1:
            node = candidates[0]
        elif not candidates:
            raise ValueError("Missing/ambiguous original archive call AST: " + repr(row))
        else:
            before = ast.parse(((baseline or PRIOR_PACKET / "source") / name).read_bytes())
            old_calls = [
                n
                for n in ast.walk(before)
                if isinstance(n, ast.Call)
                and n.lineno == row["line"]
                and ast.unparse(n.func) == row["callee"]
                and hashlib.sha256(ast.dump(n, include_attributes=False).encode()).hexdigest()
                == row["AST_sha256"]
            ]
            if len(old_calls) != 1:
                raise ValueError("Missing/ambiguous original archive call AST: " + repr(row))
            owners = [
                n
                for n in before.body
                if isinstance(n, ast.FunctionDef)
                and n.lineno <= old_calls[0].lineno <= n.end_lineno
            ]
            current = [
                n
                for n in parsed[name].body
                if isinstance(n, ast.FunctionDef) and owners and n.name == owners[0].name
            ]
            if (
                len(owners) != 1
                or len(current) != 1
                or ast.dump(owners[0], include_attributes=False)
                != ast.dump(current[0], include_attributes=False)
            ):
                raise ValueError(
                    "Archive occurrence lacks unchanged function authority: " + repr(row)
                )
            old_occurrences = sorted(
                (
                    n
                    for n in ast.walk(owners[0])
                    if isinstance(n, ast.Call)
                    and ast.unparse(n.func) == row["callee"]
                    and hashlib.sha256(ast.dump(n, include_attributes=False).encode()).hexdigest()
                    == row["AST_sha256"]
                ),
                key=lambda n: (n.lineno, n.col_offset),
            )
            new_occurrences = sorted(
                (
                    n
                    for n in ast.walk(current[0])
                    if isinstance(n, ast.Call)
                    and ast.unparse(n.func) == row["callee"]
                    and hashlib.sha256(ast.dump(n, include_attributes=False).encode()).hexdigest()
                    == row["AST_sha256"]
                ),
                key=lambda n: (n.lineno, n.col_offset),
            )
            if len(old_occurrences) != len(new_occurrences):
                raise ValueError("Archive occurrence inventory changed")
            node = new_occurrences[old_occurrences.index(old_calls[0])]
        row["line"] = node.lineno
        result.append(row)
    return result


def canonical_producer(name):
    if name.startswith("source/"):
        relative = name.removeprefix("source/")
    elif Path(name).is_absolute() and "/source/" in name:
        relative = name.split("/source/", 1)[1]
    else:
        return None
    source_snapshot.relative_path(relative)
    if not relative.startswith(("src/cells/", "tests/", "validation/")):
        raise ValueError("Unknown historical producer namespace: " + name)
    return relative


def refresh_pins(table, source):
    result = {}
    for name, expected in table.items():
        relative = canonical_producer(name)
        if relative is not None:
            target = "source/" + relative
            value = sha(source / relative)
            if target in result and result[target] != value:
                raise ValueError("Inconsistent producer aliases")
            result[target] = value
        elif Path(name).is_absolute():
            if sha(name) != expected:
                raise ValueError("Pinned external producer changed: " + name)
            result[name] = expected
        else:
            raise ValueError("Unknown capture producer binding: " + name)
    return result


def seal(directory):
    for path in sorted(directory.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_symlink():
            raise ValueError("Linked execution snapshot")
        path.chmod(0o555 if path.is_dir() else (path.stat().st_mode & 0o111) | 0o444)
    directory.chmod(0o555)


def metadata_preflight(packet, runner, plan):
    """Check the assembled contracts using stdlib helpers, without releasing a worker."""
    names = (
        "common",
        "contracts",
        "source_snapshot",
        "archive_binding",
        "capture_binding",
        "qualification_typed_evidence",
    )
    before = {name: sys.modules.get(name) for name in names}
    old_path = list(sys.path)
    sys.path[:0] = [str(packet / "tools"), str(runner)]
    for name in names:
        sys.modules.pop(name, None)
    try:
        controller = load("_assembled_init_controller_metadata", runner / "controller.py")
        controller.verify_packet(packet, plan)
        binder = __import__("capture_binding")
        contract = binder.verify_profile("ordinary_ecm_init_phase_01")
        if contract["execution_hold"] is not True:
            raise ValueError("Capture profile hold was lost")
        if any(
            name.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib"}
            for name in sys.modules
        ):
            raise ValueError("Scientific import during metadata-only preparation")
        return dict(packet_contract="passed", capture_profile="passed", scientific_imports=0)
    finally:
        sys.path[:] = old_path
        for name, module in before.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def prepare(destination, *, repository=ROOT, review_path=CLOSURE_REVIEW):
    repository = Path(repository).resolve()
    destination = Path(destination).absolute()
    if not destination.resolve().is_relative_to(BASE) or destination.resolve().is_relative_to(
        repository
    ):
        raise ValueError("Fresh preparation output must be under /mnt/workspaces/Cells")
    destination.mkdir(parents=True, exist_ok=False)
    try:
        prior_inputs = read(PRIOR_PACKET / "inputs.json")
        prior_manifest = read(PRIOR_PACKET / "MANIFEST.json")
        prior_plan = read(PRIOR_RUNNER / "plan.json")
        prior_contract = read(PRIOR_RUNNER / "source-resource-contract.json")
        evidence = read(PRIOR_RUNNER / "expected-evidence.json")
        graph = closure(repository, prior_contract, prior_plan, review_path)
        accounting = read(PRIOR_PACKET / "tools/accounting.json")
        profile = read(PRIOR_PACKET / "tools/inputs.json")
        selected_sources = set(graph["pins"])
        selected_sources.update(
            relative
            for table in (
                accounting["source_sha256"],
                profile["profiles"]["ordinary_ecm_init_phase_01"]["writer_source_sha256"],
            )
            for name in table
            if (relative := canonical_producer(name)) is not None
        )
        selected = (
            selected_sources
            | set(RUNNER_FILES.values())
            | set(TOOL_FILES.values())
            | {
                DRIVER,
                RESOURCES,
                "validation/frozen_resource_dependencies.py",
                "tests/unit/test_source_snapshot.py",
                "AGENTS.md",
                "pyproject.toml",
            }
        )
        selected.update(str(p.relative_to(repository)) for p in (repository / OWNED).glob("*.py"))
        expected = {name: sha(source_snapshot.regular_file(repository, name)) for name in selected}
        if any(expected[name] != pin for name, pin in graph["pins"].items()):
            raise ValueError("Source changed after closure analysis")
        checkout = destination / "checkout"
        snapshot = source_snapshot.freeze(repository, checkout, {name: name for name in selected})
        if any(snapshot["files"][name]["sha256"] != pin for name, pin in expected.items()):
            raise ValueError("Source changed between analysis and checkout snapshot")
        packet, runner = destination / "packet", destination / "runner"
        packet.mkdir()
        runner.mkdir()
        # Retain historical native/evidence inputs only. Executable Cells code,
        # driver and archive tools below are always copied from the Git snapshot.
        for name, digest in prior_manifest["files"].items():
            if name.startswith(("source/", "tools/")) or name in ("inputs.json", "driver.py"):
                continue
            source = PRIOR_PACKET / source_snapshot.relative_path(name)
            if source.is_symlink() or sha(source) != digest:
                raise ValueError("Changed frozen native/evidence input: " + name)
            target = packet / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        bindings = {}
        for name in sorted(selected_sources):
            target = packet / "source" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(checkout / name, target)
            bindings["source/" + name] = name
        for target_name, name in {"driver.py": DRIVER, **TOOL_FILES}.items():
            target = packet / target_name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(checkout / name, target)
            bindings[target_name] = name
        for target_name, name in RUNNER_FILES.items():
            shutil.copyfile(checkout / name, runner / target_name)
        accounting["source_sha256"] = refresh_pins(accounting["source_sha256"], packet / "source")
        previous_sites = accounting["INIT_archive_call_sites"]
        accounting["INIT_archive_call_sites"] = call_sites(previous_sites, packet / "source")
        if sum(row["module"] == TEST for row in previous_sites) != 20:
            raise ValueError("Exact original20 INIT archive calls required")
        moved_sites = sum(
            before["line"] != after["line"]
            for before, after in zip(
                previous_sites, accounting["INIT_archive_call_sites"], strict=True
            )
        )
        active = profile["profiles"]["ordinary_ecm_init_phase_01"]
        active["archive_call_sites"] = call_sites(active["archive_call_sites"], packet / "source")
        active["writer_source_sha256"] = refresh_pins(
            active["writer_source_sha256"], packet / "source"
        )
        profile["tool_sha256"] = {Path(name).name: sha(packet / name) for name in TOOL_FILES}
        accounting["checkout_source_snapshot_sha256"] = sha(checkout / "SNAPSHOT.json")
        profile["checkout_source_snapshot_sha256"] = sha(checkout / "SNAPSHOT.json")
        write(packet / "tools/accounting.json", accounting)
        write(packet / "tools/inputs.json", profile)
        inputs = copy.deepcopy(prior_inputs)
        inputs.update(
            status="held_checkout_comparator_correction",
            execution_hold=True,
            source_sha256={
                name: sha(packet / "source" / name) for name in sorted(selected_sources)
            },
            tool_sha256={"tools/" + p.name: sha(p) for p in (packet / "tools").iterdir()},
            driver_sha256=sha(packet / "driver.py"),
            checkout_bindings=bindings,
            checkout_snapshot=str(checkout),
            checkout_snapshot_sha256=sha(checkout / "SNAPSHOT.json"),
            git_revision=snapshot["git_revision"],
            source_closure_review=graph["review_path"],
            source_closure_review_sha256=graph["review_sha256"],
            previous_failed_run_review=str(FAILURE_REVIEW),
            previous_failure_reclassified=False,
        )
        metadata = contracts(repository)
        declared = {name: metadata.declaration(group) for name, group in inputs["groups"].items()}
        if (
            declared != evidence["groups"]
            or sum(len(v["typed_archives"]) for v in declared.values()) != 1298
        ):
            raise ValueError("Original complete 1298-archive evidence contract changed")
        write(packet / "inputs.json", inputs)
        write(packet / "checkout-closure.json", graph)
        manifest = {str(p.relative_to(packet)): sha(p) for p in packet.rglob("*") if p.is_file()}
        write(packet / "MANIFEST.json", dict(files=manifest, scientific_acceptance=False))
        runner_hashes = {name: sha(runner / name) for name in RUNNER_FILES}
        contract = dict(
            runtime_files=len(graph["runtime"]),
            reference_files=len(graph["references"]),
            resource_files=len(graph["resources"]),
            unresolved_reads=0,
            required_resource_sha256=graph["resources"],
            source_file_sha256=inputs["source_sha256"],
            source_audit_not_a_general_resolver=True,
            closure_review_sha256=graph["review_sha256"],
        )
        write(runner / "source-resource-contract.json", contract)
        write(runner / "expected-evidence.json", evidence)
        plan = copy.deepcopy(prior_plan)
        plan.update(
            status="sealed_held",
            packet=str(packet),
            output=str(destination / "qualification-01"),
            cpu=4,
            runner_sha256=runner_hashes,
            runner_checkout_bindings=RUNNER_FILES,
            checkout_snapshot=str(checkout),
            checkout_snapshot_sha256=sha(checkout / "SNAPSHOT.json"),
            inputs_sha256=sha(packet / "inputs.json"),
            manifest_sha256=sha(packet / "MANIFEST.json"),
            reference_runtime_source_sha256=graph["references"],
            source_resource_contract_sha256=sha(runner / "source-resource-contract.json"),
            evidence_contract_sha256=sha(runner / "expected-evidence.json"),
            root_review_still_required=True,
        )
        plan["pins"].update(
            {str(review_path): sha(review_path), str(FAILURE_REVIEW): sha(FAILURE_REVIEW)}
        )
        write(runner / "plan.json", plan)
        write(
            runner / "release-template.json",
            dict(
                authorized=False,
                requested_round=False,
                cpu_coordinated=False,
                source_and_runner_accepted_by_root=False,
                cpu=4,
                authorization_note="",
                plan_sha256=sha(runner / "plan.json"),
                seal_sha256="Root must fill after review",
            ),
        )
        seal_files = {p.name: sha(p) for p in runner.iterdir() if p.is_file()}
        write(runner / "seal.json", dict(files=seal_files, root_release_required=True))
        checked = metadata_preflight(packet, runner, plan)
        source_snapshot.assert_checkout_unchanged(checkout)
        seal(packet)
        seal(runner)
        result = dict(
            status="held_prepared_from_checkout_no_scientific_execution",
            git_revision=snapshot["git_revision"],
            checkout_snapshot=str(checkout),
            checkout_snapshot_sha256=sha(checkout / "SNAPSHOT.json"),
            packet=str(packet),
            packet_manifest_sha256=sha(packet / "MANIFEST.json"),
            runner=str(runner),
            runner_plan_sha256=sha(runner / "plan.json"),
            runner_seal_sha256=sha(runner / "seal.json"),
            planned=inputs["planned"],
            typed_archive_paths=1298,
            runtime_files=124,
            reference_files=27,
            resources=28,
            metadata_cpu=6,
            scientific_cpu=4,
            numerical_execution=0,
            scientific_imports=0,
            release_authorized=False,
            original_failure=dict(passed_prerequisite_raw=35, failed=1, unrun=26),
            fresh_full62_required=True,
            no_positive_INIT_credit_retained=True,
            launch_command=[
                plan["python"],
                "-B",
                str(runner / "supervise.py"),
                "launch",
                "--release",
                str(destination / "release.json"),
            ],
            immutable_code=True,
            input_hold_preserved=True,
            metadata_preflight=checked,
            original_INIT_writer_AST_sites=20,
            all_capture_writer_AST_sites=len(previous_sites),
            archive_AST_hashes_unchanged=True,
            rebound_source_line_locations=moved_sites,
        )
        write(destination / "preparation.json", result)
        (destination / "preparation.json").chmod(0o444)
        return result
    except BaseException as error:
        write(
            destination / "FAILURE.json",
            dict(
                status="incomplete_preparation",
                type=type(error).__name__,
                message=str(error),
                traceback=traceback.format_exc(),
                scientific_execution=0,
                automatic_retry=False,
            ),
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--closure-review", type=Path, default=CLOSURE_REVIEW)
    args = parser.parse_args()
    if os.sched_getaffinity(0) != {6}:
        parser.error("Metadata preparation requires CPU6")
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 512 * 2**20))
    result = prepare(args.output, review_path=args.closure_review)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
