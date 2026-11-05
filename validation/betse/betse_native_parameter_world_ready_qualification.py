"""Held exact-input Parameters diagnostic, ending before any phase birth.

All live returns stay in one process. Evidence contains closed observations,
never a decoded or manufactured replacement for an issued request or owner.
"""

import argparse
import ast
import builtins
import importlib
import json
import os
import stat
import struct
import sys
from contextvars import ContextVar
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, FunctionType, SimpleNamespace

from validation import source_snapshot as snapshot
from validation.betse import betse_normal_ecm_molecule_qualification_resources as resources
from validation.betse import native_seed_demo_input_profiles as input_profiles

FILE = "validation/betse/betse_native_parameter_world_ready_qualification.py"
TEST = "tests/unit/test_betse_native_parameter_world_ready_qualification.py"
RELEASE = "CELLS_NATIVE_PARAMETER_WORLD_READY_QUALIFICATION_RELEASED"
KIND = "cells.original_default_parameter_world_ready_diagnostic@1"
BASE = Path("/mnt/workspaces/Cells")
NATIVE = BASE / "betse-v1.5.0"
DEFAULT_PYTHON = BASE / "venv-betse/bin/python"
RETAINED_SITE = BASE / "venv-betse/lib/python3.13/site-packages"
CPU_SITE = BASE / "venv-cpu/lib/python3.13/site-packages"
RUNTIME_PROVIDERS = (
    ("numpy", RETAINED_SITE, "numpy-2.5.3"),
    ("scipy", RETAINED_SITE, "scipy-1.18.1"),
    ("matplotlib", RETAINED_SITE, "matplotlib-3.11.2"),
    ("jax", CPU_SITE, "jax-0.11.1"),
    ("jaxlib", CPU_SITE, "jaxlib-0.11.1"),
    ("ml_dtypes", CPU_SITE, "ml_dtypes-0.6.0"),
    ("opt_einsum", CPU_SITE, "opt_einsum-3.4.0"),
)
SOURCE_REVIEW = BASE / "native-parameter-WorldReady-pilot4-20261103-01/root-review.json"
SOURCE_REVIEW_SHA256 = "5704b98fe0aeba378cc744eab869b38e9ad96dec53978871b869ec66bf0c5c11"
CLOSURE = "agent-work/cells-worker-01/workfiles/betse_normal_ecm_reviewed_successors_resources.py"
POLICY = dict(
    cpu=0,
    threads=1,
    metadata_bytes=512 * 2**20,
    software_bytes=2**30,
    wall_seconds=480,
    host_reserve_bytes=8 * 2**30,
)
RAW_FILES = {
    "sim_config.yaml": "7ed5a32f9fc256c541db63090aeed6d0207bf706d2847b27269d6bc8c9e85415",
    "extra_configs/expression_data.yaml": (
        "c1e47550c76dd5e3a89989c3e3258833426c5fab3188e40557ddef604eba396d"
    ),
    "extra_configs/grn_basic.yaml": (
        "f25edb13132685589c803b3b4a58d9b8af80f6f8885c9d32fac3be2e382339f2"
    ),
}
MODULES = {
    "parameters": "betse_native_phase_parameters",
    "yaml": "betse_native_parameter_yaml_prefix",
    "paths": "betse_native_parameter_paths",
    "seven": "betse_native_parameter_subconfigurations",
    "numeric": "betse_native_parameter_numeric_prefix",
    "events": "betse_native_parameter_event_declarations",
    "boundary": "betse_native_parameter_network_boundary",
    "network": "betse_native_parameter_network_load",
    "grn": "betse_native_parameter_grn_variables",
    "modulators": "betse_native_parameter_modulators",
    "colormaps": "betse_native_parameter_colormaps",
    "state": "betse_native_parameter_colormap_state",
    "colormap_load": "betse_native_parameter_colormap_load",
    "constants": "betse_native_parameter_initializer_constants",
    "remainder": "betse_native_parameter_load_remainder",
}
KNOWN_PINS = {
    "colormap_state": "8664dea542a6653ab17183ff9bec2caa8aec6e17e0485b146e6fa0193594e399",
    "colormap_load": "80420c878d4955030607f56cd353fbcdd5fd4eebfae74bdfa82bfa1ee230114d",
    "initializer_constants": "a6473b99cf2a74d27f4e0f83f507074fea39b8b658fbc21860a751e152bcd508",
    "load_remainder": "7874abf3991aeef188ab7d5a6f2538a88248bc686eb2f94845e18a735255a035",
}
GATES = (
    "CELLS_ECM_MOLECULE_RUN_LIFECYCLE_RELEASED",
    *(
        "CELLS_NATIVE_PARAMETER_" + suffix + "_RELEASED"
        for suffix in (
            "PATHS",
            "SUBCONFIGURATIONS",
            "NUMERIC_PREFIX",
            "EVENT_DECLARATIONS",
            "NETWORK_LOAD",
            "GRN_VARIABLES",
            "MODULATORS",
            "COLORMAP_LOAD",
            "INITIALIZER_CONSTANTS",
            "LOAD_REMAINDER",
        )
    ),
)
MAX_STEPS = 32
MAX_OBSERVATIONS = 2000000
_WORK_OBSERVER = ContextVar("cells_parameter_only_work_observer", default=None)
ONE_LOAD = ("initial_world_ready",)
CURRENT_LOADS = (*ONE_LOAD, "fresh_current_world_ready")
_ACQUISITIONS, _ACQUISITION_PACKETS, _ACQUISITION_ACTIVE = {}, {}, []
_ACQUISITION_LOCK = RLock()
_ACQUISITION_ENTRY, _ACQUISITION_FAILURES = None, []


def require(value, message):
    if not value:
        raise ValueError(message)


def ref(path):
    return dict(path=str(path), sha256=snapshot.digest(Path(path)))


def read(path):
    path = Path(path)
    require(path.stat().st_size <= 16 * 2**20, "Bounded metadata required")
    return json.loads(path.read_text())


def unlinked(path, *, exists=False):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), "Linked path refused")
    require(path == path.resolve(strict=exists), "Canonical absolute path required")
    return path


def bound(row):
    require(type(row) is dict and set(row) == {"path", "sha256"}, "Exact file reference required")
    path = unlinked(row["path"], exists=True)
    require(path.is_file() and snapshot.digest(path) == row["sha256"], "Changed bound file")
    return path


def runtime_plan(python=DEFAULT_PYTHON):
    """Read-only explicit library composition; never import or initialize it.

    The retained colormap checker requires NumPy AND Matplotlib at RETAINED_SITE.
    JAX is absent there; its existing CPU site is appended after the retained
    site. No package installation, copy, fallback or native execution occurs.
    """
    python = Path(python).absolute()  # Keep the actual venv entry symlink.
    require(python == DEFAULT_PYTHON and python.is_file(), "Retained BETSE Python required")
    providers = {}
    for name, site, distribution in RUNTIME_PROVIDERS:
        require(site.is_dir(), "Missing declared runtime site")
        files = (
            site / name / "__init__.py",
            site / (distribution + ".dist-info/METADATA"),
            site / (distribution + ".dist-info/RECORD"),
        )
        providers[name] = dict(site=str(site), files=[ref(unlinked(p, exists=True)) for p in files])
    return dict(
        mode="retained_betse_with_explicit_cpu_jax_tail@1",
        entry=str(python),
        executable=ref(python.resolve()),
        prefix=str(python.parent.parent),
        venv_configuration=ref(python.parent.parent / "pyvenv.cfg"),
        primary_site=str(RETAINED_SITE),
        appended_site=str(CPU_SITE),
        providers=providers,
        source_inventory_required=True,
        complete_loaded_inventory_required=True,
        unchanged_shared_runtime=True,
        actual_library_import=False,
    )


