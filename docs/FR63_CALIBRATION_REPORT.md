# FR-63's calibration report: a declared pH shift on Kv1.5's activation

**Status: written 27 November 2026 at main 2274e9e4 (FR-64 landed at ff5c5fdc, D418), on branch `fr63-calibration`.**
- **A calibration report, not a registered comparison** (the user's decision, D399).
  - Each preparation's shift per pH unit is a two-point secant through its own midpoints.
  - So judging the engine against those midpoints would be circular.
- **No `src/` file changes.** Integration grants no acceptance (D143).
- **Engine models it runs:** `cells.model.resolved_pump_tissue@3` alone, with the law `cells.channel.kv1p5_mh@1`
  unchanged and FR-64's `voltage_shift` declared on its population (§2).
- **Every measured value is the Lean track's transcription,** read and never edited (§8).
  - The papers' own pages were not read for this report: their PMC pages refused automated access.
  - What the Lean files do not record is marked "not recorded".

**The request** (FR-63, logged by the user on 24 November 2026; D353, D356). Three labs agree that external acid moves
Kv1.5's activation positive.
- FR-63 is a declared `ph` shift on the m gate of a Kv1.5 population, in FR-64's mechanism.
- The gate reads V_r = V − ΔV, with ΔV = σ (pH − pH_ref) at the outside node's free protons
  (`src/cells/laws/channels/voltage_shift.py`). σ = dΔV/dpH is negative for an acid shift (D361).
- The size per pH unit is declared per preparation, since the labs differ.
- The evidence is extracellular, so each shift reads the outside, not the cell's proton row that FR-63's first reading
  named.

## 0. Summary

| Study | Cells, external K | pH, control → acid | Activation midpoint (mV), control → acid | n | Shift (mV) | σ (mV per pH unit) |
| --- | --- | --- | --- | --- | --- | --- |
| Trapani and Korn (2003) | HEK293, 10 mM | 7.3 → 6.8 | −15.3 ± 0.8 → −3.6 ± 2.4 (SEM) | 5 / 3 | +11.7 ± 2.5 | −23.4 ± 5.1 |
| Longobardo et al. (2001) | Ltk−, 4 mM | 7.4 → 6.5 | −14.2 ± 2.1 → +3.1 ± 0.7 (SEM) | 38 / 27 | +17.3 ± 2.2 | −19.2 ± 2.5 |
| Kehl et al. (2002) | HEK293, 3.5 mM | 7.4 → 6.4 | −18.3 ± 1.9 → −10.5 ± 1.2 (± as printed) | not given (§1.3) | +7.8 ± 2.2 | −7.8 ± 2.2 |

- **The uncertainty is one standard error.**
  - It is the two reported errors in quadrature, divided by |ΔpH| for σ.
  - It takes the pH as exact and the two groups as independent.
  - Where the same cells were recorded at both levels, a positive correlation makes the true error smaller.
- **The sizes differ beyond those errors.**
  - Kehl et al.'s σ lies 2.8 and 3.4 standard errors from the other two, which agree within one.
  - So σ is a per-preparation declaration, not a property of Kv1.5, as D351 and D361 say.
- **The development check meets its criteria** (§2). At each preparation's two pH levels, the engine's activation
  midpoint moves by the declared shift:
  - within 1.4e-18 V on the host path;
  - within 2.5e-17 V on the compiled path.

  **The check is circular by construction and calibrates nothing.**
- **Held out** (§4): five candidate quantities, none computed or scored here. The user decides whether a registered
  comparison follows.
- **The K–pH interaction** (§5) is reported as an indication, unjudged.
- **No engine gap blocks the calibration** (§7). One is reported: the closed set has no constant offset, so no
  declaration aligns the law's control midpoint, −6.0 mV, with a preparation's.

## 1. Each study

Each preparation carries one declaration on its Kv1.5 population's m gate.
- **σ is the full secant,** in V per pH unit.
- **The reference** is the preparation's control pH.
- **The window** is its two calibration levels, so any other pH is refused by name at the step, never clipped
  (FR-64 note §3.5).
- **There is no `source` key:** the world's registration carries the source (D361).

The literals below are the driver's (`validation/fr63/calibration_check.declaration`; the run's `declarations.json`).

### 1.1 Trapani and Korn (2003), HEK293

