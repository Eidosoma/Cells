"""GHK reversal and individual outward currents on one Na/K/Cl membrane at fixed concentrations."""

import json
from pathlib import Path

import jax
import numpy as np
from scipy.optimize import brentq

from cells.definitions.specs import parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.execution.runner import run
from cells.models import surface_pump_v3 as tissue
from cells.registry.models import get_model
from tests.unit.test_passive_routes_kind import charged, closed_pair
from validation.core_seams.references import exact

IONS = ("Na", "K", "Cl")
Z = np.array([1, 1, -1])
CI, CO = (15, 140, 20), (145, 10, 150)
AREA, PERM = 1e-10, 2**-29
DT, T = 1e-7, 300.0
F = float(exact.F_C_per_mol())


def world(weights, voltage, inside=CI, outside=CO, temperature=T):
    routes = [
        charged(s, PERM * w, species=s, host=("patch", "wall_cell_0"))
        for s, w in zip(IONS, weights, strict=True)
    ]
    raw = closed_pair(dt=DT, end=2 * DT, routes=routes)
    m = raw["model"]
    m["temperature_K"] = temperature
    patch = m["membranes"][0]
    assert patch["id"] == "wall_cell_0" and patch["area_m2"] == AREA
    cell, bath = m["cells"][0], m["extracellular"][0]
    for node, concentrations in ((cell, inside), (bath, outside)):
        for s, c in zip(IONS, concentrations, strict=True):
            node["initial_amount_fmol"][s] = c * node["volume_pL"]
        node["fixed_charge_equivalent_fmol"] = -np.dot(Z, concentrations) * node["volume_pL"]
    charge = patch["capacitance_F"] * voltage
    cell["initial_charge_C"] = charge
    cell["fixed_charge_equivalent_fmol"] += charge / (F * 1e-15)
    return parse_spec(raw)


def outward(spec):
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    control = model.Control(*(v[0] for v in control_values(spec, [0.0])))
    field = tissue.field_values(state, control, p, xp=np, structure=model.structure)
    r = field.rates
    assert r.valid
    rows = [list(spec.model.species_ids).index(s) for s in IONS]
    return (
        float(r.membrane_voltage_V[0]),
        float(r.membrane_current_A[0]),
        Z * F * 1e-15 * r.membrane_flux_fmol_s[rows, 0],
    )


def reference(weights, voltage=None, inside=CI, outside=CO, temperature=T):
    with exact.context():
        d = exact.dec
        na, k, cl = map(d, weights)
        top = na * outside[0] + k * outside[1] + cl * inside[2]
        bottom = na * inside[0] + k * inside[1] + cl * outside[2]
        thermal = exact.RT_J_per_mol(temperature) / exact.F_C_per_mol()
        if voltage is None:
            return float(thermal * (top / bottom).ln())
        currents = []
        for z, ci, co, w in zip(Z.tolist(), inside, outside, weights, strict=True):
            x = z * d(voltage) / thermal
            b = x / (x.exp() - 1) if x else d(1)
            j = z * exact.F_C_per_mol() * d(AREA) * d(PERM) * d(w) * b * (ci * x.exp() - co)
            currents.append(float(j))
        return np.array(currents)


def reversal(weights, inside=CI, outside=CO, temperature=T):
    target = reference(weights, None, inside, outside, temperature)
    root = brentq(
        lambda v: outward(world(weights, v, inside, outside, temperature))[1],
        -0.15,
        0.15,
        xtol=5e-17,
    )
    assert abs(root - target) < 2e-15
    return target, root


def check(weights, *, integrate=False):
    target, root = reversal(weights)
    for offset in (-0.005, 0.0, 0.005):
        v = target + offset
        spec = world(weights, v)
        measured_v, total, individual = outward(spec)
        expected = reference(weights, v)
        scale = sum(abs(expected))
        assert abs(measured_v - v) < 2e-15
        assert max(abs(individual - expected)) < 1e-13 * scale
        assert abs(total - sum(expected)) < 1e-13 * scale
        if offset:
            assert offset * total > 0
        else:
            assert min(abs(individual)) > 1e-14 * scale and min(individual) < 0 < max(individual)
            result = dict(
                permeability_weights=weights,
                analytic_mV=1e3 * target,
                host_mV=1e3 * root,
                outward_pA=(individual * 1e12).tolist(),
                residual_A=total,
            )
            if integrate:
                run_result = run(spec)
                obs = run_result.observations
                rows = [list(spec.model.species_ids).index(s) for s in IONS]
                observed = Z * F * 1e-15 * np.asarray(obs.membrane_flux_fmol_s)[0, rows, 0]
                assert max(abs(observed - expected)) < 1e-13 * scale
                moved = np.asarray(run_result.history.passive_transferred)[-1]
                # Transfers are inward, by species and named route; the reference is outward charge.
                avg = -Z * F * 1e-15 * moved[rows].sum(axis=1) / (2 * DT)
                np.testing.assert_allclose(avg, expected, rtol=2e-6, atol=0)
                result["two_step_mean_outward_pA"] = (avg * 1e12).tolist()
    return result


def squid_axon():
    path = Path(__file__).with_name("data") / "hodgkin_katz1949_rest.json"
    data = json.loads(path.read_text())
    assert tuple(data["ion_order"]) == IONS
    potentials = {}
    for solution, outside in data["outside_mM"].items():
        _, v = reversal(
            data["relative_permeability"], data["inside_mM"], outside, data["assumed_temperature_K"]
        )
        potentials[solution] = 1000 * v
    return [
        dict(
            solution=key,
            observed_mV=row["observed_mV"],
            predicted_mV=potentials[key] - potentials[row["baseline"]],
        )
        for key, row in data["resting_shifts"].items()
    ]


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    weights = [(0.1, 1, 0.4), (4, 1, 0.5), (2, 1, 1), (2.00002, 1, 1)]
    print(
        json.dumps(
            dict(
                synthetic=[check(w, integrate=i == 0) for i, w in enumerate(weights)],
                resting_shifts=squid_axon(),
            ),
            indent=2,
            allow_nan=False,
        )
    )
