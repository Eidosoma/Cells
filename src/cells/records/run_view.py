"""The run view: one declared record that makes a run viewable (D154; docs/RUN_VIEW_DESIGN.md).

The view (``cells.run_view@1``, one ``view.json`` per run, beside its definition) states, for a
run of the composite pump-tissue family, every entity identity, unit, time base, layer and its
representation, owner down to the law, orientation, kind, species identity and event, and the
caller's geometry, so that a viewer reconstructs no meaning from driver conventions (D174). It is
built from the definition, the registered models' and operators' declarations, the run's saved
files and three caller inputs (run labels, geometry and a recording subset), all host side. It
holds metadata, identity, geometry and the definition's constants; every recorded array stays in
the run's own files, which the view names. Writing it changes no result, and nothing reads it
back into a run. Whatever it cannot state is refused here (ViewRefused), with nothing written, or
listed under ``unstated`` with the reason; a viewer never infers it.

Where it is written. The shared output paths take an opt-in ``view=Request(...)``:
io.write_run (and batch_io.write_batch_run, through it), window_io.write_windowed_run and
batch_window_io.write_windowed_batch, one view per world beside that world's files. prepare()
runs before any output exists, so a refusal writes nothing; the view is written after the
payload and before the manifest, whose checksums then cover it. A run already on disk gets its
view from write_view(directory). Without ``view=`` every path writes exactly what it wrote before.

Scope (version 1): cells.model.resolved_pump_composite@1 over cells.model.resolved_pump_tissue@3, and @3 alone. Other
model families are refused.

Declarations read
-----------------
* The inner model's own, read from its implementation object (or the composite's inner adapter):
  ``UNITS``, ``OBSERVATION_AXES``, ``RECORD_KINDS``, ``ORIENTATION``, ``RECORD_LAYERS``,
  ``VIEW_LAYERS``, ``RECORD_NOTES``, ``RECORD_DIAGNOSTICS`` and ``RECORD_REFERENCES``, each
  structure's with its kinds' folded in (models/surface_pump_v3.view_declarations), and for its
  kinds' axes ``VIEW_AXIS_SETS`` (an axis mapped to an existing set) and ``view_sets(spec)``
  (their own sets, placed as an operator's are). A field that no declaration gives a unit, axes
  and a layer (a kind's new field, say) is refused, never guessed; the writer keeps no table of
  the inner model's fields.
* Each operator, by the contract (operators/contract.py, "The run view"): ``VIEW_LAYERS``
  (None is refused), ``view_events`` (the default gives the births and retirements of
  ``living_intervals``; an override must keep them), ``view_sets(spec, declaration)`` for its own
  axes, ``OBSERVATION_AXES`` for its readout columns, ``UNITS`` for names without a unit suffix,
  ``RECORD_KINDS``, ``ORIENTATION`` and ``RECORD_LAYERS``. Without a declared kind, a field the
  contract books as heat or work (HEAT_FIELDS, WORK_FIELDS) is cumulative; any other is listed as
  unstated.
* Retirement: where an operator RETIRES slots, a retired slot's inner history moves into that
  operator's own record at its retirement (the composite's checks add it back), so the inner
  ledgers it writes (the field map's writers) restart at zero there on the saved arrays. Their
  records say so (``resets``, with ``mask``: the slots are those where that set's merged mask,
  the record view_<mask>, closes at the event) and claim no monotonicity; every other heat record
  whose declared energy role is monotone is ``monotone`` (on S5's division the fallen heat ledgers
  were exactly those). The role is the field's declaration (a kind's energy_roles, an operator's
  ENERGY_ROLES), else today's rule, a ``*_dissipated_energy_pJ`` name (seam D, §6.1).
* Owners: the composition's field map (state owners, observation owner chains: the last).
* Laws (requirement 4): each channel population's, junction's and pump's law from the structure
  record's law declarations (models/inner_laws.py), with its provenance; membranes and faces carry
  their passive route law, whose provenance is not declared.
* Pumps (requirement 6) are columns of the membrane set: each membrane entry gives its pump's law
  and rows per cycle by role (inward-positive), from the law's declaration.
* Species (requirement 7): identities from core/species_registry.identities, with each declared
  standard potential and background.
* View fields (requirement 5; the visualizer's request 5, the lead's choice (a)): a field of the
  inner layout that operators may provide is a named constant of the definition (its bound value)
  where nothing of the composition changes it, and a record where something does (door S below).

Door S: the merged view at the observe stage (route B, the lead's ruling of 16 November 2026)
------------------------------------------------------------------------------------------
A view field is changed where an operator provides it (the composition's field map: each provider,
or the chain of changes in merge order) or, with any closer, where close() changes it: closure
propagates to every activity mask and pads the padded view fields on closed slots. That last rule
is read from the adapter's tables (MASK_FIELDS, PADDED_FIELDS), a stopgap named as such: after
D172's landing the composite declares its changed set in one method and the writer reads that.

The shared paths save, beside the observation base, an array ``view_<field>`` per changed field:
the merged view at each observed row, re-formed at write time by the composite's own host view
function (``model.view(p, state, xp=np)``, the call pump_composite.observe_history makes for that
row) from the run's bound layout and the observed state, before the recording subset (whose
cadence and elements then apply). It is the view the host observer formed for the row's saved
readouts, bitwise, not the device step's own formation. Two refusals at write time: a field of the
table that no change declares but that differs from its bound value at an observed row, and an
operator that REPLACES a column named like a state field (the observed state would not be the
state). Not covered, and listed as unstated with the reason: a run already on disk (write_view:
its manifest's checksums cover its payload, so nothing is added) and a run that saved no observed
rows (recording "checkpoints", or no observation times).

Event rows: every event in a view is an operator's event map, which acts at the start of the step
that leaves the event's time (the operator contract): the row saved at that time holds the state
before the event, the next row the state after it (``time.event_rows``).

Records and time bases
----------------------
Records are the run's time-based arrays: the state history (``<field>`` on the base
``accepted``) and the observations (``observed_<field>`` on the base ``observation``). A record's
id is its array name; ``field`` is the engine's field name. Each time base lists the files that
hold it, one entry per file with the rows it holds (requirement 8): one file for io.write_run,
one per window chunk for the windowed paths, read from the run's own index. Every record on a
base lies in those files at those rows. The layout arrays of trajectory.npz are the definition's
bound values, not records.

Orientation (requirement 2): every set with ends states its ``roles``, each with what it is
(the inner sets': SET_ROLES; an operator's: its view_sets). A flow's ``sign`` gives ``from`` and
``to``, two roles of the record's set: a positive value moves from ``from`` to ``to``. A
difference (a voltage) gives ``plus`` and ``minus`` instead: the value is plus less minus, so
positive when ``plus`` is the higher.

Sets of operators' entities (view_sets) may give per-entity facts: the species each carries
(``carries``), a declared word each (``direction``, ``kinds``) and the entity each acts at
(``at``). So the view states, for instance, where a species is produced and by which routes it
leaves a cell; a label such as "secreted" stays the reader's, from those facts.
- **Kinds are words** (docs/CORE_SEAMS_DESIGN.md §9, item 1): a ``kinds`` value never holds a
  versioned ID ("@"), in any set; a law's ID goes only under ``laws``. The writer refuses a kind
  that holds one, and so does the reader's check.
- **What ``carries`` means** (item 2): each species a route carries moves with its own flux, not
  as a coupled set. Coupled stoichiometry is ``per_cycle``, as @3's pumps give it (the membrane
  set's ``pumps``: each moved row's count per cycle, by role, inward-positive); a cycle kind's sets
  give ``per_cycle`` per mode and population, with each mode's count per species and end.
- The channel set gives each population's ``factors`` (its factor-source IDs, in declared order;
  none for one that declares no factors) where any population declares factors: the routing
  door scales its availability at every stage (docs/CORE_SEAMS_DESIGN.md §4.3), so its
  ``channel_availability`` record is the held value (that record's note says so).

The run (``run``): the caller's labels (RUN_KEYS), the engine models, the definition's
fingerprint, the scale, how it ended (``end``: status, time and step, from the shared path's final
checkpoint or the saved run's summary) and, where a shared path writes the view as the run ends,
the running engine's ``source``: its revision and whether it was dirty, from its execution
snapshot's own record (AGENTS.md: a run's provenance is its Git revision, dirty diff and frozen
snapshot). From a checkout, or for a run already on disk, the source is unstated with the reason.

Loops (FR-11; docs/LOOPING_REPLAY_DESIGN.md §2, §3): a looping replay package is one real run
whose observed rows cover exactly one period of a periodic state. The caller's Loop (species,
cell, period, tolerance) is checked before any output: refused unless the run names its engine
source (a shared path running from an execution snapshot), the totals the viewer's loop reader
differences (LOOP_TOTALS) are recorded with their kind and sign, and it is one run, not a batch's
world. Its closure is measured as the view is written, on the saved files (loop_closure): for
each observed record of kind level, amount or rate, the change from the first row to the last
over the largest magnitude the record takes. The optional top-level ``loop`` block is written
only when the observed rows span the period and that closure is within the tolerance; otherwise
the view says why under ``unstated``, so a run that does not close is never labelled a loop. The
viewer reads the revision from ``run.source``, which the writer does not copy into ``run.revision``.
"""

import json
import math
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

import numpy as np

from cells.definitions.specs import ConfigError

FORMAT = "cells.run_view@1"
FILE = "view.json"
REPRESENTATIONS = ("simulated", "modelled", "prescribed")
KINDS = ("level", "amount", "cumulative", "rate")
SCALES = ("molecule", "cell", "tissue", "organ", "organism")
GEOMETRY_KINDS = ("points", "polygons", "links", "on", "spheres")
LENGTH_UNITS = ("m", "mm", "um", "nm")
RUN_KEYS = {
    "id": str,
    "experiment": str,
    "arm": str,
    "seed": int,
    "revision": str,
    "label": str,
}
TOP_KEYS = frozenset(
    {
        "format",
        "run",
        "time",
        "space",
        "layers",
        "sets",
        "records",
        "events",
        "constants",
        "unstated",
        "recording",
    }
)
# A looping replay package (FR-11; docs/LOOPING_REPLAY_DESIGN.md §2, §3): the optional block, the
# record kinds its closure measures (cumulative totals grow by design, so the reader differences
# them inside the loop only), and the totals the viewer's loop reader differences for its rates
# (the visualizer's "What a species' looping run must carry": each channel population's
# transfers, the pumps' cycles with the membrane set's rows per cycle, the membrane's own
# transfers), each recorded with its kind and sign.
LOOP_KEY = "loop"
LOOP_KEYS = frozenset(
    {"species", "cell_type", "cell", "period", "closes", "not_measured", "follows"}
)
LOOP_KINDS = ("level", "amount", "rate")
LOOP_TOTALS = ("channel_transferred", "pump_cycles", "membrane_transferred")
# The observed records a loop's closure leaves out, by reason, in this order (the lead's ruling of
# 16 November 2026); the block lists them by name.
NOT_MEASURED = (
    (
        "diagnostic",
        "diagnostics: residuals of the engine's own checks, held to their own absolute tolerances",
    ),
    (
        "cumulative",
        "cumulative totals: they grow by design, so the reader differences them inside the loop",
    ),
    ("unstated", "records whose kind the view leaves unstated"),
)
# A record its owner declares a diagnostic (RECORD_DIAGNOSTICS) says so.
DIAGNOSTIC_NOTE = (
    "a diagnostic: the residual of the engine's own check, held to its own absolute tolerance "
    "there, not a quantity of the simulated world"
)
# The observed rows span the period exactly, up to the rounding of the times the caller gave.
LOOP_SPAN_RTOL = 1e-9
WORD = re.compile(r"\w[\w.-]*")
HEAT_SUFFIX = "_dissipated_energy_pJ"
RESETS_NOTE = (
    "Written at the events of these operators, which retire slots: a retired slot's history in "
    "this ledger moves into the retiring operator's own record (the composite's checks add it "
    "back), so on that slot it restarts at zero. The slots are those its closure closes at that "
    "event, where the merged mask named by `mask` (the record view_<mask>) turns false: a retired "
    "cell, its membrane patches, the populations on them and its junctions. A difference across "
    "such an event is the operator's booking, not this ledger's flow; a heat total only grows "
    "with that record added back."
)
HEAT_NOTE = (
    "A total per element: zero or more and never falling, checked at every accepted row (the "
    "engine's check, allowance 1e-12 pJ). Under an exact free-energy heat booking a route's value "
    "is an exact attribution of its row's fall in free energy between the routes that move it, "
    "and cannot be measured apart."
)
BASES = {
    "accepted": ("accepted_times", "the state's accepted rows"),
    "observation": ("observation_times", "the observed rows"),
}
# Door S (module docstring).
VIEW_PREFIX = "view_"
VIEW_NOTE = (
    "Door S's merged view at the observe stage: the bound value with each change merged in "
    "declared order and closures applied, as the host observer formed it for this row's saved "
    "readouts (pump_composite.observe_history); re-formed at write time by the composite's own "
    "view function on the observed state, bitwise the same. Not the device step's own formation."
)
EVENT_ROWS = (
    "Every event here is an operator's event map, which acts at the start of the step that leaves "
    "the event's time: the row saved at that time holds the state before the event, the next row "
    "the state after it."
)
# The roles of the inner model's sets, each with what it is (a set states its own, "roles"): an
# oriented record names two roles of its set, as from and to (a flow) or plus and minus (a
# difference). Operators' sets declare theirs (view_sets).
SET_ROLES = MappingProxyType(
    {
        "membrane": {
            "inside": "the patch's cell",
            "outside": "the patch's outside node (the set's outside index)",
        },
        "channel": {
            "inside": "the cell of the population's patch",
            "outside": "that patch's outside node",
        },
        "junction": {
            "sender": "the junction's first cell (ends[0])",
            "receiver": "its second cell (ends[1])",
        },
        "face": {
            "sender": "the face's first outside node (ends[0])",
            "receiver": "its second outside node (ends[1])",
        },
        "outside": {"exterior": "beyond the world (a held node's reservoir)", "node": "the node"},
    }
)
FLOW_KEYS, DIFFERENCE_KEYS = ("from", "to"), ("plus", "minus")
# Per-entity facts an operator's (or a kind's) set may give (view_sets), one per id: the species
# each carries (a species id, or a list of them), a word each (declared direction, kind), or the
# entity each acts at ({set id: entity id}).
PER_ENTITY = ("carries", "direction", "kinds", "at")
# The activity mask of each set (the adapter's MASK_FIELDS): a retirement restarts a ledger on the
# slots where it closes.
SET_MASKS = MappingProxyType(
    {
        "cell": "active",
        "outside": "outside_active",
        "membrane": "membrane_active",
        "channel": "channel_active",
        "junction": "junction_active",
        "face": "face_active",
    }
)
# Unit suffixes, compound ones before their tails (docs/RUN_VIEW_DESIGN.md §3: a suffix rule and
# a table); a name that ends in none of them needs its owner's UNITS.
SUFFIX_UNITS = (
    ("_fmol_per_s", "fmol/s"),
    ("_m2_per_s", "m2/s"),
    ("_m_per_s", "m/s"),
    ("_fmol_s", "fmol/s"),
    ("_pJ_s", "pJ/s"),
    ("_pL_s", "pL/s"),
    ("_V_s", "V/s"),
    ("_J_mol", "J/mol"),
    ("_per_s", "1/s"),
    ("_fmol", "fmol"),
    ("_pJ", "pJ"),
    ("_pL", "pL"),
    ("_mM", "mM"),
    ("_m2", "m2"),
    ("_Pa", "Pa"),
    ("_V", "V"),
    ("_C", "C"),
    ("_A", "A"),
    ("_F", "F"),
    ("_K", "K"),
    ("_s", "s"),
    ("_m", "m"),
)


