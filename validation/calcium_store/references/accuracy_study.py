"""Measure what the references reach, check the known limits, and write `accuracy.json`.

    python accuracy_study.py [--jobs N] [--to FILE]

It needs SciPy. It makes no published value. Every check has a bound; a check outside its bound is listed under "failed" and
the exit code is 1. Sizes are written to three digits. The numbers that come from SciPy or from doubles (marked in the file)
may differ in those digits on another machine.
"""

import argparse
import json
import multiprocessing
import random
import sys
import warnings
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import numpy
from scipy.integrate import solve_ivp

if __package__:
    from . import api, forms, integrators, second_route, world, write_values
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import api
    import forms
    import integrators
    import second_route
    import world
    import write_values

ZERO = Decimal(0)
RADAU_STAGES, RADAU_STEPS = 9, 2
FAILED = []


def size(number):
    """A number to three digits, as a double."""
    return float(f"{float(number):.2e}")


def bounded(name, number, bound):
    """The number to three digits; noted as failed when it is above the bound."""
    if not abs(number) <= bound:
        FAILED.append(f"{name}: {float(number):.3e} is above {float(bound):.1e}")
    return size(number)


def required(name, condition):
    if not condition:
        FAILED.append(name)
    return bool(condition)


def flatten(value, prefix=(), out=None):
    """{path: leaf} of nested mappings and lists."""
    out = {} if out is None else out
    if isinstance(value, dict):
        for key, item in value.items():
            flatten(item, prefix + (key,), out)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            flatten(item, prefix + (index,), out)
    else:
        out[prefix] = value
    return out


def relative(a, b):
    """The difference of two exact numbers over the larger, as a fraction; 0 when both are 0."""
    a, b = Fraction(a), Fraction(b)
    return abs(a - b) / max(abs(a), abs(b)) if a != b else Fraction(0)


# The kernel states


def kernel_families(inputs):
    laws = inputs["symport_laws"]
    return {
        "pump_states": (
            inputs["pump_states"],
            forms.pump_outputs,
            second_route.pump_outputs,
            lambda s: Fraction(s["capacity_fmol_per_s"]) * Fraction(s["availability"]),
        ),
        "exchanger_states": (
            inputs["exchanger_states"],
            forms.exchanger_outputs,
            second_route.exchanger_outputs,
            lambda s: Fraction(s["capacity_fmol_per_s"]) * Fraction(s["availability"]),
        ),
        "symport_states": (
            inputs["symport_states"],
            lambda s: forms.symport_outputs(s, laws[s["law"]]),
            lambda s: second_route.symport_outputs(s, laws[s["law"]]),
            lambda s: Fraction(s["capacity_fmol_per_s"]) * Fraction(s["availability"]),
        ),
    }


EXACT_ZEROS = ("J_at_V_stall_fmol_per_s", "J_at_V_rev_fmol_per_s")


def kernel_study(inputs, literal_inputs):
    out = {}
    literal_families = kernel_families(literal_inputs)
    for name, (states, first, second, scale) in kernel_families(inputs).items():
        worst = worst_digits = Fraction(0)
        worst_zero = Fraction(0)
        compared = different_doubles = different_at_90 = 0
        readings = {}
        for index, state in enumerate(states):
            with forms.working(api.KERNEL_DIGITS):
                a = flatten(first(state))
                with forms.working(90):
                    finer = flatten(first(state))
                literal = flatten(literal_families[name][1](literal_families[name][0][index]))
            b = flatten(second(state))
            required(f"{name} {state['tag']}: the same outputs", set(a) == set(b))
            for path, value in a.items():
                if value is None or isinstance(value, bool):
                    required(f"{name} {state['tag']} {path}: equal", b[path] is value)
                    continue
                if path[0] in EXACT_ZEROS:
                    required(f"{name} {state['tag']} {path}: exactly zero", value == 0)
                    if scale(state):
                        worst_zero = max(worst_zero, abs(b[path]) / scale(state))
                    continue
                compared += 1
                worst = max(worst, relative(value, b[path]))
                worst_digits = max(worst_digits, relative(value, finer[path]))
                different_doubles += float(value) != second_route._nearest_double(Fraction(b[path]))
                different_at_90 += float(value) != float(finer[path])
                if path[0].startswith("near_") or path[:2] == ("with_V_NP_changed", "V_NP_V"):
                    continue  # made voltages, which follow the reading themselves
                moved = relative(value, literal[path])
                kind = path[0]
                if moved > readings.get(kind, (0, None))[0]:
                    readings[kind] = (moved, state["tag"] if "law" not in state else f"{state['law']}, {state['tag']}")
        largest = max(readings.items(), key=lambda item: item[1][0])
        out[name] = {
            "states": len(states),
            "numbers_compared": compared,
            "largest_relative_difference_of_the_two_routes": bounded(f"{name}: the routes", worst, Decimal("1e-38")),
            "largest_relative_difference_of_60_and_90_digits": bounded(
                f"{name}: digits", worst_digits, Decimal("1e-38")
            ),
            "doubles_that_differ_between_the_routes": bounded(f"{name}: doubles", different_doubles, 0),
            "doubles_that_differ_between_60_and_90_digits": bounded(f"{name}: doubles at 90", different_at_90, 0),
            "second_route_at_the_exact_zeros_over_k_a": bounded(f"{name}: zeros", worst_zero, Decimal("1e-100")),
            "inputs_as_literals_instead_of_doubles": {
                "largest_relative_change": size(largest[1][0]),
                "where": f"{largest[0]}, {largest[1][1]}",
                "by_output": {kind: size(moved) for kind, (moved, _tag) in sorted(readings.items())},
            },
        }
    return out


