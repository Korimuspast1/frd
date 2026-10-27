#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
frdfetch — «neofetch для Termux».

Показывает характеристики устройства и окружения Termux/Android:
модель, версию Android и прошивку, ядро, SoC, GPU, память, накопитель,
батарею, Wi-Fi, разрешение экрана, оболочку, пакеты и т.д.

Зависимости: только стандартная библиотека Python 3.8+.
Опционально (если установлено приложение Termux:API): termux-battery-status,
termux-wifi-connectioninfo, termux-sensor — скрипт сам их найдёт,
а если их нет — возьмёт данные из /sys, /proc и getprop.

Запуск:
    python3 frdfetch.py
    python3 frdfetch.py --json          # машиночитаемый вывод
    python3 frdfetch.py --no-logo       # без логотипа
    python3 frdfetch.py --all           # + медленные проверки (pip, сенсоры)
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime

__version__ = "1.0.0"

# --------------------------------------------------------------------------- #
#  Мелкие утилиты
# --------------------------------------------------------------------------- #

PREFIX = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")

IS_TERMUX = (
    os.environ.get("PREFIX", "").startswith("/data/data/com.termux")
    or os.path.isdir("/data/data/com.termux/files/usr")
    or "com.termux" in os.environ.get("HOME", "")
)
IS_ANDROID = IS_TERMUX or os.path.exists("/system/build.prop") or shutil.which("getprop") is not None


def run(cmd, timeout: float = 2.5):
    """Запустить команду и вернуть stdout. Любой провал -> пустая строка."""
    try:
        proc = subprocess.run(
            cmd,
            shell=isinstance(cmd, str),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            text=True,
            errors="replace",
        )
    except Exception:
        return ""
    return (proc.stdout or "").strip()


def read_file(path: str) -> str:
    try:
        with open(path, "r", errors="replace") as fh:
            return fh.read().strip()
    except Exception:
        return ""


def first(*values):
    """Первое непустое значение."""
    for v in values:
        if callable(v):
            try:
                v = v()
            except Exception:
                v = ""
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return ""


def human_bytes(num: float) -> str:
    num = float(num)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if abs(num) < 1024.0:
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} EiB"


def fmt_freq(mhz: float) -> str:
    if mhz >= 1000:
        return f"{mhz / 1000:.2f}".rstrip("0").rstrip(".") + " GHz"
    return f"{int(mhz)} MHz"


def disk_usage(path: str):
    try:
        usage = shutil.disk_usage(path)
        return usage.total, usage.used, usage.free
    except Exception:
        return None


def disk_str(path: str) -> str:
    data = disk_usage(path)
    if not data:
        return ""
    total, used, free = data
    percent = (used / total * 100) if total else 0
    return f"{human_bytes(used)} / {human_bytes(total)} ({percent:.0f}%), св. {human_bytes(free)}"


# --------------------------------------------------------------------------- #
#  Цвета
# --------------------------------------------------------------------------- #

class Color:
    enabled = True

    RESET = "\033[0m"
    BOLD = "\033[1m"

    @staticmethod
    def rgb(r: int, g: int, b: int) -> str:
        return f"\033[38;2;{r};{g};{b}m"

    @classmethod
    def paint(cls, text: str, r: int, g: int, b: int, bold: bool = False) -> str:
        if not cls.enabled:
            return text
        return f"{cls.BOLD if bold else ''}{cls.rgb(r, g, b)}{text}{cls.RESET}"

    @classmethod
    def label(cls, text: str) -> str:
        # бирюзовый, как у neofetch
        return cls.paint(text, 90, 200, 210, bold=True)

    @classmethod
    def value(cls, text: str) -> str:
        if not cls.enabled:
            return text
        return f"\033[0m{text}{cls.RESET}"

    @classmethod
    def header(cls, text: str) -> str:
        return cls.paint(text, 61, 220, 132, bold=True)


# --------------------------------------------------------------------------- #
#  Сбор данных: Android / Termux
# --------------------------------------------------------------------------- #

_PROPS = None


def props() -> dict:
    """Все getprop-свойства одним вызовом (кешируется)."""
    global _PROPS
    if _PROPS is not None:
        return _PROPS
    _PROPS = {}
    out = run(["getprop"] if shutil.which("getprop") else "/system/bin/getprop", timeout=4)
    for line in out.splitlines():
        m = re.match(r"^\[([^\]]+)\]:\s*\[(.*)\]\s*$", line.strip())
        if m:
            _PROPS[m.group(1)] = m.group(2)
    return _PROPS


