"""Selected-state energy arithmetic diagnosis, never a trajectory acceptance rule.

Keep the original binary64 states, layout, physical constants and controls.
Separate exact products of rounded inputs from wider runtime arithmetic. The
wider replay still uses the frozen, binary64-built layout and source formulas;
it is not an independent high-precision physical reference or a new solver.
"""

import argparse
import sys
from contextlib import contextmanager
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import numpy as np


def rational(value):
    """Exact binary input, including long double, without a float64 detour."""
    value = np.asarray(value)
    if value.shape or value.dtype.kind not in "fiu" or not np.isfinite(value):
        raise ValueError("Require a finite real scalar")
    scalar = value[()]
    return (
        Fraction(int(scalar)) if value.dtype.kind in "iu" else Fraction(*scalar.as_integer_ratio())
    )


def exact_products(*factors):
    if not factors:
        raise ValueError("Require at least one product factor")
    arrays = np.broadcast_arrays(*factors)
    result = Fraction()
    for index in np.ndindex(arrays[0].shape):
        product = Fraction(1)
        for array in arrays:
            product *= rational(array[index])
        result += product
    return result


def fraction_record(value):
    return dict(numerator=str(value.numerator), denominator=str(value.denominator))


def decimal_solve(matrix, rhs, *, digits=80):
    """Small diagnostic solve of the EXACT supplied binary matrix/RHS.

    Decimal partial-pivot elimination is rounded at ``digits`` decimal digits;
    its answer is then rounded to this host's long double. This does not rebuild
    the source's cached normalized matrix. Only finite, real, square systems
    with one RHS and at most 256 rows are accepted.
    """
    a, b = np.asarray(matrix), np.asarray(rhs)
    if (
        type(digits) is not int
        or digits < 40
        or a.ndim != 2
        or not 0 < a.shape[0] <= 256
        or a.shape[1] != a.shape[0]
        or b.shape != (a.shape[0],)
        or a.dtype.kind != "f"
        or b.dtype.kind != "f"
        or not np.isfinite(a).all()
        or not np.isfinite(b).all()
    ):
        raise ValueError("Require a bounded finite real system and >=40 decimal digits")
    with localcontext() as context:
        context.prec = digits

        def convert(value):
            q = rational(value)
            return Decimal(q.numerator) / Decimal(q.denominator)

        rows = [[convert(v) for v in row] + [convert(y)] for row, y in zip(a, b, strict=True)]
        for column in range(len(rows)):
            pivot = max(range(column, len(rows)), key=lambda i: abs(rows[i][column]))
            if rows[pivot][column] == 0:
                raise np.linalg.LinAlgError("Singular diagnostic system")
            rows[column], rows[pivot] = rows[pivot], rows[column]
            for i in range(column + 1, len(rows)):
                multiplier = rows[i][column] / rows[column][column]
                for j in range(column + 1, len(rows) + 1):
                    rows[i][j] -= multiplier * rows[column][j]
                rows[i][column] = Decimal(0)
        answer = [Decimal(0)] * len(rows)
        for i in reversed(range(len(rows))):
            answer[i] = (
                rows[i][-1] - sum(rows[i][j] * answer[j] for j in range(i + 1, len(rows)))
            ) / rows[i][i]
        # Decimal -> float -> long double would silently lose the extra bits.
        result = np.asarray([str(value) for value in answer], dtype=np.longdouble)
    if not np.isfinite(result).all():
        raise ValueError("Diagnostic solution is not representable in long double")
    return result


def widen(record):
    """Promote flat numeric leaves; retain law-dispatch tuple type and masks."""
    return type(record)(
        *(
            np.asarray(value).astype(np.longdouble)
            if np.asarray(value).dtype.kind == "f"
            else np.asarray(value).copy()
            for value in record
        )
    )


