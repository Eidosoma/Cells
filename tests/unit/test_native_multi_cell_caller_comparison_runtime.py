"""Synthetic file/maps provenance only; never import scientific dependencies."""

import copy
import hashlib
import importlib.abc
import json
import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from validation.betse import native_multi_cell_caller_comparison_runtime as runtime


@pytest.fixture(autouse=True)
def deny_science():
    attempts = []

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".", 1)[0] in {"numpy", "scipy", "PIL", "cells", "betse", "jax"}:
                attempts.append(fullname)
                raise AssertionError("Scientific import forbidden: " + fullname)

    block = Block()
    sys.meta_path.insert(0, block)
    try:
        yield
    finally:
        sys.meta_path.remove(block)
    assert not attempts


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    site, overlay, source = [tmp_path / name for name in ("site", "overlay", "source")]
    for path in (site, overlay, source):
        path.mkdir()
    for name, parent in (("numpy", site), ("scipy", site), ("PIL", overlay)):
        root = parent / name
        root.mkdir()
        (root / "__init__.py").write_text("raise AssertionError('package execution forbidden')\n")
        (root / "implementation.py").write_text("# synthetic package producer\n")
        distribution = "pillow" if name == "PIL" else name
        libs = parent / (distribution + ".libs")
        libs.mkdir()
        (libs / "libsynthetic.so").write_bytes(b"synthetic library: never load")
        info = parent / (distribution + "-0.0.dist-info")
        info.mkdir()
        (info / "METADATA").write_text("Name: " + distribution + "\nVersion: 0.0\n")
    producer = source / "validation" / "producer.py"
    producer.parent.mkdir()
    producer.write_text("# frozen synthetic source\n")
    (source / "SNAPSHOT.json").write_text(
        json.dumps(
            dict(
                files={
                    "validation/producer.py": dict(
                        sha256=hashlib.sha256(producer.read_bytes()).hexdigest()
                    )
                }
            )
        )
    )
    monkeypatch.setattr(runtime, "sysconfig", SimpleNamespace(get_path=lambda key: str(site)))
    declaration = runtime.prepare_inventory([str(overlay)])
    for key in runtime.THREAD_VARIABLES:
        monkeypatch.setenv(key, "1")
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    monkeypatch.setenv("PYTHONNOUSERSITE", "1")
    monkeypatch.setenv("PYTHONPYCACHEPREFIX", str(source / ".unused-bytecode-cache"))
    return SimpleNamespace(
        site=site, overlay=overlay, source=source, producer=producer, declaration=declaration
    )


def file_module(path, identity=1):
    return dict(kind="file", file=runtime._pin(path), object_id=identity, origin=str(path))


def observations(sandbox):
    modules = {
        name: file_module(Path(row["origin"]), i + 1)
        for i, (name, row) in enumerate(sandbox.declaration["packages"].items())
    }
    modules["validation.producer"] = file_module(sandbox.producer, 5)
    modules["validation"] = dict(
        kind="namespace", object_id=6, origin=None, paths=[str(sandbox.source / "validation")]
    )
    system = sandbox.source.parent / "libsystem.so"
    system.write_bytes(b"system baseline, never load")
    return dict(modules=modules, mapped_libraries=[runtime._pin(system)])


def setup_worker(sandbox, monkeypatch):
    observed = observations(sandbox)
    calls = []
    monkeypatch.setattr(runtime, "_modules", lambda: copy.deepcopy(observed["modules"]))
    monkeypatch.setattr(runtime, "_observe", lambda: copy.deepcopy(observed))
    monkeypatch.setattr(runtime, "importlib", SimpleNamespace(import_module=calls.append))
    before = runtime.preflight(sandbox.declaration, sandbox.source)
    assert calls == list(runtime.IMPORTS)
    assert before["native_execution_attempts"] == before["scientific_api_calls"] == 0
    return observed, before


def test_prepare_does_not_import_and_pins_selected_overlay_packages_and_libraries(sandbox):
    declaration = sandbox.declaration
    assert list(declaration["packages"]) == list(runtime.PACKAGES)
    assert declaration["packages"]["PIL"]["root"] == str(sandbox.overlay / "PIL")
    assert len(declaration["files"]) == 12
    assert len({row["path"] for row in declaration["files"]}) == 12
    assert all(row["sha256"] == runtime._pin(row["path"])["sha256"] for row in declaration["files"])
    assert sum(len(row["bundled_library_roots"]) for row in declaration["packages"].values()) == 3
    runtime.verify_inventory(declaration)


