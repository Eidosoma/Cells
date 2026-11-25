# Part 2: the four calcium clusters, and the four assembly-regulated ones

`CRITERIA.md`, `TABLE.md` and the rules of `README.md` hold here. This file states what they need beyond Part 1, as far as the re-expression map and the lead's
ruling of 25 November 2026 fix it. `inputs_part2.json` governs the numbers.

**Part 2 cannot be tagged yet.** What waits is in §0, by name.

## 0. What is fixed, and what waits

**Fixed (the lead, 25 November 2026), and all of it keeps the ensemble's equations:**
- the calcium channels stay channel populations of the inner model, whose law declares its ions' valences;
- both calcium pumps (the store's and the plasma one) are one cycle law on the transporter kind;
- the store is a compartment with its own capacitor in a closed world;
- the exchanger is one monomial law module;
- the buffers are today's mass action, as local reactions;
- the release is a passive route with a factor source that is read at each stage;
- the assembly sets the K channel's availability.

**The two design notes being written now:** the note on calcium channels, the store and the exchanger (**note D**), and the note on the release factors and assembly availability (**note E**).

| Item | Waits on | What its answer changes here |
| --- | --- | --- |
| Every readout's declared order, the heats' above all (a heat that a kind books is a quadrature of its own order) | notes D and E | §4.2. A readout that a note declares at another order takes `CRITERIA.md` §4.3's window with its own p |
| The step ladder: whether the composite admits 12.5 µs, and where its order is in its window | notes D and E, their prototypes on **invented** worlds | §4.1's ladder, only before the Part 2 tag |
| The ledger and field names that the exporter reads for the store, its pump, the release, the exchanger and the reactions, and how a compartment's amounts are booked | note D | §6's canonical column, by name. The signs and the lumps are fixed here |
| The factor source's form, and whether its inputs are the cytosol's free amounts over its volume at the stage | note E | §3's condition 3 |
| The assembly form: schedule (`SPEC.md` §3.2) or operator. An operator's event times must be the pool's doubles | note E | §4.1 and the runs' `strings` |
| The strings note's labels for the pieces that do not exist yet | notes D and E | §4.3 |
| Restarts and engine plants | the build | §11 |

**What does not wait:** the captured worlds, values, scales, arrays, signs and lumps; the classes; the plants, their homes and their margins from the legacy side; the references' own classes.

## 1. The consumers, and their equations

| Consumer | Captured world | Canonical form | Equations | Integrator, declared order |
| --- | --- | --- | --- | --- |
| `spatial_calcium` | the buffered store over the JUPITER cluster with Ca | the composite over the inner model: one compartment per cell with its capacitor, Ca's plasma leak, junction route and store leak as passive routes, K's store leak, the release with its factor, the store's pump, the buffers as local reactions | **same** (§3) | IMEX, Strang halves, order 2 |
| `plasma_calcium` | + a plasma calcium pump and the exchanger | + the cycle law and the exchanger law | same | IMEX, order 2 |
| `gated_calcium` | + a Cav1.2-type channel | + a channel population that carries Ca²⁺ | same | IMEX, order 2 |
| `ip3_calcium` | + free IP3 with its buffer, and the IP3 factor on the release | + the factor source | same | IMEX, order 2 |
| `cluster_spatial_calcium` | the first with two assembly pools a world, 2 worlds a seed | the first with a pool per cell, whose availability multiplies the K channel | same | IMEX, order 2, with the pool exact |
| `cluster_plasma_calcium`, `cluster_gated_calcium`, `cluster_ip3_calcium` | the others the same way | the others the same way | same | the same |

**The availability multiplies the K channel alone.** It never touches the calcium channel, the pumps, the exchanger or the release.

## 2. What a canonical definition must hold, by name and value

Each world's block in `inputs_part2.json` is the captured definition's content in canonical terms, as Part 1's §2. Besides Part 1's keys, with Ca (valence +2) as a fourth species:

| In the block | What it is |
| --- | --- |
| `stores.<cell>.species` | The species of the cell's chemistry: Ca, B (−2), CaB (0), Ca2B (+2), K, Na, Cl, and in `ip3_calcium` IP3 (−3), IP3_buffer (0), IP3_bound (−3), each with its standard potential over RT at the network's standard concentration, 1 mM |
| `stores.<cell>.compartments` | `cytosol` and `er`: volume and initial amounts. The cytosol's are the cell's |
| `stores.<cell>.reactions` | For each reaction: its compartment, its reactants and products, its forward rate. The reverse rate is the forward one times exp(Σ products' − Σ reactants' standard potentials), per c₀ |
| `stores.<cell>.membrane` | Area, capacitance (area × specific capacitance), initial voltage 0 V, the leak permeabilities (Ca and K alone are non-zero), the pump and the release |
| `stores.<cell>.membrane.pump` | Capacity, the two constants, the fuel, and the standard free energy **at a 1 M standard state** |
| `stores.<cell>.membrane.release` | The permeability and the four constants of its calcium factor |
| `plasma.<membrane>` | The calcium pump (its 1 M standard free energy) and the exchanger (3 Na in, 1 Ca out) |
| `calcium_channels` | Per channel: membrane, maximal permeability, abundance, initial gates. Law label `cav12_m2h` |
| `ip3_release` | Per cell: the species, the activation constant and the power of the factor |

### 2.1 Derived declarations, by rule

- **The 1 M standard free energy** of a pump = its captured numeric-mM one + R T_K ln 1000 (`delta_g0_at_1M_J_per_mol`, −19,875.97 J/mol at 298.15 K). The echo
  compares it, and not the captured one, at 10⁻¹² relative. The captured number is kept beside it.
- **Capacitances** are area × specific capacitance, as in Part 1.
- **Charges:** the cell's node charge is C_m V₀ (its store's voltage is 0 at time 0), and the store's is 0. **Fixed charges** are derived from those and the initial amounts of **every** row of the node, B, CaB, Ca2B and IP3 with it, by the model's
  own anchor rule. They are recorded, and the echo does not compare them, since the captured ones refer to Na, K, Cl and Ca alone.
