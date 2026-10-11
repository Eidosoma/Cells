"""Source-specific scalar parameter input and read-only native step observation."""

import hashlib
import importlib
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import release_context as ctx

old = importlib.import_module("loop_native")
observer = importlib.import_module("loop_observer")
c = ctx.c


@dataclass(frozen=True)
class AvailabilityInput:
    baseline_maxDm: float

    def __post_init__(self):
        ctx.design.native_diffusivity(self.baseline_maxDm, 1.0)

    def apply(self, channel, value):
        previous = channel.maxDm
        # Only this parameter is changed. No expression, kinetic or state write.
        channel.maxDm = ctx.design.native_diffusivity(self.baseline_maxDm, value)
        return {
            "baseline_maxDm_m2_per_s": self.baseline_maxDm,
            "previous_maxDm_m2_per_s": previous,
            "availability": value,
            "applied_maxDm_m2_per_s": channel.maxDm,
        }


def numeric_inventory(phase):
    """All reachable numeric leaves of explicit roots; opaque metadata is labelled.

    Object graphs, sparse matrices and arbitrary object arrays are not serialized.
    The complete declared ionic/gate state is additionally saved in native snapshots.
    """
    import numpy as np

    channel = old.channel(phase.sim)
    roots = {
        "sim": phase.sim,
        "network": phase.sim.molecules.core,
        "channel": channel,
        "gates": channel.channel_core,
        "geometry": phase.cells,
    }
    numeric, opaque = {}, {}

    def collect(path, value, ancestors=(), depth=0):
        if path == "channel/maxDm":
            return
        if isinstance(value, np.ndarray) and value.dtype.kind in "biufc":
            numeric[path] = {
                "kind": "array",
                "dtype": value.dtype.str,
                "shape": list(value.shape),
                "bytes_sha256": hashlib.sha256(value.tobytes(order="C")).hexdigest(),
            }
        elif isinstance(value, (bool, int, float, np.integer, np.floating, np.bool_)):
            item = value.item() if isinstance(value, np.generic) else value
            c.require(type(item) is not float or math.isfinite(item), "Nonfinite native scalar")
            numeric[path] = {"kind": type(value).__name__, "value": item}
        elif isinstance(value, (list, tuple, dict)) and depth < 10 and id(value) not in ancestors:
            items = value.items() if isinstance(value, dict) else enumerate(value)
            opaque[path] = {"type": type(value).__name__, "length": len(value)}
            for name, child in items:
                collect(path + "/" + str(name), child, (*ancestors, id(value)), depth + 1)
        else:
            opaque[path] = {"type": type(value).__module__ + "." + type(value).__name__}

    for name, owner in roots.items():
        for field, value in vars(owner).items():
            collect(name + "/" + field, value)
    return {"numeric": numeric, "opaque_metadata": opaque, "excluded_input": "channel/maxDm"}


class StepObserver:
    """Read-only source/instance-scoped gate/transfer boundary records."""

    def __init__(self, phase, science):
        self.phase = phase
        self.science = Path(science).resolve()
        self.gates = old.channel(phase.sim).channel_core
        self.events, self.snapshots = [], {}
        self.hook = self.dispatch

    def __enter__(self):
        c.require(sys.getprofile() is None and not self.events, "Occupied or reused observer")
        sys.setprofile(self.hook)
        return self

    def __exit__(self, kind, error, trace):
        active = sys.getprofile()
        sys.setprofile(None)
        if kind is None:
            c.require(active is self.hook, "Native profile hook replaced")
            c.require(
                self.events == ["before_gate", "after_gate", "before_transfer", "after_transfer"],
                "Wrong native step order",
            )
        return False

    def dispatch(self, frame, event, argument):
        if event not in ("call", "return"):
            return
        if event == "return" and not observer.successful_return(frame):
            return
        file, name = frame.f_code.co_filename, frame.f_code.co_name
        label = None
        if (
            file == str(self.science / "channels/vg_k.py")
            and name == "run"
            and frame.f_locals.get("self") is self.gates
        ):
            label = "before_gate" if event == "call" else "after_gate"
        elif (
            file == str(self.science / "sim_toolbox.py")
            and name == "update_Co"
            and frame.f_locals.get("sim") is self.phase.sim
        ):
            label = "before_transfer" if event == "call" else "after_transfer"
        if label is not None:
            c.require(label not in self.events, "Repeated native gate/transfer boundary")
            self.events.append(label)
            # Before transfer is after gates but before any concentration assignment.
            if label != "after_transfer":
                self.snapshots[label] = old.snapshot(self.phase.sim)

    def result(self):
        return {
            "events": self.events,
            "snapshots": self.snapshots,
            "hook_restored": sys.getprofile() is None,
        }


def single_update(phase, science, mode, raw_label, *, record=None):
    sim, net, p, cells = phase.sim, phase.sim.molecules.core, phase.p, phase.cells
    row = {} if record is None else record
    c.require(not row, "Single-update record must be fresh")
    row["before"] = old.snapshot(sim)
    net.clear_run_loop(sim)
    row["after_clear"] = old.snapshot(sim)
    if mode == "observed":
        watch = StepObserver(phase, science)
        try:
            with watch:
                net.run_loop_channels(phase)
        finally:
            row["observer"] = watch.result()
    else:
        c.require(mode == "unobserved" and sys.getprofile() is None, "Unexpected observer mode")
        net.run_loop_channels(phase)
        row["observer"] = None
    row["after_channel"] = old.snapshot(sim)
    net.run_loop(phase, float(raw_label))  # Empty chemistry exports the channel current.
    row["after_network"] = old.snapshot(sim)
    sim.update_all_concs(cells, p)  # Zero ordinary permeability: must not double-transfer.
    row["after_ordinary"] = old.snapshot(sim)
    sim.update_V(cells, p)
    row["after_voltage"] = old.snapshot(sim)
    row["calls"] = {
        "clear": 1,
        "channel": 1,
        "empty_network": 1,
        "ordinary": 1,
        "voltage": 1,
        "full_simulator_loop": 0,
    }
    return row


def fresh_flux(phase):
    """Evaluate actual native constitutive flux on copies, without a gate advance."""
    import numpy as np
    from betse.science.sim_toolbox import electroflux

    sim, p, channel = phase.sim, phase.p, old.channel(phase.sim)
    core = channel.channel_core
    voltage = np.array(sim.vm, copy=True)
    inside = np.array(sim.cc_cells[1][phase.cells.mem_to_cells], copy=True)
    outside = np.array(sim.cc_env[1], copy=True)
    z = np.ones(sim.mdl, dtype=np.float64)
    diffusivity = np.array(core.m * core.h * channel.maxDm, copy=True)
    inputs = {
        "voltage_V": voltage.tolist(),
        "inside_K_mM": inside.tolist(),
        "outside_K_mM": outside.tolist(),
        "diffusivity_m2_per_s": diffusivity.tolist(),
        "valence": z.tolist(),
    }
    flux = electroflux(outside, inside, diffusivity, p.tm, z, voltage, sim.T, p)
    return {
        "source": "betse.science.sim_toolbox.electroflux",
        "evaluation": "copied_pre_update_state_new_input_not_interval_current",
        "inputs": inputs,
        "voltage_after_V": voltage.tolist(),
        "valence_after": z.tolist(),
        "density_mol_per_m2_s": flux.tolist(),
    }
