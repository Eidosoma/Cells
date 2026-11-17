# FR-1's independent references: the closed compartment

**Registered 17 November 2026, before any engine output exists.** These are the independent
references for FR-1's acceptance items C3 to C11 (`docs/CLOSED_COMPARTMENT_DESIGN.md` §6.3),
written from Appendix A.2–A.10 on the FR lane's registered worlds. The protocol calls them inside
its judged snapshot; `REFERENCES_USAGE.md` is the interface. The model is FR-10's references and
GARD's.

## What the registering commit holds

| Path | What it is |
| --- | --- |
| `reference_inputs.json` | The FR lane's registered inputs, copied byte for byte. Source: branch `fr1-protocol`, commit f78dacb9 ("FR-1: C10's closure bounded by the size of G's terms, from the quick development runs"; the file is unchanged since cf61c252), path `validation/closed_compartment/reference_inputs.json`, git blob d4becd3fa40e5571e3118584f6e35c8d429c9b59 |
| `designs/fr1_reference_design.json` | The settled readings, the claims and their tolerance basis, each planted control's deviation (the power), the honest split stand-ins, the zero-power cases and the notes |
| `designs/fr1_reference_values.json` | The references' outputs on the registered inputs. Long arrays keep every k-th record and the last, floors their largest value; the API returns every record |
| `api.py` | The functions the protocol calls, one per block of the inputs |
| `forms.py`, `stepmap.py`, `capacitor.py`, `energy.py`, `exact.py` | The forms (the desk stage, 17 November) |
| `splits.py` | Lie and Strang stand-ins of a split engine (not references) |
| `design.py` | Writes both design files. Run it with `OPENBLAS_NUM_THREADS=1`. `--check` regenerates and compares them |

Generating the design takes about 18 s of one CPU.

## Independence and disclosure

**Written without the engine.** Nothing here imports `cells` or reads `src/cells/`, the
compartment's tests (`tests/unit/test_cell_owned_compartments*.py`) or fixtures
(`validation/tissue/compartment_fixtures.py`), the FR owner's branch `fr1-protocol` beyond the one
inputs file the lead named, or anything the FR owner wrote under `/mnt/workspaces/Cells/`.

**Read:**
- the design's Appendix A, §2, §3.1–§3.3, §5, §6, §9 and §12;
- the lead's clarification on main (4adb6fed): the splitting bias is the relative displacement
  x*/x_eq − 1;
- decisions D157, D169 and D216;
- the inputs file, and the lead's relay of it (paths only).

**Not blind:** §9 and §12 report engine outcomes. These are probe 1's arms D1 and D2, the silence
claims' passes, and S4's and P2's reported differences. They inform nothing here.

## The five readings, settled against the inputs (and four more)

| Reading | Settlement |
| --- | --- |
| 1. A.4's comparison "to rounding" | The inputs fix the plan S(h) = E(h/2) I(h) E(h/2), with S(dt/2) twice per step (convention 6). The floor is the float64 moved-form iteration's distance from the 50-digit map. The registered allowance is 4 ulps of N per stage, accumulated |
| 2. A.5's units | The inputs declare a = 2.0000000000000004e-4 fmol/s = A V_max (V_max in fmol/s/m²) and b = 5e-4 fmol = K_M V_o. Both are used as declared and checked against their parameters to 1e-14 |
| 3. A.7's standard potentials | C7 declares none, and R_energy does not ask for C7's energy, so no reaction work is computed |
| 4. A.8's face | C8 declares no face to a bath: the uptake path is the closed three-node chain |
| 5. A.9's orientation | The inputs name V_b = φ_i − φ_j and V_pm = φ_i − φ_b, as computed here |
| 6. A declared rate beside its parameters | κ is used as declared (19.999999999999996 and 1.9999999999999998, the doubles of 1e15 k_u A/V) and checked against 1e15 k_u A/V of the import's source to 1e-14. A mismatch is refused |
| 7. The splitting term | The inputs' returns line reads "x* − x_eq beside −a(a + 2b) dt²/96". The design's wording since 4adb6fed names the relative displacement, x*/x_eq − 1 = −a(a + 2b) dt²/96 (§2.3). Both are returned. The relative displacement meets the leading term (ratio 0.999995 at 1 ms, 1 − O(dt)), and the absolute one is x_eq times it |
| 8. C7's moiety | S + P, summed over the cytosol's S and the compartment's S and P. P's cytosolic row is untouched and reported as its own constant |
| 9. Energy along a trajectory | dG(t) is the change of G over the two nodes the law touches. It is evaluated per node as a stable increment from the declared start, in decimals, with RT = 1e-3 R T pJ/fmol from the exact SI R |

## The references and their floors

