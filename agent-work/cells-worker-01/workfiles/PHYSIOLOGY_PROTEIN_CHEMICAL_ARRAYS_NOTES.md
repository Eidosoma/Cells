# Array ideal-protein chemical change

Worker owns new core/reference/unit files. All preceding modules stay frozen.
Chief owns repeated charged loops, cumulative work ledgers and persistence.
Bounded CPU7 qualification is authorized; no GPU or fuel interval retry.

`change(reference_protein, current_protein, cell_volume_m3,
environment_volume_m3, *, temperature_K, standard_concentration_mol_m3,
gas_constant_J_mol_K, xp=jnp)` takes complete float64 ProteinState arrays and
fixed positive m3 owner volumes in the same component-owner order. Temperature,
concentration standard and gas constant are explicit positive float64 scalars.
The caller admits physical geometry, matching owner identities and binding.
Membrane views are checked as state buffers but never counted as inventory.
Empty owner axes and actual zero concentrations are supported.

The optional Cells functional is G=RT sum V*C*(log(C/c0)-1), mu0=0. At C=0,
G=0 and mu=-infinity with explicit zero masks. No floor or stock/anchor change.
Use stable log ratios and increment/quadratic formulas for positive endpoints;
use the continuous endpoint functional when a stock is zero. Products are
scaled before float conversion, so small amounts can retain finite pJ energy.

Separate a common logarithm algebraically using a positive concentration pivot:

    DeltaG(c0) = DeltaG(pivot) + RT log(pivot/c0) * actual_net_amount_change.

The supplied c0 remains the chemical frame. This separation preserves real net
material error and does not set it to zero. Material changes use compensated
density differences, product remainders and normalized mantissa/exponent sums.
The original closed-material bound is3e-13*gross actual amount change, with
roundoff consuming that budget. Raw mol display underflow stays explicit; the
scaled representation retains the comparison without a stock-resolution grace.
The total chemical sum also retains a normalized energy representation, so a
subnormal common material term is added before the final pJ conversion. Only
error bounds round outward to a normal float when necessary; physical stocks
and energies never receive a floor. Returned owner arrays follow component
order; frozen host outputs follow physical tissue order and require the
binding's explicit permutation when comparing them.

Results distinguish chemical diagnostic validity, strict material conservation
and their conjunction for closed use. Nonconservative chemical diagnostics can
be reported. Underflow/overflow, ambiguous cancellation and unresolved precision
are explicit conservative refusals. Subnormal input buffers may be refused to
avoid backend-dependent flush behavior. Host thermodynamics remains the oracle
and admission owner; this array diagnostic does not establish full state/work
admission or representable absolute bulk endpoint energies.

Only ideal chemical endpoint change is computed. No capacitor/clamp terms,
heat, physical driving/noise law, attainable minimum, holding work or native
BETSE protein-energy law is inferred.

Qualified scope:35 NumPy checks, eight frozen-host owner/frame comparisons,
24 fresh independent SI reference cases (21 resolved, three explicit
refusals), and three CPU JAX checks including a compiled two-world batch with
zero/tiny closed transfers and empty/invalid owners. GPU is deferred. The
workqueue links the final receipt, exact sources, raw diagnostics and resource
measurements; no broad regression, fuel interval retry or loop job is queued.
