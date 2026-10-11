"""REF-003b1: native seeded BETSE initialization and finite-bath model alignment.

This does not call either simulator's time-integration driver. Prescribed states
and fluxes exercise native initialization, update_V and update_all_concs, plus
the unchanged Cells finite-extracellular resolver, charge closure and RHS.
"""

import argparse
import copy
import hashlib
import json
import math
import os
import subprocess
import sys
import time
import traceback
import warnings
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import contact as c

PROTOCOL = c.HERE / "alignment_protocol.json"
PRESERVATION = c.ROOT / "reports/ref-003b1-preservation.json"
PRIOR = c.ROOT / "runs/ref-003a-2026-09-12/contact-01"
PRIOR_CLOSEOUT = c.ROOT / "reports/ref-003a-closeout.json"
PRIOR_CLOSEOUT_SHA = "59bfc0abf386d2a8e25efd716d9c1682d0e3d3178665fcf7ef112d082b33cd47"
FILES = ("alignment.py", "alignment_protocol.json", "test_alignment.py", "contact.py")


def preserve():
    c.require(c.sha(PRIOR_CLOSEOUT) == PRIOR_CLOSEOUT_SHA, "Prior closeout changed")
    previous = c.read(PRIOR_CLOSEOUT)
    c.require(c.audit(PRIOR) == previous["independent_audit"], "Prior contact audit differs")
    old = c.authenticate_cells()
    names = set(old["worktree_files_sha256"]) | set(previous["new_files_sha256_before_closeout"])
    names.add(str(PRIOR_CLOSEOUT.relative_to(c.ROOT)))
    result = {
        "schema": "cells.betse_alignment_preservation@1",
        "status": "pass",
        "prior_closeout_sha256": PRIOR_CLOSEOUT_SHA,
        "prior_contact": c.audit(PRIOR),
        "accepted_sources": old["implementation_files_sha256"],
        "baseline_sha256": {name: c.sha(c.ROOT / name) for name in sorted(names)},
        "created_utc": datetime.now(UTC).isoformat(),
    }
    c.write(PRESERVATION, result)
    print(json.dumps({"status": "pass", "baseline_files": len(names)}))


def authenticate():
    c.require(c.sha(PRIOR_CLOSEOUT) == PRIOR_CLOSEOUT_SHA, "Prior closeout changed")
    saved = c.read(PRESERVATION)
    c.require(saved["prior_contact"] == c.audit(PRIOR), "Prior capture changed")
    c.authenticate_cells()
    return saved


def source_hashes():
    return {name: c.sha(c.HERE / name) for name in FILES}


def configuration(base, protocol, config_dir=c.HERE):
    """Only declared YAML overrides; resolve existing geo asset paths, not code."""
    conf = copy.deepcopy(base)
    for path, value in protocol["yaml_overrides"]:
        target = conf
        for key in path[:-1]:
            target = target[key]
        c.require(path[-1] in target, f"Unknown YAML option: {path}")
        target[path[-1]] = value

    def assets(value):
        if isinstance(value, dict):
            return {k: assets(v) for k, v in value.items()}
        if isinstance(value, list):
            return [assets(v) for v in value]
        if isinstance(value, str) and value.startswith(("geo/", "extra_configs/")):
            # BETSE's pathname join requires relative paths, even for disabled SVG input.
            return os.path.relpath(c.SOURCE / "betse/data/yaml" / value, config_dir)
        return value

    return assets(conf)


def footprint(name, areas, density):
    if name == "uniform":
        return [density] * len(areas)
    if name == "one_face":
        return [density] + [0.0] * (len(areas) - 1)
    if name == "balanced_faces":
        return [density, -density * areas[0] / areas[1]] + [0.0] * (len(areas) - 2)
    c.require(name == "blocked", "Unknown footprint")
    return [0.0] * len(areas)


