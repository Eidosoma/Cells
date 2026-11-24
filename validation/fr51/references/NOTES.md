# FR-51 reference: readings and checks of the spec

This note lists every reading the spec needed, and the result of checking its declared values for
consistency. No reading changes a law; each fixes a detail the spec leaves open.

## Readings

1. **One temperature.** LAWS.md §1 says T is declared per case, but `cases.json` declares one, 310 K,
   under `constants`, and none per case. Every case uses 310 K.

2. **E_ion "to 50 digits".**
   - This is read as 50 significant digits: the Nernst potential is evaluated at 120 digits and
     rounded half-even.
   - That 50-digit value is E_ion everywhere: in the voltage list, in V_ref = V − E_ion and in
     `u_at_reversal`.
     - So V_ref is exactly 0 at V = E_ion.
     - So `u_at_reversal` is exactly the closed form (Σ w K(0)/(c_B + K(0)))/Σ w under the
       reversal reference.
   - It differs from the exact Nernst potential by less than 5e-53 V. That moves no other reported
     value by more than about 1e-49 relative.
   - Hence the flux at V = E_ion is not 0. It is about 1e-51 of its two terms, the residue of E's
     rounding, and it is reported to full accuracy with its sign. This is why route A works at 120
     digits.

3. **The voltage list.**
   - It holds the 361 grid voltages in grid order, then E_ion, E_ion − 0.0005 and E_ion + 0.0005.
     These are appended, not sorted in or merged.
   - In P1, E_ion = 0, so the three extras repeat grid voltages. They are kept, and written `"0"`,
     `"-0.0005"` and `"0.0005"`, against the grid's `"0.0000"`.
   - `voltage_index` gives the extras' positions.

4. **The evaluation points.**
   - Every quantity is evaluated at the exact decimal value of its voltage string.
   - The registration reads these strings as binary64 (its §2). The gap between the two is
     outside this reference.

5. **The number format.**
   - Computed values have 30 significant digits, as `d.ddd…e±N`, rounded half-even.
   - Values that are exactly 0 are written `"0"`. These are P1's free flux and current at V = 0,
     θ_k at c_B = 0, and V_ref at V = E_ion.
   - The voltages and V_ref are written as exact decimal strings, such as `"-0.1200"` or E_ion's
     51 decimal places. These are exact values, not computed ones, so "at least 20 significant
     digits" is read as applying to computed values.

6. **Per-mode outputs.** `theta_k` and `one_minus_theta_k` are lists over the block's modes, in
   declared order from 0. Each is a list over the voltages.

7. **Cases without a block.**
   - These report the free arrays, `u` (exactly 1 at every voltage) and `u_at_reversal` = 1.
   - V_ref, θ and the blocked quantities are omitted, as `requested_outputs.unblocked_cases`
     says.

8. **Concentration slopes under the membrane voltage.** Here ∂V_ref/∂c = 0 (LAWS.md §5), so each
   slope is u times ∂J_free/∂c.

9. **The counts.**
   - C1's `abundance` of 2 replaces the population's 1.
   - C2's abundance is N/(A ρ_ref): 1000/(1e-9 × 1e12) = 1 and 2000/(1e-9 × 1e12) = 2, exactly.
   - So C2_units_declared repeats B1_two_modes_E1 value for value, and C2_units_doubled repeats
     C1.

10. **The second route.**
    - mpmath is not installed in the checkout's environment. Route B therefore uses exact rationals
      with its own exp and ln, which the self-check compares with `decimal` at 250 digits.
    - The slopes' step is 1e-50 V (1e-50 relative for a concentration), at about 192 digits. The
      README's example is 1e-12 at 50 digits. With the smaller step, the difference quotient's
      truncation stays below 1e-93, even for the steepness-8 cases.
    - Under the reversal reference, E at a perturbed concentration is recomputed unrounded. It
      enters as an offset from the 50-digit E_ion, so the difference is centred on route A's V_ref.

11. **The difference measure.**
    - It is |A − B|/max(|A|, |B|), in exact rational arithmetic.
    - A quantity that is exactly 0 in both routes counts 0; both routes give these zeros exactly.
    - V_ref is compared by its absolute difference, which is 0.

12. **"Two properties to report" (LAWS.md §2).** Each file reports them under `properties`:
    - at reversal, the flux at E_ion against the largest flux, and the flux's sign on either side;
    - for P1, the line through zero: G_lin = A P r a o v c z² F²/(R T), and I's largest relative
      deviation from G_lin V.

13. **B(x) near 0.**
    - LAWS.md §7 suggests summing B from its series near 0. Route A instead forms e^x − 1 with a
      correctly rounded exp, at a precision raised by the digits the subtraction cancels.
    - The two agree at the declared accuracy. Apart from x = 0, which takes the limit, the grid's
      smallest |x| is about 0.019.

## Declared values checked for consistency

No declared value was found inconsistent. The checks were:
- every block's modes declare exactly one steepness;
- every set of weights sums to 1 exactly;
- every K(0), c_B and steepness lies inside the registration's admitted domain;
- every reversal reference names its population's ion.

The reference also reproduces the registration's §7 figures, which informed its bands and are not
declared values:
- G3 exceeds G_max by about 7.9 times;
- B1 exceeds u G_max by about 2.1 times;
- B1 at E1, at +50 mV, gives about 190 for criterion E's plant (i);
- B4's u is about 0.989 at −80 mV.
