"""One authority for each species' identity, standard potential and background (D174, D176).

docs/ARCHITECTURE.md, "Material identity and fuel": species identity and the background and trace
policy are consolidated at the definition boundary, so new laws add no pairwise identity checks
between operators, and each standard chemical potential has one authority. Under D176's F2, ATP,
ADP and Pi are species of this registry like any other. Host side only: nothing here reaches a
traced program.

The registry
------------
Declared on the inner model's species entries, read by the inner model's parser through
parse_entries (the core's hook, docs/INNER_MODEL_V4_DESIGN.md §7.4 (f) 7: it pops these keys
from the parser's copy of the model and the model's standard_concentration_mM; to_entries writes
them back). Each entry may give:
* ``identity``: ``{catalogue: {catalogue, entry} | null, evidence}``, D150's form (parse_identity);
* ``standard_mu_RT``: mu°/RT, dimensionless, at the model's one ``standard_concentration_mM``
  (c0, mM; D152's convention, moved to the world). A pump that books fuel in J/mol at a 1 M
  standard state converts with dG° = RT (sum nu mu°/RT + (sum nu) ln(1000 mM / c0)), since
  mu°(1 M) = mu°(c0) + RT ln(1000 mM / c0);
* ``protonated_standard_mu_RT``: for a row with two forms (a buffer: the row holds its total), the
  mu°/RT of the form with one more proton, at valence z + 1 (the row's ``standard_mu_RT`` is the
  base form's, at the row's valence z, so scalar readers are unaffected). With the proton row's
  potential it gives the dissociation constant HB <-> B + H at c0 (dissociation_constant_mM, pK).
  A route or reaction that names a two-form row is refused (check_two_form_rows): the row is
  inert until a law declares how it moves the forms (the lead, 15 November 2026);
* ``background``: ``{trace_mM, floor_fmol}``, the trace the species is declared at where it is
  absent and its ledger floor (check_background). With a registry declared, a row is never an
  exact zero at a node: an absent row is a declared trace (operators/PLAN.md §2.4, accepted).

check_definition runs the definition-time checks (background and absent rows, two-form rows); the
core's hook calls it ahead of the inner model's own checks, so its messages come first.

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
    standard_mu_RT: float | None  # The base form's, at the row's valence z.
    background: Background | None
    protonated_standard_mu_RT: float | None = None  # The form at z + 1, for a two-form row.


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


REGISTRY_KEYS = ("identity", "standard_mu_RT", "protonated_standard_mu_RT", "background")
MODEL_KEY = "standard_concentration_mM"


def _potential(value, what):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ConfigError(f"{what} must be a finite number")
    return float(value)


def build(raw_entries, standard_concentration_mM=None):
    """The registry of entries {id, any of REGISTRY_KEYS}, in the model's species order, at c0
    (mM; required when an entry declares a potential)."""
    entries = []
    for raw in raw_entries:
        name = raw["id"]
        identity = raw.get("identity")
        if identity is not None:
            _fields(identity, {"catalogue", "evidence"}, f"species {name}'s identity")
            identity = parse_identity(
                identity["catalogue"], identity["evidence"], f"species {name}"
            )
        mu = raw.get("standard_mu_RT")
        if mu is not None:
            mu = _potential(mu, f"species {name}'s standard_mu_RT")
        protonated = raw.get("protonated_standard_mu_RT")
        if protonated is not None:
            protonated = _potential(protonated, f"species {name}'s protonated_standard_mu_RT")
            if mu is None:
                raise ConfigError(
                    f"species {name} declares a protonated form's potential without its base "
                    "form's: give standard_mu_RT (the base form, at the row's valence) too"
                )
        background = raw.get("background")
        if background is not None:
            _fields(background, {"trace_mM", "floor_fmol"}, f"species {name}'s background")
            background = Background(
                _positive(background["trace_mM"], f"species {name}'s trace_mM"),
                _positive(background["floor_fmol"], f"species {name}'s floor_fmol"),
            )
        entries.append(Entry(name, identity, mu, background, protonated))
    if any(e.standard_mu_RT is not None for e in entries):
        if standard_concentration_mM is None:
            raise ConfigError(
                "A species standard_mu_RT is declared at the model's standard_concentration_mM, "
                "which the model does not declare"
            )
    if standard_concentration_mM is not None:
        standard_concentration_mM = _positive(standard_concentration_mM, MODEL_KEY)
    if len({e.id for e in entries}) != len(entries):
        raise ConfigError("The model lists a species twice")
    return Declared(tuple(entries), standard_concentration_mM)


def parse_entries(raw_model):
    """The core parser's hook (docs/INNER_MODEL_V4_DESIGN.md §7.4 (f) 7): pops REGISTRY_KEYS from
    each species entry of raw_model, the parser's deep copy, and the model's
    standard_concentration_mM, so the strict species parse that follows sees only id and valence.
    Returns the registry, or None when the model declares none (its fingerprint is unchanged)."""
    popped = []
    for raw in raw_model.get("species") or ():
        keys = {k: raw.pop(k) for k in REGISTRY_KEYS if k in raw} if isinstance(raw, dict) else {}
        popped.append((raw, keys))
    c0 = raw_model.pop(MODEL_KEY, None)
    if c0 is None and not any(keys for _, keys in popped):
        return None
    return build(
        [dict(id=raw.get("id") if isinstance(raw, dict) else None, **keys) for raw, keys in popped],
        c0,
    )


def to_entries(declared_registry):
    """parse_entries' inverse, for the model's to_dict: ({species id: its registry keys}, {model
    keys}), each key present only when declared."""
    species = {}
    for e in declared_registry.entries:
        keys = {}
        if e.identity is not None:
            catalogue = e.identity.catalogue
            ref = None if catalogue is None else dict(catalogue=catalogue[0], entry=catalogue[1])
            keys["identity"] = dict(catalogue=ref, evidence=e.identity.evidence)
        if e.standard_mu_RT is not None:
            keys["standard_mu_RT"] = e.standard_mu_RT
        if e.protonated_standard_mu_RT is not None:
            keys["protonated_standard_mu_RT"] = e.protonated_standard_mu_RT
        if e.background is not None:
            keys["background"] = dict(
                trace_mM=e.background.trace_mM, floor_fmol=e.background.floor_fmol
            )
        if keys:
            species[e.id] = keys
    c0 = declared_registry.standard_concentration_mM
    return species, ({} if c0 is None else {MODEL_KEY: c0})


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
    """The identities an operator declares (the contract's species_identities: none by default)."""
    return tuple(op.species_identities(declaration))


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


def protonated_potential(spec, species):
    """(mu°/RT of a two-form row's protonated form, at valence z + 1, c0 in mM), or None."""
    model = declared(spec)
    entry = None if model is None else model.entry(species)
    if entry is None or entry.protonated_standard_mu_RT is None:
        return None
    return entry.protonated_standard_mu_RT, model.standard_concentration_mM


def dissociation_constant_mM(spec, species, proton):
    """K of HB <-> B + H, in mM, from the registry: c0 exp(mu°_HB - mu°_B - mu°_H) at the model's
    standard_concentration_mM c0. The reaction has sum nu = +1, so c0 does not cancel: K is the
    same from potentials declared at any c0 and converted consistently (mu°/RT at c0' is mu°/RT
    at c0 plus ln(c0'/c0) for every species). proton names the proton row (valence +1)."""
    model = declared(spec)
    if model is None:
        raise ConfigError(f"species {species}: no registry is declared")
    base, acid = model.entry(species), model.entry(proton)
    if base is None or base.protonated_standard_mu_RT is None:
        raise ConfigError(f"species {species} declares no protonated_standard_mu_RT")
    if acid is None or acid.standard_mu_RT is None:
        raise ConfigError(f"the proton row {proton} declares no standard_mu_RT")
    if acid.protonated_standard_mu_RT is not None:
        raise ConfigError(f"the proton row {proton} cannot have two forms")
    m = _inner_model(spec)
    if m.valence[m.species_ids.index(proton)] != 1:
        raise ConfigError(f"the proton row {proton} must have valence +1")
    exponent = base.protonated_standard_mu_RT - base.standard_mu_RT - acid.standard_mu_RT
    return model.standard_concentration_mM * math.exp(exponent)


def pK(spec, species, proton):
    """-log10 of dissociation_constant_mM in mol/L."""
    return -math.log10(dissociation_constant_mM(spec, species, proton) / 1000.0)


def check_background(spec, *, rtol=1e-12):
    """With a registry declared: no row is an exact zero (or below zero, or not finite) at a cell
    or outside node, since an absent row is a declared trace (operators/PLAN.md §2.4); each declared
    background holds (amount >= trace_mM x volume at every node), and the species' ledger floor is
    its material_balance_atol_fmol. Legacy definitions (no registry) keep the inner model's own
    refusal."""
    model = declared(spec)
    if model is None:
        return
    m = spec.model
    tolerances = tuple(spec.execution.material_balance_atol_fmol)
    for row, species in enumerate(m.species_ids):
        entry = model.entry(species)
        b = None if entry is None else entry.background
        for node in (*m.cells, *m.extracellular):
            amount = node.initial_amount_fmol[row]
            if b is None and not (math.isfinite(amount) and amount > 0):
                raise ConfigError(
                    f"species {species}: {node.id} holds {amount:g} fmol. A row absent from a "
                    "node is a declared trace, never zero: declare the species' background "
                    f"(trace_mM, floor_fmol) and give {node.id} at least trace_mM x its volume, "
                    "with that charge in its fixed-charge anchor"
                )
            if b is not None and not amount >= b.trace_mM * node.volume_pL * (1.0 - rtol):
                raise ConfigError(
                    f"species {species}: {node.id} holds {amount:g} fmol, below its declared "
                    f"trace {b.trace_mM:g} mM"
                )
        if b is None:
            continue
        floor = tolerances[row] if row < len(tolerances) else None
        if floor != b.floor_fmol:
            raise ConfigError(
                f"species {species}: its declared floor {b.floor_fmol:g} fmol is not its "
                f"material_balance_atol_fmol ({floor!r})"
            )


def check_two_form_rows(spec):
    """Refuse a route or a reaction that names a two-form row: an in-step mover of it (inner
    routes, pumps, an operator's in-step process; moved_in_step), or an operator that declares it
    among its species (D150's routes, D152's reactions, FR-3's sites, the coupling's reads). The
    row stays inert until a law declares how it moves the forms. Operators that act on every row
    alike and name none (a replacement template, a division, a lumen's fill) are not refused
    here."""
    model = declared(spec)
    if model is None:
        return
    two = [e.id for e in model.entries if e.protonated_standard_mu_RT is not None]
    if not two:
        return
    reason = "no law declares how it moves the forms, so the row stays inert"
    moved = moved_in_step(spec)
    for species in two:
        for kind in ("cell", "outside"):
            for mover in moved.get(species, {}).get(kind, ()):
                raise ConfigError(
                    f"species {species} has two forms (protonated_standard_mu_RT): {mover} moves "
                    f"its {kind} rows, and {reason}"
                )
    for op, declaration in _entries(spec):
        for item in operator_identities(op, declaration):
            if item.id in two:
                raise ConfigError(
                    f"species {item.id} has two forms (protonated_standard_mu_RT): {op.LAW_ID} "
                    f"names it, and {reason}"
                )


def check_definition(spec):
    """The registry's definition-time checks, for the core's hook to call ahead of the inner
    model's own: absent rows and backgrounds, then two-form rows."""
    check_background(spec)
    check_two_form_rows(spec)


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
