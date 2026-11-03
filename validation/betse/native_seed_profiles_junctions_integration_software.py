"""Immutable native-blocked same-phase profiles/junction integration controls."""

import importlib
import json
import os
from pathlib import Path
from types import FunctionType

from validation.betse import native_seed_core_integration_software as previous

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_seed_junctions.py"
LITERAL = "src/cells/processes/betse_native_seed_junctions_source.py"
TEST = "tests/unit/test_native_seed_profiles_junctions_integration.py"
FILE = "validation/betse/native_seed_profiles_junctions_integration_software.py"
MODULE = "validation.betse.native_seed_profiles_junctions_integration_software"
SOFTWARE_RELEASE = "BETSE_NATIVE_SEED_PROFILES_JUNCTIONS_INTEGRATION_SOFTWARE_RELEASED"
OWNED = (
    "src/cells/processes/betse_native_seed_init_core.py",
    "src/cells/processes/betse_native_seed_init_profiles.py",
    SOURCE,
    "src/cells/processes/betse_native_world_phase_construction.py",
    "src/cells/processes/betse_native_phase_dyna.py",
    "src/cells/processes/betse_native_phase_assembly.py",
    "src/cells/processes/betse_native_seed_world_prefix.py",
    TEST,
    FILE,
)
FORBIDDEN_MODULES = (
    previous.FORBIDDEN_MODULES - {"cells.processes.betse_native_phase_dyna"}
) | frozenset(
    (
        "cells.processes.betse_native_seed_init_profiles_source",
        "cells.processes.betse_native_seed_junctions_source",
        "cells.processes.betse_native_post_world_operators_source",
        "cells.processes.betse_post_cut_mesh_contact_source",
    )
)
NATIVE_ROOT, snapshot = previous.NATIVE_ROOT, previous.snapshot
base = previous.base
_RAW_FAILURES = ()


def is_forbidden_frame(frame):
    if frame.f_globals.get("__name__") in FORBIDDEN_MODULES:
        return True
    path = os.path.normpath(frame.f_code.co_filename)
    return os.path.isabs(path) and (path == NATIVE_ROOT or path.startswith(NATIVE_ROOT + os.sep))


def _scope():
    return dict(
        vars(previous),
        **{
            name: globals()[name]
            for name in (
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
        },
        __file__=__file__,
    )


def prepare(output, select):
    return FunctionType(previous.prepare.__code__, _scope())(output, select)


def child(output, select):
    inputs = json.loads((output / "inputs.json").read_text())
    if inputs.get("software_release_requested") is not True:
        raise ValueError("Separate blocked-software release required")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    for path in OWNED:
        if inputs["owned_files"][path] != manifest["files"][path]["sha256"]:
            raise ValueError("Selected expected producer changed")
    producers = {}
    for name in (
        "cells.processes.betse_native_phase_dyna",
        "cells.processes.betse_native_seed_init_profiles",
        "cells.processes.betse_native_seed_junctions",
    ):
        module = importlib.import_module(name)
        path = "src/" + name.replace(".", "/") + ".py"
        if Path(module.__file__).resolve() != ROOT / path:
            raise ValueError("Frozen definitions required")
        producers[name] = dict(path=path, sha256=manifest["files"][path]["sha256"])
    snapshot.write_json(
        output / "post-core-definition-imports.json",
        dict(
            modules=producers,
            definitions_only=True,
            source_native_or_scientific_credit=0,
        ),
    )
    scope = _scope()
    try:
        return FunctionType(previous.child.__code__, scope)(output, select)
    finally:
        global _RAW_FAILURES
        _RAW_FAILURES = scope.get("_RAW_FAILURES", ())


def main():
    scope = dict(_scope(), child=child, prepare=prepare)
    return FunctionType(previous.main.__code__, scope)()


if __name__ == "__main__":
    raise SystemExit(main())
