"""Authenticated actual flow/HH/DEC/FD bodies and narrowly identified callers."""

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

from validation.flow.betse_fluid_flow_fixtures import (
    base,
    cases,
    cell_refinement,
    environment_refinement,
    limitations,
)

PROTOCOL = Path(__file__).with_name("betse_fluid_flow_protocol.json")


def serial(value):
    if isinstance(value, np.ndarray):
        return serial(value.tolist())
    if isinstance(value, np.generic):
        return serial(value.item())
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [serial(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return str(value)
    return value


def write(path, value):
    path.write_text(json.dumps(serial(value), indent=2, allow_nan=False) + "\n")


def executable(node):
    result = copy.deepcopy(node)
    for item in ast.walk(result):
        if isinstance(item, ast.FunctionDef):
            item.decorator_list = []
            item.returns = None
            for arg in (*item.args.posonlyargs, *item.args.args, *item.args.kwonlyargs):
                arg.annotation = None
    return result


def namespace(trees, manifest):
    bodies = []
    for path, names in (
        ("betse/science/physics/flow.py", ("getFlow",)),
        ("betse/science/sim_toolbox.py", ("HH_Decomp",)),
        ("betse/science/math/finitediff.py", ("gradient", "diff", "divergence")),
    ):
        for node in trees[path].body:
            if isinstance(node, ast.FunctionDef) and node.name in names:
                bodies.append(executable(node))
                manifest["executed_bodies"][node.name] = dict(
                    source=path, first_line=node.lineno, last_line=node.end_lineno
                )
    for path, classname, newname, names in (
        (
            "betse/science/cells.py",
            "Cells",
            "CapturedCells",
            ("graphLaplacian", "curl", "HH_cells"),
        ),
        (
            "betse/science/math/finitediff.py",
            "FiniteDiffSolver",
            "CapturedGrid",
            ("makeLaplacian",),
        ),
    ):
        cls = next(
            n for n in trees[path].body if isinstance(n, ast.ClassDef) and n.name == classname
        )
        selected = [
            executable(n) for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names
        ]
        assert len(selected) == len(names)
        bodies.append(
            ast.ClassDef(name=newname, bases=[], keywords=[], decorator_list=[], body=selected)
        )
        for node in selected:
            manifest["executed_bodies"][classname + "." + node.name] = dict(
                source=path, first_line=node.lineno, last_line=node.end_lineno
            )

    def fragment(name, signature, nodes, path):
        function = ast.parse("def " + name + "(" + signature + "):\n    pass\n").body[0]
        function.body = [copy.deepcopy(n) for n in nodes]
        bodies.append(function)
        manifest["caller_fragments"][name] = dict(
            source=path, lines=[[n.lineno, n.end_lineno] for n in nodes]
        )

    parameter_nodes = [
        n
        for n in ast.walk(trees["betse/science/parameters.py"])
        if isinstance(n, ast.Assign)
        and ast.unparse(n.targets[0]) in ("self.fluid_flow", "self.mu_water", "self.td_deform")
    ]
    assert len(parameter_nodes) == 3
    fragment("read_flow_policy", "self", parameter_nodes, "betse/science/parameters.py")
    simcls = next(
        n
        for n in trees["betse/science/sim.py"].body
        if isinstance(n, ast.ClassDef) and n.name == "Simulator"
    )
    methods = {n.name: n for n in simcls.body if isinstance(n, ast.FunctionDef)}
    flow_init = next(
        n
        for n in ast.walk(methods["init_dynamics"])
        if isinstance(n, ast.If) and ast.unparse(n.test) == "p.fluid_flow is True"
    )
    fragment("initialize_flow", "self,cells,p", [flow_init], "betse/science/sim.py")
    caller = next(
        n
        for n in ast.walk(methods["_run_sim_core_loop"])
        if isinstance(n, ast.If) and ast.unparse(n.test) == "p.fluid_flow"
    )
    fragment("normal_flow_call", "self,cells,p", [caller], "betse/science/sim.py")
    consumer = next(
        n
        for n in ast.walk(methods["update_ecm"])
        if isinstance(n, ast.If) and ast.unparse(n.test) == "p.fluid_flow is True"
    )
    fragment(
        "environment_consumer",
        "self,cells,p",
        [consumer, ast.parse("return ux,uy").body[0]],
        "betse/science/sim.py",
    )
    # The appended return above is capture plumbing, not an upstream source line.
    manifest["caller_fragments"]["environment_consumer"]["appended_return"] = True
    gene = trees["betse/science/chemistry/gene.py"]
    grn = next(
        n
        for n in ast.walk(gene)
        if isinstance(n, ast.If)
        and ast.unparse(n.test) == "self.recalc_fluid"
        and "p.fluid_flow = True" in ast.unparse(n)
    )
    fragment("grn_recalculate", "self,sim,cells,p", [grn], "betse/science/chemistry/gene.py")
    manifest["reachability"] = dict(
        normal_getFlow_calls=[
            n.lineno
            for n in ast.walk(methods["_run_sim_core_loop"])
            if isinstance(n, ast.Call) and ast.unparse(n.func) == "getFlow"
        ],
        fast_getFlow_calls=[
            n.lineno
            for n in ast.walk(methods["_run_fast_sim_core_loop"])
            if isinstance(n, ast.Call) and ast.unparse(n.func) == "getFlow"
        ],
        normal_update_ecm_line=next(
            n.lineno
            for n in ast.walk(methods["_run_sim_core_loop"])
            if isinstance(n, ast.Call) and ast.unparse(n.func) == "self.update_ecm"
        ),
        normal_update_voltage_line=next(
            n.lineno
            for n in ast.walk(methods["_run_sim_core_loop"])
            if isinstance(n, ast.Call) and ast.unparse(n.func) == "self.update_V"
        ),
        initial_update_voltage_line=next(
            n.lineno
            for n in ast.walk(methods["run_sim_core"])
            if isinstance(n, ast.Call) and ast.unparse(n.func) == "self.update_V"
        ),
        graph_initialization_guards="p.deformation and p.td_deform and cells.lapGJ is None",
        graph_initialization_source=ast.unparse(
            next(
                n
                for n in ast.walk(methods["init_dynamics"])
                if isinstance(n, ast.If)
                and ast.unparse(n.test) == "p.td_deform and cells.lapGJ is None"
            )
        ),
        grn_loader_assignments=[
            dict(line=n.lineno, source=ast.unparse(n))
            for n in ast.walk(gene)
            if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "self.recalc_fluid"
        ],
        pressure_names_in_getFlow=sorted(
            {
                n.id
                for n in ast.walk(trees["betse/science/physics/flow.py"].body[-1])
                if isinstance(n, ast.Name) and "press" in n.id.lower()
            }
        ),
        attributes_in_getFlow=sorted(
            {
                n.attr
                for n in ast.walk(trees["betse/science/physics/flow.py"].body[-1])
                if isinstance(n, ast.Attribute)
            }
        ),
        consumers=(
            "ECM ions/molecules and membrane molecular drift; cell output is "
            "sampled/plotted, not passed to native GJ electroflux"
        ),
    )
    ns = dict(
        np=np,
        logs=SimpleNamespace(log_info=lambda *_: None, log_debug=lambda *_: None),
        BetseSimConfException=ValueError,
    )
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=bodies, type_ignores=[])),
            "authenticated-native-flow",
            "exec",
        ),
        ns,
    )
    ns["fd"] = SimpleNamespace(**{k: ns[k] for k in ("gradient", "diff", "divergence")})
    ns["stb"] = SimpleNamespace(HH_Decomp=ns["HH_Decomp"])
    return ns


