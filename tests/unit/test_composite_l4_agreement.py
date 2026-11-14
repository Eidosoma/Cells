"""The L4 agreement driver's CPU-only parts (validation/tissue/composite_l4_agreement.py).

Terms of the three L4 repeats, the variant rule, the stop rule, the variant protocols and
the judged run's deviation, on synthetic saved runs against the registered W1, W2 and G2-Q1
protocols (no engine run).
"""

import copy
import json

import pytest

from validation.tissue import composite_l4_agreement as agreement

W7 = "W7/literature"


def w1_run(volume=1.0, converged=True):
    return dict(
        trajectories={"P1": {"0.0": {"cell_volume_pL": [volume]}}},
        stationary={"H": dict(converged=converged, volume_pL=0.7, membrane_voltage_V=-0.05)},
    )


def w2_run(classification="stable", voltage=-0.08):
    return {
        "red_cell_15-kaji_s0.12": {
            "0": dict(
                converged=True,
                classification=classification,
                volume_pL=0.7,
                membrane_voltage_V=voltage,
                route_cycles_fmol_s=3e-5,
            )
        }
    }


def g2_run(voltage=-0.05):
    record = dict(
        time_s=0.0, membrane_voltage_V=[voltage, -0.06], slot_amount_fmol={"1": [1.0, 2.0]}
    )
    return {W7: [record]}


def executions(tree):
    """Every execution block in a predictions tree."""
    if isinstance(tree, list):
        return [e for v in tree for e in executions(v)]
    if not isinstance(tree, dict):
        return []
    found = [tree["execution"]] if isinstance(tree.get("execution"), dict) else []
    return found + [e for v in tree.values() for e in executions(v)]


@pytest.mark.parametrize("part", ["w1", "w2", "g2"])
def test_an_l4_run_declares_the_gpu_for_every_definition(part):
    """The registered definitions declare the CPU; --backend gpu sets every one, on a copy."""
    predictions = agreement.registered(part)[0]
    before = copy.deepcopy(predictions)
    declared = [e for e in executions(predictions) if "backend" in e]
    assert declared and {e["backend"] for e in declared} == {"cpu"}
    on_gpu, count = agreement.on_backend(predictions, "gpu")
    assert count == len(declared)
    assert {e["backend"] for e in executions(on_gpu) if "backend" in e} == {"gpu"}
    assert predictions == before  # The registered tree is untouched.
    blank = agreement.on_backend(on_gpu, "cpu")[0]
    assert blank == predictions  # Only the backends differ.
    assert agreement.predictions_for(part, None)[2] == 0


def test_up1_is_the_methods_rounding():
    assert agreement.up1(2.543043109426435e-09) == 3e-09
    assert agreement.up1(1e-06) == 1e-06
    assert agreement.up1(9.35552637706949e-07) == 1e-06
    assert agreement.up1(0.0) == 0.0


def test_widening_never_tightens_and_keeps_the_registered_value_when_nothing_is_added():
    assert agreement.widen(2.5e-9, 0.0, 0.0, summed=True) == (2.5e-9, False)
    new, stop = agreement.widen(3e-6, 2e-6, 0.0, summed=True)  # Above the sum 1e-6: stop.
    assert new == agreement.up1(3 * (1e-6 + 2e-6)) and stop
    new, stop = agreement.widen(1e-6, 1e-7, 1e-7, summed=False)
    assert new == 1e-6 and not stop  # 3 x 2e-7 = 6e-7 stays below the fixed bound.


@pytest.mark.parametrize(("part", "run"), [("w1", w1_run()), ("w2", w2_run()), ("g2", g2_run())])
def test_cpu_against_cpu_gives_the_registered_protocol(part, run):
    protocol = agreement.registered(part)[1]
    out = agreement.variant(part, protocol, agreement.measured(part, run, run, run, run))
    report = out.pop("backend_variant")
    assert report["status"] == agreement.STATUS
    assert out == protocol  # Zero terms: every field and tolerance exactly as registered.
    assert not report["stop"] and report["rows"]
    assert all(row["widening"] == 1.0 for row in report["rows"])


