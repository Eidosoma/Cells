"""Material and energy admission between complete states at held protein/P.

Original ionic, chemical, fuel and charge anchors are immutable. Chemical and
capacitor changes use increments, never subtraction of rounded bulk totals.
This host accounting owns no clock, random draw, integrator or checkpoint I/O.
"""

import math
from dataclasses import dataclass
from decimal import Context, Decimal, localcontext
from types import MappingProxyType

import numpy as np

from cells.core import physiology_protein_projection as projection
from cells.core import physiology_tissue_binding as units
from cells.core.errors import NumericalError
from cells.core.specs import SimulationSpec
from cells.models import compartment_reactions as chemistry
from cells.models import physiology_permeability_view as view
from cells.models import physiology_protein_charge_rhs as charged
from cells.models import physiology_protein_charge_view as charge_view
from cells.models import surface_calcium as calcium
from cells.models import surface_calcium_energy as fuel
from cells.models import surface_tissue as passive
from cells.numerics import surface_field as field
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R

KIND = "cells.physiology_protein_interval_accounting@1"


@dataclass(frozen=True, slots=True)
class IntervalAccounting:
    valid: bool
    balances: object
    limits: object
    energy_terms: object
    diagnostics: object
    checks: object


class IntervalAccountingRejected(NumericalError):
    """Refused interval with unmodified endpoints and every available check."""

    def __init__(self, reason, *, before, after, report=None):
        super().__init__("Held-protein interval accounting refused: " + str(reason))
        self.before = view._immutable_tree(before)
        self.after = view._immutable_tree(after)
        self.report = report
        self.accounting = report


def _d(value):
    return Decimal.from_float(float(value))


def _freeze_tree(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_tree(item) for key, item in value.items()})
    if isinstance(value, np.ndarray):
        return view._freeze(value)
    if isinstance(value, tuple):
        return tuple(_freeze_tree(item) for item in value)
    return value


def _log1p(value):
    """Relative-precision series, including increments below Decimal's ULP."""
    with localcontext(Context(prec=160)):
        if abs(value) > Decimal("0.125"):
            return (1 + value).ln()
        term, total, index = value, value, 1
        while term:
            index += 1
            term *= -value
            next_total = total + term / index
            if next_total == total:
                break
            total = next_total
        return total


def _h(value):
    with localcontext(Context(prec=160)):
        if abs(value) > Decimal("0.125"):
            return (1 + value) * (1 + value).ln() - value
        power, total, index = value * value, Decimal(0), 2
        while power:
            next_total = total + power / (index * (index - 1))
            if next_total == total:
                break
            total = next_total
            power *= -value
            index += 1
        return total


def _ideal_change(anchor, before, after, volume, standard, mu0_rt, temperature, active):
    """Exact f64 inputs, stable ideal DeltaG per species/owner (Decimal pJ)."""
    arrays = np.broadcast_arrays(anchor, before, after, volume, standard, mu0_rt, active)
    result = np.empty(arrays[0].shape, dtype=object)
    with localcontext(Context(prec=4096)):
        thermal = Decimal("0.001") * _d(R) * _d(temperature)
        for index in np.ndindex(result.shape):
            a, b, e, v, c0, mu, live = (value[index] for value in arrays)
            if not live:
                result[index] = Decimal(0)
                continue
            n, dn, scale = _d(a) + _d(b), _d(e) - _d(b), _d(v) * _d(c0)
            if n <= 0 or n + dn <= 0 or scale <= 0:
                raise ValueError("Chemical interval leaves its original positive owner domain")
            if dn == 0:
                result[index] = Decimal(0)
                continue
            log = _log1p((n - scale) / scale)
            result[index] = thermal * (dn * (_d(mu) + log) + n * _h(dn / n))
    return result


def _sum(values):
    return sum(np.asarray(values, dtype=object).flat, Decimal(0))


def _number(value):
    result = float(value)
    if not math.isfinite(result) or (result == 0 and value != 0):
        raise ValueError("Unrepresentable nonzero interval quantity: " + str(value))
    return result


def _float_array(values):
    return np.asarray([_number(value) for value in values], dtype=np.float64)


def _difference_sum(before, after):
    return sum(
        (
            _d(e) - _d(b)
            for b, e in zip(np.asarray(before).flat, np.asarray(after).flat, strict=True)
        ),
        Decimal(0),
    )


