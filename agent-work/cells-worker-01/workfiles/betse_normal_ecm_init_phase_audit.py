"""Pinned ordinary INIT boundary/design audit; never import or evaluate science."""

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
BASE = Path("/mnt/workspaces/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_ecm_init_phase"
NATIVE = BASE / "betse-v1.5.0"
INSTALLED = BASE / "venv-betse/lib/python3.13/site-packages"
PARENT = BASE / "betse-normal-ecm-run-lifecycle-prepared-20261031-02"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def methods(relative, cls):
    tree = ast.parse((NATIVE / relative).read_text())
    body = next(n.body for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    return {n.name: n for n in body if isinstance(n, ast.FunctionDef)}


def functions(path):
    return {n.name: n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)}


def site(relative, node):
    return dict(
        path=relative,
        line=node.lineno,
        end_line=node.end_lineno,
        AST_sha256=hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
        source=ast.unparse(node),
    )


def assign(fn, target):
    return [
        n
        for n in ast.walk(fn)
        if isinstance(n, ast.Assign) and any(ast.unparse(t) == target for t in n.targets)
    ]


def audit():
    pins = {str(p.relative_to(NATIVE)): sha(p) for p in sorted((NATIVE / "betse").rglob("*.py"))}
    assert len(pins) == 332 and all(sha(INSTALLED / p) == h for p, h in pins.items())
    sim = methods("betse/science/sim.py", "Simulator")
    runner = methods("betse/science/simrunner.py", "SimRunner")
    phase = methods("betse/science/phase/phasecls.py", "SimPhase")
    parameters = methods("betse/science/parameters.py", "Parameters")
    networks = methods("betse/science/chemistry/networks.py", "MasterOfNetworks")
    channels = methods("betse/science/chemistry/networks.py", "Channel")
    genes = methods("betse/science/chemistry/gene.py", "MasterOfGenes")
    tissue = methods("betse/science/tissue/tishandler.py", "TissueHandler")
    modulate = functions(NATIVE / "betse/science/math/modulate.py")
    init_text, sim_text = ast.unparse(runner["init"]), ast.unparse(runner["sim"])
    order = (
        "phase_kind = SimPhaseKind.INIT",
        "fh.loadWorld(",
        "self._die_if_seed_differs(",
        "phase = SimPhase(",
        "phase.sim.init_core(phase)",
        "phase.sim.run_sim_core(phase)",
    )
    positions = [init_text.index(v) for v in order]
    assert positions == sorted(positions)
    constructor = next(
        n
        for n in ast.walk(runner["init"])
        if isinstance(n, ast.Call) and ast.unparse(n.func) == "SimPhase"
    )
    assert "sim" not in {k.arg for k in constructor.keywords}
    assert "fh.loadSim(" in sim_text and "sim=sim" in sim_text
    assert "sim = Simulator()" in ast.unparse(phase["__init__"])
    assert (
        ast.unparse(assign(phase["_init_kludge"], "self.p._run_sim")[0].value)
        == "self.kind is SimPhaseKind.SIM"
    )
    assert "self._init_kludge_time()" in ast.unparse(phase["_init_kludge"])
    count = assign(parameters["load"], "self.init_tsteps")
    assert (
        len(count) == 1
        and ast.unparse(count[0].value) == "int(self.init_time_total / self.init_time_step)"
    )
    setup = phase["_init_kludge_time"]
    init_time = next(
        n
        for n in setup.body
        if isinstance(n, ast.If) and ast.unparse(n.test) == "self.kind is SimPhaseKind.INIT"
    )
    assert [ast.unparse(n) for n in init_time.body] == [
        "self.p.dt = self.p.init_time_step",
        "self.p.resample = self.p.init_time_sampling",
        "self.p.total_time = self.p.init_time_total",
    ]
    assert "self.p.t_resample = self.p.resample / self.p.dt" in ast.unparse(setup)
    clock = []
    for node in sim["_plot_loop"].body:
        if isinstance(node, ast.If) and ast.unparse(node.test) == "phase.kind is SimPhaseKind.INIT":
            clock.append(node)
        elif isinstance(node, ast.Assign) and ast.unparse(node.targets[0]) in (
            "phase_time_len",
            "time_steps",
            "time_steps_sampled",
            "i",
        ):
            clock.append(node)
        elif isinstance(node, ast.While):
            clock.append(node)
    assert len(clock) == 6
    body = next(n for n in sim["_run_sim_core_loop"].body if isinstance(n, ast.For))
    guards = [n for n in ast.walk(body) if isinstance(n, ast.If)]
    fire = next(n for n in guards if ast.unparse(n.test) == "phase.kind is SimPhaseKind.SIM")
    noise = next(n for n in guards if "p.dynamic_noise == 1" in ast.unparse(n.test))
    assert "phase.kind is SimPhaseKind.SIM" in ast.unparse(noise.test)
    assert "phase.dyna.fire_events" in ast.unparse(fire)
    stages = [
        "self.fluxes_mem.fill(0)",
        "self.fluxes_gj.fill(0)",
        "stb.pumpNaKATP(",
        "for i in self.movingIons:",
        "self.update_gj(",
        "self.update_ecm(",
        "self.update_intra(",
        "self.ca_handler(",
        "self.molecules.core.clear_run_loop(",
        "self.grn.core.clear_run_loop(",
        "osmotic_P(",
        "getFlow(",
        "getDeformation(",
        "self.update_all_concs(",
        "self.update_V(",
        "stb.check_v(",
        "phase.callbacks.progressed_next()",
        "self.write2storage(",
    ]
    loop_text = ast.unparse(body)
    positions = [loop_text.index(s) for s in stages]
    assert positions == sorted(positions)
    network_blocks = []
    for owner, enabled in (("molecules", "molecules_enabled"), ("grn", "grn_enabled")):
        block = next(n for n in guards if ast.unparse(n.test) == "p." + enabled)
        text = ast.unparse(block)
        network_order = [
            f"self.{owner}.core.clear_run_loop(self)",
            f"self.{owner}.core.run_loop_transporters(",
            f"self.{owner}.core.run_loop_channels(phase)",
            f"self.{owner}.core.run_loop_modulators(",
            f"self.{owner}.core.run_loop(phase=phase, t=t)",
        ]
        offsets = [text.index(value) for value in network_order]
        assert offsets == sorted(offsets)
        network_blocks.append(site("betse/science/sim.py", block))
    channel_skip = next(
        n
        for n in ast.walk(networks["run_loop_channels"])
        if isinstance(n, ast.If) and "chan.init_active is False" in ast.unparse(n.test)
    )
    assert (
        ast.unparse(channel_skip.test)
        == "phase.kind is SimPhaseKind.INIT and chan.init_active is False"
    )
    channel_default = assign(networks["read_channels"], "obj.init_active")
    assert (
        len(channel_default) == 1
        and ast.unparse(channel_default[0].value) == "chan_dic.get('init active', True)"
    )
    assert "self.channel_core.init(sim.vm, cells, p, targets=targets)" in ast.unparse(
        channels["init_channel"]
    )
    entry = sim["init_dynamics"]
    entry_text = ast.unparse(entry)
    for needed in (
        "phase.dyna.init_profiles(phase)",
        "self.channel_noise_factor = np.random.random(self.mdl)",
        "phase.dyna.init_events(phase)",
        "self.CaATP_block = np.ones(self.mdl)",
        "self.rho_pump = 1",
        "self.rho_channel = 1",
        "self.endo_retic = None",
    ):
        assert needed in entry_text, needed
    ca_dyn = assign(parameters["load"], "self.Ca_dyn")
    assert len(ca_dyn) == 1 and ast.literal_eval(ca_dyn[0].value) is False
    for target in ("self.fluid_flow", "self.td_deform", "self.sim_eosmosis"):
        values = assign(parameters["load"], target)
        assert len(values) == 1 and ast.literal_eval(values[0].value) is False
    assert "if p.ions_dict['Ca'] == 1 and p.Ca_dyn:" in entry_text
    assert "if p.Ca_dyn == 1:" in ast.unparse(sim["ca_handler"])
    assert "self.grn = None" in ast.unparse(sim["init_core"])
    assert "self.molecules = None" in ast.unparse(sim["init_core"])
    assert "self.vm = np.zeros(self.mdl)" in ast.unparse(sim["init_core"])
    assert "self.T = p.T" in ast.unparse(sim["init_core"])
    assert "self.core.read_channels(channels_config, phase)" in ast.unparse(
        genes["read_gene_config"]
    )
    assert "self.core.read_channels(channels_config, phase)" in ast.unparse(genes["reinitialize"])
    assert "self._finalize_events_global(phase)" in ast.unparse(tissue["init_events"])
    assert "self._finalize_events_tissue(phase)" in ast.unparse(tissue["init_events"])
    assert "shuffle(mem_i_copy)" in ast.unparse(tissue["_finalize_events_global"])
    assert "p._run_sim" in ast.unparse(modulate["f_sweep"])
    assert "p.sim_time_total" in ast.unparse(modulate["f_sweep"])
    warm_path = PARENT / "source/src/cells/processes/betse_normal_ecm_catalog_join_source.py"
    warm = functions(warm_path)["run_dispatch"]
    assert "ctx.phase.kind = 'SIM'" in ast.unparse(warm)
    owned_path = PARENT / "source/src/cells/processes/betse_normal_ecm_event_mechanics.py"
    owned = functions(owned_path)["_advance_events"]
    assert "value != index" in ast.unparse(owned)
    noise_hook = next(
        n for n in ast.walk(owned) if isinstance(n, ast.FunctionDef) and n.name == "on_noise"
    )
    assert "events.noise(" in ast.unparse(noise_hook)
    assert "on_mechanics(current)" in ast.unparse(noise_hook)
    lifecycle = PARENT / "source/src/cells/processes/betse_normal_ecm_run_lifecycle.py"
    assert "INIT execution stays closed" in ast.unparse(functions(lifecycle)["bind"])
    guards_scope = []
    for flag in (
        "self.T",
        "self.deformation",
        "self.deform_osmo",
        "self.grn_enabled",
        "self.dynamic_noise",
        "self.v_sensitive_gj",
        "self.alpha_NaK",
        "self.alpha_Ca",
        "self.channel_noise_level",
    ):
        guards_scope.extend(
            site("betse/science/parameters.py", n) for n in assign(parameters["load"], flag)
        )
    startup = ast.unparse(sim["run_sim_core"])
    startup_order = [
        "self.init_dynamics(phase)",
        "self.clear_storage(",
        "self.update_V(",
        "self._plot_loop(phase)",
    ]
    assert [startup.index(s) for s in startup_order] == sorted(
        startup.index(s) for s in startup_order
    )
    return dict(
        kind="cells.ordinary_ECM_INIT_source_boundary@1",
        status="source_audited_design_only_no_INIT_execution",
        native_revision="5269a714aa2593ed2a6708c4516289977d8ae1a2",
        native_Python_files=332,
        installed_exact=True,
        native_source_sha256=pins,
        runner_INIT_fresh_simulator=True,
        runner_SIM_loads_existing_simulator=True,
        source_INIT_runner=site("betse/science/simrunner.py", runner["init"]),
        source_phase_constructor=site("betse/science/phase/phasecls.py", phase["__init__"]),
        source_phase_legacy_flag=site("betse/science/phase/phasecls.py", phase["_init_kludge"]),
        source_phase_time_setup_complete_body=site("betse/science/phase/phasecls.py", setup),
        source_count_statement_slice=site("betse/science/parameters.py", count[0]),
        source_clock_sampling_slice=[site("betse/science/sim.py", n) for n in clock],
        startup_order=startup_order,
        loop_order_with_guarded_optional_stages=stages,
        conditional_molecule_and_GRN_dispatch_source_blocks=network_blocks,
        network_dispatch_order=[
            "clear_run_loop",
            "conditional transporters",
            "conditional channels",
            "conditional modulators",
            "run_loop chemistry and movement",
        ],
        INIT_skipped_SIM_only_event_branch=site("betse/science/sim.py", fire),
        INIT_skipped_SIM_only_protein_noise_branch=site("betse/science/sim.py", noise),
        INIT_channel_warm_skip_guard=site("betse/science/chemistry/networks.py", channel_skip),
        channel_init_active_default=site("betse/science/chemistry/networks.py", channel_default[0]),
        channel_constructor_complete_body=site(
            "betse/science/chemistry/networks.py", channels["init_channel"]
        ),
        phase_setup_rng_draw=site(
            "betse/science/sim.py", assign(entry, "self.channel_noise_factor")[0]
        ),
        setup_event_finalization_complete_body=site(
            "betse/science/tissue/tishandler.py", tissue["init_events"]
        ),
        setup_Python_shuffle_is_not_a_loop_event=site(
            "betse/science/tissue/tishandler.py", tissue["_finalize_events_global"]
        ),
        legacy_sweep_phase_dependency=site("betse/science/math/modulate.py", modulate["f_sweep"]),
        hardcoded_disabled_flags={
            target: False for target in ("Ca_dyn", "fluid_flow", "td_deform", "sim_eosmosis")
        },
        configured_flags_require_explicit_inputs=guards_scope,
        source_core_and_dynamic_initialization_body_hashes={
            name: site("betse/science/sim.py", sim[name])["AST_sha256"]
            for name in (
                "init_core",
                "init_dynamics",
                "clear_storage",
                "run_sim_core",
                "_run_sim_core_loop",
                "ca_handler",
                "write2storage",
                "_pickle_phase",
            )
        },
        ER_native_default_route_enabled=False,
        setup_rng_and_loop_rng_are_distinct=True,
        full_rng_producer_audit_claim=False,
        SIM_interface_blockers=dict(
            frozen_parent_inputs=dict(
                path=str(PARENT / "inputs.json"), sha256=sha(PARENT / "inputs.json")
            ),
            warm_dispatch=dict(path=str(warm_path), sha256=sha(warm_path), hardcodes_SIM=True),
            event_mechanics=dict(
                path=str(owned_path),
                sha256=sha(owned_path),
                assumes_every_channel_calls_equal_material_index=True,
                mechanics_callback_nested_in_noise_hook=True,
                noise_mechanics_hook=site(str(owned_path), noise_hook),
            ),
            lifecycle=dict(
                path=str(lifecycle), sha256=sha(lifecycle), explicitly_refuses_INIT=True
            ),
            resolution=(
                "Separate INIT adapter and conditional references; no shared/"
                "frozen helper edits or SIM packet relabelling"
            ),
        ),
        native_seed_load_init_core_init_dynamics_or_solver_called=False,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
        active_job_queries=0,
        new_or_retained_qualification_passes=0,
    )


def design(boundary_path):
    return dict(
        kind="cells.separate_ordinary_ECM_INIT_phase_design@1",
        status="source_design_only_implementation_and_numerical_release_not_started",
        purpose=(
            "Resolve real INIT/SIM dispatch, cold-entry, channel-count an"
            "d RNG differences before a separate ordinary ECM INIT materi"
            "al-execution feature"
        ),
        boundary=dict(path=str(boundary_path), sha256=sha(boundary_path)),
        new_prefix=PREFIX,
        entry=dict(
            proposed_initial_scope=(
                "Headless INIT material/field execution on explicitly supplie"
                "d source core/entry owners, complete phase setup receipt and"
                " caches"
            ),
            physical_seed_load_init_core_and_whole_native_init_claim=False,
            native_fresh_core_vs_loaded_SIM_distinguished=True,
            actual_pre_cold_voltage_must_be_archived=True,
            INIT_dt_used_for_cold_constructors_and_bootstrap=True,
            configured_temperature_and_actual_cache_owners_required=True,
            source_setup_single_NumPy_draw_and_optional_Python_randomness_retained=True,
            scheduled_event_finalization_is_not_event_execution=True,
            legacy_run_sim_flag=False,
            missing_f_sweep_slope_not_repaired_or_computed_from_INIT_duration=True,
        ),
        dispatch=dict(
            phase="INIT",
            solver="FULL",
            ECM=True,
            actual_source_loop_order_preserved=True,
            scheduled_event_execution=False,
            dynamic_protein_noise_execution=False,
            bulk_primary_ion_pumps_and_movers=True,
            CaATP_if_enabled_by_source_configuration=True,
            enabled_ER=False,
            general_molecules=(
                "Explicitly disabled for first isolated GRN scope; other owne"
                "r families need separate admission"
            ),
            GRN=(
                "Explicit configuration may enable or disable; never infer a "
                "global False/True default"
            ),
            channels=(
                "Every configured population is constructed; init_active=Fals"
                "e skips its warm update and leaves its cold private fields/c"
                "all count unchanged"
            ),
            channel_counts=(
                "Per population actual source population_after events; inacti"
                "ve0 and active current tick are legal together"
            ),
            rho_pump_and_rho_channel="Source setup resets both to1 at actual new phase entry",
            flow_and_dynamic_deformation=False,
            steady_mechanics=(
                "Only if explicitly configured and required source owners/caches exist"
            ),
            deferred_primary_commit_and_full_fields_once=True,
            network_internal_order=[
                "clear",
                "transporters if configured",
                "INIT-active channels if configured",
                "modulators if configured",
                "run_loop chemistry and movement",
            ],
            selected_first_GRN_scope=(
                "Admit only declared owner/transport/channel/modulator branches whose complete "
                "state is supplied and separately checked"
            ),
            mechanics_splice=(
                "Explicit post-network hook before deferred commit; never dro"
                "p mechanics when skipping the SIM-only noise hook"
            ),
        ),
        clocks=dict(
            count="int(init_time_total/init_time_step), using stored binary64 division",
            labels="Source linspace(0,N*dt,N); labels are not update dt and must not be rebased",
            material_dt="Exactly init_time_step per admitted call",
            sampling=(
                "Original repeated i+=stride; i=int(i) source rule; stride=init_sampling/init_dt"
            ),
            native_sampling_stride_below1=(
                "Explicit nonprogress boundary, never execute hanging loop"
            ),
            N0_N1_and_fractional_sampling_must_be_explicit=True,
            ordinary_native_count_not_forced_to3=True,
            first_implementation_call_cap=(
                "Audit inherited bounded kernel caps; use an explicitly label"
                "led prefix with original full calendar or refuse larger coun"
                "ts. Never call a prefix the whole phase."
            ),
        ),
        references_and_capture=dict(
            new_phase_aware_native_wrapper_and_fresh_conditional_oracle_required=True,
            common_SIM_warm_dispatch_and_channel_sequence_not_reused_unchanged=True,
            reuse_existing_pinned_source_bodies_and_unchanged_numeric_budgets_only=True,
            complete_function_bodies_and_extracted_slices_labelled_separately=True,
            actual_inputs_before_each_consumer_archived=True,
            all_reached_candidates_contexts_RNG_and_failures_preserved_before_checks=True,
            new_INIT_capture_profile_required_before_evidence_tool_selection=True,
            inherited_SIM_qualification_credit=0,
        ),
        lifecycle=dict(
            own_INIT_binding_and_state_identities=True,
            single_complete_material_and_field_advance=True,
            source_reset_and_cold_setup_only_at_explicit_new_entry=True,
            window_pause_resume_preserves_full_state_and_original_calendar=True,
            native_storage_display_pickle_and_INIT_to_SIM_transition_closed=True,
            INIT_to_SIM_requires_native_reinitialize_audit_not_blind_cache_carry=True,
            zero_sample_native_pickle_vm_time_last_requires_separate_boundary=True,
            field_domain_at_most16_and_quartic_display_at_least25_unchanged=True,
        ),
        prospective_check_families=[
            "INIT clock/count/truncation/N0/N1/original sampling and event-disabled labels",
            (
                "Poisoned event/noise callbacks prove the SIM-only branches a"
                "re unreachable without changing configured flags"
            ),
            (
                "init_active defaultTrue, explicitTrue, explicitFalse and mix"
                "ed populations; exact inactive cold cache and active-only co"
                "unts"
            ),
            "Configured GRN off/on and CaATP off/on with ERNone/Ca_dynFalse preserved",
            (
                "Complete conditional source/native/Decimal100/160 material/C"
                "aATP/channels/GRN/mechanics/field checks with old budgets"
            ),
            (
                "Phase-entry resets and RNG receipts distinguished from no pe"
                "r-loop protein-noise draws"
            ),
            "Window pause/resume, exact stop/prefix/exhaustion, callbacks and full raw failures",
            (
                "Reject SIM-labelled parents, stale dt/cache phase, forged in"
                "active warm fields, enabled ER/flow/dynamic/display/physical"
                " admission"
            ),
        ],
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
        implementation_files_created=False,
        numerical_release_authorized=False,
        automatic_launch=False,
        automatic_polling=False,
        automatic_followup=False,
    )


if __name__ == "__main__":
    boundary = audit()
    path = WORK / (PREFIX + "_source_boundary_01.json")
    with path.open("x") as stream:
        json.dump(boundary, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    plan = design(path)
    output = WORK / (PREFIX + "_design_01.json")
    with output.open("x") as stream:
        json.dump(plan, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                status=boundary["status"],
                boundary_sha256=sha(path),
                design_sha256=sha(output),
                installed_native_files=332,
                numerical_runs=0,
            )
        )
    )
