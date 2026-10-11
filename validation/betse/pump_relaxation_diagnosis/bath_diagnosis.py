"""Read-only error decomposition of the saved pump-only shared-bath updates.

This is an arithmetic replay of recorded fluxes, NOT a new simulator trajectory,
reference integration, replacement native observable, or changed acceptance rule.
"""

import math
import sys
from decimal import Decimal, localcontext

import diagnose_job as job
import numpy as np
import refined_recording as recording

c = job.c
SPECIES = ("Na", "K", "Cl")


def dec(value):
    return Decimal.from_float(float(value))


def coordinate(index):
    if index < 21:
        return f"cell_{index // 3}/{SPECIES[index % 3]}"
    if index < 24:
        return "bath/" + SPECIES[index - 21]
    if index < 45:
        return f"leak/cell_{(index - 24) // 3}/{SPECIES[(index - 24) % 3]}"
    return f"pump_cycles/cell_{index - 45}"


def common_reference(name="dop853_tight"):
    reference = c.read(job.REFERENCE / f"reference/pump_only/{name}/result.json", None)
    times = c.read(job.REFERENCE / "registration.json", None)["protocol"]["common_times_s"]
    states = []
    for t in times:
        i = min(range(len(reference["times_s"])), key=lambda i: abs(reference["times_s"][i] - t))
        c.need(abs(reference["times_s"][i] - t) < 1e-15, "Reference common grid")
        states.append(reference["states"][i])
    return times, states


def diagnostic_summary():
    times, target = common_reference()
    rows = []
    for index, step in enumerate(job.STEPS):
        saved = c.read(job.CAPTURE / f"native/pump_only/{index}/comparison.json", None)
        points = saved["common_points"]["states"]
        c.need(saved["dt_s"] == step and len(points) == len(times) == 41, "Saved row/grid")
        fields = []
        for k in range(52):
            error, i = max(
                (abs(a[k] - b[k]), i) for i, (a, b) in enumerate(zip(points, target, strict=True))
            )
            fields.append(
                dict(
                    coordinate=coordinate(k),
                    index=k,
                    time_s=times[i],
                    error_fmol=error,
                    signed_error_fmol=points[i][k] - target[i][k],
                )
            )
        c.need(
            max(v["error_fmol"] for v in fields) == saved["reference_errors"]["amount"],
            "Saved amount maximum",
        )
        ledger_errors, storage_errors, decomposition = [], [], []
        for t, observed, expected in zip(times, points, target, strict=True):
            cycles = math.fsum(observed[45:52])
            ledger = [3 * cycles, -2 * cycles, 0.0]
            reference_error = [a - b for a, b in zip(ledger, expected[21:24], strict=True)]
            storage_error = [a - b for a, b in zip(observed[21:24], ledger, strict=True)]
            ledger_errors.append(reference_error)
            storage_errors.append(storage_error)
            decomposition.append(
                dict(
                    time_s=t,
                    stored_bath_fmol=observed[21:24],
                    pump_integral_bath_fmol=ledger,
                    stored_minus_integral_fmol=storage_error,
                    integral_minus_reference_fmol=reference_error,
                )
            )
        rows.append(
            dict(
                dt_s=step,
                largest_coordinates=sorted(fields, key=lambda v: v["error_fmol"], reverse=True)[:8],
                stored_amount_error_fmol=saved["reference_errors"]["amount"],
                pump_integral_bath_error_fmol=max(abs(x) for v in ledger_errors for x in v),
                storage_minus_integral_fmol=max(abs(x) for v in storage_errors for x in v),
                common_decomposition=decomposition,
            )
        )
    agreement = {}
    for name in ("dop853_base", "radau_check"):
        _, other = common_reference(name)
        agreement[name] = max(
            abs(x - y)
            for a, b in zip(other, target, strict=True)
            for x, y in zip(a[:52], b[:52], strict=True)
        )
    return dict(
        rows=rows,
        reference_amount_agreement_fmol=agreement,
        diagnostic_only=True,
        original_convergence_verdict_changed=False,
    )


def validate_header(header, step):
    c.need(header["kind"] == "native_header", "Missing header")
    row = header["row"]
    c.need(
        row["id"] == "pump_only"
        and row["mode"] == "observed"
        and row["dt_s"] == step
        and row["steps"] == round(0.01 / step),
        "Replay row identity",
    )
    g, settings = row["geometry"], row["settings"]
    c.need(
        g["cell_count"] == 7
        and g["membrane_count"] == 30
        and g["effective_bath_volume_m3"] == 30 * g["configured_bath_volume_m3"]
        and g["configured_bath_volume_m3"] > 0
        and not settings["is_ecm"]
        and settings["cluster_open"]
        and settings["gj_surface"] == 0,
        "Supported shared-bath geometry/settings",
    )
    return row


