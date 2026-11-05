"""Prepare an independent, fresh original-BETSE SEED -> complete INIT reference.

The original package supplies Parameters, phase, callbacks, solver and pickle
round trip. No Cells owner/evaluator or normalized phase is an oracle. The only
selected source boundaries are the declared optional flux inverse omission and
run_sim_core immediately before its INIT pickle. Numerical bodies, calendar,
networks and transport otherwise remain original. Execution is held until the
explicit source/bootstrap/shared-writer contracts below are reviewed and bound.
"""

import argparse
import ast
import hashlib
import importlib
import importlib.abc
import importlib.util
import json
import os
import random
import resource
import runpy
import stat
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from validation import source_snapshot as snapshot
from validation.betse import native_seed_demo_evidence as evidence
from validation.betse import native_seed_demo_input_profiles as profiles
from validation.betse import native_seed_demo_inputs as inputs

ROOT = Path(__file__).resolve().parents[2]
NATIVE_ROOT = Path("/mnt/workspaces/Cells/betse-v1.5.0")
FILE = "validation/betse/native_init_terminal_reference.py"
TEST = "tests/unit/test_native_init_terminal_reference.py"
RUNNER = "validation/betse/native_init_terminal_reference_software.py"
CLOSURE = "agent-work/cells-worker-01/workfiles/betse_normal_ecm_reviewed_successors_resources.py"
KIND = "cells.original_betse_complete_init_reference@2"
MODES = ("original", "disabled")
ENDPOINT = "original_run_sim_core_before_init_pickle"
RNG_WITNESS_KIND = "cells.common_initial_rng_observation@1"
RNG_BUILTIN_WITNESS_KIND = "cells.common_initial_rng_observation@2"
RNG_RUNTIME_HELPER = "validation/betse/native_rng_runtime.py"
RNG_RUNTIME_HELPER_SHA256 = None
RNG_EPOCH = "pre_SEED_before_world_construction"
RNG_RUNTIME_MODULES = (
    "numpy",
    "numpy.random",
    "numpy.random.mtrand",
    "numpy.random._mt19937",
    "numpy.random.bit_generator",
    "random",
    "_random",
)
SOURCE_REVIEW_SHA256 = BOOTSTRAP_REVIEW_SHA256 = WRITER_REVIEW_SHA256 = None
EXECUTION_RELEASE_SHA256 = None
EVIDENCE_SHA256 = "e3b5228e3622b6baeaa27fd322008ec61c251f477f406dfe38f26f1f875ab4b6"
RELEASE = "CELLS_ORIGINAL_INIT_REFERENCE_RELEASED"
NATIVE_POLICY = dict(
    cpu=5, threads=1, max_rss_bytes=2**30, wall_seconds=7200, reserve_bytes=8 * 2**30
)
WRITER_PRODUCERS = {
    "validation.betse.native_seed_demo": (
        "cd34e5dfbd95630fe4f428b21093b5c2fd447ad3ff6ea8f9498ac40e53077a71"
    ),
    "validation.betse.native_seed_world_callback_prelude": (
        "b6cfd794d8edd70274eb5b1768f8a07bc15a98d88f171472f0aae7dbd4d474b5"
    ),
}
_ATTEMPT = None
AUDIT_MODULE = "validation.betse.native_seed_demo_launch"
AUDIT_COMPONENTS = (
    "_link_record",
    "_null_device",
    "WritePolicy",
    "_temporary_binding",
    "path",
    "error_record",
)
AUDIT_COMPONENT_SHA256 = "a0085966942f81f67d9ae4ab986855ecb2f457b7224503faea93315101286f51"
REVIEW_PIN_NAMES = frozenset(
    (
        "SOURCE_REVIEW_SHA256",
        "BOOTSTRAP_REVIEW_SHA256",
        "WRITER_REVIEW_SHA256",
        "EXECUTION_RELEASE_SHA256",
    )
)
_AUDITS = []
MAX_FILES, MAX_SOURCE_BYTES, MAX_FILE_BYTES = 4096, 128 * 2**20, 8 * 2**20
MAX_SEED_BYTES, MAX_SITES, MAX_WORK, MAX_ITERATIONS = 64 * 2**20, 8192, 100000, 512
CAPTURE_LIMITS = dict(
    column_bytes=evidence.payload.MAX_BLOB,
    total_column_bytes=evidence.payload.MAX_UNIQUE,
    metadata_upper_bytes=evidence.MAX_METADATA,
    atomic_metadata_upper_bytes=evidence.payload.MAX_METADATA,
    nodes=evidence.MAX_NODES,
    depth=evidence.payload.MAX_DEPTH,
)
CRITICAL = {
    "betse/science/sim.py": "02a9a049b5daa5cf6bc543332aa89437f58a4700ed31310abc3ee13697f22d43",
    "betse/science/simrunner.py": (
        "6a9389f106d717dc83ea1a594a64aa5bde278cef9a17b2a8ff01251b08d7be8a"
    ),
    "betse/science/phase/phasecls.py": (
        "e7c129aca1930fcb31884f32d4f2ebbb46d31113a66887a39c85ba0009b78ea8"
    ),
    "betse/science/parameters.py": (
        "f36ec747918aa285ca043fe51086bcff4e4e2198cd4f30a138f1e58a51ecf85e"
    ),
    "betse/science/cells.py": ("be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2"),
    "betse/science/filehandling.py": (
        "194ecf36cdc4e10a81b953ddb1a515cdd206eeea6a14670967e6fcf75c4a20c4"
    ),
    "betse/appmeta.py": "5cf6789033f62889ca01cdb083495f608f6432f92aacfeb7fac1a077e4476d9b",
    "betse/util/app/meta/appmetaabc.py": (
        "73716c647565fc92a5fa9ab95038d035405e8d845b8b3f16ea717bb7d7103b4c"
    ),
    "betse/science/phase/phasecallbacks.py": (
        "5938685e17f94e1066c938ae080800e22e918e5457d6406820e37d847540ac2b"
    ),
}
ITERATION_FIELDS = (
    "vm",
    "cc_cells",
    "cc_env",
    "cc_at_mem",
    "fluxes_mem",
    "fluxes_gj",
    "fluxes_env_x",
    "fluxes_env_y",
)
SELECTED = {
    "betse.science.simrunner": {"seed", "init"},
    "betse.science.cells": {
        "make_world",
        "make_voronoi",
        "cell_index",
        "cellVerts",
        "cellMatrices",
        "cell_vols",
        "mem_processing",
        "near_neigh",
        "makeECM",
        "environment",
        "make_maskM",
        "redo_gj",
        "graphLaplacian",
        "save_cluster",
    },
    "betse.science.sim": {
        "init_core",
        "init_dynamics",
        "clear_storage",
        "update_V",
        "_plot_loop",
        "run_sim_core",
        "_run_sim_core_loop",
        "_run_fast_sim_core_loop",
    },
    "betse.science.filehandling": {"loadWorld", "saveSim"},
    "betse.science.phase.phasecls": {"__init__"},
}
_RAW_FAILURES = []


class ReferenceRejected(ValueError):
    def __init__(self, message, *, stage, partial=None):
        super().__init__(message)
        self.stage, self.partial = stage, partial


def _require(condition, message, stage="metadata"):
    if not condition:
        raise ReferenceRejected(message, stage=stage)


def _path(value):
    value = Path(value).absolute()
    _require(not any(p.is_symlink() for p in (value, *value.parents)), "Unlinked path required")
    _require(".." not in value.parts, "Canonical path required")
    return value


def _read(path, limit):
    path = _path(path)
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, "Regular file required")
        _require(before.st_size <= limit, "File exceeds explicit bound")
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    _require(len(raw) <= limit, "File grew beyond bound")

    def identity(value):
        return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)

    _require(identity(before) == identity(after), "File changed during authenticated read")
    return raw, identity(after)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _seal(value):
    return _sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def source_inventory(root=NATIVE_ROOT):
    """Observe the original package, without importing or executing its code."""
    root = _path(root)
    result, total = {}, 0
    for path in sorted((root / "betse").rglob("*")):
        if "__pycache__" in path.parts:
            continue
        _require(not path.is_symlink(), "Linked original package member")
        if path.is_dir():
            continue
        raw, _ = _read(path, MAX_FILE_BYTES)
        total += len(raw)
        _require(len(result) < MAX_FILES and total <= MAX_SOURCE_BYTES, "Package inventory bound")
        result[str(path.relative_to(root))] = dict(sha256=_sha(raw), size_bytes=len(raw))
    _require(bool(result), "Original package missing")
    for name, pin in CRITICAL.items():
        _require(result.get(name, {}).get("sha256") == pin, "Original source changed: " + name)
    return result


def _method(tree, class_name, name):
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name]
    _require(len(classes) == 1, "Unique original class required: " + class_name)
    nodes = [n for n in classes[0].body if isinstance(n, ast.FunctionDef) and n.name == name]
    _require(len(nodes) == 1, "Unique original method required: " + name)
    return nodes[0]


def selected_tree(relative, raw, mode):
    """Compile-time selections only; never replace a class/method after birth."""
    _require(type(mode) is str and mode in MODES, "Exact flux inverse mode required")
    if relative in CRITICAL:
        _require(_sha(raw) == CRITICAL[relative], "Original numerical/source authority changed")
    tree, changes = ast.parse(raw, filename=relative), []
    if relative == "betse/science/sim.py":
        method = _method(tree, "Simulator", "run_sim_core")
        positions = [
            i
            for i, n in enumerate(method.body)
            if isinstance(n, ast.Expr)
            and isinstance(n.value, ast.Call)
            and isinstance(n.value.func, ast.Attribute)
            and n.value.func.attr == "_pickle_phase"
        ]
        _require(len(positions) == 1, "Unique original pre-pickle boundary required")
        position = positions[0]
        _require(
            ast.unparse(method.body[position].value) == "self._pickle_phase(phase)"
            and len(method.body[position:]) == 2
            and isinstance(method.body[-1], ast.If)
            and ast.unparse(method.body[-1].test) == "exception_instability is not None",
            "Original terminal/instability suffix changed",
        )
        changes.append(
            dict(
                method="Simulator.run_sim_core",
                first_excluded_line=method.body[position].lineno,
                retained_statement_sha256=_sha(
                    ast.dump(
                        ast.Module(body=method.body[:position], type_ignores=[]),
                        include_attributes=False,
                    ).encode()
                ),
                retained_native_instability_checked_by_observer=True,
            )
        )
        method.body = method.body[:position]
    if relative == "betse/science/cells.py" and mode == "disabled":
        method = _method(tree, "Cells", "make_world")
        stores = [
            n
            for n in method.body
            if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "(_, self.lapENV_P_inv)"
        ]
        _require(len(stores) == 1, "Unique original flux assignment required")
        store = stores[0]
        _require(
            isinstance(store.value, ast.Call)
            and ast.unparse(store.value.func) == "self.grid_obj.makeLaplacian",
            "Original flux inverse call changed",
        )
        changes.append(dict(method="Cells.make_world", omitted_flux_call_line=store.lineno))
        store.value = ast.copy_location(
            ast.Tuple(elts=[ast.Constant(None), ast.Constant(None)], ctx=ast.Load()), store.value
        )
    return ast.fix_missing_locations(tree), changes


