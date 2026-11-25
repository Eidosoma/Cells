# The laws: closed forms, units and the declared split

Every input is in `inputs.json`; a number quoted here is a constant, a unit or an exponent, never a result. Nothing
here is engine code. Read each declared real as the exact value of its nearest double.

## 0. Conventions and constants

- **Amounts** n in fmol, **volumes** V in pL, **concentrations** c = n/V in mM (1 fmol/pL = 1 mM), **times** in s.
- **N_A** = 6.02214076 × 10²³ per mol, exactly. One molecule is COPY = 10¹⁵/N_A fmol (the decimal quotient, read as
  its nearest double). It enters W6 only.
- **Copies.** A world is one cell (volume V_c), one finite outside node (volume V_o), and one patch between them
  that holds one site. The worlds' `copies` are independent: a run of copy c is its own world, with its own seed,
  and nothing couples two copies.
- **φ_read.** A channel that reads a row multiplies its rate by φ = c/(1 mM), c the read row's concentration at the
  current state. A channel that reads nothing has φ = 1.
- **u** = 2⁻⁵³, the unit roundoff of binary64. ε = 2u.

## 1. The population of one site

**State.** The counts N = (n_free, n_active) of two unit states, `free` (1 subunit) and `active` (2 subunits),
starting at the world's `initial_counts` (2 free, 0 active). The site's subunits Σ_k w_k n_k = n_free + 2 n_active
are constant.

**Channels, in declared order:** `assemble` (2 free → 1 active), then `dissolve` (1 active → 2 free). Channel j has
the propensity (1/s)

    a_j = k_j Π_k ff(n_k, r_jk) φ_j,     ff(n, r) = n!/(n − r)!,  ff(n, 0) = 1, ff(n, r) = 0 for r > n

- r_jk is channel j's reactant order in state k. ff counts ordered tuples: at n_free = 2, `assemble` has ff(2, 2) =
  2, and `dissolve` has ff(1, 1) = 1 at one active unit.
- φ_j is the read of §0. In W5 and W6 `assemble` reads the moved row in the **cell**. In W5-exact no channel reads.
- a₀ = Σ_j a_j, summed left to right in declared order.

