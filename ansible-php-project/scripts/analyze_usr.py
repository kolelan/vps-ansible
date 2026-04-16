#!/usr/bin/env python3
"""
Анализ содержимого /usr на VPS по SSH: размеры, назначение каталогов (FHS), топ пакетов dpkg.

  python3 scripts/analyze_usr.py
  python3 scripts/analyze_usr.py -o usr-report.txt
  python3 scripts/analyze_usr.py --depth-lib 3

Пароль: VPS_SSH_PASSWORD или .env (как disk_audit.py). Нужен paramiko.
"""
from __future__ import annotations

import argparse
import os
import re
import shlex
import sys
import time
from pathlib import Path

# Назначение верхнего уровня /usr/* (Filesystem Hierarchy Standard + типичный сервер)
USR_TOP_PURPOSE: dict[str, str] = {
    "bin": "Программы для всех пользователей (часть ОС и пакетов).",
    "sbin": "Системные утилиты (часто только root): сеть, сервисы, init.",
    "lib": "Разделяемые библиотеки (.so), часть модулей; обычно самый тяжёлый раздел /usr.",
    "lib32": "32-битные библиотеки (мультиарх).",
    "lib64": "64-битные библиотеки (если отдельное дерево, не только ссылка).",
    "libexec": "Вспомогательные исполняемые файлы для других программ.",
    "share": "Данные только для чтения: man, locale, документация, иконки, скрипты приложений.",
    "local": "Установки вручную (make install, сторонние скрипты). Имеет смысл просматривать при аномальном размере.",
    "src": "Исходники/заголовки (linux-headers и т.п.). Старые headers можно удалить после смены ядра.",
    "include": "Заголовки для компиляции C/C++.",
    "games": "Игры (на сервере редко).",
}

# Подсказки для частых путей глубже /usr (подстрока пути → пояснение)
PATH_HINTS: list[tuple[str, str]] = [
    ("/usr/lib/docker", "Клиент/части Docker Engine. Образы и слои — обычно в /var/lib/docker."),
    ("/usr/lib/modules", "Модули установленных ядер Linux (по одному каталогу на версию ядра)."),
    ("/usr/lib/firmware", "Прошивки для железа."),
    ("/usr/lib/python", "Стандартная библиотека и site-packages Python из пакетов."),
    ("/usr/lib/postgresql", "Файлы СУБД PostgreSQL из пакета (данные кластера — в /var/lib/postgresql)."),
    ("/usr/lib/systemd", "Unit-файлы и вспомогательные скрипты systemd."),
    ("/usr/lib/apt", "Логика apt."),
    ("/usr/share/doc", "Документация пакетов; можно ужимать через удаление *-doc или localepurge."),
    ("/usr/share/locale", "Переводы интерфейсов; при одной локали часть можно срезать (осторожно)."),
    ("/usr/share/man", "Страницы man."),
    ("/usr/lib/gcc", "Компилятор GCC и сопутствующие файлы."),
    ("/usr/lib/llvm", "LLVM/Clang, если установлены."),
    ("/usr/lib/x86_64-linux-gnu", "Библиотеки под вашу архитектуру (Debian/Ubuntu)."),
]


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


def purpose_for_path(path: str) -> str:
    path = path.rstrip("/")
    if path == "/usr":
        return "Корень: программы и данные дистрибутива (не пользовательские данные)."
    for prefix, hint in PATH_HINTS:
        if path.startswith(prefix) or prefix in path:
            return hint
    name = Path(path).name
    if name in USR_TOP_PURPOSE:
        return USR_TOP_PURPOSE[name]
    return "Стандартное содержимое дистрибутива или пакетов; детали — по имени пакета (см. dpkg ниже)."


