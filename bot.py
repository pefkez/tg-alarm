#!/usr/bin/env python3
import os, sys, asyncio, random, hashlib, time, threading, json
from pathlib import Path
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
PHONE = os.getenv("PHONE", "")

state = {
    "mode": "api",
    "target": None,
    "running": False,
    "stop_event": threading.Event(),
    "telethon_ready": False,
    "telethon_client": None,
    "macro_hwnd": None,
    "macro_config": None,
}

HELP = (
    "/set_target @username — кто цель\n"
    "/mode api|macro — способ дозвона\n"
    "/go — запустить\n"
    "/stop — остановить\n"
    "/status — текущее состояние"
)

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"tg-alarm-bot\n\n{HELP}")

async def cmd_set_target(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text(f"/set_target @username\n{HELP}")
        return
    state["target"] = ctx.args[0].lstrip("@")
    await update.message.reply_text(f"Цель: {state['target']}")

async def cmd_mode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args or ctx.args[0] not in ("api", "macro"):
        await update.message.reply_text("Режимы: api или macro")
        return
    state["mode"] = ctx.args[0]
    await update.message.reply_text(f"Режим: {state['mode']}")

async def cmd_go(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if state["running"]:
        await update.message.reply_text("Уже работает")
        return
    if not state["target"]:
        await update.message.reply_text("Сначала /set_target")
        return
    if state["mode"] == "api" and not state["telethon_ready"]:
        await update.message.reply_text("Telethon не авторизован. Жди...")
        if not await init_telethon(update):
            return

    state["running"] = True
    state["stop_event"].clear()
    await update.message.reply_text(f"Запущен дозвон до @{state['target']} ({state['mode']})")

    if state["mode"] == "api":
        asyncio.create_task(api_alarm_loop(update))
    else:
        threading.Thread(target=macro_alarm_loop, args=(update,), daemon=True).start()

async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not state["running"]:
        await update.message.reply_text("Не работает")
        return
    state["running"] = False
    state["stop_event"].set()
    await update.message.reply_text("Остановлено")

async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Цель: @{state['target'] or '?'}\n"
        f"Режим: {state['mode']}\n"
        f"Статус: {'работает' if state['running'] else 'стоит'}\n"
        f"Telethon: {'ок' if state['telethon_ready'] else 'нет'}"
    )

async def init_telethon(update):
    from telethon import TelegramClient
    if not all([API_ID, API_HASH, PHONE]):
        await update.message.reply_text("Нет API_ID/API_HASH/PHONE в .env")
        return False
    try:
        client = TelegramClient("tg_alarm_bot_session", API_ID, API_HASH)
        await client.start(phone=PHONE)
        me = await client.get_me()
        state["telethon_client"] = client
        state["telethon_ready"] = True
        await update.message.reply_text(f"Авторизован как {me.first_name}")
        return True
    except Exception as e:
        await update.message.reply_text(f"Ошибка Telethon: {e}")
        return False

async def api_alarm_loop(update):
    client = state["telethon_client"]
    target = state["target"]

    try:
        target_user = await client.get_entity(target)
    except Exception as e:
        await update.message.reply_text(f"Не найден {target}: {e}")
        state["running"] = False
        return

    last_msg_id = 0
    msgs = await client.get_messages(target_user, limit=1)
    if msgs:
        last_msg_id = msgs[0].id

    async def on_msg(event):
        if (event.is_private and event.sender_id == target_user.id
                and not event.message.out):
            state["running"] = False
            state["stop_event"].set()
            await update.message.reply_text(f"{target} написал(а)! Дозвон завершён")

    client.add_event_handler(on_msg)

    while state["running"] and not state["stop_event"].is_set():
        # check new msg
        msgs = await client.get_messages(target_user, limit=1)
        if msgs and msgs[0].id > last_msg_id:
            await update.message.reply_text(f"@{target} написал(а)! Дозвон завершён")
            break

        # call
        try:
            random_id = random.randint(1, 2**31 - 1)
            a_bytes = os.urandom(256)
            a = int.from_bytes(a_bytes, "big") % (0xFFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3BE39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA051015728E5A8AAAC42DAD33170D04507A33A85521ABDF1CBA64ECFB850458DBEF0A8AEA71575D060C7DB3970F85A6E1E4C7ABF5AE8CDB0933D71E8C94E04A25619DCEE3D2261AD2EE6BF12FFA06D98A0864D87602733EC86A64521F2B18177B200CBBE117577A615D6C770988C0BAD946E208E24FA074E5AB3143DB5BFCE0FD108E4B82D120A93AD2CAFFFFFFFFFFFFFFFF - 1) + 1
            g_a = pow(2, a, 0xFFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3BE39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA051015728E5A8AAAC42DAD33170D04507A33A85521ABDF1CBA64ECFB850458DBEF0A8AEA71575D060C7DB3970F85A6E1E4C7ABF5AE8CDB0933D71E8C94E04A25619DCEE3D2261AD2EE6BF12FFA06D98A0864D87602733EC86A64521F2B18177B200CBBE117577A615D6C770988C0BAD946E208E24FA074E5AB3143DB5BFCE0FD108E4B82D120A93AD2CAFFFFFFFFFFFFFFFF)
            g_a_hash = hashlib.sha256(g_a.to_bytes(256, "big")).digest()

            from telethon.tl.functions.phone import RequestCallRequest, DiscardCallRequest
            from telethon.tl.types import PhoneCallProtocol, PhoneCallWaiting, InputPhoneCall, PhoneCallDiscardReasonMissed

            protocol = PhoneCallProtocol(udp_p2p=True, udp_reflector=True, min_layer=92, max_layer=92, library_versions=["4.0.0"])
            result = await client(RequestCallRequest(user_id=target_user, random_id=random_id, g_a_hash=g_a_hash, protocol=protocol))
            call = result.call

            if isinstance(call, PhoneCallWaiting):
                await asyncio.sleep(12)
                try:
                    await client(DiscardCallRequest(peer=InputPhoneCall(id=call.id, access_hash=call.access_hash), duration=0, reason=PhoneCallDiscardReasonMissed(), connection_id=0))
                except:
                    pass
        except Exception as e:
            pass

        if not state["running"]:
            break

        # check again
        msgs = await client.get_messages(target_user, limit=1)
        if msgs and msgs[0].id > last_msg_id:
            await update.message.reply_text(f"@{target} написал(а)! Дозвон завершён")
            break

        # wait
        for _ in range(25):
            if state["stop_event"].is_set():
                break
            await asyncio.sleep(1)

    state["running"] = False
    await update.message.reply_text("Дозвон завершён")

def macro_alarm_loop(update):
    try:
        import pyautogui
        import win32gui, win32con
        import cv2, numpy as np, mss
    except ImportError:
        asyncio.run_coroutine_threadsafe(
            update.message.reply_text("Нет зависимостей: pip install -r tg_alarm_macro_requirements.txt"),
            update.get_bot().loop
        )
        state["running"] = False
        return

    target = state["target"]

    def find_telegram():
        def cb(hwnd, results):
            if win32gui.GetWindowText(hwnd) == "Telegram":
                results.append(hwnd)
        results = []
        win32gui.EnumWindows(cb, results)
        if results:
            return results[0]
        def cb2(hwnd, results):
            if "Telegram" in win32gui.GetWindowText(hwnd):
                results.append(hwnd)
        results = []
        win32gui.EnumWindows(cb2, results)
        return results[0] if results else None

    def focus(hwnd):
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.5)

    def get_rect(hwnd):
        l, t, r, b = win32gui.GetWindowRect(hwnd)
        return l, t, r - l, b - t

    def screenshot(left, top, w, h):
        with mss.mss() as sct:
            return np.array(sct.grab({"left": int(left), "top": int(top), "width": int(w), "height": int(h)}))

    def detect(img1, img2):
        h = min(img1.shape[0], img2.shape[0])
        g1 = cv2.cvtColor(img1[:h, :, :3], cv2.COLOR_BGRA2GRAY)
        g2 = cv2.cvtColor(img2[:h, :, :3], cv2.COLOR_BGRA2GRAY)
        return np.mean(cv2.absdiff(g1, g2)) > 15.0

    hwnd = find_telegram()
    if not hwnd:
        asyncio.run_coroutine_threadsafe(
            update.message.reply_text("Telegram Desktop не найден"),
            update.get_bot().loop
        )
        state["running"] = False
        return

    focus(hwnd)
    time.sleep(0.5)
    pyautogui.hotkey("ctrl", "k")
    time.sleep(0.5)
    pyautogui.write(target, interval=0.05)
    time.sleep(0.5)
    pyautogui.press("enter")
    time.sleep(1)
    pyautogui.press("escape")
    time.sleep(0.3)

    cfg_file = Path("tg_alarm_macro_calibrate.json")
    if not cfg_file.exists():
        asyncio.run_coroutine_threadsafe(
            update.message.reply_text(f"Нужна калибровка: запусти {sys.argv[0]} --calibrate"),
            update.get_bot().loop
        )
        state["running"] = False
        return

    with open(cfg_file) as f:
        cfg = json.load(f)

    l, t, w, h = get_rect(hwnd)
    base = screenshot(l, t + int(h * 0.25), w, int(h * 0.55))
    asyncio.run_coroutine_threadsafe(
        update.message.reply_text("Макро-дозвон запущен"),
        update.get_bot().loop
    )

    while state["running"] and not state["stop_event"].is_set():
        time.sleep(10)
        curr = screenshot(l, t + int(h * 0.25), w, int(h * 0.55))
        if detect(base, curr):
            asyncio.run_coroutine_threadsafe(
                update.message.reply_text("Новое сообщение!"),
                update.get_bot().loop
            )
            time.sleep(10)
            base = screenshot(l, t + int(h * 0.25), w, int(h * 0.55))
            continue

        focus(hwnd)
        pyautogui.click(cfg["call_x"], cfg["call_y"])
        time.sleep(8)
        pyautogui.click(cfg["hangup_x"], cfg["hangup_y"])
        focus(hwnd)
        base = screenshot(l, t + int(h * 0.25), w, int(h * 0.55))

    state["running"] = False
    asyncio.run_coroutine_threadsafe(
        update.message.reply_text("Макро-дозвон завершён"),
        update.get_bot().loop
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("set_target", cmd_set_target))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("go", cmd_go))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("status", cmd_status))
    print("бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
