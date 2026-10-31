"""Native ECM CaATP between ion refresh and GRN, with full field feedback.

Ca_dyn remains source-disabled. Maintained pools and kinetic constants derive
from native producers; ER physiology and finite-fuel chemistry are separate.
"""

import math
from dataclasses import dataclass, replace

import numpy as np

from cells.processes import betse_calcium_atp_source as calcium_source
from cells.processes import betse_ecm_grn_join as network
from cells.processes import betse_ecm_grn_source as source
from cells.processes import betse_ecm_transport as material
from cells.processes import betse_environment_field as geometry_source
from cells.processes import betse_normal_current as current
from cells.processes import betse_normal_ecm_field_join as full
from cells.processes import betse_normal_ion_join as ions

LAW_ID = "betse_normal_ecm_calcium_field_join_v1_5_0@1"
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
def _material_step(binding, parent, forcing, *, on_network, on_failure, on_calcium):
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
            on_calcium([cell, membrane, env, vm, fm, fg, fx_all, fy_all, vgj, egj, exy, opening])
            observe("calcium_handler")
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


def run_dispatch(ctx, material_declaration, publication, source_time_s, observer=None):
    ctx.p.substances_affect_charge = publication
    ctx.phase.kind = "SIM"
    ctx.net = ctx.sim.grn.core
    source.attach(ctx, material_declaration, observer)
    try:
        source.science()["dispatch"](ctx.sim, source_time_s, ctx.phase, ctx.cells, ctx.p)
        ctx.trace["source_completed"] = True
    finally:
        ctx.trace.update(
            cache_after=source.cache(ctx),
            values_after=source.material_values(ctx.sim),
            controls_after=dict(
                gj_block=source.clone(ctx.sim.gj_block),
                NaKATP_block=source.clone(ctx.sim.NaKATP_block),
            ),
            owner_after=source.owner_evidence(ctx),
            completed_transports=sum(
                (row["stage"] == "transport_after" for row in ctx.trace["molecule_frames"])
            ),
        )
    return ctx.trace


@dataclass(frozen=True)
class Binding:
    material_binding: object
    voltage_binding: object
    inputs: object
    calcium: object
    identity: str


@dataclass(frozen=True)
class RateCache:
    present: bool
    value: object


@dataclass(frozen=True)
class Clock:
    source_times_s: object
    call_index: int
    material_dt_sum_s: float


@dataclass(frozen=True)
class CalciumFieldState:
    binding_identity: str
    network: object
    field: object
    rate_cache: RateCache
    clock: Clock
    identity: str


class CalciumJoinRejected(RuntimeError):
    def __init__(self, error, partial):
        super().__init__(str(error))
        self.partial = freeze(partial)


def parameters(binding):
    # Original Parameters producers, individually authenticated by static AST.
    return dict(
        cATP=1.5,
        cADP=0.1,
        cPi=0.1,
        KmCa_Ca=1.0e-3,
        KmCa_ATP=0.5,
        deltaGATP=-37000,
        alpha_Ca=binding.calcium["alpha_Ca"],
        F=96485,
        R=8.314,
    )


def native_policy(ctx, binding):
    # Native cold producers. No source path initializes rate_CaATP here.
    ctx.p.Ca_dyn = False
    ctx.sim.CaATP_block = np.ones(ctx.sim.mdl)
    ctx.sim.rho_pump = 1
    ctx.sim.met_concs = None
    ctx.sim.endo_retic = None
    for key, value in parameters(binding).items():
        setattr(ctx.p, key, value)
    return dict(
        Ca_dyn=ctx.p.Ca_dyn,
        CaATP_block=ctx.sim.CaATP_block,
        rho_pump=ctx.sim.rho_pump,
        met_concs=ctx.sim.met_concs,
        endo_retic=ctx.sim.endo_retic,
        rate_CaATP_present=hasattr(ctx.sim, "rate_CaATP"),
        parameters=parameters(binding),
    )


