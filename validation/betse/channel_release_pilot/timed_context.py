"""D105 reference-gated timed experiment over frozen production and prior evidence."""

import bisect
import copy
import hashlib
import importlib
import json
import math
import sys
import zipfile
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "channel_release_reference"))
previous = importlib.import_module("piecewise_context")
previous_job = importlib.import_module("piecewise_job")
c, io, ROOT = previous.c, previous.io, previous.ROOT
design, feedback = previous.design, previous.feedback
model_fence, packet_hashes, OPERATIONAL = (
    previous.model_fence,
    previous.packet_hashes,
    previous.OPERATIONAL,
)
PLAN = HERE / "plan.json"
CAPTURE = ROOT / "runs/ref-004d-release-reference-2026-09-15/reference-01"
REFERENCE_SHA = "ae670b6e1825c1677ccfd29d008b5036aca371ede5c83d1dba49d3bcc3d01b8f"
FILES = tuple(
    "validation/betse/channel_release_pilot/" + name
    for name in (
        "plan.json",
        "timed_context.py",
        "timed_reference_review.py",
        "timed_input.py",
        "timed_native.py",
        "timed_native_check.py",
        "timed_cells.py",
        "timed_cells_check.py",
        "timed_compare.py",
        "timed_job.py",
        "test_timed_release.py",
    )
) + ("docs/BETSE_CHANNEL_TIMED_RELEASE.md",)
key = feedback.key


def validate_plan(plan):
    c.require(
        json.dumps(plan, sort_keys=True, allow_nan=False)
        == json.dumps(c.read(PLAN), sort_keys=True, allow_nan=False),
        "Unregistered timed release plan",
    )
    c.require(
        plan["schema"] == "cells.betse_timed_release_plan@1"
        and plan["decision"] == "D105"
        and plan["reference_completion_sha256"] == REFERENCE_SHA
        and plan["reference_review_before_simulators"] is True,
        "Timed scope/entrance gate differs",
    )
    for name in (
        "duration_s",
        "block_time_s",
        "release_time_s",
        "histories",
        "conditions",
        "native_steps_s",
        "cells_steps_s",
    ):
        c.require(plan[name] == c.read(design.PLAN)[name], "Timed fixture differs: " + name)
    for name in (
        "reference_integration_rerun",
        "production_changed",
        "release_response_qualified",
        "biology_validated",
        "gpu_tested",
        "automatic_polling",
        "automatic_retry",
        "automatic_followup",
    ):
        c.require(plan[name] is False, "Expanded timed scope: " + name)


def availability(schedule, t, side="right"):
    c.require(
        type(t) in (float, int) and math.isfinite(t) and t >= 0 and side in ("left", "right"),
        "Control clock/side",
    )
    starts = [r["time"] for r in schedule]
    index = (bisect.bisect_left if side == "left" else bisect.bisect_right)(starts, t) - 1
    return schedule[max(index, 0)]["availability"]


def intervals(schedule, duration, step):
    tick, end = Decimal(str(step)), Decimal(str(duration))
    c.require(tick > 0 and end > 0 and end / tick == int(end / tick), "Incomplete native grid")
    for row in schedule:
        index = Decimal(str(row["time"])) / tick
        c.require(index == int(index) and 0 <= row["time"] < duration, "Off-grid input boundary")
    return [
        {
            "index": i,
            "start_s": float(i * tick),
            "end_s": float((i + 1) * tick),
            "availability": availability(schedule, float(i * tick)),
        }
        for i in range(int(end / tick))
    ]


def prerequisite():
    c.require(c.sha(CAPTURE / "completion.json") == REFERENCE_SHA, "Reference completion changed")
    with model_fence():
        registration = previous.authenticate(CAPTURE)
        native = previous_job.validate_worker(registration, CAPTURE)
    done, hashes = c.read(CAPTURE / "completion.json"), packet_hashes(CAPTURE)
    c.require(
        done["status"] == "piecewise_reference_pass_pending_review"
        and done["comparison"]["failed_comparisons"]
        == done["dense_replay"]["failed_comparisons"]
        == 0
        and done["signal"]["pass"] is True
        and done["reference_paths"] == 24
        and done["segment_integrations"] == 48,
        "Reference result is not ready for saved review",
    )
    c.require(
        set(hashes) == set(done["files_sha256"]) | OPERATIONAL | {"completion.json"}
        and all(hashes[n] == h for n, h in done["files_sha256"].items())
        and done["tests"] == registration["tests"]
        and done["registration_sha256"] == c.sha(CAPTURE / "registration.json"),
        "Reference packet changed",
    )
    c.require(
        len(hashes) == 34
        and len(registration["sources_sha256"]) == 182
        and native["warnings"] == [],
        "Reference provenance scope",
    )
    return {"path": str(CAPTURE.relative_to(ROOT)), "files_sha256": hashes}


