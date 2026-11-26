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

One standard free energy per reaction (check_free_energies)
-----------------------------------------------------------
Seam E's check (docs/CORE_SEAMS_DESIGN.md §7.1; the lead's ruling (d) of 19 November 2026). An
operator or a kind that declares reaction-level standard free energies gives them through
``standard_free_energies(declaration)`` -> (FreeEnergyEntry, ...), each a stoichiometry ((species,
nu), ...), dG°/RT at its c0 in mM, and the cycle law and mode that produced it, or neither (F's
contract, read through its checks: kind_registry.kind_standard_free_energies, each kind bound to
its structure entry, and operators.operator_standard_free_energies). check_free_energies, part of
check_definition after check_potentials, converts each to the registry's c0, dG°/RT + (sum nu)
ln(c0_registry / c0), and refuses one that differs from the registry's sum of nu mu°/RT by more
than its band, naming the declarer and the entry:
* an entry that names a cycle law whose form has constants of its own takes that form's band for
  its mode (``free_energy_band(mode, terms, c0_mM)``, terms the entry's ((nu, the registry's
  mu°/RT), ...)): Wegscheider's B_W over the mode's cycle and the registry's potentials, plus one
  ulp of the mode's implied dG°/RT, the entry's one rounding from the exact value, so every law
  Wegscheider's condition admits, this check admits. The band comes from the law's form, never from
  the entry, so no band is self-certified, and the registry reads no diagram;
* any other entry (one that names no law, or a law whose form gives no band) takes
  check_potentials' rounding: POTENTIAL_ULPS ulps of sum |nu mu°/RT| + |dG°/RT| + |(sum nu)
  ln(c0_registry / c0)|, to which a species' potential at nu = 1 reduces.
