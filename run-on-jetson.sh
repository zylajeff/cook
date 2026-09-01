#!/usr/bin/env bash
# Run straight from the source tree.
#
# We deliberately do not `pip install` on the Jetson. JetPack 4's Python is 3.6,
# whose newest possible setuptools (59.x) predates PEP 621, so the pyproject
# metadata cannot be read there. Running from source sidesteps packaging
# entirely and, more importantly, keeps pip away from numpy and OpenCV.
set -euo pipefail
cd "$(dirname "$0")"

# Over SSH there is no DISPLAY, and guessing :0 is wrong as often as not --
# gdm puts the greeter on one display and the logged-in session on another.
# Ask `who` which local session actually exists rather than assuming.
if [[ -z "${DISPLAY:-}" && ! " $* " =~ " --headless " ]]; then
  detected="$(who 2>/dev/null | awk '$2 ~ /^:[0-9]+$/ {print $2; exit}')"
  if [[ -n "${detected}" ]]; then
    export DISPLAY="${detected}"
    echo "run-on-jetson: using DISPLAY=${DISPLAY} (from an active login session)"
  else
    echo "run-on-jetson: no local X session found; pass --headless, or log in at the console" >&2
  fi
fi

# An SSH session inherits no X authority cookie. Under gdm the cookie lives in
# the runtime dir, not the classic ~/.Xauthority.
if [[ -n "${DISPLAY:-}" && -z "${XAUTHORITY:-}" ]]; then
  for candidate in "/run/user/$(id -u)/gdm/Xauthority" "${HOME}/.Xauthority"; do
    if [[ -r "${candidate}" ]]; then
      export XAUTHORITY="${candidate}"
      echo "run-on-jetson: using XAUTHORITY=${XAUTHORITY}"
      break
    fi
  done
fi

exec env PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}" python3 -m cook_vision.app "$@"
