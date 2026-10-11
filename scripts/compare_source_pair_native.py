"""Audit recorded native steps and compare complete paths at actual source clocks.

Native adaptive Euler has a distinct error budget. Realized event schedules and
their departure from the intended protocol are assessed separately. No Cells or
upstream modules are imported here.
"""

import argparse
import copy
import hashlib
import json
import sys
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.source_pair_native_protocol import native_plan  # noqa: E402
from tests import reference_source_pair_numerics as ref  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def verify_receipt(directory):
    receipt = json.loads((directory / "verification.json").read_text())
    for name, digest in receipt.get("payload_hashes", {}).items():
        if sha(directory / name) != digest:
            raise ValueError(f"Changed payload {directory / name}")
    if "capture_source_hashes" in receipt:
        with zipfile.ZipFile(directory / "capture_sources.zip") as capsule:
            if set(capsule.namelist()) != set(receipt["capture_source_hashes"]):
                raise ValueError("Native source capsule inventory differs")
            for name, digest in receipt["capture_source_hashes"].items():
                if hashlib.sha256(capsule.read(name)).hexdigest() != digest:
                    raise ValueError("Native source capsule changed")
    return receipt


def audit_phase(model, record, phase, arrays):
    times, raw = arrays["start_times"], arrays["raw_start_packets"]
    primary, fixed, derived = ref.eq.PRIMARY_INDEX, ref.eq.CONTEXT_INDEX, ref.eq.DERIVED_INDEX
    n = len(times)
    if n != phase["steps"] or raw.shape != (n, 17, 2) or not n:
        raise ValueError("Invalid native phase shapes")
    shapes = {
        "initial_packet": (17, 2),
        "incoming_packet": (17, 2),
        "final_packet": (17, 2),
        "refreshed_caches": (n, 8, 2),
        "primary_slopes": (n, 6, 2),
        "sample_packets": (len(arrays["sample_times"]), 17, 2),
    }
    if any(arrays[name].shape != shape for name, shape in shapes.items()):
        raise ValueError("Invalid native state/rate/cache/sample shape")
    ref.check_times(arrays["sample_times"], 0, phase["local_accepted_time"])
    if phase["controls"] != model.held[model.slot(phase["actual_start"])]["controls"]:
        raise ValueError("Native control semantics differ")
    if not all(np.isfinite(value).all() for value in arrays.values()):
        raise ValueError("Nonfinite native payload")
    counts, dt = arrays["step_multiples"], record["level"]["time_step"]
    if counts.shape != (n,) or counts.dtype.kind not in "iu" or np.any(counts <= 0):
        raise ValueError("Invalid source step multipliers")
    accepted_local = np.r_[times, phase["local_accepted_time"]]
    np.testing.assert_array_equal(accepted_local, np.r_[0.0, np.cumsum(counts) * dt])
    before = raw[:, primary]
    if phase["index"] == 0:
        np.testing.assert_array_equal(before[0], model.anchor)
    after = np.concatenate((raw[1:, primary], arrays["final_packet"][primary][None]))
    # Native order is rate * integer multiplier * base step, then in-place add.
    expected = before + arrays["primary_slopes"] * counts[:, None, None] * dt
    np.testing.assert_array_equal(after, expected)
    np.testing.assert_array_equal(raw[0], arrays["initial_packet"])
    np.testing.assert_array_equal(raw[:, fixed], np.broadcast_to(model.context, (n, 3, 2)))
    np.testing.assert_array_equal(arrays["final_packet"][fixed], model.context)
    np.testing.assert_array_equal(
        arrays["incoming_packet"][primary], arrays["initial_packet"][primary]
    )
    np.testing.assert_array_equal(arrays["incoming_packet"][fixed], model.context)
    np.testing.assert_array_equal(raw[1:, derived], arrays["refreshed_caches"][:-1])
    np.testing.assert_array_equal(arrays["final_packet"][derived], arrays["refreshed_caches"][-1])
    values = np.zeros((n + 1, ref.SIZE))
    values[:, :12] = np.concatenate((before, arrays["final_packet"][primary][None])).reshape(
        n + 1, 12
    )
    global_times = phase["actual_start"] + accepted_local
    ref.domain(model, values)
    readout = ref.observations(model, global_times[:-1], values[:-1])
    np.testing.assert_allclose(
        readout["packet"][:, derived], arrays["refreshed_caches"], atol=5e-12, rtol=2e-12
    )
    indices = np.unique(
        np.linspace(0, n - 1, min(n, ref.protocol()["native_rhs_witnesses_per_phase"])).astype(int)
    )
    errors = []
    for i in indices:
        slope = model.derivative(values[i], model.slot(global_times[i]))[:12].reshape(6, 2)
        error = np.max(abs(slope - arrays["primary_slopes"][i]))
        np.testing.assert_allclose(slope, arrays["primary_slopes"][i], atol=5e-12, rtol=2e-12)
        errors.append(float(error))
    sample_indices = np.searchsorted(accepted_local, arrays["sample_times"])
    raw_accepted = np.concatenate((raw, arrays["final_packet"][None]))
    np.testing.assert_array_equal(accepted_local[sample_indices], arrays["sample_times"])
    np.testing.assert_array_equal(raw_accepted[sample_indices], arrays["sample_packets"])
    return (
        global_times,
        values,
        {
            "steps": n,
            "rhs_witnesses": len(indices),
            "maximum_rhs_error": max(errors),
            "raw_primary_updates_exact": True,
            "raw_cache_carryover_exact": True,
            "domain": ref.domain(model, values),
        },
    )


