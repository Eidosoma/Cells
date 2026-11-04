"""One-process genuine SEED demonstration, through core, profiles and junctions.

This is orchestration of existing public issuers, not a new scientific owner.
Every live parent is born in this process. Saved evidence cannot supply a
parameter, callback, phase, mesh, operator or material state. Optional INIT setup
retains the actual Cells and parameters in a fresh INIT phase. Its optional
dynamics prelude and completion continue on that same phase. The electrical
endpoint also clears storage and performs the original first voltage/field update.
The selected first-step endpoint then retains one complete ordinary INIT iteration.
It preserves the native time label and does not claim a full INIT/SIM or restart.
"""

import argparse
import fcntl
import importlib
import json
import os
import resource
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import CodeType, FunctionType

from validation import source_snapshot as snapshot

ROOT = Path(__file__).resolve().parents[2]
BASE = Path("/mnt/workspaces/Cells")
FILE = "validation/betse/native_seed_demo.py"
TEST = "tests/unit/test_native_seed_demo.py"
RUNNER = "validation/betse/native_seed_demo_software.py"
INPUT_METADATA = "validation/betse/native_seed_demo_inputs.py"
INPUT_METADATA_SHA256 = "8f5ffac15d79735d80d7b9d04910d6ea95b5e4b4ba1efb040a088e9b8573ef87"
EVIDENCE_MODULE = "validation.betse.native_seed_demo_evidence"
EVIDENCE_SOURCE_SHA256 = "e3b5228e3622b6baeaa27fd322008ec61c251f477f406dfe38f26f1f875ab4b6"
RELEASE = "CELLS_NATIVE_SEED_DEMO_RELEASED"
KIND = "cells.genuine_seed_core_profiles_junctions_demo@5"
FLUX_MODES = ("original", "disabled")
ENDPOINTS = (
    "seed",
    "init_setup",
    "init_prelude",
    "init_dynamics",
    "init_electrical",
    "init_first_step",
)
INIT_MODULES = {
    "init_setup": "cells.processes.betse_native_init_retained_world",
    "init_parameters": "cells.processes.betse_native_parameter_seed_init_transition",
}
INIT_SOURCE_PINS = dict.fromkeys(INIT_MODULES)
INIT_REVIEW_PINS = dict.fromkeys(INIT_MODULES)
PRELUDE_MODULES = {"init_prelude": "cells.processes.betse_native_init_dynamics_prelude"}
PRELUDE_SOURCE_PINS = dict.fromkeys(PRELUDE_MODULES)
PRELUDE_REVIEW_PINS = dict.fromkeys(PRELUDE_MODULES)
COMPLETION_MODULES = {
    "init_dynamics": "cells.processes.betse_native_init_dynamics_completion",
    "init_tissue": "cells.processes.betse_native_init_tissue_dynamics",
    "init_molecules": "cells.processes.betse_native_init_molecule_network",
}
COMPLETION_SOURCE_PINS = dict.fromkeys(COMPLETION_MODULES)
COMPLETION_REVIEW_PINS = dict.fromkeys(COMPLETION_MODULES)
ELECTRICAL_MODULES = {
    "init_storage": "cells.processes.betse_native_init_storage",
    "init_electrical": "cells.processes.betse_native_init_electrical",
}
ELECTRICAL_SOURCE_PINS = dict.fromkeys(ELECTRICAL_MODULES)
ELECTRICAL_REVIEW_PINS = dict.fromkeys(ELECTRICAL_MODULES)
STEP_MODULES = {"init_first_step": "cells.processes.betse_native_init_first_step"}
STEP_SOURCE_PINS = dict.fromkeys(STEP_MODULES)
STEP_REVIEW_PINS = dict.fromkeys(STEP_MODULES)
POLICY = dict(cpu=0, threads=1, max_rss_bytes=2**30, wall_seconds=7200, reserve_bytes=8 * 2**30)
MODULES = {
    "callback": "validation.betse.native_seed_world_callback_prelude",
    "parameters": "validation.betse.betse_native_parameter_world_ready_qualification",
    "geometry": "validation.betse.native_seed_world_geometry_qualification",
    "poisson": "cells.processes.betse_native_seed_world_poisson",
    "core": "cells.processes.betse_native_seed_init_core",
    "profiles": "cells.processes.betse_native_seed_init_profiles",
    "junctions": "cells.processes.betse_native_seed_junctions",
}
SOURCE_PINS = {
    "callback": "7d8de15e353998b19493f23f8cdfae62b22cabba3133ff5219b8d6558f1f0bd7",
    "parameters": "89137b398d15ba435c34ea696b608c7a44c9163eaa8088a2b02465161d26cafd",
    "geometry": "b46531bed35c4cd4674944c587b29769f6929a6b520914001234a8210912222a",
    "poisson": "39539d52b750fd75787a2897efc564ad4ca886381ab09acf1560159aa815ba33",
    "core": "1e95cb6a7b8c668979a96211c3fce1bec5ca65da11963e23d8c5e60b65f67f5e",
    "profiles": "c7fe1339169e00614a982ed10804eafebc3bd81de3b477acf0719af295c4b25f",
    "junctions": "49daf497ee903d2f1d9f2037bfdea0d10b90815d033bc690aa03f5ffb4df9de4",
}
REVIEW_PINS = {
    "callback": "c42f5e5023436e97fa23877bae552a79c8c0a22faf7b6a95a7d24557ef68297e",
    "parameters": "c42f5e5023436e97fa23877bae552a79c8c0a22faf7b6a95a7d24557ef68297e",
    "geometry": "c42f5e5023436e97fa23877bae552a79c8c0a22faf7b6a95a7d24557ef68297e",
    "poisson": "a4fd24cebcb04930a7d4d884a18b0e2368020510d7d57e6be72f4b213cad1bbb",
    "core": "b3d3aa390a6238d8eb0236dac6ee29af6f3877fd4d4e80df19d48ba62acc882d",
    "profiles": "b3d3aa390a6238d8eb0236dac6ee29af6f3877fd4d4e80df19d48ba62acc882d",
    "junctions": "a9f6d6fa62d2eb5e46cf903546f754b2c8eb204b216343f8cb7bf4752ac85bba",
}
# Root's release must coordinate all native log writers. Advisory locking alone
# cannot establish the absence of writers that do not use this protocol.
SESSION_REVIEW_SHA256 = "2f6b64bb8cfb7a7eb70f203e51f1444849d7c0ed19adc580b02d044b1c799af0"
STAGES = ("callback", "parameters", "geometry", "poisson", "core", "profiles", "junctions")
_ACTIVE = []
_ATTEMPT = None
_PROCESS_LEASES = []


class DemoRejected(ValueError):
    def __init__(self, message, *, stage, partial=None):
        super().__init__(message)
        self.stage, self.partial = stage, partial


@dataclass(slots=True)
class Execution:
    flux_operator: str
    endpoint: str = "seed"
    stage: str = "preflight"
    phase: object = None
    parameters: object = None
    input_root: object = None
    phase_links: tuple = ()
    seed_phase: object = None
    seed_links: tuple = ()
    seed_trial: object = None
    init_phase: object = None
    init_trial: object = None
    init_links: tuple = ()
    prelude_phase: object = None
    prelude_trial: object = None
    dynamics_phase: object = None
    dynamics_trial: object = None
    dynamics_file_inputs: tuple = ()
    dynamics_failure_context: object = None
    dynamics_failure_captures: list = field(default_factory=list)
    dynamics_native_molecules: object = None
    dynamics_api: object = None
    dynamics_molecule_api: object = None
    dynamics_molecule_record: object = None
    dynamics_molecule_failure_context: object = None
    init_molecule_network_completed: bool = False
    storage_phase: object = None
    storage_trial: object = None
    electrical_phase: object = None
    electrical_trial: object = None
    electrical_failure_context: object = None
    electrical_failure_captures: list = field(default_factory=list)
    first_step_phase: object = None
    first_step_trial: object = None
    first_step_record: object = None
    first_step_failure_context: object = None
    first_step_failure_captures: list = field(default_factory=list)
    init_setup_completed: bool = False
    init_prelude_completed: bool = False
    init_dynamics_completed: bool = False
    init_storage_completed: bool = False
    init_electrical_completed: bool = False
    init_first_step_completed: bool = False
    init_time_steps_completed: int = 0
    callback: object = None
    session: object = None
    world_ready: object = None
    owners: list = field(default_factory=list)
    requests: list = field(default_factory=list)
    trials: list = field(default_factory=list)
    operations: list = field(default_factory=list)
    captures: list = field(default_factory=list)
    primary: object = None
    delegate_error: object = None
    secondary: list = field(default_factory=list)
    last_return: object = None
    last_trial: object = None
    result: object = None
    methods_completed: bool = False
    evidence_completed: bool = False

    def __reduce_ex__(self, protocol):
        raise TypeError("Live demonstration state is not checkpoint or hydration authority")


