# Osmotic water and compliant volumes for the pump-channel family

`resolved_pump_water@1` is `resolved_pump_tissue@3` with osmotic water and compliant
volumes. It is opt-in ([D136](DECISIONS.md)); the default engine is unchanged.
Design: `/mnt/workspaces/Cells/water-volume-pump-20261110-01/design-note-W1.md`.
Status and runs: [Progress](../PROGRESS.md).

Files: `src/cells/core/surface_pump_water_spec.py` (definition),
`src/cells/models/surface_pump_water.py` (model), the law
`src/cells/numerics/osmotic_water.py`, worlds `validation/tissue/pump_water_fixtures.py`.

**Implementation (D143).** `resolved_pump_water@1` and `@2` are thin compositions of the
[composite pump-tissue model](PUMP_COMPOSITE.md): `resolved_pump_composite@1` with the
operator `ideal_osmosis_linear_compliance_water@1` (and, for `@2`,
`k_anion_symport_mass_action@1`). The water law, its Heun half-steps and ledgers and the
route law moved unchanged into `src/cells/models/operators/osmotic_water.py` and
`k_anion_symport.py`; the model modules re-export them. The definition formats, the
step, the checks and the qualified scope below are unchanged. Before the conversion the
composition was bitwise equal to the earlier implementation on the models' test and
qualification worlds, and the compiled steps, right-hand sides and device checks trace
to identical jaxprs (evidence: `/mnt/workspaces/Cells/composite-s1-20261111-01/`).

## Physics

Water crosses each membrane patch by the law `ideal_osmosis_linear_compliance_water@1`
([water reference](WATER_VOLUME_REFERENCE.md)):

```text
Pi = R T (sum of declared amounts + neutral impermeants) / V      ideal van 't Hoff
P  = K (V / Vref - 1) + P0                                       linear compliance
Q  = 1e15 A Lp a (psi_cell - psi_outside),  psi = P - Pi          pL/s, cell to outside
D  = 1e-3 Q (psi_cell - psi_outside) >= 0                        pJ/s
```

`a` is the scheduled water availability of the patch. Lp is the hydraulic
permeability; for an osmotic permeability Pf, Lp = Pf Vw / (R T) (Manning & Kay 2023,
J Gen Physiol 155:e202313332, Eq. 6). Water moves no solute and no charge.

- **Finite nodes** (cells, finite outside nodes) change volume. Every @3 stage — field
  solve and Kirchhoff offsets, membrane, junction and face fluxes, channels, both
  pumps, the implicit drift weights and @3's explicit-stage refusal — uses
  amount / current volume.
- **Held baths** keep their volume and composition, so their water potential
  psi_b = P_b - R T sum(c_b) is fixed. The water a bath exchanges is booked as supply,
  with work 1e-3 psi_b dS.
- **Declared species count once.** Impermeant charged species such as P count through
  their amounts; `impermeant_amount_fmol` adds only *neutral* osmolytes. Fixed-charge
  equivalents carry no particles.

Held fixed: membrane areas and capacitances (so the charge–voltage relation), junction
and face geometry, channel abundance and permeability, pump capacities, topology. Water
crosses membranes only: there is no water on junctions (that would be convection
carrying solute) or on extracellular faces (no semipermeable barrier in free solution).

## Time integration

For the IMEX solvers the step is the Strang splitting
`Phi_dt = W_{dt/2} o I_dt o W_{dt/2}`.

- **I_dt** is @3's own `checked_step`, at the volumes left by the first half, frozen
  over the ionic step. @3's code is called, never copied, so @3's fixes apply here
  unchanged.
- **The optimization barrier.** `jax.lax.optimization_barrier` wraps @3's step,
  inputs and outputs, so XLA compiles it as one unit. It changes the schedule, never
  the arithmetic. Its purpose is bitwise water-off equivalence with @3 under default
  XLA flags (see Equivalence below). Its cost is measured as water-off against @3
  alone on the 825-node world.
- **W_h** advances the volumes at frozen amounts by Heun's method.
- **Why the result is consistent.** The two pieces act on disjoint variables, so:
  - a zero of the full right-hand side is a fixed point of every piece, and so of
    Phi (rhs and step-map stationary states agree);
  - the free energy telescopes exactly over the three pieces;
  - the split is second order with ARS(2,2,2) and first order with Euler.
- **Why water can be explicit.** Water relaxes over about 0.5–85 s for the sourced
  permeabilities; at 1 ms, dt × (water rate) is 1e-5 to 2e-3.
- **RK4** (reference runs) integrates the coupled, unsplit right-hand side.

## Checks and refusal

- **Row checks call @3's own functions.** Host and device use `surface_pump.checked_rows`
  and `surface_pump_checks.row_checks` with @3's balances, magnitudes, bounds and
  dissipation fields, so @3's checks apply unchanged. The energy ledger adds:
  - the dilution at current amounts, −RT N_tot log(V/V0);
  - the exact elastic energy;
  - the water heat, minus the bath water work.
