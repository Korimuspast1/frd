# Beepnook — Gadget Shop (без Unity)

Это standalone-версия главной меню по твоему референсу. Не требует Unity — это обычный HTML-файл, который можно открыть в браузере на Android, iPhone или ПК.

## Как запустить

1. Скопируй файл `index.html` на телефон (или отправь себе через Gmail / Google Drive / Telegram).
2. Открой его в Chrome (Android) или Safari (iOS).
3. Кнопки:
   - **Continue / New game** — перейти в игру (заглушка)
   - **Settings** — заглушка
   - **How to play / Credits** — справка

## Как сделать приложением на Android (опционально)

Chrome на Android позволяет установить любой сайт как приложение:
1. Открой `index.html` в Chrome.
2. Нажми три точки ⋮ → **Добавить на главный экран**.
3. Ярлык появится на рабочем столе как приложение.

## Кастомизация

Открой `index.html` в текстовом редакторе:
- Строка `<div class="title">Beepnook</div>` — название игры.
- Строка `<div class="banner">Gadget Shop</div>` — подзаголовок (замени на свою тему, например "Workshop" или "Cafe").
- Цвета в CSS: `.continue-btn` (розовая кнопка), `.banner` (пурпурный баннер), `.title` (жёлтый текст).

## Файлы

- `index.html` — всё в одном: HTML + CSS + JS.
