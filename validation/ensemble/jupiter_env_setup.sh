#!/usr/bin/env bash
# Create or update the Cells GPU Python environment (JUPITER GH200/aarch64 or a local GPU host).
#
#   validation/ensemble/jupiter_env_setup.sh VENV_DIR [RECORD_JSON]
#   validation/ensemble/jupiter_env_setup.sh --download WHEEL_DIR
#
# The pins below are the L4 environment (venv-gpu) used for local qualification:
# Python 3.13, jax/jaxlib 0.11.1 with the CUDA 13 plugin and NVIDIA's pip CUDA
# libraries. All have linux aarch64 wheels on PyPI; nothing is built from source.
# Re-running with an existing VENV_DIR changes nothing when the pins are already
# installed. Each run rewrites RECORD_JSON (default VENV_DIR/cells-env.json) with
# the installed versions, interpreter, modules and checkout revision.
#
# Environment:
#   CELLS_MODULES      modules to load first (default "Stages/2026 GCC Python";
#                      "none" skips the module system, e.g. on the local host)
#   CELLS_BASE_PYTHON  interpreter used to create the venv (default python3)
#   CELLS_WHEELHOUSE   install only from this directory (offline nodes)
#   CELLS_ALLOW_ARCH   set to 1 to allow a non-aarch64 host
# --download fills WHEEL_DIR with the aarch64 cp313 wheels on any online host.
set -euo pipefail

usage() {
    sed -n '2,6p' "$0" >&2
    exit 2
}

pins() {
    cat <<'PINS'
jax==0.11.1
jaxlib==0.11.1
jax-cuda13-plugin==0.11.1
jax-cuda13-pjrt==0.11.1
numpy==2.5.3
ml_dtypes==0.6.0
opt_einsum==3.4.0
scipy==1.18.1
nvidia-cublas==13.8.0.4
nvidia-cuda-cccl==13.3.4.3.1
nvidia-cuda-crt==13.4.92
nvidia-cuda-cupti==13.4.92
nvidia-cuda-nvcc==13.4.92
nvidia-cuda-nvrtc==13.4.92
nvidia-cuda-runtime==13.4.92
nvidia-cudnn-cu13==9.26.0.51
nvidia-cufft==12.4.0.43
nvidia-cusolver==12.3.4.7
nvidia-cusparse==12.8.6.72
nvidia-nccl-cu13==2.31.2
nvidia-nvjitlink==13.4.92
nvidia-nvshmem-cu13==3.7.2
nvidia-nvvm==13.4.92
pytest==9.1.1
iniconfig==2.3.0
packaging==26.3
pluggy==1.6.0
Pygments==2.21.0
PINS
}

