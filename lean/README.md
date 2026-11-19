# Cells proofs

This Lean library organizes results by biological mechanism. The index connects each mathematical claim to the Cells law or model that uses it and the numerical check that exercises that use. Add a model-specific theorem when a model composes mechanisms or introduces another assumption.

## Proof index

| Lean theorems | Claim and assumptions | Cells use and numerical comparison |
| --- | --- | --- |
| `Transport.flux_reverse`, `flux_zero_voltage`, `flux_down_gradient`, `flux_blocked` | Reversing endpoints and voltage reverses the signed flux. At equal potentials the flux is the effective scale times the concentration difference. A positive scale moves ions down that gradient. A zero scale blocks the route. The four theorems apply to the analytic Bernoulli factor and the engine’s piecewise formula over the reals. [Transport proofs](CellsProofs/Transport/ConstantField.lean) | `constant_field@1` on the junctions of `resolved_pump_tissue@3`. The scale is area × permeability × opening divided by mol/fmol, and the voltage factor is zF/(RT). The checks use admitted concentrations, temperature, gates and voltages. [Flux kernel](../src/cells/laws/junctions/selective.py#L19) · [Surface comparisons](../tests/unit/test_surface_transport.py#L102) |
| `Accounting.nodeChange_reorient`, `region_balance`, `total_balance`, `charge_balance` | On a finite graph, reversing any subset of edges and their signed fluxes preserves every node’s credit or debit. Within any region, internal edges cancel and crossing edges contribute their signed flux. The whole graph conserves each species and any charge-weighted sum. Multiple edges can share an owner. [Accounting proofs](CellsProofs/Accounting/Transfer.lean) | The inner model assigns each junction flux to its two cells. The integrated potassium ledger also includes membrane, pump and channel contributions. A held bath exchanges material through a separate supply term. [Owner updates](../src/cells/numerics/surface_transport.py#L316) · [Tissue ledger](../tests/unit/test_surface_pump_v3_imex.py#L80) |
| `Chemistry.inventory_after_reactions` | For a finite network at one site, an integer-weighted inventory is preserved if it balances in every reaction. Reaction extents can be any signed real amounts. [General theorem](CellsProofs/Chemistry/Stoichiometry.lean) | `local_species_reactions@1` on `resolved_pump_composite@1` forms each species change from signed stoichiometric coefficients and extents. [Admission](../src/cells/operators/species_reactions.py#L431) · [Half-step](../src/cells/operators/species_reactions.py#L1024) |
| `Chemistry.Enzyme.enzyme_conserved`, `substrate_conserved`, `missing_enzyme_balance` | Binding and catalysis preserve E + C and S + C + P. Removing E from the catalytic products loses one enzyme unit per event while preserving the substrate count. [Enzyme proofs](CellsProofs/Chemistry/Enzyme.lean) | The comparison checks the fixture’s two columns and two weight rows in Lean. It checks the stored amounts after one compiled CPU half-step and the engine’s refusal of the altered reaction. [Fixture](../validation/tissue/species_reactions_fixtures.py#L248) · [Comparison](checks/closed_enzyme.py) |

The Lean namespaces above begin with `CellsProofs.`. The proofs use exact real arithmetic. A floating-point error bound for the near-zero series and the biological calibration of a given tissue remain separate questions. [Engine evaluator](../src/cells/laws/electrochemistry.py#L17) · [Research and design options](ENGINE_LAW_VERIFICATION.md)

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

Run these from `lean/` with the pinned Lake executable on your path. Both drivers print their numerical results as JSON. See the [development results](PROGRESS.md).

```bash
mkdir -p .lake/tmp .lake/cache
export TMPDIR="$PWD/.lake/tmp" XDG_CACHE_HOME="$PWD/.lake/cache"
export PYTHONPATH="../src:.." PYTHONDONTWRITEBYTECODE=1
export JAX_PLATFORMS=cpu JAX_ENABLE_X64=1 JAX_ENABLE_COMPILATION_CACHE=0
cells_python=${CELLS_PYTHON:-/mnt/workspaces/Cells/venv-cpu/bin/python}
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
