"""Check passive charged routes from the compiled law to a finite tissue pair and two I–V curves."""

import json
from itertools import product
from math import expm1, log
from pathlib import Path

import jax
import numpy as np
from scipy.integrate import solve_ivp

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.laws.routes import constant_field_permeation as law
from tests.unit.test_passive_routes_kind import charged_pair
from validation.core_seams.references import exact

F = float(exact.F_C_per_mol())
R = float(exact.dec(exact.GAS_CONSTANT))
DATA = Path(__file__).with_name("data")


def components():
    temperature, area, perm, vi, vo = 300.0, 8e-10, 6e-7, 0.5, 2.0
    rows = []
    expected = []
    for z, (ci, co), opening in product(
        (-2, -1, 1, 2), ((10, 140), (140, 10), (75, 75)), (0, 0.35, 1)
    ):
        xr = log(co / ci)
        for x in (-8, -1.001e-4, -0.999e-4, 0, 0.999e-4, 1.001e-4, 8, xr - 1e-7, xr, xr + 1e-7):
            voltage = x * R * temperature / (z * F)
            rows.append((ci, co, voltage, z, opening))
            with exact.context():
                rt, q = exact.RT_J_per_mol(temperature), z * exact.F_C_per_mol()
                xd = exact.Dual(q * exact.dec(voltage) / rt, 1)
                b = xd / (xd.exp() - 1) if xd.a else exact.Dual(1, -0.5)
                ap = exact.dec(area) * exact.dec(perm) * exact.dec(opening)
                k = ap * 10**15
                j = ((co - ci) * b - ci * xd) * k
                h = j.a * (rt * (exact.dec(co) / ci).ln() - q * exact.dec(voltage)) / 1000
                gain = ap * q**2 / rt
                g = gain * (ci - (co - ci) * b.b)
                assert gain * min(ci, co) <= g <= gain * max(ci, co)
                in_slope = k * (b.a + xd.a) / exact.dec(vi)
                out_slope = k * b.a / exact.dec(vo)
                expected.append((j.a, h, gain * max(ci, co), in_slope, out_slope, g))

    def fields(ci, co, v, z, opening):
        args = (ci, co, v, z, temperature, area, perm, opening)
        flux = law.flux_fmol_s(*args)
        heat = law.heat_pJ_s(flux, *args[:5])
        slopes = law.material_slope_per_s(*args[2:], vi, vo)
        dj = jax.grad(law.flux_fmol_s, argnums=2)(*args)
        return flux, heat, law.conductance_S(*args), *slopes, -z * F * 1e-15 * dj

    ci, co, v, z, opening = np.array(rows).T
    actual = np.array(jax.jit(jax.vmap(fields))(ci, co, v, z, opening))
    assert actual.dtype == np.float64
    reference = np.array(expected, dtype=np.float64).T
    errors = np.abs(actual - reference)
    # Near reversal, bound cancellation errors relative to the one-way flux and thermal energy.
    one_way = (
        area
        * perm
        * opening
        * 1e15
        * np.maximum(ci, co)
        * (1 + np.abs(z * F * v / (R * temperature)))
    )
    assert np.all(errors[0] <= 16 * exact.EPS * one_way)
    assert np.all(errors[1] <= 64 * exact.EPS * one_way * R * temperature / 1000)
    np.testing.assert_allclose(actual[2:5], reference[2:5], rtol=2e-13, atol=0)
    # Float64 AD of x/expm1(x) near the switch subtracts two nearly equal terms.
    np.testing.assert_allclose(actual[5], reference[5], rtol=1e-10, atol=0)
    return dict(
        cases=len(rows),
        max_flux_error_fmol_s=float(errors[0].max()),
        max_heat_error_pJ_s=float(errors[1].max()),
        max_slope_error_S=float(errors[5].max()),
    )


