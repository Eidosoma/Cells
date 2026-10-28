"""CPU construction checks for meaningful coupled response horizons."""

import json
import os
from pathlib import Path

import numpy as np
import pytest

from cells.core.runner import timeline
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.models import surface_cotransport_water as model
from validation.tissue import surface_cotransport_water_fixtures as short
from validation.tissue import surface_cotransport_water_response as panel


@pytest.mark.parametrize("arm", panel.ARMS)
def test_response_horizon_controls_and_remaining_step_limits(arm):
    raw = panel.definition(arm)
    spec = parse_spec(raw)
    grid = timeline(spec)
    assert not spec.model.channels and len(model.initial_values(spec)[0]) == 31
    assert grid[-1] == 0.5 and 0.25 in grid
    assert set(spec.experiment.observation_times) <= set(grid)
    assert np.max(np.diff(grid)) > 1.25e-6
    assert spec == parse_spec(spec.to_dict())
    duration = panel.duration_inputs(raw)
    assert duration["pre_intervention_water_time_constants"] >= 5
    assert duration["post_intervention_water_time_constants"] >= 5
    controls = control_values(spec, [0.0, np.nextafter(0.25, 0), 0.25, 0.5])
    if arm == "supply_recovery":
        np.testing.assert_array_equal(controls.regeneration[:, 0], [0, 0, 0.1, 0.1])
    if arm == "cotransport_release":
        np.testing.assert_array_equal(controls.cotransport[:, 0], [0, 0, 1, 1])
    # Removing channels does not remove the remaining physical safeguards.
    oversized = panel.definition(arm, dt=0.01)
    oversized["experiment"]["observation_times"] = [0.0, panel.END_TIME]
    with pytest.raises(ConfigError):
        timeline(parse_spec(oversized))
    path = os.environ.get("CELLS_COMPONENT_EVIDENCE")
    if path:
        root = Path(path) / "cpu"
        root.mkdir(parents=True, exist_ok=True)
        (root / f"response-setup-{arm}.json").write_text(
            json.dumps(
                dict(
                    status="passed",
                    inputs=raw,
                    duration=duration,
                    accepted_steps=len(grid) - 1,
                    controls=controls._asdict(),
                ),
                default=lambda value: value.tolist(),
                indent=2,
                allow_nan=False,
            )
            + "\n"
        )


@pytest.mark.parametrize("state", ["present", "blocked", "zero_permeability"])
def test_present_channel_gates_keep_their_original_ceiling(state):
    raw = short.definition("coupled", dt=2.5e-6)
    if state == "blocked":
        for group in raw["experiment"]["channel_controls"]:
            group["schedule"] = [dict(time=0.0, availability=0.0)]
    elif state == "zero_permeability":
        for channel in raw["model"]["channels"]:
            channel["max_permeability_m_per_s"] = 0.0
    with pytest.raises(ConfigError, match="1.25 us"):
        timeline(parse_spec(raw))


def test_arms_change_only_one_declared_control_family():
    baseline = panel.definition()
    families = dict(
        supply_off="regeneration_controls",
        supply_recovery="regeneration_controls",
        cotransport_blocked="cotransport_controls",
        cotransport_release="cotransport_controls",
        water_blocked="water_controls",
    )
    for arm, family in families.items():
        raw = panel.definition(arm)
        assert raw["model"] == baseline["model"] and raw["execution"] == baseline["execution"]
        assert {
            k for k in raw["experiment"] if raw["experiment"][k] != baseline["experiment"][k]
        } == {family}


def test_fast_initial_transient_keeps_energy_budget_before_long_launch():
    """Check accumulated early error; this does not replace the half-second panel."""
    rows = []
    for factor in (1, 2, 4):
        spec = parse_spec(panel.definition(dt=panel.DT / factor))
        state, p = model.initial_values(spec)
        table = control_values(spec, [0.0])
        held = type(table)(*(v[0] for v in table))
        dt = panel.DT / factor
        history = [state]
        for _ in range(40 * factor):
            slopes = []
            for scale in (0.0, 0.5, 0.5, 1.0):
                trial = (
                    state
                    if not slopes
                    else model.STATE_TYPE(
                        *(a + dt * scale * b for a, b in zip(state, slopes[-1], strict=True))
                    )
                )
                assert model.control_domain_valid(trial, held, p, p.active, xp=np)
                slopes.append(model.rhs(trial, held, p, p.active, xp=np))
            state = model.STATE_TYPE(
                *(
                    a + dt * (b + 2 * c + 2 * d + e) / 6
                    for a, b, c, d, e in zip(state, *slopes, strict=True)
                )
            )
            history.append(state)
        history = model.STATE_TYPE(*map(np.stack, zip(*history, strict=True)))
        diagnostics = model.check_values(history, spec)
        rows.append(dict(dt_s=dt, steps=40 * factor, diagnostics=diagnostics))
    path = os.environ.get("CELLS_COMPONENT_EVIDENCE")
    if path:
        target = Path(path) / "cpu" / "response-initial-transient.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                dict(
                    status="captured",
                    horizon_s=0.0005,
                    scope="Early accumulated numerical error only",
                    grids=rows,
                ),
                indent=2,
                allow_nan=False,
            )
            + "\n"
        )
    errors = [row["diagnostics"]["max_energy_balance_error_pJ"] for row in rows]
    assert max(errors) <= 2e-8, errors
    assert errors[-1] <= max(3e-13, 0.2 * errors[0]), errors
    if path:
        record = json.loads(target.read_text())
        record["status"] = "passed"
        target.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
