"""A planted kind for schema A's acceptance (docs/INNER_MODEL_V4_DESIGN.md §7.4 (j), (k)).

`tests.exchange@1`: a neutral species moved at a constant declared rate from one cell to one
outside node. It lives outside src/cells, registers under the non-cells namespace `tests.`, and
implements every hook with trivial physics, so each seam is exercised before any real kind
lands:
- its moves land in the shared inventory (rule (c));
- its own accumulators are the amount moved and the work booked;
- its work is the moved species' chemical free-energy change, so the energy ledger closes
  (rule (a));
- its control is an availability in [0, 1] (rule (d)).

Each hook call is counted in CALLS, so a test can show which seams ran; the spies count only
while tracing or on the host.
"""

import copy
from collections import Counter
from dataclasses import replace

import numpy as np

from cells.core.kind_registry import (
    ConfigError,
    Kind,
    KindRegistry,
    Schedule,
    declared_schedule,
    parse_series,
    series_to_dict,
)
from cells.numerics.species_sums import species_sum
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R

KIND_ID = "tests.exchange@1"
MODEL_KEY = "test_exchange"
CALLS = Counter()


def _spy(name, function):
    def spied(*args, **kwargs):
        CALLS[name] += 1
        return function(*args, **kwargs)

    return spied


def parse(entries, base):
    m = base.model
    if set(entries) != {"species", "cell", "node", "rate_fmol_s"}:
        raise ConfigError("test_exchange declares species, cell, node and rate_fmol_s")
    if entries["species"] not in m.species_ids:
        raise ConfigError("test_exchange: unknown species")
    if entries["cell"] not in [c.id for c in m.cells]:
        raise ConfigError("test_exchange: unknown cell")
    if entries["node"] not in [n.id for n in m.extracellular]:
        raise ConfigError("test_exchange: unknown outside node")
    rate = float(entries["rate_fmol_s"])
    if not rate >= 0:
        raise ConfigError("test_exchange: rate_fmol_s must be nonnegative")
    return (entries["species"], entries["cell"], entries["node"], rate)


def to_dict(declaration):
    species, cell, node, rate = declaration
    return dict(species=species, cell=cell, node=node, rate_fmol_s=rate)


def initial(spec, declaration, layout):
    species, cell, node, rate = declaration
    m, x = spec.model, spec.execution
    n, s = x.capacity, len(m.species_ids)
    rates = np.zeros((s, n))
    rates[m.species_ids.index(species), [c.id for c in m.cells].index(cell)] = rate
    target = np.zeros(n, dtype=np.int64)
    target[[c.id for c in m.cells].index(cell)] = [o.id for o in m.extracellular].index(node)
    state = dict(exchange_moved_fmol=np.zeros(n), exchange_work_pJ=np.zeros(n))
    return state, dict(exchange_rate_fmol_s=rates, exchange_node=target)


def control_values(spec, declaration, times):
    return dict(exchange_availability=np.ones((len(times), 1)))


def stage_read(state, p, *, xp):
    return state, True  # The identity: the seam is exercised, the amounts unchanged.


def _flow(p, control):
    return p.exchange_rate_fmol_s * control.exchange_availability[0]


def _potentials(state, p, *, xp):
    from cells.models.surface_pump_v3 import physical_amounts

    ci, co = physical_amounts(state, p)
    ci = xp.where(p.active, ci / p.volume, 1.0)
    co = xp.where(p.outside_active, co / p.extracellular_volume, 1.0)
    return ci, co


def rates(state, potentials, control, p, *, xp):
    from cells.models.surface_pump_v3 import KindRates

    flow = _flow(p, control)  # [S, n], fmol/s, out of each cell.
    ci, co = _potentials(state, p, xp=xp)
    rt = 1e-3 * R * p.temperature
    gain = rt * (xp.log(co[:, p.exchange_node]) - xp.log(ci))  # pJ/fmol, node minus cell.
    work = species_sum(flow * gain, xp=xp)  # pJ/s per cell: the free energy the move stores.
    outside = xp.zeros_like(co)
    outside = (
        outside.at[:, p.exchange_node].add(flow) if xp is not np else _scatter(flow, outside, p)
    )
    return KindRates(
        cell=-flow,
        outside=outside,
        derivatives=dict(exchange_moved_fmol=species_sum(flow, xp=xp), exchange_work_pJ=work),
        heat_pJ_s=xp.zeros(()),
        work_pJ_s=work,
    )


