# The core seams' independent references: seam A (membrane cycles) and seam C (binding)

**Registered 18 November 2026, before any engine output for seams A or C** (registering commit
f1808037). The lead confirmed that the kinds and binding owners had not started
(CORE_SEAMS_DESIGN §19 item 7). The worlds are
registered here. The engine builds its synthetic test laws from these inputs, never from the
expected values (§19 item 1). `REFERENCES_USAGE.md` is the interface. The model is FR-3's
references.

## What the registering commit holds

| Path | What it is |
| --- | --- |
| `reference_inputs.json` | The registered inputs, self-contained, written by `worlds.py`. Seam A: its registry, 13 laws (2 of them added by amendment 1), 22 planted diagram laws, 4 parse plants, 365 host states, the populations and the node volumes. Seam C: its registry, 6 binding systems with 70 manufactured states (their totals as doubles), 2 P1 nodes and 5 movers |
| `designs/core_seams_reference_values.json` | The references on every registered state, one record per line |
| `designs/core_seams_reference_design.json` | The claims; each plant's power (its largest deviation over the states, where, its smallest, and where it is weak); the zero-power cases; the readings |
| `exact.py` | Exact SI constants, 60-digit decimals and forward-mode duals |
| `diagrams.py` | Kinetic diagrams: Hill's cycles by spanning trees and by the matrix-tree minors, the master equation's steady state, and Wegscheider's residual (exact, affine and as a float64 stand-in) |
| `cycles.py` | Cycle laws on a population: free energies, fluxes, rows per host end, heat, work, the stored rate, charge, exact slopes, and the parse-time checks |
| `binding.py` | The multi-ligand closure: speciation by Newton and by nested bisection, conservation, charge, G*, the floors, P1's thresholds, and (amendment C1) the booked term |
| `primal.py` | Amendment C1: the second route, the primal Gibbs minimum by Newton on reaction extents, sharing only the registry's inputs with the dual |
| `envelope.py` | Amendment C3: the binding network's first-order lag and its kinetic reference |
| `api.py` | The entry points |
| `worlds.py` | Writes the inputs (`--check` compares) |
| `design.py` | Writes both design files in about a minute of one CPU (`--check` regenerates and compares) |

## Independence and disclosure

**Written without the engine.** Nothing here imports `cells` or reads `src/`: not the kinds, the
laws, the operators or @3. Nor does it read the step-0 probes' scripts or workspaces, or any engine
output for seams A or C.

**Read**, all design text:
- the brief's sections: CORE_SEAMS_DESIGN §3, §5, §16, §17 and §18, then §19 (the rulings on this
  package's plan), and CORE_SEAMS_STEP0 §1.1 and §7, for their claims;
- beyond the brief, disclosed to the lead in the plan and accepted in the lead's message of 18
  November (not part of §19):
  - CORE_SEAMS_DESIGN §0–§2, §4, §6.1 and §10–§15;
  - CORE_SEAMS_STEP0 §1.2–§1.3 and §8;
  - COMPARTMENT_PH_TRANSFER_DESIGN §2–§6, §17.1–§17.2 and Appendix A (the version-1 laws, B4's
    closure and its energy);
  - MITOCHONDRIA_DESIGN §1.3–§1.4 (counting from base forms);
  - INNER_MODEL_V4_DESIGN's B5 transporter declaration;
  - R-fuel's statement of the neutral law (`validation/compartment_ph/REFERENCES_USAGE.md`,
    "The laws");
  - D202;
  - FR-3's references, as the pattern.

**Not blind.** STEP0 §7 reports the independent check's figures: the effective charge 1.2118, the
3.7% basis failure, and the 3.37 µs and 38,000 of P1 (§17). They shaped which plants exist, but no
registered number derives from them. The worlds are this package's own synthetic bracket (D152
§2.4), and STEP0 §5.2's world was not read (§19 item 4).

**What the version-1 rows rest on:**
- **The proton law** (`v1_proton_n2`) is COMPARTMENT_PH_TRANSFER_DESIGN §6's statement, a design
  note.
- **The neutral law** (`v1_neutral_*`) rests on R-fuel's statement in
  `validation/compartment_ph/REFERENCES_USAGE.md`. That note says it is a reference's own
  specification, since "no engine note specifies this case yet". So if the engine's neutral law
  differs from it, for example in S, that is a gap in the specification, not a plant the
  references caught.

## Seam A: the laws and states

