"""Short adapter preflight. Synthetic traces are NOT executed BETSE evidence."""

import copy
import importlib
import sys
from decimal import Decimal, localcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ref = importlib.import_module("gate_reference")
job = importlib.import_module("gate_job")
c = ref.c


@pytest.fixture(scope="module")
def protocol():
    return c.read(ref.PROTOCOL)


@pytest.fixture(scope="module")
def synthetic(protocol):
    kinetics = {"target": [], "tau_s": []}
    one_step = []
    with localcontext() as context:
        context.prec = 70
        for v in protocol["voltages_V"]:
            target, tau = ref.kinetics_decimal(v)
            kinetics["target"].append(list(map(float, target)))
            kinetics["tau_s"].append(list(map(float, tau)))
            initial = tuple(Decimal(str(q)) for q in protocol["one_step_initial_gate"])
            one_step.append(
                list(map(float, ref.propagate(initial, target, tau, 1000, 1000, "rk4")))
            )
    native = {
        "kinetics": kinetics,
        "equilibrium_initial_gate": kinetics["target"],
        "trajectories": {},
    }
    cells = {
        "kinetics": {name: copy.deepcopy(kinetics) for name in ref.BACKENDS},
        "one_step": {name: copy.deepcopy(one_step) for name in ref.BACKENDS},
        "trajectories": {},
    }
    for result, method in ((native, "betse"), (cells, "rk4")):
        for case in protocol["cases"]:
            for dt in protocol["step_us"]:
                gate = ref.reference_trace(case, dt, method)
                times, volts = ref.grid(case)
                result["trajectories"][f"{case['id']}/{dt}"] = {
                    "time_us": times,
                    "voltage_V": volts,
                    "gate": gate,
                    "open_fraction": [m * h for m, h in gate],
                    "steps": times[-1] // dt,
                    "all_steps_valid": True,
                    "input_unchanged": True,
                }
    return native, cells


@pytest.fixture(scope="module")
def evaluated(protocol, synthetic):
    return ref.evaluate(protocol, *synthetic)


def test_complete_synthetic_comparator(evaluated):
    assert evaluated["status"] == "pass"
    assert evaluated["failed_comparisons"] == 0
    assert evaluated["isolated_gate_protocols"] == 6
    assert evaluated["trajectories_per_engine"] == 18
    assert evaluated["comparison_count"] > 10000
    assert not evaluated["independent_audit_complete"]
    assert not evaluated["coupled_cell_qualified"]
    assert len(evaluated["cross_engine_max_gate_differences"]) == 18
    assert evaluated["cross_engine_max_gate_differences"]["activation/1000"][0] > 0.01


def test_both_methods_refine_and_roundoff_is_not_order(evaluated):
    rows = evaluated["refinement"]
    assert any(r["status"] == "roundoff_limited" for r in rows)
    for name, lo, hi in (("betse", 0.4, 0.6), ("cells", 0.03, 0.1)):
        measured = [r for r in rows if f"/{name}/activation/0/" in r["id"]]
        assert len(measured) == 2
        assert all(r["status"] == "measured" and lo <= r["ratio"] <= hi for r in measured)


def test_no_discrete_engine_equality_claim(protocol):
    case = protocol["cases"][0]
    native = ref.reference_trace(case, 1000, "betse")
    cells = ref.reference_trace(case, 1000, "rk4")
    assert abs(native[5][0] - cells[5][0]) > 0.01


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", "wrong"),
        ("upstream_revision", "main"),
        ("fixture_temperature_K", 310.15),
        ("kinetic_law", "generic_gate"),
        ("step_us", [1000, 500]),
        ("voltage_domain_V", [-1, 1]),
        ("voltages_V", [0.061]),
        ("one_step_initial_gate", [True, 0.8]),
        ("cases", []),
        ("extra", "unregistered"),
    ],
)
def test_protocol_mutation_rejected(protocol, field, value):
    changed = copy.deepcopy(protocol)
    changed[field] = value
    with pytest.raises(ValueError, match="Unregistered"):
        ref.validate_protocol(changed)


