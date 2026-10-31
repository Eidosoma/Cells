# ruff: noqa: C408
"""Held detached orchestration for separate reviewed molecule qualification rosters."""

import argparse
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

if __package__:
    from .betse_normal_ecm_molecule_phase_execution_contract import (
        PREFIX,
        held,
        initial_outcomes,
        read,
        require,
        sha,
        verify_bundle,
        verify_packet,
        verify_release,
        write,
    )
else:
    from betse_normal_ecm_molecule_phase_execution_contract import (
        PREFIX,
        held,
        initial_outcomes,
        read,
        require,
        sha,
        verify_bundle,
        verify_packet,
        verify_release,
        write,
    )


def environment(bundle, packet, target, family):
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("JAX_", "XLA_", "CELLS_", "PYTEST_"))
        and k not in ("PYTHONPATH", "PYTHONHOME", "CUDA_VISIBLE_DEVICES")
    }
    env.update(
        PYTHONPATH=os.pathsep.join(
            (str(packet / "source/src"), str(packet / "source"), str(bundle))
        ),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONOPTIMIZE="0",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        BLIS_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
        MALLOC_ARENA_MAX="2",
        TMPDIR=str(target / "tmp"),
        XDG_CACHE_HOME=str(target / "cache"),
        PYTHONPYCACHEPREFIX=str(target / "cache/bytecode"),
        CELLS_COMPONENT_EVIDENCE=str(target / "evidence"),
        CELLS_MOLECULE_RUNNER_PROVENANCE=str(target),
    )
    env[
        "CELLS_ECM_MOLECULE_"
        + ("LIFECYCLE" if family == "lifecycle" else "RUN_LIFECYCLE")
        + "_RELEASED"
    ] = "1"
    return env


def live_pins(inputs, family):
    for path, pin in inputs["library_pins"].items():
        require(sha(path) == pin, "Pinned interpreter/library file changed: " + path)
    require(
        sha(inputs["interpreter"]["path"]) == inputs["interpreter"]["sha256"],
        "Pinned interpreter changed",
    )
    packet = inputs["packets"][family]
    frozen = verify_packet(packet)
    for name, pin in frozen["live_native_source_sha256"].items():
        for base in (Path(frozen["native_checkout"]), Path(frozen["installed_native_package"])):
            require(sha(base / name) == pin, "Live authenticated native source changed")


def start(bundle, request):
    inputs = verify_release(bundle, request)
    for family in request["families"]:
        verify_packet(inputs["packets"][family])
    target = Path(request["output"])
    require(not target.exists(), "Exclusive new round output required")
    if __package__:
        from .betse_normal_ecm_molecule_phase_execution_resources import memory_available
    else:
        from betse_normal_ecm_molecule_phase_execution_resources import memory_available
    require(memory_available() >= 8 * 2**30, "Host reserve unavailable before detached launch")
    target.mkdir(parents=True, exist_ok=False)
    write(target / "request.json", request)
    command = [
        sys.executable,
        "-B",
        str(bundle / (PREFIX + "_runner.py")),
        "worker",
        "--request",
        str(target / "request.json"),
    ]
    with (
        (target / "controller.stdout.log").open("x") as out,
        (target / "controller.stderr.log").open("x") as err,
    ):
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            start_new_session=True,
            close_fds=True,
        )
    write(
        target / "detached.json",
        dict(
            pid=process.pid,
            process_group=process.pid,
            command=command,
            requested_round=True,
            automatic_polling=False,
        ),
    )
    return dict(status="detached", output=str(target), pid=process.pid, automatic_polling=False)


