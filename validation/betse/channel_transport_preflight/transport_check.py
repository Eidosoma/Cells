"""Model-free native/Cells transport checks; retain all numerical rejections."""

import math

import transport_protocol as t

c = t.c


class Ledger:
    def __init__(self, protocol):
        self.tolerance = protocol["tolerances"]
        self.rows = []

    def compare(self, name, actual, expected, unit):
        if isinstance(expected, list):
            c.require(
                isinstance(actual, list) and len(actual) == len(expected),
                f"Array shape differs: {name}",
            )
            for i, (value, target) in enumerate(zip(actual, expected, strict=True)):
                self.compare(f"{name}/{i}", value, target, unit)
            return
        error = c.normalized_error(
            actual, expected, self.tolerance[unit], self.tolerance["relative"]
        )
        self.rows.append(
            {
                "id": name,
                "actual": actual,
                "expected": expected,
                "unit": unit,
                "scaled_error": error,
                "passed": error <= 1,
            }
        )


def zeros_like(value):
    return [zeros_like(v) for v in value] if isinstance(value, list) else 0.0


def scale(value, factor):
    return [scale(v, factor) for v in value] if isinstance(value, list) else value * factor


def require_zero(value, label):
    if isinstance(value, list):
        for v in value:
            require_zero(v, label)
    else:
        c.require(type(value) in (int, float) and value == 0, f"Nonzero inactive flow: {label}")


def shape_finite(value, dimensions, label):
    if dimensions:
        c.require(isinstance(value, list) and len(value) == dimensions[0], f"Wrong shape: {label}")
        for v in value:
            shape_finite(v, dimensions[1:], label)
    else:
        c.require(type(value) in (int, float) and math.isfinite(value), f"Invalid scalar: {label}")


def native_contract(p, base, variant, prep, row, expected_geometry):
    g = prep["geometry"]
    c.require({k: g[k] for k in t.GEOMETRY_FIELDS} == expected_geometry, "Geometry differs")
    c.require(prep["source_constants"] == {"F": 96485.0, "R": 8.314}, "Wrong source constants")
    c.require(
        prep["settings"]
        == {
            "is_ecm": False,
            "cell_polarizability": 0.0,
            "cluster_open": True,
            "alpha_NaK": 0.0,
            "alpha_Ca": 0.0,
            "Ca_dyn": False,
            "molecules_enabled": variant["network"],
            "grn_enabled": False,
            "fluid_flow": False,
            "deformation": False,
            "deform_osmo": False,
            "dynamic_noise": False,
            "channel_noise_level": 0.0,
            "v_sensitive_gj": False,
            "gj_surface": 0.0,
            "substances_affect_charge": True,
            "solver": "FULL",
            "temperature_K": p["temperature_K"],
            "thickness_m": p["thickness_m"],
            "constants": p["constants"],
        },
        "Native mechanism configuration differs",
    )
    c.require(
        row["dt_s"] == p["dt_s"] and row["sim_temperature_K"] == p["temperature_K"],
        "Native clock/actual temperature differs",
    )
    c.require(row["rho_channel"] == 1, "Nonuniform channel density")
    c.require(row["dtype"] == "float64", "Native dtype differs")
    c.require(
        row["species"] == base["expected_species"] and row["valence"] == base["expected_valence"],
        "Ion profile differs",
    )
    require_zero(row["ordinary_diffusivity_m2_per_s"], "background permeability")
    expected_inventory = (
        None
        if not variant["network"]
        else {
            "molecules": [],
            "reactions": [],
            "reactions_env": [],
            "transporters": [],
            "channels": ["Kv1p5_contact"] if variant["channel"] else [],
            "modulators": [],
        }
    )
    c.require(row["network_inventory"] == expected_inventory, "Unrelated network mechanisms")
    c.require(
        row["call_counts"]
        == {
            "channel_runner": int(variant["channel"]),
            "empty_chemistry_runner": int(variant["network"]),
            "ordinary_update": 1,
            "full_simulator_loop": 0,
        },
        "Wrong native call scope",
    )
    if variant["channel"]:
        meta = row["metadata"]
        expected_meta = {
            "name": "Kv1p5_contact",
            "class": "K",
            "type": "Kv1p5",
            "targets": list(range(g["membrane_count"])),
            "target_profiles": "all",
            "init_active": True,
            "maxDm_m2_per_s": p["thickness_m"]
            * p["max_permeability_m_per_s"]
            * p["abundance"]
            * variant["permeability_fraction"],
            "ions": ["K"],
            "relative_permeability": [1.0],
            "powers": [1, 1],
            "time_unit": 1000,
        }
        c.require(
            {k: v for k, v in meta.items() if k != "alpha_eval_string"} == expected_meta,
            "Native channel identity/units/targets differ",
        )
        c.require(
            isinstance(meta["alpha_eval_string"], str) and meta["alpha_eval_string"],
            "Missing native modulation expression",
        )
        for key in ("initialized_channel", "channel_before"):
            c.require(
                row[key]["P"] is None and row[key]["DChan_m2_per_s"] is None,
                "Initial native P/DChan must be absent, not invented",
            )
            require_zero(row[key]["density_mol_per_m2_s"], "initial channel flux")
        for stage in ("initialized_channel", "channel_before", "channel_after"):
            for field in ("m", "h", "derived_m_times_h", "density_mol_per_m2_s"):
                shape_finite(row[stage][field], [g["membrane_count"]], stage + field)
        for field in ("P", "DChan_m2_per_s"):
            shape_finite(row["channel_after"][field], [g["membrane_count"]], field)
        mod = row["channel_after"]["modulator"]
        c.require(mod == 1 or mod == [1.0] * g["membrane_count"], "Nonconstant modulation")
    else:
        c.require(
            all(
                row[k] is None
                for k in ("metadata", "initialized_channel", "channel_before", "channel_after")
            ),
            "Channel exists in channel-free control",
        )


