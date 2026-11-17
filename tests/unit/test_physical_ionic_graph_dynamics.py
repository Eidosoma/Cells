"""NUM-008 preflight uses shorter synthetic preparations, never full-panel solves."""

import ast
from dataclasses import replace

import pytest

from scripts import qualify_physical_ionic_graph_reference as qualify
from tests import physical_ionic_graph_numerical_data as data
from tests import reference_physical_ionic_graph_dynamics as ref


@pytest.fixture(scope="module")
def panel():
    return data.load_panel()


@pytest.fixture(scope="module")
def small(panel):
    base = panel[1][6]
    bindings = list(base.graph.channels)
    bindings[0] = replace(
        bindings[0],
        channel=replace(bindings[0].channel, initial_gate=data.spec.channel.Gate(0.3, 0.7)),
    )
    graph = replace(base.graph, channels=tuple(bindings))
    enabled = data.spec.enabled(graph)
    off = replace(
        enabled,
        leak=tuple((0.0,) * base.layout.s for _ in graph.cells),
        pump=(0.0,) * base.layout.n,
        channel=(0.0,) * base.layout.k,
        junction=(0.0,) * base.layout.e,
    )
    return data.Case(
        "short_synthetic_preflight",
        graph,
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
    for setting in plan["references"]:
        name = setting["id"]
        arrays, stats[name] = ref.integrate_reference(small, setting)
        records[name] = arrays | {
            "sample_times_s": samples,
            "sample_state": ref.sample_record(small, arrays, setting["method"], samples),
        }
    for dt in plan["candidate"]["steps_s"]:
        name = f"rk4_{dt:g}"
        arrays, stats[name] = ref.integrate_candidate(small, dt)
        assert stats[name]["status"] == "complete"
        records[name] = arrays | {
            "sample_times_s": samples,
            "sample_state": ref.sample_record(small, arrays, "RK4", samples),
        }
    return records, stats


def test_artifacts_refuse_overwrite_and_enforce_quota(tmp_path):
    path = tmp_path / "bounded"
    artifacts = qualify.Artifacts(path, 65540)
    artifacts.write("one", b"1234")
    with pytest.raises(FileExistsError):
        qualify.Artifacts(path, 65540)
    with pytest.raises(ref.ResourceLimit):
        artifacts.write("two", b"5")
    with pytest.raises(FileExistsError):
        artifacts.write("one", b"", closing=True)


def test_auditor_is_solver_free_and_capsule_is_complete():
    for name in (
        "scripts/audit_physical_ionic_graph_reference.py",
        "tests/physical_ionic_graph_numerical_checks.py",
        "tests/physical_ionic_graph_numerical_data.py",
    ):
        tree = ast.parse((data.ROOT / name).read_text())
        imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert not any(
            "dynamics" in n or "scipy" in n or n.startswith("cells") or "jax" in n for n in imports
        )
    assert len(qualify.SOURCE_FILES) == len(set(qualify.SOURCE_FILES))
    assert all((data.ROOT / n).is_file() for n in qualify.SOURCE_FILES)
