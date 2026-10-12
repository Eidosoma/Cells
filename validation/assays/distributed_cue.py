"""Fixed 75/25 source allocation with the qualified passive template reader.

Only the spatial allocation of the location-coded cue changes. All physical
times, total area-integrated inhibition, readout support and reader parameters
are inherited from the authenticated assays.
"""

import json
from pathlib import Path

import numpy as np

from cells.core.batch import BatchSpec, WorldSpec
from cells.core.specs import parse_spec
from validation.assays import template_readout, two_task
from validation.assays.template_readout import cases as cases
from validation.betse.spatial_active.refinement import digest

PROTOCOL_PATH = Path(__file__).with_name("distributed_cue_protocol.json")


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def baseline(rule):
    report = template_readout.baseline(rule)
    path = two_task.ROOT / rule["reader_protocol"]
    assert digest(path) == rule["reader_protocol_sha256"]
    previous = json.loads(path.read_text())
    assert rule["reader"] == previous["reader"]
    assert rule["dt_s"] == previous["dt_s"]
    assert rule["duration_s"] == previous["duration_s"]
    return report | dict(reader_and_margins_unchanged=True)


def definition(base, row, backend, rule):
    raw = template_readout.definition(base, row, backend, rule)
    if row["arm"] not in rule["cue"]["location_coded_arms"]:
        return raw
    weights = np.asarray(rule["cue"]["location_weights"], dtype=float)
    if (
        weights.shape != (2, 2)
        or not np.isfinite(weights).all()
        or np.any(weights < 0)
        or np.any(weights > 1)
        or not np.all(weights.sum(axis=1) == 1)
    ):
        raise ValueError("Each location needs two nonnegative source shares summing to one")
    tissue = raw["model"]["tissue"]
    owner, area = map(np.asarray, (tissue["cell_owner"], tissue["membrane_area"]))
    masks = [owner == i - 1 for i in two_task.protocol()["source_cell_ids"]]
    sizes = [area[mask].sum() for mask in masks]
    block = np.zeros(len(owner))
    for share, mask, size in zip(weights[row["location"]], masks, sizes, strict=True):
        block[mask] = row["amplitude"] * share * min(sizes) / size
    for change in raw["experiment"]["changes"]:
        if np.any(np.asarray(change["channel"]) != 1):
            change["channel"] = (1 - block).tolist()
    return raw


def batch(base, rows, backend, rule):
    return BatchSpec(
        tuple(
            WorldSpec(row["world_id"], parse_spec(definition(base, row, backend, rule)))
            for row in rows
        ),
        max_worlds=rule["batch_worlds"],
        max_padded_steps=rule["batch_worlds"]
        * (round(rule["duration_s"] / rule["dt_s"]) + len(two_task.protocol()["control_steps"])),
        max_working_bytes=rule["resources"]["max_batch_working_bytes"],
    )
