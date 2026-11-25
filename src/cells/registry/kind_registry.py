"""The kind registry of resolved_pump_tissue@3 (docs/INNER_MODEL_V4_DESIGN.md §7.4 (j), (k)).

A kind is one module's contribution to the inner model: its fields (state, layout, control and
observation columns) and optional hooks that the core calls at fixed seams. The core reaches
kinds only through the registry active for the model build: BUILTIN, unless a caller builds
inside `scope(registry)`. It imports no kind module. Built-in kinds (the cells.kinds package)
register on BUILTIN exactly as an external package would, with `registry.register(kind)`.

IDs are namespaced ("cells.transporter@1"); a bare ID resolves in the `cells` namespace, so an
outside package cannot collide with a built-in. The canonical kind order, the order in which a
structure's kinds append their fields, is the sorted namespaced ID: total, and independent of
registration, import and declaration order.

A kind's controls may follow a schedule (§7.4 (l)): the kind declares experiment keys, parses them
into a `Schedule` (named piecewise-constant series), and the schedule's breakpoints join the
experiment's change times, so each is a step boundary and the change records carry its values.
"""

import importlib
import math
import re
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, fields, replace
from functools import cache
from types import MappingProxyType
from typing import NamedTuple

import numpy as np

# The kind interface's parsing surface (§7.4 (k); D180's external modules): a kind's parse and
# check_definition refuse with ConfigError and may use these public helpers, never the
# underscored names of cells.definitions.specs.
from cells.definitions.specs import ConfigError, bounded_integer, finite_number, require_fields

__all__ = (
    "BUILTIN",
    "ENERGY_ROLES",
    "HEAT_SUFFIX",
    "MOVES_END",
    "MOVES_ENDS",
    "LEDGER_TERM_ROLES",
    "PARTITION_ROLES",
    "DG_BASES",
    "TEMPERATURE_INDEPENDENT",
    "WORK_SUFFIX",
    "ConfigError",
    "AXIS_HOST_KINDS",
    "SHARED_AXES",
    "AxisHost",
    "EntityBinding",
    "FreeEnergyEntry",
    "EnergyRole",
    "HOOKS",
    "Kind",
    "KindFields",
    "KindRates",
    "KindView",
    "KindRegistry",
    "LabelView",
    "ONE_WAY_HOOKS",
    "OneWayRecord",
    "PartitionRole",
    "Schedule",
    "active",
    "bound",
    "bounded_integer",
    "declaration_errors",
    "declared_kinds",
    "declared_schedule",
    "energy_role",
    "finite_number",
    "free_energy_entries",
    "axis_sizes",
    "kind_ledgers",
    "kind_role_species",
    "kind_standard_free_energies",
    "label_refusal_errors",
    "law_count_names",
    "law_ends",
    "law_roles",
    "entity_axes",
    "presence_fields",
    "misshapen_errors",
    "missing_partition_roles",
    "parse_series",
    "partition_fields",
    "qualified",
    "require_fields",
    "scope",
    "series_to_dict",
)

NAMESPACE = "cells"


def qualified(identifier):
    """The namespaced form of a kind or law ID: a bare ID belongs to the cells namespace."""
    if not isinstance(identifier, str) or not identifier:
        raise ValueError(f"A kind or law ID must be a non-empty string, not {identifier!r}")
    head = identifier.split("@", 1)[0]
    return identifier if "." in head else f"{NAMESPACE}.{identifier}"


# ---------------------------------------------------------------------- schedules (§7.4 (l))


def _points(points, name):
    """((time, value), ...) as floats: non-empty, from time 0, strictly increasing, finite."""
    if not isinstance(points, tuple) or not points:
        raise ConfigError(f"Series {name!r} holds one or more (time, value) points")
    out = []
    for point in points:
        if not (isinstance(point, tuple) and len(point) == 2) or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) for v in point
        ):
            raise ConfigError(f"Series {name!r}: each point is a (time, value) pair of numbers")
        time, value = float(point[0]), float(point[1])
        if not (math.isfinite(time) and math.isfinite(value)):
            raise ConfigError(f"Series {name!r}: times and values are finite")
        out.append((time, value))
    if out[0][0] != 0.0 or any(b[0] <= a[0] for a, b in zip(out, out[1:], strict=False)):
        raise ConfigError(f"Series {name!r} starts at time 0 and its times strictly increase")
    return tuple(out)


@dataclass(frozen=True)
class Schedule:
    """A kind's parsed control schedule (§7.4 (l)): named series, each right-continuous and
    piecewise constant from time 0.

    series: ((name, ((time, value), ...)), ...), names distinct and non-empty, times from 0 and
    strictly increasing, values finite (stored as floats). Its breakpoints (`times`) join the
    experiment's change times, so each is a step boundary; its values there (`at`) join the change
    records, so a branch cannot rewrite them before its checkpoint; `values` evaluates one series.
    """

    series: tuple

    def __post_init__(self):
        if not isinstance(self.series, tuple) or not self.series:
            raise ConfigError("A schedule holds one or more named series")
        names, normal = set(), []
        for item in self.series:
            if not (isinstance(item, tuple) and len(item) == 2):
                raise ConfigError("A schedule's series are (name, ((time, value), ...)) pairs")
            name, points = item
            if not isinstance(name, str) or not name or name in names:
                raise ConfigError(f"Series names are distinct, non-empty strings, not {name!r}")
            names.add(name)
            normal.append((name, _points(points, name)))
        object.__setattr__(self, "series", tuple(normal))

    @property
    def names(self):
        return tuple(name for name, _ in self.series)

    @property
    def times(self):
        """Every breakpoint of every series, sorted (0 included)."""
        return tuple(sorted({time for _, points in self.series for time, _ in points}))

    def at(self, time):
        """Each series' value at `time`, in series order (right-continuous)."""
        return tuple(
            points[np.searchsorted([t for t, _ in points], time, side="right") - 1][1]
            for _, points in self.series
        )

    def values(self, name, times):
        """The named series at `times` (right-continuous), float64."""
        points = dict(self.series)[name]
        times = np.asarray(times, dtype=np.float64)
        if np.any(times < 0):
            raise ValueError("A schedule starts at time 0")
        held = np.asarray([value for _, value in points], dtype=np.float64)
        return held[np.searchsorted([t for t, _ in points], times, side="right") - 1]


def parse_series(entries, name, *, value="value", unit_interval=True):
    """((time, value), ...) from a definition's [{"time": t, value: v}, ...] (§7.4 (l)): non-empty,
    from time 0, strictly increasing, values finite, and in [0, 1] when unit_interval (rule (d)'s
    availabilities). FR-5's injury and resealing schedules are two such lists per population."""
    if not isinstance(entries, list) or not entries:
        raise ConfigError(f"{name} is a non-empty list of {{time, {value}}} entries")
    points = []
    for entry in entries:
        require_fields(entry, {"time", value}, f"an entry of {name}")
        time = finite_number(entry["time"], f"{name}: time")
        held = entry[value]
        if isinstance(held, bool) or not isinstance(held, (int, float)):
            raise ConfigError(f"{name}: {value} must be a finite number")
        held = float(held)
        if not math.isfinite(held) or (unit_interval and not 0.0 <= held <= 1.0):
            raise ConfigError(
                f"{name}: {value} must be finite" + (" and in [0, 1]" if unit_interval else "")
            )
        points.append((time, held))
    return _points(tuple(points), name)


def series_to_dict(series, *, value="value"):
    """parse_series' inverse: [{"time": t, value: v}, ...]."""
    return [{"time": time, value: held} for time, held in series]


def declared_schedule(spec, kind_id):
    """The parsed Schedule of a declared kind in this definition's experiment (§7.4 (l)), or None
    for a kind that declares no experiment keys."""
    return dict(getattr(spec.experiment, "kinds", ())).get(qualified(kind_id))


