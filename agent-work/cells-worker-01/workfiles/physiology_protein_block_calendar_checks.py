"""Prepare a static snapshot now; run bounded qualification only after release.

Preparation imports only the standard library. The existing resource supervisor
is imported lazily for execution. No scientific module, pytest collection or
numeric test runs as part of preparation.
"""

import argparse
import ast
import hashlib
import json
import os
import shutil
import sys
import traceback
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = "agent-work/cells-worker-01/workfiles/"
QUEUE = WORK + "physiology_protein_block_calendar_workqueue.json"
TEST = "tests/integration/test_physiology_protein_block_calendar.py"
ROUND = "test_complete_round_preserves_clocks_tapes_fields_ledgers_and_restart"
HISTORY = "test_independent_carried_block_ionic_protein_and_ledger_history"
CASES = [
    (kind, law, phase)
    for kind in ("passive", "ionic", "calcium", "fuel")
    for law in ("native", "stable")
    for phase in ("SIM", "INIT")
]
CASES += [("clamped", law, "SIM") for law in ("native", "stable")]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def pytest_command(out, label, node=None, selector=None):
    command = [
        sys.executable,
        "-B",
        "-m",
        "pytest",
        "--noconftest",
        "-p",
        "no:cacheprovider",
        "-q",
        TEST if node is None else TEST + "::" + node,
    ]
    if selector is not None:
        command += ["-k", selector]
    return command + [
        "--basetemp",
        str(out / "tmp" / label),
        "--junitxml",
        str(out / ("tests-" + label + ".xml")),
    ]


def phases(out):
    sequence = []

    def add(label, node=None, selector=None, checks=1):
        sequence.append(
            dict(
                label=label,
                command=pytest_command(out, label, node, selector),
                expected_checks=checks,
                reference_forms=0,
            )
        )

    for kind, law, phase in CASES:
        case = f"{kind}-{law}-{phase}"
        for index in range(2 if kind == "clamped" else 3):
            add(f"round-{case}-{index}", ROUND + f"[{case}-round{index}]")
        add("history-" + case, HISTORY + f"[{case}]")
    for law in ("native", "stable"):
        add(
            "unblocked-" + law,
            "test_unblocked_composition_matches_original_complete_charged_loop[" + law + "]",
        )
        for profile in ("fast", "dynamic_off", "protein_off", "zero_level"):
            # Pytest appends the innermost decorator's profile before its law.
            add(
                f"guard-{law}-{profile}",
                "test_original_random_guards_preserve_complete_ionic_evolution["
                + profile
                + "-"
                + law
                + "]",
            )
    add(
        "private-scope-replay-and-destination",
        selector="private_scopes or explicit_full_call_replay or existing_destination",
        checks=3,
    )
    add("checkpoint-association", selector="resealed_checkpoint_context", checks=7)
    add("proposal-association", selector="resealed_proposals", checks=6)
    for law in ("native", "stable"):
        add(
            "failed-protein-" + law,
            "test_real_failed_protein_packet_successor_and_all_ionic_trials_are_retained["
            + law
            + "]",
        )
    add("nonfinite-ionic", selector="failed_ionic_trial_keeps_nonfinite")
    for kind in ("passive", "fuel"):
        add(
            "cumulative-budget-" + kind,
            "test_local_errors_cannot_accumulate_a_larger_global_limit[" + kind + "]",
        )
    add("unsupported-source-setters", selector="unsupported_setters", checks=3)
    add("asymmetric-contact", selector="asymmetric_contact")
    add("complete-restart", selector="restart_requires_entire", checks=5)
    add("terminal-original-calendar", selector="terminal_calendar")
    for case in ["-".join(row) for row in CASES] + ["failed"]:
        sequence.append(
            dict(
                label="isolated-" + case,
                command=[sys.executable, "-B", str(out / "isolated_reference.py"), case, "2"],
                expected_checks=0,
                reference_forms=2,
            )
        )
    assert sum(row["expected_checks"] for row in sequence) == 111
    assert sum(row["reference_forms"] for row in sequence) == 38
    assert len(sequence) == 111
    assert len({row["label"] for row in sequence}) == len(sequence)
    return sequence


def environment(out):
    return dict(
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        PYTHONPATH=str(out / "source/src") + os.pathsep + str(out / "source"),
        JAX_PLATFORMS="cpu",
        JAX_ENABLE_X64="true",
        JAX_DISABLE_JIT="false",
        JAX_ENABLE_COMPILATION_CACHE="false",
        CUDA_VISIBLE_DEVICES="",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        BLIS_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1",
        TF_NUM_INTRAOP_THREADS="1",
        TF_NUM_INTEROP_THREADS="1",
        MALLOC_ARENA_MAX="2",
        TMPDIR=str(out / "tmp"),
        XDG_CACHE_HOME=str(out / "cache"),
        CELLS_COMPONENT_EVIDENCE=str(out / "evidence"),
        XLA_FLAGS="--xla_cpu_multi_thread_eigen=false",
    )


