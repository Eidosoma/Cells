"""Offline failure replay, independently rebuilt comparison surfaces and immutable reports."""

import argparse
import copy
import importlib
import math
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import response_audit_context as ctx

c = ctx.c
frozen = importlib.import_module("held_response_check")
arrays = importlib.import_module("trajectory_check")
SCOPE = "D081 fixed 25 us held-input response rejection; no new simulation or qualification"
UNITS = ("voltage_V", "amount_fmol", "transfer_fmol", "flux_fmol_per_s", "current_A")
WORKER_FIELDS = {"registration_sha256", "sources", "elapsed_seconds"}


def immutable_summary(checks):
    """Value snapshot: later comparisons must not mutate an earlier phase's report."""
    return copy.deepcopy(
        {
            "comparisons": checks.count,
            "failed_comparisons": checks.failed_count,
            "maximum_normalized_error": checks.maximum,
            "worst": checks.worst,
            "first_failures": checks.failures[:100],
        }
    )


class AuditChecks:
    """Independent error normalization; all failures retained, not only the first 100."""

    def __init__(self):
        self.count = self.failed_count = 0
        self.maximum, self.worst, self.failures = 0.0, None, []

    def compare(self, label, actual, expected, unit, limits):
        absolute, relative = limits[unit], limits["relative"]
        c.require(
            all(
                type(v) in (int, float) and math.isfinite(v)
                for v in (actual, expected, absolute, relative)
            )
            and absolute > 0
            and relative >= 0,
            "Invalid independent comparison",
        )
        # Preserve the declared expected-value relative scale, not max(a,b).
        score = abs(actual - expected) / (absolute + relative * abs(expected))
        row = {"id": label, "actual": actual, "expected": expected, "normalized_error": score}
        self.count += 1
        if self.worst is None or score > self.maximum:
            self.maximum, self.worst = score, row
        if score > 1:
            self.failed_count += 1
            self.failures.append(row)


def reporting_defect():
    checks = AuditChecks()
    original, corrected = frozen.summary(checks), immutable_summary(checks)
    checks.compare(
        "synthetic/later_scope", 2.0, 0.0, "amount_fmol", {"amount_fmol": 1.0, "relative": 0.0}
    )
    c.require(
        original["first_failures"] is checks.failures
        and original["failed_comparisons"] == 0
        and len(original["first_failures"]) == 1,
        "Frozen alias defect not reproduced",
    )
    c.require(
        corrected["failed_comparisons"] == 0 and corrected["first_failures"] == [],
        "New snapshot aliases later results",
    )
    return {
        "issue": "mutable_failure_list_alias_between_internal_and_later_cross_scopes",
        "frozen_source_sha256": ctx.ANCHORS["sources.zip"],
        "old_checker_sha256": c.sha(c.HERE / "held_response_check.py"),
        "synthetic_reproduction": True,
        "corrected_reporting": "deep_value_snapshot",
        "physical_comparisons_changed": False,
        "old_source_rewritten": False,
    }


def instant(value):
    result = datetime.fromisoformat(value)
    c.require(result.utcoffset() == timedelta(0), "Non-UTC capture timestamp")
    return result


