#!/usr/bin/env bash
# Обёртка: ansible внутри Docker (см. Readme-vps.md).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if [[ "${1:-}" == ansible-playbook ]] && [[ -n "${VPS_SSH_PASSWORD:-}" ]]; then
  shift
  exec docker compose run --rm ansible-runner ansible-playbook -e "ansible_password=${VPS_SSH_PASSWORD}" "$@"
fi

exec docker compose run --rm ansible-runner "$@"
