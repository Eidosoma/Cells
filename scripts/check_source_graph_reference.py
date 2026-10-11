"""NUM-005a independent graph/native derivative and accounting acceptance.

No integration, long-time solver selection, preparation or production model.
The optional new output directory retains the receipt and independent sources;
it contains no upstream implementation.
"""

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import check_e02_protocol as protocol_check  # noqa: E402
from tests import reference_source_pair_numerics as pair_numeric  # noqa: E402
from tests import source_graph_fixtures as fixtures  # noqa: E402

graph = fixtures.graph
FIXTURE = ROOT / "tests/fixtures/source_graph_probes.json"
FIXTURE_SHA256 = "4ca9a9834f826aa8cbb72fe462d986bdfc1b4dcd46f2a49798bd9dfdbff83fef"
AUDITS = {
    "primary_unchanged",
    "context_unchanged",
    "repeat_rhs_exact",
    "readouts_do_not_change_refreshed_packet",
    "nonprimary_native_slopes_zero",
    "regulatory_charge_excluded",
    "temporary_parameters_restored",
    "finite",
}
SOURCES = (
    "tests/reference_source_graph.py",
    "tests/source_graph_fixtures.py",
    "tests/reference_source_pair.py",
    "tests/reference_source_pair_numerics.py",
    "tests/reference_emt.py",
    "scripts/check_source_graph_reference.py",
    "scripts/capture_source_graph_reference.py",
    "scripts/capture_contact_reference.py",
    "scripts/capture_emt_reference.py",
    "scripts/check_e02_protocol.py",
    "tests/unit/test_source_graph_reference.py",
    "tests/fixtures/source_graph_probes.json",
    "configs/reference/source_emt_graph_probes_v1.json",
    "configs/reference/e02_switching_protocol_v1.json",
    "configs/reference/source_emt_pair_panel_v1.json",
    "tests/fixtures/source_pair_probes.json",
    "requirements-lock.txt",
    "requirements-reference.txt",
)


class Audit:
    def __init__(self):
        self.count = 0

    def require(self, condition, label):
        if not condition:
            raise ValueError(label)
        self.count += 1

    def close(self, actual, expected, label, *, atol=5e-12, rtol=2e-12):
        a, b = np.asarray(actual), np.asarray(expected)
        self.require(a.shape == b.shape, f"{label}: shape differs")
        self.require(np.isfinite(a).all() and np.isfinite(b).all(), f"{label}: nonfinite")
        if not np.allclose(a, b, atol=atol, rtol=rtol):
            raise ValueError(f"{label}: mismatch, max absolute error {np.max(abs(a - b))}")
        self.count += a.size


