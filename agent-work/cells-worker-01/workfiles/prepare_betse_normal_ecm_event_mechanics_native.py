# ruff: noqa: E501
"""Copy authenticated source-capture orchestration; splice original mechanics guards."""

import ast
import copy
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PREFIX = "betse_normal_ecm_event_mechanics"
old = ast.parse((ROOT / "validation/betse/betse_mechanics_join_native.py").read_text())
f = copy.deepcopy(
    next(n for n in old.body if isinstance(n, ast.FunctionDef) and n.name == "evaluate")
)
stop = next(
    i
    for i, n in enumerate(f.body)
    if isinstance(n, ast.Assign)
    and isinstance(n.targets[0], ast.Tuple)
    and ast.unparse(n.targets[0]) == "(history, raw_calls, spline_calls)"
)
f.name = "_prepared_mechanics_view"
f.body = (
    f.body[:stop]
    + ast.parse(
        "return dict(namespace=namespace, cells=cells, parameters=p, sim=sim, pins=pins, sites=sites)"
    ).body
)
header = '''"""Original mechanics bodies on actual event/noise state at the reached native seam.

The extra DEC/neighbor view is an explicit conditional supplied declaration on
identical owners/measures/maps. It never overwrites the material/field geometry.
"""

import copy
import sys
import traceback
from types import SimpleNamespace

import numpy as np

from validation.betse import betse_mechanics_join_native as mechanics

capture = mechanics.capture
'''
adapter = """
CACHE_KEYS = ("osmo_P_cell", "osmo_P_env", "osmo_P_delta", "u_osmo", "div_u_osmo", "PP", "gPxc", "gPyc", "d_cells_x", "d_cells_y", "u_cells_x", "u_cells_y", "u_env_x", "u_env_y")


def data(value):
    if isinstance(value,np.ndarray):
        return value.copy()
    if isinstance(value,dict):
        return {key:data(item) for key,item in value.items()}
    if isinstance(value,(list,tuple)):
        return [data(item) for item in value]
    if isinstance(value,SimpleNamespace) or hasattr(value,'__dict__'):
        return {key:data(item) for key,item in vars(value).items() if not callable(item)}
    if value is None or isinstance(value,(str,int,float,bool,np.generic)):
        return value
    raise ValueError('Unsupported available mechanical source buffer: '+type(value).__name__)


class Owner:
    def __init__(self,declared,sim,cells,parameters):
        self.inputs = declared
        definition = declared['mechanics_definition']
        policy = definition['policy']
        if policy['display_regime']!='none' or policy['fluid_flow'] or policy['td_deform'] or policy['solver']!='FULL':
            raise ValueError('Inherited ordinary mechanics/display domain is unchanged')
        if not 1<=sim.cdl<=16:
            raise ValueError('Inherited native event field domain<=16')
        self.prepared = _prepared_mechanics_view(dict(definition=definition,initial=declared['mechanics_initial'],steps=[]))
        self.namespace = self.prepared['namespace']
        self.cells = self.prepared['cells']
        self.sim = sim
        self.parameters = parameters
        # Exact common geometry is checked; the separately declared DEC view
        # supplies only the mechanics operators and leaves field cells intact.
        for key in ('cell_vol','cell_sa','mem_sa','cell_centres','mem_to_cells','map_cell2ecm'):
            np.testing.assert_array_equal(getattr(cells,key),getattr(self.cells,key),err_msg=key)
        for key in ('R','dt','tm','cell_height'):
            assert getattr(parameters,key)==getattr(self.prepared['parameters'],key),key
        for key,value in vars(self.prepared['parameters']).items():
            setattr(parameters,key,value)
        for key in CACHE_KEYS:
            initial = np.array(declared['mechanics_initial'][key],dtype=float)
            if key in ('u_env_x','u_env_y'):
                assert np.array_equal(initial,getattr(sim,key)) and not np.any(initial)
            else:
                setattr(sim,key,initial)
        self.history = []
        self.raw_calls = []
        self.sample_states = []

    def cache(self):
        return {key:np.array(getattr(self.sim,key),copy=True) for key in CACHE_KEYS} | {
            key:np.asarray(self.inputs['mechanics_initial'][key]).copy()
            for key in ('display_centres_m','display_vertices_m')}

    def incoming(self,ctx,index,clock_s,sigma):
        names = list(self.sim.grn.core.molecules)
        geometry = self.inputs['mechanics_definition']['geometry']
        return dict(receipt=dict(stage='normal_full_after_handlers_before_deferred_material_voltage',
                    geometry_epoch=self.inputs['mechanics_definition']['provenance']['geometry_epoch'],
                    cell_ids=geometry['cell_ids'],environment_ids=geometry['environment_ids'],source_step=index,
                    deferred_material_voltage_commit_done=False),
            clock_s=float(clock_s),dt_s=self.parameters.dt,temperature_K=float(self.sim.T),
            pressure_Pa=self.sim.P_cells.copy(),electric_field_V_m=np.stack((self.sim.E_cell_x,self.sim.E_cell_y)),
            current_density_A_m2=np.stack((self.sim.J_cell_x,self.sim.J_cell_y)),charge_density_C_m3=self.sim.rho_cells.copy(),
            conductivity_S_m=np.array(sigma,copy=True),primary_ids=list(ctx.ion_ids),primary_cell_mM=self.sim.cc_cells.copy(),
            primary_env_mM=self.sim.cc_env.copy(),molecule_ids=[],molecule_cell_mM=[],molecule_env_mM=[],grn_ids=names,
            grn_cell_mM=[self.sim.grn.core.molecules[name].c_cells.copy() for name in names],
            grn_env_mM=[self.sim.grn.core.molecules[name].c_env.copy() for name in names],sample=False)

    def advance(self,ctx,index,clock_s,sigma):
        before = self.incoming(ctx,index,clock_s,sigma)
        frames,auxiliary,latest,hh = [],{'flow':None},{},[]
        stage = 'initial'
        completed = False
        failure = None
        previous = sys.gettrace()
        codes = {self.namespace[name].__code__:name for name in ('osmotic_P','getDeformation')}
        codes[self.namespace['CapturedCells'].HH_cells.__code__] = 'HH_cells'

        def trace(frame,event,arg):
            if previous is not None:
                previous(frame,event,arg)
            if frame.f_code in codes and event in ('return','exception'):
                observed = {key:data(value) for key,value in frame.f_locals.items() if isinstance(value,(np.ndarray,float,int,bool,np.generic))}
                record = dict(function=codes[frame.f_code],event=event,locals=observed)
                if event=='return':
                    record['returned'] = data(arg)
                    latest[codes[frame.f_code]] = observed
                    if codes[frame.f_code]=='HH_cells':hh.append(data(arg))
                else:
                    record['exception'] = dict(type=arg[0].__name__,message=str(arg[1]))
                self.raw_calls.append(record)
            return trace

        def observe(label):
            frames.append(dict(stage=label,cache=self.cache()))

        sim,cells,p = self.sim,self.cells,self.parameters
        try:
            observe('initial')
            sys.settrace(trace)
            stage = 'osmotic_pressure'
            self.namespace['block_0'](sim,cells,clock_s,p)
            if p.deform_osmo:
                auxiliary['osmotic'] = dict(zip(
                    ('cell_osmotic_pressure_Pa','environment_osmotic_pressure_Pa','delta_pressure_Pa','water_velocity_m_s','divergence_per_s','PP_native'),
                    (getattr(sim,key).copy() for key in ('osmo_P_cell','osmo_P_env','osmo_P_delta','u_osmo','div_u_osmo','PP')),strict=True))
                observe('osmotic_pressure')
            stage = 'disabled_flow_gate'
            self.namespace['block_1'](sim,cells,clock_s,p)
            observe('disabled_flow_gate')
            stage = 'steady_deformation'
            self.namespace['block_2'](sim,cells,clock_s,p)
            if p.deformation:
                local = latest['getDeformation']
                potential,rotated_x,rotated_y,*_ = hh[-1]
                _,_,divergence = cells.curl(-sim.d_cells_y,sim.d_cells_x,0)
                auxiliary['steady'] = dict(displacement_m=np.stack((sim.d_cells_x,sim.d_cells_y)),
                    pressure_gradient_Pa_m=np.stack((sim.gPxc,sim.gPyc)),
                    unprojected_elastic_m=np.stack((local['dxo'],local['dyo'])),rotational_m=np.stack((rotated_x,rotated_y)),
                    rotation_potential=potential,osmotic_addition_native=np.stack((local['dxco'],local['dyco'])) if p.deform_osmo else np.zeros((2,sim.cdl)),
                    electric_addition_m=np.stack((sim.E_cell_x,sim.E_cell_y))*p.galvanotropism,divergence_numeric=divergence)
                observe('steady_deformation')
            completed = True
        except Exception as error:
            failure = dict(stage=stage,type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
            raise
        finally:
            sys.settrace(previous)
            self.history.append(dict(before=data(before),frames=frames,auxiliaries=auxiliary,candidate=self.cache(),sample=None,
                carried_cache=self.cache(),source_completed=completed,failure=failure,
                available_source_cells=data(cells),available_source_parameters=data(p),
                raw_calls=data(self.raw_calls),complete_available_buffers=True))

    def sample_state(self,index,clock_s,labels):
        eligible = float(clock_s) in labels
        row = dict(source_call=index,source_time_s=float(clock_s),native_calendar_eligible=eligible,
            display_attempted=False,display_completed=False,
            display_status='held_separate_display_domain_required' if eligible else 'not_eligible',
            maximum_field_cells=16,minimum_quartic_display_cells=25)
        self.sample_states.append(row)
        return row
"""
path = ROOT / "validation/betse" / (PREFIX + "_native_mechanics.py")
with path.open("x") as stream:
    stream.write(header + "\n" + ast.unparse(ast.fix_missing_locations(f)) + "\n" + adapter)
