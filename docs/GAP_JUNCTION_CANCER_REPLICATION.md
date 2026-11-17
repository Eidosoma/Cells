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
  (F8). The lead filed these as FR-15 to FR-17.
- **One tissue condition runs on today's engine:** the "neither" condition on the 1D line. Its
  reference is BITSEY's log, not a printed number (§7).
- **The preprint's linear model ("intuitive model": equations 1-2, appendix, Figures 3, 5 and 8)
  runs on the engine in two forms**, both in the committed driver (§4).
  - **As written:** a source and a decay in each cell (`local_species_reactions@1`) and a junction
    route (the passive-routes kind's `passive_neutral_permeation@1`, not numerically qualified).
    In `dev-04` it reaches the dense solve of every network it ran to 1.0e-5 at the step rule's dt
    and 2.5e-6 at half of it, at second order in dt (§4).
  - **As its exact Norton equivalent** on @3's own routes. It reproduces equation 2 and Figure 5
    to 3e-14 or better and computes straight chains' Norton conductance. It is the check on the
    as-written runs.
- **Figure 8: what the printed equations give, against direct analysis and the engine's solve.**
  The appendix's recursion, read as Figure 7's resistance form, gives a chain conductance that
  grows without bound; taken literally, it is a resistance. Direct analysis and the engine's solve
  of a straight chain give a conductance that saturates at 1.618 G_eq,1 (§4).
- **The engine's energy check sets the step** for neutral species on membranes and junctions,
  well below the stability bound. This is consistent with the shared-inventory design's finding 3
  (§4). The lead filed it as FR-18.

**Engine models run.**
- `resolved_pump_tissue@3`, with `constant_field@1` membranes and junctions for one neutral
  species, held reservoirs and `junction_voltage_relaxation@1` pinned open: the Norton form.
- `resolved_pump_composite@1` over @3, with `local_species_reactions@1` and the passive-routes
  kind's `passive_neutral_permeation@1`: the linear model as written, and the "neither" search.
- The `resolved_capacitor_components_current_continuity@1` closure and
  `imex_ars222_face_electromigration@1`.

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
- Figure 1's peaks and floors and Figure 3b's values at G_GJ = G_eq, read with stated
  tolerances. The preprint gives no conductance values for Figure 8, and none of its plotted lines
  is read;
- Figure 5's 7.15 and ratio 1.33x, printed in the caption;
- the voltages and the effective valence, printed.

The reading tolerances were set after the closed forms were evaluated; they check the reading,
not the engine.

**Independent references, derived from the preprint's equations alone** (`paper.py`):
- equation 2;
- for Figure 8's chains, direct analysis and the printed recursion, taken literally and read as
  Figure 7's resistance form, in the terms of an independent derivation (§4);
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
- **The 1D log comes from an earlier revision of the code than b2cb370's.**
  - Its search is titled "lowest Kd that fixes a 1-spot", where `zombie.py` line 1068 has "...fixes
    a tumor".
  - It prints a junction dump that b2cb370's `sim_is_fixed` does not.
  - The settings it prints are b2cb370's: the switch's scales, `ITERATE=False`, valence -1 through
    junctions, Snail 72, and "no tricks".

## 3. Mapping onto Cells

| Preprint part | Cells today | Status |
| --- | --- | --- |
| Well-mixed cells, Na/K/Cl and fixed anion, voltage from charge and capacitance | `resolved_pump_tissue@3` cells; capacitor closure | Covered |
| GHK leak channels; held bath | `constant_field@1` membrane routes or `kleak_always_open@1`/`naleak_always_open@1` populations; held reservoirs | Covered |
| BETSE's thermodynamic Na/K-ATPase | `nak_atp_mass_action_positive@1`, Cells' own thermodynamic pump | Different law, same role: not a gap. A replication would set leaks so that the voltages match the preprint's |
| Ion electrodiffusion through junctions | `constant_field@1` junction routes | Covered |
| A neutral species made and destroyed in each cell that crosses junctions | `local_species_reactions@1` with the passive-routes kind's `passive_neutral_permeation@1` on a junction host: admitted, and it runs (§4). @3's own constant-field junction route for such a species is refused | Admitted and runs; not qualified (Q1) |
| The miRNA's drift on junctions (valence -1) while it reacts | The species operators and the passive routes' neutral law carry valence 0 only | **F2** |
| Chen-Izu two-state Cx45 gating | One junction law, `junction_voltage_relaxation@1`: a relaxation in abs(Vj), its rates cited from BETSE v1.5.0. A passive route opens with its junction's gate | **F3** |
| Closed gate passes ions (floor 0.06) but not miRNA (floor 0) | One minimum open fraction per junction, shared by every route through it | **F4** |
| Depolarization by state; connexin expression by state, with the border rules (minimum, and the mean of 1 and P) | `species_regulated_availability@1`: Hill factors of a route-free species in the same cell, on channel and junction availability. A junction's sides combine by product | Partly: **F5** |
| Neighbor-depol: a tumor cell depolarizes its healthy neighbours | No mechanism in the preprint; the code gates a cell's K channel by its neighbours' state | **F8** |
| The EMT switch (modified Hill rates, six-site miR200-Zeb binding) | `local_species_reactions@1`, written as sums of Hill-factored sources and translation terms. The legacy `emt_mirna@1` holds the equations (a reference, D196) | Runs in the "neither" search (§7); **F6** optional |
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
- E1: the Norton form against the dense solve of the same network, 1e-9 relative.
- E2: the steady state, under 1e-12 relative change over the last 10 s.
- E3: the probe flux from the engine's own ledger against G_probe (c - held), 1e-9.
- E4: chains' Norton conductance against direct analysis, 1e-8.
- W1-W3, for the as-written form at the step rule's dt and at half of it, fixed at 7cdd7dce before
  any as-written run:
  - W1: steady (E2) at both steps;
  - W2: within 1e-4 of the dense solve at the half step;
  - W3: an observed order log2(e(dt)/e(dt/2)) in [1.6, 2.4], where e(dt) > 1e-9.
- P1: the readings of the preprint (Figures 3b and 5). Its tolerances were set after the closed
  forms were evaluated; they check the reading, not the engine.
- K1: a planted 1% junction error must fail E1.
- A1: the engine's own run checks.

**The runs.**

| Run | Snapshot | What |
| --- | --- | --- |
| `smoke-01` | e84e62e6 | Probes, the gate fit, and the first dt study |
| `dev-01` | 36bc5f6c | dt x rate <= 0.1; one arm refused by the energy check |
| `dev-02` | b177cfa2 | dt x rate <= 0.04; every Norton arm complete |
| `dev-03` | eebd608a, clean | The same with the engine's run records and views; stopped, superseded by `dev-04` |
| `fixture-02` | 7cdd7dce, clean | Two 60 s format fixtures for the viewer, Norton and as written |
| `dev-04` | 7cdd7dce, clean | Every part: the Norton form, the as-written form with its dt study, records and views (the numbers below) |
| `neither-01` | 52caf2dc, clean | The "neither" search (§7) |

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
- **Consistent with finding 3** of
  [SHARED_INVENTORY_REACTIONS_DESIGN.md](SHARED_INVENTORY_REACTIONS_DESIGN.md) (probe C4). There,
  species-only worlds were refused by the host energy ledger from a per-step relaxation exponent
  x = 0.1, with second-order errors below it.
  - In C4's per-junction variable, x = dt G (1/V_a + 1/V_b), both worlds here pass at x = 0.039
    and are refused at 0.078. Where the refusal starts depends on the world.
- **What follows.** The check is not loosened; the lead filed it as FR-18. The driver keeps
  dt x rate <= 0.04, which covers both worlds.
  - The Norton form's compared steady state is the scheme's fixed point and does not depend on dt.
  - The as-written form's fixed point moves by O(dt²), as measured below.

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

**Figure 8: what the printed equations give, against direct analysis and the engine's solve.**
G_eq,n / G_eq,1 of a straight chain of n linear cells, sealed at its far end, at
G_GJ = V_cell K_dec = G_eq,1.
- The preprint gives no conductance values for Figure 8: no G_GJ, V_cell or K_dec. The ratio
  compared here is therefore a choice, and nothing is read from the figure's plotted lines.
- The columns besides the engine's are those of an independent derivation from the preprint's
  equations, `/mnt/workspaces/Cells/gap-junction-derivation-20261117/derivation.md`, checked by
  its `chain_check.py`. `paper.py` computes them again:
  - **D**, direct analysis: G_n+1 = g + (1/G_n + 1/G_GJ)⁻¹, with g = V_cell K_dec = G_eq,1;
  - **P_lit**, the printed recursion taken literally. Its right side is a resistance, so its values
    hold only in units of g;
  - **P_res**, the printed right side read as 1/G_eq,n+1: Figure 7's resistance form with both
    resistances indexed n, G_n+1 = (1/G_n + 1/G_GJ)⁻¹ + G_n.
- The engine's column is the Norton conductance from two loads at the port (`dev-04`, E4).

| n | Engine | D | P_lit (units of g) | P_res |
| --- | --- | --- | --- | --- |
| 1 | 1.000000 | 1 | 1 | 1 |
| 2 | 1.500000 | 1.5 | 0.666667 | 1.5 |
| 3 | 1.600000 | 1.6 | 0.937500 | 2.1 |
| 4 | 1.615385 | 1.615385 | 0.703546 | 2.777419 |
| 5 | 1.617647 | 1.617647 | 0.895628 | 3.512688 |
| 10 | 1.618034 | 1.618034 | 0.765540 | 7.665784 |

- **The engine's chains** equal D to 6e-13 (E4). They saturate at the golden ratio,
  (1 + sqrt 5)/2 G_eq,1, and their intercept is the unloaded value, 1.000000, for every n.
- **P_res** equals D at n = 1 and 2 and grows without bound from n = 3. It is 31%, 72% and 117%
  above D at n = 3, 4 and 5; equivalently, D is 24%, 42% and 54% below P_res.
  - The derivation traces the difference to the second term: the whole n-cell chain stands where
    direct analysis adds one cell's own g.
- **P_lit** equals D only at n = 1.
- **The intercept**, mR_UL0, is the same in every form; only the slope, 1/G_eq,n, differs.
- **Figure 7** reproduces D exactly when its un-indexed R_thev is read as one cell's (the
  derivation).
