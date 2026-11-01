"""Cold/warm NumPy and compiled CPU-JAX checks on a retained physical grid.

The saved dense solution is a comparison, not a replacement for independent
residual checks. The existing stdlib oracle derives exact bound/count stencil
coefficients. No dense binding/inverse, native owner or biological case is made.
"""

import hashlib
import math
import time
from fractions import Fraction
from pathlib import Path

import numpy as np

from cells.processes import rectangular_environment_iterative as iterative
from validation.betse import rectangular_environment_saved as previous

field, reference, runner = previous.field, previous.reference, previous.runner
prior, saved = previous.prior, previous.saved
KIND = "cells.retained_rectangular_iterative_diagnostic@1"
SCOPE = "retained_rectangular_iterative_numpy_jax_cpu"
POLICY = dict(max_iterations=625, rtol=2e-12, atol=0.0)


def declaration(data):
    if (
        type(data) is not dict
        or set(data)
        != {"scope", "baseline", "dense_report", "dense_review", "numpy_pins", "policy"}
        or data["scope"] != SCOPE
        or data["policy"] != POLICY
        or any(type(data["policy"][k]) is not type(v) for k, v in POLICY.items())
    ):
        raise ValueError("Require the explicit retained-grid iterative policy")
    return data


def retained_manifest(data):
    declaration(data)
    prior.verify_pins(
        [data["baseline"], data["dense_report"], data["dense_review"], *data["numpy_pins"]]
    )
    report_pin, report = runner.bound_json(data["dense_report"]["path"])
    review_pin, review = runner.bound_json(data["dense_review"]["path"])
    if (
        report_pin != data["dense_report"]
        or review_pin != data["dense_review"]
        or report["kind"] != previous.KIND
        or report["status"] != "completed_numerical_diagnostic_only"
        or review["report"] != report_pin
        or review["reference"] != report["independent_arithmetic"]
        or data["baseline"] not in report["inputs"]
    ):
        raise ValueError("Dense comparison is not the declared reviewed retained input")
    pins = [
        data["baseline"],
        report_pin,
        review_pin,
        *report["inputs"],
        report["independent_arithmetic"],
        *data["numpy_pins"],
        *[dict(path=a["path"], sha256=a["sha256"]) for a in report["arrays"].values()],
    ]
    prior.verify_pins(pins)
    return report, pins


def preflight(output, inputs):
    pin, data = runner.bound_json(inputs)
    report, pins = retained_manifest(data)
    del report
    output = protected_output(output, data, pins)
    declaration_path = Path(pin["path"])
    if declaration_path.is_relative_to(output) or output.is_relative_to(declaration_path):
        raise ValueError("Output overlaps its input declaration")
    return pin, data


def protected_output(output, data, pins):
    output = runner.retained_output(
        output, data["baseline"]["path"], data["baseline"]["sha256"], data["numpy_pins"]
    )
    # Protect the complete saved dense evidence, including its original inputs.
    for item in pins:
        path = Path(item["path"]).absolute()
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError("Linked retained evidence")
        if output.is_relative_to(path.parent) or path.parent.is_relative_to(output):
            raise ValueError("Output overlaps retained evidence")
    return output


def read_array(item, shape):
    prior.verify_pins([dict(path=item["path"], sha256=item["sha256"])])
    value = np.load(item["path"], allow_pickle=False)
    if (
        value.dtype != np.dtype("<f8")
        or value.shape != tuple(shape)
        or item["shape"] != list(shape)
        or item["dtype"] != value.dtype.str
        or hashlib.sha256(value.tobytes(order="C")).hexdigest() != item["raw_c_sha256"]
        or not np.isfinite(value).all()
    ):
        raise ValueError("Changed or invalid complete saved array")
    prior.verify_pins([dict(path=item["path"], sha256=item["sha256"])])
    return value


