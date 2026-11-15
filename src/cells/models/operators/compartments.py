"""cell_owned_compartments@1: closed compartments owned by cells, on @3's layout (FR-1, D169).

docs/CLOSED_COMPARTMENT_DESIGN.md. A compartment is a finite outside node of
resolved_pump_tissue@3 that no face names, bounded by exactly one membrane patch whose inside is its
owner cell (§1.1). Its volume, amounts, fixed charge and charge anchor are @3's own fields of that
node, and its species are @3's rows there; the patch's area and capacitance are its membrane. The
node is a free node of @3's capacitor solve, so the bounding patch's voltage is V_b = -q/C_b
exactly (§3.1). Nothing about a fixed compartment needs a field @3 lacks, so this law is a
declaration (the contract's DECLARATION_ONLY, §1.6): it owns no state, runs no part and contributes
nothing to any program (S5, §3.3). What it adds is identity and the refusals that protect it.

Refused at the definition, each with its reason (§1.4, §1.5):
1. a node that is not a declared outside node, is a held bath, is the gauge, or is named by a face;
2. a patch that is not declared, is not the only patch whose outside is the node, or whose inside
   is not the declared owner (a declared cell);
3. two compartments on one node (an owner may own several);
4. an ion route on the bounding patch (version 1): a nonzero permeability, a Na/K or Ca pump, or a
   channel population. That is the charged door (§3.4): a compartment has no face, so @3's per-cell
   bound would not see its own charge relaxation;
5. a nonzero charge anchor (version 1): the content is electroneutral, so q = 0 and V_b = 0;
6. an owner whose capacitor component (cells and outside nodes joined by membrane patches, as
   numerics/surface_field.bind joins them) holds no held bath (version 1). In such a component no
   representative is chosen, so the compartment is a free node of the capacitor solve (§3.5);
7. a composition beyond the admitted list of §4, which fails closed: a new operator may treat
   outside nodes as environment. Replacement@1 schedules no event on an owner's slot and names no
   owner as a donor (§1.5): a newcomer would inherit the compartment's content, and a donor copy
   takes the donor's cytosolic amounts only. Providers and closers of the volumes, the areas, the
   capacitances and the masks are refused through CONFLICTS_VIEW by the composite's structure check:
   water and what requires it, membrane state, insertion, the lumens, and S5's closers (division).
The stationary analysis does not admit the composite (its own ID check).

Identity is a host-side map (identity_map; ARCHITECTURE.md's modular core, D174): per compartment,
its ID, its owner, its role, its storage and its oriented bounding membrane. The map's shape is
independent of today's storage as an outside node, which is one field of it; its values are not yet.
In version 1 a compartment's ID is its node's ID (§1.4), and its role is fixed as "lumen": the
compartment lies outside its bounding membrane, whose inside is the owner's cytosol (§1.1), so
V_b = phi_owner - phi_compartment is @3's patch voltage. A declared ID distinct from the node, and a
declared role, would make the values independent too; the @1 schema has neither.
Labels and references are metadata: they reach the map and the summary, never an array. The
transfer law is D150's exchange, unchanged (§2), a driven route (D174): it books the free-energy
change of what it moves as signed work, with no heat. Loading is an export route on the bounding
patch, release an import route; degradation inside is turnover's clearance at the node, and
reactions inside are D152's at the node.
"""

from dataclasses import dataclass

from cells.core import pump_composite_spec as composite_spec
from cells.core.multispecies_spec import identifier
from cells.core.specs import ConfigError, _fields
from cells.models.operators.contract import Operator

LAW_ID = "cell_owned_compartments@1"
REPLACEMENT_LAW = "scheduled_cell_replacement@1"
# §4's admitted list (fails closed). @3 itself is the composite's inner model.
ADMITTED = (
    LAW_ID,
    "electrode_current_injection@1",
    "scheduled_species_exchange@1",
    "scheduled_species_turnover@1",
    "local_species_reactions@1",
    "species_regulated_availability@1",
    REPLACEMENT_LAW,
    "scheduled_bath_composition@1",
)
# Read as declared: the volumes, the areas, the capacitances and the activity masks (§1.4, 7).
CONFLICTS_VIEW = (
    "volume",
    "extracellular_volume",
    "membrane_area",
    "membrane_capacitance",
    "active",
    "outside_active",
    "membrane_active",
    "channel_active",
    "junction_active",
    "face_active",
)
COMPARTMENT_FIELDS = {"node", "patch", "owner", "label", "reference"}
ROLE = "lumen"  # Version 1: outside its bounding membrane, whose inside is the owner's cytosol.


