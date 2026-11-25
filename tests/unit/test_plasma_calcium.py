"""Calcium transport at the plasma membrane on the cycle kind: the ATP-driven pump at valence 2 and
one calcium per ATP, and the sodium-calcium exchange, against outside references.

- **Laws:** the pump against the pinned source's own function, run unmodified out of process
  (AGENTS.md), an independent scalar form and @3's own calcium pump's kernel; its stall. The
  exchange against the direct forward and reverse products; its reversal and its slope there. The
  sign of each heat.
- **One small closed @3 world** with both, stepped on the host in NumPy: at a stage the
  stoichiometry, the owned scatter, the charge and the energy, and the run against an independent
  ODE (SciPy, scalar rates, two methods) at h, h/2 and h/4.

The references are tests/reference_plasma_calcium.py's scalar rates and this file's own ODE, neither
with a Cells import. The worlds and their numbers are this file's own: heredity cell D's rows,
closed and bare, with calcium and held fuel (test_cycle_kind.py's). The laws' planted copies and
their refusals are in that file.
"""

import functools
import math

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from cells.kinds import transporter
from cells.laws.pumps import ca_atp_mass_action_positive as ca_atp
from tests.reference_er_calcium import F, R, native_capture
from tests.reference_plasma_calcium import scalar_rates
from tests.unit import test_cycle_kind as core
from tests.unit import test_transporter_kind as tk

EPS = np.finfo(float).eps


# ------------------------------------------------------------------ the laws, at set states

T_K = 298.15
FUEL_MM = dict(ATP=1.5, ADP=0.1, Pi=0.1)
PUMP = dict(  # The scalar form's parameters; the pump's, with the fuel's potentials below.
    capacity_fmol_per_s=0.003,
    km_ca_mM=0.001,
    km_atp_mM=0.5,
    atp_mM=FUEL_MM["ATP"],
    adp_mM=FUEL_MM["ADP"],
    pi_mM=FUEL_MM["Pi"],
    delta_g0_J_per_mol=-10000.0,
)
EXCHANGE = dict(capacity_fmol_per_s=0.003, km_na_mM=20.0, km_ca_mM=0.001)


@functools.cache
def at_rest():
    """The closed world at T_K with one pump and one exchange, and its fuel's registry potentials,
    -10 kJ/mol for hydrolysis against 1 mM."""
    pump = core.pump_case(
        "Ca", 1, tuple(PUMP[k] for k in ("capacity_fmol_per_s", "km_ca_mM", "km_atp_mM"))
    )
    exchange = core.na_ca_case(tuple(EXCHANGE.values()))
    mu = dict(ATP=0.0, ADP=PUMP["delta_g0_J_per_mol"] / (R * T_K), Pi=0.0)
    rows = {s: (0, mu[s], FUEL_MM[s], 1e-3) for s in FUEL_MM}
    raw = core.core_world(pump.entry, exchange.entry, rows=rows)
    raw["model"]["temperature_K"] = T_K
    with tk.scoped():
        return core.na_ca_start(raw)


def evaluated(mM, volts, availability=1.0):
    """(the probe's modes, its populations, the evaluation) at the nodes' mM and the cell's voltage,
    population 0 the pump and 1 the exchange."""
    spec, _, state, p, control = at_rest()
    state, _ = core.put(spec, state, p, mM)
    control = control._replace(cycle_availability=np.full(2, availability))
    potentials = np.array([volts, 0.0])
    probe = transporter.probe(state, potentials, control, p, xp=np)
    return (
        probe.modes,
        probe.populations,
        transporter._evaluate(state, potentials, control, p, xp=np),
    )


