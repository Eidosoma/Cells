"""One authority for each species' identity, standard potential and background (D174, D176).

docs/ARCHITECTURE.md, "Material identity and fuel": species identity and the background and trace
policy are consolidated at the definition boundary, so new laws add no pairwise identity checks
between operators, and each standard chemical potential has one authority. Under D176's F2, ATP,
ADP and Pi are species of this registry like any other. Host side only: nothing here reaches a
traced program.

The registry
------------
Declared on the inner model's species entries, read by the inner model's parser through
parse_entries (the core's hook; a definition declares none until it lands). Each entry may give:
* ``identity``: ``{catalogue: {catalogue, entry} | null, evidence}``, D150's form (parse_identity);
* ``standard_mu_RT``: mu°/RT, dimensionless, at the model's one ``standard_concentration_mM``
  (c0, mM; D152's convention, moved to the world). A pump that books fuel in J/mol at a 1 M
  standard state converts with dG° = RT (sum nu mu°/RT + (sum nu) ln(c0 / 1000 mM));
* ``background``: ``{trace_mM, floor_fmol}``, the trace the species is declared at where it is
  absent and its ledger floor (check_background).

Resolution of identities (identities)
-------------------------------------
The model's entries first; then the operators that declare species identities, through
``species_identities(declaration)``: authors (``IDENTITY_ROLE = "author"``, the default) in
declared order, then users (``IDENTITY_ROLE = "user"``: operators that refer to a species others
declare). The first source to declare a species' identity sets it. check_identities refuses an
operator whose identity for a species differs from the resolved one, naming that source, in the
words the pairwise checks used. So every definition without registry entries (every definition on
disk) resolves from its operator blocks with the refusals it had, and a new law adds one call, never
a pairwise check.

Moved by the step (moved_in_step)
---------------------------------
For each species, the in-step movers of its cell rows and of its outside rows, derived from
declarations and never declared by the user: the inner model's routes (membrane and junction
permeability, each channel's permeant ions, face diffusivity for outside rows), its pumps' rows
(the Na/K pump's roles, the calcium pump's role; under F2 the pump family's fuel rows), and each
operator with an in-step process, through ``moves_in_step(spec, declaration)``. An instantaneous
regulation reads only rows that nothing moves inside the step, since its factor is held through
the step: a moved row would make it lag (docs/INVENTORY_COUPLING_DESIGN.md §1.4).
"""

import math
from dataclasses import dataclass

from cells.core.specs import ConfigError, _fields

EVIDENCE_KINDS = ("label_only", "expressed_isoform", "native_current", "model")
MODEL_SOURCE = "the model's species entries"
ROLES = ("author", "user")
# Transitional, until local_species_reactions@1's owner declares species_identities (D176's round;
# the one change its owner makes): D152's identities, read from its declaration's species.
TRANSITIONAL_IDENTITIES = {
    "local_species_reactions@1": lambda declaration: tuple(s.identity for s in declaration.species),
}


@dataclass(frozen=True)
class Identity:
    catalogue: tuple | None  # (catalogue id, entry key), or None (unassigned).
    evidence: str | None  # One of EVIDENCE_KINDS when a catalogue reference is given.


@dataclass(frozen=True)
class Background:
    trace_mM: float
    floor_fmol: float


@dataclass(frozen=True)
class Entry:
    id: str
    identity: Identity | None
    standard_mu_RT: float | None
    background: Background | None


@dataclass(frozen=True)
class Declared:
    """The registry the model declares: its entries, in the model's species order."""

    entries: tuple
    standard_concentration_mM: float | None

    def entry(self, species):
        return next((e for e in self.entries if e.id == species), None)


# ------------------------------------------------------------------ parsing


def parse_catalogue(raw):
    """A catalogue reference {catalogue, entry} as (catalogue, entry), or None."""
    if raw is None:
        return None
    _fields(raw, {"catalogue", "entry"}, "catalogue reference")
    if any(type(raw[k]) is not str or not raw[k] for k in ("catalogue", "entry")):
        raise ConfigError("A catalogue reference names a catalogue and an entry")
    return (raw["catalogue"], raw["entry"])


