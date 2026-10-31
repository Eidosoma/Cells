"""Prepared normal ECM event/control owners, modern channels and protein noise.

This separately owned composition lowers actual live coefficients into legitimate
material inputs. Tissue/geometry/callback and entry RNG ownership are supplied;
no native initialization, mesh reconstruction or SimRunner equivalence follows.
"""

import hashlib
import json
import math
from dataclasses import dataclass, replace
from types import SimpleNamespace

import numpy as np

from cells.core import physiology_native_calendar as calendars
from cells.processes import betse_ecm_grn_join as network
from cells.processes import betse_ecm_transport as material
from cells.processes import betse_normal_ecm_calcium_join as calcium_component
from cells.processes import betse_normal_ecm_catalog_join as catalog_component
from cells.processes import betse_normal_ecm_catalog_join_source as source
from cells.processes import betse_normal_ecm_event_join_material as event_material
from cells.processes import betse_normal_ecm_event_join_source as events
from cells.processes import betse_normal_ecm_field_join as full
from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_perturbations as random_source

LAW_ID = "betse_normal_ecm_event_catalog_CaATP_field_join_v1_5_0@1"
RateCache, Clock = (calcium_component.RateCache, calcium_component.Clock)
ROLES = ("Na", "K", "Cl", "Ca", "M", "P")
GLOBAL_KEYS = ("K_env", "Cl_env", "Na_env", "T_change", "gj_block", "NaKATP_block")
TISSUE_KEYS = ("Na_mem", "K_mem", "Cl_mem", "Ca_mem", "pressure", "ecmJ")


@dataclass(frozen=True)
class Binding:
    material_binding: object
    voltage_binding: object
    inputs: object
    calcium: object
    catalog: object
    call_limit: int
    calendar: object
    event_owner: object
    entry_event_state: object
    noise: object
    noise_binding: object
    entry_stream: object
    entry_noise_cache: object
    identity: str


@dataclass(frozen=True)
class NoiseCache:
    present: bool
    value: object


@dataclass(frozen=True)
class EventFieldState:
    binding_identity: str
    network: object
    field: object
    rate_cache: object
    clock: object
    event_stores: object
    noise_stream: object
    noise_cache: object
    identity: str


class EventJoinRejected(RuntimeError):
    def __init__(self, error, partial):
        super().__init__(str(error))
        self.partial = ions.freeze(partial)


def document_hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def composition_record(binding):
    return (
        LAW_ID,
        binding.material_binding.identity,
        binding.voltage_binding.identity,
        binding.inputs,
        binding.calcium,
        binding.catalog,
        binding.call_limit,
        calendars.record(binding.calendar),
        binding.event_owner,
        binding.entry_event_state,
        binding.noise,
        binding.noise_binding.identity,
        random_source.native_stream_manifest(binding.entry_stream),
        binding.entry_noise_cache,
    )


def record(parent):
    return (
        parent.binding_identity,
        parent.network,
        parent.field,
        parent.rate_cache,
        parent.clock,
        parent.event_stores,
        random_source.native_stream_manifest(parent.noise_stream),
        parent.noise_cache,
    )


def joined_state(binding, net, field, rate, clock, stores, stream, noise_cache):
    result = EventFieldState(
        binding.identity, net, field, rate, clock, ions.freeze(stores), stream, noise_cache, ""
    )
    return replace(result, identity=ions.digest(record(result)))


def _finite_number(value):
    return (
        isinstance(value, (int, float, np.integer, np.floating))
        and (not isinstance(value, (bool, np.bool_)))
        and math.isfinite(value)
    )


def _vector(value, shape, label):
    array = np.asarray(value)
    if array.dtype.kind not in "iuf" or array.shape != shape or (not np.isfinite(array).all()):
        raise ValueError("Require complete finite source event store: " + label)
    return ions.freeze(np.asarray(array, np.float64))


def _control(value, m, label):
    if _finite_number(value):
        return float(value)
    return _vector(value, (m,), label)


def _broadcast(value, m):
    return np.broadcast_to(np.asarray(value, np.float64), (m,)).copy()


