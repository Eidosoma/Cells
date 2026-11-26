"""The conventions a world of version 2 declares: named tokens, with no default (OL1's FORMAT §1).

Each choice that changes a rate or a free energy is stated by the world, never assumed, so two
readers of one world (the engine and an independent reference) cannot differ silently:

- `free_energy_form`: `discrete`. F uses ln n! exactly, the only form the exact event kernel
  admits: the reverse rate derived from F is the products' mass action only in it. `continuum`
  (Stirling's n ln n - n) is reserved for the deterministic representation (U7, later) and
  refused here.
- `condensed_measure`: the membrane's mixing measure, with its offset c:
  `multinomial` (c = 0): -ln N! + sum ln n_i!;
  `multinomial_less_one` (c = 1): -ln (N - 1)! + sum ln n_i!, the multinomial plus ln N, which is
  cells.model.assembly_lineages@1's measure exactly.
- `membrane_kinetics`: `count_on_m`. The membrane has no volume until OL2: a membrane reactant's
  activity is drawn without replacement at the firing state, prod ff(n_i, a_i) / ff(N - c, r_mem),
  and the membrane's extent is E(m) = N(m) - c + 1 on the pair's common state m. An extension
  point: OL2 adds values (an area on m); this one keeps its meaning.
- `lumen_volume`: `declared`, a constant volume_L. An extension point: OL2 adds a volume from the
  counts; this one keeps its meaning.
- `empty_catalyst_phase`: `uncatalysed`: a rate factor is 1 where its catalysing phase is empty at
  m (the last-molecule factor of GARD's pair-consistent form).
- `last_molecule` (§0.2a, "The last molecule" and "The empty common state"): `kept` (any measure)
  gives rate zero only to a pair whose step changes the membrane's count and one of whose end states
  has an empty membrane, so the membrane never empties and nothing else is frozen (a pool step at an
  empty membrane fires at the pool's mass action); `reversible` (c = 0 only) makes the empty
  membrane an ordinary state, left by a join with E = 1; `extinct` (c = 1 only) is G1's boundary: a
  step in either direction whose result empties the membrane fires at the pair rule's cancelled
  form, has no reverse, and ends the assembly; its heat is booked against F_mem(empty) = 0. Wherever
  the membrane factor is 0/0 (a common state with an empty membrane, neither end state empty: a lone
  molecule changing form, or two joining), the cancelled form applies under every token.
"""

from dataclasses import dataclass
from types import MappingProxyType

from cells.definitions.specs import ConfigError

TOKENS = MappingProxyType(
    {
        "free_energy_form": ("discrete",),
        "condensed_measure": ("multinomial", "multinomial_less_one"),
        "membrane_kinetics": ("count_on_m",),
        "lumen_volume": ("declared",),
        "empty_catalyst_phase": ("uncatalysed",),
        "last_molecule": ("kept", "reversible", "extinct"),
    }
)
RESERVED = MappingProxyType(
    {
        "free_energy_form": {
            "continuum": "Stirling's form is reserved for the deterministic representation (U7, "
            "later): the exact event kernel admits only the discrete form, the one in which the "
            "reverse rate derived from F is the products' mass action"
        }
    }
)
OFFSET = MappingProxyType({"multinomial": 0, "multinomial_less_one": 1})
ENCOUNTER = "exchange_encounter"  # OL2's conditional token (§0.2b rule 1).
OSMOTIC = "osmotic"  # OL2's lumen_volume value, only with a geometry (§0.2b rule 2).
ENCOUNTERS = ("insertion_area", "diffusion_radius")
LAST_MOLECULE_MEASURES = MappingProxyType(
    {
        "kept": ("multinomial", "multinomial_less_one"),
        "reversible": ("multinomial",),
        "extinct": ("multinomial_less_one",),
    }
)


@dataclass(frozen=True)
class Conventions:
    free_energy_form: str
    condensed_measure: str
    membrane_kinetics: str
    lumen_volume: str
    empty_catalyst_phase: str
    last_molecule: str
    # OL2 (§0.2b rule 1, §0.2c rule 1): declared exactly when the world declares a geometry; absent
    # (None) otherwise, and then never written, so OL1's worlds and their ids do not move.
    exchange_encounter: str | None = None

    @property
    def offset(self):
        """c, the condensed measure's offset: 0 for the multinomial, 1 for @1's measure."""
        return OFFSET[self.condensed_measure]


def parse(raw, *, geometry=False):
    if not isinstance(raw, dict):
        raise ConfigError("world: conventions is an object of named tokens")
    if raw.get("lumen_volume") == OSMOTIC and not geometry:
        raise ConfigError(
            "world: conventions: lumen_volume osmotic takes the lumen's volume from the "
            "membrane's area, so the world declares a geometry (§0.2b rule 2)"
        )
    if geometry or ENCOUNTER in raw:
        return _parse_with_encounter(raw, geometry)
    missing, unknown = sorted(set(TOKENS) - set(raw)), sorted(set(raw) - set(TOKENS))
    if missing or unknown:
        raise ConfigError(
            f"world: conventions: every token is declared, with no default; missing={missing}, "
            f"unknown={unknown}"
        )
    for key, allowed in TOKENS.items():
        value = raw[key]
        if value in RESERVED.get(key, {}):
            raise ConfigError(f"world: conventions: {key} {value!r}: {RESERVED[key][value]}")
        if value not in allowed:
            raise ConfigError(
                f"world: conventions: {key} is one of {', '.join(allowed)}, not {value!r}"
            )
    out = Conventions(**{key: raw[key] for key in TOKENS})
    if out.condensed_measure not in LAST_MOLECULE_MEASURES[out.last_molecule]:
        raise ConfigError(
            f"world: conventions: last_molecule {out.last_molecule!r} is declared with the "
            f"condensed measure {' or '.join(LAST_MOLECULE_MEASURES[out.last_molecule])}, not "
            f"{out.condensed_measure!r}"
        )
    return out


def _parse_with_encounter(raw, geometry):
    """The six tokens and `exchange_encounter`, which only a world with a geometry declares."""
    if not geometry:
        raise ConfigError(
            f"world: conventions: {ENCOUNTER} is declared only by a world that declares a "
            "geometry (§0.2c rule 1)"
        )
    if ENCOUNTER not in raw:
        raise ConfigError(
            f"world: conventions: a world that declares a geometry declares {ENCOUNTER}, one of "
            f"{', '.join(ENCOUNTERS)}, with no default (§0.2b rule 1)"
        )
    value = raw[ENCOUNTER]
    if value not in ENCOUNTERS:
        raise ConfigError(
            f"world: conventions: {ENCOUNTER} is one of {', '.join(ENCOUNTERS)}, not {value!r}"
        )
    inner = {key: v for key, v in raw.items() if key != ENCOUNTER}
    osmotic = inner.get("lumen_volume") == OSMOTIC
    if osmotic:  # Validated as OL1's six, then set: OL1's own refusal text is unchanged.
        inner["lumen_volume"] = "declared"
    out = parse(inner)
    fields = {key: getattr(out, key) for key in TOKENS}
    if osmotic:
        fields["lumen_volume"] = OSMOTIC
    return Conventions(**fields, exchange_encounter=value)


def to_dict(conventions):
    out = {key: getattr(conventions, key) for key in TOKENS}
    if conventions.exchange_encounter is not None:
        out[ENCOUNTER] = conventions.exchange_encounter
    return out
