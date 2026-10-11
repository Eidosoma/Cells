"""Detached fresh-machine BETSE reproduction with a separately reported GPU probe.

No historical receipt is fabricated or reauthorized. The new job freezes sources,
regenerates geometry and all numerical inputs, and uses the established independent
saved-data checks. Use ``status`` only when a status check is requested.
"""

import argparse
import concurrent.futures
import json
import os
import resource
import shutil
import subprocess
import time
import traceback
from pathlib import Path

import common as u

WALL_SECONDS = 8 * 3600
PHASE_LIMITS = dict(
    prepare=300, reference=300, cpu=1800, gpu=900, native=1800, review=3600, conclude=1800
)


def register(output, workspace):
    u.need(
        output.is_relative_to(workspace) and not output.exists(),
        "Fresh output below the workspace required",
    )
    u.need(workspace.is_relative_to(Path("/mnt/workspaces")), "Outputs must be on /mnt/workspaces")
    runtimes = {}
    for name in ("cpu", "gpu", "betse"):
        u.need((workspace / f"venv-{name}/bin/python").is_file(), "Missing environment: " + name)
        command = [
            str(workspace / f"venv-{name}/bin/python"),
            "-B",
            "-c",
            "import sys,json; sys.path.insert(0,sys.argv[1]); import common; "
            "print(json.dumps(common.runtime()))",
            str(u.HERE),
        ]
        runtimes[name] = json.loads(subprocess.check_output(command, text=True))
    output.mkdir(parents=True)
    u.budget(output)
    hashes = u.sources()
    for name in hashes:
        destination = output / "source" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(u.ROOT / name, destination)
    registration = dict(
        schema="cells.fresh_machine_betse_campaign@1",
        registered_utc=u.utc(),
        original_root=str(u.ROOT),
        workspace=str(workspace),
        runtimes=runtimes,
        sources_sha256=hashes,
        protocol=u.plan(),
        native_step_ranges_s=u.RANGES,
        bounds=dict(
            total_timeout_seconds=WALL_SECONDS,
            phase_timeout_seconds=PHASE_LIMITS,
            cpu_affinity=[0, 1, 2, 3],
            native_workers=4,
            reviewer_workers=1,
            artifact_bytes=8 * 1024**3,
            per_file_bytes=512 * 1024**2,
            free_disk_reserve_bytes=4 * 1024**3,
        ),
        scope=dict(
            native_baseline_runs=12,
            native_10ms_observed_rows=18,
            native_finest_quiet_rows=6,
            native_1ms_prefix_rows=6,
            reference_solves=18,
            cpu_trajectories=24,
            cpu_saved_restarts=6,
            gpu_kernel_trajectories=18,
            native_decimal_digits=70,
            cells_independent_common_observations=984,
        ),
        historical_artifacts_recovered=False,
        prior_qualification_inherited=False,
        gpu_failure_policy="Preserve a GPU failure and continue the authorized CPU comparison",
        production_changed=False,
        scientific_tolerances_changed=False,
        automatic_polling=False,
        automatic_retry=False,
        automatic_followup=False,
    )
    u.write(output / "registration.json", registration)
    return registration


def status(output):
    for name in ("completion.json", "failure.json", "status.json", "launch.json"):
        if (output / name).exists():
            return u.read(output / name)
    raise ValueError("No job receipt")


def progress(output, **values):
    temporary = output / f"status-{os.getpid()}.tmp"
    u.write(temporary, dict(updated_utc=u.utc(), **values))
    os.replace(temporary, output / "status.json")


