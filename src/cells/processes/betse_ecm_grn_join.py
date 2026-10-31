"""Nonempty genuine GRN at the normal ECM late-network/deferred-commit boundary."""

import math
from dataclasses import dataclass, replace
from types import SimpleNamespace

import numpy as np

from cells.processes import betse_ecm_grn_source as source
from cells.processes import betse_ecm_transport as material
from cells.processes import betse_environment_field as geometry_source
from cells.processes import betse_normal_current as current
from cells.processes import betse_normal_ion_join as ions

LAW_ID = "betse_normal_ecm_grn_network_v1_5_0@1"
validate_binding, state, drive = material.validate_binding, material.state, material.drive
State, Values, Frame, ECMRecord, Trial, ECMTransportRejected = (
    material.State,
    material.Values,
    material.Frame,
    material.ECMRecord,
    material.Trial,
    material.ECMTransportRejected,
)
freeze, _electroflux, _smooth = material.freeze, material._electroflux, material._smooth
Drive = material.Drive
state_record, trial_record = material.state_record, material.trial_record
MAX_STEPS = material.MAX_STEPS


@np.errstate(all="ignore")
def material_step(binding, parent, forcing, *, on_network, on_failure):
    trial = None
    try:
        validate_binding(binding)
        if (
            type(parent) is not State
            or parent.binding_identity != binding.identity
            or parent.step_index >= MAX_STEPS
        ):
            raise ValueError(
                "Require the bound original parent within the qualified three-call cap"
            )
        checked = state(binding, parent.values._asdict(), step_index=parent.step_index)
        if (
            checked.identity != parent.identity
            or current.record(checked.values) != current.record(parent.values)
            or any((v.flags.writeable for v in parent.values))
        ):
            raise ValueError("Changed source state or mutable/non-float64 buffers")
        if (
            type(forcing) is not Drive
            or current.record(drive(binding, forcing._asdict())) != current.record(forcing)
            or any((isinstance(v, np.ndarray) and v.flags.writeable for v in forcing))
        ):
            raise ValueError("Require complete immutable typed ECM source drive")
        gb, k = (binding.geometry_binding, binding.kernel)
        cb, g = (gb.current_binding, gb.geometry)
        ck, p = (cb.kernel, gb.definition["parameters"])
        s, m = (len(cb.ion_ids), len(cb.membrane_ids))
        a = {key: value.copy() for key, value in parent.values._asdict().items()}
        cell, membrane, env, vm, fm, fg, fx_all, fy_all, vgj, egj, exy, opening = a.values()
        frames, environment_records = ([], [])
        delta, volume = (g.delta_m, p["cell_height_m"] * g.delta_m**2)
        cell_volume = np.asarray(gb.definition["geometry"]["cell_volume_m3"])
        clip = np.zeros(s)
        clamp, collocated, smoothing = (np.zeros(s), np.zeros(s), np.zeros(s))
        environment_exchange = np.zeros(s)

        def observe(stage, i=None):
            frames.append(
                Frame(
                    stage,
                    None if i is None else cb.ion_ids[i],
                    Values(
                        *(
                            freeze(value)
                            for value in (
                                cell,
                                membrane,
                                env,
                                vm,
                                fm,
                                fg,
                                fx_all,
                                fy_all,
                                vgj,
                                egj,
                                exy,
                                opening,
                            )
                        )
                    ),
                )
            )

        observe("initial")
        fm.fill(0)
        fg.fill(0)
        fx_all, fy_all = (np.zeros((s, math.prod(g.shape))), np.zeros((s, math.prod(g.shape))))
        observe("reset_flux")
        fm += forcing.supplied_pump_membrane_flux_mol_m2_s
        observe("supplied_pump_flux")
        failure = None
        with np.errstate(all="ignore"):
            for i in k.moving:
                ones = np.ones(m)
                leak = _electroflux(
                    env[i][g.membrane_to_grid],
                    membrane[i],
                    k.membrane_diffusion_m2_s[i],
                    ones * k.membrane_thickness_m,
                    ck.valence[i] * ones,
                    vm,
                    forcing.runtime_temperature_K,
                    ck.F_C_mol,
                    k.R_J_mol_K,
                    forcing.channel_multiplier,
                )
                if not k.cluster_open:
                    leak[k.boundary] = 0
                fm[i] += leak
                observe("membrane_flux", i)
                vgj = vm[k.partner] - vm[np.arange(m)]
                egj = -vgj / k.gap_length_m
                exy = np.column_stack((egj * ck.normal_xy[:, 0], egj * ck.normal_xy[:, 1]))
                opening = forcing.junction_block * np.ones(m) * k.gap_weights
                gap = _electroflux(
                    membrane[i][np.arange(m)],
                    membrane[i][k.partner],
                    k.gap_diffusion_m2_s[i] * k.gap_surface_fraction * opening,
                    k.gap_length_m * np.ones(m),
                    ck.valence[i] * np.ones(m),
                    vgj,
                    p["configured_temperature_K"],
                    ck.F_C_mol,
                    k.R_J_mol_K,
                    1,
                )
                gap[k.boundary] = 0
                fg[i] = fg[i] + gap
                observe("junction_flux", i)
                before = env[i].copy()
                image = env[i].reshape(g.shape)
                image[:, 0] = forcing.boundary_mol_m3[i]
                image[:, -1] = forcing.boundary_mol_m3[i]
                image[0, :] = forcing.boundary_mol_m3[i]
                image[-1, :] = forcing.boundary_mol_m3[i]
                clamped = image.copy()
                observe("ecm_clamp", i)
                gx, gy = geometry_source.gradient(image, delta)
                ux = forcing.velocity_x_m_s if k.fluid_flow else np.zeros(g.shape)
                uy = forcing.velocity_y_m_s if k.fluid_flow else np.zeros(g.shape)
                diffusion = k.environment_diffusion_m2_s[i].reshape(
                    g.shape
                ) * k.tight_junction_modulator[i].reshape(g.shape)
                alpha = (
                    diffusion
                    * ck.valence[i]
                    * p["q_C"]
                    / (p["kb_J_K"] * forcing.runtime_temperature_K)
                )
                fx = (
                    -diffusion * gx
                    - alpha * -forcing.electric_x_source * image
                    + ux * image
                    - 0.0 * image * -forcing.electric_x_source
                )
                fy = (
                    -diffusion * gy
                    - alpha * -forcing.electric_y_source * image
                    + uy * image
                    - 0.0 * image * -forcing.electric_y_source
                )
                fx_all[i], fy_all[i] = (fx.ravel(), fy.ravel())
                div = geometry_source.source_diff(-fx, delta, 0) + geometry_source.source_diff(
                    -fy, delta, 1
                )
                euler = image + div * forcing.dt_s
                result = _smooth(euler, k.sharpness) if k.sharpness < 1 else euler
                environment_records.append(
                    ECMRecord(
                        cb.ion_ids[i],
                        *(
                            freeze(value)
                            for value in (
                                before,
                                clamped,
                                gx,
                                gy,
                                diffusion,
                                alpha,
                                fx,
                                fy,
                                div,
                                euler,
                                result,
                            )
                        ),
                    )
                )
                clamp[i] = np.sum((clamped.ravel() - before) * volume)
                collocated[i] = np.sum((euler - clamped) * volume)
                smoothing[i] = np.sum((result - euler) * volume)
                env[i] = result.ravel()
                observe("ecm_commit", i)
                membrane[i] = cell[i][ck.owner] * 1
                observe("refresh_at_mem", i)
            fm += forcing.supplied_late_membrane_flux_mol_m2_s
            observe("supplied_late_flux")
            if on_network is not None:
                on_network(
                    [cell, membrane, env, vm, fm, fg, fx_all, fy_all, vgj, egj, exy, opening]
                )
                observe("ecm_grn_dispatch")
            for i in k.moving:
                dc = np.dot(ck.owner_sum, fm[i] * ck.membrane_area_m2) / cell_volume
                cell[i] = cell[i] + dc * forcing.dt_s
                membrane[i] = cell[i][ck.owner]
                if k.fast_update_ecm:
                    last_flux = np.zeros(math.prod(g.shape))
                    last_flux[g.membrane_to_grid] = -fm[i]
                    de = last_flux * g.membrane_area_per_site_m2 / volume
                else:
                    de = np.dot(g.membrane_divergence_map_m2, -fm[i]) / (
                        p["cell_height_m"] * delta**2
                    )
                env[i] = env[i] + de * forcing.dt_s
                environment_exchange[i] = np.sum(de * forcing.dt_s * volume)
                observe("membrane_commit", i)
                dg = np.dot(ck.owner_sum, -fg[i] * ck.membrane_area_m2) / cell_volume
                cell[i] += forcing.dt_s * dg
                observe("junction_commit", i)
                negative, nan = (cell[i] < 0, np.isnan(cell[i]))
                clip[i] = np.sum(np.where(negative, -cell[i], 0) * cell_volume)
                cell[i][negative] = 0
                if np.any(nan):
                    observe("clip_bulk_failure", i)
                    failure = "Native no_negs sees NaN after negative-value clipping"
                    break
                observe("clip_bulk", i)
        candidate = State(binding.identity, parent.step_index + 1, frames[-1].values, "")
        candidate = replace(candidate, identity=current._digest(state_record(candidate)))
        membrane_transfer = forcing.dt_s * np.sum(fm * ck.membrane_area_m2, axis=1)
        gap_transfer = forcing.dt_s * np.sum(fg * ck.membrane_area_m2, axis=1)
        cell_change = np.sum((cell - parent.values.cell_mol_m3) * cell_volume, axis=1)
        env_change = np.sum((env - parent.values.environment_mol_m3) * volume, axis=1)
        committed = np.zeros(s, dtype=bool)
        for frame in frames:
            if frame.stage in ("clip_bulk", "clip_bulk_failure"):
                committed[cb.ion_ids.index(frame.ion_id)] = True
        expected_cell = np.where(committed, membrane_transfer - gap_transfer + clip, 0)
        diagnostics = freeze(
            dict(
                finite=bool(
                    all((np.isfinite(v).all() for frame in frames for v in frame.values))
                    and all((np.isfinite(v).all() for row in environment_records for v in row[1:]))
                ),
                boundary_clamp_change_mol=clamp,
                collocated_transport_change_mol=collocated,
                smoothing_change_mol=smoothing,
                membrane_transfer_mol=membrane_transfer,
                native_environment_exchange_mol=environment_exchange,
                conservative_environment_exchange_mol=-np.where(committed, membrane_transfer, 0),
                fast_exchange_defect_mol=environment_exchange
                + np.where(committed, membrane_transfer, 0),
                gap_net_outward_mol=gap_transfer,
                clipping_added_mol=clip,
                cell_change_mol=cell_change,
                environment_change_mol=env_change,
                cell_accounting_residual_mol=cell_change - expected_cell,
                environment_accounting_residual_mol=env_change
                - (clamp + collocated + smoothing + environment_exchange),
                membrane_bulk_difference_mol_m3=membrane - cell[:, ck.owner],
                source_voltage_nonce_delta_V=vm - parent.values.voltage_V,
                negative_environment_retained=bool(np.any(env < 0)),
                negative_membrane_retained=bool(np.any(membrane < 0)),
                committed_moving_ions=committed,
                geometry_derived=True,
                pump_gate_field_seams_supplied=True,
                field_or_voltage_feedback=False,
                physical_material_or_energy_parity=False,
            )
        )
        diagnostics = freeze(
            dict(diagnostics)
            | dict(
                finite=diagnostics["finite"]
                and all(
                    (
                        np.isfinite(value).all()
                        for value in diagnostics.values()
                        if isinstance(value, np.ndarray)
                    )
                )
            )
        )
        trial = Trial(
            binding.identity,
            parent.identity,
            forcing,
            tuple(frames),
            tuple(environment_records),
            candidate,
            diagnostics,
            "",
        )
        trial = replace(trial, identity=current._digest(trial_record(trial)))
        if failure or not diagnostics["finite"]:
            raise ValueError(failure or "Nonfinite literal native ECM material trial")
        return trial
    except Exception as error:
        if on_failure is not None:
            on_failure(locals())
        raise ECMTransportRejected(
            error,
            stage="material_trial" if trial is not None else "source",
            parent=parent,
            drive=forcing,
            trial=trial,
        ) from error