@contextmanager
def wider_arithmetic(*, constants=False):
    """Process-local diagnostic only; restore all temporary overrides on exit."""
    if np.finfo(np.longdouble).nmant <= np.finfo(np.float64).nmant:
        raise ValueError("This host provides no wider NumPy arithmetic")
    previous = np.linalg.solve
    changed = []
    names = []
    try:
        np.linalg.solve = decimal_solve
        if constants:
            # Promote the actual frozen binary values, never decimal spellings
            # or recomputed F*1e-15. Python literals remain the source's literals.
            for name, module in tuple(sys.modules.items()):
                if not name.startswith("cells.") or module is None:
                    continue
                for key in ("R", "F", "CHARGE_PER_FMOL"):
                    old = vars(module).get(key)
                    if type(old) is float or isinstance(old, np.float64):
                        new = np.longdouble(old)
                        assert rational(new) == rational(old)
                        changed.append((module, key, old))
                        names.append(name + "." + key)
                        setattr(module, key, new)
        yield names
    finally:
        np.linalg.solve = previous
        for module, key, old in reversed(changed):
            setattr(module, key, old)


def product_record(name, source, factors, arrays):
    exact = exact_products(*factors)
    prefix = name + "__"
    for i, value in enumerate(factors):
        arrays[prefix + "factor_" + str(i)] = np.asarray(value)
    arrays[prefix + "source"] = np.asarray(source)
    return dict(
        name=name,
        source_pJ_s=float(source),
        exact_product_sum=fraction_record(exact),
        rounded_source_minus_exact_products_pJ_s=float(rational(source) - exact),
        exact_products_use_already_rounded_inputs=True,
    )


def expanded_terms(model, state, layout, value, *, finite, arrays):
    """Expose original chemical products, all heat arrays and fuel products."""
    from cells.models import surface_calcium as calcium
    from cells.processes.electrochemistry import R

    p = model.stage_layout(layout, value.signal)
    raw = value.parent.parent
    dr = raw.derivative
    co = np.where(
        p.outside_active,
        (p.extracellular_amount_reference + state.extracellular_amount_increment)
        / p.extracellular_volume,
        1.0,
    )
    log_co = np.log(co)
    original = 1e-3 * R * p.temperature * np.sum(log_co * dr.extracellular_amount_increment)
    records = [
        product_record(
            "outside_chemical",
            original,
            (1e-3, R, p.temperature, log_co, dr.extracellular_amount_increment),
            arrays,
        )
    ]
    arrays["outside_concentration"] = co
    for i in range(p.er_initial_amount.shape[0]):
        s, c = calcium.store_state(state, i), calcium.store_layout(p, i)
        local = calcium.store_state(dr, i)
        concentration = (c.initial_amount + s.amount_increment) / (
            c.volume * c.standard_concentration
        )
        mu_rt = c.standard_mu_RT[:, None] + np.log(concentration)
        term = 1e-3 * R * c.temperature * np.sum(mu_rt * local.amount_increment)
        original += term
        records.append(
            product_record(
                "store_" + str(i) + "_chemical",
                term,
                (1e-3, R, c.temperature, mu_rt, local.amount_increment),
                arrays,
            )
        )
        arrays["store_" + str(i) + "_concentration"] = concentration
    if original != raw.field.chemical_energy_rate_pJ_s:
        raise ValueError("Chemical expansion does not reproduce the original grouping")
    mu = R * p.temperature * log_co
    additional = value.parent.closure.additional_reservoir_supply_fmol_s
    extra = 1e-3 * np.sum(mu * additional)
    if original + extra != value.parent.field.chemical_energy_rate_pJ_s:
        raise ValueError("Maintenance chemical correction does not reproduce the source")
    records.append(product_record("maintenance_chemical", extra, (1e-3, mu, additional), arrays))
    heat = []
    for name in dr._fields:
        if name.endswith("_dissipated_energy_pJ"):
            arrays[name + "__rate"] = np.asarray(getattr(dr, name))
            heat.append((name, np.sum(getattr(dr, name))))
    # The finite-fuel parent appends regeneration after the calcium heat sum.
    if sum(v for _, v in heat) != raw.field.dissipation_pJ_s:
        raise ValueError("Heat expansion does not reproduce the original grouping")
    heat_exact = sum((exact_products(arrays[n + "__rate"]) for n, _ in heat), Fraction())
    records.append(
        dict(
            name="all_dissipation_reductions",
            source_pJ_s=float(raw.field.dissipation_pJ_s),
            exact_product_sum=fraction_record(heat_exact),
            rounded_source_minus_exact_products_pJ_s=float(
                rational(raw.field.dissipation_pJ_s) - heat_exact
            ),
            source_groups=[n for n, _ in heat],
            upstream_heat_products_already_rounded=True,
        )
    )
    if finite:
        from cells.processes import finite_energy as energy

        rate, mu = raw.exchange.amount_fmol_s, raw.energy.chemical_potential_J_mol
        source = np.sum(energy.chemical_power_pJ_s(rate, raw.energy, xp=np))
        records.append(product_record("finite_fuel_chemical", source, (1e-3, mu, rate), arrays))
    return records


