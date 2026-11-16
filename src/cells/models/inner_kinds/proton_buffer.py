"""cells.rapid_proton_buffer@1: FR-4's rapid-buffer closure as the inner model's stage read (B4).

docs/INNER_MODEL_V4_DESIGN.md §7.4 (g) 1 and (k); docs/COMPARTMENT_PH_TRANSFER_DESIGN.md §4 (the
closure, D176). The kernel is processes/rapid_proton_buffer.py (FR-4's owner); this module is
the kind the core calls at its seams.

The declaration (model key `stage_reads`, FR-4's form in validation/compartment_ph/definitions.py;
version 1 admits this one read):

    [{"read_id": "rapid_proton_buffer@1", "proton_row": "H",
      "buffers": {"cell_0": ["B_c"], "lumen": ["B_L"]},
      "k_on_per_mM_s": {"B_c": 1e7, "B_L": 1e7}}]

- `buffers` names the declared (node, row) pairs, the closure's mask; a buffer row at a node it
  does not name is a declared trace, a free row whose charge counts and which has no protonation.
- K of each buffer comes from the species registry's two standard potentials at its
  standard_concentration_mM (one authority), never from a parameter.
- k_on is D175's stand-in parameter, used only by the envelope check, never by the equilibrium.

At a buffered node the proton row stores the proton equivalents H_eq and each buffer row its
total. Every stage, the read replaces the proton row's amount by the free proton amount h V for
the rates (pumps, leaks, the pH-dependent laws); unbuffered nodes are read as stored (h = H). The
field solve keeps the stored rows' charges, so buffering changes no node's charge. A read whose
root misses |g|/H <= 1e-13, or an inadmissible state, refuses the step; so does a stage whose
estimated lag behind the kinetic system exceeds the declared budget (1e-3 pH) at the stage's
transport (the envelope). The closure's declared free-energy term, G* less the stored rows' own
terms, joins the energy ledger as stored free energy (its change since the start), in @3's
convention: the proton's standard part is taken out, so the term is zero at unbuffered nodes and
consistent with @3's reservoir work at a held bath (_declared_terms).

Version 1 refuses an inner-model route (membrane, junction, channel, face) for the proton row at
a buffered node: proton routes there read through the closure (FR-4's own laws). The species
registry already refuses in-step movers of the buffer rows (two-form rows are inert).

Precision: the read writes h V into the proton row through the state's increment, so the rates
see h to about eps H_eq / h relative (about 1e-10 in a 50 mM buffer at pH 7.2).
"""

from types import SimpleNamespace
from typing import NamedTuple

import numpy as np

from cells.core import species_registry
from cells.core.kind_registry import BUILTIN, ConfigError, Kind
from cells.processes import rapid_proton_buffer as closure
from cells.processes.electrochemistry import R

KIND_ID = "cells.rapid_proton_buffer@1"
MODEL_KEY = "stage_reads"
FIELDS = ("read_id", "proton_row", "buffers", "k_on_per_mM_s")
COLUMNS = ("free_proton_mM", "pH")


class Declaration(NamedTuple):
    proton: str
    buffers: tuple  # ((node ID, (buffer row, ...)), ...), sorted
    k_on: tuple  # ((buffer row, k_on in 1/(mM s)), ...), sorted


def parse(entries, base):
    m = base.model
    if not isinstance(entries, list) or len(entries) != 1 or not isinstance(entries[0], dict):
        raise ConfigError(f"{MODEL_KEY}: version 1 declares one read, {closure.READ_ID}")
    entry = entries[0]
    if set(entry) != set(FIELDS):
        raise ConfigError(f"{MODEL_KEY}: a read declares exactly {', '.join(FIELDS)}")
    read_id, proton, buffers, k_on = (entry[k] for k in FIELDS)
    if read_id != closure.READ_ID:
        raise ConfigError(f"{MODEL_KEY}: unknown read {read_id!r}; version 1 has {closure.READ_ID}")
    if proton not in m.species_ids:
        raise ConfigError(f"{MODEL_KEY}: unknown proton row {proton!r}")
    nodes = {c.id for c in m.cells} | {o.id for o in m.extracellular}
    if not isinstance(buffers, dict) or not buffers:
        raise ConfigError(f"{MODEL_KEY}: buffers maps nodes to their buffer rows")
    pairs = []
    for node, rows in buffers.items():
        if node not in nodes:
            raise ConfigError(f"{MODEL_KEY}: unknown node {node!r}")
        if not isinstance(rows, list) or not rows or len(set(rows)) != len(rows):
            raise ConfigError(f"{MODEL_KEY}: node {node} needs a list of distinct buffer rows")
        for row in rows:
            if row not in m.species_ids or row == proton:
                raise ConfigError(f"{MODEL_KEY}: {row!r} is not a buffer row")
        pairs.append((node, tuple(sorted(rows))))
    named = {row for _, rows in pairs for row in rows}
    if not isinstance(k_on, dict) or set(k_on) != named:
        raise ConfigError(f"{MODEL_KEY}: k_on_per_mM_s names each buffer row once")
    rates = []
    for row, value in k_on.items():
        value = float(value)
        if not (np.isfinite(value) and value > 0):
            raise ConfigError(f"{MODEL_KEY}: k_on of {row} must be positive and finite")
        rates.append((row, value))
    return Declaration(proton, tuple(sorted(pairs)), tuple(sorted(rates)))


