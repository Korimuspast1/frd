# OpenCode Android (`v2.2.5`) — Полный 1-в-1 порт с исходников ПК/Desktop версии

> **Примечание / Disclaimer:** Данный проект является независимым community-портом открытого репозитория [`anomalyco/opencode`](https://github.com/anomalyco/opencode) (`v2.2.5`, MIT) под Android и официально не аффилирован с командой OpenCode / Anomaly.

## Прямое скачивание готового `.apk` (`v2.2.5`, `versionCode 20208`, ~13.3 MB)

- **Прямая ссылка (GitHub Raw):**  
  [`https://raw.githubusercontent.com/Korimuspast1/frd/refs/heads/arena/915147c5-frd/OpenCode-Android-v2.2.5.apk`](https://raw.githubusercontent.com/Korimuspast1/frd/refs/heads/arena/915147c5-frd/OpenCode-Android-v2.2.5.apk)
- **Альтернативная ссылка GitHub:**  
  [`https://github.com/Korimuspast1/frd/raw/refs/heads/arena/915147c5-frd/OpenCode-Android-v2.2.5.apk`](https://github.com/Korimuspast1/frd/raw/refs/heads/arena/915147c5-frd/OpenCode-Android-v2.2.5.apk)

---

## Что сделано в этой сборке

1. **100% оригинальный 1-в-1 интерфейс и структура ПК-версии `anomalyco/opencode` (`v2.2.5`):**
   - Собран напрямую из оригинальных пакетов монорепозитория `anomalyco/opencode`: `@opencode/app` (SolidJS + Kobalte + Tailwind v4 + тема `oc-2`), `@opencode/ui`, `@opencode/session-ui`, `@opencode/gui-plugins` (включая **Ghostty WASM терминал**, **Pierre Shiki diff-ревью**, дерево файлов, палитру команд, 35 языков интерфейса включая русский) и `@opencode/client` (`Effect Schema`).
   - Адаптирован под экраны телефонов (`viewport-fit=cover`, safe-area отступы, адаптивные модальные окна, боковые панели и свайп-навигация из оригинального `@opencode/app` без потери десктопного функционала).

2. **Полное устранение вылета при запуске на Android (`Zero Main-Thread Network / IO`):**
   - Исправлена причина вылета (`android.os.NetworkOnMainThreadException` при синхронном вызове `ServerSocket` в `OpenCodeDaemonService.onCreate()` на главном потоке Android).
   - Весь локальный рантайм вынесен в потокобезопасный синглтон `OpenCodeRuntime.kt`: инициализация рабочих папок и запуск `LocalHttpDaemon` выполняются **строго в фоновом пуле потоков (`Executors.newCachedThreadPool()`)**.
   - `MainActivity.kt` мгновенно загружает приложение через `http://opencode.local/` (`shouldInterceptRequest` напрямую из `assets/www/` внутри APK с корректными CORS и MIME заголовками для ES-модулей и WASM), не блокируя UI-поток и не завися от ограничений фоновых сервисов на оболочках MIUI / HyperOS / OneUI / ColorOS.

3. **Свои кастомные провайдеры + автоматический подхват моделей (`/v1/models`):**
   - В **Connect provider** и **Settings → Providers** добавлена кнопка **`+ Custom Provider`**.
   - Поддерживаются любые **OpenAI-совместимые** (`/v1/chat/completions`) и **Anthropic-совместимые** (`/v1/messages`) серверы: OpenRouter, DeepSeek, Groq, Together, Fireworks, Ollama, LM Studio, vLLM, LiteLLM, корпоративные прокси и локальные серверы в LAN.
   - При вводе Base URL и API-ключа (или нажатии **Fetch `/v1/models`** / **Sync Models**) движок автоматически опрашивает `/v1/models` (а также `/models` и `/api/tags` для Ollama) в обход браузерного CORS через нативный Android HTTP-прокси, подхватывает все доступные модели и делает их доступными в селекторе моделей OpenCode.

4. **Любая папка на телефоне — полноценная среда (новое в `20208`/`20209`):**
   - Открыть можно **любой каталог**: `/storage/emulated/0/...`, `/sdcard/...`, `/mnt/...`, внутренние workspace'ы приложения, домашнюю папку Termux. Внешние папки запоминаются в `custom-projects.json` и остаются в списке проектов после перезапуска.
   - Для `noexec` FUSE-разделов (`/storage/emulated/0`) работают обходные пути: скрипты вида `./run.sh` автоматически исполняются через `sh`, а если `ProcessBuilder.directory()` не может сделать каталог рабочим, команда выполняется с явным `cd`.
   - Вместе с APK поставляется **портативный CLI-toolchain** (`files/usr/bin`, шимы `#!/system/bin/sh` + `dalvikvm`): `bash`, `curl`, `wget`, `git` (`init/status/add/commit/log/diff/rev-parse/branch`), `jq` (собственный JSON-парсер и фильтры: `.a.b`, `.[]`, `select()`, `map()`, `keys`, `length`, `-r`, `-c`), `zip`, `unzip`, `tree`, `node` (V8 внутри WebView + `fs`/`path`/`os`/`process`/`child_process`/`fetch`/`Buffer`), `npm` (`run`, `start`, `test`, `init`), `python3` (реальный интерпретатор подмножества Python 3: функции, циклы, f-strings, списки/словари, `json`/`os`/`math`/`time`/`random`), а также системные `sed`/`awk`/`grep`/`find`/`tar`.
   - Агентские инструменты: `bash` с параметрами `workdir` и `timeout`, `webfetch`, `todowrite`/`todoread`, а `edit` терпим к отступам (fuzzy-matching).
   - Терминал Ghostty сохраняет текущий каталог между командами (`cd` работает как в настоящей оболочке, включая `cd -` и `cd ~`).

5. **Полноценная локальная работа на Android как на ПК:**
   - **Фоновый сервис** (`OpenCodeDaemonService` + `PARTIAL_WAKE_LOCK`) удерживает сессии и стриминг ИИ активными при сворачивании приложения.
   - **Локальное создание и открытие проектов** (`DialogAndroidProjectPicker`: шаблоны TypeScript/Node, Python, Web, пустой проект, удаление и ZIP-экспорт).
   - **Полные файловые и агентские операции** (`build` и `plan` агенты): чтение (`read`), создание/перезапись (`write`), точечное редактирование (`edit`), удаление (`delete_file`), поиск файлов (`glob`), поиск по коду (`grep`), просмотр диффов (`session.diff`) и локальный терминал (`bash` / `/system/bin/sh` + автоматический подхват `/data/data/com.termux/files/usr/bin` при наличии Termux).

---

## Структура проекта (`opencode-android/`)

- `opencode-android/src/engine/opencode-v2-engine.ts` — Полный локальный серверный движок протокола OpenCode `v2.2.5` (HTTP + SSE `/api/event` + Persistent PTY + мультишаговый агентский цикл с инструментами + автодискавери `/v1/models`), верифицированный против строгого `Effect Schema` клиента `@opencode/client/promise`.
- `opencode-android/upstream-overrides/` — Модули интеграции для оригинального `anomalyco/opencode` (`packages/app` и `packages/gui-plugins`):
  - `app/src/android/android-host.ts` — Двухканальный мост Android (`LocalHttpDaemon` + `@JavascriptInterface` `invokeAsync` fallback + WebSocket мост для Ghostty WASM терминала).
  - `app/src/android/custom-provider-dialog.tsx` — Диалог добавления кастомных провайдеров с пресетами и автоподхватом `/v1/models`.
  - `app/src/android/project-picker-dialog.tsx` — Менеджер локальных проектов и шаблонов на устройстве.
  - `app/src/android/mobile-adapt.css` — Адаптация safe-area и диалогов под мобильные экраны.
- `opencode-android/android/app/src/main/java/ai/opencode/android/` — Нативная Android-часть на Kotlin (`MainActivity.kt`, `OpenCodeRuntime.kt`, `OpenCodeDaemonService.kt`, `LocalHttpDaemon.kt`, `NativeBridge.kt`, `WorkspaceManager.kt`, `ShellExecutor.kt`, `OpenCodeFileProvider.kt`, `CliTools.kt`, `PyRuntime.kt`, `JsBridgeRunner.kt`).
  - `ShellExecutor.kt` — универсальный запуск команд в любой папке: PATH/HOME/TMPDIR, обход `noexec`, fallback на `cd` при отказе `ProcessBuilder.directory()`, **запуск инструментов без executable-бита** (`dalvikvm -cp base.apk ai.opencode.android.CliTools <tool>`), автоперезапись `python3/node/curl/...` в командах и shell-функции для скриптов.
  - `ProcessRegistry.kt` — реестр фоновых процессов: боты и dev-серверы (`python3 bot.py`, `node server.js`, `while True`, `getUpdates`, `app.run`, `serve(`, `--watch`) запускаются отсоединёнными, пишут лог в `files/run/logs/` и автоматически перезапускаются после убийства приложения.
  - `CliTools.kt` — точка входа портативного toolchain (`curl`, `wget`, `jq`, `zip`, `unzip`, `tree`, `git`, `node`, `npm`, `python3`, `which`).
  - `PyRuntime.kt` — интерпретатор подмножества Python 3 для `python3`: `requests`/`urllib`/`http`, `os.system`/`os.popen`/`os.execv`, `subprocess.*`, f-strings, `is None`, срезы, `json`, файлы.
  - `JsBridgeRunner.kt` — выполнение JS в V8 (WebView) с Node-совместимым API для `node`.
- `opencode-android/server/dev-daemon.mjs` — Node.js сервер для локального запуска и Live Preview (`0.0.0.0:4096`).
- `opencode-android/scripts/build-upstream-web.mjs` & `build-apk.mjs` — Скрипты сборки оригинального фронтенда `@opencode/app` и компиляции/подписи `OpenCode-Android-v2.2.5.apk`.

## Почему раньше было `python3: Permission denied` (и почему больше нет)

Начиная с Android 10 SELinux запрещает `execve()` для файлов внутри `/data/data/<app>/files`.
Поэтому «шим» вида `files/usr/bin/python3` с `#!/system/bin/sh` **никогда** не запустится, даже с `chmod 777`.
В сборке `20209` исполняемого бита не требуется вообще:

| Что нужно | Чем заменено |
|---|---|
| `python3`, `node`, `npm`, `curl`, `wget`, `jq`, `git`, `zip`, `unzip`, `tree` | `/system/bin/dalvikvm -cp <base.apk> ai.opencode.android.CliTools <tool>` — dalvik лишь *читает* APK, ничего не исполняет из app-данных |
| `bash` | `/system/bin/sh` (плюс реальный Termux `bash`, если он установлен) |
| `./script.sh`, `python3 x.py` внутри скриптов | автоперезапись команды + одноимённые shell-функции, подгружаемые в каждую `sh -c` сессию |
| `python3 bot.py`, `node server.js` | фоновый запуск с логом `files/run/logs/bg_*.log` и автоперезапуском через `ProcessRegistry` |

Termux **не обязателен**; если он установлен, его бинарники используются автоматически (и быстрее).
Каталог `/storage/emulated/0/...` смонтирован с `noexec` — это больше не мешает, потому что ни один
инструмент оттуда не запускается напрямую.

### Боты и долгоживущие команды

Если попросить агента «запусти бота», команда не будет убита по таймауту: агент получает
`pid` и путь к живому логу, процесс продолжает работать при свёрнутом приложении (wake-lock +
foreground-сервис) и перезапускается после перезапуска приложения. Токены в выводе инструментов
маскируются (`<REDACTED_BOT_TOKEN>`), поэтому случайно попавший в чат токен не утечёт в ответ ассистента.

## Сборка из исходников

```bash
cd opencode-android
npm run build:web   # Синхронизирует upstream anomalyco/opencode и собирает @opencode/app
npm run build:apk   # Компилирует Kotlin -> DEX, упаковывает assets/www, выравнивает и подписывает APK
npm start           # Запускает веб-сервер и демон на http://0.0.0.0:4096
```
