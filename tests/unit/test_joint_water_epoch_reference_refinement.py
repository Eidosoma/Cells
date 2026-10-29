"""Six comparisons after new reference runs; no production integration here."""

import os
from pathlib import Path

import pytest

from tests.owned_joint_water_epoch_reference_refinement_helpers import comparison
from validation.topology.joint_water_epoch_transient_fixtures import DATASETS


@pytest.mark.parametrize("dataset", DATASETS)
def test_complete_epoch_reference_refinement(dataset):
    comparison(
        Path(os.environ["CELLS_REFERENCE_REFINEMENT_BUNDLE"]),
        Path(os.environ["CELLS_REFERENCE_REFINEMENT_OUTPUT"]),
        dataset,
    )