def test_the_pump_is_the_pinned_sources_positive_law_and_an_independent_scalar_form():
    """Six states of both signs: the pump's cycles are the pinned function's flux over the area, the
    scalar form's and @3's own calcium pump's kernel's (its drive against 1 M), to 3e-12; each heat
    is -J times the free energy and not negative; blocked it runs none, which the pinned function
    ignores. Planted: one calcium's charge for two is told apart at every state with a voltage."""
    ci = np.array([1e-6, 0.0001, 0.002, 0.002, 0.02, 0.002])
    co = np.array([0.2, 0.1, 0.2, 0.2, 0.01, 0.2])
    v = np.array([-0.12, -0.04, 0.0, 0.12, 0.04, 0.05])
    area = 1e-9
    params = dict(
        deltaGATP=PUMP["delta_g0_J_per_mol"],
        cATP=PUMP["atp_mM"],
        cADP=PUMP["adp_mM"],
        cPi=PUMP["pi_mM"],
        R=R,
        F=F,
        KmCa_Ca=PUMP["km_ca_mM"],
        KmCa_ATP=PUMP["km_atp_mM"],
        alpha_Ca=PUMP["capacity_fmol_per_s"] * 1e-15 / area,
    )
    # The pinned function, run unmodified out of process (AGENTS.md), at block 1 and block 0.
    case = dict(cCai=ci.tolist(), cCao=co.tolist(), Vm=v.tolist(), T=T_K, parameters=params)
    native = native_capture({"plasma_pump": [case | {"blocks": [1, 0]}]})["plasma_pump"][0]
    expected = -np.asarray(native["flux"][0]) * area / 1e-15
    np.testing.assert_array_equal(-np.asarray(native["flux"][1]) * area / 1e-15, expected)
    molar = PUMP["delta_g0_J_per_mol"] + R * T_K * math.log(1000.0)
    pools = (PUMP[k] for k in ("atp_mM", "adp_mM", "pi_mM", "km_ca_mM", "km_atp_mM"))
    kernel = ca_atp.Parameters(PUMP["capacity_fmol_per_s"], *pools, molar)
    actual, blocked, planted = (np.empty(6) for _ in range(3))
    for i, (a, b, volts) in enumerate(zip(ci, co, v, strict=True)):
        modes, populations, _ = evaluated(dict(Ca=(a, b)), volts)
        actual[i] = modes.j[0, 0]
        blocked[i] = evaluated(dict(Ca=(a, b)), volts, 0.0)[0].j[0, 0]
        planted[i] = evaluated(dict(Ca=(a, b)), volts / 2)[0].j[0, 0]
        rate, _, g, *_ = scalar_rates(1.0, 1.0, a, b, volts, T_K, PUMP, None, (1.0, 1.0))
        own = ca_atp.kinetics(a, b, volts, T_K, kernel, 1.0, xp=np)
        for other in (rate, own.cycles_fmol_s):
            np.testing.assert_allclose(actual[i], other, rtol=3e-12, atol=3e-14)
        np.testing.assert_allclose(populations.heat_pJ_s[0], -rate * g / 1e3, rtol=1e-11)
        assert populations.heat_pJ_s[0] >= 0 and populations.valid[0]
    np.testing.assert_allclose(actual, expected, rtol=3e-12, atol=3e-14)
    assert np.any(actual > 0) and np.any(actual < 0) and np.all(blocked == 0)
    assert np.all((np.abs(planted - actual) > 1e-6 * np.abs(actual)) == (v != 0))


def test_the_pump_stalls_where_the_fuels_drive_meets_two_charges_and_the_gradient():
    """At V = (RT/2F) [drive/RT + ln(co/ci)] it stalls: forward below it and backward above."""
    ci, co = 0.002, 0.2
    *_, drive = scalar_rates(1.0, 1.0, ci, co, 0.0, T_K, PUMP, None, (1.0, 1.0))
    head = (drive + R * T_K * math.log(co / ci)) / (2 * F)
    forward, stall, backward = (
        evaluated(dict(Ca=(ci, co)), head + dv)[0] for dv in (0.005, 0.0, -0.005)
    )
    assert forward.j[0, 0] > 0 > backward.j[0, 0]
    assert abs(stall.j[0, 0]) <= 1e-13 * stall.scale[0, 0]


