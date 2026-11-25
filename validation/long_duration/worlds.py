"""FR-8 stage 0's worlds, built as REGISTRATION_20261118.md §1 registers them.

Each function returns a raw definition from an existing builder, called as registered, with only
the registered changes. The registered numbers are read from registration_20261118.json.

* s7a, s7b, s127, t825, d1: the measurement worlds of §1's table;
* h2: the harness, projective qual-01's F1 world (case cue3) at a 3600 s horizon, without its
  projective block, at a chosen dt, with §5.2's observation times;
* w0: the stage-0 composed world of §1.1 (the coupling fixtures' moving world at synthetic
  minute-scale rates), with one optional intervention of each kind.
"""

import copy
import json
import math
from functools import cache
from pathlib import Path
from types import SimpleNamespace

from validation import id_table

HERE = Path(__file__).resolve().parent
REGISTRATION = HERE / "registration_20261118.json"
DEFAULT_BOOKING = "explicit_tableau"


@cache
def _registration_text():
    return REGISTRATION.read_text()


def registration():
    """The registered numbers, and the IDs translated (a fresh copy each call)."""
    return id_table.translate(json.loads(_registration_text()))


def s7a():
    from validation.tissue import pump_water_fixtures as wfx

    return wfx.gated_sheet(dt=1e-3, end_time=1.0)


def s7b():
    from validation.tissue import cell_replacement_fixtures as rfx

    return rfx.heredity_sheet(radius=1, disc=0, scale=0.6, dt=1e-3, end_time=0.1)


def s127():
    from validation.tissue import cell_replacement_fixtures as rfx

    return rfx.heredity_sheet(6, 3, scale=0.3, dt=1e-3, end_time=0.1)


def t825():
    from validation.tissue import pump_water_fixtures as wfx

    return wfx.scale_world(dt=1e-3, end_time=0.01)


def d1():
    from validation.stationary import worlds

    return worlds.default_world_cell()


def grid(start, stop, step, *, unit=1e-3):
    """Times i * unit (the float products the event grid accepts) from start to stop, every step.

    start and stop are included; all three are whole multiples of the unit."""
    first, last, stride = (round(v / unit) for v in (start, stop, step))
    return [i * unit for i in range(first, last + 1, stride)]


def harness_observation_times():
    """§5.2: every 10 s on [0, 3600]; every 1 ms on [1799.990, 1802.000]; every 10 ms on
    (1802, 1830]; every 1 s on (1830, 1900]. All are products i * 1 ms, which equal the 0.5 ms
    and 0.25 ms grids' own products exactly."""
    times = set()
    for start, stop, step in registration()["harness"]["observation_grids_s"]:
        times.update(grid(start, stop, step))
    return sorted(times)


def h2(dt=1e-3, *, development_end=None):
    """The harness world at dt: case_cue3's builder at the registered horizon, its projective
    block removed (as F1's fine reference), §5.2's observation times, and max_steps for dt.

    development_end (s), for smoke runs only and never a run of record: the builder's horizon
    instead (so the cue at its half), observed every 0.1 s."""
    from validation.tissue import projective_study as study

    end = registration()["harness"]["end_s"] if development_end is None else development_end
    # The protocol's projective parameters (projective_c_qualification_v1); the block is built and
    # then removed, so they only make the builder's call the protocol's.
    args = SimpleNamespace(
        end=end,
        every=10.0,
        window_start=10.0,
        burst=3000,
        slope=250,
        max_steps=120000,
        tol_concentration=1e-3,
        tol_voltage=1e-5,
        tol_gate=1e-4,
        row_checks="host",
    )
    raw = study.case_cue3(args)
    del raw["execution"]["projective"]
    raw["experiment"]["observation_times"] = (
        harness_observation_times() if development_end is None else grid(0.0, end, 0.1)
    )
    raw["execution"]["dt"] = dt
    raw["execution"]["max_steps"] = int(math.ceil(end / dt)) + 8
    return raw


def w0(
    *,
    end,
    dt=1e-3,
    observation_times=None,
    booking=DEFAULT_BOOKING,
    channel_step=None,
    dose=None,
    write=None,
):
    """The stage-0 composed world (§1.1). channel_step, dose and write are the times (s) of the
    registered interventions (kir_0 from 1.0 to 0.9; R's production from P0 to 2 P0; (s, cell_3)
    set to 0.9), or None. observation_times default to the start and the end."""
    from validation.tissue import regulated_availability_fixtures as ra

    w = registration()["w0"]
    times = [0.0, end] if observation_times is None else list(observation_times)
    raw = ra.sheet(end=end, dt=dt, observation_times=times)
    if booking != DEFAULT_BOOKING:
        raw["model"]["junction_heat_booking"] = booking
    state, c_r, c_s = w["state"], w["c_r"], w["c_s"]
    law, species, k, n = state["input"]
    registered_write = w["write"]
    writes = (
        []
        if write is None
        else [
            (registered_write["state"], registered_write["cell"], write, registered_write["value"])
        ]
    )
    raw = ra.with_coupling(
        raw,
        species=[w["regulator"], "Na"],
        states=[
            ra.state(
                state["id"],
                state["cells"],
                [(law, species, k, n)],
                on=state["on_rate_per_s"],
                off=state["off_rate_per_s"],
                initial=dict(state["initial"]),
                level=state["crossing_level"],
            )
        ],
        couplings=[
            ra.hill_coupling(
                "c_r",
                c_r["control"],
                c_r["ids"],
                c_r["species"],
                c_r["law"],
                c_r["half_saturation_mM"],
                c_r["hill_coefficient"],
                side=c_r["side"],
                basal=c_r["basal"],
            ),
            ra.coupling(
                "c_s",
                c_s["control"],
                c_s["ids"],
                ("state", c_s["state"]),
                c_s["law"],
                side=c_s["side"],
                basal=c_s["basal"],
            ),
        ],
        switches={"c_r": [(0.0, 1)], "c_s": [(0.0, 1)]},
        writes=writes,
    )
    volume = next(c for c in raw["model"]["cells"] if c["id"] == "cell_0")["volume_pL"]
    clearance = w["clearance_per_s"]
    p0 = clearance * w["regulator_anchor_mM"] * volume
    production = [(0.0, p0)] if dose is None else [(0.0, p0), (dose, w["dose_factor"] * p0)]
    raw = ra.with_regulator_turnover(
        raw,
        [("clear_R", "cell_0", "clearance"), ("dose_R", "cell_0", "production")],
        [("clear_R", "cell_0", [(0.0, clearance)]), ("dose_R", "cell_0", production)],
    )
    if channel_step is not None:
        step = w["channel_step"]
        group = next(
            g for g in raw["experiment"]["channel_controls"] if g["channel_id"] == step["channel"]
        )
        group["schedule"] = [
            dict(time=0.0, availability=step["from"]),
            dict(time=channel_step, availability=step["to"]),
        ]
    return copy.deepcopy(raw)


def m1_worlds():
    """M1's worlds (§3), by ID, each at its declared 1 ms step."""
    return dict(s7a=s7a(), s7b=s7b(), s127=s127(), t825=t825(), h2=h2(), w0=w0(end=1.0))
