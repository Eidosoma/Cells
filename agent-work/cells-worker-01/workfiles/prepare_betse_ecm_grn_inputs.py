# ruff: noqa: E501 -- frozen emit templates are formatted separately.
"""Emit ECM network cases and independent conditional reference, no evaluation."""

from pathlib import Path

ROOT = Path("/home/robert/Cells")
fixture = '''"""Nonempty ECM GRN cases on explicit retained material declarations."""
import copy
from validation.betse.betse_ecm_transport_fixtures import fixture as material
from validation.betse.betse_normal_grn_join_fixtures import fixture as grn

CASES=("charged","negative","neutral_cold_control","fast_duplicate","rectangular","tight_junction","smoothed","temperature_split","time_dilation","publication_carry","no_modulators","no_molecular_transport","zero_environment_control")
COMPONENT_CONTROLS=("neutral_cold_control","no_modulators","no_molecular_transport","zero_environment_control")
RAW_CASES=("cold_X_missing_Dm","cold_Y_missing_Dm","first_environment_negative","second_environment_negative")
DEPENDENCIES=("wrong_owner","mitochondria","fluid","charged_cold","missing_cache","missing_default","missing_coefficients","prepared_mapping")


def fixture(case="charged"):
    if case not in CASES:raise ValueError("Choose a declared ECM GRN case")
    data=material(case if case in ("fast_duplicate","rectangular","smoothed","temperature_split") else "slow")
    cfg=copy.deepcopy(grn("time_dilation" if case=="time_dilation" else "regulated")["channel_definition"]["network"]["grn_configuration"])
    z=-1.0 if case=="negative" else 0.0 if case=="neutral_cold_control" else 1.0
    for row in cfg["biomolecules"]:
        row.update({"z":z,"scale factor":1e-6,"Dm":1e-5,"Do":1e-3,"Dgj":2e-4})
        if case=="tight_junction":row.update({"TJ permeable":False,"TJ factor":0.2})
        if case=="no_molecular_transport":row.update({"Dm":0.0,"Do":0.0,"Dgj":0.0,"GJ impermeable":True})
        if case=="zero_environment_control":row.update({"Dm":0.0,"env conc":0.0})
    cfg["modulators"][0].update({"activators":["K"],"activator Km":[20.0],"activator n":[2.0]})
    if case=="tight_junction":cfg["modulators"][0]["activator zone"]=["env"]
    if case=="no_modulators":cfg["modulators"]=None
    e=len(data["initial"]["environment_mol_m3"][0])
    data["network"]=dict(owner="grn",configuration=cfg,cold_publish=case=="neutral_cold_control",
        grid_index_groups=dict(all_bound_mem_inds=[0,e//2],interior_bound_mem_inds=[e//2,e-1],ecm_inds_bound_cell=[0,e-1]),
        initial_controls=dict(gj_block=[0.7]*9,NaKATP_block=[1.0]*9),
        initial_ion_boundary=[row[0] for row in data["initial"]["environment_mol_m3"]],
        raw_initialization_fault=None,scope=dict(mitochondria=False,fluid=False,cuts=False,standalone=False))
    data["steps"]=[dict(material=packet,publication=not(case=="publication_carry" and i==1),scheduled_controls=None) for i,packet in enumerate(data["steps"])]
    data["case_id"],data["case_role"]=case,"component_control" if case in COMPONENT_CONTROLS else "new_ecm_grn_case"
    return data


def raw_fixture(case):
    if case not in RAW_CASES:raise ValueError("Choose an original ECM gene failure")
    data=fixture()
    if case.startswith("cold_"):
        name=case.split("_")[1]
        del data["network"]["configuration"]["biomolecules"][0 if name=="X" else 1]["Dm"]
        data["network"]["raw_initialization_fault"]=name
    else:
        i=0 if case=="first_environment_negative" else 1
        data["network"]["configuration"]["biomolecules"][i]["Do"]=1e12
        for call in data["steps"]:
            call["material"]["electric_y_source"]=[[0.0]*len(row) for row in call["material"]["electric_y_source"]]
    data["case_id"],data["case_role"]=case,"raw_partial_failure"
    return data
'''
with (ROOT / "validation/betse/betse_ecm_grn_fixtures.py").open("x") as f:
    f.write(fixture)

