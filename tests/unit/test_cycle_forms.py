"""Cycle forms (laws/cycles/forms.py; the kinds owner's design statement 1, §3 and §5.1).

Each claim is checked against an independent computation, with a planted error it must catch
(D187). The diagrams here are this file's own; none comes from the seam-A references.
- errors(): a form that keeps its contract is admitted, a net-flow mode with a signed weight among
  them; planted breaches are refused by name (a role without a row, a count naming a non-integer
  parameter, a factor on a row the form lacks, a diagram whose declared cycles miss one of its Hill
  cycles, a count that disagrees with its edges' orders, a net-flow weight of 0, of inf or of
  nan);
- the topology: simple cycles and spanning trees counted against closed forms (a cycle graph, a
  triangle with a parallel edge, a figure-eight, K4);
- Wegscheider at parse (§5.1): decided algebraically, exactly (integers, rationals, 50 digits); a
  diagram built consistent in binary64 is admitted inside 32 eps (T + N), and each plant (the
  constant x(1 + 1e-9), a voltage exponent off by 1e-3, a non-dyadic split) lands where its
  derivation says;
- the kernels: the diagram's steady state against a linear solve of its master equation, its Hill
  cycles' net fluxes against every edge's net flux (completeness), the exact slopes against central
  differences (an analytic zero checked too, against the differences' floor, never skipped), and
  the Hill saturation's log S and gradient against their closed forms.
"""

import math
import re
from decimal import Decimal, localcontext
from fractions import Fraction

import numpy as np
import pytest

from cells.laws.electrochemistry import F, R
from cells.laws.cycles import forms
from cells.laws.cycles.forms import (
    CycleForm,
    Diagram,
    Edge,
    FluxTerm,
    Parameter,
    Rate,
    Saturation,
)

EPS = np.finfo(float).eps
U = EPS / 2
T_K = 310.0


# ------------------------------------------------------------------ the test diagrams


def consistent(states, steps, mu, *, k_forward, standard_mM=1000.0, c0_mM=1000.0):
    """Edges whose constants satisfy every cycle's Wegscheider condition by construction: state
    energies G (in RT), and per edge k0- = k0+ exp(G_target - G_source + sum o- mu' - sum o+ mu'),
    mu' = mu°/RT - ln c0 + ln c° per (role, end) row, computed in binary64 (a producer's few
    roundings, which §5.1's band admits). steps: (id, source, target, orders+, orders-, zeta+,
    zeta-); mu: {row: mu°/RT} for every row an order names."""
    g = {name: 0.37 * k - 0.11 * k * k for k, name in enumerate(states)}
    shift = math.log(standard_mM) - math.log(c0_mM)
    edges = []
    for (eid, i, j, plus, minus, z_plus, z_minus), kf in zip(steps, k_forward, strict=True):
        mu_plus = sum(o * (mu[(r, e)] + shift) for r, e, o in plus)
        mu_minus = sum(o * (mu[(r, e)] + shift) for r, e, o in minus)
        kb = kf * math.exp(g[states[j]] - g[states[i]] + mu_minus - mu_plus)
        edges.append(Edge(eid, i, j, Rate(kf, plus, z_plus), Rate(kb, minus, z_minus)))
    return tuple(edges)


# A four-state electrogenic pump: 2 H from N to P, ATP hydrolysed at N.
PUMP_ROWS = (("H", "N"), ("H", "P"), ("ATP", "N"), ("ADP", "N"), ("Pi", "N"))
PUMP_ROLES = (("H", 1), ("ATP", 0), ("ADP", 0), ("Pi", 0))
PUMP_MU = {("H", "N"): 0.0, ("H", "P"): 0.0, ("ATP", "N"): 12.0, ("ADP", "N"): 0.4, ("Pi", "N"): -0.3}
PUMP_STEPS = (
    ("bind", 0, 1, (("H", "N", 2),), (), 0.0, 0.0),
    ("fuel", 1, 2, (("ATP", "N", 1),), (("ADP", "N", 1), ("Pi", "N", 1)), 0.0, 0.0),
    ("cross", 2, 3, (), (("H", "P", 2),), 0.75, -1.25),
    ("reset", 3, 0, (), (), 0.0, 0.0),
)
PUMP_COUNTS = (-2, 2, -1, 1, 1)


