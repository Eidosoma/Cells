"""Short software checks; synthetic results are not executed BETSE evidence."""

import copy
import importlib
import math
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
ref = importlib.import_module("pump_reference")
array = importlib.import_module("pump_array")
job = importlib.import_module("pump_job")
workers = importlib.import_module("pump_workers")


@pytest.fixture
def baseline():
    return {"id": "baseline", **ref.BASE}


def synthetic_results(plan):
    return {
        engine: {
            name: {
                case["id"]: {k: ref.oracle(case, profile["constants"])[k] for k in ref.OUTPUTS}
                for case in profile["cases"]
            }
            for name, profile in plan["profiles"].items()
        }
        for engine in ref.ENGINES
    }


@pytest.mark.parametrize("profile", ref.CONSTANTS)
def test_numpy_panel_thermodynamics_and_units(profile):
    constants = ref.CONSTANTS[profile]
    cases = ref.cases(constants)
    values = np.asarray([[case[k] for k in ref.FIELDS] for case in cases], dtype=np.float64)
    before = values.copy()
    raw = array.densities(values, constants, np)
    actual = workers.columns(raw, {"constants": constants, "cases": cases})
    assert np.array_equal(before, values)
    assert np.array_equal(raw[:, 2], -raw[:, 0])
    for case in cases:
        expected = ref.oracle(case, constants)
        assert expected["dissipation_pJ_s"] >= 0
        for name in ref.OUTPUTS:
            assert abs(actual[case["id"]][name] - expected[name]) <= (
                ref.ABSOLUTE[name] + ref.RELATIVE * abs(expected[name])
            )
        assert expected["na_in_fmol_s"] == pytest.approx(-1.5 * expected["k_in_fmol_s"])
        if case["availability"] == 0 or case["alpha_mol_m2_s"] == 0:
            assert all(actual[case["id"]][name] == 0 for name in ref.OUTPUTS)


@pytest.mark.parametrize("name", ref.FIELDS[:12])
@pytest.mark.parametrize("value", [0.0, -1.0])
def test_nonpositive_inputs_rejected(baseline, name, value):
    baseline[name] = value
    with pytest.raises(ValueError, match="Nonpositive"):
        ref.oracle(baseline, ref.CONSTANTS["source_constants"])


@pytest.mark.parametrize(
    "name,value",
    [
        ("availability", -0.01),
        ("availability", 1.01),
        ("alpha_mol_m2_s", -1),
        ("temperature_K", 100),
        ("temperature_K", 401),
        ("voltage_V", 10),
        ("na_in_mM", math.nan),
        ("voltage_V", math.inf),
        ("atp_mM", True),
    ],
)
def test_invalid_contact_domain_rejected(baseline, name, value):
    baseline[name] = value
    with pytest.raises(ValueError):
        ref.oracle(baseline, ref.CONSTANTS["source_constants"])


def test_stall_and_reversal_are_not_physiological_range():
    rows = {
        case["id"]: ref.oracle(case, ref.CONSTANTS["source_constants"])
        for case in ref.cases(ref.CONSTANTS["source_constants"])
    }
    assert rows["mathematical_reverse"]["cycles_density_mol_m2_s"] < 0
    assert rows["mathematical_forward"]["cycles_density_mol_m2_s"] > 0
    assert abs(rows["mathematical_stall"]["cycles_density_mol_m2_s"]) < 1e-20
    assert rows["baseline"]["inward_current_A"] < 0


@pytest.mark.parametrize(
    "name,value,factor",
    [
        ("area_m2", 2e-9, 2),
        ("alpha_mol_m2_s", 2e-7, 2),
        ("availability", 0.5, 0.5),
    ],
)
def test_extensive_scaling(baseline, name, value, factor):
    constants = ref.CONSTANTS["source_constants"]
    initial = ref.oracle(baseline, constants)
    changed = ref.oracle({**baseline, name: value}, constants)
    for field in ("na_in_fmol_s", "k_in_fmol_s", "inward_current_A", "dissipation_pJ_s"):
        assert changed[field] == pytest.approx(factor * initial[field], rel=1e-14)


def test_third_return_is_not_cycle_rate(baseline):
    result = ref.oracle(baseline, ref.CONSTANTS["source_constants"])
    cycles = result["cycles_density_mol_m2_s"] * baseline["area_m2"] * 1e15
    assert result["third_out_na_fmol_s"] == pytest.approx(3 * cycles)
    assert result["third_out_na_fmol_s"] != pytest.approx(cycles)


def test_synthetic_affinity_only_law_cannot_supply_substrate_saturation(baseline):
    constants = ref.CONSTANTS["source_constants"]
    first = ref.oracle(baseline, constants)
    # Keep total affinity fixed while changing ATP saturation; do not fit a pump.
    changed = {
        **baseline,
        "atp_mM": 0.15,
        "voltage_V": baseline["voltage_V"]
        + constants["R"] * baseline["temperature_K"] * math.log(10) / constants["F"],
    }
    second = ref.oracle(changed, constants)
    assert second["cycle_free_energy_J_mol"] == pytest.approx(first["cycle_free_energy_J_mol"])
    assert abs(second["cycles_density_mol_m2_s"] / first["cycles_density_mol_m2_s"] - 1) > 0.5
    a, b = (
        math.tanh(
            -result["cycle_free_energy_J_mol"] / (2 * constants["R"] * baseline["temperature_K"])
        )
        for result in (first, second)
    )
    assert a == pytest.approx(b, rel=1e-14)


