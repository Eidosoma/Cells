"""Whole pinned source reachability; text/AST/hash only, no scientific imports."""

import ast
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
CHECKOUT = Path("/mnt/workspaces/Cells/betse-v1.5.0")
INSTALLED = Path("/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages/betse")
REVISION = "5269a714aa2593ed2a6708c4516289977d8ae1a2"
ER_PARAMETERS = {
    "serca_max",
    "max_er",
    "act_Km_Ca",
    "act_n_Ca",
    "inh_Km_Ca",
    "inh_n_Ca",
    "act_Km_IP3",
    "act_n_IP3",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    spec = importlib.util.spec_from_file_location(
        "stdlib_source_index", WORK / "betse_mito_grn_reachability_audit.py"
    )
    index_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(index_module)
    revision = subprocess.check_output(
        ["git", "-C", str(CHECKOUT), "rev-parse", "HEAD"], text=True
    ).strip()
    assert revision == REVISION
    indices, inventory = {}, {}
    for path in sorted((CHECKOUT / "betse").rglob("*.py")):
        relative = str(path.relative_to(CHECKOUT))
        data = path.read_bytes()
        installed = (INSTALLED.parent / relative).read_bytes()
        assert installed == data, relative
        inventory[relative] = dict(sha256=hashlib.sha256(data).hexdigest(), installed_exact=True)
        indices[relative] = index_module.Index(relative, data.decode("utf-8"))
    writes, reads, setters, calls, parameter_writes, profiles = [], [], [], [], {}, []
    for index in indices.values():
        for node, parents in index.sites:
            if isinstance(node, ast.Attribute) and node.attr == "Ca_dyn":
                target = writes if isinstance(node.ctx, ast.Store) else reads
                target.append(index.record(node, parents))
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "EndoRetic":
                    calls.append(index.record(node, parents))
                if any(
                    isinstance(arg, ast.Constant) and arg.value == "Ca_dyn"
                    for arg in (*node.args, *[k.value for k in node.keywords])
                ):
                    setters.append(index.record(node, parents))
            if index.path == "betse/science/parameters.py" and isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "self"
                    ):
                        parameter_writes.setdefault(target.attr, []).append(
                            index.record(node, parents)
                        )
                        if target.attr == "ions_dict" and isinstance(node.value, ast.Dict):
                            try:
                                ions = ast.literal_eval(node.value)
                            except (ValueError, TypeError):
                                continue
                            if ions.get("Ca") == 1:
                                profiles.append(index.record(node, parents))
    assert len(writes) == 1 and not setters
    assert writes[0]["path"] == "betse/science/parameters.py" and writes[0]["line"] == 771
    parameter = indices["betse/science/parameters.py"]
    flag = next(
        n
        for n, parents in parameter.sites
        if isinstance(n, ast.Assign) and any(ast.unparse(t) == "self.Ca_dyn" for t in n.targets)
    )
    assert isinstance(flag.value, ast.Constant) and flag.value.value is False
    absent = sorted(ER_PARAMETERS - parameter_writes.keys())
    assert set(absent) == ER_PARAMETERS
    sim = indices["betse/science/sim.py"]
    init = sim.method("Simulator", "init_dynamics")
    guard = next(
        n
        for n in init.body
        if isinstance(n, ast.If) and ast.unparse(n.test) == "p.ions_dict['Ca'] == 1 and p.Ca_dyn"
    )
    assert len(calls) == 1
    assert "self.endo_retic = None" in ast.unparse(guard)
    assert "self.CaATP_block = np.ones(self.mdl)" in ast.unparse(init)
    handler = sim.method("Simulator", "ca_handler")
    assert len(handler.body) == 2
    assert ast.unparse(handler.body[0].test) == "p.alpha_Ca > 0.0"
    assert ast.unparse(handler.body[1].test) == "p.Ca_dyn == 1"
    assert ast.unparse(handler.body[1].body[0]) == "self.endo_retic.update(self, cells, p)"
    loop = next(
        n for n in sim.method("Simulator", "_run_sim_core_loop").body if isinstance(n, ast.For)
    )
    moving = next(
        i
        for i, n in enumerate(loop.body)
        if isinstance(n, ast.For) and ast.unparse(n.iter) == "self.movingIons"
    )
    ca = next(
        i
        for i, n in enumerate(loop.body)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "p.ions_dict['Ca'] == 1"
    )
    grn = next(
        i
        for i, n in enumerate(loop.body)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "p.grn_enabled"
    )
    commit = next(
        i
        for i, n in enumerate(loop.body)
        if isinstance(n, ast.Expr) and ast.unparse(n) == "self.update_all_concs(cells, p)"
    )
    assert moving < ca < grn < commit
    assert ast.unparse(loop.body[ca].body[0]) == "self.ca_handler(cells, p)"
    assert [ast.unparse(n) for n in loop.body[commit : commit + 3]] == [
        "self.update_all_concs(cells, p)",
        "self.update_V(cells, p)",
        "stb.check_v(self.vm)",
    ]
    needed = {"alpha_Ca", "KmCa_Ca", "KmCa_ATP", "cATP", "cADP", "cPi", "deltaGATP"}
    assert needed <= parameter_writes.keys() and profiles
    return dict(
        kind="cells.normal_ecm_calcium_reachability@1",
        source_revision=revision,
        checkout=str(CHECKOUT),
        installed=str(INSTALLED),
        source_inventory=inventory,
        Python_files=len(inventory),
        all_installed_sources_exact=True,
        Ca_dyn_writes=writes,
        Ca_dyn_reads=reads,
        literal_flag_setter_or_lookup_calls=setters,
        sole_Ca_dyn_value=False,
        ER_constructor_calls=calls,
        actual_ER_constructor_guard=sim.record(guard, ()),
        actual_ER_update_guard=sim.record(handler.body[1], ()),
        native_ER_cold_setup_reachable_without_override=False,
        missing_ER_parameter_producers=absent,
        CaATP_reachable_with_enabled_native_Ca_profile=True,
        Ca_enabled_native_profiles=profiles,
        CaATP_parameter_producers={k: parameter_writes[k] for k in sorted(needed)},
        actual_calcium_call=sim.record(loop.body[ca], ()),
        actual_CaATP_guard=sim.record(handler.body[0], ()),
        actual_order=(
            "ordinary ion refresh -> native guarded ca_handler(CaATP; disabled ER) -> GRN -> "
            "deferred ionic commit -> full fields/update_V -> NaN-only check_v"
        ),
        ECM_CaATP_policy=(
            "Source maps Ca environment to membranes before helper; EC-grid fancy-index copy "
            "means helper no_negs cannot mutate source environment, while membrane input is a "
            "view; rho_pump applied twice, rate cache aliases pre-final-rho flux and gets "
            "boundary mask in place; alpha0 leaves previous rate cache unchanged"
        ),
        qualified_prepared_ER_is_external_conditional_inventory_and_cache_seam=True,
        unsupported_flag_override_or_ER_defaults_added=False,
        prior_field_packet_unchanged=True,
        scientific_imports=0,
        scientific_AST_executions=0,
        pytest_collection_runs=0,
        numerical_runs=0,
    )


if __name__ == "__main__":
    result = audit()
    path = WORK / "betse_normal_ecm_calcium_join_reachability_01.json"
    with path.open("x") as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write("\n")
    print(
        json.dumps(
            dict(
                status="native_ER_disabled_CaATP_reachable",
                Python_files=result["Python_files"],
                missing_ER_parameters=result["missing_ER_parameter_producers"],
                witness=str(path),
                sha256=sha(path),
                scientific_imports=0,
                numerical_runs=0,
            )
        )
    )
