# ruff: noqa: E501
"""Prepare a held INIT snapshot: copy/hash/AST/resource metadata only.

The immutable lifecycle02 source tree is the only common-body parent. Live
foreign files are never refreshed. New files are exclusively this worker's
INIT prefix. No fixture/reference/model or scientific AST is evaluated.
"""

import argparse
import ast
import hashlib
import json
import shutil
import sys
from pathlib import Path

from betse_normal_ecm_reviewed_successors_resources import audit, manual_review

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-run-lifecycle-prepared-20261031-02")
CAPACITY = Path(
    "/mnt/workspaces/Cells/ecm-event-mechanics-lifecycle-capture-capacity-prepared-20261031-01"
)
PREFIX = "betse_normal_ecm_init_phase"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def copy(source, target, pin=None):
    if source.is_symlink() or not source.is_file():
        raise ValueError("Require immutable regular source: " + str(source))
    if pin is not None and sha(source) != pin:
        raise ValueError("Changed explicit parent source: " + str(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()  # This is a newly created private preparation tree only.
    shutil.copyfile(source, target)
    assert sha(target) == sha(source)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.absolute()
    if out.exists() or not out.is_relative_to(WORK):
        raise ValueError("Use an exclusive new worker INIT preparation directory")
    parent = json.loads((PARENT / "inputs.json").read_text())
    if (
        sha(PARENT / "inputs.json")
        != "0b3b3a1dd39190b74b60f31fbb65d48349fe7c21e9962c3df588ad8c081d58e4"
    ):
        raise ValueError("Wrong reviewed common parent")
    out.mkdir()
    source = out / "source"
    source.mkdir()
    for name, pin in parent["source_hashes"].items():
        copy(PARENT / "source" / name, source / name, pin)
    own = []
    for directory in (
        ROOT / "src/cells/processes",
        ROOT / "validation/betse",
        ROOT / "tests/unit",
        WORK,
    ):
        for path in sorted(directory.glob("*" + PREFIX + "*")):
            if path.is_file():
                relative = str(path.relative_to(ROOT))
                copy(path, source / relative)
                own.append(relative)
    copy(WORK / f"{PREFIX}_driver.py", out / "driver.py")
    (out / ".execution_hold").write_text(
        "Held: independent Chief source/resource/capture review and a new requested CPU-coordinated round. No launch, retry, polling, GPU or inherited pass.\n"
    )
    # Preserve the exact existing native snapshots and their binding evidence.
    native = {}
    for name, pin in parent["native_snapshot_sha256"].items():
        copy(PARENT / name, out / name, pin)
        native[name] = pin
    # Bind the complete installed-exact native Python tree, including INIT and
    # setup source files beyond the common composition's original union.
    checkout = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse")
    installed = Path("/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages/betse")
    live_native = {}
    for path in sorted(checkout.rglob("*.py")):
        name = str(path.relative_to(checkout))
        pin = sha(path)
        if sha(installed / name) != pin:
            raise ValueError("Native checkout differs from installed source: " + name)
        live_native["betse/" + name] = pin
        for label, original in (("checkout", path), ("installed", installed / name)):
            relative = "native-inputs/" + label + "/betse/" + name
            if relative not in native:
                copy(original, out / relative, pin)
                native[relative] = pin
            elif native[relative] != pin:
                raise ValueError("Conflicting native source pin: " + name)
    if len(live_native) != 332:
        raise ValueError("Wrong full native source inventory")
    # Full literal/dynamic resource closure, without importing science.
    resources = audit(source, PREFIX)
    reviewed = manual_review(resources)
    still_pending = []
    # The established auditor returns its complete reviewed list and pending
    # rows. Classify only our new fresh-reference filename spelling here.
    for _key, value in reviewed.items():
        if (
            isinstance(value, list)
            and value
            and isinstance(value[0], dict)
            and "expression" in value[0]
        ):
            for row in value:
                if (
                    row.get("classification") == "manual_resolution_pending"
                    and row.get("module") == "tests/unit/test_" + PREFIX + ".py"
                    and row.get("containing_function") == "references"
                    and row.get("expression") == "output.read_text()"
                ):
                    row.update(
                        classification="future_fresh_reference_output",
                        rationale="Explicit path just supplied to checked fresh subprocess; no packaged data read",
                    )
    pending = reviewed["pending_manual_reads"]
    for row in pending:
        if row.get("classification") == "manual_resolution_pending":
            still_pending.append(row)
    reviewed["pending_manual_reads"] = still_pending
    reviewed["INIT_additional_resolution"] = (
        "The new references() output.read_text() reads the explicit fresh subprocess "
        "output path, after a checked exit; it is not a packaged data read."
    )
    if resources["literal_resource_audit"]["missing_resources"] or still_pending:
        write(
            out / "resource-unresolved.json",
            dict(inventory=resources, review=reviewed, pending=still_pending),
        )
        raise ValueError("Resource closure requires explicit resolution; no package release")
    write(
        out / "resource-audit.json",
        dict(
            inventory=resources, review=reviewed, scientific_imports=0, scientific_AST_executions=0
        ),
    )
    tools = out / "tools"
    tools.mkdir()
    for name in ("capture_binding.py", "archive_binding.py", "qualification_typed_evidence.py"):
        copy(CAPACITY / "tools" / name, tools / name)
    profile_path = tools / "capture_binding.py"
    profile_before = profile_path.read_text()
    old_check = "        if sha(path) != expected:"
    new_check = "        if sha(Path(path) if Path(path).is_absolute() else HERE.parent / path) != expected:"
    if profile_before.count(old_check) != 1:
        raise ValueError("Unexpected profile wrapper source")
    profile_path.write_text(profile_before.replace(old_check, new_check, 1))
    # Use a distinct INIT profile. The format bound is not a measured case
    # maximum, a catalogue profile, or a claim that every future archive fits.
    accounting = json.loads((CAPACITY / "tools/accounting.json").read_text())
    accounting["scope_profiles"] = ["ordinary_ecm_init_phase_01"]
    accounting["status"] = "new_INIT_profile_held_for_Chief_review"
    writers = {}
    sites = []
    for relative, pin in resources["scientific_import_closure"].items():
        path = source / relative
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and (
                ast.unparse(node.func).endswith("write_archive")
                or ast.unparse(node.func) == "archive"
            ):
                sites.append(
                    dict(
                        module=relative,
                        line=node.lineno,
                        callee=ast.unparse(node.func),
                        AST_sha256=hashlib.sha256(
                            ast.dump(node, include_attributes=False).encode()
                        ).hexdigest(),
                    )
                )
                writers[str(path)] = pin
    for relative in (
        "validation/betse/betse_normal_current_native.py",
        "validation/betse/betse_fast_solver_native.py",
    ):
        writers[str(source / relative)] = sha(source / relative)
    # External entries are the pinned NumPy/stdlib format implementation only.
    # Actual INIT producers are bound inside this prospective snapshot.
    accounting["source_sha256"] = {
        path: pin
        for path, pin in accounting["source_sha256"].items()
        if "/site-packages/numpy/" in path or path == "/usr/lib/python3.13/zipfile/__init__.py"
    }
    accounting["source_sha256"].update(
        {str(Path(path).relative_to(out)): pin for path, pin in writers.items()}
    )
    accounting["INIT_archive_call_sites"] = sites
    write(tools / "accounting.json", accounting)
    contract = dict(
        kind="cells.held_ordinary_INIT_capture_profile@1",
        profiles=dict(
            ordinary_ecm_init_phase_01=dict(writer_source_sha256=writers, archive_call_sites=sites)
        ),
        tool_sha256={
            name: sha(tools / name)
            for name in (
                "capture_binding.py",
                "archive_binding.py",
                "qualification_typed_evidence.py",
            )
        },
        execution_hold=True,
        release_authorized=False,
        member_limit=310689,
        observed_case_maximum_claim=False,
        all_captures_fit_byte_caps_claim=False,
    )
    write(tools / "inputs.json", contract)
    # The helper's one-constant inverse remains byte-exact to the catalog tool.
    baseline = (PARENT / "archive_binding.py").read_bytes()
    candidate = (tools / "archive_binding.py").read_bytes()
    if candidate.replace(b"MAX_MEMBERS=310689\n", b"MAX_MEMBERS=32768\n", 1) != baseline:
        raise ValueError("Unexpected capture-helper change beyond member constant")
    for path in source.rglob("*.py"):
        compile(path.read_text(), str(path), "exec")
    queue = json.loads(
        (source / "agent-work/cells-worker-01/workfiles" / f"{PREFIX}_workqueue.json").read_text()
    )
    hashes = {str(p.relative_to(source)): sha(p) for p in sorted(source.rglob("*")) if p.is_file()}
    inputs = dict(
        kind="cells.held_ordinary_INIT_package@1",
        status="source_static_preparation_unrun",
        execution_hold=True,
        execution_hold_reasons=[
            "Chief independent source/resource/capture-profile review",
            "New requested CPU-coordinated numerical round",
            "No existing qualification inherited",
        ],
        parent=dict(path=str(PARENT / "inputs.json"), sha256=sha(PARENT / "inputs.json")),
        own_files=own,
        source_sha256=hashes,
        native_snapshot_sha256=native,
        live_native_source_sha256=live_native,
        native_checkout="/mnt/workspaces/Cells/betse-v1.5.0",
        installed_native_package="/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages",
        driver_sha256=sha(out / "driver.py"),
        tool_sha256={str(p.relative_to(out)): sha(p) for p in sorted(tools.iterdir())},
        resource_audit_sha256=sha(out / "resource-audit.json"),
        groups=queue["groups"],
        planned=queue["planned"],
        resources=dict(
            cpu_count=1,
            threads=1,
            gpu=False,
            max_scientific_command_seconds=480,
            max_metadata_reader_seconds=120,
            max_process_tree_rss_bytes=2**30,
            min_available_host_memory_bytes=8 * 2**30,
        ),
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_reference_model_evaluations=0,
        pytest_collections=0,
        numerical_runs=0,
        active_job_queries=0,
        inherited_qualification=False,
        automatic_launch=False,
        automatic_polling=False,
        automatic_followup=False,
    )
    write(out / "inputs.json", inputs)
    write(
        out / "MANIFEST.json",
        dict(
            kind="cells.held_INIT_preparation_manifest@1",
            status="held_unrun",
            files={str(p.relative_to(out)): sha(p) for p in sorted(out.rglob("*")) if p.is_file()},
            scientific_evaluations=0,
        ),
    )
    if any(
        name.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib"}
        for name in sys.modules
    ):
        raise ValueError("A scientific module was imported during preparation")
    print(
        json.dumps(
            dict(
                status="held_prepared",
                files=len(hashes),
                native_files=len(native),
                archive_sites=len(sites),
                inputs_sha256=sha(out / "inputs.json"),
                manifest_sha256=sha(out / "MANIFEST.json"),
            )
        )
    )


if __name__ == "__main__":
    main()