def tissue(z, steps):
    end = 0.008
    raw = charged_pair(
        valence=z, pool_mM=2e-5, node_mM=1e-5, voltage_fmol=-5.18e-5, end=end, dt=end / steps
    )
    spec = parse_spec(raw)
    model = raw["model"]
    route = model["passive_routes"][0]
    patch_index = next(i for i, p in enumerate(model["membranes"]) if p["id"] == route["patch"])
    patch = model["membranes"][patch_index]
    node_index = next(
        i for i, n in enumerate(model["extracellular"]) if n["id"] == patch["outside"]
    )
    cell, node = model["cells"][0], model["extracellular"][node_index]
    ni, no = (n["initial_amount_fmol"]["X"] for n in (cell, node))
    k = patch["area_m2"] * route["permeability_m_per_s"] * 1e15
    rt = R * model["temperature_K"]

    def voltage(y):
        return (-node["initial_charge_C"] + z * F * 1e-15 * y) / patch["capacitance_F"]

    def rates(t, state):
        y = state[0]  # inward signed extent in fmol
        ci, co = (ni + y) / cell["volume_pL"], (no - y) / node["volume_pL"]
        x = z * F * voltage(y) / rt
        b = x / expm1(x) if x else 1.0
        flux = k * ((co - ci) * b - ci * x)
        return flux, flux * rt * (log(co / ci) - x) / 1000

    refs = []
    for method in ("DOP853", "Radau"):
        solution = solve_ivp(rates, (0, end), (0, 0), method=method, rtol=2e-12, atol=1e-17)
        if not solution.success:
            raise ArithmeticError(solution.message)
        refs.append(solution.y[:, -1])
    np.testing.assert_allclose(*refs, rtol=2e-10, atol=1e-16)
    result = run(spec)
    state = result.final.state
    species = spec.model.species_ids.index("X")
    y = float(state.passive_transferred[species, 0])
    heat = float(state.passive_dissipated_energy_pJ[0])
    volts = np.asarray(result.observations.membrane_voltage_V)[:, patch_index]
    np.testing.assert_allclose(
        [
            state.amount_increment[species, 0],
            state.extracellular_amount_increment[species, node_index],
        ],
        [y, -y],
        rtol=64 * exact.EPS,
        atol=0,
    )
    np.testing.assert_allclose([volts[0], volts[-1]], [voltage(0), voltage(y)], atol=1e-12, rtol=0)
    assert heat > 0 and abs(volts[-1] - volts[0]) > 1e-3
    actual = np.array([y, heat, volts[-1]])
    ref = np.array([*refs[0], voltage(refs[0][0])])
    np.testing.assert_allclose(actual, ref, rtol=5e-4, atol=0)
    return dict(
        valence=z,
        steps=steps,
        inward_fmol=y,
        heat_pJ=heat,
        final_V=float(volts[-1]),
        reference=ref.tolist(),
        abs_errors=np.abs(actual - ref).tolist(),
        global_charge_error_C=float(result.diagnostics["max_global_charge_error_C"]),
    )


def biology():
    chloride = json.loads((DATA / "freedman1997_chloride.json").read_text())
    potassium = json.loads((DATA / "pfeffermann2026_potassium.json").read_text())

    def outward(ci, co, voltage_mV, z, temperature, ap):
        j = law.flux_fmol_s(ci, co, voltage_mV / 1000, z, temperature, 1.0, ap, 1.0, xp=np)
        return float(-z * F * 1e-15 * j)  # amperes, or A per g Hb if ap is per g Hb

    cal, test = chloride["fit"], chloride["evaluation"]

    def chloride_at_unit_rate(v):
        ap = chloride["cell_water_L_per_g_Hb"] / 1000  # m³ per g Hb × 1/s
        return 1000 * outward(
            chloride["inside_Cl_mM"],
            chloride["outside_Cl_mM"],
            v,
            -1,
            chloride["temperature_K"],
            ap,
        )

    fit_rate = cal["current_mA_per_g_Hb"] / chloride_at_unit_rate(cal["voltage_mV"])
    predicted = fit_rate * chloride_at_unit_rate(test["voltage_mV"])
    reading = chloride["figure_reading_precision"]
    corners = [
        (cal["current_mA_per_g_Hb"] + si * reading["current_mA_per_g_Hb"])
        * chloride_at_unit_rate(test["voltage_mV"] + st * reading["voltage_mV"])
        / chloride_at_unit_rate(cal["voltage_mV"] + sc * reading["voltage_mV"])
        for si, st, sc in product((-1, 1), repeat=3)
    ]
    slopes = chloride["slope_conductance_S_per_g_Hb"]
    rbc = dict(
        fit_rate_per_s=fit_rate,
        predicted_mA_per_g_Hb=predicted,
        observed_mA_per_g_Hb=test["current_mA_per_g_Hb"],
        reading_sensitivity_mA_per_g_Hb=[min(corners), max(corners)],
        model_max_slope_ratio=chloride["outside_Cl_mM"] / chloride["inside_Cl_mM"],
        measured_slope_ratio=slopes["hyperpolarized"] / slopes["near_reversal"],
    )

    cal, test = potassium["fit"], potassium["evaluation"]
    ci, co = potassium["inside_K_mM"], potassium["outside_K_mM"]

    def bilayer_at(t):
        return (
            cal["current_nA"]
            * outward(ci, co, test["voltage_mV"], 1, t, 1)
            / outward(ci, co, cal["voltage_mV"], 1, t, 1)
        )

    t = potassium["temperature_K_assumed"]
    bilayer = dict(
        predicted_nA=bilayer_at(t),
        observed_nA=test["current_nA"],
        predicted_reversal_mV=1000 * R * t / F * log(co / ci),
        measured_reversal_mV=potassium["reported_reversal_mV"],
        predicted_nA_at_temperature_limits=[
            bilayer_at(t0) for t0 in potassium["temperature_K_sensitivity"]
        ],
    )
    return dict(red_cell_chloride=rbc, bilayer_potassium=bilayer)


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    with jax.default_device(jax.devices("cpu")[0]):
        panel = components()
        runs = [tissue(z, n) for z in (-1, 2) for n in (64, 128)]
        for coarse, fine in zip(runs[::2], runs[1::2], strict=True):
            refinement = np.array(coarse["abs_errors"]) / np.array(fine["abs_errors"])
            assert np.all((3.5 < refinement) & (refinement < 4.5)), refinement
        print(
            json.dumps(
                dict(components=panel, tissue=runs, biology=biology()), indent=2, allow_nan=False
            )
        )
