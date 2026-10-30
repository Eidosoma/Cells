# ruff: noqa: E501
"""Prepare an unapplied typed-input transport patch; no scientific imports."""

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
OUT = Path("/tmp/cells-worker-01-calcium-raw-input-repair-20261030-01")
TEST = "tests/unit/test_betse_normal_calcium_join.py"
NATIVE = "validation/betse/betse_normal_calcium_join_native.py"


def main():
    OUT.mkdir(exist_ok=False)
    originals = {name: (ROOT / name).read_text() for name in (TEST, NATIVE)}
    test = originals[TEST]
    needle = '    (folder / "inputs.json").write_text(json.dumps(inputs, indent=2, allow_nan=False) + "\\n")'
    assert test.count(needle) == 1
    replacement = """    payload = inputs
    if inputs.get("helper_probe"):
        # Existing raw archive codec transports IEEE-754 values without JSON
        # numeric NaN tokens. Keep actual nonfinite bits in typed NPZ arrays.
        typed = dict(inputs)
        for key in ("membrane_mM", "bath_mM", "voltage_V", "block"):
            typed[key] = np.asarray(inputs[key], np.float64)
        native.write_archive(folder / "raw-inputs", typed)
        payload = dict(kind="cells.typed_native_capture_inputs@1", archive="raw-inputs")
    (folder / "inputs.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\\n")"""
    test = test.replace(needle, replacement)
    raw_test = ast.parse((ROOT / "tests/unit/test_betse_fast_solver.py").read_text())
    decoder = next(
        n for n in raw_test.body if isinstance(n, ast.FunctionDef) and n.name == "archive_read"
    )
    decoder.name = "read_raw_capture_inputs"
    native = originals[NATIVE].replace("import subprocess\n", "import subprocess\n")
    assert "import struct\n" not in native
    native = native.replace("import sys\n", "import struct\nimport sys\n")
    needle = "\ndef main():\n"
    assert native.count(needle) == 1
    native = native.replace(needle, "\n\n" + ast.unparse(decoder) + "\n\n" + needle)
    needle = "    payload = json.loads(args.inputs.read_text())"
    assert native.count(needle) == 1
    native = native.replace(
        needle,
        needle
        + """
    if payload.get("kind") == "cells.typed_native_capture_inputs@1":
        if set(payload) != {"kind", "archive"} or payload["archive"] != "raw-inputs":
            raise ValueError("Require the declared local typed input archive")
        payload = read_raw_capture_inputs(args.inputs.parent / "raw-inputs")""",
    )
    for name, text in ((TEST, test), (NATIVE, native)):
        path = OUT / "candidate" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    meta = {
        "kind": "cells.calcium_raw_input_unapplied_patch_preparation@1",
        "status": "UNAPPLIED_STATIC_CANDIDATE",
        "authority": "Chief request: typed NPZ plus finite JSON, no protected Ca edits while ER runs",
        "original_sha256": {
            name: hashlib.sha256(text.encode()).hexdigest() for name, text in originals.items()
        },
        "protected_source_files_modified": False,
        "new_numerical_runs": 0,
        "scientific_imports": 0,
        "scope": "Only raw helper input transport uses existing bit-preserving archive. No NaN sanitizing, nonstandard numeric JSON, equation, fixture, domain or tolerance changes.",
        "known_failure_provenance": "Chief: calcium numerical02 has23pass/1fail; nan_membrane stopped in JSON writer before native call. Independent retention review pending; no complete-panel pass claim.",
    }
    (OUT / "proposal.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    print(str(OUT))


if __name__ == "__main__":
    main()
