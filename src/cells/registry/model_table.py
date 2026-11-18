"""The static model table: every active model, its homes and its interfaces
(docs/CORE_SEAMS_DESIGN.md §8.4 in its minimal form, §15).

**Static.** The table is one literal, read when a registry loads. Nothing appends to it at import:
a family that registered itself by being imported would leave the registries, and the
declarations manifest written from them, depending on what happened to be imported first. A
built-in family joins by adding its row here, in the same change as its pieces.
tests/unit/test_model_table.py holds the table to the code: every module under `src/cells` that
registers a piece is one of its homes, and its keys are the models that core/specs.parse_spec
dispatches itself.

**Its rows**, keyed by the model's ID as definitions write it (a bare ID is in `cells`, D185):
- `type`: "inner" (the inner model, which hosts its own laws and its kinds), "composite" (an inner
  model and any ordered list of operators), "composition" (the composite with a fixed operator
  list, as core/pump_composite_spec.frozen_definition rewrites it) or "family" (a model family of
  its own);
- `module`: the module whose `parse` reads the model's definitions (parse_spec's dispatch);
- `law_homes`: the modules that register its laws and kinds, imported by name, once, when the law
  registry loads (registry/laws.py). A home that is a package registers through the modules its
  `__init__` imports; an inert law module (§8.2) declares its one law as `LAW`, which the loader
  registers;
- `operator_homes`: the modules that register its operators, imported when the operator section
  loads (registry/operators.py), the composite's package first;
- `interfaces`: the `cells` interfaces the family declares. The `cells` namespace is reserved
  (docs/MODULE_SYSTEM_DESIGN.md §2.3), so a built-in family's interfaces are `cells.*`, named for
  what they are, since other families implement them too. The law template's five
  (registry/laws.INTERFACES) are the initial set; a declaration may name one declared here, and
  its own type checks its own fields when it registers;
- `runner`: the entry of a model that runs on its own runner ("module:function"), or None for the
  fixed-step runner;
- `composition`: a composition's inner model and its operators, in order, or None;
- `ensemble`: the family's ensemble adapter ("module:object", an ensemble/families.EnsembleAdapter)
  through which `cells ensemble` plans and runs its arms, or None (CORE_SEAMS §15's follow-up; the
  lead's ruling (a), 18 November 2026). A family joins the ensemble by its adapter and this entry,
  with no edit to ensemble/*.

Replacing the dispatch chains (models/registry.get_model, core/specs.parse_spec) with this table
stays deferred (§8.4). This module imports nothing from Cells.
"""

from types import MappingProxyType
from typing import NamedTuple

TYPES = ("inner", "composite", "composition", "family")


class Model(NamedTuple):
    """One row of the table (module docstring)."""

    type: str
    module: str
    law_homes: tuple = ()
    operator_homes: tuple = ()
    interfaces: tuple = ()
    runner: str | None = None
    composition: tuple | None = None
    ensemble: str | None = None


MODELS = MappingProxyType(
    {
        "resolved_pump_tissue@3": Model(
            type="inner",
            module="cells.definitions.surface_pump_v3_spec",
            # Its own laws, and its kinds' package, whose modules declare theirs.
            law_homes=("cells.models.inner_laws", "cells.kinds"),
        ),
        "resolved_pump_composite@1": Model(
            type="composite",
            module="cells.definitions.pump_composite_spec",
            operator_homes=("cells.operators",),
        ),
        "resolved_pump_water@1": Model(
            type="composition",
            module="cells.definitions.surface_pump_water_spec",
            composition=("resolved_pump_tissue@3", ("ideal_osmosis_linear_compliance_water@1",)),
        ),
        "resolved_pump_water@2": Model(
            type="composition",
            module="cells.definitions.surface_pump_water_v2_spec",
            composition=(
                "resolved_pump_tissue@3",
                ("ideal_osmosis_linear_compliance_water@1", "k_anion_symport_mass_action@1"),
            ),
        ),
        "resolved_pump_replacement@1": Model(
            type="composition",
            module="cells.definitions.cell_replacement_spec",
            composition=("resolved_pump_tissue@3", ("scheduled_cell_replacement@1",)),
        ),
        "cells.assembly_lineages@1": Model(
            type="family",
            module="cells.models.assembly_lineages.spec",
            law_homes=(
                "cells.models.assembly_lineages.exchange",
                "cells.models.assembly_lineages.gard",
            ),
            operator_homes=(
                "cells.models.assembly_lineages.fission",
                "cells.models.assembly_lineages.continuation",
            ),
            interfaces=(
                "cells.exchange_law@1",
                "cells.rate_factor_law@1",
                "cells.lineage_operator@1",
            ),
            runner="cells.models.assembly_lineages.runner:run",
        ),
        "cells.assembly_lineages@2": Model(
            type="family",
            module="cells.models.assembly_lineages_v2.spec",
            law_homes=(
                "cells.models.assembly_lineages_v2.mass_action",
                "cells.models.assembly_lineages_v2.transition_state",
                "cells.models.assembly_lineages_v2.ideal_mixing",
                "cells.models.assembly_lineages_v2.regular_mixing",
            ),
            interfaces=(
                "cells.reaction_law@1",
                "cells.rate_factor_law@2",
                "cells.free_energy_term@1",
            ),
            runner="cells.models.assembly_lineages_v2.runner:run",
        ),
        # The older active families (D189): their laws are tables inside them, and they declare
        # no piece.
        "apical_vertex_mechanics@1": Model(type="family", module="cells.definitions.apical_vertex_spec"),  # noqa: E501
        "reaction_transport@1": Model(type="family", module="cells.definitions.specs"),
        "resolved_pump_tissue@1": Model(type="family", module="cells.definitions.surface_pump_spec"),  # noqa: E501
        "resolved_pump_tissue@2": Model(type="family", module="cells.definitions.surface_pump_v2_spec"),  # noqa: E501
    }
)
