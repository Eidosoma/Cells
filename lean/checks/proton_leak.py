"""Compare proton reversal and power with a high-precision reference and a buffered tissue cell."""

import json
import math
from decimal import Decimal, localcontext

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.laws.transport import proton_leak
from tests.unit import test_proton_buffer_kind as fixture
from validation.betse.junction_transport.check import decimal_flux
from validation.compartment_ph.ph_reference import free_proton
from validation.tissue.surface_reference import F, R


def inward_reference(h_in, h_out, voltage, temperature, area, permeability, opening):
    # The independent 70-digit reference counts inside to outside. Its D/length is P.
    return -decimal_flux(
        h_in, h_out, voltage, 1, temperature, area, permeability, 1, opening, {"F": F, "R": R}
    )


def components():
    temperature, area, permeability = 310.0, 7.854e-10, 6e-7
    h_in = 1e-4  # mM
    reversal = math.log(2)
    # (outside/inside free concentration, x, availability, expected inward sign).
    # A None marks the manufactured analytic equilibrium where float64 can leave a residual.
    cases = [
        (2.0, 0.0, 1.0, 1),
        (2.0, 1.0, 1.0, -1),
        (0.5, -1.0, 1.0, 1),
        (2.0, reversal - 1e-7, 1.0, 1),
        (2.0, reversal, 1.0, None),
        (2.0, reversal + 1e-7, 1.0, -1),
        (2.0, 1.0, 0.0, 0),
        (1.0, 0.0, 1.0, 0),
        (1.0, -1.001e-4, 0.5, 1),
        (1.0, -0.999e-4, 0.5, 1),
        (1.0, 0.999e-4, 0.5, -1),
        (1.0, 1.001e-4, 0.5, -1),
    ]
    ratios, x, opening = np.array([row[:3] for row in cases]).T
    h_out = h_in * ratios
    voltage = x * (R * temperature / F)
    args = h_in, h_out, voltage, temperature
    flux = np.asarray(jax.jit(proton_leak.flux_fmol_s)(*args, area, permeability, opening))
    heat = np.asarray(jax.jit(proton_leak.heat_pJ_s)(flux, *args))
    expected = np.array(
        [
            inward_reference(h_in, ho, v, temperature, area, permeability, m)
            for ho, v, m in zip(h_out, voltage, opening, strict=True)
        ]
    )
    # Independently form the potential from the concentration ratio and patch voltage.
    expected_heat = 1e-3 * expected * (R * temperature * np.log(ratios) - F * voltage)
    flux_unit = area * permeability * 1e15 * h_in
    flux_atol = 1e-12 * flux_unit  # The zero-voltage flux of the twofold concentration case.
    heat_atol = 1e-3 * R * temperature * flux_atol
    assert flux.dtype == heat.dtype == np.float64
    np.testing.assert_allclose(flux, expected, atol=flux_atol, rtol=0)
    np.testing.assert_allclose(heat, expected_heat, atol=heat_atol, rtol=0)
    for j, q, (_, _, _, sign) in zip(flux, heat, cases, strict=True):
        if sign is None:
            assert abs(j) < flux_atol
        else:
            assert np.sign(j) == sign
            assert q > 0 if sign else q == 0
    return {
        "cases": len(cases),
        "flux_atol_fmol_s": flux_atol,
        "heat_atol_pJ_s": heat_atol,
        "max_flux_error_fmol_s": float(np.max(np.abs(flux - expected))),
        "max_heat_error_pJ_s": float(np.max(np.abs(heat - expected_heat))),
        "opposed_flux_fmol_s": float(flux[1]),
        "nernst_residual_fmol_s": float(flux[4]),
    }


def small_voltage_reversal():
    """Resolve the polynomial's reversal shift below the spacing of float64 near 1."""
    with localcontext() as ctx:
        ctx.prec = 80
        x = Decimal("0.00009")
        even_terms = 1 + x**2 / 12 - x**4 / 720
        ratio = (even_terms + x / 2) / (even_terms - x / 2)
        shift = ratio - x.exp()
        # Between the two thresholds the polynomial flux is outward and the analytic drive inward.
        middle = (ratio + x.exp()) / 2
        scaled_flux = middle * (even_terms - x / 2) - (even_terms + x / 2)
        assert scaled_flux < 0 < middle.ln() - x
        return {"x": str(x), "outside_inside_ratio_shift": f"{shift:.12E}"}


def buffered_tissue():
    raw = fixture.leaky_world()
    spec = parse_spec(raw)
    model, state, params, control = fixture.host(spec)
    readings = model.readouts(state, control, params, xp=np)
    assert readings.valid
    h = spec.model.species_ids.index("H")
    rates = readings.field.rates
    inward = -float(rates.membrane_flux_fmol_s[h, 0])
    voltage = float(rates.membrane_voltage_V[0])
    cell = spec.model.cells[0]
    total = cell.initial_amount_fmol[h] / cell.volume_pL
    buffer = cell.initial_amount_fmol[spec.model.species_ids.index("B")] / cell.volume_pL
    h_in = free_proton(total, [(buffer, fixture.h_mM(fixture.PK))], fixture.C0_MM)
    bath = spec.model.extracellular[0]
    h_out = bath.initial_amount_fmol[h] / bath.volume_pL
    route = raw["model"]["passive_routes"][0]
    patch = next(p for p in raw["model"]["membranes"] if p["id"] == route["patch"])
    args = (
        h_out,
        voltage,
        spec.model.temperature_K,
        patch["area_m2"],
        route["permeability_m_per_s"],
        1,
    )
    expected = inward_reference(h_in, *args)
    wrong = inward_reference(total, *args)
    np.testing.assert_allclose(inward, expected, rtol=1e-8, atol=0)
    assert wrong < 0 < inward
    final = run(spec).final.state
    energy = float(final.passive_dissipated_energy_pJ[0])
    assert energy > 0
    return {
        "model": raw["model"]["id"],
        "end_s": spec.experiment.end_time,
        "total_inside_mM": total,
        "free_inside_mM": h_in,
        "free_outside_mM": h_out,
        "initial_voltage_V": voltage,
        "initial_inward_fmol_s": inward,
        "reference_inward_fmol_s": expected,
        "using_total_inward_fmol_s": wrong,
        "booked_heat_pJ": energy,
    }


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    with jax.default_device(jax.devices("cpu")[0]):
        print(
            json.dumps(
                {
                    "components": components(),
                    "small_voltage": small_voltage_reversal(),
                    "tissue": buffered_tissue(),
                },
                indent=2,
                allow_nan=False,
            )
        )
