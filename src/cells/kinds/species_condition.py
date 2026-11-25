"""cells.species_condition@1: a node's species condition, a source of the routing door (G-5).

docs/IP3_RELEASE_AND_ASSEMBLY_AVAILABILITY_DESIGN.md, Part I (the user's choice of 25 November 2026:
a general source that any route or channel can name); the law is `hill_product_factor@1`
(laws/reactions/hill_product_factor.py). A condition is one factor in [0, 1]: the product of Hill
factors of declared species rows at one node,

    f = h_1 h_2 ...,  h_j = x^n/(K^n + x^n) (hill_activation) or K^n/(K^n + x^n) (hill_inhibition),

with x = N/V (mM) the row's concentration at the node. It has no state, moves nothing and books
nothing; it reaches a route or a channel only as a factor through the routing door
(INNER_MODEL_V4_DESIGN.md §7.4 (n)), which books nothing either: the route books what it moves.

The declaration (model key `species_conditions`), each condition at a node by its ID (a cell or an
outside node, so a compartment's node reads its lumen):

    [{"id": "release_calcium_0", "node": "cell_0", "law": "hill_product_factor@1",
      "reads": [{"species": "Ca", "form": "hill_activation", "half_saturation_mM": 0.001,
                 "hill_coefficient": 2.0},
                {"species": "Ca", "form": "hill_inhibition", "half_saturation_mM": 0.02,
                 "hill_coefficient": 2.0}]}]

A condition's reads are a non-empty list, any species of the world, charged or neutral, in any
order; a species may be read more than once. Any number of routes and channels may name one
condition, and a route that names two multiplies its held value by them in its own declared order.

- **The read is the stage's:** the amounts of the state each rate of the stage reads (the free form
  where a closure owns the row) over the node's current volume, at every explicit stage and at each
  observed row. It is a concentration: the row's valence does not enter. ln x is formed as
  ln N - ln V, as local_species_reactions@1 and species_regulated_availability@1 form it, so one
  Hill read is that operator's factor (basal 0) bit for bit.
- **Positive amounts:** @3 keeps every row above zero at every node, so no run reads a zero. A
  negative or NaN amount gives NaN, and the door refuses the step or the row.
- **Layout,** per condition and read (padded to the largest number of reads): the node (cells, then
  outside nodes, as the passive routes index them), the species row, the form, K and n; and the
  flattened pairs of its feedback hooks (below). **Readout:** f per condition, on the observed row's
  read (`species_condition_factor`).
- **Refused by name:** a law that is not this kind's, an unknown node or species, a form that is not
  one of the law's two, an empty `reads`, a half-saturation or coefficient that is not a finite,
  positive, normal float, and a condition ID that is not unique among the model's IDs. The door
  refuses a source two kinds expose and one no kind exposes, and @3 refuses any kind under RK4.
- **Beside operators:** water (the read takes the current volume), the compartment wash and arrival
  labels are admitted, since the kind has no rates, no moved rows and no route. It declares no
  partition roles in version 1, so a closer or a retiring operator refuses it.
- **The feedback hooks,** factor_rows and factor_log_slopes (the contract in kind_registry.Kind),
  give the core the slopes it needs to bound a loop that a gated route closes on its own gate (it
  moves a row its condition reads). The bound itself is the core's, in material_rate. Its limits
  hold here: a loop through two routes is not bounded, nor is one through a source that reads an
  amount and has no hooks (ph_condition@1); and where a closure owns the row, the slope is in the
  free amount, without the closure's own.
- **The pH condition** (`ph_condition@1`) is this law with one hill_activation read of the proton
  row, K = 10^(3 - pH50) mM and n the slope: on 20,000 random points the two differ by at most
  2.3e-15. It retires in a landing of its own.
"""

from types import MappingProxyType
from typing import NamedTuple

import numpy as np

from cells.laws.reactions import hill_product_factor as law
from cells.modules import (
    ConfigError,
    Kind,
    KindView,
    finite_number,
    hosted_laws,
    qualified,
    require_fields,
)
from cells.registry.kind_registry import BUILTIN

KIND_ID = "cells.species_condition@1"
MODEL_KEY = "species_conditions"
LAW_ID = qualified(law.LAW_ID)
FORMS = MappingProxyType(dict(law.FORMS))  # {form: code}
ENTRY_FIELDS = ("id", "node", "law", "reads")
READ_FIELDS = ("species", "form", *law.PARAMETERS)
LAYOUT_FIELDS = (
    "species_condition_node",  # [condition] the node's index: cells, then outside nodes
    "species_condition_row",  # [condition, read] the species row (0 in padding)
    "species_condition_form",  # [condition, read] 1 activation, 2 inhibition, 0 padding
    "species_condition_half_saturation_mM",  # [condition, read] K (1 in padding)
    "species_condition_coefficient",  # [condition, read] n (1 in padding)
    "species_condition_pair",  # [condition, read] the read's flattened pair (0 in padding)
    "species_condition_pair_condition",  # [pair] each flattened pair's condition
)
READOUT_COLUMNS = ("species_condition_factor",)


