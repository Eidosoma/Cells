# The laws: closed forms, units and the declared split

Every input is in `inputs.json`; a number quoted here is a constant, a unit, an exponent or an operation count,
never a result. Nothing here is engine code. Read each declared real as the exact value of its nearest double.

## 0. Conventions and constants

- **Amounts** n in fmol, **volumes** V in pL, **concentrations** c = n/V in mM (1 fmol/pL = 1 mM), **times** in s.
- **N_A** = 6.02214076 × 10²³ per mol, exactly. One molecule is COPY = 10¹⁵/N_A fmol (the decimal quotient, read as
  its nearest double). It enters W6 only.
- **Copies.** A world is one cell (volume V_c), one finite outside node (volume V_o), and one patch between them
  that holds one site. The worlds' `copies` are independent: a run of copy c is its own world, with its own seed,
  and nothing couples two copies.
- **A read.** A channel that reads a row multiplies its rate by φ = c/(1 mM), c the read row's concentration at the
  current state. A channel that reads nothing has φ = 1.
- **The state of the population** is (f, a): f free units and a active ones. c, V, and the letters below are per
  copy.
- **u** = 2⁻⁵³, the unit roundoff of binary64.

## 1. The population of one site

**State.** (f, a): `free` units (1 subunit each) and `active` units (2 subunits each), starting at the world's
`initial_counts` (2 free, 0 active). The site's subunits f + 2a are constant.

**Channels, in declared order:** `assemble` (2 free → 1 active), then `dissolve` (1 active → 2 free). Channel j has
the propensity (1/s)

    a_j = k_j Π_k ff(n_k, r_jk) φ_j,     ff(n, r) = n!/(n − r)!,  ff(n, 0) = 1, ff(n, r) = 0 for r > n

- r_jk is channel j's reactant order in state k and n_k the count of state k (f or a). ff counts ordered tuples: at
  f = 2, `assemble` has ff(2, 2) = 2; at a = 1, `dissolve` has ff(1, 1) = 1.
- φ_j is the read of §0: in W5 and W6 `assemble` reads the shared row in the **cell**; in W5-exact nothing reads.
- a_0 = Σ_j a_j, summed left to right in declared order.

**The transfer.** The active units conduct one species x between the cell and the node, linearly and passively, with
g the conductance of one active unit (pL/s):

    J = G (n_x,c/V_c − n_x,o/V_o)   (fmol/s, cell to node),   G = g a
    dn_x,c/dt = −J + (the co-writer's terms),    dn_x,o/dt = +J

The units carry no free energy and no amount of x. Volumes are constant. The transfer moves x between the two pools,
and the co-writer's terms (§2, §3) are the only other change of n_x,c. At the node only the transfer moves x.

**The event rule (the hybrid next-reaction rule).**
1. **The hazard.** H(t) is the integral of a_0 along the solution since the last event (or since t = 0), and H = 0
   right after every event.
2. **Event k** (k = 0, 1, …, in order) fires at the first t with H(t) = E_k = −ln u1_k.
3. **Its channel** is the first j with c_j > min(u2_k a_0, nextafter(a_0, 0)), where c_j = a_1 + … + a_j are the
   partial sums at the crossing state in declared order, and nextafter is binary64's.
4. **The jump.** The counts change by −r_j + p_j, p_j the products. The rows are continuous across it: an event
   moves no material.
5. (u1_k, u2_k) is draw k of the site's own stream (§6).

In these worlds one channel has a non-zero propensity at every state, `assemble` while f = 2 and `dissolve` while a
= 1. So the channel never depends on u2 in W5, W5-exact or W6, and u2 takes no part in the result.

## 2. W5's reactions

Driven mass action in the cell, with V = V_c and c = n/V_c:

    make:   X → S       J_1 = k_1 n_X                               (fmol/s; k_1 in 1/s)
    spend:  S + Y → W   J_2 = k_2 V c_S c_Y = k_2 n_S n_Y / V        (k_2 in 1/(mM s))
    dn_X/dt = −J_1,   dn_S/dt = J_1 − J_2 − J,   dn_Y/dt = −J_2,   dn_W/dt = +J_2

S has no other route in the cell. At the node only the transfer moves S.

**The books of the co-writers.** ξ_1(t) = ∫₀ᵗ J_1, ξ_2(t) = ∫₀ᵗ J_2, and the transfer's moved(t) = ∫₀ᵗ J (positive
from cell to node). **Two conserved sums,** exactly: n_X + n_S,c + n_S,o + n_W, and n_Y + n_W (every holder of each
is named).

## 3. W6's gene unit

