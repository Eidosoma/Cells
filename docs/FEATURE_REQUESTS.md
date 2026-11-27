# Feature requests

Requests for engine features from the user or from studies the user runs, with their priority, the
lead's mapping to the existing plan, and their status. Each becomes a design note before code (D142)
and a general feature, never one built for one study (D144).

| ID | Feature | Priority | Status | Next step |
| --- | --- | --- | --- | --- |
| [FR-1](#fr-1--a-closed-internal-compartment-on-the-shared-inventory) | A closed internal compartment on the shared inventory | **High** (user, 14 November 2026; the request's own label: priority 1, blocking) | **Milestone 1 landed** (15 November; [note](CLOSED_COMPARTMENT_DESIGN.md) §12, D169): `cell_owned_compartments@1`, neutral and silent, S1–S5 checked in a live-owner world with planted controls. **Judged, 18 November 2026:** its protocol, `fr1-closed-compartment-v1` (registration 05a8d193), passed, 44 of 44 judged criteria, against the code-blind references; exchange's first judged acceptance | The later doors (creation, division, fission and fusion, retirement) with seam B: none found on main (unverified). A releasing compartment is admitted in a U2 world (merge a798e7e0, FR-7 item 3); the mitochondria work is paused (D268) |
| [FR-2](#fr-2--internalisation-of-membrane-and-its-populations) | Internalisation of membrane and its populations | Priority 2 (the request's label; logged by the user, 14 November 2026) | **Version 1 landed** (19 November; `scheduled_membrane_trafficking@1`, merge 1bd35184; D217), with its comparison against code-blind references on main (merge d2dc7b8c). The first registered run matched 770 of 782 rows. A second run matched 782 of 782 after a blind references erratum, which is weaker evidence after the failed first run (PROGRESS's run entry); the one-pool-per-cell refusal landed (fa0a78aa, merge 560da6a0) | The charge-transfer precision note for the declared-freeze numerics batch (unverified); later versions per its design note |
| [FR-3](#fr-3--the-site-occupancy-primitive) | The site-occupancy primitive | Priority 2 (the request's label; logged by the user, 14 November 2026) | **Milestone 1 landed** (15 November; [note](SITE_OCCUPANCY_DESIGN.md) §12, D169): `site_occupancy@1`, the contract fit and the run, with idle, restart, batch and controls. **Judged, 18 November 2026:** its protocol, `fr3-site-occupancy-v1` (registration 1b838d75), passed, 51 of 51 judged criteria, against the code-blind references; `site_occupancy@1`'s first judged acceptance | A shared SSPRK(3,3) block, FR-3's own milestone (INNER_MODEL_V4_DESIGN §15.3; main still has separate integrators in `site_occupancy.py` and `species_reactions.py`) |
| [FR-5](#fr-5--state-conditioned-transfer-across-an-internal-membrane-with-leak-and-reseal) | State-conditioned transfer across an internal membrane, with leak and reseal | Priority 1, blocking (the request's label; logged 14 November 2026). It depends on FR-1 and FR-4 | Design accepted (§16 of [the FR-4/FR-5 note](COMPARTMENT_PH_TRANSFER_DESIGN.md)). Built and on main since fr45-next merged (16 November): the two source kinds, refusal 4 version 1.2, refusal 5 version 1.1 and FR-5's start part, for development, not judged. Its protocol, `fr5-transfer-v1`, is registered and judged on 17 November 2026: passed, 51 of 51 judged criteria (D195; tag fr5-v1-qualified-2026-11-17) | Done. The verdict's scope: `cell_owned_compartments@1` as built at 32a1d439 (refusal 4 v1.2, refusal 5 v1.1) |
| [FR-6](#fr-6--species-driven-control-factors) | Species-driven control factors | Priority 2 (the request's label; logged 14 November 2026) | **Addressed by an accepted design (D155, D156; [the coupling note](INVENTORY_COUPLING_DESIGN.md)). Its operator, `species_regulated_availability@1`, is numerically qualified (15 November).** Three narrower items are recorded as consumer registrations. **A5″ judged, 18 November 2026:** its protocol, `fr6-a5pp-v1` (registration 555d8771), passed, 18 of 18 judged criteria, against the code-blind references: the gate-free channel target (item 1) driven through the regulatory state from a per-cell prior (item 3) **Item 2, the routing door, landed as B1′** (merge ee43b082, tag `b1prime-landed-2026-11-19`, on `species_regulated_availability@2`; development, not judged; D218) | B1′'s judged acceptance (none found: unverified); gated channel populations (A5′), leaks and pumps (item 1's rest) |
| [FR-7](#fr-7--abundance-to-function-exposed-in-the-composite) | Abundance-to-function, exposed in the composite | Priority 3, ordering and not scope (the request's label; logged 14 November 2026) | Items 1-3 judged and passed on 20 November. **Item 4's registered test (Maverick and Tamkun 2022) scored inconclusive** (D275): d = −0.381, 95% [−0.656, −0.105] against ±0.223; the direction agrees with the paper | Item 4 open: more paired cells, or a declared conducting-fraction law with its own registered test on unused data. No build now (D273's hold) |
| [FR-8](#fr-8--a-qualified-long-duration-mode) | A qualified long-duration mode | Priority 2 (the request's label; logged 14 November 2026) | **Stage 0 landed** (19 November, merge f5025e6f: the methods measured, the harness H2). **Rung 0** (the order drop through a switch) is registered and run: its first verdict was "instrument not validated"; under a blind amendment the cause is NaV activation unresolved at coarse steps, with R3's error now estimated (D224's ladder; landing). **Rung 1's C judged and passed** (20 November, tag `fr8-c-judged-2026-11-20`) Section 10.20's registered reading, N2 with C at a 100 ms step, passed (a), (b) and (c) on 21 November, re-judged independently (80de0788, tag `fr8-n2c-judged-2026-11-21`). | Rung 2. C's near-event refusal for windowed clocks landed (c65dbfa5); extending it to clocks without windows waits on a scan of the registered worlds (D280) |
| [FR-9](#fr-9--raise-the-7-species-cap) | Raise the 7-species cap | Priority 2, **blocking for world design** (the request's label; logged 14 November 2026). Measured safe to 16 (the W4 probe) | **Landed** (14 November): `MAX_SPECIES` is 16, a D148 change to `species_common` with guard worlds of 8 or more species (D165) | None: closed (D165, merge 2161f39); the requester's species list comes with its world definition (unverified) |
| [FR-10](#fr-10--a-dose-schedule-scheduled-bath-composition-in-the-pump-family) | A dose schedule: scheduled bath composition in the pump family | Priority 2, small (the request's label; logged 14 November 2026) | **Milestones 1 and 2 landed** (14–15 November; [note](BATH_SCHEDULE_DESIGN.md) §7–§8, D169): dose steps admitted only inside measured regions (neutral up and down, K up and Na down). Its protocol, `fr10-dose-schedule-v1`, is registered and judged on 17 November 2026: passed, 31 of 31 judged criteria (registration 407ba164), against the code-blind references R-faces, R-ion and R-records | Further ions and faster faces as each is measured |
| [FR-4](#fr-4--compartment-ph-a-proton-species-an-acidifying-pump-buffering) | Compartment pH: a proton species, an acidifying pump, buffering | Priority 1, blocking (the request's label; logged 14 November 2026). The request sequences it last of the block, after FR-1 | Design proposed in [the FR-4/FR-5 note](COMPARTMENT_PH_TRANSFER_DESIGN.md) (merged 15 November). Its kinds landed with D172's round (16 November), for development, not judged: the transporter with the proton pump, the rapid proton buffer, and the passive routes with the proton leak | Done: `fr4-acidification-v1` judged on 17 November 2026: passed, 21 of 21 judged criteria (D195; tag fr4-v1-qualified-2026-11-17) |
| [FR-11](#fr-11--looping-replay-packages-of-living-cells-for-the-viewer) | Looping replay packages of living cells for the viewer | Not stated (the user's request, logged 15 November 2026) | **Partly built** (on main since 16 November): the design note (`docs/LOOPING_REPLAY_DESIGN.md`), the run-view writer's loop block with its closure measure (merge 358c8c20), and the planarian loop's builder (`validation/replay/`), played by the viewer (7e20af42); a development run, not judged. The user's choices (periodic loops; a paced human ventricular cell on Track E's human law set, D183, D184; the minimal cells' cycle in scope) stand | The human loop waits for the human cardiac laws (none in `src/`: grep, 21 November). The minimal cells' cycle: its admission probe was not passed (5dbad635), four operator-composition gaps queued (759f907f); later status unverified |
| [FR-12](#fr-12--the-declarations-manifest-readable-by-the-viewer-d185) | The declarations manifest, readable by the viewer (D185) | Not stated (proposed by the visualizer session, 16 November 2026; logged 17 November) | **Landed:** `python -m cells declarations` writes the manifest (0154604f; merge 515ac020, seam F, D195). `cells.declarations@2` (merge 3891b802, D203) is the format in the engine (`FORMAT` in `registry/declarations.py`) and is read by the viewer (merge d8c56ea2) | None for the manifest; the command's help text still names @1 (a stale string, not fixed here) |
| [FR-13](#fr-13--molecular-machines-individually-and-in-aggregate) | Molecular machines, individually and in aggregate, at a level of detail set by what is looked at | Not stated (the user's request, 17 November 2026; D204) | No machine model of FR-13's own yet (D209). **M0 done:** the viewer's catalogue (40317ef7, illustration). M1's ATP synthase: the mitochondria lane's inner-membrane laws on the cycle kind include a synthase (64565faa, development, not judged), and that lane is paused (D268) | M1's build plan ([the design note](MOLECULAR_MACHINES_DESIGN.md) §10) when the mitochondria lane resumes; U4 and U6 open (D209) |
| [FR-14](#fr-14--declared-extension-of-laws-operators-and-models) | Declared extension of laws, operators and models (object-oriented) | Not stated (the user's request, 17 November 2026; D205) | Requested; not scoped. No declared extends link, inherited checks or version rule on main (a search of `src/cells/registry`, unverified beyond that); D205's check stands | Covered by FR-13's design note (U6 open, D209): options for a declared extends link, inherited checks and version rules |
| [FR-15](#fr-15--junction-crossing-and-charged-species-in-the-species-operators) | Junction-crossing and charged species in the species operators | Not stated (found by the gap-junction replication, D207; 17 November 2026) | **Landed in two parts; F2 designed.** S1, charged species in `local_species_reactions@1` (merge ddb52790, tag `fr15-s1-landed-2026-11-19`, D148). P2, `passive_constant_field_permeation@1` on the passive-routes kind, on patches (merge ce39c904, tag `fr15-p2-landed-2026-11-20`). F2, charged trace species on junctions: design note landed (7f3f6ccd, [note](CHARGED_TRACE_SPECIES_DESIGN.md)) and ruled in D310: option A, the charged law hosted on junctions; junctions crossing a floating component refused in version 1; the two-end material term; @1 widened in place | F2's build, A1 (about 2.25 to 2.75 agent-days, gated), at the next free agent slot; charged turnover routes (`scheduled_species_turnover@2`) when a consumer needs them; crossing junctions (A2, +1 to 1.5 days) when one does |
| [FR-16](#fr-16--junction-gating-and-availability) | Junction gating and availability: a two-state voltage gate, per-species floors, two-sided combination rules | Not stated (the same) | Requested; awaits the user's go (D219: not started). **F3 partly met through FR-30:** the series gates (merge 12c18db1: threshold_relaxation and boltzmann_eyring) landed. F4 (a per-species floor) and F5 (min and mean combination): not found on main (unverified) | F4 and F5 unscheduled; F3's held-out voltage test is FR-30's. A short design before any build |
| [FR-17](#fr-17--field-solves-beyond-2048-nodes) | Field solves beyond 2048 nodes | Not stated (the same) | **Stage 1 landed** 24 November 2026 at 8760d5b3 (D317): the sparse field solver `sparse_capacitive_reduction_gauged_damped_newton@1`. The composite's GPU placement closed as failed, and the vector path refuses it (D336, 72893c2a) | GJ-N1's 2D field, running on CPUs (D337); nested dissection for faced worlds follows |
| [FR-18](#fr-18--the-composites-energy-check-at-moderate-step-sizes) | The composite's energy check at moderate step sizes (a finding for the core) | Not stated (the same) | **X2 landed** (merge fd894b91, `step_doubled_energy@1`, D224): an opt-in step-doubled energy check; criterion X registered (570df4fd). The default check is not loosened for one experiment; any review of its default tolerance: unverified | None unless the core reviews the default tolerance or the step-size advice (unverified) |
| [FR-19](#fr-19--the-passive-routes-heat-share-sign-test-at-rounding-level) | The passive routes' heat-share sign test refuses rounding-level shares (a finding for the core) | Not stated (found by the gap-junction replication, D207; 17 November 2026) | **Fixed on main** (merge 49494e49): the raw-sum check's rounding floor; previously admitted steps bitwise unchanged. The band near 1 mM is closed too (merge a7122a43, 18 November) | None: closed |
| [FR-20](#fr-20--a-pulse-and-washout-for-assembly-populations) | A pulse and washout: replace an assembly population's exterior at a declared time, with the material and energy exchanged recorded | **High** (user, 20 November 2026; D237) | **Landed** (merge 3af9ce38, tag `fr20-washout-landed-2026-11-20`): `cells.pool_replacement@1`, with Q3 as a declared version-1 limit. A Lean finding (21 November): a fresh count above `molecule_capacity` was accepted and booked with a clamped table (ln 32! for 33) | None. The capacity fix landed (e289dfd9); the D263 tracer-source fix landed (c6f8d60f) |
| [FR-21](#fr-21--a-prescribed-shell-that-owns-a-lumen-and-an-exchange-conductance) | A prescribed shell that owns a lumen and an exchange conductance, independent of membrane inventory and binding-site count | **High** (user, 20 November 2026; D237) | **Landed.** The site step (merge 4fb9922b, tag `fr21-sites-landed-2026-11-21`) and the prescribed shell (merge 41338949, tag `fr21-shell-landed-2026-11-21`: `cells.prescribed_shell@1`, `cells.shell_permeation@1`, `cells.gate_factor@1`). The requester's tested revision is 9a1a95a5 | None; follow-ups on request |
| [FR-22](#fr-22--checkpoint-and-resume-for-the-stochastic-assembly-runner) | Checkpoint and resume for the stochastic assembly runner, qualified around a wash | **High** (user, 20 November 2026; D237) | **Qualified around a wash** (landed with FR-21's site step, 4fb9922b): FR-20's `test_a_cut_around_each_replacement_resumes_bitwise`, with a redo-or-skip plant. Rung P landed earlier (99770fce) | None |
| [FR-23](#fr-23--timed-bath-changes-beside-binding-sites-on-distinct-finite-nodes) | Timed bath changes beside binding sites on distinct finite nodes | **High** (user, 20 November 2026; D239) | **Built (development, D244), landed 4e3d1899:** `site_occupancy@1` beside the bath schedule by scoped reads, and the trace rule on scheduled compositions | A dose into a finite compartment is not covered (FR-27) |
| [FR-24](#fr-24--binding-site-occupancy-as-an-input-to-reaction-rates) | Binding-site occupancy as an input to reaction rates | **High** (user, 20 November 2026; D239) | **Landed** (merge 260e2ed5, tag `fr24-fr27-fr26-landed-2026-11-21`): `site_occupancy@1`'s readable quantities and @2's site source, through the contract's R3; junction targets refused in version 1 | None |
| [FR-25](#fr-25--a-reusable-one-gene-expression-unit) | A reusable one-gene expression unit, verified against independent references | **High** (user, 20 November 2026; D239) | **Final verdict: inconclusive under the registered rule** (D282): 30 of 32 worlds-by-set pass against G2, none failed; A1, the induction-and-decay world, stays inconclusive (one readout's order never settled) | The registered sequence is spent; a further test of A1 needs a new registration, disclosed as after the results (the user's call) |
| [FR-26](#fr-26--owned-state-when-a-cell-is-replaced) | Owned state when a cell is replaced: the incoming cell from its template, environment-owned material kept, departing material recorded | **High** (user, 20 November 2026; D239) | **Landed as W** (merge 87f1ebef, the same tag): `site_occupant_replacement@1`, D152's occupant rule and @2's C′; an occupancy within 4 ulps of empty or full is refused (the trace convention) | None for version 1 (W landed). L, one lifecycle shared with division, is not now (D268): designed with its first division consumer |
| [FR-27](#fr-27--a-timed-partial-wash-of-a-finite-compartment) | A timed partial wash of a finite compartment: collect a fraction of its liquid into a recorded sample, refill with a declared buffer, leave bound material in place | **High** (decided by the lead with the advisor under the user's delegation, 20 November 2026; D245) | **Landed** (merge 5fc1364f, the same tag): `scheduled_compartment_wash@1` | None |
| [FR-28](#fr-28--binding-sites-owned-by-a-compartments-surface) | Binding sites owned by a compartment's own surface, such as a vessel wall, with no cell | Normal (D245) | **Landed** (72274a53, tag fr28-node-sites-landed-2026-11-22): a node owner `{"node": N}`, counts as for every population, checker-accepted on the merged head; the wash-timing docs clarified (6b28ec55) | None |
| [FR-29](#fr-29--an-optional-proton-return-mode-for-atp-driven-proton-pumps) | An optional proton-return mode for ATP-driven proton pumps, tested on the yeast vacuolar pump | Normal, started first of D248's four (D248) | **Investigated, no build (D268).** The return mode failed its registered test, and no form tested fits Fig. 3's curves and the pH 3.1 bound together (D258) | Reopens on a difference current at vacuolar pH 3.1 to 3.5 under Fig. 3's protocol |
| [FR-30](#fr-30--homotypic-cx43-junctions-with-two-relaxation-times) | Homotypic Cx43 junctions with two relaxation times | **High,** inherited from FR-16's connexin catalogue (D225, D249) | The series gates' functions **landed** (merge 12c18db1, tag `fr30-series-gates-landed-2026-11-21`; kind `threshold_relaxation` or `boltzmann_eyring`); not registered. No openly licensed homotypic Cx43 voltage series found | All four registered papers are undetermined (D276, section 13.2); a metadata-only search for a source with two-exponential step decays at four or more voltages is running (D280). Development-only until a benchmark passes |
| [FR-31](#fr-31--vesicle-rupture-during-a-steady-tension-hold) | Vesicle rupture during a steady tension hold: an optional rupture event competing in time | **High** (user, 22 November 2026; D286; was Low, D230, D248) | **Blind test passed (D298):** set 1, 5 of 5 two-sided (3 in range, 2 extrapolated); set 2, 5 of 5 one-sided (weak); wide tolerance, in-sample misfit disclosed. **Phase A landed** (a9a67d06) | FR-39 (pores that open and reseal), now that OL6's deterministic representation and its pore clock have landed (S3, S4; D309) |
| [FR-32](#fr-32--a-dopc-swelling-validation-record-for-the-water-operator) | A DOPC swelling validation record for the water operator | Low (D248) | Requested | Folded into the next water-operator landing |
| [FR-33](#fr-33--regional-labelled-protein-readouts-redistribution-against-degradation) | Regional labelled-protein readouts: inside a measured region, outside it and across the whole cell | High (D228, D248) | **Two-way tracing landed** through D1, label families in the species registry (3c30082e), checker-accepted: redistribution keeps the labelled total and degradation lowers it by exactly the clearance, to rounding; charged log-mean faces refused. Regional readouts and the one-way tracer (ce2a3d9c) with D265's fixes (d48d40dd) | **The requester's first test landed** (7d70d63b, checker-accepted): two named regions joined by one face, with transfer and local-loss control. The in-cell compartment path stays priced (1.5 to 2 days), if a later test needs it |
| [FR-34](#fr-34--channel-population-readouts-count-availability-and-signed-current) | Channel population readouts: surface count, availability and signed current at a declared voltage, with units and sign convention | **High** (user, 20 November 2026; D251) | **Landed, composites included:** opt-in flux and current readouts with fixed-voltage evaluation (81a29442); a composite's own clamped_channel_flux and clamped_kind at the step's control and layout views (07022ddf, D265 finding 1, checker-confirmed) | None |
| [FR-35](#fr-35--timed-partial-withdrawal-of-an-assembly-populations-exterior-pool) | Timed partial withdrawal of an assembly population's well-mixed exterior pool: each molecule withdrawn independently, a declared buffer supplied, sites and particles kept | **High** (user, 21 November 2026) | **Landed** (merge b521a11c, tag `fr35-withdrawal-landed-2026-11-21`): `cells.pool_withdrawal@1` (D261) | None. Landed (b521a11c, with D263's fixes); the independent acceptance and a 4,000-stream ensemble passed |
| [FR-36](#fr-36--age--and-region-selective-loss-within-a-species-row) | Age- and region-selective loss within a species row | FR-25's reviewer (21 November 2026) | **Deferred (D273).** Today's tools cover completion-time cohorts in one well-mixed pool with age-independent loss (cohort.py) and FR-33's regional export and one-way tracer | Reopens on a requester's readout needing age-dependent loss: D1 (label families) and D2 (an ageing operator), 2.5 to 4 days |
| [FR-37](#fr-37--sampling-a-liquid-whose-dye-is-unevenly-distributed) | Sampling a liquid whose dye is unevenly distributed: a draw from chosen parts of an unevenly mixed liquid | **High** (user, 21 November 2026; D274) | **Shown with existing operators** (2bba6043, validation/sampling/uneven_draw.py): per-region wash events; the three cases match, with all 10 fmol accounted for; checker-accepted. Mixing is declared, not simulated (D246), and the sample is a host-side sum | Predicting the per-region split from the port, flow and timing needs an advection operator on faces, with the wash's face refusal lifted (about 3 to 5 days): built only if the requester asks |
| [FR-38](#fr-38--rna-release-from-its-template-into-two-pools-with-different-lifetimes) | RNA release from its template into two pools with different lifetimes, with per-producer accounting, a release-window cohort and explicit measurement denominators | A user (22 November 2026) | **Accepted functionally (D306).** The first registered comparison failed (D313: R1 failed, R2 inconclusive). **The second, registered comparison passes** (D381; tag `fr38-v2-registered-2026-11-25`), judged and independently checked, beside the first's failed verdict; a weaker test than a first-time pass would have been, since its author had read the diagnosis. Landed (4039dcba, D382) | Three readout controls in a later registration, FR-38 v3 (D354) |
| [FR-39](#fr-39--a-vesicle-that-survives-transient-pores) | A vesicle that survives transient pores: repeated opening and resealing with partial cargo loss | **High** (user, via the Lean lane, 22 November 2026; D286) | **Requested.** Cells ends a lineage at terminal lysis | A design note shared with FR-31: tension-driven pore opening that either reseals after leaking or ruptures |
| [FR-40](#fr-40--a-single-ribosome-translation-timing-benchmark) | A single-ribosome translation timing benchmark: 406 s from first detectable nascent chain to release | **High** (user, via the Lean lane, 22 November 2026; D286) | **Desk note landed** (022a5d2a). With only the paper's own speeds, which conflict, a comparison is a calibration, not a validation | A metadata-only search for a matched-condition speed or a multi-length reporter series; the spread test needs no speed |
| [FR-41](#fr-41--vesicle-shrinkage-validation-records) | Vesicle shrinkage validation records for the osmotic lumen law | **High** (user, via the Lean lane, 22 November 2026; D286) | **One agreement, retention open:** shrinkage matches (24.56% against about 25%). The data-only retention check is undetermined for all three sources; the one point estimate (gel-phase LUVs) suggests partial release | Parked until a study with paired, tabulated volume and small-solute retention appears |
| [FR-42](#fr-42--neutral-arrival-time-labels-that-leave-the-dynamics-unchanged) | Neutral arrival-time labels that leave the dynamics unchanged: loss computed once per physical population and shared by label | **High** (a user, 22 November 2026) | **Landed and accepted (D306):** labels as share vectors on the physical row (option A, D289; the label owner, D296), across kinds, pools and sources, with the kinds hook (`label_refusals`, `label_transfers`) | Done for its consumers; FR-38's comparison reads its shares |
| [FR-43](#fr-43--shared-inventories-larger-networks-shared-pools-and-low-count-populations) | Shared inventories: larger sparse reaction networks; one pool spent and replenished by separate processes, at fixed and changing volume; a low-count integer population coupled to continuous chemistry | **Very high** (logged by the user, 23 November 2026) | **All three parts on main (D328):** part 1 (bbc99163), part 2A (c9687d68) and 2B (2ca07dcb), part 3 (7fb0ad87); part 3's registered check passes (D319), and part 2's (D324). Part 1's two gaps landed (14f19f9f, D376), and so did part 3's co-writers engine build (4be34f74, D395); turnover in a swelling cell is FR-65, whose first build landed (ae349721, D398) | Part 3's co-writers: the rehearsal, the registration tag and the registered comparison (the per-event counts landed, D400; the judge's tag is made, D401); the factor-width term (D328) |
| [FR-44](#fr-44--labels-across-a-wash-arrival-time-labels-through-scheduled-compartment-washes) | Labels across a wash: neutral arrival-time labels through scheduled compartment washes | **High** (logged by the user, 23 November 2026) | **Core landed** 24 November 2026 at a6f7a0f4 (tag `fr44-landed-2026-11-24`; D327): the wash reports a typed exchange and the label owner dilutes each label exactly | Admission by species (D327's step 3) |
| [FR-45](#fr-45--several-ligands-competing-for-one-shared-wash-retained-site-capacity) | Several ligands competing for one shared, wash-retained site capacity | **High** (logged by the user, 23 November 2026) | **Registered and bound** 27 November 2026 by the protocol's own tag `fr45-protocol-registered-2026-11-27` (f30b1512, D408). It binds amendment 3, references v2, `agreement.py` and the engine-table contract with its rulings. **Its engine landed** 27 November 2026 at de72e530 (D411), and its tooling at 60b276ef (D415); the registration is on main | The contract's addenda with their confirmations, then the judged run. X2 (D224) is the user's to settle before the judged run. Its washed worlds W2 and W7 hold the wash's retirement (D364) |
| [FR-46](#fr-46--binding-from-a-shells-inner-face-lumen-ligands-on-membrane-sites) | Binding from a shell's inner face: lumen ligands on membrane sites | **High** (logged by the user, 23 November 2026) | **Landed** (merge d702f13a, D323): a site pair declares its face; an inner pair binds a lumen ligand in a prescribed shell; the face rule refuses carriers by name | Inner-face binding stays refused in the deterministic representation until a qualification covers it |
| [FR-47](#fr-47--shell-exchange-and-scheduled-washes-in-the-deterministic-representation) | Shell exchange and scheduled washes in the deterministic representation | **High** (logged by the user, 23 November 2026) | **Landed; the registered comparison passes and the schedule supplement passes separately (D373),** so it is no longer development-only, and its run records say so since D398: `cells.rate_equations@1` runs the prescribed shell, its full and fractional washes, E2's true zeros and autonomous gates in a prescribed shell's world; each is refused by name elsewhere, until a qualification covers it | None: its ledger limit stays as documented, and the alternative is not built (D379, D390) |
| [FR-48](#fr-48--a-lumen-standard-potential-a-reversible-free-energy-difference-across-a-prescribed-shell) | A lumen standard potential: a reversible free-energy difference for one neutral solute across a prescribed shell | **High** (logged by the user, 23 November 2026) | **Landed** (merge d702f13a, D323): an absolute lumen standard potential per species in a prescribed shell, read by every law through the lumen place's standard potential | None open |
| [FR-49](#fr-49--compartment-composition-qualifications-expression-site-occupancy-and-labels-beside-cell-owned-compartments) | Compartment composition qualifications: expression, site occupancy and labels beside cell-owned compartments | **High** (logged by the user, 23 November 2026) | **Parts H and L landed** (merge 7d021548): the gene unit and neutral arrival labels beside cell-owned compartments; World L's registered judgement passes (D331) | World B and the combination checks C1 and C2, after FR-49's site pairing (following FR-45) and its wash narrowing (following FR-44); C4's four-way form by amendment, once admission by species lands |
| [FR-50](#fr-50--one-way-cumulative-transfer-records-per-route) | One-way cumulative transfer records per route | **High** (logged by the user, 23 November 2026) | **Phase 1 landed** 24 November 2026 at 1939563e (tag `fr50-phase1-landed-2026-11-24`); judged against fr50-one-way-records-v1, passing (D363). **Phase 2 landed** 27 November 2026 at d92403cc (tag `fr50-phase2-landed-2026-11-27`), its judged `--phase 2` run passing (D405) | Opt-in one-way records from the existing one-way kernels, closing to the net |
| [FR-51](#fr-51--two-voltage-dependent-blocking-modes-on-one-channel-population) | Two voltage-dependent blocking modes on one channel population | **High** (logged by the user, 23 November 2026) | **Landed** 24 November 2026 at 955765ef (tag `fr51-landed-2026-11-24`); judged against fr51-channel-block-v1, every criterion passing | The slot-refusal follow-up; the law's registration after FR-64's note; the two-arm registration (D353, D356) |
| [FR-52](#fr-52--passive-cohort-observations-for-integer-functional-units) | Passive cohort observations for integer functional units: the expected surviving initial and newly assembled units at one site | **High** (logged by the user, 24 November 2026) | **Landed** 27 November 2026 at ab8b599c (tag `fr52-landed-2026-11-27`, D404), from the note `docs/PASSIVE_COHORT_DESIGN.md` (D371, D375, D377, D400): an engine record kept at each event, with the trace reader in `validation/fr52_cohorts/` as the independent check. Version 1 covers chains (dimer to tetramer) and single-subunit activation through a declared identity map, a split makes a new unit, and the declared pairings need exactly min(R, P) pairs | Done. The world `FR52_cohorts` is in crossrev's qualification set |
| [FR-53](#fr-53--a-rounding-allowance-for-global-ledgers-at-every-row) | A rounding allowance for global ledgers at every row: the first window's bound no tighter than the sum's own rounding | Normal (logged by the user, 24 November 2026 as high; lowered by the user, D371) | **Logged:** at steps 0 and 1 the bound is the bare atol, and the host reads 0.28 of it on 625 cells, growing about as √N | A design note: a derived summation allowance per row, or compensated global sums, with the planted faults still caught |
| [FR-54](#fr-54--passive-neutral-diffusion-between-two-finite-liquid-regions-qualified-against-the-exact-two-well-solution-then-a-wash-at-a-diffusion-connected-node) | Passive neutral diffusion between two finite liquid regions, qualified against the exact two-well solution; then a wash at a diffusion-connected node | **High** (logged by the user, 24 November 2026; D341) | **Designed and registered, with FR-57** (D362, D364, D381, D383, D384): one liquid router moves liquid between inlets, finite nodes and records, and takes over the wash (note `docs/LIQUID_ROUTING_DESIGN.md` on `fr54-57-design`). Its protocol is tagged (`liquid-routing-criteria-2026-11-25`), amendments 5 and 6 settle an independent audit of its spec, and the code-blind references are tagged (`liquid-routing-references-2026-11-25`) | The build, 8.25 to 10.5 agent-days with the wash's takeover (D364), queued after FR-52 (D393). The wash retires only after FR-49's World B and C1 and FR-45's W2 and W7 have run, or are pinned to an earlier snapshot (D362, D364) |
| [FR-55](#fr-55--an-input-dependent-closing-rate-for-regulated-availability-closed-until-one-labs-same-patch-record-of-closing-at-two-calcium-levels-exists) | An input-dependent closing rate for regulated availability (dose-dependent deactivation), closed until one lab's same-patch record of closing at two calcium levels exists | Normal (logged by the user, 24 November 2026; D344; lowered by D351) | **Closed, not built** (D390, D394): its design note recommends no build (`fr55-design`, 6109cfad; D378), and the Lean track's search found no same-patch closing record at two calcium levels, D351's condition | None until such a record exists; FR-55 then reopens (D390) |
| [FR-56](#fr-56--a-temperature-dependent-molecular-footprint) | A temperature-dependent molecular footprint with a declared, sourced expansion coefficient | Normal (logged by the user, 24 November 2026; D344) | **Logged:** a fixed footprint per species; two methods confirm POPC's expansion on warming | A design note |
| [FR-57](#fr-57--passive-tracer-carried-by-a-prescribed-liquid-flow-between-finite-liquid-regions) | Passive tracer carried by a prescribed liquid flow between finite liquid regions | **High** (logged by the user, 24 November 2026) | **Designed and registered, with FR-54** (D362, D364, D381, D383, D384): the same router carries prescribed flows, stepped exactly by the declared network's matrix exponential, into a collector that starts empty and can later open as a node. Version 1 admits a flow only where a node's throughput per half-step is at most 1 (D381) | The build, with FR-54's (D364), queued after FR-52 (D393) |
| [FR-58](#fr-58--a-label-on-an-exchangeable-group-carried-through-reversible-conversions) | A label on an exchangeable group, carried through reversible conversions | Normal (logged by the user, 24 November 2026; D365) | **Logged:** labels follow species rows; nothing names the group that crosses | A design note, after FR-50 and FR-44 |
| [FR-59](#fr-59--reversible-transport-into-an-initially-empty-finite-ion-pool) | Reversible transport into an initially empty finite ion pool | Normal (logged by the user, 24 November 2026; D365) | **Logged:** positive-domain laws; species kept positive by a declared trace | A design note: a boundary-capable path, refined in step |
| [FR-60](#fr-60--work-at-a-scheduled-change-of-a-states-energy) | Work at a scheduled change of a state's energy | Normal (logged by the user, 24 November 2026; D365) | **Logged:** no level change books its work | A design note: exact events, an ensemble spread class |
| [FR-61](#fr-61--an-overdamped-rotational-load-angle-speed-work-and-dissipation) | An overdamped rotational load: angle, speed, work and dissipation | Normal (logged by the user, 24 November 2026; D365) | **Logged:** no torque ledger (MODULE_SYSTEM §7 rule (a)) | One design note with FR-62 |
| [FR-62](#fr-62--ion-transfer-coupled-to-a-rotary-step) | Ion transfer coupled to a rotary step | Normal (logged by the user, 24 November 2026; D365) | **Logged:** cycles book ions, not angle or load work | One design note with FR-61 |
| [FR-63](#fr-63--a-ph-dependent-kv15-activation) | A pH-dependent Kv1.5 activation, re-formed as a declared pH shift on its population (FR-64, D356) | Normal (logged by the user, 24 November 2026; D353) | **Logged:** three labs confirm the acid shift's direction; `kv1p5_mh@1` has no pH input | A design note |
| [FR-64](#fr-64--a-declared-voltage-shift-on-a-channel-population) | A declared voltage shift on a channel population: an ion's reversal or a sourced shift per pH unit, read by its gates or its block | Normal (logged by the user, 24 November 2026; D356, D361) | **Designed; the note is final and on main** (D361, D377, D399, D406; `docs/FR64_VOLTAGE_SHIFT_DESIGN.md`, re-read at 7149f90a in its §17, which replaces the earlier `docs/VOLTAGE_SHIFT_DESIGN.md` on `fr64-design`): one optional key on a channel population, whose gates and block read V − ΔV, ΔV an ion's reversal or a sourced shift per pH unit. All four pairings are admitted in version 1, two of them claimed | The build, 5.45 to 6.7 agent-days (§17.8), free at normal priority (D391); queued after FR-52 and liquid routing (D393). Its plan step is done; question 2 is decided (keep @3, D410); the build runs in parallel with liquid routing's still-owed proposal, by the user's word (D410) |
| [FR-65](#fr-65--turnover-beside-a-changing-volume) | Turnover beside a changing volume: reading the current volume and masks beside water, partition or insertion | **High** (logged by the user, 24 November 2026, as part of FR-43; D365) | **Landed** 26 November 2026 at ae349721 (tag `fr65-landed-2026-11-26`, D398): turnover reads the current volume and its masks beside water, partition and insertion, with a lumen at nodes turnover does not read (D375). Exactly the note's 19 of 5,559 sequences newly parse; replacement@2, which gives no hook, is refused beside turnover by the volume rule | **The coupling step landed** 27 November 2026 at 00cfbda1 (tag `fr65-coupling-landed-2026-11-27`, D407): both coupling versions read the current cell volume beside water, so A1 in a swelling cell is admitted; 32 sequences newly admitted, none lost |
| [FR-66](#fr-66--a-passive-fluorescence-reader-over-regional-amount-exports) | A passive fluorescence reader over regional amount exports: several masks over one trajectory, against a prebleach state | Medium (logged by the user, 24 November 2026; D372) | **Logged:** nothing on main reads fluorescence or a prebleach state | A short design note |
| [FR-67](#fr-67--pressure-driven-flow-on-a-network-of-compliant-tubes) | Pressure-driven flow on a network of compliant tubes: Poiseuille edges, compliant nodes, advection and shear remodelling | Normal (logged by the user, 26 November 2026; D393) | **Logged:** no tube network on main | A design note, after FR-57's tagged spec is read for overlap |
| [FR-68](#fr-68--a-consistency-check-on-standard-potentials) | A consistency check on standard potentials: each potential's source and conditions, and cited reaction values, at check time | Normal (logged by the user, 26 November 2026; D393) | **Logged:** cycles close by construction; no check ties a potential to its source | A design note |
| [FR-69](#fr-69--conservative-exchange-between-a-volume-and-a-connected-surface) | Conservative bulk–surface binding and lateral membrane diffusion on unequal areas | Normal (logged by the user, 26 November 2026) | **Logged** | Design and a closed analytical fixture |

## FR-1 — A closed internal compartment on the shared inventory

**Logged 14 November 2026, high priority** (the user: "here is a new feature request please log as
high prioriity"). The request below is the requesting study's text, condensed. The lead's mapping
follows.

**The request.** A finite node that belongs to one cell rather than to the exterior:
- no bath connection, and no faces to other nodes;
- bounded by one membrane patch of its owning cell;
- with its own volume and its own rows of @3's one inventory;
- with transport routes across that bounding patch to the owner's cytosolic rows.

**Why it is general.** Secretory vesicles and granules: this is roadmap item 9's vesicle pool,
already wanted for connexin and morphogen supply. Also lysosomes and degradative compartments,
phagosomes, autophagosomes, and the ER and mitochondrial matrix as species compartments rather than
calcium-only ones.

**Why the study needs it.** Without it, an imported species lands in the same cytosolic row as free
cargo. The model cannot then tell "particle inside a vesicle" from "cargo in the cytosol", which is
the one distinction the study exists to keep.

**The request's own reading of the code** (corrected by the requester on 14 November; the lead
checked the cited lines):
- `restricted_cleft_lumen@1` is not most of this.
  - It is "a finite outside node opened at an insertion onset", not cell-owned.
  - Its volume follows the inserted patch's area, with no water flow.
  - It declares `VIEW_READS = ("membrane_area",)`, so membrane state and insertion are mandatory
    providers.
  - It refuses any source that is not a held, electroneutral bath (`restricted_lumen.py`).
- **The mutual refusal.**
  - The species operators refuse water, the lumens, insertion, partition and the bridge
    (`species_common.py`, `CONFLICTS_VIEW`; D152's refusals likewise).
  - The lumen requires insertion and membrane state.
  - So today a restricted compartment cannot carry inventory species rows with any law acting on
    them, in either direction.
  - This is the version 1.1 composition problem: the volume ledger and the `VIEW_READS`
    relaxation.
- **What transfers is the lumen's accounting:**
  - volume as state;
  - the mixing-heat Jensen gap for fluid of one composition entering a compartment of another;
  - the dilution term that brings @3's chemical term on the declared volume to the physical one.
- **What is missing:**
  - a node owned by a cell rather than by the exterior, with its bath and faces closed;
  - a membrane route for a neutral inventory species (D150 §2.6 refuses it until a material-rate
    bound exists on membranes and junctions: the queued D148 round, D155 and D156);
  - composition with a volume provider (version 1.1 and the volume ledger);
  - the transfer law itself.
- **The order, adopted from the requester's reviewer.** A compartment of fixed topology comes first.
  In it, retained material stays distinguishable from cytosolic material, and transfers reconcile
  on both sides. Dynamic internalisation (FR-2) follows it and does not gate it.

**The lead's mapping (for the design note to test, not settled).**
- **A fixed volume first.** A compartment of fixed topology and fixed volume needs no volume
  provider, so the species operators' refusal of water does not bind its first version. The
  volume-provider composition is its second step.
- **A transfer law that may already exist.** D150's `scheduled_species_exchange@1` already moves
  neutral species across a patch, between a cell and a finite node, with exact half-steps and its
  own bookings. If a cell-owned compartment node can be that patch's node, exchange may be the
  transfer law. It would then avoid the membrane-permeability route, which needs the D148 bound.
  - The design note should test this first.
- **The electrical treatment is the hard question.** @3's patches face outside nodes inside the
  extracellular field solve. A compartment inside the cell faces the cytosol. The note must say:
  - what the bounding patch's membrane voltage and the compartment's charge are;
  - whether the node takes part in the field solve;
  - for a neutral first version, whether the compartment can be electrically silent;
  - and whether the field-input node cap (64) is affected.
- **What it touches.** The S3 lumen's accounting patterns, D150's exchange and identity rules, the
  D148 round for neutral species on membranes, the volume ledger, and roadmap item 9.

**The plan entry.** It sits in CURRENT_PLAN's composition gate, high priority, after the work in
flight.

**The design notes (proposed, 14 November 2026):** [CLOSED_COMPARTMENT_DESIGN.md](CLOSED_COMPARTMENT_DESIGN.md)
for FR-1 and [BATH_SCHEDULE_DESIGN.md](BATH_SCHEDULE_DESIGN.md) for FR-10.

### The first admissible delivery world

For the requester's world definition, which it is drafting now. It combines the two notes with D150's
two operators. It has no reactions inside, no binding sites and no pH.

**The operator list,** on `resolved_pump_composite@1` over `resolved_pump_tissue@3`, in this order:
1. `scheduled_bath_composition@1` (FR-10): the dose at a held bath, as neutral formula units at
   times on the dt grid after 0;
2. `cell_owned_compartments@1` (FR-1): each compartment's node, bounding patch and owner;
3. `scheduled_species_exchange@1` (D150): uptake into the cell, an import route on a patch that faces
   a finite extracellular node, which a face joins to the dosed bath; and loading into the
   compartment, an export route on the bounding patch;
4. `scheduled_species_turnover@1` (D150): clearance in the compartment (degradation), and if wanted
   at the extracellular node.

**The topology it needs:**
- Every cell keeps a patch on a held bath (the held-bath topology).
- The dosed bath is joined by a face to a finite extracellular node. Exchange refuses a patch on a
  held bath, so uptake runs from that node, not from the bath.
- Each compartment is a finite node with no face, faced by one bounding patch of its owner. The patch
  has zero ion permeability and no pump or channel. The content is electroneutral (a zero charge
  anchor): the cargo at a trace, the ions at a declared complement.
- **Species:** the ions and the neutral cargo, declared by `inventory_species.add_inventory_species`
  (valence 0, impermeant on every membrane and junction). **The cap was 7 in all** when this
  world was written (`species_common.MAX_SPECIES` at main's ced45c87). D165 raised it to 16 on 14
  November 2026.

**The refusals the definition meets,** each refused with its reason:
- **Exchange:** a route on a patch facing a held bath; a charged or permeant species; saturable
  loading (a saturable export); a negative rate; a schedule change off the dt grid; a provider of the
  volumes, the areas or the masks; more species than the cap; a donor copy whose route values differ
  from the slot's.
- **Turnover:** production at an outside node (production is at cells only); a route on a held bath.
- **The compartment declaration:**
  - a compartment node with a face, or one that is a held bath or the gauge;
  - more than one patch facing it, or a patch whose inside is not the owner;
  - an ion route on the bounding patch, or a nonzero charge anchor;
  - a compartment that is its capacitor component's representative (refusal 6, version 1.1 since
    25 November 2026; before it, an owner whose component holds no held bath);
  - any operator outside its admitted list;
  - a replacement event on an owner's slot, or with an owner as its donor.
- **The bath schedule:** a target that is not a held bath; a net-charged formula unit; an event at
  time 0 or off the dt grid; a species that would not stay positive; water@1 with an anisosmotic step.
- **Refused beside this world,** each with its door in the notes: D152's reactions (door S), membrane
  state and FR-3's site occupancy (the membrane-state wall), FR-4's charged content (the charged
  door), water and what requires it, insertion, the partition, the bridge and the lumens.

**The onset.** A dose from nothing is D150's unresolved switch-on. FR-10's probe 1 measured it on the
engine as it is, in this world's topology ([BATH_SCHEDULE_DESIGN.md](BATH_SCHEDULE_DESIGN.md) §3.2):
- in a world whose ions move, it passes every check, with an onset-step energy residual of about 2%
  of that step's species flows, unseen;
- in a species-only world the energy ledger refuses it at row 1;
- loading the compartment from a trace books at rounding, by exchange's exact bookings.

So the definition can dose from nothing in a mixed world under the known limit, if the lead extends
D150's ruling to doses (FR-10 §3.2, way (a)). Guard worlds dose between resolved levels, at a step
ratio that registration pins; no probe has yet stepped a bath between two levels.

**Status.** Exchange and turnover exist; when this world was written, the declaration and the bath
schedule were designs, not code. Both have landed since: `cell_owned_compartments@1` (FR-1's
milestone 1, 15 November) and `scheduled_bath_composition@1` (FR-10's milestones 1 and 2, 14–15
November). Door S, which landed with D172's round (16 November), admits D152's reactions in the
compartment beside the dose, so they are no longer refused beside this world (door S's integration
world, `tests/unit/test_delivery_world.py`). FR-1's protocol is exchange's first judged acceptance.
Before the two operators landed, the same transport ran with the compartment as an anonymous
face-free node (D150's face-free world) and the dose as a bath held at the dose from time 0. That
form has no identity refusals and no dose time.

## FR-2 — Internalisation of membrane and its populations

**Logged 14 November 2026, priority 2** (the request's label; the user: "first log this one"). The
request below is the requesting study's text, condensed. The lead's mapping follows.

**The request.** The retrieval direction of `scheduled_membrane_insertion@1`: membrane area,
capacitance and the populations on it move inward at a scheduled rate, carrying the compartment they
form (FR-1) with them.

**Why it is general.**
- endocytosis of every kind;
- receptor down-regulation and recycling;
- surface-population turnover, which the roadmap lists under membrane redistribution;
- synaptic vesicle recycling;
- membrane retrieval after division.

**What is missing, in the requester's reading.**
- Insertion@1 refuses retrieval because the capacitor's free energy would rise: its heat would be
  negative, and the work would need a declared source. The lead checked this:
  `membrane_insertion.py` refuses "a negative rate (retrieval: its heat would be negative, and the
  work would need a declared …)".
- The requester notes that finite ATP/ADP/Pi pools already exist, in the older calcium and energy
  families. Letting species laws draw on energy pools is deferred: D150 question 11, D152
  question 10 and D151.
- So a declared ATP-coupled retrieval law looks like the same question arriving twice, and one
  answer would serve both.

**Why the study needs it.** Receptor-mediated uptake depletes the surface pool and returns it. A sink
that never consumes its receptors cannot produce saturation, competition between neighbouring cells
for a shared dose, or the cell-to-cell variation that makes delivery selective.

**The lead's mapping (for its design note to test, not settled).**
- **It depends on FR-1.** The retrieved membrane carries the compartment FR-1 creates, so FR-2's
  design follows FR-1's.
- **The energy source is the design question.** Retrieval's work could come from:
  - a declared external reservoir, as D150's turnover and D152's driven routes book work today; or
  - a finite energy pool.

  The pools live in the older families, outside the composite, so drawing on them in the composite
  is new work. The energy-pool coupling deferred by D150 and D152 should be designed once and serve
  every consumer.
- **Populations move with the membrane.** Channel and pump populations on the retrieved area move
  inward with it: the receptor down-regulation the study needs. That touches membrane state's
  populations, S2's domains and insertion@2's bookings, and needs their accounting.
- **What it touches.** S3's insertion and membrane-state operators, D150 and D152's energy-pool door,
  FR-1's compartment, and the composition walls (the species operators refuse insertion today).

**The design note (proposed, 18 November 2026):** [MEMBRANE_RETRIEVAL_DESIGN.md](MEMBRANE_RETRIEVAL_DESIGN.md), with the energy source answered once for D150's question 11, D152's question 10 and D151 (D216).

**Answered 18 November (D217):** version 1 is retrieval and recycling, with "no new explicit machinery fuel draw in v1" and one lumped, well-mixed pool per cell. It starts when B1's operator part, with the split-and-merge kernel, lands (the note's §12).

## FR-3 — The site-occupancy primitive

**Logged 14 November 2026, priority 2** (the request's label; the user: "then next one"). The request
below is the requesting study's text, condensed. The lead's mapping follows.

**The request.** Promote the primitive already specified as a door in
[D150 §2.5](SECRETED_SPECIES_TRANSPORT_DESIGN.md):
- binding sites as state on a membrane domain or contact, with one owner;
- bound and free in one material ledger, never a second copy;
- accessibility as a factor separate from stoichiometry;
- declared partition and reset rules at division and replacement.

**Why it is general.** D150's own list: kinetochore sites, junction docking and surface catalysis.
Add to it ligand–receptor signalling generally, and the engineered quorum-sensing consortia in the
13 November reading list, where a finite receptor pool reads the shared signal.

**What it builds on.**
- `membrane_entity_state@1`'s populations are the owner D150 identified.
- The day-one analytic guard is already derived (D150 §2.5; the lead checked it). The saturable
  sink is the quasi-steady limit of binding with internalisation:
  J = k_int R_T c / (K_M + c), K_M = (k_off + k_int)/k_on.

**Why the study needs it.** Accessibility separate from stoichiometry is not a detail. Uptake of the
same formulation differs by cell type through surface composition. The 2026 glycocalyx and
protein-corona work found heparan-sulfate dependence in some tested lines and not in others.
Accessibility is where that enters a model without naming a receptor.

**The lead's mapping (for its design note to test, not settled).**
- **D150 §2.5's four requirements are the contract.**
  - The bound amount is state on the site's owner. Binding and release are booked transfers
    with @3's free inventory, as `exchange_moved_fmol` is.
  - Version 1's import routes are the shape the internalisation step writes into.
- **Accessibility as a factor.**
  - It is a declared multiplier on the binding rate, separate from the site count.
  - It fits the coupling operator's factor form (D155 and D156: F ∈ [b, 1]) when accessibility
    is regulated, and is a plain per-domain parameter otherwise.
- **The links to FR-1 and FR-2.** Receptor-mediated uptake binds at the surface (FR-3),
  internalises the bound sites with their membrane (FR-2) and delivers the cargo into a
  compartment (FR-1). The three should be designed so the bound pool's identity survives each
  transfer.
- **The design order.** FR-3 can be designed before FR-1's code lands: its first version needs only
  membrane state and @3's free inventory, and its guard is analytic. Its internalisation step
  follows FR-2.
- **The sources.** The primitive must be designed from its own sources (kinetochore counting, the
  Hirano 2026 review in the paper backlog, receptor kinetics), not shaped by one consumer (D144).

## FR-4 — Compartment pH: a proton species, an acidifying pump, buffering

**Logged 14 November 2026, priority 1 (blocking)**, the request's label. The request itself sequences
it last of the block, after FR-1's compartment exists and can hold material. The request below is the
requesting study's text, condensed. The lead's mapping follows.

**The request.** Protons as a species, with a pump that can acidify a compartment against its
gradient, drawing on the existing fuel pools, plus buffering through the reaction operator.

**Why it is general.**
- endosomal and lysosomal acidification;
- the mitochondrial proton-motive force, which the roadmap wants for energetics;
- pH-dependent gating and enzyme activity;
- bicarbonate handling.

Cells has no pH anywhere today, and a whole-cell model needs it.

**The charge problem, in the requester's corrected reading.** The lead checked each point in the
code.
- **A proton row is legal in @3 itself.** `surface_tissue_spec.py` admits integer valences in
  [−8, 8], so a +1 species is a declarable ion row. The transport half starts from something that
  exists.
- **It cannot be a D150 or D152 inventory species.**
  - `inventory_species.py` fixes `valence=0`.
  - `parse_species` refuses a nonzero valence for all three species operators
    (`species_common.py`).
- **Buffering is D152's named door.** Its §3.2 lists, as later work, "closed reactions on charged
  species with Σ_s z_s ν_sr = 0 exactly (integer valences), such as buffering".
- **The counterion pathway is a physical modelling choice, not bookkeeping.** Acidifying a
  compartment without a parallel ion flux charges it. The counterion pathways and the pump's
  energy must be explicit.

**Numerics the requester expects to matter, which the lead agrees with.**
- pH 7.4 to 5.0 is 4e-5 to 1e-2 mM, against about 150 mM of ions. That is D150's µM–nM regime,
  where the shared IMEX energy bound was 1.7 to 1,721 times a species' whole free-energy change.
- D150's answer should transfer: a species-only guard world, a NumPy ΔG test per law, and
  per-species material floors and anchors.
- Buffering is an equilibrium with a large capacity ratio, expected to be the stiff part.

**The lead's mapping (for its design note to test, not settled).**
- **Three doors already drawn meet here:**
  - D152's charged closed reactions, for buffering;
  - the energy-pool coupling, for the pump's fuel (D150 question 11, D152 question 10, and FR-2's
    retrieval energy);
  - FR-1's electrical treatment, which a proton-carrying compartment makes unavoidable. It cannot
    be electrically silent.
- **The pump.** An acidifying pump is a new pump law on @3's patch: a V-ATPase-like stoichiometry,
  cited, with neutral naming. Its energy comes from a declared fuel. The fuel pools exist only in
  the older calcium and energy families, so drawing on them in the composite is the energy-pool
  door.
- **Stiffness.** D152 v1 refuses kinetics too stiff for the step (dt·L > 1). Buffering therefore
  needs either the stiff-kinetics door (a positive implicit half-step) or a rapid-buffer
  equilibrium treatment, each qualified. That is for the design note to choose.
- **pH-dependent gating and enzymes.** These read a charged source. Under the coupling operator
  (D156) that goes through its regulatory state, or through D152's read-only charged-species door.
- **The order.** After FR-1 and with FR-2's energy design, as the request itself sequences it.

## FR-5 — State-conditioned transfer across an internal membrane, with leak and reseal

**Logged 14 November 2026, priority 1 (blocking)**, the request's label. It depends on FR-1's
compartment and FR-4's pH. The request below is the requesting study's text, condensed. The lead's
mapping follows.

**The request.** Two parts, both generalisations of things Cells has:
1. `resolved_repair@1`'s damage fraction and prescribed closure law, applied to an internal
   compartment's bounding patch instead of the plasma membrane;
2. a transfer law across that patch whose rate reads the compartment's own state (its pH), so
   that a species crosses when the compartment is in a declared condition and not otherwise.

**Why it is general.**
- mitochondrial permeability transition;
- lysosomal membrane permeabilisation;
- pore-forming toxins and complement;
- bacterial escape from phagosomes;
- exocytic fusion, which is the same accounting in reverse.

**What is not asked for.** A fitted escape mechanism. The repair law is phenomenological, which is
fine. What is needed is the accounting:
- material that leaves a compartment arrives in the cytosol;
- damage opens and closes;
- the books close.

Calibration is the requester's to supply, with measurements.

**The lead's mapping (for its design note to test, not settled).**
- **The injury law lives only in an older family.** `resolved_repair@1` (`surface_repair_spec.py`;
  the law in `legacy/processes/membrane_injury.py`) is fixed-geometry injury on owned calcium tissue. Its
  patches carry an initial damage, an injury rate, a resealing rate and per-species permeabilities.
  It is not a composite operator.
  - Applying it to a compartment's patch means re-expressing it in the composite, as an operator.
  - That is a case of the open decision on moving old-family physics (D156: it waits for the
    conduction probe's verdict). A targeted re-expression, on its consumer's need, fits D144.
- **Damage as a control factor.** An open fraction on the patch's leak, or on the transfer's rate,
  is kinetic state with no ledger. It is like the bridge's aperture, or the coupling operator's
  regulatory state (D156). The material it lets through is booked by the transfer law.
- **The state-conditioned rate is the coupling operator's routing door.** A rate on another
  operator's transfer, read from the compartment's pH:
  - it routes to another operator's control (D156's named door);
  - it reads a charged source (FR-4's proton), through the regulatory state or D152's read-only
    charged door.
- **The accounting is FR-1's transfer bookings,** with both sides reconciled.
- **Exocytic fusion** is FR-2's direction in reverse, with the compartment's contents released.
- **The order.** After FR-1 and FR-4, with the routing door, as its dependencies require.

## FR-6 — Species-driven control factors

**Logged 14 November 2026, priority 2** (the request's label). The general request is **addressed by
an accepted design, with no code yet.** The inventory-coupling note (D155 item 1, scoped by D156;
[INVENTORY_COUPLING_DESIGN.md](INVENTORY_COUPLING_DESIGN.md)) was accepted on 14 November.
- **What it specifies:** `species_regulated_availability@1` reads a concentration from @3's own amount
  rows, through Hill laws, into a factor F ∈ [b, 1]. `hill_regulated_two_state@1` serves slow
  sources.
- **What the requester withdraws:** the general request. Its code started on 14 November, with
  milestone 1 (the contract fit) in progress.

**Three narrower items remain, recorded as consumer registrations, in the requester's order:**
1. **The channel-population availability target** (the note's milestone 1; ruling 12).
   - The junction target is accepted. The channel target is the one this study needs, because a
     delivered template's effect on a cell's electrical behaviour runs through channel
     availability.
   - Leaks and pumps on the same path would cover the rest.
   - *Status (18 November):* **qualified for gate-free channel populations** by the coupling
     operator's judged protocol `coupling_regulated_availability_v1` (A5; 15 November, 47 of 47:
     V and the amounts at order 2.00, the factor exact to rounding, every control caught). Gated
     populations are not covered.
   - *Mapping:* probe P1, the channel path, was milestone 1's. Leaks and pumps are the note's
     next targets on the same path.
2. **The routing door (§2): a factor on another operator's control,** specifically a turnover rate,
   an exchange rate and a reaction multiplier.
   - This study needs it twice: for a release rate that reads a compartment's pH (FR-5 part 2),
     and for a production rate driven by a delivered template (FR-7).
   - The requester asks for nothing to be built now. It registers as a second consumer, so the
     door is not designed for one.
   - *Mapping:* recorded against D156's named door, beside the division trigger.
3. **The two-state regulatory fraction as a per-cell slow state,** used for a cell's *prior*
   condition, set before a dose arrives. That is the variable the study turns on: the same
   formulation given to differently conditioned cells.
   - It matches the GZMK review's "slow, writable per-cell state" row.
   - *Status (18 November):* **qualified for a gate-free channel population** by `fr6-a5pp-v1`
     (A5″; registration 555d8771, 18 of 18): two cells given the same regulator dose from
     s₀ = 0.1 and 0.8, V and the amounts at order 2.01 against R-cell, and every control that
     tells the two cells apart caught (the prior swapped, shared or ignored, the state bypassed,
     its rates 1% off, the basal level).
   - *Mapping:* the note's state has a declared initial value per cell (s₀), and interventions
     write it (`regulatory_writes`). So a prior condition is a declared s₀ or a write before the
     dose. Its version 1 refuses replaced slots (version 1.1).

**Why it was general, for the record:** morphogen concentration driving a response, quorum sensing,
substrate induction, and any drug–effect relation. The note's own consumers: Track R's cycle gate,
GZMK item 6, the causal-carriers row and E15.

## FR-7 — Abundance-to-function, exposed in the composite

**Logged 14 November 2026, priority 3** (the request's label: "ordering, not scope"). The request
below is the requesting study's text, condensed. The lead's mapping follows.

**The request.** No new scope. When the closed molecular-to-physiology loop's functional unit is
chosen:
- (a) the loop admits a production rate driven by a declared species (FR-6 item 2), not only a
  scheduled one;
- (b) the quantitative abundance-to-function relation is reachable in the composite. Today it is
  state only in `resolved_redistribution@1/@2`.

**The requester's update, 14 November.** The coupling design's channel-availability target (its
milestone 1) is most of (b): a factor on a channel population's availability is an
abundance-to-function path in the composite. If that lands, (b) narrows to "and let the factor's
source be a population abundance, not only a species concentration".

**Why the study cares.** This is stage 5 of its table, and the one place where Cells already has the
better part of the answer. "A transient template changes a protein abundance, which changes a
measurable physiological response, and the response outlives or does not outlive the template" is
both the study's therapeutic question and *Plastic Heredity*'s question. The requester would rather
use Cells' unit choice than ask for its own.

**The lead's mapping (not settled).**
- **The unit choice stays the user's** (CURRENT_PLAN's closed molecular-to-physiology loop
  gate). The candidates where abundance is already state: the redistribution pumps
  (`resolved_redistribution@1/@2`, an older family) and junction formation. This request asks only
  that the chosen loop admit (a) and (b).
- **Part (a) is the coupling operator's routing door** (D156): a factor on a production operator's
  rate. FR-6 already records it, with this as a further consumer.
- **Part (b), narrowed, is a source-semantics door of the coupling operator.** The factor's source
  would be a population's abundance, read from `membrane_entity_state@1`'s view, as well as a
  species concentration. It is to be recorded in that note's doors when the channel target lands.
- **The link to the preprints.** The response's persistence after the template is gone is the
  heredity question. A unit chosen for the loop should be one where that question is measurable.

**The design note (proposed, 18 November 2026):** [ABUNDANCE_TO_FUNCTION_DESIGN.md](ABUNDANCE_TO_FUNCTION_DESIGN.md), framing the user's choice of the loop's unit (D216). **Answered 18 November (D217, D218):** U2 first, then U1; the loop is admitted through B1′; qualification needs a closed loop with a feedback-cut control (the note's §9).

**Before revisiting D218's kept refusal (the Lean lane, relayed by the user, 21 November 2026).**
D218 refuses a population's availability multiplied by its own abundance where that abundance
already sets its conductance, so a population cannot regulate its own availability through its
density. Cells reproduced the density curve on a separate reporter. An independent Kv1.5
density experiment (surface density and current density measured in the same cells, across
expression levels) is the next evidence to seek before that rule is revisited. Until then, the
refusal stands.

**The search's result (21 November 2026).** One study measures both in the same Kv1.5 cells across a
continuous range of expression: Maverick and Tamkun 2022, Biophys J 121:755-768,
doi:10.1016/j.bpj.2022.01.021 (PMC8943702; free to read, not openly licensed, so bare cited values
only, D227).
- **Method:** HEK293 cells with YFP-Kv1.5. Surface channel number came from TIRF counting
  calibrated to single channels, and from gating charge. Conductance came from the I-V slope near
  E_K.
- **Result, as reported:** conductance is not proportional to surface density. About 26% of gating
  channels conduct, and the conducting fraction falls as density rises (about 70% non-conducting
  near 100 channels per square micrometre).
- **What it supports:** not a test of "current scales with density". It could support a held-out
  test of a density-dependent conducting fraction, fitted on low-density cells and predicted on
  high-density ones. That non-conducting fraction is a separate effect from availability as
  Cells defines it.
- **What it needs:** the values are in Figs 7-8 and the supplement. A test needs the user's
  download of the PDF and supplement for digitising, or the authors' per-cell data.

A second candidate, Ding et al. 2014 (PLoS One, CC BY), varies culture temperature rather than
expression, with currents and surface data from different cells, so it can't support the test.

**The registered test, written before the paper is opened (21 November 2026).** Item 4 reopens on
Maverick and Tamkun 2022, which meets D268's condition: surface abundance and current in the same
single-variant cells (D273's correction). This entry fixes the test before anyone opens the user's
download of the PDF and Supporting Material.
- **FR-7's prediction.** The chain has no density-dependent conducting fraction.
  - A population's conductance is P a A = P N/ρ_ref, membrane_entity_state@1's view, linear in its
    units N, times its availability and its gates' open probability. Neither depends on density.
  - So at the paper's fixed protocol, the chain predicts plain proportionality: G = g N, with one
    constant g per cell line.
  - Cells' own Kv1.5 laws are not calibrated to these cells, so g is fitted, not taken from them.
- **The cells.**
  - Eligible: YFP-Kv1.5 HEK293 cells with a per-cell surface count paired with a per-cell
    conductance. They come from the figure or table that pairs the two for the most cells.
  - Other channels and conditions are information only.
  - Binned or mean-only values make the test not assessable under this entry.
- **The judged observable:** conductance against surface count, in matching extent (both per cell,
  or both per membrane area or capacitance). If the paper pairs both a gating-charge count and a
  TIRF count with the conductance, the gating-charge count is primary, since it is whole-cell, as
  the conductance is. The other count is information.
- **The held-out split** is mechanical, and uses the count alone.
  - Order the eligible cells by count, ties by the paper's order. The top ⌊n/3⌋ are held out; the
    rest are the fit set.
  - It tests what non-proportionality would break: extrapolation from low to high density.
- **The statistic,** with x = ln N and y = ln G:
  - the fitter estimates ĉ, the fit set's mean of y − x;
  - the checker computes d = (the held-out mean of y − x) − ĉ: the log ratio of held-out to
    fitted conductance per unit, with Welch's 95% interval from both sets' spreads.
- **The pass rule,** with margin δ = ln 1.25:
  - **pass:** the whole interval lies within [−δ, δ]. Conductance per unit holds within a factor of
    1.25 from low to high density, at 95% confidence;
  - **fail:** the whole interval lies outside [−δ, δ];
  - **inconclusive:** otherwise;
  - **not assessable:** fewer than 6 fit or 4 held-out cells, or a held-out median count less than
    twice the fit set's.

  The reported headline predicts a fail with d < 0. A fail with d > 0 would contradict it, and goes
  to an extraction audit before any conclusion is drawn.
- **Disclosure: what was read before registering.**
  - The headline, in the search above: conductance not proportional to density, about 26% of
    gating channels conducting, the fraction falling with density, and about 70% non-conducting
    near 100 per µm².
  - This entry's author, in a repository search before writing it, also saw the Lean lane's
    aggregate figures: conducting fractions of 0.23 and 0.18, and mean fractions of 0.96 ± 0.05
    for Kv1.4 and 0.26 ± 0.01 for a Kv channel (the line was cut off there). It also saw that the
    Lean lane cites Figs 8B–C.
  - No per-cell value was seen.
  - The Lean lane holds its own extraction of this paper,
    lean/checks/data/maverick2022_kv_density.json, which was not opened here.
- **Roles: three agents.**
  - **The extractor** opens the paper and its supplement. For every eligible cell it records the
    counts, the conductance, the capacitance if given, the source figure and the digitising error.
    It then applies the split and writes three files: the fit set's rows, the held-out counts, and
    the held-out conductances, sealed for the checker.
  - **The fitter** gets only the fit set's rows and the held-out counts. It fits ĉ and records each
    held-out prediction before the checker unseals. It never reads the paper, the sealed file, or
    the Lean lane's files on the paper, which may hold the held-out cells' values.
  - **The checker** unseals and scores by the rule. It also cross-checks the extraction against the
    Lean lane's. A documented transcription error goes to the lead; it is never silently corrected.
- **Information only, not judged:**
  - the same test on the secondary count;
  - the test with any background conductance the paper reports subtracted. An additive background
    also makes G/N fall with N;
  - a declared conducting-fraction form, G = g N/(1 + N/N_half), fitted on the fit set alone, with
    its held-out error reported beside the chain's.
- **What each outcome means.**
  - **Pass:** the linear relation holds for Kv1.5 over the measured densities, and item 4 proceeds
    with the chain.
  - **Fail:** the relation is refuted at these densities. Cells cannot predict this response until
    a declared density-dependent conducting fraction joins the abundance-to-function relation, as
    a general, qualified feature (D136, D144).
  - **Inconclusive or not assessable:** nothing changes.
- **Bearing on D218's kept refusal.**
  - The refusal forbids a factor on a population's availability from its own abundance, because
    the view's linear relation already counts that abundance. This paper tests the premise, not the
    mechanism.
  - **A fail** would show that a Kv1.5 population's function does depend nonlinearly on its own
    density: physics, not double counting. The refusal should still stand, with its reason
    restated: a population's own density reaches its function only through its declared
    abundance-to-function law, counted once there. It never reaches it through the coupling, whose
    factor is switchable regulation of availability.
  - **A pass** supports the premise as written.

**Item 4's extraction, recorded before the fitter starts (21 November 2026, 23:00 UTC).** The extractor
read Maverick and Tamkun 2022's Fig. 7C (YFP-Kv1.5: whole-cell conductance against whole-cell gating
charge) exactly from the figure's vector drawing, and cross-checked it against Fig. 8A. There are 19 cells
with per-cell pairs, so none of the registration's "not assessable" conditions holds. The count is the
gating charge over the paper's 4.23 e0 per channel. 13 cells are in the fit set and the top 6 by count are
held out; the held-out median count is 2.43 times the fit set's. The TIRF count is never paired with
conductance in the paper, so the information-only secondary test cannot run. The files are in the
workspace, outside the repository. SHA-256: held_out_conductance.json (sealed)
815f7b9b800f4b6de56fa76c16bd3067fc99b9f0c5184ada934aefd1ccd70046; fit.json 6839555bee4adc5ff154003f81b6356ca82c185b3a983590f06dd00df3698947; held_out_counts.json
5465e3b20da3c94339eb624ccd26b530ec9216a00f0cb0fd51d876281c0ff20d. The fitter sees only the fit rows, the held-out counts, the protocol
and the notes, and records its predictions before the checker unseals.

**The fitter's predictions, written before unsealing (21 November 2026).**
/mnt/workspaces/Cells/fr7-maverick2022-test/fit/predictions.json, sha256
`6027e2738278fe217787250cc781190779d9e793f71221a4184a4586b3e9e4f4`.
- **Inputs:** fit.json and held_out_counts.json only. Their sha256 are recorded in the file, and
  the sealed conductances were not read. The script is fit_chain.py beside it, sha256
  `3626dd48207c29a69d3018fc42957d1435c7bdd0d550b8ef3662f80c35fdbb6b`.
- **The chain's fit**, on the primary count (count_primary_gating_channels) for both sets:
  ĝ = 1.2128 pS per gating channel (ĉ = −6.71479 in ln nS), fit-set spread s_fit = 0.2742 in ln
  units, n = 13. Each held-out cell has G_pred = ĝ N.
- **Information only:** the declared conducting-fraction form is fitted on the fit set alone and
  sits in the file. The secondary-count and background-subtracted variants cannot run: no TIRF
  count is paired with conductance, and the paper reports no background value.

**Item 4's registered test, scored (21 November 2026, 23:07 UTC): inconclusive.** The checker's
result, under the registered rule:
- d = −0.381: held-out conductance per gating channel is 0.684 times the fit set's.
- Welch's 95% interval is [−0.656, −0.105], against the margin ±ln 1.25 (±0.223). The interval
  crosses the margin's lower edge, so it is neither wholly inside nor wholly outside it.
- The direction agrees with the paper's headline (d < 0).

Checks:
- Every digest matches the committed records: extraction, predictions, inputs and the article.
- The extraction reproduces byte for byte from the checker-only scripts.
- The Lean lane's independent aggregates agree within reading precision: mean conducting fraction
  0.250 ± 0.019 against 0.26 ± 0.01.

Information only, not judged:
- The chain's predictions are all high, with an rms ln error of 0.441; 5 of the 6 held-out cells lie
  within their 95% prediction intervals.
- The declared conducting-fraction form, fitted on the fit set alone, gives 0.272.

Score: score.json, sha256 48958cd47f5fbcd2e725b1db263ababb7d5589034c3538942647fe5cfafb1d8c.
**Consequence:** no engine change follows from the registered rule, and D218's refusal stands. Item 4
stays open. A decision needs more paired cells (a narrower interval), or a declared conducting-fraction
law with its own registered test on data not used here (D275).


## FR-8 — A qualified long-duration mode

**Logged 14 November 2026, priority 2** (the request's label). The request below is the requesting
study's text, condensed. The lead's mapping follows.

**The request.** Keep the quasi-steady electrical mode, or any qualified multirate method, on the
path. When it is qualified, include **an intervention applied during the slow phase** in its
acceptance case.

**Why it is general.** Everything slow: turnover, regulation, reconstruction, the renewal assay, and
the organ-scale ageing timescales D150 deferred for exactly this reason.

**The requester's arithmetic, corrected 14 November** (its reading of Cells' reported costs; the
requester is writing a benchmark specification for its own composition):
- **Its stages and the step count.** The stages run at ms (electrical), minutes to hours (uptake,
  acidification, escape) and 24–72 h (expression, protein turnover, response decay). At 1 ms that
  is 3.6M steps per simulated hour.
- **A 72 h trajectory, by field nodes:**

  | Field nodes | Per step | 72 h |
  | --- | --- | --- |
  | 14 | 1.7 ms | about 5.1 days |
  | 254 | 7.7 ms | about 23 days |
  | 825 | 76 ms | about 228 days |

- **Why that understates it:**
  - those per-step costs are the empty composition, with operators cost on top;
  - the 825-node figure varies by about 2× across the tree;
  - the L4 buys ensembles, not one fast trajectory: about 26.7 ms one world at a time, and
    2.10 ms per world-step only when amortised over 256 worlds.
- **So duration is a numerical-method problem, not a hardware problem.** Projective
  time-stepping failed its qualification, and the requester does not ask for it to be revisited.

**The lead's mapping (not settled).**
- **This is CURRENT_PLAN's open deliverable.** The compute-limits gate has "a verdict on
  long-time methods: multirate or quasi-steady methods qualified, or bounded, on histories and
  intervention responses". FR-8 adds that the acceptance case include an intervention applied
  during the slow phase. That is recorded in the gate (D164).
- **The gap the lead's architecture review named.** The coarse modes cover `resolved_pump_tissue@1`
  to `@3` only, so no composite operator has a long-time path. That needs its own design note,
  which does not exist yet.
- **The requester's benchmark specification,** when it arrives, is an input to that note: its
  composition, its accuracy needs and its interventions.
- **The two-clock pattern helps where the physics separates.** Track E's plan runs a slow world
  coarsely and short fast assays from frozen snapshots (D155). It is not a long-time method for
  one coupled trajectory.

**The design note (proposed, 18 November 2026):** [LONG_DURATION_MODE_DESIGN.md](LONG_DURATION_MODE_DESIGN.md), the long-time path for composite operators, written before the GH200 numbers and the benchmark specification (D216).

**Answered 18 November (D217):** stage 0 only, that is M1–M5 and a small harness, with criteria declared before comparison. The method follows stage 0 and the FR-18 probe (the note's §11).

## FR-9 — Raise the 7-species cap

**Logged 14 November 2026, priority 2, blocking for world design** (the request's label). The raise
was measured safe to 16 by the W4 probe. The request below is the requesting study's text,
condensed. The lead's decision follows.

**The count, corrected by the requester.** The lead checked the source.
- **The cap counts every species, ions included.** `check_species_cap` takes
  `count = len(spec.model.species_ids)` (`species_common.py`).
  - With the six-ion set (Na, K, Cl, Ca, P, M), one row is free under a cap of 7.
  - With a four-ion world, three are free.
- **Locations are not identities.** The arrays are (species, node). The same species inside a
  compartment and outside it is one row at two nodes.
- **One caveat the other way.** A compartment that is not a declared node has no node axis, so a
  pool held outside the node structure would need its own row. Which way FR-1 goes therefore
  changes the budget. The requester will state the count with its world definition.
- **The result.** A minimal delivery world on a six-ion set is over the cap before any cargo,
  bound complex, buffer or proton is added. So the cap binds on the first world definition,
  ahead of FR-1 to FR-5.

**What the W4 probe found** (read-only, from a clean snapshot at f7f0592; PROGRESS):
- the cap can rise to 16 in every composition D150 and D152 admit;
- no ledger, guard or promised idleness depends on NumPy's sum order;
- host checks, the face-free energy world, batches, restart and idleness hold at 16.

D150's unpromised claim 3 departs at rounding in a 12-species chain. The requester does not rely on
cross-world bitwise identity.

**Landed 14 November 2026** (merge 2161f39, tier 1 and 2 with no changed outcome). `MAX_SPECIES` is 16.
The tier-1 guard is host-side (`tests/unit/test_species_cap.py`). The runner world `cell_charged_9`
is in tier 2 (`tests/unit/test_species_cap_runs.py`), since compilation alone takes about 15 s.

**Raised again by FR-43 (D315, 23 November 2026):** `MAX_SPECIES` is 1,024, on FR-43's probe, with
the species sums folding by `lax.scan` above 16 terms so that every world at 16 or fewer keeps its
program (FR-43's part 1; D150 §14).

**The lead's decision (D165): accepted, and queued now.** The requester is the consumer that
PROGRESS's "when a consumer needs it" waited for.
- **The change:** `MAX_SPECIES` from 7 to 16 in `species_common`, as a D148 in-place change, with
  the four criteria and the stop rule written first.
- **The tests:**
  - a tier-1 guard world of 8 or more species that exercises the sum order (for example the probe's
    `cell_charged_9`);
  - the three refusal tests updated.
- **The documents:** D150 §2.6 and §11.5, D152 §7.2 and its refusal lists, and the docstrings.
- **What stays the same:**
  - D150's claim 3 stays reported, with the chain departure recorded.
  - Worlds above 7 species are outside D150's judged scope until a protocol covers them.
  - Above 16 needs another probe.
- **The requester's species list,** with its world definition, confirms the need (16 or fewer).

## FR-10 — A dose schedule: scheduled bath composition in the pump family

**Logged 14 November 2026, priority 2, small** (the request's label). The request below is the
requesting study's text, condensed. The lead's mapping follows.

**The request.** Let a held bath's composition change on the dt grid in the composite, as the older
surface families already allow for K, Cl and Na.

**Why it is general.** Any medium change:
- a wash-in or wash-out;
- a drug dose;
- an ion substitution;
- a pH step;
- a nutrient step;
- an osmotic challenge.

E07-v2's design wants an osmotic step as a post-release challenge, which is this feature (its §8:
"none found" in the pump family).

**What exists** (the lead checked the source).
- `resolved_open_calcium_energy_bath_events@1` programs an ideal reservoir's bath composition on
  the 56-law calcium/ER and finite-fuel owner.
  - The ion dose, the compensating electrode charge and the external work are kept explicit
    (`legacy/core/surface_bath_events_binding.py`, policy
    `explicit_ideal_reservoir_dose_voltage_compensation_work@1`).
  - So the law and its accounting already exist, in a frozen family.
- Its status there is guarded, with full bath trajectories out of scope and evidence at ns–µs
  horizons.
- In the pump family, nothing does this.

**The lead's mapping (not settled).**
- **A small composite operator.** An event map at dt-grid times sets a declared held bath's
  composition. It books the dose as reservoir supply and the composition change's external work
  explicitly. For a charged step it keeps the older law's compensating-charge rule.
- **It re-expresses an older family's law,** a case of D156's open decision on moving old-family
  physics. It has at least three consumers (this study's doses, E07-v2's osmotic step, FR-4's pH
  step), so a targeted re-expression fits D144.
- **D150's species.** A held bath already serves as a species' far-field source or sink at a fixed
  concentration. A scheduled change of that concentration is a species dose with no charge
  compensation, since the species are neutral.
- **Water.** An osmotic step needs water plus a bath change. Water composes with the composite,
  but water plus the species operators is refused (version 1.1). The note must state which
  compositions an osmotic step admits.
- **The order.** It is small and has several consumers, so it is a candidate for an early slot,
  after FR-1's design. Its design note should be short.

## FR-11 — Looping replay packages of living cells for the viewer

**Logged 15 November 2026, no priority stated** (the user: "we have four types of cells for
vizilation and that we are testing to different degreas in our upcomiung runs, human, planerian,
syn3a, bacteria - we'd like the engine part to prepare relativly high level simulation replay
packages so when you are not exploring some research with the viz tools the cell will be "alive" in
a loop").

**The request.** The viewer shows four cell types: human, planarian, Syn3A and a bacterium
(*M. pneumoniae*). For each, the engine prepares a relatively high-level simulation replay package.
The viewer plays it in a loop as the cell's resting state, whenever no research run is being
explored.

**The lead's mapping.**
- **It is output, not new physics.** Each package is a short run of laws the engine has, or gains
  through their own milestones.
  - It is written by the run-view writer (D154, [note](RUN_VIEW_DESIGN.md)), in its format.
  - It stays within the viewer's limit of about 1 MB per run.
- **High level means a declared low level of detail** (D175): lumped compartments and reduced
  representations. A package is labelled an illustration, never an experiment or a qualified result.
- **A seamless loop needs a periodic state.**
  - The physical way is a periodic drive, such as a pacing stimulus or a nutrient cycle. After the
    transient the response repeats, and one period loops, with the seam checked (the state at t + T
    against the state at t).
  - Playing the run back and forth, or cross-fading a stationary state, would be the viewer's
    choice, and is marked as such.
- **The four cell types differ in readiness:**
  - **Planarian:** the cue-written sheet's runs exist (E07-v1, W1).
  - **Human:** a cell type is still to be chosen. The viewer's human organ is the heart, so a paced
    cell would fit, with the channel laws it needs.
  - **Syn3A and *M. pneumoniae*:** neither has an organism definition yet (the
    [Syn3A note](SYN3A_MINIMAL_CELL_TRACK.md), D173). A first package would be a lumped single cell
    built from the engine's general laws (membrane potential, pumps, a small reaction set), labelled
    as such.
- **Sequencing:** after the run-view writer lands with D172's round. The per-species definitions are
  biological definitions, kept apart from engine mechanisms (ARCHITECTURE).
- **The user's choices (15 November 2026), after the options:**
  - **Loops are periodic:** a periodic drive, with one period played and its seam checked.
  - **Human is a paced heart cell.**
  - **For Syn3A and *M. pneumoniae*, the cell cycle is in scope as a loop** (grow, divide, follow
    one daughter), as an illustration, since division is prescribed.
  - **Timing:** after D172's round, at least to the stage where the run-view writer can carry the
    interim planarian loop. The planarian loop comes first.
- **Next:** a design note when the run-view writer lands (D142).
- **Since then (16 November 2026):**
  - **The human loop** is a paced human ventricular cell on Track E's human law set, O'Hara–Rudy
    2011's endocardial cell, and it waits for those laws (D183, D184;
    [design note](HUMAN_CARDIAC_LAWS_DESIGN.md), proposed). No generic stand-in is used: that was
    the lead's reading of the user's answer, kept under the user's delegation (D184).
  - **The run-view writer** did not land with D172's round. It merged into main later the same
    evening, on 16 November (050aa741).
  - **The design note** came with it, `docs/LOOPING_REPLAY_DESIGN.md` (ruled 16 November), with the
    writer's loop block, the interim planarian loop's builder and one development run of that loop,
    not judged.

## FR-12 — The declarations manifest, readable by the viewer (D185)

- **The request.** The visualizer session proposed it on 16 November 2026. Its full field list is in
  `visualizer/docs/LAWS_LIBRARY.md` §7.
  - One JSON file, written by the engine from its registries at a revision, with an entry for every
    registered law, operator and kind.
  - Each entry carries its id and version, interface, host and family; its provenance and
    citation; its declaring module; what it reads, writes and provides, with their roles; its
    ledgers and energy roles; its units and signs; and the models that declare it.
  - A status level is copied only from a record that states one, otherwise it is `null`.
  - Older families are listed by ID only and flagged legacy (D196).
- **Why it is general.** The viewer's laws library, the docs and the contributor guide read it, so
  contributed modules appear without hand edits (D185). The viewer never imports the engine: it
  reads the file.
- **The stable contract is the file's versioned format,** not any Python module (`cells.modules` is
  provisional, D195).
- **Status:** accepted, since D185 already decided the manifest. It is being built in seam F of the
  core-seams pass (D195).

## FR-13 — Molecular machines, individually and in aggregate

- **The request (D204).** It came from the user on 17 November 2026, first through the visualizer
  session, then to the lead directly.
  - **The viewer** gains a "Machines" tab: a catalogue of molecular machines gathered per species,
    as the proteins were.
  - **The engine** models them "both individuall and in aggregate in a cell or whatever, LODs based
    on what is being looked at".
  - **The first question is the user's:** "if there is something missing in our core archtecture
    or if they can be naturally modeled there".
- **Standing scope: D140.** Cells models the assembly of folded subunits into complexes and
  machines, from protein cages toward the proteasome and larger, and how the machines are used.
  Protein folding itself is not simulated.
  - On 16 November the user also asked for the nucleus, the Golgi apparatus and ribosomes "modeled
    to some extend, not protein folding level (yet)". That is recorded in
    `visualizer/docs/CELL_STRUCTURES.md`.
- **What exists today:**
  - membrane machines with laws: channels, pumps, exchangers and junctions;
  - `capsid_graph@1`, the first assembly case: one prescribed 20-site cage in a fixed bath
    (`docs/CAPSID_ASSEMBLY.md`);
  - `cells.assembly_lineages@1`, the stochastic assembly family built for GARD (D192, D197);
  - seam A's cycle contract: Hill cycles, the Wegscheider check and the J·ΔG guard
    (`docs/CORE_SEAMS_DESIGN.md` §16);
  - the relationship tables (`cells.relations@1`, D202) and the declarations manifest (FR-12).
  - **What is absent:** there is no model of a ribosome, RNA polymerase, ATP synthase, proteasome,
    translocon, flagellar motor, chemoreceptor array or attachment organelle.
- **The levels to scope.** This is the lead's framing, made with the advisor. A machine is one entity
  with three layers, not one model per machine:
  - **aggregate:** copy numbers and rates, with what the machine consumes and produces booked on the
    ledgers of the compartment it sits in;
  - **cycle:** the states of the machine's working cycle;
  - **assembly:** its subunits, their stoichiometry and the order they join.

  The level of detail follows what is looked at. So the layers must agree where they meet, and a
  switch between them must keep conserved accounting.
- **The first machines are chosen by constraint,** not by the catalogue's order:
  - the engine already carries what they consume and produce;
  - free-to-read data supports a judged check (D186, D201);
  - more than one organism target needs them.
- **Status (D209):** no model yet.
  - **M0 now:** the viewer's catalogue, labelled illustration.
  - **M1 next:** ATP synthase as general pieces, after the core-seams pass and D193's synthesis law.
    Its build plan is [`MOLECULAR_MACHINES_DESIGN.md`](MOLECULAR_MACHINES_DESIGN.md) §10.
  - The viewer's catalogue fields will follow what a declared model carries in the manifest once
    one exists.

## FR-14 — Declared extension of laws, operators and models

- **The request (D205).** The user asked on 17 November 2026, "is it possible to extend a model or an
  operator, like object oriently?", and then: "put the oo extension on the backlog".
- **What works today.** This was checked by planting subclasses in a scratch registry at seam F's
  registry head 6a0a9dc6, on 17 November.
  - A subclass of a law interface (`ChannelLaw`, built from `kv1p5_mh@1`'s fields) passes the law
    template's checks and registers under its own ID.
  - A subclass of a built-in operator (`OsmoticWater`) registers under a new ID. The operator
    contract checks it again at registration.
  - A subclass under a built-in `cells` ID is refused. Each built-in ID is one object, so a run
    cannot silently change meaning.
  - Models extend by composition. One composite model runs @3's step plus declared operators,
    and new combinations are definitions, not models (D143, under D142's design rule). D191 rules
    only how a composition reads fields.
  - A registry's `extended(...)` is a scoped copy with extra pieces planted in it. It is not
    extension.
- **What is missing:**
  - **A declared "extends" link:** the parent's ID and what changed, like a citation's departures.
    It would live in the registries and the declarations manifest, so the library and the viewer
    can show a family tree.
  - **Inherited checks:** the parent's contract and reference tests also run on the child.
  - **Rules for a child** when its parent moves to a new major version.
- **Why it is general.** It follows D142's object-oriented design. Molecular machines (FR-13) are a
  likely first use: one general machine cycle, specialised per machine.
- **Status:** requested; not scoped. FR-13's design note covers it, as part of the user's question
  about the core architecture.

## FR-15 — Junction-crossing and charged species in the species operators

- **Where it came from.** The gap-junction replication (D207) found it on 17 November 2026. In the
  public preprint 10.64898/2026.09.02.748840, a microRNA is made in cells and crosses gap junctions.
- **What refuses:**
  - **F1, narrower than first reported.** `species_common.check_impermeant` covers only @3's own
    constant-field junction route, for a species an operator writes.
    - A neutral species on the passive-routes kind (`cells.passive_routes@1`,
      `passive_neutral_permeation@1` on a junction host), made and destroyed by
      `local_species_reactions@1`, is admitted.
    - So the preprint's linear model runs as written, unqualified, converging at second order
      (dev-04). Its exact Norton equivalent serves as its check.
    - The first report said the model as written is refused. That was corrected the same day.
  - **F2:** the passive routes' neutral law carries valence 0 only, but the preprint's microRNA
    drifts with valence −1. The species operators also refuse charged species on @3's own routes.
- **Why it is general.** Any signalling species that cells make or use and that also crosses
  junctions needs it: second messengers, small RNAs, metabolites.
- **First step, done:** the reason for `check_impermeant`'s refusal was found (F1 above). What remains
  is F2.
- **Status:** requested; awaits the user's go. The lead recommends it first of the gap-junction
  features. (18 November 2026, D219: scheduled with the kinds and @3 owners after their current
  work.)
- **F2's direction (the lead's rulings of 19 November 2026): S1 + P2.**
  - **S1, built on `local_species_reactions@1` in place (D148, a widening).**
    - Every reaction conserves charge, Σνz = 0, checked in integers.
    - A charged row keeps @3's own routes only as a declared `counter_ion` that @3's
      explicit-rate bound covers (species_common.check_counter_ion). A charged trace row stays
      refused there.
    - A charged source with its counter-ion is a source reaction, for example ∅ → X⁻ + K⁺.
    - Exchange stays neutral.
    - **Limit:** charged turnover routes wait for a `scheduled_species_turnover@2`, when a
      consumer needs exact first-order clearance of a charged row.
  - **P2, next:** a charged constant-field route law on the passive-routes kind
    (`passive_constant_field_permeation@1`), on patches first.
    - Junction hosting waits for the @3 owner's answer on two points: whether the field solve's
      floating-component residual must include a kind's cell-to-cell current, and whether
      KindRates gains a junction_flux.

## FR-16 — Junction gating and availability

- **F3:** @3 hosts one junction law, `junction_voltage_relaxation@1`. The preprint's Cx45 gate needs a
  two-state voltage gate in the manner of Chen-Izu. The existing law's best fit is off by 0.05.
- **F4:** a junction has one minimum open fraction for every species. The preprint's microRNA curve
  needs a per-species floor (0); one floor for all is off by 0.11.
- **F5:** regulated junction availability combines the two sides only by product. The preprint
  needs min and mean as well.
- **Why it is general:** connexin-specific gating and permselectivity are general junction
  physiology.
- **Status:** requested; awaits the user's go. (18 November 2026, D219: scheduled with the F owner,
  after its per-law extractions, and with the @3 owner. Not started.)

## FR-17 — Field solves beyond 2048 nodes

- **F7:** the field solve is capped at 2048 nodes. The preprint's 3D table needs a 25³ field, 15,626
  nodes.
- **A second consumer: mitochondria (D210).** Compartment nodes count toward the cap, as cells and
  outside nodes do. K cells of N compartments, with B other outside nodes, allow
  N ≤ ⌊(2,048 − B)/K⌋ − 1: 2,046 for one cell in one bath, 126 per cell for 16 cells, and 14 for
  FR-1's 127-cell sheet. Any field-input provider, every event door among them, lowers the cap to 64
  field nodes ([MITOCHONDRIA_DESIGN](MITOCHONDRIA_DESIGN.md), addendum A.3).
- **A route that may fit compartments better than raising the cap:** condensing face-free
  compartment nodes out of the dense solve, which is exact. It is FR-1's condensation door, a new
  solver ID (D147; [CLOSED_COMPARTMENT_DESIGN](CLOSED_COMPARTMENT_DESIGN.md) §3.6, §8), and it also
  removes the 64-node cap's reason for compartment doors.
- **Status:** requested; awaits the user's go. Its consumers are the 3D table and, unless
  condensation serves them, mitochondria. (18 November 2026, D219: scheduled with numerics. Its
  owner is named when a seat frees, and FR-1's condensation door is the preferred route. Not
  started.)

## FR-18 — The composite's energy check at moderate step sizes

- **The finding.** @3's energy check (2e-3 under ARS(2,2,2)) refused neutral-species junction worlds
  at dt × rate from 0.08 to 0.31, well inside the stability bound of 1. Two dt studies show the error
  is second order, with a coefficient that depends on the world. The replication passed by using
  dt × rate ≤ 0.04.
- **What is asked of the core:** review whether the check's tolerance, or the step-size advice that
  goes with it, should change. It is not loosened for one experiment.
- **Status:** reported to the core.

## FR-19 — The passive routes' heat-share sign test at rounding level

- **The finding.** `passive_neutral_permeation@1`'s exact heat booking
  (`src/cells/kinds/passive_routes.py`, `_raw_sums` and `book`) refuses a step if any
  exact route's heat share is negative, with no tolerance. The raw-sum check beside it does allow
  `RAW_SUM_FACTOR` eps.
- **Where it showed.** The gap-junction replication's 1D tissue line has healthy cells that start
  identical, and its threshold search was refused at most coupling values.
- **The measurement.** A refused step was replayed with the engine unchanged
  (`/mnt/workspaces/Cells/gap-junction-20261117/probes/neither-fail-01/`):
  - share −2.1e-35 RT·fmol, about 40 times inside the raw-sum check's own bound for its terms;
  - transfer 4.8e-20 fmol, below the amounts' resolution;
  - potential difference 2 ulp of ln c.

  It is rounding, not a transfer against its gradient.
- **Scope.** FR-5's cargo routes use the same booking, so FR-5 can meet the refusal near equilibrium.
  FR-4's proton leak does not.
- **Fixed on main** (merge 49494e49, of branch `passive-share-tolerance` at 3d8e7b3b):
  - **The rule:** a share is refused only below `−RAW_SUM_FACTOR·eps` times its own terms, in the
    share's units. Admitted shares are booked as computed, so the ledgers close exactly.
  - **The gates:** G1 is 113 of 113; tiers 1+2 changed 0 of 514 files; FR's bitwise landing set
    passed. In crossrev only the kinds set's three checked steps differ, in the predicate, by design.
  - **The law keeps its ID** as an in-place fix (D148). Leaving qualified worlds on `@1` with a new
    `@2` stays the user's alternative.
  - **The replays:** the replication's previously refused points now run the full 20,000 s
    (`/mnt/workspaces/Cells/passive-share-tolerance-20261117/`).
- **Follow-up, the lead's call: the band near 1 mM, closed on branch `passive-share-band` and landed by merge a7122a43 on 18 November.**
  - **Why.** Near 1 mM the first floor still closed, since its terms scaled with |μ̄| while the
    potential keeps the ulp of ln c + 1.
  - **The fix.** The floor's scale adds the potential's evaluation rounding, (|μ̄_in| + |μ̄_out| +
    2)·|m|, so at 1 mM it is 32 eps |m|.
  - **On the closed pair:** all 47 rounding-level cases are admitted (leads of 1–16 ulp, 1e-4 to
    100 mM), the worst at half its floor. At 1 mM a share at twice its floor, or a million times
    below it, is still refused.
  - **Unchanged:** previously admitted steps, since the floor only moved down. The same gates
    apply, and crossrev's kinds record is renewed again at its landing.
  - The replication never reaches the band, since its concentrations stay at or below 0.1 mM.


## FR-20 — A pulse and washout for assembly populations

- **The request (user, 20 November 2026; D237).** At a declared time, replace the exterior of an
  assembly population (vesicles or shell-bounded particles in their medium) with fresh, tracer-free
  solution.
- **What is kept:** each assembly, its gate state and its bound tracer, including tracer held at an
  exposed-site control.
- **What is recorded:** the material and the energy exchanged by the replacement.
- **The wash bath is finite,** so released tracer can re-enter.
- **What exists:** the vesicle-population accounting on the ol3-engine branch (OL2 milestone 3)
  already covers much of it. That branch has not landed; D230 orders its landing behind core and
  FR-1 to FR-10.
- **Next:** a design note (D142), as a general feature (D144).

## FR-21 — A prescribed shell that owns a lumen and an exchange conductance

- **The request (user, 20 November 2026; D237).** Let a prescribed protein shell own a lumen and an
  exchange conductance, independent of the membrane's inventory and of its binding-site count.
- **Why:** to attribute a result to area or to permeability. Today every cross-phase reaction routes
  through the membrane phase. The existing two-state gate is enough to test kinetics, but not to
  separate those two causes.
- **Concrete exposed-site case (Vaults, 20 November 2026; D240).** One particle has one occupied
  site (one bound tracer), three vacant sites, and five free tracers in the finite exterior pool.
  Both vacant sites and occupied complexes belong to the particle, independent of its membrane
  inventory. Direct reversible binding consumes an exterior tracer and a vacant particle site;
  release restores that site and returns the tracer to the finite exterior pool. The current
  geometry parser refuses this interfacial reaction without a declared geometric encounter law;
  this is a required FR-21 capability, not an already supported configuration.
- **Requested control:** immediately after a tracer-free wash, exterior tracer is zero, the
  particle still has one occupied and three vacant sites, and the removal ledger contains five
  tracers. Total site count stays four; retained tracer plus removed tracer stays six. Subsequent
  release and rebinding use the finite bath. A proposed alternative representation must reproduce
  the declared direct binding and release time courses, not only an endpoint or equilibrium.
  Placing sites in the replaceable pool does not preserve their ownership; an intermediate
  membrane-join step is not presumed kinetically equivalent. FR-20's timed replacement can proceed
  independently, preserving every slot-owned place as designed.
- **Next:** a design note before any code (D142).
- **The site step's acceptance (the requester, relayed by the user on 20 November 2026; D244,
  D246).** In `cells.assembly_lineages@2`, a particle with geometry supports X@pool + S@membrane ⇌
  XS@membrane through `cells.stochastic_mass_action@1`. It is admitted only when the site and the
  complex are declared, and undeclared pairs stay refused. Built from the one-particle fixture of
  `tests/unit/test_assembly_lineages_v2_population.py`, with FR-20's timed wash:
  1. Immediately before the wash: 8 free X in the pool, 4 vacant sites and 2 occupied sites.
  2. After replacing the pool with an equal volume of X-free liquid:
     - the removal record holds 8 X;
     - the fresh pool holds 0 X;
     - the particle keeps 4 vacant and 2 occupied sites.
  3. One release gives 1 free X, 5 vacant sites and 1 occupied site. A rebinding restores the
     post-wash counts.
- **The shell's acceptance (the requester, relayed by the user on 20 November 2026).** A model
  declares the shell's area, its lumen volume and a permeability per tracer. With a neutral tracer
  at fixed inside and outside concentrations and a fixed gate state:
  1. doubling the area while halving the permeability preserves both the entry and the exit rate;
  2. doubling the permeability alone doubles both rates;
  3. changing only the wall's inventory or the binding-site count preserves both rates and the
     declared lumen volume.

  The report names the tested revision.

## FR-22 — Checkpoint and resume for the stochastic assembly runner

- **The request (user, 20 November 2026; D237).** Add checkpoint and resume to the version-2
  stochastic assembly runner.
- **The qualification:** a run interrupted around a wash (FR-20) reproduces the uninterrupted run's
  event trace, molecule counts and energy ledger exactly.
- **Short controls can proceed now,** before FR-20 exists.

## FR-23 — Timed bath changes beside binding sites on distinct finite nodes

- **The request (user, 20 November 2026; D239).** Allow a timed bath change and binding sites in
  one world when they act on distinct finite nodes.
- **What refuses today:** each operator parses on its own, but together they fail, because both
  reference `extracellular_amount_reference`, even when they access different nodes (the
  composition contract, docs/PUMP_COMPOSITE.md).
- **Acceptance:** at the event boundary, the bath records the dose, and occupied sites keep their
  bound material.

## FR-24 — Binding-site occupancy as an input to reaction rates

- **The request (user, 20 November 2026; D239).** Let a reaction read a named site population's
  occupied amount, accessible capacity, or occupied fraction as a rate input (the coupling
  operator's sources, `species_regulated_availability`).
- **Acceptance:** changing occupancy changes the linked rate, and disabling the link leaves the
  binding dynamics unchanged.

## FR-25 — A reusable one-gene expression unit

- **The request (user, 20 November 2026; D239).** Make the planned one-gene expression unit
  reusable. It exposes RNA and protein amounts over time, with precursor consumption and energy
  accounting. Its induction and decay are verified against independent references, so other
  models can use it as a component.
- **Where it stands:** this is gene regulation's option A (D235). The equation sheet is tagged
  (`gr1-sheet-2026-11-20`), and its code-blind references are under way. G4's operator is built
  as this reusable component.
- **Backlog: per-cell readouts of new RNA (a reviewer's follow-up, relayed by the user on 20
  November 2026).** A runnable example that reports, for each cell and gene, total RNA and the
  transcripts started, completed and degraded. For a chosen time window, it also reports how many
  transcripts completed in that window are still present when sampled, like a pulse label. Raw
  per-cell values are kept, so each assay can apply its own detection rule. A documented
  calculation from existing outputs is enough. It names its Cells revision, units and sampling
  times. Two controls make the readout checkable:
  1. **RNA turnover.** Start with 100 unlabelled copies, a one-hour half-life and steady
     production of 100·ln 2 copies per hour. Mark every transcript completed in the first hour,
     then continue production unmarked.
     - Total RNA stays at 100.
     - Of the 69.31 copies expected in the marked hour, 50 remain at its end and 25 an hour later.
  2. **Responding cells.** Two groups make [0, 0, 20, 20] and [10, 10, 10, 10] new copies per cell.
     - Both average 10.
     - At a threshold of one new copy, 50% against 100% of cells are positive.
     - The positive cells average 20 against 10 copies.

  The development build already shows two effects:
  - a gene's initial regulatory state changes its output under identical input, and disabling
    that link erases the difference;
  - after new starts are switched off, chains already in progress finish another 2.46 expected
    copies in the next minute.
- **Backlog: the protein version (a study's request, relayed by the user on 20 November 2026;
  D248).** A short protein-production export from A1: time, protein amount, cumulative protein
  completions and cumulative degradation, with units. Also, how to recover the protein made during
  a chosen window that survives to sampling, as a pulse label measures it. In the references,
  protein completed during minutes 60–90 was 7.46 times the net increase. The engine's development
  export (revision f96a9606) already carries these columns. A documented calculation of the
  surviving cohort from them is the first answer.
- **High-priority follow-ups (a reviewer, relayed by the user on 20 November 2026; D251).**
  - **A restart example with a rate change at the join.** It shows which interval owns the event, and
    whether the joined counters reproduce the uninterrupted run.
  - **Age- or region-selective loss.** The native counters recover the surviving cohort for one
    well-mixed pool with age-independent loss. The reviewer reproduced it: in minutes 60–90,
    2.01673e-5 fmol completed and 1.32977e-5 fmol survived, while the pool grew by 2.70386e-6 fmol.
    No field today identifies which population lost material under age- or region-selective loss.
    That needs labelled cohorts or regions (FR-33).

**FR-25's registered acceptance, scored (22 November 2026, 01:53 UTC): inconclusive under the rule; no world
failed.** The rule (fr25-rule-registered-2026-11-22), the table (fr25-table-registered-2026-11-22) and the
declared retry's table (fr25-retry-table-registered-2026-11-22) were each tagged before any comparison
with G2. The OL builder judged independently, recomputing both tables with its own code with 0
differences.
- **28 of 32 worlds-by-set pass:** 16 at dt 0.5 and 12 more at the retry's dt 0.25. Every required time
  is matched, and every judged readout is within its tolerance; the largest gap is 0.399 of tolerance.
  The effective factor against the Richardson estimate has a median of about 0.99. A planted failure
  was caught in each round.
- **4 are inconclusive after the one declared retry:** A1 at both test instances (C_tx_3's observed order
  3.69, above the 3.5 cap) and pol T=100 at both (E_tx and F_pol at 2.40, below 2.5, rising from 2.26).
  So FR-25 does not pass under the registered rule.
- **What a pass covers:** G2's trajectories in the registered readout classes, within 3 times the
  step-error estimate at the scheme's formal order. It does not cover each move's ΔG (dG_*) or A1's u(t),
  which G2 publishes but the engine does not export, nor the engine-only route extents, which G2 does not
  publish. Corners and interior points stay with G6.
- **Verdicts:** fr25-judge/verdicts.json (sha256
  ac6e44cc2b4c90051bce215a9ace737be0200c0e7d5d31604dbbf8da3d171461) and verdicts-retry.json (sha256
  2c001ef3f6355b46dd4731234905ce3269409da0993414da098699f8955455b4), in the OL builder's workspace.
- **The next step is the user's (D277):** record FR-25 as inconclusive; or register a revised rule before
  any new run, for example a second finer triple for pol T=100 and a treatment of superconvergent
  readouts such as A1's C_tx_3; or bring ΔG and u into scope with a later registration.

**FR-25's final verdict (22 November 2026, 11:26 UTC): inconclusive under the registered rule; 30 of 32
worlds-by-set pass, none failed (D282).**
- **The final retry,** registered at fr25-rule-retry2-registered-2026-11-22, with its table at
  fr25-retry2-table-registered-2026-11-22 and all from one snapshot:
  - pol T=100 is now ready and passes at both instances (largest gap 0.358 of tolerance; a planted
    failure fails);
  - A1 stays inconclusive at both. C_tx_3's observed order was 3.94, then 3.69, then 1.49 across the three
    triples, never settling inside [1.5, 3.5].
- The OL builder recomputed the final table with 0 differences. Verdicts: fr25-judge/verdicts-retry2.json,
  sha256 bbd41afb329b7ec2546236b124662ca1bb3355adc68b60664fe7e72ecf1e722a.
- **Plainly:** A1 is the world that carries the request's induction and decay under a regulator switch, so
  that world is not judged. The 30 passing worlds-by-set cover the polymerase-limited, ribosome-limited and
  two-gene chains against G2, within 3 times the step-error estimate at the scheme's formal order.
- The registered sequence is spent. Any further test of A1 needs a new registration, which would come
  after these results and must say so.

## FR-26 — Owned state when a cell is replaced

- **The request (user, 20 November 2026; D239).** Define what happens to owned state when a cell
  is replaced:
  - the incoming cell is initialised from its template;
  - environment-owned material is preserved;
  - what leaves with the departing cell is recorded.

  Today the site-occupancy operator guards against replacement.
- **Minimal acceptance:** the material balance closes across one replacement, with occupied sites
  and active reactions.

## FR-27 — A timed partial wash of a finite compartment

- **The request (another Cells user's review, relayed by the user, 20 November 2026; D245).** At a
  declared time, collect a fraction f of a finite compartment's well-mixed liquid into a recorded
  sample, refill the same volume with a declared buffer, and leave bound material in place. The
  removal, the supply and the free-energy change are booked exactly at the event.
- **Why:** a falling tracer signal can mean release from a specimen, binding to the vessel wall or
  recovery by a detector. Keeping those amounts apart across a wash needs the wash to be one
  operation with its own books. Today the bath schedule doses held baths only (FR-10), and FR-23
  keeps finite compartments out. FR-20's pool replacement works in the assembly family only, with
  a whole pool replaced by a declared composition.
- **Where it stands:** everything else in the review's example runs today. In the review's run the
  wash was applied between two runs on the host, so each run kept its own books. The design note
  states the operator's semantics against FR-20's replacement, so the two are not two laws for
  one mechanism (D175, D210).

## FR-28 — Binding sites owned by a compartment's surface

- **The request (the same review; D245).** Let a binding-site population belong to the surface of
  a finite outside node, such as a vessel wall, facing that node, with binding only.
- **Today:** a site population's owner must be a cell's patch or a contact. The review placed the
  wall's sites on an inert stand-in cell that exchanges nothing; the numbers are unaffected.
- **Where it stands:** a new owner kind for `site_occupancy@1`, a change to parse and layout only.
  It queues after FR-26 on `site_occupancy.py`.

## FR-29 — An optional proton-return mode for ATP-driven proton pumps

- **The request (the Lean project's biological review, relayed by the user, 20 November 2026;
  D248).** Kettner et al. (2003, doi:10.1016/S0006-3495(03)74789-4), Table 2: moving the yeast
  vacuole's pH from 4.1 to 6.0 moved the ATP-dependent current's reversal by −13.0 mV. The proton
  equilibrium shifts by −112.5 mV, and `proton_pump` predicts −112.40 mV at every supported ratio
  of protons per ATP; a tightly coupled pump cannot do otherwise (run by the lead at main).
- **The proposal:** one law, with an optional mode, off by default, in which protons return down
  their gradient while the pump is energized, each mode booking its own movement and dissipation.
  Yeast values are population parameters (D144). The note says which worlds run `proton_pump` today.
- **The test:** the table has five resolved reversals (three vacuolar pH values at cytosolic pH
  7.5, and two other cytosolic pH values). Fit two and predict the rest under the same subtraction.
- **The competing explanation:** other forms of variable coupling. Independent ATP-consumption or
  proton-flux data would distinguish them.

**Confirmed (the Lean lane's biological review, 21 November 2026).** The reopening evidence is the
one D268 names: an ATP-dependent difference current at vacuolar pH 3.1 to 3.5 under Kettner et al.'s
Fig. 3 protocol.

## FR-30 — Homotypic Cx43 junctions with two relaxation times

- **The request (the same review; D248).** The generic `junction_voltage_relaxation@1` relaxes once,
  in 50.0 ms at −100 mV. Sahu and Bera (doi:10.1371/journal.pone.0060506) measured 70 ± 5 and 931 ± 54
  ms in the same decay, in Cx43 cell pairs. Moreno et al. (doi:10.1161/hh0402.105667) found 0.25 and
  3.18 s at 60 mV.
- **Where it sits:** the Cx43 variant already planned in PROTEIN_CATALOGUE_PLAN.md, as a new
  versioned law or parameter set with cited values.
- **The test's limit:** the two preparations differ in voltage. A fit at one voltage leaves the
  voltage dependence free, so a prediction needs a voltage series. Tracer transfer is tested
  separately, since electrical coupling and dye transfer can differ.
- **After N2,** which is changing the gate's file.

**The benchmark (the Lean lane's biological review, 21 November 2026).** At −100 mV the reference
single gate gives 50 ms, while seven N2a cell pairs showed two decay times, 70 ± 5 and 931 ± 54 ms
(Sahu and Bera, Table 2, PMC3607587). The development two-gate host is to be benchmarked against a
held-out voltage series; the published two-component fits leave its predicted mixed amplitude
unmeasured. This still waits on the user's downloads.

**The Lin, Crye and Veenstra 2003 extraction (21 November 2026, 23:13 UTC).** The extractor applied the
registered split (tag fr30-lin2003-registered-2026-11-21) and sealed the held-out file:
held_out.json sha256 0451caa00972a116673077293c3173378d78c7bde0609e697031aefe8defafdc; fit.json 434fd8104eaecedd68234a76aa607d1569b679ba1f315c636dbf5226545d3ebc.
- The paper fits each step's decay with a single exponential. It reports one decay time per voltage
  (Fig. 5B) and no slow time constant, amplitudes or step-end conductance at any voltage; a slower
  phase is mentioned only as "data not shown".
- So no held-out voltage carries both relaxation times, which is the registration's "undetermined"
  condition. The checker confirms it.
- The next paper is taken only under an amendment registered before it is read (D276).

**The Desplantez et al. 2004 extraction (21 November 2026, 23:53 UTC), under section 13.1.** The held-out
file is sealed: held_out.json sha256 48f061c074414b6ea8b1a88e64964110fa05edc5abfaec57c657cebdb7aae53d; fit.json 29cd94719305e3155a8bc34d93d2b3e74bdfcb1ed93d56fab74a20fec33b5be1.
- For homotypic Cx43 the paper prints a legible decay time constant at only two magnitudes (Fig. 9B),
  and 60 mV of those stays in training.
- The second exponential is "data not shown", with no slow time constant or amplitude at any voltage.
- So the extractor reports both "undetermined" conditions (rules 1 and 4). The checker confirms them
  before Moreno et al. 2002 is opened, and no fitter sees these files.

**The Moreno et al. 2002 extraction (22 November 2026, 00:09 UTC), under section 13.1.** The held-out
file is sealed: held_out.json sha256 f98f88124ee8e88c3adbd76fb08a08c62c788da98b371aba8fcf29f23bdd0a9d; fit.json f46e8f37b928eec8c0c680f7065037756e6fd6c877cb5f53e5965f623ab907c5.
- For wild-type homotypic Cx43, Table 2 prints both decay time constants at only three magnitudes (60,
  80 and 100 mV), in N2a cells and in oocytes. The smallest and largest stay in training, so at most one
  magnitude can be held out.
- That is rule 4's "undetermined" condition, resting on a printed table rather than on legibility. The
  checker confirms it before Snipas et al. 2020 is opened.

**The Snipas et al. 2020 extraction (22 November 2026, 00:31 UTC), the last fallback.** Sealed:
held_out.json sha256 98dc834067563bf768557d1e6e8b7e198b1d7e2d08178c06ceac4c075ab2da4b; fit.json f93f9a6e4480df719b35219da2f4dab2854cd9b610d32046bb997017840e34d6.
- For wild-type homotypic Cx43, the paper's own measured data are a voltage ramp (Fig. 4A) and
  action-potential-like stimuli (Fig. 5D). It reports no step decay and no time constant at any voltage,
  and its other curves are model output.
- So rule 4's "undetermined" condition holds, resting on the text and captions alone; the checker
  confirms it.
- With Lin, Desplantez and Moreno already undetermined, the registered order is exhausted. What follows
  is the user's decision (D277).

**The Xu et al. 2013 extraction (22 November 2026, 11:05 UTC), under section 13.3.** Sealed: held_out.json
sha256 afa1f3e7c406580f3631205094a4633b3ba696bf02f6c85ccd6191c2d339f943; fit.json 49f36c4798c6871672a48d558aad08fd3a4085cd28540239af5edace41c077a1.
- The paper reports two on-rates per voltage, K = (1 - P_open)/tau, from two-exponential fits, but not
  the time constants themselves. P_open is neither reported per voltage nor defined, so the law's times
  cannot be mapped onto the paper's rates without inference. The times appear only in one example at
  -120 mV.
- **The lead's ruling**, made blind to every value: the strict reading applies. Section 13 judges
  relaxation times, and rule 2's "read the way the paper reads its data" cannot be applied without the
  paper's P_open.
- The extractor's legibility principle, stated before reading, stands. Corner fragments are not
  counted, since accepting them after opening would be post hoc.
- So Xu 2013 is undetermined. The checker confirms it before Lin et al. 2010 is read, and Lin 2010's PDF
  comes from the user.

**Section 13.3's candidates (22 November 2026, 15:10 UTC; D291).** Lin et al. 2010 is undetermined: the
Xu ruling extends to its on-rates without P_open, and its atrial myocytes fall outside the native
admission. Ek-Vitorín et al. 2018 is undetermined under rule 1, with one magnitude only. The registered
candidates are exhausted. The next step is the user's: FR-30 stays development-only, or a further
metadata-only search.

**Status (24 November, D343): parked, development-only (D262).** Two relaxation times at the cited voltages; the voltage dependence is unvalidated. Twelve papers have been tested: one qualified (Revilla 1999) and failed (D320), and the rest were undetermined by their data's structure. It reopens when an experiment needs the series-gate law beyond development, or when a source with per-voltage τ_fast and τ_slow at two or more magnitudes is in hand. One labelled, non-blind diagnostic follows: a joint fit to Revilla's six voltages.

**Status (24 November, later, D344): reopened narrowly (the user).** Two labs confirm two decay phases at −100 mV, which the shipped single gate cannot produce. `junction_series_gates@1` becomes usable for two phases at a declared voltage, calibrated per preparation. Its voltage dependence stays unvalidated, and its predicted third amplitude stays unmeasured. First, a labelled, non-blind joint fit to Revilla's six voltages; then a design note and a gated landing narrow D262.

## FR-31 — Vesicle rupture during a steady tension hold

- **The request (the same review; D248).** The assembly model tests rupture only at a state change.
  In a DOPC cohort (Shibly et al. 2016, doi:10.1016/j.bpj.2016.09.043) 8 of 19 vesicles survived 40 s
  and 2 of 19 survived 110 s under a held tension; a constant rate fitted to the first count predicts
  1.76. Karal and Yamazaki (doi:10.1063/1.4930108) report rates at one tension and two temperatures.
- **The proposal:** an optional rupture event, off by default, that competes in physical time when
  chemistry is idle, using the existing release and energy accounting. OL5's registered lysis rule
  stands.
- **What it needs:** rupture rates at more than one tension, and the deterministic representation
  (OL6), since giant vesicles are far beyond exact-event sizes. It interacts with FR-20's same-time
  rule, FR-22's checkpoints and F12's extinction, so a design note comes first, before OL9 registers.

**The evidence restated (the Lean lane's biological review, 21 November 2026).** At constant tension
and 12 °C, DOPC vesicle survival fell from 50% at 92 s to 12.5% at 268 s (doi:10.1063/1.4930108). A
fixed rupture threshold cannot produce continuing failures under a held load, so FR-31 needs rupture
rates across tensions, as it already states.

**The tension series is in hand (the Lean lane, 22 November 2026; raised to high priority by the user, D286).**
- **The data:** Karal and Yamazaki's Figure 2a (doi:10.1063/1.4930108) gives first-rupture rates for pure DOPC
  vesicles at 7.0, 7.5 and 8.0 mN/m, at about 25 °C and 32 °C, from 3 independent experiments of 20
  vesicles per setting. At 25 °C the rates are 0.00263, 0.00556 and 0.0153 s⁻¹. The cited log-rate readings
  are in `lean/checks/data/karal2015_rupture_rates.json` (merged at 81916b5d).
- **The test it allows:** fit a declared rupture law on the two end tensions and predict the middle one, at
  each temperature. Interpolating linearly in log rate overpredicts the middle by 14% at 25 °C and 21% at
  32 °C.
- **Disclosure:** the middle values were read by the Lean lane and the lead before any law was registered.
  The law's form is fixed before fitting, and only the end tensions enter the fit.
- **Still needed:** the deterministic representation (OL6). A design note comes first, shared with FR-39.

**The blind test passes (D298, 16:39 UTC).**
- **Set 1,** the other temperature columns, two-sided: 5 of 5. That is three in range and two
  extrapolated, the closest at 0.79 of its tolerance. The unscored 12 °C point would fail by 0.023.
- **Set 2,** Shibly's osmotic rows, one-sided: 5 of 5. These are weak tests.
- **Caveats:** the tolerance is wide (t = 4.303, about 28% in rate), and the in-sample misfit at
  7.5 mN/m stands. The two declared premises go with every verdict.
- Phase A's engine (the pore clock, the held tension and the pair check) is in its last slice before its
  gate.

## FR-32 — A DOPC swelling validation record for the water operator

- **The request (the same review; D248).** The tissue water operator's compliance, fitted to one
  dilution's swelling, predicted 2.57% at a second, against 2.6 ± 0.1% measured (Shibly et al. 2016,
  Fig. 2B). It is one fitted value and one held-out point, specific to that preparation.

**The comparison restated (the Lean lane's biological review, 21 November 2026).** DOPC swelling
was 2.6 ± 0.1% against 1.7% from the calibrated fixed-area model; the existing compliance calculation
gives 2.57% (PMC5112947). It stays routed to the next water-operator landing.

## FR-33 — Regional labelled-protein readouts: redistribution against degradation

- **The request (a study's request, relayed by the user, 20 November 2026; D248).** A reported
  48-hour decline of a synaptic protein traces to one imaging study, whose measurements a later
  paper reused, so it is one source. A separate lab observed the protein moving between synapses.
  So redistribution is a competing explanation.
- **What Cells reports:** labelled protein inside the measured region, outside it and across the
  whole cell, from existing components.
  - **Pure redistribution predicts** a compensating gain elsewhere and a stable total.
  - **Degradation predicts** a falling total.
- **The first step:** identify any missing export field, so the study can freeze both predictions
  before fresh measurements are scored.
- **High-priority follow-ups (a reviewer, relayed by the user on 20 November 2026; D251).**
  - **A maintained compartment-transfer example** that exports the donor, the receiver and the
    cumulative loss together.
  - **The control:** the same fading donor signal under transfer and under local destruction, with
    only transfer increasing the receiver.
  - **A field** that names the population that lost material under region-selective loss.

**The Lean lane's check of label rows (21 November 2026).** Two neutral labels summed to the parent
tracer at both nodes across all 101 recorded times: the parent stayed at 1 fmol on the right while the
labelled part rose from 0.1 to 0.299999 fmol. For a charged tracer on a log-mean face, splitting a +1
tracer into opposing 90:10 label gradients at +10 mV carried 72.819% of the unsplit flux. The compiled
face reproduces the proved ratio. So D1's guarantee covers independent neutral label rows with a shared
diffusion coefficient, and charged log-mean faces stay outside it, as D1's design refuses them.

**A caveat on D1's heat (the Lean lane, 22 November 2026).** Splitting a neutral species into
provenance labels preserves material transport exactly, but it can change the booked face heat. Each row
books its own driving force, so opposing label gradients book heat where the unsplit species books none.
D1's guarantee covers material and ledgers. A measurement that attributes physical heat to provenance
labels alone remains open, so a label family's face heat is not to be read as the unlabelled species'
heat.

**The requester's answer (22 November 2026, 12:04 UTC, relayed by the user).** "Two named regions of the
same cell joined by one bidirectional face are sufficient for our first test." They ask that both region
identities and volumes be preserved, and that donor label, receiver label, whole-cell label and cumulative
local clearance be reported in the same units at the same times.
- Pure transfer, with labelled production off, should conserve the total label, and the receiver's gain
  should match the donor's loss.
- A separate local-loss control should keep the receiver flat, with clearance accounting for the missing
  label.
- The in-cell compartment path (priced at about 1.5 to 2 days) is not needed for this test. The kinds owner
  builds the two-region example on D1, with no engine change, and an independent checker writes the
  acceptance from these words.

**The first test landed (7d70d63b, tag fr33-first-test-landed-2026-11-22).** `validation/regions/example.py`
(`first_test(case)`) gives two named regions of 1 pL each joined by one face. It reports donor, receiver,
whole-cell label (defined as donor plus receiver) and the donor's cumulative clearance, in fmol at the same
times.
- In transfer, the total is conserved and the receiver's gain equals the donor's loss.
- In the local-loss control, the receiver stays flat and clearance equals the donor's loss.
- The receiver starts at trace under F2's exact face heat.
- The independent checker passed every check within 1.42e-14 fmol, and its planted failure failed.
- The regions are nodes facing the cell, not compartments of it; the requester accepted that for this
  test.

## FR-34 — Channel population readouts: count, availability and signed current

- **The request (a reviewer, relayed by the user on 20 November 2026; D251).** For membrane
  channels, name the fields that report surface count, availability and signed current at a
  declared voltage, with the current's sign convention and units.
- **The control:** with count and driving force fixed, halving availability halves the population
  current.
- **Where it starts:** the FR-7 lane names today's fields (membrane state's units and abundance, the
  routes' availability and their current records). It then builds the smallest maintained example
  with the control, and records any missing field as engine work.
- **Engine work found by the FR-7 lane's desk check (D252), each its owner's:**
  - **Each population's current at a declared voltage,** evaluated from the state, in A, outward
    positive. Today `channel_flux_fmol_s` gives it only at the cell's actual voltage. It belongs to the
    @3 owner, after N2, at about 1–1.5 agent-days.
  - **One record of the effective availability,** the held value times its routed factors. The @3 or
    operators owner, 0.25–0.5.
  - **A flux or current record per route for the kinds' routes,** which today record only a cumulative
    inward transfer. The kinds owner, 0.5–1.

## FR-35 — Timed partial withdrawal of an assembly population's exterior pool

- **The request (user, 21 November 2026, high priority).** Add timed partial withdrawal of a
  well-mixed exterior pool to `cells.assembly_lineages@2`.
- **What happens today** (main beb0ddb5, `site_wash_spec()` in
  tests/unit/test_assembly_lineages_v2_replacement.py):
  - adding `fraction = 0.5` to its replacement schedule is refused;
  - setting the fresh pool to four X instead records eight original X removed and four new X
    supplied.

  A half-volume wash with tracer-free buffer should supply zero X and leave some original molecules
  in the pool.
- **The acceptance test:** start the wash with eight independently distributed free X, four vacant
  sites and two occupied sites.
  1. With half the volume withdrawn, the collected count follows Binomial(8, 0.5): mean 4 and
     variance 2 across independent streams.
  2. At one-quarter withdrawal the mean is 2.
  3. In every realization, collected plus remaining X equals eight.
  4. The sites and the particles' identities are preserved.
  5. The actual material and energy exchanged are recorded.
  6. Restarting across the wash reproduces the uninterrupted run exactly (FR-22).
- **Where it sits:** FR-20's `cells.pool_replacement@1` replaces the whole pool and draws nothing;
  FR-27's `scheduled_compartment_wash@1` is the deterministic counterpart in the inner model. A
  partial withdrawal draws each molecule's fate, so the draw, its stream and its checkpoint, the
  buffer's supply rule and the discrete energy bookings are the design's questions.

**A validation target (the Lean lane's biological review, 21 November 2026).** In 180 passive
droplet splits a nominal one-third branch collected 45.0% of the beads on average (Fornell et al.,
Fig. 2c, doi:10.1063/1.4984131); a second chip retained 28.2% ± 4.4 percentage points SD at a
measured liquid fraction of about 27.2% (Liu et al., Fig. 4, PMC6897560). The two disagree on how well
volume predicts particle sampling, and both concern particles, not molecules. FR-35 withdraws each
molecule with the volume fraction's probability, a well-mixed limit. The informative measurement is
paired liquid volume and particle count for each split. No change to FR-35 now.

**The Lean lane's check of the split heat (21 November 2026).** split_surprisal_kT is booked against
the physical volume fraction f, while the finite-word sampler withdraws each molecule with
probability q. So the exact mean heat for n tracers with tracer-free buffer is −n(1−q) ln(1−f), with
q = f at dyadic fractions such as ¼ and ½. At the largest allowed fraction, f = 1−2⁻⁵³, a tracer
survives with probability 2⁻⁵²: its booked split score exceeds its sampler score by exactly ln 2, and
the mean heat is 8.1572 × 10⁻¹⁵ kBT against the ideal-volume 4.0786 × 10⁻¹⁵ kBT. The per-event energy
accounting passes. The design note and the operator's docstring are being reworded to say so (no
code change). Their search of three passive-split studies (Fornell et al., Fig. 2,
doi:10.1063/1.4984131; Liu et al., Fig. 4, PMC6897560; Deshpande et al., Fig. 3, the mechanical
division of cell-sized liposomes) found none that reports the parent count, the daughter count and the
measured liquid fraction for the same split, the pairing that would separate volume variation from
sampling variation. Biological validation of the heat remains open.

## FR-36 — Age- and region-selective loss within a species row

- **Raised by** FR-25's reviewer (21 November 2026), as FR-25's follow-up 3: loss that depends on a
  molecule's age, or on the region it sits in, within one species row.
- **Covered today:** validation/gene_regulation/cohort.py recovers completion-time cohorts within one
  well-mixed pool whose loss does not depend on age; FR-33's regional export and one-way tracer cover
  regions joined by one-way routes.
- **The build, when needed:** D1 (label families in the species registry, now being built for
  FR-33's two-way tracing) and D2 (an ageing operator, scheduled_species_progression@1, the operators
  owner's), per docs/COHORT_LABELS_DESIGN.md; 2.5 to 4 days in all.
- **Status: deferred (D273).** Outside FR-25's own request; it reopens on a requester's readout that
  needs age-dependent loss.

## FR-37 — Sampling a liquid whose dye is unevenly distributed

- **The request (a user, 21 November 2026; D274).** A pipette can collect half a chamber's liquid
  and pick up more than half its dye, when the liquid near the collection port is richer in dye than
  the rest. The instrument then reports a higher sample concentration, although the chamber's total
  is accounted for. FR-27 withdraws from a well-mixed compartment and FR-35 from a well-mixed
  molecular pool. Can existing operators represent a draw from a particular part of an unevenly
  mixed liquid? Demonstrate it with a runnable example; if something is missing, identify the
  smallest addition.
- **The synthetic test.** A passive dissolved tracer in two liquid regions, A and B, each 100 pL,
  with 8 fmol in A and 2 fmol in B, above the same buffer background. Each case starts fresh and
  collects 100 pL.

  | Collection condition | Expected in sample | Left behind |
  |---|---|---|
  | Draw all 100 pL from A before mixing | 8 fmol | 2 fmol |
  | Mix A and B completely, then draw | 5 fmol | 5 fmol |
  | Draw 75 pL from A and 25 pL from B | 6.5 fmol | 3.5 fmol |

  For each case, report:
  - the volume drawn from each region;
  - the amount and concentration in the collected sample;
  - the tracer remaining in each region.
  Buffer supplied by any refill is recorded separately, and the sample and remainder account for
  all 10 fmol.
- **Inputs.** In this first test, the starting distribution and the volume drawn from each region
  are declared inputs. The answer must say which inputs a Cells user supplies and which Cells can
  calculate from the collection port, flow and timing. That distinction matters experimentally:
  - an assumed dye-rich region can reproduce a high reading;
  - predicting that such a region forms needs separate evidence;
  - measuring the dye left behind tests the explanation.
- **Status: shown with existing operators** (2bba6043; tag fr37-uneven-draw-landed-2026-11-21).
  validation/sampling/uneven_draw.py gives each region its own scheduled_compartment_wash@1 event, at
  fraction = drawn volume / region volume. It reproduces the three cases (8 and 2, 5 and 5, 6.5 and
  3.5 fmol) and records the refill's buffer separately. The second builder wrote its own acceptance
  and confirmed it.
  - What a user declares: the regions and their volumes, the starting distribution, each region's
    drawn volume and time, and the refill buffer.
  - What Cells cannot calculate today: which parts of the liquid a port draws, since it has no bulk
    flow. Mixing in the same world as the draw is also refused (D246), so the mixed case is a
    declared state.
  - The smallest addition for prediction: an advection operator on faces, with the wash's face
    refusal lifted, about 3 to 5 agent-days.
  - Each region's predicted remainder is what a measurement of the dye left behind would test.

**The Lean lane's check (21 November 2026).** They proved that a two-region sample has the chamber's
mean concentration exactly when the regions have equal concentrations or the draw removes the same
fraction of each region. They also reproduced the three declared draws through the compiled runner at
ee0b8106, regional remainders included: 8 fmol with 0 and 2 left; 5 fmol with 2.5 and 2.5; 6.5 fmol
with 2 and 1.5.
- **Experimental support:** their search found two outlets carrying equal flow that measured about 75%
  and 25% of the stock dye concentration (Johnson et al., Fig. 5a and paragraph 33,
  doi:10.1029/2005JB004087), which supports sampling enrichment.
- **The remaining experimental gap:** the dye left in each original region after a finite draw.
- **Not covered:** predicting how much liquid a physical port draws from each region remains a
  separate engine capability.

## FR-38 — RNA release from its template into two pools with different lifetimes

- **The request (a user, 22 November 2026).** Add a reusable configuration to the one-gene expression
  unit (FR-25's `templated_polymerisation@1`) for RNA that stays attached to its template briefly after
  transcription, then enters one of two pools with different lifetimes. Both pools count in the RNA
  measurement while their molecules survive.
  1. **Release.** A completed chain enters an attached pool owned by its producer. With mean dwell
     tau > 0 and durable fraction 0 ≤ p ≤ 1, the exits are p/tau and (1 − p)/tau. p is evaluated when
     the chain leaves the template, from a declared input or state. Each released pool has its own loss
     rate.
  2. **Accounting per producer:** arrivals, still attached, cumulative releases into each pool, survivors
     in each pool and cumulative loss. Initial RNA plus arrivals equals attached, surviving and lost RNA.
     Producer identity across replacement and restart needs its own acceptance.
  3. **The same RNA over time:** of the molecules released in a stated window and still present at its
     end, the fraction surviving at a later time.
  4. **Measurement denominators.**
     - The detection threshold applies per gene copy, before averaging.
     - Sample, cell and spot IDs are kept, and a confirmed zero-site cell counts in the per-cell average.
     - A counted spot without brightness leaves the paired result incomplete.
     - Brightness per called spot is reported apart from total signal per roster cell.
     - A two-colour result names its statistic: ratio of pooled means, or mean of within-cell ratios.
- **The requester's acceptance examples.**
  - 80 attached chains, an exit half-life of 1 h and p = 0.75: at 1 h, 40 are attached and 40 released,
    30 into the durable pool and 10 into the short-lived one. With half-lives of 2 h and 0.5 h, 24.852814
    and 5.000000 survive.
  - One cell with three spots of 10, one with one spot of 50 and one with none: 20 per spot, 30 as the
    mean of the positive cells' means, 80/3 per roster cell.
  - Two cells at (2, 1) and (6, 9): a ratio of pooled means of 0.8, and a mean of within-cell ratios of
    1.3333.
- **Reproduced (12:18 UTC).** The requester's three commands pass at their pinned revision 40c3185e and on
  main 62ef3d6f, with identical native results.
  - Their native replay runs `local_species_reactions@1` on stand-alone fixture nodes: four fractions,
    including 0 and 1, each with a matched blank.
  - Its largest pool error is 1.06e-6 transcript equivalents at 60 s and 1.32e-7 at 30 s, a ratio of 8.0
    (third order). The inventory error is at most 8.5e-14.
  - The package states no licence. It is kept as evidence under
    /mnt/workspaces/Cells/fr38-rna-residence-20261122/ (zip sha256 4f564ba7…), uncommitted, and nothing
    from it is copied into src/.
- **Status: under assessment.** The replay shows the reaction operator on stand-alone nodes, not the gene
  unit. The template operator refuses another writer on its rows, so connecting completions to the pools
  is likely an engine change in `templated_polymerisation@1`, with a sheet amendment tagged before code.
  - The gene regulation lane is pricing the build.
  - Open questions for the requester:
    - (a) whether an attached chain keeps its polymerase until release;
    - (b) the release step's energy;
    - (c) what "replacement" means for producer identity.
- **Guards against building to the test.**
  - The pools are species rows that the engine integrates, compared with independent references; never
    a formula in a reader.
  - p comes only from a constant, a schedule, or an existing factor form on an engine state, and its
    source is stamped in the record.
  - The reference's history model (its readiness function) stays out of the engine and validation.
  - New routes are development status.
  - The measurement layer is passive (`src/cells/assays`): it states its assumptions and never feeds back
    into the simulation.

**The gene regulation lane's desk assessment (12:22 UTC; no engine code).**
- **The suggested route is refused.** A `local_species_reactions@1` reaction on a chain's product row is
  refused at parse: "templated_polymerisation@1 ... is the one writer of its listed rows". The requester's
  split works only on stand-alone fixture nodes. The parse script is
  /mnt/workspaces/Cells/gene-regulation-20261120/fr38/refusal_check.py.
- **The replay's energy is driven work.** The fixture's species all have mu°/RT = 0, and every route is
  driven mass action, which books a driven-only node's dG as signed work with zero heat. Moves into a
  fuller pool (Durable and Lost outgrowing Resident in the chase) book positive work, which the
  dissipation check does not see. The ledger closes, but nothing physical pays for those moves.
- **The proposed shape:** an in-place opt-in to `templated_polymerisation@1` (D148), with a sheet amendment
  tagged before code.
  - A finished chain waits in a terminal hold owned by its chain, carrying only its residues' standard
    term. Release into a fate row has dG = RT ln a_fate. That is today's product-release term split across
    the durable and short-lived rows, so it is downhill below 1 M, with no new energy object.
  - An attached species row would instead gain a concentration term and could run uphill.
  - Initial hold occupancy is declarable (the 80-chain case), and the model gives the requester's 40, 30,
    24.852814 and 5.000000 analytically.
  - Each pool's loss is an existing degradation route.
  - New counters: the hold, cumulative releases per fate, and a per-producer ledger.
  - p comes from a constant, a per-chain schedule, or a routable factor on an engine state (B1′, at the
    midpoint when release moves its own source), each recorded.
- **Not an FR-36 D2 case:** the held transcript is producer-owned occupancy, not a free pool, so D2's
  progression operator stays the general home for ageing and label families.
- **Prices (agent-days):**
  - the sheet amendment 0.75;
  - the hold without a machine 1.5–2 (with a machine 1–1.25);
  - p as a constant and schedule 0.5, from a state factor 0.75;
  - initial hold 0.25;
  - counters, export and the per-producer ledger 0.75;
  - the host-side release-window cohort 0.25–0.5;
  - the observation layer 1–1.25;
  - tests and gate 1–1.5;
  - producer identity across replacement 1–2, depending on the requester's answer.
- **Totals:** the minimal path (hold without a machine, constant and scheduled p, counters, host cohort,
  observation layer, tests) is 5–6 days; the full path 7–9.5.
- **A fourth question for the requester:** (d) is each producer one gene in one cell, with its own fate
  rows, or do several producers feed shared pools, which would need label families?

**Decided (D284, 12:35 UTC): the full scope, finishing with a registered comparison.**
- **The engine piece,** with a sheet amendment tagged before code:
  - a terminal hold per chain, with the machine held or released as a declared option;
  - p from a constant, a schedule or a state factor;
  - counters, a per-producer ledger, and identity across restart.
- **The cohort, two ways that must agree:** label rows by schedule, and recovery from the counters.
- **The observation reader** in `src/cells/assays`.
- **A fifth question for the requester:** (e) is the window cohort marked when chains complete, as the
  package README's "completion-time cohort" reads, or when they are released, as the request body says?
  The two differ whenever the dwell matters. A pulse label marks at synthesis.
- **Only (c) and (e) block anything,** and each blocks only its own piece.

**Progress (22 November 2026, 13:25 UTC).**
- **Landed:**
  - the sheet's amendment R (§9) with its R2 addendum and a tau fix (tags gr1-sheet-fr38-2026-11-22,
    gr1-sheet-fr38-r2-2026-11-22 and gr1-sheet-fr38-tau-2026-11-22);
  - the code-blind references for R1 and R2 (679fe885, tag gr-refs-fr38-2026-11-22). In R1, the
    requester's 40/40/30/10 hold to rounding, and the survivors lie within 1.54e-8 of their limit.
- **In progress:** the engine piece (the gene regulation lane) and an erratum settling the references'
  readings, both before a registered comparison. The reader (`src/cells/assays/transcription_sites.py`) is
  checker-accepted and in its gate.
- **A disclosure for that comparison's rule.** On 22 November the lead showed the builder the references'
  R1 survivors at p = 0.75 and 1 h, to 10 digits, before any comparison, then withdrew them as a build
  target.

**The requester's clarification (22 November 2026, 15:21 UTC, relayed by the user).** It answers
questions (c) and (e).
- **The cohort:**
  - A molecule is marked when it detaches from its template during [t0, t1). A molecule that finished
    transcription before t0 qualifies if it detaches in the window, and a release exactly at t1 belongs to
    the next window.
  - Template completion, release and uptake of a synthesis tracer are three distinct events. So the
    window marks at release.
- **Survival:**
  - Count the cohort members alive at t1, then how many of those same molecules are alive at t2. Report both
    counts and their ratio; a zero denominator gives an undefined fraction. (For example, 10 released, 8
    alive at t1 and 6 at t2 give 6/8 = 75%.)
  - Under FR-42, adding a tracking label preserves the physical trajectory and the energy ledger.
- **Replacement:**
  - A producer is identified by cell ID, occupant generation and expression-chain ID, preserved across
    restart and cell reordering.
  - On replacement, removed intracellular RNA is booked to the departing generation, and removal is
    recorded separately from degradation.
  - The newcomer starts its own production counters at zero.
  - RNA retained in an extracellular compartment keeps its original producer ID.
- **Their acceptance test:** replace a producer midway through a chase, then restart. The readout still
  distinguishes the two generations' RNA and reproduces the uninterrupted run's cohort counts.
- **How it is built:** the release-marked cohort already exists. Producer identity becomes a neutral label
  on FR-42's shares, (cell, generation, chain), so RNA that leaves the cell keeps it. The replacement
  booking is in templated_polymerisation@1 and the replacement operator, after FR-42 stage 1.

**The machine options are declared choices, not validated biology (the Lean lane's evidence, 16:09 UTC).**
- In Harden et al. 2020 (PMC6978322, Figs. 1 and 3), purified E. coli polymerase stayed on the DNA after
  the RNA left in 87 of 100 selected traces. Separate recordings showed that a retained polymerase could
  make another RNA.
- The study leaves open when the polymerase becomes available to other templates. So neither of Cells'
  options, returned at completion or held until release, is quantitatively validated by it.
- Retention with reinitiation on the same template is a third behaviour that Cells does not model. It
  would be a future option, built only on a requester's need.

**An export defect, found by the Lean lane (being fixed).** In a 10 s R1 run with no loss route declared
for a fate, the exporter omitted that fate's int_D, so the cohort reader refused its survivors. The
exporter's zero-loss rule covered chain products but not release-fate rows. The fix extends it to
eligible local release-fate rows, class rows included, and the reader keeps requiring an explicit loss
series. The physical balances were unaffected.

**Status (24 November, later, D354):** the second comparison's amendment 3 is tagged. Three readout controls go to a later registration, FR-38 v3, with its own verdict: producers reordered and replaced; the same molecule leaving and returning through export; and zero loss, two loss routes on one row, and a constant-stock control.

**Status (25 November, D381, D382):** the second comparison has passed as registered, with an independent checker agreeing,
and is landed at 4039dcba (`fr38-v2-landed-2026-11-25`). FR-38 v3 is open.

## FR-39 — A vesicle that survives transient pores

- **The request (the Lean lane's evidence, relayed by the user, 22 November 2026; D286).** One study imaged the
  same vesicle opening and resealing three times, each closure within one second (eLife 03695, Figure 5).
  Another shows a tracer escaping during a pore opening (PMC5406380, Figure 4).
- **What Cells does today:** it ends the lineage at terminal lysis.
- **What it needs:** an outcome in which the vesicle survives a pore and keeps some of its cargo. The pore
  opens under tension, leaks until the tension relaxes, then reseals.
- **The first step:** a design note shared with FR-31. It covers pore opening under tension, leakage
  while the pore is open, resealing, and rupture, with the existing release and energy accounting. It
  also covers the deterministic representation (OL6) for giant vesicles.

## FR-40 — A single-ribosome translation timing benchmark

- **The request (the Lean lane's evidence, relayed by the user, 22 November 2026; D286).** Yan et al.
  (PMC4889334, Figure S2) followed a 1,462-codon reporter in live U2OS cells. Across 44 single-ribosome
  events, the mean from first detectable nascent chain to release was 406 s.
- **The discrepancy:** the paper's separately reported elongation speed, 3.1 ± 0.14 codons/s, implies a
  mean runoff of 7.86 min. Its histogram gives a lower bound of 8.93 min.
- **The ruling for now:** keep the 406 s observation, and leave the speed comparison unscored until the
  sample or timing correction is reconciled. The evidence note is
  `lean/claims/incoming/translation-release-evidence.md`.
- **The first step:** a desk note covering:
  - what `templated_polymerisation@1` predicts for this interval;
  - the detection model (where along the chain the nascent signal becomes detectable);
  - which independent speed could be used;
  - how a comparison would be registered before any reading.

**The desk note (docs/TRANSLATION_TIMING_NOTE.md, 022a5d2a).**
- **The prediction:** the translation law's mean from detection at codon d to release is (L − d)/(v_eff).
  With detection at about 8 of 24 SunTag peptides (codon 245), that is 393 s at the paper's 3.1 codons/s,
  and at least 446 s at its histogram's bound.
- **The verdict:** with only the paper's own speeds, which contradict each other by at least 13%, a
  comparison could only be a calibration. A validation needs an independent speed under matched
  conditions, plus d from the intensity calibration alone, both fixed before reading.
- **Two tests need no speed:**
  - interval ratios between reporters of different lengths with the same tag and leader, which this paper
    lacks;
  - the spread, about 3% under the per-codon law. A broader spread would be recorded as a non-claim about
    homogeneity, not fitted.
- **The next step:** a metadata-only search for a matched-condition speed, or for a multi-length reporter
  series.

## FR-41 — Vesicle shrinkage validation records

- **The evidence (the Lean lane, relayed by the user, 22 November 2026; D286).** In Fujiwara et al. 2014
  (doi:10.1021/sb4001917), five giant DOPE/DOPC liposomes, at 70 mOsm/L inside, reached about one quarter
  of their initial volume at 285 mOsm/L outside.
  - Cells' compiled equilibrium replay at f1783c55 (`cells.osmotic_lumen@1`) gives 24.56%, unfitted.
  - A paired GFP and volume track in the same liposome (Figure S3) supports the protein's retention during
    shrinkage.
  - The cited values and the replay are in `lean/checks/data/fujiwara2014_vesicle.json`.
- **Open:** the retention of smaller osmoles, including in the Lean lane's earlier Bhatia comparison.
- **The next step:** a search for paired small-solute retention and volume data.

**The search (14:25 UTC, metadata only; no values recorded).**
- **No study measures** both the volume and the retention of a small internal solute (under 1 kDa) on the
  same giant vesicles during hypertonic deflation. Several infer volume from the very dye they track, so
  they count as one measurement, not two.
- **The best candidates:**
  - Akui et al. 2021 (iScience, doi:10.1016/j.isci.2021.102859, CC BY-NC-ND): giant POPC liposomes from the
    reference group, with calcein imaged beside a protein at the end point. Its volumes come from other
    experiments. Its licence makes it analysis-only.
  - Ahumada et al. 2015 (doi:10.1016/j.chemphyslip.2015.05.001, not open): turbidity and calcein release
    in the same gel-phase LUV preparation.
  - Emami et al. 2018 (PMC6303272): a small glucose analogue entering GUVs during deflation.
- The ranked list, the near misses and the searches tried are in
  /mnt/workspaces/Cells/fr41-search-20261122/candidates.md.

**The data-only retention check (D292; 15:13 UTC): undetermined for all three sources.** It used the
analysis rule fixed before any value was read (rule.md sha256 9ae86b40…; results.json sha256 2b003647…).
- **Akui 2021:** calcein and diameter appear only as boxplots, with no mean or standard error in the text,
  so the rule cannot be applied. The authors state qualitatively that calcein stays inside.
- **Ahumada 2015:** DPPC:SM retention under the 1.4 M NaCl shock has a point estimate of 0.66, from the
  reported maximum release against the isotonic release. The paper leaves "±" and n undefined, so no 95%
  interval exists. No reading of them gives "retained".
- **Ahumada 2017:** shock-only release appears in traces only.
- **Overall:** no source shows retention near 1. The one number, from 400 nm gel-phase vesicles at 25 °C,
  points to about a third of the calcein released. That may not carry over to fluid giant vesicles.
- **Cells' retention assumption stays open.** FR-41 is parked until a study with paired, tabulated data
  appears.

## FR-42 — Neutral arrival-time labels that leave the dynamics unchanged

- **The request (a user, 22 November 2026; high priority by the user).** A neutral label records when
  otherwise identical units entered a pool, so the cohort that arrived during a window can be followed.
  Changing the number of labels must leave the total amount, the loss rate and the energy balance unchanged
  throughout the run.
  - **Loss:** computed once for each well-mixed population whose members share a per-molecule loss rate.
    With N units, a label marking n of them, and a total loss flux J, the label is assigned J × n/N.
    Unlabelled material counts as a share. An empty population has zero loss. Physically distinct
    populations can each have their own loss law.
  - **Energy:** chemical potentials, free energy and heat are computed from the physical populations
    wherever the simulator models them. Subdividing a population by arrival time preserves them.
  - **Windows:**
    - arrivals count from a window's start up to, but excluding, its end;
    - a new cohort starts at zero, even when the pool already holds material;
    - its losses are followed after the window closes;
    - a reused label accounts for the survival of its older material in the same run.
- **The reference case.** In scaled units, dN/dt = −N², so N(t) = a/(1 + a t).
  - Two units of older material, plus one newly labelled unit at t = 0. The initial loss rate is 9;
    computing each label's loss separately would give 5 and change the trajectory.
  - At t = 1 the total is 3/4. The new cohort is still one third of it, 1/4.
  - A blank run with only the two older units ends at 2/3, so blank subtraction gives 1/12. It fails
    because the added material raised the older material's loss rate.
- **The acceptance checks:**
  1. **One initial state, run unlabelled and then with one, two and several labels.** Include unequal
     shares and an empty label, and a state near the edge of the supported concentration range, where the
     loss rate is sensitive. At every comparison time the shares sum to the reference total. The total
     loss, free energy and heat agree within declared tolerances.
  2. **Arrivals at a window's start and at its end, with older material present.** Only the start-boundary
     arrival enters the cohort. Its survivors agree with an independent calculation from the arrival history
     and the run's own per-molecule loss rate.
  3. **Two physical populations with different loss rates, one subdivided by arrival time.** Each keeps its
     own reference trajectory, and the subdivided one's labels account for all its material.
- **Where Cells stands:**
  - D1's label families and FR-38's operator-local class rows are separate rows, each with its own
    potential. So a label carries its own mixing term: the Lean lane found that D1's neutral labels can
    change booked face heat, and FR-38's label rows depart from the unlabelled run by up to about 1e-8.
  - FR-38's cohort route 1 subtracts a matched blank, which is exact only when the loss is linear in the
    amount.
  - docs/COHORT_LABELS_DESIGN.md's option B (labels inside a physical population, under nonlinear laws)
    was deferred for want of a consumer. This request is that consumer.
- **The first step:** a desk assessment. It covers share-based labels inside physical populations across
  families, turnover, templated polymerisation and faces; what moves in registered worlds; and how FR-38's
  cohort would use it.

## FR-43 — Shared inventories: larger networks, shared pools and low-count populations

**Logged 23 November 2026 by the user, priority very high.** The baseline is db54d0f5. The acceptance
cases below are the request's own, condensed.

**Why.** Cells refuses three things real cells do:
- **Run reaction networks larger than 16 rows.** The cap counts every species, ions included (FR-9,
  D165).
- **Let separate processes spend and replenish one finite pool,** such as the nucleotides that
  expression consumes and metabolism restores. The gene unit is the one writer of its listed rows, and
  local reactions are refused beside the water operator, which changes volume.
- **Couple a functional unit present in a few copies to continuous chemistry,** where the unit
  assembles and disassembles stochastically. The assembly runner chooses one representation for a whole
  world (OL6's refusal 11).

**1. Larger sparse reaction networks.**
- **The world:** one compartment and a reversible chain of neutral species, with unequal initial amounts
  and both fast and slow transfers.
- **The sizes:** 16 rows is the control; then 32 and 256 rows, and 1,024 profiled if practical. The
  background ions are counted in each size.
- **The checks:**
  - the amount histories against the independent matrix-exponential solution;
  - material, charge and energy accounting;
  - at the same declared accuracy: compile time, time per simulated second after compilation, and peak
    memory, with the device and precision.

**2. One pool, two processes.**
- **At fixed volume:** one operator replenishes a pool from a finite reserve while another spends it.
  The amount and its standard chemical potential have one authority.
  - At each saved time the shared amount equals the initial stock plus receipts minus spending.
  - Both rates and the amount agree with an independent coupled calculation.
  - Disabling either process recovers the other's standalone result.
- **At changing volume:** this is D301's composition M3, with reactions in place of turnover.
  - An impermeant tracer with its reactions off keeps its amount and halves its concentration when the
    volume doubles.
  - A concentration-dependent reaction agrees with a reference evaluated at the evolving volume.
  - The energy balance includes the work of changing volume.

**3. A low-count population coupled to continuous chemistry.**
- **The world:** two free subunits form one active unit, which transfers material between two finite
  pools. Disassembly returns both subunits.
- **Conservation:** free subunits plus twice the active count stay constant, and the two pools conserve
  their total.
- **Event timing:**
  - with feedback off and constant rates, the probability of no active unit agrees with the exact
    two-state solution;
  - with feedback on, where the event rate reads the current pool, the event times agree with
    independently integrated rates under the same random draws.
- **Division:** at an equal-probability split of a single active unit, exactly one recipient receives it
  on every draw, and the recipients' inventories sum to the original.
  - The split frequencies are checked across seeds.
  - A same-seed checkpoint and restart reproduces the event trace and the balances.

**Status (23 November).**
- **The design:** one note for all three parts is being written (`docs/FR43_SHARED_INVENTORIES_DESIGN.md`),
  with part 1's probe and timings.
- **Part 3 is a new system.** Its host goes to the user with options before any build: a per-scope
  representation in the assembly model, or an integer-population operator in the composite.
- **The references:**
  - the matrix exponential is a closed form, inside the test;
  - part 2's coupled calculation and part 3's same-draws integration come from a code-blind references
    agent, started at the design ruling.
- **Part 3's version 1 is refused beside a wash.** `scheduled_compartment_wash@1` reads none of
  `integer_unit_population@1`'s transfers across a washed surface, so it refuses the operator
  (fail-closed). Lifting that is its own qualified extension.

**Status (24 November):** all three parts are on main (D328): part 1 (bbc99163), part 2A (c9687d68) and 2B (2ca07dcb), and part 3 (7fb0ad87). Part 3's registered check passes (D319), and so does part 2's (D324). Still open: the factor-width term, and the request's item-by-item check (A1, turnover in swelling cells).

**Status (24 November, later, D347):** checked item by item against the request. Judged: C2.3, C2.6, C2.7 and C2.8 (D324), and C3.3, C3.4 and C3.5 (D319). The rest are covered by the builder's tests only. Gaps: part 1's 16-row and 256-row cases have no test at main; part 1's performance report lives only in the design note, and its L4 path is now refused (D336); part 1 has no registered criterion; turnover in a swelling cell is still refused at parse.

**Correction (26 November 2026, D380):** "its L4 path is now refused (D336)" is wider than D336's words. What D336 closed is the device's own row checks, and the vector windows refuse the composite on a GPU. Part 1's L4 column was taken on the composite on a GPU through the plain runner, whose rows the host checks, and that path stays admitted. An unflagged GPU run varies from one repeat to the next (up to 1.9e-11 relative on one tissue); under XLA's deterministic flag, repeats are bitwise. What to do about a plain, unflagged run is the user's (D380).

**Next (24 November, D365; the user):**
- part 1's 16-row control and 256-row case, as rows in the existing species-cap tests;
- part 1's performance report, measured on CPU on the timed cores;
- turnover in a swelling cell, logged as FR-65.

No registered criterion for part 1 now.

**Status (24 November, late; D376):** part 1's two gaps landed at 14f19f9f (tag `fr43-part1-gaps-landed-2026-11-25`): the 16-row control and the 256-row case as rows with plants, and the CPU performance report in `validation/fr43_part1/`. Turnover in a swelling cell is FR-65.

## FR-44 — Labels across a wash: arrival-time labels through scheduled compartment washes

**Logged 23 November 2026 by the user, priority high.**

**Why.** Labelled-cohort experiments often mark newly made molecules for a while, wash the
extracellular compartment, and expose the cells again. Following the labelled cohort through a wash
needs the label owner (FR-42) and the wash (FR-27) in one world. Today they refuse each other at
parse (`operators/wash_schedule.py`, `operators/species_labels.py`).
- **A related constraint:** the wash's `buffer_mM` must name every neutral species in the world,
  including trace rows that stay in the cells. So a wash also touches those rows' extracellular
  increments.

**The proposed path.** The wash accepts labels.
- At a washed node, each label's share is diluted exactly by the unlabelled buffer:
  n_after × share_after = (1 − f) × n_before × share_before, and the buffer carries the base label.
- Label shares inside cells are untouched, and every label's books close.

**Acceptance cases:**
- a labelled cohort at a washed node scales by (1 − f), and the base label takes the buffer's amount;
- the cells' shares are unchanged;
- labels leave the physical rows bitwise unchanged through a wash (FR-42's promise);
- a restart through a wash reproduces the run.

**Status (23 November):** logged. A design note comes first.

**Status (24 November): the core is built** (D327; `docs/NEUTRAL_LABELS_DESIGN.md` §13), on
branch `fr44-labels-wash` for its gate and landing.
- **The report.** The wash reports a typed `LiquidExchange`, read from each event's own sample and
  supply records, never from a cumulative record's gain.
- **The map.** The label owner dilutes each label exactly. The buffer joins the base, even inside
  an open window.
- **Labelled ions** keep their amount while their shares dilute.
- **The record** `label_outside_removed_fmol` holds what left, by label.
- **The acceptance cases are rows:**
  - the cohort scaled by (1 − f), with the base taking the buffer;
  - the cells unchanged;
  - the physical rows bitwise, in compiled twins washed five times;
  - a restart across a wash, bitwise, with the redo and skip planted.
- **The version-1 limit** (approved): the report's axis is the outside nodes, so an exchange of a
  cell's own liquid cannot be expressed.
- **Combinations (D327):** FR-49's C1 world, labels beside a compartment with a wash at another
  node, stays refused by the compartments' admitted list until FR-49's wash narrowing.

**Acceptance targets (24 November 2026, later; checked against the build after landing):**
- **The example.** A 1 µL well holds 12 fmol of solute: 3 tagged and 9 base. A half-volume wash supplies 2 fmol of
  unlabelled solute, so the tagged share falls from 25% to 18.75%.

  | fmol | Before | Collected | Supplied | After |
  | --- | ---: | ---: | ---: | ---: |
  | Tagged | 3 | 1.5 | 0 | 1.5 |
  | Base | 9 | 4.5 | 2 | 6.5 |
  | Total | 12 | 6 | 2 | 8 |

- **The checks:**
  - label shares inside the cell are unchanged at the exchange;
  - enabling labels leaves the physical trajectory bitwise identical;
  - a no-event control;
  - a full wash;
  - a checkpoint immediately before the event, with the resume booking the sample exactly once.
- **What the build has:** a resume through a wash with planted redo and skip, a full wash after an earlier wash, and
  no-wash worlds unchanged. The example's numbers become a row in an existing test after FR-44 lands.

## FR-45 — Several ligands competing for one shared, wash-retained site capacity

**Logged 23 November 2026 by the user, priority high.**

**Why.** Extracellular matrix and surface sites are often shared by more than one ligand, and the
sites stay in place when the fluid is washed.
- FR-28's owner `{"node": N}` gives `site_occupancy@1` wash-retained sites, but each population
  binds one ligand with its own capacity, so two ligands cannot compete for one pool.
- Sites modelled instead as dissolved species in `local_species_reactions@1` are removed with the
  fluid: a wash of half the volume removes half the sites.

**The proposed paths:**
- (a) `site_occupancy@1` populations admit several ligands, each with its own binding constants,
  competing for one pool of copies × sites per copy;
- (b) immobile anchored species, which `scheduled_compartment_wash@1` leaves in place (wash fraction
  0 for anchored moieties) while conserving moieties.

**Acceptance cases:**
- a wash removes only the fluid's ligand, and the shared capacity is conserved across it;
- the competition at equilibrium matches an independent closed form for two ligands and one site
  pool;
- the books close through bind, wash and unbind.

**Status (23 November):** logged. A design note comes first, weighing (a) and (b).

**Acceptance targets (24 November 2026, later):**
- **The example.** The liquid holds 8 fmol of free A and 4 fmol of free B. The surface holds 3 fmol of empty sites,
  2 fmol occupied by A and 1 fmol occupied by B.
- **The wash.** A half-volume wash collects 4 fmol of A, 2 fmol of B and no sites. All 6 fmol of sites keep their
  pre-wash occupancy at the instant of exchange.
  - Event counters are read before a later sample is interpreted, since bound ligand can dissociate after the wash.
  - Buffer-supplied solute is accounted separately.
- **The single-ligand limit,** and competition after re-equilibration. For independent 1:1 sites, A's occupied fraction
  is (c_A/K_A)/(1 + c_A/K_A + c_B/K_B), and B's is the analogue. The c are the free equilibrium concentrations, solved
  from each ligand's conserved amount in the finite volume.
- **Conservation** of each ligand and of the shared site total holds across binding, washing and release.

**Status (24 November, late; D376):** the references' version 2 is tagged (`fr45-references-v2-2026-11-24`, with W7 and W7s under amendments 2 and 3). The judge comes after the rename.

## FR-46 — Binding from a shell's inner face: lumen ligands on membrane sites

**Logged 23 November 2026 by the user, priority high.**

**Why.** Compartments bind ligands from the inside as well as the outside. `cells.prescribed_shell@1`
(FR-21) admits a pool ligand binding a declared membrane site from the outer face. It refuses a ligand
in the lumen binding the same site, with the site and the complex on the membrane.

**The request:** reversible binding from the inner face.
- Association reads the lumen's concentration, and dissociation returns the ligand to the lumen.
- Ligand and site counts are conserved.
- The occupied wall state can take part in a declared gate rule.
- The new reaction pair has detailed-balance coverage (the event-pair rule).
- The outer-face case is kept as a regression.
- It is verified on a synthetic neutral ligand.

**Status (23 November):** logged. A design note comes first.

**Status (24 November):** landed with FR-48 at the merge d702f13a (D323). Inner-face binding stays refused in the deterministic representation until a qualification covers it.

## FR-47 — Shell exchange and scheduled washes in the deterministic representation

**Logged 23 November 2026 by the user, priority high.**

**Why.** `cells.rate_equations@1`, OL6's deterministic representation (D304), refuses some worlds by its
refusal 1:
- prescribed-shell geometry: FR-21's shell, its permeation and its gate;
- replacement and withdrawal schedules: FR-20 and FR-35 (`rate_equations.REFUSED_SCHEDULES`).

So large-count vesicle worlds with a shell and washes can run only as exact events.

**The request:**
- Qualify passive shell exchange, and scheduled full and fractional washes, in a finite two-compartment
  example.
- Compare concentrations and removed amounts with an analytical mass balance and with a large-count
  exact-event ensemble.
- Qualify switching gates separately.

**Notes.**
- OL6's design priced the replacement and withdrawal means at about half an agent-day.
- The qualification follows Protocol D's pattern: registered before reading, with an independent
  checker.

**Status (23 November):** logged. A design note comes first.

**Status (24 November): built; qualified: FR-47's independent check passed at its registered tag (D373).**
- The build (D323, D327) admits, in a prescribed shell's world only: the shell's limits, the washes
  as operators of the deterministic representation, E2's true zeros at first-order places and
  autonomous switching gates. Outside a shell's world each is refused by name, until a
  qualification covers it; site binding in a shell's world and gates driven by bound states are
  refused too.
- The qualification is registered (tag `fr47-shell-exchange-registered-2026-11-24`), with its
  code-blind references (tag `fr47-references-2026-11-24`). Its independent checker writes the
  driver and runs it after the landing. Until that verdict, these paths are development-only: the
  representation's registered `qualified` field says so, and each run that uses them records it
  (`representation.qualification` in its run.json).

**Status (24 November, later):** a reviewer found that the frozen scorer does not check the washes against the registered schedule. The frozen scorer stays official, and a separate schedule supplement is registered before any judged run (`validation/assembly_lineages_v2/FR47_SCHEDULE_SUPPLEMENT.md`, D339). FR-47 stays development-only unless both pass. A fix for inert wall places, which no rate or geometry reads, is in its gate.

**Status (24 November, late; D373):** the independent check passes, under the frozen scorer, and the schedule supplement passes separately. FR-47's development-only status is lifted.

## FR-48 — A lumen standard potential: a reversible free-energy difference across a prescribed shell

**Logged 23 November 2026 by the user, priority high** (raised the same day, with FR-46 and FR-47).

**Why.** In `cells.assembly_lineages@2`, the pool and the lumen share one solution standard potential
per species, because `place_arrays` takes μ° from the species and the place's phase alone. So a solute
cannot hold a free-energy difference across `cells.prescribed_shell@1`, and its equilibrium is always
equal concentrations at equal volumes.

**The request:** a reversible free-energy difference for the same neutral solute across the shell, at
fixed volumes.
- At equal volumes, a lumen cost of ln 2 kT gives an equilibrium inside/outside concentration ratio of
  0.5, and a zero cost gives 1.
- The tracer is conserved, and detailed balance holds from either starting side.
- Changing the permeability changes the equilibration time but preserves the ratio.

**First reading (the lead, with the advisor).**
- The layout already carries μ° per place.
- The shell law's exit is derived from μ° (k⁻ = P_s exp(Σν μ°)). So a lumen offset Δ gives
  c_in/c_out = e^−Δ with no change to the law's text.
- The equilibration rate then depends on Δ as well as on P_s.
- **For the design note to settle:**
  - one authority for μ°: a lumen phase the species declares, or a per-species transfer term the shell
    owns;
  - every reader of a lumen μ°: F and the heat per crossing, a held pool's work, the gate, and FR-46's
    inner-face binding;
  - version 1's scope: neutral solutes, a prescribed shell, fixed volume. Osmotic lumens, lysis and
    rupture returns, division, and `rate_equations@1` until FR-47 are refused by name;
  - D148: statically absent unless declared.

**Acceptance, in exact-event terms:**
- at equal volumes the inside count is binomial, n_in ~ Binomial(N, 1/(1 + e^Δ)): one third at ln 2 and
  one half at 0, as a closed form, with a planted flipped sign;
- detailed balance on the kernel's identity, from both founders;
- doubling P_s gives the same event sequence with every time exactly halved, under the same draws;
- the tracer count is constant, and the ledger closes with Δ per crossing.

**Status (23 November):** logged. A design note comes first, with FR-46 and FR-47.

**Status (24 November):** landed with FR-46 at the merge d702f13a (D323).

## FR-49 — Compartment composition qualifications: expression, site occupancy and labels beside cell-owned compartments

**Logged 23 November 2026 by the user, priority high.** This comes from a review of which fixed-volume
compartment combinations are qualified. The answers are in
/mnt/workspaces/Cells/review-answers-20261123/ANSWERS.md, read at main 61b418fc.

**Why.** `cell_owned_compartments@1` admits a fixed list of operators (refusal 7, `compartments.ADMITTED`,
failing closed). Expression, site occupancy and neutral arrival labels are each refused by that list
alone; nothing in their declarations conflicts.

**The smallest feature for each pairing:**
- **Expression (`templated_polymerisation@1`):**
  - add it to the list;
  - refuse exports and outside degradations at a compartment's node;
  - qualify with one silence world, its ledgers closing.
- **Site occupancy:** the closed-compartment design's §4 door.
  - Add the list entry.
  - Admit only outward-facing populations on a bounding patch, and populations owned by the
    compartment's node (FR-28).
  - Add a host check for both.
  - Qualify with one lumen-binding world against its closed-form depletion equilibrium.
- **Labels (`neutral_arrival_labels@1`):**
  - add the list entry;
  - qualify with one world whose physics stays bitwise unchanged, whose label shares meet their closed
    forms, and which restarts exactly.
  - Membrane state stays out of a labelled compartment world.
- **The wash** stays a version-1 restriction (ruled 20 November; COMPARTMENT_WASH_DESIGN.md §4.7). One
  narrowing is worth having: because the list refuses the whole composition, a world that declares a
  compartment cannot wash any other node either. A wash that names no compartment node could be
  admitted.

**Status (23 November):** logged.

**Status (24 November):** parts H and L landed at the merge 7d021548, and World L's registered judgement passes (D331). Still to come: World B and the combination checks C1 and C2, after FR-49's site pairing (following FR-45) and its wash narrowing (following FR-44), and C4's four-way form by amendment, once admission by species lands.

## FR-50 — One-way cumulative transfer records per route

**Logged 23 November 2026 by the user, priority high.**

**Why.** Most transfer records are net: a passive route's cumulative inward transfer, a channel's
outward flux, and the face and junction records. So equal flows in opposite directions cancel.
- One-way records exist only for exchange, turnover and expression's export, as forward and backward
  counters.
- D152's produced and consumed records split each half-step's net change by sign. They are not one-way.

**The request.** Opt-in one-way cumulative records per route, built from the existing one-way kernels.
- Each pair closes to the net record at rounding.
- They are statically absent unless declared, so unchanged worlds stay bitwise.

**Status (23 November):** logged.

**Status (24 November, evening; D363):** phase 1's registered comparison passes at 4872266d. Every criterion passes, and all five plants are caught. The gate follows after FR-51's follow-up lands.

**Status (27 November; D405):** phase 2 landed at d92403cc, with @3's own routes, faces and channels. Its judged run passes: every criterion is inside its band, and all four plants are caught.

## FR-51 — Two voltage-dependent blocking modes on one channel population

**Logged 23 November 2026 by the user, priority high.**

**Why.** It is not expressible today.
- A channel population's flux is permeation × abundance × its law's opening × availability.
- `ChannelLaw` kinetics read the voltage only, with fixed coefficients, and there is no block law.
- The routing door's factors and the coupling operator multiply, and get no voltage.
- Two populations would mean two counts.

**The request:** an optional `block` on a channel population.
- It has weighted modes summing to one, each with its own K(0) and δ, against the membrane voltage or
  V − E.
- It applies in `channel_rates`, so the clamped entry points inherit it.
- A blocker concentration of zero gives exactly the unblocked population.

**The qualification:**
- permeation first, without the blocker: currents at equal and at unequal ion concentrations against
  GHK;
- then block: the blocked-to-free current ratio against voltage, at two reversal potentials;
- then one-count scaling, and a run.

This lets consumers check permeation and block separately.

**Status (23 November):** logged.

**Next, after landing (D353, the user):** a registration tests the block's reference voltage against Lean's
two-potassium rows, read at their commit. It has two arms:
- **external:** Panama and Lopatin's 0.98 ± 0.01 mV per mV of reversal; Ishihara and Yan's curves at 150, 50 and 20 mM;
- **internal:** Lopatin and Nichols' −0.15.

It is non-blind, since the lead has seen 0.98. Also queued: one admitted row with an effective valence above |z_B|
(D352).

**Lean's evidence (D355).**
- **External arm:** it meets D351 in direction and rough size, on Lean's half-conductance reading: slopes of 0.97 for
  Panama, and 0.97 and 0.98 for Ishihara. Panama's 0.98 ± 0.01, quoted above, is a fitted steep component, a different
  observable.
- **Internal arm:** an indication (+5 mV observed, against −36.3 for the reversal reference).
- **Scope lines,** in the landing message and the block law's docstring on the follow-up branch: the reversal
  reference is supported for external-K changes only; `kir2p1_mh2@1`'s gates read absolute voltage.

**Kir2.1 and the holdouts (D356).**
- **Kir2.1** is this block on an always-open K population with a K reversal reference. It stays development-only until
  the registration passes.
- **Holdouts:** Panama's 10 and 20 mM levels are unscored, and become within-study holdouts. The 5.4 mM fit, the
  readout and the scoring rule are frozen before they are extracted.
- **After landing,** the `reference` key moves into FR-64's declared voltage shift.

**Status (24 November, evening): landed** at 955765ef (tag `fr51-landed-2026-11-24`). The landing trial passed: 494
tests in 601 s. Next:
- the follow-up on `fr51-slot-refusal`: the slot refusal, one admitted row with an effective valence above |z_B|, and
  the docstring scope lines;
- the law's registration, after FR-64's design note;
- the two-arm registration (D353, D356).

**Correction (D360):** the admitted row already existed: B5 is the spermine case, with B4, G1, G3 and G5 also admitted. The follow-up adds a plant that caps the valence at |z_B| and fails B5, plus B5's round trip.

## FR-52 — Passive cohort observations for integer functional units

**Logged 24 November 2026 by the user, priority high.**

**Why.** A population can keep the same number of active units while its members turn over. A general
observation reports how many of a site's original units still contribute to transport, and how many formed
during a named window. It leaves the physical trajectory unchanged for the same random stream.
- `integer_unit_population@1` (FR-43 part 3) records integer assembly and disassembly events per site.
- Its route conductance sums unit counts weighted by per-unit, per-state conductance.
- FR-42's neutral labels follow species rows, not units, and the operator refuses a label owner.

**The request.** For one exchangeable active-unit class at one fixed site, return the expected surviving initial
count and the expected newly assembled count, conditional on the recorded events.
- Each is given with its unit and labelled as an expectation.
- A documented postprocessing reader over complete event traces would satisfy it.
- The operator keeps the first `trace_events` events per site, and `integer_events` counts them all. An interval
  beyond a truncated trace is flagged unresolved.
- At one declared driving difference and additive per-unit conductance, each expected count gives a checkable
  expected contribution to the route flux.

**Acceptance example** (one site, identical activity, exchangeable removal within one class):

| Event at the site | Total active | Expected initial | Expected newly assembled |
| --- | ---: | ---: | ---: |
| Start with two identical active units | 2 | 2 | 0 |
| Assemble one during the observation window | 3 | 2 | 1 |
| Disassemble one, chosen uniformly from the three | 2 | 4/3 | 2/3 |
| Disassemble both remaining units | 0 | 0 | 0 |
| Assemble one more inside the same window | 1 | 0 | 1 |

- The mixed-cohort result is compared against the three equally likely choices of removed unit.
- The cohort contributions sum to the route flux at every observation.
- Event times, channel choices, physical inventories, fluxes and energy records are unchanged by observing.

**First reading (the lead, with the advisor), for the design note to settle:**
- **Classes partition the count.** "Initial" and "inside the window" alone leave out units that assemble outside
  the window. The membership classes follow FR-38 erratum I's pattern: initial, and before, inside or after the
  window. A re-assembled unit is new, a gross reading, not a net one.
- **Sum-to-flux needs teeth.** Each contribution is the expected count times the declared per-unit conductance
  times the recorded driving difference, and their sum is compared with the engine's flux. Shares of the flux
  would sum to it by construction.
- **Integrity:** the total rebuilt from the trace must equal the engine's saved integer count at every row,
  exactly. A mismatch means unresolved.
- **Fail closed on truncation:** return unresolved, never a number. No caller may read it as zero or infinity,
  following the cohort readers' precedent.
- **Carry expected counts, not shares.** E <- E*(n - d)/n gives an exact zero at an emptied site and avoids 0/0.
  Any tolerance is derived from the event count.
- **The bitwise test.** "Observation enabled against disabled" is vacuous for a pure reader. The real check is
  the trace capacity raised against its default: events, inventories, fluxes and energy all bitwise, in a fresh
  process, for scalar and batch runs.
- **Two options to weigh:**
  - a validation reader, limited by the trace's capacity;
  - an in-engine expected-cohort record, statically absent unless declared. Uniform removal leaves shares
    unchanged, so this is FR-42's share rule applied to the unit count.

  The note says which side of AGENTS.md's "no physics in validation" line a reader falls on.
- **Version-1 refusals by name:** several states with transitions between them, and division or retirement at the
  site.
- **Mutants:** oldest-first and newest-first removal both conserve totals, but must fail the 4/3 and 2/3 row,
  checked in exact rationals. A window-edge tie row uses the cohort readers' half-open convention.
- **Wording:** exchangeability is the operator's own law, one hazard per unit of a class. The output is an
  expectation, not a realization. The operator's library page already states its scope.
- **Premises checked at main by name:**
  - the trace's capacity (`trace_events`, first T events per site, with channel -1 meaning not recorded);
  - the total-event counter (`integer_events`);
  - the additive per-state conductance;
  - the label-owner refusal.

  Still to verify in the note: that the trace survives windows and a same-seed restart, and that one event moves
  exactly one unit.

**Status (27 November):** landed at ab8b599c (tag `fr52-landed-2026-11-27`, D404), from the note `docs/PASSIVE_COHORT_DESIGN.md`.

**Correction (24 November, later):** one event can move several units, so the first reading's open premise is settled the other way. A channel carries integer stoichiometry over the unit states (up to `MAX_ORDER` per state), and `integer_change` is products minus reactants.
- **The reader uses each event's declared change.** Removing d of n exchangeable units uniformly gives E <- E*(n - d)/n. Restricting version 1 to single-unit events, by name, is the fallback.
- **An acceptance row:** start with two original units and one new unit. One event removes two, chosen uniformly. The expected survivors are 2/3 original and 1/3 new, and a truncated trace returns unresolved.
- **A mutant:** a reader that assumes one unit per event gives 4/3 and 2/3, a total of 2 against the engine's 1. It must fail the integrity check.
- **For the design note:** whether a channel may list the active state on both sides. If it may, the stored change is net there, which conflicts with the gross reading.

**Design (D371; the user):** an engine record kept at each event, with the trace reader as the independent check. Version 1 covers chains (dimer to tetramer) and single-subunit activation, through a declared identity map across states. The note on `fr52-design` is being revised accordingly.

**Splits (D375; the user):** a split makes a new unit. One half keeps the original identity, and the other counts as newly assembled, so "initial" stays a survival count.

## FR-53 — A rounding allowance for global ledgers at every row

**Logged 24 November 2026 by the user, priority high.**

**Why.** FR-17's GPU qualification (D330, D336) found a limit that applies on every device.
- **Where the bound is thin.** At a run's first rows, a balance check's bound is the bare absolute tolerance: the
  rounding allowance grows with the accepted steps, and is zero at steps 0 and 1.
- **A global ledger sums every cell's terms,** and that sum's own rounding takes a growing share of the bare
  tolerance. On the host (CPU), the first window's "total" ledger reads:

  | World | Junction routes | Share of the bound |
  | --- | ---: | ---: |
  | 25-cell line | 24 | 0.044 |
  | 9 × 9 sheet | 144 | 0.122 |
  | 25 × 25 field | 1,200 | 0.281 |

  That growth is about √N (exponents 0.40–0.48), as a sum's random rounding grows.
- **Extrapolated,** the first window refuses on rounding alone at about 15,000–29,000 routes, roughly 90 × 90 to
  120 × 120 cells, on any device. By the second window the allowance dominates, and the share falls.
- **The organism targets are far larger,** so this limits tissue size before any physics does.

**The request.** Give a global ledger's own summation a rounding allowance at every row. It is derived from the sum's
term count and magnitudes, so that the bound at steps 0 and 1 is no tighter than float64 can resolve the sum. It
loosens no bound beyond what that rounding requires. Every planted fault the checks catch today is still caught.

**First reading (the lead), for the design note to settle:**
- **Derive the allowance from the sum itself,** per row: for n terms, a bound of the form γ_n·Σ|x_i|. It is not a
  constant.
- **Or make the global sums compensated (Neumaier),** on the host and the device, which brings their rounding to
  about one ulp of the total. That might also close D330's GPU gap. The two approaches can combine.
- **Bitwise:** only a check-side quantity changes, so a world's state path does not move.
- **The test:**
  - the line's, the sheet's and the field's first-window shares, before and after;
  - the existing seeded-fault rows.
- **A new GPU qualification is separate,** and the user's decision (D336).

**Status (24 November):** logged. A design note comes first.

**Correction and design note (24 November, D370):** in the `ledger_limits` family the row-1 bound is not the bare atol, since the running allowance is already about 98% to 99.9% of it. What grows with the cell count is the check's own summation. Design note: `docs/LEDGER_ROUNDING_DESIGN.md` on `fr53-design`, recommending one compensated sum and one bound form with declared classes.

**Priority (D371):** normal, by the user, after D370's correction.

## FR-54 — Passive neutral diffusion between two finite liquid regions, qualified against the exact two-well solution; then a wash at a diffusion-connected node

**Logged 24 November 2026 by the user, priority high (D341).**

**The request:**
1. **Qualify the diffusion.** Passive neutral diffusion between two finite liquid regions in
   `resolved_pump_composite@1` is compared with the exact two-well solution: the first step's mass transfer and
   dissipated free energy, across positive background concentrations and time steps.
2. **Explain a stopped run.** When the energy check stops a run, it reports the residual it computed and the
   tolerance it allowed.
3. **Qualify the wash on that basis.** Use the diffusion benchmark to qualify withdrawal and refill on a
   diffusion-connected finite node: `scheduled_compartment_wash@1`'s liquid exchange (D246), with FR-10's
   schedule.

**First reading (the lead), for the design note to settle:**
- **The reference is a closed form.** For permeance PA between volumes V₁ and V₂, a step h moves
  Δn = (c₁ − c₂)(1 − e^(−kh))/(1/V₁ + 1/V₂), with k = PA(1/V₁ + 1/V₂). The dissipated free energy is the drop in
  the two wells' ideal free energy. Both can be evaluated exactly, so the references are code-blind and tagged
  before any engine reading.
- **Tolerances come from the integrator's order and the step,** by derivation. Each case is compared at the step
  sizes declared in advance.
- **The background concentrations:** the note states what a positive background changes in the composite's
  neutral route (activity, volume or nothing) before the cases are fixed.
- **The stopped-run report is a small engine change.** It is tested by a refusal row whose message carries both
  numbers.
- **The wash at a diffusion-connected node** stays refused today (D246: faces at an exchanged node stay refused until
  measured). This qualification is that measurement. It lifts the refusal only for the qualified form.

**Status (24 November):** logged. A design note comes first.

**Addition (24 November 2026, later; items 1 and 2 stand):**
- **Two heat laws, one reference.** The default face heat and `exact_free_energy_heat@1` (D280's exact choice for
  faces) both run against the closed form.
  - **The reference** is the closed form's dissipated free energy.
  - **The subject** is the default face heat, held to its derived tolerance.
  - **The control** is `exact_free_energy_heat@1`, held to rounding alone. A miss there points at the harness, not
    the law.
- **Item 3 is one native run:** diffusion, then a withdrawal and a refill at a connected finite node. It has three
  separate checks, each against its own independent expected value:
  - the tracer removed: the fraction f of the node's amount just before the wash;
  - the tracer supplied: the buffer's amount in the refilled volume;
  - the heat released during the refill: the mixing heat in D246's small-ratio form.
- **The refusal it lifts.** `scheduled_compartment_wash@1` version 1 refuses a node that a face touches (D246 item 5),
  and any neutral species crossing the node's surface by a declared path. The qualification lifts that refusal only
  for the qualified form: one neutral species crossing by a passive route.

**Acceptance target (24 November 2026, later):**
- **The setup:** equal volumes holding 8 and 2 fmol of free solute just before the withdrawal.
- **The wash:** half the volume of the first compartment collects 4 fmol.
- **At the exchange:**
  - the first compartment keeps 4 fmol, plus any solute in the refill;
  - the second still holds 2 fmol.
- **The diffusion** before and after the event is compared with the analytical solution at successively smaller steps.

## FR-55 — An input-dependent closing rate for regulated availability: closed until one lab's same-patch record of closing at two calcium levels exists

**Logged 24 November 2026 by the user, priority high (D344); lowered to normal by the user (D351).**

**Why.** Two separate groups' recordings each contradict carrying one closing rate across calcium doses for SK2
(D338).
- Hirschberg's plateau and washout predict a 10.63 ms activation, against 4.1 ± 0.6 ms measured.
- Oliver's high-dose washout bounds the low-dose rise at 48.1 ms, against about 80 ms reported.

`cells.species_regulated_availability`'s closing rate is fixed and input-independent. D351 reads the two records as an
indication pair in opposite directions, not a confirmed finding; the design note checks the plateau condition first.

**The request.** An opt-in closing rate that depends on the input, for dose-dependent deactivation.
- It keeps the state in [0, 1], with no overshoot and detailed balance where it applies.
- It keeps the current form exactly when not declared, statically absent (D148).

**First reading:**
- The design note chooses the closing rate's form from the cited data, not from one study.
- It is qualified against both groups' records with each preparation's own inputs.
- The Lean lane's rise-time bound, ln 4 × the washout time constant, holds only for a fixed b. The new form states its
  own bound.

**Status (24 November):** logged. A design note comes first.

**For the design note (D351):** under the confirmed-means-replicated definition, SK2 is an indication pair with opposite signs. Hirschberg's rise is faster than one rate allows, and Oliver's low-dose rise is slower; the one shared quantity, the high-dose rise, agrees (4.1 against 4.46 ms). A monotone input-dependent closing rate fits both only if the macropatch plateau is at least 0.93. A same-patch rise and washout would settle it.

**Status (26 November 2026; D390, D394):** closed, not built. Its design note (`fr55-design`, 6109cfad) recommends no build: the two published records do not support a dose-dependent closing rate (D378). The user's decision is not to build it, and to reopen it on one lab's paired low-dose record (D390). The Lean track's search found none (D394): Pedarzani et al.'s closing after a low and a high calcium pulse (about 40 and 32 ms) is read from a figure and not stated to be one patch, and Hirschberg et al.'s one patch at three calcium levels shows a rising share of long openings but no trend in its closing times. Neither is a same-patch closing record at two calcium levels, D351's condition, and a single study is an indication only. FR-55 reopens when such a record exists.

## FR-56 — A temperature-dependent molecular footprint

**Logged 24 November 2026 by the user, priority normal (D344).**

**Why.** Two independent methods confirm that fluid POPC expands on warming (D340).
- Scattering gave +4.7% over 30–50 °C.
- Solid-state NMR gave +16.7% over 28–48 °C.

`cells.bilayer_geometry@1` takes a fixed footprint per species. A world compared across temperatures shows the expansion
only through footprints declared per temperature.

**The request.** An opt-in footprint law, a(T) = a(T_ref)(1 + α(T − T_ref)) or a sourced form, with α declared and
sourced per lipid. The two methods disagree on its size, so α is a declaration, never a constant of the law. It is
statically absent unless declared.

**Status (24 November):** logged. A design note comes first.

## FR-57 — Passive tracer carried by a prescribed liquid flow between finite liquid regions

**Logged 24 November 2026 by the user, priority high.**

**Why.** This follows FR-37. Today a wash (`scheduled_compartment_wash@1`) exchanges a node's liquid with a declared
buffer, and its sample goes to a record (D246). No operator carries one finite region's liquid into another, so a
prescribed flow cannot be expressed: buffer in at Q, through chambers in series, and out to a collector.

**The acceptance example:**
- **The setup:**
  - two equal, internally well-mixed chambers A and B, of volume V each;
  - all the tracer starts in A;
  - clean buffer enters at a constant flow Q, and the outlet is collected at the same rate;
  - no diffusion and no binding.
- **The targets,** after one residence time V/Q:
  - flow A → B → collector collects 1 − 2/e = 26.42% of the tracer;
  - in a fresh run, flow B → A → collector collects 1 − 1/e = 63.21%.
- **The report:** the tracer in each chamber and in the collector. Their sum equals the starting amount.
- **Both targets follow from the fluid balance,** with no fitting.

**First reading (the lead, with the advisor), for the design note to settle:**
- **The two targets alone do not test a flow.** Any two-stage first-order chain gives them, so a first-order transfer
  between two nodes would reach them with no liquid moving. That does not count as shown. The note adds rows that
  only a flow passes:
  - unequal volumes, so the rates come from Q/V;
  - two dissolved species carried by one declared Q, while a bound species stays;
  - a plant reversing the order, which must give the other row's number;
  - a plant that skips the mixing in B, which must fail.
- **One mechanism.** A flow is D246's liquid exchange, with the sample routed into a node and the supply drawn from a
  node or a declared inlet. It is written as a general operator, not a one-experiment one, with FR-54's note, after
  FR-44 lands.
- **The inlet and the collector** are records or nodes. A collector node grows in volume.
- **Volume:** at every chamber, inflow equals outflow. Anything else is refused by name.
- **Scheme and tolerance.**
  - The references are closed forms, and a train of small exchanges reaches them only in the limit. So the note
    states an exact coupled step, or a split with its order.
  - It derives the tolerance at the declared steps.
  - The sum closes to a derived rounding bound.
- **Energy:** the note says what mixing dissipation the flow books. Otherwise the composite's energy check stops the
  run.
- **Version-1 refusals:**
  - ions, since D246 requires same-composition ions;
  - a flow beside diffusion or binding at the same node.
- **Wording:** "one residence time" is V/Q of one chamber, and "clean buffer" is D246's trace-level buffer.
- **D148:** statically absent unless declared. Existing washed worlds stay bitwise unchanged, and a restart mid-flow
  is bitwise.

**Status (24 November):** logged. A design note comes first, with FR-54's.

**Addition (24 November 2026, later): a free-energy check for the flow.**
- **The check.** At volume flow Q, incoming concentration x and resident concentration y, the ideal mixing loss rate
  over RT is Q[x ln(x/y) − x + y]. It is checked against the chambers' storage and the inlet and outlet free-energy
  fluxes.
- **The cases:**
  - a uniform stream (x = y) carries tracer with zero mixing loss;
  - flow off gives zero flow contribution while diffusion continues.
- **First reading (the lead, with the advisor):**
  - **The one-mechanism link.** Expanding D246's per-event mixing heat to first order in f, with fV = QΔt, should give
    this rate. The remainder sets the scheme's order.
  - **The identity closes only with the −n term** in the free energy. The note names the engine's convention.
  - **"Flow off while diffusion continues"** meets the version-1 refusal of flow beside diffusion, so it arrives with
    FR-54's qualification. At Q = 0, the run equals its diffusion-only twin, bitwise.
  - **In an initially empty chamber,** x ln(x/y) reads the trace level. The note states the trace and the expected
    refinement, as FR-59 must.

**Addition (24 November 2026, later): a growing collector.**
- **The case.** Start with an empty tube at zero volume. Deliver 1 pL of 1 mM neutral tracer, then 1 pL of 3 mM.
  - The tube ends with 4 fmol in 2 pL, at 2 mM.
  - The first portion has zero pooling loss.
  - After both, the total ideal mixing loss is 0.523248 RT·fmol, which is 1 fmol·ln(1/2) + 3 fmol·ln(3/2).
- **The reversed order** gives the same total, with different per-portion losses.
- **This settles the collector's form:** a tube at zero volume holds no trace, so the collector starts as a record and
  grows in volume.

**Correction (24 November, later; D362):** two deliveries book (0, 0.523248) RT·fmol in either order; only the second
delivery's split between resident and arriving liquid differs. The order-dependence check uses a third delivery: 1, 3
and 3 mM gives (0, 0.523248, 0.137341), and 3, 3 and 1 mM gives (0, 0, 0.660589). Design note: `docs/LIQUID_ROUTING_DESIGN.md`
on `fr54-57-design`, one router that takes over the wash.

## FR-58 — A label on an exchangeable group, carried through reversible conversions

**Logged 24 November 2026 by the user; priority normal (the user, D365).**

**Why.** A selective tracer, an exchangeable chemical group, can move between species at chemical equilibrium while
every concentration stays constant.
- Today's labels follow species rows (FR-42).
- The transporter's label contract refuses a species changed at only one end (`docs/NEUTRAL_LABELS_DESIGN.md`).
- `local_species_reactions@1` returns one-way moves for labelled rows, but no declaration names which group crosses
  each conversion.

**The request.** For a law with physically specified one-way rates, a definition names the exchangeable group on each
side.
- It reports the expected labelled group on each species.
- Each direction carries its donor's label fraction.
- The physical trajectory is preserved.
- A law that gives only a net rate needs a separate kinetic basis, and is refused by name.

**The acceptance example.**
- **The setup:** A−X + B ⇌ A + B−X, with 1 fmol of each of the four species and forward and reverse rates of 1
  fmol/s. Initially all the X is labelled, on A−X.
- **The targets:**
  - label arrives in B−X at 1 fmol/s at first;
  - after 1 s, B−X holds (1 − e⁻²)/2 = 0.43233 fmol of label;
  - total label stays at 1 fmol, and the net extent at zero.
- **Disabling the observation** preserves the amounts, heat and work.

**First reading (the lead, with the advisor):**
- The target is any two-pool exchange, so the plant with teeth is a net-rate reader, which gives zero.
- Add unequal pool sizes, and a second group that does not cross.
- Check which reaction laws expose forward and reverse rates separately.
- It follows FR-50, the one-way records, and FR-44, labels across a wash.

**Status (24 November):** logged. A design note comes first.

**Status (25 November, D385):** the note's question 2 is ruled (b): a flux-force cycle law carries the label in complete cycles, with a limited
claim (a lower bound where partial steps exchange it). Label on ATP through the Na/K pump also needs row fuel for that pump, a
candidate request. On hold with the other builds (D383).

## FR-59 — Reversible transport into an initially empty finite ion pool

**Logged 24 November 2026 by the user; priority normal (the user, D365).**

**Why.**
- `nak_atp_mass_action_positive@1` is a positive-domain law: no floor, and invalid trials are refused. Its rate stays
  finite as the outside potassium goes to zero while the other substrates stay positive.
- A finite receiving pool that starts empty can gain ions on the first reverse transfer.
- The chemical potential of an empty ideal pool is singular. Evaluating the initial logarithm, or inserting a
  numerical floor, changes the accounting problem.
- Today Cells keeps every species positive at an active node through a declared trace.

**The request.** A boundary-capable law or integration path, qualified for a finite receiver.
- **The start:** positive inside potassium, and positive sodium and fuel.
- **The comparison:** the initial signed current at zero outside potassium, against the analytic one-sided limit from
  the positive domain.
- **Over a finite interval, under step refinement:** a positive potassium gain, the 3 Na / 2 K cycle stoichiometry,
  the capacitor charge, and the integrated work and heat.
- **The limit used:** the ideal mixing free energy's n ln n → 0 at zero amount.
- **Documentation:** the separate boundary physics needed to hold a reservoir at zero activity.

**First reading (the lead, with the advisor):**
- The hardest of this group. It runs against @3's standing rule that every species stays positive at an active node.
- The first step's free energy per ion diverges, so the note must state the refinement order it expects.
- A held zero bath stays refused.
- FR-47's true zeros in the deterministic representation (E2) are the nearest precedent.

**Status (24 November):** logged. A design note comes first.

## FR-60 — Work at a scheduled change of a state's energy

**Logged 24 November 2026 by the user; priority normal (the user, D365).**

**Why.** An external controller can change a molecular state's energy while every molecule stays in place.
- The assembly family carries per-phase standard potentials in the world definition.
- Its events report the state free energy, heat and reservoir work.
- No scheduled level change books its own work.

**The request.**
- The finite state is carried through a switch at a declared time.
- The externally supplied work is recorded as the new state free energy minus the old, at identical counts.
- This stays distinct from chemical exchange, and from the heat of the relaxation that follows.
- An interval with frozen reactions isolates the two switch records.

**The acceptance example.**
- **The setup:** one carrier, in either of two neutral, equal-energy states, with probability 1/2 each.
  1. Raise the second state's energy by k_BT ln 3.
  2. Let it equilibrate with a heat bath: its probability falls to 1/4.
  3. Restore the original levels.
- **The ensemble-mean switch works** are +k_BT ln(3)/2 and −k_BT ln(3)/4.
- **The net input and the bath heat** are both 0.27465 k_BT.
- **A finite-time check** uses the actual occupancy at the second switch.
- **Both switches** preserve every count.

**First reading (the lead, with the advisor):**
- One carrier is below the deterministic envelope, so the note names the representation: exact events.
- Ensemble means take `agreement.py`'s spread class, with a derived ensemble size.
- A new schedule kind gets D339's checks of count, time and kind from the start.

**Status (24 November):** logged. A design note comes first.

## FR-61 — An overdamped rotational load: angle, speed, work and dissipation

**Logged 24 November 2026 by the user; priority normal (the user, D365).**

**Why.** No torque or momentum ledger exists. MODULE_SYSTEM §7's version-1 rule (a) folds every kind's ledger terms
into today's ten ledgers by role. A mechanical work ledger reopens that limit, which is a decision for the design note
and the user.

**The request.** A rigid rotor in the overdamped regime takes a positive rotational drag and a signed applied torque.
- It reports the angle in radians, the signed angular speed, the mechanical work the torque's source supplies, and the
  viscous dissipation.
- The declaration says who supplies the torque. For a chemical source, it names the ion or fuel current that closes
  the source's energy balance.

**The acceptance example.**
- **Constant torque.** 12 pN·nm for 0.5 s against a drag of 3 pN·nm·s/rad gives:
  - a speed of 4 rad/s;
  - an angle of 2 rad;
  - 24 pN·nm dissipated.
- **Variations:**
  - doubling the drag halves the speed and the work;
  - reversing the torque reverses the displacement, and the dissipation stays positive;
  - a locked rotor has zero displacement and zero work.
- **Variable torque.** Zero torque for 0.5 s, then 12 pN·nm for 0.5 s:
  - the mean speed is 2 rad/s;
  - the integrated viscous work is 24 pN·nm;
  - the mean-speed shortcut gives 12 pN·nm, which is wrong.
- **Angular units.** A load calibrated per revolution per second (Hz) and one per rad/s give the same torque and work:
  - 20 pN·nm/Hz at 5 Hz gives 100 pN·nm;
  - 20/(2π) pN·nm·s/rad at 10π rad/s gives the same 100 pN·nm;
  - one revolution takes 200π pN·nm of work.

**First reading (the lead, with the advisor):**
- On its own this is ω = τ/γ. Its teeth are planted errors: the mean-speed shortcut, and a 2π factor.
- It shares one design note and one mechanical ledger with FR-62.

**Status (24 November):** logged. A design note comes first.

## FR-62 — Ion transfer coupled to a rotary step

**Logged 24 November 2026 by the user; priority normal (the user, D365).**

**Why.** Cycle laws account for proton transfer and membrane voltage (`proton_coupled_atp_synthesis_cycle`), but no
transition books angular displacement and load work.

**The request.** A reusable rotary step: one transition books signed ion transfer, angular displacement, the work
exchanged with an external load, and the electrochemical free energy drawn from the reservoirs.

**The acceptance example.**
- **The setup:** a homogeneous, isothermal rotor with energetically identical angular positions and exactly one ion
  per forward step. The reservoirs supply 3 k_BT per forward transfer, against a constant opposing torque.
- **Local detailed balance, by the load work per forward step:**

  | Load work per step | Forward-to-reverse rate ratio | Mean currents |
  | --- | --- | --- |
  | 2 k_BT | e | Forward |
  | 3 k_BT | 1 | Zero |
  | 4 k_BT | e⁻¹ | Reversed |
- **One reverse ion transfer** is counted for every backward step.
- **Over a stationary interval,** the reservoir free energy drawn, minus the load work delivered, equals temperature
  times the total entropy production, on average.
- **It assumes** tight coupling and one reversible transition type.

**Also requested:**
- **A reference implementation with existing reactions.**
  - A three-state cyclic register distinguishes every forward and reverse step.
  - Each transition couples to two pairs of held species: one pair supplies the ion free energy, and the other
    receives the load work.
  - The angle is unwrapped from the signed events.
  - Both one-way counts are reported, even at zero mean current.
  - A finite-reservoir version updates ion inventories and the capacitor charge at each event.
- **A viscous-load check.**
  - The drag declares its convention: Hz or rad/s.
  - Torque balance and the mechanical work over time are checked.
  - A fluctuating torque integrates drag × ω² over the residence times.
  - Reversing both the voltage and the log activity ratio reverses the drive. The rotation changes sign, and the
    dissipated work stays positive.
- **A calibration-range readout for mechanical feedback.** Where a rate reads a measured force table, report:
  - the force per engaged unit;
  - the rate applied;
  - the time spent below, inside and above the table's range;
  - the time at zero occupancy, separately.

**First reading (the lead, with the advisor):**
- The entropy identity holds on average, so it needs an ensemble size and a derived tolerance.
- Check that the existing-reactions benchmark parses today, and which side of the "no physics in validation" line its
  host-side angle falls on.
- The force-table readout may have no host law yet. If so, it is logged as waiting.
- It shares one design note with FR-61, and so reopens MODULE_SYSTEM §7 rule (a).

**Status (24 November):** logged. A design note comes first.

## FR-63 — A pH-dependent Kv1.5 activation

**Logged 24 November 2026 by the user, priority normal (D353).**

**Why.** Three labs agree in direction that acidification shifts Kv1.5's activation positive. Under D351's definition
this is confirmed in direction.

| Lab | System | n | Shift |
| --- | --- | --- | --- |
| Trapani | HEK293 | 5/3 | +11.7 mV |
| Longobardo | Ltk− | 38/27 | +17.3 mV |
| Kehl | — | 6 | +7.8 mV |

The sizes differ. `kv1p5_mh@1` is a parity law with no pH input.

**The request.** A new law, leaving the parity law unchanged: Kv1.5's activation reads the local proton activity, with
a declared and sourced shift per pH unit. The size is a declaration, since the labs differ.

**First reading:**
- **pH comes from the cell's proton row,** through the existing pH machinery.
- **Qualification:** against the three labs' direction, with each preparation's own solutions. The size is calibrated
  per preparation.
- **The K–pH interaction** (external K protecting the available current under acid) is an indication pair. It is
  reported, not judged.

**Status (24 November):** logged. A design note comes first.

**Re-formed (24 November, later; the user's decision, D356):** the request becomes a declared pH shift on Kv1.5's
population, in FR-64's general mechanism, instead of a new law. The parity law stays untouched, and the shift's size per
pH unit is still declared and sourced per preparation.

## FR-64 — A declared voltage shift on a channel population

**Logged 24 November 2026 by the user (D356); priority normal (the user, D361).**

**Why.** Two confirmed findings have one shape:
- Kir2.1's block shifts with external K (D355);
- Kv1.5's activation shifts with acid (D351).

In each, the voltage a factor reads is moved by a declared function of a local activity. FR-51 gives a reversal
reference to its block alone, and FR-63 asked for a new Kv1.5 law. One mechanism serves both, and later channels,
without a new law per channel.

**The request.** A channel population declares, for each factor that reads voltage (its gates, its block), the shift
that factor reads:
- **none:** the membrane voltage, the default;
- **an ion's reversal:** V − E, with E from that ion's compartment concentrations;
- **a sourced shift per pH unit,** from the local proton activity.

The set is closed: a new kind of shift is a new request.

**Constraints:**
- **Parity laws are untouched.** A population with no declared shift runs bit for bit as now.
- **FR-51's block** moves its `reference` key into this mechanism after FR-51 lands, with no aliases.
- **FR-63** is served by this mechanism.

**First reading (the lead's read of `fr51-slot-refusal`):**
- `channel_block` computes V − E for the block only;
- `channel_kinetics` hands the gating laws the plain membrane voltage;
- the block law already takes any reference voltage.

So the change is in the model's plumbing, one reference voltage per factor computed in `channel_rates`, and in no law.

**Status (24 November):** logged. A design note comes first, before FR-51's block law is registered and before the
rename's design note.

**Design note (24 November, D361):** `docs/VOLTAGE_SHIFT_DESIGN.md` on `fr64-design`.
- **Version 1** admits all four reader and kind pairings, and claims two: the block on reversal, and the gates on pH.
- **The build** comes after FR-51's follow-up and the rename.

## FR-65 — Turnover beside a changing volume

**Logged 24 November 2026 by the user, high, as part of FR-43's request (D365).**

**Why.** FR-43 asks for shared pools at fixed and at changing volume. Turnover in a swelling cell is still refused at
parse ("reads volume as declared"; D347's gap 4), so a cell whose volume changes cannot carry turnover. This is D301's
composition M3.

**The request.** Turnover reads the current volume and the activity masks, rather than the declared ones, so that it
composes with:
- water (a swelling or shrinking cell);
- partition;
- membrane insertion.

Concentrations then follow amounts over the current volume, with the material and energy ledgers closed.

**First reading (D301):** the cheapest case with a changing volume, with declared reads only, at 2 to 2.5 agent-days
plus references.

**Status (24 November):** logged. A design note comes first.

**Design note and scope (D375):** `docs/TURNOVER_CHANGING_VOLUME_DESIGN.md` on `fr65-design`. The first build covers turnover beside water, partition or insertion, pairwise, and admits a lumen at nodes turnover does not read (the user). It is followed by the coupling's reads of the current volume, so that A1 in a swelling cell is admitted.

## FR-66 — A passive fluorescence reader over regional amount exports

**Logged 24 November 2026 by the user, priority medium.**

**Why.** Imaging reads a labelled amount through a microscope's collection, region by region, against a prebleach
reference. Several masks may read the same accepted trajectory. FR-33's regional exports give the amounts, but no reader
turns them into a mask's signal and its ratio to prebleach.

**The request.** A passive reader beside FR-33's regional amount exports.
- **Inputs:**
  - the ordered region IDs;
  - the bright-label amounts per region, in fmol;
  - one collection fraction per region and mask, from 0 to 1;
  - a separately supplied prebleach state.
- **The output, per mask:**
  - the weighted bright amount, Σ_r w_r a_r;
  - its weighted prebleach amount, Σ_r w_r p_r;
  - their ratio.
- **Concentration exports** are converted once, as mM × the region's volume in pL to fmol.
- **A trajectory starting at light-off** needs its own prebleach reference; none is taken from the trajectory by
  default.

**The acceptance case, with three unequal regions:**

| | Region 1 | Region 2 | Region 3 |
| --- | ---: | ---: | ---: |
| Prebleach (fmol) | 1 | 2 | 1 |
| Later (fmol) | 0.25 | 1.50 | 0.75 |

- Mask [1, 1, 1] gives 2.50 / 4.00 = 62.5%.
- Mask [1, 0.5, 0] gives 1.00 / 2.00 = 50.0%.

**Also checked:**
- uniform 50% dimming reads 50% through either mask;
- subdividing a region, at the same weight, preserves its signal;
- observation leaves the trajectory unchanged, bit for bit.

**Refused:**
- a region order that does not match the export's;
- invalid weights: outside [0, 1], or not finite;
- a zero selected prebleach signal.

**First reading (the lead).** Nothing on main reads fluorescence, collection fractions or a prebleach state today. The
reader is a host computation over saved regional amounts, with no engine state. It belongs in `src` as a readout,
since it computes a consequence for users, with a closed-form check in the tests.

**Status (24 November):** logged. A short design note comes first.

## FR-67 — Pressure-driven flow on a network of compliant tubes

**Logged 26 November 2026 by the user, priority normal. Design first; no build is scheduled (D393).**

**Why.** Liquid driven through a network of tubes by pressure carries its solutes along, stretches compliant walls,
and over time reshapes the tubes it flows through. Cells moves water across membranes and moves declared volumes
between places (FR-27's washes; FR-54 and FR-57's liquid routing), but it has no network of tubes: no edge law gives a
volume flow along a tube from the pressures at its ends, no wall stores volume against pressure, and no conductance
adapts to the flow it carries.

**The request.** Four parts, each a general law or operator with conserved accounting:
1. **Flow on a graph.** Each edge is a tube with a Hagen–Poiseuille conductance, G = πr⁴/(8μL). Volume is conserved at
   each node (Kirchhoff's current law). Boundary pressures or inflows are declared.
2. **Compliant compartments.** A node's volume follows its pressure through a declared compliance. A prescribed wall
   activation (a time course of rest volume) drives flow, peristaltic pumping being one case. The wall's work and the
   viscous dissipation are booked.
3. **Advection.** Solutes move with the edge flows, upwind, with amounts conserved to rounding, beside diffusion where
   it is declared.
4. **Remodelling.** Each tube's radius adapts slowly to its wall shear stress by a declared, sourced law with its own
   time scale, separate from the fast flow.

**Acceptance (a proposal for the design note):**
- one tube against Poiseuille's closed form;
- a two-loop network against its Kirchhoff solution;
- solute amounts conserved under advection to rounding;
- one compliant chamber's pressure relaxation against its closed form;
- remodelling's steady state at a junction against its analytic fixed point, where the declared law has one.

**First reading (the lead).** None of the four is on main. Before the design, FR-57's tagged spec is read for
overlap: whether liquid routing's edge flows can carry a time-varying flow from part 1, so that solute transport is
built once.

**Status (26 November):** logged. A design note comes first.

## FR-68 — A consistency check on standard potentials

**Logged 26 November 2026 by the user, priority normal. Design first; no build is scheduled (D393).**

**Why.** A reaction network's equilibria come from its species' standard potentials. A slip in one entry (a sign, a
unit, a factor of ten, a value left at zero) gives wrong equilibria without any run failing, and no check catches it
today. Each mass-action reaction takes its reverse constant from its species' potentials
(`laws/reactions/mass_action.py`), so every cycle closes whatever the values are, and transporter diagrams check
Wegscheider's condition at the registry's own potentials (`kinds/transporter.py`).

**The request.** At check time, before a run:
- each standard potential a world uses states its source and the conditions it holds at (temperature, pH, ionic
  strength, free magnesium); tables held at different conditions are refused by name unless a declared transform
  joins them;
- where a cited source gives a reaction's standard free energy or equilibrium constant, the value from the species'
  potentials is compared with it, and a difference beyond a stated tolerance is named with its residual;
- a reaction whose constant is declared on its own, outside the species' potentials, joins a cycle-closure check:
  Σ_r v_r ln K_r = 0 over each independent cycle of the stoichiometry.

**Acceptance (a proposal):** a consistent table passes; one planted slip (a sign, a factor of ten, a value left at
zero) is caught and named against its cited reaction value; tables at two pH values are refused unless a transform is
declared.

**First reading (the lead).** Closure around a cycle already holds by construction where constants come from the
species' potentials, so this check's value is in tying each potential to its source and conditions. The design note
decides whether a failure refuses or warns.

**Status (26 November):** logged. A design note comes first.

## FR-69 — Conservative exchange between a volume and a connected surface

Logged by the user on 26 November 2026. A cell with a fixed surface area per volume can already be modelled with node-local reactions. A rounded rim joins face and side patches with different areas and adjacent finite volumes. Such a connected reactive geometry can today be integrated only outside the engine. The same geometry also arises for membrane polarity and cortical proteins.

**Request.** A membrane patch owns an areal amount and declares its adjacent finite liquid region. For binding flux J = k_on c − k_off σ (amount per area per second), transfer area × J from the bulk inventory to the patch with equal and opposite increments. Here c is the local amount per volume and σ is the amount per area. Lateral diffusion uses a shared edge and the distance between neighboring patch centers, including face-to-rim joins. Retain the physical areas and volumes in exports and account for each species or declared moiety over both dimensions.

**First acceptance example.** Close a volume of 2 µm³ containing 12 amount units against patches of 1 and 3 µm². Use k_on = 0.1 µm/s and k_off = 0.2/s. At equilibrium the volume contains 6 units and the patches contain 1.5 and 4.5. The one-patch reduction for the 1 µm² patch relaxes at 0.25/s. For lateral transport alone, an unequal-density pulse crosses a face-to-rim edge, the area-weighted amount closes and a uniform surface density stays uniform. Exercise unequal bulk volumes, nonnegative amounts and step refinement before transferring to a cell mesh.

FR-28 and FR-46 cover site populations on compartment boundaries. FR-54 covers transport between finite liquid volumes. FR-66 supplies the separate regional fluorescence request.

## Backlog: external tools to look at (logged by the user, 23 November 2026)

The user logged these suggestions to look at later. None is scheduled or adopted.
- **How any of them would enter:**
  - External solvers and simulators run out of process, as references (AGENTS.md).
  - A new runtime dependency in `src/cells` needs the user's approval. FR-17's stage 1 was approved with none.
  - Data licences follow D173: permissively licensed data for judged or published results, under the
    commercial open-source rule.
- **The licences below are as suggested,** still to be verified.

### B1. eQuilibrator 3.0 for consistent standard potentials at scale (relates to FR-43)
- **The concern.** The species capacity is now 1,024 (FR-43 part 1). Standard potentials μ°/RT assembled
  by hand from mixed literature tables can break Wegscheider loop closure, under which the standard free
  energies around any reaction cycle sum to zero.
- **The suggestion.**
  - equilibrator-api (MIT) and equilibrator-cache on Zenodo (CC BY 4.0).
  - Together they give component-contribution estimates of Δ_fG'° at a given pH, ionic strength,
    temperature and pMg, with covariances, across KEGG and ChEBI metabolites.
- **To look at:**
  - a loop-closure check on the potential registry itself, independent of any data source;
  - eQuilibrator as an out-of-process source of declared values, with their uncertainties and attribution;
  - what estimates, rather than measurements, mean for judged runs.

### B2. GPU sparse solves for FR-17's later stages (relates to FR-17 and D317)
- **The suggestion.**
  - Lineax (Apache-2.0): pure-JAX, matrix-free, preconditioned conjugate gradients on the CPU and the GPU.
  - spineax (MIT) and NVIDIA's nvmath-python (Apache-2.0): both wrap NVIDIA cuDSS through XLA's FFI for a
    float64 direct sparse Cholesky. The analysis is cached once per graph, with factorization and solve
    each step.
- **To look at, after FR-17's stage 1.**
  - Stage 1 is the engine's own sparse reduction, with its own minimum-degree ordering and no new
    dependency (D317). Later stages could compare against these tools as references.
  - cuDSS itself ships under NVIDIA's own licence, which needs checking against the commercial
    open-source rule.
  - Iterative solves agree only to their tolerance, so qualification would include bitwise and
    conservation checks.

### B3. XLA command buffers on the GPU (relates to D321), and two Lean libraries
- **The suggestion.**
  - `resolved_pump_composite@1` wraps @3's step in `jax.lax.optimization_barrier`, which keeps compile
    times short (src/cells/models/pump_composite.py). So each scan tick dispatches several sequential GPU
    kernels.
  - XLA's CUDA command buffers (CUDA Graphs), for example
    `XLA_FLAGS=--xla_gpu_enable_command_buffer=FUSION,CUSTOM_CALL,WHILE`, may remove the host's launch
    overhead without changing the modular compile.
- **To look at:** a flag only, with no src change. It is a candidate variant for D321's L4 timing of the
  gap-junction field, checked bitwise against the default.
- **For the Lean lane:** SciLean and Physlib (Lean 4) offer idioms for ODE discretization and SI
  thermodynamics. `lean/` is the Lean lane's, so this is passed to it, not acted on here.
