# ruff: noqa: E501 -- emitted source templates are subsequently formatted.
"""Text-only construction of the separately owned native composition capture."""

from pathlib import Path

ROOT = Path("/home/robert/Cells")
old = (ROOT / "validation/betse/betse_ecm_grn_native.py").read_text()


def change(before, after):
    global old
    assert old.count(before) == 1, before[:100]
    old = old.replace(before, after)


change("import argparse\n", "import argparse\nimport ast\nimport hashlib\nimport os\n")
change(
    "from validation.betse import betse_ecm_grn_native_network as network\n",
    "from validation.betse import betse_ecm_grn_native_network as network\n"
    "from validation.betse import betse_environment_field_native as field_native\n",
)
change(
    "capture = previous.capture",
    """def capture():
    source, geometry, sites, geometry_sites, pins, lines = previous.capture()
    root = Path(os.environ.get("CELLS_BETSE_SOURCE", pins["checkout"]))
    sim_tree = ast.parse((root / "betse/science/sim.py").read_bytes())
    tb_tree = ast.parse((root / "betse/science/sim_toolbox.py").read_bytes())
    cells_tree = ast.parse((root / "betse/science/cells.py").read_bytes())
    cls = next(n for n in sim_tree.body if isinstance(n, ast.ClassDef) and n.name == "Simulator")
    methods = {n.name:n for n in cls.body if isinstance(n, ast.FunctionDef)}
    update = methods["update_V"]
    check = next(n for n in tb_tree.body if isinstance(n, ast.FunctionDef) and n.name == "check_v")
    loop = next(n for n in methods["_run_sim_core_loop"].body if isinstance(n, ast.For))
    nodes = [n for n in loop.body if isinstance(n, ast.Expr) and ast.unparse(n) in (
        "self.update_V(cells, p)", "stb.check_v(self.vm)")]
    assert [ast.unparse(n) for n in nodes] == ["self.update_V(cells, p)", "stb.check_v(self.vm)"]
    bootstrap = [n for n in methods["run_sim_core"].body if isinstance(n, ast.Expr)
                 and ast.unparse(n) == "self.update_V(phase.cells, phase.p)"]
    assert len(bootstrap) == 1
    diviterm = [n for n in ast.walk(cells_tree) if isinstance(n, ast.Assign)
                and ast.unparse(n.targets[0]) == "self.diviterm"]
    assert len(diviterm) == 1
    blocks = dict(normal_field=nodes, bootstrap_field=bootstrap, diviterm=diviterm)
    functions = [field_native.wrapper(name, args, blocks[name]) for name,args in (
        ("normal_field","self,cells,p"),("bootstrap_field","self,phase"),("diviterm","self"))]
    geometry["BetseSimUnstableException"] = network.science()["BetseSimUnstableException"]
    exec(compile(ast.fix_missing_locations(ast.Module(
        body=copy.deepcopy([update, check]) + functions, type_ignores=[])),
        "<complete original normal ECM voltage suffix>", "exec"), geometry)
    geometry["stb"].check_v = geometry["check_v"]
    for name,nodes in dict(blocks, update_V=[update], check_v=[check]).items():
        geometry_sites[name] = dict(lines=[[n.lineno,n.end_lineno] for n in nodes],
            ast_sha256=hashlib.sha256(ast.dump(ast.Module(body=nodes,type_ignores=[]),
                                             include_attributes=False).encode()).hexdigest())
    return source, geometry, sites, geometry_sites, pins, lines
""",
)
change("sim = SimpleNamespace(\n", "sim = field_native.Observed(observations={},\n")
change(
    "    history, frames, environment_records, intermediate = [], [], [], {}\n",
    """    parameters.NAv, parameters.er, parameters.eo = p["NAv_per_mol"], p["relative_permittivity"], p["vacuum_permittivity_F_m"]
    parameters.cell_radius, parameters.true_cell_size, parameters.mu = p["cell_radius_m"], p["true_cell_size_m"], p["magnetic_permeability_H_m"]
    parameters.cm = inputs["field_parameters"]["capacitance_F_m2"]
    parameters.cell_polarizability = inputs["field_parameters"]["polarizability"]
    geometry_code["inverses"](cells)
    geometry_code["sharpness"](parameters, {"sharpness cell":cd["parameters"]["sharpness_cell"]})
    geometry_code["weights"](sim,cells,parameters)
    geometry_code["diviterm"](cells)
    initial_cache = external["cache_initial_state"]
    sim.D_free = np.asarray(initial_cache["free_diffusion_m2_s"],np.float64).copy()
    live_cells, live_env = sim.cc_cells, sim.cc_env
    sim.cc_cells, sim.cc_env = (np.asarray(initial_cache[key],np.float64).copy()
                                for key in ("cell_mol_m3","environment_mol_m3"))
    geometry_code["caches"](sim,parameters)
    sim.cc_cells, sim.cc_env = live_cells, live_env
    sim.update_V = MethodType(geometry_code["update_V"],sim)
    initializer_cache = dict(sigma_S_m=np.asarray(sim.sigma),ko_environment_per_m=np.asarray(sim.ko_env))
    history, frames, environment_records, intermediate = [], [], [], {}
    field_rows, hodge, current_locals, voltage_locals = [], [], {}, {}
    field_codes = {name:geometry_code[name].__code__ for name in ("get_current","update_V","HH_Decomp")}
    field_phase, material_candidate, post_material_cache = None, None, None
""",
)
change(
    """        if name is None:
            return None
        local = frame.f_locals
""",
    """        local = frame.f_locals
        field_name = next((key for key,code in field_codes.items() if frame.f_code is code),None)
        if field_name is not None:
            if event == "return":
                if field_name == "HH_Decomp" and arg is not None:
                    hodge.append({key:np.array(local[native],copy=True) for key,native in zip(
                        ("input_x","input_y","rotated_x","rotated_y","rotated_divergence","AA",
                         "solenoidal_x","solenoidal_y","divergence","BB","gradient_x","gradient_y"),
                        ("JJx","JJy","Jxr","Jyr","divJr","AA","Fx","Fy","divJd","BB","Gx","Gy"),strict=True)})
                elif field_name in ("get_current","update_V"):
                    target = current_locals if field_name == "get_current" else voltage_locals
                    target.update({key:np.array(value,copy=True) for key,value in local.items()
                                   if isinstance(value,(np.ndarray,np.generic))})
            return trace
        if name is None:
            return None
""",
)
anchor = '    definition = inputs["network"]\n'
helper = """    def field_input(phase):
        return dict(mode="field",phase=phase,definition=network.clone(raw),
            field_parameters=network.clone(inputs["field_parameters"]),dt_s=parameters.dt,
            current=dict(cell_mol_m3=sim.cc_cells,membrane_flux_mol_m2_s=sim.fluxes_mem,
                junction_flux_mol_m2_s=sim.fluxes_gj,extra_charge_C_m3=sim.extra_rho_cells,
                extra_current_A_m2=sim.extra_J_mem),
            environment=dict(old_voltage_V=sim.vm,boundary_V=sim.bound_V,
                environment_mol_m3=sim.cc_env,environment_flux_x=sim.fluxes_env_x,
                environment_flux_y=sim.fluxes_env_y,
                extra_environment_current_xy=np.column_stack((sim.extra_Jenv_x,sim.extra_Jenv_y)),
                extra_environment_charge_C_m3=sim.extra_rho_env))

    def field_call(phase):
        nonlocal field_phase
        field_phase=phase
        hodge.clear();current_locals.clear();voltage_locals.clear();sim.observations.clear()
        # Retain the actual pre-field inputs before any source field arithmetic.
        record=dict(before=copy.deepcopy(field_input(phase)),source_completed=False)
        field_rows.append(record)
        try:
            if phase == "bootstrap":geometry_code["bootstrap_field"](sim,ctx.phase)
            else:geometry_code["normal_field"](sim,cells,parameters)
            record["source_completed"]=True
        finally:
            record.update(current_locals=copy.deepcopy(current_locals),voltage_locals=copy.deepcopy(voltage_locals),
                hodge=copy.deepcopy(hodge),observations=copy.deepcopy(sim.observations),
                available_simulator_fields={key:network.clone(getattr(sim,key)) for key in (
                    "rho_cells","Jmem","Jgj","Jn","I_mem","J_cell_x","J_cell_y","Jc","rho_env",
                    "rho_env_surf","v_env","Phi_b","E_env_x","E_env_y","Eme","J_env_x","J_env_y",
                    "Jtx","Jty","B_field","sigma_cell","vm","vm_ave","E_cell_x","E_cell_y","Emc","dvm")
                    if hasattr(sim,key)})
        current_values = dict(charge_density_C_m3=sim.rho_cells,membrane_current_A_m2=sim.Jmem,
            junction_current_A_m2=sim.Jgj,raw_normal_current_A_m2=sim.observations["Jn"][0],
            average_normal_current_A_m2=current_locals["Jn_ave"],normal_current_A_m2=sim.Jn,
            inward_membrane_current_A=sim.I_mem,cell_current_xy_A_m2=np.column_stack((sim.J_cell_x,sim.J_cell_y)),
            projected_cell_current_A_m2=sim.Jc)
        field_values = dict(raw_environment_current_x=hodge[-1]["input_x"],raw_environment_current_y=hodge[-1]["input_y"],
            local_voltage_assignment=None,local_voltage_smoothed=None,surface_charge_C_m2=sim.rho_env_surf,
            surface_voltage_V=sim.observations["v_env"][0],environment_charge_C_m3=sim.rho_env,
            screened_voltage_source=current_locals["screen"]*sim.v_env.reshape(cells.X.shape),screen=np.asarray(current_locals["screen"]),
            boundary_rhs=current_locals["div_Jb"],boundary_potential_V=sim.Phi_b,environment_voltage_V=sim.v_env,
            electric_x_source=sim.E_env_x,electric_y_source=sim.E_env_y,normal_electric_source=sim.Eme,
            environment_current_x=sim.J_env_x,environment_current_y=sim.J_env_y,total_current_x_source=sim.Jtx,
            total_current_y_source=sim.Jty,magnetic_field_source=sim.B_field)
        voltage_values = dict(boundary_rhs_V_m2=current_locals["div_Jb"],boundary_potential_V=sim.Phi_b,
            conductivity_S_m=sim.sigma_cell,surface_charge_C_m2=voltage_locals["rho_surf"],voltage_V=sim.vm,
            mean_voltage_V=sim.vm_ave,cell_field_xy_V_m=np.column_stack((sim.E_cell_x,sim.E_cell_y)),
            normal_cell_field_V_m=sim.Emc,derivative_V_s=sim.dvm)
        record.update(current=dict(values=copy.deepcopy(current_values)),environment=dict(values=copy.deepcopy(field_values),
            current_hodge=copy.deepcopy(hodge[-1]),smoothing_hodge=None),voltage=dict(values=copy.deepcopy(voltage_values)),
            candidate=values(),initializer_cache=copy.deepcopy(initializer_cache),
            all_fields_finite=all(np.isfinite(value).all() for group in (current_values,field_values,voltage_values)
                for value in group.values() if value is not None))
        return copy.deepcopy(record)

"""
change(anchor, helper + anchor)
change(
    '    controls = network.clone(definition["initial_controls"])\n',
    """    cold_material = values()
    controls = network.clone(definition["initial_controls"])
""",
)
change(
    """            sys.settrace(trace)
            for index, call in enumerate(inputs["steps"]):
""",
    """            sys.settrace(trace)
            parameters.dt = inputs["bootstrap"]["dt_s"]
            sim.bound_V = dict(inputs["bootstrap"]["boundary_V"])
            field_call("bootstrap")
            for index, call in enumerate(inputs["steps"]):
""",
)
change(
    """                packet = dict(call["material"])
""",
    """                packet = dict(call["material"],electric_x_source=sim.E_env_x.copy(),electric_y_source=sim.E_env_y.copy())
                material_before = dict(mode="material",definition=network.clone(raw),initial=values(),steps=[network.clone(packet)])
                material_candidate, post_material_cache = None, None
                field_phase = "material_network"
""",
)
change(
    """                    ("electric_x_source", "E_env_x"),
                    ("electric_y_source", "E_env_y"),
""",
    "",
)
change(
    """                sim.update_all_concs(cells, parameters)
                history.append(
""",
    """                sim.update_all_concs(cells, parameters)
                material_candidate, post_material_cache = values(), network.cache(ctx)
                sim.bound_V = dict(call["boundary_V"])
                field_result = field_call("field")
                history.append(
""",
)
change(
    """                            candidate=values(),
                            source_completed=True,
""",
    """                            candidate=values(),
                            material_before=material_before,
                            material_candidate=material_candidate,
                            post_material_cache=post_material_cache,
                            field=field_result,
                            source_completed=True,
""",
)
change(
    """                        candidate=values(),
                        source_completed=False,
""",
    """                        candidate=values(),
                        material_before=locals().get("material_before"),
                        material_candidate=material_candidate,
                        post_material_cache=post_material_cache,
                        field=copy.deepcopy(field_rows[-1]) if field_rows and field_phase in ("bootstrap","field") else None,
                        source_completed=False,
""",
)
change(
    """                type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
""",
    """                type=type(error).__name__, message=str(error), traceback=traceback.format_exc(),stage=field_phase
""",
)
change(
    """        cold_cache=cold_cache,
""",
    """        cold_cache=cold_cache,
        cold_material=cold_material,
        initializer_cache=initializer_cache,
        bootstrap=copy.deepcopy(field_rows[0]) if field_rows else None,
        field_rows=field_rows,
""",
)
change(
    """            "fixed-gap source branch; held field/flow/bath"
""",
    """            "fixed-gap source branch; source reconstructed field feedback; explicit external flow/bath/boundary"
""",
)
change(
    '''"""Independent normal ECM material plus genuine nonempty GRN capture."""''',
    '''"""Authenticated normal material/network plus complete native ECM field suffix.

The initial update_V has no source check_v call. Normal calls retain the actual
post-commit update_V then check_v order. No supplied old-field array is consumed.
"""''',
)
path = ROOT / "validation/betse/betse_normal_ecm_field_join_native.py"
with path.open("x") as handle:
    handle.write(old)
print(path)