The gene unit transcribes one gene into an mRNA R in the cell. Its own laws, from the sheet
`docs/TEMPLATED_POLYMERISATION_LAWS.md` (§4.1 to §4.4, §3.4), as used here. Read the sheet's §§0, 1.1, 1.2, 2, 3.1,
3.4 (its two lines on `tx` and `deg_R`), 4.1, 4.2, 4.3, 4.4, 4.7 and 4.8, and nothing else in it. **In W6 there is
no translation, recharging, regulator, hold or release step: a finished chain is R.**

- **Rows** in the cell: N (the monomer drawn), M (the monomer made), Pi (the product released with each residue), R.
  The node holds R only.
- **Machines.** F (free) and the stage complexes C_1 … C_m, in fmol. m = `stages`, r = `residues`/m, κ =
  `speed_per_s`/r, L = `residues`. **The start state:** every machine is free, F(0) = `machines_copies` · COPY
  (fmol), and every complex is exactly zero, C_1(0) = … = C_m(0) = 0, as the engine starts them (`inputs.json`'s
  `start` and `machines_start`).
- **Copies to amounts.** The template has `template_copies` copies, c_T = `template_copies` · COPY/V (mM).
- **Potentials.** In RT units, at c° = `c0_mM`. Each row's is `mu_RT` (N, M, Pi, R), and the residue's is μ°_res =
  `mu_RT.R`/L, formed in doubles. With a_s = c_s/`c0_mM`, c_s the current concentration:

      x = μ°_res + 2 (μ°_Pi + ln a_Pi) − (μ°_N + ln a_N)                  (the per-residue affinity of transcription)
      y = (μ°_M + ln a_M) − μ°_res − (ln a_R)/L                            (the per-residue affinity of the degradation)

- **Rates** (fmol/s):

      J_I = k_I c_T F
      J_j = κ φ C_j,   φ = c_N/(K_N + c_N) · (1 − e^x),   j = 1 … m
      D   = k_R n_R,c (1 − e^y)

- **Equations.**

      dF/dt = −J_I + J_m,   dC_1/dt = J_I − J_1,   dC_j/dt = J_{j−1} − J_j  (j = 2 … m)
      dn_R,c/dt = J_m − D − J,   dn_R,o/dt = +J                            (J of §1)
      dn_N/dt = −r Σ_j J_j,   dn_Pi/dt = +2r Σ_j J_j,   dn_M/dt = +L D

- **The books.** inits = ∫ J_I, exits = ∫ Σ_j J_j, made = ∫ J_m (finished chains, in molecules of R as fmol), lost =
  ∫ D, moved = ∫ J. **free** is F; **engaged** is Σ_j C_j; **transit** (fmol of residues) is r Σ_j (j − 1) C_j.
- **The identities** F + Σ_j C_j constant, engaged = inits − made, transit = r exits − L made, and the rows'
  (READOUTS.md §4), hold exactly at every time.

## 4. The coupled process

Between events the counts are constant and the rows (and H) obey the ODEs of §2 (W5, W5-exact) or §3 (W6) with the
transfer and dH/dt = a_0. At an event the counts jump and the rows do not. The reference is this process, solved
exactly: it has no step and no splitting.

- **W5-exact:** no channel reads a row. So a_0 depends on the counts alone, the events' times are t_k = Σ_{i ≤ k}
  E_i/a_0,i (E_i the hazard thresholds, a_0,i the propensity total in the state between events i − 1 and i), and the
  reactions and the transfer run but no rate of the site depends on them.

## 5. What each writer does, and the declared split (sizing only)

The engine's step of length h is symmetric (Strang): the co-writer's half-steps and the population's half-steps in
declared order, then the same parts in reverse. A run declares which of the two comes first.

