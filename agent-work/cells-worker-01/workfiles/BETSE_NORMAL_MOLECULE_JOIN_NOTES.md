# Real molecule chemistry and transport seam

Chief assigned a new prefix after accepting the feedback and prepared-ER
packages. This is static preparation only. Prior209 protected paths, every
frozen/failed run and Root-owned shared work remain untouched.

The first complete configuration has two genuine low-level Molecule objects,
X and Y, optional genuine simple growth/decay and one irreversible X-to-Y cell
reaction. The original matrix has real molecule growth columns followed by the
reaction column. Original run_loop computes every GAD/reaction rate before any
concentration commit, then commits species and transports each molecule in order.
No supplied chemistry result, fake growth row, reshape or zero-D mover bypass
is introduced. Original zero-Molecule/nonempty-reaction source refusal remains
separate evidence. Full high-level network initialization is not claimed.

All cell, membrane and membrane-sized bath arrays, stale intra-flux cache,
transport flux/cache presence and boundary/static parameters are owned. The
joined network_cache and state identity carry them. Actual native DynamicValue
maps are compared against production live row/object getters and setters.
Molecule constructor, all-target init_growth, update_intra(False), transport,
core loop and mover/update_Co/electroflux/no_negs bodies are literal. Independent
AST construction matches22 numeric bodies, three exception classes and five
unchanged outer helpers without executing scientific AST.

The declared first path is no ECM, instant intracellular mixing, rho_channel1,
no motors/pumping/gating/events/clamps/mitochondria or environmental reactions.
Source computes membrane gradients even before the instant-mix branch, so the
same explicit voltage-geometry membrane radius is owned. Full shell/field,
fluid, ECM and lifecycle state are separate dependencies, rather than inactive
callbacks masquerading as their execution. IP3/finite fuel/buffers and combined
new ER-network chemistry are not part of this package.

Chronology matters. All molecule membrane buffers refresh before chemistry;
membrane movement samples that pre-chemistry cache. update_Co then refreshes
from the new bulk concentration, and GJ movement samples the refreshed values.
Membrane transport uses runtime T, GJ transport configured T. Actual Vm and Vgj
nonce stores persist. Time dilation affects GAD/GJ updates but not membrane
update_Co. Late GJ modulators affect molecule movement immediately and ordinary
ion transport on the next call. Charge/current publication preserves the
literal molecular GJ term in extra_J_mem and its scale_factor projection.

The no-ECM environmental mean is a concrete source conservation defect. Each
site changes by -f*A/vol_env*dt, then source averages. The source-effective
sum(c_env*vol_env) ledger closes, equivalent to M*vol_env at uniform final mean.
This does not rename or reinterpret the original single vol_env metadata. The
single-bath ledger, using mean(c_env)*vol_env, retains the independently derived
dt*(1-1/M)*sum(f*A) defect after chemical and directed-GJ changes are removed.
Both ledgers, observed/predicted defects and directed-GJ imbalance are archived
separately. Chief agreed this boundary. No physical global conservation,
closed-field energy or physiological scale calibration is claimed.

Read-only actual pre-network inputs feed independent stdlib Decimal90/140
forms before model rates are evaluated. These independently compute ordered
controls, all RHS, sequential chemistry/mover state, nonces and publication.
Existing standalone modulation remains a secondary control comparison; rate
tolerances come unchanged from the prior reaction law. The prior configurable
transporter law is different from molecule_mover and provides no new mover
credit. All raw arrays, full errors/budgets/units and both accounting ledgers
are saved before assertions. Scalar intermediate environment values retain
their original numeric type in typed archives.

Planned21 checks:12 new coupled histories and three component controls, each
three calls; two first/second-molecule negative partial failures; four explicit
dependency refusals.17 native captures,45 positive conditional points and90
fresh reference forms; zero independently carried forms or biological cases.
The reaction/growth controls still execute the real mover at D0. The zero-Dm
GJ case also starts with a nonuniform bath so mean/broadcast work stays visible.
Partial failures preserve local mover arrays, globally committed chemistry,
cache presence, nonce and partial charge/current accumulation without a candidate.

The runner requires exact unique pytest IDs and exact complete per-case/native
report sets. It retains480s/group,1GiB process-tree RSS,8GiB reserve and one
explicit CPU/thread. Only an observational callable is excluded from native
source_parameters serialization; all scientific parameters remain. No numerical
launch, scientific import, test collection, retry, detached-job polling, git
mutation or shared PROGRESS edit is part of this static assignment.
# Adapter successor02

Chief reports first Root qualification stopped with four dependency passes,
two raw failures and fifteen unrun checks: `Molecule.transport` eagerly read
missing `ignore_ECM_pump`. This was an adapter failure before the intended
source instability check. Original prepared01 and all failed captures remain
unchanged. No physical failure or positive chemistry credit is inferred.

The original configured initialization assigns `ignore_ECM_pump=True` at
networks.py385. The complete parameter contract and shared fixture now supply
and validate that literal value. Both existing production/native parameter
setattr loops propagate it. Native capture code, all22 scientific bodies,
references, tolerances, five outer helpers and215 protected files are unchanged.
Inverse AST checks remove one parameter-set member/guard and one fixture keyword
to recover frozen01 exactly. Six of ten scientific files remain byte exact.

The stdlib scope-aware attribute audit covers transport/update_intra, mover,
update_Co, electroflux and no_negs, including branch-condition reads and both
Dm/GJ paths under the declared no-ECM/instant-mixing/transmem-False scope. It
finds42 required attributes and no remaining missing producer in either bridge.
Before/after machine-readable witnesses are bound to successor02. This is
static adapter coverage; no scientific execution or numerical retry occurred.

