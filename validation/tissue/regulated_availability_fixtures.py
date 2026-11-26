"""Small worlds for cells.operator.species_regulated_availability@1 (coupling out of the inventory, D155 item 1).

All values are synthetic. The base world is the seven-cell heredity sheet
(cell_replacement_fixtures.heredity_sheet, radius 1, its centre cell written D): pumps, Kir and
NaV populations, gated junctions and a held bath per cell, so the ions move and junction and
channel availabilities matter electrically. A neutral regulator R is declared by the engine's helper
(cells.registry.inventory_species) at a resolved level, far above its resolution floor: five species.

* sheet: the composite definition with no operator;
* with_coupling: the operator's block and its two schedules;
* state, coupling, hill_coupling: declaration entries (every key explicit); frozen and fraction:
  a state that never moves and a coupling F = s on it (an exactly representable factor);
* schedule_junction, schedule_channel: one element's availability held at a value from time 0;
* differing: the @3 state fields and observation columns in which two runs are not bitwise equal;
* with_turnover: D150's turnover clearing R in one cell (a moving, impermeant source).
"""  # noqa: E501

import copy

from cells.definitions import pump_composite_spec as cs
from cells.registry.inventory_species import add_inventory_species
from validation.tissue import cell_replacement_fixtures as rfx
from validation.tissue import secreted_species_fixtures as sfx

LAW = "cells.operator.species_regulated_availability@1"
STATE_LAW = "cells.regulation.hill_regulated_two_state@1"
REGULATOR = "R"
REGULATOR_mM = 1e-3
FLOOR_FMOL = 1e-20
D_REGULATOR = 1e-10


def sheet(
    *, end=0.02, dt=1e-3, observation_times=None, regulator_mM=REGULATOR_mM, solver=None, extra=0
):
    """The seven-cell sheet with R declared (five species), and `extra` more neutral species X0,
    X1, ... at R's level (the cap counts every species); `solver` as the sheet's (None: its IMEX
    default; "rk4" needs dt near 2.5e-6, @3's explicit bound on this sheet)."""
    raw = rfx.heredity_sheet(radius=1, disc=0, dt=dt, end_time=end, solver=solver)
    times = observation_times or sfx.grid_times(end, dt, end / 4)
    raw["experiment"]["observation_times"] = list(times)
    for name in (REGULATOR, *(f"X{k}" for k in range(extra))):
        raw = add_inventory_species(
            raw,
            name,
            trace_mM=regulator_mM,
            diffusivity_m2_per_s=D_REGULATOR,
            floor_fmol=FLOOR_FMOL,
        )
    return cs.frozen_definition(raw)


def apart(keep, *, end=0.02, dt=1e-3, extra=()):
    """The sheet restricted to the cells `keep` (no junction may join them): each keeps its
    membrane, held bath, Kir and NaV populations and pump, with every schedule and capacity to
    match; R declared, then `extra` neutral species (name, trace mM). A6's world."""
    raw = rfx.heredity_sheet(radius=1, disc=0, dt=dt, end_time=end)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    if any(j["sender"] in keep and j["receiver"] in keep for j in m["junctions"]):
        raise ValueError("apart() keeps cells no junction joins")
    m["cells"] = [c for c in m["cells"] if c["id"] in keep]
    m["membranes"] = [p for p in m["membranes"] if p["inside"] in keep]
    outside = {p["outside"] for p in m["membranes"]}
    m["extracellular"] = [o for o in m["extracellular"] if o["id"] in outside]
    m["junctions"] = []
    membranes = {p["id"] for p in m["membranes"]}
    m["channels"] = [c for c in m["channels"] if c["membrane_id"] in membranes]
    pumps = {p["pump"]["id"] for p in m["membranes"] if p.get("pump")}
    kept = dict(
        membrane_controls=("membrane_id", membranes),
        junction_controls=("junction_id", set()),
        channel_controls=("channel_id", {c["id"] for c in m["channels"]}),
        pump_controls=("pump_id", pumps),
    )
    for key, (id_key, ids) in kept.items():
        e[key] = [g for g in e[key] if g[id_key] in ids]
    x.update(
        capacity=len(m["cells"]),
        extracellular_capacity=len(m["extracellular"]),
        membrane_capacity=len(m["membranes"]),
        edge_capacity=0,
        channel_capacity=len(m["channels"]),
    )
    e["observation_times"] = list(sfx.grid_times(end, dt, end / 4))
    for name, trace in ((REGULATOR, REGULATOR_mM), *extra):
        raw = add_inventory_species(
            raw, name, trace_mM=trace, diffusivity_m2_per_s=D_REGULATOR, floor_fmol=FLOOR_FMOL
        )
    return cs.frozen_definition(raw)


