"""Explicit finite mitochondrial owners in the 56-law calcium/fuel/transport model."""

from bisect import bisect_right
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from typing import NamedTuple

import numpy as np

from cells.core import surface_calcium_energy_transport_spec as prior
from cells.core.bioelectric_spec import positive, signed_number
from cells.core.multispecies_spec import aligned, identifier
from cells.core.specs import ChannelChange, ConfigError, _fields, _number
from cells.core.surface_energy_spec import _project
from cells.core.voltage_gated_spec import fraction
from cells.processes import mitochondrial_passive as process
from cells.processes.electrochemistry import F, R

MODEL_ID = "resolved_calcium_energy_mitochondria@1"
INITIALIZATION = "explicit_disjoint_inventory@1"
VOLTAGE = "charge_consistent_mito_minus_cytosol@1"
VOLUME_ROLE = "solvent_volume_excludes_er_and_mitochondria@1"


@dataclass(frozen=True)
class Mitochondrion:
    id: str
    cell_id: str
    volume_pL: float
    area_m2: float
    specific_capacitance_F_per_m2: float
    membrane_thickness_m: float
    initial_voltage_V: float
    initial_amount_fmol: tuple[float, ...]
    diffusivity_m2_per_s: tuple[float, ...]


@dataclass(frozen=True)
class SurfaceCalciumEnergyMitochondriaModel(prior.SurfaceCalciumEnergyTransportModel):
    mitochondria: tuple[Mitochondrion, ...]


@dataclass(frozen=True)
class Execution(prior.Execution):
    pass


Control = NamedTuple(
    "SurfaceCalciumEnergyMitochondriaControl",
    [(k, object) for k in (*prior.Control._fields, "mitochondria")],
)


@dataclass(frozen=True)
class Change(prior.Change):
    mitochondria: tuple[float, ...]


@dataclass(frozen=True)
class Experiment(prior.Experiment):
    mitochondrial_controls: tuple[tuple[ChannelChange, ...], ...]

    @property
    def changes(self):
        groups = (super().changes, *self.mitochondrial_controls)
        clocks = [[c.time for c in group] for group in groups]
        return tuple(
            Change(
                **(vars(groups[0][bisect_right(clocks[0], time) - 1]) | dict(time=time)),
                mitochondria=tuple(
                    group[bisect_right(clock, time) - 1].availability
                    for group, clock in zip(groups[1:], clocks[1:], strict=True)
                ),
            )
            for time in sorted({time for clock in clocks for time in clock})
        )


def base_spec(spec):
    return replace(
        spec,
        model=_project(spec.model, prior.SurfaceCalciumEnergyTransportModel),
        experiment=_project(spec.experiment, prior.Experiment),
        execution=_project(spec.execution, prior.Execution),
    )


def to_dict(spec):
    if (
        type(spec.model) is not SurfaceCalciumEnergyMitochondriaModel
        or type(spec.experiment) is not Experiment
        or type(spec.execution) is not Execution
    ):
        raise ConfigError("Mitochondrial composition requires its own model/experiment/execution")
    raw = prior.to_dict(base_spec(spec))
    rows = []
    for row in spec.model.mitochondria:
        value = asdict(row)
        for key in ("initial_amount_fmol", "diffusivity_m2_per_s"):
            value[key] = dict(zip(spec.model.species_ids, getattr(row, key), strict=True))
        rows.append(value)
    raw["model"].update(
        id=MODEL_ID,
        mitochondria=dict(
            law=process.LAW_ID,
            source_law=process.SOURCE_LAW,
            initialization=INITIALIZATION,
            voltage=VOLTAGE,
            cytosol_volume_role=VOLUME_ROLE,
            constants=dict(faraday_C_mol=F, gas_constant_J_mol_K=R),
            compartments=rows,
        ),
    )
    raw["experiment"]["mitochondria_controls"] = [
        dict(mitochondrion_id=row.id, schedule=[asdict(c) for c in group])
        for row, group in zip(
            spec.model.mitochondria, spec.experiment.mitochondrial_controls, strict=True
        )
    ]
    return raw


