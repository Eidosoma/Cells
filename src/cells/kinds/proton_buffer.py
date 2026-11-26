"""cells.kind.rapid_proton_buffer@1: FR-4's rapid-buffer closure as the inner model's stage read (B4).

docs/INNER_MODEL_V4_DESIGN.md §7.4 (g) 1 and (k); docs/COMPARTMENT_PH_TRANSFER_DESIGN.md §4 (the
closure, D176). The kernel is laws/reactions/rapid_proton_buffer.py (FR-4's owner); this module is
the kind the core calls at its seams.

The declaration (model key `stage_reads`, FR-4's form in
validation/compartment_ph_engine/definitions.py; version 1 admits this one read):

    [{"read_id": "cells.kind.rapid_proton_buffer@1", "proton_row": "H",
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

The general closure (seam C, docs/CORE_SEAMS_DESIGN.md §5 and §19 as amended): the same kind and
model key host a second law and read, cells.binding.rapid_binding@1, for several ligands on binders whose forms
the species registry declares (``forms``). Version 1's declaration above keeps its layout, fields
and code, chosen statically by the declaration's form, so its programs are unchanged. The general
declaration:

    [{"read_id": "cells.binding.rapid_binding@1", "ligand_rows": ["H", "Mg"], "proton_row": "H",
      "binders": {"matrix": ["ATP", "Pi"]},
      "k_on_per_mM_s": {"ATP": {"H": 1e7, "Mg": 1e5}, "Pi": {"H": 1e7, "Mg": 1e5}}}]

- The proton is declared, never inferred: proton_row, optional, names the ligand row that is the
  proton (version 1's field), which must be a declared ligand row of valence +1. A charge is no
  identity: Na+ is a ligand of valence +1 too (the third review's finding 1). Without proton_row
  the closure has no proton row, so it admits no release step (C5's scope is the proton row's),
  and the proton leak and the pH condition, which check theirs against it, are refused.
- At each named node it holds each binder row's total and the total equivalents of every ligand
  those binders bind there (its closure rows); k_on is declared per binding (binder, ligand), one
  for each ligand the binder's forms bind, and every form is reachable from its base by unit steps.
- Its admission: the registry's forms checks here, and the movers' rules in the species
  registry's check_closure_rows (@3's own routes and pumps refused on a closure row, a kind's move
  admitted only when its law reads cells.binding.rapid_binding@1, operators naming a held species refused).
- Beside that read, §5.2's admission (its charge half, species_registry._closure_mover_errors):
  - the kind declares role_species (F's EntityBinding);
  - its law declares base forms;
  - each mode, resolved through the binding, writes every row as a species row, never a form,
    with zero charge;
  - its moved rows at the closure are its entities' resolved rows.
  No shipped kind declares role_species yet (the transporter's comes after seam A), so in an
  admitted world nothing moves a closure row and its held totals never change: world-level power
  waits for a real mover. The moiety half waits for item 6, and multi-mode laws for seam A.
- Its solve (laws/reactions/rapid_binding.py): each stage, the read writes each held ligand's
  free amount and each binder's free base form into the rows. The envelope bounds the network's
  first-order lag at the stage's transport (1e-3 in log10 units). The ledger books phase 1's S_c,
  NaN where a held total is <= 0 so that the ledger refuses, beside @3's ideal terms on the rows
  (CORE_SEAMS §19 as amended). Its change since the start is formed from the stored increments
  (rapid_binding.booked_change_pJ: the dual's split, the start's free ligands in the layout's
  binding_initial_u), so it rounds at the change's scale, not at S_c's (the @3 owner's finding
  under X2, CORE_SEAMS_STEP0 §9.4; a recorded D148 note on this ledger term alone, the states
  unchanged). It holds each node's declared volume constant, as the closure's read does: an
  operator that changes a closure node's volume is refused (today the water law and the lumen's
  fill, by name in species_registry.check_stage_read_rows, and every closer, which this kind's
  undeclared partition roles refuse), and a new volume-changing operator must be refused there
  too before it runs beside a closure. One ligand takes the Newton too: a structure entry sees
  only the declaration, not the registry's forms, so B4's path cannot be chosen statically here
  (the kernel's tests show the two agree).
- The read is valid only where the joint margin t* > 0, the exact joint condition (amendment C4),
  as well as converged. While every held total must be positive (@3's stored rows, and S_c's
  logarithms), t* >= min T_L > 0 always, since the all-base speciation keeps every free ligand at
  its total. So the margin never refuses an admitted world today: it is the exact condition, kept
  fail-closed, for when totals at or below zero are admitted. Its vertices are the layout's
  binding_margin_vertices, and a network past the enumeration's caps is refused at the definition.
- **Every held total is positive at every stage, by construction** (positive_held_totals; the
  lead's decision of 21 November 2026, on the Lean lane's finding). @3 holds every stored amount
  positive at the checked states (the parse, the predictor's totals and each step's end), but a
  tableau's intermediate stages are read before any such check. With release forms a signed total
  can leave the margin within an ulp of 0, where its float sign misclassifies it (the Lean lane's
  three rel1 cases). So the read refuses any held total <= 0 at any stage, on the total's own sign,
  before the margin is consulted. It refuses through the read's validity, the engine's existing
  failed-read path: the step is refused as a domain failure, whose message does not name the read
  (no host-side reason reaches it from the compiled stage). Nothing is NaN-poisoned. No admitted
  world reaches it, so every registered world keeps its values.
- A form below its base in some ligand makes a release step, a unit step whose bound form holds
  count <= 0 in its ligand. Amendment C5 registers seven release-step cases, and the envelope
  bounds their kinetic lag, the cross-row drives included, within its first order's registered
  accuracy. So release steps are admitted within C5's registered scope (the lead's ruling, 19
  November 2026): in the proton row, with counts of -1, one release step per binder, and one path
  to each mixed-sign form (S4's pi2_PO4, S7's mgx_MgmH). Everything outside that scope is
  refused, fail-closed, naming what C5 does not cover.
"""

