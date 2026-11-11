"""apical_vertex_mechanics@1: definition, energy, forces, images and the step bound.

Energies and forces are compared with the closed forms of the regular honeycomb
(validation/morphogenesis/mg1_theory.py) and with the independent numpy reference
(mg1_reference.py, closed-form gradient). Runs are in test_apical_vertex_runs.py.
"""

import copy

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core.specs import ConfigError, parse_spec
from cells.models import apical_vertex as av
from cells.processes import vertex_mechanics as vm
from tests.apical_vertex_fixtures import (
    A_STAR,
    E_STAR,
    GAMMA,
    LAMBDA,
    P_CASE,
    arrays,
    honeycomb,
    jax_forces,
)
from validation.morphogenesis import mg1_reference as ref
from validation.morphogenesis import mg1_theory as theory

jax.config.update("jax_enable_x64", True)


def test_definition_round_trip_and_structural_refusals():
    definition = honeycomb()
    spec = parse_spec(definition)
    assert parse_spec(spec.to_dict()).to_dict() == spec.to_dict()
    assert spec.to_dict()["model"] == definition["model"]

    def refused(edit, match):
        bad = copy.deepcopy(definition)
        edit(bad)
        with pytest.raises(ConfigError, match=match):
            parse_spec(bad)

    def wrong_image(d):
        d["model"]["cells"][0]["corners"][1]["image"] = [1, 0]

    def clockwise(d):
        d["model"]["cells"][3]["corners"].reverse()

    def missing_junction(d):
        d["model"]["junctions"].pop()

    def unbounded(d):
        cell = d["model"]["cells"][0]["id"]
        d["experiment"]["parameter_controls"][0]["contractility"] = {cell: 0.0}
        d["model"]["junctions"][0]["line_tension"] = -0.1

    refused(wrong_image, "periodic image|positive")
    refused(clockwise, "junction|direction|positive")
    refused(missing_junction, "junction")
    refused(unbounded, "unbounded|negative-tension|contractility")


def test_regular_honeycomb_energy_stress_and_reference():
    spec, state, layout, topo = arrays(honeycomb())
    g = vm.geometry(state.position, topo, layout.box, xp=np)
    np.testing.assert_allclose(g.area[:16], A_STAR, rtol=1e-12)
    np.testing.assert_allclose(g.perimeter[:16], P_CASE, rtol=1e-12)
    energy = vm.energy(state.position, topo, layout.box, av.mechanics(state), xp=np)
    assert abs(energy / 16 - E_STAR) <= 1e-12 * E_STAR
    stress = np.asarray(
        vm.box_stress(
            jnp.asarray(state.position), topo, jnp.asarray(layout.box), av.mechanics(state)
        )
    )
    assert np.max(np.abs(stress)) < 1e-11
    for scale in (0.95, 1.05):
        spec, state, layout, topo = arrays(honeycomb(area=A_STAR * scale**2))
        stress = np.asarray(
            vm.box_stress(
                jnp.asarray(state.position), topo, jnp.asarray(layout.box), av.mechanics(state)
            )
        )
        expected = theory.stress_half_trace(A_STAR * scale**2, LAMBDA, GAMMA)
        assert abs(0.5 * np.trace(stress) - expected) <= 1e-10 * abs(expected)
        assert abs(stress[0, 1]) < 1e-12 and abs(stress[1, 0]) < 1e-12
        reference = ref.box_stress(ref.from_definition(spec.to_dict()), state.position[:32])
        np.testing.assert_allclose(stress, reference, atol=1e-7)


def test_forces_match_closed_form_reference_and_balance():
    definition = honeycomb(displacement=0.05, seed=3)
    spec, state, layout, topo = arrays(definition)
    tissue = ref.from_definition(definition)
    energy = vm.energy(state.position, topo, layout.box, av.mechanics(state), xp=np)
    assert abs(energy - ref.energy(tissue, tissue.position)) <= 1e-13 * abs(energy)
    force = jax_forces(state, layout)
    np.testing.assert_allclose(force, ref.forces(tissue, tissue.position), atol=1e-12)
    assert np.max(np.abs(force.sum(axis=0))) < 1e-13
    padded = copy.deepcopy(definition)
    padded["execution"].update(
        capacity=20, vertex_capacity=40, junction_capacity=60, half_edge_capacity=120
    )
    _, pstate, playout, ptopo = arrays(padded)
    np.testing.assert_allclose(jax_forces(pstate, playout)[: len(force)], force, rtol=0, atol=1e-15)
    assert np.all(jax_forces(pstate, playout)[len(force) :] == 0)


def test_periodic_image_shift_leaves_energy_unchanged():
    definition = honeycomb(displacement=0.03, seed=1)
    spec, state, layout, topo = arrays(definition)
    before = vm.energy(state.position, topo, layout.box, av.mechanics(state), xp=np)
    moved = copy.deepcopy(definition)
    vertex = moved["model"]["vertices"][5]
    period = moved["model"]["periods"][0]
    vertex["position"] = [vertex["position"][0] + period[0], vertex["position"][1]]
    vid = vertex["id"]
    for cell in moved["model"]["cells"]:
        for corner in cell["corners"]:
            if corner["vertex"] == vid:
                corner["image"][0] -= 1
    for j in moved["model"]["junctions"]:
        if j["vertices"][0] == vid:
            j["image"][0] += 1
        if j["vertices"][1] == vid:
            j["image"][0] -= 1
    _, mstate, mlayout, mtopo = arrays(moved)
    after = vm.energy(mstate.position, mtopo, mlayout.box, av.mechanics(mstate), xp=np)
    assert abs(after - before) <= 1e-12 * abs(before)


@pytest.mark.parametrize("line_tension", [0.12, -0.6])
def test_hessian_rate_bounds_the_hessian(line_tension):
    definition = honeycomb(2, 2, displacement=0.04, seed=2)
    for j in definition["model"]["junctions"]:
        j["line_tension"] = line_tension
    spec, state, layout, topo = arrays(definition)
    hessian = jax.jit(jax.hessian(vm.energy))(
        jnp.asarray(state.position), topo, jnp.asarray(layout.box), av.mechanics(state)
    )
    n = state.position.size
    largest = np.max(np.abs(np.linalg.eigvalsh(np.asarray(hessian).reshape(n, n))))
    rho = vm.hessian_rate(state.position, topo, layout.box, av.mechanics(state), layout.friction)
    assert largest <= float(rho)
