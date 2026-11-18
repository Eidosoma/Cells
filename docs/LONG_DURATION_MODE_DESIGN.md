# A qualified long-duration mode for the composite (FR-8, design)

*Status: proposed, 18 November 2026, for the lead and the user (D216). Docs only. Nothing is built,
nothing was run, and nothing is scaffolded before the user has discussed the options. Code was read
at main 5133a850 and is cited `file`:line by today's path under `src/cells/`; D188's move 2 has not
landed. Tags: **(code)** read in the code; **S** this note's own reading, derivation or arithmetic
(the script and its output are in §10). Other statements cite their source.*

**Engine models it runs** (AGENTS.md): none. A mode would run `resolved_pump_composite@1` over
`resolved_pump_tissue@3` with the operators its acceptance world declares (§5.1): the
coupling operator, D150's turnover and, for the outside-envelope case, @3's excitable channel laws.

**What is asked.**
- **FR-8, from the requesting study** (D164). "Keep the quasi-steady electrical mode, or any
  qualified multirate method, on the path. When it is qualified, include an intervention applied
  during the slow phase in its acceptance case."
- **CURRENT_PLAN's compute-limits gate.** "A verdict on long-time methods": multirate or
  quasi-steady methods qualified, or bounded, on histories and intervention responses. Projective
  failed its qualification. The coarse modes cover @1–@3 only.
- **ARCHITECTURE's "State roles and time"** lists FR-8's eventual acceptance: an intervention during
  a slow interval; histories and integer state preserved; crossing-time accuracy; restart across
  the intervention; convergence under different admissible macro-steps.
- **The standing user rule (D135).** Coarse time modes are "all optional and configurable". The
  qualified fine engine stays the default and is unchanged when a mode is off. Each mode has a
  neutral ID, a declared validity domain, automatic fallback to fine stepping and its own
  pre-registered qualification against the fine mode.
- **What has not arrived.**
  - D167 placed this note after the GH200 numbers. GH200 throughput is still unmeasured (PROGRESS),
    so every cost here is a CPU or L4 number.
  - The requester's benchmark specification (FR-8's lead mapping: "its composition, its accuracy
    needs and its interventions") has not arrived either.

**Basis.**
- [BIOELECTRIC_NUMERICS.md](BIOELECTRIC_NUMERICS.md): NUM-002's time-scale separation.
- [MULTISCALE_EXECUTION_ARCHITECTURE.md](MULTISCALE_EXECUTION_ARCHITECTURE.md), "Time scales and
  long-horizon modes" and "Coupled numerical execution".
- [CHECKPOINT_CONTINUITY_DESIGN.md](CHECKPOINT_CONTINUITY_DESIGN.md) §1, §2.2 and §3.
- [PUMP_COMPOSITE_V2_DESIGN.md](PUMP_COMPOSITE_V2_DESIGN.md) §3 (the measured step costs).
- [EXCITABLE_TISSUE_DESIGN.md](EXCITABLE_TISSUE_DESIGN.md) §4.4–§4.5 (the energy rule; two clocks).
- ARCHITECTURE.md, "Levels of detail".
- PROGRESS: projective's qual-01, the L4 throughput and E07's costs.
- FR-7's and FR-2's notes, [ABUNDANCE_TO_FUNCTION_DESIGN.md](ABUNDANCE_TO_FUNCTION_DESIGN.md) and
  [MEMBRANE_RETRIEVAL_DESIGN.md](MEMBRANE_RETRIEVAL_DESIGN.md), whose slow physics are this mode's
  consumers.

## 0. Summary

1. **Duration is set by @3's fine-step count** (§1).
   - At 1 ms one simulated hour is 3.6 million steps. On one core a step costs 1.72, 7.68 and
     75.7 ms at 14, 254 and 825 field nodes (PUMP_COMPOSITE_V2_DESIGN §3).
   - So 72 h is about 5.2, 23 and 227 days (**S**).
   - **An option helps only if it cuts that count.** Coarsening the operators alone leaves 3.6
     million steps per hour.
   - **The fine step depends on the world.** It is 1 ms in the qualified tissue, while E07-v1 ran
     at 1–5 ms, and a 5 ms full-tissue step passed with the trapezoid junction booking (§1.2). A
     method's gain is over its world's own admissible step.
2. **What sets the 1 ms step** (§1.2). The explicit charge relaxation of membranes and junctions,
   and fast gates: "these set the 1 ms step" (MULTISCALE_EXECUTION_ARCHITECTURE). The IMEX step
   already makes face electromigration implicit, while "membranes, junctions, pumps, gates and face
   diffusion stay explicit" (`numerics/surface_imex.py`:17–18 **(code)**).
