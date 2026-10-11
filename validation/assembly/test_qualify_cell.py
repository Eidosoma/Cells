"""Qualification launch budgets and CPU reuse retain their scientific guards."""

import json
import shutil
import sys
import xml.etree.ElementTree as ET

import pytest

from validation.assembly import qualify_cell as runner


def gated_definition(tmp_path, *, trace_mib=1280, event_time=None):
    definition = json.loads((runner.ROOT / "configs/gated_calcium_cluster.json").read_text())
    definition["execution"]["max_trace_bytes"] = trace_mib * 1024**2
    if event_time is not None:
        definition["experiment"]["calcium_channel_controls"][0]["schedule"].append(
            {"time": event_time, "availability": 0.5}
        )
    path = tmp_path / "gated.json"
    path.write_text(json.dumps(definition))
    protocol = json.loads((runner.ROOT / "validation/chemistry/gated_protocol.json").read_text())
    return path, protocol


def test_refinement_preflight_rejects_original_finest_trace_limit(tmp_path):
    from cells.core.runner import timeline
    from cells.core.specs import ConfigError, load_spec

    path, protocol = gated_definition(tmp_path, trace_mib=1024)
    # The old default-only preflight passed; the registered finest grid must fail.
    assert len(timeline(load_spec(path))) == 1601
    before = path.read_bytes()
    with pytest.raises(ConfigError, match="dt=6.25e-06 s: Estimated trace working storage"):
        runner.chemistry_grid_preflight(path, protocol)
    assert path.read_bytes() == before


@pytest.mark.parametrize("event_time", [None, 0.000413])
def test_refinement_preflight_covers_actual_grids_without_changing_inputs(tmp_path, event_time):
    path, protocol = gated_definition(tmp_path, event_time=event_time)
    before = path.read_bytes()
    protocol_before = json.dumps(protocol)
    record = runner.chemistry_grid_preflight(path, protocol)
    assert record["status"] == "passed"
    assert record["definition_sha256"] == runner.digest(path)
    expected = {0.000025: 800, 0.0000125: 1600, 0.00000625: 3200}
    assert {r["dt_s"]: r["steps"] for r in record["grids"]} == {
        dt: steps + (event_time is not None) for dt, steps in expected.items()
    }
    assert all(r["trace_working_bytes"] <= r["max_trace_bytes"] for r in record["grids"])
    assert max(r["trace_working_bytes"] for r in record["grids"]) > 1024**3
    assert path.read_bytes() == before and json.dumps(protocol) == protocol_before


def test_refinement_preflight_preserves_step_domain_rejection(tmp_path):
    from cells.core.specs import ConfigError

    path, protocol = gated_definition(tmp_path)
    protocol["steps_s"] = [0.001]
    with pytest.raises(ConfigError, match="dt=0.001 s:"):
        runner.chemistry_grid_preflight(path, protocol)


@pytest.mark.parametrize("steps", [[], [0], [-1], [True], [float("nan")]])
def test_refinement_preflight_requires_a_valid_declared_ladder(tmp_path, steps):
    path, protocol = gated_definition(tmp_path)
    protocol["steps_s"] = steps
    with pytest.raises(ValueError, match="positive finite refinement"):
        runner.chemistry_grid_preflight(path, protocol)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


