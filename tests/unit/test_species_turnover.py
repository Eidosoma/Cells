"""Tier-1 smoke test of cells.operator.scheduled_species_turnover@1 (secreted-species design §2.2).

The operator's half-step on a bound quiescent world, in NumPy (no compile): the closed form
n' = n e^{-kh} + (P/k)(1 - e^{-kh}) at O(1) fractions, the bookings, the booked work against the
exact free-energy change written out independently (Decimal, 50 digits: the NumPy dG test of record
for this law), the host checks closing at the species' own scale with a negative control, the start
state selected bitwise at zero rate, untouched rows and nodes bitwise, the anchored-amount limit of
a pool cleared far below its anchor, the definition refusals with their messages, and the half-step
beside a planted rate-route source (B1′), bitwise the half-step at the product rates.

The stored change at stiff rates (one table, each row a claim with its plant; the independent Lean
project's finding of 20 November 2026, lean/claims/scheduled-species-turnover.md): where the
half-step's kh exceeds NET_EXPONENT the change is formed net, (P/k - n) f, and the Lean case keeps
its 1 fmol change and its work; elsewhere the node update keeps the gross form's bits, in NumPy
and compiled (kernels only, no world).
"""

import contextlib
import math
import re
from decimal import Decimal, getcontext
from types import SimpleNamespace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.errors import NumericalError
from cells.models import pump_composite
from cells.models import pump_composite_adapter as adapter
from cells.operators import species_turnover as turnover
from cells.operators.contract import Operator
from cells.operators.species_turnover import LAW_ID as LAW_ID_TURNOVER
from cells.registry.models import get_model
from validation.tissue import secreted_species_fixtures as fx

getcontext().prec = 50
R_SI = Decimal("6.02214076e23") * Decimal("1.380649e-23")  # N_A k_B, exact (SI 2019).
H = 0.5  # s: a long half-step, so every fraction moved is O(1).
ROUTES = [
    ("produce", "cell_0", "production"),
    ("clear_cell", "cell_0", "clearance"),
    ("clear_a", "ecs_0", "clearance"),
    ("clear_b", "ecs_0", "clearance"),
]
RATES = np.array([2e-4, 0.3, 0.4, 0.6])  # fmol/s, then 1/s.
Routed = NamedTuple("Routed", [("turnover_rate", object)])  # The composite passes a NamedTuple.


def definition(routes=ROUTES, rates=RATES, **kwargs):
    raw = fx.secreting_cell(**kwargs)
    controls = [
        (r, None if node.startswith("ecs") else node, [(0.0, float(v))])
        for (r, node, _), v in zip(routes, rates, strict=True)
    ]
    return fx.with_turnover(raw, routes, controls)


@pytest.fixture(scope="module")
def bound():
    spec = parse_spec(definition())
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    s = list(spec.model.species_ids).index(fx.SPECIES)
    return spec, model, model.operators[0], state, p, s


def step(op, state, p, rates, h=H, view=None):
    control = SimpleNamespace(turnover_rate=np.asarray(rates))
    return op.half_step(state, h, control, p, xp=np, view=view)


VIEW_FIELDS = ("volume", "extracellular_volume", "active", "outside_active")  # Its current reads.
SWOLLEN = (1.7, 0.6)  # FR-65: the view's cell and outside volumes over the declared ones.


def viewed(p, *, scale=SWOLLEN, active=None, outside_active=None):
    """The reader view the composite passes where an operator changes a field turnover reads
    current (FR-65; pump_composite.reader_view): the volumes at `scale` times the declared ones,
    and the masks given (the declared ones by default)."""
    return pump_composite.reader_view_type(VIEW_FIELDS)(
        np.asarray(p.volume) * scale[0],
        np.asarray(p.extracellular_volume) * scale[1],
        np.asarray(p.active) if active is None else active,
        np.asarray(p.outside_active) if outside_active is None else outside_active,
    )


def amounts(state, p, s):
    return (
        np.asarray(p.amount_reference)[s] + state.amount_increment[s],
        np.asarray(p.extracellular_amount_reference)[s] + state.extracellular_amount_increment[s],
    )


def closed(n, production, clearance, h):
    """n e^{-kh} + (P/k)(1 - e^{-kh}) in 50 digits."""
    n, P, k, h = (Decimal(float(x)) for x in (n, production, clearance, h))
    if k == 0:
        return n + P * h
    decay = (-k * h).exp()
    return n * decay + P / k * (1 - decay)


def free_energy(n, volume):
    """RT n (ln(n/V) - 1) at 310 K, pJ (fmol x J/mol x 1e-3), in 50 digits."""
    n, volume = Decimal(float(n)), Decimal(float(volume))
    return Decimal("1e-3") * R_SI * Decimal("310") * n * ((n / volume).ln() - 1)


