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

import copy
import importlib
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from cells.definitions.specs import parse_spec
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


def _interior_pol():
    """pol T=1 at interior set 18 holding G2's own values at its one required row, t_end (the
    independent checker's repro/compare_partial_zero.py)."""
    ends = REFERENCES.ends[18]["pol T=1"]
    readouts = {n: [v] for n, v in ends.items()}
    return dict(world="pol T=1", set="interior 0", symbols_RT=_symbols(18), dt_s=0.5,
                t=[REFERENCES.horizon["pol T=1"]], readouts=readouts)  # fmt: skip


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
    ("J_bar alone, declared partial, leaves no readout", _interior_pol, True, ["J_bar_tx"],
     "no readout left", None),
    ("an empty declaration leaves no readout", _interior, False, [], "no readout left", None),
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


# (case, the untracked file, imported by the run, what the receipt must name).
RECEIPTS = [
    ("an untracked module under validation/, frozen", "validation/untracked.py", False,
     "untracked_sources"),
    ("an untracked script at the repository root, recorded", "root_driver_gr_receipt.py", True,
     "untracked_executed"),
]  # fmt: skip


@pytest.mark.parametrize(("case", "relative", "imported", "named"), RECEIPTS,
                         ids=[c[0] for c in RECEIPTS])  # fmt: skip
def test_a_receipt_names_untracked_source_or_is_refused(
    case, relative, imported, named, tmp_path, monkeypatch
):
    """Finding 8 and the independent checker's root-level case (D259): with an output folder the
    receipt names the untracked source and holds its bytes; without one the run is refused."""
    repo, run = tmp_path / "repo", tmp_path / "run"
    (repo / "validation").mkdir(parents=True)
    (repo / "validation" / "tracked.py").write_text("A = 1\n")

    def git(*args):
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@invalid",
                        *args], check=True, capture_output=True)  # fmt: skip

    git("init", "-q")
    git("add", "validation/tracked.py")
    git("commit", "-q", "-m", "tracked")
    path = repo / relative
    path.write_text("B = 'the untracked source'\n")
    if imported:  # The run executes it, as a driver at the root would be.
        monkeypatch.syspath_prepend(str(path.parent))
        monkeypatch.delitem(sys.modules, path.stem, raising=False)
        importlib.import_module(path.stem)
        monkeypatch.setitem(sys.modules, path.stem, sys.modules[path.stem])
    monkeypatch.setattr(engine_run, "ROOT", repo)
    with pytest.raises(RuntimeError, match="not track|would not be recorded"):
        engine_run.provenance()
    run.mkdir()
    record, patch = engine_run.provenance(run)
    if named == "untracked_sources":
        assert record["untracked_sources"]["files"] == [relative]
        frozen = run / "untracked-sources" / relative
        assert frozen.read_text() == "B = 'the untracked source'\n"
        assert record["untracked_executed"] == [] and patch is None
    else:
        assert record["untracked_executed"] == [relative] and "untracked_sources" not in record
        assert "the untracked source" in patch and f"?? {relative}" in record["checkout_status"]


# ------------------------------------------------------------------ D264's findings 3 to 6


def _two_cell(raw, *, reverse=False, routes="cell_1"):
    """raw with a second cell, cell_1, a copy of cell_0 with its own patch to the bath, and the
    operator's routes moved to `routes` (all of them, or {"degradations": cell} for some); with
    reverse, only the cells' declaration order reversed."""
    out = copy.deepcopy(raw)
    m, e, x = out["model"], out["experiment"], out["execution"]
    cell = dict(copy.deepcopy(m["cells"][0]), id="cell_1")
    patch = dict(copy.deepcopy(m["membranes"][0]), id="patch_1", inside="cell_1")
    m["cells"].append(cell)
    m["membranes"].append(patch)
    e["membrane_controls"].append(
        dict(membrane_id="patch_1", schedule=[dict(time=0.0, availability=1.0)])
    )
    x["capacity"], x["membrane_capacity"] = 2, 2
    block = kernel.block(out)
    moves = routes if isinstance(routes, dict) else dict.fromkeys(
        ("pools", "degradations", "transfers"), routes)  # fmt: skip
    for key, where in moves.items():
        for item in block[key]:
            item["cell"] = where
    if reverse:
        m["cells"] = m["cells"][::-1]
    return out


