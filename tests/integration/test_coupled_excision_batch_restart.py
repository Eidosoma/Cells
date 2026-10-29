"""Opt-in checks using a prepared family package and its original frozen runtime.

Select one test per process: admission, baseline, then restart. A missing package
is a skip, never a qualification pass. See the package case.json for provenance.
"""

import os

import pytest

from validation.execution.coupled_excision_batch_restart import Qualification


@pytest.fixture
def qualification():
    root = os.environ.get("CELLS_COUPLED_EXCISION_BATCH_RESTART")
    if root is None:
        pytest.skip("Requires an explicitly prepared frozen cut qualification package")
    return Qualification(root)


def test_saved_compiled_cut_batch_admission_and_roundtrip(qualification):
    qualification.admission()


def test_compiled_batch_baseline_with_real_intermediate_checkpoint(qualification):
    qualification.baseline()


def test_compiled_batch_fresh_restart_complete_suffix(qualification):
    qualification.restart()