import math
from types import MappingProxyType, SimpleNamespace
from typing import NamedTuple

import numpy as np

from cells.laws.electrochemistry import R
from cells.laws.reactions import rapid_binding as binding
from cells.laws.reactions import rapid_proton_buffer as closure
from cells.registry import species_registry
from cells.modules import KindFields, finite_number
from cells.registry.kind_registry import BUILTIN, ConfigError, Kind, KindView

KIND_ID = "cells.kind.rapid_proton_buffer@1"
MODEL_KEY = "stage_reads"
FIELDS = ("read_id", "proton_row", "buffers", "k_on_per_mM_s")
COLUMNS = ("free_proton_mM", "pH")
GENERAL_READ_ID = "cells.binding.rapid_binding@1"  # The general closure's law and read ID (CORE_SEAMS §19).
GENERAL_FIELDS = ("read_id", "ligand_rows", "binders", "k_on_per_mM_s")
GENERAL_PROTON = "proton_row"  # Optional: the declared proton row (module docstring).


class Declaration(NamedTuple):
    proton: str
    buffers: tuple  # ((node ID, (buffer row, ...)), ...), sorted
    k_on: tuple  # ((buffer row, k_on in 1/(mM s)), ...), sorted


class GeneralDeclaration(NamedTuple):
    """cells.binding.rapid_binding@1's declaration (module docstring): the ligand rows, sorted; the binder rows at
    each node, ((node ID, (binder row, ...)), ...), sorted; k_on per binding, ((binder row,
    ((ligand row, k_on in 1/(mM s)), ...)), ...), sorted; and proton, its declared proton_row (the
    row the release scope, the passive routes' leak and the pH condition check theirs against), or
    None where it declares none."""

    ligands: tuple
    binders: tuple
    k_on: tuple
    proton: str | None

    @property
    def read_id(self):
        return GENERAL_READ_ID

    @property
    def closure_rows(self):
        """((species, node ID), ...): each binder row at its node, and each ligand row at a node
        where a binder there binds it (its k_on's ligands): the rows the closure holds."""
        binds = {row: tuple(ligand for ligand, _ in rates) for row, rates in self.k_on}
        out = []
        for node, rows in self.binders:
            ligands = sorted({ligand for row in rows for ligand in binds[row]})
            out += [(ligand, node) for ligand in ligands] + [(row, node) for row in rows]
        return tuple(out)


class GeneralEntry(NamedTuple):
    """The general closure's value-free structure entry: its numbers of ligand and binder rows.
    Seam C's item 3 extends it with the solve's static structure."""

    ligands: int
    binders: int


def _parse_general(entry, m):
    where = f"{MODEL_KEY} ({GENERAL_READ_ID})"
    if set(entry) - {GENERAL_PROTON} != set(GENERAL_FIELDS):
        raise ConfigError(
            f"{where}: a read declares exactly {', '.join(GENERAL_FIELDS)}, and optionally "
            f"{GENERAL_PROTON}"
        )
    _, ligands, binders, k_on = (entry[k] for k in GENERAL_FIELDS)
    species = set(m.species_ids)
    if (
        not isinstance(ligands, list)
        or not ligands
        or len(set(ligands)) != len(ligands)
        or any(ligand not in species for ligand in ligands)
    ):
        raise ConfigError(f"{where}: ligand_rows lists distinct species rows")
    nodes = {c.id for c in m.cells} | {o.id for o in m.extracellular}
    held = {o.id for o in m.extracellular if o.reservoir}
    if not isinstance(binders, dict) or not binders:
        raise ConfigError(f"{where}: binders maps nodes to their binder rows")
    pairs = []
    for node, rows in binders.items():
        if node not in nodes:
            raise ConfigError(f"{where}: unknown node {node!r}")
        if node in held:
            raise ConfigError(
                f"{where}: node {node} is a held bath. @3 values its supply at the stored total's "
                "concentration, while every route there books against the free forms, so its "
                "energy ledger cannot close: a held bath under a closure is refused"
            )
        if not isinstance(rows, list) or not rows or len(set(rows)) != len(rows):
            raise ConfigError(f"{where}: node {node} needs a list of distinct binder rows")
        for row in rows:
            if row not in species or row in ligands:
                raise ConfigError(f"{where}: {row!r} is not a binder row")
        pairs.append((node, tuple(sorted(rows))))
    named = {row for _, rows in pairs for row in rows}
    if not isinstance(k_on, dict) or set(k_on) != named:
        raise ConfigError(f"{where}: k_on_per_mM_s names each binder row once")
    rates = []
    for row, per_ligand in k_on.items():
        if not isinstance(per_ligand, dict) or not per_ligand:
            raise ConfigError(f"{where}: k_on of {row} maps each ligand it binds to its k_on")
        values = []
        for ligand, value in per_ligand.items():
            if ligand not in ligands:
                raise ConfigError(f"{where}: k_on of {row} names {ligand!r}, no declared ligand row")
            value = finite_number(value, f"{where}: k_on of {row} for {ligand}", positive=True)
            values.append((ligand, value))
        rates.append((row, tuple(sorted(values))))
    proton = entry.get(GENERAL_PROTON)
    valence = dict(zip(m.species_ids, m.valence, strict=True))
    if proton is not None and (proton not in ligands or valence[proton] != 1):
        raise ConfigError(
            f"{where}: proton_row {proton!r} is not a declared ligand row of valence +1; the "
            "proton is the declared row, never inferred from a charge"
        )
    return GeneralDeclaration(
        tuple(sorted(ligands)), tuple(sorted(pairs)), tuple(sorted(rates)), proton
    )


