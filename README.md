# Flirtingway Help — GATE Board Scheduler (legacy rollback reference)

**Retirement status (2026-11-26):** Owner confirmed the unified Flirtingway Help bot delivered the 3:05 PM Eastern private alert and successfully refreshed the public board at 4 PM Eastern. Active production is now `kaykb97/flirtingway-help`. This repository and its application are retained for rollback only. Do not run manual scheduler, registration or deployment workflows without a deliberate rollback review. Owner confirmed on 2026-11-26 that the old Discord bot was removed from all servers. Discord-side retirement is complete; the legacy application, repository, and infrastructure are retained as rollback references. Post-removal delivery has not yet been independently verified.

Posts a rolling prediction board showing the **next nine GATEs** (three hours of coverage) in the configured Discord channel. GATE slots are spaced 20 minutes apart.

## Schedule behavior

- **Public board:** refreshes every **120 minutes** on even-hour boundaries in America/New_York time (00:00, 02:00, 04:00, and so on).
- **Replacement:** posts the new board first, then attempts to delete the previous board message using the saved message ID.
- **Private alerts:** the unified Flirtingway Help Cloudflare Worker checks every **5 minutes** and sends DMs up to **15 minutes** before a GATE.
- **Public board:** the same Cloudflare cron refreshes the public nine-GATE board every **2 hours**, posts the replacement first, and removes the previous board message. The webhook URL is encrypted before it is stored in the shared D1 database. GitHub Actions is no longer the public-board clock.
- **Delivery recovery:** a failed DM is retried on the next 5-minute check; an abandoned pending claim is eligible for retry after 10 minutes. Successful slots are deduplicated per subscriber and never sent twice.
- **Timezone display:** board timestamps use Discord timestamp markup, so each member sees times in their own local timezone. Eastern Time boundaries account for daylight-saving transitions.

## GitHub Actions configuration

The scheduler requires these repository settings:

- `DISCORD_WEBHOOK_URL` — existing Discord webhook URL for the public GATE board. Keep it in GitHub Actions secrets.
- `GATE_ALERTS_WORKER_SECRET` — used only by the manual command-registration workflow; it must exactly match the `SCHEDULER_SECRET` configured on the unified Cloudflare Worker.
- `GITHUB_TOKEN` and `GITHUB_REPOSITORY` are supplied by GitHub Actions.
- `GATE_STATE_BRANCH` is set by the workflow to the selected ref so manual test runs do not update `main` accidentally.

Historically the workflow ran on a five-minute check cadence for the public-board deadline; it is now manual-only. The first run after the schedule-version migration initializes the next two-hour boundary and does not post a surprise board. After that, the board refreshes at the saved deadline. Private GATE DMs do not depend on this workflow.

Manual **Force post immediately** is a deliberate board-post test: it posts to the configured webhook and replaces the saved previous board message. Use it only when the configured webhook points to the channel you intend to test. A forced post does not send subscriber DMs.

## Unified Worker integration

The slash-command and DM service runs in the unified `Flirtingway Help` Cloudflare Worker in the `kaykb97/fantasy-flirts-housing-bot` repository. That Worker:

- serves both `/housing` and `/gatealerts` through the new Discord application's `/interactions` endpoint;
- uses the existing `flirtingway-gate-alerts` D1 database and its `subscriptions` and `deliveries` tables without recreating or migrating them;
- keeps Housing searches on-demand only;
- authenticates the backward-compatible `/notify` endpoint and internal command-registration endpoints with `SCHEDULER_SECRET`;
- runs a native Cloudflare Cron Trigger every five minutes to predict the next GATE and deliver private alerts directly from Flirtingway Help;
- retries failed delivery records on subsequent cron checks and recovers pending claims older than 10 minutes, while deduplicating each subscriber/slot in D1.

The unified Worker has its own Wrangler configuration at `worker/wrangler.toml`, including the five-minute cron trigger. Its deployment is manual-only. The original Housing and GATE Workers remain available as rollback services; they are no longer part of the active DM scheduling path.

After the unified Worker is deployed, its Discord interactions endpoint must be set to:

`https://flirtingway-help.kalynkb97.workers.dev/interactions`

The two command registrations are intentionally separate in scope: `/housing` is global and `/gatealerts` is registered to the configured test/server guild. This avoids one bulk command registration overwriting the other. The same unified Worker owns the 5-minute private GATE DM cron and the `deliveries` idempotency/retry state.

## Prediction algorithm

The prediction logic and weights are adapted from the MIT-licensed community research project:

https://github.com/rooroodev/ffxivgateschedule

The upstream research states that GATE schedules are time-seeded and shared across worlds/regions on the same game version. If a future FFXIV patch changes the schedule, update `EVENTS` and variant definitions in `bot.py` using the upstream project's latest research.

## Files

- `bot.py` — prediction algorithm, nine-GATE board, and two-hour refresh
- `.github/workflows/daily.yml` — public-board scheduler only
- `tests/test_scheduler.py` — two-hour cadence, DST, and private-alert lead-window tests
- `.github/workflows/validate-scheduler.yml` — scheduler validation workflow
- `state.json` — saved board deadline and last posted board message ID
- `ATTRIBUTION.md` — upstream project credit/license note

**Deployment note:** deploy the unified Worker first so its Cloudflare cron trigger is active, then merge this scheduler PR. The existing board webhook and saved board state are retained.