def test_the_stop_rule():
    protocol = agreement.registered("w1")[1]
    tolerance = protocol["tolerances"]["P1"]["cell_volume_pL"]
    a = w1_run(volume=1.0 + tolerance)  # A backend term above the registered sum.
    out = agreement.variant("w1", protocol, agreement.measured("w1", w1_run(), a, a, a))
    assert out["backend_variant"]["stop_items"] == ["P1/cell_volume_pL"]
    assert out["tolerances"]["P1"]["cell_volume_pL"] >= tolerance
    # One repeat of three above the sum is enough to stop.
    out = agreement.variant(
        "w1", protocol, agreement.measured("w1", w1_run(), w1_run(), a, w1_run())
    )
    assert out["backend_variant"]["stop_items"] == ["P1/cell_volume_pL"]
    changed = w1_run(converged=False)
    out = agreement.variant(
        "w1", protocol, agreement.measured("w1", w1_run(), changed, changed, changed)
    )
    assert out["backend_variant"]["stop_items"] == ["H"]
    protocol = agreement.registered("w2")[1]
    flipped = w2_run(classification="unstable")
    out = agreement.variant(
        "w2", protocol, agreement.measured("w2", w2_run(), w2_run(), w2_run(), flipped)
    )
    assert out["backend_variant"]["stop"]  # A changed classification in the third repeat.
    shifted = g2_run(voltage=-0.05 + 1e-3)
    protocol = agreement.registered("g2")[1]
    out = agreement.variant(
        "g2", protocol, agreement.measured("g2", g2_run(), shifted, shifted, shifted)
    )
    assert f"{W7}/q3_membrane_voltage_V" in out["backend_variant"]["stop_items"]


def test_variant_rows_follow_the_rule():
    protocol = agreement.registered("w2")[1]
    a = w2_run(voltage=-0.08 + 2e-7)
    terms = agreement.measured("w2", w2_run(), a, w2_run(), w2_run())
    out = agreement.variant("w2", protocol, terms)
    (row,) = [r for r in out["backend_variant"]["rows"] if r["item"] == "voltage_V"]
    expected = max(protocol["stationary"]["voltage_V"], agreement.up1(3 * (2e-7 + 2e-7)))
    assert row["backend"] == pytest.approx(2e-7) and row["tolerance"] == expected
    assert out["stationary"]["voltage_V"] == expected


def test_terms_take_the_worst_repeat_and_the_widest_pair():
    """Backend: the largest |reference - X| over A, B and D; run-to-run: the largest of the
    three pairs' differences; each repeat's and pair's term is kept in the rows."""
    protocol = agreement.registered("w2")[1]
    a, b, d = (w2_run(voltage=-0.08 + dv) for dv in (1e-7, 3e-7, -2e-7))
    terms = agreement.measured("w2", w2_run(), a, b, d)
    entry = "red_cell_15-kaji_s0.12/0"
    assert terms["backend"][entry]["voltage_V"] == pytest.approx(3e-7)
    assert terms["run_to_run"][entry]["voltage_V"] == pytest.approx(5e-7)  # B against D.
    assert sorted(terms["backend_each"]) == ["A", "B", "D"]
    assert sorted(terms["run_to_run_pairs"]) == ["A-B", "A-D", "B-D"]
    out = agreement.variant("w2", protocol, terms)
    (row,) = [r for r in out["backend_variant"]["rows"] if r["item"] == "voltage_V"]
    assert row["backend_each"] == pytest.approx({"A": 1e-7, "B": 3e-7, "D": 2e-7})
    assert row["run_to_run_pairs"] == pytest.approx({"A-B": 2e-7, "A-D": 3e-7, "B-D": 5e-7})
    expected = max(protocol["stationary"]["voltage_V"], agreement.up1(3 * (3e-7 + 5e-7)))
    assert row["tolerance"] == expected
    assert out["backend_variant"]["repeats"]["labels"] == ["A", "B", "D"]


