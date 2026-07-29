# tg-alarm

Звонит человеку в Telegram пока он не напишет. Два варианта:

### 1. Через API (Telethon)

```
pip install -r tg_alarm_requirements.txt
```

Открыть `tg_alarm.py`, вставить API_ID, API_HASH, PHONE, TARGET. Получить [тут](https://my.telegram.org).

```
python tg_alarm.py
```

### 2. Через макрос (только Windows)

```
pip install -r tg_alarm_macro_requirements.txt
python tg_alarm_macro.py --calibrate  # навести на кнопки звонка/отбоя
python tg_alarm_macro.py
```

Детектит новые сообщения по скриншотам, звонит через Telegram Desktop.

---

Лицензия MIT. Делай что хочешь.