- **Scope.** The preprint's tissue simulations do not use this recursion. Table 2's own increments
  shrink with size: its 0.5 row rises by 2.4 from 1x1 to 2x2 and by 1 from 7x7 to 8x8, in units of
  1e-14.

**The planted control.** Every junction permeability x1.01 moves the g = 1 steady state by 8.3e-4
of the unperturbed reference. E1 catches it (K1).

**The linear model as written** (`dev-04`, part `aswritten`).
- **The world.**
  - Each cell has a zeroth-order source K_dec mR_UL and a first-order decay K_dec
    (`local_species_reactions@1`).
  - Each junction has a `passive_neutral_permeation@1` route with P A = G_GJ, its gate pinned open.
  - Each probe is the same law on a patch to its own held bath.
  - Amounts are in uM, a trace beside the ions. Volumes, G_eq and the step rule are the Norton
    form's.
- **The runs.** Every arm ran at the step rule's dt (its run of record) and at half of it:
  - Figure 3b at G_GJ = 0.5, 1, 2, 5 and 10 G_eq;
  - Figure 5b at G_eq and 10 G_eq, and Figure 5a at G_eq;
  - the chains of 1-5 and 10 cells, each with both loads.
- **The result.** All 20 arms pass W1-W3 and the engine's own checks (derived references).
  - Against the dense solve of the same network, the worst relative error is 1.0e-5 at the step
    rule's dt and 2.5e-6 at half of it. The observed order is 2.00 to 2.01.
  - The chains' Norton conductance follows D to 9.7e-6 at dt and 2.4e-6 at half of it, at every
    n. At n = 10 it is 1.618050 and then 1.618038, against D's 1.618034.
  - The probe flux from the route's own ledger matches G_probe (c - held) to 1.5e-5. That is the
    same O(dt²); E3 is a Norton criterion, reported here and not judged.
  - In `results.json` the as-written arms' E1 and E4 flags read false. They are Norton criteria
    (1e-9 and 1e-8); W1-W3 are the as-written ones.
