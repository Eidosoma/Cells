# FR-38's second comparison: the code-blind references

These are the code-blind references for FR-38's second registered comparison (D334). They are
written afresh from the references' spec folder and nothing else. The folder is
`validation/gene_regulation/fr38_v2/spec/` at efb311fd: the tagged criteria
`fr38-v2-criteria-2026-11-24` (707014e4) with `AMENDMENT-2026-11-24.md` and
`AMENDMENT-2-2026-11-24.md`, together with the sheet sections that its `LAWS.md` names.

## What was read, and what was not

**Read:**
- the spec folder: README, SPEC, LAWS, READOUTS, CRITERIA and both amendments, with their hashes
  checked;
- `docs/TEMPLATED_POLYMERISATION_LAWS.md` at 707014e4, only the sections LAWS.md §0 names:
  - §0 to §2, §3.1, §3.2, §3.4, and §4.1 to §4.8;
  - §5.1's table, "The initial state", "The schedule" and "The horizon";
  - §9.1 to §9.8, and §9.9's addendum;
  - §9.12, readings 1 to 3 and 5 to 9;
  - §9.14, §9.19 and §9.22.

**Not read:**
- `src/`, `tests/`, any engine module or output;
- any Python file under `validation/` outside this folder;
- FR-38's first comparison: its references, rule, errata, records and diagnosis;
- the protocol document.

Nothing here imports, runs or reads the engine.

**Seen in passing, and not used.** While locating the permitted sections, a few things were seen:
- the sheet's heading list;
- the first 60 to 80 characters of each line of §9.12, including its intro and reading 4;
- the heading lines of §5.1's closed forms and measured bound;
- the first lines of §9.9 and its R1 release table, which follows the addendum;
- the file names in `validation/gene_regulation/`, from one directory listing.

None of these was used. Every value here comes from the spec folder's inputs and the permitted
sections.

## Files

| File | What it holds |
| --- | --- |
| `fr38v2_worlds.py` | Every family's declared inputs (SPEC.md §1, §2, §8), echoed into each file's `inputs` with units in the names |
| `fr38v2_model.py` | The equations of motion, vectorised over a family's rows (runs, blank, planted worlds), in deviation form and numpy long double |
| `fr38v2_integrate.py` | The two methods: Gauss–Legendre collocation (primary) and Gragg–Bulirsch–Stoer extrapolation (second), with their coefficients derived in `decimal` |
| `fr38v2_writer.py` | Readouts, classes, scales, accuracy, checks, survival, route 2, the excess over the blank, the plants' predicted effects, and the deterministic JSON |
| `regenerate.py` | The bitwise regeneration under several `PYTHONHASHSEED` values, and the publication into `out/` |
| `test_fr38v2_references.py` | The self-check (about 10 s, no engine import) |
| `out/reference_{AF,AN,B,C,D}.json` | The references |
| `out/reference_invented.json` | The format sample on invented inputs, for the judge's first read (SPEC.md §8) |
| `out/SHA256SUMS`, `out/provenance.json`, `out/run_times.json` | The sidecars of amendment 2, Q5 |

## The model

Each family is one system of ODEs with these parts:
- every row, the hold, and the stage complexes;
- the free machines;
- the cumulative extents and every heat class;
- the five membership classes per fate row;
- the net trackers;
- the excess-over-blank difference states, and the plant-only classes.

Every rate is the sheet's (all in fmol/s, with concentrations n/V in mM):

- **Initiation** (§4.1): J_I = u k_I c_T F. Here c_T = T·COPY_FMOL/V and u = 1, except in B, where
  u is §4.6's Hill factor on c_X = n_X/V.
- **The stages** (§4.2): J_j = (v/r) C_j φ, with φ = c_N/(K_N + c_N)·(1 − e^x) and
  x = μ°_res + 2(μ°_Pi + ln a_Pi) − (μ°_N + ln a_N). The activities are a = c/(1000 mM).
  - S = Σ J_j.
  - The completions are Q_c = J_8, into the hold.
