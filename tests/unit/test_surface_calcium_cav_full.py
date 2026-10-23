"""Reuse complete HCN/calcium qualification with shared CaV populations active.

The adapter changes inputs/model identity, not physical tolerances or checks.
Every inherited test remains a separately collected node in the protocol.
"""

import pytest

from cells.core.runner import branch_checkpoint
from cells.core.specs import ConfigError, parse_spec
from cells.models import surface_calcium_cav as model
from tests.unit import test_surface_calcium as shared
from tests.unit import test_surface_calcium_cav as wiring
from tests.unit import test_surface_calcium_hcn as hcn_wiring
from tests.unit import test_surface_calcium_hcn_full as suite
from validation.tissue import surface_calcium_cav_fixtures as fixtures

PREFIX = wiring.PREFIX
_heterogeneous = suite.heterogeneous_definition
REFINEMENT_STEPS = (1.25e-6, 0.625e-6, 0.3125e-6)
BATCH_STEP_BUDGET = 4096
SINGLE_WORLD_STEP_BUDGET = 2048
BATCH_WORKING_BYTES = 2**32
ASSEMBLY_TICKS = 1600


def heterogeneous_definition(*, backend="cpu"):
    raw = _heterogeneous(backend=backend)
    # Also change a new population's inactivation power in the second world.
    raw["model"]["ionic"]["channels"][10]["kinetic_law"] = "betse_kv1p6_mh@1"
    raw["model"]["ionic"]["channels"][17]["kinetic_law"] = "betse_cav2p3_mh@1"
    return raw


@pytest.fixture(scope="module", autouse=True)
def composition_context():
    with pytest.MonkeyPatch.context() as patch:
        for module in (shared, hcn_wiring, suite):
            patch.setattr(module, "model", model)
            patch.setattr(module, "fixtures", fixtures)
            patch.setattr(module, "PREFIX", PREFIX)
        patch.setattr(suite, "wiring", wiring)
        patch.setattr(suite, "heterogeneous_definition", heterogeneous_definition)
        patch.setattr(shared, "reference", suite.reference)
        for name in (
            "REFINEMENT_STEPS",
            "BATCH_STEP_BUDGET",
            "SINGLE_WORLD_STEP_BUDGET",
            "BATCH_WORKING_BYTES",
            "ASSEMBLY_TICKS",
        ):
            patch.setattr(suite, name, globals()[name])
            if name != "ASSEMBLY_TICKS":
                patch.setattr(shared, name, globals()[name])
        patch.setattr(shared, "REPLAY_WINDOW_STEPS", 17)
        yield


trajectories = suite.trajectories
coupled = suite.coupled
references = suite.references

# Reuse the exact physical, replay, reporting and numerical assertions. The
# runner checks exact collection and disjoint groups against frozen sources.
globals().update({name: value for name, value in vars(suite).items() if name.startswith("test_")})


@pytest.mark.parametrize("change", ["law", "species_and_law", "kv1_gate_power", "cav_gate_power"])
def test_restart_rejects_changed_population(trajectories, change):
    if change in ("law", "species_and_law"):
        return suite.test_restart_rejects_changed_population(trajectories, change)
    value = trajectories["baseline"]
    raw = value.spec.to_dict()
    if change == "kv1_gate_power":
        raw["model"]["ionic"]["channels"][10]["kinetic_law"] = "betse_kv1p2_mh@1"
    else:
        raw["model"]["ionic"]["channels"][17]["kinetic_law"] = "betse_cav2p3_mh@1"
    alternative = parse_spec(raw)
    with pytest.raises(ConfigError, match="model or execution"):
        branch_checkpoint(value.spec, value.checkpoint_at(0.001), alternative)
    wiring.evidence(
        "identity-" + change, dict(status="passed", changed_population_branch_rejected=True)
    )
