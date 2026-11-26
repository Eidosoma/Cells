"""Tier-1 tests of cells.operator.scheduled_membrane_trafficking@1's laws (FR-2 version 1): T4, T5 and T6 of
docs/MEMBRANE_RETRIEVAL_DESIGN.md §8 at the operator level, in NumPy on bound worlds (no compile).
Each check is against an independent computation written here, and each sits beside a planted
error it catches. These are development checks; the judged references are the references agent's.

* T4, the charge rule (R2), against a dense capacitor solve of the state, written here.
  - Retrieval from a held bath (at 20 mV) and from a free node: every potential but the pool's is
    unchanged to the solve's rounding, and V_b' and the heat follow §2.2's closed forms.
    Planted: R1, the membrane leaving uncharged (its carriers not written), moves the owner by
    V dC/(C - dC).
  - Recycling into the held bath's patch: the pool keeps V_b, and V_k' = (C_k V_k + dC V_b)/(C_k +
    dC) with the heat C_k dC (V_k - V_b)^2 / (2 (C_k + dC)).
* T5, down-regulation and return, with units moved only by this operator.
  - A retrieval-recycling cycle follows N (A'/A)^e and R (A_b'/A_b)^e_r piecewise. Planted: the
    closed form at an exponent one part in 10^6 off is refused.
  - With both directions at once the palindrome converges at second order against an
    independent ODE solve. Planted: a first-order (Lie) split is refused.
* T6, energy.
  - Per half-step, the chemical free energy (50-digit arithmetic), the capacitor energy (the dense
    solve), the heat and the work close exactly. The carriers' signed work equals their
    independent free-energy change, less the held bath's chemical share of its supply. Planted:
    the carriers' work booked with the wrong sign.
  - A held bath at 20 mV books its electrode and reservoir work at its potential, and the clamp's
    transfer and the reservoir's supplied charge cancel. Planted: the reservoir work without its
    electrical part fails @3's reservoir-work ledger.
  - Planted: a merge heat booked with the wrong sign fails the dissipation check.

"""

from decimal import Decimal, localcontext

import jax
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.errors import NumericalError
from cells.laws.electrochemistry import CHARGE_PER_FMOL, F, R
from cells.models import pump_composite_adapter as adapter
from cells.models import surface_pump
from cells.operators import membrane_state
from cells.operators import membrane_trafficking as trafficking
from cells.registry.models import get_model
from tests.unit.test_membrane_trafficking import control, history, operator
from validation.tissue import membrane_trafficking_fixtures as fx

H = fx.DT / 2


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def world(*, plasma="membrane_0", bath_V=0.02, cleft=False, **changes):
    raw = fx.pooled_cells(1, bath_V=bath_V, cleft=cleft)
    entry = fx.route(raw, 0, plasma=plasma, **changes)
    raw = fx.with_trafficking(raw, [entry], [fx.schedule(entry["id"], [(0.0, 0.0)])])
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    return spec, model, state, p


def step(model, state, p, retrieval, recycling):
    new, ok = operator(model).half_step(state, H, control([retrieval], [recycling]), p, xp=np)
    assert ok
    return new


def fraction_rate(p, slot, fraction):
    """The rate that moves `fraction` of patch `slot`'s current declared area in one half-step."""
    return fraction * float(p.membrane_area[slot]) / H


# ------------------------------------------------------------------ the independent references


def dense(state, p):
    """(phi [cells, then outside nodes], patch voltages, 1/2 sum C V^2 in pJ): the capacitor
    network of the state's charges (anchors + z F increments) and membrane state's capacitances,
    solved densely here, the held nodes at their potentials."""
    n, o = p.active.size, p.outside_active.size
    capacitance = np.asarray(membrane_state.capacitance(state, p, xp=np), dtype=float)
    matrix = np.zeros((n + o, n + o))
    for m, c in enumerate(capacitance):
        if p.membrane_active[m]:
            e = np.zeros(n + o)
            e[p.membrane_cell[m]], e[n + p.membrane_outside[m]] = 1.0, -1.0
            matrix += c * np.outer(e, e)
    z = np.asarray(p.valence)[:, 0]
    charge = np.concatenate((p.initial_cell_charge_C, p.initial_outside_charge_C))
    charge = charge + CHARGE_PER_FMOL * np.concatenate(
        (
            z @ np.asarray(state.amount_increment),
            z @ np.asarray(state.extracellular_amount_increment),
        )
    )
    held = np.concatenate((~np.asarray(p.active), np.asarray(p.reservoir) | ~p.outside_active))
    phi = np.concatenate((np.zeros(n), np.asarray(p.boundary_V, dtype=float)))
    free = ~held
    rhs = charge[free] - matrix[np.ix_(free, held)] @ phi[held]
    phi[free] = np.linalg.solve(matrix[np.ix_(free, free)], rhs)
    v = np.where(p.membrane_active, phi[p.membrane_cell] - phi[n + p.membrane_outside], 0.0)
    return phi, v, 0.5e12 * float(np.sum(capacitance * v**2))