- **The hold and release** (§9.2, §9.3, §9.7):
  - dH/dt = Q_c − Q^d − Q^s, with Q^d = p H/τ and Q^s = (1 − p) H/τ.
  - Free machines: dF/dt = −J_I + Q_c (`returned`) or −J_I + Q^d + Q^s (`held`). With `held`,
    F(0) = M − H(0).
- **The fates' two-sided losses** (§4.4, §9.2, erratum I item 1):
  - The net loss is D_f = k_f n_f (1 − e^{y_f}), with y_f = μ°_M + ln a_M − (μ°_f + ln a_f)/L.
  - It returns L monomers of M per molecule.
- **Heats** (§3.4, §9.5), each flux times its −ΔG:
  - transcription: r S (−x) RT, with no release term;
  - each degradation: D_f (−L y_f) RT;
  - each release: Q^f (−ln a_f) RT.
- **The classes** (LAWS.md §1, erratum I item 2):
  - each class is integrated by its own law and never formed as a difference;
  - releases join `pre`, `win` or `post` by the label in force on the span, with restarts at t1
    and t2;
  - re-synthesis k n e^{y} joins `resyn`;
  - every class leaves at the gross rate k_f.
- **The net tracker** (erratum I, item 6) starts at 0 and is fed during W, decaying at
  k_f (1 − e^{y_f}).
- **The excess over the blank** (SPEC.md §3, item 5):
  - The blank is a row of the same system.
  - X_f = n_f − n_f^blank is carried as its own state:
    dX_f/dt = Q^f − [k_f (X_f − Δρ_f) + (k_f − k_f^b)(n^b − ρ^b)].
  - The re-synthesis difference Δρ_f = ρ_f^b expm1(Λ) is formed without cancellation. Here
    Λ = (1 − 1/L) log1p(X_f/n_f^b) + log1p(X_M/n_M^b) − (1 − 1/L) log1p(X_V/V^b).
  - X_M (and X_Mx in C, X_V in D) carry their own difference laws.
  - So the run's and the blank's common part never enters X_f.
- **Family C** (LAWS.md §3): J = k_f (n_M − n_Mx), at equal network potentials. Its heat is
  J RT ln(n_M/n_Mx).
- **Family D** (LAWS.md §4):
  - Π = RT·Σ n_s/V, over K, Y, N, M, Pi, R and R_s, with ψ_cell = −Π and
    ψ_out = −RT·(56 + 56 + 5 × 4·10⁻¹⁶) mM.
  - The flux is Q = 10¹⁵ A L_p (ψ_cell − ψ_out) and dV/dt = −Q.
  - Water's heat is 10⁻³ Q (ψ_cell − ψ_out), and the bath's work is −10⁻³ ψ_out Q.
  - Every gene-unit rate and booking reads the current V.
  - A volume outside [0.5, 3.0] pL is refused.