def replay_step(header, record):
    """Exact binary64 local replay plus 80-digit arithmetic error components.

    The Decimal components treat recorded binary64 operands exactly. Their sum
    separates the per-face addition and subsequent NumPy mean from the tiny
    flux/division/multiplication rounding. No compensated state feeds back into
    the flux, voltage, or source simulator.
    """
    c.need(record["kind"] == "native_step", "Expected native step")
    row, raw = header["row"], record["raw_step"]
    g, dt = row["geometry"], row["dt_s"]
    physical = raw["before"]["physical"]
    after = record["step"]["after_voltage"]["physical"]
    ordinary = record["step"]["before_ordinary"]["physical"]
    c.need(
        raw["before"]["rho_pump"] == 1.0 and raw["before"]["pump_block"] == 1.0,
        "Pump-only control changed",
    )
    calls = raw["calls"]
    c.need(
        [v["function"] for v in calls] == ["pumpNaKATP"] + ["electroflux"] * 6
        and [v["species_index"] for v in calls[1:]] == list(range(6)),
        "Recorded call coverage",
    )
    c.need(
        not np.any(np.asarray(ordinary["junction_density_mol_per_m2_s"])),
        "Unexpected junction flux",
    )
    c.need(
        all(not np.any(np.asarray(call["returned"])) for call in calls[1:]),
        "Pump-only leak is nonzero",
    )
    areas = np.asarray(g["membrane_areas_m2"], dtype=np.float64)
    volume = g["configured_bath_volume_m3"]
    c.need(areas.shape == (30,) and np.all(np.isfinite(areas)) and np.all(areas > 0), "Face areas")
    results = []
    with localcontext() as context:
        context.prec = job.PRECISION
        n, factor = Decimal(30), Decimal(30) * dec(volume) * Decimal(10) ** 15
        for species in range(3):
            face = np.zeros(30, dtype=np.float64)
            if species < 2:
                face += raw["before"]["rho_pump"] * np.asarray(calls[0]["returned"][species])
            before = np.asarray(physical["outside_mM"][species], dtype=np.float64)
            actual = np.asarray(after["outside_mM"][species], dtype=np.float64)
            c.need(
                before.shape == actual.shape == (30,)
                and np.all(np.isfinite(before))
                and np.all(before > 0)
                and np.all(before == before[0]),
                "Uniform finite bath",
            )
            c.need(
                np.array_equal(
                    face, np.asarray(ordinary["ordinary_density_mol_per_m2_s"][species])
                ),
                "Applied face flux differs from recorded pump return",
            )
            # Preserve source operation order: update_Co's non-ECM branch.
            delta = -face * (areas / volume)
            addition = before + delta * dt
            value = float(addition.mean())
            replay = np.full(30, value, dtype=np.float64)
            c.need(
                np.array_equal(replay.view(np.uint64), actual.view(np.uint64)),
                "Native shared-bath replay differs in float64 bits",
            )
            exact_flux_increment = (
                -sum(dec(f) * dec(a) for f, a in zip(face, areas, strict=True))
                * dec(dt)
                / (n * dec(volume))
            )
            computed_increment = sum(map(dec, delta * dt)) / n
            exact_added_mean = sum(map(dec, addition)) / n
            addition_error = exact_added_mean - dec(before[0]) - computed_increment
            mixing_error = dec(value) - exact_added_mean
            product_error = computed_increment - exact_flux_increment
            local_error = dec(value) - dec(before[0]) - exact_flux_increment
            c.need(
                abs(local_error - addition_error - mixing_error - product_error) < Decimal("1e-70"),
                "Arithmetic decomposition failed",
            )
            results.append(
                dict(
                    before_mM=float(before[0]),
                    after_mM=value,
                    exact_flux_fmol=exact_flux_increment * factor,
                    storage_error_fmol=local_error * factor,
                    addition_error_fmol=addition_error * factor,
                    mixing_error_fmol=mixing_error * factor,
                    product_error_fmol=product_error * factor,
                )
            )
    return results


