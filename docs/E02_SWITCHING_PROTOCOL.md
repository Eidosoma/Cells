# E02-SW1: the first longer switching protocol

SPEC-004 / D030, 2026-09-08. **Prospective protocol, not an executed assay.**
Cells remains 0.10.0. Its seven models and accepted short reference panel are
unchanged. The [frozen definition](../configs/reference/e02_switching_protocol_v1.json)
is reference/experiment data, **not a runnable Cells model configuration**.
The [numerical plan](E02_SWITCHING_NUMERICS.md) must pass before implementation
and biological-outcome reporting. [Design checks](../reports/SPEC004_PROTOCOL_CHECK.md)
verify the freeze and case construction, not trajectories.

## Question and smallest useful scope

Can two freely evolving, oppositely prepared neighbours change a recipient's
regulatory phenotype during a fixed contact interval, in either direction?
What happens to the donors, and which transport routes are needed in this
specified model? A numerical pass and a positive switching outcome are separate.

Use three equal-volume cells in a two-edge star. This is the smallest topology
in the completed native neighbour-switching pilot, **not a proven mathematical
minimum**. Our current `bitsey_emt_pair@1` supports only two communicating cells;
extra capacity slots and independent worlds cannot supply the third neighbour.
The next model needs a general fixed-graph extension, not an assay branch in
the solver or two independently evolved pairs sharing a conceptual recipient.

The selected conductance is `2e-15` per edge for miRNA, above the pilot's reported
two-neighbour thresholds (about `1.13e-15` E→M and `1.005e-15` M→E). This motivates
a positive hypothesis, **not a Cells acceptance threshold or guaranteed result**.
Do not search for a more convenient conductance if the hypothesis fails. There
is no threshold search, parameter sweep, donor clamp, removal, proliferation,
memory/relay claim, physical EMT calibration, organ or GPU run in this protocol.

## What the source review changes

The completed [pilot protocol](../../../preprints/ingressing-minds-v-ruliad-paper-ideas/levin-cancer-gj-exploration/PILOT_PROTOCOL.md)
and [results](../../../preprints/ingressing-minds-v-ruliad-paper-ideas/levin-cancer-gj-exploration/PILOT_RESULTS.md)
motivate the geometry and horizons. Read-only inspection of pinned BITSEY
`zombie.py:surround_flip_sims` and `surround_flip_sim` exposes details that the
phrase “500-unit disconnected preparation” alone does not specify:

- The native helper disables miRNA transfer, not all ionic exchange. It takes
  the last returned plotting sample for preparation and the assay predicate,
  not the exact requested or live accepted endpoint.
- It resets regulatory seeds between directions within a network, without a
  fresh ionic initialization. Earlier search state can therefore affect the
  second direction's initial ionic context. It also restores a 0.005 minimum
  native time quantum; that is not a maximum RK4 step.
- The native success predicate requires all cells to lie within an absolute
  distance of 2 from a prepared donor in packet rows 4 onward, including binding
  caches. It is not merely an E/M label or proof of asymptotic stationarity.

E02-SW1 deliberately uses fresh, isolated, exact-duration preparation, full
endpoint transfer and explicitly separate observers. Consequently it is an
**independent source-equation assay**, not exact reproduction of those historical
thresholds. A future native witness must receive the same full prepared packets
and report actual clocks; it cannot silently replace this protocol with the
historical helper. The existing short native/equation evidence remains valid.

