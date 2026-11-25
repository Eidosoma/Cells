# Part 2: the four calcium clusters, and the four assembly-regulated ones

`CRITERIA.md`, `TABLE.md`, `AMENDMENT-1-2026-11-25.md` and the rules of `README.md` hold here, and of `AMENDMENT-2-2026-11-25.md` what §16.1 says. This file states what Part 2 needs beyond them. **Where it differs from Part 1 it says so, and why (§16), and it governs for the eight consumers of Part 2.** Part 1's files do not move. `inputs_part2.json` governs the numbers, and `PART2_BLOCKS.md` prints its literal blocks. `PART2_EXPORTER.md` holds the sections that the exporter's builder receives, word for word, and the builder does not receive this file (§7 and §14 hold the plants).

**Status, 25 November 2026:** complete, and read by its independent auditor (yes, with named edits, which are made). The rows that waited on two design notes are answered (§0), from the lead's rulings of 25 November and from the names that the notes' author and the store worlds' builder gave the author. The author read neither note, nor any builder's branch, nor a run of the engine. It is revised directly until its tag. Nothing of a run of either side enters a bound.

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
| Whether calcium's junction route carries the junction's gate and availability | It does: a fact of the live kind's code (the lead's ruling on Part 2's audit) | §3, condition 8 |

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

### 5.1 The two sets of a cluster

**Each cluster is reported in two sets,** as `base` is (`CRITERIA.md` §8), and here the sets are whole seed indices. A prototype had run the pools of `base` s0 w0 and s0 w1, which are the two worlds of every cluster's seed index 0.
- **Set A, not blind on its pools:** seed index 0. Its pool run and its two families.
- **Set B, blind:** seed indices 1, 2 and 3. Three pool runs, six families, and the cluster's plants and engine plant.
- **The verdict of a cluster is the worse of its two sets' verdicts.** Set B must pass by itself, with every mechanism tested by a home entry of one of its families. Set A adds nothing to a pass. No run belongs to both sets, and no plant of a cluster is scored on seed index 0.
- **The ionic entries of set A** are not affected by what was seen: no captured calcium definition, alone or as a cluster, was ever composed and stepped on the live engine before the Part 2 tag (the lead's statement; the protocol's §11, item 13). They are in set A all the same, so that nothing rests on where the line is drawn.
- **The four children** are one set, and blind in that sense. **Three worlds with many of the registered numbers had run composed** (the protocol's §11, item 13, which says which): one cell and store with numbers of `plasma_calcium`, a two-cell world with `gated_calcium`'s topology, and one cell and store with the registered store's numbers. The record says so beside the children's verdicts.
- **Verdicts are per consumer** (`CRITERIA.md` §8). Part 2 passes when each of its eight consumers does. A consumer that fails, or is inconclusive after the retry, goes to the user's decision, as in Part 1.

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

**Every mechanism is observable at U_c = 0, but the store's capacitor in the four clusters, which is not tested there.** The smallest margin of a home, against the rule of 10, at the two triples' bands (§13 says which band scores a plant):

| Band | The children | The clusters (halved) |
| --- | --- | --- |
| the first triple's, U_c = 0 | 75 (`store_K` of `ip3_calcium`) | 176 (`store_voltage` of `ip3_calcium`'s cluster) |
| the retry's, U_c = 0 | 68 (`store_K`) | 105 (`store_voltage`) |
| the retry's at the widest that an unresolved triple gives (U_c = θ/3) | 29 (`store_K` of `ip3_calcium`) | 16 (`store_voltage` of `ip3_calcium`'s cluster) |

The structural plants' smallest is 1e+05 at that last band (SC5, `store_release`). Each row below holds the planted ratio and the smallest margin over the children that hold the mechanism, and for the clusters (at 0.02 s, §7.1) the ratio used and the smallest margin, at the first triple's band:

| Mechanism | Home (plant) | Children: ratio, smallest margin | Clusters at 0.02 s: ratio and smallest margin, both halved |
| --- | --- | --- | --- |
| leak permeability | `leak_Na` (P-leak) | 1.0e-02, 3e+07 | 5.0e-03, 2e+07 |
| leak permeability | `leak_K` (P-leak) | 9.9e-03, 3e+06 | 5.0e-03, 2e+06 |
| leak permeability | `leak_Cl` (P-leak) | 9.8e-03, 1e+06 | 4.9e-03, 5e+05 |
| channel permeability | `channel_K` (P-channel) | 1.0e-02, 2e+04 | 5.0e-03, 1e+04 |
| channel kinetics | `gate_m` (P-kinetics) | 3.7e-03, 1e+06 | 6.3e-03, 5e+05 |
| channel kinetics | `gate_h` (P-kinetics) | 3.4e-05, 3e+04 | 1.7e-05, 2e+04 |
| Na/K pump | `pump` (P-pump) | 1.0e-02, 1e+07 | 5.0e-03, 6e+06 |
| junction permeability | `junction_Na` (P-junction) | 9.3e-03, 3e+05 | 4.7e-03, 2e+05 |
| junction permeability | `junction_K` (P-junction) | 8.8e-03, 2e+05 | 4.4e-03, 9e+04 |
| junction permeability | `junction_Cl` (P-junction) | 8.6e-03 to 8.7e-03, 1e+05 | 3.9e-03, 4e+04 |
| junction gate | `junction_gate` (P-jgate) | 5.6e-04, 2e+05 | 2.8e-04, 1e+05 |
| faces | `face_Na` (P-face) | 9.8e-03, 3e+06 | 4.9e-03, 1e+06 |
| faces | `face_K` (P-face) | 9.8e-03, 9e+06 | 4.9e-03, 4e+06 |
| faces | `face_Cl` (P-face) | 9.9e-03, 1e+06 | 4.9e-03, 7e+05 |
| electrical closure | `voltage` (P-pump) | 3.5e-03, 2e+04 | 1.7e-03 to 1.8e-03, 1e+04 |
| electrical closure | `phi_out` (P-faceK) | 9.2e-03, 4e+06 |  |
| plasma Ca leak | `leak_Ca` (P-leakCa) | 9.9e-03, 3e+07 | 5.0e-03, 2e+07 |
| Ca junction route | `junction_Ca` (P-junctionCa) | 1.0e-02, 2e+05 | 5.0e-03, 1e+05 |
| Ca faces | `face_Ca` (P-faceCa) | 9.9e-03, 3e+06 | 5.0e-03, 2e+06 |
| store Ca leak | `store_leak_Ca` (P-storeleakCa) | 1.0e-02, 3e+06 | 5.0e-03, 2e+06 |
| store K leak | `store_voltage` (P-storeleakK) | 9.9e-03 to 1.0e-02, 4e+02 | 5.0e-03, 2e+02 |
| store pump | `store_pump` (P-storepump) | 9.9e-03, 2e+06 | 5.0e-03, 9e+05 |
| release permeability | `store_release` (P-release) | 1.0e-02 to 1.1e-02, 7e+05 | 5.1e-03 to 5.3e-03, 4e+05 |
| release's calcium factor | `store_release` (P-activation) | 6.3e-03 to 6.6e-03, 5e+05 | 3.1e-03 to 3.3e-03, 2e+05 |
| release's calcium factor | `store_release` (P-inhibition) | 1.2e-04 to 1.3e-04, 9e+03 | 5.9e-05 to 6.6e-05, 4e+03 |
| cytosolic buffer, first site | `extent_bind_0_first` (P-bind0a) | 5.7e-03, 1e+06 | 2.9e-03, 6e+05 |
| cytosolic buffer, second site | `extent_bind_0_second` (P-bind0b) | 9.7e-03 to 9.8e-03, 2e+04 | 4.9e-03, 9e+03 |
| store buffer, first site | `extent_bind_1_first` (P-bind1a) | 3.5e-03, 5e+06 | 6.3e-04 to 6.4e-04, 9e+05 |
| store buffer, second site | `extent_bind_1_second` (P-bind1b) | 8.3e-03, 4e+06 | 4.1e-03, 2e+06 |
| store capacitor | `store_K` (P-storecap) | 1.4e-04 to 1.7e-04, 8e+01 | **not tested** (ratio halved 2.9e-05 to 3.9e-05, margin halved 13 to 47) |
| plasma calcium pump | `ca_pump` (P-pmca) | 1.0e-02, 6e+06 | 5.0e-03, 3e+06 |
| exchanger | `exchanger` (P-ncx) | 9.9e-03, 6e+05 | 4.9e-03, 3e+05 |
| exchanger | `exchanger` (P-ncxkm) | 8.7e-05, 5e+03 | 4.3e-05, 3e+03 |
| Ca channel permeability | `ca_channel` (P-cav) | 1.0e-02, 3e+04 | 5.0e-03, 1e+04 |
| Ca channel kinetics | `ca_gate_m` (P-cavkinetics) | 3.6e-03, 1e+06 | 3.8e-03, 5e+05 |
| Ca channel kinetics | `ca_gate_h` (P-cavkinetics) | 1.7e-03, 2e+06 | 9.9e-04, 1e+06 |
| IP3 factor | `store_release` (P-ip3activation) | 1.3e-02, 9e+05 | 6.4e-03, 5e+05 |
| IP3 binding | `extent_ip3_binding` (P-ip3binding) | 7.8e-03, 1e+07 | 3.9e-03, 7e+06 |
| store K leak, **first home: not tested there** | `store_leak_K` (P-storeleakK) | 1.4e-04 to 1.7e-04, 80 to 184 | not tested there |
| store capacitor, **first home: not tested there** | `store_voltage` (P-storecap) | 9.9e-05 to 1.5e-04, 5 to 8 | not tested there |

- **Mechanisms with several plants** (the calcium factor, the exchanger) are tested by the largest of them (§7.1). The inhibition constant and the exchanger's Na constant are weak plants (a ratio of 10⁻⁴ or less), and their mechanisms are tested by the activation constant and the capacity.
- **The store's two electrical mechanisms are the weakest.** The K leak's 1 % plant moves `store_voltage` by 1 % of a voltage that is small against its scale (the gross throughput of K), and the capacitor's moves `store_K` by 1.4 × 10⁻⁴ to 1.7 × 10⁻⁴ of itself in the children. A candidate whose error estimate there is above about a tenth of the planted distance cannot test them, and the child is then inconclusive, with the reason `power`. The candidate's step decides, and no band is widened for it.
- **In the four clusters the capacitor is not tested** (the lead's ruling of 25 November): a cluster's captures hold one end state, and not the early rows where the capacitor shows. At the clusters' end its plant moves `store_K` by 2.9 × 10⁻⁵ to 3.9 × 10⁻⁵ (halved), so a comparison there would be a thin one. It is listed as not tested in each cluster, and nothing may be claimed of it there. This exemption is declared before any run, so `CRITERIA.md` §8's rule (a consumer with an untested mechanism is at best inconclusive) does not apply to it: the capacitor is no mechanism of the four clusters' test (`margins_part2.json` `cluster_not_tested`).
- **The margins were formed again on 25 November under §8's bands** (e_store, the closure, the reactions' heats per compartment), and again after Part 2's audit, with the own closure of the voltages and of the entries of `closure_terms`. No home moved.

**Homes replaced on 25 November, after the planted runs had been read on the reference side, and before any candidate run (dated line).** The lead accepted it as a replacement of plants. The first homes stay in the table, marked **not tested there**, with their figures (`margins_part2.json` `first_homes_not_tested_there`). The protocol's §11 says that the choice came after the planted runs were read.
- **Store K leak:** from `store_leak_K` to `store_voltage`. The K leak is so fast that K's own transfer follows calcium's, and its 1 % plant moves `store_leak_K` by 1.4 × 10⁻⁴, while the store's voltage is set by the leak and moves by 1 %.
- **Store capacitor:** from `store_voltage` to `store_K`. At the potential times the store's voltage is quasi-steady and does not know its capacitance. `store_K` holds the early charging.

**The structural plants:**

