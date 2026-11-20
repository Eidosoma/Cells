"""FR-20 in cells.assembly_lineages@2: cells.pool_replacement@1, a pulse and a washout
(docs/ASSEMBLY_WASHOUT_DESIGN.md §7; D240; the lead's conditions of 20 November 2026).

One three-phase world. Two vesicles carry a two-state gate (G <-> H: G speeds the tracer's
permeation, H slows it) and a site Y that binds the tracer S in the membrane (S + Y <-> C). The
founder pool holds no tracer; a pulse (a replacement whose pool holds S) comes at 1 s, and a wash
(a tracer-free replacement) at 2 s.

Each claim with a planted error it must catch (D187):
- W1: at each replacement every slot's places and keys, the gate's forms and the bound tracer
  included, equal those of the world stopped at the last event before it (FR-22), bitwise, and the
  pool's finite places equal the declared pool (planted: a replacement that also empties the
  lumen);
- W2: the sink's and the schedule column's increments are F(old pool) and F(fresh pool), computed
  apart, and the books close (planted: the fresh pool left unbooked, which the ledger refuses);
- W3: the removed counts are the stopped world's pool, the supplied counts the pool after (planted:
  removed counts taken after the replacement);
- W4: the first event after each replacement is the host's pick at the replaced pool, with the
  device's own uniforms; after the wash no tracer entry precedes a release, and one follows
  (planted: stale rates, the refresh returning its input after its first call);
- W5: a replacement draws nothing (planted: one draw per living assembly, as a transfer's);
- W6: the refusals: no population, an omitted pool species, solutes above c_ext, a held species
  the assemblies take up (Q3 as built), and a replacement at another schedule's declared time;
- around a wash (FR-22): a cut at the last event before each replacement and at the first after
  it, resumed bitwise; and the definition's round trip keeps its fingerprint;
- FR-21's acceptance (the requester's, relayed by the lead on 20 November 2026): on the
  one-particle fixture, a pool ligand X binds a declared site R in one step to its declared
  complex XR (the requester's S and XS; this world's S is a lumen solute). Immediately before the
  wash the pool holds 8 free X, the particle 4 vacant and 2 occupied sites; the wash by X-free
  liquid removes 8 X, supplies none and keeps the particle's 4 and 2. With no free X, binding's
  rate is exactly 0, so the binding step's next event is a release: 1 free X, 5 vacant, 1 occupied.
  A rebinding then restores the post-wash counts (seed-specific: the rates make it about 0.996
  likely before a second release). Both states are read from runs stopped at those events.

World-compiling cost: one population program (K = 2) and about 14 runs, 51.4 s for the whole file
on the timed lane, before FR-21's acceptance, which adds one program (K = 1) and three runs.
Reason: the claims are the runs' own stops, books and events.
"""

import copy
import functools

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages import folds
from cells.models.assembly_lineages_v2 import (
    SHARED_POOL,
    checkpoints,
    division,
    model,
    population,
    runner,
)
from tests.assembly_lineage_v2_fixtures import definition, site_binding, species, step
from tests.unit.test_assembly_lineages_v2_checkpoints import differences
from tests.unit.test_assembly_lineages_v2_lumen import K_L, osmotic_world
from tests.unit.test_assembly_lineages_v2_population import FOUNDER, host_rates

PULSE, WASH = 1.0, 2.0
TRACER_STEPS = ("entry", "join_S")  # the tracer's moves between the pool and a vesicle


