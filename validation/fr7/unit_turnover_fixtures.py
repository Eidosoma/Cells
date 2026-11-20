"""Small worlds for population_unit_turnover@1 (FR-7's unit producer).

All values are synthetic. The base world is one heredity cell facing its held bath
(validation/tissue/pump_water_fixtures.heredity_cell: its pump, and Kir and NaV populations on one
patch). Every population is declared in membrane_entity_state@1 at one reference density. A
neutral precursor species is declared by the engine's helper (cells.registry.inventory_species):
loaded in the cell at a resolved level and at a trace elsewhere.

* cell: that composite definition, with the membrane state and no producer;
* route, with_producer: a route entry, and the operator's block with its schedule;
* with_supply: D150's turnover supplying the precursor in the cell, the second writer of its row;
* with_template_route: a template species in the cell, and species_regulated_availability@2
  routing a Hill factor of it onto the producer's assembly rate (B1′), declared before it.
"""

import copy

from cells.definitions import pump_composite_spec as cs
from cells.registry.inventory_species import add_inventory_species
from validation.tissue import pump_water_fixtures as wfx

LAW = "population_unit_turnover@1"
STATE = "membrane_entity_state@1"
TURNOVER = "scheduled_species_turnover@1"
COUPLING_2 = "species_regulated_availability@2"
TEMPLATE = "template"
PRECURSOR = "subunit"  # The heredity cell already declares a species P.
CELL = "cell_0"
DENSITY = 1e13  # units/m^2: every population's reference density (10 per µm²).
PRECURSOR_mM = 5e-5  # The loaded pool, synthetic: about 1.7 units per declared kir_0 unit at ν = 4.
TRACE_mM = 1e-9
FLOOR_FMOL = 1e-20
DIFFUSIVITY = 1e-10  # m^2/s; the cell has no face, so it moves nothing here.


def identity(name=PRECURSOR):
    return [dict(id=name, catalogue=None, evidence=None)]


SECOND = "leak_1"  # A second gate-free K population on the same patch, at half the abundance.


def leak_cell(raw):
    """raw's heredity cell made pump-free with gate-free K populations, the coupling operator's
    qualified scope: kir_0 becomes kleak_always_open@1 (no gate), a second such population leak_1
    joins it at half its abundance, and nav_0 and the pump are dropped."""
    out = copy.deepcopy(raw)
    m, e = out["model"], out["experiment"]
    kir = next(c for c in m["channels"] if c["id"] == "kir_0")
    kir.update(kinetic_law="kleak_always_open@1", initial_gate=[])
    second = copy.deepcopy(kir)
    second.update(id=SECOND, abundance=0.5 * kir["abundance"])
    m["channels"] = [kir, second]
    for patch in m["membranes"]:
        patch["pump"] = None
    e["channel_controls"] = [g for g in e["channel_controls"] if g["channel_id"] == "kir_0"]
    e["channel_controls"].append(
        dict(channel_id=SECOND, schedule=[dict(time=0.0, availability=1.0)])
    )
    e["pump_controls"] = []
    out["execution"]["channel_capacity"] = 2
    return out


def cell(*, end=0.03, dt=1e-3, observation_times=None, precursor_mM=PRECURSOR_mM, leak=True):
    """The heredity cell with the precursor loaded in its cell and every population in the
    membrane state, observed at every step unless observation_times is given; with leak, the
    pump-free gate-free cell (leak_cell)."""
    raw = wfx.heredity_cell("H", dt=dt, end_time=end)
    if leak:
        raw = leak_cell(raw)
    steps = int(round(end / dt))
    raw["experiment"]["observation_times"] = (
        list(observation_times)
        if observation_times is not None
        else [k * dt for k in range(steps)] + [end]
    )
    raw = add_inventory_species(
        raw,
        PRECURSOR,
        trace_mM=TRACE_mM,
        diffusivity_m2_per_s=DIFFUSIVITY,
        floor_fmol=FLOOR_FMOL,
        concentrations_mM={CELL: precursor_mM},
    )
    raw = cs.frozen_definition(raw)
    raw["model"]["operators"] = [
        dict(
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
    ]
    return raw


def route(name, population, *, nu=4, pools=0, tau=None, precursor=PRECURSOR):
    """A route entry, every key explicit."""
    return dict(
        id=name,
        population=population,
        precursor=precursor,
        molecules_per_unit=nu,
        maturation_pools=pools,
        maturation_time_s=tau,
    )


def with_producer(raw, routes, controls, *, species=None):
    """routes: route entries; controls: {route id: [(time, k_a, k_r), ...]}."""
    out = copy.deepcopy(raw)
    out["model"]["operators"].append(
        dict(law=LAW, species=species or identity(), routes=list(routes))
    )
    out["experiment"]["unit_turnover_controls"] = [
        dict(
            route_id=k,
            schedule=[
                dict(time=t, assembly_rate_per_s=a, removal_rate_per_s=r) for t, a, r in changes
            ],
        )
        for k, changes in controls.items()
    ]
    return out


def with_supply(raw, changes, *, node=CELL, name="supply"):
    """D150's turnover producing the precursor at `node`; changes: [(time, fmol/s), ...]. Placed
    before the producer, so its half-steps run first."""
    out = copy.deepcopy(raw)
    operators = out["model"]["operators"]
    block = dict(
        law=TURNOVER,
        species=identity(),
        routes=[dict(id=name, species=PRECURSOR, node=node, kind="production")],
        templates=[],
    )
    at = next((i for i, op in enumerate(operators) if op["law"] == LAW), len(operators))
    operators.insert(at, block)
    out["experiment"]["turnover_controls"] = [
        dict(route_id=name, carrier_id=node, schedule=[dict(time=t, rate=v) for t, v in changes])
    ]
    return out


def with_template_route(
    raw,
    route_ids=("kir_units",),
    *,
    template_mM=1e-3,
    half_saturation_mM=1e-3,
    hill_coefficient=2.0,
    basal=0.1,
    operating_range=(0.0, 1.0),
    enabled=1,
    coupling_first=True,
):
    """raw (with a producer) and a template species loaded in the cell, with @2 routing a Hill
    activation of its concentration onto the producer's assembly rate of `route_ids`, declared
    before the producer (coupling_first; a route's source precedes its target)."""
    out = add_inventory_species(
        raw,
        TEMPLATE,
        trace_mM=TRACE_mM,
        diffusivity_m2_per_s=DIFFUSIVITY,
        floor_fmol=FLOOR_FMOL,
        concentrations_mM={CELL: template_mM},
    )
    block = dict(
        law=COUPLING_2,
        species=identity(TEMPLATE),
        states=[],
        couplings=[
            dict(
                id="c_template",
                target=dict(
                    operator=LAW,
                    control="unit_assembly_rate",
                    ids=list(route_ids),
                    evaluation="target_half_steps",
                    operating_range=list(operating_range),
                ),
                source={"species": TEMPLATE},
                law="hill_activation",
                half_saturation_mM=half_saturation_mM,
                hill_coefficient=hill_coefficient,
                basal=basal,
            )
        ],
    )
    operators = out["model"]["operators"]
    at = next(i for i, op in enumerate(operators) if op["law"] == LAW)
    operators.insert(at if coupling_first else at + 1, block)
    out["experiment"]["coupling_controls"] = [
        dict(coupling_id="c_template", schedule=[dict(time=0.0, enabled=enabled)])
    ]
    out["experiment"]["regulatory_writes"] = []
    return out
