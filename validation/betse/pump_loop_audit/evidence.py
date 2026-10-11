"""Stdlib-only evidence integrity and comparisons; no producer/model imports."""

import contextlib
import hashlib
import importlib.abc
import json
import math
import struct
import sys
import zipfile
from itertools import batched
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
CAPTURE = ROOT / "runs/ref-005b-pump-loop-2026-09-16/capture-01"
COMPLETION_SHA = "25080e882abfd303b4559132dd94512defa4793305e608afd906c9aeae3359c0"
REGISTRATION_SHA = "5d8a6285baec4182758eff0e407ff95e2580dce5db3a9718460384e45d70c6bf"
FORBIDDEN = (
    "cells",
    "betse",
    "numpy",
    "scipy",
    "jax",
    "jaxlib",
    "pump_check",
    "pump_context",
    "pump_job",
    "pump_native",
    "pump_reference",
    "coupled_reference",
    "family_audit",
    "loop_check",
)


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pairs(values):
    result = {}
    for k, v in values:
        require(k not in result, "Duplicate JSON key")
        result[k] = v
    return result


def finite_float(value):
    result = float(value)
    require(math.isfinite(result), "Nonfinite JSON number")
    return result


def read(path):
    return json.loads(
        Path(path).read_text(),
        object_pairs_hook=pairs,
        parse_float=finite_float,
        parse_constant=lambda _: require(False, "Nonfinite JSON constant"),
    )


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def flat(value):
    if isinstance(value, list):
        for v in value:
            yield from flat(v)
    else:
        yield value


def shape(value, axes):
    if axes:
        require(type(value) is list and len(value) == axes[0], "Array shape")
        for v in value:
            shape(v, axes[1:])
    else:
        require(type(value) in (int, float) and math.isfinite(value), "Array finite numeric scalar")


def array(record):
    require(
        set(record) == {"dtype", "shape", "values", "bytes_sha256"} and record["dtype"] == "<f8",
        "Array record",
    )
    shape(record["values"], record["shape"])
    digest = hashlib.sha256()
    for values in batched(flat(record["values"]), 8192, strict=False):
        digest.update(struct.pack(f"<{len(values)}d", *values))
    require(digest.hexdigest() == record["bytes_sha256"], "Array byte checksum")
    return record["values"]


class Ledger:
    def __init__(self):
        self.count = 0
        self.maxima = {}

    def compare(self, group, actual, expected, atol, rtol=2e-11):
        a, b = list(flat(actual)), list(flat(expected))
        require(len(a) == len(b), "Comparison extent: " + group)
        for x, y in zip(a, b, strict=True):
            require(math.isfinite(x) and math.isfinite(y), "Nonfinite comparison")
            error = abs(x - y)
            require(error <= atol + rtol * abs(y), "Independent mismatch: " + group)
            self.maxima[group] = max(self.maxima.get(group, 0.0), error)
            self.count += 1


@contextlib.contextmanager
def model_fence():
    def blocked(name):
        return any(name == p or name.startswith(p + ".") for p in FORBIDDEN)

    require(not any(blocked(n) for n in sys.modules), "Model already imported")

    class Fence(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path, target=None):
            if blocked(fullname):
                raise ImportError("Forbidden in independent native review: " + fullname)
            return None

    fence = Fence()
    sys.meta_path.insert(0, fence)
    try:
        yield
        require(not any(blocked(n) for n in sys.modules), "Review imported model")
    finally:
        sys.meta_path.remove(fence)


def software(path, minimum):
    suites = ET.parse(path).getroot().findall("testsuite")
    rows = [row for s in suites for row in s.findall("testcase")]
    require(
        len(rows) == sum(int(s.attrib["tests"]) for s in suites) >= minimum, "Software coverage"
    )
    require(
        all(int(s.get(k, "0")) == 0 for s in suites for k in ("failures", "errors", "skipped"))
        and all(row.find(k) is None for row in rows for k in ("failure", "error", "skipped")),
        "Software checks failed",
    )
    return dict(path=str(path.relative_to(ROOT)), sha256=sha(path), tests=len(rows))


def authenticate():
    require(
        sha(CAPTURE / "completion.json") == COMPLETION_SHA
        and sha(CAPTURE / "registration.json") == REGISTRATION_SHA,
        "Capture identity changed",
    )
    done, r = read(CAPTURE / "completion.json"), read(CAPTURE / "registration.json")
    require(
        done["status"] == "native_lifecycle_checks_pass_pending_review"
        and done["native_runs"] == 12
        and done["observed_steps"] == 48
        and done["observer_pairs"] == 6,
        "Unaccepted native scope",
    )
    paths = list(CAPTURE.rglob("*"))
    require(not any(p.is_symlink() for p in paths), "Symlink in capture")
    names = {str(p.relative_to(CAPTURE)) for p in paths if p.is_file()}
    require(
        names
        == set(done["files_sha256"])
        | {"completion.json", "launch.json", "runner.stdout.log", "runner.stderr.log"},
        "Capture membership",
    )
    require(
        len(done["files_sha256"]) == 73
        and all(sha(CAPTURE / n) == h for n, h in done["files_sha256"].items()),
        "Payload changed",
    )
    require(
        len(r["sources_sha256"]) == 613
        and all(sha(ROOT / n) == h for n, h in r["sources_sha256"].items()),
        "Captured source changed",
    )
    modules = {n for n in r["sources_sha256"] if n.startswith("src/cells/")}
    require(
        modules == {str(p.relative_to(ROOT)) for p in (ROOT / "src/cells").rglob("*.py")}
        and len(modules) == 55,
        "Production inventory changed",
    )
    with zipfile.ZipFile(CAPTURE / "sources.zip") as archive:
        require(
            len(archive.namelist()) == 613
            and set(archive.namelist()) == r["sources_sha256"].keys(),
            "Source capsule membership",
        )
        require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == h
                for n, h in r["sources_sha256"].items()
            ),
            "Source capsule bytes",
        )
    require(
        software(ROOT / r["software"]["path"], 29) == r["software"],
        "Original software receipt changed",
    )
    for prior in r["prerequisites"].values():
        directory = ROOT / prior["path"]
        require(
            sha(directory / "completion.json") == prior["completion_sha256"], "Prerequisite changed"
        )
        require(
            all(
                sha(directory / n) == h
                for n, h in read(directory / "completion.json")["files_sha256"].items()
            ),
            "Prior payload changed",
        )
    require(
        all(
            sha(ROOT / "upstream/betse-v1.5.0" / n) == h
            for n, h in r["upstream"]["files_sha256"].items()
        ),
        "Pinned upstream changed",
    )
    return r
