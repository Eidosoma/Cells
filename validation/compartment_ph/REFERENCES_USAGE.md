# Using FR-4's compartment-pH references: R-closure and R-kinetic (interface only)

How to run the independent references for FR-4's buffered compartment acidification and read their
outputs without reading their source.
- **Sources:** [COMPARTMENT_PH_TRANSFER_DESIGN.md](../../docs/COMPARTMENT_PH_TRANSFER_DESIGN.md),
  its equations and appendices only: §2–§4 (the closure, the registry's pK, §4.2's envelope and
  budget), §5.1, §6 (the pump), §7.1 (the constant field), §13 and §13.1 (the worlds), and
  Appendix A with A.2 (full protonation kinetics).
- **Not read:** the engine (`src/`), its tests and fixtures, other agents' worktrees and the Syn3A
  probes' records.
- **Not blind:** §13.1 quotes values that were read before the runs: Δ_rG'_ATP ≈ −51.4 kJ/mol;
  the negative control's V_b ≈ −0.266 V and stall of about 0.06 pH units; β ≈ 5.1 mM/pH; a
  steady lumen pH ≈ 5 (§4.2); and the counterion's "1.6 pA at about 8 mV".
- **Readings** are listed below; disagreements go to the lead.

| Module | What it gives |
| --- | --- |
| `validation/compartment_ph/ph_reference.py` (`ph`) | R-closure (Appendix A, the rapid-buffer closure) and R-kinetic (A.2, each buffer's protonation resolved), on the two-node world with the pump, the proton leak, constant-field ions, charge and the energy identity |
| `validation/compartment_ph/ph_crosschecks.py` | The driver behind the measured numbers below (`--out DIR`; about 30 s of CPU) |

**Self-tests:** `tests/unit/test_compartment_ph_references.py`, 8 tests, tier 1, 13.7 s on a shared
CPU 0. They also check that nothing here imports `cells` or `validation.tissue`. The one import from another reference
is `validation.coupling.piecewise_ode`.

## The world and its conventions

- **Two nodes:** the owner's cytosol c and a lumped lumen L, joined by the bounding patch (area
  A_b, capacitance C_b). The owner faces a held bath through an impermeant plasma patch of
  capacitance C_p, so the bath enters only as the potential's zero.
- **Units:** fmol, pL, mM (= fmol/pL), s, V and pJ; free energies in J/mol. **The constants are
  inputs** (`ph.Constants(F, R, T)`, with c° = 1000 mM).
- **Signs:** every flux is positive from c to L. V_b = φ_c − φ_L = −q_L/C_b and
  φ_c = (q_c + q_L)/C_p, with q = 1e-15 F (fixed + Σ z n). Each node's fixed charge makes it start
  at q = 0 (§13).
- **The pK from the registry (§4.1):** K = c° exp(δμ), δμ = (μ°(HB) − μ°(B) − μ°(H⁺))/RT;
  pH = −log10(h/c°).
- **The closure (Appendix A):** the state per node is H_eq (free plus bound protons); h solves
  h + Σ_k B̄_k h/(h + K_k) = H̄_eq.
- **The kinetics (A.2):** the state per node is the free n_H and each buffer's n_HB and n_B, with
  r_k = k_off a_k − k_on h b_k and k_off = k_on K_k. The start is the equilibrium speciation at
  pH₀, so both references start from the same state.
- **The pump (§6):**
  - ΔG_cyc = Δ_rG'_ATP + n [RT ln(h_L/h_c) − F V_b], with Δ_rG'_ATP from the held fuel;
  - S = [1 + (K_H/h_c)^n]⁻¹ [1 + K_ATP/c_ATP]⁻¹;
  - J_cyc = k a S (1 − e^(ΔG_cyc/RT)), moving n H⁺ from c to L per cycle.
