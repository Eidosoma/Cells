"""Independent exact-binary-input preparation check using only the stdlib.

This reconstructs a declared initial packet, not a propagated trajectory.
The existing independent ER update reference remains a separate frozen input.
"""

import math
from decimal import Decimal, localcontext


def binary(value):
    return Decimal.from_float(float(value))


def plain(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    return value


def evaluate(inputs, *, refinement=1):
    if refinement not in (1, 2) or not inputs["conditioned_before_preparation"]:
        raise ValueError("Require raw conditions captured before preparation")
    with localcontext() as ctx:
        ctx.prec = 90 if refinement == 1 else 140
        names, cell_ids = inputs["ion_ids"], inputs["cell_ids"]
        count, n = len(names), len(cell_ids)
        ca, k = names.index("Ca"), names.index(inputs["recipe"]["counterion_id"])
        z = [binary(v) for v in inputs["valence"]]
        source = [[float(v) for v in row] for row in inputs["cytosol_mM"]]
        cytosol = [row[:] for row in source]
        er = [row[:] for row in source]
        er[ca] = [0.2] * n
        literal = [row[:] for row in er]
        # These are explicit binary64 primitive stores, as in the source
        # constructor. All following charge algebra uses exact stored inputs.
        volume = [0.1 * float(v) for v in inputs["cell_volume_m3"]]
        area = [1.0 * float(v) for v in inputs["cell_area_m2"]]
        cm = binary(inputs["capacitance_F_m2"])
        p = {key: binary(v) for key, v in inputs["parameters"].items()}
        R, F, T = p["R"], p["F"], binary(inputs["initial_temperature_K"])
        target_kind = inputs["recipe"]["target"]
        target = Decimal(0) if target_kind == "neutral" else R * T / (2 * F)
        if target_kind == "Ca_thermal_minus":
            target = -target
        densities, counterion_bounds, neutral = [], [], [row[:] for row in er]
        for j in range(n):
            rho = cm * binary(area[j]) * target / binary(volume[j])
            total_other = sum((z[i] * binary(er[i][j]) for i in range(count) if i != k), Decimal(0))
            neutral[k][j] = float(-total_other / z[k])
            er[k][j] = float((rho / F - total_other) / z[k])
            if target_kind != "neutral":
                transfer = binary(volume[j]) / binary(inputs["cell_volume_m3"][j]) * rho / F
                cytosol[k][j] = float(binary(source[k][j]) + transfer)
            densities.append(rho)
            counterion_bounds.append(abs(z[k] * F) * binary(math.ulp(er[k][j])) / 2)
        owners = inputs["owner_context"]
        selected = next(
            (
                name
                for name in ("molecules", "metabo", "grn")
                if owners[name]["present"] and owners[name]["contains_IP3"]
            ),
            None,
        )
        any_owner = any(row["present"] for row in owners.values())
        base = [[binary(1e-18) for _ in range(n)] for _ in names]
        channels = [row[:] for row in base]
        for j in range(n):
            activation = (binary(cytosol[ca][j]) / p["act_Km_Ca"]) ** p["act_n_Ca"]
            inhibition = (binary(cytosol[ca][j]) / p["inh_Km_Ca"]) ** p["inh_n_Ca"]
            value = activation / (1 + activation) / (1 + inhibition)
            if any_owner:
                ip3 = binary(owners[selected]["IP3_mM"][j]) if selected is not None else Decimal(0)
                hill = (ip3 / p["act_Km_IP3"]) ** p["act_n_IP3"]
                value *= hill / (1 + hill)
            channels[ca][j] = p["max_er"] * value
        diffusion = [[base[i][j] + channels[i][j] for j in range(n)] for i in range(count)]
        unit_roundoff = Decimal(2) ** -53

        def gamma(operations):
            return operations * unit_roundoff / (1 - operations * unit_roundoff)

        charge, voltage, charge_gross = [], [], []
        q_budget, v_budget, q_target_budget, v_target_budget = [], [], [], []
        for j in range(n):
            terms = [z[i] * F * binary(er[i][j]) for i in range(count)]
            q = sum(terms, Decimal(0))
            gross = sum(map(abs, terms), Decimal(0))
            factor = binary(volume[j]) / binary(area[j]) / cm
            v = q * factor
            qb = gamma(3 * count + 4) * gross + Decimal("1e-30")
            vb = abs(factor) * qb * (1 + gamma(6)) + gamma(6) * abs(v) + Decimal("1e-30")
            charge.append(q)
            voltage.append(v)
            charge_gross.append(gross)
            q_budget.append(qb)
            v_budget.append(vb)
            q_target_budget.append(qb + counterion_bounds[j])
            v_target_budget.append(vb + abs(factor) * counterion_bounds[j])
        cache_budget = [
            [
                gamma(128) * (abs(p["max_er"]) + abs(base[i][j]) + abs(channels[i][j]))
                + Decimal("1e-30")
                for j in range(n)
            ]
            for i in range(count)
        ]
        amount, source_amount, amount_budget, redistribution, redistribution_budget = (
            [],
            [],
            [],
            [],
            [],
        )
        for i in range(count):
            amounts, original, bounds, residual, transfer_bounds = [], [], [], [], []
            for j in range(n):
                a = binary(cytosol[i][j]) * binary(inputs["cell_volume_m3"][j])
                b = binary(er[i][j]) * binary(volume[j])
                old_a = binary(source[i][j]) * binary(inputs["cell_volume_m3"][j])
                old_b = binary(literal[i][j]) * binary(volume[j])
                neutral_b = binary(neutral[i][j]) * binary(volume[j])
                amounts.append(a + b)
                original.append(old_a + old_b)
                bounds.append(gamma(8) * (abs(a) + abs(b)) + Decimal("1e-40"))
                residual.append(a + b - old_a - neutral_b)
                transfer_bounds.append(
                    gamma(16) * (abs(a) + abs(b) + abs(old_a) + abs(neutral_b)) + Decimal("1e-40")
                )
            amount.append(amounts)
            source_amount.append(original)
            amount_budget.append(bounds)
            redistribution.append(residual)
            redistribution_budget.append(transfer_bounds)
        return plain(
            dict(
                fields=dict(
                    cc_er=er,
                    er_vol=volume,
                    er_sa=area,
                    cm_er=cm,
                    zer=[[v] * n for v in z],
                    Dm_er_base=base,
                    Dm_channels=channels,
                    Dm_er=diffusion,
                    Q=charge,
                    Ver=voltage,
                ),
                cytosol_mM=cytosol,
                requested_voltage_V=[target] * n,
                target_charge_density_C_m3=densities,
                ideal_target_voltage_decimal=[str(target)] * n,
                initial_amount_mol=amount,
                source_initial_amount_mol=source_amount,
                redistribution_residual_mol=redistribution,
                budgets=dict(
                    Q=q_budget,
                    Ver=v_budget,
                    target_Q=q_target_budget,
                    target_Ver=v_target_budget,
                    caches=cache_budget,
                    amounts=amount_budget,
                    redistribution=redistribution_budget,
                ),
                charge_gross_C_m3=charge_gross,
                selected_IP3_owner=selected,
                IP3_factor_enabled=any_owner,
                exact_binary_input=True,
                decimal_precision=ctx.prec,
                preparation_only=True,
                carried_reference_forms=0,
                roundoff_scope="Initial preparation only; no propagated trajectory allowance",
            )
        )


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
            raise ImportError("Independent preparation import denied: " + name)
        return original(name, *rest, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError("Independent preparation import denied: " + fullname)

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
