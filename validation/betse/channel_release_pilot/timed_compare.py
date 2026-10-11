"""Reference/contact/refinement checks and complete restart/checkpoint validation."""

import feedback_compare as compare
import history_math
import paired_compare
import piecewise_check
import timed_cells_check as cells_check
import timed_context as ctx
import timed_native_check as native_check

c, io = ctx.c, ctx.io


def reference_view(r, history):
    registration = c.read(ctx.CAPTURE / "registration.json")
    gate = c.read(ctx.CAPTURE / "reference-gate.json")
    result = {"reference_solutions": {}, "measured_reference_disagreement": {}}
    for condition in r["plan"]["conditions"]:
        path = (
            ctx.CAPTURE
            / "reference"
            / history
            / condition
            / registration["inputs"]["reference"]["primary"]
            / "result.json.gz"
        )
        row = io.read_compressed(path)
        result["reference_solutions"][condition] = {
            "times_s": row["sample_times_s"],
            "states": row["sample_states"],
            "readouts": row["readouts"],
            "switches": row["switches"],
        }
        result["measured_reference_disagreement"][condition] = gate[
            "measured_reference_disagreement"
        ][history + "/" + condition]
    return result


def check_side_probes(view, output, aggregate):
    c.require(
        set(aggregate["side_probes"]) == set(view["cells_definitions"]), "Cells side coverage"
    )
    ledger = io.Ledger(
        {
            "gate_rate_per_s": 2e-9,
            "flux_fmol_per_s": 2e-9,
            "power_pJ_per_s": 2e-7,
            "permeability_m_per_s": 2e-19,
        },
        2e-11,
        output / "cells-side-failures.jsonl",
    )
    points = {}
    for key, path in aggregate["side_probes"].items():
        record = io.read_compressed(output / aggregate["records"][key])
        probes = io.read_compressed(output / path)
        definition = view["cells_definitions"][key]
        condition = key.split("/")[0]
        p = view["reference_parameters"][condition]
        c.require(
            [row["time_s"] for row in probes]
            == [view["protocol"]["duration_s"] / 4, view["protocol"]["duration_s"] / 2],
            "Cells side clock",
        )
        sides = {"left": [], "right": []}
        for row in probes:
            index = round(row["time_s"] / definition["execution"]["dt"])
            state = {k: v["values"][index] for k, v in record["history"].items()}
            c.require(row["state"] == state, "Cells side probe did not use complete carried state")
            q, m, h, energy = (
                state["amount_increment"][1][:7],
                state["gate"][0][:7],
                state["gate"][1][:7],
                state["dissipated_energy_pJ"][:7],
            )
            for side in ("left", "right"):
                u = ctx.availability(view["schedules"][condition], row["time_s"], side)
                actual = row[side]
                c.require(actual["availability"] == u, "Cells wrong switch side")
                rates = history_math.ready.vector_field(
                    p | {"Pmax_m_per_s": [u * v for v in p["Pmax_m_per_s"]]}, q, m, h
                )
                _, full = history_math.expected_arrays(definition, rates)
                c.require(set(actual["rhs"]) == set(full), "Incomplete side RHS")
                for name, expected in full.items():
                    unit = (
                        "gate_rate_per_s"
                        if name == "gate"
                        else "power_pJ_per_s"
                        if "energy" in name
                        else "flux_fmol_per_s"
                    )
                    ledger.compare(
                        f"{key}/{row['time_s']}/{side}/rhs/{name}",
                        actual["rhs"][name],
                        expected,
                        unit,
                    )
                    if u == 0 and name != "gate":
                        compare.zero(actual["rhs"][name])
                for name, field in (
                    ("flux_fmol_per_s", "inward_K_fmol_per_s"),
                    ("permeability_m_per_s", "permeability_m_per_s"),
                    ("power_pJ_per_s", "dissipation_pJ_per_s"),
                ):
                    expected = rates[field] + [0.0] * (
                        definition["execution"]["channel_capacity"] - 7
                    )
                    ledger.compare(
                        f"{key}/{row['time_s']}/{side}/{name}", actual[name], expected, name
                    )
                point = piecewise_check.readout(p, q + m + h + energy, u)
                # Use actual production constitutive outputs for contact, not the reconstruction.
                point.update(
                    flux_fmol_per_s=actual["flux_fmol_per_s"][:7],
                    permeability_m_per_s=actual["permeability_m_per_s"][:7],
                    inward_current_A=[p["F"] * 1e-15 * v for v in actual["flux_fmol_per_s"][:7]],
                )
                sides[side].append(point)
        points[key] = sides
    return {
        "status": "pass" if ledger.failed == 0 else "fail",
        "checks": ledger.summary(),
        "points": points,
    }


def reference_sides(view, condition, reference):
    row = reference["reference_solutions"][condition]
    result = {"left": [], "right": []}
    for time_s in (view["protocol"]["duration_s"] / 4, view["protocol"]["duration_s"] / 2):
        index = row["times_s"].index(time_s)
        for side in result:
            u = ctx.availability(view["schedules"][condition], time_s, side)
            result[side].append(
                piecewise_check.readout(
                    view["reference_parameters"][condition], row["states"][index], u
                )
            )
    return result


