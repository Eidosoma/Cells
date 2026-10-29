"""Independent stdlib owner lists, exact bitmap rationals and Decimal events."""

import bisect
import struct
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction

IONS = ("Na", "K", "Cl", "Ca", "M", "P")
ORDER = ("Na_mem", "K_mem", "Cl_mem", "Ca_mem", "pressure", "ecmJ")


def image_values(raw, points):
    bitmap, bounds = raw["bitmap"], points["bounds_m"]
    size = len(bitmap)
    image = [
        [float(struct.unpack("f", struct.pack("f", float(v)))[0]) != 255.0 for v in row]
        for row in bitmap
    ][::-1]

    def nodes(lo, hi):
        step = (hi - lo) / (size - 1)
        return [lo + i * step for i in range(size - 1)] + [hi]

    xx, yy = nodes(bounds[0], bounds[1]), nodes(bounds[2], bounds[3])
    result = []
    for px, py in points["cell_centres_m"]:
        x, y = max(xx[0], min(xx[-1], px)), max(yy[0], min(yy[-1], py))
        ix, iy = (
            min(size - 2, max(0, bisect.bisect_right(xx, x) - 1)),
            min(size - 2, max(0, bisect.bisect_right(yy, y) - 1)),
        )
        fx = (Fraction(x) - Fraction(xx[ix])) / (Fraction(xx[ix + 1]) - Fraction(xx[ix]))
        fy = (Fraction(y) - Fraction(yy[iy])) / (Fraction(yy[iy + 1]) - Fraction(yy[iy]))
        value = (1 - fy) * ((1 - fx) * image[iy][ix] + fx * image[iy][ix + 1]) + fy * (
            (1 - fx) * image[iy + 1][ix] + fx * image[iy + 1][ix + 1]
        )
        result.append(float(value))
    return result


def profiles(raw, permutations):
    layout, order = raw["layout"], list(range(len(raw["layout"]["cell_ids"])))
    count, membranes = len(order), len(layout["membrane_ids"])
    targets, aliases, dm, records = {}, [], deepcopy(raw["initial_membrane_m2_s"]), []
    rows = [raw["default"], *raw["profiles"]] if raw["enabled"] else []
    for number, row in enumerate(rows):
        kind = "all" if number == 0 else row["picker"]
        if kind == "all":
            cells = list(order)
            aliases.append(row["name"])
        elif kind == "indices":
            cells = list(row["indices"])
        elif kind == "color":
            cells = [i for i, color in enumerate(layout["seed_fills"]) if color == row["color"]]
        elif kind == "percent":
            order = list(permutations[row["name"]])
            cells = order[: int((float(row["percent"]) / 100) * count)]
        else:
            cells = [i for i, value in enumerate(image_values(row, layout)) if value != 0.0]
        mems = [m for i in cells for m in layout["cell_membranes"][i]]
        env_declared = bool(cells) and raw["is_ecm"]
        env = [layout["membrane_environment"][m] for m in mems] if env_declared else []
        targets[row["name"]] = dict(
            cells=cells,
            picked_cells=list(cells),
            membranes=mems,
            environments=env,
            environment_declared=env_declared,
        )
        for ion in range(6):
            if raw["ion_enabled"][ion]:
                for m in mems:
                    dm[ion][m] = row["diffusivity_m2_s"][ion]
        records.append(dict(name=row["name"], insular=True if number == 0 else row["insular"]))
    for name in aliases:
        targets[name]["cells"] = list(order)
    weights = [1.0] * membranes
    for m, partner in enumerate(layout["partner_membrane"]):
        a, b = layout["membrane_cell"][m], layout["membrane_cell"][partner]
        if partner != m:
            if b not in layout["cell_neighbors"][a] or any(
                row["insular"]
                and ((a in targets[row["name"]]["cells"]) != (b in targets[row["name"]]["cells"]))
                for row in records
            ):
                weights[m] = 0.0
    return dict(targets=targets, final_cell_order=order, diffusion_m2_s=dm, gj_weights=weights)


def d(value):
    return Decimal(str(value))


