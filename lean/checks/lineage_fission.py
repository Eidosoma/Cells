"""Size-triggered binary splits, the continued daughter, and inert bead partition data."""

import argparse
import json
import math
import re
from collections import defaultdict
from fractions import Fraction
from functools import partial
from itertools import permutations, product
from pathlib import Path
from statistics import variance
from xml.etree import ElementTree

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.models.assembly_lineages import continuation, fission, runner
from tests.assembly_lineage_fixtures import definition, world


@partial(jax.jit, static_argnames=("rule",))
def split_batch(parent, uniforms, rule, value):
    return jax.vmap(lambda u: fission.split(parent, parent.sum(), u, rule, value))(uniforms)


def partition_controls():
    parent = np.array([2, 0, 1, 1])
    ranks = np.asarray(list(permutations([0.2, 0.4, 0.6, 0.8])))
    masks = np.asarray(list(product([0.25, 0.5], repeat=4)))

    # Padding would win every rank or threshold comparison if accidentally counted.
    def split(draws, rule):
        padded = np.pad(draws, ((0, 0), (0, 3)), constant_values=0.01)
        got = np.asarray(split_batch(parent, padded, rule, 0.5))
        for row, first in zip(draws, got, strict=True):
            indices = (
                sorted(range(4), key=row.__getitem__)[:2]
                if rule == "exact_fraction"
                else np.flatnonzero(row < 0.5)
            )
            expected = np.bincount(np.repeat(np.arange(4), parent)[indices], minlength=4)
            np.testing.assert_array_equal(first, expected)
        return got

    ranked = split(ranks, "exact_fraction")
    independent = split(masks, "binomial")
    np.testing.assert_array_equal(np.bincount(ranked[:, 0]), [4, 16, 4])
    np.testing.assert_array_equal(np.bincount(independent[:, 0]), [4, 8, 4])
    np.testing.assert_array_equal(split(np.full((1, 4), 0.5), "exact_fraction")[0], [2, 0, 0, 0])
    # Rounding happens before floor in the declared float64 rule.
    fractions = [float(np.nextafter(0.3, 0.0)), 0.3]
    quotas = [
        int(split_batch(np.array([10]), np.full((1, 10), 0.5), "exact_fraction", f)[0, 0])
        for f in fractions
    ]
    assert quotas == [2, 3] and math.floor(10 * Fraction.from_float(0.3)) == 2

    sizes = independent.sum(axis=1)
    means, empty = {}, {}
    for policy in ("extinct", "other"):
        all_picks = []
        for u in (np.nextafter(0.5, 0.0), 0.5):
            choice = np.asarray(continuation.choose("uniform", policy, u, (sizes, 4 - sizes)))
            kept = np.where(choice == 0, sizes, 4 - sizes)
            initial = sizes if u < 0.5 else 4 - sizes
            expected = np.where(initial == 0, 4, initial) if policy == "other" else initial
            np.testing.assert_array_equal(kept, expected)
            all_picks.extend(kept.tolist())
        means[policy] = sum(all_picks) / len(all_picks)
        empty[policy] = all_picks.count(0)
    assert means == {"extinct": 2.0, "other": 2.25} and empty == {"extinct": 2, "other": 0}
    return dict(
        exact_marker_empty="4/24",
        fair_marker_empty="4/16",
        mean_retained=means,
        empty_picks_of_32=empty,
        float64_quotas=quotas,
    )


def binomial_variance(n):
    # All masks with exact integer weights for p=1/3. A molecule outside the center has two
    # equally weighted labels. The engine sees U=p as outside and U=p/2 as inside.
    p = 1 / 3
    masks = np.asarray(list(product([False, True], repeat=n)))
    first = np.asarray(split_batch(np.array([n]), np.where(masks, p / 2, p), "binomial", p))[:, 0]
    weights = 2 ** (n - masks.sum(axis=1))
    mass = [int(weights[first == k].sum()) for k in range(n + 1)]
    assert mass == [math.comb(n, k) * 2 ** (n - k) for k in range(n + 1)]
    mean = Fraction(sum(k * w for k, w in enumerate(mass)), 3**n)
    var = sum((k - mean) ** 2 * w for k, w in enumerate(mass)) / 3**n
    assert mean == Fraction(n, 3) and var == Fraction(2 * n, 9)
    return float(var)


def measurements(data):
    bins = {int(n): freq for n, freq in data["parent_count_frequency"].items()}
    assert sum(bins.values()) == data["splits_plotted"]
    by_size = {}
    for key, center in data["center_counts_by_parent"].items():
        n = int(key)
        assert len(center) == bins[n]
        by_size[n] = dict(
            pairs=len(center),
            measured_variance=variance(center),
            predicted_variance=binomial_variance(n),
        )
    expected = sum(freq * (2 / 3) ** n for n, freq in bins.items())
    none = math.prod((1 - (2 / 3) ** n) ** freq for n, freq in bins.items())
    return dict(
        by_size=by_size,
        expected_empty_centers=expected,
        probability_none=none,
        observed_empty_centers=data["zero_center"],
    )


