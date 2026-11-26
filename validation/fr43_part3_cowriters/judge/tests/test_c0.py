"""C0's self-tests: the references at their tag pass, each planted fault of CRITERIA.md §4.2 is named and refuses
its reference, and each disagreement of the judge's own recomputations is a finding that refuses nothing and stops
the judge (the lead's ruling 7, 26 November 2026). About 15 s; reads the spec folder and the references' out/ only."""

from __future__ import annotations

import json
import math
import os
import sys

import pytest

JUDGE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, JUDGE)

from cowriter_judge.c0 import c0_reference_file, compare_hashes, invented_rules, run_c0  # noqa: E402
from cowriter_judge.registry import Inputs  # noqa: E402

SPEC = os.path.join(JUDGE, "..", "spec")
OUT = os.path.join(JUDGE, "..", "references", "out")


@pytest.fixture(scope="module")
def registered() -> Inputs:
    return Inputs(os.path.join(SPEC, "inputs.json"))


@pytest.fixture(scope="module")
def originals() -> dict:
    return {w: json.load(open(os.path.join(OUT, f"reference_{w}.json"))) for w in ("W5", "W5-exact", "W6")}


def _codes(result: dict) -> set[str]:
    codes = {f["code"] for f in result["file_faults"]}
    for world in result["worlds"].values():
        codes |= {f["code"] for f in world["faults"]}
    return codes


def _finding_codes(result: dict) -> set[str]:
    codes: set[str] = set()
    for world in result["worlds"].values():
        codes |= {f["code"] for f in world["findings"]}
    return codes


def _run(tmp_path, registered: Inputs, data: dict | str, name: str = "reference.json") -> dict:
    path = tmp_path / name
    path.write_text(data if isinstance(data, str) else json.dumps(data))
    return c0_reference_file(str(path), registered, os.path.join(SPEC, "draws.json"), invented=False)


def test_c0_passes_on_the_tagged_references() -> None:
    result = run_c0(SPEC, OUT)
    assert result["passes"], result["refused"]
    assert not result["invented_rules"]["faults"] and not result["findings"] and not result["stop"]
    for block in [result["invented"], *result["files"].values()]:
        for world in block["worlds"].values():
            assert not world["faults"] and not world["disagreements"]
            assert world["summary"]["closed_forms_checked"] > 0 and world["summary"]["identities_checked"] > 0
    # ruling 4: the published P5 tolerance, and what S = t_k/h gives at the same event
    rows = result["ruling_4_p5_tolerance"]["reference_W5-exact.json W5-exact"]
    assert {r["family"] for r in rows} == {"W5-exact reactions-first", "W5-exact population-first"}
    for r in rows:
        assert abs(r["tolerance_S_T_over_h"] - r["published_tolerance"]) <= 1e-12 * r["published_tolerance"]
        assert r["tolerance_S_tk_over_h"] < r["published_tolerance"]
    # ruling 8: the key paths of `change`, in the invented inputs alone
    changes = result["ruling_8_change"]
    assert [c["key_path"].endswith(".change") for c in changes["inputs_invented.json"]] == [True, True]
    assert changes["inputs.json"] == []


def _first_dissolve(copy: dict) -> int:
    return copy["events"]["channel"].index("dissolve")


def _sizing(world: str, family: str, readout: str, key: str, value):
    def mutate(d):
        d["sizing"][family][readout][key] = value(d["sizing"][family][readout]) if callable(value) else value
    return mutate


def _set(path: list, value):
    def mutate(d):
        obj = d
        for key in path[:-1]:
            obj = obj[key]
        obj[path[-1]] = value(obj[path[-1]]) if callable(value) else value
    return mutate


def _truncate_copy(c: int, keep: int):
    def mutate(d):
        ev = d["copies"][c]["events"]
        for key in ("time_s", "channel", "counts_after"):
            ev[key] = ev[key][:keep]
        ev["K"] = ev["K_all"] = keep
    return mutate


def _shift_dissolve(c: int, delta: float):
    def mutate(d):
        ev = d["copies"][c]["events"]
        k = _first_dissolve(d["copies"][c])
        ev["time_s"][k] = ev["time_s"][k] + delta
    return mutate