def _runtime_entry(declared):
    require(declared == runtime_plan(declared["entry"]), "Runtime provider declaration changed")
    require(
        str(Path(sys.prefix)) == declared["prefix"]
        and snapshot.digest(Path(sys.executable).resolve()) == declared["executable"]["sha256"],
        "Explicit retained runtime required",
    )
    primary, extra = declared["primary_site"], declared["appended_site"]
    require(sys.path.count(primary) == 1, "Original retained site must occur once")
    # Reject a prior incompatible import before adding any search path. Equal
    # library bytes at another origin do not establish the required provenance.
    for name, provider in declared["providers"].items():
        module = sys.modules.get(name)
        if module is not None:
            require(
                type(module) is type(sys)
                and vars(module).get("__file__") == provider["files"][0]["path"],
                "Foreign already-loaded runtime provider: " + name,
            )
    require(sys.path.count(extra) <= 1, "Duplicate CPU dependency site refused")
    if extra in sys.path:
        require(sys.path.index(primary) < sys.path.index(extra), "CPU site shadows retained site")
    else:
        sys.path.append(extra)
    return declared


def input_program(path, sha256):
    """Permissions and raw bytes only; this never parses YAML or issues owners."""
    path = bound(dict(path=str(path), sha256=sha256))
    value = read(path)
    profile = input_profiles.require_profile(value.get("input_profile", input_profiles.ORIGINAL))
    raw_files = dict(RAW_FILES)
    if profile != input_profiles.ORIGINAL:
        raw_files[input_profiles.MAIN] = input_profiles.main_file(profile)["sha256"]
    require(set(value["files"]) == set(RAW_FILES), "Exact original default file set required")
    files = {}
    for name, pin in raw_files.items():
        row = value["files"][name]
        actual = bound(row["input"])
        info = actual.stat()
        require(
            actual.is_relative_to(BASE)
            and info.st_nlink == 1
            and stat.S_ISREG(info.st_mode)
            and not info.st_mode & 0o222,
            "Immutable single-link original input required",
        )
        require(
            row["input"]["sha256"] == pin and info.st_size <= 8 * 2**20,
            "Exact bounded original input bytes required",
        )
        files[name] = row["input"]
    main = Path(files["sim_config.yaml"]["path"])
    root = main.parent
    require(all(Path(files[n]["path"]) == root / n for n in files), "Original relative file layout")
    expected = (
        ("init_pickle_dirname", str(root / "INITS")),
        ("sim_pickle_dirname", str(root / "SIMS")),
        ("init_pickle_filename", str(root / "INITS/init_1.betse.gz")),
        ("seed_pickle_filename", str(root / "INITS/world_1.betse.gz")),
        ("sim_pickle_filename", str(root / "SIMS/sim_1.betse.gz")),
        ("init_export_dirname", str(root / "RESULTS/init_1")),
        ("sim_export_dirname", str(root / "RESULTS/sim_1")),
        ("grn_config_filename", str(root / "extra_configs/grn_basic.yaml")),
        ("grn_pickle_dirname", str(root / "RESULTS/GRN")),
        ("grn_pickle_filename", str(root / "RESULTS/GRN/GRN_1.betse.gz")),
        ("grn_unpickle_filename", None),
    )
    supplied = tuple(tuple(row) for row in value["ordered_path_permission"])
    require(supplied == expected, "Exact ordered original path permissions required")
    result = dict(
        manifest=ref(path),
        files=files,
        path_permission=[list(row) for row in expected],
        origin="Unmodified retained BETSE1.5.0 bundled default; not parsed state",
        root=str(root),
        directories=[
            str(root / p)
            for p in ("INITS", "SIMS", "RESULTS/init_1", "RESULTS/sim_1", "RESULTS/GRN")
        ],
    )
    if profile != input_profiles.ORIGINAL:
        result.update(
            input_profile=profile,
            configuration_changes=input_profiles.changes(profile),
            origin=(
                "Retained BETSE1.5.0 bundled default with only while-solving show/save False"
                if profile == input_profiles.HEADLESS
                else "Retained BETSE1.5.0 bundled default with while-solving show/save, "
                "cutting and custom general network False; numerical inputs unchanged"
            ),
        )
    return result


def directory_state(program):
    return [(name, unlinked(name).is_dir(), Path(name).exists()) for name in program["directories"]]


def _directory_epoch(program):
    """Retain actual directories made by the first load, never parsed p state."""
    result, paths = [], {unlinked(program["root"], exists=True)}
    root = next(iter(paths))
    for name in program["directories"]:
        path = unlinked(name, exists=True)
        require(path.is_relative_to(root), "Native output directory outside original input root")
        paths.add(path)
        paths.update(parent for parent in path.parents if parent.is_relative_to(root))
    for path in sorted(paths):
        info = path.stat()
        require(stat.S_ISDIR(info.st_mode), "Completed native output directory required")
        result.append((str(path), info.st_dev, info.st_ino, info.st_mode))
    return tuple(result)


def _acquisition_sequence(inputs):
    sequence = inputs.get("acquisition_sequence", ONE_LOAD)
    require(type(sequence) in (list, tuple), "Explicit acquisition sequence required")
    require(all(type(name) is str for name in sequence), "Exact acquisition labels required")
    sequence = tuple(sequence)
    require(
        sequence in (ONE_LOAD, CURRENT_LOADS), "Only the declared one/two-load route is available"
    )
    return sequence


def output_path(output, packet, program):
    output, packet = unlinked(output), unlinked(packet, exists=True)
    protected = (packet, Path(program["root"]), NATIVE, Path("/home/robert/Cells"))
    require(output.is_relative_to(BASE), "Diagnostic output below /mnt/workspaces/Cells required")
    require(
        all(
            output != p and not output.is_relative_to(p) and not p.is_relative_to(output)
            for p in protected
        ),
        "Output intersects source/packet/input authority",
    )
    return output


