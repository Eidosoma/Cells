"""The delivery world: a bath dose, uptake, an owned compartment, then a reaction (door S).

Door S's integration case (docs/SCOPED_COMPOSITION_DESIGN.md §5; D176): FR-1's first admissible
delivery world (docs/FEATURE_REQUESTS.md, FR-1) with D152's reactions in the compartment instead
of turnover's clearance. Without door S, D152's reactions and the bath schedule refuse each other
(both name extracellular_amount_reference: the schedule changes it at its held baths, the
reactions read it at finite nodes); with it they meet on no slot.

All values are synthetic and generic. The base is D150's quiescent species-only world
(secreted_species_fixtures.world: passive cells, zero ion permeability on every patch, every node at
the bath's ion composition with a zero charge anchor), so the energy flows and bounds are the
neutral species' own.
* Topology: cell_0 (1 pL) with its wall patch on the held bath `bath`; its contact patch contact_0
  on the finite node ecs_0 (1 pL), which face_0 joins to the bath (kappa/V = 1/s); and its second
  contact patch `bound_0` on the finite node comp_0 (0.5 pL), which no face names. comp_0 is the
  compartment `vesicle_0`, owned by cell_0 and bounded by bound_0.
* Species: the ions, the cargo S (D150's species) and its product P, an inventory species declared
  by the engine's helper. Both start resolved (DOSE_FROM over the trace); S is the moiety X, P = X
  at a lower standard potential.
* Operators, in the requester's order unless `bath_last`: FR-10's bath schedule (the cargo stepped
  at the bath from c0 to RATIO c0 at DOSE_TIME, a measured step: ratio 100 at 1e-3 mM, ARS at 1 ms,
  face rate 1/s), FR-1's declaration, D150's exchange (uptake: a first-order import on contact_0
  from ecs_0 at 0.5/s, declared as its uptake velocity k_u = 0.5/s x V / A; loading: a first-order
  export on bound_0 into comp_0 at 0.2/s), and D152's reactions (S -> P, first-order mass action,
  in comp_0).
"""

from cells.registry.inventory_species import add_inventory_species
from validation.tissue import bath_schedule_fixtures as bfx
from validation.tissue import compartment_fixtures as cfx
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import species_reactions_fixtures as rfx

BATH, NODE, COMPARTMENT, OWNER = "bath", "ecs_0", "comp_0", "cell_0"
UPTAKE, BOUND, UPTAKE_ROUTE, LOAD_ROUTE = "contact_0", "bound_0", "uptake", "load"
C0, RATIO, DOSE_TIME = 1e-5, 100.0, 0.01  # mM at the bath; the step's ratio; s.
LOAD_RATE, REACTION_RATE = 0.2, 1.0  # 1/s.
# A first-order import's rate is an uptake velocity (m/s), k_u A / V per second: 0.5/s from 1 pL
# through the contact patch's area.
UPTAKE_VELOCITY = 0.5 * 1.0e-15 / fx.CONTACT_AREA_M2
PROFILE = dict(bath=C0, ecs_0=0.9 * C0, cell_0=0.5 * C0, comp_0=0.2 * C0)  # S, resolved.
PRODUCT_mM = 0.1 * C0  # P in comp_0, resolved; the trace elsewhere.


def delivery_world(*, dt=1e-3, end=0.03, bath_last=False, observation_times=None):
    """The delivery world (module docstring), every step observed unless `observation_times`."""
    raw = fx.world(
        cells=((OWNER, 1.0),),
        nodes=((NODE, 1.0), (COMPARTMENT, 0.5)),
        baths=(BATH,),
        contacts=((UPTAKE, OWNER, NODE), (BOUND, OWNER, COMPARTMENT)),
        faces=(("face_0", NODE, BATH, 1e-10, 1e-5),),
        dt=dt,
        end=end,
        observation_times=observation_times or fx.grid_times(end, dt, dt),
        concentrations_mM=PROFILE,
    )
    raw = add_inventory_species(
        raw,
        "P",
        trace_mM=fx.TRACE_mM,
        diffusivity_m2_per_s=fx.D_S,
        floor_fmol=fx.FLOOR_FMOL,
        concentrations_mM={COMPARTMENT: PRODUCT_mM},
    )
    dose = [(DOSE_TIME, (BATH,), {"cargo": (RATIO - 1.0) * C0})]
    scheduled = bfx.with_bath_schedule(raw, (BATH,), bfx.CARGO, dose)
    schedule_block = scheduled["model"]["operators"][-1]
    raw = cfx.with_compartments(
        scheduled, [cfx.compartment("vesicle_0", COMPARTMENT, BOUND, OWNER, label="vesicle")]
    )
    raw = fx.with_exchange(
        raw,
        [
            (UPTAKE_ROUTE, UPTAKE, "import", "first_order"),
            (LOAD_ROUTE, BOUND, "export", "first_order"),
        ],
        [
            (UPTAKE_ROUTE, OWNER, [(0.0, UPTAKE_VELOCITY)]),
            (LOAD_ROUTE, OWNER, [(0.0, LOAD_RATE)]),
        ],
    )
    species = [
        rfx.species("S", moieties={"X": 1}),
        rfx.species("P", moieties={"X": 1}, mu=-1.0),
    ]
    reaction = rfx.mass_action(
        "conversion", {"outside": [COMPARTMENT]}, {"S": 1}, {"P": 1}, REACTION_RATE
    )
    raw = rfx.with_reactions(raw, species, [reaction], rfx.always(["conversion"]))
    if bath_last:
        operators = raw["model"]["operators"]
        operators.remove(schedule_block)
        operators.append(schedule_block)
    return raw
