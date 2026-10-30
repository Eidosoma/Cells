"""Independent Decimal transporter rates and ordered commits from actual inputs.

The two precision forms start afresh at the captured pre-transporter state.
The subsequent chemistry uses its frozen separate conditional reference.
"""

import copy
from decimal import localcontext

from validation.betse.betse_normal_molecule_join_reference import evaluate as molecule_evaluate
from validation.betse.betse_normal_molecule_join_reference import plain
from validation.betse.betse_normal_network_join_reference import d


def regulation(config, concentrations, site):
    regular, independent, inhibition, direct = d(1), d(0), d(1), []
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


def transporters(inputs, *, refinement=1):
    if refinement not in (1, 2) or not inputs["conditioned_before_model_transporters"]:
        raise ValueError("Require an actual pre-transporter conditional input")
    with localcontext() as context:
        context.prec = 90 if refinement == 1 else 140
        definition, geometry = inputs["definition"], inputs["geometry"]
        rows = definition["transporters"]
        if any(row["apply to"] != "all" or row["reaction zone"] != "cell" for row in rows):
            raise ValueError("Positive reference covers all-target no-ECM cell transporters")
        owner = geometry["owner"]
        area, volume, membrane_volume = (
            [d(value) for value in geometry[key]]
            for key in ("membrane_area_m2", "cell_volume_m3", "membrane_volume_m3")
        )
        n, m = len(volume), len(owner)
        counts = [owner.count(index) for index in range(n)]
        dt, F, R, temperature, bath_volume = (
            d(inputs[key]) for key in ("dt_s", "F", "R", "runtime_temperature_K", "bath_volume_m3")
        )
        voltage = [d(value) for value in inputs["values_before"]["voltage_V"]]
        density = [d(value) for value in inputs["rho_pump"]]
        # Valence is supplied separately by the bound configured state, never
        # inferred from rates, generated strings or captured output metadata.
        valence = {
            name: d(value) for name, value in zip(inputs["ion_ids"], inputs["valence"], strict=True)
        }
        valence.update({row["name"]: d(row["parameters"]["z"]) for row in definition["molecules"]})
        state = {
            zone: {name: [d(value) for value in values] for name, values in substances.items()}
            for zone, substances in inputs["concentrations_before"].items()
        }
        gross = {
            zone: {name: list(map(abs, values)) for name, values in substances.items()}
            for zone, substances in state.items()
        }
        current = [d(value) for value in inputs["extra_current_before_A_m2"]]
        current_gross = list(map(abs, current))
        frames, ledgers = [], []

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
            net_z, forward, quotient, electrical = d(0), [d(1)] * m, [d(1)] * m, [d(0)] * m
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
                    external, nu = species in moved, d(coefficient)
                    zone = "env_concs" if external else "mem_concs"
                    terms.append((sign, species, external, nu))
                    for j in range(m):
                        concentration = state[zone][species][j]
                        if concentration <= 0:
                            raise ValueError("Positive participating concentrations are required")
                        q_term = d(1e-3) * concentration**nu
                        quotient[j] = quotient[j] * q_term if sign > 0 else quotient[j] / q_term
                        if sign < 0:
                            load = (concentration / d(km)) ** nu
                            forward[j] *= load / (1 + load)
                        if external:
                            electrical[j] -= sign * nu * valence[species] * F * voltage[j]
                    if external:
                        net_z += sign * nu * valence[species]
            flux, energy, alpha, flux_gross = [], [], [], []
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
                species: dict(bulk=d(0), bath=d(0), effective=d(0), buffer=[d(0)] * m)
                for species in state["cell_concs"]
            }
            counters = {-1: 0, 1: 0}
            for sign, species, external, nu in terms:
                delta = [sign * nu * value for value in divergence]
                delta_gross = [nu * value for value in divergence_gross]
                if external:
                    for j, index in enumerate(owner):
                        change = delta[index] * dt
                        state["env_concs"][species][j] += change
                        gross["env_concs"][species][j] += delta_gross[index] * dt
                    predicted[species]["bath"] += (
                        sign
                        * nu
                        * dt
                        * bath_volume
                        / m
                        * sum((counts[i] * divergence[i] for i in range(n)), d(0))
                    )
                    predicted[species]["effective"] += (
                        sign * nu * dt * sum((flux[j] * area[j] for j in range(m)), d(0))
                    )
                else:
                    for i in range(n):
                        change = delta[i] * dt
                        state["cell_concs"][species][i] += change
                        gross["cell_concs"][species][i] += delta_gross[i] * dt
                    for j in range(m):
                        # Literal source omits nu in this membrane-buffer write.
                        change = sign * flux[j] * area[j] / membrane_volume[j] * dt
                        state["mem_concs"][species][j] += change
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
                )
            )
            frame("after", name, None, None, flux, flux_gross)
        return plain(
            dict(
                concentrations_after=state,
                gross=gross,
                extra_current_after_A_m2=current,
                current_gross=current_gross,
                frames=frames,
                ledgers=ledgers,
                decimal_precision=context.prec,
                fresh_conditional_reference=True,
                carried_reference_forms=0,
                physical_global_conservation_credit=False,
            )
        )


def evaluate(inputs, *, refinement=1):
    if inputs.get("conditioned_before_model_transporters"):
        return transporters(inputs, refinement=refinement)
    return molecule_evaluate(inputs, refinement=refinement)


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
