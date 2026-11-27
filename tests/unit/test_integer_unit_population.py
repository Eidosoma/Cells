"""cells.operator.integer_unit_population@1 (FR-43 part 3, option B; D315): the law's pieces, its refusals and
the division hook's declarations on the host, then one compiled world (W1 of the references' spec,
validation/fr43_part3/references/spec/part3.json):

* the streams reproduce the spec's draws table bit for bit (the written rule, its own generator);
* the series and the heat: q and x - log1p(x) against their sums; the heat equals -ΔF of @3's own
  per-row terms and is never negative;
* independent_segregation: exact integer sums, unit order, the probability's ends;
* the stages: rows met by two sites that can both be live split them, rows only read do not, and a
  parent and its daughters never meet;
* the refusals, one row each, and the hook's declarations (contract and composite);
* C3.1, C3.2: two free subunits form one active unit that moves S between the cell and its finite
  node, disassembly returns both, S + 2A = 2 on every row, the pools' total and every ledger hold;
* C3.4's premise: the first event at E0/a0 in closed form, each next threshold -ln u1 of the spec's
  table, and the channels alternating;
* C3.6: a same-seed restart cut between events is bitwise the uninterrupted run;
* the trace's counts are those the event loop carries (FR-43 part 3's co-writers registration):
  the declared jumps on every recorded event, and a planted wrong jump recorded as carried.

The compiled world runs once per module (about 30 s on one core, most of it the compile): the
restart and the closed forms need a run, and the run's rows serve every compiled check here.

FR-43 part 3's co-writers (docs/FR43_PART3_COWRITERS_DESIGN.md §5.2):
* the event-rate bound counts a co-writer's bounded production (a zero-order source refused at dt
  a0,max), and a producer with no static bound leaves the site unchecked (the lead's L3), where
  the same site alone is refused;
* a second compiled world, the operator beside D152's zero-order source of S in the cell
  (validation/fr43_part3/worlds.source_world, crossrev's and G1's co-writer world): the first event
  at its closed form with the source, far from the one without it; each writer's books of S at
  every row (the network's production, the transfer), a 1e-3 error in one of them caught; the
  integer ledger exact; a restart between events bitwise. Its reason: the event and restart claims
  need a run (about 35 s on one core, most of it the compile).

FR-52's passive cohorts, on the host (docs/PASSIVE_COHORT_DESIGN.md §3, §5; NumPy and parsing
only, about 3 s; the compiled world is tests/unit/test_integer_unit_cohorts.py): the frozen rows A
to D, F and G with their controls enumerated over labelled units (validation/fr52_cohorts/exact.py)
and their plants; the map's rule against brute-force counts of the legal tables; the update
against enumeration on explicit and random channels, a one-pair update failing it; the refusals;
the readout's integrity; the reference reader's integrity rows (the amendment's §9.2 and §9.8);
and the partition's finiteness check at a division beside a cohort (the lead's ruling on §9.5).
"""

import itertools
import json
import math
import random
from fractions import Fraction
from functools import partial
from pathlib import Path
from types import MappingProxyType
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.schedule import control_values
from cells.execution.windows import WindowPolicy, iter_windows
from cells.models import pump_composite
from cells.models import pump_composite_adapter as adapter
from cells.numerics import counter_streams as streams
from cells.numerics import unit_cohorts as uc
from cells.operators import OPERATORS
from cells.operators import integer_unit_population as iup
from cells.operators.contract import Operator, check_declarations
from cells.registry.models import get_model
from validation.fr43_part3 import worlds
from validation.fr52_cohorts import exact
from validation.fr52_cohorts import worlds as cohort_worlds

SPEC_DIR = Path(worlds.SPEC).parent
W1 = "W1_two_subunits_feedback"


def _draws():
    with (SPEC_DIR / "draws.json").open() as f:
        return json.load(f)["worlds"]


# ------------------------------------------------------------------ host pieces


@pytest.mark.parametrize("world", sorted(worlds.spec_worlds()))
def test_the_streams_reproduce_the_spec_draws(world):
    table = _draws()[world]
    words = streams.key_data(table["seed"], table["site_index"], "events")
    counters = jnp.asarray([0, 1, 37, 255])
    got = np.asarray(streams.site_uniforms(jnp.asarray([words] * 4), counters, 2))
    for row, k in zip(got, (0, 1, 37, 255), strict=True):
        assert float(row[0]).hex() == table["u1"][k] and float(row[1]).hex() == table["u2"][k]
    # The binding's vectorized derivation gives the same words for every site.
    many = streams.sites_key_data(table["seed"], table["site_index"] + 3, "events")
    assert (many[table["site_index"]] == words).all()


@pytest.mark.parametrize("x", [0.0, 1e-12, 1e-6, 0.03, 0.4, 0.999999, 1.0, 1.000001, 3.0, 40.0])
def test_q_is_its_series(x):
    terms = [(-1) ** (n + 1) * x**n / math.factorial(n + 1) for n in range(1, 90)]
    want = math.fsum(terms) if x < 5 else 1 - (1 - math.exp(-x)) / x
    got = float(iup.q_of(jnp.asarray(x)))
    assert abs(got - want) <= 2e-15 * max(want, 1e-300) + (0.0 if x else 0.0)


@pytest.mark.parametrize("x", [-0.9, -0.3, -0.2499, -1e-9, 0.0, 1e-9, 0.2499, 0.3, 4.0])
def test_phi_is_its_series(x):
    want = (
        math.fsum((-1) ** n * x**n / n for n in range(2, 400))
        if abs(x) < 0.5
        else x - math.log1p(x)
    )
    got = float(iup.phi_of(jnp.asarray(x)))
    assert got >= 0 and abs(got - want) <= 4e-15 * want


@pytest.mark.parametrize(
    "nc, no, vc, vo, lam, tau",
    [
        (2.0, 0.05, 1.0, 0.5, 1.2, 0.3),  # Down a steep gradient.
        (0.05, 2.0, 1.0, 0.5, 1.2, 0.3),  # Into the cell.
        (1.0, 0.5, 1.0, 0.5, 2.0, 5.0),  # Equal concentrations: nothing moves.
        (1.0 + 1e-9, 0.5, 1.0, 0.5, 0.7, 0.01),  # A gradient at 1e-9.
        (3.0, 1e-6, 0.2, 1.7, 40.0, 0.5),  # To equilibrium.
    ],
)
def test_the_heat_is_minus_the_free_energy_change(nc, no, vc, vo, lam, tau):
    u0 = nc / vc - no / vo
    moved = -u0 * math.expm1(-lam * tau) * vc * vo / (vc + vo)
    temperature = 310.0
    one = lambda v: jnp.asarray([[v]])  # noqa: E731
    heat, magnitude = iup._heat(
        one(nc), one(no), jnp.asarray([vc]), jnp.asarray([vo]), one(lam), one(u0), one(moved),
        jnp.asarray([tau]), temperature,
    )  # fmt: skip
    change = adapter.species_chemical_free_energy_pJ(
        nc, -moved, vc, temperature, xp=np
    ) + adapter.species_chemical_free_energy_pJ(no, moved, vo, temperature, xp=np)
    assert float(heat[0, 0]) >= 0.0
    assert abs(float(heat[0, 0]) + change) <= 8 * np.finfo(float).eps * float(magnitude[0, 0])