@pytest.mark.parametrize("change", ["edit", "delete", "new_file", "new_library", "metadata"])
def test_verify_refuses_changed_or_added_prospective_producers(sandbox, change):
    path = sandbox.site / "numpy" / "implementation.py"
    if change == "edit":
        path.write_text("# changed\n")
    elif change == "delete":
        path.unlink()
    elif change == "new_file":
        (path.parent / "extra.py").write_text("# new importable file\n")
    elif change == "new_library":
        (sandbox.site / "numpy.libs" / "extra.so").write_bytes(b"new")
    else:
        (sandbox.site / "numpy-0.0.dist-info" / "METADATA").write_text("changed metadata")
    with pytest.raises(ValueError, match="differs"):
        runtime.verify_inventory(sandbox.declaration)


def test_verify_refuses_new_package_shadow(sandbox):
    (sandbox.overlay / "numpy").mkdir()
    (sandbox.overlay / "numpy" / "__init__.py").write_text("raise AssertionError('never import')")
    with pytest.raises(ValueError, match="differs"):
        runtime.verify_inventory(sandbox.declaration)


def test_prepare_missing_dependency(sandbox):
    (sandbox.overlay / "PIL" / "__init__.py").unlink()
    with pytest.raises(ValueError, match="Missing declared runtime package"):
        runtime.prepare_inventory([str(sandbox.overlay)])


def test_package_symlink_is_not_followed(sandbox):
    (sandbox.site / "numpy" / "external.py").symlink_to(sandbox.producer)
    with pytest.raises(ValueError, match="Linked runtime package entry"):
        runtime.prepare_inventory([str(sandbox.overlay)])


@pytest.mark.parametrize("limit", ["MAX_FILES", "MAX_BYTES", "MAX_FILE_BYTES"])
def test_declared_inventory_bounds(sandbox, monkeypatch, limit):
    monkeypatch.setattr(runtime, limit, 1)
    with pytest.raises(ValueError, match="bound|limits"):
        runtime.prepare_inventory([str(sandbox.overlay)])


def test_cache_files_are_excluded_and_worker_prefix_must_be_unused(sandbox):
    cache = sandbox.site / "numpy" / "__pycache__"
    cache.mkdir()
    (cache / "unused.pyc").write_bytes(b"not executed")
    runtime.verify_inventory(sandbox.declaration)
    (sandbox.source / ".unused-bytecode-cache").mkdir()
    with pytest.raises(ValueError, match="unused"):
        runtime._startup(sandbox.source)


def test_loader_environment_binding(sandbox, monkeypatch):
    monkeypatch.setenv("LD_PRELOAD", "changed-unexecuted-loader-value")
    with pytest.raises(ValueError, match="differs"):
        runtime.verify_inventory(sandbox.declaration)


def test_successful_synthetic_preflight_and_finish(sandbox, monkeypatch):
    observed, before = setup_worker(sandbox, monkeypatch)
    after = runtime.finish(sandbox.declaration, sandbox.source, before)
    assert after["status"] == "bound_after_source"
    assert after["observation"] == observed
    assert after["new_module_names"] == []
    assert after["scientific_acceptance"] is False
    assert before["limits"] and after["limits"] == before["limits"]


def mmap_worker(sandbox, monkeypatch):
    observed = observations(sandbox)
    extension = sandbox.source.parent / "mmap.synthetic.so"
    extension.write_bytes(b"synthetic system extension, never loaded")
    imports = []

    def preload(name):
        imports.append(name)
        if name == "mmap":
            observed["modules"][name] = file_module(extension, 101)
            observed["mapped_libraries"].append(runtime._pin(extension))

    monkeypatch.setattr(runtime, "_observe", lambda: copy.deepcopy(observed))
    monkeypatch.setattr(runtime, "importlib", SimpleNamespace(import_module=preload))
    before = runtime.preflight(sandbox.declaration, sandbox.source)
    assert imports.count("mmap") == 1
    assert "mmap" in sandbox.declaration["imports"]
    assert "mmap" not in before["before_imports"]["modules"]
    assert before["observation"]["modules"]["mmap"] == file_module(extension, 101)
    assert runtime._pin(extension) in before["observation"]["mapped_libraries"]
    return observed, before, extension


