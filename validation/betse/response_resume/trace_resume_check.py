"""Read-only reuse and comparison; original files are never copied or relabelled."""

import argparse
import importlib
import sys
from datetime import UTC, datetime
from pathlib import Path

import trace_resume_context as ctx
import trace_resume_probe as probe

c = ctx.c
old = importlib.import_module("refined_response_check")


def cells_path(r, output, identifier):
    c.require(identifier in r["cells_definitions"], "Unregistered Cells result identity")
    relative = "cells/" + identifier + "/result.json"
    if identifier in r["reused_cells"]:
        entry = r["reused_cells"][identifier]
        c.require(
            entry["path"] == relative and c.sha(ctx.FAILED / relative) == entry["sha256"],
            "Reused Cells result link differs",
        )
        return ctx.FAILED / relative
    c.require(
        identifier in {row["id"] for row in r["new_cells_rows"]},
        "Cells row has no registered provenance",
    )
    return output / relative


def read_native(view, checks):
    natives, packets, rows, pairs = {}, {}, [], []
    original = ctx.previous()
    for row in view["native_rows"]:
        pair, row_id = {}, ctx.prior.prior.key(row)
        for mode in original["plan"]["native_modes"]:
            directory = ctx.FAILED / "native" / row_id / mode
            packet = old.links.read_packet(directory, mode)
            retained = (
                c.read(ctx.prior.overlap_path(row, mode))
                if row["condition"] != "suppression_recovery"
                else None
            )
            checked = old.native.check_row(
                row,
                mode,
                packet,
                old.evidence.trusted_registration(),
                original["plan"],
                ctx.prior.prepared(row),
                retained,
            )
            c.require(checked == c.read(directory / "checks.json"), "Retained native checks differ")
            rows.append(
                {
                    "row": row,
                    "mode": mode,
                    "path": str((directory / "result.json").relative_to(ctx.FAILED)),
                    "sha256": c.sha(directory / "result.json"),
                    **checked,
                }
            )
            pair[mode] = packet
        pairs.append({"row_id": row_id, **old.links.check_pair(pair)})
        packets[row["condition"]] = pair["observed"]
        natives[row["condition"]] = old.native_record(view, pair["observed"], row, checks)
    return natives, rows, pairs, old.native.check_zero(packets)


def zero_controls(view, records, complete):
    checked = 0
    for backend in view["plan"]["cells_backends"]:
        for factor in view["plan"]["cells_subdivisions"]:
            identifiers = [
                ctx.prior.identifier(view["plan"]["hold_step_s"], condition, backend, factor)
                for condition in ("baseline", "zero_amplitude")
            ]
            if not all(i in records for i in identifiers):
                c.require(not complete, "Missing complete-panel zero control")
                continue
            left, right = (records[i] for i in identifiers)
            c.require(
                all(
                    left[k] == right[k]
                    for k in ("times", "history", "observations", "diagnostics", "final_step_index")
                ),
                "Zero-amplitude changes Cells response",
            )
            checked += 1
    return checked


def load_fine(r, output=None, partial=False):
    panels, laws, native_rows, native_pairs, native_zero = {}, {}, [], [], {}
    retained_cells, fresh_cells, zeros = 0, 0, 0
    for h in r["plan"]["hold_steps_s"]:
        view, checks = ctx.prior.panel_view(r, h), old.Checks()
        natives, rows, pairs, zero = read_native(view, checks)
        native_rows += rows
        native_pairs += pairs
        native_zero[f"{h:.8f}"] = zero
        cells, records = {}, {}
        for row in view["cells_rows"]:
            identifier = row["id"]
            reused = identifier in r["reused_cells"]
            if partial and not reused:
                continue
            record = c.read(cells_path(r, output, identifier))
            records[identifier] = record
            cells[identifier] = old.local.cells_record(view, record, row, checks)
            retained_cells += int(reused)
            fresh_cells += int(not reused)
        zeros += zero_controls(view, records, complete=not partial)
        laws[f"{h:.8f}"] = old.summary(checks)
        panels[h] = view, natives, cells
    worker = c.read(ctx.FAILED / "native.json")
    c.require(
        native_rows == worker["results"]
        and native_pairs == worker["pairs"]
        and native_zero == worker["zero_control"],
        "Retained native worker linkage differs",
    )
    return (
        panels,
        laws,
        {
            "retained_native_runs": len(native_rows),
            "retained_cells_runs": retained_cells,
            "new_cells_runs": fresh_cells,
            "Cells_zero_pairs": zeros,
        },
    )


def reuse_check(r):
    _, laws, coverage = load_fine(r, partial=True)
    summary = old.combine(list(laws.values()))
    c.require(
        summary["failed_comparisons"] == 0 and summary["comparisons"] == 666108,
        "Retained physical/control checks failed; no continuation",
    )
    return {
        "schema": "cells.betse_trace_resume_reuse_check@1",
        "status": "retained_rows_pass_frozen_internal_checks_not_response_qualification",
        "created_utc": datetime.now(UTC).isoformat(),
        "failure_anchors": ctx.ANCHORS,
        "reused_cells": r["reused_cells"],
        "internal_laws": summary,
        "internal_laws_by_hold": laws,
        **coverage,
        "original_cells_worker_receipt_exists": False,
        "provenance": "frozen_failure_manifest_registration_started_rows_and_completed_payloads",
        "integration_calls": 0,
        "independent_audit_run": False,
        "trajectory_qualified": False,
    }


