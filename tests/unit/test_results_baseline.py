"""The results baseline's comparator (validation/results_baseline.py), on synthetic saved worlds.

Bitwise by default, a declared tolerance when given, and check K1's padding rule: per-law
dispatch may change channel_targets and channel_tau_s only at channel slots inactive for the whole
run, in worlds whose channel activity is static. A planted difference at an active slot, or in a
world whose activity an operator provides, must fail. A checkpoint held as jax arrays saves its
values, and an additive renewal of G1's record is checked (scripts/gates/c1_additive_check.py).
No engine run.
"""

import importlib.util
import json
from collections import namedtuple
from pathlib import Path

import numpy as np
import pytest

from validation import id_table
from validation import results_baseline as rb

ACTIVE = [True, True, False, False]
TABLE = {"law_x@1": "cells.channel.law_x@1", "cells.law_x@1": "cells.channel.law_x@1"}


def saved(directory, arrays, *, static=True, initial=ACTIVE, final=ACTIVE, refusal=None):
    (directory / "set").mkdir(parents=True)
    np.savez_compressed(directory / "set" / "w.npz", **arrays)
    record = dict(
        name="w", definition={}, channel_activity=dict(static=static, initial=initial, final=final)
    )
    if refusal:
        record["refusal"] = refusal
    (directory / "set" / "w.json").write_text(json.dumps(record))
    manifest = dict(source={}, worlds={"set/w": dict(refusal=(refusal or {}).get("type"))})
    (directory / "manifest.json").write_text(json.dumps(manifest))
    return directory


def arrays(targets=(0.1, 0.2, 0.7, 0.7), tau=(0.01, 0.02, 1.62, 1.62), state=1.0):
    return {
        "observations.channel_targets": np.array([targets, targets]),
        "observations.channel_tau_s": np.array([tau, tau]),
        "history.amount_increment": np.full((3, 4), state),
    }


def verdict(tmp_path, a, b, tolerances=None, padding=False, **kw):
    base = saved(tmp_path / "a", a)
    other = saved(tmp_path / "b", b, **kw)
    return rb.compare(base, other, tolerances or {}, padding=padding)


K1_PADDED = dict(targets=(0.1, 0.2, 0.0, 0.0), tau=(0.01, 0.02, 1.0, 1.0))


def test_identical_outputs_are_identical(tmp_path):
    report = verdict(tmp_path, arrays(), arrays())
    assert report["verdict"] == "identical" and report["equal"] == 1


def test_the_gate_default_compares_padding_columns_bitwise(tmp_path):
    """D172's dispatch gate runs without the padding option (the lead's ruling, 15 November):
    K1's per-law values at inactive slots are a difference there."""
    report = verdict(tmp_path, arrays(), arrays(**K1_PADDED))
    assert report["verdict"] == "differs"
    assert report["rows"][0]["failing_count"] == 2 and report["rows"][0]["padding_only"] == []


def test_with_the_k1_option_padding_at_inactive_slots_passes(tmp_path):
    """K1's per-law outputs: target 0 and tau 1 at the two inactive slots."""
    report = verdict(tmp_path, arrays(), arrays(**K1_PADDED), padding=True)
    assert report["verdict"] == "identical"
    assert sorted(report["rows"][0]["padding_only"]) == [
        "observations.channel_targets",
        "observations.channel_tau_s",
    ]


@pytest.mark.parametrize("padding", [False, True])
def test_a_planted_difference_at_an_active_slot_fails(tmp_path, padding):
    """The gate's self-test: with or without the option."""
    other = arrays(targets=(0.1, 0.2000000001, 0.0, 0.0))
    report = verdict(tmp_path, arrays(), other, padding=padding)
    assert report["verdict"] == "differs"
    assert report["rows"][0]["failing"][0]["key"] == "observations.channel_targets"


def test_padding_is_refused_where_activity_is_not_static_or_changes(tmp_path):
    padded = arrays(targets=(0.1, 0.2, 0.0, 0.0))
    report = verdict(tmp_path / "x", arrays(), padded, padding=True, static=False)
    assert report["verdict"] == "differs"
    # A slot inactive at the start but active at the end is not inactive for the whole run.
    changed = [True, True, True, False]
    report = verdict(tmp_path / "y", arrays(), padded, padding=True, final=changed)
    assert report["verdict"] == "differs"