def arithmetic(shape, bounds, rhs, potential, dense, tolerance):
    """Independent exact residual/gauge and a rigorous dense-comparison bound.

    For a path of n cells the smallest positive eigenvalue of -L is
    4/dx^2*sin(pi/(2n))^2 >= 4/(n*dx)^2. The rectangular product graph uses
    the smaller axis gap. Cauchy-Schwarz then bounds the zero-mean solution
    difference by sqrt(N)*(||r1||inf+||r2||inf)/gap. A ceiling of sqrt(N)
    makes the stored comparison entirely rational, including the gauge term.
    """
    indices = [(y, x) for y in range(shape[0]) for x in range(shape[1])]
    _, dx, dy, _, _, rows, _ = reference._grid(shape, indices, bounds)
    n = len(rows)
    b, x, d = (
        tuple(map(Fraction.from_float, reference._vector(v, n, label)))
        for v, label in ((rhs, "rhs"), (potential, "potential"), (dense, "dense potential"))
    )
    gap = min(4 / (shape[1] * dx) ** 2, 4 / (shape[0] * dy) ** 2)
    sqrt_upper = math.isqrt(n) + int(math.isqrt(n) ** 2 != n)

    def residual(values):
        return [
            sum((c * values[j] for j, c in row.items()), Fraction(0)) - b[i]
            for i, row in enumerate(rows)
        ]

    rx, rd = residual(x), residual(d)
    rx_max, rd_max = max(map(abs, rx)), max(map(abs, rd))
    mx, md = sum(x) / n, sum(d) / n
    bound = sqrt_upper * (rx_max + rd_max) / gap + abs(mx - md)
    difference = max(abs(a - z) for a, z in zip(x, d, strict=True))
    gauge_limit = 64 * Fraction(1, 2**52) * sum(map(abs, x)) / n
    return dict(
        rhs_exactly_balanced=sum(b) == 0,
        residual_ok=rx_max <= Fraction.from_float(tolerance),
        gauge_ok=abs(mx) <= gauge_limit,
        dense_agreement_bounded=difference <= bound,
        residual_inf=reference._ratio(rx_max),
        dense_residual_inf=reference._ratio(rd_max),
        potential_mean=reference._ratio(mx),
        gauge_limit=reference._ratio(gauge_limit),
        potential_difference_inf=reference._ratio(difference),
        potential_difference_bound=reference._ratio(bound),
        spectral_gap_lower_bound=reference._ratio(gap),
        residual_sum=reference._ratio(sum(rx)),
        basis="Exact Fraction bound/count stencil and input/output binary64 values",
    )


def cpu_jax(grid, policy):
    import jax
    import jaxlib

    if (
        jax.default_backend() != "cpu"
        or not jax.config.x64_enabled
        or jax.config.jax_disable_jit
        or any(d.platform != "cpu" for d in jax.devices())
    ):
        raise ValueError("Require actual compiled CPU JAX with binary64")
    return (
        jax,
        iterative.compile_jax_solver(grid, **policy),
        dict(
            jax=jax.__version__,
            jaxlib=jaxlib.__version__,
            devices=[str(d) for d in jax.devices()],
            x64=True,
            disable_jit=False,
        ),
    )


def compiled_host(jax, result):
    ready = jax.block_until_ready(result)
    if any(v.device.platform != "cpu" for v in ready):
        raise ValueError("Unexpected non-CPU output")
    return iterative.SolveResult(*(np.asarray(v) for v in ready))


def array_evidence(output, name, value):
    """Reuse the established floating writer; retain integer counters as integers."""
    value = np.asarray(value)
    if value.dtype.kind in "fb":
        return saved.array_evidence(np, output, name, value)
    if value.dtype.kind not in "iu" or value.size > 625**2:
        raise ValueError("Unexpected diagnostic counter array")
    path = output / (name + ".npy")
    with path.open("xb") as stream:
        np.save(stream, value, allow_pickle=False)
    reloaded = np.load(path, allow_pickle=False)
    if (
        reloaded.shape != value.shape
        or reloaded.dtype != value.dtype
        or reloaded.tobytes() != value.tobytes()
    ):
        raise ValueError("Counter array roundtrip changed")
    return dict(
        **prior.pin(path),
        shape=list(value.shape),
        dtype=value.dtype.str,
        raw_c_sha256=hashlib.sha256(value.tobytes()).hexdigest(),
    )


