"""Register and detach the bounded native junction mapping/transport comparison."""

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "validation/betse/fresh_rerun"))
import common as u  # noqa: E402

DETAILED_PANELS = ("trajectory", "gate", "coupled", "native_coupled")
GPU_PANELS = ("gate", "coupled", "native_coupled")


def protocol():
    return {
        "version": "betse_held_open_junction_entrypoints@1",
        "species": ["Na", "K", "Cl"],
        "fixtures": ["equal", "chemical", "electrical", "mixed", "equilibrium"],
        "topologies": ["all", "single", "disconnected"],
        "blocks": [0.0, 0.5, 1.0],
        "gj_surface_fraction": 1e-6,
        "dt_s": 1e-4,
        "tolerances": {
            "partner_area_rtol": 5e-14,
            "flux_rtol": 2e-12,
            "flux_atol_fmol_s": 1e-13,
            "concentration_atol_mM": 5e-12,
            "material_atol_fmol": 5e-13,
        },
        "purpose": (
            "Resolve face orientation, area ownership and one-update conservative "
            "transport before dynamic gates"
        ),
    }


def worker(output):
    began = time.monotonic()
    try:
        registration = u.read(output / "registration.json")
        u.need(registration["sources_sha256"] == u.sources(), "Frozen junction source mismatch")
        u.need(registration["runtime"] == u.runtime(), "Junction checker runtime mismatch")
        workspace = Path(registration["workspace"])
        kind = registration.get("panel_kind", "held_open")
        directories = {
            "held_open": "junction_transport",
            "dynamic": "junction_dynamics",
            "trajectory": "junction_trajectory",
            "gate": "junction_gate",
            "coupled": "junction_coupled",
            "native_coupled": "junction_native_coupled",
        }
        u.need(kind in directories, "Unknown junction panel kind")
        directory = Path(__file__).parents[1] / directories[kind]
        if kind in DETAILED_PANELS:
            os.sched_setaffinity(0, registration["protocol"]["resources"]["cpu_affinity"])
        u.need(
            u.read(output / "protocol.json") == registration["protocol"],
            "Junction protocol changed",
        )
        u.write(output / "started.json", {"pid": os.getpid(), "utc": u.utc()})
        native_script = directory / "native.py"
        native_extra = []
        if kind == "trajectory" and "resume" in registration:
            native_script = directory / "resume.py"
            native_extra = ["--registration", str(output / "registration.json")]
        if kind == "coupled":
            print("Starting coupled physical-time CPU/GPU comparison", flush=True)
        elif kind in ("trajectory", "native_coupled") and registration.get(
            "comparison_only", False
        ):
            resume = u.private(
                "trajectory_comparison_staging",
                Path(__file__).parents[1] / "junction_trajectory/resume.py",
            )
            resume.stage_complete(output / "native", registration)
            print("Copied complete native panel; starting comparison", flush=True)
        else:
            with (
                (output / "native.stdout.log").open("x") as out,
                (output / "native.stderr.log").open("x") as err,
            ):
                subprocess.run(
                    [
                        str(workspace / "venv-betse/bin/python"),
                        "-B",
                        str(native_script),
                        "--output",
                        str(output / "native"),
                        "--workspace",
                        str(workspace),
                        "--protocol",
                        str(output / "protocol.json"),
                        *native_extra,
                    ],
                    stdout=out,
                    stderr=err,
                    env=u.env(workspace, output / "cache"),
                    timeout=registration["max_wall_seconds"],
                    check=True,
                )
        if kind in DETAILED_PANELS:
            if kind != "coupled":
                done = u.read(output / "native/completion.json")
                u.need(
                    done["panel_sha256"] == u.sha(output / "native/panel.json"),
                    "Native trajectory panel changed",
                )
            with (
                (output / "comparison.stdout.log").open("x") as out,
                (output / "comparison.stderr.log").open("x") as err,
            ):
                subprocess.run(
                    [
                        str(workspace / "venv-gpu/bin/python")
                        if kind in GPU_PANELS
                        else sys.executable,
                        "-B",
                        str(directory / "check.py"),
                        str(output),
                    ],
                    stdout=out,
                    stderr=err,
                    env=u.env(workspace, output / "cache", gpu=kind in GPU_PANELS),
                    timeout=registration["protocol"]["resources"]["comparison_timeout_seconds"],
                    check=True,
                )
            result = u.read(output / "comparison-result.json")
            if "resume" in registration:
                result["reused_native_runs"] = len(registration["resume"]["rows"])
                result["new_native_runs"] = len(registration["resume"]["missing_rows"])
                result["resume_parent"] = registration["resume"]["parent"]
                result["comparison_only"] = registration.get("comparison_only", False)
        elif kind == "dynamic":
            checker = u.private("junction_checker", directory / "check.py")
            panel = u.read(output / "native/panel.json")
            u.need(panel["protocol"] == registration["protocol"], "Native dynamic protocol changed")
            result = checker.check(panel)
        else:
            checker = u.private("junction_checker", directory / "check.py")
            result = checker.check(output / "native")
            u.need(len(result["rows"]) == 135, "Incomplete registered junction panel")
            p = registration["protocol"]
            expected = {
                (ion, fixture, topology, block)
                for ion in p["species"]
                for fixture in p["fixtures"]
                for topology in p["topologies"]
                for block in p["blocks"]
            }
            actual = {
                tuple(row[k] for k in ("species", "fixture", "topology", "block"))
                for row in result["rows"]
            }
            u.need(actual == expected, "Junction panel controls changed or duplicated")
            result["native_preparation_sha256"] = u.sha(output / "native/preparation.json")
        result.update(
            elapsed_seconds=time.monotonic() - began,
            finished_utc=u.utc(),
        )
        if kind != "coupled":
            result["native_panel_sha256"] = u.sha(output / "native/panel.json")
        u.need(registration["sources_sha256"] == u.sources(), "Junction source changed during run")
        if kind in DETAILED_PANELS:
            limits = registration["protocol"]["resources"]
            sizes = [p.stat().st_size for p in output.rglob("*") if p.is_file()]
            u.need(
                max(sizes, default=0) <= limits["per_file_bytes"]
                and sum(sizes) <= limits["artifact_bytes"],
                "Junction trajectory artifact cap",
            )
            u.need(
                shutil.disk_usage(output).free >= limits["free_disk_reserve_bytes"],
                "Junction trajectory free-disk reserve",
            )
            result["artifact_bytes"] = sum(sizes)
        u.write(output / "result.json", result)
        u.write(
            output / "completion.json",
            {
                "status": result["status"],
                "utc": u.utc(),
                "result_sha256": u.sha(output / "result.json"),
                "registration_sha256": u.sha(output / "registration.json"),
            },
        )
    except BaseException as exc:
        u.write(
            output / "failure.json",
            {
                "status": "failed",
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "utc": u.utc(),
                "elapsed_seconds": time.monotonic() - began,
            },
        )
        raise


