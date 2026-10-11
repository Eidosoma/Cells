"""GPU-only acceptance cannot hide transient drift or promote CPU batching."""

import copy
from pathlib import Path

import numpy as np
import pytest

from cells.assembly_cell.io import flatten
from cells.assembly_cluster import engine
from cells.ensemble import cli
from validation.ensemble import parallel_cluster as screen
from validation.ensemble import rounding_cluster as rounding
from validation.ensemble import step_cluster as steps
from validation.ensemble.test_parallel_cluster import physical_spec

VARIANT = "parallel_scalar_linear_sums"


def witness_result():
    return {
        "variants": {
            steps.BASELINE: {
                "diagnostic_reproduction_pass": True,
                "saved_step_exact_by_experiment": {VARIANT: {"cpu": False, "gpu": True}},
            }
        }
    }


def test_gpu_witness_selection_does_not_claim_cpu_batching_passed():
    result = witness_result()
    steps.require_gpu_witness_pass(result, VARIANT)
    assert (
        result["variants"][steps.BASELINE]["saved_step_exact_by_experiment"][VARIANT]["cpu"]
        is False
    )


@pytest.mark.parametrize("reproduced,gpu_pass", [(False, True), (True, False), (True, 1)])
def test_unreproduced_or_nonpassing_gpu_witness_refused(reproduced, gpu_pass):
    result = witness_result()
    row = result["variants"][steps.BASELINE]
    row["diagnostic_reproduction_pass"] = reproduced
    row["saved_step_exact_by_experiment"][VARIANT]["gpu"] = gpu_pass
    with pytest.raises(ValueError, match="did not"):
        steps.require_gpu_witness_pass(result, VARIANT)


def test_complete_trajectory_retains_transient_difference_even_when_endpoint_matches():
    reference = [
        {"tick": np.array([tick], np.uint32), "energy": np.array([1.0])} for tick in range(3)
    ]
    trace = rounding.TickTrace(reference[0], 2, reference=reference)
    middle = copy.deepcopy(reference[1])
    middle["energy"][0] = np.nextafter(1.0, np.inf)
    trace.append(1, middle)
    with pytest.raises(ValueError, match="incomplete"):
        screen.trajectory_comparison(trace)
    trace.append(2, reference[2])
    assert not screen.differences(trace.samples[-1], reference[-1])["different_fields"]
    comparison = screen.trajectory_comparison(trace)
    assert comparison["compared_ticks"] == 2
    assert comparison["different_fields"]["energy"]["tick"] == 1
    assert comparison["different_fields"]["energy"]["max_ulp_difference"] == 1


@pytest.mark.parametrize("mode", screen.GPU_ONLY_MODES)
def test_gpu_screen_requires_reference_reproduction_gpu_exactness_and_cross_device_agreement(mode):
    record = {"mode": mode}
    phases = {
        "cpu": {"role": "scalar_reference_only", "reference_reproduced": True},
        "gpu": {
            "variants": {VARIANT: {"all_exact_checks_pass": True}},
            "reference_reproduced": True,
        },
    }
    assert screen.bounded_screen_pass(record, phases, VARIANT, {"passed": True})
    assert not screen.bounded_screen_pass(record, phases, VARIANT, {"passed": False})
    bad = copy.deepcopy(phases)
    bad["cpu"]["reference_reproduced"] = False
    assert not screen.bounded_screen_pass(record, bad, VARIANT, {"passed": True})
    bad = copy.deepcopy(phases)
    bad["gpu"]["variants"][VARIANT]["all_exact_checks_pass"] = False
    assert not screen.bounded_screen_pass(record, bad, VARIANT, {"passed": True})
    if mode in screen.LARGE_GPU_MODES:
        bad = copy.deepcopy(phases)
        bad["gpu"]["reference_reproduced"] = False
        assert not screen.bounded_screen_pass(record, bad, VARIANT, {"passed": True})


def test_ordinary_screen_still_requires_both_candidates_to_pass():
    phases = {
        "cpu": {"variants": {VARIANT: {"all_exact_checks_pass": False}}},
        "gpu": {"variants": {VARIANT: {"all_exact_checks_pass": True}}},
    }
    assert not screen.bounded_screen_pass({"mode": "screen"}, phases, VARIANT, {"passed": True})


