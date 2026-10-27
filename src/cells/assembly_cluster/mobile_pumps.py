"""Owned mobile ATPase inventories, transported ions and ATP work in cluster reports."""

import numpy as np

from cells.models.surface_mobile_pump_repair import EXTRA_AXES

AXES = {
    name: [
        "world",
        *(axis.replace("_slot", "").replace("membrane", "membrane_patch") for axis in axes),
    ]
    for name, axes in EXTRA_AXES.items()
} | {
    "amount_fmol": ["world", "pump_population", "membrane_patch"],
    "outward_ion_transfer_fmol": ["world", "species", "pump_population", "membrane_patch"],
}
METADATA = (
    "population_ids",
    "kinetic_laws",
    "species_ids",
    "roles",
    "stoichiometry",
    "patch_ids",
    "patch_cell_ids",
    "cell_ids",
    "surface_edge_ids",
    "surface_edge_senders",
    "surface_edge_receivers",
    "initial_amount_fmol",
    "initial_total_by_cell_fmol",
    "work_per_cycle_pJ_per_fmol",
    "axes",
    "protein_pool_exchange",
    "assembly_coupling",
    "metabolic_scope",
)
COUPLING = "assembly modulates channel conduction; pump controls remain independent"
METABOLISM = "maintained ATP/ADP/Pi reservoirs; signed cycle and work accounting"


def summary(spec, state, layout):
    m = spec.ionic.model
    patches = [p.id for p in m.membranes]
    owners = [p.inside for p in m.membranes]
    cells = [p.cell_id for p in spec.pools]
    sizes = dict(
        pump_population=len(m.mobile_pumps),
        membrane_patch=len(patches),
        surface_edge=len(m.surface_edges),
        species=len(m.species_ids),
    )
    initial = np.asarray(layout.mobile_pump_reference)[: len(m.mobile_pumps), : len(patches)]
    row = dict(
        population_ids=[p.id for p in m.mobile_pumps],
        kinetic_laws=[p.law for p in m.mobile_pumps],
        species_ids=list(m.species_ids),
        roles=[dict(zip(("sodium", "potassium"), p.roles, strict=True)) for p in m.mobile_pumps],
        stoichiometry=np.asarray(layout.mobile_pump_stoichiometry)[
            :, : len(m.mobile_pumps)
        ].tolist(),
        patch_ids=patches,
        patch_cell_ids=owners,
        cell_ids=cells,
        surface_edge_ids=[e.id for e in m.surface_edges],
        surface_edge_senders=[e.sender for e in m.surface_edges],
        surface_edge_receivers=[e.receiver for e in m.surface_edges],
        initial_amount_fmol=initial.tolist(),
        initial_total_by_cell_fmol=np.stack(
            [initial[:, np.asarray(owners) == cell].sum(axis=1) for cell in cells], axis=-1
        ).tolist(),
        work_per_cycle_pJ_per_fmol=(
            -1e-3 * np.asarray(layout.mobile_pump_drive)[: len(m.mobile_pumps), 0]
        ).tolist(),
        axes=AXES,
        protein_pool_exchange="none",
        assembly_coupling=COUPLING,
        metabolic_scope=METABOLISM,
    )
    derived = dict(
        amount_fmol=layout.mobile_pump_reference + state.ionic.mobile_pump_amount_increment,
        outward_ion_transfer_fmol=-np.asarray(layout.mobile_pump_stoichiometry)[None, :, :, None]
        * np.asarray(state.ionic.mobile_pump_cycles)[:, None, :, :],
    )
    for name, axes in AXES.items():
        value = derived[name] if name in derived else getattr(state.ionic, name)
        row[name] = np.asarray(value)[(slice(None), *(slice(sizes[a]) for a in axes[1:]))].tolist()
    return row


