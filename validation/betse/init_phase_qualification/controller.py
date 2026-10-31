"""Held INIT detached controller; no science import during preparation."""

import argparse
import os
import shutil
import subprocess
import traceback
from pathlib import Path

from common import (
    HERE,
    canonical,
    exact_ids,
    memory,
    read,
    require,
    resource_receipt,
    sha,
    utc,
    verify_files,
    verify_release,
    verify_runtime,
    write,
)
from contracts import declaration


def verify_packet(packet, plan):
    packet = Path(packet)
    require(
        sha(packet / "MANIFEST.json") == plan["manifest_sha256"]
        and sha(packet / "inputs.json") == plan["inputs_sha256"],
        "Reviewed source/input pins",
    )
    manifest, inputs = read(packet / "MANIFEST.json"), read(packet / "inputs.json")
    verify_files(packet, manifest["files"])
    require(
        inputs["execution_hold"] is True
        and inputs["planned"] == plan["planned"]
        and inputs["groups"] == plan["groups"],
        "Exact held source declarations",
    )
    verify_files(packet / "source", inputs["source_sha256"], exact=True)
    verify_files(packet, inputs["native_snapshot_sha256"])
    verify_files(packet, inputs["tool_sha256"])
    verify_files(Path(inputs["native_checkout"]), inputs["live_native_source_sha256"])
    verify_files(Path(inputs["installed_native_package"]), inputs["live_native_source_sha256"])
    require(
        sha(packet / "driver.py") == inputs["driver_sha256"],
        "Original held driver preserved",
    )
    all_ids = [node for group in inputs["groups"].values() for node in group["node_ids"]]
    require(len(all_ids) == len(set(all_ids)) == 62, "Exact unique full 62-check roster")
    require(
        sum(g["accepted_calls"] for g in inputs["groups"].values()) == 61
        and sum(g["independent_forms"] for g in inputs["groups"].values()) == 986,
        "Original call/reference totals",
    )
    for group in inputs["groups"].values():
        declaration(group)
    return inputs, manifest


def environment(out, target):
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("JAX_", "XLA_", "CELLS_", "PYTEST_"))
        and k not in {"PYTHONPATH", "PYTHONHOME", "CUDA_VISIBLE_DEVICES"}
    }
    env.update(
        PYTHONPATH=os.pathsep.join((str(out / "source/src"), str(out / "source"), str(HERE))),
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        CUDA_VISIBLE_DEVICES="",
        JAX_PLATFORMS="cpu",
        JAX_ENABLE_X64="true",
        MALLOC_ARENA_MAX="2",
        TMPDIR=str(target / "tmp"),
        XDG_CACHE_HOME=str(target / "cache"),
        CELLS_COMPONENT_EVIDENCE=str(target / "evidence"),
        CELLS_INIT_PHASE_RELEASED="1",
        CELLS_INIT_RUNNER_METADATA=str(target),
    )
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "BLIS_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
    ):
        env[name] = "1"
    return env


def evidence_inventory(target):
    from qualification_inventory import inventory

    tmp_roots = ["tmp/pytest"] if (target / "tmp/pytest").is_dir() else []
    return inventory(target, pytest_tmp_roots=tmp_roots, max_entries=50000)


