"""Bounded preflight; replay saved failures and load native YAML, never integrate."""

import copy
import shutil
import subprocess
from types import SimpleNamespace

import pytest
import refinement_check as check
import refinement_context as ctx
import refinement_job as job


@pytest.fixture(scope="module")
def original():
    return ctx.c.read(ctx.PRIOR / "registration.json")


def test_sealed_prerequisite_identity():
    assert ctx.prior()["failed_payload_files"] == 431


def test_declared_capture_counts_and_bounds():
    amendment = ctx.c.read(ctx.PROTOCOL)
    ctx.validate(amendment)
    assert amendment["native_observed_steps"] == 6720
    assert amendment["resources"]["artifact_bytes"] == 2 * 1024**3
    assert amendment["resources"]["per_file_bytes"] == 256 * 1024**2


@pytest.mark.parametrize(
    "name",
    [
        "mapping",
        "trajectory",
        "accounting",
        "refinement",
        "reference",
        "duration_s",
        "common_times_s",
        "cells_steps_s",
        "restart_time_s",
    ],
)
def test_original_numerical_and_physical_criteria_unchanged(original, name):
    current = ctx.effective_protocol(ctx.c.read(ctx.PROTOCOL))
    assert current[name] == original["protocol"][name]


@pytest.mark.parametrize(
    "name",
    [
        "production_changed",
        "scientific_tolerances_changed",
        "physical_parameters_changed",
        "energy_definition_changed",
        "automatic_retry",
        "automatic_followup",
        "automatic_polling",
    ],
)
def test_scope_expansion_refused(name):
    value = ctx.c.read(ctx.PROTOCOL)
    value[name] = True
    with pytest.raises(ValueError):
        ctx.validate(value)


@pytest.mark.parametrize(
    "name",
    [
        "native_steps_s",
        "native_runs",
        "native_observed_steps",
        "new_cells_trajectories",
        "new_reference_solves",
    ],
)
def test_unregistered_plan_refused(name):
    value = ctx.c.read(ctx.PROTOCOL)
    value[name] = 999
    with pytest.raises(ValueError):
        ctx.validate(value)


def test_all_numeric_failures_counted_with_bounded_examples():
    ledger = check.Ledger(limit=1)
    ledger.scope = "case"
    ledger.compare("energy", [2.0, 3.0, 0.0], [0.0, 0.0, 0.0], 1.0)
    assert ledger.comparisons == 3 and ledger.failed_comparisons == 2
    assert ledger.failed_groups == {"case/energy": 2}
    assert len(ledger.examples) == 1


def test_relative_budget_is_not_an_absolute_only_gate():
    ledger = check.Ledger()
    ledger.compare("value", 1.5, 1.0, 0.1, 0.5)
    assert ledger.failed_comparisons == 0


@pytest.mark.parametrize("values", [[float("nan")], [float("inf")], []])
def test_nonfinite_or_missing_evidence_stops(values):
    with pytest.raises(ValueError):
        check.Ledger().compare("invalid", values, [0.0], 1.0)


@pytest.mark.parametrize(
    "errors,valid",
    [([4.0, 2.0, 1.0], True), ([4.0, 3.9, 3.8], False), ([1e-13, 2e-13, 1e-13], True)],
)
def test_unchanged_refinement_rule(errors, valid):
    assert check.refinement(errors, 1e-12, 0.8)["passed"] is valid


def test_exact_overlap_retains_signed_zero():
    assert ctx.overlap({"x": [-0.0]}, {"x": [-0.0]})
    with pytest.raises(ValueError, match="overlap"):
        ctx.overlap({"x": [0.0]}, {"x": [-0.0]})


@pytest.mark.parametrize("name", ["dt_s", "steps"])
def test_mislabeled_native_grid_rejected(name):
    row = dict(id="pump_leak", mode="observed", dt_s=6.25e-6, steps=160, trace={})
    check.row_identity(row, "pump_leak", "observed", 6.25e-6, 0.001)
    row[name] *= 2
    with pytest.raises(ValueError, match="timestep"):
        check.row_identity(row, "pump_leak", "observed", 6.25e-6, 0.001)


@pytest.mark.parametrize("phase", job.PHASES)
def test_worker_dispatches_exactly_once(phase, monkeypatch, tmp_path):
    calls = []
    if phase == "reuse":
        result = dict(
            status="saved_evidence_reused",
            cells_trajectories=24,
            reference_solves=18,
            restart_suffixes=6,
            new_solver_runs=0,
        )
    elif phase == "betse":
        result = dict(native_runs=36, observer_pairs=18)
    else:
        result = dict(
            status="refined_pump_pilot_pass_pending_independent_review",
            failed_comparisons=0,
            exact_overlap_records=dict.fromkeys(range(12), "hash"),
            refinement={str(i): dict(passed=True) for i in range(36)},
        )

    def action(*args):
        calls.append(args)
        return result

    def module(name):
        assert name == ("pilot_native" if phase == "betse" else "refinement_check")
        return SimpleNamespace(worker=action, compare=action)

    monkeypatch.setattr(job, "authenticate", lambda *args, **kwargs: dict(reuse_files_sha256={}))
    monkeypatch.setattr(ctx, "reuse", action)
    monkeypatch.setattr(job.importlib, "import_module", module)
    job.worker(phase, tmp_path)
    assert len(calls) == 1 and (tmp_path / (phase + ".json")).is_file()
    assert not list(tmp_path.glob("*failure*"))