@pytest.mark.parametrize("change", ["noninteger", "off_grid", "duplicate_id", "negative_gate"])
def test_nested_protocol_mutation_rejected(protocol, change):
    p = copy.deepcopy(protocol)
    if change == "noninteger":
        p["cases"][0]["segments"][0]["duration_us"] = 40000.5
    elif change == "off_grid":
        p["cases"][0]["segments"][0]["sample_every_us"] = 750
    elif change == "duplicate_id":
        p["cases"][1]["id"] = p["cases"][0]["id"]
    else:
        p["cases"][0]["initial_gate"][0] = -0.1
    with pytest.raises(ValueError):
        ref.validate_protocol(p)


def test_resource_and_clock_inventory(protocol):
    ref.validate_protocol(protocol)
    steps = sum(
        sum(s["duration_us"] for s in case["segments"]) // dt
        for case in protocol["cases"]
        for dt in protocol["step_us"]
    )
    assert steps == 49980
    assert max(ref.grid(case)[0][-1] for case in protocol["cases"]) == 4000000
    assert protocol["resources"]["total_timeout_seconds"] == 180


def test_event_state_not_reset_or_double_sampled(protocol):
    case = protocol["cases"][3]
    times, volts = ref.grid(case)
    assert len(times) == len(set(times)) == 61
    assert volts[times.index(10000)] == 0.02
    assert volts[times.index(20000)] == -0.08
    trace = ref.reference_trace(case, 1000, "continuous")
    prefix = copy.deepcopy(case)
    prefix["segments"] = prefix["segments"][:1]
    assert trace[times.index(10000)] == ref.reference_trace(prefix, 1000, "continuous")[-1]


def test_samples_do_not_redefine_integration(protocol):
    original = protocol["cases"][1]
    changed = copy.deepcopy(original)
    changed["segments"][0]["sample_every_us"] = 40000
    for method in ("continuous", "betse", "rk4"):
        dense = ref.reference_trace(original, 250, method)
        assert dense[::2] == ref.reference_trace(changed, 250, method)


@pytest.mark.parametrize(
    "change",
    [
        "truncated",
        "time",
        "voltage",
        "nan",
        "boolean",
        "range",
        "steps",
        "invalid_stage",
        "mutated_input",
        "reinitialized",
        "extra",
    ],
)
def test_trace_corruption_rejected(protocol, synthetic, change):
    trace = copy.deepcopy(synthetic[0]["trajectories"]["activation/1000"])
    if change == "truncated":
        trace["gate"].pop()
    elif change == "time":
        trace["time_us"][-1] += 1
    elif change == "voltage":
        trace["voltage_V"][-1] = 20
    elif change == "nan":
        trace["gate"][-1][0] = float("nan")
    elif change == "boolean":
        trace["gate"][-1][0] = True
    elif change == "range":
        trace["gate"][-1][0] = 1.001
    elif change == "steps":
        trace["steps"] += 1
    elif change == "invalid_stage":
        trace["all_steps_valid"] = False
    elif change == "mutated_input":
        trace["input_unchanged"] = False
    elif change == "reinitialized":
        trace["gate"][0][0] = 0.5
    else:
        trace["extra"] = 1
    with pytest.raises(ValueError):
        ref.validate_trace(protocol["cases"][0], 1000, trace)


@pytest.mark.parametrize("change", ["missing_backend", "missing_trajectory", "wrong_gate_axis"])
def test_comparator_coverage_rejected(protocol, synthetic, change):
    native, cells = copy.deepcopy(synthetic)
    if change == "missing_backend":
        cells["kinetics"].pop("jax_jit")
    elif change == "missing_trajectory":
        native["trajectories"].pop("activation/250")
    else:
        native["kinetics"]["target"][0].pop()
    with pytest.raises(ValueError):
        ref.evaluate(protocol, native, cells)


def test_wrong_units_and_hidden_state_preserve_failures(protocol, synthetic):
    native, cells = copy.deepcopy(synthetic)
    native["kinetics"]["tau_s"][0][0] *= 1000
    trace = cells["trajectories"]["activation/250"]
    trace["gate"][5][0] += 0.01
    trace["open_fraction"][5] = trace["gate"][5][0] * trace["gate"][5][1]
    result = ref.evaluate(protocol, native, cells)
    assert result["status"] == "failed"
    failures = [row["id"] for row in result["comparisons"] if not row["pass"]]
    assert "kinetics/betse/0/tau_s/0" in failures
    assert "discrete/cells/activation/250/5/0" in failures
    assert "continuous/cells/activation/250/5/0" in failures


