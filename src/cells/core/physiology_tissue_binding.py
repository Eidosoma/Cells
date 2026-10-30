"""Explicit ordinary-tissue ownership and SI units for physiological buffers.

This host adapter binds geometry, not noise timing or protein charge. Native
matrix mode has one exterior volume parameter: heterogeneous actual exterior
volumes refuse. Membrane diffusivity D=P*thickness is a declared unit bridge,
never a new transporter or a reinterpretation of ionic/channel permeability.
"""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from numbers import Real

import numpy as np

from cells.core import physiology_perturbation_step as step
from cells.core import physiology_random_streams as streams
from cells.core import surface_calcium_energy_spec as fuel
from cells.core import surface_calcium_spec as calcium
from cells.core import surface_kinetic_spec as ionic
from cells.core import surface_tissue_spec as passive
from cells.core.specs import SimulationSpec
from cells.processes import betse_perturbations as perturb

KIND = "cells.physiology_tissue_binding@1"
PL_TO_M3 = 1e-15
SUPPORTED = {
    passive.SurfaceTissueModel: passive.MODEL_ID,
    ionic.SurfaceHCNExtraModel: ionic.HCN_EXTRA_MODEL_ID,
    calcium.SurfaceCalciumHCNExtraModel: calcium.HCN_EXTRA_MODEL_ID,
    fuel.SurfaceCalciumEnergyHCNExtraModel: fuel.HCN_EXTRA_MODEL_ID,
}
DOMAINS = ("cell", "membrane", "environment", "ion")


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _freeze(value, dtype=None):
    value = np.ascontiguousarray(value, dtype=dtype)
    return np.frombuffer(value.tobytes(), dtype=value.dtype).reshape(value.shape)


def _positive(value):
    if (
        not isinstance(value, Real)
        or isinstance(value, (bool, np.bool_))
        or not np.isfinite(value)
        or value <= 0
    ):
        raise ValueError("Require an explicit finite positive physical measure")
    return float(value)


def _axis(values, expected):
    if (
        not isinstance(values, (list, tuple))
        or len(values) != len(expected)
        or any(type(value) is not str or not value for value in values)
        or len(set(values)) != len(values)
        or set(values) != set(expected)
    ):
        raise ValueError("Component owner axes must be complete explicit tissue ID permutations")
    return tuple(values)


@dataclass(frozen=True, slots=True)
class TissueBinding:
    model_id: str
    source_definition_sha256: str
    component: perturb.Binding
    tissue_cell_ids: tuple
    tissue_membrane_ids: tuple
    tissue_environment_ids: tuple
    tissue_ion_ids: tuple
    cell_to_tissue: object
    membrane_to_tissue: object
    environment_to_tissue: object
    ion_to_tissue: object
    membrane_thickness_m: object  # Component membrane order.
    initial_permeability_m_s: object  # Tissue ion x padded membrane slots.
    inputs_json: str
    identity: str

    def __post_init__(self):
        for name in (
            *[domain + "_to_tissue" for domain in DOMAINS],
            "membrane_thickness_m",
            "initial_permeability_m_s",
        ):
            object.__setattr__(self, name, _freeze(getattr(self, name)))
        if type(self.component) is not perturb.Binding:
            raise ValueError("Require the qualified physiological geometry binding")
        kernel = perturb.Kernel(*(_freeze(value) for value in self.component.kernel))
        object.__setattr__(self, "component", replace(self.component, kernel=kernel))


@dataclass(frozen=True, slots=True)
class PhysicalPermeability:
    current_m_s: object
    base_m_s: object
    scheduled_m_s: object
    binding_identity: str

    def __post_init__(self):
        for name in ("current_m_s", "base_m_s", "scheduled_m_s"):
            object.__setattr__(self, name, _freeze(getattr(self, name), np.float64))


def _payload(binding):
    component = binding.component
    return dict(
        kind=KIND,
        law_id=perturb.LAW_ID,
        model_id=binding.model_id,
        source_definition_sha256=binding.source_definition_sha256,
        inputs=json.loads(binding.inputs_json),
        tissue_axes={
            domain: list(getattr(binding, "tissue_" + domain + "_ids")) for domain in DOMAINS
        },
        slot_maps={domain: getattr(binding, domain + "_to_tissue").tolist() for domain in DOMAINS},
        membrane_thickness_m=binding.membrane_thickness_m.tolist(),
        initial_permeability_m_s=binding.initial_permeability_m_s.tolist(),
        component_identity=component.identity,
        geometry=dict(
            membrane_area_m2=component.kernel.membrane_area_m2.tolist(),
            cell_volume_m3=component.kernel.cell_volume_m3.tolist(),
            environment_volume_m3=component.kernel.environment_effective_volume_m3.tolist(),
            membrane_cell_ids=[component.cell_ids[i] for i in component.kernel.owner],
            membrane_environment_ids=[
                component.environment_ids[i] for i in component.kernel.environment_owner
            ],
        ),
    )


