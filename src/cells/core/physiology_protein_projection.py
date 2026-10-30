"""Pure host projection of explicit protein stocks and reference/current deltas.

Volumes belong to the declared cell/exterior owners. Membrane concentrations
are views, never inventory. Valence and Faraday constant are explicit; no RNG,
clock, ionic inventory, charge anchor, field solve or baseline is changed.
Conservation reports keep strict gross tolerance and stock-resolution bounds
separate. They do not replace a later field/charge closure check.
"""

import math
from dataclasses import dataclass
from decimal import Decimal, localcontext
from numbers import Real
from types import MappingProxyType

import numpy as np

from cells.core import physiology_tissue_binding as units
from cells.core.physiology_perturbation_step import BALANCE_RELATIVE_TOLERANCE
from cells.processes import betse_perturbations as perturb

KIND = "cells.physiology_protein_projection@1"
FMOL_PER_MOL = 1e15


def _freeze(value):
    value = np.asarray(value)
    shape = value.shape
    return np.frombuffer(np.ascontiguousarray(value).tobytes(), dtype=value.dtype).reshape(shape)


def _number(value, name, *, positive=False):
    if not isinstance(value, Real) or isinstance(value, (bool, np.bool_)):
        raise ValueError(name + " requires an explicit finite real scalar")
    result = float(value)
    if not np.isfinite(result) or (positive and result <= 0):
        raise ValueError(
            name + " requires an explicit finite " + ("positive " if positive else "") + "scalar"
        )
    return result


class ProteinProjectionError(ValueError):
    """Invalid/unrepresentable input with unmodified raw numeric output retained."""

    def __init__(self, reason, *, raw=None):
        super().__init__(str(reason))
        self.raw = MappingProxyType({key: _freeze(value) for key, value in (raw or {}).items()})


@dataclass(frozen=True, slots=True)
class ProteinProjection:
    cell_ids: tuple
    environment_ids: tuple
    binding_identity: str
    valence: float
    faraday_C_mol: float
    cell_amount_mol: object
    environment_amount_mol: object
    cell_amount_fmol: object
    environment_amount_fmol: object
    cell_charge_C: object
    environment_charge_C: object
    total_amount_mol: float
    total_charge_C: float


@dataclass(frozen=True, slots=True)
class ProteinDelta:
    baseline: ProteinProjection
    current: ProteinProjection
    cell_amount_delta_mol: object
    environment_amount_delta_mol: object
    cell_amount_delta_fmol: object
    environment_amount_delta_fmol: object
    cell_charge_delta_C: object
    environment_charge_delta_C: object
    balance_residual_mol: float
    balance_residual_C: float
    gross_change_mol: float
    conservation_tolerance_mol: float
    conservation_tolerance_C: float
    stock_resolution_bound_mol: float
    projection_roundoff_bound_mol: float
    charge_roundoff_bound_C: float
    strict_conservation_valid: bool
    conservation_valid: bool
    storage_resolution_used: bool


def _geometry(protein, binding):
    units.validate_binding(binding)
    if type(protein) is not perturb.ProteinState:
        raise ValueError("Require a complete typed ProteinState")
    component = binding.component
    for value, owners in zip(
        protein,
        (component.cell_ids, component.membrane_ids, component.environment_ids),
        strict=True,
    ):
        value = np.asarray(value)
        if (
            value.shape != (len(owners),)
            or value.dtype != np.float64
            or not np.isfinite(value).all()
            or np.any(value < 0)
        ):
            raise ValueError("Protein buffers require finite nonnegative float64 owner vectors")
    cell = np.argsort(binding.cell_to_tissue)
    exterior = np.argsort(binding.environment_to_tissue)
    return (
        np.asarray(protein.cell_mol_m3)[cell],
        np.asarray(protein.environment_mol_m3)[exterior],
        np.asarray(component.kernel.cell_volume_m3)[cell],
        np.asarray(component.kernel.environment_effective_volume_m3)[exterior],
    )


def _amount_charge(cell_concentration, exterior_concentration, cell_volume, exterior_volume, z, f):
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        a, b = cell_concentration * cell_volume, exterior_concentration * exterior_volume
        return dict(
            cell_amount_mol=a,
            environment_amount_mol=b,
            cell_amount_fmol=a * FMOL_PER_MOL,
            environment_amount_fmol=b * FMOL_PER_MOL,
            cell_charge_C=(a * z) * f,
            environment_charge_C=(b * z) * f,
        )


def _representable(raw, concentrations, z):
    if any(not np.isfinite(value).all() for value in raw.values()):
        raise ProteinProjectionError(
            "Protein amount/charge projection overflows or is nonfinite", raw=raw
        )
    for prefix, concentration in zip(("cell", "environment"), concentrations, strict=True):
        amount, charge = raw[prefix + "_amount_mol"], raw[prefix + "_charge_C"]
        if np.any((concentration != 0) & (amount == 0)):
            raise ProteinProjectionError(
                "Nonzero protein amount underflows during SI conversion", raw=raw
            )
        if z != 0 and np.any((amount != 0) & (charge == 0)):
            raise ProteinProjectionError(
                "Nonzero protein charge underflows during conversion", raw=raw
            )


def _decimal(value):
    return Decimal.from_float(float(value))


def _sum(values):
    return sum((_decimal(value) for value in values), Decimal(0))


def _ceil_float(value):
    """Outward round diagnostic bounds only; never alter an inventory or charge."""
    result = float(value)
    if not np.isfinite(result):
        raise ProteinProjectionError("Protein projection diagnostic is unrepresentable")
    return float(np.nextafter(result, np.inf)) if _decimal(result) < value else result