def check(r, output, native, cells):
    a = native_check.check(r, output, native)
    io.write_compressed(output / "native-accounting.json.gz", a)
    results, failures, coarse, checkpoints = {}, 0, 0, 0
    arrays = restarts = backends = 0
    references, paired_results = {}, {}
    source_hashes = c.read(
        ctx.design.audit.CAPTURE
        / "a/cells/active_channel/jax_jit/dt_5e-05/final-checkpoint/manifest.json"
    )["source_hashes"]
    for history, view in r["views"].items():
        local = output / history
        b = cells_check.cells_checks(view, local, cells["by_history"][history])
        sides = check_side_probes(view, local, cells["by_history"][history])
        io.write_compressed(local / "cells-accounting.json.gz", b)
        io.write_compressed(local / "cells-sides.json.gz", sides)
        reference = reference_view(r, history)
        references[history] = reference
        paired_results[history] = {"native": a["by_history"][history], "cells": b}
        dynamic = compare.dynamic_checks(view, local, reference, a["by_history"][history], b)
        side_results = {}
        for condition in r["plan"]["conditions"]:
            oracle = reference_sides(view, condition, reference)
            for engine, step, backend in (
                ("native", r["plan"]["native_steps_s"][-1], None),
                ("cells", r["plan"]["cells_steps_s"][-1], "jax_jit"),
            ):
                key = ctx.key(condition, step, backend)
                points = (
                    a["by_history"][history]["sides"][key]
                    if engine == "native"
                    else sides["points"][key]
                )
                for side in ("left", "right"):
                    name = engine + "/" + condition + "/" + side
                    side_results[name] = compare.compare_points(
                        name,
                        points[side],
                        oracle[side],
                        view["protocol"],
                        local,
                        energy=engine == "cells",
                    )
        stored = cells_check.checkpoints(view, local, cells["by_history"][history], source_hashes)
        checkpoints += stored["checkpoints"]
        arrays += stored["checkpoint_arrays"]
        restarts += len(b["restarts"])
        backends += len(b["backends"])
        counts = (
            dynamic["required_failed_comparisons"]
            + dynamic["failed_refinement_groups"]
            + b["failed_comparisons"]
            + sides["checks"]["failed_comparisons"]
            + sum(v["failed_comparisons"] for v in side_results.values())
        )
        coarse += dynamic["coarse_diagnostic_failures"]
        # Both engines must treat extra no-op switch metadata as numerically inert.
        no_ops = {}
        for step in r["plan"]["cells_steps_s"]:
            first, last = (b["points"][ctx.key(v, step, "jax_jit")] for v in ("baseline", "no_op"))
            no_op = compare.compare_points(
                "no_op/" + str(step), first, last, view["protocol"], local
            )
            no_ops[str(step)] = no_op
            counts += no_op["failed_comparisons"]
        for step, backend in [(s, "jax_jit") for s in r["plan"]["cells_steps_s"]] + [
            (r["plan"]["cells_steps_s"][0], "jax_eager")
        ]:
            left, right = (
                io.read_compressed(
                    local / cells["by_history"][history]["records"][ctx.key(v, step, backend)]
                )
                for v in ("baseline", "no_op")
            )
            c.require(
                left["history"] == right["history"]
                and left["observations"] == right["observations"],
                "No-op schedule changed complete Cells history/readouts",
            )
        failures += counts
        results[history] = {
            "dynamic": dynamic,
            "sides": side_results,
            "checkpoints": stored,
            "no_op": no_ops,
            "required_failures": counts,
        }
        io.write(local / "trajectory-comparison.json", results[history])
    protocol = c.read(paired_compare.ctx.PROTOCOL) | {
        "variants": r["plan"]["conditions"],
        "common_times_s": r["plan"]["common_times_s"],
    }
    contrasts = paired_compare.histories(
        r | {"protocol": protocol}, output, references, paired_results
    )
    io.write(output / "history-contrasts.json", contrasts)
    failures += contrasts["failed_comparisons"]
    c.require(
        checkpoints == r["plan"]["cells_trajectories"] + 2 * r["plan"]["cells_resumed_segments"]
        and arrays == 54 * checkpoints
        and restarts == r["plan"]["cells_resumed_segments"]
        and backends == len(r["plan"]["histories"]) * len(r["plan"]["conditions"]),
        "Timed checkpoint/restart/backend coverage",
    )
    return {
        "status": "timed_release_capture_pass_pending_audit"
        if failures == a["failed_comparisons"] == 0
        else "timed_release_capture_failed_not_qualified",
        "native_boundary_comparisons": a["comparisons"],
        "native_boundary_failures": a["failed_comparisons"],
        "required_comparison_failures": failures,
        "history_contrast_failures": contrasts["failed_comparisons"],
        "coarse_diagnostic_failures": coarse,
        "checkpoints": checkpoints,
        "checkpoint_arrays": arrays,
        "observer_pairs": a["observer_pairs"],
        "restart_pairs": restarts,
        "backend_pairs": backends,
        "reference_review_closed": True,
        "independent_capture_audit_complete": False,
        "release_response_qualified": False,
        "biology_validated": False,
        "gpu_tested": False,
    }