@pytest.mark.parametrize(
    "counts, f, uniform, first, volume",
    [
        ([0, 1], 0.5, [0.49, 0.9], [0, 1], 0.5),  # One active unit: below f, the first.
        ([0, 1], 0.5, [0.51, 0.1], [0, 0], 0.5),  # Above f: the second.
        ([2, 1], 0.5, [0.1, 0.9, 0.2, 0.0], [1, 1], 0.5),  # Free units first, then the active one.
        ([3, 0], 1e-300, [0.5, 0.5, 0.5], [0, 0], 1e-300),  # f near 0: every unit to the second.
        ([3, 0], 1.0, [1 - 2**-53, 0.5, 0.25], [3, 0], 1.0),  # f = 1: u < 1, all to the first.
        # The Lean replay's three mutants (lean/claims/fr43-integer-segregation.md):
        pytest.param([0, 1], 0.75, [0.5], [0, 1], 0.25, id="the-area-share-not-the-volume-share"),
        pytest.param([0, 1], 0.5, [0.5], [0, 0], 0.5, id="a-tie-goes-to-the-second-daughter"),
        pytest.param([2, 1], 0.5, [0.1, 0.2, 0.9], [2, 0], 0.5, id="the-declared-state-order"),
    ],
)
def test_segregation_is_exact_and_in_unit_order(counts, f, uniform, first, volume, monkeypatch):
    """independent_segregation on the given draws, through segregate and through divide (the
    composite's lifecycle maps: the patch's area share f beside a volume share, and the draws
    injected in place of the parent's partition stream)."""
    held = np.asarray([counts], dtype=np.int64)
    got_first, got_second = iup.segregate(held, np.asarray([f]), np.asarray([uniform]), xp=np)
    assert got_first.tolist() == [first]
    assert (got_first + got_second).tolist() == [counts] and (got_second >= 0).all()
    k = len(counts)
    state = _Division(
        integer_counts=np.asarray([counts, [0] * k, [0] * k], dtype=np.int64),
        integer_divided_units=np.zeros((3, k), dtype=np.int64),
    )
    p = _DivisionLayout(
        integer_map_parent=np.asarray([0]),
        integer_map_daughters=np.asarray([[1, 2]]),
        integer_site_patch=np.asarray([0, 1, 2]),
        integer_partition_key=np.zeros((3, 2), dtype=np.int64),
        integer_block=np.zeros(len(uniform)),
    )
    one = (np.asarray([0]), np.asarray([[1, 2]]), None, np.asarray([True]))
    maps = {
        "membrane_slot": (one[0], one[1], np.asarray([f]), one[3]),
        "cell_slot": (one[0], one[1], np.asarray([volume]), one[3]),
    }
    monkeypatch.setattr(
        iup.streams,
        "site_uniforms",
        lambda words, counters, count: np.asarray([uniform])[:, :count],
    )
    new, valid = iup.divide(state, maps, p, xp=np)
    assert valid
    second = [n - a for n, a in zip(counts, first, strict=True)]
    assert new.integer_counts.tolist() == [[0] * k, first, second]
    assert new.integer_divided_units.tolist() == [[-n for n in counts], first, second]


class _Division(NamedTuple):
    integer_counts: object
    integer_divided_units: object


class _DivisionLayout(NamedTuple):
    integer_map_parent: object
    integer_map_daughters: object
    integer_site_patch: object
    integer_partition_key: object
    integer_block: object


def _block(raw):
    return next(op for op in raw["model"]["operators"] if op["law"] == iup.LAW_ID)


def test_the_stages():
    # Two transfer sites on one patch meet at both rows: two stages.
    raw = worlds.spec_world(W1, dt=0.02, end=0.04)
    units = _block(raw)["populations"][0]
    units["sites"].append(dict(units["sites"][0], id="site_1"))
    declaration = next(d for d in parse_spec(raw).model.operators if d.law == iup.LAW_ID)
    assert iup.stages(declaration) == [0, 1]
    # Without the transfer, the reads alone do not meet: one stage.
    units["transfers"] = []
    declaration = next(d for d in parse_spec(raw).model.operators if d.law == iup.LAW_ID)
    assert iup.stages(declaration) == [0, 0]
    # A parent and its two daughters: the daughters share the node row, the parent meets neither.
    raw = worlds.divided(sites=1, transfer=True)
    spec = parse_spec(raw)
    declaration = next(d for d in spec.model.operators if d.law == iup.LAW_ID)
    assert iup.stages(declaration, iup.lives(spec)) == [0, 0, 1]
    assert iup.stage_plan(1, 0.5) == ((0, 0.5, 0.0),)
    assert iup.stage_plan(2, 0.5) == ((0, 0.25, 0.0), (1, 0.5, 0.0), (0, 0.25, 0.25))


# ------------------------------------------------------------------ refusals


REFUSALS = {
    "a charged species": (
        lambda raw: _block(raw)["species"].__setitem__(
            0, dict(id="Na", catalogue=None, evidence=None)
        ),
        "neutral species only",
    ),
    "a site on a held bath": (
        lambda raw: _block(raw)["populations"][0]["sites"][0].update(patch="wall_cell_0"),
        "faces a held bath",
    ),
    "a channel that does not conserve the subunits": (
        lambda raw: _block(raw)["populations"][0]["channels"][0].update(products={"active": 2}),
        "conserves the subunits",
    ),
    "a channel without a reactant": (
        lambda raw: _block(raw)["populations"][0]["channels"][0].update(reactants={}),
        "has a reactant",
    ),
    "a reactant order above the limit": (
        lambda raw: _block(raw)["populations"][0]["channels"][0].update(
            reactants={"free": 6}, products={"active": 3}
        ),
        "at most 4",
    ),
    "a read of an unlisted species": (
        lambda raw: _block(raw)["populations"][0]["channels"][0].update(
            read=dict(species="K", at="cell")
        ),
        "neither a listed species",
    ),
    "a site above the subunit cap": (
        lambda raw: _block(raw)["populations"][0]["sites"][0].update(
            initial_counts={"free": 1025, "active": 0}
        ),
        "the low-count scope",
    ),
    "the assembly family's exact_fraction": (
        lambda raw: _block(raw)["populations"][0].update(division="exact_fraction"),
        "exact_fraction is the assembly family's",
    ),
    "a seed outside 32 bits": (lambda raw: _block(raw).update(seed=2**32), "[0, 2**32)"),
    "a hazard above the step's bound": (
        lambda raw: _block(raw)["populations"][0]["channels"][1].update(rate_per_s=80.0),
        "dt a0,max",
    ),
}


@pytest.mark.parametrize("name", sorted(REFUSALS))
def test_each_refusal(name):
    change, message = REFUSALS[name]
    raw = worlds.spec_world(W1, dt=0.02, end=0.04)
    change(raw)
    with pytest.raises(ConfigError) as error:
        parse_spec(raw)
    assert message in str(error.value), str(error.value)


def _cohort(site):
    """FR-52: a cohort of the divided world's conducting state at `site`."""
    return dict(id="c", site=site, states=["active"], window_s=[0.0, 1.0])


def _cohort_on_a_born_cell(raw):
    """An unmapped, empty site on a daughter's patch, its cell born at the division, with a
    cohort."""
    units = _block(raw)["populations"][0]
    empty = dict(free=0, active=0)
    units["sites"].append(dict(id="extra", patch="contact_0_d1", initial_counts=empty))
    _block(raw)["cohorts"] = [_cohort("extra")]


DIVISION_REFUSALS = {
    "a cohort at a dividing site (FR-52)": (
        lambda raw: _block(raw).update(cohorts=[_cohort("site_0")]),
        "divides or is born at a division",
    ),
    "a cohort at a daughter site (FR-52)": (
        lambda raw: _block(raw).update(cohorts=[_cohort("site_0_d1")]),
        "divides or is born at a division",
    ),
    "a cohort on a cell that is born (FR-52)": (
        _cohort_on_a_born_cell,
        "on a cell that is born or retires",
    ),
    "units at a daughter before its birth": (
        lambda raw: _block(raw)["populations"][0]["sites"][1].update(
            initial_counts={"free": 2, "active": 0}
        ),
        "declares no units",
    ),
    "a dividing site without its map": (
        lambda raw: _block(raw).update(divisions=[]),
        "a site map names its two daughter sites",
    ),
    "a map whose daughters are swapped": (
        lambda raw: _block(raw)["divisions"][0].update(daughters=["site_0_d2", "site_0_d1"]),
        "does not follow the composite's patch map",
    ),
    "a dividing population without its token": (
        lambda raw: _block(raw)["populations"][0].update(division=None),
        "declares its division token",
    ),
}


@pytest.mark.parametrize("name", sorted(DIVISION_REFUSALS))
def test_each_division_refusal(name):
    change, message = DIVISION_REFUSALS[name]
    raw = worlds.divided(sites=1, transfer=True)
    change(raw)
    with pytest.raises(ConfigError) as error:
        parse_spec(raw)
    assert message in str(error.value), str(error.value)


NEIGHBOURS = {
    "cells.operator.scheduled_cell_replacement@1": "replaces a slot's amounts",
    "cells.operator.scheduled_cell_replacement@2": "replaces a slot's amounts",
    "cells.operator.scheduled_membrane_insertion@1": "opens or closes slots without dividing them",
    "cells.operator.scheduled_membrane_insertion@2": "opens or closes slots without dividing them",
    "cells.operator.neutral_arrival_labels@1": "reports no one-way moves to a label owner",
    "cells.operator.isopotential_partition@1": "does not divide owned state through its lifecycle",
}


@pytest.mark.parametrize("law", sorted(NEIGHBOURS))
def test_each_refused_neighbour(law, monkeypatch):
    """Beside replacement, a mask changer that does not divide through the lifecycle, or a label
    owner, the operator refuses whatever the data; beside the partition only a composite without
    the hook (model None here) is refused."""
    spec = parse_spec(worlds.spec_world(W1, dt=0.02, end=0.04))
    declaration = next(d for d in spec.model.operators if d.law == iup.LAW_ID)
    monkeypatch.setattr(iup, "_entries", lambda _: ((OPERATORS[law], None, None),))
    with pytest.raises(ConfigError, match=NEIGHBOURS[law]):
        iup.check_writers(spec, declaration, None)


