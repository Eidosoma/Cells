"""FR-30's gates in series (src/cells/laws/junctions/junction_series_gates.py;
docs/JUNCTION_TWO_RELAXATION_DESIGN.md, option (A), as the lead ruled on 20 November 2026).

Host arithmetic only (NumPy), with no world compiled. Each claim with a planted error it must catch
(D187):
- S1: a boltzmann_eyring gate keeps detailed balance: α/β = exp(−u), and its steady state is the
  Boltzmann, whatever its split δ (planted: δ's voltage dependence on the opening rate only, a gate
  out of detailed balance, misses the Boltzmann);
- S2: two independent gates form a product chain that passes Kolmogorov's test on its four-state
  cycle, and whose stationary law gives the product of the gates' steady conductances (planted: a
  slow gate whose closing rate depends on the fast gate's state one way only fails the test);
- S3: the exact constant-voltage step is each gate's own exact step, and the junction's decay is
  the product of two exponential relaxations, against the four-state chain's master equation
  (planted: the slow gate stepped at the fast gate's rate; the product's cross term dropped);
- S4: a threshold_relaxation gate is junction_voltage_relaxation@1 itself, bitwise, so today's
  law is the one-gate case (planted: another residual moves the derivative);
- S5: a route's factor through the gates is the conductance for ions and the open fractions'
  product for a tracer whose residual is 0, never the conductance (planted: a tracer given g);
- S6: JunctionLaw's two defaulted fields keep every one-gate law as it was, and a several-gate law
  declares its conductance (planted: a two-gate declaration without one is refused); the domain's
  refusals;
- S7, @3's integration (D262; the @3 owner's rows): @3's parse admits the law where its gate
  declares development: true, the junction's conductance is the gates' product, the structure,
  state and layout hold the gates, the definition round-trips, @1 and @2 refuse it, and no step
  runs yet (planted: development false or absent);
- S8, v1's refusals: one gate law per world, no neutral species and no kind's passive route on a
  series junction, no composite or water family, no one-Rates kinetics (each with its case).

Cost: 1.83 s for the whole file on the timed lane (CPU 4 under the timed lock, at 4b23f252), most
of it importing the engine. Reason: the law's claims are host arithmetic.
"""

import math

import numpy as np
import pytest

from cells.laws.junctions import junction_gate
from cells.laws.junctions import junction_series_gates as series
from cells.laws.junctions import junction_voltage_relaxation as relaxation
from cells.registry.laws import JunctionLaw

BE = series.BoltzmannEyring
KINDS = ("boltzmann_eyring", "boltzmann_eyring")
FAST = BE(rate_per_s=40.0, slope_per_V=80.0, midpoint_V=0.050, split=0.3, residual=0.3)
SLOW = BE(rate_per_s=2.0, slope_per_V=60.0, midpoint_V=0.060, split=0.6, residual=0.6)


def test_a_boltzmann_eyring_gate_keeps_detailed_balance():
    rng = np.random.default_rng(30)
    for _ in range(50):
        p = BE(rate_per_s=float(rng.uniform(0.5, 50)), slope_per_V=float(rng.uniform(0, 300)),
               midpoint_V=float(rng.uniform(0, 0.1)), split=float(rng.uniform(0, 1)),
               residual=float(rng.uniform(0, 0.9)))  # fmt: skip
        v = float(rng.uniform(-0.12, 0.12))
        rate = series.boltzmann_eyring_kinetics(v, p, xp=np)
        u = p.slope_per_V * (abs(v) - p.midpoint_V)
        assert math.isclose(rate.alpha_per_s / rate.beta_per_s, math.exp(-u), rel_tol=1e-12)
        boltzmann = p.residual + (1 - p.residual) / (1 + math.exp(u))
        assert math.isclose(rate.target, boltzmann, rel_tol=1e-12)
        other = series.boltzmann_eyring_kinetics(v, p._replace(split=1 - p.split), xp=np)
        assert math.isclose(other.target, rate.target, rel_tol=1e-12)  # δ is kinetic only
    # Planted: the voltage dependence on the opening rate only (β constant), out of detailed
    # balance: its steady open fraction is not the Boltzmann.
    p, v = FAST, -0.1
    u = p.slope_per_V * (abs(v) - p.midpoint_V)
    alpha, beta = p.rate_per_s * math.exp(-p.split * u), p.rate_per_s
    planted = p.residual + (1 - p.residual) * alpha / (alpha + beta)
    assert not math.isclose(planted, series.boltzmann_eyring_kinetics(v, p, xp=np).target,
                            rel_tol=1e-6)  # fmt: skip


