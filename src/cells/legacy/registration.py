"""The older model families' registrations (D188 R1): the legacy halves of the dispatch points.

The core's dispatch points check the active families (D189) first and, on a miss, call this
module through its one entry point, `cells.registry.legacy_entry.legacy()`:

- `model_for(spec)`: `models/registry.get_model`;
- `parse(data)` and `to_dict(self)`: `core/specs.parse_spec` and `SimulationSpec._fine_dict`;
- `control_values(spec, times)`: `core/schedule.control_values`;
- `cli(command)`: the command line's older subcommands (`cells.__main__`);
- `ensemble(model)`: the ensemble adapters' older assembly families (`ensemble/families.py`,
  `ensemble/cli.py`).

Each function holds its dispatch point's legacy entries, moved verbatim and in their order, and
returns None when no older family matches, so the core goes on as before. Their modules are
imported where they live today; move 1's rewriter retargets these imports. Nothing outside this
package imports it other than through that entry point (tests/unit/test_legacy_entry.py).
"""

import json
from types import SimpleNamespace

import numpy as np

from cells.definitions.specs import (
    BIOELECTRIC_ID,
    BIOELECTRIC_PAIR_ID,
    FINITE_EXTRACELLULAR_ID,
    JUNCTION_FINITE_EXTRACELLULAR_ID,
    KINETIC_FINITE_EXTRACELLULAR_ID,
    MULTISPECIES_ID,
    PHYSICAL_IONIC_GRAPH_ID,
    SOURCE_PAIR_ID,
    SPATIAL_EXTRACELLULAR_ID,
    SPATIAL_JUNCTION_ID,
    VOLTAGE_GATED_ID,
    BioelectricPairSpec,
    BioelectricSpec,
    ConfigError,
    EMTModelSpec,
    ExperimentSpec,
    FiniteExtracellularSpec,
    JunctionFiniteExtracellularSpec,
    KineticFiniteExtracellularSpec,
    ModelSpec,
    MultispeciesExecutionSpec,
    MultispeciesSpec,
    PassivePairSpec,
    PhysicalIonicGraphSpec,
    SourcePairSpec,
    SpatialExtracellularSpec,
    SpatialJunctionSpec,
    VoltageGatedSpec,
)
from cells.definitions.surface_kinetic_spec import (
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
from cells.definitions.surface_tissue_spec import SurfaceTissueModel
from cells.execution.schedule import (
    CalciumControl,
    ERControl,
    GatedCalciumControl,
    PlasmaControl,
    SurfaceCalciumControl,
    SurfaceMobilePumpRepairControl,
    SurfaceMobileRepairControl,
    SurfaceRepairControl,
)
from cells.legacy.core.er_spec import (
    ERChange,
    ERModel,
)
from cells.legacy.core.gated_calcium_spec import (
    GatedCalciumChange,
    GatedCalciumModel,
)
from cells.legacy.core.gated_calcium_spec import base_spec as plasma_spec
from cells.legacy.core.ip3_calcium_spec import IP3CalciumModel
from cells.legacy.core.plasma_calcium_spec import (
    PlasmaChange,
    PlasmaModel,
)
from cells.legacy.core.plasma_calcium_spec import base_spec as plasma_prior
from cells.legacy.core.reaction_spec import (
    ReactionChange,
    ReactionNetworkSpec,
)
from cells.legacy.core.spatial_calcium_spec import (
    CalciumChange,
    CalciumModel,
    ionic_spec,
    store_spec,
)
from cells.legacy.core.surface_calcium_energy_mitochondria_spec import (
    SurfaceCalciumEnergyMitochondriaModel,
)
from cells.legacy.core.surface_calcium_energy_spec import Control as SurfaceCalciumEnergyControl
from cells.legacy.core.surface_calcium_energy_spec import (
    SurfaceCalciumEnergyActivatedModel,
    SurfaceCalciumEnergyCatalogModel,
    SurfaceCalciumEnergyHCNExtraModel,
    SurfaceCalciumEnergyModel,
    SurfaceCalciumEnergyMorrisLecarModel,
)
from cells.legacy.core.surface_calcium_energy_spec import initial_prior_spec as calcium_energy_prior
from cells.legacy.core.surface_calcium_energy_transport_spec import (
    SurfaceCalciumEnergyTransportModel,
)
from cells.legacy.core.surface_calcium_energy_water_hcn_extra_spec import (
    Control as JointHCNWaterControl,
)
from cells.legacy.core.surface_calcium_energy_water_hcn_extra_spec import (
    SurfaceCalciumEnergyWaterHCNExtraModel,
)
from cells.legacy.core.surface_calcium_energy_water_hcn_extra_spec import (
    energy_spec as joint_hcn_water_prior,
)
from cells.legacy.core.surface_calcium_energy_water_repair_hcn_extra_spec import (
    Control as JointHCNRepairControl,
)
from cells.legacy.core.surface_calcium_energy_water_repair_hcn_extra_spec import (
    SurfaceCalciumEnergyWaterRepairHCNExtraModel,
)
from cells.legacy.core.surface_calcium_energy_water_repair_hcn_extra_spec import (
    base_spec as joint_hcn_repair_prior,
)
from cells.legacy.core.surface_calcium_energy_water_repair_spec import Control as JointRepairControl
from cells.legacy.core.surface_calcium_energy_water_repair_spec import (
    SurfaceCalciumEnergyWaterRepairModel,
)
from cells.legacy.core.surface_calcium_energy_water_repair_spec import (
    base_spec as joint_repair_prior,
)
from cells.legacy.core.surface_calcium_energy_water_spec import (
    Control as SurfaceCalciumEnergyWaterControl,
)
from cells.legacy.core.surface_calcium_energy_water_spec import SurfaceCalciumEnergyWaterModel
from cells.legacy.core.surface_calcium_energy_water_spec import (
    energy_spec as calcium_energy_water_prior,
)
from cells.legacy.core.surface_calcium_spec import Change as SurfaceCalciumChange
from cells.legacy.core.surface_calcium_spec import (
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
from cells.legacy.core.surface_calcium_spec import ionic_spec as surface_ionic_spec
from cells.legacy.core.surface_calcium_water_spec import Control as SurfaceCalciumWaterControl
from cells.legacy.core.surface_calcium_water_spec import SurfaceCalciumWaterModel
from cells.legacy.core.surface_calcium_water_spec import prior_spec as calcium_water_prior
from cells.legacy.core.surface_cotransport_spec import Control as SurfaceCotransportControl
from cells.legacy.core.surface_cotransport_spec import SurfaceCotransportModel
from cells.legacy.core.surface_cotransport_spec import energy_spec as cotransport_energy_spec
from cells.legacy.core.surface_cotransport_water_spec import Control as CotransportWaterControl
from cells.legacy.core.surface_cotransport_water_spec import SurfaceCotransportWaterModel
from cells.legacy.core.surface_cotransport_water_spec import water_spec as cotransport_water_spec
from cells.legacy.core.surface_energy_spec import Control as SurfaceEnergyControl
from cells.legacy.core.surface_energy_spec import (
    SurfaceEnergyModel,
    SurfaceEnergyMorrisLecarModel,
    initial_ionic_spec,
)
from cells.legacy.core.surface_energy_water_spec import Control as SurfaceEnergyWaterControl
from cells.legacy.core.surface_energy_water_spec import (
    SurfaceEnergyWaterModel,
    SurfaceEnergyWaterMorrisLecarModel,
    energy_spec,
)
from cells.legacy.core.surface_mobile_channel_spec import Control as SurfaceMobileChannelControl
from cells.legacy.core.surface_mobile_channel_spec import SurfaceMobileChannelModel
from cells.legacy.core.surface_mobile_channel_spec import prior_spec as mobile_channel_prior
from cells.legacy.core.surface_mobile_pump_repair_spec import SurfaceMobilePumpRepairModel
from cells.legacy.core.surface_mobile_pump_repair_spec import prior_spec as mobile_pump_repair_prior
from cells.legacy.core.surface_mobile_pump_spec import Control as SurfaceMobilePumpControl
from cells.legacy.core.surface_mobile_pump_spec import SurfaceMobilePumpModel
from cells.legacy.core.surface_mobile_pump_spec import prior_spec as mobile_pump_prior
from cells.legacy.core.surface_mobile_repair_spec import SurfaceMobileRepairModel
from cells.legacy.core.surface_mobile_repair_spec import prior_spec as mobile_repair_prior
from cells.legacy.core.surface_redistribution_spec import SurfaceRedistributionModel
from cells.legacy.core.surface_repair_spec import (
    SurfaceMorrisLecarRepairModel,
    SurfaceRepairModel,
)
from cells.legacy.core.surface_repair_spec import base_spec as repair_base_spec
from cells.legacy.core.surface_water_kinetic_spec import Control as SurfaceWaterKineticControl
from cells.legacy.core.surface_water_kinetic_spec import (
    SurfaceWaterKineticModel,
    SurfaceWaterMorrisLecarModel,
)
from cells.legacy.core.surface_water_kinetic_spec import prior_spec as water_kinetic_prior
from cells.legacy.core.surface_water_spec import Control as SurfaceWaterControl
from cells.legacy.core.surface_water_spec import SurfaceWaterModel
from cells.legacy.core.surface_water_spec import prior_spec as water_prior
from cells.legacy.core.tissue_calcium_spec import TissueCalciumModel
from cells.legacy.core.tissue_spec import TissueModel
from cells.legacy.models import (
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
    surface_kv1,
    surface_mobile_channel,
    surface_mobile_pump,
    surface_mobile_pump_repair,
    surface_mobile_repair,
    surface_redistribution,
    surface_repair,
    surface_sodium,
    surface_water,
    surface_water_kinetic,
    tissue,
    tissue_calcium,
    voltage_gated_membrane,
)
from cells.models import surface_kinetic, surface_tissue
from cells.records.io import load_snapshot


def model_for(spec):
    """`get_model`'s older families, in its order: the model module (None when none matches)."""
    from cells.legacy.core import surface_open_calcium_bath_epoch_spec as calcium_bath_epoch
    from cells.legacy.core import surface_open_calcium_energy_bath_epoch_spec as energy_bath_epoch

    if isinstance(spec, energy_bath_epoch.SurfaceOpenCalciumEnergyBathEpochModel):
        from cells.legacy.models import surface_open_calcium_energy_bath_epoch

        return surface_open_calcium_energy_bath_epoch
    if isinstance(spec, calcium_bath_epoch.SurfaceOpenCalciumBathEpochModel):
        from cells.legacy.models import surface_open_calcium_bath_epoch

        return surface_open_calcium_bath_epoch
    from cells.legacy.core import surface_open_calcium_bath_events_spec as calcium_bath
    from cells.legacy.core import surface_open_calcium_energy_bath_events_spec as energy_bath

    if isinstance(spec, energy_bath.SurfaceOpenCalciumEnergyBathEventModel):
        from cells.legacy.models import surface_open_calcium_energy_bath_events

        return surface_open_calcium_energy_bath_events
    if isinstance(spec, calcium_bath.SurfaceOpenCalciumBathEventModel):
        from cells.legacy.models import surface_open_calcium_bath_events

        return surface_open_calcium_bath_events
    from cells.legacy.core import surface_open_calcium_energy_spec as open_energy
    from cells.legacy.core import surface_open_calcium_spec as open_calcium

    if isinstance(spec, open_energy.SurfaceOpenCalciumEnergyModel):
        from cells.legacy.models import surface_open_calcium_energy

        return surface_open_calcium_energy
    if isinstance(spec, open_calcium.SurfaceOpenCalciumModel):
        from cells.legacy.models import surface_open_calcium

        return surface_open_calcium
    from cells.legacy.core import surface_active_bath_epoch_spec as active_bath_epoch
    from cells.legacy.core import surface_passive_bath_epoch_spec as passive_bath_epoch

    if isinstance(spec, active_bath_epoch.SurfaceActiveBathEpochModel):
        from cells.legacy.models import surface_active_bath_epoch

        return surface_active_bath_epoch
    if isinstance(spec, passive_bath_epoch.SurfacePassiveBathEpochModel):
        from cells.legacy.models import surface_passive_bath_epoch

        return surface_passive_bath_epoch
    from cells.legacy.core import surface_active_bath_events_spec as active_bath
    from cells.legacy.core import surface_passive_bath_events_spec as passive_bath

    if isinstance(spec, active_bath.SurfaceActiveBathEventModel):
        from cells.legacy.models import surface_active_bath_events

        return surface_active_bath_events
    if isinstance(spec, passive_bath.SurfacePassiveBathEventModel):
        from cells.legacy.models import surface_passive_bath_events

        return surface_passive_bath_events
    from cells.legacy.core import (
        surface_calcium_energy_water_profile_barrier_epoch_spec as water_joint_epoch,
    )
    from cells.legacy.core import (
        surface_calcium_energy_water_repair_profile_barrier_epoch_spec as repair_joint_epoch,
    )

    if isinstance(spec, repair_joint_epoch.SurfaceCalciumEnergyWaterRepairProfileBarrierEpochModel):
        from cells.legacy.models import surface_calcium_energy_water_repair_profile_barrier_epoch

        return surface_calcium_energy_water_repair_profile_barrier_epoch
    if isinstance(spec, water_joint_epoch.SurfaceCalciumEnergyWaterProfileBarrierEpochModel):
        from cells.legacy.models import surface_calcium_energy_water_profile_barrier_epoch

        return surface_calcium_energy_water_profile_barrier_epoch
    from cells.legacy.core import (
        surface_calcium_energy_water_profile_barrier_interventions_spec as water_combined,
    )
    from cells.legacy.core import (
        surface_calcium_energy_water_repair_profile_barrier_interventions_spec as repair_combined,
    )

    if isinstance(
        spec, repair_combined.SurfaceCalciumEnergyWaterRepairProfileBarrierInterventionModel
    ):
        from cells.legacy.models import (
            surface_calcium_energy_water_repair_profile_barrier_interventions,
        )

        return surface_calcium_energy_water_repair_profile_barrier_interventions
    if isinstance(spec, water_combined.SurfaceCalciumEnergyWaterProfileBarrierInterventionModel):
        from cells.legacy.models import surface_calcium_energy_water_profile_barrier_interventions

        return surface_calcium_energy_water_profile_barrier_interventions
    from cells.legacy.core import (
        surface_calcium_energy_profile_barrier_epoch_spec as energy_combined_epoch,
    )
    from cells.legacy.core import (
        surface_calcium_profile_barrier_epoch_spec as calcium_combined_epoch,
    )

    if isinstance(spec, calcium_combined_epoch.SurfaceCalciumProfileBarrierEpochModel):
        from cells.legacy.models import surface_calcium_profile_barrier_epoch

        return surface_calcium_profile_barrier_epoch
    if isinstance(spec, energy_combined_epoch.SurfaceCalciumEnergyProfileBarrierEpochModel):
        from cells.legacy.models import surface_calcium_energy_profile_barrier_epoch

        return surface_calcium_energy_profile_barrier_epoch
    from cells.legacy.core import surface_active_profile_barrier_epoch_spec as combined_epoch

    if isinstance(spec, combined_epoch.SurfaceActiveProfileBarrierEpochModel):
        from cells.legacy.models import surface_active_profile_barrier_epoch

        return surface_active_profile_barrier_epoch
    from cells.legacy.core import (
        surface_calcium_energy_profile_barrier_interventions_spec as energy_combined,
    )
    from cells.legacy.core import (
        surface_calcium_profile_barrier_interventions_spec as calcium_combined,
    )

    if isinstance(spec, calcium_combined.SurfaceCalciumProfileBarrierInterventionModel):
        from cells.legacy.models import surface_calcium_profile_barrier_interventions

        return surface_calcium_profile_barrier_interventions
    if isinstance(spec, energy_combined.SurfaceCalciumEnergyProfileBarrierInterventionModel):
        from cells.legacy.models import surface_calcium_energy_profile_barrier_interventions

        return surface_calcium_energy_profile_barrier_interventions
    from cells.legacy.core import (
        surface_active_profile_barrier_interventions_spec as active_combined,
    )

    if isinstance(spec, active_combined.SurfaceActiveProfileBarrierInterventionModel):
        from cells.legacy.models import surface_active_profile_barrier_interventions

        return surface_active_profile_barrier_interventions
    from cells.legacy.core import (
        surface_calcium_energy_water_barrier_epoch_spec as water_barrier_epoch,
    )
    from cells.legacy.core import (
        surface_calcium_energy_water_repair_barrier_epoch_spec as repair_barrier_epoch,
    )

    if isinstance(spec, repair_barrier_epoch.SurfaceCalciumEnergyWaterRepairBarrierEpochModel):
        from cells.legacy.models import surface_calcium_energy_water_repair_barrier_epoch

        return surface_calcium_energy_water_repair_barrier_epoch
    if isinstance(spec, water_barrier_epoch.SurfaceCalciumEnergyWaterBarrierEpochModel):
        from cells.legacy.models import surface_calcium_energy_water_barrier_epoch

        return surface_calcium_energy_water_barrier_epoch
    from cells.legacy.core import (
        surface_calcium_energy_water_barrier_interventions_spec as water_barrier,
    )
    from cells.legacy.core import (
        surface_calcium_energy_water_repair_barrier_interventions_spec as repair_barrier,
    )

    if isinstance(spec, repair_barrier.SurfaceCalciumEnergyWaterRepairBarrierInterventionModel):
        from cells.legacy.models import surface_calcium_energy_water_repair_barrier_interventions

        return surface_calcium_energy_water_repair_barrier_interventions
    if isinstance(spec, water_barrier.SurfaceCalciumEnergyWaterBarrierInterventionModel):
        from cells.legacy.models import surface_calcium_energy_water_barrier_interventions

        return surface_calcium_energy_water_barrier_interventions
    from cells.legacy.core import surface_active_barrier_epoch_spec as active_ecm_epoch
    from cells.legacy.core import surface_calcium_barrier_epoch_spec as calcium_ecm_epoch
    from cells.legacy.core import surface_calcium_energy_barrier_epoch_spec as energy_ecm_epoch

    if isinstance(spec, active_ecm_epoch.SurfaceActiveBarrierEpochModel):
        from cells.legacy.models import surface_active_barrier_epoch

        return surface_active_barrier_epoch
    if isinstance(spec, calcium_ecm_epoch.SurfaceCalciumBarrierEpochModel):
        from cells.legacy.models import surface_calcium_barrier_epoch

        return surface_calcium_barrier_epoch
    if isinstance(spec, energy_ecm_epoch.SurfaceCalciumEnergyBarrierEpochModel):
        from cells.legacy.models import surface_calcium_energy_barrier_epoch

        return surface_calcium_energy_barrier_epoch
    from cells.legacy.core import surface_active_barrier_interventions_spec as active_barrier
    from cells.legacy.core import surface_calcium_barrier_interventions_spec as calcium_barrier
    from cells.legacy.core import (
        surface_calcium_energy_barrier_interventions_spec as energy_barrier,
    )

    if isinstance(spec, active_barrier.SurfaceActiveBarrierInterventionModel):
        from cells.legacy.models import surface_active_barrier_interventions

        return surface_active_barrier_interventions
    if isinstance(spec, calcium_barrier.SurfaceCalciumBarrierInterventionModel):
        from cells.legacy.models import surface_calcium_barrier_interventions

        return surface_calcium_barrier_interventions
    if isinstance(spec, energy_barrier.SurfaceCalciumEnergyBarrierInterventionModel):
        from cells.legacy.models import surface_calcium_energy_barrier_interventions

        return surface_calcium_energy_barrier_interventions
    from cells.legacy.core.surface_calcium_energy_water_profile_epoch_spec import (
        SurfaceCalciumEnergyWaterProfileEpochModel,
    )
    from cells.legacy.core.surface_calcium_energy_water_repair_profile_epoch_spec import (
        SurfaceCalciumEnergyWaterRepairProfileEpochModel,
    )

    if isinstance(spec, SurfaceCalciumEnergyWaterRepairProfileEpochModel):
        from cells.legacy.models import surface_calcium_energy_water_repair_profile_epoch

        return surface_calcium_energy_water_repair_profile_epoch
    if isinstance(spec, SurfaceCalciumEnergyWaterProfileEpochModel):
        from cells.legacy.models import surface_calcium_energy_water_profile_epoch

        return surface_calcium_energy_water_profile_epoch
    from cells.legacy.core.surface_calcium_energy_water_profile_interventions_spec import (
        SurfaceCalciumEnergyWaterProfileInterventionModel,
    )
    from cells.legacy.core.surface_calcium_energy_water_repair_profile_interventions_spec import (
        SurfaceCalciumEnergyWaterRepairProfileInterventionModel,
    )

    if isinstance(spec, SurfaceCalciumEnergyWaterRepairProfileInterventionModel):
        from cells.legacy.models import surface_calcium_energy_water_repair_profile_interventions

        return surface_calcium_energy_water_repair_profile_interventions
    if isinstance(spec, SurfaceCalciumEnergyWaterProfileInterventionModel):
        from cells.legacy.models import surface_calcium_energy_water_profile_interventions

        return surface_calcium_energy_water_profile_interventions
    from cells.legacy.core.surface_calcium_energy_profile_epoch_spec import (
        SurfaceCalciumEnergyProfileEpochModel,
    )
    from cells.legacy.core.surface_calcium_profile_epoch_spec import SurfaceCalciumProfileEpochModel

    if isinstance(spec, SurfaceCalciumEnergyProfileEpochModel):
        from cells.legacy.models import surface_calcium_energy_profile_epoch

        return surface_calcium_energy_profile_epoch
    if isinstance(spec, SurfaceCalciumProfileEpochModel):
        from cells.legacy.models import surface_calcium_profile_epoch

        return surface_calcium_profile_epoch
    from cells.legacy.core.surface_calcium_energy_profile_interventions_spec import (
        SurfaceCalciumEnergyProfileInterventionModel,
    )
    from cells.legacy.core.surface_calcium_profile_interventions_spec import (
        SurfaceCalciumProfileInterventionModel,
    )

    if isinstance(spec, SurfaceCalciumEnergyProfileInterventionModel):
        from cells.legacy.models import surface_calcium_energy_profile_interventions

        return surface_calcium_energy_profile_interventions
    if isinstance(spec, SurfaceCalciumProfileInterventionModel):
        from cells.legacy.models import surface_calcium_profile_interventions

        return surface_calcium_profile_interventions
    from cells.legacy.core.surface_active_profile_epoch_spec import SurfaceActiveProfileEpochModel

    if isinstance(spec, SurfaceActiveProfileEpochModel):
        from cells.legacy.models import surface_active_profile_epoch

        return surface_active_profile_epoch
    from cells.legacy.core.surface_active_profile_interventions_spec import (
        SurfaceActiveProfileInterventionModel,
    )

    if isinstance(spec, SurfaceActiveProfileInterventionModel):
        from cells.legacy.models import surface_active_profile_interventions

        return surface_active_profile_interventions
    if isinstance(spec, SurfaceCotransportWaterModel):
        from cells.legacy.models import surface_cotransport_water

        return surface_cotransport_water
    if isinstance(spec, SurfaceCotransportModel):
        from cells.legacy.models import surface_cotransport

        return surface_cotransport
    if isinstance(spec, SurfaceEnergyWaterMorrisLecarModel):
        from cells.legacy.models import surface_energy_water_morris_lecar

        return surface_energy_water_morris_lecar
    if isinstance(spec, SurfaceEnergyWaterModel):
        from cells.legacy.models import surface_energy_water

        return surface_energy_water
    if isinstance(spec, SurfaceEnergyMorrisLecarModel):
        from cells.legacy.models import surface_energy_morris_lecar

        return surface_energy_morris_lecar
    if isinstance(spec, SurfaceEnergyModel):
        from cells.legacy.models import surface_energy

        return surface_energy
    if isinstance(spec, SurfaceWaterMorrisLecarModel):
        from cells.legacy.models import surface_water_morris_lecar

        return surface_water_morris_lecar
    if isinstance(spec, SurfaceWaterKineticModel):
        return surface_water_kinetic
    if isinstance(spec, SurfaceWaterModel):
        return surface_water
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
        from cells.legacy.models import surface_repair_morris_lecar

        return surface_repair_morris_lecar
    if isinstance(spec, SurfaceRepairModel):
        return surface_repair
    from cells.legacy.core.surface_calcium_energy_water_hcn_extra_spec import (
        SurfaceCalciumEnergyWaterHCNExtraModel,
    )
    from cells.legacy.core.surface_calcium_energy_water_repair_hcn_extra_spec import (
        SurfaceCalciumEnergyWaterRepairHCNExtraModel,
    )

    if isinstance(spec, SurfaceCalciumEnergyWaterRepairHCNExtraModel):
        from cells.legacy.models import surface_calcium_energy_water_repair_hcn_extra

        return surface_calcium_energy_water_repair_hcn_extra
    if isinstance(spec, SurfaceCalciumEnergyWaterHCNExtraModel):
        from cells.legacy.models import surface_calcium_energy_water_hcn_extra

        return surface_calcium_energy_water_hcn_extra
    if isinstance(spec, SurfaceCalciumEnergyWaterRepairModel):
        from cells.legacy.models import surface_calcium_energy_water_repair

        return surface_calcium_energy_water_repair
    from cells.legacy.core.surface_calcium_energy_water_excision_spec import (
        SurfaceCalciumEnergyWaterExcisionModel,
    )

    if isinstance(spec, SurfaceCalciumEnergyWaterExcisionModel):
        from cells.legacy.models import surface_calcium_energy_water_excision

        return surface_calcium_energy_water_excision
    if isinstance(spec, SurfaceCalciumEnergyWaterModel):
        from cells.legacy.models import surface_calcium_energy_water

        return surface_calcium_energy_water
    from cells.legacy.core.surface_calcium_energy_mitochondria_excision_spec import (
        SurfaceCalciumEnergyMitochondriaExcisionModel,
    )

    if isinstance(spec, SurfaceCalciumEnergyMitochondriaExcisionModel):
        from cells.legacy.models import surface_calcium_energy_mitochondria_excision

        return surface_calcium_energy_mitochondria_excision
    from cells.legacy.core.surface_calcium_energy_mitochondria_spec import (
        SurfaceCalciumEnergyMitochondriaModel,
    )
    from cells.legacy.core.surface_calcium_energy_transport_spec import (
        SurfaceCalciumEnergyTransportModel,
    )

    if isinstance(spec, SurfaceCalciumEnergyMitochondriaModel):
        from cells.legacy.models import surface_calcium_energy_mitochondria

        return surface_calcium_energy_mitochondria

    from cells.legacy.core.surface_calcium_energy_transport_excision_spec import (
        SurfaceCalciumEnergyTransportExcisionModel,
    )

    if isinstance(spec, SurfaceCalciumEnergyTransportExcisionModel):
        from cells.legacy.models import surface_calcium_energy_transport_excision

        return surface_calcium_energy_transport_excision

    from cells.legacy.core.surface_calcium_energy_irreversible_transport_excision_spec import (
        SurfaceCalciumEnergyIrreversibleTransportExcisionModel,
    )

    if isinstance(spec, SurfaceCalciumEnergyIrreversibleTransportExcisionModel):
        from cells.legacy.models import surface_calcium_energy_irreversible_transport_excision

        return surface_calcium_energy_irreversible_transport_excision

    from cells.legacy.core.surface_calcium_energy_irreversible_transport_spec import (
        SurfaceCalciumEnergyIrreversibleTransportModel,
    )

    if isinstance(spec, SurfaceCalciumEnergyIrreversibleTransportModel):
        from cells.legacy.models import surface_calcium_energy_irreversible_transport

        return surface_calcium_energy_irreversible_transport

    from cells.legacy.core.surface_calcium_energy_atp_transport_excision_spec import (
        SurfaceCalciumEnergyATPTransportExcisionModel,
    )

    if isinstance(spec, SurfaceCalciumEnergyATPTransportExcisionModel):
        from cells.legacy.models import surface_calcium_energy_atp_transport_excision

        return surface_calcium_energy_atp_transport_excision

    from cells.legacy.core.surface_calcium_energy_atp_transport_spec import (
        SurfaceCalciumEnergyATPTransportModel,
    )

    if isinstance(spec, SurfaceCalciumEnergyATPTransportModel):
        from cells.legacy.models import surface_calcium_energy_atp_transport

        return surface_calcium_energy_atp_transport

    if isinstance(spec, SurfaceCalciumEnergyTransportModel):
        from cells.legacy.models import surface_calcium_energy_transport

        return surface_calcium_energy_transport
    from cells.legacy.core.surface_calcium_energy_excision_spec import (
        SurfaceCalciumEnergyExcisionModel,
    )

    if isinstance(spec, SurfaceCalciumEnergyExcisionModel):
        from cells.legacy.models import surface_calcium_energy_excision

        return surface_calcium_energy_excision
    from cells.legacy.core.surface_calcium_energy_regulated_spec import (
        SurfaceCalciumEnergyRegulatedModel,
    )
    from cells.legacy.core.surface_calcium_energy_regulated_v2_spec import (
        SurfaceCalciumEnergyRegulatedV2Model,
    )

    if isinstance(spec, SurfaceCalciumEnergyRegulatedModel):
        from cells.legacy.models import surface_calcium_energy_regulated

        return surface_calcium_energy_regulated
    from cells.legacy.core.surface_calcium_energy_regulated_v2_excision_spec import (
        SurfaceCalciumEnergyRegulatedV2ExcisionModel,
    )

    if isinstance(spec, SurfaceCalciumEnergyRegulatedV2ExcisionModel):
        from cells.legacy.models import surface_calcium_energy_regulated_v2_excision

        return surface_calcium_energy_regulated_v2_excision
    if isinstance(spec, SurfaceCalciumEnergyRegulatedV2Model):
        from cells.legacy.models import surface_calcium_energy_regulated_v2

        return surface_calcium_energy_regulated_v2
    if isinstance(spec, SurfaceCalciumEnergyHCNExtraModel):
        from cells.legacy.models import surface_calcium_energy_hcn_extra

        return surface_calcium_energy_hcn_extra
    if isinstance(spec, SurfaceCalciumEnergyMorrisLecarModel):
        from cells.legacy.models import surface_calcium_energy_morris_lecar

        return surface_calcium_energy_morris_lecar
    if isinstance(spec, SurfaceCalciumEnergyActivatedModel):
        from cells.legacy.models import surface_calcium_energy_activated

        return surface_calcium_energy_activated
    if isinstance(spec, SurfaceCalciumEnergyCatalogModel):
        from cells.legacy.models import surface_calcium_energy_catalog

        return surface_calcium_energy_catalog
    if isinstance(spec, SurfaceCalciumEnergyModel):
        from cells.legacy.models import surface_calcium_energy

        return surface_calcium_energy
    if isinstance(spec, SurfaceCalciumWaterModel):
        from cells.legacy.models import surface_calcium_water

        return surface_calcium_water
    from cells.legacy.core.surface_calcium_excision_spec import SurfaceCalciumExcisionModel

    if isinstance(spec, SurfaceCalciumExcisionModel):
        from cells.legacy.models import surface_calcium_excision

        return surface_calcium_excision
    if isinstance(spec, SurfaceCalciumHCNExtraModel):
        from cells.legacy.models import surface_calcium_hcn_extra

        return surface_calcium_hcn_extra
    if isinstance(spec, SurfaceCalciumMorrisLecarModel):
        from cells.legacy.models import surface_calcium_morris_lecar

        return surface_calcium_morris_lecar
    if isinstance(spec, SurfaceCalciumActivatedCatalogModel):
        from cells.legacy.models import surface_calcium_activated_catalog

        return surface_calcium_activated_catalog
    if isinstance(spec, SurfaceCalciumExtendedCatalogModel):
        from cells.legacy.models import surface_calcium_catalog_v2

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
    from cells.legacy.core.surface_active_excision_spec import SurfaceActiveExcisionModel

    if isinstance(spec, SurfaceActiveExcisionModel):
        from cells.legacy.models import surface_active_excision

        return surface_active_excision
    if isinstance(spec, SurfaceHCNExtraModel):
        from cells.legacy.models import surface_hcn_extra

        return surface_hcn_extra
    if isinstance(spec, SurfaceMorrisLecarModel):
        from cells.legacy.models import surface_morris_lecar

        return surface_morris_lecar
    if isinstance(spec, SurfaceCalciumActivatedModel):
        from cells.legacy.models import surface_calcium_activated

        return surface_calcium_activated
    if isinstance(spec, SurfaceExtendedCatalogModel):
        from cells.legacy.models import surface_catalog_v2

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
    from cells.legacy.core.surface_excision_spec import SurfaceExcisionModel

    if isinstance(spec, SurfaceExcisionModel):
        from cells.legacy.models import surface_excision

        return surface_excision
    from cells.legacy.core.surface_profile_epoch_spec import SurfaceProfileEpochModel

    if isinstance(spec, SurfaceProfileEpochModel):
        from cells.legacy.models import surface_profile_epoch

        return surface_profile_epoch
    from cells.legacy.core.surface_profile_interventions_spec import SurfaceProfileInterventionModel

    if isinstance(spec, SurfaceProfileInterventionModel):
        from cells.legacy.models import surface_profile_interventions

        return surface_profile_interventions
    from cells.legacy.core.environment_barrier_interventions_spec import EnvironmentBarrierModel

    if isinstance(spec, EnvironmentBarrierModel):
        from cells.legacy.models import environment_barrier_interventions

        return environment_barrier_interventions
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
    return None


def parse(data):
    """`parse_spec`'s older families by model ID, in its order: the parsed definition (None when
    none matches). The projective pre-check, the active families and the inline definitions
    (source_decay@1, emt_mirna@1, passive_pair@1, reaction_transport@1) stay in definitions/specs.py."""  # noqa: E501
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_open_calcium_bath_epoch@1"
    ):
        from cells.legacy.core.surface_open_calcium_bath_epoch_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_open_calcium_energy_bath_epoch@1"
    ):
        from cells.legacy.core.surface_open_calcium_energy_bath_epoch_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_open_calcium_bath_events@1"
    ):
        from cells.legacy.core.surface_open_calcium_bath_events_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_open_calcium_energy_bath_events@1"
    ):
        from cells.legacy.core.surface_open_calcium_energy_bath_events_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "resolved_open_calcium@1":
        from cells.legacy.core.surface_open_calcium_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_open_calcium_energy@1"
    ):
        from cells.legacy.core.surface_open_calcium_energy_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_passive_bath_epoch@1"
    ):
        from cells.legacy.core.surface_passive_bath_epoch_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_active_bath_epoch@1"
    ):
        from cells.legacy.core.surface_active_bath_epoch_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_passive_bath_events@1"
    ):
        from cells.legacy.core.surface_passive_bath_events_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_active_bath_events@1"
    ):
        from cells.legacy.core.surface_active_bath_events_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_water_membrane_profile_epoch@1"
    ):
        from cells.legacy.core.surface_calcium_energy_water_profile_epoch_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id")
        == "resolved_calcium_energy_water_repair_membrane_profile_epoch@1"
    ):
        from cells.legacy.core.surface_calcium_energy_water_repair_profile_epoch_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_water_repair_membrane_profiles@1"
    ):
        from cells.legacy.core.surface_calcium_energy_water_repair_profile_interventions_spec import (  # noqa: E501
            parse,
        )

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_water_membrane_profiles@1"
    ):
        from cells.legacy.core.surface_calcium_energy_water_profile_interventions_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_membrane_profile_epoch@1"
    ):
        from cells.legacy.core.surface_calcium_profile_epoch_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_membrane_profile_epoch@1"
    ):
        from cells.legacy.core.surface_calcium_energy_profile_epoch_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_membrane_profiles@1"
    ):
        from cells.legacy.core.surface_calcium_profile_interventions_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_membrane_profiles@1"
    ):
        from cells.legacy.core.surface_calcium_energy_profile_interventions_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_active_membrane_profile_epoch@1"
    ):
        from cells.legacy.core.surface_active_profile_epoch_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_active_membrane_profiles@1"
    ):
        from cells.legacy.core.surface_active_profile_interventions_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "resolved_redistribution@3":
        from cells.legacy.core.surface_mobile_channel_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "resolved_redistribution@2":
        from cells.legacy.core.surface_mobile_pump_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "resolved_redistribution@1":
        from cells.legacy.core.surface_redistribution_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "resolved_repair@3":
        from cells.legacy.core.surface_mobile_pump_repair_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "resolved_repair@2":
        from cells.legacy.core.surface_mobile_repair_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") in (
        "resolved_repair@1",
        "resolved_repair@4",
    ):
        from cells.legacy.core.surface_repair_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_mitochondria_excision@1"
    ):
        from cells.legacy.core.surface_calcium_energy_mitochondria_excision_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_mitochondria@1"
    ):
        from cells.legacy.core.surface_calcium_energy_mitochondria_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_transport_excision@1"
    ):
        from cells.legacy.core.surface_calcium_energy_transport_excision_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_irreversible_transport_excision@1"
    ):
        from cells.legacy.core.surface_calcium_energy_irreversible_transport_excision_spec import (
            parse,
        )

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_irreversible_transport@1"
    ):
        from cells.legacy.core.surface_calcium_energy_irreversible_transport_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_atp_transport_excision@1"
    ):
        from cells.legacy.core.surface_calcium_energy_atp_transport_excision_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_atp_transport@1"
    ):
        from cells.legacy.core.surface_calcium_energy_atp_transport_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_transport@1"
    ):
        from cells.legacy.core.surface_calcium_energy_transport_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_regulated@1"
    ):
        from cells.legacy.core.surface_calcium_energy_regulated_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_regulated_excision@1"
    ):
        from cells.legacy.core.surface_calcium_energy_regulated_v2_excision_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_regulated@2"
    ):
        from cells.legacy.core.surface_calcium_energy_regulated_v2_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") in (
        "resolved_calcium_energy@1",
        "resolved_calcium_energy@2",
        "resolved_calcium_energy@3",
        "resolved_calcium_energy@4",
        "resolved_calcium_energy@5",
    ):
        from cells.legacy.core.surface_calcium_energy_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_water_repair@2"
    ):
        from cells.legacy.core.surface_calcium_energy_water_repair_hcn_extra_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_water@2"
    ):
        from cells.legacy.core.surface_calcium_energy_water_hcn_extra_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_water_repair@1"
    ):
        from cells.legacy.core.surface_calcium_energy_water_repair_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_water_excision@1"
    ):
        from cells.legacy.core.surface_calcium_energy_water_excision_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_water@1"
    ):
        from cells.legacy.core.surface_calcium_energy_water_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "resolved_calcium_water@1":
        from cells.legacy.core.surface_calcium_water_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") in (
        "resolved_calcium@1",
        "resolved_calcium@2",
        "resolved_calcium@3",
        "resolved_calcium@4",
        "resolved_calcium@5",
        "resolved_calcium@6",
        "resolved_calcium@7",
        "resolved_calcium@8",
        "resolved_calcium@9",
        "resolved_calcium@10",
        "resolved_calcium@11",
    ):
        from cells.legacy.core.surface_calcium_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") in (
        "resolved_tissue@2",
        "resolved_tissue@3",
        "resolved_tissue@4",
        "resolved_tissue@5",
        "resolved_tissue@6",
        "resolved_tissue@7",
        "resolved_tissue@8",
        "resolved_tissue@9",
        "resolved_tissue@10",
        "resolved_tissue@11",
        "resolved_tissue@12",
    ):
        from cells.definitions.surface_kinetic_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") in (
        "resolved_water@2",
        "resolved_water@3",
    ):
        from cells.legacy.core.surface_water_kinetic_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_cotransport_water@1"
    ):
        from cells.legacy.core.surface_cotransport_water_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "resolved_cotransport@1":
        from cells.legacy.core.surface_cotransport_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") in (
        "resolved_energy_water@1",
        "resolved_energy_water@2",
    ):
        from cells.legacy.core.surface_energy_water_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") in (
        "resolved_energy@1",
        "resolved_energy@2",
    ):
        from cells.legacy.core.surface_energy_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "resolved_water@1":
        from cells.legacy.core.surface_water_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_excision@1"
    ):
        from cells.legacy.core.surface_calcium_energy_excision_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "resolved_calcium_excision@1":
        from cells.legacy.core.surface_calcium_excision_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_tissue_active_excision@1"
    ):
        from cells.legacy.core.surface_active_excision_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "resolved_tissue_excision@1":
        from cells.legacy.core.surface_excision_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_membrane_profile_epoch@1"
    ):
        from cells.legacy.core.surface_profile_epoch_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_membrane_profiles@1"
    ):
        from cells.legacy.core.surface_profile_interventions_spec import parse

        return parse(data)
    if (
        isinstance(data.get("model"), dict)
        and data["model"].get("id") == "resolved_calcium_energy_water_profile_barrier_epoch@1"
    ):
        from cells.legacy.core.surface_calcium_energy_water_profile_barrier_epoch_spec import parse

        return parse(data)
    if (
        isinstance(data.get("model"), dict)
        and data["model"].get("id")
        == "resolved_calcium_energy_water_repair_profile_barrier_epoch@1"
    ):
        from cells.legacy.core.surface_calcium_energy_water_repair_profile_barrier_epoch_spec import (  # noqa: E501
            parse,
        )

        return parse(data)
    if (
        isinstance(data.get("model"), dict)
        and data["model"].get("id") == "resolved_calcium_energy_water_profile_barriers@1"
    ):
        from cells.legacy.core.surface_calcium_energy_water_profile_barrier_interventions_spec import (  # noqa: E501
            parse,
        )

        return parse(data)
    if (
        isinstance(data.get("model"), dict)
        and data["model"].get("id") == "resolved_calcium_energy_water_repair_profile_barriers@1"
    ):
        from cells.legacy.core import (
            surface_calcium_energy_water_repair_profile_barrier_interventions_spec as repair_joint,
        )

        return repair_joint.parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_profile_barrier_epoch@1"
    ):
        from cells.legacy.core.surface_calcium_profile_barrier_epoch_spec import parse

        return parse(data)
    if (
        isinstance(data.get("model"), dict)
        and data["model"].get("id") == "resolved_calcium_energy_profile_barrier_epoch@1"
    ):
        from cells.legacy.core.surface_calcium_energy_profile_barrier_epoch_spec import parse

        return parse(data)
    if (
        isinstance(data.get("model"), dict)
        and data["model"].get("id") == "resolved_active_profile_barrier_epoch@1"
    ):
        from cells.legacy.core.surface_active_profile_barrier_epoch_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_profile_barriers@1"
    ):
        from cells.legacy.core.surface_calcium_profile_barrier_interventions_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_profile_barriers@1"
    ):
        from cells.legacy.core.surface_calcium_energy_profile_barrier_interventions_spec import (
            parse,
        )

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_active_profile_barriers@1"
    ):
        from cells.legacy.core.surface_active_profile_barrier_interventions_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_water_extracellular_barrier_epoch@1"
    ):
        from cells.legacy.core.surface_calcium_energy_water_barrier_epoch_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id")
        == "resolved_calcium_energy_water_repair_extracellular_barrier_epoch@1"
    ):
        from cells.legacy.core.surface_calcium_energy_water_repair_barrier_epoch_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_water_extracellular_barriers@1"
    ):
        from cells.legacy.core.surface_calcium_energy_water_barrier_interventions_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id")
        == "resolved_calcium_energy_water_repair_extracellular_barriers@1"
    ):
        from cells.legacy.core.surface_calcium_energy_water_repair_barrier_interventions_spec import (  # noqa: E501
            parse,
        )

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_active_extracellular_barrier_epoch@1"
    ):
        from cells.legacy.core.surface_active_barrier_epoch_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_extracellular_barrier_epoch@1"
    ):
        from cells.legacy.core.surface_calcium_barrier_epoch_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_extracellular_barrier_epoch@1"
    ):
        from cells.legacy.core.surface_calcium_energy_barrier_epoch_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_active_extracellular_barriers@1"
    ):
        from cells.legacy.core.surface_active_barrier_interventions_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_extracellular_barriers@1"
    ):
        from cells.legacy.core.surface_calcium_barrier_interventions_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_calcium_energy_extracellular_barriers@1"
    ):
        from cells.legacy.core.surface_calcium_energy_barrier_interventions_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == "resolved_extracellular_barriers@1"
    ):
        from cells.legacy.core.environment_barrier_interventions_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "resolved_tissue@1":
        from cells.definitions.surface_tissue_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "spatial_calcium@5":
        from cells.legacy.core.tissue_calcium_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "spatial_extracellular@3":
        from cells.legacy.core.tissue_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "spatial_calcium@4":
        from cells.legacy.core.ip3_calcium_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "spatial_calcium@3":
        from cells.legacy.core.gated_calcium_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "spatial_calcium@2":
        from cells.legacy.core.plasma_calcium_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "spatial_calcium@1":
        from cells.legacy.core.spatial_calcium_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "er_calcium@1":
        from cells.legacy.core.er_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "compartment_reactions@1":
        from cells.legacy.core.reaction_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == SPATIAL_JUNCTION_ID:
        from cells.legacy.core.spatial_junction_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == JUNCTION_FINITE_EXTRACELLULAR_ID
    ):
        from cells.legacy.core.junction_finite_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == KINETIC_FINITE_EXTRACELLULAR_ID
    ):
        from cells.legacy.core.kinetic_finite_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == SPATIAL_EXTRACELLULAR_ID:
        from cells.legacy.core.spatial_extracellular_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == FINITE_EXTRACELLULAR_ID:
        from cells.legacy.core.finite_extracellular_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == PHYSICAL_IONIC_GRAPH_ID:
        from cells.legacy.core.physical_ionic_graph_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == VOLTAGE_GATED_ID:
        from cells.legacy.core.voltage_gated_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == MULTISPECIES_ID:
        from cells.legacy.core.multispecies_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == SOURCE_PAIR_ID:
        from cells.legacy.core.source_pair_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == BIOELECTRIC_PAIR_ID:
        from cells.legacy.core.bioelectric_pair_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == BIOELECTRIC_ID:
        from cells.legacy.core.bioelectric_spec import parse

        return parse(data)
    return None