def _pool_change(before, after, p):
    mixing = _ideal_change(
        p.energy_initial_amount_fmol,
        before.energy_amount_increment_fmol,
        after.energy_amount_increment_fmol,
        p.volume,
        fuel.energy.STANDARD_STATE_mM,
        0.0,
        p.temperature,
        p.active,
    )
    result = []
    for i in range(p.active.size):
        standard = (
            -Decimal("0.001")
            * _d(p.energy_delta_g0_J_mol[i])
            * (
                _d(after.energy_amount_increment_fmol[0, i])
                - _d(before.energy_amount_increment_fmol[0, i])
            )
        )
        result.append(_sum(mixing[:, i]) + standard)
    return np.asarray(result, dtype=object)


def _pool_balance(before, after, p, free):
    result = list(free)
    owners = fuel.pump_routes(p).owner
    works = [
        np.concatenate((s.metabolic_work_pJ, s.plasma_metabolic_work_pJ, s.er_metabolic_work_pJ))
        for s in (before, after)
    ]
    for owner, b, e in zip(owners, *works, strict=True):
        result[int(owner)] += _d(e) - _d(b)
    for i, owner in enumerate(p.regeneration_owner):
        result[int(owner)] += (
            _d(after.regeneration_dissipated_energy_pJ[i])
            - _d(before.regeneration_dissipated_energy_pJ[i])
            - _d(after.regeneration_supplied_work_pJ[i])
            + _d(before.regeneration_supplied_work_pJ[i])
        )
    return _float_array(result)


def _chemical(before, after, p):
    outside = _ideal_change(
        p.extracellular_amount_reference,
        before.extracellular_amount_increment,
        after.extracellular_amount_increment,
        p.extracellular_volume,
        1.0,
        0.0,
        p.temperature,
        p.outside_active,
    )
    if not hasattr(before, "chemical_amount_increment"):
        inside = _ideal_change(
            p.amount_reference,
            before.amount_increment,
            after.amount_increment,
            p.volume,
            1.0,
            0.0,
            p.temperature,
            p.active,
        )
        return _sum(inside) + _sum(outside), Decimal(0)
    chemical, electric = _sum(outside), Decimal(0)
    for i in range(p.er_initial_amount.shape[0]):
        b, e, c = (
            calcium.store_state(before, i),
            calcium.store_state(after, i),
            calcium.store_layout(p, i),
        )
        chemical += _sum(
            _ideal_change(
                c.initial_amount,
                b.amount_increment,
                e.amount_increment,
                c.volume,
                c.standard_concentration,
                c.standard_mu_RT[:, None],
                c.temperature,
                c.active,
            )
        )
        dq = _d(CHARGE_PER_FMOL) * sum(
            (
                _d(z) * (_d(y) - _d(x))
                for z, x, y in zip(
                    c.valence, b.amount_increment[:, c.er], e.amount_increment[:, c.er], strict=True
                )
            ),
            Decimal(0),
        )
        dv = dq / _d(c.capacitance)
        vb = _d(calcium.er.voltage(b, c, xp=np))
        electric += Decimal("5e11") * _d(c.capacitance) * dv * (2 * vb + dv)
    return chemical, electric


def _limits(spec, state, p):
    tol = np.asarray(spec.execution.material_balance_atol_fmol)
    q = np.r_[p.initial_cell_charge_C, p.initial_outside_charge_C]
    q = q + passive.charge_increment(state, p, xp=np)
    electrode = field.CHARGE_ATOL_C
    if not hasattr(state, "chemical_amount_increment"):
        electrode += field.CHARGE_RTOL * abs(state.electrode_charge_transferred_C)
    return dict(
        local=tol[:, None],
        outside=tol[:, None],
        total=tol,
        charge=field.CHARGE_ATOL_C + field.CHARGE_RTOL * abs(q),
        electrode=electrode,
        global_charge=3e-25,
        energy=(
            calcium.ENERGY_ATOL_PJ
            if hasattr(state, "chemical_amount_increment")
            else passive.ENERGY_ATOL_PJ
        ),
        reservoir_work=3e-12,
        electrode_work=3e-12,
        metabolic_work=3e-12,
        plasma_metabolic_work=3e-12,
        er_metabolic_work=3e-12,
        chemical_ledger=chemistry.ROUND_ATOL,
        ownership=chemistry.ROUND_ATOL,
        pool_material=fuel.POOL_MATERIAL_ATOL_FMOL,
        adenylate=fuel.POOL_MATERIAL_ATOL_FMOL,
        phosphorus=fuel.POOL_MATERIAL_ATOL_FMOL,
        pool_energy=fuel.ENERGY_ATOL_PJ,
        regeneration_work=3e-12,
    )