def amounts(state, p):
    """[(reference, increment, volume, free), ...] per node and species: cells, then outside."""
    out = []
    cells = zip(
        np.asarray(p.amount_reference).T,
        np.asarray(state.amount_increment).T,
        p.volume,
        strict=True,
    )
    for reference, increment, volume in cells:
        out.extend((r, i, volume, True) for r, i in zip(reference, increment, strict=True))
    free = np.asarray(p.outside_active) & ~np.asarray(p.reservoir)
    nodes = zip(
        np.asarray(p.extracellular_amount_reference).T,
        np.asarray(state.extracellular_amount_increment).T,
        p.extracellular_volume,
        free,
        strict=True,
    )
    for reference, increment, volume, is_free in nodes:
        out.extend((r, i, volume, is_free) for r, i in zip(reference, increment, strict=True))
    return out


def chemical_change(before, after, p, *, outside=None):
    """The tissue's chemical free-energy change (pJ) from `before` to `after`, in 50-digit
    arithmetic: RT sum n (ln(n/V) - 1) over the cells and the free outside nodes, or over the
    outside nodes `outside` (slots) alone. A held bath's content lies outside the tissue."""
    species, cells = np.asarray(p.amount_reference).shape
    with localcontext() as context:
        context.prec = 50
        total = Decimal(0)
        pairs = zip(amounts(before, p), amounts(after, p), strict=True)
        for k, ((r0, i0, v, free), (_, i1, _, _)) in enumerate(pairs):
            node = k // species - cells  # Its outside slot (negative for a cell).
            if outside is not None and node not in outside:
                continue
            if not free or i0 == i1:
                continue
            volume = Decimal(float(v))
            for increment, sign in ((i1, 1), (i0, -1)):
                n = Decimal(float(r0)) + Decimal(float(increment))
                total += sign * n * ((n / volume).ln() - 1)
        return float(Decimal("1e-3") * Decimal(R) * Decimal(float(p.temperature)) * total)


def booked(state, name):
    return float(np.sum(getattr(state, name)))


# ------------------------------------------------------------------ T4: the charge rule


def only_the_pool_moves(phi0, phi1, j):
    """Whether every potential but phi_j is unchanged to the solve's rounding, and phi_j moved."""
    scale = np.max(np.abs(phi0))
    others = np.delete(np.abs(phi1 - phi0), j)
    return bool(np.all(others <= 1e-12 * scale)) and abs(phi1[j] - phi0[j]) > 1e-9 * scale


@pytest.mark.parametrize("source", ["held bath", "free node"])
def test_retrieval_moves_only_the_pool_into_its_closed_form(source, monkeypatch):
    cleft = source == "free node"
    _, model, state, p = world(plasma="furrow_0" if cleft else "membrane_0", cleft=cleft)
    k, b = int(p.trafficking_route_plasma[0]), int(p.trafficking_route_pool[0])
    j = p.active.size + int(p.membrane_outside[b])
    phi0, v0, u0 = dense(state, p)
    c0 = np.asarray(membrane_state.capacitance(state, p, xp=np))
    new = step(model, state, p, fraction_rate(p, k, 0.03), 0.0)
    phi1, v1, u1 = dense(new, p)
    dc = float(new.trafficking_capacitance_F[b])
    assert only_the_pool_moves(phi0, phi1, j)
    expected = (c0[b] * v0[b] + dc * v0[k]) / (c0[b] + dc)
    assert v1[b] == pytest.approx(expected, rel=1e-12)
    heat = 1e12 * c0[b] * dc * (v0[b] - v0[k]) ** 2 / (2 * (c0[b] + dc))
    assert booked(new, "trafficking_dissipated_energy_pJ") == pytest.approx(heat, rel=1e-9)
    # Planted: R1, the retrieved membrane leaving uncharged (no carriers written), moves the owner.
    real = adapter.charge_following_transfer

    def uncharged(*args, **kwargs):
        out = real(*args, **kwargs)
        return out._replace(plate_C=0.0 * out.plate_C)

    monkeypatch.setattr(trafficking.adapter, "charge_following_transfer", uncharged)
    planted = step(model, state, p, fraction_rate(p, k, 0.03), 0.0)
    phi2, _, _ = dense(planted, p)
    assert not only_the_pool_moves(phi0, phi2, j)
    if not cleft:  # One held patch: the owner moves by V dC / (C - dC).
        i = int(p.membrane_cell[k])
        assert phi2[i] - phi0[i] == pytest.approx(v0[k] * dc / (c0[k] - dc), rel=1e-9)


