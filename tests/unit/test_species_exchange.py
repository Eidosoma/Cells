"""Tier-1 smoke test of scheduled_species_exchange@1 (secreted-species design §2.3).

The operator's half-step on a bound quiescent world of two cells and two finite nodes, in NumPy (no
compile): each rate law against its closed form at O(1) fractions (the saturable one against its
implicit closed form), first-order exports from one cell combined exactly and shared by rate, the
palindromic stages second order against the exact solution of a secretion-uptake pair, the booked
work against the exact free-energy change written out independently (Decimal, 50 digits: the NumPy
dG test of record per law), the host checks closing, the start state selected bitwise at zero rate,
the refusals of a supply shortfall and of a failed saturable solve, and the definition refusals with
their messages.
"""

from decimal import Decimal, getcontext
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.linalg import expm

from cells.core.specs import ConfigError, parse_spec
from cells.models.registry import get_model
from validation.tissue import secreted_species_fixtures as fx

getcontext().prec = 50
R_SI = Decimal("6.02214076e23") * Decimal("1.380649e-23")  # N_A k_B, exact (SI 2019).
H = 0.5
ROUTES = [
    ("burst", "contact_0", "export", "flux"),  # cell_0 -> ecs_0
    ("secrete_a", "contact_0", "export", "first_order"),  # cell_0 -> ecs_0
    ("secrete_b", "contact_2", "export", "first_order"),  # cell_0 -> ecs_1
    ("take_up", "contact_1", "import", "first_order"),  # ecs_0 -> cell_1
    ("sink_1", "contact_1", "import", "saturable"),  # ecs_0 -> cell_1, rank 0
    ("sink_0", "contact_0", "import", "saturable"),  # ecs_0 -> cell_0, rank 1
]
CARRIERS = ["cell_0", "cell_0", "cell_0", "cell_1", "cell_1", "cell_0"]
PROFILE = dict(cell_0=1e-3, cell_1=2e-4, ecs_0=5e-4, ecs_1=3e-4)
KM = 5e-4  # mM
ZERO = np.zeros(6)


def definition(**kwargs):
    raw = fx.world(
        cells=(("cell_0", 1.0), ("cell_1", 1.0)),
        nodes=(("ecs_0", 1.0), ("ecs_1", 1.0)),
        contacts=(
            ("contact_0", "cell_0", "ecs_0"),
            ("contact_1", "cell_1", "ecs_0"),
            ("contact_2", "cell_0", "ecs_1"),
        ),
        faces=(("face_0", "ecs_0", "bath", 1e-10, 1e-5), ("face_1", "ecs_1", "bath", 1e-10, 1e-5)),
        concentrations_mM=kwargs.pop("concentrations_mM", PROFILE),
        **kwargs,
    )
    controls = [
        (r[0], c, [(0.0, 0.1, KM)] if r[3] == "saturable" else [(0.0, 0.1)])
        for r, c in zip(ROUTES, CARRIERS, strict=True)
    ]
    return fx.with_exchange(raw, ROUTES, controls)


@pytest.fixture(scope="module")
def bound():
    spec = parse_spec(definition())
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    s = list(spec.model.species_ids).index(fx.SPECIES)
    return spec, model, model.operators[0], state, p, s


def step(op, state, p, rates, h=H, km=KM):
    control = SimpleNamespace(
        exchange_rate=np.asarray(rates, dtype=float),
        exchange_saturation_mM=np.array([0.0, 0.0, 0.0, 0.0, km, km]),
    )
    return op.half_step(state, h, control, p, xp=np)


def pools(state, p, s):
    """(cell_0, cell_1, ecs_0, ecs_1) amounts of S, fmol."""
    cells = np.asarray(p.amount_reference)[s] + state.amount_increment[s]
    outside = (
        np.asarray(p.extracellular_amount_reference)[s] + state.extracellular_amount_increment[s]
    )
    return np.array([cells[0], cells[1], outside[1], outside[2]])


