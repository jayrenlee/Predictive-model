"""
bot.py — Magnum / Toto / DaMaCai 4D Analyzer Bot
===================================================
Commands:
  /mag  DIGITS  — analyze against Magnum 4D history
  /toto DIGITS  — analyze against Sports Toto history
  /dmc  DIGITS  — analyze against Da Ma Cai history

Shows top 10 numbers with hit count + last 3 winning dates.
"""

import os
import time
import logging
import itertools
import requests
import pandas as pd
from collections import Counter, defaultdict

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

TOKEN        = os.environ.get("TELEGRAM_TOKEN", "")
POLL_TIMEOUT = 30
RETRY_SLEEP  = 10
TOP_N        = 10
MAX_DATES    = 2   # how many recent winning dates to show

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


def build_maps(csv_path: str) -> tuple[Counter, dict]:
    """
    Returns:
      freq     — Counter: number → total hit count
      date_map — dict:    number → sorted list of winning dates (newest first)
    """
    freq     = Counter()
    date_map = defaultdict(list)

    try:
        df = pd.read_csv(csv_path)

        # Normalise draw_date to DD/MM/YYYY string
        if "draw_date" in df.columns:
            df["draw_date"] = df["draw_date"].astype(str).str.strip()

        for _, row in df.iterrows():
            date_str = row.get("draw_date", "")
            for col in PRIZE_COLS:
                if col in df.columns:
                    num = str(row[col]).zfill(4)
                    if num.isdigit() and len(num) == 4:
                        freq[num] += 1
                        if date_str:
                            date_map[num].append(date_str)

        # Sort each number's dates newest-first
        for num in date_map:
            try:
                date_map[num].sort(
                    key=lambda d: pd.to_datetime(d, dayfirst=True),
                    reverse=True
                )
            except Exception:
                date_map[num].sort(reverse=True)

        log.info(f"Loaded {csv_path}: {len(df)} draws, {len(freq)} unique numbers.")
    except FileNotFoundError:
        log.warning(f"{csv_path} not found — will be empty until first scrape.")
    except Exception as e:
        log.error(f"Failed to load {csv_path}: {e}")

    return freq, dict(date_map)


def analyze(digits: str, freq: Counter) -> list[tuple[str, int]]:
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


def handle(message: dict, data: dict):
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
            "_Returns Top 10 numbers with hit count and winning dates._"
        )
        return

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

    freq     = data[game]["freq"]
    date_map = data[game]["date_map"]
    results  = analyze(digits, freq)

    if not results:
        send(chat_id, "❌ No results found. Try a different set of digits.")
        return

    emoji = GAME_EMOJI[game]
    label = GAME_LABELS[game]
    lines = [f"📊 {emoji} *{label} — Top {TOP_N} for* `{digits}`\n"]

    for rank, (num, hits) in enumerate(results, 1):
        bar   = "█" * min(hits, 10) + "░" * max(0, 10 - min(hits, 10))
        dates = date_map.get(num, [])[:MAX_DATES]

        if dates:
            date_str = " · ".join(dates)
            lines.append(f"`{rank:>2}.` `{num}`  {bar}  *{hits} hits*\n      📅 _{date_str}_")
        else:
            lines.append(f"`{rank:>2}.` `{num}`  {bar}  *{hits} hits*")

    lines.append(f"\n_Analyzed from {len(freq):,} historical winning numbers_")
    send(chat_id, "\n".join(lines))


def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN environment variable is not set.")

    log.info("Bot starting...")

    # Load freq + date maps for all three games
    data = {}
    for game, path in CSV_FILES.items():
        freq, date_map = build_maps(path)
        data[game] = {"freq": freq, "date_map": date_map}

    last_update_id = 0
    log.info("Listening for messages...")

    while True:
        try:
            updates = get_updates(last_update_id + 1)
            for update in updates:
                last_update_id = update["update_id"]
                if "message" in update:
                    handle(update["message"], data)
        except KeyboardInterrupt:
            log.info("Stopped.")
            break
        except Exception as e:
            log.error(f"Unexpected error: {e}")
            time.sleep(RETRY_SLEEP)


if __name__ == "__main__":
    main()
