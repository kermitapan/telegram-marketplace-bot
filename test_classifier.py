"""
Run this to validate the classifier before connecting to Telegram.
Usage: python test_classifier.py

To test image recognition, drop .jpg/.png files into test_images/.
Name them so the expected outcome is clear, e.g.:
  giveaway_sofa.jpg       → should be a giveaway
  wish_suche.jpg          → should NOT be a giveaway (handwritten wish)
"""

import sys
import io
import time
import os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from classifier import classify_message, is_worth_notifying

TEXT_SAMPLES = [
    # (message_text, expected_is_giveaway)

    # giveaways
    ("Hallo, ich verschenke ein IKEA Billy Regal, weiss, 80cm breit. Abholung 8037 Zürich. Bitte PN!", True),
    ("Free to take: Sony headphones WH-1000XM3, works perfectly, just upgraded. Pickup 8005 Oerlikon.", True),
    ("Verschenke: MacBook Pro 2017 13\", startet nicht mehr, gut für Ersatzteile. Abholung 8001 Zürich HB.", True),
    ("Giving away a bag of kids clothes, sizes 2–4 years, good condition. Free, 8008 Zürich Seefeld.", True),
    ("Gratis abzugeben: Dyson V8 Staubsauger, funktioniert einwandfrei, Abholung 8047 Zürich Altstetten.", True),
    ("Verschenke grosse Ikea Hemnes Kommode, 8 Schubladen, weiss. Abholung 8057 Zürich.", True),

    # wishes
    ("Suche dringend einen Kinderwagen, budget ist leider 0 CHF. Kann jemand helfen?", False),
    ("Looking for a bicycle, doesn't have to be perfect. Anyone in Zurich?", False),
    ("Hätte jemand eine Küchentisch für mich? Brauche dringend einen.", False),

    # edge cases
    ("Admin: Bitte keine Verkaufsangebote posten, nur Verschenken erlaubt!", False),
    ("Danke an alle! Das Regal ist vergeben.", False),
]


def run_text_tests():
    passed = failed = 0
    for text, expected in TEXT_SAMPLES:
        time.sleep(13)
        result = classify_message(text)
        if result is None:
            print(f"[ERROR] API failed\n  {text[:80]!r}\n")
            failed += 1
            continue

        actual = result.get('is_giveaway')
        ok = actual == expected
        passed += ok
        failed += (not ok)

        status = "PASS" if ok else "FAIL"
        weight = result.get('estimated_weight_kg', 0)
        notify = is_worth_notifying(result)
        bike = "yes" if (weight == 0 or weight <= 15) else f"no ({weight}kg)"

        print(f"[{status}] expected={expected} got={actual}")
        print(f"  item   : {result.get('item_description') or '—'}")
        print(f"  value  : CHF {result.get('estimated_value_chf', 0)}")
        print(f"  weight : ~{weight}kg  bike={bike}")
        print(f"  postcode: {result.get('postcode') or '—'}")
        print(f"  conf   : {result.get('confidence')}  |  notify={notify}")
        print(f"  why    : {result.get('reason')}")
        print(f"  msg    : {text[:80]!r}")
        print()

    return passed, failed


def run_image_tests():
    folder = os.path.join(os.path.dirname(__file__), 'test_images')
    if not os.path.isdir(folder):
        print("[images] no test_images/ folder found, skipping image tests\n")
        return 0, 0

    files = [f for f in os.listdir(folder) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    if not files:
        print("[images] test_images/ is empty, skipping image tests\n")
        return 0, 0

    passed = failed = 0
    for filename in sorted(files):
        path = os.path.join(folder, filename)
        with open(path, 'rb') as f:
            image_bytes = f.read()

        # infer expectation from filename prefix
        expected = None
        if filename.lower().startswith('wish'):
            expected = False
        elif filename.lower().startswith('giveaway'):
            expected = True

        time.sleep(13)
        result = classify_message('', image_bytes)
        if result is None:
            print(f"[ERROR] API failed for {filename}\n")
            failed += 1
            continue

        actual = result.get('is_giveaway')
        ok = (expected is None) or (actual == expected)
        passed += ok
        failed += (not ok)

        status = "PASS" if ok else f"FAIL (expected {expected})"
        weight = result.get('estimated_weight_kg', 0)
        notify = is_worth_notifying(result)

        print(f"[{status}] {filename}")
        print(f"  item   : {result.get('item_description') or '—'}")
        print(f"  value  : CHF {result.get('estimated_value_chf', 0)}")
        print(f"  weight : ~{weight}kg")
        print(f"  postcode: {result.get('postcode') or '—'}")
        print(f"  conf   : {result.get('confidence')}  |  notify={notify}")
        print(f"  why    : {result.get('reason')}")
        print()

    return passed, failed


if __name__ == '__main__':
    print("=== Text tests ===\n")
    tp, tf = run_text_tests()

    print("\n=== Image tests ===\n")
    ip, if_ = run_image_tests()

    total_p = tp + ip
    total_f = tf + if_
    print(f"Total: {total_p}/{total_p + total_f} passed")