- **Preparation:** wild-type human Kv1.5 in HEK293 cells, whole-cell, at "room temperature" (no value given).
- **Solutions:**
  - 100 mM K and pH 7.3 inside;
  - 10 mM K outside, at pH 7.3 (control) and 6.8 (acid);
  - buffers not recorded.
- **Protocol** (Fig. 1F):
  - held at −80 mV, with prepulses 5 mV apart;
  - each prepulse lasts as long as reaches the peak step current while minimizing inactivation;
  - the peak tail conductance at −90 mV is normalized to its maximum in each condition;
  - the curves are fitted with a "modified Boltzmann" whose slopes and exponent are not printed.
- **Midpoints:** −15.3 ± 0.8 mV at pH 7.3 (n = 5) and −3.6 ± 2.4 mV at pH 6.8 (n = 3), SEM.
- **The secant:** a shift of +11.7 ± 2.5 mV, so σ = 11.7 mV / (6.8 − 7.3) = −23.4 ± 5.1 mV per pH unit.
- **The declaration:**

  ```json
  "voltage_shift": {"gates": {"m": {"ph": {"side": "outside", "shift_V_per_ph": -0.0234,
                                           "reference_ph": 7.3, "ph_window": [6.8, 7.3]}}}}
  ```

- **Sources:**
  - Fig. 1F and its caption;
  - `lean/checks/data/trapani2003_kv15_ph.json` (`trapani2003_kv15_ph`: `protocol`, `panel_F`);
  - `lean/claims/kv15-ph-activation.md`.

### 1.2 Longobardo et al. (2001), Ltk−

- **Preparation:** wild-type human Kv1.5 in Ltk− cells, whole-cell, 21–23 °C.
- **Solutions:**
  - 4 mM K outside, at pH 7.4 (control) and 6.5 (acid);
  - the internal solution and the buffers are not recorded. CAPS is recorded only for the pH 10.0 group, a held-out
    level.
- **Protocol:**
  - 250 ms depolarizations, with tails at −40 mV at pH 7.4 and −30 mV at pH 6.5;
  - the midpoints are estimated from the tail amplitudes just after the capacitive transient;
  - each curve is normalized separately;
  - the holding potential is not recorded.
- **Midpoints:**
  - −14.2 ± 2.1 mV at pH 7.4 (n = 38) and +3.1 ± 0.7 mV at pH 6.5 (n = 27), SEM;
  - the fitted slopes are 4.9 ± 0.2 and 5.2 ± 0.1 mV.
- **The secant:** a shift of +17.3 ± 2.2 mV, so σ = 17.3 mV / (6.5 − 7.4) = −19.2 ± 2.5 mV per pH unit.
  - Exactly, σ is −19.222… mV per pH unit, and the declaration carries its nearest binary64.
  - So the declared shift at pH 6.5 is +17.3 mV to rounding.
- **The declaration:**

  ```json
  "voltage_shift": {"gates": {"m": {"ph": {"side": "outside", "shift_V_per_ph": -0.019222222222222224,
                                           "reference_ph": 7.4, "ph_window": [6.5, 7.4]}}}}
  ```

- **Sources:**
  - Fig. 1 and the drug-free control results;
  - `lean/checks/data/paired_calibration_measurements.json` (`longobardo2001_kv15_controls@1`);
  - `lean/PROGRESS.md`, section `fr63-holdout-audit`.

### 1.3 Kehl et al. (2002), HEK293

- **Preparation:** wild-type human Kv1.5 in HEK293 cells, whole-cell tails, 20–25 °C.
- **Solutions:**
  - the pipette holds 130 mM KCl at pH 7.4. Its KOH titration leaves the total internal K unreported;
  - 3.5 mM K outside, at pH 7.4 (control) and 6.4 (acid);
  - buffers not recorded.
- **Protocol:**
  - held at −80 mV, with 300 ms prepulses 5 mV apart and tails at −50 mV;
  - at 3.5 mM K the prepulses run from −50 to +45 mV at pH 7.4 and from −30 to +65 mV at pH 6.4.
- **Midpoints at 3.5 mM K:** −18.3 ± 1.9 mV at pH 7.4 and −10.5 ± 1.2 mV at pH 6.4.
  - **The ±** is as printed: SEM, or the SD of a fit (§6).
  - **n** is not given for the midpoints. FR-63's table gives 6, which is the 3.5 mM conductance group's.
