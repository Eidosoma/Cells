"""D104 frozen prerequisites and reference-only scope; stdlib authentication."""

import hashlib
import importlib
import json
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "channel_release_review"))
previous = importlib.import_module("review_context")
feedback = importlib.import_module("feedback_context")
c, io, ROOT = previous.c, previous.io, previous.ROOT
design = previous.previous.design
model_fence, packet_hashes = previous.model_fence, previous.packet_hashes
OPERATIONAL = previous.previous.audit.OPERATIONAL
PLAN = HERE / "plan.json"
PRIOR = ROOT / "runs/ref-004d-release-review-2026-09-15/review-01"
PRIOR_SHA = "a3660e211dbd5cd2e2e6389d8a0ff46d15019842dd620a4114016157af5152ad"
FILES = tuple(
    "validation/betse/channel_release_reference/" + name
    for name in (
        "plan.json",
        "piecewise_context.py",
        "piecewise_reference.py",
        "piecewise_check.py",
        "piecewise_job.py",
        "test_release_reference.py",
    )
) + ("docs/BETSE_CHANNEL_RELEASE_REFERENCE.md",)


def validate_plan(plan):
    c.require(
        json.dumps(plan, sort_keys=True, allow_nan=False)
        == json.dumps(c.read(PLAN), sort_keys=True, allow_nan=False),
        "Unregistered piecewise reference plan",
    )
    c.require(
        plan["schema"] == "cells.betse_release_reference_plan@1"
        and plan["decision"] == "D104"
        and plan["prerequisite_completion_sha256"] == PRIOR_SHA
        and plan["histories"] == {"a": [0.2, 0.6], "b": [0.6, 0.2]}
        and plan["conditions"] == list(design.CONDITIONS)
        and plan["reference_paths"] == 24
        and plan["segment_integrations"] == 48,
        "Reference scope differs",
    )
    old = c.read(design.PLAN)
    c.require(
        all(plan[k] == old[k] for k in ("duration_s", "block_time_s", "release_time_s")),
        "Reference window differs from the prospective design",
    )
    for key in (
        "simulator_execution_allowed",
        "production_changed",
        "release_response_qualified",
        "biology_validated",
        "gpu_tested",
        "automatic_polling",
        "automatic_retry",
        "automatic_followup",
    ):
        c.require(plan[key] is False, "Expanded reference scope: " + key)


def prerequisite():
    c.require(c.sha(PRIOR / "completion.json") == PRIOR_SHA, "Input closeout changed")
    with model_fence():
        r = previous.authenticate(PRIOR)
    done, hashes = c.read(PRIOR / "completion.json"), packet_hashes(PRIOR)
    c.require(
        done["status"] == "release_input_preflight_review_closed"
        and done["native_input_single_update_scope_qualified"] is True
        and done["comparisons"] == 916176
        and done["failed_comparisons"] == 0
        and done["original_guard_rejections_preserved"] == 104
        and done["release_response_qualified"] is False,
        "Native input prerequisite is not closed at the required scope",
    )
    c.require(
        set(hashes) == set(done["files_sha256"]) | OPERATIONAL | {"completion.json"}
        and all(hashes[n] == h for n, h in done["files_sha256"].items())
        and done["registration_sha256"] == c.sha(PRIOR / "registration.json")
        and done["tests"] == r["tests"],
        "Input closeout packet changed",
    )
    return {"path": str(PRIOR.relative_to(ROOT)), "files_sha256": hashes}


def inputs(plan):
    """Use positive intrinsic permeability for ALL conditions; input is separate."""
    views = {h: design.view(h) for h in plan["histories"]}
    parameters = {h: v["reference_parameters"]["active_channel"] for h, v in views.items()}
    reference = views["a"]["protocol"]["reference"]
    trajectory = views["a"]["protocol"]["trajectory_absolute"]
    c.require(
        all(v["protocol"]["reference"] == reference for v in views.values())
        and reference["sample_dt_s"] == plan["sample_dt_s"]
        and all(all(p > 0 for p in v["Pmax_m_per_s"]) for v in parameters.values()),
        "Reference settings or intrinsic channel differ",
    )
    signal = plan["signal"]
    for field, unit in (
        ("minimum_block_effect_V", "voltage_V"),
        ("minimum_post_release_voltage_change_V", "voltage_V"),
        ("minimum_release_flux_fmol_per_s", "flux_fmol_per_s"),
        ("minimum_block_gate_change", "gate"),
    ):
        c.require(signal[field] == signal["budget_multiplier"] * trajectory[unit], "Signal budget")
    return {
        "parameters": parameters,
        "reference": reference,
        "comparison_relative": views["a"]["protocol"]["comparison_relative"],
        "trajectory_absolute_for_signal_only": trajectory,
        "schedules": {
            name: design.schedule(c.read(design.PLAN), name) for name in plan["conditions"]
        },
    }


def sources():
    return previous.sources() | {name: c.sha(ROOT / name) for name in FILES}


def reports():
    return previous.reports() | {
        name: c.sha(ROOT / name)
        for name in (
            "reports/ref-004d-release-review-checks-02.xml",
            "reports/ref-004d-release-reference-checks-01.xml",
            "reports/REF004D_RELEASE_INPUT_CLOSEOUT.md",
            "reports/REF004D_RELEASE_REFERENCE_HANDOFF.md",
        )
    }


def test_receipt(path):
    c.require(path.is_file() and path.is_relative_to(ROOT / "reports"), "Missing reference XML")
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    names = []
    for suite in suites:
        rows = list(suite.findall("testcase"))
        c.require(
            len(rows) == int(suite.attrib["tests"])
            and all(int(suite.attrib.get(k, 0)) == 0 for k in ("failures", "errors", "skipped")),
            "Incomplete reference software tests",
        )
        for row in rows:
            c.require(
                not any(row.find(k) is not None for k in ("failure", "error", "skipped")),
                "Failed reference software test",
            )
            names.append(row.attrib["classname"] + "::" + row.attrib["name"])
    c.require(
        len(names) >= 40
        and len(names) == len(set(names))
        and all("channel_release_reference.test_release_reference::" in n for n in names),
        "Missing reference software coverage",
    )
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": c.sha(path),
        "tests": len(names),
        "identities": sorted(names),
    }


def authenticate(output):
    r = c.read(output / "registration.json")
    c.require(r["schema"] == "cells.betse_release_reference_registration@1", "Reference schema")
    validate_plan(r["plan"])
    c.require(r["prerequisite"] == prerequisite(), "Reference prerequisite changed")
    c.require(r["inputs"] == inputs(r["plan"]), "Reference input settings changed")
    c.require(r["reference_runtime"] == feedback.reference_runtime(), "Reference runtime changed")
    c.require(r["sources_sha256"] == sources(), "Reference sources changed")
    c.require(r["historical_reports_sha256"] == reports(), "Reference reports changed")
    c.require(r["tests"] == test_receipt(ROOT / r["tests"]["path"]), "Reference software changed")
    with zipfile.ZipFile(output / "sources.zip") as archive:
        names = archive.namelist()
        c.require(
            len(names) == len(set(names)) and set(names) == set(r["sources_sha256"]),
            "Reference capsule membership",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == h
                for n, h in r["sources_sha256"].items()
            ),
            "Reference capsule bytes",
        )
    return r