def betse_worker(registration, output):
    import betse
    import numpy as np
    from betse.science import sim_toolbox as stb
    from betse.science.enum.enumphase import SimPhaseKind
    from betse.science.parameters import Parameters
    from betse.science.phase.phasecls import SimPhase
    from betse.science.simrunner import SimRunner
    from ruamel.yaml import YAML

    package = Path(betse.__file__).resolve().parent
    installed = {f"betse/{p.relative_to(package)}": c.sha(p) for p in package.rglob("*.py")}
    expected = {
        k: v
        for k, v in registration["upstream"]["files_sha256"].items()
        if k.startswith("betse/") and k.endswith(".py")
    }
    c.require(installed == expected, "Installed BETSE differs from pinned source")
    c.require(package.is_relative_to(c.REFERENCE_PYTHON.parent.parent), "Wrong BETSE origin")
    protocol = registration["protocol"]
    yaml = YAML(typ="safe")
    # Avoid flow-style emission wrapping multiword mapping keys across lines.
    # BETSE's round-trip YAML reader rejects those wrapped keys.
    yaml.default_flow_style = False
    config_path = output / "native.yaml"
    with (c.SOURCE / "betse/data/yaml/sim_config.yaml").open() as handle:
        config = configuration(yaml.load(handle), protocol, output)
    with config_path.open("x") as handle:
        yaml.dump(config, handle)
    p = Parameters()
    p.load(str(config_path))
    np.random.seed(protocol["seed"])
    seeded = SimRunner(p).seed()
    cells = seeded.cells
    # Preserve actual initialized geometry before checking our requested model.
    # In v1.5.0 the nominal single-cell preset can produce seven compartments.
    preparation = {
        "schema": "cells.betse_native_preparation@1",
        "configuration_loaded": True,
        "native_seed_completed": True,
        "requested_single_cell": p.single_cell,
        "cell_count": len(cells.cell_i),
        "membrane_count": len(cells.mem_i),
        "cell_centres_m": cells.cell_centres.tolist(),
        "cell_volumes_m3": cells.cell_vol.tolist(),
        "cell_areas_m2": cells.cell_sa.tolist(),
        "membrane_owners": cells.mem_to_cells.tolist(),
        "membrane_areas_m2": cells.mem_sa.tolist(),
        "native_initial_inside_mM": seeded.sim.cc_cells.tolist(),
        "native_initial_outside_mM": seeded.sim.cc_env.tolist(),
        "species": [name for name, enabled in p.ions_dict.items() if enabled],
        "valence": seeded.sim.zs.tolist(),
        "molecules_enabled": p.molecules_enabled,
        "constants": {"F": p.F, "R": p.R},
        "environment": c.environment(),
        "installed_python_sha256": installed,
        "native_config_sha256": c.sha(config_path),
        "registration_sha256": c.sha(output / "registration.json"),
        "time_integration_run": False,
    }
    c.write(output / "native_preparation.json", preparation)
    require_one_cell(preparation)
    geometry = {
        "cell_count": len(cells.cell_i),
        "membrane_count": len(cells.mem_i),
        "cell_volume_m3": float(cells.cell_vol[0]),
        "cell_area_m2": float(cells.cell_sa[0]),
        "membrane_areas_m2": cells.mem_sa.tolist(),
        "membrane_owners": cells.mem_to_cells.tolist(),
        "diviterm_m": float(cells.diviterm[0]),
        "configured_bath_volume_m3": float(p.vol_env),
        "effective_bath_volume_m3": float(len(cells.mem_i) * p.vol_env),
        "capacitance_F": float(cells.cell_sa[0] * p.cm),
        "specific_capacitance_F_per_m2": p.cm,
        "grid_shape": list(cells.X.shape),
    }
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
        )
    }
    settings |= {"solver": p.solver_type.name, "temperature_K": p.T, "thickness_m": p.tm}
    profiles = {}

    def snapshot(sim):
        return {
            "inside_mM": sim.cc_cells[:, 0].tolist(),
            "outside_mM": sim.cc_env.tolist(),
            "voltage_V": sim.vm.tolist(),
            "charge_density_C_per_m3": sim.rho_cells.tolist(),
            "inward_current_A": sim.I_mem.tolist(),
            "boundary_voltage_V": sim.Phi_b.tolist(),
        }

    for profile, constants in protocol["profiles"].items():
        # An explicit parameter intervention in the matched profile, not a code patch.
        p.F, p.R = constants["F"], constants["R"]
        phase = SimPhase(kind=SimPhaseKind.INIT, p=p, cells=cells)
        sim = phase.sim
        sim.init_core(phase)
        sim.init_dynamics(phase)
        sim.update_V(cells, p)
        initial = snapshot(sim)
        initial_cells, initial_outside = sim.cc_cells.copy(), sim.cc_env.copy()

        def reset(transfer, sim=sim, initial_cells=initial_cells, initial_outside=initial_outside):
            sim.cc_cells = initial_cells.copy()
            sim.cc_env = initial_outside.copy()
            sim.cc_cells[:3, 0] += np.asarray(transfer) / (cells.cell_vol[0] / 1e-15)
            sim.cc_env[:3, :] -= np.asarray(transfer)[:, None] / (
                len(cells.mem_i) * p.vol_env / 1e-15
            )
            sim.cc_at_mem = sim.cc_cells[:, cells.mem_to_cells].copy()
            sim.fluxes_mem.fill(0)
            sim.fluxes_gj.fill(0)
            sim.vm.fill(0)
            sim.update_V(cells, p)

        probes = []
        for case in protocol["transfer_probes"]:
            reset(case["inward_amount_fmol"])
            before = snapshot(sim)
            for i in sim.movingIons:
                sim.fluxes_mem[i] = stb.electroflux(
                    sim.cc_env[i],
                    sim.cc_at_mem[i],
                    sim.Dm_cells[i],
                    np.ones(sim.mdl) * p.tm,
                    np.ones(sim.mdl) * sim.zs[i],
                    sim.vm,
                    sim.T,
                    p,
                )
            density = sim.fluxes_mem.copy()
            # Actual Simulator methods, but not its time-stepping loop.
            sim.update_all_concs(cells, p)
            sim.update_V(cells, p)
            probes.append(
                {
                    "id": case["id"],
                    "before": before,
                    "after": snapshot(sim),
                    "density_mol_per_m2_s": density.tolist(),
                }
            )
        footprints = []
        for name in protocol["footprint_probes"]:
            reset([0.0, 0.0, 0.0])
            before = snapshot(sim)
            flux = footprint(
                name, geometry["membrane_areas_m2"], protocol["prescribed_density_mol_per_m2_s"]
            )
            sim.fluxes_mem[0] = flux
            sim.update_all_concs(cells, p)
            sim.update_V(cells, p)
            footprints.append(
                {"id": name, "density_mol_per_m2_s": flux, "before": before, "after": snapshot(sim)}
            )
        # Inspect native scheduling only. No solver loop or write2storage is called.
        labels, sampled, _ = sim._plot_loop(phase)
        profiles[profile] = {
            "constants": {"F": p.F, "R": p.R},
            "species": [name for name, enabled in p.ions_dict.items() if enabled],
            "valence": sim.zs.tolist(),
            "permeability_m_per_s": (sim.Dm_cells / p.tm).tolist(),
            "dt_s": p.dt,
            "initial": initial,
            "probes": probes,
            "footprints": footprints,
            "clock": {
                "native_labels_s": labels.tolist(),
                "sampled_labels_s": sorted(sampled),
                "sampled_indices": [i for i, label in enumerate(labels) if label in sampled],
            },
        }
    c.require(
        not any(n == "cells" or n.startswith("cells.") for n in sys.modules),
        "BETSE worker imported Cells",
    )
    return {
        "engine": "native_betse_seed_init_and_prescribed_updates",
        "geometry": geometry,
        "settings": settings,
        "profiles": profiles,
        "environment": c.environment(),
        "installed_python_sha256": installed,
        "package_path": str(package),
        "native_config_sha256": c.sha(config_path),
        "trajectory_run": False,
    }


