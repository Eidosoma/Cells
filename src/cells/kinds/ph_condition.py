"""cells.ph_condition@1: a node's pH condition, a source of the routing door (FR-5).

docs/COMPARTMENT_PH_TRANSFER_DESIGN.md §8, §9 and §16 (the lead's rulings of 16 November 2026);
the law is `ph_conditioned_factor@1` (laws/reactions/ph_condition.py):

    f(pH) = 1 / (1 + 10^(m (pH - pH50))),   m > 0,

open (f -> 1) below pH50 and closed above it. The pH is the node's free proton read on the stage's
state: B4's closure read (rapid_proton_buffer@1) at a buffered node, the stored row at an
unbuffered one, as pH = -log10(h / 1 M) (B4's readout convention,
rapid_proton_buffer.PH_REFERENCE_mM). It has no state, moves nothing and books nothing; it
reaches routes only as a factor through the routing door (§16.2), which the core builds.

The declaration (model key `ph_conditions`), each condition at a node by its ID (a kind's parse
sees the base model's nodes, not FR-1's identity map; in the declared world FR-1's operator gives
the node its compartment's identity):

    [{"id": "acid_0", "node": "lumen_0", "law": "ph_conditioned_factor@1", "ph50": 5.5,
      "slope": 4.0}]

with an optional `proton` row (default "H"), which must be B4's proton row where B4 is declared.

- **Layout,** per condition: its node (cells, then outside nodes, as the passive routes index
  them), its proton row, pH50 and the slope.
- **readouts:** f per condition (`ph_condition_factor`), on the observed row's read.
- **The routing door's source** (INNER_MODEL_V4_DESIGN.md §7.4 (n), the core's seam):
  `factor_sources(declaration)`, the condition IDs in declared order, and `factors(read, p, *,
  xp)`, f of each on the stage's read. h > 0 at the node is the read's and @3's domain (a failed
  read and a non-positive amount refuse the step before any factor); the door's [0, 1] check
  refuses anything else.
- **Its limit:** it has no feedback hooks (factor_rows and factor_log_slopes; kind_registry.Kind),
  so the core's bound on a gated route's feedback does not cover a loop through it, such as a route
  that moves protons at its own condition's node. FR-5's worlds use it, so it is admitted.
- **Its successor:** `cells.species_condition@1` with one hill_activation read of the proton row,
  K = 10^(3 - pH50) mM and n the slope, which has the hooks. The two factors differ by at most
  2.3e-15 on 20,000 random points (hill_product_factor@1 against ph_conditioned_factor@1). A new
  definition declares that kind; this one retires in a landing of its own, with the worlds that
  declare it.
"""

from types import MappingProxyType
from typing import NamedTuple

import numpy as np

from cells.laws.reactions import ph_condition as law
from cells.laws.reactions import rapid_proton_buffer as closure
from cells.registry.kind_registry import (
    BUILTIN,
    ConfigError,
    Kind,
    KindView,
    finite_number,
    qualified,
    require_fields,
)

KIND_ID = "cells.ph_condition@1"
MODEL_KEY = "ph_conditions"
LAW_ID = qualified(law.LAW_ID)
ENTRY_FIELDS = ("id", "node", "law", "ph50", "slope")
DEFAULT_PROTON = "H"
CLOSURE_KIND = "cells.rapid_proton_buffer@1"
LAYOUT_FIELDS = (
    "ph_condition_node",  # [condition] the node's index: cells, then outside nodes
    "ph_condition_proton_row",  # [condition] the proton row
    "ph_condition_ph50",  # [condition]
    "ph_condition_slope",  # [condition] m > 0
)
READOUT_COLUMNS = ("ph_condition_factor",)


class Condition(NamedTuple):
    """One declared pH condition."""

    id: str
    node: str
    ph50: float
    slope: float
    proton: str


# ---------------------------------------------------------------------------- definition


def _taken_ids(m):
    nodes = (*m.cells, *m.extracellular, *m.membranes, *m.junctions, *m.faces)
    return {node.id for node in nodes}


def parse(entries, base):
    """The declaration: a tuple of Conditions, in declared order."""
    m = base.model
    if not isinstance(entries, list) or not entries:
        raise ConfigError(f"{MODEL_KEY} is a non-empty list of pH conditions (omit it for none)")
    nodes = {c.id for c in m.cells} | {o.id for o in m.extracellular}
    taken, ids, out = _taken_ids(m), set(), []
    for raw in entries:
        if not isinstance(raw, dict):
            raise ConfigError(f"{MODEL_KEY}: each condition is a mapping")
        require_fields(raw, set(ENTRY_FIELDS) | ({"proton"} & set(raw)), "a pH condition")
        name = raw["id"]
        if not isinstance(name, str) or not name or name in ids or name in taken:
            raise ConfigError(f"pH condition ID {name!r} must be unique among the model's IDs")
        ids.add(name)
        where = f"pH condition {name!r}"
        if not isinstance(raw["law"], str) or not raw["law"] or qualified(raw["law"]) != LAW_ID:
            raise ConfigError(f"{where}: law is {LAW_ID}")
        if raw["node"] not in nodes:
            raise ConfigError(f"{where}: unknown node {raw['node']!r} (a cell or an outside node)")
        proton = raw.get("proton", DEFAULT_PROTON)
        if proton not in m.species_ids:
            raise ConfigError(f"{where}: unknown proton row {proton!r}")
        ph50 = finite_number(raw["ph50"], f"{where}: ph50")
        slope = finite_number(raw["slope"], f"{where}: slope", positive=True)
        out.append(Condition(name, raw["node"], ph50, slope, proton))
    return tuple(out)


