"""Read the native general-molecule configuration and FULL owner order; stdlib only."""
# ruff: noqa: E501 -- native-source findings retained as metadata strings.

import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path("/home/robert/Cells")
NATIVE = Path("/mnt/workspaces/Cells/betse-v1.5.0")
INSTALLED = Path("/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages")
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-init-phase-prepared-20261031-02")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fn(relative, name, owner=None):
    tree = ast.parse((NATIVE / relative).read_text())
    if owner:
        tree = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == owner)
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


def record(relative, name, owner=None):
    node = fn(relative, name, owner)
    return dict(
        path=relative,
        source_sha256=sha(NATIVE / relative),
        owner=owner,
        function=name,
        lines=[node.lineno, node.end_lineno],
        AST_sha256=hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
        calls=[
            dict(callee=ast.unparse(n.func), line=n.lineno)
            for n in ast.walk(node)
            if isinstance(n, ast.Call)
        ],
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    methods = {}
    for relative, owner, names in (
        ("betse/science/parameters.py", "Parameters", ("load",)),
        (
            "betse/science/sim.py",
            "Simulator",
            (
                "init_core",
                "init_dynamics",
                "_run_sim_core_loop",
                "clear_storage",
                "update_V",
            ),
        ),
        (
            "betse/science/chemistry/molecules.py",
            "MasterOfMolecules",
            ("__init__", "read_mol_config", "reinitialize"),
        ),
        (
            "betse/science/chemistry/gene.py",
            "MasterOfGenes",
            ("__init__", "read_gene_config", "reinitialize"),
        ),
        (
            "betse/science/chemistry/networks.py",
            "MasterOfNetworks",
            (
                "__init__",
                "read_substances",
                "tissue_init",
                "clear_run_loop",
                "run_loop",
                "read_channels",
                "run_loop_channels",
                "clear_cache",
                "energy_charge",
            ),
        ),
        ("betse/science/physics/pressures.py", None, ("osmotic_P",)),
    ):
        for name in names:
            methods[(owner or "module") + "." + name] = record(relative, name, owner)
    parameters = fn("betse/science/parameters.py", "load", "Parameters")
    branch = next(
        n
        for n in ast.walk(parameters)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "self.network_config is not None"
    )
    assert any(
        isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "self.molecules_enabled"
        for n in branch.body
    )
    assert not any(
        isinstance(n, ast.Assign)
        and any(ast.unparse(t) == "self.molecules_enabled" for t in n.targets)
        for statement in branch.orelse
        for n in ast.walk(statement)
    )
    assert any(
        isinstance(n, ast.Assign)
        and ast.unparse(n.targets[0]) == "self.Ca_dyn"
        and n.value.value is False
        for n in ast.walk(parameters)
    )
    setup = fn("betse/science/sim.py", "init_dynamics", "Simulator")
    setup_guards = [
        n
        for n in setup.body
        if isinstance(n, ast.If) and ast.unparse(n.test) in ("p.molecules_enabled", "p.grn_enabled")
    ]
    assert [ast.unparse(n.test) for n in setup_guards] == ["p.molecules_enabled", "p.grn_enabled"]
    loop = next(
        n
        for n in fn("betse/science/sim.py", "_run_sim_core_loop", "Simulator").body
        if isinstance(n, ast.For)
    )
    calls = [
        n
        for n in loop.body
        if isinstance(n, ast.If) and ast.unparse(n.test) in ("p.molecules_enabled", "p.grn_enabled")
    ]
    assert [ast.unparse(n.test) for n in calls] == ["p.molecules_enabled", "p.grn_enabled"]
    for node, role in zip(calls, ("molecules", "grn"), strict=True):
        text = ast.unparse(node)
        assert (
            text.index(".clear_run_loop(")
            < text.index(".run_loop_transporters(")
            < text.index(".run_loop_channels(")
            < text.index(".run_loop_modulators(")
            < text.index(".run_loop(")
        )
        assert ".run_fast_loop_channels(" not in text
        assert "self." + role + ".core.run_loop(" in text
    run = fn("betse/science/chemistry/networks.py", "run_loop", "MasterOfNetworks")
    publications = {
        ast.unparse(n.targets[0]): ast.unparse(n.value)
        for n in run.body
        if isinstance(n, ast.If) and ast.unparse(n.test) == "p.substances_affect_charge"
        for n in n.body
        if isinstance(n, ast.Assign)
    }
    assert publications == {
        "sim." + name: "self." + name
        for name in (
            "extra_rho_cells",
            "extra_rho_env",
            "extra_J_mem",
            "extra_Jenv_x",
            "extra_Jenv_y",
        )
    }
    osmo = ast.unparse(fn("betse/science/physics/pressures.py", "osmotic_P"))
    assert (
        "sim.molecules.core.molecules.items()" in osmo and "sim.grn.core.molecules.items()" in osmo
    )
    native = {}
    for path in sorted((NATIVE / "betse").rglob("*.py")):
        name = str(path.relative_to(NATIVE))
        assert sha(path) == sha(INSTALLED / name), name
        native[name] = sha(path)
    assert len(native) == 332
    result = dict(
        kind="cells.native_general_molecule_FULL_dispatch_source_boundary@1",
        status="source_audited_unrun",
        native_revision="5269a714aa2593ed2a6708c4516289977d8ae1a2",
        native_source_sha256=native,
        methods=methods,
        parent_manifest_sha256=sha(PARENT / "MANIFEST.json"),
        general_configuration_obstruction=dict(
            path="betse/science/parameters.py",
            lines=[branch.lineno, branch.end_lineno],
            native_expression="self.network_config = self._conf.get('general network', None)",
            missing_branch_attribute="molecules_enabled",
            exact_obstruction="Absent general network leaves molecules_enabled unwritten; the else sets only mol_mit_enabled=False. No automatic false default is admitted.",
            explicit_present_configuration="implement network is the independent general-handler flag; explicit True and False supported",
        ),
        source_order=[
            "general setup",
            "GRN setup",
            "primary/CaATP refresh",
            "general dispatch",
            "GRN dispatch",
            "source noise/mechanics guards",
            "deferred primary commit",
            "current/field",
        ],
        enabled_flags_independent=True,
        GRN_disabled_general_enabled_native_path=True,
        shared_publication_assignment=publications,
        shared_publication_rule="Last enabled source writer replaces shared charge/current arrays; publication false retains incoming shared arrays. Never sum network publications.",
        osmotic_rule="Source adds current concentrations from each enabled owner independently.",
        molecular_namespaces="Each owner has independent same-named molecular dictionaries and cache; cross-owner X/Y aliasing is forbidden.",
        ER_path="Parameters.load hard-sets Ca_dyn=False. No enablement inferred from handler flags.",
        first_scope="Supplied ordinary FULL/ECM SIM entry, bounded nonempty native chemistry/ECM transport; no whole initializer/phase/persistence claim.",
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_model_reference_evaluations=0,
        pytest_collections=0,
        numerical_runs=0,
        active_job_queries=0,
    )
    assert not any(
        n.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "pytest"}
        for n in sys.modules
    )
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                status="source_audited",
                methods=len(methods),
                native_files=len(native),
                configuration_obstruction=True,
            )
        )
    )


if __name__ == "__main__":
    main()
