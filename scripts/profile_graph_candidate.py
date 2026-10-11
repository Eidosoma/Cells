"""D037: one preregistered, bounded short RK4 engineering session; no long study."""

import argparse
import hashlib
import json
import os
import resource
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import audit_graph_reference_panel as accepted_audit  # noqa: E402
from scripts import complete_graph_reference_panel as accepted  # noqa: E402
from tests import reference_candidate_comparison as comparison  # noqa: E402
from tests import reference_graph_candidate as candidate  # noqa: E402

campaign, previous, ref, prep = accepted.campaign, accepted.previous, accepted.ref, comparison.prep
PANEL = ROOT / "runs/num-005c1-a2-2026-09-09/panel-01"
PREPARATIONS = campaign.PARENT
PRIOR_ROOTS = [PREPARATIONS, *accepted.PRIOR_PARENTS, PANEL.parent]
OUTPUT_PARENT = ROOT / "runs/num-005c2a-2026-09-09"
PLAN = "configs/reference/e02_candidate_engineering_v1.json"
PLAN_SHA = "b3b7e5b29a930a35e0044e0bf7513ba31aa96fe3fcc1b78a025016053cd655d5"
CLOSEOUT = "reports/num-005c1-a2-closeout.json"
CLOSEOUT_SHA = "9feed5b0c20eae977efaa3fa5b9b9788127f660a58642665a4a2cbc64f358ead"
AUDIT = "reports/num-005c1-a2-audit.json"
AUDIT_SHA = "1502aa19c262306ff44c2443c8a76488312758a0e4d4d978fd60caee41186543"
SOURCES = accepted.SOURCES + [
    PLAN,
    "docs/E02_CANDIDATE_ENGINEERING.md",
    "tests/reference_graph_candidate.py",
    "tests/reference_candidate_comparison.py",
    "scripts/profile_graph_candidate.py",
    "scripts/audit_graph_candidate.py",
    "tests/unit/test_graph_candidate.py",
]


def evidence():
    closeout = campaign.frozen.pinned_json(ROOT / CLOSEOUT, CLOSEOUT_SHA)
    audited = campaign.frozen.pinned_json(ROOT / AUDIT, AUDIT_SHA)
    for name, digest in closeout["payload_hashes"].items():
        if not (ROOT / name).resolve().is_relative_to(ROOT) or ref.sha(ROOT / name) != digest:
            raise ValueError("Accepted panel closeout payload changed")
    registered, receipt, name = accepted_audit.check_integrity(PANEL)
    if (
        closeout["status"] != "pass"
        or audited["status"] != "pass"
        or name != "verification.json"
        or receipt["qualified_conditions"] != 14
        or audited["receipt_sha256"] != ref.sha(PANEL / name)
        or audited["registration_sha256"] != ref.sha(PANEL / "registration.json")
    ):
        raise ValueError("Accepted panel is not eligible for candidate comparison")
    prepared = ref.read_json(PREPARATIONS / "registration.json")
    if (
        prepared["preparation_cases"] != prep.preparations()
        or prepared["numerics"] != registered["numerics"]
    ):
        raise ValueError("Preparation/reference numerical identity differs")
    prior_bytes = sum(previous.tree_bytes(p) for p in PRIOR_ROOTS)
    if prior_bytes != 762443122:
        raise ValueError("Accepted preparation and long-reference aggregate differs")
    return registered, prepared, prior_bytes


def storage(output, prior_bytes, cap):
    if output.absolute() != output or output.resolve() != output or output.parent != OUTPUT_PARENT:
        raise ValueError("Engineering output must be an unlinked child of its registered parent")
    if OUTPUT_PARENT.exists() and (
        OUTPUT_PARENT.is_symlink() or set(OUTPUT_PARENT.iterdir()) - {output}
    ):
        raise ValueError("Unexpected engineering session/artifact")
    used = previous.tree_bytes(output) if output.exists() else 0
    if used + prior_bytes > cap or prior_bytes + candidate.paths.TAIL_RESERVE > cap:
        raise ref.BudgetExceeded("Aggregate candidate artifact budget exhausted")
    return {
        "prior_roots": [str(p.relative_to(ROOT)) for p in PRIOR_ROOTS],
        "prior_bytes": prior_bytes,
        "aggregate_cap_bytes": cap,
        "new_root_limit_bytes": cap - prior_bytes,
        "policy": "preparation_all_old_partial_failed_qualified_roots_and_one_new_root_no_reset",
    }