@dataclass(frozen=True)
class Binding:
    material_binding: object
    inputs: object
    identity: str


@dataclass(frozen=True)
class NetworkState:
    binding_identity: str
    material: object
    network_cache: object
    controls: object
    identity: str


class ECMNetworkRejected(RuntimeError):
    def __init__(self, error, partial):
        super().__init__(str(error))
        self.partial = freeze(partial)


def _state(binding, parent, cache, controls):
    cache, controls = freeze(cache), freeze(controls)
    return NetworkState(
        binding.identity,
        parent,
        cache,
        controls,
        ions.digest((binding.identity, parent, cache, controls)),
    )


def bind(inputs):
    inputs = ions.data(inputs)
    mb = material.bind(inputs["definition"])
    source.validate(inputs["network"], mb)
    if len(inputs["steps"]) != 3:
        raise ValueError("Require three declared bounded ECM network calls")
    for row in inputs["steps"]:
        if type(row["publication"]) is not bool:
            raise ValueError("Require actual source publication flags")
        material.drive(mb, row["material"])
    return Binding(mb, freeze(inputs), ions.digest((mb.identity, inputs)))


def make_context(binding, values, definition, packet=None):
    mb = binding.material_binding
    gb, k = mb.geometry_binding, mb.kernel
    cb, g = gb.current_binding, gb.geometry
    external = gb.definition
    ep = external["parameters"]
    arrays = [np.asarray(value, np.float64) for value in values]
    sim = SimpleNamespace(
        **{attr: arrays[Values._fields.index(key)] for key, attr in source.MATERIAL_PAIRS},
        mdl=len(cb.membrane_ids),
        edl=math.prod(g.shape),
        zs=cb.kernel.valence,
        Dm_cells=k.membrane_diffusion_m2_s,
        D_gj=k.gap_diffusion_m2_s,
        D_env=k.environment_diffusion_m2_s,
        TJ_modulator=k.tight_junction_modulator,
    )
    sim.E_gj_x, sim.E_gj_y = arrays[10][:, 0], arrays[10][:, 1]
    owner = cb.kernel.owner
    cells = SimpleNamespace(
        cell_i=np.arange(len(cb.cell_ids)),
        mem_i=np.arange(len(cb.membrane_ids)),
        mem_to_cells=owner,
        nn_i=k.partner,
        bflags_mems=k.boundary,
        gj_len=k.gap_length_m,
        mem_sa=cb.kernel.membrane_area_m2,
        cell_sa=cb.kernel.cell_area_m2,
        cell_vol=np.asarray(external["geometry"]["cell_volume_m3"], np.float64),
        cell_centres=np.asarray(external["geometry"]["cell_centres_m"], np.float64),
        mem_mids_flat=np.asarray(external["geometry"]["membrane_midpoints_m"], np.float64),
        X=g.X_m,
        Y=g.Y_m,
        xypts=g.grid_points_m,
        delta=g.delta_m,
        map_mem2ecm=g.membrane_to_grid,
        M_sum_mems=cb.kernel.owner_sum,
        memSa_per_envSquare=g.membrane_area_per_site_m2,
        M_divmap_mem2ecm=g.membrane_divergence_map_m2,
        ecm_vol=ep["cell_height_m"] * g.delta_m**2,
    )
    p = SimpleNamespace(
        is_ecm=True,
        F=cb.kernel.F_C_mol,
        R=k.R_J_mol_K,
        T=ep["configured_temperature_K"],
        q=ep["q_C"],
        kb=ep["kb_J_K"],
        cell_height=ep["cell_height_m"],
        tm=k.membrane_thickness_m,
        cluster_open=k.cluster_open,
        fast_update_ecm=k.fast_update_ecm,
        sharpness=k.sharpness,
        fluid_flow=False,
        dt=0.0,
    )
    m, e = len(cb.membrane_ids), math.prod(g.shape)
    sim.T = p.T
    sim.rho_channel = np.ones(m)
    sim.gj_block = np.asarray(definition["initial_controls"]["gj_block"], np.float64).copy()
    sim.NaKATP_block = np.asarray(definition["initial_controls"]["NaKATP_block"], np.float64).copy()
    sim.c_env_bound = np.asarray(definition["initial_ion_boundary"], np.float64).copy()
    for key, size in (
        ("extra_rho_cells", len(cb.cell_ids)),
        ("extra_rho_env", e),
        ("extra_J_mem", m),
        ("extra_Jenv_x", e),
        ("extra_Jenv_y", e),
    ):
        setattr(sim, key, np.zeros(size))
    sim.E_env_x, sim.E_env_y = np.zeros(g.shape), np.zeros(g.shape)
    if packet is not None:
        p.dt, sim.T = packet.dt_s, packet.runtime_temperature_K
        sim.rho_channel = packet.channel_multiplier
        sim.c_env_bound = packet.boundary_mol_m3.copy()
        sim.E_env_x, sim.E_env_y = packet.electric_x_source, packet.electric_y_source
    return source.augment(sim, cells, p, definition, list(cb.ion_ids))


