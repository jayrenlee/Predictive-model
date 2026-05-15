"""
bot.py — Magnum 4D Analyzer Bot
================================
Receives a string of digits via Telegram, generates all 4-digit
permutations, ranks them by historical frequency, and returns the top 10.

Deploy as a Render.com Background Worker.
"""

import os
import time
import logging
import itertools
import requests
import pandas as pd
from collections import Counter

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
CSV     = os.environ.get("CSV_PATH", "results.csv")

TOP_N   = 10        # numbers to return
POLL_TIMEOUT = 30   # seconds for long-poll
RETRY_SLEEP  = 10   # seconds before retrying after error

PRIZE_COLS = (
    ["prize_1st", "prize_2nd", "prize_3rd"]
    + [f"special_{i}"     for i in range(1, 11)]
    + [f"consolation_{i}" for i in range(1, 11)]
)

# ── Build frequency map from results.csv ──────────────────────────────────────
def build_freq_map(csv_path: str) -> Counter:
    try:
        df = pd.read_csv(csv_path)
        numbers = []
        for col in PRIZE_COLS:
            if col in df.columns:
                numbers.extend(
                    df[col].astype(str).str.zfill(4).tolist()
                )
        freq = Counter(numbers)
        log.info(f"Loaded {csv_path}: {len(df)} draws, {len(freq)} unique numbers.")
        return freq
    except Exception as e:
        log.error(f"Failed to load {csv_path}: {e}")
        return Counter()


# ── Analysis logic ────────────────────────────────────────────────────────────
def analyze(digit_string: str, freq: Counter, top_n: int = TOP_N) -> list[tuple[str, int]]:
    """
    Given a string of digits, generate all unique 4-digit permutations
    from all 4-digit combinations, rank by historical frequency,
    return the top_n results as (number, hit_count) tuples.
    """
    digits = "".join(filter(str.isdigit, digit_string))

    if len(digits) < 4:
        return []

    candidates: set[str] = set()
    for combo in itertools.combinations(digits, 4):
        for perm in itertools.permutations(combo):
            candidates.add("".join(perm))

    ranked = sorted(
        [(num, freq.get(num, 0)) for num in candidates],
        key=lambda x: x[1],
        reverse=True,
    )
    return ranked[:top_n]


# ── Telegram helpers ──────────────────────────────────────────────────────────
def api(method: str, **kwargs) -> dict:
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    resp = requests.post(url, json=kwargs, timeout=15)
    resp.raise_for_status()
    return resp.json()


def send(chat_id: str, text: str):
    try:
        api("sendMessage", chat_id=chat_id, text=text, parse_mode="Markdown")
    except Exception as e:
        log.error(f"sendMessage failed: {e}")


def get_updates(offset: int) -> list[dict]:
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
        resp = requests.get(
            url,
            params={"offset": offset, "timeout": POLL_TIMEOUT},
            timeout=POLL_TIMEOUT + 5,
        )
        resp.raise_for_status()
        return resp.json().get("result", [])
    except Exception as e:
        log.warning(f"getUpdates error: {e}")
        return []


# ── Message handler ───────────────────────────────────────────────────────────
def handle(message: dict, freq: Counter):
    chat_id = str(message.get("chat", {}).get("id", ""))
    text    = message.get("text", "").strip()
    user    = message.get("from", {}).get("username", "unknown")

    # Optional: restrict to your own chat only
  
    log.info(f"Message from {user}: {text!r}")

    # ── /start or /help
    if text.lower() in ("/start", "/help"):
        send(chat_id,
            "👋 *Magnum 4D Analyzer*\n\n"
            "Send me any string of digits (at least 4) and I'll find the "
            "top 10 most historically frequent 4D numbers that can be formed "
            "from those digits.\n\n"
            "*Example:* `12345` or `019 23` or `56789012`"
        )
        return

    # ── digit input
    digits = "".join(filter(str.isdigit, text))

    if len(digits) < 4:
        send(chat_id,
            "⚠️ Please send at least *4 digits*.\n"
            "Example: `12345` or `0192 3456`"
        )
        return

    if len(digits) > 12:
        send(chat_id,
            "⚠️ Too many digits — please keep it to *12 or fewer* "
            "to avoid extremely large permutation sets."
        )
        return

    results = analyze(digits, freq)

    if not results:
        send(chat_id, "❌ No results found. Please try a different set of digits.")
        return

    lines = [f"📊 *Top {TOP_N} for digits `{digits}`*\n"]
    for rank, (num, hits) in enumerate(results, 1):
        bar  = "█" * min(hits, 10) + "░" * max(0, 10 - min(hits, 10))
        line = f"`{rank:>2}.` `{num}`  {bar}  {hits} hits"
        lines.append(line)

    lines.append(f"\n_Analyzed from {len(freq):,} historical winning numbers_")
    send(chat_id, "\n".join(lines))


# ── Main loop ─────────────────────────────────────────────────────────────────
def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN environment variable is not set.")

    log.info("Bot starting...")
    freq = build_freq_map(CSV)

    if not freq:
        log.warning("Frequency map is empty — check results.csv path.")

    last_update_id = 0

    log.info("Listening for messages...")
    while True:
        try:
            updates = get_updates(last_update_id + 1)
            for update in updates:
                last_update_id = update["update_id"]
                if "message" in update:
                    handle(update["message"], freq)

        except KeyboardInterrupt:
            log.info("Stopped by user.")
            break
        except Exception as e:
            log.error(f"Unexpected error: {e}")
            time.sleep(RETRY_SLEEP)


if __name__ == "__main__":
    main()
