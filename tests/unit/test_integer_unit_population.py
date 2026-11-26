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
* C3.6: a same-seed restart cut between events is bitwise the uninterrupted run.

The compiled world runs once per module (about 30 s on one core, most of it the compile): the
restart and the closed forms need a run, and the run's rows serve every compiled check here.
"""

import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.windows import WindowPolicy, iter_windows
from cells.models import pump_composite
from cells.models import pump_composite_adapter as adapter
from cells.numerics import counter_streams as streams
from cells.operators import OPERATORS
from cells.operators import integer_unit_population as iup
from cells.operators.contract import Operator, check_declarations
from cells.registry.models import get_model
from validation.fr43_part3 import worlds

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


DIVISION_REFUSALS = {
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
