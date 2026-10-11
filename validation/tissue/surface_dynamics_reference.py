"""Independent full-node field roots and segmented adaptive DOP853 trajectories.

No Cells/JAX imports. The existing independently checked scalar/Decimal patch
laws and full-node charge/current system are reused; no production RHS, bind,
RK4 implementation or ledger calculation is called.
"""

import copy
import math

import numpy as np
from scipy.integrate import solve_ivp

from validation.tissue import surface_field_reference as electrical
from validation.tissue import surface_reference as transport

F, R = transport.F, transport.R


def bind(raw):
    m = raw["model"]
    ids = [p["id"] for p in m["species"]]
    ci, co = [p["id"] for p in m["cells"]], [p["id"] for p in m["extracellular"]]
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
    return np.zeros(sum(math.prod(shape) for shape in c["shapes"].values()))


def unpack(c, flat):
    result, start = {}, 0
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


def stage(c, state, time):
    d, m, p = unpack(c, state), c["raw"]["model"], c["layout"]
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
    for kind in ("membrane", "junction"):
        controls = {
            g[kind + "_id"]: g["schedule"] for g in c["raw"]["experiment"][kind + "_controls"]
        }
        raw[kind + "_open"] = [
            next(v["availability"] for v in reversed(controls[r["id"]]) if v["time"] <= time)
            for r in m[kind + "s"]
        ]
    return raw


def evaluate(c, state, time):
    raw = stage(c, state, time)
    phi, proof = electrical.solve(raw)
    n, p = len(c["qi"]), c["layout"]
    rates = transport.transport(raw, phi[:n], phi[n:])
    matrix, active, reservoir, fixed, floating, _ = electrical.topology(raw)
    # Different derivative reduction: pin the first active node in each floating
    # capacitor component (production pins outside nodes). Patch rates are invariant.
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
    derivative = np.zeros_like(phi)
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
        reservoir_work_pJ=1e-3 * np.sum(reservoir_mu * rates["reservoir_supply_fmol_s"], axis=0),
        electrode_work_pJ=1e12 * phi[n:] * electrode,
    )
    for kind in ("membrane", "junction", "face"):
        result[kind + "_transferred"] = rates[kind + "_flux_fmol_s"]
        result[kind + "_dissipated_energy_pJ"] = rates[kind + "_dissipation_pJ_s"]
    return flatten(c, result), phi, proof


def integrate(raw):
    c = bind(raw)
    end = raw["experiment"]["end_time"]
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
    times = raw["experiment"]["observation_times"]
    result = {0.0: initial(c)}
    state, evaluations = initial(c), 0
    # Unit-specific absolute bounds: electrode charge is coulombs, all other
    # coordinates are fmol or pJ. No scalar loose atol can hide electrode errors.
    atols = flatten(
        c,
        {
            k: np.full(shape, 1e-29 if k.endswith("_C") else 2e-14)
            for k, shape in c["shapes"].items()
        },
    )
    for left, right in zip(events, events[1:], strict=False):
        sol = solve_ivp(
            lambda t, y, held=left: evaluate(c, y, held)[0],
            (left, right),
            state,
            method="DOP853",
            rtol=2e-11,
            atol=atols,
            max_step=0.0001,
            dense_output=True,
        )
        assert sol.success, sol.message
        evaluations += sol.nfev
        for t in times:
            if left < t <= right:
                result[t] = sol.sol(t)
        state = sol.y[:, -1]
    fields = [evaluate(c, result[t], t)[1] for t in times]
    return dict(
        times=times,
        state=np.stack([result[t] for t in times]).tolist(),
        potential_V=np.stack(fields).tolist(),
        rhs_evaluations=evaluations,
        method="DOP853 with full-node roots and Decimal transport",
        rtol=2e-11,
        amount_energy_atol=2e-14,
        electrode_charge_atol_C=1e-29,
    )
