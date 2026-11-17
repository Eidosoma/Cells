"""The frozen relationship keys and bundle format (D202): every constant pinned here.

D202 froze them before any bundle was shared: the s:c key rule and its spellings, the lives'
birth kinds, end reasons and censoring causes, the reserved `label` stream domain, the run
qualifier, the final row, the family's interface IDs, the formats' names, world.json's structure,
run.json's fields and the declared array table. A change to any of them is a format change: it
fails here, and goes to the lead and the readers (G2's harness, the visualizer, the relations
writer) before it lands.

Planted error it must catch: a declared table with one array renamed, and one with one unit
changed, each named by the pin check.
"""

import hashlib
import json

import numpy as np

from cells.core.specs import parse_spec
from cells.models.assembly_lineages import (
    EXCHANGE_INTERFACE,
    OPERATOR_INTERFACE,
    RATE_FACTOR_INTERFACE,
    arms,
    checkpoints,
    keys,
    records,
    runner,
    streams,
)
from tests.assembly_lineage_fixtures import definition, world
from validation.assembly_lineages import inheritance, probes

R, S, F, E, G, L = "row", "row", "fission", "event", "growth", "life"
TABLE = {  # name: (base, axes, unit)
    "row_time": (R, ["row"], "clock"),
    "row_event": (R, ["row"], "events"),
    "row_kind": (R, ["row"], "1"),
    "row_fission": (R, ["row"], "1"),
    "assembly_count": (R, ["row", "type", "assembly"], "molecules"),
    "joined_total": (R, ["row", "type", "assembly"], "molecules"),
    "left_total": (R, ["row", "type", "assembly"], "molecules"),
    "discarded_total": (R, ["row", "type", "assembly"], "molecules"),
    "exchange_heat_kT": (R, ["row", "assembly"], "k_BT"),
    "fission_work_kT": (R, ["row", "assembly"], "k_BT"),
    "discarded_free_energy_kT": (R, ["row", "assembly"], "k_BT"),
    "log_weight": (R, ["row", "assembly"], "k_BT"),
    "ledger_residual_kT": (R, ["row", "assembly"], "k_BT"),
    "occupant": (R, ["row", "assembly"], "carrier key"),
    "generation": (R, ["row", "assembly"], "fissions"),
    "fission_time": (F, ["fission"], "clock"),
    "fission_slot": (F, ["fission"], "1"),
    "fission_parent": (F, ["fission"], "carrier key"),
    "fission_daughters": (F, ["fission", "daughter"], "carrier key"),
    "fission_followed": (F, ["fission"], "1"),
    "fission_split": (F, ["fission", "type"], "molecules"),
    "fission_similarity": (F, ["fission", "daughter"], "1"),
    "fission_partition_counter": (F, ["fission"], "1"),
    "event_time": (E, ["event"], "clock"),
    "event_channel": (E, ["event"], "1"),
    "events_per_growth": (G, ["growth"], "events"),
    "growth_carrier": (G, ["growth"], "carrier key"),
    "event_uniforms": (E, ["event", "draw"], "1"),
    "partition_uniforms": (F, ["fission", "place"], "1"),
    "continuation_uniform": (F, ["fission"], "1"),
    "life_key": (L, ["life"], "carrier key"),
    "life_slot": (L, ["life"], "1"),
    "life_parent": (L, ["life"], "carrier key"),
    "life_birth_kind": (L, ["life"], "1"),
    "life_birth_time": (L, ["life"], "clock"),
    "life_birth_event": (L, ["life"], "events"),
    "life_birth_fission": (L, ["life"], "1"),
    "life_end_reason": (L, ["life"], "1"),
    "life_censored_by": (L, ["life"], "1"),
    "life_end_time": (L, ["life"], "clock"),
    "life_end_event": (L, ["life"], "events"),
    "life_end_fission": (L, ["life"], "1"),
    "life_generation": (L, ["life"], "fissions"),
    "life_root": (L, ["life"], "carrier key"),
    "life_sublineage": (L, ["life"], "1"),
    "life_size_at_birth": (L, ["life"], "molecules"),
}
RUN_FIELDS = {
    "format", "world", "founder", "model", "engine_models", "definition_sha256", "run", "keys",
    "lives", "law", "mode", "stream", "ssa", "ledger", "operators", "lifecycle", "source", "end",
    "time", "channels", "layers", "records", "diagnostics",
}  # fmt: skip
WORLD_FIELDS = {"format", "id", "world", "derived"}
WORLD_BODY = {
    "types",
    "supply",
    "exchange",
    "law_data",
    "founder",
    "fission",
    "continuation",
    "units",
}
DERIVED = {
    "types",
    "identity",
    "standard_transfer_mu_RT",
    "join_rate",
    "leave_rate",
    "founder_size",
}


def pin_errors(declared, clock):
    """Where a run.json's declared array table departs from the frozen one (empty: it keeps
    it); `clock` is the world's time unit, which the clock's arrays take."""
    out = sorted(set(TABLE) ^ set(declared))
    for name, (base, axes, unit) in TABLE.items():
        entry = declared.get(name)
        unit = clock if unit == "clock" else unit
        if entry is not None and (entry["base"], entry["axes"], entry["unit"]) != (
            base,
            axes,
            unit,
        ):
            out.append(name)
    return sorted(out)