def require_one_cell(preparation):
    c.require(preparation["requested_single_cell"] is True, "Single-cell configuration required")
    c.require(
        preparation["cell_count"] == 1 and preparation["membrane_count"] >= 2,
        f"Requested one cell; native seed contains {preparation['cell_count']} cells",
    )
    c.require(preparation["molecules_enabled"] is False, "Biochemical network must be disabled")


def cells_definition(protocol, geometry):
    ids, valence = protocol["mobile_species"], protocol["expected_valence"][:3]
    inside, outside = protocol["inside_mM"][:3], protocol["outside_mM"][:3]
    vi, vo = geometry["cell_volume_m3"] / 1e-15, geometry["effective_bath_volume_m3"] / 1e-15
    ni, no = [v * vi for v in inside], [v * vo for v in outside]
    return {
        "schema_version": 1,
        "model": {
            "id": "finite_extracellular@1",
            "species": [{"id": k, "valence": z} for k, z in zip(ids, valence, strict=True)],
            "temperature_K": 310.15,
            "extracellular": {
                "id": "bath",
                "volume_pL": vo,
                "initial_amount_fmol": dict(zip(ids, no, strict=True)),
                "fixed_charge_equivalent_fmol": -math.fsum(
                    z * n for z, n in zip(valence, no, strict=True)
                ),
            },
            "cells": [
                {
                    "cell": {
                        "id": "cell",
                        "volume_pL": vi,
                        "initial_amount_fmol": dict(zip(ids, ni, strict=True)),
                        "fixed_charge_equivalent_fmol": -math.fsum(
                            z * n for z, n in zip(valence, ni, strict=True)
                        ),
                        "initial_voltage_V": 0.0,
                    },
                    "membrane": {
                        "id": "membrane",
                        "inside": "cell",
                        "outside": "bath",
                        "area_m2": geometry["cell_area_m2"],
                        "specific_capacitance_F_per_m2": geometry["specific_capacitance_F_per_m2"],
                        "passive": {
                            "law": "constant_field@1",
                            "permeability_m_per_s": dict(
                                zip(ids, protocol["permeability_m_per_s"][:3], strict=True)
                            ),
                        },
                        "pump": None,
                    },
                    "channel": None,
                }
            ],
            "junctions": [],
        },
        "experiment": {
            "end_time": protocol["dt_s"],
            "observation_times": [0, protocol["dt_s"]],
            "membrane_controls": [
                {
                    "membrane_id": "membrane",
                    "leak": [{"time": 0, "multipliers": dict.fromkeys(ids, 1)}],
                    "pump": [{"time": 0, "multiplier": 0}],
                }
            ],
            "channel_controls": [],
            "junction_controls": [],
        },
        "execution": {
            "dt": protocol["dt_s"],
            "jit": True,
            "capacity": 1,
            "membrane_capacity": 1,
            "channel_capacity": 1,
            "edge_capacity": 1,
            "extracellular_capacity": 1,
            "backend": "cpu",
            "precision": "float64",
            "solver": "rk4",
            "max_steps": 10,
            "max_trace_bytes": 1048576,
            "material_balance_atol_fmol": dict.fromkeys(ids, 1e-10),
        },
    }