def validate_binding(binding):
    if type(binding) is not TissueBinding or binding.model_id not in SUPPORTED.values():
        raise ValueError("Require an exact supported ordinary tissue binding")
    streams._binding_identity(binding.component)
    if binding.component.environment_mode != "matrix":
        raise ValueError("Only the explicitly representable native matrix mode is supported")
    for domain in DOMAINS:
        tissue_ids = getattr(binding, "tissue_" + domain + "_ids")
        _axis(getattr(binding.component, domain + "_ids"), tissue_ids)
        indices = np.asarray(getattr(binding, domain + "_to_tissue"))
        expected = [
            tissue_ids.index(value) for value in getattr(binding.component, domain + "_ids")
        ]
        if indices.dtype.kind not in "iu" or not np.array_equal(indices, expected):
            raise ValueError("Owner IDs and explicit tissue slot maps disagree")
    thickness = binding.membrane_thickness_m
    if (
        thickness.shape != (len(binding.component.membrane_ids),)
        or thickness.dtype != np.float64
        or not np.isfinite(thickness).all()
        or np.any(thickness <= 0)
    ):
        raise ValueError("Invalid per-membrane SI thickness")
    _physical_array(binding.initial_permeability_m_s, binding, signed=False)
    try:
        valid = _digest(_payload(binding)) == binding.identity
    except (TypeError, ValueError, IndexError, AttributeError) as error:
        raise ValueError("Invalid physiological tissue binding provenance") from error
    if not valid:
        raise ValueError("Tissue binding owners/units/provenance changed after binding")
    return binding


def bind_tissue(
    spec,
    *,
    cell_ids,
    membrane_ids,
    environment_ids,
    ion_ids,
    membrane_thickness_m,
    boundary_cell_occurrences,
    provenance,
):
    """Bind complete explicit component axes to exact ordinary tissue owners.

    Thickness is a complete membrane-ID -> metres mapping, never inferred from
    capacitance or area. Boundary occurrences are caller-declared cell IDs;
    order and duplicates retain the native categorical weights. No RNG runs.
    """
    if type(spec) is not SimulationSpec or type(spec.model) not in SUPPORTED:
        raise ValueError("Require exact ordinary passive@1, ionic@12, calcium@11 or fuel@5")
    if spec.execution.precision != "float64":
        raise ValueError("Tissue/component unit binding requires explicit float64 precision")
    if not isinstance(provenance, dict) or not provenance:
        raise ValueError("Require explicit nonempty caller provenance")
    source = spec.to_dict()
    source_sha = _digest(source)
    model = spec.model
    tissue = dict(
        cell=tuple(row.id for row in model.cells),
        membrane=tuple(row.id for row in model.membranes),
        environment=tuple(row.id for row in model.extracellular),
        ion=tuple(model.species_ids),
    )
    axes = {
        domain: _axis(values, tissue[domain])
        for domain, values in zip(
            DOMAINS, (cell_ids, membrane_ids, environment_ids, ion_ids), strict=True
        )
    }
    if not isinstance(membrane_thickness_m, Mapping) or set(membrane_thickness_m) != set(
        tissue["membrane"]
    ):
        raise ValueError("Declare exactly one positive thickness for every physical membrane ID")
    thickness_map = {key: _positive(value) for key, value in membrane_thickness_m.items()}
    if not isinstance(boundary_cell_occurrences, (list, tuple)):
        raise ValueError("Require an explicit ordered boundary cell occurrence list")
    boundary = tuple(boundary_cell_occurrences)
    if not boundary or any(
        type(value) is not str or value not in tissue["cell"] for value in boundary
    ):
        raise ValueError("Boundary occurrences must name actual tissue cells")
    outside = {row.id: row for row in model.extracellular}
    raw_volumes = np.asarray([_positive(outside[name].volume_pL) for name in axes["environment"]])
    # Compare the original declaration as well: multiplying distinct floats by
    # 1e-15 must never conceal heterogeneity by a conversion rounding collision.
    if not np.all(raw_volumes == raw_volumes[0]):
        raise ValueError(
            "Native matrix mode cannot represent heterogeneous actual exterior volumes"
        )
    cells, membranes = ({row.id: row for row in rows} for rows in (model.cells, model.membranes))
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        volumes = np.asarray([_positive(cells[name].volume_pL) for name in axes["cell"]]) * PL_TO_M3
        exterior_volume = float(raw_volumes[0] * PL_TO_M3)
    if not np.isfinite(exterior_volume) or exterior_volume <= 0:
        raise ValueError("Actual exterior SI volume is unrepresentable")
    inputs = dict(
        **{domain + "_ids": list(axes[domain]) for domain in DOMAINS},
        membrane_thickness_m=thickness_map,
        boundary_cell_occurrences=list(boundary),
        provenance=json.loads(_json(provenance)),
    )
    component = perturb.bind_layout(
        perturb.Layout(
            *(axes[domain] for domain in DOMAINS),
            tuple(membranes[name].inside for name in axes["membrane"]),
            tuple(membranes[name].outside for name in axes["membrane"]),
            boundary,
            np.asarray([_positive(membranes[name].area_m2) for name in axes["membrane"]]),
            volumes,
            exterior_volume,
            "matrix",
            dict(
                kind=KIND,
                model_id=SUPPORTED[type(model)],
                source_definition_sha256=source_sha,
                units=dict(
                    tissue_volume="pL",
                    component_volume="m3",
                    area="m2",
                    thickness="m",
                    permeability="m/s",
                    diffusion="m2/s",
                ),
                inputs=inputs,
            ),
        )
    )
    maps = {
        domain: np.asarray([tissue[domain].index(value) for value in axes[domain]], np.int64)
        for domain in DOMAINS
    }
    capacity = spec.execution.membrane_capacity
    initial = np.zeros((len(tissue["ion"]), capacity), dtype=np.float64)
    initial[:, : len(tissue["membrane"])] = np.asarray(
        [row.permeability_m_per_s for row in model.membranes], dtype=np.float64
    ).T
    binding = TissueBinding(
        SUPPORTED[type(model)],
        source_sha,
        component,
        *(tissue[domain] for domain in DOMAINS),
        *(maps[domain] for domain in DOMAINS),
        np.asarray([thickness_map[name] for name in axes["membrane"]], np.float64),
        initial,
        _json(inputs),
        "",
    )
    binding = replace(binding, identity=_digest(_payload(binding)))
    validate_binding(binding)
    initial_diffusion(binding)  # Refuse nonrepresentable D rather than hiding underflow/overflow.
    return binding


