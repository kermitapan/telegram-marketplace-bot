import asyncio
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from config import TELEGRAM_API_ID, TELEGRAM_API_HASH, TARGET_GROUP


def build_client() -> TelegramClient:
    # Mimics a Swiss iPhone user to avoid looking like a bot.
    # Telethon connects via MTProto (user account), not the Bot API,
    # so the group sees a normal member — not a bot — reading messages.
    return TelegramClient(
        'session',
        TELEGRAM_API_ID,
        TELEGRAM_API_HASH,
        device_model='iPhone 15 Pro',
        system_version='17.4.1',
        app_version='10.2.6',
        lang_code='de',
        system_lang_code='de-CH',
    )


def register_handler(client: TelegramClient, on_new_message, on_edit=None):
    @client.on(events.NewMessage(chats=TARGET_GROUP))
    async def _new_handler(event):
        try:
            await on_new_message(event)
        except FloodWaitError as e:
            print(f"[scraper] rate-limited by Telegram, sleeping {e.seconds}s")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print(f"[scraper] unhandled error in new handler: {e}")

    if on_edit:
        @client.on(events.MessageEdited(chats=TARGET_GROUP))
        async def _edit_handler(event):
            try:
                await on_edit(event)
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except Exception as e:
                print(f"[scraper] unhandled error in edit handler: {e}")
