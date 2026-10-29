"""Independent 80-digit Decimal factors and ordered source target assignments."""

from copy import deepcopy
from decimal import Decimal, localcontext


def d(value):
    return Decimal(str(value))


def alpha(row, raw, site, *, channel=False):
    c, mapping = raw["sample_mM"], raw["membrane_to_environment"]
    m, ids = len(mapping), raw["species_ids"]
    tj = not channel and row["target"] == "TJ"
    regular, independent, inhibitor_total, running, direct = d(1), d(0), d(0), d(1), []
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
            owner = m + site if tj else (m + mapping[site] if tag == "env" else site)
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


def evaluate(raw):
    with localcontext() as context:
        context.prec = 80
        m, e, ions = len(raw["membrane_to_environment"]), raw["environment_count"], raw["ion_ids"]
        rules, values, alpha_values, run = [*raw["modulators"], *raw["channels"]], [], [], []
        gj, nak, tj = (
            deepcopy(raw["initial_gj"]),
            deepcopy(raw["initial_nak"]),
            deepcopy(raw["initial_tj"]),
        )
        channels = [[0.0] * m for _ in rules]
        diffusivities = [[[0.0] * m for _ in rules] for _ in ions]
        for index, row in enumerate(rules):
            channel = index >= len(raw["modulators"])
            count = m if channel or row["target"] != "TJ" else e
            factors = [alpha(row, raw, site, channel=channel) for site in range(count)]
            alpha_values.append([float(v) for v in factors] + [0.0] * (max(m, e) - count))
            if not channel:
                factors = [v * d(row["max effect"]) for v in factors]
            values.append([float(v) for v in factors] + [0.0] * (max(m, e) - count))
            running = channel and not (
                raw["initialization"] and row.get("init active", True) is False
            )
            run.append(running)
            if channel:
                channels[index] = list(raw["initial_channel_modulator"])
                if running:
                    channels[index] = [float(v) for v in factors]
                    maximum = row.get("max conductivity")
                    maximum = row["max Dm"] if maximum is None else maximum
                    target = raw["channel_targets"].get(row["name"], [True] * m)
                    for i in range(len(ions)):
                        for site in range(m):
                            opening = d(raw["core_P"][site]) if target[site] else d(0)
                            diffusivities[i][index][site] = float(
                                opening
                                * d(raw["relative_permeability"][i])
                                * d(maximum)
                                * factors[site]
                            )
            elif row["target"] == "GJ":
                gj = [float(v) for v in factors]
            elif row["target"] == "Na/K-ATPase":
                nak = [float(v) for v in factors]
            else:
                target_ion = row.get("target ion")
                selected = (
                    range(len(ions)) if target_ion in (None, "None") else [ions.index(target_ion)]
                )
                for i in selected:
                    for site, chosen in enumerate(raw["tj_targets"]):
                        if chosen:
                            tj[i][site] = float(factors[site])
        return dict(
            factors=values,
            regulation=alpha_values,
            controls=dict(gj=gj, nak=nak, tj=tj, channel_modulator=channels),
            channel_run=run,
            diffusivity_m2_s=diffusivities,
        )