def test_open_product_has_its_own_check(protocol, synthetic):
    native, cells = copy.deepcopy(synthetic)
    native["trajectories"]["activation/1000"]["open_fraction"][4] += 0.01
    result = ref.evaluate(protocol, native, cells)
    assert result["status"] == "failed"
    assert any(
        row["id"] == "open/betse/activation/1000/4" and not row["pass"]
        for row in result["comparisons"]
    )


def test_reference_imports_neither_engine():
    assert not any(
        n == "betse" or n.startswith("betse.") or n == "cells" or n.startswith("cells.")
        for n in sys.modules
    )


def test_reviewed_source_and_production_remain_intact():
    reviewed = c.read(c.ROOT / "configs/reference/voltage_gated_channel_v1.json")["source"]
    for name, info in reviewed["files"].items():
        assert c.sha(c.SOURCE / name) == info["sha256"]
    assert len(c.authenticate_cells()["implementation_files_sha256"]) == 352
    assert job.prior_closeout()["diagnostic_failures_retained"] == 4173


def test_existing_output_refused_before_any_model_or_write(tmp_path, monkeypatch):
    output = tmp_path / "runs/existing"
    output.mkdir(parents=True)
    monkeypatch.setattr(c, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="fresh"):
        job.register(output, tmp_path / "unused.xml")
    assert list(output.iterdir()) == []


def test_launch_detached_without_wait_or_followup(tmp_path, monkeypatch, protocol):
    output = tmp_path / "capture"
    output.mkdir()
    c.write(output / "registration.json", {})
    monkeypatch.setattr(job, "register", lambda *_: {"protocol": protocol})
    called = []

    def popen(command, **kwargs):
        called.append((command, kwargs))
        return SimpleNamespace(pid=1234)  # No wait/poll/communicate method.

    monkeypatch.setattr(job.subprocess, "Popen", popen)
    result = job.launch(output, tmp_path / "checks.xml")
    assert result["pid"] == 1234 and not result["automatic_polling"]
    assert not result["automatic_followup"] and not result["automatic_retry"]
    assert called[0][1]["start_new_session"] is True
    assert called[0][0][-2:] == ["execute", str(output)]
    assert c.read(output / "launch.json") == result


def test_execute_failure_is_durable_and_does_not_retry(tmp_path, monkeypatch):
    def reject(_output):
        raise ValueError("synthetic changed source")

    monkeypatch.setattr(job, "authenticate_registration", reject)
    with pytest.raises(ValueError, match="changed source"):
        job.execute(tmp_path)
    failure = c.read(tmp_path / "failure.json")
    assert failure["status"] == "failed_not_qualified"
    assert not failure["automatic_retry"]
    assert not (tmp_path / "completion.json").exists()


@pytest.fixture
def synthetic_provenance(protocol):
    source = {"betse/science/channels/vg_k.py": "synthetic-native-hash"}
    modules = {
        "src/cells/processes/voltage_gates.py": "synthetic-law-hash",
        "src/cells/numerics/fixed_step.py": "synthetic-solver-hash",
    }
    registration = {
        "protocol": protocol,
        "upstream": {"files_sha256": source},
        "cells_runtime": {"synthetic": True},
        "sources_sha256": modules,
    }
    common = {
        "registration_sha256": "synthetic-registration",
        "warnings": [],
        "dtype": "float64",
        "kinetic_input_unchanged": True,
        "cpu_affinity": [0, 1, 2, 3],
    }
    package = c.REFERENCE_PYTHON.parent.parent / "lib/python3.13/site-packages/betse"
    native = copy.deepcopy(common) | {
        "engine": "unmodified_betse_Kv1p5_init_run",
        "initial_open_fraction_origin": "derived_m_times_h_before_first_native_update",
        "installed_python_sha256": source,
        "environment": {
            "packages": c.locked_reference_packages(),
            "python": "3.13.5",
            "executable": str(c.REFERENCE_PYTHON),
        },
        "module_paths": [
            str(package / p)
            for p in ("science/channels/vg_k.py", "science/channels/channelsabc.py")
        ],
        "native_metadata": {
            "time_unit": 1000.0,
            "voltage_correction_mV": 0.0,
            "powers": [1, 1],
            "ions": ["K"],
            "relative_permeability": [1.0],
            "targets": None,
            "declared_unused_reversal_mV": -65,
        },
    }
    cells = copy.deepcopy(common) | {
        "engine": "unchanged_cells_kinetics_shared_rk4_isolated_harness",
        "accepted_runtime": registration["cells_runtime"],
        "environment": {"executable": str(c.CELLS_PYTHON)},
        "module_sha256": modules,
        "device": "cpu",
        "x64_enabled": True,
        "jit_disabled": False,
        "trajectory_backend": "jax_jit",
        "kinetic_backends": list(ref.BACKENDS),
        "production_world_runner_executed": False,
    }
    return registration, native, cells