def program_identity(signal):
    """Exact diagnosis of C-(C+E)+E, including the rounded C+E input."""
    result = []
    for c, ec, electrode in zip(
        signal.chemical_power_pJ_s,
        signal.electrochemical_power_pJ_s,
        signal.electrode_power_pJ_s,
        strict=True,
    ):
        electric = -electrode
        if ec != c + electric:
            raise ValueError("Unexpected bath-program power expression")
        q_c, q_e, q_ec = rational(c), rational(electric), rational(ec)
        initial_error = q_ec - q_c - q_e
        observed = c - ec - electrode
        final_error = rational(observed) - (q_c - q_ec + q_e)
        assert rational(observed) == -initial_error + final_error
        result.append(
            dict(
                chemical_pJ_s=float(c),
                electric_pJ_s=float(electric),
                electrochemical_pJ_s=float(ec),
                observed_residual_pJ_s=float(observed),
                intermediate_addition_error_pJ_s=float(initial_error),
                final_reduction_error_pJ_s=float(final_error),
                unrounded_algebraic_identity_zero=True,
            )
        )
    return result


def field_power_record(model, state, layout, value, arrays, *, finite):
    """Exact decomposition using the production rate solve, never snapshot charge."""
    from cells.models import surface_calcium as calcium
    from cells.models import surface_tissue as passive
    from cells.numerics import surface_field as field
    from cells.processes.electrochemistry import CHARGE_PER_FMOL, F
    from validation.tissue.open_calcium_bath_energy_diagnostic import closure_terms

    p = model.stage_layout(layout, value.signal)
    f = passive.field_layout(p)
    dr = value.parent.derivative
    qdot = CHARGE_PER_FMOL * np.sum(
        p.valence
        * np.concatenate((dr.amount_increment, dr.extracellular_amount_increment), axis=1),
        axis=0,
    )
    d = field._capacitor_solve(qdot, np.zeros_like(qdot), f, xp=np)
    phi = value.parent.field.potential_V
    n, size = p.active.size, qdot.size
    reservoir = np.r_[np.zeros(n, dtype=bool), p.reservoir & p.outside_active]
    if np.any(qdot[reservoir] != 0) or np.any(d[f.fixed] != 0):
        raise ValueError("Expected fixed-voltage, zero maintained-reservoir amount rates")
    matrix = [[rational(v) for v in row] for row in f.capacitor_matrix]
    a = [[rational(v) for v in row] for row in f.capacitor_solve_matrix]
    scale, q = rational(f.capacitor_scale), [rational(v) for v in qdot]
    speed, potential = [rational(v) for v in d], [rational(v) for v in phi]
    b = np.where(~f.fixed, qdot / f.capacitor_scale, 0.0)
    b = [rational(v) for v in b]
    edge = [[Fraction() for _ in range(size)] for _ in range(size)]
    for j in np.flatnonzero(p.membrane_active):
        i, o = int(p.membrane_cell[j]), n + int(p.membrane_outside[j])
        c = rational(p.membrane_capacitance[j])
        edge[i][i] += c
        edge[o][o] += c
        edge[i][o] -= c
        edge[o][i] -= c
    kd = [sum((m * v for m, v in zip(row, speed, strict=True)), Fraction()) for row in matrix]
    ad = [sum((m * v for m, v in zip(row, speed, strict=True)), Fraction()) for row in a]
    residual = [v - w for v, w in zip(kd, q, strict=True)]
    solve = [scale * (v - w) for v, w in zip(ad, b, strict=True)]
    cache = [v - scale * w for v, w in zip(kd, ad, strict=True)]
    rhs = [scale * v - w for v, w in zip(b, q, strict=True)]
    for i in np.flatnonzero(~f.fixed):
        assert residual[i] == solve[i] + cache[i] + rhs[i]
    factor = rational(1e12)

    def power(values, mask):
        return factor * sum((potential[i] * values[i] for i in np.flatnonzero(mask)), Fraction())

    matrix_delta = [
        sum(((x - y) * v for x, y, v in zip(e, k, speed, strict=True)), Fraction())
        for e, k in zip(edge, matrix, strict=True)
    ]
    assembly_power = power(matrix_delta, np.ones(size, dtype=bool))
    free_power = power(residual, ~f.fixed)
    fixed_nonreservoir = power(residual, f.fixed & ~reservoir)
    # The representative of a floating component is fixed for the solve but
    # is not an electrode. Its voltage-weighted current must remain visible.
    ideal_capacitor = factor * sum(
        (
            potential[i] * sum((e * v for e, v in zip(edge[i], speed, strict=True)), Fraction())
            for i in range(size)
        ),
        Fraction(),
    )
    ionic_power = power(q, np.ones(size, dtype=bool))
    ideal_electrode = power(kd, reservoir)
    ideal_closure = ideal_capacitor - ionic_power - ideal_electrode
    assert ideal_closure == assembly_power + free_power + fixed_nonreservoir
    vm = value.parent.field.rates.membrane_voltage_V
    dvm = np.where(p.membrane_active, d[p.membrane_cell] - d[n + p.membrane_outside], 0.0)
    if not np.array_equal(dvm, value.parent.field.membrane_voltage_rate_V_s):
        raise ValueError("Rate solve does not replay the actual membrane voltage derivative")
    source_capacitor = 1e12 * np.sum(p.membrane_capacitance * vm * dvm)
    source_electrode = value.parent.field.electrode_power_pJ_s
    stored_products = exact_products(1e12, p.membrane_capacitance, vm, dvm)
    actual_closure = rational(source_capacitor) - ionic_power - rational(source_electrode)
    assert actual_closure == (
        ideal_closure
        + rational(source_capacitor)
        - ideal_capacitor
        - (rational(source_electrode) - ideal_electrode)
    )
    amount_rate = np.concatenate((dr.amount_increment, dr.extracellular_amount_increment), axis=1)
    ionic_mu_power = exact_products(1e-3, F, p.valence, phi, amount_rate)
    raw = value.parent.parent
    owned = raw.kinetic if finite else raw
    er_power = np.asarray(0.0)
    for i in range(p.er_initial_amount.shape[0]):
        local, c = calcium.store_state(dr, i), calcium.store_layout(p, i)
        er_power += (
            1e12
            * owned.er_voltage_V[i]
            * CHARGE_PER_FMOL
            * np.sum(c.valence * local.amount_increment[:, c.er])
        )
    if source_capacitor + er_power != value.parent.field.capacitor_energy_rate_pJ_s:
        raise ValueError("Plasma/ER split does not reproduce original capacitor power")
    seven = closure_terms(value, finite_fuel=finite)
    thermochemical = (
        sum(
            (
                rational(v)
                for k, v in seven.items()
                if k
                not in (
                    "capacitor_and_ER",
                    "negative_electrode",
                )
            ),
            Fraction(),
        )
        + rational(er_power)
        + ionic_mu_power
    )
    charge_conversion = ionic_power - ionic_mu_power
    expanded = thermochemical + actual_closure + charge_conversion
    exact_seven = sum((rational(v) for v in seven.values()), Fraction())
    assert expanded - exact_seven == (
        rational(source_capacitor) + rational(er_power) - rational(seven["capacitor_and_ER"])
    )
    arrays.update(
        {
            "field__" + k: np.asarray(v)
            for k, v in dict(
                qdot=qdot,
                potential=phi,
                potential_rate=d,
                capacitor_matrix=f.capacitor_matrix,
                normalized_matrix=f.capacitor_solve_matrix,
                scale=f.capacitor_scale,
                fixed=f.fixed,
                reservoir=reservoir,
                capacitance=p.membrane_capacitance,
                membrane_cell=p.membrane_cell,
                membrane_outside=p.membrane_outside,
                membrane_active=p.membrane_active,
                stored_vm=vm,
                stored_dvm=dvm,
            ).items()
        }
    )
    terms = dict(
        exact_edge_assembly_closure=ideal_closure,
        cached_capacitor_assembly=assembly_power,
        free_rate_residual=free_power,
        fixed_nonreservoir_current=fixed_nonreservoir,
        normalized_solve_backward=power(solve, ~f.fixed),
        normalized_matrix_cache=power(cache, ~f.fixed),
        normalized_rhs_rounding=power(rhs, ~f.fixed),
        stored_voltage_differences=stored_products - ideal_capacitor,
        capacitor_products_and_reductions=rational(source_capacitor) - stored_products,
        electrode_matvec_and_products=rational(source_electrode) - ideal_electrode,
        actual_capacitor_minus_ionic_minus_electrode=actual_closure,
        thermochemical_closure_frozen_rates=thermochemical,
        charge_conversion_and_reduction=charge_conversion,
        expanded_total=expanded,
        expanded_minus_exact_seven_term_inputs=expanded - exact_seven,
        saved_final_sum_minus_exact_seven=rational(value.parent.field.energy_balance_pJ_s)
        - exact_seven,
    )
    return dict(
        power_terms_pJ_s={k: float(v) for k, v in terms.items()},
        exact_power_terms={k: fraction_record(v) for k, v in terms.items()},
        max_rate_residual_A=float(max(map(abs, residual))),
        free_node_count=int(np.sum(~f.fixed)),
        fixed_nonreservoir_node_count=int(np.sum(f.fixed & ~reservoir & f.active)),
        scope="Frozen binary qdot/phi/dphi; upstream charge/scatter rounding is not bounded",
    )


