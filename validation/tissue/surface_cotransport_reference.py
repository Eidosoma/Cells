"""Independent finite-energy tissue plus scalar/Decimal neutral cotransport.

No production Cells/JAX imports or schema helpers. Raw role/owner projections
and both material sides are reconstructed independently from declarations.
"""

from copy import deepcopy

import numpy as np
from scipy.integrate import solve_ivp

from validation.tissue import surface_energy_reference as energy
from validation.transport import cotransport_reference as transport

F, R = energy.F, energy.R
flatten, unpack = energy.flatten, energy.unpack
CONTROL_KINDS = (*energy.CONTROL_KINDS, "cotransport")
EXTRA_FIELDS = (
    "cotransport_cycles_fmol",
    "cotransport_transferred_fmol",
    "cotransport_dissipated_energy_pJ",
)


def bind(raw):
    if raw["model"]["id"] != "resolved_cotransport@1":
        raise ValueError("Require resolved_cotransport@1")
    projected = deepcopy(raw)
    projected["model"]["id"] = "resolved_energy@1"
    routes = projected["model"].pop("cotransporters")
    projected["experiment"].pop("cotransport_controls")
    projected["execution"].pop("cotransport_capacity")
    base = energy.bind(projected)
    m = raw["model"]
    species = [v["id"] for v in m["species"]]
    cells = [v["id"] for v in m["cells"]]
    outside = [v["id"] for v in m["extracellular"]]
    patches = {v["id"]: v for v in m["membranes"]}
    nu = np.zeros((len(species), len(routes)), np.int64)
    inside_owners, outside_owners = [], []
    for j, route in enumerate(routes):
        if route["law"] == "kcc_reversible_tanh@1":
            roles = {"potassium": (1, 1), "chloride": (-1, 1)}
        elif route["law"] == "nkcc_reversible_tanh@1":
            roles = {"sodium": (1, 1), "potassium": (1, 1), "chloride": (-1, 2)}
        else:
            raise ValueError("Unsupported manufactured cotransport law")
        refs = route["roles"]
        if set(refs) != set(roles) or len(set(refs.values())) != len(refs):
            raise ValueError("Cotransport role names must be unique and explicit")
        for role, (valence, coefficient) in roles.items():
            i = species.index(refs[role])
            if m["species"][i]["valence"] != valence:
                raise ValueError("Incorrect actual species valence")
            nu[i, j] = coefficient
        patch = patches[route["membrane_id"]]
        inside_owners.append(cells.index(patch["inside"]))
        outside_owners.append(len(cells) + outside.index(patch["outside"]))
    return dict(
        base,
        raw=deepcopy(raw),
        energy=base,
        cotransport_nu=nu,
        cotransport_inside=inside_owners,
        cotransport_outside=outside_owners,
        shapes=base["shapes"]
        | dict(
            cotransport_cycles_fmol=(len(routes),),
            cotransport_transferred_fmol=(len(species), len(routes)),
            cotransport_dissipated_energy_pJ=(len(routes),),
        ),
    )


def initial(c):
    d = unpack(c["energy"], energy.initial(c["energy"]))
    d.update({key: np.zeros(c["shapes"][key]) for key in EXTRA_FIELDS})
    return flatten(c, d)