def _prepare(spec, before, after, layout, binding, reference, component, species, valence):
    if type(spec) is not SimulationSpec or type(spec.model) not in view.IMPLEMENTATIONS:
        raise ValueError("Require one of the four exact ordinary tissue families")
    units.restore_binding(units.binding_record(binding), spec)
    units.component_permeability(reference, binding)
    physical = units.component_permeability(component, binding)
    implementation = view.IMPLEMENTATIONS[type(spec.model)]
    initial, original = implementation.initial_values(spec)
    if type(layout) is not type(original) or any(
        np.asarray(a).dtype != np.asarray(b).dtype
        or np.shape(a) != np.shape(b)
        or not np.array_equal(a, b)
        for a, b in zip(layout, original, strict=True)
    ):
        raise ValueError("Require the unchanged original complete layout and anchors")
    b, e = view._state(before, initial), view._state(after, initial)
    p = type(layout)(*(np.asarray(value) for value in layout))
    p = p._replace(membrane_permeability=physical.current_m_s)
    if not np.array_equal(
        p.membrane_permeability > 0, np.asarray(layout.membrane_permeability) > 0
    ):
        raise ValueError("Held permeability must preserve the original route support")
    occupied = charge_view._species_ids(spec.to_dict()["model"])
    if hasattr(b, "energy_amount_increment_fmol"):
        occupied.update(("ATP", "ADP", "Pi"))
    if type(species) is not str or not species.strip() or species in occupied:
        raise ValueError("Require a distinct explicit protein species identity")
    change = projection.delta(
        reference.protein, component.protein, binding, valence=valence, faraday_C_mol=F
    )
    if not change.strict_conservation_valid:
        raise ValueError("Held-protein intervals require strict closed protein conservation")
    delta = np.zeros(p.active.size + p.outside_active.size)
    delta[: len(binding.tissue_cell_ids)] = change.cell_charge_delta_C
    delta[p.active.size : p.active.size + len(binding.tissue_environment_ids)] = (
        change.environment_charge_delta_C
    )
    return implementation, b, e, p, delta


