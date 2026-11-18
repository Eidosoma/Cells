# FR-3's independent references: site occupancy

**Registered 17 November 2026, before any engine output exists** (registering commit 992ce385;
amended the same day before any engine output, as recorded below). These are the independent
references for FR-3's items Q1–Q5 (`docs/SITE_OCCUPANCY_DESIGN.md` §8.3). The worlds are
registered here too: the lead ruled that this package designs and registers FR-3's worlds, and
the FR lane builds its protocol on them, through paths (17 November 2026; D216 orders FR-3 as
"independent references, then its protocol"). `REFERENCES_USAGE.md` is the interface. The model
is FR-10's and FR-1's references and GARD's.

## What the registering commit holds

| Path | What it is |
| --- | --- |
| `reference_inputs.json` | The registered worlds, self-contained: units, exact SI constants, conventions, the ligand and its trace, the dt ladder, and 25 worlds with their nodes, populations, multipliers and record times, described physically. Written by `worlds.py` |
| `designs/fr3_reference_design.json` | The claims and their tolerance basis, the honest SSPRK(3,3) stand-in on the ladder, each planted control's deviation, the ceilings, Q4's ratios, the order in ε, the energy controls, the readings and the notes |
| `designs/fr3_reference_values.json` | `api.reference` on every world. Long arrays keep every k-th record and the last; floors keep their largest value |
| `kinetics.py` | R-ode: Radau, cross-checked by DOP853, with the heat and work as states |
| `closed.py` | R-closed (A.4) and R-qss (A.5) |
| `equilibrium.py` | R-eq |
| `energy.py` | R-dG (A.3) |
| `api.py` | The protocol's entry points |
| `schemes.py` | The SSPRK(3,3) stand-in: an honest engine for the dt study, not a reference |
| `design.py` | Writes both design files (about three minutes of one CPU, with `OPENBLAS_NUM_THREADS=1`). `--check` regenerates and compares every file |

## Independence and disclosure

**Written without the engine.** Nothing here imports `cells` or reads `src/cells/` (the operator
`site_occupancy` included), the operator's tests or fixtures, the FR owner's branches, or anything
the FR owner wrote under `/mnt/workspaces/Cells/`.

**Read:**
- the design's Appendix A, §2 (the laws), §3.3–§3.4 (energy and its guards), §4.1 and §4.3–§4.4
  (scales, the trace rule, the heat sign) and §8 (qualification);
- `docs/FEATURE_REQUESTS.md` (FR-3) and decisions D150, D152, D159, D169 and D216.

**Not blind:** §4.4 and §8.3 report the prototype's measurements:
- the heat-sign table;
- the orders 8.39 and 8.19 at ε = 0.1;
- the orders in ε, 0.98 and 0.998.

They are expectations here, not inputs, and nothing in the values derives from them. The worlds
and their rates are this package's own synthetic bracket, labelled so (D152 §2.4's rule): K_d =
1 µM, k_on = 1e3 /(mM s), k_int = 0.1 /s, 10⁵ copies. The lead's scope ruling holds: no world
combines site occupancy with a bath schedule.

## The worlds

Every world is face-free, so a population's patch is the only link between its cell and the
node it faces. There is no face and no held bath. The ligand is neutral and impermeant, and its
trace is 1e-12 mM ≤ 1e-6 K_d.

| Item | Worlds | What they hold |
| --- | --- | --- |
| Q1 | `q1_eps_1e-1`, `q1_eps_1e-2`, `q1_eps_1e-3`, `q1_eps_1e-1_alpha_half` | A cell's outward population facing a closed 1 pL node at c₀ = 1e-4 mM, with binding and internalisation and occupancy at its quasi-steady value. S is set by ε = (S/V)/(K_M + c₀) ∈ {0.1, 0.01, 0.001}, at fixed rates. In `q1_eps_1e-1` the receiving cell is 2 pL. The last world has α = ½ |
| Q1's dt study | `q1_fast` | The ε = 0.1 world with every rate 100 times faster, at the same K_d and K_M, so that an honest engine's error stands above the floor |
| Q2 | `q2_large`, `q2_closed`, `q2_two_populations` | Equilibrium in a 1e3 pL node at c = K_d; depletion in a 0.1 pL node; two cells' populations (K_d 1 and 4 µM) facing one node |
| Q3 | `q3_association`, `q3_dissociation`, `q3_internalisation`, `q3_binding_multiplier` (and `q2_closed`) | Association, dissociation into a node at the trace, and internalisation, in 1e3 pL nodes; the closed node's Riccati form; the binding multiplier at ¼ from 1 s to 4 s, which slows the approach and leaves the equilibrium unchanged |
| Q4 | `q4_alpha_{1,1_2,1_4}_{low,high}` (and `q1_eps_1e-1_alpha_half`) | α ∈ {1, ½, ¼} at c = 0.01 K_d and 100 K_d in a 1e6 pL node, where the depletion term is at most 1.6e-7 |
| Q5 | `q5_passive_from_zero`, `q5_passive_preformed`, `q5_washout`, `q5_class_switch`, `q5_inward`, `q5_background_{threshold,lowered}` (and `q1_eps_1e-1`, `q2_two_populations`, `q2_closed`) | §3.4's guard worlds (see below) |

