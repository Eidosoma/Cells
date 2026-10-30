# Array interval accounting

New worker lane: `cells.numerics.physiology_protein_interval_arrays`, independent
reference and unit files only. Qualified host accounting and every prior source
stay frozen. Chief owns accepted transactions, post-ion protein work and loops.

`evaluate(before, after, runtime_layout, protein_charge_increment_C,
before_control, after_control, material_atol_fmol, *, implementation, xp=jnp)`
returns an array-only `ArrayIntervalAccounting` pytree with `valid`, `balances`,
`limits`, `checks`, `energy_terms`, `diagnostics` and `first_invalid_check`.
Implementation is static and restricted to the four exact ordinary families.
Dict keys and shapes are static for a family. External `jax.vmap` maps worlds;
one invocation accounts for one pair of complete numeric states.

`endpoint_values(state, control, runtime_layout, protein_charge_increment_C,
*, implementation, xp)` returns actual charged RHS/domain data plus complete
array snapshots of state/control/layout/charge. `evaluate` optionally takes
`before_endpoint` and `after_endpoint` together. It checks exact association,
retains actual potential_V, rechecks current domains and capacitor charge
closure, verifies Vm=phi_cell-phi_out and held reservoir potentials with zero
algebraic mismatch tolerance, and requires actual rate validity. Provider
records are numerical provenance, not authentication;
the frozen high-precision host still owns acceptance. NumPy snapshots do not
alias the caller's mutable buffers. Default evaluation computes both providers.

Compiled scope is one shared original geometry/anchor recipe, with dynamic
per-world states, current P, protein charge, controls and material tolerance.
Three preserved attempts exceeded the1GiB compiler limit for monolithic full
RHS+accounting graphs (including shared geometry). Qualification therefore
separates actual CPU JAX endpoint array operations and compiled/vmapped
accounting from their associated records. No monolithic RHS JIT, GPU runtime or
performance credit is claimed. Actual endpoint solves/gates remain mandatory.

The caller admits source/binding/protein provenance and unchanged original
anchors before entering this port. The runtime layout changes current passive
P only, and the explicit projected protein charge is held at both endpoints.
Original numeric layout/anchors remain owned by the controller. No spec parsing,
Decimal, host array conversion, random draw, checkpoint I/O or time advance
belongs in this path. Frozen host accounting remains authoritative admission.

The chemical functional and ownership match host accounting. Preserve the
separate original anchor and before increment with compensated sums. Compute
the starting logarithm from compensated owner stock and the fixed volume/c0;
near equality use a scaled product remainder and log1p. For small r=dN/N use

    DeltaG = 1e-3 RT [dN mu_before + (dN*dN/N) H(r)]
    H(r) = 1/2 - r/6 + r*r/12 - ... .

Exponent-scaled products avoid losing the quadratic contribution by forming
r*r first, or by converting an intermediate amount before energy scaling.
Larger changes use the algebraically equivalent high/low endpoint expression.
Keep raw underflow/overflow and rounding diagnostics. Array validity is
conservative: insufficient precision/unrepresentable results may be refused
even when high-precision host arithmetic could resolve them. Error bounds
consume the original budget; they never enlarge it or reset a residual.
Changed stocks whose nonzero linear/quadratic pieces cancel to rounded zero
are explicitly ambiguous and invalid. No physical zero is inferred from them.

Plasma capacitor change uses original charge-only ionic increments and the
actual held-charge starting Vm. ER uses original store anchors. Calcium's full
store chemical functional replaces the intracellular exchange-ledger energy.
Finite-fuel ATP standards occur once; pump work stays internal and each pool
keeps its own transfer balance. All external work and actual heat histories
are differenced directly. Protein free energy is constant in this interval.

Port all original non-overall-energy checks with xp operations: endpoint and
interval material/electrode/global charge, store reaction/transfer ownership,
maintained-drive or finite-pool work identities, actual charged field/rate
domains, padding, and nonnegative/nondecreasing heat. Energy limits remain
2e-8pJ passive/ionic and1e-9pJ calcium/fuel (including individual fuel pools).

Chief subsequently forwarded user authorization for bounded CPU7 NumPy/JAX
qualification:480s per phase,1GiB process-tree RSS,8GiB host reserve, private
source captures under /mnt/workspaces/Cells. GPU runs remain deferred. Prepare
NumPy/JAX parity, compiled/vmapped CPU cases, corrupt-ledger and precision-gap
refusal, tiny/zero/extreme products, independent high-precision comparisons and
fresh Cells/JAX-denied reference execution. No broad regression campaign.

The final source has51 positive checks:47 NumPy, compiled chemical primitive,
and two-world compiled accounting for passive, ionic and calcium. Fresh
denied-production execution covers27 interval and11 primitive cases. The
final-source fuel compilation is unqualified under the1GiB high-water cap;
its actual CPU JAX endpoint preparation completed, but accounting did not
return a qualified result. NumPy fuel checks pass. No further fuel retry is
queued. The -08 receipt seals retained -07 results plus fresh calcium on the
same snapshot; -06's49 passes belong to its older source and remain separate.
