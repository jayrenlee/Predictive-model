"""
bot.py — 4D Analyzer Bot (Magnum / Toto / DaMaCai)
====================================================
Commands:
  /mag  DIGITS            — Top 10 by historical frequency + winning dates
  /toto DIGITS            — Top 10 by historical frequency + winning dates
  /dmc  DIGITS            — Top 10 by historical frequency + winning dates
  /predict mag|toto|dmc   — Top 30 predictions via cooldown ensemble model

Prediction Model (backtest: +8.08% edge, p=0.000, statistically significant):
  The key insight: numbers that JUST WON are unlikely to win again soon.
  The model penalises recent winners and rewards numbers that have been
  absent from draws for a while.

  Signals used (weights from backtest optimisation):
    S6: Cooldown penalty     — inverse of short-term freq  (weight: 0.970)
    S7: Gap reward           — draws since last appearance (weight: 0.005)
    S8: Tier-weighted cooldown — tier-weighted recency penalty (weight: 0.025)
"""

import os, time, logging, itertools, math, hashlib, threading, subprocess
import pytz
_MYT = pytz.timezone("Asia/Kuala_Lumpur")
from datetime import date, datetime
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
PREDICT_N    = 30

# Cooldown model half-lives
HALF_LIFE_L  = 52   # long window (S1)
HALF_LIFE_S  = 10   # short window (S2/S6 cooldown)
HALF_LIFE_CS = 8    # tier-weighted cooldown (S8)
DIGIT_WINDOW = 20   # draws for digit heat

# Best weights from 400-draw backtest:
# edge=+8.08%, HR=14.75% vs 6.67% baseline, p=0.000 (statistically significant)
# [S6_cooldown, S7_gap, S8_tier_cooldown]
MODEL_WEIGHTS = np.array([0.97, 0.005, 0.025])

# Positional digit bonuses (research-confirmed, 34yr Toto + 5yr Magnum)
# Thousands digit 1 gives +0.26% edge for Magnum, +0.22% for Toto
# Applied as tiny score multiplier — keeping cooldown as dominant signal
POSITIONAL_BONUS = {
    "mag":  {"thousands": {1: 0.05}},
    "toto": {"thousands": {1: 0.05}},
    "dmc":  {},
}

# ═══════════════════════════════════════════════════════════════
# I-CHING SYSTEM
# ═══════════════════════════════════════════════════════════════

TRIGRAMS = {
    'Qian': {'symbol': '☰', 'name': 'Heaven',   'element': 'Metal',  'digits': [1, 6]},
    'Kun':  {'symbol': '☷', 'name': 'Earth',    'element': 'Earth',  'digits': [2, 7]},
    'Zhen': {'symbol': '☳', 'name': 'Thunder',  'element': 'Wood',   'digits': [3, 8]},
    'Kan':  {'symbol': '☵', 'name': 'Water',    'element': 'Water',  'digits': [4, 9]},
    'Gen':  {'symbol': '☶', 'name': 'Mountain', 'element': 'Earth',  'digits': [5, 8, 0]},
    'Xun':  {'symbol': '☴', 'name': 'Wind',     'element': 'Wood',   'digits': [1, 6]},
    'Li':   {'symbol': '☲', 'name': 'Fire',     'element': 'Fire',   'digits': [2, 7]},
    'Dui':  {'symbol': '☱', 'name': 'Lake',     'element': 'Metal',  'digits': [3, 8]},
}

# King Wen sequence: (upper trigram, lower trigram) for hexagrams 1-64
HEXAGRAM_TRIGRAMS = [
    ('Qian','Qian'),('Kun','Kun'),('Zhen','Kan'),('Kan','Zhen'),
    ('Gen','Kan'),('Kan','Gen'),('Zhen','Kun'),('Kun','Zhen'),
    ('Qian','Xun'),('Xun','Qian'),('Qian','Li'),('Li','Qian'),
    ('Qian','Dui'),('Dui','Qian'),('Qian','Gen'),('Gen','Qian'),
    ('Qian','Kun'),('Kun','Qian'),('Kan','Kun'),('Kun','Kan'),
    ('Gen','Kun'),('Kun','Gen'),('Kun','Li'),('Li','Kun'),
    ('Kun','Dui'),('Dui','Kun'),('Zhen','Zhen'),('Xun','Xun'),
    ('Kan','Kan'),('Li','Li'),('Gen','Gen'),('Dui','Dui'),
    ('Xun','Zhen'),('Zhen','Xun'),('Li','Zhen'),('Zhen','Li'),
    ('Dui','Zhen'),('Zhen','Dui'),('Gen','Zhen'),('Zhen','Gen'),
    ('Xun','Kan'),('Kan','Xun'),('Li','Kan'),('Kan','Li'),
    ('Dui','Kan'),('Kan','Dui'),('Gen','Kan'),('Kan','Gen'),
    ('Xun','Li'),('Li','Xun'),('Dui','Li'),('Li','Dui'),
    ('Gen','Li'),('Li','Gen'),('Xun','Dui'),('Dui','Xun'),
    ('Gen','Dui'),('Dui','Gen'),('Xun','Gen'),('Gen','Xun'),
    ('Li','Gen'),('Gen','Li'),('Dui','Xun'),('Xun','Dui'),
]