def _scale_series(c: int, name: str, factor: float):
    def mutate(d):
        s = d["copies"][c]["series"][name]["value"]
        d["copies"][c]["series"][name]["value"] = [v * factor for v in s]
    return mutate


def _delete(path: list):
    def mutate(d):
        obj = d
        for key in path[:-1]:
            obj = obj[key]
        del obj[path[-1]]
    return mutate


def _plant_margin(plant: str, check: str, value: float):
    def mutate(d):
        for entry in d["plants"]:
            if entry["plant"] == plant and entry["check"] == check:
                entry["margin"] = value
                return
        raise AssertionError("no such plant entry")
    return mutate


def _guard_event(c: int):
    def mutate(d):
        cut = 20.0 - 4 * 0.02
        ev = d["copies"][c]["events"]
        ev["time_s"][-1] = cut + 1e-10
    return mutate


CASES = [
    ("q outside [p - 0.4, p + 0.4]", "W5", _sizing("W5", "W5 reactions-first", "t_events", "q", 2.45), "sizing order"),
    ("E above tau", "W5", _sizing("W5", "W5 reactions-first", "n_S_c", "E", lambda e: e["tau"] * 1.01),
     "sizing size"),
    ("a named entry with three used", "W6", _sizing("W6", "W6 gene-first", "made", "used", 3), "sizing at_rounding"),
    ("an event accuracy above SPEC 4", "W5", _set(["copies", 0, "events", "accuracy_s"], 1e-9), "accuracy"),
    ("a series accuracy above SPEC 4", "W6", _set(["copies", 3, "series", "lost", "accuracy"],
                                                    lambda a: [x * 1e8 for x in a]), "accuracy"),
    ("a check that does not pass", "W5", _set(["copies", 0, "checks", 1, "passes"], False), "check does not pass"),
    ("a check over its bound", "W6", _set(["copies", 2, "checks", 1, "residual"], 1.0), "check does not pass"),
    ("draws_check not identical", "W5-exact", _set(["draws_check", "identical"], False), "draws_check"),
    ("a plant margin below 10", "W5", _plant_margin("P9", "t_events", 9.0), "plant margin"),
    ("P4's margin a hair below 10 (1 - 1e-9)", "W6", _plant_margin("P4-W6", "t_events", 9.99999998),
     "plant margin"),
    ("a scale not positive", "W5-exact", _set(["scales", "n_W"], 0.0), "scale not positive"),
    ("a class not inputs.json's", "W5", _set(["classes", "n_X"], "S"), "class"),
    ("a class missing", "W6", _delete(["classes", "made"]), "class"),
    ("inputs_sha256", "W5", _set(["inputs_sha256"], "0" * 64), "inputs_sha256"),
    ("a missing series", "W5", _delete(["copies", 2, "series", "xi_2"]), "missing registered key"),
    ("a missing sizing entry", "W6", _delete(["sizing", "W6 gene-first", "n_R_o"]), "missing registered key"),
    ("a missing planted family", "W5", _delete(["planted", "P9", "W5 population-first"]), "missing registered key"),
    ("a missing plants entry", "W6", _set(["plants"], lambda p: [e for e in p if e["plant"] != "P13"]),
     "missing expected value"),
    ("a pair ratio below 10", "W5", _set(["sizing", "pair", "t_events", "ratio"], 9.5), "pair"),
    ("W5-exact's rungs ratio below 10", "W5-exact",
     _set(["sizing", "rungs", "W5-exact reactions-first", "moved", "ratio"], 9.0), "pair"),
    ("P3's expected order off p - 1", "W5", _set(["sizing", "mutant", "W5 reactions-first", "q"], 1.3), "sizing P3"),
    ("a copy below the minimum events", "W5", _truncate_copy(6, 11), "minimum events"),
    ("W5-exact's running check", "W5-exact", _scale_series(0, "moved", 1e-12), "running check"),
]

