# FR-49 reference: readings and checks of the spec

This note lists every reading the spec needed, and the result of checking its declared values for
consistency. No reading changes a law; each fixes a detail the spec leaves open.

## Readings

1. **World L's matrix exponentials, at high precision.**
   - The README's "exact solution by matrix exponentials" is evaluated in decimal arithmetic at
     70 digits, not in binary64. The method is the Taylor series of the augmented system
     y = (n_O, n_C, x_O, x_C, 1), with scaling and squaring.
   - The README's 1e-13 is demonstrated by a second high-precision route, the eigen closed form:
     e^(A dt) by Sylvester's formula, about each interval's steady state.
   - Radau is the README's ODE cross-check, run as three solves stopped at t₁ and t₂, at atol
     1e-30.
   - Its rtol is 1e-13, against the README's example of 1e-12. At 1e-12 its largest difference
     was 1.75e-13, between the ODE bound of 1e-10 and World L's declared 1e-13. At 1e-13 it is
     below 1e-13, so the check passes whichever bound it is read against, and it is held to
     1e-13.

2. **World L's names and units.**
   - `n_O`, `n_C`, `x_O` and `x_C` are `cases.json`'s names, in fmol.
   - The base amounts n − x are `base_O` and `base_C`. The shares x/n are `share_x_O` and
     `share_x_C`.
   - Each file's `quantities` block gives every name's unit and definition.

3. **World L at t₁ and t₂.**
   - Both are sample times. The state is continuous there; only the source switches. So the samples
     at t₁ and t₂ are unambiguous.
   - x_O and x_C are exactly 0 up to and including t₁.

4. **World B's root and transient.**
   - L_T = n_L(0) + B(0), S = α ν N/N_f, and b is in fmol.
   - The root takes the b < 0 branch.
   - B₁ is formed as L_T S/B₂, from the product of the roots, which avoids cancellation.
   - The transient is written B = B₁ − r (B₂ − B₁)/(1 − r), with r = r₀ e^(−λt). This is
     LAWS.md §3's form solved for B. B(0) is B₀ exactly.

5. **World B's names.**
   - `once` uses `cases.json`'s names: `S`, `K_d`, `b`, `c*`, `B*`, `B1`, `B2` and `lambda`. `L_T`
     and `d` are added.
   - The well beside C has no requested quantity, so it is not reported. LAWS.md §3 says C's
     equations hold through its wash, and they are integrated through it.

6. **World B's checks.**
   - The closed form is checked by a Taylor-series integration of the binding equation at 50 digits
     (step 0.05 s), and by Radau on (B, n_L).
   - The root is checked by comparing B* = L_T − V_C c* from its formula with B₁ from the quadratic
     in B.
   - Each `once` value also has a second route:
     - S, K_d, L_T and b in exact rationals, and d from b² + 4 V_C L_T K_d;
     - B₁ = (s − d)/2 and B₂ = (s + d)/2, since s² − 4 L_T S = b² + 4 V_C L_T K_d makes
       B₂ − B₁ = d;
     - λ = k_on d/V_C, c* = (L_T − B₁)/V_C, and B* = B₁.
   - The Taylor and Radau routes form their own S and L_T from the declared values, and so do C2's
     check routes.

7. **C1.**
   - "Just before" and "just after" are t_w− and t_w+.
   - "The shares there" are both x/n and b/n at W, with n_W = x_W + b_W.
   - World L's quantities are repeated in `C1.json`, identical to `L.json`'s, since the wash leaves
     them unchanged.

8. **C2's transient, at high precision.**
   - The reported transient is a Taylor-series integration of LAWS.md §5's two equations at 50
     digits, step 0.1 s. It is more accurate than the README's Radau at rtol 1e-12.
   - The README's ODE routes become the cross-checks: Radau at rtol 1e-12, and DOP853 at rtol 1e-13
     as its "checked by DOP853".
   - A rerun at step 0.05 s shows that the integrator has converged. The same integrator matches
     World B's exact transient.
   - The root comes from one equation in the free sites R, by Newton from R = 0. It is checked by
     Newton on LAWS.md §5's two equations as written.

9. **C2's ODE states.**
   - The ODE routes integrate R as a state of its own: dR/dt = −(J₁ + J₂), from R(0) = S.
   - Formed as S − B₁ − B₂, R would carry the bound amounts' errors amplified S/R times, about 50.
     DOP853's difference on R was then 1.7e-10, above the ODE bound. With R integrated it is
     1.7e-11.

10. **The difference measure.**
    - It is |A − B|/max(|A|, |B|) at each sample, in exact rationals. This is stricter than the
      registration's max-normalised e_q.
    - e_q's form is also reported for the ODE routes, as `max_normalised_difference`.
    - Quantities that are exactly 0 in both routes count 0, such as x before t₁ and B(0).

11. **The number format.**
    - Every value has 30 significant digits, as `d.ddd…e±N`, rounded half-even.
    - Exact zeros are written `"0"`. Times are exact decimal strings.

12. **The declared accuracy, by quantity.**
    - 1e-20 for the 30-digit quantities:
      - World B's transient and root;
      - C1;
      - C2's root;
      - as delivered, World L's and C2's transients, whose high-precision checks are reported.
    - 1e-10 for each ODE route's difference, except World L's, held to 1e-13 (reading 1).
    - 1e-13 for World L's matrix exponentials, shown by the eigen form.

## Declared values checked for consistency

No declared value was found inconsistent. The checks were:
- every last sample time is its world's horizon;
- the pulse lies inside world L's horizon, and C1's wash falls inside the pulse, as `cases.json`
  notes;
- sites_per_copy is an integer;
- C1's buffer declares S only;
- C2 has two ligands with zero initial bound amounts.

The reference reproduces the registration's §6 figures, which informed its bounds and are not
declared values:
- World L's eigen-rates are 6.4e-5 and 3.1e-3 /s, and C's labelled share peaks near 0.23 after the
  pulse;
- World B binds 97% at equilibrium, on the b < 0 branch, with τ = 15.8 s, and plant (a)'s Langmuir
  misses B* by 2.9%;
- C2's slowest relaxation time is 49.7 s.

One figure differs: §6 gives C2's remainder at 2000 s as 1.7e-16.
- The 50-digit transient gives about 2e-19 relative to B_j*, decaying as e^(−t/49.7 s).
- 1.7e-16 is at binary64's resolution; Radau and DOP853 here give between about 5e-17 and 6e-15.
- Every one of these figures is far inside C2-3's 1e-10.
