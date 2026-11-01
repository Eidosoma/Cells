"""Metadata/software controls; no original numerical body is executed."""

import ast
import copy
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from validation.betse import native_single_cell_prefix_comparison as runner
from validation.betse import native_single_cell_prefix_native as native

ROOT = Path("/mnt/workspaces/Cells/betse-v1.5.0")


@pytest.fixture(autouse=True)
def no_numerical_entry(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Original numerical execution is forbidden in software controls")

    monkeypatch.setattr(native, "evaluate", forbidden)


def original_class(relative, name):
    tree = ast.parse((ROOT / relative).read_text())
    return next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)


def node_dump(value):
    return ast.dump(value, include_attributes=False)


def test_literal_closure_and_only_declared_world_suffix_removed():
    groups, sites = native.source_nodes(ROOT)
    assert len(native.NATIVE_PINS) == 20
    seen = {
        file: nodes
        for file, nodes in groups
        if file in ("betse/science/math/mesh.py", "betse/science/cells.py")
    }
    assert node_dump(seen["betse/science/math/mesh.py"][0]) == node_dump(
        original_class("betse/science/math/mesh.py", "DECMesh")
    )
    original = original_class("betse/science/cells.py", "Cells")
    methods = {n.name: n for n in original.body if isinstance(n, ast.FunctionDef)}
    copied = {n.name: n for n in seen["betse/science/cells.py"][0].body}
    assert set(copied) == {
        "__init__",
        "make_world",
        "_make_cell_lattice",
        "make_voronoi",
        "cell_index",
        *native.METHODS,
    }
    for name, method in copied.items():
        if name != "make_world":
            assert node_dump(method) == node_dump(methods[name])
    prefix = copied["make_world"]
    assert node_dump(prefix.body[-1]) == node_dump(ast.parse("self.near_neigh(phase.p)").body[0])
    assert [node_dump(n) for n in prefix.body] == [
        node_dump(n) for n in methods["make_world"].body[: len(prefix.body)]
    ]
    assert node_dump(prefix.args) == node_dump(methods["make_world"].args)
    assert "self.makeECM" not in ast.unparse(prefix)
    assert len(sites) > 30
    # Compile without exec: validates AST structure and postponed annotations,
    # but runs no class body, helper, constructor or equation.
    for file, nodes in groups:
        compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), file, "exec")


def test_original_image_inheritance_and_parameter_order_retained():
    groups, _ = native.source_nodes(ROOT)
    image = next(
        nodes for file, nodes in groups if file == "betse/science/tissue/picker/tispickimage.py"
    )
    for cls in image:
        assert node_dump(cls) == node_dump(
            original_class("betse/science/tissue/picker/tispickimage.py", cls.name)
        )
    stores = next(nodes[0] for file, nodes in groups if file == "betse/science/parameters.py")
    assert [n.lineno for n in stores.body] == list(native.STORE_LINES)
    original = original_class("betse/science/parameters.py", "Parameters")
    source = {n.lineno: n for n in ast.walk(original) if isinstance(n, ast.Assign)}
    assert [node_dump(n) for n in stores.body] == [
        node_dump(source[line]) for line in native.STORE_LINES
    ]


def test_native_pin_change_refuses_before_compilation(monkeypatch):
    pins = dict(native.NATIVE_PINS)
    pins["betse/science/cells.py"] = "0" * 64
    monkeypatch.setattr(native, "NATIVE_PINS", pins)
    with pytest.raises(ValueError, match="Changed original source"):
        native.source_nodes(ROOT)


@pytest.fixture
def declared(tmp_path):
    image = tmp_path / "source.pgm"
    image.write_bytes(b"P2\n1 1\n255\n0\n")
    raw = dict(
        seed_recipe=dict(
            kind="cells.betse_lattice_seed_recipe@1",
            provenance="Synthetic metadata control only",
            lattice_type="SQUARE",
            world_len_m=4e-5,
            cell_radius_m=5e-6,
            lattice_disorder=0.35,
        ),
        seed_stream_before=["MT19937", [0] * 624, 624, 0, 0.0],
        controls=dict(
            kind="cells.betse_make_voronoi_controls@1",
            single_cell=True,
            svg_override=False,
            alpha_shape=0.4,
            use_centroids=True,
            refine_mesh=False,
            maximum_voronoi_steps=8,
            voronoi_convergence=7.5,
        ),
        image_recipe=dict(
            kind="cells.betse_image_mask_source@1",
            filename=image.name,
            conf_dirname=str(tmp_path),
            image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
        ),
    )
    return raw, {"world options": {"cell height": 1e-5, "cell spacing": 2.6e-8}}


def test_input_float_bits_and_exact_image_metadata_without_decode(declared):
    raw, conf = declared
    raw["seed_recipe"]["lattice_disorder"] = {"float64_bits": "666666666666d63f"}
    observed, image = native.inputs(raw, conf)
    assert observed["seed_recipe"]["lattice_disorder"] == 0.35
    assert image.name == "source.pgm"
    assert native.scalars({"float64_bits": "0000000000000080"}).hex() == "-0x0.0p+0"


@pytest.mark.parametrize(
    "change",
    [
        "multi",
        "svg",
        "short_mt",
        "bool_word",
        "bad_position",
        "nan_cache",
        "wrong_image",
        "bool_radius",
        "oversize",
        "extra_conf",
    ],
)
def test_input_prerequisites_refuse_without_source(change, declared):
    raw, conf = copy.deepcopy(declared)
    if change == "multi":
        raw["controls"]["single_cell"] = False
    elif change == "svg":
        raw["controls"]["svg_override"] = True
    elif change == "short_mt":
        raw["seed_stream_before"][1].pop()
    elif change == "bool_word":
        raw["seed_stream_before"][1][0] = True
    elif change == "bad_position":
        raw["seed_stream_before"][2] = 625
    elif change == "nan_cache":
        raw["seed_stream_before"][4] = float("nan")
    elif change == "wrong_image":
        raw["image_recipe"]["image_sha256"] = "0" * 64
    elif change == "bool_radius":
        raw["seed_recipe"]["cell_radius_m"] = True
    elif change == "oversize":
        raw["seed_recipe"]["world_len_m"] = 1.0
    else:
        conf["other"] = True
    with pytest.raises(ValueError):
        native.inputs(raw, conf)


@pytest.fixture
def grant(tmp_path, monkeypatch):
    prepared = tmp_path / "prepared"
    prepared.mkdir()
    review = tmp_path / "review.json"
    review.write_text('{"synthetic_only":true}')
    plan = dict(
        kind=runner.KINDS[0],
        limits=runner.prior.LIMITS,
        stages=list(runner.METHODS),
        native_executions=1,
        cells_replays=0,
        cpu=3,
        automatic_retry=False,
        independent_physical_oracle=False,
        physical_geometry_admitted=False,
        full_package_or_phase_admitted=False,
        ordinary_checkpoint_admitted=False,
        case=runner.prior.CASES[0],
        snapshot_sha256="a" * 64,
        external_inputs=[],
    )
    release = dict(
        kind=runner.KINDS[1],
        case=plan["case"],
        snapshot_sha256=plan["snapshot_sha256"],
        allow_one_native_reference=True,
        physical_geometry_admitted=False,
        source_review=runner.prior.pin(review),
    )
    calls = []
    monkeypatch.setattr(runner.prior, "output_path", lambda path: Path(path))
    monkeypatch.setattr(runner.source_snapshot, "verify", lambda *a, **kw: calls.append((a, kw)))
    monkeypatch.setattr(runner.os, "sched_getaffinity", lambda pid: {3})

    def write():
        (prepared / "plan.json").write_text(json.dumps(plan))
        release["plan_sha256"] = native.digest(prepared / "plan.json")
        filename = tmp_path / "release.json"
        filename.write_text(json.dumps(release))
        return prepared, release["plan_sha256"], filename

    return plan, release, calls, write


