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


def step(op, state, p, rates, h=H):
    return op.half_step(state, h, SimpleNamespace(turnover_rate=np.asarray(rates)), p, xp=np)


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


def test_booked_work_is_the_exact_free_energy_change(bound):
    """The NumPy dG test of record for this law: W = G(n') - G(n) at each touched node."""
    _, _, op, state, p, s = bound
    new, _ = step(op, state, p, RATES)
    (cell0, node0), (cell1, node1) = amounts(state, p, s), amounts(new, p, s)
    volume, outside_volume = np.asarray(p.volume), np.asarray(p.extracellular_volume)
    for booked, before, after, v in (
        (new.turnover_work_pJ[0], cell0[0], cell1[0], volume[0]),
        (new.turnover_outside_work_pJ[1], node0[1], node1[1], outside_volume[1]),
    ):
        exact = free_energy(after, v) - free_energy(before, v)
        assert float(abs(Decimal(float(booked)) - exact) / abs(exact)) < 1e-11
    # Both nodes lose material below 1 mM, which raises G: these laws can run uphill (signed work).
    assert cell1[0] < cell0[0] and node1[1] < node0[1]
    assert new.turnover_work_pJ[0] > 0 and new.turnover_outside_work_pJ[1] > 0


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
