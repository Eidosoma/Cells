# Cells proofs

This Lean library organizes results by biological mechanism. The index connects each mathematical claim to the Cells law or model that uses it and the numerical check that exercises that use. Add a model-specific theorem when a model composes mechanisms or introduces another assumption.

## Proof index

| Lean theorems | Claim and assumptions | Cells use and numerical comparison |
| --- | --- | --- |
| `Transport.flux_reverse`, `flux_zero_voltage`, `flux_down_gradient`, `flux_blocked` | Reversing endpoints and voltage reverses the signed flux. At equal potentials the flux is the effective scale times the concentration difference. A positive scale moves ions down that gradient. A zero scale blocks the route. The four theorems apply to the analytic Bernoulli factor and the engine’s piecewise formula over the reals. [Transport proofs](CellsProofs/Transport/ConstantField.lean) | `constant_field@1` on the junctions of `resolved_pump_tissue@3`. The scale is area × permeability × opening divided by mol/fmol, and the voltage factor is zF/(RT). The checks use admitted concentrations, temperature, gates and voltages. [Flux kernel](../src/cells/laws/junctions/selective.py#L19) · [Surface comparisons](../tests/unit/test_surface_transport.py#L102) |
| `Accounting.nodeChange_reorient`, `region_balance`, `total_balance`, `charge_balance` | On a finite graph, reversing any subset of edges and their signed fluxes preserves every node’s credit or debit. Within any region, internal edges cancel and crossing edges contribute their signed flux. The whole graph conserves each species and any charge-weighted sum. Multiple edges can share an owner. [Accounting proofs](CellsProofs/Accounting/Transfer.lean) | The inner model assigns each junction flux to its two cells. The integrated potassium ledger also includes membrane, pump and channel contributions. A held bath exchanges material through a separate supply term. [Owner updates](../src/cells/numerics/surface_transport.py#L316) · [Tissue ledger](../tests/unit/test_surface_pump_v3_imex.py#L80) |

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
  Mathlib.Algebra.BigOperators.Ring.Finset Mathlib.Data.Real.Basic
lake build
```

## CPU comparison

The driver checks the same flux against an independent scalar reference, reverses the endpoint bookings as a negative control, and runs the existing closed `resolved_pump_tissue@3` world through its normal CPU runner. It applies the existing per-cell potassium ledger check to that one world. The component tests additionally cover route reversal, multiple patches, blocking and padding. [Pilot driver](checks/constant_field.py) · [Independent reference](../validation/tissue/surface_reference.py#L71)

```bash
mkdir -p .lake/tmp .lake/cache
export TMPDIR="$PWD/.lake/tmp" XDG_CACHE_HOME="$PWD/.lake/cache"
export PYTHONPATH="../src:.." PYTHONDONTWRITEBYTECODE=1
export JAX_PLATFORMS=cpu JAX_ENABLE_X64=1 JAX_ENABLE_COMPILATION_CACHE=0
cells_python=${CELLS_PYTHON:-/mnt/workspaces/Cells/venv-cpu/bin/python}
"$cells_python" -B checks/constant_field.py
"$cells_python" -B -m pytest -q -p no:cacheprovider \
  ../tests/unit/test_surface_transport.py::test_independent_surface_laws_and_accounting \
  ../tests/unit/test_surface_transport.py::test_patch_subdivision_route_reversal_and_padding \
  ../tests/unit/test_surface_transport.py::test_equilibrium_and_transport_blocking
```

On 19 November 2026 the development comparison used engine revision `109a7355ed85`, CPU float64 and four CPU cores. The driver took 18.79 s, including the integrated world. The 11 component tests passed in 9.46 s. The largest per-cell rate difference from the reference was 1.36 × 10⁻²⁰ fmol/s against a tolerance of 3 × 10⁻¹⁴. Swapping the owners gave a 2.40 × 10⁻⁴ fmol/s discrepancy. The tissue’s potassium transfer reached 2.18 × 10⁻⁶ fmol and its maximum global material residual was 3.25 × 10⁻¹⁹ fmol. This was a working-checkout comparison. Registered runs use the project’s existing frozen-snapshot procedure.
