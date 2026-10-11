#!/usr/bin/env python3
"""Run the frozen NUM-010 CPU panel once, retaining every attempted result."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import audit_spatial_extracellular_reference as auditor  # noqa: E402
from scripts import spatial_extracellular_artifacts as evidence  # noqa: E402
from tests import reference_spatial_extracellular_dynamics as ref  # noqa: E402
from tests import spatial_extracellular_numerical_checks as checks  # noqa: E402
from tests import spatial_extracellular_numerical_data as data  # noqa: E402


def save_record(output, case, setting, arrays, stats, *, restart=False):
    names = evidence.record_names(case.id, setting["id"], restart=restart)
    output.arrays(names[0], arrays)
    output.json(names[1], stats | {"id": setting["id"]})


def qualify(destination):
    plan, cases = data.load_panel()
    runtime = evidence.runtime()
    evidence.validate_runtime(runtime)
    capsule, source_sha = evidence.sources()
    started = monotonic()
    deadline = started + plan["resources"]["session_wall_seconds"]
    output = evidence.Artifacts(destination, plan["resources"]["artifact_bytes"])
    binding = {
        "runtime": runtime,
        "resources": plan["resources"],
        "source_sha256": source_sha,
        "panel_sha256": data.PANEL_SHA256,
        "protocol_sha256": source_sha["docs/SPATIAL_EXTRACELLULAR_NUMERICS.md"],
        "inherited_sha256": data.INHERITED_SHA256,
        "coordinate_contract": plan["coordinate_contract"],
        "scope": plan["scope"],
        "case_ids": [c.id for c in cases],
        "attempts": evidence.attempts(plan),
    }
    active, phase, analyses, all_stats, restarts = None, "registration", {}, {}, {}

    def time_check():
        if monotonic() >= deadline:
            raise ref.ResourceLimit("Spatial session wall-time budget exhausted")

    try:
        output.write("sources.zip", capsule)
        output.write("panel.json", data.PANEL.read_bytes())
        output.json(
            "registration.json",
            binding
            | {
                "schema": "cells.num010.registration@1",
                "status": "registered",
                "registered_utc": datetime.now(timezone.utc).isoformat(),
                "panel_integration_started": False,
            },
        )
        for case in cases:
            time_check()
            output.json(f"cases/{case.id}/definition.json", case.definition())
            records, stats = {}, {}
            for setting in evidence.attempts(plan):
                name = setting["id"]
                phase = f"main/{case.id}/{name}"
                budget = ref.Budget(
                    deadline=deadline, max_calls=plan["resources"]["max_rhs_calls_per_attempt"]
                )
                active = (case, setting, budget, False, 0.0, None)
                print(f"START {phase}", flush=True)
                if setting["method"] == "RK4":
                    arrays, info = ref.integrate_candidate(case, setting["dt_s"], budget=budget)
                else:
                    arrays, info = ref.integrate_reference(case, setting, budget=budget)
                info["id"] = name
                save_record(output, case, setting, arrays, info)
                active = None
                records[name], stats[name] = arrays, info
                print(
                    f"END {phase}: {info['status']}, {info['accepted_steps']} steps, "
                    f"{info['rhs_calls']} RHS calls, {info['seconds']:.3f} s",
                    flush=True,
                )
            phase = f"analysis/{case.id}"
            analysis = checks.analyze_case(case, records, stats, plan)
            output.json(f"cases/{case.id}/analysis.json", analysis)
            analyses[case.id], all_stats[case.id] = analysis, stats
            checks.require(
                analysis["references_pass"], "Independent reference or analytic gate failed"
            )
            time_check()
            print(f"CHECK {case.id}: references and declared analytic check pass", flush=True)
        phase = "selection"
        gates = checks.spatial_and_relaxation_checks(analyses, plan)
        selection = checks.select_candidate(analyses, plan)
        checks.require(all(g["pass"] for g in gates.values()), "Spatial or relaxation gate failed")
        checks.require(selection["status"] == "qualified", "No registered timestep qualified")
        selected = {
            "id": f"rk4_{selection['selected_dt_s']:g}",
            "method": "RK4",
            "dt_s": selection["selected_dt_s"],
        }
        print(f"SELECT RK4 dt={selection['selected_dt_s']:g} s", flush=True)
        for case in cases:
            phase = f"restart/{case.id}"
            # Restart from disk with all five original anchored coordinate fields.
            original, _ = evidence.load_record(output.path, case.id, selected["id"])
            midpoint = len(original["native_times_s"]) // 2
            start, initial = (
                float(original["native_times_s"][midpoint]),
                original["native_state"][midpoint],
            )
            budget = ref.Budget(
                deadline=deadline, max_calls=plan["resources"]["max_rhs_calls_per_attempt"]
            )
            active = (case, selected, budget, True, start, initial)
            resumed, info = ref.integrate_candidate(
                case, selected["dt_s"], budget=budget, start=start, initial=initial
            )
            info["id"] = selected["id"]
            save_record(output, case, selected, resumed, info, restart=True)
            active = None
            restarts[case.id] = auditor.restart_check(case, original, resumed, info, midpoint)
            time_check()
            print(f"CHECK {phase}: bitwise native/dense/observation suffix pass", flush=True)
        phase = "closeout"
        data.load_panel()
        checks.require(
            all(evidence.file_sha(ROOT / p) == digest for p, digest in source_sha.items()),
            "Numerical source changed during the registered session",
        )
        time_check()
        totals = {
            "main_attempts": sum(len(v) for v in all_stats.values()),
            "complete_attempts": sum(
                s["status"] == "complete" for v in all_stats.values() for s in v.values()
            ),
            "rejected_attempts": sum(
                s["status"] == "rejected" for v in all_stats.values() for s in v.values()
            ),
            "main_rhs_calls": sum(s["rhs_calls"] for v in all_stats.values() for s in v.values()),
            "main_accepted_steps": sum(
                s["accepted_steps"] for v in all_stats.values() for s in v.values()
            ),
        }
        checks.require(
            totals["main_attempts"] == plan["resources"]["main_attempts"], "Missing panel attempt"
        )
        result = binding | {
            "schema": "cells.num010.verification@1",
            "status": "qualified",
            "seconds": monotonic() - started,
            "production_version": "0.14.0",
            "production_changed": False,
            "gpu_tested": False,
            "biology_validated": False,
            "gates": gates,
            "selection": selection,
            "restarts": restarts,
            "totals": totals,
            "files_sha256": dict(output.hashes),
            "artifact_bytes_before_receipt": output.used,
        }
        output.json("verification.json", result, closing=True)
        print(
            json.dumps(
                {
                    "status": "qualified",
                    "directory": str(output.path),
                    "selected_dt_s": selection["selected_dt_s"],
                    "totals": totals,
                    "seconds": result["seconds"],
                    "artifact_bytes": output.used,
                },
                indent=2,
            ),
            flush=True,
        )
        return True
    except Exception as exc:
        prefix = {"active_attempt": None, "saved": False, "omission": None}
        if active is not None:
            case, setting, budget, restart, start, initial = active
            prefix["active_attempt"] = {
                "case": case.id,
                "setting": setting,
                "restart": restart,
                "start_s": start,
                "actual_trial_summary": budget.summary(),
            }
            try:
                if setting["method"] == "RK4":
                    arrays, info = ref.stopped_candidate(
                        case, setting["dt_s"], budget, exc, start=start, initial=initial
                    )
                else:
                    arrays, info = ref.stopped_reference(case, setting, budget, exc)
                names = evidence.record_names(case.id, setting["id"], restart=restart)
                if names[0] not in output.hashes:
                    output.arrays(names[0], arrays)
                if names[1] not in output.hashes:
                    output.json(names[1], info | {"id": setting["id"]}, closing=True)
                prefix["saved"] = True
            except Exception as prefix_error:
                prefix["omission"] = f"{type(prefix_error).__name__}: {prefix_error}"
        failure = binding | {
            "schema": "cells.num010.failure@1",
            "status": "stopped_not_qualified",
            "phase": phase,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "seconds": monotonic() - started,
            "prefix": prefix,
            "completed_case_analyses": list(analyses),
            "restarts": restarts,
            "selection": locals().get("selection"),
            "gates": locals().get("gates"),
            "files_sha256": dict(output.hashes),
            "artifact_bytes_before_receipt": output.used,
            "production_changed": False,
            "gpu_tested": False,
            "biology_validated": False,
        }
        output.json("failure.json", failure, closing=True)
        print(
            json.dumps(
                {
                    "status": failure["status"],
                    "phase": phase,
                    "error": str(exc),
                    "directory": str(output.path),
                    "prefix": prefix,
                },
                indent=2,
            ),
            flush=True,
        )
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    if not qualify(args.directory):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
