# FR-50 reference: readings and checks of the spec

This note lists every reading the spec needed, and the result of checking its declared values for
consistency. No reading changes a law; each fixes a detail the spec leaves open.

## Readings

1. **The steady cases' cross-check at zero net.**
   - Every steady case (K1, K4, E1–E4) sits at zero net. "Recompute each flux from Ussing's ratio
     and the net" means forward = net/(1 − ρ), with ρ = backward/forward.
   - That is 0/0 where the state is exactly at zero net:
     - K1, E2 and E3, neutral routes at equal concentrations;
     - K4, where ΔG_cyc/RT is exactly 0.
   - There, route B takes each one-way flux from its direct form in exact rationals. It reports
     ρ = 1 and the net = 0 in `checks`, and says which route it used.
   - E1 and E4 are not degenerate. V is E_K rounded to 50 digits, so 1 − ρ and the net are about
     1e-50 of their scale. Both are computed to well over 100 digits, so the recomputation
     recovers each flux there.
   - The host cases (K3, K4h, E6) are off reversal, and use the recomputation directly.
   - This reading was put to the lead as a question on 24 November 2026.

2. **E_K "to 50 digits".**
   - This is read as 50 significant digits: the Nernst potential is evaluated at 120 digits and
     rounded half-even.
   - That 50-digit value is E1's and E4's voltage, and the E_K of V_ref = V − E_K in E4 and E6.
     So V_ref is exactly 0 in E4, and u is exactly 1/2.
   - Route B recomputes E_K with its own ln and rounds it by integer arithmetic; the two agree.

3. **E1's prefactor.** LAWS.md's g = 1e15 P A o, with E1's declared `availability` as o. This is
   @3's membrane route, a patch's own permeability.

4. **Directions.** The forward directions are LAWS.md §2's:
   - inward for K1, K2 and K3;
   - outward for E1, E4 and E6;
   - sender to receiver for E2 and E3;
   - forward cycles for K4.
   Each file names its own in `forward_direction`.

5. **"Their ratio" (K3, E6).**
   - Both ratios are reported: `ratio_inward_over_outward`, the registration's, and
     `ratio_backward_over_forward`.
   - For K3, forward is inward. For E6, backward is inward.

6. **E6's "difference"** is forward − backward: the outward net, which is `channel_rates`' flux in
   the registration's kernel closure. Each (voltage, availability) pair is one entry of
   `evaluations`, availabilities in declared order, then voltages.

7. **K2's records.**
   - The patch's outside node is the finite node. So F(t) = ∫ a c_node dt (inward) and
     B(t) = ∫ a c_cell dt (outward), as LAWS.md §5 writes.
   - F − B is the cell's gain, V_O (c_cell(t) − c_cell(0)), which the self-check confirms.

8. **The steady records** are flux × t, exactly 0 at t = 0.

9. **K4's ΔG_cyc/(R T).**
   - Route A computes the sum the law writes, and it comes out exactly 0. ln(0.25) and ln(4) are
     correctly rounded logarithms of reciprocals, so they cancel exactly at any precision.
   - Route B takes one logarithm of the exact product of the ratios, ln(1) = 0.
   - Neither value is forced to 0. Each is reported as computed.

10. **Names.** `cases.json` names quantities in prose, so the files use descriptive keys with
    their units: `forward_fmol_per_s`, `F_fmol`, `J_plus_fmol_cycles_per_s`, `F_fmol_cycles`,
    and so on.
    - K2 adds a, k and c̄. The steady routes add their prefactor.

11. **The difference measure.**
    - It is |A − B|/max(|A|, |B|), in exact rationals.
    - A net, 0 at these states by construction, is measured against its forward flux, and
      ΔG_cyc/RT absolutely. A relative measure means nothing at an exact or near zero.

12. **The number format.**
    - Computed values have 30 significant digits, as `d.ddd…e±N`, rounded half-even.
    - Exact zeros are written `"0"`. Times, voltages and V_ref are exact decimal strings.

13. **Temperature.** T is declared per case, as LAWS.md §1 says, and each case uses its own.

## Declared values checked for consistency

No declared value was found inconsistent. The checks were:
- every case declares the fields its kind needs;
- E4's and E6's blocks name the reversal of K;
- every record-time rule is readable;
- every steady case is at zero net in both routes.

The reference reproduces the registration's §6 figures, which informed its bounds and are not
declared values:
- K1's records are 1e-5 fmol at 100 s;
- K2's relaxation time is 50 s (k = 0.02 /s);
- K4 has J₊ = J₋ = 4.5454545455e-4 fmol of cycles per s, and ΔG_cyc/RT = 0;
- E4 has u = 1/2, and the planted fault would double each direction to 0.1828 fmol/s.
