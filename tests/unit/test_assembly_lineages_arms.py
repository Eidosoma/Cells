"""Ensemble arms (arms.py): one definition, many worlds, keyed by world ID, in lane batches.

Each claim with a planted error it must catch (D187):
- a world's records do not depend on the lane width or on its batch (planted: worlds keyed by
  their lane in the batch instead of their world ID, which moves records with the width);
- a batch paused between device calls and resumed from its checkpoints is the unpaused arm,
  bitwise (planted: a resume that keys the resumed lane by its batch position);
- the arm owns the seed and the lineage word (a definition holding others is refused).
"""

import dataclasses

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages import arms, runner
from tests.assembly_lineage_fixtures import definition, world

THE_WORLD = world(count=5, size=10, seed=13)


def the_arm(worlds=7, start=40):
    return arms.parse(
        {
            "definition": definition(THE_WORLD, fissions=3, seed=9),
            "worlds": worlds,
            "world_id_start": start,
            "seed": 9,
        }
    )


def same(a, b):
    groups = ("rows", "fissions", "trace", "lives")
    return all(
        np.array_equal(
            getattr(a, g)[k], getattr(b, g)[k], equal_nan=getattr(a, g)[k].dtype.kind == "f"
        )
        for g in groups
        for k in getattr(a, g)
    )


@pytest.fixture(scope="module")
def reference():
    return arms.run(the_arm(), lanes=7)


def test_records_do_not_depend_on_the_lane_width(reference):
    arm = the_arm()
    for lanes in (2, 3):
        runs = arms.run(arm, lanes)
        assert sorted(runs) == list(range(40, 47))
        assert all(same(runs[w], reference[w]) for w in runs)
    assert len({tuple(r.trace["event_channel"][:10]) for r in reference.values()}) == 7
    summary = arms.summary(arm, reference)
    assert summary["arm"]["worlds"] == 7 and set(summary["worlds"]) == {
        str(w) for w in range(40, 47)
    }

    # Planted: a world keyed by its lane in the batch, not its world ID.
    def by_lane(lanes):
        out = {}
        ids = list(arms.world_ids(arm))
        for start in range(0, len(ids), lanes):
            batch = ids[start : start + lanes]
            specs = [arms.world_spec(arm, i) for i in range(len(batch))]
            out.update(zip(batch, runner.run_lanes(specs), strict=True))
        return out

    two, three = by_lane(2), by_lane(3)
    assert not all(same(two[w], three[w]) for w in two)


def joined(first, second, whole):
    """Paused then resumed equals whole, on the trace and the fission table."""
    for name in ("event_channel", "event_time"):
        if not np.array_equal(
            np.concatenate([first.trace[name], second.trace[name]]), whole.trace[name]
        ):
            return False
    return all(
        np.array_equal(np.concatenate([first.fissions[k], second.fissions[k]]), v, equal_nan=True)
        for k, v in whole.fissions.items()
    )


def test_a_paused_arm_resumes_bitwise(reference):
    arm = the_arm()
    paused = arms.run(arm, lanes=4, calls=3)
    stopped = [w for w, r in paused.items() if r.status == "stopped"]
    assert stopped
    resumed = arms.resume(arm, paused, lanes=3)
    for w, r in paused.items():
        if w in resumed:
            assert joined(r, resumed[w], reference[w]), w
            assert resumed[w].lives["life_birth_kind"][0] == "continued"
        else:
            assert same(r, reference[w])
    # Planted: a resume that keys the resumed lane by its batch position.
    w = stopped[-1]
    wrong = dataclasses.replace(
        arms.world_spec(arm, w),
        execution=dataclasses.replace(arms.world_spec(arm, w).execution, lineage=0),
    )
    with pytest.raises(ConfigError, match="keeps the world"):
        runner.run(wrong, start=paused[w].checkpoint())


def test_the_arm_owns_its_seed_and_lineage_word():
    data = definition(THE_WORLD, fissions=3, seed=9, lineage=5)
    with pytest.raises(ConfigError, match="owns the seed"):
        arms.parse({"definition": data, "worlds": 2, "world_id_start": 0, "seed": 9})
    with pytest.raises(ConfigError, match="owns the seed"):
        arms.parse(
            {
                "definition": definition(THE_WORLD, seed=9),
                "worlds": 2,
                "world_id_start": 0,
                "seed": 8,
            }
        )
    assert arms.world_spec(the_arm(), 44).execution.lineage == 44
    assert parse_spec(the_arm().definition).execution.lineage == 0