class ViewRefused(ConfigError):
    """The view cannot state something it must: nothing is written."""


class ViewInvalid(ConfigError):
    """A view (or its files) breaks the format: the reader-side check."""


# ------------------------------------------------------------------ the inner model's sets

# The inner model's own declarations (cells.model.resolved_pump_tissue@3's view declarations, folded per
# structure with its kinds'; models/surface_pump_v3.view_declarations) give every field's unit,
# readout axes, kind, layer, orientation and notes; the writer keeps no table of them.
# The inner layout's view fields that operators may provide (the composite adapter's
# VIEW_FIELDS), each with its axes and unit, plus two no operator provides; requirement 5.
VIEW_FIELD_AXES = MappingProxyType(
    {
        "temperature": ((), "K"),
        "valence": (("species",), "1"),
        "volume": (("cell_slot",), "pL"),
        "extracellular_volume": (("extracellular_slot",), "pL"),
        "membrane_area": (("membrane_slot",), "m2"),
        "membrane_capacitance": (("membrane_slot",), "F"),
        "initial_cell_charge_C": (("cell_slot",), "C"),
        "channel_abundance": (("channel_slot",), "1"),
        "channel_permeability": (("channel_slot",), "m/s"),
        "membrane_permeability": (("species", "membrane_slot"), "m/s"),
        "pump_capacity": (("membrane_slot",), "fmol/s"),
        "calcium_pump_capacity": (("membrane_slot",), "fmol/s"),
        "active": (("cell_slot",), "1"),
        "outside_active": (("extracellular_slot",), "1"),
        "membrane_active": (("membrane_slot",), "1"),
        "channel_active": (("channel_slot",), "1"),
        "junction_active": (("edge_slot",), "1"),
        "face_active": (("face_slot",), "1"),
        "extracellular_amount_reference": (("species", "extracellular_slot"), "fmol"),
    }
)
# The inner model's axis names and the view's sets.
AXIS_SETS = MappingProxyType(
    {
        "species": "species",
        "cell_slot": "cell",
        "extracellular_slot": "outside",
        "membrane_slot": "membrane",
        "edge_slot": "junction",
        "face_slot": "face",
        "channel_slot": "channel",
        "gate": "gate",
        "field_node": "node",
        "world": "world",
        "floating_component": "floating_component",
    }
)


# ------------------------------------------------------------------ the caller's inputs


@dataclass(frozen=True)
class Geometry:
    """A builder's geometry for the view (docs/RUN_VIEW_DESIGN.md §4): coordinates of cells and
    outside nodes, which definitions never hold (D154).

    sets: {set id: {"kind": ..., ...}} with one entry per declared entity, in the definition's
    order (padding slots get none): points {"centres", "radius"?}; spheres {"centres", "radius"};
    polygons {"vertices", "faces"}. representation: "prescribed" for a builder's static layout.
    """

    unit: str
    dimensions: int
    sets: dict
    source: str
    representation: str = "prescribed"


@dataclass(frozen=True)
class Recording:
    """A declared recording subset (requirement 1): the fields, elements and cadence a run keeps.

    fields: engine field names (state or observation), None for all; elements: {set id: entity
    ids}, None for all; every: keep every n-th observation row, counted from the first row this
    write saves (a continuation counts from its own first row). The history keeps every accepted
    row of the kept fields and elements.
    """

    fields: tuple | None = None
    elements: dict | None = None
    every: int = 1


@dataclass(frozen=True)
class Loop:
    """A looping replay package's loop (FR-11; docs/LOOPING_REPLAY_DESIGN.md §3). The writer
    measures its closure on the saved arrays and writes the view's loop block only when the run
    closes within the tolerance; nothing here is declared as measured.

    species: the caller's label, a word (the viewer's ids are its own); cell: a declared cell id,
    the cell the loop shows; period: the drive's period T in s, which the observed rows span
    exactly (the first at t0, the last at t0 + T); tolerance: the largest closure accepted;
    follows: ({"time", "from", "to"}, ...), the cell the loop follows after a division (§6),
    refused until the cycle's probe passes and its closure is built; cell_type: the caller's
    label (a word) for which of the species' cell types the loop is of, None for the species'
    default cell (the visualizer's cell-type design).
    """

    species: str
    cell: str
    period: float
    tolerance: float
    follows: tuple = ()
    cell_type: str | None = None


@dataclass(frozen=True)
class Request:
    """The caller's part of a view: run labels, geometry, a recording subset and, for a looping
    replay package, its loop."""

    run: dict = field(default_factory=dict)
    geometry: Geometry | None = None
    recording: Recording | None = None
    loop: Loop | None = None


# ------------------------------------------------------------------ helpers


def _refuse(problems):
    if problems:
        raise ViewRefused("The run view cannot be written: " + "; ".join(problems))


def _species_of(value, species):
    """Whether a set's `carries` entry names the model's species: one id, or a list of them."""
    if isinstance(value, (list, tuple)):
        return bool(value) and all(isinstance(v, str) and v in species for v in value)
    return isinstance(value, str) and value in species


def _unstated_order(item):
    return (item["what"], item["id"])


def _suffix_unit(name):
    for suffix, unit in SUFFIX_UNITS:
        if name.endswith(suffix):
            return unit
    return None


def _ids(entities, capacity):
    ids = [e.id for e in entities]
    return ids + [None] * (capacity - len(ids))


def _finite_list(value, what, problems):
    array = np.asarray(value, dtype=float)
    if not np.all(np.isfinite(array)):
        problems.append(f"{what} is not finite")
    return array.tolist()


def _layout_value(layout, name):
    return np.asarray(getattr(layout, name) if not isinstance(layout, dict) else layout[name])


def _composite_spec():
    from cells.definitions import pump_composite_spec

    return pump_composite_spec


def _family(spec):
    """(model, inner model ID, operator entries) of a definition in the view's scope."""
    from cells.definitions import surface_pump_v3_spec as tissue3
    from cells.registry.models import get_model

    composite = _composite_spec()
    if isinstance(spec.model, composite.CompositeModel):
        if spec.model.inner_model != tissue3.MODEL_ID:
            raise ViewRefused(f"No view declarations for inner model {spec.model.inner_model}")
        return get_model(spec.model), spec.model.inner_model, composite.entries(spec)
    if isinstance(spec.model, tissue3.SurfacePumpChannelModel):
        if any(j.law == tissue3.SERIES_GATE_LAW_ID for j in spec.model.junctions):
            raise ViewRefused(  # FR-30, v1 (D262): the gates' axis has no view set yet.
                f"No view declarations for {tissue3.SERIES_GATE_LAW_ID}'s junctions yet: its "
                "gates' axis has no view set (FR-30, v1)"
            )
        if getattr(spec.model, "forms_faces", ()):
            raise ViewRefused(  # The forms law, version 1: its movers' axis has no view set yet.
                "No view declarations for cells.route.logmean_electrodiffusion_forms@1's faces "
                "yet: their "
                "movers' axis has no view set (version 1)"
            )
        return get_model(spec.model), tissue3.MODEL_ID, ()
    raise ViewRefused(
        f"No view declarations for {type(spec.model).__name__}: version 1 covers "
        "cells.model.resolved_pump_composite@1 over cells.model.resolved_pump_tissue@3, and "
        "cells.model.resolved_pump_tissue@3"
    )


def _inner(model):
    return getattr(model, "inner", model)


def _engine_source(root=None):
    """The running engine's source revision, from its execution snapshot's own record
    (SNAPSHOT.json beside src/, validation/source_snapshot.py), or None when it runs from a
    checkout. AGENTS.md: a run's provenance is its Git revision, dirty diff and frozen snapshot.
    root: the source root (default: the one this package was imported from)."""
    if root is None:
        import cells

        root = Path(cells.__file__).resolve().parents[2]
    path = Path(root) / "SNAPSHOT.json"
    if not path.is_file():
        return None
    record = json.loads(path.read_text())
    revision = record.get("git_revision")
    if not isinstance(revision, str) or not revision:
        return None
    dirty = (
        record["dirty"] if "dirty" in record else bool(record.get("selected_status_porcelain_v1_z"))
    )
    return {
        "revision": revision,
        "dirty": bool(dirty),
        "from": "the execution snapshot's record (SNAPSHOT.json)",
    }


def end_of(checkpoint):
    """A shared path's end state for its view: the run completed at its final checkpoint."""
    return {
        "status": "complete",
        "time": float(checkpoint.time),
        "step": int(checkpoint.step_index),
    }


# ------------------------------------------------------------------ the plan


@dataclass(frozen=True)
class FieldInfo:
    name: str
    axes: tuple  # Set ids, after time.
    unit: str
    layer: str
    owner: str
    kind: str | None
    sign: dict | None
    writers: tuple = ()
    diagnostic: bool = False  # Its owner's RECORD_DIAGNOSTICS.
    reference: str | None = None  # Its owner's RECORD_REFERENCES: the reference layout field.


