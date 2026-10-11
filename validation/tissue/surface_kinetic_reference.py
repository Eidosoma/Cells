"""Independent scalar/Decimal kinetics, full-node roots and adaptive trajectories.

No Cells/JAX imports. The full-node root, capacitor derivative and material
assembly differ from the production reduced solver and scatter implementation.
"""

from decimal import Decimal, localcontext

import numpy as np
from scipy.integrate import solve_ivp

from validation.betse.pump_contact.pump_reference import oracle as pump_oracle
from validation.betse.voltage_gate_audit.gate_independent import kinetics as channel_kinetics
from validation.tissue import surface_dynamics_reference as base
from validation.tissue import surface_field_reference as electrical
from validation.tissue import surface_reference as transport

F, R = transport.F, transport.R
flatten, unpack = base.flatten, base.unpack


def bind(raw):
    c = base.bind(raw)
    m = raw["model"]
    nc, ne, nm = len(m["channels"]), len(m["junctions"]), len(m["membranes"])
    c["shapes"].update(
        channel_gate=(2, nc),
        channel_transferred=(nc,),
        channel_dissipated_energy_pJ=(nc,),
        junction_gate=(ne,),
        pump_cycles=(nm,),
        pump_dissipated_energy_pJ=(nm,),
        metabolic_work_pJ=(nm,),
    )
    return c


def initial(c):
    d = unpack(c, base.initial(c))
    d["channel_gate"] = (
        np.asarray([v["initial_gate"] for v in c["raw"]["model"]["channels"]]).reshape(-1, 2).T
    )
    d["junction_gate"] = np.asarray(
        [v["gate"]["initial_gate"] for v in c["raw"]["model"]["junctions"]]
    )
    return flatten(c, d)


def availability(c, kind, name, time):
    group = next(g for g in c["raw"]["experiment"][kind + "_controls"] if g[kind + "_id"] == name)
    return next(v["availability"] for v in reversed(group["schedule"]) if v["time"] <= time)