def cells_worker(registration, output):
    import jax
    import jax.numpy as jnp
    import numpy as np

    from cells.core.schedule import PhysicalIonicGraphControl, control_values
    from cells.core.specs import parse_spec
    from cells.io import runtime_identity
    from cells.models import finite_extracellular as model

    c.require(jax.default_backend() == "cpu" and jax.config.x64_enabled, "Require CPU float64")
    c.require(not jax.config.jax_disable_jit, "JIT disabled")
    c.require(runtime_identity() == registration["cells_runtime"], "Cells runtime changed")
    native = c.read(output / "betse.json")
    definition = cells_definition(registration["protocol"], native["geometry"])
    c.write(output / "cells_definition.json", definition)
    spec = parse_spec(definition)
    state, layout = model.initial_values(spec)
    control = PhysicalIonicGraphControl(*(v[0] for v in control_values(spec, [0])))

    def evaluate(stage, parameters, held, xp):
        voltage = model.cell_voltage(stage.amount_increment, parameters, xp=xp)
        rate = model.rhs(stage, held, parameters, parameters.active, xp=xp)
        return voltage, rate.amount_increment, rate.extracellular_amount_increment

    compiled = jax.jit(lambda s, p, h: evaluate(s, p, h, jnp))
    results = {}
    for backend in c.CELLS_BACKENDS:
        rows = []
        for case in registration["protocol"]["transfer_probes"]:
            transfer = np.asarray(case["inward_amount_fmol"], dtype=np.float64)[:, None]
            stage = state._replace(
                amount_increment=transfer,
                extracellular_amount_increment=-transfer,
                leak_transferred=transfer,
            )
            if backend == "numpy":
                voltage, inside, outside = evaluate(stage, layout, control, np)
            else:
                args = jax.device_put((stage, layout, control))
                voltage, inside, outside = (
                    compiled(*args) if backend == "jax_jit" else evaluate(*args, jnp)
                )
            c.require(
                all(np.asarray(v).dtype == np.float64 for v in (voltage, inside, outside)),
                "Cells dtype differs",
            )
            rows.append(
                {
                    "id": case["id"],
                    "voltage_V": float(voltage[0]),
                    "inside_rate_fmol_per_s": np.asarray(inside[:, 0]).tolist(),
                    "outside_rate_fmol_per_s": np.asarray(outside[:, 0]).tolist(),
                }
            )
        results[backend] = rows
    return {
        "engine": "unchanged_cells_finite_extracellular_rhs",
        "definition": definition,
        "accepted_runtime": runtime_identity(),
        "results": results,
        "source_sha256": c.sha(model.__file__),
        "source_path": model.__file__,
        "device": "cpu",
        "x64_enabled": True,
        "jit_disabled": False,
        "trajectory_run": False,
    }