- **Routes (§7.1):** the constant field for each permeant ion, and for the proton leak on free h.
- **Energy (Appendix A):** ΔG_stored + Q = W, with W = ∫ (−Δ_rG'_ATP) J_cyc dt.
  - Q holds the pump's −ΔG_cyc J_cyc, each route's J Δμ̃ and, in R-kinetic, the reaction heat
    −Σ_k V r_k ΔG_k.
  - The reaction heat is also kept apart (`reaction_heat_pJ`), so A.2's vanishing limit can be read.

## Building and running

```python
from validation.compartment_ph import ph_reference as ph

w = ph.acceptance_world()  # §13.1; ph.acceptance_world(P_K=0.0) is the negative control
clo = ph.integrate(w, 900.0, record=ts)                # R-closure
kin = ph.integrate(w, 900.0, record=ts, kinetic=True)  # R-kinetic at the buffers' k_on (1e7)
k3 = ph.integrate(w, 900.0, record=ts, kinetic=True, k_on=(1e3, 1e3))  # (cytosol, lumen)
out = ph.integrate(w, 900.0, record=ts, kinetic=True, k_on=(None, 1e-3))  # the outside case
```

- **Your own world:** `ph.World(constants, cytosol=ph.Node(volume_pL, pH0, ions_mM, buffers),
  lumen=..., patch_area_m2, patch_capacitance_F, plasma_capacitance_F, permeability_m_s={"K": P},
  proton_permeability_m_s, pump=ph.Pump(...))`, with
  `ph.Buffer(total_mM, base_valence, delta_mu0_RT, k_on_per_mM_per_s)`.
- **Integration:** Radau at rtol 1e-11 (Appendix A). Each state's atol is rtol × 1e-6 × its own
  scale. `run.steps` counts the solver's steps.
- **The closure's algebra:** `ph.free_proton(Heq_mM, [(B_mM, K_mM), ...], c0)` and
  `ph.buffer_capacity(h, pairs)`.

| Key of `run.at[t]` | Meaning |
| --- | --- |
| `pH_c`, `pH_L`, `h_c`, `h_L` | pH, and free h (mM) |
| `Heq_c`, `Heq_L` | Proton equivalents, free plus bound (fmol) |
| `ions_c`, `ions_L` | Ion amounts (fmol) |
| `Vb`, `phi_c` | The patch's and the owner's potentials (V) |
| `J_cyc`, `J_H`, `J_ions`, `dG_cyc` | The pump's cycle rate, the leak and each ion's flux (fmol/s, c to L), and ΔG_cyc (J/mol) |
| `cycles` | Cycles completed (fmol) |
| `work_pJ`, `heat_pJ`, `reaction_heat_pJ` | W; Q; R-kinetic's share of Q (0 in R-closure) |
| `stored_change_pJ`, `energy_residual_pJ` | ΔG_stored, and ΔG_stored + Q − W |
| `envelope_ratio`, `buffer_capacity` | λ/ρ per node at the run's k_on (§4.2), and β per node (mM per pH unit) |

## Measured (`compartment-ph-crosschecks-02`, from snapshot `compartment-ph-snapshot-02`)

§13.1's world over 900 s, with 209 records: log-spaced from 1 µs, and every 10 s.

### 1. Acidification against a gradient, with the K⁺ counterion and held fuel

| At 900 s | R-closure | R-kinetic (k_on = 1e7 mM⁻¹ s⁻¹) |
| --- | --- | --- |
| Lumen pH (from 7.2) | 5.0960061 | 5.0960061 |
| Cytosol pH; largest \|pH_c − 7.2\| | 7.2180; 0.0180 (the band is 0.05) | the same |
| V_b; its extreme | −7.334 mV; −7.675 mV | the same |
| Cycles; K⁺ moved into the cytosol | 1.97484 fmol; 2.17218 fmol | the same to 5e-8 relative |
| ΔG_cyc; net H⁺ flux | −24.80 kJ/mol; 1.35e-5 fmol/s (nearly steady) | the same |
| W; Q; the reaction heat | 101.522 pJ; 86.028 pJ; 0 | the same; the same; 3.17e-6 pJ |
| Largest energy residual \|ΔG_stored + Q − W\| | 8.4e-12 pJ | 2.2e-11 pJ |
| Solver steps | 1,222 | 1,599 |

### 2. Convergence to the closure as k_on grows

| k_on (mM⁻¹ s⁻¹) | 1e3 | 1e5 | 1e7 |
| --- | --- | --- | --- |
| Lumen: largest \|pH_kinetic − pH_closure\|, at | **1.259e-2**, 0.36 ms | 1.279e-4, 4.8 µs | 1.279e-6, 1 µs |
| Lumen: largest after 10 s | **9.60e-3** | 9.72e-5 | 9.72e-7 |
| Cytosol: largest; after 10 s | 3.01e-4; 2.99e-4 | 3.01e-6; 2.99e-6 | 3.01e-8; 2.99e-8 |
| The first-order term at the lumen's peak | 1.241e-2 | 1.2785e-4 | 1.27888e-6 |
| Local lag over the first-order term (lumen, 169 records from 1 ms) | 1.000007 to 1.0146 | 1.0000001 to 1.00015 | 0.999998 to 1.000006 |
| Flux errors: J_cyc; J_H; J_K; net H⁺ | 9.9e-4; **2.0e-3**; **1.7e-3**; **1.7e-3** | 9.9e-6; 2.0e-5; 1.7e-5; 1.7e-5 | 9.9e-8; 2.0e-7; 1.7e-7; 1.7e-7 |
| The reaction heat at 900 s | 3.15e-2 pJ | 3.17e-4 pJ | 3.17e-6 pJ |
| §4.2's λ/ρ, lumen, smallest | 1.2e6 | 1.2e8 | 1.2e10 |
| Within the 1e-3 pH budget | **no** | yes | yes |

- **First order in 1/k_on:** the lumen's peak falls by 98.5 and 99.98 per factor of 100. The
  reaction heat falls as 1/k_on: A.2's limit, where it vanishes.
- **The first-order term** is (ρ/λ)(β/ln 10 − h)/(h ln 10) (see Reading 1).
  - It is read from the kinetic run's own state.
  - At 1e3 the ratio's 1.5% is the logarithm's curvature, about ln 10 · ΔpH/2.
- **The local lag** is pH_kinetic against the closure's pH at the kinetic run's own H_eq. Unlike the
  difference of two runs, it does not carry their drift apart.
- **Flux errors** are the largest |J_kinetic − J_closure| over the run's largest |J_closure|. This
  is my reading of the budget's "H_eq-weighted fluxes, at 1e-3 relative". J_H starts at 0, so a
  ratio at each time is unusable.

### 3. The outside case: the lumen's k_on at 1e-3 mM⁻¹ s⁻¹

- **The lumen** lags the closure by up to **2.175 pH units** (at 0.74 s): the comparison fails, as
  §4.2 requires.
- **§4.2's λ/ρ** in the lumen is as low as 1.20 in the closure run (1.20 in the kinetic run), against
  the required 1e3. The envelope check flags it.
- **The cytosol** keeps k_on = 1e7, yet differs from the closure run by up to 0.018 pH (at 870 s),
  through the shared pump and leak.
- **The energy identity** still holds, to 1.3e-11 pJ, with a reaction heat of 0.27 pJ.

### 4. The negative control, P_K = 0

| At 900 s | R-closure | R-kinetic (1e7) |
| --- | --- | --- |
| Lumen pH; the stall | 7.140427; **0.0596 pH units** | the same; the kinetic lag ≤ 1.28e-6 |
| V_b; ΔG_cyc | −0.26171 V; −196 J/mol (near static head) | the same |
| Cycles; K⁺ moved | 0.16059 fmol; 0 | the same |
| Energy residual | 1.0e-11 pJ | 9.2e-12 pJ |

**The route's effect:** pH_L(P_K = 0) − pH_L(with K⁺) = 2.044 pH units at 900 s, 2,044 times the
budget.

### 5. The window between §4.2's envelope and the budget, in this world

- **The envelope check:** λ/ρ is smallest in the lumen, 1.2019e10 at 1e7. λ is proportional to
  k_on at a fixed state, so the check passes from **k_on ≈ 0.83 mM⁻¹ s⁻¹**.
- **The budget:** the lag is first order in 1/k_on, so the budget holds from **k_on ≈ 1.28e4
  mM⁻¹ s⁻¹**.
- **So the check admits** four orders of magnitude of k_on at which the closure misses the budget.

### The floor

Radau at rtol 1e-11 against 1e-12: lumen pH within 5.2e-14 (R-closure) and 7.1e-15 (R-kinetic).
This is far below every difference above.

## Readings and findings, for the lead

1. **§4.2's envelope does not imply its budget.**
   - **What the runs show:** at k_on = 1e3 the envelope holds by a factor of about 1.2e3 (λ/ρ ≥
     1.2e6). Yet the lumen lags by 1.26e-2 pH units at 0.36 ms, and still by 9.6e-3 after 10 s.
     The flux errors exceed 1e-3 relative too.
   - **Why:** the free protons exceed the closure's h by about (dH̄_eq/dt)/λ times the bound share.
     This is derived here from A.2, as a quasi-steady expansion in 1/λ; Keener and Sneyd (2009,
     ch. 7) give the rapid-buffer approximation it corrects. In pH units:

         |ΔpH| ≈ (ρ/λ) · (β/ln 10 − h) / (h ln 10)

     The runs confirm this to 2e-4 at the peak (k_on ≥ 1e5), and as a local lag throughout.
   - **The size of the gap:** §4.2 puts the error "of order ρ/λ". It is larger by
     (β/ln 10 − h)/(h ln 10), the ratio of bound to free buffering over ln 10. That is about
     1.5e4 at the lumen's start (pH 7.2 against pK 6) and about 210 at pH 5.1.
   - **What is unaffected:** the declared inside cases (1e5 and 1e7) and the outside case.
   - **What I give:** the expression and the numbers, not a replacement threshold, because the
     factor depends on the state.
2. **The early ρ.**
   - The note's "ρ ≈ 0.1 s⁻¹ (0.25 mM/s pumped)" takes the pump at its capacity. So does "the
     pump's 1.6 pA".
   - §6's saturation at pH_c 7.2 is S = [1 + (K_H/h_c)²]⁻¹ [1 + K_ATP/c_ATP]⁻¹ ≈ 0.276.
   - So the reference's early ρ is 0.031 s⁻¹, and the outside case's λ/ρ is 1.2 rather than about
     0.4. It is still out by orders of magnitude.
3. **The outside case** lowers only the lumen buffer's k_on, as §4.2 declares; the cytosol's stays
   at 1e7.
4. **The start** is the equilibrium speciation at pH₀ (A.2), so both references start from the same
   state, and the kinetic lag builds within a few 1/λ.
5. **The flux clause** is read as the largest difference over the run's largest closure flux (§2
   above).

