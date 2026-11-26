# FR-51: the registered protocol `fr51-channel-block-v1` and its pass criteria

This note fixes the pass criteria for FR-51, two voltage-dependent blocking modes on one channel
population. It was written on 23 November 2026, before any code-blind reference exists and before
any engine code. The design is `/mnt/workspaces/Cells/fr49-51-design-20261123/DESIGN.md` §3, as
D327 approved it with the reviewers' details. The lead tags this note and the references' spec
(`references/spec/`) before the engine build (D327).

**The engine.**
- `resolved_pump_tissue@3`'s channel populations: `channel_rates`, its clamped entry point, and the
  per-stage stability rule.
- `resolved_pump_composite@1`, whose clamped entry point calls @3's.
- The host laws `kleak_always_open@1`, `naleak_always_open@1` and `clleak_always_open@1`.
- `membrane_entity_state@1`, for criterion C's units case.

**Bounds fixed before any reference value was seen.** Each bound below was fixed before this writer
saw any value from the registered references. What informed them is listed in §7.

**The inconclusive rule.** A criterion is inconclusive, not a pass, where the reference reports a
cross-check difference above its declared accuracy (`references/spec/README.md`).

## 1. What is declared

### 1.1 The declaration and its units

A channel population may declare an optional `block`:
- `law`: `open_channel_block_weighted_modes@1`;
- `blocker`: `valence` z_B, a nonzero integer; `side`, `outside` or `inside`, giving s = +1 or −1;
  `concentration_mM`, a constant c_B in mM;
- `reference`: `membrane_voltage`, or `{"reversal_of": ion}`, naming one of the population's
  permeant ions;
- `modes`, each with:
  - `weight` w_k, dimensionless;
  - `k0_mM`, K_k(0) in mM;
  - exactly one of `electrical_distance` δ_k (dimensionless) or `effective_valence` z_eff,k
    (dimensionless). This is ruling 7.

**The law** is `references/spec/LAWS.md` §3. Each mode's exponent is
a_k = s sgn(z_B) m_k F/(R T), with m_k = |z_B| δ_k or m_k = z_eff,k.

**Counts and amounts.**
- The population's abundance a is a dimensionless relative abundance, as for every @3 population.
- Under membrane state its count is N = a0 A0 ρ_ref units (molecules), with ρ_ref in units/m².
- The block declares no count. The bound blocker is not taken from any row (trace binding).

### 1.2 The admitted domain (refused at the definition, each with its reason)

| Refused | Why |
| --- | --- |
| A mode declaring both `electrical_distance` and `effective_valence`, or neither | Ruling 7: one steepness per mode |
| δ outside [0, 1] | Woodhull's electrical distance is a fraction of the field |
| `effective_valence` ≤ 0 | The sign comes from s sgn(z_B), never from z_eff |
| A steepness m_k above 8 | The admitted domain's limit (below) |
| z_B = 0 or not an integer | The sign of the charge is kept even in the effective-valence form |
| A weight outside [0, 1], or weights not summing to 1 within 8 ulps | The modes are fractions of one population |
| More than 4 modes | The mode axis is static, and its sum is unrolled |
| K_k(0) outside [1e-15, 1e15] mM | The admitted domain (below) |
| c_B outside [0, 1e3] mM | The admitted domain |
| A reversal reference naming an ion the population does not carry | |
| A blocker ID that names a species row or a permeant ion | Version 1's blocker is a declared constant, not a row |
| An N2 implicit-conductance solver beside a blocked population | A negative slope in the operator could make it indefinite |
| A block on a population of a compartment's bounding patch | Refusal 4 already refuses the population there |

**Why the domain's limits.**
- With |V_ref| ≤ 0.49 V, m_k ≤ 8 and K_k(0) in [1e-15, 1e15] mM, |a_k V_ref| ≤ 147, so every K_k
  lies in [1e-79, 1e79] mM. The bound on V_ref comes from the channel laws' domain, −120 to +60 mV,
  less a reversal potential of at most 0.369 V, for concentrations between 1e-3 and 1e3 mM.
- With c_B ≤ 1e3 mM, every 1 − θ_k is at least 1e-82.
- So every intermediate is a normal binary64 number. That matters because compiled CPU code flushes
  subnormals to zero.
