"""
Flirtingways Gate Guide — clean blue rolling Gold Saucer GATE board.

Prediction method/weights are adapted from the MIT-licensed community research:
https://github.com/rooroodev/ffxivgateschedule
See ATTRIBUTION.md.

The workflow checks every 5 minutes for private GATE DMs, while the public board
refreshes every 120 minutes. Each refresh posts the replacement board and removes
the previous board message when possible. Manual runs do not bypass the deadline unless FORCE_POST=true. Optional private GATE DMs are handled by the Cloudflare Worker when configured. The webhook's saved Discord name and avatar
are used; this code intentionally does not override them.
"""
from __future__ import annotations

import base64
import json

import os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import requests

SLOT_SECONDS = 20 * 60
GATES_TO_SHOW = 9
REFRESH_INTERVAL_SECONDS = 15 * 60  # Private DM lead window; independent of board cadence.
SCHEDULE_TIMEZONE = ZoneInfo("America/New_York")
SCHEDULE_VERSION = 4
EMBED_BLUE = 0x287BFF

AFO_CIELDALAES = (
    ("Cieldalaes — Sea Route", 1),
    ("Cieldalaes — Cave Route", 1),
    ("Cieldalaes — River Route", 1),
)
AFO_GOLD_SAUCER = (
    ("Gold Saucer — Event Square Route", 1),
    ("Gold Saucer — Wonder Square Route", 1),
    ("Gold Saucer — Round Square Route", 1),
)
LEAP_VARIANTS = (
    ("The Fall of Belah'dia", 9),
    ("The Falling City of Nym", 9),
    ("Sylphstep", 9),
)
CLIFF_VARIANTS = (
    ("Round Square", 7),
    ("Wonder Square East", 7),
)
SIMPLE_VARIANT = (("Event Square", 1),)

class Weighted:
    def __init__(self, name, weight, variants=()):
        self.name = name
        self.weight = weight
        self.variants = variants

EVENTS = {
    0: (
        Weighted("Air Force One", 32, AFO_CIELDALAES),
        Weighted("Cliffhanger", 33, CLIFF_VARIANTS),
        Weighted("Leap of Faith", 35, LEAP_VARIANTS),
    ),
    20: (
        Weighted("Any Way the Wind Blows", 45, SIMPLE_VARIANT),
        Weighted("The Slice Is Right", 33, SIMPLE_VARIANT),
        Weighted("Air Force One", 22, AFO_GOLD_SAUCER),
    ),
    40: (
        Weighted("The Slice Is Right", 12, SIMPLE_VARIANT),
        Weighted("Leap of Faith", 13, LEAP_VARIANTS),
        Weighted("Air Force One", 75, AFO_CIELDALAES),
    ),
}

EMOJI = {
    "Air Force One": "✈️",
    "Cliffhanger": "🧗",
    "Leap of Faith": "🦘",
    "Any Way the Wind Blows": "🌪️",
    "The Slice Is Right": "🍕",
}


