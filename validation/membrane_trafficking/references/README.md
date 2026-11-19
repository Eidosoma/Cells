# FR-2's code-blind references (scheduled_membrane_trafficking@1, version 1)

These are independent reference values for FR-2's checks T3–T6 and T8, with planted controls,
floors and margins. T5 also has compiled closed forms for T7's batch worlds. Nothing here imports
`cells`.

## Registration

**When.** Registered on 2026-11-19 at 04:55 UTC, before any comparison with engine
output. The branch is `fr2-references`, from main 6ca4a56f.

**What was read:**
- design statement 1 (the workspace's `fr2-retrieval-v1-20261119/design_statement_1.md`), all
  of it:
  - §12 above all;
  - §13, the builder's answers to my questions, written at 04:31 UTC, with §12 as corrected
    there;
- docs/MEMBRANE_RETRIEVAL_DESIGN.md §0–§12;
- FR-2's entry in docs/FEATURE_REQUESTS.md;
- D217 in docs/DECISIONS.md;
- the builder's declared-inputs file, `fr2-retrieval-v1-20261119/declared_inputs.json`, written
  from fr2-retrieval-v1 c710d841 (clean). That file only, not the script beside it.

**What was never read:** the operator (`src/cells/operators/membrane_trafficking.py`), its tests,
the fixtures, the probes, and any engine output.

**Engine numbers quoted in what was read.** §12 and §13 quote two sets of the builder's measured
numbers:
- the split-order probe's ratios: 4.00, and 1.94 and 1.97 for the Lie split;
- the electrode-sign probe's ratios: 1.000000000000.

I read them only as part of the brief. No reference uses them, and none was changed after reading
them. In particular, my T5 ladder was computed before §13 answered which population the test
uses, and it was not altered by that answer.

**The lead's rulings (19 November 2026):**
1. The references run on the builder's declared worlds (option b), plus two stress worlds of mine.
2. The constants are the exact SI values: F = N_A e, R = N_A k_B, and CHARGE_PER_FMOL = F × 1e-15.
3. T5's reference is the exact solution of the linear ODE, in place of the builder's 20 000-step
   RK4.
4. Register now. The primary comparisons each test makes are recorded as a dated note (below).
   An answer that would change a reference value or a tolerance goes to the lead first.

**Amendments** are made only by dated amendment, and each states whether it came before or after
any engine output.

## Method

**Arithmetic and inputs.**
- 60-digit decimals (`decimal`), reported to 50 digits.
- Inputs are read as the exact values of their doubles, as an engine reading the same numbers holds
  them.
- The declared conventions apply: V = φ_inside − φ_outside, and a node's charge anchor is its
  declared initial charge, moved by CHARGE_PER_FMOL Σ z (n − n0).
  - I checked every declared anchor against CHARGE_PER_FMOL (Σ z n0 + fixed). They agree within
    1.4e-16.

**T4, the dense nodal capacitor solve (`network.py`).**
- Held nodes sit at their potentials.
- Each patch adds C (e_i − e_o)(e_i − e_o)ᵀ.
- Each stage is re-solved densely, and §2.2's closed forms are evaluated beside it from the
  stage's start state:
  - V_b′ = (C_b V_b + dC V_k)/(C_b + dC);
  - V_k′ = (C_k V_k + dC V_b)/(C_k + dC);
  - the merge heat;
  - a held node's electrode transfer, +dC V_k on retrieval and −dC V_b on recycling;
  - the carriers, δ_s = t_s δq/(z_s CHARGE_PER_FMOL);
  - the reservoir work Σ δ (RT ln c_ref + z F φ_h).
- On every registered stage, the dense solve and the closed forms agree within 4e-55. This is the
  references' internal check, not a property of the engine.

**R2's half-step (`trafficking.py`).**
- The half-step is S_ret(h/2) S_rec(h) S_ret(h/2) over all routes at once.
- Units follow N (A′/A)^e, and records follow R (A_b′/A_b)^e_r.
- A stage's heat is shared among its routes by the first-order terms ½ dC (V_s − V_t)².
- A free node's free-energy change is shared by |the amount each route moved there| / Σ|amounts|,
  carrier row by carrier row (§4 and §13).
- A stage where two routes share a patch or a population is refused, since no rule for that is
  stated.

**The units (`units.py`).**
- Each stage has its closed forms.
- Both directions at once follow dN/dt = −r1 e N/A_k + r2 e_r R/A_b, with N + R conserved, and are
  solved exactly:
  - by an integrating factor, with Gauss–Legendre quadrature at 60 digits. Quadrature at 8 × 40
    and at 16 × 40 points agrees to about 1e-59;
  - by a Richardson value from the palindrome at 512 and 1024 steps, which agrees with the exact
    solution within 1.6e-15.
- The palindrome and the Lie split are composed exactly from the closed forms.

**T8.** The factor is F × availability × abundance × area in m², with abundance = N/(A ρ) (§13).

## What is registered (`designs/`)

`membrane_trafficking_reference_values.json` holds the following, per registered drive (the
operator-level tests' declared drives, and my stress drives).

**For every half-step:**
- each stage's report;
- the sums the tests read:
  - ΔG_chem, ΔU_view, the heat (dense and closed form), W_res and W_elec (dense and closed form),
    and the carriers' work, total and per route;
  - the electrode transfer per held node, signed and absolute;
  - the reservoir supply, and the net carriers moved into each outside node;
  - the residual and the largest |term|;
- the state after the half-step: potentials, voltages, areas, capacitances, amounts, units and
  records;
- the T4 closed forms over the half-step: V_b′ or V_k′, the heat, R1's shift and R1's potentials;
- T3's sums;
- the floors.

**T5:**
- the operator-level cycle, half-step by half-step, with the e and e_r plants;
- both directions at once: for Kir and for NaV, the exact N and R at 4 ms, and the palindrome's and
  the Lie split's N, R, relative error and error ratios at n = 8, 16, 32 and 64;
- the compiled cycle's closed forms at each observation;
- the same closed forms for T7's batch at r = 0.05, 0.1 and 0.15.

**T8:** for every population:
- the start, ½ × availability × abundance × A0 in m². §12's superseded ½ × availability × N0 in
  units is kept, labelled as superseded;
- at each observation: A(t)/A0, N(t), the factor, the start × A(t)/A0, and the two plants.

`membrane_trafficking_reference_design.json` holds the plants, the floors, the floor flags, the
zero-power list and the primary comparisons.

**Headline values** (the comparison uses the 50-digit values in the files):

| Check | World and drive | Reference |
| --- | --- | --- |
| T4 retrieval, held bath | held_bath_cell, 0.03 A_k | V_b′ = −29.8336 mV, H = 9.67558e-4 pJ; R1's owner shift = −2.46050 mV |
| T4 retrieval, free node | cleft_cell, 0.03 A_f | V_b′ = −4.50318 mV, H = 1.46047e-4 pJ; φ of everything but the pool unchanged |
| T4 recycling | held_bath_cell, 3 × 0.02 then 0.2 A_b | V_k′ = −78.7293 mV, H = 2.29195e-4 pJ, V_b unchanged |
| T5, both directions | Kir, r1 = 0.05 A_k0/dt, r2 = 0.4 A_b0/dt, 4 ms | N = 2888.780911958127; relative error 1.3759e-4 at n = 8 and 3.4418e-5 at n = 16; ratio 3.9976, and 1.9358 for the Lie split |
| T5, both directions | NaV (extra) | N = 3014.047960527597; ratio 3.9694, and 1.9017 for the Lie split |
| T6, held bath at 20 mV | held_bath_cell, 0.03 A_k | ΔG_chem 3.42387e-3, ΔU −9.67558e-4, W_res 4.20202e-3, W_elec −7.78364e-4, W_carriers 2.16850e-7 pJ |
| T6, two routes | two_routes_one_cleft | shares 1/3 and 2/3 of the cleft's ΔG (−5.13524e-4 pJ); W_carriers 8.678e-9 and 1.844e-8 pJ |
| T8 | t8_sheet, every Kir | start = 1.630636082808453e-10 m²; A(t)/A0 = 1, 0.975, 0.95, 0.925 and 0.9 |

## The planted controls, and their margins against the tests' bands

A margin is the deviation divided by the band. The band is max(the test's tolerance, 10 × the
floor), taking the floor under its conservative model: absolute storage for T4's potentials, and a
naive difference of totals for T6's ΔG_chem (see Floors).

| Plant | Check | Cases | Smallest margin | Where it is weak |
| --- | --- | --- | --- | --- |
| R1 at a held bath: the owner moves by V_k dC/(C_k − dC) | T4, every potential but the pools' unchanged | 18 | 1.4e9 | none |
| R1 at a free node: the cleft moves by −V_k dC/(C_k − dC) | T4 | 3 | 7.7e8 | none |
| The carriers without their valence | T4 | 21 | 4.1e8 in the stress worlds | the declared worlds: both carriers are +1 |
| A merge heat of the wrong sign | T6 residual | 33 | 2.9e7 | none |
| The electrode work with the wrong sign | T6 | 29 | 4.0e7 | none (zero at 0 V baths) |
| The reservoir work without z F φ_b | T6 | 29 | 2.0e7 | none (zero at 0 V baths) |
| The carriers' work with the wrong sign | T6 | 33 | 1.7e4 | none |
| The two transference numbers swapped | T6, the carriers' work | 33 | 6.5e5 in the stress worlds | the declared worlds: t = 0.5 and 0.5 |
| The whole cleft change on one route | T6, per-route work | 2 + 2 | 5.9e7 | none |
| A unit dropped from the record | T3, at relative 1e-14 | 32 | 2.7e10 | none |
| e or e_r off by 1 part in 10⁶ | T5, the closed forms per half-step | 16 | 1.0e5 | none |
| The Lie split | T5: ratio < 2.5, palindrome within (3.5, 4.5) | Kir | ratio 1.9358 against 3.9976 | none |
| T8 without the coupling | T8, relative 1e-12 | 35 | 1e12 | none |
| T8 without the retrieval | T8 | 35 | 2.6e10 for t > 0 | t = 0, before any retrieval |

Every weak case is listed in the design file's `weak` and `weak_at`. Each is in the zero-power list
by construction.

## Floors (the F4 lesson)

The design file registers a floor beside each check's tolerance, half-step by half-step:
- T4: every potential's change against 1e-12 of max|φ| (retrieval half-steps only, since the owner
  moves on recycling), V_b′ and V_k′ against relative 1e-12, V_b kept on recycling, and the heat
  against relative 1e-9;
- T6: the residual and the carriers' work.

Each floor is the worst-case rounding of a float64 engine.

**Two models for each, because the operator's code is not read.**
- **T4, how a node's charge is formed:**
  - `absolute_storage`: as F Σ z n plus its fixed part, from stored absolute amounts. That sum
    cancels: the declared cell holds 213 fmol of ions for a net 0.013 fmol, and a pool holds
    15 fmol for a net of 0 plus the carriers' 1e-4.
  - `increment_storage`: as the anchor plus F Σ z (n − n0), from stored increments. §3 names the
    carriers' write `extracellular_amount_increment`.

  In both, the rounding acts through K⁻¹. For a potential's change, a node whose amounts did not
  move carries the same rounding before and after.
- **T6, how ΔG_chem is formed:**
  - `naive_difference`: as a difference of two float64 totals;
  - `stable_change`: as a change computed to a few roundings of its own size. §4 calls the
    adapter's change exact.

**Flags, each conditional on its model:**
- Under `absolute_storage`, 60 of T4's floors exceed the 1e-12 voltage tolerances:
  - the unchanged potentials reach 1e-12 to 6e-12 of max|φ|;
  - V_b′, V_k′ and the kept V_b reach 8e-12 to 2e-10 relative.
- Under `increment_storage`, none do. The floors there are 1e-15 to 3e-14, and the heat's at most
  2.4e-12.
- Under `naive_difference`, T6's residual floor exceeds its band on 3 half-steps, and the carriers'
  work floor exceeds its band on 23 cases. Under `stable_change`, none do.

The builder's tests pass at the stated tolerances, which suggests the second model of each. The
first is registered as a possibility, not as a finding about the tests. The plants' margins use
the conservative model's band, so they hold under either.

**Recorded later.** Which model is the engine's (is a free node's charge row built from absolute
amounts or from base plus increment, and is ΔG_chem a difference of totals?) only selects a band.
Its answer will be recorded as a dated note.