- At run time the block's domain refuses a step where any K_k or c_B + K_k is not finite and normal.

### 1.3 The fraction's form (D327: right at both ends)

    1 − θ_k = K_k / (c_B + K_k)        each formed directly, then multiplied by w_k
    θ_k     = c_B / (c_B + K_k)
    u       = ( Σ_k w_k (1 − θ_k) ) / ( Σ_k w_k )

Both sums are taken left to right in declared mode order, unrolled over the static mode count.

- **At c_B = 0:** K/(0 + K) = 1 exactly. So the numerator is the denominator bit for bit and
  u = 1.0 exactly, whatever the weights. That includes (0.7, 0.2, 0.1), whose float sum is
  0.9999999999999999.
- **At strong block:** u is a sum of small positive terms, so it is relatively accurate. One mode
  with c_B/K = 1e18 gives 1e-18 exactly, where the literal 1 − Σ w θ gives 0. This was measured in
  NumPy and under `jax.jit` (§7).
- The slope term's θ_k (1 − θ_k) is the product of the two directly formed fractions, so it is
  accurate at both ends and exactly 0 at c_B = 0.
- **Unblocked populations in a blocked world, and padding slots,** carry one mode with w = 1,
  K(0) = 1 and c_B = 0, so u = 1.0 exactly.

## 2. How the engine's quantities are read

- **Currents and the fraction at a declared voltage.** They come from @3's clamped entry point, at a
  state whose cell and held bath hold the case's concentrations. The entry point is
  `clamped_channel_flux`, which FR-51 extends with the fraction at the same inputs. It runs on the
  host (NumPy) and compiled (`jax.jit` of the same function).
- **The per-stage terms.** These are the functions the stability rule calls, evaluated at the case's
  state and voltage:
  - the channel term T_V = u G_max + |I_free| (Σ w_k |a_k| θ_k (1 − θ_k))/(Σ w_k), with
    G_max = F² P A r a o v z² max(c_i, c_o)/(R T), today's term;
  - under the reversal reference, the material terms at each end:
    T_c,o = u 1e15 A P r a o v B(x) + |J_free| (Σ w |a| θ (1 − θ)/Σ w) R T/(|z_ion| F c_o), and
    likewise T_c,i with B(−x) and c_i.
- **Voltages** are the reference's decimal strings, read as binary64.

## 3. The criteria

Each criterion must pass on every case it names. Every plant must fail. A plant is the engine with
one planted change, judged by the same criterion against the same reference.

### P. Permeation without the blocker (the request's first item)

