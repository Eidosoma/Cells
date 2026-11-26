"""Check extracellular face direction and power on CPU and in a closed tissue run."""

import json
import math

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.numerics import surface_imex, surface_transport
from validation.tissue import surface_fixtures, surface_pump_v3_fixtures
from validation.tissue import surface_reference as reference

TOL = json.loads(surface_fixtures.PROTOCOL_PATH.read_text())["tolerances"]
FLUX_ATOL = TOL["flux_atol_fmol_s"]
LAW = "cells.route.logmean_electrodiffusion@1"


def check_direction(flux, reference_flux, reference_drop):
    resolved = np.abs(reference_flux) > FLUX_ATOL
    np.testing.assert_array_equal(np.sign(flux[resolved]), np.sign(reference_drop[resolved]))


def component_cases():
    fixture = surface_fixtures.definition("equilibrium")
    rt = reference.R * fixture["layout"]["temperature"]
    balance_v = -rt * reference.logarithmic_mean(145.0, 140.0)[1] / reference.F
    # Each pair straddling a branch uses r = (a-b)/(a+b); the thresholds are 1e-4 and 0.5.
    cases = [
        ("equal", 140.0, 140.0, 0.0),
        ("chemical", 145.0, 140.0, 0.0),
        ("opposed", 145.0, 140.0, 2 * balance_v),
        ("reversed", 140.0, 145.0, -2 * balance_v),
        ("balanced", 145.0, 140.0, balance_v),
        ("zero_factor", 145.0, 140.0, 0.0),
        ("series_below", 100.019, 100.0, 0.0),
        ("series_above", 100.021, 100.0, 0.0),
        ("atanh_below", 299.9, 100.0, 0.0),
        ("atanh_above", 300.1, 100.0, 0.0),
        ("adjacent_float64", math.nextafter(100.0, math.inf), 100.0, 0.0),
    ]
    evaluate = jax.jit(surface_transport.transport)
    rows = {}
    for name, left, right, voltage in cases:
        raw = surface_fixtures.definition("equilibrium")
        raw["co"][0] = [left, right, right]
        raw["outside_potential_V"] = [voltage, 0.0, 0.0]
        raw["membrane_open"] = [0.0] * len(raw["membrane_open"])
        raw["junction_open"] = [0.0] * len(raw["junction_open"])
        if name == "zero_factor":
            raw["layout"]["face_factor"][0][0] = 0.0
        ci, co, _, outside, membrane, junction, layout = surface_fixtures.arrays(raw)
        cell = np.zeros(ci.shape[1])
        rates = evaluate(ci, co, cell, outside, membrane, junction, layout)
        if not bool(rates.valid) or rates.face_flux_fmol_s.dtype != np.float64:
            raise AssertionError(f"Invalid CPU float64 case {name}")
        expected = reference.transport(raw, cell, outside)
        for field, atol in (
            ("face_flux_fmol_s", FLUX_ATOL),
            ("face_delta_mu_J_mol", TOL["chemical_potential_atol_J_mol"]),
            ("face_dissipation_pJ_s", TOL["power_atol_pJ_s"]),
        ):
            np.testing.assert_allclose(
                getattr(rates, field),
                expected[field],
                rtol=TOL["physical_rtol"],
                atol=atol,
                err_msg=f"{name} {field}",
            )
        flux = np.asarray(rates.face_flux_fmol_s)
        ref_flux, ref_drop = expected["face_flux_fmol_s"], expected["face_delta_mu_J_mol"]
        check_direction(flux, ref_flux, ref_drop)
        if np.min(rates.face_dissipation_pJ_s) < -1e-15:  # Existing surface power sign check.
            raise AssertionError(f"Negative face power in {name}")
        rows[name] = {
            "flux_fmol_s": float(flux[0, 0]),
            "reference_fmol_s": float(ref_flux[0, 0]),
            "drop_J_mol": float(rates.face_delta_mu_J_mol[0, 0]),
            "face_power_pJ_s": float(rates.face_dissipation_pJ_s[0]),
        }
        if name == "chemical":
            # Only this species and face move. Reverse its flux and both owner bookings.
            wrong_rates = -np.asarray(rates.outside_rate_fmol_s)[0]
            np.testing.assert_allclose(wrong_rates[:2], [flux[0, 0], -flux[0, 0]], rtol=0, atol=0)
            wrong_total = float(wrong_rates.sum())
            if wrong_total != 0 or ref_flux[0, 0] <= FLUX_ATOL:
                raise AssertionError("The reversed flux must conserve a resolved transfer")
            with np.testing.assert_raises(AssertionError):
                check_direction(-flux, ref_flux, ref_drop)
            wrong_power = float(-flux[0, 0] * ref_drop[0, 0] * 1e-3)
            if wrong_power >= -TOL["power_atol_pJ_s"]:
                raise AssertionError("The reversed flux must give resolved negative power")
            control = {"total_rate_fmol_s": wrong_total, "power_pJ_s": wrong_power}
    if rows["equal"]["flux_fmol_s"] != 0 or rows["zero_factor"]["flux_fmol_s"] != 0:
        raise AssertionError("Equal endpoints and the zero coefficient must give zero flux")
    np.testing.assert_allclose(rows["balanced"]["flux_fmol_s"], 0, rtol=0, atol=FLUX_ATOL)
    forward, reverse = rows["opposed"]["flux_fmol_s"], rows["reversed"]["flux_fmol_s"]
    if forward >= -FLUX_ATOL or reverse <= FLUX_ATOL:
        raise AssertionError("Opposing voltage must reverse the concentration-driven flux")
    np.testing.assert_allclose(forward, -reverse, rtol=TOL["physical_rtol"], atol=FLUX_ATOL)
    return {"cases": rows, "reversed_flux_control": control}


