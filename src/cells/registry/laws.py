"""The law template and the law registry (docs/CORE_SEAMS_DESIGN.md §8.1 and §8.3).

Provisional, as cells.modules is (D195): the template may still change before a first outside
module arrives.

**The template (§8.1).** A law declares one frozen record of its interface's type. Every type is
built on `Law`, which holds what every law declares:
- `law_id`, namespaced (`namespace.name@major`; a bare ID is in `cells`), named for its mechanism
  and its form, never for a protein; and its `interface`, a class constant of its type (an ID with
  its major);
- `host`, the namespaced ID of what runs it: a kind (`cells.transporter@1`), or the inner model
  for its own populations (`cells.resolved_pump_tissue@3`). This is version 1's restriction: each
  law's kernel is written against its host's arrays, so a host finds its laws by (interface, host),
  never in a module tuple, and refuses by name any law of its own that its version-1 code has no
  kernel path for. The cycle kind's general layout is meant to relax it for cycle laws (§3.5).
  A route law's `hosts` are something else: the entities its routes sit on;
- `provenance`: "parity" (moved from an older family; moving is not calibrating), "cited" or
  "calibrated", with `source`, what it rests on. A cited law gives a `Citation` and a calibrated
  law its data and method; both are required. A parity law may give §8.6's `moved_from` record.
  A Citation names its works as data (`works`, each a `CitedWork`: authors, year, title, and a DOI
  or a URL), so a reader can link them; whether a work was read is said on the piece's page
  (docs/library/), since that changes as people read it;
- `test`: the ID of the test that checks its kernel against its reference with a planted error
  (D187), so a manifest can link the evidence;
- B8's four optional fields (D175), reserved: a declaration that sets one is refused until their
  first consumer lands.
Each interface's type adds its own fields after `law_id`, so today's declarations keep their
fields and their positional order. The template's own fields are keyword-only. Each type also
states, as class constants, the units (UNITS) and signs (SIGNS) of its own fields, which the
declarations manifest (registry/declarations.py) writes out.

**The interfaces:**
- `cells.channel_law@1`, `ChannelLaw`: a channel population's law on @3
  (docs/INNER_MODEL_V4_DESIGN.md §7.1). H1's channel-law fields join as optional fields (§8.1);
- `cells.cycle_law@1`, `CycleLaw` (also named `PumpLaw`): a membrane cycle, such as @3's two pumps
  and the transporter kind's two laws. Seam A adds its modes and its S or J as optional fields;
- `cells.route_law@1`, `RouteLaw`: a passive route law;
- a cycle and a route law name their step terms (docs/CORE_SEAMS_DESIGN.md §18, amended): each is
  the name of the kernel that supplies it, or None where the law has none. `stage_term`, its charge
  slope in the per-stage rule; `material_term`, its material slope per stage; `charge_bound` and
  `material_bound`, its definition-time bounds on a charged and on a neutral row. Its host's
  hooks evaluate them (registry/kind_registry.Kind: stage_term, material_term, bound_rate), and
  refusal 4 reads which a law declares (operators/compartments.py). Each may also declare `forms`:
  "base" where its stoichiometry is written in base forms with every ligand out, so a rapid binding
  closure's totals stay exact (§5.2's admission; None otherwise). A cycle law may carry its general
  form, `cycle` (seam A's CycleForm, the kinds owner's type, checked by its own errors(): this
  module imports no law module), whose changes() gives its change rows. cycle_changes(law) reads a
  cycle law's change rows as declared, from its form or else its moves: the manifest's and §5.2's
  single-mode admission's one source;
- `cells.binding_law@1`, `BindingLaw`: a rapid binding closure (seam C). Its general form
  (CORE_SEAMS §19 as amended) declares `forms="registry"` (its binders' forms are the species
  registry's) and the kernels free_energy (G*), envelope (the lag envelope) and free_amounts (the
  free forms from the totals, P1's predictor's), each None in version 1;
- `cells.junction_law@1`, `JunctionLaw`: @3's junction conductance law. Its contract (a gated
  state with kinetics(V, parameters), a right-hand side, a domain and a voltage bound) is not the
  membrane channel's (codes, named gates, permeant ions, an RK4 step), so it takes an interface of
  its own. Two defaulted fields (FR-30) let it hold gates in series: `gate_count` (1) and
  `conductance` (None: the one gate's state is the conductance).
These five are the initial set, each held to its type. The set is open to built-in families: the
`cells` namespace is reserved (docs/MODULE_SYSTEM_DESIGN.md §2.3), so a built-in family declares its
interfaces as `cells.*` in its row of the static model table (registry/model_table.py), named for
what they are, and a declaration of one is a type built on `Law` whose own `errors()` checks its own
fields. An outside package's interfaces are in its own namespace.

**The registry (§8.3)** is build-scoped, as the kinds' is (registry/kind_registry.py):
- one registration call, `registry.register(law)`. It checks the declaration against the
  template and refuses a second law under one namespaced ID, whatever the spelling;
- BUILTIN holds the built-in laws, each registered from its own home through that call. The homes
  are the static model table's `law_homes` (registry/model_table.py), loaded by name, once, when
  the registry is first used, so the core imports no law module to find a law, and what is
  registered never depends on what happened to be imported first. A home either calls the
  registration call itself, or is an inert law module (§8.2): it declares its one law as `LAW`,
  importing only cells.modules and laws/, and the loader registers it with the module as its
  declarer, so importing it registers nothing;
- the active registry is BUILTIN, unless a caller builds inside `scope(registry)`;
- a registered law that no definition declares changes nothing: the inner model and the kinds
  read only the laws their declarations name;
- each `cells` law ID names one object in every registry. Another registry holds a cells law only
  as BUILTIN's own declaration, so caches keyed on law IDs (the inner model's implementation and
  compile_window) never mix two declarations under one ID. An outside law takes its own namespace.
  Module stage 1 stamps its structure entries with its declaration (MODULE_SYSTEM_DESIGN.md §2.5).
"""

