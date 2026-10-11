"""Independent SI Decimal reconstruction from raw saved fields, without model helpers.

The original comparator is not imported. Kinetics use exponential odds; the
native update uses a dimensionless implicit-Euler ratio; GHK uses exp(VF/RT).
Geometry, inventory, capacitor and current reductions are performed here.
"""

import math
from decimal import Decimal, localcontext

BACKENDS = ("numpy", "jax_eager", "jax_jit")
STAGES = ("before", "after_channel", "after_network", "after_ordinary", "after_voltage")
FMOL = Decimal("1e-15")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def d(value):
    require(type(value) in (int, float, Decimal), "Non-numeric independent input")
    result = value if isinstance(value, Decimal) else Decimal(str(value))
    require(result.is_finite(), "Nonfinite independent input")
    return result


def product(values, factor):
    return (
        [product(v, factor) for v in values] if isinstance(values, list) else d(values) * d(factor)
    )


def total(values):
    return sum((d(v) for v in values), Decimal(0))


def zero(values):
    if isinstance(values, list):
        for value in values:
            zero(value)
    else:
        require(d(values) == 0, "Nonzero inactive inventory/transfer")


def uniform(values):
    require(isinstance(values, list) and bool(values), "Empty bath/face selection")
    first = d(values[0])
    require(all(d(v) == first for v in values), "Nonuniform bath or within-cell state")
    return first


def by_cell(values, geometry):
    owners = geometry["membrane_owners"]
    n = geometry["cell_count"]
    require(len(values) == len(owners), "Face shape changed")
    require(set(owners) == set(range(n)), "Invalid membrane owner coverage")
    return [
        uniform([v for v, owner in zip(values, owners, strict=True) if owner == i])
        for i in range(n)
    ]


def integrated_faces(density, geometry):
    require(len(density) == geometry["membrane_count"], "Density shape changed")
    owners, areas = geometry["membrane_owners"], geometry["membrane_areas_m2"]
    return [
        total(
            [
                d(rate) * d(area)
                for rate, area, owner in zip(density, areas, owners, strict=True)
                if owner == i
            ]
        )
        for i in range(geometry["cell_count"])
    ]


def kinetics(voltage):
    v = d(voltage)
    odds = (
        ((v + Decimal("0.006")) / Decimal("0.0064")).exp(),
        (-(v + Decimal("0.0253")) / Decimal("0.0035")).exp(),
    )
    targets = [value / (1 + value) for value in odds]
    times = [Decimal("0.008330") - Decimal("0.1163") * v, Decimal("1.620") - Decimal("15.5") * v]
    require(all(value > 0 for value in times), "Invalid gate time constant")
    return targets, times


def native_step(gates, targets, times, step):
    return [
        (d(q) + d(step) / tau * inf) / (1 + d(step) / tau)
        for q, inf, tau in zip(gates, targets, times, strict=True)
    ]


def inward_density(voltage, inside, outside, permeability, protocol):
    f, gas = (d(protocol["constants"][key]) for key in ("F", "R"))
    x = d(voltage) * f / (gas * d(protocol["temperature_K"]))
    if x == 0:
        drive = d(outside) - d(inside)
    else:
        exponential = x.exp()
        drive = x * (d(outside) - d(inside) * exponential) / (exponential - 1)
    return d(permeability) * drive


def normalized(actual, expected, unit, tolerances):
    a, e = d(actual), d(expected)
    denominator = d(tolerances[unit]) + d(tolerances["relative"]) * abs(e)
    require(denominator > 0, "Nonpositive audit tolerance")
    return float(abs(a - e) / denominator)


class Ledger:
    def __init__(self, tolerances):
        self.tolerances, self.rows = tolerances, {}

    def add(self, name, actual, expected, unit):
        if isinstance(expected, list):
            require(
                isinstance(actual, list) and len(actual) == len(expected), f"Wrong shape: {name}"
            )
            for i, (a, e) in enumerate(zip(actual, expected, strict=True)):
                self.add(f"{name}/{i}", a, e, unit)
            return
        require(name not in self.rows, "Duplicate independent comparison")
        error = normalized(actual, expected, unit, self.tolerances)
        self.rows[name] = {
            "id": name,
            "actual": float(d(actual)),
            "expected": float(d(expected)),
            "unit": unit,
            "scaled_error": error,
            "passed": error <= 1,
        }