def validate_stores(binding, raw):
    if set(raw) != set(events.EVENT_STORES):
        raise ValueError("Require every persistent event coefficient/control/boundary store")
    mb = binding.material_binding
    gb = mb.geometry_binding
    cb = gb.current_binding
    s, m, n, e = (
        len(cb.ion_ids),
        len(cb.membrane_ids),
        len(cb.cell_ids),
        math.prod(gb.geometry.shape),
    )
    result = {}
    for name in ("Dm_base", "Dm_scheduled", "Dm_cells"):
        result[name] = _vector(raw[name], (s, m), name)
    for name in ("D_env_base", "D_env"):
        result[name] = _vector(raw[name], (s, e), name)
    for name in ("D_env_weight_base", "D_env_weight"):
        result[name] = _vector(raw[name], gb.geometry.shape, name)
    for name in ("P_base", "P_mod", "P_cells"):
        result[name] = _vector(raw[name], (n,), name)
    result["D_free"] = _vector(raw["D_free"], (s,), "D_free")
    result["c_env_bound"] = _vector(raw["c_env_bound"], (s,), "c_env_bound")
    for name in ("gj_block", "NaKATP_block", "rho_channel"):
        result[name] = _control(raw[name], m, name)
    if not _finite_number(raw["T"]) or raw["T"] <= 0:
        raise ValueError("Require a positive supplied runtime event temperature")
    result["T"] = float(raw["T"])
    if set(raw["bound_V"]) != {"R", "L", "T", "B"} or not all(
        (_finite_number(v) for v in raw["bound_V"].values())
    ):
        raise ValueError("Require all supplied persistent boundary voltages")
    result["bound_V"] = dict(raw["bound_V"])
    return result


def require_salt_roles(owner, ion_ids, valences):
    if any(owner["global_options"][key] != 0 for key in ("K_env", "Na_env")):
        if "M" not in ion_ids or valences[list(ion_ids).index("M")] != -1:
            raise ValueError("Native K/Na salt events require an explicit complete M-1 ion role")


