# FR-10's independent references: R-faces, R-ion and R-records

**Registered 17 November 2026, before any engine output exists.** These are the independent
references for FR-10, the scheduled bath composition (`scheduled_bath_composition@1`; D166, D169,
D216). They implement Appendix A of `docs/BATH_SCHEDULE_DESIGN.md` on the FR lane's registered
worlds, W1 to W3, for the qualification items B1 (R-faces), B2 (R-ion) and B4 (R-records). The
FR lane's protocol calls them inside its judged snapshot; `REFERENCES_USAGE.md` is the interface.

The model is GARD's references (`validation/gard/references/`): independent code in NumPy, SciPy
and exact `fractions` and `decimal` arithmetic, registered designs in files, planted controls
with their power, and a harness that reads only saved bundles in their declared format.

## What the registering commit holds

| Path | What it is |
| --- | --- |
| `reference_inputs.json` | The FR lane's registered inputs, copied byte for byte from branch `fr10-protocol`, commit cbe4f27d ("FR-10 reference inputs: exact SI constants stated over Appendix A's rounded ones, the supply's sign, the step's charge and K's run-time input"), path `validation/bath_schedule/reference_inputs.json`, git blob 9236a0a722c96056d941feb54885824452b5f59a |
| `designs/fr10_reference_design.json` | The registered design: the claims and their tolerance basis, every planted control's deviation on the registered dt ladder (the power), the zero-power cases and the readings |
| `designs/fr10_reference_values.json` | The references' outputs on the registered inputs, with their floors |
| `faces.py`, `ion.py`, `records.py` | R-faces, R-ion and R-records |
| `controls.py`, `schemes.py` | The planted controls, and the honest and first-order stand-in steppers |
| `design.py` | Writes both design files; `python -m validation.fr10.references.design --check` regenerates and compares them |

Run everything with `/mnt/workspaces/Cells/venv-cpu/bin/python`. Generating the design takes
about 15 s of one CPU.

## Independence and disclosure

**Written without the engine.** Nothing here imports `cells` or reads `src/cells/`, the bath
schedule's tests (`tests/unit/test_bath_schedule*.py`) or fixtures
(`validation/tissue/bath_schedule_fixtures.py`), the FR owner's branch `fr10-protocol` beyond the
one inputs file the lead named, or anything the FR owner wrote under `/mnt/workspaces/Cells/`.

**Read:**
- `docs/BATH_SCHEDULE_DESIGN.md`: Appendix A, §2.2 (dG_b), §2.3 (K), §4 (the items) and §7–§8;
- `docs/FEATURE_REQUESTS.md` (FR-10 and FR-3) and decisions D150, D152, D166, D167, D169 and D216;
- GARD's references and README, the origin-of-life references' README on branch
  `ool-references`, and `validation/compartment_ph/REFERENCES_USAGE.md` (its format only);
- the inputs file and the lead's relay of it (paths only, plus its two points: use the file's
  exact constants, and keep the code here).

**Not blind.** §7–§8 of the design report measured engine outcomes: probe 1's table, the
staircase probe, milestone 2's probes and the step rule's measured points (for example "the
admissible step ratio between resolved levels is 10"). I read them before writing. They inform
nothing in the references' values. The worlds are the FR lane's, and every planted control
follows from the forms alone.

## The references

All three use the file's exact SI constants (F = N_A e = 96485.3321233100184 C/mol,
R = N_A k_B = 8.31446261815324 J/mol/K), never Appendix A's rounded RT = 2.577 pJ/fmol and
F = 96485.33 C/mol. Inputs are the exact values of the file's doubles.

**R-faces** (`faces.py`, A.2, item B1).
- **The law:** dn_i/dt = Σ κ_f (c_j − c_i) + κ_b (c_b(t) − c_i), with κ = 1e15 D A/L pL/s. In W1
  that gives κ = 10 pL/s (bath to ecs_0) and 5 pL/s (ecs_0 to ecs_1), and relaxation rates
  10 ∓ √50 s⁻¹.
