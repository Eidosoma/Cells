"""FR-18 criterion X, amendment 1: FR-8's worlds through the registered recorder, unchanged.

recorder_x.main runs as registered. Only the probe's world builder gains two kinds, built by FR-8's
own stage-0 builders (validation/long_duration/worlds.py and its registration_20261118.json at
FR-8's snapshot c5183aba), loaded read-only by path:
  fr8h2 DT              H2: case_cue3 to 3600 s, the cue at 1800-1800.3 s, at DT (s)
  fr8w0 BOOKING:DT      W0 as M5 builds it (m5_energy.world): 60 s, the dose at 20 s, the write at
                        40 s, observed every 1 s, with BOOKING at DT (s)

Usage (cwd = the run's clean snapshot root, PYTHONPATH=src:.:<the probe's directory>:<fr18-x>):
  python -B recorder_fr8.py OUT_NPZ KIND ARG [MAX_STEPS]
"""

import copy
import importlib.util
import sys

import harness as H  # The probe's harness, unchanged.
import recorder_x as RX  # The registered recorder, unchanged.

FR8_WORLDS = (
    "/mnt/workspaces/Cells/fr8-stage0-20261118/snapshot-c5183aba/validation/long_duration/worlds.py"
)

_spec = importlib.util.spec_from_file_location("fr8_stage0_worlds", FR8_WORLDS)
fr8 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fr8)

_probe_world = H.world


def admitted(raw):
    """Admission only (the registration's note): timeline() estimates a trace for the whole
    horizon, which this replay never keeps (it keeps per-row values only; FR-8 ran these worlds
    through runners that keep no such trace). A definition whose estimate exceeds its own
    max_trace_bytes gets twice the estimate; nothing else changes."""
    from cells.definitions.specs import parse_spec
    from cells.execution.grid import EventGrid
    from cells.execution.resources import trace_bytes

    probe = copy.deepcopy(raw)
    probe["execution"]["max_trace_bytes"] = 2**52
    spec = parse_spec(probe)
    estimate = trace_bytes(spec, len(EventGrid(spec)) - 1)
    own = parse_spec(raw).execution.max_trace_bytes if "max_trace_bytes" in raw["execution"] else None
    limit = own if own is not None else spec.execution.max_trace_bytes
    if estimate > limit:
        raw["execution"]["max_trace_bytes"] = int(min(2 * estimate, 2**52))
    return raw


def world(kind, arg):
    if kind == "fr8h2":
        dt = float(arg)
        return admitted(fr8.h2(dt)), f"H2 at dt {dt:g} s", None
    if kind == "fr8w0":
        booking, dt = arg.rsplit(":", 1)
        dt = float(dt)
        reg = fr8.registration()["m5"]
        times = fr8.grid(0.0, reg["end_s"], reg["observe_every_s"])
        raw = fr8.w0(
            end=reg["end_s"],
            dt=dt,
            observation_times=times,
            booking=booking,
            dose=reg["dose_s"],
            write=reg["write_s"],
        )
        return admitted(raw), f"W0 (M5) {booking} at dt {dt:g} s", None
    return _probe_world(kind, arg)


H.world = world  # recorder_x reads the probe's module, so its main() sees these kinds too.

if __name__ == "__main__":
    RX.main(sys.argv)
