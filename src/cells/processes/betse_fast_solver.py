"""Literal pinned fast-circuit arithmetic, separate from conservative tissue.

Prepared concentrations/conductances stay fixed. Initial voltage and explicit
post-hook current packets belong to the caller. No ion/pump/noise, extracellular
voltage, thermal work, network callback or physical field parity is implied.
"""

import hashlib
import json
import math
import struct
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import NamedTuple

import numpy as np

from cells.core import physiology_native_calendar as clocks
from cells.core.errors import NumericalError

LAW_ID = "betse_fast_equivalent_circuit_v1_5_0@1"
SOURCE_REVISION = "5269a714aa2593ed2a6708c4516289977d8ae1a2"
INPUT_KIND = "cells.betse_fast_solver_inputs@1"
ION_NAMES = frozenset(("Na", "K", "Cl", "Ca", "M", "H", "P"))
GEOMETRY_FIELDS = frozenset(
    (
        "cell_ids",
        "membrane_ids",
        "owner",
        "neighbor",
        "membrane_area_m2",
        "cell_area_m2",
        "cell_volume_m3",
        "normal_xy",
        "environment_index",
        "junction_weights",
    )
)
ION_FIELDS = frozenset(
    (
        "ids",
        "valence",
        "cell_mol_m3",
        "environment_mol_m3",
        "free_diffusion_m2_s",
        "membrane_diffusion_m2_s",
    )
)
PARAMETER_FIELDS = frozenset(
    (
        "R_J_mol_K",
        "F_C_mol",
        "q_C",
        "kb_J_K",
        "configured_temperature_K",
        "temperature_K",
        "capacitance_F_m2",
        "membrane_thickness_m",
        "gap_length_m",
        "junction_surface_fraction",
        "is_ecm",
    )
)


def _freeze(value):
    if isinstance(value, np.ndarray):
        return np.frombuffer(value.tobytes(), dtype=value.dtype).reshape(value.shape)
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    return value


