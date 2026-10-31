# ruff: noqa: E501
"""Emit a new normal ECM field/material/network composition; never execute it."""

import ast
from pathlib import Path

ROOT = Path("/home/robert/Cells")
NEW = "betse_normal_ecm_field_join"
old = (ROOT / "src/cells/processes/betse_ecm_grn_join.py").read_text()
advance = next(
    ast.get_source_segment(old, n)
    for n in ast.parse(old).body
    if isinstance(n, ast.FunctionDef) and n.name == "advance"
)
advance = advance.replace(
    "def advance(binding, parent, *, before_network=None):",
    "def advance_material(binding,parent,*,electric_x_source,electric_y_source,before_network=None):",
    1,
)
advance = advance.replace(
    'dict(row["material"], junction_block=control["gj_block"])',
    'dict(row["material"],junction_block=control["gj_block"],electric_x_source=electric_x_source,electric_y_source=electric_y_source)',
    1,
)
header = '''"""Native normal ECM material/network, full current/field and voltage feedback.

Original geometry/operator/cache declarations are prepared explicitly. Each
material call consumes fields reconstructed by bootstrap or the preceding
actual source suffix; no supplied old-electric-field seam remains.
"""

import math
from dataclasses import dataclass

import numpy as np

from cells.processes import betse_ecm_grn_join as network
from cells.processes import betse_ecm_grn_source as source
from cells.processes import betse_ecm_transport as material
from cells.processes import betse_normal_current as current
from cells.processes import betse_environment_field as field
from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_normal_voltage as voltage

LAW_ID="betse_normal_ecm_field_material_network_v1_5_0@1"
freeze=ions.freeze
make_context,material_step=network.make_context,network.material_step
_state,ECMNetworkRejected=network._state,network.ECMNetworkRejected
_failure_snapshot=network._failure_snapshot


@dataclass(frozen=True)
class Binding:
    material_binding:object
    voltage_binding:object
    inputs:object
    identity:str


@dataclass(frozen=True)
class FieldStage:
    binding_identity:str
    before:object
    current:object
    environment:object
    voltage:object
    identity:str


@dataclass(frozen=True)
class State:
    binding_identity:str
    network:object
    field:FieldStage
    identity:str


class FieldJoinRejected(RuntimeError):
    def __init__(self,error,partial):
        super().__init__(str(error))
        self.partial=freeze(partial)


def field_record(value):
    return (value.binding_identity,value.before,value.current,value.environment,value.voltage)


def state(binding,network_state,fields):
    return State(binding.identity,network_state,fields,ions.digest((binding.identity,network_state,fields)))


def voltage_definition(inputs,mb):
    gb=mb.geometry_binding
    g=gb.geometry
    external=gb.definition
    raw=external["geometry"]
    cg=external["current_definition"]["geometry"]
    owner=np.asarray(cg["owner"],np.int64)
    radial=np.asarray(raw["membrane_midpoints_m"])-np.asarray(raw["cell_centres_m"])[owner]
    radius=np.sqrt(radial[:,0]**2+radial[:,1]**2)
    diviterm=np.asarray(raw["cell_volume_m3"])/np.asarray(cg["cell_area_m2"])
    p=external["parameters"]
    return dict(kind=voltage.INPUT_KIND,provenance="Original Cells volume/area and radial statements; field-derived Dirichlet operator/map",grid=dict(
        shape=list(g.shape),delta_m=float(g.delta_m),membrane_to_grid=ions.data(g.membrane_to_grid),
        inverse_m2=ions.data(g.dirichlet_inverse_m2),operator_provenance=gb.identity),
        geometry=dict(diviterm_m=diviterm,radius_m=radius),
        ions=dict(free_diffusion_m2_s=external["cache_initial_state"]["free_diffusion_m2_s"]),
        parameters=dict(capacitance_F_m2=inputs["field_parameters"]["capacitance_F_m2"],
            polarizability=inputs["field_parameters"]["polarizability"],R_J_mol_K=mb.kernel.R_J_mol_K,
            configured_temperature_K=p["configured_temperature_K"],true_cell_size_m=p["true_cell_size_m"],
            cell_radius_m=p["cell_radius_m"]))


def bind(inputs):
    inputs=ions.data(inputs)
    if inputs.get("kind")!="cells.normal_ecm_field_join_inputs@1":
        raise ValueError("Require declared normal ECM field composition")
    if set(inputs["field_parameters"])!={"capacitance_F_m2","polarizability"}:
        raise ValueError("Derive field operators and coefficients from original declarations")
    mb=material.bind(inputs["definition"])
    if mb.geometry_binding.definition["is_ecm"] is not True:
        raise ValueError("Require the original enabled ECM field branch")
    source.validate(inputs["network"],mb)
    material.state(mb,inputs["initial"])
    if len(inputs["steps"])!=3:
        raise ValueError("Require three bounded normal field-composed calls")
    required=set(material.Drive._fields)-{"electric_x_source","electric_y_source"}
    cb=mb.geometry_binding.current_binding
    n,m,s=len(cb.cell_ids),len(cb.membrane_ids),len(cb.ion_ids)
    for row in inputs["steps"]:
        if set(row)!={"material","publication","scheduled_controls","boundary_V"} or type(row["publication"]) is not bool:
            raise ValueError("Declare normal field/network call and boundary ownership")
        if set(row["material"])!=required:
            raise ValueError("Old electric fields must come from the actual preceding field stage")
        packet=row["material"]
        for name in ("dt_s","runtime_temperature_K"):
            if type(packet[name]) not in (int,float) or not math.isfinite(packet[name]) or packet[name]<=0:
                raise ValueError("Require positive finite source call scalars")
        for name,shape in (("junction_block",(m,)),("channel_multiplier",(m,)),
            ("supplied_pump_membrane_flux_mol_m2_s",(s,m)),("supplied_late_membrane_flux_mol_m2_s",(s,m)),
            ("velocity_x_m_s",mb.geometry_binding.geometry.shape),("velocity_y_m_s",mb.geometry_binding.geometry.shape),
            ("boundary_mol_m3",(s,))):
            current._array(packet[name],shape,name)
        boundaries(row["boundary_V"])
    boundaries(inputs["bootstrap"]["boundary_V"])
    if type(inputs["bootstrap"]["dt_s"]) not in (int,float) or not math.isfinite(inputs["bootstrap"]["dt_s"]) or inputs["bootstrap"]["dt_s"]<=0:
        raise ValueError("Require positive original bootstrap dt")
    vb=voltage.bind(cb,voltage_definition(inputs,mb))
    return Binding(mb,vb,freeze(inputs),ions.digest((LAW_ID,inputs,mb.identity,vb.identity)))


def boundaries(raw):
    if set(raw)!={"R","L","T","B"} or any(type(v) not in (int,float) or not math.isfinite(v) for v in raw.values()):
        raise ValueError("Require four finite original boundary voltage values")


def field_inputs(binding,parent,dt,bounds,phase):
    values=parent.material.values
    pubs=parent.network_cache["wire"]["simulator_fields"]
    return dict(mode="field",phase=phase,definition=ions.data(binding.inputs["definition"]),
        field_parameters=ions.data(binding.inputs["field_parameters"]),dt_s=dt,
        current=dict(cell_mol_m3=values.cell_mol_m3,membrane_flux_mol_m2_s=values.membrane_flux_mol_m2_s,
            junction_flux_mol_m2_s=values.junction_flux_mol_m2_s,
            extra_charge_C_m3=pubs["extra_rho_cells"],extra_current_A_m2=pubs["extra_J_mem"]),
        environment=dict(old_voltage_V=values.voltage_V,boundary_V=bounds,
            environment_mol_m3=values.environment_mol_m3,environment_flux_x=values.environment_flux_x_mol_m2_s,
            environment_flux_y=values.environment_flux_y_mol_m2_s,
            extra_environment_current_xy=np.column_stack((pubs["extra_Jenv_x"],pubs["extra_Jenv_y"])),
            extra_environment_charge_C_m3=pubs["extra_rho_env"]))


def reconstruct(binding,parent,dt,bounds,phase,before_field=None):
    before=field_inputs(binding,parent,dt,bounds,phase)
    prefix=environment=vm=None
    if before_field is not None:before_field(source.clone(before))
    try:
        gb=binding.material_binding.geometry_binding
        prefix=current.evaluate(gb.current_binding,current.inputs(gb.current_binding,**before["current"]))
        environment=field.evaluate(gb,prefix,ions.data(before["environment"]))
        vm=voltage.evaluate(binding.voltage_binding,prefix,old_voltage_V=before["environment"]["old_voltage_V"],dt_s=dt,boundary_V=bounds)
        np.testing.assert_array_equal(vm.values.boundary_potential_V,environment.values.boundary_potential_V)
        result=FieldStage(binding.identity,freeze(before),prefix,environment,vm,"")
        result=FieldStage(binding.identity,result.before,prefix,environment,vm,ions.digest(field_record(result)))
        raw=ions.data(parent.material.values._asdict())
        raw["voltage_V"]=vm.values.voltage_V
        material_parent=material.state(binding.material_binding,raw,step_index=parent.material.step_index)
        return _state(binding,material_parent,parent.network_cache,parent.controls),result
    except Exception as error:
        raise FieldJoinRejected(error,dict(stage=phase,parent=parent,before=before,current=prefix,
            environment=environment,voltage=vm,rejected_trial=getattr(error,"trial",None),
            rejected_source=getattr(error,"source",None))) from error


def initialize(binding,*,before_field=None):
    parent=material.state(binding.material_binding,ions.data(binding.inputs["initial"]))
    definition=ions.data(binding.inputs["network"])
    working=material.Values(*(np.array(v,copy=True) for v in parent.values))
    ctx=make_context(binding,working,definition)
    try:cached=source.cold(ctx)
    except Exception as error:
        raise FieldJoinRejected(error,dict(stage="cold",**_failure_snapshot(ctx,None))) from error
    parent=material.state(binding.material_binding,source.material_values(ctx.sim))
    initial=_state(binding,parent,cached,definition["initial_controls"])
    boot=ions.data(binding.inputs["bootstrap"])
    prepared,fields=reconstruct(binding,initial,boot["dt_s"],boot["boundary_V"],"bootstrap",before_field)
    return state(binding,prepared,fields)


def advance(binding,parent,*,before_material=None,before_network=None,before_field=None):
    if type(parent) is not State or parent.binding_identity!=binding.identity or parent.identity!=ions.digest((binding.identity,parent.network,parent.field)):
        raise ValueError("Require an unchanged composed field parent")
    fields=parent.field
    if type(fields) is not FieldStage or fields.binding_identity!=binding.identity or fields.identity!=ions.digest(field_record(fields)):
        raise ValueError("Require the actual prior reconstructed field")
    row=ions.data(binding.inputs["steps"][parent.network.material.step_index])
    controls=ions.data(parent.network.controls) if row["scheduled_controls"] is None else row["scheduled_controls"]
    packet=dict(row["material"],junction_block=controls["gj_block"],
        electric_x_source=fields.environment.values.electric_x_source,
        electric_y_source=fields.environment.values.electric_y_source)
    if before_material is not None:
        before_material(dict(mode="material",definition=ions.data(binding.inputs["definition"]),
            initial=ions.data(parent.network.material.values._asdict()),steps=[source.clone(packet)]))
    try:
        candidate,trial,feedback=advance_material(binding,parent.network,
            electric_x_source=fields.environment.values.electric_x_source,
            electric_y_source=fields.environment.values.electric_y_source,before_network=before_network)
    except Exception as error:
        raise FieldJoinRejected(error,dict(stage="material_network",parent=parent,
            inputs=packet,partial=getattr(error,"partial",None))) from error
    material_parent=candidate
    candidate,next_fields=reconstruct(binding,candidate,packet["dt_s"],row["boundary_V"],"field",before_field)
    return state(binding,candidate,next_fields),trial,feedback,dict(
        material_parent=material_parent,fields=next_fields,initial_field=fields)
'''
with (ROOT / ("src/cells/processes/" + NEW + ".py")).open("x") as stream:
    stream.write(header + "\n\n" + advance + "\n")
print(
    "Normal ECM composition emitted with actual prior-field ownership and conditional boundaries; not evaluated"
)
