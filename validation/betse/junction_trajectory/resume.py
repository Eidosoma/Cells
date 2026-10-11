"""Reuse complete native captures in a fresh, authenticated trajectory run."""

import argparse
import math
import os
import shutil
import statistics
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fresh_rerun"))
import common as u  # noqa: E402

# Partial capture resume permits only orchestration changes. A complete native
# panel may use a revised checker, with both revisions recorded. Native physics,
# preparation, observation, production Cells, reference and tolerances must match.
CONTROL_FILES = {
    "validation/betse/junction_transport/run.py",
    "validation/betse/junction_trajectory/resume.py",
    "validation/betse/junction_trajectory/test_resume.py",
}
COMPARISON_FILES = {
    "validation/betse/junction_trajectory/check.py",
    "validation/betse/junction_trajectory/test_trajectory.py",
}
NATIVE_COUPLED_COMPARISON_FILES = {
    "validation/betse/junction_native_coupled/check.py",
    "validation/betse/junction_native_coupled/compatibility.py",
    "validation/betse/junction_native_coupled/test_check.py",
    "validation/betse/junction_native_coupled/test_replay.py",
}


def comparison_files(panel_kind):
    u.need(panel_kind in ("trajectory", "native_coupled"), "Unsupported comparison panel kind")
    return COMPARISON_FILES if panel_kind == "trajectory" else NATIVE_COUPLED_COMPARISON_FILES


def compatible_sources(previous, current, *, comparison_only=False, panel_kind="trajectory"):
    allowed = CONTROL_FILES | (comparison_files(panel_kind) if comparison_only else set())

    def scientific(sources):
        return {k: v for k, v in sources.items() if k not in allowed}

    u.need(scientific(previous) == scientific(current), "Resume scientific source changed")
    return {
        k: {"previous": previous.get(k), "current": current.get(k)}
        for k in sorted(allowed)
        if previous.get(k) != current.get(k)
    }


def identities(protocol):
    result = {}
    for case in protocol["cases"]:
        u.need(
            Path(case["id"]).name == case["id"] and case["id"] not in (".", ".."),
            "Unsafe trajectory case name",
        )
        for i, dt in enumerate(protocol["native_steps_s"]):
            for mode in protocol["native_modes"]:
                u.need(mode in ("observed", "bare"), "Unknown native mode")
                name = f"{case['id']}/step-{i}/{mode}"
                u.need(name not in result, "Duplicate trajectory identity")
                result[name] = (case, dt, mode)
    return result


def complete_row(path, identity, protocol, *, panel_kind="trajectory"):
    """A terminal row is reusable; partial rows are never solver checkpoints."""
    u.need(not path.is_symlink(), "Linked native row")
    files = u.inventory(path)
    u.need("failure.json" not in files, "Native row has a failure artifact")
    required = {
        "result.json",
        "preparation.json",
        "native.yaml",
        "INITS/init_1.betse.gz",
        "INITS/world_1.betse.gz",
    }
    u.need(required <= files.keys(), "Incomplete native capture files")
    row = u.read(path / "result.json")
    case, dt, mode = identity
    u.need(
        row["case"] == case
        and row["dt_s"] == dt
        and row["mode"] == mode
        and row["steps"] == round(case.get("duration_s", protocol["duration_s"]) / dt),
        "Native capture identity/clock changed",
    )
    u.need(row["hook_restored"] and row["native_pickle_present"], "Incomplete native lifecycle")
    u.need(files["preparation.json"] == row["preparation_sha256"], "Native preparation changed")
    if mode == "observed":
        u.need("loop-entry.json" in files, "Missing native loop entry")
        u.need(
            "trace.npz" in files and files["trace.npz"] == row["trace_sha256"],
            "Native trace changed",
        )
    else:
        u.need(row["trace_sha256"] is None and "trace.npz" not in files, "Bare trace changed")
    if panel_kind == "native_coupled":
        if mode == "observed":
            u.need(
                "gates.npz" in files and files["gates.npz"] == row["gates_sha256"],
                "Native gate trace changed",
            )
        else:
            u.need(
                row["gates_sha256"] is None and "gates.npz" not in files, "Bare gate trace changed"
            )
    return files, u.read(path / "preparation.json")