def test_source_defaults_are_actually_read():
    assert job.source_defaults()["cADP"] == 0.1
    assert job.source_defaults()["deltaGATP"] == -37000.0


def test_synthetic_comparator_complete():
    plan = ref.protocol()
    result = ref.evaluate(plan, synthetic_results(plan))
    assert result["failures"] == 0
    assert result["comparisons"] == 4 * 2 * len(ref.cases(ref.CONSTANTS["source_constants"])) * 5
    assert not result["independent_saved_data_audit_complete"]


@pytest.mark.parametrize(
    "change", ["engine", "profile", "case", "column", "nonfinite", "numeric", "blocked"]
)
def test_saved_result_corruption(change):
    plan = ref.protocol()
    results = synthetic_results(plan)
    cases = results["native"]["source_constants"]
    if change == "engine":
        results.pop("jax_jit")
    elif change == "profile":
        results["native"].pop("matched_constants")
    elif change == "case":
        cases.pop("baseline")
    elif change == "column":
        cases["baseline"].pop("inward_current_A")
    elif change == "nonfinite":
        cases["baseline"]["na_in_fmol_s"] = math.nan
    elif change == "numeric":
        cases["baseline"]["third_out_na_fmol_s"] /= 3
    else:
        cases["availability=0.0"]["na_in_fmol_s"] = 1e-30
    if change in ("numeric", "blocked"):
        assert ref.evaluate(plan, results)["failures"] == 1
    else:
        with pytest.raises(ValueError):
            ref.evaluate(plan, results)


@pytest.mark.parametrize("key", ["relative_tolerance", "automatic_retry", "production_changed"])
def test_protocol_changes_rejected(key):
    plan = copy.deepcopy(ref.protocol())
    plan[key] = 123
    with pytest.raises(ValueError, match="Unregistered"):
        ref.validate_protocol(plan)