def raw_world():
    """The three-phase world's raw definition (module docstring), before its schedules."""
    w = osmotic_world(L_pool=30, L_mem=0, S_pool=0, S_lumen=0, I_lumen=0, floor=4 * K_L)
    u = "unsourced; test"
    for sp in w["species"]:
        if sp["id"] == "S":
            sp["standard_mu_RT"]["bilayer"] = 0.5
    for name, moieties in (("G", {"g": 1}), ("H", {"g": 1}), ("Y", {"y": 1}),
                           ("C", {"y": 1, "s": 1})):  # fmt: skip
        w["species"].append(species(name, moieties, solution=0.0,
                                    bilayer=-5.0 if name == "C" else -2.0))  # fmt: skip
        w["phases"]["membrane"]["species"].append(name)
        w["phases"]["pool"]["species"].append({"id": name, "kind": "finite"})
        w["geometry"]["area_per_leaflet"][name] = {"quanta": 60, "provenance": u}
    w["phases"]["membrane"]["species"].append("S")
    w["geometry"]["area_per_leaflet"]["S"] = {"quanta": 60, "provenance": u}
    entry = next(s for s in w["steps"] if s["id"] == "entry")
    entry["permeability_m_per_s"]["value"] = 5e-9
    join = next(s for s in w["steps"] if s["id"] == "join")
    w["steps"] += [
        step("flip", {"G": 1}, {"H": 1}, 0.5, phase="membrane"),
        dict(join, id="join_S", reactants={"S@pool": 1}, products={"S@membrane": 1},
             insertion_velocity_m_per_s={"value": 2e-8, "provenance": u}),
        step("bind", {"S": 1, "Y": 1}, {"C": 1}, 30.0, phase="membrane"),
    ]  # fmt: skip
    w["rate_factor"] = {
        "law": "cells.transition_state_factor@1",
        "catalysing_phase": "membrane",
        "entries": [{"catalyst": "G", "step": "entry", "ddG_kT": 2.0},
                    {"catalyst": "H", "step": "entry", "ddG_kT": -2.0}],
    }  # fmt: skip
    vesicle = {"L@membrane": 8, "G@membrane": 1, "H@membrane": 1, "Y@membrane": 2,
               "C@membrane": 0, "S@membrane": 0, "S@lumen": 0, "I@lumen": 2}  # fmt: skip
    w["population"] = {"structure": SHARED_POOL, "slots": 2,
                       "founders": [vesicle, dict(vesicle, **{"L@membrane": 9})]}  # fmt: skip
    w["founder"] = {"L@pool": 30, "S@pool": 0, "I@pool": 0, "G@pool": 0, "H@pool": 0,
                    "Y@pool": 0, "C@pool": 0}  # fmt: skip
    w["founder"] |= {k: 0 for k in vesicle}
    d = definition(w, molecules=128, horizon=2.5, event_limit=20000, row_every=20, uniforms=True)
    d["execution"]["mode"] = "population"
    return d


def pool_of(d, **counts):
    """One count per finite pool place, in place order (the replacement's `pool`)."""
    finite = [p["id"] for p in d["model"]["world"]["phases"]["pool"]["species"]
              if p["kind"] == "finite"]  # fmt: skip
    return [counts.get(name, 0) for name in finite]


def wash_spec(d=None):
    d = copy.deepcopy(d or raw_world())
    d["experiment"]["schedules"] = [
        {"index": 1, "kind": "replacement", "times_s": [PULSE], "pool": pool_of(d, L=30, S=12)},
        {"index": 2, "kind": "replacement", "times_s": [WASH], "pool": pool_of(d, L=30)},
    ]
    return parse_spec(d)


@functools.lru_cache(maxsize=None)
def world():
    """(spec, the uninterrupted run, its replacements [(record, row, events before it)])."""
    spec = wash_spec()
    a = runner.run(spec).check()
    rows, out = a.rows, []
    for r in a.population["replacements"]:
        i = int(np.flatnonzero((rows["row_kind"] == population.REPLACEMENT)
                               & (rows["row_time"] == r["time_s"]))[0])  # fmt: skip
        out.append((r, i, int(rows["row_event"][i])))
    return spec, a, tuple(out)


@functools.lru_cache(maxsize=None)
def stopped(k):
    """The world stopped at its k-th event (FR-22)."""
    return runner.run(world()[0], stop=k).check()


def padded(vector, size):
    out = np.zeros(size, dtype=np.int64)
    out[: len(vector)] = vector
    return out


def replacement_rows(run):
    """[(row, events before it)] of a run's replacements."""
    rows = np.flatnonzero(run.rows["row_kind"] == population.REPLACEMENT)
    return [(int(i), int(run.rows["row_event"][i])) for i in rows]


def planted_replace(monkeypatch, after):
    """population._replace, then `after(spec, state, ctx)` (a plant)."""
    real = population._replace

    def replace(spec, state, ctx, world_f, time, schedule, n_events):
        real(spec, state, ctx, world_f, time, schedule, n_events)
        after(spec, state, ctx)

    monkeypatch.setattr(population, "_replace", replace)


