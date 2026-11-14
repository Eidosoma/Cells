"""Tier-1 tests of local_species_reactions@1's half-step (D152 version 1, milestone 2), host side.

The closed forms and identities the note states (docs/SHARED_INVENTORY_REACTIONS_DESIGN.md §3.1,
§3.3, §4.2, §4.4 and Appendix A), in NumPy:
* open linear kinetics 0 -> S -> 0 against turnover's closed form, third order in h;
* a closed passive S <-> P relaxing to its potentials' ratio, its heat -dG >= 0 at every step and
  its total heat G(start) - G(end);
* Michaelis-Menten depletion against K_M ln(S0/S) + (S0 - S) = V_max t, third order in h;
* on seeded random states of the enzyme network (every law and both factor kinds): W - H = dG to
  1e-12 of its terms (Decimal, from the states), dn = nu dxi, the moiety totals moved only by the
  sources and sinks, the standard term = sum_r dG°'_r dxi_r, H = -dG at passive-only nodes;
* the node's class from its multipliers, and the hybrid's branch by Appendix A's signs, with the
  share and the quadrature against their closed forms, on a constructed passive reversal and on
  probe 2e's crossing state;
* the stage condition on unidirectional fluxes (a passive route in reverse included) and its
  refusal; positivity from a 1e-15 mM trace under a fast sink, and the anchored stall; the
  divided-difference potential across its series boundary; the Hill factors; benign padding (every
  intermediate finite with NumPy raising on divide, invalid and overflow, and a planted zero
  padding raising); the host refusal report; the observed rates and affinities.
The independent references of record (Appendix A's NumPy dG tests per law, the dissipation integral)
are another agent's (§3.4); these tests check the closed forms the note states.
"""

import math
from decimal import Decimal, getcontext
from types import SimpleNamespace

import numpy as np
import pytest

from cells.core.specs import parse_spec
from cells.models.operators import species_reactions as sr
from cells.models.registry import get_model
from validation.tissue import species_reactions_fixtures as rfx

getcontext().prec = 50
R_SI = Decimal("6.02214076e23") * Decimal("1.380649e-23")  # N_A k_B, exact (SI 2019).
RT_PJ = Decimal("1e-3") * R_SI * Decimal("310")  # pJ/fmol at the fixtures' 310 K.
RT = float(RT_PJ)
CELL = {"cells": ["cell_0"]}


def bind(raw):
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    return spec, model, model.operators[0], state, p


def control(multiplier):
    return SimpleNamespace(reaction_multiplier=np.asarray(multiplier, dtype=float))


def step(op, state, p, multiplier, h):
    return op.half_step(state, h, control(multiplier), p, xp=np)


def row(spec, name):
    return list(spec.model.species_ids).index(name)


def amount(spec, state, p, name, node="cell_0"):
    s = row(spec, name)
    cells = [c.id for c in spec.model.cells]
    if node in cells:
        i = cells.index(node)
        return float(p.amount_reference[s, i] + state.amount_increment[s, i])
    i = [c.id for c in spec.model.extracellular].index(node)
    return float(
        p.extracellular_amount_reference[s, i] + state.extracellular_amount_increment[s, i]
    )


def set_amounts(spec, state, p, values):
    """state with the amounts {(species, node): fmol} set through the stored increments."""
    cell, outside = state.amount_increment.copy(), state.extracellular_amount_increment.copy()
    cells = [c.id for c in spec.model.cells]
    nodes = [c.id for c in spec.model.extracellular]
    for (name, node), value in values.items():
        s = row(spec, name)
        if node in cells:
            cell[s, cells.index(node)] = value - p.amount_reference[s, cells.index(node)]
        else:
            j = nodes.index(node)
            outside[s, j] = value - p.extracellular_amount_reference[s, j]
    return state._replace(amount_increment=cell, extracellular_amount_increment=outside)


def free_energy(spec, state, p, names, node, standard):
    """Appendix A's G at one node, Decimal: RT sum n (ln(n/V) - 1) + sum mu°' n."""
    cells = [c.id for c in spec.model.cells]
    volume = Decimal(
        float(p.volume[cells.index(node)])
        if node in cells
        else float(p.extracellular_volume[[c.id for c in spec.model.extracellular].index(node)])
    )
    total = Decimal(0)
    for name in names:
        n = Decimal(amount(spec, state, p, name, node))
        total += RT_PJ * n * ((n / volume).ln() - 1) + standard[name] * n
    return total


