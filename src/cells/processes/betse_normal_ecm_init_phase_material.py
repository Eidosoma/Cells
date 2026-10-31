"""Exact common CaATP material body with one INIT post-network mechanics hook.

The hook precedes deferred primary commit and adds no event/protein-noise path.
Shared arithmetic, guards, diagnostics and numeric budgets are unchanged.
"""

from cells.processes import betse_normal_ecm_calcium_join as base

Drive = base.Drive
ECMRecord = base.ECMRecord
ECMTransportRejected = base.ECMTransportRejected
Frame = base.Frame
MAX_STEPS = base.MAX_STEPS
State = base.State
Trial = base.Trial
Values = base.Values
_electroflux = base._electroflux
_smooth = base._smooth
current = base.current
drive = base.drive
freeze = base.freeze
geometry_source = base.geometry_source
math = base.math
np = base.np
replace = base.replace
state = base.state
state_record = base.state_record
trial_record = base.trial_record
validate_binding = base.validate_binding


@np.errstate(all="ignore")
def step_init(binding, parent, forcing, *, on_network, on_failure, on_calcium, on_post_network):
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
            on_post_network(
                [cell, membrane, env, vm, fm, fg, fx_all, fy_all, vgj, egj, exy, opening]
            )
            observe("INIT_post_network")
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
