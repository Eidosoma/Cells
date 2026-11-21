"""Gene regulation's option A (G4): its comparison with G2's code-blind references, read from their
interface in the tree (validation/gene_regulation/references/interface/, data only), through
validation/gene_regulation/compare.py, and the readout tools' refusals (cohort.py, engine_run.py's
provenance). No world is compiled: the engine's side is the operator's own half-steps in NumPy
(validation/gene_regulation/kernel.py) over each world's first outputs.

- Every one of G2's 50 potential sets is exactly one of the sheet's (sheet_check.potential_sets),
  matched by the four values, so each engine run meets the reference of its own set.
- Over the first outputs at the test instance (a declared partial comparison), every readout G2
  holds is within 1e-4 of its scale (the sheet's §6: its largest magnitude over G2's horizon), and
  every heat class and G(t) - G(0) within 1e-6: a development bound, G6 registers the judged one.
  A wrong law moves a readout far beyond it; the sheet's plants move theirs by 1e-4 to 50%.
- G(t) - G(0), from the state alone, meets the booked heat within 1e-10 of the heat; the kernel's
  own file holds it to its inputs' rounding.
- The review's findings, each a row: a missing comparison is refused, never read as agreement (3);
  the completions are the product's own chain's, in both saved formats alike (2); a known rate
  holds at zero and near zero (6); a run's receipt freezes untracked source beside it (8).
"""

import json
import math
import subprocess
from pathlib import Path

import pytest

from validation.gene_regulation import cohort, compare, engine_run, kernel, worlds
from validation.gene_regulation import sheet_check as sheet

REFERENCES = compare.References()
TRAJECTORY_BOUND = 1e-4
HEAT_BOUND = 1e-6
SAVED = Path("/mnt/workspaces/Cells/gene-regulation-20261120")
SAVED_JSON = SAVED / "runs/dev-dt05-872a6a8e/test-instance/A1.json"  # engine_run.py, dt 0.5 s.
SAVED_CSV = SAVED / "a1-dev-export-20261120T202908Z/a1_export.csv"  # The A1 export, f96a9606.


def test_every_reference_set_is_one_sheet_set():
    sets = sheet.potential_sets(interior=True)
    found = {label: REFERENCES.find({k: str(v) for k, v in s.items()}) for label, s in sets.items()}
    assert sorted(found.values()) == sorted(REFERENCES.sets) == list(range(50))
    assert found["test instance"] == 0 and found["Spirin's E_pep"] == 1


# (world, horizon in seconds): five outputs or more each, every route of A1's but its regulator's
# coupling, which only the composite applies (A1 runs there: engine_run.py).
WORLDS = [("pol T=5", 150.0), ("two-gene", 150.0), ("rib n_R=10", 60.0)]


@pytest.mark.parametrize(("world", "horizon"), WORLDS)
def test_the_kernel_meets_the_references_over_the_first_outputs(world, horizon):
    spec, _, states, _ = kernel.run(kernel.truncated(worlds.world(world), horizon))
    times, values, checks = engine_run.readouts(spec, states)
    _, references = REFERENCES.sets[0]
    result = compare.gaps(dict(t=times, readouts=values), references[world], until=horizon)
    assert result["partial"] and result["matched_times"] == result["expected_times"] >= 5
    gaps = result["gaps"]
    assert len(gaps) >= 20
    heats = {k: v for k, v in gaps.items() if k.startswith("H_") or k == "G_minus_G0"}
    assert heats and max(heats.values()) <= HEAT_BOUND, heats
    worst = max(gaps, key=gaps.get)
    assert gaps[worst] <= TRAJECTORY_BOUND, (worst, gaps[worst])
    assert checks["G_identity_over_sum_H_at_end"] <= 1e-10


# ------------------------------------------------------------------ the review's findings


def _symbols(index):
    """An engine record's symbols (RT units) for G2's set `index`."""
    g, pd, pep, rc = REFERENCES.sets[index][0]
    return {"G_ATP": str(g / sheet.RT), "E_pd": str(pd / sheet.RT), "E_pep": str(pep / sheet.RT),
            "E_rc": str(rc)}  # fmt: skip