@dataclass(frozen=True, eq=False)
class Kind:
    """One kind's declaration (§7.4 (k)). Fields are appended in canonical kind order.

    state_axes: ((field, (axis, ...)), ...); layout_fields, control_fields and readout_columns:
    field names. Every hook is optional and pure, closing over the kind's declaration only (P5:
    never over a value). No kind reads another kind's fields. Scope rules (§7.4 (j), ruled): its
    ledger terms fold into today's ten ledgers by role; its state fields are observation columns
    right after today's state fields; its material moves land in the shared inventory; its
    controls are availabilities in [0, 1] unless control_domain says otherwise.

    The hooks, as resolved_pump_tissue@3 calls them (`p` is the world's layout, in the
    structure's layout type; `state` and `control` are in the structure's state and control
    types; `declaration` is what `parse` returned):
    - definition: `parse(entries, base)` -> declaration, from the kind's model-key block and the
      parsed @2 base definition; `to_dict(declaration)` -> that block; `structure_entry(
      declaration)` -> its hashable, value-free part of the structure (compile key, batch
      signature, cached implementation); `initial(spec, declaration, layout)` -> ({state field:
      array}, {layout field: array}); `control_values(spec, declaration, times)` -> {control
      field: [time, ...] array}; `moved_rows(declaration)` -> ((species, node ID), ...) or
      ((species, node ID, law ID), ...), the rows it moves in the step; `check_definition(spec)`,
      its refusals, after the species registry's and before @3's.
    - schedule (§7.4 (l)): `experiment_keys`, the kind's own keys in the definition's experiment
      (each optional in a definition); `parse_schedule(raw, base, declaration)` -> a Schedule,
      `raw` being {key: value} for the keys the definition gives (possibly none: the kind's
      default), or None where it gives none of them: no schedule, so the definition keeps
      today's change records by value and type (the lead's ruling (A), 19 November 2026);
      `schedule_to_dict(schedule, declaration)` -> the {key: value} to write back (the
      kind omits its default, so a definition that omits a key keeps its form). The schedule's
      breakpoints join the change times (each a step boundary) and its values the change records.
      @3 evaluates `control_values` once per change record, at the change times, and holds each
      row over the steps that record governs, so a kind's controls are constant between change
      times on every path; a scheduled kind reads its schedule with declared_schedule(spec, ID).
    - fields per declaration (§7.4 (n) 5): `declared_fields(entry)` -> KindFields(state_axes,
      layout_fields, control_fields, readout_columns) for its structure entry, in place of the
      static ones; the core binds each declared kind to its entry (`bound`) wherever it resolves a
      structure's kinds, so a field exists only where the declaration needs it.
    - the routing door (§7.4 (n)): a source declares `factor_sources(declaration)` -> (source ID,
      ...) and `factors(read, p, *, xp)` -> [len(sources)] values at the stage (from its own
      fields and the stage's read state); a sink declares `routed_controls(declaration)` ->
      ((control field, slot, (source ID, ...)), ...) on its own control fields. Binding resolves
      every source ID (the structure's `routes`); at every stage, after the stage read and before
      any kind's rates, stage_term or readouts, each routed slot becomes its held value x its
      sources' values, a left fold in declared order. A factor outside [0, 1] or not finite
      refuses the row or the step; `book` receives the held control.
    - stage: `stage_read(state, p, *, xp)` -> (the state whose amount fields hold the amounts
      every rate of the stage reads, valid), composed in hook order; a failed read refuses the
      step, and domain_valid evaluates the reads at every checked state (the step's end
      included). The read changes the concentrations the rates see, never charge: the field
      solve keeps the stored rows' charges. It must declare `stage_rows(declaration)` ->
      ((species, node ID), ...), every row it reads or rewrites, and two kinds' stage reads on a
      shared row are refused at binding (they do not commute). `rates(state, potentials,
      control, p, *, xp)` -> KindRates: inward-positive node changes (cell
      [species, cell], outside [species, outside node]) into the shared inventory, the kind's own
      state derivatives {field: array}, and heat and work rates (pJ/s), and optionally
      stored_pJ_s, the rate of its stored free energy (its stored_pJ's) less the part its read
      carries, which joins the stage energy-rate observation (§7.4 (m)); `potentials` are the
      stage's node potentials, cells then outside nodes (V). `stage_check(read, cell, outside,
      p, *, xp)` -> one bool, after every rate of the stage: `read` is the read state, `cell`
      [species, cell] and `outside` [species, outside node] the stage's total node rates (fmol/s;
      explicit stages without the implicit face drift); a false check refuses the step (FR-4's
      envelope: the closure's lag at the stage's transport).
    - step size (B7 for kinds): `stage_term(read, potentials, control, p, *, xp)` -> [cells,
      then outside nodes] conductance (S) of the kind's charged routes at the stage's read and
      node potentials (a pump's electrogenic slope, reversed past its head included; potentials
      is None when membrane_rate is called without them); a patch's slope goes to both of its
      ends (surface_pump_v3.patch_node_conductance). membrane_rate's per-stage refusal, dt x rate
      <= EXPLICIT_STEP_BOUND, then holds at every cell and every free outside node (a face-free
      compartment's included); `bound_rate(spec,
      declaration)` -> 1/s, a definition-time bound term the host step checks hold to the same
      bound (the passive law's dt L <= 1); `material_term(read, potentials, control, p, *, xp)`
      -> [cells, then outside nodes] the kind's material slope (1/s) at the stage's read amounts
      and node potentials: per node, the largest |dJ/dn| of a row it moves there (a neutral
      transporter's k S n e^a / n near its static head grows as the node empties, which no
      definition-time bound can follow). surface_pump_v3.material_rate sums the kinds' terms per
      node, and the step refuses at every explicit stage where dt x its largest over cells and
      non-held outside nodes exceeds the same bound (the material counterpart of stage_term; the
      FR-4/FR-5 note's §17, D4). Without a kind that declares it, no program changes.
    - one writer: `held_rows(declaration)` -> ((species, node ID), ...), rows the kind reads and
      never moves (held fuel); binding refuses any inner route or other kind that moves one.
    - per-stage diagnostics (gap 7): `stage_values(read, cell, outside, p, *, xp)` -> {own state
      field: value} at every explicit stage of an IMEX step, with the stage_check's arguments;
      `stage_extrema` = ((field, "max" | "min"), ...) names the reduction. The step's end state
      holds each field's running extremum: the start's value and every stage of the step (the
      closure's largest lag, the cytosol's smallest and largest pH). @3 refuses declared kinds
      under RK4 (surface_pump_v3._check_kinds_solver: every step guard here is the IMEX step's).
    - step end: `book(applied, start, end, control, p, dt, *, xp)` -> ({own state field: new
      value}, valid), after the tableau's combination; `applied(name)` is the step's applied rate
      of a state field (the tableau's weights), `start` the step's start state and `end` its end
      state before any kind books, the same for every kind, and only the kind's own state fields
      may be written, so bookings commute. `control` is the step's held control, constant over
      the step (§7.4 (l): a schedule's breakpoints are step boundaries), so a kind can book an
      exact per-step update at the step's values (FR-5's damage step). A false valid refuses the
      step (§7.5's negative exact share).
    - checks (traced on the device at binding, with stage_read, so the device's row checks
      include them as the host's do; they branch on no value in Python): `domain(state, p, *,
      xp)` -> one bool, and-ed into domain_valid; `control_domain(control, p, *, xp)` -> one
      bool, in place of the [0, 1] rule for its controls; `ledger_terms(state, p, *, xp)` ->
      {"cell": [species, cell], "outside": [species, outside node], "produced": [species],
      "heat_pJ": ..., "work_pJ": ..., "stored_pJ": ...} (any subset): cumulative inward-positive
      node changes, the net amount per species the kind created (+) or consumed (-) (a
      reaction's record, which the global material ledger otherwise holds to zero; charge-neutral,
      or the global charge ledger refuses it; §7.4 (m)), heat and work accumulators, and the free
      energy the kind stores beyond the stored rows' own terms (its change since the start),
      folded into balances, device_balances and the ledger magnitudes by role.
    - observation: `readouts(state, read, potentials, control, p, *, xp)` -> its readout columns,
      in order, after today's (on the host): the stored state, the row's read state (free h at a
      buffered node) and its node potentials, so a charged law can report its instantaneous rate.
    - a kind's own domain at a stage: KindRates.valid (from `rates`, at the stage's read and
      potentials; a charged law's V-dependent domain); false refuses the row or the step.

    The seams' declarations (docs/CORE_SEAMS_DESIGN.md §4.2, §6.1, §7.3), each optional and read
    on the host only, so a kind that declares none keeps today's behaviour and its programs:
    - `energy_roles`, {state field: EnergyRole(role, monotone)}: heat, work or stored, and
      whether the field never decreases per element (§6.1). An undeclared field takes today's
      suffix rule (energy_role); a declaration may not contradict it on a suffixed field, since
      today's energy-flow sums read heat and work by suffix;
    - `heat_bookings`, the versioned booking IDs (name@major) its routes admit beyond the tableau,
      which every mover class admits and which is never listed (§6.1, one booking per mover class:
      the definition picks, InnerStructure.heat_bookings holds the pick);
    - `partition_roles`, {field: PartitionRole(role, fill)}: extensive, intensive, history, or
      structural with its fill, for each field a split, a retirement or a close acts on
      (partition_fields: state, layout and control). A kind with a field left undeclared stays
      refused beside closers (§4.2, fail-closed; missing_partition_roles);
    - `field_axes`, {layout or control field: (axis, ...)}: the axes of each, as state_axes gives
      a state field's (CORE_SEAMS §18, B1's lift); `axis_hosts`, {own axis: AxisHost(kind,
      index)}: for each axis of its own (an entity axis that is not one of @3's), the kind of host
      its entities sit on (AXIS_HOST_KINDS) and the layout field holding each entity's host index.
      The composite lifts its refusal beside closers only for a kind that declares these and all
      its roles; `internal_axes`, (axis, ...): the axes internal to its laws (modes, rows,
      saturation factors, bands, diagram edges and terms), which carry no entities: a split copies
      them whole and none is hosted (the kinds owner's Q5, ruled yes, 19 November 2026), so an
      adapter counts an axis as an entity axis only when it is neither @3's shared axis nor one of
      these; `presence`, {entity axis: (layout field, ...)}: for each entity axis, the fields
      saying which of its entities are present, every mask its rates, readouts and stage terms
      read (the transporter's transporter_present and its two law masks are the model), each a
      bool layout field on exactly that axis, structural with fill False. They are Q2's presence
      gate's declaration (CORE_SEAMS §18 at 931b6606, widened to a tuple on 19 November): once the
      gate lands, the core ANDs each with its entity's host's activity, where a closer is
      declared, before the kind's rates, readouts and stage checks. Until then every kind with an
      entity axis stays refused beside a closer (Q7 (a)), and after it every kind that declares
      none. entity_axes and presence_fields read them for the core; `dispatch_masks`, (field,
      ...): its fields that are either full on their declared axes or empty there (length 0) by
      static dispatch, as the transporter's per-law masks are where their law is undeclared. The
      array-axes check admits length 0 for these alone (refuse_misshapen, D228 item 6);
    - `standard_free_energies(declaration)` -> (FreeEnergyEntry, ...), the reaction-level standard
      free energies it declares (§7.1, seam E), each with the cycle law and mode that produced it,
      a law the kind hosts with a general form, or None for both, and its dG° as dG°/RT or, for
      a law that cites kJ/mol, as dG° in kJ/mol with its temperature basis, which the species
      registry converts at the world's temperature (D234); () when it declares none. The species
      registry's check compares each with its own sum of nu mu°/RT (kind_standard_free_energies
      checks the form);
    - `role_species(declaration)` -> (EntityBinding, ...), one per entity the declaration declares
      (a transporter population, say), in its own entity order: the cycle law the entity runs,
      one the kind hosts; the species each of that law's roles binds, the roles being those its
      change rows name (registry/laws.cycle_changes' role column, a general form's "role@end"
      read as its role); the node at each end its rows name; and its values for the law's
      parameter-named counts. Entities of one law may bind different species and values, so each
      entity's rows resolve on their own. §5.2's admission reads it beside a general closure,
      mapping entities to the closure node's rows through moved_rows and resolving the counts
      itself, and refuses a mover kind without it (kind_role_species checks it when read;
      law_roles and law_ends give a law's roles and ends);
    - `ledgers(declaration)` -> ((ledger, diagnostic), ...), the kind's own conserved quantities
      (§7.3; INNER_MODEL_V4_DESIGN §7.4 (p)), each valued under its own name in `ledger_terms`,
      and `ledger_bounds(row, p, tol, steps, *, xp)` -> their bounds, in that order; declared
      together (kind_ledgers checks the hook's result).

    FR-42's hook (docs/NEUTRAL_LABELS_DESIGN.md §11; D289, D303 item 6), two optional hooks that
    only a labelled world calls, so KindRates, the per-stage programs and every unlabelled trace are
    unchanged (D148 case 2):
    - `label_refusals(declaration, species)` -> [reason, ...]: host side, at the definition, the
      reasons the kind cannot carry the labelled species (their IDs, in the label rows' order),
      judged on its own moved rows (moved_rows) and only for the species given; [] where it can.
      A kind with a `rates` hook and no `label_refusals` is refused while any row is labelled
      (label_refusal_errors: fail-closed);
    - `label_transfers(start, end, p, dt, rows, *, weight=None, xp)` -> ((amount [m, entity] fmol
      over the step, each >= 0, source [entity], destination [entity]), ...): the labelled rows'
      one-way amounts over one IMEX step, nodes on the core's combined axis (cells, then outside
      nodes), `rows` the labelled species' rows (traced), `p` the presence-gated layout its rates
      see. `start` and `end` are LabelViews. Under ARS(2,2,2), N2 and other tableaux `end` is
      complete and weight None: the trapezoid of the kind's one-way fluxes at the two ends. Under
      the Euler IMEX `end` holds its state alone and weight = dt a[last, 0] >= 0: weight times
      the one-way fluxes at the start. Either way the gap to the kind's own booked net (its
      cumulative field, end less start) is added on the side its sign gives, so forward less
      backward is the booked move at rounding and both stay >= 0. The core appends these after
      its own transfers. A kind declares it only beside label_refusals.

    FR-50's one-way records (D327; the FR-49/50/51 design note §2.3; the registered protocol
    fr50-one-way-records-v1), opt-in per route, so every definition without them keeps its fields,
    entries and programs (D148):
    - `one_way_records`: (OneWayRecord(net, forward, backward, gap), ...), the records the
      declaration declares, from declared_fields' KindFields.one_way_records (bound() sets it). Each
      names a net record of the kind (a cumulative state field) and the kind's own state fields of
      its forward and backward records and its gap, `one_way_gap_relative`, all in one shape;
    - `one_way_fluxes(view, p, *, xp)` -> {net field: (forward, backward)}: each record's one-way
      fluxes (fmol/s, or fmol of cycles per s, each >= 0) at one end of a step (a LabelView), in the
      record's shape, 0 where an entity does not record;
    - `one_way_nets(state, p, *, xp)` -> {net field: value}: the net record at a state, in the
      record's shape, 0 where an entity does not record.
    bound() sets both hooks to None where the declaration declares no record. @3's IMEX step applies
    the shared rule (numerics/one_way_split.py) to each record over the step, at the same ends as
    FR-42's labels (one end view serves both), and writes the record fields after the kinds book:
    F += F_t + max(g, 0), B += B_t + max(-g, 0) and gap = max(gap, r). The records are passive, so
    they never refuse a step. A pair whose step is unresolved (the end view's solve failed, or an
    amount is not finite) keeps its records. Its gap becomes surface_pump_v3.ONE_WAY_UNRESOLVED,
    2.0, outside r's range [0, 1] by design. The running maximum keeps that value for the rest of
    the run, so every reading of the gap fails closed (the lead's rulings, 24 November 2026).
    """

    kind_id: str
    model_key: str
    state_axes: tuple = ()
    layout_fields: tuple = ()
    control_fields: tuple = ()
    readout_columns: tuple = ()
    parse: Callable | None = None
    to_dict: Callable | None = None
    structure_entry: Callable | None = None
    initial: Callable | None = None
    control_values: Callable | None = None
    stage_read: Callable | None = None
    stage_rows: Callable | None = None
    rates: Callable | None = None
    stage_check: Callable | None = None
    stage_term: Callable | None = None
    bound_rate: Callable | None = None
    material_term: Callable | None = None
    held_rows: Callable | None = None
    stage_values: Callable | None = None
    stage_extrema: tuple = ()
    book: Callable | None = None
    ledger_terms: Callable | None = None
    domain: Callable | None = None
    control_domain: Callable | None = None
    readouts: Callable | None = None
    moved_rows: Callable | None = None
    check_definition: Callable | None = None
    # §7.4 (l): the kind's schedule in the definition's experiment.
    experiment_keys: tuple = ()
    parse_schedule: Callable | None = None
    schedule_to_dict: Callable | None = None
    # §7.4 (n): fields that depend on the declaration, and the routing door.
    declared_fields: Callable | None = None
    factor_sources: Callable | None = None
    factors: Callable | None = None
    routed_controls: Callable | None = None
    # The run view (D154): its fields' declarations, and its own axes' sets.
    view: object = None  # A KindView.
    view_sets: Callable | None = None
    # The seams' declarations (CORE_SEAMS §4.2, §6.1, §7.3; the docstring's last list).
    energy_roles: object = MappingProxyType({})  # {state field: EnergyRole}
    heat_bookings: tuple = ()  # Versioned booking IDs its routes admit beyond the tableau.
    partition_roles: object = MappingProxyType({})  # {field: PartitionRole}
    ledgers: Callable | None = None  # (declaration) -> ((ledger, diagnostic), ...)
    ledger_bounds: Callable | None = None  # (row, p, tol, steps, *, xp) -> their bounds
    field_axes: object = MappingProxyType({})  # {layout or control field: (axis, ...)}
    axis_hosts: object = MappingProxyType({})  # {own axis: AxisHost}
    internal_axes: tuple = ()  # Its laws' internal axes: copied whole at a split, never hosted.
    presence: object = MappingProxyType({})  # {entity axis: (bool presence layout field, ...)}
    standard_free_energies: Callable | None = None  # (declaration) -> (FreeEnergyEntry, ...)
    role_species: Callable | None = None  # (declaration) -> (EntityBinding, ...)
    dispatch_masks: tuple = ()  # Fields full on their axes, or empty there by static dispatch.
    # FR-42's hook (the docstring's last list; D303 item 6): traced only where rows are labelled.
    label_refusals: Callable | None = None  # (declaration, species) -> [reason, ...]
    label_transfers: Callable | None = None  # (start, end, p, dt, rows, *, weight, xp) -> transfers
    # FR-50's one-way records (the docstring's last list): only where a declaration declares one.
    one_way_records: tuple = ()  # (OneWayRecord, ...), bound per declaration (declared_fields).
    one_way_fluxes: Callable | None = None  # (view, p, *, xp) -> {net: (forward, backward)}
    one_way_nets: Callable | None = None  # (state, p, *, xp) -> {net: its value, record-shaped}

    @property
    def state_fields(self):
        """The kind's own state field names, in declared order."""
        return tuple(field for field, _ in self.state_axes)


