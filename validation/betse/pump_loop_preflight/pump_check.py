"""Producer-side lifecycle checks, not the later independent saved-data audit."""

import math

import pump_context as ctx

c = ctx.c


def flat(value):
    if isinstance(value, list):
        for v in value:
            yield from flat(v)
    else:
        yield value


def near(actual, expected, atol, rtol):
    a, b = list(flat(actual)), list(flat(expected))
    c.require(len(a) == len(b), "Comparison extent")
    c.require(all(math.isfinite(v) for v in a + b), "Nonfinite comparison")
    c.require(
        all(abs(x - y) <= atol + rtol * abs(y) for x, y in zip(a, b, strict=True)),
        "Native transfer mismatch",
    )


def masked(values, variant, boundaries):
    return [
        0.0 if not variant["cluster_open"] and i in boundaries else v for i, v in enumerate(values)
    ]


def check_row(plan, variant, row):
    g, trace = row["geometry"], row["trace"]
    c.require(
        row["dt_s"] == plan["dt_s"] and row["steps"] == plan["steps"] and row["phase"] == "INIT",
        "Run clock",
    )
    c.require(g["cell_count"] == 7 and g["membrane_count"] == 30, "Run geometry")
    c.require(
        row["fixture_hook"] == dict(calls=1, returns=1) and row["hook_restored"],
        "Fixture lifecycle",
    )
    c.require(
        row["fixture"]["before"]["physical"] == row["fixture"]["after"]["physical"],
        "State-changing fixture",
    )
    settings = row["settings"]
    c.require(
        settings["solver"] == "FULL"
        and settings["cluster_open"] == variant["cluster_open"]
        and settings["alpha_NaK"] == (plan["alpha_mol_per_m2_s"] if variant["pump"] else 0),
        "Solver/pump preparation",
    )
    c.require(
        settings["constants"] == plan["constants"]
        and settings["temperature_K"] == plan["temperature_K"]
        and settings["pump_parameters"] == plan["pump_parameters"],
        "Constants/chemistry preparation",
    )
    c.require(
        all(
            settings[k] == 0
            for k in (
                "is_ecm",
                "cell_polarizability",
                "alpha_Ca",
                "Ca_dyn",
                "molecules_enabled",
                "grn_enabled",
                "fluid_flow",
                "deformation",
                "deform_osmo",
                "dynamic_noise",
                "channel_noise_level",
                "v_sensitive_gj",
                "gj_surface",
            )
        ),
        "Undeclared physics",
    )
    if trace is None:
        return []
    c.require(len(trace["steps"]) == len(trace["raw_steps"]) == plan["steps"], "Trace extent")
    c.require(
        all(v == 1 for v in trace["calls"].values())
        and trace["inflight_calls"] == 0
        and trace["hook_restored"],
        "Incomplete trace",
    )
    ns, nm = len(row["metadata"]["species"]), g["membrane_count"]
    tol = plan["tolerances"]
    summaries = []
    for index, (step, raw) in enumerate(zip(trace["steps"], trace["raw_steps"], strict=True)):
        c.require(
            step["index"] == raw["index"] == index
            and step["before_elapsed_s"] == index * plan["dt_s"]
            and step["after_elapsed_s"] == (index + 1) * plan["dt_s"],
            "Elapsed chronology",
        )
        c.require(
            step["order"] == ["before_ordinary", "after_ordinary", "after_voltage"],
            "Lifecycle order",
        )
        before, after = (step[k]["physical"] for k in ("before_ordinary", "after_ordinary"))
        c.require(
            all(v == 0 for v in flat(before["junction_density_mol_per_m2_s"])),
            "Junction transport active",
        )
        density = [[0.0] * nm for _ in range(ns)]
        pump = [call for call in raw["calls"] if call["function"] == "pumpNaKATP"]
        passive = [call for call in raw["calls"] if call["function"] == "electroflux"]
        c.require(
            len(pump) == int(variant["pump"])
            and [v["species_index"] for v in passive] == row["moving_ions"],
            "Call coverage",
        )
        cycles = [0.0] * nm
        if pump:
            sodium, potassium, reported = pump[0]["returned"]
            near(
                potassium,
                [-2 * v / 3 for v in sodium],
                tol["density_mol_per_m2_s"],
                tol["relative"],
            )
            near(reported, [-v for v in sodium], tol["density_mol_per_m2_s"], tol["relative"])
            for species, values in (
                (row["sodium_index"], sodium),
                (row["potassium_index"], potassium),
            ):
                density[species] = masked(
                    [variant["rho_pump"] * v for v in values], variant, g["boundary_faces"]
                )
            cycles = [-v / 3 for v in density[row["sodium_index"]]]
            c.require(
                step["before_ordinary"]["reported_NaK_rate"] == reported,
                "Raw pump diagnostic was transformed",
            )
        else:
            c.require(
                all(v == 0 for v in step["before_ordinary"]["reported_NaK_rate"]),
                "Disabled pump rate",
            )
        for call in passive:
            species = call["species_index"]
            for face, value in enumerate(masked(call["returned"], variant, g["boundary_faces"])):
                density[species][face] += value
        near(
            before["ordinary_density_mol_per_m2_s"],
            density,
            tol["density_mol_per_m2_s"],
            tol["relative"],
        )
        for species in range(ns):
            transfer = [
                v * area * plan["dt_s"]
                for v, area in zip(density[species], g["membrane_areas_m2"], strict=True)
            ]
            expected_inside = [
                initial
                + math.fsum(
                    v for v, owner in zip(transfer, g["membrane_owners"], strict=True) if owner == i
                )
                / volume
                for i, (initial, volume) in enumerate(
                    zip(before["inside_mM"][species], g["cell_volumes_m3"], strict=True)
                )
            ]
            expected_outside = [
                v - math.fsum(transfer) / g["effective_bath_volume_m3"]
                for v in before["outside_mM"][species]
            ]
            near(
                after["inside_mM"][species],
                expected_inside,
                tol["concentration_mM"],
                tol["relative"],
            )
            near(
                after["outside_mM"][species],
                expected_outside,
                tol["concentration_mM"],
                tol["relative"],
            )
            c.require(
                all(v > 0 for v in after["inside_mM"][species] + after["outside_mM"][species]),
                "Nonpositive native chemistry",
            )
        summaries.append(
            dict(
                index=index,
                elapsed_s=(index + 1) * plan["dt_s"],
                actual_pump_cycles_fmol=math.fsum(
                    v * a for v, a in zip(cycles, g["membrane_areas_m2"], strict=True)
                )
                * plan["dt_s"]
                * 1e15,
                raw_rate_is_atp=False,
            )
        )
    return summaries


def compare(r, packet):
    plan, rows = r["protocol"], packet["rows"]
    c.require(
        set(rows) == {v["id"] + "/" + mode for v in plan["variants"] for mode in plan["modes"]},
        "Native row coverage",
    )
    records = {}
    for variant in plan["variants"]:
        observed, quiet = (rows[variant["id"] + "/" + m] for m in plan["modes"])
        for row in (observed, quiet):
            c.require(row["id"] == variant["id"], "Variant identity")
            records[variant["id"] + "/" + row["mode"]] = check_row(plan, variant, row)
        for key in (
            "settings",
            "geometry",
            "source_constants",
            "fixture",
            "final",
            "final_arrays",
            "histories",
            "metadata",
        ):
            c.require(observed[key] == quiet[key], "Observer changed native output: " + key)
    return dict(
        status="native_lifecycle_checks_pass_pending_review",
        native_runs=len(rows),
        observed_steps=sum(map(len, records.values())),
        observer_pairs=len(plan["variants"]),
        records=records,
        coupled_cells_betse_qualified=False,
        biology_validated=False,
        energy_convergence_qualified=False,
        automatic_followup=False,
    )
