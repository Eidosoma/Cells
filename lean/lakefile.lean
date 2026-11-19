import Lake

open Lake DSL

package cells_proofs where
  version := v!"0.1.0"
  leanOptions := #[⟨`autoImplicit, false⟩, ⟨`warningAsError, true⟩]

require mathlib from git "https://github.com/leanprover-community/mathlib4.git"@"v4.19.0"

@[default_target] lean_lib CellsProofs

@[default_target]
target claimDocs pkg : Unit := do
  let some lib := pkg.findLeanLib? `CellsProofs | error "missing CellsProofs library"
  let proofs ← lib.leanArts.fetch
  let lean ← getLean
  let env ← getAugmentedEnv
  proofs.mapM fun _ => do
    proc {cmd := lean.toString, args := #["-DwarningAsError=true", "scripts/CheckClaims.lean"],
          env, cwd := pkg.dir}
    let python ← IO.getEnv "CELLS_PYTHON"
    let args := #["-B", "scripts/generate_claims.py"]
    proc {cmd := python.getD "python3", args := if python.isSome then args.push "--live-registry"
          else args, cwd := pkg.dir}
