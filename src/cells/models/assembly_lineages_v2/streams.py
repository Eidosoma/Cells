"""Keyed random streams of version 2: @1's derivation and uniforms, with version 2's domain table.

Version 2 draws exactly as @1 does (cells.models.assembly_lineages.streams, imported unchanged): the
same Threefry-2x32 key derivation (seed, environment, lineage, branch, then the carrier's two words,
then the domain, then the counter's two words) and the same open-interval uniforms. Its domain
numbers 0-4 are @1's, with the same meanings, so a world of version 2 that reproduces an @1 world
(the GARD limit, OL6) draws @1's uniforms:

    0 initial_composition, 1 events (@1 names it `exchange`: the occupant's event stream),
    2 partition, 3 continuation, 4 label (reserved, D202), 5 world (reserved for OL2's world-level
    stream of a shared pool).

A reserved domain is numbered and never drawn: stream_key_data refuses it.
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
RESERVED = ("label", "world")
# @1's name for each shared domain: its numbers are @1's, so its derivation is reused as it is.
V1_NAMES = MappingProxyType(
    {"initial_composition": "initial_composition", "events": "exchange", "partition": "partition",
     "continuation": "continuation"}
)  # fmt: skip

check_word = v1.check_word
base_key_data = v1.base_key_data
uniforms = v1.uniforms


def identity(seed, environment, lineage, branch):
    """The stream's identity as a run records it: @1's, with version 2's domain table."""
    out = v1.identity(seed, environment, lineage, branch)
    out["domains"] = dict(DOMAINS)
    out["reserved_domains"] = list(RESERVED)
    out["same_as"] = (
        "cells.assembly_lineages@1's derivation and uniforms; domains 0-4 are @1's numbers "
        "(1, events, is @1's exchange stream)"
    )
    return out


def stream_key_data(base, carrier, domain):
    """An assembly's stream for one domain, as raw key data: @1's derivation for @1's numbers."""
    if domain in RESERVED:
        raise ValueError(f"The {domain} stream domain is reserved: nothing draws from it yet")
    if domain not in V1_NAMES:
        raise ValueError(f"Unknown stream domain {domain!r}")
    return v1.stream_key_data(base, carrier, V1_NAMES[domain])