def to_dict(declaration):
    return [
        dict(
            read_id=closure.READ_ID,
            proton_row=declaration.proton,
            buffers={node: list(rows) for node, rows in declaration.buffers},
            k_on_per_mM_s=dict(declaration.k_on),
        )
    ]


def structure_entry(declaration):
    """Value-free: the number of buffer rows, which selects the kernel's closed form (one) or
    its bisection (several). Rows, membership and constants are layout values."""
    return (len(declaration.k_on),)


def _buffer_rows(declaration):
    return tuple(row for row, _ in declaration.k_on)


def initial(spec, declaration, layout):
    m = spec.model
    ids, rows = list(m.species_ids), _buffer_rows(declaration)
    n, o = spec.execution.capacity, spec.execution.extracellular_capacity
    nodes = [c.id for c in m.cells] + [None] * (n - len(m.cells))
    nodes += [x.id for x in m.extracellular] + [None] * (o - len(m.extracellular))
    member = np.zeros((len(rows), n + o), dtype=bool)
    for node, named in declaration.buffers:
        for row in named:
            member[rows.index(row), nodes.index(node)] = True
    k = np.asarray(
        [species_registry.dissociation_constant_mM(spec, r, declaration.proton) for r in rows]
    )
    proton_mu, c0 = species_registry.standard_potential(spec, declaration.proton)
    acid = np.asarray([species_registry.protonated_potential(spec, r)[0] for r in rows])
    base = np.asarray([species_registry.standard_potential(spec, r)[0] for r in rows])
    own = dict(
        proton_buffer_rows=np.asarray([ids.index(declaration.proton), *map(ids.index, rows)]),
        proton_buffer_member=member,
        proton_buffer_k_mM=k,
        proton_buffer_k_on=np.asarray([value for _, value in declaration.k_on]),
        proton_buffer_mu_RT=np.stack((acid, base)),
        proton_buffer_proton_mu_RT=np.asarray(proton_mu, dtype=float),
        proton_buffer_c0_mM=np.asarray(c0, dtype=float),
        proton_buffer_initial_pJ=np.zeros(n + o),
    )
    # The term at the start (every increment zero), so the ledger books its change.
    start = SimpleNamespace(**(dict(layout) | own))
    amounts = np.concatenate((start.amount_reference, start.extracellular_amount_reference), axis=1)
    own["proton_buffer_initial_pJ"] = _declared_terms(start, amounts, xp=np)
    # Gap 7's running extrema start at the start's own values (the lag at zero).
    h, _, _, _, _ = _closure(amounts, start, np)
    _, active = _nodes(start, np)
    ph = np.where(active, -np.log10(np.where(active, h, 1.0) / closure.PH_REFERENCE_mM), 0.0)
    state = dict(
        proton_buffer_max_lag_pH=np.zeros(n + o),
        proton_buffer_min_pH=ph,
        proton_buffer_max_pH=ph.copy(),
    )
    return state, own


def _nodes(p, xp):
    volume = xp.concatenate((p.volume, p.extracellular_volume))
    active = xp.concatenate((p.active, p.outside_active))
    return volume, active


def _amounts(state, p, xp):
    return xp.concatenate(
        (
            p.amount_reference + state.amount_increment,
            p.extracellular_amount_reference + state.extracellular_amount_increment,
        ),
        axis=1,
    )


