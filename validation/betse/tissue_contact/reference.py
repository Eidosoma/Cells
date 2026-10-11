"""Independent saved-native update accounting; no BETSE or Cells model imports."""

import numpy as np
from scipy.signal import convolve2d

from validation.betse.junction_transport.check import decimal_flux


def gradient(value, spacing):
    dy, dx = np.gradient(value, spacing, edge_order=1)
    return dx, dy


def native_divergence(fx, fy, spacing):
    """Pinned compatibility convention: native edge derivatives reverse sign."""
    dx = np.gradient(fx, spacing, axis=1, edge_order=1)
    dy = np.gradient(fy, spacing, axis=0, edge_order=1)
    dx[:, [0, -1]] *= -1
    dy[[0, -1]] *= -1
    return dx + dy


def boundary_reset(value, concentration):
    result = value.copy()
    result[[0, -1], :] = concentration
    result[:, [0, -1]] = concentration
    return result


def native_field(state, row):
    p, g, a = row["parameters"], row["geometry"], row["arrays"]
    shape = np.asarray(g["X"]).shape
    outside = np.asarray(g["map_mem2ecm"], dtype=int)
    owners = np.asarray(g["mem_to_cells"], dtype=int)
    z, delta = np.asarray(a["zs"]), g["delta"]
    bounds = row["fixture"]["boundary_voltage_V"]
    rhs = np.zeros(shape)
    rhs[:, 0], rhs[:, -1] = bounds["L"] / delta**2, bounds["R"] / delta**2
    rhs[-1, :], rhs[0, :] = bounds["T"] / delta**2, bounds["B"] / delta**2
    phi = np.asarray(g["lapENVinv"]) @ rhs.ravel()
    charge = (z * p["F"]) @ state["cc_cells"] + a["extra_rho_cells"]
    vm = (charge * g["diviterm"] / p["cm"])[owners] - phi[outside]
    rho = (z * p["F"]) @ state["cc_env"] + a["extra_rho_env"]
    surface = np.zeros_like(rho)
    surface[outside] = (
        rho[outside]
        * (p["cell_height"] * delta**2)
        / np.mean(np.asarray(g["memSa_per_envSquare"])[outside])
    )
    # Independent 2-D convolution of the declared sigma=1, radius=4 kernel.
    kernel = np.exp(-0.5 * np.arange(-4, 5, dtype=float) ** 2)
    kernel /= np.sum(kernel)
    screened = surface.reshape(shape) / (a["ko_env"] * p["eo"] * p["er"])
    potential = (
        convolve2d(screened, np.outer(kernel, kernel), mode="same", boundary="fill").ravel() + phi
    )
    scale = 2 / (a["ko_env"] * delta) * (p["cell_radius"] / p["true_cell_size"])
    ex, ey = gradient(scale * potential.reshape(shape), delta)
    return {"vm": vm, "Phi_b": phi, "v_env": potential, "E_env_x": -ex, "E_env_y": -ey}


def geometry_check(row):
    g = row["geometry"]
    owners = np.asarray(g["mem_to_cells"], dtype=int)
    outside = np.asarray(g["map_mem2ecm"], dtype=int)
    partners = np.asarray(g["nn_i"], dtype=int)
    area = np.asarray(g["mem_sa"])
    n, m, shape = len(g["cell_i"]), len(owners), np.asarray(g["X"]).shape
    assert (n, m, shape) == (7, 30, (10, 10))
    assert np.all((owners >= 0) & (owners < n))
    assert np.all((outside >= 0) & (outside < np.prod(shape)))
    np.testing.assert_array_equal(partners[partners], np.arange(m))
    np.testing.assert_allclose(area, area[partners], rtol=5e-14, atol=0)
    incidence = np.arange(n)[:, None] == owners
    np.testing.assert_array_equal(g["M_sum_mems"], incidence)
    mapping = np.zeros((np.prod(shape), m))
    mapping[outside, np.arange(m)] = area
    np.testing.assert_array_equal(g["M_divmap_mem2ecm"], mapping)
    np.testing.assert_allclose(incidence @ area, g["cell_sa"], rtol=5e-14, atol=0)
    return [len(np.unique(outside[owners == i])) for i in range(n)]