def _scatter(flow, outside, p):
    out = np.array(outside, copy=True)
    np.add.at(out, (slice(None), p.exchange_node), flow)
    return out


def book(applied, start, end, p, dt, *, xp):
    # The tableau already integrated the accumulators. Re-booking `moved` from the step's applied
    # rate is the same quantity, so the seam is exercised and nothing changes.
    moved = start.exchange_moved_fmol + dt * applied("exchange_moved_fmol")
    return dict(exchange_moved_fmol=moved), True


def ledger_terms(state, p, *, xp):
    rows = (p.exchange_rate_fmol_s > 0).astype(state.exchange_moved_fmol.dtype)
    moved = rows * state.exchange_moved_fmol[None, :]  # [S, n] out of each cell.
    outside = xp.zeros((rows.shape[0], p.outside_active.size), dtype=moved.dtype)
    outside = (
        outside.at[:, p.exchange_node].add(moved) if xp is not np else _scatter(moved, outside, p)
    )
    return dict(cell=-moved, outside=outside, work_pJ=state.exchange_work_pJ)


def domain(state, p, *, xp):
    return xp.all(xp.isfinite(state.exchange_moved_fmol) & (state.exchange_moved_fmol >= 0))


def readouts(state, read, potentials, control, p, *, xp):
    return (species_sum(_flow(p, control), xp=xp),)


def moved_rows(declaration):
    species, cell, node, _ = declaration
    return ((species, cell), (species, node))


def check_definition(spec):
    declaration = dict(spec.model.kinds)[KIND_ID]
    row = spec.model.species_ids.index(declaration[0])
    if spec.model.valence[row] != 0:
        raise ConfigError("test_exchange moves a neutral species only")


EXCHANGE = Kind(
    kind_id=KIND_ID,
    model_key=MODEL_KEY,
    state_axes=(("exchange_moved_fmol", ("cell_slot",)), ("exchange_work_pJ", ("cell_slot",))),
    layout_fields=("exchange_rate_fmol_s", "exchange_node"),
    control_fields=("exchange_availability",),
    readout_columns=("exchange_rate_column",),
    parse=_spy("parse", parse),
    to_dict=_spy("to_dict", to_dict),
    structure_entry=lambda declaration: (),
    initial=_spy("initial", initial),
    control_values=_spy("control_values", control_values),
    stage_read=_spy("stage_read", stage_read),
    stage_rows=lambda declaration: (),  # The identity read touches no row.
    rates=_spy("rates", rates),
    book=_spy("book", book),
    ledger_terms=_spy("ledger_terms", ledger_terms),
    domain=_spy("domain", domain),
    readouts=_spy("readouts", readouts),
    moved_rows=_spy("moved_rows", moved_rows),
    check_definition=_spy("check_definition", check_definition),
)


# ------------------------------------------------------------------ the scheduled planted kind
# docs/INNER_MODEL_V4_DESIGN.md §7.4 (l): `tests.exchange@1` with its availability on a schedule,
# under the experiment key `test_exchange_controls`: [{"time": t, "availability": a}, ...], one
# series. An omitted key is the default, availability 1 throughout (version 1's constant), which
# schedule_to_dict omits. The values are parsed without parse_series' [0, 1] check, so the core's
# own control check (rule (d), at every change time) is what refuses an availability outside it.

SCHEDULE_KEY = "test_exchange_controls"
DEFAULT_SCHEDULE = Schedule((("availability", ((0.0, 1.0),)),))