def test_lazy_image_system_dependency_is_bound_before_source_without_mapping(sandbox, monkeypatch):
    observed, before, _ = mmap_worker(sandbox, monkeypatch)
    source, _, source_files = runtime._source_pins(sandbox.source)
    # The same late import/mapping is still refused against the old baseline.
    with pytest.raises(ValueError, match="New unbound Python producer after source: mmap"):
        runtime._check_modules(
            observed, sandbox.declaration, source, source_files, before["before_imports"]
        )
    with pytest.raises(ValueError, match="New or changed system library after source"):
        runtime._check_maps(observed, sandbox.declaration, before["before_imports"])
    after = runtime.finish(sandbox.declaration, sandbox.source, before)
    assert after["status"] == "bound_after_source"
    assert after["new_module_names"] == []
    assert after["scientific_acceptance"] is False


@pytest.mark.parametrize("change", ["module_identity", "module_bytes", "mapped_bytes", "other"])
def test_preloaded_system_dependency_keeps_strict_finish_checks(sandbox, monkeypatch, change):
    observed, before, extension = mmap_worker(sandbox, monkeypatch)
    if change == "module_identity":
        observed["modules"]["mmap"]["object_id"] += 1
    elif change == "module_bytes":
        extension.write_bytes(b"changed extension bytes")
        observed["modules"]["mmap"] = file_module(extension, 101)
    elif change == "mapped_bytes":
        observed["mapped_libraries"][-1]["sha256"] = "0" * 64
    else:
        path = extension.with_name("unrelated.py")
        path.write_text("# unbound producer\n")
        observed["modules"]["unrelated"] = file_module(path, 102)
    with pytest.raises(runtime.RuntimeInventoryError) as caught:
        runtime.finish(sandbox.declaration, sandbox.source, before)
    assert caught.value.partial["observation"] == observed
    assert caught.value.partial["status"] == "refused"


def test_system_dependency_import_failure_retains_before_source_attempt(sandbox, monkeypatch):
    observed = observations(sandbox)
    primary = ImportError("synthetic mmap load failure")

    def preload(name):
        if name == "mmap":
            raise primary

    monkeypatch.setattr(runtime, "_observe", lambda: copy.deepcopy(observed))
    monkeypatch.setattr(runtime, "importlib", SimpleNamespace(import_module=preload))
    with pytest.raises(runtime.RuntimeInventoryError) as caught:
        runtime.preflight(sandbox.declaration, sandbox.source)
    assert caught.value.__cause__ is primary
    assert caught.value.partial["imports_attempted"][-1] == "mmap"
    assert caught.value.partial["native_execution_attempts"] == 0
    assert caught.value.partial["before_imports"] == observed
    assert caught.value.partial["failure_observation"] == observed


def test_prospectively_bound_late_package_module_and_library(sandbox, monkeypatch):
    observed, before = setup_worker(sandbox, monkeypatch)
    observed["modules"]["numpy.implementation"] = file_module(
        sandbox.site / "numpy" / "implementation.py", 10
    )
    observed["mapped_libraries"].append(
        runtime._pin(sandbox.site / "numpy.libs" / "libsynthetic.so")
    )
    after = runtime.finish(sandbox.declaration, sandbox.source, before)
    assert after["new_module_names"] == ["numpy.implementation"]


def namespace_observation(sandbox):
    directory = sandbox.site / "scipy" / "_external" / "packaging_version"
    directory.mkdir(parents=True)
    (directory / "version.py").write_text("# inventoried, never executed\n")
    sandbox.declaration = runtime.prepare_inventory([str(sandbox.overlay)])
    observed = observations(sandbox)
    for index, (name, path) in enumerate(
        (("scipy._external", directory.parent), ("scipy._external.packaging_version", directory))
    ):
        observed["modules"][name] = dict(
            kind="namespace", object_id=70 + index, origin=None, paths=[str(path)]
        )
    return observed


def test_declared_nested_package_namespaces_preflight_and_finish(sandbox, monkeypatch):
    observed = namespace_observation(sandbox)
    monkeypatch.setattr(runtime, "_modules", lambda: copy.deepcopy(observed["modules"]))
    monkeypatch.setattr(runtime, "_observe", lambda: copy.deepcopy(observed))
    calls = []
    monkeypatch.setattr(runtime, "importlib", SimpleNamespace(import_module=calls.append))
    before = runtime.preflight(sandbox.declaration, sandbox.source)
    assert calls == list(runtime.IMPORTS)
    assert before["native_execution_attempts"] == before["scientific_api_calls"] == 0
    assert (
        runtime.finish(sandbox.declaration, sandbox.source, before)["status"]
        == "bound_after_source"
    )
    assert sandbox.declaration["namespace_policy"] == runtime.NAMESPACE_POLICY