def _reference_profile(value):
    value = profiles.require_profile(value)
    _require(
        value in (profiles.HEADLESS, profiles.HEADLESS_CORE),
        "Explicit headless reference input profile required",
        "inputs",
    )
    return value


def source_plan(*, input_profile=profiles.HEADLESS):
    input_profile = _reference_profile(input_profile)
    return dict(
        kind=KIND,
        endpoint=ENDPOINT,
        modes=list(MODES),
        critical_source_pins=dict(CRITICAL),
        workflow=[
            "BetseAppMeta",
            "Parameters.make",
            "SimRunner",
            "SimRunner.seed",
            "fresh_native_seed_pickle",
            "SimRunner.init",
            ENDPOINT,
        ],
        input_profile=input_profile,
        unchanged_calendar_network_transport_and_numerical_bodies=True,
        seed_pickle_scope="created_and_consumed_once_in_this_fresh_process_only",
        external_seed_phase_parameter_owner_or_cache_inputs=False,
        ordinary_checkpoint_or_restart_admission=False,
        selected_source_changes=["optional_flux_inverse_assignment", "pre_INIT_pickle_boundary"],
        native_instability_is_failure=True,
        initial_random_state="fresh_process_ambient_state_observed_without_reset",
        independent_comparison_requires_matching_initial_random_authority=True,
        common_initial_rng_observation=dict(
            kind=RNG_WITNESS_KIND,
            builtin_kind=RNG_BUILTIN_WITNESS_KIND,
            runtime_provenance_helper=dict(file=RNG_RUNTIME_HELPER, sha256=RNG_RUNTIME_HELPER_SHA256),
            epoch=RNG_EPOCH,
            boundary="after_original_Parameters.make_and_SimRunner_before_runner.seed",
            full_numpy_MT_and_python_state=True,
            source_input_runtime_and_order_bound=True,
            observation_does_not_equalize_ambient_states=True,
            semantic_common_epoch_requires_both_producers_reviewed=True,
            automatic_parity_or_starting_authority=False,
        ),
        comparator_normalized_AST_sha256=comparator_ast_sha256((ROOT / FILE).read_bytes()),
        work="per-site call/return counts plus ordered selected boundaries; never input credit",
        observation_fields=list(ITERATION_FIELDS),
        iteration_capacity=MAX_ITERATIONS,
        observation_retention=dict(
            iteration_history="file pins only; captures written synchronously",
            live_iteration_rows=1,
            static_grid_inverse_in_iteration_fields=False,
            selected_return_locals="latest dictionary per selected module/method; no frame history",
            selected_locals_and_return_slots=2 * sum(map(len, SELECTED.values())),
            preallocation_limits=dict(CAPTURE_LIMITS),
            alias_occurrences_charged_separately=True,
            metadata_budget="conservative wire-tree upper bound; refusal, never truncation",
            native_source_history_and_total_process_memory_still_guarded=True,
        ),
        source_review_sha256=SOURCE_REVIEW_SHA256,
        bootstrap_review_sha256=BOOTSTRAP_REVIEW_SHA256,
        shared_writer_review_sha256=WRITER_REVIEW_SHA256,
        execution_release_sha256=EXECUTION_RELEASE_SHA256,
        actual_source_native_reference_execution_released=False,
        shared_machinery=[
            "original BETSE package and dependencies",
            "typed wire encoder",
            "immutable snapshot",
            "multipart evidence",
            "resource/runtime tools",
            "reviewed demo shared-writer session and process-lifetime log lease",
        ],
        writer_producers=dict(WRITER_PRODUCERS),
        native_policy=dict(NATIVE_POLICY),
        prepared_inputs_are_immutable=True,
        execution_inputs="exclusive exact-byte fresh copy; original relative YAML paths",
        HOME_rewrite_or_RNG_initialization=False,
        per_execution_release_required=True,
        enclosing_filesystem_audit=dict(
            module=AUDIT_MODULE,
            components=list(AUDIT_COMPONENTS),
            component_sha256=AUDIT_COMPONENT_SHA256,
            reads="exact released roots/files; fixed input bytes authenticated separately",
            writes="reviewed native-home exception and fresh execution output only",
            lifetime="through_worker_process_exit",
            sticky_failure=True,
        ),
        physical_checkpoint_SIM_or_solver_repair_claim=False,
    )


def _input_manifest(folder, pin, mode):
    """Authenticate raw headless inputs, not a Cells parameter/phase producer."""
    folder = _path(folder)
    raw, _ = _read(folder / "inputs.json", 2**20)
    _require(_sha(raw) == pin, "Exact paired input manifest required")
    value = json.loads(raw)
    profile = _reference_profile(value.get("configuration_profile"))
    kind = inputs.kind_for_profile(profile)
    expected = profiles.selected_inventory(value)
    _require(
        kind is not None
        and value.get("kind") == kind
        and value.get("held") is True
        and value.get("source_tree_sha256") == inputs.BUNDLE_SHA256
        and inputs._digest(value["source_inventory"]) == inputs.BUNDLE_SHA256
        and value.get("source_origin") == str(inputs.NATIVE)
        and value.get("configuration_profile") == profile
        and mode in MODES
        and set(value["modes"]) == set(MODES),
        "Exact headless demo pair required",
    )
    root = folder / mode / "config"
    _require(value["modes"][mode]["config"] == str(root), "Selected input path retargeted")
    _require(inputs.inventory(root) == expected, "Selected complete input bytes changed")
    for name in expected["files"]:
        info = (root / name).stat()
        _require(info.st_nlink == 1 and not info.st_mode & 0o222, "Immutable raw input required")
    for name in ("INITS/world_1.betse.gz", "INITS/init_1.betse.gz", "SIMS/sim_1.betse.gz"):
        _require(not (root / name).exists(), "Previously used native output refuses")
    return dict(root=str(root), manifest_sha256=pin, inventory=expected, mode=mode, profile=profile)


def execution_copy(selected, destination, state):
    """Copy data only, using the existing exact-byte/no-hardlink producer.

    Original relative output paths resolve inside this new config directory.
    No YAML, path scalar, image, or numerical field is rewritten. A partial copy
    stays in the failed execution; it never receives a completion record.
    """
    source, destination = _path(selected["root"]), _path(destination)
    _require(
        not destination.exists()
        and not destination.is_relative_to(source)
        and not source.is_relative_to(destination),
        "Fresh disjoint execution copy required",
    )
    expected = selected["inventory"]
    _require(inputs.inventory(source) == expected, "Prepared input bytes changed before copying")
    destination.mkdir(mode=0o700)
    rows = []
    state.raw["execution_copy"] = dict(source=source, destination=destination, rows=rows)
    for name in expected["directories"]:
        (destination / snapshot.relative_path(name)).mkdir(mode=0o700, parents=True, exist_ok=True)
    for name, row in expected["files"].items():
        path = destination / snapshot.relative_path(name)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        record = dict(name=name, status="attempted")
        rows.append(record)
        inputs._copy_file(source / name, path, row)
        old, new = (source / name).stat(), path.stat()
        _require(
            (old.st_dev, old.st_ino) != (new.st_dev, new.st_ino) and new.st_nlink == 1,
            "Independent execution input inode required",
        )
        record.update(
            status="copied",
            sha256=snapshot.digest(path),
            source_inode=[old.st_dev, old.st_ino],
            execution_inode=[new.st_dev, new.st_ino],
        )
    _require(
        inputs.inventory(destination) == expected and inputs.inventory(source) == expected,
        "Complete exact execution copy and unchanged prepared inputs required",
    )
    return dict(root=str(destination), source_root=str(source), inventory=expected, files=rows)