def check(registration, native, local):
    """Replay saved arithmetic and invariants without importing either simulator."""
    protocol = registration["protocol"]
    t, g = protocol["tolerances"], native["geometry"]
    rows = []

    def compare(label, actual, expected, unit):
        score = c.normalized_error(actual, expected, t[unit], t["relative"])
        rows.append(
            {
                "id": label,
                "actual": actual,
                "expected": expected,
                "normalized_error": score,
                "pass": score <= 1,
            }
        )

    c.require(
        native["engine"] == "native_betse_seed_init_and_prescribed_updates", "Wrong native engine"
    )
    c.require(local["engine"] == "unchanged_cells_finite_extracellular_rhs", "Wrong Cells engine")
    c.require(native["trajectory_run"] is local["trajectory_run"] is False, "Wrong scope")
    c.require(
        local["device"] == "cpu"
        and local["x64_enabled"] is True
        and local["jit_disabled"] is False,
        "Wrong Cells backend",
    )
    c.require(g["cell_count"] == 1 and g["membrane_count"] >= 2, "Wrong cell geometry")
    m, area = g["membrane_count"], g["cell_area_m2"]
    c.require(
        g["membrane_owners"] == [0] * m and len(g["membrane_areas_m2"]) == m,
        "Wrong membrane ownership",
    )
    c.require(
        all(
            math.isfinite(v) and v > 0
            for v in [
                area,
                g["cell_volume_m3"],
                g["configured_bath_volume_m3"],
                g["specific_capacitance_F_per_m2"],
                *g["membrane_areas_m2"],
            ]
        ),
        "Invalid geometry",
    )
    c.require(math.isclose(sum(g["membrane_areas_m2"]), area, rel_tol=1e-13), "Area sum differs")
    c.require(
        math.isclose(g["diviterm_m"], g["cell_volume_m3"] / area, rel_tol=1e-13),
        "Native volume/area closure differs",
    )
    c.require(
        g["effective_bath_volume_m3"] == m * g["configured_bath_volume_m3"],
        "Bath normalization differs",
    )
    c.require(
        g["capacitance_F"] == area * g["specific_capacitance_F_per_m2"], "Capacitance differs"
    )
    expected_settings = {
        "is_ecm": False,
        "cell_polarizability": 0.0,
        "cluster_open": True,
        "alpha_NaK": 0.0,
        "alpha_Ca": 0.0,
        "Ca_dyn": False,
        "molecules_enabled": False,
        "grn_enabled": False,
        "fluid_flow": False,
        "deformation": False,
        "deform_osmo": False,
        "dynamic_noise": False,
        "channel_noise_level": 0.0,
        "v_sensitive_gj": False,
        "solver": "FULL",
        "temperature_K": 310.15,
        "thickness_m": protocol["thickness_m"],
    }
    c.require(native["settings"] == expected_settings, "Native model switches differ")
    c.require(local["definition"] == cells_definition(protocol, g), "Cells mapping differs")
    c.require(set(native["profiles"]) == set(protocol["profiles"]), "Profiles differ")
    c.require(set(local["results"]) == set(c.CELLS_BACKENDS), "Cells backend coverage differs")
    vi, vo = g["cell_volume_m3"] / 1e-15, g["effective_bath_volume_m3"] / 1e-15
    ids = [case["id"] for case in protocol["transfer_probes"]]
    for values in local["results"].values():
        c.require([v["id"] for v in values] == ids, "Cells probe coverage differs")
    max_voltage_difference = 0.0
    configured_volume_residuals = []
    for name, profile in native["profiles"].items():
        constants = protocol["profiles"][name]
        c.require(
            profile["constants"] == constants and profile["dt_s"] == protocol["dt_s"],
            "Native constants/timestep differ",
        )
        c.require(
            profile["species"] == protocol["expected_species"]
            and profile["valence"] == protocol["expected_valence"],
            "Native species differ",
        )
        c.require([p["id"] for p in profile["probes"]] == ids, "Native probe coverage differs")
        c.require(
            [p["id"] for p in profile["footprints"]] == protocol["footprint_probes"],
            "Footprint coverage differs",
        )
        for i, expected in enumerate(protocol["permeability_m_per_s"]):
            c.require(len(profile["permeability_m_per_s"][i]) == m, "Permeability shape differs")
            c.require(
                all(
                    math.isclose(v, expected, rel_tol=2e-15, abs_tol=0)
                    for v in profile["permeability_m_per_s"][i]
                ),
                "Permeability differs",
            )

        def snapshot(label, saved, transfer, amounts_after=None, flux=None, constants=constants):
            c.require(len(saved["inside_mM"]) == len(saved["outside_mM"]) == 6, "Ion shape differs")
            for i in range(len(protocol["expected_valence"])):
                delta = transfer[i] if i < 3 else 0.0
                if amounts_after is not None:
                    delta += amounts_after[i]
                ci = protocol["inside_mM"][i] + delta / vi
                co = protocol["outside_mM"][i] - delta / vo
                compare(f"{label}/inside/{i}", saved["inside_mM"][i], ci, "concentration_mM")
                c.require(len(saved["outside_mM"][i]) == m, "Outside shape differs")
                for j, value in enumerate(saved["outside_mM"][i]):
                    compare(f"{label}/outside/{i}/{j}", value, co, "concentration_mM")
            q = (
                constants["F"]
                * 1e-15
                * math.fsum(
                    z * (transfer[i] + (amounts_after[i] if amounts_after is not None else 0.0))
                    for i, z in enumerate(protocol["expected_valence"][:3])
                )
            )
            voltage = q / g["capacitance_F"]
            c.require(
                len(saved["voltage_V"]) == len(saved["inward_current_A"]) == m,
                "Voltage/current shape differs",
            )
            for j, actual in enumerate(saved["voltage_V"]):
                compare(f"{label}/voltage/{j}", actual, voltage, "voltage_V")
                expected_current = (
                    0.0
                    if flux is None
                    else constants["F"]
                    * math.fsum(z * flux[i][j] for i, z in enumerate(protocol["expected_valence"]))
                    * g["membrane_areas_m2"][j]
                )
                compare(
                    f"{label}/current/{j}",
                    saved["inward_current_A"][j],
                    expected_current,
                    "current_A",
                )
            c.require(
                all(v == 0.0 for v in saved["boundary_voltage_V"]), "Boundary voltage not zero"
            )
            compare(
                f"{label}/rho",
                saved["charge_density_C_per_m3"][0],
                q / g["cell_volume_m3"],
                "charge_density_C_per_m3",
            )
            return voltage

        snapshot(f"{name}/initial", profile["initial"], [0.0] * 3)
        for k, (case, probe) in enumerate(
            zip(protocol["transfer_probes"], profile["probes"], strict=True)
        ):
            label = f"{name}/{case['id']}"
            transfer = case["inward_amount_fmol"]
            expected_voltage = snapshot(label + "/before", probe["before"], transfer)
            density = probe["density_mol_per_m2_s"]
            c.require(len(density) == 6 and all(len(v) == m for v in density), "Flux shape differs")
            rates = [
                math.fsum(f * a for f, a in zip(row, g["membrane_areas_m2"], strict=True)) / 1e-15
                for row in density
            ]
            for i, rate in enumerate(rates):
                if i >= 3:
                    c.require(all(v == 0.0 for v in density[i]), "Auxiliary ion transported")
                oracle_case = {
                    "inside_mM": probe["before"]["inside_mM"][i],
                    "outside_mM": probe["before"]["outside_mM"][i][0],
                    "valence": protocol["expected_valence"][i],
                    "voltage_V": probe["before"]["voltage_V"][0],
                    "temperature_K": 310.15,
                    "area_m2": area,
                    "permeability_m_per_s": protocol["permeability_m_per_s"][i],
                }
                compare(
                    f"{label}/flux/{i}", rate, c.oracle(oracle_case, constants), "flux_fmol_per_s"
                )
            increments = [v * protocol["dt_s"] for v in rates]
            snapshot(label + "/after", probe["after"], transfer, increments, density)
            for i in range(6):
                di = (probe["after"]["inside_mM"][i] - probe["before"]["inside_mM"][i]) * vi
                do = (probe["after"]["outside_mM"][i][0] - probe["before"]["outside_mM"][i][0]) * vo
                compare(f"{label}/inside_transfer/{i}", di, increments[i], "amount_fmol")
                compare(f"{label}/outside_transfer/{i}", do, -increments[i], "amount_fmol")
                compare(f"{label}/conservation/{i}", di + do, 0.0, "amount_fmol")
            if name == "matched_constants":
                for backend, values in local["results"].items():
                    row = values[k]
                    compare(
                        f"{label}/{backend}/voltage",
                        row["voltage_V"],
                        expected_voltage,
                        "voltage_V",
                    )
                    max_voltage_difference = max(
                        max_voltage_difference,
                        abs(row["voltage_V"] - probe["before"]["voltage_V"][0]),
                    )
                    c.require(
                        len(row["inside_rate_fmol_per_s"])
                        == len(row["outside_rate_fmol_per_s"])
                        == 3,
                        "Cells rate shape differs",
                    )
                    for i in range(3):
                        compare(
                            f"{label}/{backend}/rate/{i}",
                            row["inside_rate_fmol_per_s"][i],
                            rates[i],
                            "flux_fmol_per_s",
                        )
                        c.require(
                            row["outside_rate_fmol_per_s"][i] == -row["inside_rate_fmol_per_s"][i],
                            "Cells ownership not exactly opposite",
                        )
        for probe in profile["footprints"]:
            label = f"{name}/footprint/{probe['id']}"
            expected_flux = footprint(
                probe["id"], g["membrane_areas_m2"], protocol["prescribed_density_mol_per_m2_s"]
            )
            c.require(probe["density_mol_per_m2_s"] == expected_flux, "Footprint flux differs")
            transfer = (
                math.fsum(f * a for f, a in zip(expected_flux, g["membrane_areas_m2"], strict=True))
                * protocol["dt_s"]
                / 1e-15
            )
            snapshot(label + "/before", probe["before"], [0.0] * 3)
            # Native current smoothing changes the individual face current; total is conserved.
            after = probe["after"]
            for i in range(6):
                expected = transfer if i == 0 else 0.0
                di = (after["inside_mM"][i] - probe["before"]["inside_mM"][i]) * vi
                do = (after["outside_mM"][i][0] - probe["before"]["outside_mM"][i][0]) * vo
                compare(f"{label}/inside/{i}", di, expected, "amount_fmol")
                compare(f"{label}/outside/{i}", do, -expected, "amount_fmol")
                compare(f"{label}/conservation/{i}", di + do, 0, "amount_fmol")
                if i == 0 and probe["id"] == "uniform":
                    configured_volume_residuals.append(di + do / m)
            compare(
                f"{label}/total_current",
                sum(after["inward_current_A"]),
                transfer / protocol["dt_s"] * constants["F"] * 1e-15,
                "current_A",
            )
        clock = profile["clock"]
        n = len(clock["native_labels_s"])
        c.require(
            n == 10 and clock["sampled_indices"] == list(range(1, n)),
            "Native clock coverage differs",
        )
        for i, value in enumerate(clock["native_labels_s"]):
            c.require(
                math.isclose(value, i * n * protocol["dt_s"] / (n - 1), abs_tol=1e-18),
                "Native time label mapping differs",
            )
        c.require(
            clock["sampled_labels_s"] == [clock["native_labels_s"][i] for i in range(1, n)],
            "Native sampling labels differ",
        )
    c.require(
        all(abs(v) > 100 * t["amount_fmol"] for v in configured_volume_residuals),
        "Bath-volume mismatch witness is not distinguishable",
    )
    return {
        "status": "pass" if all(r["pass"] for r in rows) else "failed",
        "comparison_count": len(rows),
        "maximum_normalized_error": max(r["normalized_error"] for r in rows),
        "maximum_matched_voltage_difference_V": max_voltage_difference,
        "configured_bath_volume_mass_residual_fmol": configured_volume_residuals,
        "effective_bath_volume_multiplier": m,
        "comparisons": rows,
        "trajectory_run": False,
        "biological_validation": False,
        "production_changed": False,
    }