def prop(key: str, default: str = "") -> str:
    return first(props().get(key), default)


ANDROID_NAMES = {
    "21": ("5.0", "Lollipop"), "22": ("5.1", "Lollipop"),
    "23": ("6.0", "Marshmallow"), "24": ("7.0", "Nougat"), "25": ("7.1", "Nougat"),
    "26": ("8.0", "Oreo"), "27": ("8.1", "Oreo"), "28": ("9", "Pie"),
    "29": ("10", "Queen Cake"), "30": ("11", "Red Velvet Cake"),
    "31": ("12", "Snow Cone"), "32": ("12L", "Snow Cone v2"),
    "33": ("13", "Tiramisu"), "34": ("14", "Upside Down Cake"),
    "35": ("15", "Vanilla Ice Cream"), "36": ("16", "Baklava"),
}


class Info:
    """Накопитель строк вида (подпись, значение)."""

    def __init__(self):
        self.rows = []

    def add(self, label: str, value, skip_empty: bool = True):
        if value is None:
            return
        text = str(value).strip()
        if skip_empty and text == "":
            return
        self.rows.append((label, text))


def is_emulator() -> bool:
    return prop("ro.kernel.qemu") == "1" or "sdk_gphone" in prop("ro.product.device").lower()


def detect_rom() -> str:
    p = props()
    if p.get("ro.miui.ui.version.name"):
        return f"MIUI / HyperOS {p['ro.miui.ui.version.name']}"
    for k in ("ro.build.version.oneui", "ro.vendor.build.version.oneui"):
        if p.get(k):
            return f"One UI {p[k]}"
    if p.get("ro.oxygen.version") or p.get("ro.build.version.ota", "").upper().startswith("OXYGEN"):
        return f"OxygenOS {p.get('ro.oxygen.version', '')}".strip()
    if p.get("ro.lineage.version") or p.get("ro.lineage.build.version"):
        return f"LineageOS {p.get('ro.lineage.version') or p.get('ro.lineage.build.version')}"
    if p.get("ro.crdroid.version"):
        return f"crDroid {p['ro.crdroid.version']}"
    if p.get("ro.modversion"):
        return str(p["ro.modversion"])
    if p.get("ro.evolution.version"):
        return f"Evolution X {p['ro.evolution.version']}"
    if p.get("ro.build.flavor", "").endswith("userdebug"):
        return f"{prop('ro.product.brand')} (userdebug)"
    return "Stock Android"


