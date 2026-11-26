"""cells.operator.k_anion_symport_mass_action@1: KCC-type electroneutral K+/anion symport.

Thermodynamics: the heat 1e-3 J A is never negative, J vanishes exactly where
the concentration products are equal and changes sign across that point, and
the route carries no current (1 K+ : 1 anion). Volume factor: 1 at the set
volume, exp(0.2) at +20% with s = 1 (Lew et al. 1991), about 5x with s = 0.12
(Kaji 1986's 4-5x). Units: a red-cell flux per cell volume converts to a route
capacity and back. NumPy and JAX agree; invalid inputs fail domain_valid. The
independent reduced reference's transcription (validation/tissue/
pump_water_reference.kcc_cycles) gives the same cycles.

The operator's step bound (one table, each row a claim with its plant; the independent Lean
project's finding of 19 November 2026, lean/PROGRESS.md): a finite outside node's concentrations
and volume enter the route's relaxation rate, each volume its own, a held bath adds nothing, and
routes that share a node add their rates there.

The law's log of the product ratio (a second table, likewise; the Lean project's component case,
lean/checks/potassium_anion_symport.py product_ratio): where both concentration products are
normal floats and their quotient is not (16 mM inside and 2^-510 mM outside, and its mirror), the
affinity and heat are finite and within ulps of the 60-digit reference, their derivatives finite;
every normal quotient keeps the unguarded log's bits, in numpy and compiled.
"""

import contextlib

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions.pump_composite_spec import frozen_definition
from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.runner import timeline
from cells.laws.electrochemistry import R
from cells.laws.routes import k_anion_symport as law
from cells.operators import k_anion_symport as operator
from cells.registry.models import get_model
from validation.tissue import pump_water_fixtures as fixture


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def parameters(k=2.5e-7, v_set=0.75, s=1.0):
    return law.Parameters(np.asarray(k), np.asarray(v_set), np.asarray(s))


def test_heat_is_never_negative_and_the_flux_reverses_at_equal_products():
    rng = np.random.default_rng(5)
    c = 10 ** rng.uniform(-1, 2.5, (4, 10000))
    volume = rng.uniform(0.4, 1.5, 10000)
    p = parameters(k=rng.uniform(0, 1e-6, 10000), v_set=0.75, s=rng.uniform(0.05, 2, 10000))
    r = law.rates(*c, volume, 310.0, p, rng.uniform(0, 1, 10000), xp=np)
    assert np.all(r.dissipation_pJ_s >= 0)
    assert np.all(np.sign(r.cycles_fmol_s) * np.sign(r.affinity_J_mol) >= 0)
    # Equal products: no flux, zero affinity; crossing them reverses the flux.
    k_in, a_in, k_out = 140.0, 60.0, 5.0
    a_out = k_in * a_in / k_out
    for scale, sign in ((1.0, 0.0), (0.9, 1.0), (1.1, -1.0)):
        r = law.rates(k_in, a_in, k_out, a_out * scale, 0.75, 310.0, parameters(), 1.0, xp=np)
        assert np.sign(r.cycles_fmol_s) == sign
        assert np.sign(r.affinity_J_mol) == sign
    r = law.rates(k_in, a_in, k_out, a_out, 0.75, 310.0, parameters(), 1.0, xp=np)
    assert r.cycles_fmol_s == 0.0 and abs(r.affinity_J_mol) < 1e-9


def test_affinity_and_flux_values():
    r = law.rates(141.0, 73.0, 5.0, 140.0, 0.75, 310.0, parameters(), 0.5, xp=np)
    assert r.cycles_fmol_s == pytest.approx(2.5e-7 * 0.5 * (141 * 73 - 5 * 140), rel=1e-15)
    assert r.affinity_J_mol == pytest.approx(R * 310 * np.log(141 * 73 / (5 * 140)), rel=1e-14)
    assert r.dissipation_pJ_s == pytest.approx(1e-3 * r.cycles_fmol_s * r.affinity_J_mol)


