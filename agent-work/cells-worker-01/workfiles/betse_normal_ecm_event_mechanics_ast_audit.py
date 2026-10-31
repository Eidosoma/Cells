"""Static original-order, single-call splice, source buffers and equation-scope proof."""

import ast
import copy
import json
from pathlib import Path

from betse_normal_ecm_event_mechanics_audit_tools import ROOT, functions, sha, signature, write

PREFIX = "betse_normal_ecm_event_mechanics"
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
NATIVE = Path("/mnt/workspaces/Cells/betse-v1.5.0")
INSTALLED = Path("/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages")


def digest(nodes):
    import hashlib

    return hashlib.sha256(signature(ast.Module(body=nodes, type_ignores=[])).encode()).hexdigest()


def audit():
    own = ROOT / "src/cells/processes" / (PREFIX + ".py")
    functions_own = functions(own)
    original = functions(ROOT / "src/cells/processes/betse_normal_ecm_event_join.py")["advance"]
    inverse = copy.deepcopy(functions_own["_advance_events"])
    inverse.name = "advance"
    assert (
        inverse.args.kwonlyargs[-1].arg == "on_mechanics"
        and inverse.args.kw_defaults[-1].value is None
    )
    inverse.args.kwonlyargs.pop()
    inverse.args.kw_defaults.pop()
    hook = next(
        n for n in ast.walk(inverse) if isinstance(n, ast.FunctionDef) and n.name == "on_noise"
    )
    assert ast.unparse(hook.body[-1]) == "if on_mechanics is not None:\n    on_mechanics(current)"
    hook.body.pop()
    assert signature(inverse) == signature(original)
    calls = [
        ast.unparse(n.func)
        for n in ast.walk(functions_own["_advance_events"])
        if isinstance(n, ast.Call)
    ]
    assert calls.count("event_material.step_after_events") == calls.count("full.reconstruct") == 1
    assert not any(name.endswith(".advance") for name in calls)
    wrapper = ast.unparse(functions_own["advance"])
    assert wrapper.count("_advance_events(") == wrapper.count("mechanics.step(") == 1
    for needed in (
        "mechanics_failure",
        "getattr(error, 'trial', None)",
        "event_partial",
        "mechanics_input",
        "complete_event_return",
    ):
        assert needed in wrapper, needed
    packet = ast.unparse(functions_own["mechanics_input"])
    for needed in (
        "parent.events.field",
        "ctx.sim.P_cells",
        "ctx.sim.T",
        "ctx.sim.cc_cells",
        "ctx.sim.cc_env",
        "ctx.sim.grn.core.molecules",
        "parent.events.clock.source_times_s[index]",
        "sample=False",
    ):
        assert needed in packet, needed
    bind = ast.unparse(functions_own["bind"])
    assert "1 <= n <= 16" in bind and "requires>=25" in bind
    for needed in ("mechanics.bind", "event.bind", "held-zero velocity stores", "eb.calendar.dt_s"):
        assert needed in bind, needed
    sample = ast.unparse(functions_own["sample"])
    assert "raise CompositionRejected" in sample and "display_completed=False" in sample
    assert "initial_sample_state()" in ast.unparse(functions_own["verify"])
    # Undo only the declared source-orchestration additions, retaining every
    # original native event/math statement, exception archive and source order.
    path = ROOT / "validation/betse" / (PREFIX + "_native.py")
    native = copy.deepcopy(functions(path)["evaluate"])
    assert ast.unparse(native.body[0]) == "composition = declared"
    assert ast.unparse(native.body[1]) == "declared = composition['event_inputs']"
    native.body = native.body[2:]
    removed = []

    class NativeInverse(ast.NodeTransformer):
        def visit_Assign(self, node):
            target = ast.unparse(node.targets[0])
            if target in ("mechanical_owner", "sampled_labels", "parameters.t_resample") or (
                target == "field_phase"
                and isinstance(node.value, ast.Constant)
                and node.value.value == "steady_mechanics"
            ):
                removed.append(ast.unparse(node))
                return None
            return self.generic_visit(node)

        def visit_Expr(self, node):
            if isinstance(node.value, ast.Call) and ast.unparse(node.value.func) in (
                "mechanical_owner.advance",
                "mechanical_owner.sample_state",
            ):
                removed.append(ast.unparse(node))
                return None
            return self.generic_visit(node)

        def visit_Call(self, node):
            node = self.generic_visit(node)
            if isinstance(node.func, ast.Name) and node.func.id == "dict":
                node.keywords = [
                    k
                    for k in node.keywords
                    if k.arg
                    not in {
                        "mechanics_history",
                        "sample_states",
                        "single_source_mechanics_seam",
                        "sampled_display_completed",
                        "mechanics_native_source_sha256",
                        "mechanics_source_sites",
                        "mechanical_view_separate_from_material_geometry",
                        "mechanics_partial",
                    }
                ]
            return node

    native = NativeInverse().visit(native)
    oldnative = functions(ROOT / "validation/betse/betse_normal_ecm_event_join_native.py")[
        "evaluate"
    ]
    assert len(removed) == 7 and signature(native) == signature(oldnative), (len(removed), removed)
    # Exact ordinary mechanics preparation statements; only final observation
    # return is added. No new numerical native-body implementation is present.
    prepared = functions(ROOT / "validation/betse" / (PREFIX + "_native_mechanics.py"))[
        "_prepared_mechanics_view"
    ]
    oldmech = functions(ROOT / "validation/betse/betse_mechanics_join_native.py")["evaluate"]
    stop = next(
        i
        for i, n in enumerate(oldmech.body)
        if isinstance(n, ast.Assign)
        and ast.unparse(n.targets[0]) == "(history, raw_calls, spline_calls)"
    )
    assert signature(ast.Module(body=prepared.body[0].body[:-1], type_ignores=[])) == signature(
        ast.Module(body=oldmech.body[:stop], type_ignores=[])
    )
    sim = ast.parse((NATIVE / "betse/science/sim.py").read_text())
    cls = next(n for n in sim.body if isinstance(n, ast.ClassDef) and n.name == "Simulator")
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    loop = next(n for n in methods["_run_sim_core_loop"].body if isinstance(n, ast.For))
    text = ast.unparse(loop)
    markers = (
        "phase.dyna.fire_events",
        "self.grn.core.run_loop",
        "self.protein_noise_flux =",
        "osmotic_P(",
        "getDeformation(",
        "self.update_all_concs(",
        "self.update_V(",
        "stb.check_v(",
        "self.write2storage(",
    )
    positions = [text.index(m) for m in markers]
    assert positions == sorted(positions), list(zip(markers, positions, strict=True))
    guarded = {
        name: next(n for n in loop.body if isinstance(n, ast.If) and ast.unparse(n.test) == name)
        for name in ("p.deform_osmo", "p.fluid_flow", "p.deformation")
    }
    sampling = []
    for n in methods["_plot_loop"].body:
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) in ("time_steps_sampled", "i"):
            sampling.append(n)
        elif isinstance(n, ast.While):
            sampling.append(n)
    sampler = functions(path)["source_sampling"]
    assert signature(ast.Module(body=sampler.body[:-1], type_ignores=[])) == signature(
        ast.Module(body=sampling, type_ignores=[])
    )
    # Original mechanical writes cannot change the ordinary deferred material,
    # current reconstruction or voltage path in this disabled-flow scope.
    writes = set()
    source_functions = {}
    for filename, names in (
        ("betse/science/physics/pressures.py", ("osmotic_P",)),
        ("betse/science/physics/deform.py", ("getDeformation",)),
    ):
        fs = functions(NATIVE / filename)
        for name in names:
            source_functions[name] = dict(
                source=filename, sha256=sha(NATIVE / filename), ast_sha256=digest([fs[name]])
            )
            writes |= {
                n.attr
                for n in ast.walk(fs[name])
                if isinstance(n, ast.Attribute)
                and isinstance(n.ctx, ast.Store)
                and isinstance(n.value, ast.Name)
                and n.value.id == "sim"
            }
    readers = {
        "update_all_concs": methods["update_all_concs"],
        "update_V": methods["update_V"],
        "get_current": functions(NATIVE / "betse/science/physics/ion_current.py")["get_current"],
    }
    downstream = {}
    for name, node in readers.items():
        attrs = {
            n.attr
            for n in ast.walk(node)
            if isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Name)
            and n.value.id in ("self", "sim")
        }
        assert not attrs & writes, (name, attrs & writes)
        downstream[name] = dict(ast_sha256=digest([node]), mechanical_store_reads=[])
    native_files = {
        str(p.relative_to(NATIVE)): sha(p) for p in sorted((NATIVE / "betse").rglob("*.py"))
    }
    assert len(native_files) == 332
    assert all(sha(INSTALLED / p) == h for p, h in native_files.items())
    test = functions(ROOT / "tests/unit" / ("test_" + PREFIX + ".py"))
    body = ast.unparse(test["run_history"])
    for needed in (
        "before_mechanics=before('mechanics')",
        "context['mechanics_input']",
        "noise['after']['cell_mol_m3']",
        "complete-failure",
        "constructor-failure",
        "total_fresh_reference_forms=52",
        "native_calendar_sample_eligibility_preserved=True",
    ):
        assert needed in body, needed
    assert body.index("'-complete-return-'") < body.index("assert previous_digest")
    assert "correspondence/" in ast.unparse(test["mechanical_rows"])
    reference = ast.unparse(
        functions(ROOT / "validation/betse" / (PREFIX + "_reference.py"))["main"]
    )
    assert "runtime=inventory()" in reference and "'scipy'" in reference
    return dict(
        kind="cells.event_mechanics_native_order_single_advance_AST@1",
        owned_event_advance_inverse_AST_exact=True,
        one_material_and_one_field_call=True,
        one_mechanical_step_after_completed_noise=True,
        native_event_evaluator_inverse_AST_exact=True,
        native_splice_statements=len(removed),
        native_mechanics_preparation_prefix_exact=True,
        original_native_order=list(markers),
        original_mechanical_guard_AST={k: digest([v]) for k, v in guarded.items()},
        native_sampling_while_AST_exact=True,
        pressure_actual_event_store=True,
        current_post_noise_ions_and_post_GRN_molecules=True,
        previous_reconstructed_field_epoch=True,
        mechanical_write_set=sorted(writes),
        downstream_read_write_disjoint=downstream,
        original_mechanical_source=source_functions,
        source_Python_files=len(native_files),
        installed_exact=True,
        maximum_native_field_cells=16,
        minimum_quartic_display_cells=25,
        sampling_eligibility_only_display_refused=True,
        full_partial_and_constructor_return_archives=True,
        strict_refusals_distinct_from_native_outputs=True,
        new_scientific_equations=False,
        new_budget_changes=False,
        component_qualification_pending=True,
        full_solver_or_physical_init_claim=False,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
    )


if __name__ == "__main__":
    result = audit()
    path = WORK / (PREFIX + "_AST_witness_01.json")
    write(path, result)
    print(
        json.dumps(
            dict(
                status="passed_static_AST_only",
                sha256=sha(path),
                native_files=result["source_Python_files"],
            )
        )
    )