class Reading(NamedTuple):
    """One declared read of a condition."""

    species: str
    form: str
    half_saturation_mM: float
    coefficient: float


class Condition(NamedTuple):
    """One declared species condition."""

    id: str
    node: str
    reads: tuple  # (Reading, ...), in declared order.

    @property
    def species(self):
        """The species it reads, each once, in order of first appearance."""
        return tuple(dict.fromkeys(r.species for r in self.reads))


# ---------------------------------------------------------------------------- definition


def _taken_ids(m):
    """The IDs of the base model's nodes, patches, junctions, faces and pumps."""
    entities = [*m.cells, *m.extracellular, *m.membranes, *m.junctions, *m.faces]
    pumps = [pump for patch in m.membranes for pump in (patch.pump, patch.calcium_pump)]
    return {entity.id for entity in (*entities, *pumps) if entity is not None}


NOT_UNIQUE = "its ID must be a name, unique among the model's IDs"


def _where(name):
    return f"{KIND_ID}: condition {name!r}"


def _check_law(law_id, where):
    """The law is one this kind hosts (found in the active law registry by interface and host,
    CORE_SEAMS §8.3), and the one version 1 runs."""
    hosted = sorted(qualified(x.law_id) for x in hosted_laws(law.TRANSFER_FACTOR_LAW, KIND_ID))
    if not isinstance(law_id, str) or not law_id or qualified(law_id) not in hosted:
        raise ConfigError(f"{where}: law is one of {', '.join(hosted)}")
    if qualified(law_id) != LAW_ID:
        raise ConfigError(f"{where}: version 1 runs {LAW_ID}, not {law_id}")


def _parameter(value, where):
    """A read's half-saturation or coefficient: finite, positive and a normal float."""
    value = finite_number(value, where, positive=True)
    if value < np.finfo(np.float64).tiny:
        raise ConfigError(
            f"{where} is a normal float, at least {np.finfo(np.float64).tiny} (compiled CPU code "
            "reads a subnormal one as 0)"
        )
    return value


def _parse_reading(raw, where, species_ids):
    require_fields(raw, set(READ_FIELDS), where)
    species, form = raw["species"], raw["form"]
    if not isinstance(species, str) or species not in species_ids:
        raise ConfigError(f"{where}: unknown species {species!r}")
    if not isinstance(form, str) or form not in FORMS:
        raise ConfigError(f"{where}: form is one of {', '.join(FORMS)}, not {form!r}")
    return Reading(
        species, form, *(_parameter(raw[key], f"{where}: {key}") for key in law.PARAMETERS)
    )


def parse(entries, base):
    """The declaration: a tuple of Conditions, in declared order."""
    m = base.model
    if not isinstance(entries, list) or not entries:
        raise ConfigError(
            f"{KIND_ID}: {MODEL_KEY} is a non-empty list of conditions (omit it for none)"
        )
    nodes = {c.id for c in m.cells} | {o.id for o in m.extracellular}
    taken, ids, out = _taken_ids(m), set(), []
    for raw in entries:
        name = raw.get("id") if isinstance(raw, dict) else None
        where = _where(name)
        require_fields(raw, set(ENTRY_FIELDS), where)
        if not isinstance(name, str) or not name or name in ids or name in taken:
            raise ConfigError(f"{where}: {NOT_UNIQUE}")
        ids.add(name)
        _check_law(raw["law"], where)
        node = raw["node"]
        if not isinstance(node, str) or node not in nodes:
            raise ConfigError(f"{where}: unknown node {node!r} (a cell or an outside node)")
        reads = raw["reads"]
        if not isinstance(reads, list) or not reads:
            raise ConfigError(f"{where}: reads is a non-empty list of readings")
        out.append(
            Condition(
                name,
                node,
                tuple(
                    _parse_reading(entry, f"{where}, read {j}", m.species_ids)
                    for j, entry in enumerate(reads)
                ),
            )
        )
    return tuple(out)


def _reads(condition):
    """A condition's reads as the definition writes them."""
    return [dict(zip(READ_FIELDS, r, strict=True)) for r in condition.reads]


def to_dict(declaration):
    return [dict(id=c.id, node=c.node, law=LAW_ID, reads=_reads(c)) for c in declaration]


def structure_entry(declaration):
    """Value-free: the law, and each condition's number of reads and of pairs (the layout's shapes,
    and the hooks'), so two worlds of one shape share programs."""
    return (LAW_ID, tuple((len(c.reads), len(c.species)) for c in declaration))