def pump_form(*, counts=PUMP_COUNTS, k=(5e4, 2e3, 3e3, 8e2), edges=None, cycles=None):
    edges = edges or consistent(("E", "EH", "EH*", "E'"), PUMP_STEPS, PUMP_MU, k_forward=k)
    cycles = cycles or (("pump", (("bind", 1), ("fuel", 1), ("cross", 1), ("reset", 1))),)
    return CycleForm(
        kinetics="diagram",
        roles=PUMP_ROLES,
        rows=PUMP_ROWS,
        modes=(("pump", counts),),
        diagram=Diagram(("E", "EH", "EH*", "E'"), edges, cycles, rate_scale_per_s=1e3),
    )


# A slip exchanger: three carrier states (empty A, X-bound B, Y-bound C) and two parallel edges from
# C to A, releasing Y at N (back) or at P (slip): three Hill cycles, the exchange, an X leak and a
# Y shuttle, sharing edges.
SLIP_ROWS = (("X", "N"), ("X", "P"), ("Y", "N"), ("Y", "P"))
SLIP_ROLES = (("X", 1), ("Y", 0))
SLIP_MU = {("X", "N"): -2.0, ("X", "P"): -2.0, ("Y", "N"): 1.5, ("Y", "P"): 1.5}
SLIP_STEPS = (
    ("load", 0, 1, (("X", "N", 1),), (), 0.0, 0.0),
    ("swap", 1, 2, (("Y", "P", 1),), (("X", "P", 1),), 0.5, -0.5),
    ("back", 2, 0, (), (("Y", "N", 1),), 0.0, 0.0),
    ("slip", 2, 0, (), (("Y", "P", 1),), 0.0, 0.0),
)


def slip_form(cycles=None, counts=None):
    edges = consistent(("A", "B", "C"), SLIP_STEPS, SLIP_MU, k_forward=(4e3, 9e2, 2e3, 30.0))
    cycles = cycles or (
        ("exchange", (("load", 1), ("swap", 1), ("back", 1))),
        ("leak", (("load", 1), ("swap", 1), ("slip", 1))),
        ("shuttle", (("back", 1), ("slip", -1))),
    )
    counts = counts or {
        "exchange": (-1, 1, 1, -1),
        "leak": (-1, 1, 0, 0),
        "shuttle": (0, 0, 1, -1),  # Y from P to N: back releases it at N, slip reversed takes it at P
    }
    return CycleForm(
        kinetics="diagram",
        roles=SLIP_ROLES,
        rows=SLIP_ROWS,
        modes=tuple((mode, counts[mode]) for mode, _ in cycles),
        diagram=Diagram(("A", "B", "C"), edges, cycles, rate_scale_per_s=1e3),
    )


# ------------------------------------------------------------------ errors()


