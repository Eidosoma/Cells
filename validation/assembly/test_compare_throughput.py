"""Matched timing evidence must reject lost state even when summaries agree."""

import json

import numpy as np
import pytest

from cells.assembly.engine import initial_state
from cells.assembly.io import digest, write_checkpoint
from cells.assembly.spec import parse_spec
from validation.assembly.compare_throughput import compare_checkpoints


def pair(tmp_path):
    spec = parse_spec({"worlds": 4})
    state = initial_state(spec)
    paths = [tmp_path / name for name in ("baseline", "candidate")]
    for path in paths:
        write_checkpoint(path, spec, state, execution={"backend": "cpu"})
    return paths, state


def rewrite_payload(path, arrays):
    np.savez_compressed(path / "state.npz", **arrays)
    record = json.loads((path / "manifest.json").read_text())
    record["state_sha256"] = digest(path / "state.npz")
    (path / "manifest.json").write_text(json.dumps(record))


def test_comparison_accepts_lossless_different_compression(tmp_path):
    (left, right), state = pair(tmp_path)
    rewrite_payload(left, state._asdict())
    assert digest(left / "state.npz") != digest(right / "state.npz")
    result = compare_checkpoints(left, right)
    assert result["worlds"] == 4
    assert result["identical_array_bytes"] == sum(x.nbytes for x in state)


@pytest.mark.parametrize("change", ["signed_zero", "missing_field", "dtype", "world_ids"])
def test_comparison_rejects_hidden_state_or_identity_changes(tmp_path, change):
    (left, right), state = pair(tmp_path)
    arrays = state._asdict()
    if change == "signed_zero":
        arrays["time_s"][0] = -0.0
    elif change == "missing_field":
        arrays.pop("pending_event")
    elif change == "dtype":
        arrays["time_s"] = arrays["time_s"].astype(np.float32)
    else:
        record = json.loads((right / "manifest.json").read_text())
        record["world_ids"]["first"] = 1
        (right / "manifest.json").write_text(json.dumps(record))
    rewrite_payload(right, arrays)
    with pytest.raises(ValueError, match="differ"):
        compare_checkpoints(left, right)
