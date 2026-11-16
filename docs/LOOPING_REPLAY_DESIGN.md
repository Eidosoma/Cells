# Looping replay packages of living cells (FR-11): design

**Status: accepted by the lead with rulings, 16 November 2026 (§9).** Docs only; building follows
the lead's order (§9). It is the design note FR-11 asks for when the run-view writer lands
([FEATURE_REQUESTS](FEATURE_REQUESTS.md#fr-11--looping-replay-packages-of-living-cells-for-the-viewer)),
on the run view's branch (D154, [RUN_VIEW_DESIGN](RUN_VIEW_DESIGN.md)).

**The user's choices (15 November 2026), which this note keeps:**
- loops are periodic: a periodic drive, one period played, its seam checked;
- the human cell is a paced heart cell;
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

**The closure (`closes.within`)** is measured by the writer on the saved arrays, never declared:
- **Which records:** every record of kind `level`, `amount` or `rate`. Cumulative totals are left
  out, because they grow by design; the reader differences them inside the loop only.
- **The measure:** for each record, |x(t0 + T) − x(t0)| / max over the loop of |x|, with a declared
  floor where a record is identically zero.
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
  "closes": {"within", "says", "tolerance"}, "follows"?}`.
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

## 5. The paced human heart cell

- **What @3 has:** `nav1p2_m3h_regularized@1`, `kir2p1_mh2@1` (an IK1-like inward rectifier),
  `kv1p5_mh@1` (IKur-like), leaks, the Na/K pump and a Ca pump. These are D155's generic
  excitable cell (M1 and M2, accepted narrowly, D170). It has no L-type Ca channel, no hERG or
  KCNQ1, no NCX and no Ca release, so it has no plateau.
- **Options:**
  - **(a) Now: a paced generic excitable cell.** D155's generic cell (0.01 F/m², candidate A),
    paced at 1 Hz by `electrode_current_injection@1`. It is labelled "a paced excitable cell
    with generic laws (illustration), not a human cardiomyocyte model". The engine models are
    `resolved_pump_composite@1` over `resolved_pump_tissue@3` with D155's laws
    (`nav1p2_m3h_regularized@1`, `kir2p1_mh2@1`, `kv1p5_mh@1`, `kleak_always_open@1`,
    `naleak_always_open@1`) and the Na/K pump, plus `electrode_current_injection@1`.
  - **(b) Later: cardiac laws as general laws.** Nav1.5, CaV1.2, hERG (IKr), KCNQ1/KCNE1 (IKs),
    Kv4.3 (Ito), NCX and a Ca release unit. Each is a law with provenance (published human
    ventricular models, for example O'Hara–Rudy 2011 and ToR-ORd 2019, cited, never copied)
    and its own milestone, tests and tier gate. A human ventricular cell definition then uses
    them. This is substantial work.
  - **(c) A phenomenological action-potential model:** rejected. It has no ions, so there are no
    conserved totals to feed the beads (D144, D142).
- **Recommended:** (a) as the interim heart package, and (b) when the user wants a human heart
  cell proper, as its own track.

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
3. **The paced heart cell (a)** (§5): about 0.5 agent-day on the same machinery.
4. **The minimal cell's cycle** (§6): the probe first (about 0.5 agent-day). Then about 1
   agent-day if the composite admits the composition, plus the growth law's own milestone if
   the probe confirms the refusal (§6).

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
5. **The cycle: the probe first,** with nothing built until it passes.
6. **`validation/replay/`** holds the drivers and builders; outputs go under
   `/mnt/workspaces/Cells/replay-<date>/`.

**Order:** after run-view-d154's tier rows, its cut-off I/O tests and a tier-1 gate (at the CPU
release), the loop block and the planarian loop, then the heart cell (a), then the cycle's probe.