class Plan:
    """Everything the view states that does not depend on the saved files, checked before any
    output exists (prepare). The shared paths keep its recording subset (keeper) and write the
    view from it (write)."""

    def __init__(self, spec, request, layout, recompute=True):
        self.spec, self.request = spec, request or Request()
        self.model, self.inner_id, self.entries = _family(spec)
        self.problems, self.unstated = [], []
        # Door S (module docstring): the shared paths re-form the merged view from the bound
        # layout (the run's checkpoint layout); a run already on disk gets no new arrays.
        self.recompute = recompute and hasattr(layout, "_fields")
        self.layout = (
            type(layout)(*(np.asarray(v) for v in layout)) if hasattr(layout, "_fields") else None
        )
        # The engine that runs this run, where a shared path writes the view as it runs.
        self.source = _engine_source() if self.recompute else None
        if self.source is None:
            self.unstated.append(
                {
                    "id": "source",
                    "what": "engine source",
                    "why": "the view is written for a run already on disk"
                    if not self.recompute
                    else "the engine runs from a checkout, not an execution snapshot: its revision "
                    "is the caller's label, if given",
                }
            )
        self.retiring = tuple(op.LAW_ID for op, _, _ in self.entries if op.RETIRES)
        self.energy_roles = self._declared_energy_roles()
        inner = _inner(self.model)
        inner_layers = getattr(inner, "VIEW_LAYERS", None)
        if not inner_layers:
            self.problems.append(f"{self.inner_id} declares no VIEW_LAYERS")
        self.notes = dict(getattr(inner, "RECORD_NOTES", {}))
        self.inner_names = frozenset(
            (*inner.STATE_AXES, *(k for k in inner.OBSERVATION_FIELDS if k != "times"))
        )
        self.layers = [dict(layer, owner=self.inner_id) for layer in inner_layers or ()]
        self.operator_layers = {}
        for op, _, _ in self.entries:
            layers = op.VIEW_LAYERS
            if layers is None:
                self.problems.append(f"{op.LAW_ID} declares no VIEW_LAYERS")
                continue
            self.operator_layers[op.LAW_ID] = [layer["id"] for layer in layers]
            self.layers += [dict(layer, owner=op.LAW_ID) for layer in layers]
        ids = [layer["id"] for layer in self.layers]
        duplicated = sorted({i for i in ids if ids.count(i) > 1})
        if duplicated:
            self.problems.append("layer ids declared twice: " + ", ".join(duplicated))
        self.sets = self._sets(layout)
        self.axis_sets = dict(AXIS_SETS)
        self._inner_sets(inner)
        self._operator_sets()
        self.fields = self._fields()
        self.changes = self._view_changes()
        self.constants = self._constants(layout)
        self.events = self._events()
        self.space = self._geometry()
        self.recording = self._recording()
        self.run = self._run()
        self.loop = self._loop()
        _refuse(self.problems)
        try:  # The view's structure, before any output: only its time bases come later.
            validate(self.view({}, "prepared"))
        except ViewInvalid as exc:
            raise ViewRefused(str(exc)) from exc

    # -------------------------------------------------------------- sets

    def _sets(self, layout):
        from cells.models import inner_laws
        from cells.models import surface_pump_v3 as tissue3
        from cells.registry import species_registry

        m, e = self.spec.model, self.spec.execution
        n, o = e.capacity, e.extracellular_capacity
        cells, outside = _ids(m.cells, n), _ids(m.extracellular, o)
        membranes = _ids(m.membranes, e.membrane_capacity)
        junctions = _ids(m.junctions, e.edge_capacity)
        faces = _ids(m.faces, e.face_capacity)
        channels = _ids(m.channels, e.channel_capacity)
        structure = tissue3.structure(m)

        def index(ids, of):
            return [ids.index(x) for x in of]

        def padded(values, size):
            return list(values) + [None] * (size - len(values))

        resolved = species_registry.identities(self.spec)
        registry = species_registry.declared(self.spec)
        species = []
        for s in m.species_ids:
            source, identity = resolved.get(s, (None, None))
            entry = None if registry is None else registry.entry(s)
            item = {
                "identity": None
                if identity is None
                else {
                    "catalogue": None
                    if identity.catalogue is None
                    else dict(zip(("catalogue", "entry"), identity.catalogue, strict=True)),
                    "evidence": identity.evidence,
                    "source": source,
                }
            }
            if entry is not None and entry.standard_mu_RT is not None:
                item["standard_mu_RT"] = entry.standard_mu_RT
                item["standard_concentration_mM"] = registry.standard_concentration_mM
            if entry is not None and entry.background is not None:
                item["background"] = {
                    "trace_mM": entry.background.trace_mM,
                    "floor_fmol": entry.background.floor_fmol,
                }
            species.append(item)
        lives = {}
        for op, declaration, schedule in self.entries:
            for cell, life in op.living_intervals(self.spec, declaration, schedule).items():
                if cell in lives:
                    self.problems.append(f"two operators decide the life of cell {cell}")
                lives[cell] = [None if t is None else float(t) for t in life]

        def pump(spec_pump, law_id, roles):
            law = inner_laws.PUMP_LAWS.get(law_id)
            if law is None:
                self.problems.append(f"pump law {law_id} has no declaration")
                return None
            return {
                "id": spec_pump.id,
                "law_id": law_id,
                "provenance": law.provenance,
                "per_cycle": [
                    {"role": role, "species": s, "count": count}
                    for (role, count), s in zip(law.moves, roles, strict=True)
                ],
                "per_cycle_sign": "inward-positive",
                "fuel_kinds": list(law.fuel_kinds),
            }

        def channel_law(c):
            law = inner_laws.CHANNEL_LAWS[c.kinetic_law]
            return {"law_id": law.law_id, "provenance": law.provenance, "gates": list(law.gates)}

        def junction_law(j):
            law = inner_laws.JUNCTION_LAWS.get(j.law)
            if law is None:
                self.problems.append(f"junction law {j.law} has no declaration")
                return {"law_id": j.law}
            return {"law_id": law.law_id, "provenance": law.provenance}

        basis = _layout_value(layout, "field_floating_basis")
        reservoir = _layout_value(layout, "reservoir").astype(bool).tolist()
        factored = any(getattr(c, "factors", ()) for c in m.channels)  # B1's door (docstring).
        channel_factors = (
            {
                "factors": padded(
                    [list(getattr(c, "factors", ())) for c in m.channels], len(channels)
                )
            }
            if factored
            else {}
        )
        return {
            "species": {
                "id": "species",
                "scale": "molecule",
                "ids": list(m.species_ids),
                "valence": [int(z) for z in m.valence],
                "species": species,
            },
            "cell": {
                "id": "cell",
                "scale": "cell",
                "ids": cells,
                "lifetimes": [lives.get(c) for c in cells],
                "geometry": None,
            },
            "outside": {
                "id": "outside",
                "scale": "cell",
                "holds": "outside node",
                "ids": outside,
                "reservoir": [bool(r) for r in reservoir],
                "geometry": None,
                "roles": dict(SET_ROLES["outside"]),
            },
            "membrane": {
                "id": "membrane",
                "scale": "cell",
                "holds": "membrane patch",
                "ids": membranes,
                "geometry": {
                    "kind": "on",
                    "set": "cell",
                    "index": padded(index(cells, [p.inside for p in m.membranes]), len(membranes)),
                },
                "outside": {
                    "set": "outside",
                    "index": padded(
                        index(outside, [p.outside for p in m.membranes]), len(membranes)
                    ),
                },
                "laws": padded(
                    [
                        {"law_id": getattr(p, "law", inner_laws.MEMBRANE_ROUTE_LAW_ID)}
                        for p in m.membranes
                    ],
                    len(membranes),
                ),
                "pumps": padded(
                    [
                        None if p.pump is None else pump(p.pump, p.pump.law, p.pump.roles)
                        for p in m.membranes
                    ],
                    len(membranes),
                ),
                "calcium_pumps": padded(
                    [
                        None
                        if p.calcium_pump is None
                        else pump(p.calcium_pump, p.calcium_pump.law, (p.calcium_pump.role,))
                        for p in m.membranes
                    ],
                    len(membranes),
                ),
                "pumps_are": "columns of this set (version 1)",
                "roles": dict(SET_ROLES["membrane"]),
            },
            "junction": {
                "id": "junction",
                "scale": "cell",
                "ids": junctions,
                "geometry": {
                    "kind": "links",
                    "between": "cell",
                    "ends": padded(
                        [[cells.index(j.sender), cells.index(j.receiver)] for j in m.junctions],
                        len(junctions),
                    ),
                },
                "laws": padded([junction_law(j) for j in m.junctions], len(junctions)),
                "roles": dict(SET_ROLES["junction"]),
            },
            "face": {
                "id": "face",
                "scale": "cell",
                "holds": "face",
                "ids": faces,
                "geometry": {
                    "kind": "links",
                    "between": "outside",
                    "ends": padded(
                        [[outside.index(f.sender), outside.index(f.receiver)] for f in m.faces],
                        len(faces),
                    ),
                },
                "laws": padded(
                    [{"law_id": getattr(f, "law", inner_laws.FACE_ROUTE_LAW_ID)} for f in m.faces],
                    len(faces),
                ),
                "roles": dict(SET_ROLES["face"]),
            },
            "channel": {
                "id": "channel",
                "scale": "cell",
                "holds": "channel population",
                "ids": channels,
                "geometry": {
                    "kind": "on",
                    "set": "membrane",
                    "index": padded(
                        index(membranes, [c.membrane_id for c in m.channels]), len(channels)
                    ),
                },
                "laws": padded([channel_law(c) for c in m.channels], len(channels)),
                **channel_factors,
                "roles": dict(SET_ROLES["channel"]),
            },
            "gate": {
                "id": "gate",
                "scale": "molecule",
                "holds": "channel gate row",
                "ids": [f"gate_{i}" for i in range(structure.gate_rows)],
                "says": "row i of a population's gates is gates[i] of its law (the channel set)",
            },
            "node": {
                "id": "node",
                "scale": "cell",
                "holds": "field node",
                "ids": cells + outside,
                "composed_of": ["cell", "outside"],
            },
            "world": {"id": "world", "scale": "cell", "ids": ["world"]},
            "floating_component": {
                "id": "floating_component",
                "scale": "cell",
                "holds": "floating capacitor component",
                "ids": [f"component_{k}" for k in range(basis.shape[1])],
                "members": [np.flatnonzero(basis[:, k]).tolist() for k in range(basis.shape[1])],
            },
        }

    def _inner_sets(self, inner):
        """The inner model's kinds' sets (their declarations, folded in its implementation
        object): VIEW_AXIS_SETS maps an axis of a kind's fields to an existing set (the proton
        buffer's node: cells, then outside nodes), and view_sets(spec) declares a kind's own
        axes' sets, placed as an operator's are (roles, per-entity facts), owned by the inner
        model. An axis of the inner model's fields with no set is refused."""
        for axis, set_id in dict(getattr(inner, "VIEW_AXIS_SETS", {})).items():
            if set_id in self.sets:
                self.axis_sets[axis] = set_id
            else:
                self.problems.append(f"{self.inner_id}: axis {axis} maps to no set {set_id!r}")
        view_sets = getattr(inner, "view_sets", None)
        declared = view_sets(self.spec) if callable(view_sets) else {}
        axes = {
            axis
            for name in self.inner_names
            for axis in (
                inner.STATE_AXES.get(name) or getattr(inner, "OBSERVATION_AXES", {}).get(name) or ()
            )
            if axis not in self.axis_sets
        }
        for axis in sorted(axes - set(declared)):
            self.problems.append(f"{self.inner_id} declares no set for its axis {axis}")
        for key in sorted(declared):
            set_id = self._owned_set(self.inner_id, dict(declared[key]))
            if set_id is not None and key in axes:
                self.axis_sets[key] = set_id

    def _operator_sets(self):
        """Each operator's own sets, from its view_sets declaration (the contract): one for every
        axis of its own (refused without), and any further set of its entities it describes. An
        entry gives id and ids, optionally holds, roles ({role: what it is}), "on" (set id, entity
        ids) and per-entity facts (PER_ENTITY: the species each carries, a word each, or the
        entity each acts at)."""
        for op, declaration, _ in self.entries:
            own = {
                axis
                for axes in (*op.STATE_AXES.values(), *op.OBSERVATION_AXES.values())
                for axis in axes
                if axis not in self.axis_sets
            }
            declared = op.view_sets(self.spec, declaration)
            for axis in sorted(own - set(declared)):
                self.problems.append(f"{op.LAW_ID} declares no set for its axis {axis}")
            for key in sorted(declared):
                set_id = self._owned_set(op.LAW_ID, dict(declared[key]))
                if set_id is not None and key in own:
                    self.axis_sets[key] = set_id

    def _owned_set(self, law, entry):
        """One declared set into self.sets (its id), owned by `law` (an operator's, or the inner
        model's for its kinds' sets), or None with the problem noted."""
        set_id, ids = entry.pop("id", None), list(entry.pop("ids", ()))
        if not isinstance(set_id, str) or not set_id or set_id in self.sets:
            self.problems.append(f"{law}: set {set_id!r} is unnamed or declared twice")
            return None
        if len(set(ids)) != len(ids) or not all(isinstance(i, str) and i for i in ids):
            self.problems.append(f"{law}: the ids of set {set_id} are unique strings")
        item = {"id": set_id, "scale": "cell", "ids": ids, "owner": law}
        on = entry.pop("on", None)
        if on is not None:
            target, of = on
            known = self.sets.get(target, {}).get("ids", [])
            if any(x not in known for x in of) or len(of) != len(ids):
                self.problems.append(f"{law}: set {set_id} lies on unknown entities")
            else:
                item["geometry"] = {
                    "kind": "on",
                    "set": target,
                    "index": [known.index(x) for x in of],
                }
        roles = entry.pop("roles", None)
        if roles is not None:
            if not (
                hasattr(roles, "items")
                and roles
                and all(
                    isinstance(k, str) and isinstance(v, str) and k and v for k, v in roles.items()
                )
            ):
                self.problems.append(f"{law}: the roles of set {set_id} name what each role is")
            item["roles"] = dict(roles)
        for key in PER_ENTITY:
            if key not in entry:
                continue
            values = list(entry.pop(key))
            if len(values) != len(ids):
                self.problems.append(f"{law}: set {set_id} gives {key} once per id")
            elif key == "carries" and not all(
                _species_of(v, self.sets["species"]["ids"]) for v in values
            ):
                self.problems.append(f"{law}: set {set_id} carries species the model lacks")
            elif key == "at" and not all(self._entity(v) for v in values):
                self.problems.append(f"{law}: set {set_id} acts at entities not the definition's")
            elif key not in ("carries", "at") and not all(isinstance(v, str) for v in values):
                self.problems.append(f"{law}: set {set_id} gives {key} as words")
            elif key == "kinds" and any("@" in v for v in values):
                self.problems.append(
                    f"{law}: set {set_id} gives a versioned ID as a kind; kinds are words, and a "
                    "law's ID goes under laws"
                )
            item[key] = [dict(v) for v in values] if key == "at" else values
        item |= entry
        self.sets[set_id] = item
        return set_id

    def _entity(self, value):
        """Whether value is one {set id: entity id} of a declared entity."""
        if not (hasattr(value, "items") and len(value) == 1):
            return False
        ((set_id, entity_id),) = value.items()
        return bool(entity_id) and entity_id in self.sets.get(set_id, {}).get("ids", ())

    # -------------------------------------------------------------- fields

    def _owners(self):
        if hasattr(self.model, "field_owners"):
            owners = self.model.field_owners(self.spec)
            state = {k: v["owner"] for k, v in owners["state"].items()}
            writers = {k: tuple(v["writers"]) for k, v in owners["state"].items()}
            columns = {k: v[-1] for k, v in owners["observations"].items()}
        else:
            state = dict.fromkeys(self.model.STATE_AXES, "inner")
            writers = {}
            columns = dict.fromkeys(self.model.OBSERVATION_FIELDS, "inner")
        return state, writers, columns

    def _fields(self):
        """FieldInfo of every state field and observation column of this spec's model."""
        inner = _inner(self.model)
        declared = {
            "units": getattr(inner, "UNITS", {}),
            "axes": getattr(inner, "OBSERVATION_AXES", {}),
            "kinds": getattr(inner, "RECORD_KINDS", {}),
            "signs": getattr(inner, "ORIENTATION", {}),
            "layers": getattr(inner, "RECORD_LAYERS", {}),
        }
        operators = {op.LAW_ID: op for op, _, _ in self.entries}
        state_owner, writers, column_owner = self._owners()
        names = list(self.model.STATE_AXES)
        names += [k for k in self.model.OBSERVATION_FIELDS if k != "times" and k not in names]
        checks = self._inner_checks(inner, names)
        out = {}
        for name in names:
            owner = state_owner.get(name) or column_owner.get(name)
            if owner is None:
                self.problems.append(f"field {name} has no owner in the composition's field map")
                continue
            axes = self.model.STATE_AXES.get(name)
            if owner == "inner" or name in self.inner_names:
                info = self._inner_field(name, axes, owner, declared)
            else:
                info = self._operator_field(name, axes, operators[owner])
            if info is None:
                continue
            # A diagnostic and an increment's reference are their owner's to declare.
            if owner == "inner":
                diagnostics, references = checks
            else:
                op = operators[owner]
                diagnostics, references = op.RECORD_DIAGNOSTICS, op.RECORD_REFERENCES
            out[name] = FieldInfo(
                **info,
                writers=writers.get(name, ()),
                diagnostic=name in diagnostics,
                reference=references.get(name),
            )
        return out

    def _declared_energy_roles(self):
        """{field: kind_registry.EnergyRole} of the inner model's declared kinds' fields and of
        each operator's (seam D, docs/CORE_SEAMS_DESIGN.md §6.1): a declaration, else today's
        suffix rule (kind_registry.energy_role, contract.energy_roles). @3's own fields take the
        suffix rule (_monotone), as the dissipation check does."""
        from cells.models import surface_pump_v3
        from cells.operators import contract
        from cells.registry import kind_registry

        roles = {}
        for kind in surface_pump_v3._kinds(getattr(_inner(self.model), "structure", None)):
            for name in kind.state_fields:
                role = kind_registry.energy_role(kind, name)
                if role is not None:
                    roles[name] = role
        for op, _, _ in self.entries:
            roles.update(contract.energy_roles(op))
        return roles

    def _monotone(self, name):
        """Whether a field's record claims a non-decreasing total per element: its declared
        energy role is heat and monotone, or, undeclared, it ends in _dissipated_energy_pJ (today's
        rule). A heat declared non-monotone, such as GARD's event heat, claims nothing."""
        role = self.energy_roles.get(name)
        if role is not None:
            return role.role == "heat" and role.monotone
        return name.endswith(HEAT_SUFFIX)

    def _inner_checks(self, inner, names):
        """The inner model's RECORD_DIAGNOSTICS and RECORD_REFERENCES (the contract's forms; none
        when it declares none), checked against its own fields and bound layout."""
        diagnostics = tuple(getattr(inner, "RECORD_DIAGNOSTICS", ()))
        references = dict(getattr(inner, "RECORD_REFERENCES", {}))
        unknown = sorted(set(diagnostics) - set(names))
        if unknown:
            self.problems.append(f"the inner model declares diagnostics it lacks: {unknown}")
        layout = set(getattr(self.layout, "_fields", ()))
        for name, reference in references.items():
            if name not in self.model.STATE_AXES or (layout and reference not in layout):
                self.problems.append(
                    f"the inner model's reference of {name} is not a state field's reference "
                    f"layout field ({reference!r})"
                )
        return frozenset(diagnostics), references

    def _inner_field(self, name, axes, owner, declared):
        """A field of the inner model, from its own declarations only (never guessed)."""
        axes = axes if axes is not None else declared["axes"].get(name)
        unit = declared["units"].get(name)
        layer = declared["layers"].get(name)
        if owner != "inner":  # A column an operator replaces (REPLACES): its owner's layer.
            ops = {op.LAW_ID: op for op, _, _ in self.entries}
            layer = self._operator_layer(ops[owner], name)
        if axes is None or unit is None or layer is None:
            self.problems.append(
                f"{self.inner_id} declares no axes, unit or layer for its field {name}"
            )
            return None
        kind = declared["kinds"].get(name)
        if kind is None:
            self.unstated.append(
                {"id": name, "what": "kind", "why": f"{self.inner_id} declares no kind for it"}
            )
        return self._info(
            name,
            axes,
            unit,
            layer,
            self.inner_id if owner == "inner" else owner,
            kind,
            declared["signs"].get(name),
        )

    def _operator_layer(self, op, name):
        layers = self.operator_layers.get(op.LAW_ID)
        if layers is None:
            return None  # Refused already: no VIEW_LAYERS.
        layer = op.RECORD_LAYERS.get(name)
        if layer is None and len(layers) == 1:
            layer = layers[0]
        if layer not in layers:
            self.problems.append(f"{op.LAW_ID} does not name the layer of its field {name}")
            return None
        return layer

    def _operator_field(self, name, axes, op):
        if axes is None:
            axes = op.OBSERVATION_AXES.get(name)
        if axes is None:
            self.problems.append(f"{op.LAW_ID} declares no axes for its readout column {name}")
            return None
        unit = op.UNITS.get(name) or _suffix_unit(name)
        if unit is None:
            self.problems.append(f"{op.LAW_ID} declares no unit for its field {name}")
            return None
        layer = self._operator_layer(op, name)
        if layer is None:
            return None
        kind = op.RECORD_KINDS.get(name)
        if kind is None:
            # Only the contract's energy roles say what a field is: heat and work are booked
            # totals. An entity write's accumulator may be a retirement record, whose jump is
            # bookkeeping, not a flow: its kind is its owner's to declare.
            if name in (*op.HEAT_FIELDS, *op.WORK_FIELDS):
                kind = "cumulative"
            else:
                self.unstated.append(
                    {"id": name, "what": "kind", "why": f"{op.LAW_ID} declares no kind for it"}
                )
        sign = op.ORIENTATION.get(name)
        return self._info(name, axes, unit, layer, op.LAW_ID, kind, sign)

    def _info(self, name, axes, unit, layer, owner, kind, sign):
        sets = []
        for axis in axes:
            set_id = self.axis_sets.get(axis)
            if set_id is None:
                self.problems.append(f"field {name}: axis {axis} maps to no set")
                return None
            sets.append(set_id)
        if kind is not None and kind not in KINDS:
            self.problems.append(f"field {name}: kind {kind!r} is not one of {KINDS}")
        if sign is not None:
            roles = self.sets[sets[-1]].get("roles", {}) if sets else {}
            ends = DIFFERENCE_KEYS if "plus" in sign else FLOW_KEYS
            if any(sign.get(k) not in roles for k in ends) or sign[ends[0]] == sign[ends[1]]:
                self.problems.append(f"field {name}: its orientation names roles its set lacks")
            sign = dict(sign)
        return dict(
            name=name,
            axes=tuple(sets),
            unit=unit,
            layer=layer,
            owner=owner,
            kind=kind,
            sign=sign,
        )

    # -------------------------------------------------------------- constants (requirement 5)

    def _view_changes(self):
        """Door S (module docstring): {view field: FieldInfo} of each field of the table that the
        composition's merge can change, in the table's order, its writers in merge order and its
        owner the last of them. Also refuses where the observed state is not the state."""
        if not self.entries:
            return {}
        from cells.models import pump_composite_adapter as adapter

        owners = self.model.field_owners(self.spec)
        chains = {}
        for name, entry in owners["views"].items():
            if "provider" in entry:  # Providers, in merge order (the field map's chain).
                chains[name] = (
                    [law for law, _, _ in entry["changes"]]
                    if "changes" in entry
                    else [entry["provider"]]
                )
        closers = [op.LAW_ID for op, _, _ in self.entries if op.CLOSES]
        if closers:
            # Stopgap until the composite declares its changed set (after D172's landing): what
            # close() changes, from the adapter's tables. Closure propagates to every mask and
            # pads the padded fields on closed slots, after the providers' merge.
            for name in (*adapter.MASK_FIELDS, *adapter.PADDED_FIELDS):
                if name in VIEW_FIELD_AXES:
                    chains[name] = [*chains.get(name, []), *closers]
        unknown = sorted(set(chains) - set(VIEW_FIELD_AXES))
        if unknown:
            self.problems.append("changed view fields the view cannot place: " + ", ".join(unknown))
        if not chains:
            return {}
        replaced = sorted(
            k for k in self.model.STATE_TYPE._fields if len(owners["observations"].get(k, ())) > 1
        )
        if replaced:
            self.problems.append(
                "an operator replaces the observed state columns "
                + ", ".join(replaced)
                + " (REPLACES), so the observe stage's merged view cannot be re-formed from them"
            )
        operators = {op.LAW_ID: op for op, _, _ in self.entries}
        out = {}
        for name, (axes, unit) in VIEW_FIELD_AXES.items():
            if name not in chains:
                continue
            chain = chains[name]
            layer = self._operator_layer(operators[chain[-1]], name)
            if layer is None:
                continue
            out[name] = FieldInfo(
                name=name,
                axes=tuple(self.axis_sets[a] for a in axes),
                unit=unit,
                layer=layer,
                owner=chain[-1],
                kind="level",
                sign=None,
                writers=tuple(chain),
            )
        return out

    def _constants(self, layout):
        out = []
        for name, (axes, unit) in VIEW_FIELD_AXES.items():
            if name in self.changes:  # A record (door S), unless the run is already on disk.
                if not self.recompute:
                    self.unstated.append(
                        {
                            "id": name,
                            "what": "view field",
                            "why": "changed by "
                            + ", ".join(self.changes[name].writers)
                            + ": a run already on disk, whose manifest's checksums cover its "
                            "payload, so the writer adds no merged view of it",
                        }
                    )
                continue
            value = _layout_value(layout, name)
            if name == "valence":
                value = value.reshape(-1)
            sets = [self.axis_sets[a] for a in axes]
            shape = tuple(len(self.sets[s]["ids"]) for s in sets)
            if value.shape != shape:
                self.problems.append(f"constant {name}: shape {value.shape}, its sets {shape}")
                continue
            values = (
                value.astype(bool).tolist()
                if value.dtype == bool
                else _finite_list(value, f"constant {name}", self.problems)
            )
            out.append(
                {
                    "id": name,
                    "unit": unit,
                    "axes": sets,
                    "values": values,
                    "from": "the definition (the bound layout)",
                    "says": "nothing of this composition changes it (checked at every observed "
                    "row where the composition changes another view field)",
                }
            )
        # The fixed reference of each field stored as an increment over it (RECORD_REFERENCES),
        # where no view field states it already (a view field's reference is the constant above,
        # or its merged view record where door S changes it). Checked here, before any output,
        # and written by view() only where a written record names it (§9's item 3).
        self.references = {}
        for name, info in self.fields.items():
            reference = info.reference
            if (
                reference is None
                or reference in VIEW_FIELD_AXES
                or reference in self.references
                or any(c["id"] == reference for c in out)
            ):
                continue
            value = _layout_value(layout, reference)
            shape = tuple(len(self.sets[s]["ids"]) for s in info.axes)
            if value.shape != shape:
                self.problems.append(
                    f"the reference {reference} of {name}: shape {value.shape}, its sets {shape}"
                )
                continue
            self.references[reference] = {
                "id": reference,
                "unit": info.unit,
                "axes": list(info.axes),
                "values": _finite_list(value, f"constant {reference}", self.problems),
                "from": "the definition (the bound layout)",
                "says": f"the fixed reference that {name} is stored over: its quantity is "
                "this plus the record",
            }
        return out

    def _reference_of(self, reference, merged):
        """Where a record's fixed reference is stated: a constant, or the merged view record
        where door S changes it and the run saves it (merged); otherwise its field only, which
        unstated explains (a run already on disk, or one with no observed rows)."""
        if reference in self.changes:
            return {"record": VIEW_PREFIX + reference} if merged else {"field": reference}
        return {"constant": reference}

    # -------------------------------------------------------------- events

    def _events(self):
        events = []
        for op, declaration, schedule in self.entries:
            if op.LAW_ID not in self.operator_layers:
                continue  # Refused already: no VIEW_LAYERS.
            own = [dict(event) for event in op.view_events(self.spec, declaration, schedule)]
            # Births and retirements come from living_intervals (the contract's default); an
            # override keeps them, so no life reaches the sets without its events.
            stated = {
                (float(e["time"]), e.get("kind"), json.dumps(e.get("at"), sort_keys=True))
                for e in own
                if isinstance(e.get("time"), (int, float, np.floating))
            }
            lives = op.living_intervals(self.spec, declaration, schedule)
            for cell, (birth, retirement) in sorted(lives.items()):
                for time, kind in ((birth, "birth"), (retirement, "retirement")):
                    if time is None:
                        continue
                    key = (float(time), kind, json.dumps({"cell": cell}, sort_keys=True))
                    if key not in stated:
                        self.problems.append(
                            f"{op.LAW_ID}: its view_events leave out the {kind} of {cell} at "
                            f"{float(time)} s (living_intervals)"
                        )
            events += [self._event(op, event) for event in own]
        unique = {json.dumps(e, sort_keys=True): e for e in events if e is not None}
        return sorted(
            unique.values(), key=lambda e: (e["time"], e["kind"], json.dumps(e, sort_keys=True))
        )

    def _event(self, op, event):
        keys = set(event)
        if (
            not {"time", "kind", "layer", "at"}
            <= keys
            <= {"time", "kind", "layer", "at", "from", "label"}
        ):
            self.problems.append(f"{op.LAW_ID}: an event has keys {sorted(keys)}")
            return None
        for part in ("at", "from"):
            if part not in event:
                continue
            entity = event[part]
            if not (isinstance(entity, dict) and len(entity) == 1):
                self.problems.append(f"{op.LAW_ID}: an event's {part} is one {{set: id}}")
                return None
            ((set_id, entity_id),) = entity.items()
            if (
                set_id not in self.sets
                or entity_id not in self.sets[set_id]["ids"]
                or not entity_id
            ):
                self.problems.append(f"{op.LAW_ID}: an event names {entity}, not the definition's")
                return None
        if event["layer"] not in (self.operator_layers.get(op.LAW_ID) or ()):
            self.problems.append(f"{op.LAW_ID}: an event's layer is one of its own")
            return None
        event["time"] = float(event["time"])
        event.setdefault("label", "")
        return event

    # -------------------------------------------------------------- caller inputs

    def _geometry(self):
        geometry = self.request.geometry
        if geometry is None:
            self.unstated.append(
                {
                    "id": "geometry",
                    "what": "geometry",
                    "why": "the caller gave no builder geometry: no coordinates, and no space",
                }
            )
            return None
        problems = self.problems
        if geometry.unit not in LENGTH_UNITS:
            problems.append(f"geometry unit {geometry.unit!r} is not one of {LENGTH_UNITS}")
        if geometry.dimensions not in (2, 3):
            problems.append("geometry has 2 or 3 dimensions")
        if geometry.representation not in REPRESENTATIONS:
            problems.append(f"geometry representation is one of {REPRESENTATIONS}")
        if not isinstance(geometry.source, str) or not geometry.source:
            problems.append("geometry names its source (the builder)")
        m = self.spec.model
        declared = {"cell": len(m.cells), "outside": len(m.extracellular)}
        for set_id, entry in geometry.sets.items():
            if set_id not in declared:
                problems.append(
                    f"geometry for set {set_id!r}: only cell and outside take a builder's "
                    "geometry (the definition fixes the others' topology)"
                )
                continue
            placed = self._placed(set_id, dict(entry), declared[set_id], geometry.dimensions)
            if placed is not None:
                self.sets[set_id]["geometry"] = placed
        return {
            "unit": geometry.unit,
            "dimensions": geometry.dimensions,
            "representation": geometry.representation,
            "source": geometry.source,
        }

    def _placed(self, set_id, entry, count, dimensions):
        problems, kind = self.problems, entry.get("kind")
        size = len(self.sets[set_id]["ids"])

        def points(values, what):
            array = np.asarray(values, dtype=float)
            if array.shape != (count, dimensions) or not np.all(np.isfinite(array)):
                problems.append(
                    f"geometry of {set_id}: {what} is {count} finite {dimensions}-vectors"
                )
                return None
            return array.tolist() + [None] * (size - count)

        if kind in ("points", "spheres"):
            if not set(entry) <= {"kind", "centres", "radius"} or "centres" not in entry:
                problems.append(f"geometry of {set_id}: {kind} has centres and a radius")
                return None
            if kind == "spheres" and "radius" not in entry:
                problems.append(f"geometry of {set_id}: spheres have a radius")
                return None
            out = {"kind": kind, "centres": points(entry["centres"], "centres")}
            if "radius" in entry:
                radius = np.asarray(entry["radius"], dtype=float)
                if radius.shape not in ((), (count,)) or not np.all(radius > 0):
                    problems.append(f"geometry of {set_id}: radius is positive, one or per entity")
                    return None
                out["radius"] = (
                    float(radius)
                    if radius.shape == ()
                    else radius.tolist() + [None] * (size - count)
                )
            return None if out["centres"] is None else out
        if kind == "polygons":
            if set(entry) != {"kind", "vertices", "faces"}:
                problems.append(f"geometry of {set_id}: polygons have vertices and faces")
                return None
            vertices = np.asarray(entry["vertices"], dtype=float)
            faces = entry["faces"]
            if (
                vertices.ndim != 2
                or vertices.shape[1] != dimensions
                or not np.all(np.isfinite(vertices))
            ):
                problems.append(f"geometry of {set_id}: vertices are finite {dimensions}-vectors")
                return None
            if len(faces) != count or any(
                len(f) < 3 or any(not (0 <= int(v) < len(vertices)) for v in f) for f in faces
            ):
                problems.append(f"geometry of {set_id}: one face of 3 or more vertices per entity")
                return None
            return {
                "kind": "polygons",
                "vertices": vertices.tolist(),
                "faces": [[int(v) for v in f] for f in faces] + [None] * (size - count),
            }
        problems.append(f"geometry of {set_id}: kind {kind!r} is points, spheres or polygons")
        return None

    def _recording(self):
        recording = self.request.recording
        if recording is None:
            return None
        problems = self.problems
        if type(recording.every) is not int or recording.every < 1:
            problems.append("recording: every is an integer >= 1")
        if recording.fields is not None:
            known = set(self.fields) | {VIEW_PREFIX + k for k in self.changes}
            unknown = [f for f in recording.fields if f not in known]
            if unknown or not recording.fields:
                problems.append("recording: unknown or no fields " + ", ".join(map(str, unknown)))
        selected = {}
        for set_id, ids in (recording.elements or {}).items():
            if set_id not in self.sets or set_id in ("world", "node", "floating_component"):
                problems.append(f"recording: elements of set {set_id!r} cannot be selected")
                continue
            known = self.sets[set_id]["ids"]
            if (
                not ids
                or len(set(ids)) != len(ids)
                or any(i not in known or i is None for i in ids)
            ):
                problems.append(f"recording: elements of {set_id} are distinct declared ids")
                continue
            selected[set_id] = [known.index(i) for i in ids]
        for set_id, indices in selected.items():
            self.sets[set_id]["recorded"] = indices
        return {
            "fields": None if recording.fields is None else list(recording.fields),
            "elements": None
            if recording.elements is None
            else {k: list(v) for k, v in recording.elements.items()},
            "every": recording.every,
        }

    def _run(self):
        problems, labels = self.problems, dict(self.request.run or {})
        for key, value in labels.items():
            kind = RUN_KEYS.get(key)
            if kind is None or type(value) is not kind:
                problems.append(f"run label {key!r} is one of {sorted(RUN_KEYS)}, with its type")
        composition = (
            self.model.composition_identity(self.spec)
            if hasattr(self.model, "composition_identity")
            else None
        )
        models = (
            [composition["model"], composition["inner_model"], *composition["operators"]]
            if composition
            else [self.inner_id]
        )
        return labels | {
            "model": models[0],
            "engine_models": models,
            "composition": composition,
            "definition_sha256": self.spec.fingerprint,
            "scale": "cell",
            **({"source": self.source} if self.source else {}),
        }

    # -------------------------------------------------------------- the loop (FR-11)

    def _loop(self):
        """The caller's loop, checked before any output (refused with nothing written): its
        labels well formed, the run's engine source stated, and the totals the viewer's loop
        reader differences recorded with their kind and sign. Its closure is measured as the
        view is written (close_loop)."""
        loop = self.request.loop
        if loop is None:
            return None
        problems = self.problems
        if not isinstance(loop, Loop):
            problems.append("loop: a run_view.Loop")
            return None
        if not (isinstance(loop.species, str) and WORD.fullmatch(loop.species)):
            problems.append("loop: species is a word (the caller's label)")
        if loop.cell_type is not None and not (
            isinstance(loop.cell_type, str) and WORD.fullmatch(loop.cell_type)
        ):
            problems.append("loop: cell_type is a word (the caller's label), or None")
        if loop.cell is None or loop.cell not in self.sets["cell"]["ids"]:
            problems.append(f"loop: cell {loop.cell!r} is not a declared cell")
        for what in ("period", "tolerance"):
            value = getattr(loop, what)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                problems.append(f"loop: {what} is a finite number above zero")
        if loop.follows:
            problems.append(
                "loop: follows (a loop across a division) waits for the cycle's probe "
                "(docs/LOOPING_REPLAY_DESIGN.md §6): its closure is not built yet"
            )
        if self.source is None:
            problems.append(
                "loop: a looping package names its engine source, so it is written only by a "
                "shared path running from an execution snapshot (run.source)"
            )
        kept = self.request.recording.fields if self.request.recording else None
        for name in LOOP_TOTALS:
            info = self.fields.get(name)
            if info is None or info.kind != "cumulative" or info.sign is None:
                problems.append(f"loop: {name} is not a total with its kind and sign here")
            elif kept is not None and name not in kept:
                problems.append(f"loop: the recording subset leaves out {name}")
        return loop

    def close_loop(self, view, directory):
        """The loop block, from the closure measured on the run's saved files (loop_closure):
        added to `view` when the observed rows span the period and the run closes within the
        tolerance; otherwise left out, with the reason under unstated, so a run that does not
        close is never labelled a loop."""
        loop, reason = self.loop, None
        try:
            closure = loop_closure(view, directory)
        except ViewInvalid as exc:
            reason = str(exc)
        else:
            span = closure["end"] - closure["start"]
            if not math.isclose(span, loop.period, rel_tol=LOOP_SPAN_RTOL, abs_tol=0.0):
                reason = (
                    f"the observed rows span {span!r} s from {closure['start']!r} s, not the "
                    f"period {float(loop.period)!r} s"
                )
            elif closure["within"] > loop.tolerance:
                reason = (
                    f"the last observed row meets the first within {closure['within']!r}, above "
                    f"the tolerance {float(loop.tolerance)!r} (largest in {closure['record']})"
                )
        if reason is not None:
            unstated = [*view["unstated"], {"id": LOOP_KEY, "what": "loop", "why": reason}]
            view["unstated"] = sorted(unstated, key=_unstated_order)
            return view
        view[LOOP_KEY] = {
            "species": loop.species,
            **({"cell_type": loop.cell_type} if loop.cell_type is not None else {}),
            "cell": loop.cell,
            "period": float(loop.period),
            "closes": {
                "within": closure["within"],
                "says": f"the last observed row meets the first within {closure['within']:.2g} "
                f"relative (largest in {closure['record']})",
                "tolerance": float(loop.tolerance),
                "zero": closure["zero"],
            },
            "not_measured": closure["not_measured"],
        }
        return view

    # -------------------------------------------------------------- the recording subset

    def keeper(self):
        """The arrays one run saves under its view, or None when they are the run's own.

        Called on each dict of arrays a shared path saves, in order. Door S's merged view is
        added first (view_<field>, from that dict's observed rows; module docstring); then the
        recording subset (requirement 1): history fields, observed_<field> and view_<field>
        arrays keep the declared fields and elements, observation rows (and observation_times)
        every n-th from the run's first; every other array is unchanged."""
        if self.request.recording is None and not (self.recompute and self.changes):
            return None
        return _Keeper(self)

    def merged_views(self, arrays):
        """Door S (module docstring): {view_<field>: [rows, ...]} for each changed field at each
        observed row of `arrays` (a shared path's arrays, before the recording subset), re-formed
        by the composite's own host view function from the bound layout and the observed state.
        Refused where a field of the table that no change declares differs from its bound value
        at an observed row (the view would state a wrong constant)."""
        fields = self.model.STATE_TYPE._fields
        names = {VIEW_PREFIX + k: k for k in self.changes}
        clash = sorted(k for k in names if k in arrays)
        missing = sorted(k for k in fields if f"observed_{k}" not in arrays)
        if clash or missing:
            raise ViewRefused(
                "The run view cannot add the merged view: "
                + (f"arrays {clash} exist already" if clash else f"no observed state {missing}")
            )
        p = self.layout
        bound = {k: np.asarray(getattr(p, k)) for k in VIEW_FIELD_AXES if k not in self.changes}
        observed = {k: np.asarray(arrays[f"observed_{k}"]) for k in fields}
        rows, differing = {k: [] for k in self.changes}, set()
        for j in range(len(arrays["observation_times"])):
            state = self.model.STATE_TYPE(*(observed[k][j] for k in fields))
            q = self.model.view(p, state, xp=np)
            for k, values in rows.items():
                values.append(np.asarray(getattr(q, k)))
            differing |= {
                k for k, v in bound.items() if not np.array_equal(np.asarray(getattr(q, k)), v)
            }
        if differing:
            raise ViewRefused(
                f"The run view cannot be written: the view fields {sorted(differing)} differ from "
                "their bound values at an observed row, but no change of this composition "
                "declares them"
            )
        out = {}
        for name, k in names.items():
            empty = np.asarray(getattr(p, k))
            out[name] = (
                np.stack(rows[k]) if rows[k] else np.empty((0, *empty.shape), dtype=empty.dtype)
            )
        return out

    # -------------------------------------------------------------- the view

    def view(self, bases, mode, end=None):
        """The view of a run whose time bases lie in `bases` ({base: [(file, rows)]}); end: how
        it ended (end_of), when known."""
        time = []
        for base, parts in bases.items():
            array, says = BASES[base]
            start, files = 0, []
            for name, rows in parts:
                files.append({"file": name, "rows": [start, start + rows]})
                start += rows
            time.append({"id": base, "array": array, "says": says, "files": files})
        records = []
        kept = self.request.recording.fields if self.request.recording else None
        for base in bases:
            names = (
                list(self.model.STATE_AXES)
                if base == "accepted"
                else [k for k in self.model.OBSERVATION_FIELDS if k != "times"]
            )
            for name in names:
                if kept is not None and name not in kept:
                    continue
                info = self.fields[name]
                record = {
                    "id": name if base == "accepted" else f"observed_{name}",
                    "field": name,
                    "array": name if base == "accepted" else f"observed_{name}",
                    "base": base,
                    "axes": ["time", *info.axes],
                    "set": info.axes[-1] if info.axes else None,
                    "unit": info.unit,
                    "layer": info.layer,
                    "owner": info.owner,
                }
                if info.writers:
                    record["writers"] = list(info.writers)
                if info.kind is not None:
                    record["kind"] = info.kind
                if info.sign is not None:  # A flow's sign, or a difference's ends.
                    record["difference" if "plus" in info.sign else "sign"] = info.sign
                if info.diagnostic:  # RECORD_DIAGNOSTICS: held to the engine's own check.
                    record["diagnostic"] = DIAGNOSTIC_NOTE
                if info.reference is not None:  # RECORD_REFERENCES: its quantity is the sum.
                    record["reference"] = self._reference_of(
                        info.reference, self.recompute and "observation" in bases
                    )
                by = [law for law in info.writers if law in self.retiring]
                resets = bool(by) and info.owner == self.inner_id and info.kind == "cumulative"
                if resets:  # A retired slot's history moves out at its retirement.
                    record["resets"] = {"by": by, "says": RESETS_NOTE}
                    if record["set"] in SET_MASKS:
                        record["resets"]["mask"] = SET_MASKS[record["set"]]
                elif self._monotone(name):  # Seam D: its declared energy role (§6.1).
                    record["monotone"] = "non-decreasing"
                    record["note"] = HEAT_NOTE
                if not resets and info.owner == self.inner_id and name in self.notes:
                    record["note"] = self.notes[name]
                records.append(record)
            if base == "observation" and self.recompute:  # Door S: the merged view.
                for name, info in self.changes.items():
                    array = VIEW_PREFIX + name
                    if kept is not None and array not in kept:
                        continue
                    records.append(
                        {
                            "id": array,
                            "field": name,
                            "array": array,
                            "base": base,
                            "axes": ["time", *info.axes],
                            "set": info.axes[-1] if info.axes else None,
                            "unit": info.unit,
                            "layer": info.layer,
                            "owner": info.owner,
                            "writers": list(info.writers),
                            "kind": info.kind,
                            "note": VIEW_NOTE,
                        }
                    )
        unstated = list(self.unstated)
        if self.recompute and "observation" not in bases:
            unstated += [
                {
                    "id": name,
                    "what": "view field",
                    "why": f"changed by {', '.join(info.writers)}: the run saved no observed rows",
                }
                for name, info in self.changes.items()
            ]
        if end is None:
            unstated.append(
                {"id": "end", "what": "end state", "why": "the run's end state was not given"}
            )
        named = {r["reference"].get("constant") for r in records if "reference" in r}
        constants = [*self.constants, *(c for k, c in self.references.items() if k in named)]
        return {
            "format": FORMAT,
            "run": self.run | ({"end": dict(end)} if end is not None else {}),
            "time": {"unit": "s", "bases": time, "event_rows": EVENT_ROWS},
            "space": self.space,
            "layers": self.layers,
            "sets": list(self.sets.values()),
            "records": records,
            "events": self.events,
            "constants": constants,
            "unstated": sorted(unstated, key=_unstated_order),
            "recording": {"mode": mode, "subset": self.recording},
        }

    def write(self, directory, bases, mode, *, out=None, files=False, end=None):
        """Write view.json (into `out`, default `directory`, the run's folder), its structure
        checked first; with files, also against the files it names, which lie in `directory`.

        The shared paths check the structure only: their view is written after the payload and
        before the manifest, and everything else was checked before any output (prepare). A
        loop's closure is measured here, on the saved files (close_loop)."""
        value = self.view(bases, mode, end)
        if self.loop is not None:
            self.close_loop(value, Path(directory))
        validate(value, directory if files else None)
        folder = Path(out or directory)
        folder.mkdir(parents=True, exist_ok=True)  # A batch world without chunks has no folder.
        path = folder / FILE
        with path.open("x") as handle:
            handle.write(dumps(value))
        return path


