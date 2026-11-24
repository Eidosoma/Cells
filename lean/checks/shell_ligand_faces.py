"""Compare FR-46 shell admission with the two-ligand Lean witness, using the NumPy rate kernel."""

import json
import math

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages_v2 import balance, model
from tests.assembly_lineage_v2_fixtures import definition, species, step
from tests.unit.test_assembly_lineages_v2_geometry import shell_world


def shell(binding_y):
    world = shell_world()
    del world["rate_factor"]
    wall = {"R": {"r": 1}, "A": {"r": 1, "x": 1}, "C": {"r": 1, "x": 1, "y": 1},
            "D": {"r": 1, "x": 1, "y": 1}, "B": {"r": 1, "y": 1}}
    world["species"] = [
        species("X", {"x": 1}, solution=0), species("Y", {"y": 1}, solution=0),
        *(species(name, counts, bilayer=0) for name, counts in wall.items()),
    ]
    phases = world["phases"]
    phases["pool"]["species"] = [{"id": "X", "kind": "finite"}]
    phases["lumen"]["species"] = ["X", "Y"]
    phases["membrane"]["species"] = list(wall)
    world["founder"] = {
        "X@pool": 1, "X@lumen": 0, "Y@lumen": 1,
        **{f"{name}@membrane": int(name == "R") for name in wall},
    }
    # The engine declares binding forwards. The path uses inner X dissociation in reverse.
    pairs = [("outer_x", "R", "A", "X", "outer"), ("inner_x", "B", "D", "X", "inner")]
    if binding_y:
        pairs.append(("inner_y", "A", "C", "Y", "inner"))
    world["sites"] = [{"site": free, "complex": bound, "face": face}
                      for _, free, bound, _, face in pairs]
    world["steps"] = []
    for name, free, bound, ligand, face in pairs:
        phase = "pool" if face == "outer" else "lumen"
        world["steps"].append(step(name, {f"{ligand}@{phase}": 1, f"{free}@membrane": 1},
                                   {f"{bound}@membrane": 1}, 1, locus="membrane"))
    world["steps"].append(step("isomer", {"C": 1}, {"D": 1}, 1, phase="membrane"))
    return definition(world, molecules=16)


def follow_path(spec):
    world = spec.model.world
    indices = {p.name: i for i, p in enumerate(world.places)}
    steps = {st.id: (i, st) for i, st in enumerate(world.steps)}
    structure, layout = model.structure(spec), model.layout(spec)
    counts = model.founder(spec).copy()
    rates = []
    for name, reverse in (("outer_x", False), ("inner_y", False),
                          ("isomer", False), ("inner_x", True)):
        i, st = steps[name]
        log_rate = balance.host_log_rates(counts, layout, structure)[i + (structure.steps if reverse else 0)]
        if not math.isfinite(log_rate):
            raise ValueError(f"{name} has no finite log rate on the proposed path")
        rates.append(math.exp(log_rate))
        consumed, produced = (st.products, st.reactants) if reverse else (st.reactants, st.products)
        for place, number in consumed:
            if counts[indices[place]] < number:
                raise ValueError(f"{name} cannot consume {number} at {place}")
            counts[indices[place]] -= number
        for place, number in produced:
            counts[indices[place]] += number
    return {"rates_per_s": rates, "X_pool_final": int(counts[indices["X@pool"]]),
            "X_lumen_final": int(counts[indices["X@lumen"]]), "B_final": int(counts[indices["B@membrane"]])}


def compare(binding_y):
    try:
        spec = parse_spec(shell(binding_y))
    except ConfigError as error:
        reason = str(error)
        return {"admitted": False, "reason": reason, "agrees": binding_y and "carrier" in reason.lower()}
    row = {"admitted": True, "agrees": not binding_y}
    if binding_y:
        row.update(follow_path(spec))
    return row


if __name__ == "__main__":
    rows = {"with_Y_binding": compare(True), "without_Y_binding": compare(False)}
    print(json.dumps(rows, indent=2, allow_nan=False))
    raise SystemExit(0 if all(r["agrees"] for r in rows.values()) else 1)