def to_dict(declaration):
    out = []
    for c in declaration:
        entry = dict(id=c.id, node=c.node, law=LAW_ID, ph50=c.ph50, slope=c.slope)
        if c.proton != DEFAULT_PROTON:
            entry["proton"] = c.proton
        out.append(entry)
    return out


def structure_entry(declaration):
    """Value-free: the law, and the number of sources (the factors' shape)."""
    return (LAW_ID, len(declaration))


def _node_ids(spec):
    """Cells padded to capacity, then outside nodes padded to theirs (the layout's node order)."""
    m, x = spec.model, spec.execution
    nodes = [c.id for c in m.cells] + [None] * (x.capacity - len(m.cells))
    return (
        nodes
        + [o.id for o in m.extracellular]
        + [None] * (x.extracellular_capacity - len(m.extracellular))
    )


def initial(spec, declaration, layout):
    """No state; per condition, its node, proton row, pH50 and slope."""
    nodes, ids = _node_ids(spec), list(spec.model.species_ids)
    own = dict(
        ph_condition_node=np.asarray([nodes.index(c.node) for c in declaration], dtype=np.int64),
        ph_condition_proton_row=np.asarray(
            [ids.index(c.proton) for c in declaration], dtype=np.int64
        ),
        ph_condition_ph50=np.asarray([c.ph50 for c in declaration], dtype=float),
        ph_condition_slope=np.asarray([c.slope for c in declaration], dtype=float),
    )
    return {}, own


def check_definition(spec):
    """The proton row has valence +1, and is B4's proton row where B4 is declared."""
    m = spec.model
    kinds = dict(m.kinds)
    read = kinds.get(CLOSURE_KIND)
    for c in kinds[KIND_ID]:
        if m.valence[m.species_ids.index(c.proton)] != 1:
            raise ConfigError(f"pH condition {c.id!r}: its proton row {c.proton} has valence +1")
        if read is not None and read.proton != c.proton:
            raise ConfigError(
                f"pH condition {c.id!r}: its proton row {c.proton} is not the closure's proton "
                f"row {read.proton or '(none: the closure declares no proton_row)'}"
            )


# ---------------------------------------------------------------------------- the factor


def free_proton_mM(read, p, *, xp):
    """Free h (mM) at each condition's node on the read state: the read's H row over the node's
    volume (B4's free h at a buffered node, the stored row elsewhere)."""
    amounts = xp.concatenate(
        (
            p.amount_reference + read.amount_increment,
            p.extracellular_amount_reference + read.extracellular_amount_increment,
        ),
        axis=1,
    )
    volume = xp.concatenate((p.volume, p.extracellular_volume))
    return amounts[p.ph_condition_proton_row, p.ph_condition_node] / volume[p.ph_condition_node]


def factors(read, p, *, xp):
    """f of each condition on the stage's read, in declared order (the routing door's values)."""
    ph = -xp.log10(free_proton_mM(read, p, xp=xp) / closure.PH_REFERENCE_mM)
    return law.factor(ph, p.ph_condition_ph50, p.ph_condition_slope, xp=xp)


def factor_sources(declaration):
    """The routing door's sources this kind exposes: its condition IDs, in declared order."""
    return tuple(c.id for c in declaration)


def readouts(state, read, potentials, control, p, *, xp):
    """f per condition on the observed row's read."""
    return (factors(read, p, xp=xp),)


# The run view's declarations (D154): f is a level per condition, on the kind's own axis.
AXIS = "ph_condition"
VIEW = KindView(
    units=MappingProxyType({"ph_condition_factor": "1"}),
    observation_axes=MappingProxyType({"ph_condition_factor": (AXIS,)}),
    record_kinds=MappingProxyType({"ph_condition_factor": "level"}),
    record_layers=MappingProxyType({"ph_condition_factor": "membrane"}),
)


def view_sets(spec, declaration):
    """The view's set of the conditions' axis: one entry per condition, in declared order."""
    return {
        AXIS: {
            "id": AXIS,
            "ids": [c.id for c in declaration],
            "roles": {"node": "the node whose free proton read sets the condition's pH"},
            "kinds": ["factor" for _ in declaration],
            "laws": [{"law_id": LAW_ID} for _ in declaration],
            "at": [{"node": c.node} for c in declaration],
            "ph50": [c.ph50 for c in declaration],
            "slope": [c.slope for c in declaration],
        }
    }


PH_CONDITION = BUILTIN.register(
    Kind(
        kind_id=KIND_ID,
        model_key=MODEL_KEY,
        layout_fields=LAYOUT_FIELDS,
        readout_columns=READOUT_COLUMNS,
        parse=parse,
        to_dict=to_dict,
        structure_entry=structure_entry,
        initial=initial,
        readouts=readouts,
        check_definition=check_definition,
        factor_sources=factor_sources,
        factors=factors,
        view=VIEW,
        view_sets=view_sets,
    )
)