def build_gate_notification(now_ts: int) -> dict | None:
    """Identify the next GATE slot that falls inside the private-alert lead window."""
    current_slot = (now_ts // SLOT_SECONDS) * SLOT_SECONDS
    next_slot = current_slot + SLOT_SECONDS
    seconds_until_next = next_slot - now_ts

    # Only alert ahead of a GATE, never after it has already started.
    if seconds_until_next > REFRESH_INTERVAL_SECONDS:
        return None
    slot_ts = next_slot

    event_name, variant = predict_gate(slot_ts)
    return {
        "slot_ts": slot_ts,
        "event_name": event_name,
        "variant": variant,
    }


def send_gate_dm_notifications(now_ts: int) -> None:
    """Ask the Cloudflare Worker to DM members subscribed to this upcoming GATE."""
    worker_url = os.environ.get("GATE_ALERTS_WORKER_URL", "").rstrip("/")
    worker_secret = os.environ.get("GATE_ALERTS_WORKER_SECRET", "")
    if not worker_url or not worker_secret:
        print("DM alerts are not configured yet; skipping private notifications.")
        return

    alert = build_gate_notification(now_ts)
    if not alert:
        print("No GATE falls inside the current DM alert window.")
        return

    try:
        response = requests.post(
            worker_url + "/notify",
            headers={"Authorization": f"Bearer {worker_secret}"},
            json=alert,
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
        print(
            "Private GATE alerts processed: "
            f"{result.get('sent', 0)} sent, "
            f"{result.get('failed', 0)} failed, "
            f"{result.get('already_sent', 0)} already sent."
        )
    except (requests.RequestException, ValueError) as error:
        # Do not skip saving the board schedule if the optional DM service is unavailable.
        print(f"Private GATE notification service failed: {error}")


def xorshift128(seed: int):
    x, y, z, w = seed & 0xFFFFFFFF, 0, 0, 0
    while True:
        t = (x ^ ((x << 11) & 0xFFFFFFFF)) & 0xFFFFFFFF
        x, y, z = y, z, w
        w = (w ^ (w >> 19) ^ t ^ (t >> 8)) & 0xFFFFFFFF
        yield w

def weighted_pick(items, draw):
    total = sum(item.weight if isinstance(item, Weighted) else item[1] for item in items)
    target = draw % total
    cumulative = 0
    for item in items:
        weight = item.weight if isinstance(item, Weighted) else item[1]
        cumulative += weight
        if target < cumulative:
            return item
    return items[-1]

def predict_gate(slot_start: int) -> tuple[str, str | None]:
    minute = (slot_start // SLOT_SECONDS % 3) * 20
    draws = xorshift128(slot_start)
    d1, d2, _d3, _d4 = (next(draws) for _ in range(4))
    gate = weighted_pick(EVENTS[minute], d1)
    variant = weighted_pick(gate.variants, d2)[0] if gate.variants else None
    return gate.name, variant

def next_refresh_timestamp(now_ts: int) -> int:
    """Next two-hour clock boundary in Eastern Time (00:00, 02:00, ...)."""
    now_local = datetime.fromtimestamp(now_ts, SCHEDULE_TIMEZONE)
    next_hour = ((now_local.hour // 2) + 1) * 2
    boundary = now_local.replace(minute=0, second=0, microsecond=0)
    if next_hour >= 24:
        boundary = boundary.replace(hour=0) + timedelta(days=1)
    else:
        boundary = boundary.replace(hour=next_hour)
    return int(boundary.timestamp())

def build_embed(now: datetime) -> dict:
    now_ts = int(now.timestamp())
    first_slot = ((now_ts // SLOT_SECONDS) + 1) * SLOT_SECONDS
    lines = []

    for index in range(GATES_TO_SHOW):
        ts = first_slot + index * SLOT_SECONDS
        gate, variant = predict_gate(ts)
        emoji = EMOJI.get(gate, "🎟️")
        time_text = f"<t:{ts}:t>"
        location = variant or "Event Square"

        # One compact line per GATE reduces visual clutter.
        lines.append(f"{time_text}  {emoji} **{gate}**  ·  {location}")

    description = (
        "**NEXT NINE GATES**  ·  Times shown in your local timezone\n\n"
        + "\n".join(lines)
    )

    return {
        "author": {
            "name": "GOLD SAUCER • DAILY GATE SCHEDULE",
        },
        "title": "✨ Flirtingway's GATE Board",
        "description": description,
        "color": EMBED_BLUE,
        "footer": {
            "text": "💙 Flirtingway's Gate Guide  •  Predictions are estimates"
        },
    }

def github_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

def read_state(repo: str, token: str):
    url = f"https://api.github.com/repos/{repo}/contents/state.json"
    response = requests.get(url, headers=github_headers(token), timeout=20)
    if response.status_code == 404:
        return {}, None
    response.raise_for_status()
    saved = response.json()
    try:
        raw = base64.b64decode(saved["content"]).decode("utf-8").strip()
        # Repair the legacy file ending: the old writer saved literal backslash+n.
        if raw.endswith("\\n"):
            raw = raw[:-2].rstrip()
        state = json.loads(raw)
        if not isinstance(state, dict):
            raise ValueError("Saved state must be a JSON object")
        return state, saved["sha"]
    except (KeyError, ValueError, json.JSONDecodeError):
        return {}, saved.get("sha")

def write_state(repo: str, token: str, state: dict, sha: str | None):
    url = f"https://api.github.com/repos/{repo}/contents/state.json"
    encoded = base64.b64encode(
        (json.dumps(state, indent=2) + "\n").encode("utf-8")
    ).decode("ascii")
    payload = {
        "message": "Save Flirtingway GATE posting schedule",
        "content": encoded,
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha
    response = requests.put(url, headers=github_headers(token), json=payload, timeout=20)
    response.raise_for_status()

def main():
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "").rstrip("/")
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not webhook or not token or not repo:
        raise SystemExit("Missing DISCORD_WEBHOOK_URL, GITHUB_TOKEN, or GITHUB_REPOSITORY.")

    now = datetime.now(timezone.utc)
    now_ts = int(now.timestamp())
    state, state_sha = read_state(repo, token)
    previous_due = state.get("next_due_ts")

    force_post = os.environ.get("FORCE_POST", "").strip().lower() == "true"
    next_boundary = next_refresh_timestamp(now_ts)
    schedule_version = state.get("schedule_version", 0)
    previous_due = state.get("next_due_ts")

    # Migrate the previous schedule to fixed two-hour Eastern clock boundaries.
    # Save the next boundary and wait; do not create a surprise post.
    if schedule_version != SCHEDULE_VERSION or previous_due is None:
        state.update({
            "schedule_version": SCHEDULE_VERSION,
            "next_due_ts": next_boundary,
        })
        write_state(repo, token, state, state_sha)
        print(
            "Initialized the fixed Eastern two-hour schedule. "
            f"Next post is due at {datetime.fromtimestamp(next_boundary, SCHEDULE_TIMEZONE).isoformat()}."
        )
        return

    due = now_ts >= int(previous_due)
    if not due and not force_post:
        # Check private GATE subscriptions on every five-minute workflow run,
        # independently of whether a new public board post is due.
        send_gate_dm_notifications(now_ts)
        due_text = datetime.fromtimestamp(int(previous_due), SCHEDULE_TIMEZONE).isoformat()
        print(f"Board not due yet; next post is scheduled for {due_text}.")
        return

    # Posts always point to the next fixed two-hour Eastern clock boundary,
    # regardless of small GitHub Actions scheduling delays or manual runs.
    next_due = next_refresh_timestamp(now_ts)
    payload = {
        "content": f"⏱ **Next board refresh:** <t:{next_due}:R>",
        "embeds": [build_embed(now)],
        "allowed_mentions": {"parse": []},
    }

    # Post the new board first, then remove the previous board to avoid a blank channel.
    response = requests.post(webhook + "?wait=true", json=payload, timeout=20)
    response.raise_for_status()
    message_id = response.json().get("id")

    previous_message_id = state.get("last_message_id")
    if previous_message_id and str(previous_message_id) != str(message_id):
        try:
            delete_response = requests.delete(
                webhook + f"/messages/{previous_message_id}", timeout=20
            )
            if delete_response.status_code not in (204, 404):
                delete_response.raise_for_status()
            print(f"Removed previous GATE board message ({previous_message_id}).")
        except requests.RequestException as error:
            print(f"Could not remove previous GATE board message ({previous_message_id}): {error}")

    # Manual force-posts are for board testing and never DM subscribers.
    if not force_post:
        send_gate_dm_notifications(now_ts)

    # Save the next deadline only after Discord confirms the post succeeded.
    write_state(
        repo,
        token,
        {
            "schedule_version": SCHEDULE_VERSION,
            "next_due_ts": next_due,
            "last_posted_ts": now_ts,
            "last_message_id": message_id,
        },
        state_sha,
    )
    print(
        f"Posted a new GATE board message ({message_id}). "
        f"Next due: {datetime.fromtimestamp(next_due, timezone.utc).isoformat()}."
    )

if __name__ == "__main__":
    main()