def pulse(time, on, off, change):
    g = d(10) / d(change)
    first = 1 / (1 + (-g * (d(time) - d(on))).exp())
    second = 1 / (1 + (-g * (d(time) - d(off))).exp())
    return first - second


def scalar_samples(event, raw, indices):
    if event["function"] == "None":
        return [1.0] * len(indices)
    assert event["function"] == "gradient_x"
    layout = raw["layout"]
    if len(indices) == len(layout["membrane_ids"]):
        coordinates = layout["membrane_midpoints_m"]
    elif len(indices) == len(layout["cell_ids"]):
        coordinates = layout["cell_centres_m"]
    else:
        raise ValueError("Native callback target length leaves source axis unbound")
    x = [d(v[0]) for v in coordinates]
    lo, hi = min(x), max(x)
    p = raw["gradient_x"]
    result = []
    for value in x:
        loading = (((value - lo) / (hi - lo)) / (d(".5") + d(p["x_offset"]))) ** d(p["exponent"])
        result.append(float(loading / (1 + loading) * d(p["slope"]) + d(p["z_offset"])))
    return result


def events(raw, profile_result):
    with localcontext() as context:
        context.prec = 80
        selected, declarations = profile_result["targets"], []
        for row in sorted(raw["events"], key=lambda row: ORDER.index(row["kind"])):
            domain = (
                "cells"
                if row["kind"] == "pressure"
                else "environments"
                if row["kind"] == "ecmJ"
                else "membranes"
            )
            indices = [i for name in row["profiles"] for i in selected[name][domain]]
            declarations.append(
                dict(
                    name=row["name"],
                    kind=row["kind"],
                    indices=indices,
                    scalar=scalar_samples(row, raw, indices)
                    if row["kind"] != "ecmJ"
                    else [1.0] * len(indices),
                )
            )
        dm = [[d(v) for v in row] for row in raw["initial_scheduled_m2_s"]]
        pressure = [d(v) for v in raw["pressure_mod_Pa"]]
        env = [[d(v) for v in row] for row in raw["environment_current_m2_s"]]
        weight = [d(v) for v in raw["environment_weight_current"]]
        records = []
        by_name = {row["name"]: row for row in raw["events"]}
        for time in raw["times_s"]:
            pulses = []
            for declaration in declarations:
                row = by_name[declaration["name"]]
                value = pulse(time, row["on_s"], row["off_s"], row["change_s"])
                pulses.append(float(value))
                eff = d(row["amplitude"]) * value
                kind = row["kind"]
                if kind.endswith("_mem"):
                    ion = IONS.index(kind.split("_")[0])
                    if kind in ("Cl_mem", "Ca_mem") and not raw["ion_enabled"][ion]:
                        continue
                    default = d(raw["default"]["diffusivity_m2_s"][ion])
                    for at, scalar in zip(
                        declaration["indices"], declaration["scalar"], strict=True
                    ):
                        dm[ion][at] = eff * d(scalar) * default
                elif kind == "pressure":
                    for at, scalar in zip(
                        declaration["indices"], declaration["scalar"], strict=True
                    ):
                        pressure[at] = eff * d(scalar)
                else:
                    for at in declaration["indices"]:
                        for ion in range(6):
                            env[ion][at] = d(raw["environment_base_m2_s"][ion][at]) * (
                                1 - eff
                            ) + eff * d(raw["environment_free_m2_s"][ion])
                        weight[at] = d(raw["environment_weight_base"][at]) * (1 - eff) + eff
            records.append(
                dict(
                    time_s=time,
                    pulse=pulses,
                    membrane_scheduled_m2_s=[[float(v) for v in row] for row in dm],
                    membrane_total_m2_s=[
                        [float(v + d(base)) for v, base in zip(row, baserow, strict=True)]
                        for row, baserow in zip(dm, profile_result["diffusion_m2_s"], strict=True)
                    ],
                    pressure_mod_Pa=[float(v) for v in pressure],
                    pressure_total_Pa=[
                        float(v + d(base))
                        for v, base in zip(pressure, raw["pressure_base_Pa"], strict=True)
                    ],
                    environment_current_m2_s=[[float(v) for v in row] for row in env],
                    environment_weight_current=[float(v) for v in weight],
                )
            )
        return dict(declarations=declarations, records=records)
