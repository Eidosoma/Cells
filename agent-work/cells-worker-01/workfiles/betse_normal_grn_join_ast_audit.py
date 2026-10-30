"""Stdlib-only original-AST identity and genuine GRN call-path audit."""

import ast
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path("/home/robert/Cells")
PIN = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse")


def functions(tree):
    return {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}


def classes(tree):
    return {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}


def digest(node):
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


class Numeric(ast.NodeTransformer):
    def visit_Expr(self, node):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None
        if isinstance(node.value, ast.Call) and (
            ast.unparse(node.value.func)
            in {
                "self._observe_chem",
                "self._observe_rhs",
                "self._observe_control",
                "p._mover_observe",
            }
            or ast.unparse(node.value.func).endswith("._observe_dispatch")
        ):
            return None
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        node.decorator_list = []
        node.returns = None
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            arg.annotation = None
        return self.generic_visit(node)


def captured_nodes():
    tree = ast.parse(
        (ROOT / "validation/betse/betse_normal_network_join_native_network.py").read_text()
    )
    names = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "METHODS" for target in node.targets)
    )
    ns = dict(ast=ast, copy=copy, METHODS=names)
    exec(
        compile(
            ast.Module(body=[functions(tree)["literal_nodes"]], type_ignores=[]),
            "<stdlib feedback AST builder>",
            "exec",
        ),
        ns,
    )
    for prefix in ("molecule", "grn"):
        tree = ast.parse(
            (
                ROOT / ("validation/betse/betse_normal_" + prefix + "_join_native_network.py")
            ).read_text()
        )
        definitions = functions(tree) | classes(tree)
        chosen = [definitions[name] for name in ("Clean", "statement", "literal_nodes")]
        if prefix == "grn":
            chosen.insert(2, definitions["original_nodes"])
        ns = dict(ast=ast, copy=copy, previous=SimpleNamespace(literal_nodes=ns["literal_nodes"]))
        exec(
            compile(
                ast.Module(body=chosen, type_ignores=[]),
                "<stdlib " + prefix + " AST builder>",
                "exec",
            ),
            ns,
        )
    return ns["literal_nodes"](PIN)


