# ruff: noqa: E501 -- exact capture-adapter source strings.
"""Write source-native event/catalog/noise composition; no scientific execution."""

from pathlib import Path

ROOT = Path("/home/robert/Cells")
FOLDER = ROOT / "validation/betse"
text = (FOLDER / "betse_normal_ecm_catalog_join_native.py").read_text()
text = text.replace(
    "from validation.betse import betse_normal_grn_join_native as archives",
    "from validation.betse import betse_normal_grn_join_native as archives\nfrom validation.betse import betse_normal_ecm_event_join_native_events as event_native",
)
text = text.replace(
    "    active_commit = None",
    "    active_commit = None\n    event_rows,noise_rows=[],[]\n    event_owner=None\n    event_entry=event_result=reset_return=noise_result=None\n    calcium_count=0",
)
# Install actual supplied finalized owner before the cold configured channel reader.
needle = '    network.configure(ctx, declared["catalog"])'
assert needle in text
text = text.replace(needle, needle + "\n    event_owner=event_native.Owner(ctx,declared)")
text = text.replace(
    "    cold_trace = network.clone(ctx.trace)",
    '    cold_trace = network.clone(ctx.trace)\n    cold_event_stores=event_native.snapshot(sim)\n    cold_noise_stream=event_native.manifest(event_owner.rng)\n    cold_noise_cache=dict(present=hasattr(sim,"protein_noise_flux"),value=network.clone(sim.protein_noise_flux) if hasattr(sim,"protein_noise_flux") else None)',
)
# Native cold partials retain event/noise metadata even before the loop starts.
text = text.replace(
    "            cold_trace=network.clone(ctx.trace),",
    "            cold_trace=network.clone(ctx.trace),\n            event_stores=event_native.snapshot(sim),\n            noise_stream=event_native.manifest(event_owner.rng),",
)
start = text.index(
    '            for index, call in enumerate(inputs["steps"][: declared["stop_after_calls"]]):'
)
body_end = text.index('                observe("supplied_pump_flux")', start)
old = text[start:body_end]
# Keep original ordinary/pump/GRN/CaATP/field source code after this boundary.
new = """            for index, call in enumerate(inputs["steps"][:declared["stop_after_calls"]]):
                material_before=material_candidate=post_material_cache=None
                event_entry=event_result=reset_return=noise_result=None
                event_owner.last_event=event_owner.last_noise=None
                calcium_count=len(calcium_rows)
                field_phase="events"
                parameters.dt=call["material"]["dt_s"]
                event_entry=dict(mode="events",owner=network.clone(declared["event_owner"]),
                    before=event_native.snapshot(sim),material_before=values(),clock=clock(index),
                    source_time_s=float(source_times[index]),configured_temperature_K=parameters.T,
                    dt_s=parameters.dt,ion_ids=list(names),valence=sim.zs.copy())
                source["resets"](sim,cells,parameters,float(source_times[index]))
                reset_return=values()
                event_result=event_owner.fire(float(source_times[index]))
                event_rows.append(copy.deepcopy(event_result))
                runtime_definition=network.clone(raw)
                runtime_definition["ions"]["membrane_diffusion_m2_s"]=sim.Dm_cells.copy()
                runtime_definition["ions"]["environment_diffusion_m2_s"]=sim.D_env.copy()
                packet=dict(call["material"],runtime_temperature_K=float(sim.T),
                    boundary_mol_m3=sim.c_env_bound.copy(),
                    junction_block=np.broadcast_to(np.asarray(sim.gj_block,np.float64),(m,)).copy(),
                    channel_multiplier=np.broadcast_to(np.asarray(sim.rho_channel,np.float64),(m,)).copy(),
                    electric_x_source=sim.E_env_x.copy(),electric_y_source=sim.E_env_y.copy())
                preview,preview_after=event_owner.preview(index)
                material_before=dict(mode="material",definition=network.clone(runtime_definition),initial=values(),steps=[network.clone(packet)],
                    calcium=network.clone(declared["calcium"]),rate_cache_before=rate_cache(),clock=clock(index),
                    catalog=network.clone(declared["catalog"]),network_cache=network.cache(ctx),
                    event_stores=event_native.snapshot(sim),noise=network.clone(declared["noise"]),
                    noise_stream_before=event_native.manifest(event_owner.rng),prospective_noise_uniforms=preview,
                    prospective_stream_after=preview_after,prospective_draw_is_uncommitted=True)
                ctx.trace=network.new_trace()
                ctx.trace.update(channel_events=[],channel_initializations=[])
                frames.clear();environment_records.clear()
                field_phase="material_network"
                # The actual original reset ran before events; these only mark the
                # now post-event component input, avoiding a second reset call.
                observe("initial")
                observe("reset_flux")
                for key,native in (("velocity_x_m_s","u_env_x"),("velocity_y_m_s","u_env_y")):
                    setattr(sim,native,np.asarray(packet[key],np.float64).copy())
                sim.fluxes_mem+=np.asarray(packet["supplied_pump_membrane_flux_mol_m2_s"],np.float64)
"""
text = text[:start] + new + text[body_end:]
text = text.replace(
    'run_dispatch(ctx, raw, call["publication"], float(source_times[index]))',
    'run_dispatch(ctx, runtime_definition, call["publication"], float(source_times[index]))',
)
needle = """                observe("ecm_grn_dispatch")
                sim.update_all_concs(cells, parameters)"""
