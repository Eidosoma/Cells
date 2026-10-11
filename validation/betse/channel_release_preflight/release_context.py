"""D102 source-bound native input preflight; previous evidence is immutable."""

import copy
import hashlib
import importlib
import json
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "channel_release_design"))
design = importlib.import_module("release_design")
audit = design.audit
c, io, ROOT = design.c, design.io, design.ROOT
PLAN = HERE / "plan.json"
MANIFEST = ROOT / "reports/ref-004d-release-design-source-manifest.json"
MANIFEST_SHA256 = "c4148a2988251270633f0bbf236e7737f22abd3c9133af82eaa88491633ffd93"
NEW_SOURCES = tuple(
    "validation/betse/channel_release_preflight/" + name
    for name in (
        "plan.json",
        "release_context.py",
        "release_input.py",
        "release_native.py",
        "release_check.py",
        "release_job.py",
        "test_release_preflight.py",
    )
) + ("docs/BETSE_CHANNEL_RELEASE_PREFLIGHT.md",)


def validate_plan(plan):
    c.require(
        json.dumps(plan, sort_keys=True, allow_nan=False)
        == json.dumps(c.read(PLAN), sort_keys=True, allow_nan=False),
        "Unregistered release preflight",
    )
    d = c.read(design.PLAN)
    design.validate_plan(d)
    c.require(
        plan["decision"] == "D102"
        and plan["schema"] == "cells.betse_channel_release_preflight_plan@1"
        and plan["histories"] == d["histories"]
        and plan["conditions"] == d["conditions"]
        and plan["native_steps_s"] == d["native_steps_s"]
        and plan["protocol_query_times_s"] == d["probe_times_s"],
        "Release preflight differs from design",
    )
    n = len(plan["histories"]) * len(plan["native_steps_s"])
    pairs = n * len(plan["conditions"]) * len(plan["protocol_query_times_s"])
    c.require(
        plan["modes"] == ["observed", "unobserved"]
        and plan["geometry_seeds"] == n == 6
        and plan["observer_pairs"] == pairs == 72
        and plan["fresh_phases"] == 2 * pairs == 144
        and plan["single_updates"] == 4 * pairs == 288
        and plan["input_applications"] == 2 * n * len(plan["conditions"]) * sum(range(1, 4)) == 288,
        "Wrong release preflight counts",
    )
    for key in (
        "protocol_query_time_is_simulated_elapsed_time",
        "full_simulator_loop_executed",
        "cells_trajectory_executed",
        "reference_integration_executed",
        "release_response_qualified",
        "production_changed",
        "automatic_polling",
        "automatic_retry",
        "automatic_followup",
    ):
        c.require(plan[key] is False, "Unexpected expanded scope: " + key)


def design_evidence():
    c.require(c.sha(MANIFEST) == MANIFEST_SHA256, "Frozen design manifest changed")
    manifest = c.read(MANIFEST)
    c.require(manifest["decision"] == "D101", "Wrong design manifest")
    for name, digest in manifest["design_inputs_sha256"].items():
        c.require(c.sha(ROOT / name) == digest, "Executed design input changed: " + name)
    for row, path_key, hash_key in (
        (manifest["tests"], "path", "sha256"),
        (manifest["prerequisite"], "path", "sha256"),
        (manifest["prerequisite"], "report", "report_sha256"),
    ):
        c.require(c.sha(ROOT / row[path_key]) == row[hash_key], "Design evidence changed")
    c.require(
        manifest["tests"]["passed"] == 107
        and manifest["tests"]["failed"]
        == manifest["tests"]["errors"]
        == manifest["tests"]["skipped"]
        == 0,
        "Design software did not pass",
    )
    return {"manifest_sha256": c.sha(MANIFEST), "manifest": manifest}


def sources():
    return (
        audit.sources()
        | design_evidence()["manifest"]["design_inputs_sha256"]
        | {name: c.sha(ROOT / name) for name in NEW_SOURCES}
    )


