"""Owned real protein packets for the deterministic transition array contract.

Native sampling stays on the frozen NumPy host path. Stable array sampling
calls the existing owner-keyed Threefry law. Source parents remain unchanged;
proposed packets/successors survive rejection and no loop state is committed.
"""

import hashlib
from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core import physiology_perturbation_phases as phases
from cells.core import physiology_perturbation_step as step
from cells.core import physiology_random_streams as streams
from cells.core import physiology_tissue_binding as units
from cells.core.errors import NumericalError
from cells.numerics import physiology_protein_transition_arrays as transition
from cells.processes import betse_perturbations as perturb


@dataclass(frozen=True, slots=True)
class EncodedSource:
    source: object
    geometry: object
    preparation: object
    configuration: object


@dataclass(frozen=True, slots=True)
class ProvidedProteinPacket:
    parent: object
    binding: object
    encoded: EncodedSource
    packet: object
    successor_stream: object
    array_packet: object
    array_proposal: object
    diagnostics: object


class PacketProviderRejected(NumericalError):
    def __init__(
        self,
        reason,
        *,
        stage,
        parent,
        binding,
        encoded,
        packet,
        successor_stream,
        array_packet,
        array_proposal,
    ):
        super().__init__("Protein packet provider refused at " + stage + ": " + str(reason))
        self.stage, self.parent, self.binding = stage, parent, binding
        self.encoded, self.packet, self.successor_stream = encoded, packet, successor_stream
        self.array_packet, self.array_proposal = array_packet, array_proposal


class StableProvidedPacket(NamedTuple):
    valid: object
    preflight_valid: object
    packet_generated: object
    packet: object
    proposal: object
    checks: object


def _freeze(value):
    a = np.asarray(value)
    return np.frombuffer(np.ascontiguousarray(a).tobytes(), dtype=a.dtype).reshape(a.shape)


def _frozen_tree(value):
    return jax.tree.map(_freeze, value)


def _token(value, *, digest=False):
    bits = bytes.fromhex(value) if digest else hashlib.sha256(value.encode()).digest()
    return np.frombuffer(bits, dtype="<u4").astype(np.uint32)


def _stream(stream):
    record = streams.stream_record(stream)
    r = record["rng"]
    if r["rng_id"] == perturb.NATIVE_RNG_ID:
        state = r["state"]
        rng = transition.NativeRNGState(
            np.asarray(state[1], np.uint32),
            np.asarray(state[2], np.uint32),
            np.asarray(state[3], np.uint32),
            np.asarray(state[4], np.float64),
        )
    else:
        rng = transition.StableRNGState(np.asarray(r["seed"], np.uint32))
    return _frozen_tree(
        transition.ArrayStream(
            _token(stream.stream_id),
            _token(stream.layout_identity, digest=True),
            np.asarray(stream.world_id, np.uint64),
            np.asarray(stream.next_tick, np.uint64),
            rng,
        )
    )


def source_record(source):
    """Fresh complete host inputs for durable source replay, without sampling."""
    return dict(
        protein={k: np.asarray(v).tolist() for k, v in source.protein._asdict().items()},
        diffusion={k: np.asarray(v).tolist() for k, v in source.diffusion._asdict().items()},
        controls=asdict(source.controls),
        time_s=float(source.time_s),
        loop_calls=source.loop_calls,
        stream=streams.stream_record(source.stream),
    )


def encode_source(source, binding):
    """Admit/encode complete host ownership and clock/held-P preflight; no draw."""
    units.validate_binding(binding)
    step.validate_state(source, binding.component)
    preparation = phases.prepare(source, binding.component)
    c, k = source.controls, binding.component.kernel
    controls = transition.ArrayControls(
        np.asarray(("INIT", "SIM").index(c.phase), np.int32),
        np.asarray(("normal", "fast").index(c.solver), np.int32),
        np.asarray(c.dynamic_enabled),
        np.asarray(c.protein_enabled),
        np.asarray(c.static_level, np.float64),
        np.asarray(c.dynamic_level_mol_m2_s, np.float64),
        np.asarray(c.dt_s, np.float64),
    )
    arrays = transition.ArrayComponentState(
        source.protein,
        source.diffusion,
        _stream(source.stream),
        controls,
        np.asarray(source.time_s, np.float64),
        np.asarray(source.loop_calls, np.uint64),
    )
    work = transition.drive.endpoint_work.WorkGeometry(
        binding.cell_to_tissue,
        binding.environment_to_tissue,
        binding.membrane_to_tissue,
        k.cell_volume_m3,
        k.environment_effective_volume_m3,
        k.owner,
        k.environment_owner,
        k.membrane_area_m2,
    )
    geometry = transition.TransitionGeometry(
        work,
        k,
        binding.ion_to_tissue,
        binding.membrane_thickness_m,
        _token(binding.component.identity, digest=True),
    )
    native = type(source.stream.rng) is perturb.NativeStream
    configuration = MappingProxyType(
        dict(
            rng_law=perturb.NATIVE_RNG_ID if native else perturb.STABLE_RNG_ID,
            native_numpy_version=source.stream.rng.numpy_version if native else "",
            environment_mode="matrix",
        )
    )
    return EncodedSource(_frozen_tree(arrays), _frozen_tree(geometry), preparation, configuration)


