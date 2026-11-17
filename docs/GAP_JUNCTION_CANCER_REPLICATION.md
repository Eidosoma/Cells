# Gap-junction cancer replication

**Status: development work, not judged (D138).** First task of a new track, 17 November 2026.
The experiment is that of J. Grodstein, J. Mathews and M. Levin, "Membrane voltage and connexin
expression work together to enhance tumor growth and metastasis in cancer", bioRxiv
[10.64898/2026.09.02.748840](https://doi.org/10.64898/2026.09.02.748840), version 1, 3 September
2026, CC-BY 4.0 ("the preprint"). Its bioRxiv page lists no supplementary material.

**Sources of numbers.**
- The preprint's numbers are used with a citation (D186, D201).
- So are numbers from the authors' public code and logs (BITSEY, below). The user ruled on
  17 November 2026, as the lead relayed: numbers from BITSEY's code and logs may be used, each cited
  to the repository and revision; its code is never copied.

Each comparison below says whether its number is:
- **printed** in the preprint;
- **read** off one of its plots;
- **derived** from its equations;
- **fitted**;
- **from the code**.

**In short.**
- **The preprint's tissue simulations (Tables 1-3) are not replicated.** They need four engine
  features (§5): a charged microRNA on junctions (F2), a two-state connexin gate (F3),
  species-selective closed gates (F4) and junction docking rules (F5). The 3D table also needs a
  larger field (F7), and Table 3's neighbor-depol column a mechanism the preprint does not give
  (F8).
- **The preprint's linear model ("intuitive model": equations 1-2, appendix, Figures 3, 5 and 8)
  runs on the engine in two forms.**
  - **As written:** a source and a decay in each cell, plus a junction route. It runs through
    `local_species_reactions@1` and the passive-routes kind's neutral junction law. That law is
    not numerically qualified. A scratch probe converges to equation 2 at second order in dt (§4).
  - **As its exact Norton equivalent** on @3's own routes, which is the driver's committed form.
    It reproduces equation 2 and Figure 5 to 3e-14 or better, and computes straight chains' Norton
    conductance (§4).
- **Figure 8.** The appendix's printed recursion gives a chain's conductance growing without
  bound. The engine's solve of a straight chain gives one that saturates at 1.618 G_eq,1 (§4).
- **The engine's energy check sets the step** for neutral species on membranes and junctions,
  well below the stability bound. This is the known limit of the shared-inventory design's
  finding 3 (§4).

**Engine models run.**
- `resolved_pump_tissue@3`, with `constant_field@1` membranes and junctions for one neutral
  species, held reservoirs and `junction_voltage_relaxation@1` pinned open.
- The `resolved_capacitor_components_current_continuity@1` closure and
  `imex_ars222_face_electromigration@1`.
- Probes: `local_species_reactions@1` and `cells.passive_routes@1` in `resolved_pump_composite@1`.

Driver: [`validation/gap_junction_tissue/`](../validation/gap_junction_tissue/). Evidence:
`/mnt/workspaces/Cells/gap-junction-20261117/`.

## 1. The experiment, as the preprint specifies it

**Cells and network.**
- Identical cells on a lattice, every neighbouring pair joined by a homotypic Cx45 gap junction
  (Figure 1).
- Table 1: a 6x6x6 tumor in a 25x25x25 field. Table 2: tumors of 1x1 to 8x8. Table 3: tumor and
  field sizes not printed.
- Tumor cells start in the mesenchymal (M) state (ZEB high, miR200 low), healthy cells in the
  epithelial (E) state. Every junction starts at one base conductivity.

**Channels, pumps and junctions** (Methods).
- Goldman-Hodgkin-Katz ion channels and the thermodynamically driven Na/K-ATPase of BETSE (its
  refs. 35-36).
- Healthy cells near -70 mV. Tumor cells depolarized: about -30 mV in the Abstract, roughly -20 mV
  in the Results.
- Junction flux: Fick's law with drift (Nernst-Planck, Einstein mobility). G_GJ = k_D,GJ A_GJ,CS /
  L_GJ.
- Gating: G = Gmin + (Gmax - Gmin) / (1 + exp(-A1(-dV - V01)) + exp(-A2(dV - V02))) (its ref. 52,
  Chen-Izu et al. 2001). The closed fast gate passes small ions but blocks miRNA fully
  (Figure 1). Effective miRNA valence: -1.

**Regulation.** In every cell, the miR200/ZEB EMT switch (Figure 2; its refs. 49-50).
- Modified Hill rates (1 + lambda (TF/Km)^n) / (1 + (TF/Km)^n), and miR200-Zeb binding at fast
  equilibrium.
- Snail is chosen so that only E and M are stable. Only miR200 crosses junctions.

**Strategies and protocol.**
- Table 1 columns:
  - neither strategy;
  - tumor depolarized;
  - connexins underexpressed in tumor cells to 0.3, 0.5 or 0.8 of healthy;
  - both.
- Table 1 measure: the smallest junction diffusion constant at which the healthy tissue normalizes
  the tumor (M to E), by binary search.
- Table 2 repeats Table 1's "both" column for each tumor size.
- Table 3: tumor junctions at G0 P, border junctions at G0 (1 + P)/2. It reports the smallest P
  at which the tumor flips the whole surrounding field (invasion), for three strategies:
  - depol;
  - hypol (the tumor re-hyperpolarizes);
  - neighbor-depol (the tumor depolarizes nearby healthy cells).

**Readouts.**

| Item | Readout |
| --- | --- |
| Table 1 | Minimum normalizing diffusion constant per strategy and underexpression (1e-15 m²/s) |
| Table 2 | The same against tumor size (1e-14 m²/s) |
| Table 3 | Minimum GJ_power per strategy and G0 |
| Figure 1 | Cx45/45 conductance against dV, for small ions and for miRNA |
| Figures 3b, 5b | Steady [mR] of two linear cells against G_GJ |
| Figure 8 | The lines [mR] = mR_UL0 - i_exit/G_eq,n of chains of 1-5 cells |

**What the authors' code pins and the preprint does not print**
(BITSEY at [b2cb370](https://gitlab.com/grodstein/bitsey/-/tree/b2cb370aaecbc8299f259bc4251d5396c81f19a6),
the last revision before the preprint, by file):

| Item | Value | File |
| --- | --- | --- |
| Cell and junction geometry | radius 5 um, junction length 100 nm, specific capacitance 0.05 F/m², membrane 7.5 nm, 310 K | `sim.py` |
| Ions inside / outside (mol/m³) | Na 10/145, K 125/5, Cl 55/140, impermeant anion 80/10; membrane D 1e-18 m²/s each | `sim.py` |
| Pump | BETSE form, alpha 1e-7, Km Na 12, K 0.2, ATP 0.5; ATP/ADP/Pi 1.5/0.15/0.15; dG_ATP -37 kJ/mol | `sim.py`, `sim_toolbox.py` |
| Depolarization | K membrane D x (1 + 30 h/(1 + h)), h = (miR200/(0.001 + Zeb))^10: about -68 mV healthy, -15 mV tumor | `cancer_GJ_sims/zombie.py` |
| EMT switch | Snail 72 (bistable 46-78); scaled coordinates (/250, /30, /18000, /2500); binding on total miR200 | `cancer_GJ_sims/GRN_miRNA.py` |
| miRNA on junctions | drift valence -1, zero charge weight; only through open channels | `cancer_GJ_sims/GRN_miRNA.py` |
| Cx45 gate | A 110/V, V0 -10.2 mV (the preprint's sign convention), Gmin 0.06, Gmax 1.56; scales every ion | `GJ_lib.py` |
| Protocol | seeds 0/100/100 (tumor) and 100/0/0 (healthy); 500 time units uncoupled, then 20,000 coupled; tumor at the field's corner | `cancer_GJ_sims/zombie.py` |
| Normalized | every cell miR200 > Zeb mRNA + 2, and each row's Zeb spread at most 2; binary search to 0.1% | `cancer_GJ_sims/zombie.py`, `GRN_miRNA.py` |
| Expression | underexpression: per junction the minimum of its cells' factors; overexpression: 1 + tau (P - 1) with border tau 0.5 | `cancer_GJ_sims/zombie.py` |
| Table 3 setup | a 1x1x25 line, tumor of 11 cells, tumorness level 1; neighbor-depol depolarizes higher-numbered neighbours; hypol puts every cell at -15 mV | `cancer_GJ_sims/zombie.py` and its saved log |

**Where the preprint is ambiguous or inconsistent.**
1. **Units.** Tables 1-2 give a "general system diffusion constant" (m²/s); the text calls it
   G_GJ (m³/s). The conversion is not printed. The code uses G = D x the cell's whole surface area
   / junction length. Table 3 gives no unit for G0.
2. **Geometry.**
   - Table 1 is 3D by its text. Table 2's "NxN" sizes are 2D, and Table 3's lattice is not stated.
   - Table 2's 6x6 "both" entries are 1.7 to 1.8 times Table 1's for every underexpression (130
     against 75 at 0.5), so the two tables do not share one setup.
   - The tumor's position and the neighbour rule are not stated.
3. **Membrane voltage.** The tumor's voltage is -30 or -20 mV; its mechanism is not printed.
4. **Table 3.**
   - The text says neighbor-depol is "slightly more effective than simple hyperpolarization".
     Yet the table's Hypol column is the lower in four of five rows.
   - The text says G0 above 2.3e-14 is "not shown", but 2.3e-14 is a row.
   - The tumor size, the success criterion and the horizon are not printed.
5. **Figure 5.** The text says cell B is 1.5x cell A, the caption 1.33x. The drawn network (4 cells
   against 3) and the caption's 7.15 fit 1.33x; 1.5x would give 7.0.
6. **Equation 2.** Its second line is printed with its -1 exponents dropped and A and B swapped,
   and a step of the derivation carries a stray G_eq,A. Cell A's line and Figures 3b and 5 agree
   with the correct form.
7. **The shell ratio** (proliferating tumors).
   - The numerator printed is the tumor's outer shell, not the attacking healthy shell the text
     defines.
   - The printed simplification (6r² - 6rc + 8c²)/(6r² - 6rc + 56c²) is below 1 for every radius.
     Those volumes give (6r² - 12rc + 8c²)/(6r² - 36rc + 56c²).
   - The qualitative claim stands either way.
8. **The appendix recursion** is printed as G_eq,n+1 = 1/[(G_eq,n⁻¹ + G_GJ⁻¹)⁻¹ + G_eq,n].
   - With its outer reciprocal the right side is a resistance.
   - Its second term is the whole chain's G_eq,n, where the derivation adds one cell with its own
     decay conductance (§4).
9. **Not printed:** the GRN constants, Snail, the regulatory coordinates' physical scale and time
   unit, the normalization criterion, the simulated time and the binary search's tolerance. The
   code gives them (table above), but not their physical scale and time unit.
10. **Code location.** The data statement says GitLab, with no URL or revision. BITSEY's cancer
    code changed again on 11 November 2026 (b007aab).

## 2. The reference

**BITSEY was not run.** Its repository ([grodstein/bitsey](https://gitlab.com/grodstein/bitsey))
has no licence file: GitLab detects none, and `sim.py`'s "See LICENSE" points to none, at b2cb370
and at b007aab. The task's condition for running it (a licence that allows it) was not met when
the work began.
- The user's ruling of 17 November allows running BITSEY unmodified, out of process, in its own
  environment, like BETSE. This needs a proposal first (§6).
- Its code is never copied into Cells.

**The reference is the preprint's printed numbers**, each cited in
[`paper.py`](../validation/gap_junction_tissue/paper.py) (`REPORTED`):
- Tables 1-3, printed;
- Figure 1's peaks and floors, Figure 3b's values at G_GJ = G_eq, and Figure 8's line values and
  intercepts, read with stated tolerances;
- Figure 5's 7.15 and ratio 1.33x, printed in the caption;
- the voltages and the effective valence, printed.

The reading tolerances were set after the closed forms were evaluated; they check the reading,
not the engine.

**Independent references, derived from the preprint's equations alone** (`paper.py`):
- equation 2;
- the printed recursion taken as a conductance, and the straight chain's recursion;
- a dense linear solve of any network of linear cells;
- the Chen-Izu gate, with the code's Cx45 constants. Those reproduce Figure 1: 0.968 and 0.945 at
  dV = 0, floor 0.06.

**Provenance of the tables**, from the code's notes and saved logs at b2cb370
(`cancer_GJ_sims/0readme_miRNA.txt`, `cancer_GJ_sims/results_miRNA/`), read and not copied:
- **Table 2's 0.5 row** equals, to its printed digits, the 2D size scan on a 1x25x25 field
  (`tumor_isolate_2D_V1M`).
- **Table 3's values** equal a 1D run on a 1x1x25 line (`metas_algos_1D_V1M_0_81.gz`, tumorness
  1, border tau 0.5).
  - The log records the same numbers against G0 one grid step lower for the last three rows:
    8.80e-16, 2.61e-15 and 7.75e-15, not the printed 2.6e-15, 7.8e-15 and 2.3e-14.
  - The log's depol, nbrDepol and hypol values are the printed table's depol, hypol and
    neighbor-depol columns. The log's labels agree with the preprint's text (item 4).
- **Table 1** matches no saved output at that revision.
- **The logged "no tricks" thresholds** (the "neither" condition) are 7.18e-15 m²/s on the 1D line
  and 1.89e-15 on the 2D field. The preprint prints only the 3D value, 1.1e-15.

## 3. Mapping onto Cells

| Preprint part | Cells today | Status |
| --- | --- | --- |
| Well-mixed cells, Na/K/Cl and fixed anion, voltage from charge and capacitance | `resolved_pump_tissue@3` cells; capacitor closure | Covered |
| GHK leak channels; held bath | `constant_field@1` membrane routes or `kleak_always_open@1`/`naleak_always_open@1` populations; held reservoirs | Covered |
| BETSE's thermodynamic Na/K-ATPase | `nak_atp_mass_action_positive@1`, Cells' own thermodynamic pump | Different law, same role: not a gap. A replication would set leaks so that the voltages match the preprint's |
| Ion electrodiffusion through junctions | `constant_field@1` junction routes | Covered |
| A neutral species made and destroyed in each cell that crosses junctions | `local_species_reactions@1` with the passive-routes kind's `passive_neutral_permeation@1` on a junction host: admitted, and it runs (§4). @3's own constant-field junction route for such a species is refused | Available, not qualified (Q1) |
| The miRNA's drift on junctions (valence -1) while it reacts | The species operators and the passive routes' neutral law carry valence 0 only | **F2** |
| Chen-Izu two-state Cx45 gating | One junction law, `junction_voltage_relaxation@1`, BETSE's relaxation in abs(Vj). A passive route opens with its junction's gate | **F3** |
| Closed gate passes ions (floor 0.06) but not miRNA (floor 0) | One minimum open fraction per junction, shared by every route through it | **F4** |
| Depolarization by state; connexin expression by state, with the border rules (minimum, and the mean of 1 and P) | `species_regulated_availability@1`: Hill factors of a route-free species in the same cell, on channel and junction availability. A junction's sides combine by product | Partly: **F5** |
| Neighbor-depol: a tumor cell depolarizes its healthy neighbours | No mechanism in the preprint; the code gates a cell's K channel by its neighbours' state | **F8** |
| The EMT switch (modified Hill rates, six-site miR200-Zeb binding) | `local_species_reactions@1`, written as sums of Hill-factored sources and translation terms. The legacy `emt_mirna@1` holds the equations (a reference, D196) | Admitted at the definition (§4), not run; **F6** optional |
| Lattices: 1D 25, 2D 25x25, 3D 25x25x25 | Factored field solve, at most 2048 nodes | 1D and 2D fit; 3D: **F7** |
| Binary search on the diffusion constant or GJ_power | Driver level | Validation tooling |
| The linear model | As written: reactions and a passive junction route, as above. As its Norton equivalent: @3's own routes | Both run (§4) |

**The legacy surface.** The legacy two-cell `emt_mirna_pair@1` holds bounded versions of F2 and
F4 under the source's conventions: drift with valence -1 but no charge, and algebraic 45/45 gate
scales. It has no expression feedback. Under D196 it is a reference to learn from, not a surface
for this work.

## 4. The replication worlds and their results

**The linear model, and its Norton equivalent.**
- The preprint's linear cell has generation i_gen0 = K_dec mR_UL and decay K_dec, so that [mR] =
  mR_UL - i_exit/G_eq with G_eq = V K_dec.
- Its Norton equivalent, which the preprint draws (Figure 7), is a membrane of conductance
  P A = V K_dec to a reservoir held at mR_UL. Both give V dc/dt = G_eq (mR_UL - c) - outflows,
  term for term.
- The driver builds the equivalent on @3's own routes: one neutral species, so the constant-field
  flux is Fick's. Only ratios are reported, so the declared radius (5 um) and K_dec (0.05 1/s) set
  only the run length.
- It is the linear model only, not the EMT switch.

**Criteria, fixed in the driver before any run** (`run.py`):
- E1: the engine against the dense solve of the same network, 1e-9 relative.
- E2: the steady state, under 1e-12 relative change over the last 10 s.
- E3: the probe flux from the engine's own membrane ledger.
- E4: chains' Norton conductance against the straight chain's recursion, 1e-8.
- P1 and P2: the readings of the preprint.
- K1: a planted 1% junction error must fail E1.
- A1: the engine's own run checks.

**The runs.**

| Run | Snapshot | What |
| --- | --- | --- |
| `smoke-01` | e84e62e6 | Probes, the gate fit, and the first dt study |
| `dev-01` | 36bc5f6c | dt x rate <= 0.1; one arm refused by the energy check |
| `dev-02` | b177cfa2 | dt x rate <= 0.04; every arm complete (the numbers below) |
| `dev-03` | eebd608a, clean | The same with the engine's run records and views, for the viewer |

The earlier snapshots were dirty only in `docs/README.md`'s index line, recorded in their
`checkout.patch`. No run's code differed from its revision.

**The definition probes** (the engine's own answers):
- **@3's constant-field junction route** for a species that `local_species_reactions@1` makes is
  refused. The message reads "'S' has a route through junction j_0: @3's explicit-rate bound
  covers a neutral species on faces alone...". The same world without the route is admitted.
- **The passive-routes kind's junction route** (`passive_neutral_permeation@1`) for that species
  is admitted beside the reactions.
- **The EMT switch** written as `local_species_reactions@1` reactions in one cell is admitted.
  The structure follows Figure 2 and the Methods, with synthetic values:
  - two Hill-factored sources per modified Hill rate;
  - seven translation terms for the six binding sites;
  - first-order decays.
- **The hosted laws.** @3 hosts one junction law, five channel laws and two pump laws.
- **The node bound.** 2,047 cells on one bath are admitted and 2,048 refused ("requires
  cells/outside within the dense node bound"). The preprint's 1D line (26 nodes) and 2D field (626)
  fit; its 3D field (15,626) does not.

**F3 and F4, measured: the junction law against Figure 1** (part `gate`). These numbers are fitted:
- `junction_voltage_relaxation@1`'s steady open fraction, from the engine's own kinetics function,
  fitted by grid search to the Cx45 small-ion curve. The curve uses the code's constants above,
  normalized at dV = 0, over -100 to 100 mV.
- Best fit: threshold 17 mV, minimum 0.112, worst error 0.050 of the open conductance (F3).
- The same law, with its one minimum for every route, misses the miRNA curve (floor 0) by up to
  0.112 (F4).
- At 40 mV: the law 0.128, Cx45 small ions 0.118, miRNA 0.059.

**The step: @3's energy check, not its stability bound.**
- **The refusals.** Two worlds completed their integration, and then @3's host check refused them:
  "Resolved pump accounting failed: energy". That check allows 2e-3 of the booked flows under
  ARS(2,2,2).
- **Two dt studies** (dt x rate is @3's own explicit rate times the step):

  | World | Explicit rate | Refused at | Passed at (energy residual / flows) |
  | --- | --- | --- | --- |
  | Figure 5a's network, g = 100 | 40.1/s | 0.63, 0.31 | 0.157 (1.4e-3), 0.078 (3.5e-4) |
  | Figure 3's two cells, g = 50 | 5.1/s | 0.080 | 0.040 (6.4e-4), 0.020 (1.6e-4) |

- **The reading.** The residual is second order in dt, with a coefficient that depends on the
  world. The stability bound is dt x rate <= 1.
- **Already known.** This is the limit recorded as finding 3 of
  [SHARED_INVENTORY_REACTIONS_DESIGN.md](SHARED_INVENTORY_REACTIONS_DESIGN.md) (probe C4): in
  species-only worlds the host energy ledger refuses once the per-step relaxation exponent reaches
  0.1.
- **What follows.** The check is not loosened. The driver keeps dt x rate <= 0.04, which covers
  both worlds. The compared steady state is the scheme's fixed point and does not depend on dt.

**The Norton-equivalent network** (`dev-02`).
- All 24 arms pass E1 (at most 2.7e-14), E2 (at most 9e-16) and E3 (at most 1.3e-12), and the
  engine's own material, charge and energy checks on every accepted row.
- In the Figure 3 table, the engine's and equation 2's values are derived; Figure 3b's 6.67 / 8.33
  is read.

| Figure 3: two equal cells, unloaded 5 and 10 (printed) | Engine (mM) | Equation 2 |
| --- | --- | --- |
| G_GJ = 0.5 G_eq | 6.250000 / 8.750000 | 6.25 / 8.75 |
| G_GJ = G_eq | 6.666667 / 8.333333 | 6.666667 / 8.333333; Figure 3b reads 6.67 / 8.33 |
| G_GJ = 2 G_eq | 7.000000 / 8.000000 | 7 / 8 |
| G_GJ = 5 G_eq | 7.272727 / 7.727273 | same |
| G_GJ = 10 G_eq | 7.380952 / 7.619048 | same |
| G_GJ = 50 G_eq | 7.475248 / 7.524752 | same |

**Figure 5.**
- **The lumped model** (cell B 4/3 cell A, unloaded 10 and 5, printed) equals equation 2 to
  rounding:
  - 8.181818 / 6.363636 at G_GJ = G_eq;
  - 7.297297 / 7.027027 at 10 G_eq;
  - 7.175141 / 7.118644 at 50 G_eq.
- **Its limit** is 50/7 = 7.142857 (derived). The caption prints 7.15, within the 0.01 reading
  tolerance; 7.142857 rounds to 7.14.
- **The drawn seven-cell network** (Figure 5a) equals its dense solve to 2.7e-14. Cells A / B:
  - 8.684211 / 6.052632 at G_eq;
  - 7.546513 / 6.855076 at 10 G_eq;
  - 7.238270 / 7.074732 at 50 G_eq.
- **The backup cells** act as a 4/3-larger cell B only as G_GJ grows. At 50 G_eq the drawn network
  sits 0.06 mM from the lumped values.

**Figure 8: chains' Norton conductance**, G_eq,n / G_eq,1, at G_GJ = G_eq,1.
- G_GJ = G_eq,1 is derived from Figure 8's 1- and 2-cell lines (both 0.1 in its units).
- The engine's column is from two loads at the port. The printed recursion is taken as a
  conductance.
- The [mR] values at Iexit = -0.5 mol/s are in Figure 8's units. Figure 8's values are read.

| n | Engine | Straight chain (derived) | Printed recursion (derived) | [mR] at Iexit = -0.5: engine / printed recursion / Figure 8 read |
| --- | --- | --- | --- | --- |
| 1 | 1.000000 | 1 | 1 | 6.000 / 6.000 / 6.0 |
| 2 | 1.500000 | 1.5 | 1.5 | 4.333 / 4.333 / 4.33 |
| 3 | 1.600000 | 1.6 | 2.1 | 4.125 / 3.381 / 3.4 |
| 4 | 1.615385 | 1.615385 | 2.777 | 4.095 / 2.800 / 2.8 |
| 5 | 1.617647 | 1.617647 | 3.513 | 4.091 / 2.423 / 2.45 |
| 10 | 1.618034 | 1.618034 | 7.666 | (not in Figure 8) |

- **The engine's chains** equal the straight chain's recursion to 1e-12. They saturate at the
  golden ratio, (1 + sqrt 5)/2 G_eq,1, and return the unloaded value 1.000000.
- **The printed recursion** gives values that grow without bound: 24%, 42% and 54% above the
  engine's at n = 3, 4 and 5.
- **What this rests on.** The comparison rests on the algebra and on the reading of Figure 8. The
  engine checks only the straight chain.
- **Scope.** The preprint's tissue simulations do not use this recursion. Table 2's own increments
  shrink with size: its 0.5 row rises by 2.4 from 1x1 to 2x2 and by 1 from 7x7 to 8x8, in units of
  1e-14.

**The planted control.** Every junction permeability x1.01 moves the g = 1 steady state by 8.3e-4
of the unperturbed reference. E1 catches it (K1).

**The linear model as written** (scratch probe, `probes/as-written-01`, from the checkout at
eebd608a, not part of the committed driver):
- Two cells of 1 pL, each with a zeroth-order source and a first-order decay (K 0.05 1/s,
  unloaded 5 and 10 uM), through `local_species_reactions@1`.
- One `passive_neutral_permeation@1` route on the junction between them (gate pinned open).
- **The result.** It reaches equation 2's steady state to 1.7e-5 at G_GJ = G_eq. At 5 G_eq the
  error is 1.2e-4, 3.0e-5 and 7.4e-6 at dt 0.25, 0.125 and 0.0625 s.
- **The reading.** That is second order: the split of reactions around @3's step moves the fixed
  point by O(dt²). The Norton form has no split and is exact at its fixed point.

**Records for the viewer** (`dev-03`).
- Each arm is written by the engine's own writer, `cells.io.write_run`, under `worlds/<arm>`, with
  its run view (`cells.run_view@1`, `view.json`) and the driver's `run.json`. The run view carries
  a prescribed 2D layout after the preprint's drawings.
- `run.json` holds the revision, the models, the definition's hash, what the run represents and
  every arm's parameters and readouts.
- Selected arms are written again as viewer packages, with a recording subset. Each layer's
  records stay under 1 MB (`viewer/index.json`).
- A 60 s format fixture is at `runs/fixture-01`.

## 5. Gaps, as general engine features

None is specific to this paper (D136, D144). Each needs its own design note (D142) and
qualification before a replication relies on it.

- **Q1 (qualification, not a gap). A reacting neutral species on junctions.**
  - The passive-routes kind's `passive_neutral_permeation@1` on a junction host, beside
    `local_species_reactions@1`, is admitted and runs. The law is not numerically qualified, and
    the split moves the fixed point by O(dt²) (§4).
- **Why @3's own constant-field junction route stays refused.**
  - The code: `species_common.check_impermeant`, at `src/cells/models/operators/species_common.py`
    line 148. It is called by `parse_species` (line 94) for the operators that write species
    amounts: reactions, turnover, exchange and site occupancy. `species_regulated_availability@1`
    calls it (line 370) for instantaneous couplings; a species @3 moves may be read only through a
    regulatory state.
  - The reason, from commit 17c34073 of 14 November, answering the lead's question from the D152
    review: @3's explicit-rate bound covered every species on faces but, on membranes and
    junctions, only the z²-weighted charge relaxation. So such a species "would have no
    material-rate bound at the definition".
  - The records: [SECRETED_SPECIES_TRANSPORT_DESIGN.md](SECRETED_SPECIES_TRANSPORT_DESIGN.md) §2
    (accepted at D150's milestone 1) and SHARED_INVENTORY_REACTIONS_DESIGN.md's finding 3 and §9
    Q7 (version 1 keeps the refusal; a queued D148 round adds the z = 0 bound term).
  - That term landed in 119ffb74 (`neutral_material_rate`;
    [INNER_MODEL_V4_DESIGN.md](INNER_MODEL_V4_DESIGN.md) §13.6, with its D148 record). The refusal
    and its message were not revisited.
  - The intended lift is not D191's composition rule, which settles how an operator reads a field
    that another operator changes. It is the declared passive-routes law: INNER_MODEL_V4_DESIGN.md
    §11, "Its refusal lifts only for this law, declared".
- **F2. Charged trace species in reactions and on junctions.**
  - The miRNA's drift with its effective valence -1, while it reacts, with its charge counted in
    the capacitor closure.
  - Today the species operators and the passive routes' neutral law take valence 0 only. The
    proton leak is charged, but on patches only. The code's convention of drift without charge is
    not carried into the engine.
- **F3. A connexin gating catalogue.** A two-state junction law (Chen-Izu et al. 2001), algebraic
  or relaxing, with per-connexin constants, homotypic and heterotypic, beside
  `junction_voltage_relaxation@1`. The preprint's Discussion turns on heterotypic Cx43/Cx45 at the
  tumor border.
- **F4. Size selectivity of the closed gate.** A per-species (per-route) residual permeability of
  the closed state, so that large solutes (miRNA, dyes) pass only open channels while small ions
  keep a floor.
- **F5. Expression-coupled junctions with declared docking rules.**
  - `species_regulated_availability@1` sets channel and junction availability from a cell's
    species, and a junction's two sides combine by product only.
  - Missing: the minimum, for underexpression, and the mean, for overexpression's border.
    Overexpression above the base conductance also needs the base declared at the top of the range.
- **F6. Regulatory laws as declared laws** (optional). The modified Hill (lambda) form and the
  microRNA-target binding partition as checked laws, with the regulatory coordinates' physical
  scale and time unit declared.
- **F7. A field solve beyond 2048 nodes**, for the 3D field (15,626 nodes) and any tissue beyond
  about 2,000 cells.
- **F8. A mechanism for neighbor depolarization.**
  - The preprint gives none. The code gates a cell's K channel directly by its neighbours' state.
  - A physical mechanism, a secreted or junction-borne signal acting on channels, must first be
    sourced from the literature (D136: hypotheses stay hypotheses).

**Which gaps block which result.**

| Preprint result | Needs | Blocked by |
| --- | --- | --- |
| Figure 1 | the two-state Cx45 gate with per-species floors | F3, F4 |
| Figures 3b, 5, 8 | linear cells and neutral junction transport | Nothing: run as written (Q1) and as the Norton equivalent |
| Table 1, neither | EMT switch, neutral miRNA on junctions, 3D field | F7 (with Q1) |
| Table 1, depol alone | adds state-set voltage, miRNA drift, the gate and its floors | F2, F3, F4, F7 |
| Table 1, underexpression alone | adds state-set connexin, minimum docking | F5, F7 |
| Table 1, both | all of the above | F2, F3, F4, F5, F7 |
| Table 2 (2D, both) | as Table 1, both, on 626 nodes | F2, F3, F4, F5 |
| Table 3, depol | overexpression (mean docking), depolarized tumor | F2, F3, F4, F5 |
| Table 3, hypol | overexpression, every cell at one voltage | F5 (with Q1) |
| Table 3, neighbor-depol | adds the neighbour mechanism | F2, F3, F4, F5, F8 |

**The minimum set per table:**
- Table 1: F2, F3, F4, F5 and F7.
- Table 2: F2, F3, F4 and F5.
- Table 3: F2, F3, F4 and F5, and F8 for its third column. Its hypol column alone needs F5.

The "neither" condition needs no new feature on the 1D line or the 2D field. Its references there
are the code's logged thresholds (§2), not printed numbers.

## 6. What a judged comparison would need: a D138 question for the user

A judged comparison needs the user's approval and a registered protocol (D138). Proposed, for the
user to decide:
- **(a) Now: the linear model.**
  - Figures 3b, 5 and 8, as written (with Q1's qualification: a dt study and the closed forms) and
    as the Norton equivalent.
  - It qualifies the passive-routes neutral law beside reactions, and @3's neutral permeant species,
    against analytic references.
  - It runs in under an hour on four CPUs.
- **(b) Next, with no new feature: the "neither" condition** on the 1D line and the 2D field.
  - The EMT switch with a neutral miRNA on passive junction routes.
  - Against the code's logged thresholds, 7.18e-15 and 1.89e-15 m²/s. These are from the code, not
    printed.
  - It needs a declared physical scale and clock for the regulatory coordinates (F6's question).
- **(c) After F2-F5: the tables, in the order the engine allows.**
  - Order: Table 3's line, then Table 2's field, then Table 1 with F7.
  - Cells' pump and junction laws differ from BITSEY's by design. The criteria would therefore be
    the preprint's orderings with factor tolerances:
    - depolarization beats underexpression, and both together beat either;
    - resistance grows with tumor size;
    - invasion needs P > 1;
    - depol needs the largest P.
  - Exact values are not expected to match.
- **(d) The references.** Two choices for the user:
  - which labelling of Table 3 governs: the printed rows and columns, or the code's log (§2);
  - whether to run BITSEY unmodified, out of process, in its own environment
    (`/mnt/workspaces/Cells/venv-bitsey`), to produce Cells' own reference outputs at the
    revision the preprint used (b2cb370), as is done for BETSE.
