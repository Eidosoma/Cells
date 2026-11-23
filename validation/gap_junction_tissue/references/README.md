# Gap-junction tissue: code-blind references

Exact reference values for the registered comparisons of the gap-junction cancer
replication. They were written without seeing the engine's code, runs or results.

## GJ-L1, the linear model (task A)

The specification is `spec/linear.json` at the tag `gj-linear-registered-2026-11-23`.
The references read only two inputs:

- **The preprint:** J. Grodstein, J. Mathews and M. Levin, "Membrane voltage and connexin
  expression work together to enhance tumor growth and metastasis in cancer", bioRxiv
  10.64898/2026.09.02.748840 v1 (CC-BY 4.0). The parts used are eqs. 1–2, the appendix
  "syncytium calculations", Figures 3, 5, 7 and 8, and the Methods on junctions.
- **The specification at that tag,** read with `git show`.

### Files

| File | What it is |
|---|---|
| `linear_reference.py` | The generator. It uses the standard library only and imports nothing from the engine or from this package. It reads the spec with `git show <tag>:validation/gap_junction_tissue/references/spec/linear.json`, solves every requested quantity exactly in `fractions.Fraction`, checks each one exactly (see Derivations), rounds once to binary64, and writes the interface. |
| `interface/linear.json` | The references, format `gap_junction_tissue.linear_references@1`, in the schema of the spec's `interface`. |
| `../../../tests/unit/test_gap_junction_references.py` | The test. It is self-contained: it reads the spec and the interface as data and re-implements the exact solve. It recomputes the schema, the declaration echoes, every network under all three readings (exact zero residuals, correct rounding, the declared bounds), the chains (the full balance under two port loads, the recursion and the closed form), the figure8 networks' Norton lines, the limits and the printed recursion. It does not repeat the tree reduction or eq. 2. Its task A checks take about 0.1 s. The task B checks are described below. |

### Regenerating

Run from the repository root, on one of the light CPUs:

```
taskset -c 6 /mnt/workspaces/Cells/venv-cpu/bin/python -I validation/gap_junction_tissue/references/linear_reference.py          # writes interface/linear.json
taskset -c 6 /mnt/workspaces/Cells/venv-cpu/bin/python -I validation/gap_junction_tissue/references/linear_reference.py --check  # recomputes and compares byte for byte
taskset -c 6 /mnt/workspaces/Cells/venv-cpu/bin/python -I validation/gap_junction_tissue/references/linear_reference.py --exact  # also prints the exact rationals
```

- A run takes about 0.25 s.
- `--spec FILE` reads the spec from a file instead, for a checkout without the tag.
- The generator stops with an error if the spec's format, keys or interface change. It also stops if
  a clause of `model.balance`, `model.chain` or `requested` that the derivations rest on changes.

### Derivations

Units throughout: conductances in G_eq,1 = V_1 K_dec, so G_eq,i = s_i (s_i is the size), and
concentrations in the preprint's [mR] units. Write g for a junction's G_GJ, and (h, G_p) for a probe's
held concentration and conductance.

#### 1. The steady balance

At steady state, `model.balance` gives for every cell i:

    0 = s_i (u_i - c_i) + sum_j g_ij (c_j - c_i) + sum_p G_p (h_p - c_i)

This is the preprint's eq. 1 per cell: generation K_dec u_i and decay K_dec give the black box
c = u - i_exit / G_eq with G_eq = V K_dec. The junctions follow Fick's law without drift.

In matrix form, M c = b:

- M = diag(s) + (the junction Laplacian) + diag(G_p).
- b_i = s_i u_i + sum_p G_p h_p.

M is strictly diagonally dominant (every s_i > 0), so it is nonsingular. Gauss–Jordan elimination
without pivoting never meets a zero pivot.

The system is solved over the rationals. The residual of every cell's balance is then evaluated
exactly, straight from the declaration, and is zero. That proves the values are the steady state.

#### 2. Two cells: eq. 2

Let r_X = G_rel,X^-1 = g / s_X. Then:

    c_A = [(1 + r_B) u_A + r_A u_B] / (1 + r_A + r_B)
    c_B = [r_B u_A + (1 + r_A) u_B] / (1 + r_A + r_B)