def inspect_metadata(registered, output):
    failure = ctx.verify_manifest(output, registered)
    launch, started = c.read(output / "launch.json"), c.read(output / "started.json")
    plan = registered["plan"]
    c.require(
        failure["schema"] == "cells.betse_held_response_failure@1"
        and failure["status"] == "failed_not_qualified"
        and failure["stage"] == "comparison"
        and "Response comparison failed; preserve all results without retry or tolerance changes"
        in failure["traceback"],
        "Not the recorded numerical rejection",
    )
    c.require(
        all(
            failure[k] is False
            for k in ("trajectory_qualified", "automatic_retry", "automatic_expansion")
        )
        and 0 < failure["elapsed_seconds"] < plan["total_timeout_seconds"],
        "Rejection scope/time differs",
    )
    c.require(
        launch["status"] == "launched_detached"
        and launch["registration_sha256"] == ctx.ANCHORS["registration.json"]
        and type(started["pid"]) is int
        and started["pid"] == launch["pid"] > 0
        and launch["automatic_polling"] is launch["automatic_retry"] is False
        and launch["independent_audit"] == "await_user_instruction"
        and all(launch[k] == plan[k] for k in ("stage_timeout_seconds", "total_timeout_seconds")),
        "Launch identity/resources differ",
    )
    first, began = instant(registered["registered_utc"]), instant(started["started_utc"])
    c.require(first <= instant(launch["launched_utc"]) <= began, "Capture chronology differs")
    ended = began + timedelta(seconds=failure["elapsed_seconds"])
    native, cells, comparison = (
        c.read(output / (name + ".json")) for name in ("native", "cells", "comparison")
    )
    for name, worker in (("native", native), ("cells", cells), ("comparison", comparison)):
        c.require(
            worker["registration_sha256"] == ctx.ANCHORS["registration.json"]
            and worker["sources"] == registered["sources"]
            and 0 < worker["elapsed_seconds"] < plan["stage_timeout_seconds"][name],
            "Worker identity/resource differs",
        )
    c.require(
        sum(w["elapsed_seconds"] for w in (native, cells, comparison)) < failure["elapsed_seconds"],
        "Worker/total elapsed times disagree",
    )
    c.require(
        native["engine"] == "actual_betse_full_sim_loop"
        and native["status"] == "capture_controls_pass_pending_comparison"
        and native["trajectory_run"] is True
        and native["warnings"] == []
        and cells["warnings"] == [],
        "Native execution status differs",
    )
    installed = {
        n: h
        for n, h in registered["upstream"]["files_sha256"].items()
        if n.startswith("betse/") and n.endswith(".py")
    }
    c.require(
        len(installed) == 332
        and native["installed_python_sha256"] == installed
        and Path(native["package_path"]).is_relative_to(c.REFERENCE_PYTHON.parent.parent)
        and native["environment"]["executable"] == str(c.REFERENCE_PYTHON)
        and native["environment"]["packages"]["betse"] == "1.5.0",
        "Native package provenance differs",
    )
    c.require(
        all(c.sha(Path(native["package_path"]).parent / n) == h for n, h in installed.items()),
        "Installed native source changed since capture",
    )
    c.require(
        cells["engine"] == "unchanged_cells_checked_rk4_runner"
        and cells["status"] == "exported_pending_comparison"
        and cells["accepted_runtime"] == registered["cells_runtime"]
        and cells["device"] == "cpu"
        and cells["x64_enabled"] is True
        and cells["jit_disabled"] is False
        and cells["trajectory_run"] is True
        and cells["source_path"] == str(c.ROOT / "src/cells/models/finite_extracellular.py")
        and cells["source_sha256"] == c.sha(cells["source_path"]),
        "Cells engine provenance differs",
    )
    c.require(
        native["pairs"]
        == [
            {"condition": row["condition"], "status": "observer_pair_exact"}
            for row in registered["native_rows"]
        ]
        and native["zero_control"] == {"status": "baseline_zero_response_exact"},
        "Native pair/zero coverage differs",
    )
    expected_native, stamps = [], [began]
    for row in registered["native_rows"]:
        for mode in plan["native_modes"]:
            prefix = f"native/{row['condition']}/{mode}"
            start = c.read(output / prefix / "started.json")
            c.require(start["row"] == row and start["mode"] == mode, "Native start row differs")
            stamps.append(instant(start["started_utc"]))
            checked = c.read(output / prefix / "checks.json")
            c.require(
                checked["status"] == "capture_row_checks_pass"
                and checked["observed_steps"] == (40 if mode == "observed" else 0)
                and 0 <= checked["maximum_baseline_scaled_control_error"] <= plan["control_atol"],
                "Native capture gates differ",
            )
            path = prefix + "/result.json"
            expected_native.append(
                {"row": row, "mode": mode, "path": path, "sha256": c.sha(output / path), **checked}
            )
    c.require(native["results"] == expected_native, "Native result manifest differs")
    c.require(
        cells["results"]
        == {row["id"]: f"cells/{row['id']}/result.json" for row in registered["cells_rows"]},
        "Cells result manifest differs",
    )
    for k, row in enumerate(registered["cells_rows"]):
        start = c.read(output / f"cells-started/{k:02d}.json")
        c.require(start["row"] == row, "Cells start row differs")
        stamps.append(instant(start["started_utc"]))
    c.require(stamps == sorted(stamps) and stamps[-1] < ended, "Row start chronology differs")
    c.require(
        comparison["status"] == "failed_not_qualified"
        and comparison["comparisons"] == ctx.PLAN["frozen_comparisons"]
        and comparison["failed_comparisons"] == ctx.PLAN["frozen_failures"]
        and comparison["criteria_unchanged"] is True,
        "Captured comparison verdict/counts differ",
    )
    c.require(
        all(
            comparison[k] is False
            for k in (
                "native_convergence_qualified",
                "forcing_convergence_qualified",
                "trajectory_qualified",
                "independent_audit_run",
                "biology_validated",
                "gpu_tested",
            )
        ),
        "Captured comparison overclaims qualification",
    )
    size = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
    c.require(size < plan["max_artifact_bytes"], "Capture artifact cap differs")
    c.require(
        all(
            p.stat().st_size < plan["max_worker_file_bytes"]
            for p in output.rglob("*")
            if p.is_file()
        ),
        "Capture worker-file cap differs",
    )
    return {
        "capture_seconds": failure["elapsed_seconds"],
        "stage_seconds": {
            n: w["elapsed_seconds"]
            for n, w in (("native", native), ("cells", cells), ("comparison", comparison))
        },
        "capture_bytes": size,
        "payloads": len(failure["files_sha256"]),
        "total_files": len(ctx.packet_hashes(output)),
        "native_runs": len(expected_native),
        "cells_runs": len(cells["results"]),
        "observed_native_steps": 160,
        "warnings": [],
    }


