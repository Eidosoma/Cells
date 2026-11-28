"""FR-49's C4, the four-way form (fr49-compartment-compositions-v1, amendment 2): its world, its
twins, its entity rule and its two gates (A2.1 to A2.4).

The tagged B/C files (validation/fr49/worlds_bc.py, driver_bc.py, plants_bc.py and judge_bc.py, tag
fr49-compartment-compositions-v1-judge-bc-2026-11-28) are imported here and never edited.

**C4's world (A2.1)** is C1's world (worlds_bc.world_c1), unchanged: World L, labelled, with C1's
well W washed by C1's event. Added to it:
- an unlabelled neutral ligand G: at C (`space_0`) at world B's `initial_fmol.n_L`; at every other
  cell and node, and in the wash's buffer, at its trace, 1e-6 K_d, with K_d world B's
  `k_off_per_s` / `k_on_per_mM_per_s` in binary64 (World B's builder's reading,
  worlds_bc.B_TRACE_mM);
- world B's site population (its sites, rates and initial occupancy), on World L's bounding patch
  facing C, binding G.

The builder's own values, which no criterion reads: G's ID, its diffusivity (World L's
worlds.D_S), its ledger floor (worlds.FLOOR_FMOL), and the population's ID and unit, World B's
`lumen_sites` and `lumen_site`.

**The twins and the plants' definitions** (A2.3, A2.6): `world_c4(event=False)` is the twin, the
wash declared with no event; `labelled=False` the unlabelled twin, the label owner and its schedule
removed; `bound=False` the unbound twin, the binding multiplier 0 from t = 0. Plant (c)'s
definition is plants_bc.definition's, unchanged. `without` removes one operator law with its
experiment keys, for the host rows of C4's qualified set's proper subsets (A2.7).

**The step** is 0.5 s (A2.3), to world L's horizon, observed every 60 s; plant (e) runs to its own
1800 s (amendment 3, A3.2), its definition `world_c4(end=1800)`, which the values gate's end-time
row compares against that horizon as (e)'s registered change.
"""

import copy
from decimal import Decimal

import numpy as np

from cells.registry.inventory_species import add_inventory_species
from validation.fr49 import worlds
from validation.fr49 import worlds_bc as wb
from validation.tissue import site_occupancy_fixtures as sfx

G, POP, UNIT = "G", "lumen_sites", "lumen_site"
DT, EVERY = 0.5, 60.0  # s (A2.3).
LABELS = "cells.operator.neutral_arrival_labels@1"
SITES = "cells.operator.site_occupancy@1"
WASH = "cells.operator.scheduled_compartment_wash@1"
TURNOVER = "cells.operator.scheduled_species_turnover@1"
EXPRESSION = "cells.operator.templated_polymerisation@1"
COMPARTMENTS = "cells.operator.cell_owned_compartments@1"
REACTIONS = "cells.operator.local_species_reactions@1"
EXCHANGE = "cells.operator.scheduled_species_exchange@1"
# Each law's experiment keys, which `without` removes with it.
EXPERIMENT_KEYS = {
    LABELS: ("label_arrivals",),
    WASH: ("compartment_wash_events",),
    SITES: ("site_controls",),
    EXPRESSION: ("polymerisation_controls",),
    TURNOVER: ("turnover_controls",),
    COMPARTMENTS: (),
}
QUALIFIED = (COMPARTMENTS, EXPRESSION, TURNOVER, WASH)  # C4's qualified set (A2.7).


def k_d():
    """World B's K_d, k_off / k_on, in binary64 (mM)."""
    v = worlds.declared("B")
    return float(v["k_off_per_s"]) / float(v["k_on_per_mM_per_s"])


def g_trace():
    """G's trace, 1e-6 K_d in binary64 (mM; A2.1)."""
    return 1e-6 * k_d()


