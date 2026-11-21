#!/usr/bin/env bash
# Check three pinned chemistry modules against the Cells toolchain.
set -euo pipefail
cd "$(dirname "$0")/../.."

cache="$PWD/.lake/chemistry-imports"
mkdir -p "$cache"
build=$(mktemp -d "$cache/build.XXXXXX")
trap 'rm -r -- "$build"' EXIT
lake build +CellsProofs.Chemistry.Enzyme +CellsProofs.Chemistry.AssemblyKinetics \
  +Mathlib.Algebra.Order.BigOperators.Ring.Finset +Mathlib.Data.Finsupp.Basic \
  +Mathlib.Data.NNReal.Basic +Mathlib.Tactic.GCongr +Mathlib.Tactic.NormNum
lake_path=$(lake env printenv LEAN_PATH)
export LEAN_PATH="$build:$lake_path"

check_modules() {
  local repo=$1 revision=$2
  shift 2
  local source="$cache/$repo/$revision" path
  local -a options
  for path in LICENSE "$@"; do
    if [[ ! -f "$source/$path" ]]; then
      mkdir -p "$(dirname "$source/$path")"
      curl -fsSL --retry 2 "https://raw.githubusercontent.com/$repo/$revision/$path" -o "$build/download"
      mv -- "$build/download" "$source/$path"
    fi
    [[ "$path" == *.lean ]] || continue
    mkdir -p "$(dirname "$build/$path")"
    options=()
    case "$path" in
      CRNT/Kinetics/Concentration.lean)
        # Finite-product positivity lived in Ring.Finset on Mathlib 4.19.
        sed 's/^import Mathlib.Algebra.Order.BigOperators.GroupWithZero.Finset$/import Mathlib.Algebra.Order.BigOperators.Ring.Finset/' \
          "$source/$path" > "$build/$path" ;;
      CRNT/Examples/Enzyme.lean)
        # This elaborator option was introduced after Lean 4.19.
        sed '/^set_option backward.isDefEq.respectTransparency false$/d' "$source/$path" > "$build/$path" ;;
      Pythia/Frontier/Chemistry/Eyring.lean)
        sed '/^import Mathlib$/c\
import Mathlib.Data.Complex.Exponential\
import Mathlib.Tactic.GCongr\
import Mathlib.Tactic.Positivity' "$source/$path" > "$build/$path"
        options=(-Dlinter.unusedVariables=false) ;;
      Biosim/Proofs/Invariants.lean)
        cp -- "$source/$path" "$build/$path"
        options=(-Dlinter.unusedSectionVars=false) ;;
      *) cp -- "$source/$path" "$build/$path" ;;
    esac
    lean --root="$build" -DwarningAsError=true "${options[@]}" \
      -o "$build/${path%.lean}.olean" "$build/$path"
  done
}

check_modules marpaia/crnt-lean 7386777488a41efd92e6abc2bccf889fb611660e \
  CRNT/Basic/{Complex,Reaction,Network}.lean CRNT/Stoich/Vector.lean \
  CRNT/Kinetics/{Concentration,MassAction}.lean CRNT/Examples/Enzyme.lean
check_modules OmnisGenomics/VeriBiota a145b640d7d8009a5a653849c41ef9a1d6b1c176 \
  NOTICE Biosim/Core/{Species,State,Stoich,Reaction,System}.lean Biosim/Proofs/Invariants.lean
check_modules athanor-ai/pythia 65404339b5c6fe8004d91fdd9c0c14ceb0bf7cd3 \
  Pythia/Frontier/Chemistry/Eyring.lean

lean -DautoImplicit=false -DwarningAsError=true checks/chemistry/Reuse.lean