def chain(fast, slow, coupled=1.0):
    """The four-state generator of two gates, states (fast, slow) in oo, co, cc, oc order (o open,
    c closed); `coupled` multiplies the slow gate's closing rate when the fast gate is closed."""
    af, bf, as_, bs = fast.alpha_per_s, fast.beta_per_s, slow.alpha_per_s, slow.beta_per_s
    states = ("oo", "co", "cc", "oc")
    rate = {("oo", "co"): bf, ("co", "oo"): af, ("oc", "cc"): bf, ("cc", "oc"): af,
            ("oo", "oc"): bs, ("oc", "oo"): as_, ("co", "cc"): bs * coupled,
            ("cc", "co"): as_}  # fmt: skip
    q = np.zeros((4, 4))
    for (a, b), k in rate.items():
        q[states.index(a), states.index(b)] = k
    np.fill_diagonal(q, -q.sum(axis=1))
    return q, rate


def test_two_gates_form_a_product_chain_that_passes_kolmogorov():
    v = -0.1
    fast, slow = series.kinetics(v, (FAST, SLOW), kinds=KINDS, xp=np)
    q, rate = chain(fast, slow)
    cycle = ("oo", "co", "cc", "oc", "oo")
    forward = math.prod(rate[(a, b)] for a, b in zip(cycle, cycle[1:], strict=False))
    backward = math.prod(rate[(b, a)] for a, b in zip(cycle, cycle[1:], strict=False))
    assert math.isclose(forward, backward, rel_tol=1e-12)
    # The stationary law is the product of the gates', so the steady conductance is the product
    # of their targets.
    w, vecs = np.linalg.eig(q.T)
    pi = np.real(vecs[:, np.argmin(np.abs(w))])
    pi = pi / pi.sum()
    conductance = sum(
        p * (1.0 if s[0] == "o" else FAST.residual) * (1.0 if s[1] == "o" else SLOW.residual)
        for p, s in zip(pi, ("oo", "co", "cc", "oc"), strict=True)
    )
    assert math.isclose(conductance, series.steady(v, (FAST, SLOW), kinds=KINDS, xp=np),
                        rel_tol=1e-10)  # fmt: skip
    # Planted: the slow gate's closing rate doubled when the fast gate is closed, one way only.
    _, planted = chain(fast, slow, coupled=2.0)
    forward = math.prod(planted[(a, b)] for a, b in zip(cycle, cycle[1:], strict=False))
    backward = math.prod(planted[(b, a)] for a, b in zip(cycle, cycle[1:], strict=False))
    assert not math.isclose(forward, backward, rel_tol=1e-6)


def master(fast, slow, t):
    """The product chain's state probabilities at time t from all open (oo), by the master
    equation: p(t) = p(0) exp(Q t), the exponential through Q's eigen-decomposition."""
    q, _ = chain(fast, slow)
    w, vecs = np.linalg.eig(q)
    p0 = np.array([1.0, 0.0, 0.0, 0.0])
    return np.real(p0 @ vecs @ np.diag(np.exp(w * t)) @ np.linalg.inv(vecs))


