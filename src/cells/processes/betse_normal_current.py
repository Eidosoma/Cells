"""Pinned FULL-normal intracellular current prefix, independent of field solves.

Inputs are complete post-flux bulk concentrations, face fluxes and extra source
readouts. Current smoothing is literal, including its geometry dependence. No
concentration update, initializer, ECM/BVP, voltage or conservation law is added.
"""

import hashlib
import json
import math
import struct
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import NamedTuple

import numpy as np

from cells.core.errors import NumericalError

LAW_ID = "betse_normal_intracellular_current_v1_5_0@1"
SOURCE_REVISION = "5269a714aa2593ed2a6708c4516289977d8ae1a2"
INPUT_KIND = "cells.betse_normal_current_inputs@1"


def _freeze(value):
    if isinstance(value, np.ndarray):
        return np.frombuffer(value.tobytes(), dtype=value.dtype).reshape(value.shape)
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    return value


def record(value):
    if isinstance(value, np.ndarray):
        return dict(
            dtype=value.dtype.str,
            shape=list(value.shape),
            sha256=hashlib.sha256(value.tobytes()).hexdigest(),
        )
    if isinstance(value, (dict, MappingProxyType)):
        return {key: record(item) for key, item in value.items()}
    if hasattr(value, "_asdict"):
        return {key: record(item) for key, item in value._asdict().items()}
    if isinstance(value, (tuple, list)):
        return [record(item) for item in value]
    if type(value) is float:
        return dict(float64_bits=struct.pack("<d", value).hex())
    return value


