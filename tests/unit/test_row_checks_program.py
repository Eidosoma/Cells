"""The scalar windows' device row check program and its admission (execution/row_checks.py).

docs/WINDOW_DEVICE_CHECKS_DESIGN.md §9.3. A stub model's device checks see exactly the rows
the host check sees: row 0 (the window's start, its own predecessor), then each real row with
its predecessor and its global step count; slots past the window's real steps never count.
The decision hands a window to the host on any failed check or any ratio above the band,
NaN included. Device mode is refused, fail-closed, wherever it cannot serve: a run that is not
compiled, a model without device checks or margins, a model whose device diagnostics are not
its host diagnostics, the batch and vector paths, and from the CLI. It is also refused where
it is not yet qualified: a GPU backend and a composition with a live retiring operator.
"""

import json
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.execution import row_checks
from cells.execution.batch import BatchSpec, WorldSpec
from cells.execution.batch_windows import plan_batch_windows
from cells.execution.vector_windows import plan_vector_windows
from cells.execution.windows import WindowPolicy, iter_windows, plan_windows
from cells.models import surface_pump
from cells.numerics import surface_imex as imex
from tests.integration.test_cli import cli
from validation.tissue import surface_pump_fixtures

WIDTH, FIRST_STEP, PADDING = 8, 100, 999.0
CHECKS = ("domain", "chain", "dissipation")  # The stub's checks: (marked, chain, unused).


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


class Row(NamedTuple):
    x: object  # [1] the row's index in its window (row 0: the start)
    bad: object  # [1] nonzero marks a failing row


class Parameters(NamedTuple):
    scale: object


def stub_checks(previous, row, p, constants, steps, *, margins=False):
    """Fails "domain" on a marked row and "chain" when previous is neither the row itself
    (row 0) nor the row before it; reports the row's index and step count; one ledger."""
    x, before = row.x[0], previous.x[0]
    failed = jnp.stack([row.bad[0] > 0, (before != x) & (before != x - 1), jnp.asarray(False)])
    values = jnp.stack([x, steps.astype(x.dtype)])
    if margins:
        return failed, values, jnp.stack([x * p.scale])
    return failed, values


def window(count, *, start_bad=0.0, marked=(), broken=()):
    """A start row and a full-width history: real rows 1..count, padding beyond them that
    would fail both checks if it were read."""
    x = np.where(np.arange(1, WIDTH + 1) <= count, np.arange(1, WIDTH + 1), PADDING)
    bad = np.where(np.arange(1, WIDTH + 1) <= count, 0.0, 1.0)
    for k in marked:
        bad[k - 1] = 1.0
    for k in broken:
        x[k - 1] = 7.5  # Neither its predecessor's successor nor its own predecessor.
    start = Row(jnp.zeros(1), jnp.full(1, start_bad))
    return start, Row(jnp.asarray(x)[:, None], jnp.asarray(bad)[:, None])


def summary(count, **plants):
    start, history = window(count, **plants)
    out = row_checks._compiled_window_checks(
        start,
        history,
        np.int64(count),
        np.int64(FIRST_STEP),
        Parameters(jnp.asarray(0.1)),
        None,
        checks=stub_checks,
    )
    return row_checks.Summary(*(np.asarray(v) for v in out))


@pytest.mark.parametrize("count", [5, WIDTH])
def test_the_program_reads_row_zero_and_each_real_row_with_its_predecessor_and_steps(count):
    s = summary(count)
    assert s.first.tolist() == [-1, -1, -1]  # The padding fails both checks: never read.
    assert s.maxima.tolist() == [count, FIRST_STEP + count]
    assert s.ratios.tolist() == [pytest.approx(0.1 * count)]


@pytest.mark.parametrize(
    ("plants", "expected"),
    [
        (dict(start_bad=1.0), [0, -1, -1]),  # Row 0, the window's start, is checked.
        (dict(marked=(5,)), [5, -1, -1]),  # The last real row is checked.
        (dict(marked=(2, 4)), [2, -1, -1]),  # Each check's first failing row.
        (dict(broken=(3,)), [-1, 3, -1]),  # Row 3's predecessor is row 2: the chain breaks.
    ],
)
def test_the_first_failing_row_of_each_check(plants, expected):
    assert summary(5, **plants).first.tolist() == expected


@pytest.mark.parametrize(
    ("first", "ratio", "decided", "reason"),
    [
        ([-1, -1, -1], row_checks.HOST_DECIDES_ABOVE, "device", None),  # At the band: device.
        ([-1, -1, -1], np.nextafter(row_checks.HOST_DECIDES_ABOVE, 1.0), "host", "above_band"),
        ([-1, -1, -1], np.nan, "host", "above_band"),  # NaN is not within the band.
        ([-1, -1, -1], np.inf, "host", "above_band"),
        ([-1, 2, -1], 0.0, "host", "failed"),  # A failure decides before the margins.
    ],
)
def test_the_device_decides_only_clean_windows_within_the_band(first, ratio, decided, reason):
    s = row_checks.Summary(np.array(first), np.zeros(2), np.array([ratio]))
    outcome = row_checks.decide(s, CHECKS, ("chain",))
    assert (outcome.decided_by, outcome.handed_back) == (decided, reason)
    assert outcome.failing == ({"chain": 2} if reason == "failed" else {})


