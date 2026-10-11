"""Immutable paired settings over audited production interfaces; no global patches."""

import copy
import hashlib
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import preparation_review as review

c, io, ROOT = review.c, review.io, review.ROOT
previous = review.previous
feedback = previous.prior.pilot
HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "protocol.json"
FILES = tuple(
    "validation/betse/channel_history_pilot/" + name
    for name in (
        "protocol.json",
        "paired_context.py",
        "paired_reference.py",
        "paired_reference_check.py",
        "paired_native_check.py",
        "paired_cells_check.py",
        "paired_workers.py",
        "paired_compare.py",
        "paired_job.py",
        "test_paired_history.py",
    )
) + ("docs/BETSE_CHANNEL_HISTORY_PILOT.md",)


def sources():
    return review.sources() | {name: c.sha(ROOT / name) for name in FILES}


def validate_protocol(p):
    c.require(p == c.read(PROTOCOL), "Unregistered paired protocol")
    c.require(
        p["schema"] == "cells.betse_paired_history_protocol@1" and p["decision"] == "D099",
        "Wrong paired protocol",
    )
    c.require(
        p["histories"] == {"a": [0.2, 0.6], "b": [0.6, 0.2]}
        and p["variants"] == ["active_channel", "blocked_channel"],
        "Paired settings differ",
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
        "Unexpected automatic work",
    )
    c.require(
        p["candidate_duration_s"] == 0.002
        and p["native_runs"] == 24
        and p["cells_trajectories"] == 16
        and p["reference_solves"] == 12,
        "Paired scope changed",
    )


def views(p):
    saved = c.read(previous.prior.CAPTURE / "registration.json")
    prepared = c.read(review.CAPTURE / "registration.json")["data"]
    result = {}
    for name, gates in p["histories"].items():
        numeric = copy.deepcopy(saved["protocol"])
        numeric.update(
            {
                "schema": "cells.betse_paired_history_numeric_view@1",
                "variants": p["variants"],
                "initial_gate": gates,
                "duration_s": p["candidate_duration_s"],
                "common_times_s": p["common_times_s"],
                "native_steps_s": p["native_steps_s"],
                "cells_steps_s": p["cells_steps_s"],
            }
        )
        numeric["resources"].update(p["resources"])
        count = len(p["variants"])
        numeric.update(
            {
                "native_pairs": count * len(p["native_steps_s"]),
                "native_runs": 2 * count * len(p["native_steps_s"]),
                "native_updates": 2
                * count
                * sum(round(p["candidate_duration_s"] / h) for h in p["native_steps_s"]),
                "cells_trajectories": count * (len(p["cells_steps_s"]) + 1),
                "cells_resumed_segments": count,
            }
        )
        prep = copy.deepcopy(saved["preparation_registration"])
        prep["protocol"]["initial_gate"] = gates
        prep["transport_protocol"]["variants"] = [
            v for v in prep["transport_protocol"]["variants"] if v["id"] in p["variants"]
        ]
        definitions = {}
        for variant in p["variants"]:
            for step in p["cells_steps_s"]:
                definition = copy.deepcopy(prepared["definitions"][variant + "/" + name])
                definition["execution"]["dt"] = step
                definitions[feedback.key(variant, step, "jax_jit")] = definition
            definition = copy.deepcopy(
                definitions[feedback.key(variant, numeric["cells_eager_step_s"], "jax_jit")]
            )
            definition["execution"]["jit"] = False
            definitions[feedback.key(variant, numeric["cells_eager_step_s"], "jax_eager")] = (
                definition
            )
        result[name] = {
            "history_id": name,
            "protocol": numeric,
            "preparation_registration": prep,
            "geometry": saved["geometry"],
            "native_settings": {v: saved["native_settings"][v] for v in p["variants"]},
            "reference_parameters": {v: saved["reference_parameters"][v] for v in p["variants"]},
            "cells_definitions": definitions,
        }
    return result


def test_receipt(path):
    c.require(path.is_file() and path.is_relative_to(ROOT / "reports"), "Missing paired tests")
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    names = []
    for suite in suites:
        rows = list(suite.findall("testcase"))
        c.require(
            len(rows) == int(suite.attrib["tests"])
            and all(int(suite.attrib.get(k, 0)) == 0 for k in ("failures", "errors", "skipped")),
            "Incomplete paired tests",
        )
        for row in rows:
            c.require(
                not any(row.find(k) is not None for k in ("failure", "error", "skipped")),
                "Rejected paired software test",
            )
            names.append(row.attrib["classname"] + "::" + row.attrib["name"])
    c.require(
        len(names) >= 30
        and len(names) == len(set(names))
        and all("channel_history_pilot.test_paired_history::" in n for n in names),
        "Missing paired software coverage",
    )
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": c.sha(path),
        "tests": len(names),
        "identities": sorted(names),
    }


def authenticate(output):
    r = c.read(output / "registration.json")
    c.require(r["schema"] == "cells.betse_paired_history_registration@1", "Wrong registration")
    validate_protocol(r["protocol"])
    with previous.prior.model_fence():
        prerequisite, _prepared = review.authenticate_review()
    c.require(
        r["prerequisite"] == prerequisite and r["sources_sha256"] == sources(),
        "Paired inputs or review changed",
    )
    c.require(r["views"] == views(r["protocol"]), "Paired physical or numeric settings changed")
    c.require(r["reference_runtime"] == feedback.reference_runtime(), "Reference runtime changed")
    c.require(r["tests"] == test_receipt(ROOT / r["tests"]["path"]), "Paired tests changed")
    with zipfile.ZipFile(output / "sources.zip") as archive:
        names = archive.namelist()
        c.require(
            len(names) == len(set(names)) and set(names) == set(r["sources_sha256"]),
            "Paired capsule membership",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == h
                for n, h in r["sources_sha256"].items()
            ),
            "Paired capsule bytes",
        )
    return r