def validate_reuse(result, r):
    c.require(
        result["schema"] == "cells.betse_trace_resume_reuse_check@1"
        and result["status"]
        == "retained_rows_pass_frozen_internal_checks_not_response_qualification"
        and result["failure_anchors"] == ctx.ANCHORS
        and result["reused_cells"] == r["reused_cells"]
        and result["internal_laws"] == old.combine(list(result["internal_laws_by_hold"].values()))
        and result["internal_laws"]["comparisons"] == 666108
        and result["internal_laws"]["failed_comparisons"] == 0
        and result["retained_native_runs"] == 16
        and result["retained_cells_runs"] == 26
        and result["new_cells_runs"] == 0
        and result["Cells_zero_pairs"] == 6
        and result["original_cells_worker_receipt_exists"] is False
        and result["integration_calls"] == 0
        and result["independent_audit_run"] is False
        and result["trajectory_qualified"] is False,
        "Reuse check scope/verdict differs",
    )


def run(r, output):
    c.require(
        not any(n.split(".")[0] in old.fence.FORBIDDEN for n in sys.modules),
        "Continuation comparison imported simulator/array library",
    )
    sys.meta_path.insert(0, old.fence.ImportFence())
    ctx.validate_registration(r)
    worker = c.read(output / "cells.json")
    c.require(
        worker["schema"] == "cells.betse_trace_resume_cells_worker@1"
        and worker["status"] == "exported_pending_comparison"
        and worker["new_cells_runs"] == 22
        and worker["reused_cells_runs"] == 26
        and worker["runtime_resource_probe_sha256"] == c.sha(output / "runtime-resource-probe.json")
        and worker["registration_sha256"] == c.sha(output / "registration.json")
        and worker["sources"] == r["sources"]
        and worker["engine"] == "unchanged_cells_checked_rk4_runner"
        and worker["accepted_runtime"] == r["cells_runtime"]
        and worker["warnings"] == []
        and worker["trajectory_run"] is True
        and worker["device"] == "cpu"
        and worker["x64_enabled"] is True
        and worker["jit_disabled"] is False
        and worker["results"]
        == {row["id"]: "cells/" + row["id"] + "/result.json" for row in r["new_cells_rows"]},
        "New worker coverage/provenance differs",
    )
    probe.validate(c.read(output / "runtime-resource-probe.json"), r)
    for k, row in enumerate(r["new_cells_rows"]):
        c.require(
            c.read(output / f"cells-started/{k:02d}.json")["row"] == row,
            "New started-row sequence differs",
        )
    coarse = c.read(ctx.prior.COARSE / "registration.json")
    replay = old.legacy.run(coarse, ctx.prior.COARSE)
    original = c.read(ctx.prior.COARSE / "comparison.json")
    c.require(
        replay
        == {
            k: v
            for k, v in original.items()
            if k not in {"registration_sha256", "sources", "elapsed_seconds"}
        }
        and replay["failed_comparisons"] == 150
        and replay["comparisons"] == 345576,
        "Original coarse rejection did not reproduce exactly",
    )
    panels, laws, coverage = load_fine(r, output)
    natives, cells, law, _, _, _ = old.read_panel(ctx.prior.COARSE, coarse, coarse, coarse=True)
    panels[0.000025], laws["0.00002500"] = (coarse, natives, cells), law
    scopes = {}
    for h in (0.000025, *r["plan"]["hold_steps_s"]):
        view, natives, cells = panels[h]
        c.require(
            laws[f"{h:.8f}"]["comparisons"] == 4864 * ctx.prior.count(h) + 3704,
            "Internal-law coverage differs",
        )
        scopes |= old.compare_panel(view, natives, cells, 0.00000625)
    scopes |= old.across_holds(r, panels)
    result = old.verdict(laws, scopes)
    c.require(
        result["comparisons"] == 2494936
        and result["required_gates"]["comparisons"] == 2298936
        and len(scopes) == 132
        and coverage
        == {
            "retained_native_runs": 16,
            "retained_cells_runs": 26,
            "new_cells_runs": 22,
            "Cells_zero_pairs": 12,
        },
        "Continuation comparison surface differs",
    )
    return result | {
        "schema": "cells.betse_trace_resume_comparison@1",
        **coverage,
        "new_native_runs": 0,
        "additional_coarse_native_runs_reused": 8,
        "additional_coarse_Cells_runs_reused": 24,
        "coarse_failed_comparisons": 150,
        "coarse_rejection_replayed_exactly": True,
        "resource_failure_preserved": True,
        "criteria_unchanged": True,
        "terminal_native_rate_invented": False,
        "terminal_Cells_rate_validated": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    c.require(
        not any(n.split(".")[0] in old.fence.FORBIDDEN for n in sys.modules),
        "Reuse check imported model/array library",
    )
    sys.meta_path.insert(0, old.fence.ImportFence())
    ctx.authenticate()
    r = ctx.inputs()
    result = reuse_check(r)
    validate_reuse(result, r)
    c.write(args.output.resolve(), result)
    print("16 native / 26 Cells retained rows: 666108 internal checks pass; no integration")
