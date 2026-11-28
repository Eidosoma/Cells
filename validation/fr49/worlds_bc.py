"""FR-49's registered worlds B, C1 and C2 (fr49-compartment-compositions-v1,
validation/fr49/REGISTRATION.md §4 and §5), beside World L's validation/fr49/worlds.py, which its
judge's tag froze.

Every declared value is read from the registered spec's cases.json
(validation/fr49/worlds.declared), never restated here; the mapping is the only thing this module
adds. The builder's readings (/mnt/workspaces/Cells/fr49-pairing-plan-20261127/PLAN.md §2.6), none
of which changes a declared value:
- **World B** is the review's well (validation/tissue/wash_schedule_fixtures.well, its specimen
  and stand-in cells, the 1 uL well and the held bath) with the specimen's second contact patch
  `lys_face` bounding a finite node `lys` of V_C, declared as the specimen's compartment `lys_0`:
  the design note's probe/worlds.py world_b (/mnt/workspaces/Cells/fr49-51-design-20261123/), built
  from secreted_species_fixtures.world so that each node's ions are its own volume's. The ligand is
  the fixtures' S, at n_L(0) at lys and at its trace, 1e-12 mM (1e-6 K_d exactly in binary64), at
  every other node, the well included. The wash's buffer holds it at that trace, so the honest wash
  is materially a no-op at the well while its books are written.
- **C1** is World L, labelled, with a well W of V_W: a copy of the compartment's node at every
  concentration but S's, which is x_W + b_W with the declared shares, joined to cell_0 by a copy of
  the bounding patch, which carries no route. The buffer holds S at its declared concentration and
  every other neutral species at W's own declared concentration, since none is declared.
- **C2** is World B's compartment with one shared site set on lys's bounding patch, facing lys, and
  the ligands L1 and L2, each at its total at lys and at 1e-12 mM elsewhere (within 1e-6 K_1 and
  1e-6 K_2); no wash.
C1 is built from World L's definition translated to today's IDs (validation/id_table), so every
definition this module returns is in today's IDs.
"""

import copy
import math
from decimal import Decimal

import numpy as np

from cells.registry.inventory_species import add_inventory_species
from validation import id_table
from validation.fr49 import worlds
from validation.tissue import compartment_fixtures as cfx
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import site_occupancy_fixtures as sfx
from validation.tissue import wash_schedule_fixtures as wfx

LIGAND = fx.SPECIES  # World B's ligand: D150's neutral S of the tissue fixtures.
LYS, LYS_FACE, LYS_ID, SPECIMEN, WELL = "lys", "lys_face", "lys_0", "specimen", "well"
B_TRACE_mM = 1e-12  # 1e-6 K_d, with K_d = k_off / k_on = 1e-3 / 1e3 mM.
C2_TRACE_mM = 1e-12  # At most 1e-6 K_1 (1e-12 mM) and 1e-6 K_2 (1e-11 mM).
LUMEN_SITES, LUMEN_SET = "lumen_sites", "lumen_set"
W, W_PATCH = "well_w", f"patch_{worlds.CELL}_well_w"
LABELS_LAW = "cells.operator.neutral_arrival_labels@1"


def _f(value):
    return float(value)


def grid(end, every):
    return [every * i for i in range(int(round(end / every)) + 1)]


def topology(*, dt, end, every):
    """The review's well world with lys (V_C) behind the specimen's patch lys_face, declared as the
    specimen's compartment lys_0; S at its trace everywhere; no sites and no wash."""
    v_c = _f(worlds.declared("B")["V_C_pL"])
    raw = fx.world(
        cells=((SPECIMEN, 1.0), ("wall_surface", 1.0)),
        nodes=((WELL, wfx.V_WELL), (LYS, v_c)),
        baths=("bath",),
        contacts=(
            ("specimen_face", SPECIMEN, WELL),
            ("wall_face", "wall_surface", WELL),
            (LYS_FACE, SPECIMEN, LYS),
        ),  # fmt: skip
        faces=(),
        dt=dt,
        end=end,
        observation_times=grid(end, every),
        trace_mM=B_TRACE_mM,
    )
    raw["execution"]["max_steps"] = int(math.ceil(end / dt)) + 8
    compartment = cfx.compartment(cid=LYS_ID, node=LYS, patch=LYS_FACE, owner=SPECIMEN)
    return cfx.with_compartments(raw, [compartment])