import importlib
import math
import re
import sys
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import KW_ONLY, dataclass
from types import MappingProxyType
from typing import ClassVar, NamedTuple

from cells.registry.kind_registry import NAMESPACE, qualified
from cells.registry.model_table import MODELS

__all__ = (
    "BINDING_LAW",
    "BUILTIN",
    "BUILTIN_PACKAGES",
    "CHANNEL_LAW",
    "CYCLE_LAW",
    "FAMILY_INTERFACES",
    "INTERFACES",
    "JUNCTION_LAW",
    "PROVENANCES",
    "ROUTE_LAW",
    "STEP_TERMS",
    "BindingLaw",
    "ChannelLaw",
    "Citation",
    "CitedWork",
    "CycleLaw",
    "JunctionLaw",
    "Law",
    "LawRegistry",
    "PumpLaw",
    "RouteLaw",
    "active",
    "cycle_changes",
    "hosted_laws",
    "scope",
)

CHANNEL_LAW = "cells.channel_law@1"
CYCLE_LAW = "cells.cycle_law@1"
ROUTE_LAW = "cells.route_law@1"
BINDING_LAW = "cells.binding_law@1"
JUNCTION_LAW = "cells.junction_law@1"
PROVENANCES = ("parity", "cited", "calibrated")
_ID = re.compile(r"(?:[a-z][a-z0-9_]*\.){0,2}[a-z][a-z0-9_]*@[1-9][0-9]*")


def _is_id(value, *, namespaced=False):
    """A law or host ID, [namespace.[family.]]name@major; namespaced: an interface's, exactly
    namespace.name@major."""
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        return False
    return not namespaced or value.split("@", 1)[0].count(".") == 1


def _named(value):
    return isinstance(value, str) and bool(value)


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


