"""Metadata/software controls; no original numerical body is executed."""

import ast
import copy
import hashlib
import json
import sys
from pathlib import Path

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