- **Not run: Figure 5a at 10 G_eq as written.** The runner refused it before integration.
  - At its step (1/128 s), the composite's full trace would take 2.6 GB against the 2 GB budget,
    and 5.1 GB at the half step. The Norton form needs 0.2 GB and ran it.
  - The windowed path, which keeps no whole trace, would run it, but the engine's record writer
    needs the full trace.
- **The reading.** The split of reactions around @3's step moves the fixed point by O(dt²). The
  Norton form has no split and is exact at its fixed point. A scratch probe first showed this
  (`probes/as-written-01`, from the checkout at eebd608a).

**Records for the viewer** (`dev-04`).
- Each arm is written by the engine's own writer, `cells.io.write_run`, under `worlds/<arm>`, with
  its run view (`cells.run_view@1`, `view.json`) and the driver's `run.json`. The run view carries
  a prescribed 2D layout after the preprint's drawings.
- `run.json` holds the revision, the models, the definition's hash, what the run represents (for
  its form) and every arm's parameters and readouts.
- Selected arms are written again as viewer packages, with a recording subset. Each layer's
  records stay under 1 MB (`viewer/index.json`).
  - Six Norton packages are selected. Figure 5a's (G_eq) is left out: its membrane layer is
    1.06 MB.
  - All 32 written views pass the engine's reader check (`run_view.validate`, with each run's
    files).