def population(**placement):
    """World B's site population (cases.json world B), binding G. `placement` is
    site_occupancy_fixtures.population's patch, face and node (World L's bounding patch facing C,
    by default)."""
    v = worlds.declared("B")
    sites = v["sites"]
    if Decimal(v["initial_fmol"]["B"]) != 0:
        raise ValueError("world B's B(0) is not 0: C4's population would need its occupancy")
    where = dict(patch=worlds.PATCH, face="outside", node=None) | placement
    out = sfx.population(
        POP,
        copies=float(sites["copies"]),
        sites_per_copy=int(sites["sites_per_copy"]),
        alpha=float(sites["accessible_fraction"]),
        k_on=float(v["k_on_per_mM_per_s"]),
        k_off=float(v["k_off_per_s"]),
        theta0=0.0,
        unit=UNIT,
        **where,
    )
    out["ligand"] = G
    return out


def with_g(raw, placement=None):
    """raw with G (world B's n_L(0) at C, its trace elsewhere and in every wash buffer) and C4's
    population binding it."""
    trace = g_trace()
    raw = add_inventory_species(
        raw, G, trace_mM=trace, diffusivity_m2_per_s=worlds.D_S, floor_fmol=worlds.FLOOR_FMOL
    )
    raw = wb.set_amount(raw, worlds.NODE, G, float(worlds.declared("B")["initial_fmol"]["n_L"]))
    for event in raw["experiment"].get("compartment_wash_events", ()):
        event["buffer_mM"][G] = trace
    return sfx.with_site_occupancy(
        raw, [population(**(placement or {}))], ligands=[sfx.ligand(trace_mM=trace, species=G)]
    )


def without(raw, law):
    """raw with every operator block of `law` removed, and its experiment keys (a copy)."""
    out = copy.deepcopy(raw)
    out["model"]["operators"] = [b for b in out["model"]["operators"] if b["law"] != law]
    for key in EXPERIMENT_KEYS[law]:
        out["experiment"].pop(key, None)
    return out


def world_c4(
    *, dt=DT, end=None, every=EVERY, event=True, labelled=True, bound=True, placement=None
):
    """C4's world (A2.1) at `dt` to `end` (world L's horizon by default): `event=False` its twin,
    `labelled=False` its unlabelled twin, `bound=False` its unbound twin."""
    raw = with_g(wb.world_c1(dt=dt, end=end, every=every, event=event), placement)
    if not bound:
        for control in raw["experiment"]["site_controls"]:
            control["schedule"] = [dict(time=0.0, multiplier=0.0)]
    return raw if labelled else without(raw, LABELS)


def subset_world(kept):
    """C4's world with the laws of its qualified set not in `kept` removed (A2.7's host rows)."""
    raw = world_c4()
    for law in QUALIFIED:
        if law not in kept:
            raw = without(raw, law)
    return raw


# ------------------------------------------------------------------ C4-1's entity rule (A2.4)

# READING-3's rule with the site operator's axes: C1's classes, and the site operator's populations
# and sets classed P, every slot. C4's one population lies on the patch bounding O and C, and
# c4_entity_slots refuses a population on any patch but one bounding O or C, W's aside.
C4_CLASS = dict(wb.C1_CLASS, site_population="P", site_set="P")
C4_SUB_AXES = wb.C1_SUB_AXES
C4_EMPTY_AXES = wb.C1_EMPTY_AXES


def c4_entity_slots(raw):
    """{entity axis: slots, or None for all} of a C4 definition: worlds_bc.c1_entity_slots's, and
    every slot of the site operator's populations and sets. Raises ValueError where a population
    is not on a patch bounding O or C, or is on one with W on a side."""
    slots = wb.c1_entity_slots(raw)
    patches = {p["id"]: p for p in raw["model"]["membranes"]}
    ends = {worlds.CELL, worlds.NODE}
    for block in raw["model"]["operators"]:
        for pop in block.get("populations", ()) if block["law"] == SITES else ():
            patch = patches.get(pop["owner"].get("patch"))
            sides = {patch["inside"], patch["outside"]} if patch else set()
            if not sides & ends or wb.W in sides:
                raise ValueError(
                    f"C4-1's entity rule classes a site population only on a patch bounding O or "
                    f"C, W's aside: {pop['id']} is owned by {pop['owner']}"
                )
    return dict(slots, site_population=None, site_set=None)