def test_the_export_follows_the_cell_by_its_id_not_its_position():
    """D264, finding 3: the expressing cell is cell_1; reversing only the cells' declaration order
    changes nothing exported."""
    raw = kernel.truncated(worlds.world("pol T=5"), 120.0)
    found = []
    for reverse in (False, True):
        spec, _, states, _ = kernel.run(_two_cell(raw, reverse=reverse))
        times, values, checks = engine_run.readouts(spec, states)
        assert checks["exported_cell"] == "cell_1"
        found.append(values)
    assert found[0] == found[1]
    assert (
        found[0]["n_R"][-1] > 1e3 * found[0]["n_R"][0]
    )  # The expressing cell's RNA, not the trace.
    split = _two_cell(
        raw, routes={"pools": "cell_1", "degradations": "cell_0", "transfers": "cell_1"}
    )
    spec = parse_spec(split)
    (block,) = [d for d in spec.model.operators if d.law == worlds.POLYMERISATION]
    with pytest.raises(ValueError, match="name the cell"):
        engine_run.exported_cell(spec, block)
    assert engine_run.exported_cell(spec, block, "cell_0") == "cell_0"


def _two_loss_routes(raw):
    """raw with deg_R split into two routes at half its rate each."""
    out = copy.deepcopy(raw)
    block = kernel.block(out)
    second = dict(copy.deepcopy(block["degradations"][0]), id="deg_R_b")
    block["degradations"].append(second)
    controls = out["experiment"]["polymerisation_controls"]
    (rate,) = [c for c in controls if c["route_id"] == "deg_R"]
    rate["schedule"][0]["value"] /= 2
    controls.append(dict(route_id="deg_R_b", schedule=copy.deepcopy(rate["schedule"])))
    return out


def test_two_loss_routes_are_summed_once_and_close_the_rna_account():
    """D264, finding 4: one loss reading per output; production minus loss is the RNA's change;
    the survivors equal those of one route at the full rate."""
    raw = kernel.truncated(worlds.world("pol T=5"), 150.0)
    survived = []
    for world in (raw, _two_loss_routes(raw)):
        spec, _, states, _ = kernel.run(world)
        t, x, _ = engine_run.readouts(spec, states)
        assert len(x["int_D_R"]) == len(t)
        routes = [k for k in x if k.startswith("int_D_route_")]
        for k in range(len(t)):
            assert x["int_D_R"][k] == math.fsum(x[r][k] for r in routes)
            change = x["n_R"][k] - x["n_R"][0]
            assert abs(x["int_Q_tx"][k] - x["int_D_R"][k] - change) <= 1e-12 * max(x["n_R"])
        survived.append(cohort.survivors(t, x["n_R"], x["int_Q_tx"], x["int_D_R"], 30.0, 150.0))
    assert survived[1] == pytest.approx(survived[0], rel=1e-12)


def _fast_turnover(times, n0=100.0, k=1.0, P=1.0):
    """Exact counters of a pool starting at n0 unlabelled, cleared at k, fed at P (the tester's)."""
    n = [n0 * math.exp(-k * s) + P / k * -math.expm1(-k * s) for s in times]
    Q = [P * s for s in times]
    return list(times), n, Q, [q + n0 - m for q, m in zip(Q, n, strict=True)]


def test_survivors_are_bounded_by_the_pool_and_coarse_grids_are_flagged(tmp_path, capsys):
    """D264, finding 5: from two exact observations, 0 and 8 s, the reader gave 3.32347 fmol
    labelled where 1.03321 fmol remained (exact 0.99966) and a zero grid error."""
    t, n, Q, D = _fast_turnover([0.0, 8.0])
    with pytest.raises(ValueError, match="exceeds the pool"):
        cohort.survivors(t, n, Q, D, 0.0, 8.0)
    assert cohort.grid_error(t, n, Q, D, 0.0, 8.0) is None  # Not estimable, never 0.
    path = tmp_path / "slow.csv"  # Two samples within the bound: reported, and flagged.
    path.write_text("t_s,protein_P_fmol,released_tl_fmol,degraded_P_fmol\n"
                    "0.0,1.0,0.0,0.0\n1.0,1.4,0.5,0.1\n")  # fmt: skip
    out = _cohort(capsys, path, "--t1", 0, "--t2", 1)
    assert out["grid_error_fmol"] is None and out["time_resolution"].startswith("insufficient")
    assert out["surviving_fmol"] <= 1.4
    t, n, Q, D = _fast_turnover([k * 0.1 for k in range(81)])  # Resolved: within its grid error.
    _, labelled, _ = cohort.survivors(t, n, Q, D, 0.0, 8.0)
    assert abs(labelled - -math.expm1(-8.0)) <= cohort.grid_error(t, n, Q, D, 0.0, 8.0)