def test_volume_factor():
    p = parameters(v_set=0.75, s=1.0)
    assert law.volume_factor(0.75, p, xp=np) == 1.0
    assert law.volume_factor(0.9, p, xp=np) == pytest.approx(np.exp(0.2), rel=1e-14)
    steep = parameters(v_set=0.75, s=0.12)
    assert 4.0 < law.volume_factor(0.9, steep, xp=np) < 6.0  # Kaji 1986: 4-5x at 1.2.
    assert law.volume_factor(0.6, steep, xp=np) < 1.0


def test_capacity_from_a_red_cell_flux():
    # Lew et al. 1991 reference: 15 mmol/(L cells h) at K 140 x Cl 95 - K 5 x Cl 140.
    difference = 140 * 95 - 5 * 140
    k = law.capacity_from_flux(15.0, difference, 0.75)
    flux = k * difference  # fmol/s for 0.75 pL
    assert flux / 0.75 * 3600 == pytest.approx(15.0, rel=1e-14)


def test_numpy_and_jax_agree_and_invalid_inputs_fail():
    args = (141.0, 73.0, 5.0, 140.0, 0.9, 310.0, parameters(s=0.12), 0.7)
    a = law.rates(*args, xp=np)
    b = law.rates(*(jnp.asarray(v) if not isinstance(v, tuple) else v for v in args), xp=jnp)
    for x, y in zip(a, b, strict=True):
        np.testing.assert_allclose(np.asarray(y), x, rtol=1e-14)
    good = (141.0, 73.0, 5.0, 140.0, 0.9)
    assert law.domain_valid(*good, parameters(), 1.0, xp=np)
    for bad in (
        (0.0, 73.0, 5.0, 140.0, 0.9),
        (141.0, -1.0, 5.0, 140.0, 0.9),
        (141.0, 73.0, 5.0, np.nan, 0.9),
        (141.0, 73.0, 5.0, 140.0, 0.0),
    ):
        assert not law.domain_valid(*bad, parameters(), 1.0, xp=np)
    assert not law.domain_valid(*good, parameters(s=0.0), 1.0, xp=np)
    assert not law.domain_valid(*good, parameters(k=-1.0), 1.0, xp=np)
    assert not law.domain_valid(*good, parameters(), 1.5, xp=np)
    assert not law.domain_valid(*good, parameters(s=1e-4), 1.0, xp=np)  # exp overflow domain


def test_reference_transcription_gives_the_same_cycles():
    from validation.tissue import pump_water_reference as reference

    rng = np.random.default_rng(9)
    c = 10 ** rng.uniform(-1, 2.5, (4, 1000))
    volume = rng.uniform(0.4, 1.5, 1000)
    k, s, a = rng.uniform(0, 1e-6, 1000), rng.uniform(0.05, 2, 1000), rng.uniform(0, 1, 1000)
    engine = law.rates(*c, volume, 310.0, parameters(k=k, v_set=0.75, s=s), a, xp=np)
    expected = reference.kcc_cycles(
        *c, volume, dict(capacity_fmol_s_mM2=k, set_volume_pL=0.75, steepness=s, availability=a)
    )
    np.testing.assert_allclose(engine.cycles_fmol_s, expected, rtol=1e-13, atol=0)


# ------------------------------------------------------------------ the step bound and its plants

# The Lean finding's closed pair: (K_i, A_i, K_o, A_o) in mM, one 1 pL cell and one outside node.
NEAR_STALL = (4.0, 4.0, 128.0, 0.125 - 2.0**-20)
ORDINARY = (40.0, 15.0, 10.0, 20.0)
REFUSED = "Symport rate exceeds the explicit-rate bound"