def test_one_pair_is_refused():
    with pytest.raises(ValueError, match="take 3 L4 repeats"):
        agreement.measured("w2", w2_run(), w2_run(), w2_run())
    old = dict(backend={}, run_to_run={})  # A terms file of the earlier one-pair method.
    with pytest.raises(ValueError, match="one pair are not accepted"):
        agreement.variant("w2", agreement.registered("w2")[1], old)


RUNS = dict(w1=w1_run(), w2=w2_run(), g2=g2_run())


def registered_variant(part):
    protocol = agreement.registered(part)[1]
    run = RUNS[part]
    out = agreement.variant(part, protocol, agreement.measured(part, run, run, run, run))
    out["backend_variant"]["status"] = "registered at a lead's commit (test)"
    return protocol, out


def judged(part, protocol, tmp_path):
    path = tmp_path / f"{part}.json"
    path.write_text(json.dumps(protocol))
    return agreement.judged_protocol(part, path)[1:]


@pytest.mark.parametrize("part", ["w1", "w2", "g2"])
def test_judged_runs_take_the_registered_protocol_or_a_registered_variant(part, tmp_path):
    protocol, out = registered_variant(part)
    assert out["backend_variant"]["base"] == agreement.BASES[part]
    assert judged(part, protocol, tmp_path) == (True, "the registered protocol")
    assert judged(part, out, tmp_path)[0]
    (site, *_) = agreement.tolerance_sites(part, protocol)
    widened = copy.deepcopy(out)
    parent = agreement._at(widened, site[:-1])
    parent[site[-1]] = 2 * parent[site[-1]]  # A wider tolerance stays a registered variant.
    assert judged(part, widened, tmp_path)[0]


@pytest.mark.parametrize("part", ["w1", "w2", "g2"])
def test_judged_runs_refuse_other_files(part, tmp_path):
    protocol, out = registered_variant(part)
    site = agreement.tolerance_sites(part, protocol)[0]
    proposed = copy.deepcopy(out)
    proposed["backend_variant"]["status"] = agreement.STATUS
    ok, reason = judged(part, proposed, tmp_path)
    assert not ok and "does not say registered" in reason
    edited = copy.deepcopy(out)
    edited["edited_field"] = "not in the registered protocol"
    ok, reason = judged(part, edited, tmp_path)
    assert not ok and "a field other than the widened tolerances differs" in reason
    plain = copy.deepcopy(protocol)  # An edited protocol, not a variant.
    parent = agreement._at(plain, site[:-1])
    parent[site[-1]] = 2 * parent[site[-1]]
    ok, reason = judged(part, plain, tmp_path)
    assert not ok and "no backend_variant block" in reason
    tighter = copy.deepcopy(out)
    parent = agreement._at(tighter, site[:-1])
    parent[site[-1]] = 0.5 * parent[site[-1]]
    ok, reason = judged(part, tighter, tmp_path)
    assert not ok and "at least as registered" in reason
    elsewhere = copy.deepcopy(out)
    elsewhere["backend_variant"]["base"] = "validation/tissue/another_protocol.json"
    ok, reason = judged(part, elsewhere, tmp_path)
    assert not ok and "does not name the base protocol" in reason


def test_the_g2_judge_marks_other_protocols_dry(tmp_path):
    from validation.tissue import cell_replacement_judge as judge

    protocol, out = registered_variant("g2")
    path = tmp_path / "variant.json"
    path.write_text(json.dumps(out))
    dry, acceptance = judge.run_kind(path)
    assert not dry and acceptance.startswith("a registered backend variant")
    assert judge.run_kind() == (False, None)  # The default is unchanged.
    out["backend_variant"]["status"] = agreement.STATUS
    path.write_text(json.dumps(out))
    dry, acceptance = judge.run_kind(path)
    assert dry and acceptance.startswith("dry run only")
    path.write_text(json.dumps(protocol))
    assert judge.run_kind(path) == (False, "the registered protocol")
    assert judge.run_kind(path, parameters=tmp_path / "p.json")[0]  # Still a dry run.


