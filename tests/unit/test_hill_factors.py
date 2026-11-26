"""The neutral Hill helper (processes/hill_factors) against cells.operator.local_species_reactions@1's own rates.

The lead's ruling 7 (docs/INVENTORY_COUPLING_DESIGN.md §6.3): D152's factor expression is inline in
species_reactions.route_rates, so the helper is tested against that operator's code, which stays
untouched. Three zeroth-order sources of one species at one site with one rate constant, one plain,
one under hill_activation and one under hill_inhibition of another species: D152's own rates of the
factored sources must equal the plain rate times exp of the helper's log factor, bit for bit, over a
grid of half-saturations, coefficients and concentrations. Jitted, the helper's log factor agrees
with its host value within 4 eps (XLA's log and logaddexp are not NumPy's).

cells.transfer_factor.hill_product_factor@1 (G-5), the law of cells.kind.species_condition@1, and its planted errors (D187):
- it is the left fold of the helper's log factors in one exponential, bit for bit, and the closed
  form's product at random reads (planted: a wrong exponent, the two forms exchanged, a missing
  factor, K in M for mM, K and n exchanged, a reading scaled by a valence);
- at a zero concentration it is exactly 0 or 1, and below it NaN, host and compiled (planted: a
  floored and a clipped concentration);
- its slopes are the finite differences of ln f, exact in both limits (planted: an inhibition's sign
  dropped, the slope in x for the one in ln x, 1 - h by subtraction);
- its record keeps its interface's contract, and each planted record is refused;
- it is cells.transfer_factor.ph_conditioned_factor@1 within 3e-15 (planted: K's exponent of the other sign), and
  cells.operator.species_regulated_availability@1's factor at basal 0 bit for bit (planted: ln(N/V) for
  ln N - ln V).
"""

import dataclasses
from types import SimpleNamespace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.kinds import species_condition
from cells.laws.reactions import hill_factors, ph_condition
from cells.laws.reactions import hill_product_factor as product
from cells.models import pump_composite as pc
from cells.operators import species_reactions as sr
from cells.operators import species_regulated_availability as sra
from cells.registry import laws as law_registry
from validation.tissue import species_reactions_fixtures as rfx

K_VALUES = (1e-9, 1e-6, 1e-3, 0.37, 1.0, 120.0)
N_VALUES = (0.5, 1.0, 1.7, 2.0, 4.0)
X_VALUES = (1e-12, 3e-9, 1e-6, 2.5e-4, 1e-3, 0.8, 1.0, 37.0, 1e3)


def _world():
    raw = rfx.species_world(extra=("Y",), profile=dict(Y=dict(cell_0=1e-4)), faces=False)
    cell = {"cells": ["cell_0"]}
    reactions = [
        rfx.mass_action("plain", cell, {}, {"Y": 1}, 1e-4),
        rfx.mass_action(
            "act", cell, {}, {"Y": 1}, 1e-4, factors=[rfx.hill("hill_activation", "S", 1e-3, 2.0)]
        ),
        rfx.mass_action(
            "inh", cell, {}, {"Y": 1}, 1e-4, factors=[rfx.hill("hill_inhibition", "S", 1e-3, 2.0)]
        ),
    ]
    species = [rfx.species("S"), rfx.species("Y")]
    raw = rfx.with_reactions(raw, species, reactions, rfx.always(["plain", "act", "inh"]))
    spec = parse_spec(raw)
    model = pc.model_for(spec.model)
    state, p = model.initial_values(spec)
    return spec, state, p


def test_helper_agrees_with_d152_rates_bit_for_bit():
    _, state, p = _world()
    net = sr.network(p, np.ones(3), xp=np)
    base = sr.node_amounts(state, p, xp=np)
    s_row = int(p.reaction_factor_species[1, 0])
    node = int(net.node[1])
    assert int(net.node[0]) == node == int(net.node[2])
    volume = net.route_volume[1]
    checked = 0
    for k in K_VALUES:
        for n in N_VALUES:
            q = p._replace(
                reaction_factor_half_saturation_mM=np.where(p.reaction_factor_kind > 0, k, 1.0),
                reaction_factor_coefficient=np.where(p.reaction_factor_kind > 0, n, 1.0),
            )
            for x in X_VALUES:
                amounts = np.array(base, copy=True)
                amounts[s_row, node] = x * volume
                rate = sr.route_rates(amounts, net, q, xp=np).rate
                log_x = np.log(amounts[s_row, node]) - np.log(volume)
                for route, kind in ((1, hill_factors.ACTIVATION), (2, hill_factors.INHIBITION)):
                    f = np.exp(hill_factors.log_factor(log_x, k, n, kind, xp=np))
                    assert rate[route] == rate[0] * f, (k, n, x, kind, rate[route], rate[0] * f)
                    checked += 1
    assert checked == 2 * len(K_VALUES) * len(N_VALUES) * len(X_VALUES)