def c4_part(axes, values, slots):
    """(class, rows) of the part of one state field that C4-1 compares, or None where it compares
    none of it (worlds_bc.c1_part's rule over C4's tables). Raises ValueError for an axis the rule
    does not class, a field with no entity axis or with two, and an empty axis that holds a slot."""
    entity = [a for a in axes if a not in C4_SUB_AXES]
    if len(entity) != 1 or not (entity[0] in C4_CLASS or entity[0] in C4_EMPTY_AXES):
        raise ValueError(f"C4-1's entity rule does not class the axes {tuple(axes)}")
    (axis,) = entity
    if axis in C4_EMPTY_AXES:
        if np.asarray(values).size:
            raise ValueError(f"axis {axis} holds a slot in C4's world, where the rule has none")
        return None
    chosen = slots[axis]
    if chosen is None:
        return C4_CLASS[axis], np.asarray(values)
    if not chosen:
        return None
    return C4_CLASS[axis], np.take(values, chosen, axis=1 + list(axes).index(axis))


# ------------------------------------------------------------------ the two gates (A2.2)

# The registered changes by which a twin's or a plant's definition departs from C4's.
CHANGES = (None, "twin", "unlabelled", "unbound", "plant c", "plant e")
E_HORIZON_S = "1800"  # s: plant (e)'s own horizon (amendment 3, A3.2), its end-time row's value.


def _same_decimal(value, text):
    return Decimal(repr(float(value))) == Decimal(text)


def _node(raw, name):
    m = raw["model"]
    return next(n for n in [*m["cells"], *m["extracellular"]] if n["id"] == name)


