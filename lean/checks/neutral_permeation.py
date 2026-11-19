"""Check inward neutral flux and the relaxation of a closed tissue pair."""

import json

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.laws.electrochemistry import ghk_leak
from cells.laws.routes import passive_permeation
from tests.unit import test_passive_routes_kind as fixture
from validation.passive import passive_reference as reference
from validation.tissue.secreted_species_fixtures import SPECIES


def components():
    # The first pair has more material outside and a higher concentration inside.
    c_in = np.array([2.0, 1.0, 2.0, 1.0, 2.0])
    c_out = np.array([1.0, 2.0, 2.0, 2.0, 1.0])
    opening = np.array([1.0, 1.0, 1.0, 0.0, 0.5])
    voltage = np.array([-0.1, 0.1, 0.0, 0.05, 0.1])
    v_in, v_out = 0.5, 2.0  # pL
    area, perm = fixture.AREA, fixture.P
    expected = [
        reference.closed_pair(0.0, a * v_in, b * v_out, v_in, v_out, area * perm * m)
        for a, b, m in zip(c_in, c_out, opening, strict=True)
    ]
    # The independent reference counts positive transfer from inside to outside.
    inward = -np.array([p["flux_fmol_per_s"] for p in expected])
    rates = np.array([p["k"] for p in expected])
    flux = np.asarray(jax.jit(passive_permeation.flux_fmol_s)(c_in, c_out, area, perm, opening))
    neutral_ghk = jax.jit(ghk_leak)(c_in, c_out, voltage, 0, 300.0, area, perm, opening)
    assert flux.dtype == np.float64
    np.testing.assert_allclose(flux, inward, atol=0, rtol=1e-14)
    np.testing.assert_allclose(neutral_ghk, inward, atol=0, rtol=1e-14)
    np.testing.assert_allclose(
        -flux / v_out - flux / v_in, -rates * (c_out - c_in), atol=0, rtol=1e-14
    )
    amount_gradient = c_out[0] * v_out - c_in[0] * v_in
    assert amount_gradient > 0 and flux[0] < 0
    return {
        "cases": len(flux),
        "max_flux_error_fmol_s": float(np.max(np.abs(flux - inward))),
        "unequal_volume_inward_flux_fmol_s": float(flux[0]),
    }


def tissue():
    raw = fixture.closed_pair()
    spec = parse_spec(raw)
    species = spec.model.species_ids.index(SPECIES)
    cell = spec.model.cells[0]
    outside_index = next(i for i, node in enumerate(spec.model.extracellular) if node.id == "ecs_0")
    outside = spec.model.extracellular[outside_index]
    a, b = cell.initial_amount_fmol[species], outside.initial_amount_fmol[species]
    expected = reference.closed_pair(
        spec.experiment.end_time, a, b, cell.volume_pL, outside.volume_pL, fixture.P * fixture.AREA
    )
    state = run(spec).final.state
    measured = np.array(
        [
            a + state.amount_increment[species, 0],
            b + state.extracellular_amount_increment[species, outside_index],
        ]
    )
    analytic = np.array([expected["n_a"], expected["n_b"]])
    np.testing.assert_allclose(measured, analytic, rtol=5e-4, atol=0)
    moved = float(state.passive_transferred[species, 0])
    assert moved < 0 and expected["delta_a"] < 0
    changes = [
        state.amount_increment[species, 0],
        state.extracellular_amount_increment[species, outside_index],
    ]
    np.testing.assert_allclose(changes, [moved, -moved], rtol=1e-14, atol=0)
    return {
        "model": raw["model"]["id"],
        "end_s": spec.experiment.end_time,
        "rate_per_s": expected["k"],
        "inward_transfer_fmol": moved,
        "reference_transfer_fmol": expected["delta_a"],
        "max_final_amount_error_fmol": float(np.max(np.abs(measured - analytic))),
        "max_final_amount_relative_error": float(np.max(np.abs((measured - analytic) / analytic))),
    }


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    with jax.default_device(jax.devices("cpu")[0]):
        print(
            json.dumps({"components": components(), "tissue": tissue()}, indent=2, allow_nan=False)
        )