def closed_pair(concentrations, steps, *, duration=0.01, capacity=2.5, volumes=(1.0, 1.0),
                held=False, routes=1):  # fmt: skip
    """The pair of lean/checks/potassium_anion_symport.py: water and every other membrane transfer
    closed, a route of steepness 10 on each of `routes` identical patches between the cell and the
    outside node (the second without a pump or channels). The outside node is finite (and the
    gauge), or the cell's held bath; each node's amounts are its concentrations times its volume
    (pL)."""
    dt = duration / steps
    raw = fixture.heredity_cell("D", dt=dt, end_time=duration, observation_times=[0.0, duration])
    model, experiment = raw["model"], raw["experiment"]
    cell, outside = model["cells"][0], model["extracellular"][0]
    for i in range(1, routes):
        model["membranes"].append(dict(model["membranes"][0], id=f"membrane_{i}", pump=None))
        experiment["membrane_controls"].append(
            dict(membrane_id=f"membrane_{i}", schedule=[dict(time=0.0, availability=0.0)])
        )
    raw["execution"]["membrane_capacity"] = routes
    if not held:
        outside["reservoir"] = False
        model["closure"]["gauge_reference"] = outside["id"]
    ki, ai, ko, ao = concentrations
    for node, k, a, v in ((cell, ki, ai, volumes[0]), (outside, ko, ao, volumes[1])):
        node.update(
            volume_pL=v,
            initial_amount_fmol=dict(Na=30.0 * v, K=k * v, M=a * v, P=30.0 * v),
            fixed_charge_equivalent_fmol=(a - k) * v,
            initial_charge_C=0.0,
        )
    for key in ("membrane_controls", "channel_controls", "pump_controls"):
        for control in experiment[key]:
            control["schedule"][0]["availability"] = 0.0
    raw = fixture.with_symport(fixture.with_water(raw, availability=0.0), steepness=10.0)
    for route in raw["model"]["symport"]["routes"]:
        route["capacity_fmol_s_mM2"] = capacity
    return parse_spec(frozen_definition(raw))


def admitted(spec):
    """The runner's grid check (timeline): True, or False on the symport's refusal (any other
    refusal is raised, so a row tests this bound alone)."""
    try:
        timeline(spec)
    except ConfigError as error:
        if REFUSED not in str(error):
            raise
        return False
    return True


def rate(spec):
    return operator.route_rate(spec, get_model(spec.model))


def factor_at_maximum(spec):
    """f at the declared maximum volume (with_water's 2 V_i), as the bound reads it."""
    route = spec.model.operators[-1].routes[0]
    q = law.Parameters(route.capacity_fmol_s_mM2, route.set_volume_pL, route.steepness)
    return float(law.volume_factor(2.0 * spec.model.cells[0].volume_pL, q, xp=np))


def inside_only_rate(spec):
    """The bound as it landed before 20 November 2026: k f (K_i + A_i) / V_i, transcribed."""
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    cells = np.asarray(p.membrane_cell)
    k, a = int(p.symport_potassium_species), int(p.symport_anion_species)
    ci = (p.amount_reference + state.amount_increment) / p.volume
    vmax = p.water_maximum_volume_pL[cells]
    f = np.exp((vmax - p.symport_set_volume_pL) / (p.symport_steepness * p.symport_set_volume_pL))
    rate = p.symport_capacity_fmol_s_mM2 * f * (ci[k, cells] + ci[a, cells]) / p.volume[cells]
    return np.max(np.where(p.symport_route & p.membrane_active, rate, 0.0), initial=0.0)


def outside_sums(state, p, k, a, mask):
    """[membrane] K_o + A_o (mM) at each patch's outside node where mask holds, else 0."""
    volume = np.where(mask, p.extracellular_volume, 1.0)
    co = (p.extracellular_amount_reference + state.extracellular_amount_increment) / volume
    return np.where(mask, co[k] + co[a], 0.0)[np.asarray(p.membrane_outside)]