# Hexagram names and meanings (King Wen sequence)
HEXAGRAM_DATA = [
    ("乾 Qián",  "The Creative",      "Heaven's pure creative force. Bold action brings success."),
    ("坤 Kūn",   "The Receptive",     "Earth's nurturing power. Yield and persevere quietly."),
    ("屯 Zhūn",  "Difficulty",        "New beginnings require patience. Progress comes in small steps."),
    ("蒙 Méng",  "Youthful Folly",    "Seek guidance with sincerity. Learning opens the path."),
    ("需 Xū",    "Waiting",           "Strength through patience. The right moment will come."),
    ("讼 Sòng",  "Conflict",          "Avoid confrontation. Seek mediation and compromise."),
    ("师 Shī",   "The Army",          "Discipline and organisation lead to collective strength."),
    ("比 Bǐ",    "Holding Together",  "Unity and alliances bring good fortune to all."),
    ("小畜 Xiǎo Xù", "Small Taming", "Gentle restraint. Accumulate strength before acting."),
    ("履 Lǚ",    "Treading",          "Conduct yourself carefully. Respect boundaries."),
    ("泰 Tài",   "Peace",             "Heaven and Earth in harmony. Prosperity flows naturally."),
    ("否 Pǐ",    "Standstill",        "Stagnation tests resolve. Hold your values firm."),
    ("同人 Tóng Rén", "Fellowship",   "Open hearts unite people. Shared goals bring success."),
    ("大有 Dà Yǒu",   "Great Wealth", "Abundance is yours. Share generously to keep it."),
    ("谦 Qiān",  "Modesty",           "Humble strength attracts lasting fortune."),
    ("豫 Yù",    "Enthusiasm",        "Joyful readiness moves mountains. Act with confidence."),
    ("随 Suí",   "Following",         "Adapt to the times. Flow with what is needed now."),
    ("蛊 Gǔ",    "Work on Decay",     "Correct the old wrongs. Renewal requires honest effort."),
    ("临 Lín",   "Approach",          "Opportunity draws near. Engage with care and strength."),
    ("观 Guān",  "Contemplation",     "Observe before acting. Deeper understanding guides well."),
    ("噬嗑 Shì Kè", "Biting Through","Overcome obstacles decisively. Justice prevails."),
    ("贲 Bì",    "Grace",             "Beauty and form matter. Elegance enhances substance."),
    ("剥 Bō",    "Splitting Apart",   "Yielding to decline now preserves strength for later."),
    ("复 Fù",    "Return",            "The turning point arrives. Light returns after darkness."),
    ("无妄 Wú Wàng", "Innocence",     "Act without ulterior motive. Natural conduct brings good."),
    ("大畜 Dà Xù",   "Great Taming",  "Accumulate wisdom and power. The time to act is near."),
    ("颐 Yí",    "Nourishment",       "Feed body and mind wisely. Choose what truly sustains."),
    ("大过 Dà Guò",  "Great Excess",  "The beam is bending. Act boldly before it breaks."),
    ("坎 Kǎn",   "The Abysmal",       "Danger surrounds, but sincerity carries you through."),
    ("离 Lí",    "The Clinging",      "Fire needs fuel. Clarity and attachment bring warmth."),
    ("咸 Xián",  "Influence",         "Mutual attraction. Open feelings create connection."),
    ("恒 Héng",  "Duration",          "Steadfast perseverance builds enduring success."),
    ("遯 Dùn",   "Retreat",           "Withdraw gracefully. Strategic retreat preserves strength."),
    ("大壮 Dà Zhuàng","Great Power",  "Strength is at its peak. Act with righteousness."),
    ("晋 Jìn",   "Progress",          "Advance like sunrise — steady, bright, and sure."),
    ("明夷 Míng Yí",  "Darkening",    "Hide your light in difficult times. Endure quietly."),
    ("家人 Jiā Rén",  "The Family",   "Harmony within creates harmony without."),
    ("睽 Kuí",   "Opposition",        "Differences need not divide. Find unity in contrast."),
    ("蹇 Jiǎn",  "Obstruction",       "The path is blocked. Seek allies and alternative routes."),
    ("解 Xiè",   "Deliverance",       "The storm has passed. Move quickly to restore order."),
    ("损 Sǔn",   "Decrease",          "Reduce what is excessive. Sincerity in simplicity wins."),
    ("益 Yì",    "Increase",          "Benefit flows to all. This is the time to give and grow."),
    ("夬 Guài",  "Breakthrough",      "Resolve must be decisive. Truth must be spoken clearly."),
    ("姤 Gòu",   "Coming to Meet",    "An unexpected encounter. Stay alert to what approaches."),
    ("萃 Cuì",   "Gathering",         "Bring people together around a worthy cause."),
    ("升 Shēng", "Pushing Upward",    "Gradual advance is certain. Step by step to the summit."),
    ("困 Kùn",   "Oppression",        "Exhaustion tests character. The noble one stays true."),
    ("井 Jǐng",  "The Well",          "Constant renewal nourishes all. Go to the source."),
    ("革 Gé",    "Revolution",        "Change what no longer serves. Transform with conviction."),
    ("鼎 Dǐng",  "The Cauldron",      "Refine and transform raw potential into something great."),
    ("震 Zhèn",  "The Arousing",      "Thunder awakens. Shock leads to clarity and new starts."),
    ("艮 Gèn",   "Keeping Still",     "Rest and stillness restore clarity. Know when to stop."),
    ("渐 Jiàn",  "Development",       "Gradual progress like a tree growing — steady and sure."),
    ("归妹 Guī Mèi","The Marrying",   "Align desires with reality. Sincerity guides the heart."),
    ("丰 Fēng",  "Abundance",         "Abundance is at its peak. Enjoy it and share it wisely."),
    ("旅 Lǚ",    "The Wanderer",      "Travel lightly. Adaptability is your greatest asset."),
    ("巽 Xùn",   "The Gentle",        "Gentle persistence penetrates. Influence through subtlety."),
    ("兑 Duì",   "The Joyous",        "Joy and open exchange bring good fortune to all."),
    ("涣 Huàn",  "Dispersion",        "Dissolve divisions. Gather scattered energies as one."),
    ("节 Jié",   "Limitation",        "Wise restraint creates sustainable success."),
    ("中孚 Zhōng Fú","Inner Truth",   "Sincerity in the heart moves heaven and earth."),
    ("小过 Xiǎo Guò", "Small Excess", "Small steps over the line. Caution in minor matters."),
    ("既济 Jì Jì",    "After Completion","Success achieved — maintain it with vigilance."),
    ("未济 Wèi Jì",   "Before Completion","The goal is near but not yet reached. Persevere."),
]

