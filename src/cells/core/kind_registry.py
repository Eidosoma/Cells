"""The kind registry of resolved_pump_tissue@3 (docs/INNER_MODEL_V4_DESIGN.md §7.4 (j), (k)).

A kind is one module's contribution to the inner model: its fields (state, layout, control and
observation columns) and optional hooks that the core calls at fixed seams. The core reaches
kinds only through the registry active for the model build: BUILTIN, unless a caller builds
inside `scope(registry)`. It imports no kind module. Built-in kinds (models/inner_kinds/)
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
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from functools import cache
from types import MappingProxyType
from typing import NamedTuple

import numpy as np

# The kind interface's parsing surface (§7.4 (k); D180's external modules): a kind's parse and
# check_definition refuse with ConfigError and may use these public helpers, never the
# underscored names of cells.core.specs.
from cells.core.specs import ConfigError, bounded_integer, finite_number, require_fields

__all__ = (
    "BUILTIN",
    "ConfigError",
    "Kind",
    "KindFields",
    "KindRates",
    "KindView",
    "KindRegistry",
    "Schedule",
    "active",
    "bound",
    "bounded_integer",
    "declared_schedule",
    "finite_number",
    "parse_series",
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
      default); `schedule_to_dict(schedule, declaration)` -> the {key: value} to write back (the
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
      bound (the passive law's dt L <= 1).
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

    @property
    def state_fields(self):
        """The kind's own state field names, in declared order."""
        return tuple(field for field, _ in self.state_axes)


class KindFields(NamedTuple):
    """A kind's fields for one structure entry (§7.4 (n) 5): its declared_fields(entry)."""

    state_axes: tuple  # ((field, (axis, ...)), ...)
    layout_fields: tuple
    control_fields: tuple
    readout_columns: tuple


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
    return replace(
        kind,
        state_axes=tuple(fields.state_axes),
        layout_fields=tuple(fields.layout_fields),
        control_fields=tuple(fields.control_fields),
        readout_columns=tuple(fields.readout_columns),
        declared_fields=None,
    )


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
BUILTIN_PACKAGE = "cells.models.inner_kinds"
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
