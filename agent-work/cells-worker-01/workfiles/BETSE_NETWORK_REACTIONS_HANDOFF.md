# Native configurable reaction and growth/decay integration contract

The component preserves the actual BETSE 1.5.0 generated local chemistry laws,
including three different reversible zone branches. Material conversion and
growth source/sink accounting are explicit. It is ready for Chief-owned
integration; shared models, dispatch, root documentation and PROGRESS were not
changed. Earlier scientific files/evidence remain frozen.

- Law: `betse_network_reactions_source_v1_5_0@1`.
- Process: `src/cells/processes/betse_network_reactions.py`.
  SHA `4731a672c7ebca1db101480f4ae4d0e13d6d9585282387384d8489b5bc184364`.
- Reference, fixture, native capture and protocol:
  `validation/chemistry/betse_network_reactions*`.
- Complete receipt:
  `/mnt/workspaces/Cells/betse-network-reactions-development-20261028-04/result.json`.
  SHA `84d56dacc23b4cdd5c01bda0a8a9ab633de95cc073726f4c90c771cc78e4fc07`.
- Frozen handoff metadata:
  `/mnt/workspaces/Cells/betse-network-reactions-handoff-20261028-01/result.json`.

The complete run passes **92 tests: 88 host and four CPU JAX**, with no skipped
tests. Actual native captures cover **38 valid networks and 11 limitations**.
The native, host and JAX guarded phases take **1.535 / 5.140 / 37.747 seconds**.
Peak process-tree RSS is **342,908,928 B**, minimum available host memory
**19,140,800,512 B**, on CPU7 with one BLAS thread, <=1-GiB RSS and >=8-GiB
reserve. No GPU, detached job or persistent compilation cache ran.

## Source formulas and units

For each configured reaction, `f` and `b` are products of per-item Hill
saturations `(c/Km)^nu / (1+(c/Km)^nu)`. The literal source quotient is
`Q = product(1e-3*c_product**nu) / product(1e-3*c_reactant**nu)`; the conversion
factor is outside each power, once per list item. `Keq=exp(-delta_Go/(R*T))`.

| Branch | Actual executable rate |
| --- | --- |
| Cell, reversible | `vmax * alpha * (1-Q/Keq)` |
| Mitochondria, reversible | `vmax * alpha * (f-(Q/Keq)*b)` |
| Environment, reversible | `vmax * alpha * f * (1-Q/Keq)` |
| Any zone, irreversible | `vmax * alpha * f` |

The reversible cell branch drops both saturation coefficients. The reversible
environment branch drops product saturation. LaTeX expressions do not resolve
these differences; captures execute the actual expressions. Product Km remains
validated and affects the backward diagnostic in every reaction zone, but only
affects the reversible mitochondrial executable rate.

Concentration and Km are mM (numerically mol/m3), rates mM/s, physical owner
volumes m3 and extents fmol/s: `extent = rate * volume / 1e-15`. `delta_Go` is
J/mol configured forward extent and temperature is K. The gas constant is an
explicit world parameter with **native default 8.314 J/(mol K)**. An explicit
modern SI override `8.31446261815324` is separately captured/tested; these
constant choices are distinguishable. Temperature and R have scalar or
`[...,1]` world axes.

Growth is cell-local:

`target * (modulation*production*time*alpha_growth - decay*time*c/scale - decay_max*time*alpha_decay*c/scale)`.

The nested growth/decay scale divides concentration in both decay terms. It does
not multiply production. The source time factor multiplies all three terms;
`use time dilation=False` supplies 1. Named profiles and spatial functions must
be supplied as explicit sampled target/modulation arrays. Signed finite
modulation and direct regulator terms are preserved. The source growth
optimization auxiliary is only `alpha_growth`; its decay auxiliary is only
`decay*time*c/scale`, excluding regulated decay. Both auxiliaries are unmasked
by profile targets, and both are zero for disabled growth.

## Binding, ownership and numerical API

