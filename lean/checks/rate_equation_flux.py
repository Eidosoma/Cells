"""Check the deterministic assembly reaction flux against linear mass action and PGI data."""

import json
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
from scipy.optimize import brentq

from cells.definitions.specs import parse_spec
from cells.models.assembly_lineages_v2.rate_equations import Problem
from tests.assembly_lineage_v2_fixtures import definition
from tests.unit.test_assembly_lineages_v2_rate_equations import as_representation, linear_world

EPS = np.finfo(np.float64).eps
AVOGADRO = 6.02214076e23  # per mole, exact SI definition


def setup(world):
    raw = as_representation(definition(world))
    raw["execution"]["step_capacity"] = 4
    problem = Problem(parse_spec(raw))
    assert [p.name for p in problem.world.places] == ["A@pool", "B@pool", "C@pool", "M@membrane"]
    return problem, jax.jit(jax.vmap(problem.flux))


def states(problem, a, b, c):
    a, b, c = np.broadcast_arrays(a, b, c)
    n = np.zeros((a.size, problem.P))
    n[:, :4] = np.column_stack((a, b, c, np.ones(a.size)))
    return jnp.asarray(n)


def pair_world(ratio, temperature):
    world = linear_world()
    world["steps"] = world["steps"][:1]
    world["species"][1]["standard_mu_RT"]["solution"] = -float(np.log(ratio))
    world["units"]["temperature_K"] = temperature
    return world


def closed_network():
    world = linear_world()
    for species in world["species"][:3]:
        species["standard_mu_RT"]["solution"] = 0.0
    problem, evaluate = setup(world)
    a = 8192.0
    b = a * np.array([0.5, 1 - 1e-9, 1.0, 1 + 1e-9, 2.0])
    flux, delta = map(np.asarray, evaluate(states(problem, a, b, a)))
    # A ⇌ B ⇌ C with equal standard potentials and rates 2 and 1 per second.
    expected = np.column_stack((2 * (a - b), b - a))
    force = np.log1p((b - a) / a)
    np.testing.assert_allclose(
        delta[:, :2], np.column_stack((force, -force)), atol=32 * EPS, rtol=0
    )
    np.testing.assert_allclose(flux[:, :2], expected, atol=32 * EPS * 2 * b.max(), rtol=0)
    np.testing.assert_array_equal(np.sign(flux[:, :2]), np.sign(expected))
    np.testing.assert_array_equal(flux[:, 2:], 0)
    np.testing.assert_array_equal(delta[:, 2:], 0)
    power = -flux * delta
    assert np.all(power >= 0) and np.all(power[[0, 1, 3, 4], :2] > 0)
    return dict(
        active_steps=2,
        inactive_slots=2,
        b_over_a=(b / a).tolist(),
        reaction_flux_per_s=flux[:, :2].tolist(),
        total_heat_kT_per_s=power.sum(axis=1).tolist(),
        max_flux_error_per_s=float(np.max(np.abs(flux[:, :2] - expected))),
    )


def held_reservoir():
    world = pair_world(1.0, 298.15)
    held = 2.0  # mM
    world["phases"]["pool"]["species"][0] = {"id": "A", "kind": "held", "held_mM": held}
    del world["founder"]["A@pool"]
    problem, evaluate = setup(world)
    scale = AVOGADRO * world["phases"]["pool"]["volume_L"] * 1e-3  # molecules per mM
    b = np.array([1.0, 2.0, 4.0])
    flux, delta = map(np.asarray, evaluate(states(problem, 0, b * scale, 1000)))
    expected = 2 * scale * (held - b)
    np.testing.assert_allclose(flux[:, 0], expected, atol=32 * EPS * scale * b.max() * 2, rtol=0)
    np.testing.assert_allclose(delta[:, 0], np.log(b / held), atol=32 * EPS, rtol=0)
    assert np.all(-flux * delta >= 0)
    # Without the reservoir work, the ideal potential of B is negative even at 4 mM.
    omitted = np.log(b[-1] / world["units"]["standard_concentration_mM"])
    assert omitted < 0 < delta[-1, 0] and flux[-1, 0] < 0
    return dict(
        held_a_mM=held,
        b_mM=b.tolist(),
        deltaF_kT=delta[:, 0].tolist(),
        flux_per_s=flux[:, 0].tolist(),
        last_deltaF_without_work_kT=float(omitted),
    )


def pgi_comparison():
    manifest = Path(__file__).with_name("data") / "pgi_flux_direction.json"
    data = json.loads(manifest.read_text())
    extract = data["eicher2012_pgi_direction"]
    world = pair_world(extract["fitted_F6P_over_G6P"], 273.15 + extract["temperature_C"])
    problem, evaluate = setup(world)
    scale = AVOGADRO * world["phases"]["pool"]["volume_L"] * 1e-3
    courses = []
    for course in extract["courses"]:
        _, g, f = course["first"]
        _, end_g, end_f = course["last"]
        flux, _ = evaluate(states(problem, g * scale, f * scale, 1000))
        predicted = int(np.sign(float(flux[0, 0])))
        assert predicted == np.sign(end_f - f) == -np.sign(end_g - g) and predicted != 0
        courses.append(
            dict(
                dataset=course["dataset"],
                initial_F6P_over_G6P=f / g,
                change_G6P_mM=end_g - g,
                change_F6P_mM=end_f - f,
                model_sign=predicted,
            )
        )

    rabbit = data["dyson1968_pgi_equilibrium"]
    problem, evaluate = setup(
        pair_world(rabbit["kinetic_F6P_over_G6P"], 273.15 + rabbit["temperature_C"])
    )

    # Locate the engine's zero using the kinetic estimate alone. Compare the separate assay below.
    def flux_at(ratio):
        flux, _ = evaluate(states(problem, 8192.0, 8192.0 * ratio, 1000.0))
        return float(flux[0, 0])

    ratio = brentq(flux_at, 0.1, 1.0, xtol=1e-15)
    np.testing.assert_allclose(ratio, rabbit["kinetic_F6P_over_G6P"], atol=32 * EPS, rtol=0)
    measured = rabbit["measured_F6P_over_G6P"]
    return dict(
        eicher=courses,
        dyson=dict(
            model_stall_ratio=ratio, measured_ratio=measured, model_minus_measured=ratio - measured
        ),
    )


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    print(
        json.dumps(
            dict(network=closed_network(), reservoir=held_reservoir(), pgi=pgi_comparison()),
            indent=2,
            allow_nan=False,
        )
    )