def prepare(
    repository,
    directory,
    *,
    inputs,
    inputs_sha256,
    python=DEFAULT_PYTHON,
    extra_sources=(),
    acquisition_sequence=ONE_LOAD,
):
    import runpy

    repository = unlinked(repository, exists=True)
    require(Path(__file__).resolve() == repository / FILE, "Prepare from actual checkout only")
    sequence = _acquisition_sequence(dict(acquisition_sequence=acquisition_sequence))
    require(snapshot.digest(SOURCE_REVIEW) == SOURCE_REVIEW_SHA256, "Accepted dependency review")
    program = input_program(inputs, inputs_sha256)
    directory = output_path(directory, repository, program)
    runtime = runtime_plan(python)
    starts = [FILE, TEST, *("src/cells/processes/" + m + ".py" for m in MODULES.values())]
    require(type(extra_sources) is tuple, "Explicit combined source roster required")
    for name in extra_sources:
        snapshot.relative_path(name)
        require(
            Path(name).parts[0] in ("src", "validation", "tests", "scripts"),
            "Only checkout source paths may extend the image",
        )
        require((repository / name).is_file(), "Missing combined source path")
    starts.extend(extra_sources)
    for name, pin in KNOWN_PINS.items():
        require(
            snapshot.digest(
                repository / ("src/cells/processes/betse_native_parameter_" + name + ".py")
            )
            == pin,
            "Reviewed parameter candidate changed",
        )
    names = runpy.run_path(str(repository / CLOSURE))["closure"](repository, starts)
    for name in ("pyproject.toml", "tests/__init__.py", CLOSURE):
        names[name] = snapshot.digest(repository / name)
    directory.mkdir(parents=True, exist_ok=False)
    manifest = snapshot.freeze(repository, directory / "source", {n: n for n in names})
    declaration = dict(
        kind=KIND,
        held=True,
        automatic_launch=False,
        repository=str(repository),
        source_snapshot=ref(directory / "source/SNAPSHOT.json"),
        git_revision=manifest["git_revision"],
        source_review=ref(SOURCE_REVIEW),
        program=program,
        initial_directory_state=directory_state(program),
        resources=POLICY,
        runtime=runtime,
        source_modules={
            alias: dict(
                module="cells.processes." + module,
                file="src/cells/processes/" + module + ".py",
                sha256=manifest["files"]["src/cells/processes/" + module + ".py"]["sha256"],
            )
            for alias, module in MODULES.items()
        },
        work_policy=dict(
            max_operations=MAX_STEPS,
            max_native_python_entries=MAX_OBSERVATIONS,
            scope=(
                "Python/RNG C boundaries and retained source work; "
                "not FLOPs or C constructor internals"
            ),
        ),
        one_input_sequence=True,
        acquisition_sequence=sequence,
        extra_sources=extra_sources,
        callback_phase_INIT_claim=False,
        review_and_explicit_Root_release_required=True,
    )
    snapshot.write_json(directory / "inputs.json", declaration)
    snapshot.assert_checkout_unchanged(directory / "source")
    return dict(
        packet=ref(directory / "inputs.json"),
        snapshot=declaration["source_snapshot"],
        held=True,
        native_entries=0,
    )


def _packet_inputs(packet, sha256, *, directory_epoch=None):
    packet = unlinked(packet, exists=True)
    require(snapshot.digest(packet / "inputs.json") == sha256, "Wrong parameter packet")
    inputs = read(packet / "inputs.json")
    require(
        inputs["kind"] == KIND and inputs["held"] is True and inputs["resources"] == POLICY,
        "Exact held domain/resources required",
    )
    _acquisition_sequence(inputs)
    require(set(inputs["source_modules"]) == set(MODULES), "Exact parameter source roster")
    manifest = snapshot.verify(
        packet / "source", manifest_sha256=inputs["source_snapshot"]["sha256"]
    )
    require(
        ref(bound(inputs["source_review"]))["sha256"] == SOURCE_REVIEW_SHA256,
        "Dependency review changed",
    )
    program = input_program(
        inputs["program"]["manifest"]["path"], inputs["program"]["manifest"]["sha256"]
    )
    require(program == inputs["program"], "Input/path program changed")
    if directory_epoch is None:
        require(
            directory_state(program) == [tuple(r) for r in inputs["initial_directory_state"]],
            "Initial native directory epoch changed",
        )
    else:
        require(
            _directory_epoch(program) == directory_epoch,
            "Previously issued native directory epoch changed",
        )
    require(inputs["runtime"] == runtime_plan(inputs["runtime"]["entry"]), "Runtime changed")
    for alias, row in inputs["source_modules"].items():
        require(
            row["module"] == "cells.processes." + MODULES[alias]
            and row["file"] == "src/cells/processes/" + MODULES[alias] + ".py",
            "Exact parameter module/file association",
        )
        require(row["sha256"] == manifest["files"][row["file"]]["sha256"], "Module pin mismatch")
    return inputs


def packet_inputs(packet, sha256):
    """Initial preparation always requires the declared pre-first-load epoch."""
    return _packet_inputs(packet, sha256)


def _entry(packet, packet_sha256, enabled):
    require(
        enabled is True and os.environ.get(RELEASE) == "1", "Native parameter entry remains held"
    )
    inputs = packet_inputs(packet, packet_sha256)
    packet = Path(packet).resolve(strict=True)
    require(Path(__file__).resolve() == packet / "source" / FILE, "Actual frozen entry required")
    require(os.sched_getaffinity(0) == {0} and sys.flags.optimize == 0, "CPU0/assertions required")
    _runtime_entry(inputs["runtime"])
    return packet, inputs


def acquire_world_ready(packet, directory, *, packet_sha256, enabled=False):
    return _acquisition_entry(
        _acquire_world_ready, packet, directory, packet_sha256=packet_sha256, enabled=enabled
    )


def _acquisition_entry(operation, *args, **kwargs):
    """Reserve before preflight helpers; caught recursive entry is sticky."""
    global _ACQUISITION_ENTRY
    if _ACQUISITION_ENTRY is not None:
        _ACQUISITION_ENTRY[0] = True
        if _ACQUISITION_ENTRY[1] is not None:
            _ACQUISITION_ENTRY[1].invalid = True
        raise ValueError("Reentrant parameter acquisition refused")
    entry = [False, None, None, ()]
    _ACQUISITION_ENTRY = entry
    primary = None
    try:
        entry[2] = operation(*args, **kwargs)
        _acquisition_stop()
        return entry[2]
    except BaseException as error:
        primary = error
        record = entry[1]
        if record is not None:
            record.invalid, record.published = True, False
            if record.source_error is None:
                record.source_error = error
        try:
            _ACQUISITION_FAILURES.append((entry, error))
        except BaseException as cleanup:
            entry[3] += (cleanup,)
        try:
            error.parameter_acquisition_entry = entry
        except BaseException as cleanup:
            entry[3] += (cleanup,)
        raise
    finally:
        intact = _ACQUISITION_ENTRY is entry
        _ACQUISITION_ENTRY = None
        if not intact and primary is None:
            raise ValueError("Acquisition entry reservation changed")


