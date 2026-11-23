"""FR-49's registered worlds (fr49-compartment-compositions-v1, validation/fr49/REGISTRATION.md).

World L (§3): labels and expression beside a compartment. The engine world is the gene regulation
lane's R1 world (validation/gene_regulation/worlds.py) with its export and outside degradation
removed, so that expression's routes are in cell_0 only. Its export node `space_0` is declared as
cell_0's compartment, at the registered volume V_C, its amounts scaled so that every concentration
is kept. A neutral species S is added:
- a passive_neutral_permeation@1 route on the bounding patch, of permeability
  a / (1e15 x the patch's area);
- turnover's production in cell_0 at P, and its clearance at `space_0` at k_d;
- with `labelled`, S labelled, with its arrivals joining label x from t1 and the base from t2.
The bounding patch's own permeabilities are zero and the compartment's charge anchor zero (the
silent version). Every value of S's system is read from the registered spec's cases.json (world
L), never restated here; the mapping is the only thing this module adds.
"""

import json
import math
from pathlib import Path

from cells.registry.inventory_species import add_inventory_species
from validation.gene_regulation import worlds as gw
from validation.tissue import compartment_fixtures as cfx

SPEC = Path(__file__).resolve().parent / "references" / "spec" / "cases.json"
S = "S"
COMPARTMENT = "lumen_0"
CELL, NODE = gw.CELL, gw.SPACE
PATCH = f"{gw.EXPORT_PATCH}_{gw.CELL}_{gw.SPACE}"
TURNOVER = "scheduled_species_turnover@1"
LABELS = "neutral_arrival_labels@1"
ROUTE_LAW = "passive_neutral_permeation@1"
TRACE_mM = 1e-12  # S's background at every other node (the held bath), far below C's 1e-6 mM.
D_S = 1e-10  # m^2/s: S's declared diffusivity (no face carries it in World L).
FLOOR_FMOL = 1e-20  # D150's species-scale floor.
EXPRESSION_ROUTES = ("export_R", f"deg_R_{gw.SPACE}")  # The export and its outside degradation.


def declared(world="L"):
    """The registered spec's declared values of one world (cases.json), as decimal strings."""
    return json.loads(SPEC.read_text())["worlds"][world]


def _f(value):
    return float(value)


def world_l(*, dt=2.0, labelled=True, end=None, every=60.0):
    """World L at step dt (s) to `end` (s; the registered horizon by default), observed every
    `every` s; `labelled` False gives its unlabelled twin."""
    v = declared("L")
    end = _f(v["horizon_s"]) if end is None else end
    raw = gw.with_export(gw.r1(0.75))
    block = next(o for o in raw["model"]["operators"] if o["law"] == gw.POLYMERISATION)
    block.pop("exports")
    block.pop("outside_degradations")
    e = raw["experiment"]
    e["polymerisation_controls"] = [
        c for c in e["polymerisation_controls"] if c["route_id"] not in EXPRESSION_ROUTES
    ]
    cell = next(c for c in raw["model"]["cells"] if c["id"] == CELL)
    if cell["volume_pL"] != _f(v["V_O_pL"]):
        raise ValueError(f"World L's owner is {cell['volume_pL']} pL, not the registered V_O")
    node = next(c for c in raw["model"]["extracellular"] if c["id"] == NODE)
    scale = _f(v["V_C_pL"]) / node["volume_pL"]  # Every concentration kept at the new volume.
    node["volume_pL"] = _f(v["V_C_pL"])
    node["initial_amount_fmol"] = {k: a * scale for k, a in node["initial_amount_fmol"].items()}
    node["fixed_charge_equivalent_fmol"] *= scale
    node["initial_charge_C"] *= scale
    patch = next(p for p in raw["model"]["membranes"] if p["id"] == PATCH)
    if any(value != 0.0 for value in patch["permeability_m_per_s"].values()):
        raise ValueError("World L's bounding patch must carry no permeability of its own")
    initial = v["initial_fmol"]
    raw = add_inventory_species(
        raw,
        S,
        trace_mM=TRACE_mM,
        diffusivity_m2_per_s=D_S,
        floor_fmol=FLOOR_FMOL,
        concentrations_mM={
            CELL: _f(initial["n_O"]) / _f(v["V_O_pL"]),
            NODE: _f(initial["n_C"]) / _f(v["V_C_pL"]),
        },
    )
    raw["model"]["passive_routes"] = [
        dict(
            id="s_route",
            patch=PATCH,
            law=ROUTE_LAW,
            species=S,
            permeability_m_per_s=_f(v["a_pL_per_s"]) / (1e15 * patch["area_m2"]),
        )
    ]
    raw["model"]["operators"].append(
        dict(
            law=TURNOVER,
            species=[dict(id=S, catalogue=None, evidence=None)],
            routes=[
                dict(id="make", species=S, node=CELL, kind="production"),
                dict(id="clear", species=S, node=NODE, kind="clearance"),
            ],
            templates=[],
        )
    )
    raw["experiment"]["turnover_controls"] = [
        dict(
            route_id="make", carrier_id=CELL, schedule=[dict(time=0.0, rate=_f(v["P_fmol_per_s"]))]
        ),
        dict(route_id="clear", carrier_id=None, schedule=[dict(time=0.0, rate=_f(v["k_d_per_s"]))]),
    ]
    if labelled:
        pulse = v["pulse_s"]
        raw["model"]["operators"].append(
            dict(law=LABELS, species=[dict(id=S, labels=["base", "x"], initial=[])])
        )
        raw["experiment"]["label_arrivals"] = [
            dict(
                species=S,
                schedule=[
                    dict(time=_f(pulse["t1"]), label="x"),
                    dict(time=_f(pulse["t2"]), label="base"),
                ],
            )
        ]
    raw["experiment"]["end_time"] = end
    raw["experiment"]["observation_times"] = [every * i for i in range(int(round(end / every)) + 1)]
    raw["execution"]["dt"] = dt
    raw["execution"]["max_steps"] = int(math.ceil(end / dt)) + 8
    return cfx.with_compartments(
        raw, [cfx.compartment(cid=COMPARTMENT, node=NODE, patch=PATCH, owner=CELL)]
    )


def rows(spec):
    """{name: row index} of World L's species, and the compartment's and owner's node indices."""
    m = spec.model
    return (
        {s: i for i, s in enumerate(m.species_ids)},
        [c.id for c in m.cells].index(CELL),
        [c.id for c in m.extracellular].index(NODE),
    )
