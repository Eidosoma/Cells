"""Artifact-dependent checks on actual REF-003a output, including rehashed corruptions."""

import hashlib
import json
import shutil

import pytest

from validation.betse import contact as c

RECORDED = c.ROOT / "runs/ref-003a-2026-09-12/contact-01"
RECEIPT_SHA = "7576ac12fefaf78cc3daa829a2ce0e7a2714f93ec970e9ca48218b164a03843d"


def test_actual_packet_audits_without_model_calls():
    assert c.sha(RECORDED / "verification.json") == RECEIPT_SHA
    result = c.audit(RECORDED)
    assert result["status"] == "pass"
    assert result["upstream_calls"] == result["production_calls"] == result["trajectory_calls"] == 0


@pytest.mark.parametrize(
    "corruption",
    (
        "sign",
        "amount_units",
        "current_units",
        "default_constants",
        "hidden_input_mutation",
        "missing_compiled_backend",
        "upstream_source_identity",
        "dependency_identity",
        "float32_claim",
    ),
)
def test_rehashed_actual_corruption_is_rejected(tmp_path, corruption):
    assert c.sha(RECORDED / "verification.json") == RECEIPT_SHA
    copied = tmp_path / "contact"
    shutil.copytree(RECORDED, copied)
    path = copied / "betse.json"
    value = c.read(path)
    result = value["results"]["matched_constants"]
    if corruption in ("sign", "amount_units"):
        factor = -1 if corruption == "sign" else 1e-15
        for field in ("raw_density_mol_per_m2_s", "flux_fmol_per_s", "derived_inward_current_A"):
            result[field] = [v * factor for v in result[field]]
    elif corruption == "current_units":
        result["derived_inward_current_A"] = [v * 1e12 for v in result["derived_inward_current_A"]]
    elif corruption == "default_constants":
        value["results"]["source_constants"]["constants"] = result["constants"]
    elif corruption == "hidden_input_mutation":
        result["inputs_after"]["vBA"][3] = 0.0
    elif corruption == "upstream_source_identity":
        value["installed_python_sha256"]["betse/science/sim_toolbox.py"] = "0" * 64
    elif corruption == "dependency_identity":
        value["environment"]["packages"]["numpy"] = "0.0.0"
    else:
        path = copied / "cells.json"
        value = c.read(path)
        if corruption == "missing_compiled_backend":
            value["results"].pop("jax_jit")
        else:
            value["results"]["jax_jit"]["dtype"] = "float32"
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False))
    receipt = c.read(copied / "verification.json")
    receipt["files_sha256"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (copied / "verification.json").write_text(json.dumps(receipt, sort_keys=True, allow_nan=False))
    with pytest.raises(ValueError):
        c.audit(copied)