def native_surface(registered, record):
    """Rebuild all comparison columns directly, with a separate sum of transfer history."""
    g, b = registered["geometry"], registered["base_protocol"]
    trace, dt = record["trace"], record["dt_s"]
    steps, initial = trace["steps"], trace["initial"]
    owners, areas = g["membrane_owners"], g["membrane_areas_m2"]
    ci, co = initial["inside_mM"], initial["outside_mM"]
    # Native densities are mol/m2/s; volumes convert mM (= mol/m3) to fmol.
    rates = [
        [
            [
                math.fsum(
                    step["density_mol_per_m2_s"][s][j] * areas[j]
                    for j, owner in enumerate(owners)
                    if owner == i
                )
                / 1e-15
                for i in range(7)
            ]
            for s in range(3)
        ]
        for step in steps
    ]
    values = []
    for t in registered["common_times_s"]:
        index = round(t / dt)
        c.require(
            0 <= index <= len(steps) and math.isclose(t, index * dt, abs_tol=1e-18, rel_tol=0),
            "Independent native surface is off grid",
        )
        state = initial if index == 0 else steps[index - 1]["after"]
        values.append(
            {
                "voltage_V": [state["voltage_V"][owners.index(i)] for i in range(7)],
                "amount_fmol": [
                    (state["inside_mM"][s][i] - ci[s][i]) * (g["cell_volumes_m3"][i] / 1e-15)
                    for s in range(3)
                    for i in range(7)
                ]
                + [
                    (state["outside_mM"][s][0] - co[s][0]) * (g["effective_bath_volume_m3"] / 1e-15)
                    for s in range(3)
                ],
                "transfer_fmol": [
                    math.fsum(rates[k][s][i] * dt for k in range(index))
                    for s in range(3)
                    for i in range(7)
                ],
                "flux_fmol_per_s": [v for a in rates[index] for v in a]
                if index < len(steps)
                else [],
                "current_A": [
                    record["constants"]["F"]
                    * 1e-15
                    * math.fsum(b["expected_valence"][s] * rates[index][s][i] for s in range(3))
                    for i in range(7)
                ]
                if index < len(steps)
                else [],
            }
        )
    return values