def _failure_snapshot(ctx, supplied_cache):
    # Supplied input and the original exception chain remain authoritative.
    # Capture diagnostics independently: no missing/partial owner is promoted
    # to a valid complete cache, and a diagnostic failure cannot mask the cause.
    result = dict(
        cache=None, supplied_cache=supplied_cache, available_context=None, capture_errors=[]
    )
    if ctx is None:
        return result
    owner = getattr(ctx.sim, "grn", None)
    core = getattr(owner, "core", None)
    available = dict(
        owner_available=owner is not None,
        core_available=core is not None,
        complete_owner_cache_claimed=False,
    )
    result["available_context"] = available
    for label, capture in (
        ("material", lambda: source.material_values(ctx.sim)),
        ("wire", lambda: source.wire(owner, ctx.sim)),
        (
            "coefficient_fields",
            lambda: {
                name: source.clone(getattr(ctx.sim, name))
                for name in ("D_env_weight", "D_env_weight_base", "TJ_targets")
                if hasattr(ctx.sim, name)
            },
        ),
    ):
        try:
            available[label] = capture()
        except Exception as capture_error:
            result["capture_errors"].append(
                dict(field=label, type=type(capture_error).__name__, message=str(capture_error))
            )
    if owner is not None and core is not None:
        try:
            result["cache"] = source.cache(ctx)
        except Exception as capture_error:
            result["capture_errors"].append(
                dict(field="cache", type=type(capture_error).__name__, message=str(capture_error))
            )
    return result


