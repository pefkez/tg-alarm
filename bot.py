#!/usr/bin/env python3
import os, sys, asyncio, random, hashlib, time, threading, json, logging
from pathlib import Path
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from scheduler import AlarmScheduler
from group_alarm import GroupAlarmManager
from captcha_verifier import CaptchaVerifier

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
PHONE = os.getenv("PHONE", "")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

scheduler = AlarmScheduler()
group_manager = GroupAlarmManager()
captcha = CaptchaVerifier()

whatsapp_provider = None
signal_provider = None
mqtt_bridge = None

HELP = (
    "/set_target @username \u2014 \u043a\u0442\u043e \u0446\u0435\u043b\u044c\n"
    "/mode api|macro|whatsapp|signal \u2014 \u0441\u043f\u043e\u0441\u043e\u0431 \u0434\u043e\u0437\u0432\u043e\u043d\u0430\n"
    "/go \u2014 \u0437\u0430\u043f\u0443\u0441\u0442\u0438\u0442\u044c\n"
    "/stop \u2014 \u043e\u0441\u0442\u0430\u043d\u043e\u0432\u0438\u0442\u044c\n"
    "/status \u2014 \u0442\u0435\u043a\u0443\u0449\u0435\u0435 \u0441\u043e\u0441\u0442\u043e\u044f\u043d\u0438\u0435\n"
    "/schedule HH:MM \u2014 \u0437\u0430\u043f\u043b\u0430\u043d\u0438\u0440\u043e\u0432\u0430\u0442\u044c\n"
    "/group @u1 @u2 ... \u2014 \u0433\u0440\u0443\u043f\u043f\u043e\u0432\u043e\u0439 \u0431\u0443\u0434\u0438\u043b\u044c\u043d\u0438\u043a\n"
    "/captcha on|off \u2014 \u043a\u0430\u043f\u0447\u0430 \u043f\u0440\u0438 \u043e\u0442\u0432\u0435\u0442\u0435"
)


async def init_providers():
    global whatsapp_provider, signal_provider, mqtt_bridge
    try:
        from providers.whatsapp_provider import WhatsAppProvider
        whatsapp_provider = WhatsAppProvider()
        await whatsapp_provider.init()
    except Exception as e:
        logger.warning(f"WhatsApp init failed: {e}")

    try:
        from providers.signal_provider import SignalProvider
        signal_provider = SignalProvider()
        await signal_provider.init()
    except Exception as e:
        logger.warning(f"Signal init failed: {e}")

    try:
        from mqtt_bridge import MQTTBridge
        mqtt_bridge = MQTTBridge()

        def on_mqtt_command(topic, payload):
            try:
                cmd = topic.split("/")[-1]
                if cmd == "start" and state["target"]:
                    state["running"] = True
                    state["stop_event"].clear()
                    if state["mode"] == "api":
                        asyncio.create_task(api_alarm_loop(None))
                elif cmd == "stop":
                    state["running"] = False
                    state["stop_event"].set()
            except Exception as e:
                logger.error(f"MQTT cmd error: {e}")

        mqtt_bridge.on_message(on_mqtt_command)
        mqtt_bridge.connect()
    except Exception as e:
        logger.warning(f"MQTT init failed: {e}")

    scheduler.load()
    scheduler.set_callback(on_schedule_alarm)
    scheduler.start()


def on_schedule_alarm(schedule):
    logger.info(f"Schedule triggered: {schedule}")
    target = schedule.get("target") or state["target"]
    mode = schedule.get("mode") or state["mode"]
    if target:
        state["target"] = target
        state["mode"] = mode
        state["running"] = True
        state["stop_event"].clear()
        if mode == "api":
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(api_alarm_loop(None))
            except Exception as e:
                logger.error(f"Scheduled alarm error: {e}")


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"\U0001f514 tg-alarm-bot\n\n{HELP}\n\n"
        f"\u0414\u043e\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044c\u043d\u043e:\n"
        f"\u2022 WhatsApp/Signal \u043f\u0440\u043e\u0432\u0430\u0439\u0434\u0435\u0440\u044b\n"
        f"\u2022 \u0420\u0430\u0441\u043f\u0438\u0441\u0430\u043d\u0438\u0435 (\u0431\u0443\u0434\u0438\u043b\u044c\u043d\u0438\u043a)\n"
        f"\u2022 \u0413\u0440\u0443\u043f\u043f\u043e\u0432\u044b\u0435 \u0431\u0443\u0434\u0438\u043b\u044c\u043d\u0438\u043a\u0438\n"
        f"\u2022 \u041a\u0430\u043f\u0447\u0430-\u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0430\n"
        f"\u2022 MQTT \u0438\u043d\u0442\u0435\u0433\u0440\u0430\u0446\u0438\u044f\n"
        f"\u2022 Web Dashboard (\u043f\u043e\u0440\u0442 5050)"
    )