def run_stage(
    campaign, phase, output, *, name=None, index=None, mode=None, duration=None, core=None
):
    r = u.read(campaign / "registration.json")
    workspace = Path(r["workspace"])
    u.budget(campaign)
    output.mkdir(parents=True, exist_ok=False)
    registration = dict(
        phase=phase,
        case=name,
        index=index,
        mode=mode,
        duration_s=duration,
        sources_sha256=r["sources_sha256"],
        campaign_registration_sha256=u.sha(campaign / "registration.json"),
        protocol=r["protocol"],
        registered_utc=u.utc(),
    )
    u.write(output / "registration.json", registration)
    interpreter = "betse" if phase in ("prepare", "native") else "gpu" if phase == "gpu" else "cpu"
    affinity = str(core) if core is not None else "0-3"
    command = [
        "taskset",
        "-c",
        affinity,
        str(workspace / f"venv-{interpreter}/bin/python"),
        "-B",
        str(Path(__file__).resolve()),
        "worker",
        str(campaign),
        "--stage",
        str(output),
    ]
    start = time.monotonic()
    cache = workspace / "cache" / campaign.name / str(output.relative_to(campaign))
    timeout = PHASE_LIMITS[phase]
    if (campaign / "controller_started.json").exists():
        elapsed = time.monotonic() - u.read(campaign / "controller_started.json")["monotonic"]
        timeout = min(timeout, WALL_SECONDS - elapsed)
    try:
        u.need(timeout > 0, "Campaign time limit")
        with (output / "stdout.log").open("x") as out, (output / "stderr.log").open("x") as err:
            subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                cwd=output,
                env=u.env(workspace, cache, gpu=phase == "gpu"),
                timeout=timeout,
                check=True,
            )
        u.need((output / "completion.json").is_file(), "Worker exited without completion")
        warnings = (output / "stderr.log").read_text().splitlines()
        expected = "[run.py] Ignoring cutting event, as cut profiles are disabled."
        u.need(
            all(line == expected for line in warnings)
            if phase in ("prepare", "native")
            else not warnings,
            "Unexpected worker stderr; retained in stderr.log",
        )
    except BaseException:
        u.write(
            output / "controller_failure.json",
            dict(phase=phase, utc=u.utc(), traceback=traceback.format_exc(), automatic_retry=False),
        )
        raise
    u.budget(campaign)
    return dict(
        stage=str(output.relative_to(campaign)),
        elapsed_seconds=time.monotonic() - start,
        completion_sha256=u.sha(output / "completion.json"),
    )


def worker(campaign, output):
    r = u.read(output / "registration.json")
    campaign_registration = u.read(campaign / "registration.json")
    u.need(
        r["campaign_registration_sha256"] == u.sha(campaign / "registration.json"),
        "Campaign changed",
    )
    u.need(u.sources() == r["sources_sha256"], "Frozen source mismatch")
    phase, plan = r["phase"], r["protocol"]
    interpreter = "betse" if phase in ("prepare", "native") else "gpu" if phase == "gpu" else "cpu"
    u.need(
        u.runtime() == campaign_registration["runtimes"][interpreter], "Worker environment changed"
    )
    workspace = Path(campaign_registration["workspace"])
    resource.setrlimit(resource.RLIMIT_FSIZE, (512 * 1024**2,) * 2)
    if phase != "gpu":
        resource.setrlimit(resource.RLIMIT_AS, (16 * 1024**3,) * 2)
    start = time.monotonic()
    u.write(output / "started.json", dict(pid=os.getpid(), phase=phase, utc=u.utc()))
    try:
        if phase == "prepare":
            import prepare

            result = prepare.seed(output, workspace)
        else:
            u.authenticate_stage(campaign / "prepare")
            preparation = u.read(campaign / "prepare/preparation.json")
            if phase == "native":
                import prepare

                result = prepare.capture(
                    output / "capture",
                    workspace,
                    preparation,
                    r["case"],
                    r["index"],
                    r["mode"],
                    r["duration_s"],
                )
            elif phase == "review":
                import fresh_review

                result = fresh_review.native(
                    output, campaign, preparation, plan, r["case"], r["index"]
                )
            elif phase == "conclude":
                import fresh_review

                result = fresh_review.conclude(output, campaign, preparation, plan)
            else:
                import workers

                if phase == "reference":
                    result = workers.reference(output, preparation, plan)
                elif phase == "cpu":
                    result = workers.cells(output, preparation, plan)
                elif phase == "gpu":
                    u.authenticate_stage(campaign / "cpu")
                    result = workers.gpu(output, preparation, plan, campaign / "cpu")
                else:
                    raise ValueError("Unknown phase")
        u.need(u.sources() == r["sources_sha256"], "Sources changed during work")
        u.need(
            u.runtime() == campaign_registration["runtimes"][interpreter],
            "Runtime changed during work",
        )
        files = {
            k: v for k, v in u.inventory(output).items() if k not in ("stdout.log", "stderr.log")
        }
        u.write(
            output / "completion.json",
            dict(
                status="stage_completed",
                phase=phase,
                elapsed_seconds=time.monotonic() - start,
                finished_utc=u.utc(),
                result=result,
                peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                files_sha256=files,
                registration_sha256=u.sha(output / "registration.json"),
            ),
        )
    except BaseException:
        u.write(
            output / "failure.json",
            dict(
                status="stage_failed",
                phase=phase,
                elapsed_seconds=time.monotonic() - start,
                utc=u.utc(),
                traceback=traceback.format_exc(),
            ),
        )
        raise


