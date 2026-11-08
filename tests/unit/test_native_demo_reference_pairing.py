"""Real launch preflight definition against inert source-only pair fixtures."""

import ast
import hashlib
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "validation/betse/native_seed_demo_launch.py"
REFERENCE = "validation/betse/native_init_terminal_reference.py"
PARAMETERS = "validation/betse/betse_native_parameter_world_ready_qualification.py"
WRITERS = (
    "validation.betse.native_seed_demo",
    "validation.betse.native_seed_world_callback_prelude",
)


def require(value, message):
    if not value:
        raise ValueError(message)


@pytest.fixture
def check():
    tree = ast.parse((ROOT / SOURCE).read_bytes())
    node = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_reference_writer_bindings"
    )
    namespace = dict(
        ast=ast,
        hashlib=hashlib,
        require=require,
        initial_rng=SimpleNamespace(ORIGINAL=REFERENCE),
    )
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), "<pairing-preflight>", "exec"), namespace
    )
    return namespace[node.name]


@pytest.fixture
def pair(tmp_path):
    files = {}
    writers = {}
    for index, name in enumerate(WRITERS):
        relative = name.replace(".", "/") + ".py"
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = f"INDEX = {index}\nraise AssertionError('writer must not execute')\n".encode()
        path.write_bytes(raw)
        writers[name] = hashlib.sha256(raw).hexdigest()
        files[relative] = dict(sha256=writers[name])
    value = SimpleNamespace(
        source=tmp_path,
        declaration=dict(common_start=dict(program_identity="bound-by-existing-common-check")),
        manifest=dict(files=files),
        writers=writers,
    )
    reference(value, "WRITER_PRODUCERS = " + repr(writers))
    return value


def reference(pair, declaration):
    raw = (declaration + "\nraise AssertionError('reference must not execute')\n").encode()
    (pair.source / REFERENCE).write_bytes(raw)
    pair.manifest["files"][REFERENCE] = dict(sha256=hashlib.sha256(raw).hexdigest())


def test_reference_pairing_accepts_exact_writers_without_running_any_source(check, pair):
    before = {name: (pair.source / name).read_bytes() for name in pair.manifest["files"]}
    check(pair.source, pair.declaration, pair.manifest)
    assert before == {name: (pair.source / name).read_bytes() for name in before}


@pytest.mark.parametrize("name", WRITERS)
def test_reference_pairing_rejects_stale_writer_even_with_valid_file_hashes(check, pair, name):
    # Actual11's seam: the reference file is authentic but names the prior writer.
    pair.writers[name] = "0" * 64
    reference(pair, "WRITER_PRODUCERS = " + repr(pair.writers))
    with pytest.raises(ValueError, match="bindings do not match"):
        check(pair.source, pair.declaration, pair.manifest)


@pytest.mark.parametrize("kind", ("missing", "extra", "sequence", "computed", "duplicate"))
def test_reference_pairing_rejects_incomplete_or_computed_roster(check, pair, kind):
    writers = dict(pair.writers)
    if kind == "missing":
        writers.pop(WRITERS[0])
    elif kind == "extra":
        writers["foreign.writer"] = "f" * 64
    elif kind == "sequence":
        writers = list(writers.items())
    text = "WRITER_PRODUCERS = " + repr(writers)
    if kind == "computed":
        text = "WRITER_PRODUCERS = forbidden_factory()"
    elif kind == "duplicate":
        text += "\n" + text
    reference(pair, text)
    with pytest.raises(ValueError):
        check(pair.source, pair.declaration, pair.manifest)


@pytest.mark.parametrize("name", (REFERENCE, *(n.replace(".", "/") + ".py" for n in WRITERS)))
def test_reference_pairing_rejects_source_change_after_manifest(check, pair, name):
    path = pair.source / name
    path.write_bytes(path.read_bytes() + b"# drift\n")
    with pytest.raises(ValueError, match="source changed"):
        check(pair.source, pair.declaration, pair.manifest)


def test_reference_pairing_unselected_legacy_route_does_not_require_reference(check, tmp_path):
    check(tmp_path / "absent", {}, {})


def test_reference_pairing_check_runs_in_existing_immutable_preflight():
    tree = ast.parse((ROOT / SOURCE).read_bytes())
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_immutable"
    )
    calls = [
        node.func.id
        for statement in function.body
        for node in ast.walk(statement)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert calls.count("_reference_writer_bindings") == 1
    assert (
        calls.index("_common_start")
        < calls.index("_reference_writer_bindings")
        < calls.index("_sim_contract")
    )


def test_parameter_runtime_metadata_import_never_imports_model_or_libraries():
    # The suite's real import/native guards remain installed throughout this
    # fresh module import and the exact runtime_plan used by reference prepare.
    before = set(sys.modules)
    spec = importlib.util.spec_from_file_location("_pairing_parameter_metadata", ROOT / PARAMETERS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plan = module.runtime_plan()
    assert plan["actual_library_import"] is False
    assert set(plan["providers"]) == {
        "numpy",
        "scipy",
        "matplotlib",
        "jax",
        "jaxlib",
        "ml_dtypes",
        "opt_einsum",
    }
    forbidden = {"cells", "betse", "numpy", "scipy", "matplotlib", "jax", "jaxlib"}
    assert not any(name.split(".")[0] in forbidden for name in set(sys.modules) - before)


@pytest.mark.parametrize("immutable", (False, True))
def test_history_helper_loads_at_observer_construction_and_preserves_wire(immutable):
    tree = ast.parse((ROOT / PARAMETERS).read_bytes())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_observer")
    imports, conversions = [], []

    class Descriptor:
        pass

    wire = {"field": ("raw", "bits")}
    descriptor = Descriptor() if immutable else wire

    def convert(value):
        conversions.append(value)
        assert value is descriptor
        return wire

    helper = SimpleNamespace(HistoricalDescriptor=Descriptor, history_wire_descriptor=convert)

    def load(name, globals=None, locals=None, fromlist=(), level=0):
        assert name == "cells.processes" and fromlist == ("betse_native_immutable_graph_metadata",)
        assert level == 0
        imports.append(name)
        return SimpleNamespace(betse_native_immutable_graph_metadata=helper)

    namespace = dict(require=require, SimpleNamespace=SimpleNamespace)
    exec(compile(ast.Module(body=[node], type_ignores=[]), "<observer-factory>", "exec"), namespace)
    namespace["__builtins__"] = dict(vars(__import__("builtins")), __import__=load)
    # Recreate with the bounded importer captured as the function's builtins.
    exec(compile(ast.Module(body=[node], type_ignores=[]), "<observer-factory>", "exec"), namespace)
    assert imports == []
    owner = Descriptor()
    objects = (object(), object())
    context = SimpleNamespace(graph=(objects, descriptor))
    module = SimpleNamespace(Owner=Descriptor, _ISSUED={owner: context})
    observer = namespace["_observer"]({"actual": module}, "actual", "Owner", {"p": None})
    assert imports == ["cells.processes"]
    _, graphs, captures = observer(owner, None)
    assert graphs == {"graph": {"data": wire, "object_identities": tuple(map(id, objects))}}
    assert graphs["graph"]["data"] is wire and captures == {}
    assert conversions == ([descriptor] if immutable else [])