# ------------------------------------------------------------------ the division hook


class _Divider(Operator):
    LAW_ID = "cells.operator.test_owned_divider@1"
    SPLIT = True
    RK4 = "split"
    STATE_AXES = MappingProxyType({"divider_units": ["integer_site"]})
    DIVIDES_OWNED = True

    def divide_owned(self, state, maps, masks, p, *, xp):
        return state, xp.asarray(True)


class _NoMethod(Operator):
    LAW_ID = "cells.operator.test_owned_divider_without_its_method@1"
    SPLIT = True
    RK4 = "split"
    STATE_AXES = MappingProxyType({"divider_units": ["integer_site"]})
    DIVIDES_OWNED = True


def test_the_hook_declarations():
    check_declarations(_Divider)
    no_state = type("NoState", (_Divider,), {"STATE_AXES": MappingProxyType({})})
    with pytest.raises(ValueError, match="DIVIDES_OWNED is a bool, true only"):
        check_declarations(no_state)
    with pytest.raises(ValueError, match="DIVIDES_OWNED is a bool, true only"):
        check_declarations(_NoMethod)
    # A retiring operator that takes no lifecycle beside an owned divider is refused (fails closed).
    retiring = type(
        "Retiring",
        (Operator,),
        dict(LAW_ID="cells.operator.test_retiring@1", EVENT=True, RETIRES=True, CLOSES=("active",)),
    )
    errors = pump_composite.lifecycle_errors(adapter, (retiring(), _Divider()))
    assert any("their state would not divide" in e for e in errors)
    assert not pump_composite.lifecycle_errors(adapter, (retiring(),))  # Unchanged without one.


def test_a_composition_without_an_owned_divider_keeps_its_lifecycle():
    raw = worlds.divided(sites=1, transfer=True)
    raw["model"]["operators"] = raw["model"]["operators"][:2]  # The partition alone.
    model = get_model(parse_spec(raw).model)
    assert model.owned_dividers == ()
    composition = get_model(parse_spec(worlds.divided(sites=1, transfer=True)).model)
    assert [op.LAW_ID for op in composition.owned_dividers] == [iup.LAW_ID]


# ------------------------------------------------------------------ one compiled world: W1

DT, END, WINDOW = 0.02, 6.0, 100


def _collect(spec, checkpoint=None):
    windows = list(iter_windows(spec, WindowPolicy(WINDOW, "full"), checkpoint))
    rows = {}
    for window in windows:
        for i, _ in enumerate(np.asarray(window.times)):
            rows[window.start_step + i] = type(window.history)(
                *(np.asarray(v)[i] for v in window.history)
            )
    return windows, rows


@pytest.fixture(scope="module")
def w1():
    spec = parse_spec(worlds.spec_world(W1, dt=DT, end=END, every=DT))
    windows, rows = _collect(spec)
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    return spec, model, p, windows, rows


def _pools(spec, p, row):
    s = list(spec.model.species_ids).index(worlds.SPECIES)
    cell = float(np.asarray(p.amount_reference)[s, 0] + row.amount_increment[s, 0])
    node = float(np.asarray(p.extracellular_amount_reference)[s, 1])
    node += float(row.extracellular_amount_increment[s, 1])
    return cell, node


def test_two_subunits_conserve_and_move_material(w1):
    spec, model, p, _, rows = w1
    assert sorted(rows) == list(range(int(round(END / DT)) + 1))  # Every row checked.
    world = worlds.spec_worlds()[W1]
    total = world["initial_amounts_fmol"]["cell"] + world["initial_amounts_fmol"]["node"]
    previous = None
    for k, row in rows.items():
        free, active = (int(x) for x in row.integer_counts[0])
        assert free + 2 * active == 2, k
        cell, node = _pools(spec, p, row)
        assert abs(cell + node - total) <= 4 * np.finfo(float).eps * total, k
        ledgers = model.balances(row, p)
        assert np.all(ledgers["integer_subunits"] == 0.0), k
        if previous is not None:
            moved = row.integer_transferred_fmol[0, 0] - previous.integer_transferred_fmol[0, 0]
            # The route conducts only while a unit is active (0 or 1 active units here).
            if int(previous.integer_counts[0, 1]) == 0 and int(row.integer_counts[0, 1]) == 0:
                assert moved == 0.0, k
            heat = row.integer_transfer_dissipated_energy_pJ[0]
            assert heat >= previous.integer_transfer_dissipated_energy_pJ[0], k
        previous = row
    last = rows[max(rows)]
    channels = last.integer_trace_channel[0, : int(last.integer_events[0])]
    assert last.integer_transferred_fmol[0, 0] > 0
    assert np.all(channels[0::2] == 0) and np.all(channels[1::2] == 1)  # Form, then return both.


def test_the_first_event_and_the_recorded_uniforms(w1):
    spec, _, _, _, rows = w1
    world, table = worlds.spec_worlds()[W1], _draws()[W1]
    u1 = [float.fromhex(x) for x in table["u1"]]
    # Inactive at the start, so nothing moves and a0 is constant: t0 = E0 / a0.
    c = world["initial_amounts_fmol"]["cell"] / world["volumes_pL"]["cell"]
    a0 = world["channels"][0]["rate_constant_per_s"] * 2 * c  # ff(2, 2) = 2.
    last = rows[max(rows)]
    assert abs(last.integer_trace_time_s[0, 0] - (-math.log(u1[0]) / a0)) <= 1e-15
    for row in rows.values():
        k = int(row.integer_events[0])
        want = -math.log(u1[k])  # The next event's threshold (logs may differ by an ulp).
        assert abs(row.integer_threshold[0] - want) <= 2 * np.finfo(float).eps * want


def test_a_same_seed_restart_between_events_is_bitwise(w1):
    spec, _, _, windows, rows = w1
    last = rows[max(rows)]
    times = last.integer_trace_time_s[0, : int(last.integer_events[0])]
    # A window boundary (so the resumed windows keep the run's lengths and its program) after
    # some events and strictly between two of them.
    cut = WINDOW
    assert np.sum(times < cut * DT) >= 2 and not np.any(np.abs(times - cut * DT) < 1e-12)
    checkpoint = next(
        w.checkpoint_at(float(t))
        for w in windows
        for t in np.asarray(w.times)
        if abs(t - cut * DT) < 1e-9
    )
    _, resumed = _collect(spec, checkpoint)
    for k in range(cut, len(rows)):
        for a, b in zip(resumed[k], rows[k], strict=True):
            assert np.asarray(a).tobytes() == np.asarray(b).tobytes(), k


# A wrong but balanced jump: assemble's change lost, so the subunits are kept and no count moves.
JUMPS = {"declared": None, "assemble's jump lost (planted)": 0}


@pytest.mark.parametrize("jump", sorted(JUMPS))
def test_the_trace_records_the_counts_the_loop_carries(w1, jump):
    """integer_trace_counts (FR-43 part 3's co-writers registration) holds the counts the event
    loop carries on after each event. Honest run: each recorded event's counts are the counts
    before it changed by its channel's declared jump, each row's counts are its last event's, and
    the unused slots hold -1. Plant: one eager half-step to just past the first event, with
    assemble's change zeroed in the bound layout (a wrong jump that keeps the subunits), records
    the counts the loop carries, which are not the declared jump's: the record is the loop's, never
    formed again from the declaration. It compiles only the half-step's loops (about 5 s)."""
    _, _, p, _, rows = w1
    last, start = rows[max(rows)], rows[0]
    declared = np.asarray(p.integer_change)[0]
    first = np.asarray(start.integer_counts[0])
    if JUMPS[jump] is None:
        fired = int(last.integer_events[0])
        counts = np.asarray(last.integer_trace_counts[0])
        channels = np.asarray(last.integer_trace_channel[0, :fired])
        before = first
        for k in range(fired):
            assert np.array_equal(counts[k], before + declared[channels[k]]), k
            before = counts[k]
        for row in rows.values():
            n = int(row.integer_events[0])
            held = counts[n - 1] if n else first
            assert np.array_equal(np.asarray(row.integer_counts[0]), held)
        assert np.all(counts[fired:] == -1)
        return
    planted = np.array(p.integer_change, copy=True)
    planted[0, 0, :] = JUMPS[jump]
    h = float(last.integer_trace_time_s[0, 0]) * (1 + 1e-6)  # Just past the first event.
    state = type(start)(*(jnp.asarray(v) for v in start))
    new, _ = iup.half_step(state, h, p._replace(integer_change=jnp.asarray(planted)))
    assert int(new.integer_events[0]) == 1 and int(new.integer_trace_channel[0, 0]) == 0
    recorded = np.asarray(new.integer_trace_counts[0, 0])
    assert np.array_equal(recorded, np.asarray(new.integer_counts[0]))  # What the loop carries.
    assert not np.array_equal(recorded, first + declared[0])  # It breaks the declared jump.


