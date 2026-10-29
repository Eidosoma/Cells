"""Explicit family dispatch for conservative cell removal."""

from cells.core.specs import ConfigError
from cells.core.surface_active_excision_spec import SurfaceActiveExcisionModel
from cells.core.surface_calcium_energy_excision_spec import SurfaceCalciumEnergyExcisionModel
from cells.core.surface_calcium_energy_mitochondria_excision_spec import (
    SurfaceCalciumEnergyMitochondriaExcisionModel,
)
from cells.core.surface_calcium_energy_mitochondria_spec import (
    SurfaceCalciumEnergyMitochondriaModel,
)
from cells.core.surface_calcium_energy_regulated_v2_excision_spec import (
    SurfaceCalciumEnergyRegulatedV2ExcisionModel,
)
from cells.core.surface_calcium_energy_regulated_v2_spec import SurfaceCalciumEnergyRegulatedV2Model
from cells.core.surface_calcium_energy_spec import SurfaceCalciumEnergyHCNExtraModel
from cells.core.surface_calcium_energy_transport_excision_spec import (
    SurfaceCalciumEnergyTransportExcisionModel,
)
from cells.core.surface_calcium_energy_transport_spec import SurfaceCalciumEnergyTransportModel
from cells.core.surface_calcium_energy_water_excision_spec import (
    SurfaceCalciumEnergyWaterExcisionModel,
)
from cells.core.surface_calcium_energy_water_spec import SurfaceCalciumEnergyWaterModel
from cells.core.surface_calcium_excision_spec import SurfaceCalciumExcisionModel
from cells.core.surface_calcium_spec import SurfaceCalciumHCNExtraModel
from cells.core.surface_excision_spec import SurfaceExcisionModel
from cells.core.surface_kinetic_spec import SurfaceHCNExtraModel
from cells.core.surface_tissue_spec import SurfaceTissueModel


def is_active(spec):
    return type(spec.model) in (SurfaceHCNExtraModel, SurfaceActiveExcisionModel)


def is_calcium(spec):
    return type(spec.model) in (SurfaceCalciumHCNExtraModel, SurfaceCalciumExcisionModel)


def is_calcium_energy(spec):
    return type(spec.model) in (
        SurfaceCalciumEnergyHCNExtraModel,
        SurfaceCalciumEnergyExcisionModel,
    )


def is_calcium_energy_transport(spec):
    return type(spec.model) in (
        SurfaceCalciumEnergyTransportModel,
        SurfaceCalciumEnergyTransportExcisionModel,
    )


def is_calcium_energy_mitochondria(spec):
    return type(spec.model) in (
        SurfaceCalciumEnergyMitochondriaModel,
        SurfaceCalciumEnergyMitochondriaExcisionModel,
    )


def is_calcium_energy_water(spec):
    return type(spec.model) in (
        SurfaceCalciumEnergyWaterModel,
        SurfaceCalciumEnergyWaterExcisionModel,
    )


def is_calcium_energy_regulated_v2(spec):
    return type(spec.model) in (
        SurfaceCalciumEnergyRegulatedV2Model,
        SurfaceCalciumEnergyRegulatedV2ExcisionModel,
    )


def excise(spec, checkpoint, removed_cell_ids):
    if is_calcium_energy_regulated_v2(spec):
        from cells.core.calcium_energy_regulated_v2_tissue_excision import excise as operation
    elif is_calcium_energy_water(spec):
        from cells.core.calcium_energy_water_tissue_excision import excise as operation
    elif is_calcium_energy_mitochondria(spec):
        from cells.core.calcium_energy_mitochondria_tissue_excision import excise as operation
    elif is_calcium_energy_transport(spec):
        from cells.core.calcium_energy_transport_tissue_excision import excise as operation
    elif is_calcium_energy(spec):
        from cells.core.calcium_energy_tissue_excision import excise as operation
    elif is_calcium(spec):
        from cells.core.calcium_tissue_excision import excise as operation
    elif is_active(spec):
        from cells.core.active_tissue_excision import excise as operation
    elif type(spec.model) in (SurfaceTissueModel, SurfaceExcisionModel):
        from cells.core.tissue_excision import excise as operation
    else:
        raise ConfigError(
            "Cuts support resolved_tissue@1, resolved_tissue@12, resolved_calcium@11, "
            "resolved_calcium_energy@5, resolved_calcium_energy_transport@1, "
            "resolved_calcium_energy_mitochondria@1, resolved_calcium_energy_water@1 "
            "and their excision epochs"
        )
    return operation(spec, checkpoint, removed_cell_ids)