def test_the_half_step_is_the_closed_form_and_books_it(bound):
    _, _, op, state, p, s = bound
    new, ok = step(op, state, p, RATES)
    assert ok
    (cell0, node0), (cell1, node1) = amounts(state, p, s), amounts(new, p, s)
    expected_cell = closed(cell0[0], RATES[0], RATES[1], H)
    expected_node = closed(node0[1], 0.0, RATES[2] + RATES[3], H)  # Two routes add exactly.
    assert float(abs(Decimal(float(cell1[0])) - expected_cell) / expected_cell) < 1e-14
    assert float(abs(Decimal(float(node1[1])) - expected_node) / expected_node) < 1e-14
    assert new.turnover_produced_fmol[s, 0] == RATES[0] * H
    cleared = Decimal(float(cell0[0])) + Decimal(float(RATES[0] * H)) - expected_cell
    assert float(abs(Decimal(float(new.turnover_cleared_fmol[s, 0])) - cleared) / cleared) < 1e-12
    removed = Decimal(float(node0[1])) - expected_node
    booked = Decimal(float(new.turnover_outside_cleared_fmol[s, 1]))
    assert float(abs(booked - removed) / removed) < 1e-12
    assert node1[0] == node0[0]  # The held bath: never written.


@pytest.mark.parametrize("swollen", [False, True], ids=["declared", "view"])
def test_booked_work_is_the_exact_free_energy_change(bound, swollen):
    """The NumPy dG test of record for this law: W = G(n') - G(n) at each touched node.

    FR-65's row (view): given a reader view whose volumes differ from the declared V0 (the cell at
    1.7 V0, the node at 0.6 V0), the work is the exact change at the view's V. That equals @3's
    term at V0 plus the change of water's dilution term -RT N ln(V/V0) (its node_free_energy_pJ's
    expression), so the booking is the composite's stored free-energy change. The amounts and the
    material bookings are bitwise the viewless call's, since the update reads no volume. Planted
    (P1): the view dropped, the work booked at V0 misses the change at V by -RT dn ln(V/V0)."""
    _, _, op, state, p, s = bound
    view = viewed(p) if swollen else None
    new, _ = step(op, state, p, RATES, view=view)
    (cell0, node0), (cell1, node1) = amounts(state, p, s), amounts(new, p, s)
    volume, outside_volume = np.asarray(p.volume), np.asarray(p.extracellular_volume)
    scale = SWOLLEN if swollen else (1.0, 1.0)
    rt = Decimal("1e-3") * R_SI * Decimal("310")
    rows = (
        ("turnover_work_pJ", 0, cell0[0], cell1[0], volume[0], scale[0]),
        ("turnover_outside_work_pJ", 1, node0[1], node1[1], outside_volume[1], scale[1]),
    )
    for name, k, before, after, v0, factor in rows:
        v = v0 * factor
        booked = Decimal(float(getattr(new, name)[k]))
        exact = free_energy(after, v) - free_energy(before, v)
        assert float(abs(booked - exact) / abs(exact)) < 1e-11
        moved = Decimal(float(after)) - Decimal(float(before))
        dilution = -rt * moved * (Decimal(float(v)) / Decimal(float(v0))).ln()  # Water's term.
        at_v0 = free_energy(after, v0) - free_energy(before, v0)
        assert float(abs(booked - (at_v0 + dilution)) / abs(exact)) < 1e-11
        if swollen:  # P1: booked at V0, the miss is the dilution term, far above the tolerance.
            plain, _ = step(op, state, p, RATES)
            missed = Decimal(float(getattr(plain, name)[k])) - exact
            assert float(abs(missed - (-dilution)) / abs(dilution)) < 1e-9
            assert float(abs(missed) / abs(exact)) > 1e-3
    # Both nodes lose material below 1 mM, which raises G: these laws can run uphill (signed work).
    assert cell1[0] < cell0[0] and node1[1] < node0[1]
    assert new.turnover_work_pJ[0] > 0 and new.turnover_outside_work_pJ[1] > 0
    if swollen:  # The update reads no volume: amounts and material bookings bitwise.
        plain, _ = step(op, state, p, RATES)
        for name in (
            "amount_increment",
            "extracellular_amount_increment",
            "turnover_produced_fmol",
            "turnover_cleared_fmol",
            "turnover_outside_cleared_fmol",
        ):
            assert getattr(new, name).tobytes() == getattr(plain, name).tobytes(), name


def test_the_host_checks_close_at_the_species_scale(bound):
    spec, model, op, state, p, s = bound
    new, _ = step(op, state, p, RATES, h=5e-4)
    model.check_values(new, spec, steps=[1])  # Raises on any ledger, domain or energy failure.
    # Negative control: a misbooked accumulator, far below the ions' floor (1e-10 fmol) and far
    # above the species' (1e-20 fmol), fails the species' row of the local ledger alone.
    wrong = new._replace(
        turnover_cleared_fmol=new.turnover_cleared_fmol + 1e-16 * (np.arange(4) == s)[:, None]
    )
    local = model.balances(wrong, p)["local"]
    assert abs(local[s, 0]) > 1e-17 and np.max(np.abs(np.delete(local, s, axis=0))) == 0.0
    with pytest.raises(NumericalError, match="local"):
        model.check_values(wrong, spec, steps=[1])


