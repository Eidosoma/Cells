# REF-006 design: junction transport before dynamic gate correspondence

2026-09-16, D107. Source/design review only. No junction-specific native capture
or new production mechanism is claimed. The accepted conservative physical
graph remains useful engineering, but its generic gate is not BETSE's law.

## Source findings to test, not silently reproduce

Pinned [gap-junction classes](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/channels/gap_junction.py)
contain two different models. `Gap_Junction` has evolving state with voltage-
dependent rates; `Gap_Junction_i` is an instantaneous voltage curve. Neither is
a general fitted connexin catalog. The dynamic source cites early amphibian
embryo measurements; [Harris, Spray and Bennett (1983)](https://pubmed.ncbi.nlm.nih.gov/6822860/)
is an experimental lead, not evidence that every tissue shares those parameters.

For the dynamic class, absolute transjunctional voltage is converted to mV;
rates are in inverse milliseconds and `dt` is converted from seconds. The source
uses lambda 0.0013, A1 0.077 and A2 0.14, with a saturated closing-rate expression.
Its implicit update is:

```
g_new = (g_old + dt_ms*(alpha + beta*g_min)) / (1 + dt_ms*(alpha+beta))
g_stored = block * g_new
```

Consequences for correspondence:

1. Blocking scales the **stored gate**, not just conductance. Cells' existing
   physical graph keeps intrinsic gate dynamics separate from availability.
   Suppression/release of these two models is not the same experiment.
2. Native initialization writes `self.gjopen`, whereas `run` reads/writes
   `sim.gjopen`. The initialization formula `alpha/(alpha+beta) + g_min`
   also differs from the unblocked update's fixed point
   `(alpha + beta*g_min)/(alpha+beta)`. Do not silently replace one by the other.
3. In the inspected FULL driver, `update_gj` sits inside the moving-ion loop;
   `update_gj` calls the gate's `run` when voltage sensitivity is enabled.
   Therefore **source inspection suggests multiple gate advances per outer
   step**, depending on ion selection. Measure actual counts, states and
   ordering in a native lifecycle preflight before claiming timed equivalence.
4. Native membrane-face neighbours, surface factors and boundary suppression
   need mapping to Cells' single-owned edges. Two directed records do not
   authorize counting a physical transfer twice.

See the pinned [driver](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/sim.py#L2162).
These are version-specific observations, not a biological endorsement or a
measured runtime result. A future source adapter can reproduce them; the
production model must declare its physical gate law and update semantics.

## Small useful sequence

| Gate | Deliverable | Required checks |
| --- | --- | --- |
| J0: topology and held-open flux | Reuse a supported small native cluster, not the rejected literal one-cell seed | Actual cell/face/edge ownership, areas, lengths, orientations, ion selectivity, boundary masks; no dynamic gate |
| J1: conservative coupled transport | One connected pair within the native cluster, then a small connected network | Opposite endpoint amount changes, valence-derived current, no transfer across disconnected edges, equilibrium/reversal, stage-consistent bath coupling, refinement |
| J2: isolated dynamic law and lifecycle | Separate class-state and simulator-state probes; count gate advances per outer step | Units, initialization, fixed points, voltage symmetry, exact block semantics, time and species-order dependence; observer neutrality |
| J3: explicitly chosen dynamic correspondence | Named physical gate plus a separate native compatibility adapter where needed | Voltage-clamp and free-voltage trajectories, block/release, hidden-state/restart checks; document incompatible models rather than tune them together |
| J4: biological evaluation | Tissue-specific junction conductance and recovery data | Parameter provenance, uncertainty, independent stimuli and tissue-specific scope |

J0/J1 can follow pump contact without waiting for every channel family. Dynamic
gating must not bypass J2. Register exact selected edges after native topology
inspection; no invented pair geometry or assumption that two cells can seed
BETSE independently. Pump and junction mechanisms remain independently testable,
then composed at common stages rather than embedded in a test-specific solver.

## Multiscale/GPU implications

Preserve one oriented flux per physical edge, batched edge laws, scatter/gather
owner maps, explicit gate state and data-defined heterogeneity. A native
species-loop side effect is not an architecture requirement. A physical gate
should advance according to its named continuous/discrete model and solver
stage policy, with coupling convergence demonstrated. Coarse junction bundles
will need effective selectivity and state/history, not only summed conductance.

No junction job is launched by this plan. Source contact, production support,
experimental evidence and GPU qualification remain separate milestones.