def evaluate(
    spec,
    before,
    after,
    layout,
    binding,
    charge_reference,
    component,
    *,
    protein_species_id,
    valence,
    before_control,
    after_control,
):
    """Admit a local or original-seed interval at fixed actual protein/P.

    Endpoints need not pass the old uncharged overall energy-history validator.
    All its other domain/material/work checks remain, including per-pool energy.
    No protein transition or its preparation work is included in this interval.
    """
    report = None
    balances, limits, checks, rates = {}, {}, {}, []
    terms = {}
    try:
        implementation, b, e, p, delta = _prepare(
            spec,
            before,
            after,
            layout,
            binding,
            charge_reference,
            component,
            protein_species_id,
            valence,
        )
        controls = (view._control(spec, before_control), view._control(spec, after_control))

        def record(name, value, limit):
            value, limit = np.asarray(value), np.asarray(limit)
            balances[name], limits[name] = view._freeze(value), view._freeze(limit)
            checks[name] = bool(np.isfinite(value).all() and np.all(abs(value) <= limit))

        endpoints = []
        with localcontext(Context(prec=4096)), np.errstate(all="ignore"):
            zero = type(b)(*(np.zeros_like(value) for value in b))
            for label, state, control in zip(("before", "after"), (b, e), controls, strict=True):
                checks[label + "/domain"] = bool(
                    implementation.domain_valid(state, p, p.active, xp=np)
                )
                actual = charged.array_readouts(
                    state, control, p, delta, implementation=implementation, xp=np
                )
                rates.append(actual)
                checks[label + "/charged_field_rates"] = bool(actual.valid)
                current = dict(implementation.balances(state, p))
                # Deliberately do not gate the incompatible old uncharged global
                # energy. Retain every other check even if this value is invalid.
                current.pop("energy")
                if hasattr(state, "energy_amount_increment_fmol"):
                    free = _pool_change(zero, state, p)
                    current["pool_energy"] = _pool_balance(zero, state, p, free)
                bound = _limits(spec, state, p)
                for name, value in current.items():
                    record(label + "/" + name, value, bound[name])
                endpoints.append(current)
            for name in endpoints[0]:
                if name != "pool_energy":
                    record(
                        "interval/" + name,
                        endpoints[1][name] - endpoints[0][name],
                        np.maximum(_limits(spec, b, p)[name], _limits(spec, e, p)[name]),
                    )
            heat_tolerance = chemistry.ROUND_ATOL if implementation is view.calcium else 1e-12
            for name in b._fields:
                if name.endswith("_dissipated_energy_pJ"):
                    for label, value in (
                        ("before", getattr(b, name)),
                        ("after", getattr(e, name)),
                        ("interval", getattr(e, name) - getattr(b, name)),
                    ):
                        record(
                            label + "/nondecreasing/" + name, np.minimum(value, 0), heat_tolerance
                        )

            chemical, er_electric = _chemical(b, e, p)
            # Charge-only delta retains tiny material increments below bulk ULP.
            difference = e._replace(
                amount_increment=e.amount_increment - b.amount_increment,
                extracellular_amount_increment=e.extracellular_amount_increment
                - b.extracellular_amount_increment,
            )
            _, _, dv = passive.capacitor_change(difference, p, xp=np)
            vb, ve = (np.asarray(value.field.rates.membrane_voltage_V) for value in rates)
            plasma = sum(
                (
                    Decimal("5e11") * _d(c) * _d(d) * (2 * _d(v) + _d(d))
                    for c, d, v in zip(p.membrane_capacitance, dv, vb, strict=True)
                ),
                Decimal(0),
            )
            endpoint_plasma = sum(
                (
                    Decimal("5e11") * _d(c) * (_d(y) - _d(x)) * (_d(y) + _d(x))
                    for c, x, y in zip(p.membrane_capacitance, vb, ve, strict=True)
                ),
                Decimal(0),
            )
            heat = sum(
                (
                    _difference_sum(getattr(b, name), getattr(e, name))
                    for name in b._fields
                    if name.endswith("_dissipated_energy_pJ")
                ),
                Decimal(0),
            )
            reservoir = _difference_sum(b.reservoir_work_pJ, e.reservoir_work_pJ)
            electrode = _difference_sum(b.electrode_work_pJ, e.electrode_work_pJ)
            metabolic, pool, regeneration = Decimal(0), Decimal(0), Decimal(0)
            if hasattr(b, "energy_amount_increment_fmol"):
                free = _pool_change(b, e, p)
                pool = _sum(free)
                record("interval/pool_energy", _pool_balance(b, e, p, free), fuel.ENERGY_ATOL_PJ)
                regeneration = _difference_sum(
                    b.regeneration_supplied_work_pJ, e.regeneration_supplied_work_pJ
                )
            else:
                metabolic = sum(
                    (
                        _difference_sum(getattr(b, name), getattr(e, name))
                        for name in (
                            "metabolic_work_pJ",
                            "plasma_metabolic_work_pJ",
                            "er_metabolic_work_pJ",
                        )
                        if hasattr(b, name)
                    ),
                    Decimal(0),
                )
            exact = dict(
                chemical_change_pJ=chemical,
                plasma_capacitor_change_pJ=plasma,
                er_capacitor_change_pJ=er_electric,
                fuel_chemical_change_pJ=pool,
                dissipated_energy_pJ=heat,
                reservoir_work_pJ=reservoir,
                electrode_work_pJ=electrode,
                external_metabolic_work_pJ=metabolic,
                regeneration_supplied_work_pJ=regeneration,
            )
            residual = (
                chemical
                + plasma
                + er_electric
                + pool
                + heat
                - reservoir
                - electrode
                - metabolic
                - regeneration
            )
            record("interval/energy", _number(residual), _limits(spec, e, p)["energy"])
            terms = {name: _number(value) for name, value in exact.items()}
            diagnostics = dict(
                kind=KIND,
                binding_identity=binding.identity,
                protein_species_id=protein_species_id,
                valence=valence,
                original_anchors_preserved=True,
                protein_held=True,
                permeability_held=True,
                protein_preparation_work_accounted=False,
                exact_energy_terms={name: str(value) for name, value in exact.items()},
                exact_energy_residual_pJ=str(residual),
                actual_endpoint_plasma_change_pJ=_number(endpoint_plasma),
                plasma_endpoint_roundoff_pJ=_number(plasma - endpoint_plasma),
                ionic_charge_increment_C=passive.charge_increment(difference, p, xp=np),
                protein_charge_increment_C=delta,
                plasma_voltage_increment_V=dv,
                actual_endpoint_voltage_increment_V=ve - vb,
                failures=tuple(name for name, passed in checks.items() if not passed),
                legacy_overall_energy_admission_used=False,
            )
        report = IntervalAccounting(
            all(checks.values()),
            MappingProxyType(balances),
            MappingProxyType(limits),
            MappingProxyType(terms),
            _freeze_tree(diagnostics),
            MappingProxyType(checks),
        )
        if not report.valid:
            raise ValueError("; ".join(report.diagnostics["failures"]))
        return report
    except Exception as error:
        if report is None and checks:
            checks["accounting_computed"] = False
            report = IntervalAccounting(
                False,
                MappingProxyType(balances),
                MappingProxyType(limits),
                MappingProxyType(terms),
                _freeze_tree(
                    dict(
                        kind=KIND,
                        computation_error=str(error),
                        failures=tuple(name for name, passed in checks.items() if not passed),
                        original_anchors_preserved=True,
                    )
                ),
                MappingProxyType(checks),
            )
        raise IntervalAccountingRejected(
            error, before=before, after=after, report=report
        ) from error