- **P0, bitwise.** The block declared at c_B = 0 (Z1's) against no block, in the same state.
  - The clamped flux is bitwise equal at every voltage, on the host and compiled.
  - So is a second, unblocked population's, on the same patch of the blocked world.
- **P1–P4, the closed form.** At every voltage,
  |I_e − I_r| ≤ 1e-12 |I_r| + 1e-15 max_V |I_r|. The second term covers cancellation at reversal.
  - P1 (equal concentrations) is linear in V through 0.
  - P2 to P4 reverse at E_ion.
- **Plant:** c_i and c_o exchanged in the flux. It must fail P2 at one voltage or more.

### Z. The zero blocker: the fraction's first end (compiled)

- On the compiled clamped program and on one compiled checked step of Z1's world:
  - u == 1.0 at every voltage;
  - the blocked population's flux is bitwise the block-free population's.
- **Plant:** u = Σ_k w_k/(1 + c_B/K_k). It gives 0.9999999999999999 for (0.7, 0.2, 0.1) and must
  fail.

### B. The blocked-to-free ratio against voltage (the request's second item)

- **B-u.** |u_e − u_r| ≤ 1e-12 u_r at every voltage, the extra points included. The cases are B1–B5,
  G1–G5, S1, S2, Z1, C1 and C2.
- **B-ratio, away from reversal only.** Where |V − E_ion| ≥ 1 mV,
  |I_blocked,e/I_free,e − u_r| ≤ 1e-12 u_r. At reversal the ratio is not formed (criterion R).
- **B-superposition.**
  - Under the reversal reference (B1 at E1 and E2), the engine's u at equal V_ref agrees within
    1e-12 max u.
  - Under the membrane voltage (B3 at E1 and E2), it agrees at equal V.
- **Woodhull and the weighted sum.** One mode (B2, B3) is the single-site law. Two modes with
  different δ (B1) are the weighted sum. Both are in B-u.
- **Plants.** Each must fail at one voltage or more:
  - (i) the side's sign flipped (s → −s): B1, by more than 1e-2 relative;
  - (ii) E with the wrong sign of its valence: B1 and B-superposition;
  - (iii) the two modes' weights swapped: B1;
  - (iv) the effective-valence exponent without sgn(z_B): B4, where u is 0.989 against the plant's
    0.011 at −80 mV (§7).

### R. The fraction at reversal, read directly

- At V = E_ion, |u_e − u_r| ≤ 1e-12 u_r for every case with a block.
- Under the reversal reference this is u at V_ref = 0, which is (Σ w_k K_k(0)/(c_B + K_k(0)))/Σ w_k.
- **Plant:** a reversal reference read as the membrane voltage. It must fail R for B1.

### S. Strong block: the fraction's second end (compiled)

- On the compiled clamped program and on one compiled checked step of S1's world, at every voltage:
  - |u_e − u_r| ≤ 1e-12 u_r for S1 (u_r about 1e-18) and S2;
  - the same for the slope part θ (1 − θ).
- **Plant:** the literal u = 1 − Σ_k w_k θ_k. It gives 0 for S1 (relative error 1) and is about
  3e-5 relative off for S2 (§7). It must fail.

### C. One count (the request's third item)

- **C1, abundance.** The flux at abundance 2 is bitwise twice the flux at abundance 1, at every
  voltage. u is bitwise unchanged.
- **C2, units, under membrane state.**
  - The 2000-unit flux is within 4 ulps of twice the 1000-unit flux, and u is bitwise unchanged.
  - The 1000-unit case is within 4 ulps of B1 at E1, whose abundance is 1 = N/(A ρ_ref).
- **Plant:** the blocker concentration scaled by the count. It must fail C1.

### G. The per-stage voltage slope bound

- **The bound.** For every case with a block, at every voltage, T_V,e ≥ |dI_blocked/dV|_r (1 − 1e-12).
- **Plants.** Each must fail at one point or more:
  - (i) the block's term dropped, leaving u G_max. Expected on B1 by up to 2.1 times;
  - (ii) today's unblocked G_max alone. Expected on G3 by up to 7.9 times (§7).
- **Reported:** max over V of |dI_blocked/dV|_r/T_V,e per case, which is at most 1.

### E. The per-stage concentration slope through E (D327: the step bound sees u's dependence on E)

- **The bound.** For every case under the reversal reference (B1, B5, G1, G4, Z1, C1, C2), at every
  voltage:
  - T_c,o,e ≥ |∂J_blocked/∂c_o|_r (1 − 1e-12);
  - T_c,i,e ≥ |∂J_blocked/∂c_i|_r (1 − 1e-12).
- **Plants.** Each must fail at one point or more:
  - (i) the term without its part through E. Expected on B1 at E1 by up to about 190 times at
    +50 mV (§7);
  - (ii) the term evaluated with E1's reversal potential at E2's state.
- **Where it enters the step.** The term joins the per-stage material rule, which holds
  dt × rate ≤ 1 at every explicit stage, at each end node: the cell, and an outside node that is
  not a held bath. It is divided by that node's volume. A world without a blocked population keeps
  today's rule.

### V7. Ruling 7 and the declaration

- Each refusal of §1.2 fires with its reason: one parametrized row each.
- **The plant row:** an effective-valence mode whose exponent drops sgn(z_B). It must fail B4,
  which is plant (iv).

### RUN. A run (the request's fourth item)

One compiled world:
- one cell on a held bath;
- a blocked K leak, B1's block on a gate-free K population;
- an unblocked Na leak on the same patch;
- the cell started inside the K population's negative-slope region.

The builder fixes the world's values and its step at build time, without changing these
criteria. On every observed row:
1. every host check passes, the ledgers included;
2. each population's cumulative heat is non-decreasing;
3. the readout `channel_unblocked_fraction` equals the law at the row's V and E within 1e-12
   relative;
4. the per-stage rate, read from the engine's own rate function at the row's state, is at least
   |dI_blocked/dV|/C of that row. The slope is a central difference of the clamped current
   (h = 1e-7 V), and C is the cell's capacitance.

Across the run:
- at least 10 observed rows lie in the negative-slope region, where the central difference is below
  0;
- a restart from a checkpoint at mid-run is bitwise;
- the composite's clamped entry point equals @3's bit for bit at one row.

**Plant:** the block's term dropped (u G_max). It must fail item 4 at one row or more of the
negative-slope region.

## 4. What is reported and not judged

- Each case's max of |dI/dV|_r over today's G_max: the factor by which today's term would miss.
- The run's resting potential, and which of the I–V curve's zeros it reached.

## 5. The tests (D224)

- **Host, no compile:** P, B, R, C, G, E and V7 are rows in
  `tests/unit/test_surface_pump_v3_populations.py` (tier 2). Their plants are rows beside them.
  About 5 s in all.
- **Compiled:**
  - Z and S on the compiled clamped program and one compiled checked step each: about 20–30 s;
  - RUN, with its restart: about 70–100 s.
- Each states its seconds and reason at landing.

## 6. Indications, not judged

Each of the following rests on one study, so it is an indication, not a claim. None enters a
criterion:
- the proportional shift of polyamine-induced rectification with E_K (Lopatin and Nichols 1996, J.
  Gen. Physiol. 108:105–113, PMID 8854340, DOI 10.1085/jgp.108.2.105). It motivates the reversal
  reference;
- an apparent valence of spermine block near 5, above spermine's charge of 4, arising mainly from
  K⁺ ions (Shin and Lu 2005, J. Gen. Physiol. 125:413–426, PMID 15795311, DOI
  10.1085/jgp.200409242). It motivates the effective-valence form;
- two Kir2.1 populations with different block sensitivities (Yan and Ishihara 2005, J. Physiol.
  563:725–744, PMID 15618275, DOI 10.1113/jphysiol.2004.079186). It motivates the weighted modes.

Woodhull's model is the law's form (Woodhull 1973, J. Gen. Physiol. 61:687–708, PMID 4541078, DOI
10.1085/jgp.61.6.687).

These records were checked against Europe PMC on 23 November 2026: titles, journals, pages,
identifiers, and the quoted abstract statements. The full texts were not read.

## 7. Evidence that informed the bands

The evidence is in `/mnt/workspaces/Cells/fr51-registration-20261123/probe/`
(`fraction_and_bounds.py`, with its log and JSON). It is NumPy and `jax.jit` on made-up values, with
no world and no engine call:
- **A, the fraction at both ends:**
  - the normalized form gives exactly 1.0 at c_B = 0, and exactly 1e-18 and 1e-30 at c/K = 1e18 and
    1e30;
  - the literal form gives 0 there, and is 3.2e-5 relative off for S2's two modes;
  - numerator and denominator in one order give 1.0 for (0.7, 0.2, 0.1) and for (0.3, 0.7).
- **B, steepness 8:**
  - today's G_max is exceeded up to 7.9 times (Na, blocker from the outside, half-block at −110 mV);
  - the full term T_V bounds |dI/dV| in every case, at ratios of 0.913 to 0.993;
  - the exact form u |I′| + |I| Σ w |a| θ (1 − θ) is tight, at a ratio of 1.000000.
- **C, the concentration slope under V − E:** without its part through E the term misses by up to
  192 times at +50 mV; the full term bounds it, tight at −100 mV.
- **D, the effective-valence sign** for an anion blocker: u is 0.989 at −80 mV, against 0.011
  without sgn(z_B).

The design note's probes are also relevant (`/mnt/workspaces/Cells/fr49-51-design-20261123/probe/`,
D and E). They found today's term exceeded 1.6 to 3.4 times at steepness 2 to 4.

Binary64 alone is about 1e-15 relative for u and I; the bands of 1e-12 allow about 1,000 times
that. The steepest case's exponent carries about |a V_ref| ε ≈ 3e-14 of rounding. Every plant
misses by at least 1e-2 relative, or fails a bitwise criterion.
