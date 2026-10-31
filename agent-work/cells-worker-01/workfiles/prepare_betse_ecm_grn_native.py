# ruff: noqa: E501 -- emitted original capture wiring is formatted separately.
"""Insert genuine ECM GRN into independently captured normal material order."""

import ast
from pathlib import Path

ROOT = Path("/home/robert/Cells")
old = (ROOT / "validation/betse/betse_ecm_transport_native.py").read_text()
tree = ast.parse(old)
node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "evaluate")
evaluate = ast.get_source_segment(old, node)
evaluate = evaluate.replace(
    'for index, packet in enumerate(inputs["steps"]):',
    """for index, call in enumerate(inputs["steps"]):
                packet=dict(call["material"])
                selected=controls if call["scheduled_controls"] is None else call["scheduled_controls"]
                packet["junction_block"]=selected["gj_block"]
                sim.NaKATP_block=np.asarray(selected["NaKATP_block"],np.float64).copy()
                ctx.trace=network.new_trace()""",
)
needle = '                observe("supplied_late_flux")\n'
assert evaluate.count(needle) == 1
evaluate = evaluate.replace(
    needle,
    needle
    + """                network.dispatch(ctx,raw,call["publication"])
                controls=network.clone(ctx.trace["controls_after"])
                observe("ecm_grn_dispatch")
""",
)
evaluate = evaluate.replace(
    "source_completed=True,",
    "source_completed=True,\n                            network=network.clone(ctx.trace),",
)
evaluate = evaluate.replace(
    "source_completed=False,",
    "source_completed=False,\n                        network=network.clone(ctx.trace),",
)
needle = "    previous = sys.gettrace()"
assert evaluate.count(needle) == 1
cold = """    definition=inputs["network"]
    network.validate_definition(definition,names,n,m,cells.X.size)
    sim.T,parameters.dt=parameters.T,0.0
    sim.rho_channel=np.ones(m)
    sim.gj_block=np.asarray(definition["initial_controls"]["gj_block"],np.float64).copy()
    sim.NaKATP_block=np.asarray(definition["initial_controls"]["NaKATP_block"],np.float64).copy()
    sim.c_env_bound=np.asarray(definition["initial_ion_boundary"],np.float64).copy()
    sim.E_env_x,sim.E_env_y=np.zeros(cells.X.shape),np.zeros(cells.X.shape)
    for key,size in (("extra_rho_cells",n),("extra_rho_env",cells.X.size),("extra_J_mem",m),("extra_Jenv_x",cells.X.size),("extra_Jenv_y",cells.X.size)):
        setattr(sim,key,np.zeros(size))
    ctx=network.augment(sim,cells,parameters,definition,names)
    try:
        cold_cache=network.cold(ctx)
    except Exception as error:
        return dict(status="source_refused",cold_failure=network.cache(ctx),history=[],failure=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc(),stage="cold"),RNG_unchanged=all(np.array_equal(a,b) for a,b in zip(before_rng,np.random.get_state(),strict=True)))
    controls=network.clone(definition["initial_controls"])
"""
evaluate = evaluate.replace(needle, cold + "\n" + needle)
evaluate = evaluate.replace(
    "        geometry=native_geometry,",
    '        status="source_refused" if failure else "source_completed",\n        cold_cache=cold_cache,\n        geometry=native_geometry,',
)
header = '''"""Independent normal ECM material plus genuine nonempty GRN capture."""
import argparse
import ast
import builtins
import copy
import importlib.abc
import json
import sys
import traceback
import warnings
from pathlib import Path
from types import SimpleNamespace,MethodType
import numpy as np
from validation.betse import betse_ecm_transport_native as previous
from validation.betse import betse_ecm_grn_native_network as network
from validation.betse import betse_normal_grn_join_native as archives
capture=previous.capture
'''
main = """

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--inputs",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    blocked={"cells","betse","jax","jaxlib"}
    original=builtins.__import__
    def guarded(name,*rest,**kwargs):
        if name.split(".")[0] in blocked:raise ImportError("ECM native production import denied: "+name)
        return original(name,*rest,**kwargs)
    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self,fullname,path=None,target=None):
            if fullname.split(".")[0] in blocked:raise ImportError("ECM native production import denied: "+fullname)
    builtins.__import__=guarded
    sys.meta_path.insert(0,Guard())
    result=evaluate(json.loads(args.inputs.read_text()))
    loaded=[n for n in sys.modules if n.split(".")[0] in blocked]
    assert not loaded
    result.update(production_imports_denied=True,loaded_production_modules=loaded,runtime=archives.runtime_inventory())
    archives.write_archive(args.output,result)


if __name__=="__main__":main()
"""
with (ROOT / "validation/betse/betse_ecm_grn_native.py").open("x") as f:
    f.write(header + evaluate + "\n" + main)
for rel in (
    "src/cells/processes/betse_ecm_grn_source.py",
    "validation/betse/betse_ecm_grn_native_network.py",
):
    p = ROOT / rel
    s = p.read_text()
    s = s.replace(
        "trace=dict(molecule_frames=[],mover_frames=[],rhs={},control_writes=[],dispatch_stages=[],source_completed=False))",
        "trace=new_trace())",
    )
    s += """\n\ndef new_trace():
    return dict(molecule_frames=[],mover_frames=[],rhs={},control_writes=[],dispatch_stages=[],source_completed=False)
"""
    p.write_text(s)
print({"independent_native_entry_emitted": 1, "scientific_evaluations": 0})
