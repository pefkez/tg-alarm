<div align="center">
  <h1>⏰ TG Alarm</h1>
  <p><strong>Автоматический дозвон в Telegram, пока тебе не напишут</strong></p>

  <p>
    <img src="https://img.shields.io/badge/python-3.8%2B-blue?logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/Telethon-1.36-26A5E4?logo=telegram" alt="Telethon">
    <img src="https://img.shields.io/badge/API-способ-blueviolet" alt="API">
    <img src="https://img.shields.io/badge/Macro-способ-orange" alt="Macro">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
    <img src="https://img.shields.io/badge/status-active-brightgreen" alt="Status">
  </p>

  <br>
</div>

---

## 📋 О проекте

**TG Alarm** — два скрипта, которые автоматически звонят человеку в Telegram, пока он не ответит на сообщение. Как только жертва пишет — звонки прекращаются.

Подходит для:
- 😴 **Пробуждение** — если человек не отвечает и просит разбудить
- 🕐 **Напоминалка** — когда нужно срочно привлечь внимание
- 🤡 **Пранк** — ну ты понял

---

## 🚀 Способы

| | API-способ | Macro-способ |
|---|---|---|
| **Скрипт** | `tg_alarm.py` | `tg_alarm_macro.py` |
| **Суть** | Звонок через Telegram API напрямую | Эмуляция кликов по окну Telegram Desktop |
| **Плюсы** | Работает в фоне, не трогает твой ПК | Не нужен API ID / API Hash |
| **Минусы** | Нужен API ID (my.telegram.org) | Telegram Desktop должен быть открыт |
| **Платформы** | Linux / macOS / Windows | Только Windows |

---

## 🔌 Способ 1: API (Telethon)

### Установка

```bash
# 1. Клонируй репозиторий
git clone https://github.com/pefkez/tg-alarm.git
cd tg-alarm

# 2. Установи зависимости
pip install -r tg_alarm_requirements.txt
```

### Настройка

Открой `tg_alarm.py` и замени переменные в блоке **ТВОИ ДАННЫЕ**:

```python
API_ID = 123456789       # —> Получить: https://my.telegram.org → API Development tools
API_HASH = 'abc123...'   # —> Оттуда же
PHONE = '+79123456789'   # —> Твой номер Telegram
TARGET = '@nickname'     # —> Юзернейм цели (с @) или номер телефона
```

### Запуск

```bash
python tg_alarm.py
```

Скрипт:
1. Логинится в Telegram (первый раз — введи код из SMS)
2. Начинает звонить цели каждые ~37 секунд
3. Ждёт, пока цель напишет хоть одно сообщение
4. Как только сообщение пришло — звонки прекращаются ✅

> 💡 **Важно:** Сессия сохраняется в `tg_alarm_session.session` — второй раз код вводить не нужно.

---

## 🖱️ Способ 2: Macro (Desktop)

> ⚠️ **Только Windows!** Требуется установленный **Telegram Desktop**.

### Установка

```bash
pip install -r tg_alarm_macro_requirements.txt
```

### Калибровка кнопок

```bash
python tg_alarm_macro.py --calibrate
```

Тебя попросят:
1. **Навести мышь на кнопку звонка** (иконка телефона вверху чата) → нажать Enter
2. **Навести мышь на кнопку отбоя** (красная трубка) → нажать Enter

Координаты сохранятся в `tg_alarm_macro_calibrate.json`.

### Настройки

В `tg_alarm_macro.py`:

```python
TARGET_NAME = "Имя пользователя"  # как искать чат (Ctrl+K)
CHECK_INTERVAL = 10               # пауза между звонками (сек)
RING_SECONDS = 8                  # сколько звенит звонок
CHANGE_THRESHOLD = 15.0           # чувствительность детекта новых сообщений
```

### Запуск

```bash
python tg_alarm_macro.py
```

Скрипт:
1. Находит окно Telegram
2. Открывает нужный чат через Ctrl+K
3. Делает скриншот чата
4. Звонит, ждёт, сбрасывает
5. Снова делает скриншот — сравнивает с предыдущим
6. Если есть изменения (новое сообщение) — орёт (системный звук) и продолжает мониторинг

> 💡 Чтобы прервать — нажми `Ctrl+C`.

---

## 📁 Структура

```
tg-alarm/
├── tg_alarm.py                    # API-способ
├── tg_alarm_macro.py              # Macro-способ
├── tg_alarm_requirements.txt      # Зависимости для API
├── tg_alarm_macro_requirements.txt # Зависимости для Macro
├── README.md                      # Этот файл
└── face-analyzer/                 # Отдельный проект (см. вкладку)
```

---

## ⚠️ Безопасность

- **Не показывай никому** свой `API_ID` / `API_HASH` / `PHONE`
- Сессионный файл (`tg_alarm_session.session`) — тоже секрет
- Использование для **сталкинга или домогательств** — отвратительно. Не будь мудаком.

---

## 📄 Лицензия

MIT — делай что хочешь, но ответственность на тебе.
