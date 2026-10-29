"""Authenticated native grid/barrier/bath methods and recorded actual helpers."""

import argparse
import ast
import copy
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
import traceback
import warnings
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from scipy.ndimage import gaussian_filter

from validation.transport.betse_environment_transport_fixtures import cases, limitations, refinement

PROTOCOL = Path(__file__).with_name("betse_environment_transport_protocol.json")


def serial(value):
    if isinstance(value, np.ndarray):
        return serial(value.tolist())
    if isinstance(value, np.generic):
        return serial(value.item())
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return str(value)
    return value


def write(path, value):
    path.write_text(json.dumps(serial(value), indent=2, allow_nan=False) + "\n")


def executable(node):
    result = copy.deepcopy(node)
    for value in ast.walk(result):
        if isinstance(value, ast.FunctionDef):
            value.decorator_list = []
            value.returns = None
            for arg in (*value.args.posonlyargs, *value.args.args, *value.args.kwonlyargs):
                arg.annotation = None
    return result


def namespace(trees, manifest):
    bodies = []
    for relative, classname, newname, names in (
        ("betse/science/sim.py", "Simulator", "CapturedSimulator", ("initDenv", "update_ecm")),
        (
            "betse/science/tissue/tishandler.py",
            "TissueHandler",
            "CapturedHandler",
            ("_finalize_events_global", "_fire_events_global"),
        ),
    ):
        cls = next(
            v for v in trees[relative].body if isinstance(v, ast.ClassDef) and v.name == classname
        )
        selected = [
            executable(v) for v in cls.body if isinstance(v, ast.FunctionDef) and v.name in names
        ]
        assert len(selected) == len(names)
        bodies.append(
            ast.ClassDef(name=newname, bases=[], keywords=[], decorator_list=[], body=selected)
        )
        for node in selected:
            manifest.setdefault("executed_bodies", {})[classname + "." + node.name] = dict(
                source=relative, first_line=node.lineno, last_line=node.end_lineno
            )
    for relative, names in (
        ("betse/science/math/finitediff.py", ("gradient", "diff", "divergence", "integrator")),
        (
            "betse/science/sim_toolbox.py",
            (
                "nernst_planck_flux",
                "molecule_mover",
                "update_Co",
                "div_env",
                "no_negs",
                "electroflux",
            ),
        ),
        ("betse/science/math/toolbox.py", ("pulse",)),
    ):
        selected = [
            executable(v)
            for v in trees[relative].body
            if isinstance(v, ast.FunctionDef) and v.name in names
        ]
        assert len(selected) == len(names)
        bodies.extend(selected)
        for node in selected:
            manifest.setdefault("executed_bodies", {})[node.name] = dict(
                source=relative, first_line=node.lineno, last_line=node.end_lineno
            )
    # Exact coefficient-write statements; cut geometry/selection is external.
    handler = next(
        v
        for v in trees["betse/science/tissue/tishandler.py"].body
        if isinstance(v, ast.ClassDef) and v.name == "TissueHandler"
    )
    assignments = {}
    for value in ast.walk(handler):
        if isinstance(value, ast.Assign) and value.lineno in (1248, 1251, 1254):
            assignments[value.lineno] = value
    ion_write = next(v for v in ast.walk(handler) if isinstance(v, ast.If) and v.lineno == 1257)
    assert set(assignments) == {1248, 1251, 1254}
    wrapper = ast.parse("def wound(sim,cells,p,ecmtarg):\n    pass\n").body[0]
    wrapper.body = [copy.deepcopy(assignments[k]) for k in sorted(assignments)] + [
        copy.deepcopy(ion_write)
    ]
    bodies.append(wrapper)
    manifest["wound_fragment"] = dict(
        first_line=1248, last_line=ion_write.end_lineno, cut_executed=False
    )
    ns = dict(np=np, gaussian_filter=gaussian_filter, BetseSimUnstableException=ValueError)
    exec(
        compile(
            ast.fix_missing_locations(
                ast.Module(body=[executable(v) for v in bodies], type_ignores=[])
            ),
            str(PROTOCOL),
            "exec",
        ),
        ns,
    )
    trace = []

    def recorded(name, argument_names):
        def call(*args, **kwargs):
            result = ns[name](*args, **kwargs)
            trace.append(
                dict(
                    name=name,
                    inputs={key: serial(v) for key, v in zip(argument_names, args, strict=False)},
                    kwargs=serial(kwargs),
                    result=serial(result),
                )
            )
            return result

        return call

    ns["fd"] = SimpleNamespace(
        gradient=recorded("gradient", ("concentration", "dx", "dy")),
        divergence=recorded("divergence", ("minus_flux_x", "minus_flux_y", "dx", "dy")),
        integrator=recorded("integrator", ("concentration",)),
    )
    ns["stb"] = SimpleNamespace()
    # molecule_mover calls the helper through its original module global name.
    actual_flux = ns["nernst_planck_flux"]

    def molecule_flux(*args, **kwargs):
        result = actual_flux(*args, **kwargs)
        trace.append(
            dict(
                name="nernst_planck_flux",
                concentration=serial(args[0]),
                diffusion_m2_s=serial(args[7]),
                valence=serial(args[8]),
                temperature_K=serial(args[9]),
                extra_mobility=serial(kwargs.get("mu", 0)),
                result=serial(result),
            )
        )
        return result

    ns["nernst_planck_flux"] = molecule_flux

    # The ionic recorder delegates to the saved actual function as well.
    def ion_flux(*args, **kwargs):
        return molecule_flux(*args, **kwargs)

    ns["stb"].nernst_planck_flux = ion_flux
    ns["tb"] = SimpleNamespace(pulse=ns["pulse"])
    return ns, trace