def values_gate(raw, change=None, *, development=False):
    """[(row, outcome)] of amendment 2's values gate (A2.2's table) on a definition: each entry
    against the cases.json value it points at, as decimals or by its formula in binary64, bit for
    bit. outcome is "equal", "absent (registered change)", "shortened (development job)" (the end
    time of a development job only), "plant (e)'s own 1800 s (amendment 3)" (the end time of plant
    (e)'s definition only, A3.2) or "DIFFERS". `change` is the definition's registered change
    (CHANGES)."""
    if change not in CHANGES:
        raise ValueError(f"no registered change {change!r}")
    L, C1, B = (worlds.declared(w) for w in ("L", "C1", "B"))
    f = float
    m, e = raw["model"], raw["experiment"]
    rows = []

    def check(name, ok, absent=False):
        rows.append(
            (name, "absent (registered change)" if absent else ("equal" if ok else "DIFFERS"))
        )

    cell, space, well = _node(raw, worlds.CELL), _node(raw, worlds.NODE), _node(raw, wb.W)
    S = worlds.S
    check("cell_0's volume = L.V_O_pL", _same_decimal(cell["volume_pL"], L["V_O_pL"]))
    check("space_0's volume = L.V_C_pL", _same_decimal(space["volume_pL"], L["V_C_pL"]))
    check("space_0's volume = B.V_C_pL", _same_decimal(space["volume_pL"], B["V_C_pL"]))
    n_o, n_c = L["initial_fmol"]["n_O"], L["initial_fmol"]["n_C"]
    check(
        "S at cell_0 = (n_O / V_O) x V",
        cell["initial_amount_fmol"][S] == (f(n_o) / f(L["V_O_pL"])) * cell["volume_pL"],
    )
    check(
        "S at space_0 = (n_C / V_C) x V",
        space["initial_amount_fmol"][S] == (f(n_c) / f(L["V_C_pL"])) * space["volume_pL"],
    )
    route = next(r for r in m["passive_routes"] if r["species"] == S)
    patch = next(p for p in m["membranes"] if p["id"] == route["patch"])
    check(
        "s_route's permeability = a / (1e15 x area)",
        route["permeability_m_per_s"] == f(L["a_pL_per_s"]) / (1e15 * patch["area_m2"]),
    )
    controls = {c["route_id"]: c["schedule"] for c in e["turnover_controls"]}
    check("make = L.P", controls["make"] == [dict(time=0.0, rate=f(L["P_fmol_per_s"]))])
    check("clear = L.k_d", controls["clear"] == [dict(time=0.0, rate=f(L["k_d_per_s"]))])
    owner = next((b for b in m["operators"] if b["law"] == LABELS), None)
    x_w, b_w = (Decimal(C1["initial_fmol"][k]) for k in ("x_W", "b_W"))
    if owner is None:
        for name in (
            "S's label schedule = L.pulse_s",
            "no initial shares at cell_0 or space_0",
            "S's shares at well_w = x/(x+b), b/(x+b)",
        ):
            check(name, False, absent=change == "unlabelled")
    else:
        schedule = next(a for a in e["label_arrivals"] if a["species"] == S)["schedule"]
        check(
            "S's label schedule = L.pulse_s",
            schedule
            == [
                dict(time=f(L["pulse_s"]["t1"]), label="x"),
                dict(time=f(L["pulse_s"]["t2"]), label="base"),
            ],
        )
        entry = next(s for s in owner["species"] if s["id"] == S)
        check(
            "no initial shares at cell_0 or space_0",
            not [i for i in entry["initial"] if i["node"] in (worlds.CELL, worlds.NODE)],
        )
        shares = next(i for i in entry["initial"] if i["node"] == wb.W)["shares"]
        check(
            "S's shares at well_w = x/(x+b), b/(x+b)",
            shares == {"x": float(x_w / (x_w + b_w)), "base": float(b_w / (x_w + b_w))},
        )
    horizon = E_HORIZON_S if change == "plant e" else L["horizon_s"]
    if development and not _same_decimal(e["end_time"], horizon):
        rows.append(("end time = L.horizon_s", "shortened (development job)"))
    elif change == "plant e":  # Compared against (e)'s own horizon, its registered change (A3.2).
        own = _same_decimal(e["end_time"], E_HORIZON_S)
        rows.append(
            ("end time = L.horizon_s", "plant (e)'s own 1800 s (amendment 3)" if own else "DIFFERS")
        )
    else:
        check("end time = L.horizon_s", _same_decimal(e["end_time"], L["horizon_s"]))
    check("well_w's volume = C1.V_W_pL", _same_decimal(well["volume_pL"], C1["V_W_pL"]))
    check("S at well_w = x_W + b_W", well["initial_amount_fmol"][S] == float(x_w + b_w))
    events = e.get("compartment_wash_events", [])
    if not events:
        check("the wash's event = C1.wash", False, absent=change == "twin")
    else:
        wash = C1["wash"]
        check(
            "the wash's event = C1.wash",
            len(events) == 1
            and _same_decimal(events[0]["time"], wash["time_s"])
            and _same_decimal(events[0]["fraction"], wash["fraction"])
            and _same_decimal(events[0]["buffer_mM"][S], wash["buffer_mM"]["S"])
            and events[0]["node"] == wb.W,
        )
    block = next(b for b in m["operators"] if b["law"] == SITES)
    (pop,) = block["populations"]
    sites = B["sites"]
    check(
        "copies, sites per copy, accessible fraction = B.sites",
        _same_decimal(pop["copies"], sites["copies"])
        and pop["sites_per_copy"] == int(sites["sites_per_copy"])
        and _same_decimal(pop["accessible_fraction"], sites["accessible_fraction"]),
    )
    check(
        "k_on = B.k_on",
        _same_decimal(pop["association_rate_per_mM_per_s"], B["k_on_per_mM_per_s"]),
    )
    if change == "plant c":
        check(
            "k_off = 2 x B.k_off (plant (c))",
            pop["dissociation_rate_per_s"] == 2.0 * f(B["k_off_per_s"]),
        )
    else:
        check("k_off = B.k_off", _same_decimal(pop["dissociation_rate_per_s"], B["k_off_per_s"]))
    check(
        "initial occupancy = B.initial_fmol.B / S = 0",
        Decimal(B["initial_fmol"]["B"]) == 0 and pop["initial_occupancy"] == 0.0,
    )
    check(
        "G at space_0 = B.n_L",
        _same_decimal(space["initial_amount_fmol"][G], B["initial_fmol"]["n_L"]),
    )
    trace = 1e-6 * (f(B["k_off_per_s"]) / f(B["k_on_per_mM_per_s"]))
    others = [n for n in [*m["cells"], *m["extracellular"]] if n["id"] != worlds.NODE]
    check(
        f"G elsewhere = (1e-6 K_d) x V at each of {len(others)} cells and nodes, the bath among "
        "them",
        all(n["initial_amount_fmol"][G] == trace * n["volume_pL"] for n in others),
    )
    check(
        "G's declared ligand trace = 1e-6 K_d",
        next(s for s in block["species"] if s["id"] == G)["trace_mM"] == trace,
    )
    if events:
        check("G in the wash's buffer = 1e-6 K_d", events[0]["buffer_mM"][G] == trace)
    else:
        check("G in the wash's buffer = 1e-6 K_d", False, absent=change == "twin")
    schedule = next(c for c in e["site_controls"] if c["population"] == pop["id"])["schedule"]
    want = 0.0 if change == "unbound" else 1.0
    check(
        f"the binding multiplier is {want:g} from t = 0",
        schedule == [dict(time=0.0, multiplier=want)],
    )
    on_patch = pop["owner"] == {"patch": worlds.PATCH, "face": "outside"}
    check("the population is world B's lumen_sites, on the bounding patch facing C",
          pop["id"] == POP and on_patch)  # fmt: skip
    return rows


