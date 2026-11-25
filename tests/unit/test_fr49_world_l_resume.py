"""FR-49's World L, its engine-only criterion L7 (fr49-compartment-compositions-v1, Part L;
validation/fr49/REGISTRATION.md §3): a checkpoint inside the pulse resumes bit for bit. Plant (d),
the planted checkpoint, is the judge's (validation/fr49/judge_l.py).

World L at dt = 2 s to 1260 s, checkpointed at 900 s, written and loaded, then resumed. That is two
compiles: the labelled run and the resumed segment.

Seconds and reason (D224): 82.7 s on the timed lane, measured cold at a9ea8915. The resume is
FR-49's own promise for labels beside a compartment, and it is split from test_fr49_world_l.py
to keep each file under the tier cap.
"""

from cells.definitions.specs import parse_spec
from validation import id_table
from validation.fr49 import judge_l

END = 1260.0


def test_l7_a_checkpoint_inside_the_pulse_resumes_bit_for_bit(monkeypatch):
    """L7: a checkpoint at 900 s, written and loaded, resumes bit for bit, every history field from
    the checkpoint's row on."""
    monkeypatch.setattr(judge_l, "parse_spec", lambda raw: parse_spec(id_table.translate(raw)))
    spec, labelled = judge_l.run_world(2.0, labelled=True, end=END)
    found = judge_l.restart(spec, labelled)
    assert found["passed"], found
