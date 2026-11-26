"""cells.route.inward_rectifier_linear_driving_force@1 (laws/routes/inward_rectifier_linear_driving_force.py;
D228 item 2) on cells.kind.passive_routes@1: an instantaneous inward rectifier at valence +1.

Each claim with its plant (D187), on the closed pair (cell_0 and its finite node ecs_0 joined only
by contact_0, the cell at K 140 and Na 10 mM) with one rectifier route on contact_0 carrying K:
- the law registers, hosted by the kind, its stage term a kernel of its own module; a route parses
  and binds, its fields existing only where it is declared (planted, each refused naming its
  field: s <= 0, K_ref <= 0, g_ref < 0, a non-finite and a missing coefficient, a junction host, a
  row of valence 0, the patch's own K permeability, and K at zero at one end, by the host);
- the kernel keeps §3.2's structural properties at random coefficients: I = 0 exactly at V = E,
  the sign of u, the square root of c_o at fixed u, rectification referred to E, zero opening,
  and heat = I u >= 0 (planted, each breaking one: u = V + E, q of V, c_o linear);
- its absolute units: I from hand-set SI inputs, the flux in fmol/s and the heat in pJ/s (planted:
  a unit factor);
- its stage term: |dI/dV| at the stage's potentials (a central difference), and without them a
  voltage-free bound over a dense scan of u (planted: the slope without its magnitude, and the
  bound without its V_h term);
- the kind: above E the cell's K falls and the route's transfer is negative, another species at
  zero at an end keeps the flux and heat finite, the domain refuses K at zero, and a run passes
  every host ledger (material, charge and energy, with the heat never negative);
- extreme but finite declarations: (b g_ref, b^2 K_ref) is one route. Each row is a claim with
  its plant, the law's concentration factor replaced:
  - at ordinary K_ref the kernels keep the bits of the unguarded sqrt(c_o / K_ref), in numpy and
    compiled (planted: the split form everywhere, and a selected divisor in the direct form);
  - (2^-8, 2^-14 mM) matches (1, 4 mM) bit for bit, in the kernels and in a run (planted:
    c_o / K_ref without its root);
  - (2^-512, 2^-1022 mM) overflows c_o / K_ref and is admitted, and (2^510, 5 2^1020 mM) at c_o
    below 1.25 mM underflows it, which compiled code turned into a silent zero current. Each
    matches its ordinary twin within ULPS (planted: the unguarded root);
  - the derivatives in c_i, c_o, V and the opening, forward and reverse, are finite at both
    extremes and match the twins within ULPS (planted: a single where, whose reverse derivative
    in c_o is NaN at the underflow).
"""

import contextlib
import copy
import functools
import math

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.execution.runner import run
from cells.kinds import passive_routes
from cells.laws.electrochemistry import F
from cells.laws.routes import inward_rectifier_linear_driving_force as law
from cells.registry import laws as law_registry
from cells.registry.models import get_model
from validation.tissue import secreted_species_fixtures as fx

EPS = np.finfo(float).eps
COEFFICIENTS = dict(g_ref_S_per_m2=1.0, k_ref_mM=5.0, v_half_V=0.1, slope_V=0.05)  # Weak.


def route(rid="rectifier_0", **keys):
    return {
        "id": rid,
        "patch": "contact_0",
        "law": law.LAW_ID,
        "species": "K",
        **COEFFICIENTS,
        **keys,
    }


def closed_pair(*routes, end=0.02, dt=1e-3):
    """FR-1's face-free pair as a plain @3 definition, the cell at K 140 and Na 10 mM (its charge
    unchanged), with the routes on contact_0."""
    raw = fx.face_free(end=end, dt=dt)
    m = raw["model"]
    m["id"] = "cells.model.resolved_pump_tissue@3"
    m.pop("inner_model")
    m.pop("operators")
    cell = m["cells"][0]
    cell["initial_amount_fmol"] |= dict(K=140.0 * cell["volume_pL"], Na=10.0 * cell["volume_pL"])
    m[passive_routes.MODEL_KEY] = list(routes) or [route()]
    return raw


def bound(raw):
    spec = parse_spec(copy.deepcopy(raw))
    impl = get_model(spec.model)
    state, p = impl.initial_values(spec)
    control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
    return spec, impl, state, p, control