# Copy the unchanged native event evaluator and only insert reached mechanics.
oldtext = (ROOT / "validation/betse/betse_normal_ecm_event_join_native.py").read_text()
oldtree = ast.parse(oldtext)
native = copy.deepcopy(
    next(n for n in oldtree.body if isinstance(n, ast.FunctionDef) and n.name == "evaluate")
)
# Use the existing module's helper namespace explicitly, without modifying it.
imports = []
for n in oldtree.body:
    if isinstance(n, (ast.Import, ast.ImportFrom)):
        imports.append(ast.unparse(n))
code = ast.unparse(native)
code = code.replace(
    "inputs = declared['field']",
    "composition = declared\n    declared = composition['event_inputs']\n    inputs = declared['field']",
    1,
)
code = code.replace(
    "failure = None\n    with warnings.catch_warnings",
    "failure = None\n    mechanical_owner = None\n    with warnings.catch_warnings",
    1,
)
assert code.count("field_call('bootstrap')") == 1
code = code.replace(
    "field_call('bootstrap')",
    "field_call('bootstrap')\n            mechanical_owner = mechanical.Owner(composition,sim,cells,parameters)\n            parameters.t_resample = declared['calendar']['sample_stride']\n            sampled_labels = source_sampling(source_times,ctx.phase)",
    1,
)
assert code.count("observe('protein_noise')") == 1
code = code.replace(
    "observe('protein_noise')",
    "observe('protein_noise')\n                field_phase = 'steady_mechanics'\n                mechanical_owner.advance(ctx,index,float(source_times[index]),initializer_cache['sigma_S_m'])",
    1,
)
assert code.count("field_result = field_call('field')") == 1
code = code.replace(
    "field_result = field_call('field')",
    "field_result = field_call('field')\n                mechanical_owner.sample_state(index,float(source_times[index]),sampled_labels)",
    1,
)
# Both success and refusal records keep the actually reached mechanical history.
code = code.replace(
    "history=history,",
    "history=history, mechanics_history=[] if mechanical_owner is None else mechanical_owner.history, sample_states=[] if mechanical_owner is None else mechanical_owner.sample_states, single_source_mechanics_seam=True, sampled_display_completed=False,",
    1,
)
# Original source sampling statements, with no change to their while condition.
simtree = ast.parse(
    (Path("/mnt/workspaces/Cells/betse-v1.5.0") / "betse/science/sim.py").read_text()
)
cls = next(n for n in simtree.body if isinstance(n, ast.ClassDef) and n.name == "Simulator")
plot = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_plot_loop")
sampling = []
for n in plot.body:
    if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) in ("time_steps_sampled", "i"):
        sampling.append(copy.deepcopy(n))
    elif isinstance(n, ast.While):
        sampling.append(copy.deepcopy(n))
