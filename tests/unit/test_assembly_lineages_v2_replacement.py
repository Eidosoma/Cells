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
import math

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages import folds
from cells.models.assembly_lineages_v2 import (
    SHARED_POOL,
    checkpoints,
    division,
    ledger,
    model,
    population,
    runner,
    streams,
    withdrawal,
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


def withdrawal_wash_spec(d=None):
    """FR-35's restart world: the three-phase world with one withdrawal schedule of two washes (a
    cut between them tests the schedule's draw counter), half the pool each time, the medium's L
    in the withdrawn volume."""
    d = copy.deepcopy(d or raw_world())
    d["experiment"]["schedules"] = [
        {"index": 1, "kind": "withdrawal", "times_s": [PULSE, WASH], "fraction": 0.5,
         "buffer": pool_of(d, L=15)}
    ]  # fmt: skip
    return parse_spec(d)


STOPS = {"replacement": (wash_spec, "replacements", population.REPLACEMENT),
         "withdrawal": (withdrawal_wash_spec, "withdrawals", population.WITHDRAWAL)}  # fmt: skip


@functools.lru_cache(maxsize=None)
def world(kind="replacement"):
    """(spec, the uninterrupted run, its stops [(record, row, events before it)])."""
    build, field, row_kind = STOPS[kind]
    spec = build()
    a = runner.run(spec).check()
    rows, out = a.rows, []
    for r in a.population[field]:
        i = int(np.flatnonzero((rows["row_kind"] == row_kind)
                               & (rows["row_time"] == r["time_s"]))[0])  # fmt: skip
        out.append((r, i, int(rows["row_event"][i])))
    return spec, a, tuple(out)


@functools.lru_cache(maxsize=None)
def stopped(k, kind="replacement"):
    """The world stopped at its k-th event (FR-22)."""
    return runner.run(world(kind)[0], stop=k).check()


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
    if case in SOURCES:
        return held_source(case)
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
    elif case == "a fresh count above the capacity":  # the Lean finding of 20 November
        d["execution"]["molecule_capacity"] = 32
        replacement["pool"] = pool_of(d, L=33)
    elif case == "a transfer's fresh count above the capacity":
        d["execution"]["molecule_capacity"] = 32
        d["experiment"]["schedules"] = [transfer_of(d, L=33)]
    elif case == "a fraction on a replacement":  # FR-35: a partial exchange is a withdrawal
        replacement["fraction"] = 0.5
    elif case.startswith("a withdrawal"):
        d["experiment"]["schedules"] = [withdrawal_of(d)]
        planted = d["experiment"]["schedules"][0]
        if case == "a withdrawal of the whole pool":
            planted["fraction"] = 1.0
        elif case == "a withdrawal of nothing":
            planted["fraction"] = 0.0
        elif case == "a withdrawal buffer of the wrong length":
            planted["buffer"] = planted["buffer"][:-1]
        elif case == "a withdrawal buffer above c_ext":
            planted["buffer"] = pool_of(d, L=10**6)
        elif case == "a withdrawal buffer above the capacity":
            d["execution"]["molecule_capacity"] = 32
            planted["fraction"] = 0.9  # so its concentration in fV stays below c_ext
            planted["buffer"] = pool_of(d, L=33)
        elif case == "a withdrawal at a replacement's time":
            d["experiment"]["schedules"].append(dict(replacement, index=2))
        elif case == "a withdrawal of a held species the vesicles take up":
            pool = d["model"]["world"]["phases"]["pool"]["species"]
            pool[0] = {"id": "L", "kind": "held", "held_mM": 1.0}
            del d["model"]["world"]["founder"]["L@pool"]
            planted["buffer"] = pool_of(d)
        elif case == "a withdrawal without a population":
            w = d["model"]["world"]
            d["execution"]["mode"] = "single_lineage"
            w["founder"] |= w.pop("population")["founders"][0]
    return d


def withdrawal_of(d, fraction=0.5, **counts):
    """A withdrawal at the pulse's time of half the pool, its buffer these counts in fV."""
    return {"index": 1, "kind": "withdrawal", "times_s": [PULSE], "fraction": fraction,
            "buffer": pool_of(d, **counts)}  # fmt: skip


def transfer_of(d, **counts):
    """A serial transfer at the pulse's time, keeping one assembly, with this fresh pool."""
    return {"index": 2, "kind": "transfer", "times_s": [PULSE], "K_keep": 1,
            "fresh_pool": pool_of(d, **counts)}  # fmt: skip


SOURCES = ("a held tracer the sites bind", "a tracer made from a held source",
           "a withdrawal with a held tracer the sites bind")  # fmt: skip


def held_source(case):
    """D263's escapes from Q3, on FR-21's acceptance world: the tracer X held in the pool, which no
    membrane or lumen place declares but the sites bind (the reviewer's case); or X finite but made
    in the pool from a held source Z. Either stays an unlimited source of X through the wash."""
    d = site_wash_spec().to_dict()
    w = d["model"]["world"]
    pool = w["phases"]["pool"]["species"]
    if case == "a tracer made from a held source":
        w["species"].append(species("Z", {"x": 1}, solution=-1.0))
        pool.append({"id": "Z", "kind": "held", "held_mM": 50.0})
        w["steps"].append(step("make_X", {"Z": 1}, {"X": 1}, 1.0, phase="pool"))
    else:  # X held; the sites bind it
        x = next(e for e in pool if e["id"] == "X")
        x["kind"], x["held_mM"] = "held", 133.0
        del w["founder"]["X@pool"]
    d["experiment"]["schedules"][0]["pool"] = pool_of(d, L=30, S=6)
    if case == "a withdrawal with a held tracer the sites bind":  # FR-35's own escape (D263)
        half = {"index": 1, "kind": "withdrawal", "times_s": [T_WASH], "fraction": 0.5,
                "buffer": pool_of(d, L=15, S=3)}  # fmt: skip
        d["experiment"]["schedules"] = [half]
    return d


REFUSALS = {
    "a held tracer the sites bind": "the held X@pool stays an unlimited source",
    "a withdrawal with a held tracer the sites bind": "a withdrawal washes the pool's finite",
    "a tracer made from a held source": "the held Z@pool stays an unlimited source",
    "no population": "needs a population",
    "an omitted species": "one count per finite pool place",
    "solutes above c_ext": "exceed c_ext",
    "a held species the vesicles take up": "could never be washed out",
    "a shared time": "shares the time",
    "a shear at its time": "shares the time",
    "a transfer at its time": "shares the time",
    "a fresh count above the capacity": "fresh L@pool is 33, above molecule_capacity 32",
    "a transfer's fresh count above the capacity": "fresh L@pool is 33, above molecule_capacity 32",
    # FR-35 (D261)
    "a fraction on a replacement": "a partial exchange is a withdrawal",
    "a withdrawal of the whole pool": "fraction is in \\(0, 1\\)",
    "a withdrawal of nothing": "fraction is in \\(0, 1\\)",
    "a withdrawal buffer of the wrong length": "one count per finite pool place",
    "a withdrawal buffer above c_ext": "above c_ext",
    "a withdrawal buffer above the capacity": "fresh L@pool is 33, above molecule_capacity 32",
    "a withdrawal at a replacement's time": "shares the time",
    "a withdrawal of a held species the vesicles take up": "washed out only in part",
    "a withdrawal without a population": "needs a population",
}


@pytest.mark.parametrize("case", sorted(REFUSALS))
def test_every_refusal_of_a_replacement(case):
    with pytest.raises(ConfigError, match=REFUSALS[case]):
        parse_spec(refusal(case))


def test_a_fresh_count_at_the_capacity_is_admitted_and_one_above_misses_by_its_log():
    """The Lean finding of 20 November (lean/checks/pool_replacement.py --case capacity, on the Lean
    lane's branch at aae1d978): a fresh count above molecule_capacity read the log-factorial table's
    clamped last entry, and the run's ledger, reading the same table, closed. Now 33 at capacity 32
    is refused at parse for both schedules (REFUSALS) and 32 at 32 is admitted. Planted: the
    unguarded lookup's F of a pool holding 33 at capacity 32 misses the exact F by exactly ln 33,
    which the run's own F (ledger.state_free_energy) refuses. Host arithmetic."""
    d = raw_world()
    d["execution"]["molecule_capacity"] = 32
    at_capacity = {"index": 1, "kind": "replacement", "times_s": [PULSE], "pool": pool_of(d, L=32)}
    for schedule in (at_capacity, transfer_of(d, L=32)):
        d["experiment"]["schedules"] = [schedule]
        parse_spec(copy.deepcopy(d))  # equality is valid
    exact_d = copy.deepcopy(d)
    exact_d["execution"]["molecule_capacity"] = 64
    spec, exact = parse_spec(d), parse_spec(exact_d)
    state = model.founder(spec)
    state[[p.name for p in spec.model.world.places].index("L@pool")] = 33
    world = spec.model.world
    clamped = ledger.free_energy(state, model.tables(spec), world.terms, model.layout(spec).terms)
    right = ledger.free_energy(state, model.tables(exact), world.terms, model.layout(exact).terms)
    assert right - clamped == pytest.approx(math.log(33), abs=1e-12)
    with pytest.raises(ConfigError, match="above the molecule capacity 32"):
        ledger.state_free_energy(state, model.tables(spec), world.terms, model.layout(spec).terms)


def test_a_cut_around_each_replacement_resumes_bitwise(tmp_path, monkeypatch):
    """FR-22's qualification around a wash (the lead's ruling of 20 November): a run cut at the last
    event before each replacement, or at the first after it, and resumed from its checkpoint on
    disk reproduces the uninterrupted run bit for bit: every row (the counts, the ledger's heat,
    work, F and residual, each schedule's column), the trace, the diagnostics, the lives and the
    replacement records. A cut cannot fall at the replacement itself, since cuts are at events and
    a replacement lies between two. Planted: a resumed run that redoes the wash (its checkpoint's
    applied stops one short, after the wash) or skips it (one over, before it) is caught."""
    cut_around_each_stop("replacement", tmp_path, monkeypatch)


def cut_around_each_stop(kind, tmp_path, monkeypatch, plants=True):
    """The cut test's body for a stop kind (replacement or withdrawal): a cut at the last event
    before each stop and at the first after it, resumed bitwise; with `plants`, a redone and a
    skipped stop caught."""
    spec, a, at = world(kind)
    field = STOPS[kind][1]
    assert parse_spec(spec.to_dict()).fingerprint == spec.fingerprint  # the round trip
    for _, _, n in at:
        for k in (n, n + 1):  # the last event before it, the first after it
            b1 = stopped(k, kind)
            path = checkpoints.write(tmp_path / f"{kind}{k}", b1.checkpoint())
            b2 = runner.run(spec, start=checkpoints.read(path)).check()
            assert differences(a, b1, b2, k) == []
            done = b2.population["numbering"][field]
            assert a.population[field][done:] == b2.population[field]
    if not plants:
        return
    real, (_, _, n) = checkpoints.admit, at[-1]  # the last stop
    for k, shift in ((n + 1, -1), (n, 1)):  # redone after a cut past it; skipped before it

        def shifted(spec_, checkpoint, shift=shift):
            record, lane, host = real(spec_, checkpoint)
            doc = dict(host["doc"], applied_stops=host["doc"]["applied_stops"] + shift)
            return record, lane, dict(host, doc=doc)

        monkeypatch.setattr(checkpoints, "admit", shifted)
        b1 = stopped(k, kind)
        assert differences(a, b1, runner.run(spec, start=b1.checkpoint()), k) != []
        monkeypatch.undo()


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
    """FR-21's acceptance (module docstring). The release after the wash is certain, since binding
    cannot fire without a free X. The rebinding that follows is seed-specific: the binding's
    constants make it about 0.996 likely before a second release, and this seed's trace shows it."""
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


# ------------------------------------------------------------------ FR-35: a partial withdrawal

N_STREAMS = 4000  # host draws at real run addresses: the tier test (D261 item 6)


def acceptance_spec(fraction, *, seed=1):
    """FR-35's acceptance world: site_wash_spec() with its wash a withdrawal of `fraction` (8 free
    X, 4 vacant and 2 occupied sites), the buffer tracer-free: no X, the medium's L and S in the
    withdrawn volume, floored to a count (7 and 1 at a quarter; the note's B1)."""
    d = site_wash_spec().to_dict()
    d["experiment"]["schedules"] = [
        {"index": 1, "kind": "withdrawal", "times_s": [T_WASH], "fraction": fraction,
         "buffer": pool_of(d, L=int(30 * fraction), S=int(6 * fraction))}
    ]  # fmt: skip
    d["execution"]["stream"]["seed"] = seed
    return parse_spec(d)


def pool_f_of(spec):
    """F of a pool vector at the pool's volume, through the run's guarded table read."""
    world, layout = spec.model.world, model.layout(spec)
    tables = model.tables(spec)
    return lambda c: ledger.state_free_energy(np.asarray(c), tables, world.terms, layout.terms)


def reference(spec, record):
    """§4's independent reference: exact log-factorials (lgamma), never the engine's table."""
    world, f = spec.model.world, record["fraction"]
    X = 6.02214076e23 * world.volume("pool") * world.units.standard_concentration_mM * 1e-3
    mu = {s.id: s.mu_solution for s in world.species}
    species = {p.name: p.species for p in world.places}

    def F(counts, ln_g):
        return sum(c * (mu[species[p]] - math.log(X) - ln_g) + math.lgamma(c + 1)
                   for p, c in counts.items() if c)  # fmt: skip

    before, k, kept, b = (record[x] for x in ("before", "withdrawn", "remaining", "supplied"))
    after = {p: kept[p] + b[p] for p in kept}
    ln_f, ln_rest = math.log(f), math.log1p(-f)
    ln_p = sum(math.lgamma(before[p] + 1) - math.lgamma(k[p] + 1) - math.lgamma(kept[p] + 1)
               + k[p] * ln_f + kept[p] * ln_rest for p in before)  # fmt: skip
    return {"pool_loss_kT": F(before, 0.0) - F(kept, ln_rest), "sample_F_kT": F(k, ln_f),
            "split_surprisal_kT": -ln_p, "buffer_F_kT": F(b, ln_f),
            "mixing_heat_kT": F(kept, ln_rest) + F(b, ln_f) - F(after, 0.0)}  # fmt: skip


def test_a_withdrawal_keeps_every_slot_draws_each_molecule_and_closes_its_books():
    """FR-35 (D261), two engine runs of the acceptance world (f = 1/2 and 1/4, one stream each):
    the recorded withdrawn counts are the operator's draw at the run's own address, bit for bit;
    collected plus remaining is the recorded pre-wash count in every place; the particle's sites
    and key are as they were; the record's energies are §4's independent reference (exact
    log-factorials) to 1e-10 kT, the heat is not negative, and the books close (check())."""
    for fraction in (0.5, 0.25):
        spec = acceptance_spec(fraction)
        run = runner.run(spec).check()
        (record,) = run.population["withdrawals"]
        world, (schedule,) = spec.model.world, spec.experiment.schedules
        before = model.founder(spec)
        names = [p.name for p in world.places]
        for name, count in record["before"].items():
            before[names.index(name)] = count
        taken, _ = withdrawal.draw(model.layout(spec).base_key, world, schedule, 0, before)
        assert record["withdrawn"] == withdrawal.by_place(world, taken)
        for p, n in record["before"].items():
            assert record["withdrawn"][p] + record["remaining"][p] == n
        assert record["supplied"]["X@pool"] == 0  # tracer-free
        rows = run.rows
        i = int(np.flatnonzero(rows["row_kind"] == population.WITHDRAWAL)[0])
        assert rows["row_event"][i - 1] == rows["row_event"][i]  # no event between them
        for field in ("slot_count", "slot_key"):
            np.testing.assert_array_equal(rows[field][i], rows[field][i - 1])
        for name, value in reference(spec, record).items():
            assert record[name] == pytest.approx(value, abs=1e-10), name
        assert record["mixing_heat_kT"] >= 0.0
        assert record["pool_loss_kT"] == pytest.approx(
            record["sample_F_kT"] - record["split_surprisal_kT"], abs=1e-10
        )  # the sink is not the sample's own F: they differ by the surprisal


def test_a_withdrawal_books_its_mixing_heat_never_negative_and_its_limits_are_exact():
    """FR-35's booking (D261 item 4), through the operator's booking on the guarded table read:
    the heat is not negative and the books' identity holds in random realizations whose buffer
    carries the species; at f = 1 the bookings are cells.pool_replacement@1's, with zero heat; the
    mean heat over k ~ Bin(n, f) is FR-27's continuum heat exactly for a tracer-free buffer, and
    exceeds it with a buffer at the pool's own concentration by less than the mixture's binomial
    entropy (the discrete surprisal of which side each molecule came from). Host arithmetic."""
    spec = acceptance_spec(0.5)
    world, pool_f = spec.model.world, pool_f_of(spec)

    def vector(**counts):  # a pool vector, padded to the places' capacity, with these counts
        out = np.zeros(spec.execution.place_capacity, dtype=np.int64)
        for i, p in enumerate(world.places):
            if p.phase == "pool" and not p.held:
                out[i] = counts.get(p.species, 0)
        return out

    rng = np.random.default_rng(35)
    for _ in range(40):
        f = float(rng.uniform(0.05, 0.95))
        n = vector(L=int(rng.integers(0, 40)), S=int(rng.integers(0, 20)),
                   X=int(rng.integers(0, 30)))  # fmt: skip
        k = np.asarray([int(rng.integers(0, c + 1)) for c in n])
        b = vector(L=int(rng.integers(0, 30)), S=int(rng.integers(1, 20)),
                   X=int(rng.integers(1, 30)))  # fmt: skip
        e = withdrawal.booking(pool_f, n, k, b, f, world)
        assert e["mixing_heat_kT"] >= -1e-12
        change = pool_f(n - k + b) - pool_f(n)
        assert change == pytest.approx(e["buffer_F_kT"] - e["pool_loss_kT"] - e["mixing_heat_kT"],
                                       abs=1e-9)  # fmt: skip
    n, b = vector(L=30, S=6, X=8), vector(L=12, S=3)
    whole = withdrawal.booking(pool_f, n, n, b, 1.0, world)  # f = 1: @1's whole exchange
    zero = pool_f(np.zeros_like(n))
    assert whole["pool_loss_kT"] == pytest.approx(pool_f(n) - zero, abs=1e-12)  # @1's sink
    assert whole["buffer_F_kT"] == pytest.approx(pool_f(b) - zero, abs=1e-12)  # @1's work
    assert whole["mixing_heat_kT"] == pytest.approx(0.0, abs=1e-12)
    assert whole["split_surprisal_kT"] == pytest.approx(0.0, abs=1e-12)

    def mean_heat(count, f, buffer):
        out = 0.0
        for k in range(count + 1):
            p = math.comb(count, k) * f**k * (1 - f) ** (count - k)
            taken = vector(X=k)
            e = withdrawal.booking(pool_f, vector(X=count), taken, vector(X=buffer), f, world)
            out += p * e["mixing_heat_kT"]
        return out

    for count, f in ((8, 0.5), (8, 0.25), (100, 0.25)):  # tracer-free: FR-27's -(1-f) n ln(1-f)
        assert mean_heat(count, f, 0) == pytest.approx(-(1 - f) * count * math.log1p(-f), 1e-12)
    count, f, buffer = 100, 0.25, 25  # the buffer at the pool's concentration: continuum heat 0
    m = round((1 - f) * count) + buffer
    entropy = -sum(q * math.log(q) for q in (math.comb(m, j) * f**j * (1 - f) ** (m - j)
                                             for j in range(m + 1)) if q > 0)  # fmt: skip
    assert 0.0 < mean_heat(count, f, buffer) < entropy


@functools.lru_cache(maxsize=None)
def _blocks_program(index, size):
    import jax

    def one(base, number):
        key = streams.stream_key_data(base, index, "schedule")
        return streams.uniforms(key, number, size)

    return jax.jit(jax.vmap(one, in_axes=(0, None)))


def blocks(base_keys, index, number, n):
    """[K, n]: the withdrawal's block of n uniforms at draw number `number` of schedule `index`'s
    stream, for K base keys in one compiled call: withdrawal.draw's arithmetic (streams.block's
    power-of-two prefix of streams.uniforms on the schedule's key) under jax.vmap, compiled once
    per block size."""
    import jax.numpy as jnp

    size = 1 << max(n - 1, 0).bit_length()
    out = _blocks_program(index, size)(jnp.asarray(base_keys), jnp.int64(number))
    return np.asarray(out)[:, :n]


def base_keys(seeds, environment, lineage, branch):
    """[K, 2]: streams.base_key_data for many seeds in one compiled call (its key, then its three
    fold-ins), equal to it bit for bit (a row checks it)."""
    import jax
    import jax.numpy as jnp

    def one(seed):
        key = jax.random.key(seed, impl=streams.GENERATOR)
        for value in (environment, lineage, branch):
            key = jax.random.fold_in(key, jnp.uint32(value))
        return jax.random.key_data(key)

    return np.asarray(jax.jit(jax.vmap(one))(jnp.asarray(seeds, dtype=jnp.uint32)), np.uint32)


def test_a_withdrawal_draws_binomially_independently_and_on_its_own_addresses():
    """FR-35's statistics (D261 item 6), at real run addresses: N_STREAMS streams (seeds 0 to N - 1
    of the acceptance world), 8 free X, drawn in one batched call per address. The batched draws
    equal the operator's per-call draws (withdrawal.draw and streams.block) bit for bit on a sample
    of 40 addresses, and so do the batched base keys (streams.base_key_data).
    - f = 1/2: the collected mean in 4 +- 0.1 (4.47 SD), the variance in 2 +- 0.2 (4.8 SD), and a
      chi-squared over the nine outcomes below 31.8 (alpha 1e-4, 8 df). f = 1/4: the collected mean
      in 2 +- 0.1 and its variance in 1.5 +- 0.2; the remaining count's mean, 6, would not pass.
      The rates are a prior over the seed choice, fixed once chosen.
    - Independent: two places of equal count (X and L, 8 each) and two consecutive washes of one
      place are uncorrelated, |r| < 4 / sqrt(N).
    - Disjoint: a transfer's and a Poisson shear's streams (their own indices) are other keys.
    Planted, each caught: one uniform shared by a place's molecules (mean 4, variance 16), and
    blocks overlapping by an offset (X reading L's block from X's ordinal). Host arithmetic."""
    spec = acceptance_spec(0.5)
    world, x = spec.model.world, spec.execution
    names = [p.name for p in world.places]
    schedule = spec.experiment.schedules[0]
    keys = base_keys(np.arange(N_STREAMS), x.environment, x.lineage, x.branch)
    finite = withdrawal.finite_places(world)
    places = len(finite)
    jx, jl = finite.index(names.index("X@pool")), finite.index(names.index("L@pool"))
    ux = blocks(keys, schedule.index, jx, 8)  # wash 0: draw number 0 * places + j
    ul = blocks(keys, schedule.index, jl, 8)
    ux1 = blocks(keys, schedule.index, places + jx, 8)  # wash 1
    pool = np.zeros(len(names), dtype=np.int64)
    pool[[names.index("X@pool"), names.index("L@pool")]] = 8
    for seed in range(0, N_STREAMS, N_STREAMS // 40):  # the batched draws are the operator's
        exact = streams.base_key_data(seed, x.environment, x.lineage, x.branch)
        np.testing.assert_array_equal(exact, keys[seed])
        key = streams.stream_key_data(keys[seed], schedule.index, "schedule")
        np.testing.assert_array_equal(np.asarray(streams.block(key, jx, 8)), ux[seed])
        taken, _ = withdrawal.draw(keys[seed], world, schedule, 0, pool)
        assert taken[names.index("X@pool")] == np.count_nonzero(ux[seed] < 0.5)
        assert taken[names.index("L@pool")] == np.count_nonzero(ul[seed] < 0.5)

    def bands(k, mean, var):
        return abs(k.mean() - mean) < 0.1 and abs(k.var(ddof=1) - var) < 0.2

    kx, kl = (ux < 0.5).sum(axis=1), (ul < 0.5).sum(axis=1)
    assert bands(kx, 4.0, 2.0)
    expected = np.asarray([math.comb(8, j) for j in range(9)]) * N_STREAMS / 256.0
    chi2 = float(np.sum((np.bincount(kx, minlength=9) - expected) ** 2 / expected))
    assert chi2 < 31.8
    r = 4.0 / math.sqrt(N_STREAMS)
    assert abs(np.corrcoef(kx, kl)[0, 1]) < r  # two places of equal count
    assert abs(np.corrcoef(kx, (ux1 < 0.5).sum(axis=1))[0, 1]) < r  # consecutive washes
    qx = (ux < 0.25).sum(axis=1)
    assert bands(qx, 2.0, 1.5) and not bands(8 - qx, 2.0, 1.5)  # the collected count, not the rest
    others = {i: np.asarray(streams.stream_key_data(keys[0], i, "schedule")) for i in (1, 2, 3)}
    assert len({tuple(v.tolist()) for v in others.values()}) == 3  # withdrawal, transfer, shear
    shared = 8 * (ux[:, 0] < 0.5)  # planted: one uniform for all of a place's molecules
    assert not bands(shared, 4.0, 2.0)
    long = blocks(keys, schedule.index, jl, 8 + jx)  # planted: X reads L's block from its ordinal
    ox = (long[:, jx:] < 0.5).sum(axis=1)
    assert abs(np.corrcoef(ox, (long[:, :8] < 0.5).sum(axis=1))[0, 1]) > r


def test_a_cut_around_each_withdrawal_resumes_bitwise(tmp_path, monkeypatch):
    """FR-22 around FR-35's withdrawal: the cut test's body (cuts at the last event before each
    wash and the first after it, resumed bitwise) on a world of two washes on one schedule, on the
    replacement world's compiled program. Planted: the schedule's draw counter, which a resumed run
    derives from the applied stops, left at 0 after a cut between the washes, so the second wash
    redraws the first's addresses: caught. (The redone and skipped stops' plants are the
    replacement's cut test's, on the same applied-stops record.)"""
    cut_around_each_stop("withdrawal", tmp_path, monkeypatch, plants=False)
    spec, a, at = world("withdrawal")
    k = at[0][2] + 1  # the first event after the first wash, before the second
    monkeypatch.setattr(population, "_count_washes", lambda *args: None)
    b1 = stopped(k, "withdrawal")
    b2 = runner.run(spec, start=b1.checkpoint()).check()
    assert differences(a, b1, b2, k) != [] or (
        a.population["withdrawals"][1:] != b2.population["withdrawals"]
    )


def test_one_run_s_edited_check_never_reaches_a_later_run(tmp_path):
    """D263 (shared state): every check a run exports is its own copy. Editing one run's verdict and
    world check leaves a later, independent run's checks, and its saved run.json, unchanged (the
    verdicts were cached objects handed out by reference). Two short runs (stop=1) of FR-21's
    acceptance world, on its compiled program."""
    import json

    from cells.models.assembly_lineages_v2 import records

    spec = site_wash_spec()
    a = runner.run(spec, stop=1)
    clean = copy.deepcopy((a.verdict, a.world_report))
    a.verdict["probe"]["max_abs_deviation_ln"] = 99.0
    a.verdict["holds"] = False
    a.world_report["max_abs_deviation_ln"] = 77.0
    b = runner.run(spec, stop=1)
    assert (b.verdict, b.world_report) == clean
    records.write_run(tmp_path / "b", b)
    saved = json.loads((tmp_path / "b" / "run.json").read_text())["check"]
    assert saved == {"probe": clean[0], "world": clean[1]}


# ------------------------------------------------------------------ FR-47: a shell's washes


def test_a_shell_population_washes_in_exact_events_and_its_pool_refills():
    """FR-47 (D323), the exact half's new path: a one-slot prescribed shell in a finite pool (the
    (d) rows' made-up shape, 400 tracers) through a withdrawal at f = 1/2, a tracer-free full wash
    and a withdrawal at f = 1/4. The books close; each wash's record holds the tracer's place; a
    withdrawal books −k ln(1 − f), k the kept count; the full wash removes the whole pool; the pool
    refills from the lumen before the last withdrawal; and the tracer balances exactly, present
    plus every removed count equal to the founder's. One population program (K = 1) and one run,
    with the (d) rows' module imported for the world: 17 s cold (the file's row, 58.9 to 75.9 s)."""
    from tests.unit.test_assembly_lineages_v2_rate_equations_population import (
        STOPS,
        TIMES,
        shell_definition,
        shell_world,
    )

    spec = parse_spec(shell_definition(shell_world(tracer=400, wall=20), stops=STOPS,
                                       times=TIMES, horizon=4.0, representation=False))  # fmt: skip
    run = runner.run(spec).check()
    assert run.status == "complete"
    first, last = run.population["withdrawals"]
    (full,) = run.population["replacements"]
    for record, fraction in ((first, 0.5), (last, 0.25)):
        kept = record["remaining"]["S@pool"]
        assert record["withdrawn"]["S@pool"] + kept == record["before"]["S@pool"]
        assert record["mixing_heat_kT"] == pytest.approx(-kept * math.log1p(-fraction),
                                                         rel=1e-14, abs=0)  # fmt: skip
    assert full["supplied"]["S@pool"] == 0 and full["removed"]["S@pool"] > 0
    assert last["before"]["S@pool"] > 0  # refilled from the lumen after the full wash
    names = [p.name for p in spec.model.world.places]
    present = (run.rows["pool_count"][-1][names.index("S@pool")]
               + run.rows["slot_count"][-1][0][names.index("S@lumen")])  # fmt: skip
    removed = (first["withdrawn"]["S@pool"] + full["removed"]["S@pool"]
               + last["withdrawn"]["S@pool"])  # fmt: skip
    assert int(present) + removed == 400
