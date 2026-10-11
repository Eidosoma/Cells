"""Scheduled experiment definitions and strict completed-runtime binding."""

import json
from pathlib import Path

import numpy as np

from validation.betse.spatial_active import refinement, runtime

PROTOCOL_PATH = Path(__file__).with_name("intervention_protocol.json")


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def baseline():
    rule = protocol()
    binding = rule["prior_binding"]
    root = Path(binding["root"])
    assert refinement.digest(root / "completion.json") == binding["completion_sha256"]
    report = refinement.completed_prior(binding, current_root=root / "source")
    registration = json.loads((root / "registration.json").read_text())
    changed, unchanged = [], []
    for name, sha in registration["sources_sha256"].items():
        if name.startswith("src/"):
            (unchanged if refinement.digest(runtime.ROOT / name) == sha else changed).append(name)
    assert set(changed) == set(rule["allowed_prior_source_changes"])
    assert all(
        "src/cells/numerics/" + name in unchanged
        for name in ("betse_active.py", "betse_spatial.py")
    )
    assert rule["tolerances"] == registration["component_protocol"]["tolerances"]
    prior_protocol = json.loads(
        (root / "source/validation/betse/spatial_active/runtime_protocol.json").read_text()
    )
    current = runtime.protocol()
    assert current.pop("allowed_prior_source_changes") == prior_protocol.pop(
        "allowed_prior_source_changes"
    ) + ["src/cells/core/schedule.py"]
    assert current == prior_protocol
    return report | dict(
        changed_production_files=changed,
        unchanged_production_files=len(unchanged),
        inherited_runtime_allowlist_extension="schedule.py; qualified static criteria unchanged",
    )


def definition(case="coupled_block", index=0, *, backend="cpu", full_observations=True):
    rule = protocol()
    case = next(c for c in rule["cases"] if c["id"] == case)
    dt = rule["native_steps_s"][index]
    steps = round(rule["duration_s"] / dt)
    data = runtime.definition("coupled", index, backend=backend, steps=steps)
    owner = np.asarray(data["model"]["tissue"]["cell_owner"])
    changes = []
    for entry in case["interventions"]:
        selected = (
            np.ones(owner.shape, dtype=bool)
            if entry["target_cells"] == "all"
            else np.isin(owner, entry["target_cells"])
        )
        values = {}
        for name in ("pump", "channel"):
            value = np.ones(owner.shape)
            value[selected] = entry[name + "_fraction"]
            values[name] = value.tolist()
        changes.append(dict(time=entry["time_s"], **values))
    data["experiment"]["changes"] = changes
    data["experiment"]["observation_times"] = (
        [i * dt for i in range(steps + 1)]
        if full_observations
        else sorted({0, steps * dt, *(e["time"] for e in changes)})
    )
    return data
