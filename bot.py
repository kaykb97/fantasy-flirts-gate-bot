"""
Fantasy Flirts — rolling Gold Saucer GATE board.

Prediction method/weights are adapted from the MIT-licensed community research:
https://github.com/rooroodev/ffxivgateschedule
See ATTRIBUTION.md.

Every workflow run edits the same Discord webhook message. If the message was
deleted or is missing, the bot creates a replacement and saves its ID in
state.json in this GitHub repository.
"""
from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from urllib.parse import quote

import requests

SLOT_SECONDS = 20 * 60
GATES_TO_SHOW = 6  # Six 20-minute GATE slots = the next two hours.

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

def discord_timestamp(unix_seconds: int) -> str:
    # Discord displays this timestamp in each viewer's local timezone.
    return f"<t:{unix_seconds}:t>"

def build_board(now: datetime) -> str:
    now_ts = int(now.timestamp())
    first_slot = ((now_ts // SLOT_SECONDS) + 1) * SLOT_SECONDS
    lines = [
        "🐰 **FANTASY FLIRTS — GOLD SAUCER GATE BOARD**",
        f"**Next {GATES_TO_SHOW} GATEs · refreshed <t:{now_ts}:R>**",
        "",
        "Times display automatically in your own Discord local timezone.",
        "",
    ]
    for index in range(GATES_TO_SHOW):
        ts = first_slot + index * SLOT_SECONDS
        gate, variant = predict_gate(ts)
        emoji = EMOJI.get(gate, "🎟️")
        extra = f" — {variant}" if variant else ""
        lines.append(f"{discord_timestamp(ts)}  {emoji} **{gate}**{extra}")
    lines += [
        "",
        "🦘 Leap of Faith  ·  ✈️ Air Force One",
        "_GATE predictions use community-researched timing data; verify after game patches._",
    ]
    return "\n".join(lines)

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
    payload = response.json()
    content = base64.b64decode(payload["content"]).decode("utf-8")
    return json.loads(content), payload["sha"]

def write_state(repo: str, token: str, state: dict, sha: str | None):
    url = f"https://api.github.com/repos/{repo}/contents/state.json"
    content = base64.b64encode(
        (json.dumps(state, indent=2) + "\n").encode("utf-8")
    ).decode("ascii")
    payload = {
        "message": "Save Gold Saucer board message ID",
        "content": content,
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

    state, state_sha = read_state(repo, token)
    message_id = state.get("message_id")
    content = build_board(datetime.now(timezone.utc))

    if message_id:
        edit_url = f"{webhook}/messages/{quote(str(message_id), safe='')}"
        response = requests.patch(
            edit_url,
            json={"content": content, "allowed_mentions": {"parse": []}},
            timeout=20,
        )
        if response.status_code == 404:
            message_id = None
        else:
            response.raise_for_status()
            print(f"Updated existing GATE board message {message_id}.")
            return

    # No saved message yet (or it was deleted): create one and remember its ID.
    response = requests.post(
        webhook + "?wait=true",
        json={
            "content": content,
            "username": "Fantasy Flirts GATE Guide",
            "allowed_mentions": {"parse": []},
        },
        timeout=20,
    )
    response.raise_for_status()
    message_id = response.json()["id"]
    write_state(repo, token, {"message_id": message_id}, state_sha)
    print(f"Created GATE board message {message_id}.")

if __name__ == "__main__":
    main()
