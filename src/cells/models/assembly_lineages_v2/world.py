"""The world of version 2: units, conventions, species, phases and places, steps, F terms, founder.

A world (one record, with an id its runs name) holds everything two runs of it share. Every order
that carries meaning is a list, so the canonical JSON that names a world fixes it:

    {"units": {"time": "s", "temperature_K": T, "standard_concentration_mM": c0},
     "conventions": {...},                                    conventions.py: six named tokens
     "species": [{"id", "moieties", "standard_mu_RT", "catalogue", "evidence"}, ...],
     "phases": {"pool": {"volume_L": V, "species": [{"id": "A", "kind": "finite"},
                                                     {"id": "F", "kind": "held", "held_mM": c}]},
                "membrane": {"species": ["A", "B"]},
                "lumen": {"volume_L": V, "species": ["S"]}},
     "steps": [{"id", "reactants", "products", "phase" | "locus", "law", "forward_rate_per_s"}],
     "free_energy": [{"law": "cells.free_energy.ideal_mixing@1"}, {"law": "cells.free_energy.regular_mixing@1", ...}],
     "rate_factor": {"law": "cells.rate_factor.transition_state_factor@1", ...},        optional
     "founder": {"A@membrane": 10, ...},                      every finite place, explicitly
     "world_role": "probe",                                    optional (§0.2b rule 8)
     "sites": [{"site": "R", "complex": "XR"}, ...],           optional (FR-21; §0.2f; FR-46's face)
     "hazard": {"law": "cells.assembly_hazard.pore_nucleation@1", ...}}        optional (FR-31; pore_nucleation.py)

**Species** take D152's species form (SHARED_INVENTORY_REACTIONS_DESIGN §2.1): `moieties` (positive
integer counts, or null: the species is its own moiety), the identity (`catalogue`, `evidence`,
species_registry.parse_identity) and `standard_mu_RT`. Here the potential is given per phase kind,
`{"solution": μ°/RT at c0, "bilayer": μ°/RT at mole fraction 1}`; D152's single number is accepted
as
the solution potential. A species placed in a phase has that phase kind's potential. The world's
table is the one authority for standard potentials until the registry has them per phase (R7): no
step carries a ΔG° of its own.

**A lumen potential** (FR-48; D323): `"lumen": μ°/RT at c0 in the lumen`, an absolute value beside
the solution one, which it replaces at the species' lumen place alone. Undeclared, the lumen takes
the solution potential, as before. Δ = μ°_lumen − μ°_solution is then a reversible free-energy
difference across the shell, read by every step through the place's μ°; the shell law keeps all of
it on the exit (shell_permeation.py). Version 1 admits it in a prescribed shell only, on a species
with a lumen place and a solution potential (spec._lumen_potential_refusals).

**Phases.** The membrane (condensed) is required; the pool and the lumen (dilute, each with its
volume_L) are optional. A pool species is `finite` (a count in the state) or `held` (a concentration
held_mM: no count, and its exchanges book reservoir work). A place is a species in a phase,
`<species>@<phase>`; places are ordered pool, membrane, lumen, each in its declared order.

**Steps** (D152's rules): integer counts, at most 3 reactant and 3 product molecules, every
declared moiety conserved across places (held species counted), and a step that changes nothing
refused. A step declares either `phase` (all its places in that phase; reactants and products by
species, D152's sides, `phase` in place of D152's `sites`; its locus is that phase) or `locus` (its
places as `<species>@<phase>`). A step whose places span phases (a join, a leave, permeation
between pool and lumen, an interfacial reaction) has the membrane as its locus; a step within one
phase has that phase. Held places take part only as pool places.

**Sites** (FR-21; §0.2f, the lead's rulings of 20 November 2026, D244 and D246). A pair declares a
membrane species as a binding site and another as its complex, the site with one bound molecule.
In a world with a geometry, rule 3 admits one interfacial step for a declared pair, exactly
X@pool + site@membrane -> complex@membrane under cells.reaction.stochastic_mass_action@1 with count_on_m
(spec._geometry_refusals); an undeclared pair stays refused. On a bilayer both take area.

**A pair's face** (FR-46; D323): `"face": "outer"` (the default, never written) or `"inner"`. An
inner pair binds from the lumen, X@lumen + site@membrane -> complex@membrane, in a prescribed shell
only (version 1). One face per complex: the faces propagate by ligand moiety over every wall state,
and a wall that joins the two faces is a carrier, refused by name (spec._face_rule).
"""