def _acquire_world_ready(packet, directory, *, packet_sha256, enabled=False):
    """In-process genuine load, returning the exact ``(WorldReady owner, p)``.

    A combined caller can use ``prepare(extra_sources=...)`` and the same source
    root. It must own the enclosing resource guard, work observer, filesystem
    policy and runtime inventory. This function opens no construction claim,
    spawns no child and never acquires callback/phase authority. Its output is
    an actual live return, not a persisted handoff or owner reconstruction.
    """
    _acquisition_stop(entry=True)
    packet, inputs = _entry(packet, packet_sha256, enabled)
    _acquisition_stop()
    sequence = _acquisition_sequence(inputs)
    reload_record, journal, output, primary_error = None, [], None, None
    if sequence == CURRENT_LOADS:
        with _ACQUISITION_LOCK:
            _acquisition_stop(entry=True)
            key = (str(packet), packet_sha256)
            require(
                key not in _ACQUISITION_PACKETS, "Initial two-load acquisition already consumed"
            )
            require(
                len(_ACQUISITION_PACKETS) < 32, "Bounded in-process acquisition roster exhausted"
            )
            reload_record = SimpleNamespace(
                owner=None,
                p=None,
                packet=packet,
                packet_sha256=packet_sha256,
                directory_epoch=None,
                thread=get_ident(),
                process=os.getpid(),
                attempted=False,
                published=False,
                invalid=False,
                current_owner=None,
                current_p=None,
                source_error=None,
                capture_errors=[],
                cleanup_errors=(),
                journal=[],
                initial_journal=journal,
                execution_state=None,
            )
            _ACQUISITION_PACKETS[key] = reload_record
            _ACQUISITION_ENTRY[1] = reload_record
            _ACQUISITION_ACTIVE.append(reload_record)
    try:
        output = output_path(directory, packet, inputs["program"])
        output.mkdir(parents=True, exist_ok=False)
        (output / "evidence").mkdir()
        modules = _modules(inputs, packet / "source")
        _acquisition_stop()
        owner, p = _execute(modules, inputs["program"], output / "evidence", journal)
        _acquisition_stop()
        if reload_record is not None:
            require(id(owner) not in _ACQUISITIONS, "Initial owner already retained")
            reload_record.owner, reload_record.p = owner, p
            reload_record.directory_epoch = _directory_epoch(inputs["program"])
        snapshot.write_json(
            output / "acquisition.json",
            dict(
                packet=ref(packet / "inputs.json"),
                operations=journal,
                actual_world_ready_identity=id(owner),
                actual_p_identity=id(p),
                construction_claim_opened=False,
                phase_or_persisted_owner_admission=False,
                acquisition_sequence=sequence,
            ),
        )
        _acquisition_stop()
        if reload_record is not None:
            # Only an actually returned first pair creates this private receipt.
            # It is not a new Parameters owner and cannot be read back from JSON.
            _ACQUISITIONS[id(owner)] = reload_record
        return owner, p
    except BaseException as primary:
        primary_error = primary
        capture_errors = []
        if output is not None:
            try:
                snapshot.write_json(
                    output / "failure.json",
                    dict(
                        primary=error_record(primary),
                        operations=journal,
                        source_or_evidence_incomplete=True,
                    ),
                )
            except BaseException as secondary:
                capture_errors.append(error_record(secondary))
        if reload_record is not None:
            reload_record.source_error = primary
            reload_record.invalid = True
            reload_record.capture_errors.extend(capture_errors)
        try:
            primary.parameter_acquisition = dict(operations=journal, capture_errors=capture_errors)
        except BaseException:
            pass
        raise
    finally:
        if reload_record is not None:
            try:
                if _ACQUISITION_ACTIVE and _ACQUISITION_ACTIVE[-1] is reload_record:
                    _ACQUISITION_ACTIVE.pop()
                else:
                    raise ValueError("Initial acquisition reservation changed")
            except BaseException as cleanup:
                reload_record.cleanup_errors += (cleanup,)
                reload_record.invalid = True
                # Avoid another fallible list method while restoring our own
                # exclusive reservation. This never reopens a consumed slot.
                _ACQUISITION_ACTIVE[:] = []
                if primary_error is None:
                    raise


def _acquisition_stop(*, entry=False):
    if _ACQUISITION_ENTRY is not None:
        require(not _ACQUISITION_ENTRY[0], "Rejected recursive load poisons this acquisition")
    if _ACQUISITION_ACTIVE:
        record = _ACQUISITION_ACTIVE[-1]
        if entry:
            record.invalid = True
            raise ValueError("Reentrant parameter acquisition refused")
        require(not record.invalid, "Rejected recursive load poisons this acquisition")


def acquire_current_world_ready(
    packet,
    directory,
    *,
    packet_sha256,
    previous_owner,
    previous_parameters,
    enabled=False,
):
    return _acquisition_entry(
        _acquire_current_world_ready,
        packet,
        directory,
        packet_sha256=packet_sha256,
        previous_owner=previous_owner,
        previous_parameters=previous_parameters,
        enabled=enabled,
    )


def _acquire_current_world_ready(
    packet,
    directory,
    *,
    packet_sha256,
    previous_owner,
    previous_parameters,
    enabled=False,
):
    """One fresh complete load after the initial load's genuine directory work.

    The enclosing caller must separately authenticate its completed INIT and
    retain its actual Simulator/Cells. This function grants no INIT/SIM phase
    authority. It uses the same declared immutable input/source/runtime and
    calls the original public constructor/load pipeline again; no old p fields,
    old validators, decoded owners or persisted caches feed the new load.
    """
    require(enabled is True and os.environ.get(RELEASE) == "1", "Fresh current load remains held")
    with _ACQUISITION_LOCK:
        if _ACQUISITION_ACTIVE:
            _ACQUISITION_ACTIVE[-1].invalid = True
            raise ValueError("Reentrant current-parameter acquisition refused")
        record = _ACQUISITIONS.get(id(previous_owner))
        require(
            record is not None
            and record.owner is previous_owner
            and record.p is previous_parameters
            and record.thread == get_ident(),
            "Exact in-process initial WorldReady/Parameters pair required",
        )
        require(not record.attempted, "Current-parameter acquisition already consumed")
        require(
            record.process == os.getpid() and not record.invalid,
            "Original live acquisition epoch required",
        )
        _ACQUISITION_ENTRY[1] = record
        # Consumption precedes source/packet/runtime checks and never rearms on
        # failure, including rejection by an inherited observer on their return.
        record.attempted = True
        _ACQUISITION_ACTIVE.append(record)
        primary = None
        output = None
        try:
            require(
                Path(packet).resolve(strict=True) == record.packet
                and packet_sha256 == record.packet_sha256,
                "Exact original prepared packet required",
            )
            inputs = _packet_inputs(packet, packet_sha256, directory_epoch=record.directory_epoch)
            require(_acquisition_sequence(inputs) == CURRENT_LOADS, "Two-load preparation required")
            require(
                Path(__file__).resolve() == record.packet / "source" / FILE,
                "Actual frozen entry required",
            )
            require(
                os.sched_getaffinity(0) == {0} and sys.flags.optimize == 0,
                "CPU0/assertions required",
            )
            _runtime_entry(inputs["runtime"])
            require(not record.invalid, "Rejected recursive current load poisons this attempt")
            output = output_path(directory, record.packet, inputs["program"])
            output.mkdir(parents=True, exist_ok=False)
            (output / "evidence").mkdir()
            modules = _modules(inputs, record.packet / "source")
            require(not record.invalid, "Rejected recursive current load poisons this attempt")
            pair = _execute(modules, inputs["program"], output / "evidence", record.journal)
            require(
                type(pair) is tuple and len(pair) == 2, "Exact fresh actual return pair required"
            )
            record.current_owner, record.current_p = pair
            require(
                record.current_owner is not record.owner and record.current_p is not record.p,
                "Current load must return distinct genuine owner and Parameters",
            )
            require(not record.invalid, "Rejected recursive current load poisons this attempt")
            require(
                _directory_epoch(inputs["program"]) == record.directory_epoch,
                "Current load replaced the retained native directory epoch",
            )
            snapshot.write_json(
                output / "acquisition.json",
                dict(
                    packet=ref(record.packet / "inputs.json"),
                    operations=record.journal,
                    initial_owner_identity=id(record.owner),
                    initial_p_identity=id(record.p),
                    actual_world_ready_identity=id(record.current_owner),
                    actual_p_identity=id(record.current_p),
                    retained_directory_epoch=record.directory_epoch,
                    acquisition_sequence=CURRENT_LOADS,
                    distinct_fresh_native_load=True,
                    INIT_SIM_or_persisted_owner_admission=False,
                ),
            )
            require(not record.invalid, "Rejected recursive current load poisons this attempt")
            record.published = True
            return pair
        except BaseException as error:
            primary = error
            record.source_error = error
            if output is not None:
                try:
                    snapshot.write_json(
                        output / "failure.json",
                        dict(
                            primary=error_record(error),
                            operations=record.journal,
                            current_parameters_returned=record.current_p is not None,
                            source_or_evidence_incomplete=True,
                        ),
                    )
                except BaseException as capture:
                    record.capture_errors.append(capture)
            try:
                error.parameter_acquisition = record
            except BaseException as capture:
                record.capture_errors.append(capture)
            raise
        finally:
            try:
                if _ACQUISITION_ACTIVE and _ACQUISITION_ACTIVE[-1] is record:
                    _ACQUISITION_ACTIVE.pop()
                else:
                    raise ValueError("Current-parameter acquisition reservation changed")
            except BaseException as cleanup:
                record.cleanup_errors += (cleanup,)
                record.invalid = True
                _ACQUISITION_ACTIVE[:] = []
                if primary is None:
                    raise


