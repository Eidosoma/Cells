"""Authenticated, unchanged native geometry/cache/current/field statements.

Read-only trace copies expose local arrays. No native package or Cells import is
needed, and no prepared inverse, map or cache is accepted from production.
"""

import ast
import copy
import hashlib
import json
import os
import subprocess
import sys
import warnings
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree

PROTOCOL = Path(__file__).with_name("betse_environment_field_protocol.json")


def wrapper(name, args, nodes):
    function = ast.parse("def " + name + "(" + args + "):\n pass\n").body[0]
    function.body = copy.deepcopy(nodes)
    return function


def capture():
    pins = json.loads(PROTOCOL.read_text())["native_source"]
    root = Path(pins["checkout"])
    frozen_root = Path(os.environ.get("CELLS_BETSE_SOURCE", str(root)))
    installed = Path(pins["installed_package"]).parent
    trees = {}
    for name, expected in pins["source_sha256"].items():
        raw = (frozen_root / name).read_bytes()
        for path in (root / name, installed / name, frozen_root / name):
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError("Pinned native field source changed: " + str(path))
        trees[name] = ast.parse(raw, filename=str(frozen_root / name))
    revision = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != pins["revision"]:
        raise ValueError("Pinned native revision changed")

    def method(file, cls, name):
        tree = trees[file]
        body = (
            tree.body
            if cls is None
            else next(n.body for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
        )
        return next(n for n in body if isinstance(n, ast.FunctionDef) and n.name == name)

    def target(node, text):
        return isinstance(node, ast.Assign) and any(ast.unparse(t) == text for t in node.targets)

    cells_file, sim_file = "betse/science/cells.py", "betse/science/sim.py"
    fd_file = "betse/science/math/finitediff.py"
    make_ecm = method(cells_file, "Cells", "makeECM")
    stop = next(i for i, n in enumerate(make_ecm.body) if target(n, "self.index_k"))
    start = next(i for i, n in enumerate(make_ecm.body) if target(n, "self.delta"))
    environment = method(cells_file, "Cells", "environment")
    names = {
        "self.ecm_sa",
        "self.ecm_vol",
        "self.points_tree",
        "self.map_cell2ecm",
        "self.map_mem2ecm",
        "self.map_ecm2mem",
        "self.envInds_inClust",
        "self.memSa_per_envSquare",
        "self.mems_per_envSquare",
        "self.true_ecm_vol",
        "self.cell2env_corrF",
        "self.M_divmap_mem2ecm",
    }
    prep = [
        n
        for n in environment.body
        if (
            isinstance(n, ast.Assign)
            and any(ast.unparse(t) in names for t in ast.walk(n.targets[0]))
        )
        or (
            isinstance(n, ast.For)
            and ast.unparse(n.target) in ("(ind_mem, ind_ecm)", "(ind_ecm, lst)", "(mem_i, ecm_i)")
        )
    ]
    assert len(prep) == 16, len(prep)
    world = method(cells_file, "Cells", "make_world")
    inverse = [
        n
        for n in world.body
        if target(n, "bdic")
        or isinstance(n, ast.Assign)
        and any(
            ast.unparse(t) in ("self.lapENVinv", "self.lapENV_P_inv")
            for t in ast.walk(n.targets[0])
        )
    ]
    assert len(inverse) == 4
    matrices = method(cells_file, "Cells", "cellMatrices")
    a = next(i for i, n in enumerate(matrices.body) if target(n, "self.M_sum_mems"))
    b = next(
        i
        for i, n in enumerate(matrices.body)
        if target(n, "self.num_mems")
        and isinstance(n.value, ast.Call)
        and ast.unparse(n.value.func) == "np.asarray"
    )
    dynamics = method(sim_file, "Simulator", "init_dynamics")
    a_weight = next(i for i, n in enumerate(dynamics.body) if target(n, "nfrac"))
    b_weight = next(i for i, n in enumerate(dynamics.body) if target(n, "self.smooth_weight_o"))
    cache = [n for n in dynamics.body if target(n, "self.ko_env") or target(n, "self.sigma")]
    assert len(cache) == 2
    sharpness = [
        n for n in ast.walk(trees["betse/science/parameters.py"]) if target(n, "self.smooth_cells")
    ]
    assert len(sharpness) == 1
    blocks = dict(
        grid=make_ecm.body[start : stop + 1],
        environment=prep,
        inverses=inverse,
        owner_matrices=matrices.body[a : b + 1],
        weights=dynamics.body[a_weight : b_weight + 1],
        caches=cache,
        sharpness=sharpness,
    )
    args = dict(
        grid="self,p",
        environment="self,p",
        inverses="self",
        owner_matrices="self",
        weights="self,cells,p",
        caches="self,p",
        sharpness="self,iu",
    )
    functions = [wrapper(name, args[name], body) for name, body in blocks.items()]
    original_functions = [
        method(fd_file, None, name) for name in ("gradient", "diff", "divergence")
    ]
    original_functions += [
        method("betse/science/sim_toolbox.py", None, name) for name in ("HH_Decomp", "smooth_flux")
    ]
    original_functions += [method("betse/science/physics/ion_current.py", None, "get_current")]
    cls = ast.ClassDef(
        name="FiniteDiffSolver",
        bases=[],
        keywords=[],
        decorator_list=[],
        body=[
            copy.deepcopy(method(fd_file, "FiniteDiffSolver", name))
            for name in ("cell_grid", "makeLaplacian")
        ],
    )
    module = ast.Module(body=[cls, *functions, *copy.deepcopy(original_functions)], type_ignores=[])
    namespace = dict(np=np, cKDTree=cKDTree, gaussian_filter=gaussian_filter)
    exec(
        compile(ast.fix_missing_locations(module), "<pinned native environment field>", "exec"),
        namespace,
    )
    fd = SimpleNamespace(
        **{name: namespace[name] for name in ("FiniteDiffSolver", "gradient", "diff", "divergence")}
    )
    namespace.update(
        fd=fd,
        stb=SimpleNamespace(**{name: namespace[name] for name in ("HH_Decomp", "smooth_flux")}),
    )
    sites = {
        name: dict(
            lines=[[n.lineno, n.end_lineno] for n in body],
            ast_sha256=hashlib.sha256(
                ast.dump(ast.Module(body=body, type_ignores=[]), include_attributes=False).encode()
            ).hexdigest(),
        )
        for name, body in blocks.items()
    }
    for n in original_functions + [
        method(fd_file, "FiniteDiffSolver", name) for name in ("cell_grid", "makeLaplacian")
    ]:
        sites[n.name] = dict(
            lines=[[n.lineno, n.end_lineno]],
            ast_sha256=hashlib.sha256(ast.dump(n, include_attributes=False).encode()).hexdigest(),
        )
    return namespace, sites, pins


class Observed(SimpleNamespace):
    def __setattr__(self, name, value):
        if name in ("Jn", "v_env") and hasattr(self, "observations"):
            self.observations.setdefault(name, []).append(np.array(value, copy=True))
        super().__setattr__(name, value)


def evaluate(inputs):
    source, sites, pins = capture()
    raw = inputs["definition"]
    definition = raw["current_definition"]
    g, ions, p = definition["geometry"], definition["ions"], raw["parameters"]
    owner = np.asarray(g["owner"], dtype=np.int64)
    n, m = len(g["cell_ids"]), len(owner)
    if not 1 <= n <= 16 or not 1 <= m <= 128 or not 1 <= len(inputs["frames"]) <= 64:
        raise ValueError("Refuse unbounded native field inputs")
    world = raw["world"]
    cells = SimpleNamespace(
        cell_i=np.arange(n),
        mem_i=np.arange(m),
        mem_to_cells=owner,
        cell_to_mems=[np.flatnonzero(owner == i).tolist() for i in range(n)],
        mem_sa=np.asarray(g["membrane_area_m2"], dtype=np.float64),
        cell_sa=np.asarray(g["cell_area_m2"], dtype=np.float64),
        cell_vol=np.asarray(raw["geometry"]["cell_volume_m3"], dtype=np.float64),
        cell_centres=np.asarray(raw["geometry"]["cell_centres_m"], dtype=np.float64),
        mem_mids_flat=np.asarray(raw["geometry"]["membrane_midpoints_m"], dtype=np.float64),
        mem_vects_flat=np.column_stack((np.zeros((m, 2)), g["normal_xy"])),
        **{key: world[key + "_m"] for key in ("xmin", "xmax", "ymin", "ymax")},
    )
    parameters = SimpleNamespace(
        is_ecm=raw["is_ecm"],
        grid_size=world["grid_size"],
        F=definition["parameters"]["F_C_mol"],
        **{
            native: p[key]
            for key, native in (
                ("q_C", "q"),
                ("kb_J_K", "kb"),
                ("NAv_per_mol", "NAv"),
                ("relative_permittivity", "er"),
                ("vacuum_permittivity_F_m", "eo"),
                ("configured_temperature_K", "T"),
                ("cell_height_m", "cell_height"),
                ("cell_space_m", "cell_space"),
                ("cell_radius_m", "cell_radius"),
                ("true_cell_size_m", "true_cell_size"),
                ("magnetic_permeability_H_m", "mu"),
            )
        },
    )
    initial = raw["cache_initial_state"]
    sim = Observed(
        zs=np.asarray(ions["valence"], dtype=np.float64),
        cc_cells=np.asarray(initial["cell_mol_m3"], dtype=np.float64),
        cc_env=np.asarray(initial["environment_mol_m3"], dtype=np.float64),
        D_free=np.asarray(initial["free_diffusion_m2_s"], dtype=np.float64),
        observations={},
    )
    hodge, operators, local = [], [], {}
    hodge_code = source["HH_Decomp"].__code__
    lap_code = source["FiniteDiffSolver"].makeLaplacian.__code__
    current_code = source["get_current"].__code__

    def trace(frame, event, arg):
        if event == "return":
            v = frame.f_locals
            if frame.f_code is hodge_code:
                hodge.append(
                    {
                        key: np.array(v[native], copy=True)
                        for key, native in zip(
                            (
                                "input_x",
                                "input_y",
                                "rotated_x",
                                "rotated_y",
                                "rotated_divergence",
                                "AA",
                                "solenoidal_x",
                                "solenoidal_y",
                                "divergence",
                                "BB",
                                "gradient_x",
                                "gradient_y",
                            ),
                            (
                                "JJx",
                                "JJy",
                                "Jxr",
                                "Jyr",
                                "divJr",
                                "AA",
                                "Fx",
                                "Fy",
                                "divJd",
                                "BB",
                                "Gx",
                                "Gy",
                            ),
                            strict=True,
                        )
                    }
                )
            elif frame.f_code is lap_code:
                operators.append(tuple(np.array(a, copy=True) for a in arg))
            elif frame.f_code is current_code:
                local.update(
                    {
                        key: np.array(value, copy=True)
                        for key, value in v.items()
                        if isinstance(value, (np.ndarray, np.generic))
                    }
                )
        return trace if frame.f_code in (hodge_code, lap_code, current_code) else None

    before = copy.deepcopy(np.random.get_state())
    previous_trace = sys.gettrace()
    frames = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        sys.settrace(trace)
        try:
            source["grid"](cells, parameters)
            if min(cells.X.shape) < 2 or cells.X.size > 49:
                raise ValueError("Native source grid is outside bounded domain")
            source["owner_matrices"](cells)
            source["environment"](cells, parameters)
            source["inverses"](cells)
            source["sharpness"](
                parameters, {"sharpness cell": definition["parameters"]["sharpness_cell"]}
            )
            source["weights"](sim, cells, parameters)
            source["caches"](sim, parameters)
            sim.edl = cells.X.size
            cache = dict(
                sigma_S_m=np.asarray(sim.sigma), ko_environment_per_m=np.asarray(sim.ko_env)
            )
            for row in inputs["frames"]:
                hodge.clear()
                local.clear()
                sim.observations.clear()
                for key, native in (
                    ("cell_mol_m3", "cc_cells"),
                    ("membrane_flux_mol_m2_s", "fluxes_mem"),
                    ("junction_flux_mol_m2_s", "fluxes_gj"),
                    ("extra_charge_C_m3", "extra_rho_cells"),
                    ("extra_current_A_m2", "extra_J_mem"),
                ):
                    setattr(sim, native, np.asarray(row["current"][key], dtype=np.float64).copy())
                packet = row["environment"]
                sim.vm = np.asarray(packet["old_voltage_V"], dtype=np.float64).copy()
                sim.bound_V = dict(packet["boundary_V"])
                if raw["is_ecm"]:
                    for key, native in (
                        ("environment_mol_m3", "cc_env"),
                        ("environment_flux_x", "fluxes_env_x"),
                        ("environment_flux_y", "fluxes_env_y"),
                        ("extra_environment_charge_C_m3", "extra_rho_env"),
                    ):
                        setattr(sim, native, np.asarray(packet[key], dtype=np.float64).copy())
                    sim.extra_Jenv_x, sim.extra_Jenv_y = np.asarray(
                        packet["extra_environment_current_xy"], dtype=np.float64
                    ).T.copy()
                else:
                    sim.D_env_weight = np.asarray(
                        packet["environment_weight"], dtype=np.float64
                    ).copy()
                source["get_current"](sim, cells, parameters)
                current_values = {
                    key: np.array(value, copy=True)
                    for key, value in (
                        ("charge_density_C_m3", sim.rho_cells),
                        ("membrane_current_A_m2", sim.Jmem),
                        ("junction_current_A_m2", sim.Jgj),
                        ("raw_normal_current_A_m2", sim.observations["Jn"][0]),
                        ("average_normal_current_A_m2", local["Jn_ave"]),
                        ("normal_current_A_m2", sim.Jn),
                        ("inward_membrane_current_A", sim.I_mem),
                        ("cell_current_xy_A_m2", np.column_stack((sim.J_cell_x, sim.J_cell_y))),
                        ("projected_cell_current_A_m2", sim.Jc),
                    )
                }
                is_ecm = raw["is_ecm"]
                values = dict(
                    raw_environment_current_x=hodge[-1]["input_x"],
                    raw_environment_current_y=hodge[-1]["input_y"],
                    local_voltage_assignment=None if is_ecm else local["vce"],
                    local_voltage_smoothed=None if is_ecm else local["Phi"],
                    surface_charge_C_m2=sim.rho_env_surf if is_ecm else None,
                    surface_voltage_V=sim.observations["v_env"][0] if is_ecm else None,
                    environment_charge_C_m3=sim.rho_env if is_ecm else None,
                    screened_voltage_source=local["screen"] * sim.v_env.reshape(cells.X.shape)
                    if is_ecm
                    else None,
                    screen=np.asarray(local["screen"]) if is_ecm else None,
                    boundary_rhs=local["div_Jb"],
                    boundary_potential_V=sim.Phi_b,
                    environment_voltage_V=sim.v_env,
                    electric_x_source=sim.E_env_x,
                    electric_y_source=sim.E_env_y,
                    normal_electric_source=sim.Eme,
                    environment_current_x=sim.J_env_x,
                    environment_current_y=sim.J_env_y,
                    total_current_x_source=sim.Jtx,
                    total_current_y_source=sim.Jty,
                    magnetic_field_source=sim.B_field,
                )
                frames.append(
                    copy.deepcopy(
                        dict(
                            values=values,
                            current=dict(values=current_values),
                            smoothing_hodge=None if is_ecm else hodge[0],
                            current_hodge=hodge[-1],
                        )
                    )
                )
        finally:
            sys.settrace(previous_trace)
    after = np.random.get_state()
    unchanged = (
        before[0] == after[0] and np.array_equal(before[1], after[1]) and before[2:] == after[2:]
    )
    geometry = dict(
        shape=cells.X.shape,
        delta_m=cells.delta,
        X_m=cells.X,
        Y_m=cells.Y,
        grid_points_m=cells.xypts,
        index_ij=cells.map_ij2k,
        cell_to_grid=cells.map_cell2ecm,
        membrane_to_grid=cells.map_mem2ecm,
        membrane_area_per_site_m2=cells.memSa_per_envSquare,
        membranes_per_site=cells.mems_per_envSquare,
        true_environment_volume_m3=cells.true_ecm_vol,
        membrane_divergence_map_m2=cells.M_divmap_mem2ecm,
        cell_to_environment_correction=cells.cell2env_corrF,
        dirichlet_laplacian_per_m2=operators[0][0],
        dirichlet_inverse_m2=cells.lapENVinv,
        neumann_laplacian_per_m2=operators[1][0],
        neumann_inverse_m2=cells.lapENV_P_inv,
    )
    return dict(
        geometry=geometry,
        cache=cache,
        frames=frames,
        source_sites=sites,
        native_source_sha256=pins["source_sha256"],
        RNG_unchanged=bool(unchanged),
        warnings=[str(w.message) for w in caught],
        native_source_only=True,
        physical_field_energy_parity=False,
    )
