"""REF-004b native worker: frozen D089 logic, with only the D090 configuration provider."""

import sys
from pathlib import Path

import setup_context as setup

t = setup.t
c = t.c


def native_worker(r, output):
    import betse
    import numpy as np
    from betse.science.enum.enumphase import SimPhaseKind
    from betse.science.parameters import Parameters
    from betse.science.phase.phasecls import SimPhase
    from betse.science.simrunner import SimRunner
    from ruamel.yaml import YAML

    package = Path(betse.__file__).resolve().parent
    installed = {f"betse/{p.relative_to(package)}": c.sha(p) for p in package.rglob("*.py")}
    expected = {
        k: v
        for k, v in r["upstream"]["files_sha256"].items()
        if k.startswith("betse/") and k.endswith(".py")
    }
    c.require(installed == expected, "Installed BETSE differs from pinned checkout")
    c.require(package.is_relative_to(c.REFERENCE_PYTHON.parent.parent), "Wrong BETSE origin")
    ptl, base = r["protocol"], r["base_protocol"]
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    with (c.SOURCE / "betse/data/yaml/sim_config.yaml").open() as handle:
        template = yaml.load(handle)
    preparations, rows = {}, {}

    def snapshot(sim):
        return {
            "inside_mM": sim.cc_cells.tolist(),
            "outside_mM": sim.cc_env.tolist(),
            "at_membrane_mM": sim.cc_at_mem.tolist(),
            "voltage_V": sim.vm.tolist(),
            "rho_C_per_m3": sim.rho_cells.tolist(),
            "boundary_voltage_V": sim.Phi_b.tolist(),
            "ordinary_density_mol_per_m2_s": sim.fluxes_mem.tolist(),
            "junction_density_mol_per_m2_s": sim.fluxes_gj.tolist(),
            "extra_current_density_A_per_m2": sim.extra_J_mem.tolist(),
            "Jmem_A_per_m2": sim.Jmem.tolist(),
            "Jn_A_per_m2": sim.Jn.tolist(),
            "I_mem_A": sim.I_mem.tolist(),
            "extra_rho_cells_C_per_m3": sim.extra_rho_cells.tolist(),
            "extra_rho_env_C_per_m3": sim.extra_rho_env.tolist(),
        }

    def channel_snapshot(chan):
        if chan is None:
            return None
        core = chan.channel_core
        return {
            "m": core.m.tolist(),
            "h": core.h.tolist(),
            "P": None if not hasattr(core, "P") else core.P.tolist(),
            "derived_m_times_h": (core.m * core.h).tolist(),
            "DChan_m2_per_s": None if core.DChan is None else core.DChan.tolist(),
            "density_mol_per_m2_s": core.chan_flux.tolist(),
            "modulator": np.asarray(core.modulator).tolist(),
        }

    for variant in ptl["variants"]:
        folder = output / "native" / variant["id"]
        folder.mkdir(parents=True, exist_ok=False)
        conf = setup.configuration(template, base, ptl, variant, folder)
        config_path = folder / "native.yaml"
        with config_path.open("x") as handle:
            yaml.dump(conf, handle)
        p = Parameters()
        p.load(str(config_path))
        # A declared matched-constant parameter intervention, before any preparation.
        source_constants = {"F": p.F, "R": p.R}
        p.F, p.R = ptl["constants"]["F"], ptl["constants"]["R"]
        np.random.seed(ptl["seed"])
        seeded = SimRunner(p).seed()
        cells = seeded.cells
        g = {
            "cell_count": len(cells.cell_i),
            "membrane_count": len(cells.mem_i),
            "cell_centres_m": cells.cell_centres.tolist(),
            "cell_volumes_m3": cells.cell_vol.tolist(),
            "cell_areas_m2": cells.cell_sa.tolist(),
            "membrane_owners": cells.mem_to_cells.tolist(),
            "membrane_areas_m2": cells.mem_sa.tolist(),
            "diviterm_m": cells.diviterm.tolist(),
            "configured_bath_volume_m3": p.vol_env,
            "effective_bath_volume_m3": len(cells.mem_i) * p.vol_env,
            "specific_capacitance_F_per_m2": p.cm,
            "grid_shape": list(cells.X.shape),
        }
        c.write(folder / "geometry.json", g)
        c.require(
            {key: g[key] for key in t.GEOMETRY_FIELDS} == r["expected_geometry"],
            "Native seeded geometry changed",
        )
        settings = {
            name: getattr(p, name)
            for name in (
                "is_ecm",
                "cell_polarizability",
                "cluster_open",
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
                "substances_affect_charge",
            )
        }
        settings |= {
            "solver": p.solver_type.name,
            "temperature_K": p.T,
            "thickness_m": p.tm,
            "constants": {"F": p.F, "R": p.R},
        }
        prep = {
            "geometry": g,
            "settings": settings,
            "native_config_sha256": c.sha(config_path),
            "source_constants": source_constants,
        }
        for fixture in ptl["states"]:
            # Fresh Simulator and dynamics each time; geometry is fixed, not state.
            phase = SimPhase(kind=SimPhaseKind.INIT, cells=cells, p=p)
            sim = phase.sim
            sim.init_core(phase)
            core_initial = {
                "inside_mM": sim.cc_cells.tolist(),
                "outside_mM": sim.cc_env.tolist(),
                "gate_initialization_voltage_V": sim.vm.tolist(),
            }
            sim.init_dynamics(phase)
            network = None if sim.molecules is None else sim.molecules.core
            channels = {} if network is None else network.channels
            chan = next(iter(channels.values())) if channels else None
            initialized = channel_snapshot(chan)
            sim.update_V(cells, p)
            if fixture["gate"] is not None and chan is not None:
                # An explicit initial condition; not inferred history, clipping or reinitialization.
                chan.channel_core.m[:] = fixture["gate"][0]
                chan.channel_core.h[:] = fixture["gate"][1]
            before, channel_before = snapshot(sim), channel_snapshot(chan)
            arrays = [sim.cc_cells, sim.cc_env, sim.cc_at_mem, sim.vm, sim.Dm_cells]
            if chan is not None:
                arrays += [chan.channel_core.m, chan.channel_core.h]
            c.require(all(value.dtype == np.float64 for value in arrays), "Native dtype differs")
            metadata = (
                None
                if chan is None
                else {
                    "name": chan.name,
                    "class": chan.channel_class,
                    "type": chan.channel_type,
                    "targets": chan.channel_core.targets.tolist(),
                    "target_profiles": chan.channel_profiles_list,
                    "init_active": chan.init_active,
                    "maxDm_m2_per_s": chan.maxDm,
                    "ions": chan.channel_core.ions,
                    "relative_permeability": chan.channel_core.rel_perm,
                    "powers": [chan.channel_core._mpower, chan.channel_core._hpower],
                    "time_unit": chan.channel_core.time_unit,
                    "alpha_eval_string": chan.alpha_eval_string,
                }
            )
            inventory = (
                None
                if network is None
                else {
                    key: list(getattr(network, key))
                    for key in (
                        "molecules",
                        "reactions",
                        "reactions_env",
                        "transporters",
                        "channels",
                        "modulators",
                    )
                }
            )
            start = {
                "id": f"{variant['id']}/{fixture['id']}",
                "core_initial": core_initial,
                "initialized_channel": initialized,
                "before": before,
                "channel_before": channel_before,
                "metadata": metadata,
                "network_inventory": inventory,
                "dt_s": p.dt,
                "sim_temperature_K": sim.T,
                "rho_channel": np.asarray(sim.rho_channel).tolist(),
                "ordinary_diffusivity_m2_per_s": sim.Dm_cells.tolist(),
                "species": [k for k, enabled in p.ions_dict.items() if enabled],
                "valence": sim.zs.tolist(),
                "dtype": "float64",
            }
            c.write(folder / f"{fixture['id']}-before.json", start)
            if network is not None:
                network.clear_run_loop(sim)
                if sim.molecules.channels:
                    network.run_loop_channels(phase)
            after_channel = snapshot(sim)
            channel_after = channel_snapshot(chan)
            network_current = [0.0] * sim.mdl if network is None else network.extra_J_mem.tolist()
            if network is not None:
                # Empty chemistry loop exports the real channel extra current.
                network.run_loop(phase, 0.0)
            after_network = snapshot(sim)
            # Ordinary arrays are zero: this must not apply the channel transfer twice.
            sim.update_all_concs(cells, p)
            after_ordinary = snapshot(sim)
            sim.update_V(cells, p)
            row = start | {
                "after_channel": after_channel,
                "channel_after": channel_after,
                "network_current_density_A_per_m2": network_current,
                "after_network": after_network,
                "after_ordinary": after_ordinary,
                "after_voltage": snapshot(sim),
                "smooth_weight_mem": sim.smooth_weight_mem.tolist(),
                "smooth_weight_other": sim.smooth_weight_o.tolist(),
                "call_counts": {
                    "channel_runner": int(variant["channel"]),
                    "empty_chemistry_runner": int(variant["network"]),
                    "ordinary_update": 1,
                    "full_simulator_loop": 0,
                },
            }
            c.write(folder / f"{fixture['id']}-after.json", row)
            rows[row["id"]] = row
        preparations[variant["id"]] = prep
        c.write(folder / "preparation.json", prep)
    c.require(
        not any(k == "cells" or k.startswith("cells.") for k in sys.modules),
        "Native worker imported Cells",
    )
    return {
        "engine": "unmodified_betse_native_channel_single_transfer",
        "preparations": preparations,
        "rows": rows,
        "environment": c.environment(),
        "installed_python_sha256": installed,
        "package_path": str(package),
        "full_trajectory_run": False,
        "upstream_patched": False,
    }