def validate_owner(binding, owner):
    required = {
        "kind",
        "provenance",
        "geometry_declaration_sha256",
        "owners",
        "handler_fields",
        "tissue_default",
        "tissue_target_inds",
        "cell_target_inds",
        "env_target_inds",
        "global_options",
        "scheduled_options",
        "configured_environment",
        "callbacks",
        "voltage",
        "event_cut",
    }
    if (
        set(owner) != required
        or owner["kind"] != "cells.supplied_finalized_native_tissue_event_owner@1"
    ):
        raise ValueError("Require the complete supplied finalized tissue/event owner")
    if not isinstance(owner["provenance"], str) or not owner["provenance"].strip():
        raise ValueError("Require tissue/callback source provenance")
    if owner["event_cut"] is not None:
        raise ValueError("Cuts/remeshing require separately supplied changing geometry ownership")
    definition = ions.data(binding.inputs["definition"])
    external = definition["environment_geometry_definition"]
    if owner["geometry_declaration_sha256"] != document_hash(external):
        raise ValueError("Tissue/event owners must bind the supplied original geometry declaration")
    gb = binding.material_binding.geometry_binding
    cb = gb.current_binding
    m, n, e = (len(cb.membrane_ids), len(cb.cell_ids), math.prod(gb.geometry.shape))
    o = owner["owners"]
    if set(o) != {
        "cell_ids",
        "membrane_ids",
        "environment_ids",
        "membrane_cell_ids",
        "membrane_environment_ids",
        "boundary_cell_occurrences",
    }:
        raise ValueError("Require complete supplied cell/membrane/environment ownership")
    if o["cell_ids"] != list(cb.cell_ids) or o["membrane_ids"] != list(cb.membrane_ids):
        raise ValueError("Supplied tissue axes differ from original geometry owners")
    if len(o["environment_ids"]) != e or len(set(o["environment_ids"])) != e:
        raise ValueError("Require every supplied ECM owner exactly once")
    if o["membrane_cell_ids"] != [o["cell_ids"][j] for j in cb.kernel.owner]:
        raise ValueError("Supplied membrane-cell ownership differs from original geometry")
    if o["membrane_environment_ids"] != [
        o["environment_ids"][j] for j in gb.geometry.membrane_to_grid
    ]:
        raise ValueError("Supplied membrane-ECM ownership differs from original geometry")
    maps = {}
    for key, size in (("tissue_target_inds", m), ("cell_target_inds", n), ("env_target_inds", e)):
        values = owner[key]
        if not isinstance(values, dict) or any(
            (
                not isinstance(k, str)
                or not k
                or (not isinstance(v, list))
                or any((type(i) is not int or not 0 <= i < size for i in v))
                for k, v in values.items()
            )
        ):
            raise ValueError("Require explicit ordered tissue target maps in each source domain")
        maps[key] = values
    if maps["tissue_target_inds"] != ions.data(binding.catalog["tissue_profiles"]):
        raise ValueError("Catalog and event tissue membrane owners must agree")
    if (
        not maps["tissue_target_inds"].keys()
        == maps["cell_target_inds"].keys()
        == maps["env_target_inds"].keys()
    ):
        raise ValueError("Require explicit ordered tissue target maps in each source domain")
    for name, indices in maps["tissue_target_inds"].items():
        if maps["env_target_inds"][name] != [int(gb.geometry.membrane_to_grid[i]) for i in indices]:
            raise ValueError(
                "Supplied tissue ECM targets differ from original membrane-grid ownership"
            )
    if set(owner["tissue_default"]) != {"Dm_" + role for role in ROLES} or not all(
        (_finite_number(v) for v in owner["tissue_default"].values())
    ):
        raise ValueError("Require explicit original default-tissue diffusion coefficients")
    if set(owner["global_options"]) != set(GLOBAL_KEYS) or set(owner["scheduled_options"]) != set(
        TISSUE_KEYS
    ):
        raise ValueError("Require every native global/targeted option guard")
    if set(owner["configured_environment"]) != set(cb.ion_ids) or not all(
        (_finite_number(v) for v in owner["configured_environment"].values())
    ):
        raise ValueError("Require complete fixed configured environmental reservoirs")
    require_salt_roles(owner, cb.ion_ids, cb.kernel.valence)
    fields = owner["handler_fields"]
    expected = {}
    for key, suffix in (("K_env", "Kenv"), ("Cl_env", "Clenv"), ("Na_env", "Naenv")):
        option = owner["global_options"][key]
        if option == 0:
            continue
        if (
            not isinstance(option, list)
            or len(option) != 4
            or (not all((_finite_number(v) for v in option)))
        ):
            raise ValueError("Require original complete global event parameters")
        for stem, value in zip(("t_on_", "t_off_", "t_change_", "mem_mult_"), option, strict=True):
            expected[stem + suffix] = value
    for key, names in (
        ("T_change", ("tonT", "toffT", "trampT", "multT")),
        ("NaKATP_block", ("tonNK", "toffNK", "trampNK")),
        ("gj_block", ("tonGJ", "toffGJ", "trampGJ")),
    ):
        option = owner["global_options"][key]
        if option == 0:
            continue
        needed = 4 if key in ("T_change", "gj_block") else 3
        if (
            not isinstance(option, list)
            or len(option) != needed
            or (not all((_finite_number(v) for v in option)))
        ):
            raise ValueError("Require original complete global event parameters")
        expected.update(zip(names, option, strict=False))
        if key == "gj_block":
            count = int(min(100, max(1, int(option[3]))) / 100 * m)
            expected["targets_gj_block"] = list(range(count))
    callbacks = {}
    for key, suffix in (
        ("Na_mem", "Namem"),
        ("K_mem", "Kmem"),
        ("Cl_mem", "Clmem"),
        ("Ca_mem", "Camem"),
        ("pressure", "P"),
    ):
        option = owner["scheduled_options"][key]
        if option == 0:
            continue
        if (
            not isinstance(option, list)
            or len(option) != 6
            or (not all((_finite_number(v) for v in option[:4])))
            or (not isinstance(option[4], list))
        ):
            raise ValueError("Require original complete targeted event parameters")
        map_key = "cell_target_inds" if key == "pressure" else "tissue_target_inds"
        if any((name not in maps[map_key] for name in option[4])):
            raise ValueError("Require every supplied event tissue profile")
        targets = [i for name in option[4] for i in maps[map_key][name]]
        if key == "pressure":
            expected.update(
                dict(zip(("t_onP", "t_offP", "t_changeP", "rate_P"), option[:4], strict=True))
            )
            expected.update(targets_P=targets, apply_P=option[4], function_P=option[5])
        else:
            for stem, value in zip(
                ("t_on_", "t_off_", "t_change_", "mem_mult_"), option[:4], strict=True
            ):
                expected[stem + suffix] = value
            expected["targets_" + suffix] = targets
            expected["apply_" + suffix] = option[4]
            expected["function_" + suffix] = option[5]
        if suffix not in owner["callbacks"]:
            raise ValueError("Require the actual finalized callback return and time program")
        callback = owner["callbacks"][suffix]
        if (
            set(callback) != {"source_function", "source_scalar", "dynamic", "provenance"}
            or callback["source_function"] != option[5]
        ):
            raise ValueError("Require the actual finalized callback return and time program")
        if option[5] not in (
            "None",
            "periodic",
            "f_sweep",
            "gradient_x",
            "gradient_y",
            "gradient_r",
            "single_cell",
        ):
            raise ValueError(
                "Bitmap/unowned callback initialization requires separate supplied dependencies"
            )
        scalar = np.asarray(callback["source_scalar"])
        if scalar.dtype.kind not in "iuf" or not np.isfinite(scalar).all():
            raise ValueError("Require finite supplied source callback output without shape repair")
        if option[5] in ("gradient_x", "gradient_y", "single_cell"):
            length = m if len(targets) == m else n if len(targets) == n else None
            if length is None:
                raise ValueError("Native callback constructor has no domain for this target length")
            if scalar.shape != (length,):
                raise ValueError(
                    "Supplied callback output differs from native length-selected axis"
                )
        if option[5] == "gradient_r" and scalar.shape != (m,):
            raise ValueError("Native radial callback retains the complete membrane axis")
        expected_kind = {"periodic": "periodic", "f_sweep": "sweep"}.get(option[5], "constant")
        if callback["dynamic"].get("kind") != expected_kind:
            raise ValueError("Prepared callback time law differs from original factory")
        if option[5] in ("None", "periodic", "f_sweep") and (
            scalar.shape != () or float(scalar) != 1
        ):
            raise ValueError("Preserve actual source scalar-one callback default")
        events.prepared_callback(callback["dynamic"])
        callbacks[suffix] = callback
    for kind in ("periodic", "sweep"):
        programs = [row["dynamic"] for row in callbacks.values() if row["dynamic"]["kind"] == kind]
        fields_for_kind = ("frequency", "phase") if kind == "periodic" else ("start", "slope")
        if programs and any(
            (
                any((program[key] != programs[0][key] for key in fields_for_kind))
                for program in programs
            )
        ):
            raise ValueError("Native callbacks share one supplied phase time-program configuration")
    option = owner["scheduled_options"]["ecmJ"]
    if option != 0:
        if (
            not isinstance(option, list)
            or len(option) != 5
            or (not all((_finite_number(v) for v in option[:3] + option[4:])))
            or (not isinstance(option[3], list))
        ):
            raise ValueError("Require original complete ECM junction event parameters")
        if any((name not in maps["env_target_inds"] for name in option[3])):
            raise ValueError("Require every supplied event tissue profile")
        expected.update(
            dict(zip(("t_on_ecmJ", "t_off_ecmJ", "t_change_ecmJ"), option[:3], strict=True))
        )
        expected.update(
            apply_ecmJ=option[3],
            mult_ecmJ=option[4],
            targets_ecmJ=[i for name in option[3] for i in maps["env_target_inds"][name]],
        )
    if fields != expected or set(callbacks) != set(owner["callbacks"]):
        raise ValueError(
            "Supplied finalized event fields differ from original configuration/target order"
        )
    voltage = owner["voltage"]
    if voltage is not None and (
        set(voltage)
        != {
            "start_time_step",
            "stop_time_step",
            "time_step_rate",
            "peak_voltage",
            "positive_voltage_boundary",
            "negative_voltage_boundary",
        }
        or not all(
            (
                _finite_number(voltage[k])
                for k in ("start_time_step", "stop_time_step", "time_step_rate", "peak_voltage")
            )
        )
        or any(
            (
                voltage[k] not in ("T", "B", "L", "R")
                for k in ("positive_voltage_boundary", "negative_voltage_boundary")
            )
        )
    ):
        raise ValueError("Require complete native voltage-event fields and boundary owners")