def provide(source, binding):
    """Generate one real owned packet/successor; retain failed draws without commit.

    Source INIT/fast/off guards generate no packet. Enabled zero level samples
    exactly once through the same frozen sampler as every enabled call. Clock,
    source and held-diffusion failures preflight before sampling. Native states
    are restored in full; no native seed is derived from a world label.
    """
    stage, encoded, packet, array_packet, proposal = "source_preflight", None, None, None, None
    successor = getattr(source, "stream", None)
    try:
        encoded = encode_source(source, binding)
        active = perturb.dynamic_active(source.controls)
        stage = "owned_packet"
        packet, successor = streams.draw(
            source.stream, binding.component, site="protein_flux", enabled=active
        )
        stage = "packet_association"
        if packet is not None:
            perturb.draw_manifest(packet, binding.component)
            if packet.site != "protein_flux" or packet.tick != source.stream.next_tick:
                raise ValueError("Actual packet belongs to another source site/tick")
        array_packet = _frozen_tree(
            transition.SuppliedPacket(
                np.asarray(packet is not None),
                np.zeros(len(binding.component.membrane_ids), np.float64)
                if packet is None
                else packet.values,
                np.asarray(perturb.SITES.index("protein_flux"), np.int32),
                binding.component.kernel.membrane_tokens,
                encoded.source.stream,
                _stream(successor),
            )
        )
        stage = "deterministic_proposal"
        proposal = _frozen_tree(
            transition.propose(
                encoded.source,
                array_packet,
                encoded.geometry,
                **encoded.configuration,
                xp=np,
            )
        )
        if not bool(proposal.valid):
            failed = [name for name, valid in proposal.checks.items() if not bool(valid)]
            raise ValueError("Actual packet proposal fails: " + ", ".join(failed))
        diagnostics = MappingProxyType(
            dict(
                packet_generated=packet is not None,
                source_parent_unchanged=True,
                proposed_successor_only=True,
                loop_commit=False,
                rng_law=encoded.configuration["rng_law"],
                source_stream_identity=streams.stream_record(source.stream)["identity"],
                successor_stream_identity=streams.stream_record(successor)["identity"],
                packet_identity=None if packet is None else packet.identity,
                numpy_version=np.__version__,
                jax_version=jax.__version__,
                jax_threefry_partitionable=bool(jax.config.jax_threefry_partitionable),
            )
        )
        return ProvidedProteinPacket(
            source, binding, encoded, packet, successor, array_packet, proposal, diagnostics
        )
    except Exception as error:
        raise PacketProviderRejected(
            error,
            stage=stage,
            parent=source,
            binding=binding,
            encoded=encoded,
            packet=packet,
            successor_stream=successor,
            array_packet=array_packet,
            array_proposal=proposal,
        ) from error


def stable_packet_arrays(source, geometry):
    """Stage the existing stable law on admitted numeric ownership, with no commit.

    Native MT sampling is host-only. Stateless inactive lanes yield no logical
    packet and unchanged coordinates; batched compilation may evaluate masked
    counter arithmetic. Clock/tick/source preflight controls packet generation.
    Failed sampled proposals retain their real values and proposed successors.
    """
    if not jax.config.x64_enabled:
        raise ValueError("The frozen stable law requires explicit JAX x64")
    if type(source.stream.rng) is not transition.StableRNGState:
        raise ValueError("Stable array provider does not sample native MT states")
    c = source.controls
    active = (c.phase == 1) & (c.solver == 0) & c.dynamic_enabled & c.protein_enabled
    prototype_successor = source.stream._replace(
        next_tick=source.stream.next_tick + active.astype(jnp.uint64)
    )
    prototype = transition.SuppliedPacket(
        active,
        jnp.full(geometry.kernel.owner.shape, 0.5) * active,
        jnp.asarray(perturb.SITES.index("protein_flux"), jnp.int32),
        geometry.kernel.membrane_tokens,
        source.stream,
        prototype_successor,
    )
    probe = transition.propose(
        source,
        prototype,
        geometry,
        rng_law=perturb.STABLE_RNG_ID,
        native_numpy_version="",
        environment_mode="matrix",
        xp=jnp,
    )
    # Only source/clock/geometry/held-P conditions precede the draw. Protein
    # trial/precision conditions belong to the actual sampled proposal below.
    preflight = jnp.all(
        jnp.stack(
            [
                value
                for name, value in probe.checks.items()
                if not name.startswith(("protein/", "precision/"))
            ]
        )
    )
    enabled = preflight & active

    def sample(_):
        def words(value):
            return jnp.stack(
                (value.astype(jnp.uint32), (value >> jnp.uint64(32)).astype(jnp.uint32))
            )

        return perturb.stable_uniforms(
            source.stream.rng.seed,
            words(source.stream.world_id),
            words(source.stream.next_tick),
            geometry.kernel.membrane_tokens,
            site="protein_flux",
        )

    values = jax.lax.cond(
        enabled, sample, lambda _: jnp.zeros(geometry.kernel.owner.shape, jnp.float64), None
    )
    successor = source.stream._replace(
        next_tick=source.stream.next_tick + enabled.astype(jnp.uint64)
    )
    packet = transition.SuppliedPacket(
        enabled, values, prototype.site, prototype.owner_tokens, source.stream, successor
    )
    proposal = transition.propose(
        source,
        packet,
        geometry,
        rng_law=perturb.STABLE_RNG_ID,
        native_numpy_version="",
        environment_mode="matrix",
        xp=jnp,
    )
    checks = dict(source_preflight=preflight, associated_sampled_proposal=proposal.valid)
    return StableProvidedPacket(
        jnp.all(jnp.stack(tuple(checks.values()))), preflight, enabled, packet, proposal, checks
    )