def bind(raw):
    raw = ions.data(raw)
    if (
        set(raw) != {"kind", "case_id", "case_role", "field", "calcium"}
        or raw["kind"] != "cells.normal_ecm_calcium_join_inputs@1"
    ):
        raise ValueError("Require separately declared native ECM calcium composition")
    policy = raw["calcium"]
    if (
        set(policy) != {"kind", "Ca_dyn", "alpha_Ca", "provenance"}
        or policy["kind"] != "cells.native_ECM_CaATP_configuration@1"
    ):
        raise ValueError("Derive native maintained pools, Km, blocks and rate-cache absence")
    if type(policy["Ca_dyn"]) is not bool or policy["Ca_dyn"] is not False:
        raise ValueError("Native ordinary ER is disabled; no forced Ca_dyn or missing kinetics")
    if (
        type(policy["alpha_Ca"]) not in (int, float)
        or not math.isfinite(policy["alpha_Ca"])
        or policy["alpha_Ca"] < 0
    ):
        raise ValueError("Require finite nonnegative configured native alpha_Ca")
    if not isinstance(policy["provenance"], str) or not policy["provenance"].strip():
        raise ValueError("Require calcium source provenance")
    declared_ions = raw["field"]["definition"]["environment_geometry_definition"][
        "current_definition"
    ]["ions"]
    if (
        "Ca" not in declared_ions["ids"]
        or declared_ions["valence"][declared_ions["ids"].index("Ca")] != 2
    ):
        raise ValueError("Require a real Ca+2 ion role and complete material arrays")
    base = full.bind(raw["field"])
    cb = base.material_binding.geometry_binding.current_binding
    if "Ca" not in cb.ion_ids or cb.kernel.valence[cb.ion_ids.index("Ca")] != 2:
        raise ValueError("Require a real Ca+2 ion role and complete material arrays")
    if cb.kernel.F_C_mol != 96485 or base.material_binding.kernel.R_J_mol_K != 8.314:
        raise ValueError("Require the original native CaATP F and R producers")
    dt = base.inputs["bootstrap"]["dt_s"]
    if any(row["material"]["dt_s"] != dt for row in base.inputs["steps"]):
        raise ValueError("Require one configured dt for the actual normal source clock")
    result = Binding(
        base.material_binding,
        base.voltage_binding,
        base.inputs,
        freeze(policy),
        "",
    )
    return replace(result, identity=ions.digest(composition_record(result)))


def composition_record(binding):
    return (
        LAW_ID,
        binding.material_binding.identity,
        binding.voltage_binding.identity,
        binding.inputs,
        binding.calcium,
    )


def validate_composition(binding):
    if type(binding) is not Binding or binding.identity != ions.digest(composition_record(binding)):
        raise ValueError("Require an unchanged owned calcium composition binding")


def record(parent):
    return (parent.binding_identity, parent.network, parent.field, parent.rate_cache, parent.clock)


def joined_state(binding, network, fields, rate_cache, clock):
    result = CalciumFieldState(binding.identity, network, fields, rate_cache, clock, "")
    return replace(result, identity=ions.digest(record(result)))


def initialize(binding, *, after_cold=None, before_field=None):
    validate_composition(binding)
    parent = material.state(binding.material_binding, ions.data(binding.inputs["initial"]))
    working = Values(*(np.array(v, copy=True) for v in parent.values))
    ctx = network.make_context(binding, working, ions.data(binding.inputs["network"]))
    policy = native_policy(ctx, binding)
    try:
        cached = source.cold(ctx)
    except Exception as error:
        raise CalciumJoinRejected(
            error, dict(stage="cold", policy=policy, **network._failure_snapshot(ctx, None))
        ) from error
    parent = material.state(binding.material_binding, source.material_values(ctx.sim))
    initial = network._state(
        binding, parent, cached, ions.data(binding.inputs["network"])["initial_controls"]
    )
    dt = binding.inputs["bootstrap"]["dt_s"]
    clock = Clock(ions.freeze(np.linspace(0, 3 * dt, 3)), 0, 0.0)
    rate = RateCache(False, None)
    if after_cold is not None:
        after_cold(freeze(dict(network=initial, policy=policy, rate_cache=rate, clock=clock)))
    try:
        prepared, fields = full.reconstruct(
            binding,
            initial,
            dt,
            ions.data(binding.inputs["bootstrap"]["boundary_V"]),
            "bootstrap",
            before_field,
        )
    except full.FieldJoinRejected as error:
        raise CalciumJoinRejected(
            error, dict(stage="bootstrap", partial=error.partial, rate_cache=rate, clock=clock)
        ) from error
    return joined_state(binding, prepared, fields, rate, clock)


