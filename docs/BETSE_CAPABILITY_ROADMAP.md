# BETSE calibration of the Cells bioelectric layer

Coverage reviewed against the checkout and recorded results on **2026-10-11**;
the named-channel implementation entry was refreshed on **2026-10-22** and the
membrane-redistribution and assembly integration entry on **2026-10-26**.
The channel catalog, water/volume, finite-energy and cotransport entries were
refreshed on **2026-10-28**; extracellular barriers, scheduled water/repair
profiles, ideal-reservoir bath integration and physiological perturbation
components were refreshed on **2026-10-29**. Configured irreversible/finite-ATP
transport and physiological owner/unit binding entries were refreshed on
**2026-10-30**.
This is a capability inventory, not a live run log. [Progress](../PROGRESS.md)
contains the current qualifications and their evidence; the [Roadmap](ROADMAP.md)
defines priorities. The [September planning snapshot](history/BETSE_CAPABILITY_ROADMAP_BEFORE_2026-10-11.md)
retains the earlier inventory, implementation sequence and failed comparisons.

## What the target means

Cells uses BETSE as a reference to calibrate and verify the bioelectric layer
of its broader cell and tissue simulations. This layer connects to chemistry,
protein assembly and other processes within Cells' multiscale CPU/GPU framework.
Reference comparisons, experimental validation and distributed execution each
require their own evidence; reduced models remain selectable.

The reproducible comparison baseline is BETSE **v1.5.0**, commit
`5269a714aa2593ed2a6708c4516289977d8ae1a2`. It is not a moving latest release.
The B01-B17 inventory groups capabilities; every subtype, supported option and
coupled regime still needs explicit coverage. Cells source-compatible components
may retain native update ordering and clock conventions; those choices must not
silently become universal physical laws or replace accepted physical-time models.

Calibration focuses on the selected physical mechanisms, equations and responses.
GUI, plot style, YAML import and legacy serialized-state compatibility are
separate concerns. Experimental agreement requires its own evaluation.

## Primary-source baseline