def standard_potentials(spec, op_index=0):
    """{species: mu°' (pJ/fmol, Decimal)} = RT (mu°/RT - ln c0) of the network's declaration."""
    declaration = spec.model.operators[op_index]
    c0 = Decimal(declaration.standard_concentration_mM)
    return {
        s.identity.id: RT_PJ * (Decimal(s.standard_mu_RT) - c0.ln()) for s in declaration.species
    }


# ------------------------------------------------------------------ closed forms


def test_open_linear_kinetics_follow_turnovers_closed_form_at_third_order():
    """0 -> S at P and S -> 0 at k (Appendix A: n(t) = n0 e^{-kt} + (P/k)(1 - e^{-kt}));
    SSPRK(3,3) is third order (probe 2b's B9: ratios 8.19 and 8.10)."""
    reactions = [
        rfx.mass_action("make", CELL, {}, {"S": 1}, 2e-4),
        rfx.mass_action("clear", CELL, {"S": 1}, {}, 0.5),
    ]
    raw = rfx.face_free_network(
        (),
        [rfx.species("S")],
        reactions,
        rfx.always(["make", "clear"]),
        profile=dict(S=dict(cell_0=1e-3)),
        end=4.0,
        dt=0.1,
    )
    spec, _, op, state, p = bind(raw)
    n0, P, k, T = amount(spec, state, p, "S"), 2e-4 * 1.0, 0.5, 4.0
    exact = n0 * math.exp(-k * T) + P / k * (1 - math.exp(-k * T))
    errors = []
    for h in (0.2, 0.1, 0.05):
        s = state
        for _ in range(int(round(T / h))):
            s, ok = step(op, s, p, [1.0, 1.0], h)
            assert ok
        errors.append(abs(amount(spec, s, p, "S") - exact) / exact)
    ratios = [errors[0] / errors[1], errors[1] / errors[2]]
    assert errors[0] < 1e-4 and all(7.0 < r < 9.0 for r in ratios), (errors, ratios)


def test_a_closed_passive_network_relaxes_to_its_potentials_and_books_its_free_energy():
    """S <-> P with mu°_P - mu°_S = -RT ln 10 relaxes to c_P/c_S = 10 (Appendix A); at a
    passive-only node every step books H = -dG >= 0 (to rounding), and the total heat is
    G(start) - G(end)."""
    spec, model, op, state, p = bind(rfx.passive_relaxation(end=40.0, dt=0.1))
    standard = standard_potentials(spec)
    start = free_energy(spec, state, p, ("S", "P"), "cell_0", standard)
    s = state
    for _ in range(800):  # 40 s at h = 0.05: (k_f + k_r) t = 44.
        previous = s
        s, ok = step(op, s, p, [1.0], 0.05)
        assert ok
        heat = s.reaction_dissipated_energy_pJ[0] - previous.reaction_dissipated_energy_pJ[0]
        magnitude = s.reaction_energy_magnitude_pJ[0] - previous.reaction_energy_magnitude_pJ[0]
        assert heat >= -2.5 * np.finfo(float).eps * magnitude
        assert s.reaction_work_pJ[0] == 0.0
    ratio = amount(spec, s, p, "P") / amount(spec, s, p, "S")
    assert abs(ratio / 10.0 - 1.0) < 1e-12, ratio
    end = free_energy(spec, s, p, ("S", "P"), "cell_0", standard)
    total = Decimal(float(s.reaction_dissipated_energy_pJ[0]))
    assert total > 0 and abs(total - (start - end)) <= Decimal("1e-12") * abs(start - end)


