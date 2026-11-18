"""Small serialized-output audit checks; frozen reference trajectories are read only."""

import pytest

from cells.execution.runner import run
from cells.records.io import write_run
from scripts.audit_multispecies_build import audit_run
from tests.multispecies_fixtures import spec_for
from tests.unit.test_multispecies_membrane import PLAN, REFERENCE, short_case


@pytest.fixture
def recorded(tmp_path):
    case = short_case()
    path = tmp_path / "run"
    result = run(spec_for(case, samples=[0.0, 0.003, 0.01, 0.027, 0.04]))
    write_run(path, result, checkpoint_times=(0.02,))
    return path, case


def test_ordinary_payload_corruption_is_refused(recorded):
    path, case = recorded
    with (path / "trajectory.npz").open("ab") as handle:
        handle.write(b"tamper")
    with pytest.raises(AssertionError):
        audit_run(path, case.definition(), PLAN, REFERENCE / case.id)