def _closure(amounts, p, xp):
    """(h [node] in mM, buffered [node], valid [node], B̄ [buffer, node] in mM, member)."""
    volume, active = _nodes(p, xp)
    rows = p.proton_buffer_rows
    member = p.proton_buffer_member & active[None, :]
    buffered = xp.any(member, axis=0)
    total = amounts[rows[0]] / xp.where(active, volume, 1.0)
    safe_total = xp.where(buffered, total, 1.0)
    buffer = xp.where(member, amounts[rows[1:]] / xp.where(active, volume, 1.0)[None, :], 0.0)
    h, valid = closure.free_proton(safe_total, buffer, p.proton_buffer_k_mM[:, None], xp=xp)
    return xp.where(buffered, h, total), buffered, valid, buffer, member


def stage_read(state, p, *, xp):
    """The stage's read: the proton row holds free h V at buffered nodes, for the rates."""
    amounts = _amounts(state, p, xp)
    h, buffered, ok, _, _ = _closure(amounts, p, xp)
    volume, active = _nodes(p, xp)
    n = p.active.size
    free = h * volume  # fmol, free protons.
    species = xp.arange(amounts.shape[0])[:, None]
    row = (species == p.proton_buffer_rows[0]) & buffered[None, :]
    reference = xp.concatenate((p.amount_reference, p.extracellular_amount_reference), axis=1)
    increment = xp.concatenate(
        (state.amount_increment, state.extracellular_amount_increment), axis=1
    )
    read = xp.where(row, free[None, :] - reference, increment)
    valid = xp.all(xp.where(buffered & active, ok, True))
    return state._replace(
        amount_increment=read[:, :n], extracellular_amount_increment=read[:, n:]
    ), valid


def stage_rows(declaration):
    """(proton, node) and (buffer, node) at every declared node: the rows the read uses."""
    out = []
    for node, rows in declaration.buffers:
        out.append((declaration.proton, node))
        out.extend((row, node) for row in rows)
    return tuple(out)


def _stage(read, cell, outside, p, xp):
    """(lag [node] in pH units, 0 off the buffered nodes; pH [node] of the read; active) at a
    stage: the kernel's lag estimate at the stage's transport of the proton row (dH̄_eq/dt)."""
    volume, active = _nodes(p, xp)
    amounts = _amounts(read, p, xp)
    rows = p.proton_buffer_rows
    member = p.proton_buffer_member & active[None, :]
    buffered = xp.any(member, axis=0)
    safe_volume = xp.where(active, volume, 1.0)
    free = amounts[rows[0]] / safe_volume  # The read's h at buffered nodes, H̄ elsewhere.
    h = xp.where(buffered, free, 1.0)
    buffer = xp.where(member, amounts[rows[1:]] / safe_volume[None, :], 0.0)
    rate = xp.concatenate((cell[rows[0]], outside[rows[0]])) / safe_volume  # mM/s
    lag = closure.lag_estimate_ph(
        h, buffer, p.proton_buffer_k_mM[:, None], p.proton_buffer_k_on[:, None], rate, member, xp=xp
    )
    ph = -xp.log10(xp.where(active, free, 1.0) / closure.PH_REFERENCE_mM)
    return xp.where(buffered, lag, 0.0), ph, active


def stage_check(read, cell, outside, p, *, xp):
    """FR-4's envelope (§4.2): the closure's estimated lag behind the kinetic system, at the
    stage's transport, within the budget at every buffered node; a breach refuses the step (the
    verdict), and stage_values reports the margin."""
    lag, _, _ = _stage(read, cell, outside, p, xp)
    return xp.all(lag <= closure.LAG_BUDGET_PH)


def stage_values(read, cell, outside, p, *, xp):
    """Gap 7: the stage's lag and pH per node, for their running extrema over every stage."""
    lag, ph, active = _stage(read, cell, outside, p, xp)
    return dict(
        proton_buffer_max_lag_pH=lag,
        proton_buffer_min_pH=xp.where(active, ph, xp.inf),
        proton_buffer_max_pH=xp.where(active, ph, -xp.inf),
    )


def domain(state, p, *, xp):
    """The extrema fields stay finite, the lag nonnegative, and min pH <= max pH."""
    lag, low, high = (
        state.proton_buffer_max_lag_pH,
        state.proton_buffer_min_pH,
        state.proton_buffer_max_pH,
    )
    finite = xp.all(xp.isfinite(lag) & xp.isfinite(low) & xp.isfinite(high))
    return finite & xp.all(lag >= 0) & xp.all(low <= high)