def cells_surface(registered, record):
    times = arrays.unpack(record["times"])
    history = {
        k: arrays.unpack(record["history"][k])
        for k in ("amount_increment", "extracellular_amount_increment", "leak_transferred")
    }
    obs = {
        k: arrays.unpack(record["observations"][k])
        for k in ("times", "voltage_V", "leak_flux_fmol_per_s", "membrane_current_A")
    }
    c.require(
        obs["times"] == registered["common_times_s"], "Independent Cells observation grid differs"
    )
    values = []
    for j, t in enumerate(obs["times"]):
        c.require(t in times, "Independent Cells surface is off grid")
        index = times.index(t)
        values.append(
            {
                "voltage_V": obs["voltage_V"][j][:7],
                "amount_fmol": [v for a in history["amount_increment"][index] for v in a[:7]]
                + [a[0] for a in history["extracellular_amount_increment"][index]],
                "transfer_fmol": [v for a in history["leak_transferred"][index] for v in a[:7]],
                "flux_fmol_per_s": [v for a in obs["leak_flux_fmol_per_s"][j] for v in a[:7]]
                if j < len(obs["times"]) - 1
                else [],
                "current_A": obs["membrane_current_A"][j][:7] if j < len(obs["times"]) - 1 else [],
            }
        )
    return values


def compare_surface(label, left, right, limits, checks):
    c.require(len(left) == len(right) == 41, "Independent surface coverage differs")
    maxima = dict.fromkeys(UNITS, 0.0)
    converted = limits | {"transfer_fmol": limits.get("transfer_fmol", limits["amount_fmol"])}
    before, interval_max = checks.failed_count, 0.0
    for j in range(41):
        for unit in UNITS:
            count = 7 if unit in ("voltage_V", "current_A") else 24 if unit == "amount_fmol" else 21
            if j == 40 and unit in ("current_A", "flux_fmol_per_s"):
                count = 0
            a, b = left[j][unit], right[j][unit]
            c.require(len(a) == len(b) == count, "Independent owner/endpoint axes differ")
            for i in range(count):
                maxima[unit] = max(maxima[unit], abs(a[i] - b[i]))
                checks.compare(f"{label}/{j}/{unit}/{i}", a[i], b[i], unit, converted)
    for j in range(40):
        for i in range(21):
            a = left[j + 1]["transfer_fmol"][i] - left[j]["transfer_fmol"][i]
            b = right[j + 1]["transfer_fmol"][i] - right[j]["transfer_fmol"][i]
            interval_max = max(interval_max, abs(a - b))
            checks.compare(
                f"{label}/intervals/{j}/transfer_fmol/{i}", a, b, "transfer_fmol", converted
            )
    return {
        "maximum_absolute_errors": maxima,
        "maximum_interval_transfer_error_fmol": interval_max,
        "failed_comparisons": checks.failed_count - before,
    }


def independent_panel(registered, output):
    native = {
        r["condition"]: native_surface(
            registered,
            c.read(output / f"native/{r['condition']}/observed/result.json")["numerical"],
        )
        for r in registered["native_rows"]
    }
    cells = {
        row["id"]: cells_surface(registered, c.read(output / f"cells/{row['id']}/result.json"))
        for row in registered["cells_rows"]
    }
    checks, scopes = AuditChecks(), {}
    p, plan = registered["criteria"], registered["plan"]
    for condition in plan["conditions"]:
        for backend in plan["cells_backends"]:
            for a, b in ((1, 2), (2, 4)):
                label = f"fixed_input_solver/{condition}/{backend}/{a}-{b}"
                scopes[label] = compare_surface(
                    label,
                    cells[f"{condition}/{backend}/subdivision-{a}"],
                    cells[f"{condition}/{backend}/subdivision-{b}"],
                    p["instantaneous_tolerances"],
                    checks,
                )
            label = f"cross_engine/{condition}/{backend}"
            scopes[label] = compare_surface(
                label,
                native[condition],
                cells[f"{condition}/{backend}/subdivision-4"],
                p["trajectory_tolerances"],
                checks,
            )
        for factor in plan["cells_subdivisions"]:
            label = f"backend/{condition}/{factor}"
            scopes[label] = compare_surface(
                label,
                cells[f"{condition}/jax_eager/subdivision-{factor}"],
                cells[f"{condition}/jax_jit/subdivision-{factor}"],
                p["instantaneous_tolerances"],
                checks,
            )
    return checks, scopes, cells


