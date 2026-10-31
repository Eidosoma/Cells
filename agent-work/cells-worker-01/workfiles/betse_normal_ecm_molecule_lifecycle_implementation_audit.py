"""Bounded complete source proofs; no scientific import or AST execution."""

import argparse
import ast
import builtins
import hashlib
import importlib.util
import json
import resource
import symtable
import sys
from pathlib import Path

import betse_normal_ecm_init_sim_transition_implementation_audit as common
from betse_normal_ecm_molecule_transport_implementation_audit import RemoveObservations

ROOT = Path("/home/robert/Cells")
WORK = Path(__file__).parent
BASE = Path("/mnt/workspaces/Cells")
TRANSPORT = BASE / "betse-normal-ecm-molecule-transport-prepared-20261031-01/source"
TRANSITION = BASE / "betse-normal-ecm-init-sim-transition-prepared-20261031-02/source"
INIT = BASE / "betse-normal-ecm-init-phase-prepared-20261031-04/source"
NATIVE = BASE / "betse-v1.5.0/betse"
PREFIX = "betse_normal_ecm_molecule_lifecycle"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve(name):
    if name == "validation.betse.betse_normal_ecm_molecule_failure_checks":
        return BASE / (
            "ecm-molecule-capture-repair-20261031-01/proposal/validation/betse/"
            "betse_normal_ecm_molecule_failure_checks.py"
        )
    roots = (ROOT,) if PREFIX in name else (TRANSPORT, TRANSITION, INIT)
    # The reviewed INIT04 reference override is explicit in this new packet.
    if name in (
        "validation.betse.betse_normal_ecm_init_phase_reference",
        "validation.betse.betse_normal_ecm_event_join_reference",
    ):
        roots = (INIT,)
    for root in roots:
        for prefix in ("", "src/"):
            for suffix in (".py", "/__init__.py"):
                path = root / (prefix + name.replace(".", "/") + suffix)
                if path.is_file():
                    return path
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--regenerate", type=Path, required=True)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 512 * 2**20))
    if args.output.exists() or args.regenerate.exists():
        raise ValueError("Preserve previous static evidence; use exclusive paths")
    args.regenerate.mkdir(parents=True)
    proofs = {}

    def same(label, actual, wanted):
        assert common.normalized(actual) == common.normalized(wanted), label
        proofs[label] = True

    for suffix in ("owners", "phase", "setup", "main", "reference", "native", "checks"):
        path = WORK / ("prepare_" + PREFIX + "_" + suffix + ".py")
        spec = importlib.util.spec_from_file_location("stdlib_lifecycle_generator_" + suffix, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.ROOT = args.regenerate
        module.main()
    for path in sorted(args.regenerate.rglob("*.py")):
        relative = path.relative_to(args.regenerate)
        same(
            "regeneration/" + str(relative),
            ast.parse(path.read_text()),
            ast.parse((ROOT / relative).read_text()),
        )
    product = ROOT / "src/cells/processes" / (PREFIX + "_source.py")
    independent = ROOT / "validation/betse" / (PREFIX + "_native_source.py")
    old = TRANSPORT / "src/cells/processes/betse_normal_ecm_molecule_transport_source.py"
    for node in ast.parse(old.read_text()).body:
        if isinstance(node, ast.FunctionDef):
            same("frozen_transport01_helper/" + node.name, common.fn(product, node.name), node)
    old_class = next(
        n
        for n in ast.parse(old.read_text()).body
        if isinstance(n, ast.ClassDef) and n.name == "MasterOfNetworks"
    )
    new_class = next(
        n
        for n in ast.parse(product.read_text()).body
        if isinstance(n, ast.ClassDef) and n.name == "MasterOfNetworks"
    )
    new_class.body = [n for n in new_class.body if getattr(n, "name", None) != "clear_cache"]
    same("whole_transport01_network_class_plus_clear_cache", new_class, old_class)
    for owner, names in (
        ("MasterOfMolecules", ("__init__", "read_mol_config", "reinitialize")),
        (
            "MasterOfNetworks",
            ("read_transporters", "write_transporters", "run_loop_transporters", "clear_cache"),
        ),
        ("Transporter", ("__init__", "init_reaction")),
    ):
        native = NATIVE / (
            "science/chemistry/molecules.py"
            if owner == "MasterOfMolecules"
            else "science/chemistry/networks.py"
        )
        for name in names:
            same(
                "native/" + owner + "." + name,
                RemoveObservations().visit(common.fn(product, name, owner)),
                RemoveObservations().visit(common.native_clean(common.fn(native, name, owner))),
            )
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
        same(
            "frozen_transition02_body/" + name,
            common.fn(product, name),
            common.fn(
                TRANSITION / "src/cells/processes/betse_normal_ecm_init_sim_transition_source.py",
                name,
            ),
        )
    skip = {
        "MasterOfNetworks",
        "Transporter",
        "init_profiles",
        "initDenv",
        "_finalize_events_global",
        "_finalize_events_tissue",
        "f_sweep",
        "static_and_blocks",
        "screening_conductivity",
    }
    other = ast.parse(independent.read_text())
    for node in ast.parse(product.read_text()).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name not in skip:
            matched = next(
                n for n in other.body if isinstance(n, type(node)) and n.name == node.name
            )
            same("independent_complete_owner_helper/" + node.name, matched, node)
    controller = ROOT / "src/cells/processes" / (PREFIX + ".py")
    old_controller = TRANSITION / "src/cells/processes/betse_normal_ecm_init_sim_transition.py"
    for name in ("complete_record", "prepare_complete", "prepare_failed_prefix", "check_complete"):
        same(
            "original_complete_or_failed_INIT/" + name,
            common.fn(controller, name),
            common.fn(old_controller, name),
        )
    old_phase = INIT / "src/cells/processes/betse_normal_ecm_init_phase.py"
    phase = ROOT / "src/cells/processes" / (PREFIX + "_phase.py")
    adapted = common.fn(phase, "advance")
    adapted.args = common.fn(old_phase, "advance").args
    post = next(
        n
        for n in ast.walk(adapted)
        if isinstance(n, ast.FunctionDef) and n.name == "on_post_network"
    )
    assert ast.unparse(post.body[-2].targets[0]) == "holder['before_commit']"
    assert ast.unparse(post.body[-1].test) == "before_commit is not None"
    post.body = post.body[:-2]

    class InversePhase(ast.NodeTransformer):
        def visit_Call(self, node):
            called = ast.unparse(node.func)
            if called == "owner_context":
                node.func = ast.parse("network.make_context", mode="eval").body
                node.args.insert(
                    2, ast.parse("ions.data(binding.inputs['network'])", mode="eval").body
                )
            elif called in {
                "restore_owners",
                "install_stores",
                "owners.cache",
                "owners.validate_phase_cache",
            }:
                node.func = ast.parse(
                    {
                        "restore_owners": "source.restore",
                        "install_stores": "setup.install",
                        "owners.cache": "common.cache",
                        "owners.validate_phase_cache": "source.validate_init_cache",
                    }[called],
                    mode="eval",
                ).body
            elif called == "dispatch_owners":
                node.func = ast.parse("source.run_dispatch", mode="eval").body
                node.args = (
                    node.args[:4]
                    + ast.parse("(before_network,before_channels)", mode="eval").body.elts
                )
            elif called == "phase_failure_snapshot":
                node.func = ast.parse("catalog.failure_snapshot", mode="eval").body
            return self.generic_visit(node)

        def visit_keyword(self, node):
            if node.arg == "source_phase" and ast.unparse(node.value) == "binding.calendar.phase":
                node.value = ast.Constant("INIT")
            if (
                node.arg == "legacy_run_sim"
                and ast.unparse(node.value) == "binding.calendar.phase == 'SIM'"
            ):
                node.value = ast.Constant(False)
            return self.generic_visit(node)

    adapted = InversePhase().visit(adapted)
    on_network = next(
        n for n in ast.walk(adapted) if isinstance(n, ast.FunctionDef) and n.name == "on_network"
    )
    on_network.body.insert(3, ast.parse("common.configure(ctx,ions.data(binding.catalog))").body[0])
    same(
        "complete_INIT04_primary_NaK_CaATP_mechanics_commit_field_advance_inverse",
        adapted,
        common.fn(old_phase, "advance"),
    )
    reference = ROOT / "validation/betse" / (PREFIX + "_reference.py")
    same(
        "reviewed_INIT04_complete_precision_and_failure_CLI",
        common.fn(reference, "main"),
        common.fn(INIT / "validation/betse/betse_normal_ecm_init_phase_reference.py", "main"),
    )
    models = ROOT / "validation/betse" / (PREFIX + "_reference_models.py")
    model = common.fn(models, "phase_rules")
    returned = next(n for n in model.body if isinstance(n, ast.Return))
    for item in returned.value.keywords:
        if item.arg in {
            "grn_owner_reused",
            "grn_core_reused",
            "molecular_current_concentrations_retained",
        }:
            item.value = ast.Constant(True)
    same(
        "transition02_phase_reset_arithmetic_only_owner_metadata_changed",
        model,
        common.fn(
            TRANSITION / "validation/betse/betse_normal_ecm_init_sim_transition_reference.py",
            "phase_rules",
        ),
    )
    native_helper = ROOT / "validation/betse" / (PREFIX + "_native_network.py")
    literal = common.fn(native_helper, "literal_nodes")
    assert ast.unparse(literal.body[-2]).startswith("network.body.append(")
    literal.body.pop(-2)
    same(
        "whole_transport01_authenticated_native_loader_plus_clear_cache",
        literal,
        common.fn(
            TRANSPORT / "validation/betse/betse_normal_ecm_molecule_transport_native_network.py",
            "literal_nodes",
        ),
    )
    files = []
    for directory in ("src/cells/processes", "validation/betse", "tests/unit"):
        files.extend((ROOT / directory).glob("*" + PREFIX + "*.py"))
    allowed = set(dir(builtins)) | {"__name__", "__file__", "__doc__", "__package__", "__spec__"}
    for path in sorted(files):
        source = path.read_text()
        tree = ast.parse(source)
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

        assert not missing(symtable.symtable(source, str(path), "exec")), (
            str(path),
            sorted(missing(symtable.symtable(source, str(path), "exec"))),
        )
        for statement in tree.body:
            if not isinstance(statement, ast.ImportFrom):
                continue
            for alias in statement.names:
                dep = resolve(statement.module + "." + alias.name)
                if dep is None:
                    continue
                name = alias.asname or alias.name
                used = {
                    n.attr
                    for n in ast.walk(tree)
                    if isinstance(n, ast.Attribute)
                    and isinstance(n.value, ast.Name)
                    and n.value.id == name
                }
                bound = common.bound_names(ast.parse(dep.read_text()))
                assert used <= bound, (str(path), str(dep), sorted(used - bound))
    assert len(files) == 14
    assert not any(
        n.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "pytest"}
        for n in sys.modules
    )
    result = dict(
        kind="cells.held_molecule_lifecycle_implementation_audit@1",
        status="source_static_complete_science_unrun",
        proofs=proofs,
        compile_and_global_names=True,
        direct_module_attributes=True,
        source_sha256={str(p.relative_to(ROOT)): sha(p) for p in sorted(files)},
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_model_reference_evaluations=0,
        pytest_collections=0,
        numerical_runs=0,
        regenerated_files=len(list(args.regenerate.rglob("*.py"))),
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
                scientific_evaluations=0,
            )
        )
    )


if __name__ == "__main__":
    main()
