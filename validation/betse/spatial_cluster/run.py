"""Freeze and detach the bounded spatial panel using established evidence conventions."""

import argparse
import json
import os
import resource
import shutil
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

import context as x
import fixtures

u = x.u
PHASES = ("regression", "reference", "cpu", "gpu", "compare")
TESTS = [
    "validation/betse/spatial_cluster/test_runner.py",
    "validation/betse/spatial_cluster/test_spatial.py",
    "validation/betse/junction_coupled/test_coupled.py",
]


def budget(root, protocol):
    sizes = [p.stat().st_size for p in root.rglob("*") if p.is_file()]
    limits = protocol["resources"]
    u.need(max(sizes, default=0) <= limits["per_file_bytes"], "Spatial per-file allowance")
    u.need(sum(sizes) <= limits["artifact_bytes"], "Spatial total artifact allowance")
    u.need(
        shutil.disk_usage(root).free >= limits["free_disk_reserve_bytes"], "Spatial disk reserve"
    )
    return sum(sizes)


def authenticate(root, r):
    u.need(u.sources() == r["sources_sha256"], "Frozen spatial source changed")
    for name, digest in r["inputs_sha256"].items():
        u.need(u.sha(root / name) == digest, "Frozen spatial input changed")


def worker(root, phase):
    r = u.read(root / "registration.json")
    local = root / phase
    began = time.monotonic()
    u.write(local / "started.json", dict(pid=os.getpid(), utc=u.utc()))
    try:
        authenticate(root, r)
        u.need(
            u.runtime() == r["runtimes"]["gpu" if phase == "gpu" else "cpu"],
            "Spatial runtime changed",
        )
        resource.setrlimit(
            resource.RLIMIT_FSIZE, (r["protocol"]["resources"]["per_file_bytes"],) * 2
        )
        if phase == "regression":
            command = [
                sys.executable,
                "-B",
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                *r["regression_tests"],
                "--basetemp",
                str(local / "pytest"),
                "--junitxml",
                str(local / "tests.xml"),
            ]
            u.write(local / "command.json", dict(command=command, cwd=str(x.ROOT)))
            subprocess.run(command, cwd=x.ROOT, check=True, timeout=540)
            suites = ET.parse(local / "tests.xml").getroot().iter("testsuite")
            counts = dict(tests=0, failures=0, errors=0, skipped=0)
            for suite in suites:
                for key in counts:
                    counts[key] += int(suite.attrib.get(key, "0"))
            u.need(
                counts["tests"] > 0
                and not any(counts[k] for k in ("failures", "errors", "skipped")),
                "Spatial regression did not fully pass",
            )
            result = dict(status="regressions_passed", **counts)
        else:
            import check

            if phase == "reference":
                resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3,) * 2)
                result = check.reference_worker(root)
            elif phase in ("cpu", "gpu"):
                result = check.production(root, phase)
            else:
                for name in PHASES[:-1]:
                    receipt = u.read(root / name / "completion.json")
                    u.need(receipt["status"] == "completed", "Missing spatial prerequisite")
                    x.check_artifacts(root / name, receipt, pytest_links=name == "regression")
                result = check.compare(root)
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        child_peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024
        u.need(
            max(peak, child_peak) <= r["protocol"]["resources"]["max_worker_rss_bytes"],
            "Spatial host-memory cap",
        )
        u.write(local / "result.json", result)
        u.write(
            local / "completion.json",
            dict(
                status="completed",
                elapsed_seconds=time.monotonic() - began,
                peak_rss_bytes=peak,
                child_peak_rss_bytes=child_peak,
                **x.artifacts(local, pytest_links=phase == "regression"),
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
            budget(root, r["protocol"])
            env = u.env(
                Path(r["workspace"]),
                Path(r["workspace"]) / "cache" / root.name / phase,
                gpu=phase == "gpu",
            )
            env["XLA_PYTHON_CLIENT_MEM_FRACTION"] = "0.08"
            python = Path(r["workspace"]) / (
                "venv-gpu/bin/python" if phase == "gpu" else "venv-cpu/bin/python"
            )
            monitor = None
            with (
                (root / (phase + ".stdout.log")).open("x") as out,
                (root / (phase + ".stderr.log")).open("x") as err,
            ):
                try:
                    if phase == "gpu":
                        with (root / "gpu-utilization.csv").open("x") as telemetry:
                            monitor = subprocess.Popen(
                                [
                                    "nvidia-smi",
                                    "--query-gpu=timestamp,utilization.gpu,memory.used",
                                    "--format=csv,noheader,nounits",
                                    "--loop-ms=1000",
                                ],
                                stdin=subprocess.DEVNULL,
                                stdout=telemetry,
                                stderr=err,
                            )
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
                finally:
                    if monitor is not None:
                        monitor.terminate()
                        monitor.wait(timeout=10)
            u.need(not (root / (phase + ".stderr.log")).read_text(), "Unexpected spatial stderr")
        result = u.read(root / "compare/result.json")
        samples = [
            float(row.split(",")[1])
            for row in (root / "gpu-utilization.csv").read_text().splitlines()
        ]
        u.need(bool(samples), "GPU phase has no utilization telemetry")
        result.update(
            elapsed_seconds=time.monotonic() - began,
            finished_utc=u.utc(),
            registration_sha256=u.sha(root / "registration.json"),
            phase_completions_sha256={p: u.sha(root / p / "completion.json") for p in PHASES},
            regression=u.read(root / "regression/result.json"),
            artifact_bytes=budget(root, r["protocol"]),
            gpu_utilization=dict(
                scope="entire GPU phase including compilation, host checks and snapshots",
                samples=len(samples),
                mean_percent=sum(samples) / len(samples),
                max_percent=max(samples),
                csv_sha256=u.sha(root / "gpu-utilization.csv"),
            ),
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


def launch(root):
    workspace = Path("/mnt/workspaces/Cells")
    u.need(
        root.is_relative_to("/mnt/workspaces") and not root.exists(),
        "Require a new workspace output",
    )
    protocol = u.read(Path(__file__).with_name("protocol.json"))
    limits = protocol["resources"]
    u.need(
        shutil.disk_usage(workspace).free
        >= limits["artifact_bytes"] + limits["free_disk_reserve_bytes"],
        "Spatial workspace reserve",
    )
    available = next(
        int(v.split()[1]) * 1024
        for v in Path("/proc/meminfo").read_text().splitlines()
        if v.startswith("MemAvailable:")
    )
    u.need(
        available >= limits["max_worker_rss_bytes"] + 4 * 1024**3,
        "Spatial available-memory reserve",
    )
    from cells.core.runner import timeline
    from cells.core.specs import parse_spec

    definitions = {
        a: fixtures.definition(arm=a, end=protocol["duration_s"]) for a in protocol["arms"]
    }
    grids = {}
    for arm, raw in definitions.items():
        counts = []
        for dt in protocol["steps_s"]:
            data = json.loads(json.dumps(raw))
            data["execution"]["dt"] = dt
            counts.append(len(timeline(parse_spec(data))) - 1)
        grids[arm] = counts
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
            env=u.env(workspace, workspace / "cache" / root.name / "runtime", gpu=True),
            text=True,
            timeout=30,
        )
    )
    root.mkdir(parents=True)
    u.write(root / "protocol.json", protocol)
    u.write(root / "definitions.json", definitions)
    hashes = u.sources()
    for name in hashes:
        destination = root / "source" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(x.ROOT / name, destination)
    r = dict(
        protocol=protocol,
        sources_sha256=hashes,
        runtimes=runtimes,
        regression_tests=TESTS,
        inputs_sha256={p: u.sha(root / p) for p in ("protocol.json", "definitions.json")},
        workspace=str(workspace),
        created_utc=u.utc(),
        grid_steps=grids,
        available_memory_bytes=available,
        expected_seconds=1200,
        gpu_memory_fraction=0.08,
        future_deployment_max_gpus=16,
        automatic_followup=False,
    )
    u.write(root / "registration.json", r)
    budget(root, protocol)
    with (root / "stdout.log").open("x") as out, (root / "stderr.log").open("x") as err:
        process = subprocess.Popen(
            [
                sys.executable,
                "-B",
                str(root / "source/validation/betse/spatial_cluster/run.py"),
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
    receipt = dict(status="launched", pid=process.pid, output=str(root), utc=u.utc())
    u.write(root / "launch.json", receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("launch", "_controller", "_worker"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--phase", choices=PHASES)
    args = parser.parse_args()
    if args.command == "launch":
        print(json.dumps(launch(args.output.resolve()), indent=2))
    elif args.command == "_controller":
        controller(args.output)
    else:
        if args.phase is None:
            parser.error("_worker requires --phase")
        worker(args.output, args.phase)


if __name__ == "__main__":
    main()