def stream_row(index, write, output):
    step = job.STEPS[index]
    source = job.CAPTURE / f"native/pump_only/{index}/stream"
    stream = recording.stream(source)
    times, reference = common_reference()
    saved = c.read(job.CAPTURE / f"native/pump_only/{index}/comparison.json", None)
    selected = {round(t / step): i for i, t in enumerate(times)}
    fields = (
        "exact_flux_fmol",
        "storage_error_fmol",
        "addition_error_fmol",
        "mixing_error_fmol",
        "product_error_fmol",
    )
    totals = [{k: Decimal(0) for k in fields} for _ in range(3)]
    maxima = dict.fromkeys(fields[1:], 0.0)
    observations, header, previous, steps, histories, footer = [], None, None, 0, 0, False
    residual_max = 0.0
    with localcontext() as context:
        context.prec = job.PRECISION
        for record in stream:
            kind = record["kind"]
            if header is None:
                validate_header(record, step)
                header = record
                previous = [
                    float(v[0]) for v in header["trace"]["initial"]["physical"]["outside_mM"][:3]
                ]
                initial = list(previous)
                continue
            c.need(not footer, "Record after footer")
            if kind == "native_step":
                c.need(
                    record["index"]
                    == record["raw_step"]["index"]
                    == record["step"]["index"]
                    == steps,
                    "Step order",
                )
                c.need(
                    record["step"]["before_elapsed_s"] == steps * step
                    and record["step"]["after_elapsed_s"] == (steps + 1) * step,
                    "Physical clock",
                )
                result = replay_step(header, record)
                c.need([v["before_mM"] for v in result] == previous, "Disconnected bath updates")
                previous = [v["after_mM"] for v in result]
                for s, row in enumerate(result):
                    for field in fields:
                        totals[s][field] += row[field]
                    for field in maxima:
                        maxima[field] = max(maxima[field], abs(float(totals[s][field])))
                steps += 1
                if steps in selected:
                    i = selected[steps]
                    g = header["row"]["geometry"]
                    exact_volume_fmol = (
                        Decimal(30) * dec(g["configured_bath_volume_m3"]) * Decimal(10) ** 15
                    )
                    actual = [
                        (dec(a) - dec(b)) * exact_volume_fmol
                        for a, b in zip(previous, initial, strict=True)
                    ]
                    closure = [
                        actual[s] - totals[s]["exact_flux_fmol"] - totals[s]["storage_error_fmol"]
                        for s in range(3)
                    ]
                    residual_max = max(residual_max, max(abs(float(v)) for v in closure))
                    c.need(
                        max(abs(v) for v in closure) < Decimal("1e-60"),
                        "Cumulative replay decomposition",
                    )
                    # Original amount mapping stays untouched, including its
                    # binary64 effective-volume and unit-conversion order.
                    mapped = [
                        (a - b) * g["effective_bath_volume_m3"] * 1e15
                        for a, b in zip(previous, initial, strict=True)
                    ]
                    c.need(
                        mapped == saved["common_points"]["states"][i][21:24],
                        "Saved common-point link",
                    )
                    observations.append(
                        dict(
                            time_s=times[i],
                            step=steps,
                            stored_bath_fmol=mapped,
                            transfer_only_diagnostic_fmol=[
                                float(v["exact_flux_fmol"]) for v in totals
                            ],
                            transfer_minus_reference_fmol=[
                                float(totals[s]["exact_flux_fmol"]) - reference[i][21 + s]
                                for s in range(3)
                            ],
                            components=[{k: float(v) for k, v in row.items()} for row in totals],
                            output_mapping_roundoff_fmol=[
                                float(dec(mapped[s]) - actual[s]) for s in range(3)
                            ],
                        )
                    )
            elif kind == "native_history":
                c.need(record["index"] == histories and histories + 2 == steps, "History order")
                histories += 1
            elif kind == "native_footer":
                footer = True
                c.need(
                    [v[0] for v in record["row"]["final"]["physical"]["outside_mM"][:3]]
                    == previous,
                    "Footer endpoint",
                )
            else:
                raise ValueError("Unexpected stream record")
        c.need(
            stream.complete
            and footer
            and steps == round(0.01 / step)
            and histories == steps - 1
            and len(observations) == 40,
            "Complete replay coverage",
        )
    result = dict(
        dt_s=step,
        steps=steps,
        histories=histories,
        exact_bath_scalar_matches=steps * 90,
        decimal_precision=job.PRECISION,
        decimal_decomposition_max_residual_fmol=residual_max,
        max_cumulative_components_fmol=maxima,
        common_observations=observations,
        endpoint_components=[{k: float(v) for k, v in row.items()} for row in totals],
        transfer_bath_reference_error_fmol=max(
            abs(v) for row in observations for v in row["transfer_minus_reference_fmol"]
        ),
        output_mapping_roundoff_max_fmol=max(
            abs(v) for row in observations for v in row["output_mapping_roundoff_fmol"]
        ),
        stream_metrics=stream.metrics,
        diagnostic_only=True,
    )
    write(output / f"row-{index}.json", result)
    print("Saved pump-only bath replay completed: " + str(step), flush=True)
    return {k: v for k, v in result.items() if k != "common_observations"}


def run(output, write):
    summary = diagnostic_summary()
    write(output / "coordinates.json", summary)
    rows = [stream_row(i, write, output) for i in range(3)]
    c.need(
        not any(
            n in ("cells", "betse", "jax") or n.startswith(("cells.", "betse.", "jax."))
            for n in sys.modules
        ),
        "Diagnosis imported a simulator",
    )
    return dict(
        status="saved_bath_arithmetic_replayed",
        rows=rows,
        exact_bath_scalar_matches=sum(r["exact_bath_scalar_matches"] for r in rows),
        recorded_updates=sum(r["steps"] for r in rows),
        original_amount_errors_fmol=[r["stored_amount_error_fmol"] for r in summary["rows"]],
        transfer_only_diagnostic_errors_fmol=[
            r["transfer_bath_reference_error_fmol"] for r in rows
        ],
        new_simulator_runs=0,
        new_reference_integrations=0,
        physics_changed=False,
        scientific_tolerances_changed=False,
        original_convergence_verdict_changed=False,
        matched_10ms_qualified=False,
        automatic_followup=False,
        limitation=(
            "Recorded flux replay has no feedback and cannot qualify a different integrator "
            "or repair the stored native trajectory."
        ),
    )
