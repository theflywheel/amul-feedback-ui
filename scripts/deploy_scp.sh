#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="${ROOT_DIR}/.deploy_tmp"
ARCHIVE_NAME="feedback-ui-deploy.tar.gz"
ARCHIVE_PATH="${TMP_DIR}/${ARCHIVE_NAME}"

DEPLOY_HOST="${DEPLOY_HOST:-}"
DEPLOY_USER="${DEPLOY_USER:-}"
DEPLOY_PORT="${DEPLOY_PORT:-22}"
REMOTE_DIR="${REMOTE_DIR:-amul-feedback-ui}"
SSH_KEY_PATH="${SSH_KEY_PATH:-}"
RUN_REMOTE="${RUN_REMOTE:-1}"

usage() {
  cat <<EOF
Usage:
  $(basename "$0") --host <server> [--user <ssh-user>] [options]

Options:
  --host <server>         SSH host or ssh-config alias (or set DEPLOY_HOST)
  --user <ssh-user>       SSH user (or set DEPLOY_USER). If omitted, ssh config User (if any) is used.
  --port <port>           SSH port (default: 22 or DEPLOY_PORT)
  --remote-dir <dir>      Deploy directory on server (default: amul-feedback-ui under remote \$HOME, i.e. ~/amul-feedback-ui)
  --key <path>            SSH private key path
  --no-run                Only upload/extract; do not run docker compose
  -h, --help              Show help

Environment alternatives:
  DEPLOY_HOST, DEPLOY_USER, DEPLOY_PORT, REMOTE_DIR, SSH_KEY_PATH, RUN_REMOTE
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) DEPLOY_HOST="$2"; shift 2 ;;
    --user) DEPLOY_USER="$2"; shift 2 ;;
    --port) DEPLOY_PORT="$2"; shift 2 ;;
    --remote-dir) REMOTE_DIR="$2"; shift 2 ;;
    --key) SSH_KEY_PATH="$2"; shift 2 ;;
    --no-run) RUN_REMOTE=0; shift 1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 1 ;;
  esac
done

if [[ -z "${DEPLOY_HOST}" ]]; then
  echo "Error: --host is required (or DEPLOY_HOST)."
  usage
  exit 1
fi

mkdir -p "${TMP_DIR}"
rm -f "${ARCHIVE_PATH}"

echo "Creating deploy archive..."
tar -czf "${ARCHIVE_PATH}" \
  -C "${ROOT_DIR}" \
  app.py \
  requirements.txt \
  Dockerfile \
  docker-compose.yml \
  .gitignore \
  templates \
  static \
  scripts \
  docs \
  data

SSH_OPTS=(-p "${DEPLOY_PORT}" -o StrictHostKeyChecking=accept-new)
SCP_OPTS=(-P "${DEPLOY_PORT}" -o StrictHostKeyChecking=accept-new)
if [[ -n "${SSH_KEY_PATH}" ]]; then
  SSH_OPTS+=(-i "${SSH_KEY_PATH}")
  SCP_OPTS+=(-i "${SSH_KEY_PATH}")
fi

if [[ -n "${DEPLOY_USER}" ]]; then
  REMOTE="${DEPLOY_USER}@${DEPLOY_HOST}"
else
  REMOTE="${DEPLOY_HOST}"
fi

echo "Ensuring remote directory: ${REMOTE_DIR}"
ssh "${SSH_OPTS[@]}" "${REMOTE}" "mkdir -p \"${REMOTE_DIR}\""

echo "Uploading archive via scp..."
scp "${SCP_OPTS[@]}" "${ARCHIVE_PATH}" "${REMOTE}:${REMOTE_DIR}/${ARCHIVE_NAME}"

echo "Extracting archive on remote..."
ssh "${SSH_OPTS[@]}" "${REMOTE}" "tar -xzf \"${REMOTE_DIR}/${ARCHIVE_NAME}\" -C \"${REMOTE_DIR}\" && rm -f \"${REMOTE_DIR}/${ARCHIVE_NAME}\""

if [[ "${RUN_REMOTE}" = "1" ]]; then
  echo "Running docker compose on remote..."
  ssh "${SSH_OPTS[@]}" "${REMOTE}" "cd \"${REMOTE_DIR}\" && docker compose up -d --build"
fi

echo "Done."