def make_objects(raw, ns):
    ny, nx = raw["shape"]
    size = ny * nx
    species = raw["species_ids"]
    cells = SimpleNamespace(
        X=np.zeros((ny, nx)),
        xypts=np.zeros((size, 2)),
        envInds_inClust=np.asarray(raw["regions"]["cluster"], int),
        all_bound_mem_inds=np.asarray(raw["regions"]["boundary_membrane"], int),
        interior_bound_mem_inds=np.asarray(raw["regions"]["neighbor_membrane"], int),
        ecm_inds_bound_cell=np.asarray(raw["regions"]["boundary_cell"], int),
        delta=raw["delta_m"],
    )
    sim = ns["CapturedSimulator"]()
    sim.edl = size
    sim.D_free = np.asarray(raw["D_free_m2_s"])
    sim.Dtj_rel = np.asarray(raw["relative_TJ"])
    sim.D_env = np.zeros((len(species), size))
    sim.TJ_modulator = None
    for i, ion in enumerate(species):
        setattr(sim, "i" + ion, i)
    if raw.get("missing_sodium"):
        del sim.iNa
    if raw.get("missing_counterion"):
        del sim.iM
    sim.T = raw["temperature_K"]
    sim.zs = np.asarray(raw["valence"])
    sim.cc_env = np.asarray(raw["concentration_mol_m3"], float)
    sim.c_env_bound = np.asarray(raw["initial_boundary_mol_m3"], float)
    p = SimpleNamespace(
        is_ecm=raw["is_ecm"],
        D_adh=raw["adherens_factor"],
        D_tj=raw["tight_factor"],
        er=raw["er"],
        dt=raw["dt_s"],
        sharpness=raw["sharpness"],
        fluid_flow=raw["fluid_flow"],
        q=raw["q_C"],
        kb=raw["kb_J_K"],
        T=raw["temperature_K"],
        ions_dict=dict(Cl=int(raw["enabled_Cl"])),
        env_concs=dict(zip(species, raw["base_bath_mol_m3"], strict=True)),
        global_options={
            key: 0 for key in ("K_env", "Cl_env", "Na_env", "T_change", "gj_block", "NaKATP_block")
        },
        fast_update_ecm=False,
        cell_height=raw["height_m"],
        vol_env=1e-15,
        cluster_open=True,
    )
    if raw["legacy_bath_fields"]:
        p.conc_env_k = p.env_concs["K"]
        p.conc_env_cl = p.env_concs["Cl"]
        p.conc_env_na = p.env_concs["Na"]
    for event in raw["events"]:
        p.global_options[event["kind"]] = [
            event[k] for k in ("on_s", "off_s", "change_s", "amplitude")
        ]
    electric = np.asarray(raw["electric_V_m"])
    velocity = np.asarray(raw["velocity_m_s"])
    sim.E_env_x, sim.E_env_y = electric if raw.get("flat_electric") else electric.reshape(2, ny, nx)
    sim.u_env_x, sim.u_env_y = velocity.reshape(2, ny, nx)
    sim.fluxes_env_x = np.zeros((len(species), size))
    sim.fluxes_env_y = np.zeros_like(sim.fluxes_env_x)
    # Normalized zero-membrane/GJ exchange inputs isolate the full molecule
    # function's extracellular branch; all update_Co/div_env arithmetic is real.
    sim.mdl = 4
    sim.vm = np.zeros(4)
    cells.mem_i = np.arange(4)
    cells.mem_to_cells = np.array([0, 1, 0, 1])
    cells.mem_sa = np.array([1, 2, 3, 4]) * 1e-12
    cells.cell_vol = np.array([3, 4]) * 1e-16
    cells.M_sum_mems = np.array([[1, 0, 1, 0], [0, 1, 0, 1]], float)
    cells.map_mem2ecm = np.array([0, min(1, size - 1), min(2, size - 1), min(3, size - 1)])
    cells.M_divmap_mem2ecm = np.zeros((size, 4))
    cells.M_divmap_mem2ecm[cells.map_mem2ecm, np.arange(4)] = cells.mem_sa
    cells.memSa_per_envSquare = cells.M_divmap_mem2ecm.sum(axis=1)
    cells.ecm_vol = raw["height_m"] * raw["delta_m"] ** 2
    return sim, cells, p