def bind(raw):
    raw = ions.data(raw)
    required = {
        "kind",
        "case_id",
        "case_role",
        "field",
        "calcium",
        "catalog",
        "stop_after_calls",
        "calendar",
        "event_owner",
        "entry_event_state",
        "noise",
        "prepared_rng",
        "noise_cache",
    }
    if set(raw) != required or raw["kind"] != "cells.normal_ecm_event_join_inputs@1":
        raise ValueError("Require a separately declared ECM event/catalog/noise composition")
    base = catalog_component.bind(
        {
            k: v
            for k, v in raw.items()
            if k
            in {"kind", "case_id", "case_role", "field", "calcium", "catalog", "stop_after_calls"}
        }
        | dict(kind="cells.normal_ecm_catalog_join_inputs@1")
    )
    declaration = raw["calendar"]
    if set(declaration) != {"phase", "step_count", "dt_s", "sample_stride", "provenance"}:
        raise ValueError("Require the supplied complete original normal source calendar")
    calendar = calendars.bind(**declaration)
    if (
        calendar.phase != "SIM"
        or calendar.step_count != 3
        or calendar.dt_s != base.inputs["bootstrap"]["dt_s"]
    ):
        raise ValueError("Require the actual N3 SIM calendar and configured phase dt")
    noise = raw["noise"]
    if (
        set(noise) != {"enabled", "level_mol_m2_s", "provenance"}
        or type(noise["enabled"]) is not int
        or noise["enabled"] not in (0, 1)
        or (not _finite_number(noise["level_mol_m2_s"]))
        or (not isinstance(noise["provenance"], str))
        or (not noise["provenance"].strip())
    ):
        raise ValueError("Require explicit original dynamic-protein-noise controls")
    prepared = raw["prepared_rng"]
    if (
        set(prepared) != {"kind", "manifest", "provenance"}
        or prepared["kind"] != "cells.supplied_post_event_finalization_numpy_state@1"
        or (not isinstance(prepared["provenance"], str))
        or (not prepared["provenance"].strip())
    ):
        raise ValueError("Require explicit prepared RNG epoch and full MT19937 state")
    stream = random_source.native_stream_from_manifest(prepared["manifest"])
    placeholder = SimpleNamespace(
        material_binding=base.material_binding, inputs=base.inputs, catalog=base.catalog
    )
    validate_owner(placeholder, raw["event_owner"])
    stores = validate_stores(placeholder, raw["entry_event_state"])
    mb = base.material_binding
    gb = mb.geometry_binding
    cb = gb.current_binding
    o = raw["event_owner"]["owners"]
    if not np.array_equal(
        stores["Dm_cells"], mb.kernel.membrane_diffusion_m2_s
    ) or not np.array_equal(stores["D_env"], mb.kernel.environment_diffusion_m2_s):
        raise ValueError(
            "Supplied entry live coefficients must match declared initial component inputs"
        )
    if not np.array_equal(
        stores["D_free"], gb.definition["cache_initial_state"]["free_diffusion_m2_s"]
    ):
        raise ValueError("Require original fixed supplied initializer/free-diffusion caches")
    for row in base.inputs["steps"]:
        packet = row["material"]
        if (
            row["scheduled_controls"] is not None
            or packet["runtime_temperature_K"] != stores["T"]
            or (not np.array_equal(packet["boundary_mol_m3"], stores["c_env_bound"]))
            or (dict(row["boundary_V"]) != stores["bound_V"])
            or (
                not np.array_equal(
                    packet["junction_block"], _broadcast(stores["gj_block"], len(cb.membrane_ids))
                )
            )
            or (
                not np.array_equal(
                    packet["channel_multiplier"],
                    _broadcast(stores["rho_channel"], len(cb.membrane_ids)),
                )
            )
        ):
            raise ValueError(
                "Event-owned persistent controls cannot have competing per-step overrides"
            )
    if dict(base.inputs["bootstrap"]["boundary_V"]) != stores["bound_V"]:
        raise ValueError("Supplied entry voltage boundary must own the bootstrap")
    noise_binding = random_source.bind_layout(
        random_source.Layout(
            tuple(o["cell_ids"]),
            tuple(o["membrane_ids"]),
            tuple(o["environment_ids"]),
            tuple(cb.ion_ids),
            tuple(o["membrane_cell_ids"]),
            tuple(o["membrane_environment_ids"]),
            tuple(o["boundary_cell_occurrences"]),
            cb.kernel.membrane_area_m2,
            gb.definition["geometry"]["cell_volume_m3"],
            gb.definition["parameters"]["cell_height_m"] * gb.geometry.delta_m**2,
            "source_fast" if mb.kernel.fast_update_ecm else "matrix",
            dict(supplied_owner=raw["event_owner"]["provenance"], geometry=gb.identity),
        )
    )
    cached = raw["noise_cache"]
    if (
        set(cached) != {"present", "value", "provenance"}
        or type(cached["present"]) is not bool
        or (not isinstance(cached["provenance"], str))
        or (not cached["provenance"].strip())
    ):
        raise ValueError("Require actual supplied protein-noise-cache presence/absence")
    value = (
        _vector(cached["value"], (len(cb.membrane_ids),), "protein_noise_flux")
        if cached["present"]
        else None
    )
    if not cached["present"] and cached["value"] is not None:
        raise ValueError("Absent protein-noise cache cannot contain invented values")
    result = Binding(
        base.material_binding,
        base.voltage_binding,
        base.inputs,
        base.calcium,
        base.catalog,
        base.call_limit,
        calendar,
        ions.freeze(raw["event_owner"]),
        ions.freeze(stores),
        ions.freeze(noise),
        noise_binding,
        stream,
        NoiseCache(cached["present"], value),
        "",
    )
    return replace(result, identity=ions.digest(composition_record(result)))


