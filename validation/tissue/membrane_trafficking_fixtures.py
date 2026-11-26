"""Small worlds for cells.operator.scheduled_membrane_trafficking@1 (FR-2 version 1, MEMBRANE_RETRIEVAL_DESIGN).

All values are synthetic (D152 §2.4), built on independent heredity cells
(surface_pump_v3_fixtures.heredity_cells). Each cell has:
- a patch membrane_i facing its held bath bath_i, with a Na/K pump;
- Kir2.1 and NaV1.2 populations, kir_i and nav_i.

The builders:
* pooled_cells: n cells, each with a lumped receiving pool (D1), declared with the world.
  - The pool is the finite face-free node pool_i at the bath's composition, with a zero charge
    anchor, so V_b starts at 0.
  - It is bounded by pool_membrane_i: no route on it (refusal 4), its area a seed of SEED of
    membrane_i's at membrane_i's specific capacitance.
  - It is declared as cell_i's FR-1 compartment endosome_i.
  - Membrane state declares every population at DENSITY.
* route and with_trafficking: a route's declaration entry and the operator's block with its
  schedules. Floors and rates are given as fractions of the declared areas.
* uptake: pooled_cells with one route per cell, membrane_i into endosome_i.
* cycle: one cell for 5 ms, observed every step: retrieval, then recycling from CYCLE_CHANGE.
"""

import copy
import math

from cells.definitions import pump_composite_spec as cs
from cells.laws.electrochemistry import CHARGE_PER_FMOL
from validation.tissue import surface_pump_v3_fixtures as v3fx

LAW = "cells.operator.scheduled_membrane_trafficking@1"
STATE = "cells.operator.membrane_entity_state@1"
COMPARTMENTS = "cells.operator.cell_owned_compartments@1"
DT = 1e-3
END = 0.004
DENSITY = 1e13  # Every population's reference density (units/m^2), as the insertion fixtures'.
SEED = 0.05  # The pool's declared area, as a fraction of the plasma patch's.
POOL_pL = 0.05  # The pool's volume.
CARRIERS = {"K": 0.5, "Na": 0.5}  # The plate charge's carriers (declared transference numbers).


def membrane_state(raw):
    """The cells.operator.membrane_entity_state@1 block declaring every population of raw at DENSITY."""
    return dict(
        law=STATE,
        populations=[
            dict(
                channel_id=c["id"],
                functional_unit=c["id"].split("_")[0],
                catalogue=None,
                reference_density_per_m2=DENSITY,
            )
            for c in raw["model"]["channels"]
        ],
    )


def add_pool(raw, i, *, seed=SEED, pool_pL=POOL_pL):
    """Cell i's pool: node pool_i at its bath's composition with a zero charge anchor, and its
    bounding patch pool_membrane_i (module docstring), on an inner definition, in place."""
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    plasma = next(p for p in m["membranes"] if p["id"] == f"membrane_{i}")
    bath = next(o for o in m["extracellular"] if o["id"] == plasma["outside"])
    z = {s["id"]: s["valence"] for s in m["species"]}
    amounts = {s: a / bath["volume_pL"] * pool_pL for s, a in bath["initial_amount_fmol"].items()}
    m["extracellular"].append(
        dict(
            id=f"pool_{i}",
            volume_pL=pool_pL,
            initial_amount_fmol=amounts,
            fixed_charge_equivalent_fmol=-math.fsum(z[s] * amounts[s] for s in amounts),
            initial_charge_C=0.0,
            reservoir=False,
            boundary_potential_V=0.0,
        )
    )
    patch = copy.deepcopy(plasma)
    area = seed * plasma["area_m2"]
    patch.update(
        id=f"pool_membrane_{i}",
        outside=f"pool_{i}",
        pump=None,
        calcium_pump=None,
        area_m2=area,
        capacitance_F=plasma["capacitance_F"] / plasma["area_m2"] * area,
        permeability_m_per_s={s: 0.0 for s in plasma["permeability_m_per_s"]},
    )
    m["membranes"].append(patch)
    e["membrane_controls"].append(
        dict(membrane_id=patch["id"], schedule=[dict(time=0.0, availability=1.0)])
    )
    x.update(
        extracellular_capacity=x["extracellular_capacity"] + 1,
        membrane_capacity=x["membrane_capacity"] + 1,
    )
    return raw


