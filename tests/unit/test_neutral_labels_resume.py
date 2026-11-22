"""A labelled checkpoint resumes bit for bit through a written snapshot (FR-42 stage 1): the
five-pool world of tests/unit/test_neutral_arrival_labels.py, labelled, checkpointed inside S's
window of arrivals (the cohort's share nonzero), so the resumed steps carry the shares and cross
the window's end.

Two compiles (the labelled run and the resume), about 80 s on a light CPU. Their reason (D224):
FR-42's resume, moved here from tests/unit/test_neutral_arrival_labels.py to keep each file under
the tier cap; the extra compile is the labelled run that file's fixture also makes.
"""

import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.records.io import load_snapshot, write_snapshot
from tests.unit.test_neutral_arrival_labels import POOLS, TS, H, bits, labelled, world


def test_a_labelled_checkpoint_resumes_bit_for_bit(tmp_path):
    """Through a written snapshot, from inside the window (one compile for the resume)."""
    full = run(parse_spec(labelled(world())))
    checkpoint = full.checkpoint_at(TS + H)
    assert np.asarray(checkpoint.state.label_share)[len(POOLS), 1, 0] > 0
    write_snapshot(tmp_path / "checkpoint", full.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    resumed = run(loaded.spec, loaded.checkpoint)
    for a, b in zip(resumed.history, full.history, strict=True):
        assert bits(a) == bits(np.asarray(b)[checkpoint.step_index :])