def parse(entries, base):
    m = base.model
    if not isinstance(entries, list) or len(entries) != 1 or not isinstance(entries[0], dict):
        raise ConfigError(f"{MODEL_KEY}: version 1 declares one read, {closure.READ_ID}")
    entry = entries[0]
    if entry.get("read_id") == GENERAL_READ_ID:
        return _parse_general(entry, m)
    if set(entry) != set(FIELDS):
        raise ConfigError(f"{MODEL_KEY}: a read declares exactly {', '.join(FIELDS)}")
    read_id, proton, buffers, k_on = (entry[k] for k in FIELDS)
    if read_id != closure.READ_ID:
        raise ConfigError(f"{MODEL_KEY}: unknown read {read_id!r}; version 1 has {closure.READ_ID}")
    if proton not in m.species_ids:
        raise ConfigError(f"{MODEL_KEY}: unknown proton row {proton!r}")
    nodes = {c.id for c in m.cells} | {o.id for o in m.extracellular}
    held = {o.id for o in m.extracellular if o.reservoir}
    if not isinstance(buffers, dict) or not buffers:
        raise ConfigError(f"{MODEL_KEY}: buffers maps nodes to their buffer rows")
    pairs = []
    for node, rows in buffers.items():
        if node not in nodes:
            raise ConfigError(f"{MODEL_KEY}: unknown node {node!r}")
        if node in held:
            raise ConfigError(
                f"{MODEL_KEY}: node {node} is a held bath. @3 values its supply at the stored "
                "total's concentration, while every route there books against the free proton, "
                "so its energy ledger cannot close: a buffered held bath is refused"
            )
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
    if isinstance(declaration, GeneralDeclaration):
        return [
            dict(
                read_id=GENERAL_READ_ID,
                ligand_rows=list(declaration.ligands),
                binders={node: list(rows) for node, rows in declaration.binders},
                k_on_per_mM_s={row: dict(rates) for row, rates in declaration.k_on},
                **({} if declaration.proton is None else {GENERAL_PROTON: declaration.proton}),
            )
        ]
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
    its bisection (several). Rows, membership and constants are layout values. The general
    declaration's entry is its own type (GeneralEntry), so version 1's entries are today's."""
    if isinstance(declaration, GeneralDeclaration):
        return GeneralEntry(len(declaration.ligands), len(declaration.k_on))
    return (len(declaration.k_on),)


def _buffer_rows(declaration):
    return tuple(row for row, _ in declaration.k_on)


def initial(spec, declaration, layout):
    if isinstance(declaration, GeneralDeclaration):
        return _general_initial(spec, declaration, layout)
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
    if _is_general(p):
        return _general_read(state, p, xp)
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
    """(proton, node, law) and (buffer, node, law) at every declared node: the rows the read uses
    (the general declaration's: its closure rows), each naming its read's law as a third item (P1's
    selector, the binding owner's ruling (a) of 19 November 2026). The general closure's rows name
    cells.binding.rapid_binding@1, a registered law that declares free_amounts, so @3's predictor takes P1's
    form there. Version 1's rows name cells.kind.rapid_proton_buffer@1, which is not a registered law, so they
    keep today's form bit for bit (surface_pump_v3.reads_free_amounts)."""
    if isinstance(declaration, GeneralDeclaration):
        return tuple((row, node, GENERAL_READ_ID) for row, node in declaration.closure_rows)
    out = []
    for node, rows in declaration.buffers:
        out.append((declaration.proton, node, closure.READ_ID))
        out.extend((row, node, closure.READ_ID) for row in rows)
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
    if _is_general(p):
        lag, _, _ = _general_stage(read, cell, outside, p, xp)
        return xp.all(lag <= binding.LAG_BUDGET_PX)
    lag, _, _ = _stage(read, cell, outside, p, xp)
    return xp.all(lag <= closure.LAG_BUDGET_PH)


def stage_values(read, cell, outside, p, *, xp):
    """Gap 7: the stage's lag and pH per node, for their running extrema over every stage."""
    if _is_general(p):
        lag, px, held = _general_stage(read, cell, outside, p, xp)
        return dict(
            binding_max_lag_pX=lag,
            binding_min_pX=xp.where(held, px, xp.inf),
            binding_max_pX=xp.where(held, px, -xp.inf),
        )
    lag, ph, active = _stage(read, cell, outside, p, xp)
    return dict(
        proton_buffer_max_lag_pH=lag,
        proton_buffer_min_pH=xp.where(active, ph, xp.inf),
        proton_buffer_max_pH=xp.where(active, ph, -xp.inf),
    )