def compartment(i):
    return dict(
        id=f"endosome_{i}",
        node=f"pool_{i}",
        patch=f"pool_membrane_{i}",
        owner=f"cell_{i}",
        label="lumped receiving pool",
        reference=None,
    )


def add_cleft(raw, i, *, fraction=0.1, cleft_pL=0.01, access_area_m2=1e-14, voltage_V=None):
    """Cell i's second patch furrow_i, `fraction` of membrane_i's area at its specific capacitance
    and leak, on a finite node cleft_i at the bath's composition, joined to the bath by the access
    face access_i (as membrane_insertion_fixtures' cleft cell), in place. Retrieval from furrow_i
    draws from a free node. A cleft with no charge floats with its cell (its face holds no charge
    in the capacitor field), so its charge anchor is -C_f voltage_V, which gives the furrow that
    voltage; by default the heredity cell's own."""
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    plasma = next(p for p in m["membranes"] if p["id"] == f"membrane_{i}")
    bath = next(o for o in m["extracellular"] if o["id"] == plasma["outside"])
    z = {s["id"]: s["valence"] for s in m["species"]}
    amounts = {s: a / bath["volume_pL"] * cleft_pL for s, a in bath["initial_amount_fmol"].items()}
    furrow = copy.deepcopy(plasma)
    area = fraction * plasma["area_m2"]
    voltage = v3fx.HEREDITY_STATES["H"][0] if voltage_V is None else voltage_V
    charge = -plasma["capacitance_F"] / plasma["area_m2"] * area * voltage
    m["extracellular"].append(
        dict(
            id=f"cleft_{i}",
            volume_pL=cleft_pL,
            initial_amount_fmol=amounts,
            fixed_charge_equivalent_fmol=charge / CHARGE_PER_FMOL
            - math.fsum(z[s] * amounts[s] for s in amounts),
            initial_charge_C=charge,
            reservoir=False,
            boundary_potential_V=0.0,
        )
    )
    furrow.update(
        id=f"furrow_{i}",
        outside=f"cleft_{i}",
        pump=None,
        calcium_pump=None,
        area_m2=area,
        capacitance_F=plasma["capacitance_F"] / plasma["area_m2"] * area,
    )
    m["membranes"].append(furrow)
    m["faces"].append(
        dict(
            id=f"access_{i}",
            sender=f"cleft_{i}",
            receiver=bath["id"],
            area_m2=access_area_m2,
            length_m=1e-2,
            diffusivity_m2_per_s={s: 1e-9 for s in amounts},
            law="cells.route.logmean_electrodiffusion@1",
        )
    )
    e["membrane_controls"].append(
        dict(membrane_id=furrow["id"], schedule=[dict(time=0.0, availability=1.0)])
    )
    x.update(
        extracellular_capacity=x["extracellular_capacity"] + 1,
        membrane_capacity=x["membrane_capacity"] + 1,
        face_capacity=x["face_capacity"] + 1,
    )
    return raw


def pooled_cells(
    n=1,
    *,
    end=END,
    observation_times=None,
    solver=None,
    seed=SEED,
    pool_pL=POOL_pL,
    bath_V=0.0,
    cleft=False,
    cleft_pL=0.01,
):
    """n heredity cells, each with its pool, membrane state and the compartments' declaration;
    bath_V: every held bath's potential; cleft: each cell also has its furrow on a cleft of
    cleft_pL."""
    state = v3fx.HEREDITY_STATES["H"][:4]
    options = {} if solver is None else dict(solver=solver)
    base = v3fx.heredity_cells(
        [state] * n,
        dt=DT,
        end_time=end,
        observation_times=list(observation_times or [0.0, end]),
        **options,
    )
    for bath in base["model"]["extracellular"]:
        bath["boundary_potential_V"] = bath_V
    for i in range(n):
        add_pool(base, i, seed=seed, pool_pL=pool_pL)
        if cleft:
            add_cleft(base, i, cleft_pL=cleft_pL)
    raw = cs.frozen_definition(base)
    raw["model"]["operators"] = [
        membrane_state(raw),
        dict(law=COMPARTMENTS, compartments=[compartment(i) for i in range(n)]),
    ]
    return raw


def patch(raw, name):
    return next(p for p in raw["model"]["membranes"] if p["id"] == name)


