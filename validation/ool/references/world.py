"""The registered world format (``ool_references.world@1``) and the engine's declared conventions.

A world file is the complete specification the engine side reads to build its own world. Its
vocabulary follows the OL1 family's declared format (places, a ``locus`` per step,
``standard_mu_RT`` per phase kind, ``standard_concentration_mM``, ``volume_L``,
``forward_rate_per_s``). Beside every float it holds the exact value (rationals written as
strings), so the references decide identities exactly while the engine works in float64.

- **Phases:** ``membrane`` (condensed) and dilute phases (``pool``; ``lumen`` from OL2) with a
  constant ``volume_L``.
- **Species:** integer moieties, and a standard potential per phase kind, written as
  ``exp_minus`` = exp(-mu0/k_BT) (exact) and ``float`` = mu0/k_BT. ``bilayer`` is at mole
  fraction 1; ``solution`` is at c0.
- **Places:** (species, phase) pairs, named ``species@phase``. A dilute place is finite (a count
  in the state) or held (a fixed concentration ``held_mM``). The state is the finite places'
  counts, in the declared order.
- **Steps:** reactants and products over places, the ``locus``, the forward rate constant (per
  second: every activity is dimensionless) and the transition-state factor's catalysts (membrane
  places), each with its exact enhancement beta = exp(ddG/k_BT) - 1 and the float ddG.
- **Regular mixing:** chi per pair of membrane species, symmetric, zero diagonal.

The engine's conventions are not part of a world. They are the engine's declarations, read from
its saved records, from the closed menu ``CONVENTION_MENU``. Anything outside it is refused.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

from .common import RecordFormatError
from .exact import as_fraction, log_fraction

WORLD_FORMAT = "ool_references.world@1"
MEMBRANE = "membrane"
DILUTE_PHASES = ("pool", "lumen")
MAX_MOLECULARITY = 3

# ---------------------------------------------------------------------------- conventions

CONVENTION_MENU = {
    "free_energy_form": ("discrete",),
    "condensed_measure": ("multinomial", "multinomial_less_one"),
    "membrane_kinetics": ("count_on_m",),
    "lumen_volume": ("declared",),
    "empty_catalyst_phase": ("uncatalysed",),
    "last_molecule": ("kept", "reversible", "extinct"),
}
"""The closed menu of declared conventions (the OL1 family's FORMAT draft, 17 November 2026).

``free_energy_form = continuum`` (Stirling) is not admissible in an exact event kernel; a record
that declares it is refused, as the family refuses it. ``last_molecule = reversible`` pairs only
with ``multinomial`` and ``extinct`` only with ``multinomial_less_one``."""

REFUSED_TOKENS = {"free_energy_form": ("continuum",)}


@dataclass(frozen=True)
class Conventions:
    """The engine's declared conventions for one world (one token per menu entry)."""

    condensed_measure: str
    last_molecule: str
    free_energy_form: str = "discrete"
    membrane_kinetics: str = "count_on_m"
    lumen_volume: str = "declared"
    empty_catalyst_phase: str = "uncatalysed"

    def __post_init__(self):
        for key, allowed in CONVENTION_MENU.items():
            value = getattr(self, key)
            if value in REFUSED_TOKENS.get(key, ()):
                raise RecordFormatError(f"convention {key}={value!r} is refused by the exact kernel")
            if value not in allowed:
                raise RecordFormatError(f"convention {key}={value!r} is not in the menu {allowed}")
        if self.last_molecule == "reversible" and self.condensed_measure != "multinomial":
            raise RecordFormatError("last_molecule='reversible' pairs only with condensed_measure='multinomial'")
        if self.last_molecule == "extinct" and self.condensed_measure != "multinomial_less_one":
            raise RecordFormatError("last_molecule='extinct' pairs only with condensed_measure='multinomial_less_one'")

    @property
    def c(self) -> int:
        """The measure's offset: 0 for ``multinomial``, 1 for ``multinomial_less_one``."""
        return 0 if self.condensed_measure == "multinomial" else 1

    @staticmethod
    def from_declared(declared: dict | None) -> "Conventions":
        """Read the declared tokens; a missing or unknown token is refused (status 2)."""
        if not isinstance(declared, dict):
            raise RecordFormatError("the records declare no conventions; every token in "
                                    f"{sorted(CONVENTION_MENU)} must be declared")
        missing = [k for k in CONVENTION_MENU if k not in declared]
        if missing:
            raise RecordFormatError(f"the records do not declare the conventions {missing}; there is no default")
        return Conventions(**{k: declared[k] for k in CONVENTION_MENU})

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in CONVENTION_MENU}