- **The secant:** a shift of +7.8 ± 2.2 mV, so σ = 7.8 mV / (6.4 − 7.4) = −7.8 ± 2.2 mV per pH unit.
  - Read as SDs over six cells, the errors give ±0.9 mV per pH unit instead.
- **The declaration:**

  ```json
  "voltage_shift": {"gates": {"m": {"ph": {"side": "outside", "shift_V_per_ph": -0.0078,
                                           "reference_ph": 7.4, "ph_window": [6.4, 7.4]}}}}
  ```

- **Sources:**
  - Fig. 2 and the Results;
  - `lean/checks/data/paired_calibration_measurements.json` (`kehl2002_kv15_potassium@1`);
  - `lean/checks/data/paired_replay_measurements.json` (`kehl2002_tail_protocol`).

### 1.4 What a world needs beside the declaration

- **An H row of valence +1,** the shift's default `proton`.
- **The outside pH** is the free H of the stage's read at the population's patch's outside node. That is its stored row
  where no closure holds it.
- **The bath at the preparation's own solutions,** at least its external K and its pH.
- **Leaving the window** is refused, never clipped.
  - Every held-out pH level in §4 lies outside its preparation's window.
  - Using one would need a wider declared window, an extrapolation the world's registration owns.

## 2. The development check: the engine applies the declared shift

**It is circular by construction and calibrates nothing.**
- σ is the secant through each preparation's own two midpoints. So the engine's midpoint shift between those two
  levels equals the measured shift by construction, and its sign is the data's.
- The check tests only that the engine applies the declared shift, arithmetic that FR-64's own rows already prove.
- It is not evidence about Kv1.5, and not a comparison with the measurements.
- It runs at the six calibration levels only.

**The world** (`validation/fr63/calibration_check.world`) follows FR-50 phase 2's World 1, adds FR-64's H row, and runs
@3 alone:
- one 1 pL cell on the held bath through its wall patch, at 298.15 K, the law's fixed temperature;
- the bath at the preparation's external K and at the level's pH. The H row is impermeant and has no buffer, so the
  shift reads the bath's stored row;
- one Kv1.5 population with the preparation's declaration, held closed (availability 0). Nothing crosses, so V stays
  at the cell's charge anchor, while the gates still relax to their targets;
- the cell's other contents are the fixture's, and nothing reads them.

**The engine's activation midpoint** is the voltage at which the m gate's target m∞, the readout `channel_targets`,
crosses one half.
- The labs' midpoints are Boltzmann fits to tail currents after prepulses, which also read inactivation (§3).
- **No protocol replay is run.**
  - Under the whole-gate form it would not move by exactly ΔV, since h reads V and inactivates during each prepulse
    (FR-64 note §8).
  - Its tail currents at Longobardo et al.'s calibration levels are a held-out readout (§4).

**The two paths:**
- **The host path is the run view's.**
  - For each anchor voltage, the definition is parsed and its initial state observed through the implementation's
    `observe_history`, which the runner calls at every observed row.
  - Bisection on the cell's charge anchor brackets the crossing of one half between adjacent anchors, in 52 to 55
    observations per level.
  - The midpoint is the mean of the bracket's two voltage readouts.
- **The compiled path is the runner's step.**
  - At the bracket's upper anchor, one compiled run of 0.5 s takes 5,000 steps of 0.1 ms under
    `cells.solver.imex_ars222_face_electromigration@1`, from m = 0.01.
  - That is over 50 time constants of m, so the settled m gate is the stage path's target.
  - Its midpoint is V − 4s (m − 1/2), with s = 6.4 mV the law's slope: the sigmoid's first-order inversion near one
    half.

**The criteria,** fixed in the driver before its first run:
- each preparation's midpoint shift, on both paths, equals the declared ΔV(acid) − ΔV(control) within 1e-15 V;
- each engine midpoint equals the law's −6.0 mV plus its level's ΔV within 1e-15 V;
- each settled gate equals its row's observed target within 1e-14.

ΔV is `validation/fr64/closed_forms.ph_shift`, in 50-digit decimals at the bath's own binary64 h. The bath's control
pH reads back as its reference only to rounding, so ΔV(control) is under 1e-18 V in size, not 0.

**The result: every criterion is met.**