class CitedWork(NamedTuple):
    """One work a Citation rests on, as data: its authors (a tuple of names, as the work gives
    them), its year, its title, and its DOI (without "https://doi.org/") or a URL; one at least."""

    authors: tuple
    year: int
    title: str
    doi: str | None = None
    url: str | None = None


class Citation(NamedTuple):
    """A cited law's source (§8.1): the work, the place in it, the licence of any numbers taken
    from it (D186) and the law's departures from it, each in a few words; and `works`, the works it
    names, each a CitedWork. A citation of Cells' own documents names no work."""

    source: str
    place: str
    licence: str
    departures: tuple = ()
    works: tuple = ()


@dataclass(frozen=True)
class Law:
    """The law template (module docstring): what every law declares."""

    law_id: str
    _: KW_ONLY
    host: str
    provenance: str = "parity"
    source: object = None
    test: str | None = None
    # The four optional fields of a law that stands in for something (D175, B8): reserved.
    represents: object = None
    preserves: object = None
    supports: object = None
    qualified: object = None

    interface: ClassVar[str | None] = None
    # D175's four fields stay reserved, except on an interface that declares itself a level of
    # detail: D304 makes OL6's cells.assembly_representation@1 their first consumer.
    LEVEL_OF_DETAIL: ClassVar[bool] = False
    UNITS: ClassVar = MappingProxyType({})  # {own field: unit}
    SIGNS: ClassVar = MappingProxyType({})  # {own field: its sign convention}

    def errors(self):
        """Why this declaration breaks the template (empty: it keeps it)."""
        out = []
        if not _is_id(self.law_id):
            out.append("its law_id is [namespace.]name@major")
        interface = type(self).interface
        if not _is_id(interface, namespaced=True):
            out.append("its type declares a namespaced interface ID with its major")
        elif interface in INTERFACES:
            if not isinstance(self, INTERFACES[interface]):
                out.append(
                    f"{interface} is not a cells interface of its type (cells' law interfaces: "
                    + ", ".join(INTERFACES)
                    + ")"
                )
        elif interface.split(".", 1)[0] == NAMESPACE and interface not in FAMILY_INTERFACES:
            out.append(
                f"{interface} is not a cells interface of its type: neither one of "
                + ", ".join(INTERFACES)
                + " nor one a family declares in the model table"
            )
        if not _is_id(self.host):
            out.append("its host is the ID of the kind or model that runs it")
        out += source_errors(self.provenance, self.source, self.test, "law")
        reserved = [
            name
            for name in ("represents", "preserves", "supports", "qualified")
            if getattr(self, name) is not None
        ]
        if reserved and not type(self).LEVEL_OF_DETAIL:
            out.append(
                f"{', '.join(reserved)}: B8's fields are reserved until their first consumer (D175)"
            )
        return out


def _work(work):
    return (
        isinstance(work, CitedWork)
        and isinstance(work.authors, tuple)
        and bool(work.authors)
        and all(map(_named, work.authors))
        and isinstance(work.year, int)
        and not isinstance(work.year, bool)
        and _named(work.title)
        and (_named(work.doi) or _named(work.url))
        and all(v is None or _named(v) for v in (work.doi, work.url))
    )


def _cited(source):
    return (
        isinstance(source, Citation)
        and all(_named(v) for v in (source.source, source.place, source.licence))
        and isinstance(source.departures, tuple)
        and all(_named(d) for d in source.departures)
        and isinstance(source.works, tuple)
        and all(map(_work, source.works))
    )


def source_errors(provenance, source, test, what):
    """Why a declaration's provenance, source and test break the template (empty: they keep it).
    Shared with the operator template of a family's own operators (registry/operators.py), so a
    piece states what it rests on in one form whatever it is."""
    out = []
    if provenance not in PROVENANCES:
        out.append(f"its provenance is one of {', '.join(PROVENANCES)}")
    elif provenance == "cited" and not _cited(source):
        out.append(
            f"a cited {what} gives its source as a Citation (source, place, licence, a tuple of "
            "departures and a tuple of works, each a CitedWork with its authors, year, title and "
            "a DOI or URL)"
        )
    elif provenance == "calibrated" and source is None:
        out.append(f"a calibrated {what} gives its data and method as its source")
    if test is not None and not _named(test):
        out.append("its test is a test ID")
    return out