def cpu_info() -> str:
    hardware = ""
    for line in read_file("/proc/cpuinfo").splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip().lower(), val.strip()
        if key == "hardware" and val and "generic" not in val.lower():
            hardware = val
        elif key in ("processor", "cpu part") and not hardware:
            pass

    soc = first(
        lambda: (prop("ro.soc.manufacturer") + " " + prop("ro.soc.model")).strip(),
        lambda: prop("ro.soc.model"),
        lambda: prop("ro.hardware.chipname").upper(),
        lambda: prop("ro.vendor.hardware.chipname").upper(),
        hardware,
        lambda: prop("ro.board.platform"),
        lambda: prop("ro.hardware").upper(),
        lambda: prop("ro.product.board"),
        "",
    )

    # число ядер: считаем каталоги cpuN, иначе os.cpu_count()
    cores = len([d for d in os.listdir("/sys/devices/system/cpu")
                 if re.fullmatch(r"cpu\d+", d)]) if os.path.isdir("/sys/devices/system/cpu") else 0
    if not cores:
        cores = os.cpu_count() or 1

    # кластеры ядер по максимальной частоте
    freqs = []
    for i in range(min(cores, 32)):
        raw = read_file(f"/sys/devices/system/cpu/cpu{i}/cpufreq/cpuinfo_max_freq")
        if raw.isdigit() and int(raw) > 0:
            freqs.append(int(raw) // 1000)
    clusters = ""
    if freqs:
        parts = [f"{count}×{fmt_freq(mhz)}" for mhz, count in sorted(Counter(freqs).items(), reverse=True)]
        clusters = ", ".join(parts)

    temp = ""
    raw_temp = read_file("/sys/class/thermal/thermal_zone0/temp")
    if raw_temp.replace("-", "").isdigit():
        value = int(raw_temp)
        temp = f"{value / 1000:.1f}°C" if value > 1000 else f"{value}°C"

    name = soc or platform.machine()
    result = f"{name} ({cores} яд.)"
    if clusters:
        result += f" — {clusters}"
    if temp:
        result += f" [{temp}]"
    return result


def gpu_info() -> str:
    paths = (
        "/sys/class/kgsl/kgsl-3d0/gpu_model",
        "/sys/kernel/gpu/gpu_model",
        "/sys/kernel/gpu/gpu_model_name",
        "/sys/devices/soc/soc:qcom,kgsl-3d0/kgsl/kgsl-3d0/gpu_model",
        "/sys/class/misc/mali0/device/gpu_model",
        "/proc/gpufreq/gpufreq_var_dump",
        "/sys/module/pvrsrvkm/parameters/sGpuName",
    )
    model = first(*[lambda p=p: read_file(p) for p in paths], "")

    gl = ""
    raw_gl = prop("ro.opengles.version")
    if raw_gl.isdigit():
        value = int(raw_gl)
        gl = f"OpenGL ES {value >> 16}.{value & 0xFFFF}"

    if not model:
        vendor = prop("ro.hardware").upper()
        model = f"{vendor} GPU" if vendor else ""
    return ", ".join(x for x in (model, gl) if x) or ""


def memory_info() -> str:
    mem = {}
    for line in read_file("/proc/meminfo").splitlines():
        m = re.match(r"^(\w+):\s+(\d+)\s*kB", line)
        if m:
            mem[m.group(1)] = int(m.group(2)) * 1024
    if "MemTotal" not in mem:
        return ""
    total = mem["MemTotal"]
    if not total:
        return ""
    avail = mem.get("MemAvailable", 0)
    used = max(total - avail, 0)
    text = f"{human_bytes(used)} / {human_bytes(total)} ({used / total * 100:.0f}%)"
    if mem.get("SwapTotal", 0) > 0:
        swap_used = mem["SwapTotal"] - mem.get("SwapFree", mem["SwapTotal"])
        text += f" | swap {human_bytes(swap_used)} / {human_bytes(mem['SwapTotal'])}"
    return text


def uptime_str() -> str:
    raw = read_file("/proc/uptime")
    if not raw:
        return ""
    seconds = int(float(raw.split()[0]))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    chunks = []
    if days:
        chunks.append(f"{days} дн.")
    if hours:
        chunks.append(f"{hours} ч")
    chunks.append(f"{minutes} мин")
    return " ".join(chunks)


def resolution_str() -> str:
    size = run(["wm", "size"], timeout=2)
    res = ""
    m = re.search(r"(\d{3,5})\s*x\s*(\d{3,5})", size)
    if m:
        res = f"{m.group(1)}×{m.group(2)}"
    if not res:
        raw = first(
            lambda: read_file("/sys/class/graphics/fb0/virtual_size"),
            lambda: read_file("/sys/class/graphics/fb0/modes").split("\n")[0],
        )
        m = re.search(r"(\d{3,5})[,x]\s*(\d{3,5})", raw)
        if m:
            res = f"{m.group(1)}×{m.group(2)}"

    dpi = prop("ro.sf.lcd_density")
    if dpi.isdigit():
        res += f" @ {dpi} dpi"

    rate = first(
        lambda: run(["settings", "get", "system", "peak_refresh_rate"], timeout=1.5),
        lambda: run(["settings", "get", "system", "refresh_rate"], timeout=1.5),
    )
    if re.fullmatch(r"[\d.]+", rate or "") and float(rate) > 0:
        res += f", {float(rate):.0f} Hz"
    return res


def theme_str() -> str:
    mode = run(["settings", "get", "secure", "ui_night_mode"], timeout=1.5)
    if mode.isdigit():
        return {0: "авто", 1: "светлая", 2: "тёмная", 3: "по расписанию"}.get(int(mode), mode)
    night = run(["cmd", "uimode", "night"], timeout=1.5).lower()
    if "yes" in night:
        return "тёмная"
    if "no" in night:
        return "светлая"
    return ""


def battery_str(use_api: bool) -> str:
    if use_api and shutil.which("termux-battery-status"):
        raw = run(["termux-battery-status"], timeout=3)
        try:
            data = json.loads(raw)
            percent = data.get("percentage")
            if percent is not None:
                status = {
                    "CHARGING": "зарядка", "DISCHARGING": "разряд",
                    "FULL": "полный", "NOT_CHARGING": "не заряжается",
                }.get(str(data.get("status", "")).upper(), str(data.get("status", "")).lower())
                text = f"{percent:.0f}%"
                if status:
                    text += f" ({status}"
                    temp = data.get("temperature")
                    if isinstance(temp, (int, float)):
                        text += f", {temp:.1f}°C"
                    curr = data.get("current")
                    if isinstance(curr, (int, float)) and curr != 0:
                        text += f", {abs(curr) / 1000:.0f} мА"
                    text += ")"
                return text
        except Exception:
            pass

    base = "/sys/class/power_supply/battery"
    percent = first(lambda: read_file(f"{base}/capacity"), lambda: read_file(f"{base}/batt_capacity"))
    match = re.match(r"\s*(\d+(?:[.,]\d+)?)", percent or "")
    if not match:
        return ""
    text = f"{float(match.group(1).replace(',', '.')):.0f}%"
    status = read_file(f"{base}/status").lower()
    if status:
        ru = {
            "charging": "зарядка", "discharging": "разряд", "full": "полный",
            "not charging": "не заряжается",
        }.get(status, status)
        text += f" ({ru}"
        raw_temp = read_file(f"{base}/temp")
        if raw_temp.replace("-", "").isdigit():
            value = int(raw_temp)
            # в sysfs температура батареи — в десятых долях °C
            text += f", {value / 10:.1f}°C" if abs(value) >= 100 else f", {value}°C"
        text += ")"
    return text


def wifi_str(use_api: bool) -> str:
    if use_api and shutil.which("termux-wifi-connectioninfo"):
        raw = run(["termux-wifi-connectioninfo"], timeout=3)
        try:
            data = json.loads(raw)
            ssid = data.get("ssid") or ""
            if ssid and ssid != "<unknown ssid>":
                parts = [str(ssid)]
                ip = data.get("ip")
                if ip:
                    parts.append(str(ip))
                rssi = data.get("rssi")
                if isinstance(rssi, (int, float)):
                    parts.append(f"{int(rssi)} dBm")
                link = data.get("linkspeed_mbps")
                if link:
                    parts.append(f"{link} Мбит/с")
                return " — ".join(parts)
        except Exception:
            pass

    ip = prop("dhcp.wlan0.ipaddress")
    if not ip:
        m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)",
                      run(["ip", "-4", "addr", "show", "wlan0"], timeout=1.5))
        if m:
            ip = m.group(1)
    iface = run(["ip", "route", "get", "1.1.1.1"], timeout=1.5)
    dev = ""
    m = re.search(r"dev\s+(\S+)", iface)
    if m:
        dev = m.group(1)
    if ip:
        return f"{ip} ({dev})" if dev else ip
    return ""