def test_recycling_keeps_the_pool_and_merges_into_the_plasma_closed_form():
    _, model, state, p = world()
    k, b = int(p.trafficking_route_plasma[0]), int(p.trafficking_route_pool[0])
    for _ in range(3):  # Charge the pool first.
        state = step(model, state, p, fraction_rate(p, k, 0.02), 0.0)
    _, v0, _ = dense(state, p)
    c0 = np.asarray(membrane_state.capacitance(state, p, xp=np))
    heat0 = booked(state, "trafficking_dissipated_energy_pJ")
    area = float(membrane_state.area(state, p, xp=np)[b])
    new = step(model, state, p, 0.0, 0.2 * area / H)
    _, v1, _ = dense(new, p)
    dc = float(membrane_state.capacitance(new, p, xp=np)[k]) - c0[k]  # What k gained.
    assert v1[b] == pytest.approx(v0[b], rel=1e-12)  # The pool keeps V_b.
    assert v1[k] == pytest.approx((c0[k] * v0[k] + dc * v0[b]) / (c0[k] + dc), rel=1e-12)
    heat = 1e12 * c0[k] * dc * (v0[k] - v0[b]) ** 2 / (2 * (c0[k] + dc))
    assert booked(new, "trafficking_dissipated_energy_pJ") - heat0 == pytest.approx(heat, rel=1e-9)


# ------------------------------------------------------------------ T5: down-regulation and return

E = {"kir_0": 1.0, "nav_0": 0.5}
E_R = {"kir_0": 2.0, "nav_0": 1.0}


def cycle(model, state, p, segments):
    """The rows after each half-step of [(half-steps, retrieval rate, recycling rate), ...]."""
    rows = [state]
    for count, retrieval, recycling in segments:
        for _ in range(count):
            rows.append(step(model, rows[-1], p, retrieval, recycling))
    return rows


def test_a_cycle_follows_the_closed_forms_piecewise():
    _, model, state, p = world(retrieval=E, recycling=E_R)
    k, b = int(p.trafficking_route_plasma[0]), int(p.trafficking_route_pool[0])
    rows = cycle(
        model, state, p, [(4, fraction_rate(p, k, 0.02), 0.0), (4, 0.0, fraction_rate(p, b, 0.05))]
    )
    e, e_r = np.array(list(E.values())), np.array(list(E_R.values()))

    def check(exponents, rows, start, which, slot):
        area0 = float(membrane_state.area(rows[start], p, xp=np)[slot])
        value0 = which(rows[start])
        worst = 0.0
        for row in rows[start:]:
            ratio = float(membrane_state.area(row, p, xp=np)[slot]) / area0
            expected = value0 * ratio**exponents
            worst = max(worst, float(np.max(np.abs(which(row) - expected) / np.abs(expected))))
        return worst

    def plasma(row):
        return np.asarray(membrane_state.units(row, p, xp=np))

    def record(row):
        return np.asarray(row.trafficking_internalised_units[0])

    assert check(e, rows[:5], 0, plasma, k) < 1e-13  # Retrieval: N (A_k'/A_k)^e.
    assert (
        check(e_r[:1], rows, 4, lambda r: record(r)[:1], b) < 1e-13
    )  # Recycling: R (A_b'/A_b)^e_r.
    assert check(e_r[1:], rows, 4, lambda r: record(r)[1:], b) < 1e-13
    total = plasma(rows[0]) + record(rows[0])
    np.testing.assert_allclose(plasma(rows[-1]) + record(rows[-1]), total, rtol=1e-14)
    # Planted: the closed form at an exponent one part in 10^6 off is refused.
    assert check(e * (1 + 1e-6), rows[:5], 0, plasma, k) > 1e-9


