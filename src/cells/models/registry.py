"""Small explicit model registry: no dynamic plugins or organ-name branches.

Each module supplies state/layout types, initialization, a pure RHS, numerical
checks, read-only observations, and a summary. Scientific meaning stays there;
the runner owns scheduling, integration, replay, and resource policy.
"""

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
from cells.core.surface_calcium_spec import SurfaceCalciumModel
from cells.core.surface_kinetic_spec import SurfaceKineticModel
from cells.core.surface_tissue_spec import SurfaceTissueModel
from cells.core.tissue_calcium_spec import TissueCalciumModel
from cells.core.tissue_spec import TissueModel
from cells.models import (
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
    surface_kinetic,
    surface_tissue,
    tissue,
    tissue_calcium,
    voltage_gated_membrane,
)


def get_model(spec):
    if isinstance(spec, BetseSpatialModel):
        return betse_spatial
    if isinstance(spec, SurfaceCalciumModel):
        return surface_calcium
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