def native_case(protocol, base, variant, fixture, geometry, row, ledger):
    p, g, before = protocol, geometry, row["before"]
    n, m = g["cell_count"], g["membrane_count"]
    dt, f = d(p["dt_s"]), d(p["constants"]["F"])
    volumes = [d(v) / FMOL for v in g["cell_volumes_m3"]]
    bath = d(g["effective_bath_volume_m3"]) / FMOL
    z = base["expected_valence"]
    add = lambda label, a, e, unit: ledger.add(row["id"] + "/native/" + label, a, e, unit)  # noqa: E731
    require(
        g["effective_bath_volume_m3"] == m * g["configured_bath_volume_m3"],
        "Bath normalization changed",
    )
    require(all(v > 0 for v in volumes + [bath]), "Nonpositive compartment volume")
    for region, size, profile in (("inside_mM", n, "inside_mM"), ("outside_mM", m, "outside_mM")):
        add(
            "profile/" + region,
            row["core_initial"][region],
            [[v] * size for v in base[profile]],
            "concentration_mM",
        )
        require(
            before[region] == row["core_initial"][region],
            "Network initialization changed chemistry",
        )
    densities = [Decimal(0)] * m
    if variant["channel"]:
        init, pre, post = (
            row[key] for key in ("initialized_channel", "channel_before", "channel_after")
        )
        for channel in (init, pre, post):
            for key in ("m", "h"):
                by_cell(channel[key], g)
                require(all(0 <= d(q) <= 1 for q in channel[key]), "Gate outside unit interval")
        require(init["P"] is None and pre["P"] is None, "Invented native initial open probability")
        for face, owner in enumerate(g["membrane_owners"]):
            initial_targets, _ = kinetics(
                row["core_initial"]["gate_initialization_voltage_V"][face]
            )
            add(f"init/{face}", [init["m"][face], init["h"][face]], initial_targets, "gate")
            pair = initial_targets if fixture["gate"] is None else fixture["gate"]
            add(f"before_gate/{face}", [pre["m"][face], pre["h"][face]], pair, "gate")
            target, tau = kinetics(before["voltage_V"][face])
            updated = native_step([pre["m"][face], pre["h"][face]], target, tau, dt)
            add(f"post_gate/{face}", [post["m"][face], post["h"][face]], updated, "gate")
            for label, channel in (("init", init), ("before", pre), ("after", post)):
                add(
                    f"{label}_derived/{face}",
                    channel["derived_m_times_h"][face],
                    d(channel["m"][face]) * d(channel["h"][face]),
                    "gate",
                )
            opened = d(post["m"][face]) * d(post["h"][face])
            permeability = (
                opened
                * d(p["max_permeability_m_per_s"])
                * d(p["abundance"])
                * d(variant["permeability_fraction"])
            )
            add(f"open/{face}", post["P"][face], opened, "gate")
            add(
                f"diffusivity/{face}",
                post["DChan_m2_per_s"][face],
                permeability * d(p["thickness_m"]),
                "diffusivity_m2_per_s",
            )
            densities[face] = inward_density(
                before["voltage_V"][face],
                before["inside_mM"][1][owner],
                uniform(before["outside_mM"][1]),
                permeability,
                p,
            )
        add("density", post["density_mol_per_m2_s"], densities, "density_mol_per_m2_s")
        densities = post["density_mol_per_m2_s"]
    flux = product(integrated_faces(densities, g), 1 / FMOL)
    current = product(densities, -f)
    add(
        "network_current",
        row["network_current_density_A_per_m2"],
        current,
        "current_density_A_per_m2",
    )
    add(
        "pre_export_current",
        row["after_channel"]["extra_current_density_A_per_m2"],
        [0] * m,
        "current_density_A_per_m2",
    )
    for name in STAGES:
        stage = row[name]
        by_cell(stage["voltage_V"], g)
        for field in (
            "ordinary_density_mol_per_m2_s",
            "junction_density_mol_per_m2_s",
            "extra_rho_cells_C_per_m3",
            "extra_rho_env_C_per_m3",
            "boundary_voltage_V",
        ):
            zero(stage[field])
        if name in STAGES[2:]:
            add(
                name + "/extra_current",
                stage["extra_current_density_A_per_m2"],
                current,
                "current_density_A_per_m2",
            )
        for species in range(6):
            out = uniform(stage["outside_mM"][species])
            initial_out = uniform(before["outside_mM"][species])
            change = dt if species == 1 and name != "before" else Decimal(0)
            expected = [
                d(v) + change * rate / volume
                for v, rate, volume in zip(before["inside_mM"][species], flux, volumes, strict=True)
            ]
            add(
                f"{name}/membrane_concentration/{species}",
                stage["at_membrane_mM"][species],
                [stage["inside_mM"][species][i] for i in g["membrane_owners"]],
                "concentration_mM",
            )
            add(
                f"{name}/inside/{species}",
                stage["inside_mM"][species],
                expected,
                "concentration_mM",
            )
            add(
                f"{name}/outside/{species}",
                out,
                initial_out - total(flux) * change / bath,
                "concentration_mM",
            )
            residual = (
                total(
                    [
                        (d(v) - d(old)) * volume
                        for v, old, volume in zip(
                            stage["inside_mM"][species],
                            before["inside_mM"][species],
                            volumes,
                            strict=True,
                        )
                    ]
                )
                + (out - initial_out) * bath
            )
            add(f"{name}/species_conservation/{species}", residual, 0, "amount_fmol")
        if name in ("before", "after_voltage"):
            rho = [
                f * total([d(z[s]) * d(stage["inside_mM"][s][i]) for s in range(6)])
                for i in range(n)
            ]
            add(name + "/rho", stage["rho_C_per_m3"], rho, "charge_density_C_per_m3")
            volts = [
                r * d(v) / (d(a) * d(g["specific_capacitance_F_per_m2"]))
                for r, v, a in zip(rho, g["cell_volumes_m3"], g["cell_areas_m2"], strict=True)
            ]
            add(name + "/charge_voltage", by_cell(stage["voltage_V"], g), volts, "voltage_V")
    for name in ("after_network", "after_ordinary"):
        for region in ("inside_mM", "outside_mM"):
            add(
                name + "/no_second_transfer/" + region,
                row[name][region],
                row["after_channel"][region],
                "concentration_mM",
            )
    final = row["after_voltage"]

    def charge(stage):
        return (
            f
            * FMOL
            * total(
                [
                    d(z[s])
                    * (
                        total(
                            [
                                d(v) * volume
                                for v, volume in zip(stage["inside_mM"][s], volumes, strict=True)
                            ]
                        )
                        + uniform(stage["outside_mM"][s]) * bath
                    )
                    for s in range(6)
                ]
            )
        )

    add("global_charge_change", charge(final), charge(before), "charge_C")
    add("Jmem", final["Jmem_A_per_m2"], current, "current_density_A_per_m2")
    average = [
        rate / d(area)
        for rate, area in zip(integrated_faces(current, g), g["cell_areas_m2"], strict=True)
    ]
    smoothed = [
        d(a) * j + d(b) * average[owner]
        for a, b, j, owner in zip(
            row["smooth_weight_mem"],
            row["smooth_weight_other"],
            current,
            g["membrane_owners"],
            strict=True,
        )
    ]
    add("Jn", final["Jn_A_per_m2"], smoothed, "current_density_A_per_m2")
    add(
        "I_mem",
        final["I_mem_A"],
        [-j * d(a) for j, a in zip(smoothed, g["membrane_areas_m2"], strict=True)],
        "current_A",
    )
    add(
        "delta_voltage",
        [
            v - old
            for v, old in zip(
                by_cell(final["voltage_V"], g), by_cell(before["voltage_V"], g), strict=True
            )
        ],
        [
            rate * dt * f * FMOL / (d(a) * d(g["specific_capacitance_F_per_m2"]))
            for rate, a in zip(flux, g["cell_areas_m2"], strict=True)
        ],
        "voltage_V",
    )
    if not variant["permeability_fraction"]:
        zero(densities)
    else:
        require(all(d(value) < 0 for value in densities), "Active potassium flow sign changed")
    return flux