`bind(reactions, growth, species_ids, species_valence, compartment_zones, ...)`
returns `(topology, parameters)`. `reactions` contains native reaction dictionaries.
Each `growth` row is the kinetics subset `{name, growth and decay, use time
dilation}` of a native molecule dictionary; unrelated molecule fields are not
silently accepted. `None` or string `"None"` disables growth. The raw reaction
reader, in contrast, requires literal string `"None"` for irreversible free
energy: Python `None` fails upstream and is rejected here.

Compartments explicitly declare `cell`, `mit`, `env` or `padding`. Each reaction
definition expands over all owners in its zone. Route order is growth in
supplied molecule order, then cell/mit/env reaction definitions in native
insertion order, each in owner order. Growth identity columns follow molecule
identity rather than species position. Repeated substrate entries and species
on both sides sum in the actual source matrix order. Species valences may be
any finite real declared charge weights; reaction kinetics do not infer them.

`cell_to_environment` is an explicit integer-owner mapping, not a position or
nearest-neighbor guess. Convert JSON mapping keys to integers before binding.
`growth_targets` and `growth_modulation` map molecule names to one boolean/real
value per cell owner. Named profiles/functions require these values. The binder
does not evaluate geometry, profiles or function names. `time_dilation` sets
initial source time factors; live parameter arrays can supply runtime controls.
Each configured reaction zone must have physical owners. Disabled mitochondrial
configuration must be handled explicitly by the composing model; the native
fallback is retained as limitation evidence, not silently adopted.

State axes are `[..., species, compartment]`; volume has a final compartment
axis; rates/parameters have a final expanded route axis. Topology term arrays
are `[term,route]`, and the stoichiometry is `[species,route]`, with one owner
per route. That matrix is not a replacement for owner accumulation across all
compartments. `route_capacity` allows neutral route padding. Padded compartments
must have zero state/volume and padded routes neutral data/zero rates.

`rates(c_mM, volume_m3, topology, parameters, xp=...)` is an unchecked pure kernel.
`domain_valid(...)` accepts finite nonnegative physical state and strictly
positive participating reaction substrates, positive physical volumes/Km/Hill
powers/nested scales, nonnegative production/decay/time factors, explicit
boolean controls and finite representable outputs. This predicate returns one
boolean for its supplied world/batch; use `vmap` for independent world rejection.
The predicate clips invalid indices only to evaluate a rejected trial safely;
accepted physical concentrations and rates have no floors or clamps.

`accounting(extents_fmol, topology)` returns owner-accumulated reaction conversion,
growth source/sink and total changes, plus per-route species changes and the
declared charge-weight projection. It also accepts fmol/s inputs, in which case
outputs are rates. `projected_changes(extents, topology, weights)` exposes signed
per-route changes for caller-declared moiety/charge bases `[basis,species]`.
Unbalanced reactions remain visible. The elementary-charge-fmol diagnostic is
not a membrane current law; conversion to C requires an explicit Faraday choice.

Apply `dt * extent_rate` once to an authoritative amount inventory using the
returned total change. `material_residual(initial, current, integrated_extents,
topology)` checks `current-initial-stoichiometry*extents`. Track production,
basal decay and regulated decay diagnostics when distinguishing source and sink
channels; signed net growth alone does not establish a fuel balance.

All local rates evaluate incoming state before any local update. The component
uses one authoritative concentration array: native molecule `c_cells` and the
corresponding network `cell_concs` must be synchronized on entry. Native shell
diffusion/transport or intentionally stale molecule aliases are outside this
correspondence. State is interpreted as physical mM; any top-level molecular
display/charge scale or nonmaterial GRN coordinate requires an explicit caller
mapping. The nested growth scale is already included in the local law.

No stepping/controller/checkpoint schema is installed. The caller rejects
negative Euler trials, owns solver tolerances/time, volume changes, authoritative
amounts, accumulated source ledgers, topology rebindings and checkpoint identity.
Tests serialize no shared checkpoint: they demonstrate exact local array carry
restart across eight 10-ms steps (80 ms) with material residual
**3.29424e-15 fmol**. CPU JAX also covers batching/padding, singular-world
isolation and a regulator derivative against central finite differences.

