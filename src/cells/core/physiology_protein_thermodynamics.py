"""Optional Cells ideal-protein energies and conditional endpoint work.

This is not a native BETSE energy law. Fixed owner volumes, declared T/c0/R,
and explicit reference/current stocks define the chemical frame. Zero stocks
have zero free energy and minus-infinite ideal chemical potential. No floor,
stock/anchor rebase, field solve, heat, stochastic work or holding work is
inferred. Conditional endpoint work is not an attainable protocol minimum.
"""

import math
from dataclasses import dataclass
from decimal import Context, Decimal, localcontext
from functools import lru_cache
from types import MappingProxyType

import numpy as np

from cells.core import physiology_protein_projection as projection
from cells.core.physiology_perturbation_step import BALANCE_RELATIVE_TOLERANCE
from cells.processes.electrochemistry import R

KIND = "cells.ideal_protein_thermodynamics@1"
PJ_PER_J = Decimal("1e12")


class ProteinThermodynamicsError(ValueError):
    """Invalid/unrepresentable diagnostic, retaining exact computed evidence."""

    def __init__(self, reason, *, raw=None):
        super().__init__(str(reason))
        self.raw = MappingProxyType({key: str(value) for key, value in (raw or {}).items()})


@dataclass(frozen=True, slots=True)
class ProteinThermodynamics:
    cell_ids: tuple
    environment_ids: tuple
    binding_identity: str
    temperature_K: float
    standard_concentration_mol_m3: float
    gas_constant_J_mol_K: float
    cell_free_energy_pJ: object
    environment_free_energy_pJ: object
    total_free_energy_pJ: float
    cell_chemical_potential_J_mol: object
    environment_chemical_potential_J_mol: object
    cell_zero_stock: object
    environment_zero_stock: object


@dataclass(frozen=True, slots=True)
class ProteinFreeEnergyChange:
    baseline: ProteinThermodynamics
    current: ProteinThermodynamics
    cell_free_energy_change_pJ: object
    environment_free_energy_change_pJ: object
    total_free_energy_change_pJ: float
    amount_balance_residual_mol: float
    amount_balance_residual_mol_exact: str
    gross_amount_change_mol: float
    gross_amount_change_mol_exact: str
    conservation_tolerance_mol: float
    conservation_tolerance_mol_exact: str
    stock_resolution_bound_mol: float
    stock_resolution_bound_mol_exact: str
    material_diagnostics_representable: bool
    strict_conservation_valid: bool


@dataclass(frozen=True, slots=True)
class ProteinEndpointWork:
    chemical_change: ProteinFreeEnergyChange
    protein_free_energy_change_pJ: float
    capacitor_energy_change_pJ: float
    clamp_work_pJ: float
    conditional_reversible_driving_work_pJ: float
    algebraic_rounding_residual_pJ_exact: str
    admission: object

    @property
    def reversible_driving_work_pJ(self):
        """Alias retaining the explicitly conditional, fixed-ion interpretation."""
        return self.conditional_reversible_driving_work_pJ


def _d(value):
    return Decimal.from_float(float(value))


@lru_cache(maxsize=512)
def _ln(value):
    # More than 100 guard digits beyond float64, including near-equilibrium
    # second-order changes. Products/sums use exact input decimals at 4096
    # digits so tiny stocks are not lost to premature amount conversion.
    with localcontext(Context(prec=160)):
        return _d(value).ln()


def _rounded(value, name, *, zero_stock_potential=False):
    if zero_stock_potential and value == Decimal("-Infinity"):
        return -math.inf
    result = float(value)
    if not math.isfinite(result) or (value != 0 and result == 0):
        raise ProteinThermodynamicsError(
            "Unrepresentable protein thermodynamic " + name, raw={name: value}
        )
    return result