def make_cells(raw, ns):
    mesh = raw["layout"]
    cells = ns["CapturedCells"]()
    cells.cell_nn_i = np.asarray(mesh["neighbors"], int)
    cells.nn_len = np.asarray(mesh["lengths_m"])
    cells.cell_nn_tx, cells.cell_nn_ty = np.asarray(mesh["curl_directions"]).T
    cells.M_sum_mems = np.asarray(mesh["sum_membranes"], float)
    cells.num_mems = cells.M_sum_mems.sum(axis=1)
    cells.mem_vects_flat = np.column_stack(
        (
            np.zeros((len(cells.nn_len), 2)),
            np.asarray(mesh["force_directions"]),
            np.zeros((len(cells.nn_len), 2)),
        )
    )
    cells.mem_sa, cells.mem_vol = (
        np.asarray(mesh["membrane_area_m2"]),
        np.asarray(mesh["membrane_volume_m3"]),
    )
    cells.mesh = SimpleNamespace(
        vor_edge_len=np.asarray(mesh["dual_edge_m"]),
        tri_edge_len=np.asarray(mesh["primal_edge_m"]),
        delta_tri_0=np.asarray(mesh["incidence"], float),
        delta_tri_0_inv=np.asarray(mesh["incidence_inverse"], float),
        vor_sa=np.asarray(mesh["dual_area_m2"]),
    )
    cells.graphLaplacian(SimpleNamespace(cell_height=mesh["cell_height_m"]))
    cells.X = np.zeros(raw["shape"])
    cells.delta = raw["delta_m"]
    grid = ns["CapturedGrid"]()
    grid.cents_shape = tuple(raw["shape"])
    grid.delta = raw["delta_m"]
    grid.map_ij2k_cents = np.asarray(
        [(i, j) for i in range(raw["shape"][0]) for j in range(raw["shape"][1])]
    )
    cells.grid_laplacian, cells.lapENVinv = grid.makeLaplacian(bound=dict.fromkeys("NSEW", "value"))
    return cells


