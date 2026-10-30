# ruff: noqa: E501 -- emitted source templates are formatted in their outputs.
"""Build separate literal standalone GRN port/native bodies; stdlib only."""

import ast
import copy
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PIN = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
CORE_METHODS = {
    "clear_cache",
    "write_data",
    "report",
    "init_saving",
    "export_eval_strings",
    "export_equations",
}


class Clean(ast.NodeTransformer):
    def visit_Expr(self, node):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        node.decorator_list, node.returns = [], None
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            arg.annotation = None
        return self.generic_visit(node)


def original_nodes(root):
    network = ast.parse((root / "science/chemistry/networks.py").read_text())
    core = Clean().visit(
        copy.deepcopy(
            next(
                n
                for n in network.body
                if isinstance(n, ast.ClassDef) and n.name == "MasterOfNetworks"
            )
        )
    )
    core.body = [n for n in core.body if isinstance(n, ast.FunctionDef) and n.name in CORE_METHODS]
    core.bases = [ast.parse("base.MasterOfNetworks", mode="eval").body]
    owner = Clean().visit(
        copy.deepcopy(
            next(
                n
                for n in ast.parse((root / "science/chemistry/gene.py").read_text()).body
                if isinstance(n, ast.ClassDef) and n.name == "MasterOfGenes"
            )
        )
    )
    run = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == "run_core_sim")

    class Observe(ast.NodeTransformer):
        def visit_Expr(self, node):
            if isinstance(node.value, ast.Call) and ast.unparse(node.value.func) in {
                "self.reinitialize",
                "self.core.clear_cache",
                "self.core.run_loop",
                "self.core.write_data",
            }:
                name = ast.unparse(node.value.func).rsplit(".", 1)[-1]
                before = ast.parse("observe('before_" + name + "',self,phase,locals())").body
                after = ast.parse("observe('after_" + name + "',self,phase,locals())").body
                return before + [node] + after
            return node

    Observe().visit(run)
    runner = ast.parse((root / "science/simrunner.py").read_text())
    branch = next(
        n
        for n in ast.walk(runner)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "self._p.grn_unpickle_filename is None"
    )
    start = ast.parse("def start_new(self,phase):\n    pass\n").body[0]
    start.body = Clean().visit(
        copy.deepcopy(ast.Module(body=branch.body, type_ignores=[]))
    ).body + [ast.Return(value=ast.Name(id="MoG", ctx=ast.Load()))]
    assignment = next(i for i, n in enumerate(start.body) if isinstance(n, ast.Assign))
    start.body[assignment + 1 : assignment + 1] = ast.parse("created(MoG,phase)").body
    return [core, owner, start]


def write(relative, text):
    with (ROOT / relative).open("x") as stream:
        stream.write(text)