def specification(output):
    panel, prepared, prior_bytes = evidence()
    plan = campaign.frozen.pinned_json(ROOT / PLAN, PLAN_SHA)
    if (
        plan["cases"] != panel["numerics"]["study_cases"]
        or candidate.Grid(plan["step"], plan["duration"]).count != plan["steps_per_profile"]
        or plan["planned_profiles"] != len(plan["cases"]) * len(plan["window_widths"])
        or plan["accuracy_limit"] != 1
        or plan["long_study_run"]
        or plan["timestep_selected"]
        or plan["automatic_retry_or_refinement"]
        or plan["production_changed"]
    ):
        raise ValueError("Short profile plan differs from the numerical contract")
    cases = {}
    for key in plan["cases"]:
        preparation = key.startswith("prepare_")
        if preparation:
            label = key[-1]
            selected = {
                "case": prepared["preparation_cases"][label],
                "duration": prepared["duration"],
                "methods": prepared["methods"],
                "numerics": prepared["numerics"],
            }
            trajectories = {
                variant: str((PREPARATIONS / label / variant).relative_to(ROOT))
                for variant in selected["methods"]
            }
        else:
            manifest = panel["references"][key]
            selected = {
                "case": panel["cases"][key],
                "duration": panel["duration"],
                "methods": manifest["methods"],
                "numerics": panel["numerics"],
            }
            trajectories = manifest["trajectories"]
        cases[key] = {
            "selected": selected,
            "trajectories": trajectories,
            "reference_receipt_hashes": {
                f"{directory}/trajectory.json": ref.sha(ROOT / directory / "trajectory.json")
                for directory in trajectories.values()
            },
        }
    return {
        "revision": plan["revision"],
        "plan": plan,
        "plan_sha256": PLAN_SHA,
        "output_directory": str(output.relative_to(ROOT)),
        "cases": cases,
        "observation_times": sorted(
            {t for t in panel["observation_times"] if t <= plan["duration"]} | {plan["duration"]}
        ),
        "numerics": panel["numerics"],
        "resources": panel["resources"],
        "runtime": prep.runtime(),
        "thread_environment": campaign.THREADS,
        "production_source_hashes": prep.production_identity(campaign.frozen.load_protocol()),
        "prior_closeout_sha256": CLOSEOUT_SHA,
        "prior_audit_sha256": AUDIT_SHA,
        "storage_budget": storage(output, prior_bytes, panel["resources"]["artifact_budget_bytes"]),
        "planned_attempts": [
            f"{key}/window-{width:03d}" for key in plan["cases"] for width in plan["window_widths"]
        ],
    }


