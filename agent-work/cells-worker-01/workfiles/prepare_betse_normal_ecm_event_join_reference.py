# ruff: noqa: E501
"""Initial exclusive source writer only; never import or evaluate reference science."""

from pathlib import Path

root = Path("/home/robert/Cells")
old = (root / "validation/betse/betse_normal_ecm_catalog_join_reference.py").read_text()
old = old.replace(
    "Independent ECM modern channels, CaATP, material, GRN and full-field conditionals.",
    "Independent supplied event, noise, catalog, CaATP and ECM field conditionals.",
)
old = old.replace("import json\n", "import json\nimport math\n", 1)
old = old.replace(
    "from decimal import Decimal, localcontext",
    "from decimal import ROUND_HALF_EVEN, Decimal, localcontext",
)
old = old.replace(
    'rho = d(inputs["rho_channel"][j])', 'rho = d(control_at(inputs["rho_channel"], j))'
)
start = old.index("            for key, count in (", old.index("def material_model"))
stop = old.index('            observe("reset_flux")', start)
old = (
    old[:start]
    + "            # Input is the actual post-event return of the single outer reset.\n"
    + old[stop:]
)
needle = "            for i in moving:\n                fm, fg = "
assert old.count(needle) == 1
old = old.replace(
    needle,
    """            noise_result = noise_equations(
                dict(definition=raw, noise=inputs["noise"], dt_s=packet_raw["dt_s"],
                     noise_cache_before=dict(present=False, value=None)),
                v, inputs["prospective_noise_uniforms"]
            )
            observe("protein_noise")
"""
    + needle,
)
old = old.replace(
    "                    channel_reference=channel_result,",
    "                    channel_reference=channel_result,\n                    noise_reference=noise_result,",
)
old = old.replace(
    "def evaluate(inputs, *, refinement=1):\n",
    """def evaluate(inputs, *, refinement=1):
    if inputs.get("mode") == "events":
        return event_equations(inputs, refinement=refinement)
    if inputs.get("mode") == "noise":
        with localcontext() as context:
            context.prec = 100 if refinement == 1 else 160
            before = numbers(inputs["before"])
            draws = inputs["draws"]
            uniforms = None if not draws else draws[0]["values"]
            result = noise_equations(inputs, before, uniforms)
            result.update(mode="noise", decimal_precision=context.prec,
                          carried_reference_forms=0, fresh_conditional_reference=True,
                          physical_global_conservation_credit=False)
            return serial(result)
    if inputs.get("conditioned_before_model_network"):
        # Preserve actual scalar snapshots; broadcast only at this equation consumer.
        adapted = copy.deepcopy(inputs)
        rho = adapted["rho_channel"]
        if not isinstance(rho, (tuple, list)):
            adapted["rho_channel"] = [rho] * len(adapted["values_before"]["voltage_V"])
        return full.evaluate(adapted, refinement=refinement)
""",
    1,
)
helpers = r"""

def control_at(value, j):
    return value[j] if isinstance(value, (tuple, list)) else value


def pulse_decimal(t, on, off, width):
    gain = Decimal(10) / d(width)
    return (1 / (1 + (-gain * (t - d(on))).exp())
            - 1 / (1 + (-gain * (t - d(off))).exp()))


def sine_decimal(value):
    # Independent precision follows the requested 100/160-digit form.
    with localcontext() as context:
        context.prec += 14
        tiny = Decimal(10) ** (-context.prec + 5)
        def atan_inverse(n):
            x = Decimal(1) / n
            term = total = x
            k = 1
            while True:
                term *= -(x*x)
                increment = term / (2*k + 1)
                total += increment
                if abs(increment) < tiny:
                    return total
                k += 1
        pi = 16 * atan_inverse(5) - 4 * atan_inverse(239)
        if abs(value) > 16384:
            raise ValueError("Independent trigonometric comparison phase is out of scope")
        x = value - (value/(2*pi)).to_integral_value(rounding=ROUND_HALF_EVEN)*(2*pi)
        term = total = x
        k = 1
        while True:
            term *= -x*x / ((2*k)*(2*k+1))
            total += term
            if abs(term) < tiny:
                return +total
            k += 1


def dynamic_decimal(record, t):
    if record["kind"] == "constant":
        return Decimal(1)
    # Source uses binary64 numpy.pi; do not replace an input constant by true pi.
    pi = d(math.pi)
    if record["kind"] == "periodic":
        phase = t*pi*d(record["frequency"]) + d(record["phase"])
    elif record["kind"] == "sweep":
        phase = pi*(d(record["slope"])*t + d(record["start"]))*t
    else:
        raise ValueError("Require an explicit supplied temporal callback")
    return sine_decimal(phase)**2


def assign_occurrences(target, indices, value):
    values = value if isinstance(value, list) else [value]*len(indices)
    if len(values) != len(indices):
        raise ValueError("Preserve native source assignment shape failure")
    for index, item in zip(indices, values, strict=True):
        target[index] = item


def event_equations(inputs, *, refinement=1):
    if refinement not in (1, 2):
        raise ValueError("Require the declared independent precision settings")
    with localcontext() as context:
        context.prec = 100 if refinement == 1 else 160
        owner, names = inputs["owner"], inputs["ion_ids"]
        def numeric(value):
            if isinstance(value, dict):
                return {key:numeric(item) for key,item in value.items()}
            if isinstance(value, (tuple,list)):
                return [numeric(item) for item in value]
            return d(value)
        stores = numeric(inputs["before"])
        t, h = d(inputs["source_time_s"]), owner["handler_fields"]
        stages = []
        def snap(stage):
            stages.append(dict(stage=stage,state=copy.deepcopy(stores)))
        config = {key:d(value) for key,value in owner["configured_environment"].items()}
        for role, suffix in (("K","Kenv"),("Cl","Clenv"),("Na","Naenv")):
            if owner["global_options"][role+"_env"] == 0:
                continue
            pulse = pulse_decimal(t,h["t_on_"+suffix],h["t_off_"+suffix],h["t_change_"+suffix])
            delta = d(h["mem_mult_"+suffix])*pulse*config[role]
            stores["c_env_bound"][names.index(role)] = config[role]+delta
            other = "Na" if role == "Cl" else "M"
            stores["c_env_bound"][names.index(other)] = config[other]+delta
        if owner["global_options"]["T_change"] != 0:
            stores["T"] = (d(inputs["configured_temperature_K"])
                *(1+d(h["multT"])*pulse_decimal(t,h["tonT"],h["toffT"],h["trampT"])))
        if owner["global_options"]["gj_block"] != 0:
            value = 1-pulse_decimal(t,h["tonGJ"],h["toffGJ"],h["trampGJ"])
            assign_occurrences(stores["gj_block"],h["targets_gj_block"],value)
        if owner["global_options"]["NaKATP_block"] != 0:
            stores["NaKATP_block"] = 1-pulse_decimal(t,h["tonNK"],h["toffNK"],h["trampNK"])
        snap("_fire_events_global")
        for role,suffix in (("Na","Namem"),("K","Kmem"),("Cl","Clmem"),("Ca","Camem"),("pressure","P")):
            key = role+"_mem" if role != "pressure" else role
            if owner["scheduled_options"][key] == 0:
                continue
            callback = owner["callbacks"][suffix]
            dynamic = dynamic_decimal(callback["dynamic"],t)
            if role == "pressure":
                gain = d(h["rate_P"])*dynamic*pulse_decimal(t,h["t_onP"],h["t_offP"],h["t_changeP"])
            else:
                gain = (d(h["mem_mult_"+suffix])*d(owner["tissue_default"]["Dm_"+role])
                    *dynamic*pulse_decimal(t,h["t_on_"+suffix],h["t_off_"+suffix],h["t_change_"+suffix]))
            scalar = numeric(callback["source_scalar"])
            value = [item*gain for item in scalar] if isinstance(scalar,list) else scalar*gain
            target = stores["P_mod"] if role == "pressure" else stores["Dm_scheduled"][names.index(role)]
            assign_occurrences(target,h["targets_"+suffix],value)
        if owner["scheduled_options"]["ecmJ"] != 0:
            eff = d(h["mult_ecmJ"])*pulse_decimal(t,h["t_on_ecmJ"],h["t_off_ecmJ"],h["t_change_ecmJ"])
            indices = h["targets_ecmJ"]
            for i in range(len(names)):
                values = [stores["D_env_base"][i][site]*(1-eff)+eff*stores["D_free"][i] for site in indices]
                assign_occurrences(stores["D_env"][i],indices,values)
            flat = [item for row in stores["D_env_weight"] for item in row]
            base = [item for row in stores["D_env_weight_base"] for item in row]
            assign_occurrences(flat,indices,[base[site]*(1-eff)+eff for site in indices])
            nx = len(stores["D_env_weight"][0])
            stores["D_env_weight"] = [flat[i:i+nx] for i in range(0,len(flat),nx)]
        voltage = owner["voltage"]
        if voltage is not None:
            value = d(voltage["peak_voltage"])*pulse_decimal(t,voltage["start_time_step"],voltage["stop_time_step"],voltage["time_step_rate"])
            stores["bound_V"][voltage["positive_voltage_boundary"]] = value
            stores["bound_V"][voltage["negative_voltage_boundary"]] = -value
        snap("_fire_events_tissue")
        stores["Dm_cells"] = [[a+b for a,b in zip(row,base,strict=True)] for row,base in zip(stores["Dm_scheduled"],stores["Dm_base"],strict=True)]
        stores["P_cells"] = [a+b for a,b in zip(stores["P_mod"],stores["P_base"],strict=True)]
        snap("makeAllChanges")
        reset = numbers(inputs["material_before"])
        for key in ("membrane_flux_mol_m2_s","junction_flux_mol_m2_s","environment_flux_x_mol_m2_s","environment_flux_y_mol_m2_s"):
            reset[key] = [[Decimal(0)]*len(row) for row in reset[key]]
        return serial(dict(mode="events",after=stores,stages=stages,reset_return=reset,
            decimal_precision=context.prec,carried_reference_forms=0,
            fresh_conditional_reference=True,physical_global_conservation_credit=False))


def noise_equations(inputs, values, uniforms):
    raw = inputs["definition"]
    ext = raw["environment_geometry_definition"]
    cg = ext["current_definition"]["geometry"]
    names = ext["current_definition"]["ions"]["ids"]
    before = copy.deepcopy(values)
    active = inputs["noise"]["enabled"] == 1 and "P" in names
    cached = copy.deepcopy(inputs["noise_cache_before"])
    if not active:
        if uniforms is not None:
            raise ValueError("Inactive original noise branch must have no draws")
        return dict(values_after=copy.deepcopy(values),cache_after=cached,flux=None,book=None)
    if uniforms is None or len(uniforms) != len(cg["owner"]):
        raise ValueError("Require the actual complete source-site uniform draw")
    geom = geometry(ext)
    i, dt = names.index("P"), d(inputs["dt_s"])
    level = d(inputs["noise"]["level_mol_m2_s"])
    fluxes = [level*(d(u)-Decimal("0.5")) for u in uniforms]
    area = list(map(d,cg["membrane_area_m2"]))
    volumes = list(map(d,ext["geometry"]["cell_volume_m3"]))
    owner, mapping = cg["owner"], geom["membrane_to_grid"]
    ev = d(ext["parameters"]["cell_height_m"])*geom["delta_m"]**2
    for cell, volume in enumerate(volumes):
        values["cell_mol_m3"][i][cell] += dt*sum((f*a for f,a,o in zip(fluxes,area,owner,strict=True) if o == cell),Decimal(0))/volume
    values["membrane_mol_m3"][i] = [values["cell_mol_m3"][i][cell] for cell in owner]
    for site in range(len(values["environment_mol_m3"][i])):
        positions = [j for j,k in enumerate(mapping) if k == site]
        if raw["parameters"]["fast_update_ecm"]:
            change = -fluxes[positions[-1]]*sum((area[j] for j in positions),Decimal(0)) if positions else Decimal(0)
        else:
            change = -sum((fluxes[j]*area[j] for j in positions),Decimal(0))
        values["environment_mol_m3"][i][site] += dt*change/ev
    dc = [a-b for a,b in zip(values["cell_mol_m3"][i],before["cell_mol_m3"][i],strict=True)]
    de = [a-b for a,b in zip(values["environment_mol_m3"][i],before["environment_mol_m3"][i],strict=True)]
    transfer = dt*sum((f*a for f,a in zip(fluxes,area,strict=True)),Decimal(0))
    cell_amount = sum((v*c for v,c in zip(volumes,dc,strict=True)),Decimal(0))
    effective = sum(de)*ev
    return dict(values_after=copy.deepcopy(values),flux=fluxes,
        cache_after=dict(present=True,value=fluxes[:]),book=dict(
        membrane_transfer_mol=transfer,cell_change_mol=cell_amount,
        source_effective_environment_change_mol=effective,
        source_effective_balance_mol=cell_amount+effective,
        conservative_environment_change_mol=-transfer,
        conservative_balance_mol=cell_amount-transfer,
        true_grid_environment_change_mol=sum((a*b for a,b in zip(de,geom["true_environment_volume_m3"],strict=True)),Decimal(0)),
        source_minus_conservative_environment_mol=effective+transfer))
"""
old = old.replace("\ndef native_parameters(", helpers + "\n\ndef native_parameters(", 1)
with (root / "validation/betse/betse_normal_ecm_event_join_reference.py").open("x") as stream:
    stream.write(old)