@pytest.mark.parametrize("phase", job.PHASES)
def test_failed_phase_cannot_advance(phase):
    with pytest.raises((ValueError, KeyError)):
        job.gate(phase, {"status": "failed"})


def test_reuse_is_a_copy_not_a_solver_run(tmp_path):
    manifest = ctx.reuse_manifest()
    result = ctx.reuse(tmp_path, manifest)
    assert result["new_solver_runs"] == 0 and result["cells_trajectories"] == 24
    assert all(ctx.c.sha(tmp_path / n) == h for n, h in manifest.items())
    with pytest.raises(ValueError, match="target"):
        ctx.reuse(tmp_path, manifest)


def test_existing_output_cannot_be_registered(tmp_path):
    with pytest.raises(ValueError, match="Fresh"):
        job.register(ctx.c.ROOT / "runs", tmp_path / "unused.xml")


def test_old_test_receipt_not_accepted_as_new_suite():
    with pytest.raises(ValueError, match="suite"):
        job.receipt(ctx.c.ROOT / "reports/ref-005c-pilot-checks-01.xml")


def test_artifact_limits_include_individual_files(tmp_path):
    (tmp_path / "sample").write_bytes(b"abc")
    with pytest.raises(ValueError, match="Per-file"):
        job.budget(tmp_path, dict(per_file_bytes=2, artifact_bytes=1024**2 + 10))
    assert job.budget(tmp_path, dict(per_file_bytes=3, artifact_bytes=1024**2 + 10)) == 3


def test_saved_failed_panel_reproduces_all_six_misses(original, tmp_path):
    # Recheck existing numbers in a fresh temporary output; never write into
    # the rejected capture. No model or adaptive solver is imported or run.
    r = copy.deepcopy(original)
    r["amendment"] = ctx.c.read(ctx.PROTOCOL)
    for name in ("reference.json", "cells.json"):
        shutil.copyfile(ctx.PRIOR / name, tmp_path / name)
    native = ctx.c.read(ctx.PRIOR / "betse.json")
    native["records"] = {k: str(ctx.PRIOR / v) for k, v in native["records"].items()}
    ctx.c.write(tmp_path / "betse.json", native)
    result = check.compare(r, tmp_path)
    assert result["status"] == "refined_pump_pilot_failed_not_qualified"
    assert result["failed_comparisons"] == len(result["failed_groups"]) == 6
    assert len(result["exact_overlap_records"]) == 12
    assert all(v["passed"] for v in result["refinement"].values())
    assert len(list((tmp_path / "comparison_rows").rglob("result.json"))) == 18
    with pytest.raises(ValueError, match="numerical"):
        job.gate("comparison", result)


def test_actual_native_refined_yaml_load_only(tmp_path):
    code = """
import copy, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import refinement_context as ctx
sys.path.insert(0, str(ctx.HERE.parent/'pump_loop_preflight'))
import pump_context as native_context
from betse.science.parameters import Parameters
from ruamel.yaml import YAML
original = ctx.c.read(ctx.PRIOR/'registration.json')
amendment = ctx.c.read(ctx.PROTOCOL)
y = YAML(typ='safe'); y.default_flow_style = False
with (ctx.c.SOURCE/'betse/data/yaml/sim_config.yaml').open() as stream:
    template = y.load(stream)
count = 0
for dt in amendment['native_steps_s']:
    p = copy.deepcopy(original['native_preparation']['protocol'])
    p.update(dt_s=dt, duration_s=0.001, steps=round(0.001/dt))
    for v in p['variants']:
        directory = Path(sys.argv[2])/str(count); directory.mkdir()
        path = directory/'native.yaml'
        config = native_context.configuration(template,p,v,directory)
        with path.open('x') as stream:
            y.dump(config,stream)
        native = Parameters(); native.load(str(path))
        assert native.init_time_step == dt and native.init_time_total == 0.001
        assert round(native.init_time_total/native.init_time_step) == p['steps']
        assert native.alpha_NaK == (p['alpha_mol_per_m2_s'] if v['pump'] else 0)
        assert native.T == p['temperature_K']
        assert native.molecules_enabled is False and native.is_ecm is False
        assert {k:getattr(native,k) for k in p['pump_parameters']} == p['pump_parameters']
        count += 1
assert count == 18
assert not any(n == 'cells' or n.startswith('cells.') for n in sys.modules)
"""
    result = subprocess.run(
        [str(ctx.c.REFERENCE_PYTHON), "-B", "-c", code, str(ctx.HERE), str(tmp_path)],
        cwd=ctx.c.ROOT,
        env=job.environment(),
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert result.returncode == 0, result.stdout + result.stderr