- **Water ledgers**, each with a fixed floor plus the family's per-step rounding
  allowance:
  - cell water: ΔV + Σ transfers = 0;
  - outside water: finite ΔV, or bath supply;
  - total water;
  - bath work: B − 1e-3 psi_b S = 0.
- **Refusal (the step is refused; nothing is clipped or repaired):**
  - any volume reaching its declared bound, at any water stage or step end;
  - dt × (water relaxation rate) above 0.05 at the definition or at a water stage;
  - a water availability outside [0, 1];
  - @3's face, junction and calcium explicit bounds exceeded with every compliant node
    at its minimum volume.

  A run that reaches a volume bound stops. Drivers report it as a lysis or collapse
  censor.

## Parameters (approved heredity water-arm set)

Marks:
- **V(pdf):** read in the PDF text.
- **V(sum):** full text via a fetch summary.
- **Abs:** abstract only.
- **Der:** derived here.

| Parameter | Value | Source and mark |
| --- | --- | --- |
| Pf, no aquaporins (default) | 3e-3 cm/s at 310 K (Lp 2.1e-13 m/(Pa s)) | Cells without aquaporins measure (0.5–7)e-3 cm/s at 10–25 °C: CHO 1.2e-3, MDCK 1.1–2.4e-3 (Farinas et al. 1997, J Gen Physiol 110:283, V(sum)); AQP1-null RBC 1.9e-3 (Yang & Verkman 2002, J Biol Chem 277:36782, Abs); AQP4-null astrocytes ~7e-3 (Solenov et al. 2004, Am J Physiol Cell Physiol 286:C426, Abs/Der); lymphocytes ~1e-3 (Hempling et al. 1977, J Cell Physiol 93:293, Abs/Der). Scaled to 37 °C by the lipid-path activation energy, ×2.4–2.9 (Der) |
| Pf, aquaporin arm | 0.03–0.08 cm/s at 310 K | RBC 0.020 (Mlekoday et al. 1983, J Gen Physiol 81:213, Abs); astrocytes 0.05 at 23 °C (Solenov 2004, Abs); ×1.5 to 37 °C at Ea 5.5 kcal/mol (Der) |
| Modulus K | 60 Pa (arm: 0) | Elastic cortex K = (4/3) E h / R with E h ≈ 240 Pa µm (Tinevez et al. 2009, PNAS 106:18581, V(pdf)) and R 5.6 µm (Der) |
| Pressure offset P0 | 40 Pa (arm: 0) | Interphase HeLa ΔP = 40 ± 30 Pa (Fischer-Friedrich et al. 2014, Sci Rep 4:6213, V(sum)). These pressures are 1e-4 to 1e-3 of Π, so animal cells are effectively Boyle–van 't Hoff osmometers |
| Vmax | 2 V0 | Swelling below 2× is taken up by shape change and membrane reserves; rupture comes at 4.4–10.7× (Groulx et al. 2006, J Membr Biol 214:43, Abs). This is the validity range of fixed area and capacitance, not a lysis prediction |
| Vmin | 0.5 V0 of solvent volume | A declared validity choice for the ideal-solution law, not a literature value. Osmotically inactive fractions are 0.43 in RBC (Savitz et al. 1964, J Gen Physiol 48:79, V(sum), Der) and 0.32 in lymphocytes (Hempling 1977, Abs) |
| Impermeants | The P species (135 mM, z −1, BETSE default); neutral 0. Arm: P at 100 mM | About 100 of ~290 mOsm/L, mean z from −2 to −0.7 (Kay & Blaustein 2019, J Gen Physiol 151:407, V(sum); Kay 2017, Front Cell Dev Biol 5:41, V(sum)) |
| Bath pressure | 0 Pa | Gauge |

## Stationary analysis

`stationary_continuation_analysis@1` supports the model.

- **Slow mode:** the volumes of cells and finite outside nodes are dynamical
  coordinates, in units of 1e-3 of the declared volume. A set of compliant nodes joined
  by open water routes without a bath has a closed-volume law. Cells facing held baths
  have none.
- **Fast mode** freezes the volumes with the composition.
- **New continuation parameters:** `water_availability` and
  `hydraulic_permeability_scale`.
- **Existing models** (no volume fields) keep exactly their blocks and laws.
- **The stationary identity.** At a stationary state of an isolated cell, or a uniform
  sheet, whose anion M has passive routes only, M is at Nernst. Electroneutrality plus
  osmotic balance then give

  `V = (N_P + (I + q/F − X)/2) / ((c_b + ΔP/RT)/2 − M_b exp(F Vm/RT))`

  so the stationary volume follows from Vm alone. Depolarized states swell. Only a route
  that moves M off its Nernst distribution, or a change in impermeant content, regulates
  volume.

## Equivalence with resolved_pump_tissue@3