def data():
    result = {}
    for history in c.read(PLAN)["histories"]:
        view = design.view(history)
        result[history] = {
            "preparation_registration": copy.deepcopy(view["preparation_registration"]),
            "geometry": view["geometry"],
            "settings": view["native_settings"]["active_channel"],
            "initial_gate": view["protocol"]["initial_gate"],
            "saved_initial": {},
            "saved_metadata": {},
            "saved_labels": {},
        }
        for step in c.read(PLAN)["native_steps_s"]:
            record = io.read_compressed(
                audit.CAPTURE
                / history
                / f"native/active_channel/dt_{step:.8g}/observed/result.json.gz"
            )
            key = f"{step:.8g}"
            result[history]["saved_initial"][key] = record["trace"]["initial"]
            result[history]["saved_metadata"][key] = record["fixture"]["metadata"]
            result[history]["saved_labels"][key] = record["trace"]["labels_s"]
    return result


def test_receipt(path):
    c.require(path.is_relative_to(ROOT / "reports") and path.is_file(), "Missing software XML")
    tree = ET.parse(path).getroot()
    suites = [tree] if tree.tag == "testsuite" else list(tree.findall("testsuite"))
    names = []
    for suite in suites:
        rows = list(suite.findall("testcase"))
        c.require(
            len(rows) == int(suite.attrib["tests"])
            and all(int(suite.attrib.get(k, 0)) == 0 for k in ("failures", "errors", "skipped")),
            "Incomplete or failed preflight tests",
        )
        for row in rows:
            c.require(
                not any(row.find(k) is not None for k in ("failure", "error", "skipped")),
                "Failed test",
            )
            names.append(row.attrib["classname"] + "::" + row.attrib["name"])
    c.require(
        len(names) >= 40
        and len(set(names)) == len(names)
        and all("channel_release_preflight.test_release_preflight::" in n for n in names),
        "Wrong preflight software coverage",
    )
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": c.sha(path),
        "tests": len(names),
        "identities": sorted(names),
    }


def reports():
    names = [
        "reports/REF004C_PAIRED_HISTORY_CLOSEOUT.md",
        "reports/REF004D_RELEASE_DESIGN_CHECK.md",
        "reports/ref-004d-release-design-source-manifest.json",
        "reports/ref-004d-release-design-checks-01.xml",
        "reports/REF004D_RELEASE_PREFLIGHT_HANDOFF.md",
        "reports/ref-004d-release-preflight-checks-01.xml",
        "reports/ref-004d-release-preflight-checks-02.xml",
        "reports/ref-004d-release-preflight-checks-03.xml",
        "reports/ref-004d-release-preflight-checks-04.xml",
        "reports/ref-004d-release-preflight-checks-05.xml",
        "reports/ref-004d-release-preflight-checks-06.xml",
    ]
    return {name: c.sha(ROOT / name) for name in names}


def authenticate(output):
    r = c.read(output / "registration.json")
    c.require(
        r["schema"] == "cells.betse_channel_release_preflight_registration@1", "Wrong registration"
    )
    validate_plan(r["plan"])
    c.require(r["design_evidence"] == design_evidence(), "Design evidence differs")
    c.require(r["sources_sha256"] == sources(), "Release preflight sources changed")
    c.require(r["historical_reports_sha256"] == reports(), "Historical reports changed")
    c.require(r["data"] == data(), "Release preparation changed")
    c.require(r["tests"] == test_receipt(ROOT / r["tests"]["path"]), "Preflight software changed")
    c.require(r["prerequisite"] == design.prerequisite(), "Paired prerequisite changed")
    with zipfile.ZipFile(output / "sources.zip") as archive:
        names = archive.namelist()
        c.require(
            len(names) == len(set(names)) and set(names) == set(r["sources_sha256"]),
            "Source capsule membership",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == h
                for n, h in r["sources_sha256"].items()
            ),
            "Source capsule bytes",
        )
    return r