def route(
    raw,
    i=0,
    *,
    rid=None,
    plasma=None,
    compartment_id=None,
    carriers=None,
    plasma_floor=0.5,
    pool_floor=0.5,
    retrieval=None,
    recycling=None,
    internalised=None,
):
    """Cell i's route entry: membrane_i into endosome_i, floors as fractions of the declared
    areas, and every enrichment 1 and record 0 unless given ({channel: value})."""
    plasma = plasma or f"membrane_{i}"
    channels = [c["id"] for c in raw["model"]["channels"] if c["membrane_id"] == plasma]
    pool = patch(raw, f"pool_membrane_{i}")
    return dict(
        id=rid or f"uptake_{i}",
        plasma_patch=plasma,
        compartment=compartment_id or f"endosome_{i}",
        carriers=dict(CARRIERS if carriers is None else carriers),
        plasma_area_floor_m2=plasma_floor * patch(raw, plasma)["area_m2"],
        pool_area_floor_m2=pool_floor * pool["area_m2"],
        retrieval_enrichment=dict(retrieval or dict.fromkeys(channels, 1.0)),
        recycling_enrichment=dict(recycling or dict.fromkeys(channels, 1.0)),
        internalised_units=dict(internalised or dict.fromkeys(channels, 0.0)),
    )


def schedule(rid, retrieval, recycling=((0.0, 0.0),)):
    """A route's two rate schedules, [(time, rate in m^2/s), ...] each."""
    return dict(
        route_id=rid,
        retrieval=[dict(time=t, rate_m2_per_s=r) for t, r in retrieval],
        recycling=[dict(time=t, rate_m2_per_s=r) for t, r in recycling],
    )


def with_trafficking(raw, routes, schedules):
    out = copy.deepcopy(raw)
    out["model"]["operators"].append(dict(law=LAW, routes=[dict(r) for r in routes]))
    out["experiment"]["trafficking_controls"] = [dict(s) for s in schedules]
    return out


def rate(raw, i=0, fraction=0.1, *, over=END):
    """The rate (m^2/s) that moves `fraction` of membrane_i's declared area over `over` s."""
    return fraction * patch(raw, f"membrane_{i}")["area_m2"] / over


def uptake(n=1, *, retrieval=0.1, recycling=0.0, end=END, **kwargs):
    """pooled_cells(n) with each cell's route at constant rates, given as the fraction of the
    plasma area moved over the run."""
    raw = pooled_cells(n, end=end, **kwargs)
    routes = [route(raw, i) for i in range(n)]
    schedules = [
        schedule(
            r["id"],
            [(0.0, rate(raw, i, retrieval, over=end))],
            [(0.0, rate(raw, i, recycling, over=end))],
        )
        for i, r in enumerate(routes)
    ]
    return with_trafficking(raw, routes, schedules)


CYCLE_CHANGE = 0.002  # s: retrieval until here, then recycling.
CYCLE_END = 0.005
CYCLE_TIMES = [0.0, 0.001, 0.002, 0.003, 0.004, CYCLE_END]
CYCLE_E = {"kir_0": 1.0, "nav_0": 0.5}  # Retrieval enrichments.
CYCLE_E_R = {"kir_0": 2.0, "nav_0": 1.0}  # Recycling enrichments.


def cycle(retrieval=0.1, recycling=0.3):
    """One cell for CYCLE_END, observed every step: retrieval at `retrieval` of the plasma area
    per ms until CYCLE_CHANGE, then recycling at `recycling` of the pool's declared area per ms,
    with the enrichments CYCLE_E and CYCLE_E_R."""
    raw = pooled_cells(1, end=CYCLE_END, observation_times=CYCLE_TIMES)
    entry = route(raw, 0, retrieval=CYCLE_E, recycling=CYCLE_E_R)
    plasma = patch(raw, "membrane_0")["area_m2"]
    pool = patch(raw, "pool_membrane_0")["area_m2"]
    rates = (retrieval * plasma / DT, recycling * pool / DT)
    plan = schedule(
        entry["id"],
        [(0.0, rates[0]), (CYCLE_CHANGE, 0.0)],
        [(0.0, 0.0), (CYCLE_CHANGE, rates[1])],
    )
    return with_trafficking(raw, [entry], [plan])
