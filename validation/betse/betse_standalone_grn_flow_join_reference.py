"""Fresh Decimal conditional flow and inherited molecular source equations."""

import sys
from decimal import Decimal, localcontext

from validation.betse import betse_standalone_grn_flow_join_engine as engine
from validation.betse.betse_ecm_sim_grn_reference import (
    _derivative,
    _flatten,
    _reshape,
    d,
    derivative_gross,
    smooth,
)

_API = None


def api():
    global _API
    if _API is None:
        _API = engine.load_parent("reference")
        _API.ecm_environment = ecm_environment
    return _API


def encode(value):
    if isinstance(value, Decimal):
        return dict(decimal=str(value))
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode(item) for item in value]
    if value is None or type(value) in (str, int, float, bool):
        return value
    raise TypeError("Unexpected independent raw reference value: " + type(value).__name__)


def flow_activation(inputs, *, refinement):
    with localcontext() as context:
        context.prec = 100 if refinement == 1 else 160
        activation = inputs["activation"]
        before = activation["before"]
        simulator = before["simulator"]
        if not activation["recalculate_fluid"]:
            return dict(
                velocity_x_m_s=simulator["u_env_x"],
                velocity_y_m_s=simulator["u_env_y"],
                flow_recalculated=False,
                static_for_entire_invocation=True,
                decimal_precision=context.prec,
                carried_reference_forms=0,
            )
        n = len(simulator["zs"])
        nz = sum(map(d, simulator["zs"]), Decimal(0)) / n
        concentrations = simulator["cc_env"]
        mean = [
            sum((d(row[i]) for row in concentrations), Decimal(0)) / n
            for i in range(len(concentrations[0]))
        ]
        faraday = d(before["parameters"]["F"])
        ny, nx = len(simulator["J_env_x"]), len(simulator["J_env_x"][0])
        result = {}
        for axis in ("x", "y"):
            current = simulator["J_env_" + axis]
            result["velocity_" + axis + "_m_s"] = [
                [-d(current[i][j]) / (faraday * mean[i * nx + j] * nz) for j in range(nx)]
                for i in range(ny)
            ]
        return dict(
            result,
            mean_concentration_mol_m3=[mean[i * nx : (i + 1) * nx] for i in range(ny)],
            mean_valence=nz,
            flow_recalculated=True,
            static_for_entire_invocation=True,
            decimal_precision=context.prec,
            carried_reference_forms=0,
        )


def evaluate(inputs, *, refinement=1, retain):
    if refinement not in (1, 2):
        raise ValueError("Use the unchanged 100/160-digit conditional levels")
    precision = 100 if refinement == 1 else 160
    retained = []

    def save(label, value):
        name = label + "-" + str(precision) + "-" + str(len(retained)).zfill(4)
        retain(name, encode(value))
        retained.append(name)

    def trace(frame, event, arg):
        if (
            event == "call"
            and frame.f_code.co_name == "plain"
            and (frame.f_back is None or frame.f_back.f_code.co_name != "plain")
            and frame.f_globals.get("__name__", "").startswith("validation.")
        ):
            save("raw-preprojection", frame.f_locals["value"])
        if frame.f_code is ecm_environment.__code__ and event in ("return", "exception"):
            save(
                "raw-advection-environment",
                {
                    key: value
                    for key, value in frame.f_locals.items()
                    if key
                    in {
                        "env",
                        "gross",
                        "p",
                        "inputs",
                        "grid",
                        "dt",
                        "temperature",
                        "image",
                        "ig",
                        "fx",
                        "fy",
                        "fxg",
                        "fyg",
                        "euler",
                        "eg",
                        "final",
                        "fg",
                    }
                },
            )
        if frame.f_code is flow_activation.__code__ and event in ("return", "exception"):
            save(
                "raw-flow-activation-partial",
                {
                    key: value
                    for key, value in frame.f_locals.items()
                    if key
                    in {
                        "inputs",
                        "activation",
                        "before",
                        "simulator",
                        "n",
                        "nz",
                        "concentrations",
                        "mean",
                        "faraday",
                        "ny",
                        "nx",
                        "result",
                    }
                },
            )
        return trace

    previous = sys.gettrace()
    try:
        sys.settrace(trace)
        mode = inputs.get("mode", "warm")
        if mode == "flow_activation":
            raw = flow_activation(inputs, refinement=refinement)
            save("raw-flow-activation", raw)
            result = api().plain(raw)
        else:
            result = api().evaluate(inputs, refinement=refinement)
            if mode == "cold_initialization":
                result["owner_fields"]["recalc_fluid"] = inputs["network"]["configuration"][
                    "recalculate fluid flow"
                ]
    finally:
        sys.settrace(previous)
    retain("raw-index-" + str(precision), dict(records=retained, read_only=True))
    retain("parent-runtime-provenance-" + str(precision), api().__source_provenance__)
    retain("projected-reference-" + str(precision), result)
    return result


# The inherited environment function follows, with only source advection and
# its input-predicted gross term added to the four flux assignments.


def ecm_environment(env, gross, p, inputs, grid, dt, temperature):
    shape, delta = (grid["shape"], grid["delta_m"])
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
    image, ig = (_reshape(env, shape), _reshape(gross, shape))
    bound = d(p["c_bound"])
    for i in range(ny):
        for j in range(nx):
            if i in (0, ny - 1) or j in (0, nx - 1):
                image[i][j], ig[i][j] = (bound, abs(bound))
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
    ex, ey = (inputs["electric_x_source"], inputs["electric_y_source"])
    fx, fy, fxg, fyg = ([[zero] * nx for _ in range(ny)] for _ in range(4))
    for i in range(ny):
        for j in range(nx):
            diffusion = weights[i * nx + j] * d(p["Do"])
            alpha = diffusion * d(p["z"]) * d(inputs["q_C"]) / (d(inputs["kb_J_K"]) * temperature)
            fx[i][j] = (
                -diffusion * gx[i][j]
                + alpha * d(ex[i][j]) * image[i][j]
                + (d(inputs["velocity_x_m_s"][i][j]) if inputs["fluid_flow"] else zero)
                * image[i][j]
            )
            fy[i][j] = (
                -diffusion * gy[i][j]
                + alpha * d(ey[i][j]) * image[i][j]
                + (d(inputs["velocity_y_m_s"][i][j]) if inputs["fluid_flow"] else zero)
                * image[i][j]
            )
            fxg[i][j] = (
                abs(diffusion) * ggx[i][j]
                + abs(alpha * d(ex[i][j])) * ig[i][j]
                + abs(d(inputs["velocity_x_m_s"][i][j]) if inputs["fluid_flow"] else zero)
                * ig[i][j]
            )
            fyg[i][j] = (
                abs(diffusion) * ggy[i][j]
                + abs(alpha * d(ey[i][j])) * ig[i][j]
                + abs(d(inputs["velocity_y_m_s"][i][j]) if inputs["fluid_flow"] else zero)
                * ig[i][j]
            )
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
