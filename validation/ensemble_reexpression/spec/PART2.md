# Part 2: the four calcium clusters, and the four assembly-regulated ones

`CRITERIA.md`, `TABLE.md`, `AMENDMENT-1-2026-11-25.md` and the rules of `README.md` hold here. This file states what Part 2 needs beyond them. **Where it differs from Part 1 it says so, and why (§16), and it governs for the eight consumers of Part 2.** Part 1's files do not move. `inputs_part2.json` governs the numbers, and `PART2_BLOCKS.md` prints its literal blocks. `PART2_EXPORTER.md` holds the sections that the exporter's builder receives, word for word, and the builder does not receive this file (§7 and §14 hold the plants).

**Status, 25 November 2026:** complete for its independent auditor. The rows that waited on two design notes are answered (§0), from the lead's rulings of 25 November and from the names that the notes' author and the store worlds' builder gave the author. The author read neither note, nor any builder's branch, nor a run of the engine. It is revised directly until its tag. Nothing of a run of either side enters a bound.

## 0. What was open, and how it is answered

**Fixed (the lead, 25 November 2026), and all of it keeps the ensemble's equations:**
- the calcium channels stay channel populations of the inner model, whose law declares its ions' valences;
- both calcium pumps (the store's and the plasma one) are one cycle law on the transporter kind;
- the store is a compartment with its own capacitor in a closed world;
- the exchanger is one monomial law module;
- the buffers are today's mass action, as local reactions;
- the release is a passive route with a factor source that is read at each stage;
- the assembly sets the K channel's availability.

| What was open | The answer | Where |
| --- | --- | --- |
| Every readout's declared order, the heats' above all | 2 for every S entry, the heats included (the composite's formal order, by ruling 5). Each heat's booking has the order of the transfer it belongs to | §4.2 |
| The step ladder | It stands: 12.5, 6.25 and 3.125 µs, and 1.5625 µs for the retry. The composite admits each of them (the answers) | §4.1 |
| The names, the axes and the signs that the exporter reads, and how a compartment's amounts are booked | By name. **A store is an outside node of the inner model, with that node's slot** | §6 |
| A reaction's heat | It has no canonical field. The engine books a node's reactions together, so the heats are compared **per compartment** (ruling 1) | §6 |
| The pumps' standard free energy | The cycle law declares none. **The exporter forms the one-molar number** from three potentials (ruling 2) | §2.2 |
| The factor source's form and its inputs | The species condition kind with a product of Hill factors. It reads the cell's own free rows over the cell's volume, at every explicit stage of the inner step, from that stage's amounts (the answers) | §3, condition 3 |
| An off-grid change of a channel control on the composite | It splits the composite's IMEX step, and the accepted times hold every switch (ruling 6) | §4.1 |
| The strings note's labels | Named by piece (ruling 8) | §4.3 |
| The field solver | D147's rule: the floor variant for all eight worlds, each of which has free field offsets | §4.1 |
| Restarts and engine plants | One restart and two engine plants | §11 |
| `amount_refs` and the closure, with the margins re-formed | By Part 1's rules, and from the engine's own charge tolerance | §8, §7.4 |
| An entry that the retry's triple leaves unresolved or mixed | A rule, from the author's arithmetic (ruling 10) | §13 |

**What the answers do not settle,** and §3 therefore makes a condition: that calcium's junction route carries the junction's gate and availability (condition 8).

## 1. The consumers, and their equations

| Consumer | Captured world | Canonical form | Equations | Integrator, declared order |
| --- | --- | --- | --- | --- |
| `spatial_calcium` | the buffered store over the JUPITER cluster with Ca | the composite over the inner model: one compartment per cell with its capacitor, Ca's plasma leak, junction route and store leak as passive routes, K's store leak, the release with its factor, the store's pump, the buffers as local reactions | **same** (§3) | IMEX, Strang halves, order 2 |
| `plasma_calcium` | + a plasma calcium pump and the exchanger | + the cycle law and the exchanger law | same | IMEX, order 2 |
| `gated_calcium` | + a Cav1.2-type channel | + a channel population that carries Ca²⁺ | same | IMEX, order 2 |
| `ip3_calcium` | + free IP3 with its buffer, and the IP3 factor on the release | + the factor source's second species | same | IMEX, order 2 |
| `cluster_spatial_calcium` | the first with two assembly pools a world, 2 worlds a seed | the first with a pool per cell, whose availability multiplies the K channel | same | IMEX, order 2, with the pool exact |
| `cluster_plasma_calcium`, `cluster_gated_calcium`, `cluster_ip3_calcium` | the others the same way | the others the same way | same | the same |

**The availability multiplies the K channel alone.** It never touches the calcium channel, the pumps, the exchanger or the release.

**The first four are called the children,** and the last four the clusters. A cluster's child is the one that `inputs_part2.json` names as `same_as`.

## 2. What a canonical definition must hold, by name and value

**The rule is Part 1's** (`SPEC.md` §2): a world's blocks are the content of the captured definition, value for value. A candidate's definition holds it, and the exporter writes it back from the definition that the engine parsed and ran (`TABLE.md` §3). `PART2_BLOCKS.md` says which blocks an ionic run's `inputs` holds, and prints them.

### 2.1 By name

Besides Part 1's keys (`SPEC.md` §2.1), with Ca (valence +2) as a fourth species of `ionic`:

| In the block | In the canonical definition |
| --- | --- |
| `stores.<cell>.law`, `temperature_K`, `standard_concentration_mM` | The reactions' passive mass-action law. The model's one standard concentration, **1 mM**, which the reactions and the fuel rows read. Another number is a departing echo |
| `stores.<cell>.species` | The chemical rows, each with its valence and its standard potential over RT at 1 mM: Ca (+2), B (−2), CaB (0), Ca2B (+2), K, Na, Cl, and in `ip3_calcium` IP3 (−3), IP3_buffer (0) and IP3_bound (−3) |
| `stores.<cell>.compartments` | `cytosol`: the cell's own rows and volume, whose Na, K, Cl and Ca are also the cell's in `ionic`. `er`: the store's, an outside node of the inner model with the compartment law |
| `stores.<cell>.reactions` | For each reaction: its compartment, its reactants and products, its forward rate. The reverse rate is the forward one times exp(Σ products' − Σ reactants' standard potentials). A canonical reaction may be declared once for several sites. The exporter writes each site's under the captured ID, by its stoichiometry and its compartment |
| `stores.<cell>.membrane` | The bounding patch: area, capacitance, initial voltage (the store's potential less the cytosol's) and charge, the permeability of every row (Ca and K alone are non-zero), the pump and the release. **K's permeability is the patch's own. Ca's is a passive route's** |
| `...membrane.pump`, `plasma_transport.<membrane>.pump` | One cycle law on the transporter kind, N at the cell: one Ca a cycle. Capacity, the two constants, the held ATP, ADP and Pi in mM, and the standard free energy **at a 1 M standard state**, which the exporter forms (§2.2) |
| `...membrane.release` | A passive route of Ca on the bounding patch, its permeability, and the two Hill reads of free Ca in its factor: an activation (half saturation, coefficient) and an inhibition |
| `plasma_transport.<membrane>.exchanger` | The exchanger law on the transporter kind: 3 Na in and 1 Ca out a forward cycle. Capacity and the two constants |
| `calcium_channels.<id>` | A channel population of the inner model: membrane, species Ca, its law, maximal permeability, abundance and initial gates in the law's order |
| `ip3_release.<cell>` | The third Hill read of the release's factor: an activation by free IP3 |
| `calcium_controls` | The schedules of the calcium pieces. Every one is [[0.0, 1.0]] |
| `ionic.membranes.<m>.passive`, `ionic.junctions`, `ionic.faces`: the Ca entry | The plasma leak and the junction's Ca permeability are passive routes (the junction's with condition 8 of §3). The faces' Ca diffusivity is the face law's own |

**The release may be one condition that reads both species, or two** (ruling 7). Either gives the same factor, and the block is the same. The build names which, and it is recorded in `definition`.

### 2.2 Derived declarations, by rule

- **Capacitances** are area × specific capacitance, the double product, as in Part 1.
- **Charges.** A cell's `initial_charge_C` is its membrane's capacitance times its initial voltage, as in Part 1, since its store's voltage is 0 at time 0. A store's is 0. **`initial_voltage_V`** of a cell is derived by the exporter as its charge over its membrane's capacitance, and of a store as its charge over its own.
- **The pumps' standard free energy at 1 M.** The exporter forms it from **three standard potentials of the fuel rows, those of ATP, ADP and Pi** (`standard_mu_RT`), and the model's one standard concentration c° in mM:

      delta_g0_at_1M_J_per_mol = R T [ μ°(ADP) + μ°(Pi) − μ°(ATP) + ln(1000/c°) ]

  since a potential is μ° + ln(c/c°), and a 1 M standard state is c° = 1000 mM. The captured number is the one for the numeric-mM quotient (−37,000 J/mol for every pump), and R T ln 1000 is added to it (−19,875.97 J/mol at 298.15 K). Only the combination is compared, and no single potential is.
- **Fixed charges.** A cell's and a store's are the builder's, by the model's own anchor rule, from the node's charge and **every** row of the node, B, Ca2B and the IP3 rows with it. They are recorded and not compared, since the captured ones refer to Na, K, Cl and Ca alone. The outside regions' (`local`, `near`, `far`) are compared, as in Part 1.
- **The controls** of the captured definitions are 1 at all times (`calcium_controls`).

### 2.3 What the captured form holds and the blocks do not, and why

- **IDs** of entities, of the store's membrane and of every model and law, and `calcium_species`: the maps' keys, or a label.
- **`moieties`** (what each chemical row is made of): they follow from the reactions, and §9's identities use them.
- **The pumps' `metabolism`:** the held fuel rows are the canonical form of it.
- **`delta_g0_J_per_mol`** of the calcium pumps and `specific_capacitance_F_per_m2`: the derived numbers of §2.2 replace them.
- **The execution's** capacities, step, backend and solver, and the observation at 7.3 × 10⁻⁵ s, as in Part 1 (`SPEC.md` §2.3).

### 2.4 The echo's precision

`SPEC.md` §2.4 holds, and:
- **`delta_g0_at_1M_J_per_mol`** is compared within 10⁻¹² of itself **plus 16 ε R T A,** with A = |μ°(ATP)| + |μ°(ADP)| + |μ°(Pi)| + |ln(1000/c°)| of the candidate's own potentials. The exporter writes the three potentials and c° beside it, as two more keys of `pump`: `fuel_standard_mu_RT`, an object with `ATP`, `ADP` and `Pi`, and `standard_concentration_mM`. Without them the second term is 0. **The derivation** of the second term, in units of ε/2 R T A: forming R T, the logarithm, three additions and the product take at most 11. The builder's potentials, which must give the captured number, take at most 8. The registered number's own forming takes at most 9. They add to 28, which is 14 ε, and 16 ε is the power of two above. The term matters only where A is above 2,000, since below it 10⁻¹² is the larger.
- **More defaults:** a zero permeability, and any schedule of `calcium_controls`, may be omitted.
- **`standard_mu_RT`** to 10⁻¹² of itself. A declared zero is exactly zero.
- **Other rows.** A row that the block does not name (the fuel rows) is recorded, and refuses nothing. The exporter lists in `definition` every species row that the definition declares.

## 3. When it is the same equations, and when it is a changed model

**It is "same equations" only if all of these hold** (the builders say so for each consumer, before the registration tag):
1. **The world is closed:** one gauge (`local`), and no held bath.
2. **The store has its own voltage:** a free capacitive node between cytosol and store, with the captured area, specific capacitance and initial voltage.
3. **The release factor is read at every explicit stage of the inner step, from that stage's amounts:** the cell's own row of free Ca (and of IP3 in `ip3_calcium`) over the cell's volume, not over the store's. It multiplies the opening, which is the same equation as multiplying the permeability. A factor held through a step, or a two-state fraction, is a changed model. **The factor's form** is 1/(1 + (K_a/Ca)^n) × 1/(1 + (Ca/K_i)^m), and in `ip3_calcium` × 1/(1 + (K/IP3)^q), each a Hill term (read in the captured law's code).
4. **The pumps' standard state** is the one of §2.2.
5. **The exchanger's rate** is the captured symmetric-barrier law: 3 Na for 1 Ca, third powers in the sodium terms, a denominator of the captured product form, and no standard-state part.
6. **The reactions** are the same mass-action kernel: the same rate constants at 1 mM, the same standard potentials, the same stoichiometry.
7. **The Ca channel** carries Ca²⁺ by the constant-field law at valence 2 with P = P_max × abundance × availability × m² h, and the captured gate kinetics with their −10 mV shift and no temperature term.
8. **Calcium's junction route carries the junction's own open fraction:** the captured flux multiplies every species' permeability, Ca's with the others', by the relaxation gate and the availability (read in the captured code). A Ca route that does not is a changed model. The captured gate starts at 0.6, so it would differ by tens of per cent in `junction_Ca`. **The answers say that the Ca route is a passive route of its own, and not how it takes the gate. The builders say how.**
9. **The splitting** is an error of the candidate's order and not of the equations. The reactions are Strang halves around the inner step, whose stages start from the state after the first half.