- [B1: pinned overview](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/README.rst): ions, channels, pumps, extracellular space, networks and workflows.
- [B2: pinned simulation configuration](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/data/yaml/sim_config.yaml): tissue profiles, interventions, noise, mechanics and full/circuit settings.
- [B3: network template](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/data/yaml/extra_configs/extra_config_template.yaml): configurable chemistry, transport, modulation and optimization.
- [B4: flow module](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/physics/flow.py): electroosmotic/Stokes-style flow and divergence-free projection, not a general turbulent-flow model.
- [B5: membrane redistribution](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/physics/move_channels.py): spatial channel/pump weighting dynamics.
- [B6: ER module](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/organelles/endo_retic.py): internal membrane, calcium and pump/channel state.
- [B7: source tree](https://github.com/betsee/betse/tree/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science): channel families, mitochondria and microtubule modules; presence alone does not establish runtime coverage or biological validity.

The original inventory is a read-only source/configuration review, not an
equation-by-equation audit. The later [REF-003a result](../reports/REF003A_PASSIVE_CONTACT.md)
installs pinned BETSE separately and executes only its passive-flux component;
it does not establish other inventory rows. The [earlier review](BETSE_DESIGN_REVIEW.md)
retains the experimental-evidence distinctions. Upstream source is not vendored
into Cells. Any later code/data reuse needs its own attribution and dependency
license review; BETSE and the separate BITSEY source have different provenance.

## Capability inventory and engineering route

**Partial** means that a named subset is implemented or compared. It does not
mean every BETSE mechanism in that row is covered. **Planned** means that the
physical capability is not yet implemented. Linked guides define model versions
and numerical limits; Progress links to the actual passing or failed evidence.

| ID | Scientific capability / source | Implemented scope | Remaining coverage |
| --- | --- | --- | --- |
| B01 | Ions, valence and background charge / B1-B2 | Partial: multispecies cell, finite-exterior, spatial and calcium families with explicit ownership | Broader species/route combinations and parameter regimes require their own checks |
| B02 | Passive membrane electrochemistry / B1-B2 | Partial: physical GHK transport and selected native single-cell/cluster/spatial comparisons; [spatial guide](TISSUE_RETURN_CURRENT.md) | Broader geometries, boundaries and convergence; no arbitrary-regime equivalence |
| B03 | Voltage/ligand-gated channels / B1, B7 | Partial: named [Kv1.5/Kir2.1/NaV1.2 implementations](TISSUE_RETURN_CURRENT.md#sodium-and-potassium-channels-in-resolved-tissue), [HCN1/2/4 with shared multi-ion gates](TISSUE_RETURN_CURRENT.md#shared-hcn-gates-and-multi-ion-transport), selected [CaV1.2/IP3 routes](PLASMA_CALCIUM.md), [HCN/calcium/assembly composition](TISSUE_RETURN_CURRENT.md#shared-hcn-populations-with-owned-calcium-and-assembly), the [complete pinned Kv1 catalog implementation](TISSUE_RETURN_CURRENT.md#complete-kv1-catalog-with-shared-populations-and-owned-calcium), [seven shared CaV population laws](TISSUE_RETURN_CURRENT.md#shared-calcium-channel-populations) and an [expanded catalog of 35 laws](TISSUE_RETURN_CURRENT.md#expanded-sodium-potassium-and-leak-catalog) with [owned calcium/ER and assembly control](TISSUE_RETURN_CURRENT.md#expanded-catalog-with-owned-calcium-and-assembly) and [shared finite fuel](TISSUE_RETURN_CURRENT.md#shared-finite-energy-with-owned-calcium-and-assembly); [four further calcium laws extend the shared compositions to 39 laws](TISSUE_RETURN_CURRENT.md#extended-39-law-channel-catalog) plus [legacy calcium-sensitive potassium](TISSUE_RETURN_CURRENT.md#calcium-sensitive-potassium-with-the-shared-catalog) and [thirteen Morris–Lecar laws](TISSUE_RETURN_CURRENT.md#morris-lecar-channels-with-the-shared-catalog), giving 53 shared laws with explicit two-, one- and zero-state contracts; [three further HCN variants](TISSUE_RETURN_CURRENT.md#hcn-leak-and-fixed-camp-variants) extend new ionic/calcium/finite-fuel identities to 56 laws; model-specific qualification results and pending checks are tracked in Progress | Compiled/GPU qualification of the 56-law water/repair compositions; other channel/ligand families, longer joint water/calcium/fuel/repair recovery, broader mobile catalogs, longer coupled trajectories and experimental calibration |
| B04 | Pumps, exchangers and cotransport / B1, B3 | Partial: Na/K pumps including scheduled spatial comparisons and a [mobile ATPase/calcium/injury composition](TISSUE_RETURN_CURRENT.md#mobile-pumps-with-owned-calcium-and-prescribed-repair); [finite cellular ATP/ADP/phosphate with shared Na/K demand](FINITE_ENERGY_POOLS.md#resolved-active-tissue-with-finite-cellular-pools), with qualification tracked in Progress; [manufactured KCC/NKCC cotransport](TISSUE_COTRANSPORT.md) and [salt/water/finite-energy composition](TISSUE_RETURN_CURRENT.md#cotransport-with-finite-energy-and-water), with scoped CPU checks; [PMCA and synthetic NCX](PLASMA_CALCIUM.md); [ER calcium pump](ER_CALCIUM.md); [finite-pool PMCA/ER adapter](FINITE_CALCIUM_PUMPS.md) with explicit standard-state conversion, [composed with shared Na/K fuel and owned calcium/ER](TISSUE_RETURN_CURRENT.md#shared-finite-energy-with-owned-calcium-and-assembly); [configured reversible, species-preserving transport with actual calcium and finite fuel owners](TISSUE_RETURN_CURRENT.md#configured-transport-with-owned-calcium-and-finite-fuel); a separate [irreversible configuration with explicit physical work/heat](TISSUE_RETURN_CURRENT.md#irreversible-configured-transport-with-explicit-physical-work); [configurable one-ATP transport with live finite-pool ownership](TISSUE_RETURN_CURRENT.md#configured-transport-powered-by-finite-atp), with qualification tracked in Progress | Broader species-converting transport and fuel stoichiometries, broader coupled native/GPU qualification, physiological relaxation and other pump families; synthetic NCX is not native BETSE correspondence |
| B05 | Selective, voltage-sensitive gap junctions / B1-B2 | Partial: physical-time junction models and selected native gate and combined spatial pump/channel/junction trajectories | Broader coupled native regimes, connexin diversity and fitted recovery/heterogeneity |
| B06 | ER/calcium and mitochondrial compartments / B1, B6-B7 | Partial: finite [ER/cytosol](ER_CALCIUM.md), calcium buffers, plasma transport and IP3 composition; [finite mitochondrial ion/voltage coupling](TISSUE_RETURN_CURRENT.md#finite-mitochondrial-ion-and-voltage-coupling) with explicit cytosolic ownership, capacitor energy and heat, distinct from the literal native Euler component | Longer coupled recovery and GPU qualification; respiration, ATP synthesis, dynamic organelle volume and measured calibration remain outside the passive law; [broader mitochondrial plans](PAPER_REVIEW_MITOCHONDRIA.md) |
| B07 | Chemistry, regulation and bioelectric feedback / B1, B3 | Partial: EMT, [compartment reactions](COMPARTMENT_REACTIONS.md), calcium/IP3 and one-way [assembly regulation](CAPSID_ASSEMBLY.md); [native local reactions and growth/decay component](../agent-work/cells-worker-01/workfiles/BETSE_NETWORK_REACTIONS_HANDOFF.md) with explicit material/source/sink accounting; [native network modulation component](../agent-work/cells-worker-01/workfiles/BETSE_NETWORK_MODULATION_HANDOFF.md) with ordered signed control writes; [live pump/channel/junction regulation](TISSUE_RETURN_CURRENT.md#live-network-regulation-of-pumps-channels-and-junctions) with explicit free-ion/fuel ownership and bounded physical factors, wired into shared dispatch with public execution qualification tracked in [Progress](../PROGRESS.md) | Shared reaction, chemical and fuel ownership; broader modulation consumers and native ordering; broader regulatory networks, calibrated feedback and bidirectional assembly/energy coupling |
| B08 | Extracellular electrodiffusion and barriers / B1-B2 | Partial: finite and spatial exterior, cross-region return currents and selected native spatial fields; separate [native environment/barrier component and conservative face law](../agent-work/cells-worker-01/workfiles/BETSE_ENVIRONMENT_TRANSPORT_HANDOFF.md), with source stencil/bath defects retained and convergence checked separately; [static native barrier coefficients prepare passive and five explicit full-catalog ionic/calcium/fuel/water/repair owners](TISSUE_GEOMETRY.md#apply-static-extracellular-barriers), retaining Cells logmean transport and each parent's complete field/energy accounting; [one scheduled native ECM-opening pulse](TISSUE_GEOMETRY.md#schedule-extracellular-barrier-opening) updates passive faces and five explicit complete ionic/calcium/fuel/water/repair owners at every stage with preserved history; [combined membrane-profile and ECM schedules on complete ionic, calcium and finite-fuel owners](TISSUE_GEOMETRY.md#combining-membrane-and-extracellular-events) preserve both histories and one stage clock; independent stages, full trajectories and execution qualification remain separately tracked in [Progress](../PROGRESS.md) | Coupled field/energy/tissue integration of the separate Bernoulli face law, full evolved coupled-barrier qualification, broader scheduled profile/owner combinations, bath composition with water and moving topology, broader boundary physics and transepithelial comparisons |
| B09 | Resolved membrane polarization and fields / B1-B2 | Partial: [resolved membrane surfaces and tissue fields](TISSUE_RETURN_CURRENT.md), with scoped CPU/L4 qualification; separate [native geometry/operator binding](../agent-work/cells-worker-01/workfiles/BETSE_GEOMETRY_HANDOFF.md) with explicit source inverse/nullspace limitations and distinct compatible gauge solves | Coupling general meshes to physical tissue state, larger sparse/device solves, additional boundary conditions and native coupled coverage |
| B10 | Channel/pump redistribution and polarity / B5, B7 | Partial: [conservative lateral membrane transport](TISSUE_RETURN_CURRENT.md#lateral-membrane-redistribution), CPU/L4-checked neutral always-open and [Na/K ATPase populations](TISSUE_RETURN_CURRENT.md#mobile-nak-atpase-populations), [joint Kv1.5 gating-state transport](TISSUE_RETURN_CURRENT.md#mobile-channels-carrying-joint-gating-states), and the [mobile Kv1.5/calcium/injury composition](TISSUE_RETURN_CURRENT.md#mobile-kv15-with-owned-calcium-and-prescribed-repair), with [one-way assembly integration](TISSUE_RETURN_CURRENT.md#assembly-with-mobile-channels-and-prescribed-repair) implemented; qualification evidence and pending checks in [Progress](../PROGRESS.md) | Broader mobile channel families, protein exchange with assembly pools and charged-cargo field-work accounting. The pinned native redistribution update fails on a missing helper; native trajectory correspondence remains unresolved |
| B11 | Osmotic pressure, water and flow / B2, B4 | Partial: [conservative water and compliant volumes](TISSUE_RETURN_CURRENT.md#osmotic-water-and-compliant-volumes) with shared passive ions, explicit osmolytes and pressure/energy accounting; [active pump/channel composition](TISSUE_RETURN_CURRENT.md#active-transport-with-compliant-volumes), the [53-law channel/water composition](TISSUE_RETURN_CURRENT.md#shared-channel-catalog-with-compliant-water), [finite pool osmolytes](TISSUE_RETURN_CURRENT.md#finite-cellular-energy-with-compliant-volumes), [53-law finite fuel/water](TISSUE_RETURN_CURRENT.md#shared-channel-catalog-with-finite-fuel-and-water), [owned calcium/ER with compliant cytosol](TISSUE_RETURN_CURRENT.md#owned-calcium-and-er-with-compliant-cytosol), [joint calcium/ER/fuel/water](TISSUE_RETURN_CURRENT.md#owned-calcium-finite-fuel-and-compliant-water), its [prescribed-repair composition](TISSUE_RETURN_CURRENT.md#prescribed-repair-with-owned-calcium-finite-fuel-and-water) and [cotransport coupling](TISSUE_RETURN_CURRENT.md#cotransport-with-finite-energy-and-water) implemented, with all qualification status in [Progress](../PROGRESS.md). [Pinned BETSE pressure/flow snapshots](WATER_VOLUME_REFERENCE.md#what-pinned-betse-actually-executes) have separate correspondence; its volume-update block is inactive; separate [native fluid-flow component](../agent-work/cells-worker-01/workfiles/BETSE_FLUID_FLOW_HANDOFF.md) retains disabled loader settings, boundary failures and dimensional limitations | Physical flow integration and longer coupled recovery/GPU qualification and stochastic assembly histories; organelle water exchange, evolving geometry, fluid fields, solvent drag and broader regimes. No native evolving-volume trajectory claim |
| B12 | Deformation and electromechanics / B2, B7 | Partial: [standalone native steady deformation, pressure auxiliary and display mapping](../agent-work/cells-worker-01/workfiles/BETSE_DEFORMATION_HANDOFF.md); source-disabled dynamic recurrence remains an isolated diagnostic, with dimensional and boundary limitations preserved | Physical mechanics, geometry/capacitance/contact updates, force/energy balance, convergence and tissue coupling |
| B13 | Tissue geometry, regional profiles and interventions / B2 | Partial: spatial tissues, region/surface ownership and scheduled transport controls; fixed-geometry injury/resealing, including the [53-law owned-calcium repair composition](TISSUE_RETURN_CURRENT.md#shared-channel-catalog-with-prescribed-repair) and [joint calcium/ATP/water repair](TISSUE_RETURN_CURRENT.md#prescribed-repair-with-owned-calcium-finite-fuel-and-water); [native cut captures and conservative remap component](../agent-work/cells-worker-01/workfiles/BETSE_TISSUE_CUT_HANDOFF.md), connected to [passive continuation](TISSUE_RETURN_CURRENT.md#cell-removal-and-absolute-time-continuation), [active channel/pump continuation](TISSUE_RETURN_CURRENT.md#cell-removal-with-channels-and-maintained-fuel-pumps), [owned calcium/ER continuation](TISSUE_RETURN_CURRENT.md#cell-removal-with-owned-calcium-and-er-stores), [finite-fuel continuation](TISSUE_RETURN_CURRENT.md#cell-removal-with-finite-atp-and-regeneration), [configured-transporter continuation](TISSUE_RETURN_CURRENT.md#cell-removal-with-configured-membrane-transport), separate [irreversible-transport](TISSUE_RETURN_CURRENT.md#cell-removal-with-irreversible-transport) and [finite-ATP transport](TISSUE_RETURN_CURRENT.md#cell-removal-with-finite-atp-transport) removal adapters with qualification tracked in Progress, [mitochondrial-owner continuation](TISSUE_RETURN_CURRENT.md#cell-removal-with-mitochondrial-owners), [compliant-water continuation](TISSUE_RETURN_CURRENT.md#cell-removal-with-compliant-water-and-finite-fuel) and [regulated finite-fuel continuation](TISSUE_RETURN_CURRENT.md#cell-removal-with-live-network-regulation); separate [native geometry binding](../agent-work/cells-worker-01/workfiles/BETSE_GEOMETRY_HANDOFF.md) and [regional profiles](../agent-work/cells-worker-01/workfiles/BETSE_TISSUE_PROFILES_HANDOFF.md), now connected to [static resolved-tissue preparation](../agent-work/cells-worker-01/workfiles/TISSUE_PROFILE_PREPARATION_HANDOFF.md) with explicit thickness/owner/unit provenance; [scheduled passive membrane profiles](TISSUE_RETURN_CURRENT.md#scheduled-passive-membrane-profiles) and [active channel/pump profiles](TISSUE_RETURN_CURRENT.md#scheduled-active-membrane-profiles) add native membrane-pulse laws with saved RK-stage phase clocks and complete history; [calcium/finite-fuel profile models](TISSUE_RETURN_CURRENT.md#scheduled-membrane-profiles-with-calcium-stores-and-finite-fuel) retain complete chemical and ATP owners; [water/repair profile models](TISSUE_RETURN_CURRENT.md#scheduled-membrane-profiles-with-water-and-prescribed-repair) preserve moving volumes and damage history, with qualification tracked separately. The [explicit INIT-to-SIM workflows for complete physical owners](TISSUE_PHASES.md) preserves physical state, gates and accounting history across phase clocks. Qualification is tracked in [Progress](../PROGRESS.md) | Broader qualification of mitochondrial/water/regulated cuts; assembly and combined owner families, physical wound contacts, cutting work, broader injury regimes, evolved geometry, broader intervention regimes and coupled water/repair qualification, full water/repair phase trajectory qualification and native solver-loop correspondence beyond the declared panels; [integration plan](ROADMAP.md#injury-and-repair) |
| B14 | Heterogeneity and stochastic perturbations / B2 | Partial: heterogeneous parameters and stochastic assembly with stable world IDs/random streams; separate [native physiological perturbation component](../agent-work/cells-worker-01/workfiles/BETSE_PERTURBATIONS_HANDOFF.md) with exact native RNG replay, distinct stable owner/world streams and distribution checks; [shared stream ownership, checked static/protein updates and complete material-state checkpoints](PHYSIOLOGY_RANDOM_STREAMS.md), with explicit source guards/timing and retained rejected trials; [ordinary-tissue owner/unit binding](PHYSIOLOGY_RANDOM_STREAMS.md#explicit-tissue-owners-and-units) preserves actual representable geometry, explicit thickness, complete provenance and bound checkpoint replay; an [explicit passive-permeability view](PHYSIOLOGY_RANDOM_STREAMS.md#applying-permeability-to-a-complete-tissue-readout) evaluates the complete four ordinary families with actual-control/domain/step admission, without advancing either clock; [explicit original-grid tissue stepping and bound restart](PHYSIOLOGY_RANDOM_STREAMS.md#advancing-a-bound-tissue-checkpoint) hold the component fixed through an accepted numeric interval; an [atomic physiological-loop bridge and restart](PHYSIOLOGY_RANDOM_STREAMS.md#advancing-a-complete-physiological-loop) preserve one component call across finer original tissue/control steps; [separate pre-ion/post-ion component proposals](PHYSIOLOGY_RANDOM_STREAMS.md#separate-pre-ion-and-post-ion-component-phases) expose the ordering for future charged composition; [explicit protein amount/charge projection and same-state field response](PHYSIOLOGY_RANDOM_STREAMS.md#protein-amounts-and-electrostatic-response) preserve original anchors and inventory ownership; [conditional ideal-protein endpoint work](PHYSIOLOGY_RANDOM_STREAMS.md#conditional-protein-endpoint-work) separates chemical, capacitor and clamp terms under fixed-ion constraints; [complete held-protein RHS](PHYSIOLOGY_RANDOM_STREAMS.md#complete-rates-with-held-protein-charge) routes charge through existing channels, pumps, calcium/ER and live fuel without changing saved anchors, with qualification tracked in Progress; [accepted held-protein intervals and complete restart](PHYSIOLOGY_RANDOM_STREAMS.md#accepted-intervals-with-held-protein-charge) retain the ordinary seed and check local/cumulative material and energy balances without advancing protein/RNG; [array interval accounting](PHYSIOLOGY_RANDOM_STREAMS.md#array-accounting-for-batched-execution) separates associated charged endpoints from batched numerical balances, with qualification scope in Progress; [post-ion protein proposals and declared-drive receipts](PHYSIOLOGY_RANDOM_STREAMS.md#post-ion-protein-updates-with-a-declared-energy-budget) preserve source update guards, actual endpoint fields and explicit work/dissipation with exact replay; a [repeated charged-loop owner and restart](PHYSIOLOGY_RANDOM_STREAMS.md#repeated-charged-loops-and-restart) preserve the original conditioned state and cumulative driving/electrode/dissipation ledgers, with qualification tracked in Progress; [scheduled permeability in charged loops](PHYSIOLOGY_RANDOM_STREAMS.md#scheduled-permeability-in-charged-loops) adds recorded modifiers and source-style targeted pulses with explicit clock/owner association and restart, with coupled qualification tracked in Progress; [component cell-removal remap](PHYSIOLOGY_RANDOM_STREAMS.md#cell-removal-and-surviving-owners) retains survivor buffers and removed-protein accounting under unchanged geometry | Qualify broader native coupled-loop correspondence and compose component removal with charged histories; calibrate a physical driving/heat law and field/geometry transitions; broader event/modulator coverage and native-loop correspondence; [geometry-bound x/y/r spatial factors](PHYSIOLOGY_RANDOM_STREAMS.md#spatial-intervention-gradients) preserve source selection and numerical failures, with full-owner schedule binding and coupled qualification tracked in Progress; [periodic/sweep time-factor components and schedule binding](PHYSIOLOGY_RANDOM_STREAMS.md#periodic-and-frequency-sweep-time-factors) preserve original coefficients and event clocks, with coupled qualification tracked in Progress; [native event-calendar integration](PHYSIOLOGY_RANDOM_STREAMS.md#native-phase-labels-and-elapsed-call-boundaries) preserves distinct event labels and elapsed updates, with coupled qualification tracked in Progress; stochastic tissue trajectories, partitioned/GPU qualification and other perturbation families. Source noise timing and timestep scaling remain explicit |
| B15 | Preparation and detailed/reduced modes / B1-B2 | Partial: explicit preparations, versioned fidelity choices and bounded recording | Validated fine/coarse reduction, adaptive resolution and coupled multirate execution |
| B16 | Parameters, calibration and model comparison / B3 | Partial: preserved descriptive endpoint pilot and [candidate data plan](BETSE_BIOLOGICAL_BENCHMARK_PLAN.md) | Suitable measurements, parameter provenance, uncertainty and independent biological evaluation |
| B17 | Headless workflows, observations and visualization / B1-B2 | Partial: CLI/configurations, manifests, arrays, checkpoints, windows, ensembles and GPU telemetry | A general scientific viewer, further interoperable exports and qualified remote execution |

For B08, [static ideal reservoirs](TISSUE_RETURN_CURRENT.md#static-ideal-reservoirs-with-calcium-and-finite-fuel)
now have explicit calcium/ER and finite-fuel owners, with full manufactured
trajectory evidence linked from Progress. [Scheduled bath composition](TISSUE_RETURN_CURRENT.md#scheduled-baths-with-calcium-and-finite-fuel)
is also implemented for those owners and is undergoing CPU qualification.
It retains the ordered native K/Cl/Na setters, actual counter-ion inventories,
variable reservoir chemical work and fixed-voltage compensation. Source setter
correspondence, independent physical trajectories and native solver-loop parity
remain distinct claims.

A feature combination requires its own comparison: qualifying ER, a field solver
and a pump independently does not establish their integrated trajectory. Native
law checks, native clock-matched trajectories and independently integrated
physical models retain their separate meanings. Existing numerical tolerances
and failed evidence remain part of the record.

The [global temperature/block/voltage setter components](PHYSIOLOGY_RANDOM_STREAMS.md#global-control-setters)
retain source baselines, ordered writes and invalid-input diagnostics. Their
[ordinary-tissue blocker view](PHYSIOLOGY_RANDOM_STREAMS.md#applying-blockers-to-ordinary-tissue-rates)
maps explicit symmetric contact pairs and actual Na/K pump owners to complete
physical rates while retaining all other controls. The separate
[accepted interval/restart path](PHYSIOLOGY_RANDOM_STREAMS.md#accepted-intervals-with-held-blockers)
holds each sampled blocker through an original physical interval; its coupled
qualification is tracked in Progress. The
[native-calendar controller](PHYSIOLOGY_RANDOM_STREAMS.md#native-calendar-blocker-calls)
also associates complete original phase labels with physical subintervals,
INIT/SIM dispatch, atomic calls and durable restart. It holds the component/RNG;
it does not compose their post-ion transitions. A separate
[array mapping](PHYSIOLOGY_RANDOM_STREAMS.md#blocker-controls-in-arrays)
supports shared or per-world owner maps with compiled CPU checks; accepted GPU
execution remains separate. The
[target-selection owner](PHYSIOLOGY_RANDOM_STREAMS.md#native-tissue-target-selection)
retains separate NumPy/Python tapes and the native selection order, including
the discarded GJ shuffle. Its
[initial physical preparation bridge](PHYSIOLOGY_RANDOM_STREAMS.md#preparing-physical-tissue-profiles)
produces reproducible complete definitions using the static coefficient laws;
qualification is tracked in Progress. Coupling those setup tapes into a shared physical
checkpoint, broader component ordering, and the thermal/electrode work required
for changing temperature or voltage remain open.

The [held boundary-voltage view](PHYSIOLOGY_RANDOM_STREAMS.md#applying-boundary-voltage-to-complete-tissue-rates)
maps native side controls onto actual reservoir owners in passive/ionic and the
explicit open-calcium/open-fuel models. It preserves finite-family reservoir
refusals and reports conditional capacitor-work diagnostics separately from any
accepted voltage transition or cumulative work ledger.

The [real protein packet provider](PHYSIOLOGY_RANDOM_STREAMS.md#real-protein-packets-for-array-transitions)
connects the qualified owned samplers to the deterministic transition arrays.
Native MT19937 remains host-side; stable owner-keyed sampling supports compiled
array preparation. Complete source/successor association, failed draws and
conditional work admission remain separate from committed physical loops and
GPU qualification. Progress records the actual comparison scope.

## Concrete source gaps identified on 28 October

A scoped source check identified three HCN variants beyond the 53-law catalog:
`HCNLeak`, `HCN2_cAMP` and `HCN4_cAMP`
([native source](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/channels/vg_funny.py#L291)).
HCNLeak uses Na/K/Ca permeability ratios 0.33/1/0.05. The cAMP variants use
0.2/1/0.05 and fixed voltage-threshold shifts; they do not model evolving cAMP.
HCN4_cAMP subtracts 20 mV during initialization and 24 mV during updates, so
those two contracts need separate comparisons. The
[56-law implementation](TISSUE_RETURN_CURRENT.md#hcn-leak-and-fixed-camp-variants)
adds them in new ionic/calcium/finite-fuel identities; source and execution
evidence is tracked in [Progress](../PROGRESS.md). This scoped addition is not
an exhaustive remaining-channel audit or complete native tissue equivalence.

The scoped work also covers configurable transporter saturation and ligand
regulation in the [network engine](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/chemistry/networks.py),
actual [cell cutting and contact/field rebuilding](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/tissue/tishandler.py#L921),
and the optional [mitochondrial ion/voltage compartment](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/organelles/mitochondria.py#L60).
The [reversible configured-transport composition](TISSUE_RETURN_CURRENT.md#configured-transport-with-owned-calcium-and-finite-fuel)
and [continuous mitochondrial composition](TISSUE_RETURN_CURRENT.md#finite-mitochondrial-ion-and-voltage-coupling)
declare their physical subsets separately from native implementation quirks.
The [cut/remap component](../agent-work/cells-worker-01/workfiles/BETSE_TISSUE_CUT_HANDOFF.md)
provides explicit removal accounting. [Passive solver continuation](TISSUE_RETURN_CURRENT.md#cell-removal-and-absolute-time-continuation)
preserves physical survivors and the original clock; the
[active channel/pump adapter](TISSUE_RETURN_CURRENT.md#cell-removal-with-channels-and-maintained-fuel-pumps)
also retains intrinsic gates and all source histories. The
[calcium/ER adapter](TISSUE_RETURN_CURRENT.md#cell-removal-with-owned-calcium-and-er-stores)
preserves owned chemistry, while the
[finite-fuel adapter](TISSUE_RETURN_CURRENT.md#cell-removal-with-finite-atp-and-regeneration)
adds ATP/ADP/Pi pools and regeneration owners. The
[configured-transport adapter](TISSUE_RETURN_CURRENT.md#cell-removal-with-configured-membrane-transport)
also remaps route owners and archives their work/transfer histories. The
[mitochondrial adapter](TISSUE_RETURN_CURRENT.md#cell-removal-with-mitochondrial-owners)
retains disjoint organelle inventories and paired internal charge, with qualification
tracked in Progress. The [water adapter](TISSUE_RETURN_CURRENT.md#cell-removal-with-compliant-water-and-finite-fuel)
rebases actual volumes while retaining the compliance reference and pressure law.
The [regulated adapter](TISSUE_RETURN_CURRENT.md#cell-removal-with-live-network-regulation)
also retains live rule ownership and complete source history; assembly cut
composition remains separate. The
[tissue-profile/intervention component](../agent-work/cells-worker-01/workfiles/BETSE_TISSUE_PROFILES_HANDOFF.md)
preserves native target order, overlapping selections and ownership semantics.
The [selection-stream wrapper](PHYSIOLOGY_RANDOM_STREAMS.md#native-tissue-target-selection)
adds complete native RNG records and carried ordering across repeated preparation;
shared solver/checkpoint and post-cut reselection integration remain separate.
The [native geometry component](../agent-work/cells-worker-01/workfiles/BETSE_GEOMETRY_HANDOFF.md)
supplies explicit seed/contact/measure/operator bindings with source defects
retained; physical state remapping and coupled simulation remain separate. The
[reaction/growth component](../agent-work/cells-worker-01/workfiles/BETSE_NETWORK_REACTIONS_HANDOFF.md)
also needs chemical, fuel and source/sink owners before physical tissue coupling.
Qualification status is recorded in [Progress](../PROGRESS.md). Broader native
tissue histories still need aligned field and boundary semantics beyond these
component panels and independently integrated physical subsets.

The [wound-source audit](../agent-work/cells-worker-01/workfiles/WOUND_SOURCE_LIMITS.md)
and [water-source limits](WATER_VOLUME_REFERENCE.md#what-pinned-betse-actually-executes)
record broken calls, commented-out updates and loader-disabled paths separately.
Implementing independent Cells repair, volume or mechanics laws does not by
itself resolve those source limitations or establish native equivalence.
The [pre-Jupiter compatibility milestone](ROADMAP.md#betse-compatibility-before-jupiter)
requires this distinction to remain explicit.

## Staged build order

The [Roadmap](ROADMAP.md#current-development-priorities) owns the build priorities.
New mechanisms proceed through declared equations/ownership, independent
references, implementation and integrated CPU/L4 checks. Jupiter qualification
and a distributed interacting tissue require additional execution evidence.
Completed prerequisites are recorded in Progress rather than repeated as tasks
in every design document.

## Coverage and success criteria

For each concrete mechanism record separately: specified, independently checked,
CPU implemented, source compared, experimentally evaluated, GPU qualified, and
multiscale qualified. Store the reference version, units, regime and known
omissions with each result. "Implemented" never implies all other columns pass.

Source parity uses aligned equations, boundaries and parameters with independent
numerical tolerances. Biological plausibility uses separate measured data and
outcomes. Reduction preserves the response and history relevant to its declared
task, not merely a matching final mean voltage. Parallel implementations retain
those requirements; floating reduction order means cross-device bitwise identity
must not be promised generally.

To claim progress beyond the baseline, report accuracy at a declared fidelity
alongside end-to-end runtime, memory, communication and output costs. Larger cell
counts or a GPU kernel alone do not establish an organ-scale advance.

## Immediate next slice

See [Progress](../PROGRESS.md#current-position) for the active comparison and its
next integration step. The [calibration approach](BETSE_REALISM_AND_NEXT_STEPS.md)
sets the acceptance distinctions; it is not a second current-status tracker.

## Reviewed byte identities

Hashes identify the inspected source files at the pinned commit; they do not
replace later executable source captures or reproduce upstream code here.

| Source | SHA-256 |
| --- | --- |
| B1 | `9c9c95d913fbbbf8e0db4afe6f38299dbf55bd8c164bade13b34a64b20fddb87` |
| B2 | `7ed5a32f9fc256c541db63090aeed6d0207bf706d2847b27269d6bc8c9e85415` |
| B3 | `2dd1322fdab1dff7d7b9b1d90894d27e5f8357bf37b30050c2ae8c10e91492b7` |
| B4 | `37e99f7af5030127d203bc7ed674f53796149410ab15c80d2e8aca45838413ad` |
| B5 | `b857d8d125962ef50cc48a17c53044a20b09e2e0141f046521d7909d8df23ffb` |
| B6 | `14a989709bd22558f557b7177bd7728c8bf02b5711e0306a3673833812a848f8` |
