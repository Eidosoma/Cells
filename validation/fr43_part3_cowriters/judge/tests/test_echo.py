"""The echo's equalities (CRITERIA.md §4.1) row by row, and a refused run's short lists (TABLE.md §3), read directly
without a judge pass. Under a second."""

from __future__ import annotations

import copy
import os
import sys

import pytest

JUDGE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, JUDGE)

from cowriter_judge.echo import compare, echo_departures, registered_echo  # noqa: E402
from cowriter_judge.registry import Inputs  # noqa: E402
from cowriter_judge.table import Entry, read_entry  # noqa: E402

SPEC = os.path.join(JUDGE, "..", "spec")


@pytest.fixture(scope="module")
def inputs() -> Inputs:
    return Inputs(os.path.join(SPEC, "inputs.json"))


ROWS = [
    # (label, registered, run, key, equal)
    ("an integer against the same real", 4, 4.0, "", True),
    ("an integer against a real off it", 17, 17.0000001, "", False),
    ("a real at 1e-13 relative", 0.047, 0.047 * (1 + 1e-13), "", True),
    ("a real at 1e-11 relative", 0.047, 0.047 * (1 + 1e-11), "", False),
    ("a declared zero against a tiny value", 0.0, 1e-300, "", False),
    ("a declared zero against minus zero", 0.0, -0.0, "", True),
    ("a string", "cell", "Cell", "", False),
    ("a bool is not a number", 1, True, "", False),
    ("read: null against absent", {"id": "x", "read": None}, {"id": "x"}, "", True),
    ("read: null against a value", {"id": "x", "read": None}, {"id": "x", "read": {"species": "S"}}, "", False),
    ("ruling 3b: an extra key that is null departs", {"a": 1}, {"a": 1, "b": None}, "", False),
    ("an extra key with a value", {"a": 1}, {"a": 1, "b": 2}, "", False),
    ("reactions in another order", [{"id": "make", "k": 1.0}, {"id": "spend", "k": 2.0}],
     [{"id": "spend", "k": 2.0}, {"id": "make", "k": 1.0}], "reactions", True),
    ("channels in another order", [{"id": "assemble", "k": 1.0}, {"id": "dissolve", "k": 2.0}],
     [{"id": "dissolve", "k": 2.0}, {"id": "assemble", "k": 1.0}], "channels", False),
    ("unit states in another order", [{"id": "free"}, {"id": "active"}], [{"id": "active"}, {"id": "free"}],
     "unit_states", False),
    ("a reaction missing", [{"id": "make"}, {"id": "spend"}], [{"id": "make"}], "reactions", False),
    ("samples one short", [0.0, 1.0, 2.0], [0.0, 1.0], "samples_s", False),
]


@pytest.mark.parametrize("label, registered, run, key, equal", ROWS, ids=[r[0] for r in ROWS])
def test_echo_compare(label, registered, run, key, equal) -> None:
    assert (compare(registered, run, "x", key) == []) == equal, label


def _entry(inputs: Inputs, name: str) -> tuple[dict, list[str]]:
    spec = inputs.runs[name]
    world = inputs.worlds[spec.world]
    operators = ["writer", "population"]
    entry = {"inputs": copy.deepcopy(registered_echo(inputs, spec)), "world": spec.world, "first": spec.first,
             "copy": spec.copy, "step_s": spec.raw["step_s"], "seed": world.seeds[spec.copy],
             "variant": spec.variant, "operators": list(operators)}
    return entry, operators


def test_echo_departures(inputs) -> None:
    name = "W6 gene-first h=0.0625 c3"
    entry, operators = _entry(inputs, name)
    spec = inputs.runs[name]
    assert echo_departures(inputs, spec, entry, operators) == []
    cases = [
        lambda e: e["inputs"]["gene"].__setitem__("residues", 241),
        lambda e: e["inputs"].__setitem__("rungs_s", [0.5]),
        lambda e: e["inputs"].pop("samples_s"),
        lambda e: e.__setitem__("operators", list(reversed(e["operators"]))),
        lambda e: e.__setitem__("variant", "restart"),
        lambda e: e.__setitem__("seed", e["seed"] + 1),
        lambda e: e["inputs"].__setitem__("step_s", 0.125),
        lambda e: e["inputs"]["population"]["channels"][0]["read"].__setitem__("at", "node"),
        lambda e: e["inputs"].__setitem__("note", None),  # ruling 3b, at the top of the echo
    ]
    for mutate in cases:
        changed = copy.deepcopy(entry)
        mutate(changed)
        assert echo_departures(inputs, spec, changed, operators), changed
    lie = "W5 reactions-first h=0.0025 c4 lie"
    entry, operators = _entry(inputs, lie)
    assert echo_departures(inputs, inputs.runs[lie], entry, operators) == []
    entry["variant"] = None
    assert echo_departures(inputs, inputs.runs[lie], entry, operators)


def test_ruling_8_a_declared_change_at_the_rehearsal_only() -> None:
    invented = Inputs(os.path.join(JUDGE, "..", "references", "out", "inputs_invented.json"))
    spec = [s for s in invented.run_list if s.variant == "stopped"][0]
    entry, operators = _entry(invented, spec.name)
    entry["inputs"] = copy.deepcopy(registered_echo(invented, spec, rehearsal=True))
    assert entry["inputs"]["rows_fmol"]["Pi"] == spec.raw["change"]["rows_fmol.Pi"]
    assert echo_departures(invented, spec, entry, operators, rehearsal=True) == []
    assert echo_departures(invented, spec, entry, operators, rehearsal=False)


def _read(raw: dict, kind: str = "reactions") -> Entry:
    entry = Entry(name="x", table="t", raw=raw)
    read_entry(entry, kind)
    return entry


def _shaped(status: str, n_t: int, n_series: int) -> dict:
    series = {name: [0.0] * n_series for name in
              ("n_S_c", "n_S_o", "n_X", "n_Y", "n_W", "xi_1", "xi_2", "moved")}
    return {"status": status, "t": [0.0] * n_t, "series": series, "integer_ledger": [2] * n_series,
            "events": {"time_s": [], "channel": [], "counts_after": [], "first_index": 0}}


def test_a_refused_runs_lists_may_be_short() -> None:
    assert not {i.row for i in _read(_shaped("refused", 3, 2)).issues} & {"missing leaf"}
    assert "missing leaf" in {i.row for i in _read(_shaped("completed", 3, 2)).issues}
    assert "missing leaf" in {i.row for i in _read(_shaped("refused", 3, 4)).issues}