**If any does not hold, the consumer is a changed model.** No band of this folder applies to it, and it is not judged here. It is judged by the consumer's own registered criterion
(the calcium ensemble's independent reference at 3 × 10⁻⁹ relative and 3 × 10⁻¹² absolute, §12) or by a reference written for it, in a **new registration** that the user approves. The Part 2 tag records which consumers are which, before any run.

## 4. What a candidate declares

### 4.1 Steps, solver and controls

| Item | Value |
| --- | --- |
| Model | The composite over the inner tissue model, version 3, with the kinds and operators of §4.3 |
| Integrator | The IMEX scheme ARS(2,2,2) (label `imex`), with Strang halves for the composite's splits. **Declared order 2 for every S entry** (§4.2) |
| Steps | h₁, h₂, h₃ = 12.5, 6.25, 3.125 µs. Retry 1.5625 µs. The captured h, h/2, h/4 are the same 12.5, 6.25 and 3.125 µs |
| Grid | `SPEC.md` §4's rule. The worst registered time of Part 2 differs from its grid point by 1.0 ε t, inside the rule's 2 ε t, at each of the four steps |
| An off-grid change | The changes are the pools' events. Each splits the composite's IMEX step, as it splits the inner model's. The accepted times hold every switch, as its own double, and the `steps` and the `switch_list` follow Part 1's rules (`TABLE.md` §3, `CRITERIA.md` §4.1): a child's `steps` as `jupiter`'s, a cluster's as `base`'s. A switch on a grid point makes no step. The clock's two rules hold: one inside its same-instant tolerance snaps, and a near miss (10⁻⁶ of a step) is refused. **The smallest distance of an event of worlds 0 and 1 from a grid point or a step's middle, over the four steps, is 6.8 × 10⁻⁴ of a step** (seed index 3, `cell_1`, world 1, the fourth event, at 0.0054250085078218005 s and 12.5 µs; of 89 events), so no event is a near miss |
| Gauge | `local`, 0 V, closed |
| Observations | On the grid, at the block's `potential_times_s` (a cluster's `summary_times_s`) at least. A switch is also an admitted observation time |
| Field solver | **The floor variant** of the factored capacitor reduction (label `field_solver_floor`). Every world of this part has free field offsets (`near` and `far`), and a composite follows its inner model (D147, D156; `SPEC.md` §3.1). The builders apply the rule with `declare()`. The same step before the campaign applies (the floor guard with constants) |
| Heat booking | None is picked. Every kind books by its default, which has the declared order |
| Assembly clusters | The live pool's seeds and world IDs (worlds 0 and 1 of each of four seeds). An ionic run's schedule comes from its own resolution of the composed file's pools (Amendment 1, item 8). The event times are the pool's doubles |
| Rows | Every accepted row is recorded |

### 4.2 The declared order

- **2 for every S entry of the eight consumers,** the heats included (ruling 5: the composite's formal second order). `p` is 2 in every world of `inputs_part2.json`, and the window of `CRITERIA.md` §4.3 is [1.5, 4.5].
- **The legacy side is 4,** and unresolved for every entry (`legacy_part2.json`).
- **What the candidate's truncation may look like, so that nobody is surprised by it:** the store's K leak relaxes its voltage at about 5,260 s⁻¹, so dt × rate is 0.066 at 12.5 µs and 0.016 at 3.125 µs. Fast entries of the store may not be in their
  asymptotic range at 12.5 µs. The retry's triple starts at 6.25 µs. Order is judged; a truth that is out of range is inconclusive, and no window is widened for it.
- **The answers say that two fields must never be compared:** `reaction_energy_magnitude_pJ` and `reaction_outside_energy_magnitude_pJ`. They are running rounding budgets. They depend on the step and converge to nothing.

### 4.3 Strings labels added to the note

| Label | The piece | Where a block shows it |
| --- | --- | --- |
| `composite_model` | the composite | |
| `imex` | the IMEX scheme ARS(2,2,2) | |
| `field_solver_floor` | the floor variant of the field solver | |
| `passive_routes_kind`, `transporter_kind`, `species_condition_kind` | the three kinds | |
| `compartment_law` | the store's compartment, a declaration alone | |
| `local_reactions` | the reactions' operator | |
| `mass_action_passive` | the buffers' law | `stores.<cell>.law` |
| `calcium_pump_positive` | the one cycle law of both calcium pumps | `...pump.law` |
| `exchanger_3na_1ca` | the exchanger's law | `...exchanger.law` |
| `cav12_m2h` | the calcium channel's law | `calcium_channels.<id>.kinetic_law` |
| `hill_product_factor` | the condition's product of Hill factors | `...release.law`, `ip3_release.<cell>.law` |
| `passive_constant_field` | the passive routes' constant-field law | |
| `assembly_observable` | Part 1's | |

Part 1's labels of the inner world stand (`kv15_mh`, `nak_pump_positive`, `maintained_fuel`, `junction_relaxation`, `logmean_face`, `constant_field`, `closure`, and the pool's). **The note comes after the build** (ruling 8). If the build declares a string that no label here names, the lead adds the label by a dated line, before any run. `delta_g0_at_1M_J_per_mol` carries no ID. A pool run's entry is Amendment 1's item 8.

### 4.4 The consumers' tables

One file per consumer: `table_<consumer>.json` for the eight names of §1, in the folders of `TABLE.md` §1. `part` is 2.

## 5. Compared times, worlds and sets

- **The children:** every 12.5 µs from 0 to 1 ms (81 rows), then every 100 µs from 1.1 to 20 ms (190 rows), 271 rows (`history_times`). The rows up to 1 ms resolve the store's fast modes. The potentials at `potential_times_s`.
- **The clusters:** 0.02 s for every entry, and 2.5, 5, 10, 15 and 20 ms (`summary_times_s`) for `voltage`, `store_voltage`, `channel_K_summary` and the four free cytosolic ions (`cyt_Na_summary`, `cyt_K_summary`, `cyt_Cl_summary`, `cyt_Ca_summary`), where the captured summaries exist. A `_summary` entry's scale, reference and closure are its own series'. The row at 0.02 s is in both, so one difference there fails both entries.
- **A family** is the three runs of one world (a child), or of one seed and world ID (a cluster), at h₁, h₂, h₃: one a child, eight a cluster.
- **World IDs 0 and 1** of each of four seeds (`cluster_*`). Their pools are worlds 0 and 1 of `base`, bit for bit (the 19 arrays of the four clusters, at every seed and captured step: 912 comparisons, all equal). So **the reference path of a cluster's world is `reference_paths.json`'s of `base`,** the same seed, cell and world. The 19 arrays and the exposure are the cluster's own captured checkpoint's (READOUTS §4 and §5, as `base`'s: `[world, cell, ...]`).

### 5.1 The two sets of a cluster

**Each cluster is reported in two sets,** as `base` is (`CRITERIA.md` §8), and here the sets are whole seed indices. A prototype had run the pools of `base` s0 w0 and s0 w1, which are the two worlds of every cluster's seed index 0.
- **Set A, not blind on its pools:** seed index 0. Its pool run and its two families.
- **Set B, blind:** seed indices 1, 2 and 3. Three pool runs, six families, and the cluster's plants and engine plant.
- **The verdict of a cluster is the worse of its two sets' verdicts.** Set B must pass by itself, with every mechanism tested by a home entry of one of its families. Set A adds nothing to a pass. No run belongs to both sets, and no plant of a cluster is scored on seed index 0.
- **The ionic entries of set A** are not affected by what was seen: by the lead's statements of 25 November no calcium world was run by a design author (the protocol's §11). They are in set A all the same, so that nothing rests on where the line is drawn. Those statements are to be confirmed at the Part 2 tag.
- **The four children** are one set, and blind by the same statements.