# The kind contract's hooks: every field of Kind that holds a callable or None.
HOOKS = tuple(
    f.name for f in fields(Kind) if f.type == Callable | None and f.name != "declared_fields"
)


class KindFields(NamedTuple):
    """A kind's fields for one structure entry (§7.4 (n) 5): its declared_fields(entry); and
    `without`, the hooks that entry does not have (HOOKS' names), which bound() sets to None, so a
    hook a later layout adds (material_term, say) never reaches an earlier entry's programs (the
    kinds owner's request, design statement 1 §6)."""

    state_axes: tuple  # ((field, (axis, ...)), ...)
    layout_fields: tuple
    control_fields: tuple
    readout_columns: tuple
    without: tuple = ()
    one_way_records: tuple = ()  # FR-50: (OneWayRecord, ...) the entry declares.


class OneWayRecord(NamedTuple):
    """FR-50: one of a kind's one-way record pairs, beside the net record it closes to."""

    net: str  # The net record: a cumulative state field of the kind.
    forward: str  # The forward record's state field (cumulative, in the net record's unit).
    backward: str  # The backward record's.
    gap: str  # one_way_gap_relative: the running maximum of each step's relative gap.


ONE_WAY_HOOKS = ("one_way_fluxes", "one_way_nets")  # None wherever no record is declared.