def _parse_schedule(raw, base, declaration):
    if SCHEDULE_KEY not in raw:
        return DEFAULT_SCHEDULE
    points = parse_series(
        raw[SCHEDULE_KEY], SCHEDULE_KEY, value="availability", unit_interval=False
    )
    return Schedule((("availability", points),))


def _schedule_to_dict(schedule, declaration):
    if schedule == DEFAULT_SCHEDULE:
        return {}
    points = dict(schedule.series)["availability"]
    return {SCHEDULE_KEY: series_to_dict(points, value="availability")}


def _scheduled_controls(spec, declaration, times):
    held = declared_schedule(spec, KIND_ID).values("availability", times)
    return dict(exchange_availability=held[:, None])


SCHEDULED_EXCHANGE = replace(
    EXCHANGE,
    control_values=_spy("control_values", _scheduled_controls),
    experiment_keys=(SCHEDULE_KEY,),
    parse_schedule=_spy("parse_schedule", _parse_schedule),
    schedule_to_dict=_spy("schedule_to_dict", _schedule_to_dict),
)


def schedule(raw, points):
    """raw with the exchange's availability schedule, ((time, availability), ...)."""
    raw = copy.deepcopy(raw)
    raw["experiment"][SCHEDULE_KEY] = [dict(time=t, availability=a) for t, a in points]
    return raw


def registry(*more, exchange=EXCHANGE):
    """A test-local registry with the exchange (SCHEDULED_EXCHANGE for its scheduled form)."""
    out = KindRegistry()
    out.register(exchange)
    for kind in more:
        out.register(kind)
    return out


def declare(raw, *, species="B", rate=1e-3):
    """raw with the exchange declared from its first cell to its first outside node."""
    raw = copy.deepcopy(raw)
    m = raw["model"]
    m[MODEL_KEY] = dict(
        species=species,
        cell=m["cells"][0]["id"],
        node=m["extracellular"][0]["id"],
        rate_fmol_s=rate,
    )
    return raw


# ------------------------------------------------------------------ the charged planted kind
# `tests.carrier@1`: a declared species, charged or not, carried outward across one membrane
# patch at a constant declared rate: B5's charged role in miniature (a proton pump moving H+
# from its patch's inside to its outside). Its moves land in the shared inventory, so the field
# solve sees their charge (rule (c)). Its work is the carried species' electrochemical
# free-energy change at the stage's potentials, so the energy ledger closes with the
# capacitor's energy (rule (a)). carrier(electrical=False) books the chemical part only: a
# planted error that the energy ledger must catch.

CARRIER_ID = "tests.carrier@1"
CARRIER_KEY = "test_carrier"


def _carrier_parse(entries, base):
    m = base.model
    if set(entries) != {"species", "membrane", "rate_fmol_s"}:
        raise ConfigError("test_carrier declares species, membrane and rate_fmol_s")
    if entries["species"] not in m.species_ids:
        raise ConfigError("test_carrier: unknown species")
    patches = {p.id: p for p in m.membranes}
    if entries["membrane"] not in patches:
        raise ConfigError("test_carrier: unknown membrane patch")
    rate = float(entries["rate_fmol_s"])
    if not rate >= 0:
        raise ConfigError("test_carrier: rate_fmol_s must be nonnegative")
    patch = patches[entries["membrane"]]
    return (entries["species"], patch.id, patch.inside, patch.outside, rate)


def _carrier_to_dict(declaration):
    species, membrane, _, _, rate = declaration
    return dict(species=species, membrane=membrane, rate_fmol_s=rate)


def _carrier_initial(spec, declaration, layout):
    species, membrane, _, _, rate = declaration
    m, k = spec.model, spec.execution.membrane_capacity
    rates = np.zeros((len(m.species_ids), k))
    rates[m.species_ids.index(species), [p.id for p in m.membranes].index(membrane)] = rate
    state = dict(carrier_transferred=np.zeros_like(rates), carrier_work_pJ=np.zeros(k))
    return state, dict(carrier_rate_fmol_s=rates)