All laws are on a patch with ends a (the population's cell) and b (the outside node), with N = a
except `d2_slip_exchanger_Nb`.
The states are host states: the end potentials and the free concentrations at each end.

| Law | What it is | Cycles |
| --- | --- | --- |
| `d1_pump` | A 4-state electrogenic ATP-driven pump, 2 H⁺ N → P, on held fuel | one (A) |
| `d2_slip_exchanger` | A 6-state exchanger, 3 X⁺ in for 1 Y²⁺ out, with a slip edge (the empty carrier crossing) | A (exchange), B (Y uniport), C (X uniport), sharing edges |
| `d3_figure_eight` | An X⁺ uniport and a neutral Z uniport sharing only a state | α, β: the admitted basis, which is the full set |
| `d4_parallel_branches` | Two parallel edges between the same two states, one co-transporting H⁺ | K1, K2, and K3, the branches' 2-cycle |
| `v1_proton_n2` | `cells.proton_atp_mass_action_positive@1` at n = 2 (COMPARTMENT_PH_TRANSFER_DESIGN §6) | the factored cycle |
| `v1_neutral_n1`, `v1_neutral_n2` | `cells.atp_driven_transporter_mass_action_positive@1` (R-fuel's statement) at n = 1 and 2, moving Z | the factored cycle |
| `planted_negative_S_n1` | PLANTED: the neutral law with S − 0.05 | — |
| `fb_shift`, `fb_masked`, `fb_basis` | Net-flow laws for the guard (A3) | — |
| `ff_neutral_n1` | Amendment 1: the neutral law on finite fuel rows. ATP, ADP and Pi are moved at N = a and nothing is held | the factored cycle |
| `d2_slip_exchanger_Nb` | Amendment 1: D2 with N = b, the outside node as N. Its host states are the exchange family's with the ends swapped | D2's three |

**How the diagrams are built.** State energies and per-edge rates are chosen, and each edge's
constants split its standard free-energy change evenly between its two directions. Every cycle
then satisfies Wegscheider's condition by construction, to the rounding of the published doubles.
The load fractions are dyadic, so every passing law's structural coefficients are exactly zero.

**Each diagram's states:**
- 12 random states;
- every cycle's equilibrium neighbourhood, at ΔG/RT ∈ {0, ±1e-9, ±1e-4, ±1};
- two far states at ±25;
- the unit state (every activity 1, ψ = 0).

The first d + 1 random states are the generic set. They have full rank in (1, ln a, ψ) for every
law (`power.A2_wegscheider.generic_sets`). The version-1 laws carry 12 random states, a static-head
ladder (0, ±1e-6, ±1e-3, ±0.1, ±1) and two far states.

## Seam C: the systems and states

| System | Ligands | Binders | What it tests |
| --- | --- | --- | --- |
| S1 | H⁺ | buf1 | B4's case, with three hard states: mostly bound, a saturated binder, a trace binder |
| S2 | H⁺ | buf1, buf2 | one ligand, two binders |
| S3 | H⁺, Mg²⁺ | nuc4 | a form holding both ligands (`nuc4_MgH`) |
| S4 | H⁺, Mg²⁺ | nuc4, nuc3, pi2 | three binders; `pi2_PO4` below its base (count −1, §19 item 6); a negative H total at pH 11 |
| S5 | H⁺, Ca²⁺ | buf1, cab0 | two disjoint closures at one node, solved jointly and separately |
| S6 | H⁺, Mg²⁺, Ca²⁺ | nuc4, cabuf | three ligands connected through shared binders |

**How the states are manufactured.** Free ligands and binder totals are drawn, and the ligand
totals are computed forward in 60 digits and rounded to doubles. The doubles are the registered
inputs. The free forms the engine must return are the reference's solution from those doubles,
not the manufactured ones; the two differ by the inputs' rounding times the conditioning.

## The references and their floors

| Reference | Method | Second method | Agreement |
| --- | --- | --- | --- |
| One-way cycle fluxes j±_κ = Π±_κ Σ_κ/Σ | Spanning trees, with Σ_κ from the contracted diagram | The matrix-tree minors, and the master equation solved by elimination | to 5e-53; occupancies to 8e-58 |
| The cycle set's completeness | Every edge's net flux equals the signed sum of its cycles' net fluxes | — | to 1.5e-59 (an incomplete set fails, a test) |
| Wegscheider's residual | Exact affine coefficients; 50-digit values at every state | The float64 stand-in, two ways | — |
| Slopes | Forward-mode duals through the whole computation | Central differences in decimals | to 1.2e-29 |
| The closure's speciation | Damped Newton on the convex dual Φ(u), 60 digits | Nested bisection (≤ 2 ligands) and the manufactured solution | to 6.8e-32, and 9.7e-15 (the inputs' rounding) |
| G*'s gradient | The free base forms' potentials | Central differences of re-solved speciations | to 1.6e-30 |

**The closure's floors**, per state and per output (free ligands and every form):
- **the inputs' rounding:** ½ ulp on every published double (the totals, V and each μ°/RT), at
  most 8.5e-14 relative;
- **the residual's bound:** the solution error that §19's |g_L| ≤ 1e-13 V A_L admits (amendment
  C2; |g|/T ≤ 1e-13 as first registered), at most 3.8e-11
  (S1's saturated binder). This is the floor the engine's comparison needs.

## The registered design: power

The checks are deterministic, so a plant's power is its margin, and the margin must be at least
10. A plant has power where its largest deviation over the registered states clears ten
tolerances, and the tolerance clears ten floors. `weak_at` lists the states where it does not.

Every seam-A deviation is in floors at its state:
- **On J** (and the rows, heat and work), the floor is the honest float64 rounding, absolute:
  (J⁺ + J⁻) × (ΔG/RT's terms + 8) eps. Near equilibrium no relative floor exists.
- **On one-way fluxes and slopes,** it is (terms + 8) eps, relative.

**A1, sign and zero.** Over every state:
- every admitted law has J ΔG ≤ 0, exactly 0 at the unit states;
- the planted S − 0.05 runs against its ΔG at the two states where S < 0, by at least 1.2e13
  guard allowances.

**A2, Wegscheider** (in eps of the residual's terms' absolute sum):
- **Passing laws:**
  - their structural coefficients are exactly zero;
  - their constants are at most 0.093 eps;
  - the honest stand-in is at most 0.29 eps.
- **Plants:** over the generic sets, each plant's smallest residual is:
  - the constant ×(1 + 1e-6): 1.4e7 eps;
  - ×1.01: 1.4e11;
  - the voltage exponent: 2.1e11;
  - the missing factor: 3.5e13;
  - the swapped end: 3.7e12.
- **The unit state:** the charge, concentration and swap plants fall to the passing law's
  rounding there. That shows why §19 rules out a one-state check.
- **The declared bases:** D2 as {A, B} and D4 as {K1, K2} are refused (incomplete, sharing an
  edge), and D3's basis is admitted.

**A3, the population guard.** This package's allowance is 64 eps of Σ_m (J⁺ + J⁻) × |ΔG terms|.
- `fb_shift` fires at the 12 band-interior states and is silent at its 22 others, the band's
  edges included. Its smallest margin where it fires is 142 allowances.
- **The verdicts are conditional on the band.** They hold for any stated band between 0.064 and
  9.1e3 eps (`verdicts_hold_for_a_band_in_eps`). The kinds owner states the real band (§19 item
  2). The 1e-6-inside states (`conditional_on_the_band`) set the upper end, and the mid-band
  states hold for any band below 1e6 eps.
- `fb_masked` never fires, though its exchange runs against ΔG at 12 states.
- `fb_basis` never fires, though a basis mode runs against its ΔG at 4 states.
- The admitted laws' float64 stand-in, J⁺ − J⁻, never gives a positive total at the registered
  states.

**A4, one-way fluxes** (each plant's largest margin per cycle, and where it is weak):
- **The exponent flipped:** 1e15 to 4e81, weak only at a cycle's exact equilibrium (the `near_*_+0`
  states and the unit state). At |ΔG/RT| = 1e-9 it is already about 3e5.
- **An edge's one-way fluxes in place of the cycle's:** 7e15 to 7e31, and at least 2.8e8 at every
  state.
- **The basis's fluxes:** 1.9e14 to 3.9e26, weak only at D2's far_A_+25.
- **Σ_κ omitted:** at least 3.6e13 where Σ_κ ≠ 1, and none on a cycle through every state.

**A5, two layouts** (largest margin over the states, and the weakest state):
- **N/P swapped:** 8.5e13 to 1.8e30, at least 3.8e11 everywhere.
- **The fuel end misplaced:** 4.7e13 to 3.2e30, at least 1.3e12 everywhere.
- **n ± 1:** 3.1e13 to 1.5e39, at least 1.6e11 everywhere.
- **The fuel's 1 mM frame:** 1.9e16 to 3e32, at least 2.8e4 everywhere. J is still caught far
  from static head.
- **Capacity counted twice, rows scattered and the work's sign:** about 4e13 to 1.6e14, weak only
  at static_head_+0, where there is no flux.
- **The voltage term dropped:** up to 3.1e13 on the proton law, at least 6e5 at every state. It
  has no power on the neutral law.

**A6, slopes** (largest margin, and where it is weak):
- **∂S/∂V ignored:** 1.1e16 to 5.2e22, weak only at a cycle's equilibrium.
- **The static-head formula:** 2.4e21, weak only at static head, where it is exact.
- **n_q not squared, and F/(2RT):** each at least 1.1e13 everywhere.
- **The wrong node's volume:** at least 1.5e14 everywhere.

**A8, amendment 1's finite fuel.**
- The stored rate is nonzero, up to 7.9 pJ/s.
- The 1 M frame, the stored rate dropped, and its sign clear 1.3e13 to 6.9e13 floors, weak only at
  static head.
- With the fuel held instead, the rows, the stored rate and the work move by up to 8.8e13. J does
  not move: the kinetics are the same either way.
- With the fuel moved at b, J, the rows and the stored rate move by at least 4.3e12 everywhere.

**A9, amendment 1's N = b.** Five plants were run:
- read as N = a;
- the voltage's orientation ignored;
- the charge's sign;
- rows at swapped ends;
- the conductance's sign.

The first four clear 5.9e13 or more at their largest and are weak only at the unit state, where
both ends are identical. The conductance's sign clears at least 4.1e13 everywhere.

**A7, parse checks:**
- X⁺ not conserved: charge +1.
- ATP → ADP without Pi: phosphate −1.
- Base-form hydrolysis without its proton: charge −1.
- The control is admitted, and every registered law's modes pass.

**C1–C4, binding**, at every state (each plant's deviation over the residual-bound floor):
- the constant ×1.01: at least 1.7e8;
- ×(1 + 1e-6): at least 1.7e4;
- a dropped form: at least 1.5e7;
- a count off by one: at least 1.7e11;
- conservation off by 1e-10: at least 421.

None is weak anywhere. Beside them:
- charge from totals holds to 1.6e-54 fmol e, and conservation to 3.7e-53;
- the rows' own potentials are off the gradient by at least 4.6e3 J/mol;
- a non-minimum speciation lies at least 5.4e-7 pJ above G*;
- a declared valence −1 for `nuc4_Mg` (derived −2) is refused.

**C3, movers:**
- The base-form hydrolysis is admitted, and so is MgATP written out as nuc4 and Mg.
- Refused: the proton omitted, a form moved as a row, and an undeclared mover.

**C5, P1's node** (rate-normalised: divide by |J| for θ·dt):

| Node | n_free | Stored equivalents above their floor | Linearised free capacity | Ratios to n_free |
| --- | --- | --- | --- | --- |
| P1a (40 mM, pK 7.0, pH 7.2, 0.05 pL) | 3.15e-6 fmol | 0.774 fmol | 0.474 fmol | 2.45e5 and 1.50e5 |
| P1b (H⁺, Mg²⁺ and four binders) | 1.99e-6 fmol | 0.885 fmol (floor −0.5) | 0.285 fmol | 4.45e5 and 1.43e5 |

Today's predictor goes negative at the first draw above n_free. The equilibrated free amount stays
positive up to the stored amount.

**Zero power** is in the design file's `zero_power`, with each case's remedy. In brief:
- each Wegscheider plant at its zero locus, and any one-state check;
- the exponent flip at a cycle's exact equilibrium;
- Σ_κ on cycles through every state;
- the basis's fluxes at one far state;
- the guard on masked errors, and on every admitted law;
- capacity, scattered rows and the work's sign at static head;
- the voltage term on the neutral law;
- the static-head formula at static head, and ∂S/∂V at equilibrium;
- conductance plants on neutral modes;
- a transported species' dropped μ°;
- the moved rows' standard part in the held-fuel populations (amendment 1's `ff_neutral_n1`
  gives it power);
- a population with N = b before amendment 1 (now `d2_slip_exchanger_Nb`);
- amendment 1's own weak cells: static head for the stored rate, and the unit state for N = b;
- the layouts' bitwise identity (the engine against itself);
- weakly held forms;
- today's predictor below n_free;
- a declared form valence the engine never reads.

## Findings for the lead

1. **Doubles carry rounding into the residual.**
   - A passing cycle's constant term is about 1e-16, not 0.
   - A non-dyadic load fraction leaves the voltage coefficient about 5e-17 off.
   - So an algebraic Wegscheider check needs §19's rounding band as well.
2. **A diagram's own backward flux** Π⁻Σ_κ/Σ differs from the contract's J⁺e^{ΔG/RT} by e^{−r}.
   - Here r is at most 2.4e-15 for the passing laws.
   - Booked with its own backward flux, an admitted law would show J ΔG > 0 within |r| of
     equilibrium, at about 1e-37. The contract's J⁻ keeps the sign exact.
3. **A form below its base makes a ligand's total legitimately negative** (S4 at pH 11: T_H =
   −1.86 fmol).
   - The admissible floor is Σ_B T_B min_f n_{L,f}, not zero.
   - @3's per-row ideal term RT n(ln(n/V) − 1) is then undefined on that row, and so is "G* less
     the stored rows' own terms".
   - The booked term's ruling (§19 item 3) and any positivity guard on the ligand row, P1's
     predictor included, must account for it. P1b's floor is −0.5 fmol.
4. **The guard's teeth show only on net-flow laws.** Factored and admitted diagram laws cannot
   trip it, so its plants are published as net-flow test laws.

## Amendments

- **18 November 2026, amendment 0, before any engine output for seams A or C** (the lead's
  confirmation, §19 item 7):
  - this README gained the registering hash;
  - the design file's `zero_power` gained two entries found at review. One is the moved rows'
    standard part: the stored rate is exactly 0 at every state, because every population holds
    its fuel. The other is a population with N = b, of which none is registered.
  - The inputs and values are unchanged, and so is every other registered number.
- **18 November 2026, amendment 1, before A's first output** (CORE_SEAMS_DESIGN §19, amended the
  same evening; the lead reconfirmed that no seam A or C output exists):
  - two populations added, `ff_neutral_n1` (finite fuel, A8) and `d2_slip_exchanger_Nb` (N = b,
    A9), with their states and plants. They are drawn after every earlier input, and every input
    and value registered before is unchanged;
  - the zero-power list updated: the two blind spots now name their remedies, and the amendment's
    own weak cells are listed;
  - two tests added.
- The tests' tier rows were folded the same day, after amendment 1 (see Tests).
- **18 November 2026, 20:06 UTC, amendment C1, the booked term, before any output of the general
  closure** (CORE_SEAMS_DESIGN §19, amended at 19:52 UTC on the binding owner's design statement
  1, which this package read only as the ruling states it; branched from main, never from the
  binding owner's branch):
  - **The booked-term row,** at every state of S1–S6, from this package's own G*:
    - E_c = G* − Σ_r T_r μ°′_r, the standard parts in @3's 1 mM frame;
    - S_c = E_c − Σ_r ideal_r (= G* − Σ own_r, the registered `speciation_part_pJ`);
    - @3's ideal terms, and B4's formula S_c + Σ_B T_B μ°′_B;
    - E_c's gradient in @3's frame, RT ln(c_free/1 mM) per row, against differences to 9e-26
      J/mol.

    The identity E_c = S_c + Σ ideal holds to 2e-57 pJ, so both splits are referenced. At S4[10],
    whose H total is negative, E_c and G* are defined and S_c is not.
  - **Three plants,** each on consecutive pairs of one system's states. Each misses ΔE_c by
    exactly its named sum:
    - G* booked whole (Σ ΔT_r μ°′_r): at least 7e11 floors;
    - B4's formula on moved binders (Σ_B ΔT_B μ°′_B): up to 2e14, and 0 where a pair's binder
      totals are equal (listed in zero power);
    - S_c alone with @3's ideal terms masked (Σ Δ ideal_r): at least 9e11, and undefined at
      S4[10]'s pairs.

    The floor is 8 eps of both states' terms.
  - **The second route** (the lead's question). The engine and `binding.solve` share the dual
    formulation. `primal.py` minimises the species-space Gibbs energy by Newton on the reaction
    extents, with exact conservation by construction and a start built from the totals alone.
    It forms no β and imports nothing from `binding`: it shares only the registry's μ°/RT and
    the forms' counts.
    - Its own certificate is every formation ΔG/RT ≤ 2.6e-51.
    - It agrees with the dual to 2.6e-51 in ln of every species, at all 70 states, S4[10]
      included.
    - A planted K off by 1e-6 in its inputs is caught (a test).
    - The earlier second routes, nested bisection and manufactured solutions, both share the
      dual's formulation.
  - Three tests added (binding: 9); the earlier inputs and values are unchanged.
- **18 November 2026, 20:12 UTC, amendment C2, the convergence scale, before any output of the general
  closure** (§19 amended at 19:52 UTC):
  - **The criterion:** |g_L| ≤ 1e-13 V A_L, with A_L = x_L + Σ_B Σ_f |n_{L,f}| c_f at the
    speciation, in place of 1e-13 |T_L|. Each state now records `residual_scale_fmol` (V A_L),
    `residual_rel` (|g_L|/(V A_L), which replaces |g_L|/|T_L|) and `totals_over_scale`.
  - **The solution floors** `floor_residual_1e-13` are restated on that scale, and so is the
    planted conservation error, now 1e-10 of V A_L. They are identical wherever every count is ≥ 0.
    So S1, S2, S3, S5 and S6 are unchanged to the last digit; only S4's values moved, because
    `pi2_PO4` has a count of −1.
  - **One state added,** appended as S4[12] `near_zero_H_total`. There the H total nearly cancels:
    the bound protons of nuc4, nuc3 and pi2_H against pi2_PO4's −1, so |T_H| = 1e-9 V A_H.
    - On the |T_L| scale the tolerance would be 4.5e-7 ulps of the residual's terms, which no
      solver can meet. On V A_L it is 450 ulps.
    - This package's own Newton never converged there on the |T_L| scale. It was moved to V A_L
      here.
    - Earlier states' solutions are unchanged to their printed digits.
    - The pair S4 (11, 12) joins amendment C1's plants, and the primal route agrees there to
      1.3e-55, so it now covers 71 states.
  - **The correction to 17:33:** the per-ligand floor Σ T_B min n is necessary but not sufficient
    for mixed-sign counts. The joint condition is the closure's own validity. In the registered
    systems every n_L-minimising form binds no other ligand, so P1b's registered floor is
    attained jointly.
  - One test added (binding: 10).
- **18 November 2026, 20:21 UTC, amendment C3, the envelope's two-ligand kinetic reference, before any
  output of the general closure** (§19 amended at 19:52 UTC; B4's Appendix A.2 generalised):
  - **`envelope.py`:**
    - the unit-step network, with k_on per (binder, ligand);
    - the first-order lag δ = −K⁻¹ P D at 60 digits, with K = −N diag(F) Nᵀ W;
    - the full nonlinear network under a constant drive, integrated by Radau and by BDF. Its lag
      is measured against the closure at each state's own totals.
  - **Eight registered cases** (`seam_c.envelope`, every value synthetic). The registry gains one
    binder, `coop2`, a cooperative two-proton chain (pK 1 then 13, so its singly protonated form
    is scarce at every pH) with Mg²⁺ on its base. It joins no system of S1–S6.
    - **E0_b4:** one two-form buffer. The general lag equals B4's formula exactly.
    - **E1_chain:**
      - the network's slowest mode, 78 s⁻¹, is 0.077 of the slowest single step;
      - the true first-order lag is ΔpH 1.63e-3, outside the 1e-3 budget, and the kinetic run
        gives 1.62e-3;
      - a per-step minimum λ gives 1.28e-4, inside the budget. That is the plant, 12.7 times
        non-conservative.
    - **E1_chain_small** (a tenth of the drive): the kinetic run meets the first order 9.95 times
      closer, at second order.
    - **E1_chain_kon10 and _kon100:** the lag falls exactly 10 and 100 times, so the closure is
      the limit.
    - **E1_chain_two_drives:** H⁺ and Mg²⁺ driven together.
    - **E2_nuc4 and E2_nuc4_binder_drive:** a two-ligand binder without a bottleneck, the second
      with a moved binder row. A per-step minimum is conservative there.
    - Radau and BDF agree to 1e-11 in ln x.
  - **Plants:**
    - the per-step minimum λ: the budget's verdict flips on E1;
    - a k_on that ignores the ligand: up to 1.19 on Mg²⁺;
    - k_on swapped between ligands: up to about 1e3;
    - a planted binder with a form not reachable by unit steps, refused. Every registered binder
      is admitted.
  - A test file added (envelope: 5 tests). Earlier inputs and values are unchanged. The registry's
    new binder is appended, and its form valences join the parse table
    (`seam_c.parse.form_valences.coop2`), which covers every registry binder.
- **18 November 2026, 22:50 UTC, amendment F4, the external review's finding 4, before any engine
  comparison of seam A's slopes.** The finding was verified at main by an independent agent;
  this package read only its evidence (f4_planted.py, f4_floor_only.py and f4/).
  - **The fault:** the slope check compared relatively and skipped every pair whose exact slope
    is 0. A dropped Dual seed gives exactly that 0, and all of the three neutral laws' voltage
    slopes were skipped. Nothing was hidden: each difference was also exactly 0, but the check
    was empty there.
  - **The fix:** |x − y| ≤ 10 τ for every pair (`api.slope_pairs`, `api.slope_agreement`), now
    at every state, not the first four.
    - τ = (terms + 8) u M/h is the central difference's rounding at 60 digits, with u = ½ 10⁻⁵⁹
      and M the differenced function's magnitude, after the verifier.
    - All 1,592 pairs at 251 states are within 0.221 τ, a 45× margin.
    - 139 pairs have an exact slope of 0. The 69 with τ = 0, the neutral laws' conductances,
      are exactly 0.
  - **The same class elsewhere,** each now compared absolutely against a floor from its term
    sums:
    - `method_agreement`: j± by trees against minors, through the elimination's running error
      bound (`exact.det_running`); the occupancies against the master equation's solve
      (`exact.solve_running`); and each edge against its cycles. All are within 0.051 of
      their floors;
    - `basis_signs`: within 0.0056, and the zero Hill total at the unit state is compared;
    - A1's backward fluxes: no `J_minus > 0` filter, with zero cases counted;
    - `summarise`: an undefined deviation (None, from `_rel`'s zero reference, or from
      `oneway_plants`) is weak, listed and counted, never dropped.
  - **The values file is unchanged byte for byte.** Only the design file's checks and
    weak-state lists moved; one weak list grew, S4's masked-ideal plant now listing its
    undefined pairs.
  - **The verifier's four plants are tests** (cycles: 13): a dropped V seed, a spurious response
    at a zero slope (100 τ fails, 0.1 τ passes, 1e-40 pS at a zero floor fails), a route's j⁺
    dropped to 0, and a zero Hill total hiding a basis total.
- The booked closure term follows the binding owner's statement, by a dated amendment (§19 item
  3).

## Tests

All three files are tier 1. Their rows were measured at 1b607df4 on the timed lane (CPU 4, one
thread per core, under its lock) and folded with `scripts/test_tiers.py tiers --base`: binding 2.22
s, cycles 0.67 s, registration 0.92 s. The record is
`/mnt/workspaces/Cells/core-seams-references-20261118/gate-1b607df4/tiers/measure/measured.json`.
After amendments C1–C3, the changed and new files were re-measured at 56dedfba the same way:
binding 2.52 s (10 passed), envelope 1.42 s (5), registration 1.07 s (4). The record is
`/mnt/workspaces/Cells/core-seams-references-c-20261118/gate-56dedfba/tiers/measure/measured.json`.

| File | Tests | What it holds |
| --- | --- | --- |
| `tests/unit/test_core_seams_references_cycles.py` | 9 | Seam A's machinery, amendment 1's finite fuel and N = b included, each test with its plant |
| `tests/unit/test_core_seams_references_binding.py` | 6 | Seam C's, each test with its plant |
| `tests/unit/test_core_seams_references_registration.py` | 4 | The inputs equal their generator, sampled values recompute, the registered power holds, and no engine import |
| `tests/unit/test_core_seams_references_envelope.py` | 5 | Amendment C3: B4's reduction, the chain's non-conservative per-step bound, second order and 1/k_on, a shared k_on, and reachability |

## Sources

Numbers are used under D186 and D201. No text, figures or data are copied.
- **Cycle-flux decomposition:** T. L. Hill (1989) and E. L. King and C. Altman (1956), cited as
  CORE_SEAMS_DESIGN cites them, unread. The decomposition is self-verified above.
- **The all-minors matrix-tree theorem and the convexity of the speciation's dual** are standard
  results, used as checked here, not cited.
- **The SI's 2019 defining constants.**