## Zero power (what these references cannot see)

- **The potentials and the heat in the compiled worlds** (cycle, t8_sheet). They depend on the
  pumps, leaks and channels, which are not modelled here. There, only units, areas and
  capacitances are referenced.
- **T1's refusals, T2's idleness, and T7's restart and batch equalities.** These are rules and
  bitwise equalities. T7's batch worlds get T5's closed forms only.
- **A dropped valence or swapped transference numbers in the declared worlds,** whose carriers are
  +1 at t = 0.5. The stress worlds carry these plants.
- **The per-species against the per-total sharing of a free node's free energy.** The declared
  shared cleft's routes move K and Na in one ratio, 1:2.
- **The φ_b parts of the electrode and reservoir work at a bath held at 0 V.**
- **Recycling into a patch on a free node,** for which the heat has only the dense route. No
  registered drive does this.
- **Per-route heats among several routes.** No test compares them (§13). They are registered as
  the §4 share.

## The stress worlds (approved by the lead, 19 November 2026)

`stress_held_bath` and `stress_cleft` are derived from `held_bath_cell` and `cleft_cell` by the
changes listed in `reference_inputs.json`:
- the pool at 20/120/130/10 mM Na/K/M/P, with its anchor −C_b × 40 mV, so V_b starts at +40 mV,
  against V_k ≈ −80 mV;
