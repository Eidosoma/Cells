"""Real standard-library origin metadata and synthetic saved-runtime controls."""

import copy
import hashlib
import json
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

from validation.betse import native_rng_runtime as runtime
from validation.betse import native_seed_rng_runtime_software as software


@pytest.fixture(autouse=True)
def blocked(tmp_path):
    if os.environ.get(software.RELEASE) != "1":
        pytest.skip("Explicit frozen RNG metadata controls required")
    with software.blocked(tmp_path):
        yield


def pin(path):
    path = Path(path).resolve()
    with path.open("rb") as stream:
        return dict(path=str(path), sha256=hashlib.file_digest(stream, "sha256").hexdigest())


@pytest.fixture
def actual_metadata(tmp_path, monkeypatch):
    # No Random is constructed and no state getter/setter or draw is invoked.
    import random

    files = {"random": pin(random.__file__)}
    for name in runtime.MODULES:
        if name in ("random", "_random"):
            continue
        path = tmp_path / (name + ".py")
        path.write_text("# inert metadata file\n")
        module = ModuleType(name)
        module.__file__ = str(path)
        module.__version__ = "synthetic-no-NumPy-execution"
        monkeypatch.setitem(sys.modules, name, module)
        files[name] = pin(path)
    version = ".".join(str(value) for value in sys.version_info[:3])
    return dict(
        python=version,
        executable=pin(sys.executable),
        loaded_files=files,
        modules_without_files=["_random"],
    )


def test_rng_runtime_actual_builtin_metadata_never_calls_state_or_draw(actual_metadata):
    attempted = []
    before = sys.getprofile()

    def observer(frame, event, arg):
        if event == "c_call" and getattr(arg, "__name__", None) in runtime.METHODS:
            owner = getattr(arg, "__self__", None)
            if type(owner).__module__ in ("random", "_random"):
                attempted.append(arg)
                raise AssertionError("No RNG state or draw in metadata observation")
        if before is not None:
            before(frame, event, arg)

    sys.setprofile(observer)
    try:
        result = runtime._binding(actual_metadata)
    finally:
        sys.setprofile(before)
    assert attempted == []
    assert result["kind"] == runtime.KIND
    assert set(result["files"]) == set(runtime.MODULES) - {"_random"}
    assert set(result["builtins"]) == {"_random"}
    assert (
        result["builtins"]["_random"]["executable_sha256"]
        == actual_metadata["executable"]["sha256"]
    )
    assert result["interpreter"]["builtin_module_names"] == list(sys.builtin_module_names)
    runtime.validate(json.loads(json.dumps(result)))


@pytest.mark.parametrize(
    "mutation",
    (
        "missing",
        "duplicate",
        "misfiled",
        "file_origin",
        "module_type",
        "module_name",
        "spec",
        "origin",
        "loader",
        "module_loader",
        "location",
        "cached",
        "package",
        "initializing",
        "native_type",
        "receiver_link",
        "not_builtin",
    ),
)
def test_rng_runtime_actual_associations_refuse_before_any_state_call(
    actual_metadata, monkeypatch, mutation
):
    module = sys.modules["_random"]
    spec = module.__spec__
    if mutation == "missing":
        actual_metadata["modules_without_files"] = []
    elif mutation == "duplicate":
        actual_metadata["modules_without_files"] *= 2
    elif mutation == "misfiled":
        actual_metadata["loaded_files"]["_random"] = actual_metadata["executable"]
    elif mutation == "file_origin":
        monkeypatch.setattr(module, "__file__", "/fabricated/_random.so", raising=False)
    elif mutation == "module_type":
        monkeypatch.setitem(sys.modules, "_random", object())
    elif mutation == "module_name":
        monkeypatch.setattr(module, "__name__", "wrong")
    elif mutation == "spec":
        monkeypatch.setattr(module, "__spec__", None)
    elif mutation in ("origin", "loader", "cached", "package", "initializing"):
        key, value = {
            "origin": ("origin", "frozen"),
            "loader": ("loader", object()),
            "cached": ("cached", "fabricated.pyc"),
            "package": ("submodule_search_locations", []),
            "initializing": ("_initializing", True),
        }[mutation]
        monkeypatch.setattr(spec, key, value, raising=False)
    elif mutation == "module_loader":
        monkeypatch.setattr(module, "__loader__", object())
    elif mutation == "location":
        monkeypatch.setattr(spec, "has_location", True)
    elif mutation == "native_type":
        monkeypatch.setattr(module, "Random", type("Random", (), {}))
    elif mutation == "receiver_link":
        monkeypatch.setattr(sys.modules["random"], "_random", object())
    else:
        monkeypatch.setattr(runtime._imp, "is_builtin", lambda name: 0)
    with pytest.raises(ValueError):
        runtime._binding(actual_metadata)