# (case, the counters' edit, t1, t2, ts, the refusal's words).
FINDING_6 = [
    ("a NaN loss counter", lambda s: s[3].__setitem__(1, float("nan")), 0.0, 3.0, None, "nan"),
    ("a decreasing loss counter", lambda s: s[3].__setitem__(2, 0.0), 0.0, 3.0, None, "decreases"),
    ("a decreasing completion counter", lambda s: s[2].__setitem__(2, 0.0), 0.0, 3.0, None,
     "decreases"),
    ("a reversed labelling window", None, 2.0, 1.0, None, "t1 <= t2 <= ts"),
    ("a sample before the window's end", None, 0.0, 2.0, 1.0, "t1 <= t2 <= ts"),
    ("a doubled loss series", lambda s: s[3].extend(s[3]), 0.0, 3.0, None, "8 values for 4"),
]  # fmt: skip


@pytest.mark.parametrize(("case", "edit", "t1", "t2", "ts", "words"), FINDING_6,
                         ids=[c[0] for c in FINDING_6])  # fmt: skip
def test_invalid_counters_and_windows_are_refused(case, edit, t1, t2, ts, words):
    """D264, finding 6: a NaN or decreasing counter gave 100% survival and a zero grid error, and
    a reversed window negative completions."""
    series = (
        [0.0, 1.0, 2.0, 3.0],
        [1.0, 1.1, 1.2, 1.3],
        [0.0, 0.5, 1.0, 1.5],
        [0.0, 0.1, 0.2, 0.3],
    )
    if edit is not None:
        edit(series)
    for reader in (cohort.survivors, cohort.grid_error):
        with pytest.raises(ValueError, match=words):
            reader(*series, t1, t2, ts)


# ------------------------------------------------------------------ D265's findings 9, 3, 7 and 8


def test_a_loaded_ignored_source_marks_the_receipt_dirty(tmp_path, monkeypatch):
    """D265, finding 9: an imported, Git-ignored fixture was recorded in the patch but with
    checkout_dirty false and an empty status (main's c180c1bc lists it as "!!")."""
    repo, run = tmp_path / "repo", tmp_path / "run"
    (repo / "runs").mkdir(parents=True)
    (repo / ".gitignore").write_text("runs/\n")

    def git(*args):
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@invalid",
                        *args], check=True, capture_output=True)  # fmt: skip

    git("init", "-q")
    git("add", ".gitignore")
    git("commit", "-q", "-m", "base")
    path = repo / "runs" / "gr_ignored_fixture_d265.py"
    path.write_text("C = 'the ignored source'\n")
    monkeypatch.syspath_prepend(str(path.parent))
    monkeypatch.delitem(sys.modules, path.stem, raising=False)
    monkeypatch.setitem(sys.modules, path.stem, importlib.import_module(path.stem))
    monkeypatch.setattr(engine_run, "ROOT", repo)
    with pytest.raises(RuntimeError, match="not track"):
        engine_run.provenance()
    run.mkdir()
    record, patch = engine_run.provenance(run)
    relative = "runs/gr_ignored_fixture_d265.py"
    assert record["untracked_executed"] == [relative] and "the ignored source" in patch
    assert record["checkout_dirty"] is True and f"!! {relative}" in record["checkout_status"]


def _switch_rows(r, second):
    """The interior record with a second row at the switch: "same" repeats the switch row,
    "reference" holds G2's values there, and "near" holds G2's values 0.4 us later."""
    i = r["t"].index(REFERENCES.switch["A1"])
    r["t"].insert(i + 1, r["t"][i] + (4e-7 if second == "near" else 0.0))
    for name, values in r["readouts"].items():
        values.insert(i + 1, values[i] if second == "same" else
                      REFERENCES.ends[18]["A1 at t_off"][name])  # fmt: skip


# (case, the edit, the refusal's words, or the gap of n_P at t_off).
FINDING_3_DUPLICATES = [
    ("a doubled switch row beside a reference one is refused",
     lambda r: (_double_switch(r), _switch_rows(r, "reference")), "disagree in n_P", None),
    ("an agreeing duplicate switch row collapses", lambda r: (_double_switch(r),
     _switch_rows(r, "same")), None, 1.0),
    ("a reference row 0.4 us after the switch is its own", lambda r: (_double_switch(r),
     _switch_rows(r, "near")), None, 1.0),
]  # fmt: skip


@pytest.mark.parametrize(("case", "edit", "refused", "gap"), FINDING_3_DUPLICATES,
                         ids=[c[0] for c in FINDING_3_DUPLICATES])  # fmt: skip
def test_each_required_time_has_one_engine_row(case, edit, refused, gap):
    """D265, finding 3: a second switch row holding the reference value turned the doubled row's
    gap of 1.0 into 0.0, and two times 0.4 us apart collided in the six-decimal index."""
    record = _interior(edit)
    if refused is not None:
        with pytest.raises(compare.ComparisonError, match=refused):
            compare.compare_record(REFERENCES, record)
        return
    result = compare.compare_record(REFERENCES, record)
    assert result["gaps"]["n_P at t_off"] == pytest.approx(gap, rel=1e-12)
    assert result["matched_times"] == result["expected_times"] == 2


