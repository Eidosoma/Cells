"""Explicit seven-cell native reference; no production changes or time integration."""

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

import alignment as a
import contact as c
import geometry_probe as geometry

PROTOCOL = c.HERE / "cluster_protocol.json"
GEOMETRY_PROBE = c.ROOT / "runs/ref-003b1-2026-09-12/geometry-01"
FILES = (
    "cluster_alignment.py",
    "cluster_check.py",
    "cluster_protocol.json",
    "test_cluster.py",
    "alignment.py",
    "alignment_protocol.json",
    "contact.py",
    "geometry_probe.py",
    "single_cell.svg",
)
GEOMETRY_FIELDS = (
    "cell_count",
    "membrane_count",
    "cell_centres_m",
    "cell_volumes_m3",
    "cell_areas_m2",
    "membrane_owners",
    "membrane_areas_m2",
)


def hashes():
    return {name: c.sha(c.HERE / name) for name in FILES}


def transfers(case, protocol):
    result = [[0.0] * protocol["cell_count"] for _ in range(3)]
    seen = set()
    for species, cell, amount in case["transfers"]:
        c.require(
            species in ("Na", "K", "Cl")
            and type(cell) is int
            and 0 <= cell < protocol["cell_count"]
            and math.isfinite(amount),
            "Invalid transfer",
        )
        c.require((species, cell) not in seen, "Repeated transfer owner")
        seen.add((species, cell))
        result[("Na", "K", "Cl").index(species)][cell] = amount
    c.require(case["leak_multiplier"] in (0.0, 1.0, 2.0), "Unknown probe multiplier")
    return result


def definition(base, protocol, native_geometry):
    """Compose all native cells and one explicitly finite bath through existing schema."""
    g, pieces = native_geometry, []
    for i in range(protocol["cell_count"]):
        local = {
            "cell_volume_m3": g["cell_volumes_m3"][i],
            "cell_area_m2": g["cell_areas_m2"][i],
            "effective_bath_volume_m3": g["effective_bath_volume_m3"],
            "specific_capacitance_F_per_m2": g["specific_capacitance_F_per_m2"],
        }
        spec = a.cells_definition(base, local)
        piece = spec["model"]["cells"][0]
        piece["cell"]["id"] = f"cell_{i}"
        piece["membrane"]["id"] = f"membrane_{i}"
        piece["membrane"]["inside"] = f"cell_{i}"
        pieces.append(piece)
    spec["model"]["cells"] = pieces
    schedule = spec["experiment"]["membrane_controls"][0]
    spec["experiment"]["membrane_controls"] = [
        copy.deepcopy(schedule) | {"membrane_id": piece["membrane"]["id"]} for piece in pieces
    ]
    # Retain inactive slots to exercise the actual production ownership masks.
    spec["execution"] |= {
        "capacity": protocol["cell_count"] + 1,
        "membrane_capacity": protocol["cell_count"] + 2,
        "extracellular_capacity": 2,
    }
    return spec


def probe_definition(mapped, case, protocol, base, g):
    """Each prescribed state is a new preparation, not a fabricated trajectory history."""
    result = copy.deepcopy(mapped)
    delta = transfers(case, protocol)
    ids, zs = base["mobile_species"], base["expected_valence"][:3]
    for i, piece in enumerate(result["model"]["cells"]):
        for s, species in enumerate(ids):
            piece["cell"]["initial_amount_fmol"][species] += delta[s][i]
        cap = g["cell_areas_m2"][i] * g["specific_capacitance_F_per_m2"]
        piece["cell"]["initial_voltage_V"] = (
            base["profiles"]["matched_constants"]["F"]
            * 1e-15
            * math.fsum(z * delta[s][i] for s, z in enumerate(zs))
            / cap
        )
    for s, species in enumerate(ids):
        result["model"]["extracellular"]["initial_amount_fmol"][species] -= math.fsum(delta[s])
    for control in result["experiment"]["membrane_controls"]:
        # Availability is a fraction in the production contract. A larger maximum
        # permeability is a parameter change, not an out-of-range availability.
        control["leak"][0]["multipliers"] = dict.fromkeys(ids, min(case["leak_multiplier"], 1.0))
    if case["leak_multiplier"] > 1.0:
        for piece in result["model"]["cells"]:
            values = piece["membrane"]["passive"]["permeability_m_per_s"]
            for species in ids:
                values[species] *= case["leak_multiplier"]
    return result


