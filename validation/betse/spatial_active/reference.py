"""Independent scalar native active laws and complete material accounting.

No Cells/JAX/BETSE imports. Existing Decimal constitutive oracles and native
spatial checks are reused; channel transfer is included exactly once in the
total material projection, while ordinary flux remains separately checked.
"""

import numpy as np

from validation.betse.junction_transport.check import decimal_flux
from validation.betse.pump_contact.pump_reference import oracle
from validation.betse.spatial_active import gate_roundoff
from validation.betse.spatial_trajectory import reference as spatial
from validation.betse.tissue_contact import reference as updates


def channel_update(row, before, after, near):
    p, g, active = row["parameters"], row["geometry"], row["fixture"]["active"]
    voltage = before["vm"] * 1000
    targets = (1 / (1 + np.exp(-(voltage + 6) / 6.4)), 1 / (1 + np.exp((voltage + 25.3) / 3.5)))
    taus = (8.330 - 0.1163 * voltage, 1620 - 15.5 * voltage)
    for name, target, tau in zip(("m_gate", "h_gate"), targets, taus, strict=True):
        gate = (tau * before[name] + row["dt_s"] * 1000 * target) / (tau + row["dt_s"] * 1000)
        near(name, after[name], gate, 2e-13, 2e-12)
    owners, out = (np.asarray(g[key], dtype=int) for key in ("mem_to_cells", "map_mem2ecm"))
    area, volume, k = np.asarray(g["mem_sa"]), np.asarray(g["cell_vol"]), row["species"]["K"]
    permeability = np.broadcast_to(active["channel_permeability_m_s"], area.shape)
    constants = {key: p[key] for key in ("F", "R")}
    flux = np.array(
        [
            decimal_flux(co, ci, -v, 1, p["T"], a, per, 1.0, m * h, constants)
            for co, ci, v, a, per, m, h in zip(
                before["cc_env"][k, out],
                before["cc_cells"][k, owners],
                before["vm"],
                area,
                permeability,
                after["m_gate"],
                after["h_gate"],
                strict=True,
            )
        ]
    )
    near("channel_flux_fmol_s", after["channel_flux"] * area * 1e15, flux, 2e-11, 2e-12)
    expected_cells, expected_env = before["cc_cells"].copy(), before["cc_env"].copy()
    for patch, (i, o) in enumerate(zip(owners, out, strict=True)):
        expected_cells[k, i] += row["dt_s"] * flux[patch] / (volume[i] * 1e15)
        expected_env[k, o] -= (
            row["dt_s"] * flux[patch] / (p["cell_height"] * g["delta"] ** 2 * 1e15)
        )
    near("channel_cell_update_mM", after["cc_cells"], expected_cells, 5e-12, 2e-13)
    near("channel_outside_update_mM", after["cc_env"], expected_env, 5e-12, 2e-13)
    near(
        "channel_membrane_update_mM", after["cc_at_mem"][k], expected_cells[k, owners], 5e-12, 2e-13
    )
    np.testing.assert_array_equal(after["fluxes_mem"], before["fluxes_mem"])


def native_check(row, trace, protocol, *, step_rows=None):
    if step_rows is not None:
        assert len(step_rows) == row["steps"]
        rows = iter(step_rows)

        def check_channel(unused, before, after, near):
            channel_update(next(rows), before, after, near)
    else:
        check_channel = channel_update
    report = updates.check(
        row,
        trace,
        protocol | {"tolerances": protocol["native_update_tolerances"]},
        active_pump=True,
        additional_updates={4: check_channel},
    )
    p, g, active = row["parameters"], row["geometry"], row["fixture"]["active"]
    area, out = np.asarray(g["mem_sa"]), np.asarray(g["map_mem2ecm"])
    na, k = row["species"]["Na"], row["species"]["K"]
    q, maximum = active["pump_parameters"], 0.0
    for step in range(row["steps"]):
        if step_rows is not None:
            active = step_rows[step]["fixture"]["active"]
        indices = np.flatnonzero(trace["step"] == step)
        first, final = indices[0], indices[-1]
        before = {name: trace[name][first] for name in ("cc_at_mem", "cc_env", "vm")}
        pumps = []
        for patch, site in enumerate(out):
            case = dict(
                id="spatial",
                na_in_mM=before["cc_at_mem"][na, patch],
                na_out_mM=before["cc_env"][na, site],
                k_in_mM=before["cc_at_mem"][k, patch],
                k_out_mM=before["cc_env"][k, site],
                atp_mM=q["cATP"],
                adp_mM=q["cADP"],
                pi_mM=q["cPi"],
                km_na_mM=q["KmNK_Na"],
                km_k_mM=q["KmNK_K"],
                km_atp_mM=q["KmNK_ATP"],
                temperature_K=p["T"],
                area_m2=area[patch],
                alpha_mol_m2_s=p["alpha_NaK"],
                availability=active["pump_availability"][patch],
                voltage_V=before["vm"][patch],
                delta_g0_J_mol=q["deltaGATP"],
            )
            case = {key: value if key == "id" else float(value) for key, value in case.items()}
            pumps.append(oracle(case, {key: p[key] for key in ("F", "R")})["third_out_na_fmol_s"])
        pump_na = np.asarray(pumps)
        raw = trace["rate_NaKATP"][final] * area * 1e15
        np.testing.assert_allclose(raw, pump_na, atol=2e-11, rtol=2e-12)
        maximum = max(maximum, float(np.max(abs(raw - pump_na))))
        # The native rate diagnostic precedes the optional cluster boundary mask.
        if not p["cluster_open"]:
            pump_na[np.asarray(g["bflags_mems"], dtype=int)] = 0
        for ion in row["fixture"]["moving_ions"]:
            (index,) = np.flatnonzero(
                (trace["step"] == step)
                & (trace["method"] == 0)
                & (trace["ion"] == ion)
                & ~trace["after"]
            )
            # At this boundary this ion has not yet undergone exterior diffusion.
            leak = np.array(
                [
                    decimal_flux(
                        co,
                        ci,
                        -v,
                        row["arrays"]["zs"][ion],
                        p["T"],
                        a,
                        per / p["tm"],
                        1.0,
                        1.0,
                        {key: p[key] for key in ("F", "R")},
                    )
                    for co, ci, v, a, per in zip(
                        trace["cc_env"][index, ion, out],
                        before["cc_at_mem"][ion],
                        before["vm"],
                        area,
                        row["arrays"]["Dm_cells"][ion],
                        strict=True,
                    )
                ]
            )
            if not p["cluster_open"]:
                leak[np.asarray(g["bflags_mems"], dtype=int)] = 0
            expected = leak + (-pump_na if ion == na else (2 / 3) * pump_na if ion == k else 0)
            np.testing.assert_allclose(
                trace["fluxes_mem"][final, ion] * area * 1e15, expected, atol=2e-11, rtol=2e-12
            )
        np.testing.assert_allclose(
            trace["extra_J_mem"][final],
            -trace["channel_flux"][final] * p["F"],
            atol=2e-10,
            rtol=2e-12,
        )
    report["max_pump_error_fmol_s"] = maximum
    return report


