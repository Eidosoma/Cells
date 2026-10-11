"""Replay saved rounding witnesses while protecting selected field operations.

Complete one-tick updates use the ordinary guarded engine. Reference and baseline
candidate paths must reproduce the saved trace; experimental updates start from
identical reference inputs. Passing these few steps is not trajectory acceptance.
"""

import gc
import time
import traceback
from contextlib import contextmanager, nullcontext
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import jax
import jax.numpy as jnp
import numpy as np
from jax.custom_batching import sequential_vmap

from cells.assembly_cell.io import flatten
from cells.assembly_cluster import engine, kernel
from cells.assembly_cluster.spec import parse_spec
from cells.ensemble import cli
from cells.models import finite_extracellular as finite
from cells.models import multispecies_membrane as membrane
from cells.numerics import extracellular_field as field

if __package__:
    from . import parallel_kernel as candidate
    from . import rounding_cluster as rounding
else:
    import parallel_kernel as candidate
    import rounding_cluster as rounding

BASELINE = "parallel_scalar_linear"
EXPERIMENTS = (
    BASELINE,
    "parallel_scalar_linear_sums",
    "parallel_scalar_linear_logmean",
    "parallel_scalar_field",
)
ENERGY_BASELINE = "parallel_scalar_linear_sums"
ENERGY_EXPERIMENTS = (
    ENERGY_BASELINE,
    "parallel_scalar_membrane_sum",
    "parallel_scalar_membrane_rate",
    "parallel_scalar_membrane_energy",
    "parallel_scalar_rk4",
)
need = rounding.need


def witness_ticks(results, final_tick):
    """Include every first-field witness on either device and the final step."""
    ticks = [1, final_tick]
    for result in results:
        need(result["trace_reproduces_prior_screen"], "Require a reproduced trace")
        need(result["first_divergence"]["tick"] == 1, "Require the saved first-step case")
        ticks.extend(row["tick"] for row in result["first_by_field"].values())
    need(
        all(type(t) is int and 1 <= t <= final_tick for t in ticks),
        "Invalid witness tick",
    )
    return sorted(set(ticks))


def energy_witnesses(reference, batched):
    """Cover each affected world's onset, largest ULP error and final recovery."""
    difference = rounding.differences(reference, batched)
    field_name = "ionic_dissipated_energy_pJ"
    need(
        set(difference["different_fields"]) == {field_name},
        "Require differences confined to the membrane energy ledger",
    )
    left, right = reference[field_name], batched[field_name]
    need(left.dtype == np.float64 and left.ndim == 3, "Require tick/world/membrane float64 energy")
    nt, worlds, _ = left.shape
    expected = np.broadcast_to(np.arange(nt)[:, None], (nt, worlds))
    for trace in (reference, batched):
        need(np.array_equal(trace["tick"], expected), "Incomplete energy witness tick grid")
    need(
        all(v.shape[:2] == (nt, worlds) for v in reference.values()),
        "Incomplete energy witness state grid",
    )
    need(
        np.isfinite(left).all()
        and np.isfinite(right).all()
        and np.all(left >= 0)
        and np.all(right >= 0),
        "Invalid saved energy values",
    )
    a, b = left.view(np.uint64), right.view(np.uint64)
    changed = a != b
    need(
        not changed[0].any() and not changed[-1].any(),
        "Require matching initial/final states around transient energy differences",
    )
    by_world = np.any(changed, axis=2)
    onset = {
        str(w): int(np.flatnonzero(by_world[:, w])[0])
        for w in np.flatnonzero(np.any(by_world, axis=0))
    }
    locations = np.argwhere(changed)
    first, last = int(locations[:, 0].min()), int(locations[:, 0].max())
    # Use the same ordered-bit distance as the comparator, including signed zero.
    sign = np.uint64(1 << 63)
    ordered_a = np.where((a & sign) != 0, ~a, a ^ sign)
    ordered_b = np.where((b & sign) != 0, ~b, b ^ sign)
    ulp = np.maximum(ordered_a, ordered_b) - np.minimum(ordered_a, ordered_b)
    worst_tick = int(np.argwhere(ulp == ulp.max())[0, 0])
    ticks = sorted(
        {1, nt - 1, first, max(1, first - 1), last, last + 1, worst_tick, *onset.values()}
    )
    return {
        "witness_ticks": ticks,
        "first_different_tick_by_world_offset": onset,
        "first_changed_tick": first,
        "last_changed_tick": last,
        "first_maximum_ulp_tick": worst_tick,
        "complete_trace_comparison": difference,
    }