def test_other_fields_get_no_padding_and_a_state_change_fails(tmp_path):
    assert verdict(tmp_path, arrays(), arrays(state=1.0 + 2**-40))["verdict"] == "differs"


def test_a_declared_tolerance(tmp_path):
    other = arrays(state=1.0 + 1e-13)
    tolerances = {"set/w:history.*": {"relative": 1e-12}}
    assert verdict(tmp_path / "x", arrays(), other, tolerances)["verdict"] == "within tolerance"
    tight = {"set/w:history.*": {"relative": 1e-14}}
    assert verdict(tmp_path / "y", arrays(), other, tight)["verdict"] == "differs"


@pytest.mark.parametrize(("message", "equal"), [("the same", True), ("another", False)])
def test_refusals_must_match_exactly(tmp_path, message, equal):
    base = saved(tmp_path / "a", {}, refusal=dict(type="NumericalError", message="the same"))
    other = saved(tmp_path / "b", {}, refusal=dict(type="NumericalError", message=message))
    assert rb.compare(base, other, {})["rows"][0]["equal"] is equal


def test_a_table_of_renamed_ids_translates_the_saved_side(tmp_path, monkeypatch):
    """--map (D345): compare reads the base's refusal through the table, and save --from runs the
    origin's definitions translated, an empty table changing nothing. Planted: without the table
    the refusals differ; a mapping whose keys become one and a spelling given twice are refused."""
    old, new = ({"type": "ConfigError", "message": f"{i}: refused"} for i in list(TABLE.items())[0])
    base, other = saved(tmp_path / "a", {}, refusal=old), saved(tmp_path / "b", {}, refusal=new)
    assert rb.compare(base, other, {}, table=TABLE)["rows"][0]["equal"]
    assert not rb.compare(base, other, {})["rows"][0]["equal"]
    origin, definition = tmp_path / "origin", {"law": "law_x@1", "rows": {"cells.law_x@1": 2.0}}
    (origin / "set").mkdir(parents=True)
    (origin / "set" / "w.json").write_text(json.dumps(dict(name="w", definition=definition)))
    ran = []
    monkeypatch.setattr(rb, "run_world", lambda raw, _: ran.append(raw) or ({}, 0, None))
    for name, table in (("c", {}), ("d", TABLE)):
        (tmp_path / name).mkdir()
        rb._save_sets(tmp_path / name, dict(worlds={}), ["set"], (), 1, origin, table)
    full = "cells.channel.law_x@1"
    assert ran == [definition, {"law": full, "rows": {full: 2.0}}]
    assert json.loads((tmp_path / "d" / "set" / "w.json").read_text())["definition"] == ran[1]
    with pytest.raises(id_table.Ambiguous, match="two keys"):
        rb.through(dict.fromkeys(TABLE), TABLE)
    (tmp_path / "t.json").write_text('{"law_x@1": "cells.a.x@1", "law_x@1": "cells.b.x@1"}')
    with pytest.raises(id_table.Ambiguous, match="given twice"):
        rb.id_map_table(tmp_path / "t.json")


def test_a_checkpoint_held_as_jax_arrays_saves_its_values():
    """D410's planted row: flatten read a jax array's attribute dict, which is empty, instead of its
    values, so a checkpoint held as jax arrays saved only its time and step. Each leaf (a 0-d, an
    int and a bool among them) is saved with its own dtype, shape and bytes, under the keys that a
    NumPy checkpoint of the same values gets; that control's keys and bytes are as they were."""
    import jax

    from cells.execution.state import Checkpoint

    bits = lambda a: (a.dtype, a.shape, a.tobytes())  # noqa: E731
    State = namedtuple("State", "amount count gate scale")
    host = State(
        np.arange(6.0).reshape(2, 3), np.array([3, 4]), np.array([1, 0], bool), np.float64(0.5)
    )
    device = State(*(jax.device_put(v) for v in host))
    control = rb.checkpoint_arrays(Checkpoint(host, None, 0.25, 7, -1), "final")
    saved = rb.checkpoint_arrays(Checkpoint(device, None, 0.25, 7, -1), "final")
    states = [f"final.state.{f}" for f in State._fields]
    assert sorted(control) == sorted(states + ["final.time", "final.step_index"])
    assert [bits(control[k]) for k in states] == [bits(np.asarray(v)) for v in host]
    assert sorted(saved) == sorted(control)
    assert [bits(saved[k]) for k in states] == [bits(np.asarray(v)) for v in device]