def test_real_release_predicates_accept_exact_synthetic_plan(grant):
    plan, _, calls, write = grant
    assert runner.verify(*write()) == plan
    assert len(calls) == 1


@pytest.mark.parametrize(
    "change",
    [
        "plan_bytes",
        "kind",
        "native_count",
        "boolean_count",
        "replays",
        "stages",
        "resource",
        "physical",
        "case",
        "grant",
        "review",
        "cpu",
    ],
)
def test_release_predicates_refuse_before_numerical_entry(change, grant):
    plan, release, calls, write = grant
    if change == "kind":
        plan["kind"] = "unknown"
    elif change == "native_count":
        plan["native_executions"] = 2
    elif change == "boolean_count":
        plan["native_executions"] = True
    elif change == "replays":
        plan["cells_replays"] = 1
    elif change == "stages":
        plan["stages"] = ["near_neigh"]
    elif change == "resource":
        plan["limits"] = {"timeout": 999999}
    elif change == "physical":
        release["physical_geometry_admitted"] = True
    elif change == "case":
        release["case"] = "wrong"
    elif change == "grant":
        release["allow_one_native_reference"] = False
    elif change == "review":
        release["source_review"]["sha256"] = "0" * 64
    elif change == "cpu":
        plan["cpu"] = 2
    args = write()
    if change == "plan_bytes":
        (args[0] / "plan.json").write_text("{}")
    with pytest.raises(ValueError):
        runner.verify(*args)


@pytest.mark.parametrize("name", ["nx", "cell_radius", "cell_lattice_type", "cell_height"])
def test_controls_cannot_overwrite_original_parameter_stores(name, declared):
    raw, conf = declared
    raw["controls"][name] = 123
    with pytest.raises(ValueError, match="control fields"):
        native.inputs(raw, conf)


@pytest.mark.parametrize("source_failed", [False, True])
@pytest.mark.parametrize("probe", ["image_unchanged", "stream_after", "warnings"])
def test_secondary_finalization_failures_preserve_primary_and_partial(source_failed, probe):
    primary = {"original": "source cause and context"} if source_failed else None
    partial = [{"original_raw_trial": True}]
    record = dict(
        source_body_completed=not source_failed,
        source_error=primary,
        capture_error=None,
        failed_stage="source" if source_failed else None,
        partial_captures=partial,
    )

    def failed():
        raise OSError("synthetic metadata capture failure")

    probes = dict(
        image_unchanged=lambda: True,
        global_random_stream_unchanged=lambda: True,
        stream_after=lambda: {"state": "synthetic"},
        warnings=lambda: [],
    )
    probes[probe] = failed
    result = native.finalize(record, probes, runner.prior.exception_record)
    assert result["status"] == "source_failed"
    assert result["source_error"] is primary and result["partial_captures"] is partial
    assert result["secondary_capture_errors"][0]["stage"] == probe
    assert result["capture_error"] is result["secondary_capture_errors"][0]["error"]
    assert result["failed_stage"] == ("source" if source_failed else "final_metadata")


@pytest.mark.parametrize("where", ["process_directory", "inputs_write"])
def test_owned_output_startup_failure_keeps_terminal_receipt(where, tmp_path, monkeypatch):
    output = tmp_path / "output"
    plan = dict(
        input_capture={"path": str(tmp_path / "old-input")},
        owned_trial={"path": str(tmp_path / "old-trial")},
        case="synthetic",
    )
    monkeypatch.setattr(runner, "verify", lambda *a: plan)
    monkeypatch.setattr(runner.prior, "execution_output", lambda path, *a: Path(path))
    monkeypatch.setattr(runner.prior, "pin", lambda path: {"path": str(path), "sha256": "0" * 64})
    mkdir, write = Path.mkdir, runner.prior.write

    def fail_directory(path, *args, **kwargs):
        if path.name == "process":
            raise OSError("synthetic startup directory failure")
        return mkdir(path, *args, **kwargs)

    def fail_write(path, value):
        if path.name == "inputs.json":
            raise OSError("synthetic startup write failure")
        return write(path, value)

    if where == "process_directory":
        monkeypatch.setattr(Path, "mkdir", fail_directory)
    else:
        monkeypatch.setattr(runner.prior, "write", fail_write)
    assert runner.launch(tmp_path / "prepared", "0" * 64, tmp_path / "release", output) == 1
    result = json.loads((output / "failure.json").read_text())
    assert result["process"] is None and result["worker_result"] is None
    assert result["status"] == "failed" and result["error"]


def test_reference_modules_have_no_model_imports_or_native_package_imports():
    for module in (native, runner):
        tree = ast.parse(Path(module.__file__).read_text())
        imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        imports += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        assert not any(
            name and name.split(".")[0] in ("cells", "betse", "jax", "jaxlib") for name in imports
        )
    assert not any(name == "cells" or name.startswith("cells.") for name in sys.modules)


def test_make_world_source_order_places_mask_before_constructor():
    groups, _ = native.source_nodes(ROOT)
    cls = next(nodes[0] for file, nodes in groups if file == "betse/science/cells.py")
    method = next(n for n in cls.body if n.name == "make_voronoi")
    mask_call = next(
        n
        for n in ast.walk(method)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "get_image_mask"
    )
    mesh_call = next(
        n
        for n in ast.walk(method)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "DECMesh"
    )
    assert mask_call.lineno < mesh_call.lineno
    kwargs = {v.arg: ast.unparse(v.value) for v in mesh_call.keywords}
    assert kwargs["image_mask"] == "None" and kwargs["make_all_operators"] == "False"
    assert all(
        k not in kwargs for k in ("use_centroids", "close_thresh", "merge_thresh", "alpha_shape")
    )


