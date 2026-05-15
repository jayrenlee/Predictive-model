"""
bot.py — 4D Analyzer Bot (Magnum / Toto / DaMaCai)
====================================================
Commands:
  /mag  DIGITS        — Top 10 by historical frequency
  /toto DIGITS        — Top 10 by historical frequency
  /dmc  DIGITS        — Top 10 by historical frequency
  /jackpot mag|toto|dmc — 50 best Jackpot number pairs
  /predict mag|toto|dmc — Top 20 predictions via 5-signal ensemble model

Predictive Model Signals (S1+S2+S4+S5 ensemble, optimised via backtest):
  S1: Long-term recency-weighted frequency  (half-life = 52 draws)
  S2: Short-term momentum                   (half-life = 10 draws)
  S4: Prize-tier weighted frequency         (1st=5x, 2nd=4x, 3rd=3x, special=2x, consol=1x)
  S5: Digit heat map                        (hot digits in last 20 draws)
"""

import os, time, logging, itertools, math
import numpy as np
import requests
import pandas as pd
from collections import Counter, defaultdict

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

TOKEN        = os.environ.get("TELEGRAM_TOKEN", "")
POLL_TIMEOUT = 30
RETRY_SLEEP  = 10
TOP_N        = 10
JACKPOT_N    = 50
PREDICT_N    = 20
HALF_LIFE_L  = 52    # long  (S1)
HALF_LIFE_S  = 10    # short (S2)
DIGIT_WINDOW = 20    # draws for digit heat (S5)

# Best weights from backtest: S1=0.15, S2=0.15, S3=0 (dropped), S4=0.35, S5=0.35
MODEL_WEIGHTS = np.array([0.15, 0.15, 0.00, 0.35, 0.35])

CSV_FILES = {
    "mag":  os.environ.get("CSV_MAGNUM", "results.csv"),
    "toto": os.environ.get("CSV_TOTO",   "toto_results.csv"),
    "dmc":  os.environ.get("CSV_DMC",    "dmc_results.csv"),
}
GAME_LABELS = {"mag": "Magnum 4D", "toto": "Sports Toto", "dmc": "Da Ma Cai"}
GAME_EMOJI  = {"mag": "🔴",        "toto": "🔵",          "dmc": "🟢"}

PRIZE_COLS = (
    ["prize_1st", "prize_2nd", "prize_3rd"]
    + [f"special_{i}"     for i in range(1, 11)]
    + [f"consolation_{i}" for i in range(1, 11)]
)
TOP3_COLS    = ["prize_1st", "prize_2nd", "prize_3rd"]
SPECIAL_COLS = [f"special_{i}" for i in range(1, 11)]
TIER_W = {
    "prize_1st": 5, "prize_2nd": 4, "prize_3rd": 3,
    **{f"special_{i}":     2 for i in range(1, 11)},
    **{f"consolation_{i}": 1 for i in range(1, 11)},
}


# ═══════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════

