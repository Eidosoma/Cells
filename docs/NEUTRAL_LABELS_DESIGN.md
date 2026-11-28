# Neutral arrival-time labels (FR-42): desk assessment

**Status: option A chosen (D289); stage 1 built (§7), 22 November 2026, by the kinds owner; stages 2 and 3 (§8, §9) and the kinds' hook (§11, D303 item 6) the same day.**
Sections 0 to 6 are the desk assessment, written before any code at main 184fc81c. **S** marks
this note's own reading or proposal.

**The request** (FR-42 in [FEATURE_REQUESTS.md](FEATURE_REQUESTS.md); D288; erratum B,
[TEMPLATED_POLYMERISATION_LAWS.md](TEMPLATED_POLYMERISATION_LAWS.md) §9.8 and §9.13): a label never
changes the dynamics or the energy.
- Loss is computed once per physical population and shared by label as J n/N.
- Potentials, free energy and heat come from the physical population.
- A new cohort starts at zero.
- Windows count arrivals over [start, end).

## 0. Summary

| | |
| --- | --- |
| **Where a row's own potential enters** | In operators' laws: templated polymerisation's degradation factor, which changes the dynamics. In energy terms: turnover's and exchange's work, every face, route and patch heat (F2's exact face heat included), and @3's chemical free-energy term, which change the books |
| **So** | Neutrality needs a physical population that the energy ledger reads, not operator-by-operator fixes. @3's chemical term and every heat booking sum over a species' rows |
| **Two-sided routes** | Split each one-way flux by its source's shares. For Fick faces and constant-field routes the one-way parts are the law's own two terms. A charged logmean face has none, so it needs a declared one-way form |
| **A cohort at zero** | Possible only if shares are not stored amounts. The physical row stays positive and its shares may be 0 |
| **Recommended** | (A) Labels as share vectors on a physical row: operators and @3 compute on totals, and each one-way flux carries its source's shares. Staged: pools first (FR-38's consumer), then transport |
| **What moves** | No registered world. D1's and FR-33's examples move their booked heat, not their material. FR-38's class rows move about 1e-8 at R1 (development) |
| **Price** | A: 7–10 agent-days in stages, gates included. B, a registry population of sub-rows read by total: 11–15 |

## 1. Where a row's own potential enters today

**(a) In the operators' own laws** (these decide the dynamics):
- **Templated polymerisation's degradation:** J_D = k n (1 − e^y), with y from the polymer row's
  own μ (operators/templated_polymerisation.py, `j_deg`). Each class row reads its own
  concentration, so its factor is 1 − e^(y_f) (N/n_k)^(1/L) (erratum B). **The dynamics change**
  with the number of classes.
- **Turnover's flux** is first-order, k n, and exchange's likewise. The rate reads no potential,
  so **the dynamics are neutral**.
- **@3's faces** (logmean_electrodiffusion@1): for an uncharged row the flux is factor (a − b),
  linear in each row, so **neutral** (D1). A charged row's drift carries L(a, b), which is not
  additive, so **not neutral** (the Lean lane: 72.82% at +10 mV).
- **Patch and junction routes** (constant_field@1, GHK at the shared voltage): linear in each row,
  so **neutral**.

**(b) In the energy terms** (these decide the books, and they are global):
- **@3's chemical free-energy rate,** `1e-3 RT Σ ln(c) × rate` per species row
  (models/surface_pump_v3.py, `chemical = ...`). Each row's own ln c enters. Split rows carry a
  mixing term Σ n_k RT ln n_k that the physical population does not.
- **Turnover's work:** the exact free-energy change of the touched node per row
  (`adapter.species_chemical_free_energy_pJ(n, moved, ...)`), and **exchange's** likewise.
- **Face heat:** the tableau's J RT ln(a/b) per row, and F2's exact_free_energy_heat@1 per row's
  exact decrease. Opposing label gradients book heat where the unsplit species books none (the
  Lean lane's D1 finding). **Route heat** (passive routes' exact booking) is per row too.

**So (S):** neutrality cannot be reached operator by operator. Fixing templated polymerisation's
factor alone would fix the dynamics but not the books. @3's chemical term and every heat booking
sum over species rows, so each must sum over the physical population instead. That needs a
registry-level notion of the physical population that @3, every operator and the energy ledger
read. D1's families declare the grouping, but nothing reads them as one population.

## 2. The share rule on two-sided routes

**Rule (S):** compute each one-way flux on the physical totals, then split it by its source
population's shares. A forward flux carries the source node's shares, and a backward flux the other
end's. New material from a backward chemical flux joins the label the window names. Splitting the
net flux would give FR-33's transfer at equal totals no label movement, since the net is zero while
labelled material crosses one way and unlabelled the other.