- **The method:** solved exactly per epoch. The deviation from the epoch's steady state c_b
  evolves by the symmetrised eigendecomposition: c(t) = c(t_e) + W⁻¹ Q expm1(Λτ) Qᵀ W (c(t_e) − c_b),
  with W = V^½.
- **The second method:** SciPy's `expm` of the augmented generator, chained independently.
- **The truth for both** (tests): a 50-digit Sylvester form.
- **Agreement:** the primary meets it to 3.5e-18 fmol and `expm` to 4.9e-17 fmol.
- **The floor,** |primary − expm|, is at most 4.8e-17 fmol.
- **The supply** is S(t) = Σ_i (n_i(t) − n_i(0)).

**R-ion** (`ion.py`, A.3, item B2).
- **The law:** the constant-field flux J_s = 1e15 P_s A [c_i B(−u) − c_o B(u)], with
  B(x) = x/(eˣ − 1) and u = z F V_m/RT, outward positive. The capacitor gives
  C dV_m/dt = −1e-15 F Σ z_s J_s, and the amounts follow dn_s/dt = −J_s.
- **The reduction:** in W2 only K is permeant, so C (V_m − V_m(0)) = 1e-15 F (n_K − n_K(0)) is an
  exact invariant, and the primary integrates the scalar V_m equation (DOP853, rtol 3e-14, per
  epoch).
- **The second methods:** Radau on the full state, and QUADPACK's time residual
  |f(V)(T(V) − t)| of the scalar equation. The floor is the larger of the two, at most 1.9e-14 V.
- **The start:** V_m(0) = Q₀/C = −89.0156 mV, at rest at E_K of the declared bath to 1.4e-17 V.
- **The zero-current potential after the step,** in two readings:
  - (a) at the cytosol's composition at the event: −27.504978 mV;
  - (b) the epoch's own limit, with the K that charges the wall moved into the cytosol:
    −27.505100 mV.
- **At 2 s,** V_m lies 2.8e-11 V short of (b).

**R-records** (`records.py`, A.4, A.5, §2.2 and §2.3, item B4).
- **Per event:**
  - the dose, V_b (c′ − c) per species, and the step's charge F 1e-15 Σ z dn, both in exact
    rationals, so a neutral step's charge is exactly 0;
  - dG_b, in 50-digit decimals per species (§2.2), with a float64 second evaluation. Their
    relative difference is below 5e-16.
- **Registered values of dG_b:**
  - W1: −0.12409022368254732 pJ at 1 s, then its negative at 2 s;
  - W2: −189.58785772682543 pJ;
  - W3: −0.008623434642179323 pJ.
- **K(t)** comes from any supply series at the record times. The primary is the epoch sum in
  decimals; the second is the operator's B form in float64.
- **K from the reference supplies** at the last record: 0.10195363 pJ for W1 and
  −0.0037835518 pJ for W2.

## The registered design: tolerance basis and power

Every check is deterministic, so a planted control's power is its margin: its largest deviation
from the reference over the record times, divided by the tolerance. A control has power at a
tolerance when that margin is at least 10.

**Basis.** The protocol pins its tolerances from its dt study. A tolerance τ(dt) has power
against every timing control only when τ(dt) ≤ ceiling(dt), the smallest control deviation at
that dt divided by 10. It must also exceed ten times the reference's floor. The design file
lists every number below by dt.