- `viewer/summary.json` lists the sweeps for the viewer's charts (`cells.experiment_summary@1`):
  Figures 3b, 5b, 5a and 8, each a parameter, its readouts and, where the preprint states one,
  equation 2's values. Only the Norton sweeps are listed until the as-written arms have views.
  `dev-04`'s was written after the run, from its `results.json`, by the driver's `sweep_summary`.
- **The as-written arms have complete records but no run view.** The writer refuses them:
  `local_species_reactions@1` declares no view layers, no set for its `reaction_route` axis and no
  axes for its readout columns. Seam F's registry owner is adding those declarations. Views for
  these arms will then be written from the saved records, or from a rerun.
- `runs/fixture-01` and `runs/dev-03` are superseded and are not for the viewer.

## 5. Gaps, as general engine features

None is specific to this paper (D136, D144). Each needs its own design note (D142) and
qualification before a replication relies on it.

- **Q1 (qualification, not a gap; FR-15). A reacting neutral species on junctions.**
  - The passive-routes kind's `passive_neutral_permeation@1` on a junction host, beside
    `local_species_reactions@1`, is admitted and runs today. The law is not numerically
    qualified, and the split moves the fixed point by O(dt²) (§4).
  - Whether that admission is intended is the core's call. The reactions' parser does not ask
    which species @3 or the passive routes move; only `species_regulated_availability@1` does.
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
  - D191's composition rule, which settles how an operator reads a field that another operator
    changes, does not lift this refusal. INNER_MODEL_V4_DESIGN.md §11 lifts it for the
    passive-routes law alone: "Its refusal lifts only for this law, declared".