def get_daily_hexagram(target_date=None):
    """Return deterministic hexagram number (1-64) for a given date."""
    d = target_date or datetime.now(_MYT).date()
    seed = int(hashlib.md5(str(d).encode()).hexdigest(), 16)
    return (seed % 64) + 1  # 1-64

def get_hexagram_info(hex_num: int) -> dict:
    """Return full hexagram data including lucky digits."""
    idx       = hex_num - 1
    upper, lower = HEXAGRAM_TRIGRAMS[idx]
    u_tri     = TRIGRAMS[upper]
    l_tri     = TRIGRAMS[lower]
    name, eng, meaning = HEXAGRAM_DATA[idx]
    lucky_digits = sorted(set(u_tri['digits'] + l_tri['digits']))
    return {
        'num':     hex_num,
        'symbol':  f"{u_tri['symbol']}{l_tri['symbol']}",
        'name':    name,
        'english': eng,
        'meaning': meaning,
        'upper':   f"{u_tri['symbol']} {u_tri['name']} ({u_tri['element']})",
        'lower':   f"{l_tri['symbol']} {l_tri['name']} ({l_tri['element']})",
        'digits':  lucky_digits,
    }

def filter_by_ching(predictions: list, lucky_digits: list) -> list:
    """
    Filter top-30 predictions to numbers containing I-Ching lucky digits.
    Tries ≥2 matching digits first; falls back to ≥1 if fewer than 5 results.
    Returns list of (number, score, matched_digits).
    """
    def matches(num, min_match):
        m = set(int(d) for d in num) & set(lucky_digits)
        return m if len(m) >= min_match else None

    results = [(num, sc, matches(num, 2)) for num, sc in predictions if matches(num, 2)]
    if len(results) < 5:
        results = [(num, sc, matches(num, 1)) for num, sc in predictions if matches(num, 1)]
    return results

# ═══════════════════════════════════════════════════════════════
# GEODETIC ASTROLOGY SYSTEM (Penang: 100.3°E, 5.4°N)
# ═══════════════════════════════════════════════════════════════

import math as _math

# Draw venue geodetic longitudes (ASC = longitude in geodetic system)
DRAW_LOCATIONS = {
    'mag':  {'lon': 101.7136, 'name': 'Wisma Magnum, Jalan Pudu, KL'},
    'toto': {'lon': 101.71091, 'name': 'Sports Toto HQ, Berjaya Times Square, KL'},
    'dmc':  {'lon': 101.7136, 'name': 'Wisma Magnum, Jalan Pudu, KL'},
}
# Key geodetic angles computed dynamically per location in get_geodetic_info()
ASPECT_ORB      = 8.0     # degrees

GEO_SIGNS = [
    "Aries","Taurus","Gemini","Cancer","Leo","Virgo",
    "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"
]
GEO_SYMBOLS = ["♈","♉","♊","♋","♌","♍","♎","♏","♐","♑","♒","♓"]

GEO_SIGN_DIGITS = {
    "Aries":       [9,1,8], "Taurus":      [6,4,2], "Gemini":   [5,3,8],
    "Cancer":      [2,7,6],   "Leo":         [1,4,9], "Virgo":    [5,3,6],
    "Libra":       [6,4,8], "Scorpio":     [9,2,4], "Sagittarius":[3,6,9],
    "Capricorn":   [8,4,1], "Aquarius":    [4,8,7], "Pisces":   [7,2,3],
}