def calcium(binding, arrays, forcing, incoming, clock, observer=None):
    values = {
        key: ions.freeze(np.asarray(value))
        for key, value in zip(Values._fields, arrays, strict=True)
    }
    cb = binding.material_binding.geometry_binding.current_binding
    i = cb.ion_ids.index("Ca")
    mapping = binding.material_binding.geometry_binding.geometry.membrane_to_grid
    before = dict(
        mode="calcium",
        definition=ions.data(binding.inputs["definition"]),
        values_before=values,
        parameters=parameters(binding),
        alpha_Ca=binding.calcium["alpha_Ca"],
        rate_cache_before=ions.data(incoming),
        clock=ions.data(clock),
        dt_s=forcing.dt_s,
        runtime_temperature_K=forcing.runtime_temperature_K,
        block_unused=np.ones(len(cb.membrane_ids)),
        rho_pump=1,
        met_unused=None,
        Ca_dyn=False,
        ER_executed=False,
    )
    if observer is not None:
        observer(source.clone(before))
    phase = dict(
        before=freeze(before), helper=None, source_completed=False, rate_cache_after=incoming
    )
    membrane, env, vm, fm = arrays[1], arrays[2], arrays[3], arrays[4]
    rate = incoming
    try:
        if binding.calcium["alpha_Ca"] > 0:
            core = None
            try:
                core = calcium_source.evaluate(
                    membrane_mM=membrane[i],
                    bath_mM=env[i][mapping],
                    voltage_V=vm,
                    runtime_temperature_K=forcing.runtime_temperature_K,
                    parameters=parameters(binding),
                    block=np.ones(len(cb.membrane_ids)),
                    met=None,
                )
            except calcium_source.CalciumSourceRefused as error:
                core = error.partial
                raise
            finally:
                if core is not None:
                    phase["helper"] = core
                    membrane[i] = core.membrane_after_mM
            # Native ECM co is a fancy-index copy: never copy its clipping back.
            if not core.finite:
                raise ValueError("Nonfinite actual CaATP helper trial; stricter finite admission")
            masked = 1 * core.flux_mol_m2_s.copy()
            if not binding.material_binding.kernel.cluster_open:
                masked[binding.material_binding.kernel.boundary] = 0
            rate = RateCache(True, ions.freeze(masked))
            fm[i] += 1 * masked
        phase.update(
            source_completed=True,
            rate_cache_after=rate,
            source_rate_aliases_handler_flux=binding.calcium["alpha_Ca"] > 0,
            source_rate_aliases_helper_flux=False,
        )
        return rate, freeze(
            dict(
                phase,
                values_after={
                    key: ions.freeze(np.asarray(value))
                    for key, value in zip(Values._fields, arrays, strict=True)
                },
            )
        )
    except Exception as error:
        phase.update(
            values_after={
                key: ions.freeze(np.asarray(value))
                for key, value in zip(Values._fields, arrays, strict=True)
            }
        )
        raise CalciumJoinRejected(error, dict(stage="calcium", phase=phase)) from error


