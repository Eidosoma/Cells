"""FR-43 part 2's worlds: one pool written by two processes (docs/FR43_SHARED_INVENTORIES_DESIGN.md
§2; D315). Synthetic values throughout.

The pair (C2.1): the gene unit's polymerase-limited world (validation/gene_regulation/worlds
.polymerase_limited: transcription spends the nucleotide N, recharging makes N from the finite M
and ATP reserves) beside cells.operator.local_species_reactions@1 on N, its second writer:
- "sink": the second-order route N + X -> W (driven mass action, k in 1/(mM s)), a second spender
  of N whose rate k V c_N c_X = k n_N n_X / V reads the cell's volume;
- "source": X -> N (driven mass action, k in 1/s), a second producer of N spending a finite X.
X and W are neutral, impermeant inventory rows (secreted_species_fixtures' trace, diffusivity and
floor). The network's moieties balance its route (N {n: 1}, X {x: 1}, W {n: 1, x: 1}; the source's
X {n: 1}), and in the species registry W carries N's moieties (phosphorus 3, nucleoside 1), the
source's X likewise, so every route conserves the world's moieties too. N's standard potential is
the registry's (the shared row's one authority, species_registry.check_shared_rows), converted to
the network's c0 of 1 mM; X's is 0, W's N's.

For C2.4, each writer can be idle (network_multiplier 0, or gene_rates 0: every one of the gene
unit's scheduled rates zero), and each can be taken away (gene_alone, network_alone), the rows kept.
"""

import copy
import math

from cells.registry.inventory_species import add_inventory_species
from validation.gene_regulation import worlds as gw
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import species_reactions_fixtures as rfx

C0_mM = 1.0  # The network's standard concentration (mM).
COPIES = 10  # The gene's template copies (A1-M's sweep value).
X_mM = 5.0  # X's initial concentration in the cell (mM).
W_mM = 1e-6  # W's (mM): a product starting at a trace.
K_SINK = 1e-4  # 1/(mM s): N + X -> W.
K_SOURCE = 1e-4  # 1/s: X -> N.
KINDS = ("sink", "source")


def _rows(raw, kind):
    """X (and the sink's W) as inventory rows, with the registry's moieties for the network's
    products."""
    rows = {"X": X_mM} if kind == "source" else {"X": X_mM, "W": W_mM}
    for name, mM in rows.items():
        raw = add_inventory_species(
            raw,
            name,
            trace_mM=fx.TRACE_mM,
            diffusivity_m2_per_s=fx.D_S,
            floor_fmol=fx.FLOOR_FMOL,
            concentrations_mM={gw.CELL: mM},
        )
    carrier = "X" if kind == "source" else "W"  # The row that carries N's moieties.
    for moiety in raw["model"]["moieties"]:
        weight = moiety["weights"].get("N")
        if weight:
            moiety["weights"][carrier] = weight
    return raw


def _network(raw, kind, *, k, multiplier):
    m = raw["model"]
    entry = next(s for s in m["species"] if s["id"] == "N")
    mu_N = entry["standard_mu_RT"] + math.log(C0_mM / m["standard_concentration_mM"])
    if kind == "sink":
        species = [
            rfx.species("N", moieties={"n": 1}, mu=mu_N),
            rfx.species("X", moieties={"x": 1}, mu=0.0),
            rfx.species("W", moieties={"n": 1, "x": 1}, mu=mu_N),
        ]
        rate = K_SINK if k is None else k
        reactions = [
            rfx.mass_action("spend_N", {"cells": [gw.CELL]}, {"N": 1, "X": 1}, {"W": 1}, rate)
        ]
    else:
        species = [
            rfx.species("N", moieties={"n": 1}, mu=mu_N),
            rfx.species("X", moieties={"n": 1}, mu=mu_N),
        ]
        rate = K_SOURCE if k is None else k
        reactions = [rfx.mass_action("supply_N", {"cells": [gw.CELL]}, {"X": 1}, {"N": 1}, rate)]
    controls = rfx.always([r["id"] for r in reactions], multiplier)
    return rfx.with_reactions(raw, species, reactions, controls, c0=C0_mM)


def _horizon(raw, end, every):
    if end is None:
        return raw
    out = copy.deepcopy(raw)
    dt = out["execution"]["dt"]
    every = end if every is None else every
    out["experiment"]["end_time"] = float(end)
    out["experiment"]["observation_times"] = fx.grid_times(end, dt, every)
    out["execution"]["max_steps"] = int(math.ceil(end / dt)) + 8
    return out


