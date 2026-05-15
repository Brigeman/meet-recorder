# Техническое задание: Desktop Meeting Recorder с автодетекцией звонков

## 1. Цель продукта

Создать фоновое десктопное приложение для Windows, которое помогает сотрудникам не забывать записывать рабочие звонки.

Приложение должно:

- работать в фоне;
- автоматически определять вероятное начало звонка в web и desktop-приложениях;
- показывать аккуратное уведомление: «Похоже, начался звонок. Записать?»;
- запускать запись только после действия пользователя;
- записывать микрофон и системный звук;
- иметь маленькую стильную плавающую панель управления записью;
- не падать из-за детекторов, UIA, аудио-проб или нестабильных API;
- быть расширяемым под Teams, Zoom, Slack, Discord, Telegram, WhatsApp, Google Meet и другие платформы.

Основная бизнес-задача:

> Не заставлять сотрудников вручную помнить о записи звонков, а мягко и вовремя напоминать им о возможном начале встречи.

---

## 2. Продуктовая модель

Приложение не должно автоматически начинать запись без подтверждения пользователя.

Правильный сценарий:

```text
Система видит признаки звонка
→ показывает prompt
→ пользователь нажимает «Записать»
→ начинается запись
→ появляется плавающая панель
→ пользователь останавливает запись
→ файл сохраняется
```

Неправильный сценарий:

```text
Система решила, что начался звонок
→ запись началась без участия пользователя
```

---

## 3. Базовая идея реализации

Проект строится заново на базе подхода Ghost Meet Recorder, но с продуктовой логикой для корпоративного desktop recorder.

Ключевой принцип:

```text
Audio-first + Context-first detection
```

Не нужно пытаться идеально понять, что конкретно Teams сообщил о звонке. Нужно определить, что вероятность звонка достаточно высокая, чтобы показать prompt.

---

## 4. Основные сигналы детекции

### 4.1. Microphone activity

Сильный сигнал.

Если микрофон активно используется, это может означать:

- пользователь говорит на звонке;
- приложение захватило микрофон;
- идёт голосовой ввод;
- открыта встреча.

Сам по себе микрофон не должен запускать prompt.

Вес сигнала:

```text
mic_active: +35
```

---

### 4.2. System audio / loopback activity

Сильный сигнал, если есть одновременно с микрофоном.

Примеры:

- пользователь слышит собеседников;
- идёт Teams / Zoom / Meet call;
- играет видео или музыка.

Сам по себе системный звук не должен запускать prompt.

Вес сигнала:

```text
loopback_active: +25
```

---

### 4.3. Known meeting app running

Приложение видит, что запущен известный communication app.

Список первой версии:

```text
Microsoft Teams
Zoom
Slack
Discord
Telegram Desktop
WhatsApp Desktop
Google Chrome
Microsoft Edge
```

Вес сигнала:

```text
known_meeting_app_running: +15
```

---

### 4.4. Known meeting app foreground

Если foreground window принадлежит известному meeting app, сигнал сильнее.

Вес:

```text
known_meeting_app_foreground: +20
```

---

### 4.5. Window title hints

Безопасная альтернатива UIA.

Примеры title hints:

```text
Microsoft Teams
Zoom Meeting
Slack
Huddle
Discord
Telegram
WhatsApp
Google Meet
Meet
```

Вес:

```text
title_hint: +10..15
```

---

### 4.6. Browser meeting context

Уже реализованная часть продукта.

Она должна остаться и быть интегрирована в новый detector service.

Поддерживаемые web-сценарии:

```text
Google Meet
Zoom Web
Teams Web
Slack Web
Discord Web
```

Вес:

```text
browser_meeting_context: +40
```

---

### 4.7. Optional UIA / Accessibility signal

UIA не должен использоваться в основном процессе.

Если UIA нужен, он должен быть вынесен в отдельный worker process.

UIA является дополнительным усилителем сигнала, а не основой продукта.

Вес:

```text
uia_strong_call_controls: +35
```

---

## 5. Scoring model

Детектор должен собирать сигналы и считать итоговый score.

Пример:

