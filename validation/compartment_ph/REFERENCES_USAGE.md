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

### K2(b): the self-consistent reversed pump, against J4 (D176's G3)

- **The control:** fr4_acidification_v1's `controls.K2_planted_sign` (branch fr45-physics,
  e71f1200). It is the declared world with its pump's two sides exchanged in the law:
  `ph.acceptance_world(reversed_pump=True)`, that is `Pump(reversed_sides=True)`.
  - A forward cycle moves n H⁺ from the lumen to the cytosol.
  - ΔG_cyc = Δ_rG'_ATP + n [RT ln(h_c/h_L) + F V_b], with S saturating on h_L.
  - The fuel stays at the cytosol, and the work and heat are as declared.
  - Every use of the pump's protons reads its signed flux, `J_H_pump` (c to L).
- **The run:** `compartment-k2b-crosschecks-01`, from snapshot `compartment-k2b-snapshot-01`
  (cdc84042), with the protocol file copied beside it as the input. Both worlds run over 900 s at
  the protocol's records (901 rows, every 1 s), by R-closure at rtol 1e-11. It took 23 s of CPU.

| | Lumen | Cytosol |
| --- | --- | --- |
| The effect, max over the records of \|pH(K2b) − pH(declared)\| | **3.276** (at 900 s: 8.372 against 5.096) | 0.0192 (at 900 s) |
| First record ≥ J4's budget (1e-3) | **1 s** (0.0269 there) | 16 s |
| First record ≥ K2's catch threshold (2e-3) | **1 s** | 35 s |

- **Beside it, at 900 s, K2(b) against declared:**
  - V_b: +0.42 mV against −7.33 mV;
  - the lumen's K⁺: 9.307 fmol against 6.991 (it gains K⁺);
  - the pump's cycles: 0.084 fmol against 1.975. The reversed pump stalls as h_L falls, through
    S on h_L.
- **K2(b)'s own ledgers close:**
  - the energy residual is ≤ 1.9e-11 pJ (W 4.32 pJ, Q 4.01 pJ), and the heat never decreases;
  - H_eq drifts by ≤ 3.5e-15 and K by ≤ 1.7e-15; |φ_c| ≤ 7.5e-12 V;
  - |ΔG_cyc/RT| ≤ 19.9, inside §6's domain of 80;
  - the cytosol stays within 0.0012 of 7.2, inside the band.
- **Floor** (rtol 1e-11 against 1e-12): 7.1e-15 (declared) and 1.2e-14 (K2(b)) in pH_L.
- **Self-test:** `test_k2b_the_reversed_pump_is_opposite_at_the_start_and_closes_its_ledgers`.
  - At the start, the two pumps' proton fluxes are equal and opposite.
  - The protocol's ΔG_cyc and S hold at an arbitrary state.
  - Over 20 s its ledgers close, it alkalinizes the lumen, and K⁺ follows in.

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

**Self-tests:** `tests/unit/test_compartment_transfer_references.py`, 6 tests, tier 1, 6.8 s on
CPU 7. The folder's independence tests cover this module too.

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

- **The note's revision:** both findings (§4.2's envelope above, §13.2 here) are against the note
  at f3ec04cd. §4.2 has since been revised, so read "§4.2 says" as that revision's text.
- **The start is undefined to the budget.** *Answered by 220d6e4d: the start is FR-4's
  checkpoint at 1800 s.*
  - FR-4's 900 s acceptance run ends at pH_L 5.09601, while the steady state is 5.09463,
    reached by about 1800 s.
  - The gap, 1.4e-3 pH, exceeds the 1e-3 budget, so "FR-4's world at its steady state" is not
    the end of FR-4's run.
  - The owner should declare the checkpoint's time. Otherwise a comparison starts from the
    engine's own checkpoint, passed as `tr.Start`. The reference computes its own at 3600 s.
- **No budget is declared for X.** G1/G3 require a control's effect to exceed the declared budget,
  so the two controls cannot be judged on X until §13.2 declares one. *Answered by 220d6e4d:
  1e-3 of X_L(0), used in the arms section above.*
- **Resealing is off before 110 s,** as §13.2's "k_res 0.05 s⁻¹ from 110 s" reads. With it on
  throughout, d would peak near k_inj/(k_inj + k_res) = 0.952 rather than 0.99995.