| Plant | Named entry: distance, margin |
| --- | --- |
| SC1 (`spatial_calcium`) | `store_release`: 1.3e-04, 9e+07; `store_Ca`: 1.2e-04, 4e+07 |
| SC3b (`spatial_calcium`) | `store_leak_Ca`: 1.5e-07, 1e+06; `store_release`: 1.1e-06, 8e+05 |
| SC4 (`spatial_calcium`) | `store_pump`: 1.0e-04, 5e+08; `store_Ca`: 9.9e-05, 3e+07 |
| SC5 (`spatial_calcium`) | `store_leak_Ca`: 3.7e-08, 3e+05; `store_release`: 2.9e-07, 2e+05 |
| SC6 (`spatial_calcium`) | `extent_bind_0_first`: 1.0e-03, 6e+08; `cyt_Ca`: 1.1e-03, 5e+08 |
| SC13 (`spatial_calcium`) | `heat_store_pump`: 6.5e-04, 3e+07 |
| SC7 (`plasma_calcium`) | `exchanger`: 6.0e-07, 2e+06 |
| SC8 (`plasma_calcium`) | `ca_pump`: 6.2e-05, 1e+09; `cyt_Ca`: 4.2e-05, 2e+07 |
| SC12 (`plasma_calcium`) | `heat_ca_pump`: 4.3e-04, 1e+08 |
| SC9 (`gated_calcium`) | `ca_channel`: 2.2e-06, 2e+06 |
| SC10 (`gated_calcium`) | `ca_channel`: 2.1e-05, 1e+07 |
| SC2 (`ip3_calcium`) | `store_release`: 1.9e-04, 1e+08 |
| SC11 (`cluster_gated_calcium`, seed index 1) | `ca_channel`: world 0 3.6e-06, 3e+06; world 1 3.6e-06, 3e+06 |
| SC14 (`cluster_gated_calcium`, seed index 1) | `channel_K`: world 0 4.3e-07, 3e+05; world 1 2.1e-07, 1e+05 |

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

**The closure:** `closure_share` = 10⁻¹⁰, and **e_close = 10⁻¹⁰ s in every entry that has no number of its own.** Those that have one are in `closure_terms_V` (the three potentials, in V) and in `closure_terms` (the entries that a drifted voltage reaches above that share, each in its own unit; 35 in `spatial_calcium`, 41 in `plasma_calcium`, 45 in the other two), and it takes the place of the share.

**The derivation.** It is Part 1's question, what potential error the two codes admit, asked of an IMEX step and of every path that a potential takes. **A criterion may not rest on a code's staying below what it admits.**
- **What the engine admits.** At each implicit stage a node's charge residual is at most 3 × 10⁻²⁵ C + 2 × 10⁻¹² of the larger of its charge and of the solve's own product (its declared constants, read at 49529e71). Legacy forms a membrane's and a store's voltage from its charges with no solve, and its free offsets are Part 1's (2.13 × 10⁻¹² V*).
- **As a stage's potential errors,** each the largest over its entities: a membrane's 2 × 10⁻¹² V* + 2 × 3 × 10⁻²⁵ C/C_m (its cell's and its store's residuals) = 4.4 × 10⁻¹³ V. The junction's, its two membranes' together, 8.47 × 10⁻¹³ V. A store's 2 × 10⁻¹² V* + 3 × 10⁻²⁵ C/C_s = 2.7 × 10⁻¹³ V. A free offset's 2.01 × 2 × 10⁻¹² V* + 3 × 10⁻²⁵ C × Σ|K⁻¹|/(γ h) = 1.38 × 10⁻¹² V at the retry's 1.5625 µs, the largest of the four steps (γ = 1 − 1/√2). K is the matrix of the faces' conductances over the free regions, each (F²/(R T)) Σ z² D A/L × the logarithmic mean of the two initial concentrations. Σ|K⁻¹| is the largest row sum of its inverse. 2.01 is that row sum times the region's own ΣG (2.0035 here, and formed again for other faces).
- **What the voltages may have drifted by** (`closure_terms_V`, the same in every world that has the entry):
  - **`phi_out`, 5.16 × 10⁻¹³ V:** Part 1's number (the conductances formed again with calcium's: its share of a face's is 7 × 10⁻⁵, the row sum of K⁻¹ is 2.0035 and no conductance exceeds 0.526 of the smallest ΣG). It is not a stage's potential. It is solved again at an observed row, from that row's amounts, by the field solver of §4.1. A stage's error enters the faces' transfers and through them the regions' amounts, which move it by at most 7 × 10⁻¹⁴ V (the faces' share of their scales, over the smallest amount, as a change of a logarithm). Legacy's solve at its limit (2.6 × 10⁻¹³ V), the floor variant's at its own (9.0 × 10⁻¹³ V* = 1.1 × 10⁻¹³ V, `SPEC.md` §6) and that drift are 4.3 × 10⁻¹³ V.
  - **`voltage`, 9 × 10⁻¹² V, and `store_voltage`, 2.9 × 10⁻¹¹ V:** the observed row's solve (4.4 × 10⁻¹³ V and 2.7 × 10⁻¹³ V) and what the stages' errors have done to the charge, 8.5 × 10⁻¹² V (the Ca channel, the K channel and the junction's K are the larger parts; 4.6 × 10⁻¹² V in `spatial_calcium`) and 2.86 × 10⁻¹¹ V (K's leak is nearly all of it), added, and rounded up to two figures. The second is Σ over the membrane's (or the store's) routes, its cell's junction among them, of the route's one-pass share (below) × its own scale there × its charge a move (|z|, 1 for the Na/K pump and the exchanger, 2 for a calcium pump), over the capacitance, with no restoring current counted: the largest over the membranes, or the stores, and over the worlds. They are potentials, and a share of their scale is not their closure: their scales are gross throughputs over a capacitance, 0.4 to 0.5 V and 16 V, where the store's voltage is 5 × 10⁻⁵ V.
  - Each code at its limit: **legacy's share of the last two is zero.**
