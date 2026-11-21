# An optional proton-return mode for ATP-driven proton pumps (FR-29): design note

**Status: proposed, 20 November 2026, by the kinds owner, for the lead; the build is held for the
user (D258). Evaluated at the desk against Fig. 3's curves on 20–21 November 2026: §8.** Desk work
only (D142).
This note covers the evidence, the design, the bitwise argument, the worlds affected, the held-out
test, the competing explanation, the files, the tests and a price. Nothing is built and nothing ran
on the engine. Branch `core-pass-kinds-16` from main 9b214dd8, where the code was read.

**D** marks a desk computation: short scripts outside the repository, which solve §1.3's formulas
on Table 2's numbers. They are kept with the kinds owner's workspace
(`/mnt/workspaces/Cells/core-pass-kinds-20261118/fr29/`: `desk.py`, `table.py`, `bounded.py`). No
engine code was involved.

**The request** (FR-29 in [FEATURE_REQUESTS.md](FEATURE_REQUESTS.md); D248). Kettner et al. (2003,
doi:10.1016/S0006-3495(03)74789-4), Table 2: moving the yeast vacuole's pH from 4.1 to 6.0 moved
the reversal of the ATP-dependent current by −13.0 mV. `proton_pump` predicts −112.40 mV at every
supported ratio. The data are `lean/checks/data/kettner2003_vacuole.json`, read here and not edited.
The paper's open-access copy (PMC1303676) was consulted through a web reader for the authors' model,
their Table 1 and the solutions they used. Its equations are images there, so §1.1's circuit formula
is our reading of it. That reading reproduces the ratios the paper prints for rows 4 and 5.

**Engine models it would run:** `cells.transporter@1` on its population axis, with
`cells.proton_atp_mass_action_positive@1` gaining one optional mode. The world for the test is
FR-4's development world reduced to a cytosol, a vacuole lumen and the patch between them (§4).

## 0. Summary

| | |
| --- | --- |
| **What exists** | The pump law has one mode: n H⁺ from N to P per ATP hydrolysed at N, with J = S (1 − e^x). Version 1's kernel runs it in FR-4 and FR-5; the general form (factored) runs it on the population axis. Tight coupling moves the reversal one-for-one with E_H |
| **The authors' reading** | A pump and a proton shunt in parallel through the same enzyme, with a shunt-to-pump conductance ratio of 0.17 to 1.09 across the five rows. That gives an apparent coupling ratio of 2.3 to 4.2 H⁺/ATP |
| **Recommended** | One optional mode on the same law, `return`: one H⁺ back from P to N while the pump holds ATP. Its S carries the pump's ATP factor, a site loaded from the lumen and emptied to the cytosol, and a voltage factor. Off unless a population declares it |
| **Engine changes** | `forms.py`: optional modes, mode parameters, a per-mode rate on factored modes with a bounded voltage term, and a negative Hill number for an emptying site. `transporter.py`: the population key `optional_modes`, layouts from each population's own modes, the per-mode rate in S and its voltage slope, its supremum in the definition-time bounds, and a per-mode heat record where an optional mode is declared |
| **Bitwise** | Every existing world, including FR-4 and FR-5 on version 1's kernel. No world declares the mode, so layouts and programs are unchanged (§2.5) |
| **Held-out test** | Fit the return's ratio and site pK on rows 3 and 5 (lumen pH 4.1 and 6.0). Predict rows 1, 4 and 6, each within 2 SE, and check the three bounds. Only row 4 and the bounds remain truly held out: the form's cytosolic factor and the voltage exponent's range were chosen after the desk saw rows 1 and 6 (§1.3) |
| **Desk outlook (D)** | The first prediction (a return loaded from the lumen only) missed rows 1 and 6 and two bounds. The revised one-site form predicts rows 1 and 4 within 2 SE at every voltage exponent tried. Row 6 passes only at an exponent of 1 with the voltage term bounded (−57.2 at ψ_s = −100 mV), a post hoc choice. The lumen-pH-3.1 bound (> +40 mV) fails throughout (0 to 6 mV). The return mode alone does not explain that row. Superseded by Fig. 3's curves: §8 |
| **Separating measurement** | ATP hydrolysis where the ATP-dependent current reverses. The return mode predicts 95–100% of the pump mode's saturated rate there. Variable tight coupling predicts zero |
| **Price** | 4–5 agent-days, gates excluded |

## 1. The evidence, and what the desk shows

### 1.1 Table 2, and tight coupling

Voltage is cytosol minus lumen. The current is measured in ATP, ADP and phosphate (5, 5 and
10 mM) minus a baseline in the bath medium, which has no ATP, ADP or phosphate. Five reversals
were resolved and three are bounds.