The completed [memory-probe report](../../../preprints/ingressing-minds-v-ruliad-paper-ideas/levin-cancer-gj-exploration/MEMORY_PROBE_RESULTS.md)
reports appreciable K/Cl drift despite nearly unchanged regulatory totals.
This reinforces separate preparation, phenotype and full-state drift reporting.
That experiment uses five donors and removal; neither is imported here. R006 in
[Scientific basis](SCIENTIFIC_BASIS.md#r006-selected-switching-protocol-review)
records this review, without rerunning its auditors or adopting live H4b findings.

## Preparation: fixed duration, not “equilibrate until it works”

Prepare E and M independently with the complete ionic/regulatory equations,
maintained bath and pumps, no contact, fresh ions `[10,125,55]`, and fixed
`P=80`, `snail=72`, `ST=0`. Regulatory seeds `[u,m,z]` are `[100,0,0]` for E and
`[0,100,100]` for M. Integrate from 0 to **exactly 500 nominal units**. Use the
existing source-coordinate constants and approximations, not the physical
pair's clock or constitutive laws. No equilibrium-root substitution is permitted.

Before any connected run, qualify these two trajectories independently and
write an immutable preparation receipt. Require:

1. Finite/domain-valid primary state, complete fixed context, derived readouts,
   flux histories, clocks, source/solver identity and passing numerical gates.
2. The intended phenotype at each one-unit observation from 400 through 500;
   signed `u-m` margin at least +10 for E or at most -10 for M. Numerical error
   envelopes must also clear that margin. This is a preparation gate, not feedback.
3. At 500, E/M anchors differ by at least 1 in **each** regulatory coordinate,
   including the numerical uncertainty bound, so distance scales are defined.
4. Per-coordinate end-minus-start drift, peak-to-peak range and maximum absolute
   RHS on the 400–500 observations, with separate ionic/regulatory/voltage units.
   A zero residual or ionic stationarity is **not required or claimed**.

The reference anchor is the refined Radau endpoint only after Radau/BDF/refined
agreement. There are **no generated 500-unit packets yet**. Do not substitute
the old 10,000-unit pair inputs or the exploration's saved preparation. Failure
of these gates leaves the preparation unqualified; do not silently lengthen it.

Copy the same complete E/M primary state and fixed context into every assigned
cell; donors with the same preparation are exact copies. Retain parent receipt,
phase clock and original diagnostic history in provenance. The assay is a new
world at time 0 with new fixed anchors and zero assay ledgers: an explicit
preparation import, not an ordinary exact restart and not a biological replication
mechanism. Reconstruct caches without changing primary coordinates. Candidate
solvers share these anchors for the connected-only comparison; separately test
the full candidate preparation→contact path, so preparation error is not hidden.

## Fixed panel: 14 conditions, not 14 biological replicates

Each condition runs in E→M and M→E directions from 0 to **1000 nominal units**.
Cell 100 is the recipient, 200/300 its possible donors; edges 10/20 point from
recipient to donor. Donors do not contact each other. Maintain all cells' bath,
leaks and pumps; no state-based gates, expression mechanisms or external cues.
All source miRNA approximations remain explicit. No conductance is divided by
degree, and two donor fluxes are summed into the same recipient RHS at each
shared stage. Per-edge flux uses the source whole-cell membrane-area convention.

| Condition | Donors | Donor preparation | Ionic route | miRNA route | Purpose |
| --- | ---: | --- | --- | --- | --- |
| active | 2 | Opposite | On | On | Primary switching hypothesis |
| blocked | 2 | Opposite | Off | Off | Same cells/topology, no exchange |
| ionic_only | 2 | Opposite | On | Off | Remove regulatory transfer |
| mirna_only | 2 | Opposite | Off | On | Isolate regulatory route |
| same_state | 2 | Same as recipient | On | On | Neighbour identity control |
| one_neighbor | 1 | Opposite | On | On | Pair bridge; outcome not prescribed |
| isolated | 0 | None | Off | Off | Autonomous drift/phenotype baseline |

Blocked edges remain present, with their own histories exactly constant. Removing
an edge or donor is not the same intervention. Identical ionic anchors may make
ionic exchange zero in several controls; no nonzero effect is demanded just to
make that ablation interesting. Record donor trajectories and signed delivery;
equal contact time is not necessarily equal transferred material. No RNG,
biological early stopping or replacement of inconvenient outcomes is allowed.

## Observers and interpretation

Observe all cells at integers 0–1000 and the six fixed irregular times in the
JSON. Observation requests do not change the integration grid. The source label
is E if `u>m+2`, M if `m>u+2`, otherwise X. Keep this outside the dynamics.

Primary readout: whether the recipient has its target label at **every recorded
observation** in 900–1000, including both endpoints and the irregular observation
999.613. Report the endpoint label separately. This establishes sampled
finite-window persistence under continuing contact, not continuous-time residence,
post-removal memory, equilibrium or attraction. Report all-cell target agreement
and donor changes separately; a donor can change too.

Also retain each regulatory coordinate's signed and absolute distance to both
500-unit E/M anchors, divided by that coordinate's absolute anchor separation;
full ionic/regulatory drift and RHS; voltage, fluxes and typed local/exchange
ledgers. Labels must never replace the complete state. The native-style maximum
absolute goal distance over its listed rows and all cells is a diagnostic only;
report `<2` separately, including for same-state and isolated controls. Its target
is the opposite preparation, not the donor state substituted by a control.

First sampled target time is an observation, not an exact hitting time. Retain
the preceding non-target bracket and later returns; no target by the horizon is
right-censored. A valid run without terminal switching is a finite-horizon
negative. Reference disagreement or an error envelope touching a label boundary
is **numerically unresolved**, not negative. Invalid/domain-refused trajectories
and resource-limited incomplete runs are separate statuses. Retain all cases.

## Engineering sequence and claim gates

1. **SPEC-004 (this deliverable):** freeze protocol, reviewed source hashes,
   case construction, observer criteria and bounded qualification plan.
2. **NUM-005:** independently implement/check fixed-graph reference composition,
   qualify preparation and long trajectories, publish all passing/failing cases
   and full prepared packets. No production implementation is authorized by a
   numerical failure or a desired biological label.
3. **MODEL-006 / VERIFY-011:** once numerical qualification passes, preserve
   0.10.0 and extend the named source model to fixed graphs through ordinary
   local processes, edge arrays, shared-stage scatter, typed ledgers, masks,
   strict checkpoints and existing scalar/cohort windows. Preserve pair@1
   compatibility; choose the new production identity explicitly. No assay logic
   belongs in the runner. Verify all seven earlier families and graph invariants.
4. **ASSAY-002:** run and audit all frozen production conditions against the
   qualified reference, including independently prepared end-to-end cases.
   A positive switching claim requires that outcome; honest negative results
   remain useful. Revisit M1/E02 closeout explicitly, not automatically.

Future organ geometry and cell/contact count remain data. This fixed graph is
not spatial mechanics, interacting organs or a multirate model. Bounded arrays,
stable axes and complete restart support later scale; GPU throughput, precision,
multirate/coarse interfaces and biological validity require separate evidence.