def _idle_gene(raw):
    out = copy.deepcopy(raw)
    for control in out["experiment"]["polymerisation_controls"]:
        for change in control["schedule"]:
            change["value"] = 0.0
    return out


def pair(kind="sink", *, copies=COPIES, k=None, dt=0.5, end=None, every=None,
         network_multiplier=1.0, gene_rates=1.0):  # fmt: skip
    """The gene unit beside the D152 network on N (C2.1). end: a shorter horizon than A1-M's
    (observed every `every` s, default the end); gene_rates 0 sets every gene rate to zero."""
    if kind not in KINDS:
        raise ValueError(f"kind is one of {KINDS}")
    raw = _rows(gw.polymerase_limited(copies, dt=dt), kind)
    raw = _network(raw, kind, k=k, multiplier=network_multiplier)
    if gene_rates == 0.0:
        raw = _idle_gene(raw)
    elif gene_rates != 1.0:
        raise ValueError("gene_rates is 1 or 0")
    return _horizon(raw, end, every)


def gene_alone(kind="sink", *, copies=COPIES, dt=0.5, end=None, every=None):
    """The gene unit alone on the pair's rows (no network)."""
    return _horizon(_rows(gw.polymerase_limited(copies, dt=dt), kind), end, every)


def network_alone(kind="sink", *, copies=COPIES, k=None, dt=0.5, end=None, every=None):
    """The network alone on the pair's rows (the gene unit's operator and controls removed)."""
    raw = pair(kind, copies=copies, k=k, dt=dt)
    raw["model"]["operators"] = [
        o for o in raw["model"]["operators"] if o["law"] != gw.POLYMERISATION
    ]
    raw["experiment"].pop("polymerisation_controls", None)
    return _horizon(raw, end, every)


# ------------------------------------------------------------------ at changing volume (2B)

WATER = "cells.operator.ideal_osmosis_linear_compliance_water@1"
PF_M_S = 5e-4  # Osmotic permeability (m/s): the doubling probe's (design note §2.3).
DILUTION = 0.4  # The held bath's osmolytes, as a fraction of the cell's: the cell swells.
MAXIMUM_FRACTION = 3.0  # Water's maximum volume over the reference (a synthetic world).
AB_mM = 20.0  # C2.6's A and B in the cell (mM).
K_BIND = 0.05  # 1/s at c0: C2.6's passive A + B <-> C.
MU_C = -1.0  # mu°/RT of C at c0 (A's and B's 0).


def with_water_first(raw, *, pf_m_s=PF_M_S, dilution=DILUTION, maximum_fraction=MAXIMUM_FRACTION,
                     keep=()):  # fmt: skip
    """A frozen composite world in a swelling cell: water (cells.operator.ideal_osmosis_linear_compliance_water@1,
    no modulus or pressure offset) declared first, so the readers after it take its current
    volumes, and the held bath's species but `keep` diluted to `dilution` of their amounts."""
    from cells.definitions import pump_composite_spec as cs
    from validation.tissue import pump_water_fixtures as wfx

    out = copy.deepcopy(raw)
    inner = copy.deepcopy(out)
    m = inner["model"]
    m["id"] = m.pop("inner_model")
    m.pop("operators")
    for key in [k for k in inner["experiment"] if k.endswith("_controls")]:
        if key not in ("membrane_controls", "junction_controls", "pump_controls",
                       "calcium_pump_controls", "channel_controls"):  # fmt: skip
            inner["experiment"].pop(key)
    water = cs.frozen_definition(
        wfx.with_water(
            inner,
            pf_m_s=pf_m_s,
            bulk_modulus_Pa=0.0,
            pressure_offset_Pa=0.0,
            maximum_fraction=maximum_fraction,
        )  # fmt: skip
    )
    (block,) = water["model"]["operators"]
    out["model"]["operators"] = [block, *out["model"]["operators"]]
    out["experiment"]["water_controls"] = water["experiment"]["water_controls"]
    for bath in out["model"]["extracellular"]:
        if bath.get("reservoir", False):
            for name in bath["initial_amount_fmol"]:
                if name not in keep:
                    bath["initial_amount_fmol"][name] *= dilution
    return out


