"""Independent neutral cotransport on finite-energy compliant compartments.

No Cells/JAX imports or production projections. Positive route cycles carry
declared stoichiometric ions outside-to-inside. Current amounts and volumes
drive both cotransport and the existing water/finite-energy reference.
"""

from copy import deepcopy
from numbers import Real

import numpy as np

from validation.tissue import surface_energy_water_reference as water_energy
from validation.transport import cotransport_reference as transport

F, R = water_energy.F, water_energy.R
flatten, unpack = water_energy.flatten, water_energy.unpack
MODEL_ID = "resolved_cotransport_water@1"
CONTROL_KINDS = (*water_energy.CONTROL_KINDS, "cotransport")
EXTRA_FIELDS = (
    "cotransport_cycles_fmol",
    "cotransport_transferred_fmol",
    "cotransport_dissipated_energy_pJ",
)


def bind(raw):
    if raw["model"]["id"] != MODEL_ID:
        raise ValueError("Require resolved_cotransport_water@1")
    projected = deepcopy(raw)
    projected["model"]["id"] = water_energy.MODEL_ID
    routes = projected["model"].pop("cotransporters")
    schedules = projected["experiment"].pop("cotransport_controls")
    projected["execution"].pop("cotransport_capacity")
    base = water_energy.bind(projected)
    m = raw["model"]
    species = [row["id"] for row in m["species"]]
    cells = [row["id"] for row in m["cells"]]
    outside = [row["id"] for row in m["extracellular"]]
    patches = {row["id"]: row for row in m["membranes"]}
    names = set()
    nu = np.zeros((len(species), len(routes)), dtype=np.int64)
    inside, exterior = [], []
    for j, route in enumerate(routes):
        name, capacity = route["id"], route["capacity_fmol_per_s"]
        if (
            not isinstance(name, str)
            or not name
            or name in names
            or route["membrane_id"] not in patches
            or isinstance(capacity, bool)
            or not isinstance(capacity, Real)
            or not np.isfinite(capacity)
            or capacity < 0
        ):
            raise ValueError(
                "Cotransport requires unique IDs, declared membranes and finite capacity"
            )
        names.add(name)
        if route["law"] == "kcc_reversible_tanh@1":
            roles = {"potassium": (1, 1), "chloride": (-1, 1)}
        elif route["law"] == "nkcc_reversible_tanh@1":
            roles = {"sodium": (1, 1), "potassium": (1, 1), "chloride": (-1, 2)}
        else:
            raise ValueError("Unsupported manufactured cotransport law")
        refs = route["roles"]
        if set(refs) != set(roles) or len(set(refs.values())) != len(refs):
            raise ValueError("Cotransport roles must be distinct and explicit")
        for role, (valence, coefficient) in roles.items():
            i = species.index(refs[role])
            if m["species"][i]["valence"] != valence:
                raise ValueError("Cotransport role has the wrong actual species valence")
            nu[i, j] = coefficient
        patch = patches[route["membrane_id"]]
        inside.append(cells.index(patch["inside"]))
        exterior.append(len(cells) + outside.index(patch["outside"]))
    controls = {}
    for group in schedules:
        name, rows = group["cotransport_id"], group["schedule"]
        if name in controls or not rows:
            raise ValueError("Duplicate or empty cotransport schedule")
        times = np.asarray([row["time"] for row in rows])
        levels = np.asarray([row["availability"] for row in rows])
        if (
            not np.isfinite(times).all()
            or times[0] != 0
            or np.any(np.diff(times) <= 0)
            or times[-1] > raw["experiment"]["end_time"]
            or not np.isfinite(levels).all()
            or np.any((levels < 0) | (levels > 1))
        ):
            raise ValueError("Invalid right-continuous cotransport schedule")
        controls[name] = deepcopy(rows)
    if set(controls) != names:
        raise ValueError("Cotransport controls must exactly match route owners")
    return dict(
        base,
        raw=deepcopy(raw),
        water_energy=base,
        cotransport_nu=nu,
        cotransport_inside=inside,
        cotransport_outside=exterior,
        cotransport_controls=[controls[row["id"]] for row in routes],
        shapes=base["shapes"]
        | dict(
            cotransport_cycles_fmol=(len(routes),),
            cotransport_transferred_fmol=(len(species), len(routes)),
            cotransport_dissipated_energy_pJ=(len(routes),),
        ),
    )


