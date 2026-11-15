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
"""

import importlib
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

# The kind interface's parsing surface (§7.4 (k); D180's external modules): a kind's parse and
# check_definition refuse with ConfigError and may use these public helpers, never the
# underscored names of cells.core.specs.
from cells.core.specs import ConfigError, bounded_integer, finite_number, require_fields

__all__ = (
    "BUILTIN",
    "ConfigError",
    "Kind",
    "KindRegistry",
    "active",
    "bounded_integer",
    "finite_number",
    "qualified",
    "require_fields",
    "scope",
)

NAMESPACE = "cells"


def qualified(identifier):
    """The namespaced form of a kind or law ID: a bare ID belongs to the cells namespace."""
    if not isinstance(identifier, str) or not identifier:
        raise ValueError(f"A kind or law ID must be a non-empty string, not {identifier!r}")
    head = identifier.split("@", 1)[0]
    return identifier if "." in head else f"{NAMESPACE}.{identifier}"


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
    - stage: `stage_read(state, p, *, xp)` -> (the state whose amount fields hold the amounts
      every rate of the stage reads, valid), composed in hook order; a failed read refuses the
      step, and domain_valid evaluates the reads at every checked state (the step's end
      included). The read changes the concentrations the rates see, never charge: the field
      solve keeps the stored rows' charges. It must declare `stage_rows(declaration)` ->
      ((species, node ID), ...), every row it reads or rewrites, and two kinds' stage reads on a
      shared row are refused at binding (they do not commute). `rates(state, potentials,
      control, p, *, xp)` -> surface_pump_v3.KindRates: inward-positive node changes (cell
      [species, cell], outside [species, outside node]) into the shared inventory, the kind's own
      state derivatives {field: array}, and heat and work rates (pJ/s); `potentials` are the
      stage's node potentials, cells then outside nodes (V). `stage_check(read, cell, outside,
      p, *, xp)` -> one bool, after every rate of the stage: `read` is the read state, `cell`
      [species, cell] and `outside` [species, outside node] the stage's total node rates (fmol/s;
      explicit stages without the implicit face drift); a false check refuses the step (FR-4's
      envelope: the closure's lag at the stage's transport).
    - step size (B7 for kinds): `stage_term(read, potentials, control, p, *, xp)` -> [cell]
      conductance (S) of the kind's charged routes at the stage's read and node potentials (a
      pump's electrogenic slope, reversed past its head included; potentials is None when
      membrane_rate is called without them), added to
      membrane_rate's per-stage refusal, dt x rate <= EXPLICIT_STEP_BOUND; `bound_rate(spec,
      declaration)` -> 1/s, a definition-time bound term the host step checks hold to the same
      bound (the passive law's dt L <= 1).
    - one writer: `held_rows(declaration)` -> ((species, node ID), ...), rows the kind reads and
      never moves (held fuel); binding refuses any inner route or other kind that moves one.
    - per-stage diagnostics (gap 7): `stage_values(read, cell, outside, p, *, xp)` -> {own state
      field: value} at every explicit stage of an IMEX step, with the stage_check's arguments;
      `stage_extrema` = ((field, "max" | "min"), ...) names the reduction. The step's end state
      holds each field's running extremum: the start's value and every stage of the step (the
      closure's largest lag, the cytosol's smallest and largest pH). RK4 steps leave them as
      they are.
    - step end: `book(applied, start, end, p, dt, *, xp)` -> ({own state field: new value},
      valid), after the tableau's combination; `applied(name)` is the step's applied rate of a
      state field (the tableau's weights), `start` the step's start state and `end` its end
      state before any kind books, the same for every kind, and only the kind's own state fields
      may be written, so bookings commute. A false valid refuses the step (§7.5's negative exact
      share).
    - checks (traced on the device at binding, with stage_read, so the device's row checks
      include them as the host's do; they branch on no value in Python): `domain(state, p, *,
      xp)` -> one bool, and-ed into domain_valid; `control_domain(control, p, *, xp)` -> one
      bool, in place of the [0, 1] rule for its controls; `ledger_terms(state, p, *, xp)` ->
      {"cell": [species, cell], "outside": [species, outside node], "heat_pJ": ..., "work_pJ":
      ..., "stored_pJ": ...} (any subset): cumulative inward-positive node transfers, heat and
      work accumulators, and the free energy the kind stores beyond the stored rows' own terms
      (its change since the start), folded into balances, device_balances and the ledger
      magnitudes by role.
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

    @property
    def state_fields(self):
        """The kind's own state field names, in declared order."""
        return tuple(field for field, _ in self.state_axes)


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
