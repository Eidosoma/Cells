#!/bin/bash
# Chrome for the visualizer's browser runs: on the machine's graphics card while the engine is
# not using it, on the software renderer otherwise. The check tools start whatever CHROME
# names, so a run opts in with
#
#   CHROME=$PWD/tools/chrome_gpu.sh node tools/check_all.mjs ...
#
# and no tool changes. The user, 16 November 2026: "can you speed up some of your things if
# you use it while lead is not using it?" and "so lets go for it and use it".
#
# The engine's work comes first, by the rule its lead gave the same evening:
#   - every engine job on the card takes /mnt/workspaces/Cells/locks/gpu.lock exclusively;
#     a browser here takes the same lock shared, for as long as it lives, so several browsers
#     run at once, an engine job waits for them to end, and none starts while a job holds it;
#   - while /mnt/workspaces/Cells/locks/gpu.reserved exists, nothing new starts on the card;
#   - and, as a second guard, nothing starts while another compute process is on the card.
# In each of those cases, and where the card cannot be asked, this starts Chrome exactly as
# it was asked to (the tools ask for the software renderer).
#
# The lock is held on a file descriptor that Chrome inherits, and this shell replaces itself
# with Chrome (exec): the tool that started it stops Chrome itself, not a shell in front of
# it, and the lock ends when the browser does.
REAL="${CELLS_CHROME_REAL:-google-chrome}"
LOCK="${CELLS_GPU_LOCK:-/mnt/workspaces/Cells/locks/gpu.lock}"
FLAG="${CELLS_GPU_RESERVED:-/mnt/workspaces/Cells/locks/gpu.reserved}"
# Which of ANGLE's back ends draws on the card: vulkan (the default) or egl. Through its
# OpenGL back end (egl) this machine's card now and then drew a wrong picture of a still
# page: after a frame with bloom, 18 of 40 pictures had holes where small solid parts are,
# though what the frame draws on the way (the solids' facing, the shade) was the same to
# the last count. Through Vulkan 40 of 40 were the picture at rest, as in software
# (16 November 2026). So the fault is that back end's here, not the page's, and a check
# that compares pictures is not run through it.
WAY="${CELLS_GPU_WAY:-vulkan}"

mode=software
why=""
if [ "${CELLS_GPU:-auto}" = "off" ]; then
  why="switched off (CELLS_GPU=off)"
elif [ -e "$FLAG" ]; then
  why="the card is reserved ($FLAG exists)"
elif ! others=$(nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader 2>/dev/null); then
  why="the card could not be asked (nvidia-smi failed)"
elif [ -n "$(printf '%s\n' "$others" | grep -v -i 'chrome' | grep .)" ]; then
  why="another process is on the card: $(printf '%s' "$others" | grep -v -i 'chrome' | head -1)"
elif ! exec 9<"$LOCK"; then
  why="the card's lock file cannot be opened ($LOCK)"
elif ! flock -s -n 9; then
  why="an engine job holds the card's lock"
  exec 9<&-
else
  mode=card
fi

args=()
if [ "$mode" = "card" ]; then
  for arg in "$@"; do
    case "$arg" in
      --use-angle=*|--enable-unsafe-swiftshader|--use-gl=*|--disable-gpu) ;;   # the software renderer's flags
      *) args+=("$arg") ;;
    esac
  done
  if [ "$WAY" = "egl" ]; then
    args=("--use-gl=angle" "--use-angle=gl-egl" "--enable-gpu" "--ignore-gpu-blocklist" "${args[@]}")
  else
    args=("--use-gl=angle" "--use-angle=vulkan" "--enable-features=Vulkan" "--enable-gpu" "--ignore-gpu-blocklist" "${args[@]}")
  fi
else
  args=("$@")
fi

if [ -n "$CELLS_GPU_LOG" ]; then
  printf '%s pid %s: %s%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$$" "$([ "$mode" = card ] && echo "the graphics card ($WAY)" || echo "the software renderer")" "${why:+; $why}" >> "$CELLS_GPU_LOG" 2>/dev/null
fi
exec "$REAL" "${args[@]}"
