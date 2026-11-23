"""
Flirtingways Gate Guide — clean blue rolling Gold Saucer GATE board.

Prediction method/weights are adapted from the MIT-licensed community research:
https://github.com/rooroodev/ffxivgateschedule
See ATTRIBUTION.md.

Every workflow run edits the same Discord webhook message. The webhook's saved
Discord name and avatar are used; this code intentionally does not override them.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from urllib.parse import quote

import requests

SLOT_SECONDS = 20 * 60
GATES_TO_SHOW = 6
REFRESH_INTERVAL_SECONDS = 2 * 60 * 60
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
    """Next scheduled run: minute 17 of every even UTC hour."""
    interval = REFRESH_INTERVAL_SECONDS
    next_run = (now_ts // interval) * interval + 17 * 60
    if next_run <= now_ts:
        next_run += interval
    return next_run

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

    next_refresh = next_refresh_timestamp(now_ts)
    description = (
        "**NEXT SIX GATES**  ·  Times shown in your local timezone\n\n"
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

def main():
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "").rstrip("/")
    if not webhook:
        raise SystemExit("Missing DISCORD_WEBHOOK_URL.")

    now = datetime.now(timezone.utc)
    next_refresh = next_refresh_timestamp(int(now.timestamp()))
    payload = {
        "content": f"⏱ **Next board refresh:** <t:{next_refresh}:R>",
        "embeds": [build_embed(now)],
        "allowed_mentions": {"parse": []},
    }

    # Always create a NEW Discord message on every workflow run.
    # Do not edit or delete previous posts. Discord's saved webhook
    # username and avatar are used automatically.
    response = requests.post(webhook + "?wait=true", json=payload, timeout=20)
    response.raise_for_status()
    message_id = response.json().get("id")
    print(f"Posted a new Flirtingway's GATE board message: {message_id}.")

if __name__ == "__main__":
    main()