def test_zero_rates_select_the_start_state_and_untouched_entries_stay_bitwise(bound):
    _, _, op, state, p, s = bound
    planted = state._replace(  # A signed zero in an ion row, which an added 0.0 would flip.
        amount_increment=state.amount_increment.copy()
    )
    planted.amount_increment[0, 0] = -0.0
    idle, ok = step(op, planted, p, np.zeros(4))
    assert ok
    for a, b in zip(idle, planted, strict=True):
        assert np.asarray(a).tobytes() == np.asarray(b).tobytes()
    only_node = np.array([0.0, 0.0, 0.4, 0.0])
    moved, ok = step(op, planted, p, only_node)
    assert ok and moved.amount_increment.tobytes() == planted.amount_increment.tobytes()
    assert moved.turnover_work_pJ.tobytes() == planted.turnover_work_pJ.tobytes()
    ions = np.arange(4) != s
    assert moved.extracellular_amount_increment[ions].tobytes() == (
        planted.extracellular_amount_increment[ions].tobytes()
    )
    assert (
        moved.extracellular_amount_increment[s, 1] != planted.extracellular_amount_increment[s, 1]
    )
    # FR-65: a view that closes the cell and the finite node (a pending daughter or retired parent,
    # a closed onset node), with positive rates on both: every field bitwise the start's, and the
    # held bath, where no route acts, keeps turnover's outside fields zero. Planted (P2): the view
    # with the declared masks, the half-step writes the closed slots' rows.
    outside = np.asarray(p.outside_active).copy()
    outside[1] = False
    closed = viewed(p, active=np.zeros_like(np.asarray(p.active)), outside_active=outside)
    untouched, ok = step(op, planted, p, RATES, view=closed)
    assert ok
    for a, b in zip(untouched, planted, strict=True):
        assert np.asarray(a).tobytes() == np.asarray(b).tobytes()
    written, _ = step(op, planted, p, RATES, view=viewed(p))
    assert written.amount_increment[s, 0] != planted.amount_increment[s, 0]
    assert (
        written.extracellular_amount_increment[s, 1] != planted.extracellular_amount_increment[s, 1]
    )
    assert not written.turnover_outside_cleared_fmol[:, 0].any()
    assert written.turnover_outside_work_pJ[0] == 0.0


class _Planted(Operator):
    """A planted rate-route source (B1′): a declared factor on the turnover's rates and its
    validity, or no route (factor None)."""

    LAW_ID = "tests.operator.planted_rate_route@1"
    SPLIT = True
    RK4 = "split"
    RATE_ROUTES = ((LAW_ID_TURNOVER, "turnover_rate"),)

    def __init__(self, factor, valid=True):
        self.factor, self.valid = factor, valid

    def half_step(self, state, h, control, p, *, xp):
        return state, None

    def rate_factors(self, state, p, target, field, *, xp):
        if self.factor is None:
            return None
        return np.asarray(self.factor), np.asarray(self.valid)


def test_a_routed_rate_is_the_scheduled_rate_times_its_factor_in_the_half_step(bound):
    """B1′ (docs/INVENTORY_COUPLING_DESIGN.md §2.1): beside a route source declared before it,
    the composite's half-step of the turnover multiplies its scheduled rates by the source's
    factors from the state the half-step receives. That equals, bit for bit, the half-step at the
    product rates. Planted: a source whose evaluation is invalid (an operating-range breach)
    refuses the half-step. A source with no route in the definition leaves the call unchanged."""
    _, model, op, state, p, _ = bound
    factor = np.array([0.5, 1.0, 0.25, 0.75])
    composite = pump_composite.Composition(model.inner, (_Planted(factor), op))
    assert composite.rate_routes == {op: ((composite.operators[0], "turnover_rate"),)}
    control = Routed(turnover_rate=RATES)
    routed, ok = composite._half_step(op, state, H, control, p, xp=np)
    expected, ok_expected = step(op, state, p, RATES * factor)
    assert bool(ok) and bool(ok_expected)
    for a, b in zip(routed, expected, strict=True):
        assert np.asarray(a).tobytes() == np.asarray(b).tobytes()
    breach = pump_composite.Composition(model.inner, (_Planted(factor, valid=False), op))
    _, ok = breach._half_step(op, state, H, control, p, xp=np)
    assert not bool(ok)
    idle = pump_composite.Composition(model.inner, (_Planted(None), op))
    unrouted, ok = idle._half_step(op, state, H, control, p, xp=np)
    plain, _ = step(op, state, p, RATES)
    assert bool(ok)
    for a, b in zip(unrouted, plain, strict=True):
        assert np.asarray(a).tobytes() == np.asarray(b).tobytes()


