"""Independent 80-digit Decimal local native network and amount oracle.

Only stdlib imports; dictionary/list loops intentionally differ from production
arrays. Reversible zone formulas and literal per-item Q conversion are explicit.
"""

from decimal import Decimal, localcontext


def d(value):
    return Decimal(str(value))


def linear_growth_exact(raw, duration_s):
    """Closed form for unregulated constant cell production/decay only."""
    with localcontext() as context:
        context.prec = 80
        assert not raw["reactions"] and len(raw["growth"]) == 1
        row = raw["growth"][0]
        gad = row["growth and decay"]
        assert all(
            gad.get(key) in (None, "None")
            for key in ("activators", "inhibitors", "decay activators", "decay inhibitors")
        )
        time = d(raw["time_dilation"]) if row.get("use time dilation", False) else d(1)
        decay = (
            time
            * (d(gad["decay rate"]) + d(gad.get("decay max", 0.0)))
            / d(gad.get("scale factor", 1.0))
        )
        assert decay > 0
        cells = [i for i, zone in enumerate(raw["compartment_zones"]) if zone == "cell"]
        initial = [
            d(raw["concentration_mM"][raw["species_ids"].index(row["name"])][i]) for i in cells
        ]
        mod = raw["growth_modulation"].get(row["name"], [1.0] * len(cells))
        steady = [d(gad["production rate"]) * time * d(v) / decay for v in mod]
        final = [
            eq + (start - eq) * (-decay * d(duration_s)).exp()
            for eq, start in zip(steady, initial, strict=True)
        ]
        return dict(
            tau_s=float(1 / decay),
            steady_mM=[float(v) for v in steady],
            concentration_mM=[float(v) for v in final],
        )


def regulation(config, field, owner, zone, c, mapping, ids):
    regular, independent, inhibitor, direct = d(1), d(0), d(1), []
    for activating in (True, False):
        if field == "reaction":
            prefix = "activator" if activating else "inhibitor"
            label, keys = (
                "reaction " + prefix + "s",
                (prefix + " Km", prefix + " n", prefix + " zone"),
            )
        else:
            label = ("decay " if field == "decay" else "") + (
                "activators" if activating else "inhibitors"
            )
            keys = ("Km " + label, "n " + label, "zone " + label)
        names = config.get(label)
        if names is None or names == "None" or names == []:
            continue
        tags = config.get(keys[2])
        if tags is None or tags == "None" or tags == []:
            tags = ["cell"] * len(names)
        for name, km, exponent, tag in zip(
            names, config[keys[0]], config[keys[1]], tags, strict=True
        ):
            name = name[:-1] if name.endswith("*") else name
            special = name[-1] if name.endswith(("!", "&")) else ""
            name = name[:-1] if special else name
            constant = zone == "env" and tag == "cell"
            sample_owner = mapping[owner] if zone == "cell" and tag == "env" else owner
            value = d(1) if constant else c[ids.index(name)][sample_owner]
            if special == "&":
                direct.append(value if activating or constant else -value)
                continue
            loading = (value / d(km)) ** d(exponent)
            if activating:
                hill = d(1) if constant else loading / (1 + loading)
                if special == "!":
                    independent += hill
                else:
                    regular *= hill
            else:
                inhibitor *= d(1) if constant else 1 / (1 + loading)
    result = (regular + independent) * inhibitor
    return result * sum(direct, d(0)) if direct else result


