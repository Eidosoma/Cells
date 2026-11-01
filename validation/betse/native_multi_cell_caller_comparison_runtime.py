"""Bounded runtime provenance for one independent multi-cell reference worker.

Preparation reads package files without importing them. Only ``preflight`` may
import scientific dependencies, inside the caller's released resource guard;
it invokes no array, image, RNG, mesh or linear-algebra API. Import initialization
is not certified as side-effect free. This inventory is provenance, not a proof
of numerical independence or in-memory code integrity.
"""

import hashlib
import importlib
import json
import os
import re
import sys
import sysconfig
from importlib.machinery import PathFinder, all_suffixes
from pathlib import Path

KIND = "cells.multi_cell_reference_runtime@1"
RECEIPT_KIND = "cells.multi_cell_reference_runtime_observation@1"
PACKAGES = ("numpy", "scipy", "PIL")
IMPORTS = (
    "numpy",
    "numpy.random",
    "numpy.linalg",
    "scipy.interpolate",
    "scipy.spatial",
    "PIL.Image",
    "PIL.BmpImagePlugin",
    "PIL.GifImagePlugin",
    "PIL.JpegImagePlugin",
    "PIL.PpmImagePlugin",
    "PIL.PngImagePlugin",
    # Pillow's file-backed image path imports this lazily. Bind its module and
    # system extension in the before-source baseline, without mapping a file.
    "mmap",
)
FORBIDDEN = frozenset(("cells", "betse", "jax", "jaxlib"))
MAX_FILES = 50000
MAX_BYTES = 2 * 1024**3
MAX_FILE_BYTES = 128 * 1024**2
MAX_MAP_BYTES = 4 * 1024**2
MAX_MODULES = 20000
THREAD_VARIABLES = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
)
LOADER_VARIABLES = ("LD_LIBRARY_PATH", "LD_PRELOAD", "LD_AUDIT")
NAMESPACE_POLICY = "exact_single_unlinked_package_subdirectory_with_declared_files_no_initializer"


class RuntimeInventoryError(ValueError):
    """Refusal with the successfully retained metadata, never science credit."""

    def __init__(self, message, partial=None):
        super().__init__(message)
        self.partial = {} if partial is None else partial


def _pin(path):
    path = Path(path).resolve(strict=True)
    if not path.is_file():
        raise ValueError("Require a regular runtime file: " + str(path))
    before = path.stat()
    if before.st_size > MAX_FILE_BYTES:
        raise ValueError("Runtime file exceeds the declared byte bound")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024**2), b""):
            digest.update(block)
    after = path.stat()
    keys = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if any(getattr(before, key) != getattr(after, key) for key in keys):
        raise ValueError("Runtime file changed while hashing: " + str(path))
    return dict(path=str(path), sha256=digest.hexdigest(), size_bytes=after.st_size)


def _seal(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()
    ).hexdigest()


def _paths(runtime_paths):
    if not isinstance(runtime_paths, (list, tuple)) or any(
        not isinstance(path, str) for path in runtime_paths
    ):
        raise ValueError("Runtime overlays must be an explicit sequence of paths")
    roots = []
    for raw in (*runtime_paths, sysconfig.get_path("purelib"), sysconfig.get_path("platlib")):
        path = Path(raw)
        if not path.is_absolute() or path.is_symlink() or not path.is_dir():
            raise ValueError("Require an absolute regular runtime search directory")
        resolved = str(path.resolve(strict=True))
        if resolved not in roots:
            roots.append(resolved)
    return roots


def _tree(root, files):
    stack = [root]
    while stack:
        directory = stack.pop()
        for path in sorted(directory.iterdir()):
            if path.is_symlink():
                raise ValueError("Linked runtime package entry: " + str(path))
            if path.name == "__pycache__" or path.suffix in (".pyc", ".pyo"):
                continue
            if path.is_dir():
                stack.append(path)
            elif path.is_file():
                if len(files) >= MAX_FILES:
                    raise ValueError("Runtime package inventory exceeds file bound")
                files[str(path)] = _pin(path)
            else:
                raise ValueError("Nonregular runtime package entry: " + str(path))