def test_ecm_endpoint_keeps_original_geometry_and_exact_native_grid_methods():
    groups, sites = native.source_nodes(ROOT, stop_after="makeECM")
    legacy, _ = native.source_nodes(ROOT)
    assert native.methods_for() == native.METHODS
    assert native.methods_for("makeECM") == (*native.METHODS, "makeECM")
    assert native.pins_for() == native.NATIVE_PINS and len(native.pins_for()) == 20
    assert native.metadata_imports_for() == ()
    assert native.pins_for("makeECM") == native.NATIVE_PINS | native.ECM_PINS
    cells = next(nodes[0] for file, nodes in groups if file == "betse/science/cells.py")
    original = original_class("betse/science/cells.py", "Cells")
    selected = {n.name: n for n in cells.body}
    originals = {n.name: n for n in original.body if isinstance(n, ast.FunctionDef)}
    for name, node in selected.items():
        if name != "make_world":
            assert node_dump(node) == node_dump(originals[name])
    prefix = selected["make_world"]
    assert [node_dump(n) for n in prefix.body] == [
        node_dump(n) for n in originals["make_world"].body[: len(prefix.body)]
    ]
    assert node_dump(prefix.body[-1]) == node_dump(ast.parse("self.makeECM(phase.p)").body[0])
    assert "self.environment" not in ast.unparse(prefix)
    assert "makeLaplacian" not in ast.unparse(prefix)
    grid = next(nodes[0] for file, nodes in groups if file == "betse/science/math/finitediff.py")
    original_grid = original_class("betse/science/math/finitediff.py", "FiniteDiffSolver")
    assert [node_dump(b) for b in grid.bases] == [node_dump(b) for b in original_grid.bases]
    assert [n.name for n in grid.body] == ["__init__", "cell_grid"]
    for node in grid.body:
        assert node_dump(node) == node_dump(
            next(n for n in original_grid.body if getattr(n, "name", None) == node.name)
        )
    # Every pre-existing group except the intentionally extended Cells class is exact.
    for file, nodes in legacy:
        if file != "betse/science/cells.py":
            assert any(
                file == f and [node_dump(n) for n in nodes] == [node_dump(n) for n in ns]
                for f, ns in groups
            )
    assert "betse/science/math/finitediff.py:FiniteDiffSolver" in sites
    for file, nodes in groups:
        compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), file, "exec")


@pytest.mark.parametrize("stop", [None, True, "environment", "near_neigh ", "makeLaplacian"])
def test_ecm_endpoint_policy_is_closed(stop, declared):
    for fn in (native.methods_for, native.pins_for, native.metadata_imports_for):
        with pytest.raises(ValueError, match="endpoint"):
            fn(stop)
    with pytest.raises(ValueError, match="endpoint"):
        native.source_nodes(ROOT, stop_after=stop)
    with pytest.raises(ValueError, match="endpoint"):
        native.inputs(*declared, stop_after=stop)


def test_ecm_input_requires_explicit_retained_grid_configuration(declared):
    raw, conf = declared
    conf["general options"] = {"comp grid size": 25}
    values, _ = native.inputs(raw, conf, stop_after="makeECM")
    assert values == raw and conf["general options"] == {"comp grid size": 25}
    with pytest.raises(ValueError, match="configuration"):
        native.inputs(raw, conf)


@pytest.mark.parametrize(
    "general",
    [
        None,
        {},
        {"comp grid size": True},
        {"comp grid size": 25.0},
        {"comp grid size": 24},
        {"comp grid size": 25, "other": 0},
    ],
)
def test_ecm_configuration_does_not_coerce_or_invent_descriptor_values(general, declared):
    raw, conf = declared
    conf["general options"] = general
    with pytest.raises(ValueError, match="grid size"):
        native.inputs(raw, conf, stop_after="makeECM")


@pytest.mark.parametrize(
    "path", ["betse/science/math/finitediff.py", "betse/lib/yaml/yamlalias.py", "betse/__init__.py"]
)
def test_ecm_new_source_pin_drift_refuses_before_compilation(path, monkeypatch):
    monkeypatch.setattr(native, "ECM_PINS", native.ECM_PINS | {path: "0" * 64})
    with pytest.raises(ValueError, match="Changed original source"):
        native.source_nodes(ROOT, stop_after="makeECM")


def test_ecm_descriptor_assignment_is_original_and_lazy_before_parameter_birth():
    groups, _ = native.source_nodes(ROOT, stop_after="makeECM")
    factory = next(
        n for file, nodes in groups for n in nodes if getattr(n, "name", None) == "parameter_type"
    )
    original = original_class("betse/science/parameters.py", "Parameters")
    store = next(
        n
        for n in original.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "grid_size" for t in n.targets)
    )
    assert node_dump(factory.body[0]) == node_dump(store)
    calls = []

    class SyntheticDescriptor:
        def __get__(self, owner, cls):
            calls.append(("read", owner))
            return owner._conf["general options"]["comp grid size"]

    descriptor = SyntheticDescriptor()

    def synthetic_factory(expression, dtype):
        calls.append(("factory", expression, dtype))
        return descriptor

    namespace = {"SimpleNamespace": SimpleNamespace}
    # Only an assembly wrapper plus a synthetic descriptor executes. No original
    # factory, grid body, geometry body, image decoder or numeric package enters.
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[factory], type_ignores=[])),
            "synthetic-assembly",
            "exec",
        ),
        namespace,
    )
    first = namespace["parameter_type"](synthetic_factory)
    second = namespace["parameter_type"](synthetic_factory)
    assert first is not second
    assert vars(first)["grid_size"] is descriptor
    assert calls == [("factory", "['general options']['comp grid size']", int)] * 2
    parameter = first(_conf={"general options": {"comp grid size": 25}})
    assert parameter.grid_size == 25
    assert calls[-1] == ("read", parameter)


@pytest.mark.parametrize("failure", [None, "import", "factory", "changed_producer"])
def test_ecm_lazy_import_order_and_path_restoration_on_failure(failure, monkeypatch):
    calls, before_path = [], list(sys.path)
    producer = {"synthetic": {"path": "not an actual module", "sha256": "a" * 64}}
    checks = []

    def records(root):
        checks.append(root)
        return {"changed": {}} if failure == "changed_producer" and len(checks) == 3 else producer

    def load(name):
        assert sys.path[0] == str(ROOT)
        calls.append(name)
        if failure == "import":
            raise ImportError("synthetic missing dependency")
        return SimpleNamespace(yaml_alias="synthetic callable token")

    def factory(value):
        assert value == "synthetic callable token"
        calls.append("factory")
        if failure == "factory":
            raise RuntimeError("synthetic factory error")
        return type("SyntheticParameters", (), {})

    monkeypatch.setattr(native, "metadata_records", records)
    monkeypatch.setattr(native.importlib, "import_module", load)
    if failure is None:
        runtime, result = native.grid_parameter_type(factory, ROOT)
        assert runtime.__name__ == "SyntheticParameters" and result == producer
    else:
        with pytest.raises((ImportError, RuntimeError, ValueError)):
            native.grid_parameter_type(factory, ROOT)
    assert sys.path == before_path
    if failure != "import":
        assert calls == [
            "betse.lib.yaml.yamlalias",
            "betse.util.type.descriptor.expralias",
            "betse.util.type.cls.classes",
            "factory",
        ]


@pytest.mark.parametrize("change", [None, "origin", "path", "science"])
def test_ecm_actual_metadata_module_paths_are_pinned(change, monkeypatch, tmp_path):
    name = "betse.lib.yaml.yamlalias" if change != "science" else "betse.science.cells"
    path = ROOT / "betse/lib/yaml/yamlalias.py"
    module = SimpleNamespace(__file__=str(path), __spec__=SimpleNamespace(origin=str(path)))
    if change == "path":
        module.__file__ = str(tmp_path / "other.py")
    elif change == "origin":
        module.__spec__.origin = str(tmp_path / "other.py")
    monkeypatch.setitem(sys.modules, name, module)
    if change is None:
        assert (
            native.metadata_records(ROOT)[name]["sha256"]
            == native.ECM_PINS["betse/lib/yaml/yamlalias.py"]
        )
    else:
        with pytest.raises((ValueError, ImportError)):
            native.metadata_records(ROOT)