def compare_native(native):
    """Structural and numerical audit, also exercised with deliberately corrupt copies."""
    audit = Audit()
    definitions = fixtures.definition()
    inputs = fixtures.cases()
    panel = graph.eq.load_panel()
    old_native = protocol_check.pinned_json(
        ROOT / "tests/fixtures/source_pair_probes.json",
        protocol_check.load_protocol()["provenance"]["native_fixture_sha256"],
    )
    audit.require(native["schema_version"] == 1, "Native schema")
    audit.require(native["revision"] == definitions["source_revision"], "Source revision")
    audit.require(
        native["source_hashes"] == old_native["source_hashes"], "Native source hashes differ"
    )
    audit.require(
        native["definition_sha256"] == fixtures.DEFINITION_SHA256, "Probe definition hash"
    )
    encoded = (
        json.dumps({"panel": panel, "cases": inputs}, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    )
    audit.require(
        native["inputs_sha256"] == hashlib.sha256(encoded.encode()).hexdigest(),
        "Expanded input hash",
    )
    probes = native["probes"]
    audit.require(tuple(probes["row_names"]) == graph.eq.PACKET, "Native row ordering")
    audit.require(
        probes["profile"] == old_native["probes"]["profile"], "Native approximation profile"
    )
    records = probes["records"]
    audit.require(
        [r["case_id"] for r in records] == [c["id"] for c in inputs],
        "Incomplete, reordered or duplicate case inventory",
    )
    maximum = dict.fromkeys(definitions["instantaneous_tolerances"], 0.0)
    results = {}
    for case, record in zip(inputs, records, strict=True):
        label = case["id"]
        model = graph.Model(case, panel)
        primary, context = model.anchor.copy(), model.context.copy()
        actual = model.evaluate(primary)
        audit.require(record["origin"] == case["origin"], f"{label}: origin differs")
        audit.require(set(record["audits"]) == AUDITS, f"{label}: incomplete source audits")
        for name, passed in record["audits"].items():
            audit.require(passed is True, f"{label}: {name}")
        for name, tolerances in definitions["instantaneous_tolerances"].items():
            audit.close(actual[name], record[name], f"{label}/{name}", **tolerances)
            maximum[name] = max(
                maximum[name], float(np.max(abs(actual[name] - record[name]), initial=0))
            )
        before = np.asarray(record["input_packet"])
        audit.close(
            before[graph.eq.PRIMARY_INDEX], primary, f"{label}: initial primary", atol=0, rtol=0
        )
        audit.close(
            before[graph.eq.CONTEXT_INDEX], context, f"{label}: fixed context", atol=0, rtol=0
        )
        audit.require(
            not np.array_equal(
                before[graph.eq.DERIVED_INDEX], actual["packet"][graph.eq.DERIVED_INDEX]
            ),
            f"{label}: missing stale-cache challenge",
        )
        audit.close(primary, model.anchor, f"{label}: pure primary", atol=0, rtol=0)
        audit.close(context, model.context, f"{label}: pure context", atol=0, rtol=0)
        padded = np.zeros((17, model.n))
        padded[graph.eq.PRIMARY_INDEX] = actual["primary_rate"]
        audit.close(padded, record["native_packet_rate"], f"{label}: full native RHS")
        audit.close(
            actual["contact_rate"].sum(axis=1), np.zeros(6), f"{label}: reciprocal transfer", rtol=0
        )
        # A separate incidence-matrix assembly checks the oracle's explicit loop.
        incidence = np.zeros((model.e, model.n))
        for edge, (a, b) in enumerate(model.edges):
            incidence[edge, a], incidence[edge, b] = -1, 1
        assembled = actual["membrane_rate"] + actual["local_rate"]
        assembled[:4] += actual["junction_flux"] @ incidence * model.area / model.volume
        audit.close(
            actual["primary_rate"], assembled, f"{label}: independent contribution assembly"
        )
        slope = model.derivative(model.initial())
        changed = model.initial()
        changed[6 * model.n :] = np.arange(model.coordinates.size - 6 * model.n) - 7
        audit.close(slope, model.derivative(changed), f"{label}: passive histories", atol=0, rtol=0)
        audit.close(
            slope,
            model.derivative(np.zeros(model.coordinates.size), increments=True),
            f"{label}: increment representation",
            atol=0,
            rtol=0,
        )
        # Algebraic tangent reconstruction, not an accepted integration step.
        residual = model.accounting(np.array([model.initial(), model.initial() + 1e-5 * slope]))
        audit.require(max(residual.values()) < 2e-12, f"{label}: tangent accounting")
        audit.close(actual["packet"][8], primary[3], f"{label}: free proxy", atol=0, rtol=0)
        audit.close(
            np.array([1, 6, 15, 20, 15, 6, 1]) @ actual["packet"][9:16],
            primary[4],
            f"{label}: mRNA binding configurations",
        )
        results[label] = actual
    return audit, results, maximum


def verify():
    native = protocol_check.pinned_json(FIXTURE, FIXTURE_SHA256)
    audit, results, maximum = compare_native(native)
    panel = graph.eq.load_panel()
    pair_settings = 0
    for case in panel["cases"]:
        old_model = pair_numeric.Model(panel, case)
        for time in old_model.starts:
            model = graph.from_pair(panel, case, time)
            r = model.evaluate(model.anchor)
            old = graph.eq.evaluate(model.anchor, model.context, panel, case, time)
            for name, value in old.items():
                if name == "delta_v":
                    expected = np.asarray(value).reshape(1)
                elif name in ("gate_scales", "junction_flux"):
                    expected = np.asarray(value)[:, None]
                else:
                    expected = value
                audit.close(r[name], expected, f"pair {case['id']}@{time}/{name}")
            audit.close(
                model.initial(), old_model.initial(), "Pair 30-coordinate initial", atol=0, rtol=0
            )
            audit.close(
                model.derivative(model.initial()),
                old_model.derivative(old_model.initial(), old_model.slot(time)),
                "Pair complete derivative",
            )
            pair_settings += 1
    a, reversed_physical = results["G02"], results["G04"]
    for name in ("primary_rate", "local_rate", "membrane_rate", "gate_scales"):
        audit.close(a[name], reversed_physical[name], f"Physical reversal/{name}")
    audit.close(a["junction_flux"], -reversed_physical["junction_flux"], "Oriented reversal")
    audit.require(
        np.max(abs(a["gate_scales"] - results["G03"]["gate_scales"])) > 0.001,
        "Missing reversal-without-swap negative control",
    )
    audit.close(
        results["G10"]["primary_rate"],
        results["G11"]["primary_rate"],
        "Blocked star equals disconnected local RHS",
        atol=0,
        rtol=0,
    )
    inputs = fixtures.cases()
    return {
        "status": "pass",
        "scope": "NUM-005a instantaneous graph composition only",
        "checks_passed": audit.count,
        "native_cases": len(inputs),
        "pair_control_settings": pair_settings,
        "constructed_e02_seed_cases": 14,
        "isolated_preparation_seed_cases": 2,
        "other_constructed_graph_cases": 12,
        "cell_counts": sorted({len(c["cell_ids"]) for c in inputs}),
        "maximum_absolute_native_errors": maximum,
        "definition_sha256": fixtures.DEFINITION_SHA256,
        "native_fixture_sha256": FIXTURE_SHA256,
        "source_revision": native["revision"],
        "source_hashes": native["source_hashes"],
        "preparation_packets": "not_generated",
        "trajectory_qualification": "not_run",
        "production_implementation": "unchanged_0.10.0",
        "long_time_candidate": "not_selected",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output is not None and args.output.exists():
        parser.error("--output must name a new directory")
    result = verify()
    if args.output is not None:
        args.output.mkdir(parents=True, exist_ok=False)
        result["reference_source_hashes"] = {
            name: protocol_check.sha(ROOT / name) for name in SOURCES
        }
        capsule = args.output / "reference_sources.zip"
        with zipfile.ZipFile(capsule, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in SOURCES:
                archive.write(ROOT / name, name)
        result["capsule_sha256"] = protocol_check.sha(capsule)
        with (args.output / "verification.json").open("x") as handle:
            json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
