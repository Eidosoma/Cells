"""Held genuine same-process WorldReady/phase/Cells prefix through make_maskM.

The input callback is an actually issued CallbackOwner, supplied in process by
the released application prelude. It is never loaded from evidence. Parameter
birth is delegated to Key's public acquisition API. This module opens no second
parameter claim and supplies no phase, polygon, mesh, grid or cached owner.
"""

import argparse
import importlib
import json
import os
import resource
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import FunctionType

from validation import source_snapshot as snapshot
from validation.betse import betse_native_seed_world_geometry_software as controls_runner

ROOT = Path(__file__).resolve().parents[2]
FILE = "validation/betse/native_seed_world_geometry_qualification.py"
SOURCE = FILE
TEST = "tests/unit/test_native_seed_world_geometry_qualification.py"
MODULE = "validation.betse.native_seed_world_geometry_qualification"
RELEASE = "CELLS_NATIVE_SEED_WORLD_GEOMETRY_QUALIFICATION_RELEASED"
SOFTWARE_RELEASE = "BETSE_NATIVE_SEED_WORLD_GEOMETRY_QUALIFICATION_SOFTWARE_RELEASED"
PARAMETER_ENTRY_MODULE = "validation.betse.betse_native_parameter_world_ready_qualification"
PARAMETER_ENTRY_SOURCE_SHA256 = "4d4428fd3c9bf1e98ae2725e79f40f39be5052c6a36d2d333bfc98516254757e"
PARAMETER_ENTRY_REVIEW_SHA256 = "c42f5e5023436e97fa23877bae552a79c8c0a22faf7b6a95a7d24557ef68297e"
EVIDENCE_MODULE = "validation.betse.native_seed_demo_evidence"
EVIDENCE_SOURCE_SHA256 = "e3b5228e3622b6baeaa27fd322008ec61c251f477f406dfe38f26f1f875ab4b6"
POLICY = dict(cpu=6, threads=1, software_bytes=2**30, wall_seconds=480, reserve_bytes=8 * 2**30)
NATIVE_CPU = 0  # Key's exact public acquisition contract; never switch affinity here.
FORBIDDEN_MODULES = controls_runner.FORBIDDEN_MODULES
NATIVE_ROOT = controls_runner.NATIVE_ROOT
is_forbidden_frame = controls_runner.is_forbidden_frame
_RAW_FAILURES = ()
MODULES = {
    "world": "cells.processes.betse_native_world_phase_construction",
    "prefix": "cells.processes.betse_native_seed_world_prefix",
    "image": "cells.processes.betse_native_seed_voronoi_image",
    "mesh": "cells.processes.betse_native_seed_voronoi_mesh",
    "lifecycle": "cells.processes.betse_native_seed_voronoi_lifecycle",
    "geometry": "cells.processes.betse_native_seed_world_geometry",
    "callbacks": "cells.processes.betse_native_phase_callbacks",
}
MODULE_SOURCE_SHA256 = {
    "world": "df9e0e0e260a2df648015d4bd5c15dfbacbaa9f0302145e2b7deb8aec6af07d0",
    "prefix": "7eac806b1756b1888f621fb576f527c6cc5095a7967b9edd3508d2b3e6f32725",
    "image": "98bcd55b9e00e28bf7f9dd5d5a20261217e640e901affaa1b1686d0f458b45e0",
    "mesh": "c73fd24847158223373c6d77783b8e27857bede8ff59b3b6094ceba20fa2f23f",
    "lifecycle": "2ad275b33cd123f0cf266d262dcee5609924b72a91c6c8b86328bed1116eac1e",
    "geometry": "2b8701f0fd4f59731d69d7a244fc3bdf8b347e683a9335fb561b83f90ab2f22a",
    "callbacks": "9a680cf6b6ccad865bce3365c8dff2f0d5b2e7ad845f00321a0cc26cd235d4b8",
}
MODULE_REVIEW_SHA256 = {
    "world": "b3d3aa390a6238d8eb0236dac6ee29af6f3877fd4d4e80df19d48ba62acc882d",
    "prefix": "b3d3aa390a6238d8eb0236dac6ee29af6f3877fd4d4e80df19d48ba62acc882d",
    "image": "aa5cddf4c36998d3a99bcc576af94ba6fb4993c020de402bdd6ae8b134613f6e",
    "mesh": "a4fd24cebcb04930a7d4d884a18b0e2368020510d7d57e6be72f4b213cad1bbb",
    "lifecycle": "aa5cddf4c36998d3a99bcc576af94ba6fb4993c020de402bdd6ae8b134613f6e",
    "geometry": "a4fd24cebcb04930a7d4d884a18b0e2368020510d7d57e6be72f4b213cad1bbb",
    "callbacks": "cc2ba3a07cb2177e6b6ba6c0190009f9f03086bdb4a33bd3c7d2f4ef00f9d967",
}
STAGES = ("phase", "lattice", "image", "mesh", "lifecycle", "geometry")
OWNED = (
    FILE,
    TEST,
    *(
        "src/" + module.replace(".", "/") + ".py"
        for module in MODULES.values()
        if module != MODULES["callbacks"]
    ),
    "src/cells/processes/betse_native_seed_world_geometry_source.py",
    "tests/unit/test_betse_native_seed_voronoi_lifecycle.py",
    "tests/unit/test_betse_native_seed_world_geometry.py",
    "validation/betse/betse_native_seed_world_geometry_software.py",
)