def domain(state, p, *, xp):
    """The extrema fields stay finite, the lag nonnegative, and min pH <= max pH (the general
    closure's: its lag and every ligand's pX)."""
    if _is_general(p):
        lag, low, high = state.binding_max_lag_pX, state.binding_min_pX, state.binding_max_pX
        finite = xp.all(xp.isfinite(lag)) & xp.all(xp.isfinite(low) & xp.isfinite(high))
        return finite & xp.all(lag >= 0) & xp.all(low <= high)
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


# The host path's last general term: (layout, stored increments, change). The host row checks
# value one accepted row twice (balances, then channel_magnitudes), so the second call returns a
# copy of the first's array and the closure is solved once: bit-identical by construction. It is
# reused only for the same layout object and bitwise-equal increments; device traces never reach it.
_HOST_CHANGE = []


def _host_general_change(state, p):
    increments = tuple(
        np.asarray(a) for a in (state.amount_increment, state.extracellular_amount_increment)
    )
    if (
        _HOST_CHANGE
        and _HOST_CHANGE[0] is p
        and all(
            a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()
            for a, b in zip(_HOST_CHANGE[1], increments, strict=True)
        )
    ):
        return _HOST_CHANGE[2].copy()
    change = _general_change(state, p, np)
    _HOST_CHANGE[:] = (p, tuple(a.copy() for a in increments), np.array(change, copy=True))
    return change


def ledger_terms(state, p, *, xp):
    """The declared term's change since the start, as stored free energy (rule (a)). The general
    closure books phase 1's S_c (CORE_SEAMS §19 as amended), @3 its ideal terms on the rows. On the
    host the general term is reused for a repeated row (_HOST_CHANGE)."""
    if _is_general(p):
        if xp is np:
            return dict(stored_pJ=_host_general_change(state, p))
        return dict(stored_pJ=_general_change(state, p, xp))
    return dict(
        stored_pJ=_declared_terms(p, _amounts(state, p, xp), xp=xp) - p.proton_buffer_initial_pJ
    )


def readouts(state, read, potentials, control, p, *, xp):
    if _is_general(p):
        return _general_readouts(read, p, xp)
    h, buffered, _, _, _ = _closure(_amounts(state, p, xp), p, xp)
    _, active = _nodes(p, xp)
    h = xp.where(active, h, 0.0)
    ph = xp.where(active, -xp.log10(xp.where(active, h, 1.0) / closure.PH_REFERENCE_mM), 0.0)
    return h, ph


INNER_ROUTES = ("membrane", "junction", "channel", "face")


def _unit_steps_reach(counts):
    """Whether every form (count vectors, the base the zero vector) is reachable from the base by
    unit steps: one more or one fewer of a single ligand, through declared forms."""
    forms = {tuple(c) for c in counts}
    seen, frontier = {tuple(0 for _ in counts[0])}, [tuple(0 for _ in counts[0])]
    while frontier:
        here = frontier.pop()
        for k in range(len(here)):
            for step in (1, -1):
                there = here[:k] + (here[k] + step,) + here[k + 1 :]
                if there in forms and there not in seen:
                    seen.add(there)
                    frontier.append(there)
    return seen == forms


def _release_scope_error(forms, proton):
    """The first way a binder's forms ((ID, counts, mu°/RT), ..., base first) leave amendment C5's
    registered release-step scope, or None. A release step is a unit step f' + L <-> f whose bound
    form f holds count_f(L) <= 0, so binding L only restores a ligand a form below its base
    released. In scope: no count below -1; every release step in the proton row; at most one
    release step; and each mixed-sign form reached from its base by exactly one simple path of
    unit steps (C5's zero_power names the rest)."""
    names = sorted({ligand for _, counts, _ in forms for ligand, _ in counts})
    vectors = {
        fid: tuple(dict(counts).get(ligand, 0) for ligand in names) for fid, counts, _ in forms
    }
    low = [(fid, dict(counts)) for fid, counts, _ in forms if any(n < -1 for _, n in counts)]
    if low:
        return f"its form {low[0][0]} has a count below -1, {low[0][1]}"
    by_vector = {vector: fid for fid, vector in vectors.items()}
    releases = []
    for fid, vector in vectors.items():
        for k, ligand in enumerate(names):
            below = vector[:k] + (vector[k] - 1,) + vector[k + 1 :]
            if below in by_vector and vector[k] <= 0:
                releases.append((by_vector[below], ligand, fid))
    foreign = [step for step in releases if step[1] != proton]
    if foreign:
        f, ligand, g = foreign[0]
        declared = "none declared" if proton is None else proton
        return (
            f"its release step {f} + {ligand} <-> {g} releases {ligand}, not the proton row "
            f"({GENERAL_PROTON}: {declared})"
        )
    if len(releases) > 1:
        named = ", ".join(f"{f} + {ligand} <-> {g}" for f, ligand, g in releases)
        return f"it has {len(releases)} release steps ({named}), more than one"
    nodes = set(vectors.values())
    base = vectors[forms[0][0]]
    for fid, vector in vectors.items():
        if any(n > 0 for n in vector) and any(n < 0 for n in vector):
            paths = _simple_paths(nodes, base, vector)
            if paths != 1:
                return f"its mixed-sign form {fid} is reached from its base by {paths} paths"
    return None