def identities(names):
    return [dict(id=n, catalogue=None, evidence=None) for n in names]


def state(name, cells, inputs, *, on=0.0, off=0.0, initial=0.0, level=None):
    """inputs: (law, species, K mM, n)."""
    return dict(
        id=name,
        law=STATE_LAW,
        cells=list(cells) if cells != "all" else "all",
        inputs=[
            dict(law=law, species=s, half_saturation_mM=k, hill_coefficient=n)
            for law, s, k, n in inputs
        ],
        on_rate_per_s=on,
        off_rate_per_s=off,
        initial=initial,
        crossing_level=level,
    )


def coupling(name, control, ids, source, law, *, side=None, basal=0.0):
    """source: ("state", id) or ("species", id); for a species source use hill_coupling."""
    return dict(
        id=name,
        target=dict(operator="inner", control=control, ids=list(ids), side=side),
        source={source[0]: source[1]},
        law=law,
        basal=basal,
    )


def hill_coupling(name, control, ids, species, law, k, n, *, side=None, basal=0.0):
    entry = coupling(name, control, ids, ("species", species), law, side=side, basal=basal)
    entry.update(half_saturation_mM=k, hill_coefficient=n)
    return entry


def with_coupling(raw, *, species=(), states=(), couplings=(), switches=None, writes=()):
    """switches: {coupling id: [(time, 0 or 1), ...]} (default enabled from 0); writes:
    (state id, cell id, time, value)."""
    out = copy.deepcopy(raw)
    out["model"]["operators"].append(
        dict(law=LAW, species=identities(species), states=list(states), couplings=list(couplings))
    )
    switches = dict(switches or {})
    out["experiment"]["coupling_controls"] = [
        dict(
            coupling_id=c["id"],
            schedule=[dict(time=t, enabled=v) for t, v in switches.get(c["id"], [(0.0, 1)])],
        )
        for c in couplings
    ]
    out["experiment"]["regulatory_writes"] = [
        dict(state_id=s, cell_id=c, time=t, value=v) for s, c, t, v in writes
    ]
    return out


def _hold(raw, key, id_key, element, availability):
    out = copy.deepcopy(raw)
    for group in out["experiment"][key]:
        if group[id_key] == element:
            group["schedule"] = [dict(time=0.0, availability=availability)]
            return out
    raise KeyError(element)


def schedule_junction(raw, junction_id, availability):
    return _hold(raw, "junction_controls", "junction_id", junction_id, availability)


def schedule_channel(raw, channel_id, availability):
    return _hold(raw, "channel_controls", "channel_id", channel_id, availability)


def frozen(name, cells, value):
    """A regulatory state that never moves (k_on = k_off = 0) at `value` (it reads R)."""
    return state(name, cells, [("hill_activation", REGULATOR, 1e-3, 1.0)], initial=value)


def fraction(name, control, ids, state_id, *, side=None):
    """A coupling F = s of a state on `ids` of `control` (b = 0)."""
    return coupling(name, control, ids, ("state", state_id), "state_fraction", side=side)


SHARED_JUNCTION, SHARED_CHANNEL = "junction_0", "kir_3"  # cell_0 (H) to cell_3 (D); cell_3's Kir.
SHARED_COUPLINGS = ("a", "b", "d", "k")


def scheduled(*, junction=1.0, channel=1.0, end=0.03, dt=1e-3, solver=None, extra=0):
    """The sheet without the operator, junction_0 and kir_3 held at the given availabilities."""
    raw = sheet(end=end, dt=dt, solver=solver, extra=extra)
    raw = schedule_junction(raw, SHARED_JUNCTION, junction)
    return schedule_channel(raw, SHARED_CHANNEL, channel)