def classify(failures, times):
    c.require(
        len(failures) == 150 and len({f["id"] for f in failures}) == 150,
        "Failure ledger is incomplete or duplicated",
    )
    details = []
    for failure in failures:
        parts = failure["id"].split("/")
        c.require(
            len(parts) == 6
            and parts[0] == "cross_engine"
            and parts[1] in ("baseline", "zero_amplitude", "suppression_recovery")
            and parts[2] in ("jax_eager", "jax_jit")
            and parts[3] in {str(i) for i in range(len(times))}
            and parts[4] == "amount_fmol"
            and parts[5] in ("21", "22"),
            "Unexpected failure location/quantity",
        )
        details.append(
            failure
            | {
                "condition": parts[1],
                "backend": parts[2],
                "time_s": times[int(parts[3])],
                "compartment": "shared_bath",
                "species": ("Na", "K", "Cl")[int(parts[5]) - 21],
            }
        )
    counts = dict(Counter(f["condition"] + "/" + f["species"] for f in details))
    return {
        "all_failures": details,
        "by_condition_and_species": counts,
        "all_in_shared_bath": True,
        "pulse_native_convergence_established": False,
    }


def compare_rebuild(original, checks, scopes):
    c.require(
        checks.count == ctx.PLAN["independent_surface_comparisons"]
        and checks.failed_count == ctx.PLAN["frozen_failures"],
        "Independent comparison counts differ",
    )
    c.require(
        checks.failures[:100] == original["first_failures"]
        and checks.worst == original["worst"]
        and checks.maximum == original["maximum_normalized_error"],
        "Independent failure identities/values differ",
    )
    c.require(
        set(scopes) == set(original["comparisons_by_scope"]), "Independent scope coverage differs"
    )
    for name, result in scopes.items():
        saved = original["comparisons_by_scope"][name]
        c.require(
            result["failed_comparisons"] == saved["failed_comparisons"],
            "Independent scope failure count differs",
        )
        pairs = [
            (result["maximum_absolute_errors"][u], saved["maximum_absolute_errors"][u])
            for u in UNITS
        ] + [
            (
                result["maximum_interval_transfer_error_fmol"],
                saved["maximum_interval_transfer_error_fmol"],
            )
        ]
        # Only diagnostic reconstruction roundoff from fsum vs sequential
        # accumulation; physical comparisons above use the ORIGINAL criteria.
        c.require(
            all(math.isclose(a, b, rel_tol=2e-11, abs_tol=2e-20) for a, b in pairs),
            "Independent reconstructed maximum differs beyond summation roundoff",
        )


def corrected_report(original, replay):
    c.require(
        replay == {k: v for k, v in original.items() if k not in WORKER_FIELDS},
        "Frozen numerical replay differs",
    )
    internal = original["internal_laws"]
    c.require(
        internal["comparisons"] == ctx.PLAN["internal_comparisons"]
        and internal["failed_comparisons"] == 0
        and internal["maximum_normalized_error"] < 1
        and internal["first_failures"] == original["first_failures"]
        and all(f["id"].startswith("cross_engine/") for f in internal["first_failures"]),
        "Not the verified report-list alias",
    )
    corrected = copy.deepcopy(original)
    corrected["internal_laws"]["first_failures"] = []
    return {
        "schema": "cells.betse_held_response_comparison_review@1",
        "source_comparison_sha256": ctx.ANCHORS["comparison.json"],
        "changed_fields": ["internal_laws.first_failures"],
        "correction": "empty internal failure list frozen before later cross comparisons",
        "comparison": corrected,
        "original_packet_rewritten": False,
        "physical_criteria_changed": False,
        "trajectory_qualified": False,
    }