def test_w2_reads_the_qualifications_own_judge_output(tmp_path):
    item = dict(arm="red_cell_15-kaji_s0.12", branch=0, **w2_run()["red_cell_15-kaji_s0.12"]["0"])
    path = tmp_path / "w2-judge.json"
    path.write_text(json.dumps(dict(verdict="pass", items=[copy.deepcopy(item)])))
    assert agreement.load_run("w2", path) == w2_run()


# ---------------------------------------------------------------- runs split over GPU gaps


def saved(tmp_path, name, part, quantities, backend="L4"):
    path = tmp_path / name
    path.write_text(
        json.dumps(dict(part=part, worlds=None, backend=backend, quantities=quantities))
    )
    return path


def two_worlds(part):
    """A whole run of two worlds, and its two partial files' quantities (run --worlds)."""
    if part == "w1":
        whole = w1_run()
        whole["trajectories"]["P5"] = {"0.0": {"cell_volume_pL": [0.9]}}
        first = dict(trajectories={"P1": whole["trajectories"]["P1"]}, stationary={})
        second = dict(
            trajectories={"P5": whole["trajectories"]["P5"]}, stationary=whole["stationary"]
        )
        return whole, (first, second)
    run = w2_run() if part == "w2" else g2_run()
    ((name, value),) = run.items()
    other = "red_cell_4-lew_s1" if part == "w2" else "C9/isolated/literature"
    whole = {name: value, other: copy.deepcopy(value)}
    return whole, ({name: value}, {other: whole[other]})


@pytest.mark.parametrize("part", ["w1", "w2", "g2"])
def test_terms_merge_a_run_split_over_gaps(part, tmp_path):
    """Repeats spread over GPU gaps (run --worlds) give the terms of whole runs."""
    whole, (first, second) = two_worlds(part)
    reference = saved(tmp_path, "cpu.json", part, whole, backend="cpu")
    a = [saved(tmp_path, f"a{i}.json", part, q) for i, q in enumerate((first, second))]
    b = saved(tmp_path, "b.json", part, whole)
    out = tmp_path / "split.json"
    split_argv = ["--reference", str(reference), "--runs", ",".join(map(str, a)), str(b), str(b)]
    agreement.main(["terms", "--part", part, *split_argv, "--output", str(out)])
    joined = tmp_path / "whole.json"
    whole_argv = ["--reference", str(reference), "--runs", str(b), str(b), str(b)]
    agreement.main(["terms", "--part", part, *whole_argv, "--output", str(joined)])
    split, single = json.loads(out.read_text()), json.loads(joined.read_text())
    for key in ("backend", "run_to_run", "backend_each", "run_to_run_pairs"):
        assert split[key] == single[key], key
    assert split["runs"][0] == [str(p) for p in a] and split["labels"] == ["A", "B", "D"]
    merged, backend = agreement.load_runs(part, a)
    assert merged == whole and backend == "L4"


def test_the_variant_files_record_the_three_repeats(tmp_path):
    """terms then variant from saved files: the protocol names each repeat's files."""
    reference = saved(tmp_path, "cpu.json", "w2", w2_run(), backend="cpu")
    runs = [
        saved(tmp_path, f"{x}.json", "w2", w2_run(voltage=-0.08 + dv))
        for x, dv in zip("abd", (1e-7, 3e-7, -2e-7), strict=True)
    ]
    terms = tmp_path / "terms.json"
    argv = ["--reference", str(reference), "--runs", *map(str, runs), "--output", str(terms)]
    agreement.main(["terms", "--part", "w2", *argv])
    agreement.main(["variant", "--part", "w2", "--terms", str(terms), "--output", str(tmp_path)])
    block = json.loads((tmp_path / "protocol.json").read_text())["backend_variant"]
    assert block["repeats"]["runs"] == {x: [str(p)] for x, p in zip("ABD", runs, strict=True)}
    assert block["repeats"]["reference"] == [str(reference)]
    report = json.loads((tmp_path / "variant.json").read_text())
    assert all(sorted(row["backend_each"]) == ["A", "B", "D"] for row in report["rows"])


