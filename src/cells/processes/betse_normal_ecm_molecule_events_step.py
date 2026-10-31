from cells.processes import betse_normal_ecm_molecule_events_material as material_init
from cells.processes import betse_normal_ecm_molecule_events_pump as pump
from cells.processes import betse_normal_ecm_molecule_lifecycle_phase as phase
from cells.processes.betse_normal_ecm_molecule_events import EventsRejected as InitRejected
from cells.processes.betse_normal_ecm_molecule_events import (
    failure_snapshot as phase_failure_snapshot,
)
from cells.processes.betse_normal_ecm_molecule_events import prepare_events, snapshot, state, verify

np, ions, source = (phase.np, phase.ions, phase.source)
material, calcium, network = (phase.material, phase.calcium, phase.network)
mechanical, mechanics, owners = (phase.mechanical, phase.mechanics, phase.owners)
full, setup, calendars = (phase.full, phase.setup, phase.calendars)
Clock, RateCache = (phase.Clock, phase.RateCache)
owner_context, restore_owners = (phase.owner_context, phase.restore_owners)
install_stores, dispatch_owners = (phase.install_stores, phase.dispatch_owners)


def advance(
    binding,
    parent,
    *,
    observer=None,
    before_nak=None,
    before_material=None,
    before_calcium=None,
    after_calcium=None,
    before_mechanics=None,
    after_mechanics=None,
    before_field=None,
    after_material=None,
    handler_observer=None,
    before_commit=None,
    before_events=None,
    after_events=None,
    event_observer=None,
):
    declared = binding
    verify(declared, parent)
    if parent.status != "ready":
        raise ValueError("Require a ready INIT parent with an admitted source call")
    index, holder, stage = (parent.cursor, {}, "before_call_observer")
    dt = binding.calendar.dt_s
    label = float(parent.clock.source_times_s[index])
    row = ions.data(binding.inputs["steps"][index])
    try:
        if observer is not None:
            observer("before_call", parent)
        stage = "events"
        binding, lowered, stores = prepare_events(
            declared, parent, holder, before_events, after_events, event_observer
        )
        stage = "nak"
        nak, flux, proxy = pump.produce(binding, lowered, stores, parent.nak_rate, before_nak)
        holder["nak"] = nak
        if not pump.finite(nak):
            raise ValueError("Nonfinite complete ordinary INIT NaK output")
        stores = ions.data(stores)
        packet = dict(
            row["material"],
            supplied_pump_membrane_flux_mol_m2_s=flux,
            runtime_temperature_K=stores["T"],
            boundary_mol_m3=stores["c_env_bound"],
            channel_multiplier=np.broadcast_to(stores["rho_channel"], (len(flux[0]),)).copy(),
            junction_block=np.broadcast_to(stores["gj_block"], (len(flux[0]),)).copy(),
            electric_x_source=parent.field.environment.values.electric_x_source,
            electric_y_source=parent.field.environment.values.electric_y_source,
        )
        forcing = material.drive(binding.material_binding, packet)
        incoming = dict(
            mode="material",
            definition=ions.data(binding.inputs["definition"]),
            initial=ions.data(lowered.values._asdict()),
            steps=[source.clone(packet)],
            calcium=ions.data(binding.calcium),
            rate_cache_before=ions.data(parent.rate_cache),
            clock=ions.data(parent.clock),
            catalog=ions.data(binding.catalog),
            network_cache=ions.data(parent.network.network_cache),
            nak_before=ions.data(nak["before"]),
            source_phase=binding.calendar.phase,
            legacy_run_sim=binding.calendar.phase == "SIM",
        )
        holder["material_input"] = incoming
        stage = "before_material"
        if before_material is not None:
            before_material(ions.freeze(incoming))

        def on_calcium(arrays):
            holder["stage"] = "calcium"
            result, phase = calcium.calcium(
                binding, arrays, forcing, parent.rate_cache, parent.clock, before_calcium
            )
            holder.update(rate=result, calcium=phase)
            if after_calcium is not None:
                after_calcium(result, phase)

        def on_network(arrays):
            holder["stage"] = "network"
            ctx = owner_context(binding, arrays, forcing)
            holder["ctx"] = ctx
            restore_owners(ctx, parent.network.network_cache, index)
            calcium.native_policy(ctx, binding)
            install_stores(ctx, stores)
            ctx.p.dt = dt
            ctx.sim.rate_NaKATP = proxy.copy()
            if holder["rate"].present:
                ctx.sim.rate_CaATP = holder["rate"].value.copy()
            ctx.trace.update(
                source_phase=binding.calendar.phase, legacy_run_sim=binding.calendar.phase == "SIM"
            )
            dispatch_owners(
                ctx,
                ions.data(binding.inputs["definition"]),
                row["publication"],
                label,
                handler_observer,
            )
            owners.validate_phase_cache(ctx, owners.cache(ctx), index + 1)

        def on_post_network(arrays):
            holder["stage"] = "mechanics"
            ctx = holder["ctx"]
            incoming_mech = mechanical.mechanics_input(binding, parent, ctx, index)
            holder["mechanics_input"] = ions.freeze(incoming_mech)
            if before_mechanics is not None:
                before_mechanics(
                    ions.freeze(
                        dict(
                            mode="mechanics",
                            definition=binding.mechanics.definition,
                            initial=parent.mechanics.cache,
                            steps=[incoming_mech],
                        )
                    )
                )
            try:
                trial = mechanics.step(binding.mechanics, parent.mechanics, incoming_mech)
            except Exception as error:
                holder["mechanics_failure"] = getattr(error, "trial", None)
                raise
            holder["mechanics_trial"] = trial
            if after_mechanics is not None:
                after_mechanics(trial)
            holder["before_commit"] = ions.freeze(
                dict(
                    mode="commit",
                    definition=ions.data(binding.inputs["definition"]),
                    values_before=source.material_values(ctx.sim),
                    initial=ions.data(lowered.values._asdict()),
                    steps=[source.clone(packet)],
                    material_inputs=incoming,
                    source_phase=binding.calendar.phase,
                    legacy_run_sim=binding.calendar.phase == "SIM",
                )
            )
            if before_commit is not None:
                before_commit(holder["before_commit"])

        def failed(local):
            holder["material_partial"] = dict(
                frames=local.get("frames"),
                environment_records=local.get("environment_records"),
                trial=local.get("trial"),
                diagnostics=local.get("diagnostics"),
                failure=local.get("failure"),
                available_arrays={
                    k: v.copy() for k, v in local.items() if isinstance(v, np.ndarray)
                },
            )

        stage = "material_calcium_network_mechanics"
        trial = material_init.step_init(
            binding.material_binding,
            lowered,
            forcing,
            on_network=on_network,
            on_failure=failed,
            on_calcium=on_calcium,
            on_post_network=on_post_network,
        )
        holder["material_trial"] = trial
        ctx = holder["ctx"]
        candidate = network._state(
            binding, trial.candidate, owners.cache(ctx), ctx.trace["controls_after"]
        )
        holder["material_candidate"] = candidate
        if after_material is not None:
            after_material(candidate, trial, ctx.trace, holder["calcium"])
        stage = "field"
        prepared, fields = full.reconstruct(
            binding, candidate, dt, source.clone(ctx.sim.bound_V), "field", before_field
        )
        stores = snapshot(ctx)
        for key in ("gj_block", "NaKATP_block"):
            stores[key] = source.clone(ctx.trace["controls_after"][key])
        stores["div_u_osmo"] = ions.data(holder["mechanics_trial"].candidate.cache["div_u_osmo"])
        sampled = bool(calendars.window(binding.calendar, start=index, stop=index + 1).sampled[0])
        receipt = ions.freeze(
            dict(
                call_index=index,
                source_label_s=label,
                dt_s=dt,
                material_dt_sum_s=(index + 1) * dt,
                incoming_identity=parent.identity,
                material_candidate_identity=candidate.identity,
                source_phase=binding.calendar.phase,
                legacy_run_sim=binding.calendar.phase == "SIM",
                sample_eligible=sampled,
                event_fire_calls=1,
                protein_noise_calls=0,
                pre_event_flux_reset_calls=1,
                event_owner_identity=ions.digest(declared.raw["event_owner"]),
                event_trace=holder["events"],
                after_network_identity=prepared.identity,
                after_field_identity=fields.identity,
            )
        )
        observations = parent.observations
        if sampled:
            observations += (
                ions.freeze(
                    dict(
                        call_index=index,
                        source_label_s=label,
                        elapsed_end_s=(index + 1) * dt,
                        network=prepared,
                        field=fields,
                        mechanics=holder["mechanics_trial"].candidate,
                        native_storage_called=False,
                        display_completed=False,
                    )
                ),
            )
        result = state(
            declared,
            prepared,
            fields,
            holder["rate"],
            RateCache(True, proxy),
            holder["mechanics_trial"].candidate,
            stores,
            Clock(parent.clock.source_times_s, index + 1, (index + 1) * dt),
            parent.history + (receipt,),
            observations,
            runtime_material_binding=binding.material_binding,
            runtime_definition=binding.inputs["definition"],
            entry_receipt=parent.entry_receipt,
        )
        verify(declared, result)
        holder["accepted"] = result
        stage = "after_call_observer"
        if observer is not None:
            observer("after_call", result)
        return (
            result,
            ions.freeze(
                {key: value for key, value in holder.items() if key != "ctx"}
                | dict(network=ctx.trace, field=fields, receipt=receipt)
            ),
        )
    except Exception as error:
        ctx = holder.get("ctx")
        raise InitRejected(
            error,
            dict(
                stage=stage,
                reached_stage=holder.get("stage"),
                call_index=index,
                parent=parent,
                available={key: value for key, value in holder.items() if key != "ctx"},
                inner_partial=getattr(error, "partial", None),
                root_cause=dict(type=type(error).__name__, message=str(error)),
                **phase_failure_snapshot(ctx, parent.network.network_cache),
            ),
        ) from error