import math
from dataclasses import dataclass
from types import MappingProxyType

from cells.definitions.spec_values import identifier
from cells.definitions.specs import ConfigError, bounded_integer, finite_number, require_fields
from cells.models.assembly_lineages_v2 import conventions as conventions_rules
from cells.registry import species_registry

POOL, MEMBRANE, LUMEN = "pool", "membrane", "lumen"
PHASES = (POOL, MEMBRANE, LUMEN)  # The place order, and the phase index of each.
PHASE_INDEX = MappingProxyType({p: i for i, p in enumerate(PHASES)})
DILUTE = (POOL, LUMEN)
KIND_OF = MappingProxyType({POOL: "solution", LUMEN: "solution", MEMBRANE: "bilayer"})
TIME_UNIT = "s"
MAX_SIDE = 3  # D152: molecules on each side of a step.
WORLD_KEYS = {
    "units",
    "conventions",
    "species",
    "phases",
    "steps",
    "free_energy",
    "rate_factor",
    "founder",
    "world_role",
    "geometry",
    "division",
    "population",
    "sites",
    "hazard",
}
WORLD_REQUIRED = WORLD_KEYS - {
    "rate_factor", "world_role", "geometry", "division", "population", "sites", "hazard",
}  # fmt: skip
ROLES = ("probe",)  # §0.2b rule 8: a world declared to be probed (rate tables), never a lineage.
AVOGADRO = 6.02214076e23  # mol⁻¹, exact (SI 2019).


@dataclass(frozen=True)
class Units:
    time: str  # "s".
    temperature_K: float
    standard_concentration_mM: float  # c0.

    @property
    def kT_J(self):
        """k_BT in joules: the physical value of the energy unit (k_B exact, SI 2019)."""
        return 1.380649e-23 * self.temperature_K


@dataclass(frozen=True)
class Species:
    id: str
    moieties: tuple | None  # ((moiety, count), ...), or None: the species is its own moiety.
    mu_solution: float | None  # μ°/RT at c0 in solution (pool, lumen).
    mu_bilayer: float | None  # μ°/RT at mole fraction 1 in the membrane.
    catalogue: tuple | None
    evidence: str | None
    mu_lumen: float | None = None  # FR-48: μ°/RT at c0 in the lumen, or None: the solution's.

    def mu(self, phase):
        if phase == LUMEN and self.mu_lumen is not None:
            return self.mu_lumen
        return self.mu_bilayer if KIND_OF[phase] == "bilayer" else self.mu_solution

    def moiety_counts(self):
        return {self.id: 1} if self.moieties is None else dict(self.moieties)


@dataclass(frozen=True)
class Place:
    species: str
    phase: str
    held_mM: float | None = None  # A held pool species' concentration.

    @property
    def name(self):
        return f"{self.species}@{self.phase}"

    @property
    def held(self):
        return self.held_mM is not None


@dataclass(frozen=True)
class Step:
    id: str
    form: str  # "phase" (declared by phase, D152's sides) or "locus" (declared by places).
    reactants: tuple  # ((place name, count), ...), in place order.
    products: tuple
    locus: str
    law: str
    forward_rate_per_s: float  # The step's rate constant k, in its law's unit (rate_key).
    rate_key: str = "forward_rate_per_s"  # OL2's geometric laws name theirs (§0.2d item 2).
    rate_provenance: str | None = None  # OL2: their rate constants carry it (§0.2e rule 7).


