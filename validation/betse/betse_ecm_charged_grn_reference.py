"""Independent Decimal chemistry/mover equations from actual pre-network state.

All forms are fresh conditional local checks. No upstream or independently
carried trajectory accuracy follows from this reference.
"""

import copy
from decimal import Decimal, localcontext

from validation.betse.betse_ecm_transport_reference import smooth
from validation.betse.betse_environment_field_reference import _derivative, _flatten, _reshape
from validation.betse.betse_environment_field_reference import geometry as derive_geometry
from validation.betse.betse_normal_network_join_reference import _alpha, d


def plain(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    return value


def hill(gad, prefix, state, site):
    if gad is None:
        return d(1)
    alpha = d(1)
    for activating, sign in ((True, "activators"), (False, "inhibitors")):
        names = gad.get(prefix + sign)
        if names is None:
            continue
        for name, km, power in zip(
            names, gad["Km " + prefix + sign], gad["n " + prefix + sign], strict=True
        ):
            load = (state[name][site] / d(km)) ** d(power)
            alpha *= load / (1 + load) if activating else 1 / (1 + load)
    return alpha


def configuration(inputs, *, refinement=1):
    if refinement not in (1, 2) or inputs["mode"] != "cold_initialization":
        raise ValueError("Require cold configuration inputs before owner construction")
    with localcontext() as context:
        context.prec = 100 if refinement == 1 else 160
        net = inputs["network"]
        cfg = net["configuration"]
        n, m = inputs["cells"], inputs["membranes"]
        genes = {}
        for row in cfg["biomolecules"]:
            gad = row["growth and decay"]
            fields = dict(
                Dm=d(row["Dm"]),
                Do=d(row["Do"]),
                Dgj=d(row.get("Dgj", 1e-16)),
                z=d(row["z"]),
                ignore_ECM_pump=True,
                ignoreTJ=row["TJ permeable"],
                ignoreGJ=row["GJ impermeable"],
                TJ_factor=d(row["TJ factor"]),
                update_intra_conc=False,
                transmem=False,
                Mu_mem=d(0),
                u_mt=d(0),
                scale_factor=d(row.get("scale factor", 1.0)),
                modify_time_factor=d(cfg.get("time dilation factor", 1))
                if row.get("use time dilation", False)
                else d(1),
                active_pumping=False,
                ion_channel_gating=False,
                change_bounds=False,
                cell_clamp=False,
                c_cells=[d(row["cell conc"])] * n,
                cc_at_mem=[d(row["cell conc"])] * m,
                c_env=[d(row["env conc"])] * inputs["environment_sites"],
                flux_intra=[d(0)] * m,
                c_bound=d(row["env conc"]),
                simple_growth=gad is not None,
                gad_scale_factor=d(1) if gad is None else d(gad.get("scale factor", 1)),
                r_production=None if gad is None else d(gad["production rate"]),
                r_decay=None if gad is None else d(gad["decay rate"]),
                growth_targets_cell=list(range(n)),
            )
            if gad is not None:
                fields.update(
                    growth_targets_mem=list(range(m)), decay_max=d(gad.get("decay max", 0))
                )
            genes[row["name"]] = fields
        ids = inputs["ion_ids"] + [row["name"] for row in cfg["biomolecules"]]
        matrix = [[d(0)] * 3 for _ in ids]
        matrix[ids.index("X")] = [d(1), d(0), d(-1)]
        matrix[ids.index("Y")] = [d(0), d(1), d(1)]
        return plain(
            dict(
                molecule_fields=genes,
                reaction_matrix=matrix,
                simulator_fields={
                    key: [d(0)] * size
                    for key, size in (
                        ("extra_rho_cells", n),
                        ("extra_rho_env", inputs["environment_sites"]),
                        ("extra_J_mem", m),
                        ("extra_Jenv_x", inputs["environment_sites"]),
                        ("extra_Jenv_y", inputs["environment_sites"]),
                    )
                },
                independent_geometry=derive_geometry(
                    inputs["material_declaration"]["environment_geometry_definition"],
                    precision=context.prec,
                ),
                owner_fields=dict(
                    reset_MT=False,
                    recalc_fluid=False,
                    reactions=True,
                    transporters=False,
                    channels=False,
                    modulators=cfg.get("modulators") is not None,
                ),
                charge_has_been_balanced=net["cold_publish"],
                decimal_precision=context.prec,
                carried_reference_forms=0,
                fresh_conditional_reference=True,
                cold_initialization=True,
                physical_conservation_credit=False,
            )
        )


def compensation(inputs, *, refinement=1):
    """Independent charge/count accounting from immutable pre-constructor inputs.

    Decimal computes the physical quantities. An explicitly stored primitive
    binary64 sum independently describes the source's scalar charge/branch
    semantics; no native/model output is used and no trajectory is carried.
    """
    if refinement not in (1, 2) or inputs["mode"] != "cold_initialization":
        raise ValueError("Require charged inputs before owner construction")
    with localcontext() as ctx:
        ctx.prec = 100 if refinement == 1 else 160
        net, ids = inputs["network"], inputs["ion_ids"]
        before = {
            k: [[d(v) for v in row] for row in rows] for k, rows in inputs["ionic_state"].items()
        }
        after = copy.deepcopy(before)
        bound = list(map(d, net["initial_ion_boundary"]))
        F = d(inputs["F"])
        n, m = inputs["cells"], inputs["membranes"]
        volume = list(map(d, inputs["cell_volume_m3"]))
        e = inputs["environment_sites"]
        grid = derive_geometry(
            inputs["material_declaration"]["environment_geometry_definition"], precision=ctx.prec
        )
        site_volume = (
            d(
                inputs["material_declaration"]["environment_geometry_definition"]["parameters"][
                    "cell_height_m"
                ]
            )
            * d(grid["delta_m"]) ** 2
        )
        true_volume = [d(v) for v in grid["true_environment_volume_m3"]]
        valence = list(map(d, inputs["valence"]))
        formal, source_q, charge_gross = {}, {}, {}
        for region, key in (("cell", "cell conc"), ("env", "env conc")):
            total, rounded, gross = Decimal(0), 0.0, Decimal(0)
            for row in net["configuration"]["biomolecules"]:
                term = d(row[key]) * d(row["z"]) * d(row.get("scale factor", 1.0))
                total += term
                gross += abs(term)
                first = float(float(row[key]) * float(row["z"]))
                term64 = float(first * float(row.get("scale factor", 1.0)))
                rounded = float(rounded + term64)
            formal[region], source_q[region], charge_gross[region] = total, d(rounded), gross
        simulator = {
            key: [Decimal(0)] * size
            for key, size in (
                ("extra_rho_cells", n),
                ("extra_rho_env", e),
                ("extra_J_mem", m),
                ("extra_Jenv_x", e),
                ("extra_Jenv_y", e),
            )
        }
        stages, actions, failure = [], {}, None
        published = net["cold_publish"]
        if published:
            for tag, array in (("cell", "cc_cells"), ("env", "cc_env")):
                q = source_q[tag]
                stages.append(dict(stage="before", tag=tag, Q=q))
                species = "M" if q < 0 else "K" if tag == "cell" else "Na"
                index = ids.index(species)
                capacity = sum(before[array][index], Decimal(0)) / len(before[array][index])
                refusal_capacity = (
                    sum(before["cc_at_mem"][index], Decimal(0)) / m
                    if tag == "cell" and q < 0
                    else capacity
                )
                if q != 0 and abs(q) <= capacity:
                    after[array][index] = [v - abs(q) for v in before[array][index]]
                    if tag == "env":
                        bound[index] -= abs(q)
                    actions[tag] = dict(
                        action="remove",
                        species=species,
                        source_Q=q,
                        admission_capacity=capacity,
                        refusal_capacity=refusal_capacity,
                    )
                elif q != 0 and abs(q) > refusal_capacity:
                    failure = tag + ("_negative_excess" if q < 0 else "_positive_excess")
                    actions[tag] = dict(
                        action="refuse",
                        species=species,
                        source_Q=q,
                        admission_capacity=capacity,
                        refusal_capacity=refusal_capacity,
                    )
                    break
                else:
                    actions[tag] = dict(
                        action="zero" if q == 0 else "negative_threshold_gap",
                        species=None,
                        source_Q=q,
                        admission_capacity=capacity,
                        refusal_capacity=refusal_capacity,
                    )
                simulator["extra_rho_cells" if tag == "cell" else "extra_rho_env"] = [F * q] * (
                    n if tag == "cell" else e
                )
                stages.append(dict(stage="after", tag=tag, Q=q))
        else:
            actions = {
                tag: dict(action="disabled", species=None, source_Q=source_q[tag])
                for tag in ("cell", "env")
            }
        count_before, count_after, count_gross = {}, {}, {}
        for i, species in enumerate(ids):

            def amount(state, i=i):
                return sum((v * volume[j] for j, v in enumerate(state["cc_cells"][i])), Decimal(0))

            def env_amount(state, i=i):
                return sum(state["cc_env"][i], Decimal(0)) * site_volume

            def native_diagnostic(state, i=i):
                return sum(
                    (v * vol for v, vol in zip(state["cc_env"][i], true_volume, strict=True)),
                    Decimal(0),
                )

            count_before[species] = dict(
                cell=amount(before),
                source_effective_environment=env_amount(before),
                native_true_volume_diagnostic=native_diagnostic(before),
            )
            count_after[species] = dict(
                cell=amount(after),
                source_effective_environment=env_amount(after),
                native_true_volume_diagnostic=native_diagnostic(after),
            )
            count_gross[species] = {
                k: abs(v) + abs(count_after[species][k]) for k, v in count_before[species].items()
            }
        gene_count = {}
        for row in net["configuration"]["biomolecules"]:
            gene_count[row["name"]] = dict(
                cell=d(row["cell conc"]) * sum(volume, Decimal(0)),
                source_effective_environment=d(row["env conc"]) * e * site_volume,
                native_true_volume_diagnostic=d(row["env conc"]) * sum(true_volume, Decimal(0)),
            )
        cell_charge = [
            F
            * sum(
                (
                    valence[i] * (after["cc_cells"][i][j] - before["cc_cells"][i][j])
                    for i in range(len(ids))
                ),
                Decimal(0),
            )
            for j in range(n)
        ]
        env_charge = [
            F
            * sum(
                (
                    valence[i] * (after["cc_env"][i][j] - before["cc_env"][i][j])
                    for i in range(len(ids))
                ),
                Decimal(0),
            )
            for j in range(e)
        ]
        charge_ledger = dict(
            cell_ionic_charge_change_C_m3=cell_charge,
            env_ionic_charge_change_C_m3=env_charge,
            formal_gene_cell_charge_C_m3=[F * formal["cell"]] * n,
            formal_gene_env_charge_C_m3=[F * formal["env"]] * e,
            cell_ionic_plus_formal_change_C_m3=[v + F * formal["cell"] for v in cell_charge],
            env_ionic_plus_formal_change_C_m3=[v + F * formal["env"] for v in env_charge],
        )
        return plain(
            dict(
                ionic_state=after,
                independent_geometry=grid,
                ion_boundary_state=bound,
                simulator_fields=simulator,
                formal_gene_charge_mM=formal,
                source_Q_mM=source_q,
                source_Q_gross_mM=charge_gross,
                actions=actions,
                balance_stages=stages,
                failure_case=failure,
                source_exception=None if failure is None else "BetseSimConfException",
                charge_has_been_balanced=published and failure is None,
                ionic_count_before_mol=count_before,
                ionic_count_after_mol=count_after,
                ionic_count_change_mol={
                    s: {k: count_after[s][k] - v for k, v in row.items()}
                    for s, row in count_before.items()
                },
                ionic_count_gross_mol=count_gross,
                gene_count_mol=gene_count,
                charge_ledger=charge_ledger,
                ionic_membrane_cache_refreshed=False,
                counterion_removal_is_material_sink=True,
                boundary_value_is_not_reservoir_inventory=True,
                physical_conservation_credit=False,
                energetic_conservation_credit=False,
                source_compensation_only=True,
                cold_initialization=True,
                decimal_precision=ctx.prec,
                carried_reference_forms=0,
                fresh_conditional_reference=True,
            )
        )


def cold_inputs(inputs):
    initial = inputs["initial"]
    external = inputs["definition"]["environment_geometry_definition"]
    current = external["current_definition"]
    return dict(
        mode="cold_initialization",
        network=inputs["network"],
        material_declaration=inputs["definition"],
        ion_ids=current["ions"]["ids"],
        valence=current["ions"]["valence"],
        cells=len(initial["cell_mol_m3"][0]),
        membranes=len(initial["voltage_V"]),
        environment_sites=len(initial["environment_mol_m3"][0]),
        ionic_state={
            key: initial[source]
            for key, source in (
                ("cc_cells", "cell_mol_m3"),
                ("cc_at_mem", "membrane_mol_m3"),
                ("cc_env", "environment_mol_m3"),
            )
        },
        F=current["parameters"]["F_C_mol"],
        cell_volume_m3=external["geometry"]["cell_volume_m3"],
    )


def cold(inputs, *, refinement=1):
    result = compensation(inputs, refinement=refinement)
    if result["failure_case"] is None:
        fields = configuration(inputs, refinement=refinement)
        for key in ("molecule_fields", "reaction_matrix", "owner_fields", "independent_geometry"):
            result[key] = fields[key]
    return result


def flatten_flux(values):
    return _flatten(values) if values and isinstance(values[0], list) else values


def derivative_gross(image, delta):
    ny, nx = len(image), len(image[0])
    gx, gy = [[Decimal(0)] * nx for _ in range(ny)], [[Decimal(0)] * nx for _ in range(ny)]
    for i in range(ny):
        for j in range(nx):
            left, right = (
                (j - 1, j + 1) if 0 < j < nx - 1 else (0, 1) if j == 0 else (nx - 2, nx - 1)
            )
            bottom, top = (
                (i - 1, i + 1) if 0 < i < ny - 1 else (0, 1) if i == 0 else (ny - 2, ny - 1)
            )
            gx[i][j] = (image[i][left] + image[i][right]) / (delta * (2 if 0 < j < nx - 1 else 1))
            gy[i][j] = (image[bottom][j] + image[top][j]) / (delta * (2 if 0 < i < ny - 1 else 1))
    return gx, gy


def ecm_environment(env, gross, p, inputs, grid, dt, temperature):
    shape, delta = grid["shape"], grid["delta_m"]
    ny, nx = shape
    size = ny * nx
    volume = (
        d(
            inputs["material_declaration"]["environment_geometry_definition"]["parameters"][
                "cell_height_m"
            ]
        )
        * delta**2
    )
    zero = Decimal(0)
    if not any(env) and d(p["c_bound"]) <= d(1e-15):
        return dict(
            after=env,
            gross=gross,
            flux_x=[zero] * size,
            flux_y=[zero] * size,
            flux_x_gross=[zero] * size,
            flux_y_gross=[zero] * size,
            clamp_amount=zero,
            transport_amount=zero,
            smoothing_amount=zero,
        )
    initial = env[:]
    image, ig = _reshape(env, shape), _reshape(gross, shape)
    bound = d(p["c_bound"])
    for i in range(ny):
        for j in range(nx):
            if i in (0, ny - 1) or j in (0, nx - 1):
                image[i][j], ig[i][j] = bound, abs(bound)
    clamped = _flatten(image)
    gx, gy = _derivative(image, delta, source_boundary=False)
    ggx, ggy = derivative_gross(ig, delta)
    weights = [d(1)] * size
    if not p["ignoreTJ"]:
        row = list(map(d, inputs["D_env"][inputs["ion_ids"].index("Na")]))
        weights = [v / max(row) for v in row]
        targets = {index for group in inputs["grid_index_groups"].values() for index in group}
        for index in targets:
            weights[index] *= d(p["TJ_factor"])
    ex, ey = inputs["electric_x_source"], inputs["electric_y_source"]
    fx, fy, fxg, fyg = ([[zero] * nx for _ in range(ny)] for _ in range(4))
    for i in range(ny):
        for j in range(nx):
            diffusion = weights[i * nx + j] * d(p["Do"])
            alpha = diffusion * d(p["z"]) * d(inputs["q_C"]) / (d(inputs["kb_J_K"]) * temperature)
            fx[i][j] = -diffusion * gx[i][j] + alpha * d(ex[i][j]) * image[i][j]
            fy[i][j] = -diffusion * gy[i][j] + alpha * d(ey[i][j]) * image[i][j]
            fxg[i][j] = abs(diffusion) * ggx[i][j] + abs(alpha * d(ex[i][j])) * ig[i][j]
            fyg[i][j] = abs(diffusion) * ggy[i][j] + abs(alpha * d(ey[i][j])) * ig[i][j]
    dx, _ = _derivative([[-v for v in row] for row in fx], delta, source_boundary=True)
    _, dy = _derivative([[-v for v in row] for row in fy], delta, source_boundary=True)
    dxg, _ = derivative_gross(fxg, delta)
    _, dyg = derivative_gross(fyg, delta)
    time = d(p["modify_time_factor"])
    euler = [
        [image[i][j] + (dx[i][j] + dy[i][j]) * dt * time for j in range(nx)] for i in range(ny)
    ]
    eg = [[ig[i][j] + (dxg[i][j] + dyg[i][j]) * dt * time for j in range(nx)] for i in range(ny)]
    sharp = d(inputs["sharpness"])
    final = smooth(euler, sharp) if sharp < 1 else euler
    fg = smooth(eg, sharp) if sharp < 1 else eg
    return dict(
        after=_flatten(final),
        gross=_flatten(fg),
        flux_x=fx,
        flux_y=fy,
        flux_x_gross=fxg,
        flux_y_gross=fyg,
        clamp_amount=sum((a - b for a, b in zip(clamped, initial, strict=True)), zero) * volume,
        transport_amount=sum((a - b for a, b in zip(_flatten(euler), clamped, strict=True)), zero)
        * volume,
        smoothing_amount=sum(
            (a - b for a, b in zip(_flatten(final), _flatten(euler), strict=True)), zero
        )
        * volume,
    )


def warm(inputs, *, refinement=1):
    if refinement not in (1, 2) or not inputs["conditioned_before_model_network"]:
        raise ValueError("Require actual immutable pre-network inputs")
    with localcontext() as ctx:
        ctx.prec = 100 if refinement == 1 else 160
        definition, before = inputs["definition"], inputs["molecule_states_before"]
        configured = definition["molecules"]
        names, ions = [row["name"] for row in configured], inputs["ion_ids"]
        assert set(names) == {"X", "Y"} and len(names) == 2
        grid = derive_geometry(
            inputs["material_declaration"]["environment_geometry_definition"], precision=ctx.prec
        )
        mapping, shape = grid["membrane_to_grid"], grid["shape"]
        sites = shape[0] * shape[1]
        geometry = inputs["molecular_geometry"]
        owner, partner, boundary = geometry["owner"], geometry["partner"], geometry["boundary"]
        n, m = len(geometry["cell_volume_m3"]), len(owner)
        cell_rows = [[j for j, index in enumerate(owner) if index == i] for i in range(n)]
        area, volume, length = (
            [d(v) for v in geometry[key]]
            for key in ("membrane_area_m2", "cell_volume_m3", "gap_length_m")
        )
        dt, F, R = d(inputs["dt_s"]), d(inputs["F"]), d(inputs["R"])
        runtime, configured_T = (
            d(inputs["runtime_temperature_K"]),
            d(inputs["configured_temperature_K"]),
        )
        thickness, env_volume = (
            d(inputs["membrane_thickness_m"]),
            d(
                inputs["material_declaration"]["environment_geometry_definition"]["parameters"][
                    "cell_height_m"
                ]
            )
            * grid["delta_m"] ** 2,
        )
        vm = list(map(float, inputs["values_before"]["voltage_V"]))
        vgj = list(map(float, inputs["values_before"]["junction_voltage_V"]))
        raw = dict(
            sample_mM=[
                left + right
                for left, right in zip(
                    inputs["values_before"]["membrane_mol_m3"],
                    inputs["values_before"]["environment_mol_m3"],
                    strict=True,
                )
            ],
            membrane_to_environment=mapping,
            species_ids=ions,
            species_valence=inputs["valence"],
            voltage_V=vm,
            faraday_C_mol=inputs["F"],
            gas_constant_J_mol_K=inputs["R"],
            temperature_K=inputs["runtime_temperature_K"],
        )
        controls = {key: list(map(d, value)) for key, value in inputs["controls_before"].items()}
        writes = []
        for row in definition["modulators"]:
            value = [d(row["max effect"]) * _alpha(row, raw, j) for j in range(m)]
            key = "gj_block" if row["target"] == "GJ" else "NaKATP_block"
            controls[key] = value
            writes.append(
                dict(
                    rule_id=row["name"],
                    target=row["target"],
                    value=value[:],
                    gj_block=controls["gj_block"][:],
                    NaKATP_block=controls["NaKATP_block"][:],
                )
            )
        old_cell = {name: list(map(d, before[name]["c_cells"])) for name in names}
        old_env = {name: list(map(d, before[name]["c_env"])) for name in names}
        cell_state = {
            name: list(map(d, values))
            for name, values in zip(ions, inputs["values_before"]["cell_mol_m3"], strict=True)
        }
        cell_state.update(old_cell)
        configs = {row["name"]: row for row in definition["grn_configuration"]["biomolecules"]}
        growth, growth_gross = {}, {}
        for row in configured:
            name, parameters, g = row["name"], row["parameters"], row["growth"]
            if (
                any(
                    parameters[key]
                    for key in (
                        "update_intra_conc",
                        "transmem",
                        "active_pumping",
                        "ion_channel_gating",
                        "change_bounds",
                        "cell_clamp",
                    )
                )
                or parameters["Mu_mem"] != 0
                or parameters["u_mt"] != 0
            ):
                raise ValueError(
                    "Reference requires the declared instant-mixing passive mover seam"
                )
            factor, scale = d(parameters["modify_time_factor"]), d(g["scale_factor"])
            values, gross = [], []
            for site, concentration in enumerate(old_cell[name]):
                production = (
                    d(g["production_rate_mM_s"])
                    * factor
                    * hill(configs[name]["growth and decay"], "", cell_state, site)
                )
                basal = d(g["decay_rate_per_s"]) * factor * concentration / scale
                regulated = (
                    d(g["decay_max_per_s"])
                    * factor
                    * concentration
                    / scale
                    * hill(configs[name]["growth and decay"], "decay ", cell_state, site)
                )
                values.append(production - basal - regulated if g["enabled"] else Decimal(0))
                gross.append(
                    abs(production) + abs(basal) + abs(regulated) if g["enabled"] else Decimal(0)
                )
            growth[name], growth_gross[name] = values, gross
        reaction = []
        if definition["reactions"]:
            row = definition["reactions"][0]
            if (
                row["standard free energy"] != "None"
                or row["reactants"] != ["X"]
                or row["products"] != ["Y"]
            ):
                raise ValueError("Reference only implements the declared irreversible X to Y seam")
            reaction = [
                d(row["max rate"])
                * (value / d(row["Km reactants"][0]))
                / (1 + value / d(row["Km reactants"][0]))
                for value in old_cell["X"]
            ]
        rate = reaction or [Decimal(0)] * n
        delta = {
            name: [growth[name][j] + (-rate[j] if name == "X" else rate[j]) for j in range(n)]
            for name in names
        }
        rate_gross = {
            name: [growth_gross[name][j] + abs(rate[j]) for j in range(n)] for name in names
        }
        delta_rows = [[Decimal(0)] * n for _ in ions] + [delta[name] for name in names]
        gross_rows = [[Decimal(0)] * n for _ in ions] + [rate_gross[name] for name in names]

        def ghk(ca, cb, diffusion, distance, z, voltage, temperature):
            alpha = z * voltage * F / (R * temperature)
            exponential = (-alpha).exp()
            denominator = 1 - exponential
            factor = -diffusion * alpha / (distance * denominator)
            return factor * (cb - ca * exponential), abs(factor) * (abs(cb) + abs(ca * exponential))

        molecules, gross_molecules, balances = {}, {}, {}
        charge, charge_gross = [Decimal(0)] * n, [Decimal(0)] * n
        current = list(map(d, inputs["incoming_channel_current_A_m2"]))
        current_gross = list(map(abs, current))
        env_charge, env_charge_gross = [Decimal(0)] * sites, [Decimal(0)] * sites
        env_jx, env_jy, env_jx_gross, env_jy_gross = ([Decimal(0)] * sites for _ in range(4))
        publication = inputs["substances_affect_charge"]
        for row in configured:
            name, p = row["name"], row["parameters"]
            # Source update_intra(False) refreshes this membrane cache BEFORE
            # every rate is evaluated. Chemistry later changes bulk only.
            stale_membrane = [old_cell[name][i] for i in owner]
            cell = [old_cell[name][j] + delta[name][j] * dt for j in range(n)]
            cell_gross = [abs(old_cell[name][j]) + rate_gross[name][j] * dt for j in range(n)]
            membrane_flux, membrane_flux_gross = [], []
            if p["Dm"] != 0.0:
                vm = [value + 1e-25 for value in vm]
                z = d(float(p["z"]) + 1e-25)
                for j in range(m):
                    flux, gross = ghk(
                        old_env[name][mapping[j]],
                        stale_membrane[j],
                        d(p["Dm"]),
                        thickness,
                        z,
                        d(vm[j]),
                        runtime,
                    )
                    flux *= d(inputs["rho_channel"][j])
                    gross *= abs(d(inputs["rho_channel"][j]))
                    if not inputs["cluster_open"] and boundary[j]:
                        flux = gross = Decimal(0)
                    membrane_flux.append(flux)
                    membrane_flux_gross.append(gross)
            else:
                membrane_flux = [Decimal(0)] * m
                membrane_flux_gross = [Decimal(0)] * m
            for i in range(n):
                increment = (
                    sum((membrane_flux[j] * area[j] for j in cell_rows[i]), Decimal(0))
                    / volume[i]
                    * dt
                )
                bound = (
                    sum((membrane_flux_gross[j] * area[j] for j in cell_rows[i]), Decimal(0))
                    / volume[i]
                    * dt
                )
                cell[i] += increment
                cell_gross[i] += bound
            env = old_env[name][:]
            env_gross = list(map(abs, env))
            conservative = -dt * sum((membrane_flux[j] * area[j] for j in range(m)), Decimal(0))
            exchange = [Decimal(0)] * sites
            exchange_gross = [Decimal(0)] * sites
            fast = inputs["material_declaration"]["parameters"]["fast_update_ecm"]
            for site in range(sites):
                faces = [j for j, k in enumerate(mapping) if k == site]
                if not faces:
                    continue
                if fast:
                    total_area = sum((area[j] for j in faces), Decimal(0))
                    exchange[site] = -membrane_flux[faces[-1]] * total_area / env_volume * dt
                    exchange_gross[site] = (
                        membrane_flux_gross[faces[-1]] * total_area / env_volume * dt
                    )
                else:
                    exchange[site] = (
                        -sum((membrane_flux[j] * area[j] for j in faces), Decimal(0))
                        / env_volume
                        * dt
                    )
                    exchange_gross[site] = (
                        sum((membrane_flux_gross[j] * area[j] for j in faces), Decimal(0))
                        / env_volume
                        * dt
                    )
                env[site] += exchange[site]
                env_gross[site] += exchange_gross[site]
            exchange_amount = sum(exchange, Decimal(0)) * env_volume
            membrane = [cell[i] for i in owner]
            membrane_gross = [cell_gross[i] for i in owner]
            gap_flux, gap_flux_gross = [], []
            if not p["ignoreGJ"]:
                vgj = [value + 1e-25 for value in vgj]
                z = d(float(p["z"]) + 1e-25)
                for j in range(m):
                    diffusion = d(p["Dgj"]) * controls["gj_block"][j] * d(inputs["gap_open"][j])
                    value, bound = ghk(
                        membrane[j],
                        membrane[partner[j]],
                        diffusion,
                        length[j],
                        z,
                        d(vgj[j]),
                        configured_T,
                    )
                    if boundary[j]:
                        value = bound = Decimal(0)
                    gap_flux.append(value)
                    gap_flux_gross.append(bound)
                time = d(p["modify_time_factor"])
                for i in range(n):
                    increment = (
                        sum((-gap_flux[j] * area[j] for j in cell_rows[i]), Decimal(0))
                        / volume[i]
                        * dt
                        * time
                    )
                    bound = (
                        sum((gap_flux_gross[j] * area[j] for j in cell_rows[i]), Decimal(0))
                        / volume[i]
                        * dt
                        * time
                    )
                    cell[i] += increment
                    cell_gross[i] += bound
                membrane = [cell[i] for i in owner]
                membrane_gross = [cell_gross[i] for i in owner]
            else:
                gap_flux = [Decimal(0)] * m
                gap_flux_gross = [Decimal(0)] * m
            environment = ecm_environment(env, env_gross, p, inputs, grid, dt, runtime)
            env, env_gross = environment["after"], environment["gross"]
            fenvx, fenvy = environment["flux_x"], environment["flux_y"]
            molecules[name] = dict(
                c_cells=cell,
                cc_at_mem=membrane,
                c_env=env,
                flux_intra=copy.deepcopy(before[name]["flux_intra"]),
                f_mem=membrane_flux,
                f_gj=gap_flux,
                fenvx=fenvx,
                fenvy=fenvy,
                present_fields=[
                    "c_cells",
                    "cc_at_mem",
                    "c_env",
                    "flux_intra",
                    "f_mem",
                    "f_gj",
                    "fenvx",
                    "fenvy",
                ],
            )
            gross_molecules[name] = dict(
                c_cells=cell_gross,
                cc_at_mem=membrane_gross,
                c_env=env_gross,
                fenvx=environment["flux_x_gross"],
                fenvy=environment["flux_y_gross"],
                flux_intra=list(map(abs, before[name]["flux_intra"])),
                f_mem=membrane_flux_gross,
                f_gj=gap_flux_gross,
            )
            chemical_amount = sum((delta[name][i] * volume[i] * dt for i in range(n)), Decimal(0))
            directed_gap = (
                -sum((gap_flux[j] * area[j] for j in range(m)), Decimal(0))
                * dt
                * d(p["modify_time_factor"])
            )
            old_amount = (
                sum((old_cell[name][i] * volume[i] for i in range(n)), Decimal(0))
                + sum(old_env[name], Decimal(0)) * env_volume
            )
            new_amount = (
                sum((cell[i] * volume[i] for i in range(n)), Decimal(0))
                + sum(env, Decimal(0)) * env_volume
            )
            defect = exchange_amount - conservative
            source_terms = (
                chemical_amount
                + directed_gap
                + defect
                + environment["clamp_amount"]
                + environment["transport_amount"]
                + environment["smoothing_amount"]
            )
            true_volume = grid["true_environment_volume_m3"]
            true_delta = sum(
                ((cell[i] - old_cell[name][i]) * volume[i] for i in range(n)), Decimal(0)
            ) + sum(
                ((env[k] - old_env[name][k]) * true_volume[k] for k in range(sites)), Decimal(0)
            )
            balances[name] = dict(
                initial_amount_mol=old_amount,
                final_amount_mol=new_amount,
                chemical_source_mol=chemical_amount,
                directed_GJ_change_mol=directed_gap,
                native_environment_exchange_mol=exchange_amount,
                conservative_environment_exchange_mol=conservative,
                fast_exchange_defect_mol=defect,
                boundary_clamp_change_mol=environment["clamp_amount"],
                collocated_transport_change_mol=environment["transport_amount"],
                smoothing_change_mol=environment["smoothing_amount"],
                source_effective_residual_mol=new_amount - old_amount - source_terms,
                native_true_volume_total_change_mol=true_delta,
                native_true_volume_gross_mol=sum(
                    ((abs(cell[i]) + abs(old_cell[name][i])) * volume[i] for i in range(n)),
                    Decimal(0),
                )
                + sum(
                    ((abs(env[k]) + abs(old_env[name][k])) * true_volume[k] for k in range(sites)),
                    Decimal(0),
                ),
                site_volume_m3=env_volume,
                physical_global_conservation_credit=False,
                global_GJ_zero_assumed=False,
            )
            if publication:
                z, scale = d(p["z"]), d(p["scale_factor"])
                for i in range(n):
                    charge[i] += F * cell[i] * z * scale
                    charge_gross[i] += abs(F * z * scale) * cell_gross[i]
                for j in range(m):
                    current[j] += -z * membrane_flux[j] * F * scale + z * gap_flux[j] * F * scale
                    current_gross[j] += abs(z * F * scale) * (
                        membrane_flux_gross[j] + gap_flux_gross[j]
                    )
                fx_flat = flatten_flux(fenvx)
                fy_flat = flatten_flux(fenvy)
                gx_flat = flatten_flux(environment["flux_x_gross"])
                gy_flat = flatten_flux(environment["flux_y_gross"])
                for k in range(sites):
                    env_charge[k] += F * env[k] * z * scale
                    env_charge_gross[k] += abs(F * z * scale) * env_gross[k]
                    env_jx[k] += fx_flat[k] * z * F * scale
                    env_jy[k] += fy_flat[k] * z * F * scale
                    env_jx_gross[k] += gx_flat[k] * abs(z * F * scale)
                    env_jy_gross[k] += gy_flat[k] * abs(z * F * scale)
        return plain(
            dict(
                independent_geometry=grid,
                extra_rho_env=env_charge,
                extra_rho_env_gross=env_charge_gross,
                extra_Jenv_x=env_jx,
                extra_Jenv_y=env_jy,
                extra_Jenv_x_gross=env_jx_gross,
                extra_Jenv_y_gross=env_jy_gross,
                molecules_after=molecules,
                gross_molecules=gross_molecules,
                controls_after=controls,
                control_writes=writes,
                rhs=dict(
                    growth_rates=[growth[name] for name in names],
                    reaction_rates=[reaction] if reaction else [],
                    all_rates=[growth[name] for name in names] + ([reaction] if reaction else []),
                ),
                delta_conc=delta_rows,
                delta_gross=gross_rows,
                extra_rho_cells=charge,
                extra_rho_gross=charge_gross,
                extra_J_mem=current,
                extra_J_gross=current_gross,
                voltage_after_V=vm,
                junction_voltage_after_V=vgj,
                balances=balances,
                executed_chemistry=bool(definition["reactions"])
                or any(row["growth"]["enabled"] for row in configured),
                decimal_precision=ctx.prec,
                carried_reference_forms=0,
                conditional_actual_pre_network_only=True,
                no_upstream_or_trajectory_accuracy_claim=True,
            )
        )


def evaluate(inputs, *, refinement=1):
    if inputs.get("mode") == "cold_initialization":
        return cold(inputs, refinement=refinement)
    return warm(inputs, refinement=refinement)


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
            raise ImportError("Independent molecule reference import denied: " + name)
        return original(name, *rest, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError("Independent molecule reference import denied: " + fullname)

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