def _declared_terms(p, amounts, *, xp):
    """The closure's declared term per node (pJ), in @3's energy convention.

    The kernel's term is G* less the stored rows' own terms, with every species' standard part
    (mu°/RT - ln c0 per amount) inside G*. @3's routes and its reservoir work book a proton at
    RT ln c (c in mM) with no standard part, so the proton's standard part on the stored proton
    equivalents, RT H_eq (mu°_H/RT - ln c0), is taken out: the term is then zero at every
    unbuffered node, its derivative in H_eq is RT ln(h / H̄) (the free proton against the stored
    row), and a proton exchanged with a held bath closes the ledger with @3's reservoir work.
    The buffer totals' standard part is constant (the rows are inert) and stays.
    """
    volume, active = _nodes(p, xp)
    rows = p.proton_buffer_rows
    member = p.proton_buffer_member & active[None, :]
    buffered = xp.any(member, axis=0)
    protons = xp.where(buffered, amounts[rows[0]], 1.0)
    term, _ = closure.declared_term_pJ(
        protons,
        xp.where(member, amounts[rows[1:]], 0.0),
        xp.where(active, volume, 1.0),
        p.proton_buffer_k_mM[:, None],
        p.proton_buffer_proton_mu_RT,
        p.proton_buffer_mu_RT[0][:, None],
        p.proton_buffer_mu_RT[1][:, None],
        p.temperature,
        c0_mM=p.proton_buffer_c0_mM,
        xp=xp,
    )
    standard = p.proton_buffer_proton_mu_RT - xp.log(p.proton_buffer_c0_mM)
    return xp.where(buffered, term - 1e-3 * R * p.temperature * protons * standard, 0.0)


def ledger_terms(state, p, *, xp):
    """The declared term's change since the start, as stored free energy (rule (a))."""
    return dict(
        stored_pJ=_declared_terms(p, _amounts(state, p, xp), xp=xp) - p.proton_buffer_initial_pJ
    )


def readouts(state, read, potentials, control, p, *, xp):
    h, buffered, _, _, _ = _closure(_amounts(state, p, xp), p, xp)
    _, active = _nodes(p, xp)
    h = xp.where(active, h, 0.0)
    ph = xp.where(active, -xp.log10(xp.where(active, h, 1.0) / closure.PH_REFERENCE_mM), 0.0)
    return h, ph


INNER_ROUTES = ("membrane", "junction", "channel", "face")


def check_definition(spec):
    """Version 1's admission: no inner-model route (membrane, junction, channel or face) moves
    the proton row at a buffered node, since those routes read stored rows as concentrations.
    Kinds' movers (a transporter) read the stage's read and are admitted."""
    from cells.models import surface_pump_v3

    declaration = dict(spec.model.kinds)[KIND_ID]
    buffered = {node for node, _ in declaration.buffers}
    m = spec.model
    ends = {p.id: (p.inside, p.outside) for p in m.membranes}
    ends |= {j.id: (j.sender, j.receiver) for j in m.junctions}
    ends |= {f.id: (f.sender, f.receiver) for f in m.faces}
    ends |= {c.id: ends[c.membrane_id] for c in m.channels}
    for mover, _, entities in surface_pump_v3.moved_rows(m).get(declaration.proton, ()):
        if mover not in INNER_ROUTES:
            continue
        for entity in entities:
            if set(ends[entity]) & buffered:
                raise ConfigError(
                    f"{MODEL_KEY}: the {mover} route {entity} moves the proton row "
                    f"{declaration.proton} at a buffered node; proton routes there read "
                    "through the closure (version 1)"
                )


PROTON_BUFFER = BUILTIN.register(
    Kind(
        kind_id=KIND_ID,
        model_key=MODEL_KEY,
        # Gap 7: running extrema over every IMEX stage, per node (cells, then outside nodes).
        state_axes=(
            ("proton_buffer_max_lag_pH", ("node",)),
            ("proton_buffer_min_pH", ("node",)),
            ("proton_buffer_max_pH", ("node",)),
        ),
        stage_values=stage_values,
        stage_extrema=(
            ("proton_buffer_max_lag_pH", "max"),
            ("proton_buffer_min_pH", "min"),
            ("proton_buffer_max_pH", "max"),
        ),
        domain=domain,
        layout_fields=(
            "proton_buffer_rows",
            "proton_buffer_member",
            "proton_buffer_k_mM",
            "proton_buffer_k_on",
            "proton_buffer_mu_RT",
            "proton_buffer_proton_mu_RT",
            "proton_buffer_c0_mM",
            "proton_buffer_initial_pJ",
        ),
        readout_columns=COLUMNS,
        parse=parse,
        to_dict=to_dict,
        structure_entry=structure_entry,
        initial=initial,
        stage_read=stage_read,
        stage_rows=stage_rows,
        stage_check=stage_check,
        ledger_terms=ledger_terms,
        readouts=readouts,
        check_definition=check_definition,
    )
)