def every_convention() -> list[Conventions]:
    """Every admissible token combination: (multinomial, kept), (multinomial, reversible),
    (multinomial_less_one, kept), (multinomial_less_one, extinct)."""
    out = []
    for measure in CONVENTION_MENU["condensed_measure"]:
        for last in CONVENTION_MENU["last_molecule"]:
            try:
                out.append(Conventions(condensed_measure=measure, last_molecule=last))
            except RecordFormatError:
                continue
    return out


# ---------------------------------------------------------------------------- the world

@dataclass(frozen=True)
class Exact:
    """A registered quantity: its exact value and the float the engine reads."""

    exact: Fraction
    float: float


@dataclass(frozen=True)
class Place:
    name: str            # "species@phase"
    species: str
    phase: str
    exp_minus_mu0: Fraction  # exp(-mu0) for this phase kind
    mu0_kT: float
    held_mM: Exact | None = None

    @property
    def held(self) -> bool:
        return self.held_mM is not None

    @property
    def membrane(self) -> bool:
        return self.phase == MEMBRANE


@dataclass(frozen=True)
class Catalyst:
    place: str
    beta: Fraction
    ddG_kT: float


@dataclass(frozen=True)
class Step:
    name: str
    locus: str
    reactants: dict
    products: dict
    rate: Exact
    catalysts: tuple = ()


@dataclass(frozen=True)
class World:
    name: str
    c0_mM: Exact
    avogadro: Exact
    volumes_L: dict          # dilute phase -> Exact
    places: dict             # name -> Place, in declared order
    moieties: dict           # species -> {moiety: int}
    chi: dict                # (species_a, species_b) -> Fraction, membrane species
    steps: tuple
    initial_state: dict | None = None
    raw: dict = field(compare=False, repr=False, default=None)

    # -- the state ---------------------------------------------------------------------
    @property
    def finite(self) -> tuple:
        """The finite places, in declared order: the state's coordinates."""
        return tuple(p for p in self.places.values() if not p.held)

    @property
    def dim(self) -> int:
        return len(self.finite)

    def index(self, place: str) -> int:
        return [p.name for p in self.finite].index(place)

    def membrane_mask(self) -> tuple:
        return tuple(p.membrane for p in self.finite)

    def X(self, phase: str) -> Fraction:
        """X_phase = N_A V c0, the molecules at standard concentration in the phase (exact)."""
        return self.avogadro.exact * self.volumes_L[phase].exact * self.c0_mM.exact / 1000

    def state_from(self, counts: dict) -> tuple:
        return tuple(int(counts.get(p.name, 0)) for p in self.finite)

    # -- the steps ---------------------------------------------------------------------
    def step(self, name: str) -> Step:
        for st in self.steps:
            if st.name == name:
                return st
        raise KeyError(name)

    def nu(self, st: Step) -> tuple:
        """The net change of the finite places' counts."""
        out = [0] * self.dim
        for side, sign in ((st.reactants, -1), (st.products, 1)):
            for p, c in side.items():
                if not self.places[p].held:
                    out[self.index(p)] += sign * c
        return tuple(out)

    def alpha(self, st: Step) -> tuple:
        out = [0] * self.dim
        for p, c in st.reactants.items():
            if not self.places[p].held:
                out[self.index(p)] += c
        return tuple(out)

    def beta_finite(self, st: Step) -> tuple:
        out = [0] * self.dim
        for p, c in st.products.items():
            if not self.places[p].held:
                out[self.index(p)] += c
        return tuple(out)

    def nu_held(self, st: Step) -> dict:
        out: dict = {}
        for side, sign in ((st.reactants, -1), (st.products, 1)):
            for p, c in side.items():
                if self.places[p].held:
                    out[p] = out.get(p, 0) + sign * c
        return {k: v for k, v in out.items() if v}

    def moiety_names(self) -> list:
        names = set()
        for m in self.moieties.values():
            names.update(m)
        return sorted(names)

    def moiety_matrix(self) -> list:
        """Integer rows w_q over the finite places."""
        return [[int(self.moieties[p.species].get(q, 0)) for p in self.finite] for q in self.moiety_names()]

    def chi_matrix(self) -> list:
        """chi over the finite membrane places (zero elsewhere), symmetric."""
        out = [[Fraction(0)] * self.dim for _ in range(self.dim)]
        for i, p in enumerate(self.finite):
            for j, q in enumerate(self.finite):
                if p.membrane and q.membrane:
                    key = (p.species, q.species) if (p.species, q.species) in self.chi else (q.species, p.species)
                    out[i][j] = self.chi.get(key, Fraction(0))
        return out


