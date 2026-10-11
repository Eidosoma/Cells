"""Read-only native-history comparison and independent scalar owner accounting.

No Cells/JAX imports. Native values are targets only, never trajectory inputs.
"""

import numpy as np

from validation.betse.tissue_contact.reference import boundary_reset


def ledgers(row, trace):
    g, p = row["geometry"], row["parameters"]
    voxel_fmol = p["cell_height"] * g["delta"] ** 2 * 1e15
    moving = row["fixture"]["moving_ions"]
    shape = np.asarray(g["X"]).shape
    mem = np.zeros_like(trace["initial_cc_at_mem"])
    gap = mem.copy()
    reset = np.zeros_like(trace["initial_cc_env"])
    stencil = reset.copy()
    histories = {
        name: []
        for name in (
            "membrane_inward_fmol",
            "junction_outward_fmol",
            "reservoir_reset_fmol",
            "stencil_exchange_fmol",
        )
    }
    for step in range(row["steps"]):
        for ion in moving:
            (k,) = np.flatnonzero(
                (trace["step"] == step)
                & (trace["method"] == 1)
                & (trace["ion"] == ion)
                & ~trace["after"]
            )
            before = trace["cc_env"][k, ion].reshape(shape)
            prescribed = boundary_reset(before, row["arrays"]["c_env_bound"][ion])
            reset[ion] += (prescribed - before).ravel() * voxel_fmol
            stencil[ion] += (trace["cc_env"][k + 1, ion] - prescribed.ravel()) * voxel_fmol
        (k,) = np.flatnonzero((trace["step"] == step) & (trace["method"] == 3) & trace["after"])
        mem += trace["fluxes_mem"][k] * g["mem_sa"] * row["dt_s"] * 1e15
        gap += trace["fluxes_gj"][k] * g["mem_sa"] * row["dt_s"] * 1e15
        for name, value in zip(histories, (mem, gap, reset, stencil), strict=True):
            histories[name].append(value.copy())
    return {name: np.stack(values) for name, values in histories.items()}


def material_roundoff(row, trace, states, operations):
    """Inventory-scaled accumulation allowance; separate from physical tolerances.

    gamma_(operations * completed_steps) uses epsilon, conservatively twice the
    round-to-nearest unit roundoff. Local inventories and recorded transfer
    magnitudes set the scale; global allowances sum the local allowances.
    This accounts for finite-precision bookkeeping, not integration error.
    """
    if operations == 0:
        return {}
    assert isinstance(operations, int) and operations > 0
    count = np.asarray(states["step_count"]) * operations * np.finfo(np.float64).eps
    assert np.all((count >= 0) & (count < 0.01))
    gamma = (count / (1 - count))[:, None, None]
    g, p = row["geometry"], row["parameters"]
    cell = (
        (abs(states["cell_concentration"]) + abs(trace["initial_cc_cells"]))
        * np.asarray(g["cell_vol"])
        * 1e15
    )
    outside = (
        (abs(states["outside_concentration"]) + abs(trace["initial_cc_env"]))
        * p["cell_height"]
        * g["delta"] ** 2
        * 1e15
    )
    for m, (i, o) in enumerate(zip(g["mem_to_cells"], g["map_mem2ecm"], strict=True)):
        cell[:, :, i] += abs(states["membrane_inward_fmol"][:, :, m]) + abs(
            states["junction_outward_fmol"][:, :, m]
        )
        outside[:, :, o] += abs(states["membrane_inward_fmol"][:, :, m])
    outside += abs(states["reservoir_reset_fmol"]) + abs(states["stencil_exchange_fmol"])
    cell, outside = (gamma * np.maximum.accumulate(v, axis=0) for v in (cell, outside))
    return {
        "membrane_inward_fmol": gamma
        * np.maximum.accumulate(abs(states["membrane_inward_fmol"]), axis=0),
        "junction_outward_fmol": gamma
        * np.maximum.accumulate(abs(states["junction_outward_fmol"]), axis=0),
        "reservoir_reset_fmol": outside,
        "stencil_exchange_fmol": outside,
        "local_cell_material_fmol": cell,
        "local_outside_material_fmol": outside,
        "global_material_fmol": cell.sum(axis=-1) + outside.sum(axis=-1),
    }


