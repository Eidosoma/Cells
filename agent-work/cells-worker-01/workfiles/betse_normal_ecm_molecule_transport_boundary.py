"""Audit reachable configured general-owner ECM transport; stdlib sources only."""
# ruff: noqa: E501 -- Source findings are retained as complete metadata statements.

import ast
import hashlib
import json
from pathlib import Path

BASE = Path("/mnt/workspaces/Cells")
NATIVE = BASE / "betse-v1.5.0/betse"
INSTALLED = BASE / "venv-betse/lib/python3.13/site-packages/betse"
PARENT = BASE / "betse-normal-ecm-molecule-dispatch-prepared-20261031-01"
TRANSPORTER = BASE / "betse-normal-transporter-prepared-20261030-03"
WORK = Path(__file__).parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fn(path, name, owner=None):
    tree = ast.parse(path.read_text())
    if owner:
        tree = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == owner)
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


def main():
    methods = {}
    for path, owner, names in (
        ("science/parameters.py", "Parameters", ("load",)),
        ("science/sim.py", "Simulator", ("init_dynamics", "_run_sim_core_loop")),
        (
            "science/chemistry/molecules.py",
            "MasterOfMolecules",
            ("__init__", "read_mol_config", "reinitialize"),
        ),
        (
            "science/chemistry/networks.py",
            "MasterOfNetworks",
            (
                "read_transporters",
                "write_transporters",
                "run_loop_transporters",
                "clear_run_loop",
                "run_loop",
            ),
        ),
        ("science/chemistry/networks.py", "Transporter", ("__init__", "init_reaction")),
        ("science/sim_toolbox.py", None, ("div_env",)),
    ):
        for name in names:
            node = fn(NATIVE / path, name, owner)
            methods[(owner or "module") + "." + name] = dict(
                path=path,
                source_sha256=sha(NATIVE / path),
                line=node.lineno,
                end_line=node.end_lineno,
                AST_sha256=hashlib.sha256(
                    ast.dump(node, include_attributes=False).encode()
                ).hexdigest(),
            )
    networks = NATIVE / "science/chemistry/networks.py"
    read = ast.unparse(
        fn(NATIVE / "science/chemistry/molecules.py", "read_mol_config", "MasterOfMolecules")
    )
    assert read.index("self.core.read_transporters(") < read.index("self.core.write_transporters(")
    assert "self.transporters = True" in read
    run = ast.unparse(fn(networks, "run_loop_transporters", "MasterOfNetworks"))
    assert run.index(".flux = sim.rho_pump") < run.index("self.extra_J_mem +=")
    assert run.index("delta_react =") < run.index("delta_prod =")
    assert "self.env_concs[self.transporters[name].reactants_list[i]][targ_env]" in run
    assert "self.env_concs[self.transporters[name].products_list[i]][targ_env]" in run
    assert "ignore_ECM_transporter" not in run
    write = ast.unparse(fn(networks, "write_transporters", "MasterOfNetworks"))
    assert "stb.div_env(" in write and "[cells.map_mem2ecm]" in write
    assert "ignore_ECM_transporter" not in write
    div = ast.unparse(fn(NATIVE / "science/sim_toolbox.py", "div_env"))
    assert "flux_env[cells.map_mem2ecm] = flux" in div
    assert "cells.M_divmap_mem2ecm" in div
    hashes = {}
    for path in sorted(NATIVE.rglob("*.py")):
        name = str(path.relative_to(NATIVE))
        assert sha(path) == sha(INSTALLED / name), name
        hashes[name] = sha(path)
    assert len(hashes) == 332
    assert sha(PARENT / "MANIFEST.json") == (
        "e51f7eead8d6bfe3a0e4f669005386e6f4271632f0531084754320025b1ed922"
    )
    assert sha(TRANSPORTER / "inputs.json") == (
        "8f0f502049d62344c36df591da920314c54f26b78a1ea6f36f34ea9936af45cd"
    )
    result = dict(
        kind="cells.normal_ecm_general_transporter_reachable_boundary@1",
        status="reachable_source_seam_audited_unrun",
        native_revision="5269a714aa2593ed2a6708c4516289977d8ae1a2",
        native_python_sha256=hashes,
        methods=methods,
        dependencies=dict(
            molecule_dispatch01=dict(
                path=str(PARENT), manifest_sha256=sha(PARENT / "MANIFEST.json")
            ),
            transporter03=dict(
                path=str(TRANSPORTER), inputs_sha256=sha(TRANSPORTER / "inputs.json")
            ),
        ),
        source_observations=[
            "Present general configuration builds transporters through the actual general owner.",
            "General clear/transporters/channels/modulators/chemistry precedes the independent GRN owner.",
            "Configured rates use ordinary rho_pump=1; no dormant movement is activated.",
            "Current increments precede all reactant then product commits and can survive failure.",
            "Internal membrane-buffer commits omit each stoichiometric coefficient.",
            "ECM external commits use div_env followed by native target-environment indexing.",
            "Fast div_env uses indexed assignment; repeated map sites retain a last write, not a sum.",
            "Slow div_env uses the original area map and grid volume.",
            "The configured ignore ECM field is stored but not consumed by builder/executor.",
            "General and GRN shared charge/current publications remain last-writer assignments.",
            "Whole initializer, native parser, latent disabled owners, arbitrary pump weights and movement remain excluded.",
        ],
        planned_scope="All-target cell-zone configured general-owner transporters; optional existing GRN owner. "
        "Cold first/second missing-max-rate refusals and inherited molecular failures remain separate raw controls.",
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_model_reference_evaluations=0,
        numerical_runs=0,
        active_job_queries=0,
    )
    output = WORK / "betse_normal_ecm_molecule_transport_boundary_01.json"
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                output=str(output),
                sha256=sha(output),
                methods=len(methods),
                native_files=len(hashes),
            )
        )
    )


if __name__ == "__main__":
    main()
