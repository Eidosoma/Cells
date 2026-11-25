"""What every section of a world's block is written and read with (worlds.py, stores.py)."""

import copy
from dataclasses import dataclass

from cells.definitions.surface_pump_v3_spec import channel_laws
from validation.ensemble_reexpression.labels import label, string

ONES = [[0.0, 1.0]]  # A schedule of 1 throughout, the default of every control.


class NoSection(ValueError):
    """A key or a field of a block that has no place in a definition, or a piece of a definition
    that has none in a block."""


def no_section(text):
    return NoSection(f"no_section: {text}")


@dataclass(frozen=True)
class Section:
    """Some of a block's top keys, and how they are written and read.

    write(block, raw) adds them to the raw definition; read(raw) gives {key: value} back. take(raw),
    where a section has one, gives the definition without what the section added, which the sections
    before it then read: sections are written in their order and read in the opposite one."""

    keys: tuple[str, ...]
    write: object
    read: object
    take: object = None


def entities(value):
    """The (ID, entity) pairs of a block's map of entities; none for [], {} or an omitted one."""
    return tuple(value.items()) if isinstance(value, dict) else ()


def known(value, fields, where):
    unknown = sorted(set(value) - set(fields))
    if unknown:
        raise no_section(f"{where} has no place for {', '.join(unknown)}")
    return value


def taken(value, fields):
    return {name: copy.deepcopy(value[name]) for name in fields if name in value}


def mapped(rows):
    """Entities as the block prints them: a map by ID, or [] for none."""
    return rows if rows else []


def schedule(changes):
    return [{"time": t, "availability": a} for t, a in changes]


def pairs(changes):
    return [[c["time"], c["availability"]] for c in changes]


def rest(entry, names, defaults):
    """The fields of a definition's entity that the block has no name for, without the ones at their
    defaults: they are read back under their own names, so nothing declared is hidden."""
    return {
        key: value
        for key, value in entry.items()
        if key not in names and not (key in defaults and value == defaults[key])
    }


def nothing_else(entry, names, defaults, where):
    """Refuse a definition's entity that declares anything its block has no name for, at a value
    that is not its default: read back under its own name it would be passed over."""
    more = sorted(rest(entry, names, defaults))
    if more:
        raise no_section(f"a block has no place for the {', '.join(more)} of {where}")


def groups(schedules, names, key, rename=lambda name: name):
    """One control group for each name, its schedule or 1 throughout. A schedule of any other name
    is the default written out where it is 1 throughout, and says nothing (SPEC §2.4); any other is
    written too, for the engine to refuse."""
    given = schedules if isinstance(schedules, dict) else {}
    others = [n for n in given if n not in names and given[n] != ONES]
    return [
        {key: rename(name), "schedule": schedule(given.get(name, ONES))}
        for name in (*names, *others)
    ]


# ------------------------------------------------------------------ channels


_CHANNEL = ("membrane_id", "kinetic_law", "max_permeability_m_per_s", "abundance")


def _law_of(law_id):
    return channel_laws().get(law_id)


def _permeant(species, law):
    """The permeant ions of a population of this species, with the law's own relative permeability
    (1 where the law does not carry the species, for the engine to refuse)."""
    ratios = {s: weight for s, _, weight in law.permeant} if law is not None else {}
    return [{"species_id": species, "relative_permeability": ratios.get(species, 1.0)}]


def channel_rows(channels):
    """The channel populations of a block's map of them, in the definition's form."""
    rows = []
    for name, c in entities(channels):
        known(c, (*_CHANNEL, "species_id", "initial_gate"), name)
        row = {"id": name} | taken(c, _CHANNEL)
        row["kinetic_law"] = string(c.get("kinetic_law"))
        law = _law_of(row["kinetic_law"])
        gate = c.get("initial_gate", {})
        order = tuple(gate) if law is None or set(gate) != set(law.gates) else law.gates
        row["initial_gate"] = [gate[g] for g in order]
        row["permeant_ions"] = _permeant(c.get("species_id"), law)
        rows.append(row)
    return rows


def read_channels(rows):
    """{ID: a channel's block} of a definition's channel populations."""
    out = {}
    for c in rows:
        law = _law_of(c["kinetic_law"])
        gates = law.gates if law is not None else tuple(map(str, range(len(c["initial_gate"]))))
        ions = c["permeant_ions"]
        row = {
            "membrane_id": c["membrane_id"],
            "species_id": ions[0]["species_id"]
            if len(ions) == 1
            else [i["species_id"] for i in ions],
            "kinetic_law": label(c["kinetic_law"]),
            "max_permeability_m_per_s": c["max_permeability_m_per_s"],
            "abundance": c["abundance"],
            "initial_gate": dict(zip(gates, c["initial_gate"], strict=True)),
        }
        if any(i["relative_permeability"] != 1 for i in ions):
            row["permeant_ions"] = copy.deepcopy(ions)
        out[c["id"]] = row | rest(c, {"id", *_CHANNEL, "initial_gate", "permeant_ions"}, {})
    return out
