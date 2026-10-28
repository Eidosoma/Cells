"""Retain native transport ownership and external work in ensemble reports."""

import numpy as np

from cells.core.surface_calcium_energy_transport_spec import ACCOUNTING
from cells.processes.betse_network_transport import LAW_ID
from cells.processes.electrochemistry import F, R

AXES = {
    "cycles_fmol": ["world", "route"],
    "transferred_fmol": ["world", "species", "route"],
    "dissipated_energy_pJ": ["world", "route"],
    "supplied_work_pJ": ["world", "route"],
}
METADATA = (
    "law",
    "accounting",
    "constants",
    "route_ids",
    "membrane_ids",
    "inside_ids",
    "outside_ids",
    "species_ids",
    "outward_stoichiometry",
    "supplied_energy_J_mol",
    "axes",
)


def summary(spec, state, layout):
    m = spec.ionic.model
    routes = m.network_transporters
    patches = {p.id: p for p in m.membranes}
    row = dict(
        law=LAW_ID,
        accounting=ACCOUNTING,
        constants=dict(faraday_C_mol=F, gas_constant_J_mol_K=R),
        route_ids=[r.id for r in routes],
        membrane_ids=[r.membrane_id for r in routes],
        inside_ids=[patches[r.membrane_id].inside for r in routes],
        outside_ids=[patches[r.membrane_id].outside for r in routes],
        species_ids=list(m.species_ids),
        outward_stoichiometry=layout.network_stoichiometry[:, : len(routes)].tolist(),
        supplied_energy_J_mol=layout.network_supplied_energy_J_mol[: len(routes)].tolist(),
        axes=AXES,
    )
    row.update({k: getattr(state.ionic, "network_" + k)[..., : len(routes)].tolist() for k in AXES})
    return row


def accumulate(arm, row):
    data = row.get("network_transport", {})
    if any(k not in data for k in METADATA):
        raise ValueError("Missing configured transporter owners, constants or ledgers")
    count = len(data["route_ids"])
    species = data["species_ids"]
    nu = np.asarray(data["outward_stoichiometry"], dtype=float)
    supply = np.asarray(data["supplied_energy_J_mol"], dtype=float)
    if (
        data["law"] != LAW_ID
        or data["accounting"] != ACCOUNTING
        or data["constants"] != dict(faraday_C_mol=F, gas_constant_J_mol_K=R)
        or data["axes"] != AXES
        or len(set(data["route_ids"])) != count
        or any(len(data[k]) != count for k in ("membrane_ids", "inside_ids", "outside_ids"))
        or not set(data["membrane_ids"]) <= set(row["voltage_owner_ids"])
        or not set(data["inside_ids"]) <= set(row["cell_ids"])
        or species != row["calcium"]["species_ids"]
        or nu.shape != (len(species), count)
        or not np.isfinite(nu).all()
        or np.any(~np.any(nu != 0, axis=0))
        or supply.shape != (count,)
        or not np.isfinite(supply).all()
    ):
        raise ValueError("Invalid configured transporter ownership or energetic contract")
    target = arm.setdefault("network_transport", {k: data[k] for k in METADATA})
    if any(target[k] != data[k] for k in METADATA):
        raise ValueError("Configured transport contract changed across worlds")
    sizes = dict(world=row["worlds"], species=len(species), route=count)
    arrays = {}
    for key, axes in AXES.items():
        value = np.asarray(data.get(key), dtype=float)
        if (
            value.shape != tuple(sizes[a] for a in axes)
            or not np.isfinite(value).all()
            or (key == "dissipated_energy_pJ" and np.any(value < -1e-12))
        ):
            raise ValueError("Invalid configured transporter value: " + key)
        arrays[key] = value
    if np.any(
        np.abs(arrays["transferred_fmol"] - nu * arrays["cycles_fmol"][:, None, :]) > 2e-12
    ) or np.any(np.abs(arrays["supplied_work_pJ"] - 1e-3 * supply * arrays["cycles_fmol"]) > 3e-12):
        raise ValueError("Configured transporter material or supplied-work ledger disagrees")
    for key, value in arrays.items():
        total = value.sum(axis=0)
        name = key + "_sum_over_worlds"
        target[name] = (np.asarray(target.get(name, np.zeros_like(total))) + total).tolist()