- **Two passes are counted.** A stage's potential error moves the readout that is formed with it, which is one pass. A route, a gate or a channel then reads a voltage that has drifted by what `closure_terms_V` admits, which is one more. So a path is taken at δ = the stage's error + the drift: 9.4 × 10⁻¹² V at a membrane, 1.9 × 10⁻¹¹ V at the junction (two membranes), 2.9 × 10⁻¹¹ V at a store and 2.2 × 10⁻¹² V at a free offset (both codes and `phi_out`'s).
- **As shares of s,** with u = F/(R T) and χ as in `SPEC.md` §5: a constant-field route's |z| u δ/χ; a pump's u δ a net charge (1, and 2 for the calcium pumps), and 1.5 u δ for the exchanger; a gate's slope (its target's largest slope + 0.368 × its time constant's largest logarithmic slope) × δ, from the captured laws over their domain; a channel's and the junction's, their route's and their open fraction's together; a heat's, its transfer's and its affinity's together. δ is the membrane's, the junction's, the store's or the free offset's.
  - **The five gate slopes,** per V: `gate_m` 39.06 + 0.368 × 86.02 = 70.7, `gate_h` 71.43 + 0.368 × 22.46 = 79.7, `ca_gate_m` 41.67 + 0.368 × 76.39 = 69.8, `ca_gate_h` 39.06 + 0.368 × 43.33 = 55.0, and `junction_gate` 46.86 + 0.368 × 87.71 = 79.1. An open fraction takes the sum of its gates' slopes, each as often as the law has it: m and h for `channel_K`, m twice and h for `ca_channel`, and the one gate for the junction.
  - **A heat** takes, route by route, (the transfer's share + the affinity's) × the route's own heat scale, and the sum over the routes that its scale sums. The affinity's share is |z| u δ/χ(z) for a constant-field route (for a channel and the junction too, without the open fraction), u δ/χ(1) for the Na/K pump and the exchanger, and 2 u δ/χ(2) for a calcium pump. The route's own heat scale is `SPEC.md` §5's for a passive route and for the Na/K pump. A calcium pump's is its scale × 10⁻³ (|ΔG| + R T |ln(ADP Pi/ATP)| + R T (1 + |ln Ca ratio| + 2 u V*)), with ΔG = `delta_g0_at_1M_J_per_mol` − R T ln 1000 and the three in mM. The exchanger's is its scale × 10⁻³ R T (4 + 3 |ln Na ratio| + |ln Ca ratio| + u V*). The ratios are of the initial concentrations on the two sides. A reaction's heat takes its extent's closure × 10⁻³ R T (1 + |Δμ°| + Σ ν |ln(c/c°)|), as its scale does, and its compartment's sum.

The paths' shares of s:

| Path | One pass | With the drift |
| --- | --- | --- |
| plasma leaks (z = 1, Ca) | 3.0, 3.3 × 10⁻¹² | 6.5, 7.1 × 10⁻¹¹ |
| Na/K pump | 1.7 × 10⁻¹¹ | 3.7 × 10⁻¹⁰ |
| plasma calcium pump | 3.4 × 10⁻¹¹ | 7.4 × 10⁻¹⁰ |
| exchanger | 2.6 × 10⁻¹¹ | 5.5 × 10⁻¹⁰ |
| `gate_m`, `gate_h`, `ca_gate_m`, `ca_gate_h` | 3.1, 3.5, 3.1 and 2.4 × 10⁻¹¹ | 6.7, 7.5, 6.6 and 5.2 × 10⁻¹⁰ |
| `junction_gate` | 6.7 × 10⁻¹¹ | 1.5 × 10⁻⁹ |
| the junction's routes | 7.3 × 10⁻¹¹ | 1.6 × 10⁻⁹ |
| `channel_K` | 6.9 × 10⁻¹¹ | 1.5 × 10⁻⁹ |
| `ca_channel` | 8.9 × 10⁻¹¹ | 1.9 × 10⁻⁹ |
| faces (both codes) | 1.1 to 1.2 × 10⁻¹¹ | 1.5 to 1.6 × 10⁻¹¹ |
| store leaks, release | 1.9 to 2.0 × 10⁻¹² | 2.0 to 2.2 × 10⁻¹⁰ |
| store pump | 2.1 × 10⁻¹¹ | 2.3 × 10⁻⁹ |

- **A sum takes the sum.** `exchange_x`, the cells' and regions' rows and the heats are sums of routes, and their closure is Σ share × scale over the routes, each with its own scale there, as their scale is Σ scale (a Na/K pump moves 3 Na and 2 K, an exchanger 3 Na and 1 Ca). An extent, a buffer's row and a reaction's heat follow the calcium that has moved: their closure is what calcium's movers into their compartment may be off by, since binding can follow no more. In a cytosol those are the routes of its cell's row of `exchange_Ca` and its store's leak, release and pump, and in a store those three. IP3's binding and its rows hold no calcium, and take none. Every entry takes the largest over its entities.
- **An entry whose sum is at most 10⁻¹⁰ s keeps the share** (the plasma leaks, the faces and their heat, the regions' Na, K and Cl, the IP3 rows and a few more: `closure_terms` says which by not naming them). **Every other has its own number in `closure_terms`,** rounded up to two figures: the gates, the channels, the junction's routes, the pumps, the exchanger, the store's routes, their heats, and the sums and the reactions that hold or follow them.
- **A third pass is not counted.** Counted without a restoring current the passes have no end: the second one's shares would drift `voltage` by up to 1.9 × 10⁻¹⁰ V, inside its own band (e_store alone is 1.1 × 10⁻⁸ V), and `store_voltage` by 3.1 × 10⁻⁹ V, which its band (6.7 × 10⁻¹⁰ V at U_c = 0) does not hold and which its K leak would undo in about 0.2 ms (its capacitance over that leak's conductance). **Every route reads the voltage that it drives, so the membranes' routes restore it in the same way:** what a route moves in answer to the drift opposes the drift, at fixed gates, and adds nothing to it. (A plasma membrane's answer is slow: 220 ms by its leaks alone. A gate can act either way.) **What a direct solve leaves is far below what the engine admits at any pass,** and the rehearsal looks at it (§15).
- **The reactions** are advanced by an explicit scheme with no solve, so they have no closure of their own.
- **C0 re-forms `closure_terms_V` and `closure_terms` by this section's rule,** beside what `CRITERIA.md` §5 lists (`phi_out`'s is Part 1's number, 4.3 × 10⁻¹² V*). **A cluster's scales, references and closures are its child's, without `phi_out`, and an entry named `<readout>_summary` takes its readout's.** A rehearsal's runner forms its worlds' by this section too.

## 9. Conservation and the reported identities

