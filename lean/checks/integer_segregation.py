"""Compare a compiled FR-43 division to a unit-by-unit reading of the parent's partition draws."""

import argparse
import json
import operator
from pathlib import Path
from tempfile import TemporaryDirectory

import jax
import numpy as np
from validation.fr43_part3 import worlds
from validation.fr43_part3.references.stream_draws import scratch_uniforms

from cells.definitions.partition_spec import add_division
from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.records.io import write_run

SEED = 11
VOLUME_FRACTION = 0.5
DIVISION_S = 0.02
PARENT_COUNTS = ((3, 2), (0, 3), (4, 0), (0, 0))


def division_world(area):
    world = worlds.spec_worlds()["W1_two_subunits_feedback"]
    raw = worlds.base_world(world, dt=0.01, end=0.05, every=0.01)
    division = add_division(
        raw,
        division_id="first",
        parent=worlds.CELL,
        daughters=worlds.DAUGHTERS,
        volume_fraction=VOLUME_FRACTION,
        area_fractions={worlds.PATCH: area},
        mismatch_carriers={"Na": 0.5, "K": 0.5},
    )
    states = [s["id"] for s in world["unit_states"]]
    parents = [
        worlds.site(f"site_{i}", dict(zip(states, n, strict=True)))
        for i, n in enumerate(PARENT_COUNTS)
    ]
    children = []
    maps = []
    for parent in parents:
        ids = [f"{parent['id']}_{d}" for d in worlds.DAUGHTERS]
        maps.append((parent["id"], ids))
        for name, daughter in zip(ids, worlds.DAUGHTERS, strict=True):
            children.append(
                worlds.site(name, dict.fromkeys(states, 0), patch=f"{worlds.PATCH}_{daughter}")
            )
    units = worlds.population(world, sites=parents + children, division="independent_segregation")
    # Only division can change the counts. Active units can still transfer material.
    for channel in units["channels"]:
        channel["rate_per_s"] = 0.0
    raw["model"]["operators"] = [
        dict(law=worlds.STATE, populations=[]),
        dict(law=worlds.PARTITION, divisions=[division]),
        worlds.block([units], seed=SEED, divisions=maps),
    ]
    raw["experiment"]["partition_events"] = [
        dict(division="first", time=DIVISION_S, carriers=["c1", "c2"])
    ]
    return raw, [s["subunits"] for s in world["unit_states"]]


def recipients(draws, fraction, *, wins=operator.lt, reverse_states=False):
    """Visit individual parent units in declaration order, omitting unused padding."""
    first = np.zeros_like(PARENT_COUNTS, dtype=np.int64)
    for site, (counts, words) in enumerate(zip(PARENT_COUNTS, draws, strict=True)):
        indices = range(len(counts))
        if reverse_states:
            indices = reversed(indices)
        stream = iter(words)
        for k in indices:
            first[site, k] = sum(wins(next(stream), fraction) for _ in range(counts[k]))
    return np.stack((first, np.asarray(PARENT_COUNTS) - first), axis=1)


def compare(bundle):
    # Set the area's binary64 fraction equal to the third occupied unit's draw. A weak
    # comparison differs on a real draw in this compiled world.
    area = scratch_uniforms(SEED, 0, "partition", 0, 3)[2]
    raw, weights = division_world(area)
    parents = np.asarray(PARENT_COUNTS, dtype=np.int64)
    width = int((parents @ weights).max())
    draws = [scratch_uniforms(SEED, i, "partition", 0, width) for i in range(len(parents))]
    expected = recipients(draws, area)
    zeros = np.zeros_like(parents)
    children = expected.reshape(-1, parents.shape[1])
    before = np.vstack((parents, np.zeros_like(children)))
    after = np.vstack((zeros, children))
    signed = after - before

    write_run(bundle, run(parse_spec(raw)))
    with np.load(bundle / "trajectory.npz") as rows:
        times = rows["accepted_times"]
        # The event runs at the start of the step leaving its time, after that time's saved row.
        applied = times > DIVISION_S
        np.testing.assert_array_equal(rows["division_applied"][:, 0].astype(bool), applied)
        assert np.any(applied) and np.any(~applied)
        for done, counts, records in zip(
            applied, rows["integer_counts"], rows["integer_divided_units"], strict=True
        ):
            np.testing.assert_array_equal(counts, after if done else before)
            np.testing.assert_array_equal(records, signed if done else np.zeros_like(before))
            np.testing.assert_array_equal((counts - records) @ weights, before @ weights)
        measured = rows["integer_counts"][-1, len(parents) :].reshape(expected.shape)
        assert np.issubdtype(measured.dtype, np.integer)
        np.testing.assert_array_equal(measured.sum(axis=1), parents)
        np.testing.assert_array_equal((measured @ weights).sum(axis=1), parents @ weights)
        samples = times.tolist()
        first_postdivision = float(times[applied][0])

    alternatives = {
        "volume_fraction": recipients(draws, VOLUME_FRACTION),
        "tie_to_first": recipients(draws, area, wins=operator.le),
        "reversed_state_order": recipients(draws, area, reverse_states=True),
    }
    rejected = {}
    for name, alternative in alternatives.items():
        np.testing.assert_array_equal(alternative.sum(axis=1), parents)
        mismatches = int(np.count_nonzero(alternative[:, 0] != measured[:, 0]))
        assert mismatches > 0, name
        rejected[name] = mismatches

    return dict(
        seed=SEED,
        draw_block=width,
        membrane_area_fraction=area,
        fraction_hex=area.hex(),
        volume_fraction=VOLUME_FRACTION,
        division_s=DIVISION_S,
        first_postdivision_sample_s=first_postdivision,
        saved_times_s=samples,
        subunits_per_state=weights,
        parent_counts=parents.tolist(),
        daughter_counts=measured.tolist(),
        signed_division_records=signed.tolist(),
        weighted_parent=(parents @ weights).tolist(),
        weighted_daughters=(measured @ weights).tolist(),
        mismatched_first_daughter_entries=rejected,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, help="keep the native model run at this path")
    args = parser.parse_args()
    jax.config.update("jax_enable_x64", True)
    with TemporaryDirectory() as temporary:
        print(
            json.dumps(
                compare(args.bundle or Path(temporary) / "division"), indent=2, allow_nan=False
            )
        )