def native_worker(registration, output):
    import betse
    import numpy as np
    from betse.science import sim_toolbox as stb
    from betse.science.enum.enumphase import SimPhaseKind
    from betse.science.parameters import Parameters
    from betse.science.phase.phasecls import SimPhase
    from betse.science.simrunner import SimRunner
    from ruamel.yaml import YAML

    base, protocol = registration["base_protocol"], registration["protocol"]
    package = Path(betse.__file__).resolve().parent
    c.require(package.is_relative_to(c.REFERENCE_PYTHON.parent.parent), "Wrong BETSE import")
    installed = {
        f"betse/{path.relative_to(package)}": c.sha(path) for path in package.rglob("*.py")
    }
    c.require(
        installed
        == {
            k: v
            for k, v in registration["upstream"]["files_sha256"].items()
            if k.startswith("betse/") and k.endswith(".py")
        },
        "Installed source differs",
    )
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    with (c.SOURCE / "betse/data/yaml/sim_config.yaml").open() as handle:
        config = a.configuration(yaml.load(handle), base, output)
    with (output / "native.yaml").open("x") as handle:
        yaml.dump(config, handle)
    p = Parameters()
    p.load(str(output / "native.yaml"))
    np.random.seed(base["seed"])
    seed = SimRunner(p).seed()
    cells = seed.cells
    actual_geometry = {
        "cell_count": len(cells.cell_i),
        "membrane_count": len(cells.mem_i),
        "cell_centres_m": cells.cell_centres.tolist(),
        "cell_volumes_m3": cells.cell_vol.tolist(),
        "cell_areas_m2": cells.cell_sa.tolist(),
        "membrane_owners": cells.mem_to_cells.tolist(),
        "membrane_areas_m2": cells.mem_sa.tolist(),
    }
    c.require(actual_geometry == registration["expected_geometry"], "Native geometry changed")
    g = actual_geometry | {
        "diviterm_m": cells.diviterm.tolist(),
        "configured_bath_volume_m3": p.vol_env,
        "effective_bath_volume_m3": len(cells.mem_i) * p.vol_env,
        "specific_capacitance_F_per_m2": p.cm,
        "grid_shape": list(cells.X.shape),
    }
    names = (
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
    )
    settings = {name: getattr(p, name) for name in names} | {
        "solver": p.solver_type.name,
        "temperature_K": p.T,
    }
    profiles = {}
    vi, vo = cells.cell_vol / 1e-15, g["effective_bath_volume_m3"] / 1e-15

    def snapshot(sim):
        return {
            "inside_mM": sim.cc_cells.tolist(),
            "outside_mM": sim.cc_env.tolist(),
            "voltage_V": sim.vm.tolist(),
            "rho_C_per_m3": sim.rho_cells.tolist(),
            "inward_current_A": sim.I_mem.tolist(),
            "boundary_voltage_V": sim.Phi_b.tolist(),
        }

    for name, constants in base["profiles"].items():
        p.F, p.R = constants["F"], constants["R"]
        phase = SimPhase(kind=SimPhaseKind.INIT, cells=cells, p=p)
        sim = phase.sim
        sim.init_core(phase)
        sim.init_dynamics(phase)
        sim.update_V(cells, p)
        initial = snapshot(sim)
        ci0, co0 = sim.cc_cells.copy(), sim.cc_env.copy()

        def reset(delta, sim=sim, ci0=ci0, co0=co0):
            sim.cc_cells, sim.cc_env = ci0.copy(), co0.copy()
            sim.cc_cells[:3] += delta / vi[None, :]
            sim.cc_env[:3] -= delta.sum(axis=1)[:, None] / vo
            sim.cc_at_mem = sim.cc_cells[:, cells.mem_to_cells].copy()
            sim.fluxes_mem.fill(0)
            sim.fluxes_gj.fill(0)
            sim.vm.fill(0)
            sim.update_V(cells, p)

        rows = []
        for case in protocol["cases"]:
            reset(np.asarray(transfers(case, protocol)))
            before = snapshot(sim)
            for i in sim.movingIons:
                sim.fluxes_mem[i] = stb.electroflux(
                    sim.cc_env[i],
                    sim.cc_at_mem[i],
                    sim.Dm_cells[i] * case["leak_multiplier"],
                    np.ones(sim.mdl) * p.tm,
                    np.ones(sim.mdl) * sim.zs[i],
                    sim.vm,
                    sim.T,
                    p,
                )
                sim.update_gj(cells, p, 0.0, i)
                sim.update_intra(cells, p, i)
            density = sim.fluxes_mem.copy()
            junction = sim.fluxes_gj.copy()
            sim.update_all_concs(cells, p)
            sim.update_V(cells, p)
            rows.append(
                {
                    "id": case["id"],
                    "before": before,
                    "after": snapshot(sim),
                    "density_mol_per_m2_s": density.tolist(),
                    "junction_density_mol_per_m2_s": junction.tolist(),
                }
            )
        footprints = []
        for kind in protocol["footprints"]:
            reset(np.zeros((3, protocol["cell_count"])))
            before = snapshot(sim)
            sim.fluxes_mem[0] = a.footprint(
                kind, g["membrane_areas_m2"], base["prescribed_density_mol_per_m2_s"]
            )
            density = sim.fluxes_mem.copy()
            sim.update_all_concs(cells, p)
            sim.update_V(cells, p)
            footprints.append(
                {
                    "id": kind,
                    "before": before,
                    "after": snapshot(sim),
                    "density_mol_per_m2_s": density.tolist(),
                }
            )
        labels, sampled, _ = sim._plot_loop(phase)
        profiles[name] = {
            "constants": {"F": p.F, "R": p.R},
            "dt_s": p.dt,
            "initial": initial,
            "species": [key for key, value in p.ions_dict.items() if value],
            "valence": sim.zs.tolist(),
            "permeability_m_per_s": (sim.Dm_cells / p.tm).tolist(),
            "cases": rows,
            "footprints": footprints,
            "clock": {
                "labels_s": labels.tolist(),
                "sampled_indices": [i for i, label in enumerate(labels) if label in sampled],
            },
        }
    c.require(
        not any(name == "cells" or name.startswith("cells.") for name in sys.modules),
        "Native worker imported Cells",
    )
    return {
        "engine": "native_betse_seven_cell_prescribed_updates",
        "geometry": g,
        "settings": settings,
        "profiles": profiles,
        "environment": c.environment(),
        "installed_python_sha256": installed,
        "package_path": str(package),
        "native_config_sha256": c.sha(output / "native.yaml"),
        "trajectory_run": False,
    }


