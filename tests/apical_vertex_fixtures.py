"""Shared helpers for the apical_vertex_mechanics@1 tests (periodic honeycombs)."""

import jax
import jax.numpy as jnp
import numpy as np

from cells.core import vertex_preparation as prep
from cells.core.specs import parse_spec
from cells.models import apical_vertex as av
from cells.processes import vertex_mechanics as vm
from validation.morphogenesis import mg1_theory as theory

LAMBDA, GAMMA = 0.12, 0.04
A_STAR, P_CASE, SIDE, E_STAR = theory.ground_state(LAMBDA, GAMMA)


def honeycomb(nx=4, ny=4, *, area=A_STAR, displacement=0.0, seed=0, **kw):
    model = prep.periodic_honeycomb(
        nx,
        ny,
        cell_area=area,
        line_tension=LAMBDA,
        contractility=GAMMA,
        displacement=displacement,
        seed=seed,
    )
    options = dict(end_time=1.0, observation_times=[0.0, 1.0], dt=0.0625)
    options.update(kw)
    return prep.definition(model, **options)


def arrays(definition):
    spec = parse_spec(definition)
    state, layout = av.initial_values(spec)
    return spec, state, layout, av.topology(layout)


_forces = jax.jit(vm.forces)
_stress = jax.jit(vm.box_stress)


def jax_forces(state, layout):
    return np.asarray(
        _forces(
            jnp.asarray(state.position),
            av.topology(layout),
            jnp.asarray(layout.box),
            av.mechanics(state),
        )
    )


def jax_stress(state, layout):
    return np.asarray(
        _stress(
            jnp.asarray(state.position),
            av.topology(layout),
            jnp.asarray(layout.box),
            av.mechanics(state),
        )
    )


def farhadifar_cut(definition, junction=0, time=0.5):
    model = definition["model"]
    a, b = model["junctions"][junction]["vertices"]
    cells = []
    for c in model["cells"]:
        k = c["corners"]
        edges = {(k[n]["vertex"], k[(n + 1) % len(k)]["vertex"]) for n in range(len(k))}
        if (a, b) in edges or (b, a) in edges:
            cells.append(c["id"])
    empty = {"line_tension": {}, "contractility": {}, "area_elasticity": {}, "preferred_area": {}}
    cut = {
        "time": time,
        "line_tension": {model["junctions"][junction]["id"]: 0.0},
        "contractility": {c: 0.0 for c in cells},
        "area_elasticity": {},
        "preferred_area": {},
    }
    return [{"time": 0.0, **empty}, cut], cells