def test_the_exact_step_is_each_gate_s_and_the_decay_two_relaxations():
    v, start, params = -0.1, (1.0, 1.0), (FAST, SLOW)
    rates = series.kinetics(v, params, kinds=KINDS, xp=np)
    states = ("oo", "co", "cc", "oc")
    weight = [(1.0 if s[0] == "o" else FAST.residual) * (1.0 if s[1] == "o" else SLOW.residual)
              for s in states]  # fmt: skip
    for t in (0.01, 0.1, 0.5, 2.0):
        exact = series.advance_clamped(start, v, params, t, kinds=KINDS, xp=np)
        g = series.conductance(exact, xp=np)
        # Independent: the four-state chain's master equation gives the same mean conductance.
        p = master(rates[0], rates[1], t)
        assert math.isclose(g, float(p @ np.asarray(weight)), rel_tol=1e-9)
        # The decay: a product of two exponential relaxations, k_fast and k_slow.
        closed = [r.target + (1 - r.target) * math.exp(-r.relaxation_per_s * t) for r in rates]
        assert math.isclose(g, closed[0] * closed[1], rel_tol=1e-12)
        # Planted: the slow gate stepped at the fast gate's rate.
        wrong = rates[1].target + (1 - rates[1].target) * math.exp(-rates[0].relaxation_per_s * t)
        assert not math.isclose(closed[0] * wrong, g, rel_tol=1e-6)
        # Planted: the product's cross term dropped (c_fast + c_slow - 1).
        assert not math.isclose(closed[0] + closed[1] - 1, g, rel_tol=1e-6)
    # Two clearly separated times at this voltage.
    assert rates[0].relaxation_per_s > 10 * rates[1].relaxation_per_s


def test_a_threshold_relaxation_gate_is_today_s_law_bitwise():
    p = relaxation.Parameters(threshold_voltage_V=0.017, minimum_open_fraction=0.112)
    kinds = ("threshold_relaxation", "boltzmann_eyring")
    for v in (-0.11, -0.04, 0.0, 0.03, 0.1):
        for c in (0.112, 0.5, 1.0):
            got = series.rhs((c, 1.0), v, (p, SLOW), kinds=kinds, xp=np)[0]
            assert got == relaxation.rhs(c, v, p, xp=np)
            step = series.advance_clamped((c, 1.0), v, (p, SLOW), 0.3, kinds=kinds, xp=np)[0]
            assert step == relaxation.advance_clamped(c, v, p, 0.3, xp=np)
            assert series.kinetics(v, (p, SLOW), kinds=kinds, xp=np)[0] == relaxation.kinetics(
                v, p, xp=np)  # fmt: skip
            # Planted: another residual moves the derivative wherever the gate can close.
            moved = series.rhs((c, 1.0), v, (p._replace(minimum_open_fraction=0.2), SLOW),
                               kinds=kinds, xp=np)[0]  # fmt: skip
            assert (moved != got) or c == 1.0 or relaxation.kinetics(v, p, xp=np).beta_per_s == 0
    assert junction_gate.series is series and junction_gate.SERIES_LAW_ID == series.LAW_ID


def test_routes_read_open_fractions_and_a_tracer_never_takes_the_conductance():
    v, params = -0.1, (FAST, SLOW)
    gates = series.advance_clamped((1.0, 1.0), v, params, 0.4, kinds=KINDS, xp=np)
    g = series.conductance(gates, xp=np)
    ions = series.route_factor(gates, params, (FAST.residual, SLOW.residual), kinds=KINDS, xp=np)
    assert math.isclose(ions, g, rel_tol=1e-12)
    x = series.open_fractions(gates, params, kinds=KINDS, xp=np)
    assert all(0 <= xi <= 1 for xi in x)
    tracer = series.route_factor(gates, params, (0.0, 0.0), kinds=KINDS, xp=np)
    assert math.isclose(tracer, x[0] * x[1], rel_tol=1e-12)
    assert tracer < g  # Planted: a tracer given the conductance would pass the residual states.


