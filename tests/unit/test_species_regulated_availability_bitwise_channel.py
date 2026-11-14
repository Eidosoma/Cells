"""species_regulated_availability@1, milestone 1, probe P1: the factored channel path is the
scheduled one.

docs/INVENTORY_COUPLING_DESIGN.md §1.10 and §4.4 (ruling 12), with the probe's criterion written
before any run (inventory-coupling-v1-20261114-01/HANDOFF.md). The seven-cell heredity sheet, 30
steps at 1 ms: a coupling at a frozen regulatory state (b = 0, state_fraction) on cell_3's Kir
population gives, bit for bit, what that population scheduled at the same availability gives:
* 1/2 against 1/2 scheduled;
* 0 against 0 scheduled;
* the identity: the coupling enabled at s = 1 against the world without the operator.
(a) Every @3 state field of every accepted row (the step, through control_view) and (b) every @3
observation column (through held_schedules) are compared and reported separately; the record is
written under CELLS_COMPONENT_EVIDENCE when the gate sets it. A negative control shows the
population's availability matters here: 1/2 and 1 differ in the step.
"""

import json
import os
from pathlib import Path

import numpy as np

from cells.core.runner import run
from cells.core.specs import parse_spec
from validation.tissue import regulated_availability_fixtures as rf

END = 0.03
CHANNEL, CELL = "kir_3", "cell_3"
ARMS = (("half", 0.5), ("zero", 0.0), ("identity", 1.0))
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")


def factored(value):
    return rf.with_coupling(
        rf.sheet(end=END),
        species=["R"],
        states=[rf.frozen("s", [CELL], value)],
        couplings=[rf.fraction("c", "channel", [CHANNEL], "s")],
    )


def scheduled(value):
    return rf.schedule_channel(rf.sheet(end=END), CHANNEL, value)


def test_p1_the_factored_channel_path_is_the_scheduled_one():
    record, held_runs = {}, {}
    for name, value in ARMS:
        result = run(parse_spec(factored(value)))
        held_runs[name] = run(parse_spec(scheduled(value)))
        fields, columns = rf.differing(result, held_runs[name])
        record[name] = dict(
            availability=value,
            a_step_fields_differing=fields,
            b_observation_columns_differing=columns,
            observed_factor_exact=bool(
                np.all(np.asarray(result.observations.coupling_factor) == value)
            ),
        )
    control, _ = rf.differing(held_runs["half"], held_runs["identity"])
    record["negative_control_half_against_one_step_fields_differing"] = control
    if EVIDENCE:
        Path(EVIDENCE).mkdir(parents=True, exist_ok=True)
        (Path(EVIDENCE) / "p1.json").write_text(json.dumps(record, indent=1) + "\n")
    arms = [record[name] for name, _ in ARMS]
    assert all(not arm["a_step_fields_differing"] for arm in arms), record  # (a) control_view
    assert all(not arm["b_observation_columns_differing"] for arm in arms), record  # (b) held
    assert all(arm["observed_factor_exact"] for arm in arms), record
    assert control, record  # Not vacuous.
