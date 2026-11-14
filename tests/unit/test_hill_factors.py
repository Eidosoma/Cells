"""The neutral Hill helper (processes/hill_factors) against local_species_reactions@1's own rates.

The lead's ruling 7 (docs/INVENTORY_COUPLING_DESIGN.md §6.3): D152's factor expression is inline in
species_reactions.route_rates, so the helper is tested against that operator's code, which stays
untouched. Three zeroth-order sources of one species at one site with one rate constant, one plain,
one under hill_activation and one under hill_inhibition of another species: D152's own rates of the
factored sources must equal the plain rate times exp of the helper's log factor, bit for bit, over a
grid of half-saturations, coefficients and concentrations. Jitted, the helper's log factor agrees
with its host value within 4 eps (XLA's log and logaddexp are not NumPy's).
"""

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.specs import parse_spec
from cells.models import pump_composite as pc
from cells.models.operators import species_reactions as sr
from cells.processes import hill_factors
from validation.tissue import species_reactions_fixtures as rfx

K_VALUES = (1e-9, 1e-6, 1e-3, 0.37, 1.0, 120.0)
N_VALUES = (0.5, 1.0, 1.7, 2.0, 4.0)
X_VALUES = (1e-12, 3e-9, 1e-6, 2.5e-4, 1e-3, 0.8, 1.0, 37.0, 1e3)


def _world():
    raw = rfx.species_world(extra=("Y",), profile=dict(Y=dict(cell_0=1e-4)), faces=False)
    cell = {"cells": ["cell_0"]}
    reactions = [
        rfx.mass_action("plain", cell, {}, {"Y": 1}, 1e-4),
        rfx.mass_action("act", cell, {}, {"Y": 1}, 1e-4, factors=[rfx.hill("hill_activation", "S", 1e-3, 2.0)]),
        rfx.mass_action("inh", cell, {}, {"Y": 1}, 1e-4, factors=[rfx.hill("hill_inhibition", "S", 1e-3, 2.0)]),
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
            jax.jit(lambda a, b, c, kind=kind: hill_factors.log_factor(a, b, c, kind, xp=jnp))(log_x, k, n)
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
    assert np.isfinite(hill_factors.log_factor(np.log(1e-300), 1.0, 4.0, hill_factors.ACTIVATION, xp=np))
    assert hill_factors.factor(np.log(5.0), 1.0, 2.0, 0, xp=np) == 1.0  # Padding: exactly 1.