class KindRates(NamedTuple):
    """A kind's rates at one stage (§7.4 (k), the rates hook): cell [S, n] and outside [S, o]
    inward-positive node changes, which land in the shared inventory (rule (c)); its own state
    fields' derivatives; its heat and work rates (pJ/s, joining the energy rate by role).
    membrane_flux: what it carries across membrane patches, outward [S, membrane] (fmol/s), or
    None; it joins the patches' total flux and membrane current (observations, not ledgers: its
    moves are already in cell and outside). valid: its own domain at the stage's read and
    potentials (a charged law's V-dependent domain, such as |dG_cyc/RT| <= 80); false refuses the
    row or the step. stored_pJ_s (§7.4 (m), gap 2): the rate (pJ/s) of the free energy the kind
    stores beyond the stored rows' own terms (its ledger_terms' stored_pJ), less the part its stage
    read carries (the chemical rate is taken at the read's concentrations, so B4's closure term is
    carried and B4 gives none), or None; it joins the stage energy-rate observation by role.

    Part of the kind contract (docs/CORE_SEAMS_DESIGN.md §8.5): models/surface_pump_v3.py, where it
    was defined, re-exports this object."""

    cell: object
    outside: object
    derivatives: dict
    heat_pJ_s: object
    work_pJ_s: object
    membrane_flux: object = None
    valid: object = True
    stored_pJ_s: object = None


class LabelView(NamedTuple):
    """FR-42: one end of a step as the labelled rows' one-way terms read it: @3's own
    (models/surface_pump_v3.one_way_fluxes) and a kind's (its label_transfers hook takes the start
    and the end). It holds the structure's state; its kinds' stage read (the state itself without
    kinds); its node potentials (V, cells then outside nodes); and the control the stage's rates
    see there (the routing door's where routes are declared, else the step's). On the Euler IMEX
    the end carries only its state, for the booked nets: its fluxes are the start's, weighted."""

    state: object
    read: object = None
    potentials: object = None
    control: object = None


class KindView(NamedTuple):
    """A kind's run-view declarations (docs/RUN_VIEW_DESIGN.md §3; D154), in the operator
    contract's forms, for its state fields and readout columns: the inner model's implementation
    object folds them in after @3's own (UNITS, OBSERVATION_AXES, RECORD_KINDS, ORIENTATION,
    RECORD_LAYERS, VIEW_LAYERS, RECORD_DIAGNOSTICS, RECORD_REFERENCES). axis_sets maps an axis of
    its fields to an existing view set (the buffer's "node": cells, then outside nodes); a kind's
    own axes get their sets from its view_sets(spec, declaration) hook, {axis: {"id", "ids",
    "roles", per-entity facts}}. record_diagnostics names its fields that are residuals of its own
    checks (none for today's kinds) and record_references {increment field: reference layout
    field} (none: today's kinds store no increment against a reference)."""

    units: object = MappingProxyType({})  # {field: unit}
    observation_axes: object = MappingProxyType({})  # {readout column: (axis, ...)}
    record_kinds: object = MappingProxyType({})  # {field: level | amount | cumulative | rate}
    orientation: object = MappingProxyType({})  # {field: {from, to, says} | {plus, minus, says}}
    record_layers: object = MappingProxyType({})  # {field: layer id}
    view_layers: tuple = ()  # Layers it adds: ({id, label, representation}, ...)
    axis_sets: object = MappingProxyType({})  # {axis: existing view set id}
    record_diagnostics: tuple = ()  # Its fields that are residuals of its own checks.
    record_references: object = MappingProxyType({})  # {increment field: reference layout field}


# ---------------------------------------------------------------------- the seams' declarations
# (docs/CORE_SEAMS_DESIGN.md §4.2, §6.1, §7.3; Kind's docstring, its last list)

HEAT_SUFFIX = "_dissipated_energy_pJ"  # Today's suffix rule, as operators/contract.py states it.
WORK_SUFFIX = "_work_pJ"
ENERGY_ROLES = ("heat", "work", "stored")
PARTITION_ROLES = ("extensive", "intensive", "history", "structural")
# ledger_terms' keys that fold into today's ten ledgers by role (rule (a)); a kind's own ledgers
# take other names.
LEDGER_TERM_ROLES = ("cell", "outside", "produced", "heat_pJ", "work_pJ", "stored_pJ")
_BOOKING_ID = re.compile(r"(?:[a-z][a-z0-9_]*\.){0,2}[a-z][a-z0-9_]*@[1-9][0-9]*")  # name@major


class EnergyRole(NamedTuple):
    """A state field's energy role (CORE_SEAMS §6.1): `role`, heat, work or stored; `monotone`,
    whether the field never decreases per element (the dissipation check reads it)."""

    role: str
    monotone: bool


class PartitionRole(NamedTuple):
    """A field's role at a split, a retirement and a close (CORE_SEAMS §4.2):
    - extensive: divided by the host's fraction with the anchor rule, so the daughters sum to the
      parent exactly; padded at retirement;
    - intensive: copied; padded at retirement;
    - history: each daughter starts from 0; at retirement it moves into the closer's record;
    - structural: as declared (law, host, orientation); padded with `fill` at retirement.
    `fill` is a structural field's padding value (a finite number or a bool) and None for the
    other roles."""

    role: str
    fill: object = None


# @3's axes that carry no entities, shared by every field on them (B1's adapter's SHARED_AXES).
SHARED_AXES = ("species", "gate")

# The kinds of host a kind's own entities sit on, each with the slot axis of @3's that indexes them
# (models/surface_pump_v3: HOST_KINDS' patch and junction, and the nodes).
AXIS_HOST_KINDS = MappingProxyType(
    {
        "cell": "cell_slot",
        "outside_node": "extracellular_slot",
        "patch": "membrane_slot",
        "junction": "edge_slot",
    }
)


class AxisHost(NamedTuple):
    """The host of a kind's own axis (Kind.axis_hosts): `kind`, one of AXIS_HOST_KINDS, and
    `index`, the kind's layout field holding each entity's host index on that kind's slot axis."""

    kind: str
    index: str


# The ends of a moves-only (version 1) cycle law, whose change rows carry no "@end": its host
# patch's inside and outside. Its moves are inward-positive at the inside (MOVES_END), and the
# same counts land with the opposite sign at the outside, so each role crosses the patch. A
# general form's rows name their own ends.
MOVES_END = "inside"
MOVES_ENDS = (MOVES_END, "outside")


class EntityBinding(NamedTuple):
    """One entity of a declaration as §5.2's admission resolves its rows (Kind.role_species, D142):
    `law_id`, the cycle law it runs, one its kind hosts; `roles`, {role: species ID}, the species
    each of that law's roles binds; `ends`, {end: node ID}, the node at each end its change rows
    name (a general form's "@end" names, as its patch's inside and outside; MOVES_ENDS for a
    moves-only law, whose inward-positive moves at the inside land with the opposite sign at the
    outside); and `parameters`, {name: value}, its values for the law's parameter-named
    counts, since entities of one law may differ. kind_role_species checks it."""

    law_id: str
    roles: object = MappingProxyType({})  # {role: species ID}
    ends: object = MappingProxyType({})  # {end: node ID}
    parameters: object = MappingProxyType({})  # {name: value}


