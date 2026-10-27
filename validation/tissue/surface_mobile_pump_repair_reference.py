"""Independent Decimal ATPase and scalar transport on owned calcium/injury.

No production Cells/JAX imports. Protein diffusion, 3Na/2K transfer and signed
ATP work are accumulated explicitly, alongside the independent existing model.
"""

import math
from copy import deepcopy

import numpy as np
from scipy.integrate import solve_ivp

from validation.betse.pump_contact.pump_reference import oracle as pump_oracle
from validation.tissue import surface_mobile_repair_reference as prior

flatten, unpack, initial = prior.flatten, prior.unpack, prior.initial
F, R = prior.F, prior.R


def bind(raw):
    base = deepcopy(raw)
    pumps = base["model"].pop("mobile_pumps")
    controls = base["experiment"].pop("mobile_pump_controls")
    base["model"]["id"] = "resolved_repair@2"
    c = prior.bind(base)
    k, n, e = (
        len(pumps),
        len(base["model"]["ionic"]["membranes"]),
        len(base["model"]["surface_edges"]),
    )
    c.update(mobile_pumps=pumps, mobile_pump_controls=controls, full_pump_inputs=deepcopy(raw))
    c["shapes"].update(
        mobile_pump_amount_increment=(k, n),
        mobile_pump_surface_transferred=(k, e),
        mobile_pump_surface_dissipated_energy_pJ=(k, e),
        mobile_pump_cycles=(k, n),
        mobile_pump_dissipated_energy_pJ=(k, n),
        mobile_pump_metabolic_work_pJ=(k, n),
    )
    return c


def evaluate(c, state, time, *, channel_levels=None):
    slope, phi, proof = prior.evaluate(c, state, time, channel_levels=channel_levels)
    result, d, p = unpack(c, slope), unpack(c, state), c["layout"]
    m = c["raw"]["model"]
    patches = [p["id"] for p in m["membranes"]]
    ions = [s["id"] for s in m["species"]]
    balance = 0.0
    for k, pop in enumerate(c["mobile_pumps"]):
        density = []
        meta = pop["metabolism"]
        for j, patch in enumerate(m["membranes"]):
            amount = (
                pop["initial_amount_fmol"][patch["id"]] + d["mobile_pump_amount_increment"][k, j]
            )
            density.append(amount / (patch["area_m2"] * 1e12))
            i, o = p["membrane_cell"][j], p["membrane_outside"][j]
            store = c["stores"][i]
            a = store.n0 + d["chemical_amount_increment"][i]
            ci = {s: a[store.ids.index(s), store.cy] / c["vi"][i] for s in pop["roles"].values()}
            co = {
                s: (
                    c["ao"][ions.index(s), o]
                    + d["extracellular_amount_increment"][ions.index(s), o]
                )
                / c["vo"][o]
                for s in pop["roles"].values()
            }
            na, ka = pop["roles"]["sodium"], pop["roles"]["potassium"]
            group = next(
                row["schedule"]
                for row in c["mobile_pump_controls"]
                if row["pump_id"] == pop["id"] and row["membrane_id"] == patch["id"]
            )
            level = next(v["availability"] for v in reversed(group) if v["time"] <= time)
            vm = phi[i] - phi[len(c["vi"]) + o]
            case = dict(
                id=pop["id"],
                na_in_mM=float(ci[na]),
                na_out_mM=float(co[na]),
                k_in_mM=float(ci[ka]),
                k_out_mM=float(co[ka]),
                temperature_K=p["temperature"],
                area_m2=patch["area_m2"],
                alpha_mol_m2_s=float(pop["turnover_per_s"] * amount * 1e-15 / patch["area_m2"]),
                availability=level,
                voltage_V=float(vm),
                delta_g0_J_mol=meta["delta_g0_J_per_mol"],
                **{v: meta[v] for v in ("atp_mM", "adp_mM", "pi_mM")},
                **{v: pop[v] for v in ("km_na_mM", "km_k_mM", "km_atp_mM")},
            )
            rate = pump_oracle(case, dict(F=F, R=R))
            result["mobile_pump_cycles"][k, j] = -rate["na_in_fmol_s"] / 3
            result["mobile_pump_dissipated_energy_pJ"][k, j] = rate["dissipation_pJ_s"]
            result["mobile_pump_metabolic_work_pJ"][k, j] = rate["chemical_input_power_pJ_s"]
            for s, key in ((na, "na_in_fmol_s"), (ka, "k_in_fmol_s")):
                inward = rate[key]
                result["amount_increment"][ions.index(s), i] += inward
                result["extracellular_amount_increment"][ions.index(s), o] -= inward
                result["chemical_amount_increment"][i, store.ids.index(s), store.cy] += inward
                balance += 1e-3 * inward * (R * p["temperature"] * math.log(ci[s] / co[s]) + F * vm)
            balance += rate["dissipation_pJ_s"] - rate["chemical_input_power_pJ_s"]
        for e, edge in enumerate(c["surface_edges"]):
            a, b = patches.index(edge["sender"]), patches.index(edge["receiver"])
            flow = (
                pop["diffusivity_um2_per_s"]
                * edge["width_um"]
                / edge["distance_um"]
                * (density[a] - density[b])
            )
            result["mobile_pump_amount_increment"][k, a] -= flow
            result["mobile_pump_amount_increment"][k, b] += flow
            result["mobile_pump_surface_transferred"][k, e] = flow
            if flow:
                result["mobile_pump_surface_dissipated_energy_pJ"][k, e] = (
                    1e-3 * R * p["temperature"] * flow * math.log(density[a] / density[b])
                )
    return (
        flatten(c, result),
        phi,
        proof
        | dict(
            mobile_pump_energy_balance_pJ_s=balance,
            physical_energy_balance_pJ_s=proof["physical_energy_balance_pJ_s"] + balance,
        ),
    )