def _pin(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _json_record(path, expected, limit=2**20):
    _require(_pin(expected), "Explicit exact document pin required", "release")
    raw, _ = _read(path, limit)
    _require(_sha(raw) == expected, "Authenticated document bytes changed", "release")

    def pairs(rows):
        result = {}
        for key, value in rows:
            _require(key not in result, "Duplicate document key", "release")
            result[key] = value
        return result

    def invalid(value):
        raise ReferenceRejected("Nonstandard JSON constant: " + value, stage="release")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def _writer_providers():
    modules = []
    for name, expected in WRITER_PRODUCERS.items():
        path = ROOT / (name.replace(".", "/") + ".py")
        _require(snapshot.digest(_path(path)) == expected, "Reviewed writer producer changed")
        actual = importlib.import_module(name)
        _require(
            Path(actual.__file__).resolve() == path and sys.modules.get(name) is actual,
            "Actual immutable writer producer required",
        )
        modules.append(actual)
    demo, callback = modules
    _require(
        demo.SESSION_REVIEW_SHA256 == WRITER_REVIEW_SHA256,
        "Reference must adopt the exact existing coordinated writer review",
        "shared_log",
    )
    return demo, callback


def _bootstrap_contract(callback):
    policy = callback.source_plan()["filesystem_conflicts"]
    return dict(
        kind="cells.original_INIT_bootstrap_review@1",
        original_appmeta="betse.appmeta.BetseAppMeta",
        matplotlib_backend="Agg",
        HOME_environment=os.environ.get("HOME"),
        resolved_HOME=str(Path.home()),
        filesystem_policy_sha256=_seal(policy),
        MPLCONFIGDIR="fresh_declared_execution_subdirectory",
        no_HOME_rewrite=True,
        original_package_before_any_phase=True,
        enclosing_audit_component_sha256=AUDIT_COMPONENT_SHA256,
        enclosing_audit_required=True,
    )


def _source_contract(plan):
    return dict(
        kind="cells.original_INIT_source_review@1",
        native_inventory_sha256=plan["native_inventory_sha256"],
        original_critical_pins=dict(CRITICAL),
        endpoint=ENDPOINT,
        modes=list(MODES),
        no_numerical_kernel_calendar_or_network_repair=True,
    )


def _execution_contract():
    # This is the stable reviewed verifier/resource policy, not an image pin.
    # A separate per-execution document binds the exact prepared image below;
    # keeping the two separate avoids a review/source/snapshot hash cycle.
    return dict(
        kind="cells.original_INIT_execution_policy_review@1",
        policy=dict(NATIVE_POLICY),
        one_fresh_worker=True,
        internal_fresh_seed_round_trip_only=True,
        per_execution_exact_prepared_pin_required=True,
        detached_supervision_required=True,
        scientific_or_checkpoint_credit=False,
    )


def _release(plan, prepared_pin, release_path, release_pin, output, enabled):
    _require(
        enabled is True
        and os.environ.get(RELEASE) == "1"
        and all(
            _pin(value)
            for value in (
                SOURCE_REVIEW_SHA256,
                BOOTSTRAP_REVIEW_SHA256,
                WRITER_REVIEW_SHA256,
                EXECUTION_RELEASE_SHA256,
            )
        ),
        "Original package/bootstrap/shared writer/execution adoption remains held",
        "release",
    )
    release = _json_record(release_path, release_pin)
    _require(
        type(release) is dict
        and set(release)
        == {
            "kind",
            "prepared_sha256",
            "snapshot_sha256",
            "worker_output",
            "policy",
            "reviews",
            "rng_policy",
            "pythonpath",
            "read_access",
            "enabled",
        }
        and release["kind"] == "cells.original_INIT_reference_execution_release@1"
        and release["enabled"] is True
        and release["prepared_sha256"] == prepared_pin
        and release["snapshot_sha256"] == plan["execution_source"]["snapshot_sha256"]
        and release["worker_output"] == str(output)
        and release["policy"] == NATIVE_POLICY,
        "Exact per-execution reference release required",
        "release",
    )
    _require(
        release["pythonpath"] == os.environ.get("PYTHONPATH"),
        "Exact explicitly declared runtime import paths required",
        "bootstrap",
    )
    for name in (release["pythonpath"] or "").split(os.pathsep):
        if name:
            path = _path(name)
            _require(
                not path.is_relative_to(Path("/home/robert/Cells")),
                "Mutable checkout cannot supply execution imports",
                "bootstrap",
            )
    access = release["read_access"]
    _require(
        type(access) is dict
        and set(access) == {"roots", "files"}
        and all(type(access[key]) is list and len(access[key]) <= 1024 for key in access),
        "Exact bounded bootstrap read domains required",
        "bootstrap",
    )
    for name in (*access["roots"], *access["files"]):
        path = _path(name)
        _require(path != Path("/"), "Unbounded filesystem read domain refuses", "bootstrap")
    reviews = release["reviews"]
    _require(
        type(reviews) is dict and set(reviews) == {"source", "bootstrap", "writer", "execution"},
        "Complete explicit review roster required",
        "release",
    )
    expected = dict(
        source=SOURCE_REVIEW_SHA256,
        bootstrap=BOOTSTRAP_REVIEW_SHA256,
        writer=WRITER_REVIEW_SHA256,
        execution=EXECUTION_RELEASE_SHA256,
    )
    documents = {}
    for name, pin in expected.items():
        row = reviews[name]
        _require(
            type(row) is dict and set(row) == {"path", "sha256"} and row["sha256"] == pin,
            "Exact adopted review required: " + name,
            "release",
        )
        documents[name] = _json_record(row["path"], pin)
    demo, callback = _writer_providers()
    _require(
        documents["source"] == _source_contract(plan)
        and documents["bootstrap"] == _bootstrap_contract(callback)
        and documents["execution"] == _execution_contract(),
        "Reviewed source/bootstrap/execution contract changed",
        "release",
    )
    rng = release["rng_policy"]
    _require(
        type(rng) is dict
        and set(rng) == {"exact_parity", "expected_before_seed"}
        and type(rng["exact_parity"]) is bool,
        "Explicit RNG comparison scope required",
        "rng",
    )
    record = rng["expected_before_seed"]
    if rng["exact_parity"]:
        _require(
            type(record) is dict and set(record) == {"path", "sha256"} and _pin(record["sha256"]),
            "Exact initial RNG expectation required",
            "rng",
        )
        expectation = _json_record(record["path"], record["sha256"])
        _rng_expectation_shape(expectation)
    else:
        _require(record is None, "Source-only RNG scope cannot hide a supplied state", "rng")
    return release, demo, callback


def _resources():
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    _require(
        os.sched_getaffinity(0) == {NATIVE_POLICY["cpu"]}
        and 0 < soft <= hard <= NATIVE_POLICY["max_rss_bytes"]
        and all(
            os.environ.get(name) == "1"
            for name in (
                "OPENBLAS_NUM_THREADS",
                "OMP_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        )
        and os.environ.get("CUDA_VISIBLE_DEVICES") == "",
        "Exact reference CPU/thread/memory envelope required",
        "resources",
    )
    _require(
        guard_memory_available() >= NATIVE_POLICY["reserve_bytes"],
        "Reference host memory reserve unavailable",
        "resources",
    )


def guard_memory_available():
    from validation.betse import betse_mesh_lifecycle_preparation_guard as guard

    return guard.memory_available()


def _rng_expectation_shape(value):
    legacy = (
        type(value) is dict
        and set(value) == {"kind", "state"}
        and value.get("kind") == ("cells.original_INIT_rng_expectation@1")
    )
    linked = (
        type(value) is dict
        and set(value) == {"kind", "epoch", "common_binding", "state"}
        and (
            value.get("kind") == "cells.original_INIT_rng_expectation@2"
            and value.get("epoch") == RNG_EPOCH
            and type(value.get("common_binding")) is dict
        )
    )
    _require(legacy or linked, "Typed observation-only RNG expectation required", "rng")


def _rng_check(policy, observed_state, *, witness=None):
    if policy["exact_parity"]:
        record = policy["expected_before_seed"]
        expected = _json_record(record["path"], record["sha256"])
        _rng_expectation_shape(expected)
        if witness is not None:
            _require(
                expected["kind"] == "cells.original_INIT_rng_expectation@2"
                and expected["epoch"] == witness["epoch"]
                and expected["common_binding"] == witness["common_binding"],
                "Initial RNG expectation epoch/input/runtime linkage differs; no reset",
                "rng",
            )
        _require(
            expected["state"] == typed(observed_state),
            "Initial RNG authority does not match; no reset or parity credit",
            "rng",
        )


def _read_initial_rng_states(state):
    # Assign the partial first: failure in the second getter retains the first
    # original state. Neither a draw nor a reset is part of this observation.
    observed = {}
    state.raw["before_seed_random_states"] = observed
    observed["numpy_random"] = sys.modules["numpy"].random.get_state()
    observed["python_random"] = random.getstate()
    observed["initial_random_reset_or_replacement"] = False
    return observed


def _rng_runtime_api():
    _require(_pin(RNG_RUNTIME_HELPER_SHA256), "Reviewed RNG provenance helper unavailable", "rng")
    path = ROOT / RNG_RUNTIME_HELPER
    raw, _ = _read(path, MAX_FILE_BYTES)
    _require(_sha(raw) == RNG_RUNTIME_HELPER_SHA256, "RNG provenance helper source changed", "rng")
    api = importlib.import_module("validation.betse.native_rng_runtime")
    _require(Path(api.__file__).resolve() == path, "Actual RNG provenance helper required", "rng")
    code = compile(raw, str(path), "exec", dont_inherit=True)
    from types import CodeType, FunctionType
    codes = {v.co_name: v for v in code.co_consts if type(v) is CodeType}
    for node in ast.parse(raw).body:
        if isinstance(node, ast.FunctionDef):
            fn = vars(api).get(node.name)
            _require(type(fn) is FunctionType and fn.__code__ == codes[node.name]
                     and fn.__globals__ is vars(api) and fn.__closure__ is None
                     and fn.__defaults__ is None and fn.__kwdefaults__ is None,
                     "RNG provenance helper callable changed", "rng")
    return api


def _initial_rng_runtime():
    from validation.betse import betse_normal_channel_join_runtime as runtime

    inventory = runtime.inventory()
    if not set(RNG_RUNTIME_MODULES) <= set(inventory["loaded_files"]):
        return _rng_runtime_api().binding()
    files = {name: inventory["loaded_files"][name] for name in RNG_RUNTIME_MODULES}
    _require(
        all(set(row) == {"path", "sha256"} and _pin(row["sha256"]) for row in files.values()),
        "Complete RNG runtime file identities required",
        "rng",
    )
    return dict(
        python=inventory["python"],
        executable=inventory["executable"],
        numpy_version=sys.modules["numpy"].__version__,
        files=files,
    )


def _initial_rng_witness(plan, state, observed, runtime):
    """Saved observation data only: this does not issue a model or RNG owner."""
    import numpy as np

    _require(
        type(observed) is dict
        and set(observed)
        == {
            "numpy_random",
            "python_random",
            "initial_random_reset_or_replacement",
        }
        and observed["initial_random_reset_or_replacement"] is False,
        "Complete observation-only initial RNG record required",
        "rng",
    )
    mt, py = observed["numpy_random"], observed["python_random"]
    _require(
        type(mt) is tuple
        and len(mt) == 5
        and mt[0] == "MT19937"
        and type(mt[1]) is np.ndarray
        and mt[1].dtype.str in ("<u4", ">u4")
        and mt[1].shape == (624,)
        and mt[1].strides == (4,)
        and any(int(word) != 0 for word in mt[1])
        and type(mt[2]) is int
        and 0 <= mt[2] <= 624
        and type(mt[3]) is int
        and mt[3] in (0, 1)
        and type(mt[4]) is float,
        "Complete original NumPy MT words/position/Gaussian cache required",
        "rng",
    )
    _require(
        type(py) is tuple
        and len(py) == 3
        and type(py[0]) is int
        and py[0] == 3
        and type(py[1]) is tuple
        and len(py[1]) == 625
        and all(type(word) is int and 0 <= word < 2**32 for word in py[1][:-1])
        and type(py[1][-1]) is int
        and 0 <= py[1][-1] <= 624
        and (py[2] is None or type(py[2]) is float),
        "Complete original Python words/index/Gaussian cache required",
        "rng",
    )
    p, runner = state.raw.get("parameters"), state.raw.get("runner")
    _require(
        state.stage == "original_runner"
        and p is not None
        and runner is not None
        and getattr(runner, "_p", None) is p
        and "seed_phase" not in state.raw
        and "init_phase" not in state.raw
        and not any(
            row[2:4] in (("betse.science.simrunner", "seed"), ("betse.science.simrunner", "init"))
            for row in state.work
        ),
        "Exact fresh original pre-SEED order and same-p runner required",
        "rng",
    )
    builtin_runtime = runtime.get("kind") == "cells.rng_runtime_provenance@2"
    if builtin_runtime:
        _rng_runtime_api().validate(runtime)
    _require(builtin_runtime or (
        type(runtime) is dict
        and set(runtime) == {"python", "executable", "numpy_version", "files"}
        and all(type(runtime[key]) is str and runtime[key] for key in ("python", "numpy_version"))
        and type(runtime["files"]) is dict
        and set(runtime["files"]) == set(RNG_RUNTIME_MODULES)
        and all(
            type(row) is dict
            and set(row) == {"path", "sha256"}
            and type(row["path"]) is str
            and _pin(row["sha256"])
            for row in [runtime["executable"], *runtime["files"].values()]
        )),
        "Complete initial RNG runtime binding required",
        "rng",
    )
    source = plan["execution_source"]
    _require(
        snapshot.digest(ROOT / FILE) == source["owned_files"][FILE]
        and snapshot.digest(ROOT / "SNAPSHOT.json") == source["snapshot_sha256"],
        "Exact frozen pre-SEED witness producer required",
        "rng",
    )
    _require(
        plan["inputs"]["mode"] in MODES
        and _reference_profile(plan["source_plan"]["input_profile"])
        == plan["inputs"].get("profile", profiles.HEADLESS)
        and type(plan["inputs"]["inventory"]) is dict
        and _pin(plan["native_inventory_sha256"]),
        "Declared pre-SEED input/profile/source binding required",
        "rng",
    )
    common = dict(
        input_inventory_sha256=_seal(plan["inputs"]["inventory"]),
        mode=plan["inputs"]["mode"],
        profile=plan["source_plan"]["input_profile"],
        runtime=runtime,
    )
    provenance = dict(
        reference_sha256=source["owned_files"][FILE],
        snapshot_sha256=source["snapshot_sha256"],
        native_inventory_sha256=plan["native_inventory_sha256"],
        original_critical_pins=dict(CRITICAL))
    if builtin_runtime:
        manifest = snapshot.verify(ROOT, manifest_sha256=source["snapshot_sha256"])
        _require(manifest["files"][RNG_RUNTIME_HELPER]["sha256"] == RNG_RUNTIME_HELPER_SHA256,
                 "Actual frozen RNG provenance helper required", "rng")
        provenance["files"] = {RNG_RUNTIME_HELPER: RNG_RUNTIME_HELPER_SHA256}
    return dict(
        kind=RNG_BUILTIN_WITNESS_KIND if builtin_runtime else RNG_WITNESS_KIND,
        epoch=RNG_EPOCH,
        common_binding=common,
        state=observed,
        source=provenance,
        order=dict(
            boundary="after_original_Parameters.make_and_SimRunner_before_runner.seed",
            stage=state.stage,
            parameter_identity=id(p),
            runner_identity=id(runner),
            same_parameter=True,
            seed_entered=False,
            selected_boundaries=list(state.work),
            native_sites=[
                dict(site=list(site), counts=list(counts)) for site, counts in state.sites.items()
            ],
        ),
        observed_states_equalized=False,
        common_starting_authority_established=False,
        scientific_physical_checkpoint_credit=0,
    )


def _capture_initial_rng(plan, state, archive):
    _stop(state)
    _, observed = _attempt(state, "initial_rng_states", _read_initial_rng_states, state)
    _stop(state)
    _, runtime = _attempt(state, "initial_rng_runtime", _initial_rng_runtime)
    _stop(state)
    _, witness = _attempt(
        state, "initial_rng_witness", _initial_rng_witness, plan, state, observed, runtime
    )
    _stop(state)
    state.raw["pre_seed_rng_witness"] = witness
    _attempt(state, "before_seed_rng_capture", archive.save, "before_seed_random_states", observed)
    _stop(state)
    _, pin = _attempt(state, "pre_seed_rng_capture", archive.save, "pre_seed_rng_witness", witness)
    _stop(state)
    state.initial_rng_observation = pin
    _rng_check(plan["rng_policy"], observed, witness=witness)
    return witness


def _audit_provider():
    path = ROOT / (AUDIT_MODULE.replace(".", "/") + ".py")
    raw, _ = _read(path, MAX_FILE_BYTES)
    tree = ast.parse(raw)
    selected = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in AUDIT_COMPONENTS
    ]
    _require(
        tuple(node.name for node in selected) == AUDIT_COMPONENTS
        and _sha(
            ast.dump(ast.Module(body=selected, type_ignores=[]), include_attributes=False).encode()
        )
        == AUDIT_COMPONENT_SHA256,
        "Reviewed filesystem audit components changed",
        "bootstrap",
    )
    module = importlib.import_module(AUDIT_MODULE)
    _require(
        Path(module.__file__).resolve() == path and sys.modules.get(AUDIT_MODULE) is module,
        "Actual immutable filesystem audit provider required",
        "bootstrap",
    )
    return module


class BootstrapAudit:
    """Reuse the reviewed write audit and add explicit bounded read domains."""

    def __init__(self, provider, output, filesystem, access):
        home = Path(filesystem["native_dot_directory"])
        link = filesystem["existing_native_dot_link"]
        target = home if link is None else Path(link["resolved"])
        self.writer = provider.WritePolicy(
            output, native_home=home, native_target=target, native_link=link, directories=()
        )
        self.roots = tuple(_path(value).resolve() for value in access["roots"])
        self.files = tuple(_path(value).resolve() for value in access["files"])
        self.reads, self.failures, self.first_error = [], [], None
        self.installed = False

    def audit(self, event, args):
        self.writer.audit(event, args)
        if event == "cells.original_INIT.filesystem_installed":
            if len(args) == 1 and args[0] is self:
                self.installed = True
            return
        if (
            event != "open"
            or type(args[2]) is not int
            or args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        ):
            return
        try:
            _require(len(self.reads) < 8192, "Bootstrap read audit bound", "filesystem")
            value = args[0]
            if type(value) is int:
                value = os.readlink(f"/proc/self/fd/{value}")
            _require(type(value) in (str, bytes), "Declared read pathname required", "filesystem")
            actual = Path(os.fsdecode(value)).absolute().resolve()
            self.reads.append(str(actual))
            _require(
                actual in self.files
                or any(actual == root or actual.is_relative_to(root) for root in self.roots),
                "Undeclared bootstrap/input read refused",
                "filesystem",
            )
        except BaseException as error:
            if self.first_error is None:
                self.first_error = error
            if len(self.failures) < 64:
                self.failures.append((event, args, error))
            raise

    def install(self):
        _require(not self.installed, "Filesystem audit installation is one-shot", "filesystem")
        _AUDITS.append(self)
        sys.addaudithook(self.audit)
        sys.audit("cells.seed_demo.filesystem_installed", self.writer)
        sys.audit("cells.original_INIT.filesystem_installed", self)
        _require(
            self.installed is True and self.writer.installed is True,
            "Actual enclosing filesystem audit installation required",
            "filesystem",
        )

    def check(self):
        self.writer.check()
        if self.first_error is not None:
            raise self.first_error
        _require(self.installed is True, "Filesystem audit was not installed", "filesystem")

    def record(self):
        return dict(
            installed=self.installed,
            write_policy=self.writer.record(),
            read_roots=[str(value) for value in self.roots],
            read_files=[str(value) for value in self.files],
            reads=list(self.reads),
            failures=[dict(event=event, error=_error(error)) for event, _, error in self.failures],
            first_error=_error(self.first_error),
            lifetime="through_worker_process_exit",
        )


def _filesystem(plan, authority, callback, output):
    access = authority["read_access"]
    declared = {str(_path(value).resolve()) for value in access["roots"]}
    required = {
        str(path.resolve())
        for path in (
            ROOT,
            Path(plan["native_root"]),
            Path(plan["inputs"]["root"]),
            output,
        )
    }
    _require(
        required <= declared, "Complete source/input/output read domains required", "bootstrap"
    )
    policy = BootstrapAudit(
        _audit_provider(), output, callback.source_plan()["filesystem_conflicts"], access
    )
    policy.install()
    policy.check()
    return policy


def prepare(output, *, input_pair, input_sha256, mode, native_root=NATIVE_ROOT):
    """Metadata only. Missing bootstrap/release authority remains explicit."""
    output = _path(output)
    _require(not output.exists(), "Fresh reference preparation required")
    original = source_inventory(native_root)
    selected = _input_manifest(input_pair, input_sha256, mode)
    selections = {}
    for relative in ("betse/science/sim.py", "betse/science/cells.py"):
        raw, _ = _read(Path(native_root) / relative, MAX_FILE_BYTES)
        _, selections[relative] = selected_tree(relative, raw, mode)
    output.mkdir(parents=True)
    if (ROOT / "SNAPSHOT.json").is_file():
        manifest = snapshot.verify(ROOT)
        frozen = ROOT
    else:
        starts = [
            FILE,
            TEST,
            RUNNER,
            *[name.replace(".", "/") + ".py" for name in WRITER_PRODUCERS],
            AUDIT_MODULE.replace(".", "/") + ".py",
        ]
        files = runpy.run_path(str(ROOT / CLOSURE))["closure"](ROOT, starts)
        files[CLOSURE] = snapshot.digest(ROOT / CLOSURE)
        frozen = output / "source"
        manifest = snapshot.freeze(ROOT, frozen, {name: name for name in files})
        snapshot.assert_checkout_unchanged(frozen)
    value = dict(
        kind=KIND,
        source_plan=source_plan(input_profile=selected["profile"]),
        native_root=str(_path(native_root)),
        native_inventory=original,
        native_inventory_sha256=_seal(original),
        inputs=selected,
        input_pair=str(_path(input_pair)),
        selections=selections,
        execution_source=dict(
            root=str(frozen),
            snapshot_sha256=snapshot.digest(frozen / "SNAPSHOT.json"),
            git_revision=manifest["git_revision"],
            owned_files={name: manifest["files"][name]["sha256"] for name in (FILE, TEST, RUNNER)},
        ),
        native_or_reference_calls=0,
        held=True,
    )
    snapshot.write_json(output / "prepared.json", value)
    return value


class OriginalPackage(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Compile exact original package bytes; no normalized science namespaces."""

    def __init__(self, root, inventory, mode):
        self.root, self.inventory, self.mode = _path(root), inventory, mode
        self.loaded, self.used = {}, False

    def find_spec(self, fullname, path=None, target=None):
        if fullname != "betse" and not fullname.startswith("betse."):
            return None
        stem = fullname.replace(".", "/")
        relative = stem + "/__init__.py"
        package = relative in self.inventory
        if not package:
            relative = stem + ".py"
        _require(relative in self.inventory, "Undeclared original module: " + fullname, "import")
        spec = importlib.util.spec_from_file_location(
            fullname,
            self.root / relative,
            loader=self,
            submodule_search_locations=[str(self.root / stem)] if package else None,
        )
        spec.loader_state = relative
        return spec

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        relative = module.__spec__.loader_state
        path = self.root / relative
        raw, _ = _read(path, MAX_FILE_BYTES)
        _require(_sha(raw) == self.inventory[relative]["sha256"], "Original module drift", "import")
        tree, changes = selected_tree(relative, raw, self.mode)
        self.loaded[module.__name__] = dict(path=str(path), sha256=_sha(raw), selections=changes)
        exec(compile(tree, str(path), "exec", dont_inherit=True), module.__dict__)

    def verify(self):
        for name, row in self.loaded.items():
            module = sys.modules.get(name)
            _require(
                module is not None
                and module.__loader__ is self
                and module.__file__ == row["path"]
                and snapshot.digest(Path(row["path"])) == row["sha256"],
                "Original loaded producer changed: " + name,
                "import",
            )

    def __enter__(self):
        _require(not self.used, "Original package workflow is one-shot", "import")
        _require(
            not any(n == "betse" or n.startswith("betse.") for n in sys.modules),
            "Fresh process with no preloaded original package required",
            "import",
        )
        self.used = True
        sys.meta_path.insert(0, self)
        return self

    def __exit__(self, kind, error, tb):
        if self in sys.meta_path:
            sys.meta_path.remove(self)
        return False


@dataclass
class State:
    stage: str = "preflight"
    primary: object = None
    secondary: list = field(default_factory=list)
    raw: dict = field(default_factory=dict)
    work: list = field(default_factory=list)
    sites: dict = field(default_factory=dict)
    captures: list = field(default_factory=list)
    capture_error: object = None
    native_unwind: object = None
    iterations: list = field(default_factory=list)
    source_returned: bool = False
    hooks_restored: bool = False
    observer_used: bool = False
    coverage_failed: bool = False
    initial_rng_observation: object = None


def _error(error):
    if error is None:
        return None
    # Retain raw exception objects separately; this is a bounded identity/cause
    # record, not an assertion that arbitrary failed native owners serialize.
    result, current, seen = [], error, set()
    while current is not None and id(current) not in seen and len(result) < 16:
        seen.add(id(current))
        frames, tb = [], current.__traceback__
        while tb is not None and len(frames) < 32:
            frames.append(
                dict(
                    file=tb.tb_frame.f_code.co_filename,
                    line=tb.tb_lineno,
                    function=tb.tb_frame.f_code.co_name,
                )
            )
            tb = tb.tb_next
        result.append(
            dict(
                type=type(current).__module__ + "." + type(current).__qualname__,
                identity=id(current),
                arguments=[
                    arg
                    if arg is None or type(arg) in (str, int, bool)
                    else dict(opaque_argument_type=type(arg).__name__)
                    for arg in current.args
                ],
                traceback=frames,
                complete_raw_exception_serialization=False,
            )
        )
        current = current.__cause__ if current.__cause__ is not None else current.__context__
    return result


def _secondary(state, label, error):
    state.secondary.append((label, error))
    if state.capture_error is None:
        state.capture_error = error


def _attempt(state, label, function, *args):
    """Protect the invocation boundary, including inherited observer rejection."""
    try:
        return True, function(*args)
    except BaseException as error:
        _secondary(state, label, error)
        return False, None


def _stop(state):
    if state.primary is not None:
        raise state.primary
    if state.capture_error is not None:
        if state.native_unwind is not None:
            raise state.native_unwind
        raise ReferenceRejected(
            "Observation failed; no later source entry", stage="capture", partial=state
        ) from state.capture_error


def comparator_ast_sha256(raw):
    """The existing consumer removes four review assignments, not their values."""
    tree = ast.parse(raw)
    kept, pins = [], set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and all(isinstance(t, ast.Name) for t in node.targets):
            names = {t.id for t in node.targets}
            if names <= REVIEW_PIN_NAMES:
                value = ast.literal_eval(node.value)
                _require(value is None or _pin(value), "Typed review pin required")
                pins.update(names)
                continue
        kept.append(node)
    _require(pins == REVIEW_PIN_NAMES, "Complete review-pin assignment roster required")
    tree.body = kept
    return _sha(ast.dump(tree, include_attributes=False).encode())


def capture_budget(value):
    """Refuse oversized observations before the wire clones arrays or builds hex.

    Each wire column occurrence is charged, including repeated references.
    No array bytes, object values or aliases are changed. The aggregate column
    bound is deliberately conservative: it uses the existing unique-byte cap
    even when the transport could later deduplicate repeated byte strings.
    This bounds observation allocations, not the original model's memory.
    """
    import numpy as np

    counts = dict(
        nodes=0, columns=0, column_bytes=0, metadata_upper_bytes=0, inline_hex_bytes=0, wire_depth=0
    )
    active = set()

    def check(condition, message):
        if not condition:
            error = ReferenceRejected("Observation preflight: " + message, stage="capture")
            error.capture_budget = dict(counts=counts.copy(), limits=dict(CAPTURE_LIMITS))
            raise error

    def charge(metadata):
        counts["metadata_upper_bytes"] += metadata
        check(
            counts["metadata_upper_bytes"] <= CAPTURE_LIMITS["metadata_upper_bytes"],
            "aggregate metadata upper bound",
        )

    def nodes(number, depth):
        counts["nodes"] += number
        counts["wire_depth"] = max(counts["wire_depth"], depth)
        check(
            depth <= CAPTURE_LIMITS["depth"] and counts["nodes"] <= CAPTURE_LIMITS["nodes"],
            "encoded wire node/depth bound",
        )
        # Includes fixed wire keys/values and pretty-print indentation, plus
        # the outer transport envelope. Variable text/hex is charged below.
        charge(number * (128 + 2 * (depth + 2)))

    def visit(item, depth=1):
        nodes(3, depth + 1)  # Typed node dict, type leaf and value/list leaf.
        child_depth = depth + 2
        if isinstance(item, np.ndarray):
            check(item.ndim <= 32, "array rank bound")
            if not item.dtype.hasobject:
                # Array layout, column record and shape/stride leaves. Column
                # records are rooted separately, so this depth is conservative.
                nodes(11 + 3 * item.ndim, depth + 3)
                size = item.nbytes
                counts["columns"] += 1
                counts["column_bytes"] += size
                check(size <= CAPTURE_LIMITS["column_bytes"], "single raw column bound")
                check(
                    counts["column_bytes"] <= CAPTURE_LIMITS["total_column_bytes"],
                    "aggregate raw column bound",
                )
                if size < evidence.payload.THRESHOLD:
                    counts["inline_hex_bytes"] += 2 * size
                    charge(2 * size)
                else:
                    nodes(6, 4)  # Conservative per-occurrence sidecar manifest.
                return
            nodes(6 + 2 * item.ndim, depth + 3)
            children = item.flat
        elif isinstance(item, np.generic):
            nodes(1, depth + 1)
            size = 2 * item.dtype.itemsize + 256
            check(size <= CAPTURE_LIMITS["atomic_metadata_upper_bytes"], "scalar metadata bound")
            charge(size)
            return
        elif type(item) is str:
            size = 12 * len(item) + 256  # ensure_ascii surrogate pairs use12 chars.
            check(size <= CAPTURE_LIMITS["atomic_metadata_upper_bytes"], "string metadata bound")
            charge(size)
            return
        elif type(item) is int:
            # A decimal representation uses fewer characters than the bit count.
            charge(item.bit_length() + 256)
            return
        elif item is None or type(item) in (float, bool):
            return
        elif isinstance(item, dict):
            check(len(item) <= CAPTURE_LIMITS["nodes"], "dictionary entry bound")
            if item:
                nodes(len(item), depth + 2)  # Ordered key/value pair lists.
            child_depth = depth + 3
            children = (part for pair in item.items() for part in pair)
        elif isinstance(item, (list, tuple, set, frozenset)):
            check(len(item) <= CAPTURE_LIMITS["nodes"], "sequence entry bound")
            children = iter(item)
        else:
            check(False, "unsupported wire value " + type(item).__name__)
        identity = id(item)
        check(identity not in active, "cyclic wire value")
        active.add(identity)
        try:
            for child in children:
                visit(child, child_depth)
        finally:
            active.remove(identity)

    nodes(10, 3)  # Wire roots and fixed transport-envelope/list overhead.
    visit(value)
    return dict(counts=counts, limits=dict(CAPTURE_LIMITS))


def typed(value):
    """Use the independent existing wire encoder and lossless sidecar format."""
    from validation.betse import betse_initial_mesh_preparation_wire as wire

    capture_budget(value)
    captured = wire.validate(wire.capture(value))
    return dict(
        tree=captured["tree"],
        columns={
            name: dict(
                dtype=array.dtype.str, shape=list(array.shape), raw_bytes_hex=array.tobytes().hex()
            )
            for name, array in captured["columns"].items()
        },
    )


def object_evidence(roots):
    """Read actual object dictionaries/array edges, never deserialize an owner.

    External opaque objects are explicitly listed rather than projected into
    invented numerical authority. Native/network dictionaries remain reached.
    Identity labels are process-local forensic facts, not comparison keys.
    """
    import numpy as np

    nodes, seen, opaque = [], {}, []
    budget = dict(visits=0, metadata_upper_bytes=0)

    def visit(value, depth=0):
        # Scalars do not enter ``nodes``. Charge every edge before constructing
        # its projection so a large scalar container cannot evade MAX_SITES.
        budget["visits"] += 1
        budget["metadata_upper_bytes"] += 256 + (12 * len(value) if type(value) is str else 0)
        if (
            depth > CAPTURE_LIMITS["depth"]
            or budget["visits"] > CAPTURE_LIMITS["nodes"]
            or budget["metadata_upper_bytes"] > CAPTURE_LIMITS["metadata_upper_bytes"]
        ):
            error = ReferenceRejected("Observation graph preflight bound", stage="capture")
            error.capture_budget = dict(counts=budget.copy(), limits=dict(CAPTURE_LIMITS))
            raise error
        if value is None or type(value) in (str, bool, int, float) or isinstance(value, np.generic):
            return dict(scalar=value)
        identity = id(value)
        if identity in seen:
            return dict(reference=seen[identity])
        _require(len(nodes) < MAX_SITES, "Native observation graph bound", "capture")
        index = len(nodes)
        seen[identity] = index
        node = dict(identity=identity, type=type(value).__module__ + "." + type(value).__qualname__)
        nodes.append(node)
        if isinstance(value, np.ndarray):
            node.update(
                shape=list(value.shape),
                strides_bytes=list(value.strides),
                dtype=value.dtype.str,
                base=visit(value.base, depth + 1),
            )
            if value.dtype.hasobject:
                node["items"] = [visit(item, depth + 1) for item in value.flat]
            else:
                node["value"] = value
        elif type(value) is dict:
            node["items"] = [
                (visit(key, depth + 1), visit(item, depth + 1)) for key, item in value.items()
            ]
        elif type(value) in (list, tuple, set, frozenset):
            node["items"] = [visit(item, depth + 1) for item in value]
        elif type(value).__module__.startswith("betse.") and hasattr(value, "__dict__"):
            node["fields"] = [(key, visit(item, depth + 1)) for key, item in vars(value).items()]
        else:
            node["opaque"] = True
            opaque.append(index)
        return dict(reference=index)

    entries = [(role, visit(value)) for role, value in roots.items()]
    return dict(
        roots=entries,
        nodes=nodes,
        opaque_nodes=opaque,
        complete_object_serialization=False,
        owner_hydration=False,
    )


class Archive:
    def __init__(self, folder, state):
        self.folder, self.state = _path(folder), state
        self.folder.mkdir()

    def save(self, label, value):
        row = dict(label=label, status="attempted")
        self.state.captures.append(row)
        path = self.folder / (f"capture-{len(self.state.captures):04d}.json")
        try:
            files = evidence.write(path, typed(value), label=label)
        except BaseException as error:
            self.state.raw["failed_archive"] = dict(label=label, value=value)
            row.update(status="capture_failed", error=_error(error))
            if isinstance(error, ReferenceRejected) and "capture_budget" in vars(error):
                row["preallocation_refusal"] = error.capture_budget
            raise
        row.update(status="saved", files=files)
        return dict(path=str(path), sha256=snapshot.digest(path))


class FreshSeed:
    """A native save/load token, never an external pickle/restart interface."""

    def __init__(self, path, config_root):
        self.path, self.root = _path(path), _path(config_root)
        _require(self.path.is_relative_to(self.root), "Seed path escaped fresh config", "seed")
        _require(not self.path.exists(), "External/preexisting seed refuses", "seed")
        self.saved = self.loaded = False
        self.record = None
        self.attempts = []

    def saved_return(self):
        _require(not self.saved and not self.loaded, "Seed save is one-shot", "seed")
        raw, identity = _read(self.path, MAX_SEED_BYTES)
        self.record = dict(
            path=str(self.path), sha256=_sha(raw), size_bytes=len(raw), identity=list(identity)
        )
        self.saved = True
        return self.record

    def before_load(self, path):
        self.attempts.append(dict(kind="loadWorld", path=str(path), admitted=False))
        _require(
            self.saved and not self.loaded and _path(path) == self.path,
            "Only this workflow's fresh completed seed may load",
            "seed",
        )
        self.check()
        # Consume before any original compatibility/unpickle helper can run.
        self.loaded = True
        self.attempts[-1]["admitted"] = True

    def check(self):
        _require(self.record is not None, "Native seed has not completed", "seed")
        raw, identity = _read(self.path, MAX_SEED_BYTES)
        _require(
            self.record
            == dict(
                path=str(self.path), sha256=_sha(raw), size_bytes=len(raw), identity=list(identity)
            ),
            "Fresh seed bytes/path/inode epoch changed",
            "seed",
        )


def _loop_line(root):
    raw, _ = _read(root / "betse/science/sim.py", MAX_FILE_BYTES)
    _require(_sha(raw) == CRITICAL["betse/science/sim.py"], "Original solver changed")
    method = _method(ast.parse(raw), "Simulator", "_run_sim_core_loop")
    nodes = [n for n in method.body if isinstance(n, ast.For)]
    _require(
        len(nodes) == 1 and ast.unparse(nodes[0].iter) == "time_steps",
        "Unique original full calendar loop required",
    )
    return nodes[0].lineno


class Observe:
    """Count native work and retain selected raw boundaries without replay."""

    def __init__(self, state, root, archive, seed, loop_line):
        self.state, self.root, self.archive, self.seed = state, str(_path(root)), archive, seed
        self.loop_line, self.admitted, self.pending = loop_line, {}, {}
        self.local_traces, self.profile, self.trace = {}, None, None
        self.sequence = 0
        self.managed, self.invalid, self.controls = False, False, None
        self.coverage_stop = ReferenceRejected(
            "Observer coverage failed", stage="observer", partial=state
        )
        self.capture_stop = ReferenceRejected(
            "Observation failed; no later source entry", stage="capture", partial=state
        )

    def _native(self, frame):
        filename = frame.f_code.co_filename
        return filename.startswith(self.root + os.sep)

    def _entry(self, frame):
        if self.invalid:
            raise self.state.primary if self.state.primary is not None else self.coverage_stop
        key = id(frame)
        if key in self.admitted:
            return
        _stop(self.state)
        name, module = frame.f_code.co_name, frame.f_globals.get("__name__")
        _require(name != "_pickle_phase", "INIT/SIM pickle is beyond reference endpoint", "entry")
        _require(
            not (module == "betse.science.simrunner" and name == "sim"),
            "SIM continuation is not admitted",
            "entry",
        )
        if module == "betse.science.filehandling" and name == "loadWorld":
            self.seed.before_load(frame.f_locals.get("loadPath"))
        self.admitted[key] = frame
        self.sequence += 1
        site = (module, name, frame.f_code.co_firstlineno, self.state.stage)
        if site not in self.state.sites:
            _require(len(self.state.sites) < MAX_SITES, "Native site-count bound", "work")
            self.state.sites[site] = [0, 0, self.sequence, self.sequence]
        self.state.sites[site][0] += 1
        self.state.sites[site][3] = self.sequence
        if name in SELECTED.get(module, ()):
            _require(len(self.state.work) < MAX_WORK, "Ordered native boundary bound", "work")
            self.state.work.append((self.sequence, self.state.stage, module, name, "enter"))

    def _return(self, frame, value):
        module, name = frame.f_globals.get("__name__"), frame.f_code.co_name
        key = id(frame)
        if key not in self.admitted:
            return
        self.admitted.pop(key)
        site = (module, name, frame.f_code.co_firstlineno, self.state.stage)
        self.state.sites[site][1] += 1
        error = self.pending.pop(key, None)
        if error is not None:
            self.state.native_unwind = error
        if name not in SELECTED.get(module, ()):
            return
        self.state.raw[(module, name)] = dict(frame.f_locals)
        self.state.raw[(module, name, "return")] = value
        if module == "betse.science.cells" and name == "save_cluster" and error is None:
            _attempt(self.state, "seed_save_return", self.seed.saved_return)
        if module == "betse.science.filehandling" and name == "loadWorld" and error is None:
            _attempt(self.state, "seed_load_return", self.seed.check)
        if module == "betse.science.sim" and name == "_plot_loop" and error is None:
            _attempt(
                self.state, "calendar_capture", self.archive.save, "original_calendar", value[:2]
            )
        if module == "betse.science.sim" and name == "run_sim_core":
            instability = frame.f_locals.get("exception_instability")
            if instability is not None:
                self.state.primary = instability
            self.state.source_returned = error is None and instability is None
        _require(len(self.state.work) < MAX_WORK, "Ordered native boundary bound", "work")
        self.state.work.append(
            (
                self.sequence,
                self.state.stage,
                module,
                name,
                "unwind" if error is not None else "return",
            )
        )

    def _iteration(self, frame):
        local = frame.f_locals
        if "t" not in local:
            return
        ordinal = len(self.state.iterations) + 1
        _require(
            ordinal <= MAX_ITERATIONS, "Original calendar exceeds observation capacity", "work"
        )
        phase, sim = local["phase"], local["self"]
        # All observations read the actual continuing objects; never seed/reset.
        row = dict(
            ordinal=ordinal,
            source_time=local["t"],
            sampled=local["t"] in local["time_steps_sampled"],
            configured_dt=phase.p.dt,
            fields={name: vars(sim)[name] for name in ITERATION_FIELDS if name in vars(sim)},
            numpy_random=frame.f_globals["np"].random.get_state(),
            python_random=random.getstate(),
        )
        self.state.raw["last_iteration"] = row
        saved = self.archive.save(f"iteration_{ordinal:04d}", row)
        self.state.iterations.append(saved)

    def _recover(self):
        if not self.managed:
            return
        setters, getters = self.controls
        actual = getters[0](), getters[1]()
        if actual[0] is self.profile and actual[1] is self.trace:
            return
        errors = [("observer_hooks_changed", self.coverage_stop)]
        for setter, required, label in zip(
            setters, (self.profile, self.trace), ("profile_recovery", "trace_recovery"), strict=True
        ):
            try:
                setter(required)
            except BaseException as error:
                errors.append((label, error))
        observed_hooks = []
        for getter, label in zip(getters, ("profile_identity", "trace_identity"), strict=True):
            try:
                observed_hooks.append(getter())
            except BaseException as error:
                errors.append((label, error))
                observed_hooks.append(None)
        # No fallible reporting helper is entered while coverage is uncertain.
        self.state.secondary.extend(errors)
        if self.state.capture_error is None:
            self.state.capture_error = errors[0][1]
        if observed_hooks[0] is not self.profile or observed_hooks[1] is not self.trace:
            self.invalid = self.state.coverage_failed = True
            if self.state.primary is None:
                self.state.primary = (
                    self.state.native_unwind
                    if self.state.native_unwind is not None
                    else self.coverage_stop
                )
            raise self.state.primary

    def _capture(self, label, error):
        # Primitive retention comes before recovery; no reporting helper is
        # entered while a rejecting callback may have removed both hooks.
        self.state.secondary.append((label, error))
        if self.state.capture_error is None:
            self.state.capture_error = error
        self._recover()

    def install(self):
        previous_profile, previous_trace = sys.getprofile(), sys.gettrace()
        self.controls = (sys.setprofile, sys.settrace), (sys.getprofile, sys.gettrace)

        def profile(frame, event, arg):
            native = self._native(frame)
            if (
                native
                and event == "c_call"
                and (self.state.primary is not None or self.state.capture_error is not None)
            ):
                # A completed Python helper may have failed observation on
                # return. Refuse the following C mutation even on the same
                # source line, retaining the exact unentered boundary.
                self.state.raw["blocked_native_boundary"] = dict(
                    frame=frame, event=event, callable=arg, body_entered=False
                )
                _stop(self.state)
            if native and event == "call":
                self._entry(frame)
            if native and event == "return":
                error = self.pending.get(id(frame))
                if error is not None:
                    self.state.native_unwind = error
            if previous_profile is not None:
                try:
                    previous_profile(frame, event, arg)
                except BaseException as capture:
                    if event == "return":
                        self._capture("inherited_profile_" + event, capture)
                    else:
                        if self.state.primary is None:
                            self.state.primary = (
                                self.state.native_unwind
                                if self.state.native_unwind is not None
                                else capture
                            )
                        if self.state.primary is not capture:
                            self.state.secondary.append(("inherited_profile_" + event, capture))
                        self._recover()
                        # Do not replace the original source's explicit cause
                        # with the distinct observer/entry rejection.
                        raise self.state.primary  # noqa: B904
                self._recover()
            if native and event == "call":
                _stop(self.state)
            if native and event == "return":
                try:
                    self._return(frame, arg)
                except BaseException as capture:
                    self._capture("native_return_observation", capture)

        def trace(frame, event, arg):
            native = self._native(frame)
            if (
                native
                and event == "line"
                and (self.state.primary is not None or self.state.capture_error is not None)
            ):
                # Keep an active source unwind before the normal-line logic
                # clears it. No inherited callback or native body follows.
                self.state.raw["blocked_native_boundary"] = dict(
                    frame=frame, event=event, body_entered=False
                )
                _stop(self.state)
            if native and event == "call":
                self._entry(frame)
            if native and event == "exception":
                self.pending[id(frame)] = arg[1]
                self.state.native_unwind = arg[1]
            inherited = previous_trace if event == "call" else self.local_traces.get(id(frame))
            if inherited is not None:
                try:
                    result = inherited(frame, event, arg)
                except BaseException as capture:
                    if event in ("return", "exception"):
                        self._capture("inherited_trace_" + event, capture)
                        result = inherited
                    else:
                        if self.state.primary is None:
                            self.state.primary = (
                                self.state.native_unwind
                                if self.state.native_unwind is not None
                                else capture
                            )
                        if self.state.primary is not capture:
                            self.state.secondary.append(("inherited_trace_" + event, capture))
                        self._recover()
                        raise self.state.primary  # noqa: B904 - preserve original cause
                self._recover()
                if result is None:
                    self.local_traces.pop(id(frame), None)
                else:
                    self.local_traces[id(frame)] = result
            if native:
                if event == "call":
                    _stop(self.state)
                elif event == "line":
                    self.pending.pop(id(frame), None)
                    self.state.native_unwind = None
                    if (
                        frame.f_code.co_name == "_run_sim_core_loop"
                        and frame.f_lineno == self.loop_line
                    ):
                        try:
                            self._iteration(frame)
                        except BaseException as capture:
                            self._capture("iteration_capture", capture)
                        # This FOR_ITER line observes the preceding completed
                        # body. Stop here, before advancing t or resetting any
                        # next-step arrays, not only at a later Python call.
                        _stop(self.state)
            if event == "return":
                self.local_traces.pop(id(frame), None)
            return trace

        self.profile, self.trace = profile, trace
        return previous_profile, previous_trace


@contextmanager
def observed(observer):
    """Both setters/restores are protected at their caller boundaries."""
    state = observer.state
    old_profile, old_trace = observer.install()
    setters, getters = (sys.setprofile, sys.settrace), (sys.getprofile, sys.gettrace)
    state.observer_used = True
    cleanup = []
    try:
        setters[0](observer.profile)
        setters[1](observer.trace)
        _require(
            getters[0]() is observer.profile and getters[1]() is observer.trace,
            "Both source observers required",
            "observer",
        )
        observer.managed = True
        yield
    except BaseException as error:
        if state.primary is None:
            state.primary = state.native_unwind if state.native_unwind is not None else error
        elif state.primary is not error:
            cleanup.append(("source_or_observer_exit", error))
    finally:
        observer.managed = False
        for label, setter, prior in zip(
            ("profile_restore", "trace_restore"), setters, (old_profile, old_trace), strict=True
        ):
            try:
                setter(prior)
            except BaseException as restore_error:
                # Keep primitive records only; a reporting helper must not
                # prevent the other restoration or replace the source error.
                state.secondary.append((label, restore_error))
                if state.capture_error is None:
                    state.capture_error = restore_error
        final_hooks = []
        for getter, label in zip(
            getters, ("final_profile_identity", "final_trace_identity"), strict=True
        ):
            try:
                final_hooks.append(getter())
            except BaseException as error:
                final_hooks.append(None)
                cleanup.append((label, error))
        state.hooks_restored = final_hooks[0] is old_profile and final_hooks[1] is old_trace
        if not state.hooks_restored:
            cleanup.append(("final_observer_identity", observer.coverage_stop))
            state.coverage_failed = True
        state.secondary.extend(cleanup)
        if state.capture_error is None and cleanup:
            state.capture_error = cleanup[0][1]
    if state.primary is not None:
        raise state.primary
    if state.capture_error is not None:
        if state.native_unwind is not None:
            raise state.native_unwind
        raise observer.capture_stop from state.capture_error


def _retain_native(state, archive):
    if archive is not None and state.raw:
        retained = object_evidence(state.raw)
        archive.save("retained_native_partials", retained)


def _package_execution(package, observer, execute):
    """Independently protect import-loader exit and both inherited hooks."""
    state = observer.state
    setters, getters = (sys.setprofile, sys.settrace), (sys.getprofile, sys.gettrace)
    required = getters[0](), getters[1]()
    state.raw["required_inherited_hooks"] = required
    state.observer_used = True
    entered = False
    try:
        package.__enter__()
        entered = True
        actual = getters[0](), getters[1]()
        _require(
            actual[0] is required[0] and actual[1] is required[1],
            "Package entry changed required inherited coverage",
            "observer",
        )
        with observed(observer):
            execute()
    except BaseException as error:
        if state.primary is None:
            state.primary = state.native_unwind if state.native_unwind is not None else error
        elif state.primary is not error:
            state.secondary.append(("package_execution", error))
    finally:
        if entered:
            try:
                package.__exit__(
                    None if state.primary is None else type(state.primary), state.primary, None
                )
            except BaseException as error:
                if state.primary is None:
                    state.primary = error
                else:
                    state.secondary.append(("package_exit", error))
        try:
            # __exit__ may have been rejected before its body. Remove only
            # this actual loader by identity; never reset imported modules.
            sys.meta_path[:] = [item for item in sys.meta_path if item is not package]
        except BaseException as error:
            state.secondary.append(("import_loader_cleanup", error))
            if state.capture_error is None:
                state.capture_error = error
        for setter, previous, label in zip(
            setters, required, ("outer_profile_restore", "outer_trace_restore"), strict=True
        ):
            try:
                setter(previous)
            except BaseException as error:
                state.secondary.append((label, error))
                if state.capture_error is None:
                    state.capture_error = error
        final = []
        for getter, label in zip(
            getters, ("outer_profile_identity", "outer_trace_identity"), strict=True
        ):
            try:
                final.append(getter())
            except BaseException as error:
                final.append(object())
                state.secondary.append((label, error))
                if state.capture_error is None:
                    state.capture_error = error
        state.hooks_restored = final[0] is required[0] and final[1] is required[1]
        state.coverage_failed = state.coverage_failed or not state.hooks_restored
    if state.primary is not None:
        raise state.primary
    if not state.hooks_restored:
        raise observer.coverage_stop
    if state.capture_error is not None:
        raise observer.capture_stop from state.capture_error


def _forensic_finish(state, archive, session, entered, selected, output, filesystem=None):
    if state.observer_used and not state.hooks_restored:
        # Defensive private-entry refusal. evaluate never even calls this
        # helper on that path; preserve falsey original errors by identity.
        if state.primary is not None:
            raise state.primary
        raise ReferenceRejected(
            "Forensic callbacks require restored coverage", stage="observer", partial=state
        )
    if entered:
        try:
            session.__exit__(
                None if state.primary is None else type(state.primary), state.primary, None
            )
        except BaseException as error:
            if state.primary is None:
                state.primary = error
            else:
                state.secondary.append(("writer_session_check", error))
    if selected is not None:
        try:
            _require(
                inputs.inventory(Path(selected["root"])) == selected["inventory"],
                "Immutable prepared inputs changed during execution",
                "input_after",
            )
        except BaseException as error:
            if state.primary is None:
                state.primary = error
            else:
                state.secondary.append(("prepared_inputs_after", error))
    try:
        _retain_native(state, archive)
    except BaseException as capture:
        state.secondary.append(("retained_native_partials", capture))
        if state.capture_error is None:
            state.capture_error = capture
    try:
        from validation.betse import betse_normal_channel_join_runtime as runtime

        snapshot.write_json(output / "runtime.json", runtime.inventory())
    except BaseException as capture:
        state.secondary.append(("runtime_inventory", capture))
        if state.capture_error is None:
            state.capture_error = capture
    if filesystem is not None:
        try:
            filesystem.check()
        except BaseException as error:
            if state.primary is None:
                state.primary = error
            else:
                state.secondary.append(("filesystem_final_check", error))
        try:
            snapshot.write_json(output / "filesystem.json", filesystem.record())
        except BaseException as error:
            state.secondary.append(("filesystem_record", error))
            if state.capture_error is None:
                state.capture_error = error


def _workflow(plan, state, archive, seed):
    """Whole original caller path, only reachable after explicit future release."""
    state.stage = "original_bootstrap"
    app = importlib.import_module("betse.appmeta").BetseAppMeta()
    state.raw["appmeta"] = app
    app.init_libs(matplotlib_backend_name="Agg")
    state.stage = "original_parameters"
    parameters = importlib.import_module("betse.science.parameters").Parameters
    p = parameters.make(str(Path(plan["inputs"]["root"]) / profiles.MAIN))
    state.raw["parameters"] = p
    for name, expected in inputs._program(
        Path(plan["inputs"]["root"]), _reference_profile(plan["source_plan"]["input_profile"])
    )["ordered_path_permission"]:
        _require(
            getattr(p, name) == expected,
            "Original native path escaped the execution copy: " + name,
            "native_paths",
        )
    _require(_path(p.seed_pickle_filename) == seed.path, "Original seed filename changed", "seed")
    state.stage = "original_runner"
    runner = importlib.import_module("betse.science.simrunner").SimRunner(p)
    state.raw["runner"] = runner
    _capture_initial_rng(plan, state, archive)
    state.stage = "SEED"
    seed_phase = runner.seed()
    state.raw["seed_phase"] = seed_phase
    _stop(state)
    _require(seed.saved, "Original seed save did not complete", "seed")
    state.stage = "INIT"
    phase = runner.init()
    state.raw["init_phase"] = phase
    _stop(state)
    _require(
        phase.p is p and seed.loaded and state.source_returned,
        "Genuine same-p INIT caller/source completion required",
        "completion",
    )
    _require(
        len(state.iterations) == p.init_tsteps,
        "Complete original calendar required; no selected stop",
        "completion",
    )
    archive.save(
        "final_iteration_fields",
        {name: vars(phase.sim)[name] for name in ITERATION_FIELDS if name in vars(phase.sim)},
    )
    archive.save(
        "final_calendar_configuration",
        dict(
            init_tsteps=p.init_tsteps,
            init_time_total=p.init_time_total,
            init_time_step=p.init_time_step,
            dt=p.dt,
        ),
    )
    archive.save(
        "final_native_object_evidence",
        object_evidence(
            dict(
                phase=phase,
                parameters=p,
                cells=phase.cells,
                simulator=phase.sim,
                dyna=phase.dyna,
            )
        ),
    )
    state.stage = "completed_before_INIT_pickle"
    return phase


def evaluate(
    prepared, expected_sha256, output, *, release=None, release_sha256=None, enabled=False
):
    """Forensic envelope exists before release, imports, factory or observations."""
    state, output = State(), _path(output)
    _require(not output.exists(), "Fresh isolated reference output required")
    output.mkdir(parents=True)
    archive, package, seed, session, selected, filesystem = None, None, None, None, None, None
    session_entered = False
    global _ATTEMPT
    try:
        raw, _ = _read(prepared, 16 * 2**20)
        _require(_sha(raw) == expected_sha256, "Prepared reference bytes changed")
        plan = json.loads(raw)
        _require(
            plan.get("kind") == KIND and plan.get("held") is True,
            "Exact held source preparation required",
        )
        _require(
            plan["source_plan"]
            == source_plan(input_profile=plan["inputs"].get("profile", profiles.HEADLESS)),
            "Source/adoption plan changed",
        )
        authority, demo, callback = _release(
            plan, expected_sha256, release, release_sha256, output, enabled
        )
        producer = plan["execution_source"]
        _require(ROOT == Path(producer["root"]), "Worker must use the prepared immutable source")
        manifest = snapshot.verify(ROOT, manifest_sha256=producer["snapshot_sha256"])
        _require(
            all(
                manifest["files"][name]["sha256"] == pin == snapshot.digest(ROOT / name)
                for name, pin in producer["owned_files"].items()
            ),
            "Exact prepared reference producers required",
        )
        _resources()
        _require(_ATTEMPT is None, "Reference execution requires a fresh worker", "consumed")
        _ATTEMPT = state
        _require(
            output.is_relative_to(Path("/mnt/workspaces/Cells"))
            and not output.is_relative_to(ROOT),
            "Contained reference output required",
        )
        _require(
            snapshot.digest(ROOT / "validation/betse/native_seed_demo_evidence.py")
            == EVIDENCE_SHA256,
            "Reviewed evidence transport changed",
        )
        selected = _input_manifest(
            plan["input_pair"], plan["inputs"]["manifest_sha256"], plan["inputs"]["mode"]
        )
        _require(selected == plan["inputs"], "Fresh selected inputs changed")
        inventory = source_inventory(plan["native_root"])
        _require(
            inventory == plan["native_inventory"]
            and _seal(inventory) == plan["native_inventory_sha256"],
            "Native tree drift",
        )
        session = demo._writer_session(callback, authority["reviews"]["writer"]["path"])
        _require(type(session) is demo.ProcessLogLease, "Original process log lease required")
        state.raw["shared_writer_session"] = session
        session.__enter__()
        session_entered = True
        filesystem = _filesystem(plan, authority, callback, output)
        state.raw["filesystem_audit"] = filesystem
        mpl = output / "mplconfig"
        _require(
            os.environ.get("MPLCONFIGDIR") == str(mpl) and not mpl.exists(),
            "Fresh explicitly declared MPLCONFIGDIR required",
            "bootstrap",
        )
        mpl.mkdir(mode=0o700)
        copied = execution_copy(selected, output / "config", state)
        execution = dict(
            plan, inputs=dict(selected, root=copied["root"]), rng_policy=authority["rng_policy"]
        )
        archive = Archive(output / "captures", state)
        snapshot.write_json(output / "execution-inputs.json", copied)
        seed = FreshSeed(Path(copied["root"]) / "INITS/world_1.betse.gz", copied["root"])
        package = OriginalPackage(plan["native_root"], inventory, selected["mode"])
        observer = Observe(
            state, plan["native_root"], archive, seed, _loop_line(Path(plan["native_root"]))
        )
        _package_execution(package, observer, lambda: _workflow(execution, state, archive, seed))
        package.verify()
        filesystem.check()
    except BaseException as primary:
        if state.primary is None:
            state.primary = primary
        elif state.primary is not primary:
            state.secondary.append(("outer_failure", primary))
    finally:
        # A secondary serialization/runtime failure never replaces source cause.
        if state.observer_used:
            required = state.raw.get("required_inherited_hooks")
            try:
                actual = sys.getprofile(), sys.gettrace()
                state.hooks_restored = (
                    required is not None and actual[0] is required[0] and actual[1] is required[1]
                )
            except BaseException as error:
                state.hooks_restored = False
                state.secondary.append(("before_forensics_hook_identity", error))
            state.coverage_failed = state.coverage_failed or not state.hooks_restored
        if not state.observer_used or state.hooks_restored:
            try:
                _forensic_finish(
                    state, archive, session, session_entered, selected, output, filesystem
                )
            except BaseException as error:
                state.secondary.append(("forensic_boundary", error))
                if state.capture_error is None:
                    state.capture_error = error
    if state.observer_used and not state.hooks_restored:
        # Never invoke another forensic/runtime/reporting callback uncovered.
        # The supervising guard retains the terminal process failure; raw state
        # remains attached to the original primary where assignment is possible.
        _RAW_FAILURES.append(state)
        primary = state.primary if state.primary is not None else state.capture_error
        if primary is not None:
            try:
                primary.reference_partial = state
            except BaseException as error:
                state.secondary.append(("uncovered_partial_attachment", error))
            raise primary
        raise ReferenceRejected(
            "Observer coverage could not be restored", stage="observer", partial=state
        )
    try:
        result = dict(
            kind=KIND,
            status="completed"
            if state.primary is None
            and state.capture_error is None
            and state.source_returned
            and state.hooks_restored
            else "failed",
            stage=state.stage,
            primary=_error(state.primary),
            capture_errors=[
                dict(stage=label, error=_error(error)) for label, error in state.secondary
            ],
            work=state.work,
            work_sites=[
                dict(site=list(site), counts=counts) for site, counts in state.sites.items()
            ],
            iterations=state.iterations,
            initial_rng_observation=state.initial_rng_observation,
            captures=state.captures,
            seed=None if seed is None else dict(record=seed.record, attempts=seed.attempts),
            source_returned=state.source_returned,
            inherited_hooks_restored=state.hooks_restored,
            observer_coverage_failed=state.coverage_failed,
            filesystem_audit_installed=filesystem is not None and filesystem.installed is True,
            native_producers={} if package is None else package.loaded,
            raw_objects_serialized_completely=False,
            ordinary_checkpoint_physical_or_numerical_credit=0,
        )
        snapshot.write_json(output / "result.json", result)
    except BaseException as secondary:
        state.secondary.append(("result_write", secondary))
        if state.capture_error is None:
            state.capture_error = secondary
        _RAW_FAILURES.append(state)
        cause = state.primary if state.primary is not None else secondary
        raise ReferenceRejected(
            "Forensic result sealing failed", stage="result", partial=state
        ) from cause
    if result["status"] != "completed":
        _RAW_FAILURES.append(state)
    return result


def supervise(prepared, prepared_sha256, release, release_sha256, output, *, enabled=False):
    """Resource controller for Root's future detached release; never auto-runs."""
    from validation.betse import betse_mesh_lifecycle_preparation_guard as guard

    output = _path(output)
    _require(not output.exists(), "Fresh detached controller output required")
    plan = _json_record(prepared, prepared_sha256, limit=16 * 2**20)
    _release(plan, prepared_sha256, release, release_sha256, output / "worker", enabled)
    _require(ROOT == Path(plan["execution_source"]["root"]), "Immutable controller source required")
    snapshot.verify(ROOT, manifest_sha256=plan["execution_source"]["snapshot_sha256"])
    _require(os.sched_getaffinity(0) == {NATIVE_POLICY["cpu"]}, "Exact controller CPU required")
    output.mkdir(mode=0o700)
    process = output / "process"
    process.mkdir(mode=0o700)
    env = dict(
        os.environ,
        MPLCONFIGDIR=str(output / "worker/mplconfig"),
        PYTHONDONTWRITEBYTECODE="1",
    )
    command = [
        sys.executable,
        "-B",
        "-m",
        "validation.betse.native_init_terminal_reference",
        "--worker",
        str(prepared),
        "--prepared-sha256",
        prepared_sha256,
        "--release",
        str(release),
        "--release-sha256",
        release_sha256,
        "--output",
        str(output / "worker"),
        "--enabled",
    ]
    began = time.monotonic()
    try:
        result = guard.run_bounded(
            command,
            directory=process,
            cwd=ROOT,
            env=env,
            timeout=NATIVE_POLICY["wall_seconds"],
            max_rss_bytes=NATIVE_POLICY["max_rss_bytes"],
            min_available_bytes=NATIVE_POLICY["reserve_bytes"],
        )
        child = _json_record(
            output / "worker/result.json",
            snapshot.digest(output / "worker/result.json"),
            limit=16 * 2**20,
        )
        _require(
            result["returncode"] == 0 and child["status"] == "completed",
            "Complete source/evidence worker required",
            "supervision",
        )
        snapshot.write_json(
            output / "result.json",
            dict(
                status="completed",
                process=result,
                worker_result_sha256=snapshot.digest(output / "worker/result.json"),
                elapsed_seconds=time.monotonic() - began,
                scientific_credit=0,
            ),
        )
    except BaseException as error:
        snapshot.write_json(
            output / "failure.json",
            dict(
                status="failed",
                error=_error(error),
                elapsed_seconds=time.monotonic() - began,
                automatic_retry=False,
                scientific_credit=0,
            ),
        )
        raise
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", type=Path)
    parser.add_argument("--input-pair", type=Path)
    parser.add_argument("--input-sha256")
    parser.add_argument("--mode", choices=MODES, default="original")
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--prepared-sha256")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--controller", type=Path)
    parser.add_argument("--release", type=Path)
    parser.add_argument("--release-sha256")
    parser.add_argument("--enabled", action="store_true")
    args = parser.parse_args()
    if args.prepare and args.input_pair and args.input_sha256:
        prepare(
            args.prepare, input_pair=args.input_pair, input_sha256=args.input_sha256, mode=args.mode
        )
        return 0
    if args.worker and args.prepared_sha256 and args.output:
        resource.setrlimit(
            resource.RLIMIT_AS, (NATIVE_POLICY["max_rss_bytes"], NATIVE_POLICY["max_rss_bytes"])
        )
        return int(
            evaluate(
                args.worker,
                args.prepared_sha256,
                args.output,
                release=args.release,
                release_sha256=args.release_sha256,
                enabled=args.enabled,
            )["status"]
            != "completed"
        )
    if args.controller and args.prepared_sha256 and args.output:
        supervise(
            args.controller,
            args.prepared_sha256,
            args.release,
            args.release_sha256,
            args.output,
            enabled=args.enabled,
        )
        return 0
    parser.error("Choose metadata preparation or an explicitly reviewed reference worker")


if __name__ == "__main__":
    raise SystemExit(main())
