"""Pinned physiological noise arithmetic and explicit, separately named RNG laws.

Native replay uses a local NumPy MT19937 state including its Gaussian cache;
it never changes the process-global RNG. Cells stable-owner Threefry sampling
is a distinct law. Geometry, phase scheduling and full physiology are external.
"""

import hashlib
import json
from dataclasses import asdict, dataclass
from numbers import Real
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

LAW_ID = "betse_perturbations_source_v1_5_0@1"
NATIVE_RNG_ID = "numpy_mt19937_legacy_state_with_gaussian_cache@1"
STABLE_RNG_ID = "threefry2x32_seed_world64_tick64_owner_sha256_site_open52_boxmuller@1"
SITES = ("static_K", "protein_flux", "boundary_choice", "microtubule_gaussian")
MAX_OWNERS = 4096


def _freeze(value, dtype=None):
    result = np.array(value, dtype=dtype, copy=True)
    result.setflags(write=False)
    return result


def _hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _number(value):
    return (
        isinstance(value, Real) and not isinstance(value, (bool, np.bool_)) and np.isfinite(value)
    )


def _uint(value, bits):
    if type(value) is not int or not 0 <= value < 2**bits:
        raise ValueError("Require explicit bounded unsigned integer seed/world/tick")
    return value


def _ids(values):
    if (
        not isinstance(values, (tuple, list))
        or not values
        or len(values) > MAX_OWNERS
        or any(not isinstance(v, str) or not v for v in values)
        or len(set(values)) != len(values)
    ):
        raise ValueError("Require a bounded nonempty unique stable owner axis")
    return tuple(values)


def _field(value, count, *, xp):
    result = xp.asarray(value)
    if result.ndim < 1 or result.shape[-1] != count or result.dtype.kind not in "fiu":
        raise ValueError("Require the explicit numeric final owner axis")
    return result


def _scalar_field(value, *, xp):
    result = xp.asarray(value)
    if result.dtype.kind not in "fiu":
        raise ValueError("Require numeric world-scalar controls")
    return result


def _mat(matrix, value, *, xp):
    return xp.einsum("ij,...j->...i", xp.asarray(matrix), _field(value, matrix.shape[-1], xp=xp))


def owner_tokens(ids, *, domain):
    if domain not in ("cell", "membrane", "categorical"):
        raise ValueError("Declare stable RNG owner domain")
    values = _ids(ids)
    result = []
    for value in values:
        digest = hashlib.sha256((domain + "\0" + value).encode()).digest()
        result.append([int.from_bytes(digest[i : i + 4], "little") for i in range(0, 32, 4)])
    if len({tuple(row) for row in result}) != len(result):
        raise ValueError("Owner digest collision")
    return _freeze(result, np.uint32)


@dataclass(frozen=True)
class Layout:
    cell_ids: tuple
    membrane_ids: tuple
    environment_ids: tuple
    ion_ids: tuple
    membrane_cell_ids: tuple
    membrane_environment_ids: tuple
    boundary_cell_occurrences: tuple  # Ordered, duplicates carry native weights.
    membrane_area_m2: object
    cell_volume_m3: object
    environment_parameter_volume_m3: float
    environment_mode: str  # matrix, source_fast, mixed_bath.
    provenance: dict


class Kernel(NamedTuple):
    owner: object
    environment_owner: object
    membrane_area_m2: object
    cell_volume_m3: object
    environment_effective_volume_m3: object
    cell_surface_map: object
    environment_surface_map: object
    boundary_categories: object
    boundary_cumulative_weights: object
    membrane_tokens: object


@dataclass(frozen=True)
class Binding:
    cell_ids: tuple
    membrane_ids: tuple
    environment_ids: tuple
    ion_ids: tuple
    boundary_cell_occurrences: tuple
    environment_mode: str
    kernel: Kernel
    provenance_json: str
    identity: str