def main(*, kind="held_open"):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("launch", "_worker"))
    parser.add_argument("output", type=Path)
    reuse = parser.add_mutually_exclusive_group()
    reuse.add_argument("--resume-from", type=Path)
    reuse.add_argument(
        "--compare-from",
        type=Path,
        help="Reuse a completed native panel and rerun only its comparison",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if args.command == "_worker":
        worker(output)
        return
    u.need(args.resume_from is None or kind == "trajectory", "Resume is trajectory-only")
    u.need(
        args.compare_from is None or kind in ("trajectory", "native_coupled"),
        "Comparison reuse requires a trajectory or native_coupled panel",
    )
    u.need(
        output.is_relative_to("/mnt/workspaces") and not output.exists(),
        "Need fresh /mnt/workspaces output",
    )
    u.need(shutil.disk_usage(output.parent).free > 5 * 1024**3, "Junction disk reserve")
    workspace = Path("/mnt/workspaces/Cells")
    protocols = {
        "dynamic": "junction_dynamics",
        "trajectory": "junction_trajectory",
        "gate": "junction_gate",
        "coupled": "junction_coupled",
        "native_coupled": "junction_native_coupled",
    }
    plan = (
        protocol()
        if kind == "held_open"
        else u.read(ROOT / "validation/betse" / protocols[kind] / "protocol.json")
    )
    if kind in DETAILED_PANELS:
        u.need(
            importlib.util.find_spec("scipy") is not None, "Trajectory comparison requires SciPy"
        )
    prerequisites = {}
    if kind in DETAILED_PANELS:
        required = (
            (
                "held_open_transport",
                "betse-junction-panel-20260920-01",
                "held_open_junction_mapping_and_single_update_pass",
            ),
            (
                "dynamic_lifecycle",
                "betse-dynamic-panel-20260920-01",
                "native_dynamic_junction_law_and_lifecycle_pass",
            ),
        )
        if kind in GPU_PANELS:
            required += (
                (
                    "held_open_trajectories",
                    "betse-junction-trajectory-20260920-03",
                    "held_open_free_voltage_junction_trajectories_pass",
                ),
            )
        if kind in ("coupled", "native_coupled"):
            required += (
                (
                    "gate_process_cpu_gpu",
                    "betse-junction-gate-20260920-02",
                    "junction_gate_process_cpu_gpu_pass",
                ),
            )
        if kind == "native_coupled":
            required += (
                (
                    "physical_time_coupled_cpu_gpu",
                    "betse-junction-coupled-20260920-01",
                    "physical_time_junction_coupled_cpu_gpu_pass",
                ),
            )
        for name, folder, status in required:
            prior = workspace / folder
            done = u.read(prior / "completion.json")
            u.need(
                done["status"] == status and not (prior / "failure.json").exists(),
                "Incomplete junction prerequisite: " + name,
            )
            u.need(
                done["result_sha256"] == u.sha(prior / "result.json")
                and done["registration_sha256"] == u.sha(prior / "registration.json"),
                "Changed junction prerequisite: " + name,
            )
            prerequisites[name] = {
                "path": str(prior),
                "completion_sha256": u.sha(prior / "completion.json"),
            }
    registration = {
        "sources_sha256": u.sources(),
        "runtime": u.runtime(),
        "workspace": str(workspace),
        "created_utc": u.utc(),
        "max_wall_seconds": plan["resources"].get("native_timeout_seconds", 0)
        if kind in DETAILED_PANELS
        else 300,
        "protocol": plan,
        "panel_kind": kind,
        "long_native_trajectory": False,
    }
    if kind in DETAILED_PANELS:
        registration["prerequisites"] = prerequisites
    if args.resume_from is not None or args.compare_from is not None:
        resume = u.private(
            "trajectory_resume_registration",
            ROOT / "validation/betse/junction_trajectory/resume.py",
        )
        registration["resume"] = resume.describe(
            args.resume_from or args.compare_from,
            plan,
            registration["sources_sha256"],
            registration["runtime"],
            comparison_only=args.compare_from is not None,
            panel_kind=kind,
        )
        registration["comparison_only"] = args.compare_from is not None
        registration["max_wall_seconds"] = registration["resume"]["native_timeout_seconds"]
    output.mkdir()
    u.write(output / "registration.json", registration)
    u.write(output / "protocol.json", registration["protocol"])
    source = output / "source"
    for name in ("src", "validation/betse", "configs"):
        shutil.copytree(
            ROOT / name, source / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
        )
    for name in ("pyproject.toml", "requirements-lock.txt"):
        shutil.copy2(ROOT / name, source / name)
    environment = u.env(workspace, output / "cache")
    environment["PYTHONPATH"] = str(source / "src")
    environment["JAX_PLATFORMS"] = "cpu"
    with (output / "stdout.log").open("x") as out, (output / "stderr.log").open("x") as err:
        child = subprocess.Popen(
            [
                sys.executable,
                "-B",
                str(source / "validation/betse/junction_transport/run.py"),
                "_worker",
                str(output),
            ],
            stdout=out,
            stderr=err,
            stdin=subprocess.DEVNULL,
            env=environment,
            start_new_session=True,
            close_fds=True,
        )
    launch = {"pid": child.pid, "utc": u.utc(), "output": str(output)}
    u.write(output / "launch.json", launch)
    print(json.dumps(launch, indent=2))


if __name__ == "__main__":
    main()
