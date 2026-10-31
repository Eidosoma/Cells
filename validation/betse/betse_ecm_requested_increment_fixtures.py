"""Deferred readers for immutable original ECM inputs and native-byte baselines."""

import hashlib
import json
import os
from pathlib import Path

CASES = (
    "signed_environment",
    "slow",
    "bulk_clipping",
    "stationary",
    "stationary_pump_role",
    "moving_reversed",
    "membrane_lag",
    "fast_duplicate",
    "permuted",
    "zero_transport",
)
CORRUPTION_CASES = (
    "wrong-sign",
    "wrong-cell-axis",
    "stationary-nonzero",
    "clipped-raw-lag",
    "rounded-state-difference",
)


def read(path):
    if path.stat().st_size > 16 * 2**20:
        raise ValueError("Oversize retained ECM metadata")
    return json.loads(path.read_text())


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def paths(case):
    if case not in CASES:
        raise ValueError("Require a declared retained original context")
    manifest = read(Path(__file__).with_name("betse_ecm_requested_increment_corpus.json"))
    row = manifest["cases"][case]
    root = Path(os.environ["CELLS_ECM_REQUESTED_INCREMENT_CORPUS_ROOT"])
    result = {}
    for role in ("metadata", "actual_native_arrays", "reference_arrays"):
        item = row[role]
        path = root / item["frozen_relative"]
        if sha(path) != item["sha256"]:
            raise ValueError("Changed original ECM retained corpus: " + role)
        result[role] = path
    return row, result


def fixture(case):
    row, files = paths(case)
    metadata = read(files["metadata"])
    inputs = metadata["inputs"]
    encoded = json.dumps(inputs, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    if hashlib.sha256(encoded).hexdigest() != row["inputs_sha256"]:
        raise ValueError("Changed original ECM numerical inputs")
    return inputs, row, files