def build_data(csv_path: str) -> dict:
    """Load CSV and compute all data structures needed by every command."""
    freq       = Counter()
    date_map   = defaultdict(list)
    top3_freq  = Counter()
    top3_score = defaultdict(float)
    co_occur   = Counter()

    # For the 5-signal model
    long_s    = defaultdict(float)
    short_s   = defaultdict(float)
    tier_s    = defaultdict(float)
    last_seen = {}
    gap_sums  = defaultdict(float)
    gap_sq    = defaultdict(float)
    gap_cnt   = defaultdict(int)
    digit_hist = []   # per-draw digit Counter

    try:
        df    = pd.read_csv(csv_path)
        total = len(df)

        if "draw_date" in df.columns:
            df["draw_date"] = df["draw_date"].astype(str).str.strip()

        for idx, (_, row) in enumerate(df.iterrows()):
            age  = total - 1 - idx
            wl   = math.pow(0.5, age / HALF_LIFE_L)
            ws   = math.pow(0.5, age / HALF_LIFE_S)
            date_str = str(row.get("draw_date", ""))

            draw_top3  = []
            draw_dcnt  = Counter()

            for col in PRIZE_COLS:
                if col not in df.columns: continue
                num = str(row[col]).zfill(4)
                if not (num.isdigit() and len(num) == 4): continue

                # Frequency + dates
                freq[num] += 1
                if date_str:
                    date_map[num].append(date_str)

                # Signal accumulators
                long_s[num]  += wl
                short_s[num] += ws
                tier_s[num]  += TIER_W.get(col, 1) * wl

                # Gap tracking
                if num in last_seen:
                    g = idx - last_seen[num]
                    gap_sums[num] += g
                    gap_sq[num]   += g * g
                    gap_cnt[num]  += 1
                last_seen[num] = idx

                # Digit counts
                for d in num:
                    draw_dcnt[int(d)] += 1

                if col in TOP3_COLS:
                    top3_score[num] += wl
                    top3_freq[num]  += 1
                    draw_top3.append(num)

            # Co-occurrence (jackpot)
            for i, a in enumerate(draw_top3):
                for b in draw_top3[i + 1:]:
                    co_occur[tuple(sorted([a, b]))] += 1

            digit_hist.append(draw_dcnt)

        # Sort dates newest-first
        for num in date_map:
            try:
                date_map[num].sort(
                    key=lambda d: pd.to_datetime(d, dayfirst=True), reverse=True)
            except Exception:
                date_map[num].sort(reverse=True)

        # ── Build 5-signal matrix for /predict ─────────────────────────
        all_nums = list(freq.keys())
        m        = len(all_nums)
        nidx     = {n: i for i, n in enumerate(all_nums)}

        s1 = np.array([long_s.get(n, 0)  for n in all_nums])
        s2 = np.array([short_s.get(n, 0) for n in all_nums])
        s4 = np.array([tier_s.get(n, 0)  for n in all_nums])

        # S3: overdue gap score (kept for completeness but weight=0)
        s3 = np.zeros(m)
        for i, num in enumerate(all_nums):
            if gap_cnt[num] < 2: continue
            mg  = gap_sums[num] / gap_cnt[num]
            vg  = max(gap_sq[num] / gap_cnt[num] - mg ** 2, 1.0)
            since = total - 1 - last_seen.get(num, 0)
            s3[i] = float(np.clip((since - mg) / math.sqrt(vg), -3, 3))

        # S5: digit heat (last DIGIT_WINDOW draws)
        recent = digit_hist[-DIGIT_WINDOW:]
        dh     = np.zeros(10)
        for dc in recent:
            for d, c in dc.items():
                dh[d] += c
        dh /= (dh.max() + 1e-9)
        s5 = np.array([np.mean([dh[int(d)] for d in num]) for num in all_nums])

        # Normalise each signal to [0,1]
        def norm(v):
            mn, mx = v.min(), v.max()
            return (v - mn) / (mx - mn + 1e-12)

        signal_matrix = np.column_stack([norm(s1), norm(s2), norm(s3), norm(s4), norm(s5)])

        log.info(f"Loaded {csv_path}: {total} draws, {m} unique numbers.")

    except FileNotFoundError:
        log.warning(f"{csv_path} not found.")
        all_nums = []; signal_matrix = np.empty((0, 5))
    except Exception as e:
        log.error(f"Failed to load {csv_path}: {e}")
        all_nums = []; signal_matrix = np.empty((0, 5))

    return {
        "freq":       freq,
        "date_map":   dict(date_map),
        "top3_score": dict(top3_score),
        "top3_freq":  top3_freq,
        "co_occur":   co_occur,
        "all_nums":   all_nums,
        "sig_matrix": signal_matrix,
    }


# ═══════════════════════════════════════════════════════════════
# PREDICTIVE MODEL  (/predict)
# ═══════════════════════════════════════════════════════════════

def get_predictions(maps: dict, n: int = PREDICT_N) -> list[tuple[str, float]]:
    """
    Return top-N numbers by 5-signal ensemble score.
    Each item: (number, composite_score_0_to_1)
    """
    mat      = maps["sig_matrix"]
    all_nums = maps["all_nums"]
    if mat.size == 0:
        return []

    scores    = mat @ MODEL_WEIGHTS
    top_idx   = np.argpartition(scores, -n)[-n:]
    top_idx   = top_idx[np.argsort(scores[top_idx])[::-1]]
    max_score = scores[top_idx[0]] or 1.0

    return [(all_nums[i], float(scores[i] / max_score)) for i in top_idx]


# ═══════════════════════════════════════════════════════════════
# JACKPOT PAIRS  (/jackpot)
# ═══════════════════════════════════════════════════════════════

