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
from validation.gene_regulation import cohort, compare, engine_run, kernel, release_check, worlds
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
    # FR-38: with a release, a fate row's inflow is the release's (§9.8's route 2), never the
    # chain's completions, which join its hold, though the durable fate is the chain's product.
    fates = [dict(durable="R", short_lived="R_s")]
    tx = dict(id="tx", product="R", release=dict(id="rel", fates=fates))
    makes, counters = cohort.producers([tx, dict(id="tl", product="P")])
    assert makes == {"rel_durable": "R", "rel_short_lived": "R_s", "tl": "P"}
    assert cohort.producing_chain(makes, "R") == "rel_durable"
    assert counters["rel_short_lived"] == "int_Q_rel_short_lived" and "tx" not in counters


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


K_SHORT = math.log(2) / 1800.0  # R1's short-lived loss (1/s).
# The route-2 survival check fails closed (the Lean lane's finding at a6acbc27): (case, outputs
# every s, release rate in copies/s during R1's window, first-order loss 1/s, ok, status).
SURVIVAL = [
    ("sparse", 3600, 1 / 360, 0.0, False, "insufficient resolution"),
    ("resolved lossless", 60, 1 / 360, 0.0, False, "compared"),
    ("empty cohort", 60, 0.0, K_SHORT, False, "empty cohort"),
    ("resolved first-order", 60, 1 / 360, K_SHORT, True, "compared"),
    # The Lean lane's turnover_roundoff control: constant turnover through the run (releases equal
    # losses, the amount steady), where the known-rate form is exact on any grid and its grid error
    # exactly zero; the ratio's own rounding (one ulp above 1/4) once failed a zero bound.
    ("steady turnover, zero grid error", 60, None, None, True, "compared"),
]


@pytest.mark.parametrize(("case", "every", "inflow", "loss", "ok", "status"), SURVIVAL,
                         ids=[c[0] for c in SURVIVAL])  # fmt: skip
def test_the_survival_check_fails_closed(case, every, inflow, loss, ok, status, tmp_path):
    """release_check.survival on synthetic counters of R1's short-lived fate R_s (a trace of 10
    copies, the window's releases at `inflow`, first-order loss), against e^(-k_s 3600 s) = 1/4,
    no world compiled. Route 2 carries the releases at the definition's gross k_s (erratum F).
    Outputs too far apart for a grid error are insufficient resolution, not a pass (a lossless
    ratio of 1 passed before); an empty cohort is reported, not raised (it was a
    ZeroDivisionError); a resolved lossless record fails as compared, since its booked net loss
    disagrees with the declared k_s; a first-order one passes."""
    from cells.operators.templated_polymerisation import COPY_FMOL

    t1, t2 = worlds.R1_WINDOW
    t = [float(x) for x in range(0, int(2 * t2) + 1, every)]
    n0 = 10.0
    if inflow is None:  # Steady turnover at the definition's gross k, through the whole record.
        k = release_check.gross_rate({"definition": worlds.r1(0.75), "cell": "cell_0"}, "R_s")
        made = [n0 * COPY_FMOL * k * s for s in t]
        readouts = {"n_R_s": [n0 * COPY_FMOL + q - q for q in made],
                    "int_Q_tx_release_short_lived": made, "int_D_R_s": list(made)}  # fmt: skip
        path = tmp_path / "record.json"
        path.write_text(json.dumps(dict(definition=worlds.r1(0.75), cell="cell_0", t=t,
                                        readouts=readouts)))  # fmt: skip
        checks = release_check.Checks()
        release_check.survival(checks, case, path, "R_s", "short_lived")
        (row,) = checks.rows
        assert (row["ok"], row["status"]) == (ok, status), row
        return

    def alive(s):
        made = inflow * min(s, t2)
        if loss == 0.0:
            return n0 + made
        inside = n0 * math.exp(-loss * min(s, t2)) - inflow / loss * math.expm1(-loss * min(s, t2))
        return inside * math.exp(-loss * max(s - t2, 0.0))

    n = [alive(s) * COPY_FMOL for s in t]
    Q = [inflow * min(s, t2) * COPY_FMOL for s in t]
    D = [0.0 if loss == 0.0 else n0 * COPY_FMOL + q - x for q, x in zip(Q, n, strict=True)]
    readouts = {"n_R_s": n, "int_Q_tx_release_short_lived": Q, "int_D_R_s": D}
    path = tmp_path / "record.json"
    path.write_text(json.dumps(dict(definition=worlds.r1(0.75), cell="cell_0", t=t,
                                    readouts=readouts)))  # fmt: skip
    checks = release_check.Checks()
    release_check.survival(checks, case, path, "R_s", "short_lived")
    (row,) = checks.rows
    assert (row["ok"], row["status"]) == (ok, status), row
    assert row["closed_form_ratio"] == pytest.approx(0.25, rel=1e-12)


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
    # FR-38's survival readout (the requester's answer): FR-25's turnover control, 100 copies with
    # a one-hour half-life, the first hour's completions alive at 1 h and 2 h, and their ratio, a
    # half; None where nothing was completed.
    hour, k = 3600.0, math.log(2) / 3600.0
    t = [i * 60.0 for i in range(121)]
    n, made = [100.0] * len(t), [100 * k * s for s in t]
    counted = cohort.survival(t, n, made, made, 0.0, hour, 2 * hour)
    assert counted["alive_at_window_end"] == pytest.approx(50.0, rel=1e-4)
    assert counted["ratio"] == pytest.approx(0.5, rel=1e-12)
    assert cohort.survival(t, n, [0.0] * len(t), made, 0.0, hour, 2 * hour)["ratio"] is None


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


