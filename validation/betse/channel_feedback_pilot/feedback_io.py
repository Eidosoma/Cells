"""Exclusive, lossless bounded records; no numerical model dependencies."""

import gzip
import hashlib
import io
import json
import math
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON field")
        result[key] = value
    return result


def parse(text):
    return json.loads(
        text, object_pairs_hook=unique, parse_constant=lambda _: require(False, "Nonfinite JSON")
    )


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def write_compressed(path, value):
    with (
        Path(path).open("xb") as raw,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as archive,
    ):
        with io.TextIOWrapper(archive, encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True, separators=(",", ":"), allow_nan=False)


def read_compressed(path, limit=128 * 1024**2):
    with gzip.open(path, "rb") as stream:
        raw = stream.read(limit + 1)
    require(len(raw) <= limit, "Uncompressed record limit exceeded")
    return parse(raw)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class Ledger:
    """Keep summary and every rejection; passing raw identities remain replayable."""

    def __init__(self, absolute, relative=2e-11, failure_path=None):
        self.absolute, self.relative = absolute, relative
        self.count = self.failed = 0
        self.maximum = 0.0
        self.worst = None
        self.failures = []
        self.failure_path = failure_path

    def compare(self, name, actual, expected, unit):
        if isinstance(expected, list):
            require(
                isinstance(actual, list) and len(actual) == len(expected),
                "Comparison shape: " + name,
            )
            for i, (a, b) in enumerate(zip(actual, expected, strict=True)):
                self.compare(f"{name}/{i}", a, b, unit)
            return
        require(
            type(actual) in (int, float)
            and type(expected) in (int, float)
            and math.isfinite(actual)
            and math.isfinite(expected),
            "Invalid comparison scalar: " + name,
        )
        error = abs(actual - expected) / (self.absolute[unit] + self.relative * abs(expected))
        self.count += 1
        if error > self.maximum:
            self.maximum, self.worst = error, name
        if error > 1:
            self.failed += 1
            row = {
                "id": name,
                "actual": actual,
                "expected": expected,
                "unit": unit,
                "scaled_error": error,
            }
            if self.failure_path is None:
                self.failures.append(row)
            else:
                # This file belongs to one single-use job; preserve all rejected rows.
                with Path(self.failure_path).open("a") as stream:
                    stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")

    def summary(self):
        return {
            "comparisons": self.count,
            "failed_comparisons": self.failed,
            "maximum_scaled_error": self.maximum,
            "worst_id": self.worst,
            "status": "pass" if not self.failed else "fail",
        }