class _Keeper:
    """One run's arrays as saved under its view, in the order they are saved: door S's merged
    view added from the observed rows, then the recording subset (Plan.keeper)."""

    def __init__(self, plan):
        recording = plan.request.recording
        self.plan, self.subset = plan, recording is not None
        self.fields = (
            None if recording is None or recording.fields is None else set(recording.fields)
        )
        self.every = 1 if recording is None else recording.every
        self.seen = 0
        self.views = {VIEW_PREFIX + k for k in plan.changes} if plan.recompute else set()
        infos = dict(plan.fields) | {VIEW_PREFIX + k: info for k, info in plan.changes.items()}
        self.select = {
            name: [
                (i + 1, plan.sets[s]["recorded"])
                for i, s in enumerate(info.axes)
                if "recorded" in plan.sets[s]
            ]
            for name, info in infos.items()
        }
        self.history = set(plan.model.STATE_AXES)

    def __call__(self, arrays):
        if self.views and "observation_times" in arrays:
            arrays = {**arrays, **self.plan.merged_views(arrays)}
        if not self.subset:
            return arrays
        out, rows = {}, None
        if "observation_times" in arrays:
            count = len(arrays["observation_times"])
            rows = [i for i in range(count) if (self.seen + i) % self.every == 0]
            self.seen += count
        for key, value in arrays.items():
            if key in self.views:  # Door S's merged view: an observed record of its own name.
                name, observed = key, True
            else:
                name = key[len("observed_") :] if key.startswith("observed_") else key
                observed = key.startswith("observed_") and name in self.select
            if not observed and key not in self.history:
                out[key] = value[rows] if key == "observation_times" else value
                continue
            if self.fields is not None and name not in self.fields:
                continue
            value = np.asarray(value)
            for axis, indices in self.select[name]:
                value = np.take(value, indices, axis=axis)
            out[key] = value[rows] if observed else value
        return out


