"""A planted kind for schema A's acceptance (docs/INNER_MODEL_V4_DESIGN.md §7.4 (j), (k)).

`tests.kind.exchange@1`: a neutral species moved at a constant declared rate from one cell to one
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

from cells.laws.electrochemistry import CHARGE_PER_FMOL, F, R
from cells.numerics.species_sums import entity_sum, species_sum
from cells.registry.kind_registry import (
    ConfigError,
    Kind,
    KindRegistry,
    Schedule,
    declared_schedule,
    parse_series,
    series_to_dict,
)

KIND_ID = "tests.kind.exchange@1"
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


def book(applied, start, end, control, p, dt, *, xp):
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
# docs/INNER_MODEL_V4_DESIGN.md §7.4 (l): `tests.kind.exchange@1` with its availability on a schedule,
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
# `tests.kind.carrier@1`: a declared species, charged or not, carried outward across one membrane
# patch at a constant declared rate: B5's charged role in miniature (a proton pump moving H+
# from its patch's inside to its outside). Its moves land in the shared inventory, so the field
# solve sees their charge (rule (c)). Its work is the carried species' electrochemical
# free-energy change at the stage's potentials, so the energy ledger closes with the
# capacitor's energy (rule (a)). carrier(electrical=False) books the chemical part only: a
# planted error that the energy ledger must catch.

CARRIER_ID = "tests.kind.carrier@1"
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


# ------------------------------------------------------------------ the scheduled relaxation
# docs/INNER_MODEL_V4_DESIGN.md §7.4 (l) 5: `tests.kind.relaxation@1`, FR-5's damage law in miniature
# (laws/transport/patch_damage.py, the FR-4/FR-5 note §9): per cell, d relaxes as
#     dd/dt = k_inj u_inj(t) (1 - d) - k_res u_res(t) d,
# with u_inj and u_res piecewise-constant schedules in [0, 1] under the experiment key
# `test_relaxation_controls`, {"injury": [{time, value}], "resealing": [{time, value}]} (FR-5's
# two lists; an omitted key holds both at 0). Its rates give the stages d's derivative, which the
# tableau integrates; its book replaces d with the law's exact step at the step's held control,
# so d is exact wherever the schedules are constant over each step, which their breakpoints on the
# step grid assure. It moves nothing and books no heat or work.

RELAXATION_ID = "tests.kind.relaxation@1"
RELAXATION_KEY = "test_relaxation"
RELAXATION_SCHEDULE_KEY = "test_relaxation_controls"
RELAXATION_SERIES = ("injury", "resealing")
RELAXATION_DEFAULT = Schedule(tuple((name, ((0.0, 0.0),)) for name in RELAXATION_SERIES))


def _relaxation_parse(entries, base):
    if set(entries) != {"injury_rate_per_s", "resealing_rate_per_s", "initial"}:
        raise ConfigError("test_relaxation declares its two rates (per s) and its initial d")
    rates = tuple(float(entries[k]) for k in ("injury_rate_per_s", "resealing_rate_per_s"))
    initial = float(entries["initial"])
    if not (min(rates) >= 0 and 0 <= initial <= 1):
        raise ConfigError("test_relaxation: rates are nonnegative and the initial d in [0, 1]")
    return (*rates, initial)


def _relaxation_to_dict(declaration):
    injury, resealing, initial = declaration
    return dict(injury_rate_per_s=injury, resealing_rate_per_s=resealing, initial=initial)


def _relaxation_initial(spec, declaration, layout):
    injury, resealing, initial = declaration
    state = dict(relaxation_damage=np.full(spec.execution.capacity, initial))
    return state, dict(
        relaxation_injury_rate_per_s=np.asarray([injury]),
        relaxation_resealing_rate_per_s=np.asarray([resealing]),
    )


def _relaxation_parse_schedule(raw, base, declaration):
    if RELAXATION_SCHEDULE_KEY not in raw:
        return RELAXATION_DEFAULT
    block = raw[RELAXATION_SCHEDULE_KEY]
    if not isinstance(block, dict) or set(block) != set(RELAXATION_SERIES):
        raise ConfigError(f"{RELAXATION_SCHEDULE_KEY} declares injury and resealing")
    return Schedule(
        tuple(
            (name, parse_series(block[name], f"{RELAXATION_SCHEDULE_KEY}.{name}"))
            for name in RELAXATION_SERIES
        )
    )


def _relaxation_schedule_to_dict(schedule, declaration):
    if schedule == RELAXATION_DEFAULT:
        return {}
    series = dict(schedule.series)
    return {RELAXATION_SCHEDULE_KEY: {name: series_to_dict(series[name]) for name in series}}


def _relaxation_controls(spec, declaration, times):
    schedule = declared_schedule(spec, RELAXATION_ID)
    return {
        f"relaxation_{name}": schedule.values(name, times)[:, None] for name in RELAXATION_SERIES
    }


def _relaxation_rates(state, potentials, control, p, *, xp):
    from cells.laws.transport import patch_damage
    from cells.models.surface_pump_v3 import KindRates

    rate, _, _ = patch_damage.rates(
        state.relaxation_damage,
        p.relaxation_injury_rate_per_s[0],
        p.relaxation_resealing_rate_per_s[0],
        control.relaxation_injury[0],
        control.relaxation_resealing[0],
        xp=xp,
    )
    return KindRates(
        cell=xp.zeros_like(state.amount_increment),
        outside=xp.zeros_like(state.extracellular_amount_increment),
        derivatives=dict(relaxation_damage=rate),
        heat_pJ_s=xp.zeros(()),
        work_pJ_s=xp.zeros(()),
    )


def _relaxation_book(applied, start, end, control, p, dt, *, xp):
    from cells.laws.transport import patch_damage

    exact = patch_damage.exact_step(
        start.relaxation_damage,
        p.relaxation_injury_rate_per_s[0],
        p.relaxation_resealing_rate_per_s[0],
        control.relaxation_injury[0],
        control.relaxation_resealing[0],
        dt,
        xp=xp,
    )
    return dict(relaxation_damage=exact), True


def _relaxation_domain(state, p, *, xp):
    d = state.relaxation_damage
    return xp.all(xp.isfinite(d) & (d >= 0) & (d <= 1))


def relaxation(*, booked=True):
    """The scheduled relaxation; booked=False leaves d to the tableau (no exact step)."""
    return Kind(
        kind_id=RELAXATION_ID,
        model_key=RELAXATION_KEY,
        state_axes=(("relaxation_damage", ("cell_slot",)),),
        layout_fields=("relaxation_injury_rate_per_s", "relaxation_resealing_rate_per_s"),
        control_fields=tuple(f"relaxation_{name}" for name in RELAXATION_SERIES),
        parse=_relaxation_parse,
        to_dict=_relaxation_to_dict,
        structure_entry=lambda declaration: (),
        initial=_relaxation_initial,
        control_values=_relaxation_controls,
        rates=_relaxation_rates,
        book=_relaxation_book if booked else None,
        domain=_relaxation_domain,
        experiment_keys=(RELAXATION_SCHEDULE_KEY,),
        parse_schedule=_relaxation_parse_schedule,
        schedule_to_dict=_relaxation_schedule_to_dict,
    )


def declare_relaxation(raw, *, injury, resealing, initial=0.0, schedule=None):
    """raw with the relaxation declared and, if given, its schedule {"injury": ((time, value),
    ...), "resealing": ((time, value), ...)}."""
    raw = copy.deepcopy(raw)
    raw["model"][RELAXATION_KEY] = dict(
        injury_rate_per_s=injury, resealing_rate_per_s=resealing, initial=initial
    )
    if schedule is not None:
        raw["experiment"][RELAXATION_SCHEDULE_KEY] = {
            name: [dict(time=t, value=v) for t, v in points] for name, points in schedule.items()
        }
    return raw


# ------------------------------------------------------------------ the stored-energy planted kind
# docs/INNER_MODEL_V4_DESIGN.md §7.4 (m), gap 2: `tests.kind.conversion@1` converts a neutral substrate
# S into a neutral product P at one cell at a declared constant rate: finite fuel's bookkeeping in
# miniature. Each has a declared standard potential mu°/RT, which @3's RT ln c terms leave out, and
# no stage read carries it; so the kind stores the standard part, (mu°_P - mu°_S) x moved, as
# stored_pJ, and gives its rate as stored_pJ_s. Its heat is the conversion's free-energy decrease,
# -r (mu_P - mu_S) with mu = mu° + RT ln c. conversion(stored_rate=False) leaves the rate out: the
# cumulative energy ledger still closes, but the stage energy-rate observation does not.

CONVERSION_ID = "tests.kind.conversion@1"
CONVERSION_KEY = "test_conversion"
CONVERSION_FIELDS = (
    "substrate",
    "product",
    "cell",
    "rate_fmol_s",
    "substrate_mu_RT",
    "product_mu_RT",
)


def _conversion_parse(entries, base):
    m = base.model
    if set(entries) != set(CONVERSION_FIELDS):
        raise ConfigError("test_conversion declares " + ", ".join(CONVERSION_FIELDS))
    if entries["substrate"] not in m.species_ids or entries["product"] not in m.species_ids:
        raise ConfigError("test_conversion: unknown species")
    if entries["cell"] not in [c.id for c in m.cells]:
        raise ConfigError("test_conversion: unknown cell")
    rate = float(entries["rate_fmol_s"])
    if not rate >= 0:
        raise ConfigError("test_conversion: rate_fmol_s must be nonnegative")
    return tuple(entries[k] for k in CONVERSION_FIELDS[:3]) + (
        rate,
        float(entries["substrate_mu_RT"]),
        float(entries["product_mu_RT"]),
    )


def _conversion_initial(spec, declaration, layout):
    substrate, product, cell, rate, mu_s, mu_p = declaration
    m, n = spec.model, spec.execution.capacity
    at = np.zeros(n)
    at[[c.id for c in m.cells].index(cell)] = rate
    rows = np.asarray([m.species_ids.index(substrate), m.species_ids.index(product)])
    state = dict(conversion_moved_fmol=np.zeros(n), conversion_heat_pJ=np.zeros(n))
    return state, dict(
        conversion_rate_fmol_s=at, conversion_rows=rows, conversion_mu_RT=np.asarray([mu_s, mu_p])
    )


def _conversion_moves(p, species, per_cell, *, xp):
    """[S, n]: +per_cell at the product's row, -per_cell at the substrate's."""
    rows = xp.arange(species)[:, None]
    gained = xp.where(rows == p.conversion_rows[1], per_cell[None, :], 0.0)
    return gained - xp.where(rows == p.conversion_rows[0], per_cell[None, :], 0.0)


def _conversion_standard_J_mol(p):
    """mu°_P - mu°_S (J/mol)."""
    return R * p.temperature * (p.conversion_mu_RT[1] - p.conversion_mu_RT[0])


def _conversion_rates(stored_rate):
    def rates(state, potentials, control, p, *, xp):
        from cells.models.surface_pump_v3 import KindRates

        ci, _ = _potentials(state, p, xp=xp)
        rate = p.conversion_rate_fmol_s  # [n] fmol/s converted at each cell
        drop = _conversion_standard_J_mol(p) + R * p.temperature * (
            xp.log(ci[p.conversion_rows[1]]) - xp.log(ci[p.conversion_rows[0]])
        )  # mu_P - mu_S (J/mol) per cell
        heat = -1e-3 * rate * drop  # pJ/s
        species = state.amount_increment.shape[0]
        return KindRates(
            cell=_conversion_moves(p, species, rate, xp=xp),
            outside=xp.zeros_like(state.extracellular_amount_increment),
            derivatives=dict(conversion_moved_fmol=rate, conversion_heat_pJ=heat),
            heat_pJ_s=heat,
            work_pJ_s=xp.zeros(()),
            stored_pJ_s=1e-3 * rate * _conversion_standard_J_mol(p) if stored_rate else None,
        )

    return rates


def _conversion_ledger_terms(produced):
    def ledger_terms(state, p, *, xp):
        moved = state.conversion_moved_fmol
        species = state.amount_increment.shape[0]
        terms = dict(
            cell=_conversion_moves(p, species, moved, xp=xp),
            heat_pJ=state.conversion_heat_pJ,
            stored_pJ=1e-3 * _conversion_standard_J_mol(p) * moved,
        )
        if produced:  # The reaction's record: S1 consumed, S2 produced, over every cell.
            total = entity_sum(moved, axis=None, xp=xp)
            terms["produced"] = _conversion_moves(p, species, total[None], xp=xp)[:, 0]
        return terms

    return ledger_terms


def _conversion_domain(state, p, *, xp):
    moved, heat = state.conversion_moved_fmol, state.conversion_heat_pJ
    return xp.all(xp.isfinite(moved) & (moved >= 0)) & xp.all(xp.isfinite(heat))


def conversion(*, stored_rate=True, produced=True):
    """The conversion kind; stored_rate=False gives no stored_pJ_s and produced=False no
    `produced` ledger term (planted omissions)."""
    return Kind(
        kind_id=CONVERSION_ID,
        model_key=CONVERSION_KEY,
        state_axes=(
            ("conversion_moved_fmol", ("cell_slot",)),
            ("conversion_heat_pJ", ("cell_slot",)),
        ),
        layout_fields=("conversion_rate_fmol_s", "conversion_rows", "conversion_mu_RT"),
        parse=_conversion_parse,
        to_dict=lambda declaration: dict(zip(CONVERSION_FIELDS, declaration, strict=True)),
        structure_entry=lambda declaration: (),
        initial=_conversion_initial,
        rates=_conversion_rates(stored_rate),
        ledger_terms=_conversion_ledger_terms(produced),
        domain=_conversion_domain,
        moved_rows=lambda declaration: (
            (declaration[0], declaration[2]),
            (declaration[1], declaration[2]),
        ),
    )


def declare_conversion(raw, *, rate, substrate_mu_RT, product_mu_RT, substrate="S1", product="S2"):
    """raw with the conversion declared at its first cell."""
    raw = copy.deepcopy(raw)
    raw["model"][CONVERSION_KEY] = dict(
        substrate=substrate,
        product=product,
        cell=raw["model"]["cells"][0]["id"],
        rate_fmol_s=rate,
        substrate_mu_RT=substrate_mu_RT,
        product_mu_RT=product_mu_RT,
    )
    return raw


# ------------------------------------------------------------ the routing door's planted kinds
# docs/INNER_MODEL_V4_DESIGN.md §7.4 (n). `tests.kind.factor@1` is a factor source: constant factors
# per declared source ID (model key `test_factors`: [{"id", "value"}, ...]), from its layout, so a
# test can set a stage's factor through the layout. `tests.kind.sink@1` is a sink: its control
# `sink_gain` [2] is held at declared values, and the declared slots are routed through named
# sources; its readout column reports the control it receives at the observed row, and its book
# records the control it receives (SEEN).

FACTOR_ID = "tests.kind.factor@1"
FACTOR_KEY = "test_factors"
SINK_ID = "tests.kind.sink@1"
SINK_KEY = "test_sink"
SEEN = []


def _factor_parse(entries, base):
    if not isinstance(entries, list) or not entries:
        raise ConfigError("test_factors is a nonempty list of {id, value}")
    out = []
    for entry in entries:
        if set(entry) != {"id", "value"}:
            raise ConfigError("test_factors entries declare id and value")
        out.append((str(entry["id"]), float(entry["value"])))
    return tuple(out)


def factor_source(kind_id=FACTOR_ID, model_key=FACTOR_KEY):
    """A planted factor source (another ID and key give a second source kind)."""
    return Kind(
        kind_id=kind_id,
        model_key=model_key,
        layout_fields=(f"{model_key}_values",),
        parse=_factor_parse,
        to_dict=lambda declaration: [dict(id=i, value=v) for i, v in declaration],
        structure_entry=lambda declaration: (),
        initial=lambda spec, declaration, layout: (
            {},
            {f"{model_key}_values": np.asarray([v for _, v in declaration])},
        ),
        factor_sources=lambda declaration: tuple(i for i, _ in declaration),
        factors=_spy("factors", lambda read, p, *, xp: getattr(p, f"{model_key}_values")),
    )


def _sink_parse(entries, base):
    if set(entries) != {"held", "routes", "field"} or len(entries["held"]) != 2:
        raise ConfigError("test_sink declares held [2], routes [[slot, [ids]], ...] and field")
    routes = tuple((int(slot), tuple(ids)) for slot, ids in entries["routes"])
    return (tuple(float(v) for v in entries["held"]), routes, str(entries["field"]))


def _sink_book(applied, start, end, control, p, dt, *, xp):
    SEEN.append(control)
    return {}, True


SINK = Kind(
    kind_id=SINK_ID,
    model_key=SINK_KEY,
    control_fields=("sink_gain",),
    readout_columns=("sink_gain_column",),
    parse=_sink_parse,
    to_dict=lambda d: dict(held=list(d[0]), routes=[[s, list(i)] for s, i in d[1]], field=d[2]),
    structure_entry=lambda declaration: (),
    initial=lambda spec, declaration, layout: ({}, {}),
    control_values=lambda spec, declaration, times: dict(
        sink_gain=np.tile(np.asarray(declaration[0]), (len(times), 1))
    ),
    routed_controls=lambda declaration: tuple(
        (declaration[2], slot, ids) for slot, ids in declaration[1]
    ),
    readouts=lambda state, read, potentials, control, p, *, xp: (control.sink_gain,),
    book=_sink_book,
)


def declare_routing(raw, *, factors, held=(1.0, 1.0), routes=(), field="sink_gain", key=FACTOR_KEY):
    """raw with planted factors {id: value} (under `key`) and, given routes ((slot, (ids, ...)),
    ...), the planted sink."""
    raw = copy.deepcopy(raw)
    raw["model"][key] = [dict(id=i, value=v) for i, v in factors.items()]
    if routes:
        raw["model"][SINK_KEY] = dict(
            held=list(held), routes=[[slot, list(ids)] for slot, ids in routes], field=field
        )
    return raw