def native_case(p, base, variant, fixture, prep, row, ledger):
    check = lambda label, actual, expected, unit: ledger.compare(  # noqa: E731
        row["id"] + "/native/" + label, actual, expected, unit
    )
    g, before = prep["geometry"], row["before"]
    n, m, dt, f = g["cell_count"], g["membrane_count"], p["dt_s"], p["constants"]["F"]
    vi, vo = [v / 1e-15 for v in g["cell_volumes_m3"]], g["effective_bath_volume_m3"] / 1e-15
    z = base["expected_valence"]
    c.require(
        g["effective_bath_volume_m3"] == m * g["configured_bath_volume_m3"],
        "Wrong active-path bath normalization",
    )
    c.require(
        g["specific_capacitance_F_per_m2"] == 0.01 and g["grid_shape"] == [10, 10],
        "Wrong capacitance/grid",
    )
    c.require(
        all(v > 0 for v in (*vi, vo, *g["cell_areas_m2"], *g["membrane_areas_m2"])),
        "Nonpositive geometry",
    )
    for i, (area, volume) in enumerate(zip(g["cell_areas_m2"], g["cell_volumes_m3"], strict=True)):
        c.require(
            math.isclose(t.cell_sums([1.0] * m, g)[i], area, rel_tol=1e-13),
            "Face areas do not sum to owner area",
        )
        c.require(
            math.isclose(g["diviterm_m"][i], volume / area, rel_tol=1e-13), "Wrong geometry divider"
        )
    for region, expected in (
        ("inside_mM", [[v] * n for v in base["inside_mM"]]),
        ("outside_mM", [[v] * m for v in base["outside_mM"]]),
    ):
        check("profile/" + region, row["core_initial"][region], expected, "concentration_mM")
        c.require(
            before[region] == row["core_initial"][region],
            "Native network initialization changed ionic charge/inventory",
        )
    voltage = t.uniform_faces(before["voltage_V"], g["membrane_owners"], n)
    density = [0.0] * m
    if variant["channel"]:
        initial, b, after = (
            row[k] for k in ("initialized_channel", "channel_before", "channel_after")
        )
        for key in ("m", "h"):
            for stage in (initial, b, after):
                t.uniform_faces(stage[key], g["membrane_owners"], n)
                c.require(all(0 <= v <= 1 for v in stage[key]), "Gate outside unit domain")
        for face in range(m):
            target0, _, _ = t.gate_reference(
                row["core_initial"]["gate_initialization_voltage_V"][face], [0, 0], dt
            )
            check(f"init/{face}", [initial["m"][face], initial["h"][face]], target0, "gate")
            expected_before = target0 if fixture["gate"] is None else fixture["gate"]
            check(f"before_gate/{face}", [b["m"][face], b["h"][face]], expected_before, "gate")
            target, tau, expected_after = t.gate_reference(
                before["voltage_V"][face], [b["m"][face], b["h"][face]], dt
            )
            check(f"post_gate/{face}", [after["m"][face], after["h"][face]], expected_after, "gate")
            for label, channel in (("init", initial), ("before", b), ("after", after)):
                check(
                    f"{label}_derived/{face}",
                    channel["derived_m_times_h"][face],
                    channel["m"][face] * channel["h"][face],
                    "gate",
                )
            opened = after["m"][face] * after["h"][face]
            check(f"open/{face}", after["P"][face], opened, "gate")
            permeability = (
                p["max_permeability_m_per_s"]
                * p["abundance"]
                * opened
                * variant["permeability_fraction"]
            )
            check(
                f"diffusivity/{face}",
                after["DChan_m2_per_s"][face],
                permeability * p["thickness_m"],
                "diffusivity_m2_per_s",
            )
            density[face] = c.oracle(
                {
                    "valence": 1,
                    "voltage_V": before["voltage_V"][face],
                    "temperature_K": p["temperature_K"],
                    "area_m2": 1e-15,
                    "permeability_m_per_s": permeability,
                    "inside_mM": before["inside_mM"][1][g["membrane_owners"][face]],
                    "outside_mM": t.uniform_bath(before["outside_mM"][1]),
                },
                p["constants"],
                precision=80,
            )
        check("density", after["density_mol_per_m2_s"], density, "density_mol_per_m2_s")
        if fixture["gate"] is not None:
            c.require(
                any(a != b0 for a, b0 in zip(after["m"], b["m"], strict=True)),
                "Prescribed real gate did not evolve, including under block",
            )
    native_density = (
        density if not variant["channel"] else row["channel_after"]["density_mol_per_m2_s"]
    )
    flux = scale(t.cell_sums(native_density, g), 1e15)
    current_density = scale(native_density, -f)
    check(
        "network_current",
        row["network_current_density_A_per_m2"],
        current_density,
        "current_density_A_per_m2",
    )
    check(
        "pre_export_current",
        row["after_channel"]["extra_current_density_A_per_m2"],
        [0.0] * m,
        "current_density_A_per_m2",
    )
    for stage_name in (
        "before",
        "after_channel",
        "after_network",
        "after_ordinary",
        "after_voltage",
    ):
        stage = row[stage_name]
        for name in ("inside_mM", "outside_mM", "at_membrane_mM"):
            shape_finite(stage[name], [6, n if name == "inside_mM" else m], stage_name + name)
        require_zero(stage["ordinary_density_mol_per_m2_s"], "ordinary channel duplication")
        require_zero(stage["junction_density_mol_per_m2_s"], "junction flux")
        require_zero(stage["extra_rho_cells_C_per_m3"], "extra cell charge")
        require_zero(stage["extra_rho_env_C_per_m3"], "extra outside charge")
        require_zero(stage["boundary_voltage_V"], "external voltage forcing")
        t.uniform_faces(stage["voltage_V"], g["membrane_owners"], n)
        if stage_name in ("after_network", "after_ordinary", "after_voltage"):
            check(
                stage_name + "/extra_current",
                stage["extra_current_density_A_per_m2"],
                current_density,
                "current_density_A_per_m2",
            )
        for species in range(6):
            outside = t.uniform_bath(stage["outside_mM"][species])
            c.require(
                outside > 0 and all(v > 0 for v in stage["inside_mM"][species]),
                "Nonpositive native chemistry",
            )
            check(
                f"{stage_name}/membrane_concentration/{species}",
                stage["at_membrane_mM"][species],
                [stage["inside_mM"][species][owner] for owner in g["membrane_owners"]],
                "concentration_mM",
            )
            expected_inside = [
                before["inside_mM"][species][i]
                + (flux[i] * dt / vi[i] if species == 1 and stage_name != "before" else 0)
                for i in range(n)
            ]
            expected_out = t.uniform_bath(before["outside_mM"][species]) - (
                math.fsum(flux) * dt / vo if species == 1 and stage_name != "before" else 0
            )
            check(
                f"{stage_name}/inside/{species}",
                stage["inside_mM"][species],
                expected_inside,
                "concentration_mM",
            )
            check(f"{stage_name}/outside/{species}", outside, expected_out, "concentration_mM")
            residual = math.fsum(
                [
                    (v - b0) * volume
                    for v, b0, volume in zip(
                        stage["inside_mM"][species], before["inside_mM"][species], vi, strict=True
                    )
                ]
                + [(outside - t.uniform_bath(before["outside_mM"][species])) * vo]
            )
            check(f"{stage_name}/species_conservation/{species}", residual, 0, "amount_fmol")
        if stage_name in ("before", "after_voltage"):
            charge_density = [
                f * math.fsum(z[s] * stage["inside_mM"][s][i] for s in range(6)) for i in range(n)
            ]
            check(
                stage_name + "/rho",
                stage["rho_C_per_m3"],
                charge_density,
                "charge_density_C_per_m3",
            )
            check(
                stage_name + "/charge_voltage",
                t.uniform_faces(stage["voltage_V"], g["membrane_owners"], n),
                [
                    rho * v / (area * 0.01)
                    for rho, v, area in zip(
                        charge_density, g["cell_volumes_m3"], g["cell_areas_m2"], strict=True
                    )
                ],
                "voltage_V",
            )
    # Preserve the native nonce input mutation; it is not a voltage clamp/offset.
    expected_v = [v + (1e-25 if variant["channel"] else 0) for v in before["voltage_V"]]
    c.require(row["after_channel"]["voltage_V"] == expected_v, "Undeclared channel input mutation")
    for later in ("after_network", "after_ordinary"):
        for region in ("inside_mM", "outside_mM"):
            check(
                later + "/no_second_transfer/" + region,
                row[later][region],
                row["after_channel"][region],
                "concentration_mM",
            )
    final = row["after_voltage"]

    def total_charge(stage):
        return (
            f
            * 1e-15
            * math.fsum(
                z[s]
                * math.fsum(
                    [v * volume for v, volume in zip(stage["inside_mM"][s], vi, strict=True)]
                    + [t.uniform_bath(stage["outside_mM"][s]) * vo]
                )
                for s in range(6)
            )
        )

    check("global_charge_change", total_charge(final), total_charge(before), "charge_C")
    check("Jmem", final["Jmem_A_per_m2"], current_density, "current_density_A_per_m2")
    average_current = [
        v / area
        for v, area in zip(t.cell_sums(current_density, g), g["cell_areas_m2"], strict=True)
    ]
    smoothed = [
        a * jm + b * average_current[owner]
        for a, b, jm, owner in zip(
            row["smooth_weight_mem"],
            row["smooth_weight_other"],
            current_density,
            g["membrane_owners"],
            strict=True,
        )
    ]
    check("Jn", final["Jn_A_per_m2"], smoothed, "current_density_A_per_m2")
    check(
        "I_mem",
        final["I_mem_A"],
        [-j * area for j, area in zip(smoothed, g["membrane_areas_m2"], strict=True)],
        "current_A",
    )
    check(
        "delta_voltage",
        [
            v - v0
            for v, v0 in zip(
                t.uniform_faces(final["voltage_V"], g["membrane_owners"], n), voltage, strict=True
            )
        ],
        [
            q * dt * f * 1e-15 / (area * 0.01)
            for q, area in zip(flux, g["cell_areas_m2"], strict=True)
        ],
        "voltage_V",
    )
    if not variant["permeability_fraction"]:
        require_zero(native_density, "blocked channel")
        require_zero(row["network_current_density_A_per_m2"], "blocked current")
    else:
        c.require(all(v < 0 for v in native_density), "Active K control has no outward flow")
    return flux