# How a standard free energy given in kJ/mol depends on temperature (FreeEnergyEntry.dG_basis):
# TEMPERATURE_INDEPENDENT, its declarer treating the cited dG° as the same at every temperature, so
# dG°/RT at a world's T is dG° / (R T). The table admits a later basis (one carrying dH°, say) as a
# new name, never a new meaning for an existing one (D234's option (b), 19 November 2026).
TEMPERATURE_INDEPENDENT = "temperature_independent"
DG_BASES = (TEMPERATURE_INDEPENDENT,)


class FreeEnergyEntry(NamedTuple):
    """One reaction-level standard free energy a kind or an operator declares (seam E, §7.1;
    D142): `stoichiometry`, ((species, nu), ...), nu signed, products positive; dG° in exactly one
    of two forms, `dG_RT`, dG°/RT, or `dG_kJ_mol`, dG° in kJ/mol with its `dG_basis`, how it
    depends on temperature (one of DG_BASES); `c0`, the standard concentration in mM that either
    form's dG° is at; and `law_id` and `mode`, the cycle law and the mode of its form that produced
    it, or None where none did (an operator's reaction, say). A law that cites dG° in kJ/mol (Beard
    2005's tables, say) gives it so, since no temperature is written into a law: the species
    registry converts it to dG°/RT at the world's declared temperature, the one conversion (D234's
    option (b)), and compares each entry with its own sum of nu mu°/RT. `dG_RT_offset`, beside
    dG_kJ_mol alone (0 by default), is a temperature-free term in RT units that the conversion adds:
    dG°/RT = 1000 dG_kJ_mol / (R T) + dG_RT_offset. A value cited at pH 7 puts nu_H ln 10^7 there,
    and, for a total, nu ln P(10^-7 M), so the temperature-scaled and temperature-free parts split
    as the species registry's named sets split them; the basis refers to the kJ part (the lead's
    ruling with the binding owner, 20 November 2026). The binding owner's check
    computes each entry's band from the law's form, never from the entry, so no band is
    self-certified. free_energy_entries checks it. Every field after the stoichiometry has a
    default, so either form is written by keyword; today's (stoichiometry, dG_RT, c0) positions
    are kept."""

    stoichiometry: tuple
    dG_RT: float | None = None
    c0: float | None = None
    law_id: str | None = None
    mode: str | None = None
    dG_kJ_mol: float | None = None
    dG_basis: str | None = None
    dG_RT_offset: float = 0.0


def _named(value):
    return isinstance(value, str) and bool(value)


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def free_energy_entries(entries, hosted, where):
    """The checked entries of a standard_free_energies hook, a kind's or an operator's (`where`
    names it in each refusal): a tuple of FreeEnergyEntry, each with a stoichiometry of distinct
    named species with signed nonzero coefficients, dG° in exactly one form (dG°/RT finite, or
    dG° in kJ/mol finite with a basis from DG_BASES, and neither a basis nor a nonzero
    dG_RT_offset beside dG°/RT), a finite dG_RT_offset, c0 finite and positive, and law_id and
    mode set together or neither. A set law_id is one of `hosted` ({qualified ID: cycle law}; none
    for an operator, which hosts no law), a law with a general form, and its mode one of that
    form's modes (the mode column of its registry/laws.cycle_changes): a version-1 law has neither.
    Every kind declares FreeEnergyEntry since the kinds owner's follow-up 2 (4e6ca60e), so a bare
    (stoichiometry, dG°/RT, c0) tuple is refused like any other non-entry."""
    from cells.registry import laws as law_registry  # registry/laws imports this module.

    if not isinstance(entries, tuple):
        raise ValueError(f"{where} returns a tuple of FreeEnergyEntry")
    out = []
    for index, entry in enumerate(entries):
        at = f"{where}, entry {index}"
        if not isinstance(entry, FreeEnergyEntry):
            raise ValueError(f"{where} returns a tuple of FreeEnergyEntry")
        stoichiometry = entry.stoichiometry
        if not (
            isinstance(stoichiometry, tuple)
            and stoichiometry
            and all(
                isinstance(pair, tuple)
                and len(pair) == 2
                and _named(pair[0])
                and _finite(pair[1])
                and pair[1] != 0
                for pair in stoichiometry
            )
            and len({pair[0] for pair in stoichiometry}) == len(stoichiometry)
        ):
            raise ValueError(
                f"{at}: its stoichiometry is ((species, nu), ...), distinct species, nu nonzero"
            )
        if (entry.dG_RT is None) == (entry.dG_kJ_mol is None):
            raise ValueError(f"{at}: it gives its dG° in exactly one form, dG_RT or dG_kJ_mol")
        if not _finite(entry.dG_RT_offset):
            raise ValueError(f"{at}: its dG_RT_offset is finite, in RT units")
        if entry.dG_kJ_mol is None:
            if not _finite(entry.dG_RT):
                raise ValueError(f"{at}: its dG°/RT is finite")
            if entry.dG_basis is not None:
                raise ValueError(
                    f"{at}: its dG_basis qualifies a dG_kJ_mol, which it does not give"
                )
            if entry.dG_RT_offset != 0:
                raise ValueError(
                    f"{at}: its dG_RT_offset belongs beside a dG_kJ_mol, which it does not give"
                )
        else:
            if not _finite(entry.dG_kJ_mol):
                raise ValueError(f"{at}: its dG° in kJ/mol is finite")
            if entry.dG_basis not in DG_BASES:
                raise ValueError(
                    f"{at}: its dG_kJ_mol gives its basis, one of {', '.join(DG_BASES)}, not "
                    f"{entry.dG_basis!r}"
                )
        if not (_finite(entry.c0) and entry.c0 > 0):
            raise ValueError(f"{at}: its c0 is finite and positive")
        if (entry.law_id is None) != (entry.mode is None):
            raise ValueError(f"{at}: it names its law and its mode together, or neither")
        if entry.law_id is not None:
            law = hosted.get(qualified(entry.law_id)) if _named(entry.law_id) else None
            if law is None:
                raise ValueError(f"{at}: {entry.law_id!r} is not a cycle law it hosts")
            if law.cycle is None:
                raise ValueError(f"{at}: {entry.law_id} is a version-1 law, with no form or mode")
            modes = {row["mode"] for row in law_registry.cycle_changes(law)}
            if entry.mode not in modes:
                raise ValueError(f"{at}: {entry.law_id}'s form has no mode {entry.mode!r}")
        out.append(entry)
    return tuple(out)


def kind_standard_free_energies(kind, declaration):
    """A kind's reaction-level standard free energies (Kind.standard_free_energies), checked by
    free_energy_entries, any law an entry names being one of the cycle laws the kind hosts in the
    active law registry: a tuple of FreeEnergyEntry; () for a kind that declares none."""
    if kind.standard_free_energies is None:
        return ()
    from cells.registry import laws as law_registry  # registry/laws imports this module.

    hosted = {
        qualified(law.law_id): law
        for law in law_registry.active().laws(law_registry.CYCLE_LAW, kind.kind_id)
    }
    where = f"Kind {kind.kind_id}'s standard_free_energies"
    return free_energy_entries(kind.standard_free_energies(declaration), hosted, where)


def _form_role_end(row):
    """(role, end) of a general form's change row, from its "role@end" (end None without one)."""
    role, at, end = row["role"].rpartition("@")
    return (role, end) if at else (row["role"], None)


def law_roles(law):
    """A cycle law's roles: each change row's role (registry/laws.cycle_changes), a general form's
    read without the "@end" it adds."""
    from cells.registry import laws as law_registry  # registry/laws imports this module.

    rows = law_registry.cycle_changes(law)
    if law.cycle is None:
        return {row["role"] for row in rows}
    return {_form_role_end(row)[0] for row in rows}


def law_ends(law):
    """The ends a cycle law's change rows name: a general form's "@end" names, or MOVES_ENDS for a
    moves-only law, whose moves are inward-positive at the inside and land with the opposite sign
    at the outside, so a closure at either node places its rows."""
    from cells.registry import laws as law_registry

    if law.cycle is None:
        return set(MOVES_ENDS)
    return {_form_role_end(row)[1] for row in law_registry.cycle_changes(law)}


def law_count_names(law):
    """The population parameters a cycle law's change rows name as counts, each without the
    leading "-" that negates it."""
    from cells.registry import laws as law_registry

    counts = [row["per_cycle"] for row in law_registry.cycle_changes(law)]
    return {c[1:] if c.startswith("-") else c for c in counts if isinstance(c, str)}