def test_a_pool_cleared_far_below_its_anchor_stalls_at_the_anchors_resolution(bound):
    """Amounts are anchor + increment, resolved to about one ulp of the anchor. A node cleared with
    no supply follows the closed form until kt is about ln(1/eps) = 36, then holds about one ulp
    of its anchor; it stays positive and is never refused (design §1.3 gives kt = 708, the smallest
    normal float, which applies to unanchored amounts only)."""
    _, _, op, state, p, s = bound
    rates = np.array([0.0, 0.0, 1.0, 0.0])  # k h = 0.5 per half-step at the node.
    anchor = float(np.asarray(p.extracellular_amount_reference)[s, 1])
    history = []
    for _ in range(120):  # kt = 60.
        state, ok = step(op, state, p, rates)
        assert ok
        history.append(amounts(state, p, s)[1][1])
    history = np.asarray(history)
    kt = 0.5 * np.arange(1, 121)
    exact = anchor * np.exp(-kt)
    resolved = exact > 1e3 * np.spacing(anchor)
    assert np.all(np.abs(history[resolved] - exact[resolved]) <= 8 * np.spacing(anchor))
    assert np.all(history > 0) and history[-1] >= 0.5 * np.spacing(anchor)
    assert history[-1] <= 4 * np.spacing(anchor) and history[-1] > 1e6 * exact[-1]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda raw: raw["model"]["operators"][0]["species"][0].update(id="Na"),
            "neutral species only",
        ),
        (
            lambda raw: raw["model"]["operators"][0]["routes"][0].update(node="ecs_0"),
            "production is a cell",
        ),
        (lambda raw: raw["model"]["operators"][0]["routes"][2].update(node="bath"), "held bath"),
        (
            lambda raw: raw["model"]["operators"][0]["routes"][0].update(species="X"),
            "not a listed species",
        ),
        (
            lambda raw: raw["model"]["operators"][0]["routes"][0].update(kind="decay"),
            "kind is one of",
        ),
        (
            lambda raw: raw["experiment"]["turnover_controls"][1]["schedule"][0].update(rate=-1.0),
            "rate >= 0",
        ),
        (
            lambda raw: raw["experiment"]["turnover_controls"][1]["schedule"].append(
                dict(time=0.0015, rate=0.1)
            ),
            "on the clock's grid",
        ),
        (
            lambda raw: raw["experiment"]["turnover_controls"][1]["schedule"].append(
                dict(time=1.0, rate=0.1)
            ),
            "outside the horizon",
        ),
        (
            lambda raw: raw["experiment"]["turnover_controls"][1]["schedule"][0].update(time=0.001),
            "starts at time 0",
        ),
        (lambda raw: raw["experiment"]["turnover_controls"].pop(0), "founder carrier cell_0"),
        (
            lambda raw: raw["experiment"]["turnover_controls"][2].update(carrier_id="cell_0"),
            "scheduled per node",
        ),
        (
            lambda raw: raw["experiment"]["turnover_controls"][1].update(carrier_id=None),
            "scheduled per carrier",
        ),
        (
            lambda raw: raw["experiment"]["turnover_controls"].append(
                dict(
                    route_id="clear_cell", carrier_id="ghost", schedule=[dict(time=0.001, rate=0.1)]
                )
            ),
            "never occupies its slot",
        ),
    ],
)
def test_definition_refusals(change, message):
    raw = definition()
    change(raw)
    with pytest.raises(ConfigError, match=message):
        parse_spec(raw)


# ------------------------------------------------------------ the occupant rule's tables (FR-65)