def test_the_key_rule_and_the_lives_vocabulary_are_frozen():
    assert (keys.WORD, keys.FOUNDER, keys.TEXT) == (2**32, 0, "<U12")
    assert keys.SPELLING == "s:c, with key = s * 2**32 + c"
    assert keys.ID_FORM == "carrier:a<key>, the int64 key in decimal"
    assert keys.EVENT_FORMS == {
        "fission": "event:fission/<fission-table row>",
        "extinction": "event:extinction/<key>/<lineage path event count>",
    }
    assert keys.carrier_id(keys.key(1, 1)) == "carrier:a4294967297"
    assert keys.BIRTH_KINDS == ("founder", "division", "continued")
    assert keys.END_REASONS == ("divided", "extinct", "not_followed", "censored")
    assert keys.CENSORED_BY == ("horizon", "event_limit", "stalled", "budget", "stop")
    body = {"definition": "f", "start": {"checkpoint": "d", "time": 1.5}}
    assert (
        keys.qualifier("f", body["start"])
        == hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    )
    stop = {"events": 9, "fissions": 1}
    assert (
        keys.qualifier("f", "fresh", stop)
        == hashlib.sha256(
            json.dumps({"definition": "f", "start": "fresh", "stop": stop}, sort_keys=True).encode()
        ).hexdigest()
    )
    assert dict(streams.DOMAINS) == {
        "initial_composition": 0, "exchange": 1, "partition": 2, "continuation": 3, "label": 4,
    }  # fmt: skip
    assert streams.RESERVED == ("label",) and streams.GENERATOR == "threefry2x32"
    assert (EXCHANGE_INTERFACE, RATE_FACTOR_INTERFACE, OPERATOR_INTERFACE) == (
        "cells.exchange_law@1",
        "cells.rate_factor_law@1",
        "cells.lineage_operator@1",
    )
    assert runner.ROW_KINDS == ("start", "parent", "daughter", "end")
    formats = (
        records.WORLD_FORMAT, records.RUN_FORMAT, records.PAIR_FORMAT, checkpoints.FORMAT,
        arms.FORMAT, probes.PROBE_FORMAT, inheritance.TABLE_FORMAT,
    )  # fmt: skip
    assert formats == (
        "cells.assembly_lineages.world@1", "cells.assembly_lineages.run@1",
        "cells.assembly_lineages.pair@1", "cells.assembly_lineages.checkpoint@1",
        "cells.assembly_lineages.arm@1", "cells.assembly_lineages.probe@1",
        "cells.assembly_lineages.f12_table@1",
    )  # fmt: skip


def test_the_bundle_format_is_frozen(tmp_path):
    run = runner.run(parse_spec(definition(world(), fissions=2, uniforms=True)))
    records.write_run(tmp_path / "run", run)
    run_json = json.loads((tmp_path / "run" / "run.json").read_text())
    world_json = json.loads((tmp_path / "run" / "world.json").read_text())
    assert set(run_json) == RUN_FIELDS and set(run_json["run"]) == {"qualifier", "start"}
    assert run_json["keys"] == keys.RULE and run_json["lives"] == keys.LIVES
    assert set(world_json) == WORLD_FIELDS and set(world_json["derived"]) == DERIVED
    assert set(world_json["world"]) == WORLD_BODY
    assert pin_errors(run_json["records"], "nominal") == []
    assert run_json["law"]["interface"] == RATE_FACTOR_INTERFACE
    assert run_json["law"]["exchange"]["interface"] == EXCHANGE_INTERFACE
    assert {op["interface"] for op in run_json["operators"].values()} == {OPERATOR_INTERFACE}
    _, _, arrays = records.read(tmp_path / "run")
    assert arrays["row_kind"][-1] == 3 and arrays["life_end_reason"].dtype == np.dtype("<U12")
    # Planted: one array renamed, and one unit changed (the clock's, then an event count's).
    renamed = dict(run_json["records"])
    renamed["life_ends"] = renamed.pop("life_end_reason")
    assert pin_errors(renamed, "nominal") == ["life_end_reason", "life_ends"]
    changed = dict(run_json["records"], row_time=dict(run_json["records"]["row_time"], unit="s"))
    assert pin_errors(changed, "nominal") == ["row_time"]
    changed = dict(run_json["records"], row_event=dict(run_json["records"]["row_event"], unit="1"))
    assert pin_errors(changed, "nominal") == ["row_event"]


START = {"checkpoint", "from_run", "time", "events", "fissions", "occupant", "branch_word",
         "parent_branch_word", "kind", "differs"}  # fmt: skip
BOUND = {"generation_limit", "life_budget", "lives_at_most", "growth", "lanes"}
CHECKPOINT = {"format", "definition", "definition_sha256", "qualifier", "clock", "digest",
              "runtime", "source_hashes", "lane_sha256"}  # fmt: skip
CLOCK = {"time", "events", "fissions", "age", "occupant", "generation", "next_carrier", "status"}


def test_the_start_bound_and_checkpoint_records_are_frozen(tmp_path):
    spec = parse_spec(definition(world(), fissions=3))
    state = runner.run(spec, stop=9).checkpoint()
    assert set(state.clock) == CLOCK
    checkpoints.write(tmp_path / "cp", state)
    assert set(json.loads((tmp_path / "cp" / "checkpoint.json").read_text())) == CHECKPOINT
    continued = runner.run(spec, start=state)
    assert set(continued.start) == START and continued.start["kind"] == "restart"
    data = definition(world(), fissions=2)
    data["execution"] |= {"mode": "every_descendant", "lanes": 2}
    data["experiment"]["life_budget"] = 50
    population = runner.run_population(parse_spec(data))
    assert set(population.bound) == BOUND
    records.write_run(tmp_path / "population", population)
    run_json = json.loads((tmp_path / "population" / "run.json").read_text())
    assert set(run_json) == RUN_FIELDS | {"bound"} and run_json["end"]["lives"] == 7
