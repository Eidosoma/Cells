"""Projective forward Euler numerics and the execution.projective block (no runs).

The extrapolation is affine with coefficients summing to one, so linear
identities survive it to rounding; the error estimate and its inverse agree;
the cycle amplification matches a direct linear simulation; the block parses
strictly, round-trips, and leaves definitions without it unchanged; fine-only
execution paths refuse a definition that declares it.
"""

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from cells.core.specs import ConfigError, parse_spec
from cells.numerics import projective as method
from validation.tissue import projective_fixtures as fixtures

ROOT = Path(__file__).resolve().parents[2]


def definition(end_time=10.0, **block):
    raw = fixtures.pump_cells([fixtures.H], end_time=end_time)
    raw["execution"]["projective"] = fixtures.projective_block([(1.0, end_time)], **block)
    return raw


@pytest.fixture(scope="module")
def parsed():
    return parse_spec(definition())


def test_extrapolation_is_affine_and_keeps_linear_identities():
    rng = np.random.default_rng(7)
    weights = rng.normal(size=12)
    # Rows on the plane w.y = 3 to rounding; padding and held values are equal.
    rows = []
    for _ in range(2):
        y = rng.normal(size=12) * 50
        y[0] += (3 - weights @ y) / weights[0]
        rows.append((y, np.zeros(4), np.full(3, 1.25)))
    for ratio in (0.5, 7.0, 3.3e3):
        last, base = rows[1], rows[0]
        jumped = method.extrapolate(last, base, ratio)
        predicted = weights @ last[0] + ratio * (weights @ last[0] - weights @ base[0])
        scale = (1 + 2 * ratio) * np.sum(np.abs(weights) * np.maximum(abs(last[0]), abs(base[0])))
        assert abs(weights @ jumped[0] - predicted) <= 8 * np.finfo(float).eps * scale
        assert abs(weights @ jumped[0] - 3) <= 8 * np.finfo(float).eps * scale
        np.testing.assert_array_equal(jumped[1], np.zeros(4))
        np.testing.assert_array_equal(jumped[2], np.full(3, 1.25))
    # Exactly representable values and a power-of-two ratio: the identity is exact.
    a, b = np.array([3.0, -1.0, 6.0]), np.array([2.0, 0.5, 5.5])  # Both sum to 8.
    jumped = method.extrapolate((a,), (b,), 4.0)
    assert np.sum(jumped[0]) == 8.0
    with pytest.raises(ValueError):
        method.extrapolate((a,), (b,), -1.0)


def test_error_estimate_and_admissible_jump_are_inverse():
    for settle, curvature, span in ((0.0, 0.0, 0.25), (0.02, 0.0, 0.25), (0.0, 1e-4, 0.25),
                                     (3e-3, 2e-5, 0.5)):  # fmt: skip
        duration = method.admissible_jump(settle, curvature, span, 0.5)
        if settle == curvature == 0:
            assert duration == np.inf
            continue
        assert method.error_estimate(duration, settle, curvature, span) == pytest.approx(0.5)
        assert method.error_estimate(1.01 * duration, settle, curvature, span) > 0.5
    assert method.admissible_jump(1.0, 1.0, 0.1, 0.0) == 0.0


def test_cycle_amplification_matches_a_linear_simulation():
    burst, slope, ratio = 40, 10, 25.0
    for rho in (0.995, 0.9, 0.3, -0.5, 0.97 + 0.05j):
        y = [1.0 + 0j]
        for _ in range(burst):
            y.append(rho * y[-1])
        jumped = y[-1] + ratio * (y[-1] - y[-1 - slope])
        assert method.cycle_amplification(rho, burst, slope, ratio) == pytest.approx(jumped)
    # A slow mode rho = exp(lambda h) grows like exp(lambda (K + r m) h) to first order.
    h, lam = 1e-3, -0.01
    value = method.cycle_amplification(np.exp(lam * h), burst, slope, ratio)
    cycle = lam * h * (burst + ratio * slope)
    assert abs(value - np.exp(cycle)) < cycle**2  # Second-order remainder.
    # A strongly damped fast mode is contracted; an undamped one is amplified.
    assert abs(method.cycle_amplification(0.3, burst, slope, ratio)) < 1e-13
    assert abs(method.cycle_amplification(0.999, burst, slope, 1e3)) > 1