**Conservation is the engine's own rule at every accepted step** (`CRITERIA.md` §4.4). No identity below is judged. The judge forms and reports them, each beside READOUTS §5's bounds (which are Part 1's judged ones; the energy's with its own U_c), and flags a residual above its bound to the checker:
- the balances of each cell's whole-cell ledger, region, store row and cytosol row, and the closed world;
- **the moieties** in each compartment: B + CaB + Ca2B (cytosol and store apart), IP3 + IP3_bound and IP3_buffer + IP3_bound (cytosol), and calcium's total: cytosol (Ca + CaB + 2 Ca2B) + store (the same) = `exchange_Ca`;
- **the capacitors:** `voltage` − V₀ = (F 10⁻¹⁵/C_m) Σ_x z_x `exchange_x`, and `store_voltage` less its own value at time 0 = (F 10⁻¹⁵/C_s) Σ_c z_c `store_c`;
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
- **An engine plant's block differs from its honest run's only by its change.** EP3's is the release permeability × 1.01 in both cells, EP4's is `exchange_channels` of the two cells. A `declared_change`'s path begins at the world's block, whose first key is `ionic`, `stores` or another of §2.1's (in Part 1 it begins inside `ionic`).
- **The retry's runs** are named by rule: `<family> h=1.5625e-06 retry`. The retry run of every family is made in the registered batch. They are exported only with the sha256 of `retry_owed.json`, which the lead gives from the judge's record. No support run is made at the retry's step.
- **Of Amendment 2** the exporter's builder receives items 2, 4, 7, 8, 9.1 and 10 (`AMENDMENT-2-2026-11-25_EXPORTER.md`). Item 2 does not hold here: §2.4 and §2.5 govern. Items 4, 7, 8 and 9.1 hold where they apply. There is no pool restart, so 7 (e) has no use, and every plasma membrane has its Na/K pump, so 8 (d) has none. In 9.1 a cluster's channels are those of its ionic block, the K channels: a calcium channel has no switch list, and its schedule is in `calcium_controls`.

### 11.1 The engine plants' named entries

- **EP3:** `store_release`. Its registered distance is the planted run's (`P-release`): 1.1 × 10⁻⁶ fmol, a margin of 7.4 × 10⁵.
- **EP4:** `channel_K` and `channel_K_summary`. Its registered distance is SC14's: 4.3 × 10⁻⁷ fmol, 2.2 times the honest `channel_K`, a margin of 2.9 × 10⁵. **Its `switch_list` and its `controls.channel` are class E against the swapped paths,** and it is unscorable if they or its `pool_seeds` depart.
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

**The runs are made up front.** An honest order-2 run can leave entries mixed at the first triple (below), and each is owed the retry. So the retry run of every family is made in the registered batch (§11), from the same snapshot: 36 of them. **They are kept unread.** No retry table is exported before `retry_owed.json` is hashed, and `table-retry/` is exported only after that, with the sha256 of `retry_owed.json` that the lead gives from the judge's record. No support run is made at the retry's step: `ip3_calcium`'s restart is at h₁, and no other is registered. Each retry run is judged only where it is owed. One that is not owed is recorded, flagged and not judged (`CRITERIA.md` §7).

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

**Excluded** means that rounding cannot explain the measured order: with q_lo = log₂((d₂ − 2 e)/(d₁ + 2 e)) and q_hi = log₂((d₂ + 2 e)/(d₁ − 2 e)), both at the retry's triple (q_lo is minus infinity where d₂ is at most 2 e, and q_hi plus infinity where d₁ is), the interval [q_lo, q_hi] does not meet [1.5, 4.5]. For an honest order-2 entry the interval always holds 2, since (d₂ ∓ 2 e)/(d₁ ± 2 e) brackets t/(t/4) = 4. So no honest entry is inconclusive by this rule for being mixed. **It still refuses** every entry with d₁ above θ and d₂ below it (q_hi is at most log₂(12/8) = 0.58).

**What an unresolved or mixed pass at the retry's does not exclude: a first-order error that is small enough.** Let a first-order error have the truncation t in d₂ (6.25 to 3.125 µs), and so t/2 in d₁. **It can pass where t is at most 2 θ + 4 e = 24 e,** and not above.
- **Where the bound comes from.** The entry is not resolved only if d₁ is at most θ, and rounding can lower d₁ by 2 e at the most, so t/2 − 2 e is at most θ. Above that it is resolved, and its measured order is at most log₂((t + 2 e)/(t/2 − 2 e)), which is at most log₂(26/10) = 1.38, below 1.5, so it is inconclusive by `order`. At or below it, the interval may or may not exclude it, by where rounding falls. With none in its favour it is excluded above t = (2 + 2 × 2^(3/2)) e/(2^(1/2) − 1) = 18.5 e.
- **The band does not exclude it.** What a first-order error leaves in Y* is t/3, and 2 U_c is t/3 (U_c is d₁/3 = t/6).
- **How much that is.** In an entry that reads no amount, e is 2.3 × 10⁻¹¹ s, and 24 e is 5.5 × 10⁻¹⁰ s. In Y* it leaves at most 1.8 × 10⁻¹⁰ s.
- **The first triple may have shown it.** Where its differences were above θ there, an order of 1 was resolved and the entry was owed the retry for it. The retry's triple replaces the first, so that evidence is in the record and decides nothing. The record says both classes.

