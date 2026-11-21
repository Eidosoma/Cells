# Cells proofs

Browse Cells engine laws by scientific topic. Each claim links its Lean proofs, tested engine code and biological measurements. [Current law and operator coverage](COVERAGE.md) · [Failing numerical checks](COVERAGE.md#failing-numerical-checks) · [Latest comparisons and engine findings](PROGRESS.md)

## Proof index

<!-- generated: claims-index -->

Direct Lean claims cover [49 of 49 laws](COVERAGE.md#registered-laws) and [29 of 29 operators](COVERAGE.md#registered-operators).

| Category | Registered laws with proof | Claims with proof | Numerical checks | Claims with biological evidence |
| --- | ---: | ---: | --- | ---: |
| [Membrane transport and osmosis](COVERAGE.md#category-membrane-transport) | 5 of 5 | 8 of 8 | 8 checked | 8 |
| [Ion channels and junctions](COVERAGE.md#category-channels-and-junctions) | 14 of 14 | 12 of 12 | 12 checked | 11 |
| [Pumps and cotransport](COVERAGE.md#category-pumps-and-cotransport) | 13 of 13 | 8 of 8 | 8 checked | 8 |
| [Reactions and binding](COVERAGE.md#category-reactions-and-binding) | 3 of 3 | 8 of 8 | 8 checked | 6 |
| [Molecular assembly and catalysis](COVERAGE.md#category-molecular-assembly) | 13 of 13 | 19 of 19 | 18 checked · 1 failed | 15 |
| [Tissue transport and conservation](COVERAGE.md#category-tissue-and-conservation) | 1 of 1 | 19 of 19 | 19 checked | 14 |
| [Cell physiology](COVERAGE.md#category-cell-physiology) | — | 3 of 3 | 3 checked | 3 |

<!-- /generated -->

Each category opens its detailed claim table on GitHub, including registered laws still awaiting a proof. A single claim can cover several laws. The last column counts claims with a recorded measurement or literature finding, including partial evidence. Each numerical result applies to the cases in its linked record. [All registered laws](COVERAGE.md#registered-laws) · [Design notes](ENGINE_LAW_VERIFICATION.md) · [Voltage pilot closeout](../reports/BIO003_PILOT_CLOSEOUT.md)

On 21 November, five former numerical failures passed their repair checks, including fresh-pool capacity and self-regulated turnover. The GARD pair-heat case remains recorded on version 1. [Repair results](PROGRESS.md#nov21-engine-review) · [Current failure list](COVERAGE.md#failing-numerical-checks)

## Biological evidence

The biological review identifies three engine opportunities with measured targets. It covers the reversal of the yeast vacuolar proton pump, the time to rupture of a vesicle under steady tension, and fast and slow closure of Cx43 gap junctions. [Measurements, current engine results and proposed changes](PROGRESS.md#biological-model-review)

The Cx43 polarity measurements bound the error of the registered single-gate law. The new two-gate functions satisfy the predicted amplitude relation on synthetic clamps. Resolving the mixed amplitude in a measured Cx43 trace remains open. [Measurements](PROGRESS.md#cx43-series-gates) · [Compiled comparison](claims/junction-series-amplitudes.md)

A serial dilution experiment follows free fluorescein through three successive exchanges. The catalog gives the measured concentrations alongside the ideal series, including the discrepancy at the third 80% wash. [Measured dilution and its scope](PROGRESS.md#nov21-wash)

For finite-pool washes, tracer measurements distinguish what leaves the exterior, what survives inside a vesicle, and what can later enter another membrane. [Washout and redistribution measurements](claims/pool-replacement.md#biological-evidence)

Yeast mitochondrial ATP synthase provides a measured example of reversal. The enzyme switched from hydrolysis to synthesis as the proton gradient increased. Cells captures the shift between the lowest and highest ATP loads. The comparison also records the four intermediate measurements outside the combined interpolation limits. [Mitochondrial stall and biological evidence](claims/mitochondrial-stall-heat.md#biological-evidence)

The catalog gives each measurement, its primary source and the part of the law it tests. **Partial evidence** means the literature measures a relevant part of the claim and a full biological verdict remains open. **Not assessable** means a recorded comparison has too much uncertainty for a verdict. The studies and their figures are linked in each row. [Literature review](claims/incoming/biological-evidence.md) · [Pump flux, charge and ATP measurements](claims/incoming/pump-charge-evidence.md) · [PGI worksheet audit](claims/incoming/pgi-evidence.md) · [Publisher’s PGI workbook and spectra](https://mdpi-res.com/metabolites/metabolites-02-00818/article_deploy/metabolites-02-00818-s001.zip)

## Maintaining the claims

Edit the claims register. A stable `id` gives each claim its note under `claims/`. Set `category` to a key from the register’s `categories` map. The key keeps the section link stable when its display title changes. In `formal.theorems`, map fully qualified Lean names to their source files. Use `uses` to link claims that build on earlier proofs. [Editable register](claims.json) · [JSON Schema](claims.schema.json)

Laws inherit the topic of their direct proofs. Use `law_categories` to put a law awaiting its first proof in the right section, or to choose its primary topic when proofs span several categories. Newly registered laws awaiting classification appear together in the overview.

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

### Checking whether the engine code changed

The source check compares the working files with the Git blobs already pinned by each comparison. It reads the engine or reference sources, any tests and fixtures listed alongside them, and the comparison driver at its own evidence revision. It prints JSON naming every affected comparison, claim and path. Run it from `lean/` in a checkout containing the recorded history.

```bash
python3 -B scripts/generate_claims.py --check-sources
python3 -B scripts/generate_claims.py --check-sources --since 8f9bc050
```

The first command includes historical comparisons. The second checks for changes since the reviewed engine commit. Use the previous landing as the baseline in automation, or `HEAD` for uncommitted edits. Exit 0 means all selected files match, 1 means at least one changed, and 2 means the comparison could not be completed. A changed file identifies a driver to review or rerun. Imports and data omitted from a comparison's citations can also affect its result. A replay establishes the current numerical outcome. [Source review and retests](PROGRESS.md#claim-source-review)

These queries list claims with held-out measurements and claims whose comparison exercised a given law.

```bash
jq -r '.claims[] | select(any(.biology.evidence[]; .role == "held_out_from_fitting")) | .id' claims.json
jq -r --arg law 'logmean_electrodiffusion@1' '
  .comparisons as $checks | .claims[]
  | select(any(.numerical.comparisons[]; $checks[.].laws | index($law))) | .id' claims.json
```

### Reusing a proof

For new physics claims, look first for a compatible public theorem with matching assumptions and units. The charter gives the criteria for choosing a source, recording a direct import or optional comparison, and keeping a short proof local. [Cells Lean charter](AGENTS.md)

The single-site binding proof derives the Langmuir formula locally. The face-power check imports the ATOMS Lab dimensional algebra. Both claims identify the published source and how Cells uses it. [Binding example](claims/single-site-binding.md) · [Face-power example](claims/extracellular-face-dissipation.md)

The cleft-fill and wash proofs share the same ideal mixing term. Their default proof uses Mathlib’s logarithm bounds. An optional check identifies that term with Mathlib’s relative-entropy function. A second optional check imports Physlib’s two-state ensemble and recovers the equilibrium open probability of a junction gate when the fitted gate coordinate equals the dimensionless energy gap. [Cleft heat](claims/cleft-mixing-heat.md) · [Wash heat](claims/compartment-wash.md) · [Gate specialization](checks/physlib/JunctionEquilibrium.lean)

Two monotonicity proofs from `grn-lean` also apply directly to the scalar Hill factors in Cells. The optional check compiles the pinned definition and both upstream proofs, verifies the equivalence with our log-space evaluation, and shows that basal channel availability preserves the activating and inhibiting dose responses. The chemistry review records which reaction-network results apply to the closed enzyme fixture. [Hill specialization](checks/hill/Response.lean) · [Regulated channel proof](claims/regulated-state-response.md) · [Chemistry libraries tested against Cells](ENGINE_LAW_VERIFICATION.md#chemistry-libraries-tested-against-cells)

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
  Mathlib.Analysis.Calculus.Deriv.MeanValue Mathlib.Analysis.Calculus.Deriv.Pow \
  Mathlib.Analysis.SpecialFunctions.ExpDeriv \
  Mathlib.Algebra.BigOperators.Fin Mathlib.Algebra.BigOperators.Field Mathlib.Data.List.Rotate \
  Mathlib.Algebra.Order.BigOperators.GroupWithZero.List \
  Mathlib.Tactic.FieldSimp Mathlib.Tactic.Linarith Mathlib.Tactic.Ring \
  Mathlib.Algebra.BigOperators.Group.Finset.Piecewise \
  Mathlib.Algebra.BigOperators.Group.Finset.Sigma \
  Mathlib.Algebra.BigOperators.Ring.Finset Mathlib.Data.Real.Basic Mathlib.Tactic.DeriveFintype
lake build
```

To check the ATOMS Lab dimensional algebra on the Cells toolchain, run the following from `lean/`. The first run downloads two source modules and their license from a pinned revision and fetches the compiled matrix-rank dependency if needed. Later runs can use the local cache. The check verifies that flux × molar potential has units of power and electrode charge × voltage has units of energy. [Optional proofs](checks/units/FacePower.lean) · [Pinned source and compatibility edit](checks/units/check.sh)

```bash
bash checks/units/check.sh
```

For the relative-entropy comparison, the first command fetches the additional compiled Mathlib modules on the Cells pin. The second checks that the mixing term is nonnegative and vanishes exactly at a concentration ratio of one. [Optional proof](checks/mixing/KLFun.lean)

```bash
lake exe cache get Mathlib.InformationTheory.KullbackLeibler.KLFun
lake env lean -DwarningAsError=true checks/mixing/KLFun.lean
```

For the Hill proofs, the first run fetches two pinned source files, their MIT license and any missing compiled real-power dependencies. The command works from the cache on subsequent runs. [Hill proof runner](checks/hill/check.sh)

```bash
bash checks/hill/check.sh
```

<details>
<summary>Optional Physlib check for a junction gate</summary>

Physlib v4.22.0 uses the module name `PhysLean` and its own Lean 4.22.0 toolchain. Its extra axiom `Constants.kBAx` supplies a positive Boltzmann constant in the chosen units. From `lean/`, clone the tagged source once into `.lake/`. Run the commands inside that clone with Lean and Lake 4.22.0 on your path. [Upstream two-state ensemble](https://github.com/leanprover-community/physlib/blob/559b0e14bd87896d4ee536a536a8fb65e83b77cc/PhysLean/StatisticalMechanics/CanonicalEnsemble/TwoState.lean#L26-L37) · [Boltzmann constant axiom](https://github.com/leanprover-community/physlib/blob/559b0e14bd87896d4ee536a536a8fb65e83b77cc/PhysLean/StatisticalMechanics/BoltzmannConstant.lean#L20-L30) · [Gate specialization](checks/physlib/JunctionEquilibrium.lean)

```bash
gate_proof="$PWD/checks/physlib/JunctionEquilibrium.lean"
git clone --depth 1 --branch v4.22.0 https://github.com/leanprover-community/physlib .lake/physlib-v4.22.0
(
  set -e
  cd .lake/physlib-v4.22.0
  test "$(git rev-parse HEAD)" = 559b0e14bd87896d4ee536a536a8fb65e83b77cc
  lake env lean --version
  lake exe cache get Mathlib.Analysis.Calculus.ParametricIntegral \
    Mathlib.Analysis.SpecialFunctions.Log.Summable Mathlib.MeasureTheory.Integral.Prod \
    Mathlib.MeasureTheory.Measure.ProbabilityMeasure Mathlib.Analysis.InnerProductSpace.Basic \
    Mathlib.Analysis.Calculus.Deriv.Inv Mathlib.Data.NNReal.Defs Mathlib.Lean.Expr.Basic \
    Mathlib.Tactic.FieldSimp
  lake build PhysLean.StatisticalMechanics.CanonicalEnsemble.TwoState
  lake env lean -DwarningAsError=true "$gate_proof"
)
```

</details>

## CPU comparisons

Run these from `lean/` with the pinned Lake executable on your path. Use the Cells CPU Python environment, or set `CELLS_PYTHON` to its interpreter. Each driver prints its numerical results as JSON. See the [development results](PROGRESS.md).

```bash
mkdir -p .lake/tmp .lake/cache
export TMPDIR="$PWD/.lake/tmp" XDG_CACHE_HOME="$PWD/.lake/cache"
export PYTHONPATH="../src:.." PYTHONDONTWRITEBYTECODE=1
export JAX_PLATFORMS=cpu JAX_ENABLE_X64=1 JAX_ENABLE_COMPILATION_CACHE=0
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
cells_python=${CELLS_PYTHON:-python}
```

<details>
<summary>Commands for individual comparisons</summary>

For mitochondrial respiration and ATP delivery, check the seven reaction columns, charge on each side and the material booked in a world with a finite matrix and intermembrane space. The results link complex I proton measurements and a bovine ATP synthase structure to the counts the model assumes. [Mitochondrial balance and measurements](PROGRESS.md#mitochondrial-cycle-accounting)

```bash
"$cells_python" -B checks/mitochondrial_cycles.py
```

Check the stall conditions of all seven cycles, compare instantaneous heat and flux with the independent component equations on both CPU backends, and reproduce the yeast synthase load comparison. [Thresholds, measurements and limits](PROGRESS.md#mitochondrial-stall-heat)

```bash
"$cells_python" -B checks/mitochondrial_stall.py
```

Check how free magnesium shifts the adenylate kinase equilibrium, how pH shifts the held reductant supply's stall, and how the tissue books material, work and heat. The comparison includes two kinase assays and a measured redox equilibrium. [Predictions and biological evidence](PROGRESS.md#mitochondrial-kinase-supply)

```bash
"$cells_python" -B checks/mitochondrial_reactions.py
```

For the conditioned kidney-cell voltage, check the two-dose extrapolation on three synthetic Na/K/Cl membranes and reproduce the fixed C3 prediction and its figure-reading bounds. [C3 results](PROGRESS.md#conditioned-voltage-bounds)

```bash
"$cells_python" -B checks/conditioned_voltage.py
```

For cell compartments and membrane recycling, follow each owner's species and lumen voltage, then compare how much membrane area and channel cargo return. The strict command checks whether an engine run can observe a nearly depleted channel population. It exits 1 on the recorded engine revision. [Compartment and recycling results](PROGRESS.md#owned-compartment-inventory) · [Reachable zero-count refusal](PROGRESS.md#trafficking-empty-surface)

```bash
"$cells_python" -B checks/compartment_trafficking.py
"$cells_python" -B checks/compartment_trafficking.py --require-trajectory
```

For division, compare the daughter amounts, voltage and booked work to the event equations. The same driver follows linear and exponential bridge closure, checks the resulting species fluxes, and compares both aperture curves with held-out points from a zebrafish bridge. [Division event](PROGRESS.md#isopotential-division) · [Bridge closure and measured diameters](PROGRESS.md#daughter-bridge-closure)

```bash
"$cells_python" -B checks/division_bridge.py
```

For membrane populations, follow precursor into maturing, active and removed units, then read the potassium flow at several patch areas. The driver also evaluates published receptor retention and endplate currents. The second command isolates the recorded rounding residual at exactly zero units. [Turnover and maturation](PROGRESS.md#surface-population-turnover) · [Current and surface count](PROGRESS.md#membrane-population-flow) · [Empty-population finding](PROGRESS.md#empty-surface-flow)

```bash
"$cells_python" -B checks/population_units.py
"$cells_python" -B checks/population_units.py --require-empty
```

For scheduled cell replacement, compare simultaneous donor and template arrivals, including a volume-preserving copy with nonzero water free energy. The second command checks that v2 admits the first representable template volume strictly inside the water bound and refuses the bound itself. [Material and charge](PROGRESS.md#scheduled-cell-replacement) · [Water and measured cell volumes](PROGRESS.md#cell-replacement-water) · [Boundary reproducer](PROGRESS.md#cell-replacement-volume-boundary) · [Repair and retest](PROGRESS.md#claim-source-review)

```bash
"$cells_python" -B checks/cell_replacement.py
"$cells_python" -B checks/cell_replacement.py --boundary-only --require-interior
```

For size-triggered fission and daughter continuation, compare fixed-quota and independent partitions, then follow empty and full daughters through the engine. The driver also compares measured bead-count variance with the probability model. To verify the figure readings, run `pdftocairo -f 3 -l 3 -svg article.pdf figure.svg` on the four-page PDF listed as `vector_pdf` and pass `--figure-svg figure.svg` to the driver. [Partition results and measurements](PROGRESS.md#size-threshold-fission) · [Daughter selection](PROGRESS.md#lineage-daughter-continuation) · [Ledger documentation finding](PROGRESS.md#lineage-fission-sink-sign) · [Figure source](checks/data/fornell2017_partition.json)

```bash
"$cells_python" -B checks/lineage_fission.py
```

For serial transfer and shear fission, follow an impermeant tracer through successive washes and from each parent to its daughters. The driver also checks discarded material, signed free energy and refused splits. The biological records include measured wash recovery and paired parent–daughter fluorescence. [Transfer results](PROGRESS.md#vesicle-serial-transfer) · [Division results](PROGRESS.md#vesicle-shear-fission)

```bash
"$cells_python" -B checks/vesicle_population.py
```

For the finite-compartment wash, compare compiled exchanges and whole tissue runs with the inventory formula and the fluorescein series. For the two-gate junction, compare all gate-kind pairings with the constant-voltage expansion. [Wash and its resolution limit](PROGRESS.md#nov21-wash) · [Series-gate functions](PROGRESS.md#nov21-features)

```bash
"$cells_python" -B checks/compartment_wash.py
"$cells_python" -B checks/junction_series_gates.py
```

For scheduled pool replacement, replay both sides of the pulse and wash, including species receipts and saved relations. The capacity comparison exits 1 when either schedule accepts an oversized bath. [Tracer and energy results](PROGRESS.md#pool-replacement) · [Capacity finding](PROGRESS.md#pool-replacement-capacity)

```bash
"$cells_python" -B checks/pool_replacement.py --case pulse
"$cells_python" -B checks/pool_replacement.py --case capacity
```

For vesicle exchange, compare lipid insertion and neutral solute permeation against their rate equations and measured washout and swelling. The shared-pool controls follow one lipid and one solute between two vesicles. The one-event fixed-volume case now returns the declared-lumen records. [Measurements and engine results](PROGRESS.md#vesicle-permeation) · [Shared-pool counts](PROGRESS.md#shared-pool-inventory) · [Earlier reporting failure](PROGRESS.md#shared-pool-declared-volume) · [Repair and retest](PROGRESS.md#claim-source-review)

```bash
"$cells_python" -B checks/vesicle_exchange.py
"$cells_python" -B checks/shared_pool.py --controls-only
"$cells_python" -B checks/shared_pool.py --declared-only
```

For bilayer vesicles, the driver compares two molecular area units, the osmotic volume and membrane tension with a 70-digit reference. The repaired engine agrees on all eight threshold decisions. The driver also compares measured deflation, swelling and survival during fixed-tension holds. [Physical results](PROGRESS.md#bilayer-footprint) · [Earlier threshold finding](PROGRESS.md#vesicle-threshold-hold) · [Repair and measured rupture timing](PROGRESS.md#biological-model-review)

```bash
"$cells_python" -B checks/vesicle.py --controls-only
"$cells_python" -B checks/vesicle.py
```

For a restricted cleft, the controls follow tracer dilution and mixing heat through membrane growth and a 60:40 patch split. The full comparison also tests a positive trace concentration on each side. It exits with status 1 when the engine refuses a valid fill. [Geometry, tracer measurements and heat finding](PROGRESS.md#cleft-bath-fill)

```bash
"$cells_python" -B checks/restricted_lumen.py --controls-only
"$cells_python" -B checks/restricted_lumen.py
```

For the held bath, follow the controller’s dose and the tissue’s supply through four solution changes, then compare potassium reversal shifts with measured cardiac currents. The full comparison verifies that both entry orders preserve an intended trace dose. The second command runs the ordinary controls. [Bath accounting and biological evidence](claims/scheduled-bath-exchange.md) · [Recipe-order repair and retest](PROGRESS.md#bath-order-repair)

```bash
"$cells_python" -B checks/bath_schedule.py
"$cells_python" -B checks/bath_schedule.py --controls-only
```

For regulated availability, pulse and wash out a ligand in both operator versions and compare the channel response with rat SK2 dose and timing measurements. The full driver also checks the order of reporter production when turnover changes its own regulator. The midpoint repair restored second-order convergence on the four tested grids. The controls-only run checks the pulse, both rate samples and the SK2 calculation. [Channel proof and biological measurements](claims/regulated-state-response.md) · [Turnover finding and reproducer](claims/regulated-turnover-routing.md)

```bash
"$cells_python" -B checks/regulated_availability.py
"$cells_python" -B checks/regulated_availability.py --controls-only
"$cells_python" -B checks/regulated_availability.py --ramp-only
```

For scheduled turnover, the driver checks production, clearance and chemical work, then compares a neuronal protein chase and a chamber with independently metered flow. The full run also checks that both extreme-rate worlds retain the 1 fmol net change and its chemical work. The second command runs the ordinary controls. [Proof, measurements and engine finding](claims/scheduled-species-turnover.md)

```bash
"$cells_python" -B checks/species_turnover.py
"$cells_python" -B checks/species_turnover.py --controls-only
```

For saturable uptake, compare the finite extracellular pool and both recipient cells against an independent solution, then test the concentration response against human red-cell measurements. [Proof and measured rates](claims/saturable-species-exchange.md)

```bash
"$cells_python" -B checks/species_exchange.py
```

The site driver follows two binding populations and their shared free ligand. The electrode driver compares both pulse polarities with independent charge and work calculations. The mixed-ion driver resolves the three currents at zero total current and reconstructs three measured squid-axon voltage shifts. [Site occupancy](claims/site-occupancy-stages.md) · [Electrode pulses](claims/electrode-pulses.md) · [Mixed membrane](claims/mixed-ion-reversal.md)

```bash
"$cells_python" -B checks/site_occupancy.py
"$cells_python" -B checks/current_injection.py
"$cells_python" -B checks/mixed_membrane.py
```

For membrane insertion, compare both operators with a one-patch fixed-charge solution. The first command reports the engine result and exits with status 1 if any case fails. The two optional controls rerun the stress case with known single-patch heat and image-charge values substituted in memory. Both repaired operators now complete the original stress rollout. [Driver](checks/membrane_insertion.py) · [Original result](PROGRESS.md#19-november-2026--membrane-insertion-heat) · [Repair](PROGRESS.md#nov21-engine-review)

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

For charged permeation, compare the CPU flux, heat and slopes with 60-digit arithmetic, follow charge through a finite tissue pair, and reproduce the two experimental current–voltage comparisons. [Charged-route driver](checks/charged_permeation.py)

```bash
"$cells_python" -B checks/charged_permeation.py
```

For proton leak, check the reversal voltage, instantaneous heat, the small-voltage branch and the free H⁺ read in a buffered tissue cell. The driver also resolves the polynomial’s reversal ratio at 80-digit precision. [Proton driver](checks/proton_leak.py) · [Flux reference](../validation/betse/junction_transport/check.py#L10)

```bash
"$cells_python" -B checks/proton_leak.py
```

For ATP-driven transport, compare compiled tissue rates against the four frozen proton and neutral cargo panels. The driver reports free energy, cycle flux, heat and work errors, then checks the voltage response and both off switches. It also finds the proton pump's stall voltage for each of the eight yeast vacuole assay conditions at all four supported couplings. [ATP driver](checks/atp_cycle.py) · [Tissue results](PROGRESS.md#19-november-2026--atp-driven-transport) · [Vacuole results](PROGRESS.md#biological-model-review)

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

For stochastic encounters and transition-state catalysis, compare the two directional rates with and without the catalyst, then replay a two-state clock on the same random draws. The full run returns status 1 when an expected rate or clock fails. The controls-only run checks the ordinary pairs, boundary cases and two equivalent or well-conditioned clocks. The last command evaluates the confined-binding measurements using the engine’s pool reaction. [Clock reproducer](checks/assembly_kinetics.py) · [Measured occupancies](PROGRESS.md#19-november-2026--stochastic-encounters-and-transition-state-catalysis) · [Opposed-contact clock retest](PROGRESS.md#claim-source-review)

```bash
"$cells_python" -B checks/assembly_kinetics.py
"$cells_python" -B checks/assembly_kinetics.py --controls-only
"$cells_python" -B checks/confined_binding.py
```

The inward-rectifier driver checks the current–voltage slope, equivalent concentration normalizations and Kir4.1 currents at matched driving voltage. All three normalizations now produce the same current, transfer and heat. The symport driver checks all four sodium counts and compares the two-sodium carrier with measured charge, particle flux and voltage shifts. [Original experimental comparisons](PROGRESS.md#19-november-2026--inward-rectification-and-sodium-anion-symport) · [Retest of all six numerical findings](PROGRESS.md#six-numerical-retests)

```bash
"$cells_python" -B checks/inward_rectifier.py
"$cells_python" -B checks/inward_rectifier.py --controls-only
"$cells_python" -B checks/sodium_anion_symport.py
```

For the eight-state two-sodium carrier, compare each edge with an independent stationary master equation and test the predicted dose response against measured propionate currents. The full run also checks whether the diagnostic flux agrees with the material flux down to 10⁻³⁰² fmol/s capacity and at zero. The original extreme-capacity case passes on the repaired engine. [Proof and biological comparison](claims/sodium-anion-diagram.md) · [Repair verification](PROGRESS.md#sodium-anion-capacity-repair)

```bash
"$cells_python" -B checks/sodium_anion_diagram.py
"$cells_python" -B checks/sodium_anion_diagram.py --controls-only
```

For the potassium–anion operator, compare a closed two-compartment run with the exact concentration trajectory. The full comparison checks admission of the coarse step and finite chemical affinity and heat at extreme concentration ratios. The second command runs the smaller-step controls. [Original result](PROGRESS.md#19-november-2026--potassium-and-anion-cotransport) · [Overflow repair and retest](PROGRESS.md#potassium-affinity-repair)

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
