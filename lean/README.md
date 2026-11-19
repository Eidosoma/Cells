# Cells proofs

This Lean library organizes results by biological mechanism. Each claim links to its assumptions, named theorems, implementation and comparison record. Experimental evidence attaches to a measured quantity in a specified preparation.

## Proof index

<!-- generated: claims-index -->

| Claim | Lean proof | Numerical check | Biological evidence |
| --- | --- | --- | --- |
| [Reversing a junction reverses its flux](claims/junction-flux-reversal.md) | Proved | Checked | Open |
| [At equal voltage, junction flux follows the concentration gradient](claims/junction-concentration-gradient.md) | Proved | Checked | Open |
| [A blocked junction carries zero flux](claims/junction-blocking.md) | Proved | Checked | Open |
| [Edge orientation preserves each compartment’s transfer balance](claims/transfer-orientation.md) | Proved | Checked | Open |
| [Only boundary transfers change a region’s inventory during transport](claims/transfer-inventory.md) | Proved | Checked | Open |
| [Balanced reactions preserve a weighted inventory](claims/reaction-inventory.md) | Proved | Checked | Open |
| [Binding and catalysis conserve enzyme and substrate](claims/enzyme-inventories.md) | Proved | Checked | Open |
| [Regional inventory changes by net boundary transfer across a split step](claims/regional-reaction-transport.md) | Proved | Checked | Open |
| [Membrane voltage in kidney epithelial cells under condition C3](claims/rptec-voltage-c3.md) | Open | Checked | Not assessable |

<!-- /generated -->

The proof, numerical and biological columns record independent results. A numerical check applies to the cases in its linked record. An open biological entry names a potential measurement. The voltage pilot has a measured endpoint and a descriptive comparison with unresolved biological acceptance. [Design notes](ENGINE_LAW_VERIFICATION.md) · [Voltage pilot closeout](../reports/BIO003_PILOT_CLOSEOUT.md)

## Maintaining the claims

Edit the claims register. A stable `id` gives each claim its note under `claims/`. In `formal.theorems`, map fully qualified Lean names to their source files. Use `uses` to link claims that build on earlier proofs. [Editable register](claims.json) · [JSON Schema](claims.schema.json)

In `numerical.comparisons`, list the comparison IDs for the claim. Each comparison names the model and laws it exercised. For engine runs, `engine_revision` identifies the code that ran. The `record_revision` pins the comparison driver and the published result. For a reference calculation it also pins the implementation. File paths in the register start at the checkout root.

For biological evidence, record the observable and unit, the primary paper or dataset and its exact panel or table, preparation, fit and evaluation conditions, uncertainty and the recorded verdict. Reference calculations have their own implementation kind. Detailed run records and datasets stay with their owners.

A normal `lake build` checks that each named theorem exists in its declared module, then regenerates the index and notes. Commit the generated Markdown alongside changes to the register. For documentation alone, use Python 3 from `lean/`. The check command reports missing, edited or obsolete generated pages and exits unsuccessfully if any differ.

```bash
python3 scripts/generate_claims.py
python3 scripts/generate_claims.py --check
```

These queries list claims with held-out measurements and claims whose comparison exercised a given law.

```bash
jq -r '.claims[] | select(any(.biology.evidence[]; .role == "held_out_from_fitting")) | .id' claims.json
jq -r --arg law 'local_species_reactions@1' '
  .comparisons as $checks | .claims[]
  | select(any(.numerical.comparisons[]; $checks[.].laws | index($law))) | .id' claims.json
```

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
  Mathlib.Algebra.BigOperators.Group.Finset.Piecewise \
  Mathlib.Algebra.BigOperators.Group.Finset.Sigma \
  Mathlib.Algebra.BigOperators.Ring.Finset Mathlib.Data.Real.Basic Mathlib.Tactic.DeriveFintype
lake build
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

For junction transport, the driver compares fluxes with an independent scalar reference and runs the per-cell potassium ledger on one closed tissue world. Reversing the endpoint bookings tests the sensitivity of the per-cell comparison. [Junction driver](checks/constant_field.py) · [Independent reference](../validation/tissue/surface_reference.py#L71)

```bash
"$cells_python" -B checks/constant_field.py
"$cells_python" -B -m pytest -q -p no:cacheprovider \
  ../tests/unit/test_surface_transport.py::test_independent_surface_laws_and_accounting \
  ../tests/unit/test_surface_transport.py::test_patch_subdivision_route_reversal_and_padding \
  ../tests/unit/test_surface_transport.py::test_equilibrium_and_transport_blocking
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