def test_launcher_is_detached_and_never_polls(tmp_path, monkeypatch):
    monkeypatch.setattr(job, "register", lambda *_: {"protocol": ref.protocol()})
    monkeypatch.setattr(job.c, "sha", lambda _: "fixture_hash")
    calls = []

    def popen(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(pid=123)  # Has neither poll nor wait.

    monkeypatch.setattr(job.subprocess, "Popen", popen)
    result = job.launch(tmp_path, tmp_path / "tests.xml")
    assert result["status"] == "launched_detached"
    assert result["automatic_polling"] is False
    assert calls[0][1]["start_new_session"] is True
    assert calls[0][1]["stdin"] is job.subprocess.DEVNULL
    assert (tmp_path / "launch.json").is_file()


def test_execution_failure_has_durable_receipt(tmp_path, monkeypatch):
    def reject(_output):
        raise ValueError("fixture authentication rejection")

    monkeypatch.setattr(job, "authenticate", reject)
    with pytest.raises(ValueError, match="fixture authentication"):
        job.execute(tmp_path)
    result = job.c.read(tmp_path / "failure.json")
    assert result["status"] == "failed_not_qualified"
    assert not result["automatic_retry"]
    assert not (tmp_path / "completion.json").exists()


def test_timeout_is_failure_not_qualification():
    with pytest.raises(TimeoutError):
        job.deadline(None, None)


def test_existing_output_rejected(tmp_path):
    with pytest.raises(ValueError, match="fresh run"):
        job.register(tmp_path, tmp_path / "none.xml")


def test_attempted_execution_is_not_rewritten(tmp_path):
    job.c.write(tmp_path / "started.json", {"fixture": "attempted"})
    original = (tmp_path / "started.json").read_bytes()
    with pytest.raises(ValueError, match="already attempted"):
        job.execute(tmp_path)
    assert (tmp_path / "started.json").read_bytes() == original
    assert not (tmp_path / "failure.json").exists()


@pytest.mark.parametrize(
    "field",
    [
        "registration_sha256",
        "warnings",
        "input_unchanged",
        "met_ignored",
        "third_is_outward_na",
        "engine",
        "overlap",
    ],
)
def test_worker_metadata_rejected(field):
    native = {
        "engine": "unmodified_betse_pumpNaKATP",
        "results": {"native": {}},
        "registration_sha256": "correct",
        "warnings": [],
        "input_unchanged": True,
        "met_ignored": True,
        "third_is_outward_na": True,
    }
    prototype = {
        "engine": "validation_only_nak_array_law",
        "results": {name: {} for name in ("numpy", "jax_eager", "jax_jit")},
        "registration_sha256": "correct",
        "warnings": [],
        "input_unchanged": True,
        "dtype": "float64",
        "backend": "cpu",
    }
    job.validate_workers(native, prototype, "correct")
    if field == "overlap":
        native["results"]["numpy"] = {}
    else:
        native[field] = "corruption"
    with pytest.raises(ValueError):
        job.validate_workers(native, prototype, "correct")


def test_biological_candidate_preserves_distinct_sources():
    record = job.c.read(
        job.c.ROOT / "validation/betse/biological_candidates/xenopus_costa_1989.json"
    )
    assert record["runnable"] is False and record["biology_validated"] is False
    original = record["original_abstract"]["permeability"]
    secondary = record["betse_2016_table_2"]["permeability"]
    for species in ("Na", "K", "Cl"):
        assert original["values_m_per_s"][species] == pytest.approx(
            original["values_original"][species] * original["conversion_to_m_per_s"],
            rel=1e-14,
            abs=0,
        )
        assert original["values_m_per_s"][species] != secondary["values"][species] * 1e-9
    assert record["original_abstract"]["inside_concentration"]["uncertainty_kind"] is None
    assert record["biological_tolerances"] is None


@pytest.mark.parametrize("engine", ["native", "prototype"])
def test_actual_three_fixture_worker_smoke(tmp_path, engine):
    # Component smoke only: baseline, exact block and mathematical reversal.
    plan = ref.protocol()
    profile = plan["profiles"]["source_constants"]
    profile["cases"] = [
        row
        for row in profile["cases"]
        if row["id"] in ("baseline", "availability=0.0", "mathematical_reverse")
    ]
    plan["profiles"] = {"source_constants": profile}
    registration = {
        "protocol": plan,
        "upstream": job.c.inspect_source(),
        "prototype_environment": job.c.environment(),
    }
    fixture = tmp_path / "smoke.json"
    job.c.write(fixture, registration)
    python = job.c.REFERENCE_PYTHON if engine == "native" else job.c.CELLS_PYTHON
    saved_path = tmp_path / "smoke-result.json"
    result = subprocess.run(
        [
            str(python),
            "-B",
            "-c",
            "import sys; import pump_workers as w; "
            "w.c.write(sys.argv[3], getattr(w, sys.argv[1])(w.c.read(sys.argv[2])))",
            engine,
            str(fixture),
            str(saved_path),
        ],
        cwd=Path(__file__).resolve().parent,
        env=job.environment(tmp_path),
        capture_output=True,
        text=True,
        check=True,
        timeout=25,
    )
    assert not result.stderr
    # BETSE writes startup notices to stdout. Keep machine payload separate,
    # as the actual detached controller already does; do not suppress native logs.
    saved = job.c.read(saved_path)
    assert saved["input_unchanged"] is True
    if engine == "native":
        assert saved["met_ignored"] is True and len(saved["installed_python_sha256"]) == 332
    for backend in saved["results"].values():
        for case in profile["cases"]:
            expected = ref.oracle(case, profile["constants"])
            actual = backend["source_constants"][case["id"]]
            for name in ref.OUTPUTS:
                assert abs(actual[name] - expected[name]) <= (
                    ref.ABSOLUTE[name] + ref.RELATIVE * abs(expected[name])
                )


@pytest.mark.parametrize("timeout", [False, True])
def test_controller_synthetic_success_and_worker_timeout(tmp_path, monkeypatch, timeout):
    plan = ref.protocol()
    results = synthetic_results(plan)
    job.c.write(tmp_path / "registration.json", {"fixture": "synthetic"})
    job.c.write(tmp_path / "sources.zip", {"fixture": "not_a_real_capsule"})
    registration_sha = job.c.sha(tmp_path / "registration.json")
    monkeypatch.setattr(job, "authenticate", lambda _: {"software": {"tests": 99}})
    monkeypatch.setattr(job.os, "sched_getaffinity", lambda _: {0, 1, 2, 3})
    monkeypatch.setattr(job.resource, "setrlimit", lambda *_: None)

    def run(command, **kwargs):
        assert kwargs["timeout"] == 45 and kwargs["check"] is True
        if timeout:
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        engine = command[-1]
        shared = {"registration_sha256": registration_sha, "input_unchanged": True, "warnings": []}
        if engine == "native":
            saved = {
                **shared,
                "engine": "unmodified_betse_pumpNaKATP",
                "results": {"native": results["native"]},
                "met_ignored": True,
                "third_is_outward_na": True,
            }
        else:
            saved = {
                **shared,
                "engine": "validation_only_nak_array_law",
                "results": {k: v for k, v in results.items() if k != "native"},
                "dtype": "float64",
                "backend": "cpu",
            }
        job.c.write(tmp_path / f"{engine}.json", saved)

    monkeypatch.setattr(job.subprocess, "run", run)
    if timeout:
        with pytest.raises(subprocess.TimeoutExpired):
            job.execute(tmp_path)
        assert (tmp_path / "failure.json").is_file()
        assert not (tmp_path / "completion.json").exists()
    else:
        job.execute(tmp_path)
        completion = job.c.read(tmp_path / "completion.json")
        assert completion["status"] == "contact_pass_pending_audit"
        assert completion["failures"] == 0
        assert not completion["production_pump_implemented"]
        assert not completion["independent_saved_data_audit_complete"]
        assert all(
            job.c.sha(tmp_path / name) == sha for name, sha in completion["files_sha256"].items()
        )
