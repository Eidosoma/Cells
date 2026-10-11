"""Pinned BETSE geometry and held-open junction entrypoints; no Cells imports."""

import argparse
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fresh_rerun"))
import common as u  # noqa: E402
import prepare  # noqa: E402


def preparation(
    output, workspace, *, clock=None, extracellular=False, configuration_overrides=None
):
    native, package, template, upstream, np = prepare.native_setup(workspace)
    from betse.science.enum.enumphase import SimPhaseKind
    from betse.science.parameters import Parameters
    from betse.science.phase.phasecls import SimPhase
    from betse.science.simrunner import SimRunner
    from ruamel.yaml import YAML

    protocol = u.read(native.ctx.PROTOCOL)
    variant = next(v for v in protocol["variants"] if v["id"] == "all_blocked")
    output.mkdir(parents=True, exist_ok=False)
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    configuration = native.ctx.configuration(template, protocol, variant, output)
    if configuration_overrides is not None:
        configuration.update(configuration_overrides)
    if extracellular:
        configuration["general options"]["simulate extracellular spaces"] = True
    if clock is not None:
        dt, duration = clock
        u.need(0 < dt <= duration, "Invalid junction preparation clock")
        for name in ("init time settings", "sim time settings"):
            configuration[name].update(
                {"time step": dt, "total time": duration, "sampling rate": dt}
            )
    with (output / "native.yaml").open("x") as stream:
        yaml.dump(configuration, stream)
    p = Parameters()
    p.load(str(output / "native.yaml"))
    p.F, p.R = (protocol["constants"][k] for k in ("F", "R"))
    np.random.seed(protocol["seed"])
    cells = SimRunner(p).seed().cells
    phase = SimPhase(kind=SimPhaseKind.INIT, cells=cells, p=p)
    phase.sim.init_core(phase)
    geometry = {
        name: np.asarray(getattr(cells, name)).tolist()
        for name in (
            "cell_i",
            "mem_i",
            "mem_to_cells",
            "nn_i",
            "cell_nn_i",
            "mem_sa",
            "cell_sa",
            "cell_vol",
            "gj_len",
            "gj_default_weights",
            "bflags_mems",
            "M_sum_mems",
            "cell_centres",
        )
    }
    geometry["canonical_face_pairs"] = [[int(i), int(j)] for i, j in enumerate(cells.nn_i) if i < j]
    record = {
        "geometry": geometry,
        "species": {name: int(phase.sim.get_ion(name)) for name in ("Na", "K", "Cl")},
        "native_D_gj_m2_s": phase.sim.D_gj.tolist(),
        "native_valences": phase.sim.zs.tolist(),
        "temperature_K": p.T,
        "constants": {"F": p.F, "R": p.R},
        "upstream": upstream,
        "runtime": u.runtime(),
        "scope": "actual native seed and init_core only; no junction trajectory",
    }
    u.write(output / "preparation.json", record)
    u.need(
        not any(k == "cells" or k.startswith("cells.") for k in sys.modules),
        "Native preparation imported Cells",
    )
    return phase, record


def panel(output, workspace, protocol):
    phase, prepared = preparation(output, workspace)
    import numpy as np

    sim, cells, p = phase.sim, phase.cells, phase.p
    p.v_sensitive_gj = False
    p.gj_surface, p.dt = protocol["gj_surface_fraction"], protocol["dt_s"]
    owners = np.asarray(cells.mem_to_cells)
    n = len(cells.cell_i)
    rows = []
    for name in protocol["species"]:
        i = prepared["species"][name]
        z = float(sim.zs[i])
        for fixture in protocol["fixtures"]:
            voltage = np.linspace(-0.06, 0.06, n)
            concentration = np.linspace(10.0, 70.0, n)
            if fixture in ("equal", "chemical"):
                voltage *= 0
            if fixture in ("equal", "electrical"):
                concentration[:] = 20.0
            if fixture == "equilibrium":
                concentration = 20.0 * np.exp(-z * p.F * voltage / (p.R * p.T))
            for topology in protocol["topologies"]:
                topology_mask = np.zeros(sim.mdl)
                pairs = prepared["geometry"]["canonical_face_pairs"]
                selected = pairs if topology == "all" else pairs[:1] if topology == "single" else []
                for a, b in selected:
                    topology_mask[[a, b]] = 1.0
                for block in protocol["blocks"]:
                    sim.movingIons = [i]
                    sim.gj_block = topology_mask * block
                    sim.vm = voltage[owners].copy()
                    sim.cc_cells[i] = concentration.copy()
                    sim.cc_at_mem[i] = concentration[owners].copy()
                    sim.fluxes_mem[:] = 0
                    sim.fluxes_gj[:] = 0
                    before_env = np.asarray(sim.cc_env[i]).copy()
                    sim.update_gj(cells, p, 0.0, i)
                    flux = sim.fluxes_gj[i].copy()
                    gate = sim.gjopen.copy()
                    after_voltage_argument = sim.vgj.copy()
                    sim.update_all_concs(cells, p)
                    rows.append(
                        {
                            "species": name,
                            "valence": z,
                            "fixture": fixture,
                            "topology": topology,
                            "block": block,
                            "concentration_before_mM": concentration.tolist(),
                            "voltage_clamp_V": voltage.tolist(),
                            "gjopen": gate.tolist(),
                            "native_density_mol_m2_s": flux.tolist(),
                            "concentration_after_mM": sim.cc_cells[i].tolist(),
                            "at_membrane_after_update_mM": sim.cc_at_mem[i].tolist(),
                            "environment_before_mM": before_env.tolist(),
                            "environment_after_mM": np.asarray(sim.cc_env[i]).tolist(),
                            "voltage_argument_after_native_call_V": after_voltage_argument.tolist(),
                        }
                    )
    u.need(
        not any(k == "cells" or k.startswith("cells.") for k in sys.modules),
        "Native panel imported Cells",
    )
    u.write(output / "panel.json", {"protocol": protocol, "rows": rows})
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=Path("/mnt/workspaces/Cells"))
    parser.add_argument("--protocol", type=Path)
    args = parser.parse_args()
    try:
        if args.protocol:
            panel(args.output.resolve(), args.workspace.resolve(), u.read(args.protocol))
        else:
            preparation(args.output.resolve(), args.workspace.resolve())
        u.write(
            args.output / "completion.json",
            {
                "status": (
                    "native_held_open_panel_recorded"
                    if args.protocol
                    else "native_junction_seed_prepared"
                ),
                "preparation_sha256": u.sha(args.output / "preparation.json"),
                "utc": u.utc(),
            },
        )
    except BaseException:
        if args.output.exists():
            u.write(args.output / "failure.json", {"traceback": traceback.format_exc()})
        raise