```text
mic_active                         +35
loopback_active                    +25
known_meeting_app_running          +15
known_meeting_app_foreground       +20
title_hint                         +15
browser_meeting_context            +40
uia_strong_call_controls           +35
```

Prompt показывается, если:

```text
score >= 70
AND signal sustained for N seconds
AND cooldown is not active
```

---

## 6. Sustain и cooldown

### 6.1. Web calls

Для web-звонков сигналы чище.

```text
web_sustain_seconds = 2.5
```

---

### 6.2. Desktop calls

Для desktop-звонков сигналы грязнее.

```text
desktop_sustain_seconds = 5.0..10.0
```

Рекомендуемое значение первой версии:

```text
desktop_sustain_seconds = 7.0
```

---

### 6.3. Prompt cooldown

После того как пользователь нажал «Не сейчас», prompt не должен появляться сразу снова.

```text
prompt_dismiss_cooldown_seconds = 90
```

Cooldown должен применяться к context key:

```text
app + pid + window_title_hash
```

---

### 6.4. Post-stop cooldown

После остановки записи не показывать prompt повторно для того же контекста.

```text
post_stop_cooldown_seconds = 120
```

---

## 7. Примеры scoring

### 7.1. Teams desktop call

```text
mic_active                         +35
loopback_active                    +25
Teams running                      +15
Teams foreground                   +20
---------------------------------------
score = 95
```

Результат:

```text
Показать prompt через 5-10 секунд sustain.
```

---

### 7.2. Teams открыт, но звонка нет

```text
Teams running                      +15
Teams foreground                   +20
no mic
no loopback
---------------------------------------
score = 35
```

Результат:

```text
Prompt не показывать.
```

---

### 7.3. YouTube играет, Teams открыт в фоне

```text
loopback_active                    +25
Teams running                      +15
no mic
Teams not foreground
---------------------------------------
score = 40
```

Результат:

```text
Prompt не показывать.
```

---

### 7.4. Пользователь говорит в микрофон, но звонка нет

```text
mic_active                         +35
no loopback
no meeting app foreground
---------------------------------------
score = 35
```

Результат:

```text
Prompt не показывать.
```

---

### 7.5. Google Meet web

```text
browser_meeting_context            +40
mic_active                         +35
loopback_active                    +25
---------------------------------------
score = 100
```

Результат:

```text
Prompt показать быстро: 2-3 секунды.
```

---

## 8. Архитектура приложения

Основная проблема старой версии — слишком много нестабильных компонентов внутри одного процесса.

Новая архитектура должна разделять GUI, detector и recorder.

```text
Main GUI Process
    ├── tray
    ├── floating panel
    ├── prompt windows
    └── IPC client

Detector Service Process
    ├── microphone activity probe
    ├── loopback/system audio probe
    ├── process probe
    ├── foreground window/title probe
    ├── browser meeting detector
    ├── scoring engine
    └── JSON event output

Recorder Service Process
    ├── microphone capture
    ├── system audio capture
    ├── file writer
    └── recording lifecycle

Optional UIA Worker Process
    ├── accessibility tree scan
    ├── call controls detection
    └── JSON event output
```

Главное правило:

```text
GUI process не должен падать из-за detector, recorder или UIA.
```

---

## 9. Компоненты

## 9.1. Main GUI Process

Отвечает только за:

- tray icon;
- floating recording panel;
- meeting prompt;
- stop recording prompt;
- user actions;
- отображение состояния;
- IPC с detector/recorder.

Main GUI Process не должен:

- импортировать `uiautomation`;
- выполнять Core Audio session scanning напрямую;
- делать тяжёлую запись;
- запускать transcription;
- обходить процессы каждую секунду;
- падать при ошибке detector service.

---

## 9.2. Detector Service Process

Фоновый процесс, который раз в 1-2 секунды собирает сигналы и пишет события.

Пример события:

```json
{
  "type": "call_candidate",
  "score": 85,
  "app": "Microsoft Teams",
  "source": "audio_context",
  "matched": ["mic_active", "loopback_active", "teams_foreground"],
  "context_key": "teams:1234:abc123",
  "timestamp": 1710000000.0
}
```