def test_worker_provenance_contract(synthetic_provenance):
    job.validate_workers(*synthetic_provenance, "synthetic-registration")


@pytest.mark.parametrize(
    "engine,field,value",
    [
        ("native", "engine", "synthetic_reference"),
        ("native", "initial_open_fraction_origin", "unrecorded_zero_time_update"),
        ("native", "installed_python_sha256", {}),
        ("native", "module_paths", ["/wrong/module.py"]),
        ("native", "warnings", [{"message": "numerical warning"}]),
        ("native", "dtype", "float32"),
        ("native", "kinetic_input_unchanged", False),
        ("native", "registration_sha256", "different"),
        ("cells", "engine", "reference_only"),
        ("cells", "accepted_runtime", {}),
        ("cells", "module_sha256", {}),
        ("cells", "device", "gpu"),
        ("cells", "x64_enabled", False),
        ("cells", "jit_disabled", True),
        ("cells", "trajectory_backend", "jax_eager"),
        ("cells", "kinetic_backends", ["numpy"]),
        ("cells", "production_world_runner_executed", True),
        ("cells", "cpu_affinity", [0, 1, 2, 3, 4]),
    ],
)
def test_wrong_worker_provenance_rejected(synthetic_provenance, engine, field, value):
    r, native, cells = synthetic_provenance
    (native if engine == "native" else cells)[field] = value
    with pytest.raises(ValueError):
        job.validate_workers(r, native, cells, "synthetic-registration")


def test_synthetic_gate_time_and_power_metadata_rejected(synthetic_provenance):
    r, native, cells = synthetic_provenance
    native["native_metadata"]["time_unit"] = 1.0
    native["native_metadata"]["powers"] = [4, 1]
    with pytest.raises(ValueError, match="metadata"):
        job.validate_workers(r, native, cells, "synthetic-registration")


def test_software_receipt_rejects_skip_and_count(tmp_path, monkeypatch):
    from xml.etree import ElementTree as ET

    monkeypatch.setattr(c, "ROOT", tmp_path)
    output = tmp_path / "reports"
    output.mkdir()
    root = ET.Element("testsuite", tests="20", failures="0", errors="0", skipped="0")
    for index in range(20):
        ET.SubElement(root, "testcase", classname="test_gate_contact", name=f"synthetic_{index}")
    path = output / "synthetic.xml"
    ET.ElementTree(root).write(path)
    assert job.software_receipt(path)["tests"] == 20
    root[0].append(ET.Element("skipped"))
    ET.ElementTree(root).write(path)
    with pytest.raises(ValueError, match="Rejected"):
        job.software_receipt(path)
    root[0].remove(root[0][0])
    root.set("tests", "21")
    ET.ElementTree(root).write(path)
    with pytest.raises(ValueError, match="count"):
        job.software_receipt(path)


def test_total_budget_exception_retained(tmp_path, monkeypatch):
    def timeout(_output):
        job.alarm(None, None)

    monkeypatch.setattr(job, "authenticate_registration", timeout)
    with pytest.raises(TimeoutError, match="wall budget"):
        job.execute(tmp_path)
    assert "wall budget" in c.read(tmp_path / "failure.json")["traceback"]
