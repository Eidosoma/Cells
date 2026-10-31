"""Repository imports and execution refusal with all scientific imports blocked."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("mode", ["numpy", "jax_eager", "jax_jit"])
def test_metadata_plan_and_release_refusal_need_no_scientific_imports(mode, tmp_path):
    program = r"""
import importlib.abc, json, sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path[:0] = [str(root / "src"), str(root)]
attempts = []
class DenyScience(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"numpy", "scipy", "jax", "jaxlib"}:
            attempts.append(fullname)
            raise AssertionError("Scientific import attempted: " + fullname)
sys.meta_path.insert(0, DenyScience())
from cells.processes import charged_surface_backend as backend
from cells.processes import charged_surface_backend_gate as gate
from cells.processes import charged_surface_backend_plan as planning
from cells.processes import charged_surface_work as scalar
from validation import charged_surface_backend_declarations as cases
scalar._pins()
plan = planning.make_plan(cases.cohort(sys.argv[2]))
assert len(plan.worlds) == 4
failures = []
for release in (None, sys.argv[3]):
    try:
        backend.Runner(plan, release_path=release)
    except gate.HeldDependencyError as error:
        failures.append(str(error))
    else:
        raise AssertionError("Unreleased repository execution was admitted")
assert "Scalar acceptance" in failures[0]
assert "frozen source snapshot" in failures[1]
assert attempts == []
print(json.dumps({"mode": sys.argv[2], "refusals": failures,
                  "worlds_in_metadata": len(plan.worlds), "scientific_import_attempts": attempts}))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            "-c",
            program,
            str(ROOT),
            mode,
            str(tmp_path / "unissued-release.json"),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    (tmp_path / "source-refusal-result.json").write_text(
        json.dumps(
            {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr},
            indent=2,
        )
        + "\n"
    )
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["scientific_import_attempts"] == []
    assert evidence["mode"] == mode