def _callables(law, *names):
    return [f"its {name} is callable" for name in names if not callable(getattr(law, name))]


STEP_TERMS = ("stage_term", "material_term", "charge_bound", "material_bound")


def _forms_errors(law):
    return [] if law.forms in (None, "base") else ['its forms are "base", or None']


def _cycle_errors(cycle):
    """A cycle law's general form checked by its own errors(), then its change rows' form
    (duck-typed, module docstring): a form that breaks its own contract is not asked for rows."""
    if cycle is None:
        return []
    check = getattr(cycle, "errors", None)
    if not callable(check):
        return ["its cycle is a form with its own errors() and changes(), or None"]
    problems = check()
    if not isinstance(problems, list) or not all(map(_named, problems)):
        return ["its cycle's errors() returns a list of reasons"]
    if problems:
        return [f"its cycle: {problem}" for problem in problems]
    return _form_changes(cycle)[1]


CHANGE_ROW = ("role", "per_cycle", "mode")  # A general form's change row's keys (cycle_changes).


def _count(value):
    """A declared count per cycle: an integer, or a population parameter's name (FR-4's form)."""
    return _named(value) or (isinstance(value, int) and not isinstance(value, bool))


def _form_changes(cycle):
    """(rows, reasons) of a general form's changes(): its rows, each {role, per_cycle, mode} in
    that key order, with the reasons they break the row form (rows () where they do)."""
    changes = getattr(cycle, "changes", None)
    if not callable(changes):
        return (), ["its cycle is a form with its own changes()"]
    rows = changes()
    if not isinstance(rows, tuple) or not all(
        isinstance(row, Mapping)
        and set(row) == set(CHANGE_ROW)
        and _named(row["role"])
        and _count(row["per_cycle"])
        and _named(row["mode"])
        for row in rows
    ):
        return (), [
            "its cycle's changes() returns a tuple of {role, per_cycle, mode} rows: a named role "
            "and mode, and a count that is an integer or a parameter's name"
        ]
    return tuple({key: row[key] for key in CHANGE_ROW} for row in rows), []


def cycle_changes(law):
    """A cycle law's declared change rows: its general form's changes() where the form is set,
    ({role, per_cycle, mode}, ...), each mode's rows, the role as "role@end"; otherwise its moves,
    ({role, per_cycle}, ...). Each is inward-positive per forward cycle, and its count is as
    declared, an integer or a population parameter's name negated by a leading "-": nothing is
    resolved. The one source for the manifest (registry/declarations.py) and §5.2's single-mode
    admission, which resolves named counts itself. Raises where a form's rows break the row form,
    as the law's registration refuses it."""
    if not isinstance(law, CycleLaw):
        raise TypeError(f"cycle_changes reads a CycleLaw, not {type(law).__name__}")
    if law.cycle is None:
        return tuple(dict(role=role, per_cycle=count) for role, count in law.moves)
    rows, problems = _form_changes(law.cycle)
    if problems:
        raise ValueError(f"Law {law.law_id}: {'; '.join(problems)}")
    return rows


def _named_or_none(law, *names):
    return [
        f"its {name} is named, or None"
        for name in names
        if getattr(law, name) is not None and not _named(getattr(law, name))
    ]