def cells_case(p, base, variant, g, native, result, backend, native_flux, ledger):
    add = lambda label, a, e, unit: ledger.add(  # noqa: E731
        native["id"] + "/" + backend + "/" + label, a, e, unit
    )
    before, final = native["before"], native["after_voltage"]
    n, count = g["cell_count"], g["cell_count"] if variant["channel"] else 0
    dt, f = d(p["dt_s"]), d(p["constants"]["F"])
    voltage = by_cell(before["voltage_V"], g)
    add("before_voltage", result["before_voltage_V"], voltage + [0], "voltage_V")
    add(
        "after_voltage",
        result["after_voltage_V"],
        by_cell(final["voltage_V"], g) + [0],
        "voltage_V",
    )
    cr, rhs, after = (result[key] for key in ("channel_readouts", "rhs", "after"))
    gate = [by_cell(native["channel_after"][key], g) for key in ("m", "h")] if count else [[], []]
    targets, times, rates = [[], []], [[], []], [[], []]
    opened, effective, flux = [], [], []
    for i in range(count):
        inf, tau = kinetics(voltage[i])
        for k in range(2):
            targets[k].append(inf[k])
            times[k].append(tau[k])
            rates[k].append((inf[k] - gate[k][i]) / tau[k])
        opened.append(gate[0][i] * gate[1][i])
        permeability = (
            opened[-1]
            * d(p["max_permeability_m_per_s"])
            * d(p["abundance"])
            * d(variant["permeability_fraction"])
        )
        effective.append(permeability)
        density = inward_density(
            voltage[i], before["inside_mM"][1][i], uniform(before["outside_mM"][1]), permeability, p
        )
        flux.append(density * d(g["cell_areas_m2"][i]) / FMOL)
    for key, expected, unit in (
        ("gate_inf", targets, "gate"),
        ("gate_tau_s", times, "tau_s"),
        ("gate_rate_per_s", rates, "gate_rate_per_s"),
        ("open_probability", opened, "gate"),
        ("effective_permeability_m_per_s", effective, "permeability_m_per_s"),
        ("flux_fmol_per_s", flux, "flux_fmol_per_s"),
    ):
        padding = [0] * (10 - count)
        padded = [v + padding for v in expected] if key.startswith("gate_") else expected + padding
        add(key, cr[key], padded, unit)
    matched = [[float(v) for v in q] + [0] * (10 - count) for q in gate]
    require(
        result["matched_gate"] == matched and after["gate"] == matched,
        "Gate averaged or advanced twice",
    )
    add("rhs_channel_ledger", rhs["channel_transferred"], cr["flux_fmol_per_s"], "flux_fmol_per_s")
    add("rhs_gate", rhs["gate"], cr["gate_rate_per_s"], "gate_rate_per_s")
    add(
        "cross_engine_flux",
        cr["flux_fmol_per_s"][:n] if count else [0] * n,
        native_flux,
        "flux_fmol_per_s",
    )
    for species in range(3):
        expected = (flux if species == 1 and count else [Decimal(0)] * n) + [0]
        add(f"rhs_inside/{species}", rhs["amount_increment"][species], expected, "flux_fmol_per_s")
        add(
            f"rhs_outside/{species}",
            rhs["extracellular_amount_increment"][species],
            [-total(expected), 0],
            "flux_fmol_per_s",
        )
        inside = [
            d(c) * d(v) / FMOL
            for c, v in zip(final["inside_mM"][species], g["cell_volumes_m3"], strict=True)
        ] + [0]
        outside = [
            uniform(final["outside_mM"][species]) * d(g["effective_bath_volume_m3"]) / FMOL,
            0,
        ]
        add(
            f"after_inside/{species}",
            result["after_inside_amount_fmol"][species],
            inside,
            "amount_fmol",
        )
        add(
            f"after_outside/{species}",
            result["after_outside_amount_fmol"][species],
            outside,
            "amount_fmol",
        )
        add(
            f"material/{species}",
            total(
                after["amount_increment"][species]
                + after["extracellular_amount_increment"][species]
            ),
            0,
            "amount_fmol",
        )
    for name, unit in (
        ("amount_increment", "amount_fmol"),
        ("extracellular_amount_increment", "amount_fmol"),
        ("channel_transferred", "amount_fmol"),
        ("dissipated_energy_pJ", "energy_pJ"),
    ):
        zero(result["initial_state"][name])
        add("single_transfer/" + name, after[name], product(rhs[name], dt), unit)
    add("countercharge", result["countercharge_C"], 0, "charge_C")
    add(
        "inward_current",
        product(rhs["amount_increment"][1][:n], f * FMOL),
        product(integrated_faces(native["network_current_density_A_per_m2"], g), -1),
        "current_A",
    )
    charge = [
        f * FMOL * total([d(base["expected_valence"][s]) * total(after[key][s]) for s in range(3)])
        for key in ("amount_increment", "extracellular_amount_increment")
    ]
    add("outside_countercharge", charge[1], -charge[0], "charge_C")