def project(protein, binding, *, valence, faraday_C_mol):
    """Report absolute stocks in unpadded physical tissue-owner order.

    For the Cells field the caller supplies electrochemistry.F; native BETSE
    uses 96485 instead. No default hides that distinction. Membrane values may
    be stale but must satisfy the original finite nonnegative buffer domain.
    """
    z = _number(valence, "valence")
    f = _number(faraday_C_mol, "faraday_C_mol", positive=True)
    cell, exterior, vc, ve = _geometry(protein, binding)
    raw = _amount_charge(cell, exterior, vc, ve, z, f)
    _representable(raw, (cell, exterior), z)
    with localcontext() as context:
        context.prec = 4096
        total_amount = float(_sum(np.r_[raw["cell_amount_mol"], raw["environment_amount_mol"]]))
        total_charge = float(_sum(np.r_[raw["cell_charge_C"], raw["environment_charge_C"]]))
    if not np.isfinite([total_amount, total_charge]).all():
        raise ProteinProjectionError(
            "Total projected protein stock or charge is unrepresentable", raw=raw
        )
    return ProteinProjection(
        binding.tissue_cell_ids,
        binding.tissue_environment_ids,
        binding.identity,
        z,
        f,
        **{key: _freeze(value) for key, value in raw.items()},
        total_amount_mol=total_amount,
        total_charge_C=total_charge,
    )


def delta(reference_protein, current_protein, binding, *, valence, faraday_C_mol):
    """Report (current concentration - reference concentration) * owner volume.

    The explicit reference never changes. Raw residuals are not redistributed.
    ``strict_conservation_valid`` retains 3e-13 times actual gross amount change.
    ``conservation_valid`` additionally accounts for the stated half-ULP input
    stock resolution and exact floating projection error. Reliance on stock
    resolution is explicit; later field closure retains its own tolerance.
    Nonconservative deltas are returned with false flags, never repaired.
    """
    baseline = project(reference_protein, binding, valence=valence, faraday_C_mol=faraday_C_mol)
    current = project(current_protein, binding, valence=valence, faraday_C_mol=faraday_C_mol)
    before_cell, before_env, vc, ve = _geometry(reference_protein, binding)
    after_cell, after_env, _, _ = _geometry(current_protein, binding)
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        dc, de = after_cell - before_cell, after_env - before_env
    raw = _amount_charge(dc, de, vc, ve, baseline.valence, baseline.faraday_C_mol)
    _representable(raw, (dc, de), baseline.valence)
    arrays = {
        key.replace("_amount_", "_amount_delta_").replace("_charge_", "_charge_delta_"): value
        for key, value in raw.items()
    }
    with localcontext() as context:
        context.prec = 4096
        before, after, volume = (
            np.r_[before_cell, before_env],
            np.r_[after_cell, after_env],
            np.r_[vc, ve],
        )
        amount = np.r_[raw["cell_amount_mol"], raw["environment_amount_mol"]]
        charge = np.r_[raw["cell_charge_C"], raw["environment_charge_C"]]
        ideal = [
            (_decimal(b) - _decimal(a)) * _decimal(v)
            for a, b, v in zip(before, after, volume, strict=True)
        ]
        net, net_charge = _sum(amount), _sum(charge)
        gross = sum((abs(_decimal(value)) for value in amount), Decimal(0))
        tolerance = _decimal(BALANCE_RELATIVE_TOLERANCE) * gross
        stock = sum(
            (
                (_decimal(math.ulp(float(a))) + _decimal(math.ulp(float(b)))) * _decimal(v) / 2
                for a, b, v in zip(before, after, volume, strict=True)
            ),
            Decimal(0),
        )
        projection = sum(
            (abs(_decimal(a) - b) for a, b in zip(amount, ideal, strict=True)), Decimal(0)
        )
        scale = abs(_decimal(baseline.valence) * _decimal(baseline.faraday_C_mol))
        charge_rounding = sum(
            (
                abs(
                    _decimal(q)
                    - _decimal(a) * _decimal(baseline.valence) * _decimal(baseline.faraday_C_mol)
                )
                for a, q in zip(amount, charge, strict=True)
            ),
            Decimal(0),
        )
        charge_bound = scale * (stock + projection) + charge_rounding
        strict = abs(net) <= tolerance and abs(net_charge) <= scale * tolerance
        valid = (
            abs(net) <= tolerance + stock + projection
            and abs(net_charge) <= scale * tolerance + charge_bound
        )
        rounding_only = (
            abs(net) <= tolerance + projection
            and abs(net_charge) <= scale * (tolerance + projection) + charge_rounding
        )
        diagnostics = dict(
            balance_residual_mol=float(net),
            balance_residual_C=float(net_charge),
            gross_change_mol=float(gross),
            conservation_tolerance_mol=_ceil_float(tolerance),
            conservation_tolerance_C=_ceil_float(scale * tolerance),
            stock_resolution_bound_mol=_ceil_float(stock),
            projection_roundoff_bound_mol=_ceil_float(projection),
            charge_roundoff_bound_C=_ceil_float(charge_bound),
            strict_conservation_valid=bool(strict),
            conservation_valid=bool(valid),
            storage_resolution_used=bool(valid and not rounding_only),
        )
    return ProteinDelta(
        baseline, current, **{key: _freeze(value) for key, value in arrays.items()}, **diagnostics
    )