def test_michaelis_menten_depletion_follows_its_closed_form_at_third_order():
    """S -> P at V_max c_S / (K_M + c_S) (no catalyst): K_M ln(S0/S) + (S0 - S) = V_max t."""
    reactions = [rfx.michaelis_menten("deplete", CELL, "S", {"P": 1}, 1e-3, 5e-4)]
    raw = rfx.face_free_network(
        ("P",),
        [rfx.species("S", moieties={"X": 1}), rfx.species("P", moieties={"X": 1})],
        reactions,
        rfx.always(["deplete"]),
        profile=dict(S=dict(cell_0=1e-3)),
        end=0.5,
        dt=0.1,
    )
    spec, _, op, state, p = bind(raw)
    s0, km, vmax, T = amount(spec, state, p, "S"), 5e-4, 1e-3, 0.5  # 1 pL: fmol = mM.
    residuals = []
    for h in (0.05, 0.025, 0.0125):
        s = state
        for _ in range(int(round(T / h))):
            s, ok = step(op, s, p, [1.0], h)
            assert ok
        c = amount(spec, s, p, "S")
        residuals.append(abs(km * math.log(s0 / c) + (s0 - c) - vmax * T) / (vmax * T))
    ratios = [residuals[0] / residuals[1], residuals[1] / residuals[2]]
    assert residuals[0] < 1e-6 and all(7.0 < r < 9.0 for r in ratios), (residuals, ratios)


# ------------------------------------------------------------------ the bookings


MOIETIES = dict(S={"X": 1}, E={"Y": 1}, C={"X": 1, "Y": 1}, P={"X": 1})
NAMES = ("S", "E", "C", "P")


def random_case(rng, spec, state, p):
    """Random amounts (a decade either side of the profile), parameters and multipliers."""
    values = {}
    for name, nodes in rfx.ENZYME_PROFILE.items():
        for node, level in nodes.items():
            values[(name, node)] = level * 10 ** rng.uniform(-1, 1)
    state = set_amounts(spec, state, p, values)
    q = p._replace(
        reaction_rate_constant=np.asarray(p.reaction_rate_constant)
        * 10 ** rng.uniform(-0.5, 0.5, 5),
        reaction_standard_mu_RT=rng.uniform(-3, 3, 4),
        reaction_standard_concentration_mM=np.asarray(10 ** rng.uniform(-0.7, 0.3)),
        reaction_factor_half_saturation_mM=np.asarray(p.reaction_factor_half_saturation_mM)
        * 10 ** rng.uniform(-0.5, 0.5, np.shape(p.reaction_factor_half_saturation_mM)),
    )
    multiplier = np.where(rng.uniform(size=5) < 0.25, 0.0, 10 ** rng.uniform(-1, 0.5, 5))
    return state, q, multiplier