def group_worker(group):
    target = None
    owned = False
    stage = "startup"
    try:
        plan = verify_release()
        os.sched_setaffinity(0, {plan["cpu"]})
        out = Path(plan["output"]).resolve()
        require(
            out.is_dir() and read(out / "launch.json")["plan_sha256"] == sha(HERE / "plan.json"),
            "Owned matching qualification output",
        )
        inputs = read(out / "inputs.json")
        require(
            group in plan["groups"] and inputs["groups"] == plan["groups"],
            "Exact selected group",
        )
        verify_packet(out, plan)
        target = out / ("run-" + group)
        target.mkdir(exist_ok=False)
        owned = True
        for name in ("tmp", "cache", "evidence", "process", "reader-process"):
            (target / name).mkdir()
        env = environment(out, target)
        command = [
            plan["python"],
            "-B",
            "-m",
            "pytest",
            "--noconftest",
            "-p",
            "no:cacheprovider",
            "-p",
            "init_runtime_plugin",
            "-q",
            *plan["groups"][group]["node_ids"],
            "--basetemp",
            str(target / "tmp/pytest"),
            "--junitxml",
            str(target / "tests.xml"),
        ]
        write(
            target / "execution.json",
            dict(
                command=command,
                group=group,
                cpu=plan["cpu"],
                runner_only_plugin=True,
                source_test_AST_changed=False,
                automatic_retry=False,
            ),
        )
        from resource_guard import run_bounded

        stage = "bounded_scientific_group"
        resources = run_bounded(
            command,
            directory=target / "process",
            cwd=out / "source",
            env=env,
            timeout=480,
            max_rss_bytes=2**30,
            min_available_bytes=8 * 2**30,
            process_tree_memory_metric="rss",
        )
        resource_receipt(resources, 480)
        exact_ids(target / "tests.xml", inputs["groups"][group]["node_ids"])
        stage = "bounded_complete_evidence_reader"
        reader_command = [
            plan["python"],
            "-B",
            str(HERE / "read_evidence.py"),
            "--output",
            str(out),
            "--target",
            str(target),
            "--group",
            group,
            "--plan",
            str(HERE / "plan.json"),
        ]
        reader = run_bounded(
            reader_command,
            directory=target / "reader-process",
            cwd=out,
            env=env,
            timeout=120,
            max_rss_bytes=2**30,
            min_available_bytes=8 * 2**30,
            process_tree_memory_metric="rss",
        )
        resource_receipt(reader, 120)
        verify_packet(out, plan)
        summary = read(target / "evidence-binding.json")
        require(
            summary["status"] == "passed"
            and summary["group"] == group
            and summary["exact_pytest_ids"] == inputs["groups"][group]["node_ids"],
            "Reader report association",
        )
        from runtime_inventory import inventory

        group_runtime = inventory()
        verify_runtime(
            group_runtime,
            source_root=out / "source",
            source_hashes=inputs["source_sha256"],
            runner_root=HERE,
            runner_hashes=plan["runner_sha256"],
            executable=plan["python"],
            executable_sha256=plan["python_sha256"],
            cpu=plan["cpu"],
            role="controller",
            external_roots=plan["external_runtime_roots"],
            extra_file_pins=plan["extra_runtime_file_pins"],
        )
        write(target / "group-runtime.json", group_runtime)
        write(target / "artifact-inventory.json", evidence_inventory(target))
        write(
            target / "result.json",
            dict(
                status="passed",
                group=group,
                resources=resources,
                reader_resources=reader,
                evidence=summary,
                artifacts_sha256=sha(target / "artifact-inventory.json"),
                original_driver_sha256=inputs["driver_sha256"],
                unchanged_scientific_source=True,
                automatic_retry=False,
                automatic_followup=False,
            ),
        )
    except BaseException as error:
        if owned:
            write(
                target / "failure.json",
                dict(
                    status="failed",
                    group=group,
                    stage=stage,
                    type=type(error).__name__,
                    message=str(error),
                    traceback=traceback.format_exc(),
                    raw_and_partial_outputs_untouched=True,
                    failed_check_credit=0,
                    automatic_retry=False,
                ),
            )
            try:
                write(
                    target / "failed-artifact-inventory.json",
                    evidence_inventory(target),
                )
            except BaseException as capture_error:
                write(
                    target / "failed-inventory-error.json",
                    dict(
                        type=type(capture_error).__name__,
                        message=str(capture_error),
                        traceback=traceback.format_exc(),
                        original_failure_preserved=True,
                    ),
                )
        raise


