"""G0 re-host probe: the two-task fixture builds on resolved_tissue@2 and steps stably."""

import json

import jax
import numpy as np
import pytest

from validation.assays import rehost_probe as probe
from validation.assays import two_task
from validation.betse.emulator.rehost import moved

pytestmark = pytest.mark.skipif(
    not probe.VM0_SOURCE.exists(), reason="saved initial-voltage observation not available"
)


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def raw_case(arm):
    rule = two_task.protocol()
    base = json.load(open(moved("configs/betse_spatial_junction.json")))
    case = next(
        c
        for c in two_task.cases(rule)
        if c["arm"] == arm
        and c["preparation"] == "calibration_low"
        and c["location"] == 0
        and c["timing"] == 0
    )
    return two_task.definition(base, case, "cpu", rule)


def test_definition_counts_and_schedules():
    vm0, _ = probe.initial_patch_voltage()
    d = probe.resolved_definition(raw_case("joint"), dt=6.25e-8, vm0=vm0)
    m = d["model"]
    assert (len(m["cells"]), len(m["extracellular"]), len(m["membranes"])) == (7, 100, 30)
    assert len(m["channels"]) == 30 and len(m["junctions"]) == 12
    assert sum(s["reservoir"] for s in m["extracellular"]) == 36
    cue = [c for c in d["experiment"]["channel_controls"] if len(c["schedule"]) > 1]
    assert cue and all(
        c["channel_id"] in ("channel_0", "channel_1", "channel_2", "channel_3") for c in cue
    )
    no_cue = probe.resolved_definition(raw_case("no_cue"), dt=6.25e-8, vm0=vm0)
    assert all(len(c["schedule"]) == 1 for c in no_cue["experiment"]["channel_controls"])


def test_short_run_is_finite_and_the_cue_changes_voltage():
    vm0, _ = probe.initial_patch_voltage()
    raws = {a: probe.shorten(raw_case(a), 10e-6) for a in ("joint", "no_cue")}
    out = {a: probe.run_case(r, 6.25e-8, vm0)[1] for a, r in raws.items()}
    assert all(np.isfinite(v).all() for v in out.values())
    assert np.max(np.abs(out["joint"] - out["no_cue"])) > 0
