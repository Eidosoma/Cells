"""A labelled, washed run resumes bit for bit across a wash (FR-44's case 4, D327; FR-27's
restart across a wash, which the wash note lists among its untested version-1 limits).

The world is FR-44's labelled twin world (tests/unit/test_neutral_labels_events.py), without Q
and its reaction, which only add compile time here. It is cut around its third wash, 3/7 of the
well at 0.06 s. Two washes came before it, so the checkpoint
carries their level records and nonzero cumulative records, the label owner's included.
- **At the wash row, 0.06 s**, the state the wash acts on, resumed through a written snapshot: the
  resumed run's first step applies the wash.
- **One step after it, 0.07 s**, resumed directly: the wash is behind the cut.
Each resumed run is the uninterrupted run, bit for bit, on every field and row.

The plants (FR-22's redo-or-skip pattern). Each resumed run completes and differs from the
uninterrupted one, so each is caught by the comparison, not by a refusal:
- the restored wash_applied one over at the wash row, so the wash is skipped;
- one short at the step after it, so the wash is redone.

Three compiles: the run and the two resumes. A plant reuses its cut's compile, since its program
is the same. The tier row gives the measured seconds. Their reason (D224): no other file runs a
restart across a wash. A new file, since the twins' file sits near the tier cap.
- **The cut before the wash, and the unlabelled twin's resume, are left out** for the cap's sake.
  The cut at the wash row already applies the wash after the resume.
- The unlabelled twin's physical fields are the labelled run's, bit for bit (the twins' file),
  and the wash's restart reads the same fields in both programs.
"""

import dataclasses

import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.records.io import load_snapshot, write_snapshot
from tests.unit.test_neutral_labels_events import washed_world
from validation.tissue import wash_schedule_fixtures as wfx

T3 = 0.06  # s: the third wash, 3/7 of the well.


def same(resumed, full, start):
    """Every field of the resumed run's history is the uninterrupted run's from `start`."""
    return all(
        np.asarray(a).tobytes() == np.asarray(b)[start:].tobytes()
        for a, b in zip(resumed.history, full.history, strict=True)
    )


def test_a_labelled_washed_run_resumes_bit_for_bit_across_a_wash(tmp_path):
    """The module docstring's cuts and plants."""
    full = run(parse_spec(washed_world(made=False)))
    spec = full.spec
    ids, outside = list(spec.model.species_ids), [c.id for c in spec.model.extracellular]
    s, w = ids.index(wfx.TRACER), outside.index("well")
    collected = np.asarray(full.history.wash_collected_fmol)[-1, s, w]
    times = np.asarray(full.times)  # Checkpoints are taken at exact accepted times.
    k = int(np.argmin(np.abs(times - T3)))
    for cut, shift, applied_before in ((times[k], 1, 2), (times[k + 1], -1, 3)):
        checkpoint = full.checkpoint_at(cut)
        state = checkpoint.state
        assert int(np.asarray(state.wash_applied)[w]) == applied_before, cut
        assert np.asarray(state.wash_collected_fmol)[s, w] > 0, cut
        assert np.all(np.asarray(state.label_outside_removed_fmol)[0, :, w] > 0), cut
        assert np.asarray(state.wash_last_sample_fmol)[s, w] > 0, cut
        source = spec
        if shift > 0:  # The wash row: through a written snapshot.
            write_snapshot(tmp_path / "checkpoint", spec, checkpoint)
            loaded = load_snapshot(tmp_path / "checkpoint")
            source, checkpoint = loaded.spec, loaded.checkpoint
        resumed = run(source, checkpoint)
        assert same(resumed, full, checkpoint.step_index), cut
        applied = np.array(checkpoint.state.wash_applied)
        applied[w] += shift  # Skipped at the wash row (+1), redone after it (-1).
        planted = dataclasses.replace(
            checkpoint, state=checkpoint.state._replace(wash_applied=applied)
        )
        caught = run(source, planted)  # It completes: no refusal catches it.
        assert not same(caught, full, checkpoint.step_index), cut
        end = np.asarray(caught.history.wash_collected_fmol)[-1, s, w]
        assert (end < collected) if shift > 0 else (end > collected), cut