def test_junction_law_s_two_defaulted_fields_and_the_domain():
    from cells.registry import laws as law_registry

    today = law_registry.active().lookup(relaxation.LAW_ID)
    assert (today.gate_count, today.conductance) == (1, None) and today.errors() == []
    common = dict(host="cells.resolved_pump_tissue@3")
    good = JunctionLaw(series.LAW_ID, True, series.kinetics, series.rhs, series.domain_valid,
                       series.MAX_ABS_VOLTAGE_V, 2, series.conductance, **common)  # fmt: skip
    assert good.errors() == []
    planted = JunctionLaw(series.LAW_ID, True, series.kinetics, series.rhs, series.domain_valid,
                          series.MAX_ABS_VOLTAGE_V, 2, **common)  # fmt: skip
    assert "a law of several gates declares its conductance" in planted.errors()
    for count in (0, True, 1.5):
        bad = JunctionLaw(series.LAW_ID, True, series.kinetics, series.rhs, series.domain_valid,
                          series.MAX_ABS_VOLTAGE_V, count, series.conductance,
                          **common)  # fmt: skip
        assert "its gate count is a positive integer" in bad.errors()
    params = (FAST, SLOW)

    def valid(gates=(1.0, 1.0), v=-0.1, ps=params, availability=1.0):
        return bool(series.domain_valid(gates, v, ps, availability, kinds=KINDS, xp=np))

    assert valid()
    assert not valid(gates=(0.2, 1.0))  # below the fast gate's residual
    assert not valid(v=0.2)  # beyond the voltage bound
    assert not valid(ps=(FAST._replace(split=1.5), SLOW))
    assert not valid(ps=(FAST._replace(slope_per_V=1e4), SLOW))  # an exponent beyond the bound
    assert not valid(ps=(FAST._replace(rate_per_s=0.0), SLOW))
    assert not valid(availability=1.5)
    with pytest.raises(ValueError, match="2 gates"):
        series.kinetics(-0.1, params, kinds=("boltzmann_eyring",), xp=np)


# ------------------------------------------------------------------ @3's integration (D262)

SERIES_BLOCK = {
    "law": series.LAW_ID,
    "development": True,
    "gates": [
        {"kind": "threshold_relaxation", "threshold_voltage_V": 0.015,
         "minimum_open_fraction": 0.1, "initial": 0.8},
        {"kind": "boltzmann_eyring", "rate_per_s": 2.0, "slope_per_V": 50.0, "midpoint_V": 0.06,
         "split": 0.5, "residual": 0.3, "initial": 0.9},
    ],
}  # fmt: skip


def series_world(block=SERIES_BLOCK):
    """@3's closed fixture (two cells, one junction; Na, K, Cl and Ca) with its gate in series."""
    import copy

    from validation.tissue import surface_pump_v3_fixtures as fixtures

    raw = fixtures.definition("closed", solver="imex_ars222_face_electromigration@1")
    for junction in raw["model"]["junctions"]:
        junction["gate"] = copy.deepcopy(block)
    return raw


def test_at3_alone_admits_the_series_law_with_its_fields_and_round_trips():
    """S7, the integration's scaffold (D262): @3's parse admits the law where its gate declares
    development: true; the junction's conductance (junction_gate) is the gates' product, initially
    and at its floor; the structure holds the gates' kinds, the state their factors and the layout
    their parameters, [gate, ..., edge], with padded slots at 0; the definition round-trips; @1's
    and @2's parses refuse the law, and a failed @3 parse leaves nothing admitted; and no step runs
    until the step is built (planted: development false, or absent)."""
    import copy

    from cells.definitions import surface_kinetic_spec as kinetic
    from cells.definitions import surface_pump_spec as first
    from cells.definitions import surface_pump_v3_spec as spec3
    from cells.definitions.specs import ConfigError, parse_spec
    from cells.models import surface_pump_v3 as v3
    from cells.registry.models import get_model
    from validation.tissue import surface_pump_v2_fixtures as fixtures_v2

    spec = parse_spec(series_world())
    (junction,) = spec.model.junctions
    assert isinstance(junction, kinetic.SeriesJunction) and junction.development is True
    assert junction.initial_gate == 0.8 * 0.9 and junction.minimum_open_fraction == 0.1 * 0.3
    impl = get_model(spec.model)
    assert impl.structure.junction_series_kinds == ("threshold_relaxation", "boltzmann_eyring")
    state, layout = impl.initial_values(spec)
    gates, parameters = getattr(state, v3.SERIES_GATES), getattr(layout, v3.SERIES_PARAMETERS)
    np.testing.assert_array_equal(gates, [[0.8, 0.0], [0.9, 0.0]])
    np.testing.assert_array_equal(state.junction_gate, [0.8 * 0.9, 0.0])
    declared = [[0.015, 0.1, 0, 0, 0], [2, 50, 0.06, 0.5, 0.3]]
    np.testing.assert_array_equal(parameters[:, :, 0], declared)
    assert v3.SERIES_GATES in impl.OBSERVATION_FIELDS and not np.any(parameters[:, :, 1])
    again = spec3.to_dict(spec)
    assert again["model"]["junctions"][0]["gate"] == SERIES_BLOCK
    assert parse_spec(copy.deepcopy(again)).fingerprint == spec.fingerprint
    with pytest.raises(ConfigError, match="step is not built yet"):
        impl.bind_step_checks(spec)(np.array([spec.execution.dt]))
    for planted in (False, None):
        block = copy.deepcopy(SERIES_BLOCK)
        block.pop("development") if planted is None else block.update(development=planted)
        with pytest.raises(ConfigError, match="development"):
            parse_spec(series_world(block))
    assert first._ADMITTED_GATES.get() == ()  # The failed parses left nothing admitted.
    raw = fixtures_v2.definition("closed", solver="imex_ars222_face_electromigration@1")
    for j in raw["model"]["junctions"]:
        j["gate"] = copy.deepcopy(SERIES_BLOCK)
    with pytest.raises(ConfigError):  # @2, and @1 through it, refuse the law.
        parse_spec(raw)