def _protein_world(*, lossless=False, two_cells=False):
    """rib n_R=10 to 60 s; lossless drops deg_P; two_cells gives cell_1 its own ribosomes and chain
    making P, beside cell_0's."""
    raw = kernel.truncated(worlds.world("rib n_R=10"), 60.0)
    block = kernel.block(raw)
    if lossless:
        block["degradations"] = []
        raw["experiment"]["polymerisation_controls"] = [
            c for c in raw["experiment"]["polymerisation_controls"] if c["route_id"] != "deg_P"
        ]
    if two_cells:
        raw = _two_cell(raw, routes={})
        block = kernel.block(raw)
        block["pools"].append(dict(copy.deepcopy(block["pools"][0]), id="rib_1", cell="cell_1"))
        block["chains"].append(dict(copy.deepcopy(block["chains"][0]), id="tl_1", pool="rib_1"))
        rate = next(
            c for c in raw["experiment"]["polymerisation_controls"] if c["route_id"] == "tl"
        )
        raw["experiment"]["polymerisation_controls"].append(
            dict(copy.deepcopy(rate), route_id="tl_1")
        )
    return raw


def _record(raw, tmp_path, cell=None):
    spec, _, states, _ = kernel.run(raw)
    times, values, checks = engine_run.readouts(spec, states, cell)
    path = tmp_path / f"run-{len(list(tmp_path.iterdir()))}.json"
    path.write_text(json.dumps(dict(t=times, readouts=values, cell=checks["exported_cell"],
                                    definition=raw)))  # fmt: skip
    return path, values


def test_a_lossless_product_reads_a_zero_loss_series(tmp_path):
    """D265, finding 7: with the protein's degradation route removed the export omitted int_D_P,
    and the reader raised KeyError; a declared loss route's missing counter is still refused."""
    path, values = _record(_protein_world(lossless=True), tmp_path)
    assert values["int_D_P"] == [0.0] * len(values["n_P"])
    t, n, Q, D = cohort.read(path, "P")
    completed, surviving, _ = cohort.survivors(t, n, Q, D, 0.0, 60.0)
    assert surviving == completed > 0  # Nothing is lost.
    lossy, _ = _record(_protein_world(), tmp_path)
    record = json.loads(lossy.read_text())
    del record["readouts"]["int_D_P"]
    lossy.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="deg_P"):
        cohort.read(lossy, "P")


def test_the_reader_resolves_the_chain_at_the_exported_cell(tmp_path):
    """D265, finding 8: two cells each with a chain making P; the record exports cell_0; the reader
    saw two chains, and naming the other cell's raised KeyError."""
    path, _ = _record(_protein_world(two_cells=True), tmp_path, cell="cell_0")
    t, n, Q, D = cohort.read(path, "P")
    assert Q == json.loads(path.read_text())["readouts"]["int_Q_tl"]
    with pytest.raises(ValueError, match="tl_1 is in cell_1"):
        cohort.read(path, "P", "tl_1")


def test_the_per_cell_rna_readout_meets_its_two_controls():
    """FR-25's backlog controls (validation/gene_regulation/rna_readouts.py), through the
    operator's NumPy half-steps (no world compiled; about 4 s): the turnover control (the total
    stays at 100; of 69.31 marked, 50 at the marked hour's end, 25 an hour later) and the
    responding-cells control ([0, 0, 20, 20] against [10, 10, 10, 10] at a one-copy threshold)."""
    from validation.gene_regulation import rna_readouts

    turnover = rna_readouts.turnover_control()
    found, expected = turnover["found"], turnover["expected"]
    assert abs(found["total_min"] - 100.0) <= 1e-4 and abs(found["total_max"] - 100.0) <= 1e-4
    for key in ("marked", "at_end", "hour_later"):
        assert found[key] == pytest.approx(expected[key], rel=1e-5), key
    groups = rna_readouts.responding_cells_control()
    for name, mean, positive, positive_mean in (("A", 10.0, 0.5, 20.0), ("B", 10.0, 1.0, 10.0)):
        g = groups[name]
        assert g["new_per_cell"] == pytest.approx(g["expected_new"], rel=1e-5, abs=1e-9)
        assert g["mean"] == pytest.approx(mean, rel=1e-5)
        assert g["positive_fraction"] == positive
        assert g["positive_mean"] == pytest.approx(positive_mean, rel=1e-5)
