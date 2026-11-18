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
4. an ion route on the bounding patch (version 1.3, §3.4.1, §3.4.2 and §3.4.4). @3's own routes
   keep version 1.2's rule: a Na/K or Ca pump or a channel population is refused, a nonzero
   permeability unless the world declares kinds, and, under an RK4 step, any declared kind, so
   that version 1's refusal stands there. The kinds are checked per move, not per kind
   (docs/CORE_SEAMS_DESIGN.md §4.4): every row a kind moves at the compartment's node (a move
   across the bounding patch moves its row there, at the patch's outside end) is held by a step
   term its law declares in the law registry and its kind holds by the hook of that name: a
   charged row by a charge slope (stage_term, in the per-stage rule), a neutral row by a material
   slope (material_term) or a definition-time bound (bound_rate). A move whose law declares no
   such term is refused, naming the law, and so is a move with no law ID. A kind that declares no
   moved rows is admitted only as a stage read (its rows declared; no rates, moves or slope) or a
   source (none of a mover's hooks), each judged by its hooks; any other fails closed. That is
   the charged door (§3.4) and its material twin: a compartment has no face, so its charge
   relaxation is held only by B7's face-free term and, with kinds declared, by the per-stage rule
   at free outside nodes, and the material relaxation of its small volume only by its movers'
   own terms. Both rules run only with an IMEX tableau;
5. a nonzero charge anchor (version 1.1, §3.4.3), except where refusal 4 admits charged routes (a
   world that declares kinds and steps with an IMEX tableau), since such a world must be able to
   resume from its own checkpoint; elsewhere (the silent version, and RK4) the content is
   electroneutral, so q = 0 and V_b = 0;
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

from cells.definitions import pump_composite_spec as composite_spec
from cells.definitions.spec_values import identifier
from cells.definitions.specs import ConfigError, _fields
from cells.operators.contract import Operator
from cells.registry import kind_registry
from cells.registry import laws as law_registry

LAW_ID = "cell_owned_compartments@1"
# Refusal 4's step terms (version 1.3, §3.4.4; docs/CORE_SEAMS_DESIGN.md §4.4). Each is a field a
# law declares on the law template (registry/laws.py, §8.1: its kernel's name, or None) and the
# kind hook of the same name that holds it at the step: a charge slope in the per-stage rule
# (stage_term, surface_pump_v3.membrane_rate at every free outside node, a face-free
# compartment's included), a material slope per stage (material_term, surface_pump_v3's
# material_rate) or a definition-time bound (bound_rate, the IMEX step checks). A charged row
# moved at a compartment's node needs a charge slope; a neutral row a material slope or a bound.
CHARGE_TERMS = ("stage_term",)
MATERIAL_TERMS = ("material_term", "bound_rate")
# A kind that declares no moved rows is admitted only by its hooks (never its ID), as one of two
# non-movers. A stage read (B4's buffer): it declares the rows it reads (stage_rows), and has no
# rates, so no move and no slope; the read changes the concentrations the stage's rates see, never
# charge. A source (version 1.2's routing-door kinds, §3.4.2: FR-5's damage and pH condition): it
# has none of a mover's hooks, so its factors reach routes only through the door, whose [0, 1]
# rule bounds each route at the slope its own terms declare. Anything else fails closed.
STAGE_READ_ABSENT = ("rates", "stage_term", "material_term", "bound_rate")
SOURCE_ABSENT = (
    "stage_term",
    "material_term",
    "bound_rate",
    "held_rows",
    "stage_read",
    "stage_check",
    "ledger_terms",
)
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


def held_terms(kind, law_id):
    """The step terms a move under `law_id` by `kind` has: those of CHARGE_TERMS and
    MATERIAL_TERMS that the law declares in the active law registry and that the kind moving it
    holds by its hook of the same name, with the reason when there are none. Read by law ID, so a
    planted kind that reuses a law's ID (FR-4's K2) is admitted on the law's declaration only where
    it keeps the hooks the law names. A move with no law ID, an unregistered law and a law another
    kind hosts have none (fails closed)."""
    if law_id is None:
        return (), "names no law (a moved row without a law ID)"
    laws = law_registry.active()
    if law_id not in laws:
        return (), "is not a registered law"
    law = laws.lookup(law_id)
    host = kind_registry.qualified(law.host)
    if host != kind_registry.qualified(kind.kind_id):
        return (), f"is hosted by {host}, whose hooks hold its terms"
    declared = [t for t in (*CHARGE_TERMS, *MATERIAL_TERMS) if getattr(law, t, None)]
    held = tuple(t for t in declared if getattr(kind, t, None) is not None)
    if not declared:
        return held, "declares no step term"
    holds = ", ".join(held) or "none"
    return held, f"declares {', '.join(declared)}, of which its kind holds {holds}"


def refuse_kind_moves(model, node, kind_id, declaration):
    """Refusal 4's kinds, per move (version 1.3, docs/CLOSED_COMPARTMENT_DESIGN.md §3.4.4): every
    row the kind moves at the compartment's node is held by its law's declared step term (a
    charged row by a charge slope, a neutral row by a material slope or a definition-time bound);
    a kind that declares no moved rows is admitted as a stage read or a source, by its hooks."""
    kind = kind_registry.active().lookup(kind_id)
    if kind.moved_rows is None:
        if kind.stage_read is not None:  # A stage read, which declares its rows.
            wrong = [f"has {h}" for h in STAGE_READ_ABSENT if getattr(kind, h) is not None]
            if kind.stage_rows is None:
                wrong.append("declares no stage_rows for its stage read")
        else:  # A source.
            wrong = [f"has {h}" for h in SOURCE_ABSENT if getattr(kind, h) is not None]
        if wrong:
            raise ConfigError(
                f"{LAW_ID}: compartment {node!r} is declared with the kind {kind_id}, which "
                "declares no moved rows, so version 1.3 admits it only as a stage read (its "
                f"stage_rows declared, and none of {', '.join(STAGE_READ_ABSENT)}) or a source "
                f"(none of {', '.join(SOURCE_ABSENT)}); it {' and '.join(wrong)}, so its moves "
                "at the compartment's node cannot be placed (fails closed)"
            )
        return
    valence = dict(zip(model.species_ids, model.valence, strict=True))
    for entry in kind.moved_rows(declaration):
        species, at, law = (*entry, None) if len(entry) == 2 else entry
        if at != node:
            continue
        charged = valence[species] != 0
        need = CHARGE_TERMS if charged else MATERIAL_TERMS
        terms, why = held_terms(kind, law)
        if not set(terms) & set(need):
            raise ConfigError(
                f"{LAW_ID}: compartment {node!r}: the kind {kind_id} moves "
                f"{'the charged' if charged else 'the neutral'} row {species} at its node under "
                f"{law or 'no law'}, which {why}; version 1.3 admits a move at a compartment's "
                "node only where its law declares, and its kind holds, "
                + (
                    "a charge slope (stage_term), which the per-stage rule holds there"
                    if charged
                    else "a material slope (material_term) or a definition-time bound (bound_rate)"
                )
                + " (fails closed)"
            )


def refuse_ion_routes(model, node, bounding, imex):
    """Refusal 4 (version 1.3, docs/CLOSED_COMPARTMENT_DESIGN.md §3.4.1, §3.4.2 and §3.4.4), the
    charged door. @3's own routes keep version 1.2's rule: on the bounding patch @3's Na/K or Ca
    pump and channel populations are refused, and a constant-field permeability unless the world
    declares kinds (only then does the per-stage rule hold the compartment's node); that refusal's
    message is version 1.2's, byte for byte, since FR-1's judged refusal record holds it. `imex`
    is whether @3 steps with an IMEX tableau: under RK4 neither the per-stage rule nor the
    definition-time terms run, so no declared kind is admitted beside a compartment and version
    1's refusal stands. With an IMEX tableau each declared kind is checked per move
    (refuse_kind_moves), in canonical kind order."""
    kinds = [kind_id for kind_id, _ in getattr(model, "kinds", ())]
    pumps = [p.id for p in (bounding.pump, bounding.calcium_pump) if p is not None]
    channels = [c.id for c in model.channels if c.membrane_id == bounding.id]
    if pumps or channels:
        raise ConfigError(
            f"{LAW_ID}: the bounding patch {bounding.id!r} of compartment {node!r} carries an ion "
            f"route refusal 4 refuses there, {', '.join(pumps + channels)} (a Na/K or Ca pump, "
            "or a channel population): the per-stage rule does not hold its slope at the "
            "compartment's node (a pump's slope is in no per-stage term, a channel's gating "
            "slope neither), so on a bounding patch refusal 4 admits only @3's constant-field "
            "permeability and the kinds' moves that their laws' step terms hold"
        )
    if any(v != 0.0 for v in bounding.permeability_m_per_s) and not kinds:
        raise ConfigError(
            f"{LAW_ID}: the bounding patch {bounding.id!r} of compartment {node!r} carries an ion "
            "route, a nonzero constant-field permeability, in a world that declares no kind. "
            "Version 1.2 admits it only when the world declares kinds and steps with an IMEX "
            "tableau: only then does the per-stage rule hold the compartment's node at every "
            "stage, where B7's definition-time term holds only the declared state"
        )
    if kinds and not imex:
        raise ConfigError(
            f"{LAW_ID}: compartment {node!r} is declared with kinds in a world that steps with "
            "RK4. Refusal 4 admits kinds and a constant-field permeability on a bounding patch "
            "only with an IMEX tableau, whose per-stage rule and definition-time bound terms hold "
            "the compartment's node; an RK4 step runs neither, so version 1's refusal stands "
            "(fails closed)"
        )
    for kind_id, declaration in getattr(model, "kinds", ()):
        refuse_kind_moves(model, node, kind_id, declaration)


def refuse_charge_anchor(node, compartment, kinds=False, imex=False):
    """Refusal 5 (version 1.1, docs/CLOSED_COMPARTMENT_DESIGN.md §3.4.3): a nonzero charge anchor
    is admitted only where refusal 4 admits charged routes on the bounding patch, a world that
    declares kinds (`kinds`) and steps with an IMEX tableau (`imex`): a world whose admitted
    routes charge the lumen must be able to resume from its own checkpoint. Elsewhere, the silent
    version (§3.3) and under RK4, the content is electroneutral, so V_b = 0 (fails closed)."""
    if compartment.initial_charge_C != 0.0 and not (kinds and imex):
        raise ConfigError(
            f"{LAW_ID}: compartment {node!r} declares a nonzero charge anchor "
            f"({compartment.initial_charge_C} C); version 1.1 admits one only where charged "
            "routes are admitted on its bounding patch (a world that declares kinds and steps "
            "with an IMEX tableau); elsewhere the content is electroneutral, so V_b = 0"
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
        # 5., version 1.1: where refusal 4 admits charged routes (positional: bypasses in the
        # silence tests replace it with a positional-only lambda).
        refuse_charge_anchor(node, outside[node], bool(getattr(m, "kinds", ())), imex)
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
                "refusal 4 version 1.3, refusal 5 version 1.1: a held-bath topology at a fixed "
                "volume; on a bounding patch no ion route but refusal 4's admitted ones (@3's "
                "permeabilities, and the kinds' moves at the compartment's node, each held by a "
                "step term its law declares, when the world declares kinds, with an IMEX step), "
                "and a zero charge anchor except in those same worlds; owners are never replaced, "
                "used as donors or divided"
            ),
        }