def prepare(spec, request=None, *, layout, recompute=True):
    """The plan of a run's view, from the definition, declarations, caller inputs and the bound
    layout; refused (ViewRefused) before any output exists. recompute: the shared paths add door
    S's merged view to the arrays they save (False for a run already on disk)."""
    if request is not None and not isinstance(request, Request):
        raise ViewRefused("A view is requested with a run_view.Request")
    return Plan(spec, request, layout, recompute)


def requests_for(view, world_ids):
    """{world ID: Request} of a batch: one Request for every world, or a mapping that names each
    world exactly once (each world's own geometry); {} without a view."""
    if view is None:
        return {}
    if isinstance(view, Request):
        view = dict.fromkeys(world_ids, view)
    if not isinstance(view, dict) or set(view) != set(world_ids):
        raise ViewRefused("A batch's view requests name every world once: " + str(list(world_ids)))
    if any(isinstance(r, Request) and r.loop is not None for r in view.values()):
        raise ViewRefused("A looping replay package is one run, not a batch's world")
    return dict(view)


def dumps(value):
    """The view's bytes: sorted keys, no NaN, a final newline (deterministic)."""
    return json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"


def loop_selection(view):
    """The observed records a loop's closure measures, and those it leaves out by reason
    (NOT_MEASURED): ([record], [{"why", "records": [record id]}]), the groups in NOT_MEASURED's
    order and only those that hold a record."""
    measured, left = [], {key: [] for key, _ in NOT_MEASURED}
    for record in view["records"]:
        if record["base"] != "observation":
            continue
        if "diagnostic" in record:
            left["diagnostic"].append(record["id"])
        elif record.get("kind") == "cumulative":
            left["cumulative"].append(record["id"])
        elif record.get("kind") in LOOP_KINDS:
            measured.append(record)
        else:
            left["unstated"].append(record["id"])
    groups = [{"why": why, "records": left[key]} for key, why in NOT_MEASURED if left[key]]
    return measured, groups