def views(plan):
    result = {}
    for history in plan["histories"]:
        view = copy.deepcopy(design.view(history))
        protocol = view["protocol"]
        protocol.update(
            duration_s=plan["duration_s"],
            variants=plan["conditions"],
            common_times_s=plan["common_times_s"],
            native_steps_s=plan["native_steps_s"],
            cells_steps_s=plan["cells_steps_s"],
            native_runs=24,
            cells_trajectories=16,
            cells_resumed_segments=4,
        )
        protocol["resources"].update(plan["resources"])
        view["schedules"] = {v: design.schedule(c.read(design.PLAN), v) for v in plan["conditions"]}
        view["reference_parameters"] = {
            v: copy.deepcopy(view["reference_parameters"]["active_channel"])
            for v in plan["conditions"]
        }
        view["cells_definitions"] = {}
        for condition in plan["conditions"]:
            for step, backend in [(s, "jax_jit") for s in plan["cells_steps_s"]] + [
                (plan["cells_steps_s"][0], "jax_eager")
            ]:
                definition = design.definition(
                    c.read(design.PLAN), history, condition, step, backend
                )
                definition["experiment"]["observation_times"] = plan["common_times_s"]
                view["cells_definitions"][key(condition, step, backend)] = definition
        result[history] = view
    return result


def sources():
    return previous.sources() | {name: c.sha(ROOT / name) for name in FILES}


def reports():
    return previous.reports() | {
        name: c.sha(ROOT / name)
        for name in (
            "reports/ref-004d-release-reference-checks-02.xml",
            "reports/REF004D_RELEASE_REFERENCE_CAPTURE.md",
            "reports/REF004D_TIMED_RELEASE_HANDOFF.md",
            "reports/REF004D_TIMED_RELEASE_SOFTWARE_TIMEOUT.md",
            "reports/ref-004d-timed-release-checks-02.xml",
            "reports/ref-004d-timed-release-checks-03.xml",
            "reports/ref-004d-timed-release-checks-04.xml",
            "reports/ref-004d-timed-release-checks-05.xml",
            "reports/ref-004d-timed-release-checks-06.xml",
            "reports/ref-004d-timed-release-checks-07.xml",
            "reports/ref-004d-timed-release-checks-08.xml",
        )
    }


def xml_receipt(path):
    c.require(
        path.is_file() and path.is_relative_to(ROOT / "reports"), "Missing timed software XML"
    )
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    names = []
    for suite in suites:
        rows = list(suite.findall("testcase"))
        c.require(
            len(rows) == int(suite.attrib["tests"])
            and all(int(suite.attrib.get(k, 0)) == 0 for k in ("failures", "errors", "skipped")),
            "Incomplete timed software tests",
        )
        for row in rows:
            c.require(
                not any(row.find(k) is not None for k in ("failure", "error", "skipped")),
                "Rejected software test",
            )
            names.append(row.attrib["classname"] + "::" + row.attrib["name"])
    c.require(names and len(names) == len(set(names)), "Empty/duplicate software coverage")
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": c.sha(path),
        "tests": len(names),
        "identities": sorted(names),
    }


def test_receipt(paths):
    receipts = [xml_receipt(path) for path in paths]
    names = [name for receipt in receipts for name in receipt["identities"]]
    required = {
        "test_real_full_native_timed_loop_and_accounting",
        "test_real_cells_carry_restart_backend_and_side_rhs",
        "test_reference_sources_and_capture_authenticate_without_models",
        "test_detached_launch_never_waits_or_polls",
        "test_reference_crosscheck_rejects_corrupted_original_column",
        "test_missing_reference_gate_blocks_worker_before_launch",
    }
    c.require(
        len(names) >= 50
        and len(names) == len(set(names))
        and all("channel_release_pilot.test_timed_release::" in n for n in names)
        and required <= {name.split("::")[-1] for name in names},
        "Timed software coverage",
    )
    return {"receipts": receipts, "tests": len(names), "identities": sorted(names)}


def authenticate(output):
    r = c.read(output / "registration.json")
    c.require(
        r["schema"] == "cells.betse_timed_release_registration@1", "Timed registration schema"
    )
    validate_plan(r["plan"])
    c.require(
        r["prerequisite"] == prerequisite() and r["views"] == views(r["plan"]),
        "Timed inputs changed",
    )
    c.require(
        r["sources_sha256"] == sources() and r["historical_reports_sha256"] == reports(),
        "Timed sources/reports changed",
    )
    c.require(
        r["tests"] == test_receipt([ROOT / row["path"] for row in r["tests"]["receipts"]]),
        "Timed software receipt changed",
    )
    with zipfile.ZipFile(output / "sources.zip") as archive:
        names = archive.namelist()
        c.require(
            len(names) == len(set(names)) and set(names) == set(r["sources_sha256"]),
            "Timed capsule membership",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == h
                for n, h in r["sources_sha256"].items()
            ),
            "Timed capsule bytes",
        )
    return r