- **Arm B** adds:
  - the regulator (§4.6);
  - recharging (§4.5), with share 2;
  - two translation chains `tl` and `tl_s` (§9.9's addendum), sharing the ribosome pool and
    making P;
  - protein degradation.
- **G − G(0)** (LAWS.md §5) is formed row by row in deviation form:
  δn (μ° + ln a − 1) + n(0) [log1p(δn/n(0)) − log1p(δV/V(0))], plus μ°_res (W_tx + L δH).
  - In B, μ°_P,res (W_tl + W_tl_s) is added.
  - In D, K and Y are included.

## Readings (each confirmed by amendment 1, or stated here)

- **RT.** R = fl(N_A·k_B), and RT = fl(R·310.15) J/mol. In kJ/mol, RT is that double divided by
  1000 in long double. This is the engine's double path (amendment 1, item 5).
- **Residue potentials.** μ°_res = fl(μ°_row/L) in doubles, everywhere (amendment 1, item 6):
  - −10.368889000000001 in AN, C and D;
  - 8.599269797012601 in AF;
  - in B, fl(μ°_R/1200), and fl(μ°_P/400) for translation.

  The fate rows use SPEC.md's literals. So the release's booked ΔG, RT ln a_f by definition,
  differs from G's change by RT(μ°_f − L μ°_res) per molecule. That is about 10⁻¹² RT, which is
  invisible in G's identity (below 10⁻²⁰ of its scale).
- **Copies.** Copies are multiplied by the double COPY_FMOL exactly, in long double.
- **The bath in D** holds K and Y at 56 mM. Its five traces are at 0.4 × 10⁻¹⁵ mM, and they count
  in ψ_out.
- **G's scale.** It runs over "the rows whose term in G moves" (amendment 1, item 7): the rows
  whose amount moves in A, B and C (N and Pi do not move in a blank), and every species row in D.
  - In B, the residue term adds RT|μ°_P,res|(W_tl + W_tl_s).
- **P9's G − G(0)** is LAWS.md §5's state function, on the planted run's state at its current V
  (amendment 1, item 8).
- **B's `tl_s` names** follow the engine side's pattern (amendment 1, item 9).
- **P8** is paired with its own matched blank, with the store rate × 1.01 there too (amendment 1,
  item 4).
- **P2's release counter.** Its honest series is +0.0 throughout, so its scale is 0. The entry
  divides by the planted series' own scale instead, and says so in its `scale`. P2 is judged by
  C1, bit for bit.
- **P1′.**
  - Route 2's bound is 3 g(ts), with g LAWS.md §6's grid error, on this file's own counters at
    the declared k_f.
  - The coarse grid is every second output, with t1, t2 and ts kept.
  - The net-rate form uses each output interval's ΔD/∫n dt (trapezoid), from S = 0 at t1.
- **Survival.** It has one entry per fate and per sample time after t2.
  - At an idle fate the entry stays: both counts are +0.0, `"ratio": null`, and its accuracy is
    `[null, null, null]` (amendment 1, item 3).
- **Route 2.** It has one entry per fate and per sample time, t2 included (amendment 1, item 1).
- **The blank** carries `series` and `checks` only.

## Methods and accuracy

- **The primary** is Gauss–Legendre collocation, an implicit Runge–Kutta method.
  - It has 5 stages and is of order 10.
  - Step h = 1 s; 4 s for the invented family.
  - Its stage equations are solved by fixed-point iteration until the stage states stop changing
    at round-off.
- **The primary's refinement** is the same method at h/2. Its truncation error is 2¹⁰ = 1024 times
  smaller, so it is at least 100 times tighter.
- **The second method** is Gragg–Bulirsch–Stoer extrapolation, of a different kind: explicit, the
  modified midpoint rule extrapolated in h².
  - Its substep counts are n = 2, 4, …, 16, so it is of order 16.
  - Macro step H = 2 s; 8 s for the invented family.
  - The midpoint sums run on each macro step's increment.
- **Both methods:**
  - run in numpy long double (x86 extended precision, a 64-bit significand);
  - carry the state in deviation form;
  - use fixed steps that divide every span;
  - restart at every output time and every switch (t1, t2, p_sched's 2700 s, B's t_off, and
    P3's 0.5-s-late switches in AN). No output is interpolated.
- **Coefficients.** The Gauss–Legendre nodes, matrix and weights come from the Legendre
  polynomial in 50-digit `decimal`, with the order conditions B(10) and C(5) asserted. The GBS
  weights are exact rationals.
- **The accuracy of each published value:**
  - it is 4 × max(|primary − refinement|, |primary − second|) + |written double − primary|,
    rounded up;
  - the safety factor is 4;
  - the final term is the float64 publication's rounding (amendment 2, Q7).
- **The writer refuses** to write a family if any judged entry's accuracy exceeds 10⁻¹¹ × its
  scale. That covers series, the excess, survival counts and ratios, and route 2 against its own
  scale.
- **The pool0 closed form** P(0)e^{−k_f t} is evaluated in 50-digit `decimal` on the exact
  long-double values (SPEC.md §3, item 8).

## Classes

Classes come from the model's structure (SPEC.md §4, amendment 1 item 2), never from values. An
entry is `constant`, +0.0 with null accuracy, in these cases:
- at an idle fate, at every output: its releases, its release heat, its `pre`, `win` and `post`
  classes, and its `released_present_gross`;
- in the blank, at every output:
  - the hold, both releases and both release heats;
  - the completions, initiations and stage exits;
  - every stage complex, the engaged machines and W_tx;
  - transcription's heat;
  - every `pre`, `win` and `post` class, and both `released_present_gross`;
- in every run:
  - `win` at t ≤ t1, `post` at t ≤ t2 and `pre` at t = 0;
  - `released_present_gross` at t = 0.

Every other entry is `stepped`. That includes the excess over the blank everywhere, and every
nonzero or structurally unconstrained value, however small. The writer asserts that every
`constant` entry is exactly zero in all three solves.

## Checks (each run's `checks`, largest residual)

- **The membership sum**, against the row, relative to the row's scale.
- **§9.7's identities:** the hold, the producer, each fate row and the machines; in B also the
  ribosomes and the product P.
- **The residues**, r∫S = W + L∫Q.
- **§4.8's moieties:** phosphorus and nucleoside; in B also adenine and amino acid.
- **G's identity**, with water's terms in D.
- **The pool0 closed form**, absolute and relative.
- **The excess**, by its own route against the direct subtraction.

## Plants (`plants`; SPEC.md §6)

Each entry gives the honest and the planted value at the largest distance, `relative_distance`,
and `scale` (amendment 2, Q6). P1′ also carries `route2_bound` (3 g(ts)) and
`distance_in_route2_bounds`.
- **Computed from the honest solution:** P1, P1′, P1″, P6 and P7.
- **Extra non-physical classes in the honest system:** P3a, P3b and P4.
- **Their own planted worlds:**
  - P2 (p = 1 − 2⁻³⁰) and P5 (k_s × (1 + 10⁻⁴)), in AF;
  - P8 (the store rate × 1.01, with its own blank), in C;
  - P9 (the gene unit at V₀), in D.

## Questions and answers (24 November 2026), kept with the references

The references agent asked the lead in writing. The answers became the spec's dated amendments.

1. **Route 2's place in the file.**
   - A run-level `route2` list, accepted (amendment 1, item 1).
2. **`released_present_gross` at an idle fate, in the blank and at t = 0.**
   - `constant` +0.0 where all three summands are constant; accepted (amendment 1, item 2).
3. **Survival at an idle fate, and the blank.**
   - The idle fate keeps its entries, with constant counts and `"ratio": null`.
   - The blank carries `series` and `checks` only (amendment 1, item 3).
4. **P8's blank.**
   - The planted world's own matched blank (amendment 1, item 4).
5. **Run time and hashes.**
   - Sidecars `out/run_times.json`, `out/SHA256SUMS` and `out/provenance.json` (amendment 2, Q5).
6. **Extra plant keys.**
   - `scale` everywhere; `route2_bound` and `distance_in_route2_bounds` on P1′ (amendment 2, Q6).
7. **No mpmath.**
   - Long double for the integration, and `decimal` for the closed form and the quadrature
     (amendment 2, Q7).

**Readings sent for confirmation:**
- RT, P9's G and the `tl_s` names: confirmed.
- The residue potentials: confirmed as fl(μ°_row/L).
- D's G scale: confirmed with K and Y, as a disclosed wording correction (amendment 1, items 5
  to 9).

## Regenerating

```sh
cd validation/gene_regulation/fr38_v2/references
/mnt/workspaces/Cells/venv-cpu/bin/python -B regenerate.py --work <scratch dir> --publish
```

- It runs each family under `PYTHONHASHSEED` 0, 1 and 4242, with every BLAS pinned to one thread,
  one process per CPU.
- It requires the files to be byte-identical across the seeds.
- It refuses a dirty checkout.

The self-check:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /mnt/workspaces/Cells/venv-cpu/bin/python -B -m pytest -q test_fr38v2_references.py
```