## Not built

- **FR-5's references:** cargo, damage, leak, reseal and pH-conditioned transfer.
- **Item 4:** the finite-fuel reference (a reaction feeding shared ATP, ADP and Pi to the pump).
- **Several lumen compartments:** §13 lumps them into one node, as here.

## Evidence

`/mnt/workspaces/Cells/independent-references-20261115-01/` (HANDOFF.md): `compartment-ph-crosschecks-02/`,
the record, from snapshot `compartment-ph-snapshot-02` (95f835fb).
- **Run 01** (snapshot 01, ff728f99) is kept. It gave the same numbers for §1, §3, §4 and the
  convergence peaks (the energy residuals differ in rounding), without the per-node items, the
  window, the flux errors and the reaction heat.
- **Provenance:** the driver ran from a snapshot folder, not a checkout, so the snapshot's
  SNAPSHOT.json carries the revision.

# FR-5: R-transfer, damage, leak and reseal, and pH-conditioned transfer

- **Sources:** the same note's §8 (the routing door's factors), §9 (FR-5's laws), §13.2 (the world)
  and Appendix A (FR-5's states, fluxes and energy identity).
- **Not blind:** §13.2's claims, under "What it shows", were read before the runs. The note quotes
  no FR-5 results.

| Module | What it gives |
| --- | --- |
| `validation/compartment_ph/transfer_reference.py` (`tr`) | R-transfer: FR-4's R-closure with cargo X, the damage pore and the conditioned transfer; the exact damage law; the steady start |
| `validation/compartment_ph/transfer_crosschecks.py` | The driver behind the numbers below (`--out DIR`; about 70 s of CPU) |

**Self-tests:** `tests/unit/test_compartment_transfer_references.py`, 6 tests, tier 1. The folder's
independence tests cover this module too.

## The laws, as the reference computes them

- **Damage** (§9) is exact on each constant piece of its schedules:
  d(t) = d_k e^(−s τ) + (a/s)(1 − e^(−s τ)), with a = k_inj u_inj, b = k_res u_res, s = a + b and
  τ = t − t_k. Both terms are non-negative. The schedules' breakpoints are integration segment
  ends.
- **The proton leak with damage** (Appendix A): J_H = 1e15 (P_H + d P_pore,H) A_b ψ(u)
  (h_c − h_L e^(−u)). The pore's share is its own route (`J_H_pore`), with its own heat.
- **Cargo X** (z = 0): each route carries J_r = 1e15 m_r P_r A_b (c_X,c − c_X,L).
  - m_r is §8's `multiply`: 1, f(pH_L), d, or f(pH_L)·d.
  - It is evaluated on the state at every time (the stage form).
  - f(pH) = 1/(1 + 10^(m (pH − pH₅₀))). It is computed without overflow at any pH.
- **Energy:** ΔG_stored + Q = W.
  - G_stored adds n_X RT (ln(c_X/c°) − 1) at each node to FR-4's.
  - Each route's heat J Δμ̃ and amount are kept apart (`heat_by_route_pJ`, `moved_fmol`).
- **The start** (§13.2): FR-4's world at its steady state, here R-closure at 3600 s, plus X at 1 mM
  in the lumen and 1e-4 mM in the cytosol.
  - The fixed charges stay FR-4's (§13).
  - To compare with the engine, pass its checkpoint as `tr.Start(Heq_fmol, ions_fmol, X_fmol)`.

```python
from validation.compartment_ph import transfer_reference as tr

start, steady = tr.steady_start()                 # FR-4 at 3600 s, plus X
run = tr.integrate(tr.acceptance_world(start=start), 900.0, record=ts)
f1 = tr.acceptance_world(start=start, conditioned=False)  # the control f = 1
d0 = tr.acceptance_world(start=start, damaged=False)      # the control d = 0
```

`run.at[t]` holds FR-4's keys, plus:
- `X_c`, `X_L` (fmol) and `cX_c`, `cX_L` (mM);
- `d`, `f`, `J_H_pore` and `J_X` {route};
- `heat_by_route_pJ` {pump, leak_H, pore_H, ion_K, X_route};
- `moved_fmol` {H_pore, X_route}, from c to L since the start.

## Measured (`compartment-transfer-crosschecks-01`, from snapshot `compartment-transfer-snapshot-01`)

§13.2's world over 900 s, with 199 records (log-spaced to 100 s, every 0.5 s on [100, 140] s, then
every 10 s).

**The start** (FR-4 at 3600 s):
- pH_L 5.0946273, pH_c 7.2180313 and V_b −7.330 mV;
- net H⁺ flux −2.1e-16 fmol/s, J_K −4.9e-15 fmol/s;
- pH_L moved by 4.9e-10 since 1800 s.

| The declared world | Result |
| --- | --- |
| X while the lumen is acidic (f = 0.977) | X crosses at once, with a time constant of 8.4 s. c_X,L is 0.89 mM at 1 s, 0.31 at 10 s, and 0.0155 at 99.5 s, where the gradient is 7.2e-6 of the start's |
| Damage (d = 0.99995 at 110 s) | The pore moves 0.162 fmol of H⁺ out of the lumen. pH_L rises from 5.0946 to a peak of **5.238** at 138 s; f falls only to **0.918** |
| The pore's release of X | 4.2e-7 fmol, **6.4e-6 of the lumen's start**: X has already crossed |
| Resealing | The pump re-acidifies: pH_L within 0.01 of the start by 350 s and within 0.001 by 490 s; 5.094628 at 900 s |
| Heat by route at 900 s (pJ) | Pump 48.55, leak 49.10, pore 2.03, K⁺ 0.023, X transfer 0.698, X pore 2.3e-10 |
| W; Q; cycles | 99.71 pJ; 100.41 pJ (X's relaxation releases stored energy); 1.940 fmol |
| Energy residual; material drift (H_eq, X, K); φ_c | ≤ 8.0e-12 pJ; ≤ 1.1e-15, 1.7e-15 and 2.9e-15 relative; ≤ 1.8e-11 V |
| Floor (rtol 1e-11 against 1e-12) | pH_L within 5.5e-14, c_X,L within 1.6e-15 mM |

| Negative control | Against the declared run |
| --- | --- |
| f ≡ 1 | X: up to **8.5e-3 mM** in the lumen (at 9.4 s), from f's 2.3% at the start. pH: 8.9e-15 |
| d ≡ 0 | pH_L: up to **0.144** (at 138 s), the damage's proton leak. X: up to **5.9e-6 mM** (at 101 s), with no burst in either run |

## Finding for the lead: §13.2's world does not show two of its four claims

- **"X crosses while the lumen is acidic, and not when it is not":** only the first half holds.
  The lumen never stops being acidic (pH ≤ 5.24 against pH₅₀ 5.5), so the condition never closes.
- **"Damage opens a proton leak that raises the lumen's pH and releases X":** the pH rises, but
  only by 0.14. No X is released: 6.4e-6 of the start.
- **Why:**
  - At P_X = 1e-8 m/s across the lumen's area-to-volume ratio, X relaxes with a time constant of
    8.4 s. Its gradient is below 1% of the start's by 40 s, long before the damage at 100 s.
  - P_pore,H = 1e-6 m/s only raises the leak's permeability 2.7-fold.
- **The negative controls therefore test little:**
  - d ≡ 0 differs in pH (0.144) but not in X (5.9e-6 mM);
  - f ≡ 1 differs by f's 2.3% at the start.
- **What would show the claims** (the driver's grid, to 300 s, energy residuals ≤ 2.1e-11 pJ):

| P_X (m/s) | X left in the lumen at 99.5 s | X released by the pore by 300 s |
| --- | --- | --- |
| 1e-8 (declared) | 1.5% | 6.4e-6 |
| 1e-10 | 89% | 87% |
| 1e-11 | 98.8% | 97% |

| P_pore,H (m/s) | Peak pH_L | Smallest f |
| --- | --- | --- |
| 1e-6 (declared) | 5.24 | 0.918 |
| 1e-5 | 5.64 | 0.208 |
| 1e-4 | 6.28 | 7.6e-4 |

  So a release burst needs P_X ≲ 1e-10 m/s, and closing the condition needs P_pore,H ≳ 1e-4 m/s.
  The choice is the owner's. The reference runs any of them.

## Readings

- **The start:** "a saved checkpoint and a declared start" is read as FR-4's steady state. The
  reference computes its own; pass the engine's checkpoint for a comparison.
- **The pore's proton heat** is booked apart from the leak's (each route its own heat, §9). Their
  sum is Appendix A's single J_H term.
- **The transfer route is not scaled by d,** as in Appendix A's J_X, and §13.2 declares no f·d
  route. The reference supports f·d (`CargoRoute(conditioned=True, damaged=True)`), and its
  self-test checks it.

# Finite fuel (item 4): the reference's specification, proposed before it is built

No engine note specifies the finite-fuel case yet, so this section declares what its reference
will compute. It is a proposal for the lead to confirm, from:
- ARCHITECTURE.md's "Material identity and fuel" (F2, and "the first case");
- D176, decisions 1 and 2;
- D152's §2.2 (the passive reaction law);
- this note's §5 and §6.

## The world: one fixed volume, closed

- **Nodes:** the cell c, which is the fuel node, with volume V_c; and a store s (V_s), across one
  patch of area A. There is no bath term, water or division.
- **Rows:** all are neutral, with potentials transformed at the cell's pH_ref and pMg_ref (§5.2).
  - ATP, ADP and Pi, a donor D and its product P, at c;
  - the pumped solute Y, at c and s.
- **One authority:** each row's μ°'/RT. The reaction and the pump both read it.

## The laws

- **The regeneration reaction** at c: D + ADP + Pi ⇌ P + ATP, by D152's
  `ideal_detailed_balance_mass_action@1`:

      v = m(t) V_c c° k_f [a_D a_ADP a_Pi − e^(Δ_rG'°_reg/RT) a_P a_ATP],   a = c/c°

  - Δ_rG'°_reg = μ°'(P) + μ°'(ATP) − μ°'(D) − μ°'(ADP) − μ°'(Pi).
  - m(t) ∈ [0, 1] is a declared schedule.
  - Its heat, −Δ_rG_reg v, is never negative.
- **The pump,** §6's form with Y in place of H⁺ and no voltage term. Per cycle it hydrolyses one
  ATP to ADP + Pi at c, and moves n Y from c to s:
  - ΔG_cyc = Δ_rG'_ATP + n RT ln(c_Y,s/c_Y,c);
  - Δ_rG'_ATP = Δ_rG'°_hyd + RT ln(c_ADP c_Pi/(c_ATP c°)), with Δ_rG'°_hyd = μ°'(ADP) + μ°'(Pi)
    − μ°'(ATP);
  - J_cyc = k a S (1 − e^(ΔG_cyc/RT)), with S = [1 + (K_Y/c_Y,c)^n]⁻¹ [1 + K_ATP/c_ATP]⁻¹;
  - its heat is −ΔG_cyc J_cyc.
- **The leak of Y:** J_Y = 1e15 P_Y A (c_Y,s − c_Y,c), from s to c (Fick's law at z = 0). Its heat
  is J_Y RT ln(c_Y,s/c_Y,c).

## Accounting

- **Moieties:** ATP + ADP (adenine), ATP + Pi (phosphate), D + P (the donor) and Y are each
  conserved, by both the reaction and the pump.
- **Energy, with finite fuel:** ΔG_stored + Q = 0, with G_stored = Σ n (μ°' + RT (ln(c/c°) − 1))
  over every row.
- **Energy, with held fuel:** ATP, ADP and Pi are held (§5.1), and ΔG_stored + Q = W, with
  W = ∫ (−Δ_rG'_ATP) J_cyc dt.

## The runs

1. **Depletion and recovery.** The regeneration runs, then stops (m = 0 on a declared window),
   then runs again.
   - While it is stopped, ATP falls and ADP and Pi rise. So Δ_rG'_ATP and S fall, J_cyc falls,
     and Y's gradient decays.
   - When it runs again, the fuel and the pump recover.
2. **Against held fuel:** the same world with ATP, ADP and Pi held, where nothing depletes.
3. **The negative control:** m ≡ 1, with no depletion window.

## Why not FR-4's proton pump

§5.2 refuses finite fuel at a node with a dynamic proton row in version 1, because regeneration's
protons would need explicit booking. The first case therefore moves a neutral solute. When §5.2's
boundary is designed, the same reference extends to the proton pump with the cell's H row.

## Generic numbers, to be confirmed

| Quantity | Value |
| --- | --- |
| Volumes and patch area | V_c 4.18879 pL, V_s 6.54498e-2 pL, A 7.85398e-10 m² |
| Starting rows (mM) | ATP 3, ADP 0.3, Pi 3, D 30, P 3; Y 10 on both sides |
| Standard terms | Δ_rG'°_hyd −30.5 kJ/mol; μ°'(D) − μ°'(P) = 60 kJ/mol, so Δ_rG'°_reg = −29.5 kJ/mol |
| The pump | k 0.05 fmol/s, n 1, K_Y 1 mM, K_ATP 0.1 mM, a = 1 |
| The leak | P_Y 1e-9 m/s |
| The reaction | k_f 1e3 s⁻¹ (about 0.1 fmol/s forward at the start, above the pump's demand) |
| The depletion window | m = 0 on [100, 300) s; the run lasts 900 s |