## 6. The readouts

**What governs.** READOUTS §1's orientations hold. The table below gives, for every row, its canonical source by name and sign, and the captured array. Entities are matched by ID. The captured index of an entity is its position in the captured definition's list, in natural order (`SPEC.md` §4), but for two axes that are in the **IDs' sorted order**: the chemical species (`B, Ca, Ca2B, CaB, Cl, K, Na`, and in `ip3_calcium` `B, Ca, Ca2B, CaB, Cl, IP3, IP3_bound, IP3_buffer, K, Na`) and the reactions (`bind_0_first`, `bind_0_second`, `bind_1_first`, `bind_1_second`, `ip3_binding`). The ionic species axis is (Na, K, Cl, Ca).

**The canonical axes** (the answers): cells, outside nodes, patches, channels, junctions, faces, species, transporter populations and species conditions keep the definition's order. **Passive routes do not: their axis is in the order of their IDs.** A reaction route is one reaction at one site, reaction by reaction, the cells first and then the outside nodes. `cycle_count` has a mode axis before the population's, and each population here has one mode. The exporter reads every axis from the parsed definition.

**The signs that the two codes book differently** (ruling 3):

| Row | Positive | Canonical | Captured |
| --- | --- | --- | --- |
| `store_leak_Ca`, `store_release` | into the store | **minus** the passive route's transfer, which is inward-positive, from the patch's outside node (the store) into its cell | same |
| `store_leak_K` | into the store | the bounding patch's own transfer, outward-positive, from the cell into its outside node: **no minus** | same |
| `leak_Ca` | into the cell | the passive route's transfer at the plasma patch, inward-positive: no minus | same |
| `junction_Ca` | from the junction's `from_cell` (the sender) | **minus** the passive route's transfer, which on a junction is positive from the receiver into the sender (the answers) | same |
| `ca_channel` | into the cell | **minus** the channel's transfer of Ca, which is outward | same |
| `store_pump`, `ca_pump`, `exchanger` | into the store, out of the cell, and 3 Na in with 1 Ca out | the population's forward cycles, N at the cell: no minus | same |
| `store_voltage` | the store's potential less the cytosol's | **minus** the observed voltage of the bounding patch, which is the owner's potential less the store's | same (`er_voltage_V`) |

### 6.1 The rows of the table

| Name | Unit | Entities | Canonical source | Captured source |
| --- | --- | --- | --- | --- |
| `n_out_x` (x = Na, K, Cl, Ca) | fmol | the regions `local`, `near`, `far` | `extracellular_amount_increment[x, region]`. The stores' slots of it are not regions | `extracellular_amount_increment[x, region]` |
| `leak_x` (Na, K, Cl) | fmol | membranes | as READOUTS §2 | as READOUTS §2 |
| `leak_Ca` | fmol | membranes | `passive_transferred[Ca, plasma route]` | `leak_transferred[Ca, membrane]` |
| `channel_K`, `pump`, `gate_m`, `gate_h`, `junction_gate` | | | as READOUTS §2 | as READOUTS §2 |
| `junction_x` (Na, K, Cl) | fmol | junctions | as READOUTS §2 | as READOUTS §2 |
| `junction_Ca` | fmol | junctions | minus `passive_transferred[Ca, junction route]` | `junction_transferred[Ca, junction]` |
| `face_x` (four) | fmol | faces | `face_transferred[x, face]` | `face_transferred[x, face]` |
| `cyt_c` (every chemical row c) | fmol | cells | the cell's row, `amount_increment[c, cell]` | `chemical_amount_increment[store, c, 0]` |
| `store_c` (every chemical row c) | fmol | cells | the store node's row, `extracellular_amount_increment[c, store node]` | `chemical_amount_increment[store, c, 1]` |
| `store_leak_Ca` | fmol | cells | minus `passive_transferred[Ca, store leak route]` | `er_passive_transferred[store, Ca]` |
| `store_leak_K` | fmol | cells | `membrane_transferred[K, bounding patch]` | `er_passive_transferred[store, K]` |
| `store_pump` | fmol of cycles | cells | `cycle_count[0, the store's population]` | `er_pump_transferred[store, 0]` |
| `store_release` | fmol | cells | minus `passive_transferred[Ca, release route]` | `er_release_transferred[store, 0]` |
| `ca_pump`, `exchanger` | fmol of cycles | membranes | `cycle_count[0, population]` | `plasma_pump_cycles[membrane]`, `plasma_exchange_cycles[membrane]` |
| `ca_channel` | fmol | calcium channels | minus `channel_transferred[Ca, channel]` | `calcium_channel_transferred[channel]` (inward) |
| `ca_gate_m`, `ca_gate_h` | 1 | calcium channels | `channel_gate` in the law's order m, h | `calcium_gate[0, channel]`, `calcium_gate[1, channel]` |
| `extent_r` | fmol | cells | `reaction_extent_fmol` of the route whose stoichiometry is r's, at the cell (`bind_0_*`, `ip3_binding`) or at the store's node (`bind_1_*`). Positive from reactants to products | `reaction_extent[store, r]` |
| `heat_leak` | pJ | membranes | `membrane_dissipated_energy_pJ[plasma patch]`: Na, K and Cl | none alone |
| `heat_leak_Ca` | pJ | membranes | `passive_dissipated_energy_pJ[plasma route]` | none alone |
| `heat_pump`, `heat_channel` | pJ | membranes, channels | as READOUTS §2 | none alone |
| `heat_junction_own` | pJ | junctions | `junction_dissipated_energy_pJ`: Na, K and Cl | none alone |
| `heat_junction_Ca` | pJ | junctions | `passive_dissipated_energy_pJ[junction route]` | none alone |
| `heat_face` | pJ | faces | `face_dissipated_energy_pJ` | `face_dissipated_energy_pJ[face]` |
| `heat_store_leak_Ca` | pJ | cells | `passive_dissipated_energy_pJ[store leak route]` | none alone |
| `heat_store_leak_K` | pJ | cells | `membrane_dissipated_energy_pJ[bounding patch]`, which carries K alone here | none alone |
| `heat_store_pump`, `heat_store_release` | pJ | cells | `cycle_dissipated_energy_pJ[population]`, `passive_dissipated_energy_pJ[release route]` | `er_transport_dissipated_energy_pJ[store, 1]`, `[store, 2]` |
| `heat_ca_pump`, `heat_exchanger` | pJ | membranes | `cycle_dissipated_energy_pJ[population]` | `plasma_dissipated_energy_pJ[0, membrane]`, `[1, membrane]` |
| `heat_ca_channel` | pJ | calcium channels | `channel_dissipated_energy_pJ[species, channel]`, **summed over its ions by the exporter** (ruling 4) | `calcium_channel_dissipated_energy_pJ[channel]` |
| `heat_reactions_cytosol` | pJ | cells | `reaction_dissipated_energy_pJ[cell]`: the cell's reactions together | **the sum, by the judge,** of `reaction_dissipated_energy_pJ[store, r]` over the reactions r of the cytosol (in `ip3_calcium`, `ip3_binding` with them) |
| `heat_reactions_store` | pJ | cells | `reaction_outside_dissipated_energy_pJ[store node]` | the same sum over the reactions of `er` |
| `work_pump`, `work_store_pump`, `work_ca_pump` | pJ | membranes, cells, membranes | `metabolic_work_pJ`, `cycle_metabolic_work_pJ[population]`. Recorded: §9's reported energy reads them | none |

