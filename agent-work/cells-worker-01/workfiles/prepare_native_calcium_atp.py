# ruff: noqa: E501
"""Generate literal CaATP/no_negs bodies; stdlib-only static preparation."""

import ast
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = Path("/mnt/workspaces/Cells/betse-v1.5.0")


def prepare():
    target = ROOT / "src/cells/processes/betse_calcium_atp_source.py"
    if target.exists():
        raise FileExistsError(target)
    tree = ast.parse((BASE / "betse/science/sim_toolbox.py").read_text())
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    no_negs = copy.deepcopy(functions["no_negs"])
    no_negs.name = "_no_negs"
    pump = copy.deepcopy(functions["pumpCaATP"])
    pump.name = "_equations"
    pump.args.kwonlyargs.append(ast.arg(arg="observe"))
    pump.args.kw_defaults.append(None)
    labels = dict(
        Qnumo="quotient_numerator",
        Qdenomo="quotient_denominator_raw",
        Q="quotient",
        Keq="equilibrium",
        numo_E="forward_numerator",
        denomo_E="forward_denominator",
        frwd="forward",
        numo_Eb="backward_numerator_unused",
        denomo_Eb="backward_denominator_unused",
        bkwrd="backward_unused",
        f_Ca="raw_flux_mol_m2_s",
    )

    class Observe(ast.NodeTransformer):
        def visit_Name(self, n):
            if n.id == "no_negs":
                n.id = "_no_negs"
            return n

        def visit_Assign(self, n):
            name = ast.unparse(n.targets[0])
            out = [n]
            if name in labels:
                out += ast.parse("observe('" + labels[name] + "'," + name + ")").body
            if name == "inds_Z":
                out += ast.parse("observe('zero_denominator_indices',inds_Z[0])").body
            if name == "Qdenomo[inds_Z]":
                out += ast.parse("observe('quotient_denominator_used',Qdenomo)").body
            return out if len(out) > 1 else n

        def visit_Expr(self, n):
            n = self.generic_visit(n)
            if isinstance(n.value, ast.Call) and ast.unparse(n.value.func) == "_no_negs":
                value = ast.unparse(n.value.args[0])
                name = "membrane" if value == "cCai" else "bath"
                return (
                    ast.parse("observe('before_no_negs_" + name + "'," + value + ")").body
                    + [n]
                    + ast.parse("observe('after_no_negs_" + name + "'," + value + ")").body
                )
            return n

    pump = Observe().visit(pump)
    header = '''"""Literal maintained-pool native CaATP helper; STATIC, NOT QUALIFIED.

The block and met arguments are source-unused. Negative calcium clipping,
zero-product substitution and unused backward arithmetic remain literal.
Original equations: BETSE1.5.0, Alexis Pietak and Cecil Curry.
"""

from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np

from cells.processes import betse_normal_ion_join as ions


class BetseSimUnstableException(ValueError):
    pass


class CalciumSourceRefused(ValueError):
    def __init__(self,reason,partial):
        super().__init__(str(reason))
        self.partial=partial


@dataclass(frozen=True,slots=True)
class Trial:
    incoming_membrane_mM: object
    incoming_bath_mM: object
    membrane_after_mM: object
    bath_after_mM: object
    voltage_V: object
    runtime_temperature_K: float
    parameters: object
    block_unused: object
    met_unused: object
    arithmetic: object
    flux_mol_m2_s: object
    source_completed: bool
    finite: bool
    failure: object


def evaluate(*,membrane_mM,bath_mM,voltage_V,runtime_temperature_K,parameters,block,met):
    # Explicit container shape is preserved, including the scalar refusal probe.
    ci=np.array(membrane_mM,dtype=np.float64,copy=True)
    co=np.array(bath_mM,dtype=np.float64,copy=True)
    vm=np.array(voltage_V,dtype=np.float64,copy=True)
    old_ci,old_co=ci.copy(),co.copy()
    observations={}
    flux=None
    failure=None
    def observe(name,value):
        observations[name]=ions.freeze(np.asarray(value))
    try:
        with np.errstate(all='ignore'):
            flux=_equations(ci,co,vm,runtime_temperature_K,SimpleNamespace(**parameters),
                block,met=met,observe=observe)
    except Exception as error:
        failure=dict(type=type(error).__name__,message=str(error))
    finite=all(np.isfinite(value).all() for value in (ci,co,vm,*observations.values()))
    trial=Trial(ions.freeze(old_ci),ions.freeze(old_co),ions.freeze(ci),ions.freeze(co),ions.freeze(vm),
        float(runtime_temperature_K),ions.freeze(parameters),ions.freeze(np.asarray(block)),
        ions.freeze(met),ions.freeze(observations),ions.freeze(flux),failure is None,bool(finite),ions.freeze(failure))
    if failure:raise CalciumSourceRefused(failure['message'],trial)
    return trial


'''
    target.write_text(
        header
        + ast.unparse(ast.fix_missing_locations(ast.Module(body=[no_negs, pump], type_ignores=[])))
        + "\n"
    )
    record = dict(
        kind="cells.native_calcium_atp_static_source_map@1",
        revision="5269a714aa2593ed2a6708c4516289977d8ae1a2",
        source_sha256={
            "betse/science/sim.py": hashlib.sha256(
                (BASE / "betse/science/sim.py").read_bytes()
            ).hexdigest(),
            "betse/science/sim_toolbox.py": hashlib.sha256(
                (BASE / "betse/science/sim_toolbox.py").read_bytes()
            ).hexdigest(),
            "betse/science/organelles/endo_retic.py": hashlib.sha256(
                (BASE / "betse/science/organelles/endo_retic.py").read_bytes()
            ).hexdigest(),
        },
        functions={
            name: dict(
                first_line=functions[name].lineno,
                last_line=functions[name].end_lineno,
                AST_sha256=hashlib.sha256(
                    ast.dump(functions[name], include_attributes=False).encode()
                ).hexdigest(),
            )
            for name in ("pumpCaATP", "pumpCaER", "no_negs", "update_Co")
        },
        block_Name_load_count=sum(
            isinstance(n, ast.Name) and n.id == "block" and isinstance(n.ctx, ast.Load)
            for n in ast.walk(functions["pumpCaATP"])
        ),
        met_Name_load_count=sum(
            isinstance(n, ast.Name) and n.id == "met" and isinstance(n.ctx, ast.Load)
            for n in ast.walk(functions["pumpCaATP"])
        ),
        scalar_container_refusal=dict(
            source="numpy/_core/tests/test_numeric.py",
            source_lines=[1651, 1657],
            installed_version="2.5.3",
            inference="Scalar-scoped caller fails no_negs; original rectangular native bath avoids0d by row broadcasting",
            numerically_executed=False,
        ),
        original_container=dict(
            no_ecm_edl="mdl",
            cc_env="np.asarray(list of per-ion np.zeros(edl))",
            source_lines=[485, 617, 647, 690, 691],
            update_Co="returns scalar mean; rectangular row assignment broadcasts it",
        ),
        numerical_runs=0,
        scientific_imports=0,
        status="static_preparation_not_qualified",
    )
    (ROOT / "validation/betse/betse_normal_calcium_join_source_map.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    prepare()
