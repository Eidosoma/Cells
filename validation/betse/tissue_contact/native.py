"""Pinned BETSE spatial driver capture; fixture writes precede neutral observation."""

import argparse
import hashlib
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fresh_rerun"))
import common as u  # noqa: E402

seed = u.private("tissue_native_seed", Path(__file__).parents[1] / "junction_transport/native.py")
base = u.private(
    "tissue_native_fixture", Path(__file__).parents[1] / "junction_trajectory/native.py"
)
FIELDS = (
    "cc_cells",
    "cc_at_mem",
    "cc_env",
    "vm",
    "vm_ave",
    "gjopen",
    "fluxes_gj",
    "fluxes_mem",
    "rho_cells",
    "Phi_b",
    "v_env",
    "E_env_x",
    "E_env_y",
    "fluxes_env_x",
    "fluxes_env_y",
)
METHODS = ("update_gj", "update_ecm", "update_all_concs", "update_V")


def snapshot(sim):
    import numpy as np

    return {k: np.asarray(getattr(sim, k)).copy() for k in FIELDS}


class Observer:
    def __init__(self, phase, science, snapshotter=snapshot):
        self.phase, self.source = phase, str(science / "sim.py")
        self.snapshot = snapshotter
        self.loop_frame, self.initial = None, None
        self.records, self.labels = [], []
        self.step = self.calls = self.returns = 0

    def observe(self, frame, event, argument):
        from loop_observer import successful_return

        if event not in ("call", "return") or (event == "return" and not successful_return(frame)):
            return
        if (
            frame.f_code.co_filename != self.source
            or frame.f_locals.get("self") is not self.phase.sim
        ):
            return
        name = frame.f_code.co_name
        if name == "_run_sim_core_loop":
            if event == "call":
                self.calls += 1
                self.loop_frame = frame
                self.labels = frame.f_locals["time_steps"].tolist()
                self.initial = self.snapshot(self.phase.sim)
            else:
                self.returns += 1
                self.loop_frame = None
        elif self.loop_frame is not None and name in METHODS:
            self.records.append(
                {
                    "method": METHODS.index(name),
                    "after": event == "return",
                    "ion": int(frame.f_locals["i"]) if name in METHODS[:2] else -1,
                    "step": self.step,
                    "raw_label_s": float(self.loop_frame.f_locals["t"]),
                    "state": self.snapshot(self.phase.sim),
                }
            )
            if name == "update_V" and event == "return":
                self.step += 1

    def validate_complete(self):
        u.need(self.calls == self.returns == 1, "Incomplete native loop")
        u.need(self.step == self.phase.p.init_tsteps == len(self.labels), "Native clock changed")
        expected = []
        for i in self.phase.sim.movingIons:
            expected += [(0, False, i), (0, True, i), (1, False, i), (1, True, i)]
        expected += [(2, False, -1), (2, True, -1), (3, False, -1), (3, True, -1)]
        for step, label in enumerate(self.labels):
            rows = [r for r in self.records if r["step"] == step]
            u.need(
                [(r["method"], r["after"], r["ion"]) for r in rows] == expected,
                "Native transport/field order changed",
            )
            u.need(all(r["raw_label_s"] == label for r in rows), "Native labels changed")

    def save(self, path):
        import numpy as np

        values = {
            k: np.asarray([r[k] for r in self.records])
            for k in ("method", "after", "ion", "step", "raw_label_s")
        }
        values.update({k: np.stack([r["state"][k] for r in self.records]) for k in self.initial})
        values.update({"initial_" + k: v for k, v in self.initial.items()})
        np.savez_compressed(path, **values)


def fixture(phase, prepared, protocol, case):
    import numpy as np

    sim, cells, p = phase.sim, phase.cells, phase.p
    record = base.fixture(phase, prepared, protocol, case)
    ids = [prepared["species"][s] for s in protocol["species"]]
    protein = record["protein_index"]
    sim.cc_env[ids] = np.asarray(protocol["outside_mM"])[:, None]
    charges = np.asarray(sim.zs).copy()
    charges[protein] = 0
    sim.cc_env[protein] = -(charges @ sim.cc_env) / sim.zs[protein]
    sim.c_env_bound[:] = sim.cc_env[:, 0]
    # A declared synthetic pulse, including boundary sites to expose reservoir resets.
    x = (cells.X - cells.X.min()) / (cells.X.max() - cells.X.min())
    y = (cells.Y - cells.Y.min()) / (cells.Y.max() - cells.Y.min())
    pulse = (0.25 + np.sin(np.pi * x) * np.sin(np.pi * y)).ravel()
    for name, amplitude in case["outside_pulse_mM"].items():
        sim.cc_env[prepared["species"][name]] += amplitude * pulse
    for ion, permeability in zip(ids, case["membrane_permeability_m_s"], strict=True):
        sim.Dm_cells[ion] = permeability * p.tm
    sim.bound_V.update(case["boundary_voltage_V"])
    u.need(
        np.min(sim.cc_env) > 0 and p.is_ecm and p.sharpness == 1.0,
        "Invalid spatial fixture or smoothing",
    )
    record.update(
        outside_pulse_mM=case["outside_pulse_mM"],
        membrane_permeability_m_s=case["membrane_permeability_m_s"],
        boundary_voltage_V=dict(sim.bound_V),
    )
    return record


