# Репозиторий конфигураций VPS

Этот репозиторий предназначен для хранения разных конфигураций и сценариев развёртывания VPS-серверов.

Внутри могут находиться:
- Ansible-проекты
- шаблоны конфигураций
- служебные скрипты
- документация по конкретным серверам

## Текущие конфигурации

### `ansible-php-project`

Конфигурация VPS для PHP-сайтов с:
- `nginx`
- `php-fpm`
- `MySQL/MariaDB`
- `PostgreSQL`
- `Redis`

Документация:
- общий обзор проекта: [`ansible-php-project/Readme.md`](ansible-php-project/Readme.md)
- заметки по текущему серверу: [`ansible-php-project/Readme-vps.md`](ansible-php-project/Readme-vps.md)

## Идея структуры репозитория

Предполагается, что со временем здесь может быть несколько независимых конфигураций, например:
- `ansible-php-project`
- `ansible-node-project`
- `ansible-docker-host`
- `ansible-monitoring`

У каждой папки может быть свой:
- `Readme.md`
- inventory
- набор `vars`
- playbooks
- scripts

## Правило для локальных файлов

Локальные и секретные файлы не должны попадать в git.

Для этого используются:
- `.gitignore`
- `*.example` файлы вместо реальных локальных конфигов

Если в подпроекте есть:
- `inventory/hosts.ini`
- `group_vars/vps.yml`
- `vars/*_secrets.yml`

то рядом желательно держать:
- `inventory/hosts.ini.example`
- `group_vars/vps.yml.example`
- `vars/*_secrets.yml.example`