def termux_version() -> str:
    raw = run(["termux-info"], timeout=3)
    if raw.startswith("{"):
        try:
            data = json.loads(raw)
            version = first(data.get("APP_VERSION_NAME"), data.get("TERMUX_APP_VERSION_NAME"))
            if version:
                return str(version)
        except Exception:
            pass
    dpkg_ver = run(["dpkg-query", "-W", "-f=${Version}", "termux-app"], timeout=2)
    if dpkg_ver:
        return dpkg_ver
    return ""


def packages_str(full: bool) -> str:
    parts = []

    # пакеты apt/dpkg (Termux)
    status_path = os.path.join(PREFIX, "var/lib/dpkg/status")
    try:
        with open(status_path, "r", errors="replace") as fh:
            count = sum(1 for line in fh if line.startswith("Package:"))
        if count:
            parts.append(f"{count} (pkg)")
    except Exception:
        pass

    if full:
        # Python-пакеты
        try:
            import sysconfig
            purelib = sysconfig.get_paths().get("purelib", "")
            if purelib and os.path.isdir(purelib):
                pip_count = len([d for d in os.listdir(purelib) if d.endswith((".dist-info", ".egg-info"))])
                if pip_count:
                    parts.append(f"{pip_count} (pip)")
        except Exception:
            pass
        # Node-модули глобально
        node_root = os.path.join(PREFIX, "lib/node_modules")
        if os.path.isdir(node_root):
            try:
                node_count = len([d for d in os.listdir(node_root) if not d.startswith(".")])
                if node_count:
                    parts.append(f"{node_count} (npm)")
            except Exception:
                pass

    return ", ".join(parts)


