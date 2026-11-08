"""Reuse the guarded immutable reference runner for synthetic import controls."""

import argparse
import os
import resource
from pathlib import Path
from types import FunctionType

from validation.betse import native_init_terminal_reference_compare_software as init_reader
from validation.betse import native_init_terminal_reference_software as base
from validation.betse import native_sim_reference_compare_software as sim_reader

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "validation/betse/native_reference_imports.py"
TEST = "tests/unit/test_native_reference_imports.py"
FILE = "validation/betse/native_reference_imports_software.py"
MODULE = "validation.betse.native_reference_imports_software"
RELEASE = "CELLS_ORIGINAL_IMPORT_LIFECYCLE_BLOCKED_SOFTWARE"
OWNED = (
    SOURCE,
    TEST,
    FILE,
    "validation/betse/native_init_terminal_reference.py",
    "validation/betse/native_sim_reference.py",
    "validation/betse/native_sim_reference_source.py",
    "validation/betse/native_init_terminal_reference_compare.py",
    "validation/betse/native_sim_reference_compare.py",
)
POLICY = dict(base.POLICY, cpu=6)
blocked = base.blocked


def _group(select):
    if "::" not in select:
        return None, select
    group, selection = select.split("::", 1)
    choices = {"init_reader": init_reader, "sim_reader": sim_reader}
    if group not in choices or not selection:
        raise ValueError("Exact declared blocked-reader group required")
    return choices[group], selection


def _namespace(select="reference_import"):
    target, _ = _group(select)
    selected_source, selected_test = (
        (SOURCE, TEST) if target is None else (target.SOURCE, target.TEST)
    )
    selected_owned = OWNED if target is None else (FILE, selected_source, selected_test, SOURCE)
    namespace = dict(
        vars(base),
        **{
            name: globals()[name]
            for name in (
                "ROOT",
                "SOURCE",
                "TEST",
                "FILE",
                "MODULE",
                "OWNED",
                "RELEASE",
                "POLICY",
            )
        },
        __file__=__file__,
    )
    namespace.update(SOURCE=selected_source, TEST=selected_test, OWNED=selected_owned)
    return namespace


def prepare(output, select):
    namespace = _namespace(select)
    target, _ = _group(select)
    if target is sim_reader:
        # This existing reader preparation includes the exact producer files
        # read by its forensic fixtures, including its dynamic REF_PRODUCERS.
        FunctionType(target.prepare.__code__, dict(vars(target), **namespace))(output, select)
    else:
        FunctionType(base.prepare.__code__, namespace)(output, select)
    # Bind the genuine external compiler tree before tests. No import of that
    # library, original package, constructor, RNG or operator happens here.
    from validation.betse import native_reference_imports as loader

    files = loader._tree()
    base.snapshot.write_json(
        output / "compiler-inputs.json",
        dict(
            policy=loader.specification(),
            files=files,
            actual_BETSE_or_owner_execution=False,
        ),
    )


def child(output, select):
    from validation.betse import native_reference_imports as loader

    inputs = base.json.loads((output / "compiler-inputs.json").read_text())
    if inputs != dict(
        policy=loader.specification(), files=loader._tree(), actual_BETSE_or_owner_execution=False
    ):
        raise ValueError("Pinned external compiler inputs drifted")
    target, selection = _group(select)
    namespace = _namespace(select)
    if target is None:
        return FunctionType(base.child.__code__, namespace)(output, selection)
    frozen = base.json.loads((output / "inputs.json").read_text())
    if frozen["selection"] != select:
        raise ValueError("Exact immutable group/selection binding required")
    os.environ[target.RELEASE] = "1"
    return FunctionType(target.child.__code__, dict(vars(target), **namespace))(output, selection)


def software(output, select):
    return FunctionType(base.software.__code__, _namespace(select))(output, select)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepare", "software", "child"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--select", default="reference_import")
    parser.add_argument("--software-cpu", type=int, choices=(6,), default=6)
    args = parser.parse_args()
    selected = [
        (name, getattr(args, name))
        for name in ("prepare", "software", "child")
        if getattr(args, name) is not None
    ]
    if len(selected) != 1:
        parser.error("Exactly one guarded runner action required")
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    name, output = selected[0]
    resource.setrlimit(resource.RLIMIT_AS, (2**30 if name == "child" else 512 * 2**20, 2**30))
    return globals()[name](output, args.select)


if __name__ == "__main__":
    raise SystemExit(main())