def test_ecm_import_allowlist_includes_only_pinned_metadata_packages():
    names = native.metadata_imports_for("makeECM")
    assert len(names) == len(set(names)) == 13
    assert {
        "betse",
        "betse.metadata",
        "betse.exceptions",
        "betse.util.type.types",
        "betse.lib.yaml.yamlalias",
        "betse.util.type.descriptor.expralias",
        "betse.util.type.cls.classes",
    } <= set(names)
    assert not any(name.startswith("betse.science") for name in names)
    pins = native.pins_for("makeECM")
    for name in names:
        stem = name.replace(".", "/")
        assert stem + ".py" in pins or stem + "/__init__.py" in pins
    package = ast.parse((ROOT / "betse/__init__.py").read_bytes())
    assert any(isinstance(n, ast.ImportFrom) and n.module == "beartype.claw" for n in package.body)
    assert any(
        isinstance(n, ast.Expr)
        and isinstance(n.value, ast.Call)
        and isinstance(n.value.func, ast.Name)
        and n.value.func.id == "beartype_this_package"
        for n in package.body
    )


def test_ecm_descriptor_precedes_parameter_birth_stores_and_one_original_world_call():
    tree = ast.parse(Path(native.__file__).read_text())
    evaluate = next(n for n in tree.body if getattr(n, "name", None) == "evaluate")
    calls = [n for n in ast.walk(evaluate) if isinstance(n, ast.Call)]
    descriptor = next(
        n for n in calls if isinstance(n.func, ast.Name) and n.func.id == "grid_parameter_type"
    )
    birth = next(n for n in calls if isinstance(n.func, ast.Name) and n.func.id == "runtime")
    stores = next(
        n
        for n in calls
        if isinstance(n.func, ast.Subscript)
        and isinstance(n.func.slice, ast.Constant)
        and n.func.slice.value == "store_parameters"
    )
    caller = next(
        n
        for n in calls
        if isinstance(n.func, ast.Subscript)
        and isinstance(n.func.slice, ast.Constant)
        and n.func.slice.value == "Cells"
    )
    worlds = [n for n in calls if isinstance(n.func, ast.Attribute) and n.func.attr == "make_world"]
    assert len(worlds) == 1
    assert descriptor.lineno < birth.lineno < stores.lineno < caller.lineno < worlds[0].lineno


def test_ecm_snapshot_separates_grid_owner_and_preserves_geometry_schema():
    grid = SimpleNamespace(cents_X=[1, 2])
    mesh = SimpleNamespace(vertices=[3, 4])
    caller = SimpleNamespace(mesh=mesh, grid_obj=grid, X=grid.cents_X)
    parameter = SimpleNamespace(
        _conf={"general options": {"comp grid size": 25}}, hidden_control="external"
    )
    geometry = native.snapshot_state(caller, parameter, ("_conf",))
    assert set(geometry) == {"caller", "mesh", "parameters"}
    ecm = native.snapshot_state(caller, parameter, ("_conf",), ecm=True, grid=grid)
    assert set(ecm) == {"caller", "mesh", "parameters", "grid"}
    assert ecm["caller"] == {"X": [1, 2]} and ecm["grid"] == {"cents_X": [1, 2]}
    assert ecm["mesh"] == geometry["mesh"] and ecm["parameters"] == geometry["parameters"]
    assert native.snapshot_state(caller, parameter, ("_conf",), ecm=True)["grid"] is None


@pytest.mark.parametrize("fails", [False, True])
def test_ecm_observation_wrapper_keeps_geometry_handoff_and_raw_endpoint_separate(fails):
    tree = ast.parse(Path(native.__file__).read_text())
    evaluate = next(n for n in tree.body if getattr(n, "name", None) == "evaluate")
    observed = next(
        n for n in ast.walk(evaluate) if isinstance(n, ast.FunctionDef) and n.name == "observed"
    )
    outer = ast.parse(
        "def make_observer(name, original, state, stream, save_stage, "
        "save_ecm, geometry_aliases, ecm):\n"
        "    aliases = None\n"
        "    pass\n"
        "    return observed\n"
    ).body[0]
    outer.body[1] = copy.deepcopy(observed)
    namespace = {"METHODS": native.METHODS}
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[outer], type_ignores=[])),
            "synthetic-observer",
            "exec",
        ),
        namespace,
    )
    state, history, ecm = {"counter": 0}, [], {}

    def stream():
        return {"synthetic_counter": state["counter"]}

    def action(self):
        state["counter"] += 1

    def observe(name, operation):
        return namespace["make_observer"](
            name,
            operation,
            state,
            stream,
            lambda stage: history.append((stage, state["counter"])),
            lambda key: ecm.update({key: {"synthetic_counter": state["counter"]}}),
            lambda: {"synthetic_alias": True},
            ecm,
        )(None)

    observe("cellVerts", action)
    observe("near_neigh", action)
    assert history == [("before", 0), ("cellVerts", 1), ("near_neigh", 2)]
    handoff = state["after_geometry"]

    def final_action(self):
        action(self)
        if fails:
            raise RuntimeError("synthetic original ECM failure")

    if fails:
        with pytest.raises(RuntimeError, match="original ECM"):
            observe("makeECM", final_action)
        assert "cache" not in ecm and "stream_after" not in ecm
    else:
        observe("makeECM", final_action)
        assert ecm["cache"] == ecm["stream_after"] == {"synthetic_counter": 3}
    assert state["after_geometry"] is handoff
    assert handoff == ecm["before"] == ecm["stream_before"] == {"synthetic_counter": 2}
    assert history[-1] == ("near_neigh", 2)


def test_environment_literal_prefix_and_inline_assignment_are_original():
    groups, sites = native.source_nodes(ROOT, stop_after="make_maskM")
    cells = next(nodes[0] for file, nodes in groups if file == "betse/science/cells.py")
    originals = {
        n.name: n
        for n in original_class("betse/science/cells.py", "Cells").body
        if isinstance(n, ast.FunctionDef)
    }
    methods = {n.name: n for n in cells.body}
    assert native.ENVIRONMENT_STAGES == ("environment", "assign_grid_len", "make_maskM")
    assert native.methods_for("make_maskM") == (
        *native.METHODS,
        "makeECM",
        "environment",
        "make_maskM",
    )
    assert "assign_grid_len" not in methods
    for name in ("environment", "make_maskM"):
        assert node_dump(methods[name]) == node_dump(originals[name])
    world = methods["make_world"]
    assert [node_dump(n) for n in world.body] == [
        node_dump(n) for n in originals["make_world"].body[: len(world.body)]
    ]
    assert [node_dump(n) for n in world.body[-3:]] == [
        node_dump(n)
        for n in ast.parse(
            "self.environment(phase.p)\nself.grid_len = len(self.xypts)\nself.make_maskM(phase.p)"
        ).body
    ]
    assignment = world.body[-2]
    assert sites["betse/science/cells.py:make_world.grid_len"] == {
        "first_line": 494,
        "last_line": 494,
        "ast_sha256": hashlib.sha256(node_dump(assignment).encode()).hexdigest(),
    }
    assert "makeLaplacian" not in ast.unparse(world)
    # Retain the literal native yv xmin/xmax expression and scalar overwrites.
    assert "yv = np.linspace(self.xmin, self.xmax, p.plot_grid_size)" in ast.unparse(
        methods["make_maskM"]
    )
    for field in ("ecm_sa", "ecm_vol"):
        assignments = [
            n
            for n in methods["environment"].body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Attribute) and t.attr == field for t in n.targets)
        ]
        assert len(assignments) == 1 and not isinstance(assignments[0].value, ast.Call)
    for file, nodes in groups:
        compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), file, "exec")