def test_the_series_law_runs_in_at3_alone_on_ions_only():
    """S8, v1's refusals (D262), each with its case: one gate law per world; no neutral species
    on a series junction (its factor is the ionic conductance); no kind's passive route on one; no
    composite, the water families included (the adapter's refusal); and no one-Rates junction
    kinetics."""
    import copy
    import dataclasses
    from types import SimpleNamespace

    from cells.definitions import surface_kinetic_spec as kinetic
    from cells.definitions import surface_pump_v3_spec as spec3
    from cells.definitions.specs import ConfigError, parse_spec
    from cells.registry.models import get_model
    from validation.tissue import pump_water_fixtures as water
    from validation.tissue import secreted_species_fixtures as sfx

    spec = parse_spec(series_world())
    (junction,) = spec.model.junctions
    ions = (("Na", 1), ("K", 1), ("Cl", -1), ("Ca", 2))

    def model(junctions, species=ions):
        ids, valence = zip(*species, strict=True)
        return SimpleNamespace(junctions=junctions, species_ids=ids, valence=valence)

    spec3.series_junction_errors(model((junction,)))  # Admitted.
    one_gate = kinetic.Junction(
        **{k: getattr(junction, k) for k in kinetic.Junction.__dataclass_fields__}
    )
    with pytest.raises(ConfigError, match="one gate law"):
        spec3.series_junction_errors(model((junction, one_gate)))
    neutral = dataclasses.replace(
        junction, permeability_m_per_s=(*junction.permeability_m_per_s, 1e-9)
    )
    with pytest.raises(ConfigError, match="neutral species"):
        spec3.series_junction_errors(model((neutral,), (*ions, ("S", 0))))
    with pytest.raises(ConfigError, match="runs in @3 alone"):
        parse_spec(water.with_water(series_world(), pf_m_s=5e-4, bath_pressure_Pa=12.5))
    impl, (_, layout) = get_model(spec.model), get_model(spec.model).initial_values(spec)
    with pytest.raises(ConfigError, match="one Rates per gate"):
        impl.junction_kinetics(np.zeros(2), layout, xp=np)
    raw = sfx.world(
        cells=(("cell_0", 1.0), ("cell_1", 1.0)), nodes=(), contacts=(), faces=(),
        junctions=(("j_0", "cell_0", "cell_1"),),
        concentrations_mM={"cell_0": 1e-3, "cell_1": 1e-3},
    )  # fmt: skip
    raw["model"]["junctions"][0]["gate"] = copy.deepcopy(SERIES_BLOCK)
    raw["model"]["passive_routes"] = [
        dict(id="s_route", junction="j_0", law="passive_neutral_permeation@1", species="S",
             permeability_m_per_s=1e-9)
    ]  # fmt: skip
    with pytest.raises(ConfigError, match="passive route"):
        parse_spec(raw)
