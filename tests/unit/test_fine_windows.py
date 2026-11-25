"""C, the fine-window executor: execution.fine_windows (D235; definitions/fine_window_spec.py,
execution/grid.py; docs/LONG_DURATION_MODE_DESIGN.md §4.2, §4.4 and §4.5).

- The clock, without a compile. A declared window gives exactly the clock that today's event
  splitting gives the same definition with no-op events at its fine points (the lead's two-rate
  construction), with a cue on a fine point and an event between fine points inside it: for four
  (dt, fine dt) pairs near t = 1800 s, and for three windows of which two touch. Every step is a
  whole coarse step or a fine one; none is tiny. FR-8's arm (20 ms, 1 ms inside [1799.98,
  1802.00] s of 3600 s) takes 179,899 coarse and 2,020 fine steps. Without the block a definition
  serializes as before, and a run manifest's numerics name the windows' method only where they
  are declared (the gate's crossrev, G1 and FR's set hold runs and manifests bitwise). Every
  refusal, one row each, with a branch that changes the windows and the batch and vector paths.
- One compiled @3 world with X2 on: X2's own test world (the gap-junction network at dt/16, a
  resolved_pump_tissue@3 definition as FR-8's H2 is), a window at a quarter of its step, a
  membrane cue at a fine-only instant and a row observed at another. X2 passes across both
  switches; a restart from a checkpoint inside the window continues bit for bit (rows and X2's
  record) on the same compiled program; device row checks (WindowPolicy row_checks="device") give
  the host run bit for bit, each window decided on the device; the run's resources record the
  window. Its no-op twin (no block, no-op schedule entries at the fine points) feeds the compiled
  rollout the same inputs: the same clock, control table, initial checkpoint, parameters and X2
  event steps.
- One compiled composite world with a dose inside a window (scheduled_bath_composition@1, FR-10's
  dose leg under ARS(2,2,2) at its declared 1 ms, a fine step of 0.25 ms), without X2, which the
  block does not require: every check passes on every row, a row is observed at a fine-only
  instant, and the dose's step starts at its own time inside the window. Written through the
  windowed writer, its manifest names the windows' method and records them.

A new file for a new feature (D224, the lead's ruling). Two window programs, X2's doubled one of
the @3 world (the restart and the device run reuse it) and the composite's (its writer run reuses
it), and the device row checks' program.
"""

import dataclasses
import json
from types import SimpleNamespace

import jax
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.execution import energy_check as energy
from cells.execution.grid import EventGrid, manifest_numerics
from cells.execution.runner import branch_checkpoint, timeline
from cells.execution.schedule import control_values
from cells.execution.state import initialise
from cells.execution.windows import WindowPolicy, _plan_windows_metadata, iter_windows, run_windowed
from cells.records.window_io import write_windowed_run
from cells.registry.models import get_model
from tests.window_row_check_fixtures import assert_agreement, assert_same_windows
from validation.gap_junction_tissue import worlds
from validation.tissue import bath_schedule_fixtures as bfx

METHOD = "fixed_fine_windows@1"
X2 = dict(check="step_doubled_energy@1", integration_error_cap=3e-2)  # X2's test's cap.


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def block(fine, *windows):
    windows = [dict(start_time=a, end_time=b) for a, b in windows]
    return dict(method=METHOD, dt=fine, windows=windows)


def network(dt, end, *, schedule=(), noop=(), window=None, energy_check=False):
    """X2's test world (Figure 5a's network at g = 100, a resolved_pump_tissue@3 definition): dt
    and end as given, A's Norton membrane on `schedule` ((time, availability), ...), B's carrying
    no-op entries at `noop`, a fine_windows block `window` (or none) and X2 if asked."""
    net = worlds.figure5_network(100.0)
    raw = worlds.linear_network(net.cells, net.edges, net.probes, dt=dt)
    raw["experiment"].update(end_time=end, observation_times=[0.0, end])
    raw["execution"]["max_steps"] = 10**7
    controls = {c["membrane_id"]: c for c in raw["experiment"]["membrane_controls"]}
    controls["A_norton"]["schedule"] += [dict(time=t, availability=v) for t, v in schedule]
    controls["B_norton"]["schedule"] += [dict(time=t, availability=1.0) for t in noop]
    if energy_check:
        raw["execution"]["energy_check"] = dict(X2)
    if window is not None:
        raw["execution"]["fine_windows"] = window
    return raw


