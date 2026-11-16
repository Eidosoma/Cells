# Looping replay packages of living cells (FR-11): design

**Status: ruled by the lead on 16 November 2026 (§9), with the human loop amended by D183 the
same day (§5).** Docs only; building follows the lead's order (§9). It is the design note FR-11
asks for when the run-view writer lands
([FEATURE_REQUESTS](FEATURE_REQUESTS.md#fr-11--looping-replay-packages-of-living-cells-for-the-viewer)),
on the run view's branch (D154, [RUN_VIEW_DESIGN](RUN_VIEW_DESIGN.md)).

**The user's choices (15 November 2026), which this note keeps:**
- loops are periodic: a periodic drive, one period played, its seam checked;
- the human cell is a paced heart cell: since D183 (16 November), a human ventricular cell on
  Track E's human cardiac law set, with no generic stand-in;
- for Syn3A and *M. pneumoniae*, one cell cycle is in scope as a loop: grow, divide, follow one
  daughter (an illustration, since division is prescribed);
- the interim planarian loop comes first, once the run-view writer can carry it.

**What the viewer's loop reader requires** (the visualizer's "What a species' looping run must
carry", on its branch at cf11924a). It refuses a run as a loop unless:
- the view has a `loop` block, `{"species", "cell", "closes": {"within", "says"}}`;
- the run names its engine models and its revision;
- the run is a real run, not an example;
- the totals that feed its rates carry their kind and sign: each channel population's transfers,
  the pump's cycles with what one cycle moves, and the membrane's own transfers.

## 1. What a package is

- **One real run, one period.** A package is a short engine run of laws the engine has. It is
  written by a shared output path with its view (`view=`), from a frozen snapshot. It covers
  exactly one period of a periodic state, so its first observed row and its last fall on the
  loop's two ends.
- **An illustration, never an experiment.** It runs at a declared low level of detail (D175): lumped
  cells, reduced laws. Its label says "illustration". It carries no verdict and is not registered.
- **Small.** About 1 MB per run at most (the viewer's limit). A recording subset (fields,
  elements, cadence; requirement 1) keeps it there, and the view records the subset.
- **Its definition is biological, not an engine mechanism.** Each species' cell definition is a
  builder in `validation/replay/` (ARCHITECTURE: biological definitions apart from engine
  mechanisms). One generic driver writes every package. Nothing species-specific enters
  `src/cells` (D144).

## 2. How a loop is made

**The periodic drive** comes from operators the engine already has. Each schedules piecewise
constant values at exact multiples of dt, so a periodic schedule is just a repeated one:
- `electrode_current_injection@1`: a current train (pacing);
- `scheduled_bath_composition@1`: bath doses (a periodic ion or nutrient step);
- D150's schedules (`scheduled_species_turnover@1`, `scheduled_species_exchange@1`): rates.

**The transient, then one period.** The driver runs k periods from the definition until the
response repeats. From the checkpoint at the end of period k it writes one more period through
`io.write_run` (or `window_io.write_windowed_run`) with `view=`. Checkpoint continuity (D153)
already supports that continuation. The first observed row is at t0 and the last at t0 + T.

**The closure (`closes.within`)** is measured by the writer on the saved arrays, never declared
(the two rules below are the lead's ruling of 16 November 2026, §9 ruling 7):
- **Which records:** every observed record of kind `level`, `amount` or `rate`, less the
  diagnostics: rates and amounts at the same phase of a periodic state return to their values.
  Two groups are left out, and the block names their records under `not_measured`, each group
  with its reason:
  - cumulative totals, which grow by design (the reader differences them inside the loop only);
  - diagnostics, the residuals of the step's own checks (in @3: `charge_residual_C`,
    `component_current_residual_A`, `energy_balance_pJ_s`), which sit at rounding level and are
    held to their own absolute tolerances. Each owner declares its own (the operator contract's
    `RECORD_DIAGNOSTICS`, which the inner model declares in the same form).
- **The measure, per record:** |x(t0 + T) − x(t0)| / max over the loop of |x|. No per-unit
  scale: it would hide a small species' failure to close behind a large species' magnitude (Ca²⁺
  against K⁺, both in fmol).
  - A record stored as an increment over a fixed reference (`amount_increment` over
    `amount_reference`; the contract's `RECORD_REFERENCES`, {increment field: reference layout
    field}) is measured as reference + increment, against that amount's own largest magnitude.
    The reference comes from the bound layout (a constant of the view), or from its merged view
    record where door S changes it.
  - A record identically zero over the loop is named in `closes.zero`, never divided by.
- **What is stated:** `within` is the largest of these. `says` is a sentence the page may show,
  naming the record that attains it, for example "the last record meets the first within 3e-7
  (largest in observed_membrane_voltage_V)".
- **Refusal:** the caller declares a tolerance. Above it the writer refuses the loop block, so a
  run that does not close is never labelled a loop.

## 3. What the writer adds (`src/cells/run_view.py`, host only)

- **`run_view.Loop(species, cell, period, tolerance, follows=())` in the Request.**
  - `species` is the caller's label: the viewer's ids are its own, and the engine checks only that
    it is a non-empty word.
  - `cell` is a declared cell id.
  - `follows` is for a cycle (§6): `({"time", "from", "to"},)`, the cell the loop follows after a
    division. The visualizer's schema would need to accept this field.
- **The `loop` block in the view:** an optional top-level key, `{"species", "cell", "period",
  "closes": {"within", "says", "tolerance", "zero"}, "not_measured": [{"why", "records"}],
  "follows"?}` (`zero` and `not_measured` from ruling 7).
- **The writer's checks before it writes the block:**
  - the observation base starts at t0 and ends at t0 + T exactly;
  - `within` ≤ tolerance;
  - the run names its engine source (`run.source`, from the execution snapshot), so a run from a
    checkout or an example is refused;
  - the bead totals are recorded with their kind and sign (they are, for @3: `channel_transferred`,
    `pump_cycles` with the membrane set's per-cycle rows, `membrane_transferred`).
- **The revision.** The reader reads `run.revision`; the writer states the engine's revision in
  `run.source.revision`. One of the two must change (§8, question 2).
- **The reader's check** validates the block's shape. Nothing else in the engine changes: no
  program, binding, definition field or checkpoint.

**As built (16 November 2026, run-view-d154).**
- `run_view.Loop` sits in `Request.loop`. These are refused before any output, with nothing
  written:
  - a species that is not a word, or a cell that is not declared;
  - a period or tolerance that is not finite and above zero;
  - any `follows` (the cycle's, after its probe), or a batch's world;
  - a run that names no engine source;
  - a recording subset that leaves out `LOOP_TOTALS`.
- `loop_closure` measures the closure on the saved files, one at a time, as the view is written.
  The block is written only when the observed rows span the period (1e-9 relative) and `within`
  is at most the tolerance. Otherwise it is left out, and the view says why under `unstated`.
- The reader's check measures the closure again from the files.
- Records state `diagnostic` (their owner's `RECORD_DIAGNOSTICS`) and `reference` (a constant of
  the view, or the merged view's record). An increment's fixed reference that is not already a
  view field is a named constant of the view.
- @3's own `RECORD_DIAGNOSTICS` and `RECORD_REFERENCES` are the core owner's, in its view
  declarations. Until they reach this branch, the tests plant them on a fixture inner model.
- The driver and the planarian builder are in `validation/replay/` (§4).

## 4. The interim planarian loop (first)

- **World:** a seven-cell patch of the planarian sheet (`validation/stationary/worlds.py`: the
  E07 sheet's cell and junction, `hexagon(1)`). The builder's hexagons are passed as the view's
  geometry, which is prescribed. It has junctions, so the junction voltage's convention gets its
  first data check. One cell alone is the fallback if the patch's size or closure fails.
- **Drive, two options:**
  - **(a) A slow current train** into the centre cell (`electrode_current_injection@1`, for
    example 0.5 Hz, small enough to stay subthreshold): a periodic voltage, channel and pump
    response spreading over the junctions.
  - **(b) A periodic bath K+ step** (`scheduled_bath_composition@1`): every cell depolarizes and
    recovers, and the pump's cycles rise and fall.
  - Recommended: (a). It needs no new species identity and gives the junctions a gradient.
- **Engine models:** `resolved_pump_composite@1` over `resolved_pump_tissue@3`, with the sheet
  cell's laws as `sheet_definition` declares them (`nav1p2_m3h_regularized@1`, `kir2p1_mh2@1`,
  the Na/K pump `nak_atp_mass_action_positive@1`, junctions `junction_voltage_relaxation@1`), and
  with `electrode_current_injection@1`.
- **The cell is bistable** (the cue-written sheet: two stable voltage states). The drive stays
  below the switching threshold, so the loop shows a cell held in its written state under a slow
  drive. A drive that writes the other state would not close.
- **Gaps:** the injection operator has no run-view declarations yet. It needs its `VIEW_LAYERS` and
  its `view_events` (the pulses, at their cell); both are pending in the contract test's lists and
  belong to the operator's owner.
- **Size:** seven cells, T = 2 s, observed every 10 ms: about 200 rows, well under 1 MB with the
  layers' fields.

## 5. The paced human heart cell (amended by D183)

**D183 (the user, 16 November 2026).** Track E's human cardiac law set is brought forward as its
own lane, design first. FR-11's human loop is a paced human ventricular cell built on that law
set. It has no generic stand-in, and it waits for those laws. This replaces option (a) below,
which the lead had ruled for now earlier the same day (§9, ruling 4).

- **Why @3's laws give no human cell:** @3 has `nav1p2_m3h_regularized@1`, `kir2p1_mh2@1` (an
  IK1-like inward rectifier), `kv1p5_mh@1` (IKur-like), leaks, the Na/K pump and a Ca pump. These
  are D155's generic excitable cell (M1 and M2, accepted narrowly, D170). It has no L-type Ca
  channel, no hERG or KCNQ1, no NCX and no Ca release, so it has no plateau.
- **The options, as they now stand:**
  - **(a) A paced generic excitable cell: dropped by D183.** It was D155's generic cell (0.01
    F/m², candidate A), paced at 1 Hz and labelled "not a human cardiomyocyte model".
  - **(b) Cardiac laws as general laws: chosen, as Track E's lane** ([excitable tissue
    design](EXCITABLE_TISSUE_DESIGN.md) §3.3, §7, and M4 and M5 in §11). The lane adds what @3
    lacks for a plateau and repolarization, each a general law named by its mechanism (D144),
    cited, with its own tests and the tier gate. Its design note puts the options to the user
    first: the source of equations and parameters (O'Hara–Rudy 2011, its ToR-ORd successor, or
    ten Tusscher–Panfilov 2006; cited, never copied), the cell types, the sodium current's form,
    the temperature and the verification. No engine code is written before the user chooses.
  - **(c) A phenomenological action-potential model:** rejected. It has no ions, so there are no
    conserved totals to feed the beads (D144, D142).