def parse_identity(raw_catalogue, evidence, where):
    """D150's identity: a catalogue reference with its kind of evidence, or neither."""
    catalogue = parse_catalogue(raw_catalogue)
    if catalogue is None and evidence is not None:
        raise ConfigError(f"{where}: the kind of evidence is given with a catalogue reference")
    if catalogue is not None and evidence not in EVIDENCE_KINDS:
        raise ConfigError(
            f"{where}: a catalogue reference records its kind of evidence, one of "
            + ", ".join(EVIDENCE_KINDS)
        )
    return Identity(catalogue, evidence)


def _positive(value, what):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{what} must be a finite positive number")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ConfigError(f"{what} must be a finite positive number")
    return result


REGISTRY_KEYS = ("identity", "standard_mu_RT", "background")


def parse_entries(raw_species, standard_concentration_mM=None):
    """The registry of the inner model's species entries (the core parser's hook).

    raw_species: the model's species entries, each with its id and any of REGISTRY_KEYS (the
    parser has checked the rest). standard_concentration_mM: the model's c0, required when an
    entry declares standard_mu_RT."""
    entries = []
    for raw in raw_species:
        name = raw["id"]
        identity = raw.get("identity")
        if identity is not None:
            _fields(identity, {"catalogue", "evidence"}, f"species {name}'s identity")
            identity = parse_identity(
                identity["catalogue"], identity["evidence"], f"species {name}"
            )
        mu = raw.get("standard_mu_RT")
        if mu is not None:
            if isinstance(mu, bool) or not isinstance(mu, (int, float)) or not math.isfinite(mu):
                raise ConfigError(f"species {name}'s standard_mu_RT must be a finite number")
            mu = float(mu)
        background = raw.get("background")
        if background is not None:
            _fields(background, {"trace_mM", "floor_fmol"}, f"species {name}'s background")
            background = Background(
                _positive(background["trace_mM"], f"species {name}'s trace_mM"),
                _positive(background["floor_fmol"], f"species {name}'s floor_fmol"),
            )
        entries.append(Entry(name, identity, mu, background))
    if any(e.standard_mu_RT is not None for e in entries):
        if standard_concentration_mM is None:
            raise ConfigError(
                "A species standard_mu_RT is declared at the model's standard_concentration_mM, "
                "which the model does not declare"
            )
        standard_concentration_mM = _positive(
            standard_concentration_mM, "standard_concentration_mM"
        )
    if len({e.id for e in entries}) != len(entries):
        raise ConfigError("The model lists a species twice")
    return Declared(tuple(entries), standard_concentration_mM)


# ------------------------------------------------------------------ resolution


def declared(spec):
    """The model's registry, or None when it declares none."""
    return getattr(spec.model, "species_registry", None)


def _entries(spec):
    """(operator, declaration) of a composite definition, in declared order; () otherwise."""
    if not hasattr(spec.model, "operators"):
        return ()
    from cells.core import pump_composite_spec as composite_spec

    return tuple((op, declaration) for op, declaration, _ in composite_spec.entries(spec))


def operator_identities(op, declaration):
    """The identities an operator declares: its species_identities, else the transitional map."""
    method = getattr(op, "species_identities", None)
    if method is not None:
        return tuple(method(declaration))
    read = TRANSITIONAL_IDENTITIES.get(op.LAW_ID)
    return tuple(read(declaration)) if read is not None else ()


def identities(spec):
    """{species id: (source, Identity)}, resolved: the model's entries, authors, then users."""
    resolved = {}
    model = declared(spec)
    if model is not None:
        for entry in model.entries:
            if entry.identity is not None:
                resolved[entry.id] = (MODEL_SOURCE, entry.identity)
    ordered = {role: [] for role in ROLES}
    for op, declaration in _entries(spec):
        role = getattr(op, "IDENTITY_ROLE", "author")
        if role not in ROLES:
            raise ConfigError(f"{op.LAW_ID}: IDENTITY_ROLE is one of {', '.join(ROLES)}")
        ordered[role].append((op.LAW_ID, operator_identities(op, declaration)))
    for law, items in ordered["author"] + ordered["user"]:
        for item in items:
            resolved.setdefault(item.id, (law, Identity(item.catalogue, item.evidence)))
    return resolved