def test_a_form_that_keeps_its_contract_is_admitted_and_planted_breaches_are_refused():
    assert pump_form().errors() == []
    assert slip_form().errors() == []
    factored = CycleForm(
        kinetics="factored",
        roles=(("Z", 0), ("ATP", 0)),
        rows=(("Z", "N"), ("Z", "P"), ("ATP", "N")),
        modes=(("cyc", ("-n", "n", -1)),),
        parameters=(Parameter("n", "1", 1, 4, integer=True, positive=True), Parameter("K", "mM", positive=True)),
        saturation=((Saturation(("Z", "N"), "K", "n"),),),
    )
    assert factored.errors() == []
    exchange = (-1, 1, 1, -1)  # A net-flow mode booked J_X - J_C: one signed weight (a cycle basis).
    signed = CycleForm(
        kinetics="net_flow",
        roles=(("X", 1), ("Y", 0)),
        rows=(("X", "N"), ("X", "P"), ("Y", "N"), ("Y", "P")),
        modes=(("m", exchange),),
        flux_terms=((FluxTerm(0.5, exchange), FluxTerm(-0.25, exchange)),),
    )
    assert signed.errors() == []

    def weighted(w):
        return signed._replace(flux_terms=((FluxTerm(0.5, exchange), FluxTerm(w, exchange)),))

    plants = {
        "roles \\['Q'\\] have no row": factored._replace(roles=(*factored.roles, ("Q", 0))),
        "is an integer or an integer parameter's name": factored._replace(
            modes=(("cyc", ("-K", "K", -1)),)
        ),
        "Saturations on its rows": factored._replace(
            saturation=((Saturation(("Z", "P"), "K", "n"), Saturation(("ATP", "P"), 1.0, 1)),)
        ),
        "gives no diagram data": factored._replace(diagram=pump_form().diagram),
        "miss the Hill cycle through": slip_form(
            cycles=(
                ("exchange", (("load", 1), ("swap", 1), ("back", 1))),
                ("leak", (("load", 1), ("swap", 1), ("slip", 1))),
            )
        ),
        "coefficient of ln a at H@P is -1": pump_form(counts=(-2, 1, -1, 1, 1)),
        "do not form one directed cycle": pump_form(
            cycles=(("pump", (("bind", 1), ("fuel", -1), ("cross", 1), ("reset", 1))),)
        ),
    }
    for reason, form in plants.items():
        found = "; ".join(form.errors())
        assert re.search(reason, found), (reason, found)
    for w in (0.0, 0, math.inf, -math.inf, math.nan):  # A weight of 0, or not finite.
        found = "; ".join(weighted(w).errors())
        assert re.search("a finite nonzero weight", found), (w, found)
    # Named rates (D228 item 1, version 2): a cycle that converts nothing may leave a k0 and a
    # zeta to each population; resolved() gives one population's form, and the form itself where
    # it names none; the numeric consumers refuse a named rate.
    slip = slip_form()
    load, swap = slip.diagram.edges[:2]
    params = (Parameter("k_load", "1/s", positive=True), Parameter("z_swap", "1"))
    named = slip._replace(
        parameters=params,
        diagram=slip.diagram._replace(
            edges=(
                load._replace(forward=load.forward._replace(k0_per_s="k_load")),
                swap._replace(backward=swap.backward._replace(zeta="-z_swap")),  # -(0.5).
                *slip.diagram.edges[2:],
            )
        ),
    )
    assert named.errors() == []
    values = {"k_load": load.forward.k0_per_s, "z_swap": -swap.backward.zeta}
    assert forms.resolved(named, values).diagram == slip.diagram
    assert forms.resolved(slip, values) is slip and forms.resolved(factored, {}) is factored
    for consumer in (forms.diagram_tables, lambda f: forms.wegscheider(f, 0, {}, {}, 1000.0)):
        with pytest.raises(ValueError, match="resolve the form for one population first"):
            consumer(named)
    pump = pump_form()
    bind = pump.diagram.edges[0]
    fuelled = pump._replace(
        parameters=(Parameter("k_bind", "1/s", positive=True),),
        diagram=pump.diagram._replace(
            edges=(bind._replace(forward=bind.forward._replace(k0_per_s="k_bind")),
                   *pump.diagram.edges[1:]),
        ),
    )  # fmt: skip
    named_plants = (
        ("each rate has a positive k0", named._replace(
            parameters=(params[0]._replace(positive=False), params[1]))),  # k0 not positive.
        ("each rate has a positive k0", named._replace(parameters=params[:1])),  # -z_swap: none.
        ("a cycle that converts a species gives every k0 on its edges as a number", fuelled),  # E3.
    )  # fmt: skip
    for reason, form in named_plants:
        found = "; ".join(form.errors())
        assert re.search(reason, found), (reason, found)
    with pytest.raises(ValueError, match="resolve the form for one population first"):
        forms.implied_free_energy(fuelled, 0)  # A named k0: seam E's constants refuse it too.


# ------------------------------------------------------------------ the topology


