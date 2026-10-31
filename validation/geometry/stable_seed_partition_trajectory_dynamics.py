"""Unfrozen full-horizon dynamics; seven inherited numerical functions are unchanged."""

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


class TrialSpool:
    """List interface used by the unchanged RHS, with one live mutable trial."""

    def __init__(self, journal):
        self.journal, self.current, self.count = journal, None, 0

    def __len__(self):
        return self.count

    def __getitem__(self, index):
        if index != -1 or self.current is None:
            raise IndexError("Only the current complete raw trial remains resident")
        return self.current

    def append(self, value):
        self.flush()
        self.current, self.count = value, self.count + 1

    def flush(self):
        if self.current is not None:
            self.journal.append("independent_RHS_trial", self.current)
            self.current = None


def integrate_trajectory(raw, case_plan, journal, partial):
    """DOP853 from the true initial epoch, independent of candidate checkpoints."""
    if raw["experiment"]["end_time"] != case_plan["end_time_s"]:
        raise ValueError("Independent target must use the newly declared full horizon")
    changes = [
        p["time"]
        for kind in ("membrane", "junction")
        for group in raw["experiment"][kind + "_controls"]
        for p in group["schedule"]
    ]
    if any(time != 0.0 for time in changes):
        raise ValueError("The four unchanged callers have only their explicit time-zero controls")
    if any(row["reservoir"] for row in raw["model"]["extracellular"]):
        raise ValueError("This proposal retains the original sealed finite ECM callers")
    context = bind(raw)
    initial_state = initial(context)
    journal.append(
        "independent_initial_binding", dict(definition=raw, context=context, state=initial_state)
    )
    spool = TrialSpool(journal)
    partial["rhs_trials"] = spool
    atols = flatten(
        context,
        {
            key: np.full(shape, 1e-29 if key.endswith("_C") else 2e-14)
            for key, shape in context["shapes"].items()
        },
    )
    journal.append(
        "independent_DOP853_inputs",
        dict(
            left_s=0.0,
            right_s=case_plan["end_time_s"],
            initial_state=initial_state,
            atols=atols,
            method="DOP853",
            rtol=2e-11,
            max_step=0.0001,
            dense_output=True,
            original_observations=raw["experiment"]["observation_times"],
        ),
    )
    try:
        sol = solve_ivp(
            lambda time, value: evaluate(context, value, 0.0, partial, evaluation_time_s=time)[0],
            (0.0, case_plan["end_time_s"]),
            initial_state,
            method="DOP853",
            rtol=2e-11,
            atol=atols,
            max_step=0.0001,
            dense_output=True,
        )
        spool.flush()
        # Raw return and all dense coefficients are durable before success checks.
        journal.append(
            "independent_DOP853_return", {key: value for key, value in sol.items() if key != "sol"}
        )
        if sol.sol is not None:
            journal.append(
                "independent_dense_solution",
                {key: value for key, value in vars(sol.sol).items() if key != "interpolants"},
            )
            for index, value in enumerate(sol.sol.interpolants):
                journal.append(
                    "independent_dense_interpolant",
                    dict(
                        index=index,
                        type=type(value).__module__ + "." + type(value).__qualname__,
                        attributes=vars(value),
                    ),
                )
        if (
            not sol.success
            or sol.sol is None
            or sol.t[0] != 0.0
            or sol.t[-1] != case_plan["end_time_s"]
        ):
            raise ValueError("Independent full-horizon DOP853 target failed: " + str(sol.message))
        return dict(
            binding=context,
            solution=sol,
            spool=spool,
            max_declared_samples=4 * case_plan["coarse_steps"] + 1,
            independent_initial_state=initial_state,
        )
    except BaseException:
        spool.flush()
        raise