def advance(
    binding,
    parent,
    *,
    before_material=None,
    before_calcium=None,
    before_network=None,
    before_field=None,
    after_calcium=None,
    after_material=None,
):
    validate_composition(binding)
    if (
        type(parent) is not CalciumFieldState
        or parent.binding_identity != binding.identity
        or parent.identity != ions.digest(record(parent))
    ):
        raise ValueError("Require the unchanged owned calcium/field parent")
    fields = parent.field
    if (
        type(fields) is not full.FieldStage
        or fields.binding_identity != binding.identity
        or fields.identity != ions.digest(full.field_record(fields))
    ):
        raise ValueError("Require the actual previous reconstructed full field")
    rate = parent.rate_cache
    m = len(binding.material_binding.geometry_binding.current_binding.membrane_ids)
    if (
        type(rate) is not RateCache
        or type(rate.present) is not bool
        or (
            rate.value is not None
            if not rate.present
            else not isinstance(rate.value, np.ndarray)
            or rate.value.shape != (m,)
            or rate.value.dtype != np.float64
            or rate.value.flags.writeable
            or not np.isfinite(rate.value).all()
        )
    ):
        raise ValueError(
            "Require actual rate-cache absence or complete immutable source-written rate"
        )
    index = parent.network.material.step_index
    expected_rate_present = binding.calcium["alpha_Ca"] > 0 and index > 0
    if rate.present is not expected_rate_present:
        raise ValueError(
            "Require actual rate-cache absence or complete immutable source-written rate"
        )
    dt = binding.inputs["bootstrap"]["dt_s"]
    if (
        type(parent.clock) is not Clock
        or not isinstance(parent.clock.source_times_s, np.ndarray)
        or parent.clock.source_times_s.dtype != np.float64
        or parent.clock.source_times_s.shape != (3,)
        or parent.clock.source_times_s.flags.writeable
        or parent.clock.call_index != index
        or parent.clock.material_dt_sum_s != index * dt
        or not np.array_equal(parent.clock.source_times_s, np.linspace(0, 3 * dt, 3))
    ):
        raise ValueError("Require original normal time vector and accumulated material dt")
    row = ions.data(binding.inputs["steps"][index])
    control = (
        ions.data(parent.network.controls)
        if row["scheduled_controls"] is None
        else row["scheduled_controls"]
    )
    packet = dict(
        row["material"],
        junction_block=control["gj_block"],
        electric_x_source=fields.environment.values.electric_x_source,
        electric_y_source=fields.environment.values.electric_y_source,
    )
    forcing = material.drive(binding.material_binding, packet)
    material_inputs = dict(
        mode="material",
        definition=ions.data(binding.inputs["definition"]),
        initial=ions.data(parent.network.material.values._asdict()),
        # Match the native incoming declaration, before Drive's array coercion.
        # The validated immutable forcing remains the numerical input below.
        steps=[source.clone(packet)],
        calcium=ions.data(binding.calcium),
        rate_cache_before=ions.data(rate),
        clock=ions.data(parent.clock),
    )
    if before_material is not None:
        before_material(material_inputs)
    holder = {}

    def on_calcium(arrays):
        try:
            result, phase = calcium(binding, arrays, forcing, rate, parent.clock, before_calcium)
        except CalciumJoinRejected as error:
            holder["calcium_failure"] = error.partial
            raise
        holder.update(rate=result, calcium=phase)
        if after_calcium is not None:
            after_calcium(result, phase)

    def on_network(arrays):
        ctx = network.make_context(binding, arrays, ions.data(binding.inputs["network"]), forcing)
        holder["ctx"] = ctx
        source.restore(ctx, parent.network.network_cache)
        native_policy(ctx, binding)
        if holder["rate"].present:
            ctx.sim.rate_CaATP = holder["rate"].value.copy()
        ctx.sim.gj_block = np.asarray(control["gj_block"], np.float64).copy()
        ctx.sim.NaKATP_block = np.asarray(control["NaKATP_block"], np.float64).copy()
        run_dispatch(
            ctx,
            ions.data(binding.inputs["definition"]),
            row["publication"],
            float(parent.clock.source_times_s[index]),
            before_network,
        )

    def failed(local):
        holder["material_partial"] = dict(
            frames=ions.data(tuple(local.get("frames", ()))),
            environment_records=ions.data(tuple(local.get("environment_records", ()))),
            trial=local.get("trial"),
            diagnostics=local.get("diagnostics"),
            failure=local.get("failure"),
            available_arrays={
                name: value.copy() for name, value in local.items() if isinstance(value, np.ndarray)
            },
        )

    try:
        trial = _material_step(
            binding.material_binding,
            parent.network.material,
            forcing,
            on_network=on_network,
            on_failure=failed,
            on_calcium=on_calcium,
        )
        ctx = holder["ctx"]
        candidate = network._state(
            binding, trial.candidate, source.cache(ctx), ctx.trace["controls_after"]
        )
    except Exception as error:
        ctx = holder.get("ctx")
        raise CalciumJoinRejected(
            error,
            dict(
                stage="material_calcium_network",
                parent=parent,
                inputs=material_inputs,
                material=holder.get("material_partial"),
                calcium=holder.get("calcium"),
                calcium_failure=holder.get("calcium_failure"),
                network=None if ctx is None else ctx.trace,
                inner_partial=getattr(error, "partial", None),
                **network._failure_snapshot(ctx, parent.network.network_cache),
            ),
        ) from error
    if after_material is not None:
        after_material(candidate, trial, ctx.trace, holder["calcium"])
    try:
        prepared, next_fields = full.reconstruct(
            binding, candidate, forcing.dt_s, row["boundary_V"], "field", before_field
        )
    except full.FieldJoinRejected as error:
        raise CalciumJoinRejected(
            error,
            dict(
                stage="field",
                parent=parent,
                material_parent=candidate,
                trial=trial,
                calcium=holder["calcium"],
                network=ctx.trace,
                partial=error.partial,
            ),
        ) from error
    clock = Clock(parent.clock.source_times_s, index + 1, (index + 1) * dt)
    result = joined_state(binding, prepared, next_fields, holder["rate"], clock)
    return (
        result,
        trial,
        freeze(ctx.trace),
        holder["calcium"],
        dict(
            material_parent=candidate,
            initial_field=fields,
            fields=next_fields,
            clock_before=parent.clock,
            clock_after=clock,
        ),
    )
