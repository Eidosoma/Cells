# A few integer units on shared pools (`cells.operator.integer_unit_population@1`)

**In one sentence:** A few membrane machines switch on and off one at a time, each working machine moves a dissolved substance across the membrane, and switching depends on how much is there.

## In plain words

Some cell functions rest on only a few molecules, such as a handful of channels, transporters or
machines. With so few, chance matters: each one assembles, opens or falls apart at a random moment.
This [operator](../../GLOSSARY.md#operator) follows such a small population exactly, unit by unit,
in clusters on a membrane patch. Each active unit lets an uncharged dissolved substance pass
downhill between the cell and the finite space outside it. The units' switching can speed up with
that substance's concentration, so the units and the supply shape each other. Other processes, such
as a steady production or removal, chemical reactions or gene expression, can change the same
supplies. When a cell divides, each unit goes to one daughter or the other at random. The units
store no energy; only the substance does. Left out: charged substances, saturable transport, and
changing volumes.

## Seen from each field

- **Biology:** low-copy channels, transporters or machines whose random assembly or gating drives
  a flux, and their random (binomial) partitioning at division.
- **Chemistry:** mass-action propensities counted in ordered tuples, optionally proportional to
  one concentration; passive permeation between two finite pools of one neutral species.
- **Physics:** a piecewise-deterministic Markov process. Between events the two pools relax
  exponentially, and each event fires when the integrated hazard reaches its exponential threshold.
  The heat of every move is the free-energy drop, never negative.
- **Computing:** a split part whose half-steps are closed form, with the events located inside
  them in a fixed trip of segments. Its counter-based Threefry streams are keyed by seed, site,
  domain and counter, and its owned state divides through the composite's lifecycle hook.

## At a glance

<!-- generated: at-a-glance -->

| | |
| --- | --- |
| Piece | Operator, interface `cells.operator@1` ([its fields](../../DECLARATIONS_FORMAT.md#operators)) |
| ID | `cells.operator.integer_unit_population@1`; definitions write `cells.operator.integer_unit_population@1` |
| Runs in | `cells.model.resolved_pump_composite@1`, its host. Definitions of `cells.model.resolved_pump_composite@1` can declare it |
| Where it acts in the step | A split part, by `located_events_exact_transfer_half_steps@1` |
| Needs | No law or kind |
| Provenance | Not yet extracted: the composite's operator contract has no provenance field yet |

<!-- /generated -->

## What it reads and changes

<!-- generated: touches -->

| Field | Role | Axes | Unit | Which way is positive |
| --- | --- | --- | --- | --- |
| `membrane_active` | Reads (current, at the split stage) | | 1 | |
| `extracellular_amount_reference` | Reads (current, at the split stage) | | fmol | |
| `volume` | Reads (fixed, at the split stage) | | pL | |
| `extracellular_volume` | Reads (fixed, at the split stage) | | pL | |
| `integer_counts` | Owns | integer_site, integer_state | units | Not stated |
| `integer_hazard` | Owns | integer_site | 1 | Not stated |
| `integer_threshold` | Owns | integer_site | 1 | Not stated |
| `integer_events` | Owns | integer_site | events | Not stated |
| `integer_channel_events` | Owns | integer_site, integer_channel | events | Not stated |
| `integer_clock_s` | Owns | integer_site | s | Not stated |
| `integer_clock_carry_s` | Owns | integer_site | s | Not stated |
| `integer_transferred_fmol` | Owns | integer_site, integer_route | fmol | From inside to outside: "a positive amount has left the cell of the site's patch for that patch's outside node" |
| `integer_transfer_dissipated_energy_pJ` | Owns; heat | integer_site | pJ | Not stated |
| `integer_energy_magnitude_pJ` | Owns | integer_site | pJ | Not stated |
| `integer_divided_units` | Owns | integer_site, integer_state | units | Not stated |
| `integer_trace_time_s` | Owns | integer_site, integer_trace | s | Not stated |
| `integer_trace_channel` | Owns | integer_site, integer_trace | index | Not stated |
| `integer_trace_cell_fmol` | Owns | integer_site, integer_trace, integer_route | fmol | Not stated |
| `integer_trace_node_fmol` | Owns | integer_site, integer_trace, integer_route | fmol | Not stated |
| `integer_trace_counts` | Owns | integer_site, integer_trace, integer_state | units | Not stated |

Writes into other pieces' fields: `amount_increment`, booked in `integer_transferred_fmol` and `extracellular_amount_increment`, booked in `integer_transferred_fmol`. Ledgers: `integer_subunits`. Records: `integer_counts` (amount), `integer_hazard` (level), `integer_threshold` (level), `integer_events` (cumulative), `integer_channel_events` (cumulative), `integer_clock_s` (level), `integer_clock_carry_s` (level), `integer_transferred_fmol` (cumulative), `integer_transfer_dissipated_energy_pJ` (cumulative), `integer_energy_magnitude_pJ` (cumulative), `integer_divided_units` (cumulative), `integer_trace_time_s` (level), `integer_trace_channel` (level), `integer_trace_cell_fmol` (amount), `integer_trace_node_fmol` (amount) and `integer_trace_counts` (amount).

<!-- /generated -->

## The mathematics

<!-- generated: bounds -->

None declared.

<!-- /generated -->

With counts $n_k$ of unit states $k$ (each of $w_k$ subunits), amounts $n$ in fmol, volumes $V$ in
pL (so $n/V$ is in mM), rates in 1/s and conductances $g$ in pL/s per unit:

$$a_j = k_j \prod_k \frac{n_k!}{(n_k - r_{jk})!}\,\phi_j, \qquad \phi_j = \frac{c}{1\ \text{mM}}\ \text{or}\ 1, \qquad a_0 = \sum_j a_j$$

$$J = \Big(\sum_k g_k n_k\Big)\left(\frac{n_\text{c}}{V_\text{c}} - \frac{n_\text{o}}{V_\text{o}}\right) \ \text{fmol/s, cell to node}, \qquad H(t) = \int_{t_\text{prev}}^{t} a_0\,ds$$

- **The events:**
  - event $k$ fires at $H = E_k = -\ln u_{1,k}$;
  - its channel is the first $j$ with $\sum_{i \le j} a_i > \min(u_{2,k} a_0, \mathrm{nextafter}(a_0, 0))$;
  - then $N \leftarrow N - r_j + p_j$ and $H \leftarrow 0$.
- **The draws:** $(u_1, u_2)$ is draw $k$ of the site's counter-based stream.
- **Conservation:** every channel conserves the subunits $\sum_k w_k n_k$, exactly in integers.
- **Between events** $u = n_\text{c}/V_\text{c} - n_\text{o}/V_\text{o}$ decays as $u_0 e^{-\lambda\tau}$,
  with $\lambda = G(1/V_\text{c} + 1/V_\text{o})$. So the moved amount and $H$ are closed form,
  and a read on the site's own route follows $c_0 + \delta(1 - e^{-\lambda\tau})$.
- **The heat** of a move $m$ from the cell to the node is
  $RT\,[\,m \ln(c_\text{c}'/c_\text{o}') + n_\text{c}\varphi(-m/n_\text{c}) + n_\text{o}\varphi(m/n_\text{o})\,]$,
  with $\varphi(x) = x - \ln(1 + x)$. Every term is $\ge 0$.
- **At a division**, `independent_segregation` applies this contract:
  - **Inputs:**
    - the parent site's counts $n_k \ge 0$ (integers), $k = 0, \dots, K-1$ in declared state
      order, with $U = \sum_k n_k$ units;
    - $f$, the partition's area fraction of the parent's patch for its first daughter patch,
      $0 < f < 1$;
    - the block size $W$, the largest declared subunit total of any site, so $U \le W$.
  - **The draws:** the uniforms $u_0, \dots, u_{W-1} \in (0, 1)$, draw 0 of the parent site's
    partition stream (domain 2). The uniforms $u_i$ with $i \ge U$ are drawn and not used.
  - **The unit order:** unit $i$, $0 \le i < U$, is of state $k$ exactly when
    $\sum_{k' < k} n_{k'} \le i < \sum_{k' \le k} n_{k'}$: state order, then index.
  - **The rule:** unit $i$ goes to the first daughter site if $u_i < f$, compared in binary64,
    and otherwise to the second.
  - **What each recipient receives:**
    - the first takes $a_k = \#\{i \text{ of state } k : u_i < f\}$ and the second
      $b_k = n_k - a_k$;
    - both must hold no units before, and $U \le W$ must hold (each refused otherwise, as the whole
      step); the parent is set to 0;
    - the signed record books $-n_k$ at the parent, $+a_k$ and $+b_k$ at the daughters.
  - **The invariant:** $a_k + b_k = n_k$ for every $k$ and every draw, exactly in integers, so the
    subunits $\sum_k w_k n_k$ are kept across the two daughters.
- **Scope of the segregation rule.**
  - **Its assumption.** Independence is the rule's assumption, not a result: each unit is
    allocated on its own draw, with one common first-daughter probability, the patch-area share.
  - **One study indicates it can fail for units that are not independent.** Coelho et al. (2014),
    PLoS Biology, doi:10.1371/journal.pbio.1001886, Figure 2E, counted fission-yeast Hsp104
    cytoplasmic aggregates. The figures are approximate plot readings:
    - four foci at division, 32 divisions: a mean absolute sister difference of about 1.0
      (SEM about 0.18), against 1.5, independence's minimum at any common probability, about
      2.8 SEM below it;
    - two foci, 33 divisions: about 0.97 against 1.
  - **The direction:** the daughters were more even than independence allows.
  - **Why it may not transfer.** Aggregates fuse and move under constraint, so the comparison
    does not transfer to membrane units, and one study is an indication only. Flag those
    conditions when the rule is applied to aggregates or to units that cluster.
  - **It is not a test of membrane-bound units.** A direct test needs parent and daughter counts
    paired with the daughters' membrane-area shares from the same divisions, and none exists yet.
  - **Source:** the Lean lane's claim `lean/claims/fr43-integer-segregation.md` (at aae46bde),
    which takes every figure above from that paper.
- **Refused beside a wash.** `cells.operator.scheduled_compartment_wash@1` reads no path of this operator's
  transfers across a washed surface, so the wash refuses it (fail-closed, version 1). Lifting that
  is its own qualified extension.
- **Beside other writers of its rows** (FR-43 part 3). The operator is a transfer: it keeps the
  substance's total. Any declared writer may share a moved row, such as a reaction network, the gene
  unit, turnover, exchange or site occupancy, unless a writer claims the row alone, as the gene unit
  claims its exported and labelled rows.
  - **The order.** Each writer's half-steps run in declared order (Strang's splitting), so the
    event times and the amounts are second order in the step. The event times stay exact where no
    event rate depends on the other writer, directly or through the transfer.
  - **A limit.** Second order holds while the transfer is slow against the step, $\lambda\,dt$ of
    about 2 or less. A world with a faster transfer shows its own halving.
  - **The trace.** The pools recorded at an event are the operator's view inside the step. Beside
    another writer they are first order in the step, so they are reported, not judged.
  - **The bound.** $a_{0,\max}$ counts what other writers can make of a read substance over the
    run. A writer with no static bound on that leaves the site unchecked, and the run-time cap of
    64 events guards it.
- **Refused, never repaired:**
  - a charged moved species;
  - a site on a held bath;
  - a non-conserving channel;
  - more than 1,024 subunits at a site;
  - $dt\,a_{0,\max} > 1$ where it is bounded;
  - a writer of its rows that declares neither kind of move (fails closed);
  - more than 64 events at a site in one half-step;
  - a pool that would not stay positive.
- **Assumptions:**
  - fixed volumes;
  - ideal dilute pools;
  - units that carry no free energy;
  - sites sharing a pool, or other writers sharing a row, split at second order.

## Sources

<!-- generated: provenance -->

Provenance: not yet extracted; the composite's operator contract has no provenance field yet.

<!-- /generated -->

- **Davis (1984)**, on piecewise-deterministic Markov processes. The form of the process is taken
  from it. Named from memory, not read for this page.
- **Haseltine and Rawlings (2002), and Alfonsi et al. (2005)**, on hybrid next-reaction
  simulation. The integrated hazard against an exponential threshold is taken from them.
  - Departure: the crossing is located in a closed form, not on an integrator's stage
    polynomial.
  - Named from memory, not read for this page.
- **Huh and Paulsson (2011)**, on random partitioning at division. The binomial segregation of
  each unit is taken from it. Named from memory, not read for this page.

## How it is checked

<!-- generated: tests -->

Declared test: not yet extracted; the composite's operator contract has no test field yet.

<!-- /generated -->

- **The independent reference.** A code-blind same-draws integration was written from the
  references' spec alone (`validation/fr43_part3/references/`): the same worlds, the same draws,
  and the event rule as equations.
- **What the engine is held to** (the criteria fixed before the references returned,
  `validation/fr43_part3/REGISTRATION.md`):
  - where only the operator moves its pools, its event times must agree at rounding at every
    step;
  - where turnover writes the read pool, the agreement must improve at second order under step
    halving.
- **The planted errors that must be caught:**
  - a two-state world whose assembly rate is ten per cent high must leave the exact closed form's
    band;
  - a split at fraction 0.55 must leave the equal split's binomial band.
- **The checks in the tests:**
  - exact integer conservation;
  - the recorded draws against the spec's table;
  - a same-seed restart, bit for bit.

## Status

<!-- generated: status -->

Not stated: no record states a level for this piece.

<!-- /generated -->

## Links

<!-- generated: links -->

- Declared in [`src/cells/operators/integer_unit_population.py`](../../../../src/cells/operators/integer_unit_population.py), class `IntegerUnitPopulationOperator` (`cells.operators.integer_unit_population`).
- Runs in `cells.model.resolved_pump_composite@1`.
- Manifest entry: (operator, `cells.operator.integer_unit_population@1`), from `python -m cells declarations --out FILE` ([the format](../../DECLARATIONS_FORMAT.md)).
- In the Laws library: `select=laws:cells.operator.integer_unit_population@1`.

<!-- /generated -->
