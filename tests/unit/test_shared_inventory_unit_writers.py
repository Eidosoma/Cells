"""FR-43 part 2A (D315): the gene unit beside the unit producer on one row, one adding a neutral
stock and the other consuming it (a user's review, 23 November 2026).

validation/tissue/shared_inventory_fixtures.unit_pair: the gene unit's ribosome-limited world
(translation makes the neutral protein P) beside cells.operator.population_unit_turnover@1, which consumes P as its
precursor into a population's units. The two-writer rule of 19 November 2026, extended: P's
registry potential is the shared row's one authority, each writer keeps its own books, and labelled
and exported rows keep one writer.
- The definition, both ways: the pair is admitted; refused without P's registry potential (the
  shared-row rule), on a precursor the gene unit makes only by degradation (A: no static bound on
  its supply), and with a D152 route on P beside the producer (D152's one local writer).
- R5: supply_bound holds the gene unit's largest production of P (kappa_tl M_rib), a rate, and
  check_spec_for's largest units take it times the horizon exactly once.
- The run, every host check on every row: P's amount at every saved row is its start plus the gene
  unit's books less the producer's consumption, to rounding; both writers move P.
- Restart: resumed from a mid-run checkpoint, in process and through a written snapshot, the run is
  bit for bit the unbroken one, books included.
- Restart at the switch-off (D349): the pair with both sources switched off at one instant by their
  declared schedules, cut at that row, one step after it and one step before it. Resumed, every
  state array, ledger and observation is the unbroken run's, bit for bit; a redo and a skip of each
  source's switch, planted in the schedule the resumed run reads, are caught.
Its reason and cost: one compiled world of the composition FR-43 admits, resumed twice (seconds
as the tier tool measures). The switch-off's rows compile nothing: a schedule is data, and their
runs have the two programs' 40 and 20 steps.
"""

import itertools
import math
import tempfile
from dataclasses import replace
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.runner import run
from cells.execution.schedule import event_index
from cells.operators import population_unit_turnover as put
from cells.operators import templated_polymerisation as tp
from cells.records.io import load_snapshot, write_snapshot
from cells.registry.models import get_model
from validation.gene_regulation import worlds as gw
from validation.tissue import shared_inventory_fixtures as sif
from validation.tissue import species_reactions_fixtures as rfx

END = 20.0  # 40 steps of 0.5 s.


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def producer(raw):
    return next(o for o in raw["model"]["operators"] if o["law"] == sif.UNIT_PRODUCER)


# ------------------------------------------------------------------ the definition, both ways


def test_the_pair_is_admitted():
    spec = parse_spec(sif.unit_pair(end=END))
    assert [d.law for d in spec.model.operators] == [
        gw.POLYMERISATION,
        sif.STATE,
        sif.UNIT_PRODUCER,
    ]


def test_a_shared_precursor_needs_its_registry_potential():
    raw = sif.unit_pair(end=END)
    next(s for s in raw["model"]["species"] if s["id"] == "P").pop("standard_mu_RT")
    with pytest.raises(ConfigError, match="needs its standard potential in the species registry"):
        parse_spec(raw)


def test_a_precursor_made_without_a_static_bound_is_refused():
    """A is made by P's degradation (its monomers), whose rate has no static bound for R5."""
    raw = sif.unit_pair(end=END)
    producer(raw)["species"] = [dict(id="A", catalogue=None, evidence=None)]
    producer(raw)["routes"][0]["precursor"] = "A"
    with pytest.raises(ConfigError, match="made at a rate with no static bound"):
        parse_spec(raw)


def test_a_d152_route_on_the_precursor_beside_the_producer_stays_refused():
    raw = sif.unit_pair(end=END)
    m = raw["model"]
    entry = next(s for s in m["species"] if s["id"] == "P")
    mu = entry["standard_mu_RT"] + math.log(sif.C0_mM / m["standard_concentration_mM"])
    raw = rfx.with_reactions(
        raw,
        [rfx.species("P", moieties={"p": 1}, mu=mu)],
        [rfx.mass_action("spend_P", {"cells": [gw.CELL]}, {"P": 1}, {}, 1e-6)],
        rfx.always(["spend_P"]),
        c0=sif.C0_mM,
    )
    with pytest.raises(ConfigError, match="reaction writes the precursor 'P'"):
        parse_spec(raw)