def bind_layout(layout):
    cells, membranes, environments, ions = (
        _ids(v)
        for v in (layout.cell_ids, layout.membrane_ids, layout.environment_ids, layout.ion_ids)
    )
    owner_ids, env_ids = tuple(layout.membrane_cell_ids), tuple(layout.membrane_environment_ids)
    if (
        len(owner_ids) != len(membranes)
        or len(env_ids) != len(membranes)
        or any(v not in cells for v in owner_ids)
        or any(v not in environments for v in env_ids)
    ):
        raise ValueError("Explicit cell/environment membrane ownership required")
    owner = np.asarray([cells.index(v) for v in owner_ids], int)
    outside = np.asarray([environments.index(v) for v in env_ids], int)
    area = np.asarray(layout.membrane_area_m2)
    volume = np.asarray(layout.cell_volume_m3)
    if (
        area.shape != (len(membranes),)
        or volume.shape != (len(cells),)
        or any(
            v.dtype.kind not in "fiu" or not np.isfinite(v).all() or np.any(v <= 0)
            for v in (area, volume)
        )
    ):
        raise ValueError("Require finite positive membrane areas and cell volumes")
    if (
        not _number(layout.environment_parameter_volume_m3)
        or layout.environment_parameter_volume_m3 <= 0
    ):
        raise ValueError("Require positive explicit source environment volume parameter")
    mode = layout.environment_mode
    if (
        mode not in ("matrix", "source_fast", "mixed_bath")
        or mode == "mixed_bath"
        and len(environments) != 1
    ):
        raise ValueError("Declare ECM matrix/source_fast or one mixed_bath owner")
    boundary = tuple(layout.boundary_cell_occurrences)
    if not boundary or len(boundary) > MAX_OWNERS or any(v not in cells for v in boundary):
        raise ValueError("Boundary choices require an explicit nonempty occurrence list")
    canonical = tuple(sorted(set(boundary)))
    categories = np.asarray([cells.index(v) for v in canonical], int)
    cumulative = np.cumsum([boundary.count(v) for v in canonical], dtype=np.int64)
    cell_map = np.zeros((len(cells), len(membranes)))
    cell_map[owner, np.arange(len(membranes))] = area
    if np.any(np.sum(cell_map, axis=1) == 0):
        raise ValueError("Every declared cell needs an owned membrane")
    env_map = np.zeros((len(environments), len(membranes)))
    for site in range(len(environments)):
        positions = np.flatnonzero(outside == site)
        if mode == "source_fast" and positions.size:
            env_map[site, positions[-1]] = np.sum(area[positions])
        else:
            env_map[site, positions] = area[positions]
    effective = np.full(len(environments), layout.environment_parameter_volume_m3, dtype=float)
    if mode == "mixed_bath":
        effective *= len(membranes)
    if not isinstance(layout.provenance, dict) or not layout.provenance:
        raise ValueError("Explicit geometry/source provenance is required")
    provenance = json.dumps(
        layout.provenance, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    kernel = Kernel(
        *(
            _freeze(v)
            for v in (
                owner,
                outside,
                area,
                volume,
                effective,
                cell_map,
                env_map,
                categories,
                cumulative,
                owner_tokens(membranes, domain="membrane"),
            )
        )
    )
    payload = dict(
        law_id=LAW_ID,
        cell_ids=cells,
        membrane_ids=membranes,
        environment_ids=environments,
        ion_ids=ions,
        boundary_occurrences=boundary,
        mode=mode,
        provenance=json.loads(provenance),
        kernel={key: value.tolist() for key, value in kernel._asdict().items()},
    )
    return Binding(
        cells, membranes, environments, ions, boundary, mode, kernel, provenance, _hash(payload)
    )


@dataclass(frozen=True)
class Controls:
    phase: str
    solver: str
    dynamic_enabled: bool
    protein_enabled: bool
    static_level: float
    dynamic_level_mol_m2_s: float
    dt_s: float


def validate_controls(controls):
    if (
        controls.phase not in ("INIT", "SIM")
        or controls.solver not in ("normal", "fast")
        or type(controls.dynamic_enabled) is not bool
        or type(controls.protein_enabled) is not bool
    ):
        raise ValueError("Require explicit phase/solver and boolean source guards")
    if (
        not all(
            _number(v)
            for v in (controls.static_level, controls.dynamic_level_mol_m2_s, controls.dt_s)
        )
        or controls.dt_s <= 0
    ):
        raise ValueError("Require finite signed source levels and positive dt in seconds")
    return Controls(
        controls.phase,
        controls.solver,
        controls.dynamic_enabled,
        controls.protein_enabled,
        float(controls.static_level),
        float(controls.dynamic_level_mol_m2_s),
        float(controls.dt_s),
    )


def dynamic_active(controls):
    validate_controls(controls)
    return (
        controls.phase == "SIM"
        and controls.solver == "normal"
        and controls.dynamic_enabled
        and controls.protein_enabled
    )


class StaticState(NamedTuple):
    current_m2_s: object
    base_m2_s: object
    scheduled_m2_s: object


def static_initialize(initial_m2_s, uniforms, level, binding, *, xp=jnp):
    if "K" not in binding.ion_ids:
        raise ValueError("Native static noise requires the potassium index even at zero level")
    initial = xp.asarray(initial_m2_s)
    if (
        initial.ndim < 2
        or initial.shape[-2:] != (len(binding.ion_ids), len(binding.membrane_ids))
        or initial.dtype.kind not in "fiu"
    ):
        raise ValueError("Static permeability requires [...,ion,membrane] axes")
    u = _field(uniforms, len(binding.membrane_ids), xp=xp)
    amplitude = _scalar_field(level, xp=xp)
    factor = 1 + amplitude[..., None] * u
    row = xp.arange(len(binding.ion_ids)) == binding.ion_ids.index("K")
    result = initial * xp.where(row[:, None], factor[..., None, :], 1.0)
    base = xp.broadcast_to(initial, result.shape)
    if xp is np:
        base = np.array(base, copy=True)
    return StaticState(result, base, xp.zeros_like(base))


def finalize_scheduled(state, *, xp=jnp):
    values = [xp.asarray(v) for v in state]
    if any(v.shape != values[0].shape or v.dtype.kind not in "fiu" for v in values):
        raise ValueError("Permeability buffers require identical explicit axes")
    return StaticState(values[1] + values[2], values[1], values[2])


def static_domain_valid(initial_m2_s, uniforms, level, binding, *, xp=jnp):
    try:
        result = static_initialize(initial_m2_s, uniforms, level, binding, xp=xp)
        u = xp.asarray(uniforms)
        return (
            xp.all(xp.isfinite(initial_m2_s))
            & xp.all(xp.asarray(initial_m2_s) >= 0)
            & xp.all((u >= 0) & (u < 1))
            & xp.all(xp.isfinite(level))
            & xp.all(xp.isfinite(result.current_m2_s))
            & xp.all(result.current_m2_s >= 0)
        )
    except (ValueError, TypeError, IndexError):
        return xp.asarray(False)


class ProteinState(NamedTuple):
    cell_mol_m3: object
    membrane_mol_m3: object
    environment_mol_m3: object


class ProteinResult(NamedTuple):
    state: ProteinState
    flux_mol_m2_s: object
    cell_amount_change_mol: object
    environment_amount_change_mol: object
    balance_residual_mol: object


def protein_step(state, uniforms, level_mol_m2_s, dt_s, binding, *, enabled=True, xp=jnp):
    k = binding.kernel
    cell, membrane, environment = (
        _field(v, len(ids), xp=xp)
        for v, ids in zip(
            state, (binding.cell_ids, binding.membrane_ids, binding.environment_ids), strict=True
        )
    )
    u = _field(uniforms, len(binding.membrane_ids), xp=xp)
    level, dt = (_scalar_field(v, xp=xp) for v in (level_mol_m2_s, dt_s))
    active = xp.asarray(enabled)
    if active.dtype.kind != "b":
        raise ValueError("Noise activity needs explicit boolean worlds")
    flux = xp.where(active[..., None], level[..., None] * (u - 0.5), 0.0)
    cell_amount = _mat(k.cell_surface_map, flux, xp=xp) * dt[..., None]
    env_amount = -_mat(k.environment_surface_map, flux, xp=xp) * dt[..., None]
    new_cell = cell + cell_amount / xp.asarray(k.cell_volume_m3)
    new_mem = xp.take(new_cell, xp.asarray(k.owner), axis=-1)
    new_env = environment + env_amount / xp.asarray(k.environment_effective_volume_m3)
    current = ProteinState(new_cell, xp.where(active[..., None], new_mem, membrane), new_env)
    return ProteinResult(
        current,
        flux,
        cell_amount,
        env_amount,
        xp.sum(cell_amount, axis=-1) + xp.sum(env_amount, axis=-1),
    )


def protein_domain_valid(
    state,
    uniforms,
    level_mol_m2_s,
    dt_s,
    binding,
    *,
    enabled=True,
    conservation_required=True,
    xp=jnp,
):
    try:
        if type(conservation_required) is not bool:
            return xp.asarray(False)
        result = protein_step(
            state, uniforms, level_mol_m2_s, dt_s, binding, enabled=enabled, xp=xp
        )
        u = xp.asarray(uniforms)
        dt = xp.asarray(dt_s)
        valid = (
            xp.all(xp.isfinite(level_mol_m2_s))
            & xp.all(xp.isfinite(dt))
            & xp.all(dt > 0)
            & xp.all((u >= 0) & (u < 1))
        )
        valid &= xp.all(
            xp.stack(
                [
                    xp.all(xp.isfinite(v)) & xp.all(xp.asarray(v) >= 0)
                    for v in (*state, *result.state)
                ]
            )
        )
        if conservation_required:
            scale = xp.sum(xp.abs(result.cell_amount_change_mol), axis=-1) + xp.sum(
                xp.abs(result.environment_amount_change_mol), axis=-1
            )
            valid &= xp.all(xp.abs(result.balance_residual_mol) <= 3e-13 * scale)
        return valid
    except (ValueError, TypeError, IndexError):
        return xp.asarray(False)


def boundary_mask(chosen_cell_index, binding, *, domain, offset=0.0, xp=jnp):
    if domain not in ("cell", "membrane"):
        raise ValueError("Declare cell or membrane modulator ownership")
    chosen = xp.asarray(chosen_cell_index)
    if chosen.dtype.kind not in "iu":
        raise ValueError("Choice requires an explicit cell-owner index")
    if xp is np and np.any((chosen < 0) | (chosen >= len(binding.cell_ids))):
        raise ValueError("Invalid chosen boundary cell owner")
    values = (xp.arange(len(binding.cell_ids)) == chosen[..., None]).astype(float) + _scalar_field(
        offset, xp=xp
    )[..., None]
    return (
        values if domain == "cell" else xp.take(values, xp.asarray(binding.kernel.owner), axis=-1)
    )


def stable_boundary_index(uniform, binding, *, xp=jnp):
    u = _scalar_field(uniform, xp=xp)
    k = binding.kernel
    at = xp.sum(
        u[..., None] * len(binding.boundary_cell_occurrences)
        >= xp.asarray(k.boundary_cumulative_weights),
        axis=-1,
    )
    return xp.take(
        xp.asarray(k.boundary_categories), xp.minimum(at, len(k.boundary_categories) - 1)
    )


def micro_noise_scale(
    correlation_x,
    correlation_y,
    length_m,
    drag_native,
    kb,
    temperature,
    sim_temperature,
    dt_s,
    dilation,
    binding,
    *,
    diagnostic,
    xp=jnp,
):
    """Literal source numeric scale; mixed units prohibit a physical Brownian claim."""
    if diagnostic is not True:
        raise ValueError("Microtubule path is disabled; explicitly request a source diagnostic")
    ux, uy = (_field(v, len(binding.cell_ids), xp=xp) for v in (correlation_x, correlation_y))
    length, drag = (_field(v, len(binding.membrane_ids), xp=xp) for v in (length_m, drag_native))
    k, t, st, dt, di = (
        _scalar_field(v, xp=xp) for v in (kb, temperature, sim_temperature, dt_s, dilation)
    )
    correlation = (
        xp.take(xp.sqrt(ux**2 + uy**2), xp.asarray(binding.kernel.owner), axis=-1)
        + (k * st)[..., None]
    )
    return xp.sqrt(2 * (dt * di)[..., None] * ((k * t)[..., None] / drag) * correlation * length**2)


def micro_angle_step(
    theta,
    drift_source_per_s,
    modulator,
    scale,
    standard_normal,
    dt_s,
    dilation,
    binding,
    *,
    diagnostic,
    xp=jnp,
):
    if diagnostic is not True:
        raise ValueError("Microtubule path remains source-disabled")
    values = [
        _field(v, len(binding.membrane_ids), xp=xp)
        for v in (theta, drift_source_per_s, modulator, scale, standard_normal)
    ]
    angle, drift, mod, sd, z = values
    dt, di = (_scalar_field(v, xp=xp) for v in (dt_s, dilation))
    return xp.where((di > 0)[..., None], angle + drift * (dt * di)[..., None] * mod + sd * z, angle)


def micro_domain_valid(
    correlation_x,
    correlation_y,
    length_m,
    drag_native,
    kb,
    temperature,
    sim_temperature,
    dt_s,
    dilation,
    binding,
    *,
    xp=jnp,
):
    try:
        scale = micro_noise_scale(
            correlation_x,
            correlation_y,
            length_m,
            drag_native,
            kb,
            temperature,
            sim_temperature,
            dt_s,
            dilation,
            binding,
            diagnostic=True,
            xp=xp,
        )
        values = (
            correlation_x,
            correlation_y,
            length_m,
            drag_native,
            kb,
            temperature,
            sim_temperature,
            dt_s,
            dilation,
            scale,
        )
        return (
            xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in values]))
            & xp.all(xp.asarray(length_m) > 0)
            & xp.all(xp.asarray(drag_native) > 0)
            & xp.all(xp.asarray(kb) > 0)
            & xp.all(xp.asarray(temperature) > 0)
            & xp.all(xp.asarray(sim_temperature) > 0)
            & xp.all(xp.asarray(dt_s) > 0)
            & xp.all(xp.asarray(dilation) >= 0)
        )
    except (ValueError, TypeError, IndexError):
        return xp.asarray(False)


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


