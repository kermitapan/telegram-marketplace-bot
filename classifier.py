import json
import re
import time
import io
import os
import itertools
import google.generativeai as genai
from PIL import Image
from config import GEMINI_API_KEYS, MIN_VALUE_CHF

BIKE_WEIGHT_LIMIT_KG = 15
BIKE_VALUE_THRESHOLD_CHF = 150

_EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), 'examples')


def _load_examples() -> str:
    if not os.path.isdir(_EXAMPLES_DIR):
        return ''
    parts = []
    for fname in sorted(os.listdir(_EXAMPLES_DIR)):
        if fname.endswith('.txt'):
            with open(os.path.join(_EXAMPLES_DIR, fname), encoding='utf-8') as f:
                parts.append(f.read().strip())
    if not parts:
        return ''
    return '\n\nReal examples of valuable finds from this group:\n\n' + '\n\n---\n\n'.join(parts)


_SYSTEM_INSTRUCTION = """You analyze messages (and optionally images) from a free items Telegram group in Zurich, Switzerland.
People post in German or English. Items are always offered for free.

Rules:
- is_giveaway = true only if someone is OFFERING an item. False if they are REQUESTING/WISHING for one.
- Requests use: "suche", "looking for", "anyone have", "hätte jemand", "wer hat", "brauche", or handwritten text on an image saying the same.
- If there is an image, look for handwritten or printed text in it — a handwritten "suche" on a photo means it is a wish, not a giveaway.
- postcode: extract the pickup location from the text. Accept either:
  a) A 4-digit Swiss postcode (e.g. "8005")
  b) A Zurich Kreis reference: K1–K12 or "Kreis 1"–"Kreis 12" or "k4", "kreis4" etc. → return as "K4"
  If neither is present, return empty string.
- estimated_weight_kg: realistic weight of the item in kg. Use 0 if unknown or not applicable (e.g. clothing bag).
- estimated_value_chf: median second-hand price in CHF on Ricardo.ch / tutti.ch / anibis.ch. Swiss market is higher than Germany.
  Pay special attention to high-value categories: vintage/brand sports gear (skis, snowboards, windsurfers, bikes,
  climbing gear), workshop machinery (lathes, drills, compressors), musical instruments, cameras, and quality
  electronics. A vintage pair of skis or a windsurfing board can easily be worth CHF 200–500+.
- is_large_furniture: true if the item is physically impossible to transport by bicycle regardless of weight —
  sofas, sectionals, beds, bed frames, mattresses, wardrobes, large bookshelves, dining tables, washing machines,
  fridges, dishwashers, or anything requiring a van. False for everything else.
- category: one of "electronics", "clothing", "furniture", "books", "sports", "kitchen", "toys", "other".
  Electronics = laptops, phones, tablets, headphones, cameras, gaming gear, audio equipment, small appliances, etc.
- is_functional: true if the item is described as working. False if explicitly broken, defective, "for parts",
  "startet nicht", "defekt", "kaputt", "funktioniert nicht", "as-is with issues", or condition unknown for electronics.
  For non-electronics, set is_functional to true by default.

Respond with valid JSON only — no markdown:
{
  "is_giveaway": true,
  "is_large_furniture": false,
  "category": "electronics",
  "is_functional": true,
  "item_description": "Dyson V8 vacuum cleaner, good condition",
  "estimated_value_chf": 200,
  "estimated_weight_kg": 3,
  "postcode": "8005",
  "confidence": "high",
  "reason": "Used Dyson V8 sells for CHF 180–250 on Ricardo.ch."
}

confidence must be one of: "low", "medium", "high".
If is_giveaway is false, set estimated_value_chf and estimated_weight_kg to 0, item_description to "", is_large_furniture to false, is_functional to false.""" + _load_examples()

_GENERATION_CONFIG = genai.GenerationConfig(
    response_mime_type='application/json',
    temperature=0.1,
)

_model = genai.GenerativeModel(
    model_name='gemini-2.5-flash-lite',
    system_instruction=_SYSTEM_INSTRUCTION,
)

_key_cycle = itertools.cycle(range(len(GEMINI_API_KEYS)))
_current_index = next(_key_cycle)


def _use_next_key():
    global _current_index
    _current_index = next(_key_cycle)
    genai.configure(api_key=GEMINI_API_KEYS[_current_index])


# configure with first key on startup
genai.configure(api_key=GEMINI_API_KEYS[_current_index])


def _build_parts(text: str, image_bytes: bytes | None) -> list:
    parts = []
    if image_bytes:
        parts.append(Image.open(io.BytesIO(image_bytes)))
    parts.append(f"Message text:\n{text}" if text else "No text — analyze the image only.")
    return parts


def classify_message(text: str, image_bytes: bytes | None = None) -> dict | None:
    parts = _build_parts(text, image_bytes)
    # try each key once before giving up
    for attempt in range(len(GEMINI_API_KEYS)):
        try:
            response = _model.generate_content(parts, generation_config=_GENERATION_CONFIG)
            parsed = json.loads(response.text)
            return parsed[0] if isinstance(parsed, list) else parsed
        except Exception as e:
            msg = str(e)
            if '429' in msg:
                daily_hit = 'PerDay' in msg
                if daily_hit and len(GEMINI_API_KEYS) > 1:
                    print(f"[classifier] key {_current_index} daily quota exhausted, switching ...")
                    _use_next_key()
                    continue
                # per-minute rate limit — wait and retry on same key
                match = re.search(r'retry_delay\s*\{\s*seconds:\s*(\d+)', msg)
                wait = int(match.group(1)) + 2 if match else 15
                print(f"[classifier] rate limited on key {_current_index}, waiting {wait}s ...")
                time.sleep(wait)
            else:
                print(f"[classifier] error: {e}")
                return None
    print("[classifier] all keys exhausted")
    return None


def is_worth_notifying(result: dict) -> bool:
    if not result.get('is_giveaway'):
        return False
    if result.get('is_large_furniture'):
        return False
    if result.get('category') == 'electronics' and not result.get('is_functional'):
        return False
    value = result.get('estimated_value_chf', 0)
    if value < MIN_VALUE_CHF:
        return False
    weight = result.get('estimated_weight_kg', 0)
    if value < BIKE_VALUE_THRESHOLD_CHF and weight > BIKE_WEIGHT_LIMIT_KG:
        return False
    return True