@pytest.mark.parametrize(
    "n,pairs,cycles,trees",
    [
        (4, [(0, 1), (1, 2), (2, 3), (3, 0)], 1, 4),  # C4: one cycle, n spanning trees
        (3, [(0, 1), (1, 2), (2, 0), (2, 0)], 3, 5),  # a triangle with a parallel edge
        (5, [(0, 1), (1, 2), (2, 0), (0, 3), (3, 4), (4, 0)], 2, 9),  # a figure-eight: 3 x 3
        (4, [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)], 7, 16),  # K4: 7 cycles, 4^(4-2)
    ],
)
def test_simple_cycles_and_spanning_trees_match_their_closed_forms(n, pairs, cycles, trees):
    assert len(forms.simple_cycles(n, pairs)) == cycles
    assert len(forms.spanning_trees(n, pairs)) == trees  # Kirchhoff's counts, by hand above.


# ------------------------------------------------------------------ Wegscheider at parse (§5.1)

VALENCE = {"H": 1, "ATP": 0, "ADP": 0, "Pi": 0}
POTENTIAL = {"H": 0.0, "ATP": 12.0, "ADP": 0.4, "Pi": -0.3}


def test_wegscheider_is_decided_exactly_and_a_consistent_law_sits_inside_its_band():
    w = forms.wegscheider(pump_form(), 0, VALENCE, POTENTIAL, 1000.0)
    assert all(b == 0 for *_, b in w.coefficients)
    assert w.psi == 0  # 0.75 + 1.25 = 2 = q exactly: dyadic load fractions.
    assert w.admitted
    assert abs(w.constant) <= w.band
    # Honest construction in binary64: a few eps of the terms, far inside 32 eps (T + N).
    assert abs(w.constant) < 4 * Decimal(EPS) * (w.terms + w.constants)
    # Independent: the constant summed in Fractions of the declared doubles' exact logs to 50 digits.
    with localcontext() as ctx:
        ctx.prec = 50
        total = Decimal(0)
        for e in pump_form().diagram.edges:
            total += Decimal(e.forward.k0_per_s).ln() - Decimal(e.backward.k0_per_s).ln()
        total += Decimal(12.0) * -1 + Decimal("0.4") * 0 + Decimal(0.4) + Decimal(-0.3)
    assert abs(total - w.constant) < Decimal("1e-40")


def test_wegscheider_plants_land_where_their_derivations_say():
    form = pump_form()
    base = form.diagram.edges
    # The constant x (1 + 1e-9): r0 moves by ln(1 + 1e-9), about 1e-9, far above 32 eps (T + N).
    scaled = (base[0]._replace(forward=base[0].forward._replace(k0_per_s=base[0].forward.k0_per_s * (1 + 1e-9))), *base[1:])
    w = forms.wegscheider(form._replace(diagram=form.diagram._replace(edges=scaled)), 0, VALENCE, POTENTIAL, 1000.0)
    assert not w.admitted and abs(float(w.constant)) == pytest.approx(1e-9, rel=1e-3)
    # The voltage exponent off by 1e-3: B_psi = 1e-3, about 1e13 psi bands.
    tilted = (*base[:2], base[2]._replace(forward=base[2].forward._replace(zeta=0.751)), base[3])
    w = forms.wegscheider(form._replace(diagram=form.diagram._replace(edges=tilted)), 0, VALENCE, POTENTIAL, 1000.0)
    assert not w.admitted and float(w.psi) == pytest.approx(1e-3, rel=1e-9)
    # A non-dyadic split that sums to q in decimals (0.3 + 1.7 = 2, whose doubles do not: their
    # representation errors do not cancel): inside its band of u sum |zeta|, admitted.
    split = (*base[:2], base[2]._replace(forward=base[2].forward._replace(zeta=0.3), backward=base[2].backward._replace(zeta=-1.7)), base[3])
    w = forms.wegscheider(form._replace(diagram=form.diagram._replace(edges=split)), 0, VALENCE, POTENTIAL, 1000.0)
    assert w.psi != 0 and abs(w.psi) <= w.psi_band and w.admitted
    assert w.psi == Fraction(0.3) + Fraction(1.7) - 2  # Exact rationals of the declared doubles.


# ------------------------------------------------------------------ the kernels