def _frame(temperature_K, standard_concentration_mol_m3, gas_constant_J_mol_K):
    return tuple(
        projection._number(value, name, positive=True)
        for name, value in (
            ("temperature_K", temperature_K),
            ("standard_concentration_mol_m3", standard_concentration_mol_m3),
            ("gas_constant_J_mol_K", gas_constant_J_mol_K),
        )
    )


def _state(binding, geometry, frame):
    t, c0, r = frame
    cells, exterior, vc, ve = geometry
    values, potentials, amounts, entropy = [], [], [], []
    with localcontext(Context(prec=4096)):
        rt, l0 = _d(r) * _d(t), _ln(c0)
        for concentrations, volumes in ((cells, vc), (exterior, ve)):
            g, mu, n, s = [], [], [], []
            for c, v in zip(concentrations, volumes, strict=True):
                amount = _d(c) * _d(v)
                term = Decimal(0) if c == 0 else amount * _ln(float(c))
                energy = rt * (term - amount * (l0 + 1)) * PJ_PER_J
                potential = Decimal("-Infinity") if c == 0 else rt * (_ln(float(c)) - l0)
                g.append(_rounded(energy, "free_energy_pJ"))
                mu.append(
                    _rounded(potential, "chemical_potential_J_mol", zero_stock_potential=c == 0)
                )
                n.append(amount)
                s.append(term)
            values.append(g)
            potentials.append(mu)
            amounts.append(n)
            entropy.append(s)
        total = (
            rt
            * (
                sum((*entropy[0], *entropy[1]), Decimal(0))
                - (l0 + 1) * sum((*amounts[0], *amounts[1]), Decimal(0))
            )
            * PJ_PER_J
        )
        state = ProteinThermodynamics(
            binding.tissue_cell_ids,
            binding.tissue_environment_ids,
            binding.identity,
            t,
            c0,
            r,
            projection._freeze(np.asarray(values[0])),
            projection._freeze(np.asarray(values[1])),
            _rounded(total, "total_free_energy_pJ"),
            projection._freeze(np.asarray(potentials[0])),
            projection._freeze(np.asarray(potentials[1])),
            projection._freeze(cells == 0),
            projection._freeze(exterior == 0),
        )
        return state, amounts, entropy


def evaluate(
    protein,
    binding,
    *,
    temperature_K,
    standard_concentration_mol_m3,
    gas_constant_J_mol_K=R,
):
    """Ideal chemical G=RT sum[n(log(c/c0)-1)] with declared mu0=0.

    Membrane concentration views are excluded. Positive tiny concentrations
    are multiplied/scaled before float64 conversion; actual zeros use the
    continuous x*log(x) limit and have explicit minus-infinite ideal mu.
    """
    frame = _frame(temperature_K, standard_concentration_mol_m3, gas_constant_J_mol_K)
    return _state(binding, projection._geometry(protein, binding), frame)[0]