def test_the_occupant_tables_follow_the_partition_s_carriers_and_refuse_their_gaps(monkeypatch):
    """FR-65 §3.4 (D150 §5.2), host side, about 0.3 s, no world compiled. On S5's divided world
    (cell_0 into d1 and d2 at 2 ms, carriers c1 and c2), routes on all three slots: a daughter's
    rate is zero before its birth and its own after, and the parent's is its own until its
    retirement and zero after. Planted (P3): a table without the daughter's leading zero, and one
    that keeps the parent's rate, each fails the row's check. Refused, with their reasons: a
    daughter keyed by its slot (P4), a daughter without its own schedule or with one that starts
    before its birth, a reader with no idle value, and a slot two operators fill. Without a
    lifecycle operator every slot holds its founder, replacement@1's slots are its events' (the
    occupants of today's rule), and replacement@2 fills none. An outside rate before its node's
    onset (insertion@2's) is refused, at the onset admitted."""
    from cells.operators import OPERATORS
    from cells.operators import species_common as common
    from cells.operators.contract import Occupant
    from tests import membrane_insertion_fixtures as mfx
    from tests import partition_fixtures as pfx

    spec, birth = parse_spec(pfx.divided()), pfx.EVENT
    routes = tuple(
        turnover.Route(f"p_{c}", fx.SPECIES, c, "production", c) for c in ("cell_0", "d1", "d2")
    )
    rates = {"cell_0": 1e-6, "c1": 2e-6, "c2": 3e-6}
    keys = (("p_cell_0", "cell_0", 0.0), ("p_d1", "c1", birth), ("p_d2", "c2", birth))

    def tables(keys=keys, idle=turnover.IDLE):
        schedules = tuple(
            common.RouteSchedule(r, c, ((t, (rates.get(c, 5e-6),)),)) for r, c, t in keys
        )
        return common.route_tables(spec, routes, schedules, (), LAW_ID_TURNOVER, idle=idle)

    times = [0.0, 0.001, birth, 0.003]
    expected = np.array([[1e-6, 0, 0], [1e-6, 0, 0], [0, 2e-6, 3e-6], [0, 2e-6, 3e-6]])

    def follows(tables):
        return np.array_equal(common.control_arrays(tables, times, 1)[..., 0], expected)

    built = tables()
    assert follows(built)
    assert not follows([built[0], built[1][1:], built[2]])  # P3: the leading zero dropped.
    assert not follows([built[0][:-1], built[1], built[2]])  # P3: the parent's rate kept.
    lives = common.occupants(spec)
    assert lives["d1"] == (Occupant("c1", birth, math.inf, "daughter", None, None),)
    assert lives["cell_0"] == (Occupant("cell_0", 0.0, birth, "founder", None, None),)
    for keyed, words in (
        ((*keys, ("p_d1", "d1", 0.0)), "names carrier d1, which never occupies its slot"),
        ((keys[0], ("p_d1", "d1", 0.0), keys[2]), "carrier c1, a daughter born in slot d1"),
        ((keys[0], ("p_d1", "c1", 0.001), keys[2]), "starts at its birth, 0.002 s"),
    ):
        with pytest.raises(ConfigError, match=re.escape(words)):
            tables(keyed)
    with pytest.raises(ConfigError, match="gives no idle rate for an empty slot"):
        tables(idle=None)
    # Without a lifecycle operator, founders alone; with replacement@1, its events' carriers.
    plain = parse_spec(definition())
    assert common.occupants(plain) == {
        "cell_0": (Occupant("cell_0", 0.0, math.inf, "founder", None, None),)
    }
    raw = fx.secreting_cell()
    raw = fx.with_replacement(raw, [fx.template(raw, "cell_0", "T")], [(0.002, "cell_0", "T", "n")])
    replaced = parse_spec(
        fx.with_turnover(
            raw,
            [("p", "cell_0", "production")],
            [("p", "cell_0", [(0.0, 1e-6)])],
            templates=[("T", {"p": 2e-6})],
        )
    )
    assert common.occupants(replaced)["cell_0"] == (
        Occupant("cell_0", 0.0, 0.002, "founder", None, None),
        Occupant("n", 0.002, math.inf, "isolated_template", "T", None),
    )
    # A slot two operators fill is refused by name; replacement@2 fills none (its readers are
    # refused beside it by the shared volume rule), so its slots keep their founders.
    class Filler(Operator):
        LAW_ID = "tests.operator.planted_filler@1"

        def slot_occupants(self, spec, declaration, schedule):
            return {"d1": (Occupant("x", 0.001, math.inf, "daughter", None, None),)}

    entries = common.composite_spec.entries(spec)
    monkeypatch.setattr(
        common.composite_spec, "entries", lambda s: (*entries, (Filler(), None, None))
    )
    with pytest.raises(ConfigError, match="decided by both"):
        common.occupants(spec)
    over_water = OPERATORS["cells.operator.scheduled_cell_replacement@2"]
    monkeypatch.setattr(common.composite_spec, "entries", lambda s: ((over_water, None, None),))
    assert common.occupants(spec) == common.occupants(plain) | {
        c.id: (Occupant(c.id, 0.0, math.inf, "founder", None, None),) for c in spec.model.cells
    }
    monkeypatch.undo()
    # D150 §5.3: an outside route before its node's onset (insertion@2's furrow opens the cleft).
    raw = mfx.with_operators(mfx.cleft_cell(), mfx.furrow_insertion(onset=0.002))
    raw["model"]["operators"][-1]["law"] = "cells.operator.scheduled_membrane_insertion@2"
    cleft = parse_spec(raw)
    assert common.node_onsets(cleft) == {"cleft": 0.002}
    route = (turnover.Route("c", fx.SPECIES, "cleft", "clearance", None),)
    common.check_node_onsets(cleft, route, [((0.0, (0.0,)), (0.002, (0.5,)))], LAW_ID_TURNOVER)
    with pytest.raises(ConfigError, match=r"before the node's onset at 0\.002 s"):
        common.check_node_onsets(cleft, route, [((0.0, (0.5,)),)], LAW_ID_TURNOVER)


# ------------------------------------------------------------ beside the changers it reads (FR-65)

WATER = "cells.operator.ideal_osmosis_linear_compliance_water@1"
LABELS = "cells.operator.neutral_arrival_labels@1"


def _s(raw):
    from cells.registry.inventory_species import add_inventory_species

    return add_inventory_species(
        raw, fx.SPECIES, trace_mM=fx.TRACE_mM, diffusivity_m2_per_s=fx.D_S, floor_fmol=fx.FLOOR_FMOL
    )


def _in_cell(raw, rate=1e-6):
    """Turnover making S in the world's first cell, from its founder."""
    cell = raw["model"]["cells"][0]["id"]
    return fx.with_turnover(_s(raw), [("p", cell, "production")], [("p", cell, [(0.0, rate)])])


def _first(raw, law):
    """raw with `law`'s block moved to the front of the operator list."""
    blocks = raw["model"]["operators"]
    raw["model"]["operators"] = [b for b in blocks if b["law"] == law] + [
        b for b in blocks if b["law"] != law
    ]
    return raw


def _labelled(raw):
    """raw with FR-42's label owner on S, every node at its base label."""
    nodes = [c["id"] for c in raw["model"]["cells"]] + [
        c["id"] for c in raw["model"]["extracellular"] if not c.get("reservoir", False)
    ]
    raw["model"]["operators"].append(
        dict(
            law=LABELS,
            species=[
                dict(
                    id=fx.SPECIES,
                    labels=["base", "t1"],
                    initial=[dict(node=n, shares={"base": 1.0}) for n in nodes],
                )
            ],
        )
    )
    raw["experiment"]["label_arrivals"] = [
        dict(species=fx.SPECIES, schedule=[dict(time=0.0, label="base")])
    ]
    return raw


