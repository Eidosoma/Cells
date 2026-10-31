"""PROPOSAL ONLY: requires Chief-approved source patch and numerical launch.

Never substitutes for the original signed_environment test or its raw-lag
accuracy assertion. No expected-failure/limitation conversion is introduced.
"""

import hashlib
import json
import os
from pathlib import Path

import numpy as np

from cells.processes import betse_ecm_transport as transport
from validation.betse import betse_ecm_transport_checks as checks
from validation.betse import betse_ecm_transport_reference as reference

ARCHIVE = Path("/mnt/workspaces/Cells/betse-ecm-failure-capture-20261030-01")
INPUT_SHA256 = "27be2d6d59bd3cab9196a5ee64054b667702a549f81a0e6546dcfefcc27459b8"
ACTUAL_SHA256 = "678c0b02c5361c4853102f3a2ea8b4b75a248b98ff5e8a6df79441f5138777f6"
KEY = "junction_requested_outward_increment_mol_m3"


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def inputs():
    path = ARCHIVE / "original-case.json"
    assert digest(path) == INPUT_SHA256
    return json.loads(path.read_text())["inputs"]


def original_trial(data):
    assert len(data["steps"]) == 1
    binding = transport.bind(data["definition"])
    parent = transport.state(binding, data["initial"])
    return transport.step(binding, parent, transport.drive(binding, data["steps"][0]))


def save(name, data, columns):
    root = Path(os.environ["CELLS_COMPONENT_EVIDENCE"])
    with (root / (name + ".npz")).open("xb") as handle:
        np.savez_compressed(handle, **columns)
        handle.flush()
        os.fsync(handle.fileno())
    with (root / (name + ".json")).open("x") as handle:
        json.dump(transport.plain(data), handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def test_all_original_state_and_legacy_ledger_bytes_remain_unchanged():
    data = inputs()
    trial = original_trial(data)
    columns = checks.columns(trial)
    save("legacy-byte-invariance", dict(inputs=data, metadata=checks.metadata(trial)), columns)
    path = ARCHIVE / "original-case.npz"
    assert digest(path) == ACTUAL_SHA256
    with np.load(path, allow_pickle=False) as old:
        names = {
            key.removeprefix("actual__step_0__").replace("__", ".")
            for key in old.files
            if key.startswith("actual__step_0__")
        }
        assert set(columns) == names
        for key, value in columns.items():
            baseline = old["actual__step_0__" + key.replace(".", "__")]
            value = np.asarray(value)
            assert value.dtype == baseline.dtype and value.shape == baseline.shape
            assert value.tobytes() == baseline.tobytes(), key


def test_requested_operator_increment_against_both_complete_references():
    data = inputs()
    trial = original_trial(data)
    actual = np.asarray(trial.diagnostics[KEY])
    save("requested-increment-actual", dict(inputs=data), {"actual": actual})
    primary = reference.evaluate(data)
    refined = reference.evaluate(data, refinement=2)
    target = np.asarray(primary["history"][0]["ledgers"][KEY])
    tighter = np.asarray(refined["history"][0]["ledgers"][KEY])
    save(
        "requested-increment-references",
        dict(inputs=data, reference=primary, refined_reference=refined),
        {"actual": actual, "reference": target, "refined": tighter},
    )
    assert actual.shape == target.shape == tighter.shape == (4, 3)
    # The existing comparator assigns the unchanged concentration floor and
    # relative budget to this separately named mol/m3 operator increment.
    assert np.array_equal(checks.budget(KEY, target), 3e-13 + 6e-12 * np.abs(target))
    checks.compare({KEY: actual}, {KEY: target})
    assert checks.compare({KEY: target}, {KEY: tighter}) <= 0.1
    assert not np.any(actual[3])  # P is supplied/stationary and never committed.
    assert not np.any(np.asarray(trial.diagnostics["clipping_added_mol"]))
