"""Explicit internal organelle inventories and charge/heat in assembly reports."""

import numpy as np

from cells.processes import mitochondrial_passive as process
from cells.processes.electrochemistry import CHARGE_PER_FMOL

AXES = {
    "amount_fmol": ["world", "species", "cell"],
    "transferred_fmol": ["world", "species", "cell"],
    "dissipated_energy_pJ": ["world", "species", "cell"],
    "voltage_V": ["world", "cell"],
    "charge_C": ["world", "cell"],
    "stored_energy_change_pJ": ["world", "cell"],
}
METADATA = (
    "law",
    "source_law",
    "ids",
    "cell_ids",
    "species_ids",
    "valence",
    "axes",
    "initial_amount_fmol",
    "volume_pL",
    "capacitance_F",
    "initial_voltage_V",
    "fixed_charge_C",
)


def summary(spec, state, layout):
    from cells.models import surface_calcium_energy_mitochondria as model

    m, n = spec.ionic.model, len(spec.ionic.model.cells)
    voltage = model.mitochondrial_voltage(state.ionic, layout)[..., :n]
    return dict(
        law=process.LAW_ID,
        source_law=process.SOURCE_LAW,
        ids=[r.id for r in m.mitochondria],
        cell_ids=[r.cell_id for r in m.mitochondria],
        species_ids=list(m.species_ids),
        valence=list(m.valence),
        axes=AXES,
        initial_amount_fmol=layout.mitochondrial_initial_amount_fmol[:, :n].tolist(),
        volume_pL=layout.mitochondrial_volume_pL[:n].tolist(),
        capacitance_F=layout.mitochondrial_capacitance_F[:n].tolist(),
        initial_voltage_V=layout.mitochondrial_initial_voltage_V[:n].tolist(),
        fixed_charge_C=layout.mitochondrial_fixed_charge_C[:n].tolist(),
        amount_fmol=model.mitochondrial_amount(state.ionic, layout)[..., :n].tolist(),
        transferred_fmol=state.ionic.mitochondrial_transferred_fmol[..., :n].tolist(),
        dissipated_energy_pJ=state.ionic.mitochondrial_dissipated_energy_pJ[..., :n].tolist(),
        voltage_V=voltage.tolist(),
        charge_C=(layout.mitochondrial_capacitance_F[:n] * voltage).tolist(),
        stored_energy_change_pJ=model.stored_energy_change(state.ionic, layout)[..., :n].tolist(),
    )


def accumulate(arm, row):
    data = row.get("mitochondria", {})
    if any(k not in data for k in METADATA):
        raise ValueError("Missing mitochondrial ownership, initialization or physical ledgers")
    n, ns = len(row["cell_ids"]), len(data["species_ids"])
    initial = np.asarray(data["initial_amount_fmol"], dtype=float)
    volume, cap, v0, fixed = (
        np.asarray(data[k], dtype=float)
        for k in ("volume_pL", "capacitance_F", "initial_voltage_V", "fixed_charge_C")
    )
    z = np.asarray(data["valence"])
    if (
        data["law"] != process.LAW_ID
        or data["source_law"] != process.SOURCE_LAW
        or data["cell_ids"] != row["cell_ids"]
        or len(data["ids"]) != n
        or len(set(data["ids"])) != n
        or data["species_ids"] != row["calcium"]["species_ids"]
        or data["axes"] != AXES
        or initial.shape != (ns, n)
        or not np.isfinite(initial).all()
        or np.any(initial <= 0)
        or any(v.shape != (n,) or not np.isfinite(v).all() for v in (volume, cap, v0, fixed))
        or np.any(volume <= 0)
        or np.any(cap <= 0)
        or np.any(np.abs(v0) > process.MAX_VOLTAGE_V)
        or z.shape != (ns,)
        or z.dtype.kind not in "iu"
        or np.any(np.abs(z) > 8)
    ):
        raise ValueError("Invalid mitochondrial owners, geometry or initial inventory")
    expected_fixed = cap * v0 - CHARGE_PER_FMOL * np.sum(z[:, None] * initial, axis=0)
    if np.any(np.abs(fixed - expected_fixed) > 3e-25):
        raise ValueError("Mitochondrial fixed background disagrees with initial inventory")
    target = arm.setdefault("mitochondria", {k: data[k] for k in METADATA})
    if any(target[k] != data[k] for k in METADATA):
        raise ValueError("Mitochondrial ownership or initial physical state changed across worlds")
    sizes = dict(world=row["worlds"], species=ns, cell=n)
    arrays = {}
    for key, axes in AXES.items():
        value = np.asarray(data.get(key), dtype=float)
        if value.shape != tuple(sizes[a] for a in axes) or not np.isfinite(value).all():
            raise ValueError("Invalid mitochondrial value/shape: " + key)
        arrays[key] = value
    if (
        np.any(arrays["amount_fmol"] <= 0)
        or np.any(arrays["dissipated_energy_pJ"] < -1e-12)
        or np.any(np.abs(arrays["voltage_V"]) > process.MAX_VOLTAGE_V)
        or np.any(np.abs(arrays["amount_fmol"] - initial - arrays["transferred_fmol"]) > 2e-12)
        or np.any(np.abs(arrays["charge_C"] - cap * arrays["voltage_V"]) > 3e-25)
        or np.any(
            np.abs(
                cap * (arrays["voltage_V"] - v0)
                - CHARGE_PER_FMOL * np.sum(z[:, None] * arrays["transferred_fmol"], axis=-2)
            )
            > 3e-25
        )
    ):
        raise ValueError("Mitochondrial material, voltage, charge or heat ledger disagrees")
    for key, value in arrays.items():
        total = value.sum(axis=0)
        name = key + "_sum_over_worlds"
        target[name] = (np.asarray(target.get(name, np.zeros_like(total))) + total).tolist()
