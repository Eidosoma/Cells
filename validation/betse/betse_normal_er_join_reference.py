"""Independent ER equations conditional on immutable actual pre-ER inputs.

No upstream CaATP/normal-prefix or carried-trajectory accuracy claim is made.
This module uses the Python standard library only.
"""

import copy
from decimal import Decimal, localcontext

from validation.betse.betse_normal_ion_join_reference import convert, d


def evaluate(inputs, *, refinement=1):
    if refinement not in (1, 2) or not inputs["conditioned_before_model_endoretic"]:
        raise ValueError("Require declared precision and actual pre-ER conditions")
    with localcontext() as ctx:
        ctx.prec = 90 if refinement == 1 else 140
        fields = convert(copy.deepcopy(inputs["er_state"]["fields"]), d)
        cell = convert(inputs["cytosol_mM"], d)
        cc_er = fields["cc_er"]
        gross_cell, gross_er = convert(cell, abs), convert(cc_er, abs)
        names = inputs["er_state"]["ion_ids"]
        ca = names.index("Ca")
        n = len(cell[ca])
        p = {key: d(value) for key, value in inputs["parameters"].items()}
        owners = inputs["owner_context"]
        selected = None
        for name in ("molecules", "metabo", "grn"):
            if owners[name]["present"] and owners[name]["contains_IP3"]:
                selected = name
                break
        any_owner = any(row["present"] for row in owners.values())
        ip3 = owners[selected]["IP3_mM"] if selected is not None else [0.0] * n
        for j in range(n):
            act = (cell[ca][j] / p["act_Km_Ca"]) ** p["act_n_Ca"]
            inh = (cell[ca][j] / p["inh_Km_Ca"]) ** p["inh_n_Ca"]
            mod = (act / (1 + act)) * (1 / (1 + inh))
            if any_owner:
                ip3_act = (d(ip3[j]) / p["act_Km_IP3"]) ** p["act_n_IP3"]
                mod *= ip3_act / (1 + ip3_act)
            fields["Dm_channels"][ca][j] = p["max_er"] * mod
        for i, row in enumerate(fields["Dm_er"]):
            for j in range(n):
                row[j] = fields["Dm_er_base"][i][j] + fields["Dm_channels"][i][j]
        R, F, T = p["R"], p["F"], d(inputs["runtime_temperature_K"])
        atp, adp, pi = p["cATP"], p["cADP"], p["cPi"]
        kmc, kma = p["KmCa_Ca"], p["KmCa_ATP"]
        flux, flux_gross, zero = [], [], []
        for j in range(n):
            qnum = adp * pi * cc_er[ca][j]
            qraw = atp * cell[ca][j]
            is_zero = float(inputs["parameters"]["cATP"]) * float(cell[ca][j]) == 0.0
            qden = d(1e-16) if is_zero else qraw
            if is_zero:
                zero.append(j)
            quotient = qnum / qden
            keq = (-p["deltaGATP"] / (R * T) - 2 * ((F * fields["Ver"][j]) / (R * T))).exp()
            forward = ((cell[ca][j] / kmc) * (atp / kma)) / (
                (1 + (cell[ca][j] / kmc)) * (1 + (atp / kma))
            )
            value = p["serca_max"] * forward * (1 - (quotient / keq))
            flux.append(value)
            flux_gross.append(abs(p["serca_max"] * forward) * (1 + abs(quotient / keq)))
        vol, er_vol, area = convert(inputs["cell_volume_m3"], d), fields["er_vol"], fields["er_sa"]
        dt = p["dt"]
        for j in range(n):
            a = flux[j] * (area[j] / vol[j]) * dt
            b = flux[j] * (area[j] / er_vol[j]) * dt
            cell[ca][j] -= a
            cc_er[ca][j] += b
            gross_cell[ca][j] += abs(a)
            gross_er[ca][j] += abs(b)
        # Each source electroflux call stores the nonce into binary64 Ver/z.
        # These are explicit primitive-store seams, not concentration floors.
        voltage_store = list(map(float, inputs["er_state"]["fields"]["Ver"]))
        ed_fluxes = []
        for i in inputs["moving_indices"]:
            row = []
            z = d(float(inputs["valence"][i]) + 1e-25)
            for j in range(n):
                voltage_store[j] += 1e-25
                alpha = (z * d(voltage_store[j]) * F) / (R * T)
                exponential = (-alpha).exp()
                denominator = 1 - exponential
                value = -((fields["Dm_er"][i][j] * alpha) / p["tm"]) * (
                    (cc_er[i][j] - cell[i][j] * exponential) / denominator
                )
                row.append(value)
                a = value * (area[j] / vol[j]) * dt
                b = value * (area[j] / er_vol[j]) * dt
                cell[i][j] -= a
                cc_er[i][j] += b
                gross_cell[i][j] += abs(a)
                gross_er[i][j] += abs(b)
            ed_fluxes.append(dict(ion_id=names[i], flux_mol_m2_s=row))
        charge_gross, voltage_gross = [], []
        for j in range(n):
            terms = [fields["zer"][i][j] * F * cc_er[i][j] for i in range(len(names))]
            fields["Q"][j] = sum(terms, Decimal(0))
            fields["Ver"][j] = (1 / fields["cm_er"]) * fields["Q"][j] * (er_vol[j] / area[j])
            charge_gross.append(sum(map(abs, terms), Decimal(0)))
            voltage_gross.append(charge_gross[-1] * er_vol[j] / area[j] / fields["cm_er"])
        result = dict(
            cytosol_mM=cell,
            fields=fields,
            serca_flux_mol_m2_s=flux,
            serca_flux_gross=flux_gross,
            electrofluxes=ed_fluxes,
            cytosol_gross=gross_cell,
            er_gross=gross_er,
            charge_gross=charge_gross,
            voltage_gross=voltage_gross,
            selected_IP3_owner=selected,
            IP3_factor_enabled=any_owner,
            zero_denominator_indices=zero,
            decimal_precision=ctx.prec,
            conditional_pre_endoretic_only=True,
            carried_reference_forms=0,
            no_upstream_or_trajectory_accuracy_claim=True,
        )
        return convert(result, lambda value: float(value) if isinstance(value, Decimal) else value)


def main():
    import argparse
    import builtins
    import importlib.abc
    import json
    import sys
    from pathlib import Path

    from validation.betse.betse_normal_channel_join_runtime import inventory

    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--refinement", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    blocked = {"cells", "betse", "numpy", "jax", "jaxlib"}
    original = builtins.__import__

    def guarded(name, *rest, **kwargs):
        if name.split(".")[0] in blocked:
            raise ImportError("Independent ER import denied: " + name)
        return original(name, *rest, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError("Independent ER import denied: " + fullname)

    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())
    result = evaluate(json.loads(args.inputs.read_text()), refinement=args.refinement)
    loaded = [name for name in sys.modules if name.split(".")[0] in blocked]
    assert not loaded
    result.update(
        production_imports_denied=True, loaded_production_modules=loaded, runtime=inventory()
    )
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