def evaluate(c, state, time, *, inside_amount=None, channel_levels=None):
    raw, d, m, p = base.stage(c, state, time), unpack(c, state), c["raw"]["model"], c["layout"]
    if inside_amount is not None:
        raw["ci"] = np.asarray(inside_amount) / c["vi"]
    raw["junction_open"] = np.asarray(raw["junction_open"]) * d["junction_gate"]
    phi, proof = electrical.solve(raw)
    n = len(c["qi"])
    rates = transport.transport(raw, phi[:n], phi[n:])
    result = {k: np.zeros(shape) for k, shape in c["shapes"].items()}
    for kind in ("membrane", "junction", "face"):
        result[kind + "_transferred"] = rates[kind + "_flux_fmol_s"].copy()
        result[kind + "_dissipated_energy_pJ"] = rates[kind + "_dissipation_pJ_s"].copy()
    cell, outside = rates["cell_rate_fmol_s"].copy(), rates["outside_rate_fmol_s"].copy()
    supply = rates["reservoir_supply_fmol_s"].copy()
    ids, mids = [v["id"] for v in m["species"]], [v["id"] for v in m["membranes"]]

    def transfer(species, patch, outward):
        i, o = p["membrane_cell"][patch], p["membrane_outside"][patch]
        cell[species, i] -= outward
        if p["reservoir"][o]:
            supply[species, o] -= outward
        else:
            outside[species, o] += outward

    for k, ch in enumerate(m["channels"]):
        j, s = mids.index(ch["membrane_id"]), ids.index(ch["species_id"])
        i, o = p["membrane_cell"][j], p["membrane_outside"][j]
        voltage = phi[i] - phi[n + o]
        with localcontext() as context:
            context.prec = 65
            target, tau = channel_kinetics(float(voltage))
            result["channel_gate"][:, k] = [
                (float(a) - g) / float(t)
                for a, t, g in zip(target, tau, d["channel_gate"][:, k], strict=True)
            ]
        flux = transport.decimal_flux(
            raw["ci"][s, i],
            raw["co"][s, o],
            voltage,
            p["valence"][s][0],
            p["temperature"],
            p["membrane_area"][j],
            ch["max_permeability_m_per_s"] * ch["abundance"],
            1.0,
            np.prod(d["channel_gate"][:, k])
            * availability(c, "channel", ch["id"], time)
            * (1.0 if channel_levels is None else channel_levels[i]),
            {"F": F, "R": R},
        )
        result["channel_transferred"][k] = flux
        result["channel_dissipated_energy_pJ"][k] = (
            1e-3 * flux * rates["membrane_delta_mu_J_mol"][s, j]
        )
        transfer(s, j, flux)
    for j, membrane in enumerate(m["membranes"]):
        pump = membrane["pump"]
        if pump is None:
            continue
        i, o = p["membrane_cell"][j], p["membrane_outside"][j]
        na, k = (ids.index(pump["roles"][r]) for r in ("sodium", "potassium"))
        meta = pump["metabolism"]
        case = dict(
            id=pump["id"],
            na_in_mM=float(raw["ci"][na, i]),
            na_out_mM=float(raw["co"][na, o]),
            k_in_mM=float(raw["ci"][k, i]),
            k_out_mM=float(raw["co"][k, o]),
            temperature_K=p["temperature"],
            area_m2=membrane["area_m2"],
            alpha_mol_m2_s=pump["capacity_fmol_per_s"] * 1e-15 / membrane["area_m2"],
            availability=availability(c, "pump", pump["id"], time),
            voltage_V=float(phi[i] - phi[n + o]),
            delta_g0_J_mol=meta["delta_g0_J_per_mol"],
            **{key: meta[key] for key in ("atp_mM", "adp_mM", "pi_mM")},
            **{key: pump[key] for key in ("km_na_mM", "km_k_mM", "km_atp_mM")},
        )
        value = pump_oracle(case, {"F": F, "R": R})
        result["pump_cycles"][j] = -value["na_in_fmol_s"] / 3
        result["pump_dissipated_energy_pJ"][j] = value["dissipation_pJ_s"]
        result["metabolic_work_pJ"][j] = value["chemical_input_power_pJ_s"]
        transfer(na, j, -value["na_in_fmol_s"])
        transfer(k, j, -value["k_in_fmol_s"])
    for j, route in enumerate(m["junctions"]):
        with localcontext() as context:
            context.prec = 65
            shift = Decimal(str(abs(rates["junction_voltage_V"][j]))) - Decimal(
                str(route["gate"]["threshold_voltage_V"])
            )
            alpha = Decimal("1.3") * (-77 * shift).exp()
            b = Decimal("0.0013") * (140 * shift).exp()
            beta = 1000 * b / (1 + 50 * b)
            g, minimum = (
                Decimal(str(d["junction_gate"][j])),
                Decimal(str(route["gate"]["minimum_open_fraction"])),
            )
            result["junction_gate"][j] = float(alpha * (1 - g) - beta * (g - minimum))
    matrix, active, reservoir, fixed, floating, _ = electrical.topology(raw)
    pins = ~active | reservoir
    for members in floating:
        pins[members[0]] = True
    free = np.flatnonzero(~pins)
    ionic = 1e-15 * F * (np.asarray(p["valence"]).T @ np.c_[cell, outside])[0]
    derivative = np.zeros_like(phi)
    derivative[free] = np.linalg.solve(matrix[np.ix_(free, free)], ionic[free])
    np.testing.assert_allclose(
        (matrix @ derivative)[active & ~reservoir],
        ionic[active & ~reservoir],
        rtol=2e-12,
        atol=2e-23,
    )
    electrode = np.where(p["reservoir"], (matrix @ derivative)[n:], 0.0)
    mu = R * p["temperature"] * np.log(raw["co"]) + F * np.asarray(p["valence"]) * phi[n:]
    result.update(
        amount_increment=cell,
        extracellular_amount_increment=outside,
        reservoir_supplied=supply,
        electrode_charge_transferred_C=electrode,
        reservoir_work_pJ=1e-3 * np.sum(mu * supply, axis=0),
        electrode_work_pJ=1e12 * phi[n:] * electrode,
    )
    return flatten(c, result), phi, proof


def integrate(raw):
    c, e = bind(raw), raw["experiment"]
    events = sorted(
        {
            0.0,
            e["end_time"],
            *(
                p["time"]
                for kind in ("membrane", "junction", "channel", "pump")
                for group in e[kind + "_controls"]
                for p in group["schedule"]
            ),
        }
    )
    times, state, evaluations = e["observation_times"], initial(c), 0
    result = {0.0: state.copy()}
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
    return dict(
        times=times,
        state=np.stack([result[t] for t in times]).tolist(),
        potential_V=np.stack([evaluate(c, result[t], t)[1] for t in times]).tolist(),
        rhs_evaluations=evaluations,
        method="DOP853, full-node roots, Decimal transport/gates/pumps",
        rtol=2e-11,
        amount_energy_gate_atol=2e-14,
        electrode_charge_atol_C=1e-29,
    )