def test_jitted_helper_matches_the_host_helper():
    """The device evaluation (the coupling operator's path) within a few ulps of the host one."""
    log_x = np.log(np.asarray(X_VALUES))[:, None, None]
    k = np.asarray(K_VALUES)[None, :, None]
    n = np.asarray(N_VALUES)[None, None, :]
    eps = np.finfo(float).eps
    for kind in (hill_factors.ACTIVATION, hill_factors.INHIBITION):
        host = hill_factors.log_factor(log_x, k, n, kind, xp=np)
        device = np.asarray(
            jax.jit(lambda a, b, c, kind=kind: hill_factors.log_factor(a, b, c, kind, xp=jnp))(
                log_x, k, n
            )
        )
        np.testing.assert_allclose(device, host, rtol=4 * eps, atol=4 * eps)


def test_forms_and_padding():
    for kind, expected in ((hill_factors.ACTIVATION, 0.5), (hill_factors.INHIBITION, 0.5)):
        value = hill_factors.factor(np.log(2.0), 2.0, 3.0, kind, xp=np)
        assert abs(value - expected) <= 2 * np.finfo(float).eps
    x, k, n = 3.0e-4, 1.1e-3, 1.7
    act = hill_factors.factor(np.log(x), k, n, hill_factors.ACTIVATION, xp=np)
    inh = hill_factors.factor(np.log(x), k, n, hill_factors.INHIBITION, xp=np)
    np.testing.assert_allclose(act, x**n / (k**n + x**n), rtol=1e-14)
    np.testing.assert_allclose(inh, k**n / (k**n + x**n), rtol=1e-14)
    assert np.isfinite(
        hill_factors.log_factor(np.log(1e-300), 1.0, 4.0, hill_factors.ACTIVATION, xp=np)
    )
    assert hill_factors.factor(np.log(5.0), 1.0, 2.0, 0, xp=np) == 1.0  # Padding: exactly 1.


# ------------------------------------------------------------------ cells.transfer_factor.hill_product_factor@1 (G-5)


def product_reads(count=400, reads=4):
    """Random reads [case, read]: x, K, n and form codes, each case with 1 to `reads` reads and the
    rest padding (code 0, K = n = 1)."""
    rng = np.random.default_rng(20261125)
    used = np.arange(reads) < rng.integers(1, reads + 1, count)[:, None]
    x = 10.0 ** rng.uniform(-7, 1, (count, reads))
    k = np.where(used, 10.0 ** rng.uniform(-6, 0, (count, reads)), 1.0)
    n = np.where(used, rng.uniform(0.5, 4.0, (count, reads)), 1.0)
    return x, k, n, np.where(used, rng.integers(1, 3, (count, reads)), 0)


def closed_form(x, k, n, form):
    """The product of x^n/(K^n + x^n) and K^n/(K^n + x^n), written as it stands."""
    act, inh = x**n / (k**n + x**n), k**n / (k**n + x**n)
    return np.prod(np.where(form == 1, act, np.where(form == 2, inh, 1.0)), axis=1)


def test_the_hill_product_law_and_its_planted_errors():
    x, k, n, form = product_reads()
    log_x = np.log(x)
    terms = hill_factors.log_factor(log_x, k, n, form, xp=np)
    fold = terms[:, 0]
    for j in range(1, terms.shape[1]):
        fold = fold + terms[:, j]
    log_f = product.log_factor(log_x, k, n, form, xp=np)
    f = product.factor(log_x, k, n, form, xp=np)
    assert np.array_equal(log_f, fold) and np.array_equal(f, np.exp(fold))  # Bit for bit.
    one = product.factor(log_x[:, :1], k[:, :1], n[:, :1], form[:, :1], xp=np)
    assert np.array_equal(
        one, hill_factors.factor(log_x[:, 0], k[:, 0], n[:, 0], form[:, 0], xp=np)
    )
    assert np.all((f >= 0) & (f <= 1))
    compiled = np.asarray(jax.jit(lambda *a: product.factor(*a, xp=jnp))(log_x, k, n, form))
    np.testing.assert_allclose(compiled, f, rtol=1e-12)

    def worst(value):
        return float(np.max(np.abs(value - reference) / reference))

    reference = closed_form(x, k, n, form)
    assert worst(f) < 1e-12
    used = form > 0
    last = used & ~np.pad(used, ((0, 0), (0, 1)))[:, 1:]  # Each case's last declared read.
    plants = {
        "a wrong exponent": (log_x, k, np.where(used, np.ceil(n), n), form),
        "the two forms exchanged": (log_x, k, n, np.where(used, 3 - form, 0)),
        "a missing factor": (log_x, k, n, np.where(last, 0, form)),
        "K in M": (log_x, np.where(used, 1e-3 * k, k), n, form),
        "K and n exchanged": (log_x, np.where(used, n, k), np.where(used, k, n), form),
        "a reading scaled by a valence of 3": (np.log(3.0 * x), k, n, form),
    }
    for name, planted in plants.items():
        assert worst(product.factor(*planted, xp=np)) > 1e-3, name