def set_amount(raw, node, species, fmol):
    """raw with `species` declared at `fmol` at the outside node `node` (in place)."""
    entry = next(n for n in raw["model"]["extracellular"] if n["id"] == node)
    entry["initial_amount_fmol"][species] = fmol
    return raw


def lumen_population(*, owner="patch", face="outside"):
    """World B's population of cases.json's sites on lys's bounding patch, facing `face`, or owned
    by lys's node (owner="node", FR-28: ruling 2's variant)."""
    v = worlds.declared("B")
    sites = v["sites"]
    return sfx.population(
        LUMEN_SITES,
        patch=LYS_FACE,
        face=face,
        node=LYS if owner == "node" else None,
        copies=_f(sites["copies"]),
        sites_per_copy=int(sites["sites_per_copy"]),
        alpha=_f(sites["accessible_fraction"]),
        k_on=_f(v["k_on_per_mM_per_s"]),
        k_off=_f(v["k_off_per_s"]),
        theta0=0.0,  # B(0) = 0 (cases.json's initial_fmol.B).
        unit="lumen_site",
    )


def world_b(*, dt=0.1, end=None, every=5.0, event=True, owner="patch", face="outside",
            nodes=(WELL,), event_node=WELL):  # fmt: skip
    """World B (REGISTRATION.md §4.1) at step dt (s) to `end` (the registered horizon), observed
    every `every` s. event=False: its twin, the wash declared with no event. owner="node": the
    node-owned variant (ruling 2). face, nodes and event_node serve the host rows' refused variants
    (an inward population; lys among the wash's nodes)."""
    v = worlds.declared("B")
    if _f(v["initial_fmol"]["B"]) != 0.0:
        raise ValueError("World B's sites start empty in the registered spec")
    end = _f(v["horizon_s"]) if end is None else end
    raw = set_amount(topology(dt=dt, end=end, every=every), LYS, LIGAND,
                     _f(v["initial_fmol"]["n_L"]))  # fmt: skip
    raw = sfx.with_site_occupancy(raw, [lumen_population(owner=owner, face=face)],
                                  ligands=[sfx.ligand(trace_mM=B_TRACE_mM)])  # fmt: skip
    w = v["wash_elsewhere"]
    events = [(_f(w["time_s"]), event_node, _f(w["fraction"]), {LIGAND: B_TRACE_mM})]
    return wfx.with_wash(raw, list(nodes), events if event else [])