def padded(form):
    """One population's diagram tables as the kind's layout holds them ([.., 1] each)."""
    x = forms.diagram_tables(form)
    k = len(form.rows)
    t = dict(
        log_k0=x.log_k0[:, None], orders=x.orders[:, :, None], zeta=x.zeta[:, None],
        term_slots=x.term_slots[:, :, None], term_root=x.term_root[:, None],
        term_present=np.ones((len(x.term_root), 1), bool), plus_slots=x.plus_slots[:, :, None],
        minus_slots=x.minus_slots[:, :, None], cut_slots=x.cut_slots[:, :, :, None],
        cut_present=x.cut_present[:, :, None], edge_states=x.edge_states[:, :, None],
        state_present=np.ones((len(form.diagram.states), 1), bool),
        log_scale=np.array([math.log(form.diagram.rate_scale_per_s)]),
        ln_standard=np.array([math.log(form.diagram.standard_state_mM)]),
    )  # fmt: skip
    t["term_orders"] = t["orders"][t["term_slots"][:, :, 0], :, 0].sum(axis=1)[:, :, None]
    t["term_zeta"] = t["zeta"][t["term_slots"][:, :, 0], 0].sum(axis=1)[:, None]
    t["plus_orders"] = t["orders"][t["plus_slots"][:, :, 0], :, 0].sum(axis=1)[:, :, None]
    t["plus_zeta"] = t["zeta"][t["plus_slots"][:, :, 0], 0].sum(axis=1)[:, None]
    t["cut_orders"] = t["orders"][t["cut_slots"][:, :, :, 0], :, 0].sum(axis=2)[:, :, :, None]
    t["cut_zeta"] = t["zeta"][t["cut_slots"][:, :, :, 0], 0].sum(axis=2)[:, :, None]
    assert t["orders"].shape[1] == k
    return __import__("types").SimpleNamespace(**t)


def master_equation(form, ln_c, psi):
    """The carrier's steady state by a 50-digit Gaussian elimination of its master equation
    (independent of the directional diagrams; float64 would not do, since the rates span tens of
    orders of magnitude), and each edge's two rates, at ln c [K] (mM) and psi. Decimals."""
    d = form.diagram
    rows = {row: k for k, row in enumerate(form.rows)}
    with localcontext() as ctx:
        ctx.prec = 50
        ln_a = [Decimal(float(v)) - Decimal(d.standard_state_mM).ln() for v in ln_c]

        def rate(r):
            power = sum((o * ln_a[rows[(a, b)]] for a, b, o in r.orders), Decimal(0))
            return Decimal(r.k0_per_s) * (power + Decimal(r.zeta) * Decimal(float(psi))).exp()

        n = len(d.states)
        q = [[Decimal(0)] * n for _ in range(n)]
        alphas = []
        for e in d.edges:
            f, b = rate(e.forward), rate(e.backward)
            alphas.append((f, b))
            q[e.target][e.source] += f
            q[e.source][e.source] -= f
            q[e.source][e.target] += b
            q[e.target][e.target] -= b
        a = [row[:] + [Decimal(0)] for row in q[:-1]] + [[Decimal(1)] * n + [Decimal(1)]]
        for col in range(n):  # Partial pivoting; the normalisation replaces the last balance row.
            pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
            a[col], a[pivot] = a[pivot], a[col]
            for r in range(n):
                if r != col and a[r][col] != 0:
                    factor = a[r][col] / a[col][col]
                    a[r] = [x - factor * y for x, y in zip(a[r], a[col], strict=True)]
        p = [a[i][n] / a[i][i] for i in range(n)]
        nets = [p[e.source] * f - p[e.target] * b for e, (f, b) in zip(d.edges, alphas, strict=True)]
        return p, alphas, nets  # The edge nets taken at 50 digits, before any cancellation.


STATES = [
    (np.log([1e-4, 2e-5, 3.0, 0.3, 3.0]), 0.0),
    (np.log([5e-5, 1e-4, 0.5, 2.0, 1.0]), 2.1),
    (np.log([2e-4, 1e-6, 9.0, 0.01, 7.0]), -3.4),
]