# ------------------------------------------------------------------ co-writers (FR-43 part 3)

HAZARD = {
    "a bounded source over the bound is counted": (
        lambda: worlds.beside_reactions("source", rate=10.0, end=10.0),
        "dt a0,max",
    ),
    "a producer with no static bound leaves the site unchecked": (
        lambda: worlds.beside_reactions("first_order", block=worlds.units(k_dissolve=80.0)),
        None,
    ),
    "the same site alone is over the bound": (
        lambda: worlds.with_units(
            worlds.cowriter_world(dt=0.02, end=0.04), worlds.units(k_dissolve=80.0)
        ),
        "dt a0,max",
    ),
}


@pytest.mark.parametrize("name", sorted(HAZARD))
def test_the_event_rate_bound_beside_a_co_writer(name):
    """check_hazard_bound sums the conversions' production_bound (FR-43 part 3): a zero-order
    source of 10 mM/s over 10 s raises the read row's bound past dt a0,max = 1, which the declared
    material alone keeps far below; a first-order source (no static bound) leaves the site
    unchecked, the run-time cap its guard, where the site alone is refused."""
    build, message = HAZARD[name]
    if message is None:
        parse_spec(build())
        return
    with pytest.raises(ConfigError, match=message):
        parse_spec(build())


SOURCE_DT, SOURCE_END = 0.01, 4.0


@pytest.fixture(scope="module")
def beside_a_source():
    spec = parse_spec(worlds.source_world(dt=SOURCE_DT, end=SOURCE_END))
    windows, rows = _collect(spec)
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    return spec, model, p, windows, rows


def _blocks(spec):
    units = next(d for d in spec.model.operators if d.law == iup.LAW_ID)
    network = next(d for d in spec.model.operators if d.law == worlds.REACTIONS)
    return units, network


def test_the_first_event_beside_a_source_is_its_closed_form(beside_a_source):
    """Two free subunits at the start: nothing moves before the first event, and the network's
    zero-order source raises the read concentration as c0 + k t, so H(t) = k_a ff (c0 t + k t^2/2)
    and the first event solves H = E0 (within the splitting's O(dt^2): dt^2 r / 8 with r about
    1/s); without the source it would fire at E0 / (k_a ff c0), much later."""
    spec, _, p, _, rows = beside_a_source
    units, network = _blocks(spec)
    k_a = units.populations[0].channels[0].rate_per_s * 2  # ff(2, 2) = 2.
    k = network.reactions[0].rate_constant  # mM/s: J = k V, so dc/dt = k.
    s = list(spec.model.species_ids).index(worlds.SPECIES)
    c0 = float(np.asarray(p.amount_reference)[s, 0]) / spec.model.cells[0].volume_pL
    words = jnp.asarray([streams.key_data(units.seed, 0, "events")])
    e0 = -math.log(float(streams.site_uniforms(words, jnp.asarray([0]), 2)[0, 0]))
    a, b = k_a * k / 2.0, k_a * c0
    with_source = (-b + math.sqrt(b * b + 4.0 * a * e0)) / (2.0 * a)
    without = e0 / b
    first = rows[max(rows)].integer_trace_time_s[0, 0]
    assert abs(first - with_source) <= 1e-4, (first, with_source)
    assert abs(without - with_source) > 100 * 1e-4  # The plant: the source left out.


def _books_error(spec, p, rows, produced_scale=1.0):
    """The largest error of S's amounts against its writers' books at every row: in the cell, its
    start plus the network's production less the transfer; at the node, its start plus the
    transfer (cell to node positive)."""
    s = list(spec.model.species_ids).index(worlds.SPECIES)
    cell_ref = float(np.asarray(p.amount_reference)[s, 0])
    node_ref = float(np.asarray(p.extracellular_amount_reference)[s, 1])
    worst, start = 0.0, rows[0]
    for row in rows.values():
        produced = (row.reaction_produced_fmol[s, 0] - start.reaction_produced_fmol[s, 0]) * (
            produced_scale
        )
        moved = row.integer_transferred_fmol[0, 0] - start.integer_transferred_fmol[0, 0]
        cell = row.amount_increment[s, 0] - start.amount_increment[s, 0]
        node = row.extracellular_amount_increment[s, 1] - start.extracellular_amount_increment[s, 1]
        worst = max(worst, abs(cell - (produced - moved)), abs(node - moved))
    return worst, cell_ref + node_ref


def test_each_writer_books_its_own_moves_beside_a_source(beside_a_source):
    """S's amount at every row is its start plus each writer's own books, to the rounding of that
    many accumulations (64 eps per row at the books' scale); both writers move S; the integer
    ledger is exactly 0 on every row; the network's production 1e-3 high is caught."""
    spec, model, p, _, rows = beside_a_source
    s = list(spec.model.species_ids).index(worlds.SPECIES)
    last = rows[max(rows)]
    produced, moved = last.reaction_produced_fmol[s, 0], last.integer_transferred_fmol[0, 0]
    assert produced > 0 and moved > 0 and int(last.integer_events[0]) >= 4
    error, start = _books_error(spec, p, rows)
    tolerance = 64 * np.finfo(float).eps * len(rows) * (start + produced)
    assert error <= tolerance, (error, tolerance)
    assert _books_error(spec, p, rows, produced_scale=1 + 1e-3)[0] > tolerance
    for k, row in rows.items():
        assert np.all(model.balances(row, p)["integer_subunits"] == 0.0), k


def test_a_restart_between_events_beside_a_source_is_bitwise(beside_a_source):
    """A same-seed restart cut at a window boundary strictly between two events, after some of
    them, is bitwise the uninterrupted run (both writers' state included)."""
    spec, _, _, windows, rows = beside_a_source
    last = rows[max(rows)]
    times = last.integer_trace_time_s[0, : int(last.integer_events[0])]
    cut = next(
        k * WINDOW
        for k in range(1, len(windows))
        if np.sum(times < k * WINDOW * SOURCE_DT) >= 2
        and not np.any(np.abs(times - k * WINDOW * SOURCE_DT) < 1e-12)
    )
    checkpoint = next(
        w.checkpoint_at(float(t))
        for w in windows
        for t in np.asarray(w.times)
        if abs(t - cut * SOURCE_DT) < 1e-9
    )
    _, resumed = _collect(spec, checkpoint)
    for k in range(cut, len(rows)):
        for a, b in zip(resumed[k], rows[k], strict=True):
            assert np.asarray(a).tobytes() == np.asarray(b).tobytes(), k


# ------------------------------------------------------------------ FR-52: passive cohorts (host)

WINDOW_S = cohort_worlds.WINDOW_S  # [1, 2) s throughout the frozen rows (§3).
X, D, T, INACT, A = "X", "dimer", "tetramer", "inactive", "active"
DA, DB, TC, TO = "dimer_a", "dimer_b", "closed", "open"


def V(initial, inside, after=0):
    """A frozen entry (initial, before, inside, after); no frozen event falls before the window."""
    return [Fraction(initial), Fraction(0), Fraction(inside), Fraction(after)]


