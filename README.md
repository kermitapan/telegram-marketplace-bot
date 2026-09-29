# Telegram Marketplace Listener

A monitor for "free stuff" Telegram groups. It reads every new post, uses a
vision-capable LLM to work out *what* the item actually is and *what it's worth*,
and sends you a direct message only when something is genuinely worth the trip.

Free-item groups in a city like Zürich produce hundreds of posts a day. The
overwhelming majority are junk, requests rather than offers, or furniture you
could never get home. This filters that down to the handful of posts that matter,
so you find the windsurfing board instead of scrolling past it.

## How it works

```
New post in group
        │
        ▼
┌───────────────────┐   "suche", "looking for", "reserviert"  ──▶ drop
│  Regex pre-filter │   Kills obvious requests and already-claimed
└─────────┬─────────┘   items before spending an API call
          ▼
┌───────────────────┐   Text + photo → Gemini 2.5 Flash Lite
│  LLM classifier   │   Returns structured JSON: item, CHF value,
└─────────┬─────────┘   weight, postcode, condition, confidence
          ▼
┌───────────────────┐   Value ≥ threshold? Transportable by bike?
│  Decision rules   │   Electronics actually working? Not a sofa?
└─────────┬─────────┘
          ▼
   Telegram DM to yourself
```

### The pre-filter earns its keep

The free Gemini tier allows 5 requests per minute, so the cheapest request is the
one you never make. A regex pass drops posts that are clearly wishes rather than
offers — `suche`, `brauche`, `hätte jemand`, `looking for`, `wtb` — unless the
post *also* contains giveaway language, which resolves the ambiguous cases in
favour of asking the model. It also recognises `reserviert` / `vergeben` /
`schon weg` to skip items already claimed.

### Vision matters more than you'd expect

Plenty of posts are a photo with no caption, or a photo of a handwritten note.
A handwritten "Suche Kinderwagen" on a scrap of paper is a *request*, and a
text-only classifier reads it as an empty message and guesses. The image goes to
the model alongside the caption, and the system prompt explicitly instructs it to
read text inside the picture before deciding.

### Valuation is the interesting part

The model is asked for a median second-hand price on the Swiss resale market
(Ricardo, tutti, anibis) rather than a generic "what's this worth", because Swiss
prices run well above German ones and a generic estimate is systematically low.
The prompt also calls out the categories where free listings hide real value —
vintage sports gear, workshop machinery, instruments, cameras — since those are
exactly the items a naive estimate undervalues.

### Filters tuned for someone on a bike

A decision is more than a price threshold:

| Rule | Why |
| --- | --- |
| `estimated_value_chf >= MIN_VALUE_CHF` | Ignore the genuinely worthless |
| Reject `is_large_furniture` | Sofas and mattresses need a van, whatever they're worth |
| Reject heavy items under CHF 150 | Over ~15 kg it's only worth a taxi if the item is |
| Reject broken electronics | A dead laptop is worth roughly nothing |

### Follow-up alerts

Good items go fast. Posts are tracked after you're notified, and if the author
later edits theirs to say `reserviert`, you get a second message telling you to
stop chasing it — a genuine annoyance when you're already halfway across town.

### Few-shot examples from real finds

`examples/*.txt` are loaded into the system prompt at startup. Each records a
post, what actually happened when it was collected, and why it was a good find.
Adding your own successes steadily sharpens the model's sense of what counts as
valuable in your particular group.

## Design notes

**MTProto, not the Bot API.** Telegram bots can't read messages in a group they
don't administer, which rules out the Bot API for monitoring a group you're
simply a member of. This signs in through [Telethon](https://docs.telethon.dev/)
as your own user account, so the group sees an ordinary member. The client
identifies itself with a plausible device profile and a `de-CH` locale to match
that.

**Key rotation.** Free-tier daily quotas are small. Several API keys can be
supplied and the classifier moves to the next one when one is exhausted for the
day, distinguishing a daily cap (rotate) from a per-minute rate limit (wait and
retry on the same key).

**Structured output.** The model is pinned to `response_mime_type: application/json`
at `temperature=0.1`, so parsing is a plain `json.loads` rather than a regex hunt
through prose.

## Setup

```bash
git clone https://github.com/kermitapan/telegram-marketplace-listener.git
cd telegram-marketplace-listener
pip install -r requirements.txt
cp .env.example .env    # then fill it in
python main.py
```

You'll need:

- **Telegram API credentials** from [my.telegram.org/apps](https://my.telegram.org/apps)
- **A Gemini API key** from [aistudio.google.com](https://aistudio.google.com)
- **Membership of the group** you want to watch

On first run Telethon asks for the login code Telegram sends you, then caches the
session in `session.session`. That file is a credential — it's gitignored, and it
should stay that way.

### Configuration

| Variable | Description |
| --- | --- |
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` | From my.telegram.org/apps |
| `TELEGRAM_PHONE` | Your number, international format |
| `TARGET_GROUP` | Public username, or numeric ID for a private group |
| `GEMINI_API_KEYS` | One key, or several comma-separated to rotate |
| `MIN_VALUE_CHF` | Alert threshold in CHF (default `20`) |

## Testing

Validate the classifier on a fixed set of German and English samples — giveaways,
requests, and edge cases like admin announcements — without connecting to
Telegram at all:

```bash
python test_classifier.py
```

Drop images into `test_images/` to exercise the vision path. Prefix a filename
with `giveaway_` or `wish_` and the expected result is inferred from the name.

To measure accuracy against real traffic, export a group's history from Telegram
Desktop as HTML into a `ChatExport_*/` folder and run it through the pipeline:

```bash
python test_export.py --limit 20 --seed 42   # reproducible random sample
python test_export.py --limit 0              # everything (slow, burns quota)
```

Results land in `export_results.jsonl` for review. Both the export and the
results stay gitignored — they contain other people's names, photos and
addresses.

## Project layout

| File | Role |
| --- | --- |
| `main.py` | Event loop: wires scraper → filter → classifier → notifier |
| `scraper.py` | Telethon client and event handlers, with flood-wait handling |
| `prefilter.py` | Regex heuristics for wishes and already-claimed items |
| `classifier.py` | Gemini prompt, JSON parsing, key rotation, decision rules |
| `notifier.py` | Formats the alert DM |
| `config.py` | Environment loading and validation |
| `test_classifier.py` | Fixed-sample accuracy check |
| `test_export.py` | Batch evaluation over a real chat export |

## A note on privacy

This reads a group you are a member of, and only to decide whether to notify
*you*. Nothing is republished, no profile of any poster is built, and nothing
leaves your machine except the text and image of a single post going to the
Gemini API for classification. If you run this, respect your group's rules — some
explicitly disallow automated tools, and being a good member of a gift economy
matters more than a faster alert.

## License

MIT — see [LICENSE](LICENSE).