@dataclass(frozen=True)
class World:
    units: Units
    conventions: conventions_rules.Conventions
    species: tuple  # Species, in declared order.
    volumes: tuple  # ((phase, volume_L), ...) of the dilute phases present, in PHASES order.
    places: tuple  # Place, in place order.
    steps: tuple  # Step, in declared order.
    terms: tuple  # ((law ID, parsed data), ...), in declared order.
    rate_factor: tuple | None  # (law ID, parsed data), or None.
    founder: tuple  # Counts per place (0 for a held place).
    role: str | None = None  # "probe" (§0.2b rule 8), or None: a world to run.
    geometry: tuple | None = None  # OL2: (law ID, parsed data), or None (geometry.py).
    division: dict | None = None  # OL3: the shear fission's declaration (division.py), or None.
    population: dict | None = None  # OL2 milestone 3: the shared pool's slots and founders.
    sites: tuple | None = None  # FR-21: declared ((site, complex), ...) pairs, or None.
    # FR-46: the declared pairs whose face is the lumen's, ((site, complex), ...), or None (every
    # declared pair binds from the pool, as FR-21's do).
    inner_sites: tuple | None = None
    hazard: tuple | None = None  # FR-31: a vesicle hazard, (law ID, parsed data), or None.
    # OL6 S7: cells.operator.size_threshold_division@1's declaration (size_division.py), or None. It is
    # declared in the world's division block, by law, and kept apart from `division` (shear's).
    size_division: dict | None = None

    @property
    def place_names(self):
        return tuple(p.name for p in self.places)

    def place_index(self, name):
        return self.place_names.index(name)

    def volume(self, phase):
        return dict(self.volumes).get(phase)

    def species_by_id(self, name):
        return next(s for s in self.species if s.id == name)

    @property
    def phases_present(self):
        return tuple(p for p in PHASES if any(q.phase == p for q in self.places))