def make_sim(raw):
    return SimpleNamespace(
        E_cell_x=np.asarray(raw["cell_E_V_m"][0]),
        E_cell_y=np.asarray(raw["cell_E_V_m"][1]),
        rho_cells=np.asarray(raw["cell_rho_C_m3"]),
        E_env_x=np.asarray(raw["environment_E_V_m"][0]),
        E_env_y=np.asarray(raw["environment_E_V_m"][1]),
        v_env=np.asarray(raw["environment_potential_V"]).ravel(),
        D_env_weight=np.asarray(raw["diffusion_weight"]),
        P_cells=np.asarray(raw["pressure_Pa"]),
        PP=np.asarray(raw["osmotic_PP_native"]),
        cdl=len(raw["cell_ids"]),
        mdl=4 * len(raw["cell_ids"]),
        u_cells_x="unwritten",
        u_cells_y="unwritten",
        u_env_x="unwritten",
        u_env_y="unwritten",
    )


def parameters(raw):
    return SimpleNamespace(
        is_ecm=raw["is_ecm"],
        fluid_flow=True,
        mu_water=raw["viscosity_Pa_s"],
        gj_surface=raw["gj_fraction"],
        eo=raw["epsilon_F_m"],
        er=raw["relative_permittivity"],
    )


def capture_case(raw, ns, output, limitation=False, refinement=False):
    cells, sim, p = make_cells(raw, ns), make_sim(raw), parameters(raw)
    record = dict(
        input=raw,
        status="prepared",
        limitation=limitation,
        refinement=refinement,
        full_simulator=False,
    )
    cell_calls, env_calls = [], []
    actual_cell = cells.HH_cells

    def cell_hh(x, y, **kwargs):
        result = actual_cell(x, y, **kwargs)
        cell_calls.append(dict(raw=[x.copy(), y.copy()], output=result, kwargs=kwargs))
        return result

    def env_hh(x, y, cell):
        result = ns["HH_Decomp"](x, y, cell)
        env_calls.append(
            dict(
                raw=[x.reshape(cell.X.shape).copy(), y.reshape(cell.X.shape).copy()], output=result
            )
        )
        return result

    cells.HH_cells = cell_hh
    ns["stb"].HH_Decomp = env_hh
    defect = raw.get("defect")
    if defect == "missing-cell-inverse":
        cells.lapGJinv = None
    if defect == "missing-environment-inverse":
        cells.lapENVinv = None
    if defect == "nan-cell-field":
        sim.E_cell_x[0] = np.nan
    if defect == "nan-ecm-field":
        sim.E_env_x[1, 1] = np.nan
    if defect == "missing-charge-owner":
        del sim.rho_cells
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            ns["normal_flow_call"](sim, cells, p)
            record["status"] = "passed"
        except Exception as exception:
            record.update(
                status="source-exception",
                exception=dict(type=type(exception).__name__, message=str(exception)),
            )
    record["warnings"] = [
        dict(type=type(w.message).__name__, message=str(w.message)) for w in caught
    ]
    if cell_calls:
        call = cell_calls[-1]
        stream, x, y, *_ = call["output"]
        _, _, div = cells.curl(-y, x, 0)
        record["cells"] = dict(
            unprojected_velocity_m_s=call["raw"],
            stream_potential_m2_s=stream,
            velocity_m_s=[x, y],
            divergence_numeric_per_s=div,
        )
        record["cell_hh_kwargs"] = call["kwargs"]
    if env_calls:
        call = env_calls[-1]
        stream, x, y, scalar, gx, gy = call["output"]
        record["environment"] = dict(
            unprojected_native_m3_s=call["raw"],
            stream_potential_native_m4_s=stream.reshape(cells.X.shape),
            output_native_m3_s=[x, y],
            discarded_scalar_native_m4_s=scalar.reshape(cells.X.shape),
            discarded_gradient_native_m3_s=[gx, gy],
            divergence_numeric_m2_s=ns["divergence"](x, y, cells.delta, cells.delta),
        )
    record["writes"] = dict(
        u_cells_x=sim.u_cells_x, u_cells_y=sim.u_cells_y, u_env_x=sim.u_env_x, u_env_y=sim.u_env_y
    )
    if record["status"] == "passed" and any(
        not np.all(np.isfinite(np.asarray(getattr(sim, name))))
        for name in ("u_cells_x", "u_cells_y", *(("u_env_x", "u_env_y") if p.is_ecm else ()))
    ):
        record["status"] = "source-nonfinite"
    write(output / (raw["name"] + ".json"), record)
    if not limitation:
        assert record["status"] == "passed", record
    return dict(
        name=raw["name"], status=record["status"], limitation=limitation, refinement=refinement
    )


