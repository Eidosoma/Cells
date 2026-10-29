"""Independent carried-state decoding and gross fuel turnover for ECM epochs."""

import numpy as np

from validation.tissue import surface_calcium_energy_reference as fuel
from validation.transport import joint_water_barrier_interventions_reference as scheduled


def initial(request):
    context = scheduled.bind(request["simulation"])
    values = {
        name: np.asarray(row["values"]).reshape(row["shape"])
        for name, row in request["source"]["checkpoint"]["state"].items()
    }
    state = scheduled.flatten(context, values).copy()
    state[-1] = 0.0
    return context, state


def carried_fuel_turnover(raw, initial_state):
    """Independent route-by-route gross consumption at the actual carried pools."""
    context = scheduled.bind(raw)
    process, parent = context["process"], context["parent"]
    data = process.unpack(parent, initial_state[:-1])
    amount = parent["energy_initial"] + data["energy_amount_increment_fmol"]
    n = len(parent["cell_ids"])
    owners = [*parent["patch_owners"], *parent["plasma_owners"], *range(n)]
    regeneration_owners = [
        parent["cell_ids"].index(parent["pools"][p["pool_id"]]["cell_id"])
        for p in raw["model"]["regeneration_ports"]
    ]
    clocks = {0.0, raw["experiment"]["end_time"]}
    for name, groups in raw["experiment"].items():
        if name.endswith("_controls"):
            for row in groups:
                clocks.update(
                    v["time"] for v in row["controls" if "controls" in row else "schedule"]
                )
    clocks.update(
        t
        for e in (() if raw["model"]["intervention"] is None else (raw["model"]["intervention"],))
        for t in (e["on_s"], (e["on_s"] + e["off_s"]) / 2, e["off_s"])
    )
    rows = []
    for time in sorted(clocks):
        state = initial_state.copy()
        state[-1] = time
        slope, _, _ = scheduled.evaluate(context, state)
        rates = process.unpack(parent, slope[:-1])
        pumps = [
            *rates["pump_cycles"],
            *rates["plasma_pump_cycles"],
            *rates["er_pump_transferred"][:, 0],
        ]
        exchange = fuel.chemistry.exchange(
            pumps, owners, rates["regeneration_cycles_fmol"].tolist(), regeneration_owners, n
        )
        gross = np.asarray(exchange["gross_hydrolysis_fmol_s"]) + exchange["gross_synthesis_fmol_s"]
        rows.append(
            dict(time_s=time, fractional_rate_s=float(np.max(gross / np.min(amount, axis=0))))
        )
    return max(v["fractional_rate_s"] for v in rows), rows