def loop_closure(view, directory):
    """The seam of a run's observed rows (FR-11; docs/LOOPING_REPLAY_DESIGN.md §2), measured on
    the files the view names, one at a time: for every record loop_selection measures, the
    largest change between its first row and its last over the largest magnitude it takes on
    any row. A record identically zero over the loop is reported in "zero", never divided by.
    Returns {"within": the largest ratio, "record": the record attaining it, "zero",
    "not_measured" (loop_selection's groups), "start", "end": the first and last observed
    times}; ViewInvalid when there is nothing to measure."""
    bases = {b["id"]: b for b in view["time"]["bases"]}
    if "observation" not in bases:
        raise ViewInvalid("the run saved no observed rows, so no loop closure is measured")
    base = bases["observation"]
    records, not_measured = loop_selection(view)
    if not records:
        raise ViewInvalid(f"no observed record of kind {', '.join(LOOP_KINDS)} to measure")
    constants = {c["id"]: c for c in view.get("constants") or []}
    by_id = {r["id"]: r for r in view["records"]}
    sets = {s["id"]: s for s in view["sets"]}

    def quantity(record, saved):
        """The record's saved values, plus its fixed reference where it is stored as an increment
        over one (RECORD_REFERENCES): the constant, at the recorded elements, or the merged
        view's rows (door S)."""
        values = np.asarray(saved[record["array"]], dtype=float)
        reference = record.get("reference")
        if reference is None:
            return values
        if reference.get("constant") in constants:
            fixed = np.asarray(constants[reference["constant"]]["values"], dtype=float)
            for axis, set_id in enumerate(record["axes"][1:]):
                if "recorded" in sets[set_id]:
                    fixed = np.take(fixed, sets[set_id]["recorded"], axis=axis)
            return values + fixed
        if reference.get("record") in by_id:
            return values + np.asarray(saved[by_id[reference["record"]]["array"]], dtype=float)
        raise ViewInvalid(f"record {record['id']}: its reference is not saved, so not measured")

    first, last, scale, start, end = {}, {}, {}, None, None
    for part in base["files"]:
        with np.load(Path(directory) / part["file"], allow_pickle=False) as saved:
            times = np.asarray(saved[base["array"]], dtype=float)
            if not len(times):
                continue
            start = float(times[0]) if start is None else start
            end = float(times[-1])
            for record in records:
                values = quantity(record, saved)
                key = record["id"]
                first.setdefault(key, values[0])
                last[key] = values[-1]
                top = np.max(np.abs(values), initial=0.0)  # NaN propagates.
                scale[key] = float(np.max([scale.get(key, 0.0), top]))
    if start is None:
        raise ViewInvalid("the run saved no observed rows, so no loop closure is measured")
    within, worst, zero = 0.0, None, []
    for record in records:
        key = record["id"]
        change = float(np.max(np.abs(last[key] - first[key]), initial=0.0))
        if not (math.isfinite(change) and math.isfinite(scale[key])):
            raise ViewInvalid(f"record {key} is not finite on its observed rows")
        if scale[key] == 0.0:  # Identically zero: it meets itself, stated rather than divided.
            zero.append(key)
            continue
        ratio = change / scale[key]
        if worst is None or ratio > within:
            within, worst = ratio, key
    if worst is None:
        raise ViewInvalid("every measured record is identically zero over the loop")
    return {
        "within": within,
        "record": worst,
        "zero": zero,
        "not_measured": not_measured,
        "start": start,
        "end": end,
    }