@pytest.mark.parametrize("compiled", [False, True])
def test_the_hill_product_is_exact_at_zero_and_nan_below_it(compiled):
    """One activation at x beside one inhibition at 0.3 mM, and the inhibition alone."""
    k, n = np.array([1.5e-4, 2e-2]), np.array([2.0, 1.5])

    def evaluate(x, read, xp):
        log_x = xp.stack((read(x, xp), xp.log(xp.asarray(0.3))))
        both = product.factor(log_x, k, n, np.array([1, 2]), xp=xp)
        alone = product.factor(read(x, xp)[None], k[:1], n[:1], np.array([2]), xp=xp)
        return both, alone

    def run(x, read=lambda x, xp: xp.log(x)):
        with np.errstate(all="ignore"):
            if compiled:
                return jax.jit(lambda v: evaluate(v, read, jnp))(x)
            return evaluate(np.float64(x), read, np)

    both, alone = run(0.0)
    assert float(both) == 0.0 and float(alone) == 1.0  # Exactly.
    assert 0.0 < float(run(1e-6)[0]) < 1.0
    for bad in (-1e-9, np.nan):
        assert all(np.isnan(float(v)) for v in run(bad))  # The door refuses a NaN.
    floored = run(0.0, lambda x, xp: xp.log(xp.maximum(x, 1e-9)))  # Plant: a floor.
    assert float(floored[0]) != 0.0 and float(floored[1]) != 1.0
    clipped = run(-1e-9, lambda x, xp: xp.log(xp.maximum(x, 0.0)))  # Plant: clipped at zero.
    assert not np.isnan(float(clipped[0]))


def test_the_hill_product_slopes_are_those_of_ln_f_and_exact_in_both_limits():
    x, k, n, form = product_reads()
    log_x, used, h = np.log(x), form > 0, 1e-5
    slopes = product.log_slopes(log_x, k, n, form, xp=np)
    difference = np.empty_like(slopes)
    for j in range(slopes.shape[1]):
        step = h * (np.arange(slopes.shape[1]) == j)
        up, down = (product.log_factor(log_x + s * step, k, n, form, xp=np) for s in (1, -1))
        difference[:, j] = (up - down) / (2 * h)

    def worst(value):
        return float(np.max(np.abs(value - difference)))

    assert worst(slopes) < 1e-6 and np.all(slopes[~used] == 0.0)
    assert np.all(np.abs(slopes) <= n) and np.all(slopes[form == 2] <= 0)
    assert worst(np.abs(slopes)) > 1e-2  # Plant: an inhibition's sign dropped.
    assert worst(slopes / x) > 1e-2  # Plant: d/dx for d/d ln x.
    assert worst(slopes * np.where(used, 3.0, 1.0)) > 1e-2  # Plant: a slope per charge.
    for code, low, high in ((1, 2.5, 0.0), (2, -0.0, -2.5)):  # The limits, finite and exact.
        with np.errstate(all="ignore"):
            ends = [
                float(product.log_slopes(np.array([v]), 1e-3, 2.5, np.array([code]), xp=np)[0])
                for v in (-np.inf, np.inf)
            ]
        assert ends == [low, high]
    # Where h is near 1, 1 - h keeps its relative accuracy (plant: formed as 1 - h, it is 0).
    z = 40.0
    tail = float(product.log_slopes(np.array([z]), 1.0, 1.0, np.array([1]), xp=np)[0])
    assert tail == pytest.approx(np.exp(-z) / (1 + np.exp(-z)), rel=1e-12, abs=0)
    assert 1.0 - float(product.factor(np.array([z]), 1.0, 1.0, np.array([1]), xp=np)) == 0.0