def error_record(error):
    """Safe primary/cause identity; no user exception __str__ or arbitrary repr."""
    frames, tb = [], error.__traceback__
    while tb is not None and len(frames) < 64:
        frames.append(
            dict(
                file=tb.tb_frame.f_code.co_filename,
                function=tb.tb_frame.f_code.co_name,
                line=tb.tb_lineno,
            )
        )
        tb = tb.tb_next
    kind = type(error)
    args = []
    for value in error.args[:16]:
        if value is None or type(value) in (str, int, bool):
            args.append(value if type(value) is not str else value[:4096])
        else:
            args.append(
                dict(
                    type=type(value).__module__ + "." + type(value).__qualname__, identity=id(value)
                )
            )
    return dict(
        type=type.__getattribute__(kind, "__module__")
        + "."
        + type.__getattribute__(kind, "__qualname__"),
        identity=id(error),
        argument_summary=args,
        argument_summary_is_not_full_graph=True,
        cause_identity=id(error.__cause__) if error.__cause__ is not None else None,
        context_identity=id(error.__context__) if error.__context__ is not None else None,
        frames=frames,
        frames_truncated=tb is not None,
    )


def _codec():
    from cells.processes import betse_normal_ecm_molecule_checkpoint_codec

    return betse_normal_ecm_molecule_checkpoint_codec


def archive(directory, payload, *, retained=None):
    """Reuse the closed codec or an already retained production colormap encoder."""
    directory.mkdir(exist_ok=False)
    encoder = _codec().Encoder() if retained is None else retained.encoder
    tree = encoder.capture(payload) if retained is None else retained.tree
    encoder.write(directory, tree)
    files = {n: ref(directory / n) for n in ("state.json", "arrays.npz")}
    result = dict(
        kind="parameter_observation@1",
        files=files,
        fingerprint=encoder.seal(tree),
        complete=True,
        owner_admission=False,
        reconstruct_live_owners=False,
    )
    snapshot.write_json(directory / "manifest.json", result)
    _codec()._sync_directory(directory)
    return ref(directory / "manifest.json")


class ObservationRejected(RuntimeError):
    pass


def _work_failure(stage, *, returned=None, primary=None, refuse=False):
    """Safe operation boundary; retained observations never authorize more work."""
    observer = _WORK_OBSERVER.get()
    if observer is None or not observer.deferred:
        return None
    raw = (stage, returned, primary, tuple(observer.failed_returns))
    observer.failed_boundaries.append(raw)
    detail = dict(
        stage="work-observer-" + stage,
        first_error=error_record(observer.deferred[0]),
        failed_return_records=len(observer.failed_returns),
        returned_identity=id(returned),
        primary_identity=id(primary) if primary is not None else None,
    )
    if refuse:
        error = ObservationRejected("Prior work observation failed before another operation")
        error.parameter_work_observation = raw
        raise error from observer.deferred[0]
    return detail


class WritePolicy:
    """Actual-worker writes: evidence/cache output and five original mkdir targets."""

    def __init__(self, output, directories):
        self.output = unlinked(output, exists=True)
        self.directories = tuple(unlinked(p) for p in directories)
        self.events = []

    def audit(self, event, args):
        if event == "open":
            if type(args[2]) is not int or not args[2] & (
                os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
            ):
                return
            targets = args[:1]
        elif event in ("os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.truncate"):
            targets = args[:1]
        elif event in ("os.rename", "os.link", "os.symlink"):
            targets = args[:2]
        else:
            return
        require(len(self.events) < 4096, "Bounded diagnostic filesystem events")
        self.events.append(
            dict(
                event=event,
                targets=[p if type(p) in (str, int) else type(p).__name__ for p in targets],
            )
        )
        for target in targets:
            require(type(target) in (str, bytes), "Unowned write descriptor refused")
            path = unlinked(os.fsdecode(target))
            allowed = path == self.output or path.is_relative_to(self.output)
            allowed |= event == "os.mkdir" and path in self.directories
            require(allowed, "Write outside original directory/evidence permission refused")


def take(directory, name, operation, observe, journal):
    """Exclusive observation; always forward the identical successful live return."""
    _acquisition_stop()
    _work_failure("before-operation", refuse=True)
    require(len(journal) < MAX_STEPS, "Bounded diagnostic operation count")
    path = directory / f"{len(journal):02d}-{name}"
    path.mkdir(exist_ok=False)  # Refuse collisions before invoking the operation.
    row = dict(name=name, attempted=True, returned=False, evidence_complete=False, errors=[])
    journal.append(row)
    snapshot.write_json(path / "attempt.json", dict(name=name, attempt=len(journal)))
    returned, primary = None, None
    try:
        _acquisition_stop()
        returned = operation()
        row["returned"] = True
        row["returned_identity"] = id(returned)
    except BaseException as error:
        primary = error
        row["primary"] = error_record(error)
        try:
            snapshot.write_json(path / "primary.json", row["primary"])
        except BaseException as secondary:
            row["errors"].append(dict(stage="primary-write", **error_record(secondary)))
    # A failed return recorder must not wait until the full acquisition ends.
    # Capture available original return/partial evidence, then refuse this
    # operation before its caller can invoke the following public delegate.
    failed_work = _work_failure("after-operation", returned=returned, primary=primary)
    if failed_work is not None:
        row["errors"].append(failed_work)
    try:
        payload, graphs, captures = observe(returned, primary)
        row["payload"] = archive(path / "payload", payload)
        row["graphs"] = {
            key: archive(path / ("graph-" + key), value) for key, value in graphs.items()
        }
        row["captures"] = {
            key: archive(path / ("capture-" + key), None, retained=value)
            for key, value in captures.items()
        }
        row["evidence_complete"] = not row["errors"]
    except BaseException as secondary:
        row["errors"].append(dict(stage="observe-or-archive", **error_record(secondary)))
    try:
        snapshot.write_json(path / "outcome.json", row)
    except BaseException as secondary:
        row["errors"].append(dict(stage="outcome-write", **error_record(secondary)))
        row["evidence_complete"] = False
    if primary is not None:
        try:
            primary.parameter_diagnostic = row
            if failed_work is not None:
                primary.parameter_work_observation = _WORK_OBSERVER.get().failed_boundaries[-1]
        except BaseException as secondary:
            row["errors"].append(dict(stage="primary-attachment", **error_record(secondary)))
        raise primary
    if not row["evidence_complete"]:
        error = ObservationRejected("Returned operation has incomplete evidence: " + name)
        error.parameter_diagnostic = row
        error.parameter_live_return = returned
        if failed_work is not None:
            error.parameter_work_observation = _WORK_OBSERVER.get().failed_boundaries[-1]
        raise error
    _acquisition_stop()
    return returned