def test_the_bookings_are_exact_on_random_states():
    spec, _, op, base, p0 = bind(rfx.two_factor_network(c0=0.5))
    rng = np.random.default_rng(152)
    columns = dict(cell_0=0, ecs_0=1 + 1)  # The combined node axis: the cell, the bath, ecs_0.
    checked = dict(mixed=0, passive_only=0, driven_only=0)
    for i in range(45):
        state, p, m = random_case(rng, spec, base, p0)
        # A refused case may take the log of a non-positive stage before its refusal.
        if i % 3 == 1:  # The cell's driven routes off, its binding on: passive-only.
            m[[1, 3]], m[0] = 0.0, max(m[0], 0.5)
        elif i % 3 == 2:  # The binding off: the cell driven-only (or idle).
            m[0] = 0.0
        with np.errstate(invalid="ignore"):
            report = sr.stage_report(state, control(m), p, 0.1)
        if report["start_rate_per_s"] == 0:
            continue
        h = 0.2 / report["start_rate_per_s"]  # h L = 0.2 at the start.
        with np.errstate(invalid="ignore"):
            terms = sr.half_step_terms(state, m, h, p, xp=np)
            new, ok = op.half_step(state, h, control(m), p, xp=np)
        if not ok:
            continue
        mu = {
            s: RT_PJ
            * (Decimal(float(v)) - Decimal(float(p.reaction_standard_concentration_mM)).ln())
            for s, v in zip(NAMES, p.reaction_standard_mu_RT, strict=True)
        }
        routes = spec.model.operators[0].routes
        nu = np.asarray(p.reaction_products) - np.asarray(p.reaction_reactants)
        dxi = new.reaction_extent_fmol - state.reaction_extent_fmol
        start = sr.node_amounts(state, p, xp=np)
        change = np.where(terms.written, terms.dn, 0.0)
        volume = np.concatenate((p.volume, p.extracellular_volume))
        for node, column in columns.items():
            # The exact dG of the step's own move, n -> n + dn, in 50 digits (Appendix A).
            v = Decimal(float(volume[column]))
            exact = Decimal(0)
            for k, name in enumerate(NAMES):
                a = Decimal(float(start[k, column]))
                b = a + Decimal(float(change[k, column]))
                exact += RT_PJ * (b * ((b / v).ln() - 1) - a * ((a / v).ln() - 1))
                exact += mu[name] * (b - a)
            booked = Decimal(float(terms.work[column])) - Decimal(float(terms.heat[column]))
            scale = Decimal(float(terms.magnitude[column])) + Decimal("1e-30")
            assert abs(booked - exact) <= Decimal("1e-12") * scale, node
            # The stored states agree to the anchored representation's resolution.
            g0 = free_energy(spec, state, p, NAMES, node, mu)
            g1 = free_energy(spec, new, p, NAMES, node, mu)
            resolution = sum(
                8
                * Decimal(float(np.spacing(amount(spec, state, p, n, node))))
                * (abs(RT_PJ * (Decimal(amount(spec, state, p, n, node)) / v).ln()) + abs(mu[n]))
                for n in NAMES
            )
            assert abs(booked - (g1 - g0)) <= Decimal("1e-12") * scale + resolution, node
            at = [j for j, r in enumerate(routes) if r.node == node]
            resolution = 8 * max(np.spacing(amount(spec, state, p, n, node)) for n in NAMES)
            for name in NAMES:  # dn = nu dxi, row by row.
                k = NAMES.index(name)
                dn = amount(spec, new, p, name, node) - amount(spec, state, p, name, node)
                expected = math.fsum(nu[k, j] * dxi[j] for j in at)
                assert abs(dn - expected) <= 1e-12 * abs(expected) + resolution, (node, name)
            for moiety in ("X", "Y"):  # Moiety totals move only through sources and sinks.
                moved = math.fsum(
                    MOIETIES[name].get(moiety, 0)
                    * (amount(spec, new, p, name, node) - amount(spec, state, p, name, node))
                    for name in NAMES
                )
                opened = math.fsum(
                    sum(MOIETIES[name].get(moiety, 0) * nu[NAMES.index(name), j] for name in NAMES)
                    * dxi[j]
                    for j in at
                )
                assert abs(moved - opened) <= 1e-12 * abs(opened) + 4 * resolution
            standard = math.fsum(
                sum(float(mu[name]) * nu[NAMES.index(name), j] for name in NAMES) * dxi[j]
                for j in at
            )
            assert abs(float(terms.standard[column]) - standard) <= 1e-12 * float(scale)
            if terms.passive_only[column]:
                assert terms.heat[column] == -terms.free_energy[column]
                assert terms.work[column] == 0.0
                checked["passive_only"] += 1
            elif terms.driven_only[column]:
                assert terms.heat[column] == 0.0 and terms.work[column] == terms.free_energy[column]
                checked["driven_only"] += 1
            elif terms.mixed[column]:
                assert terms.work[column] == terms.free_energy[column] + terms.heat[column]
                checked["mixed"] += 1
    assert all(v > 0 for v in checked.values()), checked


# ------------------------------------------------------------------ the node class and the hybrid


def reversal_world():
    """A fast A <-> B pumps B past a slow B <-> C, which starts in reverse (C above B) and flips
    within the step: a passive route that reverses with no driven push. A driven C -> 0 shares the
    node (K = 1 throughout; A, B, C share moiety X)."""
    reactions = [
        rfx.passive("fast", CELL, {"A": 1}, {"B": 1}, 100.0),
        rfx.passive("slow", CELL, {"B": 1}, {"C": 1}, 1.0),
        rfx.mass_action("drain", CELL, {"C": 1}, {}, 1.0),
    ]
    species = [rfx.species(n, moieties={"X": 1}) for n in ("A", "B", "C")]
    profile = dict(A=dict(cell_0=1e-3), B=dict(cell_0=1e-6), C=dict(cell_0=1e-5))
    return rfx.face_free_network(
        ("A", "B", "C"),
        species,
        reactions,
        rfx.always(["fast", "slow", "drain"]),
        profile=profile,
        end=0.1,
        dt=0.01,
    )


