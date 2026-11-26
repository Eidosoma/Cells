"""FR-43 part 3 references: the counter-based draws, regenerated from the spec's written rule.

The rule (spec/README.md, "The random-draw protocol") derives draw k of a site's stream as

    base    = jax.random.key(seed, impl="threefry2x32")
    site    = fold_in(fold_in(base, low32(s)), high32(s))
    stream  = fold_in(site, domain)                      domain: events 1, partition 2
    draw k  = fold_in(fold_in(stream, low32(k)), high32(k))
    words   = jax.random.bits(draw k, shape=(count,), dtype=uint64)
    u       = ((words & (2**52 - 1)) + 0.5) * 2**-52

Two routes regenerate it, and both are compared bit for bit with spec/draws.json:

- ``scratch``: the Threefry-2x32 hash (20 rounds) written out here, with no JAX. The word layout
  of JAX's key derivation is spelled out: the seed's key words, fold_in's counter and the
  partitionable 64-bit bits. The bit-for-bit match on every draw decides whether it holds.
- ``jax``: this module's own calls to JAX's public random primitives (jax.random.key,
  jax.random.fold_in and jax.random.bits), under jax_threefry_partitionable.

    python stream_draws.py                       both routes; write results/draws_check.json
    python stream_draws.py --routes scratch      the scratch route only (no JAX import)
"""

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SPEC_DIR = HERE / "spec"
RESULTS_DIR = HERE / "results"

MASK32 = 0xFFFFFFFF
DOMAINS = {"events": 1, "partition": 2}
MANTISSA = (1 << 52) - 1

# Threefry-2x32: the key-schedule parity constant and the two rotation sets (Salmon et al. 2011,
# "Parallel random numbers: as easy as 1, 2, 3"; Random123's threefry.h).
_PARITY = 0x1BD11BDA
_ROTATIONS = ((13, 15, 26, 6), (17, 29, 16, 24))


def _rotl32(x, r):
    return ((x << r) | (x >> (32 - r))) & MASK32


def threefry2x32(key, counter):
    """The Threefry-2x32 block function with 20 rounds: key (k0, k1), counter (x0, x1) -> 2 words."""
    k0, k1 = key
    ks = (k0, k1, k0 ^ k1 ^ _PARITY)
    x0 = (counter[0] + ks[0]) & MASK32
    x1 = (counter[1] + ks[1]) & MASK32
    for i in range(5):
        for r in _ROTATIONS[i % 2]:
            x0 = (x0 + x1) & MASK32
            x1 = _rotl32(x1, r) ^ x0
        x0 = (x0 + ks[(i + 1) % 3]) & MASK32
        x1 = (x1 + ks[(i + 2) % 3] + i + 1) & MASK32
    return x0, x1


def _scratch_key(seed):
    """jax.random.key(seed, impl="threefry2x32"): the key words (seed >> 32, seed & 0xFFFFFFFF)."""
    return (seed >> 32) & MASK32, seed & MASK32


def _scratch_fold_in(key, word):
    """jax.random.fold_in: the hash of the counter (0, word) under the key."""
    if not 0 <= word <= MASK32:
        raise ValueError(f"fold_in takes one unsigned 32-bit word, not {word}")
    return threefry2x32(key, (0, word))


def _scratch_bits64(key, count):
    """jax.random.bits(key, (count,), uint64), partitionable: word i = hash(key, (hi(i), lo(i))),
    with the first output word as the high half."""
    out = []
    for i in range(count):
        y0, y1 = threefry2x32(key, ((i >> 32) & MASK32, i & MASK32))
        out.append((y0 << 32) | y1)
    return out


def _open_unit(word):
    """((word & (2**52 - 1)) + 0.5) * 2**-52, exact in binary64 (53 significant bits)."""
    return (float(word & MANTISSA) + 0.5) * 2.0**-52


def _check_word64(value, what):
    if type(value) is not int or not 0 <= value < 2**64:
        raise ValueError(f"{what} is a non-negative 64-bit integer, not {value!r}")


def scratch_uniforms(seed, site, domain, counter, count):
    """`count` open-interval uniforms of draw `counter` of `site`'s `domain` stream (no JAX)."""
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("a seed is an integer in [0, 2**32)")
    _check_word64(site, "a site index")
    _check_word64(counter, "a counter")
    key = _scratch_key(seed)
    for word in (site & MASK32, site >> 32, DOMAINS[domain], counter & MASK32, counter >> 32):
        key = _scratch_fold_in(key, word)
    return [_open_unit(w) for w in _scratch_bits64(key, count)]