def capture_case(raw, output, ns, trace, limited=False):
    path = output / (raw["name"] + ".json")
    record = dict(name=raw["name"], input=raw, status="prepared", stage="initializing")
    write(path, record)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            sim, cells, p = make_objects(raw, ns)
            record["stage"] = "initDenv"
            sim.initDenv(cells, p)
            record["coefficients"] = serial(
                dict(
                    D_env=sim.D_env,
                    weight=sim.D_env_weight,
                    weight_base=sim.D_env_weight_base,
                    TJ_modulator=sim.TJ_modulator,
                    TJ_targets=sim.TJ_targets,
                    Chi=sim.Chi,
                )
            )
            if raw["wound"]:
                record["stage"] = "wound_coefficients"
                p.wound_TJ = raw["wound"]["factor"]
                ns["wound"](sim, cells, p, np.asarray(raw["wound"]["targets"], int))
                record["wound_coefficients"] = serial(
                    dict(D_env=sim.D_env, weight=sim.D_env_weight)
                )
            if raw["is_ecm"]:
                sim.TJ_modulator = (
                    None if raw["tj_modulator"] is None else np.asarray(raw["tj_modulator"], float)
                )
            handler = ns["CapturedHandler"]()
            phase = SimpleNamespace(sim=sim, cells=cells, p=p)
            handler._finalize_events_global(phase)
            generic = np.asarray(raw["molecule"]["initial_mol_m3"], float)
            records = []
            for t in raw["times_s"]:
                record["stage"] = "global_bath"
                handler._fire_events_global(phase, t)
                before = sim.cc_env.copy()
                before_generic = generic.copy()
                trace.clear()
                record["stage"] = "transport"
                if raw["kind"] == "ion":
                    for i in range(len(raw["species_ids"])):
                        sim.update_ecm(cells, p, t, i)
                elif raw["kind"] == "molecule":
                    config = raw["molecule"]
                    result = ns["molecule_mover"](
                        sim,
                        generic,
                        np.array([2.0, 3.0]),
                        cells,
                        p,
                        z=config["valence"],
                        Dm=0.0,
                        Do=config["diffusion_m2_s"],
                        Dgj=0.0,
                        Ftj=config["relative_TJ"],
                        c_bound=config["bath_mol_m3"],
                        ignoreGJ=True,
                        ignoreTJ=config["ignore_TJ"],
                        time_dilation_factor=config["time_dilation"],
                        mu_mem=config["extra_mobility_m2_V_s"],
                        name="source-environment-probe",
                    )
                    generic = result[0]
                    record["last_molecule_flux_shape"] = [
                        list(np.shape(result[-2])),
                        list(np.shape(result[-1])),
                    ]
                records.append(
                    dict(
                        time_s=t,
                        boundary=sim.c_env_bound.copy(),
                        before=before,
                        after=sim.cc_env.copy(),
                        molecule_before=before_generic,
                        molecule_after=generic.copy(),
                        flux_x=sim.fluxes_env_x.copy(),
                        flux_y=sim.fluxes_env_y.copy(),
                        trace=copy.deepcopy(trace),
                    )
                )
            record["records"] = serial(records)
            if raw.get("clip_probe"):
                record["stage"] = "explicit_clipping_diagnostic"
                unclipped = sim.cc_env.copy()
                clipped = ns["no_negs"](unclipped.copy())
                record["clip_probe"] = serial(
                    dict(unclipped=unclipped, clipped=clipped, applied_by_update_ecm=False)
                )
            record["status"] = "captured_limitation" if limited else "passed"
        except Exception as error:
            record.update(
                status="captured_failure" if limited else "unexpected_failure",
                failure_type=type(error).__name__,
                failure=str(error),
                traceback=traceback.format_exc(),
            )
            if "sim" in locals():
                record["partial_after_failure"] = serial(
                    dict(concentration=sim.cc_env, boundary=sim.c_env_bound)
                )
    record["warnings"] = [
        dict(category=w.category.__name__, message=str(w.message)) for w in caught
    ]
    write(path, record)
    if not limited:
        assert record["status"] == "passed", (raw["name"], record.get("failure"))
    return dict(name=raw["name"], status=record["status"], path=str(path))