def check(row, trace, protocol, *, active_pump=False, additional_updates=None):
    additional_updates = {} if additional_updates is None else additional_updates
    p, g, a, tol = (row["parameters"], row["geometry"], row["arrays"], protocol["tolerances"])
    assert p["is_ecm"] and p["sharpness"] == 1.0
    assert not any(
        p[k]
        for k in (
            "fast_update_ecm",
            "cell_polarizability",
            "fluid_flow",
            "Ca_dyn",
            "grn_enabled",
            "alpha_Ca",
        )
    )
    assert p["molecules_enabled"] == bool(additional_updates)
    assert active_pump or p["alpha_NaK"] == 0
    owner_counts = geometry_check(row)
    area, volume = np.asarray(g["mem_sa"]), np.asarray(g["cell_vol"])
    owners, outside = (np.asarray(g[k], dtype=int) for k in ("mem_to_cells", "map_mem2ecm"))
    ids = [row["species"][s] for s in protocol["species"]]
    shape, delta = np.asarray(g["X"]).shape, g["delta"]
    voxel = p["cell_height"] * delta**2
    matrix = np.asarray(g["M_divmap_mem2ecm"])
    incidence = np.asarray(g["M_sum_mems"])
    expected = [(method, after, ion) for ion in ids for method in (0, 1) for after in (False, True)]
    expected += [(method, after, -1) for method in additional_updates for after in (False, True)]
    expected += [(method, after, -1) for method in (2, 3) for after in (False, True)]
    assert len(trace["method"]) == row["steps"] * len(expected)
    assert row["steps"] == round(protocol["duration_s"] / row["dt_s"])
    for step in range(row["steps"]):
        mask = trace["step"] == step
        assert (
            list(zip(trace["method"][mask], trace["after"][mask], trace["ion"][mask], strict=True))
            == expected
        )
        np.testing.assert_array_equal(
            trace["raw_label_s"][mask], np.linspace(0, protocol["duration_s"], row["steps"])[step]
        )
    fields = [
        k
        for k in trace
        if k not in ("method", "after", "ion", "step", "raw_label_s")
        and not k.startswith("initial_")
    ]
    assert all(np.isfinite(trace[k]).all() for k in fields)
    assert all(np.min(trace[k]) > 0 for k in ("cc_cells", "cc_at_mem", "cc_env"))
    immobile = [i for i in range(len(a["zs"])) if i not in ids]
    for k in ("cc_cells", "cc_env"):
        np.testing.assert_array_equal(
            trace[k][:, immobile],
            np.broadcast_to(trace["initial_" + k][immobile], trace[k][:, immobile].shape),
        )
    errors, reset_amounts, stencil_amounts, exchange_residuals = {}, [], [], []
    max_outside_difference = max_surface_voltage_spread = max_charge_potential = 0.0

    def near(name, actual, target, atol, rtol=0):
        errors[name] = max(errors.get(name, 0.0), float(np.max(np.abs(actual - target), initial=0)))
        np.testing.assert_allclose(actual, target, rtol=rtol, atol=atol, err_msg=name)

    for k in range(0, len(trace["method"]), 2):
        method, ion = int(trace["method"][k]), int(trace["ion"][k])
        before, after = ({name: trace[name][j] for name in fields} for j in (k, k + 1))
        if method in additional_updates:
            additional_updates[method](row, before, after, near)
        if method == 1:
            c0 = before["cc_env"][ion].reshape(shape)
            c = boundary_reset(c0, a["c_env_bound"][ion])
            dx, dy = gradient(c, delta)
            diffusion = (np.asarray(a["D_env"])[ion] * np.asarray(a["TJ_modulator"])[ion]).reshape(
                shape
            )
            mobility = diffusion * a["zs"][ion] * p["q"] / (p["kb"] * p["T"])
            fx = -diffusion * dx + mobility * before["E_env_x"] * c
            fy = -diffusion * dy + mobility * before["E_env_y"] * c
            for axis, flux in (("x", fx), ("y", fy)):
                near(
                    "environment_flux_" + axis + "_mol_m2_s",
                    after["fluxes_env_" + axis][ion],
                    flux.ravel(),
                    tol["environment_flux_atol_mol_m2_s"],
                    tol["flux_rtol"],
                )
            dc = row["dt_s"] * native_divergence(-fx, -fy, delta)
            near(
                "environment_update_mM",
                after["cc_env"][ion],
                (c + dc).ravel(),
                tol["concentration_atol_mM"],
                tol["concentration_rtol"],
            )
            reset, stencil = float(np.sum(c - c0) * voxel * 1e15), float(np.sum(dc) * voxel * 1e15)
            residual = np.sum(after["cc_env"][ion] - c0.ravel()) * voxel * 1e15 - reset - stencil
            near(
                "reservoir_stencil_balance_fmol", np.asarray(residual), 0, tol["material_atol_fmol"]
            )
            reset_amounts.append(reset)
            stencil_amounts.append(stencil)
        elif method == 2:
            mem, gap = before["fluxes_mem"][ids], before["fluxes_gj"][ids]
            mem_dc = (mem * area) @ incidence.T / volume * row["dt_s"]
            gap_dc = (-gap * area) @ incidence.T / volume * row["dt_s"]
            expected_cells = before["cc_cells"][ids] + mem_dc + gap_dc
            env_dc = (-mem @ matrix.T) / voxel * row["dt_s"]
            near(
                "cell_update_mM",
                after["cc_cells"][ids],
                expected_cells,
                tol["concentration_atol_mM"],
            )
            near(
                "environment_membrane_update_mM",
                after["cc_env"][ids],
                before["cc_env"][ids] + env_dc,
                tol["concentration_atol_mM"],
            )
            near(
                "membrane_concentration_lag_mM",
                after["cc_at_mem"][ids],
                (before["cc_cells"][ids] + mem_dc)[:, owners],
                tol["concentration_atol_mM"],
            )
            residual = (
                np.sum((after["cc_cells"][ids] - before["cc_cells"][ids]) * volume, axis=1)
                + np.sum(after["cc_env"][ids] - before["cc_env"][ids], axis=1) * voxel
            ) * 1e15
            near("membrane_junction_material_fmol", residual, 0, tol["material_atol_fmol"])
            exchange_residuals.extend(residual.tolist())
        elif method == 3:
            for name, target in native_field(before, row).items():
                near(
                    name,
                    after[name],
                    target,
                    tol["field_gradient_atol_V_m"]
                    if name.startswith("E_env")
                    else tol["field_atol_V"],
                    tol["field_rtol"],
                )
            phi = after["v_env"][outside]
            max_outside_difference = max(
                max_outside_difference, float(np.max(np.abs(phi - phi[np.asarray(g["nn_i"])])))
            )
            max_charge_potential = max(
                max_charge_potential, float(np.max(np.abs(after["v_env"] - after["Phi_b"])))
            )
            max_surface_voltage_spread = max(
                max_surface_voltage_spread,
                *(float(np.ptp(after["vm"][owners == i])) for i in range(len(volume))),
            )
    return {
        "status": "passed",
        "steps": row["steps"],
        "max_errors": errors,
        "extracellular_owners_per_cell": owner_counts,
        "reservoir_reset_fmol": reset_amounts,
        "native_stencil_exchange_fmol": stencil_amounts,
        "membrane_junction_material_residual_fmol": exchange_residuals,
        "max_native_outside_difference_across_junction_V": max_outside_difference,
        "max_charge_based_outside_potential_V": max_charge_potential,
        "max_within_cell_membrane_voltage_spread_V": max_surface_voltage_spread,
        "native_drift_constant_relative_difference_from_F_R": (p["q"] / p["kb"]) / (p["F"] / p["R"])
        - 1,
        "whole_tissue_trajectory_equivalence": False,
    }