def potentials_at(p, volts):
    """Node potentials (cells, then outside nodes) with the route's patch at V."""
    out = np.zeros(p.active.size + p.outside_active.size)
    out[p.passive_inside[0]] = volts
    return out


# ------------------------------------------------------------------ registration and parse


def test_the_law_registers_and_a_route_parses_binds_and_refuses_its_plants():
    registered = law_registry.active().lookup(law.LAW_ID)
    assert registered is law.LAW and registered.host == passive_routes.KIND_ID
    assert passive_routes.hosted_laws()[law.LAW_ID] is law.LAW and law.LAW.errors() == []
    assert callable(getattr(law, law.LAW.stage_term))  # A kernel of its own module.
    assert law.LAW.hosts == ("membrane",) and law.LAW.provenance == "cited"
    spec, _, _, p, _ = bound(closed_pair())
    (declared,) = dict(spec.model.kinds)[passive_routes.KIND_ID]
    assert isinstance(declared, passive_routes.RectifierRoute)
    assert (declared.inside, declared.outside, declared.species) == ("cell_0", "ecs_0", "K")
    assert set(passive_routes.RECTIFIER_FIELDS) <= set(type(p)._fields)
    k = list(spec.model.species_ids).index("K")
    assert p.passive_rectifier_g[k, 0] == 1.0 and np.count_nonzero(p.passive_rectifier_g) == 1
    assert spec.to_dict()["model"][passive_routes.MODEL_KEY] == [route()]  # Written back whole.
    # Without the law, no rectifier field: the neutral route's definition keeps today's layout.
    neutral = dict(
        id="s_0", patch="contact_0", law=passive_routes.LAW_ID, species=fx.SPECIES,
        permeability_m_per_s=1e-9,
    )  # fmt: skip
    _, _, _, p_neutral, _ = bound(closed_pair(neutral))
    assert not set(passive_routes.RECTIFIER_FIELDS) & set(type(p_neutral)._fields)
    # Planted, each refused naming its field.
    junction = {**route(), "junction": "j_0"}
    junction.pop("patch")
    raw_own = closed_pair()
    raw_own["model"]["membranes"][1]["permeability_m_per_s"]["K"] = 1e-9  # contact_0 itself.
    raw_zero = closed_pair()
    raw_zero["model"]["extracellular"][1]["initial_amount_fmol"]["K"] = 0.0  # ecs_0.
    missing = route()
    missing.pop("k_ref_mM")
    for raw, reason in (
        (closed_pair(route(slope_V=0.0)), "slope_V is positive"),
        (closed_pair(route(k_ref_mM=-5.0)), "k_ref_mM is positive"),
        (closed_pair(route(k_ref_mM=5e-324)), "k_ref_mM is a normal float"),  # Subnormal.
        (closed_pair(route(g_ref_S_per_m2=-1.0)), "g_ref_S_per_m2 is >= 0"),
        (closed_pair(route(v_half_V=math.inf)), "v_half_V is finite"),
        (closed_pair(missing), "declares id, law, patch, species"),
        (closed_pair(junction), "sits on a membrane patch"),
        (closed_pair(route(species=fx.SPECIES)), "carries a valence \\+1 row"),
        (raw_own, "has its own permeability for K"),
        (raw_zero, "amount must be finite and positive"),  # The host's parse, first.
    ):
        with pytest.raises(ConfigError, match=reason):
            parse_spec(raw)


# ------------------------------------------------------------------ the kernel