- **What e leaves out, and why.** e is rounding. The closure that the engine admits (§8) is nine times e at the first triple in an entry that has the share, and more in one with a closure of its own: 1,090 times e in `extent_bind_0_second`, the most, and 515 in `cyt_Ca2B`, whose e holds its e_store (both in `ip3_calcium`, where their closure is 1.24 × 10⁻⁸ s), 230 in `heat_store_pump`, 210 in `store_pump`, 180 in `heat_ca_channel` and 170 in `ca_channel`. It is in neither e nor θ, as in Part 1, since what a direct solve leaves is far below it. Where a solve left as much as it may, a difference would carry up to 2 (e + c) of noise, c the admitted closure, and an honest entry could be mixed, or outside its window, by noise alone. **Tried on 200,000 random honest entries** (t log-uniform from 0.1 e to 1.6 × 10³ e; each difference t or t/4 plus a uniform noise within ± 2 (e + c), and at the retry's t/4 and t/16 with ± 2 (2 e + c)). **Inconclusive by `order` at the retry's are the ones outside their window and the mixed ones whose order is excluded.** With c = 8.8 e they are one in seven at the whole admitted closure (one in seventeen outside, one in thirteen mixed), one in four thousand at a tenth of it, and none at a hundredth; at the first triple one in five is outside its window and one in three mixed, and each is owed the retry. With c = 172 e (`ca_channel`) they are four in five at the whole, one in 310 at a hundredth and none at a thousandth, and with c = 1,090 e (`extent_bind_0_second`) five in six at the whole, one in four at a hundredth, one in 1,700 at a thousandth and none at a ten-thousandth. **Such an entry is inconclusive by `order`, and it never fails:** |Y* − L*| is at most U_c + e_round + e_store + the two codes' closure + U_l + e_round(S_l), and β holds each of them, and U_c and U_l twice. The rehearsal looks for it (§15).
- **What the retry's run judges:** the owed entries of its family, its own D, and its own class E (the structural zeros, and a cluster's switch list, channel schedule and pool seeds). A miss of its class E fails: the retry's triple is the same world.
- **What passed is not turned.** An entry that passed at the first triple keeps its pass, and one that failed keeps its fail, whatever its class and its difference at the retry's (`CRITERIA.md` §7).
- **Why the first triple is not changed.** A mixed entry there is owed the retry, and an honest one is unresolved by it. So the first triple's "inconclusive by order" costs one run and no verdict.
- **The named reasons of an inconclusive entry** are `order`, `power` (a home entry not tested, whose 2 U_c is not the larger part of β or whose retry did not make it tested), `not formed` (a missing or doubled row or leaf, a departing echo, a run in `missing`, a refused file) and `refused`. A consumer's are those of its entries, and `support` and `plant` (a refused, missing or stopped support run, and an unscorable plant). The record gives one for every inconclusive entry.

### 13.1 The band that judges size, the plants and the power at the retry's

**An owed entry's size is judged by the retry's β:** its U_c, its e_round and e_store at S_c = 12,800, with the same U_l, e_round(S_l) and closure. It is the band of the pass that is reported, since the retry's triple is what the entry is judged on. **It is not always the smaller.** U_c falls with the step, and the rounding count grows with the number of steps: at U_c = 0 the retry's β is 1.09 times the first triple's in an entry that reads no amount and has the closure share, less in one with a closure of its own, and up to twice it where e_store is the larger part.
- **At each entry it names, a plant is scored with the band, and the Y*, that the entry is judged on: the retry's where it is owed, the first triple's where it is not.** An engine plant's own run stays the one at h₃. A plant that names an owed entry waits for the retry. A plant none of whose named entries is owed is scored with the first triple's.
- **Stage 1 is repeated on the retry tables** (`CRITERIA.md` §4.5). The judge forms the retry's β of every owed entry, and whether it is tested, writes `power_retry.json`, and the lead records its sha256 **before any difference of a retry table is formed.** An owed home entry is tested, or not, by that. **`power_retry.json` stands in the judge's record beside `power.json`, and `retry_owed.json` holds `part` 2** (`TABLE.md` §6 prints 1).
- **The margins stand at both bands** (§7.4).

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
| JQ10 | the same number moved by 10⁻¹³ of itself, and another run's pump with potentials that make A = 3,000 and the number moved by 2 × 10⁻¹² of itself | neither refused |
| JQ11 | `gated_calcium`, h₁: `calcium_controls` omitted, the zero permeabilities omitted, the maps in another order | not refused |
| JQ12 | `gated_calcium`, h₁: one schedule of `calcium_controls` [[0.0, 1.0], [0.01, 0.5]] | refused, and nothing of the run judged |
| JQ13 | `spatial_calcium`, all rungs: an invented error of first order on `store_Ca`, d₁ and d₂ above θ | inconclusive by `order`, and named in `retry_owed.json` |
| JQ14 | `spatial_calcium`, all rungs: an invented error of second order on `store_Ca`, d₁ and d₂ above θ | resolved in its window, and a pass |
| JQ15 | the same, with d₂ above θ and d₁ below it | mixed, inconclusive by `order`, and named in `retry_owed.json` |
| JQ16 | JQ15 with its retry run honest (the error four times smaller) | unresolved at the retry's triple, and a pass, `order not shown` |
| JQ17 | an entry outside its window at the first triple, and at the retry's d₂ = 20 e and d₁ = 5 e, inside β | mixed, its order not excluded, and a pass, `order not shown` |
| JQ18 | the same, with d₂ = 16 e and d₁ = 9 e | mixed, its order excluded, and inconclusive by `order` |
| JQ19 | an entry that passed at the first triple, `leak_K` of the retry run alone × 1.01 | it keeps its pass |
| JQ20 | `cluster_spatial_calcium s0 w0`, all rungs: `channel_K` × 1.01, the rest honest | the cluster fails by set A, and the record shows that set B passes |
| JQ21 | `cluster_gated_calcium plant swapped`: its `pool_seeds` exchanged | EP4 unscorable |
| JQ22 | `ip3_calcium h=1.25e-05 restart` missing | `ip3_calcium` at best inconclusive, reason `support` |
| JQ23 | `gated_calcium`, h₁: `declared_strings` without the exchanger's string | refused, and nothing of the run judged |
| JQ24 | `cluster_ip3_calcium s1 pool`: `strings` with one label of the ionic definition | refused, and nothing of the run judged |
| JQ25 | `spatial_calcium`, h₂: its class S rows replaced by the captured rows of `spatial_calcium-h2` | refused by the copy guard (b), its readouts judged |
| JQ26 | `plasma_calcium`, h₁: potentials that make A = 4,000 in one pump, the number exact | refused (A above its cap), and nothing of the run judged |
| JQ27 | the retry run of a family that holds an owed entry: one `store_Na` at the last time set to 5 × 10⁻³²⁴ | a fail of class E of that run |
| JQ28 | a retry run that is not owed, with `leak_K` × 1.01 | recorded, flagged and not judged |
| JQ29 | an owed entry, an invented first-order error with d₂ = 26 e and d₁ = 13 e at the retry's | resolved outside its window, and inconclusive by `order` |
| JQ30 | the same, with d₂ = 16 e and d₁ = 8 e | mixed, its order not excluded, and a pass, `order not shown`: §13's limit |
| JQ31 | SC1 where `store_release` is owed and `store_Ca` is not, with the retry table honest | scored with the retry's β and Y* at `store_release` and with the first triple's at `store_Ca`, after `power_retry.json` |
| JQ32 | `spatial_calcium`, h₁: `definition.species_rows` with one row more | refused, and nothing of the run judged |
| JQ33 | `spatial_calcium`, h₁: `definition.entities.passive_routes` 8 | refused, and nothing of the run judged |
| JQ34 | `spatial_calcium`, h₁: `definition.trace_mM` ten times as large, its nodes and rows the same | not refused |

