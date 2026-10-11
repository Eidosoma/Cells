"""Source-bound lifecycle preparation, preserving the independently closed contact."""

import hashlib
import importlib
import math
import struct
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "channel_transport_audit"))
audit = importlib.import_module("transport_audit_context")
audit_job = importlib.import_module("transport_audit_job")
c, t = audit.c, audit.t
old = audit.capture_job
check = importlib.import_module("transport_check")
PROTOCOL = HERE / "protocol.json"
PRIOR = c.ROOT / "runs/ref-004b-transport-audit-2026-09-14/audit-01"
PRIOR_SHA = "18070f9898bbbd6061867f050ac54d00dbb407b9bd978ced3ebfef136e8b40fb"
SOURCE_NAMES = tuple(
    "validation/betse/channel_loop_preparation/" + name
    for name in (
        "protocol.json",
        "loop_context.py",
        "loop_observer.py",
        "loop_native.py",
        "loop_check.py",
        "pilot_reference.py",
        "pilot_readiness.py",
        "loop_job.py",
        "test_channel_loop.py",
    )
) + ("docs/BETSE_CHANNEL_LOOP_PREPARATION.md", "docs/BETSE_CHANNEL_FEEDBACK_DESIGN.md")


def prior_closeout():
    c.require(c.sha(PRIOR / "completion.json") == PRIOR_SHA, "Transport closeout changed")
    done = c.read(PRIOR / "completion.json")
    c.require(
        done["status"] == "single_transfer_audit_closed"
        and done["single_transfer_qualified"] is True
        and done["failed_comparisons"] == 0
        and done["independent_comparisons"] == 37068,
        "Missing independently qualified transport prerequisite",
    )
    r = audit_job.authenticate(PRIOR)  # Authentication only, never numerical_audit/execute.
    hashes = audit.packet_hashes(PRIOR)
    c.require(
        set(hashes) == set(done["files_sha256"]) | audit.OPERATIONAL | {"completion.json"},
        "Prior audit membership changed",
    )
    c.require(
        all(hashes[name] == digest for name, digest in done["files_sha256"].items()),
        "Prior audit payload changed",
    )
    c.require(
        c.inspect_source() == c.read(audit.CAPTURE / "registration.json")["upstream"],
        "Native checkout changed",
    )
    return {
        "path": str(PRIOR.relative_to(c.ROOT)),
        "files_sha256": hashes,
        "capture_sha256": r["capture_sha256"],
        "single_transfer_qualified": True,
    }


def sources():
    return {name: c.sha(c.ROOT / name) for name in sorted(set(audit.sources()) | set(SOURCE_NAMES))}


def validate_protocol(p):
    c.require(p == c.read(PROTOCOL), "Unregistered lifecycle protocol")
    c.require(p["prior_completion_sha256"] == PRIOR_SHA, "Wrong prerequisite")
    c.require(
        p["phase"] == "INIT" and p["steps"] == 8 and p["dt_s"] == 25e-6, "Wrong lifecycle scope"
    )
    c.require(p["duration_s"] == p["steps"] * p["dt_s"], "Wrong elapsed horizon")
    c.require(
        p["initial_gate"] == [0.2, 0.6]
        and p["native_runs"] == 8
        and p["observed_steps"] == 32
        and p["modes"] == ["observed", "unobserved"],
        "Wrong fixture or coverage",
    )
    c.require(p["variants"] == [v["id"] for v in c.read(t.PROTOCOL)["variants"]], "Wrong controls")
    c.require(
        p["cells_trajectory_runs"] == 0
        and all(
            p[key] is False
            for key in (
                "production_changed",
                "automatic_polling",
                "automatic_retry",
                "automatic_followup",
            )
        ),
        "Unexpected production or automatic work",
    )


def configuration(template, r, variant, directory):
    conf = old.setup.configuration(
        template, r["base_protocol"], r["transport_protocol"], variant, directory
    )
    for name in ("init time settings", "sim time settings"):
        conf[name].update(
            {
                "time step": r["protocol"]["dt_s"],
                "total time": r["protocol"]["duration_s"],
                "sampling rate": r["protocol"]["dt_s"],
            }
        )
    return conf


def test_receipt(path):
    c.require(path.is_file() and path.is_relative_to(c.ROOT / "reports"), "Missing test XML")
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    identities = []
    for suite in suites:
        rows = list(suite.findall("testcase"))
        c.require(
            len(rows) == int(suite.attrib["tests"])
            and all(int(suite.attrib.get(k, 0)) == 0 for k in ("failures", "errors", "skipped")),
            "Failed/incomplete test suite",
        )
        for row in rows:
            c.require(
                not any(row.find(k) is not None for k in ("failure", "error", "skipped")),
                "Rejected software test",
            )
            identities.append(row.attrib["classname"] + "::" + row.attrib["name"])
    c.require(
        len(identities) == len(set(identities))
        and len(identities) >= 40
        and all("test_channel_loop" in name for name in identities),
        "Wrong focused tests",
    )
    return {
        "path": str(path.relative_to(c.ROOT)),
        "sha256": c.sha(path),
        "tests": len(identities),
        "identities": identities,
    }


def array_record(value):
    import numpy as np

    a = np.asarray(value)
    c.require(a.dtype == np.float64 and np.isfinite(a).all(), "Non-float64/nonfinite state")
    return {
        "dtype": a.dtype.str,
        "shape": list(a.shape),
        "values": a.tolist(),
        "bytes_sha256": hashlib.sha256(a.tobytes(order="C")).hexdigest(),
    }


def validate_array_record(record):
    """Rebuild little-endian float64 bytes without importing an array library."""
    c.require(set(record) == {"dtype", "shape", "values", "bytes_sha256"}, "Wrong array record")
    c.require(
        record["dtype"] == "<f8"
        and isinstance(record["shape"], list)
        and all(type(n) is int and 0 <= n <= 100000 for n in record["shape"])
        and math.prod(record["shape"]) <= 1000000,
        "Wrong float64 shape/dtype",
    )
    digest = hashlib.sha256()

    def add(value, shape):
        if shape:
            c.require(
                isinstance(value, list) and len(value) == shape[0], "Array value shape differs"
            )
            for v in value:
                add(v, shape[1:])
        else:
            c.require(
                type(value) in (int, float) and math.isfinite(value),
                "Nonfinite/invalid float64 scalar",
            )
            digest.update(struct.pack("<d", value))

    add(record["values"], record["shape"])
    c.require(digest.hexdigest() == record["bytes_sha256"], "Array bytes disagree with values")