def process_count() -> str:
    try:
        return str(len([d for d in os.listdir("/proc") if d.isdigit()]))
    except Exception:
        return ""


def load_avg() -> str:
    raw = read_file("/proc/loadavg")
    if not raw:
        return ""
    parts = raw.split()
    return " ".join(parts[:3]) if len(parts) >= 3 else raw


def sensor_count() -> str:
    raw = run(["termux-sensor", "-l"], timeout=4)
    if not raw:
        return ""
    names = [line.strip() for line in raw.splitlines() if line.strip() and not line.startswith("{")]
    return f"{len(names)}"


def collect_android(args) -> Info:
    info = Info()
    p = props()

    brand = prop("ro.product.brand")
    manufacturer = prop("ro.product.manufacturer")
    model = prop("ro.product.model")
    device = prop("ro.product.device")
    vendor = (manufacturer or brand).capitalize()
    title = " ".join(x for x in (vendor, model) if x)
    if device and device.lower() not in (model or "").lower():
        title += f" ({device})"
    if is_emulator():
        title += " [эмулятор]"

    user = first(os.environ.get("USER"), os.environ.get("LOGNAME"),
                 lambda: run(["whoami"], timeout=1), "shell")
    host = first(prop("net.hostname"), platform.node(), device, "localhost")

    release = prop("ro.build.version.release")
    sdk = prop("ro.build.version.sdk")
    name = ""
    if sdk in ANDROID_NAMES:
        ver, dessert = ANDROID_NAMES[sdk]
        name = f"{ver} «{dessert}»" if ver != release else f"«{dessert}»"

    info.add("Устройство", title or prop("ro.product.name"))
    info.add("OS", " ".join(x for x in (
        f"Android {release}" if release else "Android", name, f"(API {sdk})" if sdk else "") if x))
    info.add("Прошивка", detect_rom())
    info.add("Сборка", first(prop("ro.build.display.id"), prop("ro.build.id")))
    info.add("Ядро", f"{platform.release()} ({platform.machine()})")
    info.add("Патч безопасности", prop("ro.build.version.security_patch"))
    info.add("Время работы", uptime_str())
    procs, load = process_count(), load_avg()
    info.add("Процессы", f"{procs} (ср. нагрузка {load})" if procs and load else procs)
    info.add("Оболочка", shell_str())
    info.add("Терминал", terminal_str())
    info.add("Пакеты", packages_str(args.all))
    info.add("Разрешение", resolution_str())
    info.add("Тема", theme_str())
    info.add("CPU", cpu_info())
    info.add("GPU", gpu_info())
    info.add("Память", memory_info())
    info.add("Накопитель", disk_str(os.environ.get("HOME", PREFIX)))
    if os.path.isdir("/storage/emulated/0"):
        info.add("SD-карта", disk_str("/storage/emulated/0"))
    info.add("Батарея", battery_str(not args.no_api))
    info.add("Сеть", wifi_str(not args.no_api))
    info.add("Локаль", first(prop("persist.sys.locale"), prop("ro.product.locale"),
                             os.environ.get("LANG"), ""))
    info.add("Root", root_str())
    info.add("Загрузчик", prop("ro.bootloader"))
    info.add("Модем", prop("gsm.version.baseband"))
    if args.all:
        info.add("Сенсоры", sensor_count())
    info.add("Python", platform.python_version())

    # шапка user@host — всегда в самое начало
    info.rows.insert(0, (f"{user}@{host}", ""))
    return info


def shell_str() -> str:
    shell = os.environ.get("SHELL", "")
    name = os.path.basename(shell) if shell else "sh"
    version = ""
    if "bash" in name:
        version = os.environ.get("BASH_VERSION", "").split("(")[0]
        if not version:
            version = run(["bash", "-c", "echo $BASH_VERSION"], timeout=1.5)
    elif "zsh" in name:
        version = run(["zsh", "-c", "echo $ZSH_VERSION"], timeout=1.5)
    return f"{name} {version}".strip()


def terminal_str() -> str:
    if IS_TERMUX:
        version = termux_version()
        return f"Termux {version}".strip() if version else "Termux"
    return first(os.environ.get("TERM_PROGRAM"), os.environ.get("TERM"), "")


def root_str() -> str:
    if os.geteuid() == 0:
        return "да (uid 0)"
    for path in ("/system/xbin/su", "/system/bin/su", "/sbin/su", "/su/bin/su", "/data/local/su"):
        if os.path.exists(path):
            return "доступен (su)"
    if shutil.which("su"):
        return "доступен (su)"
    return "нет"


