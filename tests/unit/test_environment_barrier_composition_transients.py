"""Full-history CPU comparisons require an explicit frozen qualification bundle."""

import os
from pathlib import Path

import pytest

from validation.transport import environment_barrier_composition_transient_fixtures as fixtures


@pytest.mark.parametrize("dataset", fixtures.DATASETS)
def test_full_physical_inputs_and_declared_control_history_are_preserved(dataset):
    values = fixtures.inputs(dataset)
    fixtures.assert_same_physics_and_control_history(
        values["source_request"]["definition"], values["request"]["definition"]
    )


@pytest.mark.parametrize("dataset", fixtures.DATASETS)
def test_complete_evolved_barrier_history_and_refinement(dataset):
    if not (bundle := os.environ.get("CELLS_BARRIER_TRANSIENT_BUNDLE")):
        pytest.skip("Full evolved qualification needs its explicit frozen input bundle")
    from tests.owned_barrier_composition_transient_helpers import qualify

    qualify(
        Path(bundle),
        Path(os.environ["CELLS_BARRIER_TRANSIENT_OUTPUT"]),
        dataset,
    )