def kernel_failures(current, reversal, heat, *, seed=7):
    """The structural properties (§3.2) a kernel breaks, by name, at random coefficients and
    states: current(c_in, c_out, V, T, A, g, K_ref, V_h, s, m) in A, reversal(c_in, c_out, T) in V,
    heat(...) in pJ/s, with the current's arguments."""
    rng = np.random.default_rng(seed)
    n = 64
    c_in, c_out = rng.uniform(1.0, 200.0, n), rng.uniform(0.5, 50.0, n)
    t, area, g = rng.uniform(280.0, 320.0, n), rng.uniform(1e-12, 1e-9, n), rng.uniform(0.1, 3, n)
    k_ref, v_half = rng.uniform(1.0, 20.0, n), rng.uniform(-0.05, 0.05, n)
    s, m = rng.uniform(0.005, 0.05, n), rng.uniform(0.1, 1.0, n)
    u = rng.choice((-1.0, 1.0), n) * rng.uniform(0.02, 0.15, n)  # Away from 0: u's rounding.

    def at(c_i, c_o, volts, opening=m):
        return current(c_i, c_o, volts, t, area, g, k_ref, v_half, s, opening)

    e = reversal(c_in, c_out, t)
    out = []
    if np.any(at(c_in, c_out, e) != 0.0):
        out.append("zero at E")
    i = at(c_in, c_out, e + u)
    if np.any(np.sign(i) != np.sign(u)):
        out.append("sign of u")
    quadrupled = at(c_in, 4 * c_out, reversal(c_in, 4 * c_out, t) + u)
    if np.any(np.abs(quadrupled / i - 2.0) > 1e-10):
        out.append("square root of c_o")
    other = at(3 * c_in, c_out, reversal(3 * c_in, c_out, t) + u)  # E moves; u and c_o do not.
    if np.any(np.abs(other / i - 1.0) > 1e-10):
        out.append("rectification referred to E")
    if np.any(at(c_in, c_out, e + u, opening=0.0 * m) != 0.0):
        out.append("zero opening")
    dissipated = heat(c_in, c_out, e + u, t, area, g, k_ref, v_half, s, m)
    exact = 1e12 * i * (e + u - e)  # The kernel's own u.
    if np.any(dissipated < 0) or np.any(np.abs(dissipated - exact) > 64 * EPS * dissipated):
        out.append("heat I u")
    return out


def test_the_kernel_keeps_its_structural_properties_and_each_plant_breaks_one():
    def current(*a):
        return law.current_A(*a, xp=np)

    def reversal(c_in, c_out, t):
        return law.reversal_V(c_in, c_out, t, xp=np)

    def heat(*a):
        return law.heat_pJ_s(*a, xp=np)

    assert kernel_failures(current, reversal, heat) == []

    def plus_e(c_in, c_out, volts, t, area, g, k_ref, v_half, s, m):  # Planted: u = V + E.
        e = law.reversal_V(c_in, c_out, t, xp=np)
        return law.current_A(c_in, c_out, volts + 2 * e, t, area, g, k_ref, v_half, s, m, xp=np)

    def absolute(c_in, c_out, volts, t, area, g, k_ref, v_half, s, m):  # Planted: q of V.
        u = volts - law.reversal_V(c_in, c_out, t, xp=np)
        q, _ = law.rectification(volts, v_half, s, xp=np)
        return m * area * g * np.sqrt(c_out / k_ref) * q * u

    def linear(c_in, c_out, volts, t, area, g, k_ref, v_half, s, m):  # Planted: c_o linear.
        root = law.current_A(c_in, c_out, volts, t, area, g, k_ref, v_half, s, m, xp=np)
        return root * np.sqrt(c_out / k_ref)

    assert "zero at E" in kernel_failures(plus_e, reversal, heat)
    assert "rectification referred to E" in kernel_failures(absolute, reversal, heat)
    assert "square root of c_o" in kernel_failures(linear, reversal, heat)


def test_its_absolute_units_from_hand_set_si_inputs_and_a_planted_unit_factor():
    c_in, c_out, volts, t = 140.0, 5.0, -0.05, 310.0
    area, g, k_ref, v_half, s, m = 1e-9, 2.0, 5.0, 0.01, 0.02, 0.5
    e = 8.314462618 * t / 96485.33212 * math.log(c_out / c_in)  # V, CODATA's R and F.
    u = volts - e
    q = 1.0 / (1.0 + math.exp((u - v_half) / s))
    current = m * area * g * math.sqrt(c_out / k_ref) * q * u  # A, outward.
    args = (c_in, c_out, volts, t, area, g, k_ref, v_half, s, m)
    assert float(law.current_A(*args, xp=np)) == pytest.approx(current, rel=1e-9, abs=0)
    flux = float(law.flux_fmol_s(*args, xp=np))  # fmol/s inward: -I/F mol/s.
    assert flux == pytest.approx(-current / 96485.33212 * 1e15, rel=1e-9, abs=0)
    assert flux < 0 < current  # Above E: K leaves the cell.
    heat = float(law.heat_pJ_s(*args, xp=np))  # pJ/s: I u W.
    assert heat == pytest.approx(current * u * 1e12, rel=1e-9, abs=0) and heat > 0
    # Planted: a flux in pmol/s (1e12 for 1e15) misses the hand value.
    planted = -1e12 * float(law.current_A(*args, xp=np)) / F
    assert planted != pytest.approx(-current / 96485.33212 * 1e15, rel=1e-3, abs=0)