def _interior(edit=None):
    """An A1 record at interior set 18 holding G2's own values at the switch and the endpoint."""
    ends = REFERENCES.ends[18]
    t_off, t_end = REFERENCES.switch["A1"], REFERENCES.horizon["A1"]
    readouts = {n: [0.0, ends["A1 at t_off"][n], v] for n, v in ends["A1"].items()}
    record = dict(world="A1", set="interior 0", symbols_RT=_symbols(18), dt_s=0.5,
                  t=[0.0, t_off, t_end], readouts=readouts)  # fmt: skip
    if edit is not None:
        edit(record)
    return record


def _trajectory(edit):
    """The test instance's A1 record holding G2's own trajectory, edited."""
    reference = REFERENCES.sets[0][1]["A1"]
    readouts = json.loads(json.dumps(reference["readouts"]))
    record = dict(world="A1", set="test instance", symbols_RT=_symbols(0), dt_s=0.5,
                  t=list(reference["t"]), readouts=readouts)  # fmt: skip
    edit(record)
    return record


def _double_switch(r):
    r["readouts"]["n_P"][1] *= 2


def _lone_60_s(r):
    r["t"], r["readouts"] = [60.0], {n: [v[-1]] for n, v in r["readouts"].items()}


def _shift_grid(r):
    r["t"] = [t + 30.0 for t in r["t"]]
    r["readouts"] = {n: [5 * x for x in v] for n, v in r["readouts"].items()}


def _drop_readout(r):
    del r["readouts"]["n_P"]


def _protein_only(r):
    r["readouts"] = {"n_P": r["readouts"]["n_P"]}


def _not_finite(r):
    r["readouts"]["n_P"][-1] = float("nan")


# (case, the record, partial, readouts declared, the refusal's words, or the readout whose gap
# must be 1).
FINDING_3 = [
    ("the switch row doubled is caught", lambda: _interior(_double_switch), False, None, None,
     "n_P at t_off"),
    ("a protein-only record, its readout declared, is caught",
     lambda: _interior(lambda r: (_double_switch(r), _protein_only(r))), False, ["n_P"], None,
     "n_P at t_off"),
    ("a protein-only record, undeclared, is refused",
     lambda: _interior(lambda r: (_double_switch(r), _protein_only(r))), False, None,
     "are not in the run", None),
    ("a lone 60 s row is not the endpoint", lambda: _interior(_lone_60_s), False, None,
     "2 of 2 required times", None),
    ("a lone 60 s row, declared partial, compares nothing", lambda: _interior(_lone_60_s), True,
     None, "no required time", None),
    ("a disjoint grid is refused", lambda: _trajectory(_shift_grid), False, None, "361 of 361",
     None),
    ("a missing readout is refused", lambda: _trajectory(_drop_readout), False, None, "n_P", None),
    ("a non-finite value is refused", lambda: _trajectory(_not_finite), False, None, "nan", None),
]  # fmt: skip


@pytest.mark.parametrize(("case", "record", "partial", "readouts", "refused", "caught"),
                         FINDING_3, ids=[c[0] for c in FINDING_3])  # fmt: skip
def test_a_missing_comparison_is_refused_never_read_as_agreement(
    case, record, partial, readouts, refused, caught
):
    if refused is not None:
        with pytest.raises(compare.ComparisonError, match=refused):
            compare.compare_record(REFERENCES, record(), partial=partial, readouts=readouts)
        return
    result = compare.compare_record(REFERENCES, record(), partial=partial, readouts=readouts)
    assert result["matched_times"] == result["expected_times"] == 2
    assert result["gaps"][caught] == pytest.approx(1.0, rel=1e-12)
    assert max(v for k, v in result["gaps"].items() if k != caught) == 0.0
    assert result["readouts_declared"] == readouts and result["partial"] == (readouts is not None)
    exact = compare.compare_record(REFERENCES, _interior(), readouts=readouts)
    assert max(exact["gaps"].values()) == 0.0 and len(exact["gaps"]) == len(result["gaps"])


def _cohort(capsys, *args):
    assert cohort.main([str(a) for a in args]) == 0
    return json.loads(capsys.readouterr().out)