def test_an_additive_renewal_is_checked_and_each_planted_fault_fails(tmp_path):
    """scripts/gates/c1_additive_check.py (D410): a renewal that adds each world's final state, its
    definitions read through the table of renamed IDs, passes. Planted, each fails under its rule:
    A, an old array one ulp off, an old array gone, an added key that is no final state, and the
    definitions read without the table; B, a final state off its last history row; C,
    run_windowed's final state off runner.run's."""
    tool = Path(__file__).resolve().parents[2] / "scripts" / "gates" / "c1_additive_check.py"
    spec = importlib.util.spec_from_file_location("c1_additive_check", tool)
    check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check)
    times, history = np.array([0.0, 1.0, 2.0]), np.arange(6.0).reshape(3, 2)

    def run(p, own=True, state=False):  # One run's saved arrays under the prefix p.
        out = {p + "final.time": np.array(2.0), p + "final.step_index": np.array(2)}
        out |= {p + "times": times, p + "history.x": history} if own else {}
        return out | ({p + "final.state.x": history[-1]} if state else {})

    def worlds(added):
        paths = run("run:", state=added) | run("run_windowed:", own=False, state=added)
        for w in (1, 2):
            paths |= run(f"run_batch:world{w}.", state=added)
            for scalar in ("run_batch_windowed", "run_vector_windowed"):
                paths |= run(f"{scalar}:world{w}.", own=False, state=True)
        return {"set/w": run("", state=added), "run-paths/p": paths}

    def save(root, saved, law, mask):
        manifest = {"worlds": {}}
        for world, arrays in saved.items():
            (root / world).parent.mkdir(parents=True, exist_ok=True)
            np.savez(root / f"{world}.npz", **arrays)
            activity = dict(static=True, initial=mask, final=mask)
            record = dict(definition={"law": law}, steps=2, channel_activity=activity)
            (root / f"{world}.json").write_text(json.dumps(record))
            manifest["worlds"][world] = {"digests": {k: rb.digest(v) for k, v in arrays.items()}}
        (root / "manifest.json").write_text(json.dumps(manifest))
        return root

    def ulp(key):
        return lambda arrays: arrays.__setitem__(key, np.nextafter(arrays[key], np.inf))

    (tmp_path / "table.json").write_text(json.dumps({"law_x@1": TABLE["law_x@1"]}))
    old = save(tmp_path / "old", worlds(False), "law_x@1", None)

    def verdict(name, change=None, world=None, table=True):
        saved = worlds(True)
        if change:
            change(saved[world])
        new = save(tmp_path / name, saved, TABLE["law_x@1"], [True])
        out = tmp_path / f"{name}.json"
        mapped = ["--map", str(tmp_path / "table.json")] if table else []
        code = check.main([str(old), str(new), str(out), "--all", *mapped])
        return code, json.loads(out.read_text())["summary"]

    code, summary = verdict("clean")
    assert code == 0 and summary["additive"] and summary["paths_agree"], summary["exceptions"]
    counts = [summary[k] for k in ("added", "final_states_checked", "records_with_masks")]
    assert counts == [5, 5, 2]
    assert summary["added_by_prefix"]["run_batch:world2.final.state"] == 1
    plants = [
        ("additive", "set/w", ulp("history.x")),
        ("additive", "set/w", lambda arrays: arrays.pop("final.time")),
        ("additive", "set/w", lambda arrays: arrays.__setitem__("observations.y", np.zeros(2))),
        ("final_rows", "set/w", ulp("final.state.x")),
        ("paths", "run-paths/p", ulp("run_windowed:final.state.x")),
    ]
    for k, (rule, world, change) in enumerate(plants):
        code, summary = verdict(f"planted-{k}", change, world)
        assert code == 1 and world in summary["exceptions"][rule], (k, summary["exceptions"])
    code, summary = verdict("unmapped", table=False)
    assert code == 1 and list(summary["exceptions"]["additive"]) == ["run-paths/p", "set/w"]