| Preparation | Declared shift | Engine midpoint, control → acid (host) | Host: shift − declared | Compiled: shift − declared | Settled gate − its target (control, acid) |
| --- | --- | --- | --- | --- | --- |
| Trapani and Korn | +11.7 mV | −6.0 → +5.7 mV | 1.2e-19 V | 2.4e-17 V | 1.9e-15, 2.9e-15 |
| Longobardo et al. | +17.3 mV | −6.0 → +11.3 mV | 1.4e-18 V | 6.8e-18 V | 2.8e-15, 2.5e-15 |
| Kehl et al. | +7.8 mV | −6.0 → +1.8 mV | 7.8e-19 V | 3.4e-18 V | 2.6e-15, 2.5e-15 |

- **Each engine midpoint** lies within 8.7e-19 V of −6.0 mV + ΔV on the host path, and within 7.4e-17 V on the
  compiled path.
- **The settled gates sit a few 1e-15 below their targets.** The gate update adds (m∞ − m)(1 − e^−z), and it stops
  moving m once that increment is below half an ulp of m (`src/cells/numerics/exponential_gates.py`).
  - That is rounding. Through the slope it moves the compiled midpoint by under 1e-16 V.
- **The evidence** is in `/mnt/workspaces/Cells/fr63-calibration-20261127/`:
  - `check-01/run_inputs.json`, `check-01/declarations.json` and `check-01/results.json`;
  - `check-01.log`.

  The driver ran from a clean checkout of its commit, 417397c0 (empty status and diff), on CPUs 22 and 23, in 67 s.
- **It saves only voltages and activation targets:** no flux, time constant or current.
- **No test is added** (D224). The arithmetic is FR-64's, and its rows cover it.

## 3. What the declaration does not align

These are reported, not judged.
- **The control midpoint.** The parity law's m midpoint is −6.0 mV at every preparation's control.
  - That is above each preparation's control by +9.3, +8.2 and +12.3 mV (Trapani and Korn, Longobardo et al., Kehl
    et al.).
  - The declaration moves the law's curve by ΔV and does not align it. So the engine's acid midpoints (+5.7, +11.3 and
    +1.8 mV) sit the same offsets above the measured ones.
  - A constant offset is not in the closed set (§7).
- **The slope.** The law's m target has a 6.4 mV slope factor, with gate power one.
  - Longobardo et al. fitted 4.9 ± 0.2 and 5.2 ± 0.1 mV.
  - Trapani and Korn's fitted parameters are not printed.
  - Kehl et al.'s slope is not recorded in the Lean manifests.
- **What the midpoints measure.** The labs' midpoints come from tail currents after prepulses, so they also read
  inactivation and the channel's gating. The engine's is m∞'s.
- **τ.** The whole gate moves (D361), so m's time constant shifts with its target. That shift is unclaimed and
  unjudged.
- **Inactivation** is not shifted: h declares no shift.
- **The form is a secant,** so nothing is claimed between or beyond the two points.
- **Mechanism:** nothing is claimed about surface charge or titratable residues.
- **The acid loss of maximal conductance** is not represented (§5).
- **The Lean register's replay of the activation pair** ran the law with no declared shift, on engine 153449799f4d, and
  found no pH-induced shift. A replay with these declarations would show the declared shift by construction, so it
  would not be evidence either.

## 4. Held-out quantities

The Lean track's audit (`lean/PROGRESS.md`, section `fr63-holdout-audit`, 26 November) located these as candidates for
a later registered comparison (D399).
- **None of them was computed, plotted or scored here.** No engine output at their pH levels or readouts appears in
  this report or in its evidence.
- **The user decides** whether a registered comparison follows. A registration would fix its criteria before any engine
  run.
- **Every held-out pH lies outside its preparation's window,** so the declaration refuses it by name (§1.4). No world
  was run at one to show that.

