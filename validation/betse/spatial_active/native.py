"""Active spatial native recording via the unchanged pinned FULL INIT loop."""

import argparse
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fresh_rerun"))
import common as u  # noqa: E402

base = u.private("active_spatial_capture", Path(__file__).parents[1] / "tissue_contact/native.py")


def channel(sim):
    return sim.molecules.core.channels["Kv1p5_spatial"].channel_core


def configuration(protocol, case):
    return {
        "general network": {
            "implement network": True,
            "biomolecules": [],
            "reactions": None,
            "transporters": None,
            "modulators": None,
            "channels": [
                {
                    "name": "Kv1p5_spatial",
                    "channel class": "K",
                    "channel type": "Kv1p5",
                    "max Dm": 0.0,
                    "apply to": "all",
                    "init active": True,
                }
            ],
        }
    }


def fixture(phase, protocol, case):
    import numpy as np

    sim, p = phase.sim, phase.p
    net, core = sim.molecules.core, channel(sim)
    u.need(
        not net.molecules
        and not net.reactions
        and not net.reactions_env
        and not net.transporters
        and not net.modulators
        and net.mit is None,
        "Only one ion channel is allowed in the native network",
    )
    u.need(
        list(net.channels) == ["Kv1p5_spatial"]
        and core.ions == ["K"]
        and core.rel_perm == [1.0]
        and (core._mpower, core._hpower) == (1, 1)
        and core.time_unit == 1000
        and core.v_corr == 0,
        "Changed native Kv1p5 identity",
    )
    np.testing.assert_array_equal(core.targets, np.arange(sim.mdl))
    u.need(
        p.T == protocol["temperature_K"]
        and sim.met_concs is None
        and sim.rho_pump == 1
        and sim.rho_channel == 1
        and p.substances_affect_charge,
        "Active settings changed",
    )
    p.alpha_NaK = case["pump_density_mol_m2_s"]
    for key, value in protocol["pump_parameters"].items():
        setattr(p, key, value)
    availability = np.resize(np.asarray(case["pump_availability_pattern"], dtype=float), sim.mdl)
    sim.NaKATP_block = availability
    core.m[:] = protocol["initial_gate"][0]
    core.h[:] = protocol["initial_gate"][1]
    net.channels["Kv1p5_spatial"].maxDm = p.tm * case["channel_permeability_m_s"]
    return {
        "active": {
            "pump_parameters": {key: getattr(p, key) for key in protocol["pump_parameters"]},
            "pump_availability": availability.tolist(),
            "initial_gate": protocol["initial_gate"],
            "channel_permeability_m_s": case["channel_permeability_m_s"],
            "channel_targets": core.targets.tolist(),
            "channel_type": "Kv1p5",
            "channel_initial_active": net.channels["Kv1p5_spatial"].init_active,
            "channel_modulation": net.channels["Kv1p5_spatial"].alpha_eval_string,
            "network_inventory": {
                key: list(getattr(net, key))
                for key in (
                    "molecules",
                    "reactions",
                    "reactions_env",
                    "transporters",
                    "channels",
                    "modulators",
                )
            },
            "substances_affect_charge": p.substances_affect_charge,
        }
    }


def snapshot(sim):
    import numpy as np

    core = channel(sim)
    values = base.snapshot(sim)
    values.update(
        {
            "m_gate": core.m,
            "h_gate": core.h,
            "channel_flux": core.chan_flux,
            "rate_NaKATP": getattr(sim, "rate_NaKATP", np.zeros(sim.mdl)),
            "extra_J_mem": sim.extra_J_mem,
        }
    )
    return {key: np.asarray(value).copy() for key, value in values.items()}


class Observer(base.Observer):
    def __init__(self, phase, science):
        super().__init__(phase, science, snapshotter=snapshot)
        self.network_source = str(science / "chemistry/networks.py")

    def observe(self, frame, event, argument):
        from loop_observer import successful_return

        if (
            self.loop_frame is not None
            and frame.f_code.co_filename == self.network_source
            and frame.f_locals.get("self") is self.phase.sim.molecules.core
            and frame.f_code.co_name == "run_loop_channels"
            and (event == "call" or (event == "return" and successful_return(frame)))
        ):
            self.records.append(
                {
                    "method": 4,
                    "after": event == "return",
                    "ion": -1,
                    "step": self.step,
                    "raw_label_s": float(self.loop_frame.f_locals["t"]),
                    "state": snapshot(self.phase.sim),
                }
            )
        super().observe(frame, event, argument)

    def validate_complete(self):
        u.need(self.calls == self.returns == 1, "Incomplete active native loop")
        u.need(self.step == self.phase.p.init_tsteps == len(self.labels), "Active clock changed")
        expected = [
            (method, after, ion)
            for ion in self.phase.sim.movingIons
            for method in (0, 1)
            for after in (False, True)
        ]
        expected += [(method, after, -1) for method in (4, 2, 3) for after in (False, True)]
        for step, label in enumerate(self.labels):
            records = [row for row in self.records if row["step"] == step]
            u.need(
                [(r["method"], r["after"], r["ion"]) for r in records] == expected,
                "Active native order changed",
            )
            u.need(all(r["raw_label_s"] == label for r in records), "Active labels changed")


def main(adapter=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=Path("/mnt/workspaces/Cells"))
    args = parser.parse_args()
    output = args.output.resolve()
    u.need(
        output.is_relative_to("/mnt/workspaces") and not output.exists(), "Fresh output required"
    )
    output.mkdir(parents=True)
    protocol, rows = u.read(args.protocol), []
    try:
        for case in protocol["cases"]:
            for index, dt in enumerate(protocol["native_steps_s"]):
                for mode in ("observed", "bare"):
                    name = f"{case['id']}/step-{index}/{mode}"
                    result = base.run_row(
                        output / name,
                        args.workspace,
                        protocol,
                        case,
                        dt,
                        mode,
                        adapter=sys.modules[__name__] if adapter is None else adapter,
                    )
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