def initial_rates_study(inputs):
    rates, heats, factors, dV_m, dV_b = second_route.initial_rates(inputs)
    worst, compared = Fraction(0), 0
    with forms.working(api.KERNEL_DIGITS):
        first = world.StoreWorld(inputs, "store_world").initial_rates()
        for mover, label in world.TRANSFERS:
            sign = -1 if mover == "release" else 1
            worst = max(worst, relative(first["rates_fmol_per_s"][mover][label], sign * rates[mover, label]))
            worst = max(worst, relative(first["heat_rates_pJ_per_s"][mover][label], heats[mover, label]))
            compared += 2
        for name, factor in factors.items():
            worst = max(worst, relative(first["condition_factors"][name], factor))
            compared += 1
        worst = max(worst, relative(first["dV_m_dt_V_per_s"], dV_m), relative(first["dV_b_dt_V_per_s"], dV_b))
        compared += 2
    return {
        "numbers_compared": compared,
        "largest_relative_difference_of_the_two_routes": bounded("initial rates", worst, Decimal("1e-45")),
    }


# The store world: one case is a variant with a control


def largest_changes(observables):
    return {
        path[:-1]: max(abs(observables[path[:-1] + (i,)] - observables[path[:-1] + (0,)]) for i in range(5))
        for path in observables
        if path[-1] == 0
    }


def scipy_solution(model, changes, times, method, rtol, atol):
    """(The second route's observables at each time, evaluations used); each unknown is scaled by its largest change."""
    R, M = len(model.rows), len(model.movers)
    scale = numpy.ones(model.size)
    for i, row in enumerate(model.rows):
        scale[i] = float(changes[("amount_changes_fmol",) + row]) or 1.0
    scale[R:R + 2] = float(changes[("m",)]), float(changes[("h",)])
    for i, mover in enumerate(model.movers):
        scale[R + 2 + i] = float(changes[("transfers_fmol",) + mover["name"]]) or 1.0
        scale[R + 2 + M + i] = float(changes[("heats_pJ",) + mover["name"]]) or 1.0
    for i, name in enumerate(world.WORKS):
        scale[R + 2 + 2 * M + i] = float(changes["works_pJ", name])
    base = model.initial()
    z = numpy.zeros(model.size)
    solutions, evaluations = [model.observables(base)], 0
    for start, end in zip(times, times[1:]):
        result = solve_ivp(
            lambda t, z: model.derivative(t, base + scale * z) / scale, (start, end), z, method=method, rtol=rtol, atol=atol
        )
        if not result.success:
            raise ArithmeticError(f"{method}: {result.message}")
        z = result.y[:, -1]
        evaluations += result.nfev
        solutions.append(model.observables(base + scale * z))
    return solutions, evaluations


def difference_to(solutions, observables, changes):
    """{path: the largest difference over the times, over the largest change} of the second route's solutions."""
    out = {}
    for path, change in changes.items():
        if path not in solutions[0]:
            continue
        gap = max(abs(Decimal(float(s[path])) - observables[path + (i,)]) for i, s in enumerate(solutions))
        if change == 0:  # SciPy's implicit methods leave the rounding of their linear algebra there
            bounded(f"a constant observable in the second route: {path}", gap, Decimal("1e-20"))
            out[path] = 0.0
        else:
            out[path] = float(gap / change)
    return out


