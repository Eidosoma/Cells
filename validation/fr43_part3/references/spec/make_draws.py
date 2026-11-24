"""The draws table of FR-43 part 3's references spec (part3.json), from the written stream rule.

Standalone: it imports JAX's random primitives and nothing of the engine, so the table is the
protocol's output, not an engine value. The rule (README.md, "The random-draw protocol"):

    base    = jax.random.key(seed, impl="threefry2x32")            seed in [0, 2**32)
    site    = fold_in(fold_in(base, low32(s)), high32(s))           s: the site's declared index
    stream  = fold_in(site, domain)                                 domain: events 1, partition 2
    draw k  = fold_in(fold_in(stream, low32(k)), high32(k))         k: the draw's counter
    words   = jax.random.bits(draw k, shape=(count,), dtype=uint64)
    u       = ((words & (2**52 - 1)) + 0.5) * 2**-52                the open interval (0, 1)

Each event k of a site takes the events stream's draw k with count 2: (u1, u2) = (u[0], u[1]).
Requires JAX's partitionable Threefry (jax_threefry_partitionable, on by default since JAX 0.5).

    python make_draws.py part3.json draws.json     write the table for part3.json's worlds
    python make_draws.py part3.json draws.json --check    regenerate and compare bit for bit
"""

import argparse
import json
import sys

import jax

jax.config.update("jax_enable_x64", True)

import jax.numpy as jnp  # noqa: E402
import numpy as np  # noqa: E402

WORD = 2**32
DOMAINS = {"events": 1, "partition": 2}


def _fold64(key, value):
    value = int(value)
    if not 0 <= value < 2**63:
        raise ValueError(f"a folded value is a non-negative 64-bit integer, not {value}")
    key = jax.random.fold_in(key, np.uint32(value % WORD))
    return jax.random.fold_in(key, np.uint32(value // WORD))


def uniforms(seed, site, domain, counter, count):
    """count open-interval float64 uniforms: draw `counter` of `site`'s `domain` stream."""
    if not jax.config.jax_threefry_partitionable:
        raise SystemExit("jax_threefry_partitionable is off: the rule needs it on")
    if type(seed) is not int or not 0 <= seed < WORD:
        raise ValueError("a seed is an integer in [0, 2**32)")
    key = jax.random.key(seed, impl="threefry2x32")
    key = _fold64(key, site)
    key = jax.random.fold_in(key, np.uint32(DOMAINS[domain]))
    key = _fold64(key, counter)
    words = jax.random.bits(key, shape=(count,), dtype=jnp.uint64)
    mantissa = words & jnp.uint64((1 << 52) - 1)
    return np.asarray((mantissa.astype(jnp.float64) + 0.5) * (2.0**-52))


def table(spec):
    out = {
        "kind": "cells.fr43_part3_draws@1",
        "rule": "README.md, the random-draw protocol (make_draws.py implements it)",
        "jax_version": jax.__version__,
        "jax_threefry_partitionable": bool(jax.config.jax_threefry_partitionable),
        "worlds": {},
    }
    for world in spec["worlds"]:
        stream = world["stream"]
        rows = [
            uniforms(stream["seed"], stream["site_index"], "events", k, 2)
            for k in range(stream["events_drawn"])
        ]
        out["worlds"][world["id"]] = {
            "seed": stream["seed"],
            "site_index": stream["site_index"],
            "domain": "events",
            "u1": [float(r[0]).hex() for r in rows],
            "u2": [float(r[1]).hex() for r in rows],
        }
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spec")
    parser.add_argument("draws")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    with open(args.spec) as f:
        spec = json.load(f)
    fresh = table(spec)
    if args.check:
        with open(args.draws) as f:
            saved = json.load(f)
        same = saved["worlds"] == fresh["worlds"]
        print("draws: identical" if same else "draws: DIFFER")
        return 0 if same else 1
    with open(args.draws, "w") as f:
        json.dump(fresh, f, indent=1)
        f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