- The first line is the preprint's eq. 2, A line. The second is its mirror.
- The generator does not use the printed B line. Its numerators lack the -1 exponents
  (G_rel,A and 1 + G_rel,B). The line before it has G_rel,A^-1 as the weight of mR_UL0, where the
  balance gives G_rel,B^-1; the two agree only when the sizes are equal.
- Every two-cell network (figure3-*, figure5-lumped-*) equals this form exactly.

#### 3. Any tree: the black-box reduction (eq. 1, Fig. 7)

Seen from its root through a junction g, a subtree with Norton pair (G, U) is a branch of
conductance (G^-1 + g^-1)^-1 with source U.

1. Fold every subtree into its root, leaves first.
2. Solve the root.
3. Unfold downwards: c_v = (sum of G U at v + g c_parent) / (sum of G at v + g).

Every declared network is a tree, and each equals section 1 exactly. For figure5-network-g, hub A
reduces to conductance 1 + 2g/(1 + g) with source 10, and hub B to 1 + 3g/(1 + g) with source 5;
eq. 2 then joins them.

#### 4. A uniform chain with a load at its port

The chain is cells 0 .. n-1: size 1, unloaded u, every g = 1. Cell 0 is sealed and cell n-1 carries
a probe (h, G_p). Let e_k = c_k - u.

- **Cell 0:** e_1 = 2 e_0.
- **Interior cells:** e_(k+1) = 3 e_k - e_(k-1).
- **Hence** e_k = F(2k+1) e_0, with Fibonacci F(1) = F(2) = 1.
- **The port:** since 2 F(2n-1) - F(2n-3) = F(2n),

      e_0 = G_p (h - u) / (F(2n) + G_p F(2n-1))

  (n = 1 is the same formula, with F(2) = F(1) = 1).
- **The port value** is c_(n-1) = (G_n u + G_p h) / (G_n + G_p), with G_n = F(2n)/F(2n-1). This is
  the Norton form of section 5.

Every figure8-* network equals this closed form exactly.

#### 5. Chains: G_eq,n / G_eq,1 and the intercept (`model.chain`)

The chain has n equal cells, every junction G_GJ = G_eq,1, and every cell unloaded 1. It is sealed
at its first cell; i_exit leaves its last cell, the port. Its port value is c = u_n - i_exit / G_eq,n.

**(a) Direct circuit analysis.** Suppose a chain of k cells obeys c_k = U_k - i / G_k at its port.
Add cell k+1 behind a junction G_GJ. Two branches then feed the new port:

- the old chain through the junction: conductance (G_k^-1 + G_GJ^-1)^-1, source U_k;
- the new cell's own generation and decay: conductance G_eq,1, source u.

Its balance gives c = U_(k+1) - i / G_(k+1), where:

    G_(k+1) = (G_k^-1 + G_GJ^-1)^-1 + G_eq,1
    U_(k+1) = [(G_k^-1 + G_GJ^-1)^-1 U_k + G_eq,1 u] / G_(k+1)

- The recursion starts from G_1 = G_eq,1 and U_1 = u.
- So U_n = u = 1 for every n: the intercept.
- With G_GJ = G_eq,1 = 1, the conductance follows G_(k+1) = G_k / (1 + G_k) + 1.
- Write G_k = p/q. Then p' = 2p + q and q' = p + q. Since F(2n+2) = 2F(2n) + F(2n-1) and
  F(2n+1) = F(2n) + F(2n-1), this gives **G_n = F(2n) / F(2n-1)** (part (c)).

**(b) The full balance with a load at the port.**

1. The n-cell chain carries a probe (h, G_p) at its port.
2. Section 1 solves it exactly, and the exit current is i = G_p (c_port - h).
3. Two loads fix the line c_port = U_n - i / G_n: h = 0.5 and h = 2 with G_p = G_eq,1. These are the
   figure8 networks' loads.
4. A third load (h = 0, G_p = 3) must fall on the same line. The unloaded chain's port value must
   equal the intercept.

**The results:**

- (a), (b) and (c) agree exactly for n = 1, 2, 3, 4, 5 and 10.
- All twelve figure8 networks' port values lie exactly on their chain's line.