def closed_form_heats(terms, state, p, h):
    """Each passive route's share and quadrature from Appendix A, written out here: the share
    -dxi_r sum_s nu_sr mu-bar_s with mu-bar_s = RT [ln(n/V) + (1 + x) log1p(x) / x - 1] + mu°'_s,
    and the quadrature h sum_k b_k RT J_r(Y_k) A_r(Y_k), b = (1/6, 1/6, 2/3)."""
    n = sr.node_amounts(state, p, xp=np)[:, 0]  # The cell.
    dn = np.where(terms.written[:, 0], terms.dn[:, 0], 0.0)
    standard = RT * (
        np.asarray(p.reaction_standard_mu_RT)
        - math.log(float(p.reaction_standard_concentration_mM))
    )
    mu = np.empty_like(n)
    for k, (a, d) in enumerate(zip(n, dn, strict=True)):
        x = d / a
        ratio = 1 + x / 2 - x * x / 6 if abs(x) < 1e-6 else (1 + x) * math.log1p(x) / x
        mu[k] = RT * (math.log(a / float(p.volume[0])) + ratio - 1) + standard[k]
    nu = np.asarray(p.reaction_products) - np.asarray(p.reaction_reactants)
    share = -terms.extent * (nu * mu[:, None]).sum(axis=0)
    (j1, j2, j3), (a1, a2, a3) = terms.rates, terms.affinities
    quadrature = h * RT * (j1 * a1 + j2 * a2 + 4 * j3 * a3) / 6
    return share, quadrature


def test_the_node_class_follows_its_multipliers_and_the_hybrid_its_signs():
    spec, _, op, state, p = bind(reversal_world())
    h = 0.004  # h L = 0.4 on the fast route.
    # The driven route switched off: passive-only, H = -dG and W = 0, although the slow route
    # reverses within the step (its branch would be the quadrature).
    off = sr.half_step_terms(state, np.array([1.0, 1.0, 0.0]), h, p, xp=np)
    assert off.valid and off.passive_only[0] and not off.mixed[0]
    assert off.nonreversing.tolist()[:2] == [True, False]
    assert off.heat[0] == -off.free_energy[0] and off.work[0] == 0.0 and off.heat[0] > 0
    # The passive routes switched off: driven-only, H = 0 and W = dG.
    driven = sr.half_step_terms(state, np.array([0.0, 0.0, 1.0]), h, p, xp=np)
    assert driven.valid and driven.driven_only[0]
    assert driven.heat[0] == 0.0 and driven.work[0] == driven.free_energy[0]
    # All on: mixed; the fast route keeps its sign (its share), the slow one reverses (its
    # quadrature), each against its closed form; W = dG + H.
    mixed = sr.half_step_terms(state, np.ones(3), h, p, xp=np)
    assert mixed.valid and mixed.mixed[0]
    (j1, j2, j3), end = mixed.rates, mixed.end_affinity
    signs = [np.sign(j1), np.sign(j2), np.sign(j3), np.sign(end)]
    rule = [  # Appendix A: three stage rates and the end-state affinity of one nonzero sign.
        bool(signs[0][i] != 0 and signs[1][i] == signs[0][i] == signs[2][i] == signs[3][i])
        for i in range(2)
    ]
    assert mixed.nonreversing.tolist()[:2] == rule == [True, False]
    share, quadrature = closed_form_heats(mixed, state, p, h)
    assert mixed.route_heat[0] == pytest.approx(share[0], rel=1e-12)
    assert mixed.route_heat[1] == pytest.approx(quadrature[1], rel=1e-12) and quadrature[1] > 0
    assert mixed.route_heat[2] == 0.0  # A driven route books no heat.
    assert mixed.heat[0] == pytest.approx(share[0] + quadrature[1], rel=1e-12)
    assert mixed.work[0] == mixed.free_energy[0] + mixed.heat[0]


def test_probe_2e_crossing_takes_the_quadrature_then_the_share():
    """The sink carries S below P within the first half-step: the passive route reverses there
    (quadrature, positive); once past the crossing it keeps its sign (share); every heat >= 0."""
    spec, _, op, state, p = bind(rfx.crossing(dt=0.1, sink=1.0, offset=0.01))
    h = 0.05
    first = sr.half_step_terms(state, np.ones(2), h, p, xp=np)
    assert first.valid and first.mixed[0] and not first.nonreversing[0]
    _, quadrature = closed_form_heats(first, state, p, h)
    assert first.route_heat[0] == pytest.approx(quadrature[0], rel=1e-12) and first.heat[0] > 0
    s, branches = state, []
    for _ in range(10):
        terms = sr.half_step_terms(s, np.ones(2), h, p, xp=np)
        branches.append(bool(terms.nonreversing[0]))
        assert terms.heat[0] >= 0
        s, ok = step(op, s, p, np.ones(2), h)
        assert ok
    assert branches[0] is False and all(branches[2:]), branches