def ode_reference(state, p, retrieval, recycling, duration):
    """(N_kir, R_kir) after `duration` at constant rates, by RK4 with 20 000 steps: dN/dt =
    -r1 e N / A_k + r2 e_r R / A_b, dR/dt = -dN/dt, with A_k = A_k0 - (r1 - r2) t and A_b = A_b0
    + (r1 - r2) t, written here."""
    k, b = int(p.trafficking_route_plasma[0]), int(p.trafficking_route_pool[0])
    a0 = float(membrane_state.area(state, p, xp=np)[k])
    b0 = float(membrane_state.area(state, p, xp=np)[b])
    n0 = float(membrane_state.units(state, p, xp=np)[0])
    rec0 = float(state.trafficking_internalised_units[0][0])
    s = retrieval - recycling

    def flux(t, n, r):
        return -retrieval * E["kir_0"] * n / (a0 - s * t) + recycling * E_R["kir_0"] * r / (
            b0 + s * t
        )

    steps = 20_000
    dt, n, r, t = duration / steps, n0, rec0, 0.0
    for _ in range(steps):  # dR/dt = -dN/dt, so one flux gives both.
        k1 = flux(t, n, r)
        k2 = flux(t + dt / 2, n + dt / 2 * k1, r - dt / 2 * k1)
        k3 = flux(t + dt / 2, n + dt / 2 * k2, r - dt / 2 * k2)
        k4 = flux(t + dt, n + dt * k3, r - dt * k3)
        change = dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        n, r, t = n + change, r - change, t + dt
    return n, r


def test_both_directions_converge_at_second_order():
    """An empty record at the start: with a large one (R0 = 400 Kir units) the Lie split's
    first-order term nearly cancels in this world (an area term, -b r1 R / A_b, offsets the frozen
    commutator ab (N + R)), so its errors fall at about 3.5x before rising, and the plant could not
    be told from second order (probe of 19 November 2026: ratios 3.53, then 0.75)."""
    _, model, state, p = world(retrieval=E, recycling=E_R)
    k, b = int(p.trafficking_route_plasma[0]), int(p.trafficking_route_pool[0])
    retrieval = 0.05 * float(p.membrane_area[k]) / fx.DT
    recycling = 0.4 * float(p.membrane_area[b]) / fx.DT
    duration = 4 * fx.DT
    reference = ode_reference(state, p, retrieval, recycling, duration)

    def error(half_steps, lie=False):
        h = duration / half_steps
        rate = control([retrieval], [recycling])
        row = state
        for _ in range(half_steps):
            if lie:  # Planted: a first-order split, S_ret(h) S_rec(h).
                row, _ = trafficking.stage(
                    row, h, rate.trafficking_retrieval_rate_m2_s, p, True, xp=np
                )
                row, _ = trafficking.stage(
                    row, h, rate.trafficking_recycling_rate_m2_s, p, False, xp=np
                )
            else:
                row, ok = trafficking.trafficked(row, h, rate, p, xp=np)
                assert ok
        n = float(membrane_state.units(row, p, xp=np)[0])
        return abs(n - reference[0]) / reference[0]

    coarse, fine = error(8), error(16)
    assert 3.5 < coarse / fine < 4.5 and fine < 1e-4  # Second order (measured 4.00).
    lie_coarse, lie_fine = error(8, lie=True), error(16, lie=True)
    assert lie_coarse / lie_fine < 2.5  # First order (measured 1.94): the check refuses it.


# ------------------------------------------------------------------ T6: energy


def energy_cases():
    yield "retrieval from a held bath at 20 mV", dict(), [], (0.03, 0.0)
    yield "retrieval from a free node", dict(plasma="furrow_0", cleft=True), [], (0.03, 0.0)
    yield "recycling into the held bath's patch", dict(), [(3, 0.02, 0.0)], (0.0, 0.2)
    yield "both directions at once", dict(), [(2, 0.02, 0.0)], (0.02, 0.1)


def run_case(changes, before, now):
    _, model, state, p = world(**changes)
    k, b = int(p.trafficking_route_plasma[0]), int(p.trafficking_route_pool[0])
    for count, retrieval, recycling in before:
        for _ in range(count):
            state = step(
                model, state, p, fraction_rate(p, k, retrieval), fraction_rate(p, b, recycling)
            )
    new = step(model, state, p, fraction_rate(p, k, now[0]), fraction_rate(p, b, now[1]))
    return model, state, new, p