def test_the_exchange_meets_the_direct_products_at_its_reversal_and_on_both_sides():
    """J is forward minus reverse of the scalar products to 3e-12; it vanishes at 3 E_Na - 2 E_Ca,
    positive below and negative above; its slope there is the scalar form's difference; its heat is
    not negative and it does no work; blocked it runs none. Planted: the reversal of two sodium."""
    ni, no, ci, co = 12.0, 140.0, 0.001, 0.2
    mM = dict(Na=(ni, no), Ca=(ci, co))
    reversal = -R * T_K / F * math.log((ni / no) ** 3 * co / ci)

    def scalar(volts):
        return scalar_rates(ni, no, ci, co, volts, T_K, None, EXCHANGE, (1, 1))[1]

    for dv in (-0.03, 0.0, 0.03):
        modes, populations, _ = evaluated(mM, reversal + dv)
        j = modes.j[0, 1]
        np.testing.assert_allclose(j, scalar(reversal + dv), rtol=3e-12, atol=3e-17)
        assert np.sign(j) == -np.sign(dv) if dv else abs(j) < 1e-17
        assert populations.heat_pJ_s[1] >= 0 and populations.work_pJ_s[1] == 0
        assert evaluated(mM, reversal + dv, 0.0)[0].j[0, 1] == 0
    *_, e = evaluated(mM, reversal)
    step = 1e-6
    difference = (scalar(reversal + step) - scalar(reversal - step)) / (2 * step)
    slope = float(e.d_j_d_psi[0, 1]) * F / (R * T_K)
    assert slope == pytest.approx(difference, rel=2e-9, abs=1e-14)
    two = -R * T_K / F * math.log((ni / no) ** 2 * co / ci)
    assert abs(evaluated(mM, two)[0].j[0, 1]) > 1e-3 * evaluated(mM, two)[0].scale[0, 1]


# ------------------------------------------------------------------ the closed world

WORLD_T_K = core.CORE_T_K
VOLTS, CA = -0.05, (0.04, 1.2)  # The cell's start: its voltage, and calcium at the two ends (mM).
FUEL = dict(ATP=(2.5, 3.0), ADP=(0.3, -4.0), Pi=(4.0, -2.5))  # mM, and RT against 1 mM.
WORLD_PUMP = (0.04, 8e-3, 0.3)  # Capacity (fmol/s), K and K_ATP (mM).
WORLD_EXCHANGE = (0.3, 25.0, 6e-3)  # Capacity (fmol/s), K_Na and K_Ca (mM).
H, STEPS = 0.02, 8  # The longest step (s) and the steps to the end.


def closed():
    """The definition of the closed world with one pump and one exchange."""
    pump, exchange = core.pump_case("Ca", 1, WORLD_PUMP), core.na_ca_case(WORLD_EXCHANGE)
    rows = {s: (0, mu, mM, 1e-3) for s, (mM, mu) in FUEL.items()}
    ends = dict(cell_0=dict(Ca=CA[0]), bath_0=dict(Ca=CA[1]))
    entries = (pump.entry, exchange.entry)
    return core.core_world(*entries, rows=rows, mM=ends, volts=VOLTS, dt=H)


def scalar_parameters():
    """The scalar form's parameters of the closed world's two populations."""
    k, km, km_atp = WORLD_PUMP
    g0 = FUEL["ADP"][1] + FUEL["Pi"][1] - FUEL["ATP"][1]
    pump = dict(
        capacity_fmol_per_s=k,
        km_ca_mM=km,
        km_atp_mM=km_atp,
        atp_mM=FUEL["ATP"][0],
        adp_mM=FUEL["ADP"][0],
        pi_mM=FUEL["Pi"][0],
        delta_g0_J_per_mol=R * WORLD_T_K * g0,  # Against 1 mM, the scalar form's numeric mM.
    )
    return pump, dict(zip(EXCHANGE, WORLD_EXCHANGE, strict=True))