def _release_world():
    """R1 at p = 0.5 to 60 s, its short-lived fate R_s with no loss route (deg_R_s dropped)."""
    raw = kernel.truncated(worlds.r1(0.5), 60.0)
    block = kernel.block(raw)
    block["degradations"] = [d for d in block["degradations"] if d["polymer"] != "R_s"]
    raw["experiment"]["polymerisation_controls"] = [
        c for c in raw["experiment"]["polymerisation_controls"] if c["route_id"] != "deg_R_s"
    ]
    return raw


# (case, the lossless world, its lossless row, a world whose row's loss route is declared, it).
LOSSLESS = [
    ("protein", lambda: _protein_world(lossless=True), "P", _protein_world, "P"),
    # The Lean lane's finding (22 November 2026): a release's fate row without a loss route
    # read as a product's does, its zero series exported.
    ("release fate", _release_world, "R_s", _release_world, "R"),
    # And with FR-42's labels on the fate rows: the label owner moves nothing (about 1 s).
    (
        "labelled fate",
        lambda: worlds.with_share_labels(_release_world(), window=(0.0, 30.0)),
        "R_s",
        _release_world,
        "R",
    ),
]


@pytest.mark.parametrize(("case", "lossless", "row", "lossy", "declared"), LOSSLESS,
                         ids=[c[0] for c in LOSSLESS])  # fmt: skip
def test_a_lossless_product_reads_a_zero_loss_series(
    case, lossless, row, lossy, declared, tmp_path
):
    """D265, finding 7: with the protein's degradation route removed the export omitted int_D_P,
    and the reader raised KeyError; likewise a release's fate row (int_D_R_s); a declared loss
    route's missing counter is still refused."""
    path, values = _record(lossless(), tmp_path)
    assert values[f"int_D_{row}"] == [0.0] * len(values[f"n_{row}"])
    t, n, Q, D = cohort.read(path, row)
    completed, surviving, _ = cohort.survivors(t, n, Q, D, 0.0, 60.0)
    assert completed > 0 and surviving == pytest.approx(completed, rel=1e-12)  # Nothing is lost.
    lossy, _ = _record(lossy(), tmp_path)
    record = json.loads(lossy.read_text())
    del record["readouts"][f"int_D_{declared}"]
    lossy.write_text(json.dumps(record))
    with pytest.raises(ValueError, match=f"deg_{declared}"):
        cohort.read(lossy, declared)


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


def _engine_triple(world, *, offsets=None, orders=None):
    """Three synthetic engine records of a world at the test instance, steps 2, 1 and 0.5 s: G2's
    trajectory plus a step error 1e-6 scale h^p at each readout's declared order (or `orders`), at
    rounding size (1e-14 scale h^p) for J_bar as in the development runs, plus `offsets` (a model
    error, the same at every step)."""
    from validation.gene_regulation import registration

    reference = REFERENCES.sets[0][1][world]
    names = [n for n in reference["readouts"] if not compare.not_exported(n)]
    triple = []
    for h in registration.STEPS:
        readouts = {}
        for name in names:
            values = reference["readouts"][name]
            scale = max(abs(v) for v in values) or 1.0
            p = (orders or {}).get(name) or registration.P_DECLARED[
                (registration.kind(world), registration.klass(name))][0]  # fmt: skip
            size = 1e-14 if name.startswith("J_bar") else 1e-6
            shift = size * scale * h**p + (offsets or {}).get(name, 0.0) * scale
            readouts[name] = [v + shift for v in values]
        triple.append({("test instance", world): dict(
            world=world, set="test instance", symbols_RT=_symbols(0), dt_s=h,
            t=list(reference["t"]), readouts=readouts)})  # fmt: skip
    return triple