def world_c2(*, dt=0.1, end=None, every=20.0, owner="patch", face="outside", wash=False):
    """C2 (REGISTRATION.md §5): World B's compartment, two ligands on one shared site set (FR-45's)
    at cases.json's C2 values, no wash. owner="node" and face="inside" serve the host rows (a set
    owned by lys's node; an inward set); wash=True adds World B's wash of the well (a host row)."""
    v = worlds.declared("C2")
    end = _f(v["horizon_s"]) if end is None else end
    raw = topology(dt=dt, end=end, every=every)
    for g in v["ligands"]:
        raw = add_inventory_species(
            raw,
            g["id"],
            trace_mM=C2_TRACE_mM,
            diffusivity_m2_per_s=worlds.D_S,
            floor_fmol=worlds.FLOOR_FMOL,
        )
        set_amount(raw, LYS, g["id"], _f(g["total_fmol"]))
    sites = v["sites"]
    site_set = sfx.site_set(LUMEN_SET, node=LYS if owner == "node" else None, patch=LYS_FACE,
                            face=face, copies=_f(sites["copies"]),
                            sites_per_copy=int(sites["sites_per_copy"]),
                            alpha=_f(sites["accessible_fraction"]), unit="lumen_site")  # fmt: skip
    bound = v["initial_bound_fmol"]
    members = [
        sfx.member(
            f"m_{g['id']}",
            LUMEN_SET,
            ligand=g["id"],
            k_on=_f(g["k_on_per_mM_per_s"]),
            k_off=_f(g["k_off_per_s"]),
            theta0=_f(bound[f"B{k + 1}"]),
        )  # fmt: skip
        for k, g in enumerate(v["ligands"])
    ]
    ligands = [sfx.ligand(trace_mM=C2_TRACE_mM, species=g["id"]) for g in v["ligands"]]
    raw = sfx.with_site_occupancy(raw, members, ligands=ligands, site_sets=[site_set])
    if wash:
        neutral = [s["id"] for s in raw["model"]["species"] if s["valence"] == 0]
        buffer = {s: B_TRACE_mM if s == LIGAND else C2_TRACE_mM for s in neutral}
        w = worlds.declared("B")["wash_elsewhere"]
        raw = wfx.with_wash(raw, [WELL], [(_f(w["time_s"]), WELL, _f(w["fraction"]), buffer)])
    return raw


def world_c1(*, dt=2.0, end=None, every=60.0, event=True):
    """C1 (REGISTRATION.md §5): World L (labelled) with a well W of V_W joined to cell_0 by a patch
    that carries no route; W's S at x_W + b_W, with the declared shares; W washed at the declared
    time and fraction for a buffer with S at its declared concentration. event=False: its twin,
    the wash declared with no event."""
    v = worlds.declared("C1")
    end = _f(worlds.declared("L")["horizon_s"]) if end is None else end
    raw = id_table.translate(worlds.world_l(dt=dt, end=end, every=every))
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    node = next(n for n in m["extracellular"] if n["id"] == worlds.NODE)
    well = copy.deepcopy(node)
    v_w = _f(v["V_W_pL"])
    scale = v_w / node["volume_pL"]  # Every concentration kept at W's volume.
    well.update(id=W, volume_pL=v_w)
    well["initial_amount_fmol"] = {k: a * scale for k, a in node["initial_amount_fmol"].items()}
    well["fixed_charge_equivalent_fmol"] = node["fixed_charge_equivalent_fmol"] * scale
    well["initial_charge_C"] = node["initial_charge_C"] * scale
    x_w, b_w = (Decimal(v["initial_fmol"][k]) for k in ("x_W", "b_W"))
    well["initial_amount_fmol"][worlds.S] = float(x_w + b_w)
    m["extracellular"].append(well)
    x["extracellular_capacity"] = len(m["extracellular"])
    patch = copy.deepcopy(next(p for p in m["membranes"] if p["id"] == worlds.PATCH))
    if any(value != 0.0 for value in patch["permeability_m_per_s"].values()):
        raise ValueError("C1's well patch must carry no permeability of its own")
    patch.update(id=W_PATCH, outside=W)
    m["membranes"].append(patch)
    x["membrane_capacity"] = len(m["membranes"])
    control = next(c for c in e["membrane_controls"] if c["membrane_id"] == worlds.PATCH)
    e["membrane_controls"].append(dict(copy.deepcopy(control), membrane_id=W_PATCH))
    owner = next(o for o in m["operators"] if o["law"] == LABELS_LAW)
    shares = {"x": float(x_w / (x_w + b_w)), "base": float(b_w / (x_w + b_w))}
    owner["species"][0]["initial"].append(dict(node=W, shares=shares))
    neutral = [s["id"] for s in m["species"] if s["valence"] == 0]
    buffer = {s: well["initial_amount_fmol"][s] / v_w for s in neutral}
    wash = v["wash"]
    buffer[worlds.S] = _f(wash["buffer_mM"][worlds.S])
    events = [(_f(wash["time_s"]), W, _f(wash["fraction"]), buffer)]
    return wfx.with_wash(raw, [W], events if event else [])


