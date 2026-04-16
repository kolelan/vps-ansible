#!/usr/bin/env python3
"""
Очистка логов на VPS по SSH (paramiko). Без --apply только план (dry-run).

Категории (можно несколько):
  --all       всё ниже: system + wg + outline + web
  --system    journald (vacuum), apt-get clean
  --wg        файлы логов WireGuard в /var/log
  --outline   логи Docker-контейнеров Outline + *.log в /opt/outline
  --vpn       то же, что --wg и --outline вместе
  --web       nginx / apache/httpd / php-fpm в /var/log

Дополнительно (к любым категориям):
  --btmp, --btmp-rotated, --docker-prune, --no-journal, --journal-size, --apt-clean

Примеры:
  python3 scripts/clean_logs.py --all
  python3 scripts/clean_logs.py --apply --system --vpn
  python3 scripts/clean_logs.py --apply --web --btmp --btmp-rotated

Пароль: VPS_SSH_PASSWORD или .env (как scripts/disk_audit.py).
"""
from __future__ import annotations

import argparse
import os
import shlex
import sys
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
    client: "paramiko.SSHClient", command: str, timeout: int = 300
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


def snapshot_disk(client: "paramiko.SSHClient", label: str) -> None:
    print(f"\n--- {label} ---", file=sys.stderr)
    for title, cmd in (
        ("df /", "df -h / | tail -1"),
        ("/var/log", "du -sh /var/log 2>/dev/null || true"),
        ("journal", "journalctl --disk-usage 2>/dev/null || true"),
    ):
        out, err, code = run_remote(client, cmd, timeout=60)
        line = (out + err).strip() or f"(пусто, код {code})"
        print(f"  {title}: {line}", file=sys.stderr)


CMD_WG = r"""shopt -s nullglob
for f in /var/log/wireguard /var/log/wg-quick.log /var/log/wg-*.log; do
  [ -e "$f" ] && truncate -s 0 "$f" 2>/dev/null || true
done
true"""

CMD_OUTLINE = r"""if command -v docker >/dev/null 2>&1; then
  docker ps -aq --filter 'name=outline' 2>/dev/null | while read -r id; do
    [ -z "$id" ] && continue
    lp=$(docker inspect --format='{{.LogPath}}' "$id" 2>/dev/null)
    [ -n "$lp" ] && [ -f "$lp" ] && truncate -s 0 "$lp" 2>/dev/null || true
  done
fi
if [ -d /opt/outline ]; then
  find /opt/outline -type f \( -name '*.log' -o -name '*.log.*' \) -print0 2>/dev/null |
    while IFS= read -r -d '' f; do truncate -s 0 "$f" 2>/dev/null || true; done
fi
true"""