| Block | Reference | Second method | Largest floor |
| --- | --- | --- | --- |
| R_closed: C3 (A.2), C4 (A.3), C5 (A.5) | Exact rationals (flux); 50-digit decimals (first-order, A.3); Newton on A.5's implicit form in decimals | float64 with `expm1`; SciPy `expm`; Wright's ω | 2.9e-18 fmol |
| R_step_map: C4 at four rungs (A.4) | The map iterated in 50-digit decimals; x*; the splitting term, relative and absolute | The float64 moved-form iteration | 2.1e-17 fmol |
| R_linear: C6, C7, C8 (A.6–A.8) | 50-digit matrix exponential, with constant rows set aside | SciPy `expm` | 1.1e-17 fmol |
| R_capacitor (A.9) | Exact rational dense solve | NumPy's dense solve | 1.7e-17 V |
| R_energy (A.10), for C3–C5 and the eight C11 worlds | Stable per-node increments in decimals, along the reference trajectory | float64 of the same increments | 2.0e-17 pJ |

**Registered numbers** (all in the values file):
- C4: x_eq = 2/3. At 1 ms x* = 0.66666319446, the relative displacement is −5.2083e-6 against
  −a(a + 2b) dt²/96 = −5.2083e-6, and the absolute one is −3.4722e-6.
- The honest map's distance from A.3 falls at order 2.000 on the ladder: 3.5e-9 fmol at 1 ms,
  5.4e-11 at 0.125 ms.
- C6's cleared amount at 3 s is 9.0300e-4 fmol.
- C7's moiety is constant at 1.0001001e-3 fmol.
- A.9: a silent compartment gives V_b = 0 and V_pm = q_i/C_pm.

## The registered design: tolerance basis and power

The checks are deterministic, so a planted control's power is its margin: its deviation over
the tolerance, with at least 10 required.

- **C3, C4 (against the map) and C5, "to rounding."** The registered allowance is 8 ulps of the
  total amount per step (4 ulps of N per stage for the map).
  - C3 and C5's controls exceed it by at least 2 × 10⁷. The controls are a rate 1% off, the
    schedule one step late, half the moved amount, K_M taken as an amount, and first order in
    place of saturable.
  - At the map, a Lie splitting exceeds it by at least 9.8 × 10⁶. The swapped palindrome
    I(h/2) E(h) I(h/2) exceeds it by 2.3 × 10⁶ at 1 ms, falling to 4.6 × 10³ at 0.125 ms.
- **C4 against the closed form.** The tolerance comes from the protocol's dt study. An honest map
  lies 3.5e-9 fmol from A.3 at 1 ms, falling at order 2. The Lie map lies 1.7e-6 fmol away,
  falling at order 1. The swapped palindrome lies 2.8e-9 fmol away, which is no power here (a
  note below).
- **C6–C8 (the dt study).** The ceiling is the smallest control's deviation over 10: a rate 1% off
  gives about 2e-7 fmol. Two split stand-ins at the declared 1 ms bracket an honest engine:
  - a first-order (Lie) split errs by 2.5e-7 fmol, above the ceiling;
  - a second-order (Strang) split errs by about 6e-11 fmol.
  So a 1% rate error is caught with margin 10 at 1 ms only if the engine's split is second
  order. A dt study separates the two, since the split error falls with dt and a rate error does
  not.
- **C9.** V_b = −q_j/C_b exactly. A flipped orientation has no power in a silent compartment.
- **C10 and C11.**
  - A wrong sign departs by 2|dG|.
  - A dropped volume (ln n for ln(n/V)) departs by RT |dn_o ln(V_o/V_c)|, at least 1.1e-4 pJ.
  - Appendix A's rounded RT departs by 2.5e-8 to 1.2e-6 pJ, a margin of 1 to 60 against RK4's
    absolute 2e-8 pJ.
  - A dropped −1 and a 1 M standard state have no power: Σ dn = 0 in every world.

**Zero power** (in the design file, with remedies):
- κ on the wrong volume in C8, since ecs_e and cell_0 are both 1 pL;
- a dropped −1 or a 1 M standard state in A.10;
- V_b's orientation in a silent compartment;
- the swapped palindrome against the closed form;
- the halves plan against the single plan, which is not an error.

## Tests

`tests/unit/test_fr1_references_forms.py` holds the forms on their own (10 tests, each with a
planted error). The world tests and the tier rows follow this registration.

## Sources

Numbers are used under D186 and D201. No text, figures or data are copied.
- Strang G., *SIAM J Numer Anal* 5:506 (1968): the splitting whose bias §2.3 computes.
- Corless R. M. et al., *Adv. Comput. Math.* 5:329 (1996), and SciPy's `wrightomega`: the Lambert W
  and Wright ω functions of A.5's second method (from memory).
- The SI's 2019 defining constants, as the inputs state them.