def execute(campaign):
    start = time.monotonic()
    u.write(
        campaign / "controller_started.json", dict(monotonic=start, utc=u.utc(), pid=os.getpid())
    )
    results = []
    try:
        for phase in ("prepare", "reference", "cpu", "gpu"):
            progress(campaign, phase=phase, completed_stages=results)
            try:
                result = run_stage(campaign, phase, campaign / phase)
            except Exception:
                if phase != "gpu":
                    raise
                result = dict(
                    stage="gpu",
                    status="failed_probe_preserved_cpu_continues",
                    traceback=traceback.format_exc(),
                )
            results.append(result)
        progress(campaign, phase="native", completed_stages=results)
        tasks = [(name, str(i), i, "observed", 0.01) for name in u.VARIANTS for i in range(3)]
        tasks += [(name, "quiet", 2, "unobserved", 0.01) for name in u.VARIANTS]
        tasks += [(name, "prefix", 2, "observed", 0.001) for name in u.VARIANTS]

        def capture(item):
            number, (name, label, index, mode, duration) = item
            return run_stage(
                campaign,
                "native",
                campaign / "native" / name / label,
                name=name,
                index=index,
                mode=mode,
                duration=duration,
                core=number % 4,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            for result in pool.map(capture, enumerate(tasks)):
                results.append(result)
                progress(campaign, phase="native", completed_stages=results)
        for name in u.VARIANTS:
            for index in range(3):
                u.need(
                    time.monotonic() - start < WALL_SECONDS - PHASE_LIMITS["review"],
                    "Campaign time reserve",
                )
                progress(campaign, phase="review", case=name, index=index, completed_stages=results)
                results.append(
                    run_stage(
                        campaign,
                        "review",
                        campaign / "review" / name / str(index),
                        name=name,
                        index=index,
                    )
                )
        progress(campaign, phase="conclude", completed_stages=results)
        results.append(run_stage(campaign, "conclude", campaign / "conclusion"))
        result = u.read(campaign / "conclusion/comparison.json")
        u.write(
            campaign / "completion.json",
            dict(
                status=result["status"],
                finished_utc=u.utc(),
                elapsed_seconds=time.monotonic() - start,
                stages=results,
                comparison_sha256=u.sha(campaign / "conclusion/comparison.json"),
                registration_sha256=u.sha(campaign / "registration.json"),
                artifact_bytes=u.budget(campaign),
                automatic_followup=False,
                gpu_probe_passed=(campaign / "gpu/completion.json").is_file()
                and not (campaign / "gpu/controller_failure.json").exists(),
            ),
        )
    except BaseException:
        u.write(
            campaign / "failure.json",
            dict(
                status="fresh_campaign_failed_not_qualified",
                finished_utc=u.utc(),
                elapsed_seconds=time.monotonic() - start,
                completed_stages=results,
                traceback=traceback.format_exc(),
                automatic_retry=False,
            ),
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("launch", "register", "execute", "worker", "status", "prepare")
    )
    parser.add_argument("output", type=Path)
    parser.add_argument("--workspace", type=Path, default=Path("/mnt/workspaces/Cells"))
    parser.add_argument("--stage", type=Path)
    args = parser.parse_args()
    output, workspace = args.output.resolve(), args.workspace.resolve()
    if args.action in ("launch", "register", "prepare"):
        register(output, workspace)
        script = output / "source/validation/betse/fresh_rerun/run.py"
        if args.action == "launch":
            with (
                (output / "controller.stdout.log").open("x") as out,
                (output / "controller.stderr.log").open("x") as err,
            ):
                child = subprocess.Popen(
                    [
                        str(workspace / "venv-cpu/bin/python"),
                        "-B",
                        str(script),
                        "execute",
                        str(output),
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=err,
                    start_new_session=True,
                    close_fds=True,
                    cwd=output,
                    env=u.env(workspace, workspace / "cache" / output.name / "controller"),
                )
            receipt = dict(
                pid=child.pid,
                launched_utc=u.utc(),
                registration_sha256=u.sha(output / "registration.json"),
                status_command=f"python3 {script} status {output}",
            )
            u.write(output / "launch.json", receipt)
            print(receipt)
        elif args.action == "prepare":
            # A short real fixture check. No full campaign or follow-up is started.
            # Run through the frozen controller function, using the same worker path.
            subprocess.run(
                [
                    str(workspace / "venv-cpu/bin/python"),
                    "-B",
                    "-c",
                    "import sys; sys.path.insert(0, sys.argv[1]); "
                    "import run; from pathlib import Path; "
                    "print(run.run_stage(Path(sys.argv[2]), 'prepare', "
                    "Path(sys.argv[2])/'prepare'))",
                    str(script.parent),
                    str(output),
                ],
                env=u.env(workspace, workspace / "cache" / output.name / "controller"),
                check=True,
            )
    elif args.action == "execute":
        execute(output)
    elif args.action == "worker":
        u.need(args.stage is not None, "Worker stage required")
        worker(output, args.stage.resolve())
    else:
        print(status(output))


if __name__ == "__main__":
    main()