3. **Six options, in two classes** (§3):
   - **numerical methods**, each a solver ID (D147), with one representation and refinement as
     their test: N1 multirate operators, N2 linearly implicit membranes and junctions, N3 fully
     implicit stiff steps, and C, projective, re-qualified;
   - **declared reductions** (D175: envelope first, one case outside it failing): R1 quasi-steady
     electrical elimination (D135's B), and R2 the stationary analysis (E) extended to the
     composite.
4. **Every option needs four things from the composite** (§4):
   - a declared, fail-closed time contract per operator, under which the dt·L and dt·(k_on + k_off)
     rules and the step-counting records bind on the macro-step;
   - compulsory event boundaries with fine windows after interventions;
   - an energy booking that holds at large steps (FR-18);
   - the mode in the definition from the start (a mid-run switch is checkpoint case 3).
5. **The recommendation (S, §7): measure first, then build N2 with N1 as the first mode.**
   - N2 cuts @3's step count while keeping one representation, and it extends the IMEX operator
     that already treats face drift implicitly.
   - **N2 lifts only the stability bound.** The energy check binds first (FR-18), so N2's gain also
     needs an energy booking that is exact at its step: seam D's branch X, 2–3 agent-days
     (CORE_SEAMS §13). Stage 0 measures where the check binds (M5).
   - R1 follows only if the measurements show that N2's remaining explicit bounds hold the step
     below what the slow questions need.
   - E extends to the composite as the slow manifold's reference. C stays paused.
6. **The acceptance case** (§5): an intervention during the slow phase, plus ARCHITECTURE's list,
   plus a near-fold excitable case that must fall back. The fine references are sized for the
   30-minute rule: about 1.7 CPU-h per simulated hour of the seven-cell sheet (**S**).
7. **Questions for the user** (§9):
   - whose error tolerances apply: the parity caps projective failed, the requester's, or a budget
     declared per question;
   - which slow question is the first consumer;
   - whether a reduction (R1) is acceptable where a method suffices.
8. **Effort (S, rough):** stage 0's measurements about 1–2 agent-days plus CPU hours. N1 with N2,
   branch X's exact booking and their qualification about 17–27 agent-days. R1 would add about
   10–18, plus D175's fields (§8).

## 1. The cost model: where the time goes

### 1.1 Sourced costs

| Quantity | Value | Source |
| --- | --- | --- |
| Steps per simulated hour at 1 ms | 3.6 × 10⁶ | Arithmetic |
| One core, empty composition, per step | 1.72 ms (14 field nodes), 7.68 ms (254), 75.7 ms (825) | PUMP_COMPOSITE_V2_DESIGN §3, the field-input cost table |
| The same with a field-input provider | 1.70 ms, 9.24 ms (+20%), 111.9 ms (+48%) | The same table |
| 825 nodes under D190's BLAS pin | 91 ms one-core step, of which 21 ms is the threaded factorization that multi-core runs lose | D190 |
| L4, per world-step, the 825-node tissue | 12.5 ms at 1 world; 2.64 at 64, 2.34 at 128, 2.28 at 256 (execute only); 4.0–4.5 ms end to end with host observers | PROGRESS, the device checks for @3 (10 November) |
| E07-v1 tier 1 | 1,786 world-hours: about 4,100 L4 GPU-hours execute-only, about 7,200 end to end | PROGRESS |
| Projective (C), qual-01 | 2.2–3.5× fewer fine steps, 1.4–3.3× wall time | PROGRESS |
| The requester's 72 h arithmetic | About 5.1, 23 and 228 days at 14, 254 and 825 nodes | FR-8's entry |
| The two-clock assay | A 5 µs step; 100 ms of assay is 20,000 steps, about 20 s of slow-world time at 1 ms | EXCITABLE_TISSUE_DESIGN §4.5 |

**What follows (S):**
- One simulated hour of the seven-cell sheet is about 1.7 CPU-h at 1 ms, and 3.4 at 0.5 ms. At 254
  nodes it is about 7.7 CPU-h, and at 825 about 76.
- A step-count cut of 10× would bring 72 h of the seven-cell sheet to about 12 h, and 100× to about
  1.2 h, at the same cost per step. These are illustrations, not measurements.
- For one 825-node world the L4's 12.5 ms per step is about 6× one core's 75.7 ms, while 256 worlds
  amortise to 2.28 ms each. The L4 buys ensembles more than one fast trajectory, as FR-8's entry
  says.

### 1.2 What sets the 1 ms step

| Process | Time scale | Basis (MULTISCALE_EXECUTION_ARCHITECTURE's table unless named) |
| --- | --- | --- |
| Fast gates (NaV1.2 activation) and membrane charging | Below 1 ms to a few ms; "these set the 1 ms step" | Model laws; 1 ms is qualified and 2 ms is not |
| Junction voltage gating | 0.05–0.4 s | `junction_voltage_relaxation@1` |
| Default-world cell, slowest modes | 0.26 s, 189 s, 16,661 s | Qualified stationary analysis |
| Ion loading of a newly depolarised cell | τ 40–50 min (asymptotic 1.5–2.6 h) | Development runs (pre-screen 9) |
| Gap-junction formation after replacement | Lag about 2–20 min, then τ 15–60 min | The cell-replacement note's ranges |
| NUM-002's single cell | A fast relaxation near 0.063 s and a slow local mode near 3706 s, a separation of about 5.9 × 10⁴ (**S**) | BIOELECTRIC_NUMERICS.md |

- **The bound.** @3's definition-time bound (`surface_pump.explicit_rate_bound`, :437–449 **(code)**)
  sums:
  - face diffusion;
  - junction and membrane charge relaxation against each cell's capacitance;
  - neutral species' material relaxation;
  - a face-free node's charge relaxation.

  A step is refused where dt × rate exceeds `EXPLICIT_STEP_BOUND` = 1 (:93 **(code)**).
- **The face precedent.** Face electromigration was made implicit because "charge relaxes through
  face conductance against the patch capacitors within 10–100 ns" (`surface_imex.py`:3–6 **(code)**).
  Membranes and junctions relax against the same capacitors in milliseconds.
- **The energy check binds before the stability bound.** @3's check (2 × 10⁻³ under ARS(2,2,2))
  refused junction worlds at dt × rate of 0.08–0.31, with a second-order error (FR-18). "It is what
  refuses coarse steps" (EXCITABLE_TISSUE_DESIGN §4.4).
- **So the admissible fine step is the world's, not one number:**
  - 1 ms is qualified on the 825-node tissue, and 2 ms is not (MULTISCALE_EXECUTION_ARCHITECTURE,
    "Coupled numerical execution");
  - E07-v1's slow worlds ran at 1–5 ms (EXCITABLE_TISSUE_DESIGN §4.5's table);
  - with the opt-in `trapezoid_nonnegative@1` junction booking, "the 5 ms collapse and the
    full-tissue cue step are accepted, with energy residuals of about 1e-7 of flows" (PROGRESS, gap
    A, 11 November);
  - R-fuel's world, with no charged row, has an example ladder of 8, 4, 2 and 1 ms (FR-4/FR-5 note
    §17.5, D5), and FR-4's implicit patch targets dt up to 10 ms (§7.3 there).
