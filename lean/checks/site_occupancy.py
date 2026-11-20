"""Two populations on a finite pool, independent binding ODE, and joint stage guard."""

import json

import jax
import numpy as np
from scipy.integrate import solve_ivp

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.operators import site_occupancy as sites
from cells.registry.models import get_model
from validation.tissue import site_occupancy_fixtures as fixture


def trajectory(dt):
    end = 0.04
    pops = [
        fixture.population("first", copies=602214, alpha=1, k_on=10000, k_off=1.8, k_int=2),
        fixture.population("second", copies=903321, alpha=1, theta0=0.36, k_on=14000, k_off=4.1),
    ]
    raw = fixture.face_free_sites(pops, dt=dt, end=end)
    spec = parse_spec(raw)
    state, p = get_model(spec.model).initial_values(spec)
    ligand = list(spec.model.species_ids).index(fixture.LIGAND)
    node = next(k for k, n in enumerate(raw["model"]["extracellular"]) if n["id"] == "ecs_0")
    volume = raw["model"]["extracellular"][node]["volume_pL"]
    start = raw["model"]["extracellular"][node]["initial_amount_fmol"][fixture.LIGAND]
    capacity = np.array([pop["copies"] / 602214076 for pop in pops])
    bound = capacity * [pop["initial_occupancy"] for pop in pops]
    bind = np.array([pop["association_rate_per_mM_per_s"] for pop in pops])
    release = np.array([pop["dissociation_rate_per_s"] for pop in pops])
    uptake = np.array([2.0, 0.0])

    def derivative(t, y):
        pool, b = y[0], y[1:3]
        binding = bind * (pool / volume) * (capacity - b) - release * b
        internal = uptake * b
        return np.r_[-sum(binding), binding - internal, sum(internal)]

    ref = solve_ivp(
        derivative, (0, end), np.r_[start, bound, 0.0], method="DOP853", rtol=3e-13, atol=1e-18
    )
    assert ref.success
    assert len(set(p.site_facing_pool)) == 1
    step = sites.half_step_terms(state, np.ones(2), np.ones(2), dt / 2, p, xp=np)
    assert step.valid and 0 < step.max_hl < 0.5
    hist = run(spec).history
    outside = start + np.asarray(hist.extracellular_amount_increment)[:, ligand, node]
    free = capacity - bound + np.asarray(hist.site_free_increment_fmol)
    occupied = bound + np.asarray(hist.site_bound_increment_fmol)
    delivered = np.asarray(hist.amount_increment)[:, ligand, 0]
    np.testing.assert_allclose(
        delivered, np.asarray(hist.site_internalised_fmol).sum(axis=1), rtol=0, atol=3e-18
    )
    assert min(outside) > 0 and min(free.min(), occupied.min(), delivered.min()) >= 0
    material = outside + occupied.sum(axis=1) + delivered
    moiety_error = float(np.max(np.abs(free + occupied - capacity)))
    cargo_error = float(np.max(np.abs(material - (start + sum(bound)))))
    assert max(moiety_error, cargo_error) < 3e-18
    final = np.r_[outside[-1], occupied[-1], delivered[-1]]
    error = float(np.max(np.abs(final - ref.y[:, -1])))
    assert occupied[-1, 0] > bound[0] and occupied[-1, 1] > bound[1] and delivered[-1] > 0
    return dict(
        dt_s=dt,
        final_fmol=final.tolist(),
        max_final_error_fmol=error,
        site_residual_fmol=moiety_error,
        cargo_residual_fmol=cargo_error,
    )


def competition():
    pops = [fixture.population(name, copies=602214, alpha=1, k_on=60000) for name in ("a", "b")]
    spec = parse_spec(fixture.face_free_sites(pops, dt=0.01, end=0.01, node_mM=1e-5))
    state, p = get_model(spec.model).initial_values(spec)
    rows = []
    for opening in ([1, 0], [0, 1], [1, 1]):
        step = sites.half_step_terms(state, np.array(opening), np.zeros(2), 0.005, p, xp=np)
        rows.append(dict(binding=opening, max_hL=float(step.max_hl), admitted=bool(step.valid)))
    assert [r["admitted"] for r in rows] == [True, True, False]
    assert rows[2]["max_hL"] > 0.5
    return rows


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    coarse, fine = (trajectory(dt) for dt in (0.005, 0.0025))
    ratio = coarse["max_final_error_fmol"] / fine["max_final_error_fmol"]
    assert 6 < ratio < 10, ratio
    print(
        json.dumps(
            dict(trajectories=[coarse, fine], error_ratio=ratio, guard=competition()),
            indent=2,
            allow_nan=False,
        )
    )
