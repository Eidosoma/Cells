"""Small explicit model registry: no dynamic plugins or organ-name branches.

Each module supplies state/layout types, initialization, a pure RHS, numerical
checks, read-only observations, and a summary. Scientific meaning stays there;
the runner owns scheduling, integration, replay, and resource policy.
"""

from cells.core.betse_junction_spec import BetseJunctionModel
from cells.core.betse_spatial_spec import BetseSpatialModel
from cells.core.er_spec import ERModel
from cells.core.gated_calcium_spec import GatedCalciumModel
from cells.core.ip3_calcium_spec import IP3CalciumModel
from cells.core.plasma_calcium_spec import PlasmaModel
from cells.core.reaction_spec import ReactionNetworkSpec
from cells.core.spatial_calcium_spec import CalciumModel
from cells.core.specs import (
    BioelectricPairSpec,
    BioelectricSpec,
    ConfigError,
    EMTModelSpec,
    FiniteExtracellularSpec,
    JunctionFiniteExtracellularSpec,
    KineticFiniteExtracellularSpec,
    ModelSpec,
    MultispeciesSpec,
    PassivePairSpec,
    PhysicalIonicGraphSpec,
    ReactionTransportSpec,
    SourcePairSpec,
    SpatialExtracellularSpec,
    SpatialJunctionSpec,
    VoltageGatedSpec,
)
from cells.core.surface_calcium_energy_spec import (
    SurfaceCalciumEnergyActivatedModel,
    SurfaceCalciumEnergyCatalogModel,
    SurfaceCalciumEnergyHCNExtraModel,
    SurfaceCalciumEnergyModel,
    SurfaceCalciumEnergyMorrisLecarModel,
)
from cells.core.surface_calcium_energy_water_repair_spec import SurfaceCalciumEnergyWaterRepairModel
from cells.core.surface_calcium_energy_water_spec import SurfaceCalciumEnergyWaterModel
from cells.core.surface_calcium_spec import (
    SurfaceCalciumActivatedCatalogModel,
    SurfaceCalciumCatalogModel,
    SurfaceCalciumCavModel,
    SurfaceCalciumChannelModel,
    SurfaceCalciumExtendedCatalogModel,
    SurfaceCalciumHCNExtraModel,
    SurfaceCalciumHCNModel,
    SurfaceCalciumKv1Model,
    SurfaceCalciumModel,
    SurfaceCalciumMorrisLecarModel,
    SurfaceCalciumSodiumModel,
)
from cells.core.surface_calcium_water_spec import SurfaceCalciumWaterModel
from cells.core.surface_cotransport_spec import SurfaceCotransportModel
from cells.core.surface_cotransport_water_spec import SurfaceCotransportWaterModel
from cells.core.surface_energy_spec import SurfaceEnergyModel, SurfaceEnergyMorrisLecarModel
from cells.core.surface_energy_water_spec import (
    SurfaceEnergyWaterModel,
    SurfaceEnergyWaterMorrisLecarModel,
)
from cells.core.surface_kinetic_spec import (
    SurfaceCalciumActivatedModel,
    SurfaceCatalogModel,
    SurfaceCavModel,
    SurfaceChannelModel,
    SurfaceExtendedCatalogModel,
    SurfaceHCNExtraModel,
    SurfaceHCNModel,
    SurfaceKineticModel,
    SurfaceKv1Model,
    SurfaceMorrisLecarModel,
    SurfaceSodiumModel,
)
from cells.core.surface_mobile_channel_spec import SurfaceMobileChannelModel
from cells.core.surface_mobile_pump_repair_spec import SurfaceMobilePumpRepairModel
from cells.core.surface_mobile_pump_spec import SurfaceMobilePumpModel
from cells.core.surface_mobile_repair_spec import SurfaceMobileRepairModel
from cells.core.surface_redistribution_spec import SurfaceRedistributionModel
from cells.core.surface_repair_spec import SurfaceMorrisLecarRepairModel, SurfaceRepairModel
from cells.core.surface_tissue_spec import SurfaceTissueModel
from cells.core.surface_water_kinetic_spec import (
    SurfaceWaterKineticModel,
    SurfaceWaterMorrisLecarModel,
)
from cells.core.surface_water_spec import SurfaceWaterModel
from cells.core.tissue_calcium_spec import TissueCalciumModel
from cells.core.tissue_spec import TissueModel
from cells.models import (
    betse_junction,
    betse_spatial,
    bioelectric_cell,
    bioelectric_pair,
    compartment_reactions,
    emt_mirna,
    er_calcium,
    finite_extracellular,
    gated_calcium,
    ip3_calcium,
    junction_finite_extracellular,
    kinetic_finite_extracellular,
    multispecies_membrane,
    passive_pair,
    physical_ionic_graph,
    plasma_calcium,
    reaction_transport,
    source_decay,
    source_pair,
    spatial_calcium,
    spatial_extracellular,
    spatial_junction,
    surface_calcium,
    surface_calcium_catalog,
    surface_calcium_cav,
    surface_calcium_channels,
    surface_calcium_hcn,
    surface_calcium_kv1,
    surface_calcium_sodium,
    surface_catalog,
    surface_cav,
    surface_channels,
    surface_hcn,
    surface_kinetic,
    surface_kv1,
    surface_mobile_channel,
    surface_mobile_pump,
    surface_mobile_pump_repair,
    surface_mobile_repair,
    surface_redistribution,
    surface_repair,
    surface_sodium,
    surface_tissue,
    surface_water,
    surface_water_kinetic,
    tissue,
    tissue_calcium,
    voltage_gated_membrane,
)


