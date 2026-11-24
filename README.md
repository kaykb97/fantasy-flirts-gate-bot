# Fantasy Flirts — Rolling GATE Board

Posts a rolling prediction board showing the **next nine GATEs** (three hours of coverage) in your Discord channel. GATE slots are spaced 20 minutes apart.

## Important timezone behavior

The GATE algorithm uses UTC Unix time. The post uses Discord timestamp markup (`<t:...:t>`), so **each member sees the schedule times in their own Discord-local timezone**. The board is refreshed every **15 minutes** (:00, :15, :30, and :45) in Eastern Time. Daylight saving time is handled automatically. Discord relative timestamps show each member the time remaining in their own local timezone.

## Free hosting: GitHub Actions + Discord webhook

This version does not need a continuously running bot process or a paid host. GitHub Actions checks every 15 minutes, but the bot posts a new board only when its saved 15-minute Eastern clock deadline is due.

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
4. Scheduled checks continue every 15 minutes; actual board posts follow the fixed 15-minute Eastern clock schedule.

GitHub Actions is free within GitHub's included usage allowances. For the most reliable no-cost operation, a public repository also receives free standard GitHub-hosted runner usage. Keep the webhook URL only in repository Secrets, never in source code.

## Private GATE DM alerts

Members can use `/gatealerts` inside the server to choose any combination of the five GATE events. The menu is private to the member and includes pause, resume, and unsubscribe controls. When one of their selected events is approaching, Flirtingway sends a direct message. Each member receives at most one alert per GATE time slot. Members must allow DMs from server members; Discord can block delivery through their privacy settings.

The DM feature runs as a Cloudflare Worker with a D1 database. The existing GitHub Actions schedule remains responsible for the board; after each scheduled board post, it asks the Worker to deliver any due private alerts.

### Setup (one-time)

1. **Create the Discord application.** In the Discord Developer Portal, create an application, add a bot user, and copy the bot token. From General Information, copy the Application ID and Public Key. Also copy your Discord server ID (enable Developer Mode in User Settings → Advanced, then use the server context menu → Copy Server ID). Never share the bot token in chat or commit it to GitHub.
2. **Invite the bot to the server.** In OAuth2 → URL Generator, select the `bot` and `applications.commands` scopes. A zero-permission bot invite is sufficient; the Worker responds to slash commands and sends DMs through the Discord API.
3. **Create a Cloudflare D1 database** named `flirtingway-gate-alerts`. Copy its Database ID and your Cloudflare Account ID.
4. **Set the D1 ID in `worker/wrangler.toml`.** Replace `REPLACE_WITH_YOUR_D1_DATABASE_ID` with the database ID. Commit that change.
5. **Create a Cloudflare API token** with permission to edit Workers Scripts and D1 databases for this account. Add these GitHub repository Actions secrets: `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`.
6. **Deploy the Worker.** In GitHub → Actions, run **Deploy Flirtingway DM Alerts Worker**. This applies the D1 migration and deploys the Worker. Its URL will look like `https://flirtingway-gate-alerts.<your-subdomain>.workers.dev`.
7. **Add Worker settings** in Cloudflare → Workers & Pages → flirtingway-gate-alerts → Settings → Variables and Secrets:
   - Variables: `DISCORD_PUBLIC_KEY`, `DISCORD_APPLICATION_ID`, and `DISCORD_GUILD_ID`.
   - Secrets: `DISCORD_BOT_TOKEN` and `SCHEDULER_SECRET`.
   Generate a long random value for `SCHEDULER_SECRET`; use the exact same value in the GitHub secret in the next step.
8. **Connect GitHub Actions to the Worker.** Add repository secrets `GATE_ALERTS_WORKER_URL` (the Worker URL, without `/interactions`) and `GATE_ALERTS_WORKER_SECRET` (the same value as `SCHEDULER_SECRET`).
9. **Connect Discord interactions.** In the Discord Developer Portal, set Interactions Endpoint URL to the Worker URL followed by `/interactions`. Discord verifies the endpoint; the Worker responds to that check and automatically registers the server-only `/gatealerts` command.
10. **Try `/gatealerts` in your Discord server.** Choose events in the private menu. The Worker stores choices in D1, and the scheduled board workflow handles private notifications.

The Worker source is in `worker/src/index.js`; its D1 schema is in `worker/migrations/`. Deployment is manual so the Worker won't attempt to deploy until your Cloudflare database and GitHub secrets are ready.

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

A local run follows the same fixed 15-minute Eastern clock schedule unless `FORCE_POST=true` is set. Do not paste your real webhook URL into chat, source code, screenshots, or a public issue.

## Files

- `bot.py` — prediction algorithm, nine-gate board, and fixed 15-minute Eastern posting schedule
- `.github/workflows/daily.yml` — 15-minute board schedule and DM notification trigger
- `worker/` — Discord slash-command endpoint, DM delivery, and D1 subscription database
- `requirements.txt` — HTTP dependency
- `ATTRIBUTION.md` — upstream project credit/license note