[[ $# -ge 1 ]] || usage
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
checkout="$(cd "$here/../.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
pins > "$work/pins.txt"

if [[ "$1" == --download ]]; then
    [[ $# -eq 2 ]] || usage
    mkdir -p "$2"
    platforms=()
    for tag in manylinux_2_28 manylinux_2_27 manylinux_2_25 manylinux_2_18 manylinux_2_17 \
        manylinux2014; do
        platforms+=(--platform "${tag}_aarch64")
    done
    "${CELLS_BASE_PYTHON:-python3}" -m pip download --no-cache-dir --only-binary=:all: \
        --no-deps --implementation cp --python-version 3.13 --abi cp313 --abi abi3 --abi none \
        "${platforms[@]}" --dest "$2" -r "$work/pins.txt"
    echo "Wheels for linux aarch64 cp313 are in $2"
    exit 0
fi

[[ $# -le 2 ]] || usage
venv="$(mkdir -p "$1" && cd "$1" && pwd)"
record="${2:-$venv/cells-env.json}"

modules="${CELLS_MODULES:-Stages/2026 GCC Python}"
if [[ "$modules" != none ]]; then
    set +u
    if ! type module > /dev/null 2>&1; then
        for init in "${LMOD_PKG:-/usr/share/lmod/lmod}/init/bash" /etc/profile.d/lmod.sh; do
            if [[ -r "$init" ]]; then
                # shellcheck disable=SC1090
                source "$init"
                break
            fi
        done
    fi
    if ! type module > /dev/null 2>&1; then
        echo "No module command; set CELLS_MODULES=none to use the PATH python3" >&2
        exit 1
    fi
    module --force purge
    # shellcheck disable=SC2086
    module load $modules
    set -u
fi

machine="$(uname -m)"
if [[ "$machine" != aarch64 && "${CELLS_ALLOW_ARCH:-0}" != 1 ]]; then
    echo "This host is $machine; JUPITER GH200 nodes are aarch64 (CELLS_ALLOW_ARCH=1 overrides)" >&2
    exit 1
fi
if [[ "${LD_LIBRARY_PATH:-}" =~ [Cc][Uu][Dd][Aa]|cudnn|nccl ]]; then
    echo "Warning: LD_LIBRARY_PATH names CUDA libraries; do not load the CUDA module" >&2
fi

if [[ ! -x "$venv/bin/python" ]]; then
    base="${CELLS_BASE_PYTHON:-python3}"
    "$base" -c 'import sys; assert sys.version_info[:2] == (3, 13), sys.version' || {
        echo "Need Python 3.13 to create the venv (found $("$base" -V 2>&1))" >&2
        exit 1
    }
    "$base" -m venv "$venv"
fi
python="$venv/bin/python"
"$python" -c 'import sys; assert sys.version_info[:2] == (3, 13), sys.version'

source=(--only-binary=:all:)
if [[ -n "${CELLS_WHEELHOUSE:-}" ]]; then
    source+=(--no-index --find-links "$CELLS_WHEELHOUSE")
fi
PIP_DISABLE_PIP_VERSION_CHECK=1 "$python" -m pip install --require-virtualenv --no-cache-dir \
    "${source[@]}" -r "$work/pins.txt"
PIP_DISABLE_PIP_VERSION_CHECK=1 "$python" -m pip check

revision="$(git -C "$checkout" rev-parse HEAD 2> /dev/null || true)"
dirty="$(git -C "$checkout" status --porcelain --untracked-files=all 2> /dev/null | head -c 1 || true)"
CELLS_RECORD="$record.tmp" CELLS_PINS="$work/pins.txt" CELLS_REVISION="$revision" \
    CELLS_DIRTY="${dirty:+true}" CELLS_MODULE_LIST="$modules" "$python" - << 'PY'
import json, os, platform, sys
from datetime import UTC, datetime
from importlib import metadata

installed = {
    (d.metadata["Name"] or "").lower().replace("_", "-"): d.version for d in metadata.distributions()
}
pins = {}
for line in open(os.environ["CELLS_PINS"]):
    name, version = line.strip().split("==")
    pins[name.lower().replace("_", "-")] = version
record = {
    "kind": "cells.gpu_environment@1",
    "written_utc": datetime.now(UTC).isoformat(),
    "venv": sys.prefix,
    "python": sys.version,
    "base_executable": getattr(sys, "_base_executable", None),
    "machine": platform.machine(),
    "platform": platform.platform(),
    "libc": "-".join(platform.libc_ver()),
    "modules_requested": os.environ["CELLS_MODULE_LIST"],
    "modules_loaded": os.environ.get("LOADEDMODULES"),
    "wheelhouse": os.environ.get("CELLS_WHEELHOUSE") or None,
    "checkout_revision": os.environ["CELLS_REVISION"] or None,
    "checkout_dirty": bool(os.environ["CELLS_DIRTY"]) if os.environ["CELLS_REVISION"] else None,
    "pins": pins,
    "pins_satisfied": all(installed.get(k) == v for k, v in pins.items()),
    "installed": dict(sorted(installed.items())),
}
with open(os.environ["CELLS_RECORD"], "w") as stream:
    json.dump(record, stream, indent=2, sort_keys=True)
    stream.write("\n")
if not record["pins_satisfied"]:
    sys.exit("Installed versions differ from the pins")
PY
mv "$record.tmp" "$record"
echo "Environment ready: $python"
echo "Record: $record"
