"""D098: close saved initial-history preparation, never run either simulator."""

import argparse
import hashlib
import importlib
import json
import struct
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "channel_history_preflight"))
previous = importlib.import_module("history_context")
job = importlib.import_module("history_job")
checker = importlib.import_module("history_check")
assembly = importlib.import_module("history_math")
checkpoint = importlib.import_module("feedback_audit_cells")
field = importlib.import_module("pilot_reference")
c, io, ROOT = previous.c, previous.io, previous.ROOT
CAPTURE = ROOT / "runs/ref-004c-history-preflight-2026-09-15/capture-01"
CAPTURE_SHA = "8b673c1797f87bdb8a4f139c8e362f6cb2289634707eb01d321d571fa0d2f928"
REVIEW = ROOT / "runs/ref-004c-history-review-2026-09-15/review-01"
FILES = ("preparation_review.py", "test_preparation_review.py")


def sources():
    return previous.sources() | {
        str((HERE / name).relative_to(ROOT)): c.sha(HERE / name) for name in FILES
    }


def load():
    c.require(c.sha(CAPTURE / "completion.json") == CAPTURE_SHA, "History capture changed")
    r = previous.authenticate(CAPTURE)
    done, hashes = c.read(CAPTURE / "completion.json"), previous.prior.packet_hashes(CAPTURE)
    c.require(
        done["status"] == "history_preflight_pass_pending_review"
        and done["comparisons"] == 2442
        and done["failed_comparisons"] == 0,
        "History preparation did not pass",
    )
    c.require(
        set(hashes) == set(done["files_sha256"]) | previous.prior.OPERATIONAL | {"completion.json"}
        and all(hashes[n] == h for n, h in done["files_sha256"].items()),
        "History packet changed",
    )
    native, cells = (job.validate_worker(CAPTURE, r, name) for name in ("betse", "cells"))
    c.require(done["tests"] == r["tests"], "Original history software receipt changed")
    return r, native, cells, hashes


def numeric_digest(record):
    codes = {"<f8": "d", "<i8": "q", "|b1": "?"}
    c.require(record["dtype"] in codes, "Unexpected checkpoint dtype")
    digest = hashlib.sha256()

    def add(value):
        if isinstance(value, list):
            for item in value:
                add(item)
        else:
            digest.update(struct.pack("<" + codes[record["dtype"]], value))

    add(record["values"])
    return digest.hexdigest()


def independent_checks(r, cells):
    """Alternate audited vector field plus exact links to audited full layouts."""
    ledger = io.Ledger(r["plan"]["absolute"], r["plan"]["relative"])
    layout_arrays = 0
    layouts = {}
    for variant in r["plan"]["variants"]:
        directory = previous.prior.CAPTURE / "cells" / variant / "jax_jit/dt_5e-05/final-checkpoint"
        decoded = checkpoint.decode_npz(directory / "state.npz")
        layouts[variant] = {
            n: numeric_digest(v) for n, v in decoded.items() if n not in assembly.ready.STATE_SHAPES
        }
    for identifier, definition in r["data"]["definitions"].items():
        variant, history = identifier.split("/")
        p, gates = r["data"]["parameters"][variant], r["plan"]["histories"][history]
        n = len(p["volume_pL"])
        rates = field.rates(p, [0.0] * n, [gates[0]] * n, [gates[1]] * n)
        expected_state, expected_rhs = assembly.expected_arrays(definition, rates)
        for backend in r["plan"]["backends"]:
            key = identifier + "/" + backend
            row = cells["rows"][key]
            c.require(row["layout_sha256"] == layouts[variant], "Audited full layout differs")
            layout_arrays += len(layouts[variant])
            for name, expected in expected_rhs.items():
                c.require(
                    checker.values(row["state"][name]) == expected_state[name], "Initial state"
                )
                unit = (
                    "gate_rate_per_s"
                    if name == "gate"
                    else ("power_pJ_per_s" if "energy" in name else "flux_fmol_per_s")
                )
                ledger.compare(key + "/" + name, checker.values(row["rhs"][name]), expected, unit)
            # Rebuild the opening slope without using D097's open_rate function.
            dm, dh = rates["gate_rate_per_s"]
            actual = [gates[1] * a + gates[0] * b for a, b in zip(dm, dh, strict=True)]
            prior_rates = assembly.initial_rates(p, gates)["gate_rate_per_s"]
            expected = [gates[1] * a + gates[0] * b for a, b in zip(*prior_rates, strict=True)]
            ledger.compare(key + "/opening_slope", actual, expected, "open_rate_per_s")
    c.require(ledger.failed == 0, "Alternate initial-rate reconstruction failed")
    return ledger.summary() | {"full_layout_arrays": layout_arrays}


