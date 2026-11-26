"""Keyed random streams of version 2: @1's derivation and uniforms, with version 2's domain table.

Version 2 draws exactly as @1 does (cells.models.assembly_lineages.streams, imported unchanged): the
same Threefry-2x32 key derivation (seed, environment, lineage, branch, then the carrier's two words,
then the domain, then the counter's two words) and the same open-interval uniforms. Its domain
numbers 0-4 are @1's, with the same meanings, so a world of version 2 that reproduces an @1 world
(the GARD limit, OL6) draws @1's uniforms:

    0 initial_composition, 1 events (@1 names it `exchange`: the occupant's event stream),
    2 partition, 3 continuation, 4 label (reserved, D202), 5 world (a shared pool's world-level
    stream, drawn since OL2 milestone 3), and 6 schedule (shear times and transfers, likewise).

A reserved domain (RESERVED: `label`) is numbered and never drawn: stream_key_data refuses it.
Domains 5 and 6 have their own derivation (LATER), and only a run that draws on them states them
(scheduled_identity). Every other run's identity keeps the table it recorded before they were
drawn, with `world` among its reserved domains (UNSCHEDULED_RESERVED), so its records do not move.
"""

from types import MappingProxyType

from cells.models.assembly_lineages import streams as v1

GENERATOR = v1.GENERATOR
UNIFORM = v1.UNIFORM
DOMAINS = MappingProxyType(
    {
        "initial_composition": 0,
        "events": 1,
        "partition": 2,
        "continuation": 3,
        "label": 4,
        "world": 5,
    }
)
RESERVED = ("label",)  # Refused by stream_key_data: no run draws from it yet.
# The reserved domains an unscheduled run's identity records: OL1's table, kept so its records do
# not move (domain 5 was reserved until OL2 milestone 3 drew on it).
UNSCHEDULED_RESERVED = ("label", "world")
# @1's name for each shared domain: its numbers are @1's, so its derivation is reused as it is.
V1_NAMES = MappingProxyType(
    {"initial_composition": "initial_composition", "events": "exchange", "partition": "partition",
     "continuation": "continuation"}
)  # fmt: skip

check_word = v1.check_word
base_key_data = v1.base_key_data
uniforms = v1.uniforms


def block(stream, counter, count):
    """The `count` uniforms of uniforms(stream, counter, count), bitwise: drawn at the next power of
    two and cut to that draw's prefix. A host draw whose size varies from call to call (a
    partition's N + k + N_L) then compiles once per power of two, not once per size. The prefix of
    a larger draw is the smaller draw only under JAX's partitionable threefry, which every run of
    the family requires (§0.2d item 9), so without it this refuses. uniforms() itself stays as it
    is: the kernel traces it."""
    import jax

    count = int(count)
    if count < 0:
        raise ValueError(f"A block holds a non-negative count of uniforms, not {count}")
    if not jax.config.jax_threefry_partitionable:
        raise ValueError(
            "A block's prefix is the smaller draw only under JAX's partitionable threefry, and "
            "jax_threefry_partitionable is off (§0.2d item 9)"
        )
    return uniforms(stream, counter, 1 << max(count - 1, 0).bit_length())[:count]


def identity(seed, environment, lineage, branch):
    """The stream's identity as a run records it: @1's, with version 2's domain table."""
    out = v1.identity(seed, environment, lineage, branch)
    out["domains"] = dict(DOMAINS)
    out["reserved_domains"] = list(UNSCHEDULED_RESERVED)
    out["same_as"] = (
        "cells.model.assembly_lineages@1's derivation and uniforms; domains 0-4 are @1's numbers "
        "(1, events, is @1's exchange stream)"
    )
    return out


# OL2 milestone 3: the world's selection stream (domain 5, carrier word 0, the lead's ruling of 19
# November) and the schedules' stream (domain 6, carrier word the schedule's declared index), by
# @1's derivation with their own numbers. identity() is unchanged: only a run that draws on them
# states them (scheduled_identity).
LATER = MappingProxyType({"world": 5, "schedule": 6})
WORLD_CARRIER = 0


def scheduled_identity(seed, environment, lineage, branch):
    """identity() of a run that draws on domain 5 or 6: both drawn, only `label` reserved."""
    out = identity(seed, environment, lineage, branch)
    out["domains"] = {**dict(DOMAINS), **dict(LATER)}
    out["reserved_domains"] = list(RESERVED)
    out["carriers"] = {"world": WORLD_CARRIER, "schedule": "the schedule's declared index"}
    return out


# FR-31 Phase A: the pore clock's thresholds (domain 7, carrier word the vesicle's key, counter its
# pore draws from 0), by @1's derivation with its own number, as domains 5 and 6. Only a run that
# draws on it states it (pore_identity), so every other run's identity is unchanged.
PORE = MappingProxyType({"pore": 7})


def pore_identity(seed, environment, lineage, branch, *, scheduled):
    """identity(), or scheduled_identity() when domain 5 or 6 is drawn too, of a run that draws
    on domain 7 (a world that declares the pore law)."""
    build = scheduled_identity if scheduled else identity
    out = build(seed, environment, lineage, branch)
    out["domains"] = {**out["domains"], **dict(PORE)}
    out["carriers"] = {**out.get("carriers", {}), "pore": "the vesicle's carrier key"}
    return out


def stream_key_data(base, carrier, domain):
    """An assembly's stream for one domain, as raw key data: @1's derivation for @1's numbers."""
    if domain in LATER or domain in PORE:
        import jax
        import jax.numpy as jnp

        number = LATER[domain] if domain in LATER else PORE[domain]
        key = v1._fold64(v1._wrap(base), carrier)
        return jax.random.key_data(jax.random.fold_in(key, jnp.uint32(number)))
    if domain in RESERVED:
        raise ValueError(f"The {domain} stream domain is reserved: nothing draws from it yet")
    if domain not in V1_NAMES:
        raise ValueError(f"Unknown stream domain {domain!r}")
    return v1.stream_key_data(base, carrier, V1_NAMES[domain])
