# Beepnook — Unity проект для Android

Главное меню сделано по твоему референсу (изометрический магазин), но тема изменена — это **не repair shop**, а **Gadget / Tech Shop** (магазин гаджетов). Цвета, шрифты и расположение кнопок повторяют референс.

## Что в репозитории

```
Assets/
  Scenes/
    MainMenu.unity   — главное меню (запускается первым)
    Game.unity       — placeholder игровой сцены
  Scripts/
    MainMenuManager.cs — создаёт UI меню программно (кнопки, заголовок, баннер)
    GameManager.cs     — заглушка игровой сцены
ProjectSettings/
  ProjectSettings.asset — настройки проекта (пакет com.korimuspast1.beepnook, Android)
  EditorBuildSettings.asset — список сцен для сборки
```

## Как открыть и собрать под Android

### 1. Установи Unity Hub + Unity Editor
- Скачай [Unity Hub](https://unity.com/download).
- Установи Unity Editor (рекомендуется LTS версия, например 2022.3 LTS или новее).
- В Unity Hub добавь этот проект: **Add** → выбери папку `/home/user/frd`.

### 2. Установи модуль Android Build Support
В Unity Hub → Installs → твоя версия → **Add modules** → поставь галочку:
- **Android Build Support**
- **Android SDK & NDK Tools** (Unity предложит скачать)
- **OpenJDK** (если требуется)

### 3. Открой проект
- Выбери проект в Unity Hub и нажми Открыть.
- Unity импортирует скрипты и сцены. Подожди終了 импорта (внизу справа sollte пропасть полоса прогресса).

### 4. Настрой Szenen для сборки
- Открой меню **File → Build Settings**.
- Нажми **Add Open Scenes** (должны добавиться `MainMenu` и `Game`).
- Убедись, что `MainMenu` находится **первым** в списке (это стартовая сцена).
- Выбери платформу **Android** и нажми **Switch Platform**.

### 5. Настройки Android (Player Settings)
- В Build Settings нажми **Player Settings**.
- В разделе **Other Settings**:
  - **Package Name**: `com.korimuspast1.beepnook` (уже задано)
  - **Minimum API Level**: Android 6.0 (API 23) или выше
  - **Target API Level**: Android 11+ (API 30)
- В разделе **X Settings → Icon** можешь добавить свою иконку приложения.

### 6. Сборка APK
- Подключи Android-устройство через USB (с включённой отладкой USB) **или** оставь для сборки APK-файла.
- В Build Settings нажми **Build** и выбери папку для сохранения `.apk`.
- После сборки перенеси `.apk` на телефон и установи.

## Как изменить тему / текст

Открой `Assets/Scripts/MainMenuManager.cs`. В начале класса есть блок `[Header("Theme")]`:

```csharp
[SerializeField] private string shopName = "BEEPNOOK";
[SerializeField] private string shopSubtitle = "GADGET SHOP";
[SerializeField] private Color titleColor = new Color(1f, 0.82f, 0.35f);   // жёлтый
[SerializeField] private Color subtitleBgColor = new Color(0.55f, 0.42f, 0.78f); // пурпурный баннер
[SerializeField] private Color buttonColor = new Color(1f, 0.65f, 0.75f);   // розовая кнопка
```

Меняй `shopName`, `shopSubtitle` и цвета — и меню сразу примет другой вид (мастерская, кафе, книжный магазин и т.д.).

## Что делают кнопки

| Кнопка | Действие |
|--------|----------|
| **Continue** | Загружает сцену `Game` |
| **New game** | Загружает сцену `Game` |
| **Settings** | Заглушка (можно добавить панель настроек) |
| **How to play** | Заглушка |
| **Credits** | Заглушка |

## Требования к ассетам

Скрипт создаёт весь UI программно (текст через TextMeshPro, кнопки, панели), поэтому отдельных картинок для меню не требуется. Если хочешь добавить изометрическую комнату как на референсе:
1. Создай 3D-модель комнаты в Blender или используй готовые ассеты из Unity Asset Store.
2. Помести её в сцену `MainMenu` за canvas-ом (или на отдельную камеру с фоном).
3. Настрой камеру под изометрический ракурс.

## Удачи с сборкой!

Если Unity ругается на отсутствующие скрипты после импорта — просто перезапусти 편집器, он сам сгенерирует недостающие `.meta` файлы.
