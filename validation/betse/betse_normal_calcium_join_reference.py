"""Independent maintained-CaATP and rectangular post-handler equations.

Inputs are actual pre-handler float conditions recorded before the model CaATP
calculation. This is a conditional handler/commit check, not a full outer-parent
or trajectory error bound. Upstream ordering has separate exact native checks.
"""

import copy
from decimal import Decimal, localcontext

from validation.betse.betse_normal_current_reference import evaluate as current_equations
from validation.betse.betse_normal_ion_join_reference import convert, d
from validation.betse.betse_normal_voltage_reference import voltage_equations


def evaluate(inputs, *, refinement=1, postcommit=True):
    if refinement not in (1, 2):
        raise ValueError("Require declared precision")
    if not inputs.get("conditioned_before_model_calcium"):
        raise ValueError("Require pre-handler conditions before outgoing CaATP computation")
    phase = inputs["phase"]
    full = inputs["definition"]
    raw = full["ion_definition"]
    names = raw["ions"]["ids"]
    i = names.index("Ca")
    geometry = raw["geometry"]
    owner = geometry["owner"]
    n, m = len(geometry["cell_ids"]), len(owner)
    with localcontext() as ctx:
        ctx.prec = 90 if refinement == 1 else 140
        values = convert(phase["values_before"], d)
        gross = convert(values, abs)
        p = phase["parameters"]
        alpha = d(phase["alpha_Ca"])
        rate = convert(phase["rate_before"], d)
        arithmetic = None
        applied = [Decimal(0)] * m
        if alpha > 0:
            ci = [max(c, Decimal(0)) for c in values["membrane_mol_m3"][i]]
            co = [max(c, Decimal(0)) for c in values["bath_mol_m3"][i]]
            values["membrane_mol_m3"][i] = ci
            values["bath_mol_m3"][i] = co
            atp, adp, pi = (d(p[key]) for key in ("cATP", "cADP", "cPi"))
            F, R, T = d(p["F"]), d(p["R"]), d(phase["runtime_temperature_K"])
            kc, ka, dg = (d(p[key]) for key in ("KmCa_Ca", "KmCa_ATP", "deltaGATP"))
            arithmetic = {
                key: []
                for key in (
                    "quotient_numerator",
                    "quotient_denominator_raw",
                    "quotient_denominator_used",
                    "quotient",
                    "equilibrium",
                    "forward_numerator",
                    "forward_denominator",
                    "forward",
                    "backward_numerator_unused",
                    "backward_denominator_unused",
                    "backward_unused",
                    "raw_flux_mol_m2_s",
                )
            }
            zero = []
            rate = []
            for j in range(m):
                qnum = adp * pi * co[j]
                qraw = atp * ci[j]
                # Source branch uses the stored binary64 product; no Ca floor.
                raw_float = float(p["cATP"]) * float(ci[j])
                qden = d(1e-16) if raw_float == 0 else qraw
                if raw_float == 0:
                    zero.append(j)
                quotient = qnum / qden
                equilibrium = (-(dg / (R * T) - 2 * F * values["voltage_V"][j] / (R * T))).exp()
                fn = (ci[j] / kc) * (atp / ka)
                fd = (1 + ci[j] / kc) * (1 + atp / ka)
                forward = fn / fd
                bn = co[j] / kc
                bd = 1 + co[j] / kc
                backward = bn / bd
                flux = -alpha * forward * (1 - quotient / equilibrium)
                for key, value in zip(
                    arithmetic,
                    (
                        qnum,
                        qraw,
                        qden,
                        quotient,
                        equilibrium,
                        fn,
                        fd,
                        forward,
                        bn,
                        bd,
                        backward,
                        flux,
                    ),
                    strict=True,
                ):
                    arithmetic[key].append(value)
                masked = (
                    Decimal(0)
                    if not raw["parameters"]["cluster_open"] and geometry["boundary"][j]
                    else flux
                )
                rate.append(masked)
                applied[j] = d(phase["rho_pump"][j]) * masked
                values["membrane_flux_mol_m2_s"][i][j] += applied[j]
                gross["membrane_flux_mol_m2_s"][i][j] += abs(applied[j])
            arithmetic["zero_denominator_indices"] = zero
        handler_values = copy.deepcopy(values)
        output = dict(
            arithmetic=arithmetic,
            rate_after=rate,
            applied_flux_mol_m2_s=applied,
            handler_state=handler_values,
            source_rate_is_masked_raw_Ca_flux=True,
            block_used=False,
            met_used=False,
            formal_ATP_consumption_claim=False,
            conditional_on_actual_pre_handler_inputs=True,
            refinement=refinement,
            decimal_precision=ctx.prec,
        )
        if postcommit:
            if full["channel_definition"]["channels"]:
                raise ValueError(
                    "Post-handler conditional commit scope requires no late channel populations"
                )
            dt = d(phase["dt_s"])
            A = convert(geometry["membrane_area_m2"], d)
            vol = convert(geometry["cell_volume_m3"], d)
            env = d(raw["parameters"]["bath_volume_m3"])
            for name in raw["ions"]["moving_ids"]:
                k = names.index(name)
                fm, fg = values["membrane_flux_mol_m2_s"][k], values["junction_flux_mol_m2_s"][k]
                gm, gg = gross["membrane_flux_mol_m2_s"][k], gross["junction_flux_mol_m2_s"][k]
                rows = [[j for j, a in enumerate(owner) if a == cell] for cell in range(n)]
                for cell, row in enumerate(rows):
                    values["cell_mol_m3"][k][cell] += (
                        dt * sum(fm[j] * A[j] for j in row) / vol[cell]
                    )
                    gross["cell_mol_m3"][k][cell] += dt * sum(gm[j] * A[j] for j in row) / vol[cell]
                values["membrane_mol_m3"][k] = [values["cell_mol_m3"][k][a] for a in owner]
                gross["membrane_mol_m3"][k] = [gross["cell_mol_m3"][k][a] for a in owner]
                mean = (
                    sum(values["bath_mol_m3"][k]) - dt * sum(fm[j] * A[j] for j in range(m)) / env
                ) / m
                bound = (
                    sum(gross["bath_mol_m3"][k]) + dt * sum(gm[j] * A[j] for j in range(m)) / env
                ) / m
                values["bath_mol_m3"][k] = [mean] * m
                gross["bath_mol_m3"][k] = [bound] * m
                for cell, row in enumerate(rows):
                    values["cell_mol_m3"][k][cell] -= (
                        dt * sum(fg[j] * A[j] for j in row) / vol[cell]
                    )
                    gross["cell_mol_m3"][k][cell] += dt * sum(gg[j] * A[j] for j in row) / vol[cell]
                    values["cell_mol_m3"][k][cell] = max(values["cell_mol_m3"][k][cell], Decimal(0))
            forcing = inputs["drive"]
            published = forcing["channels"]["substances_affect_charge"]
            extra_q = [0.0] * n if published else forcing["extra_charge_C_m3"]
            extra_j = [0.0] * m if published else forcing["extra_current_A_m2"]
            state = convert(values, float)
            scales = convert(gross, float)
            current_input = dict(
                cell_mol_m3=state["cell_mol_m3"],
                membrane_flux_mol_m2_s=state["membrane_flux_mol_m2_s"],
                junction_flux_mol_m2_s=state["junction_flux_mol_m2_s"],
                extra_charge_C_m3=extra_q,
                extra_current_A_m2=extra_j,
            )
            current = current_equations(
                full["current_definition"], current_input, refinement=refinement
            )
            gross_input = dict(
                cell_mol_m3=scales["cell_mol_m3"],
                membrane_flux_mol_m2_s=scales["membrane_flux_mol_m2_s"],
                junction_flux_mol_m2_s=scales["junction_flux_mol_m2_s"],
                extra_charge_C_m3=list(map(abs, extra_q)),
                extra_current_A_m2=list(map(abs, extra_j)),
            )
            current["gross"] = current_equations(
                full["current_definition"], gross_input, refinement=refinement
            )["gross"]
            voltage = voltage_equations(full, state, current, forcing, refinement, scales)
            output.update(
                material_state=state,
                material_gross=scales,
                current=current,
                voltage=voltage,
                postcommit_conditional_only=True,
                no_upstream_prefix_accuracy_claim=True,
            )
        return convert(output, lambda x: float(x) if isinstance(x, Decimal) else x)


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
    parser.add_argument("--kernel-only", action="store_true")
    args = parser.parse_args()
    blocked = {"cells", "betse", "numpy", "jax", "jaxlib"}
    original = builtins.__import__

    def guarded(name, *rest, **kwargs):
        if name.split(".")[0] in blocked:
            raise ImportError("Independent calcium import denied: " + name)
        return original(name, *rest, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError("Independent calcium import denied: " + fullname)

    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())
    result = evaluate(
        json.loads(args.inputs.read_text()),
        refinement=args.refinement,
        postcommit=not args.kernel_only,
    )
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