@dataclass(frozen=True)
class Compartment:
    node: str  # The compartment's @3 outside node, and its stable compartment id.
    patch: str  # Its bounding patch.
    owner: str  # The owner's cell id: the founder carrier, which never changes (version 1).
    label: str | None  # Free text; metadata only.
    reference: str | None  # An opaque ontology reference; metadata only.


@dataclass(frozen=True)
class CompartmentsDeclaration:
    law: str
    compartments: tuple  # Compartment, in declared order.


# ------------------------------------------------------------------ definition


def _metadata(value, what):
    if value is None:
        return None
    if type(value) is not str or not value.strip():
        raise ConfigError(f"{LAW_ID}: a compartment's {what} is null or a non-empty string")
    return value


def capacitor_components(model):
    """{cell or outside node id: component root}: cells and outside nodes joined by patches."""
    parent = {c.id: c.id for c in (*model.cells, *model.extracellular)}

    def root(name):
        while parent[name] != name:
            name = parent[name]
        return name

    for membrane in model.membranes:
        parent[root(membrane.outside)] = root(membrane.inside)
    return {name: root(name) for name in parent}


def refuse_ion_routes(model, node, bounding):
    """Refusal 4: no ion route on the bounding patch (version 1), the charged door (§3.4)."""
    channels = [c.id for c in model.channels if c.membrane_id == bounding.id]
    if (
        any(v != 0.0 for v in bounding.permeability_m_per_s)
        or bounding.pump is not None
        or bounding.calcium_pump is not None
        or channels
    ):
        raise ConfigError(
            f"{LAW_ID}: the bounding patch {bounding.id!r} of compartment {node!r} carries an ion "
            "route (a nonzero permeability, a pump or a channel population). Version 1 is "
            "neutral and silent: a charged compartment is the charged door (FR-4, FR-5), "
            "since its patch's charge relaxation is outside @3's per-cell explicit bound"
        )


def refuse_charge_anchor(node, compartment):
    """Refusal 5: electroneutral content (version 1), so V_b = 0 (§3.3)."""
    if compartment.initial_charge_C != 0.0:
        raise ConfigError(
            f"{LAW_ID}: compartment {node!r} declares a nonzero charge anchor "
            f"({compartment.initial_charge_C} C); version 1's content is electroneutral, so "
            "V_b = 0 (a resting potential needs charged content: FR-4)"
        )


def parse_declaration(raw, base):
    _fields(raw, {"law", "compartments"}, "compartments declaration")
    if raw["law"] != LAW_ID:
        raise ConfigError("A compartments declaration requires law " + LAW_ID)
    if type(raw["compartments"]) is not list or not raw["compartments"]:
        raise ConfigError(f"{LAW_ID} declares its compartments in a non-empty list")
    m = base.model
    outside = {c.id: c for c in m.extracellular}
    cells = {c.id for c in m.cells}
    components = capacitor_components(m)
    held = {components[c.id] for c in m.extracellular if c.reservoir}
    compartments = []
    for entry in raw["compartments"]:
        if not isinstance(entry, dict):
            raise ConfigError(f"{LAW_ID}: each compartment is an object")
        _fields(entry, COMPARTMENT_FIELDS, "compartment")
        node, patch, owner = (identifier(entry[k]) for k in ("node", "patch", "owner"))
        # 1. The node.
        if node not in outside:
            raise ConfigError(f"{LAW_ID}: compartment {node!r} is not a declared outside node")
        if outside[node].reservoir:
            raise ConfigError(
                f"{LAW_ID}: compartment {node!r} is a held bath; a compartment is a finite node"
            )
        if node == m.gauge_reference:
            raise ConfigError(f"{LAW_ID}: compartment {node!r} is the gauge")
        faces = [f.id for f in m.faces if node in (f.sender, f.receiver)]
        if faces:
            raise ConfigError(
                f"{LAW_ID}: compartment {node!r} is named by the face {faces[0]!r}; a compartment "
                "has no face (it is closed)"
            )
        # 2. The bounding patch.
        facing = [p for p in m.membranes if p.outside == node]
        if patch not in {p.id for p in m.membranes}:
            raise ConfigError(
                f"{LAW_ID}: the patch {patch!r} of compartment {node!r} is not declared"
            )
        if len(facing) != 1 or facing[0].id != patch:
            raise ConfigError(
                f"{LAW_ID}: compartment {node!r} is bounded by exactly one patch, its declared "
                f"{patch!r}; the patches facing it are {[p.id for p in facing]}"
            )
        if owner not in cells:
            raise ConfigError(
                f"{LAW_ID}: the owner {owner!r} of compartment {node!r} is not a cell"
            )
        bounding = facing[0]
        if bounding.inside != owner:
            raise ConfigError(
                f"{LAW_ID}: the patch {patch!r} of compartment {node!r} lies on "
                f"{bounding.inside!r}, not on its declared owner {owner!r}"
            )
        refuse_ion_routes(m, node, bounding)  # 4.
        refuse_charge_anchor(node, outside[node])  # 5.
        # 6. A held-bath topology.
        if components[owner] not in held:
            raise ConfigError(
                f"{LAW_ID}: the owner {owner!r} of compartment {node!r} lies in a capacitor "
                "component with no held bath; version 1 requires one, so that the compartment is a "
                "free node of the capacitor solve, never a representative"
            )
        label = _metadata(entry["label"], "label")
        reference = _metadata(entry["reference"], "reference")
        compartments.append(Compartment(node, patch, owner, label, reference))
    # 3. One compartment per node.
    nodes = [c.node for c in compartments]
    if len(set(nodes)) != len(nodes):
        raise ConfigError(f"{LAW_ID}: one compartment per node (an owner may own several)")
    return CompartmentsDeclaration(LAW_ID, tuple(compartments))