# ------------------------------------------------------------------ admission and refusals


def definition(**execution):
    raw = surface_pump_fixtures.definition("release", solver=imex.ARS222_ID)
    raw["experiment"]["end_time"] = 0.0012
    raw["experiment"]["observation_times"] = [0.0, 0.0012]
    raw["execution"].update(execution)
    return raw


def test_the_policy_records_row_checks_only_in_device_mode():
    assert WindowPolicy(5, "checkpoints").to_dict() == {
        "window_steps": 5,
        "recording": "checkpoints",
    }
    device = WindowPolicy(5, "checkpoints", "device")
    assert device.to_dict() == {
        "window_steps": 5,
        "recording": "checkpoints",
        "row_checks": "device",
    }
    assert WindowPolicy(**device.to_dict()) == device
    for value in ("Device", "", None, True):
        with pytest.raises(ConfigError, match="row_checks must be host or device"):
            WindowPolicy(5, "checkpoints", value)


def test_device_mode_refuses_what_it_cannot_serve(monkeypatch):
    policy = WindowPolicy(3, "checkpoints", "device")
    plan_windows(parse_spec(definition()), policy)  # Admitted.
    with pytest.raises(ConfigError, match="requires a compiled run"):
        plan_windows(parse_spec(definition(jit=False)), policy)
    spec = parse_spec(definition())
    batch = BatchSpec((WorldSpec(1, spec),), 1, 2**53 - 1, 2**53 - 1)
    for planner in (plan_batch_windows, plan_vector_windows):
        with pytest.raises(ConfigError, match="scalar windowed path only"):
            planner(batch, policy)
    with monkeypatch.context() as patch:
        patch.setattr(surface_pump, "device_checks", lambda *a: None)
        with pytest.raises(ConfigError, match="device checks that report margins"):
            plan_windows(spec, policy)
    with monkeypatch.context() as patch:
        patch.delattr(surface_pump, "DEVICE_DIAGNOSTICS")
        with pytest.raises(ConfigError, match="missing DEVICE_DIAGNOSTICS"):
            plan_windows(spec, policy)
    with monkeypatch.context() as patch:  # Two diagnostic lists that drift apart fail closed.
        patch.setattr(surface_pump, "DEVICE_DIAGNOSTICS", surface_pump.DEVICE_DIAGNOSTICS[:-1])
        with pytest.raises(ConfigError, match="differ in max_global_charge_bound_ratio"):
            next(iter(iter_windows(spec, policy)))


def test_device_mode_is_refused_on_a_gpu_backend():
    """Not yet qualified (no GPU measurement): refused before any device is touched."""
    spec = parse_spec(definition(backend="gpu"))
    with pytest.raises(ConfigError, match="qualified on the CPU only"):
        plan_windows(spec, WindowPolicy(3, "checkpoints", "device"))
    plan_windows(spec, WindowPolicy(3, "checkpoints"))  # Host mode admits it.


SPARSE = "cells.solver.sparse_capacitive_reduction_gauged_damped_newton@1"


def test_vector_windows_refuse_the_composite_on_a_gpu():
    """D336: D330 measured the composite's device checks on a GPU and they failed, so the vector
    path, which decides on the device's word alone, refuses cells.model.resolved_pump_composite@1 on a GPU under
    every field solver, before any device is touched; on the CPU it is planned as before. The
    composite is GJ-N1's line (not blind), planned only."""
    from validation.gap_junction_tissue import neither

    dt = neither.step(1e-13, 2)
    raw = neither.coupled_world(1e-13, neither.STAGE1_END_UNITS, end=4 * dt, shape="line")
    for solver in ("cells.solver.capacitive_reduction_gauged_damped_newton@2", SPARSE):
        for backend in ("gpu", "cpu"):
            raw["execution"].update(field_solver=solver, backend=backend)
            batch = BatchSpec((WorldSpec(1, parse_spec(raw)),), 1, 2**53 - 1, 2**53 - 1)
            if backend == "cpu":
                plan_vector_windows(batch, WindowPolicy(3, "checkpoints"))
                continue
            with pytest.raises(ConfigError, match=r"not qualified on a GPU for \S*resolved_pump_c"):
                plan_vector_windows(batch, WindowPolicy(3, "checkpoints"))


def test_device_mode_is_refused_for_a_live_retiring_composition():
    """Not yet qualified: a dividing world's partition retires cells, so its device checks read
    adjusted rows, whose refusals have no planted test yet."""
    from validation.division import division_crossrev as division

    spec = parse_spec(division.division_worlds()["division_compact"])
    with pytest.raises(ConfigError, match="live retiring operator"):
        plan_windows(spec, WindowPolicy(3, "checkpoints", "device"))
    plan_windows(spec, WindowPolicy(3, "checkpoints"))  # Host mode admits it.


def test_the_cli_passes_row_checks_to_admission(tmp_path):
    config = tmp_path / "config.json"
    config.write_text(json.dumps(definition(jit=False)))
    refused = cli("windowed", "validate", config, "--row-checks", "device")
    assert refused.returncode == 2 and "requires a compiled run" in refused.stderr
    assert cli("windowed", "validate", config).returncode == 0
