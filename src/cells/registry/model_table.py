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
            # Its own laws, each an inert law module (CORE_SEAMS §8.2), its passive kind's two,
            # and its kinds' package, whose modules declare the rest of theirs.
            law_homes=(
                "cells.laws.channels.kv1p5_mh",
                "cells.laws.channels.kir2p1_mh2",
                "cells.laws.channels.nav1p2_m3h_regularized",
                "cells.laws.channels.kleak_always_open",
                "cells.laws.channels.naleak_always_open",
                # The Kv1 pilot's five, codes 5-9 (D211, D213), since @3's parser reads its channel
                # table from the law registry (the Kv1 trigger, eb91851e).
                "cells.laws.channels.kv1p1_mh2",
                "cells.laws.channels.kv1p2_mh",
                "cells.laws.channels.kv1p3_mh",
                "cells.laws.channels.kv1p4_mh",
                "cells.laws.channels.kv1p6_mh",
                # The always-open Cl⁻ leak, code 10 (D228 item 3, the H1 seam's Cl⁻ part).
                "cells.laws.channels.clleak_always_open",
                "cells.laws.channels.open_channel_block",  # FR-51's block (D371).
                "cells.laws.junctions.junction_voltage_relaxation",
                # FR-30, development only (D262; the @3 owner's recorded exception, F's file).
                "cells.laws.junctions.junction_series_gates",
                "cells.laws.pumps.nak_atp_mass_action_positive",
                "cells.laws.pumps.ca_atp_mass_action_positive",
                "cells.laws.routes.constant_field",
                "cells.laws.routes.logmean_electrodiffusion",
                # The forms face law (MT-1b's face, the face builder under the @3 owner's leave).
                "cells.laws.routes.logmean_electrodiffusion_forms",
                "cells.laws.routes.passive_permeation",
                "cells.laws.routes.inward_rectifier_linear_driving_force",  # The kinds owner's.
                "cells.laws.routes.constant_field_permeation",  # FR-15 P2 (the operators owner's).
                "cells.laws.transport.proton_leak",
                # MT-1b's leak reading the general closure (face plan item 3; the kinds owner's).
                "cells.laws.transport.proton_leak_v2",
                # The transporter's two laws' modules: their declarations move in as inert LAWs
                # (the kinds owner's, CORE_SEAMS §18); until then they register nothing here.
                "cells.laws.pumps.atp_transporter",
                "cells.laws.pumps.proton_pump",
                "cells.laws.cycles.na_anion_symport_factored",  # The kinds owner's (D228 item 1).
                "cells.laws.cycles.na2_anion_symport_diagram",  # Its version 2, the same item.
                # The mitochondria's cycle laws (the kinds owner's, from the appendix at tag
                # mito-laws-appendix-2026-11-20b; the lead's rulings of 20 November 2026).
                "cells.laws.cycles.nadh_ubiquinone_proton_cycle",
                "cells.laws.cycles.ubiquinol_cytochrome_c_proton_cycle",
                "cells.laws.cycles.cytochrome_c_oxygen_proton_cycle",
                "cells.laws.cycles.proton_coupled_atp_synthesis_cycle",
                "cells.laws.cycles.electrogenic_nucleotide_exchange",
                "cells.laws.cycles.phosphate_proton_symport",
                "cells.laws.cycles.potassium_proton_exchange",
                "cells.laws.cycles.held_reductant_supply",
                "cells.laws.cycles.adenylate_kinase",
                # The general binding closure (rapid_binding@1), seam C's: the binding owner's
                # line, a recorded exception (the lead, 18 November 2026).
                "cells.laws.reactions.rapid_binding",
                "cells.kinds",
            ),
            interfaces=("cells.channel_block_law@1",),  # FR-51's block (D371).
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
                "cells.models.assembly_lineages_v2.geometry",
                "cells.models.assembly_lineages_v2.exchange",
                "cells.models.assembly_lineages_v2.permeation",
                "cells.models.assembly_lineages_v2.lumen",
                "cells.models.assembly_lineages_v2.population",
                "cells.models.assembly_lineages_v2.prescribed_shell",  # FR-21 (D244, D246)
                "cells.models.assembly_lineages_v2.shell_permeation",  # FR-21
                "cells.models.assembly_lineages_v2.gate_factor",  # FR-21
                "cells.models.assembly_lineages_v2.pore_nucleation",  # FR-31 (D287)
                "cells.models.assembly_lineages_v2.rate_equations",  # OL6 (D304)
            ),
            operator_homes=(
                "cells.models.assembly_lineages_v2.division",
                "cells.models.assembly_lineages_v2.transfer",
                "cells.models.assembly_lineages_v2.replacement",  # FR-20 (D240)
                "cells.models.assembly_lineages_v2.withdrawal",  # FR-35 (D261)
                "cells.models.assembly_lineages_v2.tension_hold",  # FR-31 (D287)
                "cells.models.assembly_lineages_v2.size_division",  # OL6 S7 (D304)
            ),
            interfaces=(
                "cells.reaction_law@1",
                "cells.rate_factor_law@2",
                "cells.free_energy_term@1",
                "cells.assembly_geometry@1",
                "cells.assembly_operator@1",
                "cells.population_structure@1",
                "cells.assembly_hazard@1",  # FR-31 (D287)
                "cells.assembly_representation@1",  # OL6 (D304)
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