def shared_structure(
    *,
    on=(),
    s0=(1.0, 1.0),
    junction=1.0,
    channel=1.0,
    end=0.03,
    dt=1e-3,
    solver=None,
    rates=(0.0, 0.0),
    extra=0,
):
    """One coupled structure for every bitwise arm (one compiled program): a state s of R in
    cell_0 and cell_3 (s0 per cell; frozen unless `rates` gives k_on and k_off) and four
    state_fraction couplings (b = 0), each switched on (in `on`) or off from time 0: a on
    junction_0's first side, b on its second, d on both sides, k on kir_3."""
    s = state(
        "s",
        ["cell_0", "cell_3"],
        [("hill_activation", REGULATOR, 1e-3, 1.0)],
        on=rates[0],
        off=rates[1],
        initial=dict(cell_0=s0[0], cell_3=s0[1]),
    )
    return with_coupling(
        scheduled(junction=junction, channel=channel, end=end, dt=dt, solver=solver, extra=extra),
        species=[REGULATOR],
        states=[s],
        couplings=[
            fraction("a", "junction", [SHARED_JUNCTION], "s", side="first"),
            fraction("b", "junction", [SHARED_JUNCTION], "s", side="second"),
            fraction("d", "junction", [SHARED_JUNCTION], "s", side="both"),
            fraction("k", "channel", [SHARED_CHANNEL], "s"),
        ],
        switches={c: [(0.0, int(c in on))] for c in SHARED_COUPLINGS},
    )


def differing(a, b):
    """(@3 state fields, @3 observation columns) of two runs that are not bitwise equal, every
    accepted row and every observed row (NaN-aware)."""
    import numpy as np

    from cells.models import pump_composite_adapter as adapter

    def same(x, y):
        return np.array_equal(np.asarray(x), np.asarray(y), equal_nan=True)

    fields = [
        k for k in adapter.STATE_FIELDS if not same(getattr(a.history, k), getattr(b.history, k))
    ]
    columns = [
        k
        for k in adapter.OBSERVATION_FIELDS
        if not same(getattr(a.observations, k), getattr(b.observations, k))
    ]
    return fields, columns


def with_turnover(raw, cell, clearance_per_s):
    """D150's turnover clearing R in `cell` (first order): a regulator that moves in its own
    split part, never in @3's step."""
    return with_regulator_turnover(
        raw, [("clear_R", cell, "clearance")], [("clear_R", cell, [(0.0, clearance_per_s)])]
    )


def dynamic_world(
    *,
    end=0.03,
    dt=1e-3,
    clearance=50.0,
    dose=(0.012, 1.0),
    half_saturation=1e-3,
    coefficient=1.0,
    basal=0.25,
    on=5.0,
    off=1.0,
    s0=(0.2, 0.2),
    level=0.5,
    write=(0.010, 0.9),
    switch=(0.015, 0.020),
):
    """Milestone 2's moving world (A8, the batches): the sheet, observed at every step, with
    * R cleared in cell_0 by D150's turnover (`clearance`, 1/s) and dosed there from dose[0], at
      dose[1] times the rate that holds R at its anchor (production = clearance x anchor);
    * a state of Na in cell_0 and cell_3 (on and off rates, s0 per cell, a crossing level);
    * c_r, a Hill inhibition of R on junction_0's first side, switched off over [switch[0],
      switch[1]); c_s, the state's complement on both sides with a basal level;
    * a write to (s, cell_3) at write[0], placed before the dose's step.
    Every argument is data: the worlds share one compiled program (one batch signature)."""
    raw = sheet(end=end, dt=dt, observation_times=sfx.grid_times(end, dt, dt))
    anchor = (
        REGULATOR_mM * next(c for c in raw["model"]["cells"] if c["id"] == "cell_0")["volume_pL"]
    )
    raw = with_coupling(
        raw,
        species=[REGULATOR, "Na"],
        states=[
            state(
                "s",
                ["cell_0", "cell_3"],
                [("hill_activation", "Na", 12.0, 2.0)],
                on=on,
                off=off,
                initial=dict(cell_0=s0[0], cell_3=s0[1]),
                level=level,
            )
        ],
        couplings=[
            hill_coupling(
                "c_r",
                "junction",
                ["junction_0"],
                REGULATOR,
                "hill_inhibition",
                half_saturation,
                coefficient,
                side="first",
            ),
            coupling(
                "c_s",
                "junction",
                ["junction_0"],
                ("state", "s"),
                "state_complement",
                side="both",
                basal=basal,
            ),
        ],
        switches={"c_r": [(0.0, 1), (switch[0], 0), (switch[1], 1)], "c_s": [(0.0, 1)]},
        writes=[("s", "cell_3", write[0], write[1])],
    )
    return with_regulator_turnover(
        raw,
        [("clear_R", "cell_0", "clearance"), ("dose_R", "cell_0", "production")],
        [
            ("clear_R", "cell_0", [(0.0, clearance)]),
            ("dose_R", "cell_0", [(0.0, 0.0), (dose[0], dose[1] * clearance * anchor)]),
        ],
    )


