"""Independent common-endpoint dynamics: unchanged full-node/scalar laws."""

import copy
import math

import numpy as np
from scipy.integrate import solve_ivp

from validation.geometry import (
    stable_seed_partition_physiology_bridge_field_reference as electrical,
)
from validation.geometry import (
    stable_seed_partition_physiology_bridge_scalar_reference as transport,
)

F, R = transport.F, transport.R


def bind(raw):
    m = raw["model"]
    ids = [p["id"] for p in m["species"]]
    ci, co = ([p["id"] for p in m["cells"]], [p["id"] for p in m["extracellular"]])
    n, o, nm, ne, nf, s = (
        len(ci),
        len(co),
        len(m["membranes"]),
        len(m["junctions"]),
        len(m["faces"]),
        len(ids),
    )
    p = dict(
        temperature=m["temperature_K"],
        valence=[[v["valence"]] for v in m["species"]],
        cell_active=[True] * n,
        outside_active=[True] * o,
        reservoir=[p["reservoir"] for p in m["extracellular"]],
        membrane_active=[True] * nm,
        junction_active=[True] * ne,
        face_active=[True] * nf,
    )
    for kind, owners in (
        ("membrane", m["membranes"]),
        ("junction", m["junctions"]),
        ("face", m["faces"]),
    ):
        if kind == "membrane":
            p["membrane_cell"] = [ci.index(v["inside"]) for v in owners]
            p["membrane_outside"] = [co.index(v["outside"]) for v in owners]
            p["membrane_capacitance"] = [v["capacitance_F"] for v in owners]
        else:
            names = co if kind == "face" else ci
            for side in ("sender", "receiver"):
                p[kind + "_" + side] = [names.index(v[side]) for v in owners]
        if kind == "face":
            p["face_factor"] = [
                [v["diffusivity_m2_per_s"][ion] * v["area_m2"] / v["length_m"] for v in owners]
                for ion in ids
            ]
        else:
            p[kind + "_area"] = [v["area_m2"] for v in owners]
            p[kind + "_permeability"] = [
                [v["permeability_m_per_s"][ion] for v in owners] for ion in ids
            ]
    shapes = dict(
        amount_increment=(s, n),
        extracellular_amount_increment=(s, o),
        membrane_transferred=(s, nm),
        junction_transferred=(s, ne),
        face_transferred=(s, nf),
        reservoir_supplied=(s, o),
        membrane_dissipated_energy_pJ=(nm,),
        junction_dissipated_energy_pJ=(ne,),
        face_dissipated_energy_pJ=(nf,),
        electrode_charge_transferred_C=(o,),
        reservoir_work_pJ=(o,),
        electrode_work_pJ=(o,),
    )
    return dict(
        raw=copy.deepcopy(raw),
        layout=p,
        shapes=shapes,
        ai=np.asarray([[c["initial_amount_fmol"][ion] for c in m["cells"]] for ion in ids]),
        ao=np.asarray([[c["initial_amount_fmol"][ion] for c in m["extracellular"]] for ion in ids]),
        vi=np.asarray([v["volume_pL"] for v in m["cells"]]),
        vo=np.asarray([v["volume_pL"] for v in m["extracellular"]]),
        qi=np.asarray([v["initial_charge_C"] for v in m["cells"]]),
        qo=np.asarray([v["initial_charge_C"] for v in m["extracellular"]]),
    )


def initial(c):
    return np.zeros(sum((math.prod(shape) for shape in c["shapes"].values())))


def unpack(c, flat):
    result, start = ({}, 0)
    flat = np.asarray(flat)
    for name, shape in c["shapes"].items():
        size = math.prod(shape)
        result[name] = flat[..., start : start + size].reshape((*flat.shape[:-1], *shape))
        start += size
    return result


def flatten(c, fields):
    result = []
    for name, shape in c["shapes"].items():
        value = np.asarray(fields[name])
        slices = (Ellipsis, *(slice(0, v) for v in shape))
        result.append(value[slices].reshape((*value.shape[: -len(shape)], math.prod(shape))))
    return np.concatenate(result, axis=-1)