def definition_contract(definition, p, base, variant, g, row):
    """Independently check dimensioned mapping, not equality to the old compiler."""
    model = definition["model"]
    require(
        model["id"] == "finite_extracellular@1" and model["junctions"] == [], "Wrong mapped family"
    )
    require(model["temperature_K"] == p["temperature_K"], "Mapped temperature changed")
    ids = base["mobile_species"]
    require(
        model["species"]
        == [{"id": name, "valence": base["expected_valence"][i]} for i, name in enumerate(ids)],
        "Mapped species changed",
    )
    require(len(model["cells"]) == g["cell_count"], "Mapped cell coverage changed")
    volumes = [d(v) / FMOL for v in g["cell_volumes_m3"]]
    bath = model["extracellular"]
    require(
        math.isclose(
            bath["volume_pL"], float(d(g["effective_bath_volume_m3"]) / FMOL), rel_tol=1e-13
        ),
        "Mapped bath volume changed",
    )
    for i, entry in enumerate(model["cells"]):
        cell, membrane = entry["cell"], entry["membrane"]
        require(
            cell["id"] == f"cell_{i}"
            and membrane["id"] == f"membrane_{i}"
            and membrane["inside"] == cell["id"]
            and membrane["outside"] == bath["id"],
            "Mapped endpoint ownership changed",
        )
        require(
            math.isclose(cell["volume_pL"], float(volumes[i]), rel_tol=1e-13),
            "Mapped cell volume changed",
        )
        require(
            membrane["area_m2"] == g["cell_areas_m2"][i]
            and membrane["specific_capacitance_F_per_m2"] == g["specific_capacitance_F_per_m2"],
            "Mapped capacitor changed",
        )
        require(
            membrane["pump"] is None
            and membrane["passive"]["permeability_m_per_s"] == dict.fromkeys(ids, 0),
            "Unexpected background transport",
        )
        for s, name in enumerate(ids):
            target = d(row["before"]["inside_mM"][s][i]) * volumes[i]
            require(
                normalized(
                    cell["initial_amount_fmol"][name], target, "amount_fmol", p["tolerances"]
                )
                <= 1,
                "Mapped inside inventory changed",
            )
        fixed = total(
            [
                d(base["expected_valence"][s]) * d(row["before"]["inside_mM"][s][i]) * volumes[i]
                for s in range(3, 6)
            ]
        )
        require(
            normalized(cell["fixed_charge_equivalent_fmol"], fixed, "amount_fmol", p["tolerances"])
            <= 1,
            "Mapped immobile charge changed",
        )
        require(
            cell["initial_voltage_V"] == row["before"]["voltage_V"][g["membrane_owners"].index(i)],
            "Mapped voltage reanchored",
        )
        require(
            "channel" in entry and (entry["channel"] is not None) is variant["channel"],
            "Mapped channel presence changed",
        )
        if variant["channel"]:
            channel = entry["channel"]
            require(
                channel["id"] == f"channel_{i}"
                and channel["membrane_id"] == membrane["id"]
                and channel["species_id"] == "K"
                and channel["kinetic_law"] == "betse_kv1p5_mh@1",
                "Mapped channel identity changed",
            )
            require(
                channel["max_permeability_m_per_s"]
                == p["max_permeability_m_per_s"] * variant["permeability_fraction"]
                and channel["abundance"] == p["abundance"],
                "Mapped channel scale changed",
            )
            for key in ("m", "h"):
                require(
                    d(channel["initial_gate"][key]) == by_cell(row["channel_before"][key], g)[i],
                    "Mapped hidden gate changed",
                )
    volume = d(g["effective_bath_volume_m3"]) / FMOL
    for s, name in enumerate(ids):
        require(
            normalized(
                bath["initial_amount_fmol"][name],
                uniform(row["before"]["outside_mM"][s]) * volume,
                "amount_fmol",
                p["tolerances"],
            )
            <= 1,
            "Mapped outside inventory changed",
        )
    fixed = total(
        [
            d(base["expected_valence"][s]) * uniform(row["before"]["outside_mM"][s]) * volume
            for s in range(3, 6)
        ]
    )
    require(
        normalized(bath["fixed_charge_equivalent_fmol"], fixed, "amount_fmol", p["tolerances"])
        <= 1,
        "Mapped bath fixed charge changed",
    )