def pair_world(
    *,
    end=0.02,
    dt=1e-3,
    clearance=(5.0, 2.0),
    half_saturation=1e-3,
    coefficient=1.0,
    basal=0.25,
    on=5.0,
    off=1.0,
    s0=(0.2, 0.3),
    level=0.5,
    write=(0.008, 0.9),
    switch=(0.006, 0.012),
):
    """A small moving world for the batches: D150's face-free world with two 1 pL cells joined by
    a junction (zero ion permeability), S in both and cleared by D150's turnover; a state of S in
    both cells; c_h, a Hill inhibition of S on the junction's first side, switched off over
    [switch[0], switch[1]); c_s, the state's complement on both sides; a write to (s, cell_1).
    Every argument is data: the worlds share one batch signature."""
    cells = ("cell_0", "cell_1")
    raw = sfx.world(
        cells=tuple((c, 1.0) for c in cells),
        nodes=(),
        contacts=(),
        faces=(),
        junctions=(("junction_0", "cell_0", "cell_1"),),
        dt=dt,
        end=end,
        observation_times=sfx.grid_times(end, dt, end / 4),
        concentrations_mM=dict(cell_0=2e-3, cell_1=1e-3),
    )
    raw = sfx.with_turnover(
        raw,
        [("clear_0", "cell_0", "clearance"), ("clear_1", "cell_1", "clearance")],
        [
            ("clear_0", "cell_0", [(0.0, clearance[0])]),
            ("clear_1", "cell_1", [(0.0, clearance[1])]),
        ],
    )
    return with_coupling(
        raw,
        species=[sfx.SPECIES],
        states=[
            state(
                "s",
                list(cells),
                [("hill_activation", sfx.SPECIES, 1e-3, 2.0)],
                on=on,
                off=off,
                initial=dict(zip(cells, s0, strict=True)),
                level=level,
            )
        ],
        couplings=[
            hill_coupling(
                "c_h",
                "junction",
                ["junction_0"],
                sfx.SPECIES,
                "hill_inhibition",
                half_saturation,
                coefficient,
                side="first",
            ),
            coupling(
                "c_s",
                "junction",
                ["junction_0"],
                ("state", "s"),
                "state_complement",
                side="both",
                basal=basal,
            ),
        ],
        switches={"c_h": [(0.0, 1), (switch[0], 0), (switch[1], 1)], "c_s": [(0.0, 1)]},
        writes=[("s", "cell_1", write[0], write[1])],
    )


def with_regulator_turnover(raw, routes, controls):
    """D150's turnover of R, first in the operator list. routes: (id, cell, kind); controls:
    (route id, carrier cell, [(time, rate), ...]), rates in 1/s (clearance) or fmol/s
    (production)."""
    out = copy.deepcopy(raw)
    out["model"]["operators"].insert(
        0,
        dict(
            law=sfx.TURNOVER,
            species=identities([REGULATOR]),
            routes=[dict(id=r, species=REGULATOR, node=n, kind=k) for r, n, k in routes],
            templates=[],
        ),
    )
    out["experiment"]["turnover_controls"] = [
        dict(route_id=r, carrier_id=c, schedule=[dict(time=t, rate=v) for t, v in changes])
        for r, c, changes in controls
    ]
    return out