def retained_baseline_ladder(registered, cells):
    rows = []
    root = c.ROOT / "runs/ref-003e0-expanded-2026-09-12/capture-01/native/passive/matched_constants"
    for dt in (0.000025, 0.0000125, 0.00000625):
        path = root / f"{dt:.8f}/default_profile/observed/result.json"
        record = c.read(path)["numerical"]
        c.require(
            record["dt_s"] == dt
            and all(
                all(
                    math.isclose(
                        v,
                        registered["base_protocol"]["permeability_m_per_s"][s],
                        rel_tol=2e-15,
                        abs_tol=0,
                    )
                    for v in a
                )
                for s, a in enumerate(record["permeability_m_per_s"])
            ),
            "Retained baseline is not constant-input correspondence",
        )
        checks = AuditChecks()
        compared = compare_surface(
            f"retained_baseline/{dt}",
            native_surface(registered, record),
            cells["baseline/jax_jit/subdivision-4"],
            registered["criteria"]["trajectory_tolerances"],
            checks,
        )
        rows.append(
            {
                "native_dt_s": dt,
                "path": str(path.relative_to(c.ROOT)),
                "sha256": c.sha(path),
                **immutable_summary(checks),
                **compared,
            }
        )
    errors = [r["maximum_absolute_errors"]["amount_fmol"] for r in rows]
    return {
        "scope": "previously captured constant-input baseline only; no pulse extrapolation",
        "rows": rows,
        "successive_amount_error_ratios": [errors[i + 1] / errors[i] for i in range(2)],
        "new_simulation": False,
        "pulse_native_convergence_qualified": False,
    }


def run(output):
    c.require(
        not any(n.split(".")[0] in frozen.fence.FORBIDDEN for n in sys.modules),
        "Audit imported a simulator or array library",
    )
    sys.meta_path.insert(0, frozen.fence.ImportFence())
    ctx.authenticate()
    registered = c.read(ctx.SESSION / "registration.json")
    captured = inspect_metadata(registered, ctx.SESSION)
    defect = reporting_defect()
    original = c.read(ctx.SESSION / "comparison.json")
    # Replay all original laws with their frozen, model-independent Decimal
    # helpers. Independent surface reconstruction below does not call those
    # helpers, frozen.compare_panel, frozen.difference or the original reporter.
    replay = frozen.run(registered, ctx.SESSION)
    reviewed = corrected_report(original, replay)
    checks, scopes, cells = independent_panel(registered, ctx.SESSION)
    compare_rebuild(original, checks, scopes)
    classification = classify(checks.failures, registered["common_times_s"])
    baseline = retained_baseline_ladder(registered, cells)
    c.write(output / "corrected-comparison.json", reviewed)
    c.write(output / "failure-ledger.json", classification)
    ctx.preservation_check()
    c.require(
        not any(n.split(".")[0] in frozen.fence.FORBIDDEN for n in sys.modules),
        "Audit loaded a model/array runtime",
    )
    return {
        "schema": "cells.betse_held_response_failure_audit@1",
        "status": "audit_pass_rejection_reproduced_pending_regression",
        "scope": SCOPE,
        "audited_utc": datetime.now(UTC).isoformat(),
        "anchors": ctx.ANCHORS,
        "driver_sha256": c.sha(Path(__file__)),
        "frozen_comparisons_replayed": replay["comparisons"],
        "internal_checks": {k: v for k, v in reviewed["comparison"]["internal_laws"].items()},
        "independent_surfaces": immutable_summary(checks),
        "comparisons_by_scope": scopes,
        "failure_classification": {k: v for k, v in classification.items() if k != "all_failures"},
        "reporting_defect": defect,
        "corrected_report_sha256": c.sha(output / "corrected-comparison.json"),
        "failure_ledger_sha256": c.sha(output / "failure-ledger.json"),
        "retained_constant_input_baseline": baseline,
        "external_metadata_change": ctx.EXTERNAL_METADATA,
        "response_qualified": False,
        "native_convergence_qualified": False,
        "forcing_convergence_qualified": False,
        "capture_rerun": False,
        "original_packet_rewritten": False,
        "biology_validated": False,
        "gpu_tested": False,
        "model_calls": 0,
        "model_imports": [],
        **captured,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    destination = args.output.resolve()
    c.require(
        destination.is_dir()
        and destination != ctx.SESSION
        and destination.is_relative_to(c.ROOT / "runs"),
        "Use the registered audit output directory",
    )
    c.write(destination / "audit.json", run(destination))