def _simple_paths(nodes, start, end):
    """The number of simple paths of unit steps (one ligand count up or down) from start to end
    through the count vectors `nodes`."""

    def walk(here, seen):
        if here == end:
            return 1
        total = 0
        for k in range(len(here)):
            for step in (1, -1):
                there = here[:k] + (here[k] + step,) + here[k + 1 :]
                if there in nodes and there not in seen:
                    total += walk(there, seen | {there})
        return total

    return walk(start, {start})


def _check_general(spec, declaration):
    """The general closure's admission against the species registry (module docstring): each
    ligand row a single-form species with a standard potential; each binder row a multi-form row
    whose forms bind only declared ligands (every ligand written out), with k_on declared for
    exactly the ligands its forms bind; every declared ligand bound somewhere; every form
    reachable from its base by unit steps (the envelope's network, CORE_SEAMS §19 as amended); and
    every release step inside amendment C5's registered scope (_release_scope_error), the rest
    refused, fail-closed (the lead's ruling, 19 November 2026). The movers' rules are the species
    registry's (check_closure_rows), ahead of this."""
    where = f"{MODEL_KEY} ({GENERAL_READ_ID})"
    model = species_registry.declared(spec)
    if model is None:
        raise ConfigError(f"{where}: the closure reads the species registry, which is not declared")
    ligands = set(declaration.ligands)
    for ligand in declaration.ligands:
        entry = model.entry(ligand)
        if entry is None or entry.standard_mu_RT is None:
            raise ConfigError(f"{where}: ligand row {ligand} declares no standard_mu_RT")
        if entry.forms or entry.protonated_standard_mu_RT is not None:
            raise ConfigError(f"{where}: ligand row {ligand} has forms of its own")
    bound = set()
    for row, rates in declaration.k_on:
        entry = model.entry(row)
        if entry is None or not entry.forms:
            raise ConfigError(
                f"{where}: binder row {row} declares no forms; the general closure reads the "
                "registry's forms (version 1's two-form spelling is cells.kind.rapid_proton_buffer@1's)"
            )
        forms = species_registry.forms_of(spec, row)
        binds = sorted({ligand for _, counts, _ in forms for ligand, _ in counts})
        outside = [ligand for ligand in binds if ligand not in ligands]
        if outside:
            raise ConfigError(
                f"{where}: binder row {row}'s forms bind {outside}, which the closure does not "
                "hold: every ligand of a form is a declared ligand row"
            )
        if sorted(ligand for ligand, _ in rates) != binds:
            raise ConfigError(
                f"{where}: k_on of {row} names {sorted(ligand for ligand, _ in rates)}, but its "
                f"forms bind {binds}: k_on is declared per binding"
            )
        vectors = [[dict(counts).get(ligand, 0) for ligand in binds] for _, counts, _ in forms]
        if not _unit_steps_reach(vectors):
            raise ConfigError(
                f"{where}: a form of binder row {row} is not reachable from its base by unit "
                "steps (one ligand more or fewer at a time) through declared forms"
            )
        problem = _release_scope_error(forms, declaration.proton)
        if problem is not None:
            raise ConfigError(
                f"{where}: binder row {row}: {problem}. Amendment C5 registers the envelope's "
                "release steps only in the proton row, with counts of -1, one per binder, and one "
                "path to each mixed-sign form, so the lag has no reference here: refused "
                "(fail-closed)"
            )
        bound |= set(binds)
    unbound = sorted(ligands - bound)
    if unbound:
        raise ConfigError(f"{where}: ligand rows {unbound} are bound by no declared binder")



# ---------------------------------------------------------------------------- the general closure
# cells.binding.rapid_binding@1 on the general layout (module docstring; laws/reactions/rapid_binding.py). Each
# hook above dispatches here statically, on the layout type's fields (_is_general), so version 1's
# traced operations are today's.


def _is_general(p):
    """Static: the layout of a world that declares cells.binding.rapid_binding@1 (its type holds binding_*)."""
    return "binding_rows" in type(p)._fields


def _general_binders(declaration):
    return tuple(row for row, _ in declaration.k_on)


def _general_network(spec, declaration):
    """The kernel's network arrays, from the species registry's forms (one authority)."""
    binders = []
    for row, rates in declaration.k_on:
        forms = species_registry.forms_of(spec, row)
        logs, c0 = species_registry.form_log_constants(spec, row)
        spec_forms = tuple((fid, counts, log) for (fid, counts, _), log in zip(forms, logs, strict=True))
        binders.append((row, spec_forms, c0, rates))
    try:
        return binding.network(declaration.ligands, tuple(binders))
    except ValueError as error:  # The joint margin's enumeration past its caps.
        raise ConfigError(f"{MODEL_KEY}: {error}: refused") from error


def _general_solve(amounts, p, xp):
    """(ln x [L, node], valid, T_L [L, node], T_B [B, node], held [L, node], member [B, node],
    volume [node]) at stored amounts [species, node]: the closure at every active node."""
    volume, active = _nodes(p, xp)
    nl = p.binding_held.shape[0]
    rows = p.binding_rows
    safe_v = xp.where(active, volume, 1.0)
    member = p.binding_member & active[None, :]
    held = p.binding_held & active[None, :]
    comp_l = p.binding_comp_ligand * active
    comp_b = p.binding_comp_binder * active
    total_l = amounts[rows[:nl]] / safe_v
    total_b = xp.where(member, amounts[rows[nl:]] / safe_v, 0.0)
    u, ok = binding.free_ligands(total_l, total_b, p.binding_log_beta, p.binding_counts,
                                 p.binding_present, held, comp_l, comp_b,
                                 vertices=p.binding_margin_vertices, xp=xp)
    ok = ok & positive_held_totals(total_l, held, xp=xp)  # By construction (module docstring).
    valid = xp.all(xp.where(xp.any(held, axis=0), ok, True))
    return u, valid, total_l, total_b, held, member, safe_v


