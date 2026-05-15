"""
bot.py — Magnum / Toto / DaMaCai 4D Analyzer Bot
===================================================
Commands:
  /mag  DIGITS  — analyze against Magnum 4D history
  /toto DIGITS  — analyze against Sports Toto history
  /dmc  DIGITS  — analyze against Da Ma Cai history

Deploy as a Railway Background Worker.
"""

import os
import time
import logging
import itertools
import requests
import pandas as pd
from collections import Counter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

TOKEN        = os.environ.get("TELEGRAM_TOKEN", "")
POLL_TIMEOUT = 30
RETRY_SLEEP  = 10
TOP_N        = 10

CSV_FILES = {
    "mag":  os.environ.get("CSV_MAGNUM", "results.csv"),
    "toto": os.environ.get("CSV_TOTO",   "toto_results.csv"),
    "dmc":  os.environ.get("CSV_DMC",    "dmc_results.csv"),
}

GAME_LABELS = {
    "mag":  "Magnum 4D",
    "toto": "Sports Toto",
    "dmc":  "Da Ma Cai",
}

GAME_EMOJI = {
    "mag":  "🔴",
    "toto": "🔵",
    "dmc":  "🟢",
}

PRIZE_COLS = (
    ["prize_1st", "prize_2nd", "prize_3rd"]
    + [f"special_{i}"     for i in range(1, 11)]
    + [f"consolation_{i}" for i in range(1, 11)]
)


def build_freq_map(csv_path: str) -> Counter:
    try:
        df = pd.read_csv(csv_path)
        numbers = []
        for col in PRIZE_COLS:
            if col in df.columns:
                numbers.extend(df[col].astype(str).str.zfill(4).tolist())
        freq = Counter(numbers)
        log.info(f"Loaded {csv_path}: {len(df)} draws, {len(freq)} unique numbers.")
        return freq
    except FileNotFoundError:
        log.warning(f"{csv_path} not found — will be empty until first scrape.")
        return Counter()
    except Exception as e:
        log.error(f"Failed to load {csv_path}: {e}")
        return Counter()


def analyze(digit_string: str, freq: Counter) -> list[tuple[str, int]]:
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
    return ranked[:TOP_N]


def api(method: str, **kwargs):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    requests.post(url, json=kwargs, timeout=15).raise_for_status()


def send(chat_id: str, text: str):
    try:
        api("sendMessage", chat_id=chat_id, text=text, parse_mode="Markdown")
    except Exception as e:
        log.error(f"sendMessage failed: {e}")


def get_updates(offset: int) -> list[dict]:
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{TOKEN}/getUpdates",
            params={"offset": offset, "timeout": POLL_TIMEOUT},
            timeout=POLL_TIMEOUT + 5,
        )
        resp.raise_for_status()
        return resp.json().get("result", [])
    except Exception as e:
        log.warning(f"getUpdates error: {e}")
        return []


def handle(message: dict, freq_maps: dict):
    chat_id = str(message.get("chat", {}).get("id", ""))
    text    = message.get("text", "").strip()
    user    = message.get("from", {}).get("username", "unknown")
    lower   = text.lower()

    log.info(f"Message from {user}: {text!r}")

    if lower in ("/start", "/help"):
        send(chat_id,
            "👋 *4D Analyzer Bot*\n\n"
            "Choose your game and send your digits:\n\n"
            "🔴 `/mag 123456` — Magnum 4D\n"
            "🔵 `/toto 123456` — Sports Toto\n"
            "🟢 `/dmc 123456` — Da Ma Cai\n\n"
            "_Minimum 4 digits, maximum 12 digits._\n"
            "_I'll return the Top 10 numbers by historical frequency._"
        )
        return

    # detect game
    game = None
    if lower.startswith("/mag"):
        game = "mag"
    elif lower.startswith("/toto"):
        game = "toto"
    elif lower.startswith("/dmc"):
        game = "dmc"

    if game is None:
        send(chat_id,
            "⚠️ Unknown command. Use:\n"
            "`/mag DIGITS` — Magnum 4D\n"
            "`/toto DIGITS` — Sports Toto\n"
            "`/dmc DIGITS` — Da Ma Cai"
        )
        return

    parts  = text.split(None, 1)
    digits = "".join(filter(str.isdigit, parts[1])) if len(parts) > 1 else ""

    if len(digits) < 4:
        send(chat_id, f"⚠️ Send at least *4 digits* after the command.\nExample: `/{game} 123456`")
        return

    if len(digits) > 12:
        send(chat_id, "⚠️ Too many digits — keep it to *12 or fewer*.")
        return

    freq    = freq_maps[game]
    results = analyze(digits, freq)

    if not results:
        send(chat_id, "❌ No results found. Try a different set of digits.")
        return

    emoji = GAME_EMOJI[game]
    label = GAME_LABELS[game]
    lines = [f"📊 {emoji} *{label} — Top {TOP_N} for* `{digits}`\n"]

    for rank, (num, hits) in enumerate(results, 1):
        bar = "█" * min(hits, 10) + "░" * max(0, 10 - min(hits, 10))
        lines.append(f"`{rank:>2}.` `{num}`  {bar}  {hits} hits")

    lines.append(f"\n_Analyzed from {len(freq):,} historical winning numbers_")
    send(chat_id, "\n".join(lines))


def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN environment variable is not set.")

    log.info("Bot starting...")
    freq_maps = {game: build_freq_map(path) for game, path in CSV_FILES.items()}

    last_update_id = 0
    log.info("Listening for messages...")

    while True:
        try:
            updates = get_updates(last_update_id + 1)
            for update in updates:
                last_update_id = update["update_id"]
                if "message" in update:
                    handle(update["message"], freq_maps)
        except KeyboardInterrupt:
            log.info("Stopped.")
            break
        except Exception as e:
            log.error(f"Unexpected error: {e}")
            time.sleep(RETRY_SLEEP)


if __name__ == "__main__":
    main()