# ------------------------------------------------------------------ R5


def test_r5_takes_the_gene_units_supply_times_the_horizon_once(monkeypatch):
    spec = parse_spec(sif.unit_pair(end=END))
    (block,) = [d for op, d, _ in tp.composite_spec.entries(spec) if op.LAW_ID == gw.POLYMERISATION]
    (chain,) = block.chains
    (pool,) = block.pools
    rate = chain.speed_per_s * chain.stages / chain.residues * pool.machines * tp.COPY_FMOL
    assert put.supply_bound(spec)[("P", gw.CELL)] == rate  # A rate, fmol/s.
    model = get_model(spec.model)
    (declaration,) = [d for op, d, _ in put.composite_spec.entries(spec) if op.LAW_ID == put.LAW_ID]

    def largest_units(bound):
        monkeypatch.setattr(put, "supply_bound", lambda spec: bound)
        check = put.check_spec_for(spec, spec, declaration)
        (channel,) = check.model.channels
        return channel.abundance

    area = spec.model.membranes[0].area_m2
    added = (largest_units({("P", gw.CELL): rate}) - largest_units({})) * area * sif.DENSITY
    (route,) = declaration.routes
    expected = put.conversion(route) * rate * spec.experiment.end_time
    assert added == pytest.approx(expected, rel=1e-12)
    assert model is not None


# ------------------------------------------------------------------ the run and its restart


def books(spec, history):
    """(P's amount, the gene unit's net books of P, the producer's consumption of P), [T] fmol."""
    _, p = get_model(spec.model).initial_values(spec)
    row = list(spec.model.species_ids).index("P")
    n = np.asarray(p.amount_reference)[row, 0] + np.asarray(history.amount_increment)[:, row, 0]
    gene = (
        np.asarray(history.poly_produced_fmol)[:, row, 0]
        - np.asarray(history.poly_consumed_fmol)[:, row, 0]
    )
    consumed = np.asarray(history.unit_consumed_fmol).sum(axis=1)  # One route, on P.
    return n, gene, consumed


