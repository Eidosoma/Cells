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

Scope (version 1): resolved_pump_composite@1 over resolved_pump_tissue@3, and @3 alone. Other
model families are refused.

Declarations read, and their interim stand-ins
---------------------------------------------
* The inner model's units, readout axes, kinds, orientations and layers: its own ``UNITS``,
  ``OBSERVATION_AXES``, ``RECORD_KINDS``, ``ORIENTATION``, ``RECORD_LAYERS`` and ``VIEW_LAYERS``
  when it declares them; until then this module's table for resolved_pump_tissue@3 (TISSUE_3),
  pending the core owner's declaration. A field of the model that no declaration describes (a
  kind's new field, say) is refused, never guessed.
* Each operator: ``VIEW_LAYERS`` (the contract; None is refused), ``view_events`` (the contract,
  where the operator overrides it) and ``living_intervals`` (births and retirements); and, read by
  getattr until the contract carries them: ``view_sets(spec, declaration)`` for its own axes,
  ``OBSERVATION_AXES`` for its readout columns, ``UNITS`` for names without a unit suffix,
  ``RECORD_KINDS``, ``ORIENTATION`` and ``RECORD_LAYERS``. Without a declared kind, a field the
  contract books as heat or work (HEAT_FIELDS, WORK_FIELDS) is cumulative; any other is listed as
  unstated.