def closure(state, new, p, *, carriers_sign=1.0):
    """(residual, scale) of dG + dU + H - W_reservoir - W_electrode - W_carriers over one step."""
    _, _, u0 = dense(state, p)
    _, _, u1 = dense(new, p)
    terms = dict(
        chemical=chemical_change(state, new, p),
        capacitor=u1 - u0,
        heat=booked(new, "trafficking_dissipated_energy_pJ")
        - booked(state, "trafficking_dissipated_energy_pJ"),
        reservoir=-(booked(new, "reservoir_work_pJ") - booked(state, "reservoir_work_pJ")),
        electrode=-(booked(new, "electrode_work_pJ") - booked(state, "electrode_work_pJ")),
        carriers=-carriers_sign
        * (booked(new, "trafficking_work_pJ") - booked(state, "trafficking_work_pJ")),
    )
    return sum(terms.values()), max(abs(v) for v in terms.values()), terms


def independent_carrier_work(state, new, p):
    """The carriers' free-energy change at the free nodes (50 digits) less the held baths' chemical
    share of their supply, RT ln(c_bath) per fmol supplied."""
    supplied = np.asarray(new.reservoir_supplied) - np.asarray(state.reservoir_supplied)
    held = np.asarray(p.reservoir) & np.asarray(p.outside_active)
    concentration = np.where(
        p.outside_active, np.asarray(p.extracellular_amount_reference) / p.extracellular_volume, 1.0
    )
    chemical = R * float(p.temperature) * np.log(concentration)
    share = 1e-3 * float(np.sum(np.where(held, chemical * supplied, 0.0)))
    return chemical_change(state, new, p) - share


@pytest.mark.parametrize(
    "name, changes, before, now", list(energy_cases()), ids=[c[0] for c in energy_cases()]
)
def test_the_energy_closes_exactly_and_the_carriers_work_is_their_free_energy(
    name, changes, before, now
):
    _, state, new, p = run_case(changes, before, now)
    residual, scale, terms = closure(state, new, p)
    assert abs(residual) <= 1e-9 * scale + 1e-18, terms
    work = booked(new, "trafficking_work_pJ") - booked(state, "trafficking_work_pJ")
    expected = independent_carrier_work(state, new, p)
    assert work == pytest.approx(expected, rel=1e-6, abs=1e-15 * scale), (work, expected)
    assert terms["heat"] >= 0
    # Planted: the carriers' work booked with the wrong sign breaks the closure.
    planted, _, _ = closure(state, new, p, carriers_sign=-1.0)
    assert abs(planted) > 100 * (1e-9 * scale + 1e-18) or abs(work) < 1e-16


def test_a_held_bath_books_its_electrode_and_reservoir_work_at_its_potential():
    model, state, new, p = run_case(dict(), [], (0.03, 0.0))
    bath = int(p.membrane_outside[int(p.trafficking_route_plasma[0])])
    phi = float(p.boundary_V[bath])
    assert phi == 0.02
    electrode = float(
        new.electrode_charge_transferred_C[bath] - state.electrode_charge_transferred_C[bath]
    )
    supplied = np.asarray(new.reservoir_supplied[:, bath] - state.reservoir_supplied[:, bath])
    z = np.asarray(p.valence)[:, 0]
    charge = CHARGE_PER_FMOL * float(z @ supplied)
    assert electrode != 0 and electrode == pytest.approx(-charge, rel=1e-12)  # They cancel.
    work = float(new.electrode_work_pJ[bath] - state.electrode_work_pJ[bath])
    assert work == pytest.approx(1e12 * phi * electrode, rel=1e-14)
    concentration = np.asarray(p.extracellular_amount_reference[:, bath]) / float(
        p.extracellular_volume[bath]
    )
    mu = R * float(p.temperature) * np.log(concentration) + z * F * phi
    reservoir = float(new.reservoir_work_pJ[bath] - state.reservoir_work_pJ[bath])
    assert reservoir == pytest.approx(1e-3 * float(mu @ supplied), rel=1e-12)
    ledger = model.balances(new, p)["reservoir_work"]
    assert np.max(np.abs(ledger)) < 1e-15
    # Planted: the reservoir work without its electrical part fails @3's reservoir-work ledger.
    electrical = 1e-3 * float((z * F * phi) @ supplied)
    planted = new._replace(
        reservoir_work_pJ=np.asarray(new.reservoir_work_pJ)
        - np.where(np.arange(p.outside_active.size) == bath, electrical, 0.0)
    )
    assert np.max(np.abs(model.balances(planted, p)["reservoir_work"])) > 1e3 * 3e-12