def _modules(inputs, source):
    modules = {}
    for alias, row in inputs["source_modules"].items():
        expected = source / row["file"]
        require(snapshot.digest(expected) == row["sha256"], "Changed producer before import")
        module = importlib.import_module(row["module"])
        require(
            Path(module.__file__).resolve() == expected and sys.modules[row["module"]] is module,
            "Foreign live parameter module",
        )
        modules[alias] = module
    return modules


def _code(value):
    """Typed executable constants, including binary64 sign/payload and nested code."""
    kind = type(value)
    if kind is CodeType:
        return (
            "code",
            value.co_argcount,
            value.co_posonlyargcount,
            value.co_kwonlyargcount,
            value.co_flags,
            value.co_code,
            tuple(_code(c) for c in value.co_consts),
            value.co_names,
            value.co_varnames,
            value.co_freevars,
            value.co_cellvars,
            value.co_exceptiontable,
        )
    if kind is float:
        return ("float", struct.pack(">d", value))
    if kind is complex:
        return ("complex", struct.pack(">dd", value.real, value.imag))
    if kind in (tuple, frozenset):
        values = tuple(_code(v) for v in value)
        return (kind.__name__, frozenset(values) if kind is frozenset else values)
    require(value is None or kind in (str, bytes, int, bool), "Unknown executable constant")
    return kind.__name__, value


def _function(module, name):
    function = vars(module).get(name)
    require(
        type(function) is FunctionType
        and function.__globals__ is vars(module)
        and function.__builtins__ is vars(builtins),
        "Original callable/global/builtins required",
    )
    filename = str(Path(module.__file__).resolve())
    require(function.__code__.co_filename == filename, "Original callable filename required")
    compiled = compile(ast.parse(Path(filename).read_bytes()), filename, "exec", dont_inherit=True)
    expected = next(c for c in compiled.co_consts if type(c) is CodeType and c.co_name == name)
    require(_code(function.__code__) == _code(expected), "Original public callable code required")
    return function


def _observer(modules, alias, schema, state):
    module = modules[alias]

    def observe(value, primary):
        graphs, captures, payload = {}, {}, dict(primary=None, returned=None)
        context = None
        if primary is None:
            expected = getattr(module, schema)
            require(type(value) is expected, "Exact issued return type required: " + schema)
            registry = (
                module._FILES
                if schema == "FileInput"
                else (
                    module._POLICIES
                    if schema == "PathPolicy"
                    else (module._REQUESTS if schema == "Request" else module._ISSUED)
                )
            )
            require(value in registry, "Actual live registry membership required")
            context = registry[value] if registry is module._ISSUED else None
            payload["returned"] = dict(type=schema, identity=id(value))
        else:
            payload["primary"] = error_record(primary)
            payload["primary_args"] = primary.args
            fields = vars(primary)
            context = fields.get("partial")
            if context is None:
                for name in (
                    "parameter_load_remainder",
                    "initializer_constants",
                    "parameter_context",
                ):
                    if name in fields:
                        context = fields[name]
                        break
        if context is not None:
            require(type(context) is SimpleNamespace, "Closed known source-context schema required")
            fields = vars(context)
            p = fields.get("p")
            if p is None and alias == "state":
                p = fields["bound"].p
            if p is not None:
                require(
                    state["p"] is None or state["p"] is p, "Same native Parameters identity changed"
                )
                state["p"] = p
                payload["p_identity"] = id(p)
                payload["parameter_order"] = tuple(vars(p))
                require("_run_sim" not in vars(p), "A phase must never be born by this diagnostic")
            for name in (
                "work",
                "metadata_work",
                "source_work",
                "calls",
                "entries",
                "returns",
                "filesystem",
                "observations",
                "validations",
            ):
                if name in fields:
                    value = fields[name]
                    if name == "returns" and type(value) is dict:
                        # Native parser/colormap objects are retained in the
                        # actual p/colormap graphs, never coerced to plain dicts.
                        payload[name] = {
                            key: dict(
                                identity=id(item),
                                count=len(item) if type(item) in (tuple, list) else item,
                                item_identities=tuple(id(v) for v in item)
                                if type(item) in (tuple, list)
                                else (),
                            )
                            for key, item in value.items()
                        }
                    else:
                        payload[name] = value
            for name in (
                "graph",
                "before_graph",
                "after_graph",
                "source_return_graph",
                "failure_capture",
                "stable",
                "grn_before",
            ):
                value = fields.get(name)
                if type(value) is tuple and len(value) == 2:
                    graphs[name] = dict(
                        data=value[1], object_identities=tuple(id(v) for v in value[0])
                    )
            if alias == "grn" and "authority" in fields:
                value = module._grn_graph(context)
                graphs["actual_grn"] = dict(
                    data=value[1], object_identities=tuple(id(v) for v in value[0])
                )
            for name in ("stream", "parser", "decoded", "raw_return"):
                if name in fields:
                    value = fields[name]
                    payload[name + "_identity"] = id(value) if value is not None else None
            if alias == "network" and fields.get("decoded_observed"):
                require(
                    vars(p).get("expression_data") is fields["decoded"],
                    "Actual decoded expression data must remain in full p graph",
                )
            for name in ("capture", "partial_capture", "after", "after_cm", "colormaps"):
                value = fields.get(name)
                if value is not None and all(
                    hasattr(value, attr) for attr in ("encoder", "tree", "identity")
                ):
                    captures[name] = value
                    payload["capture_" + name] = dict(
                        identity=value.identity,
                        object_identities=tuple(id(v) for v in value.objects),
                    )
            for name in ("trial", "record", "binding"):
                value = fields.get(name)
                if value is not None:
                    function = getattr(module, name + "_record", None)
                    if function is None:
                        function = getattr(
                            module,
                            "record_document" if name == "record" else "binding_record",
                            None,
                        )
                    if function is not None:
                        payload[name] = function(value)
            payload["context_identity"] = id(context)
        if primary is None and schema in ("Request", "FileInput", "PathPolicy"):
            function = getattr(
                module,
                {
                    "Request": "request_record",
                    "FileInput": "file_record",
                    "PathPolicy": "policy_record",
                }[schema],
            )
            payload["declaration"] = function(value)
        return payload, graphs, captures

    return observe