# (case, offsets, orders, FR-25's verdict, the readout that decides it).
REGISTRATION = [
    ("step error alone passes", None, None, "passed", None),
    ("a model error beyond 3 est fails", {"n_R": 1e-5}, None, "failed", "n_R"),
    ("an order below p - 0.5 is inconclusive", None, {"n_R": 1}, "inconclusive", "n_R"),
    ("an order above 3.5 is inconclusive", None, {"n_R": 4}, "inconclusive", "n_R"),
]  # fmt: skip


@pytest.mark.parametrize(("case", "offsets", "orders", "verdict", "decides"), REGISTRATION,
                         ids=[c[0] for c in REGISTRATION])  # fmt: skip
def test_the_registration_judges_from_step_error_alone(case, offsets, orders, verdict, decides):
    """FR-25's registered tolerance (validation/gene_regulation/registration.py, D268), on synthetic
    triples built from G2's pol T=5 trajectory (no world compiled). J_bar's step error is at
    rounding size, so it is judged at the floor in every case, its order unchecked."""
    from validation.gene_regulation import registration

    coarse, middle, fine = _engine_triple("pol T=5", offsets=offsets, orders=orders)
    table = registration.table(coarse, middle, fine)
    result = registration.judge(table, fine, REFERENCES)
    assert result["verdict"] == verdict
    (world,) = result["worlds"].values()
    assert world["matched_times"] == world["expected_times"] == 121
    if verdict != "inconclusive":  # An inconclusive world's tolerances are not sound to fail by.
        assert world["failed"] == ([decides] if verdict == "failed" else [])
    assert world["outside_window"] == ([decides] if verdict == "inconclusive" else [])
    entry = table["worlds"]["test instance | pol T=5"]["readouts"]["J_bar_tx"]
    assert entry["at_floor"] and entry["order"] is not None  # Its order is not checked.
    assert world["effective_factors"]["J_bar_tx"] is None
    if verdict == "passed":  # At the declared order the effective factor is F itself.
        assert world["effective_factors"]["n_R"] == pytest.approx(3.0, rel=1e-6)


# ------------------------------------------------------------------ the cohort readers fail closed
SERIES = dict(t=[0.0, 1.0, 2.0, 3.0], Q=[0.0, 0.5, 1.0, 1.5], k_f=0.1, forward=[0.0, 0.1, 0.2, 0.3],
              n_c=[1.0, 1.1, 1.2, 1.3], backward=[0.0, 0.0, 0.01, 0.02], n_o=[0.0, 0.1, 0.2, 0.3],
              k_o=0.05, t1=0.0, t2=2.0, ts=3.0)  # fmt: skip

# (case, the series' edit, the refusal's words; None for the valid case).
COHORT_READERS = [
    ("valid series", {}, None),
    ("a negative fate rate", {"k_f": -0.1}, "k_f = -0.1"),
    ("a NaN outside rate", {"k_o": float("nan")}, "k_o = nan"),
    ("a decreasing export counter", {"forward": [0.0, 0.2, 0.1, 0.3]}, "decreases"),
    ("a return from an empty node", {"n_o": [0.0, 0.0, 0.0, 0.0], "forward": [0.0, 0.0, 0.0, 0.0]},
     "empty pool"),
]  # fmt: skip


@pytest.mark.parametrize(("case", "edit", "words"), COHORT_READERS,
                         ids=[c[0] for c in COHORT_READERS])  # fmt: skip
def test_the_cohort_readers_fail_closed(case, edit, words):
    """Host only, no world compiled (a validation fix's row, D224):
    - known_rate_error is None, never 0.0, where the release window holds no output to drop;
      at a constant rate an output dropped after the window alone changes nothing, so it once
      reported an exact zero for an unresolved window (on 0, 60, 120, 180, 240 s, the window [60,
      120] and the sample at 240);
    - series refuses an invalid rate or counter and an export from an empty pool, and series_error
      bounds both parts."""
    t, Q = [0.0, 60.0, 120.0, 180.0, 240.0], [0.0, 0.0, 10.0, 10.0, 10.0]
    assert cohort.known_rate_error(t, Q, 0.02, 60.0, 120.0, 240.0) is None
    assert cohort.known_survival(t, Q, 0.02, 60.0, 120.0, 240.0)["grid_error_at_sample"] is None
    fine_t, fine_Q = [0.0, 30.0, 60.0, 90.0, 120.0, 240.0], [0.0, 0.0, 0.0, 6.0, 10.0, 10.0]
    assert cohort.known_rate_error(fine_t, fine_Q, 0.02, 60.0, 120.0, 240.0) > 0.0
    args = dict(SERIES, **edit)
    if words is None:
        cell, node = cohort.series(**args)
        assert 0.0 < node < cell
        assert cohort.series_error(**args) is None or cohort.series_error(**args) >= 0.0
    else:
        with pytest.raises(ValueError, match=words):
            cohort.series(**args)