def compare(row, trace, tol, tissue, active, rates, observed, *, gate_allowance=None):
    k, area = row["species"]["K"], np.asarray(row["geometry"]["mem_sa"])
    indices = np.flatnonzero((trace["method"] == 3) & trace["after"])
    projected_trace = dict(trace)
    projected_trace["fluxes_mem"] = trace["fluxes_mem"].copy()
    projected_trace["fluxes_mem"][:, k] += trace["channel_flux"]
    projected_states = dict(tissue)
    projected_states["membrane_inward_fmol"] = tissue["membrane_inward_fmol"].copy()
    projected_states["membrane_inward_fmol"][:, k] += active["channel_inward_fmol"]
    projected_observed = dict(observed)
    projected_observed["fluxes_mem"] = observed["fluxes_mem"].copy()
    projected_observed["fluxes_mem"][:, k] += rates["channel_inward_fmol_s"] / area * 1e-15
    report = spatial.compare(row, projected_trace, tol, projected_states, projected_observed)
    errors, count = {}, 0

    def near(name, actual, expected, atol, rtol=0):
        nonlocal count
        assert (
            actual.shape == expected.shape
            and np.isfinite(actual).all()
            and np.isfinite(expected).all()
        )
        budget = atol + rtol * abs(expected)
        allowance = gate_roundoff.addition(gate_allowance, name, expected)
        if gate_allowance is not None and name in gate_roundoff.NAMES:
            report.setdefault("gate_original_comparison", {})[name] = dict(
                max_error_over_budget=float(np.max(abs(actual - expected) / budget)),
                violations=int(np.count_nonzero(abs(actual - expected) > budget)),
                max_voltage_allowance=float(np.max(allowance)),
            )
        budget = budget + allowance
        if gate_allowance is None or name not in gate_roundoff.NAMES:
            np.testing.assert_allclose(actual, expected, atol=atol, rtol=rtol, err_msg=name)
        else:
            np.testing.assert_allclose(
                (actual - expected) / budget, 0, atol=1, rtol=0, err_msg=name
            )
        errors[name] = float(np.max(abs(actual - expected), initial=0))
        report["max_error_over_budget"] = max(
            report["max_error_over_budget"],
            float(np.max(abs(actual - expected) / budget, initial=0)),
        )
        count += actual.size

    for name in ("m_gate", "h_gate"):
        near(name, active[name], trace[name][indices], tol["gate_atol"], tol["gate_rtol"])
    ordinary = trace["fluxes_mem"][indices] * area * 1e15
    near(
        "ordinary_membrane_fmol_s",
        observed["fluxes_mem"] * area * 1e15,
        ordinary,
        tol["flux_atol_fmol_s"],
        tol["flux_rtol"],
    )
    channel = trace["channel_flux"][indices] * area * 1e15
    cycles = trace["rate_NaKATP"][indices] * area * 1e15 / 3
    if not row["parameters"]["cluster_open"]:
        cycles[:, np.asarray(row["geometry"]["bflags_mems"], dtype=int)] = 0
    for name, expected in (("channel_inward_fmol_s", channel), ("pump_cycles_fmol_s", cycles)):
        near(name, rates[name], expected, tol["flux_atol_fmol_s"], tol["flux_rtol"])
        ledger = name.removesuffix("_s")
        near(
            ledger,
            active[ledger],
            np.cumsum(expected * row["dt_s"], axis=0),
            tol["material_atol_fmol"],
        )
    near(
        "ordinary_membrane_ledger_fmol",
        tissue["membrane_inward_fmol"],
        np.cumsum(ordinary * row["dt_s"], axis=0),
        tol["material_atol_fmol"],
    )
    report.update(
        active_max_errors=errors,
        active_compared_scalars=count,
        passive_projection_compared_scalars=report["compared_scalars"],
        material_projection=(
            "ordinary membrane plus separately recorded channel transfer exactly once"
        ),
    )
    report["compared_scalars"] += count
    return report
