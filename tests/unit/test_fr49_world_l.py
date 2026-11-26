"""FR-49's World L, its engine-only criteria L1–L3 and L6 (fr49-compartment-compositions-v1, Part L;
validation/fr49/REGISTRATION.md §3). L7, the restart, is test_fr49_world_l_resume.py.

World L (validation/fr49/worlds.py) at dt = 2 s to 1260 s covers the pulse [600, 1200) s. The runs
are the labelled run and its unlabelled twin, two compiles.

Seconds and reason (D224): 77.7 s on the timed lane, measured cold at a9ea8915. This is the only
compiled path through labels and expression beside a compartment. L4 and L5, the order and the
size against the code-blind references, are the registered judgement
(validation/fr49/judge_l.py), run once the references are tagged.
"""

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from validation import id_table
from validation.fr49 import judge_l

END = 1260.0


@pytest.fixture(scope="module")
def runs():
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(judge_l, "parse_spec", lambda raw: parse_spec(id_table.translate(raw)))
        spec, labelled = judge_l.run_world(2.0, labelled=True, end=END)
        _, plain = judge_l.run_world(2.0, labelled=False, end=END)
    return spec, labelled, plain


def test_l1_l2_the_physics_is_the_unlabelled_twins_bit_for_bit(runs):
    """L1: both runs pass every host check on every row (the runner refuses otherwise). L2: every
    field, observation and diagnostic of the twin, bit for bit, in the labelled run, which adds the
    label owner's fields alone."""
    _, labelled, plain = runs
    differ, extra_is_the_labels = judge_l.same_physics(labelled, plain)
    assert differ == [] and extra_is_the_labels


def test_l3_nothing_is_labelled_before_the_pulse_and_the_label_reaches_the_compartment(runs):
    """L3: before t1, label x's share is exactly 0 at the owner and at the compartment on every
    row. Live: after the pulse the owner and the compartment both hold labelled S."""
    spec, labelled, _ = runs
    found = judge_l.base_before_the_pulse(spec, labelled)
    assert found["rows"] > 0 and found["all_zero"], found
    q = judge_l.quantities(spec, labelled, [END])
    assert q["x_O"][0] > 0 and q["x_C"][0] > 0 and np.all(q["n_C"] > 0)


def test_l6_expression_is_silent_at_the_compartment(runs):
    """L6: expression's rows at the compartment stay bitwise their declared amounts on every row,
    and S1–S3 hold there (no ion row moves, and V_b and the capacitor energy stay at rounding)."""
    spec, labelled, _ = runs
    found = id_table.function(judge_l.silence)(spec, labelled)
    assert found["passed"], found
