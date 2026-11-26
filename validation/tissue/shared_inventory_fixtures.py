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
    coupling False removes the coupling and its controls: its current-volume reads are FR-65's
    second step (§3.8), so the first build runs A1 without it, X turnover's alone."""
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
