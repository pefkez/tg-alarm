import os, sys, asyncio, random, hashlib, struct, time
from pathlib import Path
from telethon import TelegramClient, events
from telethon.tl.functions.phone import RequestCallRequest, DiscardCallRequest
from telethon.tl.types import (
    InputPhoneCall, PhoneCallWaiting, PhoneCallDiscarded,
    PhoneCallDiscardReasonMissed, PhoneCallDiscardReasonBusy,
    PhoneCallProtocol, MessageEmpty
)

DH_PRIME = 0xFFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3BE39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA051015728E5A8AAAC42DAD33170D04507A33A85521ABDF1CBA64ECFB850458DBEF0A8AEA71575D060C7DB3970F85A6E1E4C7ABF5AE8CDB0933D71E8C94E04A25619DCEE3D2261AD2EE6BF12FFA06D98A0864D87602733EC86A64521F2B18177B200CBBE117577A615D6C770988C0BAD946E208E24FA074E5AB3143DB5BFCE0FD108E4B82D120A93AD2CAFFFFFFFFFFFFFFFF
DH_GENERATOR = 2

CALL_RING_SECS = 12
RETRY_DELAY = 25
MAX_CALLS = 50

API_ID = int(os.environ.get('TG_API_ID', '0') or '0')
API_HASH = os.environ.get('TG_API_HASH', '') or ''
PHONE = os.environ.get('TG_PHONE', '') or ''
TARGET = os.environ.get('TG_TARGET', '') or ''

if not all([API_ID, API_HASH, PHONE, TARGET]):
    print("Usage: set environment variables:")
    print("  TG_API_ID     — your API ID from my.telegram.org")
    print("  TG_API_HASH   — your API hash from my.telegram.org")
    print("  TG_PHONE      — your phone number (e.g. +79123456789)")
    print("  TG_TARGET     — target username (e.g. @girlfriend or phone)")
    sys.exit(1)

client = TelegramClient('tg_alarm_session', API_ID, API_HASH)
target_user = None
my_id = None
last_msg_id = 0
is_running = True

async def get_last_msg_id():
    msgs = await client.get_messages(target_user, limit=1)
    return msgs[0].id if msgs else 0

async def check_new_msg():
    global last_msg_id
    current = await get_last_msg_id()
    if current > last_msg_id:
        msgs = await client.get_messages(target_user, limit=1)
        for m in msgs:
            if m.id > last_msg_id and not isinstance(m, MessageEmpty) and m.out is False:
                return True
    return False

async def make_call():
    random_id = random.randint(1, 2**31 - 1)
    a_bytes = os.urandom(256)
    a = int.from_bytes(a_bytes, 'big') % (DH_PRIME - 1) + 1
    g_a = pow(DH_GENERATOR, a, DH_PRIME)
    g_a_bytes = g_a.to_bytes(256, 'big')
    g_a_hash = hashlib.sha256(g_a_bytes).digest()

    protocol = PhoneCallProtocol(
        udp_p2p=True, udp_reflector=True,
        min_layer=92, max_layer=92,
        library_versions=['4.0.0']
    )

    result = await client(RequestCallRequest(
        user_id=target_user,
        random_id=random_id,
        g_a_hash=g_a_hash,
        protocol=protocol
    ))
    call = result.call
    print(f"  → State: {type(call).__name__}")

    if isinstance(call, PhoneCallWaiting):
        print(f"  📞 Ringing ({CALL_RING_SECS}s)...")
        await asyncio.sleep(CALL_RING_SECS)

        try:
            await client(DiscardCallRequest(
                peer=InputPhoneCall(id=call.id, access_hash=call.access_hash),
                duration=0,
                reason=PhoneCallDiscardReasonMissed(),
                connection_id=0
            ))
            print("  ✓ Call ended")
        except Exception as e:
            print(f"  ⚠ Discard: {e}")
    else:
        print(f"  ⚠ Unexpected call state: {type(call).__name__}")

@client.on(events.NewMessage)
async def on_message(event):
    global is_running
    if event.is_private and event.sender_id == target_user.id and not event.message.out:
        name = target_user.first_name or target_user.username or 'unknown'
        print(f"\n✅ {name} wrote: {event.message.text or '(media)'}")
        is_running = False

async def main():
    global target_user, my_id, last_msg_id, is_running

    await client.start(phone=PHONE)
    me = await client.get_me()
    my_id = me.id
    print(f"✓ Logged in as {me.first_name} (id={my_id})")

    try:
        target_user = await client.get_entity(TARGET)
    except Exception as e:
        print(f"✗ Cannot find target '{TARGET}': {e}")
        return

    name = target_user.first_name or target_user.username or TARGET
    print(f"✓ Target: {name} (id={target_user.id})")

    last_msg_id = await get_last_msg_id()
    print(f"✓ Last message id: {last_msg_id}")
    print(f"▶ Starting alarm loop (calls every {CALL_RING_SECS + RETRY_DELAY}s)...\n")

    calls_made = 0
    while is_running:
        if await check_new_msg():
            print(f"\n✅ New message from {name} detected! Stopping.")
            break

        if calls_made >= MAX_CALLS:
            print(f"\n⏹ Max calls reached ({MAX_CALLS}), stopping.")
            break

        print(f"⏰ Calling {name}... ({calls_made}/{MAX_CALLS})")
        try:
            await make_call()
        except Exception as e:
            print(f"  ✗ Error: {e}")
        calls_made += 1

        if not is_running:
            break

        if not await check_new_msg():
            print(f"⏳ Wait {RETRY_DELAY}s...")
            for _ in range(RETRY_DELAY):
                if not is_running:
                    break
                await asyncio.sleep(1)
        else:
            print(f"\n✅ New message from {name} detected! Stopping.")
            break

    print("\n🏁 Done.")

asyncio.run(main())