Если score ниже threshold:

```json
{
  "type": "no_call",
  "score": 35,
  "matched": ["teams_foreground"],
  "timestamp": 1710000000.0
}
```

---

## 9.3. Recorder Service Process

Отвечает за запись.

Функции:

- start recording;
- stop recording;
- pause/resume, если понадобится;
- запись mic audio;
- запись system audio;
- сохранение WAV/MP3/M4A;
- диагностика уровня звука;
- событие об ошибке записи.

Пример команды:

```json
{
  "command": "start_recording",
  "session_id": "uuid",
  "app": "Microsoft Teams"
}
```

Пример события:

```json
{
  "type": "recording_started",
  "session_id": "uuid",
  "file_path": "C:/Users/.../recordings/session.wav"
}
```

---

## 9.4. Optional UIA Worker Process

UIA не является частью MVP core.

Если нужен, он должен быть отдельным процессом.

Причина:

```text
uiautomation/comtypes может вызвать native access violation и уронить весь процесс.
```

Если UIA worker падает:

- GUI остаётся живым;
- detector остаётся живым;
- recorder остаётся живым;
- supervisor может перезапустить UIA worker с cooldown.

UIA worker должен включаться только флагом:

```text
WINREC_ENABLE_EXPERIMENTAL_UIA=1
```

---

## 10. IPC

Для первой версии можно использовать простой JSONL transport.

Варианты:

```text
1. JSONL files
2. stdin/stdout JSON lines
3. localhost socket
4. Windows named pipe
```

Рекомендуемый MVP-вариант:

```text
Detector → stdout JSONL → GUI reads
GUI → Recorder → subprocess stdin JSONL
```

Позже можно перейти на named pipes.

---

## 11. UI требования

## 11.1. Tray

Приложение должно жить в system tray.

Tray menu:

```text
Start recording
Stop recording
Open recordings folder
Settings
Quit
```

Tray должен оставаться активным, даже если detector service упал.

---

## 11.2. Meeting prompt

Prompt должен быть маленьким, красивым и ненавязчивым.

Размер:

```text
320×92 или около того
```

Пример текста:

```text
Похоже, начался звонок в Teams
Возможно, пора включить запись.

[Не сейчас] [Записать]
```

Для других приложений:

```text
Похоже, начался звонок в Zoom
Похоже, начался звонок в Slack
Похоже, начался звонок в Discord
Похоже, начался звонок в Telegram
Похоже, начался звонок в WhatsApp
Похоже, началась встреча в Google Meet
```

Prompt не должен блокировать экран.

---

## 11.3. Floating recording panel

Плавающая панель появляется после старта записи.

Размер:

```text
360×48
```

Содержимое:

```text
● REC   00:13   ▂▃▅▆▃   Stop
```

Требования:

- always on top;
- draggable;
- аккуратная тень;
- rounded corners;
- маленькая высота;
- минимум кнопок;
- stop button;
- индикатор уровня звука;
- таймер записи.

Не перегружать панель кнопками Settings / Hide. Эти действия лучше вынести в tray.

---

## 12. Supported apps

## 12.1. Microsoft Teams

Process names:

```text
ms-teams.exe
teams.exe
msteams.exe
msedgewebview2.exe only with Teams ancestor
```

Detection:

```text
mic active
+ loopback active
+ Teams running/foreground
+ optional title hints
```

---

## 12.2. Zoom

Process names:

```text
zoom.exe
```

Detection:

```text
mic active
+ loopback active
+ Zoom foreground/running
+ title contains Zoom Meeting
```

---

## 12.3. Slack

Process names:

```text
slack.exe
```

Detection:

```text
mic active
+ loopback active
+ Slack foreground/running
+ optional title contains Huddle
```

---

## 12.4. Discord

Process names:

```text
discord.exe
```

Detection:

```text
mic active
+ loopback active
+ Discord foreground/running
```

---

## 12.5. Telegram Desktop

Process names:

```text
telegram.exe
```

Detection:

```text
mic active
+ loopback active
+ Telegram foreground/running
```