def compare(row, trace, tol, states, observed):
    indices = np.flatnonzero((trace["method"] == 3) & trace["after"])
    errors, largest_ratio, scalars = {}, 0.0, 0
    rounding = material_roundoff(row, trace, states, tol.get("material_roundoff_ops_per_step", 0))

    def close(name, actual, expected, atol, rtol):
        nonlocal largest_ratio, scalars
        actual, expected = np.asarray(actual), np.asarray(expected)
        assert actual.shape == expected.shape, name
        assert np.isfinite(actual).all() and np.isfinite(expected).all(), name
        budget = atol + rtol * abs(expected) + rounding.get(name, 0)
        np.testing.assert_allclose((actual - expected) / budget, 0, atol=1, rtol=0, err_msg=name)
        errors[name] = float(np.max(abs(actual - expected), initial=0))
        largest_ratio = max(
            largest_ratio,
            float(
                np.max(
                    abs(actual - expected) / budget,
                    initial=0,
                )
            ),
        )
        scalars += actual.size

    required = {
        "cc_cells",
        "cc_at_mem",
        "cc_env",
        "vm",
        "vm_ave",
        "rho_cells",
        "Phi_b",
        "v_env",
        "E_env_x",
        "E_env_y",
        "fluxes_mem",
        "fluxes_gj",
        "fluxes_env_x",
        "fluxes_env_y",
    }
    assert set(observed) == required
    for name, actual in observed.items():
        expected = trace[name][indices]
        if name.startswith("cc_"):
            atol, rtol = tol["concentration_atol_mM"], tol["concentration_rtol"]
        elif name in ("fluxes_mem", "fluxes_gj"):
            actual = actual * row["geometry"]["mem_sa"] * 1e15
            expected = expected * row["geometry"]["mem_sa"] * 1e15
            atol, rtol = tol["flux_atol_fmol_s"], tol["flux_rtol"]
        elif name.startswith("fluxes_env"):
            atol, rtol = tol["environment_flux_atol_mol_m2_s"], tol["flux_rtol"]
        elif name.startswith("E_env"):
            atol, rtol = tol["field_atol_V_m"], tol["field_rtol"]
        elif name == "rho_cells":
            atol, rtol = tol["charge_density_atol_C_m3"], tol["field_rtol"]
        else:
            atol, rtol = tol["voltage_atol_V"], tol["voltage_rtol"]
        close(name, actual, expected, atol, rtol)
    for name, expected in ledgers(row, trace).items():
        close(name, states[name], expected, tol["material_atol_fmol"], 0)
    np.testing.assert_array_equal(states["step_count"], np.arange(1, row["steps"] + 1))
    np.testing.assert_allclose(
        states["elapsed_s"],
        np.arange(1, row["steps"] + 1) * row["dt_s"],
        rtol=0,
        atol=tol.get("clock_atol_s", 3e-20),
    )

    # Explicit patch-owner loops, separate from the implementation's matrix sums.
    g, p = row["geometry"], row["parameters"]
    cell = (
        (states["cell_concentration"] - trace["initial_cc_cells"])
        * np.asarray(g["cell_vol"])
        * 1e15
    )
    outside = (
        (states["outside_concentration"] - trace["initial_cc_env"])
        * p["cell_height"]
        * g["delta"] ** 2
        * 1e15
    )
    cell_transfer, outside_transfer = np.zeros_like(cell), np.zeros_like(outside)
    for m, (i, o) in enumerate(zip(g["mem_to_cells"], g["map_mem2ecm"], strict=True)):
        cell_transfer[:, :, i] += (
            states["membrane_inward_fmol"][:, :, m] - states["junction_outward_fmol"][:, :, m]
        )
        outside_transfer[:, :, o] -= states["membrane_inward_fmol"][:, :, m]
    supply, stencil = states["reservoir_reset_fmol"], states["stencil_exchange_fmol"]
    close("local_cell_material_fmol", cell, cell_transfer, tol["material_atol_fmol"], 0)
    close(
        "local_outside_material_fmol",
        outside,
        outside_transfer + supply + stencil,
        tol["material_atol_fmol"],
        0,
    )
    close(
        "global_material_fmol",
        cell.sum(axis=-1) + outside.sum(axis=-1),
        supply.sum(axis=-1) + stencil.sum(axis=-1),
        tol["material_atol_fmol"],
        0,
    )
    return dict(
        status="passed",
        compared_scalars=scalars,
        max_error_over_budget=largest_ratio,
        max_errors=errors,
        max_material_roundoff_allowance_fmol={k: float(np.max(v)) for k, v in rounding.items()},
        duration_s=row["steps"] * row["dt_s"],
        steps=row["steps"],
        native_evolving_values_used_as_inputs=False,
    )
