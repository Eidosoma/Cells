# ruff: noqa: E501 -- emitted independent scalar templates are subsequently formatted.
"""Copy independent scalar equations as text; never evaluate model bodies."""

import ast
from pathlib import Path

ROOT = Path("/home/robert/Cells")


def function(file, name):
    tree = ast.parse((ROOT / "validation/betse" / file).read_text())
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


current = function("betse_normal_current_reference.py", "evaluate")
current.name = "current_equations"
for n in ast.walk(current):
    if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "ctx.prec":
        n.value = ast.parse("100 if refinement == 1 else 160", mode="eval").body
    if (
        isinstance(n, ast.Return)
        and isinstance(n.value, ast.Call)
        and ast.unparse(n.value.func) == "serial"
    ):
        n.value = n.value.args[0]
voltage = function("betse_normal_voltage_reference.py", "voltage_equations")
for n in ast.walk(voltage):
    if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "ctx.prec":
        n.value = ast.parse("100 if refinement == 1 else 160", mode="eval").body
    if (
        isinstance(n, ast.Return)
        and isinstance(n.value, ast.Call)
        and ast.unparse(n.value.func) == "tree"
    ):
        n.value = n.value.args[0]
header = '''"""Fresh independent Decimal material/network/complete field conditional checks.

Inputs are actual pre-stage copies. No trajectory is independently carried.
Geometry, cache, inverse and field gross majorants derive from declarations.
Scientific modules may only be evaluated by the Chief's qualification runner.
"""

from decimal import Decimal,localcontext

from validation.betse import betse_ecm_grn_reference as network
from validation.betse import betse_ecm_transport_reference as material
from validation.betse import betse_environment_field_reference as environment


def d(value):
    return value if isinstance(value,Decimal) else Decimal.from_float(float(value))


def tree(value,fn):
    if isinstance(value,dict):return {key:tree(item,fn) for key,item in value.items()}
    if isinstance(value,(tuple,list)):return [tree(item,fn) for item in value]
    return fn(value)

'''
tail = '''

def absolute(value):
    return tree(value,lambda v:abs(d(v)))


def hodge_gross(x,y,g,bounds):
    """Propagate absolute sums through each source FD and Dirichlet solve."""
    shape,delta=g["shape"],g["delta_m"]
    ny,nx=shape
    inverse=absolute(g["dirichlet_inverse_m2"])
    dx,_=network.derivative_gross(y,delta)
    _,dy=network.derivative_gross(x,delta)
    dr=environment._combine(dx,dy)
    for i in range(ny):
        for j in range(nx):
            if i in (0,ny-1) or j in (0,nx-1):dr[i][j]=Decimal(0)
    aa=environment._mv(inverse,environment._flatten(dr))
    ax,ay=network.derivative_gross(environment._reshape(aa,shape),delta)
    dx,_=network.derivative_gross(x,delta)
    _,dy=network.derivative_gross(y,delta)
    divergence=environment._combine(dx,dy)
    for i in range(ny):
        divergence[i][0],divergence[i][-1]=abs(d(bounds["L"]))/delta**2,abs(d(bounds["R"]))/delta**2
    for j in range(nx):
        divergence[0][j],divergence[-1][j]=abs(d(bounds["B"]))/delta**2,abs(d(bounds["T"]))/delta**2
    bb=environment._mv(inverse,environment._flatten(divergence))
    gx,gy=network.derivative_gross(environment._reshape(bb,shape),delta)
    return dict(input_x=x,input_y=y,rotated_x=y,rotated_y=x,rotated_divergence=dr,AA=aa,
        solenoidal_x=ay,solenoidal_y=ax,divergence=divergence,BB=bb,gradient_x=gx,gradient_y=gy)


def field_gross(raw,packet,g,cache,values):
    p=raw["parameters"]
    z=list(map(d,raw["current_definition"]["ions"]["valence"]))
    f=d(raw["current_definition"]["parameters"]["F_C_mol"])
    shape,delta,mapping=g["shape"],g["delta_m"],g["membrane_to_grid"]
    size=shape[0]*shape[1]
    currents=[]
    for axis,key in enumerate(("environment_flux_x","environment_flux_y")):
        currents.append(environment._reshape([
            sum(abs(zz*f*d(packet[key][i][k])) for i,zz in enumerate(z))
            +abs(d(packet["extra_environment_current_xy"][k][axis])) for k in range(size)],shape))
    hh=hodge_gross(*currents,g,packet["boundary_V"])
    charge=[sum(abs(zz*f*d(packet["environment_mol_m3"][i][k])) for i,zz in enumerate(z))
            +abs(d(packet["extra_environment_charge_C_m3"][k])) for k in range(size)]
    surface=[Decimal(0)]*size
    mean_area=sum(g["membrane_area_per_site_m2"][k] for k in mapping)/len(mapping)
    for k in mapping:surface[k]=charge[k]*d(p["cell_height_m"])*delta**2/mean_area
    surface_voltage=[v/(cache["ko_environment_per_m"]*d(p["vacuum_permittivity_F_m"])*d(p["relative_permittivity"])) for v in surface]
    rhs=absolute(values["boundary_rhs"])
    phi=environment._mv(absolute(g["dirichlet_inverse_m2"]),environment._flatten(rhs))
    voltage=[a+b for a,b in zip(environment._flatten(environment._gaussian(
        environment._reshape(surface_voltage,shape),constant=True)),phi,strict=True)]
    screen=abs(values["screen"])
    screened=environment._reshape([screen*v for v in voltage],shape)
    gx,gy=network.derivative_gross(screened,delta)
    fx,fy=environment._flatten(gx),environment._flatten(gy)
    normals=raw["current_definition"]["geometry"]["normal_xy"]
    normal=[fx[k]*abs(d(normals[j][0]))+fy[k]*abs(d(normals[j][1])) for j,k in enumerate(mapping)]
    gross=dict(raw_environment_current_x=currents[0],raw_environment_current_y=currents[1],
        local_voltage_assignment=None,local_voltage_smoothed=None,surface_charge_C_m2=surface,
        surface_voltage_V=surface_voltage,environment_charge_C_m3=charge,screened_voltage_source=screened,
        screen=screen,boundary_rhs=rhs,boundary_potential_V=phi,environment_voltage_V=voltage,
        electric_x_source=gx,electric_y_source=gy,normal_electric_source=normal,
        environment_current_x=hh["solenoidal_x"],environment_current_y=hh["solenoidal_y"],
        total_current_x_source=environment._combine(hh["solenoidal_x"],hh["gradient_x"]),
        total_current_y_source=environment._combine(hh["solenoidal_y"],hh["gradient_y"]),
        magnetic_field_source=[v*abs(d(p["magnetic_permeability_H_m"])) for v in hh["AA"]])
    return gross,hh


def voltage_declaration(inputs,g):
    raw=inputs["definition"]["environment_geometry_definition"]
    cg=raw["current_definition"]["geometry"]
    geometry=raw["geometry"]
    radius=[sum((d(point[a])-d(geometry["cell_centres_m"][cg["owner"][j]][a]))**2
                    for a in (0,1)).sqrt() for j,point in enumerate(geometry["membrane_midpoints_m"])]
    diviterm=[d(v)/d(a) for v,a in zip(geometry["cell_volume_m3"],cg["cell_area_m2"],strict=True)]
    p=raw["parameters"]
    return dict(grid=dict(shape=g["shape"],delta_m=g["delta_m"],membrane_to_grid=g["membrane_to_grid"],
            inverse_m2=g["dirichlet_inverse_m2"]),
        geometry=dict(diviterm_m=diviterm,radius_m=radius),
        ions=dict(free_diffusion_m2_s=raw["cache_initial_state"]["free_diffusion_m2_s"]),
        parameters=dict(inputs["field_parameters"],R_J_mol_K=inputs["definition"]["parameters"]["R_J_mol_K"],
            configured_temperature_K=p["configured_temperature_K"],true_cell_size_m=p["true_cell_size_m"],cell_radius_m=p["cell_radius_m"]))


def fields(inputs,*,refinement=1):
    if refinement not in (1,2):raise ValueError("Require two declared independent precision levels")
    with localcontext() as context:
        context.prec=100 if refinement==1 else 160
        raw=inputs["definition"]["environment_geometry_definition"]
        g=environment.geometry(raw,precision=context.prec)
        cache=environment._cache(raw)
        readout=current_equations(raw["current_definition"],inputs["current"],refinement=refinement)
        values,smoothing,hodge=environment._fields(raw,inputs["environment"],g,cache)
        if smoothing is not None or values.get("refused_zero_screening"):
            raise ValueError("Independent ordinary fields require positive screening ECM branch")
        gross,hh=field_gross(raw,inputs["environment"],g,cache,values)
        state=dict(cell_mol_m3=inputs["current"]["cell_mol_m3"],voltage_V=inputs["environment"]["old_voltage_V"])
        vm=voltage_equations(dict(current_definition=raw["current_definition"],voltage_definition=voltage_declaration(inputs,g)),
            state,readout,dict(boundary_V=inputs["environment"]["boundary_V"],material=dict(dt_s=inputs["dt_s"])),
            refinement,dict(cell_mol_m3=absolute(state["cell_mol_m3"])))
        return environment.serial(dict(mode="field",phase=inputs["phase"],decimal_precision=context.prec,
            current=readout,environment=dict(values=values,gross=gross,current_hodge=hodge,hodge_gross=hh),
            voltage=vm,geometry=g,cache=cache,carried_reference_forms=0,fresh_conditional_reference=True,
            physical_global_conservation_credit=False,independent_trajectory=False,
            inverse_supplied=False,cache_supplied=False,old_fields_supplied=False))


def evaluate(inputs,*,refinement=1):
    if inputs.get("mode")=="field":return fields(inputs,refinement=refinement)
    if inputs.get("mode")=="material":
        result=material.evaluate(inputs,refinement=refinement)
        result.update(mode="material",carried_reference_forms=0,fresh_conditional_reference=True,
            physical_global_conservation_credit=False)
        return result
    return network.evaluate(inputs,refinement=refinement)
'''
main = function("betse_ecm_grn_reference.py", "main")
out = (
    header
    + ast.unparse(current)
    + "\n\n"
    + ast.unparse(voltage)
    + tail
    + "\n\n"
    + ast.unparse(main)
    + '\n\nif __name__ == "__main__":\n    main()\n'
)
path = ROOT / "validation/betse/betse_normal_ecm_field_join_reference.py"
with path.open("x") as handle:
    handle.write(out)
print(path)
