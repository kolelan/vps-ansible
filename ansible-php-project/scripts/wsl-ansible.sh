#!/usr/bin/env bash
# Запуск Ansible из WSL: проект на диске Windows, venv в $HOME (ext4).
# Везде используйте python3 (см. Readme-vps.md).
#
# Примеры из PowerShell:
#   wsl -e bash /mnt/d/PhpstormProjects/timewb-ansible/ansible-php-project/scripts/wsl-ansible.sh ansible --version
#   wsl -e bash .../wsl-ansible.sh ansible-playbook playbooks/ping.yml
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
export ANSIBLE_CONFIG="${PROJECT_ROOT}/ansible.cfg"

VENV="${HOME}/venv-ansible-php-project"
if [[ ! -f "${VENV}/bin/activate" ]]; then
  echo "Нет venv: ${VENV}" >&2
  echo "Создайте его по инструкции в Readme-vps.md (раздел WSL, python3)." >&2
  exit 1
fi

# shellcheck source=/dev/null
source "${VENV}/bin/activate"
cd "${PROJECT_ROOT}"

# ansible-playbook не подставляет ansible_password из group_vars с lookup('env') до открытия
# соединения (paramiko/ssh). Явная передача через -e снимает проблему.
if [[ "${1:-}" == ansible-playbook ]] && [[ -n "${VPS_SSH_PASSWORD:-}" ]]; then
  shift
  exec ansible-playbook -e "ansible_password=${VPS_SSH_PASSWORD}" "$@"
fi

exec "$@"