def case_study(task):
    """Both decimal integrators and the second route with an explicit SciPy integrator, for one variant and control."""
    inputs, variant, control = task
    FAILED.clear()
    with forms.working(world.SETTINGS["digits"]):
        model = world.StoreWorld(inputs, variant, control)
        times = model.times(inputs)
        values = model.solve(times)
        published = flatten(model.observables(times, values))
        changes = {path: change for path, change in largest_changes(published).items() if path != ("times_s",)}
        method = integrators.RadauIIA(RADAU_STAGES)
        pairs = integrators.radau(
            model.dynamic_derivative,
            model.dissipation,
            model.initial_unknowns()[:world.N_DYNAMIC],
            times,
            RADAU_STEPS,
            method,
        )
        implicit = flatten(model.observables(times, [y + Q for y, Q in pairs]))
        implicit_gap = {}
        for path, change in changes.items():
            gap = max(abs(implicit[path + (i,)] - published[path + (i,)]) for i in range(5))
            implicit_gap[path] = gap / change if change else gap
        balance = [
            published["free_energy_change_pJ", i] + published["heat_total_pJ", i] - published["work_total_pJ", i]
            for i in range(5)
        ]
        # matter, charge and the fixed charges, from the published unknowns
        totals = []
        for y in values:
            c = model.changes(y)
            totals += [
                c["cell", "Na"] + c["outside", "Na"],
                c["cell", "K"] + c["store", "K"] + c["outside", "K"],
                c["cell", "Cl"] + c["store", "Cl"] + c["outside", "Cl"],
                sum((c[node, "Ca"] for node in world.NODES), ZERO)
                + sum((c[node, "CaB"] + 2 * c[node, "Ca2B"] for node in ("cell", "store")), ZERO),
                sum((c["cell", s] for s in ("B", "CaB", "Ca2B")), ZERO),
                sum((c["store", s] for s in ("B", "CaB", "Ca2B")), ZERO),
            ]
        charge_gap = ZERO
        for y in values:
            c = model.changes(y)
            q = {
                node: model.charge_coulomb
                * (
                    sum((model.valence[s] * (model.initial[w, s] + c[w, s]) for w, s in model.rows if w == node), ZERO)
                    + model.fixed_charge[node]
                )
                for node in world.NODES
            }
            dV_m, dV_b = model.voltage_changes(c)
            V_m, V_b = model.initial_voltage["plasma"] + dV_m, model.initial_voltage["bounding"] + dV_b
            charge_gap = max(
                charge_gap,
                abs((q["cell"] + q["store"]) / model.capacitance["plasma"] - V_m),
                abs(-q["store"] / model.capacitance["bounding"] - V_b),
                abs(q["cell"] + q["store"] + q["outside"]) / model.capacitance["plasma"],
            )
        # each mover's heat grows from one time to the next
        falling = sorted({
            "/".join(path[1:3])
            for path in published
            if path[0] == "heats_pJ" and path[-1] > 0 and published[path] < published[path[:-1] + (path[-1] - 1,)]
        })
    second = second_route.World(inputs, variant, control)
    solutions, evaluations = scipy_solution(second, changes, [float(t) for t in times], "DOP853", 2.3e-14, 1e-14)
    explicit_gap = difference_to(solutions, published, changes)
    label = f"{variant}, {control or 'no control'}"
    # G + heat - work and the sign of the heats are as they are only where the laws are whole
    if control != "pump_without_voltage":
        bounded(f"{label}: G + heat - work", max(abs(b) for b in balance), Decimal("1e-30"))
    if control != "release_sign":
        required(f"{label}: heats that fall: {falling}", not falling)
    bounded(f"{label}: Radau IIA", max(implicit_gap.values()), Decimal("1e-20"))
    bounded(f"{label}: the second route", max(explicit_gap.values()), 1e-11)
    bounded(f"{label}: matter", max(abs(t) for t in totals), Decimal("1e-35"))
    bounded(f"{label}: charge", charge_gap, Decimal("1e-30"))
    return {
        "published": published,
        "changes": changes,
        "implicit_gap": implicit_gap,
        "explicit_gap": explicit_gap,
        "explicit_evaluations": evaluations,
        "balance": balance,
        "matter": max(abs(t) for t in totals),
        "charge": charge_gap,
        "falling": falling,
        "failed": list(FAILED),
    }


def path_name(path):
    return "/".join(str(part) for part in path)


def rounding_of(path, published, change):
    """Half the spacing of the published double over the largest change: what the double itself can hold."""
    if change == 0:
        return 0.0
    return float(max(Decimal(numpy.spacing(abs(float(published[path + (i,)])))) / 2 for i in range(5)) / change)