@dataclass(frozen=True)
class ChannelLaw(Law):
    """A channel law (docs/INNER_MODEL_V4_DESIGN.md §7.1): gates relax by the exponential stage
    update; leaks have none. A host's codes are distinct. Code 99 is reserved for test plants (the
    lead, 19 November 2026): no registered law takes it, so a planted law never meets one that
    registers later."""

    code: int
    gates: tuple[str, ...]
    permeant: tuple[tuple[str, int, float], ...]  # (species, valence, relative permeability)
    voltage_domain_V: tuple[float, float]
    rk4_step_s: float | None  # The reference RK4 step bound; None for gate-free laws.
    kinetics: Callable | None = None  # (voltage, *, xp) -> (target, tau), [..., gates, n].
    opening: Callable | None = None  # (gates, *, xp) -> [..., n]; None: always open.
    stage_term: str = "constant_field_slope"  # Today's membrane_rate term at the actual opening.
    reads: tuple = ()  # Stage reads (B4): none for today's laws.
    loop_term: object = None

    interface: ClassVar[str] = CHANNEL_LAW
    UNITS: ClassVar = MappingProxyType({"voltage_domain_V": "V", "rk4_step_s": "s"})

    @property
    def gated(self):
        return bool(self.gates)

    def errors(self):
        out = super().errors()
        if not (isinstance(self.code, int) and not isinstance(self.code, bool) and self.code >= 0):
            out.append("its code is a non-negative integer")
        gates = self.gates
        if not (isinstance(gates, tuple) and all(map(_named, gates))) or len(set(gates)) < len(
            gates
        ):
            out.append("its gates are a tuple of distinct names")
        permeant = self.permeant
        if not (
            isinstance(permeant, tuple)
            and permeant
            and all(
                isinstance(p, tuple)
                and len(p) == 3
                and _named(p[0])
                and isinstance(p[1], int)
                and not isinstance(p[1], bool)
                and _number(p[2])
                for p in permeant
            )
        ):
            out.append("its permeant ions are (species, valence, relative permeability) tuples")
        domain = self.voltage_domain_V
        if not (
            isinstance(domain, tuple)
            and len(domain) == 2
            and all(map(_number, domain))
            and domain[0] < domain[1]
        ):
            out.append("its voltage domain is a (low, high) interval")
        if self.rk4_step_s is not None and not (_number(self.rk4_step_s) and self.rk4_step_s > 0):
            out.append("its RK4 step bound is positive, or None")
        kernels = (self.kinetics, self.opening)
        if self.gated and not all(map(callable, kernels)):
            out.append("a gated law gives its kinetics and opening")
        if not self.gated and any(k is not None for k in kernels):
            out.append("a gate-free law gives no kinetics or opening")
        if not _named(self.stage_term) or not isinstance(self.reads, tuple):
            out.append("its stage term is named and its reads are a tuple")
        return out


