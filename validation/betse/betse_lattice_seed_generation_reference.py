"""Independent Decimal lattice coordinates and exact qualified MT uniform replay."""

from copy import deepcopy
from decimal import Decimal, localcontext

from validation.betse.betse_environment_field_reference import d, serial
from validation.tissue.physiology_protein_packet_provider_reference import _mt_uniforms


def fp(value):
    return float(value)


def parameters(recipe, *, precision):
    with localcontext() as context:
        context.prec = precision
        length, radius, disorder = (
            float(recipe[key]) for key in ("world_len_m", "cell_radius_m", "lattice_disorder")
        )
        diameter = fp(d(radius) * 2)
        nx = int(fp(d(length) / d(diameter)))
        ny = int(fp(d(length) / d(diameter)))
        growth = fp(d(fp(5 * d(disorder))) * d(diameter))
        width, height = fp(d(length) + d(growth)), fp(d(length) + d(growth))
        r = fp(d(diameter) / 2)
        a = fp(d(fp(Decimal(3).sqrt())) * d(r))
        b = fp(3 * d(r))
        by_start, by_stop = fp(d(a) / 2), fp(d(width) - d(fp(d(a) / 2)))
        rx_start, rx_stop = fp(d(b) / 2), fp(d(height) - d(fp(d(b) / 2)))
        blue = (int(fp(d(fp(d(by_stop) - d(by_start))) / d(a))), int(fp(d(height) / d(b))))
        red = (int(fp(d(width) / d(a))), int(fp(d(fp(d(rx_stop) - d(rx_start))) / d(b))))
        return dict(
            world_len=length,
            cell_radius=radius,
            cell_lattice_disorder=disorder,
            d_cell=diameter,
            nx=nx,
            ny=ny,
            wsx=width,
            wsy=height,
            ac=1e-6,
        ), (a, b, blue, red, by_start, by_stop, rx_start, rx_stop)


def line(start, stop, count):
    if count == 0:
        return []
    if count == 1:
        return [d(start)]
    return [d(start) + Decimal(i) * (d(stop) - d(start)) / (count - 1) for i in range(count)]


def evaluate(recipe, before, *, refinement=1):
    if refinement not in (1, 2):
        raise ValueError("Require two declared independent precision settings")
    with localcontext() as context:
        context.prec = 100 if refinement == 1 else 160
        p, hex_values = parameters(recipe, precision=context.prec)
        blue_points = red_points = None
        if recipe["lattice_type"] == "SQUARE":
            step = fp(d(p["d_cell"]) + d(p["ac"]))
            stop_x, stop_y = fp((p["nx"] - 1) * d(step)), fp((p["ny"] - 1) * d(step))
            xs, ys = line(0, stop_x, p["nx"]), line(0, stop_y, p["ny"])
            base = [[x, y] for y in ys for x in xs]
            shape = (p["ny"], p["nx"])
        else:
            _, _, blue, red, by_start, by_stop, rx_start, rx_stop = hex_values
            blue_points = [
                [x, y] for y in line(by_start, by_stop, blue[0]) for x in line(0, p["wsy"], blue[1])
            ]
            red_points = [
                [x, y] for y in line(0, p["wsx"], red[0]) for x in line(rx_start, rx_stop, red[1])
            ]
            base = blue_points + red_points
            shape = (len(base),)
        count = len(base)
        ux, intermediate = _mt_uniforms(before, count)
        uy, after = _mt_uniforms(intermediate, count)
        if not count:
            return dict(
                status="empty_native_lattice",
                parameters=p,
                rng_before=deepcopy(before),
                rng_after=after,
                x_uniforms=[],
                y_uniforms=[],
                source_arrays_undefined_after_min=True,
                precision=context.prec,
            )
        factor = d(fp(d(p["cell_lattice_disorder"]) * d(p["d_cell"])))
        dx, dy = [factor * (d(u) - d(0.5)) for u in ux], [factor * (d(u) - d(0.5)) for u in uy]
        points = [[a[0] + x, a[1] + y] for a, x, y in zip(base, dx, dy, strict=True)]
        xmin, xmax = min(row[0] for row in points), max(row[0] for row in points)
        ymin, ymax = min(row[1] for row in points), max(row[1] for row in points)
        bbox = [[xmin, ymin], [xmax, ymin], [xmax, ymax], [xmin, ymax]]
        radius = d(p["cell_radius"])
        expanded = [
            [xmin - radius, ymin - radius],
            [xmax + radius, ymin - radius],
            [xmax + radius, ymax + radius],
            [xmin - radius, ymax + radius],
        ]
        centre = [sum(row[k] for row in points) / count for k in (0, 1)]

        def shaped(values):
            return (
                values
                if len(shape) == 1
                else [values[i * shape[1] : (i + 1) * shape[1]] for i in range(shape[0])]
            )

        values = dict(
            base_points_m=base,
            blue_points_m=blue_points,
            red_points_m=red_points,
            x_uniforms=shaped(ux),
            y_uniforms=shaped(uy),
            x_displacement_m=shaped(dx),
            y_displacement_m=shaped(dy),
            lattice_points_m=points,
            bbox_seed_points_m=bbox,
            all_seed_points_m=points + bbox,
            expanded_bbox_m=expanded,
            centre_m=centre,
            axis_bounds_m=[xmin - radius, xmax + radius, ymin - radius, ymax + radius],
        )
        for key in ("blue_points_m", "red_points_m"):
            if values[key] == []:
                # JSON needs explicit width for a zero-row coordinate matrix.
                values[key] = {"empty_array_shape": [0, 2]}
        return serial(
            dict(
                status="source_equations_complete",
                parameters=p,
                values=values,
                rng_before=before,
                rng_after=after,
                precision=context.prec,
                blue_shape=hex_values[2] if recipe["lattice_type"] == "HEX" else [],
                red_shape=hex_values[3] if recipe["lattice_type"] == "HEX" else [],
                downstream_mesh_or_image_executed=False,
                biological_geometry=False,
            )
        )