* Retirement: where an operator RETIRES slots, a retired slot's inner history moves into that
  operator's own record at its retirement (the composite's checks add it back), so the inner
  ledgers it writes (the field map's writers) restart at zero there on the saved arrays. Their
  records say so (``resets``) and claim no monotonicity; every other ``*_dissipated_energy_pJ``
  record is ``monotone`` (on S5's division the fallen heat ledgers were exactly those).
* Owners: the composition's field map (state owners, observation owner chains: the last).
* Laws (requirement 4): each channel population's, junction's and pump's law from the structure
  record's law declarations (models/inner_laws.py), with its provenance; membranes and faces carry
  their passive route law, whose provenance is not declared.
* Pumps (requirement 6) are columns of the membrane set: each membrane entry gives its pump's law
  and rows per cycle by role (inward-positive), from the law's declaration.
* Species (requirement 7): identities from core/species_registry.identities, with each declared
  standard potential and background.
* View fields (requirement 5): a field of the inner layout that operators may provide is a named
  constant of the definition (its bound value) where no operator of the composition changes it.
  Where one does, the run saves no merged view of it today, so it is listed as unstated, naming
  the operators (recording the observe stage's merged view is a requested seam).

Records and time bases
----------------------
Records are the run's time-based arrays: the state history (``<field>`` on the base
``accepted``) and the observations (``observed_<field>`` on the base ``observation``). A record's
id is its array name; ``field`` is the engine's field name. Each time base lists the files that
hold it, one entry per file with the rows it holds (requirement 8): one file for io.write_run,
one per window chunk for the windowed paths, read from the run's own index. Every record on a
base lies in those files at those rows. The layout arrays of trajectory.npz are the definition's
bound values, not records.

Orientation (requirement 2): ``sign`` gives ``from`` and ``to`` by the roles of the record's
entity set: membrane and channel records ``inside`` (the patch's cell) and ``outside`` (its
outside node); junction and face records ``sender`` and ``receiver`` (the set's link ends, in
order); outside-node records ``exterior`` (beyond the world) and ``node``. A positive value moves
from ``from`` to ``to``.
"""

import json
import math
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

import numpy as np

from cells.core.specs import ConfigError

FORMAT = "cells.run_view@1"
FILE = "view.json"
REPRESENTATIONS = ("simulated", "modelled", "prescribed")
KINDS = ("level", "amount", "cumulative", "rate")
SCALES = ("molecule", "cell", "tissue", "organ", "organism")
GEOMETRY_KINDS = ("points", "polygons", "links", "on", "spheres")
LENGTH_UNITS = ("m", "mm", "um", "nm")
RUN_KEYS = {"experiment": str, "arm": str, "seed": int, "revision": str, "label": str}
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
HEAT_SUFFIX = "_dissipated_energy_pJ"
RESETS_NOTE = (
    "Written at the events of these operators, which retire slots: a retired slot's history in "
    "this ledger moves into the retiring operator's own record (the composite's checks add it "
    "back), so on that slot it restarts at zero. A difference across such an event is the "
    "operator's booking, not this ledger's flow; a heat total only grows with that record added "
    "back."
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
# Roles a sign may name, by the record's entity set.
SIGN_ROLES = {
    "membrane": ("inside", "outside"),
    "channel": ("inside", "outside"),
    "junction": ("sender", "receiver"),
    "face": ("sender", "receiver"),
    "outside": ("exterior", "node"),
}
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


# ------------------------------------------------------------------ the inner model's table

# resolved_pump_tissue@3, until its own declarations land (the core's files; a requested seam).
# Each readout's axes, every field's unit where its name has no suffix, every field's kind and
# layer, and the orientations the core's owner confirmed on 15 November 2026 (the lead's
# requirement 2). State axes are the model's own STATE_AXES.
_CONFIRMED = "the core's owner, 15 November 2026"
_OUTWARD = MappingProxyType(
    {
        "from": "inside",
        "to": "outside",
        "says": "a positive amount leaves the patch's cell for its outside node",
        "confirmed": _CONFIRMED,
    }
)
_CHANNEL = MappingProxyType(
    {
        "from": "inside",
        "to": "outside",
        "says": "a positive amount leaves the cell of the population's patch for that patch's "
        "outside node (added unchanged into the patch's membrane total)",
        "confirmed": _CONFIRMED,
    }
)
_JUNCTION = MappingProxyType(
    {
        "from": "sender",
        "to": "receiver",
        "says": "a positive amount leaves the junction's sender cell for its receiver",
        "confirmed": _CONFIRMED,
    }
)
_FACE = MappingProxyType(
    {
        "from": "sender",
        "to": "receiver",
        "says": "a positive amount leaves the face's sender node for its receiver",
        "confirmed": _CONFIRMED,
    }
)
_PUMP = MappingProxyType(
    {
        "from": "outside",
        "to": "inside",
        "says": "pump cycles are inward-positive: a positive cycle moves each moved row's "
        "per-cycle count (the membrane set's pumps, by role) from the patch's outside node into "
        "its cell; the balance subtracts stoichiometry times cycles from the membrane total",
        "confirmed": _CONFIRMED,
    }
)
_SUPPLY = MappingProxyType(
    {
        "from": "exterior",
        "to": "node",
        "says": "a positive amount is supplied into the held outside node from beyond the world",
        "confirmed": _CONFIRMED,
    }
)
TISSUE_3_LAYERS = (
    {"id": "membrane", "label": "Membrane voltage and ions", "representation": "simulated"},
    {
        "id": "channels",
        "label": "Channel populations and junction gates",
        "representation": "modelled",
    },
    {"id": "pumps", "label": "Pump populations", "representation": "modelled"},
)
# field: (readout axes or None for a state field, unit or None for the suffix rule, kind, layer,
# sign or None).
TISSUE_3 = MappingProxyType(
    {
        # State.
        "amount_increment": (None, "fmol", "amount", "membrane", None),
        "extracellular_amount_increment": (None, "fmol", "amount", "membrane", None),
        "membrane_transferred": (None, "fmol", "cumulative", "membrane", _OUTWARD),
        "junction_transferred": (None, "fmol", "cumulative", "membrane", _JUNCTION),
        "face_transferred": (None, "fmol", "cumulative", "membrane", _FACE),
        "reservoir_supplied": (None, "fmol", "cumulative", "membrane", _SUPPLY),
        "membrane_dissipated_energy_pJ": (None, None, "cumulative", "membrane", None),
        "junction_dissipated_energy_pJ": (None, None, "cumulative", "membrane", None),
        "face_dissipated_energy_pJ": (None, None, "cumulative", "membrane", None),
        "electrode_charge_transferred_C": (None, None, "cumulative", "membrane", None),
        "reservoir_work_pJ": (None, None, "cumulative", "membrane", None),
        "electrode_work_pJ": (None, None, "cumulative", "membrane", None),
        "channel_gate": (None, "1", "level", "channels", None),
        "channel_transferred": (None, "fmol", "cumulative", "channels", _CHANNEL),
        "channel_dissipated_energy_pJ": (None, None, "cumulative", "channels", None),
        "junction_gate": (None, "1", "level", "channels", None),
        "pump_cycles": (None, "fmol", "cumulative", "pumps", _PUMP),
        "pump_dissipated_energy_pJ": (None, None, "cumulative", "pumps", None),
        "metabolic_work_pJ": (None, None, "cumulative", "pumps", None),
        "calcium_pump_cycles": (None, "fmol", "cumulative", "pumps", _PUMP),
        "calcium_pump_dissipated_energy_pJ": (None, None, "cumulative", "pumps", None),
        "calcium_metabolic_work_pJ": (None, None, "cumulative", "pumps", None),
        # Readouts.
        "amount": (("species", "cell_slot"), "fmol", "amount", "membrane", None),
        "extracellular_amount": (
            ("species", "extracellular_slot"),
            "fmol",
            "amount",
            "membrane",
            None,
        ),
        "cell_potential_V": (("cell_slot",), None, "level", "membrane", None),
        "extracellular_potential_V": (("extracellular_slot",), None, "level", "membrane", None),
        "membrane_voltage_V": (("membrane_slot",), None, "level", "membrane", None),
        "junction_voltage_V": (("edge_slot",), None, "level", "membrane", None),
        "membrane_flux_fmol_s": (("species", "membrane_slot"), None, "rate", "membrane", None),
        "junction_flux_fmol_s": (("species", "edge_slot"), None, "rate", "membrane", None),
        "face_flux_fmol_s": (("species", "face_slot"), None, "rate", "membrane", None),
        "reservoir_supply_fmol_s": (
            ("species", "extracellular_slot"),
            None,
            "rate",
            "membrane",
            None,
        ),
        "electrode_charge_C": (("extracellular_slot",), None, "amount", "membrane", None),
        "electrode_current_A": (("extracellular_slot",), None, "rate", "membrane", None),
        "reservoir_power_pJ_s": (("world",), None, "rate", "membrane", None),
        "electrode_power_pJ_s": (("world",), None, "rate", "membrane", None),
        "charge_residual_C": (("field_node",), None, "level", "membrane", None),
        "component_current_residual_A": (("floating_component",), None, "rate", "membrane", None),
        "energy_balance_pJ_s": (("world",), None, "rate", "membrane", None),
        "membrane_availability": (("membrane_slot",), "1", "level", "membrane", None),
        "junction_availability": (("edge_slot",), "1", "level", "channels", None),
        "channel_flux_fmol_s": (("species", "channel_slot"), None, "rate", "channels", None),
        "channel_targets": (("gate", "channel_slot"), "1", "level", "channels", None),
        "channel_tau_s": (("gate", "channel_slot"), None, "level", "channels", None),
        "pump_cycle_rate_fmol_s": (("membrane_slot",), None, "rate", "pumps", None),
        "pump_affinity_J_mol": (("membrane_slot",), None, "level", "pumps", None),
        "metabolic_power_pJ_s": (("membrane_slot",), None, "rate", "pumps", None),
        "channel_availability": (("channel_slot",), "1", "level", "channels", None),
        "pump_availability": (("membrane_slot",), "1", "level", "pumps", None),
        "calcium_pump_cycle_rate_fmol_s": (("membrane_slot",), None, "rate", "pumps", None),
        "calcium_pump_affinity_J_mol": (("membrane_slot",), None, "level", "pumps", None),
        "calcium_metabolic_power_pJ_s": (("membrane_slot",), None, "rate", "pumps", None),
        "calcium_pump_availability": (("membrane_slot",), "1", "level", "pumps", None),
    }
)
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
# Notes a record carries (the model's own words where it states them: its summary's
# membrane_transfer_ledger).
TISSUE_3_NOTES = MappingProxyType(
    {
        "membrane_transferred": "the passive membrane routes only: each channel population's and "
        "each pump's transfers are their own ledgers (channel_transferred, pump_cycles)",
    }
)
INNER_TABLES = MappingProxyType(
    {"resolved_pump_tissue@3": (TISSUE_3, TISSUE_3_LAYERS, TISSUE_3_NOTES)}
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
class Request:
    """The caller's part of a view: run labels, geometry and a recording subset."""

    run: dict = field(default_factory=dict)
    geometry: Geometry | None = None
    recording: Recording | None = None


# ------------------------------------------------------------------ helpers


def _refuse(problems):
    if problems:
        raise ViewRefused("The run view cannot be written: " + "; ".join(problems))


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
    from cells.core import pump_composite_spec

    return pump_composite_spec


def _family(spec):
    """(model, inner model ID, operator entries) of a definition in the view's scope."""
    from cells.core import surface_pump_v3_spec as tissue3
    from cells.models.registry import get_model

    composite = _composite_spec()
    if isinstance(spec.model, composite.CompositeModel):
        if spec.model.inner_model not in INNER_TABLES:
            raise ViewRefused(f"No view declarations for inner model {spec.model.inner_model}")
        return get_model(spec.model), spec.model.inner_model, composite.entries(spec)
    if isinstance(spec.model, tissue3.SurfacePumpChannelModel):
        return get_model(spec.model), tissue3.MODEL_ID, ()
    raise ViewRefused(
        f"No view declarations for {type(spec.model).__name__}: version 1 covers "
        "resolved_pump_composite@1 over resolved_pump_tissue@3, and resolved_pump_tissue@3"
    )


def _inner(model):
    return getattr(model, "inner", model)


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


class Plan:
    """Everything the view states that does not depend on the saved files, checked before any
    output exists (prepare). The shared paths keep its recording subset (keeper) and write the
    view from it (write)."""

    def __init__(self, spec, request, layout):
        self.spec, self.request = spec, request or Request()
        self.model, self.inner_id, self.entries = _family(spec)
        self.problems, self.unstated = [], []
        self.retiring = tuple(op.LAW_ID for op, _, _ in self.entries if op.RETIRES)
        table, inner_layers, notes = INNER_TABLES[self.inner_id]
        inner = _inner(self.model)
        self.inner_table, self.notes = table, notes
        self.layers = [
            dict(layer, owner=self.inner_id)
            for layer in getattr(inner, "VIEW_LAYERS", None) or inner_layers
        ]
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
        self._operator_sets()
        self.fields = self._fields()
        self.constants = self._constants(layout)
        self.events = self._events()
        self.space = self._geometry()
        self.recording = self._recording()
        self.run = self._run()
        _refuse(self.problems)
        try:  # The view's structure, before any output: only its time bases come later.
            validate(self.view({}, "prepared"))
        except ViewInvalid as exc:
            raise ViewRefused(str(exc)) from exc

    # -------------------------------------------------------------- sets

    def _sets(self, layout):
        from cells.core import species_registry
        from cells.models import inner_laws
        from cells.models import surface_pump_v3 as tissue3

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

    def _operator_sets(self):
        """Each operator's own axes, from its view_sets declaration (a requested seam)."""
        for op, declaration, _ in self.entries:
            own = {
                axis
                for axes in op.STATE_AXES.values()
                for axis in axes
                if axis not in self.axis_sets
            }
            own |= {
                axis
                for axes in getattr(op, "OBSERVATION_AXES", {}).values()
                for axis in axes
                if axis not in self.axis_sets
            }
            if not own:
                continue
            declare = getattr(op, "view_sets", None)
            declared = {} if declare is None else declare(self.spec, declaration)
            for axis in sorted(own):
                if axis not in declared:
                    self.problems.append(f"{op.LAW_ID} declares no set for its axis {axis}")
                    continue
                entry = dict(declared[axis])
                ids = list(entry.pop("ids"))
                set_id = entry.pop("id")
                if set_id in self.sets:
                    self.problems.append(f"{op.LAW_ID}: set {set_id} is declared twice")
                    continue
                if len(set(ids)) != len(ids) or not all(isinstance(i, str) for i in ids):
                    self.problems.append(f"{op.LAW_ID}: the ids of set {set_id} are unique strings")
                item = {"id": set_id, "scale": "cell", "ids": ids, "owner": op.LAW_ID}
                on = entry.pop("on", None)
                if on is not None:
                    target, of = on
                    known = self.sets[target]["ids"]
                    if any(x not in known for x in of) or len(of) != len(ids):
                        self.problems.append(f"{op.LAW_ID}: set {set_id} lies on unknown entities")
                    else:
                        item["geometry"] = {
                            "kind": "on",
                            "set": target,
                            "index": [known.index(x) for x in of],
                        }
                item |= entry
                self.sets[set_id] = item
                self.axis_sets[axis] = set_id

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
        out = {}
        for name in names:
            owner = state_owner.get(name) or column_owner.get(name)
            if owner is None:
                self.problems.append(f"field {name} has no owner in the composition's field map")
                continue
            axes = self.model.STATE_AXES.get(name)
            if owner == "inner" or name in self.inner_table:
                info = self._inner_field(name, axes, owner, declared)
            else:
                info = self._operator_field(name, axes, operators[owner])
            if info is None:
                continue
            out[name] = FieldInfo(**info, writers=writers.get(name, ()))
        return out

    def _inner_field(self, name, axes, owner, declared):
        entry = self.inner_table.get(name)
        if entry is None and name not in declared["units"]:
            self.problems.append(f"no declaration describes the inner model's field {name}")
            return None
        readout_axes, unit, kind, layer, sign = entry or (None, None, None, None, None)
        axes = axes if axes is not None else declared["axes"].get(name, readout_axes)
        unit = declared["units"].get(name, unit) or _suffix_unit(name)
        layer = declared["layers"].get(name, layer)
        if owner != "inner":  # A column an operator replaces (REPLACES): its owner's layer.
            ops = {op.LAW_ID: op for op, _, _ in self.entries}
            layer = self._operator_layer(ops[owner], name)
        if axes is None or unit is None or layer is None:
            self.problems.append(f"the inner model's field {name} lacks its axes, unit or layer")
            return None
        return self._info(
            name,
            axes,
            unit,
            layer,
            self.inner_id if owner == "inner" else owner,
            declared["kinds"].get(name, kind),
            declared["signs"].get(name, sign),
        )

    def _operator_layer(self, op, name):
        layers = self.operator_layers.get(op.LAW_ID)
        if layers is None:
            return None  # Refused already: no VIEW_LAYERS.
        layer = getattr(op, "RECORD_LAYERS", {}).get(name)
        if layer is None and len(layers) == 1:
            layer = layers[0]
        if layer not in layers:
            self.problems.append(f"{op.LAW_ID} does not name the layer of its field {name}")
            return None
        return layer

    def _operator_field(self, name, axes, op):
        if axes is None:
            axes = getattr(op, "OBSERVATION_AXES", {}).get(name)
        if axes is None:
            self.problems.append(f"{op.LAW_ID} declares no axes for its readout column {name}")
            return None
        unit = getattr(op, "UNITS", {}).get(name) or _suffix_unit(name)
        if unit is None:
            self.problems.append(f"{op.LAW_ID} declares no unit for its field {name}")
            return None
        layer = self._operator_layer(op, name)
        if layer is None:
            return None
        kind = getattr(op, "RECORD_KINDS", {}).get(name)
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
        sign = getattr(op, "ORIENTATION", {}).get(name)
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
            roles = SIGN_ROLES.get(sets[-1] if sets else None, ())
            if sign.get("from") not in roles or sign.get("to") not in roles:
                self.problems.append(f"field {name}: its sign names roles its set does not have")
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

    def _constants(self, layout):
        changers = {}
        for op, _, _ in self.entries:
            for name in (*op.VIEW_FIELDS, *op.CLOSES):
                change = op.view_change(name)
                changers.setdefault(name, []).append(
                    f"{op.LAW_ID} ({change.contribution}, {change.stage}"
                    + (", scoped" if change.scoped else "")
                    + ")"
                )
        out = []
        for name, (axes, unit) in VIEW_FIELD_AXES.items():
            if name in changers:
                self.unstated.append(
                    {
                        "id": name,
                        "what": "view field",
                        "why": "changed by "
                        + "; ".join(changers[name])
                        + ": the run saves no merged view of it",
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
                    "says": "no operator of this composition changes it",
                }
            )
        return out

    # -------------------------------------------------------------- events

    def _events(self):
        from cells.models.operators.contract import Operator

        events = []
        for op, declaration, schedule in self.entries:
            layers = self.operator_layers.get(op.LAW_ID) or [None]
            lives = op.living_intervals(self.spec, declaration, schedule)
            for cell, (birth, retirement) in lives.items():
                for time, kind in ((birth, "birth"), (retirement, "retirement")):
                    if time is not None:
                        events.append(
                            {
                                "time": float(time),
                                "kind": kind,
                                "layer": layers[0],
                                "at": {"cell": cell},
                                "label": f"{cell} {'born' if kind == 'birth' else 'retired'}",
                            }
                        )
            if type(op).view_events is Operator.view_events:
                continue  # The default restates living_intervals, taken above.
            for event in op.view_events(self.spec, declaration, schedule):
                events.append(self._event(op, dict(event)))
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
            unknown = [f for f in recording.fields if f not in self.fields]
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
        }

    # -------------------------------------------------------------- the recording subset

    def keeper(self):
        """A selector of one run's arrays under the recording subset (requirement 1), or None.

        Called on each dict of arrays a shared path saves, in order: history fields and
        observed_<field> arrays keep the declared fields and elements; observation rows (and
        observation_times) every n-th from the run's first; every other array is unchanged."""
        if self.request.recording is None:
            return None
        return _Keeper(self)

    # -------------------------------------------------------------- the view

    def view(self, bases, mode):
        """The view of a run whose time bases lie in `bases` ({base: [(file, rows)]})."""
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
                if info.sign is not None:
                    record["sign"] = info.sign
                by = [law for law in info.writers if law in self.retiring]
                resets = bool(by) and info.owner == self.inner_id and info.kind == "cumulative"
                if resets:  # A retired slot's history moves out at its retirement.
                    record["resets"] = {"by": by, "says": RESETS_NOTE}
                elif name.endswith(HEAT_SUFFIX):
                    record["monotone"] = "non-decreasing"
                    record["note"] = HEAT_NOTE
                if not resets and info.owner == self.inner_id and name in self.notes:
                    record["note"] = self.notes[name]
                records.append(record)
        return {
            "format": FORMAT,
            "run": self.run,
            "time": {"unit": "s", "bases": time},
            "space": self.space,
            "layers": self.layers,
            "sets": list(self.sets.values()),
            "records": records,
            "events": self.events,
            "constants": self.constants,
            "unstated": sorted(self.unstated, key=lambda u: (u["what"], u["id"])),
            "recording": {"mode": mode, "subset": self.recording},
        }

    def write(self, directory, bases, mode, *, out=None, files=False):
        """Write view.json (into `out`, default `directory`, the run's folder), its structure
        checked first; with files, also against the files it names, which lie in `directory`.

        The shared paths check the structure only: their view is written after the payload and
        before the manifest, and everything else was checked before any output (prepare)."""
        value = self.view(bases, mode)
        validate(value, directory if files else None)
        folder = Path(out or directory)
        folder.mkdir(parents=True, exist_ok=True)  # A batch world without chunks has no folder.
        path = folder / FILE
        with path.open("x") as handle:
            handle.write(dumps(value))
        return path


class _Keeper:
    """The recording subset applied to one run's arrays, in the order they are saved."""

    def __init__(self, plan):
        recording = plan.request.recording
        self.fields = None if recording.fields is None else set(recording.fields)
        self.every = recording.every
        self.seen = 0
        self.select = {
            name: [
                (i + 1, plan.sets[s]["recorded"])
                for i, s in enumerate(info.axes)
                if "recorded" in plan.sets[s]
            ]
            for name, info in plan.fields.items()
        }
        self.history = set(plan.model.STATE_AXES)

    def __call__(self, arrays):
        out, rows = {}, None
        if "observation_times" in arrays:
            count = len(arrays["observation_times"])
            rows = [i for i in range(count) if (self.seen + i) % self.every == 0]
            self.seen += count
        for key, value in arrays.items():
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


def prepare(spec, request=None, *, layout):
    """The plan of a run's view, from the definition, declarations, caller inputs and the bound
    layout; refused (ViewRefused) before any output exists."""
    if request is not None and not isinstance(request, Request):
        raise ViewRefused("A view is requested with a run_view.Request")
    return Plan(spec, request, layout)


def requests_for(view, world_ids):
    """{world ID: Request} of a batch: one Request for every world, or a mapping that names each
    world exactly once (each world's own geometry); {} without a view."""
    if view is None:
        return {}
    if isinstance(view, Request):
        return dict.fromkeys(world_ids, view)
    if not isinstance(view, dict) or set(view) != set(world_ids):
        raise ViewRefused("A batch's view requests name every world once: " + str(list(world_ids)))
    return dict(view)


def dumps(value):
    """The view's bytes: sorted keys, no NaN, a final newline (deterministic)."""
    return json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"


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
    from cells.core.specs import parse_spec, read_json

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
    plan = prepare(spec, Request(run or {}, geometry), layout=saved_layout(directory))
    return plan.write(directory, bases, mode or "write_run", out=out, files=True)


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
    _check(set(view) == TOP_KEYS, problems, f"top-level keys are {sorted(TOP_KEYS)}")
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
        ):
            if key in s:
                _check(len(s[key]) == len(ids), problems, f"set {set_id}: {key} has one per id")
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
    for set_id, s in sets.items():
        _validate_geometry(set_id, s, sets, sizes, space, problems)
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
        if "resets" in record:
            resets = record["resets"]
            _check(
                isinstance(resets, dict)
                and set(resets) == {"by", "says"}
                and resets["by"]
                and all(isinstance(law, str) and "@" in law for law in resets["by"])
                and "monotone" not in record,
                problems,
                f"record {rid}: resets names the retiring laws, and claims no monotonicity",
            )
        if "sign" in record:
            roles = SIGN_ROLES.get(record.get("set"), ())
            sign = record["sign"]
            _check(
                isinstance(sign, dict)
                and sign.get("from") in roles
                and sign.get("to") in roles
                and sign["from"] != sign["to"]
                and isinstance(sign.get("says"), str),
                problems,
                f"record {rid}: its sign names two roles of its set and says what positive means",
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
    if directory is not None and not problems:
        _validate_files(view, Path(directory), sets, sizes, problems)
    if problems:
        raise ViewInvalid("Invalid run view: " + "; ".join(problems))


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
