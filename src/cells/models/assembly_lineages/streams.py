"""Keyed random streams: the module design's RNG contract (MODULE_SYSTEM_DESIGN §5), first consumer.

Cells owns the streams, their keys and the counters; a law or an operator takes keys (or the
uniforms drawn from them), never a seed. ARCHITECTURE.md's rules hold: one stream per purpose,
keys derived from the run, lineage and event identity, and diagnostics never draw from them.

Key derivation (Threefry-2x32; every fold is jax.random.fold_in of one unsigned 32-bit word):

    key(seed) -> environment -> lineage -> branch                      the world's base key
              -> carrier (low word, then high word) -> domain           an assembly's stream
              -> counter (low word, then high word)                     one draw

- seed: the campaign seed, in [0, 2**32).
- environment, lineage, branch: unsigned 32-bit identities of the world.
- carrier: the assembly's carrier key (int64, written at its birth). fold_in narrows its data
  to 32 bits, so a 64-bit value is folded as two words; folding it once would give two carriers
  that differ only above bit 31 the same stream.
- domain: DOMAINS, one stream per purpose of an assembly. `label` (4) is reserved (D202): its
  number is fixed for the material labels' draws (docs/RELATIONSHIPS_DESIGN.md §2.7), and no
  stream of it can be made until labels are built, so no run draws from it.
- counter: the draw's index within its stream (the exchange stream counts the assembly's own
  events from 0 at its birth; partition and continuation draw once, at counter 0).

So an assembly's draws depend on its identity alone, never on its lane, its batch or the order of
other assemblies' events: a lineage replays bitwise in any batch, and a branch (a future from a
restored state) is independent of its siblings by its branch word.

Uniforms (UNIFORM): each 64-bit word gives u = (m + 1/2) 2**-52, with m its low 52 bits: the
midpoints of 2**52 equal bins, so u lies in the open interval (0, 1) and -ln u is finite, without
truncating a distribution (the capsid kernel's convention, cells/assembly/kernel.py).
"""

from types import MappingProxyType

GENERATOR = "threefry2x32"
DOMAINS = MappingProxyType(
    {"initial_composition": 0, "exchange": 1, "partition": 2, "continuation": 3, "label": 4}
)
RESERVED = ("label",)  # Numbered, never drawn: stream_key_data refuses them.
FOLD_ORDER = (
    "seed",
    "environment",
    "lineage",
    "branch",
    "carrier: low 32-bit word, then high word",
    "domain",
    "counter: low 32-bit word, then high word",
)
UNIFORM = (
    "u = (m + 1/2) * 2**-52, m the low 52 bits of one 64-bit Threefry word "
    "(jax.random.bits, uint64): the open interval (0, 1)"
)
WORD = 2**32


def check_word(value, name):
    if type(value) is not int or not 0 <= value < WORD:
        raise ValueError(f"{name} must be an integer in [0, 2**32)")
    return value


def identity(seed, environment, lineage, branch):
    """The stream's identity as a run records it."""
    return {
        "generator": GENERATOR,
        "seed": seed,
        "environment": environment,
        "lineage": lineage,
        "branch": branch,
        "fold_order": list(FOLD_ORDER),
        "domains": dict(DOMAINS),
        "reserved_domains": list(RESERVED),
        "uniform": UNIFORM,
    }


# ------------------------------------------------------------------ device (JAX)


def base_key_data(seed, environment, lineage, branch):
    """The world's base key as raw key data, uint32[2] (host side, once per world)."""
    import jax
    import numpy as np

    key = jax.random.key(check_word(seed, "seed"), impl=GENERATOR)
    for value, name in ((environment, "environment"), (lineage, "lineage"), (branch, "branch")):
        key = jax.random.fold_in(key, np.uint32(check_word(value, name)))
    return np.asarray(jax.random.key_data(key), dtype=np.uint32)


def _wrap(data):
    import jax

    return jax.random.wrap_key_data(data, impl=GENERATOR)


def _fold64(key, value):
    """Fold a nonnegative int64 in as two 32-bit words, low then high."""
    import jax
    import jax.numpy as jnp

    value = jnp.asarray(value, dtype=jnp.int64)
    low = (value & jnp.int64(WORD - 1)).astype(jnp.uint32)
    high = ((value >> 32) & jnp.int64(WORD - 1)).astype(jnp.uint32)
    return jax.random.fold_in(jax.random.fold_in(key, low), high)


def stream_key_data(base, carrier, domain):
    """An assembly's stream for one domain, as raw key data (written at the assembly's birth)."""
    import jax
    import jax.numpy as jnp

    if domain in RESERVED:
        raise ValueError(f"The {domain} stream domain is reserved: nothing draws from it yet")
    key = _fold64(_wrap(base), carrier)
    key = jax.random.fold_in(key, jnp.uint32(DOMAINS[domain]))
    return jax.random.key_data(key)


def uniforms(stream, counter, count):
    """`count` open-interval float64 uniforms, the stream's draw number `counter`."""
    import jax
    import jax.numpy as jnp

    key = _fold64(_wrap(stream), counter)
    bits = jax.random.bits(key, shape=(count,), dtype=jnp.uint64)
    mantissa = bits & jnp.uint64((1 << 52) - 1)
    return (mantissa.astype(jnp.float64) + 0.5) * (2.0**-52)