def prepare_inventory(runtime_paths):
    """Resolve only three explicit package roots; do not execute their code."""
    search = _paths(runtime_paths)
    files, packages = {}, {}
    for name in PACKAGES:
        spec = PathFinder.find_spec(name, search)
        if spec is None or not spec.origin or not spec.submodule_search_locations:
            raise ValueError("Missing declared runtime package: " + name)
        roots = list(spec.submodule_search_locations)
        root = Path(roots[0])
        if len(roots) != 1 or root.is_symlink() or Path(spec.origin) != root / "__init__.py":
            raise ValueError("Unsupported package origin/namespace: " + name)
        root = root.resolve(strict=True)
        if str(root.parent) not in search:
            raise ValueError("Runtime package escaped the declared search roots")
        _tree(root, files)
        distribution = "pillow" if name == "PIL" else name
        libraries, metadata = [], []
        for sibling in sorted(root.parent.iterdir()):
            lower = sibling.name.lower()
            if lower == distribution + ".libs" or (
                lower.startswith(distribution + "-") and lower.endswith(".dist-info")
            ):
                if sibling.is_symlink() or not sibling.is_dir():
                    raise ValueError("Require an ordinary runtime library/metadata directory")
                _tree(sibling, files)
                (libraries if lower.endswith(".libs") else metadata).append(str(sibling))
        packages[name] = dict(
            root=str(root),
            origin=str(root / "__init__.py"),
            bundled_library_roots=libraries,
            metadata_roots=metadata,
        )
    ordered = sorted(files.values(), key=lambda row: row["path"])
    if len(ordered) > MAX_FILES or sum(row["size_bytes"] for row in ordered) > MAX_BYTES:
        raise ValueError("Runtime package inventory exceeds aggregate limits")
    return dict(
        kind=KIND,
        runtime_paths=list(runtime_paths),
        search_paths=search,
        packages=packages,
        files=ordered,
        imports=list(IMPORTS),
        interpreter=_pin(sys.executable),
        interpreter_invocation=str(Path(sys.executable).absolute()),
        python_version=sys.version,
        loader_environment={key: os.environ.get(key) for key in LOADER_VARIABLES},
        limits=dict(files=MAX_FILES, bytes=MAX_BYTES, file_bytes=MAX_FILE_BYTES),
        scope="Declared package bytes; system mapped dependencies bound before source only",
        bytecode_cache_excluded=True,
        namespace_policy=NAMESPACE_POLICY,
        scientific_execution=False,
    )


def verify_inventory(declaration):
    """Detect changed files, added importable files and changed package selection."""
    if not isinstance(declaration, dict) or declaration.get("kind") != KIND:
        raise ValueError("Unknown runtime inventory declaration")
    actual = prepare_inventory(declaration["runtime_paths"])
    if actual != declaration:
        raise ValueError("Runtime inventory differs from its prospective declaration")


def _source_pins(source):
    source = Path(source).resolve(strict=True)
    manifest = source / "SNAPSHOT.json"
    value = json.loads(manifest.read_text())
    pins = {}
    for name, row in value["files"].items():
        path = source / name
        if Path(name).is_absolute() or ".." in Path(name).parts or path.is_symlink():
            raise ValueError("Unsafe frozen source producer")
        if not path.resolve(strict=True).is_relative_to(source):
            raise ValueError("Frozen source producer escaped its snapshot")
        pins[str(path)] = row["sha256"]
    return source, _pin(manifest), pins


def _modules():
    """Pin actual file-backed origins; report generated/opaque entries separately."""
    result = {}
    for name, module in sorted(tuple(sys.modules.items())):
        if name.split(".", 1)[0] in FORBIDDEN:
            raise RuntimeInventoryError("Forbidden cached package: " + name, dict(modules=result))
        if len(result) >= MAX_MODULES:
            raise RuntimeInventoryError("Module inventory exceeds its bound", dict(modules=result))
        if module is None:
            result[name] = dict(kind="negative_import_cache")
            continue
        spec = getattr(module, "__spec__", None)
        origin = getattr(spec, "origin", None)
        filename = getattr(module, "__file__", None)
        row = dict(object_id=id(module), origin=origin)
        if filename:
            pin = _pin(filename)
            if origin not in (None, "built-in", "frozen") and (
                str(Path(origin).resolve(strict=True)) != pin["path"]
            ):
                raise RuntimeInventoryError(
                    "Module file/spec origin mismatch: " + name, dict(modules=result)
                )
            row.update(kind="file", file=pin)
        else:
            paths = list(getattr(module, "__path__", ()))
            row.update(
                kind="builtin_or_frozen"
                if origin in ("built-in", "frozen")
                else "namespace"
                if paths
                else "opaque",
                paths=paths,
            )
        result[name] = row
    return result