def capture(output):
    output.mkdir(parents=True, exist_ok=False)
    source = json.loads(PROTOCOL.read_text())["native_source"]
    checkout = Path(source["checkout"])
    installed = Path(source["installed_package"]).parent
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    assert revision == source["revision"]
    manifest = dict(
        status="capturing",
        version=source["version"],
        revision=revision,
        files={},
        records=[],
        full_simulator=False,
        versions={v: importlib.metadata.version(v) for v in ("numpy", "scipy")},
    )
    trees = {}
    write(output / "source-manifest.json", manifest)
    for relative, sha in source["source_sha256"].items():
        content = (installed / relative).read_bytes()
        target = output / "upstream" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(installed / relative, target)
        assert (
            content == (checkout / relative).read_bytes()
            and hashlib.sha256(content).hexdigest() == sha
        )
        manifest["files"][relative] = dict(sha256=sha, checkout_match=True)
        if relative.endswith(".py"):
            trees[relative] = ast.parse(content.decode())
    ns, trace = namespace(trees, manifest)
    for raw, limited in (
        [(v, False) for v in cases()]
        + [(v, True) for v in limitations()]
        + [(v, False) for v in refinement()]
    ):
        manifest["records"].append(capture_case(raw, output, ns, trace, limited))
        write(output / "source-manifest.json", manifest)
    manifest.update(
        status="passed",
        component_cases=len(cases()),
        limitations=len(limitations()),
        refinement_cases=len(refinement()),
        production_cells_imported=any(k == "cells" or k.startswith("cells.") for k in sys.modules),
        jax_imported=any(k == "jax" or k.startswith("jax.") for k in sys.modules),
        geometry_or_cut_executed=False,
        full_tissue_or_membrane_physics=False,
    )
    assert not manifest["production_cells_imported"] and not manifest["jax_imported"]
    write(output / "source-manifest.json", manifest)
    print(
        json.dumps(
            dict(
                status="passed",
                cases=len(cases()),
                limitations=len(limitations()),
                refinement=len(refinement()),
            )
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    capture(parser.parse_args().output)