def caller_captures(ns, output):
    raw = base()
    cells = make_cells(raw, ns)
    p = parameters(raw)
    p._conf = {
        "variable settings": {"fluid flow": {"include fluid flow": True, "water viscocity": 0.0007}}
    }
    ns["read_flow_policy"](p)
    assert p.fluid_flow is False and p.mu_water == 0.01
    sim = make_sim(raw)
    ns["normal_flow_call"](sim, cells, p)
    disabled = vars(sim).copy()
    p.fluid_flow = True
    cells.lapGJ, cells.lapGJinv = None, None
    ns["initialize_flow"](sim, cells, p)
    initialized = dict(
        cell_x=sim.u_cells_x.copy(),
        cell_y=sim.u_cells_y.copy(),
        gj_x=sim.u_gj_x.copy(),
        gj_y=sim.u_gj_y.copy(),
        env_x=sim.u_env_x.copy(),
        cell_inverse=cells.lapGJinv,
    )
    before = ns["environment_consumer"](sim, cells, p)
    try:
        ns["normal_flow_call"](sim, cells, p)
    except Exception as exception:
        missing = dict(
            type=type(exception).__name__,
            message=str(exception),
            ecm_written_before_cell_failure=not np.all(sim.u_env_x == 0),
        )
    else:
        raise AssertionError("Native initialization unexpectedly supplied cell inverse")
    cells = make_cells(raw, ns)
    ns["normal_flow_call"](sim, cells, p)
    after = ns["environment_consumer"](sim, cells, p)
    p.fluid_flow = False
    off = ns["environment_consumer"](sim, cells, p)
    write(
        output / "caller-policy.json",
        dict(
            status="passed",
            source_fluid_flow=False,
            source_viscosity_Pa_s=0.01,
            source_td_deform=p.td_deform,
            config_requested_flow=True,
            config_requested_viscosity_Pa_s=0.0007,
            disabled_writes_unchanged=disabled["u_cells_x"] == "unwritten"
            and disabled["u_env_x"] == "unwritten",
            initialized=initialized,
            missing_inverse=missing,
            consumer_before=before,
            consumer_after=after,
            consumer_disabled=off,
        ),
    )
    grn_records = []
    for name, z, cscale in (
        ("grn-current", [1.0, 2.0], 1.0),
        ("grn-negative-mean-valence", [-1.0, -2.0], 1.0),
        ("grn-zero-mean-valence", [1.0, -1.0], 1.0),
        ("grn-zero-concentration", [1.0, 2.0], 0.0),
    ):
        sim = SimpleNamespace(
            cc_env=np.asarray([[100.0 + i for i in range(20)], [20.0 + 2 * i for i in range(20)]])
            * cscale,
            zs=np.asarray(z),
            J_env_x=np.arange(20).reshape(4, 5) * 0.03,
            J_env_y=np.full((4, 5), -0.2),
        )
        p = SimpleNamespace(fluid_flow=False, F=96485.33212)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ns["grn_recalculate"](SimpleNamespace(recalc_fluid=True), sim, cells, p)
        finite = np.all(np.isfinite(sim.u_env_x)) and np.all(np.isfinite(sim.u_env_y))
        record = dict(
            name=name,
            status="passed" if finite else "source-nonfinite",
            fluid_flow=p.fluid_flow,
            input=dict(
                current_A_m2=[sim.J_env_x, sim.J_env_y],
                concentration_mol_m3=sim.cc_env.reshape(2, 4, 5),
                valence=z,
                faraday_C_mol=p.F,
            ),
            output=[sim.u_env_x, sim.u_env_y],
            warnings=[str(w.message) for w in caught],
        )
        write(output / (name + ".json"), record)
        grn_records.append(dict(name=name, status=record["status"]))
    return grn_records