def jax_uniforms_factory():
    """The same draws through JAX's public random primitives (imported here, on request only)."""
    import jax

    jax.config.update("jax_enable_x64", True)
    import jax.numpy as jnp
    import numpy as np

    if not jax.config.jax_threefry_partitionable:
        raise SystemExit("jax_threefry_partitionable is off: the spec's rule needs it on")

    def uniforms(seed, site, domain, counter, count):
        key = jax.random.key(seed, impl="threefry2x32")
        for word in (site & MASK32, site >> 32, DOMAINS[domain], counter & MASK32, counter >> 32):
            key = jax.random.fold_in(key, np.uint32(word))
        words = np.asarray(jax.random.bits(key, shape=(count,), dtype=jnp.uint64))
        return [_open_unit(int(w)) for w in words]

    info = {
        "jax_version": jax.__version__,
        "jax_threefry_partitionable": bool(jax.config.jax_threefry_partitionable),
    }
    return uniforms, info


def load_spec(spec_dir=SPEC_DIR):
    with open(spec_dir / "part3.json") as f:
        return json.load(f)


def load_draws(spec_dir=SPEC_DIR):
    """spec/draws.json: world id -> {"u1": [float, ...], "u2": [float, ...]} (from float.hex)."""
    with open(spec_dir / "draws.json") as f:
        table = json.load(f)
    return {
        wid: {
            "seed": row["seed"],
            "site_index": row["site_index"],
            "domain": row["domain"],
            "u1": [float.fromhex(h) for h in row["u1"]],
            "u2": [float.fromhex(h) for h in row["u2"]],
            "u1_hex": list(row["u1"]),
            "u2_hex": list(row["u2"]),
        }
        for wid, row in table["worlds"].items()
    }


def regenerate(spec, uniforms):
    """world id -> {"u1": [hex], "u2": [hex]} for every world's events stream."""
    out = {}
    for world in spec["worlds"]:
        stream = world["stream"]
        rows = [
            uniforms(stream["seed"], stream["site_index"], "events", k, 2)
            for k in range(stream["events_drawn"])
        ]
        out[world["id"]] = {
            "seed": stream["seed"],
            "site_index": stream["site_index"],
            "domain": "events",
            "u1": [r[0].hex() for r in rows],
            "u2": [r[1].hex() for r in rows],
        }
    return out


def compare(fresh, saved_table):
    """Per world: bit-for-bit identity of the regenerated hex strings with draws.json's."""
    report = {}
    for wid, row in fresh.items():
        saved = saved_table["worlds"].get(wid)
        entry = {"draws": len(row["u1"]), "identical": False, "first_mismatch": None}
        if saved is None:
            entry["first_mismatch"] = "world missing from draws.json"
        elif any(saved[key] != row[key] for key in ("seed", "site_index", "domain")):
            entry["first_mismatch"] = "stream header differs"
        elif len(saved["u1"]) != len(row["u1"]) or len(saved["u2"]) != len(row["u2"]):
            entry["first_mismatch"] = "draw count differs"
        else:
            for k, (a1, a2, b1, b2) in enumerate(zip(row["u1"], row["u2"], saved["u1"], saved["u2"])):
                if a1 != b1 or a2 != b2:
                    entry["first_mismatch"] = {"k": k, "fresh": [a1, a2], "saved": [b1, b2]}
                    break
            else:
                entry["identical"] = True
        report[wid] = entry
    extra = sorted(set(saved_table["worlds"]) - set(fresh))
    return report, extra


def premise_check(routes=("scratch", "jax"), spec_dir=SPEC_DIR):
    """Regenerate every world's draws by each route and compare with draws.json bit for bit."""
    spec = load_spec(spec_dir)
    with open(spec_dir / "draws.json") as f:
        saved = json.load(f)
    out = {
        "kind": "cells.fr43_part3_reference_draws_check@1",
        "rule": "spec/README.md, the random-draw protocol",
        "compared_as": "float.hex strings, bit for bit, u1 and u2 of every draw of every world",
        "routes": {},
    }
    for route in routes:
        if route == "scratch":
            fresh = regenerate(spec, scratch_uniforms)
            info = {"implementation": "Threefry-2x32-20 written out in this module; no JAX"}
        elif route == "jax":
            uniforms, info = jax_uniforms_factory()
            fresh = regenerate(spec, uniforms)
            info = {"implementation": "jax.random.key, fold_in and bits called by this module", **info}
        else:
            raise ValueError(f"unknown route {route!r}")
        worlds, extra = compare(fresh, saved)
        out["routes"][route] = {
            **info,
            "worlds": worlds,
            "worlds_only_in_draws_json": extra,
            "identical": all(w["identical"] for w in worlds.values()) and not extra,
        }
    out["identical"] = all(r["identical"] for r in out["routes"].values())
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--routes", default="scratch,jax", help="comma-separated: scratch, jax")
    parser.add_argument("--out", default=str(RESULTS_DIR / "draws_check.json"))
    args = parser.parse_args(argv)
    report = premise_check(tuple(r for r in args.routes.split(",") if r))
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(report, f, indent=1)
        f.write("\n")
    for route, row in report["routes"].items():
        print(f"{route}: {'identical' if row['identical'] else 'DIFFER'}")
    return 0 if report["identical"] else 1


if __name__ == "__main__":
    sys.exit(main())
