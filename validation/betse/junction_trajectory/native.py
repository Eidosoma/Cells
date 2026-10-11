"""Unmodified FULL-driver held-open junction trajectories and neutral observation."""

import argparse
import hashlib
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fresh_rerun"))
import common as u  # noqa: E402


def snapshot(sim):
    import numpy as np

    return {
        k: np.asarray(getattr(sim, k)).copy()
        for k in (
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
        )
    }


def fingerprints(sim):
    import numpy as np

    return {
        k: {
            "shape": list(v.shape),
            "dtype": v.dtype.str,
            "sha256": hashlib.sha256(v.tobytes()).hexdigest(),
        }
        for k, v in (
            list(snapshot(sim).items())
            + [
                (k, np.asarray(getattr(sim, k)))
                for k in ("cc_time", "vm_time", "gjopen_time", "time")
            ]
        )
    }


class Observer:
    def __init__(self, phase, science, directory):
        self.phase, self.directory = phase, directory
        self.source = str(science / "sim.py")
        self.loop_frame = None
        self.initial = None
        self.steps, self.pending, self.labels, self.order = [], None, [], []
        self.loop_calls = self.loop_returns = 0

    def observe(self, frame, event, argument):
        from loop_observer import successful_return

        if event not in ("call", "return") or (event == "return" and not successful_return(frame)):
            return
        sim = self.phase.sim
        if frame.f_code.co_filename != self.source or frame.f_locals.get("self") is not sim:
            return
        name = frame.f_code.co_name
        if name == "_run_sim_core_loop":
            if event == "call":
                self.loop_calls += 1
                self.loop_frame = frame
                self.initial = snapshot(sim)
                self.labels = frame.f_locals["time_steps"].tolist()
                u.write(
                    self.directory / "loop-entry.json",
                    {
                        "initial": {k: v.tolist() for k, v in self.initial.items()},
                        "native_labels_s": self.labels,
                    },
                )
            else:
                self.loop_returns += 1
                self.loop_frame = None
            return
        if self.loop_frame is None:
            return
        if name == "update_gj" and event == "call":
            ion = int(frame.f_locals["i"])
            if self.pending is None:
                self.pending = {
                    "before": snapshot(sim),
                    "order": [],
                    "raw_label_s": float(self.loop_frame.f_locals["t"]),
                }
            self.pending["order"].append(ion)
        elif name == "update_all_concs" and event == "call":
            u.need(self.pending is not None, "Concentration update before junction calls")
            self.pending["transport"] = snapshot(sim)
        elif name == "update_V" and event == "return":
            u.need(self.pending is not None, "Unpaired voltage update")
            self.pending["after"] = snapshot(sim)
            self.steps.append(self.pending)
            self.pending = None

    def validate_complete(self):
        u.need(
            self.loop_calls == self.loop_returns == 1 and self.pending is None,
            "Incomplete native loop lifecycle",
        )
        u.need(
            len(self.steps) == self.phase.p.init_tsteps == len(self.labels),
            "Incomplete native physical clock",
        )
        u.need(
            all(s["order"] == self.phase.sim.movingIons for s in self.steps),
            "Native ion order changed",
        )
        u.need(
            [s["raw_label_s"] for s in self.steps] == self.labels,
            "Native labels lost their actual step association",
        )

    def save(self, name="trace.npz"):
        import numpy as np

        values = {"native_labels_s": np.asarray(self.labels[: len(self.steps)])}
        for boundary in ("before", "transport", "after"):
            for field in self.initial:
                values[boundary + "_" + field] = np.stack([s[boundary][field] for s in self.steps])
        values.update({"initial_" + k: v for k, v in self.initial.items()})
        values["species_order"] = np.asarray([s["order"] for s in self.steps])
        np.savez_compressed(self.directory / name, **values)