def test_late_namespace_uses_prospectively_bound_directory(sandbox, monkeypatch):
    namespaces = namespace_observation(sandbox)["modules"]
    observed, before = setup_worker(sandbox, monkeypatch)
    observed["modules"]["scipy._external"] = namespaces["scipy._external"]
    assert runtime.finish(sandbox.declaration, sandbox.source, before)["new_module_names"] == [
        "scipy._external"
    ]


@pytest.mark.parametrize(
    "change",
    [
        "opaque",
        "origin",
        "empty",
        "multiple",
        "foreign",
        "wrong_name",
        "unlisted",
        "symlink",
        "initializer",
        "extension_initializer",
        "root",
    ],
)
def test_numerical_namespace_rejects_unowned_paths_and_kinds(sandbox, change):
    observed = namespace_observation(sandbox)
    name = "scipy._external"
    row = observed["modules"][name]
    directory = Path(row["paths"][0])
    if change == "opaque":
        row["kind"] = "opaque"
    elif change == "origin":
        row["origin"] = "generated"
    elif change == "empty":
        row["paths"] = []
    elif change == "multiple":
        row["paths"].append(str(directory))
    elif change == "foreign":
        row["paths"] = [str(sandbox.overlay)]
    elif change == "wrong_name":
        observed["modules"]["scipy.somewhere_else"] = observed["modules"].pop(name)
    elif change == "unlisted":
        unknown = directory.parent / "new_namespace"
        unknown.mkdir()
        row["paths"] = [str(unknown)]
        observed["modules"]["scipy.new_namespace"] = observed["modules"].pop(name)
    elif change == "symlink":
        actual = directory.with_name("retained_namespace")
        directory.rename(actual)
        directory.symlink_to(actual, target_is_directory=True)
    elif change in ("initializer", "extension_initializer"):
        suffix = ".py" if change == "initializer" else ".so"
        (directory / ("__init__" + suffix)).write_text("raise AssertionError('never import')\n")
    else:
        observed["modules"]["scipy"] = dict(row, paths=[str(directory.parent)])
    source, _, source_files = runtime._source_pins(sandbox.source)
    with pytest.raises(ValueError, match="Unbound numerical package"):
        runtime._check_modules(observed, sandbox.declaration, source, source_files)


def test_namespace_identity_drift_after_source_refuses(sandbox, monkeypatch):
    observed = namespace_observation(sandbox)
    monkeypatch.setattr(runtime, "_modules", lambda: copy.deepcopy(observed["modules"]))
    monkeypatch.setattr(runtime, "_observe", lambda: copy.deepcopy(observed))
    monkeypatch.setattr(runtime, "importlib", SimpleNamespace(import_module=lambda name: None))
    before = runtime.preflight(sandbox.declaration, sandbox.source)
    observed["modules"]["scipy._external"]["object_id"] += 1
    with pytest.raises(runtime.RuntimeInventoryError, match="removed or changed"):
        runtime.finish(sandbox.declaration, sandbox.source, before)


def test_actual_namespace_module_record_retains_paths(sandbox, monkeypatch):
    observed = namespace_observation(sandbox)
    namespace = ModuleType("scipy._external")
    namespace.__spec__ = SimpleNamespace(origin=None)
    namespace.__path__ = list(observed["modules"]["scipy._external"]["paths"])
    monkeypatch.setattr(runtime, "sys", SimpleNamespace(modules={namespace.__name__: namespace}))
    assert runtime._modules() == {
        namespace.__name__: dict(
            kind="namespace", object_id=id(namespace), origin=None, paths=namespace.__path__
        )
    }