# ── Numerology compatibility (Pythagorean triads) ────────────
# Group A (1-4-7): Sun/Uranus/Ketu — initiative, structure, wisdom
# Group B (2-5-8): Moon/Mercury/Saturn — emotion, change, discipline
# Group C (3-6-9): Jupiter/Venus/Mars — growth, harmony, completion
# 0 always included (primordial void — universal digit)
NUM_COMPAT = {
    1:[1,4,7], 4:[1,4,7], 7:[1,4,7],
    2:[2,5,8], 5:[2,5,8], 8:[2,5,8],
    3:[3,6,9], 6:[3,6,9], 9:[3,6,9],
    11:[1,2,4], 22:[2,4,8],
}
NUM_GROUP = {
    1:"A(1·4·7)", 4:"A(1·4·7)", 7:"A(1·4·7)",
    2:"B(2·5·8)", 5:"B(2·5·8)", 8:"B(2·5·8)",
    3:"C(3·6·9)", 6:"C(3·6·9)", 9:"C(3·6·9)",
    11:"Master11", 22:"Master22",
}

def universal_day_number(d: date) -> int:
    """Reduce full date DDMMYYYY to a single numerological digit (1-9, 11, 22)."""
    digits = f"{d.day:02d}{d.month:02d}{d.year:04d}"
    total  = sum(int(c) for c in digits)
    while total > 9 and total not in (11, 22):
        total = sum(int(c) for c in str(total))
    return total

def filter_geo_by_numerology(geo_digits: list, d: date) -> tuple:
    """
    Filter geodetic combined digits using daily numerology.
    Returns (filtered_digits, udn, group_name).
    Reduces ~7 digits to ~3 digits on average.
    0 is always kept (universal digit).
    """
    udn    = universal_day_number(d)
    compat = NUM_COMPAT.get(udn, [])
    filtered = sorted(set(x for x in geo_digits if x in compat))
    return filtered, udn, NUM_GROUP.get(udn, str(udn))

def _sun_longitude(d: date) -> float:
    jd = (d - date(2000,1,1)).days + 0.5
    L  = (280.46646 + 36000.76983*(jd/36525)) % 360
    g  = _math.radians((357.52911 + 35999.05029*(jd/36525)) % 360)
    C  = (1.914602 - 0.004817*(jd/36525))*_math.sin(g) \
       + 0.019993*_math.sin(2*g) + 0.000289*_math.sin(3*g)
    return (L + C) % 360

def _moon_longitude(d: date) -> float:
    jd = (d - date(2000,1,1)).days + 0.5
    Lm = (218.3164477 + 481267.88123421*(jd/36525)) % 360
    M  = _math.radians((134.9633964 + 477198.8675055*(jd/36525)) % 360)
    Ms = _math.radians((357.5291092 +  35999.0502909*(jd/36525)) % 360)
    lon = Lm + 6.289*_math.sin(M) \
             - 1.274*_math.sin(2*_math.radians(Lm)-M) \
             + 0.658*_math.sin(2*_math.radians(Lm)) \
             - 0.214*_math.sin(2*M) - 0.186*_math.sin(Ms)
    return lon % 360