@pytest.fixture(params=("plasma", "gated", "ip3"))
def parent(tmp_path, request):
    root = tmp_path / "parent"
    source = root / "source"
    (source / "src/cells").mkdir(parents=True)
    (source / "src/cells/solver.py").write_text("# frozen physical implementation\n")
    (source / runner.DRIVER).parent.mkdir(parents=True)
    (source / runner.DRIVER).write_text("# previous runner\n")
    modules = ["plasma_calcium", "spatial_calcium", "er_calcium", "compartment_reactions"]
    groups = ["plasma", "calcium", "er", "chemistry"]
    if request.param in ("gated", "ip3"):
        modules.insert(0, "gated_calcium")
        groups.insert(0, "cav")
    if request.param == "ip3":
        modules.insert(0, "ip3_calcium")
        groups.insert(0, "ip3")
    nodes = ["tests/unit/test_plasma_calcium.py::test_transport"] + [
        f"tests/unit/test_{name}.py::test_cpu_gpu_agreement" for name in modules
    ]
    testsuites = ET.Element("testsuites")
    suite = ET.SubElement(
        testsuites,
        "testsuite",
        tests=str(len(nodes)),
        errors="0",
        failures="0",
        skipped=str(len(modules)),
    )
    for i, node in enumerate(nodes):
        path, name = node.split("::")
        case = ET.SubElement(suite, "testcase", classname=path[:-3].replace("/", "."), name=name)
        if i:
            ET.SubElement(case, "skipped")
    ET.ElementTree(testsuites).write(root / "cpu.xml")
    for backend in ("cpu", "gpu"):
        (root / f"{backend}.collection.log").write_text(
            "\n".join(nodes) + f"\n{len(nodes)} tests collected\n"
        )
        write_json(root / f"{backend}.runtime.json", {"python": "fixed-test-runtime"})
    (root / "cpu.stdout.log").write_text(f"1 passed, {len(modules)} skipped\n")
    (root / "cpu.stderr.log").write_text("")
    protocol = {"resources": {"max_wall_seconds": 4500}, "tolerances": {"energy_atol_pJ": 1e-9}}
    write_json(root / "chemistry-protocol.json", protocol)
    write_json(
        root / "registration.json",
        {
            "chemistry": True,
            "chemistry_case": request.param,
            "max_wall_seconds": 4500,
            "sources_sha256": runner.files(source),
            "chemistry_protocol": protocol,
            "chemistry_test_counts": {"cpu": len(nodes), "gpu": len(nodes)},
        },
    )
    write_json(
        root / "failure.json",
        {
            "status": "failed",
            "traceback": "subprocess.TimeoutExpired: GPU timeout",
            "elapsed_seconds": 4501,
        },
    )
    for group in groups:
        directory = root / (group + "-evidence/cpu")
        write_json(directory / "baseline.json", {"status": "passed"})
        (directory / "baseline.npz").write_bytes(b"test fixture for copied-array checksum")
        if group in ("ip3", "cav", "plasma", "calcium"):
            write_json(directory / "assembly-baseline.json", {"status": "passed"})
            (directory / "assembly-baseline.npz").write_bytes(b"test fixture for coupled arrays")
    return root


@pytest.mark.parametrize(
    "mutation",
    [
        "source",
        "hidden_failure",
        "incomplete_xml",
        "unexpected_deferral",
        "gpu_test_order",
        "stderr",
        "non_timeout",
        "early_timeout",
        "missing_arrays",
        "changed_protocol",
        "missing_new_arrays",
        "missing_assembly_arrays",
        "missing_deferral",
        "wrong_family",
    ],
)
def test_reject_unusable_cpu_phase(parent, mutation):
    if mutation == "source":
        (parent / "source/src/cells/solver.py").write_text("changed physical equation")
    elif mutation in (
        "hidden_failure",
        "incomplete_xml",
        "unexpected_deferral",
        "missing_deferral",
    ):
        tree = ET.parse(parent / "cpu.xml")
        suite = tree.getroot().find("testsuite")
        if mutation == "hidden_failure":
            ET.SubElement(suite[0], "failure")  # Summary counts still say zero failures.
        elif mutation == "incomplete_xml":
            suite.remove(suite[0])
        elif mutation == "unexpected_deferral":
            ET.SubElement(suite[0], "skipped")
        else:
            suite[1].remove(suite[1].find("skipped"))
        tree.write(parent / "cpu.xml")
    elif mutation == "gpu_test_order":
        nodes = runner.collection_nodes(parent / "gpu.collection.log")
        (parent / "gpu.collection.log").write_text("\n".join(reversed(nodes)))
    elif mutation == "stderr":
        (parent / "cpu.stderr.log").write_text("unexpected numerical warning")
    elif mutation in ("non_timeout", "early_timeout"):
        failure = json.loads((parent / "failure.json").read_text())
        failure.update(
            {"traceback": "NumericalError"}
            if mutation == "non_timeout"
            else {"elapsed_seconds": 10}
        )
        write_json(parent / "failure.json", failure)
    elif mutation == "missing_arrays":
        (parent / "plasma-evidence/cpu/baseline.npz").unlink()
    elif mutation == "changed_protocol":
        write_json(parent / "chemistry-protocol.json", {"tolerances": "relaxed"})
    elif mutation in ("missing_new_arrays", "missing_assembly_arrays"):
        case = json.loads((parent / "registration.json").read_text())["chemistry_case"]
        group = {"plasma": "plasma", "gated": "cav", "ip3": "ip3"}[case]
        name = "baseline.npz" if mutation == "missing_new_arrays" else "assembly-baseline.npz"
        (parent / (group + "-evidence/cpu") / name).unlink()
    elif mutation == "wrong_family":
        record = json.loads((parent / "registration.json").read_text())
        record["chemistry_case"] = "plasma" if record["chemistry_case"] != "plasma" else "ip3"
        write_json(parent / "registration.json", record)
    with pytest.raises(ValueError):
        runner.cpu_baseline_binding(parent)