@pytest.mark.parametrize(
    "change",
    [
        "foreign_package",
        "new_python",
        "new_system_library",
        "module_removed",
        "module_replaced",
        "opaque",
        "forbidden",
    ],
)
def test_finish_retains_observation_and_refuses_unbound_or_changed_producers(
    sandbox, monkeypatch, change
):
    observed, before = setup_worker(sandbox, monkeypatch)
    path = sandbox.source.parent / "outside.py"
    path.write_text("# synthetic foreign producer\n")
    if change == "foreign_package":
        observed["modules"]["numpy.extra"] = file_module(path, 20)
    elif change == "new_python":
        observed["modules"]["outside"] = file_module(path, 20)
    elif change == "new_system_library":
        library = path.with_suffix(".so")
        library.write_bytes(b"not loaded")
        observed["mapped_libraries"].append(runtime._pin(library))
    elif change == "module_removed":
        del observed["modules"]["numpy"]
    elif change == "module_replaced":
        observed["modules"]["numpy"]["object_id"] += 100
    elif change == "opaque":
        observed["modules"]["new_generated"] = dict(
            kind="opaque", origin=None, paths=[], object_id=30
        )
    else:
        observed["modules"]["betse.science"] = file_module(path, 20)
    with pytest.raises(runtime.RuntimeInventoryError) as raised:
        runtime.finish(sandbox.declaration, sandbox.source, before)
    assert raised.value.partial["observation"] == observed
    assert raised.value.partial["status"] == "refused"
    assert raised.value.__cause__ is not None


def test_unchanged_existing_opaque_module_is_explicit_gap(sandbox, monkeypatch):
    observed = observations(sandbox)
    observed["modules"]["generated_extension_state"] = dict(
        kind="opaque", object_id=12, origin=None, paths=[]
    )
    monkeypatch.setattr(runtime, "_modules", lambda: observed["modules"])
    monkeypatch.setattr(runtime, "_observe", lambda: observed)
    monkeypatch.setattr(runtime, "importlib", SimpleNamespace(import_module=lambda name: None))
    before = runtime.preflight(sandbox.declaration, sandbox.source)
    assert before["opaque_module_names"] == ["generated_extension_state"]
    assert (
        runtime.finish(sandbox.declaration, sandbox.source, before)["status"]
        == "bound_after_source"
    )


def test_import_refusal_retains_attempt_and_primary_cause(sandbox, monkeypatch):
    observed = observations(sandbox)
    monkeypatch.setattr(runtime, "_modules", lambda: observed["modules"])
    monkeypatch.setattr(runtime, "_observe", lambda: observed)
    cause = ImportError("synthetic dependency refusal")

    def refuse(name):
        raise cause

    monkeypatch.setattr(runtime, "importlib", SimpleNamespace(import_module=refuse))
    with pytest.raises(runtime.RuntimeInventoryError) as raised:
        runtime.preflight(sandbox.declaration, sandbox.source)
    assert raised.value.__cause__ is cause
    assert raised.value.partial["imports_attempted"] == ["numpy"]
    assert raised.value.partial["native_execution_attempts"] == 0
    assert raised.value.partial["before_imports"] == observed
    assert raised.value.partial["failure_observation"] == observed


def test_failure_metadata_capture_error_does_not_replace_import_cause(sandbox, monkeypatch):
    observed = observations(sandbox)
    captures = []

    def observe():
        captures.append(1)
        if len(captures) == 2:
            raise OSError("synthetic metadata capture failure")
        return observed

    cause = ImportError("original synthetic import failure")

    def refuse(name):
        raise cause

    monkeypatch.setattr(runtime, "_observe", observe)
    monkeypatch.setattr(runtime, "importlib", SimpleNamespace(import_module=refuse))
    with pytest.raises(runtime.RuntimeInventoryError) as raised:
        runtime.preflight(sandbox.declaration, sandbox.source)
    assert raised.value.__cause__ is cause
    assert raised.value.partial["failure_observation_error"] == dict(
        type="OSError", message="synthetic metadata capture failure"
    )


@pytest.mark.parametrize("change", ["seal", "declaration", "snapshot", "missing_before"])
def test_finish_association_guards(sandbox, monkeypatch, change):
    _, before = setup_worker(sandbox, monkeypatch)
    if change == "seal":
        before["imports_attempted"].append("foreign")
    elif change == "declaration":
        before["declaration_sha256"] = "0" * 64
        before["receipt_sha256"] = runtime._seal(
            {k: v for k, v in before.items() if k != "receipt_sha256"}
        )
    elif change == "snapshot":
        (sandbox.source / "SNAPSHOT.json").write_text('{"files": {}}')
    else:
        before = None
    with pytest.raises(runtime.RuntimeInventoryError):
        runtime.finish(sandbox.declaration, sandbox.source, before)


