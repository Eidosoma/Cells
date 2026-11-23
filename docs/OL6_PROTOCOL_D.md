# OL6 Protocol D: the deterministic representation against exact events (registration)

**Status: proposed for registration, 23 November 2026, for the lead.** Docs and validation only, with
no src change. Branch `ol6-protocol-d` from main 07ab2e5c. It is to be tagged before any comparison of
`cells.rate_equations@1` with exact events is computed. The proposed tag is
`ol6-protocol-d-registered-2026-11-23`.

**One proposal is open.** §7.3 proposes a change to the pore clock's bound, which D7 needs. It is
marked as a proposal and is for the lead's review (with the user's, if it changes a guarantee)
before the tag. D0–D6 do not depend on it.

**Sources.**
- The design: docs/OL6_DETERMINISTIC_REPRESENTATION_DESIGN.md §5.1 (tag `ol6-design-note-2026-11-22`).
- D304, and the lead's rulings for S5:
  - the clock bound stays as designed, ruling (a);
  - σ-from-F worlds declare tight tolerances;
  - a change to the bound can only be proposed here, before Protocol D is read.
- The builders' log, `/mnt/workspaces/Cells/ol6-20261122/STATE.md`, and its clock-convergence table.

**What is registered.** The tag holds three files, read byte for byte as tagged:
- this document, which is the authority;
- `validation/assembly_lineages_v2/limit_qualification.py`, its arithmetic:
  - the worlds and both representations' definitions;
  - the observables, read from either representation's rows by the same engine functions;
  - the criteria as functions of arrays, and n_min's rule;
  - the plants' mechanisms;
  - P-D5's closed-form world;
- `validation/assembly_lineages_v2/protocol_d.json`, every number, and the plants' effects computed in
  (d) alone before the tag.

**Engine models (AGENTS.md).**
- **The representation under test:** `cells.rate_equations@1` (interface
  `cells.assembly_representation@1`), with the method `rosenbrock_rodas4_dense@1`.
- **The detailed form:** `cells.assembly_lineages@2`'s exact events.
- **Each world's laws** are listed in §2 and in the JSON's `engine_models`.

**The engine under test.** The checker runs at the first main head that holds S2, S3 and S4 (D4–D7
need all three), with the tagged files unchanged. It records the revision and every changed file of
`assembly_lineages_v2/` since 07ab2e5c. A src fix made after any reading needs an amendment, tagged
before the re-run, and the first verdicts stay in the record.

## 1. The claim

