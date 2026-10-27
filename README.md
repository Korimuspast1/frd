# frdfetch

`frdfetch.py` — мини-аналог **neofetch** для Termux: показывает характеристики
устройства и окружения прямо в терминале телефона.

```
        -o          o-             u0_a312@vayu
         +hydNNNNdyh+              ------------
       +mMMMMMMMMMMMMm+            Устройство:        Xiaomi M2101K6G (vayu)
     `dMMm:NMMMMMMN:mMMd`          OS:                Android 13 «Tiramisu» (API 33)
     hMMMMMMMMMMMMMMMMMh           Прошивка:          MIUI / HyperOS V140
 ..  yyyyyyyyyyyyyyyyyyyy  ..      Ядро:              4.14.190-perf+ (aarch64)
.mMMm`MMMMMMMMMMMMMMMMMMM`mMMm.    Время работы:      5 дн. 10 ч 15 мин
:MMMM-MMMMMMMMMMMMMMMMMMMMM-MMMM:  Процессы:          312 (ср. нагрузка 1.20 1.05 0.98)
:MMMM-MMMMMMMMMMMMMMMMMMMMM-MMMM:  Оболочка:          bash 5.2.15
:MMMM-MMMMMMMMMMMMMMMMMMMMM-MMMM:  Терминал:          Termux 0.118.0
-mMMM-MMMMMMMMMMMMMMMMMMMMM-MMMm-  Пакеты:            137 (pkg), 42 (pip)
 +yy+ MMMMMMMMMMMMMMMMMM +yy+      Разрешение:        1080×2400 @ 440 dpi, 120 Hz
      mMMMMMMMMMMMMMMMMm           Тема:              тёмная
                                   CPU:               Qualcomm SM8150 (8 яд.) — 1×2.84 GHz, 3×2.42 GHz, 4×1.80 GHz [42.1°C]
                                   GPU:               Adreno (TM) 640, OpenGL ES 3.2
                                   Память:            5.0 GiB / 7.4 GiB (67%) | swap 1.0 GiB / 2.0 GiB
                                   Накопитель:        45 GiB / 128 GiB (35%), св. 83 GiB
                                   Батарея:           78% (зарядка, 29.4°C)
                                   Сеть:              HomeNet — 192.168.1.42 — -55 dBm
                                   Локаль:            ru-RU
                                   Root:              нет
```

## Что показывает

| Строка | Откуда берётся |
|---|---|
| Устройство, сборка, патч, загрузчик, модем, локаль | `getprop` |
| Прошивка | автоопределение: MIUI/HyperOS, One UI, OxygenOS, LineageOS, crDroid, stock |
| Ядро, архитектура | `platform.release()` / `platform.machine()` |
| Время работы, процессы, нагрузка, память, CPU (модель, ядра, частоты, t°) | `/proc`, `/sys` |
| GPU | sysfs (`/sys/class/kgsl/...`, Mali и др.) + `ro.opengles.version` |
| Разрешение, dpi, герцовка, тема | `wm size`, `settings`, `ro.sf.lcd_density` |
| Батарея | `termux-battery-status`, иначе `/sys/class/power_supply/battery` |
| Сеть (SSID, IP, уровень сигнала) | `termux-wifi-connectioninfo`, иначе `getprop`/`ip` |
| Пакеты | `dpkg` (+ `pip`, `npm` с ключом `--all`) |
| Root | `id -u`, наличие `su` |

Всё необязательное опрашивается с таймаутом и молча пропускается,
если данных нет (нет root, нет Termux:API, закрыт sysfs и т.п.).

## Установка в Termux

```bash
pkg update && pkg install python        # если Python ещё не стоит
# опционально, для батареи/Wi-Fi/сенсоров:
pkg install termux-api                  # + приложение Termux:API из F-Droid

# сам скрипт
curl -O https://raw.githubusercontent.com/Korimuspast1/frd/main/frdfetch.py
chmod +x frdfetch.py
./frdfetch.py
```

Или просто:

```bash
bash install.sh          # положит скрипт в $PREFIX/bin/frdfetch
frdfetch
```

Чтобы вывод появлялся при каждом запуске Termux:

```bash
echo 'frdfetch' >> ~/.bashrc
```

## Использование

```
python3 frdfetch.py [опции]
```

| Опция | Что делает |
|---|---|
| `--json` | вывести всё в JSON (для скриптов) |
| `--no-logo` / `--logo android\|termux\|tux\|none\|auto` | управление логотипом |
| `--no-color`, `--color auto\|always\|never` | раскраска (уважает `NO_COLOR` и не-TTY) |
| `--no-api` | не дёргать команды Termux:API |
| `--all` | добавить медленные проверки: pip/npm, список сенсоров |
| `--no-blocks` | без цветных блоков внизу |
| `--version`, `-h` | версия и справка |

Примеры:

```bash
python3 frdfetch.py                 # как на скриншоте выше
python3 frdfetch.py --json          # machine-readable
python3 frdfetch.py --logo termux   # логотип Termux
python3 frdfetch.py --no-color      # чистый текст (для копирования)
```

## Если запустить не в Termux

Скрипт определяет, что он не на Android, и показывает обычный Linux-вывод
(дистрибутив из `/etc/os-release`, ядро, CPU, память, диски) с логотипом Tux.

Требования: Python 3.8+, только стандартная библиотека.
