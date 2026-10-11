"""Locate first trajectory differences without changing or accepting the candidate.

Every physical tick is retained. Endpoint comparisons against the preceding
screen establish whether the finer observation windows reproduce that screen.
Isolated field/RHS probes help localize differences but cannot prove equivalence
inside the compiled integrator.
"""

import time
import traceback
from dataclasses import replace
from pathlib import Path

import jax
import numpy as np

from cells.assembly.engine import device_for
from cells.assembly_cell.io import flatten
from cells.assembly_cluster import engine, kernel
from cells.assembly_cluster.spec import channel_owners, parse_spec
from cells.core.schedule import control_values
from cells.ensemble import cli
from cells.models import spatial_junction
from cells.models.registry import get_model

if __package__:
    from validation.assembly.cluster_partition_replay import differences

    from . import parallel_kernel as candidate
else:
    import parallel_kernel as candidate
    from cluster_partition_replay import differences


def need(value, message):
    if not value:
        raise ValueError(message)


def authenticate_previous(path, spec, settings):
    result, done, record = (
        cli.read(path / name) for name in ("result.json", "completion.json", "registration.json")
    )
    need(result["status"] == done["status"] == "completed", "Require a completed screen")
    need(done["result_sha256"] == cli.sha(path / "result.json"), "Screen result changed")
    need(result["registration_sha256"] == cli.sha(path / "registration.json"), "Screen changed")
    need(record["definition"] == spec.to_dict(), "Diagnostic definition differs from screen")
    need(record["production_sources_sha256"] == cli.sources(), "Production source changed")
    need(
        record["drivers_sha256"]["parallel_kernel.py"] == cli.sha(Path(candidate.__file__)),
        "Diagnostic candidate differs from screened candidate",
    )
    for key in ("variants", "tile_width_by_backend", "run_wall_seconds"):
        need(record[key] == settings[key], "Diagnostic execution differs: " + key)
    need(len(record["variants"]) == 1, "Trace exactly one screened candidate")
    for name, digest in record["production_sources_sha256"].items():
        need(cli.sha(path / "source/cells" / name) == digest, "Frozen screen source changed")
    for name, digest in record["drivers_sha256"].items():
        need(cli.sha(path / "source" / name) == digest, "Frozen screen driver changed")
    for name, digest in result["evidence_sha256"].items():
        need(cli.sha(path / name) == digest, "Screen evidence changed: " + name)
    variant = record["variants"][0]
    for backend in ("cpu", "gpu"):
        outcome = cli.read(path / backend / variant / "result.json")
        need(
            bool(outcome["comparisons"]["scalar_reference"]["different_fields"]),
            "Require a recorded exact-reference mismatch on each device",
        )
    return {"path": str(path), "result_sha256": cli.sha(path / "result.json")}


def load_arrays(path):
    with np.load(path, allow_pickle=False) as values:
        return {k: values[k].copy() for k in values.files}


def save_arrays(path, values):
    with path.open("xb") as stream:
        np.savez_compressed(stream, **values)


def require_same_schema(expected, values):
    need(set(values) == set(expected), "Incomplete trace state")
    for key, value in values.items():
        need(
            value.shape == expected[key].shape and value.dtype == expected[key].dtype,
            "Trace state shape/dtype mismatch: " + key,
        )


def state_from_arrays(template, values):
    """Reconstruct only arrays produced by this trace, using complete field names."""
    require_same_schema(flatten(template), values)
    parts = [
        type(getattr(template, name))(
            *(values[name + "_" + k] for k in getattr(template, name)._fields)
        )
        for name in ("pool", "ionic")
    ]
    return type(template)(*parts, *(values[k] for k in template._fields[2:]))


class TickTrace:
    def __init__(self, initial, ticks, *, reference=None):
        self.samples = [{k: np.array(v, copy=True) for k, v in initial.items()}]
        self.ticks, self.reference = ticks, reference
        self.first = None
        self.first_by_field = {}
        if reference is not None:
            need(len(reference) == ticks + 1, "Reference trace is incomplete")
            need(
                not differences(initial, reference[0])["different_fields"], "Initial states differ"
            )

    def append(self, window, values):
        need(window == len(self.samples) and window <= self.ticks, "Missing or repeated tick")
        need(np.all(values["tick"] == window), "Trace window does not represent one tick")
        # Validate all fields even if no reference is supplied.
        require_same_schema(self.samples[0], values)
        saved = {k: np.array(v, copy=True) for k, v in values.items()}
        self.samples.append(saved)
        if self.reference is None:
            return None
        delta = differences(self.reference[window], saved)
        if not delta["different_fields"]:
            return None
        for name, value in delta["different_fields"].items():
            self.first_by_field.setdefault(name, {"tick": window, **value})
        if self.first is None:
            self.first = {"tick": window, **delta}
            return self.first
        return None

    def save(self, path):
        save_arrays(path, {k: np.stack([s[k] for s in self.samples]) for k in self.samples[0]})