def no_outside_term(state, p, k, a):  # Planted: the inside-only rate (the finding's bound).
    return np.zeros(np.shape(p.membrane_outside))


def cell_volume_term(state, p, k, a):  # Planted: the equal-volume form, (K_o + A_o) / V_i.
    finite = np.asarray(p.outside_active & ~p.reservoir)
    return outside_sums(state, p, k, a, finite) / p.volume[np.asarray(p.membrane_cell)]


def unmasked_term(state, p, k, a):  # Planted: a held bath's concentrations counted.
    active = np.asarray(p.outside_active)
    return (
        outside_sums(state, p, k, a, active)
        / np.where(active, p.extracellular_volume, 1.0)[np.asarray(p.membrane_outside)]
    )


def per_route_sums(scale, p):  # Planted: each route alone, as if no node were shared.
    return scale, scale


@contextlib.contextmanager
def replaced(name, replacement):
    """An operator function replaced for the block (a plant)."""
    saved = getattr(operator, name)
    setattr(operator, name, replacement)
    try:
        yield
    finally:
        setattr(operator, name, saved)


def close(a, b, ulps):
    """|a - b| <= ulps ulps of the larger (0: bit for bit), never at a NaN or an inf."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if not ulps:
        return a.tobytes() == b.tobytes()
    spacing = np.spacing(np.maximum(np.abs(a), np.abs(b)))
    return bool(np.all(np.isfinite(a) & np.isfinite(b) & (np.abs(a - b) <= ulps * spacing)))


def bound_failures(row):
    """The claims a row breaks, by name, with the operator as it stands."""
    out = []
    if row == "lean_pair":
        # One 10 ms step: h x rate = 0.01 x 2.5 f(2 V) x (4 + 4 + 128 + 0.125 - 2^-20) / 1 pL, about
        # 3.76 (3.40 at the set volume, the note's value), so refused; 32 steps over 10 ms admitted.
        one, many = closed_pair(NEAR_STALL, 1), closed_pair(NEAR_STALL, 32)
        expected = 2.5 * factor_at_maximum(one) * sum(NEAR_STALL) / 1.0
        if not close(rate(one), expected, 4):
            out.append(f"rate {rate(one)!r} against {expected!r}")
        if admitted(one):
            out.append("one 10 ms step admitted")
        if not admitted(many):
            out.append("32 steps refused")
    elif row == "unequal_volumes":
        # V_i = 1 pL, V_o = 0.25 pL: (K_i + A_i) / V_i + (K_o + A_o) / V_o = 55 + 120 = 175 per pL,
        # against 85 if V_o were V_i. The step puts h x rate at 1.2: refused, and 1.2 x 85 / 175 =
        # 0.58 under the equal-volume form.
        probe = closed_pair(ORDINARY, 1, volumes=(1.0, 0.25))
        per_pL = (40.0 + 15.0) / 1.0 + (10.0 + 20.0) / 0.25
        expected = 2.5 * factor_at_maximum(probe) * per_pL
        if not close(rate(probe), expected, 4):
            out.append(f"rate {rate(probe)!r} against {expected!r}")
        step = 1.2 / expected
        if admitted(closed_pair(ORDINARY, 1, duration=step, volumes=(1.0, 0.25))):
            out.append("h x rate = 1.2 admitted")
        if not admitted(closed_pair(ORDINARY, 1, duration=0.8 / expected, volumes=(1.0, 0.25))):
            out.append("h x rate = 0.8 refused")
    elif row == "shared_node":
        # Two identical routes on one cell and one finite node: each node's term carries both
        # routes' k f, so the rate is twice one route's. The step puts h x rate at 1.2: refused,
        # and 0.6 if each route were counted alone.
        probe = closed_pair(NEAR_STALL, 1, routes=2)
        expected = 2.0 * 2.5 * factor_at_maximum(probe) * sum(NEAR_STALL) / 1.0
        if not close(rate(probe), expected, 4):
            out.append(f"rate {rate(probe)!r} against {expected!r}")
        if admitted(closed_pair(NEAR_STALL, 1, duration=1.2 / expected, routes=2)):
            out.append("h x rate = 1.2 admitted")
        if not admitted(closed_pair(NEAR_STALL, 1, duration=0.8 / expected, routes=2)):
            out.append("h x rate = 0.8 refused")
    elif row == "held_bath":
        # The same pair with the cell's held bath outside: the rate is the inside-only bound's, bit
        # for bit (every registered symport world faces held baths, 20 November 2026).
        for concentrations, volumes in ((ORDINARY, (1.0, 0.25)), (NEAR_STALL, (1.0, 1.0))):
            spec = closed_pair(concentrations, 1, volumes=volumes, held=True)
            if not close(rate(spec), inside_only_rate(spec), 0):
                out.append(
                    f"held bath {concentrations}: {rate(spec)!r} != {inside_only_rate(spec)!r}"
                )
    return out


BOUND = (  # Each plant a context: an operator function replaced.
    pytest.param("lean_pair", lambda: replaced("outside_term", no_outside_term), id="lean_pair"),
    pytest.param(
        "unequal_volumes", lambda: replaced("outside_term", cell_volume_term), id="unequal_volumes"
    ),
    pytest.param("shared_node", lambda: replaced("node_sums", per_route_sums), id="shared_node"),
    pytest.param("held_bath", lambda: replaced("outside_term", unmasked_term), id="held_bath"),
)


@pytest.mark.parametrize("row, plant", BOUND)
def test_the_step_bound_reads_a_finite_outside_node_and_each_plant_breaks_it(row, plant):
    assert bound_failures(row) == []
    with plant():
        assert bound_failures(row) != []


# ------------------------------------------------------------------ the affinity at extreme ratios

# The split form's four logs and two differences, carried through R T and the heat's product: a
# few ulps (measured on 20 November 2026: at most 1 on the values, 0 on the affinity's slopes).
ULPS = 8
TEMPERATURE_K = 310.0
EXTREMES = (  # (K_i, A_i, K_o, A_o) mM: both products normal floats, their quotient not.
    (16.0, 16.0, 2.0**-510, 2.0**-510),  # The Lean component case: the quotient 2^1028 overflows.
    (2.0**-510, 2.0**-510, 16.0, 16.0),  # Its mirror: the quotient 2^-1028 underflows.
)
EDGES = (  # Products near the ends of the floats, their quotient still normal: the direct form.
    (2.0**500, 2.0**500, 2.0**-11, 2.0**-11),  # 2^1022
    (2.0**-500, 2.0**-500, 2.0**10, 2.0**10),  # 2^-1020
    (16.0, 16.0, 2.0**-507, 2.0**-507),  # 2^1022: the Lean case's neighbour, still direct.
    # Within the split's margin of the ends: the largest double but one, 2^1024 (1 - 2^-52), and
    # the smallest normal, 2^-1022 (a tie rounded to even). Both normal, so both direct.
    (2.0**500, 2.0**500, 2.0**-12, 2.0**-12 * (1.0 + 2.0**-52)),
    (2.0**-500, 2.0**-500, 2.0**11, 2.0**11 * (1.0 - 2.0**-53)),
)


def unguarded(k_in, a_in, k_out, a_out, *, xp):  # The log as the law landed: ln of the quotient.
    return xp.log((k_in * a_in) / (k_out * a_out))


def split_everywhere(k_in, a_in, k_out, a_out, *, xp):  # Planted: the split form at every input.
    return (xp.log(k_in) - xp.log(k_out)) + (xp.log(a_in) - xp.log(a_out))


def single_where(k_in, a_in, k_out, a_out, *, xp):  # Planted: each branch on its raw inputs.
    quotient = (k_in * a_in) / (k_out * a_out)
    info = xp.finfo(xp.result_type(quotient))
    normal = (quotient >= info.tiny) & (quotient <= info.max)
    return xp.where(normal, xp.log(quotient), split_everywhere(k_in, a_in, k_out, a_out, xp=xp))


@contextlib.contextmanager
def log_ratio(replacement):
    """The law's log of the product ratio replaced for the block (a plant, or the unguarded)."""
    saved = law.log_product_ratio
    law.log_product_ratio = replacement
    try:
        yield
    finally:
        law.log_product_ratio = saved


