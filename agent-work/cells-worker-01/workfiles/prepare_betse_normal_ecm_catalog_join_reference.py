# ruff: noqa: E501
"""Write stdlib scalar ECM catalog conditionals; no model/reference evaluation."""

import ast
from pathlib import Path

ROOT = Path("/home/robert/Cells")
folder = ROOT / "validation/betse"
original = (folder / "betse_normal_ecm_calcium_join_reference.py").read_text()
kin_tree = ast.parse((folder / "betse_normal_catalog_join_equations.py").read_text())
kinetics = "\n\n".join(
    ast.unparse(n)
    for n in kin_tree.body
    if isinstance(n, ast.FunctionDef) and n.name in ("inventory", "kinetics")
)
kinetics = kinetics.replace("90 if refinement == 1 else 140", "100 if refinement == 1 else 160")
imports = """
from validation.betse.betse_normal_catalog_join_scalar import cav_kinetics, hcn_kinetics, kv1_kinetics
from validation.channels import calcium_catalog_extra_reference as calcium_gates
from validation.channels import hcn_extra_reference as hcn
from validation.channels import morris_lecar_channels_reference as ml
from validation.channels import potassium_catalog_reference as potassium
from validation.channels import sodium_catalog_reference as sodium
from pathlib import Path
import json
"""
kinetics = kinetics.replace("calcium._kinetics", "calcium_gates._kinetics")
channel_code = """
def modulation(row, values, molecules, names, mapping):
    m=len(mapping)
    result=[Decimal(1)]*m
    for role in ("activator","inhibitor"):
        species=row.get("channel "+role+"s") or []
        zones=row.get(role+" zone") or ["cell"]*len(species)
        for label,km,power,zone in zip(species,row.get(role+" Km") or [],row.get(role+" n") or [],zones,strict=True):
            if label in names:
                samples=(values["membrane_mol_m3"][names.index(label)] if zone=="cell"
                    else [values["environment_mol_m3"][names.index(label)][site] for site in mapping])
            else:
                samples=(molecules[label]["cc_at_mem"] if zone=="cell"
                    else [molecules[label]["c_env"][site] for site in mapping])
            for j,sample in enumerate(samples):
                hill=(d(sample)/d(km))**d(power)
                result[j]*=hill/(1+hill) if role=="activator" else 1/(1+hill)
    return result


def channel_sequence(inputs, *, refinement=1, values=None):
    # Whole bounded sequence conditional on actual incoming class caches. No ctor oracle claim.
    with localcontext() as context:
        context.prec=100 if refinement==1 else 160
        raw=inputs["material_declaration"]
        external=raw["environment_geometry_definition"]
        current=external["current_definition"]
        names=current["ions"]["ids"]
        zvals=current["ions"]["valence"]
        cg=current["geometry"]
        geom=geometry(external,precision=context.prec)
        mapping=geom["membrane_to_grid"]
        owner=cg["owner"]
        area=numbers(cg["membrane_area_m2"])
        volume=numbers(external["geometry"]["cell_volume_m3"])
        site_volume=d(external["parameters"]["cell_height_m"])*geom["delta_m"]**2
        m,n,e=len(owner),len(volume),len(geom["grid_points_m"])
        F,R,tm,dt,T=(d(inputs[k]) for k in ("F","R","membrane_thickness_m","dt_s","runtime_temperature_K"))
        v=numbers(inputs["values_before"]) if values is None else values
        start=copy.deepcopy(v)
        wire=inputs["cache_before"]["wire"]
        molecules=wire["molecule_fields"]
        extra=numbers(inputs["incoming_channel_current_A_m2"])
        extra_gross=[abs(x) for x in extra]
        cell_add=[[Decimal(0)]*n for _ in names]
        mem_add=[[Decimal(0)]*m for _ in names]
        env_add=[[Decimal(0)]*e for _ in names]
        books=[]
        events=[]
        nonce=0
        for row in inputs["catalog"]["populations"] or []:
            name,cls=row["name"],row["channel type"]
            entry=inventory()["classes"][cls]
            cache=copy.deepcopy(wire["channel_fields"][name]["core_fields"])
            targets=cache["targets"]
            moddy=modulation(row,v,molecules,names,mapping)
            gates=("m",) if entry["family"]=="ML" else ("m","h")
            updated={key:[] for key in gates}
            for slot,j in enumerate(targets):
                target,tau=kinetics(cls,d(float(v["voltage_V"][j])),refinement)
                for a,key in enumerate(gates):
                    old=cache[key][slot] if isinstance(cache[key],(tuple,list)) else cache[key]
                    updated[key].append(target[a] if entry["family"]=="ML" and cls not in ml.KINETIC
                        else (tau[a]*d(old)+dt*target[a])/(tau[a]+dt))
            opening=[Decimal(0)]*m
            powers=(1,0) if entry["family"]=="ML" else (int(cache["_mpower"]),int(cache["_hpower"]))
            for k,j in enumerate(targets):
                a,b=powers
                opening[j]=(updated["m"][k]**a if a else Decimal(1))*(updated["h"][k]**b if b else Decimal(1))
            routes=[]
            maxdm=d(row.get("max conductivity") if row.get("max conductivity") is not None else row["max Dm"])
            for ion,relative in entry["routes"]:
                i=names.index(ion)
                diffusion=[x*d(relative)*maxdm*y for x,y in zip(opening,moddy,strict=True)]
                before_cell=v["cell_mol_m3"][i][:]
                before_mem=v["membrane_mol_m3"][i][:]
                before_env=v["environment_mol_m3"][i][:]
                sampled_mem=[before_cell[a] for a in owner]
                sampled_env=[before_env[k] for k in mapping]
                v["voltage_V"]=[d(float(x)+1e-25) for x in v["voltage_V"]]
                nonce+=1
                z=d(float(zvals[i])+1e-25)
                fluxes=[]
                gross=[]
                for j in range(m):
                    alpha=z*v["voltage_V"][j]*F/(R*T)
                    exp=(-alpha).exp()
                    rho=d(inputs["rho_channel"][j])
                    fluxes.append(-diffusion[j]*alpha/tm*(sampled_mem[j]-sampled_env[j]*exp)/(1-exp)*rho)
                    probability=max(Decimal(1),abs(opening[j]))
                    dscale=probability*abs(d(relative)*maxdm*moddy[j]*rho)
                    concentration=(abs(sampled_mem[j])+abs(sampled_env[j])+cell_add[i][owner[j]]+env_add[i][mapping[j]])
                    gross.append(dscale/tm*concentration*(1+2*abs(alpha)))
                for a in range(n):
                    v["cell_mol_m3"][i][a]+=dt*sum(fluxes[j]*area[j] for j in range(m) if owner[j]==a)/volume[a]
                    cell_add[i][a]+=dt*sum(gross[j]*area[j] for j in range(m) if owner[j]==a)/volume[a]
                v["membrane_mol_m3"][i]=[v["cell_mol_m3"][i][a] for a in owner]
                mem_add[i]=[cell_add[i][a] for a in owner]
                conservative=before_env[:]
                for j,site in enumerate(mapping):
                    conservative[site]-=dt*fluxes[j]*area[j]/site_volume
                if raw["parameters"]["fast_update_ecm"]:
                    last=[Decimal(0)]*e
                    last_gross=[Decimal(0)]*e
                    for j,site in enumerate(mapping):
                        last[site]=-fluxes[j]
                        last_gross[site]=gross[j]
                    rates=[last[k]*geom["membrane_area_per_site_m2"][k]/site_volume for k in range(e)]
                    rate_gross=[last_gross[k]*geom["membrane_area_per_site_m2"][k]/site_volume for k in range(e)]
                else:
                    rates=[-sum(fluxes[j]*area[j] for j in range(m) if mapping[j]==k)/site_volume for k in range(e)]
                    rate_gross=[sum(gross[j]*area[j] for j in range(m) if mapping[j]==k)/site_volume for k in range(e)]
                v["environment_mol_m3"][i]=[x+dt*r for x,r in zip(before_env,rates,strict=True)]
                env_add[i]=[a+dt*b for a,b in zip(env_add[i],rate_gross,strict=True)]
                extra=[a-f*F*d(zvals[i]) for a,f in zip(extra,fluxes,strict=True)]
                extra_gross=[a+f*F*abs(d(zvals[i])) for a,f in zip(extra_gross,gross,strict=True)]
                transfer=dt*sum(f*a for f,a in zip(fluxes,area,strict=True))
                cell_amount=sum((a-b)*vol for a,b,vol in zip(v["cell_mol_m3"][i],before_cell,volume,strict=True))
                effective=sum((a-b)*site_volume for a,b in zip(v["environment_mol_m3"][i],before_env,strict=True))
                conservative_amount=sum((a-b)*site_volume for a,b in zip(conservative,before_env,strict=True))
                book=dict(population=name,ion=ion,membrane_transfer_mol=transfer,cell_change_mol=cell_amount,
                    source_effective_environment_change_mol=effective,source_effective_balance_mol=cell_amount+effective,
                    conservative_environment_change_mol=conservative_amount,conservative_balance_mol=cell_amount+conservative_amount,
                    true_grid_environment_change_mol=sum((a-b)*vol for a,b,vol in zip(v["environment_mol_m3"][i],before_env,geom["true_environment_volume_m3"],strict=True)),
                    source_minus_conservative_environment_mol=effective-conservative_amount)
                books.append(book)
                routes.append(dict(ion_id=ion,relative_permeability=relative,DChan=diffusion,chan_flux=fluxes,
                    flux_gross=gross,sampled_bulk_at_membrane=sampled_mem,sampled_environment_at_membrane=sampled_env,
                    stored_membrane_before=before_mem,network_current=extra[:],network_current_gross=extra_gross[:],
                    cell_after=v["cell_mol_m3"][i][:],membrane_after=v["membrane_mol_m3"][i][:],environment_after=v["environment_mol_m3"][i][:],book=book))
            events.append(dict(name=name,class_name=cls,targets=targets,modulator=moddy,**updated,P=opening,routes=routes))
        return dict(events=events,values_after=copy.deepcopy(v),values_before=start,extra_current=extra,
            extra_current_gross=extra_gross,cell_gross_add=cell_add,membrane_gross_add=mem_add,
            environment_gross_add=env_add,voltage_nonce_count=nonce,amount_books=books,
            decimal_precision=context.prec,carried_reference_forms=0,fresh_conditional_reference=True,
            physical_global_conservation_credit=False,independent_constructor_credit=False)


def material_channel_inputs(inputs,packet,v):
    raw=inputs["definition"]
    return dict(material_declaration=raw,catalog=inputs["catalog"],values_before=v,
        cache_before=inputs["network_cache"],incoming_channel_current_A_m2=[0.0]*len(v["voltage_V"]),
        F=raw["environment_geometry_definition"]["current_definition"]["parameters"]["F_C_mol"],
        R=raw["parameters"]["R_J_mol_K"],membrane_thickness_m=raw["parameters"]["membrane_thickness_m"],
        dt_s=packet["dt_s"],runtime_temperature_K=packet["runtime_temperature_K"],rho_channel=packet["channel_multiplier"])
"""
# Add independent gate/modulation/ECM sequence next to independent CaATP equations.
pos = original.index("\ndef evaluate(")
text = original[:pos] + "\n" + imports + "\n" + kinetics + "\n" + channel_code + original[pos:]
text = text.replace(
    "def evaluate(inputs, *, refinement=1):\n",
    'def evaluate(inputs, *, refinement=1):\n    if inputs.get("mode")=="channels":\n        return serial(channel_sequence(inputs, refinement=refinement))\n',
)
text = text.replace(
    "    result = full.evaluate(inputs, refinement=refinement)",
    '    result = full.evaluate(inputs, refinement=refinement)\n    if inputs.get("mode")=="cold_initialization":\n        result["owner_fields"]["channels"]=inputs["catalog"]["populations"] is not None',
)
mark = '            observe("supplied_late_flux")\n            for i in moving:'
assert mark in text
text = text.replace(
    mark,
    '            observe("supplied_late_flux")\n            channel_result=channel_sequence(material_channel_inputs(inputs,packet,v),refinement=refinement,values=v)\n            for i in moving:',
)
text = text.replace(
    "                    conservative_exchange=conservative_exchange,",
    "                    conservative_exchange=conservative_exchange,\n                    channel_reference=channel_result,",
)
text = text.replace(
    "Independent native ECM CaATP, material, GRN and full-field conditionals.",
    "Independent ECM modern channels, CaATP, material, GRN and full-field conditionals.",
)
(folder / "betse_normal_ecm_catalog_join_reference.py").write_text(text)
print(
    "Wrote fresh100/160 independent scalar gate/modulation/ordered ECM channel and material conditionals"
)