With water declared and every route closed (availability 0, or Lp 0), the full split
code runs with exact zero flows. Every @3 state field, observation and check
diagnostic then equals @3's run bitwise. This holds:
- compiled with default XLA flags;
- uncompiled;
- in vmap batches;

on the heredity cell (H and D) and the seven-cell gated sheet
(`tests/unit/test_surface_pump_water_equivalence.py`). The 825-node world is checked
by the detached driver `validation/tissue/pump_water_equivalence.py`; its result is
recorded with the run evidence.

The row checks give @3's verdicts and messages on the host and the device for injected
junction-heat, ledger and domain faults.

**Why the optimization barrier is needed.** Without it, default-flag compilation fused
the water arithmetic into @3's step differently, and `channel_dissipated_energy_pJ`
differed by about 1 ulp. That field was bitwise again with XLA's algsimp and fusion
passes disabled, and it is bitwise with the barrier.

## resolved_pump_water@2: one volume-regulation route (KCC-type)

`resolved_pump_water@2` is `resolved_pump_water@1` plus KCC-type K⁺/anion symport
routes. Files: `src/cells/core/surface_pump_water_v2_spec.py`,
`src/cells/models/surface_pump_water_v2.py`, and the law in
`src/cells/processes/k_anion_symport.py`.

**The law, `k_anion_symport_mass_action@1`.** One route per declared membrane:

```text
J = k a f(V) (K_i A_i - K_o A_o)        outward cycles, fmol/s; one K+ and one anion each
f(V) = exp[(V - V_set) / (s V_set)]     exponential_volume_activation@1
heat = 1e-3 J R T ln(K_i A_i / (K_o A_o)) >= 0
```

- Roles are named in the definition. In the heredity world they are K and M (the Cl⁻
  surrogate).
- The route carries no current.
- It is given to @3's opt-in membrane-process hook (`surface_pump_v3.MembraneProcess`),
  so it is one more explicit membrane term at every @3 stage, in readouts and in rhs.
- @3 returns the applied transfer and the trapezoid heat, which this model books in
  `symport_cycles_fmol` and `symport_dissipated_energy_pJ`. Material ledgers include
  the transfers, the energy ledger includes the heat, and dissipation includes the
  heat field.
- With no route declared, the step is `resolved_pump_water@1`'s exactly.
- Stationary states stay exact fixed points of the split step: the route moves amounts
  inside @3's step, and water acts on volumes only.

**Sources** (marks: FT full text, FT-img equation image, ABS abstract, Der derived):
- Mass action with an exponential volume factor and s = 1: Lew, Freeman, Ortiz &
  Bookchin 1991, J Clin Invest 87:100 (FT-img).
- s ≈ 0.12: matches the 4–5× K⁺ flux at relative volume 1.2 of Kaji 1986, J Gen
  Physiol 88:719 (ABS, Der).
- 1:1 stoichiometry: Jennings & Adame 2001, Am J Physiol Cell Physiol 281:C825 (ABS).
- Capacity default, the red-cell range 4–20 mmol/(L cells·h) of K:Cl efflux at Lew's
  reference product difference. These are reticulocyte-rich and young-cell data:
  Brugnara 1986/1987 quoted in Lew 1991 (FT), and Canessa et al. 1987, J Membr Biol
  97:97 (ABS). They are not normal mature red cells.
- Neuron-scale arm, model-derived: Staley & Proctor 1999, J Physiol 519:693 (ABS).
- Block arm: VU0463271 as the selective availability schedule (IC50 61 nM, >100-fold
  over NKCC1; Delpire et al. 2012, Bioorg Med Chem Lett 22:4532, ABS). DIOA is
  non-selective: it also inhibits the Na,K- and H,K-ATPases.

**Limits of the route:**
- Activation is instantaneous. The ~10 min activation lag of red-cell KCC
  (Jennings & al-Rohil 1990, J Gen Physiol 95:1021, ABS) is not modelled.
- The law reverses at the 1:1 equilibrium. Delpire & Lauf 1991 (J Gen Physiol 97:173,
  ABS) report net efflux persisting until the outside product is about 2× the inside
  one.
- No pH, Mg or phosphorylation state.

## Limits

- **Qualified scope: held-bath worlds only.** In W225 every patch faces a *finite*
  extracellular square and none faces the reservoir ring, so cell plus square water is
  closed. A swelling disc would drain its squares toward Vmin. The confined-ECS
  approximation (finite squares with a declared compliance) is accepted by the model
  but is not qualified. ECS bulk flow with solute convection is later work (W3).
- **Not modelled:**
  - membrane-reserve unfolding (area and capacitance growth);
  - ECS geometry change;
  - solvent drag;
  - solute partial volumes;
  - non-ideal activities;
  - volume regulation, other than the one KCC-type route of resolved_pump_water@2;
  - a temperature law for Lp.
- **Calibration and BETSE.** Parameters are literature ranges for generic animal cells,
  not a calibration to one cell type. BETSE v1.5.0 has no active volume update, so it
  provides no reference trajectory.