def initialize(binding):
    parent = material.state(binding.material_binding, ions.data(binding.inputs["initial"]))
    definition = ions.data(binding.inputs["network"])
    ctx = make_context(binding, parent.values, definition)
    try:
        cached = source.cold(ctx)
    except Exception as error:
        raise ECMNetworkRejected(
            error, dict(stage="cold", material=parent, **_failure_snapshot(ctx, None))
        ) from error
    return _state(binding, parent, cached, definition["initial_controls"])


def advance(binding, parent, *, before_network=None):
    if parent.binding_identity != binding.identity or parent.identity != ions.digest(
        (binding.identity, parent.material, parent.network_cache, parent.controls)
    ):
        raise ValueError("Changed ECM network parent")
    row = ions.data(binding.inputs["steps"][parent.material.step_index])
    control = (
        ions.data(parent.controls)
        if row["scheduled_controls"] is None
        else row["scheduled_controls"]
    )
    forcing = material.drive(
        binding.material_binding, dict(row["material"], junction_block=control["gj_block"])
    )
    holder = {}

    def network(arrays):
        ctx = make_context(binding, arrays, ions.data(binding.inputs["network"]), forcing)
        holder["ctx"] = ctx
        source.restore(ctx, parent.network_cache)
        ctx.sim.gj_block = np.asarray(control["gj_block"], np.float64).copy()
        ctx.sim.NaKATP_block = np.asarray(control["NaKATP_block"], np.float64).copy()
        source.run_dispatch(
            ctx, ions.data(binding.inputs["definition"]), row["publication"], before_network
        )

    def failed(local):
        holder["material_partial"] = dict(
            frames=tuple(local.get("frames", ())),
            environment_records=tuple(local.get("environment_records", ())),
        )

    try:
        trial = material_step(
            binding.material_binding,
            parent.material,
            forcing,
            on_network=network,
            on_failure=failed,
        )
        ctx = holder["ctx"]
    except Exception as error:
        ctx = holder.get("ctx")
        partial = dict(
            stage="network" if ctx is not None else "material",
            material=holder.get("material_partial"),
            network=None if ctx is None else ctx.trace,
            **_failure_snapshot(ctx, parent.network_cache),
        )
        raise ECMNetworkRejected(error, partial) from error
    candidate = _state(binding, trial.candidate, source.cache(ctx), ctx.trace["controls_after"])
    return candidate, trial, freeze(ctx.trace)
