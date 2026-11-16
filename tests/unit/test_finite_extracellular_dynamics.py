"""NUM-009 engineering preflights; no undeclared full-panel trajectories."""

import ast
import json
import subprocess
from dataclasses import replace

import numpy as np
import pytest

from scripts import qualify_finite_extracellular_reference as qualify
from tests import finite_extracellular_numerical_checks as check
from tests import finite_extracellular_numerical_data as data
from tests import reference_finite_extracellular_dynamics as ref


@pytest.fixture(scope="module")
def panel():
    return data.load_panel()


@pytest.fixture(scope="module")
def small(panel):
    base = next(c for c in panel[1] if c.id == "star_mono")
    channels = list(base.world.channels)
    channels[0] = replace(channels[0], initial_gate=data.spec.channel.Gate(0.3, 0.7))
    world = replace(base.world, channels=tuple(channels))
    enabled = data.spec.graph.enabled(world)
    off = replace(
        enabled,
        leak=((0.0,) * base.layout.s,) * base.layout.n,
        pump=(0.0,) * base.layout.n,
        channel=(0.0,) * base.layout.k,
        junction=(0.0,) * base.layout.e,
    )
    return data.Case(
        "short_synthetic_preflight",
        world,
        0.012,
        (
            data.Control(0, enabled),
            data.Control(0.0023, replace(enabled, junction=(0.0, 1.0))),
            data.Control(0.0024, replace(enabled, channel=(1.0, 0.0), pump=(0.0, 1.0, 1.0))),
            data.Control(0.0051, off),
            data.Control(0.0089, enabled),
            data.Control(0.012, off),
        ),
    )


@pytest.fixture(scope="module")
def small_records(panel, small):
    plan = panel[0]
    samples = ref.comparison_grid(small, plan["candidate"])
    records, stats = {}, {}
    attempts = [(s["id"], s) for s in plan["references"]] + [
        (f"rk4_{dt:g}", dt) for dt in plan["candidate"]["steps_s"]
    ]
    for name, setting in attempts:
        if isinstance(setting, dict):
            arrays, stats[name] = ref.integrate_reference(small, setting)
            kind = setting["method"]
        else:
            arrays, stats[name] = ref.integrate_candidate(small, setting)
            kind = "RK4"
        complete = stats[name]["status"] == "complete"
        records[name] = arrays | {
            "sample_times_s": samples if complete else np.empty(0),
            "sample_state": ref.sample_record(small, arrays, kind, samples)
            if complete
            else np.empty((0, small.size)),
        }
    return records, stats


@pytest.mark.parametrize(
    "field,bad", [("n", 0), ("n", True), ("s", 0), ("s", 2.5), ("k", -1), ("e", -1), ("e", False)]
)
def test_layout_rejects_bad_extents(field, bad):
    values = {"n": 1, "s": 3, "k": 0, "e": 0}
    values[field] = bad
    with pytest.raises(ValueError):
        data.Layout(**values)


@pytest.mark.parametrize("small_cubic", [0, 1e-17, -1e-17, 1e-25, -1e-25])
@pytest.mark.parametrize("scale", [1.0, 1e-13, 1e-100])
def test_nearly_quadratic_extrema_keep_finite_stationary_root(small_cubic, scale):
    lo, hi, count = check.polynomial_range(np.array([0, 1, -1, small_cubic]) * scale)
    assert lo == pytest.approx(0, abs=1e-15 * scale)
    assert hi == pytest.approx(0.25 * scale, rel=1e-14, abs=0)
    assert count >= 3


def test_json_duplicate_keys_are_refused(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"a":1,"a":2}')
    with pytest.raises(ValueError):
        data.spec.ion.load_json(path)


def test_artifacts_refuse_overwrite(tmp_path):
    with pytest.raises(FileExistsError):
        qualify.Artifacts(tmp_path, 100000)


def test_auditor_imports_no_solver():
    result = subprocess.run(
        [
            str(data.ROOT / ".venv/bin/python"),
            "-c",
            "import sys; from scripts import audit_finite_extracellular_reference; "
            "assert 'scipy.integrate' not in sys.modules; assert 'cells' not in sys.modules",
        ],
        cwd=data.ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    for name in (
        "tests/finite_extracellular_numerical_checks.py",
        "tests/finite_extracellular_numerical_data.py",
        "scripts/audit_finite_extracellular_reference.py",
    ):
        tree = ast.parse((data.ROOT / name).read_text())
        imported = [
            node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        ]
        assert not any(n.startswith(("cells", "jax", "scipy.integrate")) for n in imported)


def test_frozen_plan_changes_are_refused(monkeypatch, tmp_path):
    plan = json.loads(data.PANEL.read_text())
    plan["accounting_limits"]["countercharge_C"] = 1e-10
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    monkeypatch.setattr(data, "PANEL", path)
    with pytest.raises(ValueError, match="Frozen NUM-009"):
        data.load_panel()
