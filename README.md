# Fantasy Flirts — Daily GATE Bot

Posts the **predicted actual Gold Saucer GATE** for every 20-minute slot (72 entries/day) into your Discord `#events` channel.

## Important timezone behavior

The GATE algorithm uses UTC Unix time. The post uses Discord timestamp markup (`<t:...:t>`), so **each member sees the schedule times in their own Discord-local timezone**. The daily post is sent at **00:00 UTC** (7:00 PM Eastern during EST / 8:00 PM during EDT on the previous local date).

## Free hosting: GitHub Actions + Discord webhook

This version does not need a continuously running bot process or a paid host. GitHub Actions runs once per day and posts through a Discord webhook.

### 1. Create a Discord webhook in #events

1. In Discord, open **Server Settings → Integrations → Webhooks**.
2. Create a webhook named `Fantasy Flirts GATE Guide`.
3. Select your existing `#events` channel.
4. Copy the webhook URL. **Treat it like a password**; anyone with it can post to that channel.

### 2. Put this project in a GitHub repository

1. Create a repository at https://github.com/new (a private repository is fine).
2. Upload the files from this folder, keeping the `.github/workflows/daily.yml` path intact.
3. In the repository, open **Settings → Secrets and variables → Actions → New repository secret**.
4. Name it exactly `DISCORD_WEBHOOK_URL`.
5. Paste the webhook URL as the secret value.

### 3. Enable GitHub Actions

1. Open the repository's **Actions** tab.
2. If prompted, enable workflows.
3. Open **Daily GATE Schedule** and choose **Run workflow** to test immediately.
4. It will then run automatically every day at 00:00 UTC.

GitHub Actions is free within GitHub's included usage allowances. For the most reliable no-cost operation, a public repository also receives free standard GitHub-hosted runner usage. Keep the webhook URL only in repository Secrets, never in source code.

## Prediction algorithm and patch updates

The prediction logic and weights are adapted from the MIT-licensed community research project:
https://github.com/rooroodev/ffxivgateschedule

The upstream research states that GATE schedules are time-seeded and shared across worlds/regions on the same game version. It also documents the current weights and variants. If a future FFXIV patch changes the schedule, update `EVENTS` and variant definitions in `bot.py` using the upstream project's latest research.

## Manual local test

Requires Python 3.10+:

```bash
python -m pip install -r requirements.txt
DISCORD_WEBHOOK_URL="your-webhook-url" python bot.py
```

This posts immediately. Do not paste your real webhook URL into chat, source code, screenshots, or a public issue.

## Files

- `bot.py` — prediction algorithm and Discord posting
- `.github/workflows/daily.yml` — free daily scheduled runner
- `requirements.txt` — HTTP dependency
- `ATTRIBUTION.md` — upstream project credit/license note