def restate(ctx, state, extra=None):
    """The last stop's saved state and bookings, as a plant changed them."""
    n, kind, t, _, saved = ctx.stops[-1]
    ctx.stops[-1] = (n, kind, t, state.copy(), saved if extra is None else extra.copy())


def test_a_replacement_keeps_every_slot_and_replaces_the_pool(monkeypatch):
    spec, a, at = world()
    w, places = spec.model.world, len(spec.model.world.places)
    names = [p.name for p in w.places]
    gate_and_bound = [names.index(f"{x}@membrane") for x in ("G", "H", "C")]
    for r, i, n in at:
        b = stopped(n)
        assert np.array_equal(a.rows["slot_count"][i], b.final["slots"][:, :places])
        assert np.array_equal(a.rows["slot_key"][i], b.rows["slot_key"][-1])
        pool = a.rows["pool_count"][i]
        assert {name: int(pool[names.index(name)]) for name in r["supplied"]} == r["supplied"]
    bound = a.rows["slot_count"][at[1][1]][:, gate_and_bound]  # at the wash: gate and complex held
    assert bound[:, 2].sum() > 0 and bound[:, 0].sum() + bound[:, 1].sum() > 0

    def empty_the_lumen(spec, state, ctx):  # Planted: the lumen emptied with the pool.
        lumen = [j for j, p in enumerate(spec.model.world.places) if p.phase == "lumen"]
        state.slots[:, lumen] = 0
        restate(ctx, state)

    planted_replace(monkeypatch, empty_the_lumen)
    planted = runner.run(spec)
    r, i, n = at[0]
    assert not np.array_equal(planted.rows["slot_count"][i], stopped(n).final["slots"][:, :places])


def test_the_books_close_with_the_old_pool_to_the_sink_and_the_fresh_from_its_source(
    monkeypatch,
):
    spec, a, at = world()
    layout = model.layout(spec)
    world_f = population._energy(spec, layout)
    K = spec.model.world.population["slots"]
    sink, columns = a.rows["discarded_free_energy_kT"], a.rows["schedule_work_kT"]
    order = a.population["schedule_columns"]
    assert a.closure["holds"]
    for r, i, n in at:
        b = stopped(n)
        empty = population._State(b.final["pool"], b.final["slots"], np.zeros(K, dtype=bool),
                                  np.full(K, -1), b.final["supplied"])  # fmt: skip
        old = world_f(empty)
        empty.pool = padded(a.rows["pool_count"][i], b.final["pool"].size)
        fresh = world_f(empty)
        assert sink[i] - sink[i - 1] == pytest.approx(old, rel=1e-12, abs=1e-12)
        c = order.index(r["schedule"])
        assert columns[i, c] - columns[i - 1, c] == pytest.approx(fresh, rel=1e-12, abs=1e-12)
        assert r["sink_kT"] == old and r["work_kT"] == pytest.approx(fresh, rel=1e-12)

    def unbooked(spec, state, ctx):  # Planted: the fresh pool's F left unbooked.
        work = ctx.replacements[-1]["work_kT"]
        ctx.extra[population.E_TRANSFER] -= work
        ctx.extra[population.EXTRA + ctx.columns.index(ctx.replacements[-1]["schedule"])] -= work
        restate(ctx, state, ctx.extra)

    planted_replace(monkeypatch, unbooked)
    with pytest.raises(runner.LedgerRefused, match="does not close"):
        runner.run(spec).check()


def test_the_material_record_is_the_old_pool_and_the_fresh(monkeypatch):
    spec, a, at = world()
    names = [p.name for p in spec.model.world.places]
    for r, _, n in at:
        old = stopped(n).final["pool"]
        assert r["removed"] == {name: int(old[names.index(name)]) for name in r["removed"]}
        assert sum(r["removed"].values()) > 0
    assert at[1][0]["removed"]["S@pool"] > 0  # the wash takes tracer away

    def taken_after(spec, state, ctx):  # Planted: removed counts read after the replacement.
        record = ctx.replacements[-1]
        record["removed"] = dict(record["supplied"])

    planted_replace(monkeypatch, taken_after)
    planted = runner.run(spec)
    assert planted.population["replacements"][0]["removed"] != at[0][0]["removed"]


