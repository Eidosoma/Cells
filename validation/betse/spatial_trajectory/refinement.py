"""Common-completed-time refinement diagnostics; no simulator imports."""

import numpy as np

from validation.betse.spatial_trajectory.reference import ledgers


def native_series(row, trace):
    indices = np.flatnonzero((trace["method"] == 3) & trace["after"])
    names = (
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
    )
    return dict(states=ledgers(row, trace), observed={k: trace[k][indices] for k in names})


def quantities(series, index, area):
    values = {k: np.asarray(v[index]) for k, v in series["observed"].items()}
    for k in ("fluxes_mem", "fluxes_gj"):
        values[k] = values[k] * area * 1e15
    values.update(
        {k: np.asarray(v[index]) for k, v in series["states"].items() if k.endswith("fmol")}
    )
    return values


def tolerance(name, tol):
    if name.startswith("cc_"):
        return tol["concentration_atol_mM"], tol["concentration_rtol"]
    if name in ("fluxes_mem", "fluxes_gj"):
        return tol["flux_atol_fmol_s"], tol["flux_rtol"]
    if name.startswith("fluxes_env"):
        return tol["environment_flux_atol_mol_m2_s"], tol["flux_rtol"]
    if name.startswith("E_env"):
        return tol["field_atol_V_m"], tol["field_rtol"]
    if name == "rho_cells":
        return tol["charge_density_atol_C_m3"], tol["field_rtol"]
    if name.endswith("fmol"):
        return tol["material_atol_fmol"], 0
    if name == "Phi_b":
        return tol["boundary_atol_V"], tol["voltage_rtol"]
    return tol["voltage_atol_V"], tol["voltage_rtol"]


def differences(coarse, middle, fine, atol, rtol, rule):
    values = tuple(np.asarray(v) for v in (coarse, middle, fine))
    assert len({v.shape for v in values}) == 1
    assert all(np.isfinite(v).all() for v in values)
    scale = atol + rtol * abs(values[2])
    errors = [
        float(np.max(abs(a - b) / scale)) for a, b in zip(values[:-1], values[1:], strict=True)
    ]
    assert errors[1] <= errors[0] + 2, (
        "Refinement increased discrepancy above comparison resolution"
    )
    resolved = min(errors) >= rule["resolved_error_multiple"]
    ratio = errors[0] / errors[1] if errors[1] else None
    if resolved:
        assert rule["ratio_min"] <= ratio <= rule["ratio_max"], (
            "Resolved differences are not first order"
        )
    return dict(
        status="passed",
        scaled_differences=errors,
        ratio=ratio,
        first_order_resolved=resolved,
        resolution="first_order" if resolved else "below_comparison_resolution",
        max_absolute_differences=[
            float(np.max(abs(a - b))) for a, b in zip(values[:-1], values[1:], strict=True)
        ],
    )


def check(case, series, area, protocol):
    rule, tol = protocol["refinement"], protocol["tolerances"]
    dt = protocol["native_steps_s"]
    assert len(series) == len(dt) == 3 and dt[0] == 2 * dt[1] == 4 * dt[2]
    checkpoints = []
    for time in rule["common_completed_times_s"]:
        indices = [round(time / h) - 1 for h in dt]
        assert all(abs((i + 1) * h - time) < 1e-18 for i, h in zip(indices, dt, strict=True))
        values = [quantities(s, i, area) for s, i in zip(series, indices, strict=True)]
        assert set(values[0]) == set(values[1]) == set(values[2])
        fields = {
            key: differences(*(v[key] for v in values), *tolerance(key, tol), rule)
            for key in values[0]
        }
        checkpoints.append(dict(completed_time_s=time, fields=fields))
    final = checkpoints[-1]["fields"]
    for key in rule["required_resolved_final_fields"][case]:
        assert final[key]["first_order_resolved"], "Required refinement signal unresolved: " + key
    return dict(
        status="passed",
        case=case,
        checkpoints=checkpoints,
        first_order_scope=(
            "Only fields marked first_order_resolved; no continuum/spatial convergence claim"
        ),
    )
