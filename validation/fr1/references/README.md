# FR-1's independent references: the closed compartment (desk forms)

**Desk forms, 17 November 2026. Not yet registered.** These are the reference forms of
`docs/CLOSED_COMPARTMENT_DESIGN.md` Appendix A.2–A.10 for FR-1's acceptance items C3 to C11 (§6.3).
The registered design follows the FR lane's inputs file, and comes before any engine output. It
will hold the worlds, the record times, each claim's tolerance basis, the planted controls with
their margins, and the values. Until then nothing here is a registered claim.

The model is FR-10's references (`validation/fr10/references/` on branch `fr10-references`) and
GARD's.

## Independence and disclosure

**Written without the engine.** Nothing here imports `cells` or reads `src/cells/`, the
compartment's tests (`tests/unit/test_cell_owned_compartments*.py`) or fixtures
(`validation/tissue/compartment_fixtures.py`), the FR owner's branch `fr1-protocol`, or anything
the FR owner wrote under `/mnt/workspaces/Cells/`.

**Read:** the design's Appendix A, §2 (the transfer law), §3.1–§3.3 (the capacitor network and
silence), §5 (accounting), §6 (qualification), §9 (probes) and §12 (milestone 1 as built).

**Not blind:** §9 and §12 report engine outcomes. These are probe 1's arms D1 and D2, the silence
claims' passes, and S4's and P2's reported differences. They inform nothing here.

## The forms

| Module | Form | Primary | Second method (the floor) |
| --- | --- | --- | --- |
| `forms.loading_flux` | A.2 flux law; times where n_c would not stay positive are flagged | exact rationals | — (exact) |
| `forms.loading_first_order` | A.2 first-order law | 50-digit decimals | float64 with `expm1` |
| `forms.two_way` | A.3 two-way first-order exchange, x_eq = b/(a + b), b = 1e15 k_u A/V_o | decimals | SciPy `expm` |
| `stepmap.iterate`, `stepmap.fixed_point` | A.4: E(h/2) I(h) E(h/2), twice per dt, in either stage plan; x* = α(1 − β)/(1 − α²β); the bias against −a(a + 2b) dt²/96 | decimals | float64 in the moved-amount form, within 4 ulps of N per stage |
| `forms.saturable_release` | A.5: b ln(n_o/n_o′) + (n_o − n_o′) = a t, a = A V_max, b = K_M V_o | Newton in decimals | Wright's ω (SciPy) |
| `forms.degradation` | A.6, with the cleared amount | 50-digit matrix exponential | SciPy `expm` |
| `forms.reaction_inside` | A.7, with the moiety n_c + n_S + n_P | the same | the same |
| `forms.uptake` | A.8, optionally with a face to the bath and its supply | the same | the same |
| `capacitor.solve`, `capacitor.cell_compartment` | A.9's dense capacitor network, V_b = −q_j/C_b and V_pm = (q_i + q_j)/C_pm | exact rationals | NumPy's dense solve |
| `energy` | A.10: G = 1e-3 RT Σ n (ln(n/V) − 1), each law's work per node, and the closure dG = Σ W_ops + W_bath − H_faces | decimals | — |

Constants are the exact SI values (F = N_A e, R = N_A k_B). Appendix A's printed RT and F are
rounded and are never used.

**Tests:** `tests/unit/test_fr1_references_forms.py`, 10 tests. Each form is checked against an
independent integration or identity, with a planted error that must fail:
- a rate 1% off;
- κ on the wrong volume;
- K_M taken as an amount;
- a Lie splitting where the palindrome belongs;
- a flipped patch orientation;
- a dropped "−1".

## Readings to settle with the inputs

1. **A.4's comparison "to rounding"** needs an allowance. This package proposes 4 ulps of N per
   stage, accumulated. It does not depend on the engine's operation order.
2. **A.5's units:** a = A V_max in fmol/s, so V_max is in fmol/s/m², and b = K_M V_o in fmol.
3. **A.7's reaction work:** A.10's G carries no standard potential. The reaction's work adds
   1e-3 (μ°_P − μ°_S) × extent when the inputs declare standard potentials (D152's owned term).
4. **A.8's face** to the bath is optional: (κ_f, V_e, c_b). With it, the bath's supply is returned,
   positive out of the bath.
5. **A.9's orientation:** a patch's voltage is its first node less its second. So
   V_b = φ_cytosol − φ_compartment, @3's inside minus outside.
