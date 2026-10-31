"""Explicit one-time ordinary INIT setup on supplied tissue/core/cache owners.

No seed loader, profile picker, whole init_dynamics or physical initializer is
represented by these supplied seams. Setup never fires an event or evaluates a
time callback. Both random streams are local clones of complete supplied state.
"""

import hashlib
import json
import math
import random
import sys
from types import SimpleNamespace

import numpy as np

from cells.processes import betse_normal_ecm_init_phase_source as source
from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_perturbations as perturbations

GLOBAL_KEYS = ("K_env", "Cl_env", "Na_env", "T_change", "gj_block", "NaKATP_block")
TISSUE_KEYS = ("Na_mem", "K_mem", "Cl_mem", "Ca_mem", "pressure", "ecmJ")
STORES = (
    "T",
    "P_cells",
    "P_base",
    "P_mod",
    "div_u_osmo",
    "Dm_base",
    "Dm_scheduled",
    "Dm_cells",
    "D_env_base",
    "D_env",
    "D_free",
    "channel_noise_factor",
    "gj_block",
    "NaKATP_block",
    "CaATP_block",
    "rho_pump",
    "rho_channel",
    "met_concs",
    "endo_retic",
    "c_env_bound",
    "bound_V",
)


def real(value, name):
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError("Require a finite explicit setup scalar: " + name)
    return float(value)


def tuple_tree(value):
    return tuple(tuple_tree(v) for v in value) if isinstance(value, (tuple, list)) else value


def python_manifest(rng):
    payload = dict(
        kind="python.random.MT19937.full_state@1",
        implementation=sys.implementation.name,
        python_version=list(sys.version_info[:3]),
        state=json.loads(json.dumps(rng.getstate())),
    )
    identity = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    return dict(payload, identity=identity)


def python_restore(saved):
    if not isinstance(saved, dict) or set(saved) != {
        "kind",
        "implementation",
        "python_version",
        "state",
        "identity",
    }:
        raise ValueError("Require complete supplied Python shuffle state")
    rng = random.Random(0)
    rng.setstate(tuple_tree(saved["state"]))
    if python_manifest(rng) != saved:
        raise ValueError("Python shuffle law/version/state identity differs")
    return rng


