# ATP-driven transporters (`cells.transporter@1`)

**In one sentence:** Membrane pumps that each spend one ATP molecule per cycle to move a fixed number of one kind of molecule or ion across a membrane, even against its gradient.

## In plain words

Cells push many molecules "uphill", from where they are scarce to where they are plentiful, and
pay for it with ATP, the cell's energy currency. This [kind](../../GLOSSARY.md#kind) is the
machinery Cells uses to run such [pumps](../../GLOSSARY.md#pump) in the tissue model. Each pump
population sits on one membrane patch. In every cycle it splits one ATP into ADP and phosphate on
the cell's side, and moves a fixed number of its cargo to the other side. A pump runs forward only
while the energy freed by ATP exceeds the energy its cargo needs to move; otherwise it stalls or
runs backward. The kind keeps the books, counting cycles, heat and the work drawn from the fuel, so
that matter and energy add up at every step. It hosts fourteen laws today: four pumps and
cotransporters, one exchanger, and nine of the mitochondrion's, from respiration to ATP synthase.

## Seen from each field

- **Biology:** primary active transport, such as the proton pump that acidifies a compartment
  (FR-4).
- **Chemistry:** ATP hydrolysis coupled to transport in one cycle. The cycle's free energy sets its
  direction, and saturation in the cargo and in ATP sets its speed.
- **Physics:** an energy converter whose heat is the cycle rate times minus the cycle's free
  energy.
- **Computing:** a module that registers fields and hook functions, which the inner model calls at
  fixed points of each step. Its laws are pure kernels that it finds in the law registry.

## At a glance

<!-- generated: at-a-glance -->

| | |
| --- | --- |
| Piece | Kind, interface `cells.kind@1` ([its fields](../../DECLARATIONS_FORMAT.md#kinds)) |
| ID | `cells.transporter@1`; definitions write `cells.transporter@1` |
| Runs in | `cells.resolved_pump_tissue@3`, its host, which definitions write `resolved_pump_tissue@3`. Definitions of `cells.resolved_pump_composite@1` and `cells.resolved_pump_tissue@3` can declare it, under the key `transporters` |
| Laws it hosts | `cells.adenylate_kinase@1`, `cells.atp_driven_transporter_mass_action_positive@1`, `cells.cytochrome_c_oxygen_proton_cycle@1`, `cells.electrogenic_nucleotide_exchange@1`, `cells.held_reductant_supply@1`, `cells.na2_anion_symport_diagram@1`, `cells.na_anion_symport_factored@1`, `cells.nadh_ubiquinone_proton_cycle@1`, `cells.phosphate_proton_symport@1`, `cells.potassium_proton_exchange@1`, `cells.proton_atp_mass_action_positive@1`, `cells.proton_coupled_atp_synthesis_cycle@1`, `cells.sodium_calcium_exchange_symmetric_barrier@1` and `cells.ubiquinol_cytochrome_c_proton_cycle@1` |
| Provenance | Not yet extracted: the kind contract has no provenance field yet |

<!-- /generated -->

## What it reads and changes

<!-- generated: touches -->

| Field | Role | Axes | Unit | Record | Which way is positive |
| --- | --- | --- | --- | --- | --- |
| `transporter_cycles` | Owns | membrane_slot | fmol | cumulative | From inside to outside: "a positive cycle moves n (the stoichiometry) of the role from the patch's cell to its outside node; held fuel's maintenance restores its ATP (transporter_fuel_supplied_fmol)" |
| `transporter_dissipated_energy_pJ` | Owns | membrane_slot | pJ | cumulative | Not stated |
| `transporter_metabolic_work_pJ` | Owns | membrane_slot | pJ | cumulative | Not stated |
| `transporter_fuel_supplied_fmol` | Owns | species, membrane_slot | fmol | cumulative | Not stated |
| `transporter_cycle_rate_fmol_s` | Provides | | fmol/s | rate | From inside to outside: "a positive cycle moves n (the stoichiometry) of the role from the patch's cell to its outside node; held fuel's maintenance restores its ATP (transporter_fuel_supplied_fmol)" |
| `transporter_cycle_free_energy_J_mol` | Provides | | J/mol | level | Not stated |
| `transporter_chemical_drive_J_mol` | Provides | | J/mol | level | Not stated |
| `transporter_availability` | Controls | | Not stated | | |

Ledgers: not yet extracted. Energy roles: not yet extracted. Its records are on the `pumps` layer.

<details><summary>For developers</summary>

Hooks: `bound_rate`, `check_definition`, `control_values`, `declared_fields`, `domain`, `held_rows`, `initial`, `label_refusals`, `label_transfers`, `ledger_terms`, `material_term`, `moved_rows`, `one_way_fluxes`, `one_way_nets`, `parse`, `parse_schedule`, `rates`, `readouts`, `role_species`, `schedule_to_dict`, `stage_term`, `standard_free_energies`, `structure_entry`, `to_dict` and `view_sets`. Layout fields: `transporter_present`, `transporter_neutral`, `transporter_proton`, `transporter_role`, `transporter_fuel_rows`, `transporter_held`, `transporter_capacity_fmol_s`, `transporter_stoichiometry`, `transporter_km_role_mM`, `transporter_km_atp_mM`, `transporter_drive0_J_mol`, `transporter_c0_mM`, `transporter_ph_ref` and `transporter_ph_band`. Experiment keys: `transporter_controls`.

</details>

<!-- /generated -->

## The mathematics

<!-- generated: bounds -->

None declared by the kind; each law it hosts declares its own.

<!-- /generated -->

For one population with [stoichiometry](../../GLOSSARY.md#stoichiometry) $n$ (1 to 4), one cycle
turns ATP into ADP and phosphate at the patch's inside cell, and moves $n$ of its cargo from the
inside of the patch to its outside. For an uncharged cargo the
[cycle free energy](../../GLOSSARY.md#cycle-free-energy) is

$$\Delta G_\text{cyc} = \Delta_r G'_\text{ATP} + n R T \ln\frac{c_\text{out}}{c_\text{in}}, \qquad \Delta_r G'_\text{ATP} = \Delta_r G'^\circ + R T \ln\frac{c_\text{ADP}\, c_\text{Pi}}{c_\text{ATP}\, c^\circ}$$

where $\Delta_r G'^\circ = \mu'^\circ_\text{ADP} + \mu'^\circ_\text{Pi} - \mu'^\circ_\text{ATP}$
comes from the species registry's standard potentials at its standard concentration $c^\circ$,
never from a parameter. The proton law adds its charge's electrical term (its own page). Each
hosted law gives the cycle rate $J$; for each population the kind books:
- the cargo's transfer, $n J$ from inside to outside, into the shared
  [inventory](../../GLOSSARY.md#inventory);
- the [heat](../../GLOSSARY.md#heat), $-J\,\Delta G_\text{cyc}$;
- with held fuel, the [work](../../GLOSSARY.md#work) $-J\,\Delta_r G'_\text{ATP}$ drawn from the
  maintenance, and the supply of one ATP restored per cycle, kept as a record: the held rows never
  move.

- **Domain:** a population is refused at a stage where $|\Delta G_\text{cyc}/RT| > 80$, where an
  input is not positive, or, under the proton law, where the inside pH leaves its declared band.
- **Version 1:** one population per patch; the fuel at the patch's inside cell; finite fuel
  refused.
- **Not here:** the rate laws, which are the hosted laws'.

## Sources

<!-- generated: provenance -->

Provenance: not yet extracted; the kind contract has no provenance field yet.

<!-- /generated -->

- **The kind is Cells' own design:** the inner model's transporter kind
  ([the inner-model design](../../../INNER_MODEL_V4_DESIGN.md), §7.4 (g) 2 and (k)) and FR-4's
  pump ([the compartment pH design](../../../COMPARTMENT_PH_TRANSFER_DESIGN.md), §5–6), as its
  module states. Relayed; not read again here.
- **Each hosted law declares its own citation.** Both cite the sodium–potassium pump law's
  mass-action form in Cells' own documents, and take no numbers.
- **The standard potentials** come from the species registry's records, which carry their own
  sources.

## How it is checked

<!-- generated: tests -->

Declared test: not yet extracted; the kind contract has no test field yet.

<!-- /generated -->

Its tests run a one-cell world through the runner. The cargo lands in the shared inventory, the
held fuel rows never change, the maintenance's record follows the cycles, and all ten
[ledgers](../../GLOSSARY.md#ledger) close with the kind's terms. A planted flip of the cargo's
direction must fail the material ledger. Other tests check that a malformed declaration is refused
with its reason, that a change of values reuses the built implementation, and that the law's domain
and the pH band refuse at the stage.

## Status

<!-- generated: status -->

Not stated: no record states a level for this piece.

<!-- /generated -->

## Links

<!-- generated: links -->

- Declared in [`src/cells/kinds/transporter.py`](../../../../src/cells/kinds/transporter.py) (`cells.kinds.transporter`).
- Hosts `cells.adenylate_kinase@1`, `cells.atp_driven_transporter_mass_action_positive@1`, `cells.cytochrome_c_oxygen_proton_cycle@1`, `cells.electrogenic_nucleotide_exchange@1`, `cells.held_reductant_supply@1`, `cells.na2_anion_symport_diagram@1`, `cells.na_anion_symport_factored@1`, `cells.nadh_ubiquinone_proton_cycle@1`, `cells.phosphate_proton_symport@1`, `cells.potassium_proton_exchange@1`, `cells.proton_atp_mass_action_positive@1`, `cells.proton_coupled_atp_synthesis_cycle@1`, `cells.sodium_calcium_exchange_symmetric_barrier@1` and `cells.ubiquinol_cytochrome_c_proton_cycle@1`.
- Runs in `cells.resolved_pump_tissue@3`.
- Manifest entry: (kind, `cells.transporter@1`), from `python -m cells declarations --out FILE` ([the format](../../DECLARATIONS_FORMAT.md)).
- In the Laws library: `select=laws:cells.transporter@1`.

<!-- /generated -->
