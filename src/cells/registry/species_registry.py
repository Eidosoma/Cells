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
  exact zero at a node: an absent row is a declared trace (operators/PLAN.md §2.4, accepted);
* ``forms`` (seam C, docs/CORE_SEAMS_DESIGN.md §5.1 and §19 item 6): a multi-form row, a binder,
  lists its non-base forms, ``[{id, counts, standard_mu_RT[, valence]}, ...]``. The row itself is
  the base form: its ``standard_mu_RT`` and the model's valence are the base form's, so scalar
  readers are unaffected, and the row holds the binder's total. Each form gives its ID (distinct
  from every species and every other form), its ligand counts relative to the base (``{ligand
  species: nonzero integer}``; a negative count is a form below its base, such as PO4 from HPO4),
  its mu°/RT at c0 and, optionally, its valence, which must be the base's plus the ligands'
  (z_base + sum n z_L; check_forms). A ligand is a species with a standard potential and no forms
  of its own. ``forms`` and ``protonated_standard_mu_RT`` (version 1's spelling of a two-form row)
  do not meet on one row. With the ligands' potentials the forms give each form's stability
  constant (form_log_constants): c_f = c_base beta_f prod (x_L / c0)^n_L at equilibrium, where
  ln beta_f = mu°_base/RT + sum n mu°_L/RT - mu°_f/RT. A row with forms stays inert like a
  two-form row (check_two_form_rows) until a law declares how it moves the forms (§5.2).

check_definition runs the definition-time checks (background and absent rows, two-form and
multi-form rows, the forms' valences); the core's hook calls it ahead of the inner model's own
checks, so its messages come first.

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

One standard potential per species (check_potentials)
-----------------------------------------------------
An operator that declares its own standard potentials gives them through
``species_potentials(declaration)`` -> ((species, mu°/RT, c0 in mM), ...) (the contract's default:
none). check_potentials, part of check_definition, converts each to the registry's c0, mu°/RT +
ln(c0_registry / c0), and refuses one that differs from the registry's at more than rounding
(POTENTIAL_ULPS ulps of the magnitudes involved), naming the operator: two declarations of one
species' potential would otherwise book the same rows at two values (F2's one authority; the
FR-4/FR-5 note's §17, D3). A species the registry gives no potential is not compared.

Moved by the step (moved_in_step)
---------------------------------
For each species, the in-step movers of its cell rows and of its outside rows, derived from
declarations and never declared by the user: the inner model's movers from the core's join,
``moved_rows`` of its structure's implementation object (docs/INNER_MODEL_V4_DESIGN.md §7.4 (f) 6:
membrane and junction permeability, each declared channel law's permeant ions, face diffusivity
for outside rows, the pumps' transported rows; (k) 7: each declared kind's moved rows, by node),
and each operator with an in-step process, through ``moves_in_step(spec, declaration)``. An
instantaneous regulation reads only rows that nothing moves inside the step, since its factor is
held through the step: a moved row would make it lag (docs/INVENTORY_COUPLING_DESIGN.md §1.4).
"""

import math
from dataclasses import dataclass

from cells.definitions.specs import ConfigError, _fields

EVIDENCE_KINDS = ("label_only", "expressed_isoform", "native_current", "model")
MODEL_SOURCE = "the model's species entries"
ROLES = ("author", "user")
# check_potentials' rounding: a declared potential converted to the registry's c0 agrees with the
# registry's within this many ulps of |mu°/RT| (both) + |ln(c0 ratio)|, the conversion's inputs.
POTENTIAL_ULPS = 16
EPS = math.ulp(1.0)


@dataclass(frozen=True)
class Identity:
    catalogue: tuple | None  # (catalogue id, entry key), or None (unassigned).
    evidence: str | None  # One of EVIDENCE_KINDS when a catalogue reference is given.


@dataclass(frozen=True)
class Background:
    trace_mM: float
    floor_fmol: float


@dataclass(frozen=True)
class Form:
    """A non-base form of a multi-form row (module docstring, ``forms``): its ID, its ligand counts
    relative to the row's base form, ((ligand species, n), ...) in declared order with each n a
    nonzero integer (negative: a form below the base), its mu°/RT at the model's c0, and its
    valence where declared (None otherwise; check_forms compares it with z_base + sum n z_L)."""

    id: str
    counts: tuple
    standard_mu_RT: float
    valence: int | None = None


@dataclass(frozen=True)
class Entry:
    id: str
    identity: Identity | None
    standard_mu_RT: float | None  # The base form's, at the row's valence z.
    background: Background | None
    protonated_standard_mu_RT: float | None = None  # The form at z + 1, for a two-form row.
    forms: tuple = ()  # Form, ...: a multi-form row's non-base forms, in declared order.


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


REGISTRY_KEYS = ("identity", "standard_mu_RT", "protonated_standard_mu_RT", "background", "forms")
MODEL_KEY = "standard_concentration_mM"
FORM_KEYS = ("id", "counts", "standard_mu_RT")  # A form's required keys; "valence" is optional.


def _potential(value, what):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ConfigError(f"{what} must be a finite number")
    return float(value)


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_forms(raw_forms, name):
    """A row's declared non-base forms, each a Form, in declared order (structure only: the checks
    across entries are _check_forms', and the valences check_forms')."""
    where = f"species {name}'s forms"
    if not isinstance(raw_forms, list) or not raw_forms:
        raise ConfigError(f"{where}: a non-empty list of {{id, counts, standard_mu_RT}} forms")
    forms = []
    for raw in raw_forms:
        if not isinstance(raw, dict):
            raise ConfigError(f"{where}: each form is an object")
        keys = set(FORM_KEYS) | ({"valence"} & set(raw))
        _fields(raw, keys, f"a form of species {name}")
        form_id, counts = raw["id"], raw["counts"]
        if type(form_id) is not str or not form_id:
            raise ConfigError(f"{where}: a form's id is a non-empty string")
        if not isinstance(counts, dict) or not counts:
            raise ConfigError(
                f"species {name}'s form {form_id}: counts map each ligand to its number, relative "
                "to the base form (a form with no counts is the base itself)"
            )
        for ligand, n in counts.items():
            if type(ligand) is not str or not ligand or not _integer(n) or n == 0:
                raise ConfigError(
                    f"species {name}'s form {form_id}: each count is a nonzero integer of a named "
                    "ligand (negative: a form below the base)"
                )
        valence = raw.get("valence")
        if "valence" in raw and not _integer(valence):
            raise ConfigError(f"species {name}'s form {form_id}: its valence is an integer")
        mu = _potential(raw["standard_mu_RT"], f"species {name}'s form {form_id}'s standard_mu_RT")
        forms.append(Form(form_id, tuple(counts.items()), mu, valence))
    return tuple(forms)


def _check_forms(entries):
    """The forms' checks across entries (build): a row with forms has its base potential and no
    protonated form; form IDs are distinct from each other and from every species; each ligand is
    another species with a standard potential and no forms of its own; and no two forms of a row
    have equal counts (isomers, which a rapid closure cannot tell apart)."""
    by_id = {e.id: e for e in entries}
    taken = set(by_id)
    for e in entries:
        if not e.forms:
            continue
        if e.standard_mu_RT is None:
            raise ConfigError(
                f"species {e.id} declares forms without its base form's potential: give "
                "standard_mu_RT (the base form, at the row's valence) too"
            )
        if e.protonated_standard_mu_RT is not None:
            raise ConfigError(
                f"species {e.id} declares both forms and protonated_standard_mu_RT: version 1's "
                "two-form spelling and the forms are one declaration each; declare its forms only"
            )
        seen = set()
        for form in e.forms:
            if form.id in taken:
                raise ConfigError(
                    f"species {e.id}'s form {form.id}: its id is already a species' or a form's"
                )
            taken.add(form.id)
            for ligand, _ in form.counts:
                other = by_id.get(ligand)
                if ligand == e.id or other is None:
                    raise ConfigError(
                        f"species {e.id}'s form {form.id}: its ligand {ligand!r} is not another "
                        "species of the model"
                    )
                if other.standard_mu_RT is None:
                    raise ConfigError(
                        f"species {e.id}'s form {form.id}: its ligand {ligand} declares no "
                        "standard_mu_RT, so the form's stability has no authority"
                    )
                if other.forms or other.protonated_standard_mu_RT is not None:
                    raise ConfigError(
                        f"species {e.id}'s form {form.id}: its ligand {ligand} has forms of its "
                        "own; a ligand is a single-form species"
                    )
            composition = tuple(sorted(form.counts))
            if composition in seen:
                raise ConfigError(
                    f"species {e.id}: two forms have the counts {dict(composition)}. Isomers are "
                    "one form to a rapid closure: declare one, at mu°/RT = -ln(sum exp(-mu°_i/RT))"
                )
            seen.add(composition)


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
        forms = () if raw.get("forms") is None else _parse_forms(raw["forms"], name)
        entries.append(Entry(name, identity, mu, background, protonated, forms))
    _check_forms(entries)
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


def _form_to_dict(form):
    """A Form as declared: its keys in the declared form's order, the valence only when given."""
    out = dict(id=form.id, counts=dict(form.counts), standard_mu_RT=form.standard_mu_RT)
    if form.valence is not None:
        out["valence"] = form.valence
    return out


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
        if e.forms:
            keys["forms"] = [_form_to_dict(form) for form in e.forms]
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
    from cells.definitions import pump_composite_spec as composite_spec

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


