#!/usr/bin/env bash
# Check the optional ATOMS Lab import on the Cells Lean/Mathlib pin.
set -euo pipefail
cd "$(dirname "$0")/../.."

revision=de263eed945693058ef2b8a1fa56c2ec5642ea7a
upstream=https://raw.githubusercontent.com/ATOMSLab/LeanDimensionalAnalysis
source_dir="$PWD/.lake/atoms-units/$revision"
mkdir -p "$source_dir/DimensionalAnalysis"
build_dir=$(mktemp -d "$source_dir/build.XXXXXX")
trap 'rm -r -- "$build_dir"' EXIT
mkdir "$build_dir/DimensionalAnalysis"
for path in DimensionalAnalysis/Basic.lean DimensionalAnalysis/Dimensions.lean LICENSE; do
  if [[ ! -f "$source_dir/$path" ]]; then
    curl -fsSL --retry 2 "$upstream/$revision/$path" -o "$build_dir/download"
    mv "$build_dir/download" "$source_dir/$path"
  fi
done

if [[ ! -f .lake/packages/mathlib/.lake/build/lib/lean/Mathlib/Data/Matrix/Rank.olean ]]; then
  lake exe cache get Mathlib.Data.Matrix.Rank
fi
lake build CellsProofs.Transport.LogMeanFace CellsProofs.Tissue.CurrentInjection
lake_path=$(lake env printenv LEAN_PATH)
export LEAN_PATH="$build_dir:$lake_path"
# In Mathlib 4.19 the upstream matrix-rank module lived under Data.
sed '1s/Mathlib.LinearAlgebra.Matrix.Rank/Mathlib.Data.Matrix.Rank/' \
  "$source_dir/DimensionalAnalysis/Basic.lean" > "$build_dir/DimensionalAnalysis/Basic.lean"
lean --root="$build_dir" -DautoImplicit=false -o "$build_dir/DimensionalAnalysis/Basic.olean" \
  "$build_dir/DimensionalAnalysis/Basic.lean"
lean --root="$source_dir" -DautoImplicit=false -o "$build_dir/DimensionalAnalysis/Dimensions.olean" \
  "$source_dir/DimensionalAnalysis/Dimensions.lean"
lean -DautoImplicit=false -DwarningAsError=true checks/units/FacePower.lean