def validate_composition(binding):
    if type(binding) is not Binding or binding.identity != ions.digest(composition_record(binding)):
        raise ValueError("Require the unchanged owned event composition")


def runtime_material(binding, stores):
    definition = ions.data(binding.inputs["definition"])
    definition["ions"]["membrane_diffusion_m2_s"] = source.clone(stores["Dm_cells"])
    definition["ions"]["environment_diffusion_m2_s"] = source.clone(stores["D_env"])
    lowered = material.bind(definition)
    if lowered.geometry_binding.identity != binding.material_binding.geometry_binding.identity:
        raise ValueError(
            "Live coefficient lowering cannot alter supplied geometry/initializer caches"
        )
    return (lowered, definition)


def _noise_cache(ctx):
    present = hasattr(ctx.sim, "protein_noise_flux")
    return NoiseCache(present, ions.freeze(ctx.sim.protein_noise_flux) if present else None)


def _install_noise_cache(ctx, cache):
    if cache.present:
        ctx.sim.protein_noise_flux = source.clone(cache.value)


def _context(binding, values, definition=None, forcing=None):
    view = SimpleNamespace(
        material_binding=binding.material_binding if definition is None else definition
    )
    ctx = network.make_context(view, values, ions.data(binding.inputs["network"]), forcing)
    source.configure(ctx, ions.data(binding.catalog))
    ctx.p.dynamic_noise = binding.noise["enabled"]
    ctx.p.dynamic_noise_level = binding.noise["level_mol_m2_s"]
    return ctx


