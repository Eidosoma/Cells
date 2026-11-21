#!/usr/bin/env bash
# Recheck two MIT-licensed scalar proofs on the Cells Lean pin.
set -euo pipefail
cd "$(dirname "$0")/../.."

rev=070ba8da6a09bdc4b0550396c61611668768bc0b
source_dir="$PWD/.lake/grn-hill/$rev"
mkdir -p "$source_dir/GRN/Dynamics"
build_dir=$(mktemp -d "$source_dir/build.XXXXXX")
trap 'rm -r -- "$build_dir"' EXIT
for path in LICENSE GRN/Dynamics/VectorField.lean GRN/Dynamics/Sensor.lean; do
  if [[ ! -f "$source_dir/$path" ]]; then
    curl -fsSL --retry 2 "https://raw.githubusercontent.com/marpaia/grn-lean/$rev/$path" -o "$build_dir/download"
    mv "$build_dir/download" "$source_dir/$path"
  fi
done
if [[ ! -f .lake/packages/mathlib/.lake/build/lib/lean/Mathlib/Analysis/SpecialFunctions/Pow/Real.olean ]]; then
  lake exe cache get Mathlib.Analysis.SpecialFunctions.Pow.Real
fi
lake build CellsProofs.Transport.RegulatedAvailability

# The pinned Hill definition and two proof bodies use real powers and linear arithmetic.
{
  printf '%s\n' 'import Mathlib.Analysis.SpecialFunctions.Pow.Real' 'import Mathlib.Tactic.Linarith' \
    'open Real Set' 'namespace GRN.Dynamics'
  sed -n '36,37p' "$source_dir/GRN/Dynamics/VectorField.lean"
  sed -n '27p;30,48p;51,69p' "$source_dir/GRN/Dynamics/Sensor.lean"
  printf '%s\n' 'end GRN.Dynamics'
} > "$build_dir/HillSelection.lean"
lake_path=$(lake env printenv LEAN_PATH)
export LEAN_PATH="$build_dir:$lake_path"
lean --root="$build_dir" -DautoImplicit=false -DwarningAsError=true \
  -o "$build_dir/HillSelection.olean" "$build_dir/HillSelection.lean"
lean -DautoImplicit=false -DwarningAsError=true checks/hill/Response.lean
