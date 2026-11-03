"""Immutable native-blocked controls for the retained-world INIT consumer."""

import importlib
import json
import os
from pathlib import Path
from types import FunctionType

from validation.betse import native_seed_core_integration_software as reuse

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_init_retained_world.py"
LITERAL = "src/cells/processes/betse_native_init_retained_world_source.py"
TEST = "tests/unit/test_betse_native_init_retained_world.py"
FILE = "validation/betse/betse_native_init_retained_world_software.py"
MODULE = "validation.betse.betse_native_init_retained_world_software"
SOFTWARE_RELEASE = "BETSE_NATIVE_INIT_RETAINED_WORLD_SOFTWARE_RELEASED"
OWNED = (SOURCE, LITERAL, TEST, FILE)
INTEGRATION_SECONDS = 1800
INTEGRATION_SELECTIONS = (
    "test_dynamics_issued_public_INIT_pilot_has_no_hydrated_or_registry_injected_owner",
    "test_dynamics_issued_joint_public_chain_preserves_original_phase_and_once_only_epoch",
)
FORBIDDEN_MODULES = reuse.FORBIDDEN_MODULES
NATIVE_ROOT, snapshot, base = reuse.NATIVE_ROOT, reuse.snapshot, reuse.base
_RAW_FAILURES = ()


def is_forbidden_frame(frame):
    name = frame.f_globals.get("__name__")
    if (
        name in FORBIDDEN_MODULES
        or (
            name == "cells.processes.betse_native_init_retained_world"
            and frame.f_code.co_name == "_acquire"
        )
        or (
            name == "cells.processes.betse_native_parameter_seed_init_transition"
            and frame.f_code.co_name in ("seed_to_init", "_reserve")
        )
        or (
            name == "cells.processes.betse_native_init_dynamics_prelude"
            and frame.f_code.co_name == "_namespace"
        )
        or name == "cells.processes.betse_native_init_dynamics_prelude_source"
    ):
        return True
    path = os.path.normpath(frame.f_code.co_filename)
    return os.path.isabs(path) and (path == NATIVE_ROOT or path.startswith(NATIVE_ROOT + os.sep))


def _scope():
    names = (
        "ROOT",
        "SOURCE",
        "LITERAL",
        "TEST",
        "FILE",
        "MODULE",
        "SOFTWARE_RELEASE",
        "OWNED",
        "FORBIDDEN_MODULES",
        "NATIVE_ROOT",
        "snapshot",
        "is_forbidden_frame",
    )
    return dict(vars(reuse), **{name: globals()[name] for name in names}, __file__=__file__)


def _integration_policy(select, seconds):
    if type(seconds) is not int or seconds not in (480, INTEGRATION_SECONDS):
        raise ValueError(
            "Explicit ordinary480 or scoped integration1800 software envelope required"
        )
    if seconds != 480 and select not in INTEGRATION_SELECTIONS:
        raise ValueError("Long integration envelope permits exactly one named blocked pilot")
    return seconds


def prepare(output, select, *, integration_seconds=480):
    seconds = _integration_policy(select, integration_seconds)
    value = FunctionType(reuse.prepare.__code__, _scope())(output, select)
    if seconds != 480:
        # This is fresh preparation, before any execution/release receipt.
        # Preserve the inherited default inputs; atomically finish the explicit
        # software-only resource specialization without touching the snapshot.
        inputs = json.loads((output / "inputs.json").read_text())
        snapshot.write_json(output / "focused-default-inputs.json", inputs)
        inputs.update(
            wall_seconds=seconds,
            software_integration_envelope=dict(
                seconds=seconds,
                default_seconds=480,
                single_named_pilot=select,
                native_bodies_operators_RNG_reference_and_science_held=True,
                ordinary_software_and_scientific_limits_unchanged=True,
            ),
        )
        pending = output / "integration-inputs.json.pending"
        snapshot.write_json(pending, inputs)
        os.replace(pending, output / "inputs.json")
    return value


def child(output, select):
    inputs = json.loads((output / "inputs.json").read_text())
    if inputs.get("software_release_requested") is not True:
        raise ValueError("Explicit native-blocked release required")
    if inputs.get("selection") != select:
        raise ValueError("Exact prepared item selection required")
    seconds = _integration_policy(select, inputs.get("wall_seconds"))
    if seconds != 480:
        policy = inputs.get("software_integration_envelope", {})
        if (
            policy.get("seconds") != seconds
            or policy.get("single_named_pilot") != select
            or policy.get("native_bodies_operators_RNG_reference_and_science_held") is not True
        ):
            raise ValueError("Explicit blocked integration preparation required")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    path = ROOT / SOURCE
    if inputs["owned_files"][SOURCE] != manifest["files"][SOURCE]["sha256"]:
        raise ValueError("Selected exact source changed")
    definitions = {}
    for name in (
        "cells.processes.betse_native_init_retained_world",
        "cells.processes.betse_native_parameter_seed_init_transition",
        "cells.processes.betse_native_init_dynamics_prelude",
    ):
        relative = "src/" + name.replace(".", "/") + ".py"
        module = importlib.import_module(name)
        if (
            Path(module.__file__).resolve() != ROOT / relative
            or snapshot.digest(ROOT / relative) != manifest["files"][relative]["sha256"]
        ):
            raise ValueError("Frozen metadata definitions required")
        definitions[name] = dict(path=relative, sha256=manifest["files"][relative]["sha256"])
    snapshot.write_json(
        output / "INIT-definition-imports.json",
        dict(
            source=SOURCE,
            sha256=snapshot.digest(path),
            metadata_producers=definitions,
            definitions_only=True,
            source_native_or_scientific_credit=0,
        ),
    )
    namespace = _scope()
    try:
        return FunctionType(reuse.child.__code__, namespace)(output, select)
    finally:
        global _RAW_FAILURES
        _RAW_FAILURES = namespace.get("_RAW_FAILURES", ())


def main():
    return FunctionType(reuse.main.__code__, dict(_scope(), child=child, prepare=prepare))()


if __name__ == "__main__":
    raise SystemExit(main())