def accumulate(arm, row):
    data = row.get("mobile_pumps", {})
    if any(k not in data for k in METADATA):
        raise ValueError("Incomplete mobile-pump ownership")
    populations, patches, cells = data["population_ids"], data["patch_ids"], data["cell_ids"]
    owners, edges, species = data["patch_cell_ids"], data["surface_edge_ids"], data["species_ids"]
    if (
        not populations
        or len(set(populations)) != len(populations)
        or patches != row["voltage_owner_ids"]
        or len(set(patches)) != len(patches)
        or cells != row["cell_ids"]
        or owners != row["injury"]["cell_ids"]
        or len(owners) != len(patches)
        or not set(owners) <= set(cells)
        or species != row["calcium"]["species_ids"]
        or len(set(species)) != len(species)
        or data["kinetic_laws"] != ["nak_atp_mass_action_positive@1"] * len(populations)
        or data["axes"] != AXES
        or data["protein_pool_exchange"] != "none"
        or data["assembly_coupling"] != COUPLING
        or data["metabolic_scope"] != METABOLISM
        or len(set(edges)) != len(edges)
        or len(data["surface_edge_senders"]) != len(edges)
        or len(data["surface_edge_receivers"]) != len(edges)
        or len(data["roles"]) != len(populations)
    ):
        raise ValueError("Invalid mobile-pump axes, owners or laws")
    owner_by_patch = dict(zip(patches, owners, strict=True))
    for a, b in zip(data["surface_edge_senders"], data["surface_edge_receivers"], strict=True):
        if (
            a == b
            or a not in owner_by_patch
            or b not in owner_by_patch
            or owner_by_patch[a] != owner_by_patch[b]
        ):
            raise ValueError("Invalid mobile-pump surface edge ownership")
    wanted = np.zeros((len(species), len(populations)))
    for k, roles in enumerate(data["roles"]):
        if (
            set(roles) != {"sodium", "potassium"}
            or len(set(roles.values())) != 2
            or not set(roles.values()) <= set(species)
        ):
            raise ValueError("Invalid mobile-pump ion roles")
        wanted[species.index(roles["sodium"]), k] = -3
        wanted[species.index(roles["potassium"]), k] = 2
    stoichiometry = np.asarray(data["stoichiometry"], dtype=float)
    if not np.array_equal(stoichiometry, wanted):
        raise ValueError("Invalid mobile-pump stoichiometry")
    initial = np.asarray(data["initial_amount_fmol"], dtype=float)
    totals = np.asarray(data["initial_total_by_cell_fmol"], dtype=float)
    work = np.asarray(data["work_per_cycle_pJ_per_fmol"], dtype=float)
    if (
        initial.shape != (len(populations), len(patches))
        or not np.isfinite(initial).all()
        or np.any(initial < 0)
        or totals.shape != (len(populations), len(cells))
        or not np.isfinite(totals).all()
        or np.any(totals < 0)
        or work.shape != (len(populations),)
        or not np.isfinite(work).all()
    ):
        raise ValueError("Invalid mobile-pump initial inventory or metabolic drive")
    for i, cell in enumerate(cells):
        if not np.array_equal(initial[:, np.asarray(owners) == cell].sum(axis=1), totals[:, i]):
            raise ValueError("Mobile-pump initial totals disagree")
    sizes = dict(
        world=row["worlds"],
        pump_population=len(populations),
        membrane_patch=len(patches),
        surface_edge=len(edges),
        species=len(species),
    )
    values = {}
    for name, axes in AXES.items():
        value = np.asarray(data.get(name), dtype=float)
        if (
            value.shape != tuple(sizes[a] for a in axes)
            or not np.isfinite(value).all()
            or (name == "amount_fmol" and np.any(value < 0))
            or (name.endswith("_dissipated_energy_pJ") and np.any(value < -1e-12))
        ):
            raise ValueError("Invalid mobile-pump state shape or domain: " + name)
        values[name] = value
    delta = np.zeros_like(values["mobile_pump_amount_increment"])
    for i, (a, b) in enumerate(
        zip(data["surface_edge_senders"], data["surface_edge_receivers"], strict=True)
    ):
        moved = values["mobile_pump_surface_transferred"][..., i]
        delta[..., patches.index(a)] -= moved
        delta[..., patches.index(b)] += moved
    residuals = (
        values["mobile_pump_amount_increment"] - delta,
        values["amount_fmol"] - initial - delta,
        values["outward_ion_transfer_fmol"]
        + stoichiometry[None, :, :, None] * values["mobile_pump_cycles"][:, None, :, :],
    )
    if any(np.max(np.abs(v), initial=0) > 2e-13 for v in residuals):
        raise ValueError("Mobile-pump protein or ion transfer ledger disagrees")
    if (
        np.max(
            np.abs(
                values["mobile_pump_metabolic_work_pJ"]
                - values["mobile_pump_cycles"] * work[None, :, None]
            ),
            initial=0,
        )
        > 3e-12
    ):
        raise ValueError("Mobile-pump maintained ATP work disagrees")
    target = arm.setdefault("mobile_pumps", {k: data[k] for k in METADATA})
    if any(target[k] != data[k] for k in METADATA):
        raise ValueError("Mobile-pump ownership or laws changed")
    for name, value in values.items():
        total = value.sum(axis=0)
        key = name + "_sum_over_worlds"
        target[key] = (np.asarray(target.get(key, np.zeros_like(total))) + total).tolist()