def get_model(spec):
    if isinstance(spec, SurfaceCotransportWaterModel):
        from cells.models import surface_cotransport_water

        return surface_cotransport_water
    if isinstance(spec, SurfaceCotransportModel):
        from cells.models import surface_cotransport

        return surface_cotransport
    if isinstance(spec, SurfaceEnergyWaterMorrisLecarModel):
        from cells.models import surface_energy_water_morris_lecar

        return surface_energy_water_morris_lecar
    if isinstance(spec, SurfaceEnergyWaterModel):
        from cells.models import surface_energy_water

        return surface_energy_water
    if isinstance(spec, SurfaceEnergyMorrisLecarModel):
        from cells.models import surface_energy_morris_lecar

        return surface_energy_morris_lecar
    if isinstance(spec, SurfaceEnergyModel):
        from cells.models import surface_energy

        return surface_energy
    if isinstance(spec, SurfaceWaterMorrisLecarModel):
        from cells.models import surface_water_morris_lecar

        return surface_water_morris_lecar
    if isinstance(spec, SurfaceWaterKineticModel):
        return surface_water_kinetic
    if isinstance(spec, SurfaceWaterModel):
        return surface_water
    if isinstance(spec, BetseJunctionModel):
        return betse_junction
    if isinstance(spec, BetseSpatialModel):
        return betse_spatial
    if isinstance(spec, SurfaceMobileChannelModel):
        return surface_mobile_channel
    if isinstance(spec, SurfaceMobilePumpModel):
        return surface_mobile_pump
    if isinstance(spec, SurfaceRedistributionModel):
        return surface_redistribution
    if isinstance(spec, SurfaceMobilePumpRepairModel):
        return surface_mobile_pump_repair
    if isinstance(spec, SurfaceMobileRepairModel):
        return surface_mobile_repair
    if isinstance(spec, SurfaceMorrisLecarRepairModel):
        from cells.models import surface_repair_morris_lecar

        return surface_repair_morris_lecar
    if isinstance(spec, SurfaceRepairModel):
        return surface_repair
    if isinstance(spec, SurfaceCalciumEnergyWaterRepairModel):
        from cells.models import surface_calcium_energy_water_repair

        return surface_calcium_energy_water_repair
    if isinstance(spec, SurfaceCalciumEnergyWaterModel):
        from cells.models import surface_calcium_energy_water

        return surface_calcium_energy_water
    if isinstance(spec, SurfaceCalciumEnergyHCNExtraModel):
        from cells.models import surface_calcium_energy_hcn_extra

        return surface_calcium_energy_hcn_extra
    if isinstance(spec, SurfaceCalciumEnergyMorrisLecarModel):
        from cells.models import surface_calcium_energy_morris_lecar

        return surface_calcium_energy_morris_lecar
    if isinstance(spec, SurfaceCalciumEnergyActivatedModel):
        from cells.models import surface_calcium_energy_activated

        return surface_calcium_energy_activated
    if isinstance(spec, SurfaceCalciumEnergyCatalogModel):
        from cells.models import surface_calcium_energy_catalog

        return surface_calcium_energy_catalog
    if isinstance(spec, SurfaceCalciumEnergyModel):
        from cells.models import surface_calcium_energy

        return surface_calcium_energy
    if isinstance(spec, SurfaceCalciumWaterModel):
        from cells.models import surface_calcium_water

        return surface_calcium_water
    if isinstance(spec, SurfaceCalciumHCNExtraModel):
        from cells.models import surface_calcium_hcn_extra

        return surface_calcium_hcn_extra
    if isinstance(spec, SurfaceCalciumMorrisLecarModel):
        from cells.models import surface_calcium_morris_lecar

        return surface_calcium_morris_lecar
    if isinstance(spec, SurfaceCalciumActivatedCatalogModel):
        from cells.models import surface_calcium_activated_catalog

        return surface_calcium_activated_catalog
    if isinstance(spec, SurfaceCalciumExtendedCatalogModel):
        from cells.models import surface_calcium_catalog_v2

        return surface_calcium_catalog_v2
    if isinstance(spec, SurfaceCalciumCatalogModel):
        return surface_calcium_catalog
    if isinstance(spec, SurfaceCalciumCavModel):
        return surface_calcium_cav
    if isinstance(spec, SurfaceCalciumKv1Model):
        return surface_calcium_kv1
    if isinstance(spec, SurfaceCalciumHCNModel):
        return surface_calcium_hcn
    if isinstance(spec, SurfaceCalciumSodiumModel):
        return surface_calcium_sodium
    if isinstance(spec, SurfaceCalciumChannelModel):
        return surface_calcium_channels
    if isinstance(spec, SurfaceCalciumModel):
        return surface_calcium
    if isinstance(spec, SurfaceHCNExtraModel):
        from cells.models import surface_hcn_extra

        return surface_hcn_extra
    if isinstance(spec, SurfaceMorrisLecarModel):
        from cells.models import surface_morris_lecar

        return surface_morris_lecar
    if isinstance(spec, SurfaceCalciumActivatedModel):
        from cells.models import surface_calcium_activated

        return surface_calcium_activated
    if isinstance(spec, SurfaceExtendedCatalogModel):
        from cells.models import surface_catalog_v2

        return surface_catalog_v2
    if isinstance(spec, SurfaceCatalogModel):
        return surface_catalog
    if isinstance(spec, SurfaceCavModel):
        return surface_cav
    if isinstance(spec, SurfaceKv1Model):
        return surface_kv1
    if isinstance(spec, SurfaceHCNModel):
        return surface_hcn
    if isinstance(spec, SurfaceSodiumModel):
        return surface_sodium
    if isinstance(spec, SurfaceChannelModel):
        return surface_channels
    if isinstance(spec, SurfaceKineticModel):
        return surface_kinetic
    if isinstance(spec, SurfaceTissueModel):
        return surface_tissue
    if isinstance(spec, TissueCalciumModel):
        return tissue_calcium
    if isinstance(spec, TissueModel):
        return tissue
    if isinstance(spec, IP3CalciumModel):
        return ip3_calcium
    if isinstance(spec, GatedCalciumModel):
        return gated_calcium
    if isinstance(spec, PlasmaModel):
        return plasma_calcium
    if isinstance(spec, CalciumModel):
        return spatial_calcium
    if isinstance(spec, ERModel):
        return er_calcium
    if isinstance(spec, ReactionNetworkSpec):
        return compartment_reactions
    if isinstance(spec, SpatialJunctionSpec):
        return spatial_junction
    if isinstance(spec, JunctionFiniteExtracellularSpec):
        return junction_finite_extracellular
    if isinstance(spec, KineticFiniteExtracellularSpec):
        return kinetic_finite_extracellular
    if isinstance(spec, SpatialExtracellularSpec):
        return spatial_extracellular
    if isinstance(spec, FiniteExtracellularSpec):
        return finite_extracellular
    if isinstance(spec, PhysicalIonicGraphSpec):
        return physical_ionic_graph
    if isinstance(spec, VoltageGatedSpec):
        return voltage_gated_membrane
    if isinstance(spec, MultispeciesSpec):
        return multispecies_membrane
    if isinstance(spec, SourcePairSpec):
        return source_pair
    if isinstance(spec, BioelectricPairSpec):
        return bioelectric_pair
    if isinstance(spec, BioelectricSpec):
        return bioelectric_cell
    if isinstance(spec, ModelSpec):
        return source_decay
    if isinstance(spec, EMTModelSpec):
        return emt_mirna
    if isinstance(spec, PassivePairSpec):
        return passive_pair
    if isinstance(spec, ReactionTransportSpec):
        return reaction_transport
    raise ConfigError(f"No registered implementation for {type(spec).__name__}")