# ------------------------------------------------------------------ the stage condition


def one_route(reaction, profile, species=("S", "P")):
    raw = rfx.face_free_network(
        tuple(n for n in species if n != "S"),
        [rfx.species(n, moieties={"X": 1}) for n in species],
        [reaction],
        rfx.always([reaction["id"]]),
        profile=profile,
        end=1.0,
        dt=0.1,
    )
    return bind(raw)


def test_the_stage_condition_reads_unidirectional_fluxes_and_refuses_beyond_one_half():
    # A first-order driven conversion: L = k at every stage.
    spec, _, op, state, p = one_route(
        rfx.mass_action("convert", CELL, {"S": 1}, {"P": 1}, 10.0),
        dict(S=dict(cell_0=1e-3), P=dict(cell_0=1e-6)),
    )
    for h, admitted in ((0.025, True), (0.049, True), (0.051, False), (0.09, False)):
        new, ok = step(op, state, p, [1.0], h)
        report = sr.stage_report(state, control([1.0]), p, 2 * h)
        assert bool(ok) is admitted and report["admitted"] is admitted, h
        assert report["max_hL"] == pytest.approx(10.0 * h, rel=1e-9)
        assert report["admissible_dt_at_start_s"] == pytest.approx(0.1, rel=1e-9)
    # A passive route running in reverse (P well above its equilibrium with S): its net rate is
    # negative, and the condition reads the reverse flux's consumption of P (k_r = 1/s), not the
    # signed net rate, which would read nothing for P (§4.2, the correction found in review).
    spec, _, op, state, p = one_route(
        rfx.passive("back", CELL, {"S": 1}, {"P": 1}, 1.0),
        dict(S=dict(cell_0=1e-6), P=dict(cell_0=1e-3)),
    )
    terms = sr.half_step_terms(state, np.ones(1), 0.4, p, xp=np)
    assert terms.rates[0][0] < 0 and terms.valid
    for h, admitted in ((0.4, True), (0.6, False)):
        _, ok = step(op, state, p, [1.0], h)
        assert bool(ok) is admitted, h


def test_a_trace_under_a_fast_sink_stays_positive_and_stalls_at_its_anchor():
    """§4.4: depletion keeps every amount positive at h L = 1/2; an amount cleared far below its
    anchor stalls near eps x the anchor, positive and unrefused; production from a 1e-15 mM trace is
    positive."""
    spec, _, op, state, p = one_route(
        rfx.mass_action("sink", CELL, {"S": 1}, {}, 9.9), dict(S=dict(cell_0=1e-3)), ("S",)
    )
    anchor = amount(spec, state, p, "S")
    s, history = state, []
    for _ in range(200):  # k t = 99 at h = 0.05 (h L = 0.495).
        s, ok = step(op, s, p, [1.0], 0.05)
        assert ok
        history.append(amount(spec, s, p, "S"))
    assert all(v > 0 for v in history)
    assert history[-1] <= 8 * np.spacing(anchor) and history[-1] > 0
    spec, _, op, state, p = one_route(
        rfx.mass_action("make", CELL, {}, {"S": 1}, 1e-3), dict(S=dict(cell_0=1e-15)), ("S",)
    )
    s, ok = step(op, state, p, [1.0], 0.05)
    assert ok and amount(spec, s, p, "S") > amount(spec, state, p, "S") > 0


# ------------------------------------------------------------------ pieces


def test_the_divided_potential_is_the_exact_divided_difference_across_its_series_boundary():
    spec, _, op, state, p = bind(rfx.passive_relaxation())
    net = sr.network(p, np.ones(1), xp=np)
    n = sr.node_amounts(state, p, xp=np)
    standard = standard_potentials(spec)
    volume = Decimal(float(p.volume[0]))
    for x in (-0.3, -1e-3, -1.0000001e-6, -0.9999999e-6, 1e-9, 0.9999999e-6, 1.0000001e-6, 0.4):
        dn = np.zeros_like(n)
        dn[0, 0] = x * n[0, 0]
        mean = sr.divided_potential(n, dn, net, xp=np)[0, 0]
        a = Decimal(float(n[0, 0]))
        b = a + Decimal(float(dn[0, 0]))

        def g(v):
            return RT_PJ * v * ((v / volume).ln() - 1) + standard["S"] * v

        exact = (g(b) - g(a)) / (b - a)
        assert abs(Decimal(float(mean)) - exact) <= Decimal("1e-13") * abs(exact), x