assert needle in text
text = text.replace(
    needle,
    """                observe("ecm_grn_dispatch")
                field_phase="protein_noise"
                noise_result=event_owner.noise()
                noise_rows.append(copy.deepcopy(noise_result))
                observe("protein_noise")
                field_phase="material_network"
                sim.update_all_concs(cells, parameters)""",
)
# Actual event-owned boundary persists, including source same-edge last write.
text = text.replace('                sim.bound_V = dict(call["boundary_V"])\n', "")
text = text.replace(
    """                            material_before=material_before,
                            material_candidate=material_candidate,""",
    """                            material_before=material_before,
                            before_events=event_entry,events=event_result,reset_return=reset_return,
                            event_stores_after=event_native.snapshot(sim),noise=noise_result,
                            noise_stream_after=event_native.manifest(event_owner.rng),
                            noise_cache_after=dict(present=hasattr(sim,"protein_noise_flux"),value=network.clone(sim.protein_noise_flux) if hasattr(sim,"protein_noise_flux") else None),
                            material_candidate=material_candidate,""",
)
text = text.replace(
    """                        calcium=copy.deepcopy(calcium_rows[-1]) if calcium_rows else None,""",
    """                        calcium=copy.deepcopy(calcium_rows[-1]) if len(calcium_rows)>calcium_count else None,
                        before_events=event_entry,events=network.clone(event_owner.last_event),reset_return=reset_return,
                        event_stores_after=event_native.snapshot(sim),noise=network.clone(event_owner.last_noise),
                        noise_stream_after=event_native.manifest(event_owner.rng),""",
)
text = text.replace(
    """        cold_trace=cold_trace,
        cold_policy=cold_policy,""",
    """        cold_trace=cold_trace,
        cold_policy=cold_policy,
        cold_event_stores=cold_event_stores,cold_noise_stream=cold_noise_stream,cold_noise_cache=cold_noise_cache,
        event_rows=event_rows,noise_rows=noise_rows,""",
)
text = text.replace("normal_ecm_catalog_join", "normal_ecm_event_join")
# Preserve the separately authenticated existing catalog native network implementation.
text = text.replace(
    "betse_normal_ecm_event_join_native_network as network",
    "betse_normal_ecm_catalog_join_native_network as network",
)
text = text.replace(
    "Authenticated normal ECM modern catalog/CaATP/GRN/full fields",
    "Authenticated normal ECM events/catalog/CaATP/GRN/noise/full fields",
)
with (FOLDER / "betse_normal_ecm_event_join_native.py").open("x") as stream:
    stream.write(text)
print("Wrote native composition source; scientific namespace not imported/executed")
