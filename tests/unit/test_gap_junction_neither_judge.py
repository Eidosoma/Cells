"""GJ-N1's reader and judge at their tag (D308), and the 25 x 25 field the registration adds to the
driver (validation/gap_junction_tissue/neither_judge.py, neither.py).

Every search and reference here is synthetic, written in the registered formats (neither.py's
search.json, points.jsonl and half_step.jsonl; the references' neither.json). Neither is the judged
run's or the code-blind references' output, which do not exist at the tag.
- The field: BITSEY's 1 x 25 x 25 lattice (625 cells, 1,200 junctions, the 6 x 6 corner tumor),
  its row-spread criterion (healthy_snapped_rows) and its first points.
- The committed neither_rule.json is what `rule` writes.
- A matching search passes. The plants: P-A1 (a reference 1% off fails A), P-A2 (inside the
  stated w/3 passes), P-R1 (a refused point fails), P-R2 (non-monotone is inconclusive), P-C1 (a
  flipped half step is inconclusive), and P-I1 to P-I3 (refused interfaces).
- BITSEY's saved logs, where present, are read as the reported rows.

No world is compiled or run: about 1 s.
"""

import copy
import json

import pytest

from validation.gap_junction_tissue import neither
from validation.gap_junction_tissue import neither_judge as nj

THRESHOLD = 2.0e-15  # A synthetic threshold, for the plants' arithmetic only.


def test_the_field_is_bitseys_lattice_and_criterion():
    cells, junctions, centres, neighbours = neither.tissue("field")
    assert (len(cells), len(junctions), len(centres), neighbours) == (625, 1200, 625, 4)
    tumor = {c for c, kind in cells if kind == "tumor"}
    assert tumor == {f"c{y}_{z}" for y in range(6) for z in range(6)}
    assert neither.TUMOR_CELLS_OF["field"] == [f"c{y}_{z}" for y in range(6) for z in range(6)]
    healthy_u, healthy_m = [84.0] * 625, [6.0] * 625
    assert neither.criterion(healthy_u, healthy_m, "field")["normalized"]
    spread = list(healthy_m)
    spread[3 * 25 + 7] = 8.5  # Cell c3_7: still E (84 > 10.5), but row z = 7 spreads 2.5.
    result = neither.criterion(healthy_u, spread, "field")
    assert result["epithelial_cells"] == 625 and not result["normalized"]
    assert result["rows_over_spread"] == 1
    assert neither.criterion(healthy_u[:25], spread[:25], "line")["normalized"]  # One cell a row.
    assert neither.first_points(4, "field") == [0.0, 1e-13, 6.25e-15, 3.125e-15]
    assert neither.first_points(4, "line") == [0.0, 1e-13, 5e-14, 2.5e-14]
    assert neither.step(6.25e-15, 4) == neither.BASE_DT_S > neither.step(1.25e-14, 4)


def test_the_references_spec_is_what_spec_writes_and_holds_no_seen_value():
    text = nj.SPEC_FILE.read_text()
    assert json.loads(text) == json.loads(json.dumps(nj.spec()))
    for seen in ("7.17", "7.18", "1.88", "1.89", "2.7e-14", "5.8e-13"):  # Thresholds, dev errors.
        assert seen not in text


def test_the_committed_rule_is_what_rule_writes():
    committed, written = json.loads(nj.RULE_FILE.read_text()), json.loads(json.dumps(nj.rule()))
    if not nj.SAVED_LOGS.is_dir():  # The saved logs' hashes are read from them where present.
        for data in (committed, written):
            for log in data["reported"]["logs"].values():
                log.pop("sha256", None)
    assert committed == written


def search(tmp_path, name, *, threshold=THRESHOLD, refused=(), flip=(), half_flip=False):
    """A synthetic engine search directory: a bisection of [0, 1e-13] to 1e-3 around threshold."""
    directory = tmp_path / name
    directory.mkdir()
    points, lo, hi = [], 0.0, neither.BRACKET[1]
    ds = [0.0, hi]
    while hi > (1.0 + neither.RTOL) * lo:
        mid = 0.5 * (lo + hi)
        ds.append(mid)
        if mid >= threshold:
            hi = mid
        else:
            lo = mid
    for d in ds:
        status = "failed" if d in refused else "done"
        normalized = (d >= threshold) != (d in flip)
        points.append(dict(d=d, status=status, normalized=normalized if status == "done" else None))
    halves = [
        dict(d=lo, status="done", normalized=half_flip),
        dict(d=hi, status="done", normalized=True),
    ]
    (directory / "search.json").write_text(json.dumps(dict(shape=name, lo=lo, hi=hi)))
    (directory / "points.jsonl").write_text("".join(json.dumps(p) + "\n" for p in points))
    (directory / "half_step.jsonl").write_text("".join(json.dumps(h) + "\n" for h in halves))
    return directory, lo, hi