def initialize(binding, *, after_cold=None, before_field=None):
    validate_composition(binding)
    parent = material.state(binding.material_binding, ions.data(binding.inputs["initial"]))
    ctx = _context(binding, material.Values(*(np.array(v, copy=True) for v in parent.values)))
    events.install_owner(ctx, ions.data(binding.event_owner), ions.data(binding.entry_event_state))
    _install_noise_cache(ctx, binding.entry_noise_cache)
    policy = calcium_component.native_policy(ctx, binding)
    try:
        cached = source.cold(ctx)
    except Exception as error:
        raise EventJoinRejected(
            error,
            dict(
                stage="cold",
                policy=policy,
                event_stores=events.event_snapshot(ctx.sim),
                **catalog_component.failure_snapshot(ctx, None),
            ),
        ) from error
    parent = material.state(binding.material_binding, source.material_values(ctx.sim))
    initial = network._state(
        binding,
        parent,
        cached,
        dict(
            gj_block=source.clone(ctx.sim.gj_block), NaKATP_block=source.clone(ctx.sim.NaKATP_block)
        ),
    )
    labels = calendars.window(binding.calendar).event_label_s
    clock = Clock(labels, 0, 0.0)
    rate = RateCache(False, None)
    if after_cold is not None:
        after_cold(
            ions.freeze(
                dict(
                    network=initial,
                    policy=policy,
                    clock=clock,
                    rate_cache=rate,
                    channel_trace=ctx.trace,
                    event_stores=events.event_snapshot(ctx.sim),
                    noise_stream=random_source.native_stream_manifest(binding.entry_stream),
                    noise_cache=binding.entry_noise_cache,
                )
            )
        )
    try:
        source.validate_cached_channels(ctx, cached)
        prepared, fields = full.reconstruct(
            binding,
            initial,
            binding.calendar.dt_s,
            ions.data(binding.entry_event_state["bound_V"]),
            "bootstrap",
            before_field,
        )
    except Exception as error:
        raise EventJoinRejected(
            error,
            dict(
                stage="bootstrap",
                network=initial,
                event_stores=events.event_snapshot(ctx.sim),
                partial=getattr(error, "partial", None),
            ),
        ) from error
    return joined_state(
        binding,
        prepared,
        fields,
        rate,
        clock,
        events.event_snapshot(ctx.sim),
        binding.entry_stream,
        binding.entry_noise_cache,
    )