def _mapped_libraries(text=None):
    """Read this worker's mappings only, never dlopen or query another process."""
    if text is None:
        text = Path("/proc/self/maps").read_text()
    if len(text.encode()) > MAX_MAP_BYTES:
        raise ValueError("Mapped-library text exceeds the declared bound")
    paths = {}
    for line in text.splitlines():
        parts = line.split(maxsplit=5)
        if len(parts) < 5:
            raise ValueError("Malformed process map row")
        if len(parts) != 6 or not parts[5].startswith("/"):
            continue
        raw = re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), parts[5])
        if ".so" not in Path(raw).name and "x" not in parts[1]:
            continue
        if raw.endswith(" (deleted)"):
            raise ValueError("Deleted mapped library cannot be authenticated")
        path = Path(raw).resolve(strict=True)
        stat = path.stat()
        try:
            major, minor = (int(value, 16) for value in parts[3].split(":"))
            inode = int(parts[4])
        except ValueError as error:
            raise ValueError("Malformed mapped-file identity") from error
        if (os.major(stat.st_dev), os.minor(stat.st_dev), stat.st_ino) != (major, minor, inode):
            raise ValueError("Mapped library pathname no longer identifies its mapped file")
        paths[path] = (stat.st_dev, stat.st_ino)
    pins = []
    for path, identity in sorted(paths.items()):
        pin = _pin(path)
        stat = path.stat()
        if (stat.st_dev, stat.st_ino) != identity:
            raise ValueError("Mapped file changed while its bytes were pinned")
        pins.append(pin)
    return pins


def _observe():
    return dict(modules=_modules(), mapped_libraries=_mapped_libraries())


def _check_package_namespace(name, row, package_root, declared):
    """Bind a fileless package container to its already inventoried directory.

    SciPy uses namespace containers for vendored helpers. They have no source
    file to pin; their exact single search path and contained producers must
    belong to the prospective package inventory. This does not admit generated
    modules, arbitrary search roots or a namespace replacing a regular package.
    """
    parts = name.split(".")[1:]
    expected = package_root.joinpath(*parts)
    if (
        not parts
        or any(not part.isidentifier() for part in parts)
        or row["kind"] != "namespace"
        or row.get("origin") is not None
        or row.get("paths") != [str(expected)]
        or not expected.is_dir()
        or any(path.is_symlink() for path in (expected, *expected.parents))
        or any((expected / ("__init__" + suffix)).exists() for suffix in all_suffixes())
        or not any(Path(path).is_relative_to(expected) for path in declared)
    ):
        raise ValueError("Unbound numerical package namespace: " + name)


def _check_modules(observed, declaration, source, source_files, baseline=None):
    declared = {row["path"]: row for row in declaration["files"]}
    numeric_roots = [Path(row["root"]) for row in declaration["packages"].values()]
    before = {} if baseline is None else baseline["modules"]
    prior_files = {
        row["file"]["path"]: row["file"] for row in before.values() if row["kind"] == "file"
    }
    for name, row in observed["modules"].items():
        root = name.split(".", 1)[0]
        bound_namespace = False
        if root in FORBIDDEN:
            raise ValueError("Forbidden cached package: " + name)
        if root in PACKAGES:
            package_root = Path(declaration["packages"][root]["root"])
            if row["kind"] == "namespace":
                _check_package_namespace(name, row, package_root, declared)
                bound_namespace = True
            elif row["kind"] != "file":
                raise ValueError("Unbound numerical package module: " + name)
            else:
                pin = row["file"]
                if (
                    not Path(pin["path"]).is_relative_to(package_root)
                    or declared.get(pin["path"]) != pin
                ):
                    raise ValueError("Foreign or changed numerical module: " + name)
        if row["kind"] == "file":
            pin, path = row["file"], Path(row["file"]["path"])
            if (
                name == "validation"
                or name.startswith("validation.")
                or path.is_relative_to(source)
            ):
                if source_files.get(str(path)) != pin["sha256"]:
                    raise ValueError("Unbound frozen source producer: " + name)
            elif any(path.is_relative_to(base) for base in numeric_roots):
                if declared.get(str(path)) != pin:
                    raise ValueError("Unlisted numerical package file: " + str(path))
            elif baseline is not None and name not in before and prior_files.get(str(path)) != pin:
                if declared.get(str(path)) != pin:
                    raise ValueError("New unbound Python producer after source: " + name)
        elif name == "validation" or name.startswith("validation."):
            if (
                row["kind"] != "namespace"
                or not row["paths"]
                or any(
                    not Path(path).resolve(strict=True).is_relative_to(source)
                    for path in row["paths"]
                )
            ):
                raise ValueError("Foreign validation namespace: " + name)
        elif (
            baseline is not None
            and name not in before
            and not bound_namespace
            and row["kind"] not in ("builtin_or_frozen", "negative_import_cache")
        ):
            raise ValueError("New opaque/namespace Python producer after source: " + name)
    if baseline is not None:
        for name, row in before.items():
            if observed["modules"].get(name) != row:
                raise ValueError("Previously observed module removed or changed: " + name)