ROUNDED_PARTNER = {  # a value whose double is coarse, and the change published beside it
    "amounts_fmol": "amount_changes_fmol",
    "V_m_V": "V_m_change_V",
    "V_b_V": "V_b_change_V",
    "capacitor_energy_pJ": "capacitor_energy_change_pJ",
    "free_energy_pJ": "free_energy_change_pJ",
}


def world_summary(cases):
    out = {}
    for variant in api.VARIANTS:
        case = cases[variant, None]
        table = {}
        for path, change in case["changes"].items():
            if path[0] in ROUNDED_PARTNER:
                continue
            table[path_name(path)] = {
                "largest_change": size(change),
                "radau_iia": size(case["implicit_gap"][path]),
                "scipy_dop853": size(case["explicit_gap"][path]) if path in case["explicit_gap"] else None,
            }
        coarse = {}
        for path, change in case["changes"].items():
            if path[0] in ROUNDED_PARTNER and change != 0:
                coarse[path_name(path)] = size(rounding_of(path, case["published"], change))
        out[variant] = {
            "largest_difference_radau_iia": size(max(case["implicit_gap"].values())),
            "largest_difference_scipy_dop853": size(max(case["explicit_gap"].values())),
            "scipy_dop853_evaluations": case["explicit_evaluations"],
            "G_plus_heat_less_work_pJ": size(max(abs(b) for b in case["balance"])),
            "matter_fmol": size(case["matter"]),
            "charge_against_the_fixed_charges_V": size(case["charge"]),
            "observables": table,
            "what_a_double_of_the_whole_value_can_hold": coarse,
        }
    return out


def controls_summary(cases, inputs):
    out = {}
    for variant in api.VARIANTS:
        base = cases[variant, None]
        out[variant] = {}
        for control in world.control_names(inputs):
            case = cases[variant, control]
            moved = {}
            for path, change in base["changes"].items():
                if path[0] in ROUNDED_PARTNER or path[0] in ("heat_total_pJ", "work_total_pJ") or change == 0:
                    continue
                gap = max(abs(case["published"][path + (i,)] - base["published"][path + (i,)]) for i in range(5))
                moved[path] = float(gap / change)
            top = max(moved, key=lambda path: moved[path])
            out[variant][control] = {
                "largest_difference_radau_iia": size(max(case["implicit_gap"].values())),
                "largest_difference_scipy_dop853": size(max(case["explicit_gap"].values())),
                "G_plus_heat_less_work_at_the_last_time_pJ": size(case["balance"][-1]),
                "movers_whose_heat_falls": case["falling"],
                "largest_shift_over_the_base_s_largest_change": size(moved[top]),
                "observable_most_shifted": path_name(top) if moved[top] else None,
            }
    return out


def integrator_study(inputs):
    """(The base world by each integrator at several settings, against a run beyond all of them; what failed)."""
    FAILED.clear()
    out = {"measure": "the largest difference over the unknowns and the times, over each unknown's largest change"}
    with forms.working(world.SETTINGS["digits"]):
        model = world.StoreWorld(inputs, "store_world")
        times = model.times(inputs)
        finest = model.solve(times, 4, 14)
        changes = [max(abs(v[i] - finest[0][i]) for v in finest) for i in range(world.N_UNKNOWNS)]

        def worst(values):
            return max(abs(a - b) / s for v, r in zip(values, finest) for a, b, s in zip(v, r, changes))

        out["against"] = "extrapolated midpoint, 4 steps per interval of 2 ms, 14 columns (order 28), 40 digits"
        out["extrapolated_midpoint"] = {
            f"{steps} steps per interval, {columns} columns": size(worst(model.solve(times, steps, columns)))
            for steps, columns in ((1, 6), (1, 8), (1, 10), (1, 12), (2, 6), (2, 8), (2, 10), (2, 12), (2, 14))
        }
        out["radau_iia"] = {}
        for stages, steps in ((3, 1), (3, 2), (3, 4), (5, 1), (5, 2), (5, 4), (7, 1), (7, 2), (9, 1), (9, 2)):
            pairs = integrators.radau(
                model.dynamic_derivative,
                model.dissipation,
                model.initial_unknowns()[:world.N_DYNAMIC],
                times,
                steps,
                integrators.RadauIIA(stages),
            )
            out["radau_iia"][f"{steps} steps per interval, {stages} stages"] = size(worst([y + Q for y, Q in pairs]))
        published = flatten(model.observables(times, finest))
        all_changes = {path: c for path, c in largest_changes(published).items() if path != ("times_s",)}
    second = second_route.World(inputs, "store_world")
    out["scipy_on_the_second_route_in_doubles"] = {}
    for method, tolerances in (
        ("DOP853", (1e-6, 1e-9, 1e-12, 2.3e-14)),
        ("Radau", (1e-6, 1e-9, 1e-12)),
        ("BDF", (1e-6, 1e-9, 1e-12)),
        ("LSODA", (1e-6, 1e-9, 1e-12)),
    ):
        for rtol in tolerances:
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                solutions, evaluations = scipy_solution(
                    second, all_changes, [float(t) for t in times], method, rtol, rtol / 2
                )
            gaps = difference_to(solutions, published, all_changes)
            out["scipy_on_the_second_route_in_doubles"][f"{method}, rtol {rtol:.1e}"] = {
                "largest_difference": size(max(gaps.values())), "evaluations": evaluations,
            }
    return out, list(FAILED)


