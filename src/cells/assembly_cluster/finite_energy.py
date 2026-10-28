"""Keep cellular fuel ownership and supply ledgers in assembly reports."""

import numpy as np

from cells.processes import finite_energy as energy

METADATA = ("law", "species", "pool_ids", "cell_ids", "port_ids", "port_pool_ids", "axes")
AXES = {
    "amount_fmol": ["world", "energy_species", "cell"],
    "regeneration_cycles_fmol": ["world", "port"],
    "regeneration_dissipated_energy_pJ": ["world", "port"],
    "regeneration_supplied_work_pJ": ["world", "port"],
}


def summary(spec, state, layout):
    m = spec.ionic.model
    row = dict(
        law=energy.LAW_ID,
        species=list(energy.SPECIES),
        pool_ids=[p.id for p in m.energy_pools],
        cell_ids=[p.cell_id for p in m.energy_pools],
        port_ids=[p.id for p in m.regeneration_ports],
        port_pool_ids=[p.pool_id for p in m.regeneration_ports],
        axes=AXES,
        amount_fmol=(layout.energy_initial_amount_fmol + state.ionic.energy_amount_increment_fmol)[
            ..., : len(m.cells)
        ].tolist(),
    )
    for key in tuple(AXES)[1:]:
        row[key] = getattr(state.ionic, key)[..., : len(m.regeneration_ports)].tolist()
    return row


def accumulate(arm, row):
    data = row.get("finite_energy", {})
    if any(key not in data for key in METADATA):
        raise ValueError("Missing finite cellular fuel owners or ledgers")
    if (
        data["law"] != energy.LAW_ID
        or data["species"] != list(energy.SPECIES)
        or data["axes"] != AXES
        or data["cell_ids"] != row["cell_ids"]
        or len(data["pool_ids"]) != len(row["cell_ids"])
        or len(set(data["pool_ids"])) != len(data["pool_ids"])
        or len(set(data["port_ids"])) != len(data["port_ids"])
        or len(data["port_pool_ids"]) != len(data["port_ids"])
        or not set(data["port_pool_ids"]) <= set(data["pool_ids"])
    ):
        raise ValueError("Invalid finite cellular fuel ownership or axes")
    target = arm.setdefault("finite_energy", {k: data[k] for k in METADATA})
    if any(target[k] != data[k] for k in METADATA):
        raise ValueError("Finite cellular fuel ownership changed across worlds")
    sizes = dict(
        world=row["worlds"], energy_species=3, cell=len(row["cell_ids"]), port=len(data["port_ids"])
    )
    for key, axes in AXES.items():
        values = np.asarray(data.get(key), dtype=float)
        if (
            values.shape != tuple(sizes[a] for a in axes)
            or not np.isfinite(values).all()
            or (key == "amount_fmol" and np.any(values <= 0))
            or (key.endswith("dissipated_energy_pJ") and np.any(values < -1e-12))
        ):
            raise ValueError("Invalid finite cellular fuel value: " + key)
        total = values.sum(axis=0)
        name = key + "_sum_over_worlds"
        target[name] = (np.asarray(target.get(name, np.zeros_like(total))) + total).tolist()