def describe(
    prior,
    protocol,
    current_sources,
    checker_runtime,
    *,
    comparison_only=False,
    panel_kind="trajectory",
):
    """Register bytes now; the failed parent has no completed panel receipt."""
    prior = prior.resolve()
    u.need((prior / "failure.json").is_file(), "Resume requires a terminal failed parent")
    u.need(not (prior / "completion.json").exists(), "Parent is already complete")
    launch = u.read(prior / "launch.json")
    try:
        os.kill(launch["pid"], 0)
    except ProcessLookupError:
        pass
    else:
        raise ValueError("Resume parent controller is still present")
    registration = u.read(prior / "registration.json")
    u.need(registration["panel_kind"] == panel_kind, "Wrong resume panel kind")
    u.need(panel_kind == "trajectory" or comparison_only, "Dynamic native reuse is comparison-only")
    u.need(
        registration["protocol"] == protocol == u.read(prior / "protocol.json"),
        "Resume protocol changed",
    )
    u.need(registration["runtime"] == checker_runtime, "Resume checker runtime changed")
    previous_sources = registration["sources_sha256"]
    u.need(u.sources(prior / "source") == previous_sources, "Parent frozen source changed")
    changes = compatible_sources(
        previous_sources, current_sources, comparison_only=comparison_only, panel_kind=panel_kind
    )
    expected = identities(protocol)
    parent_files = ["registration.json", "protocol.json", "failure.json", "launch.json"]
    panel_rows = None
    if comparison_only:
        u.need(
            (prior / "native/completion.json").is_file()
            and not (prior / "native/failure.json").exists(),
            "Comparison requires a complete native panel",
        )
        done = u.read(prior / "native/completion.json")
        u.need(
            done["status"]
            == (
                "native_held_open_trajectories_recorded"
                if panel_kind == "trajectory"
                else "native_dynamic_free_voltage_recorded"
            )
            and done["panel_sha256"] == u.sha(prior / "native/panel.json"),
            "Completed native panel changed",
        )
        panel = u.read(prior / "native/panel.json")
        u.need(panel["protocol"] == protocol, "Completed native protocol changed")
        panel_rows = {r["path"]: r["sha256"] for r in panel["rows"]}
        u.need(
            len(panel["rows"]) == len(expected) and panel_rows.keys() == expected.keys(),
            "Completed native panel membership changed",
        )
        parent_files += ["native/completion.json", "native/panel.json"]
    actual = {
        str(p.parent.relative_to(prior / "native"))
        for p in (prior / "native").glob("*/step-*/*/result.json")
    }
    u.need(actual <= expected.keys(), "Unregistered native capture")
    rows, partial, timings = {}, [], []
    native_runtime = upstream = None
    groups = {}
    for name, identity in expected.items():
        path = prior / "native" / name
        if name not in actual:
            if path.exists():
                partial.append(name)
            continue
        u.need(path.resolve().is_relative_to(prior / "native"), "Linked native capture path")
        files, prepared = complete_row(path, identity, protocol, panel_kind=panel_kind)
        if panel_rows is not None:
            u.need(files["result.json"] == panel_rows[name], "Completed native row changed")
        if native_runtime is None:
            native_runtime, upstream = prepared["runtime"], prepared["upstream"]
        u.need(prepared["runtime"] == native_runtime, "Mixed native runtimes")
        u.need(prepared["upstream"] == upstream, "Mixed native upstream sources")
        rows[name] = {"files_sha256": files}
        # File mtimes estimate preparation-to-result cost, not physical time.
        # An explicit monotonic receipt is preferred for newly captured rows.
        timing = path / "capture-timing.json"
        elapsed = (
            u.read(timing)["elapsed_seconds"]
            if timing.exists()
            else (path / "result.json").stat().st_mtime
            - (path / "preparation.json").stat().st_mtime
        )
        u.need(math.isfinite(elapsed) and elapsed > 0, "Invalid native capture timing")
        key = (round(protocol["duration_s"] / identity[1]), identity[2])
        groups.setdefault(key, []).append(elapsed)
        timings.append(
            {
                "path": name,
                "seconds": elapsed,
                "basis": "monotonic" if timing.exists() else "file_mtimes_after_preparation",
            }
        )
    u.need(rows, "No complete native captures to resume")
    missing = [name for name in expected if name not in rows]
    u.need(not comparison_only or not missing, "Comparison requires all native captures")
    estimate = upper = 10.0  # Process startup.
    for name in missing:
        _, dt, mode = expected[name]
        samples = groups.get((round(protocol["duration_s"] / dt), mode))
        u.need(samples, "Missing timing evidence for a remaining native step/mode")
        estimate += statistics.mean(samples) + 2.0
        upper += max(samples) + 10.0
    timeout = max(300, math.ceil((2 * upper + 120) / 300) * 300)
    return {
        "parent": str(prior),
        "parent_files_sha256": {name: u.sha(prior / name) for name in parent_files},
        "control_source_changes": {k: v for k, v in changes.items() if k in CONTROL_FILES},
        "comparison_source_changes": {
            k: v for k, v in changes.items() if k in comparison_files(panel_kind)
        },
        "comparison_only": comparison_only,
        "rows": rows,
        "missing_rows": missing,
        "discarded_partial_rows": partial,
        "native_runtime": native_runtime,
        "upstream": upstream,
        "timing_evidence": timings,
        "estimated_native_seconds": 0.0 if comparison_only else estimate,
        "native_timeout_seconds": 0 if comparison_only else timeout,
        "timeout_policy": "Twice the sum of largest matching step/mode costs plus 10 s per row, "
        "10 s startup and 120 s reserve, rounded up to 300 s",
        "reuse_is_numerical_acceptance": False,
    }