def _check_maps(observed, declaration, baseline=None):
    declared = {row["path"]: row for row in declaration["files"]}
    before = {} if baseline is None else {row["path"]: row for row in baseline["mapped_libraries"]}
    roots = [Path(row["root"]) for row in declaration["packages"].values()]
    roots += [
        Path(path)
        for row in declaration["packages"].values()
        for path in row["bundled_library_roots"]
    ]
    for pin in observed["mapped_libraries"]:
        if any(Path(pin["path"]).is_relative_to(root) for root in roots):
            if declared.get(pin["path"]) != pin:
                raise ValueError("Unbound mapped package library: " + pin["path"])
        elif baseline is not None and before.get(pin["path"]) != pin:
            raise ValueError("New or changed system library after source: " + pin["path"])
    if baseline is not None:
        for pin in before.values():
            if _pin(pin["path"]) != pin:
                raise ValueError("Previously mapped system library changed on disk")


def _startup(source):
    expected = dict(
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONNOUSERSITE="1",
        PYTHONPYCACHEPREFIX=str(source / ".unused-bytecode-cache"),
        **{key: "1" for key in THREAD_VARIABLES},
    )
    if any(os.environ.get(key) != value for key, value in expected.items()):
        raise ValueError("Require the controlled one-thread/no-bytecode worker environment")
    if (source / ".unused-bytecode-cache").exists():
        raise ValueError("Worker bytecode prefix must be unused")
    return expected


def preflight(declaration, source):
    """Released worker only: import dependencies, then pin its system baseline."""
    partial = dict(
        kind=RECEIPT_KIND,
        phase="preflight",
        status="refused",
        imports_attempted=[],
        native_execution_attempts=0,
        scientific_api_calls=0,
    )
    try:
        verify_inventory(declaration)
        source, snapshot, source_files = _source_pins(source)
        partial.update(
            declaration_sha256=_seal(declaration),
            source=str(source),
            snapshot=snapshot,
            startup=_startup(source),
        )
        # An import audit in the runner also catches transient denied imports.
        partial["before_imports"] = _observe()
        _check_modules(partial["before_imports"], declaration, source, source_files)
        for name in IMPORTS:
            partial["imports_attempted"].append(name)
            importlib.import_module(name)
        observed = _observe()
        partial["observation"] = observed
        _check_modules(observed, declaration, source, source_files)
        _check_maps(observed, declaration)
        verify_inventory(declaration)
        partial.update(
            status="bound_before_source",
            opaque_module_names=[
                name for name, row in observed["modules"].items() if row["kind"] == "opaque"
            ],
            limits=[
                "System mapped libraries are first bound in this worker, not the old owned run",
                "Opaque/generated modules have no file proof; their presence is explicit",
                "File hashes do not attest in-memory callables or independently validate numerics",
                "Runner import audit is required for transient forbidden imports",
            ],
        )
        partial["receipt_sha256"] = _seal(partial)
        return partial
    except BaseException as error:
        partial["error"] = dict(type=type(error).__name__, message=str(error))
        if isinstance(error, RuntimeInventoryError):
            partial["partial_observation"] = error.partial
        if "before_imports" in partial and "observation" not in partial:
            try:
                partial["failure_observation"] = _observe()
            except BaseException as capture_error:
                partial["failure_observation_error"] = dict(
                    type=type(capture_error).__name__, message=str(capture_error)
                )
        raise RuntimeInventoryError("Runtime preflight refused: " + str(error), partial) from error


def finish(declaration, source, before):
    """Validate the same worker even after source/capture failure; no new imports."""
    partial = dict(kind=RECEIPT_KIND, phase="finish", status="refused")
    try:
        verify_inventory(declaration)
        source, snapshot, source_files = _source_pins(source)
        if not isinstance(before, dict) or before.get("status") != "bound_before_source":
            raise ValueError("Require a successful before-source runtime receipt")
        unsealed = dict(before)
        seal = unsealed.pop("receipt_sha256", None)
        if seal != _seal(unsealed) or before.get("declaration_sha256") != _seal(declaration):
            raise ValueError("Changed before-source runtime receipt/declaration")
        if before.get("source") != str(source) or before.get("snapshot") != snapshot:
            raise ValueError("Changed frozen source association")
        partial.update(
            source=str(source),
            snapshot=snapshot,
            declaration_sha256=_seal(declaration),
            before_receipt_sha256=seal,
            startup=_startup(source),
        )
        observed = _observe()
        partial["observation"] = observed
        _check_modules(observed, declaration, source, source_files, before["observation"])
        _check_maps(observed, declaration, before["observation"])
        partial.update(
            status="bound_after_source",
            scientific_acceptance=False,
            new_module_names=sorted(
                set(observed["modules"]) - set(before["observation"]["modules"])
            ),
            limits=before["limits"],
        )
        partial["receipt_sha256"] = _seal(partial)
        return partial
    except BaseException as error:
        partial["error"] = dict(type=type(error).__name__, message=str(error))
        if isinstance(error, RuntimeInventoryError):
            partial["partial_observation"] = error.partial
        raise RuntimeInventoryError("Runtime finish refused: " + str(error), partial) from error
