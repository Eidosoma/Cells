"""Read-only native phase ordering and original caller/callee boundary evidence."""

import argparse
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_ecm_run_lifecycle"
NATIVE = Path("/mnt/workspaces/Cells/betse-v1.5.0")
INSTALLED = Path("/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages")
OLD = Path("/mnt/workspaces/Cells/betse-normal-ecm-event-mechanics-prepared-20261031-01")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def site(path, node):
    return dict(
        path=path,
        line=node.lineno,
        end_line=node.end_lineno,
        source=ast.unparse(node),
        AST_sha256=hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
    )


def methods(tree, cls):
    return {
        n.name: n
        for n in next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls).body
        if isinstance(n, ast.FunctionDef)
    }


def audit():
    files = {str(p.relative_to(NATIVE)): sha(p) for p in sorted((NATIVE / "betse").rglob("*.py"))}
    assert len(files) == 332 and all(sha(INSTALLED / p) == h for p, h in files.items())
    sim = methods(ast.parse((NATIVE / "betse/science/sim.py").read_text()), "Simulator")
    params = methods(ast.parse((NATIVE / "betse/science/parameters.py").read_text()), "Parameters")
    phases = methods(
        ast.parse((NATIVE / "betse/science/phase/phasecls.py").read_text()), "SimPhase"
    )
    counts = [
        n
        for n in params["load"].body
        if isinstance(n, ast.Assign)
        and ast.unparse(n.targets[0]) in ("self.init_tsteps", "self.sim_tsteps")
    ]
    assert len(counts) == 2
    assert [ast.unparse(n) for n in counts] == [
        "self.init_tsteps = int(self.init_time_total / self.init_time_step)",
        "self.sim_tsteps = int(self.sim_time_total / self.sim_time_step)",
    ]
    time = phases["_init_kludge_time"]
    assert "self.p.t_resample = self.p.resample / self.p.dt" in ast.unparse(time)
    plot = sim["_plot_loop"]
    clock = []
    for node in plot.body:
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
    start = ast.unparse(sim["run_sim_core"])
    markers = (
        "phase.die_unless_kind_init_or_sim()",
        "self.init_dynamics(phase)",
        "self.clear_storage(",
        "self.update_V(",
        "self._plot_loop(phase)",
        "phase.callbacks.progress_ranged(",
        "with solver_context:",
        "solver_method(",
        "self._pickle_phase(phase)",
        "raise exception_instability",
    )
    positions = [start.index(m) for m in markers]
    assert positions == sorted(positions)
    loop = next(n for n in sim["_run_sim_core_loop"].body if isinstance(n, ast.For))
    body = ast.unparse(loop)
    order = (
        "self.fluxes_mem.fill(0)",
        "self.fluxes_gj.fill(0)",
        "phase.dyna.fire_events(",
        "self.ca_handler(",
        "self.grn.core.run_loop(",
        "self.protein_noise_flux =",
        "getDeformation(",
        "self.update_all_concs(",
        "self.update_V(",
        "stb.check_v(",
        "phase.callbacks.progressed_next()",
        "self.write2storage(",
    )
    positions = [body.index(m) for m in order]
    assert positions == sorted(positions)
    sample = next(
        n
        for n in loop.body
        if isinstance(n, ast.If) and ast.unparse(n.test) == "t in time_steps_sampled"
    )
    exceptions = [n for n in sim["run_sim_core"].body if isinstance(n, ast.Try)]
    assert len(exceptions) == 1
    assert [ast.unparse(h.type) for h in exceptions[0].handlers] == ["BetseSimUnstableException"]
    assert not any(isinstance(n, ast.Break) for n in ast.walk(loop))
    storage = sim["write2storage"]
    storage_text = ast.unparse(storage)
    display = next(
        n for n in storage.body if isinstance(n, ast.If) and ast.unparse(n.test) == "p.deformation"
    )
    assert storage_text.index("implement_deform_timestep(") < storage_text.index(
        "self.time.append(t)"
    )
    pickle_text = ast.unparse(sim["_pickle_phase"])
    assert "self.vm_time[-1]" in pickle_text
    # Preserve exact evidence from original frozen packets; live callers are
    # Root-owned during their explicit calendar repair, never changed here.
    callers = {}
    for relative in (
        "src/cells/processes/betse_normal_ecm_event_join.py",
        "src/cells/processes/betse_normal_ecm_event_mechanics.py",
    ):
        path = OLD / "source" / relative
        tree = ast.parse(path.read_text())
        calls = [
            site(relative, n)
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "calendars"
            and n.func.attr == "dense"
        ]
        callers[relative] = dict(frozen_sha256=sha(path), frozen_calls=calls)
    assert sum(len(r["frozen_calls"]) for r in callers.values()) == 5
    cal = "src/cells/core/physiology_native_calendar.py"
    calpath = OLD / "source" / cal
    caltree = ast.parse(calpath.read_text())
    exports = [n.name for n in caltree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
    assert "window" in exports and "dense" not in exports
    assert sha(ROOT / cal) == sha(calpath)
    lifecycle = ast.parse((ROOT / "src/cells/processes" / (PREFIX + ".py")).read_text())
    funcs = {n.name: n for n in lifecycle.body if isinstance(n, ast.FunctionDef)}
    advance = ast.unparse(funcs["advance"])
    window = ast.unparse(funcs["run_window"])
    assert advance.count("composition.advance(") == 1
    assert "calendars.dense" not in ast.unparse(lifecycle) and "calendars.window" in ast.unparse(
        lifecycle
    )
    assert "composition.initialize" not in ast.unparse(lifecycle)
    assert "begin(" not in window and "composition.advance(" not in window
    assert "while current.cursor < stop:" in window and "advance(binding, current" in window
    assert (
        advance.index("verify(binding, proposed)")
        < advance.index("current = proposed")
        < advance.index("observer('accepted_call'")
    )
    assert "headless_observation_at_native_sample_boundary" in ast.unparse(lifecycle)
    assert "INIT execution stays closed" in ast.unparse(funcs["bind"])
    repair = Path("/mnt/workspaces/Cells/ecm-event-calendar-api-repair-20261031-03/result.json")
    assert sha(repair) == "173c398f2897105eec2fd1f2c4d06e902f84301600cfe3d068b35d8a86f8dca0"
    successor_path = Path(
        "/mnt/workspaces/Cells/ecm-event-calendar-api-repair-20261031-03/root-review-01/successor-preparation.json"
    )
    successors = json.loads(successor_path.read_text())
    reviewed = {}
    for key, expected in (
        ("event03", "604eca1502addb301452f3cb8c5889853895c42334392f617b5a5d6f290460c6"),
        ("event_mechanics02", "8df92c3695c401dcf42883394a719c93b072a69ddcb3eaf38b1be53f79275b18"),
    ):
        row = successors[key]
        assert sha(row["packet_inputs"]["path"]) == row["packet_inputs"]["sha256"] == expected
        assert sha(row["review"]["path"]) == row["review"]["sha256"]
        approval = json.loads(Path(row["review"]["path"]).read_text())
        assert (
            approval["status"] == "clear_for_held_full_roster_runner_preparation"
            and approval["release_authorized"] is False
        )
        reviewed[key] = dict(inputs=row["packet_inputs"], review=row["review"])
    independent = json.loads(Path(successors["event_mechanics02"]["review"]["path"]).read_text())[
        "independent_calendar_API_review"
    ]
    assert (
        sha(independent["path"])
        == independent["sha256"]
        == "294016b28e8f47aa2a2f9669152dc510a0e8925b0a2b4db03e1dad303f5ef656"
    )
    return dict(
        kind="cells.headless_ECM_lifecycle_source_boundary@1",
        status="reviewed_successor_dependencies_bound_no_numerical_release",
        native_revision="5269a714aa2593ed2a6708c4516289977d8ae1a2",
        native_Python_files=332,
        installed_exact=True,
        native_source_sha256=files,
        source_time_count_statements=[site("betse/science/parameters.py", n) for n in counts],
        phase_time_setup_complete_source_body=site("betse/science/phase/phasecls.py", time),
        plot_clock_and_sampling_slice=[site("betse/science/sim.py", n) for n in clock],
        native_phase_start_order=list(markers),
        native_iteration_order=list(order),
        source_sampling_block=site("betse/science/sim.py", sample),
        native_display_block=site("betse/science/sim.py", display),
        native_instability_policy=(
            "Only BetseSimUnstableException is caught; pickle/report precede rethrow. "
            "Other fatal exceptions bypass that save. This headless coordinator preserves "
            "all reached errors without calling pickle."
        ),
        source_loop_break_or_cancel_branch=False,
        owned_pause_is_not_native_completion=True,
        source_time_append_after_display=True,
        whole_pickle_reports_require_nonempty_vm_samples=True,
        lifecycle_uses_one_component_call_per_advance=True,
        no_component_init_or_phase_reinitialization_on_window_resume=True,
        accepted_commit_precedes_owned_observer=True,
        unverified_run_candidate_retained_without_acceptance=True,
        headless_observations_do_not_claim_native_write2storage_or_display=True,
        active_material_execution_scope=(
            "SIM/N3 supplied-entry composition only; INIT clocks audited, "
            "INIT solver execution refused"
        ),
        installed_native_seed_init_load_run_sim_core_write2storage_pickle_called=False,
        exact_original_calendar_API_blocker=dict(
            callers=callers,
            callee_path=cal,
            callee_sha256=sha(calpath),
            callee_exports=exports,
            missing_symbol="dense",
            existing_full_window_symbol="window",
        ),
        Root_calendar_repair=dict(
            path=str(repair),
            sha256=sha(repair),
            owner="Root",
            independent_review_and_explicit_successor_pins_pending=False,
            independent_review=independent,
            reviewed_successors=reviewed,
            scientific_trajectory_credit=0,
        ),
        old_frozen_and_shared_files_changed=False,
        source_clock_dt_sample_equations_changed=False,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
        active_job_queries=0,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=WORK / (PREFIX + "_source_boundary_01.json"))
    args = parser.parse_args()
    result = audit()
    path = args.output
    with path.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                status=result["status"],
                native_files=332,
                frozen_missing_API_calls=5,
                sha256=sha(path),
            )
        )
    )