def initial(c):
    d = unpack(c["water_energy"], water_energy.initial(c["water_energy"]))
    d.update({name: np.zeros(c["shapes"][name]) for name in EXTRA_FIELDS})
    return flatten(c, d)


def evaluate(c, state, time):
    if not np.isfinite(state).all():
        raise ValueError("Complete cotransport/water reference state must be finite")
    d = unpack(c, state)
    slope, phi, proof = water_energy.evaluate(
        c["water_energy"], flatten(c["water_energy"], d), time
    )
    result = unpack(c["water_energy"], slope)
    amount = np.c_[c["ai"] + d["amount_increment"], c["ao"] + d["extracellular_amount_increment"]]
    volume = np.r_[
        c["vi"] + d["volume_increment_pL"],
        c["vo"] + d["extracellular_volume_increment_pL"],
    ]
    concentration = amount / volume
    routes = c["raw"]["model"]["cotransporters"]
    cycles, affinity, heat = (np.zeros(len(routes)) for _ in range(3))
    moved = np.zeros((amount.shape[0], len(routes)))
    temperature = c["raw"]["model"]["temperature_K"]
    for j, route in enumerate(routes):
        i, o = c["cotransport_inside"][j], c["cotransport_outside"][j]
        level = next(
            row["availability"]
            for row in reversed(c["cotransport_controls"][j])
            if row["time"] <= time
        )
        values = transport.cycle(
            concentration[:, i].tolist(),
            concentration[:, o].tolist(),
            c["cotransport_nu"][:, j].tolist(),
            route["capacity_fmol_per_s"],
            level,
            temperature,
        )
        cycles[j] = values["cycle_fmol_s"]
        affinity[j] = values["affinity_J_mol"]
        heat[j] = values["dissipated_power_pJ_s"]
        moved[:, j] = values["transported_fmol_s"]
    exchanged = np.asarray(
        transport.exchange(
            cycles.tolist(),
            c["cotransport_inside"],
            c["cotransport_outside"],
            c["cotransport_nu"].tolist(),
            amount.shape[-1],
        )
    )
    n = len(c["vi"])
    result["amount_increment"] += exchanged[:, :n]
    result["extracellular_amount_increment"] += exchanged[:, n:]
    result.update(
        cotransport_cycles_fmol=cycles,
        cotransport_transferred_fmol=moved,
        cotransport_dissipated_energy_pJ=heat,
    )
    chemical = 1e-3 * R * temperature * np.sum(np.log(concentration) * exchanged)
    valence = np.asarray([row["valence"] for row in c["raw"]["model"]["species"]])
    return (
        flatten(c, result),
        phi,
        proof
        | dict(
            physical_energy_balance_pJ_s=float(
                proof["physical_energy_balance_pJ_s"] + chemical + heat.sum()
            ),
            ionic_chemical_power_pJ_s=float(proof["ionic_chemical_power_pJ_s"] + chemical),
            ionic_dissipation_pJ_s=float(proof["ionic_dissipation_pJ_s"] + heat.sum()),
            cotransport_chemical_power_pJ_s=float(chemical),
            cotransport_dissipation_pJ_s=float(heat.sum()),
            cotransport_affinity_J_mol=affinity.tolist(),
            cotransport_cycle_fmol_s=cycles.tolist(),
            cotransport_route_charge_C_s=(
                1e-15 * F * (valence @ c["cotransport_nu"]) * cycles
            ).tolist(),
            cotransport_charge_rate_C_s=(1e-15 * F * (valence @ exchanged)).tolist(),
        ),
    )
