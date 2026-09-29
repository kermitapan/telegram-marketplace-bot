import asyncio
from scraper import build_client, register_handler
from classifier import classify_message, is_worth_notifying
from notifier import send_alert
from prefilter import is_likely_wish, is_already_taken
from config import TELEGRAM_PHONE, TARGET_GROUP

# message IDs we've notified about — used to detect "reserviert" edits
_notified_ids: set[int] = set()


def _build_link(event) -> str | None:
    chat = getattr(event.message.chat, 'username', None)
    if chat:
        return f"https://t.me/{chat}/{event.message.id}"
    return None


async def _download_image(client, event) -> bytes | None:
    msg = event.message
    if msg.photo or (msg.document and msg.document.mime_type and msg.document.mime_type.startswith('image/')):
        try:
            return await client.download_media(msg, bytes)
        except Exception as e:
            print(f"[main] image download failed: {e}")
    return None


async def main():
    client = build_client()

    async def on_message(event):
        text = (event.message.text or getattr(event.message, 'caption', None) or '').strip()
        sender = getattr(event.message.sender, 'first_name', None) or getattr(event.message.sender, 'username', None) or '?'
        has_image = bool(event.message.photo or (event.message.document and event.message.document.mime_type and event.message.document.mime_type.startswith('image/')))

        print(f"\n{'─'*60}")
        print(f"[new]  {sender} | {'📷 ' if has_image else ''}text={text[:80]!r}")

        if len(text) < 5 and not has_image:
            print(f"[skip] too short, no image")
            return

        if is_already_taken(text):
            print(f"[skip] already taken — {text[:60]!r}")
            return

        if is_likely_wish(text):
            print(f"[skip] wish detected — {text[:60]!r}")
            return

        image_bytes = None
        if has_image:
            print(f"[img]  downloading ...")
            image_bytes = await _download_image(client, event)
            print(f"[img]  {'ok' if image_bytes else 'failed'}")

        print(f"[api]  calling Gemini ...")
        result = classify_message(text, image_bytes)
        if result is None:
            print(f"[api]  failed, skipping")
            return

        print(f"[api]  giveaway={result.get('is_giveaway')} | category={result.get('category')} | functional={result.get('is_functional')} | chf={result.get('estimated_value_chf')} | kg={result.get('estimated_weight_kg')} | loc={result.get('postcode') or '—'} | large_furniture={result.get('is_large_furniture')}")
        print(f"[api]  item: {result.get('item_description') or '—'}")
        print(f"[api]  why:  {result.get('reason')}")

        if is_worth_notifying(result):
            _notified_ids.add(event.message.id)
            await send_alert(client, result, text, _build_link(event))
            print(f"[+++]  NOTIFIED")
        else:
            print(f"[skip] below threshold or filtered")

    async def on_edit(event):
        msg_id = event.message.id
        if msg_id not in _notified_ids:
            return
        text = (event.message.text or getattr(event.message, 'caption', None) or '').strip()
        if is_already_taken(text):
            _notified_ids.discard(msg_id)
            await client.send_message('me', f"Already taken — stop chasing it.\n\n_{text[:200]}_", parse_mode='md')
            print(f"\n[!!!]  TAKEN ALERT — msg_id={msg_id} | {text[:60]!r}")

    register_handler(client, on_message, on_edit)

    await client.start(phone=TELEGRAM_PHONE)
    print(f"[main] connected, watching '{TARGET_GROUP}' ...")
    await client.run_until_disconnected()


if __name__ == '__main__':
    asyncio.run(main())