- **The pore's proton heat** is booked apart from the leak's (each route its own heat, §9). Their
  sum is Appendix A's single J_H term.
- **The transfer route is not scaled by d,** as in Appendix A's J_X, and §13.2 declares no f·d
  route. The reference supports f·d (`CargoRoute(conditioned=True, damaged=True)`), and its
  self-test checks it.

## The revised world: arms T and R (§13.2 at 220d6e4d)

Run `compartment-transfer-arms-01`, from snapshot `compartment-transfer-snapshot-02` (b73769ad), on
CPU 7; driver `transfer_arms_crosschecks.py`.
- **The start:** both arms start from FR-4's steady state at 1800 s, here R-closure's own state
  there: pH_L 5.0946 and V_b −7.33 mV. The engine's checkpoint can be passed as `tr.Start`.
- **Cargo X:** 1 mM in the lumen and 1e-4 mM in the cytosol. The owner is impermeant, so the
  bath's X never enters.
- **Records:** 400 s, every second.
- **X's budget:** B = 1e-3 X_L(0) = 6.545e-5 fmol.

| | Arm T (the condition) | Arm R (the release) |
| --- | --- | --- |
| Damage window; pH_L first above pH₅₀ | [60, 120] s; **74 s**, inside the window | [100, 160] s; **114 s**, inside the window |
| Peak pH_L (time); back below pH₅₀ | 5.912 (139 s); 327 s | 5.912 (179 s); 367 s |
| Smallest f (time) | **0.022** (139 s) | 0.022 (179 s) |
| X left in the lumen: before damage, window end, 400 s | 0.503, 0.409, 0.163 of X_L(0) | 0.891, **0.0155**, 0.0155 |
| Conditioned transfer's flux: before damage, at the smallest f, at 400 s (fmol/s) | −3.80e-4, **−6.8e-6**, −9.7e-5 | −6.8e-5, 0, 0 |
| The pore's release in the window | – (proton-only pore) | **0.874 of X_L(0)**, peak flux −4.97e-3 fmol/s; afterwards c_X,L = c_X,c |
| Control | f ≡ 1 | d ≡ 0 |
| Control's distance: X_L; cumulative transfer | **314 B** (245 s); 314 B | **872 B** (102 s); 262 B (400 s) |
| Control's peak pH_L | 5.912, the same | 5.0946 (no rise; 0.818 below the arm) |
| Energy residual; H_eq and X drift | ≤ 4.2e-11 pJ; ≤ 3.0e-15, 1.7e-15 | ≤ 2.5e-11 pJ; ≤ 4.2e-15, 1.1e-15 |
| The cytosol's band \|pH_c − 7.2\| | ≤ 0.018 | ≤ 0.018 |
| Floor (rtol 1e-11 against 1e-12): X_L; pH_L | 3.7e-15 X_L(0); 1.4e-14 | 3.3e-15 X_L(0); 2.0e-14 |

**Under full damage held at d = 1** (3600 s from the start): pH_L 6.244, V_b −2.46 mV, f 1.06e-3.

**The explicit-limit figure,** max-side G = F²/(RT) P A max(c_in, c_out) at dt = 1 ms:
- the proton routes (leak plus pore) at pH 5.1 under full damage: dt G/C_b = 0.0304 (0.0287
  from the pore alone);
- over the arms' runs, the proton routes reach 0.0223; with K⁺'s route, the patch's total reaches
  **0.0476**, against the world's 0.05.

### Answers to the owner's five questions

1. **The lumen's pH crosses pH₅₀ inside each window:** confirmed, at 74 s (T) and 114 s (R).
   - The host estimate of the full-damage steady state is also confirmed: 6.244 against the
     estimated 6.2.
   - But the window ends, and resealing starts (τ = 20 s), before the lumen gets there. The peak
     is 5.912.
2. **f closes in arm T:** to 0.022, not the estimated 1.6e-3, because the peak pH is 5.91 rather
   than 6.2.
   - The conditioned flux still falls 56-fold, while 41% of X remains in the lumen.
   - X keeps crossing slowly while f is partly open, so 0.25 of X_L(0) crosses between 120 s and
     400 s.