def kind_role_species(kind, declaration):
    """A kind's entity bindings for one declaration (Kind.role_species), checked: a tuple of
    EntityBinding, one per entity in its own order, each naming a cycle law the kind hosts in the
    active law registry, binding exactly that law's roles (law_roles) to species IDs, placing every
    end its rows name (law_ends) at a node ID, and giving a finite value for every count its rows
    name as a parameter (law_count_names); every name and ID a non-empty string. Each refusal names
    the entity. None for a kind that declares none: §5.2's admission, not this reader, refuses
    such a kind beside a general closure."""
    if kind.role_species is None:
        return None
    from cells.registry import laws as law_registry  # registry/laws imports this module.

    registry = law_registry.active()
    hosted = {
        qualified(law.law_id): law for law in registry.laws(law_registry.CYCLE_LAW, kind.kind_id)
    }
    entities = kind.role_species(declaration)
    if not (
        isinstance(entities, tuple)
        and all(isinstance(entity, EntityBinding) for entity in entities)
    ):
        raise ValueError(f"Kind {kind.kind_id}'s role_species returns a tuple of EntityBinding")
    for index, entity in enumerate(entities):
        where = f"Kind {kind.kind_id}'s role_species, entity {index} ({entity.law_id!r})"
        if not (_named(entity.law_id) and qualified(entity.law_id) in hosted):
            raise ValueError(f"{where}: its law is not a cycle law the kind hosts")
        law = hosted[qualified(entity.law_id)]
        for name, mapping, valid in (
            ("roles", entity.roles, _named),
            ("ends", entity.ends, _named),
            ("parameters", entity.parameters, _finite),
        ):
            if not (
                isinstance(mapping, Mapping)
                and all(_named(k) and valid(v) for k, v in mapping.items())
            ):
                kind_of = "a finite value" if valid is _finite else "a name"
                raise ValueError(f"{where}: its {name} map names to {kind_of}")
        roles = law_roles(law)
        missing, extra = sorted(roles - set(entity.roles)), sorted(set(entity.roles) - roles)
        if missing or extra:
            raise ValueError(
                f"{where}: the law's roles are {sorted(roles)}; it lacks {missing} and binds "
                f"{extra}, which are not the law's"
            )
        ends = sorted(law_ends(law) - set(entity.ends))
        if ends:
            raise ValueError(f"{where}: it places no node at the ends {ends} its law's rows name")
        counts = sorted(law_count_names(law) - set(entity.parameters))
        if counts:
            raise ValueError(f"{where}: it gives no value for the counts {counts} its law names")
    return entities


def _suffix_role(field):
    if field.endswith(HEAT_SUFFIX):
        return EnergyRole("heat", True)
    if field.endswith(WORK_SUFFIX):
        return EnergyRole("work", False)
    return None


def energy_role(kind, field):
    """A kind state field's energy role: its declaration (Kind.energy_roles), else today's suffix
    rule (heat, monotone, for a field ending in _dissipated_energy_pJ; work, not monotone, for one
    ending in _work_pJ), else None: the field books no energy."""
    declared = kind.energy_roles.get(field)
    return declared if declared is not None else _suffix_role(field)


def partition_fields(kind):
    """The fields a split, a retirement or a close acts on: the kind's state, layout and control
    fields, in that order (for a bound kind, its structure entry's)."""
    return (*kind.state_fields, *kind.layout_fields, *kind.control_fields)


def missing_partition_roles(kind):
    """The kind's partition fields that declare no role, in field order. Empty: every field has
    one, so §4.2's fail-closed refusal beside closers may lift for it. Bind a kind that declares
    its fields per entry (bound) first."""
    return tuple(field for field in partition_fields(kind) if field not in kind.partition_roles)


def kind_ledgers(kind, declaration):
    """A kind's own ledgers (CORE_SEAMS §7.3; INNER_MODEL_V4_DESIGN §7.4 (p)): its
    ledgers(declaration) hook's ((ledger, diagnostic), ...), checked: pairs of distinct non-empty
    names, no ledger named for one of ledger_terms' roles. () for a kind that declares none."""
    if kind.ledgers is None:
        return ()
    pairs = kind.ledgers(declaration)
    named = isinstance(pairs, tuple) and all(
        isinstance(pair, tuple) and len(pair) == 2 and all(isinstance(n, str) and n for n in pair)
        for pair in pairs
    )
    if not named:
        raise ValueError(
            f"Kind {kind.kind_id}'s ledgers(declaration) returns ((ledger, diagnostic), ...)"
        )
    names = [name for pair in pairs for name in pair]
    if len(set(names)) != len(names):
        raise ValueError(f"Kind {kind.kind_id}'s ledgers and diagnostics are distinct names")
    reserved = sorted({ledger for ledger, _ in pairs} & set(LEDGER_TERM_ROLES))
    if reserved:
        raise ValueError(
            f"Kind {kind.kind_id}'s ledgers {reserved} take names of ledger_terms' roles, which "
            "fold into today's ledgers (rule (a))"
        )
    return pairs


def _finite_fill(value):
    if isinstance(value, bool):
        return True
    return isinstance(value, (int, float)) and math.isfinite(value)


def declaration_errors(kind):
    """Why a kind's seam declarations (energy_roles, heat_bookings, partition_roles, ledgers and
    ledger_bounds, and FR-42's label hooks) break the contract (empty: they keep it). The fields
    they name are checked against the kind's own where its fields are static; a kind that declares
    its fields per entry (declared_fields) may name the fields of every entry."""
    out, static = [], kind.declared_fields is None
    roles = kind.energy_roles
    if not isinstance(roles, Mapping) or not all(isinstance(k, str) and k for k in roles):
        out.append("its energy_roles map state field names to EnergyRole")
    else:
        for field, role in roles.items():
            if not (
                isinstance(role, EnergyRole)
                and role.role in ENERGY_ROLES
                and isinstance(role.monotone, bool)
            ):
                out.append(
                    f"energy role of {field}: an EnergyRole of {', '.join(ENERGY_ROLES)} with a "
                    "bool monotone"
                )
            elif _suffix_role(field) is not None and role.role != _suffix_role(field).role:
                out.append(
                    f"energy role of {field}: its suffix makes it {_suffix_role(field).role}, "
                    "which today's energy-flow sums read by name"
                )
        if static:
            stray = sorted(set(roles) - set(kind.state_fields))
            if stray:
                out.append(f"energy_roles name fields it does not hold: {stray}")
    bookings = kind.heat_bookings
    if not (
        isinstance(bookings, tuple)
        and all(isinstance(b, str) and _BOOKING_ID.fullmatch(b) for b in bookings)
        and len(set(bookings)) == len(bookings)
    ):
        out.append(
            "its heat_bookings are distinct versioned booking IDs (name@major), the tableau "
            "never among them"
        )
    parts = kind.partition_roles
    if not isinstance(parts, Mapping) or not all(isinstance(k, str) and k for k in parts):
        out.append("its partition_roles map field names to PartitionRole")
    else:
        for field, part in parts.items():
            structural = isinstance(part, PartitionRole) and part.role == "structural"
            if not (
                isinstance(part, PartitionRole)
                and part.role in PARTITION_ROLES
                and (_finite_fill(part.fill) if structural else part.fill is None)
            ):
                out.append(
                    f"partition role of {field}: a PartitionRole of {', '.join(PARTITION_ROLES)}, "
                    "a structural one with a finite fill and no other with one"
                )
        if static:
            stray = sorted(set(parts) - set(partition_fields(kind)))
            if stray:
                out.append(f"partition_roles name fields it does not hold: {stray}")
    hooks = (kind.ledgers, kind.ledger_bounds)
    if (hooks[0] is None) != (hooks[1] is None) or any(
        h is not None and not callable(h) for h in hooks
    ):
        out.append("it declares ledgers and ledger_bounds together, each a callable")
    if kind.standard_free_energies is not None and not callable(kind.standard_free_energies):
        out.append("its standard_free_energies is a callable, or None")
    if kind.role_species is not None and not callable(kind.role_species):
        out.append("its role_species is a callable, or None")
    labels = (kind.label_refusals, kind.label_transfers)  # FR-42's hook (D303 item 6).
    if any(h is not None and not callable(h) for h in labels):
        out.append("its label_refusals and label_transfers are callables, or None")
    elif labels[1] is not None and labels[0] is None:
        out.append(
            "it declares label_transfers only beside label_refusals, which say what its transfers "
            "cannot carry"
        )
    one_way = (kind.one_way_fluxes, kind.one_way_nets)  # FR-50's hooks.
    if any(h is not None and not callable(h) for h in one_way) or (one_way[0] is None) != (
        one_way[1] is None
    ):
        out.append("it declares one_way_fluxes and one_way_nets together, each a callable")
    return out + _axis_errors(kind, static) + _dispatch_mask_errors(kind, static)