def change(
    reference_protein,
    current_protein,
    binding,
    *,
    temperature_K,
    standard_concentration_mol_m3,
    gas_constant_J_mol_K=R,
):
    """Stable chemical endpoint difference, without subtracting rounded totals.

    General material changes are reported, including zero/tiny stocks; the
    strict closed-material gate is applied only by endpoint_work. The common
    standard-state term uses the actual net amount change, never a forced zero.
    Exact material strings retain values below float64 mol resolution.
    """
    frame = _frame(temperature_K, standard_concentration_mol_m3, gas_constant_J_mol_K)
    before = projection._geometry(reference_protein, binding)
    after = projection._geometry(current_protein, binding)
    baseline, n0, s0 = _state(binding, before, frame)
    current, n1, s1 = _state(binding, after, frame)
    with localcontext(Context(prec=4096)):
        rt, l0 = _d(frame[2]) * _d(frame[0]), _ln(frame[1])
        dn, ds, dg = [], [], []
        for old_n, new_n, old_s, new_s in zip(n0, n1, s0, s1, strict=True):
            amount = [b - a for a, b in zip(old_n, new_n, strict=True)]
            entropy = [b - a for a, b in zip(old_s, new_s, strict=True)]
            energy = [
                rt * (s - (l0 + 1) * n) * PJ_PER_J for n, s in zip(amount, entropy, strict=True)
            ]
            dn.extend(amount)
            ds.extend(entropy)
            dg.append([_rounded(value, "free_energy_change_pJ") for value in energy])
        net = sum(dn, Decimal(0))
        gross = sum((abs(value) for value in dn), Decimal(0))
        tolerance = _d(BALANCE_RELATIVE_TOLERANCE) * gross
        stock = sum(
            (
                (_d(math.ulp(float(a))) + _d(math.ulp(float(b)))) * _d(v) / 2
                for a, b, v in zip(
                    np.r_[before[0], before[1]],
                    np.r_[after[0], after[1]],
                    np.r_[before[2], before[3]],
                    strict=True,
                )
            ),
            Decimal(0),
        )
        material = (net, gross, tolerance, stock)
        display = tuple(float(value) for value in material)
        if not np.isfinite(display).all():
            raise ProteinThermodynamicsError(
                "Unrepresentable protein material diagnostic",
                raw=dict(
                    zip(("net", "gross", "tolerance", "stock_resolution"), material, strict=True)
                ),
            )
        total = rt * (sum(ds, Decimal(0)) - (l0 + 1) * net) * PJ_PER_J
        return ProteinFreeEnergyChange(
            baseline,
            current,
            projection._freeze(np.asarray(dg[0])),
            projection._freeze(np.asarray(dg[1])),
            _rounded(total, "total_free_energy_change_pJ"),
            display[0],
            str(net),
            display[1],
            str(gross),
            display[2],
            str(tolerance),
            display[3],
            str(stock),
            all(value == 0 or shown != 0 for value, shown in zip(material, display, strict=True)),
            bool(abs(net) <= tolerance),
        )


def endpoint_work(chemical_change, *, capacitor_energy_change_pJ, clamp_work_pJ):
    """Conditional reversible requirement with fixed ions, T, volume and clamps.

    W_conditional=delta G_protein+delta U_capacitor-W_clamp; clamp work is positive
    into the system. This is signed endpoint accounting, not attainable minimum
    or total protocol/holding work. Heat and stochastic work are not inferred.
    The caller supplies independently justified capacitor/clamp work inputs.
    """
    if type(chemical_change) is not ProteinFreeEnergyChange:
        raise ValueError("Require an explicit ProteinFreeEnergyChange")
    if not chemical_change.strict_conservation_valid:
        raise ProteinThermodynamicsError(
            "Closed-protein endpoint work requires strict material conservation",
            raw=dict(
                amount_balance_residual_mol=chemical_change.amount_balance_residual_mol_exact,
                conservation_tolerance_mol=chemical_change.conservation_tolerance_mol_exact,
                total_free_energy_change_pJ=chemical_change.total_free_energy_change_pJ,
            ),
        )
    du = projection._number(capacitor_energy_change_pJ, "capacitor_energy_change_pJ")
    clamp = projection._number(clamp_work_pJ, "clamp_work_pJ")
    dg = chemical_change.total_free_energy_change_pJ
    with localcontext(Context(prec=4096)):
        exact = _d(dg) + _d(du) - _d(clamp)
        result = _rounded(exact, "conditional_reversible_driving_work_pJ")
        residual = exact - _d(result)
    return ProteinEndpointWork(
        chemical_change,
        dg,
        du,
        clamp,
        result,
        str(residual),
        MappingProxyType(
            dict(
                kind=KIND,
                optional_Cells_physics=True,
                native_BETSE_energy_law=False,
                fixed_ion_constraints=True,
                holding_work_included=False,
                total_protocol_work_claim=False,
                attainable_minimum_claim=False,
                heat_inferred=False,
                stochastic_work_inferred=False,
                clamp_work_positive_into_system=True,
            )
        ),
    )
