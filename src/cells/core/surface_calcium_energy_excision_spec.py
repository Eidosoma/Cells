"""Conservative removal with chemical stores and finite transformed fuel owners."""

import json
from dataclasses import dataclass, replace

from cells.core import surface_calcium_energy_spec as base
from cells.core.specs import ConfigError, _fields
from cells.core.surface_energy_spec import _project
from cells.core.surface_excision_spec import MAX_CUTS
from cells.core.surface_excision_spec import POLICIES as PASSIVE_POLICIES

MODEL_ID = "resolved_calcium_energy_excision@1"
POLICIES = PASSIVE_POLICIES | {
    "state_policy": "rebase_chemical_and_fuel_owners_preserve_gates_archive_complete_source@1",
    "reference_policy": "free_cytosol_anchor_with_conserved_whole_cell_charge@1",
}


@dataclass(frozen=True)
class SurfaceCalciumEnergyExcisionModel(base.SurfaceCalciumEnergyHCNExtraModel):
    excision_json: str
    epoch_start_time: float


def base_spec(spec):
    return replace(spec, model=_project(spec.model, base.SurfaceCalciumEnergyHCNExtraModel))


def to_dict(spec):
    raw = base.to_dict(base_spec(spec))
    raw["model"] = dict(
        id=MODEL_ID, tissue=raw["model"], excision=json.loads(spec.model.excision_json)
    )
    return raw


def _depth(record):
    current = record
    for _ in range(MAX_CUTS):
        try:
            source = current["source"]["definition"]["model"]
            if source["id"] == base.HCN_EXTRA_MODEL_ID:
                return
            if source["id"] != MODEL_ID:
                raise ConfigError(
                    "Finite-fuel excision requires resolved_calcium_energy@5 source provenance"
                )
            current = source["excision"]
        except (KeyError, TypeError) as error:
            raise ConfigError("Incomplete calcium excision source provenance") from error
    raise ConfigError("Finite-fuel calcium excision provenance exceeds the supported 16-cut chain")


def parse(data):
    _fields(
        data, {"schema_version", "model", "experiment", "execution"}, "calcium excision definition"
    )
    m = _fields(data["model"], {"id", "tissue", "excision"}, "calcium excision model")
    if m["id"] != MODEL_ID:
        raise ConfigError("Require " + MODEL_ID)
    record = _fields(
        m["excision"], {*POLICIES, "source", "removed_cell_ids"}, "calcium excision event"
    )
    if any(record[k] != v for k, v in POLICIES.items()):
        raise ConfigError(
            "Declare the conservative calcium excision and gate-preservation policies"
        )
    _depth(record)
    from cells.core.calcium_energy_tissue_excision import (
        CONTROL_GROUPS,
        decode_source,
        derive_tissue,
        experiment,
    )

    before, point = decode_source(record["source"])
    expected, _, _ = derive_tissue(before, point, record["removed_cell_ids"])
    if expected is None or not record["removed_cell_ids"]:
        raise ConfigError("A runnable calcium excision needs a real cut and surviving cells")
    ordinary = base.parse(dict(data, model=m["tissue"]))
    if (
        type(ordinary.model) is not base.SurfaceCalciumEnergyHCNExtraModel
        or base.to_dict(ordinary)["model"] != expected
    ):
        raise ConfigError(
            "Calcium survivors must preserve physical owners, parameters and actual gates"
        )
    if ordinary.execution.dt != before.execution.dt:
        raise ConfigError("Finite-fuel calcium excision retains the original nominal timestep")
    expected_experiment = experiment(before, expected, point.time)
    actual_experiment = base.to_dict(ordinary)["experiment"]

    def past(schedule):
        return [v for v in schedule if v["time"] <= point.time]

    for key, (owner, schedule) in CONTROL_GROUPS.items():
        required = {v[owner]: v[schedule] for v in expected_experiment[key]}
        for row in actual_experiment[key]:
            if past(row[schedule]) != past(required[row[owner]]):
                raise ConfigError(
                    "Finite-fuel calcium excision cannot rewrite surviving control history"
                )
    required_clocks = {
        v.time for v in before.experiment.changes if v.time <= ordinary.experiment.end_time
    }
    if not required_clocks <= {v.time for v in ordinary.experiment.changes}:
        raise ConfigError("Finite-fuel calcium excision must retain removed-owner event clocks")
    if ordinary.experiment.end_time < point.time or any(
        t < point.time for t in ordinary.experiment.observation_times
    ):
        raise ConfigError(
            "Finite-fuel calcium excision observations and horizon cannot precede the cut"
        )
    spec = replace(
        ordinary,
        model=SurfaceCalciumEnergyExcisionModel(
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