@dataclass(frozen=True)
class CycleLaw(Law):
    """A membrane cycle law: the rows it moves per cycle by role, its fuel kinds, its kernel and
    its domain. moves: ((role, count), ...), inward-positive per cycle; a count is an integer, or
    the name of the population's parameter that holds it, negated by a leading "-" (FR-4's form).
    Seam A's general form (`cycle`, a CycleForm) carries the law where it is set: its own errors()
    must hold and its changes() gives its change rows (cycle_changes), so `moves` may be empty and
    kinetics and domain_valid None (the kinds owner's first gap). A law without a form keeps
    version 1's checks: moves given, both kernels callable. `electroneutral`: a cycle of it moves no
    charge from one end to the other whatever species a population binds, so its rate may have no
    voltage term; its host refuses by name a population that moves charge."""

    moves: tuple[tuple[str, object], ...] = ()
    fuel_kinds: tuple[str, ...] = ()
    kinetics: Callable | None = None
    domain_valid: Callable | None = None
    reads: tuple = ()  # Stage reads, such as rapid_proton_buffer@1's free h.
    stage_term: str | None = None  # Its charge slope in the stage rule, where its host takes one.
    loop_term: str | None = None
    # Its other step terms (module docstring), each its kernel's name or None.
    material_term: str | None = None  # Its material slope per stage.
    charge_bound: str | None = None  # Its definition-time bound on a charged row.
    material_bound: str | None = None  # Its definition-time bound on a neutral row.
    forms: str | None = None  # "base": its moves are in base forms (CORE_SEAMS §5.2), or None.
    cycle: object = None  # Its general form: seam A's CycleForm, or None (module docstring).
    electroneutral: bool = False  # Its host refuses a population that moves charge (docstring).

    interface: ClassVar[str] = CYCLE_LAW
    SIGNS: ClassVar = MappingProxyType({"moves": "inward-positive, per forward cycle"})

    def errors(self):
        out = super().errors()
        formed = self.cycle is not None  # The form carries the law (class docstring).
        if formed:
            out += [
                f"its {name} is callable, or None"
                for name in ("kinetics", "domain_valid")
                if getattr(self, name) is not None and not callable(getattr(self, name))
            ]
        else:
            out += _callables(self, "kinetics", "domain_valid")
        moves = self.moves
        if not (
            isinstance(moves, tuple)
            and (moves or formed)
            and all(
                isinstance(m, tuple) and len(m) == 2 and _named(m[0]) and _count(m[1])
                for m in moves
            )
        ):
            out.append("its moves are (role, count) pairs")
        if not (isinstance(self.fuel_kinds, tuple) and all(map(_named, self.fuel_kinds))):
            out.append("its fuel kinds are a tuple of IDs")
        if not isinstance(self.reads, tuple):
            out.append("its reads are a tuple")
        if not isinstance(self.electroneutral, bool) or (self.electroneutral and not formed):
            out.append("its electroneutral is true or false, and true only with a general form")
        out += _named_or_none(self, *STEP_TERMS, "loop_term") + _forms_errors(self)
        return out + _cycle_errors(self.cycle)


PumpLaw = CycleLaw  # @3's name for its pump laws' declarations: the same type (§8.1).


@dataclass(frozen=True)
class RouteLaw(Law):
    """A passive route law: the entities its routes sit on, what it is (its basis), and its step
    terms (module docstring)."""

    hosts: tuple[str, ...]
    basis: str
    stage_term: str | None = None  # Its charge slope in the stage rule.
    material_term: str | None = None  # Its material slope per stage.
    charge_bound: str | None = None  # Its definition-time bound on a charged row.
    material_bound: str | None = None  # Its definition-time bound on a neutral row.
    forms: str | None = None  # "base": it moves base forms (CORE_SEAMS §5.2), or None.
    # The stage reads it reads its rows through, as a cycle law's reads: () for every route law but
    # one that reads a closure's free forms (MT-1b's leak @2 reads rapid_binding@1; host side).
    reads: tuple = ()

    interface: ClassVar[str] = ROUTE_LAW

    def errors(self):
        out = super().errors()
        if not (isinstance(self.hosts, tuple) and self.hosts and all(map(_named, self.hosts))):
            out.append("its hosts name the entities its routes sit on")
        if not _named(self.basis):
            out.append("its basis says what it is")
        if not (isinstance(self.reads, tuple) and all(map(_named, self.reads))):
            out.append("its reads are a tuple of stage-read IDs")
        return out + _named_or_none(self, *STEP_TERMS) + _forms_errors(self)


@dataclass(frozen=True)
class BindingLaw(Law):
    """A rapid binding closure (seam C, docs/CORE_SEAMS_DESIGN.md §5): the ligands it binds, by
    role, and its closure kernel (free forms from totals). Seam C adds its forms and envelope."""

    ligands: tuple[str, ...]
    closure: Callable
    domain_valid: Callable | None = None
    # The general closure's (module docstring), each None in version 1.
    forms: str | None = None  # "registry": its binders' forms are the species registry's.
    free_energy: Callable | None = None  # G*, its free-energy term.
    envelope: Callable | None = None  # The first-order lag envelope of its binding network.
    free_amounts: Callable | None = None  # The free forms from the totals (P1's predictor's).

    interface: ClassVar[str] = BINDING_LAW

    def errors(self):
        out = super().errors() + _callables(self, "closure")
        if not (
            isinstance(self.ligands, tuple) and self.ligands and all(map(_named, self.ligands))
        ):
            out.append("its ligands are a tuple of roles")
        for name in ("domain_valid", "free_energy", "envelope", "free_amounts"):
            if getattr(self, name) is not None and not callable(getattr(self, name)):
                out.append(f"its {name} is callable, or None")
        if self.forms not in (None, "registry"):
            out.append('its forms are "registry", or None')
        return out