def known_solutions():
    """The two decimal integrators on equations whose solution is known."""
    with forms.working(world.SETTINGS["digits"]):
        riccati = lambda y: [-y[0] * y[0]]  # y = 1/(1 + t)
        turning = lambda y: [y[1], -y[0]]
        decay = lambda y: [Decimal(-500) * y[0]]
        times = [ZERO, Decimal("0.5"), Decimal(1)]
        exact_decay = (Decimal(-500) * Decimal("0.004")).exp()
        out = {}
        a = integrators.extrapolated_midpoint(riccati, [Decimal(1)], times, 8, 12)[-1][0]
        out["extrapolated_midpoint, y' = -y^2 to t = 1"] = bounded("riccati", a - Decimal("0.5"), Decimal("1e-28"))
        a = integrators.extrapolated_midpoint(turning, [Decimal(1), ZERO], times, 8, 12)[-1]
        out["extrapolated_midpoint, a rotation to t = 1, its radius"] = bounded(
            "rotation", a[0] ** 2 + a[1] ** 2 - 1, Decimal("1e-28")
        )
        a = integrators.extrapolated_midpoint(decay, [Decimal(1)], [ZERO, Decimal("0.004")], 4, 12)[-1][0]
        out["extrapolated_midpoint, y' = -500 y to t = 4 ms, steps of 1 ms"] = bounded(
            "decay", a - exact_decay, Decimal("1e-25")
        )
        method = integrators.RadauIIA(RADAU_STAGES)
        none = lambda y: []
        a = integrators.radau(riccati, none, [Decimal(1)], times, 8, method)[-1][0][0]
        out["radau_iia, y' = -y^2 to t = 1"] = bounded("riccati, Radau", a - Decimal("0.5"), Decimal("1e-20"))
        square = lambda y: [y[0] ** 2]  # the integral of 1/(1 + t)^2 from 0 to 1 is 1/2
        a = integrators.radau(riccati, square, [Decimal(1)], times, 8, method)[-1][1][0]
        out["radau_iia, its quadrature of y^2 = 1/(1 + t)^2"] = bounded(
            "quadrature, Radau", a - Decimal("0.5"), Decimal("1e-20")
        )
        a = integrators.radau(decay, none, [Decimal(1)], [ZERO, Decimal("0.004")], 4, method)[-1][0][0]
        out["radau_iia, y' = -500 y to t = 4 ms, steps of 1 ms"] = bounded("decay, Radau", a - exact_decay, Decimal("1e-18"))
    return out


# The material block