def test_environment_store13_keeps_other_endpoints_at12_and_descriptor_before_birth():
    original = original_class("betse/science/parameters.py", "Parameters")
    stores = {n.lineno: n for n in ast.walk(original) if isinstance(n, ast.Assign)}
    factories = []
    for stop in ("near_neigh", "makeECM", "make_maskM"):
        groups, _ = native.source_nodes(ROOT, stop_after=stop)
        selected = next(
            n
            for _, nodes in groups
            for n in nodes
            if getattr(n, "name", None) == "store_parameters"
        )
        lines = (521, *native.STORE_LINES) if stop == "make_maskM" else native.STORE_LINES
        assert [node_dump(n) for n in selected.body] == [node_dump(stores[line]) for line in lines]
        if stop != "near_neigh":
            factories.append(
                next(
                    n
                    for _, nodes in groups
                    for n in nodes
                    if getattr(n, "name", None) == "parameter_type"
                )
            )
    assert node_dump(stores[521]) == node_dump(ast.parse("self.plot_grid_size = 50").body[0])
    assert node_dump(factories[0]) == node_dump(factories[1])


def test_environment_input_and_import_closure_share_only_existing_declared_helpers(declared):
    raw, conf = declared
    conf["general options"] = {"comp grid size": 25}
    assert native.inputs(raw, conf, stop_after="make_maskM") == native.inputs(
        raw, conf, stop_after="makeECM"
    )
    assert native.pins_for("make_maskM") == native.pins_for("makeECM")
    assert native.metadata_imports_for("make_maskM") == native.metadata_imports_for("makeECM")
    tree = ast.parse(Path(native.__file__).read_text())
    evaluate = next(n for n in tree.body if getattr(n, "name", None) == "evaluate")
    optional = next(
        n
        for n in evaluate.body
        if isinstance(n, ast.If)
        and ast.unparse(n.test) == "stop_after in ('make_maskM', 'lapENV_P_inv')"
        and any(isinstance(a, ast.ImportFrom) for a in n.body)
    )
    assert [(n.module, [a.name for a in n.names]) for n in optional.body] == [
        ("scipy.interpolate", ["griddata"]),
        ("scipy.ndimage", ["gaussian_filter"]),
    ]
    assert "copy=copy" in ast.unparse(evaluate)


def test_environment_snapshot_has_exact_owner_order_and_raw_tree_fields():
    values = dict(
        data=[1, 2], indices=[0, 1], mins=[1], maxes=[2], n=2, m=1, leafsize=16, boxsize=None
    )

    class SyntheticTree:
        @property
        def tree(self):
            raise AssertionError("Lazy native tree node view must not be read")

    tree = SyntheticTree()
    vars(tree).update(values)
    grid = SimpleNamespace(cents_X=[3, 4])
    caller = SimpleNamespace(
        mesh=SimpleNamespace(vertices=[5]), grid_obj=grid, points_tree=tree, ecm_sa=3.0, ecm_vol=4.0
    )
    parameter = SimpleNamespace(
        plot_grid_size=50, _conf={"general options": {"comp grid size": 25}}
    )
    observed = native.environment_snapshot(caller, parameter, tuple(vars(parameter)), grid, [tree])
    assert tuple(observed) == ("caller", "grid", "mesh", "parameters", "trees")
    assert observed["caller"] == {"ecm_sa": 3.0, "ecm_vol": 4.0}
    assert observed["grid"] == vars(grid) and observed["mesh"] == vars(caller.mesh)
    assert observed["parameters"] == vars(parameter)
    assert observed["trees"] == [values]
    assert tuple(observed["trees"][0]) == native.TREE_FIELDS
    assert observed["trees"][0]["data"] is tree.data
    assert caller.points_tree is tree and caller.grid_obj is grid


def test_environment_tree_field_unavailability_is_explicit_without_hydration():
    partial = SimpleNamespace(data=[7])
    observed = native.tree_state(partial)
    assert observed["data"] is partial.data
    for field in native.TREE_FIELDS[1:]:
        assert observed[field] == ("unavailable", field)
    assert vars(partial) == {"data": [7]}


def test_environment_constructor_observation_returns_original_object_and_arguments():
    trees, events, called = [], [], []
    source_data = [1, 2]
    args = (source_data,)
    kwargs = {"leafsize": 16}
    results = [object(), object(), object()]

    def constructor(*actual, **options):
        assert actual[0] is source_data
        assert options == kwargs
        called.append((actual, options))
        return results[len(called) - 1]

    for expected in results:
        assert (
            native.observe_tree(
                constructor,
                args,
                kwargs,
                trees,
                events,
                copy.deepcopy,
                runner.prior.exception_record,
            )
            is expected
        )
    assert all(a is b for a, b in zip(trees, results, strict=True))
    assert len(called) == 3
    assert [e["tree_index"] for e in events] == [0, 1, 2]
    assert [e["prior_successful_trees"] for e in events] == [0, 1, 2]
    assert all(
        e["request"] == {"args": args, "kwargs": kwargs} and e["outcome"] == "returned"
        for e in events
    )


@pytest.mark.parametrize("recorder_fails", [False, True])
def test_environment_constructor_failure_retains_request_cause_and_prior_objects(recorder_fails):
    previous = object()
    trees, events = [previous], []
    data = [1, 2]
    source_error = RuntimeError("synthetic native constructor failed")
    cause = ValueError("synthetic native cause")

    def constructor(*args, **kwargs):
        args[0].append(3)
        raise source_error from cause

    def record(error):
        if recorder_fails:
            raise OSError("synthetic secondary recorder failure")
        return runner.prior.exception_record(error)

    with pytest.raises(RuntimeError) as caught:
        native.observe_tree(
            constructor, (data,), {"leafsize": 16}, trees, events, copy.deepcopy, record
        )
    assert caught.value is source_error and caught.value.__cause__ is cause
    assert trees == [previous] and trees[0] is previous
    row = events[0]
    assert row["request"] == {"args": ([1, 2],), "kwargs": {"leafsize": 16}}
    assert row["outcome"] == "raised" and row["unreturned_c_allocation_available"] is False
    assert "tree_index" not in row
    if recorder_fails:
        assert row["error_capture_failure"]["type"] == "OSError"
    else:
        text = json.dumps(row["error"])
        assert "synthetic native cause" in text and "synthetic native constructor failed" in text


def test_environment_request_capture_failure_prevents_constructor_entry():
    trees, events, calls = [], [], []

    def capture(value):
        raise OSError("synthetic metadata capture failure")

    with pytest.raises(OSError, match="metadata capture"):
        native.observe_tree(
            lambda *a, **k: calls.append(True),
            ([1],),
            {},
            trees,
            events,
            capture,
            runner.prior.exception_record,
        )
    assert not calls and not events and not trees