**A judge's plant that the code scores otherwise stops the judge's tag.** The sizes that the plants rest on were formed from the captured arrays: each altered row moves by at least 1.6 × 10⁵ bands of §8 at U_c = 0 (JQ4 and JQ7, at 1.7 × 10⁵, are the least of those), but two: the store leak's heat (JQ5, 3.9 × 10³) and the 1 % of `channel_K` (JQ20, 1.9 × 10³: in that world the channel moves nothing after 2.5 ms). The IP3 reaction's heat (JQ6) is 2.5 × 10⁵ bands of `heat_reactions_cytosol`.

## 15. The rehearsal set of Part 2

`SPEC.md` §8 and `CRITERIA.md` §10 hold. Part 2 has its own rehearsal, before its registration, in the same folders: `inputs_rehearsal_part2.json` (with `inputs_part2.json`'s schema, `p`, `amount_refs`, `closure_share`, `closure_terms_V` and `closure_terms` in every world, formed by the rehearsal's runner by §8's rules from the invented blocks, and runs named `inv_<name>`), `legacy_rehearsal_part2.json`, `margins_rehearsal_part2.json` and `plants_manifest_rehearsal_part2.json`, with the makers and readers of `SPEC.md` §8. **No value of this part's captured worlds is used.** It holds, at least:
- one cell with one store, and a two-cell cluster with a store each, free field offsets, a gated junction that carries Ca (§3, condition 8) and Ca on its faces;
- one world with the plasma pump and the exchanger, one with the calcium channel, and one with IP3 and its Hill read;
- a two-pool cluster on one of these, with at least one event in each path, so that a step splits;
- **one family whose order is resolved in its window, one whose entries straddle θ at the first triple** (so that the mixed class, the retry and §13's rule are run), **and one at rounding;**
- one world whose fuel potentials are large against their difference (A between 2,500 and its cap), for §2.4's second term;
- the retry run of every one of its families, unread until its `retry_owed.json` is hashed, so that §13's order of reading is run;
- **one world whose amounts are as large against s as the registered ones:** `amount_refs`/`scales` at least 1.7 × 10⁴ for a cytosol's row, 4.4 for a store's, 22 for `n_out_x`, 7.7 × 10³ for `voltage` and 4.8 for `store_voltage` (the largest of `inputs_part2.json`). Its honest run must pass every entry;
- one restart, one refusal of each kind, one run stopped by the engine's own check, one engine plant of each kind (EP3's and EP4's), and the faulty tables of JQ1 to JQ34 that a table can carry.

**The noise of the solves is looked at there:** in the honest runs, the step-halving differences of the entries at rounding, against 2 e (§13). One above it says that the closure is real, and θ is then corrected by `CRITERIA.md` §10's route, before the registration tag.

## 16. Where Part 2 differs from Part 1, and why

| What | Part 1 | Part 2 | Why |
| --- | --- | --- | --- |
| Integrator and order | RK4, p = 4 | IMEX with Strang halves, p = 2 for every S entry | The candidate is the composite (ruling 5) |
| e_close | 4 × 10⁻¹² s, `phi_out` its own | 10⁻¹⁰ s, and their own in the three potentials and in the entries that a drifted voltage reaches above it | The IMEX stage's charge tolerance, every path of a potential error, and the drift that the voltages' closures admit (§8) |
| θ | 10 × (e_round + e_store), without the closure | the same | §13 says what follows, since the closure is larger here |
| `amount_refs` | the declared amounts | 7/5 of them in a row that a reaction touches | Two more additions a step (§8) |
| Balances, capacitors, energy | judged (R and S) | reported | The integrator (§9) |
| A reaction's heat | none | per compartment, the captured ones summed by the judge | The engine books a node's reactions together (ruling 1) |
| `heat_junction` | one row | the junction's own and Ca's route, summed | Ca's junction route is a passive route, and legacy sums the four ions |
| What a definition holds beyond its block | an extra entity is a departing echo (Amendment 2, item 2), and another key that the block has not is recorded | listed exactly in §2.5, and anything else is a departing echo | The engine needs a positive amount of every row at every node, and the kinds' declarations (§2.5) |
| Cells' fixed charges | compared | recorded | The captured ones do not count the buffer's rows (§2.2) |
| The pumps' free energy | declared, compared | formed by the exporter, compared with a rounding term | The cycle law declares none (ruling 2) |
| The retry's runs | made when owed | made in the registered batch, unread until `retry_owed.json` is hashed | An honest order-2 run can leave entries mixed at the first triple (§13) |
| The band and the power of an owed entry, and a plant's score at it | (the new triple's, by `CRITERIA.md` §7) | the retry's, with `power_retry.json` hashed before any difference | §13.1 |
| A formed number's tolerance | none | a rounding term with a cap | §2.4 |
| A mixed entry at the retry's triple | inconclusive | judged by §13 | Part 2's entries may be resolved, and a finer step brings them to rounding (ruling 10) |
| A home with several plants | none | the best of them (§7.1) | The lead's ruling of 25 November |
| The clusters' ratios | their own plants | their child's, halved | No cluster was run with a power plant (§7.1) |
| A mechanism not tested | none | the store's capacitor in the clusters (§7.4) | The lead's ruling of 25 November |
| Two sets | 2 families and 30 of `base` | seed index 0 and the others, of each cluster | Whole seed indices, since a cluster's pool run holds both of its worlds (§5) |
| Pool restarts | `cell` and `base` | none | The pools are `base`'s |
| Potentials | two kinds | three (`store_voltage`) | The store's capacitor |
| What the exporter's builder receives | `TABLE.md`, `READOUTS.md`, `SPEC.md`, `inputs.json`, Amendment 1, and Amendment 2's part for it | those, and `PART2_EXPORTER.md`, `PART2_BLOCKS.md`, `inputs_part2.json` | The plants of Part 2 are in `PART2.md` |

Everything else of `CRITERIA.md`, `TABLE.md` and Amendment 1 is as in Part 1.

### 16.1 What of Amendment 2 holds here

| Its item | In Part 2 |
| --- | --- |
| 1, JP14's rung | It is Part 1's plant. The one restart here is compared with `ip3_calcium` at h₁, which JQ6 alters with its other rungs. So the restart's E entry of `heat_reactions_cytosol` fails there besides |
| 2, an extra entity | **Does not hold.** §2.4 and §2.5 govern |
| 3, a retry run's class E entries | Holds, and §13 says the same |
| 4, a file that is not the contract's | Holds |
| 5, the readings that the lead confirmed | Hold where they apply: (a) at the first triple, and at the retry's §13 governs; (b) to (e), with EP4 as EP2, and with §13.1 for the band and the Y*; (f) for §12's reference, and for the outputs of the scalar references that `plants_manifest_part2.json` names, which lie outside the planted folder too |
| 6, the rehearsal's profile | Holds for Part 2's rehearsal (§15) |
| 7, the builder's clarifications | Hold where they apply. There is no pool restart (§11), so (e) has no use |
| 8, a stop's second pass, empty keys, a membrane without a pump | Hold where they apply. Every plasma membrane has its Na/K pump, so (d) has no use |
| 9, the judge's readings | Hold where they apply, and where this file says otherwise it governs: for 12 and 30 (the balances, the capacitors and the energy are reported, §9), 28 (the retry, §13 and §13.1) and 29 (the two sets, §5.1). In 9.1 a cluster's channels are its ionic block's (`channel_0` and `channel_1`), and no calcium channel. 9.4 is about Part 1's printed numbers. 9.5 holds for the tables of §14 |
| 10, what holds in Part 1 alone | It points here |

## 17. What a pass of Part 2 cannot show

Besides the protocol's §9:
1. **The order of an entry that is unresolved, or mixed and passed at the retry's.** The record says `order not shown`, entry by entry. **A first-order error is not excluded there where its difference between 6.25 and 3.125 µs is at most 2 θ + 4 e = 24 e** (§13; 5.5 × 10⁻¹⁰ of the gross throughput in an entry that reads no amount).
2. **The heat of a single reaction,** and how a lumped heat divides (a membrane's, the junction's, the store's leak).
3. **Any single fuel potential,** or how the release's factor is declared. Only the factor's effect and the combination are compared.
4. **The store's capacitor in the clusters,** and any claim of it there.
5. **The clusters' trajectories.** One end state and five summaries are captured.
6. **The balances, the moieties, the capacitors and the energy,** which are reported. The engine's own ledgers, with their looser energy allowance, are the criterion.
7. **The fixed charges of cells and stores,** which the engine's own anchor rule holds.
8. **What holds the fuel rows** (`cycle_supplied_fmol`), the condition's observed factor, and the reactions' standard terms.
9. **A blind test of the pools of seed index 0.**
10. **That Ca's junction route takes the gate as the captured one does,** beyond what `junction_Ca` and `exchange_Ca` show, and the live kind's code says (§3, condition 8).
11. **The integrator.** A run on another scheme of order 3 or 4 passes wherever it agrees: its order lies in the window [1.5, 4.5]. The strings declare the scheme, and the record and the checker confirm what was declared.
12. **A factor held through a step, where its error is that small.** A held factor is a first-order error: where it is resolved it shows as order 1, so the entry is inconclusive, and it is settled as a changed model (§3, condition 3). Below item 1's bound it is not seen.
13. **Anything below a band:** at U_c = 0 about 1.2 × 10⁻¹⁰ of the gross throughput, more in an entry with a closure of its own (the most in `extent_bind_0_second` and `cyt_Ca2B` of `ip3_calcium`, 1.2 × 10⁻⁸, and 2 to 3 × 10⁻⁹ in `heat_store_pump`, `store_pump`, `heat_ca_channel` and `ca_channel`), more in one that reads an amount (the most in `cyt_Cl`, 6.2 × 10⁻⁸), and in general the candidate's own error estimate.

## 18. For Part 2's independent auditor: what to look at first

The auditor reads this folder alone, and the captured arrays and planted runs that `README.md` lists. It comes before Part 2's tag, and it asks its questions through the lead.
1. **§13 and §13.1:** the retry's rule, its arithmetic and its limit, the runs made up front, the band that scores a plant, against `CRITERIA.md` §4.3, §4.5 and §7.
2. **§8:** the closure's paths, its two passes and the entries' own numbers (`closure_terms`), the rounding count for the IMEX step with its reaction halves, `amount_refs` and the 7/5.
3. **§6:** the names, the signs and the sums. Check the signs against the arrays, and the lumps (`heat_junction`, `heat_store_leak`, `heat_membrane`, `exchange_x`, the reactions' heats per compartment) against the captured code's numbers.
4. **§2.2, §2.4 and §2.5:** the one-molar number, its three potentials, its tolerance and its cap; what a definition holds beyond its block, and what a trace touches.
5. **§3, condition 8:** what a Ca junction route without the gate would do, and where it would be seen.
6. **§5:** the two sets of a cluster, and what each owns.
7. **§7 and `margins_part2.json`:** the homes, the two replaced ones, the halved ratios, the margins under §8's bands, SC11's move and SC14.
8. **§10 and §11:** the counts, the runs, the engine plants' registered distances.
9. **`PART2_BLOCKS.md` and `inputs_part2.json`** against the captured definitions, and the defaults.
10. **§14 and §16:** a plant whose "must be" a correct judge would not give, and a difference from Part 1 that §16 does not list.

**Try to find:** an entry that an honest order-2 run would miss or leave inconclusive without a named reason; a pass with nothing judged; a sum whose parts a wrong sign would cancel; a number here that differs between two files.
