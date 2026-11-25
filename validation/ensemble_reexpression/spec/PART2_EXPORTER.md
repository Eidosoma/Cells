# Part 2, for the exporter's builder

**These are sections 1 to 6 and 11 of `PART2.md`, word for word,** without the parts that the judge alone needs (its §5.1, §6.4 and §11.1, and everything after §6 but §11). They are printed by program, with their numbers. A section that the text names and that is not here is the judge's. The exporter's builder receives this file, `PART2_BLOCKS.md` and `inputs_part2.json`, beside what `README.md` lists for Part 1, and **not** `PART2.md`, which holds the plants. Where this file and Part 1's files differ, it governs for Part 2's consumers.

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
| `stores.<cell>.reactions` | For each reaction: its compartment, its reactants and products, its forward rate. The reverse rate is the forward one times exp(Σ products' − Σ reactants' standard potentials). Each captured reaction is declared once, under its captured ID, at the cytosols' sites (`bind_0_*`, `ip3_binding`) or at the stores' (`bind_1_*`), and `extent_r` is named by it |
| `stores.<cell>.membrane` | The bounding patch: area, capacitance, initial voltage (the store's potential less the cytosol's) and charge, the permeability of every row (Ca and K alone are non-zero), the pump and the release. **K's permeability is the patch's own. Ca's is a passive route's** |
| `...membrane.pump`, `plasma_transport.<membrane>.pump` | One cycle law on the transporter kind, N at the cell: one Ca a cycle. Capacity, the two constants, the held ATP, ADP and Pi in mM, and the standard free energy **at a 1 M standard state**, which the exporter forms (§2.2). **One set of fuel rows is held at a cell,** and its store pump and its plasma pump share it. A block whose two pumps of one cell hold different fuel is refused by the generator by name (kind `harness`); the registered ones do not |
| `...membrane.release` | A passive route of Ca on the bounding patch, its permeability, and the two Hill reads of free Ca in its factor: an activation (half saturation, coefficient) and an inhibition. The store's Ca leak and its release are two routes on the bounding patch |
| `plasma_transport.<membrane>.exchanger` | The exchanger law on the transporter kind: 3 Na in and 1 Ca out a forward cycle. Capacity and the two constants |
| `calcium_channels.<id>` | A channel population of the inner model: membrane, species Ca, its law, maximal permeability, abundance and initial gates in the law's order |
| `ip3_release.<cell>` | The third Hill read of the release's factor: an activation by free IP3 |
| `calcium_controls` | The schedules of the calcium pieces. Every one is [[0.0, 1.0]]. **The engine has one availability per patch,** which multiplies the patch's own permeability and every passive route on it. So `store_passive.<cell>.Ca`, `store_passive.<cell>.K` and `store_release.<cell>` are one schedule there, and so is Ca's plasma leak with `ionic.controls.leak`. The exporter writes each from that one. A block where they differ is refused by the generator by name (kind `harness`); all are 1 here, so nothing is touched |
| `ionic.membranes.<m>.passive`, `ionic.junctions`, `ionic.faces`: the Ca entry | The plasma leak and the junction's Ca permeability are passive routes (the junction's with condition 8 of §3). The faces' Ca diffusivity is the face law's own |