@dataclass(frozen=True)
class StableCoordinates:
    seed: int
    world_id: int


def words64(value):
    _uint(value, 64)
    return _freeze([value & 0xFFFFFFFF, value >> 32], np.uint32)


def stable_pairs(seed, world_words, tick_words, tokens, *, site):
    """CPU JAX stateless identity pairs; distinct from NumPy native RNG order."""
    if site not in SITES or not jax.config.x64_enabled:
        raise ValueError("Require known RNG site and JAX x64")
    world, tick, owner = (jnp.asarray(v) for v in (world_words, tick_words, tokens))
    if (
        world.shape != (2,)
        or tick.shape != (2,)
        or owner.ndim != 2
        or owner.shape[-1] != 8
        or any(v.dtype != jnp.uint32 for v in (world, tick, owner))
    ):
        raise ValueError("Require world/tick uint64 words and SHA256 owner-word axes")
    key = jax.random.key(seed, impl="threefry2x32")
    for word in (0xB14C0001, SITES.index(site) + 1, world[0], world[1], tick[0], tick[1]):
        key = jax.random.fold_in(key, word)

    def one(words):
        current = key
        for i in range(8):
            current = jax.random.fold_in(current, words[i])
        bits = jax.random.bits(current, shape=(2,), dtype=jnp.uint64)
        return ((bits & jnp.uint64((1 << 52) - 1)).astype(jnp.float64) + 0.5) * 2.0**-52

    return jax.vmap(one)(owner)