def integrate(raw, *, refinement=1, channel_segments=None):
    c = bind(raw)
    e = raw["experiment"]
    segments = channel_segments or [(0.0, None)]
    events = {0.0, e["end_time"], *(time for time, _ in segments)}
    for kind, rows in e.items():
        if kind.endswith("_controls"):
            for row in rows:
                events.update(v["time"] for v in row.get("schedule", row.get("controls", [])))
    state = initial(c)
    saved, evaluations = {0.0: state.copy()}, 0
    atols = flatten(
        c,
        {
            k: np.full(shape, (5e-32 if k.endswith("_C") else 1e-16) / refinement)
            for k, shape in c["shapes"].items()
        },
    )
    for left, right in zip(sorted(events), sorted(events)[1:], strict=False):
        levels = next(level for time, level in reversed(segments) if time <= left)
        solution = solve_ivp(
            lambda t, y, held=left, opened=levels: evaluate(c, y, held, channel_levels=opened)[0],
            (left, right),
            state,
            method="DOP853",
            rtol=1e-12 / refinement,
            atol=atols,
            max_step=2.5e-6 / refinement,
            dense_output=True,
        )
        assert solution.success, solution.message
        evaluations += solution.nfev
        for t in e["observation_times"]:
            if left < t <= right:
                saved[t] = solution.sol(t)
        state = solution.y[:, -1]
    return dict(
        times=e["observation_times"],
        state=np.stack([saved[t] for t in e["observation_times"]]),
        potential_V=np.stack(
            [
                evaluate(
                    c,
                    saved[t],
                    t,
                    channel_levels=next(level for time, level in reversed(segments) if time <= t),
                )[1]
                for t in e["observation_times"]
            ]
        ),
        evaluations=evaluations,
        method="DOP853; Decimal ATPase/GHK/gates, scalar calcium/ER and full-node field",
        refinement=refinement,
    )
