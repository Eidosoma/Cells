# Cells proofs

This Lean library organizes results by biological mechanism. Each claim links to its assumptions, named theorems, implementation and comparison record. Experimental evidence attaches to a measured quantity in a specified preparation.

## Proof index

<!-- generated: claims-index -->

| Claim | Lean proof | Numerical check | Biological evidence |
| --- | --- | --- | --- |
| [Reversing a junction reverses its flux](claims/junction-flux-reversal.md) | Proved | Checked | Open |
| [At equal voltage, junction flux follows the concentration gradient](claims/junction-concentration-gradient.md) | Proved | Checked | Open |
| [A blocked junction carries zero flux](claims/junction-blocking.md) | Proved | Checked | Open |
| [Passive neutral solute follows its concentration gradient](claims/neutral-permeation.md) | Proved | Checked | Open |
| [Voltage and free proton concentrations set the leak reversal](claims/proton-leak.md) | Proved | Checked | Open |
| [Extracellular face flux follows the electrochemical potential drop](claims/extracellular-face-direction.md) | Proved | Checked | Open |
| [Passive extracellular face transport dissipates energy](claims/extracellular-face-dissipation.md) | Proved | Checked | Open |
| [Edge orientation preserves each compartment’s transfer balance](claims/transfer-orientation.md) | Proved | Checked | Open |
| [Only boundary transfers change a region’s inventory during transport](claims/transfer-inventory.md) | Proved | Checked | Open |
| [Balanced reactions preserve a weighted inventory](claims/reaction-inventory.md) | Proved | Checked | Open |
| [Binding and catalysis conserve enzyme and substrate](claims/enzyme-inventories.md) | Proved | Checked | Open |
| [One-site binding follows the free ligand concentration](claims/single-site-binding.md) | Proved | Checked | Open |
| [Uncharged membrane insertion dissipates nonnegative capacitor heat](claims/membrane-insertion-heat.md) | Proved | Failed | Open |
| [Regional inventory changes by net boundary transfer across a split step](claims/regional-reaction-transport.md) | Proved | Checked | Open |
| [Membrane voltage in kidney epithelial cells under condition C3](claims/rptec-voltage-c3.md) | Open | Checked | Not assessable |

<!-- /generated -->

The proof, numerical and biological columns record independent results. A numerical check applies to the cases in its linked record. The coverage table shows which registered laws and operators have a theorem about their own behavior, and which appear in a comparison. An open biological entry names a potential measurement. The voltage pilot has a measured endpoint and a descriptive comparison with unresolved biological acceptance. [Engine law coverage](COVERAGE.md) · [Design notes](ENGINE_LAW_VERIFICATION.md) · [Voltage pilot closeout](../reports/BIO003_PILOT_CLOSEOUT.md)

## Maintaining the claims

Edit the claims register. A stable `id` gives each claim its note under `claims/`. In `formal.theorems`, map fully qualified Lean names to their source files. Use `uses` to link claims that build on earlier proofs. [Editable register](claims.json) · [JSON Schema](claims.schema.json)

In `formal.about`, list the canonical registry IDs whose law or operator property the theorem establishes. General composition and accounting theorems can leave this empty. In `numerical.comparisons`, list the comparison IDs for the claim. Each comparison names the models, laws and operators it exercised. For engine runs, `engine_revision` identifies the code that ran. The `record_revision` pins the comparison driver and the published result. For a reference calculation it also pins the implementation. File paths in the register start at the checkout root.

For biological evidence, record the observable and unit, the primary paper or dataset and its exact panel or table, preparation, fit and evaluation conditions, uncertainty and the recorded verdict. Reference calculations have their own implementation kind. Detailed run records and datasets stay with their owners.

The research agent collects candidate papers in `claims/incoming/`. The November review identifies what each assay measured, which claim it can address and what is needed for a quantitative comparison. Enter a biological verdict in the register when a comparison has a documented outcome. [Reviewed measurements and follow-up](PROGRESS.md#19-november-2026--biological-evidence-review)

A normal `lake build` checks that each named theorem exists in its declared module, then regenerates the index, claim notes and coverage table. With `CELLS_PYTHON` set to the Cells Python interpreter, the build also refreshes the registry inventory from the active checkout. A Lean-only build uses the last exported inventory. Commit the generated files alongside edits to the register. The documentation commands below run from `lean/`.

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

## CPU comparisons

Run these from `lean/` with the pinned Lake executable on your path. Use the Cells CPU Python environment, or set `CELLS_PYTHON` to its interpreter. Each driver prints its numerical results as JSON. See the [development results](PROGRESS.md).

```bash
mkdir -p .lake/tmp .lake/cache
export TMPDIR="$PWD/.lake/tmp" XDG_CACHE_HOME="$PWD/.lake/cache"
export PYTHONPATH="../src:.." PYTHONDONTWRITEBYTECODE=1
export JAX_PLATFORMS=cpu JAX_ENABLE_X64=1 JAX_ENABLE_COMPILATION_CACHE=0
cells_python=${CELLS_PYTHON:-python}
```

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

For junction transport, the driver compares fluxes with an independent scalar reference and runs the per-cell potassium ledger on one closed tissue world. Reversing the endpoint bookings tests the sensitivity of the per-cell comparison. [Junction driver](checks/constant_field.py) · [Independent reference](../validation/tissue/surface_reference.py#L71)

```bash
"$cells_python" -B checks/constant_field.py
"$cells_python" -B -m pytest -q -p no:cacheprovider \
  ../tests/unit/test_surface_transport.py::test_independent_surface_laws_and_accounting \
  ../tests/unit/test_surface_transport.py::test_patch_subdivision_route_reversal_and_padding \
  ../tests/unit/test_surface_transport.py::test_equilibrium_and_transport_blocking
```

For neutral permeation, compare the compiled inward flux and the final amounts in a closed tissue pair with the analytic solution. The unequal-volume case distinguishes amount from concentration. [Neutral driver](checks/neutral_permeation.py) · [Closed-pair reference](../validation/passive/passive_reference.py#L66)

```bash
"$cells_python" -B checks/neutral_permeation.py
```

For proton leak, check the reversal voltage, instantaneous heat, the small-voltage branch and the free H⁺ read in a buffered tissue cell. The driver also resolves the polynomial’s reversal ratio at 80-digit precision. [Proton driver](checks/proton_leak.py) · [Flux reference](../validation/betse/junction_transport/check.py#L10)

```bash
"$cells_python" -B checks/proton_leak.py
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

For the tissue balance, the driver follows A and B through one 50 ms composite step on twelve finite extracellular compartments. It compares the change in their stored amounts at nodes 2 through 5 with the signed transfers on the two boundary faces. Each species also has to account for its share of the local conversion. The same comparison runs on the full chain and with the largest boundary face reversed in the recorded transfers. The existing passive-chain test checks the trajectory against the independent split-step reference. [Regional driver](checks/regional_balance.py) · [Reference comparison](../tests/unit/test_species_reactions_composition.py#L84)

```bash
"$cells_python" -B checks/regional_balance.py
"$cells_python" -B -m pytest -q -p no:cacheprovider \
  '../tests/unit/test_species_reactions_composition.py::test_guard_2_linear_networks_on_the_chain_run_the_engine_orders_map[passive]'
```