# ------------------------------------------------------------------ the stage term


def slope_failures(slope, bound_fn, *, seed=11):
    """Where a stage term breaks its claims: |dI/dV| against a central difference of the law's
    current, and the voltage-free bound against a dense scan of u."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(24):
        c_in, c_out, t = rng.uniform(5, 200), rng.uniform(0.5, 50), 300.0
        area, g, k_ref = 1e-10, rng.uniform(0.1, 3), rng.uniform(1, 20)
        v_half, s, m = rng.uniform(-0.2, 0.2), rng.uniform(0.002, 0.05), rng.uniform(0.1, 1)
        e = law.reversal_V(c_in, c_out, t, xp=np)
        u = np.linspace(-0.4, 0.4, 4001)  # Dense in u, past the bend at either sign of V_h.
        volts = e + u
        local = slope(c_in, c_out, volts, t, area, g, k_ref, v_half, s, m)
        h = 1e-7
        diff = (
            law.current_A(c_in, c_out, volts + h, t, area, g, k_ref, v_half, s, m, xp=np)
            - law.current_A(c_in, c_out, volts - h, t, area, g, k_ref, v_half, s, m, xp=np)
        ) / (2 * h)
        scale = m * area * g * math.sqrt(c_out / k_ref)
        if np.any(np.abs(local - np.abs(diff)) > 1e-5 * scale):
            out.append("magnitude of dI/dV")
        ceiling = bound_fn(c_in, c_out, t, area, g, k_ref, v_half, s, m)
        if np.any(np.abs(diff) > ceiling):
            out.append("voltage-free bound")
    return sorted(set(out))


def test_the_stage_term_is_the_slope_magnitude_or_its_voltage_free_bound():
    def slope(*a):
        return law.slope_conductance_S(*a, xp=np)

    def ceiling(*a):
        return law.slope_bound_S(*a, xp=np)

    assert slope_failures(slope, ceiling) == []

    def signed(c_in, c_out, volts, t, area, g, k_ref, v_half, s, m):  # Planted: no magnitude.
        scale, q, q1q, u = law._terms(c_in, c_out, volts, t, area, g, k_ref, v_half, s, m, xp=np)
        return scale * (q - u * q1q / s)

    def flat(c_in, c_out, t, area, g, k_ref, v_half, s, m):  # Planted: no V_h term.
        return law.slope_bound_S(c_in, c_out, t, area, g, k_ref, 0.0, s, m, xp=np)

    assert slope_failures(signed, ceiling) == ["magnitude of dI/dV"]
    assert slope_failures(slope, flat) == ["voltage-free bound"]
    # The kind's term: each route's magnitude at both of its patch's ends, or the bound.
    spec, _, state, p, control = bound(closed_pair())
    volts = -0.02
    nodes = passive_routes.stage_term(state, potentials_at(p, volts), control, p, xp=np)
    c_in, c_out = passive_routes._ends(state, p, np)
    k = list(spec.model.species_ids).index("K")
    args = (c_in[k, 0], c_out[k, 0], volts, p.temperature, p.passive_area[0], 1.0, 5.0, 0.1, 0.05)
    expected = float(law.slope_conductance_S(*args, 1.0, xp=np))
    inside, outside = p.passive_inside[0], p.passive_outside[0]
    assert nodes[inside] == nodes[outside] == pytest.approx(expected, rel=4 * EPS, abs=0)
    assert np.count_nonzero(nodes) == 2
    free = passive_routes.stage_term(state, None, control, p, xp=np)
    voltage_free = float(law.slope_bound_S(*args[:2], *args[3:], 1.0, xp=np))
    assert free[inside] == pytest.approx(voltage_free, rel=4 * EPS, abs=0)
    assert free[inside] > nodes[inside] and free[outside] == free[inside]


# ------------------------------------------------------------------ the kind


def test_the_kind_moves_k_out_above_e_keeps_its_domain_and_a_run_closes_every_ledger():
    raw = closed_pair()
    spec, impl, state, p, control = bound(raw)
    ids = list(spec.model.species_ids)
    k = ids.index("K")
    e = float(law.reversal_V(140.0, 5.0, spec.model.temperature_K, xp=np))
    assert e < -0.08  # The cell's E_K.
    # Above E (the cell at 0 V): outward, so the transfer (inward-positive) is negative.
    rates = passive_routes.rates(state, potentials_at(p, 0.0), control, p, xp=np)
    flux = rates.derivatives["passive_transferred"]
    assert flux[k, 0] < 0 and np.count_nonzero(flux) == 1
    assert rates.cell[k, 0] == flux[k, 0] < 0 and rates.heat_pJ_s > 0
    s1, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
    assert bool(valid) and s1.amount_increment[k, 0] < 0 < s1.passive_dissipated_energy_pJ[0]
    moved = float(s1.passive_transferred[k, 0])  # K at the cell: moved by nothing else.
    assert float(s1.amount_increment[k, 0]) == pytest.approx(moved, rel=8 * EPS, abs=0)
    # Another species at zero at an end: the route's flux and heat stay finite.
    na = ids.index("Na")
    outside = state.extracellular_amount_increment.copy()
    node = p.passive_outside[0] - p.active.size
    outside[na, node] = -p.extracellular_amount_reference[na, node]  # Na at ecs_0: zero.
    zeroed = state._replace(extracellular_amount_increment=outside)
    with np.errstate(divide="ignore", invalid="ignore"):  # The other laws' logs, discarded.
        rates = passive_routes.rates(zeroed, potentials_at(p, 0.0), control, p, xp=np)
    assert np.all(np.isfinite(rates.derivatives["passive_transferred"]))
    assert np.isfinite(rates.heat_pJ_s) and rates.heat_pJ_s > 0
    assert bool(passive_routes.domain(zeroed, p, xp=np))  # Na is not the route's row.
    outside[k, node] = -p.extracellular_amount_reference[k, node]  # K at ecs_0: zero.
    no_k = state._replace(extracellular_amount_increment=outside)
    assert not bool(passive_routes.domain(no_k, p, xp=np))
    # A run: the host checks every ledger (material, charge, energy with the heat), heat >= 0.
    result = run(parse_spec(raw))
    final = result.final.state
    assert final.passive_transferred[k, 0] < 0 and final.passive_dissipated_energy_pJ[0] > 0


# ------------------------------------------------------------------ extreme but finite declarations

# A few ulps: the split form's two roots and its division, carried through the kernels' products.
# Measured on 19 November 2026: at most 3 on the values and 4 on the derivatives.
ULPS = 8
KERNELS = ("current_A", "flux_fmol_s", "heat_pJ_s", "slope_conductance_S", "slope_bound_S")
FACTOR = law.concentration_factor
# Each extreme declaration (g_ref, K_ref) with its ordinary twin and the c_o values (mM) it is read
# at; a twin is the same route, (b g_ref, b^2 K_ref) from (g_ref, K_ref).
TWINS = {  # Three c_o each, so one compiled function serves a row's twin and its extreme.
    "b_minus_8": ((1.0, 4.0), (2.0**-8, 2.0**-14), (5.0, 50.0, 140.0)),
    "b_minus_512_overflow": ((1.0, 4.0), (2.0**-512, 2.0**-1022), (5.0, 50.0, 140.0)),
    "b_510_underflow": ((1.0, 5.0), (2.0**510, 5.0 * 2.0**1020), (1e-10, 3e-7, 0.25)),
}
RUNS = ("b_minus_8", "b_minus_512_overflow")  # The rows also compared in a run of the pair.


def unguarded(c_out_mM, k_ref_mM, *, xp):
    """The concentration factor as the law landed (0ef9cb71): sqrt(c_o / K_ref), unguarded."""
    return xp.sqrt(c_out_mM / k_ref_mM)


def split_everywhere(c_out_mM, k_ref_mM, *, xp):  # Planted: the split form at every input.
    return xp.sqrt(c_out_mM) / xp.sqrt(k_ref_mM)


def selected_divisor(c_out_mM, k_ref_mM, *, xp):
    """Planted: the law with its direct form's divisor selected too, which compiled code no longer
    divides as a product with K_ref's reciprocal (an ulp off at some ordinary states)."""
    quotient = c_out_mM / k_ref_mM
    info = xp.finfo(xp.result_type(quotient))
    split = (c_out_mM >= info.tiny) & (k_ref_mM >= info.tiny)
    split = split & ((quotient < info.tiny) | (quotient > info.max))
    direct = xp.sqrt(xp.where(split, 1.0, c_out_mM) / xp.where(split, 1.0, k_ref_mM))
    return xp.where(split, FACTOR(c_out_mM, k_ref_mM, xp=xp), direct)


