"""Independent saved-state arithmetic for the explicitly seven-cell comparison."""

import math

import alignment as a
import cluster_alignment as cluster
import contact as c


def check(registration, native, local):
    protocol, base, g = registration["protocol"], registration["base_protocol"], native["geometry"]
    n, m = protocol["cell_count"], protocol["membrane_face_count"]
    tolerances, rows = protocol["tolerances"], []
    maxima = {"voltage_V": 0.0, "flux_fmol_per_s": 0.0, "material_residual_fmol": 0.0}

    def compare(label, actual, expected, unit):
        score = c.normalized_error(actual, expected, tolerances[unit], tolerances["relative"])
        rows.append(
            {
                "id": label,
                "actual": actual,
                "expected": expected,
                "normalized_error": score,
                "pass": score <= 1,
            }
        )

    def matrix(value, outer, inner):
        c.require(
            len(value) == outer and all(len(row) == inner for row in value), "Array shape differs"
        )
        c.require(
            all(type(v) in (int, float) and math.isfinite(v) for row in value for v in row),
            "Nonfinite/nonnumeric array",
        )

    c.require(
        n == g["cell_count"] == 7 and m == g["membrane_count"] == 30,
        "Not the registered seven-cell fixture",
    )
    c.require(
        {key: g[key] for key in cluster.GEOMETRY_FIELDS} == registration["expected_geometry"],
        "Geometry correspondence differs",
    )
    vi = [v / 1e-15 for v in g["cell_volumes_m3"]]
    vo = g["effective_bath_volume_m3"] / 1e-15
    areas, owners, zs = g["membrane_areas_m2"], g["membrane_owners"], base["expected_valence"]
    c.require(
        set(owners) == set(range(n)) and len(owners) == len(areas) == m,
        "Membrane ownership differs",
    )
    c.require(
        g["specific_capacitance_F_per_m2"] == 0.01 and g["grid_shape"] == [10, 10],
        "Native geometry settings differ",
    )
    c.require(
        g["effective_bath_volume_m3"] == m * g["configured_bath_volume_m3"],
        "Bath normalization differs",
    )
    c.require(
        math.isclose(g["configured_bath_volume_m3"], 0.001 * 0.00015**2 * 0.00001, rel_tol=1e-14),
        "Configured bath volume differs",
    )
    c.require(
        all(math.isfinite(v) and v > 0 for v in [*vi, vo, *areas, *g["cell_areas_m2"]]),
        "Invalid geometry",
    )
    caps = [area * g["specific_capacitance_F_per_m2"] for area in g["cell_areas_m2"]]
    for i in range(n):
        c.require(
            math.isclose(
                math.fsum(area for area, owner in zip(areas, owners, strict=True) if owner == i),
                g["cell_areas_m2"][i],
                rel_tol=1e-13,
            ),
            "Cell area does not own its faces",
        )
        c.require(
            math.isclose(
                g["diviterm_m"][i], g["cell_volumes_m3"][i] / g["cell_areas_m2"][i], rel_tol=1e-13
            ),
            "Charge geometry differs",
        )
    expected_settings = {
        "is_ecm": False,
        "cell_polarizability": 0.0,
        "cluster_open": True,
        "alpha_NaK": 0.0,
        "alpha_Ca": 0.0,
        "Ca_dyn": False,
        "molecules_enabled": False,
        "grn_enabled": False,
        "fluid_flow": False,
        "deformation": False,
        "deform_osmo": False,
        "dynamic_noise": False,
        "channel_noise_level": 0.0,
        "v_sensitive_gj": False,
        "gj_surface": 0.0,
        "solver": "FULL",
        "temperature_K": 310.15,
    }
    c.require(native["settings"] == expected_settings, "Native mechanism switches differ")
    c.require(
        native["engine"] == "native_betse_seven_cell_prescribed_updates"
        and local["engine"] == "unchanged_cells_finite_extracellular_rhs",
        "Wrong engines",
    )
    c.require(
        native["trajectory_run"] is local["trajectory_run"] is False, "Wrong trajectory scope"
    )
    c.require(
        local["device"] == "cpu"
        and local["x64_enabled"] is True
        and local["jit_disabled"] is False,
        "Wrong Cells execution",
    )
    for record in (native, local):
        c.require(
            all(
                w["category"] not in protocol["forbidden_warning_categories"]
                for w in record["warnings"]
            ),
            "Numerical runtime warning",
        )
    mapped = cluster.definition(base, protocol, g)
    c.require(local["definition"] == mapped, "Cells base definition differs")
    c.require(
        local["probe_definitions"]
        == {
            case["id"]: cluster.probe_definition(mapped, case, protocol, base, g)
            for case in protocol["cases"]
        },
        "Cells preparation mapping differs",
    )
    c.require(
        set(native["profiles"]) == set(base["profiles"])
        and set(local["results"]) == set(c.CELLS_BACKENDS),
        "Context coverage differs",
    )
    ids = [case["id"] for case in protocol["cases"]]
    for values in local["results"].values():
        c.require([v["id"] for v in values] == ids, "Cells case coverage differs")
    volume_mismatch_witnesses = []

    def flux_rates(density):
        matrix(density, 6, m)
        return [
            [
                math.fsum(density[s][j] * areas[j] for j, owner in enumerate(owners) if owner == i)
                / 1e-15
                for i in range(n)
            ]
            for s in range(6)
        ]

    def state(label, saved, delta, constants, density=None):
        matrix(saved["inside_mM"], 6, n)
        matrix(saved["outside_mM"], 6, m)
        c.require(
            len(saved["voltage_V"]) == len(saved["inward_current_A"]) == m
            and len(saved["rho_C_per_m3"]) == n,
            "Native readout shape differs",
        )
        c.require(
            len(saved["boundary_voltage_V"]) == 100
            and all(v == 0 for v in saved["boundary_voltage_V"]),
            "Boundary voltage differs",
        )
        for s in range(6):
            for i in range(n):
                ci = base["inside_mM"][s] + delta[s][i] / vi[i]
                c.require(ci > 0, "Invalid intracellular concentration")
                compare(f"{label}/ci/{s}/{i}", saved["inside_mM"][s][i], ci, "concentration_mM")
            co = base["outside_mM"][s] - math.fsum(delta[s]) / vo
            c.require(co > 0, "Invalid outside concentration")
            for j in range(m):
                compare(f"{label}/co/{s}/{j}", saved["outside_mM"][s][j], co, "concentration_mM")
        voltages = []
        rates = flux_rates(density) if density is not None else [[0.0] * n for _ in range(6)]
        for i in range(n):
            q = constants["F"] * 1e-15 * math.fsum(z * delta[s][i] for s, z in enumerate(zs))
            v = q / caps[i]
            voltages.append(v)
            compare(
                f"{label}/rho/{i}",
                saved["rho_C_per_m3"][i],
                q / g["cell_volumes_m3"][i],
                "charge_density_C_per_m3",
            )
            for j, owner in enumerate(owners):
                if owner == i:
                    compare(f"{label}/voltage/{j}", saved["voltage_V"][j], v, "voltage_V")
            current = math.fsum(
                saved["inward_current_A"][j] for j, owner in enumerate(owners) if owner == i
            )
            expected = constants["F"] * 1e-15 * math.fsum(z * rates[s][i] for s, z in enumerate(zs))
            compare(f"{label}/cell_current/{i}", current, expected, "current_A")
        return voltages

    for profile_id, profile in native["profiles"].items():
        constants = base["profiles"][profile_id]
        c.require(
            profile["constants"] == constants and profile["dt_s"] == base["dt_s"],
            "Constants/dt differ",
        )
        c.require(
            profile["species"] == base["expected_species"] and profile["valence"] == zs,
            "Ion table differs",
        )
        matrix(profile["permeability_m_per_s"], 6, m)
        for s in range(6):
            c.require(
                all(
                    math.isclose(p, base["permeability_m_per_s"][s], rel_tol=2e-15, abs_tol=0)
                    for p in profile["permeability_m_per_s"][s]
                ),
                "Permeability differs",
            )
        c.require(
            [r["id"] for r in profile["cases"]] == ids
            and [r["id"] for r in profile["footprints"]] == protocol["footprints"],
            "Native case coverage differs",
        )
        state(f"{profile_id}/initial", profile["initial"], [[0.0] * n for _ in range(6)], constants)
        for k, (case, saved) in enumerate(zip(protocol["cases"], profile["cases"], strict=True)):
            label = f"{profile_id}/{case['id']}"
            delta = cluster.transfers(case, protocol) + [[0.0] * n for _ in range(3)]
            voltage = state(label + "/before", saved["before"], delta, constants)
            density = saved["density_mol_per_m2_s"]
            rates = flux_rates(density)
            matrix(saved["junction_density_mol_per_m2_s"], 6, m)
            c.require(
                all(v == 0 for row in saved["junction_density_mol_per_m2_s"] for v in row),
                "Disabled junction transported",
            )
            for s in range(6):
                if s >= 3 or case["leak_multiplier"] == 0:
                    c.require(
                        all(v == 0 for v in density[s]), "Blocked or auxiliary route transported"
                    )
                for j, owner in enumerate(owners):
                    point = {
                        "inside_mM": saved["before"]["inside_mM"][s][owner],
                        "outside_mM": saved["before"]["outside_mM"][s][j],
                        "valence": zs[s],
                        "voltage_V": saved["before"]["voltage_V"][j],
                        "temperature_K": 310.15,
                        "area_m2": areas[j],
                        "permeability_m_per_s": base["permeability_m_per_s"][s]
                        * case["leak_multiplier"],
                    }
                    compare(
                        f"{label}/oracle/{s}/{j}",
                        density[s][j] * areas[j] / 1e-15,
                        c.oracle(point, constants),
                        "flux_fmol_per_s",
                    )
            after_delta = [
                [delta[s][i] + rates[s][i] * base["dt_s"] for i in range(n)] for s in range(6)
            ]
            state(label + "/after", saved["after"], after_delta, constants, density)
            for s in range(6):
                di = [
                    (saved["after"]["inside_mM"][s][i] - saved["before"]["inside_mM"][s][i]) * vi[i]
                    for i in range(n)
                ]
                do = (saved["after"]["outside_mM"][s][0] - saved["before"]["outside_mM"][s][0]) * vo
                for i in range(n):
                    compare(
                        f"{label}/transfer/{s}/{i}",
                        di[i],
                        rates[s][i] * base["dt_s"],
                        "amount_fmol",
                    )
                compare(
                    f"{label}/outside_transfer/{s}",
                    do,
                    -math.fsum(rates[s]) * base["dt_s"],
                    "amount_fmol",
                )
                residual = math.fsum(di) + do
                maxima["material_residual_fmol"] = max(
                    maxima["material_residual_fmol"], abs(residual)
                )
                compare(f"{label}/global_material/{s}", residual, 0, "amount_fmol")
            if profile_id == "matched_constants":
                for backend, values in local["results"].items():
                    item = values[k]
                    c.require(
                        item["valid_domain"] is item["inactive_slots_zero"] is True,
                        "Cells domain/mask failed",
                    )
                    matrix(item["inside_rate_fmol_per_s"], 3, n)
                    c.require(
                        len(item["outside_rate_fmol_per_s"]) == 3
                        and len(item["voltage_V"]) == len(item["increment_voltage_V"]) == n,
                        "Cells output shape differs",
                    )
                    for i in range(n):
                        compare(
                            f"{label}/{backend}/voltage/{i}",
                            item["voltage_V"][i],
                            voltage[i],
                            "voltage_V",
                        )
                        compare(
                            f"{label}/{backend}/increment_voltage/{i}",
                            item["increment_voltage_V"][i],
                            voltage[i],
                            "voltage_V",
                        )
                        for j, owner in enumerate(owners):
                            if owner == i:
                                maxima["voltage_V"] = max(
                                    maxima["voltage_V"],
                                    abs(item["voltage_V"][i] - saved["before"]["voltage_V"][j]),
                                )
                    for s in range(3):
                        for i in range(n):
                            compare(
                                f"{label}/{backend}/rate/{s}/{i}",
                                item["inside_rate_fmol_per_s"][s][i],
                                rates[s][i],
                                "flux_fmol_per_s",
                            )
                            maxima["flux_fmol_per_s"] = max(
                                maxima["flux_fmol_per_s"],
                                abs(item["inside_rate_fmol_per_s"][s][i] - rates[s][i]),
                            )
                            if case["leak_multiplier"] == 0:
                                c.require(
                                    item["inside_rate_fmol_per_s"][s][i] == 0,
                                    "Blocked Cells route transported",
                                )
                        compare(
                            f"{label}/{backend}/outside/{s}",
                            item["outside_rate_fmol_per_s"][s],
                            -math.fsum(rates[s]),
                            "flux_fmol_per_s",
                        )
                        compare(
                            f"{label}/{backend}/ownership/{s}",
                            item["outside_rate_fmol_per_s"][s]
                            + math.fsum(item["inside_rate_fmol_per_s"][s]),
                            0,
                            "flux_fmol_per_s",
                        )
        for saved in profile["footprints"]:
            label = f"{profile_id}/footprint/{saved['id']}"
            expected = a.footprint(saved["id"], areas, base["prescribed_density_mol_per_m2_s"])
            c.require(
                saved["density_mol_per_m2_s"] == [expected] + [[0.0] * m for _ in range(5)],
                "Footprint changed",
            )
            density = saved["density_mol_per_m2_s"]
            rates = flux_rates(density)
            state(label + "/before", saved["before"], [[0.0] * n for _ in range(6)], constants)
            state(
                label + "/after",
                saved["after"],
                [[v * base["dt_s"] for v in row] for row in rates],
                constants,
                density,
            )
            inside = math.fsum(
                (saved["after"]["inside_mM"][0][i] - saved["before"]["inside_mM"][0][i]) * vi[i]
                for i in range(n)
            )
            outside = (
                saved["after"]["outside_mM"][0][0] - saved["before"]["outside_mM"][0][0]
            ) * vo
            compare(label + "/conservation", inside + outside, 0, "amount_fmol")
            if saved["id"] == "uniform":
                volume_mismatch_witnesses.append(inside + outside / m)
        clock = profile["clock"]
        c.require(
            clock["sampled_indices"] == list(range(1, 10)) and len(clock["labels_s"]) == 10,
            "Native schedule differs",
        )
        c.require(
            all(
                math.isclose(label, i * 10 * base["dt_s"] / 9, rel_tol=1e-14, abs_tol=1e-18)
                for i, label in enumerate(clock["labels_s"])
            ),
            "Native time labels differ",
        )
    c.require(
        all(abs(v) > 100 * tolerances["amount_fmol"] for v in volume_mismatch_witnesses),
        "Bath normalization witness too small",
    )
    return {
        "status": "pass" if all(row["pass"] for row in rows) else "failed",
        "comparison_count": len(rows),
        "maximum_normalized_error": max(row["normalized_error"] for row in rows),
        "maximum_matched_differences": maxima,
        "configured_volume_mass_residual_fmol": volume_mismatch_witnesses,
        "comparisons": rows,
        "cell_count": n,
        "native_membrane_faces": m,
        "trajectory_run": False,
        "biological_validation": False,
    }
