"""D094 source/receipt authentication and model-free saved-comparison replay."""

import importlib
import importlib.metadata
import math
import sys
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import loop_independent as independent
import readiness_independent as readiness

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "channel_loop_preparation"))
preparation = importlib.import_module("loop_context")
capture_job = importlib.import_module("loop_job")
checker = importlib.import_module("loop_check")
candidate = importlib.import_module("pilot_readiness")
reference = importlib.import_module("pilot_reference")
c = preparation.c
ROOT = c.ROOT
CAPTURE = ROOT / "runs/ref-004b-loop-preparation-2026-09-14/capture-01"
PLAN = HERE / "plan.json"
ANCHORS = {
    "completion.json": "49db72ff95caa5e69c96e476233f0874bde6a046affea5130dc1e0ad640a6efd",
    "registration.json": "e8ec5eb5e6274544bfced0dec64d77509c540d25e9222ed4703ace29e211cd27",
    "loop-comparisons.json": "56e8ca0d237d635e347b77bbf1b35e237481325d6b503326189937d2aadc304f",
    "cells.json": "6f04de8cc3a1b0afb7812933faf1c2d3e9d12a1f3e4e3db28e2a1a30a83e9951",
}
FORBIDDEN = preparation.audit.FORBIDDEN
OPERATIONAL = preparation.audit.OPERATIONAL
model_fence = preparation.audit.model_fence
packet_hashes = preparation.audit.packet_hashes
NEW_SOURCES = tuple(
    "validation/betse/channel_loop_audit/" + name
    for name in (
        "plan.json",
        "loop_audit_context.py",
        "loop_independent.py",
        "readiness_independent.py",
        "loop_audit_job.py",
        "test_loop_audit.py",
    )
) + ("docs/BETSE_CHANNEL_LOOP_CLOSEOUT.md",)


def sources():
    return {
        name: c.sha(ROOT / name) for name in sorted(set(preparation.sources()) | set(NEW_SOURCES))
    }


def validate_plan(plan):
    c.require(plan == c.read(PLAN), "Audit plan changed")
    c.require(
        plan["schema"] == "cells.betse_channel_loop_audit_plan@1" and plan["decision"] == "D094",
        "Wrong audit version",
    )
    c.require(
        plan["capture"] == str(CAPTURE.relative_to(ROOT)) and plan["anchors"] == ANCHORS,
        "Wrong audit evidence",
    )
    c.require(
        (
            plan["native_comparisons"],
            plan["readiness_comparisons"],
            plan["expected_comparisons"],
            plan["precision_digits"],
        )
        == (73744, 348, 74092, 80),
        "Audit numerical scope changed",
    )
    c.require(
        plan["cpu_affinity"] == [0, 1, 2, 3]
        and plan["total_timeout_seconds"] == 120
        and plan["max_artifact_bytes"] == 64 * 1024**2
        and plan["max_file_bytes"] == 32 * 1024**2,
        "Audit resources changed",
    )
    c.require(
        all(
            plan[k] is False
            for k in (
                "simulators_rerun",
                "automatic_polling",
                "automatic_retry",
                "automatic_followup",
            )
        ),
        "Unexpected automatic work",
    )


def manifest(packet, completion):
    payloads = {
        "betse.json",
        "betse.log",
        "cells.json",
        "cells.log",
        "loop-comparisons.json",
        "pilot-candidate-definitions.json",
        "registration.json",
        "sources.zip",
        "started.json",
        "matplotlib-cache/fontlist-v3.11.0.json",
    }
    for variant in independent.VARIANTS:
        for mode in ("observed", "unobserved"):
            folder = f"native/{variant}/{mode}/"
            payloads |= {
                folder + name
                for name in (
                    "INITS/world_1.betse.gz",
                    "INITS/init_1.betse.gz",
                    "core.json",
                    "fixture.json",
                    "geometry.json",
                    "native.yaml",
                    "result.json",
                )
            }
            if mode == "observed":
                payloads.add(folder + "loop-entry.json")
    hashes = packet_hashes(packet)
    c.require(
        len(payloads) == 70 and set(hashes) == payloads | OPERATIONAL | {"completion.json"},
        "Preparation packet membership changed",
    )
    c.require(
        set(completion["files_sha256"]) == payloads
        and all(hashes[n] == h for n, h in completion["files_sha256"].items()),
        "Preparation manifest changed",
    )
    c.require(
        all(
            (packet / name).stat().st_size == 0
            for name in ("runner.stdout.log", "runner.stderr.log", "cells.log")
        ),
        "Unexpected controller/Cells log",
    )
    return hashes