def cells_case(p, base, variant, g, row, definition, result, backend, ledger, native_flux):
    check = lambda label, actual, expected, unit: ledger.compare(  # noqa: E731
        row["id"] + "/" + backend + "/" + label, actual, expected, unit
    )
    c.require(definition == t.definition(base, p, variant, g, row), "Cells mapping differs")
    c.require(
        result["valid_matched_state"] is True and result["valid_transferred_state"] is True,
        "Cells domain rejected",
    )
    n, nk, dt, f = g["cell_count"], 7 if variant["channel"] else 0, p["dt_s"], p["constants"]["F"]
    before, final = row["before"], row["after_voltage"]
    voltage = t.uniform_faces(before["voltage_V"], g["membrane_owners"], n)
    check("before_voltage", result["before_voltage_V"], voltage + [0.0], "voltage_V")
    check(
        "after_voltage",
        result["after_voltage_V"],
        t.uniform_faces(final["voltage_V"], g["membrane_owners"], n) + [0.0],
        "voltage_V",
    )
    cr, rhs, after = (result[key] for key in ("channel_readouts", "rhs", "after"))
    state_shapes = {
        "amount_increment": ([3, 8], 7),
        "leak_transferred": ([3, 9], 7),
        "pump_cycles": ([9], 7),
        "dissipated_energy_pJ": ([9], 7),
        "gate": ([2, 10], nk),
        "channel_transferred": ([10], nk),
        "junction_gate": ([1], 0),
        "junction_transferred": ([3, 1], 0),
        "junction_dissipated_energy_pJ": ([1], 0),
        "extracellular_amount_increment": ([3, 2], 1),
    }
    for stage_name in ("initial_state", "rhs", "after"):
        c.require(set(result[stage_name]) == set(state_shapes), "Wrong state fields")
        for name, (dimensions, used) in state_shapes.items():
            value = result[stage_name][name]
            shape_finite(value, dimensions, stage_name + name)
            for vector in value if len(dimensions) == 2 else [value]:
                require_zero(vector[used:], "padded " + name)
    if nk:
        expected_initial = [
            t.uniform_faces(row["channel_before"][k], g["membrane_owners"], n) + [0.0] * (10 - nk)
            for k in ("m", "h")
        ]
    else:
        expected_initial = [[0.0] * 10 for _ in range(2)]
    c.require(result["initial_state"]["gate"] == expected_initial, "Original m/h pair was lost")
    flux, targets, taus, gate_rate, opened, effective, gates = (
        [],
        [[], []],
        [[], []],
        [[], []],
        [],
        [],
        [[], []],
    )
    if variant["channel"]:
        gates = [
            t.uniform_faces(row["channel_after"][k], g["membrane_owners"], n) for k in ("m", "h")
        ]
        for i in range(n):
            inf, tau, _ = t.gate_reference(voltage[i], [gates[0][i], gates[1][i]], dt)
            for k in range(2):
                targets[k].append(inf[k])
                taus[k].append(tau[k])
                gate_rate[k].append((inf[k] - gates[k][i]) / tau[k])
            opened.append(gates[0][i] * gates[1][i])
            effective.append(
                opened[-1]
                * p["max_permeability_m_per_s"]
                * p["abundance"]
                * variant["permeability_fraction"]
            )
            flux.append(
                c.oracle(
                    {
                        "valence": 1,
                        "voltage_V": voltage[i],
                        "temperature_K": p["temperature_K"],
                        "area_m2": g["cell_areas_m2"][i],
                        "permeability_m_per_s": effective[-1],
                        "inside_mM": before["inside_mM"][1][i],
                        "outside_mM": t.uniform_bath(before["outside_mM"][1]),
                    },
                    p["constants"],
                    precision=80,
                )
            )
    for key, expected, unit in (
        ("gate_inf", targets, "gate"),
        ("gate_tau_s", taus, "tau_s"),
        ("gate_rate_per_s", gate_rate, "gate_rate_per_s"),
        ("open_probability", opened, "gate"),
        ("effective_permeability_m_per_s", effective, "permeability_m_per_s"),
        ("flux_fmol_per_s", flux, "flux_fmol_per_s"),
    ):
        padded = (
            [v + [0.0] * (10 - nk) for v in expected]
            if key.startswith("gate_")
            else expected + [0.0] * (10 - nk)
        )
        check(key, cr[key], padded, unit)
    matched = [v + [0.0] * (10 - nk) for v in gates]
    c.require(
        result["matched_gate"] == matched and after["gate"] == matched,
        "Post-native gate state was averaged, advanced twice or changed",
    )
    check(
        "rhs_channel_ledger", rhs["channel_transferred"], cr["flux_fmol_per_s"], "flux_fmol_per_s"
    )
    check("rhs_gate", rhs["gate"], cr["gate_rate_per_s"], "gate_rate_per_s")
    check(
        "cross_engine_flux",
        (cr["flux_fmol_per_s"][:n] if nk else [0.0] * n),
        native_flux,
        "flux_fmol_per_s",
    )
    for state_key in ("initial_state", "rhs", "after"):
        for name in (
            "leak_transferred",
            "pump_cycles",
            "junction_gate",
            "junction_transferred",
            "junction_dissipated_energy_pJ",
        ):
            require_zero(result[state_key][name], name)
    for species in range(3):
        expected = (flux if species == 1 and nk else [0.0] * n) + [0.0]
        check(
            f"rhs_inside/{species}", rhs["amount_increment"][species], expected, "flux_fmol_per_s"
        )
        check(
            f"rhs_outside/{species}",
            rhs["extracellular_amount_increment"][species],
            [-math.fsum(expected), 0.0],
            "flux_fmol_per_s",
        )
        check(
            f"after_inside/{species}",
            result["after_inside_amount_fmol"][species],
            [
                v * volume / 1e-15
                for v, volume in zip(final["inside_mM"][species], g["cell_volumes_m3"], strict=True)
            ]
            + [0.0],
            "amount_fmol",
        )
        check(
            f"after_outside/{species}",
            result["after_outside_amount_fmol"][species],
            [
                t.uniform_bath(final["outside_mM"][species])
                * g["effective_bath_volume_m3"]
                / 1e-15,
                0,
            ],
            "amount_fmol",
        )
        check(
            f"material/{species}",
            math.fsum(
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
        require_zero(result["initial_state"][name], "initial " + name)
        check("single_transfer/" + name, after[name], scale(rhs[name], dt), unit)
    check("countercharge", result["countercharge_C"], 0, "charge_C")
    check(
        "inward_current",
        scale(rhs["amount_increment"][1][:n], f * 1e-15),
        scale(t.cell_sums(row["network_current_density_A_per_m2"], g), -1),
        "current_A",
    )
    cell_delta_charge = (
        f
        * 1e-15
        * math.fsum(
            base["expected_valence"][s] * math.fsum(after["amount_increment"][s]) for s in range(3)
        )
    )
    bath_delta_charge = (
        f
        * 1e-15
        * math.fsum(
            base["expected_valence"][s] * math.fsum(after["extracellular_amount_increment"][s])
            for s in range(3)
        )
    )
    check("outside_countercharge", bath_delta_charge, -cell_delta_charge, "charge_C")


def evaluate(r, native, cells):
    p, base = r["protocol"], r["base_protocol"]
    t.validate_protocol(p)
    keys = set(t.case_ids(p))
    c.require(
        set(native["rows"]) == keys and set(cells["definitions"]) == keys,
        "Missing/extra native or definition cases",
    )
    c.require(set(native["preparations"]) == {v["id"] for v in p["variants"]}, "Wrong preparations")
    c.require(set(cells["results"]) == set(t.BACKENDS), "Missing backend")
    c.require(all(set(rows) == keys for rows in cells["results"].values()), "Wrong backend cases")
    ledger = Ledger(p)
    for variant in p["variants"]:
        prep = native["preparations"][variant["id"]]
        for fixture in p["states"]:
            key = f"{variant['id']}/{fixture['id']}"
            row = native["rows"][key]
            c.require(row["id"] == key, "Case identity differs")
            native_contract(p, base, variant, prep, row, r["expected_geometry"])
            flux = native_case(p, base, variant, fixture, prep, row, ledger)
            for backend in t.BACKENDS:
                cells_case(
                    p,
                    base,
                    variant,
                    prep["geometry"],
                    row,
                    cells["definitions"][key],
                    cells["results"][backend][key],
                    backend,
                    ledger,
                    flux,
                )
    distinct = []
    for variant in ("blocked_channel", "active_channel"):
        aa, bb = (native["rows"][variant + "/prescribed_mh_" + suffix] for suffix in ("a", "b"))
        ledger.compare(
            variant + "/equal_initial_open",
            aa["channel_before"]["derived_m_times_h"],
            bb["channel_before"]["derived_m_times_h"],
            "gate",
        )
        difference = max(
            abs(a - b)
            for a, b in zip(aa["channel_after"]["P"], bb["channel_after"]["P"], strict=True)
        )
        c.require(difference > 1e-6, "Distinct m/h pairs collapsed to one open fraction")
        distinct.append(
            {
                "variant": variant,
                "post_update_open_fraction_difference": difference,
                "initial_pairs_are_prescribed_not_reconstructed_histories": True,
            }
        )
    identities = [row["id"] for row in ledger.rows]
    c.require(len(set(identities)) == len(identities), "Duplicate comparison")
    failed = sum(not row["passed"] for row in ledger.rows)
    return {
        "schema": "cells.betse_channel_transport_preflight_comparison@1",
        "status": "pass" if failed == 0 else "fail",
        "comparison_count": len(ledger.rows),
        "failed_comparisons": failed,
        "comparisons": ledger.rows,
        "distinct_hidden_state_controls": distinct,
        "native_single_updates": 12,
        "cells_matched_transfers_per_backend": 12,
        "independent_audit_complete": False,
        "coupled_trajectory_qualified": False,
        "biology_validated": False,
        "gpu_tested": False,
    }
