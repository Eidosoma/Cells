"""Verify a prepared static snapshot and record a worker receipt; stdlib only."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def record(family, directory, number):
    prefix = {
        "sim_grn": "betse_sim_grn",
        "ecm_grn": "betse_ecm_grn",
        "ecm_charged_grn": "betse_ecm_charged_grn",
        "ecm_sim_grn": "betse_ecm_sim_grn",
        "native_cut_lifecycle": "betse_native_cut_lifecycle",
    }.get(family, "betse_normal_" + family + "_join")
    queue_path = WORK / (prefix + "_workqueue.json")
    queue = json.loads(queue_path.read_text())
    inputs = json.loads((directory / "inputs.json").read_text())
    protocol = json.loads(
        (
            directory
            / (
                "source/validation/"
                + ("topology/" if family == "native_cut_lifecycle" else "betse/")
                + prefix
                + "_protocol.json"
            )
        ).read_text()
    )
    for relative, expected in inputs["source_hashes"].items():
        assert sha(directory / "source" / relative) == expected, relative
    for relative, expected in inputs["native_snapshot_sha256"].items():
        assert sha(directory / relative) == expected, relative
    for relative, expected in (inputs["owned_sha256"] | inputs["protected_sha256"]).items():
        assert sha(ROOT / relative) == sha(directory / "source" / relative) == expected, relative
    assert sha(directory / "driver.py") == inputs["driver_sha256"]
    assert inputs["reference_closure"] == queue["reference_closure"]
    path = WORK / (prefix + "_static_receipt_" + number + ".json")
    result = dict(
        kind="cells.native_" + family + "_static_receipt@1",
        status="static_frozen_unqualified_no_numerical_retry",
        inputs=str(directory / "inputs.json"),
        inputs_sha256=sha(directory / "inputs.json"),
        driver_sha256=inputs["driver_sha256"],
        source_snapshot_files=len(inputs["source_hashes"]),
        native_source_copies=inputs["native_source_copies"],
        binding_evidence_copies=inputs["binding_evidence_copies"],
        owned_files=len(inputs["owned_sha256"]),
        protected_files=len(inputs["protected_sha256"]),
        all_frozen_source_native_binding_hashes_match=True,
        live_and_frozen_owned_protected_match=True,
        static_checks=queue["static_checks"],
        planned=inputs["planned"],
        planned_groups={key: len(value) for key, value in inputs["groups"].items()},
        reference_closure=inputs["reference_closure"],
        binding_evidence=inputs["binding_evidence"],
        accounting=protocol["accounting"],
        adapter_field_repair_02=queue.get("adapter_field_repair_02"),
        admission_bridge_repair_02=queue.get("admission_bridge_repair_02"),
        configuration_container_repair_03=queue.get("configuration_container_repair_03"),
        native_key_retention_repair02=queue.get("native_key_retention_repair02"),
        reference_fixed_cold_budget_repair02=queue.get("reference_fixed_cold_budget_repair02"),
        error_capture_repair_02=queue.get("error_capture_repair_02"),
        capture_repair_03=queue.get("capture_repair_03"),
        controlled_dependency_refresh=queue.get("controlled_molecule_adapter_refresh"),
        scientific_imports=0,
        scientific_AST_executions=0,
        pytest_collection_runs=0,
        native_capture_runs=0,
        reference_runs=0,
        numerical_runs=0,
        physical_global_conservation_credit=False,
        no_biological_or_trajectory_accuracy_claim=True,
        automatic_launch=False,
        automatic_polling=False,
        automatic_followup=False,
    )
    with path.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    queue.update(
        prepared_inputs=result["inputs"],
        prepared_inputs_sha256=result["inputs_sha256"],
        static_receipt=str(path.relative_to(ROOT)),
        static_receipt_sha256=sha(path),
        status="static_frozen_ready_for_Chief_review_no_" + family + "_numerics",
    )
    queue_path.write_text(json.dumps(queue, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(
        json.dumps(
            dict(
                inputs=result["inputs"],
                inputs_sha256=result["inputs_sha256"],
                receipt=str(path),
                receipt_sha256=sha(path),
                source_files=result["source_snapshot_files"],
                native_copies=result["native_source_copies"],
                binding_copies=result["binding_evidence_copies"],
                owned=result["owned_files"],
                protected=result["protected_files"],
                scientific_imports=0,
                numerical_runs=0,
            )
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "family",
        choices=(
            "molecule",
            "transporter",
            "grn",
            "charged_grn",
            "sim_grn",
            "ecm_grn",
            "ecm_charged_grn",
            "ecm_sim_grn",
            "ecm_field",
            "ecm_catalog",
            "ecm_event",
            "native_cut_lifecycle",
        ),
    )
    parser.add_argument("directory", type=Path)
    parser.add_argument("number")
    args = parser.parse_args()
    record(args.family, args.directory, args.number)
