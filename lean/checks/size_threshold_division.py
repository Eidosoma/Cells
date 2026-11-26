"""Replay the ranked membrane partition from saved size-division events and sink records."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from cells.definitions.specs import parse_spec
from cells.models.assembly_lineages import keys
from cells.models.assembly_lineages_v2 import records, runner, size_division
from cells.records import relations
from tests.unit.test_assembly_lineages_v2_size_division import FOUNDER, SIZE, TYPES, definition, world


def ranked_counts(parent, draws, quota):
    places = [species for species, count in enumerate(parent) for _ in range(count)]
    assert len(places) == len(draws)
    order = sorted(range(len(places)), key=lambda i: (draws[i], i))
    counts = np.zeros(len(parent), dtype=np.int64)
    for i in order[:quota]:
        counts[places[i]] += 1
    return counts


def tied_controls():
    parent = [2, 0, 2, 1]
    cases = [([0.25] * 5, [2, 0, 1, 0]), ([0.2, 0.9, 0.2, 0.2, 0.05], [1, 0, 1, 1])]
    for draws, expected in cases:
        np.testing.assert_array_equal(ranked_counts(parent, draws, 3), expected)
        np.testing.assert_array_equal(size_division.split(parent, draws, 0.6), expected)
    return len(cases)


def replay(directory):
    fraction = 0.4
    spec = parse_spec(definition(world(partition={"rule": "exact_fraction", "fraction": fraction})))
    run = runner.run(spec)
    records.write_run(directory, run)
    _, record, arrays = records.read(directory)
    _, tables = relations.read(directory)
    assert size_division.SIZE_THRESHOLD_DIVISION in record["engine_models"]["operators"]
    membrane = [spec.model.world.place_index(f"{s}@membrane") for s in TYPES]
    quota = int(SIZE * fraction)
    parent = np.array(FOUNDER)
    divided = np.flatnonzero(arrays["row_kind"] == runner.DIVISION)
    events = arrays["fission_event"].tolist()
    assert len(events) == len(divided) == record["division"]["fissions"] and len(events) >= 2
    np.testing.assert_array_equal(arrays["row_event"][divided], events)

    expected_sink = []
    r = 0
    for event, code in enumerate(arrays["event_channel"], start=1):
        assert code != 0
        parent[abs(int(code)) - 1] += 1 if code > 0 else -1
        assert np.all(parent >= 0) and parent.sum() <= SIZE
        if parent.sum() < SIZE:
            continue
        assert code > 0 and event == events[r]
        assert arrays["fission_time"][r] == arrays["event_time"][event - 1]
        np.testing.assert_array_equal(arrays["fission_parent_counts"][r, membrane], parent)
        kept = ranked_counts(parent, arrays["partition_uniforms"][r], quota)
        discarded = parent - kept
        assert 0 < kept.sum() == quota < SIZE and 0 < discarded.sum() == SIZE - quota < SIZE
        np.testing.assert_array_equal(arrays["fission_daughter_counts"][r, 0, membrane], kept)
        np.testing.assert_array_equal(arrays["fission_daughter_counts"][r, 1, membrane], discarded)
        np.testing.assert_array_equal(arrays["place_count"][divided[r], membrane], kept)
        sibling = keys.carrier_id(int(arrays["fission_daughters"][r, 1]))
        for species, count in zip(TYPES, discarded, strict=True):
            if count:
                expected_sink.append((f"event:fission/{r}", sibling, species, int(count)))
        parent = kept
        r += 1
    assert r == len(events)
    sink = sorted((e.event, e.from_, e.species, e.weight) for e in tables["edges"]
                  if e.relation == "removes_to" and e.to == "sink:discard")
    assert sink == sorted(expected_sink)
    return dict(events=len(arrays["event_channel"]), divisions=r, parent_size=SIZE,
                kept=quota, discarded=SIZE - quota, species=len(TYPES), sink_rows=len(sink))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, help="retain the engine bundle in a new directory")
    args = parser.parse_args()
    controls = tied_controls()
    with TemporaryDirectory() as tmp:
        result = replay(args.bundle or Path(tmp) / "bundle")
    print(json.dumps(dict(passed=True, tied_controls=controls, **result), indent=2))