def _bridged(s_crosses):
    from tests import partition_fixtures as pfx

    raw = _s(pfx.cleft_divided(bridge=("linear", 0.001)))
    if s_crosses:  # S given the cytoplasmic diffusivity, and the junction permeability, it implies.
        for junction in raw["model"]["junctions"]:
            junction["permeability_m_per_s"][fx.SPECIES] = 1e-10
        for entry in raw["model"]["operators"]:
            for bridge in entry.get("bridges", []):
                bridge["cytoplasmic_diffusivity_m2_per_s"][fx.SPECIES] = 1e-10
    return fx.with_turnover(
        raw, [("p", "cell_0", "production")], [("p", "cell_0", [(0.0, 1e-6)])]
    )


def _replaced_over_water():
    """Replacement@2 over water, replacing cell_1, with turnover in cell_0, whose occupant tables
    stand (its founder throughout): the shared volume rule refuses it by name."""
    from tests import replacement_water_fixtures as rwfx

    raw = rwfx.sheet(end=0.02)
    return _in_cell(rwfx.over_water(raw, rwfx.templates(raw), ((0.01, "cell_1", "h", "n1"),)))


def _companion(kind):
    from validation.tissue import bath_schedule_fixtures as bfx
    from validation.tissue import pump_water_fixtures as wfx

    if kind == "symport":
        world = wfx.with_symport(
            wfx.with_water(wfx.heredity_cell("D", end_time=0.1), pf_m_s=5e-4), steepness=0.12
        )
        from cells.definitions import pump_composite_spec as cs

        return _in_cell(cs.frozen_definition(world))
    return _in_cell(bfx.water_world({"NaM": -10.0, "KM": 10.0}))


def _worlds():
    """{name: (builder, refusal words or None for admitted)}: §3.6's newly parsing sets and their
    neighbours that stay refused (docs/TURNOVER_CHANGING_VOLUME_DESIGN.md)."""
    from tests import membrane_insertion_fixtures as mfx
    from tests import partition_fixtures as pfx
    from validation.tissue import shared_inventory_fixtures as sif

    swelling = lambda: sif.swelling_turnover(dt=0.01, end=0.1, every=0.05)  # noqa: E731
    cleft = mfx.cleft_turnover
    at_cleft = ("c", "cleft", "clearance")
    in_cell = ("p", "cell_0", "production", [(0.0, 1e-6)])
    order = "reads the view {} at stage split before {} changes it there"
    return {
        "water": (swelling, None),
        "water after it": (
            lambda: _first(swelling(), fx.TURNOVER),
            order.format("volume", WATER),
        ),
        "the symport beside water": (lambda: _companion("symport"), None),
        "the bath schedule beside water": (lambda: _companion("bath"), None),
        "replacement@2 over water": (
            _replaced_over_water,
            "cells.operator.scheduled_cell_replacement@2 changes the volumes it reads",
        ),
        "the partition, daughters keyed by carriers": (
            lambda: pfx.with_turnover(pfx.divided()),
            None,
        ),
        "the partition, daughters keyed by slots (P4)": (
            lambda: pfx.with_turnover(pfx.divided(), keyed="slots"),
            "needs a schedule for carrier c1, a daughter born in slot d1",
        ),
        "insertion@2, clearance at the cleft from its onset": (
            lambda: cleft(2, routes=[(*at_cleft, [(0.0, 0.0), (0.002, 0.5)])]),
            None,
        ),
        "insertion@2, clearance at the cleft before its onset": (
            lambda: cleft(2, routes=[(*at_cleft, [(0.0, 0.5)])]),
            "before the node's onset at 0.002 s",
        ),
        "insertion@2 after it": (
            lambda: _first(cleft(2, routes=[in_cell]), fx.TURNOVER),
            order.format("outside_active", mfx.INSERTION_2),
        ),
        "insertion@1, cell routes": (lambda: cleft(1, routes=[in_cell]), None),
        "insertion@1, clearance at the cleft (the anchor guard)": (
            lambda: cleft(1, routes=[(*at_cleft, [(0.0, 0.5)])]),
            f"{mfx.INSERTION} changes the outside anchors at cleft, where route c clears",
        ),
        "lumen@1 at a node it does not read": (
            lambda: cleft(1, lumen=True, routes=[in_cell]),
            None,
        ),
        "lumen@1 at the node it clears (P5)": (
            lambda: cleft(1, lumen=True, routes=[(*at_cleft, [(0.0, 0.5)])]),
            "changes the volumes it reads (the outside volume at cleft)",
        ),
        "lumen@2 at a node it does not read": (
            lambda: cleft(2, lumen=True, routes=[in_cell]),
            None,
        ),
        "lumen@2 at the node it clears (P5)": (
            lambda: cleft(2, lumen=True, routes=[(*at_cleft, [(0.0, 0.0), (0.002, 0.5)])]),
            "changes the volumes it reads (the outside volume at cleft)",
        ),
        "the furrow world with its lumen, daughters keyed by carriers": (
            lambda: pfx.with_turnover(pfx.cleft_divided()),
            None,
        ),
        "the furrow world, the lumen after it": (
            lambda: _first(pfx.with_turnover(pfx.cleft_divided()), fx.TURNOVER),
            order.format("extracellular_volume", pfx.LUMEN2),
        ),
        "the furrow world with an injection": (
            lambda: pfx.with_turnover(pfx.cleft_divided(injection=1e-13)),
            None,
        ),
        "the bridged furrow world, S impermeant on the bridge": (lambda: _bridged(False), None),
        "the bridged furrow world, S on the bridge": (
            lambda: _bridged(True),
            "'S' has a route through junction bridge_1",
        ),
        "labels beside insertion@1": (
            lambda: _labelled(cleft(1, routes=[in_cell])),
            "its view changes species amounts",
        ),
        "labels beside insertion@2": (
            lambda: _labelled(cleft(2, routes=[in_cell])),
            "it closes or retires slots",
        ),
        "labels beside a lumen": (
            lambda: _labelled(cleft(2, lumen=True, routes=[in_cell])),
            "it writes species amounts without reporting its one-way moves",
        ),
        "A1 without the coupling, beside water": (lambda: sif.swelling_a1(end=60.0), None),
        "A1 with the coupling, beside water": (
            lambda: sif.swelling_a1(coupling=True, end=60.0),
            None,
        ),
    }


