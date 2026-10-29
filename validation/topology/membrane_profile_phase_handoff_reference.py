"""Independent owner-loop handoff/conservation and complete passive dynamics.

This reference preserves source increments against their original inventory;
it does not reset ledgers or manufacture new initial concentrations. Decimal
thermodynamic changes and explicit owner loops check more than array copying.
"""

from copy import deepcopy
from decimal import Decimal, localcontext

import numpy as np
from scipy.integrate import solve_ivp

from validation.topology import surface_profile_interventions_reference as scheduled


def values(record):
    return {key: np.asarray(row["values"]).reshape(row["shape"]) for key, row in record.items()}


def target_definition(epoch):
    raw = deepcopy(epoch)
    raw["model"] = raw["model"]["scheduled"]
    return raw


def initial(request):
    context = scheduled.bind(request["simulation"])
    source = values(request["source"]["checkpoint"]["state"])
    state = scheduled.flatten(context, source)
    state[-1] = 0.0
    return context, state


def integrate(raw, *, initial_state=None, end_time=None):
    context = scheduled.bind(raw)
    state = scheduled.initial(context) if initial_state is None else initial_state.copy()
    end = raw["experiment"]["end_time"] if end_time is None else end_time
    knots = {0.0, end}
    for kind in ("membrane_controls", "junction_controls"):
        for row in raw["experiment"][kind]:
            knots.update(v["time"] for v in row["schedule"] if 0 < v["time"] < end)
    atols = np.r_[
        scheduled.passive.flatten(
            context["parent"],
            {
                name: np.full(shape, 1e-29 if name.endswith("_C") else 2e-14)
                for name, shape in context["parent"]["shapes"].items()
            },
        ),
        1e-22,
    ]
    evaluations = 0
    clocks = sorted(knots)
    for left, right in zip(clocks, clocks[1:], strict=False):
        result = solve_ivp(
            lambda t, y, held=left: scheduled.evaluate(context, y, held_time=held)[0],
            (left, right),
            state,
            method="DOP853",
            rtol=2e-11,
            atol=atols,
            max_step=min(0.125e-6, right - left),
        )
        if not result.success:
            raise RuntimeError(result.message)
        evaluations += result.nfev
        state = result.y[:, -1]
    return state, dict(
        method="DOP853 with exact held-control segments", rhs_evaluations=evaluations
    )


def conservation(raw, state):
    """Independent material, charge, capacitor and chemical/work history checks."""
    context = scheduled.bind(raw)
    c = context["parent"]
    p = scheduled.passive
    model = c["raw"]["model"]
    history = p.unpack(c, state[:-1])
    di, do = history["amount_increment"], history["extracellular_amount_increment"]
    ci, co = c["ai"] + di, c["ao"] + do
    cells = [v["id"] for v in model["cells"]]
    outside = [v["id"] for v in model["extracellular"]]
    local, external = di.copy(), do.copy() - history["reservoir_supplied"]
    for i, row in enumerate(model["membranes"]):
        h = history["membrane_transferred"][:, i]
        local[:, cells.index(row["inside"])] += h
        external[:, outside.index(row["outside"])] -= h
    for i, row in enumerate(model["junctions"]):
        h = history["junction_transferred"][:, i]
        local[:, cells.index(row["sender"])] += h
        local[:, cells.index(row["receiver"])] -= h
    for i, row in enumerate(model["faces"]):
        h = history["face_transferred"][:, i]
        external[:, outside.index(row["sender"])] += h
        external[:, outside.index(row["receiver"])] -= h
    valence = np.asarray([v["valence"] for v in model["species"]])[:, None]
    qdelta = p.F * 1e-15 * np.r_[np.sum(valence * di, axis=0), np.sum(valence * do, axis=0)]
    raw_stage = p.stage(c, state[:-1], 0.0)
    matrix, active, reservoir, _, floating, _ = p.electrical.topology(raw_stage)
    pins = ~active | reservoir
    for component in floating:
        pins[component[0]] = True
    free = np.flatnonzero(~pins)
    dp = np.zeros_like(qdelta)
    dp[free] = np.linalg.solve(matrix[np.ix_(free, free)], qdelta[free])
    n = len(cells)
    # Resolve the charge-only anchor with an independent floating pin. These
    # patch voltages are independent of the new kinetic controls and offsets.
    phi0 = np.r_[np.zeros(n), [v["boundary_potential_V"] for v in model["extracellular"]]]
    initial_charge = np.r_[c["qi"], c["qo"]]
    phi0[free] = np.linalg.solve(
        matrix[np.ix_(free, free)],
        initial_charge[free] - matrix[np.ix_(free, np.flatnonzero(pins))] @ phi0[pins],
    )
    required = active & ~reservoir
    charge_residual = (matrix @ dp - qdelta)[required]
    electrode_residual = history["electrode_charge_transferred_C"] - np.where(
        reservoir[n:], (matrix @ dp)[n:], 0.0
    )
    with localcontext() as decimal_context:
        decimal_context.prec = 80

        def d(value):
            return Decimal(str(float(value)))

        chemical = Decimal(0)
        for delta, anchor, volume in ((di, c["ai"], c["vi"]), (do, c["ao"], c["vo"])):
            for i in range(delta.shape[0]):
                for j in range(delta.shape[1]):
                    a, change, v = d(anchor[i, j]), d(delta[i, j]), d(volume[j])
                    chemical += (
                        d(1e-3)
                        * d(p.R)
                        * d(model["temperature_K"])
                        * (change * ((a / v).ln() - 1) + (a + change) * (1 + change / a).ln())
                    )
        electric = Decimal(0)
        for row in model["membranes"]:
            a, b = cells.index(row["inside"]), n + outside.index(row["outside"])
            dv, vm0 = d(dp[a] - dp[b]), d(phi0[a] - phi0[b])
            electric += d(0.5e12) * d(row["capacitance_F"]) * dv * (2 * vm0 + dv)
        dissipation = sum(
            (
                d(v)
                for kind in ("membrane", "junction", "face")
                for v in history[kind + "_dissipated_energy_pJ"]
            ),
            Decimal(0),
        )
        work = sum(
            (d(v) for kind in ("reservoir", "electrode") for v in history[kind + "_work_pJ"]),
            Decimal(0),
        )
        energy = chemical + electric + dissipation - work
    return dict(
        cell_amount_fmol=ci,
        extracellular_amount_fmol=co,
        cell_charge_C=c["qi"] + qdelta[:n],
        extracellular_charge_C=c["qo"] + qdelta[n:],
        local_residual_fmol=local,
        outside_residual_fmol=external,
        global_residual_fmol=di.sum(axis=1)
        + do.sum(axis=1)
        - history["reservoir_supplied"].sum(axis=1),
        capacitor_charge_residual_C=charge_residual,
        electrode_charge_residual_C=electrode_residual,
        global_charge_residual_C=float(
            history["electrode_charge_transferred_C"].sum()
            + p.F * 1e-15 * np.sum(valence * history["reservoir_supplied"])
        ),
        chemical_change_pJ=float(chemical),
        capacitor_change_pJ=float(electric),
        dissipated_energy_pJ=float(dissipation),
        work_pJ=float(work),
        energy_residual_pJ=float(energy),
    )
