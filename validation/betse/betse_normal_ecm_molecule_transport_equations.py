# ruff: noqa: E501
"""Independent Decimal ECM rate, ordered commit and explicit native-defect books."""

import copy
from decimal import localcontext

from validation.betse.betse_environment_field_reference import geometry as derive_geometry
from validation.betse.betse_normal_molecule_join_reference import plain
from validation.betse.betse_normal_network_join_reference import d


def regulation(config, concentrations, site):
    regular, independent, inhibition, direct = (d(1), d(0), d(1), [])
    for activating, label, km_key, exponent_key in (
        (True, "transporter activators", "activator Km", "activator n"),
        (False, "transporter inhibitors", "inhibitor Km", "inhibitor n"),
    ):
        names = config.get(label)
        if names in (None, "None") or names == []:
            continue
        for raw_name, km, exponent in zip(names, config[km_key], config[exponent_key], strict=True):
            name = raw_name[:-1] if raw_name.endswith("*") else raw_name
            suffix = name[-1:] if name.endswith(("!", "&")) else ""
            name = name[:-1] if suffix else name
            value = concentrations["mem_concs"][name][site]
            if suffix == "&":
                direct.append(value if activating else -value)
                continue
            load = (value / d(km)) ** d(exponent)
            if activating:
                if suffix == "!":
                    independent += load / (1 + load)
                else:
                    regular *= load / (1 + load)
            else:
                inhibition /= 1 + load
    return (regular + independent) * inhibition * (sum(direct, d(0)) if direct else d(1))