---

## 12.6. WhatsApp Desktop

Process names:

```text
whatsapp.exe
msedgewebview2.exe only with WhatsApp ancestor
```

Detection:

```text
mic active
+ loopback active
+ WhatsApp foreground/running
```

---

## 12.7. Browser meetings

Processes:

```text
chrome.exe
msedge.exe
firefox.exe
brave.exe
```

Detection should reuse existing web meeting logic.

Supported platforms:

```text
Google Meet
Teams Web
Zoom Web
Slack Web
Discord Web
```

---

## 13. WebView2 ancestry rule

Do not treat `msedgewebview2.exe` as a meeting app by itself.

Correct rule:

```text
msedgewebview2.exe counts only if its parent/ancestor is a known meeting app.
```

Example:

```text
msedgewebview2.exe → msteams.exe → Teams app
```

Valid.

```text
msedgewebview2.exe → random-app.exe
```

Invalid.

---

## 14. False positive protection

Use three levels of protection:

```text
1. score threshold
2. sustain
3. cooldown
```

Prompt should not be shown for:

- YouTube/music;
- game audio;
- Teams opened in background without call;
- microphone noise without system audio;
- browser page with meeting word but no actual audio activity;
- join/pre-call screens without duplex audio.

---

## 15. Recording requirements

The application must record:

```text
1. microphone audio
2. system audio / loopback audio
```

Preferred output:

```text
WAV for raw reliability
MP3/M4A optional later
```

Recommended file structure:

```text
recordings/
    2026-05-15_14-30_Teams_call.wav
    2026-05-15_14-30_Teams_call.json
```

Metadata JSON:

```json
{
  "session_id": "uuid",
  "started_at": "2026-05-15T14:30:00",
  "ended_at": "2026-05-15T15:05:00",
  "app": "Microsoft Teams",
  "detected_by": ["mic_active", "loopback_active", "teams_foreground"],
  "user_confirmed": true,
  "audio_file": "...wav"
}
```

---

## 16. Lifecycle

Application startup:

```text
1. start GUI
2. acquire single instance lock
3. start detector service
4. start recorder service idle
5. show tray
```

Prompt flow:

```text
1. detector emits call_candidate
2. GUI checks cooldown
3. GUI shows prompt
4. user clicks Record
5. GUI sends start_recording
6. recorder starts
7. GUI shows floating panel
```

Stop flow:

```text
1. user clicks Stop
2. GUI sends stop_recording
3. recorder finalizes file
4. GUI hides panel
5. post-stop cooldown starts
```

Detector crash flow:

```text
1. detector process exits unexpectedly
2. GUI logs event
3. GUI remains alive
4. supervisor restarts detector after cooldown
5. tray remains active
```

---

## 17. Crash safety

Hard rule:

```text
No unstable native detector should run in the GUI process.
```

Main GUI process must not import:

```text
uiautomation
comtypes for UIA
heavy audio session scanner directly
```

If detector crashes:

```text
GUI survives.
Recording already started should survive if recorder is separate.
```

---

## 18. Logging

Use structured logs.

Important events:

```text
app_start
app_exit
single_instance_acquired
single_instance_duplicate
detector_started
detector_crashed
detector_restarted
call_candidate
prompt_shown
prompt_dismissed
recording_started
recording_stopped
recording_failed
```

Detector trace mode:

```text
WINREC_DETECTOR_TRACE=1
```

Trace should log:

```text
audio levels
mic active status
loopback active status
foreground process
foreground title
known app status
score
matched signals
cooldown state
```

Example:

```text
signal_score | score=95 app=Teams matched=mic_active,loopback_active,teams_foreground sustain=7.2
```

---

## 19. Configuration

Config file:

```text
config.json
```

Example:

```json
{
  "prompt_threshold": 70,
  "web_sustain_seconds": 2.5,
  "desktop_sustain_seconds": 7.0,
  "dismiss_cooldown_seconds": 90,
  "post_stop_cooldown_seconds": 120,
  "enable_experimental_uia": false,
  "recordings_dir": "recordings",
  "supported_apps": {
    "teams": true,
    "zoom": true,
    "slack": true,
    "discord": true,
    "telegram": true,
    "whatsapp": true,
    "browser_meetings": true
  }
}
```

