"""Pinned native class contact and actual FULL-driver junction lifecycle."""

import argparse
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fresh_rerun"))
import common as u  # noqa: E402


def primitives(protocol):
    import numpy as np
    from betse.science.channels.gap_junction import Gap_Junction, Gap_Junction_i

    rows = []
    voltage = np.asarray(protocol["probe_voltage_V"])
    for cls in (Gap_Junction, Gap_Junction_i):
        for dt in protocol["probe_dt_s"]:
            for initial in protocol["probe_initial_gates"]:
                p = SimpleNamespace(
                    dt=dt,
                    gj_min=protocol["gj_min"],
                    gj_vthresh=protocol["gj_vthresh_mV"],
                    gj_vgrad=protocol["gj_vgrad_mV"],
                )
                sim = SimpleNamespace(
                    vgj=voltage.copy(), gj_block=1.0, gjopen=np.full(voltage.shape, initial)
                )
                obj = cls(sim, None, p)
                row = {
                    "class": cls.__name__,
                    "dt_s": dt,
                    "initial_gate": initial,
                    "sim_after_init": sim.gjopen.tolist(),
                    "class_after_init": None if not hasattr(obj, "gjopen") else obj.gjopen.tolist(),
                    "updates": [],
                }
                for block in protocol["probe_block_schedule"]:
                    before = sim.gjopen.copy()
                    sim.gj_block = block
                    obj.run(sim, None, p)
                    row["updates"].append(
                        {"block": block, "before": before.tolist(), "after": sim.gjopen.tolist()}
                    )
                rows.append(row)
    return rows


class Observer:
    def __init__(self, phase, science):
        self.phase = phase
        self.gate_file = str(science / "channels/gap_junction.py")
        self.sim_file = str(science / "sim.py")
        self.loop_frame = None
        self.steps, self.calls, self.inflight, self.initializations = 0, [], {}, []

    def observe(self, frame, event, argument):
        import numpy as np
        from loop_observer import successful_return

        if event not in ("call", "return") or (event == "return" and not successful_return(frame)):
            return
        sim, p = self.phase.sim, self.phase.p
        name, filename = frame.f_code.co_name, frame.f_code.co_filename
        if filename == self.sim_file and frame.f_locals.get("self") is sim:
            if name == "_run_sim_core_loop":
                self.loop_frame = frame if event == "call" else None
            elif name == "update_all_concs" and event == "return":
                self.steps += 1
        if filename != self.gate_file or name not in ("init", "run"):
            return
        obj = frame.f_locals.get("self")
        if obj.__class__.__name__ != "Gap_Junction":
            return
        if event == "call":
            parent = frame.f_back
            record = {
                "name": name,
                "step": self.steps,
                "dt_s": p.dt,
                "voltage_V": np.asarray(sim.vgj).tolist(),
                "block": np.asarray(sim.gj_block).tolist(),
                "sim_before": np.asarray(sim.gjopen).tolist(),
                "parent": parent.f_code.co_name,
                "species_index": int(parent.f_locals["i"])
                if parent.f_code.co_name == "update_gj"
                else None,
            }
            self.inflight[id(frame)] = record
        else:
            record = self.inflight.pop(id(frame))
            record.update(
                sim_after=np.asarray(sim.gjopen).tolist(),
                class_after=np.asarray(obj.gjopen).tolist(),
                alpha=np.asarray(obj.alpha).tolist(),
                beta=np.asarray(obj.beta).tolist(),
            )
            (self.initializations if name == "init" else self.calls).append(record)

    def validate_complete(self):
        u.need(
            not self.inflight and len(self.initializations) == 1,
            "Incomplete native gate observations",
        )
        u.need(self.steps == self.phase.p.init_tsteps, "Native outer step count changed")
        u.need(
            len(self.calls) == self.steps * len(self.phase.sim.movingIons),
            "Unexpected native gate call count",
        )


def lifecycle(output, workspace, protocol, order, block, observed):
    native = u.private(
        "junction_seed", Path(__file__).resolve().parents[1] / "junction_transport/native.py"
    )
    phase, prep = native.preparation(output, workspace)
    sim, p = phase.sim, phase.p
    p.v_sensitive_gj = True
    p.gj_surface = protocol["gj_surface_fraction"]
    p.gj_min, p.gj_vthresh, p.gj_vgrad = (
        protocol[k] for k in ("gj_min", "gj_vthresh_mV", "gj_vgrad_mV")
    )
    u.module_path("channel_loop_preparation")
    import betse
    import numpy as np
    from loop_observer import InitialConditionHook

    science = Path(betse.__file__).resolve().parent / "science"
    observer = Observer(phase, science) if observed else None
    fixture = {}

    def initialize(value):
        value.sim.movingIons = [prep["species"][name] for name in order]
        value.sim.gj_block = block
        fixture.update(moving_ions=list(value.sim.movingIons), block=block)

    with InitialConditionHook(phase, science, initialize, observer):
        sim.run_sim_core(phase)
    keys = (
        "cc_cells",
        "cc_at_mem",
        "cc_env",
        "vm",
        "vgj",
        "gjopen",
        "fluxes_gj",
        "fluxes_mem",
        "gjopen_time",
        "vm_time",
        "cc_time",
        "time",
    )
    result = {
        "order": order,
        "block": block,
        "observed": observed,
        "fixture": fixture,
        "steps": int(p.init_tsteps),
        "dt_s": p.dt,
        "final": {k: np.asarray(getattr(sim, k)).tolist() for k in keys},
        "gate_calls": [] if observer is None else observer.calls,
        "initializations": [] if observer is None else observer.initializations,
        "profile_hook_restored": sys.getprofile() is None,
        "native_pickle_present": Path(p.init_pickle_filename).is_file(),
    }
    u.write(output / "lifecycle.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=Path("/mnt/workspaces/Cells"))
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    try:
        p = u.read(args.protocol)
        import prepare

        prepare.native_setup(args.workspace)
        contact = primitives(p)
        rows = []
        for index, order in enumerate(p["orders"]):
            for b, block in enumerate(p["blocks"]):
                for observed in (False, True):
                    rows.append(
                        lifecycle(
                            output / f"order-{index}-block-{b}-observed-{int(observed)}",
                            args.workspace,
                            p,
                            order,
                            block,
                            observed,
                        )
                    )
        u.need(
            not any(k == "cells" or k.startswith("cells.") for k in sys.modules),
            "Native process imported Cells",
        )
        u.write(output / "panel.json", {"protocol": p, "primitives": contact, "lifecycles": rows})
        u.write(
            output / "completion.json",
            {
                "status": "native_dynamic_gate_recorded",
                "utc": u.utc(),
                "panel_sha256": u.sha(output / "panel.json"),
            },
        )
    except BaseException as exc:
        u.write(
            output / "failure.json",
            {"error": str(exc), "traceback": traceback.format_exc(), "utc": u.utc()},
        )
        raise


if __name__ == "__main__":
    main()