def swelling_pair(kind="sink", *, dt=0.01, end=40.0, every=1.0, **kwargs):
    """C2.8: the pair (pair()) in a swelling cell, water first."""
    return with_water_first(pair(kind, dt=dt, end=end, every=every), **kwargs)


def swelling_cell(*, network_multiplier=1.0, dt=0.01, end=40.0, every=0.5, **kwargs):
    """C2.5 to C2.7: one quiescent 1 pL cell (secreted_species_fixtures.world, its impermeant
    tracer S at 1 uM) with A and B at AB_mM and C at a trace, the passive A + B <-> C (ideal
    detailed balance, k_f = K_BIND at c0 = 1 mM, mu°/RT 0, 0 and MU_C; sum nu = -1, so the
    reaction moves the osmolarity and with it the volume), in a swelling cell. network_multiplier
    0 is C2.5's world: the network declared, every multiplier zero."""
    raw = fx.world(
        nodes=(), contacts=(), faces=(), dt=dt, end=end,
        observation_times=fx.grid_times(end, dt, every), concentrations_mM={"cell_0": 1e-3},
    )  # fmt: skip
    for name, mM in (("A", AB_mM), ("B", AB_mM), ("C", 1e-6)):
        raw = add_inventory_species(
            raw, name, trace_mM=fx.TRACE_mM, diffusivity_m2_per_s=fx.D_S,
            floor_fmol=fx.FLOOR_FMOL, concentrations_mM={"cell_0": mM},
        )  # fmt: skip
    species = [
        rfx.species("A", moieties={"a": 1}, mu=0.0),
        rfx.species("B", moieties={"b": 1}, mu=0.0),
        rfx.species("C", moieties={"a": 1, "b": 1}, mu=MU_C),
    ]
    reactions = [rfx.passive("bind", {"cells": ["cell_0"]}, {"A": 1, "B": 1}, {"C": 1}, K_BIND)]
    raw = rfx.with_reactions(raw, species, reactions, rfx.always(["bind"], network_multiplier))
    return with_water_first(raw, keep=(fx.SPECIES, "A", "B", "C"), **kwargs)


# ------------------------------------------------------------------ turnover, changing volume

TURNOVER_MAKE = 1.0  # fmol/s: S made in the cell, enough to move the volume (FR-65 §6.1).
TURNOVER_CLEAR = 1e-3  # 1/s: S's first-order clearance, P/k far above S while V moves (§4.1).
COUPLING_2 = "cells.operator.species_regulated_availability@2"


def swelling_turnover(*, make=TURNOVER_MAKE, clear=TURNOVER_CLEAR, network_multiplier=1.0,
                      dt=0.01, end=40.0, every=0.5, **kwargs):  # fmt: skip
    """FR-65 (docs/TURNOVER_CHANGING_VOLUME_DESIGN.md §6.1): the swelling cell (swelling_cell, water
    declared first, the network active unless network_multiplier 0) with
    cells.operator.scheduled_species_turnover@1 declared last, making the tracer S at `make` fmol/s
    and clearing it at `clear` /s in the cell from time 0. Turnover reads the cell's volume current
    at its split, so its booked work is the free-energy change at the swelling volume."""
    raw = swelling_cell(
        network_multiplier=network_multiplier, dt=dt, end=end, every=every, **kwargs
    )
    return fx.with_turnover(
        raw,
        [("make_s", "cell_0", "production"), ("clear_s", "cell_0", "clearance")],
        [("make_s", "cell_0", [(0.0, make)]), ("clear_s", "cell_0", [(0.0, clear)])],
    )


def swelling_a1(*, coupling=False, dt=0.5, end=None, every=60.0, **kwargs):
    """FR-65's A1 in a swelling cell: the gene regulation sheet's A1
    (validation/gene_regulation/worlds.a1: the gene unit, turnover of X, and the coupling's Hill
    factor of X on transcription's initiation) under water declared first (with_water_first).
    coupling False removes the coupling and its controls (the first build's world, X turnover's
    alone); with it, the coupling reads the current volume (FR-65's coupling step, §11)."""
    raw = gw.a1(dt=dt, end=end, every=every)
    if not coupling:
        operators = raw["model"]["operators"]
        raw["model"]["operators"] = [o for o in operators if o["law"] != COUPLING_2]
        for key in ("coupling_controls", "regulatory_writes"):
            raw["experiment"].pop(key, None)
    return with_water_first(raw, **kwargs)