def _pin(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _relative(module):
    return ("" if module.startswith("validation.") else "src/") + module.replace(".", "/") + ".py"


def source_plan(*, endpoint="seed"):
    if type(endpoint) is not str or endpoint not in ENDPOINTS:
        raise DemoRejected(
            "Choose exactly seed or init_setup or init_prelude or init_dynamics"
            " or init_electrical or init_first_step",
            stage="endpoint",
        )
    return dict(
        kind=KIND,
        stages=(
            STAGES
            if endpoint == "seed"
            else (*STAGES, "init_setup")
            if endpoint == "init_setup"
            else (*STAGES, "init_setup", "init_prelude")
            if endpoint == "init_prelude"
            else (*STAGES, "init_setup", "init_prelude", "init_dynamics")
            if endpoint == "init_dynamics"
            else (
                *STAGES,
                "init_setup",
                "init_prelude",
                "init_dynamics",
                "init_storage",
                "init_electrical",
                *(("init_first_step",) if endpoint == "init_first_step" else ()),
            )
        ),
        selected_endpoint=endpoint,
        endpoint=(
            "original graphLaplacian after whole init_core, init_profiles and redo_gj"
            if endpoint == "seed"
            else "fresh retained-world INIT phase and whole init_core; before run_sim_core"
            if endpoint == "init_setup"
            else "same INIT phase dynamics prelude; before profile remapping and RNG"
            if endpoint == "init_prelude"
            else "same INIT phase ordinary init_dynamics completion; before INIT timesteps"
            if endpoint == "init_dynamics"
            else "same INIT Simulator clear_storage then original update_V; before INIT timesteps"
            if endpoint == "init_electrical"
            else "same INIT phase; one complete ordinary iteration at its original time label"
        ),
        optional_init_setup=dict(
            modules=dict(INIT_MODULES),
            source_pins=dict(INIT_SOURCE_PINS),
            review_pins=dict(INIT_REVIEW_PINS),
            same_process=True,
            same_parameters_cells_callbacks=True,
            new_phase_simulator_cache_handler=True,
            checkpoint_or_time_loop_admission=False,
        ),
        optional_init_prelude=dict(
            modules=dict(PRELUDE_MODULES),
            source_pins=dict(PRELUDE_SOURCE_PINS),
            review_pins=dict(PRELUDE_REVIEW_PINS),
            entry="from_init(actual InitOwner, law_id=LAW_ID) -> prepare(enabled=True)",
            same_phase_parameters_cells_simulator_handler_callbacks_cache=True,
            parent_trial_retained_before_consumption=True,
            original_prefix="Simulator.init_dynamics 758-806 with original reached helpers",
            stops_before="init_profiles, channel_noise_factor RNG and INIT timesteps",
            checkpoint_or_time_loop_admission=False,
        ),
        optional_init_dynamics=dict(
            modules=dict(COMPLETION_MODULES),
            source_pins=dict(COMPLETION_SOURCE_PINS),
            review_pins=dict(COMPLETION_REVIEW_PINS),
            entry=(
                "Original p.molecules_enabled selects from_prelude/LAW_ID or "
                "from_prelude_native_molecules/MOLECULE_LAW_ID(actual PreludeOwner, file_inputs=())"
                " -> prepare(enabled=True)"
            ),
            participant="Exact pinned molecular module before enabled request; no flag override",
            same_phase_parameters_cells_simulator_handler_callbacks_cache=True,
            parent_trial_retained_before_consumption=True,
            file_inputs=(
                "Original bundle bytes for actual picker filenames and configured gradient bitmap"
            ),
            rng="Original continuing streams; no seed, reset, copy or replacement draw",
            branch_policy="Producer refuses unavailable optional owners; no configuration repair",
            failure_observation=(
                "Independently capture available original trial/context values; no new snapshot"
                " or RNG read; bounded 4096 RNG rows / 100000 raw-return rows;"
                " no live-frame serialization"
            ),
            stops_before="INIT timesteps, SIM and restart",
            checkpoint_or_time_loop_admission=False,
        ),
        optional_init_electrical=dict(
            modules=dict(ELECTRICAL_MODULES),
            source_pins=dict(ELECTRICAL_SOURCE_PINS),
            review_pins=dict(ELECTRICAL_REVIEW_PINS),
            entry=(
                "from_dynamics(actual CompletionOwner) -> prepare -> "
                "from_storage(actual StorageOwner) -> prepare"
            ),
            same_phase_parameters_cells_simulator_handler_callbacks_cache=True,
            parent_trials_retained_before_consumption=True,
            original_methods=("clear_storage", "update_V"),
            evidence="Original before/after snapshots, stream identities, stores and raw returns",
            rng="Retained producer stream identities; no additional RNG reads or draws",
            electrical_operator="Retained value-boundary lapENVinv only",
            flux_inverse_rebuilt_repaired_or_required=False,
            stops_before="INIT timestep loop, SIM and restart",
            checkpoint_or_time_loop_admission=False,
        ),
        optional_init_first_step=dict(
            modules=dict(STEP_MODULES),
            source_pins=dict(STEP_SOURCE_PINS),
            review_pins=dict(STEP_REVIEW_PINS),
            entry="from_electrical(actual ElectricalOwner, law_id=LAW_ID) -> prepare(enabled=True)",
            same_phase_parameters_cells_simulator_handler_callbacks_cache=True,
            parent_trial_retained_before_consumption=True,
            selected_complete_iterations=1,
            original_calendar_sampling_time_label_and_configured_dt=True,
            selected_stop_distinct_from_full_loop_return=True,
            no_synthetic_elapsed_time_or_calendar_relabel=True,
            evidence="Trial, original snapshot values, streams, work, stores and raw returns",
            failure_observation="Independent retained trial/partial fields; no owner or RNG reread",
            normal_transport_unchanged=True,
            flux_inverse_rebuilt_repaired_or_required=False,
            full_INIT_SIM_or_restart_admission=False,
        ),
        source_pins=dict(SOURCE_PINS),
        review_pins=dict(REVIEW_PINS),
        shared_log_session_api="Root process-lifetime canonical log-target lease",
        shared_log_session_review=SESSION_REVIEW_SHA256,
        shared_log_scope="callback bootstrap and every later native stage in this process",
        flux_modes=FLUX_MODES,
        flux_policy={
            "original": "retain the original flux inverse and its known numerical defect",
            "disabled": (
                "omit only that inverse; retain value inverse and membrane/junction transport"
            ),
        },
        one_mode_per_fresh_process=True,
        no_retry_or_fallback=True,
        stage_trials="non-additive work and retained evidence, not independent cases",
        profile_images="Actual retained picker filenames, issued immutable original input files",
        input_metadata_sha256=INPUT_METADATA_SHA256,
        evidence_profile="seed_demo",
        evidence_source=EVIDENCE_SOURCE_SHA256,
        evidence_reader=EVIDENCE_MODULE + ".read/files with capture root SHA",
        evidence_scope="lossless bounded transport; partial captures never establish completion",
        native_policy=dict(POLICY),
        native_or_scientific_release=False,
        complete_seed_runner_order_claim=False,
        evolving_SIM_or_restart_claim=False,
        held_postcut_owners=11,
        held_postcut_cases=12,
    )


def _dependencies(endpoint="seed"):
    """Check every producer before importing even a callback definition."""
    if type(endpoint) is not str or endpoint not in ENDPOINTS:
        raise DemoRejected(
            "Choose exactly seed or init_setup or init_prelude or init_dynamics"
            " or init_electrical or init_first_step",
            stage="endpoint",
        )
    if (
        set(SOURCE_PINS) != set(MODULES)
        or set(REVIEW_PINS) != set(MODULES)
        or not all(_pin(p) for p in (*SOURCE_PINS.values(), *REVIEW_PINS.values()))
        or not _pin(SESSION_REVIEW_SHA256)
        or not _pin(EVIDENCE_SOURCE_SHA256)
    ):
        raise DemoRejected("Combined producer/route/session adoption remains held", stage="unbound")
    if endpoint != "seed" and (
        set(INIT_SOURCE_PINS) != set(INIT_MODULES)
        or set(INIT_REVIEW_PINS) != set(INIT_MODULES)
        or not all(_pin(p) for p in (*INIT_SOURCE_PINS.values(), *INIT_REVIEW_PINS.values()))
    ):
        raise DemoRejected("Retained-world INIT producers remain unadopted", stage="init_unbound")
    if endpoint in ("init_prelude", "init_dynamics", "init_electrical", "init_first_step") and (
        set(PRELUDE_SOURCE_PINS) != set(PRELUDE_MODULES)
        or set(PRELUDE_REVIEW_PINS) != set(PRELUDE_MODULES)
        or not all(_pin(p) for p in (*PRELUDE_SOURCE_PINS.values(), *PRELUDE_REVIEW_PINS.values()))
    ):
        raise DemoRejected("INIT prelude producers remain unadopted", stage="prelude_unbound")
    if endpoint in ("init_dynamics", "init_electrical", "init_first_step") and (
        set(COMPLETION_SOURCE_PINS) != set(COMPLETION_MODULES)
        or set(COMPLETION_REVIEW_PINS) != set(COMPLETION_MODULES)
        or not all(
            _pin(p) for p in (*COMPLETION_SOURCE_PINS.values(), *COMPLETION_REVIEW_PINS.values())
        )
    ):
        raise DemoRejected("INIT dynamics producers remain unadopted", stage="dynamics_unbound")
    if endpoint in ("init_electrical", "init_first_step") and (
        set(ELECTRICAL_SOURCE_PINS) != set(ELECTRICAL_MODULES)
        or set(ELECTRICAL_REVIEW_PINS) != set(ELECTRICAL_MODULES)
        or not all(
            _pin(p) for p in (*ELECTRICAL_SOURCE_PINS.values(), *ELECTRICAL_REVIEW_PINS.values())
        )
    ):
        raise DemoRejected("INIT electrical producers remain unadopted", stage="electrical_unbound")
    if endpoint == "init_first_step" and (
        set(STEP_SOURCE_PINS) != set(STEP_MODULES)
        or set(STEP_REVIEW_PINS) != set(STEP_MODULES)
        or not all(_pin(p) for p in (*STEP_SOURCE_PINS.values(), *STEP_REVIEW_PINS.values()))
    ):
        raise DemoRejected("INIT first-step producers remain unadopted", stage="step_unbound")
    for key, name in MODULES.items():
        path = ROOT / _relative(name)
        if path.is_symlink() or not path.is_file() or snapshot.digest(path) != SOURCE_PINS[key]:
            raise DemoRejected("Reviewed source changed: " + key, stage="producer")
    path = ROOT / _relative(EVIDENCE_MODULE)
    if path.is_symlink() or not path.is_file() or snapshot.digest(path) != EVIDENCE_SOURCE_SHA256:
        raise DemoRejected("Reviewed evidence source changed", stage="producer")
    if endpoint != "seed":
        for key, name in INIT_MODULES.items():
            path = ROOT / _relative(name)
            if (
                path.is_symlink()
                or not path.is_file()
                or snapshot.digest(path) != INIT_SOURCE_PINS[key]
            ):
                raise DemoRejected("Reviewed INIT source changed: " + key, stage="producer")
    if endpoint in ("init_prelude", "init_dynamics", "init_electrical", "init_first_step"):
        for key, name in PRELUDE_MODULES.items():
            path = ROOT / _relative(name)
            if (
                path.is_symlink()
                or not path.is_file()
                or snapshot.digest(path) != PRELUDE_SOURCE_PINS[key]
            ):
                raise DemoRejected("Reviewed INIT prelude source changed: " + key, stage="producer")
    if endpoint in ("init_dynamics", "init_electrical", "init_first_step"):
        for key, name in COMPLETION_MODULES.items():
            path = ROOT / _relative(name)
            if (
                path.is_symlink()
                or not path.is_file()
                or snapshot.digest(path) != COMPLETION_SOURCE_PINS[key]
            ):
                raise DemoRejected(
                    "Reviewed INIT dynamics source changed: " + key, stage="producer"
                )
    if endpoint in ("init_electrical", "init_first_step"):
        for key, name in ELECTRICAL_MODULES.items():
            path = ROOT / _relative(name)
            if (
                path.is_symlink()
                or not path.is_file()
                or snapshot.digest(path) != ELECTRICAL_SOURCE_PINS[key]
            ):
                raise DemoRejected(
                    "Reviewed INIT electrical source changed: " + key, stage="producer"
                )
    if endpoint == "init_first_step":
        for key, name in STEP_MODULES.items():
            path = ROOT / _relative(name)
            if (
                path.is_symlink()
                or not path.is_file()
                or snapshot.digest(path) != STEP_SOURCE_PINS[key]
            ):
                raise DemoRejected(
                    "Reviewed INIT first-step source changed: " + key, stage="producer"
                )
    return Modules(endpoint)


def _evidence_writer():
    path = ROOT / _relative(EVIDENCE_MODULE)
    if (
        not _pin(EVIDENCE_SOURCE_SHA256)
        or path.is_symlink()
        or not path.is_file()
        or snapshot.digest(path) != EVIDENCE_SOURCE_SHA256
    ):
        raise DemoRejected("Exact evidence transport unavailable", stage="evidence")
    module = importlib.import_module(EVIDENCE_MODULE)
    if sys.modules.get(EVIDENCE_MODULE) is not module or Path(module.__file__).resolve() != path:
        raise DemoRejected("Actual frozen evidence origin required", stage="evidence")
    return _function(module, "capture_writer")


class Modules:
    """Lazy imports preserve native application bootstrap before parameter birth."""

    def __init__(self, endpoint="seed"):
        self.endpoint = endpoint

    def __getitem__(self, key):
        if key in INIT_MODULES:
            if self.endpoint not in (
                "init_setup",
                "init_prelude",
                "init_dynamics",
                "init_electrical",
                "init_first_step",
            ) or not _pin(INIT_SOURCE_PINS[key]):
                raise DemoRejected(
                    "INIT producer unavailable in this endpoint", stage="init_unbound"
                )
            name, expected = INIT_MODULES[key], INIT_SOURCE_PINS[key]
        elif key in PRELUDE_MODULES:
            if self.endpoint not in (
                "init_prelude",
                "init_dynamics",
                "init_electrical",
                "init_first_step",
            ) or not _pin(PRELUDE_SOURCE_PINS[key]):
                raise DemoRejected("INIT prelude producer unavailable", stage="prelude_unbound")
            name, expected = PRELUDE_MODULES[key], PRELUDE_SOURCE_PINS[key]
        elif key in COMPLETION_MODULES:
            if self.endpoint not in (
                "init_dynamics",
                "init_electrical",
                "init_first_step",
            ) or not _pin(COMPLETION_SOURCE_PINS[key]):
                raise DemoRejected("INIT dynamics producer unavailable", stage="dynamics_unbound")
            name, expected = COMPLETION_MODULES[key], COMPLETION_SOURCE_PINS[key]
        elif key in ELECTRICAL_MODULES:
            if self.endpoint not in ("init_electrical", "init_first_step") or not _pin(
                ELECTRICAL_SOURCE_PINS[key]
            ):
                raise DemoRejected(
                    "INIT electrical producer unavailable", stage="electrical_unbound"
                )
            name, expected = ELECTRICAL_MODULES[key], ELECTRICAL_SOURCE_PINS[key]
        elif key in STEP_MODULES:
            if self.endpoint != "init_first_step" or not _pin(STEP_SOURCE_PINS[key]):
                raise DemoRejected("INIT first-step producer unavailable", stage="step_unbound")
            name, expected = STEP_MODULES[key], STEP_SOURCE_PINS[key]
        else:
            name, expected = MODULES[key], SOURCE_PINS[key]
        path = ROOT / _relative(name)
        if path.is_symlink() or snapshot.digest(path) != expected:
            raise DemoRejected("Selected producer changed: " + key, stage="producer")
        module = importlib.import_module(name)
        if sys.modules.get(name) is not module or Path(module.__file__).resolve() != path:
            raise DemoRejected("Actual frozen producer origin required", stage="producer")
        return module


def _function(module, name):
    value = getattr(module, name, None)
    if type(value) is not FunctionType or value.__globals__ is not vars(module):
        raise DemoRejected("Actual public producer function required: " + name, stage="interface")
    return value


def _output(path):
    path = Path(path)
    if (
        not path.is_absolute()
        or ".." in path.parts
        or path == BASE
        or not path.resolve().is_relative_to(BASE.resolve())
        or path.exists()
        or any(p.is_symlink() for p in (path, *path.parents))
        or path == ROOT
        or path.is_relative_to(ROOT)
        or ROOT.is_relative_to(path)
    ):
        raise DemoRejected(
            "Fresh unlinked output contained in the run root required", stage="output"
        )
    return path


def _validate_output(path, declaration, parameter):
    """Use Key's exact metadata-only packet/input protection before any work."""
    output = _output(path)
    inputs = _function(parameter, "packet_inputs")(
        declaration["parameter_packet"], declaration["parameter_sha256"]
    )
    checked = _function(parameter, "output_path")(
        output, declaration["parameter_packet"], inputs["program"]
    )
    if checked != output:
        raise DemoRejected("No output rewrite permitted", stage="output")
    return output, inputs["program"]["root"]


def _read_plan(path, expected):
    path = Path(path)
    if (
        not _pin(expected)
        or path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > 2**20
        or snapshot.digest(path) != expected
    ):
        raise DemoRejected("Exact bounded demonstration plan required", stage="plan")
    value = json.loads(path.read_text())
    if (
        set(value)
        != {
            "kind",
            "source_plan",
            "snapshot_sha256",
            "parameter_packet",
            "parameter_sha256",
            "callback_bootstrap",
            "callback_bootstrap_sha256",
            "auxiliary_configuration",
            "shared_writer_review",
            "flux_operator",
            "endpoint",
            "policy",
            "held",
        }
        or value["kind"] != KIND
        or type(value["endpoint"]) is not str
        or value["endpoint"] not in ENDPOINTS
        or value["source_plan"] != json.loads(json.dumps(source_plan(endpoint=value["endpoint"])))
        or value["flux_operator"] not in FLUX_MODES
        or type(value["flux_operator"]) is not str
        or value["policy"] != POLICY
        or value["held"] is not True
        or type(value["auxiliary_configuration"]) is not dict
        or not all(
            _pin(value[k])
            for k in ("snapshot_sha256", "parameter_sha256", "callback_bootstrap_sha256")
        )
    ):
        raise DemoRejected("Declared complete single-mode plan changed", stage="plan")
    snapshot.verify(ROOT, manifest_sha256=value["snapshot_sha256"])
    return value


def _resources():
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    if (
        os.sched_getaffinity(0) != {POLICY["cpu"]}
        or not 0 < soft <= hard <= POLICY["max_rss_bytes"]
        or any(
            os.environ.get(k) != "1"
            for k in (
                "OPENBLAS_NUM_THREADS",
                "OMP_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        )
        or os.environ.get("CUDA_VISIBLE_DEVICES") != ""
    ):
        raise DemoRejected("Declared native CPU/thread/memory envelope required", stage="resources")
    available = next(
        int(s.split()[1]) * 1024
        for s in Path("/proc/meminfo").read_text().splitlines()
        if s.startswith("MemAvailable:")
    )
    if available < POLICY["reserve_bytes"]:
        raise DemoRejected("Host reserve unavailable", stage="resources")


class ProcessLogLease:
    """Keep the actual descriptor locked until worker exit, including shutdown."""

    def __init__(self, path):
        self.path, self.fd, self.identity = Path(path), None, None
        self.entry_error, self.cleanup_errors = None, ()

    def __enter__(self):
        if self.fd is not None or any(p.is_symlink() for p in (self.path, *self.path.parents)):
            raise DemoRejected("One canonical log lease required", stage="shared_log")
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            value = os.fstat(fd)
            if (
                not stat.S_ISREG(value.st_mode)
                or stat.S_IMODE(value.st_mode) != 0o600
                or value.st_nlink != 1
                or value.st_uid != os.getuid()
            ):
                raise DemoRejected("Private regular stable log lease required", stage="shared_log")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.fd, self.identity = fd, (value.st_dev, value.st_ino)
            self.check()
            _PROCESS_LEASES.append(self)
            return self
        except BaseException as primary:
            self.entry_error = primary
            try:
                os.close(fd)
            except BaseException as cleanup:
                # Retain the descriptor number and cleanup error as forensic
                # state; do not guess whether a failing close completed.
                self.fd = fd
                self.cleanup_errors = (*self.cleanup_errors, cleanup)
            else:
                self.fd = None
            raise

    def check(self):
        value, named = os.fstat(self.fd), self.path.lstat()
        if self.identity != (value.st_dev, value.st_ino) or self.identity != (
            named.st_dev,
            named.st_ino,
        ):
            raise DemoRejected("Retained log lease descriptor/path changed", stage="shared_log")

    def __exit__(self, kind, error, tb):
        self.check()
        # Deliberately do not close or unlock here. Native logging teardown and
        # later atexit handlers still run in this worker. The kernel releases
        # this fd on process exit; the runner never forks scientific children.
        return False


def _writer_session(callback, review_path):
    path = Path(review_path)
    if (
        not _pin(SESSION_REVIEW_SHA256)
        or path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > 2**20
        or snapshot.digest(path) != SESSION_REVIEW_SHA256
    ):
        raise DemoRejected(
            "Explicit shared native writer coordination required", stage="shared_log"
        )
    review = json.loads(path.read_text())
    policy = _function(callback, "source_plan")()["filesystem_conflicts"]["shared_writer_lease"]
    lock = Path(policy["stable_lock_path"])
    if (
        set(review) != {"kind", "lock_path", "all_native_writers_coordinated", "lifetime"}
        or review["kind"] != "cells.seed_demo_shared_log_release@1"
        or review["lock_path"] != str(lock)
        or review["all_native_writers_coordinated"] is not True
        or review["lifetime"] != "through_worker_process_exit"
        or policy["required"] is not True
        or policy["release_at_acquire_callback_return"] is not False
        or lock != (Path.home() / ".betse").resolve() / ".cells-seed-world-writer.lock"
    ):
        raise DemoRejected("Full native writer lifetime coordination changed", stage="shared_log")
    return ProcessLogLease(lock)


def _fail(state, label, error):
    if state.primary is None:
        state.primary = error
    elif state.primary is not error:
        state.secondary.append((label, error))


def _stop(state):
    if state.primary is not None:
        raise state.primary


def _call(state, label, function, *args, **kwargs):
    _stop(state)
    state.stage = label
    row = dict(name=label, status="attempted")
    state.operations.append(row)
    try:
        value = function(*args, **kwargs)
    except BaseException as error:
        # This is a delegated API failure. Its own source/capture classification
        # and raw partials remain on the exact original exception.
        state.delegate_error = error
        _fail(state, label, error)
        row["status"] = "failed"
        raise
    state.last_return = value  # Preserve a raw return before fallible registration.
    row["status"] = "returned"
    _stop(state)
    return value


def _capture(state, evidence, label, value):
    _stop(state)
    try:
        if not evidence.save(label, value):
            raise ValueError("Typed observation refused: " + label)
        state.captures.append(label)
    except BaseException as error:
        _fail(state, label, error)
        raise
    _stop(state)


def _retain(state, evidence, name, owner, module):
    state.owners.append((name, owner))
    trial = owner.trial  # Exactly before the next issuer consumes this owner.
    state.last_trial = trial
    state.trials.append((name, trial))
    phase = owner.phase
    if state.phase is None:
        if phase.p is not state.parameters:
            raise ValueError("Fresh phase must use the actual acquired parameters")
        state.phase = phase
        state.phase_links = (phase.p, phase.cells, phase.sim, phase.dyna, phase.callbacks)
    if phase is not state.phase or any(
        actual is not expected
        for actual, expected in zip(
            (phase.p, phase.cells, phase.sim, phase.dyna, phase.callbacks),
            state.phase_links,
            strict=True,
        )
    ):
        raise ValueError("Demonstration changed its actual phase/parameter/Cells/Simulator/handler")
    if trial.source_completed is not True:
        raise ValueError("Only completed issued stage trials can advance")
    if name in ("poisson", "core", "junctions") and trial.flux_operator != state.flux_operator:
        raise ValueError("Original/disabled inverse mode changed during continuation")
    _capture(state, evidence, name + ".record", module.trial_record(trial))
    for field_name in ("cache", "after"):
        if hasattr(trial, field_name):
            _capture(state, evidence, name + "." + field_name, getattr(trial, field_name))
    return owner


def _execute(state, modules, plan, directory, evidence):
    """One complete source chain; private adapters are used only by blocked tests."""
    if (
        type(state.endpoint) is not str
        or state.endpoint not in ENDPOINTS
        or state.endpoint != plan.get("endpoint", "seed")
    ):
        raise ValueError("Exact declared demonstration endpoint required")
    callback = modules["callback"]
    state.callback = _call(
        state,
        "callback",
        callback.acquire_callback,
        plan["auxiliary_configuration"],
        directory / "callback",
        bootstrap=plan["callback_bootstrap"],
        bootstrap_sha256=plan["callback_bootstrap_sha256"],
        enabled=True,
    )
    parameter = modules["parameters"]
    pair = _call(
        state,
        "parameters",
        parameter.acquire_world_ready,
        plan["parameter_packet"],
        directory / "parameters",
        packet_sha256=plan["parameter_sha256"],
        enabled=True,
    )
    if type(pair) is not tuple or len(pair) != 2:
        raise ValueError("Exact actual WorldReady/parameter pair required")
    state.world_ready, state.parameters = pair
    if state.world_ready.parameters is not state.parameters:
        raise ValueError("Actual WorldReady owner and parameter instance disagree")
    geometry = modules["geometry"]
    owner = _call(
        state,
        "geometry",
        geometry.evaluate_live,
        state.world_ready,
        state.callback,
        directory / "geometry",
        enabled=True,
        evidence_profile="seed_demo",
    )
    # The qualifier retains its own six-stage records. Its final GeometryOwner
    # is authenticated by the actual next public issuer, never by JSON.
    trial = owner.trial
    state.last_trial = trial
    state.trials.append(("geometry", trial))
    state.owners.append(("geometry", owner))
    state.phase = owner.phase
    if state.phase.p is not state.parameters or trial.source_completed is not True:
        raise ValueError("Completed genuine same-p geometry required")
    state.phase_links = (
        state.phase.p,
        state.phase.cells,
        state.phase.sim,
        state.phase.dyna,
        state.phase.callbacks,
    )
    for name, factory in (
        ("poisson", "from_geometry"),
        ("core", "from_world"),
        ("profiles", "from_core"),
        ("junctions", "from_profiles"),
    ):
        module = modules[name]
        keywords = dict(law_id=module.LAW_ID)
        if name == "poisson":
            keywords["flux_operator"] = state.flux_operator
        elif name == "profiles":
            keywords["image_inputs"] = _profile_image_inputs(state, module)
        request = _call(state, name + "_request", getattr(module, factory), owner, **keywords)
        state.requests.append((name, request))
        owner = _call(state, name, module.prepare, request, enabled=True)
        _retain(state, evidence, name, owner, module)
    if state.endpoint != "seed":
        owner = _init_setup(state, modules["init_setup"], owner, evidence)
    if state.endpoint in ("init_prelude", "init_dynamics", "init_electrical", "init_first_step"):
        owner = _init_prelude(state, modules["init_prelude"], owner, evidence)
    if state.endpoint in ("init_dynamics", "init_electrical", "init_first_step"):
        # The completion producer authenticates an already-loaded participant;
        # import it through the same pinned loader before requesting its claim.
        p = state.init_phase.p
        if p is not state.parameters or p is not state.init_links[0]:
            raise ValueError("Original INIT parameters required for network route")
        selected = p.molecules_enabled
        if type(selected) is not bool:
            raise ValueError("Original exact boolean molecular configuration required")
        state.dynamics_native_molecules = selected
        modules["init_tissue"]
        if selected:
            state.dynamics_molecule_api = modules["init_molecules"]
        owner = _init_dynamics(state, modules["init_dynamics"], owner, evidence)
    if state.endpoint in ("init_electrical", "init_first_step"):
        for name in ("init_storage", "init_electrical"):
            owner = _init_field_stage(state, modules[name], owner, evidence, name)
    if state.endpoint == "init_first_step":
        owner = _init_first_step(state, modules["init_first_step"], owner, evidence)
    state.result, state.methods_completed = owner, True
    return owner


def _init_setup(state, module, owner, evidence):
    """Consume the issued endpoint once; keep raw history without rereading it."""
    state.seed_phase = state.phase
    state.seed_links = (*state.phase_links, state.phase.cache)
    state.seed_trial = state.last_trial
    request = _call(state, "init_setup_request", module.from_seed, owner, law_id=module.LAW_ID)
    state.requests.append(("init_setup", request))
    child = _call(state, "init_setup", module.prepare, request, enabled=True)
    state.owners.append(("init_setup", child))
    trial = child.trial
    state.init_trial = trial
    state.last_trial = trial
    state.trials.append(("init_setup", trial))
    phase = child.phase
    state.init_phase = phase
    old_p, old_cells, old_sim, old_dyna, old_callbacks, old_cache = state.seed_links
    if (
        phase is state.seed_phase
        or phase.p is not state.parameters
        or phase.p is not old_p
        or phase.cells is not old_cells
        or phase.callbacks is not old_callbacks
        or phase.sim is old_sim
        or phase.dyna is old_dyna
        or phase.cache is old_cache
        or any(value is None for value in (phase.sim, phase.dyna, phase.cache))
        or trial.source_completed is not True
        or trial.parent_identity != state.seed_trial.identity
        or trial.parameter_record is None
    ):
        raise ValueError("Completed fresh INIT phase must retain exact p/Cells/callback/parent")
    state.phase = phase
    state.phase_links = (phase.p, phase.cells, phase.sim, phase.dyna, phase.callbacks)
    state.init_links = (*state.phase_links, phase.cache)
    _capture(state, evidence, "init_setup.record", module.trial_record(trial))
    _capture(state, evidence, "init_setup.before", trial.before)
    _capture(state, evidence, "init_setup.after", trial.after)
    state.init_setup_completed = True
    return child


def _init_prelude(state, module, owner, evidence):
    """Continue the issued INIT owner; never reopen it after its retirement."""
    parent_trial = state.init_trial
    request = _call(state, "init_prelude_request", module.from_init, owner, law_id=module.LAW_ID)
    state.requests.append(("init_prelude", request))
    child = _call(state, "init_prelude", module.prepare, request, enabled=True)
    state.owners.append(("init_prelude", child))
    trial = child.trial
    state.prelude_trial = state.last_trial = trial
    state.trials.append(("init_prelude", trial))
    phase = child.phase
    state.prelude_phase = phase
    if (
        not state.init_setup_completed
        or phase is not state.init_phase
        or phase is not state.phase
        or any(
            actual is not expected
            for actual, expected in zip(
                (phase.p, phase.cells, phase.sim, phase.dyna, phase.callbacks, phase.cache),
                state.init_links,
                strict=True,
            )
        )
        or trial.source_completed is not True
        or trial.parent_identity != parent_trial.identity
    ):
        raise ValueError("Completed INIT prelude must retain the exact phase, objects and parent")
    _capture(state, evidence, "init_prelude.record", module.trial_record(trial))
    _capture(state, evidence, "init_prelude.before", trial.before)
    _capture(state, evidence, "init_prelude.after", trial.after)
    # Trial retains the actual frames. The record names their identities;
    # persist the original returned values without trying to serialize frames.
    _capture(
        state, evidence, "init_prelude.raw_returns", tuple(raw for _, raw in trial.raw_returns)
    )
    state.init_prelude_completed = True
    return child


def _init_dynamics(state, module, owner, evidence):
    """Finish ordinary setup on the issued prelude; no time-loop or replay path."""
    state.dynamics_api = module
    parent_trial = state.prelude_trial
    selected = state.dynamics_native_molecules
    if type(selected) is not bool or state.init_phase.p.molecules_enabled is not selected:
        raise ValueError("Original molecular route changed before completion request")
    files = _profile_image_inputs(state, module, include_bitmap=True)
    state.dynamics_file_inputs = files
    request = _call(
        state,
        "init_dynamics_request",
        module.from_prelude_native_molecules if selected else module.from_prelude,
        owner,
        law_id=module.MOLECULE_LAW_ID if selected else module.LAW_ID,
        file_inputs=files,
    )
    state.requests.append(("init_dynamics", request))
    if getattr(request, "native_molecules", False) is not selected:
        raise ValueError("Actual completion request does not retain the chosen molecular route")
    child = _call(state, "init_dynamics", module.prepare, request, enabled=True)
    state.owners.append(("init_dynamics", child))
    trial = child.trial
    state.dynamics_trial = state.last_trial = trial
    state.trials.append(("init_dynamics", trial))
    phase = child.phase
    state.dynamics_phase = phase
    tissue = trial.tissue_record
    molecule = getattr(trial, "molecule_record", None)
    state.dynamics_molecule_record = molecule
    if (
        not state.init_prelude_completed
        or phase is not state.prelude_phase
        or phase is not state.init_phase
        or phase is not state.phase
        or any(
            actual is not expected
            for actual, expected in zip(
                (phase.p, phase.cells, phase.sim, phase.dyna, phase.callbacks, phase.cache),
                state.init_links,
                strict=True,
            )
        )
        or trial.source_completed is not True
        or trial.parent_identity != parent_trial.identity
        or tissue is None
        or tissue.source_completed is not True
        or tissue.init_trial is not state.init_trial
        or tissue.work_views_are_non_additive is not True
        or tuple(name for name, _ in tissue.calls) != ("init_profiles", "init_events")
        or not trial.rng_calls
        or any(
            row.index != index
            or row.returned is not True
            or row.primary is not None
            or row.capture_errors
            for index, row in enumerate(trial.rng_calls)
        )
    ):
        raise ValueError(
            "Completed INIT dynamics must retain exact lineage and complete tissue/RNG evidence"
        )
    if phase.p.molecules_enabled is not selected:
        raise ValueError("Original molecular flag changed during completion")
    if selected:
        if (
            request.native_molecules is not True
            or trial.request_identity != request.identity
            or molecule is None
            or molecule.source_completed is not True
            or not _pin(molecule.identity)
            or molecule.original_claim is not tissue.completion_claim
            or molecule.original_molecules is not phase.sim.molecules
            or molecule.original_core is not phase.sim.molecules.core
            or not molecule.source_work
            or any(row["returned"] is not True for row in molecule.source_work)
        ):
            raise ValueError("Completed original molecular source and same actual owners required")
    elif molecule is not None:
        raise ValueError("Unrequested molecular source cannot replace the disabled route")
    _capture(state, evidence, "init_dynamics.record", module.trial_record(trial))
    _capture(state, evidence, "init_dynamics.before", trial.before)
    _capture(state, evidence, "init_dynamics.after", trial.after)
    _capture(state, evidence, "init_dynamics.stream_before", trial.stream_before)
    _capture(state, evidence, "init_dynamics.stream_after", trial.stream_after)
    _capture(
        state,
        evidence,
        "init_dynamics.rng_calls",
        tuple(
            dict(
                index=row.index,
                library=row.library,
                operation=row.operation,
                before=row.before,
                after=row.after,
                raw_return=row.raw_return,
                returned=row.returned,
            )
            for row in trial.rng_calls
        ),
    )
    _capture(
        state,
        evidence,
        "init_dynamics.tissue_record",
        _tissue_values(tissue),
    )
    _capture(
        state, evidence, "init_dynamics.raw_returns", tuple(raw for _, raw in trial.raw_returns)
    )
    if selected:
        _capture(state, evidence, "init_dynamics.molecule_record", _molecule_values(molecule))
        _capture(
            state,
            evidence,
            "init_dynamics.molecule_raw_returns",
            _raw_failure_values(molecule.raw_returns),
        )
        state.init_molecule_network_completed = True
    state.init_dynamics_completed = True
    return child


def _store_values(rows):
    """Retain original assignment witnesses, including both raw values."""
    if type(rows) not in (tuple, list) or len(rows) > 100000:
        raise ValueError("Bounded original assignment rows required")
    for row in rows:
        if (
            type(row) is not tuple
            or len(row) != 6
            or type(row[0]) is not int
            or row[0] <= 0
            or type(row[1]) is not str
            or type(row[4]) is not bool
            or type(row[5]) is not bool
        ):
            raise ValueError("Exact original assignment witness required")
    return tuple(rows)


def _init_field_stage(state, module, owner, evidence, name):
    """Advance one actual owner; capture its values before the next retirement."""
    if name == "init_storage":
        field, factory = "storage", "from_dynamics"
        parent_trial = state.dynamics_trial
        parent_completed = state.init_dynamics_completed
        completed_field, rng_fields = "source_completed", ("stream_before", "stream_after")
    elif name == "init_electrical":
        field, factory = "electrical", "from_storage"
        parent_trial = state.storage_trial
        parent_completed = state.init_storage_completed
        completed_field, rng_fields = "completed", ("rng_before", "rng_after")
    else:
        raise ValueError("Exact storage/electrical continuation required")
    if parent_completed is not True or parent_trial is None:
        raise ValueError("Completed retained parent trial required before field continuation")
    request = _call(state, name + "_request", getattr(module, factory), owner, law_id=module.LAW_ID)
    state.requests.append((name, request))
    child = _call(state, name, module.prepare, request, enabled=True)
    state.owners.append((name, child))
    trial = child.trial
    setattr(state, field + "_trial", trial)
    state.last_trial = trial
    state.trials.append((name, trial))
    phase = child.phase
    setattr(state, field + "_phase", phase)
    if (
        phase is not state.phase
        or phase is not state.init_phase
        or any(
            actual is not expected
            for actual, expected in zip(
                (phase.p, phase.cells, phase.sim, phase.dyna, phase.callbacks, phase.cache),
                state.init_links,
                strict=True,
            )
        )
        or getattr(trial, completed_field) is not True
        or trial.parent_identity != parent_trial.identity
    ):
        raise ValueError("Completed electrical chain must retain exact phase/objects/parent")
    before, after = (getattr(trial, key) for key in rng_fields)
    if (
        type(before) is not tuple
        or type(after) is not tuple
        or len(before) != 2
        or len(after) != 2
        or not all(_pin(value) for value in (*before, *after))
        or before != after
    ):
        raise ValueError("Storage/electrical source must retain both original stream identities")
    stores = _store_values(trial.stores)
    if not stores or any(row[5] is not True for row in stores):
        raise ValueError("Completed source requires completed original assignment witnesses")
    _capture(state, evidence, name + ".record", module.trial_record(trial))
    _capture(state, evidence, name + ".before", trial.before)
    _capture(state, evidence, name + ".after", trial.after)
    _capture(state, evidence, name + "." + rng_fields[0], before)
    _capture(state, evidence, name + "." + rng_fields[1], after)
    _capture(state, evidence, name + ".stores", stores)
    _capture(state, evidence, name + ".raw_returns", _raw_failure_values(trial.raw_returns))
    setattr(state, name + "_completed", True)
    return child


def _field_failure_evidence(state, evidence):
    """Recover available field-stage values without reopening consumed owners."""
    if state.endpoint not in ("init_electrical", "init_first_step") or state.primary is None:
        return
    if state.endpoint == "init_first_step" and state.init_electrical_completed:
        return
    names = [
        name
        for name in ("init_storage", "init_electrical")
        if any(row["name"] in (name + "_request", name) for row in state.operations)
    ]
    if not names:
        return
    name = names[-1]
    field = name.removeprefix("init_")
    context = None
    failure = state.delegate_error if state.delegate_error is not None else state.primary
    attributes = ("init_storage_partial", "partial") if field == "storage" else ("partial",)
    for attribute in attributes:
        try:
            context = getattr(failure, attribute, None)
        except BaseException as error:
            _fail(state, name + ".failure.context", error)
        if context is not None:
            break
    state.electrical_failure_context = context
    trial = getattr(state, field + "_trial")
    source = trial if trial is not None else context
    if source is None:
        return
    missing = object()

    def value(obj, key):
        return getattr(obj, key, missing)

    def project(key, function):
        raw = value(source, key)
        return missing if raw is missing else function(raw)

    projections = (
        ("before", lambda: value(source, "before")),
        ("after", lambda: value(source, "after")),
        (
            "stream_before",
            lambda: value(source, "stream_before" if field == "storage" else "rng_before"),
        ),
        (
            "stream_after",
            lambda: value(source, "stream_after" if field == "storage" else "rng_after"),
        ),
        ("retained_stream_ids", lambda: value(context, "stream_ids")),
        ("stores", lambda: project("stores", _store_values)),
        ("raw_returns", lambda: project("raw_returns", _raw_failure_values)),
        ("last_store", lambda: value(context, "last_store")),
        (
            "last_raw_return",
            lambda: missing if value(context, "last_raw") is missing else context.last_raw[1],
        ),
        (
            "primary",
            lambda: dict(
                primary=_failure_identity(state.primary),
                cause=_failure_identity(state.primary.__cause__),
                live_claim_or_frame_serialization=False,
            ),
        ),
    )
    for key, observe in projections:
        label = name + ".failure." + key
        row = dict(label=label, status="attempted")
        state.electrical_failure_captures.append(row)
        try:
            raw = observe()
            if raw is missing:
                row["status"] = "unavailable"
                continue
            if not evidence.save(label, raw):
                raise ValueError("Failure observation refused: " + label)
            row["status"] = "saved"
            state.captures.append(label)
        except BaseException as error:
            row.update(status="capture_failed", error=_failure_identity(error))
            _fail(state, label, error)


def _init_first_step(state, module, owner, evidence):
    """Consume the electrical owner once, retaining its already-verified trial."""
    parent = state.electrical_trial
    if state.init_electrical_completed is not True or parent is None:
        raise ValueError("Completed retained electrical trial required before first step")
    request = _call(
        state, "init_first_step_request", module.from_electrical, owner, law_id=module.LAW_ID
    )
    state.requests.append(("init_first_step", request))
    child = _call(state, "init_first_step", module.prepare, request, enabled=True)
    state.owners.append(("init_first_step", child))
    trial = child.trial
    state.first_step_trial = state.last_trial = trial
    state.trials.append(("init_first_step", trial))
    phase = child.phase
    state.first_step_phase = phase
    if (
        phase is not state.phase
        or phase is not state.init_phase
        or any(
            actual is not expected
            for actual, expected in zip(
                (phase.p, phase.cells, phase.sim, phase.dyna, phase.callbacks, phase.cache),
                state.init_links,
                strict=True,
            )
        )
        or trial.parent_identity != parent.identity
        or trial.request_identity != request.identity
        or trial.iteration_complete is not True
        or type(trial.loop_index) is not int
        or trial.loop_index != 0
        or type(trial.loop_returned) is not bool
        or type(trial.selected_stop) is not bool
        or trial.loop_returned == trial.selected_stop
    ):
        raise ValueError("One complete original INIT iteration on the same retained chain required")
    before, after = trial.stream_before, trial.stream_after
    if (
        type(before) is not tuple
        or type(after) is not tuple
        or len(before) != 2
        or len(after) != 2
        or not all(_pin(value) for value in (*before, *after))
        or before != parent.rng_after
    ):
        raise ValueError("First-step original stream handoff required")
    # The producer has already sealed these snapshots. Do not decode, recalculate
    # the native t=0 label, or synthesize an elapsed-time value from p.dt.
    for name in ("before", "after", "calendar", "sampled", "source_time_label", "configured_dt"):
        if not _pin(getattr(trial, name).identity):
            raise ValueError("Original first-step snapshot identity required: " + name)
    stores = _store_values(trial.stores)
    if not stores or any(row[5] is not True for row in stores):
        raise ValueError("Complete first-step assignment witnesses required")
    state.first_step_record = module.trial_record(trial)
    _capture(state, evidence, "init_first_step.record", state.first_step_record)
    for name in ("before", "after", "calendar", "sampled", "source_time_label", "configured_dt"):
        _capture(state, evidence, "init_first_step." + name, getattr(trial, name))
    _capture(state, evidence, "init_first_step.stream_before", before)
    _capture(state, evidence, "init_first_step.stream_after", after)
    _capture(state, evidence, "init_first_step.stores", stores)
    _capture(state, evidence, "init_first_step.raw_returns", _raw_failure_values(trial.raw_returns))
    state.init_first_step_completed = True
    state.init_time_steps_completed = 1
    return child


def _step_work_values(rows):
    """Closed work metadata only; preserve raw frames in the retained live partial."""
    if type(rows) not in (tuple, list) or len(rows) > 100000:
        raise ValueError("Bounded original first-step work rows required")
    result = []
    for row in rows:
        code = row["code"]
        if type(code) is not CodeType:
            raise ValueError("Retained original work CodeType required")
        result.append((code.co_filename, code.co_firstlineno, row["body_started"], row["returned"]))
    return tuple(result)


def _step_failure_evidence(state, evidence):
    """Capture each available original field independently, without owner/RNG reads."""
    if state.endpoint != "init_first_step" or state.primary is None:
        return
    if not any(
        row["name"] in ("init_first_step_request", "init_first_step") for row in state.operations
    ):
        return
    failure = state.delegate_error if state.delegate_error is not None else state.primary
    context, trial = None, state.first_step_trial
    for name in ("partial", "trial"):
        try:
            value = getattr(failure, name, None)
            if name == "partial":
                context = value
                state.first_step_failure_context = context
            elif trial is None and value is not None:
                trial = value
                state.first_step_trial = value
        except BaseException as error:
            _fail(state, "init_first_step.failure." + name, error)
    missing = object()

    def value(key, partial_key=None):
        if trial is not None:
            found = getattr(trial, key, missing)
            if found is not missing:
                return found
        return getattr(context, key if partial_key is None else partial_key, missing)

    def project(key, function):
        found = value(key)
        return missing if found is missing else function(found)

    def sampled():
        found = value("sampled")
        if trial is None and type(found) is set:
            if len(found) > 100000:
                raise ValueError("Bounded retained sampling set required")
            # The producer seals this same tuple projection. Keep the actual
            # set in the raw partial; no sorting or manufactured sample labels.
            return tuple(found)
        return found

    projections = (
        ("record", lambda: missing if state.first_step_record is None else state.first_step_record),
        ("before", lambda: value("before")),
        ("after", lambda: value("after")),
        ("calendar", lambda: value("calendar", "time_steps")),
        ("sampled", sampled),
        ("source_time_label", lambda: value("source_time_label")),
        ("configured_dt", lambda: value("configured_dt")),
        ("stream_before", lambda: value("stream_before", "stream_ids")),
        ("stream_after", lambda: value("stream_after")),
        ("loop_index", lambda: value("loop_index")),
        ("iteration_complete", lambda: value("iteration_complete")),
        ("loop_returned", lambda: value("loop_returned")),
        ("selected_stop", lambda: value("selected_stop", "selected_stopped")),
        ("work", lambda: project("work", _step_work_values)),
        ("stores", lambda: project("stores", _store_values)),
        ("raw_returns", lambda: project("raw_returns", _raw_failure_values)),
        ("last_store", lambda: getattr(context, "last_store", missing)),
        (
            "last_raw_return",
            lambda: (
                missing if getattr(context, "last_raw", missing) is missing else context.last_raw[1]
            ),
        ),
        (
            "primary",
            lambda: dict(
                primary=_failure_identity(state.primary),
                cause=_failure_identity(state.primary.__cause__),
                live_claim_or_frame_serialization=False,
            ),
        ),
    )
    for key, observe in projections:
        label = "init_first_step.failure." + key
        row = dict(label=label, status="attempted")
        state.first_step_failure_captures.append(row)
        try:
            raw = observe()
            if raw is missing:
                row["status"] = "unavailable"
                continue
            if not evidence.save(label, raw):
                raise ValueError("Failure observation refused: " + label)
            row["status"] = "saved"
            state.captures.append(label)
        except BaseException as error:
            row.update(status="capture_failed", error=_failure_identity(error))
            _fail(state, label, error)


def _failure_identity(error):
    if error is None:
        return None
    return dict(identity=id(error), type=type(error).__qualname__)


def _tissue_values(tissue):
    return dict(
        record_identity=id(tissue),
        completion_claim_identity=id(tissue.completion_claim),
        init_trial_identity=tissue.init_trial.identity,
        calls=tuple(name for name, _ in tissue.calls),
        source_completed=tissue.source_completed,
        work_views_are_non_additive=tissue.work_views_are_non_additive,
        live_claim_or_frame_serialization=False,
    )


def _molecule_values(record):
    """Transport actual completed evidence; retain live objects only in the original trial."""
    if (
        type(record.source_work) is not tuple
        or len(record.source_work) > 100000
        or type(record.constructor_work) is not tuple
        or len(record.constructor_work) > 100000
        or type(record.dynamic_callbacks) is not tuple
        or len(record.dynamic_callbacks) > 100000
    ):
        raise ValueError("Bounded original molecular work required")
    return dict(
        identity=record.identity,
        record_identity=id(record),
        completion_claim_identity=id(record.original_claim),
        molecules_identity=id(record.original_molecules),
        core_identity=id(record.original_core),
        source_completed=record.source_completed,
        constructors=tuple(
            (name, id(value), id(frame)) for name, value, frame in record.constructor_work
        ),
        source_work=_molecule_work_values(record.source_work),
        dynamic_callbacks=tuple(
            (id(value), id(getter), id(setter), id(frame))
            for value, getter, setter, frame, _ in record.dynamic_callbacks
        ),
        work_views_are_non_additive=True,
        live_claim_or_frame_serialization=False,
    )


def _molecule_work_values(rows):
    if type(rows) not in (tuple, list) or len(rows) > 100000:
        raise ValueError("Bounded retained molecular source work required")
    result = []
    for row in rows:
        code = row["code"]
        if type(code) is not CodeType:
            raise ValueError("Actual retained molecular CodeType required")
        result.append((code.co_filename, code.co_firstlineno, id(row["frame"]), row["returned"]))
    return tuple(result)


def _molecular_failure_context(state, context):
    """Recover only original associations through the public forensic interfaces."""
    if state.dynamics_molecule_record is not None:
        return
    if state.dynamics_trial is not None:
        state.dynamics_molecule_record = getattr(state.dynamics_trial, "molecule_record", None)
        if state.dynamics_molecule_record is not None:
            return
    if context is None or getattr(context, "claim", None) is None:
        return
    original = _function(state.dynamics_api, "failed_context")(context.claim)
    request = next((value for name, value in state.requests if name == "init_dynamics"), None)
    if original is not context or request is None or context.request is not request:
        raise ValueError("Original failed Completion/request association required")
    session = context.molecule_session
    if session is None:
        return
    if context.molecule is not state.dynamics_molecule_api:
        raise ValueError("Original retained molecular participant required")
    if context.molecule_record is not None:
        # Molecular source may have finished before Completion sealing failed.
        # Its raw record is evidence, not completed-demo authority.
        state.dynamics_molecule_record = context.molecule_record
        return
    partial = _function(state.dynamics_molecule_api, "failed_context")(session)
    if (
        partial.completion is not context
        or partial.claim is not context.claim
        or partial.session is not session
    ):
        raise ValueError("Original failed molecular session/Completion association required")
    state.dynamics_molecule_failure_context = partial


def _rng_failure_values(rows):
    if type(rows) not in (tuple, list) or len(rows) > 4096:
        raise ValueError("Bounded original RNG rows required for failure observation")
    return tuple(
        dict(
            index=row.index,
            library=row.library,
            operation=row.operation,
            before=row.before,
            after=row.after,
            raw_return=row.raw_return,
            returned=row.returned,
            primary=_failure_identity(row.primary),
            capture_errors=tuple(
                (name, _failure_identity(error)) for name, error in row.capture_errors
            ),
        )
        for row in rows
    )


def _raw_failure_values(rows):
    if type(rows) not in (tuple, list) or len(rows) > 100000:
        raise ValueError("Bounded original return rows required for failure observation")
    return tuple(raw for _, raw in rows)


def _dynamics_failure_evidence(state, evidence):
    """Independent forensic writes; never validate a consumed owner or read RNG."""
    if (
        state.endpoint not in ("init_dynamics", "init_electrical", "init_first_step")
        or state.init_dynamics_completed
        or state.primary is None
    ):
        return
    if not any(row["name"] == "init_dynamics" for row in state.operations):
        return
    context = None
    failure = state.delegate_error if state.delegate_error is not None else state.primary
    try:
        context = getattr(failure, "init_dynamics_completion_partial", None)
        if context is None:
            context = getattr(failure, "partial", None)
        state.dynamics_failure_context = context
    except BaseException as error:
        _fail(state, "init_dynamics.failure.context", error)
    if state.dynamics_native_molecules is True:
        try:
            # error.partial may be Completion itself, and ordinary native
            # errors need not have it. Never label it as molecular by guesswork.
            _molecular_failure_context(state, context)
        except BaseException as error:
            _fail(state, "init_dynamics.failure.molecule_context", error)
    source = state.dynamics_trial if state.dynamics_trial is not None else context
    if source is None:
        return
    missing = object()

    def field(obj, name):
        return getattr(obj, name, missing)

    def project(name, function):
        value = field(source, name)
        return missing if value is missing or value is None else function(value)

    projections = (
        ("before", lambda: field(source, "before")),
        ("after", lambda: field(source, "after")),
        ("stream_before", lambda: field(source, "stream_before")),
        ("stream_after", lambda: field(source, "stream_after")),
        ("current_streams", lambda: field(context, "current_streams")),
        ("rng_calls", lambda: project("rng_calls", _rng_failure_values)),
        ("tissue_record", lambda: project("tissue_record", _tissue_values)),
        ("raw_returns", lambda: project("raw_returns", _raw_failure_values)),
        ("last_rng_return", lambda: field(context, "last_rng_return")),
        ("last_raw_return", lambda: project("last_raw", lambda pair: pair[1])),
        (
            "primary",
            lambda: dict(
                primary=_failure_identity(state.primary),
                cause=_failure_identity(state.primary.__cause__),
                live_claim_or_frame_serialization=False,
            ),
        ),
    )
    if state.dynamics_native_molecules is True:
        molecular = state.dynamics_molecule_failure_context

        def molecule_field(name):
            if state.dynamics_molecule_record is not None:
                return field(state.dynamics_molecule_record, name)
            return field(molecular, name)

        projections += (
            (
                "molecule_record",
                lambda: (
                    missing
                    if state.dynamics_molecule_record is None
                    else _molecule_values(state.dynamics_molecule_record)
                ),
            ),
            (
                "molecule_raw_returns",
                lambda: (
                    missing
                    if molecule_field("raw_returns") is missing
                    else _raw_failure_values(molecule_field("raw_returns"))
                ),
            ),
            (
                "molecule_work",
                lambda: (
                    missing
                    if field(molecular, "work") is missing
                    else _molecule_work_values(molecular.work)
                ),
            ),
            (
                "molecule_last_return",
                lambda: (
                    missing if field(molecular, "last_raw") is missing else molecular.last_raw[1]
                ),
            ),
        )
    for name, observe in projections:
        label = "init_dynamics.failure." + name
        row = dict(label=label, status="attempted")
        state.dynamics_failure_captures.append(row)
        try:
            value = observe()
            if value is missing:
                row["status"] = "unavailable"
                continue
            if not evidence.save(label, value):
                raise ValueError("Failure observation refused: " + label)
            row["status"] = "saved"
            state.captures.append(label)
        except BaseException as error:
            row.update(status="capture_failed", error=_failure_identity(error))
            _fail(state, label, error)


def _profile_image_inputs(state, module, *, include_bitmap=False):
    """Declare bytes for observed filenames; from_core authenticates picker ancestry."""
    selected = []
    for profile in state.phase.dyna.tissue_name_to_profile.values():
        filename = getattr(profile.picker, "filename", None)
        if filename is not None:
            if type(filename) is not str:
                raise ValueError("Original native picker filename required")
            if filename in selected:
                continue  # Multiple actual profiles may share the same original image.
            selected.append(filename)
    if include_bitmap:
        bitmap = getattr(state.parameters, "grad_bm_fn", None)
        if bitmap is not None:
            dirname = state.parameters.conf_dirname
            if type(bitmap) is not str or type(dirname) is not str:
                raise ValueError("Original configured bitmap filename/directory required")
            # This declares input bytes only. The native modulator still resolves
            # its actual call arguments and checks their FileInput itself.
            filename = os.path.join(dirname, bitmap)
            if filename not in selected:
                selected.append(filename)
        if len(selected) > 64:
            raise ValueError("Bounded original completion file declarations required")
    if not selected:
        return ()
    producer = ROOT / INPUT_METADATA
    if producer.is_symlink() or snapshot.digest(producer) != INPUT_METADATA_SHA256:
        raise ValueError("Reviewed original input metadata producer changed")
    metadata = importlib.import_module("validation.betse.native_seed_demo_inputs")
    if Path(metadata.__file__).resolve() != producer:
        raise ValueError("Actual frozen original input metadata required")
    original = _function(metadata, "_source")()
    root = Path(state.input_root)
    if not root.is_absolute() or root.resolve() != root:
        raise ValueError("Original acquired parameter input root required")
    result = []
    for filename in selected:
        path = Path(filename)
        if not path.is_absolute() or not path.is_relative_to(root):
            raise ValueError("Profile image is outside the actual parameter input tree")
        name = str(path.relative_to(root))
        row = original["files"].get(name)
        if row is None:
            raise ValueError("Profile image is absent from the original data bundle")
        value = _call(
            state,
            "init_dynamics_file" if include_bitmap else "profile_image_file",
            _function(module.files, "input_file"),
            filename,
            sha256=row["sha256"],
            origin="original BETSE input bundle: " + metadata.BUNDLE_SHA256 + "/" + name,
        )
        result.append(value)
    return tuple(result)


def _finish(state, evidence, directory):
    if state.primary is not None:
        # The raw trial still records an actually completed selected body.
        # Endpoint credit requires complete surrounding execution/evidence too.
        state.init_first_step_completed, state.init_time_steps_completed = False, 0
        try:
            _step_failure_evidence(state, evidence)
        except BaseException as error:
            _fail(state, "init_first_step.failure.finalizer", error)
        try:
            _field_failure_evidence(state, evidence)
        except BaseException as error:
            _fail(state, "init_electrical.failure.finalizer", error)
        try:
            _dynamics_failure_evidence(state, evidence)
        except BaseException as error:
            _fail(state, "init_dynamics.failure.finalizer", error)
        try:
            evidence.failure(state.primary)
        except BaseException as error:
            _fail(state, "failure_forensics", error)
    try:
        snapshot.write_json(
            directory / "outcome.json",
            dict(
                kind=KIND,
                status="completed"
                if state.methods_completed and state.primary is None
                else "failed",
                flux_operator=state.flux_operator,
                endpoint=state.endpoint,
                init_setup_completed=state.init_setup_completed,
                init_prelude_completed=state.init_prelude_completed,
                init_dynamics_completed=state.init_dynamics_completed,
                init_native_molecules=state.dynamics_native_molecules,
                init_molecule_network_completed=state.init_molecule_network_completed,
                init_storage_completed=state.init_storage_completed,
                init_electrical_completed=state.init_electrical_completed,
                init_first_step_completed=state.init_first_step_completed,
                first_step_failure_captures=state.first_step_failure_captures,
                electrical_failure_captures=state.electrical_failure_captures,
                dynamics_failure_captures=state.dynamics_failure_captures,
                init_time_steps_completed=state.init_time_steps_completed,
                original_flux_defect_repaired=False,
                methods_completed=state.methods_completed,
                stage=state.stage,
                completed_stage_trials=[name for name, _ in state.trials],
                operations=[dict(name=r["name"], status=r["status"]) for r in state.operations],
                primary=None if state.primary is None else type(state.primary).__qualname__,
                secondary=[dict(stage=n, error=type(e).__qualname__) for n, e in state.secondary],
                captures=evidence.rows,
                stage_work_is_non_additive=True,
                live_failed_owner_serialization_claimed=False,
                complete_seed_runner_or_INIT_SIM_restart_claim=False,
                scientific_or_physical_credit=0,
            ),
        )
        state.evidence_completed = True
    except BaseException as error:
        state.init_first_step_completed, state.init_time_steps_completed = False, 0
        _fail(state, "outcome", error)


def _run(state, modules, plan, directory, evidence, session):
    """Protected execution; source failures cannot be hidden by logging or capture."""
    state.session = session
    try:
        with session:
            try:
                _execute(state, modules, plan, directory, evidence)
                _stop(state)
            except BaseException as error:
                # Even an erroneous suppressing session must not erase the
                # original failure or make a partial chain look completed.
                _fail(state, "execution", error)
                raise
    except BaseException as error:
        _fail(state, "execution_or_session", error)
    finally:
        _finish(state, evidence, directory)
    _stop(state)
    if not state.methods_completed or not state.evidence_completed:
        raise ValueError("No complete source/evidence endpoint")
    return state


def run_demo(plan, directory, *, plan_sha256, enabled=False):
    global _ATTEMPT
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise DemoRejected("Combined actual demonstration remains held", stage="release")
    if _ACTIVE:
        error = DemoRejected("A fresh process is required for another demonstration", stage="entry")
        _fail(_ACTIVE[-1], "reentry", error)
        raise error
    if _ATTEMPT is not None:
        raise DemoRejected("Each mode/attempt requires a fresh worker", stage="consumed")
    modules = _dependencies()
    declaration = _read_plan(plan, plan_sha256)
    if declaration["endpoint"] != "seed":
        modules = _dependencies(declaration["endpoint"])
    output, input_root = _validate_output(directory, declaration, modules["parameters"])
    _resources()
    state = Execution(declaration["flux_operator"], endpoint=declaration["endpoint"])
    state.input_root = input_root
    _ATTEMPT = state
    _ACTIVE.append(state)
    try:
        callback = modules["callback"]
        session = _writer_session(callback, declaration["shared_writer_review"])
        output.mkdir(parents=True)
        from validation.betse.native_single_cell_prefix_qualification import Evidence

        evidence = Evidence(output, sidecars=True, capture_writer=_evidence_writer())
        result = _run(state, modules, declaration, output, evidence, session)
    except BaseException as error:
        _fail(state, "run", error)
        result = None
    finally:
        try:
            if _ACTIVE and _ACTIVE[-1] is state:
                _ACTIVE.pop()
            else:
                raise ValueError("Original demonstration reservation changed")
        except BaseException as error:
            _fail(state, "reservation", error)
    if state.primary is not None or result is None:
        cause = state.primary if state.primary is not None else ValueError("No issued endpoint")
        raise DemoRejected(
            "Genuine SEED demonstration failed", stage=state.stage, partial=state
        ) from cause
    return result


def prepare(
    repository,
    directory,
    *,
    inputs,
    inputs_sha256,
    python,
    bootstrap,
    bootstrap_sha256,
    auxiliary_configuration,
    flux_operator,
    endpoint="seed",
    shared_writer_review=None,
    extra_sources=(),
):
    """Freeze the full closure once via Key's existing current-checkout prepare."""
    if type(flux_operator) is not str or flux_operator not in FLUX_MODES:
        raise DemoRejected("Choose exactly original or disabled flux inverse", stage="mode")
    if type(extra_sources) is not tuple:
        raise DemoRejected("Explicit immutable extra source roster required", stage="source_roster")
    for name in extra_sources:
        snapshot.relative_path(name)
        if Path(name).parts[0] not in ("src", "validation", "scripts", "tests"):
            raise DemoRejected(
                "Only checkout execution sources may extend the image", stage="source_roster"
            )
    modules = _dependencies(endpoint)
    if Path(repository).resolve() != ROOT:
        raise DemoRejected("One-way canonical checkout preparation required", stage="checkout")
    parameter = modules["parameters"]
    extra = (
        FILE,
        TEST,
        RUNNER,
        INPUT_METADATA,
        _relative(EVIDENCE_MODULE),
        *(_relative(name) for name in MODULES.values()),
        *(_relative(name) for name in INIT_MODULES.values() if endpoint != "seed"),
        *(
            _relative(name)
            for name in PRELUDE_MODULES.values()
            if endpoint in ("init_prelude", "init_dynamics", "init_electrical", "init_first_step")
        ),
        *(
            _relative(name)
            for name in COMPLETION_MODULES.values()
            if endpoint in ("init_dynamics", "init_electrical", "init_first_step")
        ),
        *(
            _relative(name)
            for name in ELECTRICAL_MODULES.values()
            if endpoint in ("init_electrical", "init_first_step")
        ),
        *(_relative(name) for name in STEP_MODULES.values() if endpoint == "init_first_step"),
        *extra_sources,
    )
    value = _function(parameter, "prepare")(
        repository,
        directory,
        inputs=inputs,
        inputs_sha256=inputs_sha256,
        python=python,
        extra_sources=extra,
    )
    directory = Path(directory)
    snapshot.write_json(
        directory / "demo-plan.json",
        dict(
            kind=KIND,
            source_plan=source_plan(endpoint=endpoint),
            snapshot_sha256=snapshot.digest(directory / "source/SNAPSHOT.json"),
            parameter_packet=str(directory),
            parameter_sha256=snapshot.digest(directory / "inputs.json"),
            callback_bootstrap=str(bootstrap),
            callback_bootstrap_sha256=bootstrap_sha256,
            auxiliary_configuration=auxiliary_configuration,
            shared_writer_review=str(shared_writer_review),
            flux_operator=flux_operator,
            endpoint=endpoint,
            policy=dict(POLICY),
            held=True,
        ),
    )
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-plan", action="store_true")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--plan-sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.source_plan:
        print(json.dumps(source_plan(), indent=2))
        return 0
    if args.plan is not None and args.output is not None and args.plan_sha256:
        run_demo(args.plan, args.output, plan_sha256=args.plan_sha256, enabled=True)
        return 0
    parser.error("Use source-plan or an exactly released plan in a bounded fresh worker")


if __name__ == "__main__":
    raise SystemExit(main())