def _dispatch_mask_errors(kind, static):
    """Why a kind's dispatch_masks break the contract: distinct names, each, where the kind's
    fields are static, one of its state or layout fields with at least one declared axis to be
    empty along."""
    masks = kind.dispatch_masks
    if not (isinstance(masks, tuple) and all(map(_named, masks)) and len(set(masks)) == len(masks)):
        return ["its dispatch_masks are a tuple of distinct field names"]
    if not static:
        return []
    axes = {
        **(kind.field_axes if isinstance(kind.field_axes, Mapping) else {}),
        **dict(kind.state_axes),
    }
    fields = {*kind.layout_fields, *(name for name, _ in kind.state_axes)}
    return [
        f"dispatch mask {mask}: one of its state or layout fields with a declared axis"
        for mask in masks
        if mask not in fields or not axes.get(mask)
    ]


def _axis_errors(kind, static):
    """Why a kind's field_axes, axis_hosts and internal_axes break the contract (declaration_errors'
    part)."""
    out, axes = [], kind.field_axes
    if not isinstance(axes, Mapping) or not all(
        _named(field)
        and isinstance(names, tuple)  # () for a field on no axis: a scalar.
        and all(map(_named, names))
        and len(set(names)) == len(names)
        for field, names in axes.items()
    ):
        out.append("its field_axes map layout and control fields to tuples of distinct axis names")
        axes = {}
    elif static:
        stray = sorted(set(axes) - {*kind.layout_fields, *kind.control_fields})
        if stray:
            out.append(f"field_axes name fields that are not its layout or control fields: {stray}")
    hosts = kind.axis_hosts
    if not isinstance(hosts, Mapping) or not all(
        _named(axis) and isinstance(host, AxisHost) for axis, host in hosts.items()
    ):
        return [*out, "its axis_hosts map its own axes to AxisHost(kind, index)"]
    used = {a for _, names in kind.state_axes for a in names} | {
        a for names in axes.values() for a in names
    }
    for axis, host in hosts.items():
        if host.kind not in AXIS_HOST_KINDS:
            out.append(f"axis {axis}: its host kind is one of {', '.join(AXIS_HOST_KINDS)}")
        if axis in AXIS_HOST_KINDS.values():
            out.append(f"axis {axis}: @3's own slot axis, not one of the kind's")
        if static and axis not in used:
            out.append(f"axis {axis}: no field of the kind's is on it")
        if static and host.index not in kind.layout_fields:
            out.append(
                f"axis {axis}: its host index {host.index!r} is not one of its layout fields"
            )
        elif host.index in axes and axes[host.index] != (axis,):
            out.append(f"axis {axis}: its host index {host.index!r} is on {axes[host.index]}")
    return out + _internal_axis_errors(kind, static, used) + _presence_errors(kind, static, axes)


def entity_axes(kind):
    """A kind's entity axes: the axes of its own fields that carry entities, neither @3's shared
    axes nor its laws' internal ones, in first-use order (state fields, then its layout and control
    fields' field_axes). field_axes may cover every entry's fields, and bound keeps it whole, so
    only the kind's own fields count. For a kind that declares its fields per entry, bind it first
    (bound)."""
    axes = [a for _, names in kind.state_axes for a in names]
    if isinstance(kind.field_axes, Mapping):
        own = {*kind.layout_fields, *kind.control_fields}
        axes += [a for field, names in kind.field_axes.items() if field in own for a in names]
    internal = set(kind.internal_axes) if isinstance(kind.internal_axes, tuple) else set()
    return tuple(a for a in dict.fromkeys(axes) if a not in SHARED_AXES and a not in internal)


def presence_fields(kind):
    """{entity axis: (presence field, ...)} of a kind bound to its entry (Q2's presence gate): {}
    where it declares no presence, which leaves it refused beside a closer. A kind that declares
    presence declares it for each entity axis it has, each field one of its layout fields; a key of
    an axis this entry does not have belongs to another entry and is left out. Raises otherwise.
    The core reads presence only through this, on the bound kind: a kind's own fields may differ
    per entry, and declaration_errors checks these two only where they are static."""
    if not kind.presence:
        return {}
    axes = entity_axes(kind)
    missing = [a for a in axes if a not in kind.presence]
    named = [f for a in axes if a in kind.presence for f in kind.presence[a]]
    absent = [f for f in named if f not in kind.layout_fields]
    if missing or absent:
        raise ValueError(
            f"Kind {kind.kind_id}'s presence lacks its entity axes {missing} or names fields "
            f"{absent} that are not its layout fields"
        )
    return {a: tuple(kind.presence[a]) for a in axes}


def _presence_errors(kind, static, axes):
    """Why a kind's presence breaks the contract (declaration_errors' part; the Kind docstring):
    for each of its entity axes a non-empty tuple of distinct bool layout fields, each on exactly
    that axis, structural with fill False; none on a shared or internal axis, and no field named
    twice; where the fields are static, every entity axis covered and each field one of its layout
    fields. A field's dtype is the layout's: fill False is what the declaration can say."""
    presence = kind.presence
    if not presence:
        return []
    if not isinstance(presence, Mapping) or not all(
        _named(axis) and isinstance(names, tuple) and all(map(_named, names))
        for axis, names in presence.items()
    ):
        return ["its presence maps its entity axes to tuples of layout fields"]
    out = []
    named = [field for names in presence.values() for field in names]
    repeated = sorted({field for field in named if named.count(field) > 1})
    if repeated:
        out.append(f"its presence names fields more than once: {repeated}")
    internal = set(kind.internal_axes) if isinstance(kind.internal_axes, tuple) else set()
    roles = kind.partition_roles if isinstance(kind.partition_roles, Mapping) else {}
    for axis, names in presence.items():
        if not names:
            out.append(f"presence of axis {axis}: an empty tuple, so no field gates its entities")
        if axis in SHARED_AXES or axis in internal:
            out.append(f"presence of axis {axis}: a shared or internal axis carries no entities")
        for field in names:
            if axes.get(field) != (axis,):
                out.append(f"presence field {field}: on {axes.get(field)}, not exactly {(axis,)}")
            role = roles.get(field)
            if not (isinstance(role, PartitionRole) and role.role == "structural"):
                out.append(f"presence field {field}: {role}, not structural with fill False")
            elif role.fill is not False:
                out.append(f"presence field {field}: its fill is {role.fill!r}, not False")
            if static and field not in kind.layout_fields:
                out.append(f"presence field {field}: not one of its layout fields")
    if static:
        own = entity_axes(kind)
        uncovered = [a for a in own if a not in presence]
        if uncovered:
            out.append(f"its presence lacks its entity axes {uncovered}")
        stray = sorted(set(presence) - set(own) - set(SHARED_AXES) - internal)
        if stray:
            out.append(f"its presence names axes no field of its own is on: {stray}")
    return out


def _internal_axis_errors(kind, static, used):
    """Why a kind's internal_axes break the contract: distinct names, none of @3's slot axes, none
    hosted (an internal axis carries no entities), each one some field of the kind's is on."""
    internal = kind.internal_axes
    if not (
        isinstance(internal, tuple)
        and all(map(_named, internal))
        and len(set(internal)) == len(internal)
    ):
        return ["its internal_axes are a tuple of distinct axis names"]
    out = []
    for axis in internal:
        if axis in AXIS_HOST_KINDS.values():
            out.append(f"internal axis {axis}: @3's own slot axis, an entity axis")
        if isinstance(kind.axis_hosts, Mapping) and axis in kind.axis_hosts:
            out.append(f"internal axis {axis}: it is hosted, so its entities are not internal")
        if static and axis not in used:
            out.append(f"internal axis {axis}: no field of the kind's is on it")
    return out


def axis_sizes(declared, arrays):
    """{axis: length} of the axes the host's own fields bind ({field: (axis, ...)} and {field:
    array}): the host's lengths, read where it binds its kinds' arrays (refuse_misshapen). Raises
    where one of its fields has a shape other than its axes', or two disagree on an axis."""
    out = {}
    for name, axes in declared.items():
        if name not in arrays:
            continue
        shape = tuple(np.shape(arrays[name]))
        if len(shape) != len(axes):
            raise ValueError(f"The host's {name} has shape {shape}, not its axes {tuple(axes)}")
        for axis, size in zip(axes, shape, strict=True):
            if out.setdefault(axis, size) != size:
                raise ValueError(f"The host's axis {axis} has lengths {out[axis]} and {size}")
    return out


def misshapen_errors(kind, arrays, sizes):
    """Why a kind's state and layout arrays ({field: array}) break the axes it declares for them
    (state_axes; field_axes for a layout field that declares them): each with one dimension per
    axis, each host axis (in `sizes`, axis_sizes') at the host's length, and each of its own and
    its laws' internal axes at one length across its fields. A dispatch mask may instead be empty
    along its axes (length 0, by static dispatch)."""
    declared = {
        **(kind.field_axes if isinstance(kind.field_axes, Mapping) else {}),
        **dict(kind.state_axes),
    }
    masks = set(kind.dispatch_masks) if isinstance(kind.dispatch_masks, tuple) else set()
    out, own = [], {}
    for name, value in arrays.items():
        if name not in declared:
            continue
        shape, axes = tuple(np.shape(value)), tuple(declared[name])
        if len(shape) != len(axes):
            out.append(f"{name} binds shape {shape}, not its declared axes {axes}")
            continue
        if name in masks and 0 in shape:
            continue  # Empty by static dispatch.
        for axis, size in zip(axes, shape, strict=True):
            if axis in sizes:
                if size != sizes[axis]:
                    out.append(
                        f"{name}'s axis {axis} has length {size}, not the host's {sizes[axis]}"
                    )
            elif own.setdefault(axis, (size, name))[0] != size:
                out.append(
                    f"{name}'s axis {axis} has length {size}, {own[axis][1]}'s {own[axis][0]}"
                )
    return out