@contextlib.contextmanager
def margin(value):  # Planted (-SPLIT_MARGIN): the margin on the wrong side of the normal range.
    saved = law.SPLIT_MARGIN
    law.SPLIT_MARGIN = value
    try:
        yield
    finally:
        law.SPLIT_MARGIN = saved


def kernel(args, compiled):
    """The four Rates outputs stacked, in numpy or compiled afresh (a new function, so a plant is
    traced, never a cached law)."""
    if compiled:
        out = jax.jit(lambda *a: law.rates(*a, xp=jnp))(*args)
    else:
        with np.errstate(over="ignore", divide="ignore", invalid="ignore"):  # A plant's.
            out = law.rates(*args, xp=np)
    shape = np.shape(args[0])
    return np.stack([np.broadcast_to(np.asarray(v, dtype=float), shape) for v in out])


def derivatives(args, outputs=(1, 3)):
    """d/d(K_i, A_i, K_o, A_o, V) of the chosen Rates outputs (affinity 1, heat 3), forward
    (jacfwd) and reverse (grad), compiled afresh: [state, output and mode, argument]."""
    k_in, a_in, k_out, a_out, volume, temperature, q, opening = args

    def one(k_in, a_in, k_out, a_out, volume, q, opening):
        out = []
        for index in outputs:

            def value(*c, index=index):
                return law.rates(*c, temperature, q, opening, xp=jnp)[index]

            for mode in (jax.jacfwd, jax.grad):
                out.append(jnp.stack(mode(value, argnums=(0, 1, 2, 3, 4))(
                    k_in, a_in, k_out, a_out, volume)))  # fmt: skip
        return jnp.stack(out)

    axes = (0, 0, 0, 0, 0, law.Parameters(0, None, 0), 0)
    return np.asarray(jax.jit(jax.vmap(one, in_axes=axes))(
        k_in, a_in, k_out, a_out, volume, q, opening))  # fmt: skip