def fine_points(dt, fine, start, stop):
    """The fine points a window adds: (m i + r) x fine inside each coarse step it covers."""
    m = round(dt / fine)
    first, last = round(start / dt), round(stop / dt)
    return [(m * i + r) * fine for i in range(first, last) for r in range(1, m)]


def event_clock(spec, times):
    """Today's event splitting of spec's own clock without the block, with no-op events at times:
    the lead's two-rate construction, without parsing a definition that holds them (a resolved
    definition checks its domain at every schedule time, about 30 ms each)."""
    changes = sorted({*(c.time for c in spec.experiment.changes), *times})
    experiment = SimpleNamespace(
        end_time=spec.experiment.end_time, changes=tuple(SimpleNamespace(time=t) for t in changes)
    )
    return EventGrid(SimpleNamespace(experiment=experiment, execution=spec.execution))


# ------------------------------------------------------------------ the clock


@pytest.mark.parametrize(
    "dt, fine, spans",
    [
        (0.02, 0.001, [(89999, 90100)]),  # FR-8's arm, [1799.98, 1802.0]: to the run's end.
        (0.2, 0.001, [(8999, 9005)]),  # 200 ms, N2's registered gain-10 step; 8999 x 0.2 > 1799.8.
        (0.05, 0.001, [(35999, 36010)]),  # Fine and coarse products 1 ulp apart at 17% of points.
        (0.1, 0.01, [(17999, 18010)]),
        (0.02, 0.001, [(89990, 89995), (89995, 89999), (90050, 90060)]),  # Two touch; one apart.
    ],
)
def test_a_window_is_the_clock_of_no_op_events_at_its_fine_points(dt, fine, spans):
    """The windows' ends are declared as the clock's own coarse products, read off the grid."""
    end, m = 1802.0, round(dt / fine)
    windows = [(a * dt, b * dt) for a, b in spans]
    start = windows[0][0]
    cue = (m * spans[0][0] + 3) * fine  # On a fine point: it coincides.
    split = start + 2.5 * fine  # Between fine points: it splits one.
    window = block(fine, *windows)
    spec = parse_spec(network(dt, end, schedule=[(split, 1.0), (cue, 0.5)], window=window))
    windowed = EventGrid(spec)
    oracle = event_clock(spec, [t for a, b in windows for t in fine_points(dt, fine, a, b)])
    assert len(windowed) == len(oracle)
    # Before the windows both clocks are i x dt, with no window or event there: compare from them.
    head = windowed.exact_index(start) - 2
    assert head == oracle.exact_index(start) - 2
    assert min(windowed.span_positions) > head and min(oracle.extra_indices) > head
    tail = [windowed[i] for i in range(head, len(windowed))]
    assert tail == [oracle[i] for i in range(head, len(oracle))]
    steps = np.diff(tail)
    near = lambda value: np.abs(steps - value) <= 1e-9 * value  # noqa: E731
    inside = np.zeros(len(steps), dtype=bool)
    for a, b in windows:
        inside[windowed.exact_index(a) - head : windowed.exact_index(b) - head] = True
    assert np.all(np.where(inside, near(fine) | near(0.5 * fine), near(dt)))  # No tiny step.
    assert np.count_nonzero(near(0.5 * fine)) == 2  # The split's two halves.
    assert windowed.extras == (split,)  # The cue is a fine point; the split is the one extra.
    record = windowed.fine_window_record()
    assert [w["steps"] for w in record["windows"]] == [
        m * (b - a) + (k == 0) for k, (a, b) in enumerate(spans)
    ]
    assert record["fine_steps"] + record["coarse_steps"] == len(windowed) - 1


def test_fr8_arm_clock_and_no_block_serialization():
    raw = network(0.02, 3600.0, window=block(0.001, (1799.98, 1802.0)))
    spec = parse_spec(raw)
    grid = EventGrid(spec)
    assert len(grid) - 1 == 181_919
    assert grid.fine_window_record() == dict(
        windows=[dict(start_time=1799.98, end_time=1802.0, dt=0.001, subdivision=20, steps=2020)],
        fine_steps=2020,
        coarse_steps=179_899,
    )
    assert spec.to_dict()["execution"]["fine_windows"] == raw["execution"]["fine_windows"]
    del raw["execution"]["fine_windows"]
    plain = parse_spec(raw)
    assert plain.fine_windows is None and "fine_windows" not in plain.to_dict()["execution"]
    assert plain.fingerprint == dataclasses.replace(spec, fine_windows=None).fingerprint
    assert len(EventGrid(plain)) - 1 == 180_000 and not EventGrid(plain).spans
    # The run manifests' clock entries (records/io.py and records/window_io.py): the windows'
    # method only where they are declared, so a manifest without the block keeps its bytes.
    assert manifest_numerics(spec) == dict(grid="zero_anchored_event_split", fine_windows=METHOD)
    assert manifest_numerics(plain) == dict(grid="zero_anchored_event_split")