def rebuild(registration, native, cells):
    p, base = registration["protocol"], registration["base_protocol"]
    ledger = Ledger(p["tolerances"])
    with localcontext() as context:
        context.prec = 80
        for variant in p["variants"]:
            geometry = native["preparations"][variant["id"]]["geometry"]
            for fixture in p["states"]:
                key = f"{variant['id']}/{fixture['id']}"
                row = native["rows"][key]
                definition_contract(cells["definitions"][key], p, base, variant, geometry, row)
                flux = native_case(p, base, variant, fixture, geometry, row, ledger)
                for backend in BACKENDS:
                    cells_case(
                        p,
                        base,
                        variant,
                        geometry,
                        row,
                        cells["results"][backend][key],
                        backend,
                        flux,
                        ledger,
                    )
        hidden = []
        for variant in ("blocked_channel", "active_channel"):
            a, b = (native["rows"][variant + "/prescribed_mh_" + suffix] for suffix in ("a", "b"))
            ledger.add(
                variant + "/equal_initial_open",
                a["channel_before"]["derived_m_times_h"],
                b["channel_before"]["derived_m_times_h"],
                "gate",
            )
            difference = max(
                abs(d(x) - d(y))
                for x, y in zip(a["channel_after"]["P"], b["channel_after"]["P"], strict=True)
            )
            require(difference > Decimal("1e-6"), "Distinct hidden gate states collapsed")
            hidden.append(
                {
                    "variant": variant,
                    "post_update_open_fraction_difference": float(difference),
                    "initial_pairs_are_prescribed_not_reconstructed_histories": True,
                }
            )
    return {
        "comparisons": list(ledger.rows.values()),
        "distinct_hidden_state_controls": hidden,
        "definition_contracts_checked": 12,
        "precision_digits": 80,
    }


