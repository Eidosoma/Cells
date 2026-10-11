"""Reject corrupted gate equations and lifecycle evidence without rerunning BETSE."""

import copy
import json
import os
from pathlib import Path

import pytest
from check import check


@pytest.mark.parametrize("fault", ["none", "gate", "count", "order", "observer", "initial"])
def test_lifecycle_checker(fault):
    fixture = os.environ.get("CELLS_DYNAMIC_PREFLIGHT")
    if not fixture:
        pytest.skip("Requires explicit native preflight artifact")
    panel = copy.deepcopy(json.loads(Path(fixture).read_text()))
    observed = next(r for r in panel["lifecycles"] if r["observed"])
    if fault == "gate":
        observed["gate_calls"][0]["sim_after"][0] += 0.01
    elif fault == "count":
        observed["gate_calls"].pop()
    elif fault == "order":
        observed["gate_calls"][0]["species_index"] = 999
    elif fault == "observer":
        observed["final"]["vm"][0] += 0.01
    elif fault == "initial":
        observed["initializations"][0]["sim_after"][0] += 0.01
    if fault == "none":
        assert check(panel)["status"] == "native_dynamic_junction_law_and_lifecycle_pass"
    else:
        with pytest.raises(AssertionError):
            check(panel)
