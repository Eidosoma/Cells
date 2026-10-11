"""Unmodified native class on registered voltage-clamp/block schedules."""

import argparse
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fresh_rerun"))
import common as u  # noqa: E402
import prepare  # noqa: E402


def run(protocol, dt, calls, *, record):
    import numpy as np
    from betse.science.channels.gap_junction import Gap_Junction

    voltage = np.repeat(protocol["voltages_V"], len(protocol["initial_gates"]))
    initial = np.tile(protocol["initial_gates"], len(protocol["voltages_V"]))
    p = SimpleNamespace(
        dt=dt,
        gj_min=protocol["minimum_open_fraction"],
        gj_vthresh=1000 * protocol["threshold_voltage_V"],
    )
    sim = SimpleNamespace(vgj=voltage.copy(), gjopen=initial.copy(), gj_block=1.0)
    obj = Gap_Junction(sim, None, p)
    initialization = {"class_gate": obj.gjopen.tolist(), "sim_gate": sim.gjopen.tolist()}
    history, labels = [sim.gjopen.copy()], [0]
    step_index = 0
    for phase_index, phase in enumerate(protocol["phases"]):
        sim.vgj = voltage * phase["voltage_multiplier"]
        sim.gj_block = phase["availability"]
        count = round(phase["duration_s"] / dt)
        u.need(abs(count * dt - phase["duration_s"]) < 1e-15, "Unaligned clamp phase")
        for _ in range(count):
            for _ in range(calls):
                obj.run(sim, None, p)
            step_index += 1
            if record:
                history.append(sim.gjopen.copy())
                labels.append(phase_index)
    return initialization, sim.gjopen.copy(), np.asarray(history), np.asarray(labels)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    try:
        _, _, _, upstream, np = prepare.native_setup(args.workspace)
        protocol = u.read(args.protocol)
        rows = []
        for calls in protocol["calls_per_outer_step"]:
            for i, dt in enumerate(protocol["native_steps_s"]):
                init, final, gate, phase = run(protocol, dt, calls, record=True)
                bare_init, bare_final, _, _ = run(protocol, dt, calls, record=False)
                u.need(init == bare_init, "Native initialization observation changed")
                np.testing.assert_array_equal(final, bare_final)
                name = f"calls-{calls}-step-{i}.npz"
                np.savez_compressed(
                    output / name, gate=gate, phase=phase, times_s=np.arange(len(gate)) * dt
                )
                rows.append(
                    {
                        "path": name,
                        "sha256": u.sha(output / name),
                        "calls_per_outer_step": calls,
                        "dt_s": dt,
                        "steps": len(gate) - 1,
                        "initialization": init,
                        "observer_pair_exact": True,
                    }
                )
                print(name, "recorded; bare final matches", flush=True)
                u.budget(output)
        u.need(
            not any(k == "cells" or k.startswith("cells.") for k in sys.modules),
            "Native class process imported Cells",
        )
        u.write(
            output / "panel.json",
            {"protocol": protocol, "upstream": upstream, "runtime": u.runtime(), "rows": rows},
        )
        u.write(
            output / "completion.json",
            {
                "status": "native_junction_clamp_panel_recorded",
                "panel_sha256": u.sha(output / "panel.json"),
                "utc": u.utc(),
            },
        )
    except BaseException:
        u.write(output / "failure.json", {"traceback": traceback.format_exc(), "utc": u.utc()})
        raise


if __name__ == "__main__":
    main()