def reconcile(rebuilt, saved, tolerances):
    actual = {row["id"]: row for row in rebuilt["comparisons"]}
    original = {row["id"]: row for row in saved["comparisons"]}
    require(
        len(actual)
        == len(rebuilt["comparisons"])
        == len(original)
        == len(saved["comparisons"])
        == 37068
        and set(actual) == set(original),
        "Independent/saved comparison coverage differs",
    )
    failed = []
    with localcontext() as context:
        context.prec = 80
        for name, row in actual.items():
            old = original[name]
            require(row["unit"] == old["unit"], "Independent/saved units differ")
            errors = [row["scaled_error"]] + [
                normalized(old[key], row[key], row["unit"], tolerances)
                for key in ("actual", "expected")
            ]
            if max(errors) > 1 or old["passed"] is not True:
                failed.append(
                    {
                        "id": name,
                        "independent_error": errors[0],
                        "saved_actual_error": errors[1],
                        "saved_expected_error": errors[2],
                    }
                )
        for row, old in zip(
            rebuilt["distinct_hidden_state_controls"],
            saved["distinct_hidden_state_controls"],
            strict=True,
        ):
            require(
                row["variant"] == old["variant"]
                and old["initial_pairs_are_prescribed_not_reconstructed_histories"] is True,
                "Hidden-state control identity differs",
            )
            require(
                normalized(
                    row["post_update_open_fraction_difference"],
                    old["post_update_open_fraction_difference"],
                    "gate",
                    tolerances,
                )
                <= 1,
                "Hidden-state difference differs",
            )
    return {
        "independent_comparisons": len(actual),
        "failed_comparisons": len(failed),
        "failures": failed,
        "maximum_independent_scaled_error": max(row["scaled_error"] for row in actual.values()),
        "definition_contracts_checked": rebuilt["definition_contracts_checked"],
        "hidden_state_controls_checked": 2,
        "precision_digits": 80,
    }