3. **Arm R's burst and pH rise:** confirmed.
   - The pore releases 0.874 of X_L(0) within the window, and the lumen's X then equals the
     cytosol's.
   - **Re-acidification is partial at 400 s.** The pH is back below pH₅₀ by 367 s (327 s in T),
     but not within 0.01 of the start (see the follow-up below).
4. **Both controls clear 10× the budget,** by far: 314 B (T) and 872 B (R) in X_L.
5. **The explicit-limit figure:** confirmed, 0.029 from the pore alone at pH 5.1 (0.030 with the
   leak).
   - **A reading:** 0.048 is the figure only if the 0.05 bound applies to the patch's total over
     its routes, where K⁺'s route adds about 0.025. Per route, the proton routes peak at 0.022 over
     the runs.

### The follow-up: what the shortfalls need

`compartment-transfer-arms-01-followup.log` is a probe from the checkout at b73769ad, kept beside
the record.

| Question | Result |
| --- | --- |
| Re-acidification, with the run extended to 1500 s | T: pH_L 5.333 at 400 s, back within 0.01 of the start by 640 s and within 0.001 by 780 s. R: 5.421 at 400 s, then 680 s and 820 s |
| Arm T's smallest f against the window (damage from 60 s) | [60, 120]: 0.022 (peak 5.912). [60, 180]: 5.9e-3 (6.057). [60, 240]: 2.9e-3 (6.133). [60, 360]: **1.5e-3** (6.204) |

**Arm T's "the transfer stops", judged on the budget's own quantity.** The second probe,
`compartment-transfer-arms-01-followup2.log`, measures the conditioned route's cumulative transfer
while pH_L is above pH₅₀.

| Damage window | Above pH₅₀ | Transfer while above (B; fraction of X_L(0)) | Before damage, 0–59 s |
| --- | --- | --- | --- |
| [60, 120] (declared) | 74–326 s | **152 B**; 0.152 | 497 B |
| [60, 180] | 74–434 s | 155 B; 0.155 | 497 B |
| [60, 240] | 74–517 s | 155 B; 0.155 | 497 B |
| [60, 360] | 74–658 s | 156 B; 0.156 | 497 B |

- **So arm T shows "slows", not "stops".** About 150 budgets cross while the lumen is alkaline.
  The mean rate falls about 14-fold.
- **A longer window does not change it.** Most of the transfer happens while f passes through its
  half-open range, on the way up and on the way down.
- **The owner must restate the claim,** for example as a reduced transfer with its number, or
  change the condition's sharpness. That second option was not explored here.

**The nearest changes, for the owner to choose between:**
- **For "re-acidifies" to mean back within 0.01 pH:** a horizon of about 700 s, or 850 s for 0.001.
  Otherwise, state the claim as "back below pH₅₀", which 400 s shows.
- **For f near the estimated 1.6e-3:** a 300-s damage window in arm T ([60, 360] s). It does
  not make the transfer stop (above).

### The restated claims (fr45-physics a593c0a2), confirmed on the record

`compartment-transfer-arms-01-readout.py`, with its log and JSON, sits beside the record.
- **How it was produced:** the readout re-integrates the record's worlds with the record's own code
  (snapshot 02, b73769ad). It reproduces the record's stored X_L fractions and peak pH exactly,
  with differences of 0.0.
- **Crossing times** are resolved by Brent's method on re-integrations.
- **Rates** are taken from the conditioned route's cumulative transfer, in units of B.

| Claim | On the record | Holds |
| --- | --- | --- |
| Arm T: while pH_L > pH₅₀, the conditioned mean rate falls at least 10× below its pre-damage mean | Pre-damage, over [0, 60] s: **8.375 B/s**. Above pH₅₀, over [73.081, 326.882] s: **0.6120 B/s**. Ratio **13.69** | Yes |
| pH_L back below pH₅₀ before 400 s | Arm T: **326.882 s**; arm R: **366.882 s** (up-crossings at 73.081 s and 113.081 s) | Yes |
| Arm R: at least 0.8 of X_L(0) released inside the window | **0.8736** through the pore over [100, 160] s | Yes |

In arm R, the conditioned route carries nothing while pH_L > pH₅₀: the burst has already equalised
c_X,L and c_X,c.

**Dependence on the start state.** The readout was repeated from FR-4's state at 900 s, whose
pH_L is 1.38e-3 above the 1800 s state.