def rootless(c_out_mM, k_ref_mM, *, xp):  # Planted: c_o / K_ref without its root.
    return c_out_mM / k_ref_mM


def single_where(c_out_mM, k_ref_mM, *, xp):  # Planted: the direct form on its raw inputs.
    quotient = c_out_mM / k_ref_mM
    info = xp.finfo(xp.result_type(quotient))
    normal = (quotient >= info.tiny) & (quotient <= info.max)
    return xp.where(normal, xp.sqrt(quotient), FACTOR(c_out_mM, k_ref_mM, xp=xp))


@contextlib.contextmanager
def factor(replacement):
    """The law's concentration factor replaced for the block (a plant, or the unguarded root)."""
    saved = law.concentration_factor
    law.concentration_factor = replacement
    try:
        yield
    finally:
        law.concentration_factor = saved


def kernels(args, xp):
    """The five kernels stacked, at the current's arguments (the bound drops V)."""
    values = [getattr(law, name)(*args, xp=xp) for name in KERNELS[:-1]]
    return xp.stack([*values, law.slope_bound_S(*args[:2], *args[3:], xp=xp)])


def in_numpy(args):
    with np.errstate(over="ignore", invalid="ignore"):  # A plant's overflow is a finding here.
        return np.asarray(kernels(args, np))