def free_energy(n, volume=1.0):
    n, volume = Decimal(float(n)), Decimal(float(volume))
    return Decimal("1e-3") * R_SI * Decimal("310") * n * ((n / volume).ln() - 1)


def exact_work(before, after):
    return sum(free_energy(b) - free_energy(a) for a, b in zip(before, after, strict=True))


def one(index, value):
    rates = ZERO.copy()
    rates[index] = value
    return rates


def test_each_law_is_its_closed_form_and_books_its_free_energy_change(bound):
    _, _, op, state, p, s = bound
    n0 = pools(state, p, s)
    kappa = 1e-4 * 1e-11 * 1e15 / 1.0  # k_u A / V_o = 1 / s.
    cases = (
        (0, 1e-7, 1e-7 * H),  # Flux: J h.
        (1, 0.8, n0[0] * -np.expm1(-0.8 * H)),  # First-order export.
        (3, 1e-4, n0[2] * -np.expm1(-kappa * H)),  # First-order import (k_u in m/s).
    )
    for index, rate, moved in cases:
        new, ok = step(op, state, p, one(index, rate))
        assert ok
        booked = new.exchange_moved_fmol[index]
        assert abs(abs(booked) - moved) <= 1e-14 * moved, index
        assert np.count_nonzero(new.exchange_moved_fmol) == 1
        work = Decimal(float(new.exchange_work_pJ[index]))
        exact = exact_work(n0, pools(new, p, s))
        assert float(abs(work - exact) / abs(exact)) < 1e-10, index
    # Saturable: b ln(n / n') + (n - n') = a h, with a = A V_max and b = K_M V_o.
    vmax = 1e8  # fmol s^-1 m^-2: a = 1e-3 fmol/s against a pool of 5e-4 fmol.
    new, ok = step(op, state, p, one(4, vmax))
    assert ok
    n, after = n0[2], pools(new, p, s)[2]
    a, b = 1e-11 * vmax, KM * 1.0
    residual = b * np.log(n / after) + (n - after) - a * H
    assert abs(residual) <= 1e-12 * a * H and 0.3 < (n - after) / n < 0.9
    exact = exact_work(n0, pools(new, p, s))
    assert float(abs(Decimal(float(new.exchange_work_pJ[4])) - exact) / abs(exact)) < 1e-10


def test_first_order_exports_from_one_cell_combine_exactly_and_share_by_rate(bound):
    _, _, op, state, p, s = bound
    n0 = pools(state, p, s)[0]
    rates = ZERO.copy()
    rates[1], rates[2] = 0.8, 1.2
    new, ok = step(op, state, p, rates)
    assert ok
    total = n0 * -np.expm1(-(0.8 + 1.2) * H)
    a, b = new.exchange_moved_fmol[1], new.exchange_moved_fmol[2]
    assert abs(a + b - total) <= 1e-15 * total
    assert a / (a + b) == pytest.approx(0.4, rel=1e-14)
    assert pools(new, p, s)[0] == pytest.approx(n0 * np.exp(-2.0 * H), rel=1e-13)


def test_the_palindrome_is_second_order_for_a_secretion_uptake_pair(bound):
    """Secretion into ecs_0 and uptake from it do not commute; the half-step is a symmetric
    composition of exact stages, so its local error falls as h^3 (ratio 8 per halving)."""
    _, _, op, state, p, s = bound
    k, kappa = 1.0, 2.0
    rates = ZERO.copy()
    rates[1], rates[3] = k, kappa * 1e-4  # k_u gives kappa = 1e4 k_u per second here.
    n0 = pools(state, p, s)[[0, 2, 1]]  # cell_0 -> ecs_0 -> cell_1.
    matrix = np.array([[-k, 0.0, 0.0], [k, -kappa, 0.0], [0.0, kappa, 0.0]])
    errors = []
    for h in (0.1, 0.05, 0.025):
        new, ok = step(op, state, p, rates, h=h)
        assert ok
        exact = expm(matrix * h) @ n0
        errors.append(np.max(np.abs(pools(new, p, s)[[0, 2, 1]] - exact)))
    assert 7.0 < errors[0] / errors[1] < 9.0 and 7.0 < errors[1] / errors[2] < 9.0


