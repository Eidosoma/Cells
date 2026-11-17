"""Every descendant (mode every_descendant; RELATIONSHIPS_DESIGN §1.4, P-a; keys.py).

Each claim with a planted error it must catch (D187):
- the followed path is the single lineage, bitwise, at lane widths 1, 3 and 4: every row (counts,
  cumulative ledgers, times, keys), fission, growth, event, time and draw (planted: one event's
  time moved by one unit in the last place);
- the lives are the founder and both daughters of every fission, keys are unique, and every
  sub-lineage is numbered by the rule (generation, parent key, daughter index), re-derived here
  from the tree alone (planted: numbering by fission time instead);
- horizons G and G + 1 give the same keys and lives up to G; the ledger closes at every row of
  every path;
- a budget that binds censors a whole generation at its birth, and the run says so (planted: a
  dropped life, which the census catches).
"""

import copy

import numpy as np
import pytest

from cells.core.specs import ConfigError, parse_spec
from cells.models.assembly_lineages import keys, runner
from tests.assembly_lineage_fixtures import definition, world

THE_WORLD = world(count=6, size=12, seed=11)


def population(fissions=4, budget=1000, lanes=4):
    data = definition(THE_WORLD, fissions=fissions, uniforms=True)
    data["execution"] |= {"mode": "every_descendant", "lanes": lanes}
    data["experiment"]["life_budget"] = budget
    return parse_spec(data)


@pytest.fixture(scope="module")
def single():
    return runner.run(parse_spec(definition(THE_WORLD, fissions=4, uniforms=True)))


@pytest.fixture(scope="module")
def runs():
    return {lanes: runner.run_population(population(lanes=lanes)) for lanes in (1, 3, 4)}


def followed_path(run):
    table = run.fissions
    by_parent = {int(k): i for i, k in enumerate(table["fission_parent"])}
    path = [keys.FOUNDER]
    while path[-1] in by_parent:
        i = by_parent[path[-1]]
        path.append(int(table["fission_daughters"][i, int(table["fission_followed"][i])]))
    return path


def path_view(run):
    """The followed path's records, selected from an every-descendant run."""
    path = followed_path(run)
    rows = np.isin(run.rows["occupant"][:, 0], path)
    fissions = np.isin(run.fissions["fission_parent"], path)
    growths = np.isin(run.trace["growth_carrier"], path)
    edges = np.concatenate(([0], np.cumsum(run.trace["events_per_growth"])))
    events = np.concatenate(
        [np.arange(edges[g], edges[g + 1]) for g in np.flatnonzero(growths)]
    ).astype(int)
    out = {f"rows.{k}": v[rows] for k, v in run.rows.items()}
    out |= {f"fissions.{k}": v[fissions] for k, v in run.fissions.items() if k != "fission_slot"}
    out |= {
        "trace.event_channel": run.trace["event_channel"][events],
        "trace.event_time": run.trace["event_time"][events],
        "trace.events_per_growth": run.trace["events_per_growth"][growths],
        "trace.growth_carrier": run.trace["growth_carrier"][growths],
        "diagnostics.event_uniforms": run.diagnostics["event_uniforms"][events],
        "diagnostics.partition_uniforms": run.diagnostics["partition_uniforms"][fissions],
        "diagnostics.continuation_uniform": run.diagnostics["continuation_uniform"][fissions],
    }
    return out


def differences(view, single):
    """The arrays in which a path view differs from the single lineage (empty: none)."""
    out = []
    for name, values in view.items():
        group, key = name.split(".")
        if key == "fission_slot":
            continue
        if not np.array_equal(getattr(single, group)[key], values, equal_nan=True):
            out.append(name)
    return out


def test_the_followed_path_is_the_single_lineage_bitwise(single, runs):
    for lanes, run in runs.items():
        view = path_view(run)
        assert differences(view, single) == [], lanes
        assert run.closure["checked"] and run.closure["holds"], lanes
    planted = dict(path_view(runs[3]))
    planted["trace.event_time"] = planted["trace.event_time"].copy()
    planted["trace.event_time"][5] = np.nextafter(planted["trace.event_time"][5], np.inf)
    assert differences(planted, single) == ["trace.event_time"]


def derived_keys(run, order):
    """Every life's key, re-derived from the tree alone by the rule (keys.py), with new
    sub-lineages numbered in `order`: the rule's (generation, parent key, daughter index), or a
    planted one."""
    table, lives = run.fissions, run.lives
    by_parent = {int(k): i for i, k in enumerate(table["fission_parent"])}
    generation = {keys.FOUNDER: 0}
    counter = {keys.FOUNDER: keys.key(0, 1)}
    expect = {keys.FOUNDER: keys.FOUNDER}
    sizes = dict(zip(lives["life_key"].tolist(), lives["life_size_at_birth"].tolist(), strict=True))
    frontier, next_sub = [keys.FOUNDER], 1
    while frontier:
        starters, born = [], []
        for parent in frontier:
            if parent not in by_parent:
                continue
            i = by_parent[parent]
            first = counter[parent]
            followed = int(table["fission_followed"][i])
            daughters = [first, first + 1]
            for d, child in enumerate(daughters):
                expect[int(table["fission_daughters"][i, d])] = child
                generation[child] = generation[parent] + 1
                born.append(int(table["fission_daughters"][i, d]))
                if d == followed:
                    counter[child] = first + 2
                elif sizes[int(table["fission_daughters"][i, d])] > 0:
                    starters.append((generation[child], parent, d, table["fission_time"][i], child))
        for n, (_, _, _, _, child) in enumerate(sorted(starters, key=order)):
            counter[child] = keys.key(next_sub + n, 1)
        next_sub += len(starters)
        frontier = born
    return expect