def stage(c, state, time, *, charge_equivalent_increment_fmol=None):
    d, m, p = (unpack(c, state), c["raw"]["model"], c["layout"])
    raw = dict(
        layout=p,
        ci=(c["ai"] + d["amount_increment"]) / c["vi"],
        co=(c["ao"] + d["extracellular_amount_increment"]) / c["vo"],
        cell_charge_C=c["qi"]
        + 1e-15 * F * np.sum(np.asarray(p["valence"]) * d["amount_increment"], axis=0),
        outside_charge_C=c["qo"]
        + 1e-15
        * F
        * np.sum(np.asarray(p["valence"]) * d["extracellular_amount_increment"], axis=0),
        boundary_V=[v["boundary_potential_V"] for v in m["extracellular"]],
        gauge_mask=[v["id"] == m["closure"]["gauge_reference"] for v in m["extracellular"]],
        seed_potential_V=np.zeros(len(c["qi"]) + len(c["qo"])),
    )
    if charge_equivalent_increment_fmol is not None:
        charge = np.asarray(charge_equivalent_increment_fmol)
        if (
            charge.shape != (len(c["qi"]) + len(c["qo"]),)
            or charge.dtype.kind not in "fi"
            or (not np.isfinite(charge).all())
        ):
            raise ValueError("Charge increments require one finite real value per node")
        split = len(c["qi"])
        raw["cell_charge_C"] = c["qi"] + 1e-15 * F * charge[:split]
        raw["outside_charge_C"] = c["qo"] + 1e-15 * F * charge[split:]
    for kind in ("membrane", "junction"):
        controls = {
            g[kind + "_id"]: g["schedule"] for g in c["raw"]["experiment"][kind + "_controls"]
        }
        raw[kind + "_open"] = [
            next((v["availability"] for v in reversed(controls[r["id"]]) if v["time"] <= time))
            for r in m[kind + "s"]
        ]
    return raw


def evaluate(c, state, time, partial, *, evaluation_time_s=None):
    event = dict(
        index=len(partial.setdefault("rhs_trials", [])),
        held_control_time_s=time,
        evaluation_time_s=evaluation_time_s,
        state=np.array(state, copy=True),
        raw=None,
        root={},
    )
    partial["rhs_trials"].append(event)
    partial["stage"] = "independent_RHS_" + str(event["index"])
    raw = stage(c, state, time)
    event["raw"] = raw
    phi, proof = electrical.solve(raw, event["root"])
    event["completed_root"] = dict(potential_V=phi, receipt=proof)
    n, p = (len(c["qi"]), c["layout"])
    rates = transport.transport(raw, phi[:n], phi[n:])
    event["completed_scalar_rates"] = rates
    matrix, active, reservoir, fixed, floating, _ = electrical.topology(raw)
    pins = ~active | reservoir
    for members in floating:
        pins[members[0]] = True
    free = np.flatnonzero(~pins)
    ionic = (
        1e-15
        * F
        * (
            np.asarray(p["valence"]).T
            @ np.c_[rates["cell_rate_fmol_s"], rates["outside_rate_fmol_s"]]
        )[0]
    )
    event["derivative_linear_input"] = dict(
        capacitor_matrix=matrix,
        ionic_rate=ionic,
        active=active,
        reservoir=reservoir,
        pins=pins,
        free=free,
    )
    derivative = np.zeros_like(phi)
    event["potential_derivative_return"] = derivative
    derivative[free] = np.linalg.solve(matrix[np.ix_(free, free)], ionic[free])
    electrode = np.where(p["reservoir"], (matrix @ derivative)[n:], 0.0)
    np.testing.assert_allclose(
        (matrix @ derivative)[active & ~reservoir],
        ionic[active & ~reservoir],
        rtol=2e-12,
        atol=2e-23,
    )
    reservoir_mu = R * p["temperature"] * np.log(raw["co"]) + F * np.asarray(p["valence"]) * phi[n:]
    result = dict(
        amount_increment=rates["cell_rate_fmol_s"],
        extracellular_amount_increment=rates["outside_rate_fmol_s"],
        reservoir_supplied=rates["reservoir_supply_fmol_s"],
        electrode_charge_transferred_C=electrode,
        reservoir_work_pJ=0.001 * np.sum(reservoir_mu * rates["reservoir_supply_fmol_s"], axis=0),
        electrode_work_pJ=1000000000000.0 * phi[n:] * electrode,
    )
    event["complete_RHS_fields"] = result
    for kind in ("membrane", "junction", "face"):
        result[kind + "_transferred"] = rates[kind + "_flux_fmol_s"]
        result[kind + "_dissipated_energy_pJ"] = rates[kind + "_dissipation_pJ_s"]
    flat = flatten(c, result)
    event["completed_flat_RHS"] = flat
    return (flat, phi, proof)