def verify_figure(svg, data):
    counts = defaultdict(list)
    for el in ElementTree.parse(svg).iter():
        path = el.get("d", "")
        if el.get("fill") != "rgb(73.724365%, 86.273193%, 90.194702%)" or path.count("C") != 4:
            continue
        coords = list(map(float, re.findall(r"-?\d+(?:\.\d+)?", path)))
        x = (min(coords[::2]) + max(coords[::2])) / 2
        y = (min(coords[1::2]) + max(coords[1::2])) / 2
        n = round(60 * (x - 173.533203) / 226.878906)
        counts[n].append(round(n * (337.111328 - y) / 62.871094))
    assert {str(n): len(v) for n, v in counts.items()} == data["parent_count_frequency"]
    for n, center in data["center_counts_by_parent"].items():
        assert sorted(counts[int(n)]) == center
    assert sum(v.count(0) for v in counts.values()) == data["zero_center"]
    assert sum(v.count(n) for n, v in counts.items()) == data["zero_both_sides"]


def phi(counts, theta):
    n = int(sum(counts))
    if n == 0:
        return 0.0
    return math.lgamma(n) + math.fsum(
        int(m) * math.log(t) - math.lgamma(int(m) + 1) for m, t in zip(counts, theta, strict=True)
    )


def lineage_definition(rule, value, pick, empty, *, sink="discard", homogeneous=False, limit=6):
    part = {"rule": rule, fission.RULES[rule]: value}
    w = world(
        count=1 if homogeneous else 3,
        size=4,
        matrix=False,
        founder_size=3,
        partition=part,
        daughter=pick,
        empty=empty,
        transfer_constant=1.0 if homogeneous else 8.0,
        supply=1.0,
    )
    w["continuation"]["sink"] = sink
    return definition(w, law=None, fissions=limit, uniforms=True, seed=1)


def lineage(raw):
    spec = parse_spec(raw)
    run = runner.run(spec).check()
    assert run.closure["holds"]
    world = spec.model.world
    types, limit = world.types.count, spec.experiment.fissions
    rule, value = world.fission.partition.rule, world.fission.partition.value
    pick, empty = world.continuation.daughter, world.continuation.empty
    rows, table = run.rows, run.fissions
    counts = rows["assembly_count"][:, :, 0]
    joined, left, discarded = (
        rows[key][:, :, 0] for key in ("joined_total", "left_total", "discarded_total")
    )
    np.testing.assert_array_equal(counts + discarded + left, np.array(world.founder) + joined)
    parents = np.flatnonzero(rows["row_kind"] == runner.PARENT)
    assert len(parents) == len(table["fission_time"]) > 0
    theta = np.asarray(world.types.transfer_constant) * world.supply
    current = np.array(world.founder)
    channels = iter(run.trace["event_channel"])
    errors, births, immediate, work_sink = [], [], 0, []
    for j, r in enumerate(parents):
        parent = counts[r]
        for _ in range(run.trace["events_per_growth"][j]):
            assert 0 < current.sum() < 4
            channel = int(next(channels))
            current[abs(channel) - 1] += 1 if channel > 0 else -1
            assert (current >= 0).all() and current.sum() <= 4
        np.testing.assert_array_equal(current, parent)
        assert parent.sum() == 4 and rows["row_kind"][r + 1] == runner.DAUGHTER
        assert rows["row_time"][r] == rows["row_time"][r + 1] == table["fission_time"][j]
        assert rows["row_event"][r] == rows["row_event"][r + 1]
        draws = run.diagnostics["partition_uniforms"][j, :4]
        indices = (
            sorted(range(4), key=draws.__getitem__)[: math.floor(value * 4)]
            if rule == "exact_fraction"
            else np.flatnonzero(draws < value)
        )
        first = np.bincount(np.repeat(np.arange(types), parent)[indices], minlength=types)
        np.testing.assert_array_equal(first, table["fission_split"][j])
        children = (first, parent - first)
        u = run.diagnostics["continuation_uniform"][j]
        selected = int(pick == "second" or (pick == "uniform" and u >= 0.5))
        if empty == "other" and not children[selected].any():
            selected = 1 - selected
        assert table["fission_followed"][j] == selected
        kept, sibling = children[selected], children[1 - selected]
        current = kept.copy()
        np.testing.assert_array_equal(counts[r + 1], kept)
        np.testing.assert_array_equal(discarded[r + 1] - discarded[r], sibling)
        keys = table["fission_daughters"][j]
        assert rows["occupant"][r, 0] == table["fission_parent"][j]
        assert (keys == [2 * j + 1, 2 * j + 2]).all() and rows["occupant"][r + 1, 0] == keys[
            selected
        ]
        assert rows["generation"][r + 1, 0] == j + 1
        work = phi(parent, theta) - phi(kept, theta) - phi(sibling, theta)
        booked_sink = -phi(sibling, theta)
        for field, target in (
            ("fission_work_kT", work),
            ("discarded_free_energy_kT", booked_sink),
            ("log_weight", -work + booked_sink),
            ("exchange_heat_kT", 0.0),
        ):
            errors.append(abs(float(rows[field][r + 1, 0] - rows[field][r, 0]) - target))
        work_sink.append(
            [work, booked_sink, float(rows["log_weight"][r + 1, 0] - rows["log_weight"][r, 0])]
        )
        births.append(int(kept.sum()))
        if births[-1] == 4 and j + 1 < limit:
            nxt = parents[j + 1]
            assert rows["row_time"][nxt] == rows["row_time"][r]
            assert rows["row_event"][nxt] == rows["row_event"][r]
            np.testing.assert_array_equal(counts[nxt], kept)
            immediate += 1
    assert max(errors) < 2e-12
    assert next(channels, None) is None
    assert run.status == ("extinct" if births[-1] == 0 else "complete")
    return dict(
        birth_sizes=births,
        immediate_resplits=immediate,
        status=run.status,
        max_booking_error_kT=max(errors),
        ledger_residual_kT=run.closure["max_abs_residual_kT"],
        first_work_sink_jump=work_sink[0],
    )


