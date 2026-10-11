"""Freeze, register and detach one bounded reference/CPU/L4 intervention panel."""

import argparse
import json
import os
import resource
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

import experiment as x

u = x.u
PHASES = ("reference", "cpu", "gpu", "compare")


def budget(root, protocol):
    sizes = [p.stat().st_size for p in root.rglob("*") if p.is_file()]
    limits = protocol["resources"]
    u.need(max(sizes, default=0) <= limits["per_file_bytes"], "Recovery per-file allowance")
    u.need(sum(sizes) <= limits["artifact_bytes"], "Recovery total artifact allowance")
    u.need(
        shutil.disk_usage(root).free >= limits["free_disk_reserve_bytes"], "Recovery disk reserve"
    )
    return sum(sizes)


def authenticate(root, r):
    u.need(u.sources() == r["sources_sha256"], "Frozen recovery source changed")
    for name, digest in r["inputs_sha256"].items():
        u.need(u.sha(root / name) == digest, "Frozen recovery input changed")
    prior = Path(r["preparation_parent"])
    u.need(
        u.sha(prior / "completion.json") == r["parent_completion_sha256"], "Recovery parent changed"
    )


def worker(root, phase):
    r = u.read(root / "registration.json")
    local = root / phase
    began = time.monotonic()
    u.write(local / "started.json", dict(pid=os.getpid(), utc=u.utc()))
    try:
        authenticate(root, r)
        u.need(
            u.runtime() == r["runtimes"]["gpu" if phase == "gpu" else "cpu"],
            "Recovery runtime changed",
        )
        resource.setrlimit(
            resource.RLIMIT_FSIZE, (r["protocol"]["resources"]["per_file_bytes"],) * 2
        )
        if phase == "reference":
            resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3,) * 2)
            from reference import worker as reference

            result = reference(root)
        else:
            import check

            if phase == "compare":
                for name in PHASES[:-1]:
                    completed = u.read(root / name / "completion.json")
                    u.need(completed["status"] == "completed", "Missing recovery prerequisite")
                    for path, digest in completed["files_sha256"].items():
                        u.need(
                            u.sha(root / name / path) == digest, "Recovery phase artifact changed"
                        )
                result = check.compare(root)
            else:
                result = check.production(root, phase)
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        u.need(
            peak <= r["protocol"]["resources"]["max_worker_rss_bytes"], "Recovery host-memory cap"
        )
        u.write(local / "result.json", result)
        u.write(
            local / "completion.json",
            dict(
                status="completed",
                elapsed_seconds=time.monotonic() - began,
                peak_rss_bytes=peak,
                files_sha256=u.inventory(local),
            ),
        )
    except BaseException as exc:
        u.write(
            local / "failure.json",
            dict(error=str(exc), traceback=traceback.format_exc(), utc=u.utc()),
        )
        raise


def controller(root):
    r = u.read(root / "registration.json")
    began = time.monotonic()
    u.write(root / "started.json", dict(pid=os.getpid(), utc=u.utc()))
    try:
        authenticate(root, r)
        for phase in PHASES:
            env = u.env(
                Path(r["workspace"]),
                Path(r["workspace"]) / "cache" / root.name / phase,
                gpu=phase == "gpu",
            )
            env["XLA_PYTHON_CLIENT_MEM_FRACTION"] = "0.08"
            python = Path(r["workspace"]) / (
                "venv-gpu/bin/python" if phase == "gpu" else "venv-cpu/bin/python"
            )
            with (
                (root / (phase + ".stdout.log")).open("x") as out,
                (root / (phase + ".stderr.log")).open("x") as err,
            ):
                subprocess.run(
                    [
                        "taskset",
                        "-c",
                        ",".join(map(str, r["protocol"]["resources"]["cpu_affinity"])),
                        str(python),
                        "-B",
                        str(Path(__file__).resolve()),
                        "_worker",
                        str(root),
                        "--phase",
                        phase,
                    ],
                    stdout=out,
                    stderr=err,
                    stdin=subprocess.DEVNULL,
                    env=env,
                    timeout=r["protocol"]["resources"]["phase_seconds"][phase],
                    check=True,
                )
            u.need(not (root / (phase + ".stderr.log")).read_text(), "Unexpected recovery stderr")
            budget(root, r["protocol"])
        result = u.read(root / "compare/result.json")
        result.update(
            elapsed_seconds=time.monotonic() - began,
            finished_utc=u.utc(),
            registration_sha256=u.sha(root / "registration.json"),
            phase_completions_sha256={p: u.sha(root / p / "completion.json") for p in PHASES},
            artifact_bytes=budget(root, r["protocol"]),
            automatic_followup=False,
        )
        u.write(root / "result.json", result)
        u.write(
            root / "completion.json",
            dict(
                status=result["status"],
                result_sha256=u.sha(root / "result.json"),
                registration_sha256=u.sha(root / "registration.json"),
                utc=u.utc(),
            ),
        )
    except BaseException as exc:
        u.write(
            root / "failure.json",
            dict(
                status="failed",
                error=str(exc),
                traceback=traceback.format_exc(),
                elapsed_seconds=time.monotonic() - began,
                utc=u.utc(),
                automatic_retry=False,
            ),
        )
        raise