def cells_worker(registration, output):
    import jax
    import jax.numpy as jnp
    import numpy as np

    from cells.core.schedule import PhysicalIonicGraphControl, control_values
    from cells.core.specs import parse_spec
    from cells.io import runtime_identity
    from cells.models import finite_extracellular as model

    c.require(
        jax.default_backend() == "cpu"
        and jax.config.x64_enabled
        and not jax.config.jax_disable_jit,
        "Require CPU float64 JIT",
    )
    c.require(runtime_identity() == registration["cells_runtime"], "Cells runtime changed")
    protocol = registration["protocol"]
    n = protocol["cell_count"]
    native = c.read(output / "betse.json")
    mapped = definition(registration["base_protocol"], protocol, native["geometry"])
    c.write(output / "cells_definition.json", mapped)
    _, baseline_layout = model.initial_values(parse_spec(mapped))
    definitions = {
        case["id"]: probe_definition(
            mapped, case, protocol, registration["base_protocol"], native["geometry"]
        )
        for case in protocol["cases"]
    }
    c.write(output / "cells_probe_definitions.json", definitions)

    def evaluate(state, layout, control, baseline_layout, delta, xp):
        v = model.cell_voltage(state.amount_increment, layout, xp=xp)
        increment_v = model.cell_voltage(delta, baseline_layout, xp=xp)
        rate = model.rhs(state, control, layout, layout.active, xp=xp)
        valid = model.domain_valid(state, layout, layout.active, xp=xp)
        return v, rate.amount_increment, rate.extracellular_amount_increment, valid, increment_v

    compiled = jax.jit(
        lambda state, layout, control, baseline_layout, delta: evaluate(
            state, layout, control, baseline_layout, delta, jnp
        )
    )
    results = {}
    for backend in c.CELLS_BACKENDS:
        rows = []
        for case in protocol["cases"]:
            spec = parse_spec(definitions[case["id"]])
            state, layout = model.initial_values(spec)
            delta = np.zeros_like(state.amount_increment)
            delta[:, :n] = np.asarray(transfers(case, protocol))
            control = PhysicalIonicGraphControl(*(v[0] for v in control_values(spec, [0])))
            model.check_values(state, spec)
            if backend == "numpy":
                values = evaluate(state, layout, control, baseline_layout, delta, np)
            else:
                args = jax.device_put((state, layout, control, baseline_layout, delta))
                values = compiled(*args) if backend == "jax_jit" else evaluate(*args, jnp)
            voltage, inside, outside, valid, increment_v = (np.asarray(v) for v in values)
            c.require(
                all(v.dtype == np.float64 for v in (voltage, inside, outside)) and bool(valid),
                "Cells dtype/domain differs",
            )
            c.require(
                np.all(inside[:, n:] == 0)
                and np.all(outside[:, 1:] == 0)
                and np.all(voltage[n:] == 0),
                "Inactive slots changed",
            )
            rows.append(
                {
                    "id": case["id"],
                    "voltage_V": voltage[:n].tolist(),
                    "increment_voltage_V": increment_v[:n].tolist(),
                    "inside_rate_fmol_per_s": inside[:, :n].tolist(),
                    "outside_rate_fmol_per_s": outside[:, 0].tolist(),
                    "valid_domain": bool(valid),
                    "inactive_slots_zero": True,
                }
            )
        results[backend] = rows
    c.require(
        not any(name == "betse" or name.startswith("betse.") for name in sys.modules),
        "Cells worker imported BETSE",
    )
    return {
        "engine": "unchanged_cells_finite_extracellular_rhs",
        "definition": mapped,
        "probe_definitions": definitions,
        "results": results,
        "accepted_runtime": runtime_identity(),
        "source_path": model.__file__,
        "source_sha256": c.sha(model.__file__),
        "device": "cpu",
        "x64_enabled": True,
        "jit_disabled": False,
        "trajectory_run": False,
    }


