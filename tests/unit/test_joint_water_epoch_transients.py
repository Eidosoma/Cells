"""Six full transient comparisons; contract and padding evidence is retained separately."""

import os
from pathlib import Path

import pytest

from tests.owned_joint_water_epoch_transient_helpers import comparison
from validation.topology.joint_water_epoch_transient_fixtures import DATASETS


@pytest.mark.parametrize("dataset", DATASETS)
def test_complete_epoch_transient_refinement(dataset):
    comparison(
        Path(os.environ["CELLS_REFINEMENT_BUNDLE"]),
        Path(os.environ["CELLS_REFINEMENT_OUTPUT"]),
        dataset,
    )