def stable_uniforms(seed, world_words, tick_words, tokens, *, site):
    return stable_pairs(seed, world_words, tick_words, tokens, site=site)[..., 0]


def stable_normals(seed, world_words, tick_words, tokens, *, site="microtubule_gaussian"):
    pairs = stable_pairs(seed, world_words, tick_words, tokens, site=site)
    return jnp.sqrt(-2 * jnp.log(pairs[..., 0])) * jnp.cos(2 * jnp.pi * pairs[..., 1])


@dataclass(frozen=True)
class Draw:
    site: str
    tick: int
    layout_identity: str
    owner_ids: tuple
    values: object
    provenance_json: str
    identity: str


def prescribed_draw(site, tick, values, binding, *, provenance):
    if site not in SITES:
        raise ValueError("Unknown perturbation RNG site")
    _uint(tick, 64)
    value = np.asarray(values)
    if site == "boundary_choice":
        if (
            value.shape != (1,)
            or value.dtype.kind not in "iu"
            or not 0 <= int(value[0]) < len(binding.cell_ids)
        ):
            raise ValueError("Choice draw requires one explicit cell-owner index")
        owner = (binding.cell_ids[int(value[0])],)
        if owner[0] not in binding.boundary_cell_occurrences:
            raise ValueError("Selected owner is not in boundary occurrences")
    else:
        if (
            value.shape != (len(binding.membrane_ids),)
            or value.dtype.kind not in "fiu"
            or not np.isfinite(value).all()
        ):
            raise ValueError("Draw requires one finite value per ordered membrane owner")
        if site in ("static_K", "protein_flux") and (np.any(value < 0) or np.any(value >= 1)):
            raise ValueError("Uniform draw must be in native [0,1) support")
        owner = binding.membrane_ids
    if not isinstance(provenance, dict) or not provenance:
        raise ValueError("Draw RNG/provenance must be explicit")
    source = json.dumps(provenance, sort_keys=True, separators=(",", ":"), allow_nan=False)
    payload = dict(
        site=site,
        tick=tick,
        layout_identity=binding.identity,
        owner_ids=owner,
        values=value.tolist(),
        provenance=json.loads(source),
    )
    return Draw(site, tick, binding.identity, owner, _freeze(value), source, _hash(payload))