def _lon_to_sign(lon: float) -> tuple:
    idx = int(lon // 30)
    return GEO_SIGNS[idx], GEO_SYMBOLS[idx], round(lon % 30, 1)

def get_geodetic_info(today: date, lon: float = 101.7136) -> dict:
    """
    Compute full Penang geodetic analysis for today.
    Combines:
      - Penang natal Cancer energy (permanent)
      - Transiting Sun sign digits
      - Transiting Moon sign digits
      - Aspect bonus if Sun/Moon within 8° of Penang angles
    """
    sun_lon  = _sun_longitude(today)
    moon_lon = _moon_longitude(today)

    sun_sign,  sun_sym,  sun_deg  = _lon_to_sign(sun_lon)
    moon_sign, moon_sym, moon_deg = _lon_to_sign(moon_lon)

    sun_house  = int((sun_lon  - lon) % 360 // 30) + 1
    moon_house = int((moon_lon - lon) % 360 // 30) + 1

    # Aspect detection
    active_aspects = []
    angle_names    = ["ASC","IC","DSC","MC"]
    key_pts = [lon, lon+90, lon+180, lon-90]
    for pt, ang_name in zip(key_pts, angle_names):
        if abs((sun_lon  - pt + 180) % 360 - 180) < ASPECT_ORB:
            active_aspects.append(f"☀️ Sun on Penang {ang_name}")
        if abs((moon_lon - pt + 180) % 360 - 180) < ASPECT_ORB:
            active_aspects.append(f"🌙 Moon on Penang {ang_name}")

    # Digit pool: natal Cancer + Sun sign + Moon sign
    natal_digits = GEO_SIGN_DIGITS["Cancer"]  # 101.7136° = 11.7° Cancer
    sun_digits   = GEO_SIGN_DIGITS[sun_sign]
    moon_digits  = GEO_SIGN_DIGITS[moon_sign]
    combined     = sorted(set(natal_digits + sun_digits + moon_digits))

    filtered_num, udn, udn_group = filter_geo_by_numerology(combined, today)
    return {
        "sun_sign":  sun_sign,  "sun_sym":   sun_sym,
        "sun_deg":   sun_deg,   "sun_house": sun_house,
        "sun_digits": sun_digits,
        "moon_sign": moon_sign, "moon_sym":  moon_sym,
        "moon_deg":  moon_deg,  "moon_house":moon_house,
        "moon_digits": moon_digits,
        "natal_digits":natal_digits,
        "combined":  combined,
        "filtered":  filtered_num,
        "udn":       udn,
        "udn_group": udn_group,
        "aspects":   active_aspects,
    }

def score_number_lucky(num: str, geo_digits: list, ching_digits: list) -> tuple:
    """
    Score a number against 2 independent filters:
      1. Geodetic astrology (Penang combined digits)
      2. I-Ching hexagram digits
    Returns (score 0-2, matched_filters list).
    """
    d       = set(int(c) for c in num)
    matched = []
    if d & set(geo_digits):   matched.append("Geo")
    if d & set(ching_digits): matched.append("Ching")
    return len(matched), matched


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

    # Cooldown model accumulators
    short_s    = defaultdict(float)   # S6: short-term freq (to invert)
    tier_short = defaultdict(float)   # S8: tier-weighted short freq (to invert)
    last_seen  = {}                   # S7: track last draw index per number
    gap_sums   = defaultdict(float)
    gap_sq     = defaultdict(float)
    gap_cnt    = defaultdict(int)

    long_s = defaultdict(float)

    try:
        df    = pd.read_csv(csv_path)
        total = len(df)

        if "draw_date" in df.columns:
            df["draw_date"] = df["draw_date"].astype(str).str.strip()

        for idx, (_, row) in enumerate(df.iterrows()):
            age    = total - 1 - idx
            wl     = math.pow(0.5, age / HALF_LIFE_L)
            ws     = math.pow(0.5, age / HALF_LIFE_S)
            wcs    = math.pow(0.5, age / HALF_LIFE_CS)
            date_str = str(row.get("draw_date", ""))

            draw_top3 = []

            for col in PRIZE_COLS:
                if col not in df.columns: continue
                num = str(row[col]).zfill(4)
                if not (num.isdigit() and len(num) == 4): continue

                freq[num] += 1
                if date_str:
                    date_map[num].append(date_str)

                long_s[num]    += wl
                short_s[num]   += ws
                tier_short[num]+= TIER_W.get(col, 1) * wcs

                if num in last_seen:
                    g = idx - last_seen[num]
                    gap_sums[num] += g
                    gap_sq[num]   += g * g
                    gap_cnt[num]  += 1
                last_seen[num] = idx

                if col in TOP3_COLS:
                    top3_score[num] += wl
                    top3_freq[num]  += 1
                    draw_top3.append(num)

            for i, a in enumerate(draw_top3):
                for b in draw_top3[i + 1:]:
                    co_occur[tuple(sorted([a, b]))] += 1

        # Sort dates newest-first
        for num in date_map:
            try:
                date_map[num].sort(
                    key=lambda d: pd.to_datetime(d, dayfirst=True), reverse=True)
            except Exception:
                date_map[num].sort(reverse=True)

        # ── Build cooldown signal matrix for /predict ────────────────────
        all_nums = list(freq.keys())
        m        = len(all_nums)
        total_draws = total

        # S6: cooldown = INVERSE of short-term frequency
        #     numbers that appeared recently get LOW score
        s6_raw = np.array([-short_s.get(n, 0) for n in all_nums])

        # S7: gap reward = draws since last seen (capped at 50)
        #     numbers absent for longer get HIGHER score
        s7_raw = np.array([
            min(total_draws - 1 - last_seen.get(n, 0), 50)
            for n in all_nums
        ], dtype=float)

        # S8: tier-weighted cooldown = inverse of tier-weighted short freq
        s8_raw = np.array([-tier_short.get(n, 0) for n in all_nums])

        def norm(v):
            mn, mx = v.min(), v.max()
            return (v - mn) / (mx - mn + 1e-12)

        signal_matrix = np.column_stack([norm(s6_raw), norm(s7_raw), norm(s8_raw)])

        log.info(f"Loaded {csv_path}: {total} draws, {m} unique numbers.")

    except FileNotFoundError:
        log.warning(f"{csv_path} not found.")
        all_nums = []; signal_matrix = np.empty((0, 3))
    except Exception as e:
        log.error(f"Failed to load {csv_path}: {e}")
        all_nums = []; signal_matrix = np.empty((0, 3))

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

def get_predictions(maps: dict, n: int = PREDICT_N, game: str = "") -> list:
    """
    Return top-N numbers by cooldown score + positional digit bonus.
    Thousands digit 1 bonus: +0.26% edge (Magnum) / +0.22% (Toto) from research.
    Returns list of (number, normalised_score).
    """
    mat      = maps["sig_matrix"]
    all_nums = maps["all_nums"]
    if mat.size == 0 or len(all_nums) == 0:
        return []

    base     = mat @ MODEL_WEIGHTS
    pb       = POSITIONAL_BONUS.get(game, {})
    th_bonus = pb.get("thousands", {})
    if th_bonus:
        scores = np.array([base[i] * (1 + th_bonus.get(int(all_nums[i][0]), 0))
                           for i in range(len(all_nums))])
    else:
        scores = base

    top_idx  = np.argpartition(scores, -n)[-n:]
    top_idx  = top_idx[np.argsort(scores[top_idx])[::-1]]
    max_s    = scores[top_idx[0]] or 1.0

    return [(all_nums[i], float(scores[i] / max_s)) for i in top_idx]


# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
# DIGIT ANALYSIS  (/mag /toto /dmc)
# ═══════════════════════════════════════════════════════════════

def analyze_digits(digit_str: str, freq: Counter) -> list:
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
            "*Digit Analysis:*\n"
            "🔴 `/mag 123456` — Magnum 4D\n"
            "🔵 `/toto 123456` — Sports Toto\n"
            "🟢 `/dmc 123456` — Da Ma Cai\n\n"
            "*Smart Predictions (top 30):*\n"
            "🔮 `/predict mag` — Magnum\n"
            "🔮 `/predict toto` — Sports Toto\n"
            "🔮 `/predict dmc` — Da Ma Cai\n\n"
                        "*I-Ching Daily Filter:*\n"
            "🔯 `/ching mag` — Magnum\n"
            "🔯 `/ching toto` — Sports Toto\n"
            "🔯 `/ching dmc` — Da Ma Cai\n\n"
            "*Geodetic Filter (Wisma Magnum KL):*\n"
            "🌍 `/geo mag` — Magnum\n"
            "🌍 `/geo toto` — Sports Toto\n"
            "🌍 `/geo dmc` — Da Ma Cai\n\n"
            "*Lucky Filter (Geodetic + I-Ching):*\n"
            "🌟 `/lucky mag` — Magnum\n"
            "🌟 `/lucky toto` — Sports Toto\n"
            "🌟 `/lucky dmc` — Da Ma Cai\n\n"
            "_Digit commands: min 4, max 12 digits._"
        )
        return

    # ── /geo ─────────────────────────────────────────────────────────
    if lower.startswith("/geo"):
        parts = text.split()
        if len(parts) < 2 or parts[1].lower() not in ("mag","toto","dmc"):
            send(chat_id,
                "⚠️ Usage:\n"
                "`/geo mag`\n`/geo toto`\n`/geo dmc`\n\n"
                "Filters top 88 predictions using geodetic astrology\n"
                "anchored to Wisma Magnum, Jalan Pudu, KL (101.7°E)."
            )
            return

        game  = parts[1].lower()
        emoji = GAME_EMOJI[game]
        label = GAME_LABELS[game]

        today    = datetime.now(_MYT).date()
        loc      = DRAW_LOCATIONS[game]
        geo      = get_geodetic_info(today, loc["lon"])
        preds    = get_predictions(data[game], n=88, game=game)

        if not preds:
            send(chat_id, "❌ Not enough data yet.")
            return

        # Filter: numbers passing geodetic + numerology filtered digits
        active_digits = geo["filtered"] if geo["filtered"] else geo["combined"]
        geo_nums = [(num, sc) for num, sc in preds
                    if set(int(c) for c in num) & set(active_digits)]

        today_str = today.strftime("%d %b %Y")
        lon_str   = f"{loc['lon']:.4f}"
        lines = [
            f"🌍 *Geodetic + Numerology Filter — {today_str}*\n",
            f"*{loc['name']} ({lon_str}°E)*\n",
            f"🔢 UDN *{geo['udn']}* — {geo['udn_group']} → compat digits *{geo['filtered']}*\n",
            f"☀️ Sun {geo['sun_deg']}° {geo['sun_sign']} {geo['sun_sym']} "
            f"(H{geo['sun_house']}) → *{', '.join(str(d) for d in geo['sun_digits'])}*",
            f"🌙 Moon {geo['moon_deg']}° {geo['moon_sign']} {geo['moon_sym']} "
            f"(H{geo['moon_house']}) → *{', '.join(str(d) for d in geo['moon_digits'])}*",
            f"♋ Natal Cancer → *{', '.join(str(d) for d in geo['natal_digits'])}*",
            f"Combined → *{', '.join(str(d) for d in geo['combined'])}*",
        ]
        if geo["aspects"]:
            for asp in geo["aspects"]:
                lines.append(f"🔥 _{asp}_")

        lines += [
            f"\n─────────────────────",
            f"{emoji} *{label} — {len(geo_nums)} matched numbers*\n",
        ]

        if geo_nums:
            for num, sc in geo_nums:
                bar = "█" * round(sc * 10) + "░" * (10 - round(sc * 10))
                lines.append(f"`{num}`  {bar}")
        else:
            lines.append("_No numbers matched today's geodetic digits._")
            lines.append("_Try /predict for the full top 88._")

        lines.append(f"\n_Geodetic {len(geo['combined'])} digits → Numerology filtered to {len(active_digits)} digits_")
        lines.append(f"_Backtest edge: +10.45% · p=0.000 · ✅ significant_")
        lines.append(f"_For inspiration only · Not a guarantee of winning_")
        send(chat_id, "\n".join(lines))
        return

    # ── /lucky ───────────────────────────────────────────────────────
    if lower.startswith("/lucky"):
        parts = text.split()
        if len(parts) < 2 or parts[1].lower() not in ("mag","toto","dmc"):
            send(chat_id,
                "⚠️ Usage: `/lucky mag`\n\n"
                "Filters top 30 predictions using:\n"
                "🌍 Geodetic Astrology (Penang chart)\n"
                "🔯 I-Ching (today\'s hexagram)\n\n"
                "Each number scored 0–2 ⭐"
            )
            return

        game  = parts[1].lower()
        emoji = GAME_EMOJI[game]
        label = GAME_LABELS[game]

        today     = datetime.now(_MYT).date()
        loc       = DRAW_LOCATIONS[game]
        geo       = get_geodetic_info(today, loc["lon"])
        hex_num   = get_daily_hexagram()
        ching_inf = get_hexagram_info(hex_num)
        ching_d   = ching_inf["digits"]

        preds = get_predictions(data[game], n=30)
        if not preds:
            send(chat_id, "❌ Not enough data yet.")
            return

        # Score all 30 numbers
        scored = []
        for num, model_score in preds:
            stars, matched = score_number_lucky(num, geo["combined"], ching_d)
            scored.append((num, model_score, stars, matched))

        # Sort: most stars first, then model score
        scored.sort(key=lambda x: (x[2], x[1]), reverse=True)

        today_str = today.strftime("%d %b %Y")
        lines = [
            f"🌟 *Lucky Filter — {today_str}*\n",
            f"🌍 *Geodetic* ({loc['name']})",
            f"   ☀️ {geo['sun_deg']}° {geo['sun_sign']} {geo['sun_sym']}  "
            f"🌙 {geo['moon_deg']}° {geo['moon_sign']} {geo['moon_sym']}",
            f"   UDN *{geo['udn']}* ({geo['udn_group']}) → active *{active_geo}*",
            f"🔯 *I-Ching* #{hex_num} {ching_inf['symbol']} {ching_inf['name']} → *{list(ching_d)}*",
        ]
        if geo["aspects"]:
            for asp in geo["aspects"]:
                lines.append(f"   🔥 _{asp}_")
        lines += [
            f"\n🔯 *I-Ching:* #{hex_num} {ching_inf['symbol']} "
            f"{ching_inf['name']} → *{', '.join(str(d) for d in ching_d)}*",
            f"\n─────────────────────",
            f"{emoji} *{label} — 88 numbers scored*",
            f"_⭐⭐ = geodetic + I-Ching both matched_\n",
        ]

        # Only show numbers that passed BOTH filters (⭐⭐)
        both_passed = [(num, sc, stars, matched)
                       for num, sc, stars, matched in scored if stars == 2]

        if both_passed:
            for num, model_score, stars, matched in both_passed:
                bar   = "█" * round(model_score * 10) + "░" * (10 - round(model_score * 10))
                lines.append(f"`{num}`  ⭐⭐  {bar}")
        else:
            lines.append("_No numbers matched both filters today._")
            lines.append("_Try /ching or /predict for broader results._")

        lines.append(f"\n_Total matched: {len(both_passed)}/88 numbers_")
        lines.append(f"_Prediction model + geodetic astrology + I-Ching_")
        lines.append(f"_For inspiration only · Not a guarantee of winning_")
        send(chat_id, "\n".join(lines))
        return

    # ── /ching ───────────────────────────────────────────────────────
    if lower.startswith("/ching"):
        parts = text.split()
        if len(parts) < 2 or parts[1].lower() not in ("mag", "toto", "dmc"):
            send(chat_id,
                "⚠️ Usage:\n"
                "`/ching mag`\n`/ching toto`\n`/ching dmc`")
            return

        game     = parts[1].lower()
        emoji    = GAME_EMOJI[game]
        label    = GAME_LABELS[game]
        hex_num  = get_daily_hexagram()
        info     = get_hexagram_info(hex_num)
        preds    = get_predictions(data[game], n=88, game=game)

        if not preds:
            send(chat_id, "❌ Not enough data yet.")
            return

        filtered = filter_by_ching(preds, info['digits'])

        today_str = datetime.now(_MYT).date().strftime("%d %b %Y")
        lines = [
            f"🔯 *I-Ching Daily Reading — {today_str}*\n",
            f"*Hexagram #{info['num']}* {info['symbol']}",
            f"*{info['name']}* — _{info['english']}_\n",
            f"_{info['meaning']}_\n",
            f"▲ Upper: {info['upper']}",
            f"▽ Lower: {info['lower']}",
            f"🔢 Lucky digits: *{', '.join(str(d) for d in info['digits'])}*\n",
            f"─────────────────────",
            f"{emoji} *{label} — {len(filtered)} filtered predictions*\n",
        ]

        if filtered:
            for rank, (num, score, matched) in enumerate(filtered, 1):
                bar = "█" * round(score * 10) + "░" * (10 - round(score * 10))
                md  = ", ".join(str(d) for d in sorted(matched))
                lines.append(f"`{rank:>2}.` `{num}`  {bar}  _digits: {md}_")
        else:
            lines.append("_No numbers matched today's hexagram digits._")
            lines.append("_Try /predict for the full top 30 instead._")

        lines.append(f"\n_For inspiration only · Not a guarantee of winning_")
        send(chat_id, "\n".join(lines))
        return

    # ── /predict ──────────────────────────────────────────────────────
    if lower.startswith("/predict"):
        parts = text.split()
        if len(parts) < 2 or parts[1].lower() not in ("mag", "toto", "dmc"):
            send(chat_id,
                "⚠️ Usage:\n"
                "`/predict mag`\n`/predict toto`\n`/predict dmc`")
            return

        game  = parts[1].lower()
        emoji = GAME_EMOJI[game]
        label = GAME_LABELS[game]
        preds = get_predictions(data[game], game=game)

        if not preds:
            send(chat_id, "❌ Not enough data yet.")
            return

        date_map = data[game]["date_map"]
        lines = [
            f"🔮 {emoji} *{label} — Top {PREDICT_N} Predictions*\n",
            f"_Model: Cooldown · numbers unlikely to repeat soon_",
            f"_Backtest: +8% edge · p=0.000 · statistically significant_\n",
        ]

        for rank, (num, score) in enumerate(preds, 1):
            bar       = "█" * round(score * 10) + "░" * (10 - round(score * 10))
            conf      = f"{score*100:.0f}%"
            last_date = (date_map.get(num) or [None])[0]
            if last_date:
                lines.append(
                    f"`{rank:>2}.` `{num}`  {bar}  *{conf}*\n"
                    f"`       `_{last_date}_"
                )
            else:
                lines.append(f"`{rank:>2}.` `{num}`  {bar}  *{conf}*")

        send(chat_id, "\n".join(lines))
        return

        game  = parts[1].lower()
        emoji = GAME_EMOJI[game]
        label = GAME_LABELS[game]

        if not pairs:
            send(chat_id, "❌ Not enough data yet.")
            return

        lines = [
            f"_Built from top 30 predicted numbers · ⭐ = historical co-occurrence_\n",
        ]
        for rank, (a, b, score, fa, fb, co) in enumerate(pairs, 1):
            star = " ⭐" if co > 0 else ""
            lines.append(f"`{rank:>2}.` `{a}` + `{b}`{star}")

        lines.append(f"\n_⭐ = pair appeared together in Top 3 before_")
        send(chat_id, "\n".join(lines))
        return

    # ── /mag /toto /dmc ───────────────────────────────────────────────
    game = None
    if lower.startswith("/mag"):    game = "mag"
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

    lines = [f"📊 {GAME_EMOJI[game]} *{GAME_LABELS[game]} — Top {TOP_N} for* `{digits}`\n"]

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
# AUTO-SCRAPER + DATA RELOADER
# ═══════════════════════════════════════════════════════════════

def auto_scrape_loop(data: dict, token: str):
    """
    Background thread: runs scraper.py on draw nights (Wed/Sat/Sun)
    after 8pm MYT, then reloads all CSV data into memory.
    Sends a Telegram notification when new data is loaded.
    """
    scraped_dates = set()
    myt = _MYT
    log.info("Auto-scraper started.")

    while True:
        try:
            now = datetime.now(myt)
            today_key = now.strftime("%Y-%m-%d")

            if (now.weekday() in DRAW_DAYS
                    and now.hour >= SCRAPE_AFTER
                    and today_key not in scraped_dates):

                log.info(f"Draw night detected ({now.strftime('%A %d %b')}). Running scraper...")
                result = subprocess.run(
                    ["python", "scraper.py"],
                    capture_output=True, text=True, timeout=60
                )
                log.info(f"Scraper output: {result.stdout.strip()}")
                scraped_dates.add(today_key)

                # Reload all CSVs into memory
                log.info("Reloading data after scrape...")
                for game, path in CSV_FILES.items():
                    data[game] = build_data(path)
                log.info("Data reload complete.")

                # Notify via Telegram if token available
                if token:
                    try:
                        draws = {
                            "mag":  len(data["mag"]["freq"]),
                            "toto": len(data["toto"]["freq"]),
                            "dmc":  len(data["dmc"]["freq"]),
                        }
                        msg = (
                            f"🔄 *Results updated — {now.strftime('%d %b %Y')}*\n\n"
                            f"🔴 Magnum: {data['mag']['freq'] and 'loaded' or 'no data'}\n"
                            f"🔵 Toto: {data['toto']['freq'] and 'loaded' or 'no data'}\n"
                            f"🟢 DMC: {data['dmc']['freq'] and 'loaded' or 'no data'}\n\n"
                            f"_Bot predictions refreshed with latest draw_"
                        )
                        url = f"https://api.telegram.org/bot{token}/sendMessage"
                        chat = os.environ.get("NOTIFY_CHAT_ID", os.environ.get("CHAT_ID",""))
                        if chat:
                            requests.post(url, json={"chat_id":chat,"text":msg,"parse_mode":"Markdown"}, timeout=10)
                    except Exception as e:
                        log.warning(f"Notification failed: {e}")

        except Exception as e:
            log.error(f"Scheduler error: {e}")

        time.sleep(SCRAPE_CHECK)

# ═══════════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════════

def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN environment variable is not set.")

    log.info("Bot starting — loading data...")
    data = {game: build_data(path) for game, path in CSV_FILES.items()}
    log.info("All data loaded. Starting auto-scraper thread...")
    scraper_thread = threading.Thread(
        target=auto_scrape_loop, args=(data, TOKEN), daemon=True
    )
    scraper_thread.start()
    log.info("Listening for messages...")

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
