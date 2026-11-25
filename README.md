# Flirtingway Help — GATE Board Scheduler

Posts a rolling prediction board showing the **next nine GATEs** (three hours of coverage) in the configured Discord channel. GATE slots are spaced 20 minutes apart.

## Schedule behavior

- **Public board:** refreshes every **120 minutes** on even-hour boundaries in America/New_York time (00:00, 02:00, 04:00, and so on).
- **Replacement:** posts the new board first, then attempts to delete the previous board message using the saved message ID.
- **Private alerts:** the unified Flirtingway Help Cloudflare Worker checks every **5 minutes** and sends DMs up to **15 minutes** before a GATE. This runs independently of GitHub Actions, so board-post timing and GitHub schedule delays cannot suppress private alerts.
- **Delivery recovery:** a failed delivery is retried on the next 5-minute check; an abandoned pending claim is eligible for retry after 10 minutes. Successful slots are deduplicated per subscriber and never sent twice.
- **Timezone display:** board timestamps use Discord timestamp markup, so each member sees times in their own local timezone. Eastern Time boundaries account for daylight-saving transitions.

## GitHub Actions configuration

The scheduler requires these repository settings:

- `DISCORD_WEBHOOK_URL` — existing Discord webhook URL for the public GATE board. Keep it in GitHub Actions secrets.
- `GATE_ALERTS_WORKER_SECRET` — used only by the manual command-registration workflow; it must exactly match the `SCHEDULER_SECRET` configured on the unified Cloudflare Worker.
- `GITHUB_TOKEN` and `GITHUB_REPOSITORY` are supplied by GitHub Actions.
- `GATE_STATE_BRANCH` is set by the workflow to the selected ref so manual test runs do not update `main` accidentally.

The workflow runs on a five-minute check cadence for the public-board deadline. The first run after the schedule-version migration initializes the next two-hour boundary and does not post a surprise board. After that, the board refreshes at the saved deadline. Private GATE DMs do not depend on this workflow.

Manual **Force post immediately** is a deliberate board-post test: it posts to the configured webhook and replaces the saved previous board message. Use it only when the configured webhook points to the channel you intend to test. A forced post does not send subscriber DMs.

## Unified Worker integration

The slash-command and DM service is now being consolidated into the separate `Flirtingway Help` Cloudflare Worker in the `kaykb97/fantasy-flirts-housing-bot` repository. That Worker:

- serves both `/housing` and `/gatealerts` through the new Discord application's `/interactions` endpoint;
- uses the existing `flirtingway-gate-alerts` D1 database and its `subscriptions` and `deliveries` tables without recreating or migrating them;
- keeps Housing searches on-demand only;
- authenticates `/notify` and the two internal command-registration endpoints with `SCHEDULER_SECRET`.

The unified Worker has its own Wrangler configuration at `worker/wrangler.toml`. Its deployment is manual-only while the consolidation is being tested. The original Housing and GATE Workers remain available for rollback; do not disable them until the new bot has passed testing and cutover is explicitly approved.

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

**Migration note:** this branch is preparation-only. Do not merge or deploy it until the unified Worker is deployed separately, the GitHub URL secret points to the new Worker, the secret matches Cloudflare, both slash commands are registered, and the test checklist passes.
