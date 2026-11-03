"""Immutable native-blocked controls for INIT tissue participation, CPU6 only."""

import importlib
import json
import sys
from pathlib import Path
from types import FunctionType

from validation.betse import betse_native_init_retained_world_software as inherited
from validation.betse import betse_native_phase_tail_software as tail

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_init_tissue_dynamics.py"
LITERAL = "src/cells/processes/betse_native_init_tissue_dynamics_source.py"
TEST = "tests/unit/test_betse_native_init_tissue_dynamics.py"
FILE = "validation/betse/betse_native_init_tissue_dynamics_software.py"
MODULE = "validation.betse.betse_native_init_tissue_dynamics_software"
SOFTWARE_RELEASE = "BETSE_NATIVE_INIT_TISSUE_DYNAMICS_SOFTWARE_RELEASED"
OWNED = (SOURCE, LITERAL, TEST, FILE)
snapshot = inherited.snapshot
base, NATIVE_ROOT = inherited.base, inherited.NATIVE_ROOT
FORBIDDEN_MODULES = inherited.FORBIDDEN_MODULES | frozenset(
    (
        "cells.processes.betse_native_init_tissue_dynamics_source",
        "cells.processes.betse_native_seed_init_profiles_source",
        "cells.processes.betse_native_init_dynamics_completion_source",
        "cells.processes.betse_native_init_dynamics_prelude_source",
    )
)
_RAW_FAILURES = ()


def is_forbidden_frame(frame):
    name = frame.f_globals.get("__name__", "")
    return (
        name in FORBIDDEN_MODULES
        or (
            name == "cells.processes.betse_native_init_tissue_dynamics"
            and frame.f_code.co_name == "_bind_methods"
        )
        or (name == "random" and frame.f_code.co_name != "<module>")
        or inherited.is_forbidden_frame(frame)
    )


def _scope():
    result = inherited._scope()
    result.update(
        ROOT=ROOT,
        SOURCE=SOURCE,
        LITERAL=LITERAL,
        TEST=TEST,
        FILE=FILE,
        MODULE=MODULE,
        SOFTWARE_RELEASE=SOFTWARE_RELEASE,
        OWNED=OWNED,
        FORBIDDEN_MODULES=FORBIDDEN_MODULES,
        NATIVE_ROOT=NATIVE_ROOT,
        is_forbidden_frame=is_forbidden_frame,
        __file__=__file__,
    )
    return result


def prepare(output, select):
    return FunctionType(inherited.reuse.prepare.__code__, _scope())(output, select)


def _external_producers(inputs, *, loaded):
    declared = inputs.get("external_runtime_pins", {})
    observed = {}
    for name, filename, pin in tail.PILLOW_PINS:
        expected = dict(path=filename, sha256=pin)
        if declared.get(name) != expected or snapshot.digest(Path(filename)) != pin:
            raise ValueError("Exact existing Pillow input must be declared before freeze")
        if loaded:
            module = sys.modules.get(name)
            if module is None or Path(module.__file__).resolve() != Path(filename):
                raise ValueError("Actual loaded Pillow producer differs from prepared input")
            observed[name] = dict(expected, actual_loaded_path=str(Path(module.__file__).resolve()))
    return observed


def child(output, select):
    inputs = json.loads((output / "inputs.json").read_text())
    if inputs.get("software_release_requested") is not True:
        raise ValueError("Explicit native-blocked software release required")
    if inputs.get("selection") != select:
        raise ValueError("Exact frozen item-name selection required")
    _external_producers(inputs, loaded=False)
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    for name in OWNED:
        if (
            snapshot.digest(ROOT / name) != manifest["files"][name]["sha256"]
            or inputs["owned_files"][name] != manifest["files"][name]["sha256"]
        ):
            raise ValueError("Frozen owned tissue source changed")
    module = importlib.import_module("cells.processes.betse_native_init_tissue_dynamics")
    if Path(module.__file__).resolve() != ROOT / SOURCE:
        raise ValueError("Actual frozen source definitions required")
    snapshot.write_json(
        output / "tissue-source-plan.json",
        dict(
            plan=module.source_plan(),
            owned_files=inputs["owned_files"],
            snapshot_sha256=inputs["snapshot_sha256"],
            definitions_and_AST_metadata_only=True,
            actual_source_constructor_RNG_operator_reference_or_scientific_credit=0,
        ),
    )
    namespace = _scope()
    required_hooks = sys.getprofile(), sys.gettrace()
    try:
        result = FunctionType(inherited.reuse.child.__code__, namespace)(output, select)
        if sys.getprofile() is not required_hooks[0] or sys.gettrace() is not required_hooks[1]:
            raise ValueError("Exact inherited hooks required before post-run producer callbacks")
        snapshot.write_json(
            output / "tissue-loaded-external-producers.json",
            dict(
                expected=inputs["external_runtime_pins"],
                actual=_external_producers(inputs, loaded=True),
                actual_native_or_scientific_credit=0,
            ),
        )
        return result
    finally:
        global _RAW_FAILURES
        _RAW_FAILURES = namespace.get("_RAW_FAILURES", ())


def main():
    return FunctionType(
        inherited.reuse.main.__code__,
        dict(_scope(), prepare=prepare, child=child),
    )()


if __name__ == "__main__":
    raise SystemExit(main())
