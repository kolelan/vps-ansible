#!/usr/bin/env python3
"""
Аудит диска на VPS по SSH — те же проверки, что playbooks/disk_audit.yml.

  export VPS_SSH_PASSWORD='…'
  python3 scripts/disk_audit.py

  python3 scripts/disk_audit.py --env-file .env -o report.txt

Зависимость: pip install paramiko (есть в requirements.txt проекта).
"""
from __future__ import annotations

import argparse
import os
import shlex
import sys
import time
from pathlib import Path


def merge_env_file(path: Path) -> None:
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8-sig")
    for raw in text.splitlines():
        line = raw.strip().strip("\r")
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("'\"")
        if key:
            os.environ.setdefault(key, val)


def run_remote(
    client: "paramiko.SSHClient", command: str, timeout: int = 180
) -> tuple[str, str, int]:
    import paramiko

    wrapped = "bash -lc " + shlex.quote(command)
    stdin, stdout, stderr = client.exec_command(wrapped, timeout=timeout)
    try:
        out_b = stdout.read()
        err_b = stderr.read()
        code = stdout.channel.recv_exit_status()
    except paramiko.SSHException as e:
        return "", str(e), -1
    return out_b.decode("utf-8", errors="replace"), err_b.decode(
        "utf-8", errors="replace"
    ), code


def main() -> int:
    parser = argparse.ArgumentParser(description="Аудит использования диска на VPS (SSH).")
    parser.add_argument(
        "--host",
        default=os.environ.get("VPS_HOST", "80.90.182.160"),
        help="Хост VPS",
    )
    parser.add_argument(
        "--user",
        default=os.environ.get("VPS_USER", "root"),
        help="Пользователь SSH",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("VPS_PORT", "22")),
        help="Порт SSH",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Пароль SSH (если не задан — VPS_SSH_PASSWORD или .env)",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Подгрузить переменные из файла, если пароль не задан",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Сохранить отчёт в файл (печать в stdout всегда)",
    )
    args = parser.parse_args()

    try:
        import paramiko
    except ImportError:
        print("Нужен пакет paramiko: python3 -m pip install paramiko", file=sys.stderr)
        return 1

    root = Path(__file__).resolve().parent.parent
    for candidate in (
        Path.cwd() / ".env",
        root / ".env",
        args.env_file.expanduser() if args.env_file else None,
    ):
        if candidate is not None:
            merge_env_file(candidate)

    password = args.password or os.environ.get("VPS_SSH_PASSWORD")

    if not password:
        print(
            "Задайте VPS_SSH_PASSWORD или --password, либо положите пароль в .env",
            file=sys.stderr,
        )
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=args.host,
            port=args.port,
            username=args.user,
            password=password,
            timeout=30,
            allow_agent=False,
            look_for_keys=False,
        )
    except Exception as e:
        print(f"SSH: {e}", file=sys.stderr)
        return 1

    sections: list[tuple[str, str]] = []

    cmds: list[tuple[str, str]] = [
        ("df -hT", "df -hT"),
        ("du --max-depth=1 /", "du -xh --max-depth=1 / 2>/dev/null | sort -h"),
        ("/var/log", "du -sh /var/log 2>/dev/null || echo 'нет /var/log'"),
        (
            "топ в /var/log",
            "du -sh /var/log/* 2>/dev/null | sort -h | tail -n 30",
        ),
        ("journalctl --disk-usage", "journalctl --disk-usage 2>/dev/null || echo '(journalctl недоступен)'"),
        (
            "VPN / Outline пути",
            "for p in /etc/wireguard /var/log/wireguard /opt/outline; do "
            'if [ -e "$p" ]; then du -sh "$p" 2>/dev/null; else echo "$p — нет"; fi; done',
        ),
    ]

    for title, remote_cmd in cmds:
        out, err, code = run_remote(client, remote_cmd)
        body = out
        if err.strip():
            body = (body + "\n" + err).strip()
        if code != 0 and not body:
            body = f"(код выхода {code})"
        sections.append((title, body))

    client.close()

    lines = [
        f"=== VPS disk audit {args.user}@{args.host} ===",
        f"=== время (локально): {time.strftime('%Y-%m-%d %H:%M:%S')} ===",
        "",
    ]
    for title, body in sections:
        lines.append(f"=== {title} ===")
        lines.append(body.rstrip())
        lines.append("")

    report = "\n".join(lines).rstrip() + "\n"
    sys.stdout.write(report)
    if args.output:
        args.output.write_text(report, encoding="utf-8")
        print(f"\nСохранено: {args.output.resolve()}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