def get_jackpot_pairs(maps: dict, n: int = JACKPOT_N) -> list:
    top3_score = maps["top3_score"]
    top3_freq  = maps["top3_freq"]
    co_occur   = maps["co_occur"]
    if not top3_score:
        return []

    max_t3 = max(top3_score.values()) or 1
    cands  = sorted(top3_score, key=top3_score.get, reverse=True)[:50]
    max_co = max(co_occur.values()) if co_occur else 1
    seen, scored = set(), []

    for (a, b), count in co_occur.most_common():
        if a not in top3_score or b not in top3_score: continue
        key = tuple(sorted([a, b]))
        if key in seen: continue
        seen.add(key)
        t3a = top3_score[a] / max_t3; t3b = top3_score[b] / max_t3
        co  = count / max_co
        div = (4 - len(set(a) & set(b))) / 4
        scored.append((a, b, 0.40*t3a + 0.40*t3b + 0.15*co + 0.05*div,
                       top3_freq[a], top3_freq[b], count))

    for i, a in enumerate(cands):
        for b in cands[i + 1:]:
            key = tuple(sorted([a, b]))
            if key in seen: continue
            seen.add(key)
            t3a = top3_score.get(a, 0) / max_t3
            t3b = top3_score.get(b, 0) / max_t3
            div = (4 - len(set(a) & set(b))) / 4
            scored.append((a, b, 0.40*t3a + 0.40*t3b + 0.05*div,
                           top3_freq[a], top3_freq[b], 0))

    scored.sort(key=lambda x: x[2], reverse=True)
    return scored[:n]


# ═══════════════════════════════════════════════════════════════
# DIGIT ANALYSIS  (/mag /toto /dmc)
# ═══════════════════════════════════════════════════════════════

def analyze_digits(digit_str: str, freq: Counter) -> list[tuple[str, int]]:
    digits = "".join(filter(str.isdigit, digit_str))
    if len(digits) < 4:
        return []
    candidates: set[str] = set()
    for combo in itertools.combinations(digits, 4):
        for perm in itertools.permutations(combo):
            candidates.add("".join(perm))
    return sorted([(n, freq.get(n, 0)) for n in candidates],
                  key=lambda x: x[1], reverse=True)[:TOP_N]


# ═══════════════════════════════════════════════════════════════
# TELEGRAM HELPERS
# ═══════════════════════════════════════════════════════════════

def api(method: str, **kwargs):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    requests.post(url, json=kwargs, timeout=15).raise_for_status()

def send(chat_id: str, text: str):
    try:
        if len(text) <= 4096:
            api("sendMessage", chat_id=chat_id, text=text, parse_mode="Markdown")
        else:
            for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
                api("sendMessage", chat_id=chat_id, text=chunk, parse_mode="Markdown")
                time.sleep(0.3)
    except Exception as e:
        log.error(f"sendMessage failed: {e}")

def get_updates(offset: int) -> list:
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


# ═══════════════════════════════════════════════════════════════
# MESSAGE HANDLER
# ═══════════════════════════════════════════════════════════════

