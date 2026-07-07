# Установка и запуск на macOS

Инструкция для ad-hoc / unsigned сборок (без Apple Developer ID), распространяемых через GitHub Releases.

## Скачать

1. Откройте [Releases](https://github.com/Brigeman/meet-recorder/releases).
2. Скачайте **`DesktopMeetingRecorder-vX.Y.Z-macos.dmg`** для нужной версии.

## Установка

Откройте DMG. В окне будут:

- `Desktop Meeting Recorder.app`
- ярлык **Applications →**
- **`Install.command`**
- **`Первый запуск.txt`**

### Способ 1 — Install.command (рекомендуется)

1. Дважды кликните **`Install.command`**.
2. Если macOS спросит про неизвестный скрипт — **Открыть**.
3. Скрипт скопирует приложение в `/Applications` и запустит его через Finder.

### Способ 2 — вручную

1. Перетащите **`Desktop Meeting Recorder.app`** в **Applications**.
2. Снимите карантин Gatekeeper (один раз после скачивания):

```bash
xattr -dr com.apple.quarantine "/Applications/Desktop Meeting Recorder.app"
```

3. Запустите:

```bash
open "/Applications/Desktop Meeting Recorder.app"
```

### Способ 3 — macOS 15+ (Sequoia), если блокирует запуск

1. Дважды кликните приложение → появится предупреждение → **Готово**.
2. **Системные настройки → Конфиденциальность и безопасность**.
3. Внизу — **«Все равно открыть»** для Desktop Meeting Recorder.
4. Подтвердите паролем или Touch ID.

> **Важно:** не запускайте `.app` прямо из окна DMG — macOS 15/16 может блокировать или крашить приложение с образа. Всегда копируйте в **Applications** сначала.

> Не запускайте `Contents/MacOS/MeetRec` из Terminal для обычного использования — окно Terminal останется открытым на всё время работы приложения.

## Первый запуск

- Иконка появится в **строке меню** (menubar). В Dock приложения **нет** — это нормально.
- При первой записи разрешите **Микрофон**.
- Для системного звука и детекции браузерных встреч нужны **Запись экрана** и **Универсальный доступ** (Accessibility).

| Разрешение | Зачем |
|------------|-------|
| **Запись экрана** (Screen Recording) | Заголовки окон браузера (Google Meet и т.д.) |
| **Универсальный доступ** (Accessibility) | Активное приложение / окно |
| **Микрофон** | Запись вашей стороны разговора |

Откройте **Системные настройки → Конфиденциальность и безопасность** и включите все три для **Desktop Meeting Recorder**.

## Автозапуск

В **Settings** приложения можно включить автозапуск. Регистрируется Launch Agent `ai.o2consult.meetrec`.

## После обновления

Ad-hoc сборки каждый раз получают новую подпись. macOS может снова запросить разрешения:

```bash
xattr -dr com.apple.quarantine "/Applications/Desktop Meeting Recorder.app"
```

Проверьте **Запись экрана**, **Универсальный доступ** и **Микрофон** в настройках, если детекция перестала работать.

Подпись **Developer ID** ($99/год) сохраняет права между пересборками — для внутреннего использования достаточно ad-hoc + `xattr`.

## Проверка детекции

Во время реального звонка (Teams, Zoom, Meet в браузере):

```bash
grep call_candidate ~/Documents/Desktop\ Meeting\ Recordings/logs/meetrec-detector-*.log | tail -5
```

Должны появиться строки `call_candidate` со score ≥ 70.

## Логи

```text
~/Documents/Desktop Meeting Recordings/logs/
  meetrec-gui-YYYY-MM-DD.log
  meetrec-detector-YYYY-MM-DD.log
  meetrec-recorder-YYYY-MM-DD.log
```

Успешный старт: `app_start` в GUI-логе, `detector_started` в detector-логе.

## Разработка из исходников

```bash
./start.sh
# или
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
bash meetrec/platform/macos/helper/build.sh
python -m meetrec
```

## Troubleshooting

- **Нет иконки в menubar:** `pkill -f "Desktop Meeting Recorder"`, удалите `~/Library/Application Support/Desktop Meeting Recorder/meetrec.lock`, переустановите и выдайте права заново.
- **Install.command «убит» (killed):** сначала снимите quarantine с DMG: `xattr -dr com.apple.quarantine ~/Downloads/DesktopMeetingRecorder-*.dmg`, затем смонтируйте снова.
- **Desktop Teams/Zoom не детектится:** обычно достаточно микрофона + системного звука во время звонка.
- **Meet в браузере не детектится:** включите **Запись экрана**.