def _execute(modules, program, evidence, journal):
    """Exact public source path. No caller-supplied operations or intermediate owners."""
    state = dict(p=None)
    if _ACQUISITION_ACTIVE:
        _ACQUISITION_ACTIVE[-1].execution_state = state
    require(
        os.environ.get(RELEASE) == "1" and set(modules) == set(MODULES),
        "Actual released module set required",
    )
    for alias, module in modules.items():
        require(
            module is sys.modules.get("cells.processes." + MODULES[alias]),
            "Actual canonical module identity required",
        )

    def op(alias, name, schema, method, *args, **kwargs):
        function = _function(modules[alias], method)
        return take(
            evidence,
            name,
            lambda: function(*args, **kwargs),
            _observer(modules, alias, schema, state),
            journal,
        )

    m = modules
    birth_request = op(
        "parameters",
        "birth-request",
        "Request",
        "declare",
        law_id=m["parameters"].LAW_ID,
        run_id="original-default-parameter-diagnostic",
    )
    birth = op(
        "parameters", "actual-birth", "ParameterOwner", "prepare", birth_request, enabled=True
    )
    raw = program["files"]
    main = op(
        "yaml",
        "main-file",
        "FileInput",
        "input_file",
        raw["sim_config.yaml"]["path"],
        sha256=raw["sim_config.yaml"]["sha256"],
        origin=program["origin"],
    )
    request = op(
        "yaml", "yaml-request", "Request", "from_unloaded", birth, main, law_id=m["yaml"].LAW_ID
    )
    owner = op("yaml", "actual-yaml", "YamlPrefixOwner", "prepare", request, enabled=True)
    policy = op(
        "paths",
        "path-permission",
        "PathPolicy",
        "declare_paths",
        paths=tuple(tuple(r) for r in program["path_permission"]),
        law_id=m["paths"].LAW_ID,
    )
    request = op(
        "paths", "path-request", "Request", "from_yaml", owner, policy, law_id=m["paths"].LAW_ID
    )
    owner = op("paths", "actual-paths", "PathsOwner", "prepare", request, enabled=True)
    for alias, method, schema in (
        ("seven", "from_paths", "SubconfigurationsOwner"),
        ("numeric", "from_subconfigurations", "NumericPrefixOwner"),
        ("events", "from_numeric", "EventDeclarationsOwner"),
    ):
        request = op(alias, alias + "-request", "Request", method, owner, law_id=m[alias].LAW_ID)
        owner = op(alias, "actual-" + alias, schema, "prepare", request, enabled=True)
    expression = op(
        "yaml",
        "expression-file",
        "FileInput",
        "input_file",
        raw["extra_configs/expression_data.yaml"]["path"],
        sha256=raw["extra_configs/expression_data.yaml"]["sha256"],
        origin=program["origin"],
    )
    owner = op(
        "boundary",
        "network-input",
        "NetworkBoundary",
        "prepare",
        owner,
        law_id=m["boundary"].LAW_ID,
        expression_file=expression,
    )
    request = op(
        "network", "network-request", "Request", "from_boundary", owner, law_id=m["network"].LAW_ID
    )
    owner = op("network", "actual-network", "NetworkLoadOwner", "prepare", request, enabled=True)
    request = op(
        "grn",
        "grn-request",
        "Request",
        "from_network",
        owner,
        law_id=m["grn"].LAW_ID,
        grn_file=None,
    )
    owner = op("grn", "actual-grn", "GrnVariablesOwner", "prepare", request, enabled=True)
    request = op(
        "modulators",
        "modulator-request",
        "Request",
        "from_grn",
        owner,
        law_id=m["modulators"].LAW_ID,
    )
    owner = op(
        "modulators", "actual-modulators", "ModulatorsOwner", "prepare", request, enabled=True
    )
    owner = op(
        "colormaps",
        "colormap-input",
        "ColormapBoundary",
        "prepare",
        owner,
        law_id=m["colormaps"].LAW_ID,
    )
    owner = op(
        "state",
        "registry-capture",
        "ColormapRegistryState",
        "capture_registry",
        owner,
        law_id=m["state"].LAW_ID,
    )
    owner = op(
        "colormap_load",
        "actual-colormaps",
        "ColormapsOwner",
        "prepare",
        owner,
        law_id=m["colormap_load"].LAW_ID,
        enabled=True,
    )
    owner = op(
        "constants",
        "actual-constants",
        "ConstantsOwner",
        "prepare",
        owner,
        law_id=m["constants"].LAW_ID,
        enabled=True,
    )
    owner = op(
        "remainder",
        "actual-world-ready",
        "WorldReadyParametersOwner",
        "complete_load",
        owner,
        law_id=m["remainder"].LAW_ID,
        enabled=True,
    )
    state["owner"] = owner
    context = m["remainder"]._context(owner)
    require(
        context.p is state["p"] and context.record.load_cursor == 218, "Actual complete same-p load"
    )

    def verify_observation(value, primary, *, native_p=False):
        if primary is None:
            require(
                value is (state["p"] if native_p else context.record),
                "Identical actual final validation return required",
            )
        payload, graphs, captures = _observer(m, "remainder", "WorldReadyParametersOwner", state)(
            owner, primary
        )
        payload["verification_return_identity"] = id(value) if primary is None else None
        return payload, graphs, captures

    take(
        evidence,
        "final-history",
        lambda: m["remainder"].validate_completed_history(owner),
        verify_observation,
        journal,
    )
    take(
        evidence,
        "final-live-parameters",
        lambda: owner.parameters,
        lambda value, primary: verify_observation(value, primary, native_p=True),
        journal,
    )
    return owner, state["p"]