class Reference:
    """The closed world as an ODE of its two cycle counts, its heat and its work, in scalar rates:
    no Cells import. Per cycle the pump takes one calcium out, and the exchange one, against three
    sodium in; so the cell's charge changes by -2 and by +1, over its patch's capacitance."""

    def __init__(self, raw, sodium=3.0, pump_faster=1.0):
        (cell,), (bath,), (patch,) = (
            raw["model"][k] for k in ("cells", "extracellular", "membranes")
        )
        self.volumes = cell["volume_pL"], bath["volume_pL"]
        self.start = [
            tuple(node["initial_amount_fmol"][s] for node in (cell, bath)) for s in ("Na", "Ca")
        ]
        self.per_fmol = F * 1e-15 / patch["capacitance_F"]
        self.sodium, (self.pump, self.exchange) = sodium, scalar_parameters()
        self.pump["capacity_fmol_per_s"] *= pump_faster

    def amounts(self, p, x):
        """((Na, Ca) in the cell, in the bath) (fmol) after p pump and x exchange cycles."""
        (na_i, na_o), (ca_i, ca_o) = self.start
        na, ca = self.sodium * x, p + x
        return (na_i + na, ca_i - ca), (na_o - na, ca_o + ca)

    def volts(self, p, x):
        return VOLTS + self.per_fmol * (-2 * p + (self.sodium - 2) * x)

    def rhs(self, _, y):
        p, x = y[:2]
        (ni, ci), (no, co) = (
            [n / v for n in end] for end, v in zip(self.amounts(p, x), self.volumes, strict=True)
        )
        jp, jx, gp, gx, drive = scalar_rates(
            ni, no, ci, co, self.volts(p, x), WORLD_T_K, self.pump, self.exchange, (1.0, 1.0)
        )
        return [jp, jx, -1e-3 * (jp * gp + jx * gx), -1e-3 * jp * drive]

    def solved(self, end, method="DOP853"):
        found = solve_ivp(
            self.rhs, (0.0, end), np.zeros(4), method=method, rtol=1e-12, atol=1e-15, t_eval=[end]
        )
        assert found.success
        return found.y[:, -1]


def stepped(start, h, steps):
    """(the state, the cell's voltage) after `steps` host steps of h from a started world, in its
    scope: every step valid and every ledger closed."""
    spec, impl, state, p, control = start
    states = [state]
    for _ in range(steps):
        state, valid = impl.imex_step(state, h, control, p, xp=np)
        assert bool(valid)
        states.append(state)
    history = impl.STATE_TYPE(*(np.stack(v) for v in zip(*states, strict=True)))
    impl.check_values(history, spec, steps=np.arange(len(states)))
    potential = impl.readouts(state, control, p, xp=np).field.potential_V
    return state, float(potential[0] - potential[1])