def field_snapshot(c, state, time, partial):
    """All physical field and RHS targets from a retained independent evaluation."""
    flat_rhs, phi, proof = evaluate(c, state, time, partial, evaluation_time_s=time)
    event = partial["rhs_trials"][-1]
    raw, rates = event["raw"], dict(event["completed_scalar_rates"])
    p, n = raw["layout"], len(c["qi"])
    matrix, active, reservoir, _, floating, _ = electrical.topology(raw)
    charge = np.r_[raw["cell_charge_C"], raw["outside_charge_C"]]
    capacitor = matrix @ phi
    residual = np.where(active & ~reservoir, capacitor - charge, 0.0)
    derivative = event["potential_derivative_return"]
    patch_rate = derivative[p["membrane_cell"]] - derivative[n + p["membrane_outside"]]
    divergence, scale = electrical.currents(raw, phi)
    current = np.asarray([math.fsum(float(divergence[i]) for i in members) for members in floating])
    bound = 3e-25 + 2e-12 * np.maximum(np.abs(charge), np.abs(capacitor))
    patch_charge = np.asarray(p["membrane_capacitance"]) * rates["membrane_voltage_V"]
    electrode = unpack(c, flat_rhs)["electrode_charge_transferred_C"]
    supply = rates["reservoir_supply_fmol_s"]
    mu = R * p["temperature"] * np.log(raw["co"]) + F * np.asarray(p["valence"]) * phi[n:]
    chemical = (
        1e-3
        * R
        * p["temperature"]
        * (
            np.sum(np.log(raw["ci"]) * rates["cell_rate_fmol_s"])
            + np.sum(np.log(raw["co"]) * rates["outside_rate_fmol_s"])
        )
    )
    cap_power = 1e12 * np.sum(patch_charge * patch_rate)
    supplied_power = 1e-3 * np.sum(mu * supply)
    electrode_power = 1e12 * np.sum(phi[n:] * electrode)
    dissipation = sum(
        np.sum(rates[k + "_dissipation_pJ_s"]) for k in ("membrane", "junction", "face")
    )
    rates["valid"] = np.asarray(all(np.isfinite(value).all() for value in rates.values()))
    values = dict(
        potential_V=phi,
        membrane_charge_C=patch_charge,
        capacitor_node_charge_C=capacitor,
        charge_residual_C=residual,
        charge_normalized=np.max(np.abs(residual) / bound),
        component_current_residual_A=current,
        current_normalized=np.max(np.abs(current), initial=0.0) / (1e-23 + 2e-12 * scale),
        electrode_charge_C=np.where(p["reservoir"], (capacitor - charge)[n:], 0.0),
        electrode_current_A=electrode,
        reservoir_supply_charge_A=1e-15 * F * np.sum(np.asarray(p["valence"]) * supply, axis=0),
        membrane_voltage_rate_V_s=patch_rate,
        capacitor_energy_pJ=0.5e12 * np.sum(patch_charge * rates["membrane_voltage_V"]),
        capacitor_energy_rate_pJ_s=cap_power,
        chemical_energy_rate_pJ_s=chemical,
        reservoir_power_pJ_s=supplied_power,
        electrode_power_pJ_s=electrode_power,
        dissipation_pJ_s=dissipation,
        energy_balance_pJ_s=chemical + cap_power + dissipation - supplied_power - electrode_power,
        rates=rates,
        iterations=None,
        converged=np.asarray(True),
    )
    event["completed_full_field"] = values
    return dict(field=values, rhs=unpack(c, flat_rhs), root_receipt=proof)