async def cmd_set_target(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text(f"/set_target @username\n{HELP}")
        return
    state["target"] = ctx.args[0].lstrip("@")
    await update.message.reply_text(f"\u0426\u0435\u043b\u044c: {state['target']}")


async def cmd_mode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args or ctx.args[0] not in ("api", "macro", "whatsapp", "signal"):
        await update.message.reply_text("\u0420\u0435\u0436\u0438\u043c\u044b: api, macro, whatsapp, signal")
        return
    state["mode"] = ctx.args[0]
    await update.message.reply_text(f"\u0420\u0435\u0436\u0438\u043c: {state['mode']}")


async def cmd_go(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if state["running"]:
        await update.message.reply_text("\u0423\u0436\u0435 \u0440\u0430\u0431\u043e\u0442\u0430\u0435\u0442")
        return
    if not state["target"]:
        await update.message.reply_text("\u0421\u043d\u0430\u0447\u0430\u043b\u0430 /set_target")
        return
    if state["mode"] == "api" and not state["telethon_ready"]:
        await update.message.reply_text("Telethon \u043d\u0435 \u0430\u0432\u0442\u043e\u0440\u0438\u0437\u043e\u0432\u0430\u043d. \u0416\u0434\u0438...")
        if not await init_telethon(update):
            return

    state["running"] = True
    state["stop_event"].clear()
    mqtt_publish({"status": "running", "target": state["target"], "mode": state["mode"]})

    if state["mode"] == "api":
        asyncio.create_task(api_alarm_loop(update))
    elif state["mode"] == "whatsapp":
        asyncio.create_task(whatsapp_alarm_loop(update))
    elif state["mode"] == "signal":
        asyncio.create_task(signal_alarm_loop(update))
    else:
        threading.Thread(target=macro_alarm_loop, args=(update,), daemon=True).start()

    await update.message.reply_text(
        f"\u0417\u0430\u043f\u0443\u0449\u0435\u043d \u0434\u043e\u0437\u0432\u043e\u043d \u0434\u043e @{state['target']} ({state['mode']})"
    )


async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not state["running"]:
        await update.message.reply_text("\u041d\u0435 \u0440\u0430\u0431\u043e\u0442\u0430\u0435\u0442")
        return
    state["running"] = False
    state["stop_event"].set()
    mqtt_publish({"status": "stopped"})
    await update.message.reply_text("\u041e\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u043e")


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    sched_count = len(scheduler.list())
    group_count = len(group_manager.groups)
    captcha_enabled = "captcha_enabled" in state and state["captcha_enabled"]

    msg = (
        f"\u0426\u0435\u043b\u044c: @{state['target'] or '?'}\n"
        f"\u0420\u0435\u0436\u0438\u043c: {state['mode']}\n"
        f"\u0421\u0442\u0430\u0442\u0443\u0441: {'\u0440\u0430\u0431\u043e\u0442\u0430\u0435\u0442' if state['running'] else '\u0441\u0442\u043e\u0438\u0442'}\n"
        f"Telethon: {'\u043e\u043a' if state['telethon_ready'] else '\u043d\u0435\u0442'}\n"
        f"\u0420\u0430\u0441\u043f\u0438\u0441\u0430\u043d\u0438\u0439: {sched_count}\n"
        f"\u0413\u0440\u0443\u043f\u043f: {group_count}\n"
        f"\u041a\u0430\u043f\u0447\u0430: {'\u0432\u043a\u043b' if captcha_enabled else '\u0432\u044b\u043a\u043b'}\n"
        f"\u0414\u0430\u0448\u0431\u043e\u0440\u0434: http://localhost:5050"
    )
    await update.message.reply_text(msg)


async def cmd_schedule(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("/schedule HH:MM [label]")
        return
    time_str = ctx.args[0]
    label = " ".join(ctx.args[1:]) if len(ctx.args) > 1 else "Alarm"
    sid = scheduler.add({
        "time": time_str,
        "days": [0, 1, 2, 3, 4, 5, 6],
        "target": state["target"],
        "mode": state["mode"],
        "enabled": True,
        "label": label
    })
    await update.message.reply_text(f"\u0411\u0443\u0434\u0438\u043b\u044c\u043d\u0438\u043a \u043d\u0430 {time_str} \u0434\u043e\u0431\u0430\u0432\u043b\u0435\u043d (id: {sid})")


async def cmd_group(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("/group @user1 @user2 ...")
        return
    targets = [a.lstrip("@") for a in ctx.args]
    gid = group_manager.create_group(str(int(time.time())), targets)
    await update.message.reply_text(
        f"\u0413\u0440\u0443\u043f\u043f\u0430 \u0441\u043e\u0437\u0434\u0430\u043d\u0430: {gid}\n"
        f"\u0426\u0435\u043b\u0438: {', '.join(targets)}\n"
        f"/group_go {gid} \u2014 \u0437\u0430\u043f\u0443\u0441\u0442\u0438\u0442\u044c"
    )


async def cmd_group_go(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("/group_go <group_id>")
        return
    gid = ctx.args[0]
    group = group_manager.groups.get(gid)
    if not group:
        await update.message.reply_text("\u0413\u0440\u0443\u043f\u043f\u0430 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430")
        return

    def on_target_reply(group_id, target):
        asyncio.run_coroutine_threadsafe(
            update.message.reply_text(f"@{target} \u043e\u0442\u0432\u0435\u0442\u0438\u043b! \u041e\u0441\u0442\u0430\u043b\u043e\u0441\u044c: {group_manager.group_status(group_id)['pending']}"),
            update.get_bot().loop
        )

    group_manager._on_reply = on_target_reply

    if state["mode"] == "api" and not state["telethon_ready"]:
        if not await init_telethon(update):
            return

    def alarm_func(target):
        target_user = None
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            target_user = loop.run_until_complete(
                state["telethon_client"].get_entity(target)
            )
            random_id = random.randint(1, 2**31 - 1)
            a_bytes = os.urandom(256)
            a = int.from_bytes(a_bytes, "big") % (0xFFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3BE39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA051015728E5A8AAAC42DAD33170D04507A33A85521ABDF1CBA64ECFB850458DBEF0A8AEA71575D060C7DB3970F85A6E1E4C7ABF5AE8CDB0933D71E8C94E04A25619DCEE3D2261AD2EE6BF12FFA06D98A0864D87602733EC86A64521F2B18177B200CBBE117577A615D6C770988C0BAD946E208E24FA074E5AB3143DB5BFCE0FD108E4B82D120A93AD2CAFFFFFFFFFFFFFFFF - 1) + 1
            g_a = pow(2, a, 0xFFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3BE39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA051015728E5A8AAAC42DAD33170D04507A33A85521ABDF1CBA64ECFB850458DBEF0A8AEA71575D060C7DB3970F85A6E1E4C7ABF5AE8CDB0933D71E8C94E04A25619DCEE3D2261AD2EE6BF12FFA06D98A0864D87602733EC86A64521F2B18177B200CBBE117577A615D6C770988C0BAD946E208E24FA074E5AB3143DB5BFCE0FD108E4B82D120A93AD2CAFFFFFFFFFFFFFFFF)
            g_a_hash = hashlib.sha256(g_a.to_bytes(256, "big")).digest()

            from telethon.tl.functions.phone import RequestCallRequest, DiscardCallRequest
            from telethon.tl.types import PhoneCallProtocol, PhoneCallWaiting, InputPhoneCall, PhoneCallDiscardReasonMissed

            protocol = PhoneCallProtocol(udp_p2p=True, udp_reflector=True, min_layer=92, max_layer=92, library_versions=["4.0.0"])
            result = loop.run_until_complete(state["telethon_client"](RequestCallRequest(user_id=target_user, random_id=random_id, g_a_hash=g_a_hash, protocol=protocol)))
            call = result.call
            if isinstance(call, PhoneCallWaiting):
                time.sleep(12)
                try:
                    loop.run_until_complete(state["telethon_client"](DiscardCallRequest(peer=InputPhoneCall(id=call.id, access_hash=call.access_hash), duration=0, reason=PhoneCallDiscardReasonMissed(), connection_id=0)))
                except:
                    pass
        except Exception as e:
            logger.error(f"Group alarm error for {target}: {e}")
        finally:
            loop.close()

    group_manager.start_group(gid, alarm_func)
    await update.message.reply_text(f"\u0413\u0440\u0443\u043f\u043f\u043e\u0432\u043e\u0439 \u0431\u0443\u0434\u0438\u043b\u044c\u043d\u0438\u043a \u0437\u0430\u043f\u0443\u0449\u0435\u043d: {', '.join(group['targets'])}")


async def cmd_captcha(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("/captcha on|off")
        return
    state["captcha_enabled"] = ctx.args[0] == "on"
    await update.message.reply_text(f"\u041a\u0430\u043f\u0447\u0430: {'\u0432\u043a\u043b\u044e\u0447\u0435\u043d\u0430' if state['captcha_enabled'] else '\u0432\u044b\u043a\u043b\u044e\u0447\u0435\u043d\u0430'}")


async def init_telethon(update):
    from telethon import TelegramClient
    if not all([API_ID, API_HASH, PHONE]):
        await update.message.reply_text("\u041d\u0435\u0442 API_ID/API_HASH/PHONE \u0432 .env")
        return False
    try:
        client = TelegramClient("tg_alarm_bot_session", API_ID, API_HASH)
        await client.start(phone=PHONE)
        me = await client.get_me()
        state["telethon_client"] = client
        state["telethon_ready"] = True
        await update.message.reply_text(f"\u0410\u0432\u0442\u043e\u0440\u0438\u0437\u043e\u0432\u0430\u043d \u043a\u0430\u043a {me.first_name}")
        return True
    except Exception as e:
        await update.message.reply_text(f"\u041e\u0448\u0438\u0431\u043a\u0430 Telethon: {e}")
        return False


async def api_alarm_loop(update):
    client = state["telethon_client"]
    target = state["target"]
    user_id = update.effective_user.id if update else None
    captcha_solved = False

    try:
        target_user = await client.get_entity(target)
    except Exception as e:
        if update:
            await update.message.reply_text(f"\u041d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d {target}: {e}")
        state["running"] = False
        return

    last_msg_id = 0
    msgs = await client.get_messages(target_user, limit=1)
    if msgs:
        last_msg_id = msgs[0].id

    async def on_msg(event):
        nonlocal captcha_solved
        if (event.is_private and event.sender_id == target_user.id
                and not event.message.out):
            if state.get("captcha_enabled") and not captcha_solved:
                challenge_id, question = captcha.create_challenge(target, 'math')
                if update:
                    asyncio.create_task(
                        update.message.reply_text(
                            f"\U0001f6a8 @{target} \u043d\u0430\u043f\u0438\u0441\u0430\u043b! \u041d\u043e \u0441\u043d\u0430\u0447\u0430\u043b\u0430 \u0440\u0435\u0448\u0438 \u043a\u0430\u043f\u0447\u0443:\n{question}\n\n/captcha_answer {challenge_id} \u043e\u0442\u0432\u0435\u0442"
                        )
                    )
                captcha_solved = False
                return
            state["running"] = False
            state["stop_event"].set()
            if update:
                await update.message.reply_text(f"@{target} \u043d\u0430\u043f\u0438\u0441\u0430\u043b(\u0430)! \u0414\u043e\u0437\u0432\u043e\u043d \u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043d")
            group_manager.mark_replied("default", target)
            mqtt_publish({"status": "answered", "target": target})

    client.add_event_handler(on_msg)

    while state["running"] and not state["stop_event"].is_set():
        msgs = await client.get_messages(target_user, limit=1)
        if msgs and msgs[0].id > last_msg_id:
            if update:
                await update.message.reply_text(f"@{target} \u043d\u0430\u043f\u0438\u0441\u0430\u043b(\u0430)! \u0414\u043e\u0437\u0432\u043e\u043d \u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043d")
            break

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

        msgs = await client.get_messages(target_user, limit=1)
        if msgs and msgs[0].id > last_msg_id:
            if update:
                await update.message.reply_text(f"@{target} \u043d\u0430\u043f\u0438\u0441\u0430\u043b(\u0430)! \u0414\u043e\u0437\u0432\u043e\u043d \u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043d")
            break

        for _ in range(25):
            if state["stop_event"].is_set():
                break
            await asyncio.sleep(1)

    state["running"] = False
    mqtt_publish({"status": "finished"})
    if update:
        await update.message.reply_text("\u0414\u043e\u0437\u0432\u043e\u043d \u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043d")


async def whatsapp_alarm_loop(update):
    if not whatsapp_provider or not whatsapp_provider.ready:
        await update.message.reply_text("WhatsApp \u043f\u0440\u043e\u0432\u0430\u0439\u0434\u0435\u0440 \u043d\u0435 \u0433\u043e\u0442\u043e\u0432")
        state["running"] = False
        return

    target = state["target"]

    def on_reply():
        state["running"] = False
        state["stop_event"].set()
        asyncio.run_coroutine_threadsafe(
            update.message.reply_text(f"@{target} \u043d\u0430\u043f\u0438\u0441\u0430\u043b \u0432 WhatsApp!"),
            update.get_bot().loop
        )

    reply_task = asyncio.create_task(whatsapp_provider.wait_for_reply(target, on_reply))

    while state["running"] and not state["stop_event"].is_set():
        await whatsapp_provider.make_call(target)
        for _ in range(30):
            if state["stop_event"].is_set():
                break
            await asyncio.sleep(1)

    await whatsapp_provider.cleanup()
    state["running"] = False


async def signal_alarm_loop(update):
    if not signal_provider or not signal_provider.ready:
        await update.message.reply_text("Signal \u043f\u0440\u043e\u0432\u0430\u0439\u0434\u0435\u0440 \u043d\u0435 \u0433\u043e\u0442\u043e\u0432")
        state["running"] = False
        return

    target = state["target"]

    def on_reply():
        state["running"] = False
        state["stop_event"].set()
        asyncio.run_coroutine_threadsafe(
            update.message.reply_text(f"@{target} \u043d\u0430\u043f\u0438\u0441\u0430\u043b \u0432 Signal!"),
            update.get_bot().loop
        )

    reply_task = asyncio.create_task(signal_provider.wait_for_reply(target, on_reply))

    while state["running"] and not state["stop_event"].is_set():
        await signal_provider.send_message(target, "\U0001f514 \u041f\u0440\u043e\u0441\u043d\u0438\u0441\u044c!")
        for _ in range(60):
            if state["stop_event"].is_set():
                break
            await asyncio.sleep(1)

    await signal_provider.cleanup()
    state["running"] = False


def macro_alarm_loop(update):
    try:
        import pyautogui
        import win32gui, win32con
        import cv2, numpy as np, mss
    except ImportError:
        asyncio.run_coroutine_threadsafe(
            update.message.reply_text("\u041d\u0435\u0442 \u0437\u0430\u0432\u0438\u0441\u0438\u043c\u043e\u0441\u0442\u0435\u0439: pip install -r tg_alarm_macro_requirements.txt"),
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
            update.message.reply_text("Telegram Desktop \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d"),
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
            update.message.reply_text(f"\u041d\u0443\u0436\u043d\u0430 \u043a\u0430\u043b\u0438\u0431\u0440\u043e\u0432\u043a\u0430: \u0437\u0430\u043f\u0443\u0441\u0442\u0438 {sys.argv[0]} --calibrate"),
            update.get_bot().loop
        )
        state["running"] = False
        return

    with open(cfg_file) as f:
        cfg = json.load(f)

    l, t, w, h = get_rect(hwnd)
    base = screenshot(l, t + int(h * 0.25), w, int(h * 0.55))
    asyncio.run_coroutine_threadsafe(
        update.message.reply_text("\u041c\u0430\u043a\u0440\u043e-\u0434\u043e\u0437\u0432\u043e\u043d \u0437\u0430\u043f\u0443\u0449\u0435\u043d"),
        update.get_bot().loop
    )

    while state["running"] and not state["stop_event"].is_set():
        time.sleep(10)
        curr = screenshot(l, t + int(h * 0.25), w, int(h * 0.55))
        if detect(base, curr):
            asyncio.run_coroutine_threadsafe(
                update.message.reply_text("\u041d\u043e\u0432\u043e\u0435 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435!"),
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
        update.message.reply_text("\u041c\u0430\u043a\u0440\u043e-\u0434\u043e\u0437\u0432\u043e\u043d \u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043d"),
        update.get_bot().loop
    )


def mqtt_publish(data):
    if mqtt_bridge and mqtt_bridge.ready:
        try:
            mqtt_bridge.publish_state(data)
        except Exception:
            pass


def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set in .env")
        return

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("set_target", cmd_set_target))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("go", cmd_go))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("group", cmd_group))
    app.add_handler(CommandHandler("group_go", cmd_group_go))
    app.add_handler(CommandHandler("captcha", cmd_captcha))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_providers())

    logger.info("\u0431\u043e\u0442 \u0437\u0430\u043f\u0443\u0449\u0435\u043d")
    app.run_polling()


if __name__ == "__main__":
    main()