def run(bundle, diagnostic, output):
    from cells.core.schedule import control_values
    from validation.tissue import open_calcium_bath_energy_diagnostic as prior
    from validation.tissue import open_calcium_bath_reference as reference
    from validation.tissue import open_calcium_bath_trajectory_common as artifact
    from validation.tissue.open_calcium_bath_trajectory_observers import full_state

    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    last = {}
    try:
        bundle, diagnostic = Path(bundle).resolve(), Path(diagnostic).resolve()
        artifact.verify_bundle(bundle)
        saved = artifact.verify_result(diagnostic)
        if saved["bundle_manifest_sha256"] != artifact.sha(bundle / "manifest.json"):
            raise ValueError("Different frozen source bundle")
        plan = artifact.read_json(bundle / "plan.json")
        records, constant_names = [], set()
        for family in ("ordinary-calcium", "ordinary-energy"):
            finite = family.endswith("energy")
            if finite:
                from cells.core import surface_open_calcium_energy_bath_events_spec as schema
                from cells.models import surface_open_calcium_energy_bath_events as model
            else:
                from cells.core import surface_open_calcium_bath_events_spec as schema
                from cells.models import surface_open_calcium_bath_events as model
            raw = artifact.read_json(bundle / plan["datasets"][family]["definition"])
            spec, context = schema.parse(raw), reference.bind(raw)
            zero, layout = model.initial_values(spec)
            with np.load(diagnostic / (family + "-layout.npz"), allow_pickle=False) as arrays:
                if set(arrays.files) != set(layout._fields) or any(
                    not np.array_equal(arrays[name], getattr(layout, name))
                    for name in layout._fields
                ):
                    raise ValueError("Frozen physical layout changed")
            for row in saved["records"]:
                if not row["job"].startswith(family) or row["status"] != "saved_row_replayed":
                    continue
                last = dict(job=row["job"], time_s=row["time_s"], sample_index=row["sample_index"])
                with np.load(diagnostic / row["arrays"], allow_pickle=False) as arrays:
                    state = full_state(model, zero, context, arrays["complete_saved_state"])
                    table = control_values(schema.owner_spec(spec), [row["time_s"]])
                    control = type(table)(*(v[0] for v in table))
                    if any(
                        not np.array_equal(v, arrays["control__" + k])
                        for k, v in control._asdict().items()
                    ):
                        raise ValueError("Frozen actual control changed")
                baseline = model.readouts(state, control, layout, xp=np)
                observed = row["reduction"]["observed_pJ_s"]
                if not baseline.valid or baseline.field.energy_balance_pJ_s != observed:
                    raise ValueError("Original failed residual no longer reproduces exactly")
                arrays = dict(baseline_state=np.concatenate([v.ravel() for v in state]))
                expanded = expanded_terms(
                    model, state, layout, baseline, finite=finite, arrays=arrays
                )
                field = field_power_record(model, state, layout, baseline, arrays, finite=finite)
                modes = {}
                for promote_constants in (False, True):
                    mode = "wider_arrays_and_constants" if promote_constants else "wider_arrays"
                    with wider_arithmetic(constants=promote_constants) as names:
                        constant_names.update(names)
                        wide = model.readouts(widen(state), widen(control), widen(layout), xp=np)
                        terms = prior.closure_terms(wide, finite_fuel=finite)
                        exact = sum((rational(v) for v in terms.values()), Fraction())
                    if not wide.valid or any(not np.isfinite(v).all() for v in wide.derivative):
                        raise ValueError("Wider diagnostic readout violates the original domain")
                    arrays[mode + "__terms"] = np.asarray(list(terms.values()), dtype=np.longdouble)
                    arrays[mode + "__potential"] = wide.field.potential_V
                    for key in wide.derivative._fields:
                        arrays[mode + "__rhs__" + key] = getattr(wide.derivative, key)
                    modes[mode] = dict(
                        residual_pJ_s=float(wide.field.energy_balance_pJ_s),
                        residual_decimal=str(wide.field.energy_balance_pJ_s),
                        exact_sum_of_generated_terms=fraction_record(exact),
                        largest_potential_change_V=float(
                            np.max(np.abs(wide.field.potential_V - baseline.field.potential_V))
                        ),
                        charge_normalized=float(wide.field.charge_normalized),
                        current_normalized=float(wide.field.current_normalized),
                        program_identity=program_identity(wide.signal),
                    )
                filename = row["arrays"]
                artifact.save_arrays(output / filename, **arrays)
                records.append(
                    last
                    | dict(
                        original_residual_pJ_s=observed,
                        expanded_terms=expanded,
                        field_power=field,
                        program_identity=program_identity(baseline.signal),
                        modes=modes,
                        arrays=filename,
                    )
                )
        artifact.verify_bundle(bundle)
        artifact.verify_result(diagnostic)
        artifact.success(
            output,
            dict(
                kind="cells.saved_bath_energy_upstream_diagnosis@1",
                records=records,
                replayed_rows=len(records),
                source_bundle_sha256=artifact.sha(bundle / "manifest.json"),
                prior_diagnostic_sha256=artifact.sha(diagnostic / "result.json"),
                longdouble_mantissa_bits=np.finfo(np.longdouble).nmant + 1,
                decimal_solve_digits=80,
                promoted_constant_sites=sorted(constant_names),
                physical_constants=(
                    "Exact frozen binary values; no decimal reinterpretation or recomputation"
                ),
                scope=(
                    "Selected fixed states, exact products and wider source arithmetic; "
                    "no trajectory or acceptance change"
                ),
                limitations=[
                    "Wider runtime is the same production formula, not an independent oracle",
                    "Frozen binary64 layout, normalized solve matrix and anchors remain unchanged",
                    "Exact product sums do not bound errors in their already-rounded inputs",
                    "Long double/transcendental functions give no rigorous interval bound",
                ],
                original_failures_retained=True,
                automatic_followup=False,
            ),
        )
    except BaseException as error:
        artifact.failure(output, error, context=last)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--diagnostic", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run(args.bundle, args.diagnostic, args.output)