**The potentials** (`potentials`, at `potential_t`): `voltage` (membranes: `membrane_voltage_V[plasma patch]`; captured `observations.plasma_voltage_V`, and `final_voltage_V` in the clusters' summaries), `phi_out` (regions but the gauge: `extracellular_potential_V[region]`; captured `observations.extracellular_potential_V`, children alone), and `store_voltage` (cells: minus `membrane_voltage_V[bounding patch]`; captured `observations.er_voltage_V`, and `calcium.er_voltage_V` in the summaries). They exist at observed rows alone, since no state field holds a voltage.

**The clusters' summaries.** `channel_K_summary`: `channel_transferred_fmol`. `cyt_x_summary`: `calcium.cytosol_amounts_fmol[x, cell]` **less the block's initial amount**, which the judge subtracts, since the summary holds amounts. The tick of a summary time t is t over the captured step.

### 6.2 What the judge forms

| Entry | From | Against |
| --- | --- | --- |
| `exchange_x`, the whole-cell ledger (4) | Σ over the cell's membranes of what crossed them inward, plus what the junctions brought: Na: `leak_Na` − 3 `pump` + 3 `exchanger`. K: `leak_K` + `channel_K` + 2 `pump`. Cl: `leak_Cl`. Ca: `leak_Ca` − `ca_pump` − `exchanger` + `ca_channel`. Each ± `junction_x`, minus at the sender and plus at the receiver. **It is not the free cytosol,** which is `cyt_x` | `amount_increment[x, cell]` |
| `heat_membrane` | `heat_leak` + `heat_leak_Ca` + `heat_pump` + Σ `heat_channel` of that membrane's K channels | `dissipated_energy_pJ[membrane]` |
| `heat_junction` | `heat_junction_own` + `heat_junction_Ca`. **Legacy's number is the sum over the four ions** | `junction_dissipated_energy_pJ[junction]` |
| `heat_store_leak` | `heat_store_leak_Ca` + `heat_store_leak_K` | `er_transport_dissipated_energy_pJ[store, 0]` |

A series that a world lacks counts as zero in every sum that names it, and is no entry (READOUTS §2).

### 6.3 The class of each

| What | Class |
| --- | --- |
| Every row of §6.1 that moves, but the parts named "none alone" and the works; the four formed entries of §6.2; the potentials; the `_summary` entries | **S** (`CRITERIA.md` §4.3, p = 2) |
| `store_Na`, `store_Cl`, and in `ip3_calcium` `store_IP3`, `store_IP3_buffer`, `store_IP3_bound`: zero at every time of every captured run (`legacy_part2.json` `zero_entries`) | **E**, exactly zero, every row |
| The pool's 19 arrays, its path, its seed; an ionic run's switch list, channel schedule and pool seeds; a restart | **E** |
| A pool's exposure | **R** (READOUTS §5) |
| Completion, with the engine's own ledgers at every accepted step | **D** |
| The balances, the moieties, the capacitors and the energy of a run | reported, not judged (§9) |

**Never compared:** the two rounding budgets (§4.2); `cycle_supplied_fmol`, `cycle_free_energy_J_mol`, `cycle_held_drive_J_mol`; the reactions' produced and consumed rows, their standard terms and their works (exactly zero where every reaction is passive, and recorded); `species_condition_factor`; rates, affinities and currents.

### 6.4 What the copy guard reads

**The copy guard** (`CRITERIA.md` §5) reads the class S rows of §6.1. The formed entries of §6.2 are not compared by it, and neither are the two heats of reactions against a capture, which the judge sums.

## 7. Mechanisms, homes and plants

### 7.1 Mechanisms and homes (besides Part 1's)

| Mechanism | Home | Consumers |
| --- | --- | --- |
| Plasma Ca leak | `leak_Ca` | all eight |
| Ca junction route | `junction_Ca` | all eight |
| Ca faces | `face_Ca` | all eight |
| Store Ca leak | `store_leak_Ca` | all eight |
| Store K leak | `store_voltage` | all eight |
| Store pump | `store_pump` | all eight |
| Release permeability | `store_release` | all eight |
| Release's calcium factor | `store_release` | all eight |
| Cytosolic buffer, first site | `extent_bind_0_first` | all eight |
| Cytosolic buffer, second site | `extent_bind_0_second` | all eight |
| Store buffer, first site | `extent_bind_1_first` | all eight |
| Store buffer, second site | `extent_bind_1_second` | all eight |
| Store capacitor | `store_K` | the four children. **In the four clusters it is not tested** (§7.4) |
| Plasma calcium pump | `ca_pump` | plasma, gated, ip3, and their clusters |
| Exchanger | `exchanger` | plasma, gated, ip3, and their clusters |
| Ca channel permeability | `ca_channel` | gated, ip3, and their clusters |
| Ca channel kinetics | `ca_gate_m`, `ca_gate_h` | gated, ip3, and their clusters |
| IP3 factor | `store_release` | ip3 and its cluster |
| IP3 binding | `extent_ip3_binding` | ip3 and its cluster |

- **Part 1's mechanisms** (leak of Na, K, Cl, K channel, its kinetics, the pump, the junction, its gate, the faces, the closure) are in every one of the eight, and their homes are Part 1's. **Their ratios come from their own planted runs** in each of the four ionic children (§7.2), and not from Part 1's.
- **Where a home entry has several plants** (the calcium factor's two constants, the exchanger's two, and the IP3 factor's, all on one entry), each plant is tested at it with its own ratio, the entry takes the largest, and the mechanism is tested when one of its plants is (the lead's ruling of 25 November). **A mechanism whose plants are all unseen,** so that none is tested at a home entry, is listed as **not tested, and nothing may be claimed of it.** This goes beyond
  `CRITERIA.md` §4.5, which gives a home entry one plant, and it changes nothing of Part 1, where no home has two.
- **The four clusters** take their ionic child's ratio, formed at 0.02 s alone (the summary entries at the summary times), **halved**. That is a declared lower bound. The availability changes the channel's current, not its relative response to a 1 % change in it. No cluster was run with a power plant.
- **A mechanism whose plant has no effect above its band** is declared not observable in §7.4, and is not a home.

### 7.2 Power plants, Part 2 (each a legacy run of the captured definition with one constant × 1.01, at the captured 12.5 µs step)

**Part 1's set,** run again in each of the four ionic children: `P-leak`, `P-channel`, `P-pump`, `P-junction`, `P-jgate`, `P-face`, `P-faceK`, `P-kinetics` (the K channel's two time constants, patch).

**The calcium set:** `P-leakCa` (plasma Ca leak permeability), `P-junctionCa`, `P-faceCa`, `P-storeleakCa`, `P-storeleakK`, `P-storepump` (capacity), `P-release` (permeability), `P-activation`, `P-inhibition` (the two constants of the calcium factor), `P-bind0a`, `P-bind0b`, `P-bind1a`,
`P-bind1b` (the four forward rates), `P-storecap` (store specific capacitance, its initial voltage 0), `P-pmca` (capacity), `P-ncx` (capacity), `P-ncxkm` (Na constant), `P-cav` (maximal permeability), `P-cavkinetics` (both time constants, patch), `P-ip3activation`, `P-ip3binding` (forward rate). Each is run in every child that holds it. 103 power runs in all, with ten controls (eight of the children, two each, and two of `cluster_gated_calcium`, at seed indices 0 and 1).

### 7.3 Structural plants, Part 2

| Plant | World | Change | Named entries |
| --- | --- | --- | --- |
| SC1 | spatial | The release's calcium factor left out (it is 1) | `store_release`, `store_Ca` |
| SC2 | ip3 | The IP3 factor left out (it is 1) | `store_release` |
| SC3 | spatial | The store voltage's sign reversed in its leak, release and pump | **not scored:** legacy's own domain check stops the run (§7.4) |
| SC3b | spatial | The store voltage's sign reversed in the calcium leak and release alone, the K leak honest (replaces SC3) | `store_leak_Ca`, `store_release` |
| SC4 | spatial | The store pump's direction reversed | `store_pump`, `store_Ca` |
| SC5 | spatial | Ca's valence taken as 1 in the store's leak and release | `store_leak_Ca`, `store_release` |
| SC6 | spatial | The first buffer's forward rate is second order in calcium | `extent_bind_0_first`, `cyt_Ca` |
| SC7 | plasma | The exchanger's sodium terms squared and not cubed, with 3 Na moved | `exchanger` |
| SC8 | plasma | The plasma calcium pump's direction reversed | `ca_pump`, `cyt_Ca` |
| SC9 | gated | The channel's inactivation gate left out | `ca_channel` |
| SC10 | gated | The channel's m² taken as m | `ca_channel` |
| SC11 | cluster_gated_calcium, seed index 1 | The pool's availability acts on the calcium channel as well as the K channel | `ca_channel`, worlds 0 and 1 |
| SC12 | plasma | The pump's standard free energy left at the numeric-mM one under the 1 M quotient | `heat_ca_pump` |
| SC13 | spatial | The store pump's standard free energy left at the numeric-mM one under the 1 M quotient | `heat_store_pump` |
| SC14 | cluster_gated_calcium, seed index 1 | Each pool's availability acts on the other cell's K channel | `channel_K`, worlds 0 and 1 |

**Two lines of 25 November 2026 (dated), after Part 2's margins had been read and before any candidate run.** SC11 moved from seed index 0, whose pools are not blind (§5), to seed index 1, and was run again there. Its first run stays in the manifest and is not scored. SC14 was added as EP4's reference side (§11), by the patch of Part 1's ST6.

### 7.4 Observability and margins (from the legacy side alone, 25 November 2026)

**103 power runs, 17 structural runs (SC3 stopped by legacy's domain check, the refused stoichiometry of SC6 and SC11's first seed among them), and ten controls, 130 runs in the manifest,** of the frozen snapshot at the captured 12.5 µs, under the lead's conditions of 25 November, after the first commit of this branch. `plants_manifest_part2.json` holds each run, its patch text and its sha256, and `margins_part2.json` the numbers below, entry by entry. The bands are §8's, at U_c = 0.
**The controls are bit-identical to their captures:** `spatial_calcium` 371 arrays, `plasma_calcium` 413, `gated_calcium` 455, `ip3_calcium` 469 (each twice, before and after its batch), and `cluster_gated_calcium` seed index 0 and 1, 48 each.

**Every mechanism is observable at U_c = 0, but the store's capacitor in the four clusters, which is not tested there.** The smallest margin of a home is 105 in the children (`store_voltage` of `ip3_calcium`) and 53 in the clusters (`store_voltage`, halved), against the rule of 10. Each row holds the planted ratio and the smallest margin over the children that hold the mechanism, and for the clusters (at 0.02 s, §7.1) the ratio used and the smallest margin:

| Mechanism | Home (plant) | Children: ratio, smallest margin | Clusters at 0.02 s: ratio and smallest margin, both halved |
| --- | --- | --- | --- |
| leak permeability | `leak_Na` (P-leak) | 1.0e-02, 3e+07 | 5.0e-03, 2e+07 |
| leak permeability | `leak_K` (P-leak) | 9.9e-03, 3e+06 | 5.0e-03, 2e+06 |
| leak permeability | `leak_Cl` (P-leak) | 9.8e-03, 1e+06 | 4.9e-03, 5e+05 |
| channel permeability | `channel_K` (P-channel) | 1.0e-02, 3e+05 | 5.0e-03, 1e+05 |
| channel kinetics | `gate_m` (P-kinetics) | 3.7e-03, 6e+06 | 6.3e-03, 3e+06 |
| channel kinetics | `gate_h` (P-kinetics) | 3.4e-05, 2e+05 | 1.7e-05, 1e+05 |
| Na/K pump | `pump` (P-pump) | 1.0e-02, 4e+07 | 5.0e-03, 2e+07 |
| junction permeability | `junction_Na` (P-junction) | 9.3e-03, 5e+06 | 4.7e-03, 2e+06 |
| junction permeability | `junction_K` (P-junction) | 8.8e-03, 3e+06 | 4.4e-03, 1e+06 |
| junction permeability | `junction_Cl` (P-junction) | 8.6e-03 to 8.7e-03, 1e+06 | 3.9e-03, 6e+05 |
| junction gate | `junction_gate` (P-jgate) | 5.6e-04, 3e+06 | 2.8e-04, 1e+06 |
| faces | `face_Na` (P-face) | 9.8e-03, 3e+06 | 4.9e-03, 1e+06 |
| faces | `face_K` (P-face) | 9.8e-03, 9e+06 | 4.9e-03, 4e+06 |
| faces | `face_Cl` (P-face) | 9.9e-03, 1e+06 | 4.9e-03, 7e+05 |
| electrical closure | `voltage` (P-pump) | 3.5e-03, 2e+04 | 1.7e-03 to 1.8e-03, 1e+04 |
| electrical closure | `phi_out` (P-faceK) | 9.2e-03, 4e+06 |  |
| plasma Ca leak | `leak_Ca` (P-leakCa) | 9.9e-03, 3e+07 | 5.0e-03, 2e+07 |
| Ca junction route | `junction_Ca` (P-junctionCa) | 1.0e-02, 3e+06 | 5.0e-03, 2e+06 |
| Ca faces | `face_Ca` (P-faceCa) | 9.9e-03, 3e+06 | 5.0e-03, 2e+06 |
| store Ca leak | `store_leak_Ca` (P-storeleakCa) | 1.0e-02, 6e+06 | 5.0e-03, 3e+06 |
| store K leak | `store_voltage` (P-storeleakK) | 9.9e-03 to 1.0e-02, 1e+02 | 5.0e-03, 5e+01 |
| store pump | `store_pump` (P-storepump) | 9.9e-03, 3e+07 | 5.0e-03, 2e+07 |
| release permeability | `store_release` (P-release) | 1.0e-02 to 1.1e-02, 1e+06 | 5.1e-03 to 5.3e-03, 7e+05 |
| release's calcium factor | `store_release` (P-activation) | 6.3e-03 to 6.6e-03, 1e+06 | 3.1e-03 to 3.3e-03, 5e+05 |
| release's calcium factor | `store_release` (P-inhibition) | 1.2e-04 to 1.3e-04, 2e+04 | 5.9e-05 to 6.6e-05, 9e+03 |
| cytosolic buffer, first site | `extent_bind_0_first` (P-bind0a) | 5.7e-03, 3e+06 | 2.9e-03, 2e+06 |
| cytosolic buffer, second site | `extent_bind_0_second` (P-bind0b) | 9.7e-03 to 9.8e-03, 2e+06 | 4.9e-03, 1e+06 |
| store buffer, first site | `extent_bind_1_first` (P-bind1a) | 3.5e-03, 5e+06 | 6.3e-04 to 6.4e-04, 9e+05 |
| store buffer, second site | `extent_bind_1_second` (P-bind1b) | 8.3e-03, 3e+07 | 4.1e-03, 2e+07 |
| store capacitor | `store_K` (P-storecap) | 1.4e-04 to 1.7e-04, 1e+02 | **not tested** (ratio halved 2.9e-05 to 3.9e-05, margin halved 22 to 82) |
| plasma calcium pump | `ca_pump` (P-pmca) | 1.0e-02, 4e+07 | 5.0e-03, 2e+07 |
| exchanger | `exchanger` (P-ncx) | 9.9e-03, 3e+06 | 4.9e-03, 1e+06 |
| exchanger | `exchanger` (P-ncxkm) | 8.7e-05, 3e+04 | 4.3e-05, 1e+04 |
| Ca channel permeability | `ca_channel` (P-cav) | 1.0e-02, 4e+05 | 5.0e-03, 2e+05 |
| Ca channel kinetics | `ca_gate_m` (P-cavkinetics) | 3.6e-03, 6e+06 | 3.8e-03, 3e+06 |
| Ca channel kinetics | `ca_gate_h` (P-cavkinetics) | 1.7e-03, 1e+07 | 9.9e-04, 5e+06 |
| IP3 factor | `store_release` (P-ip3activation) | 1.3e-02, 2e+06 | 6.4e-03, 9e+05 |
| IP3 binding | `extent_ip3_binding` (P-ip3binding) | 7.8e-03, 1e+07 | 3.9e-03, 7e+06 |
| store K leak, **first home: not tested there** | `store_leak_K` (P-storeleakK) | 1.4e-04 to 1.7e-04, 148 to 340 | not tested there |
| store capacitor, **first home: not tested there** | `store_voltage` (P-storecap) | 9.9e-05 to 1.5e-04, 2 to 3 | not tested there |

- **Mechanisms with several plants** (the calcium factor, the exchanger) are tested by the largest of them (§7.1). The inhibition constant and the exchanger's Na constant are weak plants (a ratio of 10⁻⁴ or less), and their mechanisms are tested by the activation constant and the capacity.
- **The store's two electrical mechanisms are the weakest.** The K leak's 1 % plant moves `store_voltage` by 1 % of a voltage that is small against its scale (the gross throughput of K), and the capacitor's moves `store_K` by 1.4 × 10⁻⁴ to 1.7 × 10⁻⁴ of itself in the children. A candidate whose error estimate there is above about a tenth of the planted distance cannot test them, and the child is then inconclusive, with the reason `power`. The candidate's step decides, and no band is widened for it.
- **In the four clusters the capacitor is not tested** (the lead's ruling of 25 November): a cluster's captures hold one end state, and not the early rows where the capacitor shows. At the clusters' end its plant moves `store_K` by 2.9 × 10⁻⁵ to 3.9 × 10⁻⁵ (halved), so a comparison there would be a thin one. It is listed as not tested in each cluster, and nothing may be claimed of it there. This exemption is declared before any run, so `CRITERIA.md` §8's rule (a consumer with an untested mechanism is at best inconclusive) does not apply to it: the capacitor is no mechanism of the four clusters' test (`margins_part2.json` `cluster_not_tested`).
- **The margins were formed again on 25 November under §8's bands** (e_store, the closure, the reactions' heats per compartment). The smallest were 550 and more before, under Part 1's closure share and without e_store. No home moved.

**Homes replaced on 25 November, after the planted runs had been read on the reference side, and before any candidate run (dated line).** The lead accepted it as a replacement of plants. The first homes stay in the table, marked **not tested there**, with their figures (`margins_part2.json` `first_homes_not_tested_there`). The protocol's §11 says that the choice came after the planted runs were read.
- **Store K leak:** from `store_leak_K` to `store_voltage`. The K leak is so fast that K's own transfer follows calcium's, and its 1 % plant moves `store_leak_K` by 1.4 × 10⁻⁴, while the store's voltage is set by the leak and moves by 1 %.
- **Store capacitor:** from `store_voltage` to `store_K`. At the potential times the store's voltage is quasi-steady and does not know its capacitance. `store_K` holds the early charging.

**The structural plants:**

| Plant | Named entry: distance, margin |
| --- | --- |
| SC1 (`spatial_calcium`) | `store_release`: 1.3e-04, 2e+08; `store_Ca`: 1.2e-04, 4e+07 |
| SC3b (`spatial_calcium`) | `store_leak_Ca`: 1.5e-07, 2e+06; `store_release`: 1.1e-06, 2e+06 |
| SC4 (`spatial_calcium`) | `store_pump`: 1.0e-04, 1e+10; `store_Ca`: 9.9e-05, 3e+07 |
| SC5 (`spatial_calcium`) | `store_leak_Ca`: 3.7e-08, 5e+05; `store_release`: 2.9e-07, 4e+05 |
| SC6 (`spatial_calcium`) | `extent_bind_0_first`: 1.0e-03, 7e+08; `cyt_Ca`: 1.1e-03, 5e+08 |
| SC13 (`spatial_calcium`) | `heat_store_pump`: 6.5e-04, 7e+08 |
| SC7 (`plasma_calcium`) | `exchanger`: 6.0e-07, 8e+06 |
| SC8 (`plasma_calcium`) | `ca_pump`: 6.2e-05, 9e+09; `cyt_Ca`: 4.2e-05, 2e+07 |
| SC12 (`plasma_calcium`) | `heat_ca_pump`: 4.3e-04, 8e+08 |
| SC9 (`gated_calcium`) | `ca_channel`: 2.2e-06, 2e+07 |
| SC10 (`gated_calcium`) | `ca_channel`: 2.1e-05, 2e+08 |
| SC2 (`ip3_calcium`) | `store_release`: 1.9e-04, 3e+08 |
| SC11 (`cluster_gated_calcium`, seed index 1) | `ca_channel`: world 0 3.6e-06, 4e+07; world 1 3.6e-06, 4e+07 |
| SC14 (`cluster_gated_calcium`, seed index 1) | `channel_K`: world 0 4.3e-07, 4e+06; world 1 2.1e-07, 2e+06 |

- **SC3 is replaced by SC3b (dated line, 25 November).** With the store voltage's sign reversed in the K leak the store runs away, and legacy's own domain check stops the run at 1.4875 ms. There is no planted array, so nothing can be scored, and a candidate with that error is stopped by its own check or leaves its domain. SC3b reverses the sign in the calcium leak and release alone, and is scored.
- **SC6 is the runnable stand-in for a wrong stoichiometry.** The captured first buffer with two calcium bound (2 Ca + B = CaB) was tried too, and legacy refuses it at parse ("Each reaction must conserve every declared moiety and charge"). So SC6 changes the kinetic order and not the stoichiometry. The refused run is in the manifest.
- **Which ran with legacy's own host-side ledgers off:** SC3, SC3b, SC4, SC5, SC6, SC7 and SC8, since those errors break them by construction. Their domain checks stayed on. The power plants, the controls and SC1, SC2 and SC9 to SC14 ran with all checks on.