def authenticate_previous(path, spec, settings):
    result, done, record = (
        cli.read(path / name) for name in ("result.json", "completion.json", "registration.json")
    )
    need(result["status"] == done["status"] == "completed", "Require a completed trace")
    need(result["mode"] == record["mode"] == "rounding_trace", "Require a rounding trace")
    need(done["result_sha256"] == cli.sha(path / "result.json"), "Trace result changed")
    need(result["registration_sha256"] == cli.sha(path / "registration.json"), "Trace changed")
    need(record["definition"] == spec.to_dict(), "Witness definition differs from trace")
    need(record["production_sources_sha256"] == cli.sources(), "Production source changed")
    need(settings["variants"] == record["variants"] == [BASELINE], "Require original baseline")
    for key in ("tile_width_by_backend", "run_wall_seconds"):
        need(record[key] == settings[key], "Witness execution differs: " + key)
    for name, digest in record["production_sources_sha256"].items():
        need(cli.sha(path / "source/cells" / name) == digest, "Frozen trace source changed")
    for name, digest in record["drivers_sha256"].items():
        need(cli.sha(path / "source" / name) == digest, "Frozen trace driver changed")
    for name, digest in result["evidence_sha256"].items():
        need(cli.sha(path / name) == digest, "Trace evidence changed: " + name)
    need(
        rounding.authenticate_previous(Path(record["rounding_parent"]["path"]), spec, settings)
        == record["rounding_parent"],
        "Original candidate screen changed",
    )
    phases = [cli.read(path / b / "result.json") for b in ("cpu", "gpu")]
    return {
        "path": str(path),
        "result_sha256": cli.sha(path / "result.json"),
        "witness_ticks": witness_ticks(phases, spec.ticks),
    }


def require_gpu_witness_pass(result, variant):
    summary = result["variants"][BASELINE]
    need(summary["diagnostic_reproduction_pass"] is True, "Saved steps did not reproduce")
    need(
        summary["saved_step_exact_by_experiment"][variant]["gpu"] is True,
        "Selected GPU candidate did not pass saved steps",
    )


def authenticate_gpu_screen(path, spec, settings):
    """Bind the successful GPU witnesses while retaining scalar CPU execution."""
    result, done, record = (
        cli.read(path / name) for name in ("result.json", "completion.json", "registration.json")
    )
    need(result["status"] == done["status"] == "completed", "Require completed saved steps")
    need(result["mode"] == record["mode"] == "saved_steps", "Require a saved-step screen")
    need(done["result_sha256"] == cli.sha(path / "result.json"), "Step result changed")
    need(result["registration_sha256"] == cli.sha(path / "registration.json"), "Steps changed")
    need(record["definition"] == spec.to_dict(), "GPU screen definition differs")
    need(settings["variants"] == ["parallel_scalar_linear_sums"], "Select solve-plus-sums")
    for key in ("tile_width_by_backend", "run_wall_seconds"):
        need(record[key] == settings[key], "GPU screen execution differs: " + key)
    need(record["production_sources_sha256"] == cli.sources(), "Production source changed")
    need(
        record["drivers_sha256"]["parallel_kernel.py"] == cli.sha(Path(candidate.__file__)),
        "GPU candidate changed since saved-step screen",
    )
    for name, digest in record["production_sources_sha256"].items():
        need(cli.sha(path / "source/cells" / name) == digest, "Frozen step source changed")
    for name, digest in record["drivers_sha256"].items():
        need(cli.sha(path / "source" / name) == digest, "Frozen step driver changed")
    for name, digest in result["evidence_sha256"].items():
        need(cli.sha(path / name) == digest, "Step evidence changed: " + name)
    trace = authenticate_previous(Path(record["step_parent"]["path"]), spec, record)
    need(trace == record["step_parent"], "Reference trace changed")
    require_gpu_witness_pass(result, settings["variants"][0])
    return {
        "path": str(path),
        "result_sha256": cli.sha(path / "result.json"),
        "reference_trace": trace,
    }


