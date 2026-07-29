# tg-alarm

Звонит человеку в Telegram пока он не напишет. Три способа:

### Бот (управление через Telegram)

```
cp .env.example .env
pip install -r tg_alarm_requirements.txt
```

В `.env` вставить BOT_TOKEN (от @BotFather), API_ID, API_HASH, PHONE.

```
python bot.py
```

Команды: `/set_target`, `/mode api|macro`, `/go`, `/stop`, `/status`.

### Через API (Telethon)

```
pip install -r tg_alarm_requirements.txt
```

Открыть `tg_alarm.py`, вставить API_ID, API_HASH, PHONE, TARGET (https://my.telegram.org).

```
python tg_alarm.py
```

### Через макрос (только Windows)

```
pip install -r tg_alarm_macro_requirements.txt
python tg_alarm_macro.py --calibrate
python tg_alarm_macro.py
```

---
