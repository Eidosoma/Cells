"""Native uniform-temperature setters with explicit physical owner association.

Kelvin is a prescribed isothermal parameter. Active catalog families retain
their fixed 298.15-K model contract; no thermal state or temperature law is added.
"""

import math
from dataclasses import dataclass, replace
from numbers import Real
from types import MappingProxyType
from typing import NamedTuple

import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import SimulationSpec, digest
from cells.core.surface_calcium_energy_spec import SurfaceCalciumEnergyHCNExtraModel
from cells.core.surface_calcium_spec import SurfaceCalciumHCNExtraModel
from cells.core.surface_kinetic_spec import SurfaceHCNExtraModel
from cells.core.surface_open_calcium_energy_spec import SurfaceOpenCalciumEnergyModel
from cells.core.surface_open_calcium_spec import SurfaceOpenCalciumModel
from cells.core.surface_tissue_spec import SurfaceTissueModel
from cells.models import physiology_permeability_view as immutable
from cells.processes import betse_global_controls as source

KIND = "cells.physiology_temperature_binding@1"
POLICY = "uniform_prescribed_kelvin_original_model_domain@1"
MODEL_TYPES = (
    SurfaceTissueModel,
    SurfaceHCNExtraModel,
    SurfaceCalciumHCNExtraModel,
    SurfaceCalciumEnergyHCNExtraModel,
    SurfaceOpenCalciumModel,
    SurfaceOpenCalciumEnergyModel,
)
OWNER_KINDS = (
    "cells",
    "environment",
    "membranes",
    "junctions",
    "faces",
    "channel_populations",
    "stores",
    "fuel_pools",
)


@dataclass(frozen=True, slots=True)
class Binding:
    source_definition_sha256: str
    program: source.Program
    owners: tuple
    provenance: str
    identity: str


class TemperatureState(NamedTuple):
    temperature_K: object


@dataclass(frozen=True, slots=True)
class PreparedTemperature:
    state: TemperatureState
    source_values: source.Values
    binding_identity: str
    event_time_s: float
    events_enabled: bool


class TemperatureRejected(NumericalError):
    def __init__(self, reason, trial):
        super().__init__(reason)
        self.trial = MappingProxyType(dict(trial))


def _spec(spec):
    if type(spec) is not SimulationSpec or type(spec.model) not in MODEL_TYPES:
        raise ValueError("Require an exact reviewed passive/ionic/calcium/fuel model identity")
    if type(spec.model) is not SurfaceTissueModel:
        if spec.model.temperature_K != 298.15:
            raise ValueError("Original active model must retain its declared 298.15-K contract")
        raw = spec.to_dict()["model"]
        if any(
            row["model"]["temperature_K"] != spec.model.temperature_K
            for row in raw.get("stores", [])
        ):
            raise ValueError("Original store and ionic temperature declarations must match")
    return spec


def actual_owners(spec):
    _spec(spec)
    raw = spec.to_dict()["model"]
    ion = raw.get("ionic", raw)
    return dict(
        cells=tuple(row["id"] for row in ion["cells"]),
        environment=tuple(row["id"] for row in ion["extracellular"]),
        membranes=tuple(row["id"] for row in ion["membranes"]),
        junctions=tuple(row["id"] for row in ion["junctions"]),
        faces=tuple(row["id"] for row in ion["faces"]),
        channel_populations=tuple(row["id"] for row in ion.get("channels", [])),
        stores=tuple(row["cell_id"] for row in raw.get("stores", [])),
        fuel_pools=tuple(row["id"] for row in raw.get("energy_pools", [])),
    )


def inventory(spec):
    """Machine-readable parameter roles, not a thermal evolution declaration."""
    owners = actual_owners(spec)
    active = type(spec.model) is not SurfaceTissueModel
    roles = [
        dict(
            fields=["temperature"],
            owners=["cells", "environment", "membranes", "junctions", "faces"],
            units="K",
            laws=[
                "GHK transport and affinity",
                "exterior electrodiffusion",
                "floating field root",
                "reservoir chemical potential and instantaneous power",
            ],
        ),
    ]
    if active:
        roles.extend(
            [
                dict(
                    fields=["pump_drive", "pump_delta_g0_J_mol"],
                    owners=["membranes"],
                    units="J/mol",
                    laws=["maintained ATP drive at held T", "original fixed-T work-history cache"],
                ),
                dict(
                    fields=["channel_laws", "channel_gate"],
                    owners=["channel_populations"],
                    units="declared source kinetics",
                    laws=[
                        "298.15-K channel composition contract",
                        "temperature-sensitive instantaneous calcium-K opening",
                        "no invented Q10",
                    ],
                ),
                dict(
                    fields=["junction_gate", "junction_threshold_voltage", "junction_minimum"],
                    owners=["junctions"],
                    units="declared voltage/second kinetics",
                    laws=["no declared junction-gate temperature scaling"],
                ),
            ]
        )
    if owners["stores"]:
        roles.extend(
            [
                dict(
                    fields=["er_temperature"],
                    owners=["stores"],
                    units="K",
                    laws=[
                        "ER electrochemical transport",
                        "pump drive and affinity",
                        "chemical powers",
                    ],
                ),
                dict(
                    fields=["er_standard_mu_RT", "er_delta_mu_RT", "er_forward_rate"],
                    owners=["stores"],
                    units="dimensionless, dimensionless, 1/s",
                    laws=["declared chemistry; no enthalpy or activation-energy law"],
                ),
                dict(
                    fields=["pmca_dg", "ncx_capacity"],
                    owners=["membranes"],
                    units="J/mol, fmol/s",
                    laws=["PMCA drive and Na/Ca exchange affinity use global held T"],
                ),
            ]
        )
    if owners["fuel_pools"]:
        roles.append(
            dict(
                fields=[
                    "energy_delta_g0_J_mol",
                    "energy_amount_increment_fmol",
                    "er_pump_dg0",
                    "pmca_dg",
                ],
                owners=["fuel_pools", "stores", "membranes"],
                units="J/mol, fmol, J/mol, J/mol",
                laws=[
                    "live pool chemical potentials and regeneration affinity",
                    "shared three-pump projection",
                    "1 M to numeric-mM standard conversion: delta_g0 - RT log(1000)",
                ],
            )
        )
    return dict(
        model_id=spec.to_dict()["model"]["id"],
        policy=POLICY,
        owners=owners,
        roles=roles,
        changed_temperature_supported=not active,
        active_family_temperature_K=298.15 if active else None,
        caloric_internal_energy_defined=False,
        heat_capacity_defined=False,
        thermal_transition_defined=False,
    )


