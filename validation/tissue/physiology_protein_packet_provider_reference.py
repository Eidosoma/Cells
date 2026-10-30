"""Independent MT19937 uniform replay and owner-keyed Threefry2x32 arithmetic.

Pure stdlib RNG transforms; no Cells/JAX/NumPy RNG engine. Complete native
words/cache and configured stable bit-layout semantics are explicit inputs.
This replays supplied owned sources, not a stochastic thermodynamic law.
"""

import hashlib
import json
import math
import struct
from copy import deepcopy

from validation.tissue import physiology_protein_transition_arrays_reference as transition

NATIVE = "numpy_mt19937_legacy_state_with_gaussian_cache@1"
STABLE = "threefry2x32_seed_world64_tick64_owner_sha256_site_open52_boxmuller@1"
MASK = 2**32 - 1


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _mt_uniforms(state, count):
    algorithm, words, position, has_gauss, cached = deepcopy(state)
    if algorithm != "MT19937" or len(words) != 624 or not 0 <= position <= 624:
        raise ValueError("Independent complete native state required")

    def word():
        nonlocal position
        if position >= 624:
            # In-place wraparound matches MT's second twist segment and tail.
            for i in range(624):
                y = (words[i] & 0x80000000) | (words[(i + 1) % 624] & 0x7FFFFFFF)
                words[i] = (words[(i + 397) % 624] ^ (y >> 1) ^ (0x9908B0DF if y & 1 else 0)) & MASK
            position = 0
        y = words[position]
        position += 1
        y ^= y >> 11
        y ^= (y << 7) & 0x9D2C5680
        y ^= (y << 15) & 0xEFC60000
        y ^= y >> 18
        return y & MASK

    result = []
    for _ in range(count):
        a, b = word() >> 5, word() >> 6
        result.append((a * 67108864.0 + b) * 2.0**-53)
    return result, [algorithm, words, position, has_gauss, cached]


def _threefry(key, counter):
    k = (key[0], key[1], key[0] ^ key[1] ^ 0x1BD11BDA)
    x, y = (counter[i] + k[i] for i in range(2))
    x, y = x & MASK, y & MASK
    rotations = (13, 15, 26, 6, 17, 29, 16, 24)
    for i in range(20):
        x = (x + y) & MASK
        r = rotations[i % 8]
        y = (((y << r) | (y >> (32 - r))) & MASK) ^ x
        if i % 4 == 3:
            injection = (i + 1) // 4
            x = (x + k[injection % 3]) & MASK
            y = (y + k[(injection + 1) % 3] + injection) & MASK
    return x, y


def _stable_uniforms(seed, world, tick, owners, partitionable):
    key = (0, seed)
    for value in (0xB14C0001, 2, world & MASK, world >> 32, tick & MASK, tick >> 32):
        key = _threefry(key, (0, value))
    result = []
    for owner in owners:
        current = key
        words = struct.unpack("<8I", hashlib.sha256(("membrane\0" + owner).encode()).digest())
        for value in words:
            current = _threefry(current, (0, value))
        # Frozen sampler asks for two uint64 pairs and uses the first one.
        # Partitionable counter0=(0,0); original packed layout pairs0=(0,2).
        hi, lo = _threefry(current, (0, 0 if partitionable else 2))
        bits = (hi << 32) | lo
        result.append(((bits & (2**52 - 1)) + 0.5) * 2.0**-52)
    return result


def _words(value, *, digest_string=False):
    raw = bytes.fromhex(value) if digest_string else hashlib.sha256(value.encode()).digest()
    return list(struct.unpack("<8I", raw))


def _numeric_stream(record):
    r = record["rng"]
    rng = (
        dict(
            words=r["state"][1],
            position=r["state"][2],
            has_gauss=r["state"][3],
            cached_gaussian=r["state"][4],
        )
        if r["rng_id"] == NATIVE
        else dict(seed=r["seed"])
    )
    return dict(
        stream_identity=_words(record["stream_id"]),
        layout_identity=_words(record["layout_identity"], digest_string=True),
        world_id=record["world_id"],
        next_tick=record["next_tick"],
        rng=rng,
    )


def provide(binding, source, *, threefry_partitionable):
    c, stream = source["controls"], source["stream"]
    active = (
        c["phase"] == "SIM"
        and c["solver"] == "normal"
        and c["dynamic_enabled"]
        and c["protein_enabled"]
    )
    if (
        source["loop_calls"] == 2**64 - 1
        or not math.isfinite(source["time_s"] + c["dt_s"])
        or source["time_s"] + c["dt_s"] <= source["time_s"]
    ):
        raise ValueError("Independent source clock cannot advance")
    if active and stream["next_tick"] == 2**64 - 1:
        raise ValueError("Independent active logical tick overflows")
    successor, packet = deepcopy(stream), None
    owners = binding["inputs"]["membrane_ids"]
    if active:
        r = stream["rng"]
        if r["rng_id"] == NATIVE:
            values, state = _mt_uniforms(r["state"], len(owners))
            payload = dict(rng_id=NATIVE, numpy_version=r["numpy_version"], state=state)
            successor["rng"] = payload | dict(identity=digest(payload))
            provenance = dict(
                rng_id=NATIVE,
                before_identity=r["identity"],
                after_identity=successor["rng"]["identity"],
                numpy_version=r["numpy_version"],
            )
        elif r["rng_id"] == STABLE:
            values = _stable_uniforms(
                r["seed"], stream["world_id"], stream["next_tick"], owners, threefry_partitionable
            )
            provenance = dict(
                rng_id=STABLE,
                seed=r["seed"],
                world_id=stream["world_id"],
                tick=stream["next_tick"],
                implementation="threefry2x32",
                owner_digest="sha256-domain-NUL-id/little-endian-u32x8",
                boundary_order="Canonical unique ID order with native occurrence multiplicities",
            )
        else:
            raise ValueError("Independent exact native/stable law required")
        payload = dict(
            site="protein_flux",
            tick=stream["next_tick"],
            layout_identity=binding["component_identity"],
            owner_ids=owners,
            values=values,
            provenance=provenance,
        )
        packet = payload | dict(identity=digest(payload))
        successor["next_tick"] += 1
        successor["identity"] = digest(
            {key: value for key, value in successor.items() if key != "identity"}
        )
    numeric = dict(
        protein=deepcopy(source["protein"]),
        diffusion=deepcopy(source["diffusion"]),
        stream=_numeric_stream(stream),
        time_s=source["time_s"],
        loop_calls=source["loop_calls"],
        controls=dict(
            phase=("INIT", "SIM").index(c["phase"]),
            solver=("normal", "fast").index(c["solver"]),
            dynamic_enabled=c["dynamic_enabled"],
            protein_enabled=c["protein_enabled"],
            static_level=c["static_level"],
            dynamic_level_mol_m2_s=c["dynamic_level_mol_m2_s"],
            dt_s=c["dt_s"],
        ),
    )
    array_packet = dict(
        present=active,
        values=[0.0] * len(owners) if packet is None else packet["values"],
        site=1,
        owner_tokens=[_words("membrane\0" + owner) for owner in owners],
        source_stream=numeric["stream"],
        successor_stream=_numeric_stream(successor),
    )
    proposal = transition.propose(binding, numeric, array_packet)
    return dict(
        active=active,
        packet=packet,
        successor_stream=successor,
        array_source=numeric,
        array_packet=array_packet,
        proposal=proposal,
        independent_RNG_engine=True,
        loop_commit=False,
    )