def _worker_body(packet, output, inputs, filesystem):
    """Called only after the public frozen-worker/resource/release preflight."""
    from validation.betse.betse_normal_channel_join_runtime import inventory
    from validation.betse.betse_normal_ecm_molecule_handoff_run_plugin import Calls, identity

    initial_profile, initial_trace = sys.getprofile(), sys.gettrace()
    set_profile, set_trace = sys.setprofile, sys.settrace

    def restore(errors):
        for name, setter, getter, expected in (
            ("profile", set_profile, sys.getprofile, initial_profile),
            ("trace", set_trace, sys.gettrace, initial_trace),
        ):
            try:
                setter(expected)
                require(getter() is expected, "Diagnostic " + name + " recovery failed")
            except BaseException as error:
                errors.append(dict(stage=name + "-recovery", **error_record(error)))

    class ParameterCalls(Calls):
        @staticmethod
        def category(module, name):
            if module.startswith(("betse.", "matplotlib.")):
                return (
                    "native_parameter_boundary"
                    if name
                    in (
                        "__init__",
                        "load",
                        "reload_paths",
                        "_load_ion_profile",
                        "_balance_charge",
                        "get_colormap",
                        "upgrade_sim_conf",
                        "make_unless_dir",
                    )
                    else "other_Cells_callable"
                )
            return Calls.category(module, name)

        def profile(self, frame, event, arg):
            try:
                if (
                    event == "call"
                    and self.category(frame.f_globals.get("__name__", ""), frame.f_code.co_name)
                    is not None
                ):
                    self.observed_calls += 1
                    if frame.f_globals.get("__name__", "").startswith(("betse.", "matplotlib.")):
                        self.native_calls += 1
                        require(self.native_calls <= MAX_OBSERVATIONS, "Diagnostic callable bound")
                self.observe(frame, event, arg)
            except BaseException as error:
                if event in ("return", "c_return", "c_exception"):
                    deferred.append(error)
                    # Exact live witness, including None on exception unwind,
                    # is separate from fallible recorder/serializer output.
                    self.failed_returns.append((frame, event, arg, error))
                else:
                    raise

    journal, deferred, recovery = [], [], []
    primary, returned, counters = None, None, None
    snapshot.write_json(
        output / "started.json", dict(child=identity(), packet=ref(packet / "inputs.json"))
    )
    with (output / "calls.jsonl").open("x") as stream:
        calls = ParameterCalls(stream)
        calls.observed_calls = calls.native_calls = 0
        calls.deferred = deferred
        calls.failed_returns, calls.failed_boundaries = [], []
        token = _WORK_OBSERVER.set(calls)
        try:
            calls.start()
            returned, p = acquire_world_ready(
                packet,
                output / "parameter-entry",
                packet_sha256=snapshot.digest(packet / "inputs.json"),
                enabled=True,
            )
            journal = read(output / "parameter-entry/acquisition.json")["operations"]
            require("_run_sim" not in vars(p), "Parameter-only boundary")
            require(not deferred, "Incomplete inherited observation")
        except BaseException as error:
            primary = error
            acquisition = vars(error).get("parameter_acquisition")
            if type(acquisition) is dict:
                journal = acquisition["operations"]
        finally:
            try:
                counters = calls.stop()
                require(counters["profile_intact"], "Actual work observer lost")
            except BaseException as error:
                recovery.append(error_record(error))
            restore(recovery)
            _WORK_OBSERVER.reset(token)
    for name, produce in (
        (
            "work.json",
            lambda: dict(
                journal=journal,
                counters=counters,
                observer_errors=[error_record(e) for e in deferred],
                observer_return_witnesses=[
                    dict(
                        function=frame.f_code.co_qualname,
                        file=frame.f_code.co_filename,
                        event=event,
                        returned_identity=id(value),
                        returned_type=type(value).__module__ + "." + type(value).__qualname__,
                        error=error_record(error),
                    )
                    for frame, event, value, error in calls.failed_returns
                ],
                filesystem=filesystem.events,
            ),
        ),
        ("runtime.json", inventory),
    ):
        try:
            snapshot.write_json(output / name, produce())
            require(
                sys.getprofile() is initial_profile and sys.gettrace() is initial_trace,
                "Evidence callback changed diagnostic hooks",
            )
        except BaseException as error:
            recovery.append(error_record(error))
            restore(recovery)
    result = dict(
        kind=KIND,
        succeeded=primary is None and not recovery and not deferred,
        actual_world_ready_returned=any(
            row["name"] == "actual-world-ready" and row["returned"] for row in journal
        ),
        final_verified_owner_available=returned is not None,
        operations=journal,
        primary=error_record(primary) if primary is not None else None,
        recovery_errors=recovery,
        packet=ref(packet / "inputs.json"),
        child=identity(),
        source_native_work_is_not_independent_cases=True,
        independent_biological_cases=0,
        phase_callback_INIT_or_physical_admission=False,
        checkpoint_or_native_pickle=False,
    )
    try:
        snapshot.write_json(
            output / ("result.json" if result["succeeded"] else "failure.json"), result
        )
        require(
            sys.getprofile() is initial_profile and sys.gettrace() is initial_trace,
            "Terminal callback changed diagnostic hooks",
        )
    except BaseException as error:
        recovery.append(dict(stage="terminal-publication", **error_record(error)))
        restore(recovery)
        if primary is None:
            raise
    if primary is not None:
        raise primary
    require(result["succeeded"], "Diagnostic source/evidence refused")
    return result


def worker(packet, output, *, packet_sha256, enabled=False):
    packet, inputs = _entry(packet, packet_sha256, enabled)
    output = output_path(output, packet, inputs["program"])
    output.mkdir(parents=True, exist_ok=False)
    (output / "evidence").mkdir()
    filesystem = WritePolicy(output, inputs["program"]["directories"])
    sys.addaudithook(filesystem.audit)
    try:
        return _worker_body(packet, output, inputs, filesystem)
    except BaseException as error:
        secondary = []
        try:
            if not (output / "failure.json").exists():
                snapshot.write_json(
                    output / "failure.json",
                    dict(
                        kind=KIND,
                        succeeded=False,
                        primary=error_record(error),
                        packet=ref(packet / "inputs.json"),
                        result_visible=(output / "result.json").exists(),
                        source_or_evidence_incomplete=True,
                        scientific_credit=0,
                    ),
                )
        except BaseException as capture:
            secondary.append(error_record(capture))
        try:
            error.parameter_worker_recovery = secondary
        except BaseException:
            pass
        raise


def start(packet, output, *, packet_sha256, enabled=False):
    require(
        enabled is True and os.environ.get(RELEASE) == "1", "Actual parameter launch remains held"
    )
    inputs = packet_inputs(packet, packet_sha256)
    packet = Path(packet).resolve(strict=True)
    output = output_path(output, packet, inputs["program"])
    output.mkdir(parents=True, exist_ok=False)
    (output / "process").mkdir()
    # Keep launcher environment construction metadata-only: importing a test
    # controller here also initializes its secrets/SystemRandom dependency.
    source = packet / "source"
    environment = {k: v for k, v in os.environ.items() if not k.startswith(("CELLS_", "PYTEST_"))}
    environment.update(
        PYTHONPATH=os.pathsep.join(
            (
                str(source / "src"),
                str(source),
                "/mnt/workspaces/Cells/pillow-overlay-12.3.0-20261030-01",
            )
        ),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONOPTIMIZE="0",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1",
        RAYON_NUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
        JAX_PLATFORMS="cpu",
    )
    environment.update({name: "1" for name in (RELEASE, *GATES)})
    environment["MPLCONFIGDIR"] = str(output / "worker/runtime-cache/matplotlib")
    environment["XDG_CACHE_HOME"] = str(output / "worker/runtime-cache")
    command = [
        "taskset",
        "-c",
        "0",
        inputs["runtime"]["entry"],
        "-B",
        str(packet / "source" / FILE),
        "--worker",
        str(packet),
        "--output",
        str(output / "worker"),
        "--packet-sha256",
        packet_sha256,
        "--enabled",
    ]
    return resources.run_bounded(
        command,
        directory=output / "process",
        cwd=packet / "source",
        env=environment,
        timeout=480,
        max_rss_bytes=2**30,
        min_available_bytes=8 * 2**30,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", type=Path)
    mode.add_argument("--start", type=Path)
    mode.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--inputs-sha256")
    parser.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    parser.add_argument("--extra-source", action="append", default=[])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--packet-sha256")
    parser.add_argument("--enabled", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        require(args.inputs is not None and args.inputs_sha256, "Exact input manifest required")
        result = prepare(
            args.repository,
            args.prepare,
            inputs=args.inputs,
            inputs_sha256=args.inputs_sha256,
            python=args.python,
            extra_sources=tuple(args.extra_source),
        )
    else:
        require(
            args.output is not None and args.packet_sha256, "Exact output/packet binding required"
        )
        operation = worker if args.worker else start
        result = operation(
            args.worker or args.start,
            args.output,
            packet_sha256=args.packet_sha256,
            enabled=args.enabled,
        )
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