def evaluate(inputs, *, refinement=1, retain_decimal=None):
    if refinement not in (1, 2) or not inputs["conditioned_before_model_transporters"]:
        raise ValueError("Require complete actual pre-transporter inputs")
    with localcontext() as context:
        context.prec = 100 if refinement == 1 else 160
        definition, geometry = (inputs["definition"], inputs["geometry"])
        rows = definition["transporters"] or []
        if any((row["apply to"] != "all" or row["reaction zone"] != "cell" for row in rows)):
            raise ValueError(
                "Positive conditional reference covers all-target ECM cell transporters"
            )
        owner = geometry["owner"]
        area, volume, membrane_volume = (
            [d(value) for value in geometry[key]]
            for key in ("membrane_area_m2", "cell_volume_m3", "membrane_volume_m3")
        )
        n, m = (len(volume), len(owner))
        raw = inputs["material_declaration"]
        external = raw["environment_geometry_definition"]
        grid = derive_geometry(external, precision=context.prec)
        mapping = grid["membrane_to_grid"]
        sites = len(grid["grid_points_m"])
        site_volume = d(external["parameters"]["cell_height_m"]) * grid["delta_m"] ** 2
        fast = raw["parameters"]["fast_update_ecm"]
        dt, F, R, temperature = (
            d(inputs[key]) for key in ("dt_s", "F", "R", "runtime_temperature_K")
        )
        voltage = [d(value) for value in inputs["values_before"]["voltage_V"]]
        density = [d(value) for value in inputs["rho_pump"]]
        valence = {
            name: d(value) for name, value in zip(inputs["ion_ids"], inputs["valence"], strict=True)
        }
        valence.update({row["name"]: d(row["z"]) for row in definition["biomolecules"]})
        charge_scale = {name: d(1) for name in inputs["ion_ids"]}
        charge_scale.update(
            {row["name"]: d(row.get("scale factor", 1.0)) for row in definition["biomolecules"]}
        )
        state = {
            zone: {name: [d(v) for v in values] for name, values in substances.items()}
            for zone, substances in inputs["concentrations_before"].items()
        }
        gross = {
            zone: {name: list(map(abs, values)) for name, values in substances.items()}
            for zone, substances in state.items()
        }
        current = [d(value) for value in inputs["extra_current_before_A_m2"]]
        current_gross = list(map(abs, current))
        frames, ledgers = ([], [])

        def project(values):
            if fast:
                last = [d(0)] * sites
                for j, site in enumerate(mapping):
                    last[site] = values[j]
                return [
                    last[k] * grid["membrane_area_per_site_m2"][k] / site_volume
                    for k in range(sites)
                ]
            return [
                sum((values[j] * area[j] for j in range(m) if mapping[j] == k), d(0)) / site_volume
                for k in range(sites)
            ]

        def frame(stage, name, term, delta, flux, flux_gross, delta_gross=None):
            frames.append(
                dict(
                    stage=stage,
                    name=name,
                    term=term,
                    delta=delta,
                    delta_gross=delta_gross,
                    flux=flux[:],
                    flux_gross=flux_gross[:],
                    concentrations=copy.deepcopy(state),
                    gross=copy.deepcopy(gross),
                    extra_current_A_m2=current[:],
                    current_gross=current_gross[:],
                )
            )

        for config in rows:
            name = config["name"]
            initial = copy.deepcopy(state)
            net_z, forward, quotient, electrical = (d(0), [d(1)] * m, [d(1)] * m, [d(0)] * m)
            terms = []
            for sign, role, coefficients, km_key, transferred in (
                (-1, "reactants", "reactant multipliers", "Km reactants", "transfered into cell"),
                (1, "products", "product multipliers", "Km products", "transfered out of cell"),
            ):
                moved = config[transferred]
                moved = [] if moved in (None, "None") else moved
                for species, coefficient, km in zip(
                    config[role], config[coefficients], config[km_key], strict=True
                ):
                    external, nu = (species in moved, d(coefficient))
                    zone = "env_concs" if external else "mem_concs"
                    terms.append((sign, species, external, nu))
                    for j in range(m):
                        concentration = state[zone][species][mapping[j] if external else j]
                        if concentration <= 0:
                            raise ValueError("Positive participating concentrations are required")
                        q_term = d(0.001) * concentration**nu
                        quotient[j] = quotient[j] * q_term if sign > 0 else quotient[j] / q_term
                        if sign < 0:
                            load = (concentration / d(km)) ** nu
                            forward[j] *= load / (1 + load)
                        if external:
                            electrical[j] -= sign * nu * valence[species] * F * voltage[j]
                    if external:
                        net_z += sign * nu * valence[species]
            flux, energy, alpha, flux_gross = ([], [], [], [])
            for j in range(m):
                value = regulation(config, state, j)
                alpha.append(value)
                standard = config["standard free energy"]
                reversible = standard not in (None, "None")
                equilibrium = (
                    (-(d(standard) + electrical[j]) / (R * temperature)).exp()
                    if reversible
                    else d(1)
                )
                reversal = 1 - quotient[j] / equilibrium if reversible else d(1)
                prefactor = density[j] * d(config["max rate"]) * value * forward[j]
                flux.append(prefactor * reversal)
                flux_gross.append(
                    abs(prefactor) * (1 + abs(quotient[j] / equilibrium) if reversible else d(1))
                )
                energy.append(
                    d(standard) + electrical[j] + R * temperature * quotient[j].ln()
                    if reversible
                    else d(0)
                )
            divergence = [
                sum((flux[j] * area[j] for j, index in enumerate(owner) if index == i), d(0))
                / volume[i]
                for i in range(n)
            ]
            divergence_gross = [
                sum((flux_gross[j] * area[j] for j, index in enumerate(owner) if index == i), d(0))
                / volume[i]
                for i in range(n)
            ]
            for j in range(m):
                increment = net_z * flux[j] * F
                current[j] += increment
                current_gross[j] += abs(net_z * F) * flux_gross[j]
            frame("current", name, None, None, flux, flux_gross)
            predicted = {
                species: dict(
                    bulk=d(0), environment=d(0), requested_environment=d(0), buffer=[d(0)] * m
                )
                for species in state["cell_concs"]
            }
            counters = {-1: 0, 1: 0}
            for sign, species, external, nu in terms:
                if external:
                    delta = [sign * nu * value for value in project(flux)]
                    delta_gross = [nu * value for value in project(flux_gross)]
                    for k in dict.fromkeys(mapping):
                        state["env_concs"][species][k] += delta[k] * dt
                        gross["env_concs"][species][k] += delta_gross[k] * dt
                    predicted[species]["environment"] += dt * site_volume * sum(delta, d(0))
                    predicted[species]["requested_environment"] += (
                        sign * nu * dt * sum((flux[j] * area[j] for j in range(m)), d(0))
                    )
                else:
                    delta = [sign * nu * value for value in divergence]
                    delta_gross = [nu * value for value in divergence_gross]
                    for i in range(n):
                        state["cell_concs"][species][i] += delta[i] * dt
                        gross["cell_concs"][species][i] += delta_gross[i] * dt
                    for j in range(m):
                        state["mem_concs"][species][j] += (
                            sign * flux[j] * area[j] / membrane_volume[j] * dt
                        )
                        gross["mem_concs"][species][j] += (
                            flux_gross[j] * area[j] / membrane_volume[j] * dt
                        )
                        predicted[species]["buffer"][j] += (
                            sign * (1 - nu) * flux[j] * area[j] / membrane_volume[j] * dt
                        )
                    predicted[species]["bulk"] += (
                        sign * nu * dt * sum((flux[j] * area[j] for j in range(m)), d(0))
                    )
                frame(
                    "reactant_commit" if sign < 0 else "product_commit",
                    name,
                    counters[sign],
                    delta[:],
                    flux,
                    flux_gross,
                    delta_gross[:],
                )
                counters[sign] += 1
            charge_bulk = F * sum(
                (valence[s] * charge_scale[s] * p["bulk"] for s, p in predicted.items()), d(0)
            )
            charge_environment = F * sum(
                (valence[s] * charge_scale[s] * p["environment"] for s, p in predicted.items()),
                d(0),
            )
            ledgers.append(
                dict(
                    name=name,
                    initial=initial,
                    final=copy.deepcopy(state),
                    predicted=predicted,
                    flux=flux,
                    net_z=net_z,
                    forward=forward,
                    regulation=alpha,
                    source_energy_J_mol=energy,
                    quotient=quotient,
                    electrical_J_mol=electrical,
                    charge_bulk_change_C=charge_bulk,
                    charge_environment_change_C=charge_environment,
                    source_current_transfer_C=dt
                    * F
                    * net_z
                    * sum((flux[j] * area[j] for j in range(m)), d(0)),
                    physical_global_conservation_credit=False,
                )
            )
            frame("after", name, None, None, flux, flux_gross)
        result = dict(
            concentrations_after=state,
            gross=gross,
            extra_current_after_A_m2=current,
            current_gross=current_gross,
            frames=frames,
            ledgers=ledgers,
            independent_grid=grid,
            site_volume_m3=site_volume,
            decimal_precision=context.prec,
            fresh_conditional_reference=True,
            carried_reference_forms=0,
            physical_global_conservation_credit=False,
        )
        if retain_decimal is not None:
            retain_decimal(copy.deepcopy(result))
        return plain(result)
