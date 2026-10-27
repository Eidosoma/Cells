"""Owned mobile-channel inventories and ledgers in assembly-cluster reports."""

import numpy as np

from cells.models.surface_mobile_repair import EXTRA_AXES
from cells.processes.mobile_channel_gates import STATE_IDS, TRANSITION_IDS

AXES = {
    name: [
        "world",
        *(axis.replace("_slot", "").replace("membrane", "membrane_patch") for axis in axes),
    ]
    for name, axes in EXTRA_AXES.items()
} | {"amount_fmol": ["world", "channel_population", "joint_gate_state", "membrane_patch"]}
METADATA = (
    "population_ids",
    "species_ids",
    "kinetic_laws",
    "patch_ids",
    "patch_cell_ids",
    "surface_edge_ids",
    "surface_edge_senders",
    "surface_edge_receivers",
    "joint_state_ids",
    "transition_ids",
    "cell_ids",
    "initial_total_by_cell_fmol",
    "axes",
    "protein_pool_exchange",
    "gating_energy_scope",
)
ENERGY_SCOPE = "phenomenological ideal-mixture/rate-bias accounting; no resolved gating charge"


def summary(spec, state, layout):
    m = spec.ionic.model
    patches = [p.id for p in m.membranes]
    owners = [p.inside for p in m.membranes]
    cells = [p.cell_id for p in spec.pools]
    sizes = {
        "channel_population": len(m.mobile_channels),
        "joint_gate_state": 4,
        "gate_transition": 4,
        "membrane_patch": len(patches),
        "surface_edge": len(m.surface_edges),
    }
    initial = np.asarray(layout.channel_state_reference)[
        : len(m.mobile_channels), :, : len(patches)
    ]
    amounts = layout.channel_state_reference + state.ionic.channel_state_amount_increment
    row = {
        "population_ids": [p.id for p in m.mobile_channels],
        "species_ids": [p.species_id for p in m.mobile_channels],
        "kinetic_laws": [p.kinetic_law for p in m.mobile_channels],
        "patch_ids": patches,
        "patch_cell_ids": owners,
        "cell_ids": cells,
        "surface_edge_ids": [e.id for e in m.surface_edges],
        "surface_edge_senders": [e.sender for e in m.surface_edges],
        "surface_edge_receivers": [e.receiver for e in m.surface_edges],
        "joint_state_ids": list(STATE_IDS),
        "transition_ids": list(TRANSITION_IDS),
        "initial_total_by_cell_fmol": np.stack(
            [initial[:, :, np.asarray(owners) == cell].sum(axis=(1, 2)) for cell in cells], axis=-1
        ).tolist(),
        "axes": AXES,
        "protein_pool_exchange": "none",
        "gating_energy_scope": ENERGY_SCOPE,
    }
    for name, axes in AXES.items():
        value = amounts if name == "amount_fmol" else getattr(state.ionic, name)
        index = (slice(None), *(slice(sizes[a]) for a in axes[1:]))
        row[name] = np.asarray(value)[index].tolist()
    return row


def accumulate(arm, row):
    data = row.get("mobile_channels", {})
    if any(k not in data for k in METADATA):
        raise ValueError("Incomplete mobile-channel ownership")
    populations, patches, cells = data["population_ids"], data["patch_ids"], data["cell_ids"]
    owners, edges = data["patch_cell_ids"], data["surface_edge_ids"]
    if (
        not populations
        or len(set(populations)) != len(populations)
        or patches != row["voltage_owner_ids"]
        or len(set(patches)) != len(patches)
        or cells != row["cell_ids"]
        or owners != row["injury"]["cell_ids"]
        or len(owners) != len(patches)
        or not set(owners) <= set(cells)
        or data["species_ids"] != ["K"] * len(populations)
        or data["kinetic_laws"] != ["betse_kv1p5_mh@1"] * len(populations)
        or data["joint_state_ids"] != list(STATE_IDS)
        or data["transition_ids"] != list(TRANSITION_IDS)
        or data["axes"] != AXES
        or data["protein_pool_exchange"] != "none"
        or data["gating_energy_scope"] != ENERGY_SCOPE
        or len(set(edges)) != len(edges)
        or len(data["surface_edge_senders"]) != len(edges)
        or len(data["surface_edge_receivers"]) != len(edges)
    ):
        raise ValueError("Invalid mobile-channel axes, owners or laws")
    owner_by_patch = dict(zip(patches, owners, strict=True))
    for a, b in zip(data["surface_edge_senders"], data["surface_edge_receivers"], strict=True):
        if (
            a == b
            or a not in owner_by_patch
            or b not in owner_by_patch
            or owner_by_patch[a] != owner_by_patch[b]
        ):
            raise ValueError("Invalid mobile-channel surface edge ownership")
    initial = np.asarray(data["initial_total_by_cell_fmol"], dtype=float)
    if (
        initial.shape != (len(populations), len(cells))
        or not np.isfinite(initial).all()
        or np.any(initial < 0)
    ):
        raise ValueError("Invalid mobile-channel initial inventory")
    sizes = {
        "world": row["worlds"],
        "channel_population": len(populations),
        "joint_gate_state": 4,
        "gate_transition": 4,
        "membrane_patch": len(patches),
        "surface_edge": len(edges),
    }
    target = arm.setdefault("mobile_channels", {k: data[k] for k in METADATA})
    if any(target[k] != data[k] for k in METADATA):
        raise ValueError("Mobile-channel ownership or laws changed")
    for name, axes in AXES.items():
        values = np.asarray(data.get(name), dtype=float)
        if (
            values.shape != tuple(sizes[a] for a in axes)
            or not np.isfinite(values).all()
            or (name == "amount_fmol" and np.any(values < 0))
            or (name.endswith("_dissipated_energy_pJ") and np.any(values < -1e-12))
        ):
            raise ValueError("Invalid mobile-channel state shape or domain: " + name)
        if name == "amount_fmol":
            for i, cell in enumerate(cells):
                total = values[..., np.asarray(owners) == cell].sum(axis=(2, 3))
                if np.max(np.abs(total - initial[:, i]), initial=0) > 2e-13:
                    raise ValueError("Mobile-channel inventory is not conserved by cell")
        total = values.sum(axis=0)
        key = name + "_sum_over_worlds"
        target[key] = (np.asarray(target.get(key, np.zeros_like(total))) + total).tolist()