- **F2. Charged trace species in reactions and on junctions (FR-15).**
  - The miRNA's drift with its effective valence -1, while it reacts, with its charge counted in
    the capacitor closure.
  - Today the species operators and the passive routes' neutral law take valence 0 only. The
    proton leak is charged, but on patches only. The code's convention of drift without charge is
    not carried into the engine.
- **F3. A connexin gating catalogue (FR-16).** A two-state junction law (Chen-Izu et al. 2001), algebraic
  or relaxing, with per-connexin constants, homotypic and heterotypic, beside
  `junction_voltage_relaxation@1`. The preprint's Discussion turns on heterotypic Cx43/Cx45 at the
  tumor border.
- **F4. Size selectivity of the closed gate (FR-16).** A per-species (per-route) residual permeability of
  the closed state, so that large solutes (miRNA, dyes) pass only open channels while small ions
  keep a floor.
- **F5. Expression-coupled junctions with declared docking rules (FR-16).**
  - `species_regulated_availability@1` sets channel and junction availability from a cell's
    species, and a junction's two sides combine by product only.
  - Missing: the minimum, for underexpression, and the mean, for overexpression's border.
    Overexpression above the base conductance also needs the base declared at the top of the range.
- **F6. Regulatory laws as declared laws** (optional). The modified Hill (lambda) form and the
  microRNA-target binding partition as checked laws, with the regulatory coordinates' physical
  scale and time unit declared.
- **F7. A field solve beyond 2048 nodes (FR-17)**, for the 3D field (15,626 nodes) and any tissue beyond
  about 2,000 cells.
- **F8. A mechanism for neighbor depolarization.**
  - The preprint gives none. The code gates a cell's K channel directly by its neighbours' state.
  - A physical mechanism, a secreted or junction-borne signal acting on channels, must first be
    sourced from the literature (D136: hypotheses stay hypotheses).

**Which gaps block which result.**

| Preprint result | Needs | Blocked by | Compared number printed in the preprint? |
| --- | --- | --- | --- |
| Figure 1 | the two-state Cx45 gate with per-species floors | F3, F4 | No: read off the plot; the gate's constants are the code's |
| Figures 3b, 5, 8 | linear cells and neutral junction transport | Nothing: run as written (Q1) and as the Norton equivalent | Figure 5: yes (7.15 and 1.33x, in the caption). Figure 3b: read (6.67 / 8.33). Figure 8: none; derived only |
| Table 1, neither | EMT switch, neutral miRNA on junctions, 3D field | F7 (with Q1) | Yes (1.1e-15, 3D) |
| The neither condition on the 1D line or 2D field | as above, on 26 or 626 nodes | Nothing (with Q1) | No: BITSEY's log (§2, §7) |
| Table 1, depol alone | adds state-set voltage, miRNA drift, the gate and its floors | F2, F3, F4, F7 | Yes |
| Table 1, underexpression alone | adds state-set connexin, minimum docking | F5, F7 | Yes |
| Table 1, both | all of the above | F2, F3, F4, F5, F7 | Yes |
| Table 2 (2D, both) | as Table 1, both, on 626 nodes | F2, F3, F4, F5 | Yes |
| Table 3, depol | overexpression (mean docking), depolarized tumor | F2, F3, F4, F5 | Yes; the log labels its columns and rows differently (§2) |
| Table 3, hypol | overexpression, every cell at one voltage | F5 (with Q1) | Yes; as above |
| Table 3, neighbor-depol | adds the neighbour mechanism | F2, F3, F4, F5, F8 | Yes; as above |

**The minimum set per table:**
- Table 1: F2, F3, F4, F5 and F7.
- Table 2: F2, F3, F4 and F5.
- Table 3: F2, F3, F4 and F5, and F8 for its third column. Its hypol column alone needs F5.