An entry may give dG° in kJ/mol with its basis instead (F's FreeEnergyEntry, D234's option (b)): a
law writes no temperature, so the registry converts it at the world's, dG°/RT = 1000 dG° / (R T) +
dG_RT_offset with R laws/electrochemistry's (the one conversion; TEMPERATURE_INDEPENDENT is today's
one basis). The kJ part is held constant and the offset carries no temperature (the lead's ruling
(A)): a law citing a value at pH 7 writes it with the offset nu_H ln 1e7, and nu ln P(1e-7 M) for a
total, the split a named set makes, so the two agree at every temperature. The entry's band gains
one ulp of the converted value, the conversion's own rounding.
The residual is evaluated at FREE_ENERGY_DIGITS digits from the declared doubles, so its verdict
does not depend on the order of its terms. An entry naming a species that is not a row of the model
is refused: water, at unit activity, is omitted, never named. An entry with a row the registry gives
no potential is not compared. Its power is for energies no parse-time Wegscheider check covers:
where one does (the transporter's diagram cycles), it holds the same band, and its refusal comes
first.

Named potential sets (POTENTIAL_SETS, with_potential_set, check_potential_set)
-----------------------------------------------------------------------------
A source that cites reaction-level standard free energies, not species potentials, fixes the
potentials only up to one reference per conserved quantity. A named set (PotentialSet; the lead's
rulings of 20 November 2026, D234's B1) states its references and derives every other potential
from its values, so its potentials hold together only as a whole:
* **References:** mu°/RT = 0 at 1 M for one row per conserved quantity (cells.potential_set.beard2005@1 and @2: H+, K+,
  Mg2+, O2, NAD, Q, cytochrome c oxidised, ADP3-, HPO4 2- and the substrate's oxidised form). Water
  is never a row: it stands at unit activity with mu = 0 and is omitted from every stoichiometry,
  so each dG° is at unit water activity.
* **Derived:** a form's potential from its dissociation constant (mu°_f = mu°_base + sum n mu°_L +
  ln K_d, with no temperature), and each other row's from one reaction, solved in order: dG°/RT at
  the world's temperature, plus its basis's logarithms, which carry none (a reaction cited at pH 7
  adds nu_H ln(1 M / 1e-7 M) for its scalar protons and nu ln P(1e-7 M) for each total over proton
  forms, P the row's binding polynomial). dG° is treated as independent of temperature, since no
  dH° is cited: an approximation. A reaction may instead give its equilibrium constant in base
  forms at 1 M, which, like a K_d, carries no temperature: matched to a cited constant on totals
  at a declared buffer, from which the set derives it (SetMatch; cells.potential_set.beard2005@2's adenylate kinase).
  Every value is moved to the world's c0 by ln(c0 / 1 M), evaluated at FREE_ENERGY_DIGITS digits
  and rounded once.
* **The limit:** a dG° computed from these potentials is meaningful only for a reaction that
  conserves every reference quantity. check_moieties holds every declared moiety to that.
* **No mixing:** with_potential_set applies a set whole to a raw definition, every row of it the
  definition declares, refusing a row whose potential or forms come from elsewhere, and names it
  under ``potential_set``. check_potential_set then refuses, at the definition, a named set's row
  whose valence, potential or forms differ from the set's at the world's temperature and c0: a hand
  edit, a mixed value, or a temperature changed after the set was applied. Rows the set does not
  name are the world's. The set's moieties, over the rows present, are required (the limit above
  rests on them); the world's other moieties stay its own. A declared one-site proton buffer takes
  the set's proton reference through with_potential_set (proton_buffers {row: pK}, recorded under
  the model's ``proton_buffers``): its base at 0, its protonated form at -pK ln 10 + mu°_H/RT, at
  1 M, checked at the definition like the set's rows.
* **A set's name versions its derivation:** check_potential_set compares the doubles exactly, so
  the name covers the derivation's arithmetic as well as the set's data. Any change to
  potential_set_values or to a set's values is a new version (cells.potential_set.beard2005@2), never an edit of an
  existing one, so no recorded world that names a set is refused by a later revision.
* **Not potentials:** a closure's binding rates (k_on) are the world's, declared in its block; the
  source's X_MgA is class C, set large. Each set's notes say what its sources leave to it.

Moieties (moieties, check_moieties)
-----------------------------------
The model may declare its conserved moieties, ``moieties``: [{id, weights: {row: nonzero
integer}}, ...], each weight per unit of the row's total. A row with forms holds every form, so Mg
bound in MgATP counts in the Mg row's total where a closure holds it, and a form needs no weights
of its own. The registry is their one authority for kinds, entries and operators' moves (the
lead's Q7 ruling): check_moieties refuses any kind mode, resolved through its role_species
(entity_modes), any declared free-energy entry, and any net move an operator reports through the
contract's species_moieties (operators.operator_species_moieties; docs/GENE_REGULATION_DESIGN.md
§7.6) that changes a moiety, naming it (CORE_SEAMS §3.2 and §7.3). Transport keeps a species'
identity, so a mode's net change over both ends is its chemistry. A model that declares none is not
checked. An operator that reports no moves (the hook's default, D152's reactions today) keeps its
own moieties; whether D152 reports through the hook is the operators owner's call.

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

import copy
import math
from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction
from types import MappingProxyType
from typing import NamedTuple

from cells.definitions.specs import ConfigError, _fields

EVIDENCE_KINDS = ("label_only", "expressed_isoform", "native_current", "model")
MODEL_SOURCE = "the model's species entries"
ROLES = ("author", "user")
# check_potentials' rounding: a declared potential converted to the registry's c0 agrees with the
# registry's within this many ulps of |mu°/RT| (both) + |ln(c0 ratio)|, the conversion's inputs.
POTENTIAL_ULPS = 16
EPS = math.ulp(1.0)
# check_free_energies' residual is evaluated at this many digits from the declared doubles.
FREE_ENERGY_DIGITS = 50


@dataclass(frozen=True)
class Identity:
    catalogue: tuple | None  # (catalogue id, entry key), or None (unassigned).
    evidence: str | None  # One of EVIDENCE_KINDS when a catalogue reference is given.


@dataclass(frozen=True)
class NamedRow:
    """A species an operator names, moves or reads with no identity claim at all, which its
    species_identities may give beside identity items. The registry's row checks see it
    (check_two_form_rows, check_stage_read_rows); identity resolution and check_identities skip
    it, so it sets no species' identity and no resolved source (current injection's carriers;
    the second review's finding 3)."""

    id: str


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
    """The registry the model declares: its entries, in the model's species order; its moieties
    (Moiety, ...), in declared order; the named potential set its potentials come from, or None;
    and the proton buffers applied on that set's proton reference, ((row, pK), ...) (module
    docstring)."""

    entries: tuple
    standard_concentration_mM: float | None
    moieties: tuple = ()
    potential_set: str | None = None
    proton_buffers: tuple = ()

    def entry(self, species):
        return next((e for e in self.entries if e.id == species), None)


@dataclass(frozen=True)
class Moiety:
    """A conserved moiety (module docstring, ``moieties``): its ID and its weights, ((row, w), ...)
    in declared order, each w a nonzero integer per unit of the row's total."""

    id: str
    weights: tuple


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
MOIETIES_KEY = "moieties"  # The model's conserved moieties (module docstring), optional.
SET_KEY = "potential_set"  # The named potential set the model's potentials come from, optional.
BUFFERS_KEY = "proton_buffers"  # {row: pK} applied on the named set's proton reference, optional.
MOIETY_KEYS = ("id", "weights")
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
    another species with a standard potential and no forms of its own; no two forms of a row
    have equal counts (isomers, which a rapid closure cannot tell apart).

    Counts of both signs are admitted (the C4 follow-up, the lead's ruling of 19 November 2026):
    for them the per-ligand floor (the sum over binders of T_B min_f n) is necessary but not
    sufficient, and the general closure's read checks the exact joint condition, its margin
    t* > 0 (laws/reactions/rapid_binding.py, amendment C4). The general closure's own admission
    still refuses any negative count beside its envelope, until a release-step envelope case is
    registered (kinds/proton_buffer.py)."""
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


def _parse_moieties(raw, rows):
    """The model's moieties, [{id, weights: {row: nonzero integer}}, ...], each ID named once and
    each row one of the model's (`rows`), as (Moiety, ...) in declared order (module docstring)."""
    if type(raw) is not list or not raw:
        raise ConfigError(f"The model's {MOIETIES_KEY} is a non-empty list of {{id, weights}}")
    out, seen = [], set()
    for item in raw:
        if not isinstance(item, dict):
            raise ConfigError(f"Each of the model's {MOIETIES_KEY} is an object {{id, weights}}")
        _fields(item, set(MOIETY_KEYS), "a moiety")
        name, weights = item["id"], item["weights"]
        if type(name) is not str or not name or name in seen:
            raise ConfigError(f"A moiety's id is a non-empty string, each named once: {name!r}")
        seen.add(name)
        if not isinstance(weights, dict) or not weights:
            raise ConfigError(f"moiety {name}: its weights map each row to a nonzero integer")
        for row, w in weights.items():
            if row not in rows:
                raise ConfigError(f"moiety {name}: {row!r} is not a species of the model")
            if type(w) is not int or w == 0:
                raise ConfigError(f"moiety {name}: the weight of {row} is a nonzero integer")
        out.append(Moiety(name, tuple(weights.items())))
    return tuple(out)


def _parse_buffers(raw, rows, potential_set):
    """The model's proton buffers, {row: pK}, as ((row, pK), ...) in declared order: only beside a
    named potential set, each row one of the model's and outside the set, each pK finite."""
    if potential_set is None:
        raise ConfigError(f"The model's {BUFFERS_KEY} are applied on a named {SET_KEY} only")
    if not isinstance(raw, dict) or not raw:
        raise ConfigError(f"The model's {BUFFERS_KEY} map each buffer row to its pK")
    set_rows = dict(POTENTIAL_SETS[potential_set].rows)
    for row, pk in raw.items():
        if row not in rows or row in set_rows:
            raise ConfigError(f"proton buffer {row!r}: a species of the model outside {SET_KEY}")
        if isinstance(pk, bool) or not isinstance(pk, (int, float)) or not math.isfinite(pk):
            raise ConfigError(f"proton buffer {row}: its pK is a finite number")
    return tuple((row, float(pk)) for row, pk in raw.items())


def build(
    raw_entries,
    standard_concentration_mM=None,
    moieties=None,
    potential_set=None,
    buffers=None,
):
    """The registry of entries {id, any of REGISTRY_KEYS}, in the model's species order, at c0
    (mM; required when an entry declares a potential), with the model's moieties, named potential
    set and proton buffers where it declares them (module docstring)."""
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
    if moieties is not None:
        moieties = _parse_moieties(moieties, {e.id for e in entries})
    if potential_set is not None and potential_set not in POTENTIAL_SETS:
        raise ConfigError(
            f"The model's {SET_KEY} {potential_set!r} is not a named potential set: one of "
            f"{sorted(POTENTIAL_SETS)}"
        )
    if buffers is not None:
        buffers = _parse_buffers(buffers, {e.id for e in entries}, potential_set)
    return Declared(
        tuple(entries),
        standard_concentration_mM,
        moieties or (),
        potential_set,
        buffers or (),
    )


def parse_entries(raw_model):
    """The core parser's hook (docs/INNER_MODEL_V4_DESIGN.md §7.4 (f) 7): pops REGISTRY_KEYS from
    each species entry of raw_model, the parser's deep copy, and the model's
    standard_concentration_mM, moieties and potential_set, so the strict species parse that
    follows sees only id and valence. Returns the registry, or None when the model declares none
    (its fingerprint is unchanged)."""
    popped = []
    for raw in raw_model.get("species") or ():
        keys = {k: raw.pop(k) for k in REGISTRY_KEYS if k in raw} if isinstance(raw, dict) else {}
        popped.append((raw, keys))
    c0 = raw_model.pop(MODEL_KEY, None)
    moieties = raw_model.pop(MOIETIES_KEY, None)
    named = raw_model.pop(SET_KEY, None)
    buffers = raw_model.pop(BUFFERS_KEY, None)
    if (c0, moieties, named, buffers) == (None,) * 4 and not any(k for _, k in popped):
        return None
    return build(
        [dict(id=raw.get("id") if isinstance(raw, dict) else None, **keys) for raw, keys in popped],
        c0,
        moieties,
        named,
        buffers,
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
    keys = {} if c0 is None else {MODEL_KEY: c0}
    if declared_registry.moieties:
        keys[MOIETIES_KEY] = [
            dict(id=m.id, weights=dict(m.weights)) for m in declared_registry.moieties
        ]
    if declared_registry.potential_set is not None:
        keys[SET_KEY] = declared_registry.potential_set
    if declared_registry.proton_buffers:
        keys[BUFFERS_KEY] = dict(declared_registry.proton_buffers)
    return species, keys


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
            if isinstance(item, NamedRow):  # A row it names, with no identity claim.
                continue
            resolved.setdefault(item.id, (law, Identity(item.catalogue, item.evidence)))
    return resolved


def check_identities(spec, law, items):
    """Refuse an item (id, catalogue, evidence) whose identity differs from its species' resolved
    identity, naming the source that set it."""
    resolved = identities(spec)
    for item in items:
        if isinstance(item, NamedRow):  # No identity claim to compare.
            continue
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


def operator_written_rows(op, declaration):
    """The species rows an operator's split half-steps write, for the shared-row rule: its
    written_species hook, or none (an operator without the hook writes no shared row)."""
    hook = getattr(op, "written_species", None)
    return () if hook is None else tuple(hook(declaration))


def check_shared_rows(spec, law):
    """Refuse a species row that two operators write (the two-writer rule of 19 November 2026,
    extended to the gene unit beside a D152 network by FR-43 / D315) when the species registry
    gives no standard potential for it. Each writer books the exact dG of its own moves from its
    own mu°/RT, so the row needs one authority for its potential, and check_potentials holds both
    writers to the registry's value, but only where the registry gives one. One function, called
    by every operator with writers and naming the caller, so no pairwise check is added (D176)."""
    writers = {}
    for op, declaration in _entries(spec):
        for species in dict.fromkeys(operator_written_rows(op, declaration)):
            writers.setdefault(species, []).append(op.LAW_ID)
    for species, laws in writers.items():
        if len(laws) > 1 and standard_potential(spec, species) is None:
            raise ConfigError(
                f"{law}: species {species!r} is written by {' and '.join(laws)}; a row that two "
                "operators write needs its standard potential in the species registry, its one "
                "authority (FR-43 / D315)"
            )


def declared_free_energies(spec):
    """Every reaction-level standard free energy the definition declares (seam E, module
    docstring): ((where, (FreeEnergyEntry, ...)), ...), each composite operator's in declared order
    (operators.operator_standard_free_energies: an operator hosts no law, so its entries name
    none), then each declared kind's, the kind bound to its structure entry so that an entry
    without the hook declares none (kind_registry.kind_standard_free_energies: a law an entry names
    is a cycle law the kind hosts, and its mode one of that law's form's). Each is read through F's
    checks, whose refusal is the definition's."""
    from cells.registry import kind_registry
    from cells.registry import operators as operator_registry

    out = []
    try:
        for op, declaration in _entries(spec):
            entries = operator_registry.operator_standard_free_energies(op, declaration)
            out.append((f"Operator {op.LAW_ID}'s standard_free_energies", entries))
        registry = kind_registry.active()
        for kind_id, declaration in getattr(_inner_model(spec), "kinds", ()):
            kind = registry.lookup(kind_id)
            entry = kind.structure_entry(declaration) if kind.structure_entry else ()
            bound = kind_registry.bound(kind, entry)
            entries = kind_registry.kind_standard_free_energies(bound, declaration)
            out.append((f"Kind {kind.kind_id}'s standard_free_energies", entries))
    except ValueError as error:
        raise ConfigError(str(error)) from error
    return tuple(out)


def _law_band(entry, terms, c0_mM, where):
    """The band of an entry that names a cycle law, from that law's form (module docstring): its
    free_energy_band for the entry's mode, as a Decimal; None for an entry that names no law, or
    whose law's form gives no band (no constants of its own)."""
    if entry.law_id is None:
        return None
    from cells.registry import laws as law_registry

    form = law_registry.active().lookup(entry.law_id).cycle
    method = getattr(form, "free_energy_band", None)
    try:
        band = method(entry.mode, terms, c0_mM) if callable(method) else None
    except ValueError as error:
        raise ConfigError(f"{where}: {entry.law_id}'s form gives no band: {error}") from error
    if band is None:
        return None
    band = Decimal(band)
    if not (band.is_finite() and band >= 0):
        raise ConfigError(
            f"{where}: {entry.law_id}'s form gives mode {entry.mode} the band {band!r}, not a "
            "finite non-negative number"
        )
    return band


def check_free_energies(spec):
    """Refuse a declared reaction-level standard free energy that, converted to the registry's c0
    by (sum nu) ln(c0_registry / c0), differs from the registry's sum of nu mu°/RT by more than its
    band, naming the declarer and the entry (module docstring). The band of an entry naming a
    cycle law whose form gives one is that form's for its mode: Wegscheider's B_W plus one ulp of
    the mode's implied dG°/RT, the entry's one rounding, so every law Wegscheider's condition
    admits, this check admits. Any other entry's is check_potentials' rounding. An entry in kJ/mol
    is converted first, dG°/RT = 1000 dG° / (R T) + dG_RT_offset at the model's temperature (its
    basis, TEMPERATURE_INDEPENDENT, the one today), and its band gains one ulp of that value, the
    conversion's own rounding. Every declared entry is read through F's checks, in a world without
    a registry too; an entry with a species the registry gives no potential is not compared."""
    model = _inner_model(spec)
    rows = set(model.species_ids)
    for where, entries in declared_free_energies(spec):
        for index, entry in enumerate(entries):
            at = f"{where}, entry {index}"
            law = "" if entry.law_id is None else f" ({entry.law_id}'s cycle, mode {entry.mode})"
            stray = [species for species, _ in entry.stoichiometry if species not in rows]
            if stray:
                raise ConfigError(
                    f"{at}{law}: it names {stray[0]!r}, which is not a species of the model: an "
                    "entry's stoichiometry names the model's rows only (water, at unit activity, "
                    "is omitted)"
                )
            found = [standard_potential(spec, species) for species, _ in entry.stoichiometry]
            if any(item is None for item in found):
                continue  # Not compared, as check_potentials.
            c0_registry = found[0][1]
            terms = tuple(
                (nu, mu) for (_, nu), (mu, _) in zip(entry.stoichiometry, found, strict=True)
            )
            with localcontext() as ctx:
                ctx.prec = FREE_ENERGY_DIGITS
                dg_rt, given = _entry_dG_RT(entry, model.temperature_K, at, law)
                net = sum(Decimal(nu) for nu, _ in terms)
                shift = net * (Decimal(c0_registry).ln() - Decimal(entry.c0).ln())
                registry_sum = sum(Decimal(nu) * Decimal(mu) for nu, mu in terms)
                converted = dg_rt + shift
                residual = converted - registry_sum
                band, source = _law_band(entry, terms, c0_registry, at), "its law's form's band"
                if band is None:
                    magnitude = sum(abs(Decimal(nu) * Decimal(mu)) for nu, mu in terms)
                    magnitude += abs(dg_rt) + abs(shift)
                    band, source = POTENTIAL_ULPS * Decimal(EPS) * magnitude, "the rounding bound"
                if entry.dG_kJ_mol is not None:  # The conversion's own rounding.
                    band += Decimal(math.ulp(float(dg_rt)))
                if abs(residual) <= band:
                    continue
            raise ConfigError(
                f"{at}{law}: {given} at {entry.c0!r} mM is {float(converted)!r} at the registry's "
                f"{c0_registry!r} mM, where the species registry's sum of nu mu°/RT gives "
                f"{float(registry_sum)!r}: {float(residual):.3e} apart, beyond {source} "
                f"{float(band):.3e}: one authority for each standard free energy"
            )


def _entry_dG_RT(entry, temperature_K, at, law):
    """(dG°/RT as a Decimal, its words for a refusal) of a free-energy entry: its dG_RT, or its
    dG_kJ_mol converted at the model's temperature plus its offset, 1000 dG° / (R T) +
    dG_RT_offset, R laws/electrochemistry's (the lead's ruling (A): the kJ part is held constant,
    the offset, its basis's logarithms, carries no temperature). A basis this conversion does not
    know is refused (F's reader admits only DG_BASES')."""
    from cells.registry.kind_registry import TEMPERATURE_INDEPENDENT

    if entry.dG_kJ_mol is None:
        return Decimal(entry.dG_RT), f"dG°/RT {entry.dG_RT!r}"
    if entry.dG_basis != TEMPERATURE_INDEPENDENT:
        raise ConfigError(f"{at}{law}: the registry converts no dG_basis {entry.dG_basis!r}")
    offset = entry.dG_RT_offset or 0.0
    value = Decimal(entry.dG_kJ_mol) * 1000 / (_gas_constant() * Decimal(temperature_K))
    value += Decimal(offset)
    plus = f" + {offset!r} RT" if offset else ""
    return value, (
        f"dG° {entry.dG_kJ_mol!r} kJ/mol{plus} (dG°/RT {float(value)!r} at {temperature_K!r} K)"
    )


# ------------------------------------------------------------------ named potential sets (B1)

SET_C0_MM = 1000.0  # A set's own standard state: every species at 1 M.


def _gas_constant():
    """R in J/(mol K) as a Decimal: laws/electrochemistry's, the one authority (N_A k_B in SI),
    imported here only when a set or an entry in kJ/mol needs it."""
    from cells.laws.electrochemistry import R

    return Decimal(R)


class SetForm(NamedTuple):
    """A non-base form of a set's row from its dissociation constant K_d = [base] prod [L]^n /
    [form] at equilibrium, in M^(sum n): mu°_form/RT = mu°_base/RT + sum n mu°_L/RT + ln K_d at
    1 M, with no temperature (the lead's Q4 ruling); `cited`, where the constant is printed."""

    row: str
    id: str
    counts: tuple  # ((ligand row, n), ...)
    dissociation_M: float
    cited: str


class SetMatch(NamedTuple):
    """A reaction's constant in base forms, matched to a cited constant on totals at a declared
    buffer (D236's adenylate kinase): K_base = K_totals prod_rows P_row(m)^(-nu_row), P_row the
    row's binding polynomial over the set's own forms at the free ligand m. The buffer holds its
    rows at the given totals (M); one of them is the ligand that the others' forms bind, and m
    solves its mass balance with the set's own dissociation constants (the state-3 buffer's free
    Mg2+, 3.808553529 mM, for the kinase). `cited`: where the constant on totals is printed and why
    the buffer is the one declared."""

    constant_on_totals: float
    buffer_M: tuple  # ((row, total in M), ...)
    cited: str


class SetReaction(NamedTuple):
    """A reaction-level standard free energy that fixes the potential of the one row it
    `determines`: its stoichiometry over base rows, ((row, nu), ...), products positive and water
    omitted (unit activity); its value in kJ/mol, `multiple` times over where the set's turnover is
    a multiple of the cited one; its basis, the set's proton row at proton_reference_M (pH 7:
    1e-7 M) or at 1 M (None), and the rows it counts as totals over their proton forms at that
    reference (`totals`); and `cited`, where it is printed, or why it is declared.

    Or, in place of the value in kJ/mol (dG_kJ_mol None), `match`: its equilibrium constant in
    base forms at 1 M, matched to a constant on totals (SetMatch). Like a form's K_d it carries no
    temperature: dG°/RT = -ln K_base at every temperature (cells.potential_set.beard2005@2's adenylate kinase). Such a
    reaction is on the 1 M basis, with no totals and a multiple of 1."""

    determines: str
    stoichiometry: tuple
    dG_kJ_mol: float | None
    multiple: int
    proton_reference_M: float | None
    totals: tuple
    cited: str
    match: SetMatch | None = None


class PotentialSet(NamedTuple):
    """A named set of standard potentials (module docstring, "Named potential sets")."""

    name: str
    sources: tuple  # Each work cited, as its reference string.
    proton: str  # Its proton row: the scalar proton of a reaction cited at a reference pH.
    rows: tuple  # ((row, valence of its base form), ...)
    references: tuple  # Rows at mu°/RT = 0 at 1 M, one per conserved quantity.
    forms: tuple  # SetForm, ...
    reactions: tuple  # SetReaction, ..., solved in order.
    moieties: tuple  # ((moiety ID, ((row, weight), ...)), ...)
    notes: tuple  # What its sources leave to it: departures, declared values and limits.


_BEARD_2005 = "Beard 2005, PLoS Comput Biol 1(4):e36"
_APPENDIX = "docs/MITOCHONDRIA_LAWS_APPENDIX.md at tag mito-laws-appendix-2026-11-20b"
_BEARD_2006 = "Beard 2006 (correction), PLoS Comput Biol 2(1):e8"
BEARD_2005 = PotentialSet(
    name="cells.potential_set.beard2005@1",
    sources=(
        "Beard DA (2005), A biophysical model of the mitochondrial respiratory system and "
        "oxidative phosphorylation, PLoS Comput Biol 1(4):e36, doi:10.1371/journal.pcbi.0010036 "
        "(CC BY)",
        "Beard DA (2006), Correction, PLoS Comput Biol 2(1):e8, doi:10.1371/journal.pcbi.0020008 "
        "(CC BY): Table 1's corrected values",
    ),
    proton="H",
    rows=(
        ("H", 1), ("K", 1), ("Mg", 2), ("O2", 0), ("NAD", -1), ("NADH", -2), ("Q", 0),
        ("QH2", 0), ("cytc_ox", 3), ("cytc_red", 2), ("ADP", -3), ("ATP", -4), ("Pi", -2),
        ("S_ox", 0), ("S_red", 0),
    ),  # fmt: skip
    references=("H", "K", "Mg", "O2", "NAD", "Q", "cytc_ox", "ADP", "Pi", "S_ox"),
    forms=(
        SetForm("ATP", "MgATP", (("Mg", 1),), 24.0e-6, f"{_BEARD_2006}, Table 1: K_MgATP"),
        SetForm("ADP", "MgADP", (("Mg", 1),), 347.0e-6, f"{_BEARD_2006}, Table 1: K_MgADP"),
        SetForm("Pi", "H2PO4", (("H", 1),), 1.7783e-7, f"{_BEARD_2006}, Table 1: k_dH"),
    ),
    reactions=(
        SetReaction(
            "cytc_red", (("O2", -1), ("cytc_red", -4), ("H", -4), ("cytc_ox", 4)), -122.94, 2,
            1e-7, (), f"{_BEARD_2005}, Table 2: complex IV, per 1/2 O2 at pH 7 (here per O2)",
        ),
        SetReaction(
            "QH2", (("QH2", -1), ("cytc_ox", -2), ("Q", 1), ("cytc_red", 2), ("H", 2)), -32.53, 1,
            1e-7, (), f"{_BEARD_2005}, Table 2: complex III, at pH 7",
        ),
        SetReaction(
            "NADH", (("NADH", -1), ("Q", -1), ("H", -1), ("NAD", 1), ("QH2", 1)), -69.37, 1, 1e-7,
            (), f"{_BEARD_2005}, Table 2: complex I, at pH 7",
        ),
        SetReaction(
            "ATP", (("ADP", -1), ("Pi", -1), ("H", -1), ("ATP", 1)), 36.03, 1, 1e-7, ("Pi",),
            f"{_BEARD_2005}, Table 2: ATP synthesis at pH 7, Pi its total (+36.03 kJ/mol; the "
            "text under Eq. 11 prints -36.03, a sign slip)",
        ),
        SetReaction(
            "S_red", (("S_red", -1), ("NAD", -1), ("S_ox", 1), ("NADH", 1), ("H", 1)), 0.0, 1,
            1e-7, (), "declared, uncited: the lumped dehydrogenase substrate the NADH supply "
            "oxidises, which the source does not print; a world sets the supply's drive through "
            "its held pair's ratio",
        ),
    ),  # fmt: skip
    moieties=(
        ("adenine", (("ATP", 1), ("ADP", 1))),
        ("NAD", (("NAD", 1), ("NADH", 1))),
        ("quinone", (("Q", 1), ("QH2", 1))),
        ("cytochrome_c", (("cytc_ox", 1), ("cytc_red", 1))),
        ("phosphorus", (("Pi", 1), ("ADP", 2), ("ATP", 3))),
        ("magnesium", (("Mg", 1),)),
        ("substrate", (("S_red", 1), ("S_ox", 1))),
    ),
    notes=(
        "Table 2's values are reaction-level only; the references fix the rest (module "
        "docstring), and water is omitted at unit activity.",
        "dG° is treated as independent of temperature, since the source cites no dH°; it prints "
        "no temperature either, so the world declares its own.",
        "The source binds no H+ to the nucleotides and no Mg2+ to phosphate; AMP waits for an "
        "adenylate kinase law (the lead's Q3 ruling).",
        "Binding rates are not potentials: a closure's k_on is the world's, declared in its block. "
        "The source's X_MgA (Table 1) is class C, set large.",
    ),
)
# cells.potential_set.beard2005@2 (D236): @1 with AMP2-, whose potential adenylate kinase's constant in base forms
# fixes, and AMP in the adenine and phosphorus moieties. Frame B, Eq. 24 as run and the balanced
# supply add nothing to the set: phosphate's proton form and the ATP reaction's total phosphate
# are @1's already, Eq. 7's protons are complex III's scalar protons, and the supply's held pair
# sets its drive against the declared reaction's anchor, which stays @1's.
BEARD_2005_V2 = BEARD_2005._replace(
    name="cells.potential_set.beard2005@2",
    rows=(*BEARD_2005.rows, ("AMP", -2)),
    reactions=(
        *BEARD_2005.reactions,
        SetReaction(
            "AMP", (("ADP", -2), ("ATP", 1), ("AMP", 1)), None, 1, None, (),
            f"{_BEARD_2005}, Eqs. 17 and 18 (adenylate kinase, 2 ADP -> ATP + AMP), in base forms "
            f"(D236; {_APPENDIX}, section 7): K_base 0.388964538, derived from the match",
            match=SetMatch(
                0.4331, (("Mg", 5.0e-3), ("ADP", 1.3e-3)),
                f"{_BEARD_2005}, Table 1: K_AK, unchanged by the correction, on totals (Eq. 18; "
                "footnote c: from Alberty 2003's tables, at conditions the source does not "
                "print). Converted with the set's own K_MgADP and K_MgATP at the free Mg2+ of the "
                "source's state-3 buffer, 5.0 mM total Mg2+ and 1.3 mM ADP, with no ATP or AMP "
                "(p. 0258; Figs. 2-5): 3.808553529 mM. The source never states the IMS's free "
                "Mg2+, so the match is declared (D236)",
            ),
        ),
    ),  # fmt: skip
    moieties=tuple(
        (moiety, (*weights, ("AMP", 1)) if moiety in ("adenine", "phosphorus") else weights)
        for moiety, weights in BEARD_2005.moieties
    ),
    notes=(
        *BEARD_2005.notes[:2],
        "The source binds no H+ to the nucleotides, and no Mg2+ to phosphate or to AMP. AMP2-'s "
        "potential is from adenylate kinase's constant in base forms (D236), whose ln K carries "
        "no temperature, as a form's ln K_d. Its constant on totals follows the free Mg2+ (0.153 "
        "at 1 mM, 0.491 at 5 mM), so the set derives K_base from the buffer it was matched at.",
        *BEARD_2005.notes[3:],
        "Frame B (D236): phosphate's protons count as protons, H2PO4- being a form of Pi that "
        "binds H+, and the ATP reaction's total phosphate is converted with the set's own k_dH, "
        "as in @1. The supply's declared reaction keeps @1's anchor, dG°' = 0 at pH 7 (the lead's "
        "ruling): a world holding the supply's neutral reductant pair sets the reference pH "
        "through the pair's ratio, S_red/S_ox = r h_ref / 1e-7 M (0.794 r at the ruled pH 7.10; "
        f"{_APPENDIX}, section 6).",
    ),
)
POTENTIAL_SETS = MappingProxyType({s.name: s for s in (BEARD_2005, BEARD_2005_V2)})


def potential_set_errors(potential_set):
    """Why a named set breaks its own contract (empty: it keeps it): its rows, references, forms,
    reactions and moieties well formed; each reaction solvable for the one row it determines, in
    order, every other row of it known by then; every non-reference row determined exactly once;
    every reaction conserving charge and every moiety of the set; and a reaction's totals only
    over rows whose forms bind the proton alone."""
    s, out = potential_set, []
    valence = dict(s.rows)
    if len(valence) != len(s.rows):
        out.append("its rows are distinct")
    if valence.get(s.proton) != 1:
        out.append(f"its proton row {s.proton} is one of its rows, at valence +1")
    if not set(s.references) <= set(valence):
        out.append("its references are rows of it")
    form_ids = [f.id for f in s.forms]
    if len(set(form_ids)) != len(form_ids) or set(form_ids) & set(valence):
        out.append("its forms' IDs are distinct, and no row's")
    for f in s.forms:
        if f.row not in valence or not all(
            ligand in valence and type(n) is int and n != 0 for ligand, n in f.counts
        ):
            out.append(f"form {f.id}: its row and ligands are rows of the set, its counts nonzero")
        if not (math.isfinite(f.dissociation_M) and f.dissociation_M > 0):
            out.append(f"form {f.id}: its dissociation constant is finite and positive")
    proton_only = {f.row for f in s.forms if [ligand for ligand, _ in f.counts] == [s.proton]}
    other = {f.row for f in s.forms} - proton_only
    known = set(s.references)
    for r in s.reactions:
        nu = dict(r.stoichiometry)
        if not (set(nu) <= set(valence) and all(type(n) is int and n for n in nu.values())):
            out.append(f"reaction for {r.determines}: its rows are the set's, its counts nonzero")
            continue
        if r.determines in known or r.determines not in nu:
            out.append(f"reaction for {r.determines}: it determines a row of it not yet known")
        elif not set(nu) - {r.determines} <= known:
            out.append(f"reaction for {r.determines}: its other rows are known before it")
        known.add(r.determines)
        if sum(valence[row] * n for row, n in nu.items()) != 0:
            out.append(f"reaction for {r.determines}: it conserves charge")
        for moiety, weights in s.moieties:
            if sum(w * nu.get(row, 0) for row, w in weights) != 0:
                out.append(f"reaction for {r.determines}: it conserves moiety {moiety}")
        if not (type(r.multiple) is int and r.multiple > 0):
            out.append(f"reaction for {r.determines}: its multiple is a positive integer")
        if r.totals and (r.proton_reference_M is None or not set(r.totals) <= proton_only - other):
            out.append(f"reaction for {r.determines}: its totals are over proton forms at a pH")
        out.extend(_match_errors(s, r, nu))
    if known != set(valence):
        out.append(f"its rows {sorted(set(valence) - known)} have no potential")
    for moiety, weights in s.moieties:
        if not all(row in valence and type(w) is int and w != 0 for row, w in weights):
            out.append(f"moiety {moiety}: its weights are nonzero integers on the set's rows")
    return out


def _match_errors(s, r, nu):
    """Why a set reaction's value is ill formed: one value, in kJ/mol or as a match; a match on
    the 1 M basis, with no totals and a multiple of 1, its constant on totals finite and positive,
    its buffer distinct rows of the set at finite positive totals, exactly one of them a ligand of
    the set's forms, and every form of its other rows and of the reaction's rows binding that
    ligand alone, so one mass balance fixes it."""
    where = f"reaction for {r.determines}"
    if (r.dG_kJ_mol is None) == (r.match is None):
        return [f"{where}: it gives one value, in kJ/mol or as a match"]
    if r.match is None:
        return []
    if r.proton_reference_M is not None or r.totals or r.multiple != 1:
        return [f"{where}: a matched constant is in base forms at 1 M, its multiple 1"]
    m, valence = r.match, dict(s.rows)
    buffer = dict(m.buffer_M)
    if not (
        isinstance(m.constant_on_totals, float)
        and math.isfinite(m.constant_on_totals)
        and m.constant_on_totals > 0
        and len(buffer) == len(m.buffer_M)
        and all(row in valence and math.isfinite(c) and c > 0 for row, c in buffer.items())
    ):
        return [
            f"{where}: its match has a finite positive constant on totals and a buffer of "
            "distinct rows at finite positive totals"
        ]
    ligands = {ligand for f in s.forms for ligand, _ in f.counts}
    held = [row for row in buffer if row in ligands]
    bound = {f.row for f in s.forms} & (set(buffer) | set(nu))
    if len(held) != 1 or any(
        [ligand for ligand, _ in f.counts] != held for f in s.forms if f.row in bound
    ):
        return [
            f"{where}: its match's buffer holds one ligand, which alone the forms of its other "
            "rows and of the reaction's rows bind"
        ]
    return []


def _matched_constant(s, r):
    """K_base of a matched reaction (SetMatch), as a Decimal in the caller's context: the buffer's
    free ligand m by bisection of its mass balance, monotone in m on (0, its total], then
    K_totals prod_rows P_row(m)^(-nu_row)."""
    m, nu = r.match, dict(r.stoichiometry)
    buffer = {row: Decimal(c) for row, c in m.buffer_M}
    (ligand,) = [row for row in buffer if any(row in dict(f.counts) for f in s.forms)]
    forms = {}
    for f in s.forms:
        if f.row in buffer or f.row in nu:
            ((_, n),) = f.counts  # The buffer's one ligand (potential_set_errors).
            forms.setdefault(f.row, []).append((n, Decimal(f.dissociation_M)))

    def polynomial(row, x):
        return sum((x**n / k for n, k in forms.get(row, ())), Decimal(1))

    def bound(row, x):
        return sum((n * x**n / k for n, k in forms.get(row, ())), Decimal(0)) / polynomial(row, x)

    low, high = Decimal(0), buffer[ligand]
    for _ in range(4 * FREE_ENERGY_DIGITS):  # Each halving gains a bit; 200 exceed 50 digits.
        x = (low + high) / 2
        held = x + sum(c * bound(row, x) for row, c in buffer.items() if row != ligand)
        low, high = (x, high) if held < buffer[ligand] else (low, x)
    x = (low + high) / 2
    value = Decimal(m.constant_on_totals)
    for row, n in nu.items():
        value *= polynomial(row, x) ** -n
    return value


def potential_set_values(name, *, temperature_K, standard_concentration_mM):
    """{row or form ID: mu°/RT} of the named set at a world's temperature (K) and c0 (mM), each
    evaluated at FREE_ENERGY_DIGITS digits and rounded once (module docstring): a reaction's
    dG°/RT at temperature_K (or -ln K_base, with no temperature, for a matched one) with
    its basis's logarithms (the scalar protons' nu_H ln(1 M / h_ref), and each total's
    nu ln P(h_ref), P the row's proton binding polynomial), a form's ln K_d, and every value moved
    to c0 by ln(c0 / 1 M). Its arithmetic is part of every set's version: a change that moves a
    set's doubles is a new version of that set, since check_potential_set compares them exactly
    (cells.potential_set.beard2005@2's constant path leaves @1's doubles bit for bit)."""
    s = POTENTIAL_SETS[name]
    problems = potential_set_errors(s)
    if problems:
        raise ValueError(f"Potential set {name}: " + "; ".join(problems))
    with localcontext() as ctx:
        ctx.prec = FREE_ENERGY_DIGITS
        rt = _gas_constant() * Decimal(temperature_K) / 1000  # kJ/mol
        shift = (Decimal(standard_concentration_mM) / Decimal(SET_C0_MM)).ln()
        polynomial = {}
        for f in s.forms:
            if [ligand for ligand, _ in f.counts] == [s.proton]:
                polynomial.setdefault(f.row, []).append((f.counts[0][1], Decimal(f.dissociation_M)))
        mu = {row: Decimal(0) for row in s.references}
        for r in s.reactions:
            nu = dict(r.stoichiometry)
            if r.match is None:
                x = Decimal(r.dG_kJ_mol) * r.multiple / rt
            else:  # In base forms at 1 M, with no temperature (SetReaction).
                x = -_matched_constant(s, r).ln()
            if r.proton_reference_M is not None:
                h = Decimal(r.proton_reference_M)
                x += nu.get(s.proton, 0) * (1 / h).ln()
                for row in r.totals:
                    x += nu[row] * (1 + sum(h**n / k for n, k in polynomial[row])).ln()
            known = sum(Decimal(n) * mu[row] for row, n in nu.items() if row != r.determines)
            mu[r.determines] = (x - known) / nu[r.determines]
        for f in s.forms:
            ligands = sum(Decimal(n) * mu[ligand] for ligand, n in f.counts)
            mu[f.id] = mu[f.row] + ligands + Decimal(f.dissociation_M).ln()
        return {key: float(value + shift) for key, value in mu.items()}


def _set_forms(s, row, values):
    valence = dict(s.rows)
    return [
        dict(
            id=f.id,
            counts=dict(f.counts),
            standard_mu_RT=values[f.id],
            valence=valence[f.row] + sum(n * valence[ligand] for ligand, n in f.counts),
        )
        for f in s.forms
        if f.row == row
    ]


def with_potential_set(raw, name, *, proton_buffers=None):
    """A copy of a raw @3 or composite definition with the named set applied whole (module
    docstring): every species the definition declares that the set names takes the set's valence
    check, potential and forms at the model's temperature_K and c0 (1000 mM where it declares
    none), the model declares the set's moieties over the rows it has, and potential_set names the
    set. Refused (ValueError): an unknown set, a definition that already names one, a row of the set
    that already declares a potential or forms (no mixing), a valence unlike the set's, and a moiety
    ID the definition already uses. proton_buffers {row: pK}: each a declared row outside the set,
    given the set's proton reference: its base at 0 and its protonated form, H<row>, at
    -pK ln 10 + mu°_H/RT (at 1 M, then moved to c0)."""
    if name not in POTENTIAL_SETS:
        raise ValueError(f"No potential set {name!r}: one of {sorted(POTENTIAL_SETS)}")
    s, out = POTENTIAL_SETS[name], copy.deepcopy(raw)
    m = out["model"]
    if m.get(SET_KEY) is not None:
        raise ValueError(f"The definition already names the potential set {m[SET_KEY]!r}")
    c0 = m.setdefault(MODEL_KEY, SET_C0_MM)
    values = potential_set_values(
        name, temperature_K=m["temperature_K"], standard_concentration_mM=c0
    )
    declared = {e["id"]: e for e in m["species"]}
    valence = dict(s.rows)
    buffers = dict(proton_buffers or {})
    for row in [r for r in declared if r in valence] + list(buffers):
        entry = declared[row]
        taken = [k for k in ("standard_mu_RT", "protonated_standard_mu_RT", "forms") if k in entry]
        if taken:
            raise ValueError(
                f"species {row} already declares {', '.join(taken)}: the rows of potential set "
                f"{name} take their potentials from it alone"
            )
    for row, entry in declared.items():
        if row not in valence:
            continue
        if entry.get("valence") != valence[row]:
            raise ValueError(
                f"species {row} has valence {entry.get('valence')!r}; {name} gives it "
                f"{valence[row]}"
            )
        entry["standard_mu_RT"] = values[row]
        forms = _set_forms(s, row, values)
        if forms:
            entry["forms"] = forms
    for row, pk in buffers.items():
        if row in valence or row not in declared:
            raise ValueError(
                f"proton buffer {row}: a declared species outside potential set {name}"
            )
        entry = declared[row]
        entry["standard_mu_RT"], form = _buffer_potentials(s, values, c0, row, pk, entry["valence"])
        entry["forms"] = [form]
    moieties = list(m.get(MOIETIES_KEY) or [])
    taken = {item.get("id") for item in moieties if isinstance(item, dict)}
    for moiety, weights in s.moieties:
        present = {row: w for row, w in weights if row in declared}
        if not present:
            continue
        if moiety in taken:
            raise ValueError(f"The definition already declares a moiety {moiety!r}")
        moieties.append(dict(id=moiety, weights=present))
    if moieties:
        m[MOIETIES_KEY] = moieties
    m[SET_KEY] = name
    if buffers:
        m[BUFFERS_KEY] = dict(buffers)
    return out


def _buffer_potentials(s, values, c0, row, pk, valence):
    """(base mu°/RT, its protonated form as declared) of a proton buffer on set s's proton
    reference, at c0: the base at 0 and the form H<row> at mu°_H/RT - pK ln 10, both at 1 M, then
    moved to c0 (values are the set's at c0). The one code with_potential_set writes them with and
    check_potential_set checks them with."""
    shift = math.log(c0 / SET_C0_MM)
    proton = values[s.proton] - shift
    form = dict(
        id=f"H{row}",
        counts={s.proton: 1},
        standard_mu_RT=proton - pk * math.log(10.0) + shift,
        valence=valence + 1,
    )
    return shift, form


def check_potential_set(spec):
    """Refuse a definition naming a potential set whose rows depart from it (module docstring):
    each species of the model that the set names has the set's valence, and the set's potential
    and forms at the model's temperature and c0, exactly (a hand edit, a value from elsewhere, or
    a temperature changed after the set was applied); each of the set's moieties over the rows
    present is declared, with the set's weights (the guard of the references' limit, so required);
    and each recorded proton buffer has the potentials with_potential_set gives it, exactly. Rows
    the set does not name are the world's, and so are its other moieties."""
    model = declared(spec)
    if model is None or model.potential_set is None:
        return
    s, m = POTENTIAL_SETS[model.potential_set], _inner_model(spec)
    c0 = model.standard_concentration_mM
    if c0 is None:
        raise ConfigError(f"potential set {s.name}: the model declares no standard concentration")
    values = potential_set_values(
        s.name, temperature_K=m.temperature_K, standard_concentration_mM=c0
    )
    valence, ids = dict(s.rows), dict(zip(m.species_ids, m.valence, strict=True))
    for row in m.species_ids:
        if row not in valence:
            continue
        entry, where = model.entry(row), f"species {row} (potential set {s.name})"
        if ids[row] != valence[row]:
            raise ConfigError(f"{where}: its valence is {ids[row]}, not the set's {valence[row]}")
        given = (
            entry.standard_mu_RT,
            entry.protonated_standard_mu_RT,
            [(f.id, dict(f.counts), f.standard_mu_RT, f.valence) for f in entry.forms],
        )
        wanted = (
            values[row],
            None,
            [(f["id"], f["counts"], f["standard_mu_RT"], f["valence"])
             for f in _set_forms(s, row, values)],
        )  # fmt: skip
        if given != wanted:
            raise ConfigError(
                f"{where}: its potentials {given} are not the set's {wanted} at "
                f"{m.temperature_K!r} K and {c0!r} mM: a named set's rows take their potentials "
                "from it alone, at the world's temperature"
            )
    declared_moieties = {moiety.id: dict(moiety.weights) for moiety in model.moieties}
    for moiety, weights in s.moieties:
        present = {row: w for row, w in weights if row in ids}
        if present and declared_moieties.get(moiety) != present:
            raise ConfigError(
                f"potential set {s.name}: its moiety {moiety} over the rows present, {present}, "
                f"is declared as {declared_moieties.get(moiety)}: a named set's moieties are "
                "required, since its references hold only for reactions that conserve them"
            )
    for row, pk in model.proton_buffers:
        entry = model.entry(row)
        base, form = _buffer_potentials(s, values, c0, row, pk, ids[row])
        given = (
            entry.standard_mu_RT,
            entry.protonated_standard_mu_RT,
            [(f.id, dict(f.counts), f.standard_mu_RT, f.valence) for f in entry.forms],
        )
        wanted = (base, None, [tuple(form.values())])
        if given != wanted:
            raise ConfigError(
                f"proton buffer {row} (potential set {s.name}, pK {pk!r}): its potentials {given} "
                f"are not {wanted}, on the set's proton reference at {c0!r} mM"
            )


# ------------------------------------------------------------------ moieties (B2)


def check_moieties(spec):
    """Refuse a kind mode, a declared free-energy entry or an operator's reported move that
    changes a declared moiety (module docstring, "Moieties"): each mode resolved through its
    kind's role_species (entity_modes), its net change over both ends being its chemistry, each
    entry's stoichiometry, and each move of an operator's species_moieties, sum w nu = 0 exactly
    for every moiety; naming the mover, the mode, entry or move, the moiety and its change. A model
    without moieties is not checked: a known limit, since its operators' species_moieties are then
    not read, and the hook's shape is not checked there either."""
    model = declared(spec)
    if model is None or not model.moieties:
        return
    from cells.registry import kind_registry

    def changes(net, where):
        for moiety in model.moieties:
            change = sum(Fraction(w) * Fraction(net.get(row, 0)) for row, w in moiety.weights)
            if change:
                raise ConfigError(
                    f"{where}: it changes moiety {moiety.id} by {float(change):+g} per turnover; "
                    "every declared moiety is conserved (the registry's moieties)"
                )

    m, registry = _inner_model(spec), kind_registry.active()
    try:
        for kind_id, declaration in getattr(m, "kinds", ()):
            resolved = entity_modes(registry.lookup(kind_id), declaration)
            for law_id, _, modes in resolved or ():
                for mode, rows in sorted(modes.items(), key=lambda item: str(item[0])):
                    net = {}
                    for species, _, count in rows:
                        net[species] = net.get(species, 0) + Fraction(count)
                    changes(net, f"Kind {kind_id}'s move under {law_id}, mode {mode}")
    except ValueError as error:
        raise ConfigError(str(error)) from error
    for where, entries in declared_free_energies(spec):
        for index, entry in enumerate(entries):
            changes(dict(entry.stoichiometry), f"{where}, entry {index}")
    from cells.registry import operators as operator_registry

    rows = set(m.species_ids)
    try:
        for op, declaration in _entries(spec):
            for name, pairs in operator_registry.operator_species_moieties(op, declaration):
                where = f"Operator {op.LAW_ID}'s move {name}"
                stray = [species for species, _ in pairs if species not in rows]
                if stray:
                    raise ConfigError(
                        f"{where}: it names {stray[0]!r}, which is not a species of the model"
                    )
                changes(dict(pairs), where)
    except ValueError as error:
        raise ConfigError(str(error)) from error


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
    its material_balance_atol_fmol. Definitions without a registry keep the inner model's own
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
    not refused here.

    One exception, §5.2's own (the kinds owner's K1; a D148 widening of this check): a declared
    kind's move of the row at a node where a general closure holds it, under a law that declares
    its moves in base forms (forms "base"), is not refused here. check_closure_rows' admission
    holds it instead: the closure's read among its law's reads, the kind's role_species, each
    resolved mode in base rows with zero charge, and its moved rows the resolved ones. A move of
    the row at a node no closure holds it at, or under a law without base forms, stays refused."""
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
    deferred = _deferred_to_closure(spec)
    for species, label in labels.items():
        for kind in ("cell", "outside"):
            for mover in moved.get(species, {}).get(kind, ()):
                if mover in deferred.get(species, ()):
                    continue  # §5.2's admission holds it (check_closure_rows).
                raise ConfigError(
                    f"species {species} has {label}: {mover} moves its {kind} rows, and {reason}"
                )
    for op, declaration in _entries(spec):
        for item in operator_identities(op, declaration):
            if item.id in labels:
                raise ConfigError(
                    f"species {item.id} has {labels[item.id]}: {op.LAW_ID} names it, and {reason}"
                )


INNER_MOVERS = ("membrane", "junction", "channel", "face", "pump")
# The forms face law (laws/routes/logmean_electrodiffusion_forms; MT-1b's face note, §4's
# admission): at a general closure's rows it moves each binder's forms and each ligand's free
# amount from the closure's own read, so check_closure_rows admits it there, as it admits a kind
# whose law reads the closure; today's face law stays refused. Names, so this module imports no law.
FORMS_FACE_LAW, FORMS_FACE_READ = "cells.route.logmean_electrodiffusion_forms@1", "cells.binding.rapid_binding@1"


def _deferred_to_closure(spec):
    """{species: {mover, ...}}: the moves check_two_form_rows leaves to check_closure_rows'
    admission, each named as moved_in_step names it: a declared kind's move of a row at a node
    where a general closure holds that row (its closure_rows), under a law that declares base
    forms; and a forms face (FORMS_FACE_LAW) that moves a row the closure holds at both its ends (a
    binder as its forms). {} for a world without a general closure, whose movers are then not built
    here."""
    if not any(hasattr(d, "closure_rows") for _, d in getattr(spec.model, "kinds", ())):
        return {}
    from cells.registry import laws

    m = _inner_model(spec)
    held = {
        row for _, d in getattr(m, "kinds", ()) if hasattr(d, "closure_rows")
        for row in d.closure_rows
    }  # fmt: skip
    _, movers = inner_movers(spec)
    ends = _entity_ends(m)
    out = {}
    for species, entries in movers.items():
        for kind, law_id, nodes in entries:
            if kind == "face" and law_id == FORMS_FACE_LAW:  # Its binder held at both its ends.
                for entity in nodes:
                    if all((species, end) in held for end in ends.get(entity, (entity,))):
                        out.setdefault(species, set()).add(_named(kind, law_id, entity))
                continue
            if kind in INNER_MOVERS or law_id not in laws.active():
                continue
            if getattr(laws.active().lookup(law_id), "forms", None) != "base":
                continue
            for node in nodes:
                if (species, node) in held:
                    out.setdefault(species, set()).add(f"{kind} ({law_id}) at {node}")
    return out


def _law_reads(law_id):
    """The stage reads a kind move's law declares (a cycle law's reads), or () for a law that
    declares none (a route law) or that the active law registry does not hold."""
    from cells.registry import laws

    try:
        law = laws.active().lookup(law_id)
    except KeyError:
        return ()
    return tuple(getattr(law, "reads", ()) or ())


def _entity_ends(m):
    """{entity ID: its two end nodes}: patches, junctions, faces and channels (their patch's)."""
    ends = {p.id: (p.inside, p.outside) for p in m.membranes}
    ends |= {j.id: (j.sender, j.receiver) for j in m.junctions}
    ends |= {f.id: (f.sender, f.receiver) for f in m.faces}
    ends |= {f.id: (f.sender, f.receiver) for f in getattr(m, "forms_faces", ())}  # Their own set.
    ends |= {c.id: ends[c.membrane_id] for c in m.channels}
    return ends


def mode_errors(valence, form_ids, rows, declares_base_forms):
    """§5.2's admission of one mover mode at a general closure's rows, its charge half; the moiety
    half is check_moieties', which check_definition runs ahead of the closure rows for every mode,
    a closure's movers included: the reasons the mode is refused, or () when it is admitted. rows
    are ((species, node, count), ...), resolved: each count a number per forward
    cycle, inward-positive, at its node. valence is {species: z} over the model's rows, and
    form_ids are every binder form's ID.
    - A mover whose law declares no base forms (its forms is not "base") is refused by name.
    - A row that names a binder's form is refused: a form is moved only as its base row with every
      ligand written out, so the closure's totals, counted from the base forms, stay exact.
    - The mode's charge, the sum of valence x count over its rows at every node, must be zero: a
      base-form reaction that drops a ligand changes the charge (the references' C3 movers)."""
    if not declares_base_forms:
        return ("its law declares no base forms (forms is not \"base\"): an undeclared mover",)
    out = []
    as_forms = sorted({species for species, _, _ in rows if species in form_ids})
    if as_forms:
        out.append(f"it moves the forms {as_forms} as rows: write each as its base row and ligands")
    unknown = sorted({species for species, _, _ in rows
                      if species not in valence and species not in form_ids})  # fmt: skip
    if unknown:
        out.append(f"it moves {unknown}, which are not rows of the model")
    if not as_forms and not unknown:
        charge = math.fsum(valence[species] * count for species, _, count in rows)
        if charge != 0:
            out.append(f"its charge per cycle is {charge:+g}, not zero")
    return tuple(out)


def entity_modes(kind, declaration):
    """§5.2's resolution of a kind's moves for one declaration, or None for a kind that declares
    no role_species. One entry per entity, (law ID, law, {mode: ((species, node, count), ...)}):
    its law's change rows (registry/laws.cycle_changes, the one source the manifest reads) bound
    through the kind's EntityBinding (kind_registry.kind_role_species). Each role is bound to its
    species, each end to its node, and each parameter-named count to that entity's value. A
    moves-only law's rows land at MOVES_ENDS: inward-positive at the inside, with the opposite sign
    at the outside."""
    from cells.registry import kind_registry
    from cells.registry import laws as law_registry

    bindings = kind_registry.kind_role_species(kind, declaration)
    if bindings is None:
        return None
    inside, outside = kind_registry.MOVES_ENDS
    out = []
    for binding in bindings:
        law = law_registry.active().lookup(binding.law_id)
        modes = {}
        for row in law_registry.cycle_changes(law):
            role, _, end = row["role"].partition("@")
            count = row["per_cycle"]
            if isinstance(count, str):
                count = (-1 if count.startswith("-") else 1) * binding.parameters[count.lstrip("-")]
            species, rows = binding.roles[role], modes.setdefault(row.get("mode", 0), [])
            if end:
                rows.append((species, binding.ends[end], count))
            else:
                rows += [(species, binding.ends[inside], count),
                         (species, binding.ends[outside], -count)]  # fmt: skip
        out.append((binding.law_id, law, {mode: tuple(rows) for mode, rows in modes.items()}))
    return tuple(out)


def _route_law(law_id):
    """Whether a kind move's law is a route law (registry/laws.RouteLaw's interface)."""
    from cells.registry import laws

    try:
        law = laws.active().lookup(law_id)
    except KeyError:
        return False
    return type(law).interface == laws.ROUTE_LAW


def _route_mover_errors(closure, law_id, species):
    """§5.2's admission of a kind's route law at a general closure's rows (MT-1b's face plan, item
    3; the binding owner's file, under the lead's leave), after the reads check: the reasons it is
    refused, or (). Its one carried row is a ligand of the closure, whose stage read writes that
    ligand's free amount into its row, so the route moves the ligand's base form, never a binder's
    forms (a binder's row holds their total); and it crosses between the two ends of the hosts it
    sits on (a patch or a junction), so it moves that row out of one end and into the other. The
    moieties wait for item 6, as for every mover here."""
    from cells.registry import laws

    law = laws.active().lookup(law_id)
    out = []
    if species not in closure.ligands:
        out.append(
            f"under {law_id}, {species} is no ligand of the closure: a route law moves a ligand's "
            "free amount, never a binder's forms"
        )
    if not set(law.hosts) <= {"membrane", "junction"}:
        out.append(f"under {law_id}, its hosts {list(law.hosts)} are not two-ended")
    return tuple(out)


def _closure_mover_errors(spec, m, kind_id, law_id, rows):
    """§5.2's admission of a kind's moves under one law at a general closure's rows (the charge
    half; the moieties wait for item 6): the reasons it is refused, or (). The kind must declare
    role_species; every entity of that law must declare its stoichiometry in base forms (its law's
    forms is "base"), with each mode passing mode_errors; and every closure row the kind's
    moved_rows names under that law must be among its entities' resolved rows (the cross-check)."""
    from cells.registry import kind_registry

    kind = kind_registry.active().lookup(kind_id)
    declaration = dict(m.kinds)[kind_registry.qualified(kind_id)]
    resolved = entity_modes(kind, declaration)
    if resolved is None:
        return (f"its kind {kind_id} declares no role_species, so its rows cannot be resolved",)
    valence = dict(zip(m.species_ids, m.valence, strict=True))
    registry = getattr(m, "species_registry", None)
    form_ids = {f.id for entry in getattr(registry, "entries", ()) for f in entry.forms}
    out, placed = [], set()
    for binding_law, law, modes in resolved:
        if kind_registry.qualified(binding_law) != kind_registry.qualified(law_id):
            continue
        for mode, mode_rows in sorted(modes.items(), key=lambda item: str(item[0])):
            errors = mode_errors(valence, form_ids, mode_rows, getattr(law, "forms", None) == "base")
            out += [f"under {law_id}, mode {mode}: {error}" for error in errors]
            placed |= {(species, node) for species, node, _ in mode_rows}
    unplaced = sorted(set(rows) - placed)
    if unplaced and not out:
        out.append(f"its moved_rows name {unplaced} under {law_id}, which its entities' resolved "
                   "rows do not hold")  # fmt: skip
    return tuple(out)


def check_closure_rows(spec):
    """The movers at a node where a general binding closure holds rows (seam C, version 2;
    docs/CORE_SEAMS_DESIGN.md §19 as amended at 20:09 UTC, 18 November 2026). A declared kind
    whose declaration carries closure_rows, ((species, node ID), ...), and read_id is such a
    closure. At its rows:
    - @3's own routes and pumps (membrane, junction, channel, face, pump) are refused: they read
      stored totals as concentrations;
    - a kind's in-step move is admitted only when its law's reads name the closure's read ID, so
      no mover reads a stored total (a route law without reads is refused). A route law that reads
      the closure (MT-1b's leak @2) is admitted where its row is a ligand of the closure and its
      hosts two-ended (_route_mover_errors; the face plan's item 3). For a cycle law, the read
      is kept beside §5.2's admission (the lead, 19 November 2026), which follows it: the kind
      declares role_species, its law declares base forms, each resolved mode passes mode_errors
      (the charge half; the moieties wait for item 6), and its moved_rows at the closure are its
      entities' resolved rows (_closure_mover_errors). No shipped kind declares role_species yet,
      so none is admitted: the transporter's comes with the kinds owner after seam A;
    - an operator that names a held species, or moves one in the step, is refused by
      check_stage_read_rows, which holds every stage read's rows, version 1's included. Operators
      that name no row (replacement, division, insertion) are admitted: the closure re-solves from
      the totals they leave. The water law and the lumen's fill are refused there too.
    Version 1's closure declares no closure_rows, so its worlds are not checked here.

    Why here and not in the closure's kind: the rule reads each kind move's law from the law
    registry (_law_reads), which the import surface cells.modules does not export, and kinds/ is
    held to the F owner's recorded import guard, where a new import would be a new entry. The
    registry already refuses the movers of two-form and multi-form rows, so the movers' rule for
    a closure's rows sits beside it (the lead, 18 November 2026). It also sees a composite's
    operators, which the kinds' own checks, on the inner spec, do not."""
    if not any(hasattr(d, "closure_rows") for _, d in getattr(spec.model, "kinds", ())):
        return  # No general closure: nothing to check, and no projection is built.
    m = _inner_model(spec)
    closures = [d for _, d in getattr(m, "kinds", ()) if hasattr(d, "closure_rows")]
    from cells.registry.kind_registry import qualified

    _, movers = inner_movers(spec)
    ends = _entity_ends(m)
    for closure in closures:
        rows, read = set(closure.closure_rows), closure.read_id
        for species, entries in movers.items():
            for kind, law, entities in entries:
                for entity in entities:
                    nodes = ends.get(entity, (entity,)) if kind in INNER_MOVERS else (entity,)
                    for node in nodes:
                        if (species, node) not in rows:
                            continue
                        held = f"species {species} at {node} is held by the closure {read}"
                        if kind == "face" and law == FORMS_FACE_LAW and read == FORMS_FACE_READ:
                            continue  # The forms law moves each form at the closure's read.
                        if kind in INNER_MOVERS:
                            raise ConfigError(
                                f"{held}: the {kind} {entity} moves it in the step, and @3's own "
                                "routes and pumps read stored totals (refused at a closure node)"
                            )
                        reads = _law_reads(law)
                        if qualified(read) not in {qualified(r) for r in reads}:
                            raise ConfigError(
                                f"{held}: {kind} moves it under {law}, whose reads "
                                f"{list(reads)} lack {read}; a mover at a closure node reads the "
                                "closure"
                            )
                        if _route_law(law):  # MT-1b's face plan, item 3: a route law's own branch.
                            errors = _route_mover_errors(closure, law, species)
                        else:
                            at_rows = sorted(
                                (s, n) for s, kinds in movers.items() for k, w, ns in kinds
                                if k == kind and w == law for n in ns if (s, n) in rows
                            )  # fmt: skip
                            errors = _closure_mover_errors(spec, m, kind, law, at_rows)
                        if errors:
                            raise ConfigError(
                                f"{held}: §5.2's admission refuses {kind}'s move under {law}: "
                                f"{'; '.join(errors)}"
                            )


# Operators that sum every stored row of a node as free particles (the second review's finding 3,
# verified; the lead's ruling, 18 November 2026): the water law's osmolyte sum, and the lumen's
# fill, whose bath work and dilution term sum the stored rows (cells.operator.restricted_cleft_lumen@2 reuses
# @1's fill unmodified). Beside a stage read that stores totals (a closure: H_eq beside its
# buffers' totals) they count every bound ligand twice.
WATER_LAWS = ("cells.operator.ideal_osmosis_linear_compliance_water@1",)
LUMEN_LAWS = ("cells.operator.restricted_cleft_lumen@1", "cells.operator.restricted_cleft_lumen@2")


def check_stage_read_rows(spec):
    """Operators beside a stage read that stores totals, refused at the definition (the second
    review's finding 3, verified; the lead's ruling, option (a), 18 November 2026). Each declared
    kind with a stage read names the rows it rewrites (its stage_rows: a closure's ligand and
    binder rows at its nodes). Operators read the stored rows, so beside such a read:
    - an operator that names a read species (its species_identities: a regulated availability's
      state inputs, a reaction's, an exchange's, a turnover's or a site's species) or moves one in
      the step is refused, since it would read or write the stored total (H_eq/V) as the free
      species. The rule is per species, not per node, until operators declare their nodes: an
      operator naming H anywhere is refused while any read holds H somewhere (the lead, 18
      November 2026);
    - the water operators (WATER_LAWS) are refused beside any such read: their osmolyte sum counts
      the stored rows, so bound ligands count twice (a plant took up 17% more water);
    - the lumen's fill (LUMEN_LAWS) is refused where a read holds rows at an outside node: its
      dilution term sums the lumen's stored rows, and the closure reads the node at its declared
      volume, not the lumen's.
    A world without a stage read, or without operators, is not checked, and neither is a read
    whose stage_rows name no row: an identity read stores no totals, so nothing counts twice.
    Reading through the closure (option (b)) waits until an experiment needs it."""
    if not hasattr(spec.model, "operators"):
        return  # No composite, no operators.
    from cells.registry import kind_registry

    m = _inner_model(spec)
    registry = kind_registry.active()
    reads = []
    for kind_id, declaration in getattr(m, "kinds", ()):
        kind = registry.lookup(kind_id)
        if kind.stage_read is not None and kind.stage_rows is not None:
            # Each row as (species, node), normalized here: mixed list and tuple rows from one kind,
            # or two rows of one (species, node) whose third items are None and a law ID, made
            # sorted(rows) below raise TypeError. A malformed row is @3's to refuse
            # (_check_stage_rows), which in a composite runs first, in the inner parse.
            rows = tuple(
                tuple(row[:2])
                for row in kind.stage_rows(declaration)
                if isinstance(row, (tuple, list)) and len(row) in (2, 3)
            )
            if rows:  # A read that rewrites no row (an identity read) stores nothing.
                reads.append((kind_registry.qualified(kind_id), rows))
    if not reads:
        return
    outside = {o.id for o in m.extracellular}
    for kind_id, rows in reads:
        nodes = {}
        for row in sorted(rows):  # (species, node), with the read's law as an optional third.
            nodes.setdefault(row[0], row[1])
        outside_nodes = sorted({row[1] for row in rows} & outside)
        for op, declaration in _entries(spec):
            if op.LAW_ID in WATER_LAWS:
                raise ConfigError(
                    f"{op.LAW_ID} sums every stored row as free particles, so beside the stage "
                    f"read of {kind_id}, which stores totals, it counts bound ligands twice: "
                    "refused"
                )
            if op.LAW_ID in LUMEN_LAWS and outside_nodes:
                raise ConfigError(
                    f"{op.LAW_ID}'s fill sums the lumen's stored rows as free particles, and the "
                    f"stage read of {kind_id} holds rows at outside node {outside_nodes[0]}, read "
                    "at its declared volume: refused"
                )
            named = [item.id for item in operator_identities(op, declaration)]
            if op.PROCESS:
                named += [s for s, _ in op.moves_in_step(spec, declaration)]
            for species in named:
                if species in nodes:
                    raise ConfigError(
                        f"species {species} is held by the stage read of {kind_id} at "
                        f"{nodes[species]}: {op.LAW_ID} names or moves it, and would read or "
                        "write its stored total as the free species: refused"
                    )


# Route laws that read their row's amounts at both ends, never a closure's free forms (FR-15 P2:
# cells.route.passive_constant_field_permeation@1; the lead's ruling of 19 November 2026, option (a)). The
# charged law is listed because its flux and its material slope |dJ/dn| are taken against the
# stored amount, which at a closure row is the total, not the free species: the wrong derivative.
# Any future route law with a material term must be checked against this list. The proton leak is
# not one: it reads free h through B4's closure.
AMOUNT_READING_ROUTE_LAWS = ("cells.route.passive_constant_field_permeation@1",)


def check_amount_reading_routes(spec):
    """A route law that reads amounts (AMOUNT_READING_ROUTE_LAWS), refused at a row a declared
    kind's closure holds, fail-closed (FR-15 P2): a stage read's stage_rows (B4's proton and buffer
    rows at its buffered nodes) or a general closure's closure_rows, at either end of the route.
    The stored total there is not the free species the law would read. Beside check_closure_rows
    and check_stage_read_rows, which hold the same rows for the other movers; per (species, node),
    from each declared kind's moved rows (the core's join, inner_movers). A world with no closure
    is not checked, and its movers are not built (no new path in a closure-free world). A general
    closure's rows refuse such a route earlier, in check_closure_rows (a route law declares no
    reads, so its reads [] lack the closure's read), so this rule's own message fires at held rows
    outside any closure_rows: today, B4's stage rows."""
    m = _inner_model(spec)
    kinds = getattr(m, "kinds", ())
    if not kinds:
        return
    from cells.registry.kind_registry import active, qualified

    registry, held = active(), {}
    for kind_id, declaration in kinds:
        kind = registry.lookup(kind_id)
        rows = ()
        if kind.stage_read is not None and kind.stage_rows is not None:
            rows = tuple(kind.stage_rows(declaration))
        rows += tuple(getattr(declaration, "closure_rows", ()))
        for row in rows:  # A malformed row (not species, node[, law]) is @3's to refuse, later.
            if isinstance(row, (tuple, list)) and len(row) in (2, 3):  # @3 admits list rows too.
                held.setdefault((row[0], row[1]), qualified(kind_id))
    if not held:
        return
    reading = {qualified(law) for law in AMOUNT_READING_ROUTE_LAWS}
    _, movers = inner_movers(spec)
    moves = [
        (species, law, kind, node)
        for species, entries in movers.items()
        for kind, law, nodes in entries
        if kind not in INNER_MOVERS and qualified(law) in reading
        for node in nodes
    ]
    for species, law, kind, node in moves:
        if (species, node) in held:
            raise ConfigError(
                f"species {species} at {node} is held by {held[(species, node)]}, which owns its "
                f"free/total split: {kind} moves it under {law}, which reads amounts, not free "
                "forms: refused (FR-15)"
            )


def check_definition(spec):
    """The registry's definition-time checks, for the core's hook to call ahead of the inner
    model's own: absent rows and backgrounds, two-form and multi-form rows, the forms' valences, a
    named potential set's rows, the moieties, the movers at a general closure's rows, the
    operators beside a stage read, the amount-reading route laws at a closure's rows, then
    operators' potentials and the reaction-level standard free energies of operators and kinds."""
    check_background(spec)
    check_two_form_rows(spec)
    check_forms(spec)
    check_potential_set(spec)
    check_moieties(spec)
    check_closure_rows(spec)
    check_stage_read_rows(spec)
    check_amount_reading_routes(spec)
    check_potentials(spec)
    check_free_energies(spec)


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