| Quantity | Shift from that 1.38e-3 pH offset |
| --- | --- |
| Crossing times | ≤ 0.008 s |
| Arm T's ratio | 13.686 → 13.682 |
| Arm R's release | +1.5e-5 |
| X_L along the run | Up to 8.5e-5 of X_L(0), that is **0.085 B** |

- **No restated claim depends on the start** at the level of an engine checkpoint.
- **The X budget itself is start-sensitive.** The engine-against-reference difference in X_L moves
  by about 0.06 B per 1e-3 pH of start offset. So the comparison should start the reference from
  the engine's own checkpoint (`tr.Start`). Otherwise a start offset of about 1.6e-2 pH would
  consume the whole budget.

# Finite fuel (item 4): R-fuel

The lead chose option (a) on 15 November 2026: a neutral solute Y moved by an ATP-driven pump in
§6's form, with D152's passive regeneration on a schedule m(t). No engine note specifies this case
yet, so the sections below are the reference's own specification, from:
- ARCHITECTURE.md's "Material identity and fuel" (F2, and "the first case");
- D176, decisions 1 and 2;
- D152's §2.2 (the passive reaction law);
- this note's §5 and §6.

| Module | What it gives |
| --- | --- |
| `validation/compartment_ph/fuel_reference.py` (`fr`) | R-fuel: the world, both laws, the leak, held fuel, the energy identity and the moieties |
| `validation/compartment_ph/fuel_crosschecks.py` | The driver behind the numbers below (`--out DIR`; about 20 s) |

**Self-tests:** `tests/unit/test_compartment_fuel_references.py`, 5 tests. The folder's
independence tests cover this module too.

**Limits:**
- The pump is exercised at n = 1 only.
- The schedule is on/off (`off_windows`), though the specification allows m ∈ [0, 1].
- The specification and the reference share an author, so only an engine note can check the
  specification itself.

```python
from validation.compartment_ph import fuel_reference as fr

run = fr.integrate(fr.acceptance_world(), 900.0, record=ts)               # finite fuel
held = fr.integrate(fr.acceptance_world(held=True), 900.0, record=ts)     # held fuel
ctl = fr.integrate(fr.acceptance_world(off_windows=()), 900.0, record=ts)  # m = 1
```

`run.at[t]` holds:
- `c` {ATP, ADP, Pi, D, P, Y_c, Y_s} (mM);
- `J_cyc`, `J_Y` (from s to c) and `v` (fmol/s), and `m`;
- `dG_ATP`, `dG_cyc` and `dG_reg` (J/mol);
- `cycles` and `regenerated` (fmol);
- `heat_pJ` {pump, leak, reg}, `Q_pJ`, `W_pJ`, `stored_change_pJ` and `energy_residual_pJ`;
- `moieties` {adenine, phosphate, donor, Y} (fmol).

## Units and the standard state

- **Units:** fmol, pL, mM (= fmol/pL), s, m and m/s. Potentials are in J/mol, and energies in pJ
  (1e-3 × fmol × J/mol).
- **The standard state** is c° = 1000 mM (`FuelWorld.standard_mM`). Every activity is a = c/c°,
  as in D152's law and §5.2's Δ_rG'.
- **The registry's potentials:** each row's μ°'/RT (`FuelWorld.mu0_RT`) at the world's
  temperature. Every ΔG° is formed from them, and none is a parameter of a law.
  - Δ_rG'°_hyd = RT [μ°'(ADP) + μ°'(Pi) − μ°'(ATP)] = −30.5 kJ/mol;
  - Δ_rG'°_reg = RT [μ°'(P) + μ°'(ATP) − μ°'(D) − μ°'(ADP) − μ°'(Pi)] = −29.5 kJ/mol;
  - the proposal's values are μ°'(ATP) = 30.5 kJ/mol, μ°'(D) = 60 kJ/mol, and 0 for ADP, Pi, P
    and Y (only differences enter).
  - RT = R × 310 K = 2577.48 J/mol.

## The world: one fixed volume, closed

- **Nodes:** the cell c, which is the fuel node, with volume V_c; and a store s (V_s), across one
  patch of area A. There is no bath term, water or division.
- **Rows:** all are neutral, with potentials transformed at the cell's pH_ref and pMg_ref (§5.2).
  - ATP, ADP and Pi, a donor D and its product P, at c;
  - the pumped solute Y, at c and s.