@pytest.mark.parametrize("change", ["foreign_validation", "unlisted_source", "wrong_namespace"])
def test_source_producer_guards(sandbox, monkeypatch, change):
    observed, before = setup_worker(sandbox, monkeypatch)
    if change == "foreign_validation":
        observed["modules"]["validation.extra"] = file_module(
            sandbox.site / "numpy" / "implementation.py", 23
        )
    elif change == "unlisted_source":
        path = sandbox.source / "unlisted.py"
        path.write_text("# not in source manifest")
        observed["modules"]["helper"] = file_module(path, 23)
    else:
        observed["modules"]["validation"]["paths"] = [str(sandbox.site)]
    with pytest.raises(runtime.RuntimeInventoryError, match="source|namespace"):
        runtime.finish(sandbox.declaration, sandbox.source, before)


@pytest.mark.parametrize(
    "key", ["OPENBLAS_NUM_THREADS", "PYTHONDONTWRITEBYTECODE", "PYTHONNOUSERSITE"]
)
def test_worker_policy_not_preparation_pythonpath(sandbox, monkeypatch, key):
    monkeypatch.setenv("PYTHONPATH", "/deliberately/different/preparation/path")
    runtime.verify_inventory(sandbox.declaration)
    monkeypatch.setenv(key, "0")
    with pytest.raises(runtime.RuntimeInventoryError, match="controlled"):
        runtime.preflight(sandbox.declaration, sandbox.source)


def test_maps_parser_pins_unique_libraries_and_executable_with_escaped_path(sandbox):
    library = sandbox.source.parent / "lib with space.so"
    library.write_bytes(b"synthetic mapped file")
    executable = sandbox.source.parent / "python-synthetic"
    executable.write_bytes(b"synthetic executable")
    escaped = str(library).replace(" ", r"\040")
    library_stat, executable_stat = library.stat(), executable.stat()
    library_id = (
        f"{os.major(library_stat.st_dev):x}:{os.minor(library_stat.st_dev):x} "
        f"{library_stat.st_ino} "
    )
    executable_id = (
        f"{os.major(executable_stat.st_dev):x}:{os.minor(executable_stat.st_dev):x} "
        f"{executable_stat.st_ino} "
    )
    text = "\n".join(
        (
            "0000-1000 r-xp 00000000 " + library_id + escaped,
            "1000-2000 r--p 00000000 " + library_id + escaped,
            "2000-3000 r-xp 00000000 " + executable_id + str(executable),
            "3000-4000 rw-p 00000000 00:00 0 [heap]",
        )
    )
    assert runtime._mapped_libraries(text) == [
        runtime._pin(path) for path in sorted((library, executable))
    ]


def test_mapped_file_identity_mismatch_refused(sandbox):
    library = sandbox.site / "numpy.libs" / "libsynthetic.so"
    stat = library.stat()
    wrong = f"{os.major(stat.st_dev):x}:{os.minor(stat.st_dev):x} {stat.st_ino + 1} "
    with pytest.raises(ValueError, match="no longer identifies"):
        runtime._mapped_libraries("0000-1000 r-xp 00000000 " + wrong + str(library))


@pytest.mark.parametrize("problem", ["deleted", "missing", "malformed", "too_large"])
def test_maps_refusals(sandbox, monkeypatch, problem):
    path = sandbox.source.parent / "missing.so"
    text = "0000-1000 r-xp 00000000 00:01 1 " + str(path)
    if problem == "deleted":
        text += " (deleted)"
    elif problem == "malformed":
        text = "malformed"
    elif problem == "too_large":
        monkeypatch.setattr(runtime, "MAX_MAP_BYTES", 1)
    with pytest.raises((ValueError, FileNotFoundError)):
        runtime._mapped_libraries(text)


def test_observed_module_origins_forbidden_cache_and_file_spec_mismatch(sandbox, monkeypatch):
    module = ModuleType("numpy")
    module.__file__ = str(sandbox.site / "numpy" / "__init__.py")
    module.__spec__ = SimpleNamespace(origin=module.__file__)
    monkeypatch.setattr(runtime, "sys", SimpleNamespace(modules={"numpy": module}))
    assert runtime._modules()["numpy"]["file"] == runtime._pin(module.__file__)
    module.__spec__.origin = str(sandbox.producer)
    with pytest.raises(runtime.RuntimeInventoryError, match="origin mismatch"):
        runtime._modules()
    runtime.sys.modules = {"betse": ModuleType("betse")}
    with pytest.raises(runtime.RuntimeInventoryError, match="Forbidden cached"):
        runtime._modules()
