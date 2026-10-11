"""BIO-002: frozen, descriptive endpoint calculation; no Cells trajectory integration."""

import argparse
import csv
import hashlib
import io
import json
import math
import platform
import sys
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import check_biological_benchmark as data_check  # noqa: E402
from tests import reference_conditioned_voltage as ref  # noqa: E402

PLAN = ROOT / "configs/reference/bio002_conditioned_voltage_v1.json"
PLAN_SHA256 = "d5f24b40d80083f2b2b4694aee67a1fe21089e578203235d12520ce2ee2982ba"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_inputs(plan_path=PLAN, data_directory=None):
    if sha(plan_path) != PLAN_SHA256:
        raise ValueError("Frozen BIO-002 protocol changed")
    plan = json.loads(Path(plan_path).read_text())
    directory = ROOT / plan["dataset_directory"] if data_directory is None else Path(data_directory)
    for name, expected in plan["dataset_sha256"].items():
        if sha(directory / name) != expected:
            raise ValueError(f"Frozen BIO-001 dataset changed: {name}")
    integrity = data_check.verify(directory)
    conditions = data_check.read_rows(
        directory / "conditions.csv", ("condition_id", *data_check.RECIPE_COLUMNS, "role")
    )
    endpoints = data_check.read_rows(
        directory / "voltage_endpoints.csv", data_check.ENDPOINT_COLUMNS
    )
    ids = plan["split"]["fit"] + plan["split"]["evaluation"]
    readings = {}
    for identity in ids:
        row, endpoint = conditions[identity], endpoints[identity]
        na, k, cl = (float(row[f"figure2b_{ion}_mM"]) for ion in ("Na", "K", "Cl"))
        ca, mg = float(row["CaCl2_mM"]), float(row["MgCl2_mM"])
        actual = (na + k, cl, ca, mg, 2 * ca + 2 * mg)
        expected = tuple(
            plan["boundary"][key]
            for key in (
                "external_Na_plus_K_mM",
                "external_Cl_mM",
                "external_Ca_mM",
                "external_Mg_mM",
                "background_positive_charge_mM_equivalents",
            )
        )
        if not all(
            math.isclose(a, b, rel_tol=0, abs_tol=1e-9)
            for a, b in zip(actual, expected, strict=True)
        ):
            raise ValueError("Condition is not in the fixed-boundary series")
        if not math.isclose(na + k + 2 * ca + 2 * mg, cl, rel_tol=0, abs_tol=1e-9):
            raise ValueError("Background-ion charge accounting failed")
        readings[identity] = ref.Reading(
            identity,
            k,
            float(endpoint["mean_voltage_mV_approx"]),
            float(endpoint["digitization_bound_mV"]),
        )
    return plan, readings, integrity


def decimal_voltage(first, second, target_potassium_mM, temperature_K):
    """Independent weighted-exponential calculation, not the a/b implementation."""
    with localcontext() as context:
        context.prec = 60

        def d(value):
            return Decimal(str(value))

        thermal = (
            Decimal(1000) * Decimal("1.380649e-23") * d(temperature_K) / Decimal("1.602176634e-19")
        )
        weight = (d(target_potassium_mM) - d(first.potassium_mM)) / (
            d(second.potassium_mM) - d(first.potassium_mM)
        )
        z1, z2 = (d(first.voltage_mV) / thermal).exp(), (d(second.voltage_mV) / thermal).exp()
        argument = (1 - weight) * z1 + weight * z2
        if argument <= 0:
            raise ValueError("Decimal reference has nonpositive logarithm argument")
        return float(thermal * argument.ln())


def numerical_crosscheck(prediction, first, second, temperature_K, tolerance_mV):
    target = prediction["target_potassium_mM"]
    checks = []
    direct = decimal_voltage(first, second, target, temperature_K)
    checks.append(abs(prediction["prediction_mV"] - direct))
    checks.append(abs(prediction["change_from_first_fit_mV"] - (direct - first.voltage_mV)))
    for corner, (p1, p2) in zip(
        prediction["reading_corners"], ref.reading_corners(first, second), strict=True
    ):
        direct = decimal_voltage(p1, p2, target, temperature_K)
        checks.append(abs(corner["prediction_mV"] - direct))
        checks.append(abs(corner["change_from_first_fit_mV"] - (direct - p1.voltage_mV)))
    curve = ref.Curve(
        **{**prediction["curve"], "dose_domain_mM": tuple(prediction["curve"]["dose_domain_mM"])}
    )
    for point in (first, second):
        checks.append(abs(curve.voltage_at(point.potassium_mM) - point.voltage_mV))
    if not all(math.isfinite(error) and error <= tolerance_mV for error in checks):
        raise ValueError("Independent numerical crosscheck failed")
    return {
        "status": "pass",
        "decimal_precision_digits": 60,
        "scalar_comparisons": len(checks),
        "maximum_absolute_error_mV": max(checks),
        "absolute_tolerance_mV": tolerance_mV,
        "scope": (
            "central_and_four_corner_voltage_and_shared_baseline_change_plus_two_fit_residuals"
        ),
        "formal_interval_certificate": False,
    }