| W1, amounts (fmol) | dt = 1 ms | 0.5 ms | 0.25 ms | 0.125 ms |
| --- | --- | --- | --- | --- |
| Honest stand-ins (ARS(2,2,2)'s implicit and explicit halves) | 2.0e-8, 8.2e-8 | 4.9e-9, 2.0e-8 | 1.2e-9, 5.1e-9 | 3.1e-10, 1.3e-9 |
| First-order engine (implicit Euler) | 1.5e-5 | 7.5e-6 | 3.8e-6 | 1.9e-6 |
| Event one step late; one step early; half a step late | 7.8e-5; 8.9e-5; 3.9e-5 | 3.9e-5; 4.5e-5; 1.9e-5 | 1.9e-5; 2.2e-5; 9.7e-6 | 9.7e-6; 1.1e-5; 4.8e-6 |
| Ceiling (half-step / 10); its margin over the honest bracket | 3.9e-6; 47 | 1.9e-6; 95 | 9.7e-7; 190 | 4.8e-7; 381 |

| W2, V_m (V) | dt = 1 ms | 0.5 ms | 0.25 ms | 0.125 ms |
| --- | --- | --- | --- | --- |
| Honest stand-ins | 1.3e-7, 4.9e-7 | 3.1e-8, 1.2e-7 | 7.8e-9, 3.0e-8 | 2.0e-9, 7.6e-9 |
| First-order engine | 1.4e-4 | 6.9e-5 | 3.4e-5 | 1.7e-5 |
| Late; early; half | 6.8e-4; 7.5e-4; 3.4e-4 | 3.4e-4; 3.7e-4; 1.7e-4 | 1.7e-4; 1.9e-4; 8.4e-5 | 8.4e-5; 9.4e-5; 4.2e-5 |
| Ceiling; its margin over the honest bracket | 3.4e-5; 69 | 1.7e-5; 139 | 8.4e-6; 277 | 4.2e-6; 555 |

- **The view absent** (null) moves W1's amounts by 8.8e-3 fmol and W2's V_m by 61.5 mV.
- **Offsets accumulated** move W1's amounts by 8.8e-3 fmol. With a single event, W2 and W3 have
  no power against it.
- **Order.** The honest stand-ins' errors fall at order 2.00 per halving, and the timing controls'
  and implicit Euler's at order 1.00. So a dt study separates them.
- **Appendix A's rounded constants** would move W2's V_m by 1.36e-5 V. A V_m tolerance has power
  against them only below 1.36e-6 V, which is feasible at dt ≤ 0.25 ms.
- **Records.** Every dG_b control (wrong sign, the content after the event, linearised, log10, a
  dropped −1, a 1 M standard state, the rounded RT) departs by at least 1.8e-4 relative where it
  has power. That is more than 1e8 times the 1e-12 criterion.
- **K.** Dropping K, flipping its sign or booking each epoch at the previous potential departs by
  at least 3.7e-3 pJ, against floors of 2e-17 pJ. Without the accumulator B (W1 only), K departs
  by 0.10 pJ.

**Zero power** (listed in the design file, with remedies for the lead):
- every bath is 1 pL, so a dose or held content booked in mM without V_b is invisible in W1 to W3;
- W1's nodes are both 1 pL (n against c);
- W2 and W3 have a single event, so accumulated offsets are invisible there;
- W2 has Σ dn = 0, so a dropped −1 and a 1 M standard state are invisible there;
- in W2 K is the only permeant species, so the view of Na and Cl at the membrane is invisible;
- φ_b = 0, so an uncancelled z F φ_b in K is invisible;
- W2's cell is at rest before its event, so K without B is invisible there.

## Readings registered with the design

- Events are right-continuous. Amounts and V_m are continuous, so a record at an event time has
  one value.
- ln(a_s/V_b) in dG_b is the log of the mM number (a 1 mM standard state).
- K needs the supply at every event time. Each event time must be a record time to 1e-12 s, or the
  call is refused; nothing is interpolated.
- K from the engine's own supply checks the reconciliation's arithmetic only. K from the reference
  supply also checks the supply.
- The zero-current potential has the two readings above, both returned.

## Sources

Numbers are used under D186 and D201. No text, figures or data are copied.
- Hille B., *Ion Channels of Excitable Membranes*, 3rd ed., Sinauer 2001: the constant-field flux
  and the zero-current potential, as the design cites it (from memory, not fetched).
- Ascher U. M., Ruuth S. J. and Spiteri R. J., *Appl. Numer. Math.* 25:151–167 (1997), §2.6: the
  ARS(2,2,2) tableau of the stand-ins (from memory).
- The SI's 2019 defining constants, as the inputs file states them.

## What follows on this branch

The tests with their planted controls, the harness skeleton and its stand-in, and the tier rows.
The engine adapter waits for the engine's declared bundle format, whose path the lead will give.
