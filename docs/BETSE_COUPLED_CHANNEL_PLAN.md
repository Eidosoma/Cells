# REF-004b: channel-to-cell contact, staged design

D088, 2026-09-13. **Source-reviewed design only.** No new native preparation,
coupled trajectory, production change or parameter calibration has run under
this plan. The prerequisite is REF-004a's [isolated-channel closeout](BETSE_VOLTAGE_GATE_CLOSEOUT.md).
The immediate next implementation is a small configuration/transport preflight,
not a large tissue simulation or a replacement integrator.

## What this adds

Close the feedback loop already implemented in Cells:

`m,h → channel permeability → ion transfer → cell/bath amounts → voltage → m,h`

The isolated benchmark checked channel kinetics at prescribed voltages. A
coupled comparison must also establish which state each rate reads, where each
ion goes, how charge changes voltage, and which native output records that flow.
Use existing `finite_extracellular@1`, its pure kernels, channel slots, separate
transfer ledgers and shared checked RK4. No experiment-specific engine branch.

## Findings from the pinned native source

Read directly from v1.5.0, commit `5269a714aa2593ed2a6708c4516289977d8ae1a2`:

1. `Channel.init_channel` supplies a membrane-target array even for `apply to:
   all`; the isolated benchmark used `targets=None`. The tissue pathway must
   therefore test the actual target-index/scatter behavior. Native m/h are
   face-indexed. Mapping them to one Cells channel per cell is valid only when
   all faces of that cell have identical voltage, gate state and parameters;
   check this explicitly, not by averaging hidden states.
2. `run_loop_channels` advances the channel at current `sim.vm`, computes
   `DChan = P * rel_perm * maxDm * moddy`, calls the full electroflux law, and
   updates concentrations immediately through `update_Co` and dynamic mappings
   into the simulator's ion arrays. The zero-time initial P exception remains:
   native initialization does not create P, so label a derived initial product.
3. The channel addition to `sim.fluxes_mem` is commented out. Instead, native
   channel flux is saved as `chan_flux`, while `extra_J_mem` uses `-F*z*f_ED`.
   Export of extra current to the simulator depends on `substances_affect_charge`.
   Thus an ordinary passive-flux observer alone is insufficient for channel
   transfer accounting. Record channel-specific flux, concentration changes,
   extra-current fields and the chosen flag; never count the same transfer twice.
4. In the full native loop, passive flux is assembled before the network
   channel step. The channel performs its concentration update, then the loop
   applies ordinary flux updates and recalculates voltage. Cells evaluates
   coupled amount/gate rates at shared RK4 stages. These are different numerical
   methods: compare corresponding laws and refined solutions, not identical
   discrete updates or gates from mismatched points in the step.
5. The FAST channel path constructs a conductivity/current approximation.
   Use the FULL path for this GHK/amount comparison. Its nonspatial `update_Co`
   still averages outside concentration over membrane faces. Recheck the
   effective lumped volume `M * p.vol_env` for this channel path; do not assume
   the passive-path result alone validates all active bookkeeping.
6. Enabling the default general network also enables unrelated example
   biomolecules/channels. Generate a minimal native configuration with only
   the selected K/Kv1p5 mechanism, not the default Nav/KLeak/ligand network.
   Test an empty-network control before adding channel transport. Trusted
   upstream configuration expressions are not a Cells expression/plugin API.

Sources: [native network initialization and channel transport](../upstream/betse-v1.5.0/betse/science/chemistry/networks.py),
[full simulator loop and voltage update](../upstream/betse-v1.5.0/betse/science/sim.py),
[concentration updater](../upstream/betse-v1.5.0/betse/science/sim_toolbox.py),
[current assembly](../upstream/betse-v1.5.0/betse/science/physics/ion_current.py),
[native example configuration](../upstream/betse-v1.5.0/betse/data/yaml/sim_config.yaml).
These are source-derived findings, not claims that the new native configuration
has executed successfully. Pin these bytes in the next preflight registration.

## Common physical regime and mapping

Keep the existing explicit **seven-cell / 30-face native fixture**, one shared
finite well-mixed outside, fixed geometry and zero cell polarizability. The
literal one-cell native geometry remains rejected. This fixture does not make
seven cells an architectural constant: Cells still supports one cell and data-
defined larger worlds. Start with a single channel type uniformly targeted to
all native faces; selective tissue targets are a later comparison.