def to_dict(self):
    """`SimulationSpec._fine_dict`'s older families, in its order, for the spec `self`: its
    definition dict (None when none matches). The two refusals that stood among these entries
    (multispecies execution settings, an experiment type other than ExperimentSpec) stay here,
    at their places, so they also hold for the inline definitions the core serializes after."""
    m, e, x = self.model, self.experiment, self.execution
    from cells.legacy.core import surface_open_calcium_bath_epoch_spec as calcium_bath_epoch
    from cells.legacy.core import surface_open_calcium_energy_bath_epoch_spec as energy_bath_epoch

    if isinstance(m, energy_bath_epoch.SurfaceOpenCalciumEnergyBathEpochModel):
        return energy_bath_epoch.to_dict(self)
    if isinstance(m, calcium_bath_epoch.SurfaceOpenCalciumBathEpochModel):
        return calcium_bath_epoch.to_dict(self)
    from cells.legacy.core import surface_open_calcium_bath_events_spec as calcium_bath
    from cells.legacy.core import surface_open_calcium_energy_bath_events_spec as energy_bath

    if isinstance(m, energy_bath.SurfaceOpenCalciumEnergyBathEventModel):
        return energy_bath.to_dict(self)
    if isinstance(m, calcium_bath.SurfaceOpenCalciumBathEventModel):
        return calcium_bath.to_dict(self)
    from cells.legacy.core import surface_open_calcium_energy_spec as open_energy
    from cells.legacy.core import surface_open_calcium_spec as open_calcium

    if isinstance(m, open_energy.SurfaceOpenCalciumEnergyModel):
        return open_energy.to_dict(self)
    if isinstance(m, open_calcium.SurfaceOpenCalciumModel):
        return open_calcium.to_dict(self)
    from cells.legacy.core import surface_active_bath_epoch_spec as active_bath_epoch
    from cells.legacy.core import surface_passive_bath_epoch_spec as passive_bath_epoch

    if isinstance(m, active_bath_epoch.SurfaceActiveBathEpochModel):
        return active_bath_epoch.to_dict(self)
    if isinstance(m, passive_bath_epoch.SurfacePassiveBathEpochModel):
        return passive_bath_epoch.to_dict(self)
    from cells.legacy.core import surface_active_bath_events_spec as active_bath
    from cells.legacy.core import surface_passive_bath_events_spec as passive_bath

    if isinstance(m, active_bath.SurfaceActiveBathEventModel):
        return active_bath.to_dict(self)
    if isinstance(m, passive_bath.SurfacePassiveBathEventModel):
        return passive_bath.to_dict(self)
    from cells.legacy.core import (
        surface_calcium_energy_water_profile_barrier_epoch_spec as water_joint_epoch,
    )
    from cells.legacy.core import (
        surface_calcium_energy_water_repair_profile_barrier_epoch_spec as repair_joint_epoch,
    )

    if isinstance(m, repair_joint_epoch.SurfaceCalciumEnergyWaterRepairProfileBarrierEpochModel):
        return repair_joint_epoch.to_dict(self)
    if isinstance(m, water_joint_epoch.SurfaceCalciumEnergyWaterProfileBarrierEpochModel):
        return water_joint_epoch.to_dict(self)
    from cells.legacy.core import (
        surface_calcium_energy_water_profile_barrier_interventions_spec as water_combined,
    )
    from cells.legacy.core import (
        surface_calcium_energy_water_repair_profile_barrier_interventions_spec as repair_joint,
    )

    if isinstance(m, repair_joint.SurfaceCalciumEnergyWaterRepairProfileBarrierInterventionModel):
        return repair_joint.to_dict(self)
    if isinstance(m, water_combined.SurfaceCalciumEnergyWaterProfileBarrierInterventionModel):
        return water_combined.to_dict(self)
    from cells.legacy.core import (
        surface_calcium_energy_profile_barrier_epoch_spec as energy_combined_epoch,
    )
    from cells.legacy.core import (
        surface_calcium_profile_barrier_epoch_spec as calcium_combined_epoch,
    )

    if isinstance(m, calcium_combined_epoch.SurfaceCalciumProfileBarrierEpochModel):
        return calcium_combined_epoch.to_dict(self)
    if isinstance(m, energy_combined_epoch.SurfaceCalciumEnergyProfileBarrierEpochModel):
        return energy_combined_epoch.to_dict(self)
    from cells.legacy.core import surface_active_profile_barrier_epoch_spec as combined_epoch

    if isinstance(m, combined_epoch.SurfaceActiveProfileBarrierEpochModel):
        return combined_epoch.to_dict(self)
    from cells.legacy.core import (
        surface_calcium_energy_profile_barrier_interventions_spec as energy_combined,
    )
    from cells.legacy.core import (
        surface_calcium_profile_barrier_interventions_spec as calcium_combined,
    )

    if isinstance(m, calcium_combined.SurfaceCalciumProfileBarrierInterventionModel):
        return calcium_combined.to_dict(self)
    if isinstance(m, energy_combined.SurfaceCalciumEnergyProfileBarrierInterventionModel):
        return energy_combined.to_dict(self)
    from cells.legacy.core import (
        surface_active_profile_barrier_interventions_spec as active_combined,
    )

    if isinstance(m, active_combined.SurfaceActiveProfileBarrierInterventionModel):
        return active_combined.to_dict(self)
    from cells.legacy.core import (
        surface_calcium_energy_water_barrier_epoch_spec as water_barrier_epoch,
    )
    from cells.legacy.core import (
        surface_calcium_energy_water_repair_barrier_epoch_spec as repair_barrier_epoch,
    )

    if isinstance(m, repair_barrier_epoch.SurfaceCalciumEnergyWaterRepairBarrierEpochModel):
        return repair_barrier_epoch.to_dict(self)
    if isinstance(m, water_barrier_epoch.SurfaceCalciumEnergyWaterBarrierEpochModel):
        return water_barrier_epoch.to_dict(self)
    from cells.legacy.core import (
        surface_calcium_energy_water_barrier_interventions_spec as water_barrier,
    )
    from cells.legacy.core import (
        surface_calcium_energy_water_repair_barrier_interventions_spec as repair_barrier,
    )

    if isinstance(m, repair_barrier.SurfaceCalciumEnergyWaterRepairBarrierInterventionModel):
        return repair_barrier.to_dict(self)
    if isinstance(m, water_barrier.SurfaceCalciumEnergyWaterBarrierInterventionModel):
        return water_barrier.to_dict(self)
    from cells.legacy.core import surface_active_barrier_epoch_spec as active_ecm_epoch
    from cells.legacy.core import surface_calcium_barrier_epoch_spec as calcium_ecm_epoch
    from cells.legacy.core import surface_calcium_energy_barrier_epoch_spec as energy_ecm_epoch

    if isinstance(m, active_ecm_epoch.SurfaceActiveBarrierEpochModel):
        return active_ecm_epoch.to_dict(self)
    if isinstance(m, calcium_ecm_epoch.SurfaceCalciumBarrierEpochModel):
        return calcium_ecm_epoch.to_dict(self)
    if isinstance(m, energy_ecm_epoch.SurfaceCalciumEnergyBarrierEpochModel):
        return energy_ecm_epoch.to_dict(self)
    from cells.legacy.core import surface_active_barrier_interventions_spec as active_barrier
    from cells.legacy.core import surface_calcium_barrier_interventions_spec as calcium_barrier
    from cells.legacy.core import (
        surface_calcium_energy_barrier_interventions_spec as energy_barrier,
    )

    if isinstance(m, active_barrier.SurfaceActiveBarrierInterventionModel):
        return active_barrier.to_dict(self)
    if isinstance(m, calcium_barrier.SurfaceCalciumBarrierInterventionModel):
        return calcium_barrier.to_dict(self)
    if isinstance(m, energy_barrier.SurfaceCalciumEnergyBarrierInterventionModel):
        return energy_barrier.to_dict(self)
    from cells.legacy.core.surface_calcium_energy_water_profile_epoch_spec import (
        SurfaceCalciumEnergyWaterProfileEpochModel,
    )
    from cells.legacy.core.surface_calcium_energy_water_profile_epoch_spec import (
        to_dict as joint_water_epoch_dict,
    )
    from cells.legacy.core.surface_calcium_energy_water_repair_profile_epoch_spec import (
        SurfaceCalciumEnergyWaterRepairProfileEpochModel,
    )
    from cells.legacy.core.surface_calcium_energy_water_repair_profile_epoch_spec import (
        to_dict as joint_repair_epoch_dict,
    )

    if isinstance(m, SurfaceCalciumEnergyWaterRepairProfileEpochModel):
        return joint_repair_epoch_dict(self)
    if isinstance(m, SurfaceCalciumEnergyWaterProfileEpochModel):
        return joint_water_epoch_dict(self)
    from cells.legacy.core.surface_calcium_energy_water_profile_interventions_spec import (
        SurfaceCalciumEnergyWaterProfileInterventionModel,
    )
    from cells.legacy.core.surface_calcium_energy_water_profile_interventions_spec import (
        to_dict as joint_water_profiles_dict,
    )
    from cells.legacy.core.surface_calcium_energy_water_repair_profile_interventions_spec import (
        SurfaceCalciumEnergyWaterRepairProfileInterventionModel,
    )
    from cells.legacy.core.surface_calcium_energy_water_repair_profile_interventions_spec import (
        to_dict as joint_repair_profiles_dict,
    )

    if isinstance(m, SurfaceCalciumEnergyWaterRepairProfileInterventionModel):
        return joint_repair_profiles_dict(self)
    if isinstance(m, SurfaceCalciumEnergyWaterProfileInterventionModel):
        return joint_water_profiles_dict(self)
    from cells.legacy.core.surface_calcium_energy_profile_epoch_spec import (
        SurfaceCalciumEnergyProfileEpochModel,
    )
    from cells.legacy.core.surface_calcium_energy_profile_epoch_spec import (
        to_dict as calcium_energy_epoch_dict,
    )
    from cells.legacy.core.surface_calcium_profile_epoch_spec import SurfaceCalciumProfileEpochModel
    from cells.legacy.core.surface_calcium_profile_epoch_spec import to_dict as calcium_epoch_dict

    if isinstance(m, SurfaceCalciumEnergyProfileEpochModel):
        return calcium_energy_epoch_dict(self)
    if isinstance(m, SurfaceCalciumProfileEpochModel):
        return calcium_epoch_dict(self)
    from cells.legacy.core.surface_calcium_energy_profile_interventions_spec import (
        SurfaceCalciumEnergyProfileInterventionModel,
    )
    from cells.legacy.core.surface_calcium_energy_profile_interventions_spec import (
        to_dict as calcium_energy_profiles_dict,
    )
    from cells.legacy.core.surface_calcium_profile_interventions_spec import (
        SurfaceCalciumProfileInterventionModel,
    )
    from cells.legacy.core.surface_calcium_profile_interventions_spec import (
        to_dict as calcium_profiles_dict,
    )

    if isinstance(m, SurfaceCalciumEnergyProfileInterventionModel):
        return calcium_energy_profiles_dict(self)
    if isinstance(m, SurfaceCalciumProfileInterventionModel):
        return calcium_profiles_dict(self)
    from cells.legacy.core.surface_active_profile_epoch_spec import (
        SurfaceActiveProfileEpochModel,
    )
    from cells.legacy.core.surface_active_profile_epoch_spec import to_dict as active_epoch_dict

    if isinstance(m, SurfaceActiveProfileEpochModel):
        return active_epoch_dict(self)
    from cells.legacy.core.surface_active_profile_interventions_spec import (
        SurfaceActiveProfileInterventionModel,
    )
    from cells.legacy.core.surface_active_profile_interventions_spec import (
        to_dict as active_profiles_dict,
    )

    if isinstance(m, SurfaceActiveProfileInterventionModel):
        return active_profiles_dict(self)
    from cells.legacy.core.surface_mobile_channel_spec import SurfaceMobileChannelModel, to_dict

    if isinstance(m, SurfaceMobileChannelModel):
        return to_dict(self)
    from cells.legacy.core.surface_mobile_pump_spec import SurfaceMobilePumpModel, to_dict

    if isinstance(m, SurfaceMobilePumpModel):
        return to_dict(self)
    from cells.legacy.core.surface_redistribution_spec import SurfaceRedistributionModel, to_dict

    if isinstance(m, SurfaceRedistributionModel):
        return to_dict(self)
    from cells.legacy.core.surface_mobile_pump_repair_spec import (
        SurfaceMobilePumpRepairModel,
        to_dict,
    )

    if isinstance(m, SurfaceMobilePumpRepairModel):
        return to_dict(self)
    from cells.legacy.core.surface_mobile_repair_spec import SurfaceMobileRepairModel, to_dict

    if isinstance(m, SurfaceMobileRepairModel):
        return to_dict(self)
    from cells.legacy.core.surface_repair_spec import SurfaceRepairModel, to_dict

    if isinstance(m, SurfaceRepairModel):
        return to_dict(self)
    from cells.legacy.core.surface_calcium_energy_water_repair_hcn_extra_spec import (
        SurfaceCalciumEnergyWaterRepairHCNExtraModel,
        to_dict,
    )

    if isinstance(m, SurfaceCalciumEnergyWaterRepairHCNExtraModel):
        return to_dict(self)
    from cells.legacy.core.surface_calcium_energy_water_hcn_extra_spec import (
        SurfaceCalciumEnergyWaterHCNExtraModel,
        to_dict,
    )

    if isinstance(m, SurfaceCalciumEnergyWaterHCNExtraModel):
        return to_dict(self)
    from cells.legacy.core.surface_calcium_energy_water_repair_spec import (
        SurfaceCalciumEnergyWaterRepairModel,
        to_dict,
    )

    if isinstance(m, SurfaceCalciumEnergyWaterRepairModel):
        return to_dict(self)
    from cells.legacy.core.surface_calcium_energy_water_excision_spec import (
        SurfaceCalciumEnergyWaterExcisionModel,
        to_dict,
    )

    if isinstance(m, SurfaceCalciumEnergyWaterExcisionModel):
        return to_dict(self)
    from cells.legacy.core.surface_calcium_energy_water_spec import (
        SurfaceCalciumEnergyWaterModel,
        to_dict,
    )

    if isinstance(m, SurfaceCalciumEnergyWaterModel):
        return to_dict(self)
    from cells.legacy.core.surface_calcium_energy_mitochondria_excision_spec import (
        SurfaceCalciumEnergyMitochondriaExcisionModel,
        to_dict,
    )

    if isinstance(m, SurfaceCalciumEnergyMitochondriaExcisionModel):
        return to_dict(self)
    from cells.legacy.core.surface_calcium_energy_mitochondria_spec import (
        SurfaceCalciumEnergyMitochondriaModel,
        to_dict,
    )

    if isinstance(m, SurfaceCalciumEnergyMitochondriaModel):
        return to_dict(self)
    from cells.legacy.core.surface_calcium_energy_transport_excision_spec import (
        SurfaceCalciumEnergyTransportExcisionModel,
        to_dict,
    )

    if isinstance(m, SurfaceCalciumEnergyTransportExcisionModel):
        return to_dict(self)
    from cells.legacy.core.surface_calcium_energy_irreversible_transport_excision_spec import (
        SurfaceCalciumEnergyIrreversibleTransportExcisionModel,
        to_dict,
    )

    if isinstance(m, SurfaceCalciumEnergyIrreversibleTransportExcisionModel):
        return to_dict(self)
    from cells.legacy.core.surface_calcium_energy_irreversible_transport_spec import (
        SurfaceCalciumEnergyIrreversibleTransportModel,
        to_dict,
    )

    if isinstance(m, SurfaceCalciumEnergyIrreversibleTransportModel):
        return to_dict(self)
    from cells.legacy.core.surface_calcium_energy_atp_transport_excision_spec import (
        SurfaceCalciumEnergyATPTransportExcisionModel,
        to_dict,
    )

    if isinstance(m, SurfaceCalciumEnergyATPTransportExcisionModel):
        return to_dict(self)
    from cells.legacy.core.surface_calcium_energy_atp_transport_spec import (
        SurfaceCalciumEnergyATPTransportModel,
        to_dict,
    )

    if isinstance(m, SurfaceCalciumEnergyATPTransportModel):
        return to_dict(self)
    from cells.legacy.core.surface_calcium_energy_transport_spec import (
        SurfaceCalciumEnergyTransportModel,
        to_dict,
    )

    if isinstance(m, SurfaceCalciumEnergyTransportModel):
        return to_dict(self)
    from cells.legacy.core.surface_calcium_energy_excision_spec import (
        SurfaceCalciumEnergyExcisionModel,
        to_dict,
    )

    if isinstance(m, SurfaceCalciumEnergyExcisionModel):
        return to_dict(self)
    from cells.legacy.core.surface_calcium_energy_regulated_spec import (
        SurfaceCalciumEnergyRegulatedModel,
    )
    from cells.legacy.core.surface_calcium_energy_regulated_spec import (
        to_dict as regulated_to_dict,
    )
    from cells.legacy.core.surface_calcium_energy_regulated_v2_spec import (
        SurfaceCalciumEnergyRegulatedV2Model,
    )
    from cells.legacy.core.surface_calcium_energy_regulated_v2_spec import (
        to_dict as regulated_v2_to_dict,
    )

    if isinstance(m, SurfaceCalciumEnergyRegulatedModel):
        return regulated_to_dict(self)
    from cells.legacy.core.surface_calcium_energy_regulated_v2_excision_spec import (
        SurfaceCalciumEnergyRegulatedV2ExcisionModel,
    )
    from cells.legacy.core.surface_calcium_energy_regulated_v2_excision_spec import (
        to_dict as regulated_v2_excision_to_dict,
    )

    if isinstance(m, SurfaceCalciumEnergyRegulatedV2ExcisionModel):
        return regulated_v2_excision_to_dict(self)
    if isinstance(m, SurfaceCalciumEnergyRegulatedV2Model):
        return regulated_v2_to_dict(self)
    from cells.legacy.core.surface_calcium_energy_spec import SurfaceCalciumEnergyModel, to_dict

    if isinstance(m, SurfaceCalciumEnergyModel):
        return to_dict(self)
    from cells.legacy.core.surface_calcium_water_spec import SurfaceCalciumWaterModel, to_dict

    if isinstance(m, SurfaceCalciumWaterModel):
        return to_dict(self)
    from cells.legacy.core.surface_calcium_excision_spec import SurfaceCalciumExcisionModel, to_dict

    if isinstance(m, SurfaceCalciumExcisionModel):
        return to_dict(self)
    from cells.legacy.core.surface_calcium_spec import SurfaceCalciumModel, to_dict

    if isinstance(m, SurfaceCalciumModel):
        return to_dict(self)
    from cells.legacy.core.surface_water_kinetic_spec import SurfaceWaterKineticModel, to_dict

    if isinstance(m, SurfaceWaterKineticModel):
        return to_dict(self)
    from cells.legacy.core.surface_cotransport_water_spec import (
        SurfaceCotransportWaterModel,
        to_dict,
    )

    if isinstance(m, SurfaceCotransportWaterModel):
        return to_dict(self)
    from cells.legacy.core.surface_cotransport_spec import SurfaceCotransportModel, to_dict

    if isinstance(m, SurfaceCotransportModel):
        return to_dict(self)
    from cells.legacy.core.surface_energy_water_spec import SurfaceEnergyWaterModel, to_dict

    if isinstance(m, SurfaceEnergyWaterModel):
        return to_dict(self)
    from cells.legacy.core.surface_energy_spec import SurfaceEnergyModel, to_dict

    if isinstance(m, SurfaceEnergyModel):
        return to_dict(self)
    from cells.legacy.core.surface_active_excision_spec import SurfaceActiveExcisionModel, to_dict

    if isinstance(m, SurfaceActiveExcisionModel):
        return to_dict(self)
    from cells.definitions.surface_kinetic_spec import SurfaceKineticModel, to_dict

    if isinstance(m, SurfaceKineticModel):
        return to_dict(self)
    from cells.legacy.core.surface_water_spec import SurfaceWaterModel, to_dict

    if isinstance(m, SurfaceWaterModel):
        return to_dict(self)
    from cells.legacy.core.surface_excision_spec import SurfaceExcisionModel, to_dict

    if isinstance(m, SurfaceExcisionModel):
        return to_dict(self)
    from cells.legacy.core.surface_profile_epoch_spec import SurfaceProfileEpochModel
    from cells.legacy.core.surface_profile_epoch_spec import to_dict as profile_epoch_to_dict

    if isinstance(m, SurfaceProfileEpochModel):
        return profile_epoch_to_dict(self)
    from cells.legacy.core.surface_profile_interventions_spec import (
        SurfaceProfileInterventionModel,
    )
    from cells.legacy.core.surface_profile_interventions_spec import (
        to_dict as profile_interventions_to_dict,
    )

    if isinstance(m, SurfaceProfileInterventionModel):
        return profile_interventions_to_dict(self)
    from cells.legacy.core.environment_barrier_interventions_spec import EnvironmentBarrierModel
    from cells.legacy.core.environment_barrier_interventions_spec import to_dict as barrier_to_dict

    if isinstance(m, EnvironmentBarrierModel):
        return barrier_to_dict(self)
    from cells.definitions.surface_tissue_spec import SurfaceTissueModel, to_dict

    if isinstance(m, SurfaceTissueModel):
        return to_dict(self)
    from cells.legacy.core.tissue_calcium_spec import TissueCalciumModel, to_dict

    if isinstance(m, TissueCalciumModel):
        return to_dict(self)
    from cells.legacy.core.tissue_spec import TissueModel, to_dict

    if isinstance(m, TissueModel):
        return to_dict(self)
    from cells.legacy.core.ip3_calcium_spec import IP3CalciumModel, to_dict

    if isinstance(m, IP3CalciumModel):
        return to_dict(self)
    from cells.legacy.core.gated_calcium_spec import GatedCalciumModel, to_dict

    if isinstance(m, GatedCalciumModel):
        return to_dict(self)
    from cells.legacy.core.plasma_calcium_spec import PlasmaModel, to_dict

    if isinstance(m, PlasmaModel):
        return to_dict(self)
    from cells.legacy.core.spatial_calcium_spec import CalciumModel, to_dict

    if isinstance(m, CalciumModel):
        return to_dict(self)
    from cells.legacy.core.er_spec import ERModel, to_dict

    if isinstance(m, ERModel):
        return to_dict(self)
    from cells.legacy.core.reaction_spec import ReactionNetworkSpec, to_dict

    if isinstance(m, ReactionNetworkSpec):
        return to_dict(self)
    if isinstance(m, SpatialJunctionSpec):
        from cells.legacy.core.spatial_junction_spec import to_dict

        return to_dict(self)
    if isinstance(m, JunctionFiniteExtracellularSpec):
        from cells.legacy.core.junction_finite_spec import to_dict

        return to_dict(self)
    if isinstance(m, KineticFiniteExtracellularSpec):
        from cells.legacy.core.kinetic_finite_spec import to_dict

        return to_dict(self)
    if isinstance(m, SpatialExtracellularSpec):
        from cells.legacy.core.spatial_extracellular_spec import to_dict

        return to_dict(self)
    if isinstance(m, FiniteExtracellularSpec):
        from cells.legacy.core.finite_extracellular_spec import to_dict

        return to_dict(self)
    if isinstance(m, PhysicalIonicGraphSpec):
        from cells.legacy.core.physical_ionic_graph_spec import to_dict

        return to_dict(self)
    if isinstance(m, VoltageGatedSpec):
        from cells.legacy.core.voltage_gated_spec import to_dict

        return to_dict(self)
    if isinstance(m, MultispeciesSpec):
        from cells.legacy.core.multispecies_spec import to_dict

        return to_dict(self)
    if isinstance(x, MultispeciesExecutionSpec):
        raise ConfigError("Multispecies execution settings require their own model identity")
    if isinstance(m, SourcePairSpec):
        from cells.legacy.core.source_pair_spec import to_dict

        return to_dict(self)
    if isinstance(m, BioelectricPairSpec):
        from cells.legacy.core.bioelectric_pair_spec import to_dict

        return to_dict(self)
    if not isinstance(e, ExperimentSpec):
        raise ConfigError("Experiment type does not match the declared model")
    if isinstance(m, BioelectricSpec):
        from cells.legacy.core.bioelectric_spec import to_dict

        return to_dict(self)
    return None