def worker(bundle, request):
    verify_release(bundle, request)
    target = Path(request["output"])
    stage, family, group = ("preflight", None, None)
    completed = {}
    try:
        inputs = verify_release(bundle, request)
        write(target / "family-outcomes-initial.json", initial_outcomes(inputs))
        require(read(target / "request.json") == request, "Changed detached request")
        os.sched_setaffinity(0, {request["cpu"]})
        if __package__:
            from .betse_normal_ecm_molecule_phase_execution_resources import run_bounded
        else:
            from betse_normal_ecm_molecule_phase_execution_resources import run_bounded
        for family in request["families"]:
            packet = Path(inputs["packets"][family]["packet"])
            completed[family] = []
            for group, roster in inputs["rosters"][family].items():
                stage = "source_and_library_preflight"
                live_pins(inputs, family)
                folder = target / family / group
                folder.mkdir(parents=True, exist_ok=False)
                for name in ("tmp", "cache", "evidence", "process", "reader-process"):
                    (folder / name).mkdir()
                env = environment(bundle, packet, folder, family)
                command = [
                    sys.executable,
                    "-B",
                    "-m",
                    "pytest",
                    "--noconftest",
                    "-p",
                    "no:cacheprovider",
                    "-p",
                    PREFIX + "_plugin",
                    "-q",
                    *roster["node_ids"],
                    "--basetemp",
                    str(folder / "tmp/pytest"),
                    "--junitxml",
                    str(folder / "tests.xml"),
                ]
                write(
                    folder / "execution.json",
                    dict(
                        command=command,
                        family=family,
                        group=group,
                        cpu=request["cpu"],
                        packet_manifest_sha256=inputs["packets"][family]["manifest"]["sha256"],
                        profile=inputs["packets"][family]["capture_profile"],
                        automatic_retry=False,
                    ),
                )
                limits = inputs["resources"][family]
                stage = "bounded_requested_pytest"
                run_bounded(
                    command,
                    directory=folder / "process",
                    cwd=packet / "source",
                    env=env,
                    timeout=limits["max_scientific_command_seconds"],
                    max_rss_bytes=limits["max_process_tree_rss_bytes"],
                    min_available_bytes=limits["min_available_host_memory_bytes"],
                    process_tree_memory_metric="rss",
                )
                stage = "bounded_complete_evidence_reader"
                reader_command = [
                    sys.executable,
                    "-B",
                    str(bundle / (PREFIX + "_reader.py")),
                    "--inputs",
                    str(bundle / "inputs.json"),
                    "--family",
                    family,
                    "--group",
                    group,
                    "--target",
                    str(folder),
                    "--cpu",
                    str(request["cpu"]),
                ]
                run_bounded(
                    reader_command,
                    directory=folder / "reader-process",
                    cwd=bundle,
                    env=env,
                    timeout=limits["max_metadata_reader_seconds"],
                    max_rss_bytes=512 * 2**20,
                    min_available_bytes=8 * 2**30,
                    process_tree_memory_metric="rss",
                )
                stage = "postflight"
                live_pins(inputs, family)
                result = read(folder / "reader-result.json")
                require(result["status"] == "passed", "No completion credit from incomplete reader")
                require(
                    result["reader_identity"]["pid"]
                    == read(folder / "reader-process/process-started.json")["pid"]
                    and result["reader_identity"]["cpu_affinity"] == [request["cpu"]],
                    "Actual bounded evidence-reader child required",
                )
                write(
                    folder / "completion.json",
                    dict(
                        status="passed",
                        node_ids=roster["node_ids"],
                        reader_sha256=sha(folder / "reader-result.json"),
                        execution_sha256=sha(folder / "execution.json"),
                        original_budgets_preserved=True,
                        automatic_followup=False,
                    ),
                )
                completed[family].append(group)
            require(
                set(completed[family]) == set(inputs["rosters"][family]),
                "Complete separate family roster required",
            )
            write(
                target / family / "family-completion.json",
                dict(
                    status="passed",
                    family=family,
                    completed_groups=completed[family],
                    no_inherited_passes=True,
                    packet_manifest_sha256=inputs["packets"][family]["manifest"]["sha256"],
                ),
            )
        write(
            target / "completion.json",
            dict(
                status="passed",
                completed=completed,
                packet_manifests={f: inputs["packets"][f]["manifest"]["sha256"] for f in completed},
                actual_complete_evidence_required=True,
                no_inherited_passes=True,
                automatic_followup=False,
            ),
        )
    except BaseException as error:
        if family is not None and (target / family).is_dir():
            write(
                target / family / "family-failure.json",
                dict(
                    status="failed",
                    family=family,
                    group=group,
                    stage=stage,
                    completed_groups=completed.get(family, []),
                    no_inherited_passes=True,
                    preserve_all_raw_evidence=True,
                    automatic_retry=False,
                ),
            )
        write(
            target / "failure.json",
            dict(
                status="failed",
                stage=stage,
                family=family,
                group=group,
                completed=completed,
                type=type(error).__name__,
                message=str(error),
                traceback=traceback.format_exc(),
                preserve_all_raw_evidence=True,
                automatic_retry=False,
                automatic_followup=False,
            ),
        )
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("plan", "start", "worker"))
    parser.add_argument("--families", nargs="+", choices=("lifecycle", "run_lifecycle"))
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--round-id")
    parser.add_argument("--requested-round", action="store_true")
    parser.add_argument("--release", type=Path)
    parser.add_argument("--release-sha256")
    parser.add_argument("--request", type=Path)
    args = parser.parse_args()
    bundle = Path(__file__).resolve().parent
    if args.action == "plan":
        inputs = verify_bundle(bundle)
        print(
            json.dumps(
                dict(
                    status="held_unrun",
                    planned=inputs["planned"],
                    execution_hold=True,
                    release_authorized=False,
                    automatic_launch=False,
                    prerequisites=inputs["prerequisites"],
                    families=initial_outcomes(inputs),
                ),
                sort_keys=True,
            )
        )
        return
    held()
    if args.action == "worker":
        require(args.request is not None, "Held: explicit detached request required")
        worker(bundle, read(args.request))
        return
    request = dict(
        families=args.families,
        cpu=args.cpu,
        output=str(args.output.resolve()) if args.output else None,
        round_id=args.round_id,
        requested_round=args.requested_round,
        release_path=str(args.release.resolve()) if args.release else None,
        release_sha256=args.release_sha256,
    )
    print(json.dumps(start(bundle, request), sort_keys=True))


if __name__ == "__main__":
    main()