def positive_held_totals(total_l, held, *, xp):
    """[node] whether every ligand total the closure holds at the node is positive (and so finite):
    the read's precondition, by construction at every stage (module docstring)."""
    return xp.all(xp.where(held, total_l > 0, True), axis=0)


def _general_terms(p, amounts, xp):
    """Phase 1's booked term per node (pJ): S_c at a closure node (NaN where a held total is <= 0,
    so the ledger refuses), 0 elsewhere."""
    u, _, total_l, total_b, held, _, safe_v = _general_solve(amounts, p, xp)
    nl = held.shape[0]
    _, _, s_c, defined = binding.booked_terms_pJ(
        u, total_l, total_b, p.binding_log_beta, p.binding_counts, p.binding_present, held,
        p.binding_mu0p[:nl], p.binding_mu0p[nl:], safe_v, p.temperature, xp=xp,
    )  # fmt: skip
    return xp.where(xp.any(held, axis=0), xp.where(defined, s_c, xp.nan), 0.0)


def _general_change(state, p, xp):
    """Phase 1's booked term's change since the start per node (pJ), formed from the stored
    increments (rapid_binding.booked_change_pJ), so it rounds at the change's scale: NaN where a
    held total is <= 0, so the ledger refuses, and 0 where the closure holds nothing."""
    u, _, _, _, held, member, safe_v = _general_solve(_amounts(state, p, xp), p, xp)
    nl, rows = held.shape[0], p.binding_rows
    reference = xp.concatenate((p.amount_reference, p.extracellular_amount_reference), axis=1)
    increment = xp.concatenate(
        (state.amount_increment, state.extracellular_amount_increment), axis=1
    )
    change, defined = binding.booked_change_pJ(
        u, p.binding_initial_u, reference[rows[:nl]], increment[rows[:nl]],
        reference[rows[nl:]], increment[rows[nl:]], p.binding_log_beta, p.binding_counts,
        p.binding_present, held, member, safe_v, p.temperature, xp=xp,
    )  # fmt: skip
    return xp.where(xp.any(held, axis=0), xp.where(defined, change, xp.nan), 0.0)


def free_log_sensitivity(read, p, *, xp):
    """The general closure's d ln c_free / d n_total at a stage, for a kind's material term (the
    kinds owner's K3b; exported through cells.modules): (D [S, S, n + o] in 1/fmol, held
    [S, n + o]) from the read the kinds' hooks receive, D[i, k] the derivative of ln of what the
    read writes into row i (a free ligand or a binder's free base form) by row k's stored total at
    the same node, exactly 0 off the closure's rows and at inactive nodes
    (rapid_binding.free_log_sensitivity_block). Its domain is a valid read's, whose held free
    ligands are positive; an empty binder's own 1/T_B is left out there. None, decided statically,
    where the layout holds no general closure: version 1's buffer is outside it (the lead's
    ruling)."""
    if not _is_general(p):
        return None
    amounts = _amounts(read, p, xp)
    volume, active = _nodes(p, xp)
    safe_v = xp.where(active, volume, 1.0)
    nl, rows = p.binding_held.shape[0], p.binding_rows
    held = p.binding_held & active[None, :]
    member = p.binding_member & active[None, :]
    free = amounts[rows] / safe_v
    u = xp.log(xp.where(held, free[:nl], 1.0))
    return binding.free_log_sensitivity_block(
        u, free[nl:], p.binding_log_beta, p.binding_counts, p.binding_present, held, member,
        safe_v, rows, amounts.shape[0], xp=xp,
    )  # fmt: skip


def _general_read(state, p, xp):
    """The stage's read: each held ligand row holds its free ligand x V, each held binder row its
    free base form c_base V, for the rates; every other row as stored."""
    amounts = _amounts(state, p, xp)
    u, valid, _, total_b, held, member, safe_v = _general_solve(amounts, p, xp)
    x, forms = binding.speciation(u, total_b, p.binding_log_beta, p.binding_counts,
                                  p.binding_present, xp=xp)
    free = xp.concatenate((x * safe_v, forms[:, 0] * safe_v), axis=0)  # [L + B, node]
    hold = xp.concatenate((held, member), axis=0)
    mask, value = binding.onto_species(p.binding_rows, hold, free, amounts.shape[0], xp=xp)
    reference = xp.concatenate((p.amount_reference, p.extracellular_amount_reference), axis=1)
    increment = xp.concatenate(
        (state.amount_increment, state.extracellular_amount_increment), axis=1
    )
    read = xp.where(mask, value - reference, increment)
    n = p.active.size
    return state._replace(
        amount_increment=read[:, :n], extracellular_amount_increment=read[:, n:]
    ), valid