**The release is one species condition a cell, with all its reads** (the build's choice; ruling 7 admits two, and either gives the same factor and the same block). It is recorded in `definition` (`release_conditions`).

### 2.2 Derived declarations, by rule

- **Capacitances** are area × specific capacitance, the double product, as in Part 1.
- **Charges.** A cell's `initial_charge_C` is its membrane's capacitance times its initial voltage, as in Part 1, since its store's voltage is 0 at time 0. A store's is 0. **`initial_voltage_V`** of a cell is derived by the exporter as its charge over its membrane's capacitance, and of a store as its charge over its own.
- **The pumps' standard free energy at 1 M.** The exporter forms it from **three standard potentials of the fuel rows, those of ATP, ADP and Pi** (`standard_mu_RT`), and the model's one standard concentration c° in mM:

      delta_g0_at_1M_J_per_mol = R T [ μ°(ADP) + μ°(Pi) − μ°(ATP) + ln(1000/c°) ]

  since a potential is μ° + ln(c/c°), and a 1 M standard state is c° = 1000 mM. The registry declares a standard potential for every row (0 for a row that the block does not give one), and the standard concentration once. The captured number is the one for the numeric-mM quotient (−37,000 J/mol for every pump), and R T ln 1000 is added to it (−19,875.97 J/mol at 298.15 K). Only the combination is compared, and no single potential is.
- **Fixed charges.** A cell's and a store's are the builder's, by the model's own anchor rule, from the node's charge and **every** row of the node, B, Ca2B, the IP3 rows, the fuel and the traces with it. They are recorded and not compared, since the captured ones refer to Na, K, Cl and Ca alone. The outside regions' (`local`, `near`, `far`) are compared, as in Part 1.
- **The controls** of the captured definitions are 1 at all times (`calcium_controls`).

### 2.3 What the captured form holds and the blocks do not, and why

- **IDs** of entities, of the store's membrane and of every model and law, and `calcium_species`: the maps' keys, or a label.
- **`moieties`** (what each chemical row is made of): they follow from the reactions, and §9's identities use them.
- **The pumps' `metabolism`:** the held fuel rows are the canonical form of it.
- **`delta_g0_J_per_mol`** of the calcium pumps and `specific_capacitance_F_per_m2`: the derived numbers of §2.2 replace them.
- **The execution's** capacities, step, backend and solver, and the observation at 7.3 × 10⁻⁵ s, as in Part 1 (`SPEC.md` §2.3).

### 2.4 The echo's precision

`SPEC.md` §2.4 holds, and:
- **`delta_g0_at_1M_J_per_mol`** is compared within 10⁻¹² of itself **plus 16 ε R T A,** with A = |μ°(ATP)| + |μ°(ADP)| + |μ°(Pi)| + |ln(1000/c°)| of the candidate's own potentials. The exporter writes the three potentials and c° beside it, as two more keys of `pump`: `fuel_standard_mu_RT`, an object with `ATP`, `ADP` and `Pi`, and `standard_concentration_mM`. Without them the second term is 0. **The derivation** of the second term, in units of ε/2 R T A: forming R T, the logarithm, three additions and the product take at most 11. The builder's potentials, which must give the captured number, take at most 8. The registered number's own forming takes at most 9. They add to 28, which is 14 ε, and 16 ε is the power of two above. The term matters only where A is above 2,000, since below it 10⁻¹² is the larger. **A is at most 3,200, and a larger one is a departing echo.** The derivation: the number enters the pumps' affinity, and a forward cycle changes by at most capacity × saturation for each unit of affinity over R T, so an error δ in it moves a pump's cycles by at most δ/(R T) of its scale, and its heat by less. The second term is 16 ε A of R T. At A = (S + 1)/2, with S = 6,400 the steps of the finest judged run, it is 8 ε (S + 1), which is e_round's own share. So the tolerance hides no more than the rounding count that the band already holds. The engine forms the drive from the same potentials at every rate, so its own rounding of it is of that size too.
- **More defaults:** a zero permeability, and any schedule of `calcium_controls`, may be omitted.
- **`standard_mu_RT`** to 10⁻¹² of itself. A declared zero is exactly zero.
- **What stands beyond the block** is §2.5's, and anything else is a departing echo. `inputs` holds the block's own entities and no other.
- **The material tolerances** of the rows that the block gives none for are the engine's largest. They are recorded, and not compared.

### 2.5 What a definition holds beyond its block, exactly

The blocks name the physics. A canonical definition also holds what the engine needs to declare it, and it stands in `definition`, not in `inputs`. **It is this and nothing else. Another species row, another row at a node, or another entity than the table's is a departing echo.** For Part 2 these words govern.

| Beyond the block | Exactly |
| --- | --- |
| Species rows | ATP, ADP and Pi, neutral. There is no fourth. With the block's own, a definition has ten species rows: Na, K, Cl, Ca, B, CaB, Ca2B and the three, and in `ip3_calcium` thirteen, with IP3, IP3_buffer and IP3_bound |
| Rows at a node | **Every node has an amount of every row, which must be positive.** At each cell: ATP, ADP and Pi, held at the pumps' concentrations. At each store's node: ATP, ADP and Pi, a trace. At each region (`local`, `near`, `far`): B, CaB, Ca2B, ATP, ADP and Pi, and in `ip3_calcium` IP3, IP3_buffer and IP3_bound, a trace. No other: a store's own chemical rows are all in its `er`, and a cell's in its `cytosol` |
| The trace | One concentration, the same at every node and for every such row, with no background key: 10⁻¹² mM, a number that the definition chooses. It is recorded, and not compared |
| In the lists by species | A zero permeability of every such row on every membrane, bounding patch and junction, a zero diffusivity on every face, and a material tolerance of every row |
| Entities | For each store: one outside node, one compartment declaration, one bounding patch with no pump of the inner model, one availability schedule. Passive routes, all of Ca: one for each plasma membrane, one for each junction, two for each store. One species condition for each cell. Transporter populations: one for each store, and in `plasma_calcium`, `gated_calcium` and `ip3_calcium` two more for each plasma membrane. Two operators: the compartment law and the local reactions |
| Declared values | The fuel rows' standard potentials, the moieties that the reactions imply, the sites of each reaction and one multiplier schedule a reaction and site, each population's orientation, roles, held rows and availability, the fixed charges of cells and stores, and the IDs of all of these |
| Written as nothing | No pump of the inner model on a bounding patch, no calcium pump of the inner model, no factor on a reaction, no catalogue or evidence of a species, no background, no reservoir |

**The exporter writes in `definition` of every ionic run** (beside the engine's own form), and the judge reads the first three as echo, exactly. **A pool run has none of the three. A key of the three that is missing from an ionic run is a departing echo. Names are this table's and the block's, sorted by code point.** The judge forms the expected rows, traces and counts from the block by the table's rule, so the rehearsal's worlds have theirs. The numbers below are the registered worlds':
- `species_rows`: the sorted list of every species row declared;
- `traces`: an object, node to the sorted list of the rows that hold the trace there, for `local`, `near`, `far`, `store:cell_0` and `store:cell_1`;
- `entities`: an object of counts: `cells` 2, `outside_nodes` 5 (the regions and the stores), `membranes` 4 (the plasma ones and the bounding patches), `channels` 2 (4 in `gated_calcium` and `ip3_calcium`, K's and calcium's), `junctions` 1, `faces` 3, `compartments` 2, `passive_routes` 7, `species_conditions` 2, `populations` 2 (6 in the three worlds with plasma transport), `reactions` 4 (5 in `ip3_calcium`; the declared reactions, and not their sites), `operators` 2;
- `trace_mM`, `release_conditions` and the rest: recorded.

A cluster's are its child's.

**What a trace of 10⁻¹² mM touches** (the author's arithmetic): **nothing that is compared.** Nothing carries it: its permeabilities and diffusivities are zero, no reaction is declared at a region, and no pump reads the fuel there. So its increments are zero, and no class E zero, no moiety and no balance has it in a sum: those are sums of increments at the cytosols and the stores, and the regions' sums are over Na, K, Cl and Ca. Its charge at a region is that of the IP3 rows alone (B's and Ca2B's cancel and the fuel is neutral): at most 1.7 × 10⁻²¹ C, at `far` in `ip3_calcium`, and zero in the other worlds. The regions' fixed charges may therefore be the block's, double for double: the model's charge anchor has a floor of 10⁻²⁰ C (`SPEC.md` §2.2). It enters no potential, which is formed from the anchors and the increments. At a store the fuel's trace is neutral.

## 3. When it is the same equations, and when it is a changed model

**It is "same equations" only if all of these hold** (the builders say so for each consumer, before the registration tag):
1. **The world is closed:** one gauge (`local`), and no held bath.
2. **The store has its own voltage:** a free capacitive node between cytosol and store, with the captured area, specific capacitance and initial voltage.
3. **The release factor is read at every explicit stage of the inner step, from that stage's amounts:** the cell's own row of free Ca (and of IP3 in `ip3_calcium`) over the cell's volume, not over the store's. It multiplies the opening, which is the same equation as multiplying the permeability. A factor held through a step, or a two-state fraction, is a changed model. **The factor's form** is 1/(1 + (K_a/Ca)^n) × 1/(1 + (Ca/K_i)^m), and in `ip3_calcium` × 1/(1 + (K/IP3)^q), each a Hill term (read in the captured law's code).
4. **The pumps' standard state** is the one of §2.2.
5. **The exchanger's rate** is the captured symmetric-barrier law: 3 Na for 1 Ca, third powers in the sodium terms, a denominator of the captured product form, and no standard-state part.
6. **The reactions** are the same mass-action kernel: the same rate constants at 1 mM, the same standard potentials, the same stoichiometry.
7. **The Ca channel** carries Ca²⁺ by the constant-field law at valence 2 with P = P_max × abundance × availability × m² h, and the captured gate kinetics with their −10 mV shift and no temperature term.
8. **Calcium's junction route carries the junction's own open fraction:** the captured flux multiplies every species' permeability, Ca's with the others', by the relaxation gate and the availability (read in the captured code). A Ca route that does not is a changed model. The captured gate starts at 0.6, so it would differ by tens of per cent in `junction_Ca`. **The live passive kind does it:** a passive route on a junction is opened by that junction's gate times its availability at every explicit stage, and the junction's sender and receiver give the sign (the lead's statement of 25 November, a fact of the kind's code, which this author has not read).
9. **The splitting** is an error of the candidate's order and not of the equations. The reactions are Strang halves around the inner step, whose stages start from the state after the first half.

**This section states the captured forms,** read in the captured code. The live forms are stated by the builders' README, read in the live code, and the lead confirms both at the tag. The builders read conditions 1, 2 and 9 in the definition (one gauge; a free store node with one patch; Strang halves around the IMEX step), condition 3 as a condition read at every explicit stage from that stage's amounts over the cell's volume, which multiplies the route's opening, condition 5 as the live exchanger's monomial form with the constants that the builders' README gives, and condition 7 as m² h with the ten-millivolt shift and no temperature term. This author has read none of the live forms.

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

Part 1's labels of the inner world stand (`kv15_mh`, `nak_pump_positive`, `maintained_fuel`, `junction_relaxation`, `logmean_face`, `constant_field`, `closure`, and the pool's). **A run's entry in the note** (`TABLE.md` §5): its `model` is the composite's, and its inner model stands among `laws`; `operators` are the compartment law and the local reactions; `kinds` are the three kinds, taken from the parsed definition's declared kinds, since a definition does not write them; the rest are `laws`. **The note comes after the build** (ruling 8). If the build declares a string that no label here names, the lead adds the label by a dated line, before any run. `delta_g0_at_1M_J_per_mol` carries no ID. A pool run's entry is Amendment 1's item 8.

### 4.4 The consumers' tables

One file per consumer: `table_<consumer>.json` for the eight names of §1, in the folders of `TABLE.md` §1. `part` is 2.

## 5. Compared times, worlds and sets

- **The children:** every 12.5 µs from 0 to 1 ms (81 rows), then every 100 µs from 1.1 to 20 ms (190 rows), 271 rows (`history_times`). The rows up to 1 ms resolve the store's fast modes. The potentials at `potential_times_s`.
- **The clusters:** 0.02 s for every entry, and 2.5, 5, 10, 15 and 20 ms (`summary_times_s`) for `voltage`, `store_voltage`, `channel_K_summary` and the four free cytosolic ions (`cyt_Na_summary`, `cyt_K_summary`, `cyt_Cl_summary`, `cyt_Ca_summary`), where the captured summaries exist. A `_summary` entry's scale, reference and closure are its own series'. The row at 0.02 s is in both, so one difference there fails both entries.
- **A family** is the three runs of one world (a child), or of one seed and world ID (a cluster), at h₁, h₂, h₃: one a child, eight a cluster.
- **World IDs 0 and 1** of each of four seeds (`cluster_*`). Their pools are worlds 0 and 1 of `base`, bit for bit (the 19 arrays of the four clusters, at every seed and captured step: 912 comparisons, all equal). So **the reference path of a cluster's world is `reference_paths.json`'s of `base`,** the same seed, cell and world. The 19 arrays and the exposure are the cluster's own captured checkpoint's (READOUTS §4 and §5, as `base`'s: `[world, cell, ...]`).

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

**The potentials** (`potentials`, at `potential_t`): `voltage` (membranes: `membrane_voltage_V[plasma patch]`; captured `observations.plasma_voltage_V`, and `final_voltage_V` in the clusters' summaries), `phi_out` (regions but the gauge: `extracellular_potential_V[region]`; captured `observations.extracellular_potential_V`, children alone), and `store_voltage` (cells: 0 minus `membrane_voltage_V[bounding patch]`; captured `observations.er_voltage_V`, and `calcium.er_voltage_V` in the summaries). They exist at observed rows alone, since no state field holds a voltage. **At potential time 0** `store_voltage` is the field solve's own residue and need not be exactly 0. It is judged there as at every potential time, in class S and within its entry's band, and it is no class E zero.

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

## 11. The runs

**`inputs_part2.json` lists 127:** 12 for the four children, 112 for the clusters (a cluster's 4 pool runs and 24 ionic runs), one restart and two engine plants.
- **The restart** (support): `ip3_calcium h=1.25e-05 restart`, at 0.01 s, by `SPEC.md` §4 and `TABLE.md` §3. It resumes a checkpoint of its judged run. `ip3_calcium` holds every mechanism of the eight consumers but the pools, so its state holds every kind of state there is. The clusters have no pool restart: their pools are `base`'s code and seeds, and Part 1 restarts those.
- **EP3** (`ip3_calcium plant release`, at h₃): both stores' release permeability × 1.01.
- **EP4** (`cluster_gated_calcium plant swapped`, seed index 1, world 0, at h₃): each K channel's schedule is the other cell's path. Its `pool_seeds` are by position, and so its honest run's (Amendment 1, item 7, which holds for EP4).
- **An engine plant's block differs from its honest run's only by its change.** EP3's is the release permeability × 1.01 in both cells, EP4's is `exchange_channels` of the two cells. A `declared_change`'s path begins at the world's block, whose first key is `ionic`, `stores` or another of §2.1's (in Part 1 it begins inside `ionic`).
- **The retry's runs** are named by rule: `<family> h=1.5625e-06 retry`. The retry run of every family is made in the registered batch. They are exported only with the sha256 of `retry_owed.json`, which the lead gives from the judge's record. No support run is made at the retry's step.
- **Of Amendment 2** the exporter's builder receives items 2, 4, 7, 8, 9.1 and 10 (`AMENDMENT-2-2026-11-25_EXPORTER.md`). Item 2 does not hold here: §2.4 and §2.5 govern. Items 4, 7, 8 and 9.1 hold where they apply. There is no pool restart, so 7 (e) has no use, and every plasma membrane has its Na/K pump, so 8 (d) has none.
