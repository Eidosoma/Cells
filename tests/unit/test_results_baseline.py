"""The results baseline's comparator (validation/results_baseline.py), on synthetic saved worlds.

Bitwise by default, a declared tolerance when given, and check K1's padding rule: per-law
dispatch may change channel_targets and channel_tau_s only at channel slots inactive for the whole
run, in worlds whose channel activity is static. A planted difference at an active slot, or in a
world whose activity an operator provides, must fail. No engine run.
"""

import json

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