---

## 20. Testing plan

## 20.1. Unit tests

Test scoring:

```text
mic + loopback + Teams foreground → prompt candidate
Teams foreground only → no prompt
loopback only → no prompt
mic only → no prompt
YouTube + Teams background → no prompt
Google Meet web context + mic → prompt candidate
```

---

## 20.2. Integration tests

Test process communication:

```text
GUI starts detector
GUI receives candidate event
GUI shows prompt
GUI sends start_recording
recorder starts
recorder stops
```

---

## 20.3. Crash tests

```text
Kill detector process → GUI stays alive
Kill optional UIA worker → GUI stays alive
Recorder error → GUI shows error but does not crash
Duplicate app launch → second instance exits cleanly
```

---

## 20.4. Manual QA matrix

Windows 11:

```text
Teams desktop call → prompt in 5-10s
Teams open, no call → no prompt
Teams background, YouTube playing → no prompt
Zoom desktop call → prompt
Slack huddle → prompt
Discord voice → prompt
Telegram call → prompt
WhatsApp call → prompt
Google Meet web → prompt in 2-3s
YouTube only → no prompt
Music only → no prompt
Manual recording → works
Hotkey recording → works
Detector crash → tray remains active
Recorder crash → GUI remains active
```

---

## 21. Roadmap

## Phase 1 — Stable base

Goal:

```text
Stable tray + floating panel + manual recording + detector process skeleton.
```

Tasks:

```text
1. Port useful audio detection ideas from Ghost Meet Recorder.
2. Keep GUI separate from detector.
3. Implement detector JSONL output.
4. Implement recorder service.
5. Implement prompt UI.
```

---

## Phase 2 — Desktop detection without UIA

Goal:

```text
Detect most desktop calls through audio + process + foreground context.
```

Tasks:

```text
1. Mic activity detection.
2. Loopback activity detection.
3. Known app running detection.
4. Foreground window detection.
5. WebView2 ancestry detection.
6. Score threshold + sustain + cooldown.
```

---

## Phase 3 — Web meeting integration

Goal:

```text
Reuse existing web-call detector from the current product.
```

Tasks:

```text
1. Integrate existing browser meeting detection.
2. Normalize browser events into CallSignal.
3. Apply scoring model.
```

---

## Phase 4 — Hardening

Goal:

```text
Make the app stable for daily corporate usage.
```

Tasks:

```text
1. Better single instance guard.
2. Detector supervisor.
3. Recorder supervisor.
4. Structured logs.
5. Crash recovery.
6. Config file.
```

---

## Phase 5 — Optional UIA worker

Goal:

```text
Improve precision for Teams/Zoom/Slack without risking main app stability.
```

Tasks:

```text
1. Separate UIA worker process.
2. Low-frequency scanning.
3. Strict timeout.
4. Crash isolation.
5. Feature flag.
```

---

## 22. Non-goals for first version

Do not implement in the first version:

```text
automatic recording without user confirmation
perfect Teams internal call detection
full UIA integration inside main process
calendar integration as required dependency
cloud transcription dependency
employee surveillance features
silent recording
```

---

## 23. Acceptance criteria

The product is acceptable when:

```text
1. App stays alive in tray for 8+ hours.
2. Manual recording works reliably.
3. Floating panel is stable and usable.
4. Web calls still detected as before.
5. Teams desktop calls produce prompt in most normal cases.
6. Zoom desktop calls produce prompt in most normal cases.
7. YouTube/music does not constantly trigger false prompts.
8. Detector crash does not close GUI.
9. Recorder crash does not close GUI.
10. UIA is not required for core functionality.
```

---

## 24. Final product principle

The product should not try to be magical.

It should be:

```text
stable
quiet
fast
beautiful
useful
hard to crash
```

The core value:

```text
When a meeting probably starts, the employee gets a timely, elegant reminder to record it.
```

Not:

```text
The app perfectly understands every meeting app internals.
```