@dataclass(frozen=True)
class JunctionLaw(Law):
    """A junction conductance law; a gated one carries junction_gate state.

    FR-30 (docs/JUNCTION_TWO_RELAXATION_DESIGN.md §5; the lead's ruling of 20 November 2026, D191:
    two defaulted fields, not a new interface version): `gate_count` gates in series, each with
    today's kinetics, and `conductance(gates)`, the junction's relative conductance from them. Their
    defaults, 1 and None, keep every one-gate law as it was: its one gate's state is its
    conductance."""

    gated: bool
    kinetics: Callable  # (voltage, parameters, *, xp) -> junction_gate.Rates
    rhs: Callable
    domain_valid: Callable
    max_abs_voltage_V: float
    gate_count: int = 1
    conductance: Callable | None = None  # (gates, *, xp) -> relative conductance; None: one gate

    interface: ClassVar[str] = JUNCTION_LAW
    UNITS: ClassVar = MappingProxyType({"max_abs_voltage_V": "V"})

    def errors(self):
        out = super().errors() + _callables(self, "kinetics", "rhs", "domain_valid")
        if not isinstance(self.gated, bool):
            out.append("its gated flag is a bool")
        if not (_number(self.max_abs_voltage_V) and self.max_abs_voltage_V > 0):
            out.append("its voltage bound is positive")
        if isinstance(self.gate_count, bool) or not (
            isinstance(self.gate_count, int) and self.gate_count >= 1
        ):
            out.append("its gate count is a positive integer")
        elif self.conductance is None and self.gate_count > 1:
            out.append("a law of several gates declares its conductance")
        if self.conductance is not None and not callable(self.conductance):
            out.append("its conductance is a callable, or None for one gate")
        return out


INTERFACES = MappingProxyType(
    {
        CHANNEL_LAW: ChannelLaw,
        CYCLE_LAW: CycleLaw,
        ROUTE_LAW: RouteLaw,
        BINDING_LAW: BindingLaw,
        JUNCTION_LAW: JunctionLaw,
    }
)
# The cells interfaces the built-in families declare in the static model table (module docstring).
FAMILY_INTERFACES = frozenset(i for model in MODELS.values() for i in model.interfaces)


