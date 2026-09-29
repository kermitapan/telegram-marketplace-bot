import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_API_ID = int(os.getenv('TELEGRAM_API_ID') or '0')
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH', '')
TELEGRAM_PHONE = os.getenv('TELEGRAM_PHONE', '')
_tg_raw = os.environ['TARGET_GROUP']
TARGET_GROUP = int(_tg_raw) if _tg_raw.lstrip('-').isdigit() else _tg_raw
# Support multiple keys as comma-separated list: GEMINI_API_KEYS=key1,key2,key3
# Falls back to single GEMINI_API_KEY for backwards compatibility
_keys_raw = os.getenv('GEMINI_API_KEYS', '') or os.getenv('GEMINI_API_KEY', '')
GEMINI_API_KEYS = [k.strip() for k in _keys_raw.split(',') if k.strip()]
if not GEMINI_API_KEYS:
    raise ValueError("Set GEMINI_API_KEYS (comma-separated) or GEMINI_API_KEY in .env")
GEMINI_API_KEY = GEMINI_API_KEYS[0]
MIN_VALUE_CHF = int(os.getenv('MIN_VALUE_CHF', '20'))