## Regulator and native-capture boundaries

Cell reactions and growth sample their cell owner or the explicitly mapped
environment owner. Mitochondrial regulators always sample their mitochondrial
owner regardless of configured cell/env tag. Environment regulators tagged env
sample their own environment, while those tagged cell become literal factor 1;
even a direct **inhibitor** tagged cell contributes **positive 1** in this branch.

Ordinary activator Hills multiply, independent `!` activator Hills add to that
product, and inhibitor Hills multiply the result. Independent-only activation
starts from baseline 1. Optional direct `&` terms form a signed raw-concentration
sum multiplying the expression. Inhibitor `!` is stripped and remains
multiplicative. A trailing `*` is stripped but voltage sensitivity is absent
because all three generators pass `in_mem_tag=False`.

Pinned source revision is `5269a714aa2593ed2a6708c4516289977d8ae1a2`. The native
child authenticates installed/checkout bytes and executes `read_reactions`,
`Reaction.__init__`, `default_zones`, `get_influencers`, all four rate generators
and all three matrix builders. Actual time-dilation assignments and the
`tissue_init` growth block are extracted with source line ranges; actual
`Molecule.init_growth` selects supplied small profile maps. The sole modulator
hook returns explicit samples and makes no spatial-function equivalence claim.
Neither production Cells nor JAX is imported in the native child. The independent
80-digit Decimal oracle imports only stdlib and uses dictionary/owner loops.

Eleven limitations retain native inputs, partial expressions/state and outcomes:
Python `None` reaction free energy, unknown zone, empty reactants, mismatched
lists, direct inhibitor before another inhibitor, only-direct activator plus
only-direct inhibitor, unknown regulator zone, disabled-mito fallback retaining
the original zone, duplicate-name overwrite, zero reversible substrate and
negative growth scale. The zero-substrate case produces nonfinite values and
dense matrix contamination; no native clamp is inferred. Supported bindings
reject malformed/broken configurations. Positive-substrate and positive-scale
requirements bound the supported numerical domain explicitly.

The full native `run_loop` is not executed. In particular, source environment
then cell Euler mutation, concentration clipping, transport/pumping/gating,
mitochondrial row coupling/voltage refresh, energy charge and charge scaling
remain composition concerns. No native geometry/full-cell/tissue parity, ATP
demand, physical heat or thermodynamic closure is claimed. Literal Q and signed
regulation do not establish a passive dissipation law.

## Reproducible clock evidence and freeze

The unregulated growth fixture has `tau = 4.040404040404041 s`. At three tau
(12.1212121212 s), 48/96/192 Euler updates produce maximum errors
**0.00553528209 / 0.00277595473 / 0.00138991979 mM**, observed orders
**0.995673 / 0.997982**. At 12 tau (48.4848484848 s), 384 updates leave
**5.07340e-6** of the initial departure from equilibrium, with maximum material
residual **2.66454e-15 fmol**. This is a local linear-growth clock, not a settling
claim for an arbitrary network, organelle or tissue.

Attempt 01 stops at lint; attempt 02 is explicitly source preflight (38/11 and
no unit-test count); attempt 03 stops at lint; attempt 04 is the complete
92-test receipt. All failed evidence is retained. Metadata finalization only
verifies existing hashes/resources and copies this contract; no scientific
follow-up, acceptance, regression or audit is running.

```sh
taskset -c 7 env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 \
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  /mnt/workspaces/Cells/venv-cpu/bin/python -B \
  agent-work/cells-worker-01/workfiles/check_betse_network_reactions.py \
  --output /mnt/workspaces/Cells/betse-network-reactions-development-NEW
```

All seven owned scientific files and the evidence are frozen. Shared integration
remains Chief-owned.