# docs/PASSIVE_COHORT_DESIGN.md §3, frozen at ed0bd135 and unchanged since: each event's time,
# class reactants and products, pairing table, and the frozen record after it (None: not frozen).
# most: N, the most class units the row's site can hold (§2.3's bound).
ROWS = {
    "A, row 4 as one two-unit event": dict(states=[X], start={X: 2}, most=3, events=[
        (1.5, {}, {X: 1}, {}, {X: V(2, 1)}),
        (1.6, {X: 1}, {}, {}, {X: V("4/3", "2/3")}),
        (1.7, {X: 2}, {}, {}, {X: V(0, 0)}),
        (1.8, {}, {X: 1}, {}, {X: V(0, 1)}),
    ]),
    "A, row 4 as two one-unit events": dict(states=[X], start={X: 2}, most=3, events=[
        (1.5, {}, {X: 1}, {}, {X: V(2, 1)}),
        (1.6, {X: 1}, {}, {}, {X: V("4/3", "2/3")}),
        (1.7, {X: 1}, {}, {}, None),
        (1.75, {X: 1}, {}, {}, {X: V(0, 0)}),
        (1.8, {}, {X: 1}, {}, {X: V(0, 1)}),
    ]),
    "B": dict(states=[X], start={X: 2}, most=3, events=[
        (1.5, {}, {X: 1}, {}, {X: V(2, 1)}),
        (1.6, {X: 2}, {}, {}, {X: V("2/3", "1/3")}),
    ]),
    "C": dict(states=[D, T], start={D: 2, T: 0}, most=3, events=[
        (1.5, {}, {D: 1}, {}, {D: V(2, 1), T: V(0, 0)}),
        (1.6, {D: 2}, {T: 1}, {(D, T): 1}, {D: V("2/3", "1/3"), T: V("2/3", "1/3")}),
        (2.5, {T: 1}, {D: 2}, {(T, D): 1}, {D: V("4/3", "2/3", 1), T: V(0, 0)}),
        (3.0, {D: 1}, {}, {}, {D: V("8/9", "4/9", "2/3"), T: V(0, 0)}),
    ]),
    "C', the round trip": dict(states=[D, T], start={D: 2, T: 0}, most=3, events=[
        (1.6, {D: 2}, {T: 1}, {(D, T): 1}, None),
        (1.8, {T: 1}, {D: 2}, {(T, D): 1}, {D: V(1, 1), T: V(0, 0)}),
    ]),
    "D": dict(states=[INACT, A], start={INACT: 1, A: 1}, most=3, events=[
        (1.5, {}, {INACT: 1}, {}, {INACT: V(1, 1), A: V(1, 0)}),
        (2.5, {INACT: 1}, {A: 1}, {(INACT, A): 1}, {INACT: V("1/2", "1/2"), A: V("3/2", "1/2")}),
        (3.0, {A: 1}, {INACT: 1}, {(A, INACT): 1}, {INACT: V("5/4", "3/4"), A: V("3/4", "1/4")}),
        (3.5, {INACT: 1}, {}, {}, {INACT: V("5/8", "3/8"), A: V("3/4", "1/4")}),
    ]),
    "F": dict(states=[DA, DB, T], start={DA: 2, DB: 1, T: 0}, most=4, events=[
        (1.5, {}, {DB: 1}, {}, {DA: V(2, 0), DB: V(1, 1), T: V(0, 0)}),
        (1.6, {DA: 1, DB: 1}, {T: 1}, {(DA, T): 1},
         {DA: V(1, 0), DB: V("1/2", "1/2"), T: V(1, 0)}),
        (2.5, {T: 1}, {DA: 1, DB: 1}, {(T, DA): 1},
         {DA: V(2, 0), DB: V("1/2", "1/2", 1), T: V(0, 0)}),
        (3.0, {DB: 1}, {}, {}, {DA: V(2, 0), DB: V("1/4", "1/4", "1/2"), T: V(0, 0)}),
    ]),
    "G": dict(states=[D, TC, TO], start={D: 1, TC: 3, TO: 0}, most=8, events=[
        (1.5, {}, {D: 1}, {}, {D: V(1, 1), TC: V(3, 0), TO: V(0, 0)}),
        (1.6, {D: 2}, {TC: 1}, {(D, TC): 1}, {D: V(0, 0), TC: V("7/2", "1/2"), TO: V(0, 0)}),
        (2.5, {TC: 2}, {TO: 2}, {(TC, TO): 2},
         {D: V(0, 0), TC: V("7/4", "1/4"), TO: V("7/4", "1/4")}),
        (3.0, {TC: 1}, {TO: 1}, {(TC, TO): 1},
         {D: V(0, 0), TC: V("7/8", "1/8"), TO: V("21/8", "3/8")}),
    ]),
}  # fmt: skip


def _vectors(states, counts, r, p, pairs):
    n = np.array([counts[s] for s in states])
    rv, pv = (np.array([side.get(s, 0) for s in states]) for side in (r, p))
    m = np.zeros((len(states), len(states)), dtype=np.int64)
    for (a, b), x in pairs.items():
        m[states.index(a), states.index(b)] = x
    return n, rv, pv, m


def _kernel_run(row, *, advance=uc.advance, tables=None):
    """The kernel's binary64 record [state, label] after each event of a frozen row; tables:
    {event: table} put in place of the row's (a plant)."""
    states, counts = row["states"], dict(row["start"])
    units = np.zeros((len(states), len(uc.LABELS)))
    units[:, uc.INITIAL] = [counts[s] for s in states]
    out = []
    for k, (time, r, p, pairs, _) in enumerate(row["events"]):
        n, rv, pv, m = _vectors(states, counts, r, p, (tables or {}).get(k, pairs))
        label = np.asarray(uc.label_of(np.asarray(time), *WINDOW_S, xp=np))
        with np.errstate(all="ignore"):
            units = advance(units, n, rv, pv, m, label, xp=np)
        counts = {s: counts[s] - r.get(s, 0) + p.get(s, 0) for s in states}
        out.append(units)
    return out


def _exact_run(row, *, tables=None, members=None):
    """The reference's exact record after each event; members: a class put in place of the row's."""
    members = members or row["states"]
    counts, out = dict(row["start"]), []
    record = exact.start_record(counts, members)
    for k, (time, r, p, pairs, _) in enumerate(row["events"]):
        pairs = (tables or {}).get(k, pairs)
        r_c, p_c = (exact.class_side(side, members) for side in (r, p))
        pairs = {(a, b): m for (a, b), m in pairs.items() if a in members and b in members}
        record = exact.update(
            record, {s: counts[s] for s in members}, r_c, p_c, pairs,
            exact.label_index(time, WINDOW_S),
        )  # fmt: skip
        counts = {s: counts[s] - r.get(s, 0) + p.get(s, 0) for s in row["states"]}
        out.append(record)
    return out


@pytest.mark.parametrize("name", sorted(ROWS))
def test_a_frozen_row(name):
    """The frozen fractions three ways (§3): enumerated over labelled units, by the exact update,
    and by the kernel's binary64 record within 8 (K + 1) u N, an emptied state's entries exactly
    0. Each channel's table is the rule's, or, in row F, one of two or more legal tables."""
    row = ROWS[name]
    states = row["states"]
    start = {s: [uc.INITIAL] * n for s, n in row["start"].items()}
    labels = [exact.label_index(t, WINDOW_S) for t, *_ in row["events"]]
    events = [
        (r, p, pairs, x) for (_, r, p, pairs, _), x in zip(row["events"], labels, strict=True)
    ]
    enumerated = exact.enumerate_events(start, events, states)
    rational, kernel = _exact_run(row), _kernel_run(row)
    for k, (_, r, p, pairs, frozen) in enumerate(row["events"]):
        legal = exact.tables(r, p)
        rule = uc.unique_table(*(_vectors(states, row["start"], r, p, {})[1:3]))
        if rule is None:
            assert name == "F" and len(legal) > 1 and pairs in legal
        else:
            assert legal == [pairs] == [{(states[a], states[b]): m for (a, b), m in rule.items()}]
        if frozen is None:
            continue
        bound = uc.rounding_bound(k + 1, row["most"])
        for s in states:
            assert enumerated[k][s] == frozen[s] and rational[k][s] == frozen[s], (k, s)
            got = kernel[k][states.index(s)]
            pairs_ = zip(got, frozen[s], strict=True)
            assert max(abs(Fraction(float(x)) - y) for x, y in pairs_) <= bound
            if not any(frozen[s]):
                assert np.all(got == 0.0), (k, s)  # An emptied state: exact zeros.


@pytest.mark.parametrize(
    "time, label",
    [(1.0, uc.INSIDE), (2.0, uc.AFTER), (math.nextafter(1.0, 0.0), uc.BEFORE),
     (math.nextafter(2.0, 0.0), uc.INSIDE), (0.0, uc.BEFORE), (3.0, uc.AFTER)],
)  # fmt: skip
def test_the_window_is_half_open(time, label):
    """An arrival at exactly start joins inside, one at exactly end joins after (the ties)."""
    assert int(uc.label_of(np.asarray(time), *WINDOW_S, xp=np)) == label
    assert exact.label_index(time, WINDOW_S) == label


def _sides(names):
    """Each side of a small channel: empty, or one to three states with coefficients 1 to 3 and
    at most 7 units."""
    out = [{}]
    for k in range(1, 4):
        for coefficients in itertools.product(range(1, 4), repeat=k):
            if sum(coefficients) <= 7:
                out.append(dict(zip(names, coefficients, strict=False)))
    return out


def test_the_rule_agrees_with_brute_force_counts_of_the_legal_tables():
    """§2.3's reading of a unique table, against the reference's brute-force count of the legal
    tables of all 1,296 small channels (36 sides a side): unique exactly where the rule says, and
    then the rule's table."""
    consumed, produced = ["a0", "a1", "a2"], ["b0", "b1", "b2"]
    states, unique = consumed + produced, 0
    for r in _sides(consumed):
        for p in _sides(produced):
            legal = exact.tables(r, p)
            rule = uc.unique_table(*(_vectors(states, dict.fromkeys(states, 0), r, p, {})[1:3]))
            assert (rule is not None) == (len(legal) == 1), (r, p)
            if rule is not None:
                assert legal == [{(states[a], states[b]): m for (a, b), m in rule.items()}]
                unique += 1
    assert unique == 90  # 1,296 channels, 1,206 of them with two or more legal tables.