def check_definition(spec):
    """A condition's ID is no channel population's or forms face's: the base model that parse sees
    holds neither."""
    m = spec.model
    others = {entity.id for entity in (*m.channels, *getattr(m, "forms_faces", ()))}
    for c in dict(m.kinds)[KIND_ID]:
        if c.id in others:
            raise ConfigError(f"{_where(c.id)}: {NOT_UNIQUE}")


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
    """No state; the layout fields, padded to the largest number of reads."""
    nodes, ids = _node_ids(spec), list(spec.model.species_ids)
    shape = (len(declaration), max(len(c.reads) for c in declaration))
    row, form, pair = (np.zeros(shape, dtype=np.int64) for _ in range(3))
    half_saturation, coefficient = np.ones(shape), np.ones(shape)
    owners = []  # Each flattened pair's condition: conditions in declared order, then species.
    for i, c in enumerate(declaration):
        first = len(owners)
        owners += [i] * len(c.species)
        for j, r in enumerate(c.reads):
            row[i, j] = ids.index(r.species)
            form[i, j] = FORMS[r.form]
            half_saturation[i, j], coefficient[i, j] = r.half_saturation_mM, r.coefficient
            pair[i, j] = first + c.species.index(r.species)
    own = dict(
        species_condition_node=np.asarray([nodes.index(c.node) for c in declaration], np.int64),
        species_condition_row=row,
        species_condition_form=form,
        species_condition_half_saturation_mM=half_saturation,
        species_condition_coefficient=coefficient,
        species_condition_pair=pair,
        species_condition_pair_condition=np.asarray(owners, np.int64),
    )
    return {}, own


# ---------------------------------------------------------------------------- the factor


def log_concentration(read, p, *, xp):
    """[condition, read] ln of each read's concentration (mM) on the read state: ln N - ln V of its
    row at its condition's node, the node's amounts and volume taken by index alone."""
    n, node, row = p.active.size, p.species_condition_node, p.species_condition_row
    is_cell = node < n
    cell, outside = xp.where(is_cell, node, 0), xp.where(is_cell, 0, node - n)
    amount = xp.where(
        is_cell[:, None],
        p.amount_reference[row, cell[:, None]] + read.amount_increment[row, cell[:, None]],
        p.extracellular_amount_reference[row, outside[:, None]]
        + read.extracellular_amount_increment[row, outside[:, None]],
    )
    volume = xp.where(is_cell, p.volume[cell], p.extracellular_volume[outside])
    return xp.log(amount) - xp.log(volume)[:, None]


def _arguments(read, p, *, xp):
    """The law's kernels' arguments, in their order."""
    return (
        log_concentration(read, p, xp=xp),
        p.species_condition_half_saturation_mM,
        p.species_condition_coefficient,
        p.species_condition_form,
    )


def factors(read, p, *, xp):
    """f of each condition on the stage's read, in declared order (the routing door's values)."""
    return law.factor(*_arguments(read, p, xp=xp), xp=xp)


def factor_sources(declaration):
    """The routing door's sources this kind exposes: its condition IDs, in declared order."""
    return tuple(c.id for c in declaration)


def factor_rows(declaration):
    """The rows each condition reads, ((species ID, node ID), ...) per source in factor_sources'
    order, each pair once, in order of first appearance (the feedback hooks; names only)."""
    return tuple(tuple((species, c.node) for species in c.species) for c in declaration)


def factor_log_slopes(read, p, *, xp):
    """[pair] d ln f / d ln n of each of factor_rows' pairs, flattened (sources in order, then each
    source's pairs), signed and dimensionless, on the stage's read: the sum, over the condition's
    reads of the pair's species, of their signed slopes (log_slopes), a serial left fold in declared
    order. Finite at a zero amount."""
    slopes = law.log_slopes(*_arguments(read, p, xp=xp), xp=xp)
    owner = p.species_condition_pair_condition
    index = xp.arange(owner.shape[0])  # Static: one element per pair.
    total = xp.zeros(owner.shape[0])
    for j in range(slopes.shape[1]):
        mine = p.species_condition_pair[owner, j] == index  # A padded read's slope is 0.
        total = total + xp.where(mine, slopes[owner, j], 0.0)
    return total


def readouts(state, read, potentials, control, p, *, xp):
    """f per condition on the observed row's read."""
    return (factors(read, p, xp=xp),)


# The run view's declarations (D154): f is a level per condition, on the kind's own axis.
AXIS = "species_condition"
VIEW = KindView(
    units=MappingProxyType({"species_condition_factor": "1"}),
    observation_axes=MappingProxyType({"species_condition_factor": (AXIS,)}),
    record_kinds=MappingProxyType({"species_condition_factor": "level"}),
    record_layers=MappingProxyType({"species_condition_factor": "membrane"}),
)


def view_sets(spec, declaration):
    """The view's set of the conditions' axis: one entry per condition, in declared order."""
    return {
        AXIS: {
            "id": AXIS,
            "ids": [c.id for c in declaration],
            "roles": {"node": "the node whose concentrations set the condition"},
            "kinds": ["factor" for _ in declaration],
            "laws": [{"law_id": LAW_ID} for _ in declaration],
            "at": [{"node": c.node} for c in declaration],
            "reads": [_reads(c) for c in declaration],
        }
    }


SPECIES_CONDITION = BUILTIN.register(
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
        factor_rows=factor_rows,
        factor_log_slopes=factor_log_slopes,
        view=VIEW,
        view_sets=view_sets,
    )
)