- **The controls** of the captured definitions are all 1 at all times, and are declared as 1.

### 2.2 What has no counterpart

As Part 1 §2.3. The captured release, pump and passive multipliers are 1 throughout, so no schedule is needed.

## 3. When it is the same equations, and when it is a changed model

**It is "same equations" only if all of these hold** (the fixed forms keep them; the builders say so for each consumer, before the Part 2 tag):
1. **The world is closed:** one gauge (`local`), and no held bath.
2. **The store has its own voltage:** a free capacitive node between cytosol and store, with the captured area, specific capacitance and initial voltage.
3. **A release factor is read at each stage** from the cytosol's free amounts over the cytosol's volume (Ca always, and IP3 in `ip3_calcium`), and multiplies the permeability. A factor held through a step, or a two-state fraction, is a changed model.
4. **The pumps' standard state** is the one of §2.1.
5. **The exchanger's rate** is the captured symmetric-barrier law: 3 Na for 1 Ca, third powers in the sodium terms, a denominator of the captured product form, and no standard-state part.
6. **The reactions** are the same mass-action kernel: the same rate constants at 1 mM, the same standard potentials, the same stoichiometry.
7. **The Ca channel** carries Ca²⁺ by the constant-field law at valence 2 with P = P_max × abundance × availability × m² h, and the captured gate kinetics with their −10 mV shift and no temperature term.

