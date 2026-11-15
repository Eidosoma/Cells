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

import numpy as np

from cells.core.kind_registry import Kind, KindRegistry
from cells.core.specs import ConfigError
from cells.numerics.species_sums import species_sum
from cells.processes.electrochemistry import R

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
    return state  # The identity: the seam is exercised, the amounts unchanged.


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
    outside = outside.at[:, p.exchange_node].add(flow) if xp is not np else _scatter(flow, outside, p)
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


def book(applied, start, stage, p, dt, *, xp):
    # The tableau already integrated the accumulators. Re-booking `moved` from the step's applied
    # rate is the same quantity, so the seam is exercised and nothing changes.
    return dict(exchange_moved_fmol=start.exchange_moved_fmol + dt * applied("exchange_moved_fmol"))


def ledger_terms(state, p, *, xp):
    rows = (p.exchange_rate_fmol_s > 0).astype(state.exchange_moved_fmol.dtype)
    moved = rows * state.exchange_moved_fmol[None, :]  # [S, n] out of each cell.
    outside = xp.zeros((rows.shape[0], p.outside_active.size), dtype=moved.dtype)
    outside = outside.at[:, p.exchange_node].add(moved) if xp is not np else _scatter(moved, outside, p)
    return dict(cell=-moved, outside=outside, work_pJ=state.exchange_work_pJ)


def domain(state, p, *, xp):
    return xp.all(xp.isfinite(state.exchange_moved_fmol) & (state.exchange_moved_fmol >= 0))


def readouts(state, control, p, *, xp):
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
    rates=_spy("rates", rates),
    book=_spy("book", book),
    ledger_terms=_spy("ledger_terms", ledger_terms),
    domain=_spy("domain", domain),
    readouts=_spy("readouts", readouts),
    moved_rows=_spy("moved_rows", moved_rows),
    check_definition=_spy("check_definition", check_definition),
)


def registry():
    out = KindRegistry()
    out.register(EXCHANGE)
    return out


def declare(raw, *, species="B", rate=1e-3):
    """raw with the exchange declared from its first cell to its first outside node."""
    raw = copy.deepcopy(raw)
    m = raw["model"]
    m[MODEL_KEY] = dict(
        species=species, cell=m["cells"][0]["id"], node=m["extracellular"][0]["id"], rate_fmol_s=rate
    )
    return raw
