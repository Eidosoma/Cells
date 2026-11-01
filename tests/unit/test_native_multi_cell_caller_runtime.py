"""Namespace metadata and synthetic definitions only; no native body executes."""

import ast
import copy
import hashlib
import importlib.abc
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from validation.betse import native_multi_cell_caller_native_source as source
from validation.betse import native_multi_cell_caller_runtime as runtime

ROOT = Path("/mnt/workspaces/Cells/betse-v1.5.0")


@pytest.fixture(autouse=True)
def no_native_or_science(monkeypatch):
    attempts = []

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {"cells", "betse", "numpy", "scipy", "PIL", "jax"}:
                attempts.append(("import", fullname))
                raise AssertionError("Scientific import forbidden: " + fullname)

    previous = sys.getprofile()

    def profile(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if event == "call" and frame.f_code.co_filename.startswith(str(ROOT) + "/"):
            attempts.append(("native_call", frame.f_code.co_qualname))
            raise AssertionError("Original native body execution forbidden")

    blocker = Block()
    sys.meta_path.insert(0, blocker)
    sys.setprofile(profile)
    try:
        yield
    finally:
        sys.setprofile(previous)
        sys.meta_path.remove(blocker)
    assert not attempts


@pytest.fixture
def package(tmp_path):
    """Small synthetic functions occupy the declared module roles, not native ASTs."""
    bodies = {name: "marker = 'synthetic'\n" for name in runtime.MODULE_ORDER}
    exceptions = (
        "BetseMathLineException",
        "BetseMathPointException",
        "BetseMathPolygonException",
        "BetsePathnameException",
        "BetseFileException",
        "BetseMathInterpolationException",
        "BetseImageException",
        "BetseMathMeshException",
        "BetseSimConfException",
        "BetseIterableException",
    )
    bodies["betse.exceptions"] = "".join(
        "class " + name + "(ValueError):\n    pass\n" for name in exceptions
    )
    bodies["betse.util.type.types"] = "def type_check(value):\n    return value\n"
    bodies["betse.util.type.iterable.sequences"] = (
        "def is_sequence(value):\n    return isinstance(value, SequenceTypes)\n"
    )
    bodies["betse.util.type.iterable.generators"] = (
        "def is_generator(value):\n    return isinstance(value, GeneratorType)\n"
    )
    bodies["betse.util.type.cls.classes"] = (
        "@type_check\ndef get_name_unqualified(cls):\n    return cls.__name__\n"
    )
    bodies["betse.lib.numpy.nparray"] = (
        "@type_check\ndef to_iterable(value):\n    return ('array', value)\n"
        "def from_iterable(value):\n    return ('from_array', value)\n"
        "def to_signed(value):\n    return value\n"
        "def independent_global():\n    return __name__\n"
    )
    bodies["betse.lib.numpy.npscalar"] = "def to_python(value):\n    return value\n"
    bodies["betse.util.type.iterable.iterables"] = (
        "@type_check\ndef to_iterable(value):\n"
        "    from betse.lib.numpy import nparray\n"
        "    from betse.util.type.cls import classes\n"
        "    from betse.util.type.iterable import generators\n"
        "    from numpy import ndarray\n"
        "    return ('iterable', nparray.to_iterable(value), "
        "classes.get_name_unqualified(ndarray), "
        "generators.is_generator(value))\n"
        "def qualified_import():\n"
        "    import betse.lib.numpy.nparray\n"
        "    return betse.lib.numpy.nparray.independent_global()\n"
    )
    bodies["betse.util.math.geometry.geopoint"] = (
        "def intersect_lines(value):\n    return iterables.to_iterable(value)\n"
        "def fail_original(value):\n    raise BetseMathLineException(value)\n"
    )
    bodies["betse.util.type.numeric.floats"] = "PI = math.pi\nTWO_PI = 2 * PI\n"
    bodies["betse.util.math.geometry.polygon.geopoly"] = (
        "def is_convex(value):\n"
        "    from betse.util.type.numeric.floats import PI, TWO_PI\n"
        "    return (PI, TWO_PI, value)\n"
        "def is_cyclic_quad(value):\n    return value\n"
        "def orient_counterclockwise(value):\n    return value\n"
    )
    bodies["betse.util.math.geometry.polygon.geopolyconvex"] = (
        "def clip_counterclockwise(value):\n    return geopoint.intersect_lines(value)\n"
    )
    bodies["betse.util.math.mathoper"] = "def det1d(value):\n    return value\n"
    bodies["betse.lib.pil.pilnumpy"] = "class ImageModeType(Enum):\n    SYNTHETIC = 'S'\n"
    bodies["betse.util.math.mathinterp"] = "def interp2d_linear(value):\n    return value\n"
    bodies["betse.science.tissue.picker.tispickcls"] = "class TissuePickerABC:\n    pass\n"
    bodies["betse.science.tissue.picker.tispickimage"] = (
        "class TissuePickerImageMask:\n"
        "    def __init__(self):\n        raise AssertionError('decode forbidden')\n"
        "class TissuePickerImage(TissuePickerABC):\n"
        "    def __init__(self):\n        raise AssertionError('picker forbidden')\n"
    )
    bodies["betse.science.math.mesh"] = (
        "class DECMesh:\n"
        "    def __init__(self):\n        raise AssertionError('constructor forbidden')\n"
        "    def synthetic_route(self, value):\n        return clip_counterclockwise(value)\n"
        "    def display(self):\n        from matplotlib import pyplot\n        return pyplot\n"
        "    def private_random(self):\n        return np.random\n"
    )
    bodies["betse.science.cells"] = (
        "class Cells:\n"
        "    def __init__(self):\n        raise AssertionError('constructor forbidden')\n"
        "    def synthetic_import(self):\n"
        "        from betse.science.tissue.picker.tispickimage import TissuePickerImage\n"
        "        return TissuePickerImage\n"
    )
    bodies["betse.science.parameters"] = (
        "def store_parameters(self):\n    raise AssertionError('stores forbidden')\n"
    )
    groups = []
    for name, body in bodies.items():
        relative = name.replace(".", "/") + ".py"
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        groups.append((relative, ast.parse(body, filename=str(path)).body))
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Scientific delegate forbidden")

    class FakeArray:
        pass

    fake_numpy = SimpleNamespace(array=forbidden, ndarray=FakeArray, random=object())
    dependencies = dict(
        numpy=fake_numpy,
        image=SimpleNamespace(open=forbidden),
        spline=forbidden,
        hull=forbidden,
        delaunay=forbidden,
        tree=forbidden,
        rng=object(),
        log=forbidden,
    )
    return SimpleNamespace(root=tmp_path, groups=groups, dependencies=dependencies, calls=calls)


def build(package):
    return runtime.build(package.groups, native_root=package.root, **package.dependencies)


def append(package, module, text):
    relative = module.replace(".", "/") + ".py"
    nodes = ast.parse(text, filename=str(package.root / relative)).body
    package.groups.append((relative, nodes))


def test_build_exports_and_definition_only_boundaries(package):
    before = {name: value for name, value in sys.modules.items() if name.startswith("betse")}
    result = build(package)
    assert set(result) == set(runtime.EXPORTS) | {"CellLatticeType", "modules", "metadata"}
    assert len(result["modules"]) == 25
    assert result["Cells"].__module__ == "betse.science.cells"
    assert result["DECMesh"].__module__ == "betse.science.math.mesh"
    assert result["TissuePickerImage"].__bases__ == (
        result["modules"]["betse.science.tissue.picker.tispickcls"]["TissuePickerABC"],
    )
    assert [item.name for item in result["CellLatticeType"]] == ["HEX", "SQUARE"]
    after = {name: value for name, value in sys.modules.items() if name.startswith("betse")}
    assert after == before
    assert package.calls == []


def test_same_named_helpers_keep_original_globals_and_lazy_modules(package):
    result = build(package)
    modules = result["modules"]
    array = modules["betse.lib.numpy.nparray"]["to_iterable"]
    iterable = modules["betse.util.type.iterable.iterables"]["to_iterable"]
    assert array is not iterable and array.__globals__ is not iterable.__globals__
    assert array.__globals__ is modules["betse.lib.numpy.nparray"]
    assert iterable.__globals__ is modules["betse.util.type.iterable.iterables"]
    assert iterable("token") == ("iterable", ("array", "token"), "FakeArray", False)
    assert result["DECMesh"].synthetic_route(None, "token") == iterable("token")
    assert result["Cells"].synthetic_import(None) is result["TissuePickerImage"]
    assert modules["betse.util.type.iterable.iterables"]["qualified_import"]() == (
        "betse.lib.numpy.nparray"
    )
    assert package.calls == []


def test_private_packages_override_nothing_in_sys_modules(package, monkeypatch):
    poisoned = ModuleType("betse.lib.numpy.nparray")
    monkeypatch.setitem(sys.modules, "betse.lib.numpy.nparray", poisoned)
    result = build(package)
    helper = result["modules"]["betse.util.type.iterable.iterables"]["to_iterable"]
    assert helper("token")[1] == ("array", "token")
    assert sys.modules["betse.lib.numpy.nparray"] is poisoned


def test_each_build_has_fresh_module_function_and_rng_ownership(package):
    first = build(package)
    second_rng = object()
    package.dependencies["rng"] = second_rng
    second = build(package)
    assert first["modules"] is not second["modules"]
    assert first["Cells"] is not second["Cells"]
    assert first["DECMesh"].private_random(None) is not second_rng
    assert second["DECMesh"].private_random(None) is second_rng
    assert second["DECMesh"].private_random(None) is not package.dependencies["numpy"].random


def test_source_module_exception_identity_and_original_cause_unchanged(package):
    result = build(package)
    error_type = result["modules"]["betse.exceptions"]["BetseMathLineException"]
    helper = result["modules"]["betse.util.math.geometry.geopoint"]["fail_original"]
    with pytest.raises(error_type, match="retained cause") as caught:
        helper("retained cause")
    assert type(caught.value) is error_type and caught.value.__cause__ is None


@pytest.mark.parametrize(
    "statement",
    [
        "from matplotlib import pyplot",
        "from betse.util.type.call import callers",
        "from cells import models",
        "import numpy.linalg",
        "import subprocess",
        "from betse.lib.numpy.nparray import missing",
        "from betse.lib.numpy.nparray import *",
        "from . import nparray",
    ],
)
def test_reached_unprepared_imports_refuse_without_package_fallback(package, statement):
    if statement.endswith("import *"):
        # Python forbids star imports in functions before our private policy.
        with pytest.raises(ValueError, match="module scope"):
            append(package, "betse.lib.numpy.nparray", statement)
            build(package)
        return
    append(package, "betse.lib.numpy.nparray", "def probe():\n    " + statement + "\n")
    result = build(package)
    with pytest.raises(ImportError, match="independent import|imported member"):
        result["modules"]["betse.lib.numpy.nparray"]["probe"]()
    assert package.calls == []


def test_import_hook_refuses_undeclared_requests_even_for_prepared_module(package):
    result = build(package)
    namespace = result["modules"]["betse.util.type.iterable.iterables"]
    importer = namespace["__builtins__"]["__import__"]
    with pytest.raises(ImportError, match="Undeclared"):
        importer("betse.exceptions", fromlist=("BetseMathLineException",))
    with pytest.raises(ImportError, match="Undeclared"):
        importer("betse.lib.numpy", fromlist=("nparray", "npscalar"))


def test_original_file_line_ast_metadata_and_input_ast_are_retained(package):
    before = [
        [ast.dump(node, include_attributes=True) for node in nodes] for _, nodes in package.groups
    ]
    result = build(package)
    name = "betse.lib.numpy.nparray"
    record = result["metadata"]["modules"][name]
    path = package.root / "betse/lib/numpy/nparray.py"
    assert record["file"] == str(path)
    assert record["file_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    function = result["modules"][name]["to_iterable"]
    assert function.__code__.co_filename == str(path)
    assert function.__module__ == name
    assert function.__code__.co_firstlineno == 1  # synthetic decorator retains line attribution
    assert record["sites"]["to_iterable"]["first_line"] == 2
    assert before == [
        [ast.dump(node, include_attributes=True) for node in nodes] for _, nodes in package.groups
    ]


def test_partial_namespace_and_primary_failure_are_retained(package):
    append(
        package,
        "betse.science.cells",
        "class FailDuringDefinition:\n    raise ValueError('original definition failure')\n",
    )
    with pytest.raises(runtime.RuntimeAssemblyError) as caught:
        build(package)
    error = caught.value
    assert error.module == "betse.science.cells"
    assert error.source_error is error.__cause__
    assert type(error.source_error) is ValueError
    assert str(error.source_error) == "original definition failure"
    assert "Cells" in error.modules["betse.science.cells"]
    assert "FailDuringDefinition" not in error.modules["betse.science.cells"]
    assert "store_parameters" not in error.modules["betse.science.parameters"]
    assert package.calls == []


@pytest.mark.parametrize("mode", ["missing", "duplicate", "unknown", "escape", "symlink", "call"])
def test_malformed_namespace_groups_refuse_before_definitions(package, mode):
    if mode == "missing":
        package.groups.pop()
    elif mode == "duplicate":
        package.groups.append(copy.deepcopy(package.groups[-1]))
    elif mode == "unknown":
        package.groups.append(("betse/science/foreign.py", ast.parse("x=1").body))
    elif mode == "escape":
        package.groups.append(("../betse/science/cells.py", ast.parse("x=1").body))
    elif mode == "symlink":
        path = package.root / "betse/science/cells.py"
        saved = path.with_suffix(".txt")
        path.rename(saved)
        path.symlink_to(saved)
    else:
        append(package, "betse.science.cells", "forbidden_constructor()")
    with pytest.raises(ValueError):
        build(package)
    assert package.calls == []


def test_native_groups_compile_without_original_body_execution():
    groups, sites = source.source_nodes(ROOT)
    codes, requests, metadata = runtime.compile_groups(groups, native_root=ROOT)
    assert len(codes) == len(source.pins_for()) == 25
    assert set(codes) == set(runtime.MODULE_ORDER)
    assert metadata["constructors_methods_rng_decode_or_operators_executed"] is False
    assert ("betse.util.type.numeric.floats", ("PI", "TWO_PI"), 0) in requests[
        "betse.util.math.geometry.polygon.geopoly"
    ]
    for name, record in metadata["modules"].items():
        relative = name.replace(".", "/") + ".py"
        assert record["file_sha256"] == source.pins_for()[relative]
        for function, site in record["sites"].items():
            key = relative + ":" + function
            if key in sites:
                assert site["ast_sha256"] == sites[key]["ast_sha256"]
    assert metadata["modules"]["betse.util.type.numeric.floats"]["definitions"] == [
        "PI",
        "TWO_PI",
    ]


def test_native_import_sites_keep_optional_unprepared_paths_explicit():
    groups, _ = source.source_nodes(ROOT)
    _, requests, metadata = runtime.compile_groups(groups, native_root=ROOT)
    assert ("matplotlib", ("pyplot",), 0) in requests["betse.science.math.mesh"]
    assert ("betse.util.type.call", ("callers",), 0) in requests["betse.exceptions"]
    assert metadata["unsupported_imports"] == [
        "matplotlib optional display branches",
        "betse.util.type.call.callers optional unimplemented-method exception",
    ]