ref = (ROOT / "validation/betse/betse_normal_grn_join_reference.py").read_text()
ref = ref.replace(
    "from validation.betse.betse_normal_network_join_reference import _alpha, d",
    """from validation.betse.betse_normal_network_join_reference import _alpha, d
from validation.betse.betse_environment_field_reference import geometry as derive_geometry, _reshape, _flatten, _derivative
from validation.betse.betse_ecm_transport_reference import smooth""",
)
ref = ref.replace("90 if refinement == 1 else 140", "100 if refinement == 1 else 160")
ref = ref.replace('cfg = net["grn_configuration"]', 'cfg = net["configuration"]', 1)
ref = ref.replace("scale_factor=d(1),", 'scale_factor=d(row.get("scale factor",1.0)),', 1)
ref = ref.replace(
    "charge_has_been_balanced=True,", 'charge_has_been_balanced=net["cold_publish"],', 1
)
start = ref.index("                simulator_fields=dict(")
end = ref.index("                owner_fields=dict(", start)
ref = (
    ref[:start]
    + """                simulator_fields={key:[d(0)]*size for key,size in (("extra_rho_cells",n),("extra_rho_env",inputs["environment_sites"]),("extra_J_mem",m),("extra_Jenv_x",inputs["environment_sites"]),("extra_Jenv_y",inputs["environment_sites"]))},
                independent_geometry=derive_geometry(inputs["material_declaration"]["environment_geometry_definition"],precision=context.prec),
"""
    + ref[end:]
)
ref = ref.replace(
    'c_env=[d(row["env conc"])] * m,',
    'c_env=[d(row["env conc"])] * inputs["environment_sites"],',
    1,
)
ref = ref.replace(
    '        geometry = inputs["molecular_geometry"]',
    """        grid=derive_geometry(inputs["material_declaration"]["environment_geometry_definition"],precision=ctx.prec)
        mapping,shape=grid["membrane_to_grid"],grid["shape"]
        sites=shape[0]*shape[1]
        geometry = inputs["molecular_geometry"]""",
    1,
)
ref = ref.replace(
    'd(inputs["bath_volume_m3"])',
    'd(inputs["material_declaration"]["environment_geometry_definition"]["parameters"]["cell_height_m"])*grid["delta_m"]**2',
)
ref = ref.replace(
    'inputs["values_before"]["bath_mol_m3"]', 'inputs["values_before"]["environment_mol_m3"]'
)
ref = ref.replace(
    'membrane_to_environment=definition["membrane_to_environment"],',
    "membrane_to_environment=mapping,",
)
ref = ref.replace(
    "old_env[name][j],\n                        stale_membrane[j],",
    "old_env[name][mapping[j]],\n                        stale_membrane[j],",
)
needle = '                    if not inputs["cluster_open"] and boundary[j]:'
ref = ref.replace(
    needle,
    """                    flux*=d(inputs["rho_channel"][j])
                    gross*=abs(d(inputs["rho_channel"][j]))
"""
    + needle,
    1,
)
start = ref.index("            env_scalar = (")
end = ref.index("            membrane = [cell[i] for i in owner]", start)
ref = (
    ref[:start]
    + """            env=old_env[name][:]
            env_gross=list(map(abs,env))
            conservative=-dt*sum((membrane_flux[j]*area[j] for j in range(m)),Decimal(0))
            exchange=[Decimal(0)]*sites
            exchange_gross=[Decimal(0)]*sites
            fast=inputs["material_declaration"]["parameters"]["fast_update_ecm"]
            for site in range(sites):
                faces=[j for j,k in enumerate(mapping) if k==site]
                if not faces:continue
                if fast:
                    total_area=sum((area[j] for j in faces),Decimal(0))
                    exchange[site]=-membrane_flux[faces[-1]]*total_area/env_volume*dt
                    exchange_gross[site]=membrane_flux_gross[faces[-1]]*total_area/env_volume*dt
                else:
                    exchange[site]=-sum((membrane_flux[j]*area[j] for j in faces),Decimal(0))/env_volume*dt
                    exchange_gross[site]=sum((membrane_flux_gross[j]*area[j] for j in faces),Decimal(0))/env_volume*dt
                env[site]+=exchange[site]
                env_gross[site]+=exchange_gross[site]
            exchange_amount=sum(exchange,Decimal(0))*env_volume
"""
    + ref[end:]
)
needle = "            env = [env_scalar] * m\n"
assert needle in ref
ref = ref.replace(
    needle,
    """            environment=ecm_environment(env,env_gross,p,inputs,grid,dt,runtime)
            env,env_gross=environment["after"],environment["gross"]
            fenvx,fenvy=environment["flux_x"],environment["flux_y"]
""",
    1,
)
ref = ref.replace(
    "                fenvx=0,\n                fenvy=0,",
    "                fenvx=fenvx,\n                fenvy=fenvy,",
    1,
)
ref = ref.replace(
    "c_env=[env_gross] * m,",
    'c_env=env_gross,\n                fenvx=environment["flux_x_gross"],fenvy=environment["flux_y_gross"],',
    1,
)
start = ref.index("            declared_old = (")
end = ref.index("            if publication:", start)
ref = (
    ref[:start]
    + """            defect=exchange_amount-conservative
            source_terms=chemical_amount+directed_gap+defect+environment["clamp_amount"]+environment["transport_amount"]+environment["smoothing_amount"]
            true_volume=grid["true_environment_volume_m3"]
            true_delta=sum(((cell[i]-old_cell[name][i])*volume[i] for i in range(n)),Decimal(0))+sum(((env[k]-old_env[name][k])*true_volume[k] for k in range(sites)),Decimal(0))
            balances[name]=dict(initial_amount_mol=old_amount,final_amount_mol=new_amount,
                chemical_source_mol=chemical_amount,directed_GJ_change_mol=directed_gap,
                native_environment_exchange_mol=exchange_amount,conservative_environment_exchange_mol=conservative,
                fast_exchange_defect_mol=defect,boundary_clamp_change_mol=environment["clamp_amount"],
                collocated_transport_change_mol=environment["transport_amount"],smoothing_change_mol=environment["smoothing_amount"],
                source_effective_residual_mol=new_amount-old_amount-source_terms,
                native_true_volume_total_change_mol=true_delta,site_volume_m3=env_volume,
                physical_global_conservation_credit=False,global_GJ_zero_assumed=False)
"""
    + ref[end:]
)
ref = ref.replace(
    '        publication = inputs["substances_affect_charge"]',
    """        env_charge,env_charge_gross=[Decimal(0)]*sites,[Decimal(0)]*sites
        env_jx,env_jy,env_jx_gross,env_jy_gross=([Decimal(0)]*sites for _ in range(4))
        publication = inputs["substances_affect_charge"]""",
    1,
)
needle = "        return plain(\n            dict(\n                molecules_after=molecules,"
ref = ref.replace(
    needle,
    """                fx_flat=flatten_flux(fenvx)
                fy_flat=flatten_flux(fenvy)
                gx_flat=flatten_flux(environment["flux_x_gross"])
                gy_flat=flatten_flux(environment["flux_y_gross"])
                for k in range(sites):
                    env_charge[k]+=F*env[k]*z*scale
                    env_charge_gross[k]+=abs(F*z*scale)*env_gross[k]
                    env_jx[k]+=fx_flat[k]*z*F*scale
                    env_jy[k]+=fy_flat[k]*z*F*scale
                    env_jx_gross[k]+=gx_flat[k]*abs(z*F*scale)
                    env_jy_gross[k]+=gy_flat[k]*abs(z*F*scale)
        return plain(
            dict(
                independent_geometry=grid,
                extra_rho_env=env_charge,extra_rho_env_gross=env_charge_gross,
                extra_Jenv_x=env_jx,extra_Jenv_y=env_jy,
                extra_Jenv_x_gross=env_jx_gross,extra_Jenv_y_gross=env_jy_gross,
                molecules_after=molecules,""",
    1,
)
helper = """

def flatten_flux(values):
    return _flatten(values) if values and isinstance(values[0],list) else values


def derivative_gross(image,delta):
    ny,nx=len(image),len(image[0])
    gx,gy=[[Decimal(0)]*nx for _ in range(ny)],[[Decimal(0)]*nx for _ in range(ny)]
    for i in range(ny):
        for j in range(nx):
            left,right=(j-1,j+1) if 0<j<nx-1 else (0,1) if j==0 else (nx-2,nx-1)
            bottom,top=(i-1,i+1) if 0<i<ny-1 else (0,1) if i==0 else (ny-2,ny-1)
            gx[i][j]=(image[i][left]+image[i][right])/(delta*(2 if 0<j<nx-1 else 1))
            gy[i][j]=(image[bottom][j]+image[top][j])/(delta*(2 if 0<i<ny-1 else 1))
    return gx,gy


def ecm_environment(env,gross,p,inputs,grid,dt,temperature):
    shape,delta=grid["shape"],grid["delta_m"]
    ny,nx=shape
    size=ny*nx
    volume=d(inputs["material_declaration"]["environment_geometry_definition"]["parameters"]["cell_height_m"])*delta**2
    zero=Decimal(0)
    if not any(env) and d(p["c_bound"])<=d(1e-15):
        return dict(after=env,gross=gross,flux_x=[zero]*size,flux_y=[zero]*size,flux_x_gross=[zero]*size,flux_y_gross=[zero]*size,clamp_amount=zero,transport_amount=zero,smoothing_amount=zero)
    initial=env[:]
    image,ig=_reshape(env,shape),_reshape(gross,shape)
    bound=d(p["c_bound"])
    for i in range(ny):
        for j in range(nx):
            if i in (0,ny-1) or j in (0,nx-1):image[i][j],ig[i][j]=bound,abs(bound)
    clamped=_flatten(image)
    gx,gy=_derivative(image,delta,source_boundary=False)
    ggx,ggy=derivative_gross(ig,delta)
    weights=[d(1)]*size
    if not p["ignoreTJ"]:
        row=list(map(d,inputs["D_env"][inputs["ion_ids"].index("Na")]))
        weights=[v/max(row) for v in row]
        targets={index for group in inputs["grid_index_groups"].values() for index in group}
        for index in targets:weights[index]*=d(p["TJ_factor"])
    ex,ey=inputs["electric_x_source"],inputs["electric_y_source"]
    fx,fy,fxg,fyg=([[zero]*nx for _ in range(ny)] for _ in range(4))
    for i in range(ny):
        for j in range(nx):
            diffusion=weights[i*nx+j]*d(p["Do"])
            alpha=diffusion*d(p["z"])*d(inputs["q_C"])/(d(inputs["kb_J_K"])*temperature)
            fx[i][j]=-diffusion*gx[i][j]+alpha*d(ex[i][j])*image[i][j]
            fy[i][j]=-diffusion*gy[i][j]+alpha*d(ey[i][j])*image[i][j]
            fxg[i][j]=abs(diffusion)*ggx[i][j]+abs(alpha*d(ex[i][j]))*ig[i][j]
            fyg[i][j]=abs(diffusion)*ggy[i][j]+abs(alpha*d(ey[i][j]))*ig[i][j]
    dx,_=_derivative([[-v for v in row] for row in fx],delta,source_boundary=True)
    _,dy=_derivative([[-v for v in row] for row in fy],delta,source_boundary=True)
    dxg,_=derivative_gross(fxg,delta)
    _,dyg=derivative_gross(fyg,delta)
    time=d(p["modify_time_factor"])
    euler=[[image[i][j]+(dx[i][j]+dy[i][j])*dt*time for j in range(nx)] for i in range(ny)]
    eg=[[ig[i][j]+(dxg[i][j]+dyg[i][j])*dt*time for j in range(nx)] for i in range(ny)]
    sharp=d(inputs["sharpness"])
    final=smooth(euler,sharp) if sharp<1 else euler
    fg=smooth(eg,sharp) if sharp<1 else eg
    return dict(after=_flatten(final),gross=_flatten(fg),flux_x=fx,flux_y=fy,flux_x_gross=fxg,flux_y_gross=fyg,
        clamp_amount=sum((a-b for a,b in zip(clamped,initial,strict=True)),zero)*volume,
        transport_amount=sum((a-b for a,b in zip(_flatten(euler),clamped,strict=True)),zero)*volume,
        smoothing_amount=sum((a-b for a,b in zip(_flatten(final),_flatten(euler),strict=True)),zero)*volume)
"""
point = ref.index("\ndef warm(")
ref = ref[:point] + helper + ref[point:]
with (ROOT / "validation/betse/betse_ecm_grn_reference.py").open("x") as f:
    f.write(ref)
print({"files_emitted_without_evaluation": 2})
