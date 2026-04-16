# VPS 192.144.14.9

## Назначение

Сервер используется для размещения PHP-сайтов с `nginx`, `php-fpm`, `MySQL/MariaDB`, `PostgreSQL` и `Redis`.

Конкретная конфигурация сайтов и БД хранится в:
- `vars/php_sites.yml`
- `vars/mysql.yml`
- `vars/postgresql.yml`
- `vars/redis.yml`

## Подключение

Текущий inventory настроен на:
- хост: `192.144.14.9`
- пользователь: `gstepenko`
- порт: `22`

Локальные файлы подключения:
- `inventory/hosts.ini`
- `group_vars/vps.yml`

Они не коммитятся и заменяются шаблонами:
- `inventory/hosts.ini.example`
- `group_vars/vps.yml.example`

## Рекомендуемый способ запуска

Лучше запускать Ansible из WSL.

Путь к проекту в WSL:

```bash
/mnt/d/PhpstormProjects/timewb-ansible/ansible-php-project
```

### Подготовка окружения в WSL

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip

python3 -m venv ~/venv-ansible-php-project
source ~/venv-ansible-php-project/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r /mnt/d/PhpstormProjects/timewb-ansible/ansible-php-project/requirements.txt
```

### Проверка Ansible

```powershell
wsl -e bash /mnt/d/PhpstormProjects/timewb-ansible/ansible-php-project/scripts/wsl-ansible.sh ansible --version
```

## Проверка связи с сервером

```powershell
wsl -e bash /mnt/d/PhpstormProjects/timewb-ansible/ansible-php-project/scripts/wsl-ansible.sh ansible-playbook -i inventory/hosts.ini playbooks/ping.yml
```

## Основные плейбуки

Развёртывание `nginx` + `php-fpm` + сайтов:

```powershell
wsl -e bash /mnt/d/PhpstormProjects/timewb-ansible/ansible-php-project/scripts/wsl-ansible.sh ansible-playbook -i inventory/hosts.ini playbooks/deploy_php_sites.yml
```

Развёртывание PostgreSQL:

```powershell
wsl -e bash /mnt/d/PhpstormProjects/timewb-ansible/ansible-php-project/scripts/wsl-ansible.sh ansible-playbook -i inventory/hosts.ini playbooks/deploy_postgresql.yml
```

Развёртывание MySQL:

```powershell
wsl -e bash /mnt/d/PhpstormProjects/timewb-ansible/ansible-php-project/scripts/wsl-ansible.sh ansible-playbook -i inventory/hosts.ini playbooks/deploy_mysql.yml
```

Развёртывание Redis:

```powershell
wsl -e bash /mnt/d/PhpstormProjects/timewb-ansible/ansible-php-project/scripts/wsl-ansible.sh ansible-playbook -i inventory/hosts.ini playbooks/deploy_redis.yml
```

## Redis

По умолчанию Redis:
- слушает `127.0.0.1:6379`
- включён в `protected-mode`
- не имеет пароля, пока не задан `requirepass` в `vars/redis.yml`

Проверка доступности:

```powershell
wsl -e bash /mnt/d/PhpstormProjects/timewb-ansible/ansible-php-project/scripts/wsl-ansible.sh ansible -i inventory/hosts.ini vps -b -m shell -a "systemctl is-active redis-server && redis-cli PING"
```

## Аудит диска и обслуживание

Аудит диска:

```bash
cd /mnt/d/PhpstormProjects/timewb-ansible/ansible-php-project
source ~/venv-ansible-php-project/bin/activate
python3 scripts/disk_audit.py
```

Очистка логов:

```bash
python3 scripts/clean_logs.py --all
python3 scripts/clean_logs.py --apply --system --vpn --btmp --btmp-rotated
```

## Замечания

- Проектный обзор и схема конфигурации описаны в `Readme.md`.
- Этот файл содержит практические заметки именно по текущему VPS и его обслуживанию.