def interface(lo, hi, *, constants=None):
    points = [dict(d=0.0, normalized=False), dict(d=neither.BRACKET[1], normalized=True),
              dict(d=lo, normalized=False), dict(d=hi, normalized=True)]  # fmt: skip
    geometry = dict(bracket=[lo, hi], points=points, method="synthetic",
                    tighter=dict(factor=10.0, lo_normalized=False, hi_normalized=True))  # fmt: skip
    model = dict(constants=constants or copy.deepcopy(nj.MODEL["constants"]))
    model["seeds"] = {k: dict(v) for k, v in nj.MODEL["seeds"].items() if k != "note"}
    return dict(
        format=nj.REFERENCE_FORMAT,
        model=model,
        geometries=dict(line=geometry, field=copy.deepcopy(geometry)),
    )


def read(tmp_path, data):
    directory = tmp_path / "interface"
    directory.mkdir(exist_ok=True)
    (directory / nj.INTERFACE_FILE).write_text(json.dumps(data))
    return nj.read_interface(directory)


def test_a_matching_search_passes_and_the_plants_are_caught(tmp_path):
    line, lo, hi = search(tmp_path, "line")
    result = nj.cells(line)
    assert result["R"] and result["C"]
    assert nj.judge(dict(line=result), read(tmp_path, interface(lo, hi)))["verdict"] == "passed"
    off = interface(lo * 1.01, hi * 1.01)  # P-A1
    verdict = nj.judge(dict(line=result), read(tmp_path, off))
    assert verdict["geometries"]["line"]["status"] == "failed"
    w = hi - lo  # P-A2: a reference just above Cells' bracket, inside hi + w/3.
    inside = interface(hi + 0.2 * w, (hi + 0.2 * w) * (1.0 + 0.5 * neither.RTOL))
    assert nj.judge(dict(line=result), read(tmp_path, inside))["verdict"] == "passed"
    refused, *_ = search(tmp_path, "refused", refused=(neither.BRACKET[1] / 2,))  # P-R1
    assert nj.judge(dict(line=nj.cells(refused)), None)["verdict"] == "failed"
    odd, *_ = search(tmp_path, "odd", flip=(neither.BRACKET[1] / 4,))  # P-R2
    verdict = nj.judge(dict(line=nj.cells(odd)), None)
    assert verdict["geometries"]["line"]["reason"] == "the outcomes are not monotone in D"
    flipped, *_ = search(tmp_path, "flipped", half_flip=True)  # P-C1
    verdict = nj.judge(dict(line=nj.cells(flipped)), None)
    assert verdict["geometries"]["line"]["status"] == "inconclusive"
    assert not nj.cells(flipped)["C"]


def test_refused_interfaces(tmp_path):
    lo, hi = THRESHOLD, THRESHOLD * 1.0005
    wide = interface(lo, lo * 1.01)  # P-I1
    with pytest.raises(nj.ComparisonError, match="wider"):
        read(tmp_path, wide)
    moved = interface(lo, hi)  # P-I2
    moved["geometries"]["field"]["tighter"]["lo_normalized"] = True
    with pytest.raises(nj.ComparisonError, match="tighter"):
        read(tmp_path, moved)
    constants = copy.deepcopy(nj.MODEL["constants"])  # P-I3
    constants["g_u"] = 4.0
    with pytest.raises(nj.ComparisonError, match="g_u"):
        read(tmp_path, interface(lo, hi, constants=constants))
    zero = interface(lo, hi)  # A seed echoed as BITSEY's 0 rather than the registered 1e-6.
    zero["model"]["seeds"]["tumor"]["u"] = 0.0
    with pytest.raises(nj.ComparisonError, match="seed tumor u"):
        read(tmp_path, zero)


@pytest.mark.skipif(not nj.SAVED_LOGS.is_dir(), reason="BITSEY's saved logs are not on this host")
def test_bitseys_saved_logs_are_reported(tmp_path):
    line, *_ = search(tmp_path, "line", threshold=7.1777e-15)
    rows = nj.bitsey_rows(nj.cells(line), [nj.SAVED_LOGS / "tumor_isolate_1D_V1M"])
    assert rows[0]["bracket"] == [7.171630859375002e-15, 7.177734375000002e-15]
    assert rows[0]["common_points"] == rows[0]["common_outcomes_agree"] > 10