@pytest.mark.parametrize("failed_stage", [None, "environment", "make_maskM"])
def test_environment_wrapper_observes_inline_assignment_without_reexecution(failed_stage):
    tree = ast.parse(Path(native.__file__).read_text())
    evaluate = next(n for n in tree.body if getattr(n, "name", None) == "evaluate")
    observed = next(
        n for n in ast.walk(evaluate) if isinstance(n, ast.FunctionDef) and n.name == "observed"
    )
    outer = ast.parse(
        "def make_observer(name, original, state, stream, save_stage, save_ecm, "
        "geometry_aliases, ecm, environment, save_environment, events, sites, "
        "namespace, environment_tree):\n"
        "    aliases = None\n    pass\n    return observed\n"
    ).body[0]
    outer.body[1] = copy.deepcopy(observed)
    scope = {"METHODS": native.METHODS}
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[outer], type_ignores=[])),
            "synthetic-env-observer",
            "exec",
        ),
        scope,
    )
    state = {"counter": 0}
    geometry, events = [], []
    ecm, environment = (
        {},
        dict(before=None, stages=[], cache=None, stream_before=None, stream_after=None),
    )
    original_tree = object()
    namespace = {"cKDTree": original_tree}
    caller = SimpleNamespace()
    trees = []

    def stream():
        return {"counter": state["counter"]}

    def save_environment(name):
        snapshot = dict(
            counter=state["counter"], grid_len=getattr(caller, "grid_len", None), trees=list(trees)
        )
        if name == "before":
            environment[name] = snapshot
        else:
            environment["stages"].append((name, snapshot))

    def environment_tree():
        trees.append(len(trees))
        return trees[-1]

    def observe(name, action):
        return scope["make_observer"](
            name,
            action,
            state,
            stream,
            lambda stage: geometry.append((stage, state["counter"])),
            lambda key: ecm.update({key: stream()}),
            lambda: {"synthetic_alias": True},
            ecm,
            environment,
            save_environment,
            events,
            {"betse/science/cells.py:make_world.grid_len": {"first_line": 494}},
            namespace,
            environment_tree,
        )(caller)

    def advance(self):
        state["counter"] += 1

    for name in ("cellVerts", "near_neigh", "makeECM"):
        observe(name, advance)
    saved_geometry = copy.deepcopy(geometry)
    saved_ecm = copy.deepcopy(ecm)

    def action(self):
        assert namespace["cKDTree"] is environment_tree
        advance(self)
        namespace["cKDTree"]()
        if state["stage"] == failed_stage:
            raise RuntimeError("synthetic native stage failure")
        if state["stage"] == "make_maskM":
            assert self.grid_len == 7
            namespace["cKDTree"]()

    if failed_stage == "environment":
        with pytest.raises(RuntimeError):
            observe("environment", action)
        assert environment["stages"] == []
    else:
        observe("environment", action)
        assert not hasattr(caller, "grid_len")
        # Stand-in for the independently AST-verified original inline assignment.
        caller.grid_len = 7
        if failed_stage == "make_maskM":
            with pytest.raises(RuntimeError):
                observe("make_maskM", action)
            assert [n for n, _ in environment["stages"]] == ["environment", "assign_grid_len"]
            assert environment["cache"] is None
        else:
            observe("make_maskM", action)
            assert [n for n, _ in environment["stages"]] == list(native.ENVIRONMENT_STAGES)
            assert environment["cache"] is environment["stages"][-1][1]
            assert len(trees) == 3
        assert events[-1]["kind"] == "inline_assignment_observed"
        assert events[-1]["observed_at"] == "make_maskM_entry"
        assert environment["stages"][0][1]["grid_len"] is None
        assert environment["stages"][1][1]["grid_len"] == 7
    assert namespace["cKDTree"] is original_tree
    assert geometry == saved_geometry and ecm == saved_ecm


@pytest.mark.parametrize(
    "mutation",
    [
        None,
        "missing_stage",
        "wrong_order",
        "missing_cache",
        "two_trees",
        "four_trees",
        "source_error",
        "capture_error",
    ],
)
def test_environment_completion_refuses_partial_stages_or_tree_rosters(mutation):
    tree = ast.parse(Path(native.__file__).read_text())
    evaluate = next(n for n in tree.body if getattr(n, "name", None) == "evaluate")
    assignment = next(
        n
        for n in evaluate.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "completed" for t in n.targets)
    )
    env = dict(
        before={},
        cache={},
        stream_before={},
        stream_after={},
        stages=[(name, {}) for name in native.ENVIRONMENT_STAGES],
    )
    scope = dict(
        stop_after="make_maskM",
        error=None,
        state={"capture_error": None},
        METHODS=native.METHODS,
        ENVIRONMENT_STAGES=native.ENVIRONMENT_STAGES,
        stages=[(n, {}) for n in ("before", *native.METHODS)],
        ecm=dict(before={}, cache={}, stream_before={}, stream_after={}),
        environment=env,
        environment_trees=[object() for _ in range(3)],
    )
    if mutation == "missing_stage":
        env["stages"].pop()
    elif mutation == "wrong_order":
        env["stages"].reverse()
    elif mutation == "missing_cache":
        env["cache"] = None
    elif mutation == "two_trees":
        scope["environment_trees"].pop()
    elif mutation == "four_trees":
        scope["environment_trees"].append(object())
    elif mutation == "source_error":
        scope["error"] = {"source": "failed"}
    elif mutation == "capture_error":
        scope["state"]["capture_error"] = {"capture": "failed"}
    observed = eval(
        compile(ast.Expression(assignment.value), "synthetic-completion", "eval"), scope
    )
    assert observed is (mutation is None)


def test_poisson_literal_methods_default_and_four_caller_sites_are_original():
    groups, sites = native.source_nodes(ROOT, stop_after="lapENV_P_inv")
    cells = next(nodes[0] for file, nodes in groups if file == "betse/science/cells.py")
    world = next(n for n in cells.body if n.name == "make_world")
    original = next(
        n
        for n in original_class("betse/science/cells.py", "Cells").body
        if getattr(n, "name", None) == "make_world"
    )
    assert native.POISSON_STAGES == ("environment_voltage", "environment_current")
    assert native.methods_for("lapENV_P_inv") == native.methods_for("make_maskM")
    assert "makeLaplacian" not in native.methods_for("lapENV_P_inv")
    assert [node_dump(n) for n in world.body] == [
        node_dump(n) for n in original.body[: len(world.body)]
    ]
    assert node_dump(world.body[-1]) == node_dump(
        ast.parse("_, self.lapENV_P_inv = self.grid_obj.makeLaplacian(bound=bdic)").body[0]
    )
    assert "lapGJ" not in ast.unparse(world)
    for line in (503, 504, 511, 512):
        node = next(n for n in original.body if n.lineno == line)
        assert sites[f"betse/science/cells.py:make_world.assignment_{line}"] == {
            "first_line": line,
            "last_line": node.end_lineno,
            "ast_sha256": hashlib.sha256(node_dump(node).encode()).hexdigest(),
        }
    grid = next(nodes[0] for file, nodes in groups if file == "betse/science/math/finitediff.py")
    source = original_class("betse/science/math/finitediff.py", "FiniteDiffSolver")
    assert [n.name for n in grid.body] == ["__init__", "cell_grid", "makeLaplacian"]
    for method in grid.body:
        assert node_dump(method) == node_dump(
            next(n for n in source.body if getattr(n, "name", None) == method.name)
        )
    laplacian = grid.body[-1]
    assert sites["betse/science/math/finitediff.py:FiniteDiffSolver.makeLaplacian"] == {
        "first_line": laplacian.lineno,
        "last_line": laplacian.end_lineno,
        "ast_sha256": hashlib.sha256(node_dump(laplacian).encode()).hexdigest(),
    }
    assert (
        ast.unparse(laplacian.args.defaults[0])
        == "{'N': 'value', 'S': 'value', 'E': 'value', 'W': 'value'}"
    )
    assert [
        ast.unparse(n.func)
        for n in ast.walk(laplacian)
        if isinstance(n, ast.Call) and ast.unparse(n.func) in ("np.zeros", "np.linalg.pinv")
    ] == ["np.zeros", "np.linalg.pinv"]
    for file, nodes in groups:
        compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), file, "exec")