def partials(packet, native):
    for key, row in native["rows"].items():
        directory = packet / "native" / key
        c.require(c.read(directory / "result.json") == row, "Native aggregate/partial differs")
        for name, field in (
            ("core.json", "core_initial"),
            ("fixture.json", "fixture"),
            ("geometry.json", "geometry"),
        ):
            c.require(c.read(directory / name) == row[field], "Preparation partial differs")
        c.require(
            row["native_pickle"] == "INITS/init_1.betse.gz"
            and (directory / row["native_pickle"]).is_file(),
            "Wrong native restart path",
        )
        # Only hashes authenticate native pickles. Never unpickle/restart here.
        if row["mode"] == "observed":
            trace = row["trace"]
            entry = trace | {
                "status": "partial_not_qualified",
                "steps": [],
                "pending": None,
                "storage": [],
                "hook_restored": False,
                "calls": trace["calls"] | {"loop_return": 0, "run_return": 0},
            }
            c.require(c.read(directory / "loop-entry.json") == entry, "Loop-entry partial differs")


def receipts(packet, r, done, native, cells):
    launch, started = c.read(packet / "launch.json"), c.read(packet / "started.json")
    budget = r["protocol"]["resources"]
    c.require(
        launch["status"] == "launched_detached" and launch["pid"] == started["pid"] == 2427639,
        "Preparation controller differs",
    )
    c.require(
        launch["registration_sha256"] == done["registration_sha256"] == ANCHORS["registration.json"]
        and launch["resources"] == budget,
        "Preparation launch differs",
    )
    c.require(
        all(
            launch[k] is False
            for k in ("automatic_polling", "automatic_retry", "automatic_followup")
        ),
        "Preparation launch continuation differs",
    )
    c.require(
        done["schema"] == "cells.betse_channel_loop_preparation_capture@1"
        and done["status"] == "preparation_readiness_pass_pending_audit",
        "Original receipt rewritten",
    )
    counts = {
        "native_runs": 8,
        "native_updates": 64,
        "observed_steps": 32,
        "observer_pairs_checked": 4,
        "loop_comparisons": 73744,
        "initial_rate_comparisons": 348,
        "failed_comparisons": 0,
        "candidate_definitions_checked": 12,
        "cells_trajectory_runs": 0,
    }
    c.require(all(done[k] == v for k, v in counts.items()), "Preparation scope differs")
    c.require(
        done["tests"] == r["tests"] and done["prior_completion_sha256"] == preparation.PRIOR_SHA,
        "Preparation prerequisite differs",
    )
    c.require(
        all(
            done[k] is False
            for k in (
                "independent_audit_complete",
                "coupled_trajectory_qualified",
                "biology_validated",
                "gpu_tested",
                "production_changed",
                "automatic_retry",
                "automatic_followup",
            )
        ),
        "Preparation overclaims",
    )
    dates = [
        datetime.fromisoformat(v)
        for v in (
            r["registered_utc"],
            launch["launched_utc"],
            started["started_utc"],
            done["finished_utc"],
        )
    ]
    c.require(
        all(d.tzinfo is not None and d.utcoffset().total_seconds() == 0 for d in dates)
        and dates == sorted(dates),
        "Preparation chronology differs",
    )
    elapsed = done["elapsed_seconds"]
    c.require(
        type(elapsed) in (int, float)
        and math.isfinite(elapsed)
        and 0 < elapsed < budget["total_timeout_seconds"],
        "Preparation timeout",
    )
    c.require(
        (dates[-1] - dates[2]).total_seconds() <= elapsed <= (dates[-1] - dates[0]).total_seconds(),
        "Preparation clocks disagree",
    )
    c.require(
        sum(v["elapsed_seconds"] for v in (native, cells)) < elapsed,
        "Preparation worker accounting",
    )
    c.require(
        native["engine"] == "unmodified_betse_FULL_INIT_with_declared_initial_gate_fixture"
        and cells["engine"] == "unchanged_cells_initial_rates_and_candidate_grids",
        "Worker engines differ",
    )
    for kind, value in (("betse", native), ("cells", cells)):
        c.require(
            0 < value["elapsed_seconds"] < budget["worker_timeout_seconds"][kind], "Worker timeout"
        )
        c.require(
            value["warnings"] == []
            and value["cpu_affinity"] == [0, 1, 2, 3]
            and value["numerical_environment"] == r["cells_runtime"]["numerical_environment"],
            "Worker warnings/environment differ",
        )
        c.require(
            value["registration_sha256"] == ANCHORS["registration.json"],
            "Worker registration differs",
        )
    used = sum(p.stat().st_size for p in packet.rglob("*") if p.is_file())
    c.require(
        used - (packet / "completion.json").stat().st_size == done["artifact_bytes_before_receipt"]
        and used < budget["max_artifact_bytes"],
        "Preparation artifact accounting",
    )
    c.require(
        all(
            p.stat().st_size <= budget["max_worker_file_bytes"]
            for p in packet.rglob("*")
            if p.is_file()
        ),
        "Preparation file limit",
    )
    site = c.REFERENCE_PYTHON.parent.parent / "lib/python3.13/site-packages"
    installed = {
        "betse/" + str(p.relative_to(site / "betse")): c.sha(p)
        for p in (site / "betse").rglob("*.py")
    }
    packages = {
        dist.metadata["Name"]: dist.version
        for dist in importlib.metadata.distributions(path=[str(site)])
    }
    c.require(
        len(installed) == 332
        and installed == native["installed_python_sha256"]
        and packages == native["environment"]["packages"] == c.locked_reference_packages(),
        "Installed native source/packages differ",
    )
    c.require(
        all(
            importlib.metadata.version(k) == v == cells["environment"]["packages"].get(k)
            for k, v in r["cells_runtime"]["packages"].items()
        ),
        "Cells package versions differ",
    )
    return {
        "capture_files": 74,
        "capture_artifact_bytes": used,
        "captured_elapsed_seconds": elapsed,
        "installed_native_python_files": 332,
        "capture_source_inputs": 94,
        "accepted_implementation_files": 352,
        "production_modules": 51,
    }