# ------------------------------------------------------------------ beside the unit producer

UNIT_PRODUCER = "cells.operator.population_unit_turnover@1"
STATE = "cells.operator.membrane_entity_state@1"
LEAK = "kleak_0"  # The producer's population: gate-free K units on the gene cell's patch.
DENSITY = 1e13  # units/m^2: the population's reference density (validation/fr7's).
MOLECULES_PER_UNIT = 4  # nu: P molecules per unit.
K_ASSEMBLY, K_REMOVAL = 1e-3, 1e-3  # 1/s: the producer's assembly and removal rates.


def unit_pair(*, n_R=10, dt=0.5, end=None, every=None, k_a=K_ASSEMBLY, k_r=K_REMOVAL,
              gene_off=(), assembly_off=()):  # fmt: skip
    """2A's second pair (FR-43 / D315): the gene unit's ribosome-limited world
    (validation/gene_regulation/worlds.ribosome_limited: translation makes the neutral protein P
    from the held mRNA, drawing A and ATP; P's degradation returns A) beside the unit producer
    (cells.operator.population_unit_turnover@1), which consumes P as its precursor into the units of a gate-free K
    population on the cell's patch (cells.channel.kleak_always_open@1 at zero permeability: its units carry no
    current, so the membrane stays inert at the gene world's 0.5 s step whatever R5's largest
    units are), every unit removed at k_r. The gene unit adds P and the
    producer consumes it; P's registry potential is the shared row's one authority.
    gene_off, assembly_off: the times (s) at which each source's declared schedule switches it, off
    first, then on and off in turn (D349's restart row): tl's initiation rate, which makes P, and
    the route's assembly rate, which makes the units. P's degradation and the units' removal stay.
    """
    raw = gw.ribosome_limited(n_R, dt=dt)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    m["channels"] = [
        dict(
            id=LEAK,
            membrane_id=gw.PATCH,
            kinetic_law="cells.channel.kleak_always_open@1",
            max_permeability_m_per_s=0.0,  # Its units carry no current (below).
            abundance=1.0,
            initial_gate=[],
            permeant_ions=[dict(species_id="K", relative_permeability=1.0)],
        )
    ]
    e["channel_controls"] = [dict(channel_id=LEAK, schedule=[dict(time=0.0, availability=1.0)])]
    x["channel_capacity"] = 1
    state = dict(
        law=STATE,
        populations=[
            dict(
                channel_id=LEAK,
                functional_unit="kleak",
                catalogue=None,
                reference_density_per_m2=DENSITY,
            )  # fmt: skip
        ],
    )
    route = dict(
        id="assemble",
        population=LEAK,
        precursor="P",
        molecules_per_unit=MOLECULES_PER_UNIT,
        maturation_pools=0,
        maturation_time_s=None,
        initial_pool_units=[],
    )
    producer = dict(
        law=UNIT_PRODUCER, species=[dict(id="P", catalogue=None, evidence=None)], routes=[route]
    )
    m["operators"] = [*m["operators"], state, producer]
    e["unit_turnover_controls"] = [
        dict(
            route_id="assemble",
            schedule=[dict(time=0.0, assembly_rate_per_s=k_a, removal_rate_per_s=k_r)],
        )
    ]
    (initiation,) = (c for c in e["polymerisation_controls"] if c["route_id"] == "tl")
    (assembly,) = e["unit_turnover_controls"]
    for control, rate, times in (
        (initiation, "value", gene_off),
        (assembly, "assembly_rate_per_s", assembly_off),
    ):
        on = control["schedule"][0]
        control["schedule"] += [
            {**on, "time": float(t), rate: on[rate] if i % 2 else 0.0} for i, t in enumerate(times)
        ]
    return _horizon(raw, end, every)


# ------------------------------------------------------------------ the coupling beside water