@pytest.mark.parametrize("changed", [False, True])
@pytest.mark.parametrize("mode", screen.GPU_ONLY_MODES)
def test_cpu_phase_uses_scalar_engine_and_refuses_changed_reference(
    tmp_path, monkeypatch, changed, mode
):
    spec = screen.rebound(physical_spec(), worlds=5, first=0)
    initial = engine.initial_state(spec)
    final = initial._replace(
        tick=np.full_like(initial.tick, spec.ticks),
        pool=initial.pool._replace(time_s=np.full_like(initial.pool.time_s, spec.pool.end_time_s)),
    )
    trace_root = tmp_path / "trace"
    (trace_root / "cpu").mkdir(parents=True)
    rounding.save_arrays(
        trace_root / "cpu/reference-trace.npz",
        {k: np.stack([v, v]) for k, v in flatten(final).items()},
    )
    record = {
        "mode": mode,
        "definition": spec.to_dict(),
        "gpu_screen_parent": {"reference_trace": {"path": str(trace_root)}},
    }
    if mode == "larger_gpu_screen":
        rounding.save_arrays(
            trace_root / "cpu/reference.npz", {k: v[1:4] for k, v in flatten(final).items()}
        )
        record["larger_screen_parent"] = {
            "path": str(trace_root),
            "cpu_reference_world_id_start": 1,
            "cpu_reference_worlds": 3,
        }
    if mode == "energy_gpu_screen":
        rounding.save_arrays(trace_root / "cpu/reference.npz", flatten(final))
        record["energy_screen_parent"] = {
            "reference_screen": {"path": str(trace_root), "result_sha256": "test-reference"}
        }
    monkeypatch.setattr(screen, "authenticate", lambda root: record)
    monkeypatch.setattr(screen, "runtime", lambda: {})
    calls = []

    def run(definition, *, backend):
        assert definition.to_dict() == spec.to_dict() and backend == "cpu"
        calls.append(backend)
        if changed:
            return final._replace(
                availability_exposure_s=np.nextafter(final.availability_exposure_s, np.inf)
            ), {"backend": "cpu"}
        return final, {"backend": "cpu"}

    def forbidden(*args, **kwargs):
        pytest.fail("CPU reference must never enter a candidate context")

    monkeypatch.setattr(engine, "run", run)
    monkeypatch.setattr(screen.candidate_kernel, "candidate", forbidden)
    root = tmp_path / "run"
    root.mkdir()
    if changed:
        with pytest.raises(ValueError, match="reference endpoint changed"):
            screen.phase(root, "cpu")
        assert not (root / "cpu/result.json").exists()
    else:
        screen.phase(root, "cpu")
        result = cli.read(root / "cpu/result.json")
        assert result["role"] == "scalar_reference_only" and result["reference_reproduced"]
        assert not (root / "cpu" / VARIANT).exists()
    assert calls == ["cpu"]
    assert (Path(root) / "cpu/reference-replay-comparison.json").is_file()


@pytest.mark.parametrize(
    "reproduced,passed", [(True, True), (False, True), (1, True), (True, False), (True, 1)]
)
def test_energy_qualification_requires_exact_reproduced_witnesses(reproduced, passed):
    result = {
        "variants": {
            steps.ENERGY_BASELINE: {
                "diagnostic_reproduction_pass": reproduced,
                "saved_step_exact_by_experiment": {screen.ENERGY_SCREEN_VARIANT: {"gpu": passed}},
            }
        }
    }
    if reproduced is True and passed is True:
        screen.require_energy_screen_pass(result)
    else:
        with pytest.raises(ValueError, match="did not"):
            screen.require_energy_screen_pass(result)


def test_energy_variant_cannot_be_launched_without_its_passing_parent(tmp_path):
    with pytest.raises(ValueError, match="requires --energy-screen-parent"):
        screen.launch(
            tmp_path / "parent", tmp_path / "run", variants=[screen.ENERGY_SCREEN_VARIANT]
        )
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize("width", [32, 64])
def test_qualification_executes_the_existing_energy_wrapper_and_restores_it(width):
    from cells.models import multispecies_membrane as membrane

    original_rate, original_advance = membrane.dissipation_rate, engine.advance
    with screen.execution_candidate(screen.ENERGY_SCREEN_VARIANT, width):
        assert membrane.dissipation_rate is not original_rate
        assert engine.advance is not original_advance
        before = {
            "rate": original_rate(np.ones((4, 2)), np.ones(2), -np.ones((4, 2)), -np.ones(2), xp=np)
        }
        after = {
            "rate": membrane.dissipation_rate(
                np.ones((4, 2)), np.ones(2), -np.ones((4, 2)), -np.ones(2), xp=np
            )
        }
        assert not screen.differences(before, after)["different_fields"]
    assert membrane.dissipation_rate is original_rate and engine.advance is original_advance