def _changed(change):
    """The refusals' world (dt 20 ms, a window [1799.98, 1801.0] s at 1 ms), changed."""

    def build():
        raw = network(0.02, 1802.0, window=block(0.001, (1799.98, 1801.0)))
        change(raw)
        return raw

    return build


def _set(path, value):
    def change(raw):
        target = raw
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return change


def _windows(*pairs):
    return _set(("execution", "fine_windows", "windows"), block(1.0, *pairs)["windows"])


def _reaction_transport():
    """A model the block does not admit (reaction_transport@1, one cell without a contact)."""
    return dict(
        schema_version=1,
        model=dict(
            id="reaction_transport@1",
            units=dict(amount="fmol", volume="pL", time="s"),
            species=["A", "B"],
            population=dict(count=1, cell_ids=[101]),
            initial_state=dict(amount=[[8.0], [0.0]], volume=[1.0]),
            parameters=dict(
                reaction=dict(
                    from_species="A", to_species="B", forward_rate=[0.2], reverse_rate=[0.05]
                ),
                contacts=[],
            ),
        ),
        experiment=dict(
            end_time=12.0,
            source=dict(kind="none"),
            contact=dict(
                kind="prescribed_contact_open_fractions",
                contact_ids=[],
                schedule=[dict(time=0.0, open_fractions=[])],
            ),
            observation_times=[0.0, 12.0],
        ),
        execution=dict(
            backend="cpu",
            precision="float64",
            solver="rk4",
            dt=0.05,
            capacity=1,
            edge_capacity=0,
            jit=True,
            max_steps=100000,
            max_trace_bytes=2**26,
            fine_windows=block(0.0125, (1.0, 2.0)),
        ),
    )


def _counting_operator():
    """species_regulated_availability@1 in the composite: its record counts steps."""
    from validation.tissue import regulated_availability_fixtures as rafx

    raw = rafx.shared_structure(end=0.02)
    raw["execution"]["fine_windows"] = block(2.5e-4, (0.005, 0.01))
    return raw


def _projective(raw):
    from validation.tissue import projective_fixtures

    raw["execution"]["projective"] = projective_fixtures.projective_block([(1790.0, 1799.0)])


FINE_POINT = (20 * 90000 + 1) * 0.001  # A fine point of the refusals' window, as the clock has it.
REFUSALS = {
    "a start off the coarse grid": (
        _changed(_windows((1799.99, 1801.0))),
        "start 1799.99 is not a point of the coarse grid",
    ),
    "an end off the coarse grid": (
        _changed(_windows((1799.98, 1801.01))),
        "end 1801.01 is not a point of the coarse grid",
    ),
    "a fine dt that does not divide dt": (
        _changed(_set(("execution", "fine_windows", "dt"), 0.003)),
        "whole number of fine steps",
    ),
    "a fine dt not below dt": (
        _changed(_set(("execution", "fine_windows", "dt"), 0.02)),
        "smaller than execution.dt",
    ),
    "overlapping windows": (_changed(_windows((1799.0, 1800.0), (1799.98, 1801.0))), "not overlap"),
    "a window past the horizon": (_changed(_windows((1800.0, 1803.0))), "fit the horizon"),
    "no window": (_changed(_windows()), "non-empty list"),
    "another method": (
        _changed(_set(("execution", "fine_windows", "method"), "x@1")),
        "requires method",
    ),
    "a clock above max_steps": (
        _changed(_set(("execution", "max_steps"), 91_000)),
        "Fine-windowed integration grid exceeds max_steps",
    ),
    # D283 renews these two rows: an event within the same-instant tolerance of a point now snaps
    # there (admitted); one past it but within NEAR_MISS of its step is the refused near miss.
    "an event in the near-miss band of a fine point": (
        _changed(
            lambda raw: raw["experiment"]["membrane_controls"][0]["schedule"].append(
                dict(time=FINE_POINT - 1e-10, availability=0.5)
            )
        ),
        "misses the fine point 1800.001",
    ),
    # A coarse point's: an event exactly on one (90005 x 0.02, not the decimal 1800.1) is admitted,
    # and one 1e-10 s below the next (90010 x 0.02), in its fine step's band, is refused, naming it.
    "an event in the near-miss band of a coarse point": (
        _changed(
            lambda raw: raw["experiment"]["membrane_controls"][0]["schedule"].extend(
                [
                    dict(time=90005 * 0.02, availability=0.5),
                    dict(time=90010 * 0.02 - 1e-10, availability=1.0),
                ]
            )
        ),
        f"misses the coarse point {90010 * 0.02!r}",
    ),
    "a model it does not admit": (
        _reaction_transport,
        "fine_windows admits .*; ReactionTransportSpec is refused",
    ),
    "an operator that counts steps": (
        _counting_operator,
        "species_regulated_availability@1 is refused: its crossing record counts steps",
    ),
    "a projective block beside it": (
        _changed(_projective),
        "projective, which has its own windows",
    ),
}