def _general_stage(read, cell, outside, p, xp):
    """(lag [node] in log10 units, the largest over its ligands, 0 off the closure; pX [L, node];
    held [L, node]) at a stage: the network's first-order lag at the stage's transport of the held
    rows, from the read's free forms (no re-solve)."""
    volume, active = _nodes(p, xp)
    amounts = _amounts(read, p, xp)
    nl = p.binding_held.shape[0]
    rows = p.binding_rows
    held = p.binding_held & active[None, :]
    member = p.binding_member & active[None, :]
    safe_v = xp.where(active, volume, 1.0)
    x = xp.where(held, amounts[rows[:nl]] / safe_v, 1.0)
    base = xp.where(member, amounts[rows[nl:]] / safe_v, 0.0)
    u = xp.log(x)
    forms = binding.forms_from_free(u, base, p.binding_log_beta, p.binding_counts,
                                    p.binding_present, xp=xp)
    rates = xp.concatenate((cell, outside), axis=1)
    lag = binding.lag_first_order(
        u, forms, binding.binder_totals(forms, xp=xp),
        xp.where(held, rates[rows[:nl]] / safe_v, 0.0),
        xp.where(member, rates[rows[nl:]] / safe_v, 0.0), p.binding_log_beta, p.binding_counts,
        p.binding_present, held, p.binding_step_matrix, p.binding_step_from,
        p.binding_step_ligand, p.binding_step_kon, p.binding_conservation, xp=xp,
    )  # fmt: skip
    lag_px = xp.max(xp.abs(lag), axis=0) / binding.LN10
    px = -xp.log10(x / closure.PH_REFERENCE_mM)
    return xp.where(xp.any(held, axis=0), lag_px, 0.0), px, held


def _general_readouts(read, p, xp):
    """free_ligand_mM [L, node]: the read's ligand rows over the volume at active nodes (free at a
    closure node, as stored elsewhere), 0 at inactive ones."""
    volume, active = _nodes(p, xp)
    nl = p.binding_held.shape[0]
    amounts = _amounts(read, p, xp)
    x = amounts[p.binding_rows[:nl]] / xp.where(active, volume, 1.0)
    return (xp.where(active[None, :], x, 0.0),)


def _general_initial(spec, declaration, layout):
    m = spec.model
    ids = list(m.species_ids)
    n, o = spec.execution.capacity, spec.execution.extracellular_capacity
    nodes = [c.id for c in m.cells] + [None] * (n - len(m.cells))
    nodes += [x.id for x in m.extracellular] + [None] * (o - len(m.extracellular))
    net = _general_network(spec, declaration)
    binders = _general_binders(declaration)
    rows = (*declaration.ligands, *binders)
    member = np.zeros((len(binders), n + o), dtype=bool)
    for node, named in declaration.binders:
        for row in named:
            member[binders.index(row), nodes.index(node)] = True
    held, comp_l, comp_b = binding.connected_sets(member, net["counts"])
    c0 = species_registry.declared(spec).standard_concentration_mM
    mu0p = [species_registry.standard_potential(spec, r)[0] - math.log(c0) for r in rows]
    own = dict(
        binding_rows=np.asarray([ids.index(r) for r in rows]),
        binding_counts=net["counts"],
        binding_present=net["present"],
        binding_log_beta=net["log_beta"],
        binding_member=member,
        binding_held=held,
        binding_comp_ligand=comp_l,
        binding_comp_binder=comp_b,
        binding_margin_vertices=net["margin_vertices"],
        binding_step_matrix=net["step_matrix"],
        binding_step_from=net["step_from"],
        binding_step_ligand=net["step_ligand"],
        binding_step_kon=net["step_kon"],
        binding_conservation=net["conservation"],
        binding_mu0p=np.asarray(mu0p),
        binding_initial_pJ=np.zeros(n + o),
        binding_initial_u=np.zeros((len(declaration.ligands), n + o)),
    )
    start = SimpleNamespace(**(dict(layout) | own))
    amounts = np.concatenate((start.amount_reference, start.extracellular_amount_reference), axis=1)
    u, valid, *_ = _general_solve(amounts, start, np)
    if not valid:
        raise ConfigError(
            f"{MODEL_KEY} ({GENERAL_READ_ID}): the closure has no speciation at the start's totals "
            "at every node it holds"
        )
    terms = _general_terms(start, amounts, np)
    if not np.all(np.isfinite(terms)):
        raise ConfigError(
            f"{MODEL_KEY} ({GENERAL_READ_ID}): a held total is at or below zero at the start, "
            "where phase 1 books @3's ideal terms on the closure's rows"
        )
    own["binding_initial_pJ"] = terms
    own["binding_initial_u"] = u
    _, active = _nodes(start, np)
    px = np.where(held & active[None, :], -np.log10(np.exp(u) / closure.PH_REFERENCE_mM), 0.0)
    state = dict(
        binding_max_lag_pX=np.zeros(n + o), binding_min_pX=px, binding_max_pX=px.copy()
    )
    return state, own

def check_definition(spec):
    """Version 1's admission: no inner-model route (membrane, junction, channel or face) moves
    the proton row at a buffered node, since those routes read stored rows as concentrations.
    Kinds' movers (a transporter) read the stage's read and are admitted. The general closure's
    admission is _check_general's (and the species registry's check_closure_rows, ahead of it)."""
    from cells.models import surface_pump_v3

    declaration = dict(spec.model.kinds)[KIND_ID]
    if isinstance(declaration, GeneralDeclaration):
        _check_general(spec, declaration)
        return
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