common = (WORK / "sim_grn_adapter_template.txt").read_text()
header = '''# ruff: noqa: B007, B905, E501
"""Literal standalone run_core_sim at an explicit prepared-phase boundary.

Filesystem persistence is captured in memory; full SimRunner loading is outside
this boundary. Original clocks, reinitialization and sampled state execute.
"""
import csv
import io
import os
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
from types import SimpleNamespace
import numpy as np
from cells.processes import betse_normal_grn_source as base
from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_normal_current as current
clone,public,wire=base.clone,base.public,base.wire
set_net_opts=base.set_net_opts
BetseSimException=base.molecule_source.BetseSimException
class BetseSimConfException(BetseSimException):
    pass
logs=SimpleNamespace(log_info=lambda *_:None,log_warning=lambda *_:None)
fh=SimpleNamespace(saveSim=lambda filename,data: save_boundary(filename,data))
pathnames=SimpleNamespace(join=os.path.join)
dirs=SimpleNamespace(make_unless_dir=lambda path: directory_boundary(path))
_ACTIVE=None
'''
write(
    "src/cells/processes/betse_sim_grn.py",
    header
    + ast.unparse(ast.fix_missing_locations(ast.Module(body=original_nodes(PIN), type_ignores=[])))
    + "\n"
    + common
    + """

open=capture_open

def science():
    return dict(MasterOfGenes=MasterOfGenes,MasterOfNetworks=MasterOfNetworks,
                Molecule=base.Molecule,Reaction=base.feedback_source.Reaction,
                Modulator=base.feedback_source.Modulator,
                DynamicValue=base.DynamicValue,DynamicValueDict=base.DynamicValueDict)


@dataclass(frozen=True)
class Binding:
    identity: str
    inputs: Mapping


@dataclass(frozen=True)
class State:
    binding_identity: str
    invocation: int
    snapshot: Mapping
    identity: str


class StandaloneRejected(RuntimeError):
    def __init__(self,error,partial):
        super().__init__(str(error))
        self.partial=ions.freeze(partial)


def bind(inputs):
    inputs=ions.data(inputs)
    validate(inputs)
    ib=ions.bind(inputs["ion_definition"])
    cb=current.bind(inputs["current_definition"])
    checked=clone(inputs["network"])
    checked["grn_initialization_publish"]=True
    base.validate(checked,ib,cb,ib.kernel.configured_temperature_K)
    return Binding(ions.digest(inputs),ions.freeze(inputs))


def state(binding,snapshot,invocation):
    snapshot=ions.freeze(snapshot)
    return State(binding.identity,invocation,snapshot,ions.digest((binding.identity,invocation,snapshot)))


def initialize(binding):
    ctx=make_context(ions.data(binding.inputs))
    try:
        with active(ctx):
            ctx.owner=start_new(SimpleNamespace(_p=ctx.p),ctx.phase)
    except Exception as error:
        raise StandaloneRejected(error,dict(stage="cold",snapshot=snapshot(ctx),trace=ctx.trace)) from error
    return state(binding,snapshot(ctx),0)


def advance(binding,parent,*,before_step=None):
    if parent.binding_identity!=binding.identity or parent.identity!=ions.digest((binding.identity,parent.invocation,parent.snapshot)):
        raise ValueError("Changed standalone GRN parent")
    if parent.invocation>=len(binding.inputs["calls"]):
        raise ValueError("No remaining standalone invocation")
    ctx=make_context(ions.data(binding.inputs))
    restore(ctx,ions.data(parent.snapshot))
    ctx.before_step=before_step
    configure_call(ctx,ions.data(binding.inputs["calls"][parent.invocation]))
    try:
        with active(ctx):
            ctx.owner.run_core_sim(ctx.phase)
    except Exception as error:
        raise StandaloneRejected(error,dict(stage="run_core_sim",snapshot=snapshot(ctx),trace=ctx.trace,invocation=parent.invocation)) from error
    return state(binding,snapshot(ctx),parent.invocation+1),ions.freeze(ctx.trace)
""",
)