def closed_tissue():
    raw = surface_pump_v3_fixtures.definition(
        "closed", solver=surface_imex.ARS222_ID, backend="cpu"
    )
    faces = raw["model"]["faces"]
    if not faces or any(face["law"] != LAW for face in faces):
        raise AssertionError(f"Expected active {LAW} faces")
    result = run(parse_spec(raw))
    model, obs = result.spec.model, result.observations
    nodes = {node.id: i for i, node in enumerate(model.extracellular)}
    volumes = np.asarray([node.volume_pL for node in model.extracellular])
    co = obs.extracellular_amount[:, :, : len(volumes)] / volumes
    actual = np.asarray(obs.face_flux_fmol_s[:, :, : len(faces)])
    expected = np.empty_like(actual)
    rt = reference.R * model.temperature_K
    for f, face in enumerate(model.faces):
        i, j = nodes[face.sender], nodes[face.receiver]
        voltages = obs.extracellular_potential_V[:, i] - obs.extracellular_potential_V[:, j]
        for s, z in enumerate(model.valence):
            factor = face.area_m2 * face.diffusivity_m2_per_s[s] / face.length_m
            for t, voltage in enumerate(voltages):
                mean, log_ratio = reference.logarithmic_mean(co[t, s, i], co[t, s, j])
                drop = rt * log_ratio + z * reference.F * voltage
                expected[t, s, f] = factor * mean * drop / rt * 1e15
    np.testing.assert_allclose(actual, expected, rtol=TOL["physical_rtol"], atol=FLUX_ATOL)
    moved = float(np.max(np.abs(result.history.face_transferred[:, :, : len(faces)])))
    if not np.isfinite(moved) or moved <= 0 or not np.any(np.abs(expected) > FLUX_ATOL):
        raise AssertionError("The tissue must exercise resolved face flux and nonzero transfer")
    return {
        "model": raw["model"]["id"],
        "law": LAW,
        "solver": raw["execution"]["solver"],
        "samples_species_faces": list(actual.shape),
        "max_flux_error_fmol_s": float(np.max(np.abs(actual - expected))),
        "max_abs_transferred_fmol": moved,
    }


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    with jax.default_device(jax.devices("cpu")[0]):
        print(
            json.dumps(
                {
                    "backend": "cpu",
                    "dtype": "float64",
                    "flux_atol_fmol_s": FLUX_ATOL,
                    "physical_rtol": TOL["physical_rtol"],
                    **component_cases(),
                    "tissue": closed_tissue(),
                },
                indent=2,
                allow_nan=False,
            )
        )