def fixture(phase, prepared, protocol, case):
    import numpy as np

    sim, cells, p = phase.sim, phase.cells, phase.p
    ids = [prepared["species"][s] for s in protocol["species"]]
    coordinate = np.linspace(-1.0, 1.0, len(cells.cell_i))
    coordinate -= np.dot(cells.cell_sa, coordinate) / np.sum(cells.cell_sa)
    shape = case["fixture"]
    if shape == "reverse":
        coordinate *= -1
    voltage = coordinate * protocol["initial_voltage_extent_V"]
    concentration = np.asarray(protocol["base_concentration_mM"])[:, None] + (
        np.asarray(protocol["concentration_gradient_mM"])[:, None] * coordinate
    )
    if shape in ("equal", "chemical"):
        voltage *= 0
    if shape in ("equal", "electrical"):
        concentration[:] = np.asarray(protocol["base_concentration_mM"])[:, None]
    if shape == "equilibrium":
        concentration = np.asarray(protocol["base_concentration_mM"])[:, None] * np.exp(
            -np.asarray(sim.zs)[ids, None] * p.F * voltage / (p.R * p.T)
        )
    sim.cc_cells[ids] = concentration
    # The fixed protein charge is a declared preparation variable. Only this
    # one-time fixture changes it; it is immobile throughout the actual run.
    protein = sim.get_ion("P")
    other = np.asarray(sim.zs).copy()
    other[protein] = 0
    required = voltage * p.cm / (p.F * cells.diviterm)
    sim.cc_cells[protein] = (required - other @ sim.cc_cells) / sim.zs[protein]
    u.need(np.min(sim.cc_cells) > 0, "Invalid native fixture concentration")
    sim.cc_at_mem[:] = sim.cc_cells[:, cells.mem_to_cells]
    sim.movingIons = ids
    sim.gj_block = np.zeros(sim.mdl)
    pairs = prepared["geometry"]["canonical_face_pairs"]
    selected = (
        pairs if case["topology"] == "all" else pairs[:1] if case["topology"] == "single" else []
    )
    for a, b in selected:
        sim.gj_block[[a, b]] = 1.0
    u.need(
        np.all(sim.Dm_cells == 0) and p.alpha_NaK == p.alpha_Ca == 0,
        "Fixture unexpectedly has membrane transport",
    )
    return {
        "target_voltage_V": voltage.tolist(),
        "selected_face_pairs": selected,
        "moving_ions": ids,
        "protein_index": int(protein),
        "after_setup": {
            "cc_cells": sim.cc_cells.tolist(),
            "cc_at_mem": sim.cc_at_mem.tolist(),
            "gj_block": sim.gj_block.tolist(),
        },
    }


def run_row(directory, workspace, protocol, case, dt, mode):
    import betse

    seed = u.private("junction_seed", Path(__file__).parents[1] / "junction_transport/native.py")
    phase, prepared = seed.preparation(directory, workspace, clock=(dt, protocol["duration_s"]))
    sim, cells, p = phase.sim, phase.cells, phase.p
    p.v_sensitive_gj, p.gj_surface = False, protocol["gj_surface_fraction"]
    u.module_path("channel_loop_preparation")
    from loop_observer import InitialConditionHook

    science = Path(betse.__file__).resolve().parent / "science"
    observer = Observer(phase, science, directory) if mode == "observed" else None
    applied = {}
    try:
        with InitialConditionHook(
            phase,
            science,
            lambda value: applied.update(fixture(value, prepared, protocol, case)),
            observer,
        ):
            sim.run_sim_core(phase)
        u.need(
            p.dt == dt and p.init_tsteps == round(protocol["duration_s"] / dt),
            "Native clock differs from registration",
        )
        u.need(Path(p.init_pickle_filename).is_file(), "Native checkpoint missing")
        if observer is not None:
            observer.save()
        row = {
            "case": case,
            "dt_s": dt,
            "steps": int(p.init_tsteps),
            "mode": mode,
            "fixture": applied,
            "final": fingerprints(sim),
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
                )
            },
            "trace_sha256": None if observer is None else u.sha(directory / "trace.npz"),
        }
        u.write(directory / "result.json", row)
        return row
    except BaseException:
        failure = {"traceback": traceback.format_exc(), "hook_restored": sys.getprofile() is None}
        if observer is not None and observer.steps:
            failure["completed_observed_steps"] = len(observer.steps)
            try:
                observer.save("partial-trace.npz")
            except Exception as exc:
                failure["partial_recording_error"] = str(exc)
        u.write(
            directory / "failure.json",
            failure,
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=Path("/mnt/workspaces/Cells"))
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    protocol = u.read(args.protocol)
    rows = []
    try:
        for case in protocol["cases"]:
            for j, dt in enumerate(protocol["native_steps_s"]):
                for mode in protocol["native_modes"]:
                    name = f"{case['id']}/step-{j}/{mode}"
                    run_row(output / name, args.workspace, protocol, case, dt, mode)
                    rows.append({"path": name, "sha256": u.sha(output / name / "result.json")})
                    u.budget(output)
                    sizes = [p.stat().st_size for p in output.rglob("*") if p.is_file()]
                    used = sum(sizes)
                    u.need(used < protocol["resources"]["artifact_bytes"], "Junction artifact cap")
                    u.need(
                        max(sizes, default=0) <= protocol["resources"]["per_file_bytes"],
                        "Junction per-file cap",
                    )
                    print(name, "recorded", flush=True)
        u.need(
            not any(k == "cells" or k.startswith("cells.") for k in sys.modules),
            "Native process imported Cells",
        )
        u.write(output / "panel.json", {"protocol": protocol, "rows": rows})
        u.write(
            output / "completion.json",
            {
                "status": "native_held_open_trajectories_recorded",
                "panel_sha256": u.sha(output / "panel.json"),
                "utc": u.utc(),
            },
        )
    except BaseException:
        u.write(output / "failure.json", {"traceback": traceback.format_exc(), "utc": u.utc()})
        raise


if __name__ == "__main__":
    main()
