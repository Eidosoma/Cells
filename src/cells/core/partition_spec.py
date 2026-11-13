"""Definition helper for isopotential_partition@1 (docs/CELL_DIVISION_S5_DESIGN.md §3.2).

add_division writes one prescribed division's daughter slots into a raw composite definition
and returns its division block for the partition declaration. Each daughter slot is declared
by the anchor rule: for every extensive anchor x of the parent, daughter 1 takes fl(a x) and
daughter 2 fl(x - fl(a x)), and the two must sum to x exactly. That covers:
* the reference amounts, volume, fixed background and charge anchor, with the volume
  fraction f;
* each patch's area and capacitance, with its area fraction a_k;
* each contact's area, with its fraction a_e.
Domain parameters are copied: permeability per area, laws, gates and population parameters.
Schedules of the new patches, populations and contacts are copied from the parent's, and the
execution's capacities grow to hold the new slots.

A split that does not sum exactly is refused here, as the partition's parser would refuse it.
For f = 1/2 every split is exact. For other fractions the complement is exact by Sterbenz when
a >= 1/2, so name the larger daughter first. Pumps on the parent are refused (later work).

add_bridge writes the cytoplasmic bridge between two daughters (an @3 junction with
P_s A = 2 a_0 D_s^cyt and a gate fixed open), and cytoplasmic_diffusivities gives D_s^cyt from a
declared cytoplasmic conductivity (S5 design §4.2).
"""

import copy
import math

from cells.core.specs import ConfigError

F = 6.02214076e23 * 1.602176634e-19  # C/mol (exact SI product N_A e)
R = 6.02214076e23 * 1.380649e-23  # J/(mol K) (exact SI product N_A k_B)
BRIDGE_LENGTH_M = 1.0  # Only P A enters the junction law: area 2 a_0 x 1 m, P = D / (1 m).


def cytoplasmic_diffusivities(sigma_S_per_m, cytosol_mM, free_diffusivity, valence, temperature_K):
    """{species: D_s^cyt} = D_s sigma_cyt / sigma_free (S5 design §4.2, Appendix A.7).

    sigma_free = (F^2 / RT) sum z_s^2 c_s D_s is the free-solution conductivity of the cytosol's
    declared composition (mM = mol/m^3); one obstruction factor applies to every species.
    """
    free = (F * F / (R * temperature_K)) * math.fsum(
        valence[s] ** 2 * cytosol_mM[s] * free_diffusivity[s] for s in free_diffusivity
    )
    return {s: d * sigma_S_per_m / free for s, d in free_diffusivity.items()}


def add_bridge(raw, *, junction_id, daughters, aperture_m, diffusivity):
    """Append a cytoplasmic bridge between two daughters (in place); return its bridge block
    for cytoplasmic_bridge_closure@1 without the closure law (closure, closure_time_s).

    The @3 junction has P_s A = 2 a_0 D_s^cyt (area 2 a_0 x 1 m, permeability D_s^cyt / 1 m)
    and a gate fixed open (minimum open fraction 1, initial gate 1); its availability is 1.
    """
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    species = [s["id"] for s in m["species"]]
    m["junctions"].append(
        dict(
            id=junction_id,
            sender=daughters[0],
            receiver=daughters[1],
            area_m2=2.0 * aperture_m * BRIDGE_LENGTH_M,
            permeability_m_per_s={s: diffusivity.get(s, 0.0) / BRIDGE_LENGTH_M for s in species},
            law="constant_field@1",
            gate=dict(
                law="junction_voltage_relaxation@1",
                threshold_voltage_V=0.0,
                minimum_open_fraction=1.0,
                initial_gate=1.0,
            ),
        )
    )
    e.setdefault("junction_controls", []).append(
        dict(junction_id=junction_id, schedule=[dict(time=0.0, availability=1.0)])
    )
    x["edge_capacity"] = max(x["edge_capacity"], len(m["junctions"]))
    return dict(
        junction_id=junction_id,
        initial_aperture_m=aperture_m,
        cytoplasmic_diffusivity_m2_per_s={s: diffusivity.get(s, 0.0) for s in species},
    )


def split(x, a):
    """(fl(a x), fl(x - fl(a x))), refused unless the two sum to x exactly."""
    first = a * x
    second = x - first
    if first + second != x:
        raise ConfigError(
            f"The split of {x!r} at {a!r} does not sum exactly; name the larger daughter first"
        )
    return first, second


def _slot(name, daughter):
    return f"{name}_{daughter}"