## 8. Scales, amount references, the rounding count and the closure

**Scales:** `inputs_part2.json` `scales`, in every world. Part 1's rule (`SPEC.md` §5), with these additions, each the gross throughput over 20 ms that the readout is formed from:
- `leak_Ca`, `junction_Ca`, `face_Ca`, `n_out_Ca` as Part 1's with z = 2.
- `store_leak_x` = P_x A/10⁻¹⁵ × c* × χ × T, c* the larger of the cytosol's and the store's initial concentrations; `store_pump` = capacity × T; `store_release` = P A/10⁻¹⁵ × c*_Ca × χ(2) × T, with the factors taken as 1.
- `extent_r` = the larger of the forward and reverse initial rates at the **total** amounts that the moieties allow, times T.
- A reaction's heat: its extent's scale × 10⁻³ R T (1 + |Δμ°| + Σ ν |ln(c/c°)|) over its reactants and products. **`heat_reactions_cytosol` and `heat_reactions_store` are the sums over the compartment's reactions,** the largest over the cells.
- `heat_store_*`, the Ca heats: their transfer's scale times the RT and potential terms, as Part 1's heats. `heat_junction` and `heat_membrane` with Ca's routes.
- `cyt_c`, `store_c`, `exchange_x`: the sum of the scales of the routes and reactions that move them.
- `store_voltage` = max |V₀| + (F 10⁻¹⁵/C) Σ_c |z_c| × the store row's scale, with C the store's capacitance. `voltage` as Part 1's with the calcium routes.
- `ca_pump` = capacity × T, `exchanger` = capacity × T × exp(F V*/2 R T_K), `ca_channel` as `channel_K` with z = 2. Gates are 1.

**The rounding count.** e_round(S) = 8 ε (S + 1) s stands, by `SPEC.md` §6's derivation with two changes of the candidate. The IMEX step adds to a stored value at most five times, and each Strang half of the reactions once more (its extent, and each row's stored increment, are added once a half-step: the engine's documented update). So seven additions a step, and 8 ε (S + 1) holds up to sixteen. The scheme's weights have a negative one, and the sum of their magnitudes is 2.42, so the 64 roundings of a rate are 155, without a factor S, which the bound covers for S ≥ 17.

**`amount_refs`,** by Part 1's rule (the declared amounts that an entry reads, for e_store(S) = 2.5 ε (S + 1) × it): `cyt_c`, `store_c`, `n_out_x`, `voltage` (its cell's rows and its store's, since the membrane's charge is the two nodes' together) and `store_voltage` (the store's rows). **A row that a reaction of its compartment touches is added to seven times a step and not five, so its reference is 7/5 of its amount.** The transfers, the extents, the cycles, the heats, the gates, `phi_out` and the formed `exchange_x` read no amount and have none. The engine's documented state stores increments, as in Part 1, and the `state form` flag is Part 1's (`CRITERIA.md` §4.3).

**The closure:** `closure_share` = 10⁻¹⁰, and **e_close = 10⁻¹⁰ s in every entry of Part 2, but `phi_out`,** whose closure is Part 1's 5.16 × 10⁻¹³ V (`closure_terms_V`; the conductances formed again with calcium's: its share of a face's is 7 × 10⁻⁵, the row sum of K⁻¹ is 2.0035 and no conductance exceeds 0.526 of the smallest ΣG, as before).
**The derivation.** It is Part 1's question, what potential error the two codes admit, asked of an IMEX step and of every path that a potential takes.
- **What the engine admits.** At each implicit stage a node's charge residual is at most 3 × 10⁻²⁵ C + 2 × 10⁻¹² of the larger of its charge and of the solve's own product (its declared constants, read at 49529e71). Legacy forms a membrane's and a store's voltage from its charges with no solve, and its free offsets are Part 1's (2.13 × 10⁻¹² V*).
- **As potential errors:** a membrane's 2 × 10⁻¹² V* + 2 × 3 × 10⁻²⁵ C/C_m (its cell's and its store's residuals) = 4.4 × 10⁻¹³ V. The junction's, the two membranes' together, 8.5 × 10⁻¹³ V. A store's 2 × 10⁻¹² V* + 3 × 10⁻²⁵ C/C_s = 2.7 × 10⁻¹³ V. A free offset's 2.01 × 2 × 10⁻¹² V* + 3 × 10⁻²⁵ C × Σ|K⁻¹|/(γ h) = 1.4 × 10⁻¹² V at the retry's 1.5625 µs, the largest of the four steps (γ = 1 − 1/√2).
- **As shares of s,** with u = F/(R T) and χ as in `SPEC.md` §5: a constant-field route's |z| u δ/χ; a pump's u δ a net charge (1, and 2 for the calcium pumps), and 1.5 u δ for the exchanger; a gate's (its target's largest slope + 0.37 × its time constant's largest logarithmic slope) × δ, from the captured laws over their domain; a channel's and the junction's, their route's and their open fraction's together; a heat's, its transfer's and its affinity's together:

| Path | Share of s |
| --- | --- |
| plasma leaks | 3.0 to 3.3 × 10⁻¹² |
| store leaks and release | 1.9 to 2.0 × 10⁻¹² |
| Na/K pump, calcium pumps, exchanger | 1.7 × 10⁻¹¹, 3.4 × 10⁻¹¹ (the store's 2.1 × 10⁻¹¹), 2.6 × 10⁻¹¹ |
| faces, both codes | 1.1 to 1.2 × 10⁻¹¹ |
| `gate_m`, `gate_h`, `ca_gate_m`, `ca_gate_h` | 3.1, 3.5, 3.1 and 2.4 × 10⁻¹¹ |
| `junction_gate`, and the junction's routes | 6.7 × 10⁻¹¹, 7.3 × 10⁻¹¹ |
| `channel_K`, `ca_channel` | 6.9 × 10⁻¹¹, 8.9 × 10⁻¹¹ |
| `heat_junction`, `heat_membrane`, `heat_ca_channel` (the largest of the heats) | 8.0, 7.2 and 9.2 × 10⁻¹¹ |

The largest is 9.2 × 10⁻¹¹, and 10⁻¹⁰ is the power of ten above. A sum of routes is at most its largest route's share. The solve's own error of `voltage` and `store_voltage` is 8 × 10⁻¹³ s and 2 × 10⁻¹⁴ s. The reactions are advanced by an explicit scheme with no solve, so they have no closure of their own. **`phi_out` is not a stage's potential.** It is solved again at an observed row, from that row's amounts, by the field solver of §4.1, whose acceptance is Part 1's. A stage's free-offset error enters the faces' transfers, and through them the regions' amounts, which move `phi_out` by at most 6 × 10⁻¹⁴ V. So its closure is Part 1's number, and not the stage's 1.4 × 10⁻¹² V. **What a direct solve leaves is far below what the engine admits,** and the bound is on what is admitted.

## 9. Conservation and the reported identities

**Conservation is the engine's own rule at every accepted step** (`CRITERIA.md` §4.4). No identity below is judged. The judge forms and reports them, each beside READOUTS §5's bounds (which are Part 1's judged ones; the energy's with its own U_c), and flags a residual above its bound to the checker:
- the balances of each cell's whole-cell ledger, region, store row and cytosol row, and the closed world;
- **the moieties** in each compartment: B + CaB + Ca2B (cytosol and store apart), IP3 + IP3_bound and IP3_buffer + IP3_bound (cytosol), and calcium's total: cytosol (Ca + CaB + 2 Ca2B) + store (the same) = `exchange_Ca`;
- **the capacitors:** `voltage` − V₀ = (F 10⁻¹⁵/C_m) Σ_x z_x `exchange_x`, and `store_voltage` = (F 10⁻¹⁵/C_s) Σ_c z_c `store_c`;
- **the energy:** every chemical row of cytosol and store (d (μ°_RT + ln(n₀/(V c₀)) − 1) + (n₀ + d) ln(1 + d/n₀)), both capacitors, the heats and the works.

**In Part 2 the engine's own energy allowance is looser than the comparison's.** The declared rule allows 2 × 10⁻³ of the integrated flows on the IMEX integrator. So the heats are judged against the captures, readout by readout, and not by the identity.

**Why they are not judged here and are in Part 1:** the candidate changes the integrator. Where a kind books its heat as a quadrature of the tableau, the energy closes at the integrator's order and not at rounding, and a bound at legacy's order would refuse an honest run.

## 10. The judged sets, counted

| Consumer | S, a family | Families | S in all | E | R | D |
| --- | --- | --- | --- | --- | --- | --- |
| `spatial_calcium` | 56 | 1 | 56 | 6 | none | 3 |
| `plasma_calcium` | 60 | 1 | 60 | 6 | none | 3 |
| `gated_calcium` | 64 | 1 | 64 | 6 | none | 3 |
| `ip3_calcium` | 68 | 1 | 68 | 83 | none | 3 |
| `cluster_spatial_calcium` | 60 | 8 | 480 | 288 | 8 | 28 |
| `cluster_plasma_calcium` | 64 | 8 | 512 | 288 | 8 | 28 |
| `cluster_gated_calcium` | 68 | 8 | 544 | 288 | 8 | 28 |
| `cluster_ip3_calcium` | 72 | 8 | 576 | 360 | 8 | 28 |

- **S** entries are `legacy_part2.json`'s, with the three potentials in the children (two in the clusters, which have no `phi_out`) and the five `_summary` entries in the clusters.
- **E, children:** the structural zeros, 2 a judged run (5 in `ip3_calcium`), and the restart's 68 in `ip3_calcium` (one per class S readout and potential).
- **E, clusters:** per pool run and cell the 19 arrays, the path and the seed (21 × 2 × 4 = 168); per judged ionic run the switch list, the channel schedule and the pool seeds (3 × 24 = 72) and the structural zeros (2 × 24 = 48, or 5 × 24 = 120 in `cluster_ip3_calcium`).
- **R:** one exposure per pool run and cell.
- **D:** one a judged run. A pool run completes too.
- A consumer whose entries formed are fewer than these, in any class, is at best inconclusive (`CRITERIA.md` §5).
- **`energy_identity` is no entry of Part 2.**

## 11. The runs

**`inputs_part2.json` lists 127:** 12 for the four children, 112 for the clusters (a cluster's 4 pool runs and 24 ionic runs), one restart and two engine plants.
- **The restart** (support): `ip3_calcium h=1.25e-05 restart`, at 0.01 s, by `SPEC.md` §4 and `TABLE.md` §3. It resumes a checkpoint of its judged run. `ip3_calcium` holds every mechanism of the eight consumers but the pools, so its state holds every kind of state there is. The clusters have no pool restart: their pools are `base`'s code and seeds, and Part 1 restarts those.
- **EP3** (`ip3_calcium plant release`, at h₃): both stores' release permeability × 1.01.
- **EP4** (`cluster_gated_calcium plant swapped`, seed index 1, world 0, at h₃): each K channel's schedule is the other cell's path. Its `pool_seeds` are by position, and so its honest run's (Amendment 1, item 7, which holds for EP4).
- **An engine plant's block differs from its honest run's only by its change.**
- **The retry's runs** are registered by rule, only when owed: `<family> h=1.5625e-06 retry`, with an extra support run only if owed.

### 11.1 The engine plants' named entries

- **EP3:** `store_release`. Its registered distance is the planted run's (`P-release`): 1.1 × 10⁻⁶ fmol, a margin of 1.5 × 10⁶.
- **EP4:** `channel_K` and `channel_K_summary`. Its registered distance is SC14's: 4.3 × 10⁻⁷ fmol, 2.2 times the honest `channel_K`, a margin of 3.7 × 10⁶. **Its `switch_list` and its `controls.channel` are class E against the swapped paths,** and it is unscorable if they or its `pool_seeds` depart.
- They are scored as `CRITERIA.md` §6 says.

## 12. The independent reference

**What it is.** A scalar ODE reference of these worlds' equations, with its own code and no engine import: `validation/betse/spatial_cluster/reference.py` for the cluster (leak, pump, K channel, junction, faces and the Kirchhoff solve), and
the store, plasma-pump, channel and IP3 references of the live tests, with an adaptive integrator at a relative tolerance of 2 × 10⁻¹³. It stays through the deletion and moves under this folder later (the lead's ruling of 25 November).

**What it is used for.**
- **Corroborating the reference side, before any run.** It is run on the captured definitions, and must agree with the captured h/4 rows at the compared times within its own registered criterion, 3 × 10⁻⁹ relative and 3 × 10⁻¹² absolute, readout by readout. A disagreement is a C0 fault of the
  references, found before a table is opened. **The author ran it on 25 November** on the four children and on both JUPITER arms: every **state** field agrees at every compared time (the potentials were not compared), with the worst entry at 5.5 × 10⁻⁴ of that criterion. The largest difference relative to a field's largest value is 3.3 × 10⁻¹² (the store's K leak) in the children, and 2.5 × 10⁻¹⁴ in the JUPITER arms (the protocol's §11).
- **Reporting beside a miss.** Where the candidate misses an S entry, the judge reports its distance to the independent reference too. It decides nothing by itself.
- **A changed model** (§3), if one is found, has it as its registered criterion, at 3 × 10⁻⁹ against the independent equations **as they are written there**, which must first be changed to the changed model's.

**What it covers.** The four ionic clusters and the JUPITER cluster, with a prescribed channel availability (so, the assembly clusters' ionic sides too, given their paths; the author did not run those). Amounts, transfers, cycles, gates, potentials, reaction extents and heats.

**What it does not cover.** The assembly pools, their events and seeds. The energy balance as an integral law. Legacy's interpolants and domain proofs. It is written from the same model description, so it shares any reading of it. It is a check of the arithmetic and of the book-keeping, not of the physics.

## 13. The retry, and an entry that its triple leaves unresolved or mixed

**The retry's triple** is (h₂, h₃, h₃/2) = (6.25, 3.125, 1.5625) µs, with S_c = 12,800 in e_round, e_store and θ (`CRITERIA.md` §7). It is owed as there, by the reasons `order` and `power`.

**The arithmetic.** Let e = e_round(S_c) + e_store(S_c) at a triple's finest run, so θ = 10 e, and let a run lie within e of its scheme's exact value. A difference of two runs carries at most 2 e of rounding. For an honest entry of order 2 let t be the truncation in d₂. Then d₂ lies in t ± 2 e, and d₁ in t/4 ± 2 e. At the retry's triple the truncation in d₂ is t/4 and e is doubled.
- **Unresolved at the first triple** (t at most 12 e): unresolved at the retry's, where the truncation is at most 1.5 of its e.
- **Mixed at the first triple** (t between 8 e and 48 e): **unresolved at the retry's,** where it is between 1 and 6 of its e, and so d₂ is at most 8 of them, below θ.
- **Resolved at the first triple** (t above 32 e): resolved, mixed or unresolved at the retry's. So an honest entry is mixed at the retry's triple only if the first triple had resolved it.

**The rule, for an owed entry at the retry's triple.** Above β it fails, whatever its class, but where the last line of the table says otherwise. At most β:

| Class at the retry's triple | What decides |
| --- | --- |
| **unresolved** | β alone, as `CRITERIA.md` §4.3 has it. The record says `order not shown` |
| **resolved, in its window** | β alone |
| **mixed, with its order not excluded** | β alone. The record says `order not shown` |
| **mixed, with its order excluded** | **inconclusive,** reason `order` |
| **resolved, outside its window** | **inconclusive,** reason `order`, whatever its error. Never a pass |

**Excluded** means that rounding cannot explain the measured order: with q_lo = log₂((d₂ − 2 e)/(d₁ + 2 e)) and q_hi = log₂((d₂ + 2 e)/(d₁ − 2 e)), both at the retry's triple (q_lo is minus infinity where d₂ is at most 2 e, and q_hi plus infinity where d₁ is), the interval [q_lo, q_hi] does not meet [1.5, 4.5]. For an honest order-2 entry the interval always holds 2, since (d₂ ∓ 2 e)/(d₁ ± 2 e) brackets t/(t/4) = 4. So no honest entry is inconclusive by this rule for being mixed. **It still refuses:** an order-1 entry with d₁ = θ and d₂ = 2 θ (q_hi = log₂(22/8) = 1.46), and every entry with d₁ above θ and d₂ below it (q_hi is at most log₂(12/8) = 0.58).

- **What e leaves out, and why.** e is rounding. The closure that the engine admits (§8) is about nine times e at the first triple, and it is in neither e nor θ, as in Part 1, since what a direct solve leaves is far below it. Where a solve left as much as it may, a difference would carry up to 18 e of noise, and an honest entry could be mixed, or outside its window, by noise alone (tried on random honest entries: one in five at the whole admitted closure, none at a hundredth of it). **Such an entry is inconclusive by `order`, and it never fails.** The rehearsal looks for it (§15).
- **What passed is not turned.** An entry that passed at the first triple keeps its pass, and one that failed keeps its fail, whatever its class and its difference at the retry's (`CRITERIA.md` §7). The retry's run judges the owed entries of its family, and its own D.
- **Why the first triple is not changed.** A mixed entry there is owed the retry, and an honest one is unresolved by it. So the first triple's "inconclusive by order" costs one run and no verdict.
- **What a mixed or unresolved pass at the retry's says:** the candidate at 3.125 and 1.5625 µs differs by at most ten times its rounding bound, and it agrees with legacy within β. It does not show the order (§17).
- **The named reasons of an inconclusive entry** are `order`, `power` (a home entry not tested, whose 2 U_c is not the larger part of β or whose retry did not make it tested), `not formed` (a missing or doubled row or leaf, a departing echo, a run in `missing`, a refused file) and `refused`. A consumer's are those of its entries, and `support` and `plant` (a refused, missing or stopped support run, and an unscorable plant). The record gives one for every inconclusive entry.

## 14. The judge's plants of Part 2 (JQ)

`PLANTS.md` §6's rules hold, and so does its honest table: made from the captures (or the rehearsal's `runs/`), each value moved by at most one unit in the last place, with an invented split of the heats that legacy lumps. **Where a plant needs an order,** the judge adds an error of its own to the rows of the three rungs (recorded as invented). "All rungs" are h₁, h₂ and h₃.

| Plant | The run altered, and what | Must be |
| --- | --- | --- |
| JQ1 | `spatial_calcium`, all rungs: `store_release` negated | a fail of `store_release` |
| JQ2 | `spatial_calcium`, all rungs: `store_leak_K` negated | a fail of `store_leak_K` |
| JQ3 | `spatial_calcium`, all rungs: `junction_Ca` negated | a fail of `junction_Ca` and of `exchange_Ca` |
| JQ4 | `spatial_calcium`, all rungs: `heat_junction_Ca` set to zero (a tenth of the sum in the honest table) | a fail of `heat_junction` |
| JQ5 | `spatial_calcium`, all rungs: `heat_store_leak_Ca` set to zero (a tenth of the sum) | a fail of `heat_store_leak` |
| JQ6 | `ip3_calcium`, all rungs: `heat_reactions_cytosol` less the captured heat of `ip3_binding` | a fail of `heat_reactions_cytosol` |
| JQ7 | `gated_calcium`, all rungs: `store_voltage` negated | a fail of `store_voltage` |
| JQ8 | `spatial_calcium`, h₃: one `store_Na` at the last time set to 5 × 10⁻³²⁴ | a fail of class E, and of no S entry |
| JQ9 | `plasma_calcium`, h₁: `delta_g0_at_1M_J_per_mol` of one pump moved by 10⁻⁹ of itself | refused, and nothing of the run judged. Not a fail plant |
| JQ10 | the same number moved by 10⁻¹³ of itself, and another run's pump with potentials 1,000 times as large (A ≈ 22,000) and the number moved by 2 × 10⁻¹² of itself | neither refused |
| JQ11 | `gated_calcium`, h₁: `calcium_controls` omitted, the zero permeabilities omitted, the maps in another order | not refused |
| JQ12 | `gated_calcium`, h₁: one schedule of `calcium_controls` [[0.0, 1.0], [0.01, 0.5]] | refused, and nothing of the run judged |
| JQ13 | `spatial_calcium`, all rungs: an invented error of first order on `store_Ca`, d₁ and d₂ above θ | inconclusive by `order`, and named in `retry_owed.json` |
| JQ14 | `spatial_calcium`, all rungs: an invented error of second order on `store_Ca`, d₁ and d₂ above θ | resolved in its window, and a pass |
| JQ15 | the same, with d₂ above θ and d₁ below it | mixed, inconclusive by `order`, and named in `retry_owed.json` |
| JQ16 | JQ15 with its retry run honest (the error four times smaller) | unresolved at the retry's triple, and a pass, `order not shown` |
| JQ17 | an entry outside its window at the first triple, and at the retry's d₂ = 20 e and d₁ = 5 e, inside β | mixed, its order not excluded, and a pass, `order not shown` |
| JQ18 | the same, with d₂ = 20 e and d₁ = 10 e | mixed, its order excluded, and inconclusive by `order` |
| JQ19 | an entry that passed at the first triple, `leak_K` of the retry run alone × 1.01 | it keeps its pass |
| JQ20 | `cluster_spatial_calcium s0 w0`, all rungs: `channel_K` × 1.01, the rest honest | the cluster fails by set A, and the record shows that set B passes |
| JQ21 | `cluster_gated_calcium plant swapped`: its `pool_seeds` exchanged | EP4 unscorable |
| JQ22 | `ip3_calcium h=1.25e-05 restart` missing | `ip3_calcium` at best inconclusive, reason `support` |
| JQ23 | `gated_calcium`, h₁: `declared_strings` without the exchanger's string | refused, and nothing of the run judged |
| JQ24 | `cluster_ip3_calcium s1 pool`: `strings` with one label of the ionic definition | refused, and nothing of the run judged |
| JQ25 | `spatial_calcium`, h₂: its class S rows replaced by the captured rows of `spatial_calcium-h2` | refused by the copy guard (b), its readouts judged |

**A judge's plant that the code scores otherwise stops the judge's tag.** The sizes that the plants rest on were formed from the captured arrays: each altered row moves by at least 10⁴ bands at U_c = 0, and the IP3 reaction's heat is 10⁶ bands of `heat_reactions_cytosol`.

## 15. The rehearsal set of Part 2

`SPEC.md` §8 and `CRITERIA.md` §10 hold. Part 2 has its own rehearsal, before its registration, in the same folders: `inputs_rehearsal_part2.json` (with `inputs_part2.json`'s schema, `p`, `amount_refs`, `closure_share` and `closure_terms_V` in every world, and runs named `inv_<name>`), `legacy_rehearsal_part2.json`, `margins_rehearsal_part2.json` and `plants_manifest_rehearsal_part2.json`, with the makers and readers of `SPEC.md` §8. **No value of this part's captured worlds is used.** It holds, at least:
- one cell with one store, and a two-cell cluster with a store each, free field offsets, a gated junction that carries Ca (§3, condition 8) and Ca on its faces;
- one world with the plasma pump and the exchanger, one with the calcium channel, and one with IP3 and its Hill read;
- a two-pool cluster on one of these, with at least one event in each path, so that a step splits;
- **one family whose order is resolved in its window, one whose entries straddle θ at the first triple** (so that the mixed class, the retry and §13's rule are run), **and one at rounding;**
- one world whose fuel potentials are large against their difference (A at least 3,000), for §2.4's second term;
- **one world whose amounts are as large against s as the registered ones:** `amount_refs`/`scales` at least 1.7 × 10⁴ for a cytosol's row, 4.4 for a store's, 22 for `n_out_x`, 7.7 × 10³ for `voltage` and 4.8 for `store_voltage` (the largest of `inputs_part2.json`). Its honest run must pass every entry;
- one restart, one refusal of each kind, one run stopped by the engine's own check, one engine plant of each kind (EP3's and EP4's), and the faulty tables of JQ1 to JQ25 that a table can carry.

**The noise of the solves is looked at there:** in the honest runs, the step-halving differences of the entries at rounding, against 2 e (§13). One above it says that the closure is real, and θ is then corrected by `CRITERIA.md` §10's route, before the registration tag.

## 16. Where Part 2 differs from Part 1, and why

| What | Part 1 | Part 2 | Why |
| --- | --- | --- | --- |
| Integrator and order | RK4, p = 4 | IMEX with Strang halves, p = 2 for every S entry | The candidate is the composite (ruling 5) |
| e_close | 4 × 10⁻¹² s | 10⁻¹⁰ s | The IMEX stage's charge tolerance, and every path of a potential error counted (§8) |
| θ | 10 × (e_round + e_store), without the closure | the same | §13 says what follows, since the closure is larger here |
| `amount_refs` | the declared amounts | 7/5 of them in a row that a reaction touches | Two more additions a step (§8) |
| Balances, capacitors, energy | judged (R and S) | reported | The integrator (§9) |
| A reaction's heat | none | per compartment, the captured ones summed by the judge | The engine books a node's reactions together (ruling 1) |
| `heat_junction` | one row | the junction's own and Ca's route, summed | Ca's junction route is a passive route, and legacy sums the four ions |
| Cells' fixed charges | compared | recorded | The captured ones do not count the buffer's rows (§2.2) |
| The pumps' free energy | declared, compared | formed by the exporter, compared with a rounding term | The cycle law declares none (ruling 2) |
| A mixed entry at the retry's triple | inconclusive | judged by §13 | Part 2's entries may be resolved, and a finer step brings them to rounding (ruling 10) |
| A home with several plants | none | the best of them (§7.1) | The lead's ruling of 25 November |
| The clusters' ratios | their own plants | their child's, halved | No cluster was run with a power plant (§7.1) |
| A mechanism not tested | none | the store's capacitor in the clusters (§7.4) | The lead's ruling of 25 November |
| Two sets | 2 families and 30 of `base` | seed index 0 and the others, of each cluster | Whole seed indices, since a cluster's pool run holds both of its worlds (§5) |
| Pool restarts | `cell` and `base` | none | The pools are `base`'s |
| Potentials | two kinds | three (`store_voltage`) | The store's capacitor |
| What the exporter's builder receives | `TABLE.md`, `READOUTS.md`, `SPEC.md`, `inputs.json`, Amendment 1 | those, and `PART2_EXPORTER.md`, `PART2_BLOCKS.md`, `inputs_part2.json` | The plants of Part 2 are in `PART2.md` |

Everything else of `CRITERIA.md`, `TABLE.md` and Amendment 1 is as in Part 1.

## 17. What a pass of Part 2 cannot show

Besides the protocol's §9:
1. **The order of an entry that is unresolved, or mixed and passed at the retry's.** The record says `order not shown`, entry by entry.
2. **The heat of a single reaction,** and how a lumped heat divides (a membrane's, the junction's, the store's leak).
3. **Whether the release's factor is one condition or two,** and any single fuel potential. Only the factor's effect and the combination are compared.
4. **The store's capacitor in the clusters,** and any claim of it there.
5. **The clusters' trajectories.** One end state and five summaries are captured.
6. **The balances, the moieties, the capacitors and the energy,** which are reported. The engine's own ledgers, with their looser energy allowance, are the criterion.
7. **The fixed charges of cells and stores,** which the engine's own anchor rule holds.
8. **What holds the fuel rows** (`cycle_supplied_fmol`), the condition's observed factor, and the reactions' standard terms.
9. **A blind test of the pools of seed index 0.**
10. **That Ca's junction route takes the gate as the captured one does,** beyond what `junction_Ca` and `exchange_Ca` show.
11. **Anything below a band:** at U_c = 0 about 1.2 × 10⁻¹⁰ of the gross throughput, and in general the candidate's own error estimate.

## 18. For Part 2's independent auditor: what to look at first

The auditor reads this folder alone, and the captured arrays and planted runs that `README.md` lists. It comes before Part 2's tag, and it asks its questions through the lead.
1. **§13:** the retry's rule and its arithmetic, against `CRITERIA.md` §4.3 and §7.
2. **§8:** the closure's paths and their numbers, the rounding count for the IMEX step with its reaction halves, `amount_refs` and the 7/5.
3. **§6:** the names, the signs and the sums. Check the signs against the arrays, and the lumps (`heat_junction`, `heat_store_leak`, `heat_membrane`, `exchange_x`, the reactions' heats per compartment) against the captured code's numbers.
4. **§2.2 and §2.4:** the one-molar number, its three potentials and its tolerance.
5. **§3, condition 8:** what a Ca junction route without the gate would do, and where it would be seen.
6. **§5:** the two sets of a cluster, and what each owns.
7. **§7 and `margins_part2.json`:** the homes, the two replaced ones, the halved ratios, the margins under §8's bands, SC11's move and SC14.
8. **§10 and §11:** the counts, the runs, the engine plants' registered distances.
9. **`PART2_BLOCKS.md` and `inputs_part2.json`** against the captured definitions, and the defaults.
10. **§14 and §16:** a plant whose "must be" a correct judge would not give, and a difference from Part 1 that §16 does not list.

**Try to find:** an entry that an honest order-2 run would miss or leave inconclusive without a named reason; a pass with nothing judged; a sum whose parts a wrong sign would cancel; a number here that differs between two files.