def reference_imports(source):
    """Static transitive import audit without loading scientific modules."""
    pending = ["validation.tissue.physiology_protein_block_calendar_reference"]
    seen, deferred = {}, []
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        path = source / (name.replace(".", "/") + ".py")
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        seen[name] = sha(path)
        parents = {
            child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)
        }
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [item.name for item in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    raise ValueError("Resolve a relative independent-reference import explicitly")
                names = [node.module or ""] + [
                    (node.module + "." if node.module else "") + item.name for item in node.names
                ]
            for imported in names:
                if imported.split(".")[0] in {"cells", "jax", "jaxlib"}:
                    outer, functions = parents.get(node), []
                    while outer is not None:
                        if isinstance(outer, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            functions.append(outer.name)
                        outer = parents.get(outer)
                    if not functions:
                        raise ValueError("Reference module import includes production: " + imported)
                    deferred.append(
                        dict(
                            module=name,
                            functions=functions,
                            line=node.lineno,
                            imported=imported,
                            runtime_import_denial_required=True,
                        )
                    )
                if imported.startswith("validation.") and imported not in seen:
                    pending.append(imported)
    return dict(
        module_import_closure=seen,
        deferred_production_imports_in_dependency_utilities=deferred,
        complete_call_path_independence_requires_future_runtime_denial=True,
    )


def prepare(out, cpu):
    queue = json.loads((ROOT / QUEUE).read_text())
    if queue["kind"] != "cells.complete_charged_block_calendar_preparation@1" or cpu < 0:
        raise ValueError("Require the complete preparation contract and a declared CPU")
    out.mkdir(exist_ok=False)
    source = out / "source"
    source.mkdir()
    for name in ("src", "tests", "validation", "configs"):
        shutil.copytree(
            ROOT / name,
            source / name,
            ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".ruff_cache"),
        )
    for name in (
        "pyproject.toml",
        "AGENTS.md",
        QUEUE,
        queue["contract"],
        *queue["preparation_helpers"],
    ):
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    for name in ("tmp", "cache", "evidence"):
        (out / name).mkdir()
    hashes = {
        str(path.relative_to(source)): sha(path)
        for path in sorted(source.rglob("*"))
        if path.is_file()
    }
    for name, expected in (queue["owned_sha256"] | queue["protected_sha256"]).items():
        if hashes[name] != expected or sha(ROOT / name) != expected:
            raise ValueError("Frozen scientific source changed: " + name)
    for name, expected in hashes.items():
        if sha(ROOT / name) != expected:
            raise ValueError("Source changed during private capture: " + name)
    parsed = []
    for name in (*queue["owned"], *queue["preparation_helpers"]):
        ast.parse((source / name).read_text(), filename=name)
        parsed.append(name)
    closure = reference_imports(source)
    (out / "driver.py").write_bytes(Path(__file__).read_bytes())
    (out / "isolated_reference.py").write_bytes(
        (ROOT / WORK / "physiology_protein_block_calendar_oracle.py").read_bytes()
    )
    (out / "launch.py").write_bytes(
        (ROOT / WORK / "physiology_protein_block_calendar_launch.py").read_bytes()
    )
    sequence = phases(out)
    write(
        out / "static-checks.json",
        dict(
            kind="cells.charged_block_calendar_static_preparation@1",
            ast_parsed=parsed,
            independent_reference_import_closure=closure,
            copied_files=len(hashes),
            pinned_owned_and_protected_unchanged=True,
            input_source_files_stable_during_copy=True,
            numerical_runs=0,
            pytest_collection_runs=0,
            active_job_status_reads=0,
            scientifically_qualified=False,
        ),
    )
    write(
        out / "inputs.json",
        dict(
            kind="cells.complete_charged_block_calendar_checks@1",
            status="prepared_not_executed",
            source_snapshot=str(source),
            source_hashes=hashes,
            owned_source_sha256=queue["owned_sha256"],
            protected_sha256=queue["protected_sha256"],
            helper_sha256={
                name: sha(out / name)
                for name in ("driver.py", "isolated_reference.py", "launch.py")
            },
            resource_limits=queue["resource_limits"] | dict(cpu=cpu),
            tolerances=queue["tolerances"],
            qualification_plan=queue["qualification_plan"],
            environment=environment(out) | dict(CELLS_PROTEIN_BLOCK_CPU=str(cpu)),
            phase_sequence=sequence,
            expected_checks=111,
            expected_reference_forms=38,
            expected_phases=111,
            execution_requires_explicit_cpu_release=True,
            automatic_launch=False,
            automatic_polling=False,
            automatic_followup=False,
            gpu_run=False,
            new_drive_or_heat_law=False,
            prepared_utc=datetime.now(timezone.utc).isoformat(),
        ),
    )
    print(
        json.dumps(
            dict(
                status="prepared_not_executed",
                inputs=str(out / "inputs.json"),
                inputs_sha256=sha(out / "inputs.json"),
                copied_files=len(hashes),
                expected_checks=111,
                numerical_runs=0,
            )
        )
    )


def run(out):
    inputs = json.loads((out / "inputs.json").read_text())
    for name in ("result.json", "failure.json"):
        if (out / name).exists():
            raise FileExistsError(out / name)
    for name, expected in inputs["source_hashes"].items():
        if sha(out / "source" / name) != expected:
            raise ValueError("Captured input source changed: " + name)
    for name, expected in inputs["helper_sha256"].items():
        if sha(out / name) != expected:
            raise ValueError("Prepared validation helper changed: " + name)
    cpu = inputs["resource_limits"]["cpu"]
    os.sched_setaffinity(0, {cpu})
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(out / "source/src"), str(out / "source")]
    from validation.assembly.component_process import run_bounded

    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("JAX_", "XLA_", "PYTEST_", "CELLS_"))
        and key not in {"PYTHONPATH", "PYTHONHOME", "CUDA_VISIBLE_DEVICES"}
    }
    env.update(inputs["environment"])
    resources, runtime, tests, independent = {}, {}, [], []
    stage = "initial_inputs"
    try:
        for phase in inputs["phase_sequence"]:
            stage = phase["label"]
            folder = out / stage
            folder.mkdir()
            print(json.dumps(dict(starting_phase=stage)), flush=True)
            resources[stage] = run_bounded(
                phase["command"],
                directory=folder,
                cwd=out / "source",
                env=env | dict(CELLS_PROTEIN_BLOCK_PHASE=stage),
                timeout=480,
                max_rss_bytes=2**30,
                min_available_bytes=8 * 2**30,
                process_tree_memory_metric="rss",
            )
            telemetry = (
                out / "evidence/tissue-step" / ("protein-block-calendar-runtime-" + stage + ".json")
            )
            runtime[stage] = json.loads(telemetry.read_text())
            assert runtime[stage]["measured_child_cpu_affinity"] == [cpu]
            if phase["expected_checks"]:
                rows = ET.parse(out / ("tests-" + stage + ".xml")).getroot().findall(".//testcase")
                assert len(rows) == phase["expected_checks"], (stage, len(rows))
                assert all(
                    all(row.find(key) is None for key in ("failure", "error", "skipped"))
                    for row in rows
                )
                tests.extend(row.attrib for row in rows)
            else:
                result = json.loads(
                    (
                        out
                        / "evidence"
                        / ("independence-" + stage.removeprefix("isolated-") + ".json")
                    ).read_text()
                )
                assert result["actual_reference_forms"] == phase["reference_forms"]
                independent.append(result)
            print(
                json.dumps(
                    dict(completed_phase=stage, seconds=resources[stage]["elapsed_seconds"])
                ),
                flush=True,
            )
        assert len(tests) == inputs["expected_checks"]
        assert (
            sum(row["actual_reference_forms"] for row in independent)
            == inputs["expected_reference_forms"]
        )
        for name, expected in inputs["source_hashes"].items():
            assert sha(out / "source" / name) == expected, name
        for name, expected in (inputs["owned_source_sha256"] | inputs["protected_sha256"]).items():
            assert sha(ROOT / name) == expected, name
        write(
            out / "result.json",
            dict(
                kind=inputs["kind"],
                status="passed",
                checks=len(tests),
                check_ids=tests,
                independent_reference_forms=sum(
                    row["actual_reference_forms"] for row in independent
                ),
                maximum_independent_error_fraction=max(
                    row["maximum_error_fraction"] for row in independent
                ),
                resources=resources,
                measured_child_runtime=runtime,
                full_qualification=True,
                owned_source_sha256=inputs["owned_source_sha256"],
                protected_sources_unchanged=True,
                original_frozen_code_and_thresholds=True,
                actual_raw_failed_trials_packets_successors_retained=True,
                complete_blocker_ionic_protein_ledger_calls=True,
                actual_ionic_solver="NumPy CPU",
                gpu_run=False,
                new_drive_or_heat_law=False,
                automatic_followup=False,
            ),
        )
    except BaseException:
        write(
            out / "failure.json",
            dict(
                kind=inputs["kind"],
                status="failed",
                stage=stage,
                traceback=traceback.format_exc(),
                completed_phases=list(resources),
                automatic_retry=False,
                automatic_followup=False,
            ),
        )
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "run"))
    parser.add_argument("directory", type=Path)
    parser.add_argument("--cpu", type=int, default=7)
    parser.add_argument("--cpu-released", action="store_true")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.directory.resolve(), args.cpu)
    else:
        if not args.cpu_released:
            parser.error("Full execution waits for explicit coordination of the declared CPU")
        run(args.directory.resolve())


if __name__ == "__main__":
    main()
