"""Counter-based keyed random streams for the cell composite (FR-43 part 3; D315).

The composite's first random streams, owned by Cells: an operator takes key data and counters, never
a seed (docs/MODULE_SYSTEM_DESIGN.md §5). Every draw depends only on (seed, site, domain, counter),
never on the order of other draws, a batch's lane or a window. So a run restarted from a checkpoint,
which carries the counters as state, draws what the uninterrupted run drew, and each world of a
batch draws its own stream from its own bound key data.

**The derivation**, Threefry-2x32 (`jax.random`; each fold is `jax.random.fold_in` of one unsigned
32-bit word):

    base    = jax.random.key(seed, impl="threefry2x32")            seed in [0, 2**32)
    site    = fold_in(fold_in(base, low32(s)), high32(s))           s: the site's declared index
    stream  = fold_in(site, domain)                                 DOMAINS
    draw k  = fold_in(fold_in(stream, low32(k)), high32(k))         k: the draw's counter
    words   = jax.random.bits(draw k, shape=(count,), dtype=uint64)
    u       = ((words & (2**52 - 1)) + 0.5) * 2**-52

**The uniform map** is the assembly family's (cells.models.assembly_lineages.streams.UNIFORM): the
midpoints of 2**52 equal bins, so u lies in the open interval (0, 1) and -ln u is finite. It needs
JAX's partitionable Threefry (jax_threefry_partitionable, JAX's default since 0.5), under which a
key's bits do not depend on how a computation is partitioned; key_data refuses without it.

**Where each piece lives.** The seed is declared. Each site's stream key is bound host side as
layout data (key_data: two int64 words, each a uint32 value), and the counters are owned state. The
device code folds the counter into the bound key (uniforms).

The written rule is also FR-43 part 3's references spec (validation/fr43_part3/references/spec/
README.md, whose standalone make_draws.py implements it without this module).
"""

from types import MappingProxyType

import numpy as np

GENERATOR = "threefry2x32"
DOMAINS = MappingProxyType({"events": 1, "partition": 2})
FOLD_ORDER = (
    "seed",
    "site: low 32-bit word, then high word",
    "domain",
    "counter: low 32-bit word, then high word",
)
UNIFORM = (
    "u = (m + 1/2) * 2**-52, m the low 52 bits of one 64-bit Threefry word "
    "(jax.random.bits, uint64): the open interval (0, 1)"
)
WORD = 2**32


def check_seed(value, what="A stream seed"):
    """The seed, an integer in [0, 2**32) (bool refused)."""
    if type(value) is not int or not 0 <= value < WORD:
        raise ValueError(f"{what} is an integer in [0, 2**32)")
    return value


def identity(seed):
    """The streams' identity as a run records it."""
    import jax

    return {
        "generator": GENERATOR,
        "seed": check_seed(seed),
        "fold_order": list(FOLD_ORDER),
        "domains": dict(DOMAINS),
        "uniform": UNIFORM,
        "jax_threefry_partitionable": bool(jax.config.jax_threefry_partitionable),
    }


def _require_partitionable():
    import jax

    if not jax.config.jax_threefry_partitionable:
        raise ValueError(
            "The composite's streams need JAX's partitionable Threefry, and "
            "jax_threefry_partitionable is off"
        )


def _fold64(key, value):
    """key with a non-negative 64-bit integer folded in as two 32-bit words, low then high: a host
    integer, or an int64 array (traced or not)."""
    import jax
    import jax.numpy as jnp

    if isinstance(value, (int, np.integer)):
        value = int(value)
        if not 0 <= value < 2**63:
            raise ValueError(f"A folded value is a non-negative 64-bit integer, not {value}")
        low, high = np.uint32(value % WORD), np.uint32(value // WORD)
    else:
        value = jnp.asarray(value, dtype=jnp.int64)
        low = (value & jnp.int64(WORD - 1)).astype(jnp.uint32)
        high = ((value >> 32) & jnp.int64(WORD - 1)).astype(jnp.uint32)
    return jax.random.fold_in(jax.random.fold_in(key, low), high)


def key_data(seed, site, domain):
    """A site's stream for one domain as two int64 words (each a uint32 value), host side, for a
    layout: the derivation's `stream` (module docstring)."""
    import jax

    _require_partitionable()
    check_seed(seed)
    if type(site) is not int or site < 0:
        raise ValueError("A site index is a non-negative integer")
    key = jax.random.key(seed, impl=GENERATOR)
    key = _fold64(key, site)
    key = jax.random.fold_in(key, np.uint32(DOMAINS[domain]))
    return np.asarray(jax.random.key_data(key), dtype=np.uint32).astype(np.int64)


def sites_key_data(seed, count, domain):
    """key_data for sites 0 .. count - 1 at once, [count, 2] int64 (host side, one vectorized
    call: the same words as key_data per site)."""
    import jax
    import jax.numpy as jnp

    _require_partitionable()
    check_seed(seed)
    if type(count) is not int or count < 0:
        raise ValueError("A site count is a non-negative integer")
    if count == 0:
        return np.zeros((0, 2), dtype=np.int64)
    base = jax.random.key(seed, impl=GENERATOR)

    def one(site):
        key = _fold64(base, site)
        return jax.random.key_data(jax.random.fold_in(key, jnp.uint32(DOMAINS[domain])))

    words = jax.vmap(one)(jnp.arange(count, dtype=jnp.int64))
    return np.asarray(words, dtype=np.uint32).astype(np.int64)


def uniforms(words, counter, count):
    """`count` open-interval float64 uniforms: draw `counter` (int64) of the stream whose key data
    are `words` (two int64 words, as key_data gives them). Traceable; map it over sites with
    jax.vmap."""
    import jax
    import jax.numpy as jnp

    key = jax.random.wrap_key_data(jnp.asarray(words).astype(jnp.uint32), impl=GENERATOR)
    key = _fold64(key, counter)
    bits = jax.random.bits(key, shape=(count,), dtype=jnp.uint64)
    mantissa = bits & jnp.uint64((1 << 52) - 1)
    return (mantissa.astype(jnp.float64) + 0.5) * (2.0**-52)


def site_uniforms(words, counters, count):
    """uniforms over sites: words [site, 2], counters [site] -> [site, count]."""
    import jax

    return jax.vmap(lambda w, k: uniforms(w, k, count))(words, counters)
