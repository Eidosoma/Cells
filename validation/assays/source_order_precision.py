"""Bind a numerical charge-summation repair to frozen failed and native evidence."""

import json
from pathlib import Path

from validation.assays import source_order_long, two_task
from validation.betse.spatial_active.refinement import completed_prior, digest

PROTOCOL_PATH = Path(__file__).with_name("source_order_long") / "precision_protocol.json"


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def baseline():
    rule = protocol()
    binding = rule["failed_binding"]
    root = Path(binding["root"])
    assert digest(root / "registration.json") == binding["registration_sha256"]
    assert digest(root / "failure.json") == binding["failure_sha256"]
    assert json.loads((root / "failure.json").read_text())["status"] == "failed"
    assert not (root / "completion.json").exists()
    registration = json.loads((root / "registration.json").read_text())
    changed = []
    for name, expected in registration["sources_sha256"].items():
        assert digest(root / "source" / name) == expected, name
        if digest(two_task.ROOT / name) != expected:
            changed.append(name)
    assert changed == [rule["changed_production_file"]]
    assert digest(root / "source" / changed[0]) == rule["old_production_sha256"]
    assert digest(two_task.ROOT / changed[0]) == rule["new_production_sha256"]
    assert {str(p.relative_to(two_task.ROOT)) for p in (two_task.ROOT / "src").rglob("*.py")} == {
        name for name in registration["sources_sha256"] if name.startswith("src/")
    }
    old = source_order_long.protocol()
    assert old == registration["component_protocol"]
    assert digest(two_task.ROOT / rule["original_protocol"]) == rule["original_protocol_sha256"]
    for key in (
        "template",
        "template_sha256",
        "duration_s",
        "dt_s",
        "max_steps",
        "primary_panel",
        "observation_panels",
        "observation_times_us",
        "readout",
        "reader",
        "preparations",
        "world_id_offset",
        "source_cell_ids",
        "task_meanings",
        "cue_timing",
        "replay",
        "score_stability",
        "contrast",
        "batch_worlds",
        "window_steps",
        "historical_binding",
    ):
        assert rule[key] == old[key], key
    audit = rule["archive_audit"]
    folder = Path(audit["root"])
    assert digest(folder / audit["result"]) == audit["sha256"]
    report = json.loads((folder / audit["result"]).read_text())
    assert report["source_registration_sha256"] == binding["registration_sha256"]
    assert report["source_failure_sha256"] == binding["failure_sha256"]
    assert digest(folder / "full_archive_audit.py") == report["script_sha256"]
    for name, expected in report["inputs_sha256"].items():
        assert digest(root / name) == expected, name
    assert {row["field"] for row in report["failures"]} == {"active__m_gate"}
    native = rule["native_reference_binding"]
    native_root = Path(native["root"])
    reference = completed_prior(native, current_root=native_root / "source")
    assert reference["completion_sha256"] == native["completion_sha256"]
    return dict(
        status="passed",
        changed_prior_files=changed,
        unchanged_prior_sources=len(registration["sources_sha256"]) - len(changed),
        authenticated_failed_archive_inputs=len(report["inputs_sha256"]),
        failed_archive_compared_scalars=report["compared_scalars"],
        archived_failure_fields=["active__m_gate"],
        native_reference=reference,
        physical_inputs_and_tolerances_unchanged=True,
        old_bitwise_histories_not_required_after_precision_correction=True,
        new_replay_still_bitwise=True,
    )