§3.4's guard worlds cover:
- passive binding from B = 0 and from a pre-formed occupancy;
- the mixed share branch at quasi-steady uptake;
- a washout, which takes the quadrature branch;
- the class switch, internalisation off, on at 5 s and off at 10 s;
- a receiving cell (2 pL) faced by an inward population;
- two populations on one node;
- a closed relaxation;
- the background pair, with the trace at 1e-6 K_d and 1e3 below it.

## The references and their floors

| Reference | Method | Second method or truth | Floor |
| --- | --- | --- | --- |
| R-ode (A.2, A.3) | Radau, rtol 1e-12, with an analytic Jacobian. The heat is carried as H = RT [Y − Δ(R ln(R/S) + B ln(B/S))] with dY/dt = Σ J ln(c/K_d) + I ln(R/B), exact along the path and finite at B = 0 and R = 0 | DOP853 at rtol 1e-13 | B: at most 4.8e-17 fmol. n: at most 2.5e-10 fmol, at the 1e5 fmol of the 1e6 pL nodes (2.5e-15 relative) |
| The ledger | Δ(Σ G_node) + Δ(Σ G_site) + H − W from the states, in 50-digit decimals | — | at rounding: at most 1.7e-14 of the nodes' free energy where the nodes hold resolved amounts; where a node starts at the trace (`q3_dissociation`, `q5_washout`, `q5_background_*`), at most 1.5e-16 pJ absolute, against heats near 1e-3 pJ |
| R-closed (A.4) | The Riccati form and the depletion quadratic (exact for the closed node); the fixed-c forms on the reference side | R-ode | Riccati against R-ode at most 3.1e-17 fmol |
| R-eq | Bisection in 50-digit decimals of c V + Σ S c/(K_d + c) = N; the heat G(start) − G(eq) | Riccati's r₋ (one population) | exact to its digits |
| R-qss (A.5) | D150's saturable law with a = k_int S, b = K_M V | R-ode | — |

## The registered design: tolerance basis and power

The checks are deterministic, so a planted control's power is its margin, of at least 10. The
protocol pins each judged tolerance from its dt study. A tolerance has power in a world where it
lies below that world's ceiling, the smallest control's deviation over 10, and above ten times
the reference's floor.

- **Q1's order (the dt study).** The honest SSPRK(3,3) stand-in, one stage per half-step,
  on `q1_fast` errs by 2.9e-13, 3.5e-14 and 4.4e-15 fmol at 1, 0.5 and 0.25 ms. That is order
  3.04 and 3.02, above the floor of 1.9e-18. Planted lower orders fail the claim on the same
  world: SSPRK(2,2) errs by 1.8e-11 to 1.1e-12 fmol (order 2.04 and 2.02) and Euler by 3.6e-9 to
  9.1e-10 (order 1.00). In the slow worlds the honest error is already at rounding at 1 ms (about
  1e-16 fmol), so their order is not measurable: **not shown there**, and shown in `q1_fast`.
- **Rates and declarations.**
  - k_on, k_off or k_int 1% off depart by 5.4e-8 to 3.4e-7 fmol. The exception is q3_dissociation's
    k_on, at 1.3e-10, listed below.
  - The internalised cargo sent to the wrong node departs by 1.9e-5 to 2.3e-5 fmol.
  - α ignored departs by 8.9e-6 fmol.
  - The binding multiplier ignored, or applied squared, departs by 1.6e-6 fmol
    (`q3_binding_multiplier`). These are one test counted twice: each is a ×4 time rescaling of
    the same trajectory, and neither moves the equilibrium. The amendment adds the control that
    does: m_b applied to k_on alone departs by 2.6e-5 fmol.
  - The receiving cell's volume taken as 1 pL departs by 3.1e-7 fmol in `q5_inward`, where an
    inward population binds from the cytosol. In `q1_eps_1e-1` it moves the work by 3.3e-5 pJ.
  - The ceilings of the ladder worlds are 5.4e-9 to 2.0e-8 fmol. Each lies at least 10⁴ times
    above the honest stand-in's error at every rung.