# The lead's ruling 7: the judge's own recomputations and consistency checks are findings, not faults.
FINDINGS = [
    ("used that its d does not give", "W5", _sizing("W5", "W5 population-first", "xi_2", "used", 5),
     "recomputed sizing"),
    ("tau that its d does not give", "W6", _sizing("W6", "W6 population-first", "lost", "tau", lambda e: e["tau"] * 2),
     "recomputed sizing"),
    ("a dissolve wait off its closed form", "W5", _shift_dissolve(0, 1e-10), "closed form"),
    ("a W5-exact time off its decimal sum", "W5-exact", _set(["copies", 1, "events", "time_s", 3],
                                                             lambda t: t + 8e-14), "closed form"),
    ("K against the times", "W5", _set(["copies", 2, "events", "K"], lambda k: k - 1), "consistency events"),
    ("a scale off READOUTS 2", "W5", _set(["scales", "n_S_c"], lambda s: s * 1.001), "recomputed scale"),
    ("a series value that breaks an identity", "W5", _set(["copies", 1, "series", "n_X", "value", 5],
                                                          lambda v: v * (1 + 1e-12)), "consistency identity"),
    ("an event within 1e-9 T of the cut", "W5", _guard_event(4), "guard"),
    ("a start off its declared value", "W6", _set(["copies", 0, "series", "n_N", "value", 0],
                                                    lambda v: v * (1 + 1e-14)), "start"),
    ("a seed not the registered one", "W6", _set(["copies", 5, "seed"], 1), "consistency copies"),
]


@pytest.mark.parametrize("label, world, mutate, code", CASES, ids=[c[0] for c in CASES])
def test_c0_names_each_fault(tmp_path, registered, originals, label, world, mutate, code) -> None:
    data = json.loads(json.dumps(originals[world]))
    mutate(data)
    result = _run(tmp_path, registered, data)
    assert result["refused"], label
    assert code in _codes(result), (label, _codes(result))


@pytest.mark.parametrize("label, world, mutate, code", FINDINGS, ids=[c[0] for c in FINDINGS])
def test_c0_ruling_7_a_finding_refuses_nothing(tmp_path, registered, originals, label, world, mutate, code) -> None:
    data = json.loads(json.dumps(originals[world]))
    mutate(data)
    result = _run(tmp_path, registered, data)
    assert not result["refused"], (label, _codes(result))
    assert code in _finding_codes(result), (label, _finding_codes(result))


def test_c0_refuses_a_non_finite_number(tmp_path, registered, originals) -> None:
    data = json.loads(json.dumps(originals["W5"]))
    data["copies"][0]["series"]["n_S_c"]["value"][3] = math.nan
    result = _run(tmp_path, registered, json.dumps(data))
    assert result["refused"] and "non-finite" in _codes(result)
    text = json.dumps(originals["W5"]).replace('"accuracy_s": ', '"accuracy_s": 1e999, "accuracy_x": ', 1)
    assert "non-finite" in _codes(_run(tmp_path, registered, text))


def test_c0_refuses_a_duplicate_key(tmp_path, registered, originals) -> None:
    text = json.dumps(originals["W6"]).replace('"kind": ', '"kind": "x", "kind": ', 1)
    result = _run(tmp_path, registered, text)
    assert result["refused"] and "duplicate key" in _codes(result)


def test_invented_rules_name_a_registered_number(tmp_path, registered) -> None:
    data = json.load(open(os.path.join(OUT, "inputs_invented.json")))
    data["worlds"]["W5"]["cell_pL"] = registered.worlds["W5"].block["cell_pL"]
    data["retry"]["runs"][0]["name"] = data["retry"]["runs"][0]["name"].replace(" retry", "")
    path = tmp_path / "inputs_invented.json"
    path.write_text(json.dumps(data))
    rules = invented_rules(Inputs(str(path)), registered)
    assert {f["code"] for f in rules["faults"]} == {"invented number equals a registered one"}
    assert {f["code"] for f in rules["findings"]} == {"invented retry"}


def test_the_protocols_hashes() -> None:
    files = {"reference_W5.json": "a" * 64}
    assert not compare_hashes({"reference_W5.json": "A" * 64}, files)["faults"]
    assert compare_hashes({"reference_W5.json": "b" * 64}, files)["faults"]
    assert compare_hashes({}, files)["faults"]
    assert not compare_hashes(None, files)["faults"]
