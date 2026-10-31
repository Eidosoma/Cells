"""Read and compare lifecycle source AST; never execute captured scientific code."""

import ast
import hashlib
import json
from pathlib import Path

from betse_normal_ecm_run_lifecycle_dependencies import PARENT, PREFIX, ROOT, locate, sha
from betse_normal_ecm_run_lifecycle_source_audit import audit as boundary_audit

WORK = ROOT / "agent-work/cells-worker-01/workfiles"
NATIVE = Path("/mnt/workspaces/Cells/betse-v1.5.0")


def functions(path, cls=None):
    body = ast.parse(Path(path).read_text()).body
    if cls:
        body = next(n.body for n in body if isinstance(n, ast.ClassDef) and n.name == cls)
    return {n.name: n for n in body if isinstance(n, ast.FunctionDef)}


def signature(nodes):
    if isinstance(nodes, list):
        nodes = ast.Module(body=nodes, type_ignores=[])
    return ast.dump(nodes, include_attributes=False)


def audit():
    boundary = boundary_audit()
    assert boundary == json.loads((WORK / (PREFIX + "_source_boundary_02.json")).read_text())
    native = functions(ROOT / "validation/betse" / (PREFIX + "_native.py"))
    parameters = functions(NATIVE / "betse/science/parameters.py", "Parameters")
    sim = functions(NATIVE / "betse/science/sim.py", "Simulator")
    phases = functions(NATIVE / "betse/science/phase/phasecls.py", "SimPhase")
    counts = [
        n
        for n in parameters["load"].body
        if isinstance(n, ast.Assign)
        and ast.unparse(n.targets[0]) in ("self.init_tsteps", "self.sim_tsteps")
    ]
    assert signature(native["_source_counts"].body) == signature(counts)
    assert signature(native["_source_phase_time"].body) == signature(
        phases["_init_kludge_time"].body
    )
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
    assert len(clock) == 6 and isinstance(native["_source_clock"].body[-1], ast.Return)
    assert signature(native["_source_clock"].body[:-1]) == signature(clock)
    native_tree = ast.parse((ROOT / "validation/betse" / (PREFIX + "_native.py")).read_text())
    local_enum = next(
        n for n in native_tree.body if isinstance(n, ast.ClassDef) and n.name == "SimPhaseKind"
    )
    enum_members = {
        n.targets[0].id: ast.literal_eval(n.value)
        for n in local_enum.body
        if isinstance(n, ast.Assign)
    }
    assert enum_members == {"SEED": 1, "INIT": 2, "SIM": 3}
    used_enum_members = {
        n.attr
        for n in ast.walk(native_tree)
        if isinstance(n, ast.Attribute)
        and isinstance(n.value, ast.Name)
        and n.value.id == "SimPhaseKind"
    }
    assert used_enum_members <= set(enum_members)
    original_enum = ast.parse((NATIVE / "betse/science/enum/enumphase.py").read_text())
    declared_enum = next(
        n
        for n in original_enum.body
        if isinstance(n, ast.Assign)
        and isinstance(n.targets[0], ast.Name)
        and n.targets[0].id == "SimPhaseKind"
    )
    assert next(
        ast.literal_eval(k.value) for k in declared_enum.value.keywords if k.arg == "member_names"
    ) == tuple(enum_members)
    old = functions(PARENT / "source/tests/unit/test_betse_normal_ecm_event_mechanics.py")
    loop = next(
        n
        for n in old["run_history"].body
        if isinstance(n, ast.For) and ast.unparse(n.target) == "(index, native_call)"
    )
    start = next(
        i
        for i, n in enumerate(loop.body)
        if isinstance(n, ast.Assign)
        and ast.unparse(n.targets[0]) == "(inner, trial, feedback, calcium, noise, event_context)"
    )
    stop = next(i for i, n in enumerate(loop.body) if ast.unparse(n) == "states.append(candidate)")
    comparison = functions(ROOT / "validation/betse" / (PREFIX + "_compare.py"))["compare_call"]
    assert signature(comparison.body) == signature(loop.body[start:stop])
    own = functions(ROOT / "src/cells/processes" / (PREFIX + ".py"))
    body = ast.unparse(own["advance"])
    assert body.count("composition.advance(") == 1
    ordered = (
        "next_call(binding, parent)",
        "observer('before_call'",
        "composition.advance(",
        "attempted.update(component_candidate=",
        "attempted['run_candidate'] = proposed",
        "verify(binding, proposed)",
        "current = proposed",
        "observer('accepted_call'",
        "observer('headless_observation'",
    )
    positions = [body.index(value) for value in ordered]
    assert positions == sorted(positions)
    for needed in (
        "caller_parent=parent",
        "accepted=failed",
        "attempt=attempted",
        "component_partial=getattr(error, 'partial', None)",
        "automatic_retry=False",
        "native_pickle_called=False",
    ):
        assert needed in body, needed
    whole = ast.unparse(ast.parse((ROOT / "src/cells/processes" / (PREFIX + ".py")).read_text()))
    for forbidden in (
        "composition.initialize(",
        "clear_storage(",
        "init_dynamics(",
        "np.linspace(",
    ):
        assert forbidden not in whole, forbidden
    assert "count = int(ratio)" in ast.unparse(own["profile"])
    assert "ratio = total / dt" in ast.unparse(own["profile"])
    assert "stride = sampling / dt" in ast.unparse(own["profile"])
    # Attribute API checks are separate from global-name checks. In particular,
    # the original dense/window defect and the SEED enum guard must be caught.
    calendar_tree = ast.parse(locate("src/cells/core/physiology_native_calendar.py").read_text())
    calendar_exports = {
        n.name for n in calendar_tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
    }
    calendar_uses = set()
    for path in (
        ROOT / "src/cells/processes" / (PREFIX + ".py"),
        ROOT / "tests/unit" / ("test_" + PREFIX + ".py"),
        locate("src/cells/processes/betse_normal_ecm_event_join.py"),
        locate("src/cells/processes/betse_normal_ecm_event_mechanics.py"),
    ):
        calendar_uses |= {
            n.attr
            for n in ast.walk(ast.parse(path.read_text()))
            if isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Name)
            and n.value.id == "calendars"
        }
    assert calendar_uses <= calendar_exports and "dense" not in calendar_uses
    evaluate_calls = [
        ast.unparse(n.func) for n in ast.walk(native["evaluate"]) if isinstance(n, ast.Call)
    ]
    assert evaluate_calls.count("component.evaluate") == 1
    return dict(
        kind="cells.headless_ECM_lifecycle_AST_proof@1",
        status="passed_source_AST_only",
        native_boundary_sha256=sha(WORK / (PREFIX + "_source_boundary_02.json")),
        complete_phase_time_body_exact=True,
        time_count_statement_slice_exact=True,
        clock_sampling_six_statement_slice_exact=True,
        local_source_phase_enum_members=enum_members,
        source_phase_enum_member_references_resolve=True,
        inherited_scientific_comparison_AST_exact=True,
        comparison_statement_count=len(comparison.body),
        comparison_AST_sha256=hashlib.sha256(signature(comparison.body).encode()).hexdigest(),
        one_component_advance_per_owned_call=True,
        one_component_native_capture_per_history=True,
        original_calendar_window_API_resolves=sorted(calendar_uses),
        source_dt_label_sample_order_preserved=True,
        commit_before_owned_observer=True,
        full_candidate_context_and_component_failure_retained=True,
        native_initializer_phase_reset_storage_display_pickle_calls=0,
        scientific_imports=0,
        scientific_AST_executions=0,
        numerical_runs=0,
    )


if __name__ == "__main__":
    result = audit()
    path = WORK / (PREFIX + "_AST_witness_01.json")
    with path.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps(dict(status=result["status"], sha256=sha(path))))