def capture(output):
    output.mkdir(parents=True, exist_ok=False)
    source = json.loads(PROTOCOL.read_text())["native_source"]
    checkout, installed = Path(source["checkout"]), Path(source["installed_package"]).parent
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    assert revision == source["revision"]
    manifest = dict(
        status="capturing",
        revision=revision,
        files={},
        executed_bodies={},
        caller_fragments={},
        full_simulator=False,
        production_cells_imported=False,
        jax_imported=False,
        geometry_generation_or_cut_executed=False,
        numpy_version=np.__version__,
        scipy_version=importlib.metadata.version("scipy"),
    )
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
    ns = namespace(trees, manifest)
    manifest["grn_records"] = caller_captures(ns, output)
    records = []
    for raw, limit, refine in (
        [(v, False, False) for v in cases()]
        + [(v, False, True) for v in cell_refinement() + environment_refinement()]
        + [(v, True, False) for v in limitations()]
    ):
        records.append(capture_case(raw, ns, output, limit, refine))
        manifest["records"] = records
        write(output / "source-manifest.json", manifest)
    assert not any(k == "jax" or k.startswith("cells.") for k in sys.modules)
    manifest.update(
        status="passed",
        component_cases=len(cases()),
        refinement_cases=6,
        limitations=len(limitations()),
    )
    write(output / "source-manifest.json", manifest)
    print(
        json.dumps(
            {
                k: manifest[k]
                for k in ("status", "component_cases", "refinement_cases", "limitations")
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    capture(parser.parse_args().output)
