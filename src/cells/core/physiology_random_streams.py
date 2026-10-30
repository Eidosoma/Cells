"""Immutable physiological draw ownership over the qualified RNG samplers.

One logical tick spans all sites of a stream, independently of floating time
or physical effect size. Native sequential MT19937 and stable owner/world
coordinates remain different laws. This host API schedules neither physiology
nor the source-disabled microtubule diagnostic.
"""

import hashlib
import json
from dataclasses import dataclass, replace

import numpy as np

from cells.processes import betse_perturbations as perturb

KIND = "cells.physiology_random_stream@1"
MAX_TICK = 2**64 - 1
_NO_BINDING = object()
RECORD_FIELDS = {
    "kind",
    "law_id",
    "stream_id",
    "world_id",
    "next_tick",
    "layout_identity",
    "rng",
    "identity",
}


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _uint(value, bits, name):
    if type(value) is not int or not 0 <= value < 2**bits:
        raise ValueError("Require an explicit uint" + str(bits) + " " + name)


def _identity(value):
    if (
        type(value) is not str
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError("Require a complete canonical layout identity")


def _binding_identity(binding):
    if type(binding) is not perturb.Binding or type(binding.kernel) is not perturb.Kernel:
        raise ValueError("Require an explicit qualified perturbation Binding")
    for name in ("cell_ids", "membrane_ids", "environment_ids", "ion_ids"):
        ids = getattr(binding, name)
        if (
            type(ids) is not tuple
            or not 0 < len(ids) <= perturb.MAX_OWNERS
            or any(type(value) is not str or not value for value in ids)
            or len(set(ids)) != len(ids)
        ):
            raise ValueError("Invalid explicit perturbation owner axis: " + name)
    _identity(binding.identity)
    try:
        payload = dict(
            law_id=perturb.LAW_ID,
            cell_ids=binding.cell_ids,
            membrane_ids=binding.membrane_ids,
            environment_ids=binding.environment_ids,
            ion_ids=binding.ion_ids,
            boundary_occurrences=binding.boundary_cell_occurrences,
            mode=binding.environment_mode,
            provenance=json.loads(binding.provenance_json),
            kernel={key: value.tolist() for key, value in binding.kernel._asdict().items()},
        )
        same = _digest(payload) == binding.identity
    except (TypeError, AttributeError, ValueError) as error:
        raise ValueError("Invalid perturbation binding identity") from error
    if not same:
        raise ValueError("Perturbation owners/layout changed after binding")
    for owner, count in (
        (binding.kernel.owner, len(binding.cell_ids)),
        (binding.kernel.environment_owner, len(binding.environment_ids)),
    ):
        value = np.asarray(owner)
        if (
            value.shape != (len(binding.membrane_ids),)
            or value.dtype.kind not in "iu"
            or np.any(value < 0)
            or np.any(value >= count)
        ):
            raise ValueError("Invalid explicit membrane cell/environment ownership")
    return binding.identity


def _rng_record(rng, world_id):
    if type(rng) is perturb.NativeStream:
        return perturb.native_stream_manifest(rng)
    if type(rng) is perturb.StableCoordinates:
        _uint(rng.seed, 32, "seed")
        _uint(rng.world_id, 64, "stable world_id")
        if rng.world_id != world_id:
            raise ValueError("Stable coordinates belong to another world")
        return dict(rng_id=perturb.STABLE_RNG_ID, seed=rng.seed, world_id=rng.world_id)
    raise ValueError("Declare the qualified native or stable-owner RNG law")


@dataclass(frozen=True, slots=True)
class PhysiologyRandomStream:
    stream_id: str
    world_id: int
    next_tick: int
    layout_identity: str
    rng: object

    def __post_init__(self):
        if type(self.stream_id) is not str or not self.stream_id:
            raise ValueError("Require a nonempty explicit stream_id")
        _uint(self.world_id, 64, "world_id")
        _uint(self.next_tick, 64, "next_tick")
        _identity(self.layout_identity)
        _rng_record(self.rng, self.world_id)


def new_stream(binding, rng, *, stream_id, world_id, next_tick=0):
    """Declare ownership without sampling or deriving native seeds from a world.

    Native world IDs label ownership only. Callers supply independent native
    states when they need independent worlds; cloning a state replays its tape.
    """
    return PhysiologyRandomStream(stream_id, world_id, next_tick, _binding_identity(binding), rng)


def _checked(stream, binding=_NO_BINDING):
    if type(stream) is not PhysiologyRandomStream:
        raise ValueError("Require an explicit physiological random stream")
    stream.__post_init__()
    if binding is not _NO_BINDING and stream.layout_identity != _binding_identity(binding):
        raise ValueError("Stream belongs to another layout; explicitly rebind surviving owners")


def draw(stream, binding, *, site, enabled=True):
    """Draw at next_tick then increment once, regardless of vector length.

    Disabled calls return the identical stream and consume no native/cache or
    logical state. Enabled zero-effect calls must still use enabled=True. At
    MAX_TICK an enabled call refuses before sampling because incrementing would
    overflow the serialized uint64 next tick.
    """
    _checked(stream, binding)
    if site not in perturb.SITES or type(enabled) is not bool:
        raise ValueError("Require a known perturbation site and explicit enabled boolean")
    if not enabled:
        return None, stream
    if stream.next_tick == MAX_TICK:
        raise ValueError("Physiological next_tick increment would overflow uint64")
    if type(stream.rng) is perturb.NativeStream:
        packet, rng = perturb.sample_native(stream.rng, binding, site=site, tick=stream.next_tick)
    else:
        packet = perturb.sample_stable(stream.rng, binding, site=site, tick=stream.next_tick)
        rng = stream.rng
    return packet, replace(stream, next_tick=stream.next_tick + 1, rng=rng)


def stream_record(stream):
    """Return a fresh JSON record, preserving MT19937's complete Gaussian cache."""
    _checked(stream)
    payload = dict(
        kind=KIND,
        law_id=perturb.LAW_ID,
        stream_id=stream.stream_id,
        world_id=stream.world_id,
        next_tick=stream.next_tick,
        layout_identity=stream.layout_identity,
        rng=_rng_record(stream.rng, stream.world_id),
    )
    return payload | dict(identity=_digest(payload))


def restore_stream(record, binding):
    if type(record) is not dict or set(record) != RECORD_FIELDS:
        raise ValueError("Incomplete physiological stream record")
    if record["kind"] != KIND or record["law_id"] != perturb.LAW_ID:
        raise ValueError("Unsupported physiological stream kind/law")
    payload = {key: value for key, value in record.items() if key != "identity"}
    if _digest(payload) != record["identity"]:
        raise ValueError("Physiological stream record identity mismatch")
    if record["layout_identity"] != _binding_identity(binding):
        raise ValueError("Restored stream belongs to another layout")
    raw = record["rng"]
    if type(raw) is not dict:
        raise ValueError("Require a complete declared RNG record")
    if raw.get("rng_id") == perturb.NATIVE_RNG_ID:
        rng = perturb.native_stream_from_manifest(raw)
    elif raw.get("rng_id") == perturb.STABLE_RNG_ID and set(raw) == {"rng_id", "seed", "world_id"}:
        rng = perturb.StableCoordinates(raw["seed"], raw["world_id"])
    else:
        raise ValueError("Unsupported physiological RNG record")
    stream = new_stream(
        binding,
        rng,
        stream_id=record["stream_id"],
        world_id=record["world_id"],
        next_tick=record["next_tick"],
    )
    if stream_record(stream) != record:
        raise ValueError("Noncanonical or incomplete physiological stream record")
    return stream


def rebind_stream(stream, old_binding, new_binding):
    """Explicitly transfer stream coordinates to declared surviving owners.

    No owner is invented or reassigned. A caller owns physical geometry/state
    remapping. Native tapes are preserved, but a changed count/order of draws
    or boundary occurrences changes native samples; there is no native subset
    invariance claim. Stable membrane tokens keep their existing qualified law.
    """
    _checked(stream, old_binding)
    new_identity = _binding_identity(new_binding)
    for name in ("cell_ids", "membrane_ids", "environment_ids", "ion_ids"):
        if not set(getattr(new_binding, name)).issubset(getattr(old_binding, name)):
            raise ValueError("Rebinding introduced a foreign owner: " + name)
    for new_index, membrane in enumerate(new_binding.membrane_ids):
        old_index = old_binding.membrane_ids.index(membrane)
        for ids, owner in (("cell_ids", "owner"), ("environment_ids", "environment_owner")):
            before = getattr(old_binding, ids)[int(getattr(old_binding.kernel, owner)[old_index])]
            after = getattr(new_binding, ids)[int(getattr(new_binding.kernel, owner)[new_index])]
            if before != after:
                raise ValueError("Rebinding reassigned a surviving membrane owner")
    return replace(stream, layout_identity=new_identity)