def _exact(entry, where: str) -> Exact:
    if not isinstance(entry, dict) or "exact" not in entry or "float" not in entry:
        raise RecordFormatError(f"{where}: an exact quantity needs 'exact' and 'float'")
    ex = as_fraction(entry["exact"])
    fl = float(entry["float"])
    if not math.isclose(float(ex), fl, rel_tol=4 * 2.0 ** -52, abs_tol=0.0):
        raise RecordFormatError(f"{where}: float {fl!r} is not the exact value {ex} to rounding")
    return Exact(ex, fl)


def _potential(entry, where: str) -> tuple[Fraction, float]:
    em = as_fraction(entry["exp_minus"])
    if em <= 0:
        raise RecordFormatError(f"{where}: exp_minus must be positive")
    mu = float(entry["float"])
    if abs(mu + log_fraction(em)) > 4 * 2.0 ** -52 * max(1.0, abs(mu)):
        raise RecordFormatError(f"{where}: mu0/k_BT {mu!r} is not -ln({em}) to rounding")
    return em, mu


def parse_world(doc: dict) -> World:
    """Parse and check a registered world; anything inconsistent is refused."""
    if doc.get("format") != WORLD_FORMAT:
        raise RecordFormatError(f"world format {doc.get('format')!r}, {WORLD_FORMAT!r} expected")
    name = str(doc["id"])
    volumes = {}
    for ph, spec in doc["phases"].items():
        if ph == MEMBRANE:
            if spec.get("kind") != "condensed":
                raise RecordFormatError(f"{name}: the membrane is condensed")
        elif ph in DILUTE_PHASES:
            if spec.get("kind") != "dilute":
                raise RecordFormatError(f"{name}: phase {ph} is dilute")
            volumes[ph] = _exact(spec["volume_L"], f"{name}.{ph}.volume_L")
        else:
            raise RecordFormatError(f"{name}: unknown phase {ph!r}")
    potentials, moieties = {}, {}
    for entry in doc["species"]:
        sid = entry["id"]
        moieties[sid] = {str(k): int(v) for k, v in (entry.get("moieties") or {sid: 1}).items()}
        potentials[sid] = {kind: _potential(v, f"{name}.{sid}.{kind}") for kind, v in entry["standard_mu_RT"].items()}
    places = {}
    for entry in doc["places"]:
        sid, ph = entry["species"], entry["phase"]
        pname = f"{sid}@{ph}"
        if pname in places:
            raise RecordFormatError(f"{name}: place {pname} repeated")
        if sid not in potentials or ph not in doc["phases"]:
            raise RecordFormatError(f"{name}: place {pname} names an unknown species or phase")
        kind = "bilayer" if ph == MEMBRANE else "solution"
        if kind not in potentials[sid]:
            raise RecordFormatError(f"{name}: species {sid} has no {kind} potential for place {pname}")
        em, mu = potentials[sid][kind]
        held = None
        if "held_mM" in entry:
            if ph == MEMBRANE:
                raise RecordFormatError(f"{name}: a membrane place cannot be held")
            held = _exact(entry["held_mM"], f"{name}.{pname}.held_mM")
            if held.exact <= 0:
                raise RecordFormatError(f"{name}: held concentration of {pname} must be positive")
        places[pname] = Place(pname, sid, ph, em, mu, held)
    chi = {}
    mem_species = {p.species for p in places.values() if p.membrane}
    for entry in doc.get("regular_mixing_chi", []):
        a, b = entry["pair"]
        if a == b:
            raise RecordFormatError(f"{name}: chi has a zero diagonal ({a}, {a} given)")
        if a not in mem_species or b not in mem_species:
            raise RecordFormatError(f"{name}: chi pair {a, b} names a species with no membrane place")
        if (a, b) in chi or (b, a) in chi:
            raise RecordFormatError(f"{name}: chi pair {a, b} given twice")
        chi[(a, b)] = as_fraction(entry["chi"])
    steps, seen = [], set()
    for entry in doc["steps"]:
        sid = entry["id"]
        if sid in seen:
            raise RecordFormatError(f"{name}: step {sid} repeated")
        seen.add(sid)
        cats = []
        for c in entry.get("transition_state_factor", []):
            beta = as_fraction(c["beta"])
            if beta <= -1:
                raise RecordFormatError(f"{name}: step {sid} catalyst {c['catalyst']} has beta <= -1")
            ddg = float(c["ddG_kT"])
            if abs(ddg - math.log1p(float(beta))) > 4 * 2.0 ** -52 * max(1.0, abs(ddg)):
                raise RecordFormatError(f"{name}: step {sid} ddG_kT {ddg!r} is not ln(1 + {beta})")
            if c["catalyst"] not in places or not places[c["catalyst"]].membrane:
                raise RecordFormatError(f"{name}: catalyst {c['catalyst']} is not a membrane place")
            cats.append(Catalyst(c["catalyst"], beta, ddg))
        for key in ("standard_delta_G_RT", "delta_G0_kT", "standard_free_energy"):
            if key in entry:
                raise RecordFormatError(f"{name}: step {sid} carries a standard free energy of its own ({key}); "
                                        "potentials come from the species table only")
        for side in ("reactants", "products"):
            for p, c in entry[side].items():
                if not isinstance(c, int) or isinstance(c, bool):
                    raise RecordFormatError(f"{name}: step {sid} has a non-integer coefficient {c!r} for {p}")
        st = Step(sid, entry["locus"], {str(k): int(v) for k, v in entry["reactants"].items()},
                  {str(k): int(v) for k, v in entry["products"].items()},
                  _exact(entry["forward_rate_per_s"], f"{name}.{sid}.forward_rate_per_s"), tuple(cats))
        steps.append(st)
    world = World(name, _exact(doc["standard_concentration_mM"], f"{name}.c0"),
                  _exact(doc["avogadro_per_mol"], f"{name}.avogadro"), volumes, places, moieties, chi,
                  tuple(steps), doc.get("initial_state"), doc)
    for st in world.steps:
        check_step(world, st)
    return world


