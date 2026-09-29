"""
Test the classifier against the real Telegram export.

Usage:
  python test_export.py                      # 20 random posts (default)
  python test_export.py --limit 50           # 50 random posts
  python test_export.py --limit 30 --seed 42 # reproducible random sample
  python test_export.py --limit 0            # all posts (slow, uses quota)
  python test_export.py --skip 30            # sequential mode: skip first N

Results are saved to export_results.jsonl so you can review them.
"""

import sys
import io
import os
import re
import json
import time
import random
import argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from bs4 import BeautifulSoup
from classifier import classify_message, is_worth_notifying
from prefilter import is_likely_wish

EXPORT_DIR = os.path.join(os.path.dirname(__file__), 'ChatExport_2026-05-02')
HTML_FILES = [
    'messages.html', 'messages2.html', 'messages3.html',
    'messages4.html', 'messages5.html', 'messages6.html',
]
RATE_DELAY = 13  # seconds between API calls (free tier: 5 RPM)


def parse_posts(limit: int, skip: int) -> list[dict]:
    """
    Parse HTML files and group consecutive messages from the same sender
    into logical posts. Each post has text and a list of image paths.
    """
    posts = []
    current_post = None

    for filename in HTML_FILES:
        path = os.path.join(EXPORT_DIR, filename)
        if not os.path.exists(path):
            print(f"[parser] missing {filename}, skipping")
            continue

        with open(path, encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')

        for div in soup.select('div.message'):
            is_joined = 'joined' in div.get('class', [])
            msg_id = div.get('id', '')

            # extract text
            text_div = div.select_one('div.text')
            text = text_div.get_text(separator=' ', strip=True) if text_div else ''

            # extract image paths
            images = []
            for a in div.select('a.photo_wrap'):
                href = a.get('href', '')
                if href:
                    full_path = os.path.join(EXPORT_DIR, href)
                    if os.path.exists(full_path):
                        images.append(full_path)

            # extract sender
            sender_div = div.select_one('div.from_name')
            sender = sender_div.get_text(strip=True) if sender_div else ''

            # extract timestamp
            date_div = div.select_one('div.date')
            timestamp = date_div.get('title', '') if date_div else ''

            if is_joined and current_post:
                # append to existing post
                if text:
                    current_post['text'] = (current_post['text'] + ' ' + text).strip()
                current_post['images'].extend(images)
            else:
                # save previous post
                if current_post and (current_post['text'] or current_post['images']):
                    posts.append(current_post)
                current_post = {
                    'id': msg_id,
                    'sender': sender,
                    'timestamp': timestamp,
                    'text': text,
                    'images': images,
                }

        if limit and len(posts) >= limit + skip:
            break

    if current_post and (current_post['text'] or current_post['images']):
        posts.append(current_post)

    posts = posts[skip:]
    if limit:
        posts = posts[:limit]
    return posts


def run(limit: int, skip: int, seed: int | None):
    random_mode = seed is not None or (skip == 0 and limit > 0)
    if random_mode:
        print(f"Parsing all posts for random sampling (limit={limit}, seed={seed}) ...")
        all_posts = parse_posts(limit=0, skip=0)
        rng = random.Random(seed)
        posts = rng.sample(all_posts, min(limit, len(all_posts)))
        print(f"Sampled {len(posts)} posts from {len(all_posts)} total\n")
    else:
        print(f"Parsing export sequentially (skip={skip}, limit={limit or 'all'}) ...")
        posts = parse_posts(limit, skip)
    if not random_mode:
        print(f"Found {len(posts)} posts to classify\n")

    results_path = os.path.join(os.path.dirname(__file__), 'export_results.jsonl')
    notify_count = skip_count = error_count = 0

    with open(results_path, 'a', encoding='utf-8') as out:
        for i, post in enumerate(posts):
            text = post['text']
            images = post['images']

            # load first image if present
            image_bytes = None
            if images:
                try:
                    with open(images[0], 'rb') as f:
                        image_bytes = f.read()
                except Exception as e:
                    print(f"[{i+1}] image load failed: {e}")

            if not text and not image_bytes:
                continue

            if is_likely_wish(text) and not image_bytes:
                skip_count += 1
                print(f"[pre-filter] {i+1}/{len(posts)} wish skipped | {text[:60]!r}")
                continue

            time.sleep(RATE_DELAY)
            result = classify_message(text, image_bytes)

            if result is None:
                error_count += 1
                print(f"[{i+1}/{len(posts)}] ERROR  | {post['sender']} | {text[:60]!r}")
                continue

            notify = is_worth_notifying(result)
            if notify:
                notify_count += 1
            else:
                skip_count += 1

            # build skip reason
            skip_reason = ''
            if not result.get('is_giveaway'):
                skip_reason = 'not a giveaway'
            elif result.get('is_large_furniture'):
                skip_reason = 'large furniture'
            elif result.get('estimated_value_chf', 0) < 20:
                skip_reason = f"low value (CHF {result.get('estimated_value_chf')})"
            elif result.get('estimated_value_chf', 0) < 150 and result.get('estimated_weight_kg', 0) > 15:
                skip_reason = f"too heavy ({result.get('estimated_weight_kg')}kg)"

            icon = '[NOTIFY]' if notify else '[skip  ]'
            print(
                f"{icon} {i+1}/{len(posts)} | "
                f"{result.get('item_description') or '—'} | "
                f"CHF {result.get('estimated_value_chf')} | "
                f"{result.get('estimated_weight_kg')}kg | "
                f"postcode={result.get('postcode') or '—'} | "
                f"{skip_reason or 'ok'}"
            )
            if result.get('is_giveaway') and not result.get('item_description'):
                print(f"         text: {text[:80]!r}")

            record = {**post, 'images': [os.path.basename(p) for p in post['images']], 'classification': result, 'notify': notify}
            out.write(json.dumps(record, ensure_ascii=False) + '\n')

    print(f"\nDone. notify={notify_count}  skipped={skip_count}  errors={error_count}")
    print(f"Results saved to export_results.jsonl")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--skip', type=int, default=0)
    parser.add_argument('--seed', type=int, default=None)
    args = parser.parse_args()
    run(args.limit, args.skip, args.seed)