def capture(output):
    from cluster_check import check

    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    try:
        geometry.authenticate()
        geometry_audit = geometry.audit(GEOMETRY_PROBE)
        protocol = c.read(PROTOCOL)
        previous_geometry = c.read(c.ROOT / protocol["geometry_source"])
        c.require(
            previous_geometry["cell_count"] == protocol["cell_count"] == 7
            and previous_geometry["membrane_count"] == protocol["membrane_face_count"] == 30,
            "Wrong registered cluster",
        )
        registration = {
            "schema": "cells.betse_cluster_alignment_registration@1",
            "registered_utc": datetime.now(UTC).isoformat(),
            "protocol": protocol,
            "base_protocol": c.read(a.PROTOCOL),
            "upstream": c.inspect_source(),
            "sources": hashes(),
            "cells_runtime": c.read(c.PRESERVATION)["runtime"],
            "expected_geometry": {key: previous_geometry[key] for key in GEOMETRY_FIELDS},
            "geometry_source_sha256": c.sha(c.ROOT / protocol["geometry_source"]),
            "geometry_probe": geometry_audit,
        }
        c.write(output / "registration.json", registration)
        with zipfile.ZipFile(
            output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED
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
            c.require(remaining > 0, "Session time limit exceeded")
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
        a.provenance(registration, native, local)
        comparison = check(registration, native, local)
        c.write(output / "comparison.json", comparison)
        c.require(
            comparison["status"] == "pass", "Cluster alignment not qualified; retain comparison"
        )
        c.require(
            hashes() == registration["sources"] and c.inspect_source() == registration["upstream"],
            "Source changed",
        )
        geometry.authenticate()
        c.require(
            time.monotonic() - started < protocol["total_timeout_seconds"],
            "Session time limit exceeded",
        )
        c.require(
            sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
            < protocol["max_artifact_bytes"] - 65536,
            "Artifact budget exceeded",
        )
        receipt = {
            "status": "pass",
            "schema": "cells.betse_cluster_alignment_capture@1",
            "seconds": time.monotonic() - started,
            "trajectory_run": False,
            "finished_utc": datetime.now(UTC).isoformat(),
            "files_sha256": {
                str(p.relative_to(output)): c.sha(p) for p in output.rglob("*") if p.is_file()
            },
        }
        c.write(output / "verification.json", receipt)
        print(
            json.dumps(
                {
                    "status": "pass",
                    "seconds": receipt["seconds"],
                    "comparisons": comparison["comparison_count"],
                }
            )
        )
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
    from cluster_check import check

    receipt = c.read(output / "verification.json")
    c.require(
        receipt["status"] == "pass" and not (output / "failure.json").exists(), "Incomplete capture"
    )
    actual = {str(p.relative_to(output)) for p in output.rglob("*") if p.is_file()} - {
        "verification.json"
    }
    c.require(actual == set(receipt["files_sha256"]), "Payload coverage differs")
    for name, digest in receipt["files_sha256"].items():
        c.require(c.sha(output / name) == digest, f"Payload changed: {name}")
    registered = c.read(output / "registration.json")
    c.require(
        registered["sources"] == hashes() and registered["protocol"] == c.read(PROTOCOL),
        "Use captured source context",
    )
    c.require(registered["base_protocol"] == c.read(a.PROTOCOL), "Base inputs differ")
    with zipfile.ZipFile(output / "sources.zip") as archive:
        c.require(
            len(archive.namelist()) == len(FILES) and set(archive.namelist()) == set(FILES),
            "Capsule coverage differs",
        )
        for name, digest in registered["sources"].items():
            c.require(
                hashlib.sha256(archive.read(name)).hexdigest() == digest, "Capsule bytes differ"
            )
    native, local = c.read(output / "betse.json"), c.read(output / "cells.json")
    c.require(
        native["registration_sha256"]
        == local["registration_sha256"]
        == c.sha(output / "registration.json"),
        "Worker inputs differ",
    )
    c.require(
        native["native_config_sha256"] == c.sha(output / "native.yaml"),
        "Native configuration differs",
    )
    c.require(
        local["definition"] == c.read(output / "cells_definition.json"), "Cells definition differs"
    )
    c.require(
        local["probe_definitions"] == c.read(output / "cells_probe_definitions.json"),
        "Cells prescribed preparations differ",
    )
    a.provenance(registered, native, local)
    result = check(registered, native, local)
    c.require(
        result["status"] == "pass" and result == c.read(output / "comparison.json"),
        "Numerical replay differs",
    )
    c.require(
        geometry.audit(GEOMETRY_PROBE) == registered["geometry_probe"],
        "Geometry feasibility evidence differs",
    )
    c.require(c.inspect_source() == registered["upstream"], "Native source changed")
    c.require(
        registered["geometry_source_sha256"]
        == c.sha(c.ROOT / registered["protocol"]["geometry_source"]),
        "Geometry source changed",
    )
    c.require(
        0 <= receipt["seconds"] <= registered["protocol"]["total_timeout_seconds"],
        "Time budget exceeded",
    )
    c.require(
        sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
        <= registered["protocol"]["max_artifact_bytes"],
        "Storage budget exceeded",
    )
    return {
        "status": "pass",
        "cells": 7,
        "native_faces": 30,
        "comparisons": result["comparison_count"],
        "verification_sha256": c.sha(output / "verification.json"),
        "payloads": len(actual),
        "upstream_calls": 0,
        "production_calls": 0,
        "trajectory_calls": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("capture").add_argument("output", type=Path)
    auditor = sub.add_parser("audit")
    auditor.add_argument("output", type=Path)
    auditor.add_argument("--receipt", type=Path, required=True)
    worker = sub.add_parser("worker")
    worker.add_argument("kind", choices=("betse", "cells"))
    worker.add_argument("output", type=Path)
    args = parser.parse_args()
    target = args.output.resolve()
    if args.action == "capture":
        capture(target)
    elif args.action == "audit":
        result = audit(target)
        c.write(args.receipt, result)
        print(json.dumps(result))
    else:
        registration = c.read(target / "registration.json")
        c.require(registration["sources"] == hashes(), "Worker source differs")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = (native_worker if args.kind == "betse" else cells_worker)(registration, target)
        result["warnings"] = [
            {"category": warning.category.__name__, "message": str(warning.message)}
            for warning in caught
        ]
        result["registration_sha256"] = c.sha(target / "registration.json")
        c.write(target / f"{args.kind}.json", result)