def tests(path):
    c.require(path.is_relative_to(ROOT / "reports") and path.is_file(), "Missing review tests")
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    names = []
    for suite in suites:
        rows = list(suite.findall("testcase"))
        c.require(
            len(rows) == int(suite.attrib["tests"])
            and all(int(suite.attrib.get(k, 0)) == 0 for k in ("failures", "errors", "skipped")),
            "Incomplete review tests",
        )
        for row in rows:
            c.require(
                not any(row.find(k) is not None for k in ("failure", "error", "skipped")),
                "Rejected review test",
            )
            names.append(row.attrib["classname"] + "::" + row.attrib["name"])
    c.require(
        len(names) >= 10 and len(names) == len(set(names)), "Missing review software coverage"
    )
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": c.sha(path),
        "tests": len(names),
        "identities": sorted(names),
    }


def authenticate_review():
    r, _native, _cells, hashes = load()
    done = c.read(REVIEW / "completion.json")
    c.require(
        done["status"] == "history_preparation_review_closed"
        and done["capture_sha256"] == hashes
        and done["sources_sha256"] == sources()
        and done["tests"] == tests(ROOT / done["tests"]["path"]),
        "Review identity changed",
    )
    packet = previous.prior.packet_hashes(REVIEW)
    c.require(
        set(packet) == set(done["files_sha256"]) | {"completion.json"}
        and all(packet[n] == h for n, h in done["files_sha256"].items()),
        "Review packet changed",
    )
    with zipfile.ZipFile(REVIEW / "sources.zip") as archive:
        c.require(
            len(archive.namelist()) == len(set(archive.namelist()))
            and set(archive.namelist()) == set(done["sources_sha256"]),
            "Review capsule membership",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == h
                for n, h in done["sources_sha256"].items()
            ),
            "Review capsule bytes",
        )
    return {"files_sha256": packet, "completion_sha256": c.sha(REVIEW / "completion.json")}, r


def execute(output, test_path):
    c.require(output == REVIEW and not output.exists(), "Use the fresh registered review directory")
    began = time.monotonic()
    with previous.prior.model_fence():
        r, native, cells, hashes = load()
        bound, receipt = sources(), tests(test_path)
        output.mkdir(parents=True, exist_ok=False)
        io.write(
            output / "registration.json",
            {
                "sources_sha256": bound,
                "capture_sha256": hashes,
                "tests": receipt,
                "simulators_rerun": False,
            },
        )
        with zipfile.ZipFile(
            output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for name in bound:
                archive.write(ROOT / name, arcname=name)
        replayed = checker.check(r["data"], r["plan"], native, cells)
        c.require(replayed == c.read(CAPTURE / "comparison.json"), "Preparation replay differs")
        independent = independent_checks(r, cells)
        c.require(sources() == bound and load()[3] == hashes, "Inputs changed during review")
        io.write(output / "review.json", {"replayed": replayed, "independent": independent})
        done = {
            "status": "history_preparation_review_closed",
            "decision": "D098",
            "finished_utc": datetime.now(UTC).isoformat(),
            "elapsed_seconds": time.monotonic() - began,
            "replayed_comparisons": replayed["comparisons"],
            "failed_comparisons": 0,
            "independent_rate_comparisons": independent["comparisons"],
            "full_layout_arrays": independent["full_layout_arrays"],
            "capture_sha256": hashes,
            "sources_sha256": bound,
            "tests": receipt,
            "files_sha256": previous.prior.packet_hashes(output),
            "simulators_rerun": False,
            "reference_integration_run": False,
            "production_changed": False,
            "original_receipt_rewritten": False,
            "history_trajectory_qualified": False,
            "biology_validated": False,
            "gpu_tested": False,
        }
        io.write(output / "completion.json", done)
    return {
        k: v
        for k, v in done.items()
        if k not in ("capture_sha256", "sources_sha256", "files_sha256", "tests")
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tests", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute(REVIEW, args.tests.resolve()), indent=2))