- **One authority:** each row's μ°'/RT. The reaction and the pump both read it.

## The laws

- **The regeneration reaction** at c: D + ADP + Pi ⇌ P + ATP, by D152's
  `cells.species_reaction.ideal_detailed_balance_mass_action@1`:

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

## The calibrated first case

| Quantity | Value |
| --- | --- |
| Volumes and patch area | V_c 4.18879 pL, V_s 6.54498e-2 pL, A 7.85398e-10 m² |
| Starting rows (mM) | ATP 3, ADP 0.3, Pi 3, D 30, P 3; Y 10 on both sides |
| Standard terms | Δ_rG'°_hyd −30.5 kJ/mol; μ°'(D) − μ°'(P) = 60 kJ/mol, so Δ_rG'°_reg = −29.5 kJ/mol |
| The pump | k 0.1 fmol/s, n 1, K_Y 1 mM, K_ATP 0.1 mM, a = 1 |
| The leak | P_Y 1e-9 m/s |
| The reaction | k_f 1e4 s⁻¹ (about 1.1 fmol/s forward at the start, well above the pump's demand) |
| The depletion window | m = 0 on [100, 300) s; the run lasts 900 s |

**The law near zero ATP.** It is evaluated as the identical rational form
k a [c_Y,c^n c_ATP − c_ADP c_Pi e^(Δ_rG'°_hyd/RT) c_Y,s^n/c°] / [(K_Y^n + c_Y,c^n)(K_ATP + c_ATP)].
- It is §6's S (1 − e^(ΔG_cyc/RT)) for every positive state, and it stays finite at the
  integrator's trial states.
- m(t) is held at its value inside each segment, so no evaluation at a window's edge sees the
  next segment's value.

## Measured (`compartment-fuel-crosschecks-01`, from snapshot `compartment-fuel-snapshot-01`)

900 s, 132 records: every 10 s, and every second on [95, 105] and [295, 330] s.

| | Finite fuel | Held fuel | Control, m ≡ 1 |
| --- | --- | --- | --- |
| J_cyc at 99 s; at 299 s (fmol/s) | 8.713e-2; **1.552e-4** | 8.690e-2; 8.642e-2 | 8.713e-2; 8.664e-2 |
| ATP at 99 s; at 299 s (mM) | 3.270; **1.74e-4** | 3 (held) | 3.270; 3.263 |
| ADP, Pi at 299 s (mM) | 3.300, 6.000 | 0.3, 3 | 0.037, 2.737 |
| Δ_rG'_ATP at 99 s; at 299 s (kJ/mol) | −57.8; **−18.3** | −51.4 | −57.8; −57.2 |
| Y in the store at 99 s; 299 s; 900 s (mM) | 86.9; 75.9; 118.5 | 86.7; 115.7; 118.3 | 86.9; 115.9; 118.5 |
| Recovery of J_cyc after the window | Within 1% by 302 s, within 0.1% by 303 s | – | – |
| Cycles; regenerated (fmol) | 74.46; 75.37 | 77.88; 0 | 78.07; 78.95 |
| Heat: pump, leak, regeneration (pJ) | 3567.1, 440.8, 558.2 | 3498.3, 472.7, 0 | 3915.9, 474.3, 386.9 |
| W; ΔG_stored (pJ) | 0; −4566.2 | 4003.6; 32.7 | 0; −4777.1 |
| Largest energy residual (pJ) | 2.5e-11 | 3.6e-12 | 9.6e-12 |
| Moiety drift (relative) | ≤ 4.5e-15 | ≤ 1.0e-15 | ≤ 1.8e-15 |
| Largest \|ΔG_cyc/RT\| | 21.7 | 19.1 | 21.7 |

- **Finite fuel against held fuel:** J_cyc at 299 s is 0.0018 of held fuel's. The window costs
  3.42 fmol of cycles, and the store holds 39.8 mM less Y at 299 s.
- **Floor** (rtol 1e-11 against 1e-12): ATP within 6.3e-14 mM, J_cyc within 4.3e-16 fmol/s and Q
  within 3.0e-11 pJ.
- **Fed, the cell's fuel sits near the regeneration's equilibrium.** ADP is low and Δ_rG'_ATP is
  −57.8 kJ/mol, below held fuel's −51.4.
