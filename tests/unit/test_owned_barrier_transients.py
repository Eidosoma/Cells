"""Six full trajectories; accepted stage and public checks are retained separately."""

import os
from pathlib import Path

import pytest

from tests.owned_barrier_transient_helpers import comparison
from validation.transport.owned_barrier_transient_fixtures import DATASETS


@pytest.mark.parametrize("dataset", DATASETS)
def test_complete_scheduled_barrier_transient_refinement(dataset):
    comparison(
        Path(os.environ["CELLS_BARRIER_BUNDLE"]), Path(os.environ["CELLS_BARRIER_OUTPUT"]), dataset
    )
