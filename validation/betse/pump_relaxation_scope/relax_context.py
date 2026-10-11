"""Authenticate R0 closeout; explicitly scope the next reference-only experiment."""

import copy
import importlib.metadata
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "live_recording_audit"))
import audit_context as c  # noqa: E402
import live_audit_job as previous  # noqa: E402

ROOT = c.ROOT
AUDIT = ROOT / "runs/ref-005d-live-audit-2026-09-17/audit-01"
AUDIT_REG_SHA = "4b8cb8f0e4eb919c4930b40f2b7b8702ab8fd2bc96e45e39de6ca9d23da0eb55"
AUDIT_SHA = "769994fac30ba99e64bc5c3f998c49e9d1c747c3a2e9bbeb5fadd2c57febb647"
SCOPE = HERE / "scope.json"
FORBIDDEN_REFERENCE = (
    "cells",
    "betse",
    "jax",
    "jaxlib",
    "pilot_native",
    "pilot_cells",
    "live_native",
    "live_observer",
    "output_worker",
)
REFERENCE_FILES = (
    "validation/betse/contact.py",
    "validation/betse/pump_matched_pilot/pilot_context.py",
    "validation/betse/pump_matched_pilot/pilot_math.py",
    "validation/betse/pump_matched_pilot/pilot_reference.py",
    "validation/betse/pump_matched_pilot/protocol.json",
    "validation/betse/pump_coupled/coupled_plan.py",
    "validation/betse/pump_coupled/coupled_reference.py",
)


def runtime():
    return dict(
        python=sys.version,
        packages={
            n: importlib.metadata.version(n)
            for n in ("numpy", "jax", "jaxlib", "scipy", "ml_dtypes", "opt_einsum")
        },
    )


def inherited():
    return c.read(c.LEGACY / "registration.json", None)


def sources():
    names = set(c.sources()) | set(REFERENCE_FILES)
    names.update(
        str(p.relative_to(ROOT)) for p in HERE.iterdir() if p.suffix in (".py", ".md", ".json")
    )
    names.update(
        (
            "reports/REF005D_LIVE_CLOSEOUT.md",
            "reports/REF005E_REFERENCE_SCOPE_HANDOFF.md",
            "docs/BETSE_NEXT_GATES.md",
            "validation/betse/biological_candidates/xenopus_costa_1989.json",
        )
    )
    return {n: c.sha(c.child(ROOT, n)) for n in sorted(names)}


def authenticate_r0():
    """Recheck seals/coverage, not numerical trajectories or the full review."""
    with c.e.model_fence():
        previous.authenticate(AUDIT, AUDIT_REG_SHA)
        done, files = c.packet(
            AUDIT,
            "completion.json",
            AUDIT_SHA,
            extras=("launch.json", "runner.stdout.log", "runner.stderr.log"),
            count=66,
        )
        c.need(
            done["status"] == "live_recording_saved_outputs_and_receipts_independently_closed"
            and done["failed_comparisons"] == 0
            and len(files) == 70,
            "R0 review verdict",
        )
        for name in (
            "physics_rerun",
            "production_changed",
            "scientific_tolerances_changed",
            "native_memory_bounded",
            "longer_horizon_qualified",
            "biology_validated",
            "gpu_tested",
            "unsaved_trajectories_directly_inspected",
            "automatic_followup",
        ):
            c.need(done[name] is False, "Expanded R0 scope: " + name)
        c.need(
            c.read(AUDIT / "launch.json")["registration_sha256"] == AUDIT_REG_SHA
            and (AUDIT / "runner.stderr.log").read_bytes() == b"",
            "R0 launch/stderr",
        )
        for phase in ("probe", "matrix"):
            rows = {
                v["key"]: v
                for p in sorted((AUDIT / phase).glob("*.json"))
                for v in [c.read(p, None)]
            }
            c.need(previous.cells_gate(phase, rows) == done[phase], "R0 Cells report coverage")
        rows = {
            v["label"]: v
            for p in sorted((AUDIT / "native").glob("*.json"))
            for v in [c.read(p, None)]
        }
        c.need(
            previous.native_review.matrix_gate(rows, c.read(AUDIT / "pairs.json", None))
            == done["native"],
            "R0 native report coverage",
        )
        c.need(
            c.read(AUDIT / "review.json", None)
            == {k: done[k] for k in ("native", "probe", "matrix")},
            "R0 report link",
        )
    return dict(
        status="r0_saved_live_outputs_and_expected_receipts_closed",
        audit_registration_sha256=AUDIT_REG_SHA,
        audit_completion_sha256=AUDIT_SHA,
        audit_files_sha256=files,
        review_elapsed_seconds=done["elapsed_seconds"],
        native=done["native"],
        matrix=done["matrix"],
        probe=done["probe"],
        reviewer_peak_rss_bytes=done["reviewer_peak_rss_bytes"],
        native_memory_bounded=False,
        unsaved_trajectories_directly_inspected=False,
        full_betse_parity=False,
        longer_horizon_qualified=False,
        automatic_followup=False,
    )