def test_rng_runtime_file_backed_schema_is_retained(actual_metadata, monkeypatch, tmp_path):
    path = tmp_path / "_random.extension"
    path.write_bytes(b"inert extension metadata, never loaded")
    module = ModuleType("_random")
    module.__file__ = str(path)
    monkeypatch.setitem(sys.modules, "_random", module)
    actual_metadata["loaded_files"]["_random"] = pin(path)
    actual_metadata["modules_without_files"] = []
    result = runtime._binding(actual_metadata)
    assert set(result) == {"python", "executable", "numpy_version", "files"}
    assert set(result["files"]) == set(runtime.MODULES)
    runtime.validate(result)


@pytest.mark.parametrize("falsey", (False, True))
def test_rng_runtime_metadata_failure_keeps_exact_primary_and_cause(
    actual_metadata, monkeypatch, falsey
):
    class Falsey(ValueError):
        def __bool__(self):
            return False

    primary = Falsey("metadata rejected") if falsey else ValueError("metadata rejected")
    cause = OSError("original cause")
    primary.__cause__ = cause

    def rejected(name):
        raise primary

    monkeypatch.setattr(runtime._imp, "is_builtin", rejected)
    with pytest.raises(ValueError) as caught:
        runtime._binding(actual_metadata)
    assert caught.value is primary and caught.value.__cause__ is cause


@pytest.mark.parametrize(
    "mutation",
    (
        "kind",
        "missing",
        "overlap",
        "extra",
        "executable",
        "loader",
        "boolean",
        "version",
        "cache_tag",
        "roster",
        "duplicate",
    ),
)
def test_rng_runtime_saved_schema_is_closed(actual_metadata, mutation):
    value = runtime._binding(actual_metadata)
    row = value["builtins"]["_random"]
    if mutation == "kind":
        value["kind"] = "unknown"
    elif mutation == "missing":
        del value["builtins"]["_random"]
    elif mutation == "overlap":
        value["files"]["_random"] = value["executable"]
    elif mutation == "extra":
        value["builtins"]["other"] = row
    elif mutation == "executable":
        row["executable_sha256"] = "0" * 64
    elif mutation == "loader":
        row["loader"] = "foreign.BuiltinImporter"
    elif mutation == "boolean":
        row["has_location"] = 0
    elif mutation == "version":
        value["interpreter"]["hexversion"] += 256
    elif mutation == "cache_tag":
        value["interpreter"]["cache_tag"] = "cpython-999"
    elif mutation == "roster":
        value["interpreter"]["builtin_module_names"].remove("_random")
    else:
        value["interpreter"]["builtin_module_names"].append("_random")
    with pytest.raises(ValueError):
        runtime.validate(value)


@pytest.mark.parametrize(
    "mutation", (None, "missing", "misfiled", "duplicate", "python", "executable")
)
def test_rng_runtime_saved_reader_checks_actual_inventory(actual_metadata, mutation):
    from validation.betse.native_seed_demo_report import Reader

    value = runtime._binding(actual_metadata)
    final = copy.deepcopy(actual_metadata)
    if mutation == "missing":
        final["modules_without_files"] = []
    elif mutation == "misfiled":
        final["loaded_files"]["_random"] = value["executable"]
    elif mutation == "duplicate":
        final["modules_without_files"] *= 2
    elif mutation == "python":
        final["python"] = "0.0.0"
    elif mutation == "executable":
        final["executable"]["sha256"] = "0" * 64
    roots = {str(Path(row["path"]).parent) for row in value["files"].values()}

    def check():
        runtime.validate_saved(
            Reader(),
            value,
            executable=value["executable"],
            runtime_roots=roots,
            final=final,
            completed=True,
        )

    if mutation is None:
        check()
    else:
        with pytest.raises(ValueError):
            check()
