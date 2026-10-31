"""Audit pinned BETSE source as text/AST; never import or execute science."""

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REVISION = "5269a714aa2593ed2a6708c4516289977d8ae1a2"
FLAGS = {"mit_enabled", "mol_mit_enabled"}
NETWORK = "betse/science/chemistry/networks.py"
GENE = "betse/science/chemistry/gene.py"
MOLECULE = "betse/science/chemistry/molecules.py"


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Index(ast.NodeVisitor):
    def __init__(self, path, source):
        self.path = path
        self.source = source
        self.tree = ast.parse(source, filename=path)
        self.stack = []
        self.sites = []
        self.visit(self.tree)

    def generic_visit(self, node):
        self.sites.append((node, tuple(self.stack)))
        self.stack.append(node)
        super().generic_visit(node)
        self.stack.pop()

    def record(self, node, parents):
        return {
            "path": self.path,
            "line": node.lineno,
            "end_line": node.end_lineno,
            "scope": ".".join(
                item.name
                for item in parents
                if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            ),
            "source": ast.get_source_segment(self.source, node),
        }

    def method(self, owner, name):
        cls = next(
            node for node in self.tree.body if isinstance(node, ast.ClassDef) and node.name == owner
        )
        return next(
            node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == name
        )


def audit(checkout, installed):
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    assert revision == REVISION, revision
    inventory = {}
    indices = {}
    for path in sorted((checkout / "betse").rglob("*.py")):
        relative = path.relative_to(checkout).as_posix()
        data = path.read_bytes()
        installed_path = installed.parent / relative
        installed_data = installed_path.read_bytes()
        inventory[relative] = {
            "sha256": digest(data),
            "installed_sha256": digest(installed_data),
            "installed_exact": data == installed_data,
        }
        indices[relative] = Index(relative, data.decode("utf-8"))
    assert all(item["installed_exact"] for item in inventory.values())

    calls = {"MasterOfNetworks": [], "Mito": [], "SimMaster": []}
    bindings = []
    writes = []
    literal_flag_lookups = []
    flag_named_dict_keys = []
    for index in indices.values():
        for node, parents in index.sites:
            if isinstance(node, ast.ImportFrom):
                for item in node.names:
                    if item.name == "MasterOfNetworks":
                        record = index.record(node, parents)
                        record.update(module=node.module, alias=item.asname)
                        bindings.append(record)
            if isinstance(node, ast.Call):
                leaf = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else None
                )
                if leaf in calls:
                    record = index.record(node, parents)
                    record["guards"] = [
                        ast.unparse(item.test) for item in parents if isinstance(item, ast.If)
                    ]
                    record["positional_arguments"] = [ast.unparse(arg) for arg in node.args]
                    record["keywords"] = [[kw.arg, ast.unparse(kw.value)] for kw in node.keywords]
                    calls[leaf].append(record)
                if leaf in {"setattr", "getattr", "hasattr", "delattr"} and any(
                    isinstance(arg, ast.Constant) and arg.value in FLAGS
                    for arg in node.args
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                ):
                    literal_flag_lookups.append(index.record(node, parents))
            if isinstance(node, ast.Attribute) and node.attr in FLAGS:
                if isinstance(node.ctx, (ast.Store, ast.Del)):
                    record = index.record(parents[-1], parents[:-1])
                    record["target"] = ast.unparse(node)
                    writes.append(record)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in FLAGS:
                    flag_named_dict_keys.append(index.record(node, parents))

    assert len(bindings) == 2
    assert all(
        item["module"] == "betse.science.chemistry.networks" and item["alias"] is None
        for item in bindings
    )
    assert {(item["path"], item["scope"]) for item in calls["MasterOfNetworks"]} == {
        (GENE, "MasterOfGenes.read_gene_config"),
        (MOLECULE, "MasterOfMolecules.read_mol_config"),
    }
    assert len(calls["MasterOfNetworks"]) == 2
    assert all(
        item["positional_arguments"] == ["sim", "cells", "substances_config", "p"]
        and item["keywords"] == []
        for item in calls["MasterOfNetworks"]
    )

    network = indices[NETWORK]
    constructor = network.method("MasterOfNetworks", "__init__")
    assert [item.arg for item in constructor.args.args] == [
        "self",
        "sim",
        "cells",
        "config_substances",
        "p",
        "mit_enabled",
    ]
    assert len(constructor.args.defaults) == 1
    assert isinstance(constructor.args.defaults[0], ast.Constant)
    assert constructor.args.defaults[0].value is False
    core_writes = [item for item in writes if item["target"] == "self.mit_enabled"]
    assert len(core_writes) == 1
    assert core_writes[0]["scope"] == "MasterOfNetworks.__init__"
    assert core_writes[0]["source"] == "self.mit_enabled = mit_enabled"
    child_writes = [
        item for item in writes if item["target"] in {"mol.mit_enabled", "obj.mit_enabled"}
    ]
    assert len(child_writes) == 6
    assert all(item["path"] == NETWORK for item in child_writes)
    parameter_writes = [item for item in writes if item["target"] == "self.mol_mit_enabled"]
    assert len(parameter_writes) == 2
    assert all(item["source"] == "self.mol_mit_enabled = False" for item in parameter_writes)
    assert len(writes) == len(core_writes) + len(child_writes) + len(parameter_writes)
    assert not literal_flag_lookups
    assert not flag_named_dict_keys
    assert len(calls["Mito"]) == 2
    assert {item["scope"] for item in calls["Mito"]} == {
        "MasterOfNetworks.read_substances",
        "MasterOfNetworks.redefine_dynamic_dics",
    }
    assert all(item["guards"] == ["self.mit_enabled"] for item in calls["Mito"])
    assert not calls["SimMaster"]

    evidence_methods = {
        NETWORK: (
            "MasterOfNetworks",
            [
                "__init__",
                "read_substances",
                "tissue_init",
                "bal_charge",
                "clear_run_loop",
                "run_loop",
                "redefine_dynamic_dics",
            ],
        ),
        GENE: ("MasterOfGenes", ["read_gene_config", "reinitialize"]),
        MOLECULE: ("MasterOfMolecules", ["read_mol_config", "reinitialize"]),
        "betse/science/organelles/mitochondria.py": ("Mito", ["__init__", "get_v", "update"]),
        "betse/science/sim.py": ("Simulator", ["init_dynamics", "_run_sim_core_loop"]),
    }
    methods = []
    for relative, (owner, names) in evidence_methods.items():
        index = indices[relative]
        for name in names:
            method = index.method(owner, name)
            methods.append(
                {
                    "path": relative,
                    "owner": owner,
                    "method": name,
                    "line": method.lineno,
                    "end_line": method.end_lineno,
                    "ast_sha256": digest(ast.dump(method, include_attributes=False).encode()),
                }
            )

    forbidden = sorted(
        name
        for name in sys.modules
        if name.split(".")[0] in {"numpy", "jax", "betse", "cells", "pytest"}
    )
    assert not forbidden, forbidden
    return {
        "kind": "cells.betse_mito_grn_reachability_static_audit@1",
        "status": "blocked_no_builtin_cold_enable_producer",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "native_revision": revision,
        "checkout": str(checkout),
        "installed_package": str(installed),
        "source_inventory": inventory,
        "parsed_python_file_count": len(inventory),
        "installed_exact_file_count": sum(item["installed_exact"] for item in inventory.values()),
        "constructor_default_mit_enabled": False,
        "network_import_bindings": bindings,
        "constructor_calls": calls,
        "flag_writes": writes,
        "literal_dynamic_flag_operations": literal_flag_lookups,
        "literal_flag_string_keys": flag_named_dict_keys,
        "method_anchors": methods,
        "decision": {
            "cold_normal_branch": "Both actual callers omit mit_enabled, so its literal False default reaches the sole core flag assignment. read_substances therefore publishes core.mit=None and no mitochondrial mapping.",
            "normal_dispatch": "Actual normal solver dispatch reaches the network, but does not enable mitochondria. Existing GRN dispatch is not mitochondrial execution credit.",
            "configuration": "Both mol_mit_enabled parameter assignments are False. The commented enable-mitochondria config read has no runtime effect and neither actual constructor passes that parameter.",
            "reinitialize": "Wrapper reinitialize methods refresh network properties on the existing core; there is no core flag write. redefine_dynamic_dics constructs Mito only under an already-true core flag.",
            "restart_boundary": "Original loadSim/pickles.load may deserialize a preenabled object. This audit does not rule out arbitrary externally prepared state; no authenticated built-in cold producer for such an enabled object was found. Loading alone does not establish its provenance.",
            "child_flags": "Molecule/reaction obj.mit_enabled assignments propagate the existing core flag and do not enable the network.",
            "unused_systems_class": "The separate math.systems.SimMaster constructor also has a False default, but no call to SimMaster occurs in the parsed BETSE package; it is not a replacement for MasterOfNetworks.",
            "future_scope": "A source variation explicitly threading True into the actual owner constructor, or an authenticated externally preenabled snapshot, requires a separately named boundary. Neither is represented as native cold reachability here.",
        },
        "existing_component_boundary": {
            "implementation": "src/cells/processes/betse_mitochondria.py",
            "protocol": "validation/organelles/betse_mitochondria_protocol.json",
            "reuse": "Isolated cached-voltage/ordered-ion/charge component only, conditional on an explicit owner and supplied external charge density.",
            "network_order_if_enabled": "clear_run_loop zeroes extra_rho_mit; tissue_init balances cell then environment then mitochondrial counterions; run_loop commits molecular mitochondrial reactions, accumulates molecular rho without scale_factor, computes energy_charge, conditionally publishes simulator charge/current, copies extra_rho_mit to mit.extra_rho, then calls Mito.update.",
            "organelle_order": "Constructor snapshots half volume/area and copies cytosolic ions without refreshing zero Q/V or defining extra_rho. update mutates moving ions in source order from incoming Vmit, then refreshes charge/voltage once.",
            "credit": "No new combined solver, physical/energy/fuel, ECM/fluid/cut or mitochondrial network qualification credit.",
        },
        "static_only": {
            "scientific_imports": forbidden,
            "scientific_ast_execution": False,
            "fixture_or_reference_evaluation": False,
            "pytest_collection": False,
            "numerical_job_launched": False,
            "scientific_files_changed": [],
            "freeze_requested": False,
            "automatic_followup": False,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, default=Path("/mnt/workspaces/Cells/betse-v1.5.0"))
    parser.add_argument(
        "--installed",
        type=Path,
        default=Path("/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages/betse"),
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.checkout, args.installed)
    result["audit_script_sha256"] = digest(Path(__file__).read_bytes())
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "source_files": result["parsed_python_file_count"],
                "output": str(args.output),
                "sha256": digest(args.output.read_bytes()),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