- in `stress_cleft`, the cleft at 100/40/120/20 mM;
- the carriers K at 0.75 and M (z = −1) at 0.25;
- in `stress_held_bath`, the enrichments e of 1 for Kir and 0.5 for NaV, e_r of 2 and 1, and R0
  of 400 and 200 units.

The drives are explicit half-steps:
- `stress_held_bath`: retrieval 0.03, recycling 0.2, both at once (0.02 and 0.1), and a cycle;
- `stress_cleft`: retrieval only.

**One departure from the approved design:** the transference numbers are 0.75 and 0.25, not 0.7
and 0.3. As doubles, 0.7 + 0.3 is 1 − 5.55e-17, so the carriers would not carry exactly the moved
charge, and the dense solve and closed forms would disagree at 1e-16. The binary-exact pair keeps
the same power: unequal transference numbers, and an anion.

## Primary comparisons (dated note, 2026-11-19, from §13, before any engine comparison)

**T3:**
- N + R = N0 + R0 per population;
- the per-cell sums of dA and dC are zero;
- the dropped-unit plant deviates by 1 unit.

**T4,** after one half-step:
- every potential but the pools' is unchanged (1e-12 of max|φ|);
- V_b′ (retrieval) or V_k′ (recycling) matches its closed form (relative 1e-12);
- the single route's booked heat (share 1) matches C_b dC (V_b − V_k)²/(2 (C_b + dC)) (relative
  1e-9);