def descendants():
    raw = lineage_definition("exact_fraction", 0.125, "first", "extinct", limit=4)
    raw["execution"].update(mode="every_descendant", lanes=2)
    raw["experiment"]["life_budget"] = 8
    run = runner.run_population(parse_spec(raw)).check()
    assert run.status == "complete" and run.closure["holds"]
    table, lives = run.fissions, run.lives
    assert len(table["fission_time"]) == 4 and np.unique(table["fission_time"]).size == 1
    np.testing.assert_array_equal(table["fission_followed"], 0)
    np.testing.assert_array_equal(table["fission_parent"][1:], table["fission_daughters"][:-1, 1])
    born = lives["life_generation"] > 0
    for gen in range(1, 5):
        np.testing.assert_array_equal(
            sorted(lives["life_size_at_birth"][lives["life_generation"] == gen]), [0, 4]
        )
    assert np.all(lives["life_end_reason"][born & (lives["life_size_at_birth"] == 0)] == "extinct")
    assert np.unique(lives["life_birth_event"][born]).size == 1
    horizon = born & (lives["life_generation"] == 4) & (lives["life_size_at_birth"] == 4)
    assert lives["life_censored_by"][horizon].tolist() == ["horizon"]
    return dict(
        generations=4,
        empty_births=4,
        full_births=4,
        distinct_split_times=1,
        ledger_residual_kT=run.closure["max_abs_residual_kT"],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--figure-svg", type=Path, help="Verify the measurements from the Figure 2 vector page"
    )
    args = parser.parse_args()
    data = json.loads((Path(__file__).with_name("data") / "fornell2017_partition.json").read_text())
    if args.figure_svg:
        verify_figure(args.figure_svg, data)
    controls = partition_controls()
    fixed = lineage(
        lineage_definition("exact_fraction", 0.5, "first", "extinct", limit=1, homogeneous=True)
    )
    extinct = lineage(lineage_definition("exact_fraction", 0.125, "first", "extinct", limit=1))
    fallback = lineage(lineage_definition("exact_fraction", 0.125, "first", "other"))
    full = lineage(
        lineage_definition("exact_fraction", 0.125, "second", "extinct", sink="reservoir")
    )
    ordinary = lineage(lineage_definition("binomial", 0.25, "uniform", "other", limit=12))
    assert extinct["birth_sizes"] == [0]
    assert fallback["birth_sizes"] == full["birth_sizes"] == [4] * 6
    assert fallback["immediate_resplits"] == full["immediate_resplits"] == 5
    assert 0 < ordinary["immediate_resplits"] < 12
    np.testing.assert_allclose(
        fixed["first_work_sink_jump"], [0, math.log(2), math.log(2)], rtol=0, atol=2e-15
    )
    print(
        json.dumps(
            dict(
                partition=controls,
                half=fixed,
                extinct=extinct,
                fallback=fallback,
                second=full,
                binomial=ordinary,
                descendants=descendants(),
                bead_measurements=measurements(data),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