def _record(value):
    if isinstance(value, np.ndarray):
        return dict(
            dtype=value.dtype.str,
            shape=list(value.shape),
            sha256=hashlib.sha256(value.tobytes()).hexdigest(),
        )
    if isinstance(value, (dict, MappingProxyType)):
        return {key: _record(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_record(item) for item in value]
    if type(value) is float:
        return dict(float64_bits=struct.pack("<d", value).hex())
    return value


def _digest(value):
    return hashlib.sha256(
        json.dumps(_record(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _array(value, shape, name, *, positive=False, fraction=False):
    if np.asarray(value).dtype.kind not in "iuf":
        raise ValueError("Require explicit numeric source values: " + name)
    array = np.asarray(value, np.float64)
    if array.shape != shape or not np.isfinite(array).all():
        raise ValueError("Require complete finite source array: " + name)
    if positive and np.any(array <= 0) or fraction and np.any((array < 0) | (array > 1)):
        raise ValueError("Source domain violation: " + name)
    return _freeze(array)


def _indices(value, count, maximum, name):
    a = np.asarray(value)
    if a.shape != (count,) or a.dtype.kind not in "iu" or np.any(a < 0) or np.any(a >= maximum):
        raise ValueError("Require explicit integer source owners: " + name)
    return _freeze(a.astype(np.int64))


def _ids(value, maximum):
    if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= maximum:
        raise ValueError("Require a bounded original source owner axis")
    if any(type(item) is not str or not item for item in value) or len(set(value)) != len(value):
        raise ValueError("Require unique named source owners")
    return tuple(value)


class Coefficients(NamedTuple):
    leak_reversal_V: object
    leak_conductance_S_m2: object
    junction_conductance_S_m2: object
    init_dynamics_sigma_S_m: object
    sigma_cell_S_m: object
    membrane_conductivity_S_m2: object
    ion_reversal_V: object
    ion_mean_mol_m3: object
    cbar_all_mol_m3: object
    cbar_sum_mol_m3: object
    checks: object
    valid: bool


@dataclass(frozen=True, slots=True)
class FastModel:
    definition: object
    calendar: object
    coefficients: Coefficients
    identity: str


class Drive(NamedTuple):
    extra_current_A_m2: object
    junction_block: object


@dataclass(frozen=True, slots=True)
class FastCheckpoint:
    model_identity: str
    cell_voltage_V: object
    membrane_voltage_V: object
    drive: Drive
    call_index: int
    elapsed_s: float
    parent_identity: str | None
    identity: str


class CircuitValues(NamedTuple):
    cell_voltage_V: object
    membrane_voltage_V: object
    old_gap_voltage_V: object
    junction_open: object
    normal_current_A_m2: object
    cell_current_xy_A_m2: object
    cell_field_xy_V_m: object
    membrane_field_xy_V_m: object
    corrected_divergence_V_m2: object
    monotone_dt_limit_s: object
    monotone_step: object
    native_voltage_nan_gate: object
    finite: object


@dataclass(frozen=True, slots=True)
class FastTrial:
    source_identity: str
    drive: Drive
    values: CircuitValues
    event_label_s: float
    start_s: float
    end_s: float
    identity: str


@dataclass(frozen=True, slots=True)
class FastReceipt:
    checkpoint: FastCheckpoint
    trial: FastTrial


class FastRejected(NumericalError):
    def __init__(self, reason, *, stage, source=None, trial=None, coefficients=None):
        super().__init__("Fast circuit refused at " + stage + ": " + str(reason))
        self.stage, self.source, self.trial, self.coefficients = stage, source, trial, coefficients


def _definition(raw):
    if type(raw) is not dict or set(raw) != {
        "kind",
        "provenance",
        "geometry",
        "ions",
        "parameters",
    }:
        raise ValueError("Require the complete separate fast-circuit definition")
    if (
        raw["kind"] != INPUT_KIND
        or type(raw["provenance"]) is not str
        or not raw["provenance"].strip()
    ):
        raise ValueError("Require the exact fast law and declared source provenance")
    g, ions, p = raw["geometry"], raw["ions"], raw["parameters"]
    if set(g) != GEOMETRY_FIELDS or set(ions) != ION_FIELDS or set(p) != PARAMETER_FIELDS:
        raise ValueError("Incomplete/extended geometry, ion or constant fields")
    cells, membranes = _ids(g["cell_ids"], 256), _ids(g["membrane_ids"], 1536)
    names = _ids(ions["ids"], 7)
    if not set(names) <= ION_NAMES:
        raise ValueError("Ion names must match source get_ion dispatch")
    n, m, count = len(cells), len(membranes), len(names)
    environment = np.asarray(ions["environment_mol_m3"])
    if (
        environment.ndim != 2
        or environment.shape[0] != count
        or not 1 <= environment.shape[1] <= 1024
    ):
        raise ValueError("Require the original bounded environment axis")
    ne = environment.shape[1]
    owner = _indices(g["owner"], m, n, "membrane owner")
    if set(owner.tolist()) != set(range(n)):
        raise ValueError("Every native cell requires a nonempty membrane row")
    geometry = dict(
        cell_ids=cells,
        membrane_ids=membranes,
        owner=owner,
        neighbor=_indices(g["neighbor"], m, n, "neighbor"),
        environment_index=_indices(g["environment_index"], m, ne, "environment"),
    )
    for key, shape in (
        ("membrane_area_m2", (m,)),
        ("cell_area_m2", (n,)),
        ("cell_volume_m3", (n,)),
    ):
        geometry[key] = _array(g[key], shape, key, positive=True)
    normals = _array(g["normal_xy"], (m, 2), "normal_xy")
    if np.any(abs(np.sum(normals**2, axis=1) - 1) > 3e-14):
        raise ValueError("The literal projection requires source unit membrane normals")
    geometry["normal_xy"] = normals
    geometry["junction_weights"] = _array(
        g["junction_weights"], (m,), "junction_weights", fraction=True
    )
    parameters = {}
    for key in PARAMETER_FIELDS - {"is_ecm"}:
        value = p[key]
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, (float, int, np.floating)):
            raise ValueError("Require explicit real SI parameters: " + key)
        value = float(value)
        if not math.isfinite(value) or (
            value < 0 if key == "junction_surface_fraction" else value <= 0
        ):
            raise ValueError("Invalid source parameter: " + key)
        parameters[key] = value
    if type(p["is_ecm"]) is not bool:
        raise ValueError("Declare the source environment mode")
    parameters["is_ecm"] = p["is_ecm"]
    if not p["is_ecm"] and (
        ne != m or not np.array_equal(geometry["environment_index"], np.arange(m))
    ):
        raise ValueError("No-ECM source concentrations are membrane indexed")
    valence = _array(ions["valence"], (count,), "valence")
    if np.any(valence == 0) or np.any(valence != np.trunc(valence)):
        raise ValueError("Declare nonzero integer source ion valences")
    values = dict(
        ids=names,
        valence=valence,
        cell_mol_m3=_array(ions["cell_mol_m3"], (count, n), "cell concentration", positive=True),
        environment_mol_m3=_array(
            environment, (count, ne), "environment concentration", positive=True
        ),
        free_diffusion_m2_s=_array(ions["free_diffusion_m2_s"], (count,), "free D"),
        membrane_diffusion_m2_s=_array(ions["membrane_diffusion_m2_s"], (count, m), "membrane D"),
    )
    if np.any(values["free_diffusion_m2_s"] < 0) or np.any(values["membrane_diffusion_m2_s"] < 0):
        raise ValueError("Diffusion coefficients must be nonnegative")
    return _freeze(
        dict(
            kind=INPUT_KIND,
            provenance=raw["provenance"],
            geometry=geometry,
            ions=values,
            parameters=parameters,
        )
    )


def _operators(definition):
    g = definition["geometry"]
    matrix = np.asarray(g["owner"][None, :] == np.arange(len(g["cell_ids"]))[:, None], np.float64)
    return matrix, matrix.sum(axis=1)


def prepare_coefficients(definition):
    """Literal source coefficients; preserve undefined numerical trials."""
    g, ions, p = (definition[name] for name in ("geometry", "ions", "parameters"))
    matrix, counts = _operators(definition)
    ci, co, dm, df, z = (
        ions[key]
        for key in (
            "cell_mol_m3",
            "environment_mol_m3",
            "membrane_diffusion_m2_s",
            "free_diffusion_m2_s",
            "valence",
        )
    )
    reversals, cbar, sg, sm = {}, {}, [], []
    an_in, an_out, cat_in, cat_out = [], [], [], []
    with np.errstate(all="ignore"):
        for i, name in enumerate(ions["ids"]):
            inside = ci[i].mean()
            outside = co[i].mean() if p["is_ecm"] else co[i]
            cbar[name] = np.asarray((inside + outside) / 2)
            reversals[name] = np.asarray(
                p["R_J_mol_K"]
                * p["temperature_K"]
                / (z[i] * p["F_C_mol"])
                * np.log(outside / inside)
            )
            sg.append(
                df[i]
                * p["q_C"]
                * p["junction_surface_fraction"]
                * p["F_C_mol"]
                * inside
                * z[i] ** 2
                / (p["gap_length_m"] * p["kb_J_K"] * p["configured_temperature_K"])
            )
            sm.append(
                dm[i]
                * p["q_C"]
                * p["F_C_mol"]
                * cbar[name]
                * z[i] ** 2
                / (p["membrane_thickness_m"] * p["kb_J_K"] * p["configured_temperature_K"])
            )
            dbar = matrix @ dm[i] / counts
            exterior = co[i][g["environment_index"]] if p["is_ecm"] else co[i]
            outside_at_cell = matrix @ exterior / counts
            first, last = (an_in, an_out) if z[i] < 0 else (cat_in, cat_out)
            first.append(dbar * ci[i] / p["membrane_thickness_m"])
            last.append(dbar * outside_at_cell / p["membrane_thickness_m"])
        leak = (
            p["R_J_mol_K"]
            * p["temperature_K"]
            / p["F_C_mol"]
            * np.log(
                (np.sum(cat_out, axis=0) + np.sum(an_in, axis=0))
                / (np.sum(cat_in, axis=0) + np.sum(an_out, axis=0))
            )
        )
        conductance = matrix @ (sum(sm) * g["membrane_area_m2"]) / g["cell_area_m2"]
        gj = sum(sg) / counts
        sigma_init = np.asarray(
            [
                zz**2
                * p["q_C"]
                * p["F_C_mol"]
                * c
                * d
                * 0.1
                / (p["kb_J_K"] * p["configured_temperature_K"])
                for zz, c, d in zip(z, ci, df, strict=True)
            ]
        ).sum(axis=0)
        sigma = np.asarray(
            [
                zz**2
                * p["F_C_mol"] ** 2
                * c
                * d
                * 0.1
                / (p["R_J_mol_K"] * p["configured_temperature_K"])
                for zz, c, d in zip(z, ci, df, strict=True)
            ]
        ).mean(axis=0)
        mean = np.asarray(np.mean(list(cbar.values())))
        total = np.asarray(np.sum([value.mean() for value in cbar.values()]))
    numeric = (
        leak,
        conductance,
        gj,
        sigma_init,
        sigma,
        np.asarray(sm),
        mean,
        total,
        *reversals.values(),
        *cbar.values(),
    )
    checks = dict(
        finite=all(np.isfinite(value).all() for value in numeric),
        nonnegative_conductance=bool(np.all(conductance >= 0) and np.all(gj >= 0)),
        positive_readout_conductivity=bool(np.all(sigma > 0)),
    )
    return Coefficients(
        *(_freeze(np.asarray(value)) for value in numeric[:6]),
        _freeze(reversals),
        _freeze(cbar),
        _freeze(mean),
        _freeze(total),
        MappingProxyType(checks),
        all(checks.values()),
    )


def model_record(model):
    return dict(
        law=LAW_ID,
        native_revision=SOURCE_REVISION,
        definition=_record(model.definition),
        calendar=clocks.record(model.calendar),
        coefficients=_record(model.coefficients),
    )


def bind(definition, calendar):
    """Caller supplies static source concentrations/geometry; no initializer graft."""
    raw = _definition(definition)
    calendar = clocks.validate(calendar)
    coefficients = prepare_coefficients(raw)
    if not coefficients.valid:
        raise FastRejected(
            "Undefined source coefficients/readouts",
            stage="coefficients",
            source=raw,
            coefficients=coefficients,
        )
    model = FastModel(raw, calendar, coefficients, "")
    return replace(model, identity=_digest(model_record(model)))


def drive(model, extra_current_A_m2, junction_block):
    size = len(model.definition["geometry"]["membrane_ids"])
    block = np.asarray(junction_block, np.float64)
    if block.shape == ():
        block = np.full(size, block)
    return Drive(
        _array(extra_current_A_m2, (size,), "external current"),
        _array(block, (size,), "junction block", fraction=True),
    )


def checkpoint_record(point):
    return dict(
        model_identity=point.model_identity,
        cell_voltage_V=point.cell_voltage_V,
        membrane_voltage_V=point.membrane_voltage_V,
        drive=point.drive,
        call_index=point.call_index,
        elapsed_s=point.elapsed_s,
        parent_identity=point.parent_identity,
    )


def _seal(point):
    return replace(point, identity=_digest(checkpoint_record(point)))


def initialise(model, cell_voltage_V, initial_drive):
    if (
        type(model) is not FastModel
        or model.identity != _digest(model_record(model))
        or not model.coefficients.valid
    ):
        raise ValueError("Require the complete admitted fast-circuit model")
    n = len(model.definition["geometry"]["cell_ids"])
    voltage = _array(cell_voltage_V, (n,), "caller initial voltage")
    packet = drive(model, *initial_drive)
    return _seal(
        FastCheckpoint(
            model.identity,
            voltage,
            _freeze(voltage[model.definition["geometry"]["owner"]]),
            packet,
            0,
            0.0,
            None,
            "",
        )
    )


def validate(model, point):
    if type(model) is not FastModel or model.identity != _digest(model_record(model)):
        raise ValueError("Changed source circuit/calibration association")
    clocks.validate(model.calendar)
    if not model.coefficients.valid or _record(model.coefficients) != _record(
        prepare_coefficients(model.definition)
    ):
        raise ValueError("Prepared conductances differ from their original fixed source inputs")
    if type(point) is not FastCheckpoint or point.identity != _digest(checkpoint_record(point)):
        raise ValueError("Changed complete circuit checkpoint")
    if (
        point.model_identity != model.identity
        or type(point.call_index) is not int
        or not 0 <= point.call_index <= model.calendar.step_count
        or point.elapsed_s != point.call_index * model.calendar.dt_s
    ):
        raise ValueError("Circuit state differs from its original phase cursor")
    g = model.definition["geometry"]
    if any(
        type(value) is not np.ndarray or value.dtype != np.float64 or value.flags.writeable
        for value in (point.cell_voltage_V, point.membrane_voltage_V, *point.drive)
    ):
        raise ValueError("Accepted circuit buffers must retain immutable complete float64 arrays")
    voltage = _array(point.cell_voltage_V, (len(g["cell_ids"]),), "accepted voltage")
    if not np.array_equal(point.membrane_voltage_V, voltage[g["owner"]]):
        raise ValueError("Membrane voltage differs from the actual source owner map")
    drive(model, *point.drive)


def _values(model, point, packet):
    d, c = model.definition, model.coefficients
    g, p = d["geometry"], d["parameters"]
    matrix, counts = _operators(d)
    owner, neighbor = g["owner"], g["neighbor"]
    area, surface, volume = (
        g[key] for key in ("membrane_area_m2", "cell_area_m2", "cell_volume_m3")
    )
    cm, sigma = p["capacitance_F_m2"], c.sigma_cell_S_m
    with np.errstate(all="ignore"):
        vgj = point.cell_voltage_V[neighbor] - point.cell_voltage_V[owner]
        jgap = c.junction_conductance_S_m2 * (matrix @ vgj)
        jmem = matrix @ (packet.extra_current_A_m2 * area) / surface
        voltage = point.cell_voltage_V + model.calendar.dt_s * (1 / cm) * (
            jgap - jmem - c.leak_conductance_S_m2 * (point.cell_voltage_V - c.leak_reversal_V)
        )
        current = -vgj * c.junction_conductance_S_m2[owner] + packet.extra_current_A_m2
        unprojected = current[:, None] * g["normal_xy"] / (0.1 * sigma.mean())
        div = matrix @ (np.sum(unprojected * g["normal_xy"], axis=1) * area) / volume
        pressure = div[owner] / counts[owner] * volume[owner] / area
        field_mem = unprojected - pressure[:, None] * g["normal_xy"]
        field_div = matrix @ (np.sum(field_mem * g["normal_xy"], axis=1) * area) / volume
        cell_current = (matrix @ (current[:, None] * g["normal_xy"] * area[:, None])) / surface[
            :, None
        ]
        cell_field = cell_current / (0.1 * sigma[:, None])
        rate = c.leak_conductance_S_m2 + c.junction_conductance_S_m2 * (
            matrix @ (neighbor != owner)
        )
        bound = np.divide(cm, rate, out=np.full_like(rate, np.inf), where=rate > 0)
    numeric = (
        voltage,
        voltage[owner],
        vgj,
        packet.junction_block * g["junction_weights"],
        current,
        cell_current,
        cell_field,
        field_mem,
        field_div,
    )
    finite = all(np.isfinite(value).all() for value in numeric)
    return CircuitValues(
        *(_freeze(value) for value in numeric),
        _freeze(bound),
        _freeze(np.asarray(model.calendar.dt_s <= bound)),
        _freeze(np.asarray(not np.isnan(voltage).any())),
        _freeze(np.asarray(finite)),
    )


def advance(model, point, packet=None):
    """One literal Euler call; finite guard is stricter than source's NaN test."""
    trial = None
    try:
        validate(model, point)
        label = clocks.event_label_s(model.calendar, point.call_index)
        if packet is not None and model.calendar.phase != "SIM":
            raise ValueError("INIT keeps its original carried current/block packet")
        packet = point.drive if packet is None else drive(model, *packet)
        values = _values(model, point, packet)
        end = (point.call_index + 1) * model.calendar.dt_s
        trial = FastTrial(point.identity, packet, values, label, point.elapsed_s, end, "")
        trial = replace(
            trial,
            identity=_digest(
                dict(
                    source=point.identity,
                    drive=packet,
                    values=values,
                    event_label_s=label,
                    start_s=point.elapsed_s,
                    end_s=end,
                )
            ),
        )
        if not values.native_voltage_nan_gate or not values.finite:
            raise ValueError("Undefined/nonfinite literal source circuit trial")
        candidate = _seal(
            FastCheckpoint(
                model.identity,
                values.cell_voltage_V,
                values.membrane_voltage_V,
                packet,
                point.call_index + 1,
                end,
                point.identity,
                "",
            )
        )
        validate(model, candidate)
        return FastReceipt(candidate, trial)
    except Exception as error:
        raise FastRejected(
            error,
            stage="circuit_trial" if trial is not None else "source_or_clock",
            source=point,
            trial=trial,
        ) from error