def test_the_shared_stock_closes_per_writer_and_restarts_bitwise():
    spec = parse_spec(sif.unit_pair(end=END))
    result = run(spec)  # Every host check on every accepted row.
    n, gene, consumed = books(spec, result.history)
    assert float(np.max(gene)) > 0 and float(np.max(consumed)) > 0  # Both writers move P.
    scale = float(np.max(np.abs(n)) + np.max(np.abs(gene)) + np.max(np.abs(consumed)))
    tolerance = 64 * np.finfo(float).eps * len(n) * scale
    assert float(np.max(np.abs((n - n[0]) - (gene - consumed)))) <= tolerance
    checkpoint = result.checkpoint_at(float(result.times[len(result.times) // 2]))
    resumed = run(spec, checkpoint)
    with tempfile.TemporaryDirectory() as tmp:
        write_snapshot(Path(tmp) / "checkpoint", result.spec, checkpoint)
        loaded = load_snapshot(Path(tmp) / "checkpoint")
        again = run(loaded.spec, loaded.checkpoint)
    for rerun in (resumed, again):
        for x, y in zip(rerun.history, result.history, strict=True):
            tail = np.asarray(y)[checkpoint.step_index :]
            assert np.asarray(x).tobytes() == tail.tobytes()


# ------------------------------------------------------------------ a restart at the switch-off

DT = 0.5  # s: the pair's step.
CUT = END / 2  # s: row 20, where the restart above cuts too, so its 40- and 20-step programs serve.
SOURCES = {  # The fixture's keyword for each source's switch, and the source's own count.
    "gene_off": "poly_initiated_fmol",  # The gene unit's: chains of P initiated by tl.
    "assembly_off": "unit_assembled_units",  # The unit producer's: units assembled by its route.
}


def switched(**times):
    """The pair, its sources switched at these times, observed every 2.5 s, the cut among them."""
    return parse_spec(sif.unit_pair(end=END, every=2.5, **times))


def reported(result, start):
    """{name: its rows} of everything a run reports from accepted step `start` on: the times, every
    state array (each writer's books among them), every ledger's residual, every observation."""
    model, first = get_model(result.spec.model), start - result.start_step
    rows = type(result.history)(*(np.asarray(v)[first:] for v in result.history))
    _, p = model.initial_values(result.spec)
    ledgers = [model.balances(type(rows)(*(v[i] for v in rows)), p) for i in range(len(rows[0]))]
    seen = result.observations.times >= result.times[first]
    return (
        {"times": result.times[first:], **rows._asdict()}
        | {f"ledger {k}": np.stack([row[k] for row in ledgers]) for k in ledgers[0]}
        | {f"observed {k}": v[seen] for k, v in vars(result.observations).items()}
    )


def differing(a, b):
    """{name: the first of its rows that two runs' reports do not share bit for bit}."""
    assert a.keys() == b.keys()
    out = {}
    for name in a:
        pairs = enumerate(zip(a[name], b[name], strict=True))
        row = next((i for i, (x, y) in pairs if x.tobytes() != y.tobytes()), None)
        if row is not None:
            out[name] = row
    return out


@pytest.mark.parametrize(
    ("after", "plants"),
    ((0, ("redo", "skip")), (1, ("redo",)), (-1, ())),
    ids=("at the switch", "one step after it", "one step before it"),
)
def test_a_restart_at_the_sources_switch_off_is_bitwise_and_a_redo_or_skip_is_caught(
    after, plants, tmp_path
):
    """D349: the run cut `after` steps from the row of both sources' switch-off, and resumed.

    The switch acts in the step that leaves its row, for both sources: each still makes in the step
    that ends there, and nothing after it. So a cut at the switch holds the state the switch acts
    on, and the resumed run's first step applies it, though the checkpoint's event position counts
    it already. The chains of P in production go on to their release.

    The plants (FR-44's method). A schedule sets a level: the checkpoint holds no count of its
    switches to shift, a shifted event position is refused, and a rate of 0 set to 0 again changes
    nothing. So each is planted, one source at a time, in what the resumed run reads, its
    definition's schedule. Each completes, and the comparison catches it at the end of its first
    wrong step, where the source has made more than the unbroken run's:
    - redo: on again for the step after the switch's own, then switched off a second time;
    - skip: never switched off."""
    off = CUT - after * DT
    switch = dict.fromkeys(SOURCES, (off,))
    spec = switched(**switch)
    full = run(spec)
    k = int(np.flatnonzero(full.times == off)[0])
    for count in SOURCES.values():
        made = np.asarray(getattr(full.history, count))
        assert np.all(made[k] > made[k - 1]) and np.all(made[k:] == made[k]), count
    released = np.asarray(full.history.poly_released_fmol)
    assert np.all(released[-1] > released[k])
    checkpoint = full.checkpoint_at(CUT)
    assert checkpoint.event_index == int(after >= 0)
    start = checkpoint.step_index
    whole = reported(full, start)
    assert differing(reported(run(spec, checkpoint), start), whole) == {}
    if after == 0:  # The cut at the switch, through a written snapshot too.
        write_snapshot(tmp_path / "checkpoint", spec, checkpoint)
        loaded = load_snapshot(tmp_path / "checkpoint")
        assert differing(reported(run(loaded.spec, loaded.checkpoint), start), whole) == {}
    changes = {"redo": (off, off + DT, off + 2 * DT), "skip": ()}
    wrong = {"redo": off + DT, "skip": off}  # The first step a plant takes wrong, by its start.
    for (source, count), plant in itertools.product(SOURCES.items(), plants):
        read = switched(**(switch | {source: changes[plant]}))
        planted = run(read, replace(checkpoint, event_index=event_index(read, CUT)))
        rows = differing(reported(planted, start), whole)
        assert count in rows, (source, plant)
        row = rows[count]
        assert full.times[start + row] == wrong[plant] + DT, (source, plant)
        made, unbroken = (getattr(r.history, count) for r in (planted, full))
        assert np.all(made[row] > unbroken[start + row]), (source, plant)
