"""
scraper.py
==========
Fetches the latest Magnum, Sports Toto, and Da Ma Cai results
from check4d.org and appends new rows to their respective CSV files.

  results.csv       — Magnum 4D
  toto_results.csv  — Sports Toto
  dmc_results.csv   — Da Ma Cai
"""

import csv
import os
import re
import sys
from datetime import datetime

import requests
from bs4 import BeautifulSoup

URL     = "https://www.check4d.org/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Each game: logo pattern → CSV file
GAMES = {
    "magnum": {"logo": "logo_magnum", "csv": "results.csv"},
    "toto":   {"logo": "logo_toto",   "csv": "toto_results.csv"},
    "dmc":    {"logo": "logo_damacai","csv": "dmc_results.csv"},
}

CSV_COLUMNS = [
    "draw_id", "draw_date", "day_of_week",
    "prize_1st", "prize_2nd", "prize_3rd",
    *[f"special_{i}"     for i in range(1, 11)],
    *[f"consolation_{i}" for i in range(1, 11)],
]


def parse_game_block(block_html: str) -> dict | None:
    """Extract draw info and prizes from a game's HTML block."""
    soup  = BeautifulSoup(block_html, "html.parser")
    text  = soup.get_text(" ", strip=True)

    # Draw number
    m = re.search(r"Draw No[:\s]*([\d]+/[\d]+)", text)
    draw_id = m.group(1) if m else ""

    # Date and day
    m = re.search(r"Date[:\s]*([\d]{2}-[\d]{2}-[\d]{4})\s*\(([\w]+)\)", text)
    if m:
        try:
            dt = datetime.strptime(m.group(1), "%d-%m-%Y")
            draw_date   = dt.strftime("%d/%m/%Y")
            day_of_week = m.group(2)
        except Exception:
            draw_date   = m.group(1)
            day_of_week = m.group(2)
    else:
        draw_date = day_of_week = ""

    # Top 3 prizes — grab all 4-digit numbers tagged near prize labels
    prize_1st = prize_2nd = prize_3rd = ""
    m1 = re.search(r"1st[^0-9]*(\d{4})", text)
    m2 = re.search(r"2nd[^0-9]*(\d{4})", text)
    m3 = re.search(r"3rd[^0-9]*(\d{4})", text)
    if m1: prize_1st = m1.group(1)
    if m2: prize_2nd = m2.group(1)
    if m3: prize_3rd = m3.group(1)

    if not prize_1st:
        return None

    # Special prizes — find the "Special" table
    specials = []
    for tbl in soup.find_all("table"):
        t = tbl.get_text(" ", strip=True)
        if "Special" in t and "Consolation" not in t:
            found = re.findall(r"\b(\d{4})\b", t)
            if found:
                specials = found[:10]
                break

    # Consolation prizes
    consolations = []
    for tbl in soup.find_all("table"):
        t = tbl.get_text(" ", strip=True)
        if "Consolation" in t and "Special" not in t:
            found = re.findall(r"\b(\d{4})\b", t)
            if found:
                consolations = found[:10]
                break

    specials     = (specials     + [""] * 10)[:10]
    consolations = (consolations + [""] * 10)[:10]

    return {
        "draw_id":    draw_id,
        "draw_date":  draw_date,
        "day_of_week": day_of_week,
        "prize_1st":  prize_1st,
        "prize_2nd":  prize_2nd,
        "prize_3rd":  prize_3rd,
        **{f"special_{i+1}":     specials[i]     for i in range(10)},
        **{f"consolation_{i+1}": consolations[i] for i in range(10)},
    }


def split_game_blocks(html: str) -> dict[str, str]:
    """Split the full page HTML into per-game sections by logo image."""
    blocks = {}
    for game, cfg in GAMES.items():
        pattern = rf'({re.escape(cfg["logo"])}.*?)(?:logo_magnum|logo_toto|logo_damacai|SINGAPORE|$)'
        m = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
        if m:
            blocks[game] = m.group(0)
    return blocks


def load_existing_ids(csv_path: str) -> set:
    if not os.path.exists(csv_path):
        return set()
    with open(csv_path, newline="") as f:
        return {row.get("draw_id", "").strip() for row in csv.DictReader(f)}


def append_result(csv_path: str, result: dict):
    file_exists = os.path.exists(csv_path)
    with open(csv_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(result)


def main():
    print(f"Fetching {URL} ...")
    try:
        resp = requests.get(URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    blocks = split_game_blocks(resp.text)
    any_new = False

    for game, cfg in GAMES.items():
        print(f"\n── {game.upper()} ──")
        block_html = blocks.get(game, "")
        if not block_html:
            print(f"  Could not find {game} section on page.")
            continue

        result = parse_game_block(block_html)
        if not result or not result["prize_1st"]:
            print(f"  Could not parse prize data for {game}.")
            continue

        print(f"  Draw: {result['draw_id']} | Date: {result['draw_date']}")
        print(f"  1st: {result['prize_1st']}  2nd: {result['prize_2nd']}  3rd: {result['prize_3rd']}")

        csv_path = cfg["csv"]
        existing = load_existing_ids(csv_path)

        if result["draw_id"] in existing:
            print(f"  Already in {csv_path}. Skipping.")
            continue

        append_result(csv_path, result)
        print(f"  ✅ Appended to {csv_path}")
        any_new = True

    if not any_new:
        print("\nNo new draws found.")
    else:
        print("\nDone — results updated.")


if __name__ == "__main__":
    main()
