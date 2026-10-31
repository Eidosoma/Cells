"""Independent scalar Decimal controls; this file imports only the stdlib.

No Cells flux, energy or RK implementation is imported or evaluated. Heat is
integrated directly from flux times electrochemical affinity, never recovered
from an energy closing residual. The CLI is for a separately authorized fresh
reference process; preparing this source does not start that process.
"""

import json
import math
import os
import struct
import sys
from decimal import Decimal, localcontext


def binary(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Reference inputs must be finite binary64 real values")
    return Decimal.from_float(float(value))


def constants(hex_values):
    if set(hex_values) != {"F", "R"}:
        raise ValueError("Both pinned binary64 constants are required")
    return tuple(binary(float.fromhex(hex_values[key])) for key in ("F", "R"))


def bernoulli(value):
    return Decimal(1) if value == 0 else value / (value.exp() - 1)


def shape(value):
    if not isinstance(value, list):
        return ()
    if not value:
        return (0,)
    tail = shape(value[0])
    if any(shape(item) != tail for item in value):
        raise ValueError("Reference output must be rectangular")
    return (len(value), *tail)


def flatten(value):
    if isinstance(value, list):
        return [leaf for item in value for leaf in flatten(item)]
    return [value]


def retained(value):
    """Retain every Decimal before one binary64 projection, with exact axes."""
    if isinstance(value, dict):
        return {key: retained(item) for key, item in value.items()}
    if type(value) is bool:
        return dict(raw_boolean=value, binary_boolean=value)
    leaves = flatten(value)
    if any(not isinstance(item, Decimal) or not item.is_finite() for item in leaves):
        raise ValueError("Nonfinite or non-Decimal reference return")
    return dict(
        shape=list(shape(value)),
        decimal=[str(item) for item in leaves],
        binary64=dict(
            dtype="<f8",
            shape=list(shape(value)),
            data_hex=b"".join(struct.pack("<d", float(item)) for item in leaves).hex(),
        ),
    )


def _stage(raw, amounts, pinned_constants):
    p = raw["layout"]
    F, R = constants(pinned_constants)
    T = binary(p["temperature_K"])
    k, m, e, c = (len(raw["owners"][key]) for key in ("populations", "patches", "edges", "cells"))
    if len(amounts) != k or any(len(row) != m for row in amounts):
        raise ValueError("Complete reference amount axes are required")
    N = [[binary(item) for item in row] for row in amounts]
    z = [binary(item) for item in p["effective_charge_e"]]
    phi = [binary(item) for item in raw["prescribed_potential_V"]]
    area = [
        binary(a) if active else Decimal(1)
        for a, active in zip(p["patch_area_um2"], p["patch_active"], strict=True)
    ]
    ref = [binary(item) for item in raw["reference_density_fmol_um2"]]
    zero = Decimal(0)
    density = [
        [N[a][i] / area[i] if p["patch_active"][i] else zero for i in range(m)] for a in range(k)
    ]
    mu = [
        [
            R * T * (density[a][i] / ref[a]).ln() if raw["initial_amount_fmol"][a][i] > 0 else zero
            for i in range(m)
        ]
        for a in range(k)
    ]
    flux, forward, reverse, heat, work, affinity = (
        [[zero for _ in range(e)] for _ in range(k)] for _ in range(6)
    )
    dN, outgoing = ([[zero for _ in range(m)] for _ in range(k)] for _ in range(2))
    for a in range(k):
        for edge in range(e):
            s, r = p["edge_sender"][edge], p["edge_receiver"][edge]
            electric = z[a] * F * (phi[s] - phi[r])
            affinity[a][edge] = mu[a][s] - mu[a][r] + electric
            if not p["edge_active"][edge]:
                continue
            x = z[a] * F * (phi[r] - phi[s]) / (R * T)
            if abs(x) > 50:
                raise ValueError("Reference charged exponent outside the unchanged domain")
            g = (
                binary(p["edge_diffusivity_um2_s"][a][edge])
                * binary(p["edge_width_um"][edge])
                / binary(p["edge_distance_um"][edge])
            )
            forward[a][edge] = g * bernoulli(x) / area[s]
            reverse[a][edge] = g * bernoulli(-x) / area[r]
            J = forward[a][edge] * N[a][s] - reverse[a][edge] * N[a][r]
            flux[a][edge] = J
            dN[a][s] -= J
            dN[a][r] += J
            outgoing[a][s] += forward[a][edge]
            outgoing[a][r] += reverse[a][edge]
            heat[a][edge] = Decimal("0.001") * J * affinity[a][edge]
            work[a][edge] = Decimal("0.001") * J * electric
    cell_rate = [
        [sum((dN[a][i] for i in range(m) if p["patch_cell"][i] == cell), zero) for cell in range(c)]
        for a in range(k)
    ]
    chemical_power = [[Decimal("0.001") * mu[a][i] * dN[a][i] for i in range(m)] for a in range(k)]
    kernel = dict(
        density_fmol_um2=density,
        flux_fmol_s=flux,
        amount_rate_fmol_s=dN,
        forward_rate_s_inv=forward,
        reverse_rate_s_inv=reverse,
        outgoing_rate_s_inv=outgoing,
        cell_rate_residual_fmol_s=cell_rate,
        valid=True,
    )
    return dict(
        kernel=kernel,
        amount_fmol=N,
        chemical_mu_J_mol=mu,
        electrochemical_mu_J_mol=[
            [mu[a][i] + z[a] * F * phi[i] for i in range(m)] for a in range(k)
        ],
        electrochemical_drop_J_mol=affinity,
        chemical_power_patch_pJ_s=chemical_power,
        dissipation_edge_pJ_s=heat,
        field_power_edge_pJ_s=work,
        cargo_charge_C=[
            [Decimal("1e-15") * F * z[a] * N[a][i] for i in range(m)] for a in range(k)
        ],
        cargo_charge_rate_C_s=[
            [Decimal("1e-15") * F * z[a] * dN[a][i] for i in range(m)] for a in range(k)
        ],
        cell_cargo_charge_rate_C_s=[
            [Decimal("1e-15") * F * z[a] * cell_rate[a][i] for i in range(c)] for a in range(k)
        ],
        energy_rate_residual_pJ_s=[
            sum(chemical_power[a], zero) + sum(heat[a], zero) - sum(work[a], zero) for a in range(k)
        ],
        derivative=dict(
            amount_increment_fmol=dN,
            transferred_fmol=flux,
            dissipated_energy_pJ=heat,
            field_work_pJ=work,
        ),
    )


def stage(raw, amounts, pinned_constants, *, precision):
    if precision not in (100, 160):
        raise ValueError("Only the predeclared precision pair is admitted")
    with localcontext() as context:
        context.prec = precision
        result = _stage(raw, amounts, pinned_constants)
        return dict(
            kind="independent_charged_surface_stage@1",
            precision=precision,
            raw_before_projection=True,
            result=retained(result),
        )


def stage_batch(raw, points, pinned_constants, *, precision):
    if not 1 <= len(points) <= 6 or len({point["role"] for point in points}) != len(points):
        raise ValueError("At most six uniquely labelled actual stage points are admitted")
    return dict(
        kind="independent_actual_charged_surface_stage_batch@1",
        precision=precision,
        points={
            point["role"]: stage(raw, point["amounts"], pinned_constants, precision=precision)
            for point in points
        },
    )


def direct_heat_quadrature(function, horizon, tolerance, *, retain):
    """Bounded Decimal Simpson refinement, with every evaluation retained.

    Refusal preserves the partial tree. There is no tolerance widening, second
    algorithm or energy-residual substitution. The two precision arms use their
    own predeclared quadrature tolerances.
    """
    evaluations = 0

    def evaluate(t):
        nonlocal evaluations
        evaluations += 1
        if evaluations > 16385:
            raise ValueError("Predeclared direct-heat quadrature budget exhausted")
        value = function(t)
        retain(dict(kind="integrand", time_s=str(t), heat_power_pJ_s=str(value)))
        return value

    a, b = Decimal(0), horizon
    midpoint = (a + b) / 2
    fa, fm, fb = evaluate(a), evaluate(midpoint), evaluate(b)
    initial = (b - a) * (fa + 4 * fm + fb) / 6

    def refine(left, right, fleft, fmid, fright, whole, budget, depth):
        middle = (left + right) / 2
        fl, fr = evaluate((left + middle) / 2), evaluate((middle + right) / 2)
        first = (middle - left) * (fleft + 4 * fl + fmid) / 6
        second = (right - middle) * (fmid + 4 * fr + fright) / 6
        error = (first + second - whole) / 15
        accepted = abs(error) <= budget
        retain(
            dict(
                kind="interval",
                left_s=str(left),
                right_s=str(right),
                depth=depth,
                raw_first_pJ=str(first),
                raw_second_pJ=str(second),
                estimated_error_pJ=str(error),
                declared_local_budget_pJ=str(budget),
                accepted=accepted,
            )
        )
        if accepted:
            return first + second + error, abs(error)
        if depth >= 16:
            raise ValueError("Predeclared direct-heat quadrature depth exhausted")
        one, err_one = refine(left, middle, fleft, fl, fmid, first, budget / 2, depth + 1)
        two, err_two = refine(middle, right, fmid, fr, fright, second, budget / 2, depth + 1)
        return one + two, err_one + err_two

    heat, error = refine(a, b, fa, fm, fb, initial, tolerance, 0)
    return heat, error, evaluations


def analytic_two_patch(raw, pinned_constants, *, precision):
    if precision not in (100, 160):
        raise ValueError("Only the predeclared precision pair is admitted")
    if (
        len(raw["owners"]["cells"]) != 1
        or len(raw["owners"]["patches"]) != 2
        or len(raw["owners"]["edges"]) != 1
    ):
        raise ValueError("Analytic control is only for a single supplied two-patch edge")
    p = raw["layout"]
    if (
        not all(p["patch_active"])
        or p["edge_active"] != [True]
        or p["edge_sender"] != [0]
        or p["edge_receiver"] != [1]
    ):
        raise ValueError("Analytic control requires the literal oriented active edge")
    audit = []
    try:
        with localcontext() as context:
            context.prec = precision
            F, R = constants(pinned_constants)
            T = binary(p["temperature_K"])
            initial_rates = _stage(raw, raw["initial_amount_fmol"], pinned_constants)
            horizon = binary(raw["time_labels_s"][-1])
            if horizon <= 0:
                raise ValueError("Declared analytic horizon must be positive")
            state = {
                key: []
                for key in (
                    "amount_increment_fmol",
                    "transferred_fmol",
                    "dissipated_energy_pJ",
                    "field_work_pJ",
                )
            }
            scales, budgets = [], []
            for a, amounts in enumerate(raw["initial_amount_fmol"]):
                N0, N1 = map(binary, amounts)
                A0, A1 = map(binary, p["patch_area_um2"])
                total = N0 + N1
                forward = initial_rates["kernel"]["forward_rate_s_inv"][a][0]
                reverse = initial_rates["kernel"]["reverse_rate_s_inv"][a][0]
                rate = forward + reverse
                electric = (
                    binary(p["effective_charge_e"][a])
                    * F
                    * (
                        binary(raw["prescribed_potential_V"][0])
                        - binary(raw["prescribed_potential_V"][1])
                    )
                )
                if rate == 0 or total == 0:
                    endpoint, transferred, heat, error, evaluations = (
                        N0,
                        Decimal(0),
                        Decimal(0),
                        Decimal(0),
                        0,
                    )
                else:
                    equilibrium = reverse * total / rate

                    def amount_at(t, equilibrium=equilibrium, N0=N0, rate=rate):
                        return equilibrium + (N0 - equilibrium) * (-rate * t).exp()

                    def heat_power(
                        t,
                        amount_at=amount_at,
                        total=total,
                        forward=forward,
                        reverse=reverse,
                        A0=A0,
                        A1=A1,
                        electric=electric,
                    ):
                        left = amount_at(t)
                        right = total - left
                        J = forward * left - reverse * right
                        return (
                            Decimal("0.001")
                            * J
                            * (R * T * ((left / A0) / (right / A1)).ln() + electric)
                        )

                    endpoint = amount_at(horizon)
                    transferred = N0 - endpoint
                    tolerance = Decimal("1e-14") if precision == 100 else Decimal("2.5e-15")
                    heat, error, evaluations = direct_heat_quadrature(
                        heat_power,
                        horizon,
                        tolerance,
                        retain=lambda row, population=a: audit.append(
                            dict(population=population, **row)
                        ),
                    )
                state["amount_increment_fmol"].append([endpoint - N0, N0 - endpoint])
                state["transferred_fmol"].append([transferred])
                state["dissipated_energy_pJ"].append([heat])
                state["field_work_pJ"].append([Decimal("0.001") * electric * transferred])
                scales.append(
                    dict(
                        population=a,
                        rate_s_inv=str(rate),
                        local_relaxation_time_s=str(1 / rate) if rate else None,
                        declared_horizon_s=str(horizon),
                        horizon_times_local_rate=str(horizon * rate),
                    )
                )
                budgets.append(
                    dict(
                        population=a,
                        summed_estimated_heat_error_pJ=str(error),
                        integrand_evaluations=evaluations,
                    )
                )
            return dict(
                kind="analytic_two_patch_direct_heat_control@1",
                precision=precision,
                result=retained(state),
                local_time_scales=scales,
                direct_heat_audit=audit,
                heat_quadrature_budgets=budgets,
                biological_time_scale_claim=False,
                heat_defined_from_energy_residual=False,
            )
    except Exception as error:
        raise ValueError(
            json.dumps(dict(reason=str(error), retained_direct_heat_audit=audit), sort_keys=True)
        ) from error


def main():
    # One bounded request in a fresh interpreter; no Cells/native/science import.
    blocked = ("cells", "numpy", "scipy", "jax", "jaxlib", "pytest", "betse")

    class NoScience:
        @staticmethod
        def find_spec(fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError("Independent Decimal worker denies science imports: " + fullname)
            return None

    sys.meta_path.insert(0, NoScience())
    if any(name.split(".")[0] in blocked for name in sys.modules):
        raise RuntimeError("Independent reference worker started with science loaded")
    text = sys.stdin.read(2**21 + 1)
    if len(text.encode()) > 2**21:
        raise ValueError("Bounded independent reference request exceeded")
    request = json.loads(text, parse_constant=lambda text: (_ for _ in ()).throw(ValueError(text)))
    if request["mode"] == "stage":
        response = stage(
            request["declaration"],
            request["amounts"],
            request["constants_binary64_hex"],
            precision=request["precision"],
        )
    elif request["mode"] == "stage_batch":
        response = stage_batch(
            request["declaration"],
            request["points"],
            request["constants_binary64_hex"],
            precision=request["precision"],
        )
    elif request["mode"] == "analytic_two_patch":
        response = analytic_two_patch(
            request["declaration"],
            request["constants_binary64_hex"],
            precision=request["precision"],
        )
    else:
        raise ValueError("Unknown predeclared independent reference mode")
    response["independent_runtime"] = dict(
        pid=os.getpid(),
        ppid=os.getppid(),
        executable=sys.executable,
        version=sys.version,
        isolated=sys.flags.isolated,
        no_site=sys.flags.no_site,
        science_modules_loaded=[name for name in sys.modules if name.split(".")[0] in blocked],
    )
    json.dump(response, sys.stdout, sort_keys=True, separators=(",", ":"), allow_nan=False)


if __name__ == "__main__":
    main()