def validate(raw, base):
    if (
        set(raw)
        != {
            "kind",
            "provenance",
            "receipts",
            "numpy_rng",
            "python_rng",
            "channel_noise_level",
            "global_options",
            "scheduled_options",
            "maps",
            "frequency_sweep",
            "dynamic_noise",
        }
        or raw["kind"] != "cells.supplied_pre_INIT_setup@1"
    ):
        raise ValueError("Require the complete pre-setup INIT declaration")
    if not isinstance(raw["provenance"], str) or not raw["provenance"].strip():
        raise ValueError("Require supplied setup provenance")
    if set(raw["receipts"]) != {"tissue_profiles", "init_core", "initializer_cache"} or any(
        not isinstance(v, str) or not v.strip() for v in raw["receipts"].values()
    ):
        raise ValueError("Declare supplied tissue, core and conditional initializer-cache seams")
    real(raw["channel_noise_level"], "channel_noise_level")
    perturbations.native_stream_from_manifest(raw["numpy_rng"])
    python_restore(raw["python_rng"])
    if set(raw["global_options"]) != set(GLOBAL_KEYS) or set(raw["scheduled_options"]) != set(
        TISSUE_KEYS
    ):
        raise ValueError("Require all global and targeted event setup options")
    for key, row in raw["global_options"].items():
        if type(row) is int and row == 0:
            continue
        if not isinstance(row, list) or len(row) != (3 if key == "NaKATP_block" else 4):
            raise ValueError("Require disabled zero or the exact source global option: " + key)
        for value in row:
            real(value, key)
    for key, row in raw["scheduled_options"].items():
        if type(row) is int and row == 0:
            continue
        expected = 5 if key == "ecmJ" else 6
        if not isinstance(row, list) or len(row) != expected:
            raise ValueError("Require a literal targeted setup row: " + key)
        for value in row[:3]:
            real(value, key)
        if key != "ecmJ":
            real(row[3], key)
            if row[5] not in ("None", "f_sweep"):
                raise ValueError("Only constant or dormant source f_sweep setup is admitted")
        else:
            real(row[4], key)
    if set(raw["frequency_sweep"]) != {"f start", "f stop", "f slope"}:
        raise ValueError("Require original frequency-sweep setup fields")
    for key, value in raw["frequency_sweep"].items():
        if value is not None or key != "f slope":
            real(value, key)
    if (
        set(raw["dynamic_noise"]) != {"enabled", "level"}
        or type(raw["dynamic_noise"]["enabled"]) is not bool
    ):
        raise ValueError("Require explicit dormant dynamic-noise configuration")
    real(raw["dynamic_noise"]["level"], "dormant dynamic noise")
    cb = base.material_binding.geometry_binding.current_binding
    g = base.material_binding.geometry_binding.geometry
    if set(raw["maps"]) != {"tissue_target_inds", "cell_target_inds", "env_target_inds"}:
        raise ValueError("Require explicit target maps, without profile selection")
    for key, size in (
        ("tissue_target_inds", len(cb.membrane_ids)),
        ("cell_target_inds", len(cb.cell_ids)),
        ("env_target_inds", len(g.grid_points_m)),
    ):
        for name, values in raw["maps"][key].items():
            if (
                not isinstance(name, str)
                or not name
                or not isinstance(values, list)
                or any(type(v) is not int or not 0 <= v < size for v in values)
            ):
                raise ValueError("Invalid supplied target ownership: " + key)
    for key, row in raw["scheduled_options"].items():
        if row == 0:
            continue
        profiles = row[3 if key == "ecmJ" else 4]
        table = raw["maps"][
            "env_target_inds"
            if key == "ecmJ"
            else "cell_target_inds"
            if key == "pressure"
            else "tissue_target_inds"
        ]
        if not isinstance(profiles, list) or any(name not in table for name in profiles):
            raise ValueError("Unknown explicitly supplied event target profile")
    if not np.array_equal(base.inputs["initial"]["voltage_V"], np.zeros(len(cb.membrane_ids))):
        raise ValueError("This fresh INIT entry requires the source init_core zero voltage")


def noise_layout(base, provenance):
    gb = base.material_binding.geometry_binding
    cb, g = gb.current_binding, gb.geometry
    cg = gb.definition["current_definition"]["geometry"]
    # Boundary occurrences only bind the existing RNG API; this setup samples
    # static_K and never samples a boundary category.
    return perturbations.bind_layout(
        perturbations.Layout(
            tuple(cb.cell_ids),
            tuple(cb.membrane_ids),
            tuple("native-grid/" + str(i) for i in range(len(g.grid_points_m))),
            tuple(cb.ion_ids),
            tuple(cb.cell_ids[i] for i in cg["owner"]),
            tuple("native-grid/" + str(i) for i in g.membrane_to_grid),
            tuple(cb.cell_ids),
            cb.kernel.membrane_area_m2,
            gb.definition["geometry"]["cell_volume_m3"],
            gb.definition["parameters"]["cell_height_m"] * g.delta_m**2,
            "source_fast" if base.material_binding.kernel.fast_update_ecm else "matrix",
            dict(supplied_setup=provenance, geometry=gb.identity),
        )
    )


