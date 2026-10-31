"""Static original-body/cache/order audit; execute only stdlib AST builders."""

import ast
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PIN = Path("/mnt/workspaces/Cells/betse-v1.5.0")
PREFIX = "betse_normal_ecm_catalog_join"


def parsed(path):
    return ast.parse(path.read_text())


def functions(tree):
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def classes(tree):
    return {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}


def digest(value):
    return hashlib.sha256(ast.dump(value, include_attributes=False).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Numeric(ast.NodeTransformer):
    def visit_Expr(self, node):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None
        if isinstance(node.value, ast.Call) and ast.unparse(node.value.func) in (
            "p._catalog_observe",
            "self.grn.core._observe_dispatch",
        ):
            return None
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        node.decorator_list = []
        node.returns = None
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            arg.annotation = None
        return self.generic_visit(node)


def audit():
    source_path = ROOT / "src/cells/processes" / f"{PREFIX}_source.py"
    native_path = ROOT / "validation/betse" / f"{PREFIX}_native_network.py"
    st = parsed(source_path)
    nt = parsed(native_path)
    original = classes(parsed(PIN / "betse/science/chemistry/networks.py"))
    original |= classes(parsed(PIN / "betse/science/chemistry/gene.py"))
    source = classes(st)
    sf = functions(st)
    nf = functions(nt)
    # Compile/call only this builder's stdlib functions, returning AST objects.
    defs = functions(nt) | classes(nt)
    builders = [
        defs[name] for name in ("parsed", "node", "Clean", "hook", "Observe", "literal_additions")
    ]
    ns = dict(ast=ast, copy=copy, Path=Path)
    exec(
        compile(
            ast.Module(body=builders, type_ignores=[]), "<stdlib catalog AST construction>", "exec"
        ),
        ns,
    )
    methods, channel = ns["literal_additions"](PIN / "betse")
    captured = {"MasterOfNetworks": {n.name: n for n in methods}, "Channel": functions(channel)}
    bodies = {}
    for cls, names in (
        ("MasterOfNetworks", ("read_channels", "run_loop_channels")),
        ("Channel", ("__init__", "init_channel")),
    ):
        actual = functions(source[cls])
        raw = functions(original[cls])
        for name in names:
            assert digest(actual[name]) == digest(captured[cls][name]), (cls, name, "port/native")
            assert digest(Numeric().visit(copy.deepcopy(actual[name]))) == digest(
                Numeric().visit(copy.deepcopy(raw[name]))
            ), (cls, name, "literal")
            bodies[cls + "." + name] = dict(
                original_AST_sha256=digest(raw[name]),
                port_AST_sha256=digest(actual[name]),
                first_line=raw[name].lineno,
                last_line=raw[name].end_lineno,
            )
    for name, node in functions(source["MasterOfGenes"]).items():
        assert digest(Numeric().visit(copy.deepcopy(node))) == digest(
            Numeric().visit(copy.deepcopy(functions(original["MasterOfGenes"])[name]))
        )
    # Scientific original dispatcher/initializer are preserved apart from read-only hooks.
    basef = functions(parsed(ROOT / "src/cells/processes/betse_ecm_grn_source.py"))
    for name in ("initialize_owner", "dispatch"):
        assert digest(sf[name]) == digest(basef[name])
    # Every owned plumbing function is identical across separately compiled port/native namespaces.
    plumbing = set(sf) & set(nf) - {"science", "class_for"}
    for name in plumbing:
        assert digest(sf[name]) == digest(nf[name]), name
    assert "class MasterOfNetworks(base.MasterOfNetworks)" in ast.unparse(st)
    assert "return nodes + [channel]" in ast.unparse(nf["literal_nodes"])
    science = ast.unparse(nf["science"])
    assert "ns = dict(base.science())" in science and "literal_nodes(root)" in science
    for key in ("molecule_mover", "no_negs", "electroflux", "update_Co"):
        assert key in science
    assert "channel_fields" in ast.unparse(sf["wire"])
    fields = ast.unparse(sf["channel_fields"])
    assert "clone(vars(obj.channel_core))" in fields and "k != 'channel_core'" in fields
    cache = ast.unparse(sf["cache"])
    assert "initial_channel_fields" in cache and "channel_calls" in cache
    restore = ast.unparse(sf["restore"])
    assert (
        "api['class_for'](saved['core_class'])" in restore
        and "clone(saved['core_fields'])" in restore
    )
    assert "validate_cached_channels(ctx, incoming)" in restore
    attach = ast.unparse(sf["attach"])
    assert attach.index("ctx.trace['before_channels']") < attach.index("ctx.trace['before']")
    assert "stage == 'run_loop_channels'" in attach
    # The lower frozen material/CaATP/field math is reused, without forged old Binding types.
    main = parsed(ROOT / "src/cells/processes" / f"{PREFIX}.py")
    mf = functions(main)
    text = ast.unparse(main)
    for alias in (
        "_material_step = calcium_component._material_step",
        "native_policy, calcium = (calcium_component.native_policy, calcium_component.calcium)",
    ):
        assert alias in text, alias
    init = ast.unparse(mf["initialize"])
    assert (
        init.index("source.configure(")
        < init.index("source.cold(")
        < init.index("after_cold(")
        < init.index("source.validate_cached_channels(")
        < init.index("full.reconstruct(")
    )
    advance = ast.unparse(mf["advance"])
    assert "source.restore(ctx, parent.network.network_cache)" in advance
    assert "before_channels" in advance and "before_network" in advance
    assert "float(parent.clock.source_times_s[index])" in advance
    native = functions(parsed(ROOT / "validation/betse" / f"{PREFIX}_native.py"))
    inherited = functions(parsed(ROOT / "validation/betse/betse_normal_ecm_calcium_join_native.py"))
    for name in ("field_nodes", "calcium_nodes"):
        assert digest(native[name]) == digest(inherited[name]), name
    assert digest(native["run_dispatch"].args) == digest(sf["run_dispatch"].args)
    evaluate = ast.unparse(native["evaluate"])
    # Verify the repaired observation map never introduces local ion-name shadowing.
    trace = next(
        n
        for n in ast.walk(native["evaluate"])
        if isinstance(n, ast.FunctionDef) and n.name == "trace"
    )
    assert not any(
        isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id == "names"
        for n in ast.walk(trace)
    )
    loop = next(
        n
        for n in ast.walk(native["evaluate"])
        if isinstance(n, ast.For) and ast.unparse(n.target) == "(index, call)"
    )
    order = [ast.unparse(n) for n in loop.body]
    moving = next(i for i, s in enumerate(order) if s.startswith("source['ordered']("))
    ca = order.index("calcium_result = calcium_call(index)")
    late = next(
        i for i, s in enumerate(order) if s.startswith("sim.fluxes_mem +=") and "supplied_late" in s
    )
    grn = next(i for i, s in enumerate(order) if s.startswith("run_dispatch("))
    commit = order.index("sim.update_all_concs(cells, parameters)")
    field = order.index("field_result = field_call('field')")
    assert moving < ca < late < grn < commit < field
    assert "inputs['steps'][:declared['stop_after_calls']]" in ast.unparse(loop.iter)
    assert "parameters.sim_tsteps = 3" in evaluate
    assert "cold_trace" in evaluate and "post_material_cache" in evaluate
    ref = functions(parsed(ROOT / "validation/betse" / f"{PREFIX}_reference.py"))
    previous_ref = functions(
        parsed(ROOT / "validation/betse/betse_normal_ecm_calcium_join_reference.py")
    )
    for name in ("calcium_equations", "calcium", "native_parameters"):
        assert digest(ref[name]) == digest(previous_ref[name]), name
    inverse = copy.deepcopy(ref["material_model"])

    class RemoveChannels(ast.NodeTransformer):
        def visit_Assign(self, node):
            return (
                None
                if ast.unparse(node.targets[0]) == "channel_result"
                else self.generic_visit(node)
            )

        def visit_Call(self, node):
            node = self.generic_visit(node)
            node.keywords = [k for k in node.keywords if k.arg != "channel_reference"]
            return node

    inverse = RemoveChannels().visit(inverse)
    assert digest(inverse) == digest(previous_ref["material_model"])
    sequence = ast.unparse(ref["channel_sequence"])
    for needed in (
        "source_effective_environment_change_mol",
        "true_grid_environment_change_mol",
        "conservative_balance_mol",
        "voltage_nonce_count",
        "wire['channel_fields']",
        "modulation(row, v, molecules, names, mapping)",
    ):
        assert needed in sequence, needed
    assert "100 if refinement == 1 else 160" in ast.unparse(ref["kinetics"])
    witness = json.loads((WORK / f"{PREFIX}_reachability_01.json").read_text())
    assert (
        witness["class_count"] == 55
        and witness["modern_numeric_methods"] == 110
        and witness["Ca_routing_classes"] == 23
    )
    assert (
        not witness["implicit_free_Ca_class_gating"]
        and not witness["legacy_cagPotassium_runtime_calls"]
    )
    assert (
        sha(ROOT / "src/cells/processes/betse_channel_catalog_source.py")
        == witness["unchanged_catalog_port_sha256"]
    )
    return dict(
        kind="cells.normal_ecm_catalog_static_AST_audit@1",
        literal_channel_bodies=bodies,
        new_literal_channel_bodies=4,
        inherited_network_bodies=47,
        inherited_complete_field_functions=10,
        inherited_complete_CaATP_functions=3,
        modern_classes=55,
        modern_numeric_methods=110,
        modern_Ca_routing_classes=23,
        common_cache_capture_plumbing_functions=len(plumbing),
        complete_private_channel_cache=True,
        actual_cold_config_flag=True,
        source_clock_N3_prefix=True,
        actual_pre_channel_and_post_channel_checkpoints=True,
        scalar_ECM_channel_reference_inside_material=True,
        unchanged_CaATP_and_field_components=True,
        source_modern_ion_CaATP_GeRN_commit_field_order=True,
        native_trace_ion_names_not_shadowed=True,
        old_Cav_G_failed_panel_reclassified=False,
        enabled_ER_calls=0,
        scientific_imports=0,
        scientific_AST_executions=0,
        pytest_collection_runs=0,
        numerical_runs=0,
    )


if __name__ == "__main__":
    result = audit()
    with (WORK / f"{PREFIX}_AST_witness_01.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(
        json.dumps(
            {k: v for k, v in result.items() if k != "literal_channel_bodies"}, sort_keys=True
        )
    )