| n | 1 | 2 | 3 | 4 | 5 | 10 |
|---|---|---|---|---|---|---|
| G_eq,n / G_eq,1 | 1 | 3/2 | 8/5 | 21/13 | 55/34 | 6765/4181 |
| intercept | 1 | 1 | 1 | 1 | 1 | 1 |

#### 6. The limits

**The pairs.** Let L = (s_A u_A + s_B u_B) / (s_A + s_B). Then:

    c_X(g) - L = s_A s_B (u_X - L) / (s_A s_B + g (s_A + s_B))

This holds for X = A and X = B.

- By Cramer's rule, c_X(g) is a ratio of first-degree polynomials in g, with denominator
  s_A s_B + g (s_A + s_B). The identity therefore holds for every g once it holds at two values.
  The generator checks it exactly at five: g = 1/2, 1, 10, 10^6 and 10^30.
- Both cells therefore tend to L as g grows without bound. This is the preprint's syncytium:
  the size-weighted mean.
- **figure3:** u = 5 and 10, equal sizes. L = **15/2**.
- **figure5b:** u_A = 10 with s_A = 1, and u_B = 5 with s_B = 4/3, as `requested.limits` states.
  L = **50/7**.

**The chain.**

- The map f(G) = G / (1 + G) + 1 sends [1, 2] into itself, and |f'(G)| = (1 + G)^-2 <= 1/4. It is a
  contraction.
- Its fixed point solves G^2 - G - 1 = 0, so the limit is **(1 + sqrt 5) / 2**.
- mpmath is not installed in venv-cpu, so the generator brackets this root with exact rationals. The
  bracket comes from an integer square root at 256 bits, and its width is 4.3e-78.
- The generator checks that lo^2 - lo - 1 < 0 < hi^2 - hi - 1.
- Both ends round to the same binary64.
- G_10 = 6765/4181 lies 2.6e-8 below the limit.

#### 7. The printed recursion

Both forms run from G_1 = 1 at G_GJ = G_eq,1 = 1. Each gives ten values, G_eq,1 .. G_eq,10.

- **`literal`:** G_(n+1) = 1 / [(G_n^-1 + G_GJ^-1)^-1 + G_n], exactly as printed on p. 15 and in
  the appendix's bullet on p. 20.
- **`resistance_form`:** G_(n+1) = (G_n^-1 + G_GJ^-1)^-1 + G_n, as the spec defines it. This is
  Fig. 7's R_thev2 = 1 / (1/(R_thev1 + R_GJ) + 1/R_thev) read with R = G^-1.

| n | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| literal | 1 | 2/3 | 15/16 | 496/705 | 846705/945376 |
| resistance_form | 1 | 3/2 | 21/10 | 861/310 | 1275141/363010 |
| physical (5a) | 1 | 3/2 | 8/5 | 21/13 | 55/34 |

`--exact` prints all ten values of each.

- The appendix derives the step from one cell to two, where cell B "has the same internal generation
  rate and volume as cell A". There the last term G_eq,A is both the old chain's conductance and the
  new cell's own.
- The physical recursion (5a) keeps the new cell's own G_eq,1 as the last term at every step.
- The printed forms carry G_eq,n instead. The literal form also takes the reciprocal.
- The resistance form therefore equals 5a at n = 2 and departs from n = 3. The literal form departs
  from n = 2.

### Accuracy

- **Rounding.** Every float in the interface is the correctly rounded binary64 of an exact rational.
  The generator proves this for each value: it compares, exactly, against both neighbouring
  binary64 numbers. So |fl(x) - x| <= 2^-53 |x|.
- **`accuracy_rel`.** Each network and each chain declares 2^-53 = 1.1102230246251565e-16, and the
  bound is verified exactly for every value. The largest actual relative rounding error over all
  network concentrations is 1.07e-16. Many values are exact: every chain intercept, and
  G_eq,n/G_eq,1 for n = 1 and 2.
- **The size 1.3333333333333333.** The figure5-lumped-* networks declare this size.
  - The interface solves its exact binary64 value. That is what any JSON reader gets, and what the
    echoed declaration holds.
  - The generator also solves each of those networks exactly with the size read as the decimal
    literal and as 4/3.
  - The three exact solutions differ by at most 9.5e-18 relative.
  - The declared 2^-53 bounds the reported values' error against all three readings (at most
    5.9e-17), so the reading cannot change a comparison.