def _digest(value):
    return hashlib.sha256(
        json.dumps(record(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _ids(values, maximum):
    if (
        not isinstance(values, (tuple, list))
        or not 1 <= len(values) <= maximum
        or any(type(v) is not str or not v for v in values)
        or len(set(values)) != len(values)
    ):
        raise ValueError("Require bounded, named, unique source owner axes")
    return tuple(values)


def _array(values, shape, name, *, positive=False, nonnegative=False):
    if np.asarray(values).dtype.kind not in "iuf":
        raise ValueError("Require numeric source arrays: " + name)
    a = np.asarray(values, np.float64)
    if (
        a.shape != shape
        or not np.isfinite(a).all()
        or positive
        and np.any(a <= 0)
        or nonnegative
        and np.any(a < 0)
    ):
        raise ValueError("Incomplete/nonfinite source array or domain: " + name)
    return _freeze(a)


class CurrentKernel(NamedTuple):
    valence: object
    F_C_mol: float
    owner: object
    owner_sum: object
    membrane_area_m2: object
    cell_area_m2: object
    normal_xy: object
    source_smooth_cells: float
    membrane_weight: object
    other_weight: object
    source_area_ratio: object


@dataclass(frozen=True, slots=True)
class CurrentBinding:
    cell_ids: tuple
    membrane_ids: tuple
    ion_ids: tuple
    sharpness_cell: float
    provenance: str
    kernel: CurrentKernel
    identity: str


class CurrentInputs(NamedTuple):
    cell_mol_m3: object
    membrane_flux_mol_m2_s: object
    junction_flux_mol_m2_s: object
    extra_charge_C_m3: object
    extra_current_A_m2: object


class CurrentValues(NamedTuple):
    charge_density_C_m3: object
    membrane_current_A_m2: object
    junction_current_A_m2: object
    raw_normal_current_A_m2: object
    average_normal_current_A_m2: object
    normal_current_A_m2: object
    inward_membrane_current_A: object
    cell_current_xy_A_m2: object
    projected_cell_current_A_m2: object


@dataclass(frozen=True, slots=True)
class CurrentReadout:
    binding_identity: str
    source_identity: str
    source: CurrentInputs
    values: CurrentValues
    diagnostics: object
    identity: str


class NormalCurrentRejected(NumericalError):
    def __init__(self, reason, *, stage, source=None, trial=None):
        super().__init__("Native normal current refused at " + stage + ": " + str(reason))
        self.stage, self.source, self.trial = stage, source, trial


def binding_record(binding):
    return dict(
        law=LAW_ID,
        native_revision=SOURCE_REVISION,
        cell_ids=binding.cell_ids,
        membrane_ids=binding.membrane_ids,
        ion_ids=binding.ion_ids,
        sharpness_cell=binding.sharpness_cell,
        provenance=binding.provenance,
        kernel=binding.kernel,
    )


def bind(raw):
    """Prepare literal source sharpness/owner weights; preserve invalid weights."""
    if (
        type(raw) is not dict
        or set(raw) != {"kind", "provenance", "geometry", "ions", "parameters"}
        or raw["kind"] != INPUT_KIND
    ):
        raise ValueError("Require the separate complete normal-current definition")
    if type(raw["provenance"]) is not str or not raw["provenance"].strip():
        raise ValueError("Declare source provenance")
    g, z, p = raw["geometry"], raw["ions"], raw["parameters"]
    if (
        set(g)
        != {"cell_ids", "membrane_ids", "owner", "membrane_area_m2", "cell_area_m2", "normal_xy"}
        or set(z) != {"ids", "valence"}
        or set(p) != {"F_C_mol", "sharpness_cell"}
    ):
        raise ValueError("Incomplete/extended source owner, ion or parameter fields")
    cells, membranes, ions = (
        _ids(g["cell_ids"], 256),
        _ids(g["membrane_ids"], 1536),
        _ids(z["ids"], 32),
    )
    n, m, i = len(cells), len(membranes), len(ions)
    owners = np.asarray(g["owner"])
    if (
        owners.shape != (m,)
        or owners.dtype.kind not in "iu"
        or np.any(owners < 0)
        or np.any(owners >= n)
        or set(owners.tolist()) != set(range(n))
    ):
        raise ValueError("Require exactly one original owner per face and nonempty cells")
    owners = _freeze(owners.astype(np.int64))
    area = _array(g["membrane_area_m2"], (m,), "membrane area", positive=True)
    surface = _array(g["cell_area_m2"], (n,), "cell area", positive=True)
    normal = _array(g["normal_xy"], (m, 2), "membrane normals")
    if np.any(abs(np.sum(normal**2, axis=1) - 1) > 3e-14):
        raise ValueError("Require source unit normal vectors")
    valence = _array(z["valence"], (i,), "ion valence")
    if np.any(valence != np.trunc(valence)):
        raise ValueError("Require declared integer ion valences, including neutral rows")
    numbers = {}
    for key in ("F_C_mol", "sharpness_cell"):
        if (
            isinstance(p[key], (bool, np.bool_))
            or not isinstance(p[key], (int, float, np.floating))
            or not math.isfinite(p[key])
            or p[key] <= 0
        ):
            raise ValueError("Require finite positive source parameter: " + key)
        numbers[key] = float(p[key])
    owner_sum = np.asarray(owners[None, :] == np.arange(n)[:, None], np.float64)
    counts = np.bincount(owners, minlength=n)
    with np.errstate(all="ignore"):
        scale = 1 / float(numbers["sharpness_cell"])
        denominator = scale * counts[owners]
        membrane = (denominator - 1) / denominator
        other = 1 / denominator
        ratio = (owner_sum @ area) / surface
    weights = dict(
        source_smooth_cells=scale,
        membrane_weight=membrane,
        other_weight=other,
        source_area_ratio=ratio,
    )
    if not math.isfinite(scale) or not all(np.isfinite(v).all() for v in (membrane, other, ratio)):
        raise NormalCurrentRejected(
            "Undefined literal smoothing initialization",
            stage="smoothing",
            source=raw,
            trial=_freeze(weights),
        )
    kernel = CurrentKernel(
        valence,
        numbers["F_C_mol"],
        owners,
        _freeze(owner_sum),
        area,
        surface,
        normal,
        scale,
        _freeze(membrane),
        _freeze(other),
        _freeze(ratio),
    )
    result = CurrentBinding(
        cells, membranes, ions, numbers["sharpness_cell"], raw["provenance"], kernel, ""
    )
    return replace(result, identity=_digest(binding_record(result)))


def inputs(
    binding,
    cell_mol_m3,
    membrane_flux_mol_m2_s,
    junction_flux_mol_m2_s,
    extra_charge_C_m3,
    extra_current_A_m2,
):
    n, m, i = len(binding.cell_ids), len(binding.membrane_ids), len(binding.ion_ids)
    return CurrentInputs(
        _array(cell_mol_m3, (i, n), "bulk concentration", nonnegative=True),
        _array(membrane_flux_mol_m2_s, (i, m), "membrane flux"),
        _array(junction_flux_mol_m2_s, (i, m), "junction flux"),
        _array(extra_charge_C_m3, (n,), "extra charge density"),
        _array(extra_current_A_m2, (m,), "extra current density"),
    )


def evaluate(binding, source):
    """Literal post-flux source readout; never change concentrations or fluxes."""
    trial = None
    try:
        if type(binding) is not CurrentBinding or binding.identity != _digest(
            binding_record(binding)
        ):
            raise ValueError("Changed source current/owner association")
        k = binding.kernel
        fresh = bind(
            dict(
                kind=INPUT_KIND,
                provenance=binding.provenance,
                geometry=dict(
                    cell_ids=binding.cell_ids,
                    membrane_ids=binding.membrane_ids,
                    owner=k.owner,
                    membrane_area_m2=k.membrane_area_m2,
                    cell_area_m2=k.cell_area_m2,
                    normal_xy=k.normal_xy,
                ),
                ions=dict(ids=binding.ion_ids, valence=k.valence),
                parameters=dict(F_C_mol=k.F_C_mol, sharpness_cell=binding.sharpness_cell),
            )
        )
        if record(binding_record(fresh)) != record(binding_record(binding)):
            raise ValueError(
                "Prepared current weights/operators differ from their original source inputs"
            )
        if type(source) is not CurrentInputs:
            raise ValueError("Require complete typed current inputs")
        original = source
        checked = inputs(binding, *source)
        if record(checked) != record(original):
            raise ValueError("Input dtype/shape differs from complete float64 source buffers")
        if any(value.flags.writeable for value in source):
            raise ValueError("Source buffers must be immutable")
        with np.errstate(all="ignore"):
            rho = np.dot(k.valence * k.F_C_mol, source.cell_mol_m3) + source.extra_charge_C_m3
            jmem = (
                -np.dot(k.valence * k.F_C_mol, source.membrane_flux_mol_m2_s)
                + source.extra_current_A_m2
            )
            jgj = np.dot(k.valence * k.F_C_mol, source.junction_flux_mol_m2_s)
            raw = jmem + jgj
            average = np.dot(k.owner_sum, raw * k.membrane_area_m2) / k.cell_area_m2
            normal = k.membrane_weight * raw + average[k.owner] * k.other_weight
            inward = -normal * k.membrane_area_m2
            vector = np.column_stack(
                tuple(
                    np.dot(k.owner_sum, normal * k.normal_xy[:, axis] * k.membrane_area_m2)
                    / k.cell_area_m2
                    for axis in (0, 1)
                )
            )
            projected = (
                vector[k.owner, 0] * k.normal_xy[:, 0] + vector[k.owner, 1] * k.normal_xy[:, 1]
            )
            surface_before = k.owner_sum @ (raw * k.membrane_area_m2)
            surface_after = k.owner_sum @ (normal * k.membrane_area_m2)
            rho_gross = np.dot(abs(k.valence * k.F_C_mol), abs(source.cell_mol_m3)) + abs(
                source.extra_charge_C_m3
            )
            mem_gross = np.dot(
                abs(k.valence * k.F_C_mol), abs(source.membrane_flux_mol_m2_s)
            ) + abs(source.extra_current_A_m2)
            gap_gross = np.dot(abs(k.valence * k.F_C_mol), abs(source.junction_flux_mol_m2_s))
        values = CurrentValues(
            *(_freeze(v) for v in (rho, jmem, jgj, raw, average, normal, inward, vector, projected))
        )
        diagnostics = _freeze(
            dict(
                finite=bool(all(np.isfinite(v).all() for v in values)),
                smoothing_weights_convex=bool(
                    np.all((k.membrane_weight >= 0) & (k.membrane_weight <= 1))
                    and np.all((k.other_weight >= 0) & (k.other_weight <= 1))
                ),
                sharpness_in_documented_range=binding.sharpness_cell <= 1,
                source_area_ratio=k.source_area_ratio,
                surface_current_before_A=surface_before,
                surface_current_after_A=surface_after,
                smoothing_current_difference_A=surface_after - surface_before,
                charge_gross_C_m3=rho_gross,
                membrane_current_gross_A_m2=mem_gross,
                junction_current_gross_A_m2=gap_gross,
                field_or_voltage_computed=False,
                physical_charge_conservation_inferred=False,
            )
        )
        sid = _digest(source)
        trial = CurrentReadout(binding.identity, sid, source, values, diagnostics, "")
        trial = replace(
            trial,
            identity=_digest(
                dict(binding=binding.identity, source=sid, values=values, diagnostics=diagnostics)
            ),
        )
        if not diagnostics["finite"]:
            raise ValueError("Nonfinite literal native current trial")
        return trial
    except Exception as error:
        raise NormalCurrentRejected(
            error,
            stage="current_trial" if trial is not None else "source",
            source=source,
            trial=trial,
        ) from error
