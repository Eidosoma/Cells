"""Scalar windows with their rows checked on the device: WindowPolicy row_checks="device".

docs/WINDOW_DEVICE_CHECKS_DESIGN.md §9, the lead's conditions C1–C3, on cells.model.resolved_pump_tissue@1:
- C1: in device mode every window's times, history, observations and final checkpoint are host
  mode's, bitwise, at windows of 4 and 7 steps (a partial last window included) and after a
  restart from a host-mode checkpoint;
- C2: each device-decided window's diagnostics agree with the host's check of the same rows,
  under the host's keys in its order; faults at a window's first row, at the partial last
  window's last row and a dissipation decrease across a window boundary are caught and refused
  exactly as in host mode;
- C3: a ledger residual over its bound that the device under-reads into the band (1/2, 1] is
  handed back and refused by the host, which a band at 1 would have accepted; a residual in the
  band is handed back and the run goes on, bitwise.
One step double serves every case, so the file compiles each program once: the model's own
step, plus planted work or a dissipation drop at steps whose first pump availability is a
marker value. Unmarked steps add exactly zero.
"""

import json

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution import row_checks
from cells.execution.errors import NumericalError
from cells.execution.grid import EventGrid
from cells.execution.windows import WindowPolicy, iter_windows, run_windowed
from cells.models import surface_pump
from cells.numerics import surface_imex as imex
from cells.records.window_io import write_windowed_run
from tests.window_row_check_fixtures import assert_agreement, assert_same_windows, windows
from validation.tissue import surface_pump_fixtures

# The fixture's grid to 1.2 ms: 0.1 ms steps with its pump change at 0.73 ms, 13 steps.
SMALL, LARGE = 0.75, 0.76  # Marker availabilities of the first pump: planted metabolic work.
DROP = 1e-9  # A marker that nearly stops the first pump, whose heat then drops (below).
WORK = {SMALL: 1.05e-12, LARGE: 1e-10}  # pJ added to the first pump's metabolic work per step.
HEAT_DROP_PJ = 2e-12  # A DROP step ends this far below its start's first-pump heat.
LEDGER = "metabolic_work"  # Bound 3e-12 pJ: SMALL is 0.35 of it per marked step.


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def planted(original):
    def step(state, dt, control, p, active):
        updated, ok = original(state, dt, control, p, active)
        mark = control.pump[0]  # Only the first pump is planted: padding must stay empty.
        work = updated.metabolic_work_pJ
        work = work.at[0].add(
            sum(jnp.where(mark == value, delta, 0.0) for value, delta in WORK.items())
        )
        heat = updated.pump_dissipated_energy_pJ
        heat = heat.at[0].set(
            jnp.where(mark == DROP, state.pump_dissipated_energy_pJ[0] - HEAT_DROP_PJ, heat[0])
        )
        return updated._replace(metabolic_work_pJ=work, pump_dissipated_energy_pJ=heat), ok

    return step


def under_reading(original, factor=0.5):
    """The device checks with LEDGER's ratio read at factor of its value (a device that
    disagrees with the host near the bound): its failure bit follows the reduced ratio."""
    index = surface_pump.LEDGERS.index(LEDGER)

    def checks(previous, row, p, constants, steps, *, margins=False):
        failed, values, ratios = original(previous, row, p, constants, steps, margins=True)
        ratio = factor * ratios[index]
        out = (failed.at[1 + index].set(ratio > 1), values, ratios.at[index].set(ratio))
        return out if margins else out[:2]

    return checks


PLANTED = planted(surface_pump.checked_step)
UNDER_READ = under_reading(surface_pump.device_checks)


@pytest.fixture(scope="module", autouse=True)
def step_double():
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(surface_pump, "checked_step", PLANTED)
        yield


def definition(marks=(), observations=(0.0, 0.0007, 0.0012)):
    """The fixture's release arm to 1.2 ms. marks: (first, last, marker): the first pump holds
    marker over steps first..last (last None: to the end), at the grid's own times."""
    raw = surface_pump_fixtures.definition("release", solver=imex.ARS222_ID)
    raw["experiment"]["end_time"] = 0.0012
    raw["experiment"]["observation_times"] = list(observations)
    control = raw["experiment"]["pump_controls"][0]
    base, grid = control["schedule"], EventGrid(parse_spec(raw))
    entries = {e["time"]: e["availability"] for e in base}
    for first, last, marker in marks:
        if last is not None:
            end = float(grid[last])
            entries.setdefault(end, [e["availability"] for e in base if e["time"] <= end][-1])
        entries[float(grid[first - 1])] = marker
    control["schedule"] = [dict(time=t, availability=a) for t, a in sorted(entries.items())]
    return parse_spec(raw)


def refusal(spec, width, mode):
    """(windows yielded, the exception) of a run that must be refused."""
    seen = []
    with pytest.raises(NumericalError) as caught:
        for window in iter_windows(spec, WindowPolicy(width, "checkpoints", mode)):
            seen.append(window)
    return seen, caught.value


@pytest.fixture(scope="module")
def runs():
    spec = definition()
    return spec, {(w, m): windows(spec, w, m) for w in (4, 7) for m in ("host", "device")}