def integrate_common_endpoint(raw, sample_times, partial):
    """Original DOP853 budgets and full-node laws; extra sampling adds no event."""
    partial["original_definition"] = copy.deepcopy(raw)
    partial["declared_reference_sample_times"] = list(sample_times)
    context = bind(raw)
    partial["independent_binding"] = context
    end = raw["experiment"]["end_time"]
    times = sorted(set(float(time) for time in sample_times))
    if not times or times[0] != 0.0 or times[-1] != end or len(times) > 5:
        raise ValueError("Reference sampling must bind original clocks and exact common endpoint")
    events = sorted(
        {
            0.0,
            end,
            *(
                p["time"]
                for kind in ("membrane", "junction")
                for group in raw["experiment"][kind + "_controls"]
                for p in group["schedule"]
            ),
        }
    )
    values = {0.0: initial(context)}
    partial["completed_reference_states"] = values
    state = initial(context)
    partial["initial_reference_state"] = state
    evaluations = 0
    atols = flatten(
        context,
        {
            key: np.full(shape, 1e-29 if key.endswith("_C") else 2e-14)
            for key, shape in context["shapes"].items()
        },
    )
    partial["independent_unit_specific_atol"] = atols
    segments = []
    partial["segments"] = segments
    for left, right in zip(events, events[1:], strict=False):
        segment = dict(
            left_s=left,
            right_s=right,
            held_control_time_s=left,
            initial_state=np.array(state, copy=True),
            returned=None,
        )
        segments.append(segment)
        partial["stage"] = "independent_DOP853_segment"
        sol = solve_ivp(
            lambda time, value, held=left: evaluate(
                context, value, held, partial, evaluation_time_s=time
            )[0],
            (left, right),
            state,
            method="DOP853",
            rtol=2e-11,
            atol=atols,
            max_step=0.0001,
            dense_output=True,
        )
        segment["returned"] = {key: value for key, value in sol.items() if key != "sol"}
        if sol.sol is not None:
            dense = {key: value for key, value in vars(sol.sol).items() if key != "interpolants"}
            dense["interpolants"] = [
                dict(
                    type=type(value).__module__ + "." + type(value).__qualname__,
                    attributes=vars(value),
                )
                for value in sol.sol.interpolants
            ]
            segment["dense_output"] = dense
        partial["stage"] = "independent_DOP853_success_gate"
        if not sol.success:
            raise ValueError("Independent DOP853 segment failed: " + str(sol.message))
        evaluations += sol.nfev
        for time in times:
            if left < time <= right:
                values[time] = sol.sol(time)
        state = sol.y[:, -1]
        segment["completed_endpoint_state"] = state
    samples = {}
    partial["completed_reference_field_RHS_samples"] = samples
    for time in times:
        samples[time] = field_snapshot(context, values[time], time, partial)
    return dict(
        times=times,
        states={time: unpack(context, values[time]) for time in times},
        flat_states={time: values[time] for time in times},
        samples=samples,
        rhs_evaluations=evaluations,
        binding=context,
        method="DOP853 with full-node roots and Decimal transport",
        rtol=2e-11,
        amount_energy_atol=2e-14,
        electrode_charge_atol_C=1e-29,
        experiment_observations_modified=False,
        reference_sampling_is_a_numerical_control=True,
    )