# FR-65's coupling step (docs/TURNOVER_CHANGING_VOLUME_DESIGN.md §11): the coupling's version 1.1
# reads the current cell volume beside water declared first.
COUPLING_1 = "cells.operator.species_regulated_availability@1"
STATE_LAW = "cells.regulation.hill_regulated_two_state@1"
TURNOVER = "cells.operator.scheduled_species_turnover@1"
REACTIONS = "cells.operator.local_species_reactions@1"
REGULATOR, REGULATOR_mM = "R", 1e-3  # The water door's conserved neutral regulator: 1 uM.
DOOR_CHANNEL = "leak_0"  # A channel population at zero permeability: the regulation moves no ion.
DOOR_ON, DOOR_OFF = 1.0, 0.5  # 1/s: the water door's state, which relaxes within its horizon.
DOOR_K_S = 5.0  # mM: the self route's half-saturation of S, which turnover makes to about 10 mM.
DOOR_BASAL = 0.1
DOOR_HIGH = 10 * REGULATOR_mM  # mM: the operating range of a route of R, [0, DOOR_HIGH].


def with_regulator(raw, cell="cell_0", *, mM=REGULATOR_mM):
    """raw with the conserved neutral regulator R in `cell`: a trace species that nothing moves."""
    return add_inventory_species(
        raw, REGULATOR, trace_mM=fx.TRACE_mM, diffusivity_m2_per_s=fx.D_S,
        floor_fmol=fx.FLOOR_FMOL, concentrations_mM={cell: mM},
    )  # fmt: skip


def hill_coupling(name, target, source, *, law="hill_activation", k=REGULATOR_mM, n=1.0,
                  basal=DOOR_BASAL):  # fmt: skip
    """A coupling of the species `source`'s Hill factor on `target`."""
    return dict(
        id=name, target=target, source={"species": source}, law=law, half_saturation_mM=k,
        hill_coefficient=n, basal=basal,
    )  # fmt: skip


def inner_target(ids, *, version, high=DOOR_HIGH, control="channel"):
    """An inner target; version 2's declares its evaluation and its source's operating range."""
    target = dict(operator="inner", control=control, ids=list(ids), side=None)
    if version == 2:
        target.update(evaluation="step_view", operating_range=[0.0, high])
    return target


def routed_target(operator, control, ids, *, high=DOOR_HIGH):
    """Version 2's operator target: `operator`'s routable `control` on `ids`."""
    return dict(
        operator=operator, control=control, ids=list(ids), evaluation="target_half_steps",
        operating_range=[0.0, high],
    )  # fmt: skip


def with_coupling_block(raw, couplings, states=(), *, law=COUPLING_2, species=(REGULATOR,),
                        before=None):  # fmt: skip
    """raw with the coupling declared just before the first operator of law `before` (last when
    None), its couplings enabled from 0, and no regulatory write."""
    out = copy.deepcopy(raw)
    ops = out["model"]["operators"]
    block = dict(
        law=law, species=[dict(id=k, catalogue=None, evidence=None) for k in species],
        states=list(states), couplings=list(couplings),
    )  # fmt: skip
    at = len(ops) if before is None else next(i for i, o in enumerate(ops) if o["law"] == before)
    out["model"]["operators"] = [*ops[:at], block, *ops[at:]]
    out["experiment"]["coupling_controls"] = [
        dict(coupling_id=c["id"], schedule=[dict(time=0.0, enabled=1)]) for c in couplings
    ]
    out["experiment"]["regulatory_writes"] = []
    return out