def _signed(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ConfigError(f"{name} must be a finite number")
    return result


def parse_units(raw):
    require_fields(raw, {"time", "temperature_K", "standard_concentration_mM"}, "world: units")
    if raw["time"] != TIME_UNIT:
        raise ConfigError("world: units: time is 's' (version 2 runs in physical units, R3)")
    return Units(
        TIME_UNIT,
        finite_number(raw["temperature_K"], "world: units: temperature_K", positive=True),
        finite_number(
            raw["standard_concentration_mM"],
            "world: units: standard_concentration_mM",
            positive=True,
        ),
    )


def _moieties(raw, name):
    if raw is None:
        return None
    if not isinstance(raw, dict) or not raw:
        raise ConfigError(
            f"world: species {name} declares its moieties as positive integer counts (null: its "
            "own moiety)"
        )
    out = []
    for moiety, count in raw.items():
        if type(count) is not int or count < 1:
            raise ConfigError(f"world: species {name}'s moiety counts are positive integers")
        out.append((identifier(moiety), count))
    return tuple(sorted(out))


def _potentials(raw, name):
    """(solution, bilayer, lumen): D152's single number is the solution potential; `lumen` is
    FR-48's, absolute, None when undeclared."""
    if isinstance(raw, dict):
        if not raw or set(raw) - {"solution", "bilayer", "lumen"}:
            raise ConfigError(
                f"world: species {name}'s standard_mu_RT is a number (solution) or an object of "
                "solution, bilayer and lumen potentials"
            )
        solution, bilayer, lumen = raw.get("solution"), raw.get("bilayer"), raw.get("lumen")
        return (
            None if solution is None else _signed(solution, f"species {name}: solution μ°/RT"),
            None if bilayer is None else _signed(bilayer, f"species {name}: bilayer μ°/RT"),
            None if lumen is None else _signed(lumen, f"species {name}: lumen μ°/RT"),
        )
    return _signed(raw, f"species {name}'s standard_mu_RT"), None, None


def parse_species(raw):
    if type(raw) is not list or not raw:
        raise ConfigError("world: species is a non-empty list")
    out = []
    for entry in raw:
        require_fields(
            entry, {"id", "moieties", "standard_mu_RT", "catalogue", "evidence"}, "world: species"
        )
        name = identifier(entry["id"])
        if "@" in name:
            raise ConfigError(f"world: species id {name!r} has no '@' (it names places)")
        identity = species_registry.parse_identity(
            entry["catalogue"], entry["evidence"], f"world: species {name}"
        )
        solution, bilayer, lumen = _potentials(entry["standard_mu_RT"], name)
        out.append(
            Species(
                name,
                _moieties(entry["moieties"], name),
                solution,
                bilayer,
                identity.catalogue,
                identity.evidence,
                mu_lumen=lumen,
            )
        )
    if len({s.id for s in out}) != len(out):
        raise ConfigError("world: a species is listed twice")
    return tuple(out)


def _species_list(raw, phase, known):
    if type(raw) is not list or not raw:
        raise ConfigError(f"world: phases: {phase} lists its species in a non-empty list")
    names = [identifier(n) for n in raw]
    for n in names:
        if n not in known:
            raise ConfigError(f"world: phases: {phase} names {n!r}, not a declared species")
    if len(set(names)) != len(names):
        raise ConfigError(f"world: phases: {phase} lists a species twice")
    return names


def parse_phases(raw, species, *, osmotic=False):
    """(places, volumes): the places in place order, the dilute phases' volumes. Under
    `lumen_volume: osmotic` (OL2) the lumen's volume is a function of the counts, so its block
    declares none and it has no entry in the volumes."""
    if not isinstance(raw, dict) or MEMBRANE not in raw or set(raw) - set(PHASES):
        raise ConfigError(
            "world: phases is an object with the membrane (required) and the pool and the lumen "
            "(optional)"
        )
    known = {s.id: s for s in species}
    places, volumes = [], []
    for phase in PHASES:
        if phase not in raw:
            continue
        block = raw[phase]
        if phase == MEMBRANE:
            require_fields(block, {"species"}, "world: phases: membrane")
            names = _species_list(block["species"], phase, known)
            places += [Place(n, phase) for n in names]
            continue
        if phase == LUMEN and osmotic:
            if "volume_L" in block:
                raise ConfigError(
                    "world: phases: lumen: under lumen_volume osmotic the lumen's volume follows "
                    "from its counts and the membrane's area, so it declares no volume_L "
                    "(§0.2b rule 2)"
                )
            require_fields(block, {"species"}, "world: phases: lumen")
            names = _species_list(block["species"], phase, known)
            places += [Place(n, phase) for n in names]
            continue
        require_fields(block, {"volume_L", "species"}, f"world: phases: {phase}")
        volume = finite_number(
            block["volume_L"], f"world: phases: {phase}: volume_L", positive=True
        )
        volumes.append((phase, volume))
        if phase == LUMEN:
            names = _species_list(block["species"], phase, known)
            places += [Place(n, phase) for n in names]
            continue
        entries = block["species"]
        if type(entries) is not list or not entries:
            raise ConfigError("world: phases: pool lists its species in a non-empty list")
        listed = []
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("kind") not in ("finite", "held"):
                raise ConfigError(
                    "world: phases: a pool species is {id, kind: finite} or {id, kind: held, "
                    "held_mM}"
                )
            kind = entry["kind"]
            require_fields(
                entry, {"id", "kind"} | ({"held_mM"} if kind == "held" else set()), "pool species"
            )
            name = identifier(entry["id"])
            if name not in known:
                raise ConfigError(f"world: phases: pool names {name!r}, not a declared species")
            held = None
            if kind == "held":
                held = finite_number(
                    entry["held_mM"], f"pool species {name}: held_mM", positive=True
                )
            places.append(Place(name, phase, held))
            listed.append(name)
        if len(set(listed)) != len(listed):
            raise ConfigError("world: phases: pool lists a species twice")
    for place in places:
        if known[place.species].mu(place.phase) is None:
            raise ConfigError(
                f"world: species {place.species} is placed in the {place.phase}, so it declares "
                f"its {KIND_OF[place.phase]} standard potential"
            )
    return tuple(places), tuple(volumes)


def phases_to_dict(world):
    """The phases block, from the places (in place order) and the volumes."""
    out = {}
    for phase in PHASES:
        mine = [p for p in world.places if p.phase == phase]
        if not mine:
            continue
        if phase == MEMBRANE:
            out[phase] = {"species": [p.species for p in mine]}
        elif phase == LUMEN and world.volume(phase) is None:  # OL2's osmotic lumen
            out[phase] = {"species": [p.species for p in mine]}
        elif phase == LUMEN:
            out[phase] = {"volume_L": world.volume(phase), "species": [p.species for p in mine]}
        else:
            out[phase] = {
                "volume_L": world.volume(phase),
                "species": [
                    {"id": p.species, "kind": "finite"}
                    if not p.held
                    else {"id": p.species, "kind": "held", "held_mM": p.held_mM}
                    for p in mine
                ],
            }
    return out


def _side(raw, step, which, form, phase, by_name):
    if not isinstance(raw, dict):
        raise ConfigError(f"world: step {step}'s {which} is an object {{place: count}}")
    out = []
    for key, count in raw.items():
        name = f"{key}@{phase}" if form == "phase" else key
        if form == "phase" and "@" in key:
            raise ConfigError(
                f"world: step {step} is declared by phase ({phase}): its {which} name species, "
                "not places"
            )
        if name not in by_name:
            raise ConfigError(f"world: step {step} names {name!r}, not a declared place")
        if type(count) is not int or count < 1:
            raise ConfigError(
                f"world: step {step}'s counts are positive integers ({which} {key}: {count!r})"
            )
        out.append((name, count))
    return out


def parse_step(raw, world_places, species, laws, encounter=None):
    if not isinstance(raw, dict):
        raise ConfigError("world: a step is an object")
    form = "phase" if "phase" in raw else "locus"
    rate_key = _rate_key(raw, laws, encounter)
    keys = {"id", "reactants", "products", form, "law", rate_key}
    require_fields(raw, keys, "world: step")
    step = identifier(raw["id"])
    by_name = {p.name: p for p in world_places}
    where = raw[form]
    if where not in PHASES:
        raise ConfigError(f"world: step {step}'s {form} is one of {', '.join(PHASES)}")
    reactants = _side(raw["reactants"], step, "reactants", form, where, by_name)
    products = _side(raw["products"], step, "products", form, where, by_name)
    for which, side in (("reactant", reactants), ("product", products)):
        molecules = sum(c for _, c in side)
        if molecules > MAX_SIDE:
            raise ConfigError(
                f"world: step {step} has {molecules} {which} molecules; at most {MAX_SIDE} (D152: "
                "each direction is an elementary step)"
            )
    if not reactants or not products:
        raise ConfigError(
            f"world: step {step} has reactants and products (a passive step conserves its "
            "moieties; a source or a sink is a held species, declared as such)"
        )
    order = {p.name: i for i, p in enumerate(world_places)}
    reactants = tuple(sorted(reactants, key=lambda e: order[e[0]]))
    products = tuple(sorted(products, key=lambda e: order[e[0]]))
    phases = {by_name[n].phase for n, _ in (*reactants, *products)}
    if form == "locus":
        expected = MEMBRANE if len(phases) > 1 else next(iter(phases))
        if where != expected:
            raise ConfigError(
                f"world: step {step}'s locus is {where}, but its places "
                + (
                    "span phases, so its locus is the membrane (OL1's only interface)"
                    if len(phases) > 1
                    else f"lie in the {expected}, so its locus is the {expected}"
                )
            )
    net = {}
    for name, count in reactants:
        net[name] = net.get(name, 0) - count
    for name, count in products:
        net[name] = net.get(name, 0) + count
    if not any(net.values()):
        raise ConfigError(f"world: step {step} changes nothing")
    known = {s.id: s for s in species}
    balance = {}
    for name, change in net.items():
        for moiety, count in known[by_name[name].species].moiety_counts().items():
            balance[moiety] = balance.get(moiety, 0) + count * change
    unbalanced = sorted(m for m, v in balance.items() if v)
    if unbalanced:
        raise ConfigError(
            f"world: step {step} does not conserve its declared moieties ({', '.join(unbalanced)}"
            "): a passive step conserves every moiety across places, held species counted"
        )
    if raw["law"] not in laws:
        raise ConfigError(f"world: step {step}'s law is one of {', '.join(sorted(laws))}")
    if rate_key == "forward_rate_per_s":  # OL1's key: a bare number, as it always was.
        rate = finite_number(raw[rate_key], f"step {step}: {rate_key}", positive=True)
        return Step(step, form, reactants, products, where, raw["law"], rate, rate_key)
    entry = raw[rate_key]
    if not isinstance(entry, dict) or set(entry) != {"value", "provenance"}:
        raise ConfigError(
            f"world: step {step}'s {rate_key} is {{value, provenance}} (§0.2e rule 7)"
        )
    if not isinstance(entry["provenance"], str) or not entry["provenance"]:
        raise ConfigError(f"world: step {step}'s {rate_key} states its provenance")
    rate = finite_number(entry["value"], f"step {step}: {rate_key}", positive=True)
    return Step(
        step, form, reactants, products, where, raw["law"], rate, rate_key, entry["provenance"]
    )


def _rate_key(raw, laws, encounter):
    """The step's rate-constant key: OL1's `forward_rate_per_s`, unless its law names its own
    (a mapping by the world's exchange_encounter for OL2's geometric laws, §0.2d item 2)."""
    name = raw.get("law")
    law = laws.get(name) if isinstance(name, str) else None
    key = getattr(law, "rate_key", "forward_rate_per_s")
    if isinstance(key, str):
        return key
    if encounter is None:
        raise ConfigError(
            f"world: step {raw.get('id')!r}'s law {name} takes its encounter from a geometry, and "
            "the world declares none (§0.2c rule 3)"
        )
    return key[encounter]


FACES = ("outer", "inner")  # FR-46: the pool's face and the lumen's


def parse_sites(raw, places):
    """FR-21's declared pairs, [{"site", "complex"}, ...] -> (((site, complex), ...), inner): both
    membrane species, distinct, each complex the complex of one site (§0.2f). FR-46: a pair may
    declare its face, outer (the default) or inner; `inner` is the inner pairs, or None."""
    if type(raw) is not list or not raw:
        raise ConfigError("world: sites is a non-empty list of {site, complex} pairs")
    membrane = {p.species for p in places if p.phase == MEMBRANE}
    out, complexes, inner = [], set(), []
    for entry in raw:
        keys = {"site", "complex"} | ({"face"} if isinstance(entry, dict) and "face" in entry
                                      else set())  # fmt: skip
        require_fields(entry, keys, "world: sites: a pair")
        face = entry.get("face", "outer")
        if face not in FACES:
            raise ConfigError(f"world: sites: a pair's face is outer or inner, not {face!r}")
        site, complex_ = identifier(entry["site"]), identifier(entry["complex"])
        for role, name in (("site", site), ("complex", complex_)):
            if name not in membrane:
                raise ConfigError(f"world: sites: the {role} {name} is not a membrane species")
        if site == complex_:
            raise ConfigError(f"world: sites: {site} is declared as its own complex")
        if complex_ in complexes:
            raise ConfigError(
                f"world: sites: the complex {complex_} is declared twice (one site per complex)"
            )
        complexes.add(complex_)
        out.append((site, complex_))
        if face == "inner":
            inner.append((site, complex_))
    return tuple(out), (tuple(inner) or None)


def sites_to_dict(sites, inner=None):
    """The sites block; FR-46's face is written only for an inner pair (D148)."""
    inner = set(inner or ())
    return [{"site": site, "complex": complex_, **({"face": "inner"} if (site, complex_) in inner
                                                    else {})}
            for site, complex_ in sites]  # fmt: skip


def parse_founder(raw, places):
    if not isinstance(raw, dict):
        raise ConfigError("world: founder is an object {place: count} of every finite place")
    finite = [p.name for p in places if not p.held]
    missing = sorted(set(finite) - set(raw))
    unknown = sorted(set(raw) - set(finite))
    if missing or unknown:
        raise ConfigError(
            f"world: founder gives a count for every finite place, explicitly (held places have "
            f"none); missing={missing}, unknown={unknown}"
        )
    return tuple(
        0
        if p.held
        else bounded_integer(raw[p.name], f"world: founder {p.name}", minimum=0, maximum=2**31 - 1)
        for p in places
    )


def steps_to_dict(steps):
    out = []
    for s in steps:
        if s.form == "phase":
            strip = lambda side: {n.split("@")[0]: c for n, c in side}  # noqa: E731
            entry = {"id": s.id, "phase": s.locus}
        else:
            strip = dict
            entry = {"id": s.id, "locus": s.locus}
        entry.update(
            reactants=strip(s.reactants),
            products=strip(s.products),
            law=s.law,
        )
        entry[s.rate_key] = (
            s.forward_rate_per_s
            if s.rate_provenance is None
            else {"value": s.forward_rate_per_s, "provenance": s.rate_provenance}
        )
        out.append(entry)
    return out


def species_to_dict(species):
    out = []
    for s in species:
        potentials = {}
        if s.mu_solution is not None:
            potentials["solution"] = s.mu_solution
        if s.mu_bilayer is not None:
            potentials["bilayer"] = s.mu_bilayer
        if s.mu_lumen is not None:  # FR-48: written only when declared (D148)
            potentials["lumen"] = s.mu_lumen
        out.append(
            {
                "id": s.id,
                "moieties": None if s.moieties is None else dict(s.moieties),
                "standard_mu_RT": potentials,
                "catalogue": None
                if s.catalogue is None
                else {"catalogue": s.catalogue[0], "entry": s.catalogue[1]},
                "evidence": s.evidence,
            }
        )
    return out