@pytest.mark.parametrize("width", [4, 7])
def test_device_mode_keeps_every_array_at_any_window(width, runs):
    _, out = runs
    host, device = out[width, "host"], out[width, "device"]
    assert [len(w.times) - 1 for w in host] == ([4, 4, 4, 1] if width == 4 else [7, 6])
    assert_same_windows(host, device)
    assert all(w.row_checks.decided_by == "device" for w in device)


def test_device_diagnostics_agree_with_the_host_check_of_the_same_rows(runs):
    spec, out = runs
    for width in (4, 7):
        assert assert_agreement(spec, out[width, "host"], out[width, "device"]) == len(
            out[width, "device"]
        )


def test_a_restart_in_device_mode_from_a_host_checkpoint_is_bitwise(runs):
    spec, out = runs
    host = out[4, "host"]
    resumed = windows(spec, 4, "device", host[1].final)
    assert_same_windows(host[2:], resumed)


def test_the_windowed_writer_records_device_outcomes_and_keeps_host_records(runs, tmp_path):
    spec, _ = runs
    for mode in ("host", "device"):
        write_windowed_run(tmp_path / mode, spec, WindowPolicy(4, "checkpoints", mode))
    read = lambda mode, name: json.loads((tmp_path / mode / name).read_text())  # noqa: E731
    lines = {
        mode: [json.loads(line) for line in (tmp_path / mode / "windows.jsonl").open()]
        for mode in ("host", "device")
    }
    assert [set(line) | {"row_checks"} for line in lines["host"]] == [
        set(line) for line in lines["device"]
    ]
    assert [line["row_checks"]["decided_by"] for line in lines["device"]] == ["device"] * 4
    host, device = read("host", "manifest.json"), read("device", "manifest.json")
    assert host["policy"] == {"window_steps": 4, "recording": "checkpoints"}
    assert device["policy"] == host["policy"] | {"row_checks": "device"}
    assert "row_checks" not in host["resources"]
    assert device["resources"]["row_checks"]["windows"] == 4
    with (
        np.load(tmp_path / "host/checkpoint_final/state.npz") as a,
        np.load(tmp_path / "device/checkpoint_final/state.npz") as b,
    ):
        assert sorted(a.files) == sorted(b.files)
        assert all(a[k].tobytes() == b[k].tobytes() for k in a.files)


@pytest.mark.parametrize(
    ("mark", "windows_before", "message"),
    [
        ((5, 5, LARGE), 1, surface_pump.LEDGER_MESSAGE + LEDGER),  # Window 1's first row.
        ((13, None, LARGE), 3, surface_pump.LEDGER_MESSAGE + LEDGER),  # The last window's last.
        ((13, None, DROP), 3, surface_pump.DISSIPATION_MESSAGE),  # Below its window's start row.
    ],
    ids=["first-row", "last-row", "dissipation-across-boundary"],
)
def test_a_fault_at_a_window_edge_is_refused_as_in_host_mode(mark, windows_before, message):
    spec = definition([mark])
    host_seen, host_error = refusal(spec, 4, "host")
    assert (len(host_seen), str(host_error)) == (windows_before, message)
    if mark[2] == DROP:  # A decrease from the window's start row, not a negative heat.
        assert host_seen[-1].history.pump_dissipated_energy_pJ[-1, 0] > 2 * HEAT_DROP_PJ
    seen, error = refusal(spec, 4, "device")
    assert (type(error), str(error)) == (type(host_error), str(host_error))
    assert_same_windows(host_seen, seen)


def report(spec, width):
    return run_windowed(spec, WindowPolicy(width, "checkpoints", "device")).resources["row_checks"]


def test_a_ledger_the_device_under_reads_into_the_band_is_refused_by_the_host(monkeypatch):
    # Steps 9-12: 1.4 x the bound after them. Observed only before them, so that only the
    # window checks see the planted rows (the host checks observed rows across windows too).
    spec = definition([(9, 12, SMALL)], observations=(0.0, 0.0007))
    host_seen, host_error = refusal(spec, 4, "host")
    assert str(host_error) == surface_pump.LEDGER_MESSAGE + LEDGER
    monkeypatch.setattr(surface_pump, "device_checks", UNDER_READ)
    seen, error = refusal(spec, 4, "device")
    assert (type(error), str(error)) == (type(host_error), str(host_error))
    assert_same_windows(host_seen, seen)
    # The control: without the band the device's word (at most 0.7 of the bound) accepts it.
    monkeypatch.setattr(row_checks, "HOST_DECIDES_ABOVE", 1.0)
    accepted = report(spec, 4)
    assert accepted["host_decided"] == {"failed": 0, "above_band": 0}
    assert 0.5 < accepted["max_ratios"][LEDGER] <= 1.0


def test_a_residual_in_the_band_is_handed_back_and_the_run_goes_on():
    spec = definition([(9, 10, SMALL)])  # Steps 9 and 10: 0.7 x the bound after them.
    host, device = windows(spec, 4, "host"), windows(spec, 4, "device")
    assert_same_windows(host, device)
    decided = [(w.row_checks.decided_by, w.row_checks.handed_back) for w in device]
    assert decided == [("device", None)] * 2 + [("host", "above_band")] * 2
    assert 0.5 < device[2].row_checks.ratios[LEDGER] <= 1.0
    assert [w.diagnostics for w in device[2:]] == [w.diagnostics for w in host[2:]]
    counts = report(spec, 4)
    assert (counts["windows"], counts["host_decided"]["above_band"]) == (4, 2)