def _carrier_controls(spec, declaration, times):
    return dict(carrier_availability=np.ones((len(times), 1)))


def _carrier_flow(p, control, *, xp):
    """Outward flow [species, membrane] (fmol/s) on the active patches."""
    return xp.where(p.membrane_active, p.carrier_rate_fmol_s * control.carrier_availability[0], 0.0)


def _carrier_rates(electrical):
    def rates(state, potentials, control, p, *, xp):
        from cells.models.surface_pump_v3 import KindRates
        from cells.numerics.extracellular_field import scatter

        flow = _carrier_flow(p, control, xp=xp)
        ci, co = _potentials(state, p, xp=xp)
        cell, node, n = p.membrane_cell, p.membrane_outside, p.active.size
        mu = R * p.temperature * (xp.log(co[:, node]) - xp.log(ci[:, cell]))  # J/mol, out - in
        if electrical:
            mu = mu + p.valence * F * (potentials[n + node] - potentials[cell])
        work = 1e-3 * species_sum(flow * mu, xp=xp)  # pJ/s per patch: the free energy it stores.
        return KindRates(
            cell=-scatter(flow, ci, (cell,), xp=xp),
            outside=scatter(flow, co, (node,), xp=xp),
            derivatives=dict(carrier_transferred=flow, carrier_work_pJ=work),
            heat_pJ_s=xp.zeros(()),
            work_pJ_s=work,
            membrane_flux=flow,  # Outward across its patch: joins the membrane current.
        )

    return rates


def _carrier_ledger_terms(state, p, *, xp):
    from cells.numerics.extracellular_field import scatter

    moved = state.carrier_transferred  # Cumulative outward [species, membrane].
    return dict(
        cell=-scatter(moved, state.amount_increment, (p.membrane_cell,), xp=xp),
        outside=scatter(moved, state.extracellular_amount_increment, (p.membrane_outside,), xp=xp),
        work_pJ=state.carrier_work_pJ,
    )


def _carrier_domain(state, p, *, xp):
    moved, work = state.carrier_transferred, state.carrier_work_pJ
    valid = xp.all(xp.isfinite(moved) & (moved >= 0)) & xp.all(xp.isfinite(work))
    return valid & xp.all(xp.where(p.membrane_active, True, (moved == 0) & (work == 0)))


def _carrier_readouts(state, read, potentials, control, p, *, xp):
    current = CHARGE_PER_FMOL * species_sum(p.valence * _carrier_flow(p, control, xp=xp), xp=xp)
    return (current,)  # Outward current per patch (A).


def _carrier_moved_rows(declaration):
    species, _, inside, outside, _ = declaration
    return ((species, inside), (species, outside))


def carrier(*, electrical=True):
    """The charged planted kind; electrical=False omits the electrical part of its work."""
    return Kind(
        kind_id=CARRIER_ID,
        model_key=CARRIER_KEY,
        state_axes=(
            ("carrier_transferred", ("species", "membrane_slot")),
            ("carrier_work_pJ", ("membrane_slot",)),
        ),
        layout_fields=("carrier_rate_fmol_s",),
        control_fields=("carrier_availability",),
        readout_columns=("carrier_current_A",),
        parse=_carrier_parse,
        to_dict=_carrier_to_dict,
        structure_entry=lambda declaration: (),
        initial=_carrier_initial,
        control_values=_carrier_controls,
        rates=_carrier_rates(electrical),
        ledger_terms=_carrier_ledger_terms,
        domain=_carrier_domain,
        readouts=_carrier_readouts,
        moved_rows=_carrier_moved_rows,
    )


def declare_carrier(raw, *, species="K", rate=1e-3, membrane=None):
    """raw with the carrier declared on a membrane patch (its first by default)."""
    raw = copy.deepcopy(raw)
    m = raw["model"]
    m[CARRIER_KEY] = dict(
        species=species, membrane=membrane or m["membranes"][0]["id"], rate_fmol_s=rate
    )
    return raw
