# ruff: noqa: E501 -- source templates are formatted in their outputs.
"""Extend the frozen independent local reference with genuine GRN regulation."""

from pathlib import Path

ROOT = Path("/home/robert/Cells")
text = (ROOT / "validation/betse/betse_normal_molecule_join_reference.py").read_text()
text = text.replace(
    "def evaluate(inputs, *, refinement=1):", "def warm(inputs, *, refinement=1):", 1
)
needle = "        growth, growth_gross = {}, {}"
assert text.count(needle) == 1
text = text.replace(
    needle,
    """        cell_state = {name: list(map(d, values)) for name,values in zip(ions,inputs["values_before"]["cell_mol_m3"],strict=True)}
        cell_state.update(old_cell)
        configs={row["name"]:row for row in definition["grn_configuration"]["biomolecules"]}
"""
    + needle,
    1,
)
text = text.replace(
    "            for concentration in old_cell[name]:",
    "            for site,concentration in enumerate(old_cell[name]):",
)
text = text.replace(
    '                production = d(g["production_rate_mM_s"]) * factor',
    '                production = d(g["production_rate_mM_s"]) * factor * hill(configs[name]["growth and decay"],"",cell_state,site)',
)
text = text.replace(
    '                regulated = d(g["decay_max_per_s"]) * factor * concentration / scale',
    '                regulated = d(g["decay_max_per_s"]) * factor * concentration / scale * hill(configs[name]["growth and decay"],"decay ",cell_state,site)',
)
position = text.index("def warm(")
text = (
    text[:position]
    + """def hill(gad,prefix,state,site):
    if gad is None:
        return d(1)
    alpha=d(1)
    for activating,sign in ((True,"activators"),(False,"inhibitors")):
        names=gad.get(prefix+sign)
        if names is None:
            continue
        for name,km,power in zip(names,gad["Km "+prefix+sign],gad["n "+prefix+sign],strict=True):
            load=(state[name][site]/d(km))**d(power)
            alpha*=load/(1+load) if activating else 1/(1+load)
    return alpha


def cold(inputs,*,refinement=1):
    if refinement not in (1,2) or inputs["mode"]!="cold_initialization":
        raise ValueError("Require cold configuration inputs before owner construction")
    with localcontext() as context:
        context.prec=90 if refinement==1 else 140
        net=inputs["network"]
        cfg=net["grn_configuration"]
        n,m=inputs["cells"],inputs["membranes"]
        genes={}
        for row in cfg["biomolecules"]:
            gad=row["growth and decay"]
            fields=dict(Dm=d(row["Dm"]),Do=d(row["Do"]),Dgj=d(row.get("Dgj",1e-16)),z=d(row["z"]),ignore_ECM_pump=True,ignoreTJ=row["TJ permeable"],ignoreGJ=row["GJ impermeable"],TJ_factor=d(row["TJ factor"]),update_intra_conc=False,transmem=False,Mu_mem=d(0),u_mt=d(0),scale_factor=d(1),modify_time_factor=d(cfg.get("time dilation factor",1)) if row.get("use time dilation",False) else d(1),active_pumping=False,ion_channel_gating=False,change_bounds=False,cell_clamp=False,c_cells=[d(row["cell conc"])]*n,cc_at_mem=[d(row["cell conc"])]*m,c_env=[d(row["env conc"])]*m,flux_intra=[d(0)]*m,c_bound=d(row["env conc"]),simple_growth=gad is not None,gad_scale_factor=d(1) if gad is None else d(gad.get("scale factor",1)),r_production=None if gad is None else d(gad["production rate"]),r_decay=None if gad is None else d(gad["decay rate"]),growth_targets_cell=list(range(n)))
            if gad is not None:
                fields.update(growth_targets_mem=list(range(m)),decay_max=d(gad.get("decay max",0)))
            genes[row["name"]]=fields
        ids=inputs["ion_ids"]+[row["name"] for row in cfg["biomolecules"]]
        matrix=[[d(0)]*3 for _ in ids]
        matrix[ids.index("X")]=[d(1),d(0),d(-1)]
        matrix[ids.index("Y")]=[d(0),d(1),d(1)]
        return plain(dict(molecule_fields=genes,reaction_matrix=matrix,owner_fields=dict(reset_MT=False,recalc_fluid=False,reactions=True,transporters=False,channels=False,modulators=cfg.get("modulators") is not None),charge_has_been_balanced=True,decimal_precision=context.prec,carried_reference_forms=0,fresh_conditional_reference=True,cold_initialization=True,physical_conservation_credit=False))


"""
    + text[position:]
)
position = text.index("def main():")
text = (
    text[:position]
    + """def evaluate(inputs,*,refinement=1):
    if inputs.get("mode")=="cold_initialization":
        return cold(inputs,refinement=refinement)
    return warm(inputs,refinement=refinement)


"""
    + text[position:]
)
with (ROOT / "validation/betse/betse_normal_grn_join_reference.py").open("x") as stream:
    stream.write(text)
print("Created independent cold/Decimal regulated-GAD local reference; no evaluation")
