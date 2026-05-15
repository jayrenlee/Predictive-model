# Deployment Guide — Magnum 4D Analyzer Bot

## Files you need in your GitHub repo

```
your-repo/
├── bot.py
├── requirements.txt
├── render.yaml
└── results.csv
```

---

## Step 1 — Regenerate your Telegram bot token

Your previous token was exposed in a shared file.

1. Open Telegram → search **@BotFather**
2. Send `/mybots` → select your bot
3. **API Token** → **Revoke current token**
4. Copy the new token

---

## Step 2 — Get your Telegram Chat ID

1. Send any message to your bot
2. Open this URL in a browser (replace TOKEN):
   `https://api.telegram.org/botTOKEN/getUpdates`
3. Find `"id"` inside `"from"` — that number is your CHAT_ID

---

## Step 3 — Push files to GitHub

```bash
git init                        # if not already a repo
git add bot.py requirements.txt render.yaml results.csv
git commit -m "initial deploy"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

---

## Step 4 — Deploy on Render

1. Go to https://render.com → **New** → **Blueprint**
2. Connect your GitHub repo
3. Render reads `render.yaml` automatically → click **Apply**
4. Go to your service → **Environment** tab → add:
   - `TELEGRAM_TOKEN` = your new bot token
   - `CHAT_ID` = your numeric Telegram ID
5. Click **Save** — the service restarts and goes live

---

## Step 5 — Test it

Send your bot any string of digits, e.g.:

```
019234
```

You should receive a reply within a few seconds listing the top 10 numbers.

---

## Updating results.csv

When you have new draw results:

```bash
# edit results.csv locally, then:
git add results.csv
git commit -m "update results"
git push
```

Render auto-deploys on every push. The bot reloads the CSV on startup.

---

## Keeping the bot running

Render Background Workers run 24/7 and restart automatically on crash.
You do not need a keep-alive ping or external scheduler.

---

## Digit limits

| Input digits | Combinations | Permutations | Response time |
|---|---|---|---|
| 4 | 1 | 24 | instant |
| 6 | 15 | 360 | instant |
| 8 | 70 | 1,680 | < 1 sec |
| 10 | 210 | 5,040 | < 1 sec |
| 12 | 495 | 11,880 | ~2 sec |

Bot rejects inputs above 12 digits to prevent timeouts.