class LawRegistry:
    """Registered laws by namespaced ID (module docstring). A registered law that a definition
    does not declare changes nothing."""

    def __init__(self):
        self._laws = {}
        self._modules = {}  # {namespaced ID: the module that registered it}

    def register(self, law):
        """The one registration call: `law` checked against the template, then held under its
        namespaced ID, with the module that called this (its declaring module, for the
        declarations manifest). Returns the law."""
        return self._register(law, sys._getframe(1).f_globals.get("__name__"))

    def _register(self, law, module):
        """register, with `module` as the law's declaring module (the loader's form for an inert
        law module, which declares its LAW and registers nothing itself)."""
        if not isinstance(law, Law):
            raise ValueError(f"A law's declaration is built on the template (Law), not {law!r}")
        problems = law.errors()
        if problems:
            raise ValueError(f"Law {law.law_id!r}: " + "; ".join(problems))
        key = qualified(law.law_id)
        known = self._laws.get(key)
        if known is law:
            return law
        if known is not None:
            raise ValueError(f"Law {key} is already registered")
        if self is not BUILTIN and key.split(".", 1)[0] == NAMESPACE:
            _load_builtins()
            if BUILTIN._laws.get(key) is not law:
                raise ValueError(
                    f"Law {key} is in the cells namespace: another registry holds a cells law "
                    "only as BUILTIN's own declaration (one object per cells ID)"
                )
        if isinstance(law, ChannelLaw):
            host = qualified(law.host)
            for other_key, other in self._laws.items():
                if (
                    isinstance(other, ChannelLaw)
                    and qualified(other.host) == host
                    and other.code == law.code
                ):
                    raise ValueError(
                        f"Law {key}'s code {law.code} is {other_key}'s (a host's channel codes "
                        "are distinct)"
                    )
        self._laws[key] = law
        self._modules[key] = module
        return law

    def module(self, law_id):
        """The module that registered a law (its declaring module), or None."""
        return self._modules.get(qualified(law_id))

    def lookup(self, law_id):
        key = qualified(law_id)
        if key not in self._laws:
            raise KeyError(f"No registered law {key}")
        return self._laws[key]

    def __contains__(self, law_id):
        return _named(law_id) and qualified(law_id) in self._laws

    def laws(self, interface, host):
        """The laws of `interface` that `host` runs, in canonical (sorted namespaced ID) order:
        how the inner model and each kind find their laws."""
        host = qualified(host)
        return tuple(
            law
            for _, law in sorted(self._laws.items())
            if type(law).interface == interface and qualified(law.host) == host
        )

    def extended(self, *laws):
        """A new registry holding this one's laws (BUILTIN's with its built-ins loaded), then
        `laws`; this one is unchanged."""
        if self is BUILTIN:
            _load_builtins()
        caller = sys._getframe(1).f_globals.get("__name__")
        out = LawRegistry()
        for law in self._laws.values():
            out.register(law)
        out._modules.update(self._modules)  # Each copied law keeps its declaring module.
        for law in laws:
            new = qualified(law.law_id) not in out._laws
            out.register(law)
            if new:
                out._modules[qualified(law.law_id)] = caller
        return out


BUILTIN = LawRegistry()
_ACTIVE = ContextVar("cells_law_registry", default=None)
# The built-in laws' homes, imported by name, so the core imports no law module: every model's
# `law_homes` in the static model table, in its order (registry/model_table.py). For @3 they are its
# own declarations and the kinds' package, whose modules declare their laws
# (docs/INNER_MODEL_V4_DESIGN.md §7.4 (k)), until each law moves to its own module under laws/
# (docs/CORE_SEAMS_DESIGN.md §8.2).
BUILTIN_PACKAGES = tuple(home for model in MODELS.values() for home in model.law_homes)
_builtins_loaded = False


def _load_builtins():
    """Import the built-in laws' homes once, by name. A home that calls the registration call an
    outside package uses has registered its laws by then. An inert law module (docs/
    CORE_SEAMS_DESIGN.md §8.2; the lead's ruling R1, 18 November 2026) declares its one law as a
    module-level `LAW` and registers nothing at import; it is registered here, with that module
    as its declarer, so importing a law module, as the shared kernel modules do, changes no
    registry."""
    global _builtins_loaded
    if not _builtins_loaded:
        for name in BUILTIN_PACKAGES:
            law = getattr(importlib.import_module(name), "LAW", None)
            if isinstance(law, Law) and BUILTIN._laws.get(qualified(law.law_id)) is not law:
                BUILTIN._register(law, name)
        _builtins_loaded = True


def hosted_laws(interface, host):
    """The active registry's laws of `interface` that `host` runs, in canonical (sorted namespaced
    ID) order: how a kind or the inner model finds its laws (§8.3), on the surface for kinds."""
    return active().laws(interface, host)


def active():
    """The law registry of the model build in progress: BUILTIN, with the built-in laws loaded,
    unless scope() says otherwise."""
    registry = _ACTIVE.get()
    if registry is not None:
        return registry
    _load_builtins()
    return BUILTIN


@contextmanager
def scope(registry):
    """Build (parse, bind, run) with `registry` as the law lookup, restored on exit."""
    token = _ACTIVE.set(registry)
    try:
        yield registry
    finally:
        _ACTIVE.reset(token)