# --------------------------------------------------------------------------- #
#  Сбор данных: обычный Linux (если скрипт запущен не в Termux)
# --------------------------------------------------------------------------- #

def collect_linux(args) -> Info:
    info = Info()
    user = first(os.environ.get("USER"), os.environ.get("LOGNAME"), lambda: run(["whoami"]), "user")
    host = platform.node() or "localhost"
    info.add(f"{user}@{host}", "", skip_empty=False)

    os_name = ""
    if os.path.exists("/etc/os-release"):
        data = {}
        for line in read_file("/etc/os-release").splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                data[k.strip()] = v.strip().strip('"')
        os_name = data.get("PRETTY_NAME", data.get("NAME", ""))
    if not os_name:
        os_name = first(lambda: run(["lsb_release", "-sd"]).strip('"'), "")

    info.add("OS", f"{os_name} {platform.machine()}".strip())
    info.add("Хост", host_model())
    info.add("Ядро", platform.release())
    info.add("Время работы", uptime_str())
    procs, load = process_count(), load_avg()
    info.add("Процессы", f"{procs} (ср. нагрузка {load})" if procs and load else procs)
    info.add("Оболочка", shell_str())
    info.add("Терминал", terminal_str())
    info.add("Окно/DE", first(os.environ.get("XDG_CURRENT_DESKTOP"), os.environ.get("DESKTOP_SESSION"), ""))
    info.add("CPU", cpu_info())
    info.add("GPU", gpu_info())
    info.add("Память", memory_info())
    info.add("Накопитель", disk_str("/"))
    info.add("Пакеты", packages_str(args.all))
    info.add("Python", platform.python_version())
    return info


def host_model() -> str:
    for path in ("/sys/devices/virtual/dmi/id/product_name",
                 "/sys/devices/virtual/dmi/id/board_name",
                 "/proc/device-tree/model"):
        value = read_file(path).replace("\x00", "").strip()
        if value and value != "None":
            return value
    return ""


# --------------------------------------------------------------------------- #
#  Логотипы
# --------------------------------------------------------------------------- #

def android_logo():
    body = "M" * 21
    mid = ":MMMM-" + body + "-MMMM:"
    low = "-mMMM-" + body + "-MMMm-"
    return [
        "        -o          o-",
        "         +hydNNNNdyh+",
        "       +mMMMMMMMMMMMMm+",
        "     `dMMm:NMMMMMMN:mMMd`",
        "     hMMMMMMMMMMMMMMMMMh",
        " ..  yyyyyyyyyyyyyyyyyyyy  ..",
        ".mMMm`MMMMMMMMMMMMMMMMMMM`mMMm.",
        mid,
        mid,
        mid,
        mid,
        low,
        " +yy+ MMMMMMMMMMMMMMMMMM +yy+",
        "      mMMMMMMMMMMMMMMMMm",
    ]


def tux_logo():
    return [
        "   a8888b.",
        "  d888888b.",
        "  8P\"YP\"Y88",
        "  8|o||o|88",
        "  8'    .88",
        "  8`._.' Y8.",
        " d/      `8b.",
        "dP   .    Y8b.",
    ]


def termux_logo():
    # figlet "Termux" (шрифт standard); обратные слеши экранированы
    return [
        "  _____",
        " |_   _|__ _ __ _ __ ___  _   ___ __",
        "   | |/ _ \\ '__| '_ ` _ \\| | | \\ \\/ /",
        "   | |  __/ |  | | | | | | |_| |>  <",
        "   |_|\\___|_|  |_| |_| |_|\\__,_/_/\\_\\",
    ]


LOGOS = {"android": android_logo, "termux": termux_logo, "tux": tux_logo, "none": lambda: []}


# --------------------------------------------------------------------------- #
#  Вывод
# --------------------------------------------------------------------------- #