Where its envelope admits a world, (d) is the large-count limit of that world's exact events:
- **Means** converge to the exact means, with a bias of order 1/N.
- **Single trajectories** stay within O(N^(−½)) of (d)'s.
- **Events** (lysis at σ_max, a pore's opening) converge in mean, and their spread falls with N.
- **(d)'s own ledgers close.**
- **The envelope's n_min** follows from the results by the rule of §6.

Not claimed (the note's §5.4):
- the anchors' scale, above the top rungs;
- FR-39's Phase B;
- an independent ODE reference.

## 2. The worlds

Every parameter is in `limit_qualification.py` and in protocol_d.json. "Ω" is the system size, and
the vesicle rungs are diameters.

| World | What it is | Laws (beside ideal mixing) | Rungs | Replicas |
| --- | --- | --- | --- | --- |
| **D0** | The sparse plant, P4's world. Closed 2A ⇌ B at T = n_A + 2n_B = 12 and qT = 4 (X = 12, μ°_B = −ln 4), its founder at the fixed point rounded, (4, 4). Times 5 to 40 s, every 5 s, at least 7 relaxation times apart | `cells.stochastic_mass_action@1` | One | 256 |
| **D1** | Dilute A + B ⇌ C and 2A ⇌ D in a finite pool with X = Ω. Founders (0.5, 0.3, 0.1, 0.1)Ω, relaxing to (0.4, 0.25, 0.15, 0.125)Ω, so every place stays at or above 0.1Ω. One inert membrane molecule | Mass action | Ω = 1000, 4000, 16000, 64000 | 256 |
| **D2** | Four types join a membrane from held pool places (Σ K_i ρ_i = 1.5, so N grows), catalysed by GARD's lognormal factor (β from seed 20261124, recorded), with T0 + T1 ⇌ C in the membrane (order 2 there). Founder (0.3, 0.25, 0.25, 0.1, 0.1)Ω; N about doubles by 0.4 s. `multinomial`, `kept` | Mass action, `cells.transition_state_factor@1` | As D1 | 256 |
| **D3** | Three types between a finite pool (X = Ω) and a membrane, with regular mixing (χ = +1.5 and −1.5), relaxing to equilibrium by 4 s | Mass action, `cells.regular_mixing@1` | As D1 | 256 |
| **D4** | A floppy vesicle (V_osm/V_sph = 0.9) whose lumen takes up a permeant S from a held pool (480 mM, outside osmolarity 600 mM), through the lumen's kink, to lysis at σ_max = 3 mN/m. L exchanges with a held pool at its floppy equilibrium. Rtol 1e-12, atol_count 1e-9, as D7's twin | `cells.bilayer_geometry@1`, `cells.phase_exchange@1`, `cells.membrane_permeation@1`, `cells.osmotic_lumen@1` | d = 25, 50, 100 nm (N ≈ 1.3 × 10⁴, 5.2 × 10⁴, 2.1 × 10⁵ amphiphiles at 0.3 nm² per leaflet) | 128 |
| **D5** | Two vesicles on one finite pool of L, one tense (x0 = 1.43, σ ≈ 2 mN/m) and one floppy (0.85): A1's mechanism at small scale. The tense one gains about 4% of its amphiphile by 60 s | Geometry, exchange, lumen, `cells.shared_pool@1` | As D4 | 128 |
| **D6** | A floppy vesicle (v = 0.6) in a finite pool of L at its equilibrium, split at a shear time of 1 s (k = 2, continuation `first`) | Geometry, exchange, lumen, `cells.shear_fission@1` | As D4 | 128 |
| **D7** | D4 with the pore law and σ from F, paired with exact events by each vesicle's domain-7 threshold E. ln(A ν_A) = 34 and Γ = 4.5 pN (σ_β/4 = 3.9 mN/m ≥ σ_max). It needs §7.3's proposal (§7.4) | D4's laws, `cells.pore_nucleation@1` | As D4 | 128 |

**The ladder starts at Ω = 1000, not the note's 250.** At Ω = 250, D1's smallest place holds 25.
- n_min could then come out at 25, where c_r/√25 = 1.0.
- D0's per-replica spread at its 99th percentile is about 1.1 (§8), so P-D1 would not fail.
- From Ω = 1000 the smallest count the ladder can output is 97 (D3's pool U2 at Ω = 1000). That
  holds P-D1's margin at 2.2 or more, whatever the results.

**Observation times** (8 per world and rung, `TIMES` in the module):
- **D1 and D3:** 0.25, 0.5, 0.75, 1, 1.5, 2, 3 and 4 s.
- **D2:** 0.05 to 0.4 s, every 0.05 s.
- **D5:** 7.5 to 60 s, every 7.5 s.
- **D6:** 0.25, 0.5, 0.75, 1.25, 1.5, 2, 2.5 and 3 s, so none falls at the shear.
- **D4 and D7:** placed per rung from (d)'s kink t_k and lysis t* (the sizing of §12):
  - three times at (0.3, 0.6, 0.9) t_k;
  - then five at t_k + (0.2, 0.4, 0.6, 0.8, 1.0) × (0.75 t* − t_k);
  - the horizon is 2 t*.
  - (t_k, t*) = (0.065, 0.378), (0.13, 0.384) and (0.26, 0.492) s at 25, 50 and 100 nm.
- **Seeds:** 1 to M, with environment 0, lineage 0 and branch 0. The retry's seeds are 100001 to
  100000 + M.
- **The exact runs' settings:** `molecule_capacity` is the power of two above 4 × the founder's
  total, `chunk_events` 4096, and no event limit before the horizon.

## 3. Observables and scales

**The observables** (`observables`), at the 8 registered times, from each representation's own
rows:
- the count of every enveloped place, the places `rate_equations.enveloped` marks;
- in the vesicle worlds, A, V and σ:
  - all three come from one function, `vesicle_derived`, for both representations;
  - it calls the engine's own `lumen.log_volume` and `lumen.tension` on real N_L and W, with A = qW/2;
  - in D5 they are taken per slot;
- `W_res` (the reservoir work) where it is nonzero, in D2, D4 and D7;
- the event time per replica (`event_time`): D4's lysis at σ_max, and D7's pore opening.

The host helpers `lumen.host_tension` and `lumen.host_volume_L` truncate counts to integers, so they
are not used.

**The scales.**
- **s_y** is the largest |y_d| over the founder and the registered times. A growing place's scale
  is then its largest value, so growth does not inflate its relative spread (§5.3).
- **n_k** is the smallest count of any enveloped place along (d)'s trajectory at the founder and the
  registered times, over every slot.
- Both come from (d)'s own run, so neither reads an exact result.

**An early end.** In D4 and D7, an exact replica that ends before the last registered time
fails a precondition (§9), and the world is inconclusive. A replica's value at a time after its own
end is NaN and enters no statistic.

## 4. The stated error terms

Every tolerance below is derived from these terms, and none from a result:
1. **Sampling.**
   - The SE of a mean over M replicas.
   - The relative SE of an RMS over replicas, at most 1/√(2M) in ln D. That is the worst case,
     with every term within a replica fully correlated.
   - The relative SE of a standard deviation, 1/√(2(M − 1)).
2. **The limit.**
   - A mean's bias is O(1/N), by van Kampen's system-size expansion (from memory).
   - A trajectory deviates by O(N^(−½)), by Kurtz's limit and the linear-noise approximation.
3. **The integrator.**
   - The density worlds run at rtol 1e-10 and atol_count 1e-6. The vesicle worlds run at rtol
     1e-12 and atol_count 1e-9.
   - So the error is at most about 1e-8 of a scale, against SE of about 5e-4.
4. **Crossings.**
   - The Illinois locator runs to 1e-13 in θ.
   - The re-step's guard is accepted within 10(atol + rtol·scale).
   - The pore clock's error is bounded per step (§7).
5. **Rounding,** about 1e-15.

## 5. The criteria

### 5.1 P: pathwise order (D1–D3)

- **The statistic:** D_k is the RMS, over replicas, times and observables, of (y_a − y_d)/s_y at
  rung k (`pathwise_rms`).
- **Pass:** the least-squares slope of ln D_k against ln Ω_k over the four rungs lies in
  [−0.6, −0.4] (`criterion_p`).

**The window's derivation (S).**
- SE(ln D_k) ≤ 1/√(2 × 256) = 0.044.
- With four rungs a factor of 4 apart, Σ(x − x̄)² = 9.61, so the slope's SE is 0.044/√9.61 =
  0.0142.
- At z* = 4.5 that is 0.064.
- The O(1/n) corrections at the bottom rung (n ≥ 97) are at most 2/97 in ln D, which shifts the
  slope by at most 0.004.
- So the half-width needed is 0.068, rounded up to 0.1. The note's was 0.15.

A model error ε puts a floor under D_k, which flattens the slope toward 0 and fails.

### 5.2 M: means converge (every world, on its top two rungs)

**The statistic.** For each registered (observable, time), e_k = mean_a − y_d, with SE_k from the
replicas (`mean_error`, `criterion_m`).

**The test, at the top rung K:** the largest excess, (|e_K| − |e_(K−1)|/2) / (SE_K² + SE_(K−1)²/4)^½.
- It **passes** at most z* = 4.5.
- It is **inconclusive** between 4.5 and 6, and takes the retry.
- It **fails** beyond 6.

**Why.**
- The limit's bias falls by 4 per rung, so at least half the previous rung's error remains as
  allowance. No bias constant is guessed.
- A model error ε does not fall. It fails once ε passes about 12 combined SE: 7 × 10⁻³ of its scale
  at Ω = 64,000 with M = 256.

**The false-alarm bound (S, corrected from the note).**
- The excess is at most |n_K| + |n_(K−1)|/2 of noise, which by Cauchy–Schwarz exceeds z times the
  combined SE with probability at most exp(−z²/2).
- That is 4.0 × 10⁻⁵ at 4.5 and 1.5 × 10⁻⁸ at 6, not the two-sided normal tail.
- Over about 350 comparisons in all, a false retry has probability at most 1.4% and a false fail
  5 × 10⁻⁶.
- The bias's order across all rungs is reported, as a description.

### 5.3 B: the error budget at each rung (every world and rung)

`criterion_b` checks two things per observable:
- **The mean:** |e_k| ≤ z* SE_k + b s_y/n_k, with b = 2.
- **Each replica:** the 99th percentile over replicas of max over the 8 times of |y_a − y_d|/s_y
  is at most c_r/√n_k, with c_r = 5.

**c_r's derivation (S).**
- At the 99th percentile over 8 times, the union bound gives a two-sided z of 3.23 (0.125% each).
- Under the linear-noise approximation, Var(y)/s_y² ≤ κ/n_k, where κ is the observable's Fano
  factor relative to the smallest count. The choice of s_y (§3) keeps that inequality for growing
  and shrinking places alike.
- So c_r = 3.23 √κ_max. The declared bound κ_max = 2.4 (an SD 1.55 times Poisson's) gives c_r = 5.

**b** is a declared bound on the system-size expansion's O(1) mean correction, in molecules relative
to the smallest count, for propensities of order at most 2. P4's dimerization has 0.072.

b and c_r are the envelope's promise. They are tested, not derived from results. Each world's
smallest passing b and c_r are reported (`b_needed`, `c_r_needed`).

**A world outside the envelope** is held to the envelope's budget, with n_k = n_min
(`criterion_b_at`).

### 5.4 E: events (D4; D7 paired by E)

**D4.**
- M is applied to mean(T_a) − t*_d, on the 50 and 100 nm rungs.
- **The spread** must fall: SD_K ≤ 0.75 SD_(K−1) (`criterion_e`). N grows 4 times per rung, so 0.5
  is expected (N^(−½)), or less if the lumen's count dominates.

**0.75's derivation (S).** 0.5 × exp(4.5 × √2/√(2(M − 1))) = 0.5 × exp(4.5 × 0.0887) = 0.745, the
null ratio at 4.5 SE of the log-ratio of two independent sample SDs, with M = 128.

**D7** takes the same two tests on Δ = T_a − t*_d(E) per replica, using RMS(Δ) for the spread.
- Each replica's (d) run draws its own E from domain 7, with the vesicle key 0:0 and the replica's
  seed: the same E as the exact run.
- So D7 has 128 (d) runs per rung.

**Censoring.** The horizon is 2 t*. A censored replica, one with no event by the horizon, fails its
world.

### 5.5 L: ledgers

- **(d) alone, every run:**
  - closure within the note's §2.2 tolerance;
  - moieties to 1e-12, per moiety;
  - the per-step dissipation margin.

  (d) refuses a run whose books do not close, so such a run is a fail of L.
- **Across the representations:** W_res per scale is an observable under M and B.

### 5.6 N: numerics

The builders' closed-form tests are the representation's own, and run in the tier gate at the
checker's head, with their results recorded. This protocol adds two:
- P-D5's identity (§8);
- D7's clock convergence (§7.4).

## 6. The envelope's n_min

- **The rule** (`n_min_rule`): n_min is the smallest n_k among the (world, rung) pairs such that every
  pair with n_k at or above it passes B, with P and M passing over the ladder.
  - It is rounded up to two significant figures and stated in the verdict, with the tag.
  - The representation's declarations then cite it ("Protocol D, criterion B's smallest passing
    rung, <tag>").
- **Its possible values** run from 97 upward.
- **What moves it:**
  - A failure at the smallest rungs moves n_min up a rung. That is an outcome, not a fail.
  - B failing at a world's top rung is a fail.
- **The qualification runs themselves** declare `min_count` 10, with the provenance "Protocol D's
  qualification runs".
- **D0 is refused at parse with it.** Its founder's 4 is below 10, as the author's parse check
  shows. That refusal is §7.1's "a sparse case admitted", the other half of P-D1.

## 7. The pore clock: its tolerances, a finding, and a proposal

### 7.1 As ruled (a)

- **The bound:** H's embedded error estimate per accepted step, |U^H| ≤ 1 × 10⁻¹⁰ absolute
  (`rate_equations.H_ERROR`). A run beyond it is refused, never silently inaccurate.
- **σ-from-F worlds** declare rtol 1e-12 and atol_count 1e-9. D4–D6 take the same, as D7's twins.
- **A property, stated:** the order-3 embedded estimate overstates the crossing time's actual
  error about 200-fold. S3's table, in its σ-from-F test world, has |t*(rtol) − t*(1e-12)| = 1.5e-8,
  2.7e-9, 3.5e-10 and 4.0e-11 s at rtol 1e-8 to 1e-11, with atol scaled. That is about 10-fold per
  decade of rtol, at an error far below what the estimate implies.
- **A (d) run refused by the bound** is inconclusive (numerics) for that replica, never a fail.

### 7.2 The finding, in (d) alone

The bound as ruled cannot run D7 above 25 nm. These runs are measurements, made with the bound
disabled where so marked (`/mnt/workspaces/Cells/ol6-20261122/protocol-d/clock_*.json`):

| D7, ln(A ν_A) | Rung | rtol | Outcome | Largest estimate | Largest (estimate − 1e-10)/ΔH |
| --- | --- | --- | --- | --- | --- |
| 30 | 25 nm | 1e-12 | Runs: 12 seeds, 6 open by pore and 6 lyse at σ_max | 9.0e-11 | 0 |
| 30 | 50 nm | 1e-12 | Refused at 1.01e-10; measured, 5.1e-10 | 5.1e-10 | 1.4e-6 |
| 30 | 50 nm | 1e-13 | Runs: 12 seeds, 5 open by pore and 7 lyse at σ_max | 5.1e-11 | — |
| 30 | 100 nm | 1e-12 and 1e-13 | Refused at 1.13e-10 and 1.0e-10; measured, 4.0e-9 | 4.0e-9 | 5.7e-5 |
| 34 | 25, 50, 100 nm | 1e-12 | Measured: 12 of 12 seeds open by pore at every rung | 4.9e-9, 2.8e-8, 2.2e-7 | 4.0e-6, 3.4e-5, 5.3e-4 |

- **Why rtol does not help.** H is integrated by the state's own stages but kept out of step
  selection (§3.5 of the note), so that a pore world steps exactly as its pore-free twin. The steps
  are therefore chosen by the state alone, and k_v = exp(−σ_β/σ …) varies by a large factor within
  one of them near the opening. A tenfold smaller rtol barely moves the estimate (1.13e-10 to
  1.0e-10 at 100 nm).
- **Why a slower pore does not help either.** At ln(A ν_A) = 26 the estimate passes (7.3e-11 at
  100 nm), but then no replica opens before σ_max.
- **What D7 needs.** Every replica should open by pore, so that a replica cannot end by different
  causes in the two representations.
  - That needs H(t_σmax) far above the largest of 128 thresholds, about 5.4.
  - At ln(A ν_A) = 34, measured just before σ_max at 0.999 t*, H is 38, 26 and 22 at the three rungs.
    A threshold lysis then has probability e⁻²² ≈ 2 × 10⁻¹⁰ per replica.

### 7.3 PROPOSAL (for the lead's review, and the user's if it changes a guarantee): a relative clock bound

**The bound:** |U^H| ≤ 1 × 10⁻¹⁰ + c·|ΔH| per accepted step, with c = 2 × 10⁻³.
- ΔH is the step's own increment of H.
- The engine change is one line in `rate_equations` (the bound) and its refusal's words, plus a test
  row. It is an S3 follow-up, to land before Protocol D runs.

**Its derivation (S).** Sum the per-step bound up to the crossing, where H = E:
- The accumulated error is at most n·10⁻¹⁰ + c E.
- The crossing time's error is that divided by k_v(t*).
- While k_v does not fall before t* (a rising tension), E = ∫k_v dt ≤ k_v(t*) t*.
- So the crossing time's relative error is at most c + n·10⁻¹⁰/E, by the estimate.

**The constant's reason.**
- **Room to run D7:** c is 3.8 times the largest ratio measured, 5.3e-4 at 100 nm, which 12 seeds
  found.
- **A guarantee inside the representation's own promise:** by the estimate the crossing time is
  within 2 × 10⁻³ relative. That is at most the envelope's mean budget, b/n_min = 2/n_min, for any
  n_min up to 1,000.
- **And far tighter in fact.** By S3's measured overstatement (§7.1), the error is about
  1 × 10⁻⁵. In D7 itself, t* moves by at most 1.1 × 10⁻⁸ relative between rtol 1e-12 and 1e-13
  (§7.4). D7's own convergence check verifies that against each rung's resolution at the run.
- **The absolute part stays at 10⁻¹⁰.** That governs the steps before the opening, where ΔH ≈ 0.

**What it does to the clock's guarantee.**
- **Today:** absolute, 10⁻¹⁰ per step, so a crossing time is within n·10⁻¹⁰/k_v.
- **Proposed:** relative, c per unit of H.
- **A guarantee loosens in the estimate's terms.** For a world with E ≈ 1 and n ≈ 2,000 steps, the
  bound on the crossing time goes from 2 × 10⁻⁷/k_v to about 2 × 10⁻³/k_v. That is why the user may
  need to see it.
- **Where it does not loosen:** in the measured terms, t* moves by at most 1.1 × 10⁻⁸ relative
  between rtol 1e-12 and 1e-13 in D7. The pore/no-pore twin identity is untouched, since H still
  selects no step.
- **The alternative** is an H-aware step limit: H in step selection once the clock is live. It
  keeps the absolute bound but breaks the twin identity of §3.6 from that point. That is a design
  change, not offered here.

### 7.4 D7 under the proposal

- **D7 is registered, and is not run until §7.3 is ruled and landed.** If the lead rules otherwise,
  D7 is amended by a tag before it runs, and D0–D6 are unaffected.
- **Its integrator:** rtol 1e-12 and atol_count 1e-9, as ruled.
- **Its clock convergence (N, (d) alone, by the checker at the tag):** for seeds 1–6 at each rung,
  |t*(1e-12) − t*(1e-13)|/t* must be at most 0.1 × SE_Δ/t*, with SE_Δ = RMS(Δ)/√128 at that rung
  from the exact runs. Otherwise D7 is inconclusive (numerics).
  - The author's measurement of the same quantity, with the bound disabled, is at most
    5.4 × 10⁻¹⁰, 1.8 × 10⁻⁹ and 1.1 × 10⁻⁸ relative at 25, 50 and 100 nm, over seeds 1–6
    (`clock_tstar_convergence.json`).

## 8. The planted failures

Each plant is O(1) and must fail its criterion; a plant not caught makes the protocol fail. Each runs
through a definition edit or a scoped patch of (d)'s path in `validation/` (`plant_definition`,
`plant_scope`, `plant_d7_caught`), never through `src/`, and in a process that runs no exact events.
The effects below were computed in (d) alone before the tag (protocol_d.json, `plant_power_d_alone`).
The budget is B's at the top rung, z*·(1/n_K)^½/√M + b/n_K with n_K = 6,400, which is 3.8 × 10⁻³ of
scale.

| Plant | Mechanism | World | Must fail | Effect in (d) alone, against what it must exceed |
| --- | --- | --- | --- | --- |
| **P-D1**, the envelope disabled | `min_count` 1, so the sparse world is admitted | D0 | B's replica part at the envelope's budget (§6) | Closed form (S): D0's stationary law at T = 12 gives P(n_A ∈ {0, 8}) = 0.065 at any one time. So the 99th percentile of max_t \|Δn_A\|/s_A is at least \|8 − 3.56\|/4 = 1.11, against c_r/√n_min ≤ 5/√97 = 0.51: at least 2.2 times. The mean part, 1.8% against b/n_min ≤ 2.1%, is reported (it fails only for n_min ≥ about 110). With `min_count` 10, D0 is refused at parse |
| **P-D2**, a power off by one | `validation.ol6_plant_power_off_by_one@1`, mass action with each reactant's power + 1 in its limit, in a scoped registry; D1's (d) steps on it | D1 | (i) With the check on: the limit's check. (ii) With the world's own check off: M and B | (i) Refused: "not the products' law". (ii) 0.21 of scale, 54 times the budget |
| **P-D3**, a β entry | D2's largest β entry × 1.5 in (d)'s world only | D2 | M and B | 0.095 of scale, 25 times the budget (the note's rule: at least 10) |
| **P-D4**, the Laplace factor doubled | The tension (d)'s guards read, `lumen.tension`, × 2 | D4 | E's mean (the lysis time) | t*_d moves by −49%, −36% and −25% at the three rungs, against SE(mean T_a) of at most 0.9% of t* even at an SD of 10%: at least 27 SE |
| **P-D5**, a snapped crossing | `_locate` returns its bracket's end, and the re-step's secant is off (`RESTEPS` = 0) | P-D5's world: S3's regression identity, a held vesicle at a fixed area | N: the opening at start + E/k_v within 10(H_ERROR + 1e-9 max(1, E))/k_v | Honest: 1.4e-7 of the tolerance. Planted: the run stalls, with no opening: caught |
| **P-D6**, the heat's sign | The heat row of `Shape.rhs` negated | D1, bottom rung | L (closure) | Refused: "the ledger did not close" |
| **P-D7**, μ° in F_cont only | The ideal term's limit + 0.5 n₀ on the world's own Problem | D1 | The limit's check, item 1 | Refused: "not the products' law" |

Plants of order 1/N vanish in the limit and are not used, as the note says.

## 9. Preconditions (checked at run time, before any criterion)

- **D4 and D7:**
  - no exact replica ends before the last registered time;
  - (d)'s kink and event are not within 1% of a registered time (a crossing at a stop is refused).
- **D6:** at the shear time every exact replica's v = V/V_sph lies at least 5 of its own replicas'
  SD away from 2^(−½) = 0.707.
  - (d) has v = 0.6 there, where the lumen is impermeant and floppy.
  - V is fixed by the lumen's count. Only W fluctuates, at about 10⁻³ in v.
- **Every (d) run** ends as registered: D1–D3, D5 and D6 `complete`, D4 and D7 `lysed`. No run may
  end `stalled`, `step_limit` or `outside_envelope`.

A precondition that fails makes its world inconclusive.

## 10. Verdicts and the retry

- **A world** is:
  - **pass:** every criterion that applies to it passes;
  - **fail:** any criterion fails beyond its band, or a replica is censored;
  - **inconclusive:** a band result, a precondition, or a numerics refusal (the clock bound, or a
    stalled (d) run).
- **A plant** is caught or not caught.
- **The protocol:**
  - **passes** when every world passes (with n_min stated) and every plant is caught;
  - **fails** when any world fails or any plant is not caught;
  - **is inconclusive** otherwise.
- **The retry:** once, for inconclusive worlds only, on seeds 100001 to 100000 + M. Its verdict is
  final, under the same rules, except that the bands then fail.
- **D7 is "not run"** until §7.3 is settled. The protocol's verdict over D0–D6 is reported when they
  are run.

## 11. Who runs it, and its cost

- **Who:** an independent checker assigned by the lead (D304), never a builder of S1–S4 and never
  this protocol's author. It runs detached, with durable logs (AGENTS.md), on the light CPUs.
- **The checker's driver:** it may write its own, using `limit_qualification.py`'s functions as the
  registered arithmetic, as Protocol G does. That is for the lead to confirm.
- **The cost**, from the rates in §2:
  - D1–D3: about 2 events per unit of Ω per replica over rungs summing to 85,000, × 256 × 3, about
    1.3 × 10⁸ events. That is about 45 min at P3's 5 × 10⁴ events/s.
  - D4 and D7: about 10⁵ events per replica at the top rung.
  - D5: about 4 × 10⁵ events per replica at the top rung.
  - D6: about 10⁵ events per replica at the top rung.
  - In all, about 2–3 CPU-hours, within the note's 2.5–4.5.
- **The outputs** go under `/mnt/workspaces/Cells/ol6-protocol-d-<head>/`:
  - definitions;
  - both representations' rows at the registered times, and the event times;
  - the per-criterion tables;
  - each world's smallest passing b and c_r;
  - n_min;
  - the plants' outcomes;
  - verdicts, as JSON.
- **PROGRESS** gets one line, linking to them.

## 12. Not blind (disclosed)

- **The note's probes:**
  - P2b and P2c, arithmetic identities;
  - P4, D0's exact stationary mean against the rate-equation fixed point in closed form: 2.0% at
    T = 12, a constant 0.072 molecule in T. P4 is an exact-against-limit comparison for D0 itself,
    and it designed P-D1. P-D1's spread (§8) is the same closed form, and runs nothing.
- **The parity item of the limit's check** (the builders' tests) compares each law's limit with its
  exact kernel at λ-scaled states.
- **S3's clock-convergence table** (STATE.md).
- **The author's sizing, in cells.rate_equations@1 alone,** at the frozen snapshot of 8df9b012 (S4's
  source). The files are in `/mnt/workspaces/Cells/ol6-20261122/protocol-d/`:
  - **Sizing:** every world at seed 1 on its rungs (`size_*.json`). The worlds were resized once each
    from these runs: D3's U2, D4's solute and osmolarity, D5's tense founder, D6's exchange, and D7's
    line tension and pore rate.
  - **The registered definitions,** run once (`final_d_check.py`).
  - **D7's clock,** over seeds 1–12, with the bound disabled where marked (`clock_*.json`).
  - **The plants' effects** (`plants_all.json`).
- **What the author did not run:** no exact-event run of any registered world. Exact definitions
  were parsed only (`parse_check.py`). Nothing of an exact run's observables was read.