def _one_pair(table):
    """The planted update's table: at most one pair per channel (§5.2)."""
    first = sorted(table)[:1]
    return {first[0]: 1} if first else {}


def _against_enumeration(r, p, pairs, start, label, *, plant=False):
    """(the kernel's record, the enumerated mean, its bound) after one event from start
    {state: [label, ...]} (the plant: the one-pair table in the kernel)."""
    states = sorted(start)
    mean = exact.enumerate_events(start, [(r, p, pairs, label)], states)[0]
    units = np.zeros((len(states), len(uc.LABELS)))
    for s, held in start.items():
        for x in held:
            units[states.index(s), x] += 1
    counts = {s: len(held) for s, held in start.items()}
    n, rv, pv, m = _vectors(states, counts, r, p, _one_pair(pairs) if plant else pairs)
    got = uc.advance(units, n, rv, pv, m, np.asarray(label), xp=np)
    most = sum(len(held) for held in start.values()) + sum(p.values())
    error = max(
        abs(Fraction(float(got[states.index(s), x])) - mean[s][x])
        for s in states
        for x in range(len(uc.LABELS))
    )
    return error, uc.rounding_bound(1, most)


EXPLICIT = {  # (r, p, start {state: [labels]}): several labels in every start.
    "2X -> 2Z (m = 2)": ({"X": 2}, {"Z": 2}, {"X": [0, 1, 2, 3], "Z": [3]}),
    "X + Y -> 2Z (two states into one)": (
        {"X": 1, "Y": 1}, {"Z": 2}, {"X": [0, 2, 1], "Y": [3, 0], "Z": [2]}),
    "2X + Y -> 3Z (m = 2 and 1)": (
        {"X": 2, "Y": 1}, {"Z": 3}, {"X": [0, 1, 2], "Y": [0, 3], "Z": [1]}),
    "2T_c -> 2T_o (open2)": ({"Tc": 2}, {"To": 2}, {"Tc": [0, 0, 2, 1], "To": [3]}),
}  # fmt: skip


@pytest.mark.parametrize("name", sorted(EXPLICIT))
def test_the_update_is_the_enumerated_mean(name):
    """The host update test (the lead, after D376): the kernel's update equals the exact mean over
    individually labelled units within its bound, and the one-pair update fails it."""
    r, p, start = EXPLICIT[name]
    (pairs,) = exact.tables(r, p)  # Each resolves by rule.
    error, bound = _against_enumeration(r, p, pairs, start, uc.INSIDE)
    assert error <= bound, (error, bound)
    planted, _ = _against_enumeration(r, p, pairs, start, uc.INSIDE, plant=True)
    assert planted > bound, planted


def test_the_update_on_random_small_channels():
    """120 random channels (two to four states, coefficients 1 to 3, up to six pairs, each a random
    legal table), from random starts with random labels: the kernel's update is the enumerated mean
    within its bound on every one; the one-pair plant departs on most of those holding two or
    more pairs (at the desk, 721 of 760)."""
    rng = random.Random(52)
    checked = multi = departed = 0
    while checked < 120:
        size = rng.randint(2, 4)
        names = [f"s{i}" for i in range(size)]
        cut = rng.randint(1, size - 1)
        r = {s: rng.randint(1, 3) for s in names[:cut]}
        p = {s: rng.randint(1, 3) for s in names[cut:]}
        pairs = rng.choice(exact.tables(r, p))
        if sum(pairs.values()) > 6:
            continue
        start = {s: [rng.randrange(4) for _ in range(r[s] + rng.randint(0, 1))] for s in r}
        start |= {s: [rng.randrange(4) for _ in range(rng.randint(0, 2))] for s in p}
        ways = 1
        for a in r:
            carried = [m for (x, _), m in pairs.items() if x == a]
            ways *= math.comb(len(start[a]), r[a]) * math.factorial(r[a])
            ways //= math.prod(math.factorial(m) for m in carried) * math.factorial(
                r[a] - sum(carried)
            )
        if ways > 200:  # Enumeration cost.
            continue
        label = rng.choice((uc.BEFORE, uc.INSIDE, uc.AFTER))
        error, bound = _against_enumeration(r, p, pairs, start, label)
        assert error <= bound, (r, p, pairs, start, label)
        checked += 1
        if sum(pairs.values()) >= 2:
            multi += 1
            departed += _against_enumeration(r, p, pairs, start, label, plant=True)[0] > bound
    assert multi >= 20 and departed > multi // 2, (multi, departed)


def _cut_oldest(record, taken, newest=False):
    """A mutant removal of one state's units, oldest (initial first) or newest first."""
    out, left = list(record), taken
    for x in reversed(range(len(out))) if newest else range(len(out)):
        k = min(out[x], left)
        out[x], left = out[x] - k, left - k
    return out


def _n_after(units, n, r, p, m, label, *, xp):
    return uc.advance(units, n - r + p, r, p, m, label, xp=xp)


def _shares_after_the_loss(units, n, r, p, m, label, *, xp):
    lost = units * (n - r)[:, None] / np.where(r > 0, n, 1)[:, None]
    shares = lost / np.where(r > 0, n - r, 1)[:, None]  # 0/0 at an emptied state.
    out = np.where((r > 0)[:, None], lost, units)
    out = out + np.einsum("ab,al->bl", m, shares)
    hot = np.arange(units.shape[1]) == label
    return out + np.where(hot[None, :], (p - m.sum(axis=0))[:, None], 0)


def _two_labels(units, n, r, p, m, label, *, xp):
    out = uc.advance(units, n, r, p, m, label, xp=xp)
    out[:, uc.INITIAL] += p - m.sum(axis=0)  # The new units joined to the initial label too.
    return out


def _no_negative_arrival(units, n, r, p, m, label, *, xp):
    """A merge that carries both identities and adds no unit: no arrival below 0."""
    out = uc.advance(units, n, r, p, m, label, xp=xp)
    out[:, int(label)] += np.maximum(m.sum(axis=0) - p, 0)
    return out


def _total_off(states, units, counts, events):
    return max(abs(float(units[states.index(s)].sum()) - counts[s]) for s in states) > (
        uc.rounding_bound(events, 3)
    )


def _counts_after(row, k):
    counts = dict(row["start"])
    for _, r, p, _, _ in row["events"][: k + 1]:
        counts = {s: counts[s] - r.get(s, 0) + p.get(s, 0) for s in counts}
    return counts


_A3 = ROWS["A, row 4 as one two-unit event"]["events"][1][4][X]  # (4/3, 2/3), frozen.

COHORT_PLANTS = {  # §5.2: each returns whether the plant is caught where the note says.
    "one unit per event: integrity in row B": lambda: _total_off(
        [X], _kernel_run(ROWS["B"], advance=lambda u, n, r, p, m, x, xp: uc.advance(
            u, n, np.minimum(r, 1), p, m, x, xp=xp))[1], _counts_after(ROWS["B"], 1), 2),
    "oldest-first removal: row A3 exactly": lambda: _cut_oldest(V(2, 1), 1) == V(1, 1) != _A3,
    "newest-first removal: row A3 exactly": lambda: (
        _cut_oldest(V(2, 1), 1, newest=True) == V(2, 0) != _A3),
    "n read after the event: rows A3 and B": lambda: all(
        not np.allclose(_kernel_run(ROWS[name], advance=_n_after)[k][0],
                        [float(x) for x in ROWS[name]["events"][k][4][X]])
        for name, k in (("A, row 4 as one two-unit event", 1), ("B", 1))),
    "the merge read as new: row C3": lambda: (
        _exact_run(ROWS["C"], tables={1: {}})[1][T] == V(0, 1) != ROWS["C"]["events"][1][4][T]),
    "a split that copies its identity (not taken): rows C4, C5 and C'": lambda: (
        _exact_run(ROWS["C"], tables={2: {(T, D): 2}})[2][D] == V(2, 1)
        and _exact_run(ROWS["C"], tables={2: {(T, D): 2}})[3][D] == V("4/3", "2/3")
        and _exact_run(ROWS["C', the round trip"], tables={1: {(T, D): 2}})[1][D] == V(2, 0)),
    "a merge carrying both identities: integrity in row C3": lambda: (
        _total_off([D, T], _kernel_run(ROWS["C"], advance=_no_negative_arrival,
                                       tables={1: {(D, T): 2}})[1], _counts_after(ROWS["C"], 1), 2)
        and min(_exact_run(ROWS["C"], tables={1: {(D, T): 2}})[1][T]) < 0),
    "one pair per channel: row G at open2": lambda: (
        _exact_run(ROWS["G"], tables={2: {(TC, TO): 1}})[2][TO] == V("7/8", "1/8", 1)),
    "a wrong pair in join: row F3, then F4": lambda: (
        _exact_run(ROWS["F"], tables={1: {(DB, T): 1}})[1][T] == V("1/2", "1/2")
        and _exact_run(ROWS["F"], tables={1: {(DB, T): 1}})[2][DA] == V("3/2", "1/2")),
    "a wrong pair in cut: row F4": lambda: (
        _exact_run(ROWS["F"], tables={2: {(T, DB): 1}})[2][DA] == V(1, 0, 1)
        and _exact_run(ROWS["F"], tables={2: {(T, DB): 1}})[2][DB] == V("3/2", "1/2")),
    "the shares read after the loss: row C4 reads 0/0": lambda: not np.all(
        np.isfinite(_kernel_run(ROWS["C"], advance=_shares_after_the_loss)[2])),
    "the residence reading of an activation: row D3": lambda: (
        _exact_run(ROWS["D"], members=[A])[1][A] == [1, 0, 0, 1]),
    "an arrival added to two labels: the partition": lambda: _total_off(
        [X], _kernel_run(ROWS["B"], advance=_two_labels)[0], _counts_after(ROWS["B"], 0), 1),
    "a closed end: the tie at end": lambda: (
        (lambda t: uc.BEFORE if t < 1.0 else (uc.INSIDE if t <= 2.0 else uc.AFTER))(2.0)
        != exact.label_index(2.0, WINDOW_S)),
    "an open start: the tie at start": lambda: (
        (lambda t: uc.BEFORE if t <= 1.0 else (uc.INSIDE if t < 2.0 else uc.AFTER))(1.0)
        != exact.label_index(1.0, WINDOW_S)),
}  # fmt: skip