def test_poisson_endpoint_keeps_environment_stores_inputs_and_metadata_closure(declared):
    raw, conf = declared
    conf["general options"] = {"comp grid size": 25}
    assert native.inputs(raw, conf, stop_after="lapENV_P_inv") == native.inputs(
        raw, conf, stop_after="make_maskM"
    )
    assert native.pins_for("lapENV_P_inv") == native.pins_for("make_maskM")
    assert native.metadata_imports_for("lapENV_P_inv") == native.metadata_imports_for("make_maskM")
    old, old_sites = native.source_nodes(ROOT, stop_after="make_maskM")
    new, new_sites = native.source_nodes(ROOT, stop_after="lapENV_P_inv")
    for (old_file, old_nodes), (new_file, new_nodes) in zip(old, new, strict=True):
        assert old_file == new_file
        if old_file not in ("betse/science/cells.py", "betse/science/math/finitediff.py"):
            assert [node_dump(n) for n in old_nodes] == [node_dump(n) for n in new_nodes]
    assert (
        new_sites["betse/science/cells.py:make_world.grid_len"]
        == old_sites["betse/science/cells.py:make_world.grid_len"]
    )
    conf["general options"]["comp grid size"] = 24
    with pytest.raises(ValueError, match="integer computational grid size 25"):
        native.inputs(raw, conf, stop_after="lapENV_P_inv")


def test_poisson_helper_observes_once_and_keeps_immediate_and_mutated_return_distinct():
    calls, helpers, events = [], [], []
    value = [0, 0]
    args, kwargs = ((2, 2),), {"synthetic": True}

    def source(*actual, **options):
        calls.append((actual, options))
        return value

    result = native.observe_poisson_helper(
        source,
        "zeros",
        "environment_voltage",
        args,
        kwargs,
        helpers,
        events,
        copy.deepcopy,
        runner.prior.exception_record,
    )
    assert result is value and helpers[0][2] is value
    assert calls == [(args, kwargs)]
    assert events[0]["request"] == {"args": args, "kwargs": kwargs}
    assert events[0]["output"] == [0, 0]
    value[0] = -4
    assert helpers[0][2] == [-4, 0] and events[0]["output"] == [0, 0]
    assert events[0]["outcome"] == "returned"


@pytest.mark.parametrize("recorder_fails", [False, True])
def test_poisson_helper_source_failure_keeps_primary_cause_and_earlier_returns(recorder_fails):
    previous = object()
    helpers, events = [("environment_voltage", "zeros", previous)], []
    primary, cause = RuntimeError("synthetic pinv failed"), ValueError("original cause")

    def source(*args, **kwargs):
        raise primary from cause

    def record(error):
        if recorder_fails:
            raise OSError("synthetic error recorder failed")
        return runner.prior.exception_record(error)

    with pytest.raises(RuntimeError) as caught:
        native.observe_poisson_helper(
            source,
            "pinv",
            "environment_voltage",
            ([1],),
            {},
            helpers,
            events,
            copy.deepcopy,
            record,
        )
    assert caught.value is primary and caught.value.__cause__ is cause
    assert helpers[0][2] is previous and len(helpers) == 1
    assert events[0]["outcome"] == "raised" and "output" not in events[0]
    if recorder_fails:
        assert events[0]["error_capture_failure"]["type"] == "OSError"
    else:
        assert "original cause" in json.dumps(events[0]["source_error"])


@pytest.mark.parametrize("failed_capture", ["request", "output"])
def test_poisson_helper_capture_failure_has_no_extra_delegate_call(failed_capture):
    calls, helpers, events = [], [], []
    value = [0]

    def source(*args, **kwargs):
        calls.append(True)
        return value

    def capture(item):
        if (type(item) is dict) == (failed_capture == "request"):
            raise OSError("synthetic capture failure")
        return copy.deepcopy(item)

    with pytest.raises(OSError, match="capture failure"):
        native.observe_poisson_helper(
            source,
            "zeros",
            "environment_voltage",
            ((1, 1),),
            {},
            helpers,
            events,
            capture,
            runner.prior.exception_record,
        )
    if failed_capture == "request":
        assert calls == helpers == events == []
    else:
        assert calls == [True] and helpers[0][2] is value
        assert events[0]["outcome"] == "returned" and "output" not in events[0]


@pytest.mark.parametrize("stage", native.POISSON_STAGES)
def test_poisson_assignment_requires_exact_original_inverse_object(stage):
    index = native.POISSON_STAGES.index(stage)
    A, Ainv = [1], [2]
    caller = SimpleNamespace(**{native.POISSON_ASSIGNMENTS[index]: Ainv})
    native.poisson_assignment(caller, stage, (A, Ainv))
    with pytest.raises(ValueError, match="identity"):
        native.poisson_assignment(caller, stage, (A, list(Ainv)))
    with pytest.raises(ValueError, match="return pair"):
        native.poisson_assignment(caller, stage, [A, Ainv])
    assert getattr(caller, native.POISSON_ASSIGNMENTS[index]) is Ainv


def poisson_synthetic_scope():
    """Execute only normalized observer functions with Python-list delegates."""
    tree = ast.parse(Path(native.__file__).read_text())
    evaluate = next(n for n in tree.body if getattr(n, "name", None) == "evaluate")
    names = (
        "poisson_snapshot",
        "finish_poisson_assignment",
        "poisson_helper",
        "poisson_zeros",
        "poisson_pinv",
        "observed_laplacian",
        "callback",
    )
    functions = [
        copy.deepcopy(
            next(n for n in ast.walk(evaluate) if isinstance(n, ast.FunctionDef) and n.name == name)
        )
        for name in names
    ]

    class CaptureFailure(Exception):
        pass

    grid = SimpleNamespace()
    caller = SimpleNamespace(grid_obj=grid, retained_env=[7])
    namespace = {"np": object()}
    state = dict(caller=caller, stage="make_maskM", capture_error=None)
    helpers, results, events, calls = [], [], [], []
    scope = dict(
        state=state,
        namespace=namespace,
        events=events,
        stop_after="lapENV_P_inv",
        poisson=dict(before=None, stages=[], cache=None, stream_before=None, stream_after=None),
        poisson_results=results,
        poisson_helpers=helpers,
        POISSON_STAGES=native.POISSON_STAGES,
        poisson_assignment=native.poisson_assignment,
        observe_poisson_helper=native.observe_poisson_helper,
        SimpleNamespace=SimpleNamespace,
        CaptureFailure=CaptureFailure,
        wire=SimpleNamespace(capture=copy.deepcopy),
        capture_environment=copy.deepcopy,
        public_environment=lambda: {k: v for k, v in vars(caller).items() if k != "grid_obj"},
        stream=lambda: {"unchanged_synthetic_stream": True},
        record_exception=runner.prior.exception_record,
        sites={
            f"betse/science/cells.py:make_world.assignment_{line}": {"first_line": line}
            for line in (504, 512)
        },
    )

    def zeros(*args, **kwargs):
        calls.append(("zeros", args, kwargs))
        return [0]

    def pinv(value):
        calls.append(("pinv", value))
        return ["inverse", *value]

    def original(owner, *, bound):
        assert owner is grid
        calls.append(("method", bound))
        numeric = namespace["np"]
        A = numeric.zeros((1, 1))
        A[0] = bound["N"]
        # The real method divides into a new A; use a distinct symbolic list.
        scaled = ["scaled", *A]
        return scaled, numeric.linalg.pinv(scaled)

    scope.update(original_zeros=zeros, original_pinv=pinv, original_grid_method=original)
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])),
            "synthetic-poisson-observers",
            "exec",
        ),
        scope,
    )
    return scope, caller, grid, calls