# The fields of each layout (declared_fields, chosen statically by the structure entry, as the
# passive routes' Factored is): version 1's, today's exactly; the general closure's, which exist
# only in a world that declares cells.binding.rapid_binding@1.
V1_STATE_AXES = (
    ("proton_buffer_max_lag_pH", ("node",)),
    ("proton_buffer_min_pH", ("node",)),
    ("proton_buffer_max_pH", ("node",)),
)
V1_LAYOUT_FIELDS = (
    "proton_buffer_rows",
    "proton_buffer_member",
    "proton_buffer_k_mM",
    "proton_buffer_k_on",
    "proton_buffer_mu_RT",
    "proton_buffer_proton_mu_RT",
    "proton_buffer_c0_mM",
    "proton_buffer_initial_pJ",
)
# Gap 7's running extrema for the general closure: per node, its largest lag in log10 units over
# its ligands and every stage; per ligand and node, the free ligand's pX (-log10 x/1 M) extrema.
GENERAL_STATE_AXES = (
    ("binding_max_lag_pX", ("node",)),
    ("binding_min_pX", ("binding_ligand", "node")),
    ("binding_max_pX", ("binding_ligand", "node")),
)
GENERAL_LAYOUT_FIELDS = (
    "binding_rows",  # [L + B]: species indices, the ligand rows then the binder rows.
    "binding_counts",  # [B, F, L]
    "binding_present",  # [B, F]
    "binding_log_beta",  # [B, F], the mM frame.
    "binding_member",  # [B, node]
    "binding_held",  # [L, node]
    "binding_comp_ligand",  # [L, L, node]: the connected ligand sets.
    "binding_comp_binder",  # [L, B, node]
    "binding_margin_vertices",  # [V, L]: the joint margin's vertices (amendment C4).
    "binding_step_matrix",  # [species, steps]: the unit steps' stoichiometry.
    "binding_step_from",  # [steps]
    "binding_step_ligand",  # [steps]
    "binding_step_kon",  # [steps]
    "binding_conservation",  # [L + B, species]
    "binding_mu0p",  # [L + B]: each row's mu°/RT - ln c0 (@3's 1 mM frame).
    "binding_initial_pJ",  # [node]: the booked term at the start.
    "binding_initial_u",  # [L, node]: the free ligands' ln x (mM) at the start.
)
GENERAL_COLUMNS = ("free_ligand_mM",)


def declared_fields(entry):
    """The kind's fields for its structure entry (§7.4 (n) 5): version 1's for its entry, the
    general closure's for a GeneralEntry."""
    if isinstance(entry, GeneralEntry):
        return KindFields(GENERAL_STATE_AXES, GENERAL_LAYOUT_FIELDS, (), GENERAL_COLUMNS)
    return KindFields(V1_STATE_AXES, V1_LAYOUT_FIELDS, (), COLUMNS)


def view_sets(spec, declaration):
    """The view's set of the general closure's own axis, its ligand rows (none in version 1)."""
    if not isinstance(declaration, GeneralDeclaration):
        return {}
    return {
        "binding_ligand": {
            "id": "binding_ligand",
            "ids": list(declaration.ligands),
            "roles": {
                "ligand": "a ligand row of the closure: its stored total counts every bound "
                "equivalent from the base forms, and the closure solves its free amount per node"
            },
            "carries": [[ligand] for ligand in declaration.ligands],
        }
    }


# The run view's declarations (D154): per node, cells then outside nodes (the view's node set).
# Both layouts' fields are declared; the view keeps those a world's types hold.
_PH_FIELDS = ("proton_buffer_max_lag_pH", "proton_buffer_min_pH", "proton_buffer_max_pH")
_PX_FIELDS = tuple(field for field, _ in GENERAL_STATE_AXES)
VIEW = KindView(
    units=MappingProxyType(
        {
            **dict.fromkeys(_PH_FIELDS, "pH"),
            "free_proton_mM": "mM",
            "pH": "pH",
            **dict.fromkeys(_PX_FIELDS, "pX"),
            "free_ligand_mM": "mM",
        }
    ),
    observation_axes=MappingProxyType(
        {"free_proton_mM": ("node",), "pH": ("node",), "free_ligand_mM": ("binding_ligand", "node")}
    ),
    record_kinds=MappingProxyType(
        dict.fromkeys((*_PH_FIELDS, *COLUMNS, *_PX_FIELDS, *GENERAL_COLUMNS), "level")
    ),
    record_layers=MappingProxyType(
        dict.fromkeys((*_PH_FIELDS, *COLUMNS, *_PX_FIELDS, *GENERAL_COLUMNS), "membrane")
    ),
    axis_sets=MappingProxyType({"node": "node"}),
)


PROTON_BUFFER = BUILTIN.register(
    Kind(
        kind_id=KIND_ID,
        model_key=MODEL_KEY,
        # Gap 7: running extrema over every IMEX stage, per node (cells, then outside nodes).
        state_axes=V1_STATE_AXES,
        stage_values=stage_values,
        stage_extrema=(
            ("proton_buffer_max_lag_pH", "max"),
            ("proton_buffer_min_pH", "min"),
            ("proton_buffer_max_pH", "max"),
            ("binding_max_lag_pX", "max"),
            ("binding_min_pX", "min"),
            ("binding_max_pX", "max"),
        ),
        domain=domain,
        layout_fields=V1_LAYOUT_FIELDS,
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
        declared_fields=declared_fields,
        view=VIEW,
        view_sets=view_sets,
    )
)