def test_the_producing_chain_is_resolved_from_the_product():
    makes = {"tx": "R", "tl": "P"}
    assert cohort.producing_chain(makes, "R") == "tx" and cohort.producing_chain(makes, "P") == "tl"
    assert cohort.producing_chain(makes, "R", "tx") == "tx"
    for chain_map, product, chain, words in (
        (makes, "R", "tl", "completes P, not R"),
        (makes, "X", None, "no chain makes X"),
        ({"tx1": "R", "tx2": "R"}, "R", None, "make R"),
        (makes, "R", "tz", "no chain 'tz'"),
    ):
        with pytest.raises(ValueError, match=words):
            cohort.producing_chain(chain_map, product, chain)


@pytest.mark.skipif(not (SAVED_JSON.exists() and SAVED_CSV.exists()),
                    reason="the saved A1 runs are not on this machine")  # fmt: skip
def test_the_completions_are_the_products_own_chain_in_both_saved_formats(capsys):
    window = ("--t1", 3600, "--t2", 5400)
    expected = {"R": (3.03679216635198e-07, 5.598289352600016e-08),  # tx's, as the CSV gives.
                "P": (2.016730173988118e-05, 1.3297652131140184e-05)}  # fmt: skip
    for product, (completed, surviving) in expected.items():
        found = [_cohort(capsys, path, "--product", product, *window)
                 for path in (SAVED_JSON, SAVED_CSV)]  # fmt: skip
        for out in found:
            assert out["completed_fmol"] == pytest.approx(completed, rel=1e-12)
            assert out["surviving_fmol"] == pytest.approx(surviving, rel=1e-12)
        assert found[0] == found[1]  # Format parity on the saved interval.
    for path in (SAVED_JSON, SAVED_CSV):
        with pytest.raises(SystemExit):
            cohort.main([str(path), "--product", "R", "--chain", "tl", *map(str, window)])
        assert "completes P, not R" in capsys.readouterr().err


def test_a_known_rate_holds_at_zero_and_near_zero(tmp_path, capsys):
    path = tmp_path / "one_fmol.csv"  # 1 fmol completed evenly over 1 s, nothing lost.
    path.write_text(
        "t_s,protein_P_fmol,released_tl_fmol,degraded_P_fmol\n0.0,1.0,0.0,0.0\n1.0,2.0,1.0,0.0\n"
    )
    for rate in ("0", "1e-18"):
        out = _cohort(capsys, path, "--t1", 0, "--t2", 1, f"--rate={rate}")
        assert out["surviving_known_rate_fmol"] == 1.0 and out["surviving_fmol"] == 1.0
    out = _cohort(capsys, path, "--t1", 0, "--t2", 1, "--rate=1e-3")
    assert out["surviving_known_rate_fmol"] == pytest.approx(-math.expm1(-1e-3) / 1e-3, rel=1e-15)
    with pytest.raises(SystemExit):
        cohort.main([str(path), "--t1", "0", "--t2", "1", "--rate=-1"])


def test_a_receipt_freezes_untracked_source_beside_the_run(tmp_path, monkeypatch):
    repo, run = tmp_path / "repo", tmp_path / "run"
    (repo / "validation").mkdir(parents=True)
    (repo / "validation" / "tracked.py").write_text("A = 1\n")

    def git(*args):
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@invalid",
                        *args], check=True, capture_output=True)  # fmt: skip

    git("init", "-q")
    git("add", "validation/tracked.py")
    git("commit", "-q", "-m", "tracked")
    (repo / "validation" / "untracked.py").write_text("B = 2\n")
    monkeypatch.setattr(engine_run, "ROOT", repo)
    with pytest.raises(RuntimeError, match="would not be recorded"):
        engine_run.provenance()
    run.mkdir()
    record, patch = engine_run.provenance(run)
    assert record["untracked_sources"]["files"] == ["validation/untracked.py"]
    frozen = run / "untracked-sources" / "validation" / "untracked.py"
    assert frozen.read_text() == "B = 2\n" and patch == ""  # No tracked change to diff.
