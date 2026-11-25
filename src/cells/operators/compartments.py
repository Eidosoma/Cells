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
   term its law declares in the law registry and its kind holds by the hook that supplies it: a
   charged row by a charge slope (stage_term, in the per-stage rule), a neutral row by a material
   slope (material_term) or a definition-time material bound (material_bound, through the kind's
   bound_rate). A charge bound alone holds neither. A move whose law declares no such term is
   refused, naming the law, and so is a move with no law ID. A kind that declares no
   moved rows is admitted only as a stage read (its rows declared; no rates, moves or slope) or a
   source (none of a mover's hooks), each judged by its hooks; any other fails closed. That is
   the charged door (§3.4) and its material twin: a compartment has no face, so its charge
   relaxation is held only by B7's face-free term and, with kinds declared, by the per-stage rule
   at free outside nodes, and the material relaxation of its small volume only by its movers'
   own terms. Both rules run only with an IMEX tableau;
5. a nonzero charge anchor (version 1.2, §3.4.3 and §3.4.5), except where the world's admitted
   routes charge the compartment, since such a world must be able to resume from its own
   checkpoint: where refusal 4 admits charged routes (a world that declares kinds and steps with
   an IMEX tableau; version 1.1), and where an operator of the admitted list moves charge into
   that compartment (its routes, through the contract's charged_compartments: the pool of
   scheduled_membrane_trafficking@1's routes; version 1.2). Elsewhere (the silent version, and
   RK4 without such routes) the content is electroneutral, so q = 0 and V_b = 0. Version 1.2
   reads the composition, so it is checked at the definition with refusal 7, after it;
6. a node that is the representative of its capacitor component (cells and outside nodes joined by
   membrane patches, as numerics/surface_field.bind joins them; version 1.1, §3.5.1): the gauge
   where the component holds it, else its first outside node, and none where it holds a held bath
   (surface_field.representative, bind's own rule). Any other node is a free node of the capacitor
   solve (§3.5), in a held-bath topology, a closed world and a floating component alike;
7. a composition beyond the admitted list of §4, which fails closed: a new operator may treat
   outside nodes as environment. Replacement@1 schedules no event on an owner's slot and names no
   owner as a donor (§1.5): a newcomer would inherit the compartment's content, and a donor copy
   takes the donor's cytosolic amounts only. Providers and closers of the volumes and the masks
   are refused through CONFLICTS_VIEW by the composite's structure check: water and what requires
   it, insertion, the lumens, and S5's closers (division). The areas and capacitances are
   reference reads (D217): the declaration reads the declared bounding patch as data, its
   identity, so a provider of them is no conflict. Membrane state, which provides them, is
   admitted only together with one of its admitted writers, and only where every writer of its
   fields is one of them (the membrane-state wall's door): scheduled_membrane_trafficking@1
   (FR-2), whose routes write areas, capacitances and units, and FR-7's unit producer
   population_unit_turnover@1, which writes units only, never an area or a capacitance (the
   lead's ruling of 20 November 2026, amending that of 19 November on FR-2's question 11). The
   producer acts in its populations' cells only, and species_regulated_availability@2 reads its
   sources in its elements' cells and refuses an outside-node element (FR-7's U2 world with a
   releasing compartment, D217). FR-49 (D327; validation/fr49/REGISTRATION.md, Part H) admits two
   more laws, each with its own check:
   - templated_polymerisation@1, whose own check refuses an export into a compartment's node and
     an outside degradation there (an export into a compartment is a later step, with its books
     at the compartment's node); its routes in the owner's cytosol never touch the compartment;
   - neutral_arrival_labels@1, refused here beside membrane state (FR-49's ruling 4, World L's
     scope): today the labels refuse membrane state's admitted writers anyway, and this check
     names the reason and stays fail closed if the labels' list widens. It runs before the
     membrane-state wall's rule, so its reason is the one given.
   Site occupancy, the compartment wash and site_occupant_replacement@1 stay off the list until
   their own FR-49 pieces land.
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
from cells.models import pump_composite_adapter as adapter
from cells.numerics import surface_field
from cells.operators.contract import Operator, Read
from cells.registry import kind_registry
from cells.registry import laws as law_registry

LAW_ID = "cell_owned_compartments@1"
# Refusal 4's step terms (version 1.3, §3.4.4; docs/CORE_SEAMS_DESIGN.md §4.4 and §18 as amended).
# Each is a field the cycle and route law types declare (registry/laws.STEP_TERMS, §8.1: its
# kernel's name, or None), held at the step by the kind hook it maps to: a charge slope in the
# per-stage rule (stage_term, surface_pump_v3.membrane_rate at every free outside node, a
# face-free compartment's included), a material slope per stage (material_term,
# surface_pump_v3's material_rate), and the definition-time bounds of its charge and of its
# material relaxation (charge_bound and material_bound, both through the kind's bound_rate, which
# the IMEX step checks hold). A charged row moved at a compartment's node needs a charge slope; a
# neutral row a material slope or a material bound. A charge bound alone holds neither: it bounds
# the declared state only.
TERM_HOOKS = {
    "stage_term": "stage_term",
    "material_term": "material_term",
    "charge_bound": "bound_rate",
    "material_bound": "bound_rate",
}
CHARGE_TERMS = ("stage_term",)
MATERIAL_TERMS = ("material_term", "material_bound")
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
STATE_LAW = "membrane_entity_state@1"
# FR-2's operator (docs/MEMBRANE_RETRIEVAL_DESIGN.md; D217): named here before its module lands,
# so that the admission is on main for its builder (the lead's ruling of 19 November 2026).
TRAFFICKING_LAW = "scheduled_membrane_trafficking@1"
# FR-7's unit producer (docs/ABUNDANCE_TO_FUNCTION_DESIGN.md; D217, D232): it writes membrane
# state's units only, in its populations' cells (the lead's ruling of 20 November 2026).
PRODUCER_LAW = "population_unit_turnover@1"
# FR-49 (D327): expression, whose own check refuses exports and outside degradations at a
# compartment's node (templated_polymerisation.check_compartments), and the labels, refused here
# beside membrane state (refuse_labels_beside_membrane_state).
EXPRESSION_LAW = "templated_polymerisation@1"
LABELS_LAW = "neutral_arrival_labels@1"
# §4's admitted list (fails closed). @3 itself is the composite's inner model. Membrane state is
# admitted only together with one of its admitted writers (check_definition).
ADMITTED = (
    LAW_ID,
    "electrode_current_injection@1",
    "scheduled_species_exchange@1",
    "scheduled_species_turnover@1",
    "local_species_reactions@1",
    "species_regulated_availability@1",
    REPLACEMENT_LAW,
    "scheduled_bath_composition@1",
    STATE_LAW,
    TRAFFICKING_LAW,
    "species_regulated_availability@2",
    PRODUCER_LAW,
    EXPRESSION_LAW,
    LABELS_LAW,
)
# Membrane state's fields that its writers write (membrane_state.ACCEPTS_WRITES): the wall's door
# admits a writer of any of them only if it is one of the admitted writers (check_definition).
STATE_FIELDS = (
    "membrane_area_increment_m2",
    "membrane_capacitance_increment_F",
    "population_abundance_increment",
)
# Read as declared: the volumes and the activity masks (§1.4, 7).
CONFLICTS_VIEW = (
    "volume",
    "extracellular_volume",
    "active",
    "outside_active",
    "membrane_active",
    "channel_active",
    "junction_active",
    "face_active",
)
# The areas and capacitances are reference reads (D217; docs/MEMBRANE_RETRIEVAL_DESIGN.md §6): the
# declaration's identity checks read the declared bounding patch as data, so a provider of them
# (membrane state, written by trafficking) is no conflict. A declaration's reads are unscoped
# reference reads (the contract's DECLARATION_ONLY), at end, a stage a part-less operator's read
# may name; a reference read takes the bound value whatever its stage.
SCOPED_READS = {
    "membrane_area": Read("reference", "end"),
    "membrane_capacitance": Read("reference", "end"),
}
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


def representatives(model):
    """The outside nodes that the capacitor solve fixes as representatives, their IDs: one per
    capacitor component without a held bath. surface_field.representative, the rule that bind
    applies, on the declared topology; a bound layout's are surface_field.representatives."""
    nodes = [c.id for c in (*model.cells, *model.extracellular)]
    first = len(model.cells)
    reservoirs = {first + k for k, o in enumerate(model.extracellular) if o.reservoir}
    gauge = {first + k for k, o in enumerate(model.extracellular) if o.id == model.gauge_reference}
    components, members = capacitor_components(model), {}
    for k, name in enumerate(nodes):
        members.setdefault(components[name], []).append(k)
    chosen = [
        surface_field.representative(found, first, reservoirs, gauge) for found in members.values()
    ]
    return frozenset(nodes[k] for k in chosen if k is not None)


def held_terms(kind, law_id):
    """The step terms a move under `law_id` by `kind` has: those of TERM_HOOKS that the law
    declares in the active law registry and that the kind moving it holds by the hook each maps
    to, with the reason when there are none. `kind` is the kind bound to its declaration's
    structure entry (refuse_kind_moves), whose hooks the step runs. Read by law ID, so a planted
    kind that reuses a law's ID (FR-4's K2) is admitted on the law's declaration only where it
    keeps the hooks the law names. A move with no law ID, an unregistered law and a law another
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
    declared = [t for t in TERM_HOOKS if getattr(law, t, None)]
    held = tuple(t for t in declared if getattr(kind, TERM_HOOKS[t], None) is not None)
    if not declared:
        return held, "declares no step term"
    holds = ", ".join(held) or "none"
    return held, f"declares {', '.join(declared)}, of which its kind holds {holds}"


def refuse_kind_moves(model, node, kind_id, declaration):
    """Refusal 4's kinds, per move (version 1.3, docs/CLOSED_COMPARTMENT_DESIGN.md §3.4.4): every
    row the kind moves at the compartment's node is held by its law's declared step term (a
    charged row by a charge slope, a neutral row by a material slope or a material bound); a kind
    that declares no moved rows is admitted as a stage read or a source, by its hooks. Every
    hook is read on the kind bound to the declaration's structure entry
    (pump_composite_adapter.bound_kind), as the inner model binds it, never on the static kind,
    which may differ per entry: a static read could admit what the bound kind refuses (fail-open;
    the lead's bound-kind sweep, CORE_SEAMS §18)."""
    kind = adapter.bound_kind(kind_registry.active().lookup(kind_id), declaration)
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
                    else "a material slope (material_term) or a definition-time material bound "
                    "(material_bound, through the kind's bound_rate)"
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


def refuse_charge_anchor(node, compartment, kinds=False, imex=False, into=(), charging=()):
    """Refusal 5 (version 1.2, docs/CLOSED_COMPARTMENT_DESIGN.md §3.4.3 and §3.4.5): a nonzero
    charge anchor is admitted only where the world's admitted routes charge the compartment, since
    such a world must be able to resume from its own checkpoint:
    - version 1.1: where refusal 4 admits charged routes on its bounding patch, a world that
      declares kinds (`kinds`) and steps with an IMEX tableau (`imex`);
    - version 1.2: where an operator of the admitted list moves charge into the compartment
      (`into`: the laws whose routes charge it, through the contract's charged_compartments),
      whatever the solver: its pool keeps no conductance of its own, and V_b = -q/C_b holds at any
      q (§3.1).
    Elsewhere, the silent version (§3.3) and under RK4, the content is electroneutral, so V_b = 0
    (fails closed). `charging`: the laws of the composition whose routes charge any compartment.
    Where there is none, version 1.1's message is kept byte for byte, since FR-1's judged refusal
    record holds it; otherwise the message names them. Called with positional arguments only: the
    silence tests and FR-1's plants bypass it with a positional lambda."""
    if compartment.initial_charge_C == 0.0 or (kinds and imex) or into:
        return
    if not charging:
        raise ConfigError(
            f"{LAW_ID}: compartment {node!r} declares a nonzero charge anchor "
            f"({compartment.initial_charge_C} C); version 1.1 admits one only where charged "
            "routes are admitted on its bounding patch (a world that declares kinds and steps "
            "with an IMEX tableau); elsewhere the content is electroneutral, so V_b = 0"
        )
    raise ConfigError(
        f"{LAW_ID}: compartment {node!r} declares a nonzero charge anchor "
        f"({compartment.initial_charge_C} C), and no route of {', '.join(charging)} moves charge "
        "into it; version 1.2 admits one only where charged routes are admitted on its bounding "
        "patch (a world that declares kinds and steps with an IMEX tableau) or where an admitted "
        "operator's routes move charge into the compartment; elsewhere the content is "
        "electroneutral, so V_b = 0"
    )


def charged_by(spec, declaration, entries):
    """{compartment ID: (law, ...)}: the operators whose routes charge each compartment (the
    contract's charged_compartments, host side), in declared order; entries are the composite's,
    every operator already on the admitted list. An ID this declaration does not declare is
    refused (fails closed): a route's charge then reaches no compartment refusal 5 judges."""
    declared = {c.id for c in declaration.compartments}
    into = {}
    for op, d, _ in entries:
        for cid in op.charged_compartments(spec, d):
            if cid not in declared:
                raise ConfigError(
                    f"{LAW_ID}: {op.LAW_ID}'s routes charge {cid!r}, which is not a compartment "
                    "this declaration declares (fails closed)"
                )
            laws = into.setdefault(cid, [])
            if op.LAW_ID not in laws:
                laws.append(op.LAW_ID)
    return {cid: tuple(laws) for cid, laws in into.items()}


def parse_declaration(raw, base):
    _fields(raw, {"law", "compartments"}, "compartments declaration")
    if raw["law"] != LAW_ID:
        raise ConfigError("A compartments declaration requires law " + LAW_ID)
    if type(raw["compartments"]) is not list or not raw["compartments"]:
        raise ConfigError(f"{LAW_ID} declares its compartments in a non-empty list")
    m = base.model
    outside = {c.id: c for c in m.extracellular}
    cells = {c.id for c in m.cells}
    fixed = representatives(m)
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
        # 5. is checked at the definition (check_definition): version 1.2 reads the composition.
        # 6. Never its component's representative.
        if node in fixed:
            raise ConfigError(
                f"{LAW_ID}: compartment {node!r} is the representative of its capacitor component "
                f"(no held bath and no gauge is in it, and {node!r} is its first outside node); "
                "the capacitor solve fixes a representative, so its row would carry the "
                "component's net charge. Declare another outside node of the component first "
                "(refusal 6, version 1.1)"
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


def refuse_unwritten_state(entries):
    """7. Membrane state beside a compartment only together with one of its admitted writers, and
    only where every writer of its fields is one of them (the membrane-state wall's door). The
    writers: trafficking (FR-2, D217; the lead's ruling of 19 November 2026 on its question 11),
    which writes every patch's area and capacitance, a bounding patch's included, and units; and
    FR-7's unit producer, which writes units only (the lead's ruling of 20 November 2026). Alone,
    membrane state would provide the declared values only, a composition no world needs, so it
    fails closed; any other writer of its fields is refused, whatever the admitted list holds.
    The writers are read when the check runs, so a stand-in may take trafficking's place."""
    writers = (TRAFFICKING_LAW, PRODUCER_LAW)
    laws = [op.LAW_ID for op, _, _ in entries]
    if STATE_LAW not in laws:
        return
    if not set(writers) & set(laws):
        raise ConfigError(
            f"{LAW_ID} admits {STATE_LAW} only together with {TRAFFICKING_LAW} or "
            f"{PRODUCER_LAW}: membrane state provides every patch's area and capacitance, a "
            "bounding patch's included, and they are the writers of its fields on its admitted "
            "list (trafficking of areas, capacitances and units; the producer of units only), so "
            "alone it is a composition no world needs (fails closed)"
        )
    for op, _, _ in entries:
        written = [field for field in STATE_FIELDS if field in op.ENTITY_WRITES]
        if written and op.LAW_ID not in writers:
            raise ConfigError(
                f"{LAW_ID} admits {STATE_LAW} only where every writer of its fields is "
                f"{TRAFFICKING_LAW} or {PRODUCER_LAW}; {op.LAW_ID} writes its {written[0]} "
                "(fails closed)"
            )


def refuse_labels_beside_membrane_state(entries):
    """7. FR-49's ruling 4 (D327): neutral_arrival_labels@1 is qualified beside a compartment
    without membrane state (fr49-compartment-compositions-v1, World L), so a compartment world
    that declares both is refused by name. Today the labels refuse membrane state's admitted
    writers beside a compartment (trafficking and the unit producer), and membrane state alone is
    the wall's own refusal, so no admitted world changes. The check names the reason and keeps the
    pair refused if the labels' list widens before a world qualifies it."""
    laws = {op.LAW_ID for op, _, _ in entries}
    if LABELS_LAW in laws and STATE_LAW in laws:
        raise ConfigError(
            f"{LAW_ID}: {LABELS_LAW} beside a compartment is qualified without {STATE_LAW} "
            "(FR-49's World L; ruling 4), so a compartment world that declares both is refused "
            "until a world qualifies labels beside membrane state there"
        )


def check_definition(spec, declaration):
    """7. The admitted list, which fails closed, replacement@1's owners, the labels without
    membrane state (FR-49), and membrane state only with its admitted writers; then 5. (version
    1.2), which reads the admitted operators' routes."""
    owners = {c.owner for c in declaration.compartments}
    entries = composite_spec.entries(spec)
    for op, _, schedule in entries:
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
    refuse_labels_beside_membrane_state(entries)  # FR-49: before the wall's rule, so its reason.
    refuse_unwritten_state(entries)
    # 5., version 1.2: per compartment, in declared order (positional: bypasses in the silence
    # tests and FR-1's plants replace it with a positional-only lambda).
    into = charged_by(spec, declaration, entries)
    charging = tuple(dict.fromkeys(law for laws in into.values() for law in laws))
    m = spec.model
    outside = {c.id: c for c in m.extracellular}
    kinds, imex = bool(getattr(m, "kinds", ())), spec.execution.solver != RK4_SOLVER
    for c in declaration.compartments:
        refuse_charge_anchor(c.node, outside[c.node], kinds, imex, into.get(c.id, ()), charging)


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
    SCOPED_READS = SCOPED_READS

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
                "refusal 4 version 1.3, refusal 5 version 1.2, refusal 6 version 1.1: a node that "
                "its capacitor component does not take as its representative, at a fixed volume; "
                "on a bounding patch no ion route but refusal 4's admitted ones (@3's "
                "permeabilities, and the kinds' moves at the compartment's node, each held by a "
                "step term its law declares, when the world declares kinds, with an IMEX step), "
                "and a zero charge anchor except in those same worlds and where an admitted "
                "operator's routes move charge into the compartment (trafficking's pool); a "
                "bounding patch's area and capacitance change only by trafficking; owners are "
                "never replaced, used as donors or divided"
            ),
        }
