"""Versioned D095 definitions/provenance, preserving all accepted implementations."""

import copy
import importlib
import importlib.metadata
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "channel_loop_audit"))
audit = importlib.import_module("loop_audit_context")
audit_job = importlib.import_module("loop_audit_job")
c = audit.c
ROOT = c.ROOT
PROTOCOL = HERE / "protocol.json"
PRIOR = ROOT / "runs/ref-004b-loop-audit-2026-09-14/audit-01"
PRIOR_SHA = "8ec513d8171ebf3a6670ae270f66fed1821ff4caf66670076c3e4bc03ef5c391"
REFERENCE_PYTHON = ROOT / ".reference-venv/bin/python"
FILES = tuple(
    "validation/betse/channel_feedback_pilot/" + name
    for name in (
        "protocol.json",
        "feedback_context.py",
        "feedback_io.py",
        "feedback_reference.py",
        "feedback_reference_check.py",
        "feedback_native.py",
        "feedback_cells.py",
        "feedback_compare.py",
        "feedback_job.py",
        "test_feedback_pilot.py",
    )
) + ("docs/BETSE_CHANNEL_FEEDBACK_PILOT.md",)


def sources():
    return {name: c.sha(ROOT / name) for name in sorted(set(audit.sources()) | set(FILES))}


def prerequisite():
    c.require(c.sha(PRIOR / "completion.json") == PRIOR_SHA, "Preparation audit changed")
    done = c.read(PRIOR / "completion.json")
    c.require(
        done["status"] == "loop_preparation_audit_closed"
        and done["preparation_readiness_qualified"] is True
        and done["independent_comparisons"] == 74092
        and done["failed_comparisons"] == 0,
        "Preparation/readiness is not independently qualified",
    )
    audit_job.authenticate(PRIOR)  # Source/receipt authentication only, no numerical replay.
    hashes = audit.packet_hashes(PRIOR)
    c.require(
        set(hashes) == set(done["files_sha256"]) | audit.OPERATIONAL | {"completion.json"}
        and all(hashes[n] == h for n, h in done["files_sha256"].items()),
        "Preparation audit packet changed",
    )
    prior = audit.capture_job.authenticate(audit.CAPTURE)
    c.require(
        c.authenticate_cells()["runtime"] == prior["cells_runtime"], "Accepted production differs"
    )
    return {
        "path": str(PRIOR.relative_to(ROOT)),
        "files_sha256": hashes,
        "preparation_files_sha256": audit.packet_hashes(audit.CAPTURE),
    }, prior


def reference_runtime():
    site = REFERENCE_PYTHON.parent.parent / "lib/python3.13/site-packages"
    packages = {
        dist.metadata["Name"]: dist.version
        for dist in importlib.metadata.distributions(path=[str(site)])
    }
    c.require(
        packages.get("numpy") == "2.5.3"
        and packages.get("scipy") == "1.18.1"
        and "jax" not in packages,
        "Independent reference environment differs",
    )
    modules = {
        str(p.relative_to(site)): c.sha(p)
        for p in sorted((site / "scipy/integrate/_ivp").glob("*.py"))
    }
    c.require(len(modules) >= 8, "Missing independent solver sources")
    return {
        "executable": str(REFERENCE_PYTHON),
        "packages": packages,
        "ivp_sources_sha256": modules,
        "python": "3.13.5",
        "platform": "Linux",
        "precision": "float64",
    }


def validate_protocol(p):
    c.require(p == c.read(PROTOCOL), "Unregistered feedback protocol")
    c.require(
        p["schema"] == "cells.betse_channel_feedback_protocol@1"
        and p["prior_completion_sha256"] == PRIOR_SHA,
        "Feedback prerequisite differs",
    )
    c.require(
        p["duration_s"] == 0.002 and p["initial_gate"] == [0.2, 0.6], "Feedback fixture differs"
    )
    c.require(p["variants"] == list(audit.independent.VARIANTS), "Feedback controls differ")
    c.require(
        p["native_steps_s"] == [25e-6, 12.5e-6, 6.25e-6]
        and p["cells_steps_s"] == [50e-6, 25e-6, 12.5e-6],
        "Feedback grids differ",
    )
    c.require(
        p["reference_gate_before_simulators"] is True
        and all(
            p[k] is False
            for k in (
                "production_changed",
                "automatic_polling",
                "automatic_retry",
                "automatic_followup",
            )
        ),
        "Unregistered automatic work",
    )
    c.require(
        p["resources"]["cpu_affinity"] == [0, 1, 2, 3]
        and p["resources"]["total_timeout_seconds"] == 900,
        "Feedback resources differ",
    )


def key(variant, step, backend=None):
    return variant + ("/" + backend if backend else "") + f"/dt_{step:.8g}"


def cells_definitions(p):
    saved = c.read(audit.CAPTURE / "pilot-candidate-definitions.json")
    definitions = {}
    for variant in p["variants"]:
        for step in p["cells_steps_s"]:
            definition = copy.deepcopy(saved[variant + f"/dt_{step:.8g}"])
            c.require(
                definition["experiment"]["end_time"] == p["duration_s"]
                and definition["experiment"]["observation_times"] == p["common_times_s"],
                "Readiness horizon changed",
            )
            definitions[key(variant, step, "jax_jit")] = definition
        eager = copy.deepcopy(saved[variant + f"/dt_{p['cells_eager_step_s']:.8g}"])
        eager["execution"]["jit"] = False
        definitions[key(variant, p["cells_eager_step_s"], "jax_eager")] = eager
    return definitions


def parameters():
    saved = c.read(audit.CAPTURE / "cells.json")["records"]
    return {
        v: next(row["independent_parameters"] for row in saved if row["id"] == v + "/dt_5e-05")
        for v in audit.independent.VARIANTS
    }


def loop_registration(r, step):
    result = copy.deepcopy(r["preparation_registration"])
    steps = round(r["protocol"]["duration_s"] / step)
    result["protocol"].update(
        {
            "schema": "cells.betse_channel_feedback_loop_view@1",
            "dt_s": step,
            "duration_s": r["protocol"]["duration_s"],
            "steps": steps,
            "observed_steps": 4 * steps,
        }
    )
    return result


def test_receipt(path):
    c.require(path.is_file() and path.is_relative_to(ROOT / "reports"), "Missing feedback test XML")
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    identities = []
    for suite in suites:
        rows = list(suite.findall("testcase"))
        c.require(
            len(rows) == int(suite.attrib["tests"])
            and all(int(suite.attrib.get(k, 0)) == 0 for k in ("failures", "errors", "skipped")),
            "Incomplete feedback preflight",
        )
        for row in rows:
            c.require(
                not any(row.find(k) is not None for k in ("failure", "error", "skipped")),
                "Rejected software preflight",
            )
            identities.append(row.attrib["classname"] + "::" + row.attrib["name"])
    original = c.read(audit.CAPTURE / "registration.json")["tests"]["identities"]
    added = set(identities) - set(original)
    c.require(
        len(identities) == len(set(identities))
        and len(original) == 96
        and set(original) <= set(identities),
        "Preparation software coverage changed",
    )
    c.require(
        len(added) >= 40
        and all("channel_feedback_pilot.test_feedback_pilot::" in n for n in added),
        "Feedback software coverage incomplete",
    )
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": c.sha(path),
        "tests": len(identities),
        "previous_tests": 96,
        "new_tests": len(added),
        "identities": sorted(identities),
    }