**The sizing model.** Where the references size a plant or a statistic, they compute the split scheme's own result
at step h, with each sub-flow solved accurately (any method, error below 10⁻³ of the split's own error):

- **B(τ), the co-writer's flow** over τ: the equations of §2 or §3 with the transfer off (J = 0), the counts and the
  node's row fixed, no hazard accruing. W5's reactions: an accurate solution. **W6's gene unit: the third-order
  SSPRK(3,3) of Shu and Osher (the co-writer's declared method), one step of τ** (here τ = h/2), so that its own
  third-order error is present; `made` and `exits` depend on nothing else.
- **A(τ), the population's flow** over τ: the two pools of the shared row relax through the transfer at the current
  counts, H accrues at the current propensities (which read the cell's row as it relaxes), events fire inside τ as
  §1 says, and every other row is fixed.
- **One step of `cowriter-first`** (`reactions-first`, `gene-first`): B(h/2) A(h/2) A(h/2) B(h/2). **One step of
  `population-first`:** A(h/2) B(h/2) B(h/2) A(h/2).

**This model is never used to judge a run, and no honest tolerance reads it.** It is how a plant's size, and a
pooled statistic's expected value and order, are estimated before any run. Nothing of it enters a verdict except
through C0 (CRITERIA.md §4.2).

**The phase of an event.** An event at phase φ of its step (0 at the start, 1 at the end) is off by a term of order
h² that depends on φ, so the errors of neighbouring steps scatter, and only an average over many events is smooth.
That is why CRITERIA.md's order is one fit over the family's rungs on a pooled statistic, and why no judgement rests
on one ratio.

## 6. The draws

Every draw is counter-based and depends only on (seed, site, domain, counter). The derivation is Threefry-2x32 in
JAX's partitionable layout (`jax_threefry_partitionable`, its default since JAX 0.5):

    base    = jax.random.key(seed, impl="threefry2x32")            seed in [0, 2**32)
    site    = fold_in(fold_in(base, low32(s)), high32(s))           s: the site's declared index (0 here)
    stream  = fold_in(site, domain)                                 domain: events 1
    draw k  = fold_in(fold_in(stream, low32(k)), high32(k))         k: the event's counter, 0, 1, ...
    words   = jax.random.bits(draw k, shape=(2,), dtype=uint64)
    u       = ((words & (2**52 − 1)) + 0.5) * 2**-52                (u1_k, u2_k) = (u[0], u[1])

- Each `fold_in` takes one unsigned 32-bit word. `draws.json` holds the first `pairs_per_copy` (160) pairs of every
  copy's stream, as `float.hex` strings. A run of copy c uses its world's seed `seeds[c]` and site index 0, and an
  event takes draw k whenever it fires.
- **The premise check.** Regenerate the table from this rule with your own code, and compare it bit for bit.
  `make_draws.py` is the generator of record: the lead and the checker run it, and you neither read nor run it.

## 7. Rounding counts

**The model of arithmetic.** Each rounded operation on a term of size at most s errs by at most u·s. A quantity
formed from at most m rounded operations a step, over S = t/h steps, from a declared start, is off by at most

    e_round = m (S + 1) u s                                          (m, s by quantity below)

| Quantity | m | s |
| --- | --- | --- |
| An event's time (the clock, and W5-exact's bound) | 4 | T, the world's end time |
| A row, or a book, at a sample | 16 | the scale of READOUTS.md §2 |

**Where these come from.** The author wrote them with the engine's own arithmetic in view (the protocol's §10 says
what was read). The event-time count rests on that arithmetic; the row count on the operators' declared increments.
Both are bounds, not observed errors. **The rehearsal exercises each** (CRITERIA.md §10), and a bound an honest run
misses is re-derived or it is a defect.

- **Why 4, for a time.** An event's time is the half-step clock's compensated sum (2 roundings of the total, each at
  most u·T), plus the hazard's own arithmetic: the uncompensated sum over the half-steps since the last event (at
  most 2S additions, each rounded once), a bounded number of operations in a half-step (fewer than 20) and the final
  division. Between two events the relative error is at most (n + 20) u, n the half-steps it spans, and H = a_0 w
  with w the waiting time, so the time moves by at most (n + 20) u w. Summed over the events to T, with n ≤ 2S and Σ
  w ≤ T, it is at most (2S + 20) u T, and with the clock's 2 u T at most (2S + 22) u T. 4 (S + 1) ≥ 2S + 22 for
  every S ≥ 9, and every registered S is at least 1,000. (A reference carries the same sum exactly: it adds its own
  accuracy.)
- **Why 16, for a row or book.** Each half-step adds at most 4 rounded increments to a stored amount, 8 a step, each
  at most u times the absolute terms of §2 and §3 (a row is a declared amount plus an increment). 16 doubles it for
  the books that are read back and the reading.

## 8. What the exactness of W5-exact means

With no read, the events' times are a function of the draws alone, so the engine's equal the decimal sums of §4 to
e_round at every step and in either declared order, whatever the co-writer and the transfer do. That is the claim of
exactness. The co-writer and the transfer must run in that world for the claim to mean anything: CRITERIA.md §3.2's
running check (E1) says when.

## 9. The planted changes

Each reference plant is computed from the same laws with one change (`inputs.json`'s `plants`):

| Plant | Change |
| --- | --- |
| P1 | W5's k_1 multiplied by 1.01 |
| P2 | W6's initiation k_I multiplied by 1.01 |
| P5 | W5-exact's `assemble` rate multiplied by 1.01 |
| P9 | W5's `assemble` reads S at the node, not the cell |
| P10 | W5: k_1 = k_2 = 0, the transfer and the population unchanged. W6: k_I = 0 |
| P11 | W6: the factor (1 − e^x) replaced by 1 in J_j |
| P12 | W6: the factor (1 − e^y) replaced by 1 in D |

P4's shift is 10 times the family's expected τ of `t_events`, formed by the references, by family. The other plants
are records or engine runs (CRITERIA.md §6) and need no series.