| Law | Its one-way parts | Share split |
| --- | --- | --- |
| Fick face (uncharged logmean) | factor a and factor b | J+ s_a, J− s_b. Equals the per-row flux exactly, since the law is linear |
| Constant-field route (GHK) | P A x/(1 − e^(−x)) a and P A x e^(−x)/(1 − e^(−x)) b | Same, at the shared voltage |
| Charged logmean face | None: L(a, b) μ/RT has no one-way form | Needs a declared one-way decomposition, or is refused |
| Reversible mass action (local_species_reactions@1) | k+ Π reactants, k− Π products | Each by its own side's shares |
| Templated polymerisation's degradation | k n (forward), k n e^y (backward, re-synthesis) | Forward by the polymer's shares. Backward joins the window's arrival label |
| Turnover, exchange | One-way already | By the source's shares |

## 3. A cohort that starts at zero

The engine refuses a non-positive stored amount at any active node: @3's domain at every checked
state, and since the guard (6f3aa8f2), the binding closure's held totals at every stage. So a label
**row** cannot start at zero. D1's rows and FR-38's class rows start at the inventory trace, which
FR-42 forbids.

**Shares can be zero (S)** if they are not stored amounts:
- the physical row stays positive, and the domain checks only it;
- a share vector s_k ∈ [0, 1] per node with Σ s_k = 1 carries the labels;
- a new cohort's share is exactly 0 at its window's start, and grows by its arrivals.

The domain then checks the shares by value: finite, each in [0, 1], and summing to 1 within
rounding.

## 4. What moves

- **Registered worlds: none.** No registered world declares a family or class rows, and with
  static switches the undeclared programs are unchanged.
- **D1-labelled worlds and FR-33's examples** (the first test, the synapse acceptance, the
  two-node control):
  - their material and transfer records stay the same, since the laws are linear;
  - their booked face heat changes, to the physical population's value. That resolves D1's
    docstring caveat;
  - **F2's trace start** becomes an exact zero start.
  - The host tracer (FR-33's one-way pulse-chase) is unaffected.
- **FR-38's class rows** are replaced by shares (D288). The 1 − e^(y_f) (N/n_k)^(1/L) departure
  vanishes: about 1e-8 relative at R1 (erratum B), and up to percent level near the domain bound.
  Route 1's blank subtraction is no longer needed. Route 2, cohort.py, stays as the host-side
  check.

## 5. The design options

**A. Labels as share vectors on a physical row (recommended, S).**
- **The declaration:** the registry declares a species' labels, a list of IDs. @3's state gains
  `label_share` [label, node] for that species, only where declared (a static switch, as K4's
  readouts do).
- **Dynamics:** every law computes on the physical row's total, as today, so the dynamics are
  unchanged by construction.
- **Shares:** each step updates the shares from the step's one-way fluxes (§2). Each mover reports
  its one-way parts for a labelled species, a contract addition for operators and kinds. @3's
  faces and routes report theirs from their own two terms.
- **Energy:** the physical row only. Nothing reads a share, so free energy and heat are unchanged.
- **D148, crossrev and G1:** unchanged for every world without labels.
- **Checkpoints:** the new field appears only where declared, so a checkpoint version for labelled
  worlds only.
- **Price, staged:**
  - Stage 1, pools: the registry's labels; @3's share state; turnover's and templated
    polymerisation's one-way reports; windows by step index (as FR-33's step_index); FR-42's
    checks 1 to 3 in one pool. **3–4 days.**
  - Stage 2, transport: faces and routes report one-way parts; the charged logmean face refused
    without a declared decomposition; FR-33's first test rebuilt on shares. **2–3 days.**
  - Stage 3: exchange, reactions and kinds' one-way reports, each by its owner. **1–2 days.**
  - Gates: about 1 day.
  - **A in all: 7–10 agent-days.**

**B. A registry-level population with labelled sub-rows that every law reads by total.**
- Each sub-row stays a stored species row.
- Every law, @3's chemical term and every booking read the family total for rates and potentials,
  and split their moves by sub-row shares.
- The positivity domain must exempt sub-rows, so that zero is allowed.
- It touches every law's read path, @3's field and energy terms, and the binding closure.
- D148: every family world's records move; registered worlds stay unchanged.
- **Price: 11–15 agent-days,** across every owner.

**C. Host-side only** (cohort.py's method generalised: the run's per-molecule loss J/N and the
arrival history).
- Exact for a well-mixed pool under any loss law, so FR-42's reference case passes on the host.
- It cannot follow labels through two-way transport, since @3's records are net.
- **Price: 2–3 days,** and it leaves FR-33's transfer case unserved.

**Recommendation (S): A, staged.** Stage 1 serves FR-38's rebuild (D288). Stage 2 serves FR-33's
transfer. C remains the host-side cross-check, as route 2 is for FR-38.

## 6. The requester's acceptance checks, and how each would be built

1. **Unlabelled and 1, 2 and several labels from one initial state,** including unequal shares, an
   empty label and a state near the edge of the supported concentration range.
   - Under A the physical fields are identical bit for bit across label counts, since no law reads
     a share. The check compares every physical state field and the energy ledger's records
     between K = 0 and each K, exactly.
   - At every comparison time the shares sum to the reference total.
   - The edge case: templated polymerisation's degradation near y → x_dom, where the class rows
     departed by percent.
