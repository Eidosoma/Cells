# ruff: noqa: F841
"""Independent actual pre-GRN chemistry prefix; transport is outside this raw check.

Existing qualified scalar RHS/delta equations and fixed budgets are unchanged.
The historical no_negs exception is a NaN refusal after X transport, not a
refusal of finite negative concentration (the source clips finite negatives).
"""

import argparse
import json
from decimal import Decimal, localcontext
from pathlib import Path

from validation.betse import betse_ecm_grn_reference as grn

d = grn.d
_alpha = grn._alpha
hill = grn.hill
plain = grn.plain
derive_geometry = grn.derive_geometry


def chemistry_prefix(inputs, *, refinement=1):
    if refinement not in (1, 2) or not inputs["conditioned_before_model_network"]:
        raise ValueError("Require actual immutable pre-network inputs")
    with localcontext() as ctx:
        ctx.prec = 100 if refinement == 1 else 160
        definition, before = (inputs["definition"], inputs["molecule_states_before"])
        configured = definition["molecules"]
        names, ions = ([row["name"] for row in configured], inputs["ion_ids"])
        assert set(names) == {"X", "Y"} and len(names) == 2
        grid = derive_geometry(
            inputs["material_declaration"]["environment_geometry_definition"], precision=ctx.prec
        )
        mapping, shape = (grid["membrane_to_grid"], grid["shape"])
        sites = shape[0] * shape[1]
        geometry = inputs["molecular_geometry"]
        owner, partner, boundary = (geometry["owner"], geometry["partner"], geometry["boundary"])
        n, m = (len(geometry["cell_volume_m3"]), len(owner))
        cell_rows = [[j for j, index in enumerate(owner) if index == i] for i in range(n)]
        area, volume, length = (
            [d(v) for v in geometry[key]]
            for key in ("membrane_area_m2", "cell_volume_m3", "gap_length_m")
        )
        dt, F, R = (d(inputs["dt_s"]), d(inputs["F"]), d(inputs["R"]))
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
        growth, growth_gross = ({}, {})
        for row in configured:
            name, parameters, g = (row["name"], row["parameters"], row["growth"])
            if (
                any(
                    (
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
                )
                or parameters["Mu_mem"] != 0
                or parameters["u_mt"] != 0
            ):
                raise ValueError(
                    "Reference requires the declared instant-mixing passive mover seam"
                )
            factor, scale = (d(parameters["modify_time_factor"]), d(g["scale_factor"]))
            values, gross = ([], [])
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
            growth[name], growth_gross[name] = (values, gross)
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
        chemical = {
            name: [old_cell[name][j] + delta[name][j] * dt for j in range(n)] for name in names
        }
        chemical_gross = {
            name: [abs(old_cell[name][j]) + rate_gross[name][j] * dt for j in range(n)]
            for name in names
        }
        return plain(
            dict(
                mode="network_chemistry_prefix",
                rhs=dict(
                    growth_rates=[growth[name] for name in names],
                    reaction_rates=[reaction] if reaction else [],
                    all_rates=[growth[name] for name in names] + ([reaction] if reaction else []),
                ),
                delta_conc=delta_rows,
                delta_gross=gross_rows,
                chemical_commit=chemical,
                chemical_gross=chemical_gross,
                decimal_precision=ctx.prec,
                carried_reference_forms=0,
                fresh_conditional_reference=True,
                complete_network_return_predicted=False,
                transport_evaluations=0,
                physical_global_conservation_credit=False,
            )
        )


def main():
    import builtins
    import importlib.abc
    import sys

    from validation.betse.betse_normal_channel_join_runtime import inventory

    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--refinement", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    denied = {"cells", "betse", "numpy", "jax", "jaxlib"}
    original = builtins.__import__

    def guarded(name, *rest, **kwargs):
        if name.split(".")[0] in denied:
            raise ImportError("Independent chemistry-prefix import denied: " + name)
        return original(name, *rest, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in denied:
                raise ImportError("Independent chemistry-prefix import denied: " + fullname)

    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())
    result = chemistry_prefix(json.loads(args.inputs.read_text()), refinement=args.refinement)
    loaded = [name for name in sys.modules if name.split(".")[0] in denied]
    assert not loaded
    result.update(
        production_imports_denied=True, loaded_production_modules=loaded, runtime=inventory()
    )
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()

# Explicit read projection for the chemistry-prefix interface. Full raw source
# input is archived separately; unconsumed NaN ordinary-flux arrays stay there.
CHEMISTRY_INPUT_KEYS = (
    "conditioned_before_model_network",
    "definition",
    "molecule_states_before",
    "ion_ids",
    "material_declaration",
    "molecular_geometry",
    "dt_s",
    "F",
    "R",
    "runtime_temperature_K",
    "configured_temperature_K",
    "membrane_thickness_m",
    "valence",
    "controls_before",
)
CHEMISTRY_VALUE_KEYS = (
    "voltage_V",
    "junction_voltage_V",
    "cell_mol_m3",
    "membrane_mol_m3",
    "environment_mol_m3",
)