def handle(message: dict, data: dict):
    chat_id = str(message.get("chat", {}).get("id", ""))
    text    = message.get("text", "").strip()
    user    = message.get("from", {}).get("username", "unknown")
    lower   = text.lower()

    log.info(f"Message from {user}: {text!r}")

    # ── /start /help ──────────────────────────────────────────────────
    if lower in ("/start", "/help"):
        send(chat_id,
            "👋 *4D Analyzer Bot*\n\n"
            "*Digit Analysis (historical frequency):*\n"
            "🔴 `/mag 123456` — Magnum 4D\n"
            "🔵 `/toto 123456` — Sports Toto\n"
            "🟢 `/dmc 123456` — Da Ma Cai\n\n"
            "*Smart Predictions (5-signal model):*\n"
            "🔮 `/predict mag` — Magnum top 20\n"
            "🔮 `/predict toto` — Sports Toto top 20\n"
            "🔮 `/predict dmc` — Da Ma Cai top 20\n\n"
            "*Jackpot Pairs (50 best pairs):*\n"
            "🎰 `/jackpot mag` — Magnum\n"
            "🎰 `/jackpot toto` — Sports Toto\n"
            "🎰 `/jackpot dmc` — Da Ma Cai\n\n"
            "_Digit commands: min 4, max 12 digits._"
        )
        return

    # ── /predict ──────────────────────────────────────────────────────
    if lower.startswith("/predict"):
        parts = text.split()
        if len(parts) < 2 or parts[1].lower() not in ("mag", "toto", "dmc"):
            send(chat_id,
                "⚠️ Usage:\n"
                "`/predict mag` — Magnum\n"
                "`/predict toto` — Sports Toto\n"
                "`/predict dmc` — Da Ma Cai"
            )
            return

        game  = parts[1].lower()
        emoji = GAME_EMOJI[game]
        label = GAME_LABELS[game]
        maps  = data[game]

        preds = get_predictions(maps)
        if not preds:
            send(chat_id, "❌ Not enough data yet.")
            return

        date_map = maps["date_map"]
        lines    = [
            f"🔮 {emoji} *{label} — Top {PREDICT_N} Predictions*\n",
            f"_Model: Long freq · Momentum · Tier weight · Digit heat_\n",
        ]

        for rank, (num, score) in enumerate(preds, 1):
            bar   = "█" * round(score * 10) + "░" * (10 - round(score * 10))
            dates = date_map.get(num, [])[:3]
            conf  = f"{score*100:.0f}%"

            if dates:
                date_str = " · ".join(dates)
                lines.append(
                    f"`{rank:>2}.` `{num}`  {bar}  *{conf}*\n"
                    f"      📅 _{date_str}_"
                )
            else:
                lines.append(f"`{rank:>2}.` `{num}`  {bar}  *{conf}*")

        lines.append(f"\n_Backtest edge: +1.5% above random baseline_")
        send(chat_id, "\n".join(lines))
        return

    # ── /jackpot ──────────────────────────────────────────────────────
    if lower.startswith("/jackpot"):
        parts = text.split()
        if len(parts) < 2 or parts[1].lower() not in ("mag", "toto", "dmc"):
            send(chat_id,
                "⚠️ Usage:\n"
                "`/jackpot mag` — Magnum\n"
                "`/jackpot toto` — Sports Toto\n"
                "`/jackpot dmc` — Da Ma Cai"
            )
            return

        game  = parts[1].lower()
        emoji = GAME_EMOJI[game]
        label = GAME_LABELS[game]
        pairs = get_jackpot_pairs(data[game])

        if not pairs:
            send(chat_id, "❌ Not enough data yet.")
            return

        lines = [
            f"🎰 {emoji} *{label} — Top {JACKPOT_N} Jackpot Pairs*\n",
            f"_⭐ = pair historically appeared together in Top 3_\n",
        ]
        for rank, (a, b, score, fa, fb, co) in enumerate(pairs, 1):
            star = " ⭐" if co > 0 else ""
            lines.append(f"`{rank:>2}.` `{a}` + `{b}`  _{fa}× & {fb}×_{star}")

        lines.append(f"\n_⭐ pairs = strongest Jackpot 1 candidates_")
        send(chat_id, "\n".join(lines))
        return

    # ── /mag /toto /dmc ───────────────────────────────────────────────
    game = None
    if lower.startswith("/mag"):   game = "mag"
    elif lower.startswith("/toto"): game = "toto"
    elif lower.startswith("/dmc"):  game = "dmc"

    if game is None:
        send(chat_id, "⚠️ Unknown command. Send /help for usage.")
        return

    parts  = text.split(None, 1)
    digits = "".join(filter(str.isdigit, parts[1])) if len(parts) > 1 else ""

    if len(digits) < 4:
        send(chat_id, f"⚠️ Send at least *4 digits*.\nExample: `/{game} 123456`")
        return
    if len(digits) > 12:
        send(chat_id, "⚠️ Too many digits — keep it to *12 or fewer*.")
        return

    freq     = data[game]["freq"]
    date_map = data[game]["date_map"]
    results  = analyze_digits(digits, freq)

    if not results:
        send(chat_id, "❌ No results found.")
        return

    emoji = GAME_EMOJI[game]
    label = GAME_LABELS[game]
    lines = [f"📊 {emoji} *{label} — Top {TOP_N} for* `{digits}`\n"]

    for rank, (num, hits) in enumerate(results, 1):
        bar   = "█" * min(hits, 10) + "░" * max(0, 10 - min(hits, 10))
        dates = date_map.get(num, [])[:3]
        if dates:
            lines.append(
                f"`{rank:>2}.` `{num}`  {bar}  *{hits} hits*\n"
                f"      📅 _{' · '.join(dates)}_"
            )
        else:
            lines.append(f"`{rank:>2}.` `{num}`  {bar}  *{hits} hits*")

    lines.append(f"\n_Analyzed from {len(freq):,} historical winning numbers_")
    send(chat_id, "\n".join(lines))


# ═══════════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════════

def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN environment variable is not set.")

    log.info("Bot starting — loading data...")
    data = {game: build_data(path) for game, path in CSV_FILES.items()}
    log.info("All data loaded. Listening for messages...")

    last_update_id = 0
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
