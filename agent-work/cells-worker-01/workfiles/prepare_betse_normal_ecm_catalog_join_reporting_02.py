"""Prepare current metadata for driver-only catalog02, retaining every science pin."""

import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_ecm_catalog_join"
FROZEN = Path("/mnt/workspaces/Cells/betse-normal-ecm-catalog-join-prepared-20261031-01")
REVIEW = Path(
    "/mnt/workspaces/Cells/betse-normal-ecm-catalog-join-preflight-20261031-01/REVIEW.json"
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


assert sha(REVIEW) == "fc24a488b881d81fa221160ce312e3a8ffcd963c3e9d799ed1e6080d1666e814"
review = json.loads(REVIEW.read_text())
inputs = json.loads((FROZEN / "inputs.json").read_text())
assert review["inputs_sha256"] == sha(FROZEN / "inputs.json")
assert [r["id"] for r in review["blockers"]] == ["catalog_report_channel_pluralization"]
assert review["other_concrete_source_blockers"] == []
queue_path = WORK / f"{PREFIX}_workqueue.json"
old_bytes = queue_path.read_bytes()
q = json.loads(old_bytes)
assert q["owned_sha256"] == inputs["owned_sha256"] == review["reviewed_owned_sha256"]
for p, h in (q["owned_sha256"] | q["protected_sha256"]).items():
    assert sha(ROOT / p) == h, p
assert (
    sum(map(len, inputs["groups"].values())) == 94
    and inputs["planned"]["fresh_Decimal_reference_forms"] == 1314
)
metadata = WORK / f"{PREFIX}_reporting_metadata_check_02.json"
check = json.loads(metadata.read_text())
assert (
    check["corrected_reader_passes_one_and_three_call_metadata"]
    and check["synthetic_metadata_only"]
)
assert check["numerical_runs"] == check["model_evaluations"] == check["fixture_evaluations"] == 0
assert check["successor_driver_sha256"] == sha(WORK / f"{PREFIX}_checks_02.py")
final = WORK / f"{PREFIX}_reporting_final_witness_02.json"
proof = dict(
    kind="cells.catalog_driver_only_reporting02_final_static_witness@1",
    original01_inputs_sha256=sha(FROZEN / "inputs.json"),
    Chief_review_path=str(REVIEW),
    Chief_review_sha256=sha(REVIEW),
    Chief_final_review_received=True,
    awaiting_final_review=False,
    original_driver_sha256=inputs["driver_sha256"],
    successor_driver_sha256=sha(WORK / f"{PREFIX}_checks_02.py"),
    explicit_report_key_mapping=dict(channels="conditional_channel_reference_forms"),
    mode_and_folder_remain="channels",
    inverse_correspondence_witness_sha256=sha(WORK / f"{PREFIX}_reporting_witness_02.json"),
    synthetic_metadata_check_sha256=sha(metadata),
    synthetic_metadata_cases=2,
    original_metadata_KeyError_reproduced=True,
    corrected_actual_producer_metadata_reader_passes=True,
    identical_owned_sha256=q["owned_sha256"],
    identical_protected_sha256=q["protected_sha256"],
    identical_planned=q["planned"],
    identical_group_ID_sets=inputs["groups"],
    scientific_equations_inputs_assertions_protocols_budgets_unchanged=True,
    preserved01=True,
    scientific_imports=0,
    fixture_evaluations=0,
    model_evaluations=0,
    reference_evaluations=0,
    pytest_collection_runs=0,
    numerical_runs=0,
    automatic_launch=False,
)
write(final, proof)
with (WORK / f"{PREFIX}_workqueue_before_reporting02.json").open("xb") as stream:
    stream.write(old_bytes)
for name, path in {
    "frozen_catalog01_inputs": FROZEN / "inputs.json",
    "Chief_catalog01_final_preflight_review": REVIEW,
    "reporting_key_inverse02": WORK / f"{PREFIX}_reporting_witness_02.json",
    "reporting_synthetic_metadata02": metadata,
    "reporting_final_static02": final,
}.items():
    q["binding_evidence"][name] = dict(path=str(path), sha256=sha(path))
new_files = [
    WORK / f"{PREFIX}_checks_02.py",
    WORK / f"{PREFIX}_reporting_audit_02.py",
    WORK / f"{PREFIX}_reporting_witness_02.json",
    WORK / f"{PREFIX}_reporting_metadata_check_02.py",
    metadata,
    final,
    WORK / f"{PREFIX}_workqueue_before_reporting02.json",
    Path(__file__),
]
for p in new_files:
    relative = str(p.relative_to(ROOT))
    if relative not in q["workfiles"]:
        q["workfiles"].append(relative)
q.update(
    status="reporting_only02_static_ready_to_freeze_no_numerics",
    runner=str((WORK / f"{PREFIX}_checks_02.py").relative_to(ROOT)),
    reporting_only_successor02=proof,
    previous_prepared_inputs=q.pop("prepared_inputs"),
    previous_prepared_inputs_sha256=q.pop("prepared_inputs_sha256"),
    previous_static_receipt=q.pop("static_receipt"),
    previous_static_receipt_sha256=q.pop("static_receipt_sha256"),
)
q["static_checks"].update(
    report_key_inverse_AST_exact=True,
    actual_producer_synthetic_metadata_cases=2,
    synthetic_metadata_old_KeyError_reproduced=True,
    report_mapping_channels_to_channel=True,
    all94_IDs_and_scientific_assertions_protocols_budgets_retained=True,
    Chief_final_source_review_bound=True,
)
queue_path.write_text(json.dumps(q, indent=2, sort_keys=True) + "\n")
print(
    json.dumps(
        dict(
            status=q["status"],
            scientific_files_unchanged=len(q["owned"]),
            binding_evidence=len(q["binding_evidence"]),
            final_witness_sha256=sha(final),
            corrected_driver_sha256=check["successor_driver_sha256"],
            numerical_runs=0,
        ),
        sort_keys=True,
    )
)