@pytest.mark.parametrize("name", sorted(COHORT_PLANTS))
def test_each_cohort_plant_is_caught(name):
    assert COHORT_PLANTS[name]()


def _homo(raw):
    return _block(raw)["cohorts"][0]


def _hetero(raw):
    return _block(raw)["cohorts"][1]


def _both_sides(raw):
    homo = _block(raw)["populations"][0]
    homo["channels"].append(
        dict(id="shed", reactants={"dimer": 2}, products={"dimer": 1, "free": 2},
             rate_per_s=0.1, read=None)
    )  # fmt: skip


COHORT_REFUSALS = {  # §2.6, one row each, on the qualification world.
    "an empty cohorts list": (
        lambda raw: _block(raw).update(cohorts=[]),
        "cohorts is a non-empty list (omit it for none)"),
    "an unknown site": (lambda raw: _homo(raw).update(site="site_9"), "names an undeclared site"),
    "an unknown state": (
        lambda raw: _homo(raw)["states"].append("trimer"), "not a unit state of population homo"),
    "a repeated cohort ID": (
        lambda raw: _hetero(raw).update(id="homo_units"), "cohort IDs are unique"),
    "an empty class": (lambda raw: _homo(raw).update(states=[]), "lists its states"),
    "a state listed twice": (
        lambda raw: _homo(raw)["states"].append("dimer"), "lists each state once"),
    "a window that ends before it starts": (
        lambda raw: _homo(raw).update(window_s=[2.0, 1.0]), "0 <= start < end"),
    "a window that starts before 0": (
        lambda raw: _homo(raw).update(window_s=[-1.0, 1.0]), "0 <= start < end"),
    "a window that does not end": (
        lambda raw: _homo(raw).update(window_s=[1.0, math.inf]), "0 <= start < end"),
    "an empty carries list": (
        lambda raw: _homo(raw).update(carries=[]),
        "carries is a non-empty list (omit it for none)"),
    "a pairing for an unknown channel": (
        lambda raw: _hetero(raw)["carries"].append(dict(channel="fuse", pairs=[])),
        "undeclared channel 'fuse'"),
    "a conducting state outside the class": (
        lambda raw: _homo(raw).update(states=["dimer", "closed"]),
        "leaves out open, which conducts S"),
    "an ambiguous channel left undeclared": (
        lambda raw: _hetero(raw)["carries"].pop(0), "ambiguous: declare its pairs"),
    "a pairing declared where the rule resolves it (open2)": (
        lambda raw: _homo(raw).update(
            carries=[dict(channel="open2", pairs=[["closed", "open"], ["closed", "open"]])]),
        "resolved by rule; omit it"),
    "the copying split, where the rule resolves it (D375)": (
        lambda raw: _homo(raw).update(
            carries=[dict(channel="split", pairs=[["closed", "dimer"], ["closed", "dimer"]])]),
        "resolved by rule; omit it"),
    "a pairing given twice": (
        lambda raw: _hetero(raw)["carries"].append(
            dict(channel="join", pairs=[["dimer_a", "tetramer"]])),
        "pairing twice"),
    "a pair naming a state outside the class": (
        lambda raw: _hetero(raw)["carries"][0].update(pairs=[["free", "tetramer"]]),
        "names a state outside the class"),
    "a pair from a state the channel does not consume": (
        lambda raw: _hetero(raw)["carries"][0].update(pairs=[["tetramer", "tetramer"]]),
        "does not consume tetramer"),
    "a pair into a state the channel does not make": (
        lambda raw: _hetero(raw)["carries"][0].update(pairs=[["dimer_a", "dimer_b"]]),
        "does not make dimer_b"),
    "more pairs into a state than the channel makes": (
        lambda raw: _hetero(raw)["carries"][0].update(
            pairs=[["dimer_a", "tetramer"], ["dimer_b", "tetramer"]]),
        "more than channel join makes of it"),
    "the copying cut, more pairs from a state than it consumes (D375)": (
        lambda raw: _hetero(raw)["carries"][1].update(
            pairs=[["tetramer", "dimer_a"], ["tetramer", "dimer_b"]]),
        "an identity is not copied"),
    "an incomplete pairing": (
        lambda raw: _hetero(raw)["carries"][0].update(pairs=[]),
        "fewer than min(R, P) = 1: incomplete"),
    "a class state on both sides of a channel": (_both_sides, "on both sides"),
}  # fmt: skip


@pytest.mark.parametrize("name", sorted(COHORT_REFUSALS))
def test_each_cohort_refusal(name):
    change, message = COHORT_REFUSALS[name]
    raw = cohort_worlds.qualification()
    change(raw)
    with pytest.raises(ConfigError) as error:
        parse_spec(raw)
    assert message in str(error.value), str(error.value)


def test_cohorts_round_trip_bind_their_tables_and_none_is_omitted():
    """The declaration writes back as given and parses again; the bound tables are the declared
    pairs for join and cut and the rule's elsewhere (row F's binding check); the record starts at
    [n_k(0), 0, 0, 0] in each class state; a world without cohorts writes none, binds zero-size
    cohort arrays, and keeps its batch signature's form."""
    raw = cohort_worlds.qualification()
    spec = parse_spec(raw)
    declaration = next(d for d in spec.model.operators if d.law == iup.LAW_ID)
    written = iup.declaration_to_dict(declaration)
    assert written["cohorts"] == _block(raw)["cohorts"]
    assert parse_spec(raw) == spec
    state, p = get_model(spec.model).initial_values(spec)
    for q, population in enumerate(declaration.populations):
        cohort = declaration.cohorts[q]
        ids = [u.id for u in population.unit_states]
        declared = {c.channel: c.pairs for c in cohort.carries}
        for y, channel in enumerate(population.channels):
            want = np.zeros((4, 4), dtype=np.int64)
            for a, b in declared.get(channel.id, ()):
                want[ids.index(a), ids.index(b)] += 1
            if channel.id not in declared:
                r, s = iup.class_stoichiometry(population, set(cohort.states))[channel.id]
                for (a, b), m in uc.unique_table(r, s).items():
                    want[a, b] = m
            assert np.array_equal(np.asarray(p.integer_cohort_pairs)[q, y], want), channel.id
        start = np.asarray(state.integer_cohort_units)[q]
        counts = dict(population.sites[0].initial_counts)
        assert [list(x) for x in start] == [
            [counts[s] if s in cohort.states else 0, 0, 0, 0] for s in ids
        ]
    assert [t["found"] for t in iup.cohort_summary(declaration)[1]["tables"].values()] == [
        "rule", "rule", "rule", "rule", "declared", "declared"
    ]  # fmt: skip
    plain = parse_spec(cohort_worlds.unobserved())
    bare = next(d for d in plain.model.operators if d.law == iup.LAW_ID)
    assert "cohorts" not in iup.declaration_to_dict(bare) and bare.cohorts == ()
    state, p = get_model(plain.model).initial_values(plain)
    assert np.asarray(state.integer_cohort_units).shape == (0, 4, 4)
    assert np.asarray(p.integer_cohort_pairs).shape == (0, 7, 4, 4)
    op = OPERATORS[iup.LAW_ID]
    assert len(op.batch_signature(bare)) == 7 and len(op.batch_signature(declaration)) == 8