def _places(value, path, name):
    """Every path at which `name` appears as a key or a string value."""
    out = []
    if isinstance(value, dict):
        for k, v in value.items():
            here = f"{path}.{k}"
            if k == name:
                out.append(here)
            out += _places(v, here, name)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            out += _places(v, f"{path}[{i}]", name)
    elif value == name:
        out.append(path)
    return out


def decoupling_gate(raw):
    """[(check, holds)] of amendment 2's decoupling gate on a definition: G is moved by nothing but
    its binding and is not labelled, S is no site population's ligand, and the wash names W
    alone."""
    m = raw["model"]
    checks = [
        (
            "G's permeability is 0 on every patch",
            all(p["permeability_m_per_s"].get(G) == 0.0 for p in m["membranes"]),
        ),
        (
            "G's permeability is 0 on every junction",
            all(j["permeability_m_per_s"].get(G, 0.0) == 0.0 for j in m.get("junctions", [])),
        ),
        ("no face carries G", not m.get("faces")),
        ("G is in no passive route", all(r["species"] != G for r in m.get("passive_routes", []))),
        ("G is in no kind", not _places(m.get("kinds", []), "kinds", G)),
    ]
    laws = [b["law"] for b in m["operators"]]
    for block in m["operators"]:
        law = block["law"]
        if law == TURNOVER:
            checks.append((
                "G is in no turnover route or species",
                all(s["id"] != G for s in block["species"])
                and all(r["species"] != G for r in block["routes"]),
            ))  # fmt: skip
        elif law == EXPRESSION:
            checks.append(
                ("G is not an expression species", all(s["id"] != G for s in block["species"]))
            )
        elif law == LABELS:
            checks.append(("G is not labelled", all(s["id"] != G for s in block["species"])))
        elif law == SITES:
            checks.append((
                "S is no site population's ligand",
                all(p["ligand"] != worlds.S for p in block["populations"]),
            ))  # fmt: skip
        elif law == WASH:
            checks.append(("the wash names well_w alone", block["nodes"] == [wb.W]))
    checks.append(
        ("no reactions or exchange are declared", REACTIONS not in laws and EXCHANGE not in laws)
    )
    return checks


def gates_refusal(raw, change=None, *, development=False):
    """Why a definition fails either gate (A2.2), or None."""
    bad = [f"{row}: {outcome}" for row, outcome in values_gate(raw, change, development=development)
           if outcome == "DIFFERS"]  # fmt: skip
    bad += [f"{check}: does not hold" for check, holds in decoupling_gate(raw) if not holds]
    return "; ".join(bad) if bad else None