- **Q1 against R-qss.** The order in ε is 0.97 and 0.997, measured on the uptake's relative error
  (7.5e-2, 8.0e-3, 8.0e-4).
- **Q4.**
  - θ(α)/θ(1) = α to 4e-8 at c = 0.01 K_d and 4e-12 at 100 K_d (the depletion term), with the
    relaxation rate equal to 1e-9 across α.
  - The kinetic factor (K) departs by 0.5 and 0.75 at both concentrations.
  - The affinity factor (A) departs by 0.49 and 0.72 at saturation, but only by 2.5e-3 and 1.9e-3
    at c ≪ K_d, as §2.3 predicts: (A) is caught at saturation.
- **Q5, energy.** The reference's ledger closes at rounding.
  - The heat never falls between records by more than 8 ulps of its largest value. That is the
    registered `min_heat_increment_pJ` against `heat_increment_allowance_pJ`. It is a property of
    the reference's heat, not a tolerance for the engine.
  - The work scaled by 1 + 10⁻⁶ departs by 3.7e-12 to 1.6e-10 pJ wherever work is booked.
  - The site free energy dropped departs by at least 4.2e-9 pJ.
  - The heat's sign departs by at least 9.8e-8 pJ.

  Each control lies far above the ledger's rounding.

**Zero power, or not shown** (also in the design file's `zero_power`, with remedies):
- Q1's third order in the slow worlds, where the honest error is at rounding: shown in `q1_fast`.
- The work control in passive worlds, which book no work.
- The receiving cell's volume on `q1_eps_1e-1`'s state, since internalisation is driven: shown on
  its work and in `q5_inward`.
- k_on in `q3_dissociation` (1.3e-10 fmol, since rebinding into a near-empty node is weak).
- (A) at c ≪ K_d, weak by design.
- The background guard on heat and work (the findings below).

## Findings for the lead

- **The background guard holds for the occupancy, not for the energy.**
  - Lowering the trace from the threshold, 1e-6 K_d, by 10³ moves B by 1.4e-6 relative and n by
    1.9e-5.
  - It moves the heat by 6.9e-5 and the work by 1.9e-4. The receiving cell starts at the trace,
    and the work's RT ln(c_r) carries the trace's logarithm (`q5_background_*`).
  - So "every compared quantity far below its tolerance" holds for heat and work only above about
    1e-3 relative.
  - The judged comparisons are unaffected, because the engine and the references share the
    trace.
- **The prototype's third order needs fast rates.** At this bracket's slow rates (about 1/s), an
  honest engine is at rounding at 1 ms. Hence `q1_fast`.

## Amendment, 17 November 2026: two controls and exact statements

After the registering commit 992ce385, before any engine output and before FR-3's protocol
started, at the advisor's review:
- **Two controls are added to the design.**
  - **m_b applied to k_on alone** (k_off unscaled), on `q3_binding_multiplier`. It moves the
    equilibrium while m_b ≠ 1 and departs by 2.6e-5 fmol. It gives power to the claim that the
    binding multiplier scales k_on and k_off together.
  - **m_i ignored** on `q5_class_switch`: internalisation running through the off epochs departs
    by 1.4e-5 fmol. That world had no control margin on record.
- **The README states two things exactly.** The ledger bound now gives an absolute bound for
  worlds whose node starts at the trace. The heat-increment allowance is described as a property
  of the reference.
- **What changed in the files:** the design file's `power.controls_fmol` gains the two entries.
  The values file, the inputs and every other registered number are unchanged.

## Tests

Both files are tier 1 on the timed lane (CPUs 4 and 5, under its lock) at 992ce385: forms
5.63 s, worlds 4.43 s. The record is
`/mnt/workspaces/Cells/fr3-references-20261117/measure-01/measured.json`.

- `tests/unit/test_fr3_references_forms.py`: the forms on their own, nine tests with planted
  controls.
- `tests/unit/test_fr3_references_worlds.py`: the registered inputs equal their generator and
  parse under the declaration's rules (a trace above 1e-6 K_d, and internalisation on an inward
  population, are refused). It also holds:
  - the closed node against its Riccati form and the registered values (a changed value caught);
  - the dropped site free energy;
  - `q1_fast`'s third order with a rate error far above it;
  - Q4's ratios with (K) and (A);
  - the registered power;
  - no engine import.

## Sources

Numbers are used under D186 and D201. No text, figures or data are copied.
- Langmuir 1918; Segel and Slemrod 1989; Borghans, de Boer and Segel 1996; Shu and Osher 1988;
  Gottlieb, Shu and Tadmor 2001; all as the design cites them, from memory.
- The SI's 2019 defining constants.