def build_analysis(plan_path=PLAN, data_directory=None):
    plan, readings, integrity = load_inputs(plan_path, data_directory)
    first, second = (readings[key] for key in plan["split"]["fit"])
    evaluation_id = plan["split"]["evaluation"][0]
    target = readings[evaluation_id]
    temperature = plan["boundary"]["temperature_K"]
    # Only target dose crosses into forecasting. Its voltage enters comparison later.
    prediction = ref.forecast(
        first,
        second,
        target.potassium_mM,
        temperature,
        tuple(plan["model"]["dose_domain_mM"]),
    )
    checked = numerical_crosscheck(
        prediction,
        first,
        second,
        temperature,
        plan["comparison"]["numerical_crosscheck_absolute_tolerance_mV"],
    )
    comparison = ref.compare_prediction(prediction, target)
    source_files = (
        "scripts/check_biological_benchmark.py",
        "scripts/evaluate_conditioned_voltage.py",
        "tests/reference_conditioned_voltage.py",
        "docs/CONDITIONED_VOLTAGE_REFERENCE.md",
    )
    return {
        "protocol_id": plan["protocol_id"],
        "protocol_sha256": PLAN_SHA256,
        "artifact_kind": "descriptive_conditioned_endpoint_comparison",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
        "dataset_id": plan["dataset_id"],
        "dataset_sha256": plan["dataset_sha256"],
        "source_doi": "10.1242/bio.048553",
        "source_sha256": {name: sha(ROOT / name) for name in source_files},
        "dataset_integrity_status": integrity["integrity_status"],
        "split": plan["split"],
        "boundary": plan["boundary"],
        "prediction": prediction,
        "comparison": comparison,
        "numerical_crosscheck": checked,
        "model_fit": "performed_on_C1_C2_only",
        "trajectory_integration": False,
        "production_model_changed": False,
        "physical_parameters_identified": False,
        "biological_acceptance": "not_assessable",
        "experimental_sem_available": False,
        "confidence_interval": False,
        "next_gate": "measurement_uncertainty_and_boundary_review_not_C3_retuning",
    }


def condition_rows(analysis):
    prediction = analysis["prediction"]
    first, second = (ref.Reading(**point) for point in prediction["fit_readings"])
    target = ref.Reading(
        analysis["comparison"]["evaluation_id"],
        prediction["target_potassium_mM"],
        analysis["comparison"]["measured_voltage_mV_approx"],
        analysis["comparison"]["measured_reading_bound_mV"],
    )
    rows = []
    for point, role in ((first, "fit"), (second, "fit"), (target, "evaluation")):
        response = ref.forecast(
            first,
            second,
            point.potassium_mM,
            prediction["curve"]["temperature_K"],
            tuple(prediction["curve"]["dose_domain_mM"]),
        )
        rows.append(
            {
                "condition": point.identity,
                "role": role,
                "potassium_mM": point.potassium_mM,
                "measured_voltage_mV_approx": point.voltage_mV,
                "measured_reading_bound_mV": point.reading_bound_mV,
                "predicted_voltage_mV": response["prediction_mV"],
                "prediction_reading_low_mV": response["prediction_reading_box_mV"][0],
                "prediction_reading_high_mV": response["prediction_reading_box_mV"][1],
                "signed_error_mV": response["prediction_mV"] - point.voltage_mV,
                "no_response_voltage_mV": first.voltage_mV,
            }
        )
    return rows