def _compartments(block, model):
    _fields(
        block,
        {
            "law",
            "source_law",
            "initialization",
            "voltage",
            "cytosol_volume_role",
            "constants",
            "compartments",
        },
        "mitochondria",
    )
    for key, expected in dict(
        law=process.LAW_ID,
        source_law=process.SOURCE_LAW,
        initialization=INITIALIZATION,
        voltage=VOLTAGE,
        cytosol_volume_role=VOLUME_ROLE,
    ).items():
        if block[key] != expected:
            raise ConfigError("Declare the continuous mitochondrial contract: " + key)
    c = _fields(
        block["constants"], {"faraday_C_mol", "gas_constant_J_mol_K"}, "mitochondrial constants"
    )
    if (
        _number(c["faraday_C_mol"], "Faraday constant") != F
        or _number(c["gas_constant_J_mol_K"], "gas constant") != R
    ):
        raise ConfigError("Mitochondrial constants must match the coupled SI laws")
    rows = block["compartments"]
    if type(rows) is not list or len(rows) != len(model.cells):
        raise ConfigError("Declare one finite mitochondrial compartment per actual cell")
    occupied = set(model.species_ids) | {
        p.id
        for p in (
            *model.cells,
            *model.extracellular,
            *model.membranes,
            *model.junctions,
            *model.faces,
            *model.channels,
            *model.calcium_channels,
            *model.energy_pools,
            *model.regeneration_ports,
            *model.network_transporters,
            *(p.pump for p in model.membranes if p.pump is not None),
        )
    }
    cells, result = {c.id for c in model.cells}, {}
    for row in rows:
        _fields(row, set(Mitochondrion.__dataclass_fields__), "mitochondrial compartment")
        name, owner = identifier(row["id"]), identifier(row["cell_id"])
        if name in occupied or owner not in cells or owner in result:
            raise ConfigError("Mitochondria require distinct identities and exactly one cell owner")
        occupied.add(name)
        v = signed_number(row["initial_voltage_V"], "mitochondrial voltage")
        if abs(v) > process.MAX_VOLTAGE_V:
            raise ConfigError("Mitochondrial voltage exceeds the declared numerical domain")
        result[owner] = Mitochondrion(
            name,
            owner,
            *(
                positive(row[k], k)
                for k in (
                    "volume_pL",
                    "area_m2",
                    "specific_capacitance_F_per_m2",
                    "membrane_thickness_m",
                )
            ),
            v,
            aligned(
                row["initial_amount_fmol"], model.species_ids, "mitochondrial inventory", positive
            ),
            aligned(
                row["diffusivity_m2_per_s"], model.species_ids, "mitochondrial diffusivity", _number
            ),
        )
        m = result[owner]
        if (
            not np.isfinite(m.area_m2 * m.specific_capacitance_F_per_m2)
            or m.area_m2 * m.specific_capacitance_F_per_m2 <= 0
        ):
            raise ConfigError("Mitochondrial capacitance must be positive and representable")
    return tuple(result[c.id] for c in model.cells)


def _controls(rows, compartments, end):
    if type(rows) is not list:
        raise ConfigError("Declare mitochondrial controls")
    result = {}
    for row in rows:
        _fields(row, {"mitochondrion_id", "schedule"}, "mitochondrial control")
        name, schedule = identifier(row["mitochondrion_id"]), row["schedule"]
        if name in result or type(schedule) is not list or not schedule:
            raise ConfigError("Require unique mitochondrial controls with nonempty schedules")
        for value in schedule:
            _fields(value, {"time", "availability"}, "mitochondrial change")
        changes = tuple(
            ChannelChange(
                _number(v["time"], "mitochondrial time"),
                fraction(v["availability"], "mitochondrial availability"),
            )
            for v in schedule
        )
        if (
            changes[0].time != 0
            or any(c.time > end for c in changes)
            or any(b.time <= a.time for a, b in zip(changes, changes[1:], strict=False))
        ):
            raise ConfigError(
                "Mitochondrial controls start at zero and increase within the horizon"
            )
        result[name] = changes
    if set(result) != {m.id for m in compartments}:
        raise ConfigError("Mitochondrial control IDs must exactly match compartments")
    return tuple(result[m.id] for m in compartments)


def parse(data):
    _fields(data, {"schema_version", "model", "experiment", "execution"}, "definition")
    raw = deepcopy(data)
    if type(raw["model"]) is not dict or raw["model"].get("id") != MODEL_ID:
        raise ConfigError("Require " + MODEL_ID)
    try:
        block = raw["model"].pop("mitochondria")
        schedules = raw["experiment"].pop("mitochondria_controls")
    except (KeyError, TypeError, AttributeError) as error:
        raise ConfigError("Declare mitochondrial compartments and controls") from error
    raw["model"]["id"] = prior.MODEL_ID
    original = prior.parse(raw)
    compartments = _compartments(block, original.model)
    spec = replace(
        original,
        model=SurfaceCalciumEnergyMitochondriaModel(
            **vars(original.model), mitochondria=compartments
        ),
        experiment=Experiment(
            **vars(original.experiment),
            mitochondrial_controls=_controls(schedules, compartments, original.experiment.end_time),
        ),
        execution=Execution(**vars(original.execution)),
    )
    from cells.models import surface_calcium_energy_mitochondria

    try:
        with np.errstate(all="ignore"):
            surface_calcium_energy_mitochondria.check_definition(spec)
    except (ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid mitochondrial composition: " + str(error)) from error
    return spec