def evaluate(c, state, time):
    d = unpack(c, state)
    slope, phi, proof = energy.evaluate(c["energy"], flatten(c["energy"], d), time)
    result = unpack(c["energy"], slope)
    amounts = np.c_[c["ai"] + d["amount_increment"], c["ao"] + d["extracellular_amount_increment"]]
    if not np.isfinite(amounts).all() or np.any(amounts <= 0):
        raise ValueError(
            "Positive finite ionic substrates required even when cotransport is blocked"
        )
    volumes = np.r_[c["vi"], c["vo"]]
    concentrations = amounts / volumes
    routes = c["raw"]["model"]["cotransporters"]
    count = len(routes)
    cycles, heat = np.zeros(count), np.zeros(count)
    transferred = np.zeros((amounts.shape[0], count))
    temperature = c["raw"]["model"]["temperature_K"]
    for j, route in enumerate(routes):
        i, o = c["cotransport_inside"][j], c["cotransport_outside"][j]
        level = energy.ionic.availability(c, "cotransport", route["id"], time)
        value = transport.cycle(
            concentrations[:, i].tolist(),
            concentrations[:, o].tolist(),
            c["cotransport_nu"][:, j].tolist(),
            route["capacity_fmol_per_s"],
            level,
            temperature,
        )
        cycles[j], heat[j] = value["cycle_fmol_s"], value["dissipated_power_pJ_s"]
        transferred[:, j] = value["transported_fmol_s"]
    exchanged = np.asarray(
        transport.exchange(
            cycles.tolist(),
            c["cotransport_inside"],
            c["cotransport_outside"],
            c["cotransport_nu"].tolist(),
            amounts.shape[-1],
        )
    )
    n = len(c["cell_ids"])
    result["amount_increment"] += exchanged[:, :n]
    result["extracellular_amount_increment"] += exchanged[:, n:]
    result.update(
        cotransport_cycles_fmol=cycles,
        cotransport_transferred_fmol=transferred,
        cotransport_dissipated_energy_pJ=heat,
    )
    # Independent chemical derivative from actual owner material, not -heat assignment.
    chemical = 1e-3 * R * temperature * np.sum(np.log(concentrations) * exchanged)
    ionic_chemical = proof["ionic_chemical_power_pJ_s"] + chemical
    total_heat = proof["ionic_dissipation_pJ_s"] + np.sum(heat)
    balance = (
        ionic_chemical
        + proof["capacitor_power_pJ_s"]
        + proof["pool_chemical_power_pJ_s"]
        + total_heat
        + proof["regeneration_dissipation_pJ_s"]
        - proof["regeneration_supply_pJ_s"]
    )
    valence = np.array([v["valence"] for v in c["raw"]["model"]["species"]])
    return (
        flatten(c, result),
        phi,
        proof
        | dict(
            physical_energy_balance_pJ_s=float(balance),
            ionic_chemical_power_pJ_s=float(ionic_chemical),
            ionic_dissipation_pJ_s=float(total_heat),
            cotransport_chemical_power_pJ_s=float(chemical),
            cotransport_dissipation_pJ_s=float(np.sum(heat)),
            cotransport_cycle_fmol_s=cycles.tolist(),
            cotransport_charge_rate_C_s=(1e-15 * F * (valence @ exchanged)).tolist(),
        ),
    )


def integrate(raw, *, refinement=1):
    """Independent six-clock DOP853 reference; coordinator owns trajectory runs."""
    if type(refinement) is not int or refinement < 1:
        raise ValueError("Reference refinement must be a positive integer")
    c, e = bind(raw), raw["experiment"]
    events = sorted(
        {
            0.0,
            e["end_time"],
            *(
                v["time"]
                for kind in CONTROL_KINDS
                for group in e[kind + "_controls"]
                for v in group["schedule"]
            ),
        }
    )
    state = initial(c)
    saved, evaluations = {0.0: state.copy()}, 0
    atol = flatten(
        c,
        {
            key: np.full(shape, (1e-29 if key.endswith("_C") else 2e-14) / refinement)
            for key, shape in c["shapes"].items()
        },
    )
    for left, right in zip(events, events[1:], strict=False):
        solution = solve_ivp(
            lambda t, y, held=left: evaluate(c, y, held)[0],
            (left, right),
            state,
            method="DOP853",
            rtol=2e-11 / refinement,
            atol=atol,
            max_step=1.25e-6 / refinement,
            dense_output=True,
        )
        if not solution.success:
            raise RuntimeError(solution.message)
        evaluations += solution.nfev
        for time in e["observation_times"]:
            if left < time <= right:
                saved[time] = solution.sol(time)
        state = solution.y[:, -1]
    return dict(
        times=e["observation_times"],
        state=np.stack([saved[t] for t in e["observation_times"]]),
        potential_V=np.stack([evaluate(c, saved[t], t)[1] for t in e["observation_times"]]),
        evaluations=evaluations,
        refinement=refinement,
        rtol=2e-11 / refinement,
        amount_energy_gate_atol=2e-14 / refinement,
        electrode_charge_atol_C=1e-29 / refinement,
        max_step_s=1.25e-6 / refinement,
        event_times=events,
        method="DOP853; full-node/finite-energy reference plus independent 80-digit cotransport",
    )