2. **Arrivals at a window's start and at its end, with older material present.**
   - The window resolves to step indices (FR-33's step_index). Production in the step that starts
     at the window's start joins the cohort; the step that starts at the end does not.
   - Survivors are checked against an independent calculation: the arrival history times
     exp(−∫ J/N dt), from the run's own per-molecule loss, as cohort.py does.
3. **Two physical populations with different loss laws, one labelled.**
   - Each keeps its own reference trajectory, bitwise against its unlabelled run.
   - The labelled one's shares account for all its material at every time.

**The reference case, dN/dt = −N².** Of today's laws, a second-order loss is mass action
(2A → B in local_species_reactions@1, with B removed or held). So stage 1's acceptance needs either
that law with one-way reports, or a test-only law. N(t) = a/(1 + a t): the new cohort is 1/4 of
3/4 at t = 1, against blank subtraction's 1/12.

## 7. Stage 1 as built (pools)

**The operator.** Labels are an operator, `neutral_arrival_labels@1` (operators/species_labels.py),
not a registry key (the lead's approval). The registry is host side only, and the share state, each
step's arrival label and the update reach the traced program. A composition's types are keyed on
its law tuple, so a world without the operator keeps its composition key and its programs by
construction.
- **The declaration:** `species`, each with its `labels` (one to 16, distinct) and its `initial`
  shares by node, a list that may be empty.
- **The base** is each species' first label. It holds unlabelled material: all initial material
  at every node not listed, and every arrival outside a window. Unlabelled material counts as a
  share, as FR-42 asks.
- **The schedule:** `label_arrivals`, per species, gives the label that each step's arrivals join.
  - Switch times are exact multiples of dt, and each step's label is the one in force at its start.
  - Steps are resolved by step index with execution/grid.py's `same_instant`, the predicate D283
    names for label switches. So arrivals in the step that starts at a window's start join it,
    and those in the step that starts at its end do not.
  - `label_arrivals` is a new consumer of the on-grid rule, for D283's stage 2 to sweep.
- **The state:** `label_share` [labelled species, label, cell] and `label_outside_share` [...,
  outside node], padded labels at 0 under a presence mask. Checkpoints carry it, and a resume is
  bit for bit, in process and through a snapshot.
- **A diagnostic:** `label_closure_relative`, the largest closure residual of any reporter's
  half-step. It measures each reporter's own consistency. That no other mover touched the row is
  the refusals' to hold.

**The interface** (operators/contract.py, the lead's leave; one for every operator, agreed with the
gene regulation agent). A reporter's `half_step` takes `labels=(rows, arrival)` and returns
`(state, valid, moves)`, its state and validity bit for bit the unlabelled call's.
- **moves:** `(out [m, node], into [m, label, node], transfers)`, from the same combination as the
  booked move.
- **The node axis:** cells, then outside nodes. A reporter at cells only may give its cells alone.
- **transfers:** `()` until stage 2.
- **The composite** (models/pump_composite.py `_half_step`, the lead's leave) advances the shares
  after each applied half-step of a reporter. That covers the midpoint path's second half-step;
  its predictor runs unlabelled. Without a label owner no call changes.
- **The reporters:**
  - turnover: its booked clearance out, its production in;
  - reactions: each driven route's extent times its consumed and produced coefficients, with the
    lead's leave for species_reactions.py;
  - templated polymerisation: the gene regulation lane's side, 824da76b.

**The update** (numerics/label_shares.advance). Over one half-step it solves
n1 = n0 e^(−u) + I φ(u), φ(u) = (1 − e^(−u))/u, for u ≥ 0 from the engine's own n0, n1 and the
arrivals I, by bisection with a fixed count. Each label's material is then n0 s e^(−u) + into φ(u),
and the shares are that over its sum.
- **Non-negative for any step.** Zero stays zero until a label receives arrivals, so a new cohort
  starts at zero.
- **Exact for a constant per-molecule rate,** with constant arrival rates, within a half-step.
  Turnover is such a case.
- **Without arrivals the shares are kept bit for bit,** whatever the loss law. FR-42's reference,
  dN/dt = −N², is therefore exact: the new cohort is 1/4 of 3/4 at t = 1, where blank subtraction
  gives 1/12.
- **Otherwise second order.** With k(t) and a(t) varying within a half-step of length h, the new
  material it attributes exceeds the exact amount by (a(0) k′(0) − a′(0) k(0)) h³/12 + O(h⁴), and
  the old falls short by as much. That is second order over a run, as Strang splitting is.
  - A halving row measures this: per-halving ratios of 7.7 to 7.9, and the coefficient within 0.8%
    at h = 0.0125.
  - The error vanishes when a and k vary in proportion.
- **Never the totals:** they are the engine's, so no record of the physical state moves.

**How FR-42's check 2 is computed** (against the run's own per-molecule loss rate). The cohort's
survivors at T are the arrivals of its window's steps, each carried by exp(−∫ k dt) to T.
- Within each step, k = one-way loss / n, from the run's records.
- Where k is constant within each step (first-order clearance at a scheduled rate), that
  calculation and the update agree at rounding. The test row measures 8e-16 against the analytic
  solution, at both boundaries.
- Elsewhere they agree to the update's second order.

**Refused in stage 1** (fail closed; each refusal names the stage that lifts it):
- **Stage 2:** a labelled species moved inside the inner step, by a face, a route, a channel, a
  pump, a kind or an in-step process (registry `moved_in_step`). Rows refuse a face, a membrane
  and a junction route, and a transporter kind's moved role and finite fuel. Today's pumps hold
  their fuel as parameters, so no fuel row of theirs is moved.
- **Stage 3:** exchange on a labelled species, and a passive reaction route on a labelled row.
  The reactions refuse the second themselves.
- **No stage plans these yet:**
  - other operators that write species amounts in their split parts without reporting;
  - events that write amounts;
  - closers, retirers, and providers of the amount references, such as a bath schedule.
- **D1's families:** a world that declares them admits only turnover and declarations beside them
  (D1's own refusal), so the label owner never meets a family row and reads no family. Shares
  replace family rows.
- **The composition matrix** (docs/PUMP_COMPOSITE.md) marks the law-level refusals "d" and lists
  the data-level ones.
- **Not refused:** RK4 on the coupled path. It is vacuous, since a coupled RK4 composition already
  refuses every split-only part, so no reporter runs there.

**What moves: nothing.** Worlds without the operator keep their programs, which crossrev and G1
check in the gate. In labelled worlds every physical field, observation and diagnostic is the
unlabelled run's, bit for bit, in each test row.
- **FR-42's check 1 as rows:** five pools in one labelled run against one unlabelled run, not one
  run per label count. The pools are independent, so each is its own initial state labelled its
  own way.
- **D1's and FR-33's examples, before and after:** all 422 history and observation arrays of their
  five worlds are bit for bit main's, and so are their diagnostics.
- **Templated polymerisation's reports (824da76b),** checked in a scratch merge only:
  - every record is bit for bit the unlabelled run's;
  - the shares sum to 1 within 1.1e-16;
  - the closure is within 1e-16.
- **The reactions' rule:** a species on both sides of one route counts its net, so a catalytic
  copy is never relabelled. Stage 3's owners inherit that rule.

## 8. Stage 2 (transport), and pools and sources (D296): the label owner's side

**The inner step's report** is the @3 owner's side, to the rule the lead confirmed.
- Faces and routes report their one-way amounts over the step:
  - for an uncharged face, c a and c b;
  - for a constant-field route, the GHK terms.
- Under ARS222 and N2, those amounts are the trapezoid of the start and end fluxes, plus the O(dt³)
  gap to the booked net, added to the side whose sign it has. So forward − backward equals the
  booked net at rounding, both are ≥ 0, and both are second order.
- Under the Euler IMEX, the stage terms are combined directly. RK4 refuses labels.

**The transfer update** (numerics/label_shares.advance_transfers).
- Each node is advanced by stage 1's kernel. Its arrivals carry their sources' shares: first at the
  step's start (predictor), then at the mean of start and predicted end (corrector).
- **Order:** second order. Measured against the exact linear exchange of three nodes, the error
  falls 3.9 to 4.0 times per halving.
- **Domain:** non-negative, and the shares sum to 1.
- **Exactness:** exact, at rounding, where no source's shares change.

**The composite** (models/pump_composite.py `_labelled_inner`). Where the inner step takes
`labels=` (static, by its signature) and the tableau is IMEX, the inner step returns its transfers,
and the owner advances the shares from them. Without a label owner, or before @3's side lands,
today's call is unchanged.

**What stage 2 admits.** Where the inner step reports, it admits:
- an uncharged face;
- a membrane route and a junction route (constant_field@1).

Refused, each naming why:
- a charged face, which has no one-way form;
- channels, pumps and operators' in-step processes;
- kinds, which wait for their hook after @3's side;
- RK4 beside any followed mover.

**Measured against exact rows** (tests/unit/test_region_label_shares.py and
tests/unit/test_neutral_labels_transport.py; @3's side merged).
- **The method:** each case runs plain rows of the same material in the same world. Transport is
  linear in each row, so those rows are the exact reference.
- **FR-33's first test, rebuilt on shares** (validation/regions/example.first_test):
  - **Transfer:** the shares follow P_L within 5.4e-7 of the label's scale, and 1.4e-7 at half the
    step: 4.0 per halving, second order.
  - **Local loss:** the shares and the cleared label match at rounding.
- **Routes:** a junction and two membrane routes carry the shares within the same bound (8.3e-10
  for label a's total).
- **A label's total over the nodes** holds to the update's second order in general. It is not
  conserved by construction, since each node's shares are normalised on their own. In the worlds
  measured it held at rounding: by symmetry in FR-33's, and within 3.7e-16 in the routes' world,
  which has no loss.
- **Labelled and unlabelled twins,** with every report non-zero: FR-33's transfer (a face), the
  routes (a junction and patches), exchange's export and a passive S ↔ P route. Each was run with
  and without the label owner. Every history field, observation and diagnostic is bit for bit
  equal, and the closure diagnostic reads at most 1e-16. The routes' twin is a test row.
- **Inner reporting** beside declared kinds: off until the kinds' hook, now on (§11).

**Pools and sources** (D296, operators/contract.py).
- **Reporter flags:** a reporter flags `LABEL_POOLS` or `LABEL_SOURCES` (static). It declares its
  pools, `label_pools`, entries of its own state holding a labelled species' material (the
  release hold), and its sources, `label_sources` (its chains).
- **Sources:** the owner's schedule may name a source. Each step a source reporter receives its
  sources' arrival labels, `source_arrival`. A source without its own switch takes its species'
  window.
- **Pools:** a pool reporter returns a pools part:
  - its pools' start and end amounts;
  - new material into them by label;
  - their losses;
  - `carried`, material that keeps its labels between sites, row sites (j N + k) and its pool
    entries.
- **The owner holds** `label_pool_share` [pool reporter, label, pool entry]. It advances a pool
  reporter's rows and pools together as sites, through the same predictor-corrector. A site with
  no move keeps its shares bit for bit, and the closure diagnostic covers both.
- **Limits:** labels may number up to 64 per species (producer × window). The domain's allowance is
  128 ulps.
- **Rows** (NumPy, no world):
  - a release carries the hold's shares;
  - a completion enters the hold at its label;
  - with no release the row keeps its shares bit for bit;
  - each source takes its own schedule, or its species' window.

**Replacement** (D284 and D296; the lead's leave for a minimal hunk in replacement@1's file).
- **The event reports what it replaced.** replacement@1's event takes `labels=rows` and also
  returns the slots it replaced. Its state and validity are bit for bit the unlabelled call's.
- **The owner relabels each replaced slot:** its labelled shares become the label in force for the
  species at the event step, the newcomer label.
  - The departing material leaves with its own shares.
  - A donor copy's material is newcomer material too. It does not inherit the donor's shares.
- **What leaves is recorded** (erratum E, TEMPLATED_POLYMERISATION_LAWS §9.18; FR-38's step 5).
  - Each event reports only its own material, so the two still commute: replacement@1 the slots
    whose rows it swapped, and a pool reporter's event the amounts it emptied from its pools
    (`removed [P]`, in label_pools order).
  - The owner records by label the amount before the event times its shares just before it,
    cumulative from t = 0: `label_removed_fmol` [labelled species, label, cell] for the rows,
    `label_pool_removed_fmol` [pool reporter, label, pool] for the pools. An emptied pool entry
    takes the base label. replacement@1's report no longer touches the pools.
  - Both records are zero-size unless a replacing event is declared (D148 case 2), and restart
    carries them as state. Beside a replacing event, a pool reporter whose event takes no labels
    is refused (fail-closed).
  - The gene unit's `removed` report comes with FR-38's step 4 branch.
- **Producer identity across generations:** a source's schedule may switch its label at the event
  time.
- **Still refused:** replacement@2 (its event does not report). So is a template that would make a
  labelled species membrane-permeable, which replacement@1's own check already refuses as a new
  leak.
- **The composition matrix** admits replacement@1 beside the owner.

**What moves.** Worlds without the owner: nothing. Labelled worlds: the owner gains
`label_pool_share` and the control `label_source_arrival`, both empty where no reporter declares
pools or sources. So a stage-1 labelled checkpoint (development; none registered) does not
resume across this change.

## 9. Stage 3: exchange and the reactions' passive routes (the lead's leaves)

**Exchange** (scheduled_species_exchange@1).
- Its half-step sums each route's amount moved over its palindrome, stage by stage. It reports that
  sum as a transfer from the route's source to its destination: an export from the cell to its
  outside node, an import back. The transfer carries the source's shares.
- The owner advances such a reporter on the combined node axis, as it does the inner step
  (`advance_nodes`).

**The reactions' passive routes** (local_species_reactions@1).
- Each route's forward and reverse extents are the SSPRK(3,3) combination of its stages' one-way
  rates, combined as its extent is from its net rates. A driven route's are its extent and 0,
  bitwise as before. A passive route's are its two unidirectional fluxes.
- The forward extent consumes max(−ν, 0) and makes max(ν, 0), the reverse the opposite. So a species
  on both sides of a route counts its net in each direction.
- Chemistry makes new molecules, so products join their species' arrival label. A passive route's
  reverse flux re-makes its reactants at theirs.
- The refusal of a passive route on a labelled row is gone.

**What stays the same:** with labels, both operators' states and validity are bit for bit the
unlabelled calls'. Without labels nothing of theirs is traced. The owner's closure diagnostic reads
rounding for both.

**Kinds** (transporters, passive-route kinds) report through their own hook (§11).

## 10. D1's label families retired (D300)

The user's direction: D1's families, separate rows with their own potentials, are removed rather
than kept beside shares. "We don't want old backwards compatibility — we're still in heavy dev, not
even at alpha."

**Removed:**
- **The species registry's families:** the `label_families` key, `Family`, `family_of`,
  `family_rows` and `check_families`, with its operator check and the row-linear constants. The
  labels owner names the reported movers' laws itself.
- **The region export's family path:** summed rows, `host_transport`, and the hosts' records.

**Replaced:**
- **FR-33's examples run on shares:** the first test, and the synapse acceptance. Plain rows of the
  same material ride beside as the exact reference.
- **The readouts read a label's amounts from the shares** (`readouts.label_nodes`), and classify the
  owner as moving no amount.

**No registered world declared a family:** no definition in the repository names `label_families`.

## 11. The kinds' hook (D303 item 6)

Declared kinds report their labelled rows' one-way moves through two optional hooks of the kind
contract (registry/kind_registry.Kind). @3's half is in models/surface_pump_v3.py, under the lead's
leave for the kinds owner.

**The contract.**
- `label_refusals(declaration, species)` -> reasons: host side, at the definition, judged on the
  kind's moved rows and only for the labelled species given.
- `label_transfers(start, end, p, dt, rows, *, weight=None, xp)`: the labelled rows' one-way amounts
  over the step, each >= 0, on the core's combined node axis.
  - `start` and `end` are LabelViews: the state, the kinds' stage read, the node potentials and the
    routed control. `p` is the presence-gated layout the kind's rates see.
  - Under ARS(2,2,2), N2 and other tableaux: the trapezoid of the kind's one-way fluxes at the two
    ends. Under the Euler IMEX: weight = dt a[last, 0] times the start's.
  - Either way, the gap to the kind's own booked net (its cumulative field, end less start) is added
    on the side its sign gives. So forward less backward is the booked move at rounding, both stay
    >= 0, and nothing is stage-weighted.
- **Static:** @3 calls a kind's hook only where rows are labelled, after its own transfers. KindRates,
  the per-stage programs and every unlabelled trace are unchanged (D148 case 2), at two evaluations
  per labelled step.

**What each kind does.**
- **Passive routes:** the neutral, leak and charged constant-field kernels are linear in their two
  ends at a fixed voltage. So the inward flux is the kernel with c_in = 0, and the outward one is
  minus the kernel with c_out = 0: no new kernel, and the FR-4 and FR-5 law files unedited. The
  booked net is `passive_transferred`. A labelled row a rectifier moves is refused.
- **Transporter,** both layouts: every flux-force form runs J = J+ (1 - e^x), so each mode's one-way
  cycle rates are J+ = k a S and J- = J+ e^x (Hill's). A crossing row moves |nu| J+ from the end
  where it is consumed to the end where it is made, and |nu| J- back: version 1's from the patch's
  cell to its outside node, the population axis's between N and P. The booked nets are
  `transporter_cycles` and `cycle_count`. Refused, reading each population through its general form:
  - a net-flow form, which has no one-way rates;
  - a species changed at one end only (chemistry there);
  - a held row the law changes (held fuel: its maintenance's new material is not reported);
  - unequal counts at the two ends.
- **Patch damage** moves no row, so its label_refusals give none. Kinds without rates (the stage
  read, the pH condition) need neither hook.

**Central refusals** (operators/species_labels.in_step_errors; kind_registry.label_refusal_errors):
- a kind with a rates hook and no label_refusals, while any row is labelled (fail-closed; @3's
  labelled step refuses it statically too);
- a kind's move of a labelled row without its label_transfers;
- a labelled species a closure holds at some node (a kind's stage_rows: B4's proton row and buffers
  at buffered nodes, rapid_binding@1's closure rows), whatever moves it.

The composite's inner step now reports beside declared kinds (`inner_reports_labels`). MT-1b's forms
face is not on main yet, so its refusal line in `label_errors` comes with the face builder's branch
(docs/MITOCHONDRIA_DESIGN.md §7: whichever lands second adds it).

**Measured** (tests/unit/test_neutral_labels_kinds.py; the refusals are rows of
tests/unit/test_neutral_arrival_labels.py).
- **The compiled twin:** a neutral passive route and a neutral transporter crossing, labelled against
  unlabelled. Every history field, observation and diagnostic is bit for bit equal, and the closure
  diagnostic reads rounding.
- **Zero net flux:** S's labels exchange at the route's one-way rate P A c, at rounding of the closed
  form (2.2e-16). The update's predictor-corrector gives the two nodes' difference e^(-2u) per step
  exactly.
- **The split, which the closure cannot see:**
  - each kernel's two terms are its law's own, and J- / J+ = e^x;
  - a planted halving of the one-way amounts leaves the closure exact and misses the zero-net closed
    form by 0.074.
- **The gap** is O(dt^3): it falls 8.000 times per halving for a route and 8.005 to 8.009 for the
  pump.
- **Beside a face:** a kind carrying Q leaves labelled face-moved S admitted, with S's face
  transfers the kind-free twin's bit for bit.

**What moves:** no registered world, since worlds without labels keep their programs (crossrev and
G1). Labelled worlds beside kinds, refused before, are admitted where the kinds report.

## 12. Producer labels derived from the replacement events (amendment G, D307)

TEMPLATED_POLYMERISATION_LAWS §9.20 chose option (a): the label owner derives each producer's label
and schedule, so a schedule can no longer disagree with the events (operators/species_labels.py,
`derived`).
- **The declaration:** a species' entry names its chain sources, `producers: [{source, windows:
  [{label, from, to}, ...]}]`. Window times are on the clock's grid inside the horizon, increasing
  and disjoint.
- **The derivation,** at the definition and on the host:
  - the chain's cell comes from a source reporter's `label_sources`, and that cell's occupants from
    replacement@1 (species_common.occupants), keyed by cell ID;
  - the labels are `<cell>-g<k>-<chain>` for each generation k (the founder 0, then each newcomer
    in event order) and `<cell>-g<k>-<chain>-<window>` for each window, after the species' own,
    within MAX_LABELS;
  - the source's schedule is the generation's label from its birth, its window's inside each
    window, and the next generation's from the next event's step.
- **One authority:** a hand-written schedule for a producer source is refused, and so is a producer
  that is no source reporter's chain at a cell.
- **Bitwise:** on FR-38's step-5 world the derived definition binds to a correct hand-written one's
  types, initial state, layout and every control array bit for bit (tests/unit/
  test_neutral_labels_events.py).
- **Identity:** the definition keeps `producers`, not the derived labels. So a restart derives the
  same, and so does a reordering of the cells, since names follow cell IDs and generations the
  event order.
- **Batches:** the derived label count follows a cell's replacement events, which a declaration
  does not hold, and the batch check compares declarations' signatures only. So version 1 batches
  a definition that declares producers with no other world: its signature holds a part equal to
  nothing (fail-closed; a batch of one runs).
- **The gene unit's check** compares a release's two fate rows' declared labels. Each fate row
  should declare the same producers, so their derived lists agree.

## 13. Liquid exchanges (FR-44, D327)

**What it admits:** the label owner beside the compartment wash (`scheduled_compartment_wash@1`),
in either order.
- **Before FR-44 each refused the other.** The owner refused an event that writes amounts without
  reporting them. The wash refused the owner, which follows labelled material only through
  reported moves.
- **Both refusals are lifted, each with a check:**
  - The wash reports each exchange.
  - The owner is shown local to the wash, since it moves no amount.

**The report** (`operators/contract.py`). An exchanging event's `event` with `labels=rows` returns
`(state, valid, LiquidExchange)`: removed and supplied, each [labelled species, outside node] in
fmol.
- **They are the wash's own per-event level records** (`wash_last_sample_fmol`,
  `wash_last_supply_fmol`) at the labelled rows, masked by the nodes due in this step.
  - A cumulative record's gain would be inexact.
  - At f = 1 after an earlier wash, the kept part n − (fl(c + n) − c) is nonzero in about half
    of random cases and negative in a quarter (the design's probe).
  - A row plants this on two concrete cases.
- **The state and validity are the unlabelled call's,** bit for bit. The report only reads the
  records.
- **The axis is the outside nodes,** the record's. An exchange of a cell's own liquid cannot be
  expressed in version 1 (the coordinator's approval, 24 November 2026). The kernel itself is
  axis-free.

**The kind.** Each labels-taking event has one report kind (`LABEL_EVENT`, `contract.label_event`):
- "replaced", replacement@1's, from `EVENT_REPLACES`;
- "emptied", a pool reporter's, from `LABEL_POOLS`;
- "exchanged", declared by the wash.

The composite passes the kind to the owner, which reads the report by it, never by the report's
shape. A labels-taking event with no kind, or with one that its declarations contradict, is refused
by `contract.label_event_error`:
- at registration, by `check_declarations`;
- in a composition, by the owner.

**The map** (`numerics/label_shares.exchange`). With n the row's amount just before the event, r
the sample and a the supply, each label's material after is (n − r) s_k + a [k = 0]. The shares
are that over its sum.
- **The sample is well mixed,** so it carries the node's shares: every label loses the fraction f.
- **The buffer carries no label and joins the base,** even while a window is open (D327).
  - A buffer is not an arrival.
  - A replaced slot differs: its newcomer material takes the label in force.
- **The map is exact in the amounts it is given:**
  - a zero share stays 0;
  - a base-only row stays (1, 0, …);
  - at f = 1 every other share is exactly 0, since r = fl(1.0 n) = n.
- **A labelled ion keeps its amount,** since its buffer is the node's own composition. Its shares
  still become (1 − f) s + f at the base.
- **Labels carry no free energy,** so the energy ledger is the unlabelled run's (option A, D289).

**The record** `label_outside_removed_fmol` [labelled species, label, outside node] holds what left
at each exchange: the sample times the shares just before it, cumulative from t = 0.
- It is zero-size without an exchanging event (`exchanging`), so every other labelled world keeps
  its fields (D148 case 2).
- `same_physics`'s exact set gains it (D327).
- Its domain check (finite, ≥ 0), its view set and its summary follow erratum E's records.

**The books.** Where only the wash moves a labelled species at a node, each label's material there,
plus its record, less the wash's supplied record at the base, equals its start to rounding. The
twin row checks this on every row.

**What stays refused:**
- **A path that moves a neutral species across a washed node's surface:** the wash's own
  refusals (D263).
- **Site populations beside labels:** `cells.operator.site_occupancy@1` writes amounts without
  reporting them. Admission by species (§14) lifts this where the populations bind unlabelled
  ligands.
- **A compartment beside the wash:** the compartments' admitted list refuses it until FR-49's wash
  narrowing. FR-49's C1 world, which is also the inherited three-way composition, is a refusal
  row.

**Tests (D224):**

| File | Rows |
| --- | --- |
| `test_neutral_arrival_labels.py` (NumPy) | The map on six rows, with two plants failing; a wash and a replacement in the composite's event stage, in both orders; turnover's clearance at a washed node keeping the diluted shares; the report kinds on planted declarations; `same_physics`'s set |
| `test_wash_schedule.py` (NumPy) | Either order parses; the labelled event's report, in NumPy and compiled; a whole wash after an earlier one, with plant 5 failing on its two cases; a labelled gene-unit export and a labelled exchange route at the washed node refused, each parsing beside a wash of another node; FR-49's C1 world refused |
| `test_neutral_labels_events.py` (compiled) | The twins: five washes, three of them at 3/7 (D266's condition); every physical record bit for bit; the identities, the records and the books on every row |
| `test_wash_schedule_resume.py` (compiled) | The resume across a wash, at the wash row through a snapshot and one step after, with the redo and skip plants |

## 14. Admission by species (FR-44 step 3; D327, D424)

**What it admits:** `cells.operator.site_occupancy@1` beside the label owner where no ligand of its
populations is labelled, with four partners: the wash, D152's reactions, turnover and exchange.

**The rule** (`species_labels.operator_errors`, `BY_SPECIES`).
- **Before:** every split part that writes species amounts and reports no one-way moves was
  refused, whatever species it wrote.
- **Now:** a writer on `BY_SPECIES` is admitted if it declares its rows (the contract's
  `ROW_MOVES` and `written_rows`, FR-43 part 3's one authority; D327's `written_species` hook
  became these) and none of its written rows is a labelled species.
- **The test is by species, not by row.** A labelled species has shares at every cell and
  finite node, and an unreported change at any one of them would be carried onward by every later
  transfer.
- **The list holds the site operator alone.**
  - Its half-steps write amounts only at its pools, which are exactly its written rows, and they
    keep every other entry bit for bit.
  - A host row holds this on patch, node-owned, contact and internalising populations, with a
    plant.
  - The other six writers that report nothing keep today's refusal, word for word: the injection,
    trafficking, the unit producer, both lumens and the integer population.

**Refused by name beside an admitted writer** (`by_species_errors`, fail closed), each until a world
qualifies it:
- **every operator law but the four partners,** named in one message. Among them:
  - `cells.operator.cell_owned_compartments@1`, named as FR-49's C4, registered by amendment. This
    is C4's one home (D424). Its four-way form and its three-way form without a wash stay refused
    whatever the compartments' own list admits.
  - `cells.operator.templated_polymerisation@1`, which World L declares;
- **an internalising population,** which no registered world needs, and **a population that binds
  from a cell** (an inward patch face or a contact). The twin qualifies binding at outside nodes
  only, so an admitted writer writes no cell row in version 1;
- **the inner model's later options,** FR-45's list beside sets:
  - `cells.model.resolved_pump_tissue@3`'s own one-way records;
  - a blocked channel population;
  - a declared voltage shift;
  - the sparse field solver;
  - X2, which is attached after the definition's checks, so the owner's binding refuses it.

**Still refused:**
- **A labelled ligand.** It waits for sites as label reporters (D327's priced follow-up).
- **Shared site sets beside labels,** by FR-45's partner rule.

**Tests (D224):**

| File | Rows |
| --- | --- |
| `test_neutral_arrival_labels.py` (host) | The rule on planted declarations; the refusals by name on parsed worlds, contact and inward populations among them; a declared kind beside the sites, admitted on an unlabelled species and refused as today on a labelled one; the inner model's options; C4's four-way and three-way forms with FR-49's two list entries patched in; the site operator's pools equal to its written rows, with a plant |
| `test_neutral_labels_sites.py` (compiled, new) | FR-44's twin world with the well's sites kept and Cl and Q labelled, beside the four partners. Every physical record is bit for bit the unlabelled twin's; the well's identities at each wash; in the specimen, the base gains exactly exchange's import and the cohort exactly turnover's production |

**No new state:**
- no resume row and no FR-49 judge erratum are needed;
- `same_physics`'s set is unchanged;
- D148's criteria hold by construction, since only definition-time and binding-time checks
  change.