def check_step(world: World, st: Step) -> None:
    """The parse-time rules (D152's, as the family states them): known places, positive integer
    coefficients, at most three reactant and three product molecules, every moiety conserved
    (held places counted), a change, and a locus that is the membrane whenever the step touches
    more than one phase. A violation is refused."""
    for side in (st.reactants, st.products):
        for p, c in side.items():
            if p not in world.places:
                raise RecordFormatError(f"{world.name}: step {st.name} names unknown place {p}")
            if not isinstance(c, int) or c <= 0:
                raise RecordFormatError(f"{world.name}: step {st.name} coefficient {c!r} for {p}")
    if sum(st.reactants.values()) > MAX_MOLECULARITY or sum(st.products.values()) > MAX_MOLECULARITY:
        raise RecordFormatError(f"{world.name}: step {st.name} has more than three molecules on a side")
    unbalanced = moiety_imbalance(world, st)
    if unbalanced:
        raise RecordFormatError(f"{world.name}: step {st.name} does not conserve moieties {unbalanced}")
    net = {}
    for side, sign in ((st.reactants, -1), (st.products, 1)):
        for p, c in side.items():
            net[p] = net.get(p, 0) + sign * c
    if not any(net.values()):
        raise RecordFormatError(f"{world.name}: step {st.name} changes nothing")
    phases = {world.places[p].phase for p in list(st.reactants) + list(st.products)}
    expected = MEMBRANE if len(phases) > 1 else next(iter(phases))
    if st.locus != expected:
        raise RecordFormatError(f"{world.name}: step {st.name} has locus {st.locus!r}; {expected!r} expected")
    if all(world.places[p].held for p in list(st.reactants) + list(st.products)):
        raise RecordFormatError(f"{world.name}: step {st.name} touches held places only")


def moiety_imbalance(world: World, st: Step) -> dict:
    out = {}
    for q in world.moiety_names():
        d = sum(c * world.moieties[world.places[p].species].get(q, 0) for p, c in st.products.items())
        d -= sum(c * world.moieties[world.places[p].species].get(q, 0) for p, c in st.reactants.items())
        if d:
            out[q] = d
    return out


def load_world(path) -> World:
    return parse_world(json.loads(Path(path).read_text()))
