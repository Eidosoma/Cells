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
| `../../../tests/unit/test_gap_junction_references.py` | The test. It is self-contained: it reads the spec and the interface as data and re-implements the exact solve. It recomputes the schema, the declaration echoes, every network under all three readings (exact zero residuals, correct rounding, the declared bounds), the chains (the full balance under two port loads, the recursion and the closed form), the figure8 networks' Norton lines, the limits and the printed recursion. It does not repeat the tree reduction or eq. 2. Its checks take about 0.1 s; pytest reports 0.5 s for the file, collection included. |

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
