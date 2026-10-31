"""Observe five admission-only software checks without permitting a timestep.

Load explicitly with pytest's -p option. Scientific families remain held; this
probe supplies no campaign, native/reference or accepted-call credit.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

EXPECTED = {
    "changed_publication_projection": "Field projection and actual shared publication epoch differ",
    "changed_shared_epoch": "Shared network publications differ from their actual field epoch",
    "arbitrary_pump_weight": "Ordinary source rho_pump remains the identity scalar",
}


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    if item.path.name not in {
        "test_betse_normal_ecm_molecule_dispatch.py",
        "test_betse_normal_ecm_molecule_transport.py",
    }:
        yield
        return
    case = item.callspec.params["case"]
    assert case in EXPECTED, "This software probe admits only the five declared guard checks"
    module = item.module
    dispatch, ions = module.dispatch, module.ions
    original_verify, original_advance = dispatch.verify, dispatch.advance
    original_popen = subprocess.Popen
    calls, originals = [], []

    def verified(binding, parent):
        record = {"parent_digest": ions.digest(parent), "call_index": parent.clock.call_index}
        calls.append(record)
        try:
            result = original_verify(binding, parent)
        except BaseException as error:
            record.update(status="refused", type=type(error).__name__, message=str(error))
            raise
        else:
            record["status"] = "admitted"
            originals.append((parent, record["parent_digest"]))
            return result

    def no_advance(*args, **kwargs):
        raise AssertionError("Admission software checks cannot advance a scientific timestep")

    def guarded_popen(command, *args, **kwargs):
        parts = [command] if isinstance(command, str) else command
        if any("_native" in str(p) or "_reference" in str(p) for p in parts):
            raise AssertionError(
                "Admission software checks cannot launch native/reference children"
            )
        return original_popen(command, *args, **kwargs)

    dispatch.verify, dispatch.advance, subprocess.Popen = verified, no_advance, guarded_popen
    try:
        outcome = yield
    finally:
        dispatch.verify, dispatch.advance = original_verify, original_advance
        subprocess.Popen = original_popen
        unchanged = all(ions.digest(parent) == digest for parent, digest in originals)
        root = Path(os.environ["CELLS_MOLECULE_RUNNER_PROVENANCE"]) / item.path.stem
        root.mkdir(exist_ok=True)
        with (root / ("guard-" + case + ".json")).open("x") as stream:
            json.dump(
                dict(
                    nodeid=item.nodeid,
                    expected_refusal=EXPECTED[case],
                    calls=calls,
                    every_admitted_parent_unchanged=unchanged,
                    advance_calls=0,
                    native_reference_calls=0,
                    scientific_qualification_credit=0,
                ),
                stream,
                indent=2,
                allow_nan=False,
            )
            stream.write("\n")
    outcome.get_result()
    assert originals, "A valid initial state must be admitted before the challenged guard"
    assert unchanged, "Private challenge mutated an admitted parent"
    assert calls[-1]["status"] == "refused" and calls[-1]["type"] == "ValueError"
    assert calls[-1]["message"] == EXPECTED[case], "An unrelated refusal cannot supply a guard pass"