class QualificationRejected(ValueError):
    def __init__(
        self,
        reason,
        *,
        stage,
        partial=None,
        source_error=None,
        metadata_error=None,
        capture_errors=(),
    ):
        super().__init__(reason)
        self.stage, self.partial = stage, partial
        self.source_error, self.metadata_error = source_error, metadata_error
        self.capture_errors = capture_errors


@dataclass(slots=True)
class Execution:
    stage: str = "preflight"
    parameters: object = None
    world_ready: object = None
    callback_owner: object = None
    phase: object = None
    owners: list = field(default_factory=list)
    requests: list = field(default_factory=list)
    trials: list = field(default_factory=list)
    operations: list = field(default_factory=list)
    source_error: object = None
    metadata_error: object = None
    primary: object = None
    capture_errors: list = field(default_factory=list)
    last_return: object = None
    source_completed: bool = False
    result: object = None
    diagnostics: object = None
    forensic_rows: object = None

    def __reduce_ex__(self, protocol):
        raise TypeError("Live diagnostic state is not checkpoint or hydration authority")


def _pin(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def source_plan():
    return dict(
        endpoint="same original phase.cells through make_maskM, before first Poisson callback",
        actual_live_inputs=("WorldReadyParametersOwner", "CallbackOwner"),
        parameter_entry=PARAMETER_ENTRY_MODULE,
        parameter_source=PARAMETER_ENTRY_SOURCE_SHA256,
        parameter_review=PARAMETER_ENTRY_REVIEW_SHA256,
        module_sources=dict(MODULE_SOURCE_SHA256),
        module_reviews=dict(MODULE_REVIEW_SHA256),
        evidence_profiles=("ordinary", "seed_demo"),
        evidence_default="ordinary",
        seed_demo_evidence_source=EVIDENCE_SOURCE_SHA256,
        seed_demo_evidence_reader=EVIDENCE_MODULE + ".read/files with capture root SHA",
        stages=STAGES,
        one_parameter_claim="only WPC.prepare opens Key construction; no intermediate closed claim",
        callback_provision=(
            "genuine separately issued callback supplied in process; explicit input route, "
            "not default caller-order equivalence"
        ),
        source_work=(
            "all constructor/authentication/helper/body attempts count as work, "
            "not independent inputs"
        ),
        runtime_order=(
            "parameter entry authenticates its runtime before importing phase/geometry stages"
        ),
        diagnostics=(
            "population, finite positive geometry, native bounds and mask support; "
            "no independent geometric oracle"
        ),
        original_layouts_failures_zero_masks_retained=True,
        software_policy=dict(POLICY),
        native_policy=dict(POLICY, cpu=NATIVE_CPU),
        actual_release=False,
        physical_checkpoint_full_phase_admission=False,
        invalidated_postcut_owners=11,
        held_postcut_cases=12,
    )


def _producer_path(name, pin):
    prefix = "" if name.startswith("validation.") else "src/"
    path = ROOT / (prefix + name.replace(".", "/") + ".py")
    if not _pin(pin) or path.is_symlink() or not path.is_file() or snapshot.digest(path) != pin:
        raise QualificationRejected(
            "Exact reviewed producer unavailable: " + name, stage="producer"
        )
    return path


def _bound_module(name, pin):
    path = _producer_path(name, pin)
    module = importlib.import_module(name)
    if sys.modules.get(name) is not module or Path(module.__file__).resolve() != path:
        raise QualificationRejected(
            "Actual immutable source-root module required", stage="producer"
        )
    return module


def _dependencies(*, stages=True):
    if (
        not all(
            _pin(value)
            for value in (
                PARAMETER_ENTRY_SOURCE_SHA256,
                PARAMETER_ENTRY_REVIEW_SHA256,
                *MODULE_SOURCE_SHA256.values(),
                *MODULE_REVIEW_SHA256.values(),
            )
        )
        or set(MODULE_SOURCE_SHA256) != set(MODULES)
        or set(MODULE_REVIEW_SHA256) != set(MODULES)
    ):
        raise QualificationRejected(
            "Whole-milestone producer adoption remains held", stage="unbound"
        )
    # Verify every selected byte before acquisition or other owner access, but
    # leave numerical stage imports until Key authenticates the real runtime.
    for name, path in MODULES.items():
        _producer_path(path, MODULE_SOURCE_SHA256[name])
    parameter = _bound_module(PARAMETER_ENTRY_MODULE, PARAMETER_ENTRY_SOURCE_SHA256)
    if type(parameter.POLICY) is not dict or parameter.POLICY.get("cpu") != NATIVE_CPU:
        raise QualificationRejected("Reviewed native parameter CPU contract changed", stage="cpu")
    for name in ("acquire_world_ready", "prepare", "packet_inputs"):
        function = getattr(parameter, name, None)
        if type(function) is not FunctionType or function.__globals__ is not vars(parameter):
            raise QualificationRejected(
                "Actual public parameter entry unavailable", stage="parameter_api"
            )
    if not stages:
        return parameter, None
    modules = {
        name: _bound_module(path, MODULE_SOURCE_SHA256[name]) for name, path in MODULES.items()
    }
    modules["world"]._dependencies()  # All genuine stage/Key/helper bindings, before owner access.
    return parameter, modules


def _released(enabled):
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise QualificationRejected("Actual source diagnostic remains held", stage="release")


def _resources():
    limits = resource.getrlimit(resource.RLIMIT_AS)
    if (
        os.sched_getaffinity(0) != {NATIVE_CPU}
        or limits[0] <= 0
        or limits[0] > POLICY["software_bytes"]
        or limits[1] <= 0
        or limits[1] > POLICY["software_bytes"]
        or any(
            os.environ.get(name) != "1"
            for name in (
                "OPENBLAS_NUM_THREADS",
                "OMP_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        )
        or os.environ.get("CUDA_VISIBLE_DEVICES") != ""
    ):
        raise QualificationRejected(
            "Exact CPU/thread/address-space diagnostic envelope required", stage="resources"
        )
    available = next(
        int(line.split()[1]) * 1024
        for line in Path("/proc/meminfo").read_text().splitlines()
        if line.startswith("MemAvailable:")
    )
    if available < POLICY["reserve_bytes"]:
        raise QualificationRejected("Host reserve unavailable", stage="resources")


def _capture(state, evidence, label, value):
    try:
        if not evidence.save(label, value):
            raise RuntimeError("Typed capture refused: " + label)
    except BaseException as error:
        state.capture_errors.append((label, error, value))
        raise


def _operation(state, evidence, label, function, *args, **kwargs):
    state.stage = label
    row = dict(sequence=len(state.operations), name=label, state="attempted")
    state.operations.append(row)
    try:
        value = function(*args, **kwargs)
    except BaseException as error:
        row["state"], row["error"] = "source_failed", error
        state.source_error = error
        raise
    state.last_return = value  # Before observers, serialization or properties.
    row["state"], row["returned"] = "returned", value
    return value


def _execute_chain(state, modules, evidence):
    """Actual public calls, with injection only for private blocked controls."""
    world = modules["world"]
    request = _operation(
        state,
        evidence,
        "phase_request",
        world.from_world_ready,
        state.world_ready,
        state.callback_owner,
        law_id=world.LAW_ID,
        mode=world.MODE,
    )
    state.requests.append(request)
    owner = _operation(state, evidence, "phase", world.prepare, request, enabled=True)
    for index, name in enumerate(STAGES):
        module = modules[{"phase": "world", "lattice": "prefix"}.get(name, name)]
        state.owners.append((name, owner))
        trial = owner.trial  # Save before irreversible downstream consumption.
        state.trials.append((name, trial))
        if name == "phase":
            state.phase = owner.phase
            if state.parameters is not None and state.phase.p is not state.parameters:
                raise ValueError("Fresh phase must retain the actual acquired parameter instance")
        record = module._trial_record(trial) if name == "phase" else module.trial_record(trial)
        _capture(state, evidence, name + ".record", record)
        _capture_caches(state, evidence, name, trial)
        if index == len(STAGES) - 1:
            state.result, state.source_completed = owner, True
            return owner
        next_stage = STAGES[index + 1]
        successor = modules["prefix" if next_stage == "lattice" else next_stage]
        method = {
            "lattice": "from_phase",
            "image": "from_prefix",
            "mesh": "from_image",
            "lifecycle": "from_constructor",
            "geometry": "from_lifecycle",
        }[next_stage]
        kwargs = dict(law_id=successor.LAW_ID)
        if next_stage == "lattice":
            kwargs["mode"] = world.MODE
        request = _operation(
            state, evidence, next_stage + "_request", getattr(successor, method), owner, **kwargs
        )
        state.requests.append(request)
        owner = _operation(state, evidence, next_stage, successor.prepare, request, enabled=True)
    raise AssertionError("Unreachable stage boundary")


def _capture_caches(state, evidence, label, trial):
    """Save full typed columns/layouts, without treating live trials as wire owners."""
    from dataclasses import fields, is_dataclass

    from cells.processes import betse_initial_mesh_preparation_cache as caches

    pending, seen = [(label, trial)], set()
    while pending:
        name, value = pending.pop()
        if value is None or id(value) in seen:
            continue
        if len(seen) >= 4096:
            raise ValueError("Bounded source-stage cache roster exhausted")
        seen.add(id(value))
        if type(value) is caches.Cache:
            caches.validate(value)
            _capture(
                state,
                evidence,
                name + ".cache",
                dict(
                    descriptor_json=value.descriptor_json,
                    identity=value.identity,
                    all_finite=value.all_finite,
                    columns=value.numeric_columns(),
                    live_owner_or_checkpoint_admission=False,
                ),
            )
        elif is_dataclass(value):
            for item in fields(value):
                if item.name in (
                    "before",
                    "cache",
                    "helper_cache",
                    "stage_caches",
                    "stage_trials",
                    "stages",
                    "stream_before",
                    "stream_after",
                    "rng_before",
                    "rng_after",
                ):
                    raw = getattr(value, item.name)
                    if (
                        item.name
                        in (
                            "stream_before",
                            "stream_after",
                            "rng_before",
                            "rng_after",
                        )
                        and raw is not None
                    ):
                        _capture(state, evidence, name + "." + item.name, raw)
                    else:
                        pending.append((name + "." + item.name, raw))
        elif type(value) in (list, tuple):
            pending.extend((name + "." + str(index), item) for index, item in enumerate(value))


def diagnostics(caller):
    """Read-only observations; original empty/nonfinite values remain intact.

    This uses the actual issued caller after successful source completion. It
    is not an independent geometry calculation, physical admission or a reason
    to change the input, native grid constants, zero masks or failed source.
    """
    import numpy as np

    values = vars(caller)
    result = dict(population={}, support={}, geometry={}, observation_errors=[])

    def observe(name, function):
        try:
            function(values[name])
        except Exception as error:
            result["observation_errors"].append(dict(field=name, error=str(error)))

    for label, name in (
        ("cells", "cell_i"),
        ("membranes", "mem_i"),
        ("vertices", "ecm_verts_unique"),
        ("ecm_nodes", "xypts"),
    ):
        observe(name, lambda value, label=label: result["population"].update({label: len(value)}))
    for name in ("maskM", "maskECM", "voronoi_mask"):

        def mask(value, name=name):
            array = np.asarray(value)
            result["support"][name] = dict(
                shape=list(array.shape),
                size=array.size,
                finite=bool(np.isfinite(array).all()),
                nonzero=int(np.count_nonzero(array)),
            )

        observe(name, mask)
    for name in ("cell_vol", "mem_vol", "ecm_vol", "cell_centres", "ecm_verts_unique", "xypts"):

        def geometry(value, name=name):
            array = np.asarray(value)
            result["geometry"][name] = dict(
                size=array.size,
                finite=bool(np.isfinite(array).all()),
                positive=bool(array.size and np.all(array > 0)) if name.endswith("vol") else None,
            )

        observe(name, geometry)
    try:
        xmin, xmax, ymin, ymax = (values[name] for name in ("xmin", "xmax", "ymin", "ymax"))
        for name in ("cell_centres", "ecm_verts_unique"):
            points = np.asarray(values[name])
            if points.ndim != 2 or points.shape[1] != 2:
                raise ValueError("Native coordinate array must retain its two columns")
            result["geometry"][name]["inside_native_bounds"] = int(
                np.count_nonzero(
                    (xmin <= points[:, 0])
                    & (points[:, 0] <= xmax)
                    & (ymin <= points[:, 1])
                    & (points[:, 1] <= ymax)
                )
            )
    except Exception as error:
        result["observation_errors"].append(dict(field="bounds", error=str(error)))
    finite_masks = all(
        result["support"].get(name, {}).get("finite") is True
        for name in ("maskM", "maskECM", "voronoi_mask")
    )
    result["gates"] = dict(
        populated=result["population"].get("cells", 0) > 1,
        finite_geometry=bool(result["geometry"])
        and all(row["finite"] for row in result["geometry"].values()),
        positive_volumes=all(
            result["geometry"].get(name, {}).get("positive") is True
            for name in ("cell_vol", "mem_vol", "ecm_vol")
        ),
        finite_masks=finite_masks,
        mask_support=finite_masks
        and all(
            result["support"].get(name, {}).get("nonzero", 0) > 0 for name in ("maskM", "maskECM")
        ),
    )
    result["domain_gate_passed"] = not result["observation_errors"] and all(
        result["gates"].values()
    )
    result["physical_admission"] = result["independent_geometric_accuracy"] = False
    return result


def _seal_execution(state, evidence, directory):
    """Always try final evidence, preserving a prior primary and all raw state."""
    if state.primary is not None:
        try:
            evidence.failure(state.primary)
        except BaseException as capture:
            state.capture_errors.append(("failure_forensics", capture, state.primary))
    state.forensic_rows = evidence.rows
    try:
        snapshot.write_json(
            directory / "outcome.json",
            dict(
                status="source_completed"
                if state.source_completed and state.primary is None and not state.capture_errors
                else "failed",
                source_completed=state.source_completed,
                stage=state.stage,
                source_error=None
                if state.source_error is None
                else type(state.source_error).__qualname__,
                metadata_error=None
                if state.metadata_error is None
                else type(state.metadata_error).__qualname__,
                capture_errors=[
                    dict(stage=label, type=type(error).__qualname__)
                    for label, error, _ in state.capture_errors
                ],
                captures=evidence.rows,
                actual_inputs=int(bool(state.operations)),
                api_operations=len(state.operations),
                work_accounting=(
                    "stage Trial ledgers are retained non-additive views, not extra cases"
                ),
                raw_live_failed_state=(
                    "retained in process via rejected.partial; wire capture gaps remain explicit"
                ),
                diagnostics=state.diagnostics,
                independent_numerical_physical_checkpoint_credit=0,
            ),
        )
    except BaseException as capture:
        state.capture_errors.append(("final_outcome", capture, state))


def _evidence_writer(profile):
    """Explicit finite observation capacity, independent of native authority."""
    if type(profile) is not str or profile not in ("ordinary", "seed_demo"):
        raise QualificationRejected("Unknown evidence profile", stage="evidence")
    if profile == "ordinary":
        return None
    module = _bound_module(EVIDENCE_MODULE, EVIDENCE_SOURCE_SHA256)
    writer = module.capture_writer
    if type(writer) is not FunctionType or writer.__globals__ is not vars(module):
        raise QualificationRejected("Actual evidence writer required", stage="evidence")
    return writer


def evaluate_live(
    world_ready, callback_owner, directory, *, enabled=False, evidence_profile="ordinary"
):
    """Complete the genuine issued chain; no JSON or cache can supply parents."""
    _released(enabled)
    writer = _evidence_writer(evidence_profile)
    _, modules = _dependencies()
    _resources()
    directory = Path(directory)
    if directory.exists() or any(path.is_symlink() for path in (directory, *directory.parents)):
        raise QualificationRejected("Fresh unlinked evidence directory required", stage="output")
    directory.mkdir(parents=True)
    from validation.betse.native_single_cell_prefix_qualification import Evidence

    evidence = Evidence(directory, sidecars=True, capture_writer=writer)
    state = Execution(world_ready=world_ready, callback_owner=callback_owner)
    try:
        modules["callbacks"]._validate(callback_owner)
        state.parameters = world_ready.parameters  # Genuine pre-claim access only.
        owner = _execute_chain(state, modules, evidence)
        context = modules["geometry"]._authority(owner)
        if context.phase is not state.phase or context.p is not state.parameters:
            raise ValueError("Completed geometry changed the original phase/parameter identity")
        _capture_caches(state, evidence, "completed_geometry", context.trial.cache)
        state.stage = "diagnostics"
        state.diagnostics = diagnostics(context.cells)
        _capture(state, evidence, "diagnostics", state.diagnostics)
    except BaseException as error:
        state.primary = error
        if state.source_error is None and not state.capture_errors:
            state.metadata_error = error
    finally:
        try:
            _seal_execution(state, evidence, directory)
        except BaseException as capture:
            # Also protect helper entry: inherited observers can reject before
            # the final writer's own body gets a chance to retain anything.
            state.capture_errors.append(("seal_entry", capture, state))
    if state.primary is not None or state.capture_errors:
        cause = state.primary if state.primary is not None else state.capture_errors[0][1]
        raise QualificationRejected(
            "Same-phase geometry diagnostic failed",
            stage=state.stage,
            partial=state,
            source_error=state.source_error,
            metadata_error=state.metadata_error,
            capture_errors=tuple(state.capture_errors),
        ) from cause
    return state.result


def acquire_and_evaluate(packet, directory, *, packet_sha256, callback_owner, enabled=False):
    _released(enabled)
    parameter, _ = _dependencies(stages=False)
    _resources()
    ready, p = parameter.acquire_world_ready(
        packet,
        Path(directory) / "parameter-entry",
        packet_sha256=packet_sha256,
        enabled=True,
    )
    # WPC opens the one construction claim AFTER this completed fresh load.
    # No access to ready.parameters is made after WPC consumes that epoch.
    if ready.parameters is not p:
        raise QualificationRejected(
            "Actual same-parameter phase relationship changed", stage="identity"
        )
    return evaluate_live(ready, callback_owner, Path(directory) / "world", enabled=True)


def prepare(repository, directory, *, inputs, inputs_sha256, python):
    """One-way combined snapshot using the actual parameter producer's API."""
    parameter, _ = _dependencies(stages=False)
    if Path(repository).resolve() != ROOT:
        raise QualificationRejected("Canonical checkout preparation required", stage="checkout")
    # Key owns raw files, path permissions and explicit runtime inventory. No
    # packet/source tree is copied from an older execution image.
    value = parameter.prepare(
        repository,
        directory,
        inputs=inputs,
        inputs_sha256=inputs_sha256,
        python=python,
        extra_sources=OWNED,
    )
    snapshot.write_json(
        Path(directory) / "geometry-plan.json",
        dict(
            kind="cells.genuine_seed_world_geometry_diagnostic@1",
            held=True,
            automatic_launch=False,
            source_plan=source_plan(),
            parameter_inputs_sha256=snapshot.digest(Path(directory) / "inputs.json"),
            requires_actual_in_process_CallbackOwner=True,
            actual_owner_or_native_release=False,
        ),
    )
    return value


def software_prepare(output, select):
    from validation.betse import betse_native_seed_world_geometry_software as base

    namespace = dict(
        vars(base.base.base),
        __file__=__file__,
        ROOT=ROOT,
        SOURCE=FILE,
        LITERAL="src/cells/processes/betse_native_seed_world_geometry_source.py",
        TEST=TEST,
        FILE=FILE,
        MODULE=MODULE,
        OWNED=OWNED,
        SOFTWARE_RELEASE=SOFTWARE_RELEASE,
        FORBIDDEN_MODULES=base.FORBIDDEN_MODULES,
    )
    return FunctionType(base.base.base.prepare.__code__, namespace)(output, select)


def software_child(output, select):
    from validation.betse import betse_native_seed_world_geometry_software as base

    namespace = dict(
        vars(base.reuse),
        ROOT=ROOT,
        SOURCE=FILE,
        TEST=TEST,
        FILE=FILE,
        MODULE=MODULE,
        OWNED=OWNED,
        SOFTWARE_RELEASE=SOFTWARE_RELEASE,
        FORBIDDEN_MODULES=base.FORBIDDEN_MODULES,
        is_forbidden_frame=base.is_forbidden_frame,
    )
    try:
        return FunctionType(base.reuse.child.__code__, namespace)(output, select)
    finally:
        global _RAW_FAILURES
        _RAW_FAILURES = namespace.get("_RAW_FAILURES", ())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-plan", action="store_true")
    parser.add_argument("--prepare-software", type=Path)
    parser.add_argument("--child", type=Path)
    parser.add_argument("--select", default="")
    args = parser.parse_args()
    if args.source_plan:
        print(json.dumps(source_plan(), indent=2))
    elif args.prepare_software is not None:
        if not args.select:
            parser.error("Explicit full test-name selection required")
        software_prepare(args.prepare_software, args.select)
    elif args.child is not None:
        resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
        raise SystemExit(software_child(args.child, args.select))
    else:
        parser.error("Actual execution requires live typed parents in a released worker")


if __name__ == "__main__":
    main()
