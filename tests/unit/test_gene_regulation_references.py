"""Gene regulation's option-A references (G2) are complete, consistent, and catch planted errors.

The interface (validation/gene_regulation/references/interface/*.json) was written by that
package's run.py from the equation sheet at tag gr1-sheet-2026-11-20 alone. This test recomputes,
with validation/gene_regulation/references/checks.py and without the code that wrote the files:
- completeness: 50 potential sets, 16 worlds, every readout on every output grid, both R-noise
  worlds, every plant;
- every identity of §4.8 (and W's definition) from the stored test-instance trajectories;
- the window rates J̄, §5.2's closed forms at every set and their gaps, §5.1's scalar formulas
  and steady states, the R-noise band and its verdicts, the plants' margins and summaries;
- that a planted error in each kind of stored number is caught;
- amendment R (§9 and its R2 addendum): the release references' R1 and R2 (complete, §9.7's
  identities recomputed from the stored outputs, the requester's limit and the cohort recomputed,
  the precision summaries, the development check's shape), and a planted error in each kind of
  stored number caught.

About 1 s; nothing here imports the engine (the last test imports run.py, hence scipy). Regeneration is
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


def test_receipt_records_untracked_executed_source(tmp_path, monkeypatch):
    """A checkout's receipt holds an imported file Git does not track, with its content (D259)."""
    import subprocess
    import sys

    from validation.gene_regulation.references import run

    git = lambda *a: subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)  # noqa: E731
    git("init", "-q")
    (tmp_path / "tracked.txt").write_text("x\n")
    git("add", "tracked.txt")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "c")
    (tmp_path / "untracked_exec.py").write_text("MARKER = 'only in the working tree'\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(run, "HERE", tmp_path)
    import untracked_exec  # noqa: F401

    try:
        src = run.provenance()["source"]
    finally:
        sys.modules.pop("untracked_exec", None)
    assert src["untracked_executed"] == ["untracked_exec.py"]
    assert "only in the working tree" in src["diff"]
    assert "?? untracked_exec.py" in src["status"]


# ---- amendment R (§9 at gr1-sheet-fr38-2026-11-22, its R2 addendum at gr1-sheet-fr38-r2-...) --
@pytest.fixture(scope="module")
def rel():
    return checks.load_release()


def test_release_interface_complete_and_consistent(rel):
    checks.check_release_all(rel)


CASE = ("release_r1", "cases", 7)  # p = 0.75 with `returned` sits at index 3; 7 is `held`, p = 0
RELEASE_PLANTED = [
    ("a hold value", (*CASE, "readouts", "hold_tx", 2), _times(1 + 1e-9),
     checks.check_release_identities),
    ("a release counter", (*CASE, "readouts", "int_Qf_s1", 3), _times(1 + 1e-9),
     checks.check_release_identities),
    ("a fate loss", ("release_r1", "cases", 3, "readouts", "int_D_R", 4), _times(1 + 1e-6),
     checks.check_release_identities),
    ("a held machine", (*CASE, "readouts", "F_pol", 1), _times(1 + 1e-9),
     checks.check_release_identities),
    ("a limit's survivors", ("release_r1", "limit_checks", "p=0.75, returned", "rows", 2,
                             "fate_d", "limit_survivors"), lambda v: repr(float(v) * 1.001),
     checks.check_release_limit),
    ("a requester figure", ("release_r1", "requester_figures", "surviving_durable",
                            "relative_distance"), _plus(1e-6), checks.check_release_limit),
    ("a cohort's route 1", ("release_r1", "cohorts", "p=0.25, held", "s", 1, "route1_blank"),
     _times(1 + 1e-6), checks.check_release_cohort),
    ("a convergence summary", ("release_r1", "cases", 5, "summary", "convergence_worst"),
     _plus(1e-8), checks.check_release_summaries),
    ("R2's short-lived row", ("release_r2", "runs", 0, "readouts", "n_R_s", 120),
     _times(1 + 1e-9), checks.check_release_r2),
    ("R2's second translation chain", ("release_r2", "runs", 1, "readouts", "int_Q_tl_s", 200),
     _times(1 + 1e-9), checks.check_release_r2),
    ("R2's development check", ("release_r2", "development_check", 2, "distance_to_A1", "P"),
     _times(1e3), checks.check_release_r2),
]


@pytest.mark.parametrize("path,edit,check", [p[1:] for p in RELEASE_PLANTED],
                         ids=[p[0] for p in RELEASE_PLANTED])
def test_release_planted_error_is_caught(rel, path, edit, check):
    holder, key = _at(rel, path)
    original = holder[key]
    try:
        holder[key] = edit(original)
        with pytest.raises(checks.CheckError):
            check(rel)
    finally:
        holder[key] = original
    check(rel)
