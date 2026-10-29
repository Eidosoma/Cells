"""An explicit passive-tissue accounting epoch after a physical cell removal."""

import json
from dataclasses import dataclass, replace

from cells.core import surface_tissue_spec as base
from cells.core.specs import ConfigError, _fields
from cells.core.surface_energy_spec import _project
from cells.processes.betse_tissue_cut import LAW_ID

MODEL_ID = "resolved_tissue_excision@1"
POLICIES = dict(
    law=LAW_ID,
    state_policy="rebase_passive_owners_archive_complete_source@1",
    clock_policy="absolute_time_original_nominal_grid@1",
    energy_policy="record_jump_without_cut_work_law@1",
    ordering="right_continuous_controls_then_removal@1",
)
MAX_CUTS = 16


@dataclass(frozen=True)
class SurfaceExcisionModel(base.SurfaceTissueModel):
    excision_json: str
    epoch_start_time: float


def base_spec(spec):
    return replace(spec, model=_project(spec.model, base.SurfaceTissueModel))


def to_dict(spec):
    raw = base.to_dict(base_spec(spec))
    raw["model"] = dict(
        id=MODEL_ID, tissue=raw["model"], excision=json.loads(spec.model.excision_json)
    )
    return raw


def _depth(record):
    count, current = 0, record
    while True:
        count += 1
        if count > MAX_CUTS:
            raise ConfigError("Excision provenance exceeds the supported 16-cut chain")
        try:
            model = current["source"]["definition"]["model"]
            if model["id"] == base.MODEL_ID:
                return
            if model["id"] != MODEL_ID:
                raise ConfigError("Excision currently requires the passive resolved tissue model")
            current = model["excision"]
        except (KeyError, TypeError) as error:
            raise ConfigError("Incomplete excision source provenance") from error


def parse(data):
    _fields(data, {"schema_version", "model", "experiment", "execution"}, "excision definition")
    m = _fields(data["model"], {"id", "tissue", "excision"}, "excision model")
    if m["id"] != MODEL_ID:
        raise ConfigError("Require " + MODEL_ID)
    record = _fields(m["excision"], {*POLICIES, "source", "removed_cell_ids"}, "excision event")
    if any(record[k] != v for k, v in POLICIES.items()):
        raise ConfigError("Declare the conservative excision epoch and clock policies")
    _depth(record)
    from cells.core.tissue_excision import _experiment, decode_source, derive_tissue

    before, point = decode_source(record["source"])
    expected, _, _ = derive_tissue(before, point, record["removed_cell_ids"])
    if expected is None or not record["removed_cell_ids"]:
        raise ConfigError("A runnable excision model needs a real cut and surviving cells")
    ordinary = base.parse(dict(data, model=m["tissue"]))
    if base.to_dict(ordinary)["model"] != expected:
        raise ConfigError("Post-cut tissue must exactly preserve the declared physical survivors")
    if ordinary.execution.dt != before.execution.dt:
        raise ConfigError("Excision retains the original nominal timestep and absolute grid")
    expected_experiment = _experiment(before, expected, point.time)
    actual_experiment = base.to_dict(ordinary)["experiment"]

    def past(schedule):
        return [v for v in schedule if v["time"] <= point.time]

    for kind in ("membrane", "junction"):
        key = kind + "_controls"
        required = {v[kind + "_id"]: v["schedule"] for v in expected_experiment[key]}
        for row in actual_experiment[key]:
            if past(row["schedule"]) != past(required[row[kind + "_id"]]):
                raise ConfigError(
                    "Excision must preserve surviving control history through the cut"
                )
    required_clocks = {
        v.time for v in before.experiment.changes if v.time <= ordinary.experiment.end_time
    }
    if not required_clocks <= {v.time for v in ordinary.experiment.changes}:
        raise ConfigError("Excision must preserve source event clocks, including removed routes")
    if ordinary.experiment.end_time < point.time or any(
        t < point.time for t in ordinary.experiment.observation_times
    ):
        raise ConfigError("Excision observations and horizon cannot precede the cut")
    spec = replace(
        ordinary,
        model=SurfaceExcisionModel(
            **vars(ordinary.model),
            excision_json=json.dumps(
                record, sort_keys=True, separators=(",", ":"), allow_nan=False
            ),
            epoch_start_time=point.time,
        ),
    )
    from cells.core.grid import EventGrid

    EventGrid(spec).exact_index(point.time)
    return spec