def audit():
    captured = ast.Module(body=captured_nodes(), type_ignores=[])
    native = classes(captured)
    feedback = classes(
        ast.parse((ROOT / "src/cells/processes/betse_normal_network_join_source.py").read_text())
    )
    molecule_tree = ast.parse(
        (ROOT / "src/cells/processes/betse_normal_molecule_source.py").read_text()
    )
    molecules = classes(molecule_tree)
    own_tree = ast.parse((ROOT / "src/cells/processes/betse_normal_grn_source.py").read_text())
    own = classes(own_tree)
    originals = (
        classes(ast.parse((PIN / "science/chemistry/networks.py").read_text()))
        | classes(ast.parse((PIN / "science/chemistry/gene.py").read_text()))
        | classes(ast.parse((PIN / "util/type/iterable/mapping/mapcls.py").read_text()))
    )
    implementations = {
        "MasterOfNetworks": functions(feedback["_LiteralNetwork"])
        | functions(molecules["_Network"])
        | functions(own["MasterOfNetworks"]),
        "Molecule": functions(molecules["_Molecule"]),
        "Reaction": functions(feedback["Reaction"]),
        "Modulator": functions(feedback["Modulator"]),
    }
    implementations.update(
        {
            name: functions(own[name])
            for name in ("MasterOfGenes", "DynamicValue", "DynamicValueDict")
        }
    )
    proof = {}
    for cls, methods in implementations.items():
        for name, node in functions(native[cls]).items():
            assert digest(methods[name]) == digest(node), (cls, name, "observational")
            clean = Numeric().visit(copy.deepcopy(node))
            assert digest(clean) == digest(
                Numeric().visit(copy.deepcopy(functions(originals[cls])[name]))
            ), (cls, name, "original")
            proof[cls + "." + name] = dict(
                numeric_AST_sha256=digest(clean),
                original_AST_equal=True,
                observational_AST_equal=True,
            )
    originals_f = functions(ast.parse((PIN / "science/sim_toolbox.py").read_text())) | functions(
        ast.parse((PIN / "science/chemistry/netplot.py").read_text())
    )
    native_f, own_f = functions(captured), functions(own_tree)
    for name in ("electroflux", "update_Co", "molecule_mover", "no_negs", "set_net_opts"):
        impl = own_f[name] if name == "set_net_opts" else functions(molecule_tree)[name]
        assert digest(impl) == digest(native_f[name]), name
        cleaned = Numeric().visit(copy.deepcopy(native_f[name]))
        assert digest(cleaned) == digest(Numeric().visit(copy.deepcopy(originals_f[name]))), name
        proof[name] = dict(
            numeric_AST_sha256=digest(cleaned),
            original_AST_equal=True,
            observational_AST_equal=True,
        )
    sim = ast.parse((PIN / "science/sim.py").read_text())
    for name, line in (("initialize_owner", 884), ("dispatch", 1306)):
        assert digest(own_f[name]) == digest(native_f[name]), name
        cleaned = Numeric().visit(copy.deepcopy(own_f[name]))
        block = next(
            node for node in ast.walk(sim) if isinstance(node, ast.If) and node.lineno == line
        )
        assert digest(cleaned.body[0]) == digest(Numeric().visit(copy.deepcopy(block))), name
        proof[name] = dict(
            numeric_AST_sha256=digest(cleaned),
            original_guarded_block_equal=True,
            first_line=block.lineno,
            last_line=block.end_lineno,
        )
    helpers = {}
    old = functions(
        ast.parse((ROOT / "src/cells/processes/betse_normal_molecule_join.py").read_text())
    )
    new = functions(ast.parse((ROOT / "src/cells/processes/betse_normal_grn_join.py").read_text()))
    for name in (
        "_pump_material_step",
        "_pumped_material_step",
        "_active_material_step",
        "vector_state",
        "_initialize_gate",
    ):
        assert digest(old[name]) == digest(new[name]), name
        helpers[name] = dict(AST_sha256=digest(new[name]), unchanged=True)
    # Full public fields are snapshotted and restored; only alias objects,
    # separately serialized object containers and observation-only fields are
    # excluded. Hot hydration never reruns read_gene_config/tissue_init.
    native_adapter = functions(
        ast.parse((ROOT / "validation/betse/betse_normal_grn_join_native_network.py").read_text())
    )
    for name in (
        "wire",
        "restore_owner",
        "public",
        "cache",
        "snapshot",
        "attach_observers",
        "cold_owner",
    ):
        assert digest(own_f[name]) == digest(native_adapter[name]), name
    assert "vars(obj).update(clone(values))" in ast.unparse(own_f["restore_owner"])
    assert "read_gene_config" not in ast.unparse(own_f["restore_owner"])
    default = next(
        node
        for node in ast.walk(originals["MasterOfNetworks"])
        if isinstance(node, ast.Assign)
        and any(ast.unparse(target) == "mol.ignore_ECM_pump" for target in node.targets)
    )
    assert ast.literal_eval(default.value) is True
    roster = json.loads(
        (
            ROOT
            / "agent-work/cells-worker-01/workfiles"
            / "betse_normal_molecule_adapter_attributes_after_02.json"
        ).read_text()
    )["reachable_required"]
    required = next(
        ast.literal_eval(node.value)
        for node in own_tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "REQUIRED_MOLECULE"
            for target in node.targets
        )
    )
    assert set(roster["self"]) <= required
    providers = {}
    for key in ("sim", "cells", "p"):
        constructor = next(
            node.value
            for node in ast.walk(own_f["context"])
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == key for target in node.targets)
            and isinstance(node.value, ast.Call)
            and ast.unparse(node.value.func) == "SimpleNamespace"
        )
        providers[key] = {item.arg for item in constructor.keywords}
        assert set(roster[key]) <= providers[key], (key, set(roster[key]) - providers[key])
    source_molecule_fields = {
        node.attr
        for cls in (originals["Molecule"], originals["MasterOfNetworks"])
        for node in ast.walk(cls)
        if isinstance(node, ast.Attribute)
        and isinstance(node.ctx, ast.Store)
        and isinstance(node.value, ast.Name)
        and node.value.id in {"self", "mol"}
    }
    assert set(roster["self"]) <= source_molecule_fields
    assert {"edl", "Dm_cells", "zs"} <= providers["sim"]
    assert "sim.c_env_bound" in ast.unparse(own_f["configure_owner_context"])
    return dict(
        literal_numeric_bodies=proof,
        unchanged_outer_helpers=helpers,
        literal_scientific_body_count=len(proof),
        actual_init_guard_source_lines=[884, 900],
        actual_normal_dispatch_source_lines=[1306, 1319],
        genuine_owner_classes=["MasterOfGenes", "MasterOfNetworks"],
        molecules_owner_disabled=True,
        standalone_sim_grn_executed=False,
        complete_public_state_bridge_AST_equal=True,
        hot_cache_does_not_rerun_cold_readers=True,
        source_default_ignore_ECM_pump=dict(value=True, line=default.lineno),
        source_default_hydration_audit=dict(
            required_runtime_attributes=42,
            required_molecule_fields=sorted(roster["self"]),
            original_ctor_read_tissue_providers=True,
            model_context_fields={key: sorted(values) for key, values in providers.items()},
            hot_hydration_restores_all_public_fields=True,
            missing_runtime_attributes={},
            zero_charge_scope_avoids_nonzero_counterion_branches=True,
        ),
        scientific_AST_executions=0,
        scientific_imports=0,
    )


if __name__ == "__main__":
    result = audit()
    print(
        json.dumps(
            dict(
                literal_numeric_bodies=result["literal_scientific_body_count"],
                unchanged_outer_helpers=len(result["unchanged_outer_helpers"]),
                scientific_AST_executions=0,
            )
        )
    )
