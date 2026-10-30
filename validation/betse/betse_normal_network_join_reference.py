"""Independent Decimal90/140 native feedback from actual pre-network inputs.

Only control factors/ordered writes are checked independently here. Chemistry
is explicitly empty, and upstream transport/voltage/trajectories are excluded.
The frozen standalone scalar alpha is reused with binary64 input conversion.
"""

from decimal import Decimal, localcontext


def d(value):
    return Decimal.from_float(float(value))


def _alpha(row, raw, site, *, channel=False):
    c, mapping = (raw["sample_mM"], raw["membrane_to_environment"])
    m, ids = (len(mapping), raw["species_ids"])
    tj = not channel and row["target"] == "TJ"
    regular, independent, inhibitor_total, running, direct = (d(1), d(0), d(0), d(1), [])
    for activating in (True, False):
        prefix = "activator" if activating else "inhibitor"
        label = ("channel " if channel else "") + prefix + "s"
        names = row.get(label)
        if names is None or names == "None" or names == []:
            continue
        tags = row.get(prefix + " zone")
        if tags is None or tags == "None" or tags == []:
            tags = ["cell"] * len(names)
        floors = row.get(prefix + " max") if channel else None
        floors = [0.0] * len(names) if floors is None else floors
        for name, km, n, tag, floor in zip(
            names, row[prefix + " Km"], row[prefix + " n"], tags, floors, strict=True
        ):
            star = name.endswith("*")
            name = name[:-1] if star else name
            special = name[-1] if name.endswith(("!", "&")) else ""
            name = name[:-1] if special else name
            constant = tj and tag == "cell"
            owner = m + site if tj else m + mapping[site] if tag == "env" else site
            value = d(1) if constant else d(c[ids.index(name)][owner])
            if special == "&":
                direct.append(value if activating or constant else -value)
                continue
            half = d(km)
            if channel and star:
                coefficient = d(raw["species_valence"][ids.index(name)]) * (
                    1 if tag == "env" else -1
                )
                half *= (
                    coefficient
                    * d(raw["voltage_V"][site])
                    * d(raw["faraday_C_mol"])
                    / (d(raw["gas_constant_J_mol_K"]) * d(raw["temperature_K"]))
                ).exp()
            load = (value / half) ** d(n)
            if activating:
                hill = d(1) if constant else load / (1 + load)
                if special == "!":
                    independent += hill
                else:
                    regular *= hill
            else:
                floor = d(0) if floor is None else d(floor)
                h = d(1) if constant else 1 / (1 + load)
                running *= (1 - floor) * h
                if floor != 0:
                    inhibitor_total += running
                    running = floor
    result = (regular + independent) * (inhibitor_total + running)
    return result * sum(direct, d(0)) if direct else result


def evaluate(inputs, *, refinement=1):
    if refinement not in (1, 2) or not inputs["conditioned_before_model_network"]:
        raise ValueError("Require actual pre-network conditions and declared refinement")
    definition = inputs["definition"]
    values = inputs["values_before"]
    names = inputs["ion_ids"]
    if definition["reactions"]:
        raise ValueError("Feedback reference cannot stand in for executed chemical reactions")
    with localcontext() as ctx:
        ctx.prec = 90 if refinement == 1 else 140
        m = len(values["voltage_V"])
        raw = dict(
            sample_mM=[
                a + b for a, b in zip(values["membrane_mol_m3"], values["bath_mol_m3"], strict=True)
            ],
            membrane_to_environment=definition["membrane_to_environment"],
            species_ids=names,
            species_valence=inputs["valence"],
            voltage_V=values["voltage_V"],
            faraday_C_mol=inputs["F"],
            gas_constant_J_mol_K=inputs["R"],
            temperature_K=inputs["runtime_temperature_K"],
        )
        controls = {name: [d(v) for v in row] for name, row in inputs["controls_before"].items()}
        writes = []
        for row in definition["modulators"]:
            applied = [d(row["max effect"]) * _alpha(row, raw, j) for j in range(m)]
            key = "gj_block" if row["target"] == "GJ" else "NaKATP_block"
            controls[key] = applied
            writes.append(
                dict(
                    rule_id=row["name"],
                    target=row["target"],
                    value=list(applied),
                    gj_block=list(controls["gj_block"]),
                    NaKATP_block=list(controls["NaKATP_block"]),
                )
            )

        def plain(value):
            if isinstance(value, Decimal):
                return float(value)
            if isinstance(value, dict):
                return {k: plain(v) for k, v in value.items()}
            if isinstance(value, list):
                return [plain(v) for v in value]
            return value

        return plain(
            dict(
                controls_after=controls,
                control_writes=writes,
                executed_chemistry=False,
                delta_conc=[0.0] * len(names),
                decimal_precision=ctx.prec,
                carried_reference_forms=0,
                conditional_actual_pre_network_only=True,
                no_upstream_or_trajectory_accuracy_claim=True,
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
            raise ImportError("Independent network import denied: " + name)
        return original(name, *rest, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError("Independent network import denied: " + fullname)

    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())
    result = evaluate(json.loads(args.inputs.read_text()), refinement=args.refinement)
    loaded = [name for name in sys.modules if name.split(".")[0] in blocked]
    assert not loaded
    result.update(
        production_imports_denied=True, loaded_production_modules=loaded, runtime=inventory()
    )
    with args.output.open("x") as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write("\n")


if __name__ == "__main__":
    main()