def copy_row(source, destination, expected):
    u.need(u.inventory(source) == expected, "Native capture changed before copy")
    shutil.copytree(source, destination)
    u.need(u.inventory(destination) == expected, "Copied native capture changed")


def stage_complete(output, registration):
    """Copy a complete native panel without importing or executing BETSE."""
    receipt = registration["resume"]
    u.need(receipt["comparison_only"], "Expected comparison-only registration")
    u.need(registration["sources_sha256"] == u.sources(), "Frozen comparison source changed")
    prior = Path(receipt["parent"])
    u.need(
        describe(
            prior,
            registration["protocol"],
            u.sources(),
            registration["runtime"],
            comparison_only=True,
            panel_kind=registration.get("panel_kind", "trajectory"),
        )
        == receipt,
        "Registered comparison evidence changed",
    )
    expected = {
        f"{name}/{file}": value
        for name, row in receipt["rows"].items()
        for file, value in row["files_sha256"].items()
    }
    expected.update(
        {
            name: receipt["parent_files_sha256"]["native/" + name]
            for name in ("panel.json", "completion.json")
        }
    )
    copy_row(prior / "native", output, expected)
    u.budget(output)


def capture(output, workspace, registration):
    output.mkdir(parents=True, exist_ok=False)
    protocol, resume = registration["protocol"], registration["resume"]
    try:
        u.need(not resume["comparison_only"], "Completed panel must use comparison-only staging")
        u.need(registration["sources_sha256"] == u.sources(), "Frozen resume source changed")
        u.need(
            describe(Path(resume["parent"]), protocol, u.sources(), registration["runtime"])
            == resume,
            "Registered resume evidence changed",
        )
        u.need(u.runtime() == resume["native_runtime"], "Resume native runtime changed")
        import prepare

        upstream = prepare.native_setup(workspace)[3]
        u.need(upstream == resume["upstream"], "Resume native upstream changed")
        native = u.private("trajectory_native_resume", Path(__file__).with_name("native.py"))
        rows = []
        for name, (case, dt, mode) in identities(protocol).items():
            path = output / name
            if name in resume["rows"]:
                copy_row(
                    Path(resume["parent"]) / "native" / name,
                    path,
                    resume["rows"][name]["files_sha256"],
                )
                action = "reused"
            else:
                began = time.monotonic()
                native.run_row(path, workspace, protocol, case, dt, mode)
                u.write(
                    path / "capture-timing.json",
                    {
                        "elapsed_seconds": time.monotonic() - began,
                        "finished_utc": u.utc(),
                    },
                )
                _, prepared = complete_row(path, (case, dt, mode), protocol)
                u.need(
                    prepared["runtime"] == resume["native_runtime"], "New native runtime changed"
                )
                u.need(prepared["upstream"] == upstream, "New native upstream changed")
                action = "recorded"
            rows.append({"path": name, "sha256": u.sha(path / "result.json")})
            used = u.budget(output)
            u.need(used <= protocol["resources"]["artifact_bytes"], "Junction artifact cap")
            u.need(
                max(p.stat().st_size for p in output.rglob("*") if p.is_file())
                <= protocol["resources"]["per_file_bytes"],
                "Junction per-file cap",
            )
            print(name, action, flush=True)
        u.need(
            not any(k == "cells" or k.startswith("cells.") for k in sys.modules),
            "Native process imported Cells",
        )
        u.write(output / "panel.json", {"protocol": protocol, "rows": rows})
        u.write(
            output / "completion.json",
            {
                "status": "native_held_open_trajectories_recorded",
                "panel_sha256": u.sha(output / "panel.json"),
                "utc": u.utc(),
                "reused_rows": len(resume["rows"]),
                "new_rows": len(resume["missing_rows"]),
            },
        )
    except BaseException:
        u.write(output / "failure.json", {"traceback": traceback.format_exc(), "utc": u.utc()})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--registration", type=Path, required=True)
    args = parser.parse_args()
    registration = u.read(args.registration)
    u.need(u.read(args.protocol) == registration["protocol"], "Resume protocol changed")
    capture(args.output, args.workspace, registration)