@pytest.mark.parametrize("ln_c,psi", STATES)
def test_the_diagram_steady_state_and_cycle_fluxes_match_the_master_equation(ln_c, psi):
    for form, ln in ((pump_form(), ln_c), (slip_form(), np.log([3.0, 0.4, 1.2, 0.7]) + 0.1 * psi)):
        t = padded(form)
        d = forms.diagram_logs(t, np.asarray(ln)[:, None], np.array([psi]), xp=np)
        p, alphas, nets = master_equation(form, np.asarray(ln), psi)
        np.testing.assert_allclose(d.occupancy[: len(p), 0], [float(v) for v in p], rtol=1e-12)
        # Hill: each cycle's one-way fluxes Pi+- Sigma_k / Sigma per carrier (the engine's, in
        # float64), whose signed sums over the cycles through each edge equal that edge's net flux
        # (completeness), here against the 50-digit steady state. Tolerance, derived: each log
        # alpha carries u times its terms A_d = |ln k0| + sum |order ln a| + |zeta psi| (up to 8
        # roundings with the logsumexps), and log j sums at most n of them, so each j is within
        # 8 u n max_d A_d of itself, relatively; the bound is that times (j+ + j-) over the cycles.
        share = np.exp(d.log_share[:, 0])
        plus, minus = share * np.exp(d.log_plus[:, 0]), share * np.exp(d.log_minus[:, 0])
        ln_a = np.asarray(ln) - math.log(form.diagram.standard_state_mM)
        terms = np.abs(t.log_k0[:, 0]) + np.abs(t.orders[:, :, 0] * ln_a[None]).sum(1)
        terms = terms + np.abs(t.zeta[:, 0] * psi)
        relative = 8 * U * len(form.diagram.states) * float(terms.max())
        ids = {e.id: k for k, e in enumerate(form.diagram.edges)}
        for k, e in enumerate(form.diagram.edges):
            through = [
                (m, sign) for m, (_, steps) in enumerate(form.diagram.cycles) for eid, sign in steps
                if ids[eid] == k
            ]  # fmt: skip
            exact = nets[k]
            signed = sum(sign * (plus[m] - minus[m]) for m, sign in through)
            bound = relative * sum(plus[m] + minus[m] for m, _ in through)
            assert abs(float(exact) - signed) <= bound, (e.id, float(exact), signed, bound)
        # Planted: the slip form with its 2-cycle dropped misses the slip edge's flux.
        if len(form.diagram.cycles) == 3:
            k = ids["slip"]
            e = form.diagram.edges[k]
            exact = float(nets[k])
            dropped = sum(
                s * (plus[m] - minus[m]) for m, (_, steps) in enumerate(form.diagram.cycles[:2])
                for eid, s in steps if ids[eid] == k
            )  # fmt: skip
            assert abs(exact - dropped) > 1e6 * relative * (plus + minus).sum()


@pytest.mark.parametrize("ln_c,psi", STATES)
def test_the_diagram_slopes_are_exact_against_central_differences(ln_c, psi):
    form = pump_form()
    t = padded(form)

    def log_s(ln, ps):
        return forms.diagram_logs(t, ln[:, None], np.array([ps]), xp=np).log_s[0, 0]

    d = forms.diagram_logs(t, ln_c[:, None], np.array([psi]), xp=np)
    h = 1e-6
    for k in range(len(ln_c)):
        step = np.zeros_like(ln_c)
        step[k] = h
        fd = (log_s(ln_c + step, psi) - log_s(ln_c - step, psi)) / (2 * h)
        floor = 1e-8  # Central differences' own error at h = 1e-6 (truncation and rounding).
        assert abs(d.d_log_s_d_ln_c[0, k, 0] - fd) <= floor, k  # An analytic zero is checked too.
    fd = (log_s(ln_c, psi + h) - log_s(ln_c, psi - h)) / (2 * h)
    assert abs(d.d_log_s_d_psi[0, 0] - fd) <= 1e-8
    # Planted: a wrong slope (the exponents' mean taken without the Pi+ part) fails.
    wrong = d.d_log_s_d_ln_c[0, :, 0] - t.plus_orders[0, :, 0]
    fd_all = np.array([(log_s(ln_c + h * np.eye(len(ln_c))[k], psi) - log_s(ln_c - h * np.eye(len(ln_c))[k], psi)) / (2 * h) for k in range(len(ln_c))])
    assert np.max(np.abs(wrong - fd_all)) > 1e-3