@contextmanager
def experiment(name, width):
    need(name in EXPERIMENTS, "Unknown saved-step experiment")
    original = field.logmean

    @sequential_vmap
    def scalar_mean(left, right):
        return original(left, right)

    def protected_mean(left, right, *, xp=None):
        if xp is np:
            return original(left, right, xp=xp)
        return scalar_mean(left, right)

    logarithm = name == "parallel_scalar_linear_logmean"
    variant = BASELINE if logarithm else name
    with candidate.candidate(variant, width=width):
        with patch.object(field, "logmean", protected_mean) if logarithm else nullcontext():
            yield


@contextmanager
def energy_experiment(name, width):
    """Protect original energy operations at progressively wider boundaries.

    These wrappers change batching only. They retain the existing equations,
    NumPy accounting and complete checked RK4; no ledger repair or new tolerances.
    """
    need(name in ENERGY_EXPERIMENTS, "Unknown energy witness experiment")
    rate, assemble, integrate = (
        membrane.dissipation_rate,
        finite.assemble_rhs,
        kernel.rk4_checked_step,
    )
    sums = candidate._FieldBackend(scalar_sums=True)

    @sequential_vmap
    def scalar_rate(leak, cycles, mu, affinity):
        return rate(leak, cycles, mu, affinity, xp=jnp)

    def protected_rate(leak, cycles, mu, affinity, *, xp=jnp):
        if xp is np:
            return rate(leak, cycles, mu, affinity, xp=xp)
        if name == "parallel_scalar_membrane_sum":
            return rate(leak, cycles, mu, affinity, xp=sums)
        return scalar_rate(leak, cycles, mu, affinity)

    @sequential_vmap
    def scalar_energy(*args):
        return assemble(*args, xp=jnp).dissipated_energy_pJ

    def protected_assembly(*args, xp=jnp):
        rates = assemble(*args, xp=xp)
        if xp is np:
            return rates
        return rates._replace(dissipated_energy_pJ=scalar_energy(*args))

    def protected_integrator(rhs, valid, state, dt, control, parameters, active):
        @sequential_vmap
        def scalar_step(s, h, c, p, a):
            return integrate(rhs, valid, s, h, c, p, a)

        return scalar_step(state, dt, control, parameters, active)

    target = nullcontext()
    if name in ("parallel_scalar_membrane_sum", "parallel_scalar_membrane_rate"):
        target = patch.object(membrane, "dissipation_rate", protected_rate)
    elif name == "parallel_scalar_membrane_energy":
        target = patch.object(finite, "assemble_rhs", protected_assembly)
    elif name == "parallel_scalar_rk4":
        target = patch.object(kernel, "rk4_checked_step", protected_integrator)
    with candidate.candidate(ENERGY_BASELINE, width=width), target:
        yield


class CompilerCapture:
    """Save IR outside compilation without changing the function or its outputs."""

    def __init__(self, advance, directory):
        self.advance, self.directory = advance, directory
        self.saved = False

    def lower(self, *args, **kwargs):
        lowered = self.advance.lower(*args, **kwargs)
        capture = self

        class Lowered:
            def compile(self):
                compiled = lowered.compile()
                if not capture.saved:
                    for name, value in (
                        ("lowered.mlir", lowered.as_text(debug_info=True)),
                        ("optimized.hlo", compiled.as_text()),
                    ):
                        need(isinstance(value, str) and value, "Missing compiler text: " + name)
                        with (capture.directory / name).open("x") as stream:
                            stream.write(value)
                    capture.saved = True
                return compiled

        return Lowered()