def test_cpu_reuse_accepts_only_runner_changes(parent, tmp_path):
    binding = runner.cpu_baseline_binding(parent)
    output = tmp_path / "continuation"
    shutil.copytree(parent, output)
    (output / "source" / runner.DRIVER).write_text("# new continuation driver\n")
    runner.verify_cpu_baseline(output, binding)
    expected = {"plasma": (5, 4, 16), "gated": (6, 5, 20), "ip3": (7, 6, 24)}[
        binding["chemistry_case"]
    ]
    assert int(binding["cpu_suite"]["tests"]) == expected[0]
    assert int(binding["cpu_suite"]["skipped"]) == expected[1]
    assert len(binding["cpu_files_sha256"]) == expected[2]


@pytest.mark.parametrize(
    "mutation", ["physics", "copied_arrays", "test_order", "parent_arrays", "protocol"]
)
def test_bound_reuse_rejects_changed_source_artifacts_or_parent(parent, tmp_path, mutation):
    binding = runner.cpu_baseline_binding(parent)
    output = tmp_path / "continuation"
    shutil.copytree(parent, output)
    targets = {
        "physics": output / "source/src/cells/solver.py",
        "copied_arrays": output / "plasma-evidence/cpu/baseline.npz",
        "test_order": output / "gpu.collection.log",
        "parent_arrays": parent / "plasma-evidence/cpu/baseline.npz",
        "protocol": output / "chemistry-protocol.json",
    }
    if mutation == "protocol":
        write_json(targets[mutation], {"tolerances": "changed"})
    else:
        targets[mutation].write_bytes(b"changed")
    with pytest.raises(ValueError):
        runner.verify_cpu_baseline(output, binding)


def test_retry_wall_budget_keeps_parent_protocol_unchanged(parent):
    binding = runner.cpu_baseline_binding(parent)
    path = parent / "chemistry-protocol.json"
    before = path.read_bytes()
    protocol = json.loads(before)
    assert runner.chemistry_wall_seconds(protocol, binding, None) == 4500
    assert runner.chemistry_wall_seconds(protocol, binding, 14400) == 14400
    assert runner.chemistry_wall_seconds(protocol, None, None) == 4500
    assert path.read_bytes() == before and protocol == json.loads(before)


@pytest.mark.parametrize("seconds", [0, -1, True, 4499, 5000.5, float("nan")])
def test_invalid_retry_wall_allowance_rejected(seconds):
    protocol = {"resources": {"max_wall_seconds": 4500}}
    with pytest.raises(ValueError, match="GPU retry wall allowance"):
        runner.chemistry_wall_seconds(protocol, {"path": "test-parent"}, seconds)


def test_retry_override_requires_cpu_reuse(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="requires CPU reuse"):
        runner.chemistry_wall_seconds({"resources": {"max_wall_seconds": 4500}}, None, 14400)
    output = tmp_path / "must-not-launch"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "qualify_cell",
            "launch",
            str(output),
            "--chemistry",
            "--chemistry-case",
            "ip3",
            "--gpu-retry-wall-seconds",
            "14400",
        ],
    )
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == 2 and not output.exists()


def test_cli_rejects_cpu_parent_from_another_panel(parent, tmp_path, monkeypatch):
    case = json.loads((parent / "registration.json").read_text())["chemistry_case"]
    wrong = "ip3" if case != "ip3" else "plasma"
    output = tmp_path / "must-not-launch"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "qualify_cell",
            "launch",
            str(output),
            "--chemistry",
            "--chemistry-case",
            wrong,
            "--cpu-baseline",
            str(parent),
        ],
    )
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == 2 and not output.exists()