| Quantity | Proposed correspondence / required check |
| --- | --- |
| Temperature | 298.15 K in all native and Cells physical fields; no adopted Q10 law |
| Constants | Explicit matched F/R profile; native-default constants are a separate question |
| Channel | Native K/Kv1p5; Cells `betse_kv1p5_mh@1`, K-bound, separate m and h |
| Permeability | With `rho_channel=1`, rel_perm=1 and constant modulation, `maxDm = membrane_thickness * P_max * abundance`; verify actual arrays and units |
| Geometry | Sum native face areas by owner; preserve every cell volume and one capacitor per cell |
| Bath | Explicit Cells volume; test the native face-normalization mapping, uniformity and conservation |
| Signed flux | Native inward `f_ED` in mol/(m² s); Cells channel transfer in fmol/s after area and 1e15 conversion |
| Current | Cells inward `F*z*transfer_mol_per_s`; native outward extra current has the opposite sign and must be area-integrated |
| Gate state | Native equilibrium export first; separately declared non-equilibrium m/h fixtures may follow, never inferred from P alone |

Na/K/Cl background leak may remain from the qualified passive setup, but pumps,
gap-junction transport, ER/Ca dynamics, noise, extracellular fields, water,
mechanics and unrelated network chemistry stay disabled. Auxiliary fixed charge
and native initial charge residuals must remain explicit. There is no physiological
resting-state claim and no post hoc voltage offset or silent neutralization.
Do not import the existing example's nonzero synthetic pump into this comparison.

## Small next implementation: preparation and single-update preflight

Register this separately before native numerical work:

1. Prepare four controlled variants at 298.15 K: network off; minimal network
   with no channels; one Kv1p5 with zero maximum permeability; and one Kv1p5 with
   a declared nonzero maximum permeability. Keep all other inputs fixed. Verify
   the new native objects, target indices, core state, native modulation and
   any preparation-dependent charge/chemistry changes. Zero maximum permeability
   should still exercise gate updates; disabling a mechanism is a different control.
2. Export geometry, amounts, fixed charge, temperatures, actual voltage, m/h,
   effective diffusion and array ownership. Resolve counterpart definitions
   through the unchanged Cells parser. Reject unmatched semantics before a
   trajectory; do not patch either solver or substitute fake native tissue objects.
3. On fresh prepared states, test gate/transport composition and one native
   update using the actual channel runner. Record pre-update voltage/gates,
   post-gate/pre-transfer P and effective permeability, channel-specific flux,
   intracellular/outside changes, derived current and post-transfer charge/voltage.
   Compare Cells instantaneous flux at the *same declared gate state*, not its
   old gates against native's already-updated gates. Keep own-method state
   propagation checks separate from same-state constitutive comparisons.
4. Require exact blocking, explicit opening-state history, conservation of each
   mobile species, outside countercharge, and one channel-transfer contribution.
   Validate source-array mapping and current signs with independent arithmetic.
   Define tolerances, all cases, memory reservations and wall/artifact caps before
   the numerical capture; no exploratory tolerance adjustment after results.

This preflight may involve native initialization and prescribed single updates;
it does not authorize a full coupled time loop. A pass still needs its own saved-
data review. If enabling the network changes the preparation, preserve that
result and determine the reason before moving to dynamics.

## Later dynamic comparison and multiscale design

Only after preflight, register a short full-loop pilot with zero-permeability and
active counterparts, measurable voltage/channel feedback and separate native/
Cells timestep refinement. Choose a millisecond-scale opening experiment first;
select the exact horizon and resource budget from measured preflight costs and
model validity, not by reusing the passive 1 ms horizon or isolated 4 s recovery.
Slow coupled recovery, suppression/release and more channels follow separately.

Record both primary gates and channel-transfer ledgers alongside voltage,
cell/bath inventories and instantaneous rates. Reconcile fresh rates versus
interval-integrated transfers. Fixed-input solver error and interface/input
sampling remain different numerical questions; the earlier 4173 passive
diagnostic failures remain preserved and do not become convergence evidence.

For future multiscale/GPU execution, channel kinetics remain local numeric work;
membrane-owner gathers and cell/bath scatters retain explicit axes. Connected
worlds need stage-consistent shared-bath reductions. Any gate subcycling or
coarse-graining must preserve or quantify error in the slow h history. No GPU
optimization, channel catalog, multi-organ implementation or generic framework
is required for this next small preflight.
