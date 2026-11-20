# Cells proofs

Browse Cells engine laws by scientific topic. Each claim links its Lean proofs, tested engine code and biological measurements. [Current law and operator coverage](COVERAGE.md) · [November 19 review of 30 laws and their biological evidence](PROGRESS.md#19-november-2026--law-and-evidence-review)

## Proof index

<!-- generated: claims-index -->

Direct Lean claims cover [30 of 32 laws](COVERAGE.md#registered-laws) and [5 of 24 operators](COVERAGE.md#registered-operators).

| Category | Claims | Lean proved | Numerical checks | Claims with biological evidence |
| --- | ---: | ---: | --- | ---: |
| [Membrane transport and osmosis](COVERAGE.md#category-membrane-transport) | 3 | 3 | 3 checked | 3 |
| [Ion channels and junctions](COVERAGE.md#category-channels-and-junctions) | 8 | 8 | 7 checked · 1 failed | 8 |
| [Pumps and cotransport](COVERAGE.md#category-pumps-and-cotransport) | 4 | 4 | 3 checked · 1 failed | 4 |
| [Reactions and binding](COVERAGE.md#category-reactions-and-binding) | 3 | 3 | 3 checked | 3 |
| [Molecular assembly and catalysis](COVERAGE.md#category-molecular-assembly) | 8 | 8 | 6 checked · 2 failed | 6 |
| [Tissue transport and conservation](COVERAGE.md#category-tissue-and-conservation) | 6 | 6 | 5 checked · 1 failed | 6 |
| [Cell physiology](COVERAGE.md#category-cell-physiology) | 1 | 0 | 1 checked | 1 |

<!-- /generated -->

Each category opens its detailed claim table on GitHub. The last column above counts claims with a recorded measurement or literature finding, including partial evidence. Each numerical result applies to the cases in its linked record. [Engine law coverage](COVERAGE.md) · [Design notes](ENGINE_LAW_VERIFICATION.md) · [Voltage pilot closeout](../reports/BIO003_PILOT_CLOSEOUT.md)

## Biological evidence

The catalog gives each measurement, its primary source and the part of the law it tests. **Partial evidence** means the literature measures a relevant part of the claim and a full biological verdict remains open. **Not assessable** means a recorded comparison has too much uncertainty for a verdict. The studies and their figures are linked in each row. [Literature review](claims/incoming/biological-evidence.md) · [Pump flux, charge and ATP measurements](claims/incoming/pump-charge-evidence.md) · [PGI worksheet audit](claims/incoming/pgi-evidence.md) · [Publisher’s PGI workbook and spectra](https://mdpi-res.com/metabolites/metabolites-02-00818/article_deploy/metabolites-02-00818-s001.zip)

## Maintaining the claims

Edit the claims register. A stable `id` gives each claim its note under `claims/`. Set `category` to a key from the register’s `categories` map. The key keeps the section link stable when its display title changes. In `formal.theorems`, map fully qualified Lean names to their source files. Use `uses` to link claims that build on earlier proofs. [Editable register](claims.json) · [JSON Schema](claims.schema.json)

In `formal.about`, list the canonical registry IDs whose law or operator property the theorem establishes. General composition and accounting theorems can leave this empty. In `numerical.comparisons`, list the comparison IDs for the claim. Each comparison names the models, laws and operators it exercised. For engine runs, `engine_revision` identifies the code that ran. The `record_revision` pins the comparison driver and the published result. For a reference calculation it also pins the implementation. File paths in the register start at the checkout root.

In `biology.observable` and `unit`, name the quantity the claim needs. Use `biology.finding` for a brief published measurement, its scope and its primary citation. The generator puts that finding in the detailed catalog and the claim page. Formal experimental comparisons go in `biology.evidence`. The catalog reads their observed and predicted values, assessment and citation directly from those records. A claim awaiting measurements displays its requested observable.

The Search agent collects primary biological references in `claims/incoming/`, with the preparation, protocol, measured quantity, uncertainty and figure or table. The Lean lane checks the corresponding engine observable and records the comparison in the register. Enter a biological verdict when a comparison has a documented outcome. [Reviewed measurements and follow-up](PROGRESS.md#19-november-2026--biological-evidence-review) · [Channel voltage-clamp sources](claims/incoming/channel-gating-evidence.md)

A normal `lake build` checks that each named theorem exists in its declared module, then regenerates the topic overview, claim notes and catalog. With `CELLS_PYTHON` set to the Cells Python interpreter, the build also refreshes the registry inventory from the active checkout. A Lean-only build uses the last exported inventory. Commit the generated files alongside edits to the register. The documentation commands below run from `lean/`.

```bash
python3 scripts/generate_claims.py
python3 scripts/generate_claims.py --check
```

To compare with today's engine registrations, run the following in the Cells environment. Omit `--check` to refresh the inventory and pages. The inventory contains declaration IDs and locations exported by the engine. [Manifest source](../src/cells/registry/declarations.py#L659)

```bash
python -B scripts/generate_claims.py --live-registry --check
```

These queries list claims with held-out measurements and claims whose comparison exercised a given law.

```bash
jq -r '.claims[] | select(any(.biology.evidence[]; .role == "held_out_from_fitting")) | .id' claims.json
jq -r --arg law 'logmean_electrodiffusion@1' '
  .comparisons as $checks | .claims[]
  | select(any(.numerical.comparisons[]; $checks[.].laws | index($law))) | .id' claims.json
```

### Reusing a proof

Keep the Cells theorem beside the mechanism it explains. Import a narrow upstream module when it fits our pinned Lean version. For a short result from another Lean version, a local derivation can be simpler. When copying licensed source, keep the original attribution, license and required notices with the copy. Give the claim a `formal.sources` entry for the upstream theorem at a fixed revision and label how we used it. The binding claim shows a local Lean 4 derivation. The face-power claim links an optional external import. [Binding example](claims/single-site-binding.md) · [Face-power example](claims/extracellular-face-dissipation.md)

Two monotonicity proofs from `grn-lean` also apply directly to the scalar Hill factors in Cells. The optional check compiles the pinned definition and both upstream proofs, then verifies the equivalence with our log-space evaluation. The chemistry review records which reaction-network results apply to the closed enzyme fixture. [Hill specialization](checks/hill/Response.lean) · [Chemistry libraries tested against Cells](ENGINE_LAW_VERIFICATION.md#chemistry-libraries-tested-against-cells)

## Build

Run these commands from `lean/`. Lean and Mathlib are pinned to 4.19.0. Lake reads the dependency revisions from the lockfile. The Linux x86-64 setup below reuses the lane’s installed compiler, or fetches it on a fresh checkout. [Lean release](https://github.com/leanprover/lean4/releases/tag/v4.19.0) · [Mathlib release](https://github.com/leanprover-community/mathlib4/releases/tag/v4.19.0)

```bash
mkdir -p .lake/bootstrap .lake/tmp .lake/cache
export TMPDIR="$PWD/.lake/tmp" XDG_CACHE_HOME="$PWD/.lake/cache"
if [ ! -x .lake/bootstrap/lean-4.19.0-linux/bin/lake ]; then
  curl -fL --retry 2 -o .lake/bootstrap/lean-4.19.0-linux.tar.zst \
    https://github.com/leanprover/lean4/releases/download/v4.19.0/lean-4.19.0-linux.tar.zst &&
    tar --zstd -xf .lake/bootstrap/lean-4.19.0-linux.tar.zst -C .lake/bootstrap
fi
export PATH="$PWD/.lake/bootstrap/lean-4.19.0-linux/bin:$PATH"
```

On the first build, fetch the compiled dependencies for the imported modules. Subsequent edits normally need only `lake build`.

```bash
lake exe cache get Mathlib.Data.Complex.Exponential \
  Mathlib.Analysis.SpecialFunctions.Log.Basic Mathlib.Algebra.Order.BigOperators.Group.Finset \
  Mathlib.Analysis.Calculus.Deriv.Add Mathlib.Analysis.Calculus.Deriv.Inv \
  Mathlib.Data.Nat.Factorial.Basic Mathlib.Data.Matrix.Mul Mathlib.Tactic.Positivity \
  Mathlib.Tactic.FieldSimp Mathlib.Tactic.Linarith Mathlib.Tactic.Ring \
  Mathlib.Algebra.BigOperators.Group.Finset.Piecewise \
  Mathlib.Algebra.BigOperators.Group.Finset.Sigma \
  Mathlib.Algebra.BigOperators.Ring.Finset Mathlib.Data.Real.Basic Mathlib.Tactic.DeriveFintype
lake build
```

To check the ATOMS Lab dimensional algebra on the Cells toolchain, run the following from `lean/`. The first run downloads two source modules and their license from a pinned revision and fetches the compiled matrix-rank dependency if needed. Later runs can use the local cache. The check compiles the dimension of flux × molar potential and checks the scalar conversion used by the engine. [Optional proof](checks/units/FacePower.lean) · [Pinned source and compatibility edit](checks/units/check.sh)

```bash
bash checks/units/check.sh
```

For the Hill proofs, the first run fetches two pinned source files, their MIT license and any missing compiled real-power dependencies. The command works from the cache on subsequent runs. [Hill proof runner](checks/hill/check.sh)

```bash
bash checks/hill/check.sh
```

## CPU comparisons

Run these from `lean/` with the pinned Lake executable on your path. Use the Cells CPU Python environment, or set `CELLS_PYTHON` to its interpreter. Each driver prints its numerical results as JSON. See the [development results](PROGRESS.md).

```bash
mkdir -p .lake/tmp .lake/cache
export TMPDIR="$PWD/.lake/tmp" XDG_CACHE_HOME="$PWD/.lake/cache"
export PYTHONPATH="../src:.." PYTHONDONTWRITEBYTECODE=1
export JAX_PLATFORMS=cpu JAX_ENABLE_X64=1 JAX_ENABLE_COMPILATION_CACHE=0
cells_python=${CELLS_PYTHON:-python}
```

<details>
<summary>Commands for individual comparisons</summary>

For membrane insertion, compare both operators with a one-patch fixed-charge solution. The first command reports the engine result and exits with status 1 if any case fails. The two optional controls rerun the stress case with known single-patch heat and image-charge values substituted in memory. At the recorded revision the original and heat-only runs fail, and the heat-and-charge control completes. [Driver](checks/membrane_insertion.py) · [Results](PROGRESS.md#19-november-2026--membrane-insertion-heat)

```bash
"$cells_python" -B checks/membrane_insertion.py
"$cells_python" -B checks/membrane_insertion.py --one-patch-control heat
"$cells_python" -B checks/membrane_insertion.py --one-patch-control heat-and-charge
```

For single-site binding, compare the compiled law against the independent S1 states and read the occupied fraction in a tissue cell. The input substitution checks whether the comparison distinguishes free and total ligand. [Binding driver](checks/single_site_binding.py)

```bash
"$cells_python" -B checks/single_site_binding.py
```

For Hill activation and inhibition, compare the compiled Cells factors with a 65-digit evaluation of the upstream formula on the engine's reaction test grid. [Hill comparison](checks/hill/compare.py)

```bash
"$cells_python" -B checks/hill/compare.py
```

For junction transport, the driver compares fluxes with an independent scalar reference and runs the per-cell potassium ledger on one closed tissue world. Reversing the endpoint bookings tests the sensitivity of the per-cell comparison. [Junction driver](checks/constant_field.py) · [Independent reference](../validation/tissue/surface_reference.py#L71)

```bash
"$cells_python" -B checks/constant_field.py
"$cells_python" -B -m pytest -q -p no:cacheprovider \
  ../tests/unit/test_surface_transport.py::test_independent_surface_laws_and_accounting \
  ../tests/unit/test_surface_transport.py::test_patch_subdivision_route_reversal_and_padding \
  ../tests/unit/test_surface_transport.py::test_equilibrium_and_transport_blocking
```

For voltage-dependent junction gating, compare the clamped trajectory at both polarities, then follow tracer transfer in three tissue cell pairs through a block and release. [Gate comparison](checks/junction_gate.py) · [Cx43 clamp measurements](claims/incoming/junction-gate-evidence.md)

```bash
"$cells_python" -B checks/junction_gate.py
```

The Na⁺/K⁺ driver checks the eight gated channels and both leaks together on one tissue membrane. The chloride driver checks the sign of material transfer, electrode current and the shift in reversal voltage. A third calculation applies published voltage-clamp protocols to Kv1.1, Kv1.4 and NaV1.2. [Na⁺/K⁺ comparison](checks/ion_channels.py) · [Chloride comparison](checks/chloride_channel.py) · [Experimental conditions and measured currents](claims/incoming/channel-gating-evidence.md)

```bash
"$cells_python" -B checks/ion_channels.py
"$cells_python" -B checks/chloride_channel.py
"$cells_python" -B checks/channel_clamp_evidence.py
```

For neutral permeation, compare the compiled inward flux and the final amounts in a closed tissue pair with the analytic solution. The unequal-volume case distinguishes amount from concentration. [Neutral driver](checks/neutral_permeation.py) · [Closed-pair reference](../validation/passive/passive_reference.py#L66)

```bash
"$cells_python" -B checks/neutral_permeation.py
```

For proton leak, check the reversal voltage, instantaneous heat, the small-voltage branch and the free H⁺ read in a buffered tissue cell. The driver also resolves the polynomial’s reversal ratio at 80-digit precision. [Proton driver](checks/proton_leak.py) · [Flux reference](../validation/betse/junction_transport/check.py#L10)

```bash
"$cells_python" -B checks/proton_leak.py
```

For ATP-driven transport, compare compiled tissue rates against the four frozen proton and neutral cargo panels. The driver reports free energy, cycle flux, heat and work errors, then checks the voltage response and both off switches. [ATP driver](checks/atp_cycle.py) · [Numerical and biological results](PROGRESS.md#19-november-2026--atp-driven-transport)

```bash
"$cells_python" -B checks/atp_cycle.py
```

For the Na⁺/K⁺ and calcium pumps, compare both stall voltages and the outward current against independent scalar calculations. One of the five cells starts with cancelling pump currents. The 1 ms tissue run checks all three ion transfers and the heat booked by each pump. [Driver](checks/electrogenic_pumps.py) · [Results](PROGRESS.md#19-november-2026--sodium-potassium-and-calcium-pump-charge)

```bash
"$cells_python" -B checks/electrogenic_pumps.py
```

For extracellular faces, run the direction and power cases and the closed tissue model. The driver checks the engine's two mean thresholds, opposing drives, an adjacent-float pair and an intentionally reversed flux. The reference test checks the scalar mean against Decimal. [Face driver](checks/logmean_face.py) · [Scalar reference](../validation/tissue/surface_reference.py#L13)

```bash
"$cells_python" -B checks/logmean_face.py
"$cells_python" -B -m pytest -q -p no:cacheprovider \
  ../tests/unit/test_surface_reference.py::test_reference_logarithmic_mean_against_decimal
```

For closed reactions, the driver reads the declaration, checks its correspondence to Lean and runs the registered operator with the fixture’s time-zero controls. It compares all four stored species changes with the booked extents, then measures both inventory residuals at the existing tolerances for stored amounts. [Enzyme driver](checks/closed_enzyme.py) · [Tolerance definitions](../tests/unit/test_species_reactions_halfstep.py#L275)

```bash
"$cells_python" -B checks/closed_enzyme.py
"$cells_python" -B -m pytest -q -p no:cacheprovider \
  ../tests/unit/test_species_reactions_halfstep.py::test_the_bookings_are_exact_on_random_states \
  '../tests/unit/test_species_reactions_refusals.py::test_definition_refusals[unbalanced]'
```

For assembly exchange, compare entry and exit rates at every three-species composition through eight molecules. Two seeded lineages check the heat and material booked through growth, division and loss of the last molecule. The driver also compares the first species’ share during growth with equal and unequal leave constants. [Assembly driver](checks/reservoir_exchange.py) · [Results and lipid measurements](PROGRESS.md#19-november-2026--assembly-reservoir-exchange)

```bash
"$cells_python" -B checks/reservoir_exchange.py
```

For the two GARD laws, compare both directions of each transfer and each four-event cycle against exact rational rates. The full run also exercises two cases where subtracting a large diagonal coefficient loses the remaining catalyst. It exits with status 1 when the passive law refuses a valid event. The controls-only command runs the ordinary comparisons and two passing one-event controls. [Driver](checks/gard_catalysis.py) · [Findings and membrane measurements](PROGRESS.md#19-november-2026--gard-catalysis-on-reversible-transfers)

```bash
"$cells_python" -B checks/gard_catalysis.py
"$cells_python" -B checks/gard_catalysis.py --controls-only
```

For ideal and regular assembly mixing, one command checks the 592 registered probe states under both count measures and rebooks four compiled trajectories. It compares the activity curves with Shaw’s 25 DOPC measurements and Parker’s independent crystal-onset endpoint. [Driver](checks/assembly_mixing.py) · [Fit, assumptions and results](PROGRESS.md#19-november-2026--ideal-and-regular-assembly-mixing)

```bash
"$cells_python" -B checks/assembly_mixing.py
```

For stochastic encounters and transition-state catalysis, compare the two directional rates with and without the catalyst, then replay a two-state clock on the same random draws. The full run returns status 1 when an expected rate or clock fails. The controls-only run checks the ordinary pairs, boundary cases and two equivalent or well-conditioned clocks. The last command evaluates the confined-binding measurements using the engine’s pool reaction. [Clock reproducer](checks/assembly_kinetics.py) · [Measured occupancies and engine finding](PROGRESS.md#19-november-2026--stochastic-encounters-and-transition-state-catalysis)

```bash
"$cells_python" -B checks/assembly_kinetics.py
"$cells_python" -B checks/assembly_kinetics.py --controls-only
"$cells_python" -B checks/confined_binding.py
```

The inward-rectifier driver checks the bound on the current–voltage slope, a change of reference concentration, and Kir4.1 currents at matched driving voltage. Its full comparison exits with status 1 if an equivalent reference setting fails. The symport driver checks all four sodium counts and compares the two-sodium carrier with measured charge, particle flux and voltage shifts. [Experimental comparisons and engine finding](PROGRESS.md#19-november-2026--inward-rectification-and-sodium-anion-symport)

```bash
"$cells_python" -B checks/inward_rectifier.py
"$cells_python" -B checks/inward_rectifier.py --controls-only
"$cells_python" -B checks/sodium_anion_symport.py
```

For the potassium–anion operator, the driver compares a closed two-compartment run with the exact concentration trajectory. The latest retest confirmed that the engine refuses the earlier wrong-direction step. The full comparison still reports the extreme concentration-ratio overflow. The controls use smaller steps and finite product ratios. [Original result](PROGRESS.md#19-november-2026--potassium-and-anion-cotransport) · [Retest](PROGRESS.md#20-november-2026--osmotic-water-and-potassiumanion-transport)

```bash
"$cells_python" -B checks/potassium_anion_symport.py
"$cells_python" -B checks/potassium_anion_symport.py --controls-only
```

For water and potassium–anion transport in changing volumes, compare the CPU engine with two independent numerical integrators. The second command checks vesicle swelling, red-cell volumes, pressure-driven flow and the water change accompanying measured solute transfer in trout red cells. [Proof, experiments and numerical results](claims/osmotic-water.md)

```bash
"$cells_python" -B checks/osmotic_water.py
"$cells_python" -B checks/osmometry.py
```

For the tissue balance, the driver follows A and B through one 50 ms composite step on twelve finite extracellular compartments. It compares the change in their stored amounts at nodes 2 through 5 with the signed transfers on the two boundary faces. Each species also has to account for its share of the local conversion. The same comparison runs on the full chain and with the largest boundary face reversed in the recorded transfers. The existing passive-chain test checks the trajectory against the independent split-step reference. [Regional driver](checks/regional_balance.py) · [Reference comparison](../tests/unit/test_species_reactions_composition.py#L84)

```bash
"$cells_python" -B checks/regional_balance.py
"$cells_python" -B -m pytest -q -p no:cacheprovider \
  '../tests/unit/test_species_reactions_composition.py::test_guard_2_linear_networks_on_the_chain_run_the_engine_orders_map[passive]'
```

</details>