def check_identities(spec, law, items):
    """Refuse an item (id, catalogue, evidence) whose identity differs from its species' resolved
    identity, naming the source that set it."""
    resolved = identities(spec)
    for item in items:
        source, identity = resolved.get(item.id, (law, None))
        if source == law or identity is None:
            continue
        if (item.catalogue, item.evidence) != (identity.catalogue, identity.evidence):
            raise ConfigError(
                f"{law} declares species {item.id!r} with another identity than {source} "
                "(catalogue reference and kind of evidence must agree)"
            )


def standard_potential(spec, species):
    """(mu°/RT, c0 in mM) of a species from the model's registry, or None when not declared."""
    model = declared(spec)
    entry = None if model is None else model.entry(species)
    if entry is None or entry.standard_mu_RT is None:
        return None
    return entry.standard_mu_RT, model.standard_concentration_mM


def check_background(spec, *, rtol=1e-12):
    """Each declared background against the definition: every cell and outside node holds at least
    the trace (amount >= trace_mM x volume), and the species' ledger floor is its
    material_balance_atol_fmol."""
    model = declared(spec)
    if model is None:
        return
    m = spec.model
    tolerances = tuple(spec.execution.material_balance_atol_fmol)
    for entry in model.entries:
        if entry.background is None:
            continue
        b, row = entry.background, m.species_ids.index(entry.id)
        for node in (*m.cells, *m.extracellular):
            amount = node.initial_amount_fmol[row]
            if amount < b.trace_mM * node.volume_pL * (1.0 - rtol):
                raise ConfigError(
                    f"species {entry.id}: {node.id} holds {amount:g} fmol, below its declared "
                    f"trace {b.trace_mM:g} mM"
                )
        floor = tolerances[row] if row < len(tolerances) else None
        if floor != b.floor_fmol:
            raise ConfigError(
                f"species {entry.id}: its declared floor {b.floor_fmol:g} fmol is not its "
                f"material_balance_atol_fmol ({floor!r})"
            )


# ------------------------------------------------------------------ moved by the step


def _inner_model(spec):
    if hasattr(spec.model, "operators"):
        from cells.core import pump_composite_spec as composite_spec

        return composite_spec.projection(spec).model
    return spec.model


def moved_in_step(spec):
    """{species id: {"cell": movers, "outside": movers}}: what moves each species' rows inside the
    inner step, each mover named (module docstring). Refuses an in-step process that does not
    declare what it moves."""
    m = _inner_model(spec)
    ids = m.species_ids
    moved = {s: {"cell": [], "outside": []} for s in ids}

    def add(species, kinds, mover):
        for kind in kinds:
            if mover not in moved[species][kind]:
                moved[species][kind].append(mover)

    both = ("cell", "outside")
    for p in m.membranes:
        for row, value in enumerate(p.permeability_m_per_s):
            if value != 0:
                add(ids[row], both, f"membrane {p.id}")
        pump = getattr(p, "pump", None)
        if pump is not None:
            for species in pump.roles:
                add(species, both, f"the Na/K pump on membrane {p.id}")
        calcium = getattr(p, "calcium_pump", None)
        if calcium is not None:
            add(calcium.role, both, f"the calcium pump on membrane {p.id}")
    for j in m.junctions:
        for row, value in enumerate(j.permeability_m_per_s):
            if value != 0:
                add(ids[row], ("cell",), f"junction {j.id}")
    for c in getattr(m, "channels", ()):
        for ion in c.permeant_ions:
            if ion.relative_permeability != 0:
                add(ion.species_id, both, f"channel {c.id}")
    for f in m.faces:
        for row, value in enumerate(f.diffusivity_m2_per_s):
            if value != 0:
                add(ids[row], ("outside",), f"face {f.id}")
    for op, declaration in _entries(spec):
        if not op.PROCESS:
            continue
        method = getattr(op, "moves_in_step", None)
        if method is None:
            raise ConfigError(
                f"{op.LAW_ID} has an in-step process but does not declare what it moves "
                "(moves_in_step)"
            )
        for species, kind in method(spec, declaration):
            if kind not in both:
                raise ConfigError(f"{op.LAW_ID}: moves_in_step gives node kinds cell or outside")
            add(species, (kind,), f"{op.LAW_ID} (its in-step process)")
    return {s: {k: tuple(v) for k, v in rows.items()} for s, rows in moved.items()}