def test_the_host_checks_close(bound):
    spec, model, op, state, p, s = bound
    rates = np.array([1e-9, 0.2, 0.3, 1e-5, 1e6, 1e6])
    new, ok = step(op, state, p, rates, h=5e-4)
    assert ok
    model.check_values(new, spec, steps=[1])
    assert np.all(new.exchange_moved_fmol[:3] > 0) and np.all(new.exchange_moved_fmol[3:] < 0)


def test_zero_rates_select_the_start_state(bound):
    _, _, op, state, p, s = bound
    idle, ok = step(op, state, p, ZERO)
    assert ok
    for a, b in zip(idle, state, strict=True):
        assert np.asarray(a).tobytes() == np.asarray(b).tobytes()
    moved, _ = step(op, state, p, one(2, 0.5))  # Only cell_0 -> ecs_1.
    ions = np.arange(4) != s
    assert moved.amount_increment[ions].tobytes() == state.amount_increment[ions].tobytes()
    assert moved.extracellular_amount_increment[s, 1] == state.extracellular_amount_increment[s, 1]
    assert np.all(moved.exchange_moved_fmol[[0, 1, 3, 4, 5]] == 0.0)


def test_a_supply_shortfall_and_a_failed_saturable_solve_refuse(bound):
    _, _, op, state, p, s = bound
    with np.errstate(all="ignore"):
        _, ok = step(op, state, p, one(0, 1.0))  # 0.5 fmol from a 1e-3 fmol pool.
    assert not ok
    # Nearly the whole node taken up in one half-step with K_M far below c_o: Newton from the
    # first-order step needs about 23 iterations (u falls by about 1 per step), more than the 8.
    n = pools(state, p, s)[2]
    vmax = n * (1 - 1e-10) / (1e-11 * H)
    with np.errstate(all="ignore"):
        _, ok = step(op, state, p, one(4, vmax), km=1e-15)
    assert not ok


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda raw: raw["model"]["operators"][0]["routes"][3].update(law="flux"), "never a flux"),
        (
            lambda raw: raw["model"]["operators"][0]["routes"][1].update(law="saturable"),
            "export law is flux or first_order",
        ),
        (
            lambda raw: raw["model"]["operators"][0]["routes"][1].update(patch="wall_cell_0"),
            "faces a held bath",
        ),
        (
            lambda raw: raw["model"]["operators"][0]["routes"][1].update(patch="nowhere"),
            "undeclared patch",
        ),
        (
            lambda raw: raw["model"]["operators"][0]["routes"][1].update(direction="across"),
            "direction is one of",
        ),
        (
            lambda raw: raw["experiment"]["exchange_controls"][4]["schedule"][0].update(
                saturation_mM=0.0
            ),
            "K_M of route sink_1",
        ),
        (
            lambda raw: raw["experiment"]["exchange_controls"][1]["schedule"][0].update(rate=-0.1),
            "rate >= 0",
        ),
        (
            lambda raw: raw["experiment"]["exchange_controls"][4]["schedule"][0].pop(
                "saturation_mM"
            ),
            "missing=\\['saturation_mM'\\]",
        ),
        (
            lambda raw: raw["experiment"]["exchange_controls"][1]["schedule"][0].update(
                saturation_mM=1.0
            ),
            "unknown=\\['saturation_mM'\\]",
        ),
        (
            lambda raw: raw["experiment"]["exchange_controls"].append(
                dict(route_id="take_up", carrier_id="cell_0", schedule=[dict(time=0.001, rate=0.1)])
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