def register(output):
    previous.check_threads()
    spec = specification(output)
    if spec["runtime"]["cpu_affinity"] != spec["resources"]["cpu_affinity"]:
        raise ValueError("Candidate CPU affinity differs")
    output.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(
        output / "reference_sources.zip", "x", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for name in SOURCES:
            archive.write(ROOT / name, name)
    receipt = spec | {
        "source_hashes": {name: ref.sha(ROOT / name) for name in SOURCES},
        "source_capsule_sha256": ref.sha(output / "reference_sources.zip"),
    }
    ref.write_json(output / "registration.json", receipt)
    return receipt


def check_registration(output):
    receipt = ref.read_json(output / "registration.json")
    spec = specification(output)
    if set(receipt) != set(spec) | {"source_hashes", "source_capsule_sha256"} or any(
        receipt[k] != v for k, v in spec.items()
    ):
        raise ValueError("Candidate registration inputs/runtime/budgets changed")
    if receipt["source_hashes"] != {name: ref.sha(ROOT / name) for name in SOURCES} or receipt[
        "source_capsule_sha256"
    ] != ref.sha(output / "reference_sources.zip"):
        raise ValueError("Candidate source identity changed")
    with zipfile.ZipFile(output / "reference_sources.zip") as archive:
        if sorted(archive.namelist()) != sorted(SOURCES) or any(
            hashlib.sha256(archive.read(name)).hexdigest() != digest
            for name, digest in receipt["source_hashes"].items()
        ):
            raise ValueError("Candidate source capsule differs")
    return receipt


def execution(registration, key):
    if key not in registration["planned_attempts"]:
        raise ValueError("Unregistered candidate profile")
    case, window = key.rsplit("/window-", 1)
    r = registration["resources"] | {
        "window_steps": int(window),
        "artifact_budget_bytes": registration["storage_budget"]["new_root_limit_bytes"],
    }
    return case, r


def identity(registration, case):
    return {
        "sources": registration["source_hashes"],
        "runtime": registration["runtime"],
        "reference_selection": registration["cases"][case],
    }


def worker(output, key):
    begun = perf_counter()
    previous.check_threads()
    if (output / "verification.json").exists() or (output / "failure.json").exists():
        raise ValueError("Closed engineering session cannot launch a worker")
    r = check_registration(output)
    case, resources = execution(r, key)
    session = ref.read_json(output / "session.json")
    starts = [json.loads(line) for line in (output / "attempts.jsonl").read_text().splitlines()]
    if (
        session["registration_sha256"] != ref.sha(output / "registration.json")
        or session["automatic_retry"]
        or [a["key"] for a in starts] != r["planned_attempts"][: len(starts)]
        or starts[-1]["key"] != key
        or any(not (output / a["key"] / "profile.json").exists() for a in starts[:-1])
        or (
            datetime.now(timezone.utc) - datetime.fromisoformat(session["started_utc"])
        ).total_seconds()
        >= r["resources"]["session_wall_budget_seconds"]
    ):
        raise ValueError("Candidate worker order/session differs")
    selected = r["cases"][case]["selected"]
    model = prep.graph.Model(selected["case"])
    checked_begun = perf_counter()
    consumer = comparison.Comparison(
        {v: ROOT / d for v, d in r["cases"][case]["trajectories"].items()},
        selected,
        output / key,
        output,
        resources,
        r["observation_times"],
    )
    result = candidate.integrate(
        model,
        output / key,
        step=r["plan"]["step"],
        end=r["plan"]["duration"],
        numerics=r["numerics"],
        resources=resources,
        identity=identity(r, case),
        artifact_root=output,
        comparison=consumer,
    )
    checked_seconds = perf_counter() - checked_begun
    profile = {
        "key": key,
        "status": result["status"],
        "checked_candidate_seconds": checked_seconds,
        "process_wall_seconds_including_input_checks": perf_counter() - begun,
        "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "rss_scope": "Linux_process_high_water_with_imports_checks_comparison_not_array_estimate",
        "artifact_bytes_before_profile_receipt": previous.tree_bytes(output / key),
        "trajectory_sha256": ref.sha(output / key / "trajectory.json"),
        "long_time_step_selected": False,
        "production_changed": False,
    }
    ref.write_json(output / key / "profile.json", profile)
    print(json.dumps(profile, sort_keys=True), flush=True)


def run(output):
    r = register(output)
    begun = perf_counter()
    ref.write_json(
        output / "session.json",
        {
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "registration_sha256": ref.sha(output / "registration.json"),
            "wall_budget_seconds": r["resources"]["session_wall_budget_seconds"],
            "automatic_retry": False,
        },
    )
    attempts = []
    try:
        for key in r["planned_attempts"]:
            remaining = r["resources"]["session_wall_budget_seconds"] - (perf_counter() - begun)
            if remaining <= 0:
                raise ref.BudgetExceeded("Candidate engineering session exhausted")
            started = {"key": key, "status": "started", "initial_time": 0}
            with (output / "attempts.jsonl").open("a") as handle:
                handle.write(json.dumps(started, sort_keys=True) + "\n")
            attempts.append(started)
            log = output / f"{key.replace('/', '-')}.log"
            print(f"Starting short profile {key}", flush=True)
            worker_begun = perf_counter()
            with log.open("x") as handle:
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "scripts/profile_graph_candidate.py"),
                        "--output",
                        str(output),
                        "--worker",
                        key,
                    ],
                    cwd=ROOT,
                    env=os.environ | campaign.THREADS,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    timeout=min(remaining, r["resources"]["worker_timeout_seconds"]),
                    check=False,
                )
            attempts[-1] = started | {
                "status": "complete" if completed.returncode == 0 else "failed",
                "returncode": completed.returncode,
                "log_sha256": ref.sha(log),
                "wall_seconds_including_startup_and_all_receipts": perf_counter() - worker_begun,
            }
            if completed.returncode != 0:
                raise ValueError("Short candidate profile failed; no automatic retry/refinement")
            measured = ref.read_json(output / key / "profile.json")
            print(
                f"Completed {key}: {measured['checked_candidate_seconds']:.3f} s checked",
                flush=True,
            )
        check_registration(output)
        seconds = perf_counter() - begun
        if seconds > r["resources"]["session_wall_budget_seconds"]:
            raise ref.BudgetExceeded("Candidate engineering session exhausted")
        receipt = {
            "status": "pass",
            "scope": "short_engineering_only_pending_independent_audit",
            "seconds": seconds,
            "attempts": attempts,
            "profiles": {
                key: ref.read_json(output / key / "profile.json") for key in r["planned_attempts"]
            },
            "registration_sha256": ref.sha(output / "registration.json"),
            "payload_hashes": previous.payload_hashes(output),
            "long_study_run": False,
            "long_time_step_selected": False,
            "production_changed": False,
        }
        ref.write_json(output / "verification.json", receipt)
        storage(output, r["storage_budget"]["prior_bytes"], r["resources"]["artifact_budget_bytes"])
        return receipt
    except Exception as error:
        ref.write_json(
            output / "failure.json",
            {
                "status": "incomplete",
                "exception": type(error).__name__,
                "message": str(error),
                "seconds": perf_counter() - begun,
                "attempts": attempts,
                "not_started": r["planned_attempts"][len(attempts) :],
                "no_automatic_retry": True,
                "registration_sha256": ref.sha(output / "registration.json"),
                "payload_hashes": previous.payload_hashes(output),
                "long_study_run": False,
                "long_time_step_selected": False,
                "production_changed": False,
            },
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    output = args.output.absolute()
    if args.worker and not args.run:
        worker(output, args.worker)
    elif args.run and not args.worker:
        run(output)
    else:
        parser.error("Choose --run for one new session or an already registered --worker")


if __name__ == "__main__":
    main()