def add_division(
    raw,
    *,
    division_id,
    parent,
    daughters,
    volume_fraction=0.5,
    area_fractions=None,
    contact_fractions=None,
    mismatch_carriers=None,
    bridges=(),
):
    """Append the daughter slots of one division to raw (in place); return its block.

    area_fractions and contact_fractions: {parent slot id: daughter 1's fraction} (default
    volume_fraction and 1/2). Daughter slot ids are "<parent slot id>_<daughter id>". bridges:
    the parent's bridge junctions to its sibling, which retire with it and are not mapped.
    """
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    cells = {c["id"]: c for c in m["cells"]}
    if parent not in cells or any(d in cells for d in daughters) or len(set(daughters)) != 2:
        raise ConfigError("add_division takes an existing parent and two new daughter IDs")
    area_fractions = dict(area_fractions or {})
    contact_fractions = dict(contact_fractions or {})
    f = volume_fraction
    source = cells[parent]
    for k, daughter in enumerate(daughters):
        cell = copy.deepcopy(source)
        cell["id"] = daughter

        def take(value, k=k):
            return split(value, f)[k]

        cell["volume_pL"] = take(source["volume_pL"])
        cell["fixed_charge_equivalent_fmol"] = take(source["fixed_charge_equivalent_fmol"])
        cell["initial_charge_C"] = take(source["initial_charge_C"])
        cell["initial_amount_fmol"] = {s: take(v) for s, v in source["initial_amount_fmol"].items()}
        m["cells"].append(cell)
    patches, populations, contacts = [], [], []
    controls = {c["membrane_id"]: c for c in e["membrane_controls"]}
    channel_controls = {c["channel_id"]: c for c in e.get("channel_controls", [])}
    junction_controls = {c["junction_id"]: c for c in e.get("junction_controls", [])}
    for patch in [p for p in m["membranes"] if p["inside"] == parent]:
        if patch.get("pump") is not None or patch.get("calcium_pump") is not None:
            raise ConfigError("Pumps on a dividing cell are later work")
        a = area_fractions.get(patch["id"], f)
        names = [_slot(patch["id"], d) for d in daughters]
        for k, (daughter, name) in enumerate(zip(daughters, names, strict=True)):
            new = copy.deepcopy(patch)
            new.update(
                id=name,
                inside=daughter,
                area_m2=split(patch["area_m2"], a)[k],
                capacitance_F=split(patch["capacitance_F"], a)[k],
            )
            m["membranes"].append(new)
            control = copy.deepcopy(controls[patch["id"]])
            control["membrane_id"] = name
            e["membrane_controls"].append(control)
        patches.append(dict(parent=patch["id"], daughters=names, fraction=a))
        for channel in [c for c in m["channels"] if c["membrane_id"] == patch["id"]]:
            ids = [_slot(channel["id"], d) for d in daughters]
            for name, membrane in zip(ids, names, strict=True):
                new = copy.deepcopy(channel)
                new.update(id=name, membrane_id=membrane)
                m["channels"].append(new)
                if channel["id"] in channel_controls:
                    control = copy.deepcopy(channel_controls[channel["id"]])
                    control["channel_id"] = name
                    e["channel_controls"].append(control)
            populations.append(dict(parent=channel["id"], daughters=ids))
    incident = [j for j in m["junctions"] if parent in (j["sender"], j["receiver"])]
    for junction in [j for j in incident if j["id"] not in bridges]:
        a = contact_fractions.get(junction["id"], 0.5)
        ids = [_slot(junction["id"], d) for d in daughters]
        for k, (daughter, name) in enumerate(zip(daughters, ids, strict=True)):
            new = copy.deepcopy(junction)
            new["id"] = name
            new["sender" if junction["sender"] == parent else "receiver"] = daughter
            new["area_m2"] = split(junction["area_m2"], a)[k]
            m["junctions"].append(new)
            if junction["id"] in junction_controls:
                control = copy.deepcopy(junction_controls[junction["id"]])
                control["junction_id"] = name
                e["junction_controls"].append(control)
        contacts.append(dict(parent=junction["id"], daughters=ids, fraction=a))
    x["capacity"] = max(x["capacity"], len(m["cells"]))
    x["membrane_capacity"] = max(x["membrane_capacity"], len(m["membranes"]))
    x["channel_capacity"] = max(x["channel_capacity"], len(m["channels"]))
    x["edge_capacity"] = max(x["edge_capacity"], len(m["junctions"]))
    return dict(
        id=division_id,
        parent=parent,
        daughters=list(daughters),
        volume_fraction=f,
        patches=patches,
        populations=populations,
        contacts=contacts,
        mismatch_carriers=dict(mismatch_carriers or {}),
    )