def validate(scope, old):
    c.need(scope == c.read(SCOPE), "Unregistered reference scope")
    c.need(
        scope["schema"] == "cells.pump_relaxation_reference_scope@1"
        and scope["stage"] == "R1-S0"
        and scope["duration_s"] == 0.01
        and scope["reference_solves"] == 18
        and scope["variants"] == old["protocol"]["variants"],
        "Reference-only scope",
    )
    for name in (
        "native_ladder_qualified",
        "matched_10ms_qualified",
        "biology_validated",
        "production_changed",
        "equations_changed",
        "scientific_tolerances_changed",
        "automatic_polling",
        "automatic_retry",
        "automatic_followup",
    ):
        c.need(scope[name] is False, "Expanded reference scope: " + name)
    c.need(
        scope["native_runs"] == scope["cells_runs"] == 0
        and scope["steady_state_thresholds"] is None,
        "Unregistered model/physiology work",
    )
    reference = old["protocol"]["reference"]
    c.need(
        scope["reference_rhs_calls_per_solve"] == reference["max_rhs_calls_per_solve"] == 30000
        and scope["reference_accepted_steps_per_solve"]
        == reference["max_accepted_steps_per_solve"]
        == 4096,
        "Reference work cap changed",
    )
    c.need(
        round(scope["duration_s"] / reference["sample_dt_s"]) + 1
        == scope["reference_samples_per_solve"]
        == 1601
        and round(old["protocol"]["duration_s"] / reference["sample_dt_s"]) + 1
        == scope["overlap_samples_per_solve"]
        == 161,
        "Reference sample coverage",
    )
    c.need(runtime() == old["cells_reference_runtime"], "Reference runtime changed")


def preparation(scope, old):
    validate(scope, old)
    plan, cases = copy.deepcopy(old["protocol"]), copy.deepcopy(old["cases"])
    plan.update(
        schema="cells.pump_reference_scoping_protocol@1",
        decision="D130",
        scope="10 ms reference/domain study only; no native or Cells integration",
        duration_s=scope["duration_s"],
        restart_time_s=0.005,
        common_times_s=[i * scope["shared_observation_interval_s"] for i in range(41)],
    )
    for case in cases.values():
        c.need(
            case["end_time_s"] == 0.001
            and case["controls"] == [dict(time_s=0.0, pump=1.0, leak=1.0)]
            and len(case["volume_pL"]) == 7,
            "Inherited preparation scope",
        )
        case["end_time_s"] = scope["duration_s"]
    return plan, cases


def resource_context():
    """Actual recorder measurements and explicitly nonbinding projections."""
    rows = [c.read(p, None) for p in sorted((AUDIT / "native").glob("*.json"))]
    captures = [c.read(p, None) for p in sorted((c.NATIVE / "native").glob("*/capture.json"))]
    c.need(len(rows) == len(captures) == 36, "Measured resource coverage")
    stream_bytes = sum(r["stream"]["stream_bytes"] for r in rows)
    elapsed = math.fsum(r["elapsed_seconds"] for r in captures)
    history_bytes = max(r["native_history_numeric_payload_bytes"] for r in captures)
    return dict(
        measured_1ms=dict(
            stream_bytes=stream_bytes,
            native_capture_seconds_sum=elapsed,
            largest_native_history_numeric_payload_bytes=history_bytes,
            max_native_process_peak_rss_bytes=max(
                r[k]["process_peak_bytes"]
                for r in captures
                for k in ("rss_before_loop", "rss_after_loop", "rss_after_recording")
            ),
        ),
        linear_10ms_projection=dict(
            stream_bytes=10 * stream_bytes,
            native_capture_seconds=10 * elapsed,
            largest_native_history_numeric_payload_bytes=10 * history_bytes,
        ),
        projection_is_measurement=False,
        projection_is_eta=False,
        includes_all_native_allocations=False,
        full_campaign_budget_approved=False,
        native_histories_retained=True,
    )


def readiness(old):
    candidate = c.read(
        ROOT / "validation/betse/biological_candidates/xenopus_costa_1989.json", None
    )
    geometry = old["native_geometry"]
    c.need(geometry["cell_count"] == 7 and geometry["membrane_count"] == 30, "Known cluster")
    c.need(
        candidate["runnable"] is False and candidate["biology_validated"] is False,
        "Candidate accidentally promoted",
    )
    return dict(
        junction=dict(
            status="supported_cluster_known_topology_capture_required",
            cell_count=7,
            membrane_faces=30,
            saved_geometry_fields=sorted(geometry),
            reciprocal_face_edge_map_present=False,
            selected_edges=None,
            native_job_launched=False,
            next="Record neighbour/edge ownership and held-open fluxes before dynamic gating",
        ),
        biology=dict(
            status="candidate_methods_and_data_provenance_pending",
            candidate_sha256=c.sha(
                ROOT / "validation/betse/biological_candidates/xenopus_costa_1989.json"
            ),
            blockers=candidate["blocking_questions_before_biological_registration"],
            new_literature_review=False,
            parameters_selected=False,
            experimental_run_launched=False,
        ),
    )