def refuse_misshapen(kind, hook, state, layout, sizes):
    """A kind's state and layout from its `hook`, checked where the host binds them (at @3's
    initial values) against the axes the kind declares (misshapen_errors), so a field whose array
    does not match its axes is refused before any step: the lifecycle, the partition and the run
    view read arrays by those axes. Shapes are static, so one check at binding holds for every
    step (D228 item 6; the review's finding)."""
    problems = misshapen_errors(kind, {**state, **layout}, sizes)
    if problems:
        raise ValueError(
            f"Kind {kind.kind_id}'s {hook} break the axes it declares: " + "; ".join(problems)
        )


def refuse_foreign_writes(kind, hook, values, fields, role):
    """A kind's hook output, {field: value}, may name only that kind's own declared fields of one
    role: `fields`, from the kind bound to its structure entry (`bound`), so a field that another
    kind, the base model or another declaration of the same kind owns is refused.

    - Where the outputs merge: the initial values (state and layout), the rates' derivatives
      (state) and the control outputs (control). That is @3's booking guard
      (surface_pump_v3._kind_bookings), extended.
    - It reads the keys alone, at construction and while tracing, so it adds nothing to a
      compiled step.
    - Without it, a foreign key overwrote a base or another kind's initial value, or was dropped
      silently, or was taken as another kind's derivative or control."""
    foreign = set(values) - set(fields)
    if foreign:
        raise ValueError(
            f"Kind {kind.kind_id} writes {sorted(foreign)} from its {hook}; a kind writes only its "
            f"own declared {role} fields ({', '.join(fields) or 'none'})"
        )


@cache
def bound(kind, entry):
    """The kind with the fields of one declaration's structure entry (§7.4 (n) 5): its
    declared_fields(entry) in place of its static fields, or the kind itself when it declares
    none. Cached, so each (kind, entry) gives one object; the bound kind is not bound again."""
    if kind.declared_fields is None:
        return kind
    fields = kind.declared_fields(entry)
    if type(fields) is not KindFields:
        raise ValueError(f"Kind {kind.kind_id}'s declared_fields must return a KindFields")
    without = fields.without
    if not isinstance(without, tuple) or any(name not in HOOKS for name in without):
        raise ValueError(
            f"Kind {kind.kind_id}'s declared_fields' `without` names its hooks only, not "
            f"{sorted(set(without) - set(HOOKS)) if isinstance(without, tuple) else without!r}"
        )
    records = tuple(fields.one_way_records)
    names = {name for name, _ in fields.state_axes}
    for record in records:
        if type(record) is not OneWayRecord or not set(record) <= names:
            raise ValueError(
                f"Kind {kind.kind_id}'s one_way_records are OneWayRecords naming its own state "
                f"fields, not {record!r}"
            )
    absent = dict.fromkeys(without) | ({} if records else dict.fromkeys(ONE_WAY_HOOKS))
    return replace(
        kind,
        state_axes=tuple(fields.state_axes),
        layout_fields=tuple(fields.layout_fields),
        control_fields=tuple(fields.control_fields),
        readout_columns=tuple(fields.readout_columns),
        declared_fields=None,
        one_way_records=records,
        **absent,
    )


def declared_kinds(declared):
    """((kind ID, the active registry's kind bound to its declaration's structure entry,
    declaration), ...) for a model's declared kinds (((kind ID, declaration), ...)), in order: the
    kinds as the core reads them, on the host."""
    registry, out = active(), []
    for kind_id, declaration in declared:
        kind = registry.lookup(kind_id)
        entry = kind.structure_entry(declaration) if kind.structure_entry is not None else ()
        out.append((qualified(kind_id), bound(kind, entry), declaration))
    return tuple(out)


def label_refusal_errors(declared, species):
    """FR-42's kinds hook at the definition (D303 item 6): why the declared kinds (a model's
    ((kind ID, declaration), ...)) cannot carry the labelled species (their IDs, in the label rows'
    order), each reason naming its kind; [] where they can, and always where nothing is labelled.
    A kind's own label_refusals give its reasons. A kind with a rates hook and no label_refusals is
    refused whenever any species is labelled (fail-closed: nothing says which of its moves it
    could report)."""
    species = tuple(species)
    if not species:
        return []
    out = []
    for kind_id, kind, declaration in declared_kinds(declared):
        if kind.label_refusals is not None:
            reasons = kind.label_refusals(declaration, species)
            if not isinstance(reasons, list) or not all(isinstance(r, str) and r for r in reasons):
                raise ValueError(f"Kind {kind_id}'s label_refusals returns a list of its reasons")
            out += [f"{kind_id}: {reason}" for reason in reasons]
        elif kind.rates is not None:
            out.append(
                f"{kind_id} has a rates hook and no label_refusals, so it is refused while any "
                "row is labelled (fail-closed)"
            )
    return out


class KindRegistry:
    """Registered kinds by namespaced ID. A registered kind that a definition does not declare
    changes nothing: no field, no hook call, no change to types, compile key or snapshot."""

    def __init__(self):
        self._kinds = {}

    def register(self, kind):
        key = qualified(kind.kind_id)
        known = self._kinds.get(key)
        if known is not None and known is not kind:
            raise ValueError(f"Kind {key} is already registered")
        problems = declaration_errors(kind)  # The seams' declarations (CORE_SEAMS §4.2-§7.3).
        if problems:
            raise ValueError(f"Kind {key}: " + "; ".join(problems))
        clash = [k for k in self._kinds.values() if k.model_key == kind.model_key and k is not kind]
        if clash:
            raise ValueError(f"Kind {key}'s model key {kind.model_key!r} is already registered")
        keys = kind.experiment_keys  # §7.4 (l): its schedule's keys, each owned by one kind.
        if not isinstance(keys, tuple) or any(not isinstance(k, str) or not k for k in keys):
            raise ValueError(f"Kind {key}'s experiment_keys are a tuple of non-empty strings")
        if len(set(keys)) != len(keys):
            raise ValueError(f"Kind {key} declares an experiment key twice")
        if keys and (kind.parse_schedule is None or kind.schedule_to_dict is None):
            raise ValueError(
                f"Kind {key} declares experiment keys, so it supplies parse_schedule and "
                "schedule_to_dict"
            )
        taken = [
            (k, other.kind_id)
            for other in self._kinds.values()
            if other is not kind
            for k in other.experiment_keys
            if k in keys
        ]
        if taken:
            raise ValueError(f"Kind {key}'s experiment key {taken[0][0]!r} is {taken[0][1]}'s")
        self._kinds[key] = kind
        return kind

    def lookup(self, kind_id):
        key = qualified(kind_id)
        if key not in self._kinds:
            raise KeyError(f"No registered kind {key}")
        return self._kinds[key]

    def __contains__(self, kind_id):
        return qualified(kind_id) in self._kinds

    def model_keys(self):
        """{model key: kind} of every registered kind."""
        return {kind.model_key: kind for kind in self._kinds.values()}

    def experiment_keys(self):
        """{experiment key: kind} of every registered kind's schedule keys (§7.4 (l))."""
        return {key: kind for kind in self._kinds.values() for key in kind.experiment_keys}

    @staticmethod
    def canonical(kind_ids):
        """kind_ids, namespaced, distinct and in canonical (sorted) order."""
        return tuple(sorted({qualified(k) for k in kind_ids}))


BUILTIN = KindRegistry()
_ACTIVE = ContextVar("cells_kind_registry", default=None)
BUILTIN_PACKAGE = "cells.kinds"
_builtins_loaded = False


def _load_builtins():
    """Import the built-in kinds' package once (by name: the core imports no kind module), so
    each built-in registers on BUILTIN through the call an external package uses."""
    global _builtins_loaded
    if not _builtins_loaded:
        importlib.import_module(BUILTIN_PACKAGE)
        _builtins_loaded = True


def active():
    """The registry of the model build in progress: BUILTIN, with the built-in kinds loaded,
    unless scope() says otherwise."""
    registry = _ACTIVE.get()
    if registry is not None:
        return registry
    _load_builtins()
    return BUILTIN


@contextmanager
def scope(registry):
    """Build (parse, bind, run) with `registry` as the kind lookup, restored on exit."""
    token = _ACTIVE.set(registry)
    try:
        yield registry
    finally:
        _ACTIVE.reset(token)
