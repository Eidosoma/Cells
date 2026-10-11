"""Source-bound data variants for a history challenge, not a new cell model."""

import copy
import hashlib
import importlib
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "channel_feedback_audit"))
prior_job = importlib.import_module("feedback_audit_job")
prior = prior_job.ctx
c, io, ROOT = prior.c, prior.io, prior.ROOT
PLAN = HERE / "plan.json"
PRIOR = ROOT / "runs/ref-004b-feedback-audit-2026-09-15/audit-01"
PRIOR_SHA = "61e700cbddda5141f92443ba684bf344d14d09e1b3c9db12110d1a0a923a28b9"
NEW_FILES = tuple(
    "validation/betse/channel_history_preflight/" + name
    for name in (
        "plan.json",
        "history_context.py",
        "history_math.py",
        "history_workers.py",
        "history_check.py",
        "history_job.py",
        "test_history_preflight.py",
    )
) + ("docs/BETSE_CHANNEL_HISTORY_PREFLIGHT.md",)


def sources():
    return {name: c.sha(ROOT / name) for name in sorted(set(prior.sources()) | set(NEW_FILES))}


def validate_plan(plan):
    c.require(plan == c.read(PLAN), "Unregistered history plan")
    c.require(
        plan["schema"] == "cells.betse_channel_history_preflight_plan@1"
        and plan["decision"] == "D097"
        and plan["prerequisite_completion_sha256"] == PRIOR_SHA,
        "Wrong history prerequisite",
    )
    c.require(
        plan["histories"] == {"a": [0.2, 0.6], "b": [0.6, 0.2]}
        and plan["variants"] == ["active_channel", "blocked_channel"]
        and plan["backends"] == ["numpy", "jax_eager", "jax_jit"],
        "History panel changed",
    )
    c.require(
        all(
            plan[name] is False
            for name in (
                "production_changed",
                "coupled_trajectories_run",
                "reference_integration_run",
                "automatic_polling",
                "automatic_retry",
                "automatic_followup",
            )
        ),
        "Unexpected production, integration or automatic work",
    )


def prerequisite():
    """Authenticate completed evidence without numerical replay or model imports."""
    c.require(c.sha(PRIOR / "completion.json") == PRIOR_SHA, "Coupled closeout changed")
    with prior.model_fence():
        prior_job.authenticate(PRIOR)
        capture = prior.load_capture()
    done = c.read(PRIOR / "completion.json")
    hashes = prior.packet_hashes(PRIOR)
    c.require(
        done["status"] == "coupled_feedback_pilot_audit_closed"
        and done["coupled_trajectory_qualified"] is True
        and done["independent_column_mismatches"] == 0,
        "Coupled pilot is not closed",
    )
    c.require(
        set(hashes) == set(done["files_sha256"]) | prior.OPERATIONAL | {"completion.json"}
        and all(hashes[name] == digest for name, digest in done["files_sha256"].items()),
        "Coupled closeout packet changed",
    )
    return {
        "audit_files_sha256": hashes,
        "capture_files_sha256": capture["hashes"],
        "audit_tests": done["tests"],
    }


def data(plan):
    """Only initial_gate differs within each paired configuration."""
    saved = c.read(prior.CAPTURE / "registration.json")
    definitions = {}
    for variant in plan["variants"]:
        base = saved["cells_definitions"][variant + "/jax_jit/dt_5e-05"]
        for name, gates in plan["histories"].items():
            definition = copy.deepcopy(base)
            for entry in definition["model"]["cells"]:
                entry["channel"]["initial_gate"] = dict(zip(("m", "h"), gates, strict=True))
            definitions[variant + "/" + name] = definition
    return {
        "definitions": definitions,
        "parameters": {v: saved["reference_parameters"][v] for v in plan["variants"]},
        "native_voltage_V": saved["reference_parameters"]["active_channel"]["initial_voltage_V"],
        "cells_runtime": saved["preparation_registration"]["cells_runtime"],
        "upstream": saved["preparation_registration"]["upstream"],
    }


def test_receipt(path):
    c.require(path.is_relative_to(ROOT / "reports") and path.is_file(), "Missing history tests")
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    names = []
    for suite in suites:
        rows = list(suite.findall("testcase"))
        c.require(
            len(rows) == int(suite.attrib["tests"])
            and all(int(suite.attrib.get(k, 0)) == 0 for k in ("failures", "errors", "skipped")),
            "Incomplete history tests",
        )
        for row in rows:
            c.require(
                not any(row.find(k) is not None for k in ("failure", "error", "skipped")),
                "Rejected history test",
            )
            names.append(row.attrib["classname"] + "::" + row.attrib["name"])
    c.require(
        len(names) >= 30
        and len(names) == len(set(names))
        and all("channel_history_preflight.test_history_preflight::" in n for n in names),
        "Missing or duplicated history software coverage",
    )
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": c.sha(path),
        "tests": len(names),
        "identities": sorted(names),
    }


def authenticate(output):
    r = c.read(output / "registration.json")
    c.require(r["schema"] == "cells.betse_channel_history_registration@1", "Wrong registration")
    validate_plan(r["plan"])
    c.require(r["prerequisite"] == prerequisite(), "Prerequisite packet changed")
    c.require(r["sources_sha256"] == sources(), "History source inputs changed")
    c.require(r["data"] == data(r["plan"]), "History settings changed")
    c.require(r["tests"] == test_receipt(ROOT / r["tests"]["path"]), "History tests changed")
    with zipfile.ZipFile(output / "sources.zip") as archive:
        names = archive.namelist()
        c.require(
            len(names) == len(set(names)) and set(names) == set(r["sources_sha256"]),
            "History source capsule membership",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == h
                for n, h in r["sources_sha256"].items()
            ),
            "History source capsule bytes",
        )
    return r