def test_a_stage_moves_each_laws_counts_where_they_belong_and_its_energy_balances():
    """At the start the rates are the scalar form's: calcium leaves the cell at the pump's and the
    exchange's cycles, three sodium enter per exchange, the bath takes the opposite and nothing else
    moves; the charge that crosses is -2 and +1 per cycle; and the ideal and electrical energy of
    the moved ions changes by the fuel's work less the heat. Planted: the charge with the sodium
    missing, and the energy with the fuel's work missing."""
    raw = closed()
    with tk.scoped():
        spec, impl, state, p, control = core.na_ca_start(raw)
        potential = np.asarray(impl.readouts(state, control, p, xp=np).field.potential_V)
        rates = transporter.rates(state, potential, control, p, xp=np)
    reference = Reference(raw)
    jp, jx, *_ = reference.rhs(0.0, np.zeros(4))
    assert jp > 0 and jx != 0
    cycles = np.asarray(rates.derivatives["cycle_count"][0])
    np.testing.assert_allclose(cycles, (jp, jx), rtol=1e-11)
    ids = list(spec.model.species_ids)
    counts = dict(Ca=(-1.0, -1.0), Na=(0.0, 3.0))
    for k, s in enumerate(ids):
        moved = float(np.dot(counts.get(s, (0.0, 0.0)), cycles))
        assert float(rates.cell[k, 0]) == pytest.approx(moved, rel=8 * EPS, abs=0), s
        assert float(rates.outside[k, 0]) == pytest.approx(-moved, rel=8 * EPS, abs=0), s
    valence = np.array(spec.model.valence)
    charge = float(valence @ rates.cell[:, 0])
    assert charge == pytest.approx(-2 * cycles[0] + cycles[1], rel=1e-12, abs=0)
    assert charge != pytest.approx(-2 * (cycles[0] + cycles[1]), rel=1e-3, abs=0)
    nodes = (*spec.model.cells, *spec.model.extracellular)
    energy = 0.0  # pJ/s: each ion's electrochemical potential times its rate, at both nodes.
    for node, phi, out in zip(nodes, potential, (rates.cell, rates.outside), strict=True):
        for k in (ids.index("Na"), ids.index("Ca")):
            c = node.initial_amount_fmol[k] / node.volume_pL
            energy += 1e-3 * (R * WORLD_T_K * math.log(c) + valence[k] * F * phi) * out[k, 0]
    heat, work = float(np.sum(rates.heat_pJ_s)), float(np.sum(rates.work_pJ_s))
    size = abs(energy) + heat + abs(work)
    assert abs(energy + heat - work) < 1e-12 * size
    assert abs(energy + heat) > 1e-3 * size  # Planted: the fuel's work missing.
    assert heat > 0 and work > 0 and rates.work_pJ_s[1] == 0


def test_the_closed_run_converges_to_the_independent_ode_at_second_order():
    """The cycles, the heat, the work, the amounts at both ends and the voltage at the end of the
    run approach the ODE's (DOP853 and Radau agree to 1e-9 of each), by a factor of 3.8 to 4.3 at
    each halving of the step, and every ledger closes. Planted: an ODE with two sodium per cycle,
    and one with a pump 1% faster, each lies over ten times further off than the finest step."""
    raw, end = closed(), H * STEPS
    reference = Reference(raw)
    exact = reference.solved(end)
    np.testing.assert_allclose(reference.solved(end, "Radau"), exact, rtol=1e-9)

    def of(y):
        cell, bath = reference.amounts(*y[:2])
        return np.array([*y, *cell, *bath, reference.volts(*y[:2])])

    target, errors = of(exact), []
    with tk.scoped():
        start = core.na_ca_start(raw)
        runs = [stepped(start, H / halving, STEPS * halving) for halving in (1, 2, 4)]
    spec, ids = start[0], list(start[0].model.species_ids)
    nodes = (spec.model.cells[0], spec.model.extracellular[0])
    for state, volts in runs:
        moved = (state.amount_increment[:, 0], state.extracellular_amount_increment[:, 0])
        amounts = [
            node.initial_amount_fmol[ids.index(s)] + float(gained[ids.index(s)])
            for node, gained in zip(nodes, moved, strict=True)
            for s in ("Na", "Ca")
        ]
        heat = float(np.sum(state.cycle_dissipated_energy_pJ))
        work = float(np.sum(state.cycle_metabolic_work_pJ))
        found = [*state.cycle_count[0], heat, work, *amounts, volts]
        errors.append(np.abs(np.array(found) - target))
    errors, ratios = np.array(errors), np.array(errors[:-1]) / np.array(errors[1:])
    assert np.all(ratios > 3.8) and np.all(ratios < 4.3)
    assert np.all(errors[-1] < 1e-4 * np.abs(target - of(np.zeros(4))))
    for planted in (Reference(raw, sodium=2.0), Reference(raw, pump_faster=1.01)):
        off = np.abs(planted.solved(end)[:2] - exact[:2])
        assert np.all(off > 10 * errors[-1][:2])