def probes(directory, spec, variant, width, backend, values, label):
    """Same-input field and complete derivative probes outside time integration."""
    model = get_model(spec.ionic.model)
    _, layout = model.initial_values(spec.ionic)
    controls = control_values(spec.ionic, [0.0])
    control = type(controls)(*(v[0] for v in controls))
    levels = np.array([[b.inactive_availability, b.active_availability] for b in spec.pools])
    state = state_from_arrays(engine.initial_state(spec), values)
    state, _ = engine.validate_state(spec, state)
    inputs = jax.device_put(
        (state, layout, control, levels, channel_owners(spec)), device_for(backend, 0)
    )

    def field_probe(current, p, c, opening, owners):
        return spatial_junction.field_values(current.ionic, p)

    def rhs_probe(current, p, c, opening, owners):
        held = c._replace(channel=c.channel * kernel.availability(current.pool, opening)[owners])
        return model.rhs(current.ionic, held, p, p.active)

    result = {}
    for name, probe in (("field", field_probe), ("rhs", rhs_probe)):

        def scalar(worlds, *rest, operation=probe):
            return jax.lax.map(lambda current: operation(current, *rest), worlds)

        def parallel(worlds, *rest, operation=probe):
            return candidate.tile_map(
                lambda current: operation(current, *rest), worlds, width=width
            )

        reference = jax.jit(scalar)(*inputs)
        jax.block_until_ready(reference)
        with candidate.candidate(variant, width=width):
            actual = jax.jit(parallel)(*inputs)
            jax.block_until_ready(actual)
        left, right = (jax.tree.map(np.asarray, v)._asdict() for v in (reference, actual))
        save_arrays(directory / f"probe-{label}-{name}-reference.npz", left)
        save_arrays(directory / f"probe-{label}-{name}-candidate.npz", right)
        result[name] = differences(left, right)
    cli.write(directory / f"probe-{label}.json", result)
    return result


def phase(root, directory, backend, record, progress):
    began = time.time()
    spec = replace(parse_spec(record["definition"]), window_ticks=1)
    variant = record["variants"][0]
    width = record["tile_width_by_backend"][backend]
    previous = Path(record["rounding_parent"]["path"])
    initial = flatten(engine.initial_state(spec))
    traces, reports = {}, {}
    cli.write(directory / "trace-definition.json", spec.to_dict())

    def observe(label, trace, window, state):
        first = trace.append(window, flatten(state))
        if first:
            cli.write(directory / "first-divergence.json", first)
            for source, samples in (("reference", trace.reference), ("candidate", trace.samples)):
                for point, index in (("before", window - 1), ("after", window)):
                    save_arrays(directory / f"first-{source}-{point}.npz", samples[index])
        if window == 1 or window % 100 == 0 or first:
            progress(
                phase=backend, step=label, completed_ticks=window, first_divergence=trace.first
            )

    try:
        for label in ("reference", "candidate"):
            reference = traces["reference"].samples if label == "candidate" else None
            trace = TickTrace(initial, spec.ticks, reference=reference)
            traces[label] = trace
            progress(phase=backend, step=label, completed_ticks=0)

            def callback(window, state, name=label, recorder=trace):
                observe(name, recorder, window, state)

            if label == "reference":
                endpoint, report = engine.run(spec, backend=backend, callback=callback)
            else:
                with candidate.candidate(variant, width=width):
                    endpoint, report = engine.run(spec, backend=backend, callback=callback)
            need(len(trace.samples) == spec.ticks + 1, "Incomplete tick trace")
            need(
                not differences(flatten(endpoint), trace.samples[-1])["different_fields"],
                "Trace endpoint differs",
            )
            trace.save(directory / f"{label}-trace.npz")
            cli.write(directory / f"{label}.json", report)
            anchor = (
                previous
                / backend
                / ("reference.npz" if label == "reference" else variant + "/full.npz")
            )
            reports[label] = differences(load_arrays(anchor), flatten(endpoint))
            cli.write(directory / f"{label}-endpoint-comparison.json", reports[label])
        first = traces["candidate"].first
        probe_results = {}
        if first:
            for label, tick in (("before", first["tick"] - 1), ("after", first["tick"])):
                progress(phase=backend, step="isolated_probes_" + label, first_divergence=first)
                probe_results[label] = probes(
                    directory,
                    spec,
                    variant,
                    width,
                    backend,
                    traces["reference"].samples[tick],
                    label,
                )
        reproduced = first is not None and all(not r["different_fields"] for r in reports.values())
        cli.write(
            directory / "result.json",
            {
                "status": "completed",
                "backend": backend,
                "variant": variant,
                "trace_reproduces_prior_screen": reproduced,
                "endpoint_comparisons": reports,
                "first_divergence": first,
                "first_by_field": traces["candidate"].first_by_field,
                "isolated_probes": probe_results,
                "elapsed_seconds": time.time() - began,
                "scientifically_qualified": False,
                "scope": (
                    "One-tick trajectory diagnosis and isolated probes, "
                    "not acceptance or performance"
                ),
            },
        )
    except BaseException:
        for label, trace in traces.items():
            if not (directory / f"{label}-trace.npz").exists():
                trace.save(directory / f"{label}-partial-trace.npz")
        cli.write(
            directory / "failure.json",
            {
                "status": "failed",
                "elapsed_seconds": time.time() - began,
                "traceback": traceback.format_exc(),
            },
        )
        raise