def pick(spec, a, i, n):
    """(group, signed channel) the host picks at row i's state with the n-th event's uniforms."""
    structure = model.structure(spec)
    P, R = structure.places, structure.steps
    pool = padded(a.rows["pool_count"][i], P)
    slots = np.stack([padded(v, P) for v in a.rows["slot_count"][i]])
    rates, _ = host_rates(spec, pool, slots, a.rows["slot_key"][i] >= 0)
    u = a.diagnostics["event_uniforms"][n]
    prefixes = np.stack([folds.prefix(g, np) for g in rates])
    totals = prefixes[:, -1]
    running = folds.prefix(totals, np)
    a0 = running[-1]
    g = int(np.argmax(running > min(u[1] * a0, np.nextafter(a0, 0.0))))
    j = int(np.argmax(prefixes[g] > min(u[2] * totals[g], np.nextafter(totals[g], 0.0))))
    return g, (j + 1 if j < R else -(j - R + 1))


def test_the_rates_follow_the_replaced_pool_and_released_tracer_re_enters(monkeypatch):
    spec, a, at = world()
    trace = a.trace
    for _, i, n in at:
        assert pick(spec, a, i, n) == (int(trace["event_group"][n]), int(trace["event_channel"][n]))
    steps = [s.id for s in spec.model.world.steps]
    tracer = [steps.index(x) + 1 for x in TRACER_STEPS]
    moves = [int(c) for c, t in zip(trace["event_channel"], trace["event_time"], strict=True)
             if t > WASH and abs(int(c)) in tracer]  # fmt: skip
    assert moves[0] < 0 and any(c > 0 for c in moves)  # a release first, then a re-entry

    real = population.program  # Planted: the device's rates left stale after a host stop.

    def stale(structure):
        advance, refresh = real(structure)
        calls = []

        def frozen(lanes, layouts, ms):
            calls.append(1)
            return refresh(lanes, layouts, ms) if len(calls) == 1 else lanes

        return advance, frozen

    monkeypatch.setattr(population, "program", stale)
    planted = runner.run(spec)
    events = planted.trace
    assert any(
        pick(spec, planted, i, n)
        != (int(events["event_group"][n]), int(events["event_channel"][n]))
        for i, n in replacement_rows(planted)
    )


def test_a_replacement_draws_nothing(monkeypatch):
    spec, a, at = world()
    assert a.population["schedule_draws"] == []

    def draws(spec, state, ctx):  # Planted: a draw per living assembly, as a transfer's.
        ctx.schedule_draws += [(ctx.replacements[-1]["schedule"], k, 0.5, "transfer", np.nan)
                               for k in range(int(state.alive.sum()))]  # fmt: skip

    planted_replace(monkeypatch, draws)
    assert runner.run(spec).population["schedule_draws"] != []


def refusal(case):
    d = raw_world()
    replacement = {"index": 1, "kind": "replacement", "times_s": [PULSE],
                   "pool": pool_of(d, L=30)}  # fmt: skip
    d["experiment"]["schedules"] = [replacement]
    if case == "no population":
        w = d["model"]["world"]
        d["execution"]["mode"] = "single_lineage"
        w["founder"] |= w.pop("population")["founders"][0]
    elif case == "an omitted species":
        replacement["pool"] = replacement["pool"][:-1]
    elif case == "solutes above c_ext":
        replacement["pool"] = pool_of(d, L=10**9)
    elif case == "a held species the vesicles take up":
        pool = d["model"]["world"]["phases"]["pool"]["species"]
        pool[0] = {"id": "L", "kind": "held", "held_mM": 1.0}
        del d["model"]["world"]["founder"]["L@pool"]
        replacement["pool"] = pool_of(d, S=0)
    elif case == "a shared time":
        d["experiment"]["schedules"].append(dict(replacement, index=2))
    elif case == "a shear at its time":
        d["model"]["world"]["division"] = {"law": division.SHEAR_FISSION}
        d["experiment"]["schedules"].append({"index": 2, "kind": "shear", "k": 2,
                                              "times_s": [PULSE]})  # fmt: skip
    elif case == "a transfer at its time":
        d["experiment"]["schedules"].append({"index": 2, "kind": "transfer", "times_s": [PULSE],
                                              "K_keep": 1, "fresh_pool": pool_of(d)})  # fmt: skip
    return d


