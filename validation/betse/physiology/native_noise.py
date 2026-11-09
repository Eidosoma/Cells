"""BETSE-order random-number replay for the physiology stack (validation side only).

Wraps the engine's physiological noise law with the BETSE sequential NumPy
MT19937 stream, including its Gaussian cache, so the BETSE-loop reproduction can
replay a reference run's draws. The engine itself only takes prescribed draws
or stable-owner Threefry sampling. Everything else is re-exported unchanged.
"""

import json
from dataclasses import dataclass

import numpy as np

from cells.processes import physiological_noise as _noise

globals().update({k: v for k, v in vars(_noise).items() if not k.startswith("__")})
from cells.processes.physiological_noise import (  # noqa: E402
    _hash,
    _number,
    _uint,
    prescribed_draw,
)

NATIVE_RNG_ID = "numpy_mt19937_legacy_state_with_gaussian_cache@1"


@dataclass(frozen=True)
class NativeStream:
    state_json: str
    numpy_version: str
    identity: str


def _native_stream(state, version):
    if version != np.__version__:
        raise ValueError("Native replay requires the recorded NumPy version")
    if not isinstance(state, (tuple, list)) or len(state) != 5 or state[0] != "MT19937":
        raise ValueError("Require complete MT19937 algorithm/words/position/Gaussian cache state")
    algorithm, words, position, cached, gaussian = state
    if (
        not isinstance(words, (tuple, list, np.ndarray))
        or len(words) != 624
        or not any(words)
        or any(
            not isinstance(v, (int, np.integer))
            or isinstance(v, (bool, np.bool_))
            or not 0 <= int(v) < 2**32
            for v in words
        )
        or type(position) is not int
        or not 0 <= position <= 624
        or type(cached) is not int
        or cached not in (0, 1)
        or not _number(gaussian)
    ):
        raise ValueError("Invalid native MT19937 state, including Gaussian cache")
    normalized = [algorithm, [int(v) for v in words], position, cached, float(gaussian)]
    payload = dict(rng_id=NATIVE_RNG_ID, numpy_version=version, state=normalized)
    return NativeStream(json.dumps(normalized, separators=(",", ":")), version, _hash(payload))


def native_stream(seed):
    _uint(seed, 32)
    rng = np.random.RandomState(seed)
    state = rng.get_state()
    return _native_stream(
        [state[0], state[1].tolist(), int(state[2]), int(state[3]), float(state[4])], np.__version__
    )


def native_stream_manifest(stream):
    expected = _native_stream(json.loads(stream.state_json), stream.numpy_version)
    if expected != stream:
        raise ValueError("Stale native RNG identity")
    return dict(
        rng_id=NATIVE_RNG_ID,
        numpy_version=stream.numpy_version,
        state=json.loads(stream.state_json),
        identity=stream.identity,
    )


def native_stream_from_manifest(record):
    if (
        set(record) != {"rng_id", "numpy_version", "state", "identity"}
        or record["rng_id"] != NATIVE_RNG_ID
    ):
        raise ValueError("Unsupported/incomplete native replay state")
    stream = _native_stream(record["state"], record["numpy_version"])
    if stream.identity != record["identity"]:
        raise ValueError("Native RNG state identity mismatch")
    return stream


def sample_native(stream, binding, *, site, tick):
    manifest = native_stream_manifest(stream)
    rng = np.random.RandomState(0)
    state = manifest["state"]
    rng.set_state((state[0], np.asarray(state[1], np.uint32), state[2], state[3], state[4]))
    provenance = dict(
        rng_id=NATIVE_RNG_ID, before_identity=stream.identity, numpy_version=np.__version__
    )
    if site == "boundary_choice":
        at = int(rng.choice(len(binding.boundary_cell_occurrences)))
        value = np.asarray([binding.cell_ids.index(binding.boundary_cell_occurrences[at])], int)
        provenance["source_occurrence_index"] = at
    elif site == "microtubule_gaussian":
        value = rng.normal(loc=0.0, scale=1.0, size=len(binding.membrane_ids))
    elif site in ("static_K", "protein_flux"):
        value = rng.random(len(binding.membrane_ids))
    else:
        raise ValueError("Unsupported native perturbation RNG site")
    after = rng.get_state()
    next_stream = _native_stream(
        [after[0], after[1].tolist(), int(after[2]), int(after[3]), float(after[4])], np.__version__
    )
    provenance["after_identity"] = next_stream.identity
    return prescribed_draw(site, tick, value, binding, provenance=provenance), next_stream


def replay_record(binding, controls, replay):
    if isinstance(replay.rng, NativeStream):
        return _noise.replay_record(
            binding, controls, replay, rng_manifest=native_stream_manifest(replay.rng)
        )
    return _noise.replay_record(binding, controls, replay)


def restore_replay(record, binding, controls):
    def restore(raw):
        if raw.get("rng_id") != NATIVE_RNG_ID:
            raise ValueError("Unsupported replay RNG law")
        return native_stream_from_manifest(raw)

    return _noise.restore_replay(record, binding, controls, restore_rng=restore)