def compiled():
    """The kernels compiled afresh: a new function, so a plant is traced, never a cached law."""
    function = jax.jit(lambda *a: kernels(a, jnp))
    return lambda args: np.asarray(function(*args))


def states(declaration, c_out):
    """The current's arguments at c_i 140 mM, each c_o, the opening 0.6 or 1, and V at 0 V and at
    four drives about E: 310 K, 1e-10 m^2, V_h 0.1 V and s 0.05 V."""
    rows = []
    for c_o, opening in [(c, m) for c in c_out for m in (0.6, 1.0)]:
        e = float(law.reversal_V(140.0, c_o, 310.0, xp=np))
        rows += [(140.0, c_o, v, opening) for v in (0.0, e - 0.12, e - 0.015, e + 0.015, e + 0.12)]
    c_in, c_o, volts, opening = np.array(rows).T
    return (c_in, c_o, volts, 310.0, 1e-10, *declaration, 0.1, 0.05, opening)


def ordinary_states(seed=13):
    """Random ordinary arguments in the kind's layout ([species, route], each coefficient per
    route, g_ref nonzero at one row a route) and as flat vectors: compiled code divides by a
    broadcast K_ref as a product with its reciprocal, and by a full one exactly. A divisor that
    loses that rewrite moves about one conducting value in nine by an ulp, so the kind's layout
    holds 96 routes."""
    rng = np.random.default_rng(seed)
    s, r, n = 4, 96, 64

    def uniform(low, high, shape):
        return rng.uniform(low, high, shape)

    g = np.zeros((s, r))
    g[rng.integers(0, s, r), np.arange(r)] = uniform(0.1, 3.0, r)
    kind = (uniform(1.0, 200.0, (s, r)), uniform(0.5, 50.0, (s, r)), uniform(-0.15, 0.1, r), 310.0,
            uniform(1e-12, 1e-9, r), g, uniform(0.3, 20.0, r), uniform(-0.05, 0.05, r),
            uniform(0.005, 0.05, r), uniform(0.1, 1.0, r))  # fmt: skip
    flat = (uniform(1.0, 200.0, n), uniform(0.5, 50.0, n), uniform(-0.15, 0.1, n),
            uniform(280.0, 320.0, n), uniform(1e-12, 1e-9, n), uniform(0.1, 3.0, n),
            uniform(0.3, 20.0, n), uniform(-0.05, 0.05, n), uniform(0.005, 0.05, n),
            uniform(0.1, 1.0, n))  # fmt: skip
    return kind, flat


