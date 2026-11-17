"""Run records: the bundle (world record, run record, arrays, manifest) and the pair of forms.

Planted errors it must catch:
- a tampered array file (the manifest's checksum refuses it on reading);
- a pair whose runs differ in more than the law (another seed): refused;
- an array without its declaration in the run record (every saved array is declared).
"""

import json

import numpy as np
import pytest

from cells.core.specs import ConfigError, parse_spec
from cells.models.assembly_lineages import (
    GARD_PAIR_CONSISTENT,
    GARD_SINGLE_EVENT,
    MODEL_ID,
    records,
    runner,
)
from tests.assembly_lineage_fixtures import definition, world


@pytest.fixture(scope="module")
def pair():
    the_world = world(seed=5)
    return [
        runner.run(parse_spec(definition(the_world, law, fissions=3, uniforms=True)))
        for law in (GARD_SINGLE_EVENT, GARD_PAIR_CONSISTENT)
    ]


def test_a_pair_bundle_states_its_world_law_and_streams(pair, tmp_path):
    entries = records.write_pair(tmp_path / "pair", pair)
    assert [e["form"] for e in entries] == ["single-event", "pair-consistent"]
    pair_record = json.loads((tmp_path / "pair" / "pair.json").read_text())
    assert pair_record["differs"] == ["law"]
    worlds, ids = [], set()
    for entry, run in zip(entries, pair, strict=True):
        world_record, run_record, arrays = records.read(tmp_path / "pair" / entry["bundle"])
        worlds.append((tmp_path / "pair" / entry["bundle"] / "world.json").read_bytes())
        ids.add(world_record["id"])
        assert run_record["world"] == world_record["id"] == pair_record["world"]
        assert run_record["founder"] == "world"
        assert (
            run_record["law"]["form"] == entry["form"] and run_record["law"]["id"] == entry["law"]
        )
        assert run_record["law"]["comparison_only"] is True
        assert run_record["engine_models"]["model"] == MODEL_ID
        assert run_record["mode"] == "single_lineage"
        assert run_record["stream"] == pair_record["stream"]
        assert {"tau", "channel", "channels", "prefix"} <= set(run_record["ssa"])
        assert {"fission_work", "sink", "closure"} <= set(run_record["ledger"])
        # What a replay needs, declared in the record (G2 reads the bundle, never the code).
        assert {"g_join_i(n)", "g_leave_i(n)", "state", "update"} <= set(
            run_record["law"]["formulas"]
        )
        assert {"join_i", "leave_i", "affinity_i(n)"} <= set(
            run_record["law"]["exchange"]["formulas"]
        )
        fission_rules = run_record["operators"]["fission"]
        assert {"trigger", "places", "draw", "exact_fraction", "binomial"} <= set(fission_rules)
        assert {"uniform", "empty", "carrier_keys"} <= set(run_record["operators"]["continuation"])
        assert {"statuses", "order"} <= set(run_record["lifecycle"])
        assert run_record["end"]["fissions"] == 3
        assert run_record["time"]["unit"] == "nominal"
        assert run_record["records"]["event_time"]["unit"] == "nominal"
        table = run_record["channels"]["rows"]
        count = run.spec.model.world.types.count
        assert [r["row"] for r in table] == list(range(2 * count))
        by_signed = {r["event_channel"]: r for r in table}
        for signed in arrays["event_channel"]:
            row = by_signed[int(signed)]
            assert row["kind"] == ("join" if signed > 0 else "leave")
            assert row["row"] == (signed - 1 if signed > 0 else count - signed - 1)
        assert world_record["world"]["founder"] == list(run.spec.model.world.founder)
        for name, values in arrays.items():
            declared = run_record["records"][name]
            assert {"base", "axes", "unit", "layer", "owner"} <= set(declared)
            assert len(declared["axes"]) == np.ndim(values)
            original = {**run.rows, **run.fissions, **run.trace, **run.diagnostics}[name]
            assert np.array_equal(values, original, equal_nan=True)
    assert len(ids) == 1 and worlds[0] == worlds[1]
    assert set(records.RECORDS) == set(arrays)  # Every declared record is saved here.


def test_a_tampered_array_is_refused(pair, tmp_path):
    records.write_run(tmp_path / "run", pair[1])
    records.read(tmp_path / "run")
    path = tmp_path / "run" / records.ARRAYS
    data = dict(np.load(path))
    data["assembly_count"] = data["assembly_count"].copy()
    data["assembly_count"][0, 0, 0] += 1
    np.savez(path, **data)
    with pytest.raises(ConfigError, match="checksum"):
        records.read(tmp_path / "run")


def test_a_pair_differing_in_more_than_the_law_is_refused(pair, tmp_path):
    data = pair[1].spec.to_dict()
    data["execution"]["stream"]["seed"] += 1
    other = runner.run(parse_spec(data))
    with pytest.raises(ConfigError, match="differ in the law alone"):
        records.write_pair(tmp_path / "bad", [pair[0], other])
    assert not (tmp_path / "bad").exists()
    with pytest.raises(ConfigError):
        records.write_pair(tmp_path / "same", [pair[1], pair[1]])


def test_every_saved_array_is_declared(pair):
    run = pair[0]
    saved = {**run.rows, **run.fissions, **run.trace, **run.diagnostics}
    assert set(saved) <= set(records.RECORDS)
    record = records.run_record(run, "w")
    assert set(record["records"]) == set(saved)
    planted = dict(run.diagnostics, extra=np.zeros(2))
    with pytest.raises(KeyError):
        records.run_record(type(run)(**{**run.__dict__, "diagnostics": planted}), "w")
