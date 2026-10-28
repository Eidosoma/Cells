"""Manufactured expanded populations sharing one chemical cytosol/ER per cell."""

from validation.tissue import surface_calcium_cav_fixtures as prior
from validation.tissue import surface_catalog_fixtures as shared

ARMS = shared.ARMS


def definition(arm="open", *, backend="cpu", padded=True):
    raw = prior.definition("baseline", backend=backend, padded=padded)
    ionic = shared.definition(arm, backend=backend, padded=padded)
    raw["model"]["id"] = "resolved_calcium@7"
    raw["model"]["ionic"] = ionic["model"]
    raw["experiment"]["channel_controls"] = ionic["experiment"]["channel_controls"]
    raw["experiment"]["observation_times"] = ionic["experiment"]["observation_times"]
    raw["execution"]["channel_capacity"] = ionic["execution"]["channel_capacity"]
    return raw


def compact_probe():
    """Early feedback only; no slow-gate/ER settling or physiological claim."""
    raw = definition("release", padded=False)
    dt = raw["execution"]["dt"]
    e = raw["experiment"]
    e.update(end_time=40 * dt, observation_times=[i * dt for i in (0, 10, 20, 30, 40)])
    for name, groups in e.items():
        if name.endswith("_controls"):
            for group in groups:
                key = "controls" if "controls" in group else "schedule"
                group[key] = [row for row in group[key] if row["time"] <= e["end_time"]]
    return raw


def assembly_definition(*, backend="cpu"):
    raw = prior.assembly_definition(backend=backend)
    raw["ionic"] = definition(backend=backend)
    return raw
