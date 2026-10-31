# ruff: noqa: E501 -- independent-equation template, formatted before audit.
"""Build independent conditional equations as text; never evaluate science."""

import ast
from pathlib import Path

ROOT = Path("/home/robert/Cells")
old = ast.parse((ROOT / "validation/betse/betse_ecm_transport_reference.py").read_text())
material = next(n for n in old.body if isinstance(n, ast.FunctionDef) and n.name == "evaluate")
material.name = "material_model"
added = 0
for node in ast.walk(material):
    if isinstance(node, ast.For) and ast.unparse(node.target) == "packet_raw":
        for index, child in enumerate(node.body):
            if (
                isinstance(child, ast.For)
                and ast.unparse(child.target) == "i"
                and ast.unparse(child.iter) == "range(s)"
                and "supplied_late_membrane_flux_mol_m2_s" in ast.unparse(child)
            ):
                node.body[index:index] = ast.parse(
                    'calcium_equations(v,inputs["calcium"],native_parameters(inputs["calcium"]),inputs["rate_cache_before"],mapping,junction["boundary"],p["cluster_open"],temperature)\nobserve("calcium_handler")'
                ).body
                added += 1
                break
assert added == 1
header = '''"""Independent native ECM CaATP, material, GRN and full-field conditionals.

No native or numerical-package imports. Each boundary starts from archived actual
inputs; no independently carried trajectory or native enabled-ER claim follows.
"""

import copy
from decimal import Decimal,localcontext

from validation.betse import betse_ecm_transport_reference as ordinary
from validation.betse import betse_environment_field_reference as environment
from validation.betse import betse_normal_ecm_field_join_reference as full

deepcopy=copy.deepcopy
numbers,flux,smooth=ordinary.numbers,ordinary.flux,ordinary.smooth
geometry,serial=environment.geometry,environment.serial
_combine,_derivative,_flatten,_reshape=environment._combine,environment._derivative,environment._flatten,environment._reshape


def d(value):
    return value if isinstance(value,Decimal) else Decimal.from_float(float(value))


def native_parameters(policy):
    return dict(cATP=1.5,cADP=0.1,cPi=0.1,KmCa_Ca=1.0e-3,KmCa_ATP=0.5,
        deltaGATP=-37000,alpha_Ca=policy["alpha_Ca"],F=96485,R=8.314)


def calcium_equations(v,policy,p,incoming,mapping,boundary,cluster_open,temperature):
    names=policy.get("ion_ids")
    # Ca is the explicitly validated final row of this declared family; callers
    # inject its actual index rather than infer a fictitious buffer/default.
    i=policy["Ca_index"] if "Ca_index" in policy else len(v["cell_mol_m3"])-1
    m=len(v["voltage_V"])
    applied=[Decimal(0)]*m
    rate=copy.deepcopy(incoming)
    arithmetic=None
    if d(policy["alpha_Ca"])>0:
        ci=list(map(d,v["membrane_mol_m3"][i]))
        co=[d(v["environment_mol_m3"][i][k]) for k in mapping]
        arithmetic=dict(before_no_negs_membrane=ci[:],before_no_negs_bath=co[:])
        ci=[max(Decimal(0),c) for c in ci]
        co=[max(Decimal(0),c) for c in co]
        arithmetic.update(after_no_negs_membrane=ci[:],after_no_negs_bath=co[:])
        v["membrane_mol_m3"][i]=ci
        # Source fancy-index co is a temporary: the grid row stays unchanged.
        labels=("quotient_numerator","quotient_denominator_raw","quotient_denominator_used","quotient", "equilibrium",
            "forward_numerator","forward_denominator","forward","backward_numerator_unused", "backward_denominator_unused",
            "backward_unused","raw_flux_mol_m2_s")
        arithmetic.update({key:[] for key in labels})
        zeros=[]
        atp,adp,pi,F,R,kc,ka,dg=(d(p[key]) for key in ("cATP","cADP","cPi","F","R","KmCa_Ca","KmCa_ATP","deltaGATP"))
        T=d(temperature)
        for j in range(m):
            qnum=adp*pi*co[j]
            qraw=atp*ci[j]
            stored_product=float(p["cATP"])*float(ci[j])
            qden=d(1e-16) if stored_product==0 else qraw
            if stored_product==0:zeros.append(j)
            quotient=qnum/qden
            equilibrium=(-(dg/(R*T)-2*F*d(v["voltage_V"][j])/(R*T))).exp()
            fn=ci[j]/kc*(atp/ka)
            fd=(1+ci[j]/kc)*(1+atp/ka)
            forward=fn/fd
            bn,bd=co[j]/kc,1+co[j]/kc
            backward=bn/bd
            value=-d(policy["alpha_Ca"])*forward*(1-quotient/equilibrium)
            for key,item in zip(labels,(qnum,qraw,qden,quotient,equilibrium,fn,fd,forward,bn,bd,backward,value),strict=True):
                arithmetic[key].append(item)
            applied[j]=Decimal(0) if not cluster_open and boundary[j] else value
            v["membrane_flux_mol_m2_s"][i][j]+=applied[j]
        arithmetic["zero_denominator_indices"]=zeros
        rate=dict(present=True,value=applied[:])
    return dict(arithmetic=arithmetic,rate_cache_after=rate,applied_flux_mol_m2_s=applied,
        values_after=copy.deepcopy(v),ER_executed=False,Ca_dyn=False,conditional_before_calcium=True)


def calcium(inputs,*,refinement=1):
    if refinement not in (1,2):raise ValueError("Require declared independent precision")
    with localcontext() as ctx:
        ctx.prec=100 if refinement==1 else 160
        external=inputs["definition"]["environment_geometry_definition"]
        g=environment.geometry(external,precision=ctx.prec)
        values=full.tree(inputs["values_before"],d)
        policy=dict(alpha_Ca=inputs["alpha_Ca"],Ca_index=external["current_definition"]["ions"]["ids"].index("Ca"))
        result=calcium_equations(values,policy,inputs["parameters"],inputs["rate_cache_before"],g["membrane_to_grid"],
            inputs["definition"]["junction_geometry"]["boundary"],inputs["definition"]["parameters"]["cluster_open"],inputs["runtime_temperature_K"])
        result.update(mode="calcium",decimal_precision=ctx.prec,carried_reference_forms=0,
            fresh_conditional_reference=True,physical_global_conservation_credit=False,formal_ATP_consumption_claim=False)
        return serial(result)


def evaluate(inputs,*,refinement=1):
    if inputs.get("mode")=="calcium":return calcium(inputs,refinement=refinement)
    if inputs.get("mode")=="material":
        adapted=copy.deepcopy(inputs)
        adapted["calcium"]["Ca_index"]=inputs["definition"]["environment_geometry_definition"]["current_definition"]["ions"]["ids"].index("Ca")
        result=material_model(adapted,refinement=refinement)
        result.update(mode="material",decimal_precision=result["precision"],carried_reference_forms=0,
            fresh_conditional_reference=True,physical_global_conservation_credit=False)
        return result
    result=full.evaluate(inputs,refinement=refinement)
    if inputs.get("mode")=="cold_initialization":
        # Explicit source store seams for the N3 np.linspace clock.
        end=3*float(inputs["bootstrap_dt_s"])
        result.update(native_policy=dict(Ca_dyn=False,CaATP_block=[1.0]*inputs["membranes"],rho_pump=1,
            met_concs=None,endo_retic=None,rate_CaATP_present=False,parameters=native_parameters(inputs["calcium_configuration"])),
            clock=dict(source_times_s=[0.0,end/2,end],call_index=0,material_dt_sum_s=0.0))
    return result
'''
oldmain = next(
    n
    for n in ast.parse(
        (ROOT / "validation/betse/betse_normal_ecm_field_join_reference.py").read_text()
    ).body
    if isinstance(n, ast.FunctionDef) and n.name == "main"
)
out = (
    header
    + "\n\n"
    + ast.unparse(ast.fix_missing_locations(material))
    + "\n\n"
    + ast.unparse(oldmain)
    + '\n\nif __name__ == "__main__":\n    main()\n'
)
path = ROOT / "validation/betse/betse_normal_ecm_calcium_join_reference.py"
with path.open("x") as f:
    f.write(out)
print(path)
