<!-- Generated from lean/registry.json and lean/claims.json. -->

# Engine law coverage

Each row links to a Cells registry declaration. The proof column lists named claims about that piece. The comparison column links to runs that exercised it, including runs checking another property. Open means the Cells claim register has no entry in that column. [Proof index](README.md#proof-index) · [Registry inventory](registry.json)

## Registered laws

Direct Lean claims cover 2 of 27 registered laws. Recorded numerical comparisons exercise 2.

| Law | Direct Lean claims | Recorded comparisons |
| --- | --- | --- |
| [`cells.atp_driven_transporter_mass_action_positive@1`](../src/cells/laws/pumps/atp_transporter.py#L165) | Open | Open |
| [`cells.ca_atp_mass_action_positive@1`](../src/cells/laws/pumps/ca_atp_mass_action_positive.py#L150) | Open | Open |
| [`cells.constant_field@1`](../src/cells/laws/routes/constant_field.py#L13) | [Reversing a junction reverses its flux](claims/junction-flux-reversal.md) · [At equal voltage, junction flux follows the concentration gradient](claims/junction-concentration-gradient.md) · [A blocked junction carries zero flux](claims/junction-blocking.md) | [junction](https://github.com/Eidosoma/Cells/blob/627c376c463ae66c0f9e53db6dbb1374ec8ac1fd/lean/README.md#cpu-comparison) |
| [`cells.gard_catalysis_pair_consistent@1`](../src/cells/models/assembly_lineages/gard.py#L208) | Open | Open |
| [`cells.gard_catalysis_single_event@1`](../src/cells/models/assembly_lineages/gard.py#L174) | Open | Open |
| [`cells.ideal_mixing@1`](../src/cells/models/assembly_lineages_v2/ideal_mixing.py#L109) | Open | Open |
| [`cells.junction_voltage_relaxation@1`](../src/cells/laws/junctions/junction_voltage_relaxation.py#L100) | Open | Open |
| [`cells.kir2p1_mh2@1`](../src/cells/laws/channels/kir2p1_mh2.py#L47) | Open | Open |
| [`cells.kleak_always_open@1`](../src/cells/laws/channels/kleak_always_open.py#L13) | Open | Open |
| [`cells.kv1p1_mh2@1`](../src/cells/laws/channels/kv1p1_mh2.py#L62) | Open | Open |
| [`cells.kv1p2_mh@1`](../src/cells/laws/channels/kv1p2_mh.py#L62) | Open | Open |
| [`cells.kv1p3_mh@1`](../src/cells/laws/channels/kv1p3_mh.py#L62) | Open | Open |
| [`cells.kv1p4_mh@1`](../src/cells/laws/channels/kv1p4_mh.py#L61) | Open | Open |
| [`cells.kv1p5_mh@1`](../src/cells/laws/channels/kv1p5_mh.py#L47) | Open | Open |
| [`cells.kv1p6_mh@1`](../src/cells/laws/channels/kv1p6_mh.py#L61) | Open | Open |
| [`cells.logmean_electrodiffusion@1`](../src/cells/laws/routes/logmean_electrodiffusion.py#L14) | [Extracellular face flux follows the electrochemical potential drop](claims/extracellular-face-direction.md) · [Passive extracellular face transport dissipates energy](claims/extracellular-face-dissipation.md) | [regional-chain](https://github.com/Eidosoma/Cells/blob/9252236d3f6339d4dfdd18fd79fc1d73246faf7e/lean/PROGRESS.md#19-november-2026--regional-reaction-and-transport-balance) · [extracellular-face](https://github.com/Eidosoma/Cells/blob/0c2e9f962480f430c2383bb1dddf97477f434335/lean/PROGRESS.md#19-november-2026--extracellular-face-electrodiffusion) |
| [`cells.nak_atp_mass_action_positive@1`](../src/cells/laws/pumps/nak_atp_mass_action_positive.py#L153) | Open | Open |
| [`cells.naleak_always_open@1`](../src/cells/laws/channels/naleak_always_open.py#L13) | Open | Open |
| [`cells.nav1p2_m3h_regularized@1`](../src/cells/laws/channels/nav1p2_m3h_regularized.py#L47) | Open | Open |
| [`cells.passive_neutral_permeation@1`](../src/cells/laws/routes/passive_permeation.py#L97) | Open | Open |
| [`cells.proton_atp_mass_action_positive@1`](../src/cells/laws/pumps/proton_pump.py#L257) | Open | Open |
| [`cells.proton_constant_field_leak@1`](../src/cells/laws/transport/proton_leak.py#L52) | Open | Open |
| [`cells.rapid_binding@1`](../src/cells/laws/reactions/rapid_binding.py#L581) | Open | Open |
| [`cells.regular_mixing@1`](../src/cells/models/assembly_lineages_v2/regular_mixing.py#L153) | Open | Open |
| [`cells.reservoir_exchange@1`](../src/cells/models/assembly_lineages/exchange.py#L64) | Open | Open |
| [`cells.stochastic_mass_action@1`](../src/cells/models/assembly_lineages_v2/mass_action.py#L143) | Open | Open |
| [`cells.transition_state_factor@1`](../src/cells/models/assembly_lineages_v2/transition_state.py#L154) | Open | Open |

## Registered operators

Direct Lean claims cover 1 of 22 registered operators. Recorded numerical comparisons exercise 1.

| Operator | Direct Lean claims | Recorded comparisons |
| --- | --- | --- |
| [`cells.cell_owned_compartments@1`](../src/cells/operators/compartments.py#L603) | Open | Open |
| [`cells.cytoplasmic_bridge_closure@1`](../src/cells/operators/bridge_closure.py#L272) | Open | Open |
| [`cells.daughter_continuation@1`](../src/cells/models/assembly_lineages/continuation.py#L55) | Open | Open |
| [`cells.electrode_current_injection@1`](../src/cells/operators/current_injection.py#L244) | Open | Open |
| [`cells.ideal_osmosis_linear_compliance_water@1`](../src/cells/operators/osmotic_water.py#L489) | Open | Open |
| [`cells.isopotential_partition@1`](../src/cells/operators/partition.py#L1110) | Open | Open |
| [`cells.k_anion_symport_mass_action@1`](../src/cells/operators/k_anion_symport.py#L167) | Open | Open |
| [`cells.local_species_reactions@1`](../src/cells/operators/species_reactions.py#L1244) | [Balanced reactions preserve a weighted inventory](claims/reaction-inventory.md) · [Binding and catalysis conserve enzyme and substrate](claims/enzyme-inventories.md) | [closed-enzyme](https://github.com/Eidosoma/Cells/blob/9c0b99d30676863d67dd8d30efea6ae490f2bd40/lean/PROGRESS.md#19-november-2026--closed-enzyme-reactions) · [regional-chain](https://github.com/Eidosoma/Cells/blob/9252236d3f6339d4dfdd18fd79fc1d73246faf7e/lean/PROGRESS.md#19-november-2026--regional-reaction-and-transport-balance) |
| [`cells.membrane_entity_state@1`](../src/cells/operators/membrane_state.py#L182) | Open | Open |
| [`cells.restricted_cleft_lumen@1`](../src/cells/operators/restricted_lumen.py#L401) | Open | Open |
| [`cells.restricted_cleft_lumen@2`](../src/cells/operators/restricted_lumen_v2.py#L298) | Open | Open |
| [`cells.scheduled_bath_composition@1`](../src/cells/operators/bath_schedule.py#L541) | Open | Open |
| [`cells.scheduled_cell_replacement@1`](../src/cells/operators/cell_replacement.py#L613) | Open | Open |
| [`cells.scheduled_cell_replacement@2`](../src/cells/operators/cell_replacement_v2.py#L346) | Open | Open |
| [`cells.scheduled_membrane_insertion@1`](../src/cells/operators/membrane_insertion.py#L468) | Open | Open |
| [`cells.scheduled_membrane_insertion@2`](../src/cells/operators/membrane_insertion_v2.py#L263) | Open | Open |
| [`cells.scheduled_membrane_trafficking@1`](../src/cells/operators/membrane_trafficking.py#L814) | Open | Open |
| [`cells.scheduled_species_exchange@1`](../src/cells/operators/species_exchange.py#L452) | Open | Open |
| [`cells.scheduled_species_turnover@1`](../src/cells/operators/species_turnover.py#L415) | Open | Open |
| [`cells.site_occupancy@1`](../src/cells/operators/site_occupancy.py#L1177) | Open | Open |
| [`cells.size_threshold_fission@1`](../src/cells/models/assembly_lineages/fission.py#L71) | Open | Open |
| [`cells.species_regulated_availability@1`](../src/cells/operators/species_regulated_availability.py#L851) | Open | Open |
