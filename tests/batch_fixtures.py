"""Small live worlds for the shared run paths: scalar windows, batches, records and replay.

They are cells.model.reaction_transport@1 definitions (configs/reaction_transport_*.json): two species that
convert in each cell and pass through contacts, which a schedule opens and closes. They compile in
under a second and have an independent reference (tests/reference_reaction_transport.py).

The model takes plain RK4 steps. The run paths have two more step routes, an RK4 step checked by
the model's domain and a model's own checked step, so step_route plants each on this model for a
test's duration (MonkeyPatch only, never in a source file). The planted pieces are the model's own
law and domain: every amount finite and nonnegative, and the forward Euler step of its rates.
"""

import copy
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions.specs import load_spec, parse_spec
from cells.execution.batch import BatchSpec, WorldSpec
from cells.models import reaction_transport

ROOT = Path(__file__).resolve().parents[1]
# One cell without a contact, and three with two (two with one: conftest's, and synthetic_pair's).
MODELS = ("reaction_transport_single", "reaction_transport_chain")
# Rows of (world, step route) for conftest's short_world: both worlds on their model's plain RK4,
# one of them on each planted route.
_ROUTES = (
    *((name, "rk4") for name in MODELS),
    ("reaction_transport_chain", "checked_rk4"),
    ("reaction_transport_chain", "own_step"),
)
ROUTES = tuple(pytest.param(row, id="-".join(row)) for row in _ROUTES)
# The same rows with a window width: every width on the model's own route, and on a planted one
# the width whose last window is padded (seven of ten steps).
WIDTHS = tuple(
    pytest.param(row, width, id=f"{'-'.join(row)}-{width}")
    for row in _ROUTES
    for width in ((1, 7, 1000) if row[1] == "rk4" else (7,))
)


def in_domain(state, parameters, active):
    return jnp.all(jnp.stack([jnp.all(jnp.isfinite(v)) for v in state])) & jnp.all(
        state.amount >= 0
    )


def euler_step(domain):
    """The model's rates over one forward Euler step, refused when its end leaves `domain`."""

    def checked_step(state, dt, control, parameters, active):
        slope = reaction_transport.rhs(state, control, parameters, active)
        updated = jax.tree.map(lambda y, dy: y + dt * dy, state, slope)
        return updated, domain(updated, parameters, active)

    return checked_step


OWN_STEP = euler_step(in_domain)  # One function, so one program per shape in a process.


def step_route(patch, route, domain=None):
    """Plant a step route on the model for a MonkeyPatch's duration ("rk4": its own, none), with
    its own domain or a narrower one."""
    if route == "checked_rk4":
        patch.setattr(reaction_transport, "domain_valid", domain or in_domain, raising=False)
    elif route == "own_step":
        step = euler_step(domain) if domain else OWN_STEP
        patch.setattr(reaction_transport, "checked_step", step, raising=False)
    else:
        assert route == "rk4" and domain is None


def short_spec(name, end=0.3, *, jit=True):
    data = load_spec(ROOT / f"configs/{name}.json").to_dict()

    def trim(value):
        if isinstance(value, list):
            return [
                trim(item)
                for item in value
                if not isinstance(item, dict) or "time" not in item or item["time"] <= end
            ]
        if isinstance(value, dict):
            return {key: trim(item) for key, item in value.items()}
        return value

    data["experiment"] = trim(data["experiment"])
    data["experiment"]["end_time"] = end
    data["experiment"]["observation_times"] = [0.0, 0.113 * end, 0.613 * end, end]
    data["execution"]["jit"] = jit
    data["execution"]["dt"] = min(data["execution"]["dt"], end / 3)
    return parse_spec(data)


def definition(specs, ids=None):
    if ids is None:
        ids = [10 + i for i in range(len(specs))]
    return BatchSpec(
        tuple(WorldSpec(i, s) for i, s in zip(ids, specs, strict=True)), 64, 1000000, 536870912
    )


def same(a, b):
    """Two pytrees' leaves, in order, bitwise: each one's type, shape and bytes."""
    for x, y in zip(jax.tree.leaves(a), jax.tree.leaves(b), strict=True):
        assert np.asarray(x).dtype == np.asarray(y).dtype
        assert np.asarray(x).shape == np.asarray(y).shape
        assert np.asarray(x).tobytes() == np.asarray(y).tobytes()


def assert_parity(got, expected, *, exact=False):
    np.testing.assert_array_equal(got.times, expected.times)
    for a, b in zip(got.history, expected.history, strict=True):
        if exact:
            np.testing.assert_array_equal(a, b)
        else:
            np.testing.assert_allclose(a, b, rtol=2e-12, atol=2e-12)
    assert vars(got.observations).keys() == vars(expected.observations).keys()
    for name, a in vars(got.observations).items():
        b = vars(expected.observations)[name]
        if exact or a.dtype.kind in "bUSiu":
            np.testing.assert_array_equal(a, b)
        else:
            np.testing.assert_allclose(a, b, rtol=2e-11, atol=2e-11)
    for a, b in zip(got.final.layout, expected.final.layout, strict=True):
        np.testing.assert_array_equal(a, b)


def synthetic_pair():
    """Two worlds of one layout on their own clocks: a closed contact opens at 0.137 in world 10
    and at 0.173 in world 11, which converts faster, starts with less and ends first."""
    a = short_spec("reaction_transport_pair", 1).to_dict()
    a["experiment"]["contact"]["schedule"] = [
        {"time": 0, "open_fractions": [0]},
        {"time": 0.137, "open_fractions": [1]},
    ]
    a["experiment"]["observation_times"] = [0, 0.071, 0.137, 0.5, 1]
    b = copy.deepcopy(a)
    b["model"]["parameters"]["reaction"]["forward_rate"][0] = 0.7
    b["model"]["initial_state"]["amount"][0][0] = 0.8
    b["experiment"]["contact"]["schedule"][1]["time"] = 0.173
    b["experiment"]["end_time"] = 0.7
    b["experiment"]["observation_times"] = [0, 0.173, 0.5, 0.7]
    return definition([parse_spec(a), parse_spec(b)])


def failing_second_world(original):
    """`original` (the model's rhs) going non-finite in the pair's world 11, which its first cell's
    forward rate tells apart (0.7, and 0.2 in world 10)."""

    def rhs(state, control, parameters, active):
        slope = original(state, control, parameters, active)
        fails = parameters.forward_rate[0] > 0.5
        return slope._replace(amount=jnp.where(fails, jnp.inf, slope.amount))

    return rhs