- R1's owner shift is V_k dC/(C_k − dC) (relative 1e-9).

Against these references, use the band max(tolerance, 10 × floor).

**T5:**
- the operator-level cycle's N and R per half-step match the closed forms (relative 1e-13), and
  N + R is conserved (1e-14);
- both directions at once, on Kir's plasma N only, as relative error at 4 ms with n = 8 and 16:
  - 3.5 < err(8)/err(16) < 4.5, and err(16) < 1e-4;
  - the Lie plant's ratio is below 2.5;
  - here, also the scheme's own N at n = 8 and 16, to float64 floors;
- compiled: the closed forms hold at each observation (1e-12).

**T6,** per half-step:
- |ΔG_chem + ΔU_view + H − W_res − W_elec − W_carriers| ≤ 1e-9 max|term| + 1e-18 pJ;
- the carriers' work matches the independent value (relative 1e-6, absolute 1e-15 max|term|);
- a held bath, on retrieval:
  - electrode transfer = −F Σ z × supplied;
  - electrode work = φ_b × the transfer (1e-14);
  - reservoir work = 1e-3 Σ μ × supplied (1e-12);
- two routes: each route's work is its pool's change plus its |amount| share of the cleft's
  (1e-6), and the shares are 1:2 (1e-3).

**T8:** F × availability × abundance × area per Kir population, in m², equals the start × A(t)/A0
(relative 1e-12). The start is ½ × availability × abundance × A0 (relative 1e-14).

## Regenerating

```
python -m validation.membrane_trafficking.references.worlds DECLARED_INPUTS.json  # re-freeze
python -m validation.membrane_trafficking.references.design                       # write
python -m validation.membrane_trafficking.references.design --check               # compare
```

The design takes about 2 s on one CPU. tests/unit/test_membrane_trafficking_references.py checks
the registered files and the references' internal agreement.