- **What FR-11 adds once those laws land:** a builder in `validation/replay/` for a human
  ventricular cell definition on the law set, paced by `electrode_current_injection@1`, through
  the same generic driver and loop block (§2, §3). Its cell type, pacing cycle length (the loop's
  period) and temperature follow the lane's note. Its engine models are the composite over the
  inner model D172 lands, the law set's laws and the injection operator, named in full when it is
  built. FR-11 designs and builds none of the laws.
- **The lane's gates stay its own:** a whole-cell action-potential comparison against a published
  model needs the user's approval (D138, D151), which the lane's note asks for.

## 6. The minimal cells' cycle (Syn3A, *M. pneumoniae*)

- **The loop:** one cycle. The mother grows, divides at T (prescribed: `isopotential_partition@1`,
  S5) and the loop follows one daughter. The seam compares the daughter at T with the mother at 0.
  Because the loop's cell changes at T, the block carries `follows: [{"time": T, "from":
  "cell_0", "to": "d1"}]`.
- **Growth from general laws:**
  - production of an osmolyte and of the ions' share, by `scheduled_species_turnover@1`;
  - volume following it, by `ideal_osmosis_linear_compliance_water@1`;
  - membrane area following it, through the membrane entity state or insertion.
  - The rates are set so the cell doubles in T, which lets the daughter at T meet the mother at 0.
- **Engine models:** `resolved_pump_composite@1` over `resolved_pump_tissue@3`, with
  `isopotential_partition@1`, `ideal_osmosis_linear_compliance_water@1`,
  `scheduled_species_turnover@1`, and `membrane_entity_state@1` or
  `scheduled_membrane_insertion@2`.
- **Expected to be refused today.** D150's operators hold the volumes and the activity masks as
  declared (`species_common.CONFLICTS_VIEW`: `volume`, `extracellular_volume`, `active`,
  `outside_active`, `membrane_active`; a `fixed` read in door S's terms). So turnover is refused
  beside water (a volume provider) and beside the partition (a closer). Growth by production
  therefore needs an engine feature first: a production law that reads the current volume, with
  its own bookings (a `current` reader, door V; D150 §5.1's fallback). That is a general feature
  (D144), not a driver workaround, and the cycle's estimate below is conditional on it.
- **To check first, with a cheap host-side probe:**
  - which compositions the composite admits: the partition beside water and the area law (door
    S's admissions; the padded-field rule), and the refusal above, stated by the engine;
  - how many divisions one world's slots allow (one is enough for a loop).
  - An engine gap found here becomes a general feature, not a workaround in a driver.
- **The organisms:** neither has an organism definition yet (D173). The package is "a lumped
  minimal cell from the engine's general laws (illustration)" for both, and differs only in its
  declared sizes and rates until their definitions exist.

## 7. Order and cost (S, our estimate)

1. **The writer's loop block** (§3), its tests and a tier row: about 0.5 agent-day. It needs a
   synthetic periodic world for the closure tests, for example a passive cell under a current
   train.
2. **The interim planarian loop** (§4): about 1 agent-day, plus the injection operator's view
   declarations from its owner.
3. **The minimal cell's cycle** (§6): the probe first (about 0.5 agent-day). Then about 1
   agent-day if the composite admits the composition, plus the growth law's own milestone if
   the probe confirms the refusal (§6).
4. **The paced human ventricular cell** (§5): it waits for Track E's human law set (D183). Once
   those laws land, FR-11's part is about 0.5 agent-day on the same machinery; the laws are the
   lane's work.

Every package run is a development run from a snapshot, written with its source and
`closes.within`. Each runs at most a few minutes on one CPU core.

## 8. For the lead

1. **The loop block** (§3): its fields, the writer-measured closure, and the refusal above a
   declared tolerance. Is `follows` acceptable to put to the visualizer for the cycle?
2. **The revision.** Should the writer fill `run.revision` from `run.source.revision` when the
   caller gives none, or should the viewer read `run.source.revision`?
3. **The planarian drive:** (a) a current train, or (b) a bath K+ cycle (§4)? And the injection
   operator's run-view declarations: ask its owner now?
4. **The heart cell:** (a) now, labelled generic, with (b) as a later track (§5)?
5. **The cycle:** run its admission probe first (§6), with no build until it passes?
6. **Where drivers live:** `validation/replay/` for the builders and the one generic driver,
   with run outputs under `/mnt/workspaces/Cells/replay-<date>/`?

## 9. The lead's rulings (16 November 2026)

1. **The loop block** is accepted, with `closes.within` measured by the writer and the three
   refusals. The lead proposes `follows` to the visualizer as a schema addition.
2. **One source of truth for the revision:** the viewer reads `run.source.revision`; the writer
   does not copy it into `run.revision`.
3. **The planarian drive is the subthreshold current train** (`electrode_current_injection@1`).
   The run view's owner adds the injection operator's `VIEW_LAYERS` and `view_events`, as their
   own commit with tests (no owner is active on that file this round).
4. **The heart cell is (a) now:** D155's generic excitable cell paced at 1 Hz, labelled "not a
   human cardiomyocyte model". **(b) is Track E's work** (cardiac channel laws as general laws with
   provenance: the plan's M4 and M5), not FR-11's. A phenomenological model stays rejected.
   **Amended the same day by D183 (the user):** (a) is dropped, with no generic stand-in. Track
   E's human cardiac law set is brought forward as its own lane, and FR-11's human loop is a
   paced human ventricular cell on it, which waits for those laws (§5). The laws stay Track E's.
5. **The cycle: the probe first,** with nothing built until it passes.
6. **`validation/replay/`** holds the drivers and builders; outputs go under
   `/mnt/workspaces/Cells/replay-<date>/`.
7. **The closure's records and measure (later the same day):**
   - **The measure stays per record.** There is no per-unit scale.
   - **What is measured:** records of kind level, amount and rate, less the declared diagnostics.
   - **What is left out:** cumulative records and diagnostics. The block names them under
     `not_measured`, with the reason.
   - **Increments:** a field stored over a fixed reference is measured as reference + increment.
   - **Zero records:** a record identically zero is reported, not divided by.
   - **The two declarations are general:** `RECORD_DIAGNOSTICS` and `RECORD_REFERENCES`, in the
     operator contract. The core owner declares @3's (and any kind's) in its view declarations on
     core-next. The run view's owner adds the contract's names and the writer's reading of them.

**Order (as amended by D183):** after run-view-d154's tier rows, its cut-off I/O tests and a
tier-1 gate (at the CPU release), the loop block and the planarian loop first, then the cycle's
probe. The human loop follows when the human law set lands.
