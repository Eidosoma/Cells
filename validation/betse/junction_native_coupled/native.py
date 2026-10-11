"""Free-voltage FULL driver: neutral step and per-ion gate observation."""

import argparse
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fresh_rerun"))
import common as u  # noqa: E402

base = u.private(
    "native_held_open_trajectory", Path(__file__).parents[1] / "junction_trajectory/native.py"
)


class Observer(base.Observer):
    def __init__(self, phase, science, directory):
        super().__init__(phase, science, directory)
        self.gate_file = str(science / "channels/gap_junction.py")
        self.calls, self.active = [], None

    def observe(self, frame, event, argument):
        import numpy as np
        from loop_observer import successful_return

        super().observe(frame, event, argument)
        if self.loop_frame is None or frame.f_code.co_filename != self.gate_file:
            return
        if (
            frame.f_code.co_name != "run"
            or frame.f_locals.get("self") is not self.phase.sim.gj_funk
        ):
            return
        sim = self.phase.sim
        if event == "call":
            u.need(self.active is None and self.pending is not None, "Unpaired gate call")
            self.active = {
                "before": sim.gjopen.copy(),
                "voltage": sim.vgj.copy(),
                "block": np.broadcast_to(sim.gj_block, sim.gjopen.shape).copy(),
                "species": int(frame.f_back.f_locals["i"]),
                "step": len(self.steps),
            }
        elif event == "return" and successful_return(frame):
            u.need(self.active is not None, "Gate return without call")
            self.calls.append(self.active | {"after": sim.gjopen.copy()})
            self.active = None

    def validate_complete(self):
        super().validate_complete()
        u.need(
            self.active is None
            and len(self.calls) == len(self.steps) * len(self.phase.sim.movingIons),
            "Incomplete dynamic gate trace",
        )

    def save(self, name="trace.npz"):
        import numpy as np

        super().save(name)
        if self.calls:
            np.savez_compressed(
                self.directory / ("gates.npz" if name == "trace.npz" else "partial-gates.npz"),
                **{k: np.asarray([r[k] for r in self.calls]) for k in self.calls[0]},
            )


def run_row(directory, workspace, protocol, case, dt, mode):
    import betse
    import numpy as np

    protocol = protocol | {
        key: case[key]
        for key in ("duration_s", "observation_step_s", "restart_time_s")
        if key in case
    }
    began = time.monotonic()
    seed = u.private("dynamic_seed", Path(__file__).parents[1] / "junction_transport/native.py")
    phase, prepared = seed.preparation(directory, workspace, clock=(dt, protocol["duration_s"]))
    sim, cells, p = phase.sim, phase.cells, phase.p
    p.v_sensitive_gj, p.gj_surface = True, protocol["gj_surface_fraction"]
    p.gj_min, p.gj_vthresh = (
        protocol["minimum_open_fraction"],
        1000 * protocol["threshold_voltage_V"],
    )
    u.module_path("channel_loop_preparation")
    from loop_observer import InitialConditionHook

    science = Path(betse.__file__).resolve().parent / "science"
    observer = Observer(phase, science, directory) if mode == "observed" else None
    applied = {}

    def initialize(value):
        record = base.fixture(value, prepared, protocol, case)
        sim.movingIons = [prepared["species"][name] for name in case["order"]]
        sim.gj_block *= case["block"]
        sim.gjopen[:] = protocol["initial_gate"] * np.asarray(cells.gj_default_weights)
        record["moving_ions"] = list(sim.movingIons)
        record["after_setup"].update(gj_block=sim.gj_block.tolist(), gjopen=sim.gjopen.tolist())
        applied.update(record)

    try:
        with InitialConditionHook(phase, science, initialize, observer):
            sim.run_sim_core(phase)
        u.need(p.dt == dt and p.init_tsteps == round(protocol["duration_s"] / dt), "Changed clock")
        u.need(Path(p.init_pickle_filename).is_file(), "Native checkpoint missing")
        if observer is not None:
            observer.save()
        row = {
            "case": case,
            "dt_s": dt,
            "steps": int(p.init_tsteps),
            "mode": mode,
            "fixture": applied,
            "final": base.fingerprints(sim),
            "hook_restored": sys.getprofile() is None,
            "native_pickle_present": True,
            "preparation_sha256": u.sha(directory / "preparation.json"),
            "specific_capacitance_F_m2": p.cm,
            "diviterm_m": cells.diviterm.tolist(),
            "effective_bath_volume_pL": len(cells.mem_i) * p.vol_env * 1e15,
            "settings": {
                k: getattr(p, k)
                for k in (
                    "is_ecm",
                    "cell_polarizability",
                    "alpha_NaK",
                    "alpha_Ca",
                    "Ca_dyn",
                    "molecules_enabled",
                    "grn_enabled",
                    "fluid_flow",
                    "deformation",
                    "deform_osmo",
                    "dynamic_noise",
                    "channel_noise_level",
                    "v_sensitive_gj",
                    "gj_surface",
                    "gj_min",
                    "gj_vthresh",
                )
            },
            "trace_sha256": None if observer is None else u.sha(directory / "trace.npz"),
            "gates_sha256": None if observer is None else u.sha(directory / "gates.npz"),
            "elapsed_seconds": time.monotonic() - began,
        }
        u.write(directory / "result.json", row)
        return row
    except BaseException:
        if observer is not None and observer.steps:
            observer.save("partial-trace.npz")
        u.write(directory / "failure.json", {"traceback": traceback.format_exc(), "utc": u.utc()})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=Path("/mnt/workspaces/Cells"))
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    protocol, rows = u.read(args.protocol), []
    try:
        for case in protocol["cases"]:
            for index, dt in enumerate(protocol["native_steps_s"]):
                for mode in protocol["native_modes"]:
                    name = f"{case['id']}/step-{index}/{mode}"
                    row = run_row(output / name, args.workspace, protocol, case, dt, mode)
                    rows.append({"path": name, "sha256": u.sha(output / name / "result.json")})
                    u.budget(output)
                    sizes = [p.stat().st_size for p in output.rglob("*") if p.is_file()]
                    limits = protocol["resources"]
                    u.need(
                        sum(sizes) <= limits["artifact_bytes"]
                        and max(sizes, default=0) <= limits["per_file_bytes"],
                        "Native dynamic panel artifact limit",
                    )
                    print(name, "recorded", round(row["elapsed_seconds"], 3), "seconds", flush=True)
        u.need(
            not any(k == "cells" or k.startswith("cells.") for k in sys.modules),
            "Native imported Cells",
        )
        u.write(output / "panel.json", {"protocol": protocol, "rows": rows})
        u.write(
            output / "completion.json",
            {
                "status": "native_dynamic_free_voltage_recorded",
                "panel_sha256": u.sha(output / "panel.json"),
                "utc": u.utc(),
            },
        )
    except BaseException:
        u.write(output / "failure.json", {"traceback": traceback.format_exc(), "utc": u.utc()})
        raise


if __name__ == "__main__":
    main()