def test_the_deviation_of_the_judged_run(tmp_path):
    """|A - C| per quantity over the run-to-run term; unbounded where the repeats agreed
    exactly and C does not; a changed classification is listed."""
    reference = saved(tmp_path, "cpu.json", "w2", w2_run(), backend="cpu")
    runs = [
        saved(tmp_path, f"{x}.json", "w2", w2_run(voltage=-0.08 + dv))
        for x, dv in zip("abd", (1e-7, 3e-7, -2e-7), strict=True)
    ]
    terms = tmp_path / "terms.json"
    argv = ["--reference", str(reference), "--runs", *map(str, runs), "--output", str(terms)]
    agreement.main(["terms", "--part", "w2", *argv])
    c = w2_run(voltage=-0.08 + 1e-7 + 1e-6)  # 1e-6 from A: twice the run-to-run 5e-7.
    c["red_cell_15-kaji_s0.12"]["0"]["volume_pL"] = 0.7 * (1 + 1e-9)  # Equal in A, B, D.
    judged = saved(tmp_path, "c.json", "w2", c)
    out = tmp_path / "deviation.json"
    argv = ["--terms", str(terms), "--judged", str(judged), "--output", str(out)]
    agreement.main(["deviation", "--part", "w2", *argv])
    record = json.loads(out.read_text())
    rows = {row["item"]: row for row in record["rows"]}
    voltage = rows["red_cell_15-kaji_s0.12/0/voltage_V"]
    assert voltage["deviation"] == pytest.approx(1e-6) and voltage["ratio"] == pytest.approx(2.0)
    assert record["summary"]["unbounded"] == ["red_cell_15-kaji_s0.12/0/volume_relative"]
    assert record["summary"]["largest_ratio"] == pytest.approx(2.0)
    assert record["summary"]["changed"] == [] and record["a"] == [str(runs[0])]
    flipped = saved(
        tmp_path, "c2.json", "w2", w2_run(classification="unstable", voltage=-0.08 + 1e-7)
    )
    argv = ["--terms", str(terms), "--judged", str(flipped), "--output", str(out)]
    agreement.main(["deviation", "--part", "w2", *argv])
    assert json.loads(out.read_text())["summary"]["changed"] == ["red_cell_15-kaji_s0.12/0"]


def test_split_runs_are_refused_when_inconsistent(tmp_path):
    whole, (first, second) = two_worlds("g2")
    a1, a2 = (saved(tmp_path, f"a{i}.json", "g2", q) for i, q in enumerate((first, second)))
    with pytest.raises(ValueError, match="measured twice"):
        agreement.load_runs("g2", [a1, a1])
    other = saved(tmp_path, "other.json", "g2", second, backend="cpu")
    with pytest.raises(ValueError, match="different backends"):
        agreement.load_runs("g2", [a1, other])
    w2 = saved(tmp_path, "w2.json", "w2", w2_run())
    with pytest.raises(ValueError, match="is a w2 run"):
        agreement.load_runs("g2", [a1, w2])
    reference = agreement.load_runs("g2", [saved(tmp_path, "cpu.json", "g2", whole)])[0]
    partial = agreement.load_runs("g2", [a1])[0]
    with pytest.raises(ValueError, match="run A lacks"):
        agreement.same_worlds("g2", reference, A=partial, B=reference, D=reference)
    with pytest.raises(ValueError, match="run D lacks"):
        agreement.same_worlds("g2", reference, A=reference, B=reference, D=partial)
    joined = agreement.load_runs("g2", [a1, a2])[0]
    agreement.same_worlds("g2", reference, A=joined, B=reference, D=reference)