def test_keys_follow_the_rule_from_the_tree_alone(runs):
    run = runs[4]
    lives = run.lives
    assert len(set(lives["life_key"].tolist())) == len(lives["life_key"])
    assert len(lives["life_key"]) == 1 + 2 * len(run.fissions["fission_time"])
    rule = derived_keys(run, order=lambda s: (s[0], s[1], s[2]))
    assert all(rule[k] == k for k in lives["life_key"].tolist())
    spelled = [keys.spelled(k) for k in lives["life_key"].tolist()]
    assert spelled[:7] == ["0:0", "0:1", "0:2", "0:3", "0:4", "1:1", "1:2"]  # §5.3's example.
    assert spelled.index("0:5") < spelled.index("2:1")  # The followed path keeps 0:5, 0:6.
    planted = derived_keys(run, order=lambda s: (s[0], s[3], s[2]))  # By fission time.
    assert any(planted[k] != k for k in lives["life_key"].tolist())
    for lanes in (1, 3):
        assert runs[lanes].lives["life_key"].tolist() == lives["life_key"].tolist()


def test_a_longer_horizon_keeps_the_keys_and_lives(runs):
    short, longer = runs[4], runner.run_population(population(fissions=5))
    upto = longer.lives["life_generation"] <= 4
    for name in (
        "life_key",
        "life_parent",
        "life_sublineage",
        "life_birth_time",
        "life_size_at_birth",
    ):
        assert np.array_equal(short.lives[name], longer.lives[name][upto], equal_nan=True), name
    divided = short.lives["life_end_reason"] == "divided"
    assert np.array_equal(
        short.lives["life_end_time"][divided], longer.lives["life_end_time"][upto][divided]
    )
    leaves = short.lives["life_generation"] == 4
    assert set(short.lives["life_censored_by"][leaves].tolist()) <= {"horizon", ""}


def census(run):
    lives = run.lives
    ran = lives["life_end_reason"] == "divided"
    return int(ran.sum()) * 2 + 1 == len(lives["life_key"])


def test_a_binding_budget_censors_a_whole_generation(runs):
    full = runs[4]
    runnable = [int(np.sum(full.lives["life_generation"] == g)) for g in range(5)]
    budget = sum(runnable[:3]) + 1  # Generation 3's lives exceed what is left.
    run = runner.run_population(population(budget=budget))
    lives = run.lives
    assert run.status == "budget" and census(run)
    assert set(lives["life_censored_by"][lives["life_generation"] == 3].tolist()) == {"budget"}
    assert lives["life_generation"].max() == 3
    assert run.bound["lives_at_most"] == min(2**5 - 1, 2 * budget + 1)
    assert len(lives["life_key"]) <= run.bound["lives_at_most"]
    assert (
        lives["life_key"].tolist()
        == full.lives["life_key"][full.lives["life_generation"] <= 3].tolist()
    )
    planted = copy.copy(run)
    planted.lives = {k: v[:-1] for k, v in lives.items()}  # A dropped life.
    assert not census(planted)
    with pytest.raises(ConfigError, match="life_budget"):
        data = definition(THE_WORLD, fissions=3)
        data["execution"]["mode"] = "every_descendant"
        parse_spec(data)


SMALL = world(
    count=3,
    size=4,
    founder_size=2,
    daughter="uniform",
    empty="other",
    partition={"rule": "binomial", "probability": 0.25},
)


def small(seed, fissions, *, mode="every_descendant"):
    data = definition(SMALL, fissions=fissions, seed=seed, uniforms=True, limit=400)
    if mode == "every_descendant":
        data["execution"] |= {"mode": mode, "lanes": 3}
        data["experiment"]["life_budget"] = 5000
    return parse_spec(data)


def test_empty_and_born_at_size_daughters_keep_every_rule():
    """Binomial splits at size 4 (p = 0.25) make daughters with no molecule and daughters born at
    the fission size. Every rule holds there: the followed path is the single lineage, keys follow
    the rule from the tree (an empty daughter takes no sub-lineage), and a longer horizon keeps
    the keys and lives."""
    empty = at_size = 0
    for seed in (2, 3, 4, 7):
        pop = runner.run_population(small(seed, 5))
        lives = pop.lives
        assert differences(path_view(pop), runner.run(small(seed, 5, mode="single_lineage"))) == []
        rule = derived_keys(pop, order=lambda s: (s[0], s[1], s[2]))
        assert all(rule[k] == k for k in lives["life_key"].tolist())
        none = lives["life_size_at_birth"] == 0
        assert np.all(lives["life_end_reason"][none] == "extinct")
        assert np.all(lives["life_sublineage"][none] == -1)  # Unfollowed: "other" moves the pick.
        empty += int(none.sum())
        at_size += int(np.sum(lives["life_size_at_birth"] == 4))
        assert pop.closure["holds"]
        longer = runner.run_population(small(seed, 6))
        upto = longer.lives["life_generation"] <= 5
        for name in ("life_key", "life_parent", "life_sublineage", "life_size_at_birth"):
            assert np.array_equal(lives[name], longer.lives[name][upto]), (seed, name)
    assert empty > 0 and at_size > 0  # Both cases occurred.