def shared_cleft():
    """Two cells whose furrows face one cleft, cleft_0: both routes draw their carriers from one
    free node, so its exact free-energy change is shared between them by the amounts moved."""
    raw = fx.pooled_cells(2, cleft=True)
    m, x = raw["model"], raw["execution"]
    next(q for q in m["membranes"] if q["id"] == "furrow_1")["outside"] = "cleft_0"
    m["extracellular"] = [o for o in m["extracellular"] if o["id"] != "cleft_1"]
    m["faces"] = [f for f in m["faces"] if f["id"] != "access_1"]
    x.update(
        extracellular_capacity=x["extracellular_capacity"] - 1,
        face_capacity=x["face_capacity"] - 1,
    )
    routes = [fx.route(raw, i, plasma=f"furrow_{i}") for i in range(2)]
    raw = fx.with_trafficking(raw, routes, [fx.schedule(r["id"], [(0.0, 0.0)]) for r in routes])
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    return model, state, p


def test_two_routes_on_one_free_node_close_and_share_its_free_energy_by_amount():
    model, state, p = shared_cleft()
    plasma = [int(s) for s in p.trafficking_route_plasma]
    pools = [int(p.membrane_outside[int(s)]) for s in p.trafficking_route_pool]
    (cleft,) = {int(p.membrane_outside[s]) for s in plasma}  # One node faces both furrows.
    rates = [r * float(p.membrane_area[s]) / H for r, s in zip((0.03, 0.06), plasma, strict=True)]
    new, ok = operator(model).half_step(state, H, control(rates, [0.0, 0.0]), p, xp=np)
    assert ok
    residual, scale, terms = closure(state, new, p)
    assert abs(residual) <= 1e-9 * scale + 1e-18, terms
    works = np.asarray(new.trafficking_work_pJ) - np.asarray(state.trafficking_work_pJ)
    assert float(np.sum(works)) == pytest.approx(independent_carrier_work(state, new, p), rel=1e-6)
    # Each route: its own pool's change, and its share of the cleft's by the amounts it moved.
    k = list(p.valence[:, 0]).index(1.0)  # A carrier row (K or Na, t = 1/2 each).
    moved = np.array(
        [new.trafficking_carrier_fmol[k, j] - state.trafficking_carrier_fmol[k, j] for j in pools]
    )
    share = np.abs(moved) / np.sum(np.abs(moved))
    shared = chemical_change(state, new, p, outside={cleft})
    own = np.array([chemical_change(state, new, p, outside={j}) for j in pools])
    np.testing.assert_allclose(works, own + share * shared, rtol=1e-6)
    assert share[1] == pytest.approx(2 * share[0], rel=1e-3)  # Twice the rate, twice the share.
    # Planted: the cleft's whole change booked on the first route is told apart.
    planted = own + np.array([shared, 0.0])
    assert not np.allclose(works, planted, rtol=1e-6, atol=0.0)


def test_a_merge_heat_with_the_wrong_sign_fails_the_dissipation_check(monkeypatch):
    spec, model, state, p = world()
    k = int(p.trafficking_route_plasma[0])
    real = trafficking.stage

    def negated(state, *args, **kwargs):  # Planted: each stage books -H.
        new, ok = real(state, *args, **kwargs)
        heat = 2 * state.trafficking_dissipated_energy_pJ - new.trafficking_dissipated_energy_pJ
        return new._replace(trafficking_dissipated_energy_pJ=heat), ok

    monkeypatch.setattr(trafficking, "stage", negated)
    rows = [state]
    for _ in range(3):
        rows.append(step(model, rows[-1], p, fraction_rate(p, k, 0.02), 0.0))
    assert np.all(np.diff([booked(r, "trafficking_dissipated_energy_pJ") for r in rows]) < 0)
    assert "trafficking_dissipated_energy_pJ" in model.DISSIPATION_FIELDS
    steps = list(range(len(rows)))
    # The dissipation check alone: neutral ledgers, and a domain that admits every row (the
    # operator's own domain refuses a negative heat total too, which the full check shows).
    neutral = {name: 0.0 for name in model.inner.LEDGERS}
    with pytest.raises(NumericalError, match=surface_pump.DISSIPATION_MESSAGE):
        model.inner.checked_rows(
            history(rows),
            spec,
            p,
            domain=lambda row, q, active, *, xp: True,
            balances=lambda row, q: neutral,
            magnitudes=model.inner_magnitudes,
            dissipation=model.DISSIPATION_FIELDS,
            steps=steps,
            ledgers=model.inner,
        )
    with pytest.raises(NumericalError):
        model.check_values(history(rows), spec, steps=steps)
