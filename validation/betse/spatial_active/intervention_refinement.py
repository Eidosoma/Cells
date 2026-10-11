"""Long scheduled definitions and an unchanged completed CPU/L4 prerequisite."""

import json
from pathlib import Path

from validation.betse.spatial_active import interventions, refinement, runtime

PROTOCOL_PATH = Path(__file__).with_name("intervention_refinement_protocol.json")


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def baseline():
    rule = protocol()
    binding = rule["prior_binding"]
    root = Path(binding["root"])
    assert refinement.digest(root / "completion.json") == binding["completion_sha256"]
    report = refinement.completed_prior(binding, current_root=runtime.ROOT)
    registration = json.loads((root / "registration.json").read_text())
    # The earlier tests and native/oracle helpers are part of this prerequisite,
    # as well as the production model. New files only extend the qualification.
    for name, digest in registration["sources_sha256"].items():
        assert refinement.digest(runtime.ROOT / name) == digest, name
    production = {str(p.relative_to(runtime.ROOT)) for p in (runtime.ROOT / "src").rglob("*.py")}
    assert production == {n for n in registration["sources_sha256"] if n.startswith("src/")}
    return report | dict(
        unchanged_prior_files=len(registration["sources_sha256"]),
        inherited_suites=registration["test_nodes"],
        qualification_scope="Completed prior CPU/L4 tests plus new long scheduled checks",
    )


def definition(case="coupled_block", index=2, *, backend="cpu", full_observations=True):
    rule = protocol()
    # Only initial/static data and prescribed inputs come from the short setup.
    # No evolving native values are used to drive the Cells trajectory.
    data = interventions.definition(case, 0, backend=backend, full_observations=False)
    dt = rule["native_steps_s"][index]
    steps = round(rule["duration_s"] / dt)
    data["execution"]["dt"] = dt
    data["experiment"]["end_time"] = steps * dt
    data["experiment"]["observation_times"] = (
        [i * dt for i in range(steps + 1)]
        if full_observations
        else sorted({0, steps * dt, *(c["time"] for c in data["experiment"]["changes"])})
    )
    return data