def record(binding):
    if type(binding) is not Binding:
        raise ValueError("Require the complete typed temperature binding")
    payload = dict(
        kind=KIND,
        policy=POLICY,
        units=dict(temperature="K", native_amplitude="dimensionless"),
        source_definition_sha256=binding.source_definition_sha256,
        program=source.record(binding.program),
        owners=[[kind, list(ids)] for kind, ids in binding.owners],
        provenance=binding.provenance,
    )
    return payload | dict(identity=digest(payload))


def bind(spec, program, *, owners, provenance):
    actual = actual_owners(spec)
    source.validate(program)
    if program.membrane_ids != actual["membranes"]:
        raise ValueError("Native setter axes must match actual ordered membrane owners")
    if any(row.kind != "temperature" for row in program.events):
        raise ValueError("Temperature bindings require a temperature-only native setter program")
    if type(owners) is not dict or set(owners) != set(OWNER_KINDS):
        raise ValueError("Declare all physical temperature owner axes")
    rows = []
    for kind in OWNER_KINDS:
        values = owners[kind]
        if (
            not isinstance(values, (tuple, list))
            or any(type(name) is not str for name in values)
            or len(set(values)) != len(values)
            or set(values) != set(actual[kind])
        ):
            raise ValueError("Temperature owner association differs from actual " + kind)
        rows.append((kind, tuple(values)))
    if type(provenance) is not str or not provenance.strip():
        raise ValueError("Declare the physical uniform-thermostat association provenance")
    result = Binding(spec.fingerprint, program, tuple(rows), provenance, "")
    return replace(result, identity=record(result)["identity"])


def restore(saved, spec):
    if type(saved) is not dict or saved.get("kind") != KIND:
        raise ValueError("Require the complete saved temperature binding")
    try:
        program = source.restore(saved["program"], expected_identity=saved["program"]["identity"])
        rows = saved["owners"]
        if (
            type(rows) is not list
            or any(type(row) is not list or len(row) != 2 for row in rows)
            or len({row[0] for row in rows}) != len(rows)
        ):
            raise ValueError("Malformed or duplicated temperature owner axes")
        expected = bind(spec, program, owners=dict(rows), provenance=saved["provenance"])
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError("Malformed saved temperature binding") from error
    if record(expected) != saved:
        raise ValueError("Temperature binding differs from its original owners/units/source")
    return expected


def prepare(spec, binding, state, *, time_s, events_enabled):
    _spec(spec)
    if type(binding) is not Binding or binding.identity != record(binding)["identity"]:
        raise ValueError("Stale temperature binding")
    restore(record(binding), spec)
    if (
        not isinstance(time_s, Real)
        or isinstance(time_s, (bool, np.bool_))
        or not math.isfinite(time_s)
        or type(events_enabled) is not bool
    ):
        raise ValueError("Declare a finite source label and explicit enable flag")
    if type(state) is not TemperatureState:
        raise ValueError("Require the complete typed temperature memory")
    current = np.asarray(state.temperature_K)
    if (
        current.dtype != np.float64
        or current.shape != ()
        or not np.isfinite(current)
        or current <= 0
    ):
        raise ValueError("Temperature memory requires a finite positive float64 Kelvin scalar")
    original = source.State(
        current, np.ones(len(binding.program.membrane_ids)), np.asarray(1.0), np.zeros(4)
    )
    with np.errstate(over="ignore", under="ignore", invalid="ignore", divide="ignore"):
        values = source.apply(
            original,
            source.compile_program(binding.program),
            np.asarray(time_s, dtype=np.float64),
            np.asarray(spec.model.temperature_K),
            events_enabled,
            xp=np,
        )
    frozen = immutable._immutable_tree(values)
    trial = dict(
        source_values=frozen,
        binding_identity=binding.identity,
        original_temperature_K=spec.model.temperature_K,
        event_time_s=float(time_s),
    )
    if not values.physical_domain:
        raise TemperatureRejected(
            "Native setter proposed a nonphysical held Kelvin temperature", trial
        )
    if (
        type(spec.model) is not SurfaceTissueModel
        and values.state.temperature_K != spec.model.temperature_K
    ):
        raise TemperatureRejected(
            "Active catalog model requires unchanged 298.15 K; no declared temperature scaling",
            trial,
        )
    return PreparedTemperature(
        TemperatureState(frozen.state.temperature_K),
        frozen,
        binding.identity,
        float(time_s),
        events_enabled,
    )
