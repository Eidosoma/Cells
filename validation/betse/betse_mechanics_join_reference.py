"""Isolated Decimal owner/DEC and conditional display composition."""

from copy import deepcopy
from decimal import Decimal, localcontext

from validation.mechanics.betse_deformation_reference import (
    arrays,
    d,
    gradient,
    matmul,
    matvec,
    rotation,
    solve_many,
    transpose,
)


def numbers(value):
    if isinstance(value, dict):
        return {key: numbers(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [numbers(item) for item in value]
    return d(value)


def project(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: project(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [project(item) for item in value]
    return value


def encode(value):
    if isinstance(value, Decimal):
        return dict(decimal=str(value))
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [encode(item) for item in value]
    return value


def display(centres, original, displacement, weights):
    low = [min(c[a] for c in centres) for a in range(2)]
    high = [max(c[a] for c in centres) for a in range(2)]
    offset = [sum(c[a] for c in centres) / len(centres) for a in range(2)]
    scale = [high[a] - low[a] for a in range(2)]

    def basis(point):
        x, y = [(point[a] - offset[a]) / scale[a] for a in range(2)]
        return [(x**i if i else d(1)) * (y**j if j else d(1)) for i in range(5) for j in range(5)]

    design = [basis(point) for point in centres]
    target = [basis([max(low[a], min(high[a], point[a])) for a in range(2)]) for point in original]
    transposed = transpose(design)
    inverse_action = solve_many(matmul(transposed, design), transposed)
    interpolation = matmul(target, inverse_action)
    delta = matmul(interpolation, transpose(displacement))
    vertices = [
        [a + b for a, b in zip(row, change, strict=True)]
        for row, change in zip(original, delta, strict=True)
    ]
    return dict(
        interpolation=interpolation, vertices_m=vertices, cell_centres_m=matmul(weights, vertices)
    )


def evaluate(inputs, *, refinement=1, retain):
    if refinement not in (1, 2) or not callable(retain):
        raise ValueError("Require explicit complete raw retention and declared precision")
    precision = 100 if refinement == 1 else 160
    with localcontext() as context:
        context.prec = precision
        declared = inputs["definition"]
        geometry, policy, p = (declared[key] for key in ("geometry", "policy", "parameters"))
        if policy["fluid_flow"] or policy["td_deform"] or policy["solver"] != "FULL":
            raise ValueError("Ordinary policy has no enabled flow/dynamic branch")
        if not policy["is_ecm"]:
            count = len(geometry["layout"]["neighbors"])
            if len(geometry["environment_ids"]) != count or geometry[
                "membrane_to_environment"
            ] != list(range(count)):
                raise ValueError("NoECM source environment rows use the original membrane axis")
        op = arrays(geometry["layout"])
        cache = numbers(inputs["initial"])
        history = []
        for packet in inputs["steps"]:
            frames, auxiliary = [], {"flow": None}

            def observe(stage, frames=frames):
                frames.append(dict(stage=stage, cache=deepcopy(cache)))

            observe("initial")
            pressure = numbers(packet["pressure_Pa"])
            if policy["deform_osmo"]:
                total = []
                for side in ("cell", "env"):
                    rows = list(packet["primary_" + side + "_mM"])
                    for group, enabled in (
                        ("molecule", policy["molecules_enabled"]),
                        ("grn", policy["grn_enabled"]),
                    ):
                        if enabled:
                            rows.extend(packet[group + "_" + side + "_mM"])
                    total.append([sum(d(row[i]) for row in rows) for i in range(len(rows[0]))])
                rt = d(p["gas_constant_J_mol_K"]) * d(packet["temperature_K"])
                cell, env = [[rt * value for value in row] for row in total]
                mapped = (
                    [env[index] for index in geometry["cell_to_environment"]]
                    if policy["is_ecm"]
                    else [
                        sum(d(weight) * value for weight, value in zip(row, env, strict=True))
                        / sum(d(weight) for weight in row)
                        for row in geometry["layout"]["sum_membranes"]
                    ]
                )
                delta = [a - b for a, b in zip(mapped, cell, strict=True)]
                velocity = [
                    (a - b)
                    * d(p["aquaporin_fraction"])
                    / d(p["water_viscosity_Pa_s"])
                    * d("9e-20")
                    / d(p["membrane_thickness_m"])
                    for a, b in zip(delta, pressure, strict=True)
                ]
                mesh = geometry["layout"]
                divergence = [
                    u * d(a) / d(v)
                    for u, a, v in zip(
                        velocity, mesh["cell_area_m2"], mesh["cell_volume_m3"], strict=True
                    )
                ]
                pp = matvec(
                    op["laplacian_inverse"],
                    [-v * d(p["density_kg_m3"]) * d(p["dt_s"]) for v in divergence],
                )
                for key, value in zip(
                    ("osmo_P_cell", "osmo_P_env", "osmo_P_delta", "u_osmo", "div_u_osmo", "PP"),
                    (cell, env, delta, velocity, divergence, pp),
                    strict=True,
                ):
                    cache[key] = value
                auxiliary["osmotic"] = dict(
                    zip(
                        (
                            "cell_osmotic_pressure_Pa",
                            "environment_osmotic_pressure_Pa",
                            "delta_pressure_Pa",
                            "water_velocity_m_s",
                            "divergence_per_s",
                            "PP_native",
                        ),
                        (cell, env, delta, velocity, divergence, pp),
                        strict=True,
                    )
                )
                observe("osmotic_pressure")
            observe("disabled_flow_gate")
            if policy["deformation"]:
                grad = gradient(pressure, op)
                mu = d(p["young_modulus_Pa"]) / (2 * (1 + d("0.49")))
                raw = [
                    matvec(op["laplacian_inverse"], [-value / mu for value in row]) for row in grad
                ]
                potential, rotated = rotation(raw, op)
                osmotic = (
                    gradient(cache["PP"], op)
                    if policy["deform_osmo"]
                    else [[d(0)] * len(pressure) for _ in range(2)]
                )
                electric = [
                    [d(value) * d(p["galvanotropism_m2_V"]) for value in row]
                    for row in packet["electric_field_V_m"]
                ]
                displacement = [
                    [a + b + c for a, b, c in zip(x, y, z, strict=True)]
                    for x, y, z in zip(rotated, osmotic, electric, strict=True)
                ]
                divergence = [
                    a + b
                    for a, b in zip(
                        matvec(op["curl_gradient_x"], displacement[0]),
                        matvec(op["curl_gradient_y"], displacement[1]),
                        strict=True,
                    )
                ]
                auxiliary["steady"] = dict(
                    displacement_m=displacement,
                    pressure_gradient_Pa_m=grad,
                    unprojected_elastic_m=raw,
                    rotational_m=rotated,
                    rotation_potential=potential,
                    osmotic_addition_native=osmotic,
                    electric_addition_m=electric,
                    divergence_numeric=divergence,
                )
                cache["gPxc"], cache["gPyc"] = grad
                cache["d_cells_x"], cache["d_cells_y"] = displacement
                observe("steady_deformation")
            candidate = deepcopy(cache)
            sampled = None
            if packet["sample"]:
                sampled = display(
                    cache["display_centres_m"],
                    numbers(geometry["layout"]["vertices_m"]),
                    [cache["d_cells_x"], cache["d_cells_y"]],
                    numbers(geometry["display_vertex_weights"]),
                )
                cache["display_centres_m"] = sampled["cell_centres_m"]
                cache["display_vertices_m"] = sampled["vertices_m"]
            history.append(
                dict(
                    frames=frames,
                    auxiliaries=auxiliary,
                    candidate=candidate,
                    sample=sampled,
                    carried_cache=deepcopy(cache),
                )
            )
        raw = dict(
            precision=precision,
            operators=op,
            history=history,
            final_cache=cache,
            source_flow_enabled=False,
            source_dynamic_enabled=False,
            physical_geometry_rebuilt=False,
        )
        retain("raw-decimal-" + str(precision), dict(precision=precision, payload=encode(raw)))
        projected = project(raw)
        retain("projected-reference-" + str(precision), projected)
        return projected
