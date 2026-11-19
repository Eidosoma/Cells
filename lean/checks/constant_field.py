"""Compare the Lean junction claims with the CPU float64 component and one closed tissue world."""

import json

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.numerics import surface_imex, surface_transport
from tests.unit.test_surface_pump_v3_imex import (
    test_imex_ledgers_constraints_and_channel_transfer as check_tissue_ledgers,
)
from validation.tissue import surface_fixtures, surface_pump_v3_fixtures, surface_reference


def equal_voltage():
    """Isolate junction contributions to the cell rates and measure both gradient directions."""
    raw = surface_fixtures.definition("gradient")
    raw["membrane_open"] = [0.0] * len(raw["membrane_open"])
    ci, co, _, outside, membrane, opening, layout = surface_fixtures.arrays(raw)
    cell_voltage = np.zeros(ci.shape[1])
    outside_voltage = np.zeros_like(outside)
    rates = jax.jit(surface_transport.transport)(
        ci, co, cell_voltage, outside_voltage, membrane, opening, layout
    )
    if not bool(rates.valid):
        raise AssertionError("Equal-voltage state failed the surface domain check")

    tolerance = json.loads(surface_fixtures.PROTOCOL_PATH.read_text())["tolerances"]
    reference = surface_reference.transport(raw, cell_voltage, outside_voltage)
    flux = np.asarray(rates.junction_flux_fmol_s)
    gradient = ci[:, layout.junction_sender] - ci[:, layout.junction_receiver]
    if not (np.any(gradient > 0) and np.any(gradient < 0)):
        raise AssertionError("The fixture must exercise both directions")
    np.testing.assert_array_equal(np.sign(flux), np.sign(gradient))
    np.testing.assert_allclose(
        flux,
        reference["junction_flux_fmol_s"],
        rtol=tolerance["physical_rtol"],
        atol=tolerance["flux_atol_fmol_s"],
    )

    owner_rates = np.asarray(rates.cell_rate_fmol_s)
    expected = reference["cell_rate_fmol_s"]
    material_atol = tolerance["material_rate_atol_fmol_s"]
    np.testing.assert_allclose(owner_rates, expected, rtol=0, atol=material_atol)
    np.testing.assert_allclose(owner_rates.sum(axis=1), 0, rtol=0, atol=material_atol)
    # Swapping the two owners of every junction keeps the global sum zero.
    # The same per-cell comparison must detect that error.
    with np.testing.assert_raises(AssertionError):
        np.testing.assert_allclose(owner_rates, -expected, rtol=0, atol=material_atol)
    return {
        "junction_flux_fmol_s": flux.tolist(),
        "max_flux_error_fmol_s": float(np.max(np.abs(flux - reference["junction_flux_fmol_s"]))),
        "max_owner_error_fmol_s": float(np.max(np.abs(owner_rates - expected))),
        "max_swapped_owner_error_fmol_s": float(np.max(np.abs(owner_rates + expected))),
        "owner_tolerance_fmol_s": material_atol,
    }


def closed_tissue():
    """Run one existing world and apply its existing integrated per-cell potassium ledger check."""
    solver = surface_imex.ARS222_ID
    raw = surface_pump_v3_fixtures.definition("closed", solver=solver, backend="cpu")
    value = run(parse_spec(raw))
    # The upstream pytest fixture also builds the release, clamped, Euler and RK4 worlds.
    check_tissue_ledgers("closed", solver, {("closed", solver): value})
    ion = value.spec.model.species_ids.index("K")
    moved = float(np.max(np.abs(value.history.junction_transferred[:, ion])))
    if not np.isfinite(moved) or moved <= 0:
        raise AssertionError("The tissue ledger must exercise a nonzero K⁺ junction transfer")
    return {
        "model": raw["model"]["id"],
        "solver": solver,
        "max_abs_junction_K_fmol": moved,
        "max_global_material_error_fmol": float(value.diagnostics["max_global_balance_error_fmol"]),
    }


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    with jax.default_device(jax.devices("cpu")[0]):
        results = {"equal_voltage": equal_voltage(), "tissue": closed_tissue()}
        print(json.dumps(results, indent=2, allow_nan=False))