def run_row(directory, workspace, protocol, case, dt, mode, *, adapter=None):
    import betse
    import numpy as np

    began = time.monotonic()
    phase, prepared = seed.preparation(
        directory,
        workspace,
        clock=(dt, protocol["duration_s"]),
        extracellular=True,
        configuration_overrides=None if adapter is None else adapter.configuration(protocol, case),
    )
    sim, cells, p = phase.sim, phase.cells, phase.p
    p.v_sensitive_gj, p.gj_surface = False, protocol["gj_surface_fraction"]
    u.module_path("channel_loop_preparation")
    from loop_observer import InitialConditionHook

    science = Path(betse.__file__).resolve().parent / "science"
    observer_type = Observer if adapter is None else adapter.Observer
    observer = observer_type(phase, science) if mode == "observed" else None
    applied = {}

    def initialise(value):
        applied.update(fixture(value, prepared, protocol, case))
        if adapter is not None:
            applied.update(adapter.fixture(value, protocol, case))

    try:
        hook = (
            adapter.hook(phase, science, initialise, observer, protocol, case, applied)
            if adapter is not None and hasattr(adapter, "hook")
            else InitialConditionHook(phase, science, initialise, observer)
        )
        with hook:
            sim.run_sim_core(phase)
        u.need(
            p.dt == dt and p.init_tsteps == round(protocol["duration_s"] / dt),
            "Changed native clock",
        )
        u.need(Path(p.init_pickle_filename).is_file(), "Native checkpoint missing")
        u.need(
            not any(n == "cells" or n.startswith("cells.") for n in sys.modules),
            "Native capture imported Cells",
        )
        geometry = prepared["geometry"] | {
            k: np.asarray(getattr(cells, k)).tolist()
            for k in (
                "X",
                "Y",
                "map_mem2ecm",
                "M_divmap_mem2ecm",
                "delta",
                "diviterm",
                "memSa_per_envSquare",
                "lapENVinv",
            )
        }
        parameters = {
            k: getattr(p, k)
            for k in (
                "F",
                "R",
                "q",
                "kb",
                "T",
                "cm",
                "tm",
                "cell_height",
                "cell_radius",
                "true_cell_size",
                "eo",
                "er",
                "sharpness",
                "is_ecm",
                "fast_update_ecm",
                "cell_polarizability",
                "fluid_flow",
                "alpha_NaK",
                "alpha_Ca",
                "cluster_open",
                "Ca_dyn",
                "molecules_enabled",
                "grn_enabled",
            )
        }
        arrays = {
            k: np.asarray(getattr(sim, k)).tolist()
            for k in (
                "D_env",
                "TJ_modulator",
                "D_gj",
                "Dm_cells",
                "zs",
                "c_env_bound",
                "ko_env",
                "extra_rho_cells",
                "extra_rho_env",
            )
        }
        final = base.fingerprints(sim)
        for k, v in (snapshot(sim) if adapter is None else adapter.snapshot(sim)).items():
            final[k] = {
                "shape": list(v.shape),
                "dtype": v.dtype.str,
                "sha256": hashlib.sha256(v.tobytes()).hexdigest(),
            }
        if observer is not None:
            observer.save(directory / "trace.npz")
        row = {
            "case": case,
            "dt_s": dt,
            "steps": p.init_tsteps,
            "mode": mode,
            "fixture": applied,
            "geometry": geometry,
            "parameters": parameters,
            "arrays": arrays,
            "species": prepared["species"],
            "final": final,
            "preparation_sha256": u.sha(directory / "preparation.json"),
            "trace_sha256": None if observer is None else u.sha(directory / "trace.npz"),
            "hook_restored": sys.getprofile() is None,
            "native_pickle_present": True,
            "elapsed_seconds": time.monotonic() - began,
        }
        u.write(directory / "result.json", row)
        return row
    except BaseException:
        if observer is not None and observer.records:
            observer.save(directory / "partial-trace.npz")
        u.write(directory / "failure.json", {"traceback": traceback.format_exc(), "utc": u.utc()})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=Path("/mnt/workspaces/Cells"))
    args = parser.parse_args()
    output = args.output.resolve()
    u.need(
        output.is_relative_to("/mnt/workspaces") and not output.exists(),
        "Fresh workspace output required",
    )
    output.mkdir(parents=True)
    protocol, rows = u.read(args.protocol), []
    try:
        for case in protocol["cases"]:
            for index, dt in enumerate(protocol["native_steps_s"]):
                for mode in ("observed", "bare"):
                    name = f"{case['id']}/step-{index}/{mode}"
                    result = run_row(output / name, args.workspace, protocol, case, dt, mode)
                    rows.append({"path": name, "sha256": u.sha(output / name / "result.json")})
                    u.budget(output)
                    print(
                        name, "recorded", round(result["elapsed_seconds"], 3), "seconds", flush=True
                    )
        u.write(output / "panel.json", {"protocol": protocol, "rows": rows})
        u.write(
            output / "completion.json",
            {
                "status": "native_spatial_contact_recorded",
                "panel_sha256": u.sha(output / "panel.json"),
                "utc": u.utc(),
            },
        )
    except BaseException:
        u.write(
            output / "failure.json",
            {"status": "failed", "traceback": traceback.format_exc(), "utc": u.utc()},
        )
        raise


if __name__ == "__main__":
    main()