def material_study(inputs):
    out = {}
    for variant in api.VARIANTS:
        for which in ("t = 0", "the last time"):
            with forms.working(world.SETTINGS["digits"]):
                model = world.StoreWorld(inputs, variant)
                times = model.times(inputs)
                y = model.initial_unknowns() if which == "t = 0" else model.solve(times)[-1]
            second = second_route.World(inputs, variant)
            entry = {}
            with forms.working(api.BLOCK_DIGITS):
                model = world.StoreWorld(inputs, variant)
                amounts = model.material_amounts(y)
                _changes, _voltage, c = model._state(y)
                for name, opening_moves in (("release_opening_moving", True), ("release_opening_held", False)):
                    matrix = model.material_jacobian(y, opening_moves)
                    opening = None if opening_moves else model.release_opening(c)
                    worst = Decimal(0)
                    for j in range(5):
                        step = amounts[j] * Decimal("1e-18")
                        up, down = list(amounts), list(amounts)
                        up[j] += step
                        down[j] -= step
                        column = [
                            (a - b) / (2 * step)
                            for a, b in zip(model.material_rates(y, up, opening), model.material_rates(y, down, opening))
                        ]
                        for i in range(5):
                            if matrix[i][j] == 0:
                                required(f"material block {variant} {which} {i}{j}", abs(column[i]) < Decimal("1e-30"))
                            else:
                                worst = max(worst, abs(column[i] / matrix[i][j] - 1))
                    eigenvalues = world.material_eigenvalues(matrix)
                    doubles = numpy.array([[float(a) for a in row] for row in matrix])
                    numerical = numpy.linalg.eigvals(doubles)
                    scale = max(abs(numerical))
                    gap = max(
                        min(abs(complex(float(a), float(b)) - other) for other in numerical) / scale for a, b in eigenvalues
                    )
                    columns = max(
                        max(abs(sum(matrix[i][j] for i in (0, 1, 2))), abs(sum(matrix[i][j] for i in (3, 4))))
                        for j in range(5)
                    )
                    entry[name] = {
                        "slopes_against_central_differences": bounded("material block", worst, Decimal("1e-25")),
                        "slopes_against_the_second_route_in_doubles": bounded(
                            "material block, second route",
                            _second_block_gap(second, model, y, doubles, None if opening_moves else float(opening)),
                            1e-7,
                        ),
                        "eigenvalues_against_numpy_over_the_largest": bounded("material eigenvalues", gap, 1e-12),
                        "column_sums_over_Ca_and_Na_per_s": bounded("material columns", columns, Decimal("1e-50")),
                        "largest_modulus_per_s": size(max((a * a + b * b).sqrt() for a, b in eigenvalues)),
                    }
            out[f"{variant}, {which}"] = entry
    return out


def _second_block_gap(second, model, y, doubles, opening):
    """The block by extrapolated central differences of the second route's rates, the potentials and gates held."""
    change = numpy.array([float(model.changes(y)[row]) for row in second.rows])
    gates = [float(y[world.N_TRANSFERS]), float(y[world.N_TRANSFERS + 1])]
    phi = second.potentials(change)
    chosen = [second.at[row] for row in world.MATERIAL_ROWS]
    names = ("plasma_leak", "store_leak", "release", "calcium_channel", "plasma_pump", "store_pump", "exchanger")
    counted = numpy.array([mover["name"][0] in names for mover in second.movers])

    def g(moved):
        J, *_rest = second.rates(moved, gates, phi=phi, opening=opening)
        return ((J * counted) @ second.moves)[chosen]

    worst = 0.0
    for j, index in enumerate(chosen):
        amount = second.n0[index] + change[index]
        slopes = []
        for step in (2e-4 * amount, 1e-4 * amount):
            up, down = change.copy(), change.copy()
            up[index] += step
            down[index] -= step
            slopes.append((g(up) - g(down)) / (up[index] - down[index]))
        column = (4 * slopes[1] - slopes[0]) / 3
        for i in range(5):
            reference = doubles[i, j]
            if reference != 0:
                worst = max(worst, abs(column[i] / reference - 1))
    return worst


# The fastest rates


def fastest_rates(inputs):
    out = {}
    for variant in api.VARIANTS:
        with forms.working(world.SETTINGS["digits"]):
            model = world.StoreWorld(inputs, variant)
            times = model.times(inputs)
            for name, y in (("t = 0", model.initial_unknowns()), ("the last time", model.solve(times)[-1])):
                jacobian = integrators.finite_difference_jacobian(model.dynamic_derivative, y[:world.N_DYNAMIC])
                values = sorted(numpy.linalg.eigvals(jacobian), key=lambda v: -abs(v))
                out[f"{variant}, {name}"] = [
                    [size(v.real), size(v.imag)] for v in values if abs(v) > 1e-6
                ]
    return out


# The known limits of the laws