@pytest.mark.parametrize("name", REFUSALS)
def test_refusals_at_the_definition(name):
    build, message = REFUSALS[name]
    with pytest.raises(ConfigError, match=message):
        parse_spec(build())


def test_the_batch_and_vector_paths_are_refused():
    spec = parse_spec(_changed(lambda raw: None)())
    for refuse in (lambda: timeline(spec), lambda: _plan_windows_metadata(spec, WindowPolicy())):
        with pytest.raises(ConfigError, match="fine_windows runs only through"):
            refuse()


# ------------------------------------------------------------------ an @3 world, X2 on

DT = worlds.BASE_DT_S / 16.0  # X2's test step, 1/64 s, exact in binary.
FINE = DT / 4
END = 12 * DT
WINDOW = (2 * DT, 6 * DT)
CUE = 3 * DT + FINE  # A fine-only instant inside the window.
WIDTH = 5


def x2_world(*, windowed=True):
    entries = [] if windowed else [t for t in fine_points(DT, FINE, *WINDOW) if t != CUE]
    window = block(FINE, WINDOW) if windowed else None
    raw = network(DT, END, schedule=[(CUE, 0.5)], noop=entries, window=window, energy_check=True)
    raw["experiment"]["observation_times"] = [0.0, CUE + FINE, 7 * DT, END]  # A fine-only row.
    return raw


def test_a_branch_may_not_change_the_windows():
    spec = parse_spec(network(DT, END, window=block(FINE, WINDOW)))  # No X2: no compile here.
    changed = parse_spec(network(DT, END, window=block(FINE, (2 * DT, 4 * DT))))
    with pytest.raises(ConfigError, match="may not change model or execution settings"):
        branch_checkpoint(spec, initialise(spec), changed)


@pytest.fixture(scope="module")
def runs():
    spec = parse_spec(x2_world())
    windows = []
    result = run_windowed(spec, WindowPolicy(WIDTH, "checkpoints"), sink=windows.append)
    return spec, windows, result


def test_x2_passes_on_the_two_rate_clock(runs):
    spec, windows, result = runs
    assert result.final.step_index == 8 + 16
    assert result.resources["fine_windows"] == dict(
        windows=[dict(start_time=WINDOW[0], end_time=WINDOW[1], dt=FINE, subdivision=4, steps=16)],
        fine_steps=16,
        coarse_steps=8,
    )
    summary = result.resources["energy_check"]  # X2 decided the whole run at its end.
    assert summary["counted_steps"] == 24 and summary["held_out_of_band"] == 0
    assert 3.5 <= summary["median_step_ratio"] <= 4.6
    times = np.concatenate([w.times[:-1] for w in windows] + [windows[-1].times[-1:]])
    assert sorted(set(np.diff(times))) == [FINE, DT]  # Binary-exact: two rates, no other step.
    observed = np.concatenate([w.observations.times for w in windows])
    assert CUE + FINE in observed  # The fine-only row, an accepted boundary.


def test_a_restart_inside_the_window_continues_bit_for_bit(runs):
    spec, windows, _ = runs
    at = 4 * DT + 3 * FINE  # A fine point inside the window, inside an execution window.
    window = next(w for w in windows if w.times[0] < at < w.times[-1])
    checkpoint = window.checkpoint_at(at)
    assert checkpoint.step_index == 13
    rest = list(iter_windows(spec, WindowPolicy(WIDTH, "checkpoints"), checkpoint))
    assert rest[-1].final.energy_check.same(windows[-1].final.energy_check)
    rows = {}
    for w in windows:
        for j, t in enumerate(w.times):
            rows[float(t)] = [np.asarray(v)[j].tobytes() for v in w.history]
    later = [(float(t), j, w) for w in rest for j, t in enumerate(w.times)]
    assert later[0][0] == at and len({t for t, _, _ in later}) == 24 - 13 + 1
    for t, j, w in later:
        assert [np.asarray(v)[j].tobytes() for v in w.history] == rows[t]