| Row | pH cyt / lumen | E_ATP (mV) | E_H (mV) | Measured | Tight, n = 2 (D) |
| --- | --- | --- | --- | --- | --- |
| 1 | 8.5 / 5.0 | −587.5 | 207.2 | −17.5 ± 5 (6) | −86.7 |
| 2 | 7.5 / 3.1 | −531.4 | 260.5 | > +40 (3) | −5.4 |
| 3 | 7.5 / 4.1 | −531.4 | 201.3 | −25.6 ± 1 (4) | −64.6 |
| 4 | 7.5 / 5.0 | −531.4 | 148.0 | −34.0 ± 4 (14) | −117.8 |
| 5 | 7.5 / 6.0 | −531.4 | 88.8 | −38.6 ± 9 (3) | −177.0 |
| 6 | 6.0 / 5.0 | −491.9 | 59.2 | −59.8 ± 3 (9) | −186.8 |
| 7 | 5.0 / 5.0 | −494.0 | 0.0 | < −80 (5) | −247.0 |
| 8 | 7.5 / 7.5 | −531.4 | 0.0 | < −80 (4) | −265.7 |

- **Tight coupling:** a pump moving n H⁺ per ATP reverses at E_H + E_ATP/n. From row 3 to row 5
  that moves by ΔE_H = −112.5 mV, whatever n is.
- **n = 2 is the largest integer** that puts every resolved reversal on the pump's forward side.
  It is also the paper's N.
- **The apparent ratio:** n_app = −E_ATP/(E_H − V_rev) is 2.62, 2.34, 2.92, 4.17 and 4.14 on
  rows 1, 3, 4, 5 and 6 (D).