def operator_potentials(op, declaration):
    """The standard potentials an operator declares (the contract's species_potentials: none by
    default): ((species, mu°/RT, c0 in mM), ...)."""
    return tuple(op.species_potentials(declaration))


def check_potentials(spec):
    """Refuse an operator whose standard potential of a species, converted to the registry's c0,
    differs from the registry's at more than rounding, naming the operator."""
    for op, declaration in _entries(spec):
        for species, mu_RT, c0 in operator_potentials(op, declaration):
            declared = standard_potential(spec, species)
            if declared is None:
                continue
            registry_mu_RT, registry_c0 = declared
            shift = math.log(registry_c0 / c0)
            converted = mu_RT + shift
            bound = POTENTIAL_ULPS * EPS * (abs(registry_mu_RT) + abs(mu_RT) + abs(shift))
            if not abs(converted - registry_mu_RT) <= bound:
                raise ConfigError(
                    f"{op.LAW_ID} declares species {species!r} with mu°/RT {mu_RT!r} at {c0!r} mM, "
                    f"{converted!r} at the registry's {registry_c0!r} mM, where the species "
                    f"registry gives {registry_mu_RT!r}: one authority for each standard potential"
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


def _multi_form_entry(spec, species):
    model = declared(spec)
    entry = None if model is None else model.entry(species)
    if entry is None or not entry.forms:
        raise ConfigError(f"species {species} declares no forms")
    return model, entry


def forms_of(spec, species):
    """A multi-form row's forms, base first: ((form ID, ((ligand, n), ...), mu°/RT), ...), the base
    being the row itself with no counts and its standard_mu_RT (module docstring, ``forms``)."""
    _, entry = _multi_form_entry(spec, species)
    base = (entry.id, (), entry.standard_mu_RT)
    return (base, *((f.id, f.counts, f.standard_mu_RT) for f in entry.forms))


def form_log_constants(spec, species):
    """((ln beta_f per form, base first, the base's 0.0), c0 in mM) of a multi-form row, from the
    one authority: ln beta_f = mu°_base/RT + sum n_L mu°_L/RT - mu°_f/RT, the stability of form f
    against its base form and its free ligands, so that at equilibrium
    c_f = c_base beta_f prod (x_L / c0)^n_L with c0 the model's standard_concentration_mM."""
    model, entry = _multi_form_entry(spec, species)
    logs = [0.0]
    for form in entry.forms:
        value = entry.standard_mu_RT
        for ligand, n in form.counts:
            value += n * model.entry(ligand).standard_mu_RT
        logs.append(value - form.standard_mu_RT)
    return tuple(logs), model.standard_concentration_mM


def one_step_dissociation_constant_mM(spec, species):
    """K (mM) of a multi-form row whose one form holds one more of a single ligand, B4's two-form
    case written as forms, computed operation for operation as dissociation_constant_mM computes
    version 1's: c0 exp(mu°_f - mu°_base - mu°_L). So a two-form row gives B4's K bit for bit
    however it is spelt, and the general closure's one-ligand path is B4's (CORE_SEAMS §10, C)."""
    model, entry = _multi_form_entry(spec, species)
    forms = entry.forms
    if len(forms) != 1 or len(forms[0].counts) != 1 or forms[0].counts[0][1] != 1:
        raise ConfigError(
            f"species {species} is not a one-step two-form row (one form holding one more of a "
            "single ligand)"
        )
    form, (ligand, _) = forms[0], forms[0].counts[0]
    exponent = form.standard_mu_RT - entry.standard_mu_RT - model.entry(ligand).standard_mu_RT
    return model.standard_concentration_mM * math.exp(exponent)


def form_valences(spec, species):
    """Each form's valence, base first: the row's (the base form's) plus sum n_L z_L, the charge
    its ligand counts carry (CORE_SEAMS §19 item 6)."""
    _, entry = _multi_form_entry(spec, species)
    m = _inner_model(spec)
    z = dict(zip(m.species_ids, m.valence, strict=True))
    base = z[entry.id]
    return (base, *(base + sum(n * z[ligand] for ligand, n in f.counts) for f in entry.forms))


def ligand_floor_counts(spec, species):
    """{ligand: the smallest count of it over the row's forms, the base's 0 included}, each <= 0. A
    binder total T_B times it is that ligand's part of the admissible floor of its total,
    sum_B T_B min_f n_L,f (CORE_SEAMS §19 item 6; negative with a form below its base)."""
    _, entry = _multi_form_entry(spec, species)
    floors = {}
    for form in entry.forms:
        for ligand, n in form.counts:
            floors[ligand] = min(floors.get(ligand, 0), n)
    return floors


def check_forms(spec):
    """Refuse a form whose declared valence is not the base's plus sum n_L z_L: its counts fix the
    charge it carries, so a declared valence that disagrees would book another charge (the
    references' planted valence)."""
    model = declared(spec)
    if model is None:
        return
    for entry in model.entries:
        if not entry.forms:
            continue
        base, *derived = form_valences(spec, entry.id)
        for form, valence in zip(entry.forms, derived, strict=True):
            if form.valence is not None and form.valence != valence:
                raise ConfigError(
                    f"species {entry.id}'s form {form.id} declares valence {form.valence}, but its "
                    f"counts {dict(form.counts)} on the base's {base} give {valence} "
                    "(z_base + sum n z_L)"
                )


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


def _forms_label(entry):
    """How a refusal names a row's forms: version 1's two-form spelling, or its declared forms."""
    if entry.protonated_standard_mu_RT is not None:
        return "two forms (protonated_standard_mu_RT)"
    return f"forms ({', '.join(f.id for f in entry.forms)} beside its base)"


def check_two_form_rows(spec):
    """Refuse a route or a reaction that names a two-form or multi-form row: an in-step mover of
    it (inner routes, pumps, an operator's in-step process; moved_in_step), or an operator that
    declares it among its species (D150's routes, D152's reactions, FR-3's sites, the coupling's
    reads). The row stays inert until a law declares how it moves the forms (§5.2). Operators that
    act on every row alike and name none (a replacement template, a division, a lumen's fill) are
    not refused here."""
    model = declared(spec)
    if model is None:
        return
    labels = {
        e.id: _forms_label(e)
        for e in model.entries
        if e.protonated_standard_mu_RT is not None or e.forms
    }
    if not labels:
        return
    reason = "no law declares how it moves the forms, so the row stays inert"
    moved = moved_in_step(spec)
    for species, label in labels.items():
        for kind in ("cell", "outside"):
            for mover in moved.get(species, {}).get(kind, ()):
                raise ConfigError(
                    f"species {species} has {label}: {mover} moves its {kind} rows, and {reason}"
                )
    for op, declaration in _entries(spec):
        for item in operator_identities(op, declaration):
            if item.id in labels:
                raise ConfigError(
                    f"species {item.id} has {labels[item.id]}: {op.LAW_ID} names it, and {reason}"
                )


def check_definition(spec):
    """The registry's definition-time checks, for the core's hook to call ahead of the inner
    model's own: absent rows and backgrounds, two-form and multi-form rows, the forms' valences,
    then operators' potentials."""
    check_background(spec)
    check_two_form_rows(spec)
    check_forms(spec)
    check_potentials(spec)


# ------------------------------------------------------------------ moved by the step


def _inner_model(spec):
    if hasattr(spec.model, "operators"):
        from cells.definitions import pump_composite_spec as composite_spec

        return composite_spec.projection(spec).model
    return spec.model


# The node kinds each of today's mover kinds moves (the core's moved_rows, §7.4 (f) 6). A declared
# kind's entries name nodes, whose kinds come from the model's node lists (§7.4 (k) 7).
NODE_KINDS = {
    "membrane": ("cell", "outside"),
    "channel": ("cell", "outside"),
    "pump": ("cell", "outside"),
    "junction": ("cell",),
    "face": ("outside",),
}


def inner_movers(spec):
    """(inner model, {species: ((mover kind, law ID, entity IDs), ...)}): the core's join of the
    inner model's in-step movers, through its structure's implementation object: today's routes,
    channels and pumps (§7.4 (f) 6) and each declared kind's moved_rows (§7.4 (k) 7)."""
    from cells.models import surface_pump_v3

    m = _inner_model(spec)
    return m, surface_pump_v3.model_for(m).moved_rows(m)


def _named(kind, law, entity):
    if kind == "pump":
        from cells.laws.pumps import calcium_atpase

        return (
            f"the {'calcium' if law == calcium_atpase.LAW_ID else 'Na/K'} pump on membrane {entity}"
        )
    return f"{kind} {entity}"


def moved_in_step(spec):
    """{species id: {"cell": movers, "outside": movers}}: what moves each species' rows inside the
    inner step, each mover named (module docstring): the inner model's movers from the core's join
    (inner_movers), then each operator's in-step process (the contract's moves_in_step)."""
    m, movers = inner_movers(spec)
    moved = {s: {"cell": [], "outside": []} for s in m.species_ids}
    cells = {c.id for c in m.cells}
    outside = {n.id for n in m.extracellular}

    def add(species, kinds, mover):
        for kind in kinds:
            if mover not in moved[species][kind]:
                moved[species][kind].append(mover)

    for species, entries in movers.items():
        for kind, law, entities in entries:
            for entity in entities:
                if kind in NODE_KINDS:
                    add(species, NODE_KINDS[kind], _named(kind, law, entity))
                elif entity in cells or entity in outside:
                    node = "cell" if entity in cells else "outside"
                    add(species, (node,), f"{kind} ({law}) at {entity}")
                else:
                    raise ConfigError(
                        f"{kind} ({law}) moves {species} at {entity}, which is no node"
                    )
    for op, declaration in _entries(spec):
        if not op.PROCESS:
            continue
        for species, kind in op.moves_in_step(spec, declaration):
            if kind not in ("cell", "outside"):
                raise ConfigError(f"{op.LAW_ID}: moves_in_step gives node kinds cell or outside")
            add(species, (kind,), f"{op.LAW_ID} (its in-step process)")
    return {s: {k: tuple(v) for k, v in rows.items()} for s, rows in moved.items()}