def test_block_parses_strictly_and_round_trips(parsed):
    block = parsed.projective
    assert block.method == method.METHOD_ID and block.windows[0].start_time == 1.0
    assert block.jump.rule == "error_controlled" and block.burst_steps == 2000
    raw = parsed.to_dict()
    assert raw["execution"]["projective"] == definition()["execution"]["projective"]
    assert parse_spec(raw) == parsed
    fixed = parse_spec(definition(rule="fixed", max_steps=5000, min_steps=500))
    assert fixed.projective.jump.max_steps == 5000 and fixed.projective.jump.max_growth is None
    assert parse_spec(fixed.to_dict()) == fixed


@pytest.mark.parametrize(
    "edit",
    [
        lambda b: b.update(method="projective_forward_euler@2"),
        lambda b: b.update(extra=1),
        lambda b: b.pop("tolerance"),
        lambda b: b.update(windows=[dict(start_time=2.0, end_time=1.0)]),
        lambda b: b.update(windows=[dict(start_time=0.0, end_time=11.0)]),
        lambda b: b.update(
            windows=[dict(start_time=0.0, end_time=5.0), dict(start_time=4.0, end_time=6.0)]
        ),
        lambda b: b.update(slope_steps=1001),
        lambda b: b.update(burst_steps=1),
        lambda b: b["jump"].update(min_steps=10**6),
        lambda b: b["jump"].update(max_growth=1.0),
        lambda b: b["jump"].update(safety_factor=1.5),
        lambda b: b["jump"].update(rule="adaptive"),
        lambda b: b["tolerance"].update(gate=0.0),
        lambda b: b["safety"].update(rejection_shrink=1.0),
        lambda b: b["safety"].update(cooldown_bursts=-1),
        lambda b: b["safety"].pop("max_correction"),
        lambda b: b.update(row_checks="gpu"),
        lambda b: b.pop("row_checks"),
    ],
)
def test_block_errors_reject(edit):
    raw = definition()
    edit(raw["execution"]["projective"])
    with pytest.raises(ConfigError):
        parse_spec(raw)


def test_unsupported_model_rejects():
    raw = json.loads((ROOT / "configs/multispecies_baseline.json").read_text())
    end = raw["experiment"]["end_time"]
    raw["execution"]["projective"] = fixtures.projective_block([(0.0, end)])
    with pytest.raises(ConfigError, match="supports"):
        parse_spec(raw)


def test_definitions_without_the_block_are_unchanged():
    for name in ("resolved_pump_tissue.json", "multispecies_baseline.json"):
        raw = json.loads((ROOT / "configs" / name).read_text())
        spec = parse_spec(copy.deepcopy(raw))
        assert spec.projective is None
        assert "projective" not in spec.to_dict()["execution"]
        assert parse_spec(spec.to_dict()) == spec


def test_fine_only_paths_refuse_and_branches_keep_the_block(parsed):
    from cells.core import runner, windows
    from cells.core.batch import BatchSpec, WorldSpec, plan_batch
    from cells.core.state import initialise

    with pytest.raises(ConfigError, match="projective"):
        runner.timeline(parsed)
    with pytest.raises(ConfigError, match="projective"):
        windows.run_windowed(parsed)
    with pytest.raises(ConfigError, match="projective"):
        plan_batch(BatchSpec((WorldSpec(1, parsed),), 1, 10**9, 2**40))
    changed = definition()
    changed["execution"]["projective"]["burst_steps"] = 1000
    with pytest.raises(ConfigError, match="branch"):
        runner.branch_checkpoint(parsed, initialise(parsed), parse_spec(changed))