# C1-1's entity rule (the lead's ruling, validation/fr49/READING-3-2026-11-28.md): C1-1 compares
# every non-label state field whose entity is O or C, and the books of every patch bounding O or C
# but one with W on a side (with its routes and faces).
# Each axis of C1's state is classed: an entity axis (its class: O, C, or P for the patches that
# bound O or C, W's aside), a sub-axis kept whole, or an axis with no slot in C1's world. An axis
# outside the three is refused.
C1_CLASS = {
    "cell_slot": "O",  # O, C1's only cell.
    "poly_chain": "O",  # O's polymerisation: its chains, machine pool, holds and degradations.
    "poly_pool": "O",
    "poly_release": "O",
    "poly_degradation": "O",
    "extracellular_slot": "C",  # C's node; W's and the bath's are not compared.
    "membrane_slot": "P",  # Every patch bounding O or C, but one with W on a side.
    "passive_route": "P",  # The routes on those patches.
    "face_slot": "P",  # Faces on them: C1 declares none, so its one slot is padding.
}
C1_SUB_AXES = ("species", "gate", "poly_stage", "poly_class", "poly_fate", "poly_chain_counter",
               "poly_export_part")  # fmt: skip
C1_EMPTY_AXES = ("edge_slot", "channel_slot", "poly_export", "poly_transfer", "poly_outside_node",
                 "poly_outside_degradation", "poly_replaced_slot", "poly_replaced_chain",
                 "poly_replaced_release", "poly_replaced_degradation", "poly_replaced_transfer",
                 "poly_replaced_export")  # fmt: skip


def c1_entity_slots(raw):
    """{entity axis: slots, or None for all} of C1's definition `raw` under C1-1's entity rule: O's
    every slot on O's axes, C's node, every patch bounding O or C but one with W on a side (the
    O-bath wall and the O-C patch), the passive routes on them, and no face. Raises ValueError where
    the world is not one the rule classifies (one cell, no face)."""
    m = raw["model"]
    cells = [c["id"] for c in m["cells"]]
    nodes = [n["id"] for n in m["extracellular"]]
    if cells != [worlds.CELL] or m.get("faces"):
        raise ValueError("C1-1's entity rule classifies a world of one cell, O, with no face")
    ends = {worlds.CELL, worlds.NODE}
    patches = [
        p["id"]
        for p in m["membranes"]
        if {p["inside"], p["outside"]} & ends and W not in {p["inside"], p["outside"]}
    ]
    routes = m.get("passive_routes", [])
    return dict(
        dict.fromkeys(("poly_chain", "poly_pool", "poly_release", "poly_degradation")),
        cell_slot=[cells.index(worlds.CELL)],
        extracellular_slot=[nodes.index(worlds.NODE)],
        membrane_slot=[k for k, p in enumerate(m["membranes"]) if p["id"] in patches],
        passive_route=[k for k, r in enumerate(routes) if r.get("patch") in patches],
        face_slot=[],
    )


def c1_part(axes, values, slots):
    """(class, rows) of the part of one state field that C1-1 compares, or None where it compares
    none of it. axes: the field's axes; values: [row, *axes]; slots: c1_entity_slots's. Raises
    ValueError for an axis the rule does not class, a field with no entity axis or with two, and an
    empty axis that holds a slot."""
    entity = [a for a in axes if a not in C1_SUB_AXES]
    if len(entity) != 1 or not (entity[0] in C1_CLASS or entity[0] in C1_EMPTY_AXES):
        raise ValueError(f"C1-1's entity rule does not class the axes {tuple(axes)}")
    (axis,) = entity
    if axis in C1_EMPTY_AXES:
        if np.asarray(values).size:
            raise ValueError(f"axis {axis} holds a slot in C1's world, where the rule has none")
        return None
    chosen = slots[axis]
    if chosen is None:
        return C1_CLASS[axis], np.asarray(values)
    if not chosen:
        return None
    return C1_CLASS[axis], np.take(values, chosen, axis=1 + list(axes).index(axis))
