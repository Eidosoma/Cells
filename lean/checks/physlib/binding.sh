#!/usr/bin/env bash
# Use the same Physlib checkout and toolchain as the two-state gate check.
set -euo pipefail
cells=$(cd "$(dirname "$0")/../.." && pwd)
cd "${1:-$cells/.lake/physlib-v4.22.0}"
revision=559b0e14bd87896d4ee536a536a8fb65e83b77cc
if [[ $(git rev-parse HEAD) != "$revision" ]]; then
  echo "This comparison uses Physlib v4.22.0 at $revision." >&2
  exit 1
fi
lake build PhysLean.StatisticalMechanics.CanonicalEnsemble.Finite
build=$(mktemp -d "$cells/.lake/binding-ensemble.XXXXXX")
trap 'rm -r -- "$build"' EXIT
mkdir -p "$build/CellsProofs/Chemistry"
lake_path=$(lake env printenv LEAN_PATH)
export LEAN_PATH="$build:$lake_path"
lean --root="$cells" -DwarningAsError=true -o "$build/CellsProofs/Chemistry/BindingEnsemble.olean" \
  "$cells/CellsProofs/Chemistry/BindingEnsemble.lean"
lean -DwarningAsError=true "$cells/checks/physlib/BindingEnsemble.lean"