def pre_cold(base, raw):
    """Real static sampler/arithmetic, blocks and pressure stores, once per entry."""
    gb, k = base.material_binding.geometry_binding, base.material_binding.kernel
    cb = gb.current_binding
    stream = perturbations.native_stream_from_manifest(raw["numpy_rng"])
    draw, after = perturbations.sample_native(
        stream, noise_layout(base, raw["provenance"]), site="static_K", tick=0
    )
    static = perturbations.static_initialize(
        k.membrane_diffusion_m2_s,
        draw.values,
        raw["channel_noise_level"],
        noise_layout(base, raw["provenance"]),
        xp=np,
    )
    n, m = len(cb.cell_ids), len(cb.membrane_ids)
    controls = dict(
        gj_block=np.ones(m) if raw["global_options"]["gj_block"] != 0 else 1,
        NaKATP_block=np.ones(m) if raw["global_options"]["NaKATP_block"] != 0 else 1,
    )
    stores = dict(
        T=gb.definition["parameters"]["configured_temperature_K"],
        P_cells=np.zeros(n),
        P_base=np.zeros(n),
        P_mod=np.zeros(n),
        div_u_osmo=np.zeros(n),
        Dm_base=static.base_m2_s,
        Dm_scheduled=static.scheduled_m2_s,
        Dm_cells=static.current_m2_s,
        D_env_base=np.array(k.environment_diffusion_m2_s, copy=True),
        D_env=np.array(k.environment_diffusion_m2_s, copy=True),
        D_free=np.asarray(gb.definition["cache_initial_state"]["free_diffusion_m2_s"]).copy(),
        channel_noise_factor=np.array(draw.values, copy=True),
        CaATP_block=np.ones(m),
        met_concs=None,
        endo_retic=None,
        c_env_bound=np.array(base.inputs["network"]["initial_ion_boundary"], copy=True),
        bound_V=ions.data(base.inputs["bootstrap"]["boundary_V"]),
        **controls,
    )
    return dict(
        stage="pre_cold_static_setup",
        source_phase="INIT",
        legacy_run_sim=False,
        setup_draw_count=1,
        numpy_rng_before=raw["numpy_rng"],
        numpy_rng_after=perturbations.native_stream_manifest(after),
        python_rng_before=raw["python_rng"],
        static_uniforms=draw.values,
        static_level=raw["channel_noise_level"],
        static_diffusion_before=k.membrane_diffusion_m2_s,
        stores=stores,
        store_presence_before_cold=dict(rho_pump=False, rho_channel=False),
        receipts=raw["receipts"],
    )


def install(ctx, stores):
    ctx.phase.kind = "INIT"
    ctx.p._run_sim = False
    for key, value in stores.items():
        setattr(ctx.sim, key, source.clone(value))


def callable_record(value):
    if callable(value):
        return dict(
            callable=True,
            evaluated=False,
            name=value.__name__,
            free_variables=list(value.__code__.co_freevars),
            closure=[]
            if value.__closure__ is None
            else [
                None
                if c.cell_contents is None
                else c.cell_contents
                if isinstance(c.cell_contents, (int, float, str))
                else type(c.cell_contents).__name__
                for c in value.__closure__
            ],
        )
    return source.clone(value)


def finalize(ctx, raw):
    """Literal global+targeted finalizers after fresh GRN/mechanics setup."""
    rng = python_restore(raw["python_rng"])
    ctx.p.global_options = source.clone(raw["global_options"])
    ctx.p.scheduled_options = source.clone(raw["scheduled_options"])
    ctx.p.f_scan_properties = source.clone(raw["frequency_sweep"])
    ctx.p._run_sim = False
    ctx.p.is_ecm = True
    for key, values in raw["maps"].items():
        setattr(ctx.sim.dyna, key, source.clone(values))
    owner = SimpleNamespace(
        **{key: source.clone(value) for key, value in vars(ctx.sim.dyna).items()}
    )
    source._finalize_events_global(owner, ctx.phase, shuffle=rng.shuffle)
    source._finalize_events_tissue(owner, ctx.phase)
    return dict(
        stage="event_finalization_after_cold",
        global_options=raw["global_options"],
        scheduled_options=raw["scheduled_options"],
        finalized_fields={key: callable_record(value) for key, value in vars(owner).items()},
        frequency_sweep_after=source.clone(ctx.p.f_scan_properties),
        python_rng_before=raw["python_rng"],
        python_rng_after=python_manifest(rng),
        event_fire_calls=0,
        dynamic_noise_calls=0,
        dynamic_noise_configuration=raw["dynamic_noise"],
        source_phase="INIT",
        legacy_run_sim=False,
    )


def snapshot(ctx):
    return {key: source.clone(getattr(ctx.sim, key)) for key in STORES}
