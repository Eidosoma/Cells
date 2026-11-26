"""The draws table of FR-43 part 3's co-writer references spec (inputs.json), from the written
stream rule.

Standalone: it imports JAX's random primitives and nothing of the engine, so the table is the
protocol's output, not an engine value. The rule (LAWS.md section 6):

    base    = jax.random.key(seed, impl="threefry2x32")            seed in [0, 2**32)
    site    = fold_in(fold_in(base, low32(s)), high32(s))           s: the site's declared index (0)
    stream  = fold_in(site, domain)                                 domain: events 1
    draw k  = fold_in(fold_in(stream, low32(k)), high32(k))         k: the event's counter
    words   = jax.random.bits(draw k, shape=(2,), dtype=uint64)
    u       = ((words & (2**52 - 1)) + 0.5) * 2**-52                (u1_k, u2_k) = (u[0], u[1])

    python make_draws.py inputs.json draws.json            write the table for inputs.json's worlds
    python make_draws.py inputs.json draws.json --check    regenerate and compare bit for bit
"""

import argparse
import json
import sys

import jax

jax.config.update("jax_enable_x64", True)

import jax.numpy as jnp  # noqa: E402
import numpy as np  # noqa: E402

WORD = 2**32
EVENTS = 1


def _fold64(key, value):
    value = int(value)
    if not 0 <= value < 2**63:
        raise ValueError(f"a folded value is a non-negative 64-bit integer, not {value}")
    key = jax.random.fold_in(key, np.uint32(value % WORD))
    return jax.random.fold_in(key, np.uint32(value // WORD))


def uniforms(seed, site, count_pairs):
    """The first count_pairs (u1, u2) of a site's events stream, [count_pairs, 2] float64."""
    if not jax.config.jax_threefry_partitionable:
        raise SystemExit("jax_threefry_partitionable is off: the rule needs it on")
    if type(seed) is not int or not 0 <= seed < WORD:
        raise ValueError("a seed is an integer in [0, 2**32)")
    key = jax.random.key(seed, impl="threefry2x32")
    key = _fold64(key, site)
    stream = jax.random.fold_in(key, np.uint32(EVENTS))

    def one(k):
        draw = jax.random.fold_in(jax.random.fold_in(stream, k), jnp.uint32(0))
        return jax.random.bits(draw, shape=(2,), dtype=jnp.uint64)

    words = jax.vmap(one)(jnp.arange(count_pairs, dtype=jnp.uint32))
    mantissa = words & jnp.uint64((1 << 52) - 1)
    return np.asarray((mantissa.astype(jnp.float64) + 0.5) * (2.0**-52))


def table(spec):
    out = {
        "kind": "fr43 part 3 co-writers draws, version 1",
        "rule": "LAWS.md section 6 (make_draws.py implements it)",
        "jax_version": jax.__version__,
        "jax_threefry_partitionable": bool(jax.config.jax_threefry_partitionable),
        "worlds": {},
    }
    pairs = spec["draws"]["pairs_per_copy"]
    for name, world in spec["worlds"].items():
        rows = []
        for c, seed in enumerate(world["seeds"]):
            u = uniforms(seed, spec["draws"]["site_index"], pairs)
            rows.append(
                {
                    "copy": c,
                    "seed": seed,
                    "site_index": spec["draws"]["site_index"],
                    "domain": "events",
                    "u1": [float(x).hex() for x in u[:, 0]],
                    "u2": [float(x).hex() for x in u[:, 1]],
                }
            )
        out["worlds"][name] = {"copies": rows}
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("inputs")
    parser.add_argument("draws")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    with open(args.inputs) as f:
        spec = json.load(f)
    fresh = table(spec)
    if args.check:
        with open(args.draws) as f:
            saved = json.load(f)
        same = saved["worlds"] == fresh["worlds"]
        print("draws: identical" if same else "draws: DIFFER")
        return 0 if same else 1
    with open(args.draws, "w") as f:
        json.dump(fresh, f, indent=0, separators=(",", ":"))
        f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
