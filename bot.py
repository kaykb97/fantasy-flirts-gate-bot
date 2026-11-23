"""
Fantasy Flirts — FFXIV Gold Saucer GATE schedule poster.

Prediction method and current weights are adapted from:
https://github.com/rooroodev/ffxivgateschedule
Original project is MIT-licensed. See ATTRIBUTION.md.

The game selects the same GATE for all worlds/regions on the same game version.
Times in Discord are rendered in each member's own local timezone via Discord
timestamp markup (<t:UNIX:t>).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import NamedTuple

import requests

SLOT_SECONDS = 20 * 60
DAY_SECONDS = 24 * 60 * 60

class Weighted(NamedTuple):
    name: str
    weight: int
    variants: tuple[tuple[str, int], ...] = ()

# Order is significant. Keep in sync with the upstream research.
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
    """Upstream's xorshift128 variant: timestamp in x, other words zeroed."""
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
    """Predict one GATE at a Unix timestamp aligned to a 20-minute boundary."""
    minute = (slot_start // SLOT_SECONDS % 3) * 20
    draws = xorshift128(slot_start)
    d1, d2, _d3, _d4 = (next(draws) for _ in range(4))
    gate = weighted_pick(EVENTS[minute], d1)
    variant = weighted_pick(gate.variants, d2)[0] if gate.variants else None
    return gate.name, variant

def discord_timestamp(unix_seconds: int) -> str:
    # Discord renders this timestamp in each viewer's own local timezone.
    return f"<t:{unix_seconds}:t>"

def build_daily_message(day_start: datetime) -> str:
    start = int(day_start.timestamp())
    lines = [
        "🐰 **FANTASY FLIRTS — DAILY GOLD SAUCER GATES**",
        "**NEXT 24 HOURS**",
        "",
        "Times automatically display in *your* Discord local timezone.",
        "GATEs are predicted from the current community-researched time seed.",
        "",
    ]
    for hour in range(24):
        entries = []
        for minute in (0, 20, 40):
            ts = start + hour * 3600 + minute * 60
            gate, variant = predict_gate(ts)
            emoji = EMOJI.get(gate, "🎟️")
            extra = f" — {variant}" if variant else ""
            entries.append(f"{discord_timestamp(ts)} {emoji} **{gate}**{extra}")
        lines.append("  •  ".join(entries))
    lines += [
        "",
        "🦘 Leap of Faith  ·  ✈️ Air Force One",
        "_Predictions follow the current researched schedule; verify in-game if a patch changes GATE weights._",
    ]
    return "\n".join(lines)

def main():
    webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook:
        raise SystemExit("Missing DISCORD_WEBHOOK_URL environment variable.")

    # GitHub Actions runs this at 00:00 UTC. The GATE schedule itself is UTC-based.
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    message = build_daily_message(day_start)

    # Webhook content limit is 2000 chars; split safely into multiple posts if needed.
    chunks, current = [], ""
    for line in message.splitlines():
        candidate = f"{current}\n{line}".strip() if current else line
        if len(candidate) > 1950:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)

    for index, chunk in enumerate(chunks):
        payload = {
            "content": chunk,
            "username": "Fantasy Flirts GATE Guide",
            "allowed_mentions": {"parse": []},
        }
        response = requests.post(webhook, json=payload, timeout=20)
        response.raise_for_status()
        if index < len(chunks) - 1:
            import time
            time.sleep(1)
    print(f"Posted {len(chunks)} schedule message(s) for {day_start.date()}.")

if __name__ == "__main__":
    main()