def state_at(trace, tick):
    values = {key: value[tick].copy() for key, value in trace.items()}
    need(np.all(values["tick"] == tick), "Trace tick does not match witness")
    return values


def compare_step(directory, spec, backend, before, expected, tick):
    directory.mkdir()
    template = engine.initial_state(spec)
    state = rounding.state_from_arrays(template, before)
    need(np.all(state.tick == tick - 1), "Witness must advance exactly one tick")
    rounding.save_arrays(directory / "before.npz", before)
    after, report = engine.run(
        spec, backend=backend, state=state, until=tick * spec.ionic.execution.dt
    )
    values = flatten(after)
    rounding.save_arrays(directory / "after.npz", values)
    cli.write(directory / "report.json", report)
    need(np.all(values["tick"] == tick), "Witness did not advance exactly one tick")
    comparison = rounding.differences(expected, values)
    cli.write(directory / "comparison.json", comparison)
    return comparison


def require_reproduction(comparison, label):
    need(not comparison["different_fields"], "Saved trace was not reproduced: " + label)


def phase(root, directory, backend, record, progress):
    started = time.time()
    spec = replace(parse_spec(record["definition"]), window_ticks=1)
    energy = record["mode"] == "energy_steps"
    binding = record["energy_step_parent"] if energy else record["step_parent"]
    previous = Path(binding["path"]) / backend
    ticks = binding["witnesses"]["witness_ticks"] if energy else binding["witness_ticks"]
    width = record["tile_width_by_backend"][backend]
    baseline = ENERGY_BASELINE if energy else BASELINE
    experiments = ENERGY_EXPERIMENTS if energy else EXPERIMENTS
    traces = {
        "reference": rounding.load_arrays(previous / "reference-trace.npz"),
        "candidate": rounding.load_arrays(
            previous / (baseline + "/full-trace.npz" if energy else "candidate-trace.npz")
        ),
    }
    outcomes = {}
    try:
        for name in ("reference", *experiments):
            target = directory / name
            target.mkdir()
            progress(phase=backend, step=name, witness_ticks=ticks)
            context = (
                nullcontext()
                if name == "reference"
                else (energy_experiment if energy else experiment)(name, width)
            )
            comparisons, reproduction = {}, {}
            with context:
                capture = CompilerCapture(engine.advance, target)
                with patch.object(engine, "advance", capture):
                    for tick in ticks:
                        progress(phase=backend, step=name, witness_tick=tick)
                        comparison = compare_step(
                            target / str(tick),
                            spec,
                            backend,
                            state_at(traces["reference"], tick - 1),
                            state_at(traces["reference"], tick),
                            tick,
                        )
                        comparisons[str(tick)] = comparison
                        if name == "reference":
                            require_reproduction(comparison, f"reference tick {tick}")
                        elif name == baseline:
                            reproduced = compare_step(
                                target / (str(tick) + "-prior-candidate"),
                                spec,
                                backend,
                                state_at(traces["candidate"], tick - 1),
                                state_at(traces["candidate"], tick),
                                tick,
                            )
                            reproduction[str(tick)] = reproduced
                            require_reproduction(reproduced, f"candidate tick {tick}")
            outcomes[name] = {
                "same_input_comparisons": comparisons,
                "all_saved_steps_exact": all(
                    not c["different_fields"] for c in comparisons.values()
                ),
                "prior_candidate_comparisons": reproduction,
            }
            cli.write(target / "result.json", outcomes[name])
            del capture
            jax.clear_caches()
            gc.collect()
        cli.write(
            directory / "result.json",
            {
                "status": "completed",
                "backend": backend,
                "witness_ticks": ticks,
                "experiments": outcomes,
                "trace_reproduced": True,
                "elapsed_seconds": time.time() - started,
                "scientifically_qualified": False,
                "scope": (
                    "Selected one-tick witnesses only; no trajectory or performance acceptance"
                ),
            },
        )
    except BaseException:
        cli.write(
            directory / "failure.json",
            {
                "status": "failed",
                "elapsed_seconds": time.time() - started,
                "traceback": traceback.format_exc(),
            },
        )
        raise