def evaluate(raw):
    with localcontext() as context:
        context.prec = 80
        ids, zones = raw["species_ids"], raw["compartment_zones"]
        c = [[d(v) for v in row] for row in raw["concentration_mM"]]
        volumes = [d(v) for v in raw["volume_m3"]]
        mapping = {int(k): int(v) for k, v in raw["cell_to_environment"].items()}
        rt = d(raw["temperature_K"]) * d(raw["gas_constant_J_mol_K"])
        records, changes, growth_changes = (
            [],
            [[d(0)] * len(zones) for _ in ids],
            [[d(0)] * len(zones) for _ in ids],
        )
        cells = [i for i, zone in enumerate(zones) if zone == "cell"]
        matrices = {zone: [[] for _ in ids] for zone in ("cell", "mit", "env")}
        # Native growth identity columns precede cell reaction columns, even
        # when molecule insertion order differs from the concentration dictionary.
        for row in raw["growth"]:
            species = ids.index(row["name"])
            for i in range(len(ids)):
                matrices["cell"][i].append(1.0 if i == species else 0.0)
            gad = row.get("growth and decay")
            enabled = gad is not None and gad != "None"
            for j, owner in enumerate(cells):
                alpha = (
                    regulation(gad, "growth", owner, "cell", c, mapping, ids) if enabled else d(0)
                )
                time = d(raw["time_dilation"]) if row.get("use time dilation", False) else d(1)
                scale = d(gad.get("scale factor", 1.0)) if enabled else d(1)
                concentration = c[species][owner] / scale
                mod = d(raw["growth_modulation"].get(row["name"], [1.0] * len(cells))[j])
                production = d(gad["production rate"]) * time * mod * alpha if enabled else d(0)
                basal = d(gad["decay rate"]) * time * concentration if enabled else d(0)
                regulated = (
                    d(gad.get("decay max", 0.0))
                    * time
                    * concentration
                    * regulation(gad, "decay", owner, "cell", c, mapping, ids)
                    if enabled
                    else d(0)
                )
                targeted = (
                    enabled and raw["growth_targets"].get(row["name"], [True] * len(cells))[j]
                )
                rate = production - basal - regulated if targeted else d(0)
                extent = rate * volumes[owner] / d("1e-15")
                changes[species][owner] += extent
                growth_changes[species][owner] += extent
                records.append(
                    dict(
                        name=row["name"],
                        kind="growth",
                        owner=owner,
                        concentration_rate_mM_s=float(rate),
                        extent_fmol_s=float(extent),
                        forward_saturation=0.0,
                        backward_saturation=0.0,
                        regulation=float(alpha) if enabled else 1.0,
                        log_source_quotient=0.0,
                        production_mM_s=float(production) if targeted else 0.0,
                        basal_decay_mM_s=float(basal) if targeted else 0.0,
                        regulated_decay_mM_s=float(regulated) if targeted else 0.0,
                        growth_optimization_alpha=float(alpha),
                        decay_optimization_mM_s=float(basal),
                    )
                )
        for zone in ("cell", "mit", "env"):
            for row in raw["reactions"]:
                if row["reaction zone"] != zone:
                    continue
                stoich = [d(0)] * len(ids)
                for sign, key, coeff in (
                    (-1, "reactants", "reactant multipliers"),
                    (1, "products", "product multipliers"),
                ):
                    for s, n in zip(row[key], row[coeff], strict=True):
                        stoich[ids.index(s)] += sign * d(n)
                for i in range(len(ids)):
                    matrices[zone][i].append(float(stoich[i]))
                for owner, owner_zone in enumerate(zones):
                    if owner_zone != zone:
                        continue
                    quotient, forward, backward = d(1), d(1), d(1)
                    for product, key, coeff, kmkey in (
                        (False, "reactants", "reactant multipliers", "Km reactants"),
                        (True, "products", "product multipliers", "Km products"),
                    ):
                        saturation = d(1)
                        for s, n, km in zip(row[key], row[coeff], row[kmkey], strict=True):
                            value, power = c[ids.index(s)][owner], d(n)
                            if value <= 0:
                                raise ValueError(
                                    "Strictly positive participating substrate required"
                                )
                            literal = d(".001") * value**power
                            quotient = quotient * literal if product else quotient / literal
                            load = (value / d(km)) ** power
                            saturation *= load / (1 + load)
                        if product:
                            backward = saturation
                        else:
                            forward = saturation
                    alpha = regulation(row, "reaction", owner, zone, c, mapping, ids)
                    reversible = row["standard free energy"] != "None"
                    qkeq = (
                        quotient * (d(row["standard free energy"]) / rt).exp()
                        if reversible
                        else d(0)
                    )
                    if not reversible:
                        factor = forward
                    elif zone == "cell":
                        factor = 1 - qkeq
                    elif zone == "mit":
                        factor = forward - qkeq * backward
                    else:
                        factor = forward * (1 - qkeq)
                    rate = d(row["max rate"]) * alpha * factor
                    extent = rate * volumes[owner] / d("1e-15")
                    for i, nu in enumerate(stoich):
                        changes[i][owner] += nu * extent
                    records.append(
                        dict(
                            name=row["name"],
                            kind=zone,
                            owner=owner,
                            concentration_rate_mM_s=float(rate),
                            extent_fmol_s=float(extent),
                            forward_saturation=float(forward),
                            backward_saturation=float(backward),
                            regulation=float(alpha),
                            log_source_quotient=float(quotient.ln()),
                            production_mM_s=0.0,
                            basal_decay_mM_s=0.0,
                            regulated_decay_mM_s=0.0,
                            growth_optimization_alpha=0.0,
                            decay_optimization_mM_s=0.0,
                        )
                    )

        def convert(array):
            return [[float(v) for v in row] for row in array]

        return dict(
            routes=records,
            matrices=matrices,
            amount_fmol_s=convert(changes),
            growth_source_sink_fmol_s=convert(growth_changes),
            reaction_conversion_fmol_s=convert(
                [
                    [v - g for v, g in zip(row, gr, strict=True)]
                    for row, gr in zip(changes, growth_changes, strict=True)
                ]
            ),
        )
