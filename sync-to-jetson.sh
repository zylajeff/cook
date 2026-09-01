#!/usr/bin/env bash
# Push the source tree to the Jetson.
#
# Uses tar over ssh rather than rsync: rsync must be installed on BOTH ends and
# the JetPack base image has no rsync. tar and ssh are always present.
#
#   ./sync-to-jetson.sh                    # uses the defaults below
#   ./sync-to-jetson.sh user@host [path]
set -euo pipefail

TARGET="${1:-burninator@192.168.86.30}"
REMOTE_DIR="${2:-cook}"

cd "$(dirname "$0")"
echo "Syncing $(pwd) -> ${TARGET}:~/${REMOTE_DIR}/"

tar czf - \
  --exclude=.venv --exclude=__pycache__ --exclude=.pytest_cache \
  --exclude='*.egg-info' --exclude=.git --exclude='*.pyc' \
  . | ssh "${TARGET}" "mkdir -p ~/${REMOTE_DIR} && tar xzf - -C ~/${REMOTE_DIR} && chmod +x ~/${REMOTE_DIR}/*.sh"

echo "Done. On the Jetson:"
echo "  cd ~/${REMOTE_DIR} && PYTHONPATH=src python3 -m cook_vision.doctor"