def load_capture():
    c.require(
        all(c.sha(CAPTURE / name) == h for name, h in ANCHORS.items()), "Preparation anchor changed"
    )
    r = capture_job.authenticate(CAPTURE)
    c.require(
        len(r["sources_sha256"]) == 94 and c.authenticate_cells()["runtime"] == r["cells_runtime"],
        "Accepted production/source context differs",
    )
    done = c.read(CAPTURE / "completion.json")
    hashes = manifest(CAPTURE, done)
    native, cells = (capture_job.validate_worker(r, CAPTURE, kind) for kind in ("betse", "cells"))
    provenance = receipts(CAPTURE, r, done, native, cells)
    partials(CAPTURE, native)
    return {
        "registration": r,
        "completion": done,
        "native": native,
        "cells": cells,
        "comparison": c.read(CAPTURE / "loop-comparisons.json"),
        "definitions": c.read(CAPTURE / "pilot-candidate-definitions.json"),
        "hashes": hashes,
        "provenance": provenance,
    }


def frozen_readiness_replay(data):
    r, native, cells = data["registration"], data["native"], data["cells"]
    ledger = preparation.check.Ledger(
        {
            "tolerances": r["transport_protocol"]["tolerances"]
            | {"power_pJ_per_s": r["protocol"]["initial_power_atol_pJ_per_s"]}
        }
    )
    records = {row["id"]: row for row in cells["records"]}
    for variant in r["transport_protocol"]["variants"]:
        row = native["rows"][variant["id"] + "/observed"]
        enabled = variant["channel"]
        for step in r["protocol"]["pilot_candidate"]["cells_steps_s"]:
            key = variant["id"] + f"/dt_{step:.8g}"
            record, definition = records[key], data["definitions"][key]
            c.require(
                definition == candidate.definition(r, variant, row, step),
                "Frozen candidate compiler does not replay",
            )
            par = candidate.parameters(r, variant, row)
            c.require(record["independent_parameters"] == par, "Frozen parameter map differs")
            m, h = r["protocol"]["initial_gate"] if enabled else [0.0, 0.0]
            oracle = reference.rates(par, [0.0] * 7, [m] * 7, [h] * 7)
            c.require(
                record["independent_initial_rates"] == oracle, "Frozen vector field does not replay"
            )
            rate = record["initial_rhs"]
            pairs = [
                (
                    "voltage",
                    [e["cell"]["initial_voltage_V"] for e in definition["model"]["cells"]],
                    oracle["voltage_V"],
                    "voltage_V",
                ),
                (
                    "K_rate",
                    rate["amount_increment"][1][:7],
                    oracle["inward_K_fmol_per_s"],
                    "flux_fmol_per_s",
                ),
                (
                    "outside_K_rate",
                    rate["extracellular_amount_increment"][1][0],
                    oracle["outside_K_fmol_per_s"],
                    "flux_fmol_per_s",
                ),
            ]
            if enabled:
                pairs += [
                    (
                        "gates",
                        [v[:7] for v in rate["gate"]],
                        oracle["gate_rate_per_s"],
                        "gate_rate_per_s",
                    ),
                    (
                        "channel_transfer",
                        rate["channel_transferred"][:7],
                        oracle["inward_K_fmol_per_s"],
                        "flux_fmol_per_s",
                    ),
                    (
                        "dissipation",
                        rate["dissipated_energy_pJ"][:7],
                        oracle["dissipation_pJ_per_s"],
                        "power_pJ_per_s",
                    ),
                ]
            for name, actual, expected, unit in pairs:
                ledger.compare(key + "/" + name, actual, expected, unit)
    c.require(
        ledger.rows == cells["comparisons"] and len(ledger.rows) == 348,
        "Saved initial-rate comparisons do not replay",
    )