def render(rows, logo_lines, show_blocks: bool, gap: int = 2):
    logo_w = max((len(line) for line in logo_lines), default=0)
    # первая строка без значения — это шапка user@host
    header = rows[0][0] if rows and rows[0][0] and not rows[0][1] else None
    body = rows[1:] if header else rows
    pad = max((len(label) for label, _ in body), default=0)

    info_lines = []
    if header:
        info_lines.append(Color.header(header))
        info_lines.append(Color.header("-" * len(header)))
    for label, value in body:
        if not label:
            info_lines.append("")
            continue
        info_lines.append(
            f"{Color.label(label)}:{' ' * (pad - len(label) + 1)}{Color.value(value)}"
        )

    total = max(len(logo_lines), len(info_lines))
    out = []
    for i in range(total):
        left = logo_lines[i] if i < len(logo_lines) else ""
        right = info_lines[i] if i < len(info_lines) else ""
        left_colored = Color.paint(left, 61, 220, 132) if left else ""
        if left_colored:
            out.append(left_colored + " " * (gap + max(0, logo_w - len(left))) + right)
        else:
            out.append(" " * (logo_w + gap) + right)
    text = "\n".join(line.rstrip() for line in out)

    if show_blocks:
        text += "\n\n" + color_blocks(logo_w, gap)
    return text


def color_blocks(offset: int, gap: int):
    palette = [
        (0, 0, 0), (183, 44, 44), (61, 220, 132), (196, 160, 0),
        (52, 101, 164), (140, 71, 153), (0, 174, 176), (200, 200, 200),
    ]
    pad = " " * (offset + gap)
    dark = "".join(Color.paint("   ", r, g, b) for r, g, b in palette)
    light_palette = [(int(r * 0.55), int(g * 0.55), int(b * 0.55)) for r, g, b in palette]
    light = "".join(Color.paint("   ", r, g, b) for r, g, b in light_palette)
    return pad + dark + "\n" + pad + light


# --------------------------------------------------------------------------- #
#  CLI
# --------------------------------------------------------------------------- #

def build_parser():
    parser = argparse.ArgumentParser(
        prog="frdfetch.py",
        description="Показывает характеристики устройства/окружения (аналог neofetch для Termux).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Примеры:\n"
               "  python3 frdfetch.py\n"
               "  python3 frdfetch.py --json\n"
               "  python3 frdfetch.py --logo termux --no-color\n",
    )
    parser.add_argument("--logo", choices=sorted(LOGOS) + ["auto"], default="auto",
                        help="логотип: android (по умолчанию на Android), tux (на Linux), termux, none")
    parser.add_argument("--no-logo", action="store_true", help="вывод без логотипа")
    parser.add_argument("--color", choices=("auto", "always", "never"), default="auto",
                        help="раскраска вывода (по умолчанию auto)")
    parser.add_argument("--no-color", action="store_true", help="то же, что --color never")
    parser.add_argument("--json", action="store_true", help="вывести данные в JSON")
    parser.add_argument("--no-api", action="store_true",
                        help="не дёргать команды Termux:API (termux-battery-status и т.п.)")
    parser.add_argument("--all", action="store_true",
                        help="добавить медленные проверки (pip/npm, список сенсоров)")
    parser.add_argument("--no-blocks", action="store_true", help="не печатать цветные блоки")
    parser.add_argument("--version", action="version", version=f"frdfetch {__version__}")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.no_color or args.color == "never" or os.environ.get("NO_COLOR"):
        Color.enabled = False
    elif args.color == "always":
        Color.enabled = True
    else:
        Color.enabled = sys.stdout.isatty()

    if args.json:
        Color.enabled = False

    start = time.time()
    try:
        if IS_ANDROID:
            info = collect_android(args)
        else:
            info = collect_linux(args)
    except KeyboardInterrupt:
        return 130
    # шапка (user@host) в первой строке, дальше — только непустые значения
    rows = [(k, v) for k, v in info.rows if k or v]

    if args.json:
        header = rows[0][0] if rows and rows[0][0] and not rows[0][1] else None
        body = rows[1:] if header else rows
        data = {"Пользователь": header} if header else {}
        for label, value in body:
            if label:
                data[label] = value
        data["_generated"] = datetime.now().isoformat(timespec="seconds")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    logo_key = args.logo
    if args.no_logo:
        logo_key = "none"
    elif logo_key == "auto":
        columns = shutil.get_terminal_size((80, 24)).columns
        # на узком экране телефона логотип только мешает
        logo_key = "none" if columns < 70 else ("android" if IS_ANDROID else "tux")
    logo_lines = LOGOS.get(logo_key, lambda: [])()

    show_blocks = Color.enabled and not args.no_blocks
    print(render(rows, logo_lines, show_blocks))
    print()

    if os.environ.get("FRDFETCH_TIMING"):
        print(f"[собрано за {time.time() - start:.2f} с]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