The "neither" condition needs no new feature on the 1D line or the 2D field. Its references there
are the code's logged thresholds (§2), not printed numbers. The preprint's own "neither" number is
3D (Table 1's 1.1e-15), so comparing that condition with a printed number needs F7 alone (with Q1),
not F2: F7 may come before F2.

## 6. What a judged comparison would need: a D138 question for the user

A judged comparison needs the user's approval and a registered protocol (D138). Proposed, for the
user to decide:
- **(a) Now: the linear model.**
  - Figures 3b, 5 and 8, as written (with Q1's qualification: a dt study and the closed forms) and
    as the Norton equivalent.
  - It qualifies the passive-routes neutral law beside reactions, and @3's neutral permeant species,
    against analytic references.
  - `dev-04` ran it as development work (§4) in 46 minutes, the as-written part in 23. It ran on
    CPUs 6 and 7, with 22 and 23 also for its first 20 minutes.
- **(b) Next, with no new feature: the "neither" condition** on the 1D line, then the 2D field.
  - The EMT switch with a neutral miRNA on passive junction routes.
  - A comparison with BITSEY's log at b2cb370 (7.18e-15 m²/s on the line, 1.89e-15 on the field),
    not with the preprint, which prints only the 3D value.
  - The lead approved the 1D search on 17 November, once the two conditions in §7 were written
    down. It runs as `neither-01`, as development work.
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

## 7. The "neither" comparison (b): written before the search

BITSEY's code below is cited at b2cb370 under D208; nothing is copied.

**1. A neutral miRNA is BITSEY's "no tricks" model** for the junction transport.
- **What the run builds.** It calls `setup_basic_network(..., do_gate=False, do_drive_Vmem=False)`
  (`cancer_GJ_sims/zombie.py`, lines 990-991). There is no junction voltage gate and no state-set K
  channel.
- **The baseline adds neither.** Part 1 of `zombie_tumor_isol` searches at once
  (`find_min_Kd_tumorFix(1e-13, ...)`, line 1004).
- **Every cell is the same.**
  - Each has the same membrane coefficients (`sim.py`'s `init_big_arrays`) and the same ion seeds:
    `disconnected_sim` resets Na 10, K 125 and Cl 55 in every cell (lines 1476-1478).
  - The switch's species have valence 0 in the voltage sum (`GRN_miRNA.py`, lines 384-390).
    miR200's valence -1 is set only inside `EMT_GJ_gate.func`, while its own junction flux is
    computed, and is reset to 0 before the function returns (lines 294-318: set at 304, reset at
    315).
  - So every cell has the same voltage, and every junction's dV is exactly 0.
- **The drift vanishes.** The junction flux is `GJ_Ith + deltaV_GJ*GJ_Gth` (`sim.py`, line 375),
  with drift `GJ_Gth` proportional to the valence (line 623). At dV = 0 the miRNA's valence -1
  (`GRN_miRNA.py`, line 304) contributes nothing, and the flux is Fick's, `-D dc/L` (line 624).
- **One miR200, not free and total.** In the mode used (`ITERATE = False`, line 31), the
  free-miR200 proxy is set equal to the total (`compute_bound_complex_concs_simple`, lines
  191-200), and the junction flux computed from it is applied to the total
  (`out_ion=miR200_total`, line 298). So the junction moves the total down its own gradient, as it
  moves the one species u in Cells.
- **What remains different.**
  - BITSEY also integrates the ions, which neither drive the switch nor move the miRNA in this
    condition.
  - It steps with explicit adaptive Euler.
  - Cells needs positive amounts, so seeds at 0 start at the fixtures' trace, 1e-9 mM (1e-6
    units).

**2. The criterion, the bracket and the tolerance** (BITSEY's own, `zombie.py`):
- **World.** A line of 25 cells (the log's "Field=1x1x25"). The first 6 cells form the tumor at the
  corner (`tumor_size = 6`, `set_corner_tumor`).
- **Seeds and protocol.** Tumor cells start at miR200 0, Zeb mRNA 100, ZEB 100; healthy cells at
  100, 0, 0 (scaled coordinates). Then 500 time units uncoupled (line 1060), then coupled for
  20,000 (line 1056).
  - BITSEY computes the uncoupled state once and starts every coupled run from it (`cc_discon`,
    lines 1059-1060).
  - Cells does the same in one tumor cell and one healthy cell: while uncoupled, every tumor cell
    is the same, and so is every healthy cell.
  - The switch is autonomous, so each coupled run starts its clock at 0.
  - A check of the switch's constants and scale before the search: the uncoupled stage's end
    state in Cells (a cost probe) equals the log's dump after its uncoupled 500 s to the dump's
    printed digits. As Zeb mRNA / ZEB : miR200, the log prints tumor 69/63:9 and healthy 6/0:84;
    Cells gives 68.6/62.7:8.8 and 5.95/0.41:84.0.
  - It does not test the time unit. Both cells are already at steady state: the log's dump at
    D = 0, after 20,000 more, is the same.
- **Coupling.** Junction conductance G_GJ = D x 4 pi (5 um)² / 100 nm (`RThev_GJ`). Only miR200
  crosses.
- **Criterion: normalized.** At the end, every cell has miR200 > Zeb mRNA + 2
  (`healthy_snapped_rows`, line 519). Its row-spread condition is empty on a line of one-cell rows.
- **Bracket: D in [0, 1e-13] m²/s**, BITSEY's. Both ends are run first, as `binSearch` does
  (lines 89-95). If the upper end does not normalize, or the lower end does, the search stops and
  is reported, not widened.
- **Tolerance.** Narrow until x2 <= 1.001 x0 (`binSearch`, line 97) and report x2, the smallest
  normalizing D found.
  - Several points run in parallel, one per CPU. Whenever one finishes, its worker takes a new
    point inside the current bracket.
  - The criterion and the stopping rule are unchanged.
  - After convergence, the final bracket's two ends are rerun at half their step. This is reported,
    not used to move the threshold.
- **The switch's constants** are `GRN_miRNA.py`'s at b2cb370, as in [EMT_REFERENCE.md](EMT_REFERENCE.md):
  - Snail 72;
  - du/dt = 4.2 H(z; 100/9, 3, 0.1) - 0.05 u;
  - dm/dt = (55/24) H(z; 25/9, 2, 15) - 0.5 m;
  - dz/dt = (1/6) m sum_i C(6,i) l_i (u/40)^i/(1 + u/40)^6 - 0.1 z, with l = 1, 0.5, 0.2 and 0.02
    four times.
  - Rates are per BITSEY time unit, taken as 1 s. One scaled unit is 1 uM.
- **Step.** Each coupled run keeps the driver's dt x rate <= 0.04 (§4), with a largest step of
  1/8 s.
  - Every D up to 1.33e-14 m²/s runs at 1/8 s. So the points that decide a threshold near
    BITSEY's share one step; the bound halves it only above that D.
  - The uncoupled stage uses the finest coupled step, the upper end's (1/64 s).
- **Before the search.** Cost probes ran with 2,000 s coupled, not the criterion's 20,000 s. They
  are not search points.
- **Reported.** Cells' threshold and its ratio to BITSEY's logged 7.18e-15 m²/s. Agreement is called
  if the ratio lies within 0.95-1.05. Two engines integrating the same equations with different
  schemes can differ near the switch's separatrix, so the band is set before the run.
  - The log was written by an earlier revision of the code than b2cb370's, with b2cb370's printed
    settings (§2).
  - Descriptive, not judged: Cells' first points (0 and 1e-13 / 2^k) include the first six of the
    log's bisection (0, 1e-13, 5e-14, 2.5e-14, 1.25e-14 and 6.25e-15). Their outcomes, and the end
    states the log dumps, compare point by point.