@pytest.mark.parametrize("basis", ["energy_steps", "energy_gpu_screen"])
@pytest.mark.parametrize(
    "change",
    [
        "none",
        "failed",
        "width",
        "cpu_width",
        "budget",
        "physics",
        "kernel",
        "evidence",
    ],
)
def test_energy_screen_widens_only_a_passed_trajectory_with_unchanged_physics(
    tmp_path, monkeypatch, basis, change
):
    variant = screen.ENERGY_SCREEN_VARIANT
    spec = screen.with_run_budget(screen.rebound(physical_spec(), worlds=65, first=0), 1200)
    settings = screen.screen_settings(
        [variant], 4, 64 if basis == "energy_gpu_screen" else 32, 1200
    )
    parent, source = tmp_path / "campaign", tmp_path / "reference"
    (source / "gpu").mkdir(parents=True)
    cli.write(source / "result.json", {"status": "completed"})
    (source / "gpu/reference-trace.npz").write_bytes(b"authenticated scalar trace")
    previous = {
        "mode": basis,
        "parent": str(parent),
        "definition": spec.to_dict(),
        "variants": [variant],
        "tile_width_by_backend": {"cpu": 4, "gpu": 32},
        "run_wall_seconds": 1200,
        "drivers_sha256": {
            Path(module.__file__).name: cli.sha(Path(module.__file__))
            for module in (screen.candidate_kernel, steps)
        },
        "production_sources_sha256": {},
        "energy_step_parent": {"path": str(source)},
        "energy_screen_parent": {"reference_screen": {"path": str(source)}},
    }
    evidence = tmp_path / "evidence"
    evidence.write_text("exact states")
    result = {
        "status": "completed",
        "mode": basis,
        "evidence_sha256": {"evidence": cli.sha(evidence)},
        "variants": {
            variant: {
                "bounded_numerical_checks_pass": change != "failed",
                "eligible_for_performance_measurement": True,
                "candidate_backends": ["gpu"],
                "cpu_execution": "scalar_reference",
                "cpu_gpu_comparison": {"passed": True},
            }
        }
        if basis == "energy_gpu_screen"
        else {
            steps.ENERGY_BASELINE: {
                "diagnostic_reproduction_pass": True,
                "saved_step_exact_by_experiment": {variant: {"gpu": change != "failed"}},
            }
        },
    }
    if change == "width":
        settings["tile_width_by_backend"]["gpu"] = 32 if basis == "energy_gpu_screen" else 64
    elif change == "cpu_width":
        settings["tile_width_by_backend"]["cpu"] = 8
    elif change == "budget":
        settings["run_wall_seconds"] = 1500
    elif change == "physics":
        previous["definition"]["window_ticks"] += 1
    elif change == "kernel":
        previous["drivers_sha256"]["parallel_kernel.py"] = "changed"
    elif change == "evidence":
        evidence.write_text("changed states")
    cli.write(tmp_path / "registration.json", previous)
    result["registration_sha256"] = cli.sha(tmp_path / "registration.json")
    cli.write(tmp_path / "result.json", result)
    cli.write(
        tmp_path / "completion.json",
        {
            "status": "completed",
            "result_sha256": cli.sha(tmp_path / "result.json"),
        },
    )
    authenticated = []
    monkeypatch.setattr(screen, "authenticate", lambda path: authenticated.append(path))
    if change == "none":
        binding = screen.authenticate_energy_screen(tmp_path, spec, settings, parent)
        assert binding["path"] == str(tmp_path)
        assert binding["reference_screen"]["path"] == str(source)
        assert binding["reference_trace_sha256"] == cli.sha(source / "gpu/reference-trace.npz")
    else:
        with pytest.raises(ValueError):
            screen.authenticate_energy_screen(tmp_path, spec, settings, parent)
    assert authenticated == [tmp_path]