def test_device_row_checks_under_the_window(runs):
    """WindowPolicy row_checks="device" on the windowed X2 world: every window bit for bit as the
    host run (times, histories, observations, X2's record), each decided on the device with the
    host's diagnostics (tests/window_row_check_fixtures.py, X2's own criteria)."""
    spec, windows, _ = runs
    device = list(iter_windows(spec, WindowPolicy(WIDTH, "checkpoints", "device")))
    assert_same_windows(windows, device)
    assert assert_agreement(spec, windows, device) == len(device)


def test_the_no_op_twin_feeds_the_rollout_the_same_inputs(runs):
    spec, _, _ = runs
    twin = parse_spec(x2_world(windowed=False))
    times = timeline(spec, energy_check=True)
    assert times.tobytes() == timeline(twin, energy_check=True).tobytes()
    for a, b in zip(
        control_values(spec, times[:-1]), control_values(twin, times[:-1]), strict=True
    ):
        assert np.asarray(a).tobytes() == np.asarray(b).tobytes()
    model = get_model(spec.model)
    assert model is get_model(twin.model)  # One implementation per declared structure.
    events = energy.event_mask(spec, times, model)
    assert np.array_equal(events, energy.event_mask(twin, times, model)) and not events.any()
    first, other = initialise(spec), initialise(twin)
    for a, b in zip((*first.state, *first.layout), (*other.state, *other.layout), strict=True):
        assert np.asarray(a).tobytes() == np.asarray(b).tobytes()
    params = model.parameters(spec, first.layout), model.parameters(twin, other.layout)
    for a, b in zip(*(jax.tree.leaves(p) for p in params), strict=True):
        assert np.asarray(a).tobytes() == np.asarray(b).tobytes()


# ------------------------------------------------------------------ the composite, a dose

DOSE_DT, DOSE_END, DOSE = 1e-3, 0.02, 0.012  # FR-10's declared step under ARS(2,2,2).
DOSE_FINE = DOSE_DT / 4
DOSE_WINDOW = (0.01, 0.015)


def test_a_dose_inside_a_window_on_the_composite_without_x2(tmp_path):
    """scheduled_bath_composition@1's dose leg (bath_schedule_fixtures.dosed_world), the dose at a
    coarse point inside the window. The block does not require X2: @3's own checks (every ledger,
    today's energy bound) pass on every row of the two-rate clock."""
    row = (4 * 10 + 1) * DOSE_FINE  # A fine-only instant, observed.
    observed = [0.0, row, DOSE, DOSE_END]
    raw = bfx.dosed_world(dt=DOSE_DT, end=DOSE_END, observation_times=observed)
    raw = bfx.with_bath_schedule(raw, ["bath"], bfx.CARGO, [(DOSE, ["bath"], {"cargo": 1.5e-3})])
    raw["execution"]["max_steps"] = 64
    raw["execution"]["fine_windows"] = block(DOSE_FINE, DOSE_WINDOW)
    spec = parse_spec(raw)
    assert [d.law for d in spec.model.operators] == ["scheduled_bath_composition@1"]
    windows = []
    result = run_windowed(spec, WindowPolicy(64, "checkpoints"), sink=windows.append)
    (window,) = windows
    assert result.resources["fine_windows"] == dict(
        windows=[dict(start_time=0.01, end_time=0.015, dt=DOSE_FINE, subdivision=4, steps=20)],
        fine_steps=20,
        coarse_steps=15,
    )
    assert window.observations.times.tolist() == observed
    j = int(np.flatnonzero(window.times == DOSE)[0])
    assert j == 10 + 2 * 4  # The dose's coarse point, kept bit for bit inside the window.
    held = np.asarray(window.history.bath_held_amount_fmol)
    moved = [k for k in range(1, len(held)) if not np.array_equal(held[k], held[k - 1])]
    assert moved == [j + 1]  # The step leaving the dose applies it, at its own time.
    write_windowed_run(tmp_path / "run", spec, WindowPolicy(64, "checkpoints"))
    manifest = json.loads((tmp_path / "run" / "manifest.json").read_text())
    assert manifest["numerics"]["fine_windows"] == METHOD
    assert manifest["resources"]["fine_windows"] == result.resources["fine_windows"]