REFUSALS = {
    "no population": "needs a population",
    "an omitted species": "one count per finite pool place",
    "solutes above c_ext": "exceed c_ext",
    "a held species the vesicles take up": "could never be washed out",
    "a shared time": "shares the time",
    "a shear at its time": "shares the time",
    "a transfer at its time": "shares the time",
}


@pytest.mark.parametrize("case", sorted(REFUSALS))
def test_every_refusal_of_a_replacement(case):
    with pytest.raises(ConfigError, match=REFUSALS[case]):
        parse_spec(refusal(case))


def test_a_cut_around_each_replacement_resumes_bitwise(tmp_path):
    spec, a, at = world()
    assert parse_spec(spec.to_dict()).fingerprint == spec.fingerprint  # the round trip
    for _, _, n in at:
        for k in (n, n + 1):  # the last event before it, the first after it
            b1 = stopped(k)
            path = checkpoints.write(tmp_path / f"c{k}", b1.checkpoint())
            b2 = runner.run(spec, start=checkpoints.read(path)).check()
            assert differences(a, b1, b2, k) == []
            done = b2.population["numbering"]["replacements"]
            assert a.population["replacements"][done:] == b2.population["replacements"]


T_WASH = 1e-7  # s: before the binding's first event (about 3e-4 likely otherwise, at 2.7e3 /s)


def site_wash_spec():
    """FR-21's acceptance world (module docstring): the one-particle fixture (the population tests'
    pop_spec([FOUNDER], 1)) with the declared binding, 8 free X, and the wash at T_WASH. The
    binding's constants (k_f 5000 /s, mu_XR -10) make a released X rebind before another release
    about 0.996 of the time, and a release within the horizon all but certain."""
    w = osmotic_world(L_pool=30, L_mem=0, S_pool=6, S_lumen=0, I_lumen=0, floor=4 * K_L)
    site_binding(w)
    w["founder"]["X@pool"] = 8
    particle = dict(FOUNDER, **{"R@membrane": 4, "XR@membrane": 2})
    w["population"] = {"structure": SHARED_POOL, "slots": 1, "founders": [particle]}
    d = definition(w, molecules=128, horizon=5.0, event_limit=20000, row_every=20, uniforms=True)
    d["execution"]["mode"] = "population"
    d["experiment"]["schedules"] = [
        {"index": 1, "kind": "replacement", "times_s": [T_WASH], "pool": pool_of(d, L=30, S=6)}
    ]
    return parse_spec(d)


def test_a_site_bound_ligand_stays_through_a_wash_and_a_released_one_rebinds():
    spec = site_wash_spec()
    names = [p.name for p in spec.model.world.places]
    structure = model.structure(spec)
    P, R = structure.places, structure.steps
    r = [s.id for s in spec.model.world.steps].index("bind")

    def sites(pool, slot):  # (free X, vacant sites, occupied sites)
        at = names.index
        return int(pool[at("X@pool")]), int(slot[at("R@membrane")]), int(slot[at("XR@membrane")])

    a = runner.run(spec).check()
    (record,) = a.population["replacements"]
    assert record["removed"]["X@pool"] == 8 and record["supplied"]["X@pool"] == 0
    i = int(np.flatnonzero(a.rows["row_kind"] == population.REPLACEMENT)[0])
    pool, slot = a.rows["pool_count"][i], a.rows["slot_count"][i][0]
    assert sites(pool, slot) == (0, 4, 2)  # 8 X removed with no event before: still 4 and 2
    rates, _ = host_rates(spec, padded(pool, P), padded(slot, P)[None, :], np.array([True]))
    assert rates[1][r] == 0.0 and rates[1][R + r] > 0.0  # no free X: binding cannot fire
    trace = a.trace
    moves = [(n, int(c)) for n, (c, t) in enumerate(zip(trace["event_channel"],
                                                        trace["event_time"], strict=True))
             if t > T_WASH and abs(int(c)) == r + 1]  # fmt: skip
    (n1, c1), (n2, c2) = moves[:2]
    assert (c1, c2) == (-(r + 1), r + 1)  # a release, then (for this seed) a rebinding
    for n, after in ((n1, (1, 5, 1)), (n2, (0, 4, 2))):
        b = runner.run(spec, stop=n + 1).check()  # FR-22: the world stopped at that event
        assert sites(b.rows["pool_count"][-1], b.rows["slot_count"][-1][0]) == after
