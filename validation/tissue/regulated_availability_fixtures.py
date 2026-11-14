"""Small worlds for species_regulated_availability@1 (coupling out of the inventory, D155 item 1).

All values are synthetic. The base world is the seven-cell heredity sheet
(cell_replacement_fixtures.heredity_sheet, radius 1, its centre cell written D): pumps, Kir and
NaV populations, gated junctions and a held bath per cell, so the ions move and junction and
channel availabilities matter electrically. A neutral regulator R is declared by the engine's helper
(cells.core.inventory_species) at a resolved level, far above its resolution floor: five species.

* sheet: the composite definition with no operator;
* with_coupling: the operator's block and its two schedules;
* state, coupling, hill_coupling: declaration entries (every key explicit); frozen and fraction:
  a state that never moves and a coupling F = s on it (an exactly representable factor);
* schedule_junction, schedule_channel: one element's availability held at a value from time 0;
* differing: the @3 state fields and observation columns in which two runs are not bitwise equal;
* with_turnover: D150's turnover clearing R in one cell (a moving, impermeant source).
"""

import copy

from cells.core import pump_composite_spec as cs
from cells.core.inventory_species import add_inventory_species
from validation.tissue import cell_replacement_fixtures as rfx
from validation.tissue import secreted_species_fixtures as sfx

LAW = "species_regulated_availability@1"
STATE_LAW = "hill_regulated_two_state@1"
REGULATOR = "R"
REGULATOR_mM = 1e-3
FLOOR_FMOL = 1e-20
D_REGULATOR = 1e-10


def sheet(*, end=0.02, dt=1e-3, observation_times=None, regulator_mM=REGULATOR_mM, solver=None):
    """The seven-cell sheet with R declared; `solver` as the sheet's (None: its IMEX default; "rk4"
    needs dt near 2.5e-6, @3's explicit bound on this sheet)."""
    raw = rfx.heredity_sheet(radius=1, disc=0, dt=dt, end_time=end, solver=solver)
    times = observation_times or sfx.grid_times(end, dt, end / 4)
    raw["experiment"]["observation_times"] = list(times)
    raw = add_inventory_species(
        raw,
        REGULATOR,
        trace_mM=regulator_mM,
        diffusivity_m2_per_s=D_REGULATOR,
        floor_fmol=FLOOR_FMOL,
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


def scheduled(*, junction=1.0, channel=1.0, end=0.03):
    """The sheet without the operator, junction_0 and kir_3 held at the given availabilities."""
    raw = schedule_junction(sheet(end=end), SHARED_JUNCTION, junction)
    return schedule_channel(raw, SHARED_CHANNEL, channel)


def shared_structure(*, on=(), s0=(1.0, 1.0), junction=1.0, channel=1.0, end=0.03):
    """One coupled structure for every bitwise arm (one compiled program): a frozen state s in
    cell_0 and cell_3 (s0 per cell) and four state_fraction couplings (b = 0), each switched on (in
    `on`) or off from time 0: a on junction_0's first side, b on its second, d on both sides, k on
    kir_3."""
    return with_coupling(
        scheduled(junction=junction, channel=channel, end=end),
        species=[REGULATOR],
        states=[frozen("s", ["cell_0", "cell_3"], dict(cell_0=s0[0], cell_3=s0[1]))],
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
    out = copy.deepcopy(raw)
    out["model"]["operators"].insert(
        0,
        dict(
            law=sfx.TURNOVER,
            species=identities([REGULATOR]),
            routes=[dict(id="clear_R", species=REGULATOR, node=cell, kind="clearance")],
            templates=[],
        ),
    )
    out["experiment"]["turnover_controls"] = [
        dict(route_id="clear_R", carrier_id=cell, schedule=[dict(time=0.0, rate=clearance_per_s)])
    ]
    return out