CMD_WEB = r"""for d in /var/log/nginx /var/log/apache2 /var/log/httpd; do
  [ -d "$d" ] || continue
  find "$d" -type f \( -name '*.log' -o -name '*.log.*' \) -exec truncate -s 0 {} \; 2>/dev/null || true
done
find /var/log -maxdepth 3 -type f \( -name 'php*-fpm*.log' -o -name 'php8*.log' -o -name 'php7*.log' \) 2>/dev/null \
  | while read -r f; do truncate -s 0 "$f" 2>/dev/null || true; done
true"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Очистка логов на VPS по категориям (journald, VPN, веб, …)."
    )
    parser.add_argument("--host", default=os.environ.get("VPS_HOST", "80.90.182.160"))
    parser.add_argument("--user", default=os.environ.get("VPS_USER", "root"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("VPS_PORT", "22")))
    parser.add_argument("--password", default=None)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Выполнить на сервере (иначе только план)",
    )
    g = parser.add_argument_group("категории (нужна хотя бы одна или --all)")
    g.add_argument(
        "--all",
        action="store_true",
        help="system + wg + outline + web",
    )
    g.add_argument(
        "--system",
        action="store_true",
        help="journald vacuum + apt-get clean",
    )
    g.add_argument("--wg", action="store_true", help="логи WireGuard в /var/log")
    g.add_argument(
        "--outline",
        action="store_true",
        help="логи контейнеров Outline (docker) и файлы в /opt/outline",
    )
    g.add_argument(
        "--vpn",
        action="store_true",
        help="WireGuard + Outline (--wg и --outline)",
    )
    g.add_argument(
        "--web",
        action="store_true",
        help="nginx, apache/httpd, php-fpm в /var/log",
    )
    parser.add_argument(
        "--journal-size",
        default="200M",
        metavar="SIZE",
        help="для system: journalctl --vacuum-size (по умолчанию 200M)",
    )
    parser.add_argument(
        "--no-journal",
        action="store_true",
        help="не вызывать journalctl --vacuum-size (внутри --system)",
    )
    parser.add_argument(
        "--no-apt",
        action="store_true",
        help="не вызывать apt-get clean (внутри --system)",
    )
    parser.add_argument(
        "--btmp",
        action="store_true",
        help="обнулить /var/log/btmp",
    )
    parser.add_argument(
        "--btmp-rotated",
        action="store_true",
        help="удалить /var/log/btmp.1",
    )
    parser.add_argument(
        "--apt-clean",
        action="store_true",
        help="только apt-get clean без --system / --all",
    )
    parser.add_argument(
        "--docker-prune",
        action="store_true",
        help="docker system prune -f",
    )
    args = parser.parse_args()

    try:
        import paramiko
    except ImportError:
        print("Нужен paramiko: python3 -m pip install paramiko", file=sys.stderr)
        return 1

    root = Path(__file__).resolve().parent.parent
    for candidate in (Path.cwd() / ".env", root / ".env", args.env_file.expanduser()):
        merge_env_file(candidate)

    password = args.password or os.environ.get("VPS_SSH_PASSWORD")
    if not password:
        print("Задайте VPS_SSH_PASSWORD или --password / .env", file=sys.stderr)
        return 1

    steps = build_steps(args)

    if not steps:
        print(
            "Укажите категорию: --all, --system, --wg, --outline, --vpn, --web\n"
            "Или только дополнения: --btmp, --docker-prune (без journal/system).\n"
            "Пример:  python3 scripts/clean_logs.py --system\n"
            "         python3 scripts/clean_logs.py --apply --all --btmp",
            file=sys.stderr,
        )
        return 1

    mode = "ВЫПОЛНЕНИЕ" if args.apply else "DRY-RUN (добавьте --apply)"
    print(f"Режим: {mode}", file=sys.stderr)
    print(f"Цель: {args.user}@{args.host}:{args.port}\n", file=sys.stderr)
    for title, cmd in steps:
        preview = cmd.strip().splitlines()
        if len(preview) == 1:
            print(f"  • {title}\n    $ {preview[0]}\n", file=sys.stderr)
        else:
            print(f"  • {title}\n    $ ({len(preview)} строк bash)\n", file=sys.stderr)

    if not args.apply:
        print("\nДля запуска добавьте --apply.", file=sys.stderr)
        return 0

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

    snapshot_disk(client, "До очистки")

    for title, cmd in steps:
        print(f"\n>>> {title}", file=sys.stderr)
        out, err, code = run_remote(client, cmd)
        if out.strip():
            print(out.rstrip())
        if err.strip():
            print(err.rstrip(), file=sys.stderr)
        if code != 0:
            print(f"(код выхода {code})", file=sys.stderr)

    snapshot_disk(client, "После очистки")
    client.close()
    print("\nГотово.", file=sys.stderr)
    return 0


def build_steps(args: argparse.Namespace) -> list[tuple[str, str]]:
    cats: set[str] = set()
    if args.all:
        cats |= {"system", "wg", "outline", "web"}
    if args.system:
        cats.add("system")
    if args.wg:
        cats.add("wg")
    if args.outline:
        cats.add("outline")
    if args.vpn:
        cats |= {"wg", "outline"}
    if args.web:
        cats.add("web")

    steps: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(title: str, cmd: str) -> None:
        k = cmd.strip()
        if k in seen:
            return
        seen.add(k)
        steps.append((title, cmd))

    if "system" in cats:
        if not args.no_journal:
            add(
                f"[system] journalctl --vacuum-size={args.journal_size}",
                f"journalctl --vacuum-size={args.journal_size}",
            )
        if not args.no_apt:
            add(
                "[system] apt-get clean",
                "DEBIAN_FRONTEND=noninteractive apt-get clean -qq 2>/dev/null || true",
            )

    if "wg" in cats:
        add("[wg] логи WireGuard в /var/log", CMD_WG)

    if "outline" in cats:
        add("[outline] Docker Outline + /opt/outline/*.log", CMD_OUTLINE)

    if "web" in cats:
        add("[web] nginx / apache / httpd / php-fpm", CMD_WEB)

    if args.apt_clean and "system" not in cats and not args.all:
        add(
            "[apt] apt-get clean (только кеш пакетов)",
            "DEBIAN_FRONTEND=noninteractive apt-get clean -qq 2>/dev/null || true",
        )

    if args.btmp:
        add(
            "[extra] /var/log/btmp",
            "truncate -s 0 /var/log/btmp 2>/dev/null || true",
        )
    if args.btmp_rotated:
        add("[extra] rm /var/log/btmp.1", "rm -f /var/log/btmp.1")
    if args.docker_prune:
        add(
            "[extra] docker system prune -f",
            "docker system prune -f 2>/dev/null || echo '(docker недоступен)'",
        )

    return steps


if __name__ == "__main__":
    raise SystemExit(main())