builder = ast.parse(Path(__file__).read_text())
selected = [
    n
    for n in builder.body
    if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in {"Clean", "original_nodes"}
]
native_header = '''# ruff: noqa: B007, B905, E501
"""Independent pinned-AST standalone GRN capture; production imports denied."""
import ast
import copy
import csv
import io
import json
import hashlib
import os
from abc import ABCMeta
from collections import OrderedDict
from collections.abc import Mapping,MutableMapping
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from validation.betse import betse_normal_grn_join_native_network as previous
from validation.betse import betse_normal_grn_join_native as archive_native
clone,public,wire=previous.clone,previous.public,previous.wire
PROTOCOL=Path(__file__).with_name("betse_sim_grn_protocol.json")
_ACTIVE=None
_SCIENCE=None
CORE_METHODS={"clear_cache","write_data","report","init_saving","export_eval_strings","export_equations"}
'''
native = native_header + ast.unparse(
    ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))
)
native += """

def literal_nodes(root):
    original=original_nodes(root)
    inherited=previous.literal_nodes(root)
    core=next(n for n in inherited if getattr(n,"name",None)=="MasterOfNetworks")
    core.body.extend(original[0].body)
    inherited=[n for n in inherited if getattr(n,"name",None) not in {"MasterOfGenes","initialize_owner","dispatch"}]
    exceptions=ast.parse((root/"exceptions.py").read_text())
    conf=Clean().visit(copy.deepcopy(next(n for n in exceptions.body if isinstance(n,ast.ClassDef) and n.name=="BetseSimConfException")))
    return inherited+[conf,original[1],original[2]]


def science():
    global _SCIENCE
    if _SCIENCE is None:
        pins=json.loads(PROTOCOL.read_text())["native_source"]
        for name,digest in pins["source_sha256"].items():
            data=(Path(pins["checkout"])/name).read_bytes()
            assert hashlib.sha256(data).hexdigest()==digest
            assert data==(Path(pins["installed_package"]).parent/name).read_bytes()
        ns=dict(np=np,copy=copy,csv=csv,open=capture_open,ABCMeta=ABCMeta,
                OrderedDict=OrderedDict,SimpleNamespace=SimpleNamespace,MappingMutableType=MutableMapping,
                types=SimpleNamespace(trim=repr),BetseMethodUnimplementedException=NotImplementedError,
                logs=SimpleNamespace(log_info=lambda *_:None,log_warning=lambda *_:None),tex_val=str,
                Mito=outside,mods=SimpleNamespace(),fd=SimpleNamespace(gradient=outside,divergence=outside,integrator=outside),
                div_env=outside,nernst_planck_flux=outside,observe=observe,created=created,
                fh=SimpleNamespace(saveSim=save_boundary),pathnames=SimpleNamespace(join=os.path.join),
                dirs=SimpleNamespace(make_unless_dir=directory_boundary))
        exec(compile(ast.fix_missing_locations(ast.Module(body=literal_nodes(Path(pins["checkout"])/"betse"),type_ignores=[])),"<pinned standalone GRN>","exec"),ns)
        ns["stb"]=SimpleNamespace(molecule_mover=ns["molecule_mover"],no_negs=ns["no_negs"],map_to_cells=outside)
        _SCIENCE=ns
    return _SCIENCE
"""
native += (
    "\n"
    + common
    + """

def capture(inputs):
    validate(inputs)
    ctx=make_context(inputs)
    before=copy.deepcopy(np.random.get_state())
    answer=dict(cold=None,history=[],failure=None)
    try:
        with active(ctx):
            ctx.owner=science()["start_new"](SimpleNamespace(_p=ctx.p),ctx.phase)
        answer["cold"]=snapshot(ctx)
        attach(ctx)
        for index,call in enumerate(inputs["calls"]):
            ctx.trace=new_trace()
            configure_call(ctx,call)
            try:
                with active(ctx):
                    ctx.owner.run_core_sim(ctx.phase)
            except Exception as error:
                answer["failure"]=dict(type=type(error).__name__,message=str(error),invocation=index,stage="run_core_sim")
            answer["history"].append(dict(snapshot=snapshot(ctx),trace=clone(ctx.trace)))
            if answer["failure"]:
                break
    except Exception as error:
        answer["failure"]=dict(type=type(error).__name__,message=str(error),stage="cold")
        answer["partial"]=snapshot(ctx)
    answer.update(status="source_refused" if answer["failure"] else "source_completed",
                  RNG_unchanged=all(np.array_equal(a,b) for a,b in zip(before,np.random.get_state(),strict=True)),
                  file_persistence_credit=False,normal_solver_executed=False)
    return answer


def main():
    import argparse
    import builtins
    import importlib.abc
    import sys
    parser=argparse.ArgumentParser()
    parser.add_argument("--inputs",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    blocked={"cells","betse","jax","jaxlib"}
    original=builtins.__import__
    def guarded(name,*rest,**kwargs):
        if name.split(".")[0] in blocked:
            raise ImportError("Standalone native production import denied: "+name)
        return original(name,*rest,**kwargs)
    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self,fullname,path=None,target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError("Standalone native production import denied: "+fullname)
    builtins.__import__=guarded
    sys.meta_path.insert(0,Guard())
    result=capture(json.loads(args.inputs.read_text()))
    loaded=[name for name in sys.modules if name.split(".")[0] in blocked]
    assert not loaded
    result.update(production_imports_denied=True,loaded_production_modules=loaded)
    archive_native.write_archive(args.output,result)


if __name__=="__main__":
    main()
"""
)
write("validation/betse/betse_sim_grn_native.py", native)
print({"emitted_without_scientific_execution": 2})