**The transfer.** The active units conduct one species x between the cell and the node, linearly and passively, with
g the conductance of one active unit (pL/s):

    J = G (n_x,c/V_c − n_x,o/V_o)   (fmol/s, cell to node),   G = g n_active
    dn_x,c/dt = −J + (the co-writer's terms),    dn_x,o/dt = +J

The units carry no free energy and no amount of x. Volumes are constant. The transfer moves x between the two pools
and the co-writer's terms (§2, §3) are the only other change of n_x,c. At the node only the transfer moves x.

**The event rule (the hybrid next-reaction rule).**
1. **The hazard.** H(t) is the integral of a₀ along the solution since the last event (or since t = 0), and H = 0
   right after every event.
2. **Event k** (k = 0, 1, …, in order) fires at the first t with H(t) = E_k = −ln u1_k.
3. **Its channel** is the first j with c_j > min(u2_k a₀, nextafter(a₀, 0)), where c_j = a_1 + … + a_j are the
   partial sums at the crossing state in declared order, and nextafter is binary64's.
4. **The jump.** N ← N − r_j + p_j, p_j the products. The rows are continuous across it: an event moves no material.
5. (u1_k, u2_k) is draw k of the site's own stream (§6).

In these worlds one channel has a non-zero propensity at every state: `assemble` while 2 are free, `dissolve` while
1 is active. So the channel never depends on u2 at a W5, W5-exact or W6 event, and u2 takes no part in the result.

## 2. W5's reactions

Driven mass action in the cell, with V = V_c and c = n/V_c:

    make:   X → S       J_1 = k_1 n_X                      (fmol/s; k_1 in 1/s)
    spend:  S + Y → W   J_2 = k_2 V c_S c_Y = k_2 n_S n_Y / V   (k_2 in 1/(mM s))
    dn_X/dt = −J_1,   dn_S/dt = J_1 − J_2 − J,   dn_Y/dt = −J_2,   dn_W/dt = +J_2

S has no other route in the cell. At the node only the transfer moves S.

**The books of the co-writers.** ξ_1(t) = ∫₀ᵗ J_1, ξ_2(t) = ∫₀ᵗ J_2, and the transfer's book moved(t) = ∫₀ᵗ J
(positive from cell to node).

**Two conserved sums,** exactly: n_X + n_S,c + n_S,o + n_W (the S moiety) and n_Y + n_W.

## 3. W6's gene unit

The gene unit transcribes one gene into an mRNA R in the cell. Its own laws, from the sheet
`docs/TEMPLATED_POLYMERISATION_LAWS.md` (§4.1 to §4.4, §3.4), as used here. Read the sheet's §§0, 1.1, 1.2, 2, 3.1,
3.4 (its two lines on `tx` and `deg_R`), 4.1, 4.2, 4.3, 4.4, 4.7 and 4.8, and nothing else in it. **In W6 there is
no translation, recharging, regulator, hold or release step: a finished chain is R.**

- **Rows** in the cell: N (the NTP lump), M (the NMP lump), Pi, R. The node holds R only, beside the trace rows of
  the engine, which nothing here moves.
- **Machines.** F (free) and the stage complexes C_1 … C_m, in fmol. m = `stages`, r = `residues`/m, κ =
  `speed_per_s`/r.
- **Copies to amounts.** The template has T = `template_copies` copies, c_T = T · COPY/V (mM). The machines' total
  is `machines_copies` · COPY fmol. R, machines and complexes are in fmol.
- **Reduced affinities.** With a_s = c_s/`c0_mM` and μ_s = μ°_s + ln a_s in RT units (`mu_RT`, R's residue potential
  `mu_RT.residue` = μ°_res), the per-residue affinity of transcription and of the degradation are

      x = μ°_res + 2 (μ°_Pi + ln a_Pi) − (μ°_N + ln a_N)
      y = (μ°_M + ln a_M) − μ°_res − (ln a_R)/L,       L = residues

  (the sheet's ΔG_tx/RT per residue, and ΔG_deg,R/(L RT) with μ°_R = L μ°_res).
- **Rates** (fmol/s):

      J_I = k_I c_T F                                                   (initiation; k_I in 1/(mM s))
      J_j = κ φ C_j,   φ = c_N/(K_N + c_N) · (1 − e^x),   j = 1 … m
      D   = k_R n_R,c (1 − e^y)

- **Equations.**

      dF/dt = −J_I + J_m,   dC_1/dt = J_I − J_1,   dC_j/dt = J_{j−1} − J_j
      dn_R,c/dt = J_m − D − J,   dn_R,o/dt = +J                     (J of §1)
      dn_N/dt = −r Σ_j J_j,   dn_Pi/dt = +2 r Σ_j J_j,   dn_M/dt = +L D

- **The books.** made(t) = ∫ J_m (finished chains, in molecules of R as fmol), lost(t) = ∫ D, moved(t) = ∫ J. The
  machines' identity F + Σ_j C_j is constant.

## 4. The coupled process

Between events N is constant, and the rows (and H) obey the ODEs of §2 (W5, W5-exact) or §3 (W6) together with the
transfer and dH/dt = a₀. At an event N jumps and the rows do not. The reference is this process, solved exactly: it
has no step and no splitting.

- **W5-exact:** no channel reads a row. So a₀ depends on N alone, the events' times are t_k = Σ_{i ≤ k} E_i/a₀(N_i)
  (E_i the hazard thresholds, a₀ the propensity total in the state between events i − 1 and i), and the reactions
  and the transfer run but no rate of the site depends on them.

## 5. What each writer does, and the declared split (sizing only)

The engine's step of length h is symmetric (Strang): the co-writer's half-steps and the population's half-steps in
declared order, then the same parts in reverse. A run declares which of the two comes first.

**The sizing model.** Where a reference agent sizes a plant or a statistic, it may compute the split scheme's own
result at step h, with each sub-flow solved accurately (any method, error below 10⁻³ of the split's own error):

- **B(τ), the co-writer's flow** over τ: the equations of §2 or §3 with the transfer off (J = 0), N and the node's
  row fixed, and no hazard accruing. (The engine's own half-step of these is third order: the model's flow is exact,
  so the two differ by O(h³), far below the split's own error.)
- **A(τ), the population's flow** over τ: the two pools of the shared row relax through the transfer at the current
  counts, H accrues at the current propensities (which read the cell's row as it relaxes), events fire inside τ as
  §1 says, and every other row is fixed.
- **One step of `cowriter-first`** (`reactions-first`, `gene-first`): B(h/2) A(h/2) A(h/2) B(h/2). **One step of
  `population-first`:** A(h/2) B(h/2) B(h/2) A(h/2).

**This model is never used to judge a run, and no honest tolerance reads it.** It is how a plant's size, and a
pooled statistic's expected value and order, are estimated before any run.

**The phase of an event.** In a step of the split scheme an event at phase φ of its step (0 at the start, 1 at the
end) is off by a term of order h² that depends on φ, so the errors of neighbouring steps scatter, and only an
average over many events is smooth. That is why CRITERIA.md's order is one fit over five steps on a pooled
statistic, and why no judgement rests on one ratio of neighbouring steps.

## 6. The draws

Every draw is counter-based and depends only on (seed, site, domain, counter). The derivation is Threefry-2x32 in
JAX's partitionable layout (`jax_threefry_partitionable`, its default since JAX 0.5):

    base    = jax.random.key(seed, impl="threefry2x32")            seed in [0, 2**32)
    site    = fold_in(fold_in(base, low32(s)), high32(s))           s: the site's declared index (0 here)
    stream  = fold_in(site, domain)                                 domain: events 1
    draw k  = fold_in(fold_in(stream, low32(k)), high32(k))         k: the event's counter, 0, 1, ...
    words   = jax.random.bits(draw k, shape=(2,), dtype=uint64)
    u       = ((words & (2**52 − 1)) + 0.5) * 2**-52                (u1_k, u2_k) = (u[0], u[1])

- Each `fold_in` takes one unsigned 32-bit word. `draws.json` holds the first 160 pairs of every copy's stream, as
  `float.hex` strings.
- **The premise check.** Regenerate the table from this rule with your own code, not from `make_draws.py`, and
  compare it bit for bit.
- A run of copy c uses its world's seed `seeds[c]` and site index 0. A site's event k takes draw k whenever it
  fires.

## 7. Rounding counts

**The model of arithmetic.** Each rounded operation on a term of size at most s errs by at most u·s. A quantity
formed from at most m rounded operations a step, over S = t/h steps, from a declared start, is off by at most

    e_round = m (S + 1) u s                                          (m, s by quantity below)

| Quantity | m | s |
| --- | --- | --- |
| An event's time (the clock, and W5-exact's bound) | 4 | T, the world's end time |
| A row, or a book, at a sample | 16 | s_y: the sum of the absolute terms the quantity is formed from (READOUTS.md §2) |

**Why 4, for a time.** An event's time is the half-step clock's compensated sum (2 roundings of the total, each at
most u·T, whatever the number of half-steps), plus the hazard's own arithmetic: the uncompensated sum over the
half-steps since the last event (at most 2S additions over the whole run, each rounded once), a bounded number of
operations in a half-step (fewer than 20) and the final division. Between two events the hazard's relative error is
at most (n + 20) u, with n the half-steps the interval spans, and H = a₀ w with w the waiting time, so the time
moves by at most (n + 20) u w. Summed over the events to T, with n ≤ 2S and Σ w ≤ T, this is at most (2S + 20) u T.
With 2 u T for the clock it is at most (2S + 22) u T, and 4 (S + 1) ≥ 2S + 22 for every S ≥ 9. Every registered S is
at least 1,000. (A reference carries the same sum exactly: it adds its own accuracy instead.)

**Why 16, for a row or book.** Each half-step adds at most 4 rounded increments to a stored amount, 8 a step (16
includes 4 for the books that are read back and 4 for the reading), each at most u times the absolute terms.

A rounding bound here is a bound, not an observed error. The rehearsal exercises each (CRITERIA.md §10), and a bound
an honest run misses is corrected by re-derivation only, by a dated change before the registration tag.

## 8. What the exactness of W5-exact means

With no read, the events' times are a function of the draws alone. The engine's times must therefore equal the
decimal sums to e_round at every step and every declared order, whatever the co-writer and the transfer do. That is
the claim of exactness tested here.

## 9. The planted series, in words

Each is computed from the same laws with one change.

| Plant | Change |
| --- | --- |
| P1 | W5's k_1 multiplied by 1.01 |
| P2 | W6's initiation k_I multiplied by 1.01 |
| P5 | W5-exact's `assemble` rate multiplied by 1.01 |
| P9 | W5's `assemble` reads S at the node, not the cell |
| P10 | W5 without the two reactions (k_1 = k_2 = 0), the transfer and the population unchanged; W6 with the initiation off (k_I = 0) |

The other plants are records or engine runs (CRITERIA.md §6): they need no series of the references.