def advance(
    binding,
    parent,
    *,
    before_events=None,
    after_events=None,
    before_material=None,
    before_calcium=None,
    before_channels=None,
    before_network=None,
    before_noise=None,
    before_field=None,
    after_calcium=None,
    after_noise=None,
    after_material=None,
):
    validate_composition(binding)
    if (
        type(parent) is not EventFieldState
        or parent.binding_identity != binding.identity
        or parent.identity != ions.digest(record(parent))
    ):
        raise ValueError("Require the unchanged owned event/channel/material parent")
    index = parent.network.material.step_index
    dt = binding.calendar.dt_s
    if index >= binding.call_limit:
        raise ValueError("Declared bounded normal-call prefix is complete")
    if (
        type(parent.clock) is not Clock
        or not isinstance(parent.clock.source_times_s, np.ndarray)
        or parent.clock.source_times_s.dtype != np.float64
        or (parent.clock.source_times_s.shape != (3,))
        or parent.clock.source_times_s.flags.writeable
        or (parent.clock.call_index != index)
        or (parent.clock.material_dt_sum_s != index * dt)
        or (
            not np.array_equal(
                parent.clock.source_times_s, calendars.window(binding.calendar).event_label_s
            )
        )
    ):
        raise ValueError("Require original source labels and separate accumulated material dt")
    if (
        type(parent.field) is not full.FieldStage
        or parent.field.binding_identity != binding.identity
        or parent.field.identity != ions.digest(full.field_record(parent.field))
    ):
        raise ValueError("Require the actual preceding full field")
    rate = parent.rate_cache
    m = len(binding.material_binding.geometry_binding.current_binding.membrane_ids)
    if (
        type(rate) is not RateCache
        or rate.present is not (binding.calcium["alpha_Ca"] > 0 and index > 0)
        or (
            rate.value is not None
            if not rate.present
            else not isinstance(rate.value, np.ndarray)
            or rate.value.shape != (m,)
            or rate.value.dtype != np.float64
            or rate.value.flags.writeable
            or (not np.isfinite(rate.value).all())
        )
    ):
        raise ValueError("Require actual CaATP rate absence or complete immutable source cache")
    stores = validate_stores(binding, ions.data(parent.event_stores))
    for key in ("gj_block", "NaKATP_block"):
        if not source.equal_tree(parent.network.controls[key], stores[key]):
            raise ValueError("Event and GRN control owners differ at the actual parent epoch")
    stream = parent.noise_stream
    random_source.native_stream_manifest(stream)
    nc = parent.noise_cache
    if (
        type(nc) is not NoiseCache
        or type(nc.present) is not bool
        or (
            nc.value is not None
            if not nc.present
            else not isinstance(nc.value, np.ndarray)
            or nc.value.dtype != np.float64
            or nc.value.shape != (m,)
            or nc.value.flags.writeable
            or (not np.isfinite(nc.value).all())
        )
    ):
        raise ValueError("Require complete immutable actual protein-noise cache or absence")
    row = ions.data(binding.inputs["steps"][index])
    holder = dict(parent=parent)
    ctx = _context(
        binding, material.Values(*(np.array(v, copy=True) for v in parent.network.material.values))
    )
    try:
        source.restore(ctx, parent.network.network_cache)
        events.install_owner(ctx, ions.data(binding.event_owner), stores)
        _install_noise_cache(ctx, nc)
        ctx.phase.kind = "SIM"
        entry = dict(
            mode="events",
            owner=ions.data(binding.event_owner),
            before=events.event_snapshot(ctx.sim),
            material_before=source.material_values(ctx.sim),
            clock=ions.data(parent.clock),
            source_time_s=float(parent.clock.source_times_s[index]),
            configured_temperature_K=ctx.p.T,
            dt_s=dt,
            ion_ids=list(ctx.ion_ids),
            valence=source.clone(ctx.sim.zs),
        )
        holder["before_events"] = entry
        if before_events is not None:
            before_events(source.clone(entry))
        events.reset_fluxes(ctx.sim, ctx.p)
        holder["reset_return"] = source.material_values(ctx.sim)
        event = events.fire(ctx, float(parent.clock.source_times_s[index]))
        holder["events"] = event
        if after_events is not None:
            after_events(ions.freeze(event))
        stores = events.event_snapshot(ctx.sim)
        runtime, definition = runtime_material(binding, stores)
        lowered = material.state(runtime, source.material_values(ctx.sim), step_index=index)
        holder.update(runtime_binding=runtime, lowered_parent=lowered, definition=definition)
        packet = dict(
            row["material"],
            runtime_temperature_K=float(stores["T"]),
            boundary_mol_m3=source.clone(stores["c_env_bound"]),
            junction_block=_broadcast(stores["gj_block"], m),
            channel_multiplier=_broadcast(stores["rho_channel"], m),
            electric_x_source=parent.field.environment.values.electric_x_source,
            electric_y_source=parent.field.environment.values.electric_y_source,
        )
        forcing = material.drive(runtime, packet)
        material_input = dict(
            mode="material",
            definition=definition,
            initial=ions.data(lowered.values._asdict()),
            steps=[source.clone(packet)],
            calcium=ions.data(binding.calcium),
            rate_cache_before=ions.data(rate),
            clock=ions.data(parent.clock),
            catalog=ions.data(binding.catalog),
            network_cache=source.cache(ctx),
            event_stores=source.clone(stores),
            noise=ions.data(binding.noise),
            noise_stream_before=random_source.native_stream_manifest(stream),
        )
        material_input["prospective_noise_draw"] = None
        material_input["prospective_noise_uniforms"] = None
        material_input["prospective_stream_after"] = random_source.native_stream_manifest(stream)
        if binding.noise["enabled"] == 1 and "P" in ctx.ion_ids:
            preview, next_preview = random_source.sample_native(
                stream, binding.noise_binding, site="protein_flux", tick=index
            )
            material_input["prospective_noise_uniforms"] = preview.values.copy()
            material_input["prospective_noise_draw"] = random_source.draw_manifest(
                preview, binding.noise_binding
            )
            material_input["prospective_stream_after"] = random_source.native_stream_manifest(
                next_preview
            )
        material_input["prospective_draw_is_uncommitted"] = True
        holder["material_inputs"] = material_input
        if before_material is not None:
            before_material(source.clone(material_input))

        def on_calcium(arrays):
            result, phase = calcium_component.calcium(
                binding, arrays, forcing, rate, parent.clock, before_calcium
            )
            holder.update(rate=result, calcium=phase)
            if after_calcium is not None:
                after_calcium(result, phase)

        def on_network(arrays):
            current = _context(binding, arrays, runtime, forcing)
            holder["ctx"] = current
            source.restore(current, parent.network.network_cache)
            if any((value != index for value in current.channel_calls.values())):
                raise ValueError("Require actual channel cache counters at source clock epoch")
            events.install_owner(current, ions.data(binding.event_owner), stores)
            _install_noise_cache(current, nc)
            calcium_component.native_policy(current, binding)
            if holder["rate"].present:
                current.sim.rate_CaATP = holder["rate"].value.copy()
            source.run_dispatch(
                current,
                definition,
                row["publication"],
                float(parent.clock.source_times_s[index]),
                before_network,
                before_channels,
            )

        def on_noise(arrays):
            current = holder["ctx"]

            def noise_input(value):
                value.update(
                    mode="noise",
                    definition=source.clone(definition),
                    noise=ions.data(binding.noise),
                    dt_s=forcing.dt_s,
                    source_time_s=float(parent.clock.source_times_s[index]),
                    noise_cache_before=ions.data(nc),
                )
                holder["before_noise"] = source.clone(value)
                if before_noise is not None:
                    before_noise(value)

            next_stream, phase = events.noise(
                current, stream, binding.noise_binding, index, ions.data(binding.noise), noise_input
            )
            expected = material_input["prospective_noise_draw"]
            if expected is None:
                if phase["draws"]:
                    raise ValueError("Disabled noise branch consumed an unexpected draw")
            elif len(phase["draws"]) != 1 or phase["draws"][0] != expected:
                raise ValueError(
                    "Actual post-GRN draw differs from cloned incoming-stream condition"
                )
            holder.update(noise_stream=next_stream, noise=phase)
            if after_noise is not None:
                after_noise(ions.freeze(phase))

        def failed(local):
            holder["material_partial"] = dict(
                frames=ions.data(tuple(local.get("frames", ()))),
                environment_records=ions.data(tuple(local.get("environment_records", ()))),
                trial=local.get("trial"),
                diagnostics=local.get("diagnostics"),
                failure=local.get("failure"),
                available_arrays={
                    name: value.copy()
                    for name, value in local.items()
                    if isinstance(value, np.ndarray)
                },
            )

        trial = event_material.step_after_events(
            runtime,
            lowered,
            forcing,
            on_network=on_network,
            on_failure=failed,
            on_calcium=on_calcium,
            on_noise=on_noise,
        )
        current = holder["ctx"]
        source.validate_cached_channels(current, source.cache(current))
        candidate = network._state(
            binding, trial.candidate, source.cache(current), current.trace["controls_after"]
        )
        holder.update(
            material_parent=candidate,
            trial=trial,
            network=current.trace,
            post_material_cache=source.cache(current),
        )
        if after_material is not None:
            after_material(candidate, trial, current.trace, holder["calcium"], holder["noise"])
        prepared, fields = full.reconstruct(
            binding, candidate, dt, source.clone(current.sim.bound_V), "field", before_field
        )
        clock = Clock(parent.clock.source_times_s, index + 1, (index + 1) * dt)
        result = joined_state(
            binding,
            prepared,
            fields,
            holder["rate"],
            clock,
            events.event_snapshot(current.sim),
            holder["noise_stream"],
            _noise_cache(current),
        )
        return (
            result,
            trial,
            ions.freeze(current.trace),
            holder["calcium"],
            holder["noise"],
            ions.freeze(
                dict(
                    before_events=entry,
                    events=event,
                    reset_return=holder["reset_return"],
                    runtime_material_declaration=definition,
                    runtime_material_binding=runtime,
                    lowered_parent=lowered,
                    material_parent=candidate,
                    post_material_cache=holder["post_material_cache"],
                    initial_field=parent.field,
                    fields=fields,
                    clock_before=parent.clock,
                    clock_after=clock,
                )
            ),
        )
    except Exception as error:
        current = holder.get("ctx", ctx)
        raise EventJoinRejected(
            error,
            dict(
                stage="event_material_network_noise_field",
                parent=parent,
                available={key: value for key, value in holder.items() if key != "ctx"},
                source_partial=getattr(error, "partial", None),
                available_event_stores={
                    name: source.clone(getattr(current.sim, name))
                    for name in events.EVENT_STORES
                    if hasattr(current.sim, name)
                },
                missing_event_stores=[
                    name for name in events.EVENT_STORES if not hasattr(current.sim, name)
                ],
                **catalog_component.failure_snapshot(current, parent.network.network_cache),
            ),
        ) from error
