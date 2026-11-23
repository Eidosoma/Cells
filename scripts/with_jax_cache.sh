#!/bin/bash
# Run one command with this VM's shared CPU compilation cache (D321, step 1): the environment of
# scripts/jax_cache.py env (the machine's folder, every compile written, the CPU only), for this
# command alone. It is never exported into a shell, so nothing ambient can reach a judged step run
# from the same shell, nor a gate or a tier measurement (they disable the cache themselves anyway).
# For a detached unit use scripts/run_detached.sh --jax-cache instead.
#
# Refused when a GPU is visible (CUDA_VISIBLE_DEVICES set, or JAX_PLATFORMS other than cpu): the
# L4's recorded bitwise failure (8 November 2026) was executables crossing processes through this
# cache. The command runs with JAX_PLATFORMS=cpu, so an engine run that asks for a GPU is refused.
# One exception until the routine fix to configure_caches() lands (D321, branch
# speedup-r4-configure-caches): `cells ensemble`'s GPU workers set their own device visibility and
# would inherit this cache. Run no `cells ensemble` under this wrapper before that fix is on main.
#
# Usage: scripts/with_jax_cache.sh COMMAND [ARGS...]
set -euo pipefail
[ $# -gt 0 ] || { echo "usage: with_jax_cache.sh COMMAND [ARGS...]" >&2; exit 2; }
if [ -n "${CUDA_VISIBLE_DEVICES:-}" ] || { [ -n "${JAX_PLATFORMS:-}" ] && [ "${JAX_PLATFORMS}" != cpu ]; }; then
  echo "with_jax_cache.sh: refused: a GPU may be visible (CUDA_VISIBLE_DEVICES='${CUDA_VISIBLE_DEVICES:-}'," \
    "JAX_PLATFORMS='${JAX_PLATFORMS:-}'); the shared cache is CPU-only" >&2
  exit 2
fi
lines=$(python3 -I "$(cd "$(dirname "$0")" && pwd)/jax_cache.py" env)
while IFS= read -r line; do export "${line?}"; done <<< "$lines"
mkdir -p "$JAX_COMPILATION_CACHE_DIR"
exec "$@"