assert len(sampling) == 3
sampler = ast.parse("def source_sampling(time_steps,phase):\n pass").body[0]
sampler.body = sampling + ast.parse("return time_steps_sampled").body
path = ROOT / "validation/betse" / (PREFIX + "_native.py")
main = """

def main():
    from validation.betse.betse_normal_channel_join_runtime import inventory
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    blocked = {'cells','betse','jax','jaxlib'}
    original = builtins.__import__
    def guarded(name,*values,**kwargs):
        if name.split('.')[0] in blocked:
            raise ImportError('Native event/mechanics production import denied: '+name)
        return original(name,*values,**kwargs)
    builtins.__import__ = guarded
    result = evaluate(json.loads(args.inputs.read_text()))
    loaded = [name for name in sys.modules if name.split('.')[0] in blocked]
    assert not loaded
    result.update(production_imports_denied=True,loaded_production_modules=loaded,runtime=inventory())
    archives.write_archive(args.output,result)


if __name__=='__main__':main()
"""
source = (
    '"""Actual original event/noise state with steady mechanics before one deferred commit.\n\nSupplied DEC view and held sampling remain conditional; no whole solver claim.\n"""\n'
    + "\n".join(imports)
    + "\nfrom validation.betse import betse_normal_ecm_event_mechanics_native_mechanics as mechanical\nfrom validation.betse.betse_normal_ecm_event_join_native import capture, run_dispatch\n\n"
    + ast.unparse(ast.fix_missing_locations(sampler))
    + "\n\n"
    + code
    + "\n"
    + main
)
with path.open("x") as stream:
    stream.write(source)
print("two native files written without scientific imports or execution")