def test_hill_factors_match_their_closed_forms_from_the_trace_to_large_values():
    for law in ("hill_activation", "hill_inhibition"):
        reaction = rfx.mass_action(
            "convert", CELL, {"S": 1}, {"P": 1}, 1.0, factors=[rfx.hill(law, "E", 1e-3, 2.5)]
        )
        spec, _, op, state, p = one_route(reaction, dict(S=dict(cell_0=1e-3)), ("S", "P", "E"))
        net = sr.network(p, np.ones(1), xp=np)
        for x in (1e-15, 1e-9, 1e-4, 1e-3, 1e-1, 1e3):
            s = set_amounts(spec, state, p, {("E", "cell_0"): x})
            rate = sr.route_rates(sr.node_amounts(s, p, xp=np), net, p, xp=np).rate[0]
            factor = rate / amount(spec, s, p, "S")  # k V c_S = n_S at k = 1, V = 1 pL.
            # The stored amount (anchor + increment): an amount far below its anchor is resolved
            # to about eps x the anchor (§4.4), so the closed form takes the amount stored.
            stored = Decimal(amount(spec, s, p, "E"))
            xn, kn = stored ** Decimal(2.5), Decimal("1e-3") ** Decimal(2.5)
            exact = xn / (kn + xn) if law == "hill_activation" else kn / (kn + xn)
            assert abs(Decimal(float(factor)) - exact) <= Decimal("1e-13") * exact, (law, x)


def test_every_unused_branch_and_padded_entry_stays_finite_on_the_host():
    """The lead's ruling Q11 (a): every law and both factor kinds, padded cell and outside slots
    and padded factor slots, with NumPy raising on divide, invalid and overflow; and a planted zero
    padding (a padded factor's K) raises, so the check bites."""
    raw = rfx.two_factor_network(c0=0.5)
    raw["execution"]["capacity"] += 1
    raw["execution"]["extracellular_capacity"] += 1
    spec, _, op, state, p = bind(raw)
    assert np.asarray(p.reaction_factor_kind).shape == (5, 2)
    m = np.ones(5)
    with np.errstate(divide="raise", invalid="raise", over="raise"):
        terms = sr.half_step_terms(state, m, 1e-3, p, xp=np)
        new, ok = op.half_step(state, 1e-3, control(m), p, xp=np)
    assert ok and terms.valid
    for name in sr.Step._fields:
        assert np.all(np.isfinite(np.asarray(getattr(terms, name), dtype=float))), name
    for name, value in new._asdict().items():
        assert np.all(np.isfinite(np.asarray(value, dtype=float))), name
    kind = np.asarray(p.reaction_factor_kind)
    planted = p._replace(
        reaction_factor_half_saturation_mM=np.where(
            kind == 0, 0.0, p.reaction_factor_half_saturation_mM
        )
    )
    with np.errstate(divide="raise", invalid="raise", over="raise"):
        with pytest.raises(FloatingPointError):
            sr.half_step_terms(state, m, 1e-3, planted, xp=np)


def test_the_observed_rates_and_affinities():
    spec, model, op, state, p = bind(rfx.enzyme_network())
    columns = op.observe({}, state, control(np.ones(5)), p, None, model, spec)
    rates = sr.route_rates(
        sr.node_amounts(state, p, xp=np), sr.network(p, np.ones(5), xp=np), p, xp=np
    )
    assert columns["reaction_rate_fmol_per_s"].tolist() == rates.rate.tolist()
    affinity = columns["reaction_affinity_RT"]
    assert affinity[0] == rates.affinity[0] and affinity[0] != 0.0
    assert affinity[1:].tolist() == [0.0, 0.0, 0.0, 0.0]  # Driven routes.
    assert set(columns) == {*sr.STATE_AXES, *sr.READOUT_COLUMNS}