**From the paper (PMC1303676):**
- **E_ATP:** K_ATP in its Table 1 is the apparent equilibrium constant of hydrolysis, by cytosolic
  pH (83.8, 9.47, 2.04 and 2.21, in the table's units of 10⁶ M, at pH 8.5, 7.5, 6.0 and 5.0). The
  table's E_ATP comes from it, so E_ATP is the authors' estimate, not a measurement (the data
  file's limits).
- **No pump affinity for ATP** is given.
- **The temperature** is not reported. E_H's 59.2 mV per pH unit implies 298 K.
- **The current–voltage curves (Fig. 3):** the legend says the pump currents saturate at positive
  voltages. The results attribute saturation at high voltages of either sign to rate-limiting
  chemical steps such as substrate binding or release. No slope conductance is given.
- **The authors' model** is an equivalent circuit: the pump limb (EMF E_P = E_ATP/N + E_H,
  conductance G_P) in parallel with a proton shunt (EMF E_H, conductance G_S) through the same
  enzyme, with N = 2.
  - Reading their circuit as E_rev = (G_P E_P + G_S E_H)/(G_P + G_S) gives G_S/G_P = 0.308, 0.172,
    0.461, 1.087 and 1.068 on the five rows (D). Their Table 2 lists 0.461 and 1.086 on rows 4
    and 5.
  - So the shunt is a fitted ratio per row. It rises about sixfold as ΔpH falls from 3.4 to 1.5.
  - Their empirical fit is n = 4.9 − 0.69 ΔpH.
- **Their proposed separating measurements:** net proton flux and ATP hydrolysis at several points
  of the current–voltage curve, pH-sensitive electrodes in large vacuoles, bafilomycin-sensitive
  channel-like noise, and a- and c-subunit mutants.

### 1.2 What a return mode must do in the kind's kinetics (D)

Each mode's flux is J = S (1 − e^x), with S its magnitude and x its free energy per cycle in RT
units.
- **Both modes are saturated at every resolved reversal.** With n = 2, the pump mode is 39–138 mV
  beyond its own reversal there, so e^x < 0.05. A return of protons from P to N is 119–227 mV from
  E_H.
- **So S must depend on voltage.** With S independent of voltage, the net current would be flat
  near the measured reversals. It could cross zero there only if the return's S were tuned to equal
  the pump's.
- The return's S must therefore carry a voltage factor. It must also carry the protons it reads:
  - in the lumen, which loads it;
  - in the cytosol, which it empties into. The cytosolic series (rows 1, 4 and 6) moves the
    reversal by about 17 mV per unit of cytosolic pH.
- **The voltage factor must be bounded.** A bare e^(−δ_r ψ) grows e-fold every 25.7/δ_r mV below
  the reversal, without limit. That conflicts with the authors' saturation at high voltages of
  either sign.
  - It also breaks the kind's definition-time bound. `_population_bound_rate` (B7) takes a factored
    mode's S at most 1, and the bare stage term evaluates S without a voltage.
  - The design therefore uses e^(ζψ)/(1 + e^(ζ(ψ − ψ_s))), with ζ = −δ_r and ψ_s a saturation
    voltage. It is e^(ζψ) above ψ_s and tends to e^(ζψ_s) below it.

### 1.3 The desk's two families, fitted on rows 3 and 5 (D)

**The pump mode is today's in both,** with n = 2, its cytosolic proton site saturated and the
fuel's drive at the table's E_ATP. ρ is the return's rate relative to the pump's saturated rate.

**The first prediction (D248: preserved as made).** A return loaded from the lumen only,
J_r = ρ k a [ATP factor] [h_P/(h_P + K_r)] e^(−ψ/2) (1 − e^(x_r)), with δ_r = ½ fixed a priori.
- ρ = 1.16 and pK_r = 6.66 were fitted on rows 3 and 5.
- It predicted −28.6, −29.1 and −30.7 mV on rows 1, 4 and 6 (measured −17.5 ± 5, −34.0 ± 4 and
  −59.8 ± 3), and +4.4, −40.8 and −135.0 mV on rows 2, 7 and 8 (bounds > +40, < −80, < −80).
- So it passed row 4 and row 8's bound. It missed row 1 (2.2 SE), row 6 (9.7 SE) and the bounds of
  rows 2 and 7.
- The same run also tried δ_r = ¼ and 1. Both missed row 6 by more than 8 SE and row 7's bound.
- It has no dependence on the cytosolic side. The misses on rows 1 and 6 show that one is needed.

**The revised family,** written after that miss. The return mode is:

    J_r = ρ k a [ATP factor] [h_P/(h_P + K_r)] [K_r/(K_r + h_N)] e^(−δ_r ψ) (1 − e^(x_r)),

- x_r = ln(h_N/h_P) + ψ, where ψ = F(φ_N − φ_P)/RT is the kind's voltage. With N the cytosol, ψ is
  the table's voltage in RT/F units.
- **One site, one pK:** it is loaded from the lumen and must be empty on the cytosolic side.
- **k a** is the population's capacity times availability.
- **ρ and K_r are fitted** on rows 3 and 5 for each value of the voltage exponent δ_r. The fit is
  exact, since there are two unknowns and two rows.

| δ_r | ρ | pK_r | Row 1 (−17.5 ± 5) | Row 4 (−34.0 ± 4) | Row 6 (−59.8 ± 3) | Row 2 (> +40) | Row 7 (< −80) | Row 8 (< −80) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.5 | 1.33 | 6.66 | −22.6 | −29.1 | −110.0 | +4.4 | −214.9 | −135.0 |
| 0.75 | 0.98 | 6.41 | −25.7 | −28.4 | −69.6 | +1.8 | −138.5 | −116.1 |
| 1.0 | 0.75 | 6.24 | −26.7 | −28.1 | −52.9 | +0.2 | −101.9 | −103.2 |

**With the bounded voltage term of §1.2,** at ψ_s = −100 mV (D):
- At δ_r = 1, rows 1, 4 and 6 move to −26.5, −28.2 and −57.2, and the bounds to +0.3, −216.0 and
  −183.1.
- At δ_r = ½, they move to −18.9, −29.6 and −173.4.
- At ψ_s = −150 mV the shifts are smaller still.

**Below the reversal, the form predicts a large inward current.** 60 mV below row 4's reversal, the
net current is inward at 1.3 to 9.4 times the pump mode's outward ceiling, from δ_r = ½ with
ψ_s = −100 mV to δ_r = 1 unbounded. That is a second check against Fig. 3, once its curves are read.

**What the desk establishes:**
1. **The lumen series' flattening:** a return mode reproduces the measured −13.0 mV, and both
   families predict row 4 within 2 SE.
2. **The cytosolic side is needed, and row 6 pins δ_r.** Row 1 passes at every δ_r in the revised
   family. Row 6 misses by 17 SE at δ_r = ½, 3.3 SE at ¾ and 2.3 SE at 1. With the voltage term
   bounded at ψ_s = −100 mV, δ_r = 1 brings it within 1 SE (−57.2).
3. **The lumen-pH-3.1 bound fails in every variant tried,** at 0–6 mV against > +40 mV measured.
   At the bound's ΔpH of 4.4, the authors' circuit needs G_S/G_P > 0.2. A return saturated in its
   own drive cannot grow that much from pH 4.1 to 3.1 without spoiling the flat middle.
4. **ATP is still hydrolysed at the reversal.** At every resolved reversal the pump mode runs at
   95–100% of its saturated rate: the share 1 − e^(x_c) is 0.95 on row 3 and 0.99–1.00 elsewhere.
   This is the measurable difference from variable coupling (§5).

**What the desk saw, and what is still held out.**
- The desk saw all eight rows.
- The revised family's cytosolic factor was added after the first prediction missed rows 1 and 6.
  δ_r's range was explored against row 6.
- **So rows 1 and 6 are no longer out of sample** for the revised form or for δ_r. Only row 4 and
  the three bounds are.
- §4 registers that. The first prediction stands as made.

## 2. The design: one law, an optional return mode, off by default

### 2.1 The return mode on `proton_atp_mass_action_positive@1`

- **Rows and counts:** the law's rows stay as they are: proton at N and P, then ATP, ADP and Pi at
  N. The `return` mode's counts are (+1, −1, 0, 0, 0), one proton from P to N, so q is −1 in the
  kind's sign.
- **Free energy:** x_r is the kind's, from the registry's potentials: ln(h_N/h_P) − q ψ. No
  constant of the law enters it, it converts nothing, and so it emits no seam-E entry.
- **Magnitude**, a factored mode with a rate:
  - `Saturation(("ATP", "N"), "km_atp_mM", 1)`, the pump mode's own ATP factor and parameter. It
    holds the return to "while energized": without ATP, neither mode runs.
  - `Saturation(("proton", "P"), "km_return_mM", 1)`: the site loads from the lumen.
  - `Saturation(("proton", "N"), "km_return_mM", -1)`: the site empties to the cytosol. This needs
    a negative Hill number, `[1 + c/K]^-1` (§2.2).
  - A per-mode rate: the constant `return_ratio` (ρ), and the bounded voltage factor
    e^(ζψ)/(1 + e^(ζ(ψ − ψ_s))), with ζ = −δ_r. δ_r is the parameter `return_delta` and ψ_s comes
    from `return_saturation_mV`.
- **Each mode books its own movement and dissipation:**
  - Its cycle count is already per mode (`cycle_count` [M, P]), and so is its proton movement,
    the counts times the mode's ν.
  - Its heat, −RT J_m x_m, is today summed into `cycle_dissipated_energy_pJ`. Where a population
    declares an optional mode, a per-mode accumulator `cycle_mode_dissipated_energy_pJ` [M, P]
    joins it. It is booked by seam D's trapezoid rule, as the total is, and the total stays
    exactly its sum (a check).
  - The held fuel's work stays the pump mode's alone, since the return mode moves no fuel row.

### 2.2 `laws/cycles/forms.py` (the kinds owner's)

- **Optional modes:**
  - `CycleForm.optional_modes`, a tuple of mode IDs that a population runs only if it declares
    them.
  - `Parameter.mode`, the optional mode a parameter belongs to, or None. A mode's parameters are
    required where it is declared and refused where it is not.
  - `resolve`, `resolved` and `parameter_errors` take a population's declared optional modes and
    drop the others, with their saturations, rates and parameters.
  - A form that declares none behaves exactly as today.
- **A per-mode rate for factored modes:** `FactoredRate(constants=(), zeta=0.0, saturation_mV=None)`
  per mode, in `CycleForm.mode_rates`.
  - Its constants are parameters only, as on a monomial rate (D144).
  - zeta is a number, a parameter's name or an Affine.
  - With zeta nonzero, saturation_mV (a parameter's name) is required. The form refuses an
    unbounded voltage term: log S gains ζψ − log(1 + e^(ζ(ψ − ψ_s))), so S stays below
    e^(ζψ_s) Π K.
- **The manifest:** `cycle_changes` gives an optional mode's rows with `optional: true`. The
  declarations manifest, the library's generated blocks and the visualizer's data built from them
  gain those rows when regenerated.
- **Negative Hill numbers in a saturation:** `[1 + (K/c)^h]^-1` with h a negative integer is an
  emptying site.
  - `hill_log_saturation` already computes it, gradient included.
  - The kind's other use, B7's held-row factor −log(1 + e^(h ln(K/c))), is valid for either sign,
    since every factor stays at most 1.
  - So only the form's check changes: a Hill number is a nonzero integer, or a positive integer
    parameter as today.
- **Plants:**
  - an optional mode that is not a mode;
  - a mode parameter on a required mode;
  - a FactoredRate constant given as a number;
  - Hill 0.

### 2.3 `kinds/transporter.py` (the kinds owner's)

- **The entry:** a general-form entry gains the optional key `optional_modes`, a list of the law's
  optional mode IDs. It is written back only if declared, so every definition round-trips as
  today. Version 1's keys cannot declare it, so a world that wants the return declares its pump in
  the general form.
- **The layout:**
  - Each population's own form (resolved with its declared modes) sets its rows, modes and
    saturations.
  - M is the most modes of any population, not of any law. A world without the key gets today's M
    and today's arrays.
  - The per-mode rate's fields, `cycle_fr_log_k` and `cycle_fr_zeta` [M, P], exist only where some
    population declares a FactoredRate. That is a static switch, as `cycle_sat_*` and the monomial
    tables have.
- **The evaluation:**
  - A factored mode's log S gains the constants' Σ ln K and the bounded voltage term.
  - Its `d_log_s_psi` gains ζ (1 − σ), with σ the logistic of ζ(ψ − ψ_s). The stage rule's charge
    slope and the K3b material term read it as they read a monomial mode's (K6).
  - The per-mode heat accumulator exists only where a population declares an optional mode.
- **The bounds:**
  - `_population_bound_rate` (B7) takes S_max as today, times the mode's Π K and e^(ζψ_s), the
    supremum of its voltage term.
  - The bare stage term evaluates S at zero voltage. For a mode with a voltage term it uses that
    supremum instead, so the voltage-free path stays an upper bound. (A monomial mode fails closed
    there, since its S has no bound in ψ.)
  - The entity binding (`cycle_changes`' rows per population) reads each population's declared
    modes.
- **Refusals:** an undeclared optional mode's parameter, a declared mode the law lacks, and the
  key in version 1's keys.

### 2.4 `laws/pumps/proton_pump.py`

- The general form `CYCLE` gains the `return` mode as above. Its parameters each carry
  `mode="return"`:
  - `return_ratio` (1, positive);
  - `km_return_mM` (mM, positive);
  - `return_delta` (1, in [0, 1]);
  - `return_saturation_mV` (mV).
- The module docstring gains the mode and its sources.
- **Version 1's kernel is untouched.** `kinetics`, `domain_valid`, the stage and loop terms,
  `MOVES` and `DECLARATION` stay as they are.
- The law ID stays (D147): a declaration without the key runs exactly today's law, and one with it
  asks for the extension by name.

### 2.5 What stays bitwise, and why (D148, D175)

- **Version 1's worlds:** FR-4 and FR-5 run the pump through version 1's kernel, and nothing in it
  changes.
- **Population-axis worlds:** none declares `optional_modes`. Each population's resolved form is
  therefore its law's form as today, M and every array are today's, and the new fields do not
  exist. The programs are the same jaxprs.
- **The check:** the full gate. Crossrev's eleven sets, FR's bitwise landing set and G1's 113
  worlds must be identical, with no declared difference. D148's four criteria then hold
  trivially: no field, verdict, ledger or baseline moves.
- **D175:** the return is a mechanism, not a representation. Its presence is a declared key, real
  in the kernels when declared and absent from them when not. It is not a runtime flag.

### 2.6 Yeast values as population parameters (D144)

| Parameter | Value for the test | Source |
| --- | --- | --- |
| `stoichiometry` n | 2 | The paper's N; the largest integer with every resolved reversal on the pump's forward side |
| `km_role_mM` (cytosolic H⁺ site, Hill n) | 1e-7 mM, saturated over pH 6.0–8.5 | Declared: the source gives none, and pumping is measured at cytosolic pH 8.5 |
| `km_atp_mM` | 0.2 mM | Declared: the source gives none. Both modes share it, so it cancels at the reversal |
| fuel (held, at the cytosol) | ATP 5, ADP 5, Pi 10 mM; drive set to the table's E_ATP | Table 2's AAP medium, and the authors' E_ATP through the fuel rows' potentials, as FR-4 declares its own |
| `return_ratio` ρ, `km_return_mM` K_r | fitted on rows 3 and 5 | §4 |
| `return_delta` δ_r, `return_saturation_mV` ψ_s | registered before the run (§4) | §4; from Fig. 3 if ruled (§7) |
| temperature | 298.15 K | Not reported; E_H's 59.2 mV per pH unit implies it |

## 3. Which worlds run `proton_pump` today

- **Registered and judged, on version 1's kernel:**
  - FR-4 (`validation/compartment_ph/protocols/fr4_acidification_v1.json`) and FR-5
    (`fr5_transfer_v1.json`), built by `validation/compartment_ph_engine/definitions.py`
    (`PUMP_LAW`, version 1's keys).
  - FR's bitwise landing set (`scripts/gates/fr_landing_set.sh`) and crossrev's kinds set
    (`validation/tissue/composite_crossrev.py`: FR-4's development and declared worlds and FR-5's
    arm T, first five steps).
  - The tissue protocol `validation/tissue/compartment_ph_protocol.py`.
- **Development and checks on version 1's kernel:**
  - `compartment_ph_engine`'s `dt_study.py`, `refusal_paths.py`, `planted.py` and
    `fr5_quick_check.py`;
  - `validation/compartment_ph/ph_reference.py`, FR-4's independent reference;
  - `validation/execution/window_row_checks_runs.py`;
  - the test files `test_rapid_binding_world.py`, `test_rapid_binding_parse.py` (its refusals
    under the general closure), `test_cell_owned_compartments.py` (its step-term pins),
    `test_fr45_proton_laws.py` (the kernels) and `test_transporter_kind.py` (version 1's refusal
    rows, `PROTON_LAW`).
- **The population axis:**
  - seam A's references: `validation/core_seams/references/worlds.py`, whose `law_v1_proton` is the
    factored form with one mode, with its `design.py`, `designs/core_seams_reference_design.json`
    and `reference_inputs.json`. They are compared in `test_cycle_kind_references.py`;
  - `test_cycle_kind.py`'s refusal rows;
  - `test_law_registry.py`'s hosted-laws pin, which names the law and not its modes.
- **Generated or recorded copies that name the law:**
  - the visualizer's `data/engine/declarations.json`, `data/laws/pieces.json` (its change rows per
    mode) and `data/architecture/architecture.scene.json`;
  - its run-view fixture `tests/engine-views/run-view-89bd2ffb/condition/resolved_config.json`
    (FR-4's run) and `tests/fixtures/run-view-made-up/plants.json`;
  - `scripts/moves/move2*.json` (a source move's record);
  - the Lean project's `lean/checks/atp_cycle.py`, its own copy.

  Only `pieces.json` and the manifest it is generated from show modes, and they gain the optional
  mode's rows when regenerated, as `optional`. That is the visualizer owner's regeneration.
- **None declares a second mode.** Each keeps its bits (§2.5).

## 4. The held-out test

- **The data:** Table 2's eight rows, transcribed with their provenance into
  `validation/vacuole/kettner2003_table2.json`. It is checked row for row against the Lean
  project's file, which stays read-only and is not a dependency. Table 1's K_ATP enters only
  through Table 2's E_ATP.
- **The subtraction:** the ATP-dependent current is the population's current in the AAP medium
  minus the baseline medium.
  - The baseline has no ATP, ADP or phosphate, so neither mode can run either way. The pump
    population's baseline current is zero, a declared reading.
  - The factored form's own limit at c_ATP → 0 is not used. It lacks product saturation, and with
    ADP and Pi present it would give an artefactual backward flux.
  - The test's current is therefore the population's own, both modes, outward from the cytosol
    positive.
- **The evaluation:**
  - One world per row: the cytosol, the lumen and the patch, with the row's pHs as the free proton
    concentrations at each node, and the row's fuel drive.
  - The pump population in the general form, with `optional_modes: ["return"]`.
  - The kind evaluates its per-mode rates at clamped voltages, through the same evaluation the step
    uses, with no stepping. The reversal is the zero of the population's current, by bracketing and
    bisection to 0.01 mV.
  - A small public entry point in the kind, `clamped_rates(spec, state, control, voltages_V)`, gives
    per-mode J at declared voltages in fmol/s and A, outward positive. That is also FR-34's
    transporter half.
- **What is registered, and its status:**
  - **The first prediction** (§1.3) is recorded as made, with its misses on rows 1 and 6 and on the
    bounds of rows 2 and 7. It is never rescored or replaced.
  - **The engine's registered model:** n = 2 and the pump mode as today, with the §2.6 values,
    and the one-site return of §2.1. It was revised after the first prediction.
  - **Ruled (D258): δ_r and ψ_s are fitted on Fig. 3's rows 3 and 5 curves; §8 has the result.**
  - **δ_r and ψ_s are not registered by this note.** δ_r = ½ is the only a-priori value, a
    symmetric barrier. δ_r = 1 is the desk's best for row 6, and is post hoc. Ruling 1 chooses:
    - δ_r and ψ_s from Fig. 3's curves at rows 3 and 5's conditions, digitized and registered
      before the run, which uses no held-out row; or
    - δ_r = ½ with ψ_s declared, and 1 reported beside it, labelled post hoc, never as the score.
- **The fit:** ρ and K_r on rows 3 and 5, exactly.
- **The predictions:** rows 1, 4 and 6, and the bounds of rows 2, 7 and 8.
  - **Out of sample:** row 4 and the three bounds. **In sample for the form's choice:** rows 1
    and 6, which are scored and labelled so.
  - **Pass:** each predicted reversal within 2 SE of the measured value (row 1 ±10, row 4 ±8,
    row 6 ±6 mV), and every bound respected.
  - **The score:** row 4 and the bounds out of four, and rows 1 and 6 out of two, kept apart as the
    registered comparator (D248).
- **Preservation (D248):** the prediction is written to its record before it is scored, with the
  data's revision, the fitted values, the comparator, the units and the thresholds. A miss stays
  as it is. Its investigation records what it established, who owns the open question, and which
  observation would resolve it.
- **The desk's expectation (D):**
  - Row 4 passes.
  - The zero-gradient bounds pass.
  - The bound at lumen pH 3.1 fails at every δ_r tried.
  - Row 6 passes only at δ_r = 1 with the voltage term bounded, a post hoc choice.

  A recorded miss on row 2's bound is informative: the return mode alone would not account for the
  very acidic lumen.

## 5. The competing explanation, and the measurement that separates them

- **Variable coupling.** The pump's own stoichiometry changes with the gradient: n_app runs from
  2.34 to 4.17 on the five rows, and the authors fit n = 4.9 − 0.69 ΔpH. In the kind it would be
  a diagram law with two coupled cycles of different n through shared states, as seam A's D4
  reference has a slip cycle. It would not be a mode of this law. It is not built here.
- **What separates them is ATP hydrolysis at the current's reversal.**
  - **Return mode:** the pump mode still runs forward there, at 95–100% of its saturated rate (D),
    and the return carries the protons back. So ATP is consumed at about the pump's full rate
    while the net current is zero, and the ratio of ATP hydrolysis to current diverges at the
    reversal.
  - **Tight variable coupling:** the effective cycle is at equilibrium at its reversal, so ATP
    hydrolysis passes through zero with the current.
- **The fresh measurement** is the authors' own proposal: ATP hydrolysis and net proton flux
  together, at several clamped voltages around the reversal. Examples are Pi release from a
  voltage-clamped vacuole, or vesicles at a set ΔpH and Δψ with ionophores.
- **Net proton flux alone does not separate them,** since it is the current. A unidirectional
  proton flux would, but that is harder.
- **The engine predicts it directly.** The return mode's per-mode counts give the ATP hydrolysed
  (the pump mode's count, which the held fuel's supply records) and the proton movement of each
  mode, at every clamped voltage. The test's record exports both, as this mechanism's prediction
  for that measurement, before any such data exist.

## 6. Files, tests and price

| File | Change | Owner |
| --- | --- | --- |
| `src/cells/laws/cycles/forms.py` | Optional modes, mode parameters, FactoredRate with its bounded voltage term, negative Hill, optional rows in `cycle_changes` | kinds owner |
| `src/cells/kinds/transporter.py` | `optional_modes` key, per-population layouts and bindings, the rate in S and its ψ slope, its supremum in B7 and the bare stage term, the per-mode heat, `clamped_rates` | kinds owner |
| `src/cells/laws/pumps/proton_pump.py` | The `return` mode in `CYCLE`, its parameters and docstring; the kernel untouched | kinds owner |
| `validation/vacuole/kettner2003_table2.json`, `return_mode_comparison.py` | The data with provenance, and the registered held-out comparison | kinds owner (a validation driver, D224) |
| `docs/library/cells/kinds/transporter@1.md` | The optional mode, re-rendered blocks | kinds owner |
| `visualizer/data/...` | The manifest's new rows, regenerated | the visualizer owner, after landing |

**Tests,** as rows in existing files (D224), except one comparison row:
- **`test_cycle_forms.py`:** optional-mode resolution, the refusals and their plants, FactoredRate's
  arithmetic, and a negative Hill number's value and gradient.
- **`test_cycle_kind.py`:**
  - the key's parse, its refusals and its round trip;
  - the off-by-default invariance row: a population-axis pump world with and without the law's
    optional mode in its form gives identical arrays and two identical steps;
  - a world with the return mode: two steps close every ledger, the per-mode heat sums exactly to
    the total, each mode's proton movement is its counts, and the charge slope includes the
    voltage term's;
  - B7's bound and the bare stage term bound the return mode's slope from above at every voltage.
    Planted: S at zero voltage instead of its supremum fails that row.
  - Each row is a numpy world, a few seconds.
- **The comparison:** its registered run is landing evidence, as the mitochondria harness's is.
  One small row in `test_cycle_kind.py` checks that `clamped_rates` gives the kind's own J at the
  world's voltage.

**Price:**
- forms and kind, the bounds included: 2–2.5 days;
- the law: 0.25 day;
- tests: 0.5 day;
- the data, the comparison driver and its registered run: 1–1.5 days;
- docs and review: 0.25 day.

That is **4–5 agent-days,** gates excluded. Digitizing Fig. 3, if ruled (§7, ruling 1), is about
0.5 day more.

## 7. Rulings asked

1. **δ_r and ψ_s:** taken from Fig. 3's curves at rows 3 and 5's conditions, digitized and
   registered first, which the note recommends since it uses no held-out row. Or δ_r = ½, the only
   a-priori value, with ψ_s declared and δ_r = 1 reported beside it as post hoc.
2. **Per-mode heat:** a per-mode heat accumulator only where an optional mode is declared (§2.1),
   or a per-mode heat readout derived from per-mode counts without new state.
3. **The data:** Table 2 transcribed into `validation/vacuole/` with provenance, rather than read
   from the Lean project's file.
4. **The baseline:** the ATP-free baseline taken as zero pump current, as a declared reading
   (§4).
5. **Variable coupling:** whether it is built later as the competing hypothesis's own law (§5), or
   left as the recorded alternative until the separating measurement exists.

## 8. The desk evaluation against Fig. 3 (D258, 20–21 November 2026)

This section reports what the lead's desk evaluation established on the curves. It is a closed-form
computation, not the engine, run on the FR-7 lane's reading of Fig. 3
(`validation/vacuole/kettner2003_fig3_readings.csv`).
- **Records:** frozen as evidence in `/mnt/workspaces/Cells/core-pass-kinds-20261118/fr29/evidence/`
  (README and SHA256SUMS). The lead ruled them out of `validation/`, since a closed-form return mode
  is physics the engine lacks. They were registered in git on branch core-pass-kinds-18:
  - the prediction, `fr29_desk_prediction.json`, at 4531d06d (tagged
    `fr29-prediction-registered-2026-11-20`);
  - the score, `fr29_desk_score.json`, at de8cfe16;
  - the joint fits, `fr29_desk_variants.json`, made by e91541b3's code.

  Each is beside the script at its revision.
- **Rulings applied:** δ_r and ψ_s were fitted on Fig. 3 (ruling 1), and the ATP-free baseline is
  read as zero (ruling 4).

**The registered prediction.**
- **The fit:** δ_r, ψ_s, ρ, the site pK and one current scale, on panel B's vacuolar pH 6.0 and 4.1
  curves below −5 mV, 28 rows.
- **Committed before panel A was read:** 4531d06d at 23:26 UTC; the score is de8cfe16, at 23:27.
- **The family fails its own training curves:**
  - δ_r comes out at 1.0, the family's bound;
  - the in-sample RMS is 3.1 mA m⁻²;
  - the pH 4.1 curve's fitted reversal is −16.1 mV against −23.2 read.

  That is a failure of the family, not of the data. At −75 mV the pump mode's mass-action backward
  branch falls 9 mA m⁻² below the reading (−46.5 against −37.5).
- **Panel A, scored by the record's own rules:**

  | Curve | Shape | Reversal |
  | --- | --- | --- |
  | 5.0/5.0 | passes | no crossing, met |
  | 6.0/5.0 | passes | +4.5 mV off, passes |
  | 7.5/5.0 | fails (RMS 7.1 against 6.1) | +12.1 mV off, fails |
  | 8.5/5.0 | fails | −1.6 mV off, passes |

  Of the bounds, pH 3.1 fails (+3.5 mV predicted) and both zero-gradient bounds are met.
- **Seen before:**
  - Panel A's reversals shaped the family, so its reversal scores are in sample in that sense.
  - Its curve shapes were not seen, apart from the facts the reading's README states: the meeting
    points, the values near +60 mV, 12.2 mA m⁻² at 0 mV for 7.5/5.0, and the zero-gradient curves'
    lowest readings. One reversal slope was also seen.
- **The comparator:** reversals are scored against the curves' read crossings. Table 2's means
  stand beside them, 2.0 to 4.7 mV more negative.

**The joint question: can any member fit the curves and the pH 3.1 bound together?** No, and
neither can any of three minimal changes.
- **The fits:** all 122 reliable rows at once. That is panel A from −75 to +20 mV without its
  ambiguous rows, and panel B below −5 mV, with the −80 mV ends left out.
- **Each model** is fitted from the same 24 starts, free and then with the bound imposed (the
  current at +40 mV at pH 3.1 held at or below 0).
- **The run:** e91541b3's code; the record is the evidence folder's `fr29_desk_variants.json`.
- **Scoring:** each fit's seven reversals are scored against the curves' read crossings, within
  2 Table 2 SE (±2 mV for 7.5/4.1, ±6 for 6.0/5.0). The two zero-gradient curves must not cross
  above −80 mV.

| Model | Free: RMS (mA m⁻²) | Free: reversals passed | Free: pH 3.1 crossing (mV) | Bound imposed: RMS | Bound imposed: reversals passed |
| --- | --- | --- | --- | --- | --- |
| The family | 4.3 | 5 of 7 | +2.2 | 7.5 | 2 of 7 |
| A second site | 3.4 | 6 of 7 | +2.1 | 4.5 | 4 of 7 |
| A pump voltage law (the pump mode's own bounded term) | 3.5 | 7 of 7 | +0.9 | 7.0 | 4 of 7 |
| Variable coupling (n levelling off with ΔpH, the pump's voltage law, no return) | 7.7 | 4 of 7 | +34.8 | 7.8 | 4 of 7 |

- **The bound is never quite met.** Each bound-imposed fit reaches only its edge, crossing at +39.7
  to +39.9 mV.
- **The family free:**
  - It misses 6.0/5.0 at −70.7 mV against −55.1 read.
  - It misses 7.5/4.1 at −20.9 against −23.2. That is the in-sample failure again.
- **The family with the bound:** its 7.5/5.0, 8.5/5.0 and 7.5/4.1 reversals move to +29 to +36 mV,
  against −16 to −31 read.
- **A second site:** its RMS of 4.5 with the bound hides three failures:
  - 6.0/5.0 lands at −177 mV against −55;
  - the zero-gradient 7.5/7.5 curve crosses at −75 mV, breaking its bound;
  - 7.5/4.1 lands at −13.6 against −23.2.

  So it does not fit both. The earlier version of this section said it did, from RMS alone, and
  was wrong.
- **A pump voltage law fits the curves best of all.** All seven reversals pass, the in-sample
  7.5/4.1 miss among them (−21.4 against −23.2). Yet it puts pH 3.1 at +0.9 mV.
- **Variable coupling** draws the curves worse, but it puts pH 3.1 nearest the bound when free
  (+34.8 mV).

**What this means.** The curves and the bound pull apart:
- every model that draws Fig. 3's curves puts the pH 3.1 reversal near 0 mV;
- every model held to the bound loses three to five of the seven reversals.

No minimal change to the return mode reconciles them. That would need one of two things:
- **The pH 3.1 condition is not the same system** as Fig. 3's. The bound comes from Fig. 2's
  recordings, not Fig. 3's protocol.
- **Something changes steeply below vacuolar pH 4,** in the pump rather than the return. Examples
  are a coupling ratio that rises again (the authors' own linear fit, n = 4.9 − 0.69 ΔpH, gives
  1.86 at ΔpH 4.4, where the bound needs more than 2.41), or a change in the enzyme at that pH.

A difference current read at vacuolar pH 3.1 to 3.5 under Fig. 3's protocol would decide between
them.

**What the curves say about the return mode, in two lines:**
1. A return through the energized pump flattens the reversal's pH dependence as measured. The
   family fitted on panel B moves the reversal 17.1 mV from vacuolar pH 6.0 to 4.1 (−33.2 to
   −16.1), against 12.6 read and 112.5 for tight coupling. With a voltage law on the pump mode as
   well, it draws all seven curves within tolerance.
2. No form tested fits those curves and the pH 3.1 bound together, so the bound is either a
   different system or a change below vacuolar pH 4 that a return mode does not supply. A curve
   at vacuolar pH 3.1 to 3.5 should come before any build.