def draw_manifest(draw, binding):
    expected = prescribed_draw(
        draw.site, draw.tick, draw.values, binding, provenance=json.loads(draw.provenance_json)
    )
    if (
        draw.identity != expected.identity
        or draw.layout_identity != binding.identity
        or draw.owner_ids != expected.owner_ids
    ):
        raise ValueError("Stale draw site/tick/owner/layout identity")
    return dict(
        site=draw.site,
        tick=draw.tick,
        layout_identity=draw.layout_identity,
        owner_ids=list(draw.owner_ids),
        values=draw.values.tolist(),
        provenance=json.loads(draw.provenance_json),
        identity=draw.identity,
    )


def draw_from_manifest(record, binding):
    if set(record) != {
        "site",
        "tick",
        "layout_identity",
        "owner_ids",
        "values",
        "provenance",
        "identity",
    }:
        raise ValueError("Incomplete draw manifest")
    draw = prescribed_draw(
        record["site"], record["tick"], record["values"], binding, provenance=record["provenance"]
    )
    if draw_manifest(draw, binding) != record:
        raise ValueError("Draw manifest mismatch")
    return draw


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


def sample_stable(coordinates, binding, *, site, tick):
    _uint(coordinates.seed, 32)
    _uint(coordinates.world_id, 64)
    _uint(tick, 64)
    world, clock = words64(coordinates.world_id), words64(tick)
    tokens = binding.kernel.membrane_tokens
    if site == "boundary_choice":
        pairs = stable_pairs(
            coordinates.seed,
            world,
            clock,
            owner_tokens(("boundary",), domain="categorical"),
            site=site,
        )
        value = np.asarray([int(stable_boundary_index(pairs[0, 0], binding))], int)
    elif site == "microtubule_gaussian":
        value = np.asarray(stable_normals(coordinates.seed, world, clock, tokens))
    else:
        value = np.asarray(stable_uniforms(coordinates.seed, world, clock, tokens, site=site))
    return prescribed_draw(
        site,
        tick,
        value,
        binding,
        provenance=dict(
            rng_id=STABLE_RNG_ID,
            seed=coordinates.seed,
            world_id=coordinates.world_id,
            tick=tick,
            implementation="threefry2x32",
            owner_digest="sha256-domain-NUL-id/little-endian-u32x8",
            boundary_order="Canonical unique ID order with native occurrence multiplicities",
        ),
    )


