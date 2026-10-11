"""Native directed faces versus Decimal GHK and Cells' once-owned transport."""

import json
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np


def decimal_flux(ca, cb, dv, z, temperature, area, diffusion, length, opening, constants):
    """Independent high-precision constant-field formula, positive A -> B, fmol/s."""
    with localcontext() as context:
        context.prec = 70
        ca, cb, dv, z, temperature, area, diffusion, length, opening = (
            Decimal(str(x)) for x in (ca, cb, dv, z, temperature, area, diffusion, length, opening)
        )
        x = z * Decimal(str(constants["F"])) * dv / (Decimal(str(constants["R"])) * temperature)
        if x == 0:
            driving = ca - cb
        else:
            exponential = x.exp()
            driving = x * (ca * exponential - cb) / (exponential - 1)
        return float(area * diffusion / length * opening * driving * Decimal("1e15"))


def check(directory):
    from cells.coupling.selective import selective_flux

    directory = Path(directory)
    prepared = json.loads((directory / "preparation.json").read_text())
    panel = json.loads((directory / "panel.json").read_text())
    protocol, geometry = panel["protocol"], prepared["geometry"]
    tol = protocol["tolerances"]
    owners, partners = (np.asarray(geometry[k], dtype=int) for k in ("mem_to_cells", "nn_i"))
    area, volume = (np.asarray(geometry[k]) for k in ("mem_sa", "cell_vol"))
    faces = np.arange(len(owners))
    np.testing.assert_array_equal(partners[partners], faces)
    pairs = np.asarray(geometry["canonical_face_pairs"], dtype=int)
    a, b = pairs.T
    np.testing.assert_array_equal(np.sort(pairs.ravel()), faces[partners != faces])
    boundary = np.asarray(geometry["bflags_mems"], dtype=int)
    np.testing.assert_array_equal(np.sort(boundary), faces[partners == faces])
    np.testing.assert_array_equal(
        np.asarray(geometry["cell_nn_i"]), np.column_stack((owners, owners[partners]))
    )
    np.testing.assert_allclose(area[a], area[b], rtol=tol["partner_area_rtol"], atol=0)
    incidence = np.asarray(geometry["M_sum_mems"])
    np.testing.assert_array_equal(incidence, np.arange(len(volume))[:, None] == owners[None, :])
    np.testing.assert_allclose(
        incidence @ area, geometry["cell_sa"], rtol=tol["partner_area_rtol"], atol=0
    )
    report = []
    for row in panel["rows"]:
        before, voltage = (
            np.asarray(row[k]) for k in ("concentration_before_mM", "voltage_clamp_V")
        )
        density = np.asarray(row["native_density_mol_m2_s"])
        after = np.asarray(row["concentration_after_mM"])
        ion = prepared["species"][row["species"]]
        diffusion = np.asarray(prepared["native_D_gj_m2_s"][ion])
        gate = np.asarray(row["gjopen"])
        expected_gate = np.zeros(len(faces))
        selected = (
            pairs if row["topology"] == "all" else pairs[:1] if row["topology"] == "single" else []
        )
        for left, right in selected:
            expected_gate[[left, right]] = row["block"]
        expected_gate *= np.asarray(geometry["gj_default_weights"])
        np.testing.assert_array_equal(gate, expected_gate)
        native = density[a] * area[a] * 1e15
        decimal = np.asarray(
            [
                decimal_flux(
                    before[owners[left]],
                    before[owners[right]],
                    voltage[owners[left]] - voltage[owners[right]],
                    row["valence"],
                    prepared["temperature_K"],
                    area[left],
                    diffusion[left],
                    geometry["gj_len"],
                    gate[left] * protocol["gj_surface_fraction"],
                    prepared["constants"],
                )
                for left, right in pairs
            ]
        )
        cells_flux = np.asarray(
            selective_flux(
                before[owners[a]],
                before[owners[b]],
                voltage[owners[a]] - voltage[owners[b]],
                row["valence"],
                prepared["temperature_K"],
                area[a],
                diffusion[a] * protocol["gj_surface_fraction"] / geometry["gj_len"],
                0.0,
                gate[a],
                1.0,
                xp=np,
            )
        )
        for actual in (native, cells_flux):
            np.testing.assert_allclose(
                actual, decimal, rtol=tol["flux_rtol"], atol=tol["flux_atol_fmol_s"]
            )
        np.testing.assert_allclose(
            density[a] * area[a] * 1e15,
            -density[b] * area[b] * 1e15,
            rtol=tol["flux_rtol"],
            atol=tol["flux_atol_fmol_s"],
        )
        np.testing.assert_array_equal(density[boundary], 0.0)
        # One transfer per physical edge: subtract once at owner A, add once at B.
        net = np.zeros(len(volume))
        np.add.at(net, owners[a], -cells_flux)
        np.add.at(net, owners[b], cells_flux)
        predicted = before + protocol["dt_s"] * net * 1e-15 / volume
        np.testing.assert_allclose(after, predicted, rtol=0, atol=tol["concentration_atol_mM"])
        native_net = incidence @ (-density * area) * 1e15
        np.testing.assert_allclose(
            native_net, net, rtol=tol["flux_rtol"], atol=tol["flux_atol_fmol_s"]
        )
        amount_residual = float(np.sum((after - before) * volume) * 1e15)
        if abs(amount_residual) > tol["material_atol_fmol"] or np.min(after) <= 0:
            raise ValueError("Native one-update material/domain check failed")
        # In this entrypoint, membrane concentration is refreshed before the GJ
        # update. The driver must call update_intra before the next junction flux.
        np.testing.assert_array_equal(row["at_membrane_after_update_mM"], before[owners])
        np.testing.assert_allclose(
            row["environment_after_mM"], row["environment_before_mM"], rtol=0, atol=0
        )
        if (
            row["fixture"] in ("equal", "equilibrium")
            or row["block"] == 0
            or row["topology"] == "disconnected"
        ):
            np.testing.assert_allclose(native, 0, rtol=0, atol=tol["flux_atol_fmol_s"])
        report.append(
            {k: row[k] for k in ("species", "fixture", "topology", "block")}
            | {
                "max_native_decimal_flux_error_fmol_s": float(np.max(np.abs(native - decimal))),
                "max_cells_decimal_flux_error_fmol_s": float(np.max(np.abs(cells_flux - decimal))),
                "max_concentration_error_mM": float(np.max(np.abs(after - predicted))),
                "material_residual_fmol": amount_residual,
                "minimum_concentration_mM": float(np.min(after)),
            }
        )
    return {
        "status": "held_open_junction_mapping_and_single_update_pass",
        "rows": report,
        "cells": len(volume),
        "directed_faces": len(faces),
        "physical_junctions": len(pairs),
        "partner_area_max_relative_difference": float(np.max(np.abs(area[a] - area[b]) / area[a])),
        "canonical_area_policy": (
            "Use lower-index native face area; both native areas retained and checked"
        ),
        "full_betse_parity": False,
        "dynamic_gate_qualified": False,
        "free_voltage_trajectory_qualified": False,
        "scope": (
            "Pinned native seed; held-open voltage clamp; "
            "isolated update_gj/update_all_concs entrypoints"
        ),
    }