WORLDS = _worlds()


@pytest.mark.parametrize("name", list(WORLDS))
def test_beside_the_changers_it_reads_by_name(name, monkeypatch):
    """FR-65 §3.6, host side, about 0.1 s a world (parse only, nothing compiled): turnover beside
    the changers of the volumes and masks it reads current. Admitted: water first, with the
    symport or the bath schedule beside it; the partition, daughters keyed by their carriers;
    insertion@2 with clearance at the cleft from its onset; insertion@1 with cell routes; a lumen
    at a node it does not read; S5's furrow world with its lumen, with an injection, and with a
    bridge S does not cross; A1 with and without the coupling (whose own reads are current since
    FR-65's coupling step). Refused, in the engine's words: a changer
    declared after it (C2's order rule), replacement@2 and a lumen at a node it clears (the shared
    volume rule; P5), a daughter keyed by its slot (P4), a rate before its node's onset, insertion@1
    at a node it clears (the anchor guard), S on a bridge, and labels beside insertion or a lumen
    (the label owner). Planted: today's declarations (the shared static-tissue list) put back,
    every admitted world is refused."""
    from cells.models import pump_composite as composite
    from cells.operators import species_common as common

    build, words = WORLDS[name]
    if words is not None:
        with pytest.raises(ConfigError, match=re.escape(words)):
            parse_spec(build())
        return
    parse_spec(build())
    cls = turnover.ScheduledSpeciesTurnover
    monkeypatch.setattr(cls, "CONFLICTS_VIEW", common.CONFLICTS_VIEW)
    monkeypatch.setattr(cls, "VIEW_READS", ())
    monkeypatch.setattr(cls, "SCOPED_READS", {})
    composite._implementation.cache_clear()  # Compositions are cached per operator list.
    today = re.escape(LAW_ID_TURNOVER) + r" reads \w+ as declared"
    try:
        with pytest.raises(ConfigError, match=today):
            parse_spec(build())
    finally:
        monkeypatch.undo()
        composite._implementation.cache_clear()


# ------------------------------------------------------------ the stored change at stiff rates

EPS = np.finfo(np.float64).eps
TEMPERATURE_K = 310.0  # free_energy's.


@pytest.fixture(scope="module")
def x64():
    jax.config.update("jax_enable_x64", True)


def landed(increment, anchor, volume, mask, production, clearance, h, temperature, *, xp):
    """The node update's increment, bookings and work as they landed (transcribed): the moved
    amount produced - cleared at every kh."""
    touched = mask[None, :] & ((production > 0) | (clearance > 0))
    n = xp.where(mask[None, :], anchor + increment, 1.0)
    produced, cleared = turnover.produced_cleared(n, production, clearance, h, xp=xp)
    moved = xp.where(touched, produced - cleared, 0.0)
    work = adapter.species_chemical_free_energy_pJ(n, moved, volume, temperature, xp=xp)
    return (
        xp.where(touched, increment + moved, increment),
        xp.where(touched, produced, 0.0),
        xp.where(touched, cleared, 0.0),
        xp.where(touched, work, 0.0),
    )


def update(args, compiled, function=None):
    """Increment, produced, cleared and work stacked, from the node update (or `function`), in
    NumPy or compiled afresh (a new function, so a plant is traced)."""
    f = function or turnover._node_update
    if compiled:
        out = jax.jit(lambda *a: f(*a, xp=jnp)[:4])(*args)
    else:
        with np.errstate(all="ignore"):
            out = f(*args, xp=np)[:4]
    return np.stack([np.asarray(v, dtype=float) for v in out])


def nodes(low, high, seed, *, ordinary=False, rows=3, columns=48):
    """Random nodes at half-step exponents kh log-uniform in [low, high] (h = 0.37 s, the last
    column masked). Stiff states put the equilibrium P/k near the pool; ordinary states also hold
    entries with production or clearance alone."""
    rng = np.random.default_rng(seed)
    shape, h = (rows, columns), 0.37
    anchor = 10 ** rng.uniform(-3, 1, shape)
    increment = anchor * rng.uniform(-0.5, 0.5, shape)
    clearance = 10 ** rng.uniform(np.log10(low), np.log10(high), shape) / h
    if ordinary:
        production = 10 ** rng.uniform(-4, 1, shape) * (rng.uniform(size=shape) > 0.2)
        clearance = clearance * (rng.uniform(size=shape) > 0.2)
    else:
        production = clearance * (anchor + increment) * rng.uniform(0.5, 2, shape)
    mask, volume = np.arange(columns) < columns - 1, 10 ** rng.uniform(-1, 1, columns)
    return increment, anchor, volume, mask, production, clearance, h, TEMPERATURE_K