- **The limits and the printed recursion.** They are correctly rounded in the same way. The schema
  gives them no accuracy field.

## The "neither" threshold (task B)

The specification is `spec/neither.json` at the tag `gj-neither-registered-2026-11-23`. That tag is
the same commit as task A's.

The references read only two inputs: the specification at that tag, read with `git show`, and the
preprint. The names in the spec's `constants_source` record where the numbers came from, and the
references do not follow them.

### Files

| File | What it is |
|---|---|
| `neither_reference.py` | The generator: stage 1, the search for each geometry, and the interface. It uses numpy and scipy only, and imports nothing from the engine or from this package. |
| `interface/neither.json` | The references, format `gap_junction_tissue.neither_references@1`, in the schema of the spec's `interface`. |
| `/mnt/workspaces/Cells/gj-references-20261123/run-b674113c/` | The run folder (outputs, not source). |

The run folder holds:

- `stage1.json`;
- `line-points.jsonl` and `field-points.jsonl`: every integration, written as it finished, with its
  diagnostics;
- `line.json` and `field.json`: each search's bracket, tighter rerun, explicit check, end-state
  diagnostics and provenance (the generator's head, which was clean);
- the logs.

### Regenerating

Run from the repository root, with `PY="taskset -c 6 /mnt/workspaces/Cells/venv-cpu/bin/python -I"`,
`RUN=<a new run folder>` and `OMP_NUM_THREADS=1`:

```
$PY validation/gap_junction_tissue/references/neither_reference.py stage1 --run-dir $RUN
$PY validation/gap_junction_tissue/references/neither_reference.py search --geometry line --run-dir $RUN
$PY validation/gap_junction_tissue/references/neither_reference.py search --geometry field --run-dir $RUN
$PY validation/gap_junction_tissue/references/neither_reference.py interface --run-dir $RUN          # writes interface/neither.json
$PY validation/gap_junction_tissue/references/neither_reference.py interface --run-dir $RUN --check  # compares byte for byte
```

The searches are deterministic. On CPU 6, which other jobs shared, they took 26 s for the line and
2 min 51 s for the field (wall time, the tighter and explicit reruns included).

### The model as implemented

Each cell carries u (total miR200), m (Zeb mRNA) and z (ZEB protein):

    du/dt = g_u H(z; K_u, n_u, lambda_u) - k_u u + sum over its junctions of (G/V) (u_j - u)
    dm/dt = g_m H(z; K_m, n_m, lambda_m) - k_m m
    dz/dt = g_z m P(X) / (1 + X)^6 - k_z z,   P(X) = sum_{i=0..6} C(6, i) l_i X^i,   X = u / x0
    H(z; K, n, lambda) = (1 + lambda (z/K)^n) / (1 + (z/K)^n)

- G/V = `g_over_v_per_d` x D. The generator checks that `g_over_v_per_d` equals 3 / (r L_GJ) from
  `radius_m` and `junction_length_m`.
- Only u crosses junctions.
- The constants are used exactly as read.

### Geometries

- **line:** 25 cells, c0..c24 along z. The tumor is c0..c5. There are 24 junctions, c_k - c_(k+1).
  Each cell is its own row.
- **field:** 625 cells, c{y}_{z}. The tumor is the 36 cells with y < 6 and z < 6. There are 1,200
  junctions between cells one lattice step apart, and no diagonals. Row z holds c0_z .. c24_z.
- **The spec's `nodes`** (26 and 626) count the cells plus one held outside node. No equation uses
  that node, and the lead confirmed on 23 November that it carries no physics here. It is not
  modelled.
- **Assertions:** the generator checks the counts of cells, junctions, tumor cells and neighbours,
  and that the rows partition the cells.

### The stages and the criterion

**Stage 1** runs once. One tumor cell and one healthy cell, uncoupled, run 500 s from the seeds.
- Integrator: DOP853 at rtol 1e-13, atol 1e-16.
- Radau at rtol 1e-12 agrees with it to 6e-14 relative.

**Stage 2** runs once for each D.
- Every tumor cell starts at stage 1's tumor end state, and every healthy cell at its healthy one.
- It runs coupled for 20,000 s, its clock starting from 0.

**The criterion**, at t = 20,000 s: a point is normalized when u > m + 2 in every cell and
max m - min m <= 2 in every row. Each point records:

- `epithelial_cells`: the number of cells with u > m + 2;
- `min_margin`: the least u - m - 2;
- `max_row_spread`: the largest row spread of m.

`normalized` follows from min_margin > 0 and max_row_spread <= 2. The generator asserts this.

### The integrator and its checks

- **The integrator.** Stage 2 uses scipy's `BDF` (variable order 1 to 5) with the analytic sparse
  Jacobian, at rtol 1e-9 and atol 1e-12. It steps to exactly t = 20,000 s and keeps only the final
  state.
- **The Jacobian check.** Each search starts by checking the Jacobian against central differences.
  It agrees to about 1e-9.
- **The tighter rerun.** The spec requires both final bracket ends to be rerun at rtol 1e-10,
  atol 1e-13.
- **The explicit check.** Both final ends are also rerun with DOP853 at rtol 1e-9, atol 1e-12. This
  is an explicit 8th-order Runge–Kutta method: no Jacobian and no implicit damping. It guards
  against an implicit method damping a slowly growing mode near the threshold.
- **The field's symmetry.** The field is symmetric under y <-> z, and every field end state is
  checked to be so, to within 1e-6 relative. Rows stay rows of one z.
- **Steadiness.** The run logs record |dy/dt| at t = 20,000 s for every point.

### The search

1. Run D = 0 and D = 1e-13 first. They must give not normalized and normalized.
2. Bisect: mid = (lo + hi) / 2 replaces lo or hi by its outcome.
3. Stop when hi <= 1.001 lo. The test is exact, on the rationals of the binary64 values.

- Every point is integrated from stage 1's end state over the full 20,000 s.
- The interface lists the points sorted by D. Bisection makes the outcomes monotone, and the
  generator asserts it.

| Geometry | lo (m²/s) | hi = x2 (m²/s) | hi/lo - 1 | Points |
|---|---|---|---|---|
| line | 7.171630859375002e-15 | 7.177734375000002e-15 | 8.5e-4 | 16 |
| field | 1.8859863281250003e-15 | 1.8875122070312503e-15 | 8.1e-4 | 18 |

**The tumor flips cell by cell.** Below the threshold, only the most exposed tumor cells have flipped
by t = 20,000 s. Near it, the flips cascade inward, and whether the cascade finishes within 20,000 s
decides the outcome.

- At the line's lo, the end state is still changing: one cell is mid-flip, with |dy/dt| = 1.1e-3 per s.
- The outcome is therefore a finite-horizon one: the state at t = 20,000 s, as the criterion defines it.
- The tighter and explicit reruns move the least margin there by about 1e-6, and keep both outcomes.

**In the field**, the lo end has flipped 8 of the 36 tumor cells, so 597 of 625 cells are epithelial.

- It is nearly steady at t = 20,000 s: |dy/dt| = 8.0e-8 per s.
- At hi, all 625 cells are epithelial.
- The tighter and explicit reruns move the least margin by at most 5e-11, and keep both outcomes.

### The test

The task B part of `tests/unit/test_gap_junction_references.py` checks:

- the schema and the echo of `model.constants` and `seeds`;
- the interface's conditions: the stopping rule in exact rationals; lo not normalized and hi
  normalized, in the points and at the tighter tolerance; the points monotone in D, with 0 not
  normalized and 1e-13 normalized; each outcome consistent with its recorded numbers;
- stage 1, recomputed with ODEPACK's LSODA (scipy `odeint`), to 1e-8 relative;
- the line's two final ends, recomputed with LSODA from that stage 1, keeping their outcomes. LSODA
  is a third integrator, besides the generator's BDF and DOP853, and the test uses its own
  right-hand side.

The field is not re-integrated in the test. The whole file takes about 2.5 s under pytest on a
shared CPU 6, and the line recompute is nearly all of it (1.1–1.9 s, depending on the load).