def shared_inputs(row, trace, protocol):
    g, p, a = row["geometry"], row["parameters"], row["arrays"]
    area = np.asarray(g["mem_sa"])
    outside, partners = (np.asarray(g[k], dtype=int) for k in ("map_mem2ecm", "nn_i"))
    boundary = np.asarray(g["bflags_mems"], dtype=int)
    values = {name: [] for name in ("membrane", "junction")}
    for k in np.flatnonzero((trace["method"] == 0) & ~trace["after"]):
        i = int(trace["ion"][k])
        ci, vm = trace["cc_at_mem"][k, i], trace["vm"][k]
        for name in values:
            if name == "membrane":
                co = trace["cc_env"][k, i, outside]
                voltage, permeability = vm, np.asarray(a["Dm_cells"])[i] / p["tm"]
                multiplier = np.ones_like(area)
                if not p["cluster_open"]:
                    multiplier[boundary] = 0
                observed = trace["fluxes_mem"][k, i] * area * 1e15
                left, right, dv = co, ci, -voltage
            else:
                co, voltage = ci[partners], vm - vm[partners]
                permeability = (
                    np.asarray(a["D_gj"])[i]
                    * protocol["gj_surface_fraction"]
                    / np.asarray(g["gj_len"])
                )
                multiplier = trace["gjopen"][k + 1].copy()
                multiplier[boundary] = 0
                observed = (trace["fluxes_gj"][k + 1, i] - trace["fluxes_gj"][k, i]) * area * 1e15
                left, right, dv = ci, co, voltage
            constants = {key: p[key] for key in ("F", "R")}
            reference = np.asarray(
                [
                    decimal_flux(x, y, v, a["zs"][i], p["T"], ar, per, 1.0, mult, constants)
                    for x, y, v, ar, per, mult in zip(
                        left, right, dv, area, permeability, multiplier, strict=True
                    )
                ]
            )
            np.testing.assert_allclose(
                observed,
                reference,
                rtol=protocol["tolerances"]["flux_rtol"],
                atol=protocol["tolerances"]["flux_atol_fmol_s"],
            )
            args = (
                ci,
                co,
                voltage,
                np.full_like(area, a["zs"][i]),
                np.full_like(area, p["T"]),
                area,
                permeability,
                multiplier,
            )
            values[name].append((*args, observed, reference))
    return {
        name: tuple(np.stack(items) for items in zip(*rows, strict=True))
        for name, rows in values.items()
    }