def _physical_array(value, binding, *, signed):
    array = np.asarray(value)
    shape = binding.initial_permeability_m_s.shape
    if (
        array.dtype.kind not in "fiu"
        or array.shape != shape
        or len(shape) != 2
        or shape[0] != len(binding.tissue_ion_ids)
        or shape[1] < len(binding.tissue_membrane_ids)
        or not np.isfinite(array).all()
        or not signed
        and np.any(array < 0)
    ):
        raise ValueError(
            "Invalid physical permeability with explicit tissue ion/padded membrane axes"
        )
    if np.any(array[:, len(binding.tissue_membrane_ids) :] != 0):
        raise ValueError("Inactive physical membrane padding must remain exactly zero")
    return array


def _convert(values, thickness, *, divide):
    with np.errstate(over="ignore", under="ignore", invalid="ignore", divide="ignore"):
        result = values / thickness if divide else values * thickness
    if not np.isfinite(result).all() or np.any((values != 0) & (result == 0)):
        raise ValueError("Permeability/diffusion SI conversion is unrepresentable")
    return result


def permeability_to_diffusion(permeability_m_s, binding, *, scheduled=False):
    """Gather actual padded physical P, then multiply each named membrane thickness."""
    validate_binding(binding)
    if type(scheduled) is not bool:
        raise ValueError("Declare whether this is a signed scheduled modifier")
    array = _physical_array(permeability_m_s, binding, signed=scheduled)
    values = array[np.ix_(binding.ion_to_tissue, binding.membrane_to_tissue)]
    return _freeze(_convert(values, binding.membrane_thickness_m, divide=False), np.float64)


def initial_diffusion(binding):
    return permeability_to_diffusion(binding.initial_permeability_m_s, binding)


def diffusion_to_permeability(diffusion, binding):
    """Map all three component buffers to actual physical tissue order, without draws."""
    validate_binding(binding)
    if type(diffusion) is not perturb.StaticState:
        raise ValueError("Require complete current/base/scheduled diffusion buffers")
    result = []
    shape = (len(binding.component.ion_ids), len(binding.component.membrane_ids))
    for key, values in diffusion._asdict().items():
        values = np.asarray(values)
        if (
            values.shape != shape
            or values.dtype.kind not in "fiu"
            or not np.isfinite(values).all()
            or key != "scheduled_m2_s"
            and np.any(values < 0)
        ):
            raise ValueError("Invalid explicit component diffusivity buffer")
        physical = np.zeros_like(binding.initial_permeability_m_s)
        physical[np.ix_(binding.ion_to_tissue, binding.membrane_to_tissue)] = _convert(
            values, binding.membrane_thickness_m, divide=True
        )
        result.append(physical)
    return PhysicalPermeability(*result, binding.identity)


def component_permeability(state, binding):
    validate_binding(binding)
    step.validate_state(state, binding.component)
    return diffusion_to_permeability(state.diffusion, binding)


def binding_record(binding):
    """Return fresh JSON provenance; mutable exports cannot modify the binding."""
    validate_binding(binding)
    return _payload(binding) | dict(identity=binding.identity)


def restore_binding(record, spec):
    """Rebuild actual geometry/units from the caller's exact ordinary definition."""
    if not isinstance(record, dict) or record.get("kind") != KIND:
        raise ValueError("Require an explicit physiological tissue binding record")
    payload = {key: value for key, value in record.items() if key != "identity"}
    if record.get("identity") != _digest(payload):
        raise ValueError("Corrupt physiological tissue binding record")
    try:
        restored = bind_tissue(spec, **record["inputs"])
    except (KeyError, TypeError) as error:
        raise ValueError("Invalid physiological tissue binding declaration") from error
    if binding_record(restored) != record:
        raise ValueError(
            "Binding record differs from actual tissue owners/geometry/units/provenance"
        )
    return restored