def water_door(*, version=2, dt=0.01, end=10.0, every=0.5, network_multiplier=1.0):
    """FR-65's coupling step, T1 (§11.8): the swelling cell beside turnover of S
    (swelling_turnover: water first, the passive network, S made and cleared), with the conserved
    neutral regulator R, a K channel population at zero permeability (so the regulation moves no
    ion), and the coupling declared after water. Its routes: an instantaneous Hill factor of R on
    the population (the control view) and a state with a Hill input of R gating it (the split);
    and in version 2, Hill factors of R routed onto S's production and onto the binding
    reaction's multiplier, and S's own Hill inhibition on its production (self-moved: turnover
    moves S, so the composite evaluates it at the midpoint)."""
    raw = with_regulator(swelling_turnover(network_multiplier=network_multiplier, dt=dt, end=end,
                                           every=every))  # fmt: skip
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    m["channels"] = [
        dict(
            id=DOOR_CHANNEL,
            membrane_id=m["membranes"][0]["id"],
            kinetic_law="cells.channel.kleak_always_open@1",
            max_permeability_m_per_s=0.0,
            abundance=1.0,
            initial_gate=[],
            permeant_ions=[dict(species_id="K", relative_permeability=1.0)],
        )  # fmt: skip
    ]
    e["channel_controls"] = [
        dict(channel_id=DOOR_CHANNEL, schedule=[dict(time=0.0, availability=1.0)])
    ]
    x["channel_capacity"] = 1
    state = dict(
        id="s", law=STATE_LAW, cells=["cell_0"],
        inputs=[dict(law="hill_activation", species=REGULATOR, half_saturation_mM=REGULATOR_mM,
                     hill_coefficient=1.0)],
        on_rate_per_s=DOOR_ON, off_rate_per_s=DOOR_OFF, initial=0.5, crossing_level=None,
    )  # fmt: skip
    couplings = [
        hill_coupling("inst", inner_target([DOOR_CHANNEL], version=version), REGULATOR),
        dict(
            id="gate",
            target=inner_target([DOOR_CHANNEL], version=version, high=1.0),
            source={"state": "s"},
            law="state_fraction",
            basal=0.0,
        ),  # fmt: skip
    ]
    if version == 2:
        couplings += [
            hill_coupling("make", routed_target(TURNOVER, "turnover_rate", ["make_s"]), REGULATOR),
            hill_coupling(
                "bind",
                routed_target(REACTIONS, "reaction_multiplier", ["bind"]),
                REGULATOR,
                law="hill_inhibition",
            ),  # fmt: skip
            hill_coupling(
                "self",
                routed_target(TURNOVER, "turnover_rate", ["make_s"], high=1e3),
                fx.SPECIES,
                law="hill_inhibition",
                k=DOOR_K_S,
            ),  # fmt: skip
        ]
    law = COUPLING_1 if version == 1 else COUPLING_2
    species = (REGULATOR,) if version == 1 else (REGULATOR, fx.SPECIES)
    return with_coupling_block(raw, couplings, [state], law=law, species=species, before=REACTIONS)


def companion_world(kind, *, coupling=False):
    """The first build's companion world (FR-65 §3.6): turnover making and clearing S in the cell
    beside water and cells.operator.k_anion_symport_mass_action@1 ("symport") or
    cells.operator.scheduled_bath_composition@1 ("bath schedule"). With `coupling`, R in the cell
    and the coupling's Hill factor of R routed onto S's production, declared before turnover
    (§11.6: covered by argument, with a parse row each)."""
    from cells.definitions import pump_composite_spec as cs
    from validation.tissue import bath_schedule_fixtures as bfx
    from validation.tissue import pump_water_fixtures as wfx

    if kind == "symport":
        world = cs.frozen_definition(
            wfx.with_symport(
                wfx.with_water(wfx.heredity_cell("D", end_time=0.1), pf_m_s=5e-4), steepness=0.12
            )
        )
    else:
        world = bfx.water_world({"NaM": -10.0, "KM": 10.0})
    world = add_inventory_species(
        world, fx.SPECIES, trace_mM=fx.TRACE_mM, diffusivity_m2_per_s=fx.D_S,
        floor_fmol=fx.FLOOR_FMOL,
    )  # fmt: skip
    cell = world["model"]["cells"][0]["id"]
    if coupling:
        world = with_regulator(world, cell)
    world = fx.with_turnover(
        world,
        [("make_s", cell, "production"), ("clear_s", cell, "clearance")],
        [("make_s", cell, [(0.0, COMPANION_MAKE)]), ("clear_s", cell, [(0.0, COMPANION_CLEAR)])],
    )
    if not coupling:
        return world
    route = hill_coupling("make", routed_target(TURNOVER, "turnover_rate", ["make_s"]), REGULATOR)
    return with_coupling_block(world, [route], before=TURNOVER)


COMPANION_MAKE, COMPANION_CLEAR = 1e-6, 0.5  # fmol/s and 1/s: S moves a hundredfold in 0.1 s.


def swelling_arm_b(run, *, dt=0.01, end=10.0, every=2.5, window=(2.0, 4.0)):
    """FR-38 v2's arm B (the sheet's A1 with transcription's release, labelled or not) in a
    swelling cell (FR-65's coupling step, T2's labelled row): a short made-up B with its own
    horizon, window and output rows and the registered inputs otherwise, water declared first, its
    IDs translated, since its registered builders keep the IDs from before the move."""
    from dataclasses import replace

    from validation import id_table
    from validation.gene_regulation.fr38_v2 import worlds as w2

    f = replace(w2.ARM_B, horizon=float(end), window=tuple(window), every=float(every))
    return id_table.translate(with_water_first(w2.b(run, dt=dt, f=f)))
