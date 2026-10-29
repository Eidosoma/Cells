"""Authenticated deformation, pressure, DEC/HH, reset and display captures."""

import argparse
import ast
import copy
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
import warnings
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from scipy.interpolate import SmoothBivariateSpline
from scipy.spatial import cKDTree

from validation.mechanics.betse_deformation_fixtures import base, cases, display_cases, limitations
from validation.mechanics.betse_deformation_reference import display_expected, evaluate

PROTOCOL = Path(__file__).with_name("betse_deformation_protocol.json")


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
    if isinstance(result, ast.FunctionDef):
        result.decorator_list, result.returns = [], None
        for arg in (*result.args.posonlyargs, *result.args.args, *result.args.kwonlyargs):
            arg.annotation = None
    return result


def capture(output):
    output.mkdir(parents=True, exist_ok=False)
    contract = json.loads(PROTOCOL.read_text())
    source = contract["native_source"]
    checkout, installed = Path(source["checkout"]), Path(source["installed_package"]).parent
    manifest = dict(
        status="capturing",
        files={},
        executed_bodies={},
        full_simulator=False,
        scipy_version=importlib.metadata.version("scipy"),
        numpy_version=np.__version__,
    )
    write(output / "source-manifest.json", manifest)
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    assert revision == source["revision"]
    manifest["revision"] = revision
    trees = {}
    for relative, expected in source["source_sha256"].items():
        content = (installed / relative).read_bytes()
        dest = output / "upstream" / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(installed / relative, dest)
        manifest["files"][relative] = dict(
            sha256=hashlib.sha256(content).hexdigest(),
            checkout_match=content == (checkout / relative).read_bytes(),
        )
        write(output / "source-manifest.json", manifest)
        assert (
            manifest["files"][relative]["sha256"] == expected
            and manifest["files"][relative]["checkout_match"]
        )
        if relative.endswith(".py"):
            trees[relative] = ast.parse(content.decode())
    metadata = trees["betse/metadata.py"]
    manifest["version"] = next(
        ast.literal_eval(n.value)
        for n in metadata.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "VERSION" for t in n.targets)
    )
    assert manifest["version"] == source["version"]
    namespace = dict(
        np=np,
        cKDTree=cKDTree,
        copy=copy,
        logs=SimpleNamespace(log_info=lambda *_: None, log_debug=lambda *_: None),
        BetseSimUnstableException=ValueError,
        BetseSimConfException=ValueError,
    )
    bodies = []
    for relative, names in (
        (
            "betse/science/physics/deform.py",
            ("getDeformation", "timeDeform", "implement_deform_timestep"),
        ),
        ("betse/science/physics/pressures.py", ("osmotic_P",)),
        ("betse/science/sim_toolbox.py", ("check_v",)),
    ):
        selected = [
            n for n in trees[relative].body if isinstance(n, ast.FunctionDef) and n.name in names
        ]
        assert {n.name for n in selected} == set(names)
        bodies.extend(executable(n) for n in selected)
        for n in selected:
            manifest["executed_bodies"][n.name] = dict(
                source=relative, first_line=n.lineno, last_line=n.end_lineno
            )
    cls = next(
        n
        for n in trees["betse/science/cells.py"].body
        if isinstance(n, ast.ClassDef) and n.name == "Cells"
    )
    selected = [
        n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in source["cell_methods"]
    ]
    assert {n.name for n in selected} == set(source["cell_methods"])
    bodies.append(
        ast.ClassDef(
            name="CapturedCells",
            bases=[],
            keywords=[],
            body=[executable(n) for n in selected],
            decorator_list=[],
        )
    )
    for n in selected:
        manifest["executed_bodies"]["Cells." + n.name] = dict(
            source="betse/science/cells.py", first_line=n.lineno, last_line=n.end_lineno
        )
    params_tree = trees["betse/science/parameters.py"]
    attrs = {
        "deformation",
        "galvanotropism",
        "td_deform",
        "fixed_cluster_bound",
        "youngMod",
        "mu_tissue",
        "deform_osmo",
        "aquaporins",
        "poi",
        "lame_mu",
        "lame_lamb",
    }
    assignments = [
        n
        for n in ast.walk(params_tree)
        if isinstance(n, ast.Assign)
        and any(
            isinstance(t, ast.Attribute)
            and isinstance(t.value, ast.Name)
            and t.value.id == "self"
            and t.attr in attrs
            for t in n.targets
        )
    ]
    assert len(assignments) == len(attrs)
    assignments.sort(key=lambda n: n.lineno)
    synthetic = ast.parse("def read_mechanical_parameters(self):\n    pass\n").body[0]
    synthetic.body = copy.deepcopy(assignments)
    bodies.append(synthetic)
    manifest["parameter_fragments"] = [
        dict(first_line=n.lineno, last_line=n.end_lineno) for n in assignments
    ]
    fragments = {}
    sim_tree = trees["betse/science/sim.py"]
    candidates = [
        n
        for n in ast.walk(sim_tree)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "p.deformation"
    ]
    for name, signature, contains in (
        ("init_deformation", "self, cells, p", "self.d_cells_x = np.zeros"),
        ("clear_deformation_storage", "self, cells, p", "self.dx_time = []"),
        ("sample_display", "self, cells, t, p", "implement_deform_timestep(self, self.cellso"),
    ):
        node = next(n for n in candidates if contains in ast.unparse(n))
        function = ast.parse("def " + name + "(" + signature + "):\n    pass\n").body[0]
        function.body = [copy.deepcopy(node)]
        bodies.append(function)
        fragments[name] = dict(
            source="betse/science/sim.py", first_line=node.lineno, last_line=node.end_lineno
        )
    tissue = trees["betse/science/tissue/tishandler.py"]
    node = next(
        n
        for n in ast.walk(tissue)
        if isinstance(n, ast.If)
        and ast.unparse(n.test) == "p.fluid_flow or p.deformation"
        and "sim.cellso = copy.deepcopy(cells)" in ast.unparse(n)
    )
    function = ast.parse("def reset_deformation(self, sim, cells, p):\n    pass\n").body[0]
    function.body = [copy.deepcopy(node)]
    bodies.append(function)
    fragments[function.name] = dict(
        source="betse/science/tissue/tishandler.py",
        first_line=node.lineno,
        last_line=node.end_lineno,
    )
    manifest["caller_fragments"] = fragments
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=bodies, type_ignores=[])),
            "authenticated-native-mechanics",
            "exec",
        ),
        namespace,
    )
    namespace["stb"] = SimpleNamespace(check_v=namespace["check_v"])
    spline_calls = []

    def spline(*args, **kwargs):
        result = SmoothBivariateSpline(*args, **kwargs)
        knots = result.get_knots()
        spline_calls.append(
            dict(
                knots=[v.copy() for v in knots],
                residual=result.get_residual(),
                samples=len(args[0]),
            )
        )
        return result

    namespace["SmoothBivariateSpline"] = spline

    def make_parameters(raw):
        conf = {
            "variable settings": {
                "deformation": {
                    "turn on": True,
                    "galvanotropism": raw.get("galvanotropism_m2_V", 1e-9),
                    "fixed cluster boundary": raw.get("fixed_boundary", True),
                    "young modulus": raw.get("young_modulus_Pa", 1000.0),
                    "viscous damping": raw.get("viscous_damping_native", 0.01),
                },
                "pressures": {
                    "include osmotic pressure": raw.get("include_osmotic", False),
                    "membrane water conductivity": raw.get("aquaporin_fraction", 0.01),
                },
            }
        }
        p = SimpleNamespace(
            _conf=conf,
            dt=raw.get("dt_s", 1e-6),
            cell_radius=raw.get("cell_radius_m", 1e-5),
            fluid_flow=False,
            cell_height=raw["layout"]["cell_height_m"],
            R=raw.get("gas_constant_J_mol_K", 8.314),
            mu_water=raw.get("water_viscosity_Pa_s", 1e-3),
            tm=raw.get("membrane_thickness_m", 7.5e-9),
            rho=raw.get("density_kg_m3", 1050.0),
            is_ecm=raw.get("is_ecm", True),
            molecules_enabled=True,
            grn_enabled=True,
        )
        namespace["read_mechanical_parameters"](p)
        assert p.td_deform is False
        return p

    def make_cells(mesh, p, graph=True):
        cells = namespace["CapturedCells"]()
        n = len(mesh["centers_m"])
        nn = np.asarray(mesh["neighbors"], int)
        normal = np.asarray(mesh["force_directions"], float)
        tangent = np.asarray(mesh["curl_directions"], float)
        cells.cell_nn_i, cells.nn_len = nn, np.asarray(mesh["lengths_m"])
        cells.nn_tx, cells.nn_ty = normal.T
        cells.cell_nn_tx, cells.cell_nn_ty = tangent.T
        cells.M_sum_mems = np.asarray(mesh["sum_membranes"], float)
        cells.num_mems = cells.M_sum_mems.sum(axis=1)
        cells.mem_vects_flat = np.column_stack(
            (np.zeros((len(nn), 2)), normal, np.zeros((len(nn), 2)))
        )
        cells.mem_sa, cells.mem_vol = (
            np.asarray(mesh["membrane_area_m2"]),
            np.asarray(mesh["membrane_volume_m3"]),
        )
        cells.cell_sa, cells.cell_vol = (
            np.asarray(mesh["cell_area_m2"]),
            np.asarray(mesh["cell_volume_m3"]),
        )
        cells.cell_centres, cells.mem_verts = (
            np.asarray(mesh["centers_m"]),
            np.asarray(mesh["vertices_m"]),
        )
        cells.cell_verts = np.asarray(mesh["vertices_m"]).reshape((n, 4, 2))
        cells.cell_to_mems = np.arange(4 * n).reshape(n, 4)
        cells.mem_to_cells = np.repeat(np.arange(n), 4)
        cells.ecm_verts_unique, cells.ecm_verts = cells.mem_verts.copy(), cells.cell_verts.copy()
        cells.mesh = SimpleNamespace(
            vor_edge_len=np.asarray(mesh["dual_edge_m"]),
            tri_edge_len=np.asarray(mesh["primal_edge_m"]),
            delta_tri_0=np.asarray(mesh["incidence"], float),
            delta_tri_0_inv=np.asarray(mesh["incidence_inverse"], float),
            vor_sa=np.asarray(mesh["dual_area_m2"]),
        )
        cells.lapGJ, cells.lapGJinv = None, None
        if graph:
            cells.graphLaplacian(p)
        return cells

    # Exact initialization/storage-reset/cut-reset semantics on supplied layout.
    raw = base()
    p, mesh = make_parameters(raw), raw["layout"]
    cells = make_cells(mesh, p)
    sim = SimpleNamespace(
        cdl=len(mesh["centers_m"]),
        mdl=4 * len(mesh["centers_m"]),
        d_cells_x=np.ones(len(mesh["centers_m"])),
        d_cells_y=np.ones(len(mesh["centers_m"])),
        dx_time=[np.ones(len(mesh["centers_m"]))],
        dy_time=[np.ones(len(mesh["centers_m"]))],
    )
    namespace["init_deformation"](sim, cells, p)
    initialized = dict(
        x=sim.d_cells_x.copy(), y=sim.d_cells_y.copy(), separate_copy=sim.cellso is not cells
    )
    namespace["clear_deformation_storage"](sim, cells, p)
    sim.d_cells_x[:] = 3.0
    sim.dx_time.append(np.ones(sim.cdl))
    namespace["reset_deformation"](SimpleNamespace(), sim, cells, p)
    write(
        output / "initialization-reset.json",
        dict(
            initialized=initialized,
            after_cut_reset_x=sim.d_cells_x,
            history_count_after_cut_reset=len(sim.dx_time),
            separate_copy=sim.cellso is not cells,
            td_deform=p.td_deform,
            interpretation=(
                "Initialization zeros displacement; storage clear resets histories; "
                "cut-reset fragment recreates display copy without resetting "
                "existing displacement/history"
            ),
        ),
    )
    records = []
    all_rows = (
        [(row, False, False) for row in cases()]
        + [(row, False, True) for row in display_cases()]
        + [(row, True, row.get("display_only", False)) for row in limitations()]
    )
    for raw, limitation, display_mode in all_rows:
        path = output / (raw["name"] + ".json")
        record = dict(
            status="prepared",
            input=raw,
            limitation=limitation,
            display_only=display_mode,
            stage="prepare",
            full_simulator=False,
        )
        write(path, record)
        p, mesh = make_parameters(raw), raw["layout"]
        cells = make_cells(mesh, p, graph=not display_mode)
        n = len(mesh["centers_m"])
        sim = SimpleNamespace(cdl=n, mdl=4 * n, edl=5, T=raw.get("temperature_K", 310.0))
        try:
            if display_mode:
                sim.d_cells_x, sim.d_cells_y = np.asarray(raw["displacement_m"])
                namespace["init_deformation"](sim, cells, p)
                # Source initialization zeros the field; supplied sampled field
                # is the explicit input to the later sampled display call.
                sim.d_cells_x, sim.d_cells_y = np.asarray(raw["displacement_m"])
                namespace["clear_deformation_storage"](sim, cells, p)
                record["display_calls"] = []
                for call in range(raw["calls"]):
                    spline_calls.clear()
                    record["stage"] = "sample_display"
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter("always")
                        namespace["sample_display"](sim, cells, float(call), p)
                    entry = dict(
                        vertices_m=sim.cellso.cell_verts.reshape(-1, 2),
                        cell_centres_m=sim.cellso.cell_centres,
                        splines=copy.deepcopy(spline_calls),
                        warnings=[str(w.message) for w in caught],
                    )
                    record["display_calls"].append(entry)
                record["physical_centres_unchanged"] = np.array_equal(
                    cells.cell_centres, np.asarray(mesh["centers_m"])
                )
                record["original_membrane_vertices_unchanged"] = np.array_equal(
                    sim.cellso.mem_verts, np.asarray(mesh["vertices_m"])
                )
                record["volumes_unchanged"] = np.array_equal(
                    sim.cellso.cell_vol, np.asarray(mesh["cell_volume_m3"])
                )
                record["history_counts"] = dict(
                    vertices=len(sim.cell_verts_time),
                    centres=len(sim.cell_centres_time),
                    displacement=len(sim.dx_cell_time),
                )
                write(path, record)
                if not limitation:
                    expected = display_expected(raw)
                    record["independent_reference"] = expected
                    for actual, oracle in zip(record["display_calls"], expected, strict=True):
                        for field in ("vertices_m", "cell_centres_m"):
                            np.testing.assert_allclose(
                                np.asarray(actual[field], float),
                                oracle[field],
                                rtol=8e-12,
                                atol=3e-17,
                            )
                        assert all(
                            len(v) == 10
                            for spline_call in actual["splines"]
                            for v in spline_call["knots"]
                        )
            else:
                sim.P_cells, sim.PP = np.asarray(raw["pressure_Pa"]), np.asarray(raw["PP_native"])
                sim.E_cell_x, sim.E_cell_y = np.asarray(raw["electric_field_V_m"])
                sim.J_cell_x, sim.J_cell_y = np.asarray(raw["current_density_A_m2"])
                sim.rho_cells, sim.sigma = (
                    np.asarray(raw["charge_density_C_m3"]),
                    np.asarray(raw["conductivity_S_m"]),
                )
                sim.d_cells_x, sim.d_cells_y = np.asarray(raw["displacement_m"])
                sim.dx_time, sim.dy_time = (
                    [np.asarray(v).copy()] for v in raw["previous_displacement_m"]
                )
                if raw.get("empty_history"):
                    sim.dx_time, sim.dy_time = [], []
                if raw.get("missing_PP"):
                    del sim.PP
                record["native_operators"] = dict(
                    laplacian=cells.lapGJ, laplacian_inverse=cells.lapGJinv
                )
                record["source_td_deform"] = p.td_deform
                record["source_shear_Pa"] = p.lame_mu
                if raw["compute_osmotic"]:
                    record["stage"] = "osmotic_P"
                    mapping = np.asarray(raw["cell_to_environment"])
                    cells.map_cell2ecm = mapping
                    mem_env = mapping[cells.mem_to_cells]
                    sim.cc_cells = np.asarray(raw["primary_cell_mM"])
                    sim.cc_env = np.asarray(raw["primary_env_mM"])
                    if not p.is_ecm:
                        sim.cc_env = sim.cc_env[:, mem_env]
                    for target, ck, ek in (
                        ("molecules", "molecule_cell_mM", "molecule_env_mM"),
                        ("grn", "grn_cell_mM", "grn_env_mM"),
                    ):
                        molecules = {
                            str(i): SimpleNamespace(
                                c_cells=np.asarray(c),
                                c_env=np.asarray(e) if p.is_ecm else np.asarray(e)[mem_env],
                            )
                            for i, (c, e) in enumerate(zip(raw[ck], raw[ek], strict=True))
                        }
                        setattr(
                            sim, target, SimpleNamespace(core=SimpleNamespace(molecules=molecules))
                        )
                    namespace["osmotic_P"](sim, cells, p)
                    record["osmotic"] = dict(
                        cell_osmotic_pressure_Pa=sim.osmo_P_cell,
                        environment_osmotic_pressure_Pa=sim.osmo_P_env,
                        delta_pressure_Pa=sim.osmo_P_delta,
                        water_velocity_m_s=sim.u_osmo,
                        divergence_per_s=sim.div_u_osmo,
                        PP_native=sim.PP,
                    )
                    record["geometry_volumes_unchanged"] = np.array_equal(
                        cells.cell_vol, np.asarray(mesh["cell_volume_m3"])
                    )
                record["stage"] = "timeDeform" if raw["mode"] == "time" else "getDeformation"
                with np.errstate(all="ignore"):
                    namespace[record["stage"]](sim, cells, raw["clock_s"], p)
                record["result"] = dict(
                    displacement_m=[sim.d_cells_x, sim.d_cells_y],
                    pressure_gradient_native=[sim.gPxc, sim.gPyc],
                    history_x=sim.dx_time,
                    history_y=sim.dy_time,
                )
                write(path, record)
                if not limitation:
                    expected = evaluate(raw)
                    record["independent_reference"] = expected
                    np.testing.assert_allclose(
                        record["result"]["displacement_m"],
                        expected["result"]["displacement_m"],
                        rtol=8e-12,
                        atol=3e-20,
                    )
                    grad_key = (
                        "pressure_gradient_native"
                        if raw["mode"] == "time"
                        else "pressure_gradient_Pa_m"
                    )
                    np.testing.assert_allclose(
                        record["result"]["pressure_gradient_native"],
                        expected["result"][grad_key],
                        rtol=8e-12,
                        atol=3e-9,
                    )
                    for field, actual in record["native_operators"].items():
                        np.testing.assert_allclose(
                            actual, expected["operators"][field], rtol=8e-12, atol=2e-14
                        )
                    if raw["compute_osmotic"]:
                        for field, actual in record["osmotic"].items():
                            oracle = expected["osmotic"][field]
                            if field == "environment_osmotic_pressure_Pa" and not p.is_ecm:
                                oracle = np.asarray(oracle)[mem_env]
                            np.testing.assert_allclose(
                                actual,
                                oracle,
                                rtol=8e-12,
                                atol=3e-9 if field.endswith("_Pa") else 3e-14,
                            )
            record["status"] = "captured_limitation" if limitation else "passed"
            if limitation:
                assert not raw["expected_failure"] or "captured_limitation" in raw.get(
                    "expected_outcomes", []
                ), raw["name"]
        except (ValueError, TypeError, IndexError, AttributeError) as error:
            record.update(
                status="captured_failure",
                failure_type=type(error).__name__,
                message=str(error),
                partial_displacement=[sim.d_cells_x, sim.d_cells_y]
                if hasattr(sim, "d_cells_x")
                else None,
                history_x=getattr(sim, "dx_time", None),
                history_y=getattr(sim, "dy_time", None),
            )
            write(path, record)
            assert limitation and (
                raw["expected_failure"] or "captured_failure" in raw.get("expected_outcomes", [])
            ), raw["name"]
        write(path, record)
        records.append(dict(name=raw["name"], status=record["status"], path=str(path)))
    assert not any(name == "cells" or name.startswith(("cells.", "jax")) for name in sys.modules)
    manifest.update(
        status="passed",
        records=records,
        component_cases=len(cases()),
        display_cases=len(display_cases()),
        limitations=len(limitations()),
        production_cells_imported=False,
        jax_imported=False,
        time_deformation_enabled=False,
        checks_native_geometry_rebuild=False,
    )
    write(output / "source-manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = capture(args.output)
    print(
        json.dumps(
            {
                key: result[key]
                for key in ("status", "component_cases", "display_cases", "limitations")
            }
        )
    )