def test_the_readout_fails_closed():
    """The host readout (§1, §2.3): at the start every cohort is resolved, its entries the start's
    and FR-52's two quantities 0; a non-finite entry, a state outside the class holding units,
    labels that miss the count and a relative drift of 1e-12 per event (20 events) are each
    unresolved, with every value None, never 0 or ∞."""
    spec = parse_spec(cohort_worlds.qualification())
    declaration = next(d for d in spec.model.operators if d.law == iup.LAW_ID)
    state, p = get_model(spec.model).initial_values(spec)
    state = type(state)(*(np.asarray(v) for v in state))
    honest = iup.cohort_readout(declaration, p, state, delta_c_mM={"flow": 0.5})
    assert [e["resolved"] for e in honest] == [True, True]
    homo = honest[0]
    assert homo["expected_units"]["closed"] == dict(initial=3.0, before=0.0, inside=0.0, after=0.0)
    assert homo["initial_conducting_units"] == 0.0 and homo["inside_units"] == 0.0
    assert homo["flux_fmol_per_s"]["flow"] == dict.fromkeys(uc.LABELS, 0.0)
    units = state.integer_cohort_units
    events = np.array([20, 0])
    plants = {
        "a non-finite entry": units.copy(),
        "a state outside the class holding units": units.copy(),
        "labels that miss the count": units.copy(),
        "a drift of 1e-12 per event": units * (1 + 1e-12) ** 20,
    }
    plants["a non-finite entry"][0, 1, 2] = np.nan
    plants["a state outside the class holding units"][0, 0, 0] = 1.0
    plants["labels that miss the count"][0, 2, 3] = 1e-9
    for name, planted in plants.items():
        row = state._replace(integer_cohort_units=planted, integer_events=events)
        (entry, _) = iup.cohort_readout(declaration, p, row)
        assert not entry["resolved"] and entry["problems"], name
        assert entry["expected_units"] is None and entry["inside_units"] is None, name


class _Row(NamedTuple):
    integer_events: np.ndarray
    integer_counts: np.ndarray
    integer_trace_time_s: np.ndarray
    integer_trace_channel: np.ndarray
    integer_trace_counts: np.ndarray
    integer_cohort_units: np.ndarray


CHAIN = dict(  # Row C's population, as the reference reads a declaration.
    populations=[dict(
        id="chain",
        unit_states=[dict(id="free", subunits=1), dict(id="dimer", subunits=2),
                     dict(id="tetramer", subunits=4)],
        channels=[dict(id="assemble", reactants={"free": 2}, products={"dimer": 1}),
                  dict(id="dissolve", reactants={"dimer": 1}, products={"free": 2}),
                  dict(id="merge", reactants={"dimer": 2}, products={"tetramer": 1}),
                  dict(id="split", reactants={"tetramer": 1}, products={"dimer": 2})],
        sites=[dict(id="site_0", initial_counts={"free": 2, "dimer": 2, "tetramer": 0})],
    )],
    cohorts=[dict(id="chain_units", site="site_0", states=["dimer", "tetramer"],
                  window_s=list(WINDOW_S))],
)  # fmt: skip
CHAIN_EVENTS = ((1.5, 0), (1.6, 2), (2.5, 3), (3.0, 1))  # Row C's events: (time, channel).


def _chain_run(capacity=6, *, jump=None, edit=None):
    """{step: row} as an engine would save row C's events (rows after 0, 2 and 4 events): the
    counts by each event's declared jump (jump: {event: change} applied in its place, a planted
    engine), the record by the kernel; edit(trace) tampers with the recorded counts."""
    population = CHAIN["populations"][0]
    states = [u["id"] for u in population["unit_states"]]
    member = np.array([s in CHAIN["cohorts"][0]["states"] for s in states])
    counts = np.array([2, 2, 0])
    units = np.zeros((1, 3, 4))
    units[0, 1, uc.INITIAL] = 2
    times, chans = np.zeros((1, capacity)), -np.ones((1, capacity), dtype=np.int64)
    trace = -np.ones((1, capacity, 3), dtype=np.int64)
    saved = {0: (0, counts.copy(), units.copy())}
    for k, (time, c) in enumerate(CHAIN_EVENTS):
        channel = population["channels"][c]
        r = np.array([channel["reactants"].get(s, 0) for s in states])
        p = np.array([channel["products"].get(s, 0) for s in states])
        m = np.zeros((1, 3, 3), dtype=np.int64)
        for (a, b), x in uc.unique_table(r * member, p * member).items():
            m[0, a, b] = x
        label = np.asarray(uc.label_of(np.asarray([time]), *WINDOW_S, xp=np))
        units = uc.advance(units, counts[None], (r * member)[None], (p * member)[None], m, label,
                           xp=np)  # fmt: skip
        counts = counts + (p - r if jump is None or k not in jump else jump[k])
        if k < capacity:
            times[0, k], chans[0, k], trace[0, k] = time, c, counts
        if k + 1 in (2, 4):
            saved[k + 1] = (k + 1, counts.copy(), units.copy())
    if edit is not None:
        edit(trace)
    return {
        step: _Row(np.array([n]), held[None], times, chans, trace, record)
        for step, (n, held, record) in enumerate(saved.values())
    }


def _bump(trace):
    trace[0, 2] += np.array([-2, 1, 0])  # A balanced change to event 2's recorded counts.


INTEGRITY = {  # (the run, the problems that must be named; None: resolved).
    "the honest run": (lambda: _chain_run(), None),
    "a slot's counts altered between two saved rows (§9.8)": (
        lambda: _chain_run(edit=_bump), ["event 2"]),
    "a wrong but balanced jump (D400's plant, §9.8)": (
        lambda: _chain_run(jump={0: np.array([0, 0, 0])}), ["event 0", "saved counts"]),
    "a slot recorded in its channel only": (
        lambda: _chain_run(edit=lambda t: t[0, 3].__setitem__(slice(None), -1)),
        ["recorded in its channel or counts only"]),
    "a trace whose capacity ends before the last events (row B's truncation)": (
        lambda: _chain_run(capacity=3), ["past the trace's 3 slots"]),
}  # fmt: skip


@pytest.mark.parametrize("name", sorted(INTEGRITY))
def test_the_reference_reader_holds_its_integrity_rows(name):
    """The reference rebuilds the counts from the channels and the declared stoichiometry, never
    from the engine's: the rebuilt counts equal the recorded ones at every event and the saved ones
    at every row, the slots agree with the channels, and the record meets the exact one within its
    bound. Each failure leaves the run unresolved, naming it. A tampered slot between two saved
    rows fails only the per-event row; a wrong but balanced jump fails both."""
    run, named = INTEGRITY[name]
    report = exact.read_run(CHAIN, run(), "chain_units")
    if named is None:
        assert report["resolved"] and not report["problems"]
        assert report["rows"][2]["exact"]["dimer"] == V("8/9", "4/9", "2/3")
        return
    assert not report["resolved"]
    for words in named:
        assert any(words in problem for problem in report["problems"]), report["problems"]
    if name.startswith("a slot's counts"):
        assert not any("saved counts" in problem for problem in report["problems"])


@pytest.mark.parametrize("record", ["honest", "planted non-finite"])
def test_a_division_reads_the_cohort_record_beside_it(record):
    """The lead's ruling on §9.5 (option a): at a division,
    cells.operator.isopotential_partition@1's finiteness check reads every field of the state,
    the cohort record of a site that never divides among them. An honest world passes the
    division, its units segregated and the record kept bit for bit; a non-finite record, which
    only an engine fault could make, refuses it."""
    spec = parse_spec(cohort_worlds.dividing_beside_cohort())
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    state = type(state)(*(np.asarray(v) for v in state))
    p = type(p)(*(np.asarray(v) for v in p))
    control = control_values(spec, [0.02])
    control = type(control)(*(np.asarray(v)[0] for v in control))
    partition = next(op for op in model.operators if op.LAW_ID == worlds.PARTITION)
    if record != "honest":
        nan = np.full_like(state.integer_cohort_units, np.nan)
        state = state._replace(integer_cohort_units=nan)
    new, ok = partition.event(
        state, control, p, xp=np, view=model._view_for(partition, p, xp=np),
        lifecycle=partial(model._owned_lifecycle, p),
    )  # fmt: skip
    if record != "honest":
        assert not bool(ok)
        return
    assert bool(ok)
    counts = np.asarray(new.integer_counts)
    assert counts[0].tolist() == [0, 0] and int(counts[1:3, 0].sum()) == 2  # Segregated.
    assert np.asarray(new.integer_cohort_units).tobytes() == state.integer_cohort_units.tobytes()