def accuracy(args, out):
    """The largest stored-amount error against the 50-digit closed form, in eps of the entry's
    scale, and the largest |change - (produced - cleared)| in eps of the bookings and increments."""
    increment, anchor, _, mask, production, clearance, h, _ = args
    new, produced, cleared = out[0], out[1], out[2]
    stored_error, balance = 0.0, 0.0
    for i, j in np.argwhere(mask[None, :] & (clearance > 0)):
        exact = closed(anchor[i, j] + increment[i, j], production[i, j], clearance[i, j], h)
        scale = max(anchor[i, j], abs(new[i, j]), float(exact), production[i, j] / clearance[i, j])
        error = abs(Decimal(float(anchor[i, j] + new[i, j])) - exact)
        stored_error = max(stored_error, float(error) / (EPS * scale))
        size = produced[i, j] + cleared[i, j] + abs(increment[i, j]) + abs(new[i, j])
        change = new[i, j] - increment[i, j]
        balance = max(balance, abs(change - (produced[i, j] - cleared[i, j])) / (EPS * size))
    return stored_error, balance


def stiff_failures(row):
    """The claims a row breaks, by name, with the operator as it stands."""
    failures = []
    if row == "lean_endpoint":
        # The Lean case: 1 fmol in 1 pL, k = 2^54 /s, P = 2k, two half-steps of 0.5 s. The exact
        # pool, 2 - e^{-k} fmol, is 2.0 in float64; the work is G(2) - G(1).
        expected = free_energy(2.0, 1.0) - free_energy(1.0, 1.0)
        for compiled in (False, True):
            increment, work = np.zeros((1, 1)), 0.0
            for _ in range(2):
                rates = np.full((1, 1), 2.0**55), np.full((1, 1), 2.0**54)
                args = (increment, np.ones((1, 1)), np.ones(1), np.ones(1, bool), *rates, 0.5)
                out = update((*args, TEMPERATURE_K), compiled)
                increment, work = out[0], work + out[3, 0, 0]
            name = "compiled" if compiled else "numpy"
            if 1.0 + increment[0, 0] != 2.0:
                failures.append(f"stored {1.0 + increment[0, 0]!r} fmol ({name})")
            if not abs(Decimal(float(work)) - expected) <= Decimal("1e-14") * expected:
                failures.append(f"work {work!r} pJ against {float(expected)!r} ({name})")
    elif row == "stiff_accuracy":
        # kh from 36 (f = 1 in float64) to 1e15: the stored pool within 8 eps of its scale and the
        # change within 4 eps of the gross bookings, in NumPy and compiled.
        args = nodes(36.0, 1e15, 11)
        for compiled in (False, True):
            stored_error, balance = accuracy(args, update(args, compiled))
            if stored_error > 8 or balance > 4:
                failures.append(f"errors {stored_error:.3g}, {balance:.3g} eps ({compiled=})")
    elif row == "ordinary_bits":
        # kh from 1e-6 to 1, with production or clearance alone in some entries: the landed bits.
        for seed in (13, 17):
            args = nodes(1e-6, 1.0, seed, ordinary=True)
            for compiled in (False, True):
                if update(args, compiled).tobytes() != update(args, compiled, landed).tobytes():
                    failures.append(f"not the landed bits (seed {seed}, {compiled=})")
    elif row == "threshold_edge":
        # At kh from 0.5 to 1, the landed bits; just above 1, where the net form's factor f is far
        # from 1, the stored pool and the balance as at stiff rates (NumPy).
        below = nodes(0.5, 1.0, 19)
        if update(below, False).tobytes() != update(below, False, landed).tobytes():
            failures.append("not the landed bits below 1")
        stored_error, balance = accuracy(above := nodes(1.0001, 8.0, 23), update(above, False))
        if stored_error > 8 or balance > 4:
            failures.append(f"errors above 1: {stored_error:.3g}, {balance:.3g} eps")
    return failures


@contextlib.contextmanager
def replaced(name, value):
    """An attribute of the operator's module replaced for the block (a plant)."""
    saved = getattr(turnover, name)
    setattr(turnover, name, value)
    try:
        yield
    finally:
        setattr(turnover, name, saved)


def factor_dropped(n, production, clearance, h, *, xp):  # Planted: (P/k - n) without f.
    return production / clearance - n


STIFF = (  # Each plant a context: the threshold moved, or the net form's factor dropped.
    pytest.param("lean_endpoint", lambda: replaced("NET_EXPONENT", np.inf), id="lean_endpoint"),
    pytest.param("stiff_accuracy", lambda: replaced("NET_EXPONENT", np.inf), id="stiff_accuracy"),
    pytest.param("ordinary_bits", lambda: replaced("NET_EXPONENT", 0.0), id="ordinary_bits"),
    pytest.param(
        "threshold_edge", lambda: replaced("net_change", factor_dropped), id="threshold_edge"
    ),
)


@pytest.mark.parametrize("row, plant", STIFF)
def test_the_stored_change_is_net_where_kh_exceeds_one_and_each_plant_breaks_it(x64, row, plant):
    assert stiff_failures(row) == []
    with plant():
        assert stiff_failures(row) != []
