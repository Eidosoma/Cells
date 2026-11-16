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
4. an ion route on the bounding patch (version 1.1, §3.4.1): a Na/K or Ca pump or a channel
   population; a nonzero permeability unless the world declares kinds; any declared kind outside
   the known ones (ROUTE_KINDS, READ_KINDS), which fails closed; and, under an RK4 step, any
   declared kind, so that version 1's refusal stands there. That is the charged door (§3.4): a
   compartment has no face, so its charge relaxation is held only by B7's face-free term and,
   with kinds declared, by the per-stage rule at free outside nodes, where the known kinds'
   charged routes put their slopes (ROUTE_KINDS' comment names the neutral laws' terms). Both run
   only with an IMEX tableau;
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
its declared ID, its owner, its declared role, its storage and its oriented bounding membrane. The
ID is the compartment's own: a declared string, unique among every ID of the world (the node's
included), so the map does not depend on today's storage as an outside node, which is one field of
it. The role is a declared short string, "lumen" by default when the declaration omits it (the map
and the summary record which). **No physics depends on the role in version 1**: it is metadata,
like the label, carried to the map, the summary and later the run view. Every version-1
compartment lies outside its bounding membrane, whose inside is the owner's cytosol (§1.1), so
V_b = phi_owner - phi_compartment is @3's patch voltage, whatever its role.
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
# Refusal 4's known kinds (version 1.1, §3.4.1). Their charged routes on a bounding patch (the
# transporter's proton law, the passive routes' proton leak) put their slopes at the compartment's
# node through stage_term, which the per-stage rule holds; the proton law also has a
# definition-time bound_rate, the leak none. The passive neutral law moves no charge: its
# definition-time bound_rate (dt L <= 1, the compartment's own volume in L) holds its material
# relaxation. The transporter's neutral law has neither term: its material stiffness at a small
# node is an open question (§3.4.1), not the charged door's. The buffer is a stage read and
# declares no route. Any other declared kind is refused while a compartment is declared.
ROUTE_KINDS = ("cells.passive_routes@1", "cells.transporter@1")
READ_KINDS = ("cells.rapid_proton_buffer@1",)
# @3's step for an empty tableau (surface_pump_v3.checked_step). Every other solver steps with
# imex_step, whose per-stage rule holds a compartment's node, and only those solvers' step checks
# hold B7's and the kinds' definition-time terms (surface_pump_v3.StepChecks). Refusal 4 admits
# routes beside a compartment only with an IMEX tableau (§3.4.1).
RK4_SOLVER = "rk4"
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
COMPARTMENT_FIELDS = {"id", "node", "patch", "owner", "label", "reference"}
OPTIONAL_FIELDS = {"role"}
ROLE = "lumen"  # The default role when a declaration omits it; no physics depends on a role.
ROLE_LENGTH = 40  # A role is a short string.


@dataclass(frozen=True)
class Compartment:
    id: str  # The compartment's own stable ID, unique among the world's IDs.
    node: str  # Its storage today: its @3 outside node.
    patch: str  # Its bounding patch.
    owner: str  # The owner's cell id: the founder carrier, which never changes (version 1).
    role: str  # A short string; metadata only in version 1.
    role_declared: bool  # False when the declaration omitted the role (the default ROLE).
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


def world_ids(model):
    """Every ID the world declares: species, cells, outside nodes, patches, pumps, junctions,
    faces and channel populations."""
    ids = {*model.species_ids}
    ids |= {c.id for c in (*model.cells, *model.extracellular)}
    ids |= {p.id for p in model.membranes}
    ids |= {pump.id for p in model.membranes for pump in (p.pump, p.calcium_pump) if pump}
    ids |= {j.id for j in model.junctions} | {f.id for f in model.faces}
    return ids | {c.id for c in model.channels}


def _role(entry):
    """(role, declared): a declared short string, or the default ROLE."""
    if "role" not in entry:
        return ROLE, False
    role = entry["role"]
    if type(role) is not str or not role.strip() or role != role.strip() or len(role) > ROLE_LENGTH:
        raise ConfigError(
            f"{LAW_ID}: a compartment's role is a short string (1 to {ROLE_LENGTH} characters, no "
            "surrounding spaces); no physics depends on it in version 1"
        )
    return role, True


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