def sample_saved(path, times):
    with np.load(path, allow_pickle=False) as data:
        intervals, coefficients = data["polynomial_times"], data["polynomial_coefficients"]
        ref.check_times(times, intervals[0, 0], intervals[-1, 1])
        slot = np.minimum(np.searchsorted(intervals[:, 1], times, side="right"), len(intervals) - 1)
        theta = (times - intervals[slot, 0]) / (intervals[slot, 1] - intervals[slot, 0])
        c = coefficients[slot]
        result = c[:, -1].copy()
        for column in range(c.shape[1] - 2, -1, -1):
            result = result * theta[:, None] + c[:, column]
        return result


def compare_one(path, qualified, output, extension=None):
    output.mkdir()
    record = json.loads((path / "result.json").read_text())
    panel = ref.eq.load_panel()
    cases, levels = native_plan(extension)
    if record["case"] not in cases or record["level"] not in levels:
        raise ValueError("Native case/settings are outside the frozen protocol")
    case = copy.deepcopy(record["case"])
    case["end_time"] = record["phases"][-1]["actual_end"]
    for event, phase in zip(case.get("events", []), record["phases"][1:], strict=True):
        event["time"] = phase["actual_start"]
    model = ref.Model(panel, case)
    all_times, all_values, audits = [], [], []
    previous_final = None
    for phase in record["phases"]:
        payload = path / phase["payload"]
        if sha(payload) != phase["sha256"]:
            raise ValueError("Changed native payload")
        with np.load(payload, allow_pickle=False) as npz:
            arrays = dict(npz)
        if previous_final is not None:
            np.testing.assert_array_equal(arrays["incoming_packet"], previous_final)
        previous_final = arrays["final_packet"]
        times, values, audit = audit_phase(model, record, phase, arrays)
        all_times.append(times if not audits else times[1:])
        all_values.append(values if not audits else values[1:])
        audits.append(audit)
    times, values = np.concatenate(all_times), np.concatenate(all_values)
    sources = {}
    for name, method in (("radau", "Radau"), ("bdf", "BDF")):
        solved = ref.integrate_reference(model, method=method, refinement=0.1)
        polynomials = list(ref.native_polynomials(solved))
        for _, _, c in polynomials:
            ref.check_polynomial(model, c)
        sources[name] = solved.sample(times)
        with (output / f"{name}-realized.npz").open("xb") as handle:
            np.savez_compressed(
                handle,
                polynomial_times=np.array([(a, b) for a, b, _ in polynomials]),
                polynomial_coefficients=np.array(
                    [np.pad(c, ((0, 6 - len(c)), (0, 0))) for _, _, c in polynomials]
                ),
                **{
                    k: v
                    for i, s in enumerate(solved.segments)
                    for k, v in (
                        (f"segment_{i}_times", s.t),
                        (f"segment_{i}_increment_state", s.y.T),
                    )
                },
            )
        write_json(output / f"{name}-solver.json", solved.stats)
    reference_scores = ref.scores(model, times, sources["bdf"], sources["radau"])
    native_scores = ref.scores(
        model,
        times,
        values,
        sources["radau"],
        targets=ref.protocol()["native_error_targets"],
        ledgers=False,
    )
    nominal_model = ref.Model(model.panel, record["case"])
    common = times[times <= nominal_model.end]
    nominal = sample_saved(qualified / record["case"]["id"] / "refined-accepted.npz", common)
    realized = sources["radau"][: len(common)]
    timing_scores = ref.scores(
        nominal_model,
        common,
        realized,
        nominal,
        targets=ref.protocol()["native_error_targets"],
        ledgers=False,
    )
    # At a delayed event, readout controls themselves differ; compare both explicitly.
    actual_readouts = ref.observations(model, common, realized)
    intended_readouts = ref.observations(nominal_model, common, nominal)
    timing_flux = float(
        np.max(
            abs(
                actual_readouts["membrane_and_junction_flux"]
                - intended_readouts["membrane_and_junction_flux"]
            )
        )
    )
    errors = ref.accounting(model, sources["radau"])
    event_error = max(abs(p["actual_start"] - p["requested_start"]) for p in record["phases"])
    endpoint_error = times[-1] - nominal_model.end
    with (output / "comparison.npz").open("xb") as handle:
        np.savez_compressed(
            handle,
            actual_times=times,
            native_primary=values[:, :12],
            reference_state=sources["radau"],
            nominal_common_times=common,
            nominal_reference=nominal,
        )
    result = {
        "status": "pass"
        if max(reference_scores.values()) <= 0.1
        and max(errors.values()) <= ref.protocol()["accounting_atol"]
        else "reference_failure",
        "native_score_pass": max(native_scores.values()) <= 1,
        "native_scores_at_realized_times": native_scores,
        "reference_scores": reference_scores,
        "realized_versus_intended_state_scores": timing_scores,
        "realized_versus_intended_max_flux_difference": timing_flux,
        "event_time_error": event_error,
        "endpoint_overshoot": endpoint_error,
        "native_steps": sum(a["steps"] for a in audits),
        "phase_audits": audits,
        "realized_reference_accounting": errors,
        "case": case,
        "source_result_sha256": sha(path / "result.json"),
    }
    write_json(output / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", required=True, type=Path, action="append")
    parser.add_argument("--qualified", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--native-extension", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output must be new")
    qualified = verify_receipt(args.qualified)
    if qualified["status"] != "pass":
        raise ValueError("Independent qualification missing")
    roots = {}
    for directory in args.native:
        receipt = verify_receipt(directory)
        for name, run in receipt["runs"].items():
            if run["status"] == "pass":
                if sha(directory / name / "result.json") != run["result_sha256"]:
                    raise ValueError("Native receipt mismatch")
                roots[name] = directory / name
    args.output.mkdir(parents=True)
    sources = [
        "scripts/compare_source_pair_native.py",
        "scripts/source_pair_native_protocol.py",
        "tests/reference_source_pair_numerics.py",
        "tests/reference_source_pair.py",
        "tests/reference_emt.py",
        "configs/reference/source_emt_pair_numerics_v1.json",
        "configs/reference/source_emt_pair_panel_v1.json",
    ]
    if args.native_extension is not None:
        sources.append(str(args.native_extension.resolve().relative_to(ROOT)))
    source_hashes = {name: sha(ROOT / name) for name in sources}
    with zipfile.ZipFile(
        args.output / "comparison_sources.zip", "x", compression=zipfile.ZIP_DEFLATED
    ) as z:
        for name in sources:
            z.write(ROOT / name, name)
    results = {}
    cases, levels = native_plan(args.native_extension)
    for case in cases:
        for level in levels:
            name = f"{case['id']}-{level['name']}"
            print(name, flush=True)
            if name not in roots:
                results[name] = {"status": "missing_native"}
                continue
            try:
                results[name] = compare_one(
                    roots[name], args.qualified, args.output / name, args.native_extension
                )
            except (ValueError, AssertionError) as error:
                results[name] = {"status": "comparison_failure", "error": str(error)}
                write_json(args.output / name / "failure.json", results[name])
    accepted = True
    refinement = {}
    for case in cases:
        group = [results[f"{case['id']}-{level['name']}"] for level in levels]
        if any(row["status"] != "pass" for row in group):
            accepted = False
            continue
        error = [max(row["native_scores_at_realized_times"].values()) for row in group]
        ratio_pass = error[-1] <= max(
            ref.protocol()["native_refinement_noise_floor_score"],
            error[0] * ref.protocol()["native_refinement_max_fine_to_coarse_ratio"],
        )
        event_pass = group[-1]["event_time_error"] <= ref.protocol()["native_fine_event_time_atol"]
        timing_pass = max(group[-1]["realized_versus_intended_state_scores"].values()) <= 1
        passed = group[-1]["native_score_pass"] and ratio_pass and event_pass and timing_pass
        refinement[case["id"]] = {
            "scores_coarse_medium_fine": error,
            "pass": passed,
            "refinement_pass": ratio_pass,
            "event_clock_pass": event_pass,
            "timing_state_pass": timing_pass,
        }
        accepted &= passed
    report = {
        "status": "pass" if accepted else "native_qualification_incomplete",
        "runs": results,
        "refinement": refinement,
        "source_hashes": source_hashes,
        "native_receipts": {str(d.resolve()): sha(d / "verification.json") for d in args.native},
        "independent_receipt_sha256": sha(args.qualified / "verification.json"),
        "native_extension": None
        if args.native_extension is None
        else {"path": str(args.native_extension.resolve()), "sha256": sha(args.native_extension)},
        "payload_hashes": {
            str(p.relative_to(args.output)): sha(p) for p in args.output.rglob("*") if p.is_file()
        },
    }
    write_json(args.output / "verification.json", report)
    print(report["status"], flush=True)
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