def ordinary_states(n, seed):
    """Random ordinary routes (the reference transcription's ranges), the edge rows appended."""
    rng = np.random.default_rng(seed)
    c = np.concatenate([10 ** rng.uniform(-1, 2.5, (4, n)), np.array(EDGES).T], axis=1)
    m = c.shape[1]
    q = law.Parameters(rng.uniform(1e-8, 1e-6, m), 0.75, rng.uniform(0.05, 2, m))
    return (*c, rng.uniform(0.4, 1.5, m), TEMPERATURE_K, q, rng.uniform(0.1, 1, m))


def edge_states():
    c = np.array(EDGES).T
    m = c.shape[1]
    q = law.Parameters(np.full(m, 1e-7), 0.75, np.ones(m))
    return (*c, np.full(m, 0.75), TEMPERATURE_K, q, np.ones(m))


def extreme_states():
    c = np.array(EXTREMES).T
    m = c.shape[1]
    q = law.Parameters(np.full(m, 0.01), 1.0, np.ones(m))
    return (*c, np.ones(m), TEMPERATURE_K, q, np.ones(m))


def references():
    """The 60-digit affinity, heat and affinity derivatives R T (1/K_i, 1/A_i, -1/K_o, -1/A_o, 0)
    at EXTREMES (validation/core_seams/references/exact.py, as the Lean reproducer uses)."""
    from validation.core_seams.references import exact

    values, slopes = [], []
    with exact.context():
        rt = exact.RT_J_per_mol(TEMPERATURE_K)
        for k_in, a_in, k_out, a_out in EXTREMES:
            ki, ai, ko, ao = map(exact.dec, (k_in, a_in, k_out, a_out))
            affinity = rt * (ki.ln() + ai.ln() - ko.ln() - ao.ln())
            heat = exact.dec(0.01) * (ki * ai - ko * ao) * affinity / 1000
            values.append([float(affinity), float(heat)])
            slopes.append([float(rt / ki), float(rt / ai), float(-rt / ko), float(-rt / ao), 0.0])
    return np.array(values), np.array(slopes)


