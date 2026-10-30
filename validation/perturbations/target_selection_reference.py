"""Independent ordered-owner expansion from externally captured permutations.

No Cells, JAX, NumPy or random imports. This checks selection and target order;
RNG transitions are compared separately with the pinned executable source sites.
It does not claim an independent implementation of either random generator.
"""

from copy import deepcopy


def evaluate(raw, start_order, permutations):
    layout = raw["layout"]
    cells, membranes, environments = (
        layout[key] for key in ("cell_ids", "membrane_ids", "environment_ids")
    )
    indices = {name: i for i, name in enumerate(cells)}
    order, targets, aliases = list(start_order), {}, []
    dm = deepcopy(raw["initial_membrane_m2_s"])
    for index, row in enumerate([raw["default"], *raw["profiles"]] if raw["enabled"] else []):
        kind = "all" if index == 0 else row["picker"]
        if kind == "all":
            selected = list(order)
            aliases.append(row["name"])
        elif kind == "percent":
            order = list(permutations[row["name"]])
            assert len(order) == len(cells) and set(order) == set(cells)
            selected = order[: int((row["percent"] / 100) * len(cells))]
        elif kind == "indices":
            selected = [cells[value] for value in row["indices"]]
        else:
            raise ValueError("Independent random selection panel covers ALL/PERCENT/INDICES")
        mem_indices = [m for name in selected for m in layout["cell_membranes"][indices[name]]]
        declared = bool(selected) and raw["is_ecm"]
        env = (
            [environments[layout["membrane_environment"][m]] for m in mem_indices]
            if declared
            else []
        )
        targets[row["name"]] = dict(
            cells=selected,
            picked_cells=list(selected),
            membranes=[membranes[m] for m in mem_indices],
            environments=env,
            environment_declared=declared,
        )
        for ion, enabled in enumerate(raw["ion_enabled"]):
            if enabled:
                for m in mem_indices:
                    dm[ion][m] = row["diffusivity_m2_s"][ion]
    for name in aliases:
        targets[name]["cells"] = list(order)
    percent = raw.get("global_gj_percent")
    gj = (
        None
        if percent is None
        else membranes[: int((min(100, max(1, int(percent))) / 100) * len(membranes))]
    )
    return dict(targets=targets, final_cell_order=order, global_gj_targets=gj, diffusion_m2_s=dm)
