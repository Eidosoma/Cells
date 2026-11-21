"""Gene regulation's option-A references (G2) are complete, consistent, and catch planted errors.

The interface (validation/gene_regulation/references/interface/*.json) was written by that
package's run.py from the equation sheet at tag gr1-sheet-2026-11-20 alone. This test recomputes,
with validation/gene_regulation/references/checks.py and without the code that wrote the files:
- completeness: 50 potential sets, 16 worlds, every readout on every output grid, both R-noise
  worlds, every plant;
- every identity of §4.8 (and W's definition) from the stored test-instance trajectories;
- the window rates J̄, §5.2's closed forms at every set and their gaps, §5.1's scalar formulas
  and steady states, the R-noise band and its verdicts, the plants' margins and summaries;
- that a planted error in each kind of stored number is caught.

About 1 s; nothing here imports the engine or scipy. Regeneration is
`python -m validation.gene_regulation.references.run` (an hour or more, detached).
"""

from __future__ import annotations

from functools import partial

import pytest

from validation.gene_regulation.references import checks


@pytest.fixture(scope="module")
def data():
    return checks.load()


def test_interface_complete_and_consistent(data):
    checks.check_all(data)


def _at(d, path):
    for key in path[:-1]:
        d = d[key]
    return d, path[-1]


def _times(factor):
    return lambda v: v * factor


def _plus(delta):
    return lambda v: v + delta


def _ids(*pairs):
    """check_identities on the edited worlds only (the full check runs once, above)."""
    return partial(checks.check_identities, only=set(pairs))


TS = ("trajectories_test_instances", "sets", "0", "worlds")
TS1 = ("trajectories_test_instances", "sets", "1", "worlds")
# Each row: a stored number, an exact edit of it, and the check that must catch it.
PLANTED = [
    ("readout removed", (*TS, "A1", "readouts", "C_tx_3"), None, checks.check_complete),
    ("free polymerases", (*TS, "pol T=5", "readouts", "F_pol", 60), _times(1 + 1e-9),
     _ids(("0", "pol T=5"))),
    ("a stage's complexes", (*TS, "A1", "readouts", "C_tl_4", 100), _times(1 + 1e-9),
     _ids(("0", "A1"))),
    ("residues in transit", (*TS, "two-gene", "readouts", "W_tx2", 50), _times(1 + 1e-6),
     _ids(("0", "two-gene"))),
    ("a release extent", (*TS, "rib n_R=20", "readouts", "int_Q_tl", 30), _times(1 + 1e-9),
     _ids(("0", "rib n_R=20"))),
    ("an amino-acid row", (*TS, "rib n_R=50", "readouts", "n_A", 30), _times(1 + 1e-10),
     _ids(("0", "rib n_R=50"))),
    ("G(t) − G(0)", (*TS, "A1", "readouts", "G_minus_G0", 200), _times(1 + 1e-9),
     _ids(("0", "A1"))),
    ("Spirin's set, a protein row", (*TS1, "A1", "readouts", "n_P", 250), _times(1 + 1e-9),
     _ids(("1", "A1"))),
    ("a heat class", (*TS, "A1", "readouts", "H_rc", 300), _times(1 + 1e-8),
     _ids(("0", "A1"))),
    ("a window rate", (*TS, "pol T=10", "readouts", "J_bar_tx", 0), _times(1 + 1e-9),
     checks.check_window),
    ("a machine closed form", ("r_machine", "sets", 7, "worlds", "pol T=20", "closed", "J_tx"),
     _times(1 + 1e-9), partial(checks.check_machine, only_sets={7})),
    ("a machine gap", ("r_machine", "sets", 3, "worlds", "rib n_R=5", "gaps", "F_rib"),
     _times(2.0), partial(checks.check_machine, only_sets={3})),
    ("an R-chain series value", ("r_chain", "test_instance", "closed_form", "n_R", 30),
     lambda v: repr(float(v) * (1 + 1e-9)), checks.check_chain),
    ("an R-chain gap", ("r_chain", "sets", 0, "gaps", "n_P"), _times(1.01), checks.check_chain),
    ("an R-noise mean", ("r_noise", "worlds", "T10", "readouts", "n_R", "mean", 60), _plus(1.0),
     checks.check_noise),
    ("an R-noise verdict", ("r_noise", "worlds", "A1", "outside"), _plus(1), checks.check_noise),
    ("a plant verdict", ("plants", "rows", 0, "verdicts", 0, "fails"), lambda v: not v,
     checks.check_plants),
    ("a transcribed value", ("inputs", "transcription_check", "mu_N", "agrees"), lambda v: False,
     checks.check_summaries),
]


@pytest.mark.parametrize("path,edit,check", [p[1:] for p in PLANTED], ids=[p[0] for p in PLANTED])
def test_planted_error_is_caught(data, path, edit, check):
    holder, key = _at(data, path)
    original = holder[key]
    try:
        if edit is None:
            del holder[key]
        else:
            holder[key] = edit(original)
        with pytest.raises(checks.CheckError):
            check(data)
    finally:
        holder[key] = original
    check(data)  # restored