def worker():
    owned = False
    out = None
    completed, ids, summaries, receipts = [], [], [], []
    stage = "startup"
    try:
        plan = verify_release()
        require(
            memory()["available_host_bytes"] >= plan["launch_min_available_bytes"],
            "Host launch reserve",
        )
        os.sched_setaffinity(0, {plan["cpu"]})
        require(sha(plan["python"]) == plan["python_sha256"], "Pinned interpreter changed")
        inputs, manifest = verify_packet(plan["packet"], plan)
        out = Path(plan["output"])
        out.mkdir(exist_ok=False)
        owned = True
        write(
            out / "launch.json",
            dict(
                status="launched",
                utc=utc(),
                cpu=plan["cpu"],
                plan_sha256=sha(HERE / "plan.json"),
                release_sha256=sha(HERE / "release.json"),
                detached=True,
                automatic_retry=False,
            ),
        )
        stage = "complete_frozen_packet_copy"
        packet = Path(plan["packet"])
        for name, digest in manifest["files"].items():
            target = out / canonical(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(packet / name, target)
            require(sha(target) == digest, "Copied frozen file mismatch: " + name)
        shutil.copyfile(packet / "MANIFEST.json", out / "MANIFEST.json")
        verify_packet(out, plan)
        from runtime_inventory import inventory

        initial_runtime = inventory()
        verify_runtime(
            initial_runtime,
            source_root=out / "source",
            source_hashes=inputs["source_sha256"],
            runner_root=HERE,
            runner_hashes=plan["runner_sha256"],
            executable=plan["python"],
            executable_sha256=plan["python_sha256"],
            cpu=plan["cpu"],
            role="controller",
            external_roots=plan["external_runtime_roots"],
            extra_file_pins=plan["extra_runtime_file_pins"],
        )
        write(out / "controller-runtime-start.json", initial_runtime)
        write(
            out / "execution-view.json",
            dict(
                kind="cells.explicit_INIT_runner_execution_authorization@1",
                source_inputs_sha256=plan["inputs_sha256"],
                original_hold_marker_preserved=True,
                source_and_inputs_overlays=[],
                exact_test_ids=True,
                release_sha256=sha(HERE / "release.json"),
                original_driver_preserved_not_invoked=True,
                why=(
                    "Reviewed runner supplies strict complete archives and runtime binding; "
                    "scientific pytest commands unchanged except metadata-only plugin."
                ),
            ),
        )
        for group in plan["group_order"]:
            stage = group
            write(
                out / "status.json",
                dict(
                    status="running",
                    group=group,
                    completed_groups=completed,
                    completed_unique_ids=ids,
                    utc=utc(),
                ),
                mutable=True,
            )
            with (
                (out / (group + ".stdout.log")).open("x") as stdout,
                (out / (group + ".stderr.log")).open("x") as stderr,
            ):
                subprocess.run(
                    [
                        plan["python"],
                        "-B",
                        str(HERE / "controller.py"),
                        "group",
                        "--group",
                        group,
                    ],
                    cwd=HERE,
                    stdout=stdout,
                    stderr=stderr,
                    stdin=subprocess.DEVNULL,
                    check=True,
                )
            target = out / ("run-" + group)
            result = read(target / "result.json")
            require(
                result["status"] == "passed" and result["group"] == group,
                "Group terminal failure",
            )
            resource_receipt(result["resources"], 480)
            resource_receipt(result["reader_resources"], 120)
            require(
                read(target / "process/result.json") == result["resources"]
                and read(target / "reader-process/result.json") == result["reader_resources"],
                "Exact durable guard-result binding",
            )
            accepted = exact_ids(target / "tests.xml", inputs["groups"][group]["node_ids"])
            require(not set(accepted).intersection(ids), "Duplicate passing check credit")
            ids.extend(accepted)
            completed.append(group)
            summaries.append(result["evidence"])
            receipts.append(
                dict(
                    group=group,
                    files_sha256={
                        name: sha(target / name)
                        for name in (
                            "result.json",
                            "tests.xml",
                            "artifact-inventory.json",
                            "evidence-binding.json",
                            "reader-detail.json",
                            "pytest-runtime.json",
                            "reader-runtime.json",
                            "group-runtime.json",
                            "process/result.json",
                            "reader-process/result.json",
                        )
                    },
                )
            )
        stage = "terminal_exact_inventory"
        require(
            set(completed) == set(inputs["groups"])
            and len(ids) == len(set(ids)) == 62
            and sum(s["complete_calls"] for s in summaries) == 61
            and sum(s["independent_reference_forms"] for s in summaries) == 986
            and sum(s["native_captures"] for s in summaries) == 29,
            "Complete exact checks/calls/forms/native inventory",
        )
        verify_packet(out, plan)
        final_runtime = inventory()
        verify_runtime(
            final_runtime,
            source_root=out / "source",
            source_hashes=inputs["source_sha256"],
            runner_root=HERE,
            runner_hashes=plan["runner_sha256"],
            executable=plan["python"],
            executable_sha256=plan["python_sha256"],
            cpu=plan["cpu"],
            role="controller",
            external_roots=plan["external_runtime_roots"],
            extra_file_pins=plan["extra_runtime_file_pins"],
        )
        write(out / "controller-runtime-end.json", final_runtime)
        write(
            out / "finalization-detail.json",
            dict(
                exact_pytest_ids=ids,
                completed_groups=completed,
                group_summaries=summaries,
                group_receipts=receipts,
                original_manifest_sha256=plan["manifest_sha256"],
                controller_runtime_start_sha256=sha(out / "controller-runtime-start.json"),
                controller_runtime_end_sha256=sha(out / "controller-runtime-end.json"),
            ),
        )
        result = dict(
            status="numerical_phases_completed_pending_review",
            checks=62,
            newly_executed_checks=62,
            retained_checks=0,
            accepted_calls=61,
            fresh_conditional_reference_forms=986,
            native_captures=29,
            positive_declarations=22,
            dependency_controls=33,
            observer_controls=2,
            intended_raw_failures=5,
            precision_forms_not_independent_trajectories=True,
            max_budget_fraction=max(s["max_budget_fraction"] for s in summaries),
            max_self_resolution_fraction=max(s["max_self_resolution_fraction"] for s in summaries),
            detail_sha256=sha(out / "finalization-detail.json"),
            completed_groups=completed,
            source_manifest_sha256=plan["manifest_sha256"],
            source_inputs_sha256=plan["inputs_sha256"],
            native_seed_init_load_chain=False,
            physical_global_conservation=False,
            GPU=False,
            biological_cases=0,
            automatic_retry=False,
            automatic_followup=False,
            utc=utc(),
        )
        write(out / "result.json", result)
        write(out / "status.json", result, mutable=True)
    except BaseException as error:
        if owned:
            failure = dict(
                status="failed",
                stage=stage,
                type=type(error).__name__,
                message=str(error),
                traceback=traceback.format_exc(),
                completed_groups=completed,
                completed_unique_ids=ids,
                failed_and_unrun_ids_uncredited=True,
                all_raw_outputs_untouched=True,
                automatic_retry=False,
                automatic_followup=False,
                utc=utc(),
            )
            write(out / "failure.json", failure)
            if not (out / "result.json").exists():
                write(out / "result.json", failure)
            write(out / "status.json", failure, mutable=True)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("worker", "group"))
    parser.add_argument("--group")
    args = parser.parse_args()
    if args.action == "worker":
        worker()
    else:
        require(args.group is not None, "Explicit group required")
        group_worker(args.group)


if __name__ == "__main__":
    main()