def numerical_audit(data):
    r = data["registration"]
    c.require(
        checker.evaluate(r, data["native"]) == data["comparison"],
        "Frozen native comparison does not replay",
    )
    frozen_readiness_replay(data)
    metrics = independent.Metrics()
    contracts = independent.native_metrics(r, data["native"], metrics)
    c.require(len(metrics.values) == 73744, "Native independent coverage differs")
    contracts |= readiness.readiness_metrics(
        r, data["native"], data["cells"], data["definitions"], metrics
    )
    tolerances = r["transport_protocol"]["tolerances"] | {
        "power_pJ_per_s": r["protocol"]["initial_power_atol_pJ_per_s"]
    }
    rows = metrics.audit(
        data["comparison"]["comparisons"] + data["cells"]["comparisons"], tolerances
    )
    c.require(len(rows) == 74092, "Independent total coverage differs")
    return contracts | {
        "frozen_comparisons_replayed": 74092,
        "independent_comparisons": len(rows),
        "failed_comparisons": sum(not row["passed"] for row in rows),
        "maximum_independent_scaled_error": max(row["scaled_error"] for row in rows),
    }, rows


def test_receipt(path):
    c.require(path.is_file() and path.is_relative_to(ROOT / "reports"), "Missing audit XML")
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    identities = []
    for suite in suites:
        rows = list(suite.findall("testcase"))
        c.require(
            len(rows) == int(suite.attrib["tests"])
            and all(int(suite.attrib.get(k, 0)) == 0 for k in ("failures", "errors", "skipped")),
            "Audit software checks incomplete",
        )
        for row in rows:
            c.require(
                not any(row.find(k) is not None for k in ("failure", "error", "skipped")),
                "Rejected audit software check",
            )
            identities.append(row.attrib["classname"] + "::" + row.attrib["name"])
    original = c.read(CAPTURE / "registration.json")["tests"]["identities"]
    new = set(identities) - set(original)
    c.require(
        len(original) == 96
        and len(identities) == len(set(identities))
        and set(original) <= set(identities),
        "Original 96 software tests missing/duplicated",
    )
    c.require(
        len(new) >= 40 and all("channel_loop_audit.test_loop_audit::" in name for name in new),
        "Wrong new audit test coverage",
    )
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": c.sha(path),
        "tests": len(identities),
        "previous_tests": 96,
        "new_tests": len(new),
        "identities": sorted(identities),
    }
