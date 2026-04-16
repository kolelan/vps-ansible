# Ansible-проект для VPS с PHP-сайтами

Проект разворачивает на VPS:
- `nginx`
- `php-fpm`
- `MySQL/MariaDB`
- `PostgreSQL`
- `Redis`

Сайты описываются в `vars/php_sites.yml`. Для каждого сайта можно выбрать:
- `mysql`
- `pgsql`
- `both`
- `none`

Подробные заметки по WSL, Docker и серверу: `Readme-vps.md`.

## Структура настройки

Основные файлы:
- `inventory/hosts.ini` или `inventory/hosts.ini.example`
- `group_vars/vps.yml` или `group_vars/vps.yml.example`
- `vars/php_sites.yml` или `vars/php_sites.yml.example`
- `vars/mysql.yml` или `vars/mysql.yml.example`
- `vars/postgresql.yml` или `vars/postgresql.yml.example`
- `vars/redis.yml` или `vars/redis.yml.example`

Секреты:
- `vars/mysql_secrets.yml` и `vars/mysql_secrets.yml.example`
- `vars/pgsql_secrets.yml` и `vars/pgsql_secrets.yml.example`
- `.env` и `.env.example`

Локальные и секретные файлы добавлены в `.gitignore`:
- `.env`
- `inventory/hosts.ini`
- `group_vars/vps.yml`
- `vars/mysql_secrets.yml`
- `vars/pgsql_secrets.yml`

## Описание сайта

Пример записи в `vars/php_sites.yml`:

```yml
php_sites:
  - name: example.org
    db: both
    use_redis: true
    redis_db: 0

  - name: api.example.org
    db: mysql
    mysql_id: api_example_org

  - name: legacy.example.org
    db: pgsql
    pgsql_id: legacy_example_org

  - name: static.example.org
    db: none
```

Поля:
- `name` — домен сайта
- `db` — тип БД: `mysql`, `pgsql`, `both`, `none`
- `mysql_id` — необязательный идентификатор для MySQL
- `pgsql_id` — необязательный идентификатор для PostgreSQL
- `use_redis` — нужен ли Redis, если глобальная установка Redis отключена
- `redis_db` — логическая БД Redis (справочно)

Если `mysql_id` или `pgsql_id` не указаны, имя вычисляется автоматически из домена.

## Генерация секретов

MySQL:

```bash
python3 scripts/generate_mysql_secrets.py
```

PostgreSQL:

```bash
python3 scripts/generate_pgsql_secrets.py
```

Полная регенерация:

```bash
python3 scripts/generate_mysql_secrets.py --force-all
python3 scripts/generate_pgsql_secrets.py --force-all
```

Для генераторов нужен `PyYAML`.

## Плейбуки

Проверка связи:

```bash
bash scripts/wsl-ansible.sh ansible-playbook -i inventory/hosts.ini playbooks/ping.yml
```

Развёртывание сайтов:

```bash
bash scripts/wsl-ansible.sh ansible-playbook -i inventory/hosts.ini playbooks/deploy_php_sites.yml
```

Развёртывание PostgreSQL для сайтов с `db: pgsql` и `db: both`:

```bash
bash scripts/wsl-ansible.sh ansible-playbook -i inventory/hosts.ini playbooks/deploy_postgresql.yml
```

Развёртывание MySQL для сайтов с `db: mysql` и `db: both`:

```bash
bash scripts/wsl-ansible.sh ansible-playbook -i inventory/hosts.ini playbooks/deploy_mysql.yml
```

Развёртывание Redis:

```bash
bash scripts/wsl-ansible.sh ansible-playbook -i inventory/hosts.ini playbooks/deploy_redis.yml
```

## Рекомендуемый порядок запуска

```bash
bash scripts/wsl-ansible.sh ansible-playbook -i inventory/hosts.ini playbooks/ping.yml
bash scripts/wsl-ansible.sh ansible-playbook -i inventory/hosts.ini playbooks/deploy_php_sites.yml
bash scripts/wsl-ansible.sh ansible-playbook -i inventory/hosts.ini playbooks/deploy_postgresql.yml
bash scripts/wsl-ansible.sh ansible-playbook -i inventory/hosts.ini playbooks/deploy_mysql.yml
bash scripts/wsl-ansible.sh ansible-playbook -i inventory/hosts.ini playbooks/deploy_redis.yml
```

## Redis

По умолчанию Redis ставится на хост для всех сайтов, если в `vars/redis.yml`:

```yml
redis_install_for_all_sites: true
```

Текущая базовая схема подключения:
- host: `127.0.0.1`
- port: `6379`
- password: не задан, если `requirepass` не включён

Проверка доступности Redis:

```bash
bash scripts/wsl-ansible.sh ansible -i inventory/hosts.ini vps -b -m shell -a "systemctl is-active redis-server && redis-cli PING"
```

## Example-файлы

Для проекта подготовлены example-файлы:
- `.env.example`
- `inventory/hosts.ini.example`
- `group_vars/vps.yml.example`
- `vars/php_sites.yml.example`
- `vars/mysql.yml.example`
- `vars/mysql_secrets.yml.example`
- `vars/postgresql.yml.example`
- `vars/pgsql_secrets.yml.example`
- `vars/redis.yml.example`

## Полезно знать

- `deploy_php_sites.yml` разворачивает `nginx`, `php-fpm`, виртуальные хосты и базовые PHP-модули.
- `deploy_postgresql.yml` и `deploy_mysql.yml` создают пользователей и базы только для тех сайтов, которым это нужно по `db`.
- `deploy_redis.yml` управляет `redis-server` и его конфигурацией.
- Для запуска из Windows удобнее использовать WSL-обёртку `scripts/wsl-ansible.sh`.