**If any does not hold, the consumer is a changed model.** No band of this folder applies to it, and it is not judged here. It is judged by the consumer's own registered criterion
(the calcium ensemble's independent reference at 3 × 10⁻⁹ relative and 3 × 10⁻¹² absolute, §12) or by a reference written for it, in a **new registration** that the user approves. The Part 2 tag records which consumers are which, before any run.

## 4. What a candidate declares

### 4.1 Steps

| Item | Value |
| --- | --- |
| Model | The composite over the inner tissue model, version 3, with the notes' operators and kinds |
| Integrator | `ars222` (IMEX, order 2), with Strang halves for the composite's splits. **Declared order 2 for every S entry** (§4.2) |
| Steps | h₁, h₂, h₃ = 12.5, 6.25, 3.125 µs. Retry 1.5625 µs. The captured h, h/2, h/4 are the same 12.5, 6.25 and 3.125 µs |
| Gauge | `local`, 0 V, closed |
| Observations | On the grid, at the block's `potential_times_s` at least |
| Assembly clusters | The live pool's seeds and world IDs (worlds 0 and 1 of each of four seeds), the event path as the channel's schedule (`SPEC.md` §3.2) or as note E's operator, with the event times as the pool's doubles |

### 4.2 The declared order

- **2** for every S entry, heats included, unless a note declares otherwise for a named readout before the Part 2 tag. The gates are advanced by the exponential update at the stage voltages, order 2. A readout of a different declared order takes `CRITERIA.md` §4.3's window with its own p.
- **The legacy side is 4** and unresolved for every entry (`legacy_part2.json`).
- **What the candidate's truncation may look like, so that nobody is surprised by it:** the store's K leak relaxes its voltage at about 5,260 s⁻¹, so dt × rate is 0.066 at 12.5 µs and 0.016 at 3.125 µs. Fast entries of the store may not be in their
  asymptotic range at 12.5 µs. The retry's triple starts at 6.25 µs. Order is judged; a truth that is out of range is inconclusive, and no window is widened for it.

### 4.3 Strings labels added to the note

`composite_model`, `imex`, `passive_routes_kind`, `local_reactions`, `mass_action_passive`, `store_node`, `calcium_pump_positive`, `exchanger_3na_1ca`, `cav12_m2h`, `store_calcium_release`, `ip3_release_factor`, `calcium_release_factor`, and note E's operator's. `delta_g0_at_1M_J_per_mol` carries no ID.

## 5. Compared times and worlds

- **The ionic children:** every 12.5 µs from 0 to 1 ms (81 rows), then every 100 µs from 1.1 to 20 ms (190 rows), 271 rows (`history_times`). The rows up to 1 ms resolve the store's fast modes.
- **The assembly-regulated clusters:** 0.02 s for every entry, and 2.5, 5, 10 and 15 ms and 20 ms for `voltage`, `channel_K`, `store_voltage` and the four free cytosolic ions, where the summaries exist (`summary_times_s`).
- **World IDs 0 and 1** of each of four seeds (`cluster_*`). Their pools are worlds 0 and 1 of `base`, bit for bit.

## 6. The readouts

**The signs that the map names, settled.** Part 1's orientations hold (READOUTS §1). For the store:
- **Into the store is positive** for `store_leak_x`, `store_pump` and `store_release`. The captured `er_passive_transferred`, `er_pump_transferred` and `er_release_transferred` are oriented the same way. So `store_release` is **negative** while calcium leaves the store. A canonical bounding patch has the cell inside and the store outside, so its outward flow is into the store, the same sign.
- **`store_voltage` is the store's potential less the cytosol's.** The captured `er_voltage_V` is this. The canonical boundary voltage V_b is the owner's potential less the store's, so **`store_voltage` = −V_b**.
- **`exchange_x` is a whole-cell ledger** (the sum of what crossed the plasma membrane and the junction), and legacy calls it `amount_increment`. **It is not the free cytosol.** The free cytosol and the store come from
  `chemical_amount_increment`'s compartment slots 0 and 1 (slot 2 is padding), or, for the cytosol, the rows of the canonical cell.

**The chemical species axis is in the IDs' sorted order, and not the definition's.** It is `B, Ca, Ca2B, CaB, Cl, K, Na` (`B, Ca, Ca2B, CaB, Cl, IP3, IP3_bound, IP3_buffer, K, Na` in `ip3_calcium`). The reaction axis is sorted too: `bind_0_first`, `bind_0_second`, `bind_1_first`, `bind_1_second`, `ip3_binding`. The ionic species axis is (Na, K, Cl, Ca), the definition's.

| Name | Unit | Entities | Canonical source | Captured source |
| --- | --- | --- | --- | --- |
| Part 1's series, with `leak_Ca`, `junction_Ca`, `face_Ca` and `n_out_Ca` | | | As READOUTS §2. Ca's leak and junction routes: the passive kind's transfers, converted to READOUTS' orientation | As READOUTS §2 |
| `exchange_x` (4) | fmol | cells | Formed by the judge from the run's own transfers: what the plasma routes, pumps, exchanger, channels and junctions brought in | `amount_increment[x, cell]` |
| `cyt_c` | fmol | cells | the cell's row of `c` (increment) | `chemical_amount_increment[store, c, 0]` |
| `store_c` | fmol | cells | the store node's row of `c` (increment) | `chemical_amount_increment[store, c, 1]`. Na and Cl in the store, and every IP3 species there, do not move: zero (class E) |
| `store_leak_Ca`, `store_leak_K` | fmol | cells | Ca: the passive route's transfer, outward of the bounding patch (into the store); K: the inner model's own constant-field transfer there | `er_passive_transferred[store, c]` |
| `store_pump` | fmol of cycles | cells | the transporter kind's cycle law at the bounding patch: cycles, one Ca into the store in each | `er_pump_transferred[store, 0]` |
| `store_release` | fmol | cells | the release route's transfer, into the store | `er_release_transferred[store, 0]` |
| `heat_store_leak`, `heat_store_pump`, `heat_store_release` | pJ | cells | leak: **the sum over Ca and K of the two routes** (legacy lumps the species); pump and release alone | `er_transport_dissipated_energy_pJ[store, 0..2]` |
| `extent_r`, `heat_r` | fmol, pJ | cells | the reaction's own ledgers | `reaction_extent[store, r]`, `reaction_dissipated_energy_pJ[store, r]` |
| `store_voltage` | V | cells | **−V_b**, at the potential times | `observations.er_voltage_V[cell]` (`cluster_*`: the summary's `calcium.er_voltage_V`) |
| `ca_pump`, `heat_ca_pump` | fmol of cycles, pJ | membranes | the same cycle law at the plasma patch: cycles, one Ca out of the cell in each, and its heat | `plasma_pump_cycles`, `plasma_dissipated_energy_pJ[0]` |
| `exchanger`, `heat_exchanger` | fmol of cycles, pJ | membranes | the exchanger law's cycles (3 Na in, 1 Ca out each), its heat | `plasma_exchange_cycles`, `plasma_dissipated_energy_pJ[1]` |
| `ca_channel`, `heat_ca_channel` | fmol, pJ | membranes | the Ca channel population's transfer, **minus** the inner model's outward one, and its heat | `calcium_channel_transferred` (inward), `calcium_channel_dissipated_energy_pJ` |
| `ca_gate_m`, `ca_gate_h` | 1 | membranes | the gates | `calcium_gate[0]`, `calcium_gate[1]` |

- **`heat_membrane` lumps more here.** Legacy's `dissipated_energy_pJ[membrane]` is the leak of Na, K, Cl and **Ca**, the Na/K pump and the Kv1.5-type channel. The canonical sum is `heat_leak` (the patch's own), the Ca leak route's heat, `heat_pump` and `heat_channel`.
- **Which are E.** `store_Na`, `store_Cl` and the store's IP3 rows are zero at every time in every captured run. `ca_*` and `ip3_*` series exist only in the worlds that hold the mechanism.

## 7. Mechanisms, homes and plants

### 7.1 Mechanisms and homes (besides Part 1's)

| Mechanism | Home | Consumers |
| --- | --- | --- |
| Plasma Ca leak | `leak_Ca` | all eight |
| Ca junction route | `junction_Ca` | all eight |
| Ca faces | `face_Ca` | all eight |
| Store Ca leak | `store_leak_Ca` | all eight |
| Store K leak | `store_leak_K` | all eight, **if observable** (below) |
| Store pump | `store_pump` | all eight |
| Release permeability | `store_release` | all eight |
| Release's calcium factor | `store_release` | all eight |
| Cytosolic buffers | `extent_bind_0_first`, `extent_bind_0_second` | all eight |
| Store buffers | `extent_bind_1_first`, `extent_bind_1_second` | all eight |
| Store capacitor | `store_voltage` | all eight |
| Plasma calcium pump | `ca_pump` | plasma, gated, ip3, and their clusters |
| Exchanger | `exchanger` | plasma, gated, ip3, and their clusters |
| Ca channel permeability | `ca_channel` | gated, ip3, and their clusters |
| Ca channel kinetics | `ca_gate_m`, `ca_gate_h` | gated, ip3, and their clusters |
| IP3 factor | `store_release` | ip3 and its cluster |
| IP3 binding | `extent_ip3_binding` | ip3 and its cluster |

- **Part 1's mechanisms** (leak of Na, K, Cl, K channel, its kinetics, the pump, the junction, its gate, the faces, the closure) are in every one of the eight. Their homes are Part 1's, and the ratio is Part 1's `jupiter_baseline` ratio halved, a declared lower bound, for the ionic part that Part 2 shares with it.
- **A mechanism whose plant has no effect above its band** is declared not observable in §7.4, and is not a home.

### 7.2 Power plants, Part 2 (each a legacy run of the captured definition with one constant × 1.01, at the captured 12.5 µs step)

`PC-leakCa` (plasma Ca leak permeability), `PC-junctionCa`, `PC-faceCa`, `PC-storeleakCa`, `PC-storeleakK`, `PC-storepump` (capacity), `PC-release` (permeability), `PC-activation`, `PC-inhibition` (the two factor constants), `PC-bind0a`, `PC-bind0b`, `PC-bind1a`,
`PC-bind1b` (the four forward rates), `PC-storecap` (store specific capacitance, its initial voltage 0), `PC-pmca` (capacity), `PC-ncx` (capacity), `PC-ncxkm` (Na constant), `PC-cav` (maximal permeability), `PC-cavkinetics` (both time constants, patch), `PC-ip3activation`, `PC-ip3binding` (forward rate). Each in every consumer that holds it.

### 7.3 Structural plants, Part 2

| Plant | World | Change | Named entries |
| --- | --- | --- | --- |
| SC1 | spatial | The release's calcium factor left out (it is 1) | `store_release`, `store_Ca` |
| SC2 | ip3 | The IP3 factor left out (it is 1) | `store_release` |
| SC3 | spatial | The store voltage's sign reversed in its leak, release and pump | `store_leak_K`, `store_voltage` (the run may leave its domain: that is a catch, §7.4) |
| SC4 | spatial | The store pump's direction reversed | `store_pump`, `store_Ca` |
| SC5 | spatial | Ca's valence taken as 1 in the store's leak and release | `store_leak_Ca`, `store_release` |
| SC6 | spatial | The first buffer binds two calcium (2 Ca + B = CaB) | `extent_bind_0_first`, `cyt_Ca` |
| SC7 | plasma | The exchanger's sodium terms squared and not cubed, with 3 Na moved | `exchanger` |
| SC8 | plasma | The plasma calcium pump's direction reversed | `ca_pump`, `cyt_Ca` |
| SC9 | gated | The channel's inactivation gate left out | `ca_channel` |
| SC10 | gated | The channel's m² taken as m | `ca_channel` |
| SC11 | cluster_gated_calcium | The pool's availability acts on the calcium channel as well as the K channel | `ca_channel` |
| SC12 | plasma | The pump's standard free energy left at the numeric-mM one under the 1 M quotient | `heat_ca_pump` |

### 7.4 Observability

Filled with the margins (`PLANTS.md` §8): for every mechanism above, whether its 1 % plant moves its home above the band at U_c = 0, and, where it does not, that it is **not tested** and no home.

## 8. Scales

`inputs_part2.json` `scales`. Part 1's rule, with these additions, each the gross throughput over 20 ms that the readout is formed from:
- `leak_Ca`, `junction_Ca`, `face_Ca`, `n_out_Ca` as Part 1's with z = 2.
- `store_leak_x` = P_x A/10⁻¹⁵ × c* × χ × T, c* the larger of the cytosol's and the store's initial concentrations; `store_pump` = capacity × T; `store_release` = P A/10⁻¹⁵ × c*_Ca × χ(2) × T, with the factors taken as 1.
- `extent_r` = the larger of the forward and reverse initial rates at the **total** amounts that the moieties allow, times T.
- `heat_r`, `heat_store_*` and the Ca heats: their transfer's scale times the RT and potential terms, as Part 1's heats.
- `cyt_c`, `store_c`, `exchange_x`: the sum of the scales of the routes and reactions that move them.
- `store_voltage` = max |V₀| + (F 10⁻¹⁵/C) Σ_c |z_c| × the store row's scale, with C the store's capacitance. `voltage` as Part 1's with the calcium routes.
- `ca_pump` = capacity × T, `exchanger` = capacity × T × exp(F V*/2 R T_K), `ca_channel` as `channel_K` with z = 2. Gates are 1.

## 9. Conservation and the reported identities

**Conservation is the engine's own rule at every accepted step** (`CRITERIA.md` §4.4). No identity below is judged. The judge forms and reports them:
- the balances of each cell, region, store row and cytosol row, and the closed world;
- **the moieties** in each compartment: B + CaB + Ca2B (cytosol and store apart), IP3 + IP3_bound and IP3_buffer + IP3_bound (cytosol), and calcium's total: cytosol (Ca + CaB + 2 Ca2B) + store (the same) = `exchange_Ca`;
- **the capacitors:** `voltage` − V₀ = (F 10⁻¹⁵/C_m) Σ_x z_x `exchange_x`, and `store_voltage` = (F 10⁻¹⁵/C_s) Σ_c z_c `store_c`;
- **the energy:** every chemical row of cytosol and store (d (μ°_RT + ln(n₀/(V c₀)) − 1) + (n₀ + d) ln(1 + d/n₀)), both capacitors, the heats and the works.

**In Part 2 the engine's own energy allowance is looser than the comparison's.** The declared rule allows 2 × 10⁻³ of the integrated flows on the IMEX integrator. So the heats are judged against the captures, readout by readout, and not by the identity.

## 10. Judged sets

`legacy_part2.json` lists the entries: 58 for `spatial_calcium`, 62 for `plasma_calcium`, 66 for `gated_calcium`, 71 for `ip3_calcium` (S, over the compared times, with the three potentials), and 62, 66, 70 and 75 per family for the four clusters, of which those at the summary times are named `<name>_summary`. The E entries are the pool's, the structural zeros and the restarts.

## 11. The runs

`inputs_part2.json` lists 124: 12 for the four ionic children, 112 for the clusters (4 pool runs and 8 × 3 ionic runs each). Restarts and engine plants are added at the Part 2 tag, as Part 1's are: a restart at 0.01 s and an engine plant on the release permeability for `ip3_calcium`, and the swapped schedule for `cluster_gated_calcium`.

## 12. The independent reference

**What it is.** A scalar ODE reference of these worlds' equations, with its own code and no engine import: `validation/betse/spatial_cluster/reference.py` for the cluster (leak, pump, K channel, junction, faces and the Kirchhoff solve), and
the store, plasma-pump, channel and IP3 references of the live tests, with an adaptive integrator at a relative tolerance of 2 × 10⁻¹³. It stays through the deletion and moves under this folder later, before the Part 2 tag.

**What it is used for.**
- **Corroborating the reference side, before any run.** It is run on the captured definitions, and must agree with the captured h/4 rows at the compared times within its own registered criterion, 3 × 10⁻⁹ relative and 3 × 10⁻¹² absolute, readout by readout. A disagreement is a C0 fault of the
  references, found before a table is opened. The author's first run of it on the Part 1 cluster is in the protocol's §8.
- **Reporting beside a miss.** Where the candidate misses an S entry, the judge reports its distance to the independent reference too. It decides nothing by itself.
- **A changed model** (§3), if one is found, has it as its registered criterion, at 3 × 10⁻⁹ against the independent equations **as they are written there**, which must first be changed to the changed model's.

**What it covers.** The four ionic clusters and the JUPITER cluster, with a prescribed channel availability (so, the assembly clusters' ionic sides too, given their paths). Amounts, transfers, cycles, gates, potentials, reaction extents and heats.

**What it does not cover.** The assembly pools, their events and seeds. The energy balance as an integral law. Legacy's interpolants and domain proofs. It is written from the same model description, so it shares any reading of it. It is a check of the arithmetic and of the book-keeping, not of the physics.