def control_values(spec, times):
    """`control_values`' older families, in its order: their model entries, then the change
    types of the moved modules (surface calcium, gated, plasma and stored calcium, ER,
    reactions). None when none matches, or when there are no changes (the core's zeros)."""
    from cells.execution.schedule import (
        control_values,  # Recursion: the core's whole chain, as before.
    )
    from cells.legacy.core import surface_open_calcium_bath_epoch_spec as calcium_bath_epoch
    from cells.legacy.core import surface_open_calcium_energy_bath_epoch_spec as energy_bath_epoch

    if isinstance(spec.model, energy_bath_epoch.SurfaceOpenCalciumEnergyBathEpochModel):
        return control_values(energy_bath_epoch.scheduled_spec(spec), times)
    if isinstance(spec.model, calcium_bath_epoch.SurfaceOpenCalciumBathEpochModel):
        return control_values(calcium_bath_epoch.scheduled_spec(spec), times)
    from cells.legacy.core import surface_open_calcium_bath_events_spec as calcium_bath
    from cells.legacy.core import surface_open_calcium_energy_bath_events_spec as energy_bath

    if isinstance(spec.model, energy_bath.SurfaceOpenCalciumEnergyBathEventModel):
        return control_values(energy_bath.owner_spec(spec), times)
    if isinstance(spec.model, calcium_bath.SurfaceOpenCalciumBathEventModel):
        return control_values(calcium_bath.owner_spec(spec), times)
    from cells.legacy.core import surface_open_calcium_energy_spec as open_energy
    from cells.legacy.core import surface_open_calcium_spec as open_calcium

    if isinstance(spec.model, open_energy.SurfaceOpenCalciumEnergyModel):
        return control_values(open_energy.equation_spec(spec), times)
    if isinstance(spec.model, open_calcium.SurfaceOpenCalciumModel):
        return control_values(open_calcium.equation_spec(spec), times)
    from cells.legacy.core import surface_active_bath_epoch_spec as active_bath_epoch
    from cells.legacy.core import surface_passive_bath_epoch_spec as passive_bath_epoch

    if isinstance(spec.model, active_bath_epoch.SurfaceActiveBathEpochModel):
        return control_values(active_bath_epoch.scheduled_spec(spec), times)
    if isinstance(spec.model, passive_bath_epoch.SurfacePassiveBathEpochModel):
        return control_values(passive_bath_epoch.scheduled_spec(spec), times)
    from cells.legacy.core import surface_active_bath_events_spec as active_bath
    from cells.legacy.core import surface_passive_bath_events_spec as passive_bath

    if isinstance(spec.model, active_bath.SurfaceActiveBathEventModel):
        return control_values(active_bath.owner_spec(spec), times)
    if isinstance(spec.model, passive_bath.SurfacePassiveBathEventModel):
        return control_values(passive_bath.owner_spec(spec), times)
    from cells.legacy.core import (
        surface_calcium_energy_water_profile_barrier_epoch_spec as water_joint_epoch,
    )
    from cells.legacy.core import (
        surface_calcium_energy_water_repair_profile_barrier_epoch_spec as repair_joint_epoch,
    )

    if isinstance(
        spec.model, repair_joint_epoch.SurfaceCalciumEnergyWaterRepairProfileBarrierEpochModel
    ):
        return control_values(repair_joint_epoch.scheduled_spec(spec), times)
    if isinstance(spec.model, water_joint_epoch.SurfaceCalciumEnergyWaterProfileBarrierEpochModel):
        return control_values(water_joint_epoch.scheduled_spec(spec), times)
    from cells.legacy.core import (
        surface_calcium_energy_water_profile_barrier_interventions_spec as water_combined,
    )
    from cells.legacy.core import (
        surface_calcium_energy_water_repair_profile_barrier_interventions_spec as repair_combined,
    )

    if isinstance(
        spec.model, repair_combined.SurfaceCalciumEnergyWaterRepairProfileBarrierInterventionModel
    ):
        return control_values(repair_combined.owner_spec(spec), times)
    if isinstance(
        spec.model, water_combined.SurfaceCalciumEnergyWaterProfileBarrierInterventionModel
    ):
        return control_values(water_combined.owner_spec(spec), times)
    from cells.legacy.core import (
        surface_calcium_energy_profile_barrier_epoch_spec as energy_combined_epoch,
    )
    from cells.legacy.core import (
        surface_calcium_profile_barrier_epoch_spec as calcium_combined_epoch,
    )

    if isinstance(spec.model, calcium_combined_epoch.SurfaceCalciumProfileBarrierEpochModel):
        return control_values(calcium_combined_epoch.scheduled_spec(spec), times)
    if isinstance(spec.model, energy_combined_epoch.SurfaceCalciumEnergyProfileBarrierEpochModel):
        return control_values(energy_combined_epoch.scheduled_spec(spec), times)
    from cells.legacy.core import surface_active_profile_barrier_epoch_spec as combined_epoch

    if isinstance(spec.model, combined_epoch.SurfaceActiveProfileBarrierEpochModel):
        return control_values(combined_epoch.scheduled_spec(spec), times)
    from cells.legacy.core import (
        surface_calcium_energy_profile_barrier_interventions_spec as energy_combined,
    )
    from cells.legacy.core import (
        surface_calcium_profile_barrier_interventions_spec as calcium_combined,
    )

    if isinstance(spec.model, calcium_combined.SurfaceCalciumProfileBarrierInterventionModel):
        return control_values(calcium_combined.owner_spec(spec), times)
    if isinstance(spec.model, energy_combined.SurfaceCalciumEnergyProfileBarrierInterventionModel):
        return control_values(energy_combined.owner_spec(spec), times)
    from cells.legacy.core import (
        surface_active_profile_barrier_interventions_spec as active_combined,
    )

    if isinstance(spec.model, active_combined.SurfaceActiveProfileBarrierInterventionModel):
        return control_values(active_combined.owner_spec(spec), times)
    from cells.legacy.core import (
        surface_calcium_energy_water_barrier_epoch_spec as water_barrier_epoch,
    )
    from cells.legacy.core import (
        surface_calcium_energy_water_repair_barrier_epoch_spec as repair_barrier_epoch,
    )

    if isinstance(
        spec.model, repair_barrier_epoch.SurfaceCalciumEnergyWaterRepairBarrierEpochModel
    ):
        return control_values(repair_barrier_epoch.scheduled_spec(spec), times)
    if isinstance(spec.model, water_barrier_epoch.SurfaceCalciumEnergyWaterBarrierEpochModel):
        return control_values(water_barrier_epoch.scheduled_spec(spec), times)
    from cells.legacy.core import (
        surface_calcium_energy_water_barrier_interventions_spec as water_barrier,
    )
    from cells.legacy.core import (
        surface_calcium_energy_water_repair_barrier_interventions_spec as repair_barrier,
    )

    if isinstance(
        spec.model, repair_barrier.SurfaceCalciumEnergyWaterRepairBarrierInterventionModel
    ):
        return control_values(repair_barrier.owner_spec(spec), times)
    if isinstance(spec.model, water_barrier.SurfaceCalciumEnergyWaterBarrierInterventionModel):
        return control_values(water_barrier.owner_spec(spec), times)
    from cells.legacy.core import surface_active_barrier_epoch_spec as active_ecm_epoch
    from cells.legacy.core import surface_calcium_barrier_epoch_spec as calcium_ecm_epoch
    from cells.legacy.core import surface_calcium_energy_barrier_epoch_spec as energy_ecm_epoch

    if isinstance(spec.model, active_ecm_epoch.SurfaceActiveBarrierEpochModel):
        return control_values(active_ecm_epoch.scheduled_spec(spec), times)
    if isinstance(spec.model, calcium_ecm_epoch.SurfaceCalciumBarrierEpochModel):
        return control_values(calcium_ecm_epoch.scheduled_spec(spec), times)
    if isinstance(spec.model, energy_ecm_epoch.SurfaceCalciumEnergyBarrierEpochModel):
        return control_values(energy_ecm_epoch.scheduled_spec(spec), times)
    from cells.legacy.core import surface_active_barrier_interventions_spec as active_barrier
    from cells.legacy.core import surface_calcium_barrier_interventions_spec as calcium_barrier
    from cells.legacy.core import (
        surface_calcium_energy_barrier_interventions_spec as energy_barrier,
    )

    if isinstance(spec.model, active_barrier.SurfaceActiveBarrierInterventionModel):
        return control_values(active_barrier.owner_spec(spec), times)
    if isinstance(spec.model, calcium_barrier.SurfaceCalciumBarrierInterventionModel):
        return control_values(calcium_barrier.owner_spec(spec), times)
    if isinstance(spec.model, energy_barrier.SurfaceCalciumEnergyBarrierInterventionModel):
        return control_values(energy_barrier.owner_spec(spec), times)
    from cells.legacy.core import (
        surface_calcium_energy_water_profile_epoch_spec as joint_water_epoch,
    )
    from cells.legacy.core import (
        surface_calcium_energy_water_repair_profile_epoch_spec as joint_repair_epoch,
    )

    if isinstance(spec.model, joint_repair_epoch.SurfaceCalciumEnergyWaterRepairProfileEpochModel):
        return control_values(joint_repair_epoch.scheduled_spec(spec), times)
    if isinstance(spec.model, joint_water_epoch.SurfaceCalciumEnergyWaterProfileEpochModel):
        return control_values(joint_water_epoch.scheduled_spec(spec), times)
    from cells.legacy.core import (
        surface_calcium_energy_water_profile_interventions_spec as joint_water_profile,
    )
    from cells.legacy.core import (
        surface_calcium_energy_water_repair_profile_interventions_spec as joint_repair_profile,
    )

    if isinstance(
        spec.model, joint_repair_profile.SurfaceCalciumEnergyWaterRepairProfileInterventionModel
    ):
        return control_values(joint_repair_profile.owner_spec(spec), times)
    if isinstance(
        spec.model, joint_water_profile.SurfaceCalciumEnergyWaterProfileInterventionModel
    ):
        return control_values(joint_water_profile.owner_spec(spec), times)
    changes = spec.experiment.changes
    if isinstance(spec.model, SurfaceCalciumEnergyWaterRepairHCNExtraModel):
        original = control_values(joint_hcn_repair_prior(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        extra = []
        for key in ("injury", "resealing"):
            values = np.asarray([getattr(p, key) for p in changes], dtype=float)[indices]
            padded = np.zeros((len(times), spec.execution.membrane_capacity))
            padded[:, : len(spec.model.membranes)] = values
            extra.append(padded)
        return JointHCNRepairControl(*original, *extra)
    if isinstance(spec.model, SurfaceCalciumEnergyWaterHCNExtraModel):
        original = control_values(joint_hcn_water_prior(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.water for p in changes], dtype=float)[indices]
        padded = np.zeros((len(times), spec.execution.membrane_capacity))
        padded[:, : len(spec.model.membranes)] = values
        return JointHCNWaterControl(*original, padded)
    if isinstance(spec.model, SurfaceCalciumEnergyWaterRepairModel):
        original = control_values(joint_repair_prior(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        extra = []
        for key in ("injury", "resealing"):
            values = np.asarray([getattr(p, key) for p in changes], dtype=float)[indices]
            padded = np.zeros((len(times), spec.execution.membrane_capacity))
            padded[:, : len(spec.model.membranes)] = values
            extra.append(padded)
        return JointRepairControl(*original, *extra)
    if isinstance(spec.model, SurfaceCalciumEnergyWaterModel):
        original = control_values(calcium_energy_water_prior(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.water for p in changes], dtype=float)[indices]
        padded = np.zeros((len(times), spec.execution.membrane_capacity))
        padded[:, : len(spec.model.membranes)] = values
        return SurfaceCalciumEnergyWaterControl(*original, padded)
    if isinstance(spec.model, SurfaceCalciumWaterModel):
        original = control_values(calcium_water_prior(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.water for p in changes], dtype=float)[indices]
        padded = np.zeros((len(times), spec.execution.membrane_capacity))
        padded[:, : len(spec.model.membranes)] = values
        return SurfaceCalciumWaterControl(*original, padded)
    if isinstance(spec.model, SurfaceCalciumEnergyMitochondriaModel):
        from cells.legacy.core.surface_calcium_energy_mitochondria_spec import Control
        from cells.legacy.core.surface_calcium_energy_mitochondria_spec import base_spec as prior

        original = control_values(prior(spec), times)
        indices = np.searchsorted([c.time for c in changes], times, side="right") - 1
        values = np.asarray([c.mitochondria for c in changes])[indices]
        padded = np.zeros((len(times), spec.execution.capacity))
        padded[:, : len(spec.model.mitochondria)] = values
        return Control(*original, padded)
    if isinstance(spec.model, SurfaceCalciumEnergyTransportModel):
        from cells.legacy.core.surface_calcium_energy_transport_spec import Control
        from cells.legacy.core.surface_calcium_energy_transport_spec import base_spec as prior

        original = control_values(prior(spec), times)
        changes = spec.experiment.changes
        indices = np.searchsorted([c.time for c in changes], times, side="right") - 1
        values = np.asarray([c.network_transport for c in changes])[indices]
        padded = np.zeros((len(times), spec.execution.network_transport_capacity))
        padded[:, : len(spec.model.network_transporters)] = values
        return Control(*original, padded)
    from cells.legacy.core.surface_calcium_energy_regulated_spec import (
        SurfaceCalciumEnergyRegulatedModel,
    )
    from cells.legacy.core.surface_calcium_energy_regulated_spec import (
        control_values as regulated_controls,
    )
    from cells.legacy.core.surface_calcium_energy_regulated_v2_spec import (
        SurfaceCalciumEnergyRegulatedV2Model,
    )
    from cells.legacy.core.surface_calcium_energy_regulated_v2_spec import (
        control_values as regulated_v2_controls,
    )

    if isinstance(spec.model, SurfaceCalciumEnergyRegulatedModel):
        return regulated_controls(spec, times)
    if isinstance(spec.model, SurfaceCalciumEnergyRegulatedV2Model):
        return regulated_v2_controls(spec, times)
    if isinstance(spec.model, SurfaceCalciumEnergyModel):
        original = control_values(calcium_energy_prior(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.regeneration for p in changes], dtype=float)[indices]
        padded = np.zeros((len(times), spec.execution.regeneration_capacity))
        padded[:, : len(spec.model.regeneration_ports)] = values
        return SurfaceCalciumEnergyControl(*original, padded)
    if isinstance(spec.model, SurfaceCotransportWaterModel):
        original = control_values(cotransport_water_spec(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.cotransport for p in changes], dtype=float)[indices]
        padded = np.zeros((len(times), spec.execution.cotransport_capacity))
        padded[:, : len(spec.model.cotransporters)] = values
        return CotransportWaterControl(*original, padded)
    if isinstance(spec.model, SurfaceCotransportModel):
        original = control_values(cotransport_energy_spec(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.cotransport for p in changes], dtype=float)[indices]
        padded = np.zeros((len(times), spec.execution.cotransport_capacity))
        padded[:, : len(spec.model.cotransporters)] = values
        return SurfaceCotransportControl(*original, padded)
    if isinstance(spec.model, SurfaceEnergyWaterModel):
        original = control_values(energy_spec(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.water for p in changes], dtype=float)[indices]
        padded = np.zeros((len(times), spec.execution.membrane_capacity))
        padded[:, : len(spec.model.membranes)] = values
        return SurfaceEnergyWaterControl(*original, padded)
    if isinstance(spec.model, SurfaceEnergyModel):
        original = control_values(initial_ionic_spec(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.regeneration for p in changes], dtype=float)[indices]
        padded = np.zeros((len(times), spec.execution.regeneration_capacity))
        padded[:, : len(spec.model.regeneration_ports)] = values
        return SurfaceEnergyControl(*original, padded)
    if isinstance(spec.model, SurfaceWaterKineticModel):
        original = control_values(water_kinetic_prior(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.water for p in changes], dtype=float)[indices]
        padded = np.zeros((len(times), spec.execution.membrane_capacity))
        padded[:, : len(spec.model.membranes)] = values
        return SurfaceWaterKineticControl(*original, padded)
    if isinstance(spec.model, SurfaceWaterModel):
        original = control_values(water_prior(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.water for p in changes], dtype=float)[indices]
        padded = np.zeros((len(times), spec.execution.membrane_capacity))
        padded[:, : len(spec.model.membranes)] = values
        return SurfaceWaterControl(*original, padded)
    if isinstance(spec.model, SurfaceMobileChannelModel):
        original = control_values(mobile_channel_prior(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.channel for p in changes], dtype=float)[indices]
        padded = np.zeros(
            (
                len(times),
                spec.execution.channel_population_capacity,
                spec.execution.membrane_capacity,
            )
        )
        padded[:, : len(spec.model.mobile_channels), : len(spec.model.membranes)] = values
        return SurfaceMobileChannelControl(*original, padded)
    if isinstance(spec.model, SurfaceMobilePumpModel):
        original = control_values(mobile_pump_prior(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.pump for p in changes], dtype=float)[indices]
        padded = np.zeros(
            (len(times), spec.execution.pump_population_capacity, spec.execution.membrane_capacity)
        )
        padded[:, : len(spec.model.mobile_pumps), : len(spec.model.membranes)] = values
        return SurfaceMobilePumpControl(*original, padded)
    if isinstance(spec.model, SurfaceMobilePumpRepairModel):
        original = control_values(mobile_pump_repair_prior(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.mobile_pump for p in changes], dtype=float)[indices]
        padded = np.zeros(
            (len(times), spec.execution.pump_population_capacity, spec.execution.membrane_capacity)
        )
        padded[:, : len(spec.model.mobile_pumps), : len(spec.model.membranes)] = values
        return SurfaceMobilePumpRepairControl(*original, padded)
    if isinstance(spec.model, SurfaceMobileRepairModel):
        original = control_values(mobile_repair_prior(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.mobile_channel for p in changes], dtype=float)[indices]
        padded = np.zeros(
            (
                len(times),
                spec.execution.channel_population_capacity,
                spec.execution.membrane_capacity,
            )
        )
        padded[:, : len(spec.model.mobile_channels), : len(spec.model.membranes)] = values
        return SurfaceMobileRepairControl(*original, padded)
    if isinstance(spec.model, SurfaceRepairModel):
        original = control_values(repair_base_spec(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        routes = []
        for name in ("injury", "resealing"):
            values = np.asarray([getattr(p, name) for p in changes], dtype=float)[indices]
            array = np.zeros((len(times), spec.execution.membrane_capacity))
            array[:, : values.shape[-1]] = values
            routes.append(array)
        return SurfaceRepairControl(*original, *routes)
    if not changes:  # The core returns its zeros (D188 R1).
        return None
    if isinstance(changes[0], SurfaceCalciumChange):
        original = control_values(surface_ionic_spec(spec), times)
        stores = [control_values(store_spec(spec, i), times) for i in range(len(spec.model.stores))]
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        routes = []
        for name in ("plasma_pump", "plasma_exchange", "calcium_channel"):
            values = np.asarray([getattr(p, name) for p in changes], dtype=float)[indices]
            array = np.zeros((len(times), spec.execution.membrane_capacity))
            array[:, : values.shape[-1]] = values
            routes.append(array)
        return SurfaceCalciumControl(
            *original, *(np.stack([v[j] for v in stores], axis=1) for j in range(4)), *routes
        )
    if isinstance(changes[0], GatedCalciumChange):
        original = control_values(plasma_spec(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.calcium_channel for p in changes], dtype=np.float64)[indices]
        array = np.zeros((len(times), spec.execution.membrane_capacity))
        array[:, : values.shape[-1]] = values
        return GatedCalciumControl(*original, array)
    if isinstance(changes[0], PlasmaChange):
        original = control_values(plasma_prior(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        routes = []
        for name in ("plasma_pump", "plasma_exchange"):
            values = np.asarray([getattr(p, name) for p in changes], dtype=np.float64)[indices]
            array = np.zeros((len(times), spec.execution.membrane_capacity))
            array[:, : values.shape[-1]] = values
            routes.append(array)
        return PlasmaControl(*original, *routes)
    if isinstance(changes[0], CalciumChange):
        ionic = control_values(ionic_spec(spec), times)
        stores = [control_values(store_spec(spec, i), times) for i in range(len(spec.model.stores))]
        return CalciumControl(*ionic, *(np.stack([v[j] for v in stores], axis=1) for j in range(4)))
    if isinstance(changes[0], ERChange):
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        reactions = np.zeros((len(times), spec.execution.reaction_capacity))
        values = np.asarray([p.reactions for p in changes], dtype=np.float64)
        reactions[:, : values.shape[-1]] = values[indices]
        return ERControl(
            reactions,
            *(
                np.asarray([getattr(p, name) for p in changes], dtype=np.float64)[indices]
                for name in ("passive", "pump", "release")
            ),
        )
    if isinstance(changes[0], ReactionChange):
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.multipliers for p in changes], dtype=np.float64)
        result = np.zeros((len(times), spec.execution.reaction_capacity))
        result[:, : values.shape[-1]] = values[indices]
        return result
    return None


def cli(command):
    """The command line's older subcommands: the main function of tissue-phase, tissue-geometry,
    tissue-profiles, assembly-cluster or assembly-cell (called with the remaining arguments), or
    excise's handler (called with the parsed arguments inside the command line's error
    handling); None for any other command."""
    if command == "tissue-phase":
        from cells.legacy.tissue_phase import main as phase_main

        return phase_main
    if command == "tissue-geometry":
        from cells.legacy.tissue_geometry import main as geometry_main

        return geometry_main
    if command == "tissue-profiles":
        from cells.legacy.tissue_profiles import main as profiles_main

        return profiles_main
    if command == "assembly-cluster":
        from cells.legacy.assembly_cluster.cli import main as cluster_main

        return cluster_main
    if command == "assembly-cell":
        from cells.legacy.assembly_cell.cli import main as coupled_main

        return coupled_main
    if command == "excise":
        return _excise
    return None


def _excise(args):
    from cells.legacy.core.excision import excise
    from cells.legacy.excision_io import write_excision

    saved = load_snapshot(args.snapshot)
    result = excise(saved.spec, saved.checkpoint, args.remove)
    write_excision(args.output, result)
    print(
        json.dumps(
            dict(
                status="complete",
                output=str(args.output),
                terminal=result.report["terminal"],
                absolute_time_s=saved.checkpoint.time,
                continuation=str(args.output / "after") if result.spec is not None else None,
            ),
            indent=2,
        )
    )
    return 0


def ensemble(model):
    """The ensemble adapters' hooks of an older assembly family, by model ID: parse_spec(),
    runtime(), flatten(), for the cluster aggregate() and for the cell working_size(), each
    importing as the adapters did and returning what they used; None for any other model."""
    if model == "assembly_regulated_cluster@1":
        return _CLUSTER
    if model == "assembly_regulated_cell@1":
        return _CELL
    return None


def _cluster_parse_spec():
    from cells.legacy.assembly_cluster.spec import parse_spec

    return parse_spec


def _cell_parse_spec():
    from cells.legacy.assembly_cell.spec import parse_spec

    return parse_spec


def _cluster_runtime():
    from cells.legacy.ensemble.cluster import load_checkpoint, run, write_checkpoint

    return run, load_checkpoint, write_checkpoint


def _cell_runtime():
    from cells.legacy.ensemble.coupled import load_checkpoint, run, write_checkpoint

    return run, load_checkpoint, write_checkpoint


def _flatten():
    from cells.legacy.assembly_cell.io import flatten

    return flatten


def _cluster_aggregate():
    from cells.legacy.ensemble.cluster import aggregate as aggregate_cluster

    return aggregate_cluster


def _cell_working_size():
    """ensemble/families.output_bound's ionic working size (D188 R3: the model module moves)."""
    from cells.legacy.models.kinetic_finite_extracellular import working_size

    return working_size


_CLUSTER = SimpleNamespace(
    parse_spec=_cluster_parse_spec,
    runtime=_cluster_runtime,
    flatten=_flatten,
    aggregate=_cluster_aggregate,
)
_CELL = SimpleNamespace(
    parse_spec=_cell_parse_spec,
    runtime=_cell_runtime,
    flatten=_flatten,
    working_size=_cell_working_size,
)
