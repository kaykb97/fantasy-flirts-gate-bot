# Fantasy Flirts — Rolling GATE Board

Posts a rolling prediction board showing the **next nine GATEs** (three hours of coverage) in your Discord channel. GATE slots are spaced 20 minutes apart.

## Important timezone behavior

The GATE algorithm uses UTC Unix time. The post uses Discord timestamp markup (`<t:...:t>`), so **each member sees the schedule times in their own Discord-local timezone**. The board is refreshed every **two hours on the clock**: 12 AM, 2 AM, 4 AM, 6 AM, 8 AM, 10 AM, 12 PM, 2 PM, 4 PM, 6 PM, 8 PM, and 10 PM Eastern Time. Daylight saving time is handled automatically. Discord relative timestamps show each member the time remaining in their own local timezone.

## Free hosting: GitHub Actions + Discord webhook

This version does not need a continuously running bot process or a paid host. GitHub Actions checks every 15 minutes, but the bot posts a new board only when its saved two-hour Eastern clock deadline is due.

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
3. Open **Flirtingway GATE Scheduler** and choose **Run workflow** to run a check. To post immediately, select **Force post immediately**.
4. Scheduled checks continue every 15 minutes; actual board posts follow the fixed two-hour Eastern clock schedule.

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

A local run follows the same fixed three-hour Eastern clock schedule unless `FORCE_POST=true` is set. Do not paste your real webhook URL into chat, source code, screenshots, or a public issue.

## Files

- `bot.py` — prediction algorithm, nine-gate board, and fixed three-hour Eastern posting schedule
- `.github/workflows/daily.yml` — 15-minute checks for fixed Eastern clock deadlines
- `requirements.txt` — HTTP dependency
- `ATTRIBUTION.md` — upstream project credit/license note
