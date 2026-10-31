"""Regenerate and inspect lifecycle drafts; never execute scientific modules."""

import argparse
import ast
import builtins
import hashlib
import importlib.util
import json
import symtable
import sys
from pathlib import Path

import betse_normal_ecm_init_sim_transition_implementation_audit as common

ROOT = Path("/home/robert/Cells")
WORK = Path(__file__).parent
BASE = Path("/mnt/workspaces/Cells")
TRANSPORT = BASE / "betse-normal-ecm-molecule-transport-prepared-20261031-01/source"
TRANSITION = BASE / "betse-normal-ecm-init-sim-transition-prepared-20261031-02/source"
INIT = BASE / "betse-normal-ecm-init-phase-prepared-20261031-04/source"
PREFIX = "betse_normal_ecm_molecule_lifecycle"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--regenerate", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists() or args.regenerate.exists():
        raise ValueError("Preserve existing static evidence")
    args.regenerate.mkdir(parents=True)
    proofs = {}
    for suffix in ("owners", "phase", "setup", "main"):
        path = WORK / ("prepare_" + PREFIX + "_" + suffix + ".py")
        spec = importlib.util.spec_from_file_location("stdlib_lifecycle_generator_" + suffix, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.ROOT = args.regenerate
        module.main()
    for path in args.regenerate.rglob("*.py"):
        relative = path.relative_to(args.regenerate)
        assert common.normalized(ast.parse(path.read_text())) == common.normalized(
            ast.parse((ROOT / relative).read_text())
        ), str(relative)
        proofs["regeneration/" + str(relative)] = True
    source = ROOT / "src/cells/processes" / (PREFIX + "_source.py")
    old = TRANSPORT / "src/cells/processes/betse_normal_ecm_molecule_transport_source.py"
    tree = ast.parse(old.read_text())
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            assert common.normalized(node) == common.normalized(common.fn(source, node.name)), (
                node.name
            )
            proofs["unchanged_frozen_owner_helper/" + node.name] = True
    for name in (
        "init_profiles",
        "initDenv",
        "_finalize_events_global",
        "_finalize_events_tissue",
        "f_sweep",
        "static_and_blocks",
        "screening_conductivity",
        "clear_cache",
        "clear_storage",
    ):
        assert common.normalized(common.fn(source, name)) == common.normalized(
            common.fn(
                TRANSITION / "src/cells/processes/betse_normal_ecm_init_sim_transition_source.py",
                name,
            )
        ), name
        proofs["unchanged_transition02_native_body/" + name] = True
    controller = ROOT / "src/cells/processes" / (PREFIX + ".py")
    for name in ("complete_record", "prepare_complete", "prepare_failed_prefix", "check_complete"):
        assert common.normalized(common.fn(controller, name)) == common.normalized(
            common.fn(
                TRANSITION / "src/cells/processes/betse_normal_ecm_init_sim_transition.py", name
            )
        ), name
        proofs["complete_or_failed_INIT_source_artifact/" + name] = True
    allowed = set(dir(builtins)) | {"__name__", "__file__", "__doc__", "__package__", "__spec__"}
    files = sorted((ROOT / "src/cells/processes").glob(PREFIX + "*.py"))
    for path in files:
        text = path.read_text()
        tree = ast.parse(text)
        compile(tree, str(path), "exec")
        known = common.bound_names(tree) | allowed

        def missing(scope, known=known):
            result = {
                s.get_name()
                for s in scope.get_symbols()
                if s.is_global() and s.is_referenced() and s.get_name() not in known
            }
            for child in scope.get_children():
                result |= missing(child)
            return result

        assert not missing(symtable.symtable(text, str(path), "exec")), str(path)
    assert len(files) == 6
    assert not any(
        n.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "pytest"}
        for n in sys.modules
    )
    result = dict(
        kind="cells.general_molecule_lifecycle_draft_audit@1",
        status="draft_sources_only_remaining_reference_native_controls",
        proofs=proofs,
        source_sha256={str(p.relative_to(ROOT)): sha(p) for p in files},
        compile_and_global_names=True,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_model_reference_evaluations=0,
        pytest_collections=0,
        numerical_runs=0,
    )
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                output=str(args.output),
                sha256=sha(args.output),
                proofs=len(proofs),
                compiled_files=len(files),
            )
        )
    )


if __name__ == "__main__":
    main()
