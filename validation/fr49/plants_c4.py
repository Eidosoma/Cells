"""FR-49's C4 plants (fr49-compartment-compositions-v1, amendment 2, A2.6). The tagged B/C files are
imported here and never edited.

Each plant is one run at C4's step, in a fresh process of its own (driver_c4), except (a), which is
the judge's substitution. Each must fail at least one named criterion:
- (a) no depletion: B from the free-ligand Langmuir with c0 = L_T / V_C, formed by the judge from
  the declared values (World B's (a)). Must fail C4-6.
- (c) K_d x 2: the population's k_off doubled in the definition (plants_bc.definition's (c),
  unchanged, since C4's population keeps World B's ID). Must fail C4-6.
- (d) the wash at every finite node: in-process, below the wash's compartment-node refusal. The
  wash's binding marks every finite outside node washed and its controls give each one W's events,
  so C is washed at 900 s too (World B's (d), on C4's well, `well_w`). The declaration names W
  alone, so the refusal passes. Must fail C4-1, and C4-5.
- (c1) the buffer labelled x: C1's plant, plants_bc.plant_c1, unchanged (its own drift check before
  it patches). Must fail C4-2.
- (e) the sites write the labelled species: in-process, below FR-44's by-species check. The
  population's bound layout binds S at C in place of G: its ligand row and its pool's row are S's.
  Its declaration and written_rows are unchanged, so the check passes. Before it patches, it checks
  that the engine's site layout is the one it was written against (E_LAYOUT_FIELDS, and one
  population binding G from one pool), as C1's plant checks its copy. Must fail C4-7, and C4-8;
  C4-5 is reported.

Plants (d) and (e) are reviewed by an agent who is not the builder before the judge's tag (D424).
"""

import contextlib

import numpy as np

from validation.fr49 import plants_bc, worlds
from validation.fr49 import worlds_bc as wb
from validation.fr49 import worlds_c4 as w4

# The site operator's layout fields that plant (e) was written against (site_occupancy.LAYOUT_FIELDS
# at fr49-c4's build, from main c536bf77): it patches site_ligand_row and site_pool_row only.
E_LAYOUT_FIELDS = (
    "site_capacity_fmol",
    "site_free_anchor_fmol",
    "site_bound_anchor_fmol",
    "site_on_rate",
    "site_off_rate",
    "site_internalisation_rate",
    "site_standard_RT",
    "site_ligand_row",
    "site_facing_kind",
    "site_facing_node",
    "site_receiving_cell",
    "site_internalises",
    "site_component",
    "site_component_count",
    "site_pool_kind",
    "site_pool_node",
    "site_pool_row",
    "site_pool_component",
    "site_facing_pool",
    "site_receiving_pool",
    "site_set_of",
    "site_set_capacity_fmol",
    "site_set_facing_kind",
    "site_set_facing_node",
)


@contextlib.contextmanager
def plant_d():
    """(d): the wash applied at every finite outside node, each with W's events (World B's (d), on
    C4's well)."""
    from cells.operators import wash_schedule as ws

    original_bind = ws.bind
    original_controls = ws.ScheduledCompartmentWash.control_values

    def finite(spec):
        o = spec.execution.extracellular_capacity
        mask = np.zeros(o, dtype=bool)
        for k, node in enumerate(spec.model.extracellular):
            mask[k] = not node.reservoir
        return mask

    def bind(spec, declaration):
        state, layout = original_bind(spec, declaration)
        return state, dict(layout, wash_node=finite(spec))

    def control_values(self, spec, declaration, schedule, records, indices, times):
        count, fraction, buffer = (
            np.array(v) for v in original_controls(self, spec, declaration, schedule, records,
                                                   indices, times)
        )  # fmt: skip
        well = [c.id for c in spec.model.extracellular].index(wb.W)
        for k in np.flatnonzero(finite(spec)):
            count[:, k], fraction[:, k], buffer[:, :, k] = (
                count[:, well],
                fraction[:, well],
                buffer[:, :, well],
            )
        return count, fraction, buffer

    ws.bind = bind
    ws.ScheduledCompartmentWash.control_values = control_values
    try:
        yield
    finally:
        ws.bind = original_bind
        ws.ScheduledCompartmentWash.control_values = original_controls


def e_layout_drift():
    """Where the engine's site layout differs from the one plant (e) was written against: [] when
    site_occupancy.LAYOUT_FIELDS is E_LAYOUT_FIELDS."""
    from cells.operators import site_occupancy as so

    found = tuple(so.LAYOUT_FIELDS)
    if found == E_LAYOUT_FIELDS:
        return []
    return [
        f"site_occupancy.LAYOUT_FIELDS gains {sorted(set(found) - set(E_LAYOUT_FIELDS))} and "
        f"loses {sorted(set(E_LAYOUT_FIELDS) - set(found))}, or reorders them"
    ]


@contextlib.contextmanager
def plant_e():
    """(e): the population binds S at C in place of G, its declaration and written rows unchanged.
    It stops, before it patches, if the engine's site layout is not the one it was written against,
    or if the bound layout does not hold one population binding G from one pool."""
    from cells.operators import site_occupancy as so

    drift = e_layout_drift()
    if drift:
        raise RuntimeError(f"plant (e) was written against another site layout: {'; '.join(drift)}")
    original = so.bind

    def planted(spec, declaration):
        state, layout = original(spec, declaration)
        ids = list(spec.model.species_ids)
        g, s = ids.index(w4.G), ids.index(worlds.S)
        rows = np.asarray(layout["site_ligand_row"])
        pools = np.asarray(layout["site_pool_row"])
        if rows.tolist() != [g] or pools.tolist() != [g]:
            raise RuntimeError(
                "plant (e) was written against one population binding G from one pool: ligand "
                f"rows {rows.tolist()}, pool rows {pools.tolist()}, G's row {g}"
            )
        return state, dict(layout, site_ligand_row=np.full_like(rows, s),
                           site_pool_row=np.full_like(pools, s))  # fmt: skip

    so.bind = planted
    try:
        yield
    finally:
        so.bind = original


ENGINE = {"d": plant_d, "c1": plants_bc.plant_c1, "e": plant_e}


def definition(raw, plant):
    """raw with a definition plant applied (a copy): (c), the population's k_off x 2
    (plants_bc.definition's, unchanged). Any other plant leaves the definition as it is."""
    return plants_bc.definition(raw, "c" if plant == "c" else None)


@contextlib.contextmanager
def engine(plant):
    """The engine plant `plant` ("d", "c1" or "e") for the enclosed run; any other is a no-op."""
    if plant in ENGINE:
        with ENGINE[plant]():
            yield
    else:
        yield
