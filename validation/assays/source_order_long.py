"""Paired source-order follow-up through 512 us with unchanged cues and reader."""

import json
from pathlib import Path

from cells.core.batch import BatchSpec, WorldSpec
from cells.core.specs import parse_spec
from validation.assays import source_order as previous
from validation.assays import two_task
from validation.assays.source_order import archived_segment as archived_segment
from validation.assays.source_order import compare_reader_predictions as compare_reader_predictions
from validation.assays.source_order import features as features
from validation.assays.source_order import ordered as ordered
from validation.assays.source_order import paired_contrasts as paired_contrasts
from validation.assays.source_order import reader_reports as reader_reports
from validation.assays.source_order import times as times
from validation.assays.source_order import world_name as world_name
from validation.betse.spatial_active.refinement import completed_prior, digest

PROTOCOL_PATH = Path(__file__).with_name("source_order_long") / "protocol.json"


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def cases(rule=None):
    return previous.cases(protocol() if rule is None else rule)


def baseline(rule):
    current = two_task.baseline(rule)
    binding = rule["historical_binding"]
    root = Path(binding["root"])
    historical = completed_prior(binding, current_root=root / "source")
    assert historical["completion_sha256"] == binding["completion_sha256"]
    old = previous.protocol()
    assert old == json.loads((root / "component-protocol.json").read_text())
    assert digest(two_task.ROOT / rule["source_protocol"]) == rule["source_protocol_sha256"]
    runtime = json.loads(
        (Path(rule["prior_binding"]["root"]) / "component-protocol.json").read_text()
    )
    assert runtime["source_binding"] == binding
    assert runtime["duration_s"] == rule["duration_s"] == 512e-6
    for key in (
        "template",
        "template_sha256",
        "dt_s",
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
    ):
        assert rule[key] == old[key], key
    assert cases(rule) == previous.cases()
    assert rule["observation_panels"] == old["observation_panels"] | {"long512": 8}
    assert rule["observation_times_us"] == old["observation_times_us"] | {
        "long512": [320, 384, 512]
    }
    assert rule["primary_panel"] == "long512"
    diagnostic = rule["diagnostic_binding"]
    folder = Path(diagnostic["root"])
    assert not (folder / "failure.json").exists()
    assert digest(folder / "completion.json") == diagnostic["completion_sha256"]
    done = json.loads((folder / "completion.json").read_text())
    assert done["status"] == "completed"
    for name, sha in done["evidence_sha256"].items():
        assert digest(folder / name) == sha, name
    for name, key in (("inputs.json", "inputs_sha256"), ("result.json", "result_sha256")):
        assert digest(folder / name) == done[key], name
    inputs = json.loads((folder / "inputs.json").read_text())
    assert inputs["source_binding"] == binding
    for name, sha in inputs["diagnostic_sources_sha256"].items():
        assert digest(folder / "source" / name) == digest(two_task.ROOT / name) == sha
    registration = json.loads(
        (Path(rule["prior_binding"]["root"]) / "registration.json").read_text()
    )
    assert {str(p.relative_to(two_task.ROOT)) for p in (two_task.ROOT / "src").rglob("*.py")} == {
        name for name in registration["sources_sha256"] if name.startswith("src/")
    }
    return dict(
        status="passed",
        runtime=current,
        historical_assay=historical,
        diagnostic_completion_sha256=diagnostic["completion_sha256"],
        all_prior_sources_unchanged=current["all_prior_sources_unchanged"],
        production_physics_cues_strengths_reader_and_tolerances_unchanged=True,
        paired_followup_is_not_fresh_holdout=True,
        response_simulation_before_registration=False,
    )


def definition(base, row, level, backend, rule):
    raw = previous.definition(base, row, level, backend, rule)
    # This is a work ceiling, not a timestep or numerical-law change. Windows
    # retain the preceding 1024-step memory budget and archive every state.
    raw["execution"]["max_steps"] = rule["max_steps"]
    return raw


def batch(base, rows, level, backend, rule):
    return BatchSpec(
        tuple(
            WorldSpec(row["world_id"], parse_spec(definition(base, row, level, backend, rule)))
            for row in rows
        ),
        rule["batch_worlds"],
        rule["batch_worlds"] * (round(rule["duration_s"] / rule["dt_s"][level]) + 7),
        rule["resources"]["max_batch_working_bytes"],
    )


def reference_reports(rows, maps, reports, rule):
    """Apply the unchanged reference-assisted reader to the declared later panel."""
    panel = rule["primary_panel"]
    # The earlier helper names its selected panel long256 internally. Only the
    # lookup is adapted; features, fitting, reference choice and scores are reused.
    selected = {(level, "long256"): maps[level, panel] for level in range(3)}
    result = previous.reference_reports(rows, selected, {"long256": reports[panel]}, rule)
    return result | dict(panel=panel, fixed_primary_panel=True)
