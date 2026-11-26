"""Bind the Lean enzyme example to the Cells fixture and check one compiled CPU half-step."""

import copy
import json
import math
import subprocess
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.schedule import control_values
from cells.registry.models import get_model
from tests.unit.test_species_reactions_halfstep import amount
from validation.tissue import species_reactions_fixtures as fixtures

SPECIES = ("E", "S", "C", "P")
REACTIONS = ("binding", "catalysis")
WEIGHTS = {"X": "substrateUnits", "Y": "enzymeUnits"}
TRACE_MM = 1e-12


def signed_column(reaction):
    return [reaction["products"].get(s, 0) - reaction["reactants"].get(s, 0) for s in SPECIES]


def fixture_tables(block):
    reactions = {r["id"]: r for r in block["reactions"]}
    moieties = {s["id"]: s["moieties"] for s in block["species"]}
    groups = {g for counts in moieties.values() for g in counts}
    if (
        set(reactions) != set(REACTIONS)
        or set(moieties) != set(SPECIES)
        or groups != WEIGHTS.keys()
    ):
        raise AssertionError("The enzyme fixture and the Lean example have different declarations")
    columns = {r: signed_column(reactions[r]) for r in REACTIONS}
    weights = {g: [moieties[s].get(g, 0) for s in SPECIES] for g in WEIGHTS}
    return columns, weights


def check_lean_tables(columns, weights):
    """Ask the Lean kernel to equate its two columns and two weight rows to the raw integers."""
    functions = {f"net .{r}": column for r, column in columns.items()}
    functions.update({WEIGHTS[g]: row for g, row in weights.items()})
    species = "[" + ", ".join(f".{s}" for s in SPECIES) + "]"
    source = ["import CellsProofs.Chemistry.Enzyme", "open CellsProofs.Chemistry.Enzyme"]
    for function, values in functions.items():
        source.append(f"example : List.map ({function}) {species} = {values} := by decide")
    project = Path(__file__).resolve().parents[1]
    subprocess.run(
        ["lake", "--quiet", "build", "+CellsProofs.Chemistry.Enzyme"], cwd=project, check=True
    )
    subprocess.run(
        ["lake", "env", "lean", "-DwarningAsError=true", "--stdin"],
        cwd=project,
        input="\n".join(source) + "\n",
        text=True,
        check=True,
    )


def half_step(raw, columns, weights):
    spec = parse_spec(raw)
    model = get_model(spec.model)
    (declaration,) = spec.model.operators
    (operator,) = model.operators
    routes = [r.reaction for r in declaration.routes]
    if sorted(routes) != sorted(REACTIONS) or any(r.node != "cell_0" for r in declaration.routes):
        raise AssertionError("Expected one binding and one catalytic route at cell_0")
    if any(r.kind != "closed" for r in declaration.reactions):
        raise AssertionError("Cells must admit both reactions as closed")
    start, parameters = model.initial_values(spec)
    schedule = control_values(spec, [0.0])
    control = jax.tree.map(lambda field: field[0], schedule)
    h = spec.execution.dt / 2
    advance = jax.jit(lambda state, c: operator.half_step(state, h, c, parameters, xp=jnp))
    end, valid = advance(start, control)
    if not bool(valid) or end.amount_increment.dtype != np.float64:
        raise AssertionError("Expected an admitted float64 reaction half-step")
    extents = dict(
        zip(routes, map(float, end.reaction_extent_fmol - start.reaction_extent_fmol), strict=True)
    )

    before = np.array([amount(spec, start, parameters, s, "cell_0") for s in SPECIES])
    after = np.array([amount(spec, end, parameters, s, "cell_0") for s in SPECIES])
    change = after - before
    expected = [math.fsum(columns[r][i] * extents[r] for r in routes) for i in range(len(SPECIES))]
    # Same anchored amount resolution and four-species moiety tolerance as the upstream ledger test.
    resolution = 8 * max(np.spacing(before))
    tolerance = 4 * resolution
    if not all(math.isfinite(x) and x > tolerance for x in extents.values()):
        raise AssertionError(f"The check needs two resolved forward extents, got {extents}")
    np.testing.assert_allclose(change, expected, rtol=1e-12, atol=resolution)
    residuals = {g: math.fsum(change * row) for g, row in weights.items()}
    for g, residual in residuals.items():
        np.testing.assert_allclose(residual, 0, rtol=0, atol=tolerance, err_msg=g)
    return {
        "backend": end.amount_increment.device.platform,
        "dtype": end.amount_increment.dtype.name,
        "half_step_s": h,
        "extent_fmol": extents,
        "species_change_fmol": dict(zip(SPECIES, change.tolist(), strict=True)),
        "max_species_residual_fmol": float(np.max(np.abs(change - expected))),
        "inventory_residual_fmol": residuals,
        "inventory_tolerance_fmol": float(tolerance),
    }


def missing_enzyme(raw, weights):
    """Remove E from the catalytic products and check the two unit counts and engine admission."""
    damaged = copy.deepcopy(raw)
    (block,) = damaged["model"]["operators"]
    catalysis = next(r for r in block["reactions"] if r["id"] == "catalysis")
    del catalysis["products"]["E"]
    column = signed_column(catalysis)
    change = {g: sum(a * b for a, b in zip(row, column, strict=True)) for g, row in weights.items()}
    if change != {"X": 0, "Y": -1}:
        raise AssertionError(f"Unexpected stoichiometry in the missing-enzyme control: {change}")
    try:
        parse_spec(damaged)
    except ConfigError as error:
        if "reaction catalysis is unbalanced in its declared moieties" not in str(error):
            raise
        return {"inventory_change_per_catalytic_event": change, "engine_admission": "refused"}
    raise AssertionError("Cells accepted catalysis with a missing enzyme")


if __name__ == "__main__":
    raw = fixtures.enzyme_recipe(TRACE_MM)
    (block,) = raw["model"]["operators"]
    if (
        raw["model"]["id"] != "cells.model.resolved_pump_composite@1"
        or block["law"] != "cells.operator.local_species_reactions@1"
    ):
        raise AssertionError("Unexpected enzyme fixture model or operator")
    columns, weights = fixture_tables(block)
    check_lean_tables(columns, weights)
    jax.config.update("jax_enable_x64", True)
    with jax.default_device(jax.devices("cpu")[0]):
        step = half_step(raw, columns, weights)
    print(
        json.dumps(
            {
                "model": raw["model"]["id"],
                "operator": block["law"],
                "trace_mM": TRACE_MM,
                "species_order": SPECIES,
                "lean_checked_columns": columns,
                "lean_checked_weights": weights,
                "cell_0": step,
                "missing_enzyme": missing_enzyme(raw, weights),
            },
            indent=2,
            allow_nan=False,
        )
    )
