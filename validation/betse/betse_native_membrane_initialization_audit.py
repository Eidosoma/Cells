"""Static correspondence for paired owners, cache readiness and component entry."""

import ast
import hashlib
import json
from pathlib import Path

CORE = "src/cells/processes/betse_native_membrane_initialization.py"
INITIAL = "src/cells/processes/betse_normal_ecm_initialization.py"
SOURCE = "src/cells/processes/betse_ecm_grn_source.py"
FIELD = "src/cells/processes/betse_normal_ecm_field_join.py"
LAYOUT = "src/cells/processes/betse_native_membrane_layout.py"
INITIAL02 = Path("/mnt/workspaces/Cells/betse-normal-ecm-initialization-prepared-20261031-02")
INITIAL02_SHA256 = "f423016aedf458d416b51e2b56640e64f5d36716b84d77efb953d7b2be371909"
LAYOUT01 = Path("/mnt/workspaces/Cells/betse-native-membrane-layout-prepared-20261031-01")
LAYOUT01_SHA256 = "b645dc11765fca88111514496392a6b65d89cf70aec13228ef699c89d96ba451"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def literal(tree, name):
    return ast.literal_eval(
        next(
            node.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
        )
    )


def function(tree, name, cls=None):
    body = tree.body
    if cls:
        body = next(
            node.body for node in body if isinstance(node, ast.ClassDef) and node.name == cls
        )
    return next(node for node in body if isinstance(node, ast.FunctionDef) and node.name == name)


def site(path, node):
    return dict(
        source=path,
        first_line=node.lineno,
        last_line=node.end_lineno,
        ast_sha256=hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
        expression=ast.unparse(node),
    )


def calls(node, name):
    return [
        child
        for child in ast.walk(node)
        if isinstance(child, ast.Call) and ast.unparse(child.func) == name
    ]


def audit(native, project):
    native, project = Path(native), Path(project)
    assert sha(INITIAL02 / "manifest.json") == INITIAL02_SHA256
    assert sha(LAYOUT01 / "manifest.json") == LAYOUT01_SHA256
    parent = json.loads((INITIAL02 / "manifest.json").read_text())["file_sha256"]
    layout_parent = json.loads((LAYOUT01 / "manifest.json").read_text())["file_sha256"]
    code = ast.parse((project / CORE).read_bytes())
    pins = dict(literal(code, "DEPENDENCY_PINS"))
    for name, expected in pins.items():
        rel = "src/cells/processes/" + name + ".py"
        assert sha(project / rel) == expected, rel
        manifest = layout_parent if rel == LAYOUT else parent
        assert manifest["source/" + rel] == expected, rel
    initial, source, field = (
        ast.parse((project / path).read_bytes()) for path in (INITIAL, SOURCE, FIELD)
    )
    original = function(initial, "handoff")
    original_calls = {
        name: site(INITIAL, calls(original, name)[0])
        for name in ("_check_owners", "source.restore", "source.cache", "field.reconstruct")
    }
    assert len(calls(original, "field.reconstruct")) == 1 and not calls(original, "source.cold")
    project_method = function(code, "_project")
    assert len(calls(project_method, "layout.midpoint_normal_view")) == 1
    assert len(calls(project_method, "np.frombuffer")) == 1
    assert not calls(project_method, "layout.normal_tangent_view")
    entry = function(code, "bootstrap_component")
    assert len(calls(entry, "initial.handoff")) == 1
    assert not any(
        isinstance(node, ast.Call)
        and ast.unparse(node.func).endswith(
            (".cold", ".init_core", ".init_dynamics", ".run_sim_core", ".step")
        )
        for node in ast.walk(code)
    )
    held_shape = [
        node
        for node in ast.walk(function(initial, "_check_owners"))
        if isinstance(node, ast.Compare) and ast.unparse(node) == "vectors.shape != (m, 4)"
    ]
    assert len(held_shape) == 1
    native_paths = ("betse/science/cells.py", "betse/science/sim.py", "betse/science/simrunner.py")
    native_pins = {}
    trees = {}
    for path in native_paths:
        native_pins[path] = parent["native/" + path]
        assert sha(native / path) == native_pins[path], path
        trees[path] = ast.parse((native / path).read_bytes())
    sim = trees["betse/science/sim.py"]
    run = function(sim, "run_sim_core", "Simulator")
    ordered = [
        calls(run, name)[0]
        for name in ("self.init_dynamics", "self.clear_storage", "self.update_V")
    ]
    assert [node.lineno for node in ordered] == sorted(node.lineno for node in ordered)
    egj = []
    for node in next(
        node.body
        for node in sim.body
        if isinstance(node, ast.ClassDef) and node.name == "Simulator"
    ):
        if not isinstance(node, ast.FunctionDef):
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Assign) and any(
                ast.unparse(target) == "self.Egj" for target in child.targets
            ):
                egj.append(dict(method=node.name, **site("betse/science/sim.py", child)))
    assert len(egj) == 1 and egj[0]["method"] == "update_gj"
    gate_function = function(code, "require_ordinary_loop")
    assert isinstance(gate_function.body[0], ast.Raise)
    return dict(
        kind="cells.betse_native_membrane_initialization_static_correspondence@1",
        initial02_manifest_sha256=INITIAL02_SHA256,
        layout01_manifest_sha256=LAYOUT01_SHA256,
        runtime_source_sha256=pins,
        native_source_sha256=native_pins,
        explicit_projection=site(CORE, project_method),
        unchanged_four_column_gate=site(INITIAL, held_shape[0]),
        old_component_calls=original_calls,
        source_cache={name: site(SOURCE, function(source, name)) for name in ("cache", "restore")},
        old_owner_admission=site(INITIAL, function(initial, "_check_owners")),
        old_native_capture=site(INITIAL, function(initial, "capture_native")),
        old_single_field_reconstruct=site(FIELD, function(field, "reconstruct")),
        new_pair_shared_store_check=site(CORE, function(code, "_shared_stores")),
        new_readiness_and_entry={
            name: site(CORE, function(code, name))
            for name in ("prepare", "_validate_request", "bootstrap_component")
        },
        native_load=site(
            "betse/science/simrunner.py",
            function(trees["betse/science/simrunner.py"], "sim", "SimRunner"),
        ),
        native_prebootstrap_calls=[site("betse/science/sim.py", node) for node in ordered],
        native_Egj_writer=egj,
        readiness_scope=dict(
            common="unchanged owner/operator/state/publication/coefficient and cache epoch checks",
            serializer="complete source restore/cache roundtrip remains inside unchanged handoff",
            calcium="persisted rate, pool, pump and clock admission remains before hydration",
            missing_stores="retained and refused; optional inventory does not become a default",
            Egj="observe actual loaded epoch; update_gj writes it; no zero filling",
            physical_geometry="supplied operators do not establish native mesh origin",
            tangent="retained unused columns4/5; no tangent geometry qualification",
            source_history="pinned instances do not prove seed/init/load execution",
        ),
        new_ordinary_loop_gate=site(CORE, gate_function),
        scope=dict(
            science_imports=False,
            candidate_evaluation=False,
            fixture_construction=False,
            test_collection=False,
            jobs=False,
            PROGRESS_edited=False,
            held_packets_changed=False,
            physics_or_numeric_budgets_changed=False,
            native_seed_init_chain_closed=False,
            ordinary_ECM_loop_ready=False,
        ),
    )