def test_the_hill_saturation_and_its_gradient_are_their_closed_forms():
    ln_c = np.log(np.array([[1e-4, 5e-5], [2e-4, 3e-3], [3.0, 0.05]]))  # [K=3, P=2]
    row = np.array([[[0, 2]], [[1, 2]]]).reshape(1, 2, 2)  # [M=1, F=2, P=2]: rows (0, 2) and (1, 2)
    row = np.array([[[0, 1], [2, 2]]])  # population 0 reads rows 0 and 2; population 1 rows 1 and 2
    log_k = np.log(np.array([[[1e-4, 1e-4], [0.1, 0.1]]]))
    hill = np.array([[[2.0, 3.0], [1.0, 1.0]]])
    present = np.ones((1, 2, 2), bool)
    log_s, grad = forms.hill_log_saturation(row, log_k, hill, present, ln_c, xp=np)
    for p in range(2):
        rows = row[0, :, p]
        s = 1.0
        for f in range(2):
            c = math.exp(ln_c[rows[f], p])
            s *= 1.0 / (1.0 + (math.exp(log_k[0, f, p]) / c) ** hill[0, f, p])
        assert log_s[0, p] == pytest.approx(math.log(s), rel=1e-14, abs=0)
        for k in range(3):
            step = np.zeros_like(ln_c)
            step[k, p] = 1e-6
            up = forms.hill_log_saturation(row, log_k, hill, present, ln_c + step, xp=np)[0][0, p]
            down = forms.hill_log_saturation(row, log_k, hill, present, ln_c - step, xp=np)[0][0, p]
            assert abs(grad[0, k, p] - (up - down) / 2e-6) <= 1e-8, (p, k)


def test_the_sign_exact_flux_carries_the_sign_of_minus_x_at_every_argument():
    rng = np.random.default_rng(3)
    x = np.concatenate([rng.uniform(-80, 80, 4000), [0.0, -0.0, 1e-300, -1e-300, 5e-324]])
    log_plus = rng.uniform(-120, 40, x.size)
    j = forms.sign_exact_flux(log_plus, x, xp=np)
    assert np.all(j * x <= 0.0)
    # J's sign is -x's, or J is zero where |J+ (1 - e^x)| underflows (x within 1e-300 of 0 here).
    assert np.all((np.sign(j) == -np.sign(x)) | ((j == 0) & (np.abs(x) < 1e-290)))
    np.testing.assert_allclose(j, np.exp(log_plus) * -np.expm1(x), rtol=1e-12, atol=0.0)
    # Planted: a backward flux taken by another path, as a diagram's own Pi- Sigma_k / Sigma is
    # (it differs from J+ e^x by e^-r, r a Wegscheider residual of about 1e-15; the 17:33 ruling),
    # runs against x within |r| of equilibrium; the contract's form keeps the sign there.
    near = rng.choice([-1.0, 1.0], 2000) * 10.0 ** rng.uniform(-17, -14, 2000)
    lp = rng.uniform(-50, 50, near.size)
    other_path = np.exp(lp) - np.exp(lp + near + 1e-15)
    assert np.any((other_path != 0) & (np.sign(other_path) == np.sign(near)))
    exact = forms.sign_exact_flux(lp, near, xp=np)
    assert np.all(np.sign(exact) == -np.sign(near))


def test_logsumexp_and_softmax_count_only_the_masked_in_terms():
    v = np.array([[1.0, 2.0], [800.0, -5.0], [3.0, 1e308]])
    mask = np.array([[True, True], [False, True], [True, False]])
    lse = forms.logsumexp(v, mask, 0, xp=np)
    assert lse[0] == pytest.approx(math.log(math.exp(1.0) + math.exp(3.0)))
    assert lse[1] == pytest.approx(math.log(math.exp(2.0) + math.exp(-5.0)))
    w = forms.softmax(v, mask, 0, xp=np)
    np.testing.assert_allclose(w.sum(axis=0), 1.0)
    assert w[1, 0] == 0.0 and w[2, 1] == 0.0
    assert forms.logsumexp(v, np.zeros_like(mask), 0, xp=np)[0] == -np.inf