def comparison_svg(analysis):
    """Code-native plot: reading bounds are not statistical error/confidence bars."""
    rows = condition_rows(analysis)
    prediction = analysis["prediction"]
    first, second = (ref.Reading(**point) for point in prediction["fit_readings"])
    temperature = prediction["curve"]["temperature_K"]
    domain = tuple(prediction["curve"]["dose_domain_mM"])
    samples = [
        ref.forecast(
            first, second, domain[0] + i * (domain[1] - domain[0]) / 60, temperature, domain
        )
        for i in range(61)
    ]

    # Pinned pilot viewport; numerical values are also retained without rounding in JSON/CSV.
    def position(k, v):
        return 85 + 9 * k, 80 - 5.2 * v

    def points(values):
        return " ".join(f"{x:.3f},{y:.3f}" for x, y in values)

    def line(x1, y1, x2, y2, extra=""):
        return f'<line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" {extra}/>'

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="820" height="440" viewBox="0 0 820 440">',
        "<title>BIO-002: RPTEC voltage endpoints and conditioned response</title>",
        "<desc>Two fitting conditions and one retrospective evaluation. "
        "Bars and shading show figure-reading sensitivity, "
        "not SEM or confidence intervals.</desc>",
        '<rect width="820" height="440" fill="white"/>',
        '<g font-family="sans-serif" font-size="13" fill="#222">',
        '<text x="85" y="27" font-size="19">First electrical-response pilot</text>',
        '<text x="85" y="49">C1/C2 fit; C3 retrospective evaluation. '
        "No biological acceptance claim.</text>",
    ]
    for voltage in (-50, -40, -30, -20, -10, 0):
        _, y = position(0, voltage)
        parts += [
            line(85, y, 733, y, 'stroke="#ddd"'),
            f'<text x="68" y="{y + 4:.3f}" text-anchor="end">{voltage}</text>',
        ]
    for dose in (0, 20, 40, 60):
        x, y = position(dose, -50)
        parts += [
            line(x, y, x, y + 5, 'stroke="#333"'),
            f'<text x="{x:.3f}" y="362" text-anchor="middle">{dose}</text>',
        ]
    upper = [position(s["target_potassium_mM"], s["prediction_reading_box_mV"][1]) for s in samples]
    lower = [
        position(s["target_potassium_mM"], s["prediction_reading_box_mV"][0])
        for s in reversed(samples)
    ]
    central = [position(s["target_potassium_mM"], s["prediction_mV"]) for s in samples]
    parts += [
        f'<polygon points="{points(upper + lower)}" fill="#e78524" fill-opacity="0.18"/>',
        f'<polyline points="{points(central)}" fill="none" stroke="#bc5b00" stroke-width="2.5"/>',
        line(
            *position(domain[0], first.voltage_mV),
            *position(domain[1], first.voltage_mV),
            'stroke="#777" stroke-dasharray="6 4"',
        ),
    ]
    for row in rows:
        k, v, bound = (
            row["potassium_mM"],
            row["measured_voltage_mV_approx"],
            row["measured_reading_bound_mV"],
        )
        x, y = position(k, v)
        parts += [
            line(
                *position(k, v - bound), *position(k, v + bound), 'stroke="#222" stroke-width="2"'
            ),
            f'<circle cx="{x:.3f}" cy="{y:.3f}" r="4" fill="#222"/>',
            f'<text x="{x:.3f}" y="{y + 23:.3f}" text-anchor="middle">'
            f"{escape(row['condition'])} ({row['role']})</text>",
        ]
    x, y = position(prediction["target_potassium_mM"], prediction["prediction_mV"])
    parts += [
        f'<path d="M {x - 5:.3f} {y - 5:.3f} L {x + 5:.3f} {y + 5:.3f} '
        f'M {x - 5:.3f} {y + 5:.3f} L {x + 5:.3f} {y - 5:.3f}" '
        'stroke="#bc5b00" stroke-width="2.5"/>',
        '<text x="408" y="391" text-anchor="middle">External potassium (mM); '
        "sodium decreases correspondingly</text>",
        '<text transform="translate(22 220) rotate(-90)" text-anchor="middle">'
        "Membrane voltage (mV)</text>",
        '<text x="85" y="417">Black: approximate readings +/-2 mV. '
        "Orange: model / reading sensitivity. Dashed: no response.</text>",
        "</g></svg>\n",
    ]
    return "\n".join(parts)


def write_artifacts(directory, analysis, plan_path=PLAN):
    directory = Path(directory)
    if directory.exists():
        raise FileExistsError(f"Output already exists: {directory}")
    if sha(plan_path) != PLAN_SHA256 or analysis["protocol_sha256"] != PLAN_SHA256:
        raise ValueError("Protocol identity changed before publication")
    stream = io.StringIO(newline="")
    rows = condition_rows(analysis)
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    payloads = {
        "analysis.json": (json.dumps(analysis, indent=2, allow_nan=False) + "\n").encode(),
        "conditions.csv": stream.getvalue().encode(),
        "comparison.svg": comparison_svg(analysis).encode(),
        "protocol.json": Path(plan_path).read_bytes(),
    }
    directory.mkdir(parents=True, exist_ok=False)
    for name, content in payloads.items():
        with (directory / name).open("xb") as handle:
            handle.write(content)
    receipt = {
        "status": "complete",
        "biological_acceptance": "not_assessable",
        "payload_sha256": {
            name: hashlib.sha256(content).hexdigest() for name, content in payloads.items()
        },
    }
    with (directory / "manifest.json").open("x") as handle:
        json.dump(receipt, handle, indent=2, allow_nan=False)
        handle.write("\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New directory; existing outputs are refused")
    args = parser.parse_args()
    if args.output is not None and args.output.exists():
        parser.error(f"Output already exists: {args.output}")
    result = build_analysis()
    if args.output is not None:
        write_artifacts(args.output, result)
    print(json.dumps(result, indent=2, allow_nan=False))