def derivatives():
    """d/d(c_i, c_o, V, m) of the current and the heat at each state, forward (jacfwd) and reverse
    (grad), compiled afresh (as compiled) with every coefficient an argument: [current/heat and
    mode, argument, state]."""

    def one(c_i, c_o, v, t, area, g, k_ref, v_half, slope, m):
        out = []
        for name in ("current_A", "heat_pJ_s"):

            def value(c_i, c_o, v, m, name=name):
                return getattr(law, name)(c_i, c_o, v, t, area, g, k_ref, v_half, slope, m)

            for mode in (jax.jacfwd, jax.grad):
                out.append(jnp.stack(mode(value, argnums=(0, 1, 2, 3))(c_i, c_o, v, m)))
        return jnp.stack(out)

    axes = (0, 0, 0, None, None, None, None, None, None, 0)  # The states' axes: c_i, c_o, V, m.
    function = jax.jit(jax.vmap(one, in_axes=axes))
    return lambda args: np.moveaxis(np.asarray(function(*args)), 0, -1)


def close(a, b, ulps):
    """Bit for bit at 0 ulps; else |a - b| <= ulps ulps of the larger, never at a NaN or an inf."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if not ulps:
        return a.tobytes() == b.tobytes()
    spacing = np.spacing(np.maximum(np.abs(a), np.abs(b)))
    return bool(np.all(np.isfinite(a) & np.isfinite(b) & (np.abs(a - b) <= ulps * spacing)))


@functools.cache
def pair_run(declaration):
    """K's transfer (fmol) and the route's heat (pJ) at the end of the closed pair's run with one
    route of (g_ref, K_ref), or the refusal's text."""
    g, k_ref = declaration
    try:
        spec = parse_spec(closed_pair(route(g_ref_S_per_m2=g, k_ref_mM=k_ref)))
    except ConfigError as err:
        return str(err)
    final = run(spec).final.state
    k = list(spec.model.species_ids).index("K")
    return np.array([final.passive_transferred[k, 0], final.passive_dissipated_energy_pJ[0]])


def admitted(declaration):
    g, k_ref = declaration
    try:
        parse_spec(closed_pair(route(g_ref_S_per_m2=g, k_ref_mM=k_ref)))
    except ConfigError:
        return False
    return True


def extreme_failures(row, *, runs=True):
    """The claims a row breaks, by name, with the law's concentration factor as it stands. Without
    runs, a run row checks admission alone (a plant is never run: runs are compiled once)."""
    out = []
    if row == "ordinary":
        for args in ordinary_states():
            with factor(unguarded):
                old = dict(numpy=in_numpy(args), compiled=compiled()(args))
            new = dict(numpy=in_numpy(args), compiled=compiled()(args))
            out += [f"the unguarded bits ({b})" for b in old if not close(old[b], new[b], 0)]
        return out
    if row == "derivatives":
        evaluate = derivatives()
        for name in ("b_minus_512_overflow", "b_510_underflow"):
            twin, extreme, c_out = TWINS[name]
            if not close(evaluate(states(twin, c_out)), evaluate(states(extreme, c_out)), ULPS):
                out.append(f"derivatives ({name})")
        return out
    twin, extreme, c_out = TWINS[row]
    ulps = 0 if row == "b_minus_8" else ULPS
    for backend, evaluate in (("numpy", in_numpy), ("compiled", compiled())):
        if not close(evaluate(states(twin, c_out)), evaluate(states(extreme, c_out)), ulps):
            out.append(f"kernels ({backend})")
    if row in RUNS and not runs and not admitted(extreme):
        out.append("admitted")
    if row in RUNS and runs:
        ran = pair_run(extreme)
        if isinstance(ran, str) or not close(pair_run(twin), ran, ulps):
            out.append(f"run: {ran}")
    return out


EXTREME = (  # Each row with its plants.
    pytest.param("ordinary", (split_everywhere, selected_divisor), id="ordinary"),
    pytest.param("b_minus_8", (rootless,), id="b_minus_8"),
    pytest.param("b_minus_512_overflow", (unguarded,), id="b_minus_512_overflow"),
    pytest.param("b_510_underflow", (unguarded,), id="b_510_underflow"),
    pytest.param("derivatives", (single_where,), id="derivatives"),
)


@pytest.mark.filterwarnings("ignore:overflow encountered in divide:RuntimeWarning")  # The host's.
@pytest.mark.parametrize("row, plants", EXTREME)
def test_equivalent_declarations_are_one_route_at_extreme_finite_coefficients(row, plants):
    assert extreme_failures(row) == []
    for plant in plants:
        with factor(plant):
            assert extreme_failures(row, runs=False) != [], plant.__name__
