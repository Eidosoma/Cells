"""Parse original caller order and reusable boundaries without executing science."""

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PIN = Path("/mnt/workspaces/Cells/betse-v1.5.0")
INSTALLED = Path("/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages")


def audit():
    paths = (
        "betse/science/sim.py",
        "betse/science/physics/ion_current.py",
        "betse/science/cells.py",
        "betse/science/chemistry/gene.py",
        "betse/science/chemistry/networks.py",
        "betse/science/sim_toolbox.py",
    )
    trees, pins = {}, {}
    for path in paths:
        raw = (PIN / path).read_bytes()
        assert raw == (INSTALLED / path).read_bytes()
        trees[path] = ast.parse(raw)
        pins[path] = hashlib.sha256(raw).hexdigest()
    simulator = next(
        n for n in trees[paths[0]].body if isinstance(n, ast.ClassDef) and n.name == "Simulator"
    )
    methods = {n.name: n for n in simulator.body if isinstance(n, ast.FunctionDef)}
    caller = methods["run_sim_core"]
    calls = [
        ast.unparse(n.value.func)
        for n in caller.body
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
    ]
    assert (
        calls.index("self.init_dynamics")
        < calls.index("self.clear_storage")
        < calls.index("self.update_V")
    )
    loop = next(n for n in methods["_run_sim_core_loop"].body if isinstance(n, ast.For))
    commit = next(
        i
        for i, n in enumerate(loop.body)
        if isinstance(n, ast.Expr) and ast.unparse(n) == "self.update_all_concs(cells, p)"
    )
    suffix = loop.body[commit : commit + 3]
    assert [ast.unparse(n) for n in suffix] == [
        "self.update_all_concs(cells, p)",
        "self.update_V(cells, p)",
        "stb.check_v(self.vm)",
    ]
    grn = next(
        i
        for i, n in enumerate(loop.body)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "p.grn_enabled"
    )
    assert grn < commit
    update = methods["update_V"]
    get_current = next(
        i
        for i, n in enumerate(update.body)
        if isinstance(n, ast.Expr) and ast.unparse(n) == "get_current(self, cells, p)"
    )
    sigma = next(
        i
        for i, n in enumerate(update.body)
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "self.sigma_cell"
    )
    assert get_current < sigma
    physics = next(
        n
        for n in trees[paths[1]].body
        if isinstance(n, ast.FunctionDef) and n.name == "get_current"
    )
    assert any(
        isinstance(n, ast.If) and ast.unparse(n.test) == "p.is_ecm is True" for n in physics.body
    )
    all_statements = {
        ast.unparse(n) for n in ast.walk(trees[paths[2]]) if isinstance(n, ast.Assign)
    }
    assert "self.diviterm = self.cell_vol / self.cell_sa" in all_statements
    assert "self.rads = self.mem_mids_flat - self.cell_centres[self.mem_to_cells]" in all_statements
    return dict(
        kind="cells.normal_ecm_field_join_reachability@1",
        reachable=True,
        native_source_sha256=pins,
        actual_bootstrap_after_dynamics_and_storage=True,
        original_suffix_lines=[suffix[0].lineno, suffix[-1].end_lineno],
        original_grn_before_deferred_commit=True,
        complete_ECM_get_current_before_sigma_and_vm=True,
        old_voltage_native_adapter_not_complete_environment_execution=True,
        explicit_derived_geometry_operator_and_fixed_initializer_cache_boundary=True,
        existing_material_global_accuracy_limit=(
            "failed39/40 preserved; new local composition gains no inherited "
            "global material acceptance"
        ),
        no_new_caller_enable_flag_required=True,
        scientific_execution=False,
    )


if __name__ == "__main__":
    path = (
        ROOT
        / "agent-work/cells-worker-01/workfiles/betse_normal_ecm_field_join_reachability_01.json"
    )
    with path.open("x") as stream:
        stream.write(json.dumps(audit(), indent=2, sort_keys=True) + "\n")
    print("Reachable normal ECM suffix and bootstrap audited; science never executed")