def launch(root, parent):
    workspace = Path("/mnt/workspaces/Cells")
    u.need(
        root.is_relative_to("/mnt/workspaces") and not root.exists(),
        "Require a new workspace output",
    )
    done = u.read(parent / "completion.json")
    u.need(
        done["status"] == "fresh_10ms_numerical_review_pass", "Require qualified 10-ms preparation"
    )
    u.need(
        done["registration_sha256"] == u.sha(parent / "registration.json")
        and done["comparison_sha256"] == u.sha(parent / "conclusion/comparison.json"),
        "Recovery parent receipt mismatch",
    )
    u.authenticate_stage(parent / "prepare")
    protocol = u.read(Path(__file__).with_name("protocol.json"))
    preparation = u.read(parent / "prepare/preparation.json")
    grid_check = x.preflight(preparation, protocol)
    u.need(
        shutil.disk_usage(workspace).free
        >= protocol["resources"]["artifact_bytes"]
        + protocol["resources"]["free_disk_reserve_bytes"],
        "Recovery workspace reserve",
    )
    available = next(
        int(v.split()[1]) * 1024
        for v in Path("/proc/meminfo").read_text().splitlines()
        if v.startswith("MemAvailable:")
    )
    u.need(
        available >= protocol["resources"]["max_worker_rss_bytes"] + 4 * 1024**3,
        "Recovery available-memory reserve",
    )
    runtimes = {"cpu": u.runtime()}
    runtimes["gpu"] = json.loads(
        subprocess.check_output(
            [
                str(workspace / "venv-gpu/bin/python"),
                "-B",
                "-c",
                "import sys,json;sys.path.insert(0,sys.argv[1]);"
                "import common;print(json.dumps(common.runtime()))",
                str(u.HERE),
            ],
            text=True,
            timeout=30,
        )
    )
    root.mkdir(parents=True)
    for name in ("protocol.json", "preparation.json"):
        u.write(root / name, protocol if name == "protocol.json" else preparation)
    hashes = u.sources()
    for name in hashes:
        destination = root / "source" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(x.ROOT / name, destination)
    r = dict(
        protocol=protocol,
        grid_preflight=grid_check,
        sources_sha256=hashes,
        runtimes=runtimes,
        inputs_sha256={p: u.sha(root / p) for p in ("protocol.json", "preparation.json")},
        workspace=str(workspace),
        preparation_parent=str(parent),
        parent_completion_sha256=u.sha(parent / "completion.json"),
        created_utc=u.utc(),
        host_memory_allowance_bytes=protocol["resources"]["max_worker_rss_bytes"],
        gpu_memory_fraction=0.08,
        future_deployment_max_gpus=16,
        automatic_followup=False,
    )
    u.write(root / "registration.json", r)
    with (root / "stdout.log").open("x") as out, (root / "stderr.log").open("x") as err:
        process = subprocess.Popen(
            [
                sys.executable,
                "-B",
                str(root / "source/validation/betse/pump_recovery/run.py"),
                "_controller",
                str(root),
            ],
            stdout=out,
            stderr=err,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
            env=u.env(workspace, workspace / "cache" / root.name / "controller"),
        )
    result = dict(status="launched", pid=process.pid, output=str(root), utc=u.utc())
    u.write(root / "launch.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("launch", "_controller", "_worker"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--parent", type=Path)
    parser.add_argument("--phase", choices=PHASES)
    args = parser.parse_args()
    if args.command == "launch":
        if args.parent is None:
            parser.error("launch requires --parent")
        print(json.dumps(launch(args.output.resolve(), args.parent.resolve()), indent=2))
    elif args.command == "_controller":
        controller(args.output)
    else:
        if args.phase is None:
            parser.error("_worker requires --phase")
        worker(args.output, args.phase)


if __name__ == "__main__":
    main()