- **This note's 3.6 million steps per hour is the 1 ms case.** A world that already runs at 5 ms
  needs a fifth of that, and every gain below is relative to the world's own step (**S**).

### 1.3 The model

For a run of length T (**S**):

    cost ≈ N_fine c_step + N_macro c_macro + N_handoff c_window,

with N_fine = T_fine/dt, the fine windows after interventions counted in c_window.
- **The fine engine:** N_fine = T/dt and nothing else.
- **A method that coarsens only the operators** keeps N_fine. It saves at most the operators' share
  of c_step. The measured shares are 3% for one species row on a small world (D150's note §4.4),
  13–40% for membrane state and insertion at 64 nodes (PUMP_COMPOSITE_V2_DESIGN §3), and about
  1.5 ms of 6–7 ms for replacement@2 on the 127-cell sheet (its B.13). Removing the operators'
  whole cost would give at most about 1.03–1.4× (**S**).
- **A method that cuts N_fine** gains the ratio dt_macro/dt, less c_macro's excess over c_step.

## 2. What exists

| Mode | ID | Reach | Status |
| --- | --- | --- | --- |
| E: stationary states and continuation | `stationary_continuation_analysis@1` | `resolved_pump_tissue@1`–`@3` and `resolved_pump_water@1`–`@2` (`analysis/stationary.py`:99–105 **(code)**) | Qualified. It refuses the composite (D150's note §8, §11.1) |
| C: projective integration | `projective_forward_euler@1` | `resolved_pump_tissue@1`–`@3` (`definitions/projective_spec.py`:38–43 **(code)**) | Failed qual-01 on the absolute caps |
| Two clocks | — | Track E's slow world plus assays from frozen snapshots | A pattern under D153's rule (b), "not a long-time method for one coupled trajectory" (FR-8's lead mapping) |

**E's fast mode is an algebraic closure** (`analysis/stationary.py`:21–30 **(code)**): "the
electrical state at frozen ion composition", with charge offsets and gates as unknowns. It is the
singular-perturbation fast subsystem. R1 could reuse it, with three changes:
- composite admission;
- per-species tolerance scaling: "It stops on one absolute correction of 1e-10 mM per amount" (D150
  §8; `NEWTON_TOLERANCE`, :123 **(code)**), which is 10% of a 10⁻⁹ mM trace;
- a device Newton with a fixed iteration count, since the analysis is host-side.

**Projective's lesson** (PROGRESS, qual-01). It failed "only on the absolute caps" (|dVm| ≤ 20 µV,
|dc|/c ≤ 2 × 10⁻⁴).
- "The per-jump tolerance of 1 µM, summed over 100–170 jumps, admits about 0.16 mM, while the cap
  admits about 1.2 µM at 6 mM Na. The error estimator was accurate, but the tolerance it was held to
  was looser than the caps."
- **So any mode budgets its cumulative error against the caps it is judged by, not a per-step
  tolerance.** Its machinery is reusable: bursts, verified windows, the settling thresholds and the
  tolerance-normalised coordinates (`models/surface_pump_projective.py` **(code)**).
- Continuity refuses projective definitions (CHECKPOINT_CONTINUITY_DESIGN §2.2).

## 3. The options

| Option | Class | Cuts @3's fine steps? | Gain (S, unmeasured) | Interventions | Main cost or risk |
| --- | --- | --- | --- | --- | --- |
| **N1. Multirate operators:** slow operators take a macro-step H, @3 subcycles at dt | Method | **No** | ≤ about 1.03–1.4× (§1.3) | Compulsory boundaries | A component only |
| **N2. Linearly implicit membranes and junctions:** their slope conductances join the IMEX operator (C + a dt L) | Method: a new IMEX ID | **Yes** | dt set by what stays explicit (face diffusion, pumps, kinds, operators) and by the energy check: perhaps 10–100× over a 1 ms world, less over a 5 ms one | Boundaries, then a declared fine window | Same matrix size and one factorization per step, as today; **an energy booking exact at its step** (§4.3; branch X) |
| **N3. Fully implicit stiff steps** (an L-stable SDIRK or BDF on the whole state) | Method | **Yes** | Steps set by accuracy on the slow manifold | Step control | A Newton on every unknown: about 6–8 × 10³ at 825 nodes with 2,580 channel populations (**S**; PROGRESS's tissue). It needs sparse or Krylov solvers (FR-17, the field-solver interface) |
| **R1. Quasi-steady electrical elimination** (D135's B): Vm, the field and fast gates algebraic; the slow state at H | Reduction (D175) | **Yes** | Up to 10³–10⁴× in steps, less a Newton per macro-step | Handoff to fine windows, then re-entry | D175's fields (refused at registration today); E's fast mode made composite, scaled and device-side; non-electrical stiffness stays |
| **R2. E for the composite:** fixed points and continuation | Reduction: no trajectory | — | The end state only | A sequence of steady states | No histories and no crossing times: it fails ARCHITECTURE's list as a mode |
| **C, re-qualified** with cumulative error control | Method | Yes, partly | Below qual-01's 1.4–3.3× once budgeted (**S**) | Never jumps across an event (`execution/projective.py`:9–13 **(code)**) | The requester does not ask for it |

### 3.1 N1: multirate operators

- **What it is.** In `Composition.split_step` the operators' half-steps wrap one @3 step. N1 lets
  operators whose time contract admits it (§4.1) take H/2 halves around m fine @3 steps.
- **For:** D150's laws are "exact over any step", and "the species never sets dt; the ions do" (D150
  §8).
- **Against:** it keeps N_fine. It is worth building only as a part of N2 or R1, where the macro-step
  is the step.

### 3.2 N2: linearly implicit membranes and junctions

- **What it is (S).** Today's IMEX stage solves (C + a dt L) φ = q, with L the face-conductance
  Laplacian of frozen weights. N2 adds to L:
  - each membrane's slope conductance, a cell–outside coupling;
  - each junction's slope conductance, a cell–cell coupling;
  both evaluated at the tableau's operator time, as the face weights are (`surface_imex.py`:18–22
  **(code)**).
- **The matrix stays SPD** (a Laplacian plus C, **S**), the same size, and one factorization serves a
  step. The species move in flux form with the same conductances, so material and charge stay exact
  by construction, as for faces.
- **What remains explicit and sets the step:**
  - face diffusion;
  - the pumps' electrogenic currents, and the kinds' B7 terms and routes;
  - gates, which are already exponential (Rush–Larsen; EXCITABLE_TISSUE §2.1);
  - the operators' own conditions.

  Measurement M1 (§6) gives that bound per world.
- **Accuracy.** In a slow phase the fast charge modes sit at their quasi-steady values, and an
  L-stable, stiffly accurate tableau tracks them. ARS(2,2,2)'s implicit part is L-stable
  (`surface_imex.py`:51 **(code)**).
  - Spikes are not slow. An excitable world at a coarse dt must be refused at run time, or run at
    1 ms there.
- **Precedents in the repository.** Faces, and FR-4's per-compartment implicit block
  (COMPARTMENT_PH_TRANSFER_DESIGN §7.3, whose qualification targets dt up to 10 ms).
- **It is a method, not a reduction:** one representation, so D175's envelope machinery does not
  apply. It is a new IMEX ID under D147, and refinement is its test.

### 3.3 N3: fully implicit stiff steps

- An implicit stage on every unknown makes the step depend on accuracy alone, including after
  interventions with step control.
- At the qualified sizes the dense Newton is too large (**S**: a dense LU is cubic in thousands of
  unknowns). It waits for the field-solver interface's sparse or matrix-free solves (CURRENT_PLAN's
  compute-limits gate; FR-17).
- A small-world reference variant is useful now: the independent references already use SciPy's
  Radau and BDF (BIOELECTRIC_NUMERICS).

### 3.4 R1: quasi-steady electrical elimination (D135's B)

- **What it is.** Tikhonov's fast–slow split (singular perturbation theory, cited from memory):
  - at each macro-step the fast subsystem (charges, Vm, the field, fast gates) is solved at the
    frozen slow state;
  - the slow state (amounts, slow gates, operator states) advances with the quasi-steady currents.
- **Its error** is O(ε) with ε the ratio of fast to slow time scales. It is about 1/(5.9 × 10⁴) for
  NUM-002's cell (**S**), and larger in tissues with junction gating at 0.05–0.4 s, unless those
  gates are slow variables.
- **It is a reduction,** so ARCHITECTURE's "Levels of detail" binds:
  - the envelope and error budget declared before any comparison;
  - one case outside them that must fail;
  - the fine engine as the reference;
  - and its four fields, which "registration refuses" today (the core lane's item 4).
- **Its envelope:** a fast subsystem with one stable equilibrium (no excitation, no oscillation),
  checked at each macro-step from the closure's Jacobian. Outside it, the run falls back to fine
  stepping (D135's rule).
- **What stays stiff:** non-electrical terms such as face diffusion and D152's dt·L. So R1's
  macro-step is bounded by the same non-electrical terms as N2's, unless its slow step is implicit
  (**S**). This is why §7 orders N2 first.

### 3.5 R2: the stationary analysis for the composite (E)

- **Its use:** "where does this world end up after the intervention, and is that stable?", with no
  trajectory.
- **It needs** the operators' rates in the composite's coupled right-hand side, and per-species
  Newton scaling (D150 §8).
- **It cannot be FR-8's mode:** it preserves no histories and no crossing times. It is the slow
  manifold's end-point reference for N2 and R1.

### 3.6 C, projective, re-qualified

- **Budgeting its error against the caps** (§2) means a per-jump tolerance near cap/N_jumps. That
  shrinks the jumps and the gain (**S**).
- **The requester does not ask for it,** and MULTISCALE_EXECUTION_ARCHITECTURE records pausing it as
  the lead's recommendation.
- **Its burst-and-verify machinery** serves N2's and R1's fine windows.

### 3.7 Not methods

- **Two clocks** stay within their scope (ARCHITECTURE).
- **GPU ensembles** raise throughput, not one trajectory's speed.
- **GH200** lowers c_step, not N_fine.

## 4. What every option needs from the composite

### 4.1 A declared time contract per operator, fail-closed

Each operator declares how it behaves under a macro-step H (**S**). An undeclared operator is refused
in the mode.

| Class | Operators (today's) | Under H |
| --- | --- | --- |
| Exact at any step | D150's turnover and first-order exchange; the coupling's state half-step; replacement's formation law (`laws/junctions/junction_formation.py`, exact `advance`) | Admitted at H |
| Conditioned | D152's reactions (dt·L ≤ 1); the coupling (dt·(k_on + k_off) ≤ 1); exchange's saturable solve (its residual) | **The condition binds on H.** Refused, or subcycled at the operator's own sub-step, which is N1 |
| Events | Replacement, the partition, insertion's onsets, regulatory writes, FR-10's doses | Compulsory boundaries (§4.2) |
| Inside @3's stages | Kinds, including FR-4's per-compartment implicit block | @3's solver ID decides (N2 or R1) |
| Counting records | The coupling's crossing record "counts numerical steps today" (ARCHITECTURE, "State roles and time") | **Refused until it declares physical time:** a step count does not survive a change of step |

- **The contract** adds one static declaration to `contract.py`. The composite checks it when the
  model is built. The fine engine's programs are unchanged, since the declaration is host-side.

### 4.2 Interventions: compulsory boundaries and fine windows

- **No macro-step crosses an event.** Doses, writes, switches, replacements and divisions are
  boundaries, as projective's jumps are today. ARCHITECTURE asks the same of plans: they "carry ...
  the next compulsory event boundary, so a future coarse step respects doses, regulatory writes and
  timed events".
- **After an intervention, a fine window.**
  - It runs at the fine dt until declared settling thresholds hold: projective's |dVm/dt| and gate
    distances, budgeted as §2 requires.
  - Then the macro-steps resume. The window's length is measurement M4's.
- **Crossing times** are located within the macro-step that contains them, or the step is shortened
  to the crossing. That is the coupling note's §2.5 question 2, which a macro-step makes sharper.

### 4.3 The energy check at large steps

- **@3's relative energy check binds at moderate steps** (FR-18). So a coarse mode books its heat
  exactly at the macro-step, or it is refused at once.
- **The booking options are seam D's** (CORE_SEAMS §6): the trapezoid, written once, and branch X's
  exact booking for charged rows, not built after P1's weak no.
- **A coarse IMEX re-opens branch X's question at its own step sizes (S).** Its residual is second
  order in dt with a world-dependent coefficient (FR-18), so a 10–100× larger step raises it by
  10²–10⁴ under the tableau's booking. N2's gain therefore assumes the exact booking: 2–3 agent-days
  in CORE_SEAMS §13's table, the @3 owner's.
- **The check is not loosened for a mode** (FR-18: "It is not loosened for one experiment").

### 4.4 Checkpoints

- **The mode lives in the definition's execution block from the start,** absent by default, as
  `execution.projective` does (`definitions/projective_spec.py`:1–7 **(code)**).
- **A switch between fine and coarse in mid-run is a definition change:** checkpoint continuity's
  case 3, refused (CHECKPOINT_CONTINUITY_DESIGN §1).
- **Two-clock style switches** are new runs that import a state under D153's rule (b), claiming no
  continuity.
- **Within one run,** fine windows and macro-steps are the mode's own. Its checkpoints restart it
  exactly under the same definition (ARCHITECTURE's "restart across the intervention").
- **D195 holds:** no checkpoint crosses move 2.

### 4.5 GPU-native execution

- **No per-step host work** (D191's "fast" criterion).
- **Device Newtons with fixed iteration counts** (seam C's rule for its closure, CORE_SEAMS §5.1).
- **Fine windows as compiled window rollouts,** as projective's bursts are (`execution/projective.py`:4–7
  **(code)**).

## 5. The qualification plan

### 5.1 The acceptance case

**The world (S).** The seven-cell heredity sheet (14 field nodes), with:
- a neutral regulator under D150's turnover;
- the coupling operator's channel target (qualified for gate-free populations, A5);
- one regulatory state;
- a slow phase of 1–2 h, with **an intervention at its middle (D164)**: a step in the regulator's
  production and a regulatory write at one exact grid time.

FR-7's U2 loop becomes the second world when it exists.

| Item | Check |
| --- | --- |
| L1. The slow trajectory | Vm, amounts, gates and operator states against the fine reference, at every record, within the declared budget (§5.4) |
| L2. The intervention's response (D164) | The response after the intervention, against the fine reference |
| L3. Crossing time | The time to a declared threshold after the intervention, within its declared tolerance |
| L4. Histories and integer state | Accumulated transfers, heat and work, counters, latches and records against the fine run's |
| L5. Restart across the intervention | Bitwise, under the same definition |
| L6. Convergence | H, H/2 and H/4 with an observed order inside its registered window |
| L7. Conservation and energy | Every ledger within its bound at every row |
| L8. Outside the envelope | The near-fold excitable case must fall back or be refused, never run coarse. One candidate is NaV1.2's D state: it survives 1800 s at scale 0.72 and switches within 3 s at 0.71 (PROGRESS, projective's F2 pre-scan) |
| L9. Off means unchanged | The mode absent: every program unchanged (crossrev) |
| L10. Cost | Validated world-hours per allocated CPU- or GPU-hour, and elapsed time to the trajectory (CURRENT_PLAN's two numbers) |

### 5.2 The fine references and the 30-minute rule

- **The references are the fine engine itself,** run once from a clean snapshot, detached, and
  frozen. They are inputs to the check, so the check reaches its code in minutes (AGENTS.md's
  30-minute rule).
- **Their cost (S, from §1.1):**
  - about 1.7 CPU-h per simulated hour of the seven-cell sheet at 1 ms, and 3.4 at 0.5 ms;
  - a 2 h slow phase with one refinement is about 10 CPU-h per arm;
  - several arms (L1, L6, L8) come to some tens of CPU-h, on lane CPUs.
- **A development harness first:** NUM-002's single cell, or a two-cell pair, where a fine hour takes
  minutes. Its cost is to be measured (M3), not assumed.
- **An independent reference** for the harness: SciPy's Radau and BDF, as BIOELECTRIC_NUMERICS's
  panel uses, by an agent that has read neither the engine nor the mode.

### 5.3 Planted controls

- A macro-step allowed across the intervention must fail L2 and L3.
- A fine window shortened below its settling thresholds must fail L2.
- A counting record left in step units must fail L4.
- A conditioned operator run at H past its condition must be refused at the definition.
- For R1 only: a fast subsystem outside its envelope admitted without fallback must fail L8.

### 5.4 Error budgets

- **Declared before any comparison runs** (ARCHITECTURE's rule for reductions, applied to methods
  too).
- **Cumulative over the run,** never per step (§2's lesson).
- **Whose tolerances** is the user's question (§9): the parity caps (|dVm| ≤ 20 µV,
  |dc|/c ≤ 2 × 10⁻⁴), the requester's specification when it arrives, or a budget per question.

## 6. Measurements to propose before building (not run)

| ID | What | Where | Cost (S) |
| --- | --- | --- | --- |
| M1 | @3's explicit bound per world, term by term: today's dt × rate for each term, and the step N2 would admit with the membrane and junction terms removed | Host-side, on the definitions of the seven-cell sheet, the 127-cell sheet and the 825-node tissue | Minutes |
| M2 | The slow spectrum from E's dense eigenvalues: the step R1's slow integrator would face | Default world and seven-cell sheet | Minutes to an hour |
| M3 | A fine hour of the harness world, and the operators' share of c_step in one composed world | One CPU, detached | Under an hour |
| M4 | Settling after interventions: the time for \|dVm/dt\| and gate distances to fall below thresholds after a channel step, a dose step and a regulatory write | The seven-cell sheet, short fine runs | About an hour of CPU |
| M5 | Where the energy check binds: the energy residual against dt (1, 2, 5, 10 ms) in the acceptance world, with the trapezoid junction booking on and off | The seven-cell sheet, short runs at each dt | About an hour of CPU |

Each criterion is written before its run. Runs go through `scripts/run_detached.sh` on lane CPUs.

## 7. Recommendation (S)

**Stage 0 first:** M1–M5, then a dated decision.

**Then N2 with N1, as the first long-duration mode:**
- **It cuts @3's fine-step count,** the only lever that matters (§1.3), at today's cost per step.
- **It needs branch X's exact booking with it.** N2 lifts the stability bound, while the energy
  check binds first (§1.2, §4.3). If M5 shows the check binding near today's step, N2 without the
  exact booking gains little.
- **It keeps one representation:** no envelope, no handoff semantics and no D175 fields, which are
  not executable yet.
- **It extends the operator that already treats face drift implicitly.** Its qualification is
  refinement against the fine engine.
- **N1's per-operator contract** comes with it, since the macro-step is then the step.

**R1, only if M1 shows** that N2's remaining explicit terms hold the step below what the first slow
question needs, and after D175's fields exist. R1 then shares N2's contract, boundaries and fine
windows.

**R2 (E for the composite)** as the slow manifold's end-point reference. **C stays paused.**

**Optional and configurable, always:** each mode is an opt-in execution block with a neutral ID,
fine stepping by default, automatic fallback at its boundaries, and its own registered
qualification (D135).

## 8. Ownership, order and effort

| Piece | Files | Owner | Agent-days (S, rough) |
| --- | --- | --- | --- |
| Stage 0's measurements | Scratch and `validation/` | The FR lane, or numerics | 1–2, plus CPU hours |
| The time contract (N1) | `operators/contract.py`, `models/pump_composite.py` | Operators owner (STEP0 §4.2), after the pass | 3–5 |
| N2's IMEX ID | `numerics/surface_imex.py` (not byte-kept), with @3's slope terms in `models/surface_pump_v3.py` | Numerics, with the @3 owner for its file | 6–10 |
| The exact charged booking (seam D's branch X), which N2 needs | `models/surface_pump_v3.py` | @3 owner (CORE_SEAMS §13) | 2–3 |
| The coarse executor: boundaries, fine windows, records | A new module beside `execution/projective.py` | Numerics and execution | 3–5 |
| References, the protocol, the judged run | `validation/` | A references agent; the FR lane | 3–4, plus tens of CPU-h |
| **N1 with N2 and branch X, qualified** | | | **about 17–27** |
| R1, if needed | E's fast mode made composite and device-side; D175's fields (core lane item 4) | Numerics; the core lane | about 10–18 more |

- **Not before** the user's answers (§9), D188's move 2 and the core-seams pass, which owns
  `contract.py`, `pump_composite.py` and `surface_pump_v3.py` (D195, D213).
- **Byte-kept files stay untouched.** `numerics/extracellular_field.py` and `numerics/fixed_step.py`
  keep their bytes (CORE_SEAMS §8.2), so N2's solve is new code beside them.

## 9. Questions

**For the user:**
1. **Whose tolerances?** The parity caps (|dVm| ≤ 20 µV, |dc|/c ≤ 2 × 10⁻⁴) that projective failed?
   The requesting study's, when its specification arrives? Or a budget declared per question before
   each comparison?
2. **The first slow question.** Which consumer comes first: FR-7's loop at measured lifetimes,
   coupled renewal (E07-v2's turnover), or the requester's 24–72 h benchmark? Its horizon and its
   interventions set the acceptance world.
3. **Method or reduction.** Is a reduction (R1) acceptable where a method (N2) might suffice, given
   that a reduction needs D175's machinery and an envelope?
4. **Stage 0 first,** before any build?

**For the lead:**
5. N2 as a new IMEX ID under D147, owned by numerics with the @3 owner?
6. The time contract's classes (§4.1), and the counting record refused until it declares physical
   time?
7. Branch X's exact charged booking re-opened for N2 (§4.3), with the @3 owner, and M5 run before
   it is built?

## 10. The arithmetic

Every number marked **S** in §0, §1 and §5 comes from this script, run with `python3 -I` outside the
repository. It imports nothing from Cells.

```python
# FR-8 note arithmetic (S); costs from PUMP_COMPOSITE_V2_DESIGN.md §3 (one core) and PROGRESS (L4).
steps_per_hour = 3600 / 1e-3
one_core = {14: 1.72e-3, 254: 7.68e-3, 825: 75.7e-3}   # s per step, empty composition
for n, c in one_core.items():
    h = steps_per_hour * c / 3600            # CPU-h per simulated hour; 72 h in days = 72 h / 24
for sim_h in (1, 2, 4):                      # the seven-cell sheet's fine references, 1 and 0.5 ms
    ref = sim_h * steps_per_hour * one_core[14] / 3600
for factor in (10, 100, 1000):               # a step-count cut at the same cost per step
    t14 = 72 * steps_per_hour * one_core[14] / 3600 / factor
wh = 1786                                    # E07 tier 1 world-hours; 2.28 ms per world-step
gpu_h = wh * steps_per_hour * 2.28e-3 / 3600
separation = 3706 / 0.063                    # NUM-002's slow and fast modes
```

Its output, condensed: 3.6 × 10⁶ steps per hour. 1.72, 7.68 and 75.70 CPU-h per simulated hour at
14, 254 and 825 nodes, so 72 h is 5.2, 23.0 and 227.1 days. The seven-cell sheet's references are
1.7, 3.4 and 6.9 CPU-h for 1, 2 and 4 h at 1 ms, doubled at 0.5 ms. Cuts of 10×, 100× and 1000×
give 12.4, 1.2 and 0.1 h at 14 nodes and 55.3, 5.5 and 0.6 h at 254. E07 tier 1 is 4,072 L4
GPU-hours execute-only, 407 at a 10× cut. Projective admitted 0.10–0.17 mM cumulatively against a
cap of 1.2 × 10⁻³ mM. NUM-002's separation is 58,825.

## Sources

- The code at main 5133a850, as cited.
- Tikhonov's singular perturbation theory (§3.4), Rush and Larsen's exponential gates (as cited in
  EXCITABLE_TISSUE_DESIGN §2.1) and Ascher, Ruuth and Spiteri's ARS(2,2,2) (as cited in
  `surface_imex.py`) were not read for this note.
- No web search was made, and no external file was fetched.

## 11. The user's answers (18 November 2026; D217)

- **Approved: stage 0 only,** that is M1–M5 plus a small numerical harness. The harness is an existing
  single-cell or two-cell case on today's fine engine, benchmarked under M3, with its trajectory and
  reference outputs kept.
- **Each measurement's criteria and tolerance budget** are declared before its comparison. They cover
  cumulative trajectory error, intervention response, threshold timing, histories, conservation and
  measured cost. The old parity caps stay as benchmarks.
- **The method** (N2, or a reduction R1) is chosen after stage 0 and the core's FR-18 energy-check
  probe. The full solver build and an exact charged booking are not approved in advance. Questions
  5–7 for the lead wait for that choice.
- **The first scientific consumer** is FR-7's loop at measured lifetimes. Stage 0 does not wait for
  it.
