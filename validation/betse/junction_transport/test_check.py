"""Prove the checker rejects mapping, orientation and amount-update corruption."""

import json
import os
from pathlib import Path

import pytest
from check import check


@pytest.mark.parametrize("change", ["none", "partner", "area", "sign", "amount"])
def test_native_preflight_checker(tmp_path, change):
    source = os.environ.get("CELLS_JUNCTION_PREFLIGHT")
    if not source:
        pytest.skip("Set CELLS_JUNCTION_PREFLIGHT to immutable native fixture evidence")
    prepared = json.loads((Path(source) / "preparation.json").read_text())
    panel = json.loads((Path(source) / "panel.json").read_text())
    first = prepared["geometry"]["canonical_face_pairs"][0][0]
    if change == "partner":
        prepared["geometry"]["nn_i"][first] = first
    elif change == "area":
        prepared["geometry"]["mem_sa"][first] *= 1.01
    elif change == "sign":
        panel["rows"][0]["native_density_mol_m2_s"][first] *= -1
    elif change == "amount":
        panel["rows"][0]["concentration_after_mM"][0] += 0.01
    (tmp_path / "preparation.json").write_text(json.dumps(prepared))
    (tmp_path / "panel.json").write_text(json.dumps(panel))
    if change == "none":
        assert check(tmp_path)["status"] == "held_open_junction_mapping_and_single_update_pass"
    else:
        with pytest.raises((AssertionError, ValueError)):
            check(tmp_path)