def quotient_failures(row):
    """The claims a row breaks, by name, with the law's log of the product ratio as it stands."""
    out = []
    if row == "quotient_ordinary":
        # The kernel's four outputs and the affinity's derivatives keep the unguarded log's bits at
        # ordinary and edge states, 4096 routes and one, in numpy and compiled.
        for n, seed in ((4096, 3), (1, 5)):
            args = ordinary_states(n, seed)
            with log_ratio(unguarded):
                old = [kernel(args, False), kernel(args, True), derivatives(args, (1,))]
            new = [kernel(args, False), kernel(args, True), derivatives(args, (1,))]
            for name, a, b in zip(("numpy", "compiled", "derivatives"), old, new, strict=True):
                if not close(a, b, 0):
                    out.append(f"the unguarded bits ({name}, {n} routes)")
    elif row == "quotient_edges":
        # Every normal quotient keeps the direct form, also within the split's margin of the ends
        # of the normal range: the unguarded log's bits, in numpy and compiled.
        args = edge_states()
        with log_ratio(unguarded):
            old = [kernel(args, False), kernel(args, True)]
        new = [kernel(args, False), kernel(args, True)]
        for name, a, b in zip(("numpy", "compiled"), old, new, strict=True):
            if not close(a, b, 0):
                out.append(f"the unguarded bits at the edges ({name})")
    elif row == "quotient_extremes":
        # Finite and within ULPS of the 60-digit affinity and heat, admitted by domain_valid.
        args, (expected, _) = extreme_states(), references()
        for name, compiled in (("numpy", False), ("compiled", True)):
            got = kernel(args, compiled)[[1, 3]].T
            if not close(got, expected, ULPS):
                out.append(f"values ({name}): {got.tolist()} against {expected.tolist()}")
        if not np.all(law.domain_valid(*args[:5], args[6], args[7], xp=np)):
            out.append("refused by domain_valid")
    elif row == "quotient_derivatives":
        # Forward and reverse derivatives finite at both extremes; the affinity's within ULPS.
        d = derivatives(extreme_states())
        _, slopes = references()
        if not np.all(np.isfinite(d)):
            out.append(f"non-finite derivatives: {np.argwhere(~np.isfinite(d)).tolist()}")
        for mode in (0, 1):
            if not close(d[:, mode], slopes, ULPS):
                out.append(f"affinity derivatives (mode {mode}): {d[:, mode].tolist()}")
    return out


QUOTIENT = (  # Each plant a context: the law's log replaced, or its margin moved.
    pytest.param("quotient_ordinary", lambda: log_ratio(split_everywhere), id="quotient_ordinary"),
    pytest.param("quotient_edges", lambda: margin(-law.SPLIT_MARGIN), id="quotient_edges"),
    pytest.param("quotient_extremes", lambda: log_ratio(unguarded), id="quotient_extremes"),
    pytest.param(
        "quotient_derivatives", lambda: log_ratio(single_where), id="quotient_derivatives"
    ),
)


@pytest.mark.parametrize("row, plant", QUOTIENT)
def test_the_affinity_is_finite_where_the_product_quotient_is_not_and_each_plant_breaks_it(
    row, plant
):
    assert quotient_failures(row) == []
    with plant():
        assert quotient_failures(row) != []