def refuse_ion_routes(model, node, bounding, imex):
    """Refusal 4 (version 1.1, docs/CLOSED_COMPARTMENT_DESIGN.md §3.4.1), the charged door: on
    the bounding patch @3's Na/K or Ca pump and channel populations are refused, and a
    constant-field permeability unless the world declares kinds (only then does the per-stage
    rule hold the compartment's node); a declared kind outside ROUTE_KINDS and READ_KINDS is
    refused, since its routes may cross the patch (fails closed). `imex` is whether @3 steps with
    an IMEX tableau: under RK4 neither the per-stage rule nor the definition-time terms run, so no
    declared kind is admitted beside a compartment and version 1's refusal stands."""
    kinds = [kind_id for kind_id, _ in getattr(model, "kinds", ())]
    pumps = [p.id for p in (bounding.pump, bounding.calcium_pump) if p is not None]
    channels = [c.id for c in model.channels if c.membrane_id == bounding.id]
    if pumps or channels:
        raise ConfigError(
            f"{LAW_ID}: the bounding patch {bounding.id!r} of compartment {node!r} carries an ion "
            f"route version 1.1 refuses there, {', '.join(pumps + channels)} (a Na/K or Ca pump, "
            "or a channel population): the per-stage rule does not hold its slope at the "
            "compartment's node (a pump's slope is in no per-stage term, a channel's gating "
            "slope neither), so on a bounding patch version 1.1 admits only @3's constant-field "
            "permeability and the known kinds' routes"
        )
    if any(v != 0.0 for v in bounding.permeability_m_per_s) and not kinds:
        raise ConfigError(
            f"{LAW_ID}: the bounding patch {bounding.id!r} of compartment {node!r} carries an ion "
            "route, a nonzero constant-field permeability, in a world that declares no kind. "
            "Version 1.1 admits it only when the world declares kinds and steps with an IMEX "
            "tableau: only then does the per-stage rule hold the compartment's node at every "
            "stage, where B7's definition-time term holds only the declared state"
        )
    if kinds and not imex:
        raise ConfigError(
            f"{LAW_ID}: compartment {node!r} is declared with kinds in a world that steps with "
            "RK4. Version 1.1 admits kinds and a constant-field permeability on a bounding patch "
            "only with an IMEX tableau, whose per-stage rule and definition-time bound terms hold "
            "the compartment's node; an RK4 step runs neither, so version 1's refusal stands "
            "(fails closed)"
        )
    unknown = sorted(k for k in kinds if k not in ROUTE_KINDS + READ_KINDS)
    if unknown:
        raise ConfigError(
            f"{LAW_ID}: compartment {node!r} is declared with the kind(s) {', '.join(unknown)}, "
            "which refusal 4 does not know: a kind's routes may cross its bounding patch "
            f"{bounding.id!r}, so version 1.1 admits only {', '.join(ROUTE_KINDS + READ_KINDS)} "
            "(fails closed)"
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
    imex = base.execution.solver != RK4_SOLVER  # Refusal 4's admissions need an IMEX tableau.
    taken = world_ids(m)
    compartments = []
    for entry in raw["compartments"]:
        if not isinstance(entry, dict):
            raise ConfigError(f"{LAW_ID}: each compartment is an object")
        _fields(
            {k: v for k, v in entry.items() if k not in OPTIONAL_FIELDS},
            COMPARTMENT_FIELDS,
            "compartment",
        )
        node, patch, owner = (identifier(entry[k]) for k in ("node", "patch", "owner"))
        # The compartment's own ID: unique among the world's IDs and the other compartments'.
        cid = identifier(entry["id"])
        if cid in taken:
            raise ConfigError(
                f"{LAW_ID}: the compartment ID {cid!r} collides with an ID the world already "
                "declares (a compartment's ID is its own, distinct from its node's)"
            )
        if cid in {c.id for c in compartments}:
            raise ConfigError(f"{LAW_ID}: the compartment ID {cid!r} is declared twice")
        role, role_declared = _role(entry)
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
        refuse_ion_routes(m, node, bounding, imex)  # 4.
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
        compartments.append(
            Compartment(cid, node, patch, owner, role, role_declared, label, reference)
        )
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
            dict(
                id=c.id,
                node=c.node,
                patch=c.patch,
                owner=c.owner,
                **(dict(role=c.role) if c.role_declared else {}),
                label=c.label,
                reference=c.reference,
            )
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

    {id, owner {cell, slot, carrier}, role, role_declared, storage {kind, node, slot}, membrane
    {patch, slot, inside {kind, id, slot}, outside {kind, id}, voltage}, label, reference}. The ID
    and the role are the declared ones (role_declared False: the default ROLE); the node is storage.
    Slots are today's array columns. The owner's carrier is its founder, which never changes in
    version 1 (§1.5). No physics depends on the role in version 1.
    """
    cells = [c.id for c in model.cells]
    outside = [c.id for c in model.extracellular]
    patches = [p.id for p in model.membranes]
    return tuple(
        dict(
            id=c.id,
            owner=dict(cell=c.owner, slot=cells.index(c.owner), carrier=c.owner),
            role=c.role,
            role_declared=c.role_declared,
            storage=dict(kind="outside_node", node=c.node, slot=outside.index(c.node)),
            membrane=dict(
                patch=c.patch,
                slot=patches.index(c.patch),
                inside=dict(kind="cell", id=c.owner, slot=cells.index(c.owner)),
                outside=dict(kind="compartment", id=c.id),
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
            "compartments_role_default": ROLE,  # Entries with role_declared False carry it.
            "compartments_role_physics": "none in version 1: a role is metadata",
            "compartments_scope": (
                "version 1.1: a zero charge anchor and a held-bath topology at a fixed volume; "
                "on a bounding patch no ion route but refusal 4's admitted ones (the known "
                "kinds' routes, and @3's permeabilities when the world declares kinds, with an "
                "IMEX step); owners are never replaced, used as donors or divided"
            ),
        }
