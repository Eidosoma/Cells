# ruff: noqa: F841
"""Pinned complete time-setup body and clock slices, plus original component capture.

No installed BETSE function, full Parameters.load, _plot_loop, seed/init/load,
run_sim_core, write2storage or pickle is invoked. Clock-only INIT probes execute
only the declared source time arithmetic, never an INIT material solver.
"""

import argparse
import builtins
import copy
import enum
import hashlib
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from validation.betse import betse_normal_ecm_event_mechanics_native as component


class SimPhaseKind(enum.Enum):
    SEED = 1
    INIT = 2
    SIM = 3


BetseSimPhaseException = ValueError


def _source_counts(self):
    self.init_tsteps = int(self.init_time_total / self.init_time_step)
    self.sim_tsteps = int(self.sim_time_total / self.sim_time_step)


# fmt: off
def _source_phase_time(self):
    "\n        Initialize all time-specific kludges required by this simulation phase.\n        "
    if self.kind is SimPhaseKind.SEED:
        return
    if self.kind is SimPhaseKind.INIT:
        self.p.dt = self.p.init_time_step
        self.p.resample = self.p.init_time_sampling
        self.p.total_time = self.p.init_time_total
    elif self.kind is SimPhaseKind.SIM:
        self.p.dt = self.p.sim_time_step
        self.p.resample = self.p.sim_time_sampling
        self.p.total_time = self.p.sim_time_total
    else:
        raise BetseSimPhaseException('Simulation phase "{}" unsupported.'.format(self.kind.name))
    self.p.t_resample = self.p.resample / self.p.dt
# fmt: on


def _source_clock(phase):
    if phase.kind is SimPhaseKind.INIT:
        phase_verb = "Initializing"
        phase_noun = "initialization"
        phase_time_step_count = phase.p.init_tsteps
    else:
        phase_verb = "Simulating"
        phase_noun = "simulation"
        phase_time_step_count = phase.p.sim_tsteps
    phase_time_len = phase_time_step_count * phase.p.dt
    time_steps = np.linspace(0, phase_time_len, phase_time_step_count)
    time_steps_sampled = set()
    i = 0
    while i < len(time_steps) - phase.p.t_resample:
        i += phase.p.t_resample
        i = int(i)
        time_steps_sampled.add(time_steps[i])
    return (time_steps, time_steps_sampled, phase_time_len)


def clock_profile(raw):
    if raw["phase"] not in ("INIT", "SIM"):
        raise ValueError("Clock slice requires an explicit supported phase")
    for name in ("init", "sim"):
        dt, total, sampling = (
            raw[name + suffix] for suffix in ("_dt_s", "_total_s", "_sampling_s")
        )
        if (
            not all(type(x) in (int, float) and math.isfinite(x) for x in (dt, total, sampling))
            or dt <= 0
            or total < 0
            or not math.isfinite(total / dt)
            or not math.isfinite(sampling / dt)
            or sampling / dt < 1
        ):
            raise ValueError("Refuse nonprogressing clock/sampling input before native slice")
    p = SimpleNamespace(
        init_time_total=raw["init_total_s"],
        init_time_step=raw["init_dt_s"],
        init_time_sampling=raw["init_sampling_s"],
        sim_time_total=raw["sim_total_s"],
        sim_time_step=raw["sim_dt_s"],
        sim_time_sampling=raw["sim_sampling_s"],
    )
    _source_counts(p)
    phase = SimpleNamespace(kind=getattr(SimPhaseKind, raw["phase"]), p=p)
    _source_phase_time(phase)
    labels, sampled, duration = _source_clock(phase)
    return dict(
        phase=raw["phase"],
        step_count=len(labels),
        dt_s=p.dt,
        sample_stride=p.t_resample,
        configured_total_s=p.total_time,
        source_phase_duration_s=duration,
        source_labels_s=labels,
        sampled=[float(label) in sampled for label in labels],
        events_enabled=raw["phase"] == "SIM",
        installed_native_function_calls=0,
        complete_captured_source_function_bodies=["SimPhase._init_kludge_time"],
        extracted_statement_slices=[
            "Parameters.load.time_counts",
            "Simulator._plot_loop.clock_and_sampling",
        ],
        material_solver_executed=False,
    )


def evaluate(inputs):
    raw = inputs["time_profile"]
    clock = clock_profile(raw)
    if clock["phase"] != "SIM" or clock["step_count"] != 3:
        raise ValueError("Only clock probes may use INIT or non-N3 source counts")
    declared = inputs["composition_inputs"]
    calendar = declared["event_inputs"]["calendar"]
    if clock["dt_s"] != calendar["dt_s"] or clock["sample_stride"] != calendar["sample_stride"]:
        raise ValueError("Component/profile clock association differs")
    captured = component.evaluate(declared)
    for index, row in enumerate(captured.get("sample_states", ())):
        assert row["source_time_s"] == float(clock["source_labels_s"][index])
        assert row["native_calendar_eligible"] is clock["sampled"][index]
    return dict(
        clock=clock,
        composition=captured,
        RNG_unchanged=captured["RNG_unchanged"],
        source_scope=(
            "Captured original component bodies and explicit time slices; no full native lifecycle"
        ),
        native_init_load_run_sim_core_write2storage_pickle_called=False,
        native_full_phase_completed=False,
        physical_initialization_claim=False,
    )


def main():
    from validation.betse.betse_normal_channel_join_runtime import inventory

    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--clock-only", action="store_true")
    args = parser.parse_args()
    protocol = json.loads(
        Path(__file__).with_name("betse_normal_ecm_run_lifecycle_protocol.json").read_text()
    )
    pins = protocol["native_source"]
    for name, expected in pins["source_sha256"].items():
        for base in (Path(pins["checkout"]), Path(pins["installed_package"]).parent):
            if hashlib.sha256((base / name).read_bytes()).hexdigest() != expected:
                raise ValueError("Changed native time source: " + name)
    blocked = {"cells", "betse", "jax", "jaxlib"}
    original = builtins.__import__

    def guarded(name, *values, **kwargs):
        if name.split(".")[0] in blocked:
            raise ImportError("Native lifecycle production import denied: " + name)
        return original(name, *values, **kwargs)

    builtins.__import__ = guarded
    inputs = json.loads(args.inputs.read_text())
    before_rng = copy.deepcopy(np.random.get_state())
    result = (
        dict(clock=clock_profile(inputs), RNG_unchanged=True, clock_only=True)
        if args.clock_only
        else evaluate(inputs)
    )
    after_rng = np.random.get_state()
    result["RNG_unchanged"] = bool(
        before_rng[0] == after_rng[0]
        and np.array_equal(before_rng[1], after_rng[1])
        and before_rng[2:] == after_rng[2:]
    )
    loaded = [name for name in sys.modules if name.split(".")[0] in blocked]
    assert not loaded
    result.update(
        production_imports_denied=True, loaded_production_modules=loaded, runtime=inventory()
    )
    component.archives.write_archive(args.output, result)


if __name__ == "__main__":
    main()