def _capture(output, name, result, records):
    records[name] = {}
    for key, value in result._asdict().items():
        records[name][key] = array_evidence(output, name + "_" + key, value)


def run(data, output):
    declaration(data)
    dense_report, pins = retained_manifest(data)
    output = protected_output(output, data, pins)
    output.mkdir(parents=True, exist_ok=False)
    report = dict(
        kind=KIND,
        status="started",
        stage="load_grid",
        policy=data["policy"],
        inputs=pins,
        arrays={},
        results={},
        checks={},
        timings={},
        biological_cases=0,
        native_execution=False,
        physical_tissue_admission=False,
        checkpoint_admission=False,
        gpu_qualification=False,
        inverse_constructions=0,
        dense_bindings=0,
        reference_scope="Shared saved geometry; independent stdlib exact stencil arithmetic",
        timing_scope="Guarded diagnostic including observation; not a throughput benchmark",
    )
    raw, live = {}, {}
    try:
        saved.primitive_bindings(np, data["numpy_pins"])
        observed, arrays, problem = previous.load_grid(
            data["baseline"]["path"], data["baseline"]["sha256"]
        )
        live.update(arrays)
        n = math.prod(observed.shape)
        for name, value in arrays.items():
            old = read_array(dense_report["arrays"][name], value.shape)
            if value.tobytes() != old.tobytes():
                raise ValueError("Saved comparison grid differs from retained original")
        audit = previous.metric.audit(
            observed, boundaries=tuple((s, "flux") for s in previous.metric.SIDES)
        )
        spec = field.spec_from_observation(
            audit, environment_ids=tuple("saved-index:" + str(i) for i in range(n))
        )
        grid = field.bind_metric(spec)
        if (
            list(grid.shape) != dense_report["grid"]["shape"]
            or list(grid.bounds_m) != dense_report["grid"]["bounds_m"]
            or list(grid.spacing_xy_m) != dense_report["grid"]["spacing_xy_m"]
            or grid.coordinates_m.tobytes() != arrays["retained_coordinates"].tobytes()
        ):
            raise ValueError("Metric-only binding changed the retained physical grid")
        probes = previous.probes(grid.shape, problem["indices"])
        rhs = read_array(dense_report["arrays"]["rhs"], (len(probes), n))
        dense = read_array(dense_report["arrays"]["potential"], rhs.shape)
        live.update(rhs=rhs, dense_potential=dense)
        if (
            list(probes) != dense_report["probes"]
            or rhs.tobytes() != np.stack(list(probes.values())).tobytes()
        ):
            raise ValueError("Changed declared original probe values/order")
        report["grid"] = dict(
            shape=grid.shape,
            bounds_m=grid.bounds_m,
            spacing_xy_m=grid.spacing_xy_m,
            identity=grid.identity,
        )
        report["probes"] = list(probes)
        for name, value in dict(**arrays, rhs=rhs, dense_potential=dense).items():
            report["arrays"][name] = saved.array_evidence(np, output, name, value)
        before = rhs.tobytes()
        thresholds = np.array(
            [
                max(data["policy"]["atol"], data["policy"]["rtol"] * max(map(abs, row.tolist())))
                for row in rhs
            ]
        )
        jax, solver, report["jax_runtime"] = cpu_jax(grid, data["policy"])
        for backend in ("numpy", "jax"):
            initial = None
            for mode in ("cold", "warm"):
                name = backend + "_" + mode
                report["stage"] = name
                if initial is not None:
                    live[name + "_initial"] = initial
                initial_bits = None if initial is None else initial.tobytes()
                start = time.perf_counter()
                if backend == "numpy":
                    result = iterative.solve(rhs, grid, initial_potential=initial, **data["policy"])
                    raw[name] = result
                else:
                    args = (rhs,) if initial is None else (rhs, initial)
                    lowered = solver.lower(*args)
                    ir = str(lowered.compiler_ir(dialect="stablehlo"))
                    if "stablehlo.while" not in ir or "callback" in ir:
                        raise ValueError("Expected compiled iteration loop without callbacks")
                    path = output / (name + ".stablehlo.txt")
                    path.write_text(ir)
                    report[name + "_compiled_ir"] = prior.pin(path)
                    executable = lowered.compile()
                    raw[name] = executable(*args)
                    result = compiled_host(jax, raw[name])
                    raw[name] = result
                report["timings"][name] = time.perf_counter() - start
                _capture(output, name, result, report["results"])
                if not np.array_equal(result.tolerance, thresholds):
                    raise ValueError("Solver tolerance differs from original forcing/policy")
                if initial is not None and initial.tobytes() != initial_bits:
                    raise ValueError("Solver changed the retained warm-start input")
                report["stage"] = name + "_independent_arithmetic"
                checks = report["checks"][name] = []
                for i, probe in enumerate(probes):
                    check = arithmetic(
                        grid.shape,
                        grid.bounds_m,
                        rhs[i].tolist(),
                        result.potential[i].tolist(),
                        dense[i].tolist(),
                        float(thresholds[i]),
                    )
                    check["probe"] = probe
                    checks.append(check)
                initial = result.potential
                if rhs.tobytes() != before:
                    raise ValueError("Solver changed original forcing")
        report["stage"] = "criteria"
        expected = np.array([True, True, True, True, False])
        accepted = True
        for name, result in raw.items():
            accepted &= bool(np.array_equal(result.converged, expected))
            accepted &= bool(np.array_equal(result.rhs_compatible, expected))
            accepted &= bool(np.all(result.finite_result) and not np.any(result.breakdown))
            accepted &= all(
                c["rhs_exactly_balanced"]
                and c["residual_ok"]
                and c["gauge_ok"]
                and c["dense_agreement_bounded"]
                for c in report["checks"][name][:-1]
            )
            accepted &= not report["checks"][name][-1]["rhs_exactly_balanced"]
            if name.endswith("warm"):
                accepted &= bool(np.all(result.iterations == 0))
        report["criteria_passed"] = bool(accepted)
        report["work"] = dict(
            metric_bindings=1,
            batch_solves=4,
            probe_rows=5,
            new_independent_cases=0,
            warm_rows_reuse_cold=True,
        )
        prior.verify_pins(pins)
        if not accepted:
            raise ArithmeticError("Declared retained-grid iterative diagnostic criteria failed")
        report.update(status="completed_bounded_iterative_diagnostic", stage="complete")
        prior.write(output / "report.json", report)
        return report
    except BaseException as error:
        error.rectangular_raw_returns = raw
        error.rectangular_live_inputs = live
        report.update(
            status="failed",
            error=prior.exception_record(error),
            failed_return_capture={},
            failed_input_capture={},
        )
        # Publish primary metadata before any device synchronization or array
        # serialization that can itself fail or outlive the resource guard.
        try:
            prior.write(output / "primary-failure.json", report)
        except BaseException as capture:
            error.rectangular_primary_persistence_error = capture
        for name, value in live.items():
            try:
                report["failed_input_capture"][name] = array_evidence(
                    output, "failed_input_" + name, value
                )
            except BaseException as capture:
                report["failed_input_capture"][name] = dict(error=prior.exception_record(capture))
        for name, result in raw.items():
            for key, value in result._asdict().items():
                try:
                    report["failed_return_capture"][name + "." + key] = array_evidence(
                        output, "failed_" + name + "_" + key, value
                    )
                except BaseException as capture:
                    report["failed_return_capture"][name + "." + key] = dict(
                        error=prior.exception_record(capture)
                    )
        try:
            prior.write(output / "failure.json", report)
        except BaseException as capture:
            error.rectangular_persistence_error = capture
        raise
