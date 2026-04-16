#!/usr/bin/env python3
"""
Генерация vars/mysql_secrets.yml: случайные пароли для каждого сайта из php_sites
и для all_db_user (MySQL/MariaDB).

Зависимость: pip install pyyaml

Использование (из каталога ansible-php-project):
  python3 scripts/generate_mysql_secrets.py              # создать или дополнить файл
  python3 scripts/generate_mysql_secrets.py --force-all  # заново сгенерировать все пароли
  python3 scripts/generate_mysql_secrets.py --dry-run    # только вывод в stdout

После смены паролей в файле снова запустите:
  ansible-playbook playbooks/deploy_mysql.yml
модуль mysql_user обновит пароли на сервере идемпотентно.
"""
from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Установите PyYAML: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


def pw() -> str:
    return secrets.token_urlsafe(24)


def load_yaml(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    return data if isinstance(data, dict) else {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Сгенерировать vars/mysql_secrets.yml")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Корень ansible-php-project",
    )
    parser.add_argument(
        "--force-all",
        action="store_true",
        help="Перезаписать все пароли, даже если файл уже есть",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Не писать файл, показать YAML в stdout",
    )
    args = parser.parse_args()
    root: Path = args.project_root
    sites_file = root / "vars" / "php_sites.yml"
    out_file = root / "vars" / "mysql_secrets.yml"

    if not sites_file.is_file():
        print(f"Нет файла: {sites_file}", file=sys.stderr)
        sys.exit(1)

    data = load_yaml(sites_file)
    sites = data.get("php_sites")
    if not isinstance(sites, list):
        print("В php_sites.yml не найден список php_sites", file=sys.stderr)
        sys.exit(1)

    names: list[str] = []
    for row in sites:
        if not (isinstance(row, dict) and "name" in row):
            continue
        db = row.get("db")
        if db is None or str(db) in {"mysql", "both"}:
            names.append(str(row["name"]))
    if not names:
        print("Список сайтов пуст", file=sys.stderr)
        sys.exit(1)

    existing_pw: dict = {}
    existing_all: str | None = None
    if out_file.is_file() and not args.force_all:
        sec = load_yaml(out_file)
        raw = sec.get("mysql_site_passwords")
        if isinstance(raw, dict):
            existing_pw = {str(k): str(v) for k, v in raw.items()}
        a = sec.get("mysql_all_db_user_password")
        if isinstance(a, str) and a:
            existing_all = a

    site_passwords: dict[str, str] = {}
    for name in names:
        if not args.force_all and name in existing_pw:
            site_passwords[name] = existing_pw[name]
        else:
            site_passwords[name] = pw()

    if args.force_all or existing_all is None:
        all_db_pw = pw()
    else:
        all_db_pw = existing_all

    body = yaml.safe_dump(
        {"mysql_site_passwords": site_passwords, "mysql_all_db_user_password": all_db_pw},
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    header = (
        "# Файл с секретами MySQL/MariaDB — в .gitignore.\n"
        "# Регенерация: python3 scripts/generate_mysql_secrets.py --force-all\n\n"
    )
    output = header + body

    if args.dry_run:
        print(output, end="")
        return

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(output, encoding="utf-8")
    print(f"Записано: {out_file} ({len(names)} сайтов + all_db_user)")


if __name__ == "__main__":
    main()