def limits(inputs):
    draw = random.Random(20261125)
    number = lambda low, high: Decimal(repr(10 ** draw.uniform(low, high)))
    out = {}
    with forms.working(api.KERNEL_DIGITS):
        required("F = N_A e, exactly", forms.AVOGADRO * forms.ELEMENTARY_CHARGE == forms.FARADAY)
        required("R = N_A k_B, exactly", forms.AVOGADRO * forms.BOLTZMANN == forms.GAS_CONSTANT)
        required("B(0) = 1", forms.bernoulli(ZERO) == 1)
        worst = max(
            abs(forms.bernoulli(-x) - x - forms.bernoulli(x)) / forms.bernoulli(-x)
            for x in (Decimal("1e-30"), Decimal("1e-9"), Decimal("0.3"), Decimal(7), Decimal(60))
        )
        out["B(-x) = B(x) + x"] = bounded("B(-x) = B(x) + x", worst, Decimal("1e-57"))

        # constant field
        zero, mirrored, small_voltage, least_heat = ZERO, ZERO, ZERO, None
        for _ in range(400):
            T, z = number(2.43, 2.5), Decimal(draw.choice((-1, 1, 2)))
            c_i, c_o, P = number(-6, 3), number(-6, 3), number(-12, -6)
            V = Decimal(repr(draw.uniform(-0.15, 0.15)))
            common = {"valence": z, "temperature": T, "area": Decimal("4e-10"), "permeability": P, "opening": number(-3, 0)}
            J, heat = forms.constant_field(voltage=V, c_inside=c_i, c_outside=c_o, **common)
            inside, _outside = forms.constant_field_slopes(voltage=V, **common)
            least_heat = heat if least_heat is None else min(least_heat, heat)
            back, back_heat = forms.constant_field(voltage=-V, c_inside=c_o, c_outside=c_i, **common)
            mirrored = max(mirrored, abs(J + back) / abs(J), abs(heat - back_heat) / heat)
            nernst = forms.GAS_CONSTANT * T / (z * forms.FARADAY) * (c_o / c_i).ln()
            at_rest, _heat = forms.constant_field(voltage=nernst, c_inside=c_i, c_outside=c_o, **common)
            slope_there, _o = forms.constant_field_slopes(voltage=nernst, **common)
            zero = max(zero, abs(at_rest) / (slope_there * c_i))
            flat, _heat = forms.constant_field(voltage=ZERO, c_inside=c_i, c_outside=c_o, **common)
            diffusion = Decimal("1e15") * common["area"] * P * common["opening"] * (c_i - c_o)
            near, _heat = forms.constant_field(voltage=Decimal("1e-40"), c_inside=c_i, c_outside=c_o, **common)
            small_voltage = max(small_voltage, abs(flat - diffusion) / abs(diffusion), abs(near - flat) / abs(flat))
        out["constant field: flux at the reversal potential over the one-way flux"] = bounded(
            "Nernst", zero, Decimal("1e-55")
        )
        out["constant field: the two sides and the voltage exchanged"] = bounded("mirror", mirrored, Decimal("1e-45"))
        out["constant field: A P (c_i - c_o) at no voltage, and near it"] = bounded(
            "diffusion", small_voltage, Decimal("1e-30")
        )
        out["constant field: the least of 400 heat rates is not negative"] = required("heat of a field", least_heat >= 0)

        # conditions and gates
        half = [(Decimal("0.3"), Decimal("0.3"), Decimal("2.6"), form) for form in ("activation", "inhibition")]
        worst = max(abs(forms.condition_factor([read]) - Decimal("0.5")) for read in half)
        out["a read at its half saturation is 1/2"] = bounded("half saturation", worst, Decimal("1e-58"))
        pair = [
            forms.condition_factor([(Decimal("0.07"), Decimal("0.3"), Decimal("1.7"), form)])
            for form in ("activation", "inhibition")
        ]
        out["activation + inhibition of one read is 1"] = bounded("complement", sum(pair) - 1, Decimal("1e-57"))
        dm, _dh = forms.channel_gate_rates(Decimal("-0.020"), Decimal("0.5"), Decimal("0.1"))
        out["m at rest at u = -0.030 V is 1/2"] = bounded("m half", dm, Decimal("1e-55"))
        _dm, dh = forms.channel_gate_rates(Decimal("-0.070"), Decimal("0.1"), Decimal("0.5"))
        out["h at rest at u = -0.080 V is 1/2"] = bounded("h half", dh, Decimal("1e-55"))

        # pumps
        least_heat, beyond, signs = None, ZERO, True
        for state in inputs["pump_states"]:
            a = forms.pump_outputs(state)
            least_heat = a["heat_rate_pJ_per_s"] if least_heat is None else min(least_heat, a["heat_rate_pJ_per_s"])
            beyond = max(beyond, a["S"])
            k = forms.exact(state["capacity_fmol_per_s"]) * forms.exact(state["availability"])
            if state["z"] != 0 and k != 0:
                # J rises with V_NP for z > 0 and falls for z < 0
                low, high = a["J_at_V_stall_minus_1e-6_V_fmol_per_s"], a["J_at_V_stall_plus_1e-6_V_fmol_per_s"]
                signs = signs and (low < 0 < high if state["z"] > 0 else high < 0 < low)
        out["pumps: the least heat rate of the states is not negative"] = required("pump heat", least_heat >= 0)
        out["pumps: S is below 1 in every state"] = required("pump saturation", beyond < 1)
        out["pumps: J changes sign at the stall voltage, by the sign of z"] = required("pump stall", signs)
        # the exchanger and the symports
        least_heat, signs = None, True
        for state in inputs["exchanger_states"]:
            a = forms.exchanger_outputs(state)
            least_heat = a["heat_rate_pJ_per_s"] if least_heat is None else min(least_heat, a["heat_rate_pJ_per_s"])
            if forms.exact(state["capacity_fmol_per_s"]) * forms.exact(state["availability"]) != 0:
                signs = signs and a["J_at_V_rev_minus_1e-6_V_fmol_per_s"] > 0 > a["J_at_V_rev_plus_1e-6_V_fmol_per_s"]
            if "equal concentrations" in state["tag"]:
                required("exchanger: equal concentrations reverse at no voltage", a["V_rev_V"] == 0)
        out["exchanger: the least heat rate of the states is not negative"] = required("exchanger heat", least_heat >= 0)
        out["exchanger: J falls through zero at the reversal voltage"] = required("exchanger reversal", signs)
        least_heat, bound, still, kept = None, True, True, True
        for state in inputs["symport_states"]:
            a = forms.symport_outputs(state, inputs["symport_laws"][state["law"]])
            least_heat = a["heat_rate_pJ_per_s"] if least_heat is None else min(least_heat, a["heat_rate_pJ_per_s"])
            bound = bound and abs(a["J_fmol_per_s"]) <= a["one_way_rates_sum_fmol_per_s"]
            kept = kept and all(J == a["J_fmol_per_s"] for J in a["with_V_NP_changed"]["J_fmol_per_s"])
            if "x = 0" in state["tag"]:
                still = still and a["x"] == 0 and a["J_fmol_per_s"] == 0 and a["heat_rate_pJ_per_s"] == 0
        out["symports: the least heat rate of the states is not negative"] = required("symport heat", least_heat >= 0)
        out["symports: J is at most k a in modulus"] = required("symport bound", bound)
        out["symports: x, J and heat are exactly 0 at equal concentrations"] = required("symport zero", still)
        out["symports: J does not move with the voltage"] = required("symport voltage", kept)

        # the reactions
        rest, least_heat = ZERO, None
        for _ in range(200):
            a, b, delta = number(-6, 1), number(-6, 1), Decimal(repr(draw.uniform(-12, 2)))
            made = a * b * (-delta).exp()
            common = {"temperature": Decimal(300), "volume": number(-2, 1), "rate_constant": number(0, 3), "delta_mu": delta}
            r, _heat = forms.reaction(reactants=[a, b], products=[made], **common)
            one_way = common["volume"] * common["rate_constant"] * a * b
            rest = max(rest, abs(r) / one_way)
            _r, heat = forms.reaction(reactants=[a, b], products=[number(-8, 3)], **common)
            least_heat = heat if least_heat is None else min(least_heat, heat)
        out["reactions: the rate at equilibrium over the one-way rate"] = bounded("reaction at rest", rest, Decimal("1e-55"))
        out["reactions: the least of 200 heat rates is not negative"] = required("reaction heat", least_heat >= 0)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--to", type=Path, default=api.FOLDER / "accuracy.json")
    arguments = parser.parse_args()
    inputs = api._inputs()
    literal_inputs = json.loads(api.INPUTS.read_text(encoding="utf-8"), parse_float=Decimal)
    out = {"schema": "calcium_store_references_accuracy@1", "what": "Written by accuracy_study.py; see README.md."}
    out["kernel_states"] = kernel_study(inputs, literal_inputs)
    out["initial_rates"] = initial_rates_study(inputs)
    out["known_limits"] = limits(inputs)
    out["integrators_on_known_solutions"] = known_solutions()
    out["material_block"] = material_study(inputs)
    out["fastest_rates_per_s"] = fastest_rates(inputs)
    failed = list(FAILED)
    tasks = [(inputs, variant, control) for variant in api.VARIANTS for control in [None] + world.control_names(inputs)]
    with multiprocessing.get_context("fork").Pool(arguments.jobs) as pool:
        study = pool.apply_async(integrator_study, (inputs,))
        results = pool.map(case_study, tasks, chunksize=1)
        out["integrators"], study_failed = study.get()
    cases = {(variant, control): result for (_inputs, variant, control), result in zip(tasks, results)}
    out["world"] = world_summary(cases)
    out["controls"] = controls_summary(cases, inputs)
    failed += study_failed
    for result in results:
        failed += result["failed"]
    out["failed"] = failed
    arguments.to.write_text(write_values.dump(out) + "\n", encoding="utf-8")
    print(f"wrote {arguments.to}; failed: {failed or 'none'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