def declaration_to_dict(declaration):
    if type(declaration) is not CompartmentsDeclaration or any(
        type(c) is not Compartment for c in declaration.compartments
    ):
        raise ConfigError("Require explicit immutable compartments declaration types")
    return dict(
        law=declaration.law,
        compartments=[
            dict(node=c.node, patch=c.patch, owner=c.owner, label=c.label, reference=c.reference)
            for c in declaration.compartments
        ],
    )


def check_definition(spec, declaration):
    """7. The admitted list, which fails closed, and replacement@1's owners."""
    owners = {c.owner for c in declaration.compartments}
    for op, _, schedule in composite_spec.entries(spec):
        if op.LAW_ID not in ADMITTED:
            raise ConfigError(
                f"{LAW_ID} composes only with {', '.join(ADMITTED[1:])}; {op.LAW_ID} is not on "
                "its admitted list (it fails closed: a new operator may treat outside nodes as "
                "environment)"
            )
        if op.LAW_ID != REPLACEMENT_LAW:
            continue
        for event in schedule:
            if event.slot in owners:
                raise ConfigError(
                    f"{LAW_ID}: replacement@1 schedules an event on {event.slot!r}, which owns a "
                    "compartment; a newcomer would inherit the compartment's content (door R)"
                )
            if event.donor in owners:
                raise ConfigError(
                    f"{LAW_ID}: replacement@1 names {event.donor!r}, which owns a compartment, as "
                    "a donor; a donor copy takes the donor's cytosolic amounts only, so the "
                    "newcomer would not be a copy (door R)"
                )


def identity_map(model, declaration):
    """The host-side compartment map (D174): one entry per compartment, in declared order.

    {id, owner {cell, slot, carrier}, role, storage {kind, node, slot}, membrane {patch, slot,
    inside {kind, id, slot}, outside {kind, id}, voltage}, label, reference}. Slots are today's
    array columns. The owner's carrier is its founder, which never changes in version 1 (§1.5).
    """
    cells = [c.id for c in model.cells]
    outside = [c.id for c in model.extracellular]
    patches = [p.id for p in model.membranes]
    return tuple(
        dict(
            id=c.node,
            owner=dict(cell=c.owner, slot=cells.index(c.owner), carrier=c.owner),
            role=ROLE,
            storage=dict(kind="outside_node", node=c.node, slot=outside.index(c.node)),
            membrane=dict(
                patch=c.patch,
                slot=patches.index(c.patch),
                inside=dict(kind="cell", id=c.owner, slot=cells.index(c.owner)),
                outside=dict(kind="compartment", id=c.node),
                voltage="inside minus outside: V_b = phi_owner - phi_compartment",
            ),
            label=c.label,
            reference=c.reference,
        )
        for c in declaration.compartments
    )


class CellOwnedCompartments(Operator):
    LAW_ID = LAW_ID
    DECLARATION_ONLY = True
    CONFLICTS_VIEW = CONFLICTS_VIEW

    def parse(self, raw, base, inner_model):
        return parse_declaration(raw, base)

    def to_dict(self, declaration, base):
        return declaration_to_dict(declaration)

    def check_definition(self, spec, declaration, schedule, model):
        check_definition(spec, declaration)

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return {}, {}

    def summary(self, spec, declaration, schedule, history):
        """The identity block (§1.5's run view, D154): the host-side compartment map."""
        return {
            "compartments_law": LAW_ID,
            "compartments": list(identity_map(spec.model, declaration)),
            "compartments_scope": (
                "version 1: neutral and electrically silent (no ion route on a bounding patch, a "
                "zero charge anchor, a held-bath topology), at a fixed volume; owners are never "
                "replaced, used as donors or divided"
            ),
        }