def test_the_hill_product_s_record_keeps_its_interface_s_contract():
    law = law_registry.active().lookup(product.LAW_ID)
    assert law is product.LAW and law.errors() == [] and law.provenance == "parity"
    hosted = law_registry.hosted_laws(product.TRANSFER_FACTOR_LAW, species_condition.KIND_ID)
    assert hosted == (law,)
    plants = {
        "a kernel that is not callable": dict(log_slopes=None),
        "no form": dict(forms=()),
        "a form named twice": dict(forms=(("hill_activation", 1), ("hill_activation", 2))),
        "a code used twice": dict(forms=(("hill_activation", 1), ("hill_inhibition", 1))),
        "the padding's code": dict(forms=(("hill_activation", 0),)),
        "a parameter named twice": dict(parameters=("hill_coefficient", "hill_coefficient")),
        "an empty range": dict(value_range=(1.0, 0.0)),
        "a cited record with no source": dict(provenance="cited", source=None),
    }
    for name, change in plants.items():
        planted = dataclasses.replace(law, law_id="tests.transfer_factor.planted_factor@1", **change)
        assert planted.errors(), name
        with pytest.raises(ValueError, match="tests.transfer_factor.planted_factor@1"):
            law_registry.LawRegistry().register(planted)


def test_the_ph_law_is_the_hill_activation_of_the_free_proton():
    """cells.transfer_factor.ph_conditioned_factor@1 and one hill_activation read of h, K = 10^(3 - pH50) mM and n the
    slope: one function, within rounding (the first one's tanh form loses accuracy at small f)."""
    rng = np.random.default_rng(0)
    ph, ph50 = rng.uniform(4.0, 9.0, 20000), rng.uniform(4.5, 7.5, 20000)
    slope = rng.uniform(0.5, 6.0, 20000)
    expected = ph_condition.factor(ph, ph50, slope, xp=np)

    def gap(exponent):
        k = (10.0**exponent)[:, None]
        form = np.full(k.shape, hill_factors.ACTIVATION)
        f = product.factor(np.log(10.0 ** (3.0 - ph))[:, None], k, slope[:, None], form, xp=np)
        return float(np.max(np.abs(f - expected)))

    assert gap(3.0 - ph50) < 3e-15
    assert gap(ph50 - 3.0) > 0.1  # Plant: K's exponent of the other sign.


def test_a_condition_of_one_read_is_the_coupling_s_factor_bit_for_bit():
    """The instantaneous Hill factor of cells.operator.species_regulated_availability@1 at basal 0, on its own
    kernel, and the condition's, for one neutral species in each of N cells, both forms."""
    rng = np.random.default_rng(1)
    count = 2000
    amount, volume = 10.0 ** rng.uniform(-9, 0, count), rng.uniform(0.05, 5.0, count)
    k, n = 10.0 ** rng.uniform(-6, 0, count), rng.uniform(0.5, 4.0, count)
    form, cells, rows = rng.integers(1, 3, count), np.arange(count), np.zeros(count, dtype=int)
    state = SimpleNamespace(amount_increment=np.zeros((1, count)), coupling_enabled=np.ones(1))
    coupling = SimpleNamespace(
        amount_reference=amount[None], volume=volume, coupling_route_law=form,
        coupling_route_row=rows, coupling_route_cell=cells,
        coupling_route_half_saturation_mM=k, coupling_route_coefficient=n,
        coupling_route_basal=np.zeros(count), coupling_route_coupling=rows,
        regulatory_slot_cell=np.zeros(0, dtype=int),
    )  # fmt: skip
    read = SimpleNamespace(
        amount_increment=np.zeros((1, count)), extracellular_amount_increment=np.zeros((1, 1))
    )
    layout = SimpleNamespace(
        active=np.ones(count, dtype=bool), amount_reference=amount[None], volume=volume,
        extracellular_amount_reference=np.ones((1, 1)), extracellular_volume=np.ones(1),
        species_condition_node=cells, species_condition_row=rows[:, None],
        species_condition_form=form[:, None], species_condition_half_saturation_mM=k[:, None],
        species_condition_coefficient=n[:, None],
    )  # fmt: skip
    expected = sra.route_factors(state, coupling, xp=np)
    assert np.array_equal(species_condition.factors(read, layout, xp=np), expected)
    quotient = hill_factors.factor(np.log(amount / volume), k, n, form, xp=np)
    assert not np.array_equal(quotient, expected)  # Plant: ln(N/V).