| # | Quantity | Conditions | What it could test | Caveats |
| --- | --- | --- | --- | --- |
| 1 | Trapani and Korn, WT Fig. 6A: midpoints labelled at pH 6.2, 8.0 and 8.5 | HEK293, the calibration's preparation. The caption leaves external K unspecified. The Methods describe a zero-added-K control, and the Results discuss 10 mM K to isolate the shift. Fig. 6C normalizes the same series to a fit across pH | Whether a linear shift per pH unit holds outside [6.8, 7.3], on both sides | Outside the window. External K is unknown, and K changes the acid effect (§5). Fig. 6C's normalization reads a fit across pH |
| 2 | Longobardo et al., Fig. 1B: an untreated midpoint at pH 10.0 | Ltk−, 13 cells, CAPS buffer | Whether it holds on the alkaline side, far beyond the control | Outside the window. Its buffer differs from the calibration levels', which are not recorded |
| 3 | Longobardo et al., Fig. 2: a measured group near pH 5.5 | Five cells. Fig. 2 takes pH 10 as its reference. Its 6.5 and 7.4 markers have 21 observations each, against 27 and 38 in Fig. 1's pooled results | Whether it holds on the acid side, below the acid level | Outside the window. The group's bath details and its overlap with the calibration are unspecified |
| 4 | Longobardo et al., the drug-free tail-current decay: its fast and slow time constants and amplitudes | pH 7.4 and 6.5, inside the window. 250 ms depolarizations, with tails at −40 mV (pH 7.4) and −30 mV (pH 6.5). 38 and 24 recordings | The declaration with the law's kinetics at the calibration levels. That tests the parity law with the shift (its whole-gate move and its control offset, §3), not the shift alone | It shares the calibration's protocol and may share its cells. A registration must first fix the trace, the fitting interval, the components' order and the criterion for a resolvable second component. The outcomes are visible to evidence reviewers |
| 5 | Kehl et al., Figs. 3–4: WT maximal conductance across pH | HEK293. The external K of those figures is not recorded in the Lean files | A readout other than the midpoint: the available conductance across pH. A registration would first name the declaration it tests, and FR-63 declares only the gate's shift | The mutant series in the same figures measure other preparations |

**Also located by the audit, but not candidates:**
- **Trapani and Korn's Fig. 1B,** the acid/control current in a 75 ms step to 0 mV. It supplied no fit input, but the
  Lean track scored it on 21 November, so it is no longer unscored. It is excluded.
- **Longobardo et al.'s activation time constant at +60 mV,** at the two calibration levels. It is public in the Lean
  register as descriptive evidence, and the audit does not propose it.
- **Kehl et al.'s pH 5.9 readings.**
  - In Fig. 10's Results, an approximate shift is mentioned with no curve, bath K, n or error.
  - Fig. 9 holds one saturated-tail recording at 3.5 mM K.
  - The audit found no third WT midpoint inside the calibration window.

## 5. The K–pH interaction: an indication, unjudged

FR-63's first reading reports it and does not judge it. D351 ruled it an indication, from different readouts.
- The Lean register records both of its pairs as supporting the direction (`lean/WET_LAB_EVIDENCE.md`, rows
  `pair-kv15-potassium-protection` and `pair-kv15-acid-potassium-interaction`).
- It stays an indication here, and no engine value is set beside it.

| Study | Readout | pH | Value by external K | n | Error |
| --- | --- | --- | --- | --- | --- |
| Kehl et al. (2002), HEK293, Fig. 2 | Acid/control maximal tail conductance | 7.4 → 6.4 | 0 mM: 0.19 ± 0.02; 3.5 mM: 0.56 ± 0.01; 140 mM: 0.81 ± 0.12 | 12, 6, 6 | As printed |
| Trapani and Korn (2003), HEK293, Figs. 1C/D and 9B | Acid/control current at +100 mV | 7.3 → 6.8 | 0 mM: 0.380 ± 0.015; 3 mM: 0.977 ± 0.003; 10 mM: "essentially unaffected" | 3, 3, 5 | SEM at 0 and 3 mM |
| Jäger et al. (2001), RBL cells, Fig. 2 | Peak current at +40 mV (200 ms from −80 mV), nominal-zero K over 4.5 mM K | 7.4 and 6.0 | About 1 at pH 7.4; about 0.1 at pH 6.0 | Not given | None given |

- **The direction is common:** under acid, more external K leaves more current.
- **The readouts and their denominators differ:** a fitted maximum, a current at +100 mV, and a ratio within each pH.
- **FR-63's declaration does not carry it.** The shift moves only the m gate's voltage.
  - A loss of available conductance under acid that depends on external K would need its own declaration, which FR-63
    does not ask for.
  - FR-64's note (§8) names a routing-door factor for the acid loss alone, as one lab's indication, unclaimed.
- **Representability.** +100 mV lies above the law's domain (−120 to +60 mV). A nominally K-free bath would be declared
  at a trace, since @3 keeps every row above zero.

## 6. What is uncertain in the sources

- **Buffers** are not recorded in the Lean manifests at any calibration level. CAPS is recorded only for Longobardo et
  al.'s pH 10.0 group. The papers' Methods were not read for this report.