def parse_du_line(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line:
        return None
    parts = line.split("\t", 1)
    if len(parts) != 2:
        parts = re.split(r"\s+", line, 1)
        if len(parts) != 2:
            return None
    size, path = parts[0].strip(), parts[1].strip()
    if not path.startswith("/"):
        return None
    return size, path


def size_to_kb_approx(size: str) -> float | None:
    """Грубое сравнение для эвристик: K M G T."""
    size = size.strip().upper()
    m = re.match(r"^([\d.]+)([KMGT]?)B?$", size.replace("I", ""))
    if not m:
        return None
    n = float(m.group(1))
    u = m.group(2) or ""
    mul = {"": 1 / 1024, "K": 1, "M": 1024, "G": 1024**2, "T": 1024**3}
    return n * mul.get(u, 1)


def lines(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if ln.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Анализ каталога /usr на удалённом хосте (SSH + du + dpkg)."
    )
    parser.add_argument("--host", default=os.environ.get("VPS_HOST", "80.90.182.160"))
    parser.add_argument("--user", default=os.environ.get("VPS_USER", "root"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("VPS_PORT", "22")))
    parser.add_argument("--password", default=None)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument(
        "--depth",
        type=int,
        default=2,
        metavar="N",
        help="Глубина du под /usr для таблицы «крупные вложенные» (по умолчанию 2)",
    )
    parser.add_argument(
        "--depth-lib",
        type=int,
        default=0,
        metavar="N",
        help="Если >0: дополнительно du с этой глубиной только под /usr/lib",
    )
    parser.add_argument(
        "--top-du",
        type=int,
        default=45,
        help="Сколько строк du (с конца после sort -h) показать",
    )
    parser.add_argument(
        "--top-packages",
        type=int,
        default=35,
        help="Сколько крупнейших пакетов dpkg показать",
    )
    parser.add_argument("-o", "--output", type=Path, help="Сохранить отчёт в файл")
    args = parser.parse_args()

    try:
        import paramiko
    except ImportError:
        print("Нужен paramiko: python3 -m pip install paramiko", file=sys.stderr)
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
        print("Задайте VPS_SSH_PASSWORD или --password / .env", file=sys.stderr)
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

    out_parts: list[str] = []

    def emit(s: str = "") -> None:
        out_parts.append(s)
        print(s)

    emit(f"=== Анализ /usr на {args.user}@{args.host} ===")
    emit(f"=== время: {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
    emit()

    # --- /usr верхний уровень с пояснениями
    emit("### 1. Размеры прямых подкаталогов /usr (du --max-depth=1)")
    cmd1 = "du -xh --max-depth=1 /usr 2>/dev/null | sort -h"
    du1, err1, c1 = run_remote(client, cmd1)
    if err1.strip():
        emit(err1.strip())
    rows1: list[tuple[str, str]] = []
    for ln in lines(du1):
        p = parse_du_line(ln)
        if p:
            rows1.append(p)
    for size, path in rows1:
        purpose = purpose_for_path(path)
        emit(f"  {size:>8}  {path}")
        emit(f"            └─ {purpose}")
    emit()

    total_usr_kb = 0.0
    for size, path in rows1:
        if path == "/usr":
            total_usr_kb = size_to_kb_approx(size) or 0
            break

    # --- глубже: крупнейшие по суммарному du
    depth = max(1, min(args.depth, 4))
    emit(f"### 2. Крупнейшие пути под /usr (du --max-depth={depth}, хвост sort -h)")
    cmd2 = (
        f"du -xh --max-depth={depth} /usr 2>/dev/null | sort -h | tail -n {args.top_du}"
    )
    du2, err2, c2 = run_remote(client, cmd2)
    if err2.strip():
        emit(err2.strip())
    for ln in lines(du2):
        emit(f"  {ln}")
    emit()

    # --- опционально /usr/lib
    if args.depth_lib > 0:
        dlib = max(1, min(args.depth_lib, 5))
        emit(f"### 2b. Детализация /usr/lib (max-depth={dlib})")
        cmd2b = (
            f"du -xh --max-depth={dlib} /usr/lib 2>/dev/null | sort -h | tail -n {args.top_du}"
        )
        du2b, e2b, _ = run_remote(client, cmd2b)
        if e2b.strip():
            emit(e2b.strip())
        for ln in lines(du2b):
            emit(f"  {ln}")
        emit()

    # --- dpkg
    emit("### 3. Крупнейшие установленные пакеты (dpkg, поле Installed-Size в КБ)")
    emit(
        "    Удалять только через apt remove / autoremove, не rm -rf в /usr."
    )
    cmd3 = (
        "if command -v dpkg-query >/dev/null 2>&1; then "
        "dpkg-query -Wf '${Installed-Size}\t${Package}\n' 2>/dev/null | sort -rn | head -n "
        f"{args.top_packages}; else echo 'NO_DPKG'; fi"
    )
    dpk, err3, _ = run_remote(client, cmd3)
    if "NO_DPKG" in dpk:
        emit("  (dpkg не найден — не Debian/Ubuntu или минимальный образ)")
    else:
        for ln in lines(dpk):
            emit(f"  {ln}")
    emit()

    # --- эвристики
    emit("### 4. На что обратить внимание (эвристики, не диагноз)")
    notes: list[str] = []
    for size, path in rows1:
        if path == "/usr":
            continue
        name = Path(path).name
        kb = size_to_kb_approx(size)
        if name == "local" and kb and kb > 100 * 1024:
            notes.append(
                f"  • {path} занимает ~{size}: вручную установленное ПО — просмотрите "
                "`ls -la /usr/local` и документацию проектов."
            )
        if kb and total_usr_kb > 0 and kb / total_usr_kb > 0.35 and path != "/usr":
            notes.append(
                f"  • {path} (~{size}) даёт существенную долю /usr — см. расшифровку выше и "
                f"при необходимости `du -xh --max-depth=2 {path} | sort -h | tail` на сервере."
            )
    # дубликаты убрать
    seen_n = set()
    for n in notes:
        if n not in seen_n:
            seen_n.add(n)
            emit(n)
    if not notes:
        emit("  Особых выбросов по простым правилам не найдено; смотрите таблицу пакетов и du.")
    emit()
    emit(
        "### 5. Безопасные направления для высвобождения (общие советы)\n"
        "  • apt autoremove && apt autoclean — снятые зависимости и старый кеш .deb (кеш в /var).\n"
        "  • Старые linux-image-* / linux-headers-* после стабильной работы нового ядра.\n"
        "  • Документация: удаление неиспользуемых *-doc или localepurge (осторожно с локалями).\n"
        "  • Docker: образы/контейнеры — docker system df; данные не в /usr, а в /var/lib/docker."
    )

    client.close()

    if args.output:
        args.output.write_text("\n".join(out_parts) + "\n", encoding="utf-8")
        print(f"\nСохранено: {args.output.resolve()}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