def provenance(registration, native, local):
    expected = {
        k: v
        for k, v in registration["upstream"]["files_sha256"].items()
        if k.startswith("betse/") and k.endswith(".py")
    }
    c.require(native["installed_python_sha256"] == expected, "Native installed sources differ")
    c.require(
        native["environment"]["packages"] == c.locked_reference_packages(),
        "Native dependencies differ",
    )
    c.require(
        native["environment"]["python"] == "3.13.5"
        and Path(native["environment"]["executable"]) == c.REFERENCE_PYTHON,
        "Native interpreter differs",
    )
    c.require(
        Path(native["package_path"]).is_relative_to(c.REFERENCE_PYTHON.parent.parent),
        "Native path differs",
    )
    c.require(local["accepted_runtime"] == registration["cells_runtime"], "Cells runtime differs")
    source = c.ROOT / "src/cells/models/finite_extracellular.py"
    c.require(
        Path(local["source_path"]) == source and local["source_sha256"] == c.sha(source),
        "Cells source differs",
    )


def capture(output):
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    try:
        authenticate()
        protocol = c.read(PROTOCOL)
        registration = {
            "schema": "cells.betse_alignment_registration@1",
            "protocol": protocol,
            "registered_utc": datetime.now(UTC).isoformat(),
            "upstream": c.inspect_source(),
            "source_sha256": source_hashes(),
            "preservation_sha256": c.sha(PRESERVATION),
            "cells_runtime": c.read(c.PRESERVATION)["runtime"],
        }
        c.write(output / "registration.json", registration)
        with zipfile.ZipFile(
            output / "adapter_sources.zip", "x", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for name in FILES:
                archive.write(c.HERE / name, arcname=name)
        env = os.environ | {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(output / "matplotlib-cache"),
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "JAX_PLATFORMS": "cpu",
            "JAX_ENABLE_X64": "true",
        }
        env.pop("PYTHONPATH", None)
        for kind, python in (("betse", c.REFERENCE_PYTHON), ("cells", c.CELLS_PYTHON)):
            remaining = protocol["total_timeout_seconds"] - (time.monotonic() - started)
            c.require(remaining > 0, "Capture time limit exceeded")
            with (
                (output / f"{kind}.stdout.log").open("x") as out,
                (output / f"{kind}.stderr.log").open("x") as err,
            ):
                subprocess.run(
                    [
                        "taskset",
                        "-c",
                        "0-3",
                        str(python),
                        "-B",
                        str(Path(__file__).resolve()),
                        "worker",
                        kind,
                        str(output),
                    ],
                    cwd=c.ROOT,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=err,
                    check=True,
                    timeout=min(remaining, protocol["worker_timeout_seconds"]),
                )
        native, local = c.read(output / "betse.json"), c.read(output / "cells.json")
        provenance(registration, native, local)
        result = check(registration, native, local)
        c.write(output / "comparison.json", result)
        c.require(result["status"] == "pass", "Alignment checks failed; retain results")
        c.require(c.inspect_source() == registration["upstream"], "Upstream changed")
        c.require(source_hashes() == registration["source_sha256"], "Adapter changed")
        authenticate()
        payloads = {str(p.relative_to(output)): c.sha(p) for p in output.rglob("*") if p.is_file()}
        c.require(
            time.monotonic() - started <= protocol["total_timeout_seconds"],
            "Capture time limit exceeded",
        )
        c.require(
            sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
            < protocol["max_artifact_bytes"] - 65536,
            "Capture storage limit exceeded",
        )
        receipt = {
            "schema": "cells.betse_alignment_capture@1",
            "status": "pass",
            "seconds": time.monotonic() - started,
            "files_sha256": payloads,
            "finished_utc": datetime.now(UTC).isoformat(),
            "trajectory_run": False,
        }
        c.write(output / "verification.json", receipt)
        print(json.dumps({k: v for k, v in receipt.items() if k != "files_sha256"}))
    except BaseException:
        c.write(
            output / "failure.json",
            {
                "status": "failed_not_qualified",
                "seconds": time.monotonic() - started,
                "traceback": traceback.format_exc(),
            },
        )
        raise


def audit(output):
    receipt = c.read(output / "verification.json")
    c.require(
        receipt["status"] == "pass" and not (output / "failure.json").exists(), "Incomplete capture"
    )
    names = {str(p.relative_to(output)) for p in output.rglob("*") if p.is_file()} - {
        "verification.json"
    }
    c.require(names == set(receipt["files_sha256"]), "Payload coverage differs")
    for name, digest in receipt["files_sha256"].items():
        c.require(c.sha(output / name) == digest, f"Payload changed: {name}")
    r = c.read(output / "registration.json")
    c.require(
        r["source_sha256"] == source_hashes() and r["protocol"] == c.read(PROTOCOL),
        "Use captured source context",
    )
    c.require(r["preservation_sha256"] == c.sha(PRESERVATION), "Preservation changed")
    with zipfile.ZipFile(output / "adapter_sources.zip") as archive:
        c.require(
            len(archive.namelist()) == len(FILES) and set(archive.namelist()) == set(FILES),
            "Capsule coverage differs",
        )
        for name, digest in r["source_sha256"].items():
            c.require(
                hashlib.sha256(archive.read(name)).hexdigest() == digest, "Capsule bytes differ"
            )
    native, local = c.read(output / "betse.json"), c.read(output / "cells.json")
    c.require(
        native["registration_sha256"]
        == local["registration_sha256"]
        == c.sha(output / "registration.json"),
        "Worker registration differs",
    )
    c.require(
        native["native_config_sha256"] == c.sha(output / "native.yaml"), "Native config differs"
    )
    c.require(
        local["definition"] == c.read(output / "cells_definition.json"), "Cells definition differs"
    )
    provenance(r, native, local)
    result = check(r, native, local)
    c.require(
        result["status"] == "pass" and result == c.read(output / "comparison.json"),
        "Arithmetic replay differs",
    )
    c.require(c.inspect_source() == r["upstream"], "Pinned source changed")
    authenticate()
    c.require(
        0 <= receipt["seconds"] <= r["protocol"]["total_timeout_seconds"], "Time budget exceeded"
    )
    c.require(
        sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
        <= r["protocol"]["max_artifact_bytes"],
        "Storage budget exceeded",
    )
    return {
        "status": "pass",
        "verification_sha256": c.sha(output / "verification.json"),
        "payloads": len(names),
        "comparisons": result["comparison_count"],
        "upstream_calls": 0,
        "production_calls": 0,
        "trajectory_calls": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("preserve")
    sub.add_parser("capture").add_argument("output", type=Path)
    auditor = sub.add_parser("audit")
    auditor.add_argument("output", type=Path)
    auditor.add_argument("--receipt", type=Path, required=True)
    child = sub.add_parser("worker")
    child.add_argument("kind", choices=("betse", "cells"))
    child.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.action == "preserve":
        preserve()
    elif args.action == "capture":
        capture(args.output.resolve())
    elif args.action == "audit":
        result = audit(args.output.resolve())
        c.write(args.receipt, result)
        print(json.dumps(result))
    else:
        target = args.output.resolve()
        registration = c.read(target / "registration.json")
        c.require(registration["source_sha256"] == source_hashes(), "Worker source differs")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = (betse_worker if args.kind == "betse" else cells_worker)(registration, target)
        result["warnings"] = [
            {"category": w.category.__name__, "message": str(w.message)} for w in caught
        ]
        result["registration_sha256"] = c.sha(target / "registration.json")
        c.write(target / f"{args.kind}.json", result)