- **Trapani and Korn:**
  - the fits are a "modified Boltzmann" whose exponent and slopes are not printed, so the printed midpoint may not be
    the curve's half-activation voltage;
  - the temperature is given only as "room temperature";
  - n is 5 at control and 3 at acid. Whether the acid cells are among the control's is not recorded.
- **Longobardo et al.:**
  - n is 38 and 27 in Fig. 1's pooled results, but 21 and 21 at Fig. 2's markers;
  - the tail voltage was −40 mV at pH 7.4 and −30 mV at pH 6.5, so the two curves were read at different tail
    voltages;
  - the curves are normalized separately;
  - the internal solution and the holding potential are not recorded.
- **Kehl et al.:**
  - the ± type is open. The Methods use SEM in general and SD for nonlinear least-squares outputs. Read as SDs over
    six cells, σ's error would be ±0.9 mV per pH unit, not ±2.2;
  - no n is given for the midpoints. FR-63's table gives 6, which is the 3.5 mM conductance group's;
  - at 3.5 mM K the prepulse ranges differ between the two levels, and the acid range's +65 mV lies above the law's
    domain;
  - the total internal K is unreported.
- **All three:** the propagation assumes the two groups are independent.
- **FR-63's table** gives Kehl et al.'s system as "—". The Lean manifests give HEK293.

## 7. Engine gaps

- **None blocks the calibration.** FR-64's declaration carries each preparation's secant, and the check shows that the
  engine applies it.
- **Reported, not built:** the closed set has no constant offset.
  - So no declaration aligns the law's control midpoint (−6.0 mV) or its slope (6.4 mV) with a preparation's (§3).
  - Any registered comparison would carry the parity law's offset.
  - A constant offset would be a new kind of shift, and so a new request (FR-64 note §3.5 and §8).

## 8. Sources

**The papers.** Their bibliographic details are as FR-64's note read them from Crossref's records. Jäger et al. is
cited as the Lean record cites it.

| Work | Used here for | DOI |
| --- | --- | --- |
| Trapani JG, Korn SJ (2003), Biophys. J. 84(1):195–204 | Fig. 1F (calibration); Figs. 1C/D and 9B (§5); Fig. 6A and 6C (held out); Fig. 1B (excluded) | 10.1016/S0006-3495(03)74842-5 |
| Longobardo M et al. (2001), Br. J. Pharmacol. 134(2):359–369 | Fig. 1, the drug-free controls (calibration); Fig. 1B at pH 10.0, Fig. 2 and the tail decays (held out) | 10.1038/sj.bjp.0704251 |
| Kehl SJ et al. (2002), J. Physiol. 541(1):9–24 | Fig. 2 at 3.5 mM K (calibration, §5); Figs. 3–4 (held out); Figs. 9–10 (located) | 10.1113/jphysiol.2001.014456 |
| Jäger et al. (2001) | Fig. 2 (§5) | 10.1016/S0014-5793(00)02396-6 |

**The Lean track's files,** read and never edited:
- `lean/claims/kv15-ph-activation.md`;
- `lean/WET_LAB_EVIDENCE.md`, rows `pair-kv15-acid-activation-shift`, `pair-kv15-potassium-protection` and
  `pair-kv15-acid-potassium-interaction`;
- `lean/PROGRESS.md`, section `fr63-holdout-audit` (26 November);
- `lean/checks/data/trapani2003_kv15_ph.json`;
- `lean/checks/data/paired_calibration_measurements.json`: `longobardo2001_kv15_controls@1`,
  `trapani2003_kv15_high_voltage@1` and `kehl2002_kv15_potassium@1`;
- `lean/checks/data/paired_replay_measurements.json`: `jager2001_kv15_potassium@1` and `kehl2002_tail_protocol`.

**Cells:**
- FR-63 and FR-64 in [FEATURE_REQUESTS.md](FEATURE_REQUESTS.md);
- [FR64_VOLTAGE_SHIFT_DESIGN.md](FR64_VOLTAGE_SHIFT_DESIGN.md) §3.5, §8, §10 and §17;
- the decisions D143, D351, D353, D356, D361, D399 and D418;
- `validation/fr63/calibration_check.py`;
- the law's library page, [channel.kv1p5_mh@1](library/cells/laws/channel.kv1p5_mh@1.md).