# ------------------------------------------------------------------ the shared paths' parts


def single_file_bases(times, observation_times, *, file="trajectory.npz"):
    """io.write_run's time bases: one file holds both (a base with no rows is left out)."""
    counts = {"accepted": len(times), "observation": len(observation_times)}
    return {base: [(file, count)] for base, count in counts.items() if count}


def window_bases(index, *, world_id=None, prefix=""):
    """A windowed run's time bases from its index (windows.jsonl): one part per chunk, with the
    rows the index counts (never by reopening the chunks). For a batch world, the lines of that
    world, with paths relative to its folder `prefix`."""
    bases = {"accepted": [], "observation": []}
    with Path(index).open() as handle:
        for line in handle:
            entry = json.loads(line)
            if entry["kind"] not in ("window", "world_window") or entry["path"] is None:
                continue
            if world_id is not None and entry.get("world_id") != world_id:
                continue
            path = entry["path"]
            if prefix:
                if not path.startswith(prefix + "/"):
                    raise ViewRefused(f"chunk {path} lies outside {prefix}")
                path = path[len(prefix) + 1 :]
            for base, count in (
                ("accepted", entry["accepted_records"]),
                ("observation", entry["observation_records"]),
            ):
                if count:
                    bases[base].append((path, count))
    return {base: parts for base, parts in bases.items() if parts}


def saved_layout(directory):
    """The bound layout of a saved run, from its final checkpoint (state and layout arrays)."""
    with np.load(Path(directory) / "checkpoint_final" / "state.npz", allow_pickle=False) as saved:
        return {k: saved[k] for k in saved.files}


def write_view(directory, spec=None, *, out=None, run=None, geometry=None, bases=None, mode=None):
    """Write the view of a run already on disk (written by a shared output path).

    directory: the run's folder (resolved_config.json with trajectory.npz, or windows.jsonl);
    spec: its definition, read from resolved_config.json when not given; out: where to write
    view.json (default: beside the run). Paths in the view are relative to the run's folder.
    A world of batch_io.write_batch_run is such a folder; a world of a windowed batch is not
    (its index and checkpoints are the batch's): its view is written by the run itself."""
    from cells.definitions.specs import parse_spec, read_json

    directory = Path(directory)
    if spec is None:
        spec = parse_spec(read_json(directory / "resolved_config.json"))
    if bases is None:
        if (directory / "trajectory.npz").exists():
            with np.load(directory / "trajectory.npz", allow_pickle=False) as saved:
                bases = single_file_bases(saved["accepted_times"], saved["observation_times"])
            mode = mode or "write_run"
        elif (directory / "windows.jsonl").exists():
            bases = window_bases(directory / "windows.jsonl")
            manifest = read_json(directory / "manifest.json")
            mode = mode or manifest["policy"]["recording"]
        else:
            raise ViewRefused(f"{directory} holds no run written by a shared output path")
    plan = prepare(
        spec, Request(run or {}, geometry), layout=saved_layout(directory), recompute=False
    )
    end = None
    if (directory / "summary.json").exists():  # The run's own summary says how it ended.
        summary = read_json(directory / "summary.json")
        if {"status", "end_time", "global_step_index"} <= set(summary):
            end = {
                "status": summary["status"],
                "time": float(summary["end_time"]),
                "step": int(summary["global_step_index"]),
            }
    return plan.write(directory, bases, mode or "write_run", out=out, files=True, end=end)


# ------------------------------------------------------------------ the reader's check


def _check(condition, problems, message):
    if not condition:
        problems.append(message)
    return condition


def _shape_of(values):
    array = np.asarray(values, dtype=object)
    return array.shape


def validate(view, directory=None):
    """The reader's check of a view (ViewInvalid with every problem found); with the run's
    folder, also every file, array, shape and time base it names, and every heat record's
    monotonicity."""
    problems = []
    if not _check(isinstance(view, dict), problems, "a view is a JSON object"):
        raise ViewInvalid("; ".join(problems))
    _check(
        TOP_KEYS <= set(view) <= TOP_KEYS | {LOOP_KEY},
        problems,
        f"top-level keys are {sorted(TOP_KEYS)}, and optionally {LOOP_KEY}",
    )
    _check(view.get("format") == FORMAT, problems, f"format is {FORMAT}")
    run = view.get("run") or {}
    _check(isinstance(run.get("model"), str), problems, "run names its model")
    models = run.get("engine_models")
    _check(
        isinstance(models, list)
        and models
        and all(isinstance(m, str) and "@" in m for m in models),
        problems,
        "run lists its engine models, each a versioned ID",
    )
    _check(
        isinstance(run.get("definition_sha256"), str)
        and re.fullmatch("[0-9a-f]{64}", run["definition_sha256"]) is not None,
        problems,
        "run gives its definition's fingerprint",
    )
    _check(run.get("scale") in SCALES, problems, f"run scale is one of {SCALES}")
    for key, kind in RUN_KEYS.items():
        if key in run:
            _check(type(run[key]) is kind, problems, f"run {key} is a {kind.__name__}")
    if "end" in run:
        end = run["end"]
        _check(
            isinstance(end, dict)
            and set(end) == {"status", "time", "step"}
            and isinstance(end["status"], str)
            and isinstance(end["time"], (int, float))
            and math.isfinite(end["time"])
            and type(end["step"]) is int,
            problems,
            "run end gives its status, time and step",
        )
    if "source" in run:
        source = run["source"]
        _check(
            isinstance(source, dict)
            and set(source) == {"revision", "dirty", "from"}
            and isinstance(source["revision"], str)
            and source["revision"]
            and type(source["dirty"]) is bool,
            problems,
            "run source gives the engine's revision, whether it was dirty, and where from",
        )
    layers = view.get("layers") or []
    layer_ids = [layer.get("id") for layer in layers]
    _check(len(set(layer_ids)) == len(layer_ids), problems, "layer ids are unique")
    for layer in layers:
        _check(
            set(layer) == {"id", "label", "representation", "owner"}
            and all(isinstance(layer[k], str) and layer[k] for k in ("id", "label", "owner"))
            and layer["representation"] in REPRESENTATIONS,
            problems,
            f"layer {layer.get('id')!r}: id, label, owner and a representation of "
            f"{REPRESENTATIONS} (never null)",
        )
    sets = {s.get("id"): s for s in view.get("sets") or []}
    _check(len(sets) == len(view.get("sets") or []), problems, "set ids are unique")
    sizes = {}
    for set_id, s in sets.items():
        ids = s.get("ids")
        if not _check(
            isinstance(ids, list) and all(i is None or isinstance(i, str) for i in ids),
            problems,
            f"set {set_id}: ids are strings or null (padding)",
        ):
            continue
        named = [i for i in ids if i is not None]
        _check(len(set(named)) == len(named), problems, f"set {set_id}: ids are unique")
        _check(s.get("scale") in SCALES, problems, f"set {set_id}: scale is one of {SCALES}")
        sizes[set_id] = len(ids)
        for key in (
            "lifetimes",
            "laws",
            "pumps",
            "calcium_pumps",
            "reservoir",
            "valence",
            "species",
            "factors",
            *PER_ENTITY,
        ):
            if key in s:
                _check(len(s[key]) == len(ids), problems, f"set {set_id}: {key} has one per id")
        if "kinds" in s:  # Kinds are words; a law's versioned ID goes under laws (docstring).
            _check(
                all(isinstance(k, str) and "@" not in k for k in s["kinds"]),
                problems,
                f"set {set_id}: its kinds are words, never a versioned ID (that goes under laws)",
            )
        if "roles" in s:
            roles = s["roles"]
            _check(
                isinstance(roles, dict)
                and roles
                and all(
                    isinstance(k, str) and isinstance(v, str) and k and v for k, v in roles.items()
                ),
                problems,
                f"set {set_id}: its roles name what each role is",
            )
        if "recorded" in s:
            _check(
                all(isinstance(i, int) and 0 <= i < len(ids) and ids[i] for i in s["recorded"]),
                problems,
                f"set {set_id}: recorded entities are declared ones",
            )
    space = view.get("space")
    if space is not None:
        _check(
            set(space) == {"unit", "dimensions", "representation", "source"}
            and space["unit"] in LENGTH_UNITS
            and space["dimensions"] in (2, 3)
            and space["representation"] in REPRESENTATIONS,
            problems,
            "space gives a length unit, 2 or 3 dimensions, a representation and a source",
        )
    species = (sets.get("species") or {}).get("ids") or []
    for set_id, s in sets.items():
        _validate_geometry(set_id, s, sets, sizes, space, problems)
        if "carries" in s:
            _check(
                all(_species_of(c, species) for c in s["carries"]),
                problems,
                f"set {set_id}: carries the model's species",
            )
        if "at" in s:
            _check(
                all(
                    isinstance(a, dict)
                    and len(a) == 1
                    and next(iter(a)) in sets
                    and next(iter(a.values())) in (sets[next(iter(a))].get("ids") or [])
                    for a in s["at"]
                ),
                problems,
                f"set {set_id}: each acts at one declared entity",
            )
        if set_id == "membrane" and "outside" in s:
            index = s["outside"].get("index", [])
            _check(
                s["outside"].get("set") == "outside"
                and len(index) == sizes.get(set_id)
                and all(i is None or 0 <= i < sizes.get("outside", 0) for i in index),
                problems,
                "membrane: each faces one outside node",
            )
    time = view.get("time") or {}
    _check(time.get("unit") == "s", problems, "time is in s")
    if "event_rows" in time:
        _check(
            isinstance(time["event_rows"], str) and time["event_rows"],
            problems,
            "time: event_rows says which row holds an event's time",
        )
    bases = {}
    for base in time.get("bases") or []:
        files = base.get("files") or []
        start = 0
        for part in files:
            rows = part.get("rows")
            _check(
                isinstance(part.get("file"), str)
                and not part["file"].startswith("/")
                and ".." not in Path(part["file"]).parts
                and isinstance(rows, list)
                and len(rows) == 2
                and rows[0] == start
                and rows[1] > rows[0],
                problems,
                f"time base {base.get('id')}: files hold contiguous rows from 0, at relative paths",
            )
            start = rows[1] if isinstance(rows, list) and len(rows) == 2 else start
        bases[base.get("id")] = base
    _check(set(bases) <= set(BASES), problems, f"time bases are of {sorted(BASES)}")
    record_ids = [r.get("id") for r in view.get("records") or []]
    _check(len(set(record_ids)) == len(record_ids), problems, "record ids are unique")
    for record in view.get("records") or []:
        rid, axes = record.get("id"), record.get("axes") or []
        _check(
            {"id", "field", "array", "base", "axes", "set", "unit", "layer", "owner"} <= set(record)
            and record.get("base") in bases
            and axes[:1] == ["time"]
            and all(a in sets for a in axes[1:])
            and record.get("set") == (axes[-1] if len(axes) > 1 else None)
            and isinstance(record.get("unit"), str)
            and record.get("unit")
            and record.get("layer") in layer_ids
            and isinstance(record.get("owner"), str),
            problems,
            f"record {rid}: a time base, axes from time over known sets, a unit, a layer, an owner",
        )
        if "kind" in record:
            _check(record["kind"] in KINDS, problems, f"record {rid}: kind is one of {KINDS}")
        if "diagnostic" in record:
            _check(
                isinstance(record["diagnostic"], str) and record["diagnostic"],
                problems,
                f"record {rid}: a diagnostic says what it is",
            )
        if "reference" in record:
            reference = record["reference"]
            constants = {c.get("id") for c in view.get("constants") or []}
            ids = {r.get("id") for r in view.get("records") or []}
            # A field reference (door S's merged view, not saved) names a field the view leaves
            # unstated, with the reason (§9's item 3).
            unstated = {u.get("id") for u in view.get("unstated") or [] if isinstance(u, dict)}
            _check(
                isinstance(reference, dict)
                and len(reference) == 1
                and (
                    reference.get("constant") in constants
                    or reference.get("record") in ids
                    or (isinstance(reference.get("field"), str) and reference["field"] in unstated)
                ),
                problems,
                f"record {rid}: its reference is a constant, a record, or a field the view "
                "leaves unstated (with the reason)",
            )
        if "resets" in record:
            resets = record["resets"]
            _check(
                isinstance(resets, dict)
                and {"by", "says"} <= set(resets) <= {"by", "says", "mask"}
                and resets["by"]
                and all(isinstance(law, str) and "@" in law for law in resets["by"])
                and resets.get("mask", "active") in SET_MASKS.values()
                and "monotone" not in record,
                problems,
                f"record {rid}: resets names the retiring laws (and a mask), and claims no "
                "monotonicity",
            )
        roles = (sets.get(record.get("set")) or {}).get("roles") or {}
        for key, ends in (("sign", FLOW_KEYS), ("difference", DIFFERENCE_KEYS)):
            if key not in record:
                continue
            given = record[key]
            _check(
                isinstance(given, dict)
                and all(given.get(e) in roles for e in ends)
                and given[ends[0]] != given[ends[1]]
                and isinstance(given.get("says"), str),
                problems,
                f"record {rid}: its {key} names two roles of its set and says what positive means",
            )
    for event in view.get("events") or []:
        ok = (
            isinstance(event.get("time"), (int, float))
            and math.isfinite(event["time"])
            and isinstance(event.get("kind"), str)
            and event.get("layer") in layer_ids
            and isinstance(event.get("label"), str)
        )
        for part in ("at", "from"):
            if part in event or part == "at":
                entity = event.get(part)
                ok = ok and isinstance(entity, dict) and len(entity) == 1
                if ok:
                    ((set_id, entity_id),) = entity.items()
                    ok = set_id in sets and entity_id in sets[set_id]["ids"] and entity_id
        _check(ok, problems, f"event {event}: time, kind, layer, label and entities by known id")
    times = [e.get("time") for e in view.get("events") or []]
    _check(times == sorted(times, key=float), problems, "events are in time order")
    for constant in view.get("constants") or []:
        axes = constant.get("axes", [])
        shape = tuple(sizes.get(a, -1) for a in axes)
        _check(
            all(a in sets for a in axes)
            and isinstance(constant.get("unit"), str)
            and _shape_of(constant.get("values")) == shape,
            problems,
            f"constant {constant.get('id')}: values run along its sets",
        )
    for item in view.get("unstated") or []:
        _check(set(item) == {"id", "what", "why"}, problems, "an unstated item has id, what, why")
    if LOOP_KEY in view:
        _validate_loop(view[LOOP_KEY], run, sets, bases, set(record_ids), problems)
    if directory is not None and not problems:
        _validate_files(view, Path(directory), sets, sizes, problems)
    if problems:
        raise ViewInvalid("Invalid run view: " + "; ".join(problems))