def test_poisson_observers_keep_single_calls_return_aliases_boundaries_and_environment():
    scope, caller, grid, calls = poisson_synthetic_scope()
    original_numpy = scope["namespace"]["np"]
    env_before = copy.deepcopy(vars(caller)["retained_env"])
    returned = []
    scope["callback"](status="before voltage")
    for index, (stage, boundary) in enumerate(
        zip(native.POISSON_STAGES, ("value", "flux"), strict=True)
    ):
        options = dict.fromkeys(("N", "S", "E", "W"), boundary)
        value = scope["observed_laplacian"](grid, bound=options)
        returned.append(value)
        assert calls[index * 3][1] is options
        assert scope["namespace"]["np"] is original_numpy
        assert scope["poisson_results"][-1][1] is value
        # The original AST assignment is separately exact-checked above.
        setattr(caller, native.POISSON_ASSIGNMENTS[index], value[1])
        if index == 0:
            scope["callback"](status="before current")
        else:
            scope["finish_poisson_assignment"]()
        assert scope["poisson"]["stages"][-1][0] == stage
    data = scope["poisson"]
    assert data["before"]["outputs"] == {"results": [], "helpers": []}
    assert len(calls) == 6
    assert data["cache"] is data["stages"][-1][1]
    first, final = (row[1] for row in data["stages"])
    assert len(first["outputs"]["results"]) == 1 and len(final["outputs"]["results"]) == 2
    assert [(s, n) for s, n, _ in final["outputs"]["helpers"]] == [
        (s, n) for s in native.POISSON_STAGES for n in ("zeros", "pinv")
    ]
    assert first["outputs"]["helpers"][0][2] == ["value"]
    immediate = [e for e in scope["events"] if e["kind"] == "poisson_helper"]
    assert immediate[0]["output"] == immediate[2]["output"] == [0]
    assert caller.lapENVinv is returned[0][1] and caller.lapENV_P_inv is returned[1][1]
    assert caller.retained_env == env_before
    assert "lapENVinv" not in data["before"]["environment"]
    assert "lapENV_P_inv" not in first["environment"]
    assert scope["state"]["capture_error"] is None


def test_poisson_observer_source_failure_restores_namespace_and_preserves_helpers():
    scope, caller, grid, calls = poisson_synthetic_scope()
    original_numpy = scope["namespace"]["np"]
    primary = RuntimeError("synthetic inverse source failure")

    def failed(*args, **kwargs):
        raise primary

    scope["original_pinv"] = failed
    with pytest.raises(RuntimeError) as caught:
        scope["observed_laplacian"](grid, bound=dict.fromkeys(("N", "S", "E", "W"), "value"))
    assert caught.value is primary
    assert scope["namespace"]["np"] is original_numpy
    assert scope["poisson_results"] == [] and scope["poisson"]["stages"] == []
    assert [name for _, name, _ in scope["poisson_helpers"]] == ["zeros"]
    assert scope["events"][-1]["outcome"] == "raised"
    assert not hasattr(caller, "lapENVinv")
    assert scope["state"]["capture_error"] is None


@pytest.mark.parametrize("failure", ["assignment", "snapshot"])
def test_poisson_boundary_capture_failure_is_not_a_source_failure(failure):
    scope, caller, grid, _ = poisson_synthetic_scope()
    returned = scope["observed_laplacian"](grid, bound=dict.fromkeys(("N", "S", "E", "W"), "value"))
    caller.lapENVinv = list(returned[1]) if failure == "assignment" else returned[1]
    if failure == "snapshot":

        def capture(value):
            raise OSError("synthetic boundary writer failed")

        scope["wire"].capture = capture
    with pytest.raises(scope["CaptureFailure"]):
        scope["finish_poisson_assignment"]()
    assert scope["poisson"]["stages"] == []
    assert scope["poisson_results"][0][1] is returned
    assert scope["state"]["capture_error"] is not None


@pytest.mark.parametrize(
    "mutation",
    [
        None,
        "missing_stage",
        "wrong_order",
        "missing_cache",
        "missing_result",
        "missing_helper",
        "wrong_helper",
        "source_error",
        "capture_error",
    ],
)
def test_poisson_completion_requires_two_full_stages_and_exact_helpers(mutation):
    tree = ast.parse(Path(native.__file__).read_text())
    evaluate = next(n for n in tree.body if getattr(n, "name", None) == "evaluate")
    expression = next(
        n.value
        for n in evaluate.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "completed" for t in n.targets)
    )
    scope = dict(
        stop_after="lapENV_P_inv",
        error=None,
        state={"capture_error": None},
        METHODS=native.METHODS,
        ENVIRONMENT_STAGES=native.ENVIRONMENT_STAGES,
        POISSON_STAGES=native.POISSON_STAGES,
        stages=[(n, {}) for n in ("before", *native.METHODS)],
        ecm=dict(before={}, cache={}, stream_before={}, stream_after={}),
        environment=dict(
            before={},
            cache={},
            stream_before={},
            stream_after={},
            stages=[(n, {}) for n in native.ENVIRONMENT_STAGES],
        ),
        environment_trees=[object() for _ in range(3)],
        poisson=dict(
            before={},
            cache={},
            stream_before={},
            stream_after={},
            stages=[(n, {}) for n in native.POISSON_STAGES],
        ),
        poisson_results=[(n, ([], [])) for n in native.POISSON_STAGES],
        poisson_helpers=[(s, n, []) for s in native.POISSON_STAGES for n in ("zeros", "pinv")],
    )
    if mutation == "missing_stage":
        scope["poisson"]["stages"].pop()
    elif mutation == "wrong_order":
        scope["poisson"]["stages"].reverse()
    elif mutation == "missing_cache":
        scope["poisson"]["cache"] = None
    elif mutation == "missing_result":
        scope["poisson_results"].pop()
    elif mutation == "missing_helper":
        scope["poisson_helpers"].pop()
    elif mutation == "wrong_helper":
        scope["poisson_helpers"][-1] = ("environment_current", "zeros", [])
    elif mutation == "source_error":
        scope["error"] = {"failed": "source"}
    elif mutation == "capture_error":
        scope["state"]["capture_error"] = {"failed": "capture"}
    assert eval(
        compile(ast.Expression(expression), "synthetic-poisson-completion", "eval"), scope
    ) is (mutation is None)