class Replay(NamedTuple):
    protein: ProteinState
    diffusion: StaticState
    rng: object
    tick: int
    time_s: float


def replay_record(binding, controls, replay):
    controls = validate_controls(controls)
    _uint(replay.tick, 64)
    if not _number(replay.time_s) or replay.time_s < 0:
        raise ValueError("Explicit finite nonnegative replay clock required")
    pstate = ProteinState(
        *(
            _field(v, len(ids), xp=np)
            for v, ids in zip(
                replay.protein,
                (binding.cell_ids, binding.membrane_ids, binding.environment_ids),
                strict=True,
            )
        )
    )
    shape = (len(binding.ion_ids), len(binding.membrane_ids))
    if any(
        np.asarray(v).shape != shape
        or np.asarray(v).dtype.kind not in "fiu"
        or not np.isfinite(v).all()
        for v in replay.diffusion
    ) or any(v.ndim != 1 or not np.isfinite(v).all() or np.any(v < 0) for v in pstate):
        raise ValueError("Replay records require finite unbatched declared component buffers")
    if isinstance(replay.rng, NativeStream):
        rng = native_stream_manifest(replay.rng)
    elif isinstance(replay.rng, StableCoordinates):
        _uint(replay.rng.seed, 32)
        _uint(replay.rng.world_id, 64)
        rng = dict(rng_id=STABLE_RNG_ID, seed=replay.rng.seed, world_id=replay.rng.world_id)
    else:
        raise ValueError("Replay must declare native sequential or stable-owner RNG law")
    payload = dict(
        law_id=LAW_ID,
        layout_identity=binding.identity,
        controls=asdict(controls),
        rng=rng,
        tick=replay.tick,
        time_s=replay.time_s,
        protein={k: np.asarray(v).tolist() for k, v in pstate._asdict().items()},
        diffusion={k: np.asarray(v).tolist() for k, v in replay.diffusion._asdict().items()},
    )
    return dict(payload, identity=_hash(payload))


def restore_replay(record, binding, controls):
    if (
        record.get("law_id") != LAW_ID
        or record.get("layout_identity") != binding.identity
        or record.get("controls") != asdict(validate_controls(controls))
    ):
        raise ValueError("Replay law/layout/controls mismatch")
    if (
        "identity" not in record
        or _hash({k: v for k, v in record.items() if k != "identity"}) != record["identity"]
    ):
        raise ValueError("Replay buffer/RNG/clock identity mismatch")
    raw = record["rng"]
    if raw.get("rng_id") == NATIVE_RNG_ID:
        rng = native_stream_from_manifest(raw)
    elif raw.get("rng_id") == STABLE_RNG_ID and set(raw) == {"rng_id", "seed", "world_id"}:
        rng = StableCoordinates(raw["seed"], raw["world_id"])
    else:
        raise ValueError("Unsupported replay RNG law")
    state = Replay(
        ProteinState(*(_freeze(record["protein"][k], float) for k in ProteinState._fields)),
        StaticState(*(_freeze(record["diffusion"][k], float) for k in StaticState._fields)),
        rng,
        record["tick"],
        record["time_s"],
    )
    if replay_record(binding, controls, state) != record:
        raise ValueError("Incomplete replay fields")
    return state