def _positive(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def _validate_loop(loop, run, sets, bases, record_ids, problems):
    """A loop block's shape (FR-11): the caller's species word and declared cell, the period,
    the closure within its tolerance with what it says and the records identically zero, the
    records it leaves out by reason, any cells followed, and the run's engine source and observed
    rows, which a loop needs."""
    cells = [c for c in (sets.get("cell") or {}).get("ids") or [] if c is not None]
    closes = loop.get("closes") if isinstance(loop, dict) else None
    _check(
        isinstance(loop, dict)
        and {"species", "cell", "period", "closes", "not_measured"} <= set(loop) <= LOOP_KEYS
        and isinstance(loop["species"], str)
        and WORD.fullmatch(loop["species"]) is not None
        and (
            "cell_type" not in loop
            or (isinstance(loop["cell_type"], str) and WORD.fullmatch(loop["cell_type"]))
        )
        and loop["cell"] in cells
        and _positive(loop["period"])
        and isinstance(closes, dict)
        and set(closes) == {"within", "says", "tolerance", "zero"}
        and isinstance(closes["within"], (int, float))
        and math.isfinite(closes["within"])
        and 0 <= closes["within"]
        and _positive(closes["tolerance"])
        and closes["within"] <= closes["tolerance"]
        and isinstance(closes["says"], str)
        and closes["says"]
        and isinstance(closes["zero"], list)
        and all(r in record_ids for r in closes["zero"]),
        problems,
        "loop: a species word, a declared cell, a period, and a closure within its tolerance that "
        "says what it measures and names the records identically zero",
    )
    left = loop.get("not_measured") if isinstance(loop, dict) else None
    _check(
        isinstance(left, list)
        and all(
            isinstance(group, dict)
            and set(group) == {"why", "records"}
            and isinstance(group["why"], str)
            and group["why"]
            and isinstance(group["records"], list)
            and group["records"]
            and all(r in record_ids for r in group["records"])
            for group in left
        ),
        problems,
        "loop: the records left out of its closure, by name, each group with its reason",
    )
    follows = loop.get("follows", []) if isinstance(loop, dict) else []
    _check(
        isinstance(follows, list)
        and all(
            isinstance(f, dict)
            and set(f) == {"time", "from", "to"}
            and isinstance(f["time"], (int, float))
            and math.isfinite(f["time"])
            and f["from"] in cells
            and f["to"] in cells
            and f["from"] != f["to"]
            for f in follows
        ),
        problems,
        "loop: each cell followed has a time and two declared cells",
    )
    _check(
        "source" in run and "observation" in bases,
        problems,
        "loop: the run names its engine source and saves its observed rows",
    )


def _validate_geometry(set_id, s, sets, sizes, space, problems):
    geometry = s.get("geometry")
    if geometry is None:
        return
    kind, n = geometry.get("kind"), sizes.get(set_id, 0)
    if not _check(
        kind in GEOMETRY_KINDS, problems, f"set {set_id}: geometry kind of {GEOMETRY_KINDS}"
    ):
        return
    if kind in ("on", "links"):
        target = geometry.get("set") if kind == "on" else geometry.get("between")
        values = geometry.get("index") if kind == "on" else geometry.get("ends")
        m = sizes.get(target, -1)
        flat = [
            v
            for item in values or []
            if item is not None
            for v in ([item] if kind == "on" else item)
        ]
        _check(
            target in sets
            and isinstance(values, list)
            and len(values) == n
            and all(isinstance(v, int) and 0 <= v < m for v in flat)
            and (kind == "on" or all(item is None or len(item) == 2 for item in values)),
            problems,
            f"set {set_id}: its {kind} geometry indexes set {target}",
        )
        return
    if not _check(space is not None, problems, f"set {set_id}: coordinates need a space"):
        return
    d = space["dimensions"]
    if kind in ("points", "spheres"):
        centres = geometry.get("centres") or []
        _check(
            len(centres) == n
            and all(
                c is None or (len(c) == d and all(math.isfinite(x) for x in c)) for c in centres
            )
            and (kind == "points" or "radius" in geometry),
            problems,
            f"set {set_id}: {kind} give one {d}-vector centre per id (null for padding)",
        )
    else:
        vertices, faces = geometry.get("vertices") or [], geometry.get("faces") or []
        _check(
            all(len(v) == d for v in vertices)
            and len(faces) == n
            and all(
                f is None or (len(f) >= 3 and all(0 <= i < len(vertices) for i in f)) for f in faces
            ),
            problems,
            f"set {set_id}: polygons give one face per id over {d}-vector vertices",
        )


def _npz_shapes(path):
    """{array: shape} of an npz archive, from the arrays' headers, without reading their data."""
    readers = {
        (1, 0): np.lib.format.read_array_header_1_0,
        (2, 0): np.lib.format.read_array_header_2_0,
    }
    shapes = {}
    with zipfile.ZipFile(path) as archive:
        for member in archive.namelist():
            if not member.endswith(".npy"):
                continue
            with archive.open(member) as stream:
                version = np.lib.format.read_magic(stream)
                if version not in readers:
                    raise ViewInvalid(f"{path.name}: {member} has npy format {version}")
                shapes[member[: -len(".npy")]] = readers[version](stream)[0]
    return shapes


def _validate_files(view, directory, sets, sizes, problems):
    """Every file a time base names, one at a time: its time array (finite, increasing across
    files), each record's shape from the arrays' headers, and the data of the heat records that
    claim monotonicity, carrying only their last row from file to file."""
    for base in view["time"]["bases"]:
        records = [r for r in view["records"] if r["base"] == base["id"]]
        shapes = {
            r["id"]: tuple(
                len(sets[a]["recorded"]) if "recorded" in sets[a] else sizes[a]
                for a in r["axes"][1:]
            )
            for r in records
        }
        monotone = [r for r in records if r.get("monotone") == "non-decreasing"]
        last_time, last_rows = None, {}
        for part in base["files"]:
            name, rows = part["file"], part["rows"][1] - part["rows"][0]
            path = directory / name
            if not _check(path.is_file(), problems, f"{name} does not exist"):
                continue
            held = _npz_shapes(path)
            missing = [a for a in (base["array"], *(r["array"] for r in records)) if a not in held]
            if not _check(not missing, problems, f"{name} holds no array {missing[:3]}"):
                continue
            _check(held[base["array"]] == (rows,), problems, f"{name}: {base['array']} rows")
            for record in records:
                _check(
                    held[record["array"]] == (rows, *shapes[record["id"]]),
                    problems,
                    f"{name}: {record['array']} has shape {held[record['array']]}, its view "
                    f"{(rows, *shapes[record['id']])}",
                )
            if problems:
                continue
            with np.load(path, allow_pickle=False) as archive:
                times = archive[base["array"]]
                joined = times if last_time is None else np.concatenate(([last_time], times))
                _check(
                    np.all(np.isfinite(times)) and np.all(np.diff(joined) > 0),
                    problems,
                    f"time base {base['id']}: finite and increasing ({name})",
                )
                last_time = times[-1]
                for record in monotone:
                    value = archive[record["array"]]
                    before = last_rows.get(record["id"])
                    joined = value if before is None else np.concatenate((before, value))
                    _check(
                        np.all(value >= -1e-12) and np.all(np.diff(joined, axis=0) >= -1e-12),
                        problems,
                        f"record {record['id']}: zero or more and never falling ({name})",
                    )
                    last_rows[record["id"]] = value[-1:].copy()
    if LOOP_KEY in view and not problems:  # The stated closure is the one its files give.
        loop = view[LOOP_KEY]
        try:
            closure = loop_closure(view, directory)
        except ViewInvalid as exc:
            problems.append(f"loop: {exc}")
            return
        span = closure["end"] - closure["start"]
        _check(
            closure["within"] == loop["closes"]["within"]
            and closure["zero"] == loop["closes"]["zero"]
            and closure["not_measured"] == loop["not_measured"]
            and math.isclose(span, loop["period"], rel_tol=LOOP_SPAN_RTOL, abs_tol=0.0),
            problems,
            "loop: its closure is the one measured on its files, over exactly one period",
        )
