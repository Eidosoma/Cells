"""Tier-1 smoke test of scheduled_species_turnover@1 (secreted-species design §2.2).

The operator's half-step on a bound quiescent world, in NumPy (no compile): the closed form
n' = n e^{-kh} + (P/k)(1 - e^{-kh}) at O(1) fractions, the bookings, the booked work against the
exact free-energy change written out independently (Decimal, 50 digits: the NumPy dG test of record
for this law), the host checks closing at the species' own scale with a negative control, the start
state selected bitwise at zero rate, untouched rows and nodes bitwise, the anchored-amount limit of
a pool cleared far below its anchor, and the definition refusals with their messages.
"""

from decimal import Decimal, getcontext
from types import SimpleNamespace

import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError, parse_spec
from cells.models.registry import get_model
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
            "exact multiple of dt",
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
