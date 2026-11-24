const EVENTS = [
  { value: "air_force_one", name: "Air Force One", emoji: "✈️" },
  { value: "cliffhanger", name: "Cliffhanger", emoji: "🧗" },
  { value: "leap_of_faith", name: "Leap of Faith", emoji: "🦘" },
  { value: "any_way_the_wind_blows", name: "Any Way the Wind Blows", emoji: "🌪️" },
  { value: "the_slice_is_right", name: "The Slice Is Right", emoji: "🍕" },
];
const API = "https://discord.com/api/v10";
const EPHEMERAL = 64;

function json(data, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json; charset=utf-8" } });
}
function hexToBytes(hex) {
  if (!/^[0-9a-f]+$/i.test(hex) || hex.length % 2) throw new Error("Invalid hex");
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < bytes.length; i++) bytes[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  return bytes;
}
async function verifySignature(request, body, publicKeyHex) {
  const signature = request.headers.get("x-signature-ed25519");
  const timestamp = request.headers.get("x-signature-timestamp");
  if (!signature || !timestamp || !publicKeyHex) return false;
  try {
    const key = await crypto.subtle.importKey("raw", hexToBytes(publicKeyHex), { name: "Ed25519" }, false, ["verify"]);
    return await crypto.subtle.verify("Ed25519", key, hexToBytes(signature), new TextEncoder().encode(timestamp + body));
  } catch (error) {
    console.error("Signature verification error:", String(error));
    return false;
  }
}
async function discordRequest(env, path, method = "GET", data) {
  const response = await fetch(API + path, {
    method,
    headers: { authorization: "Bot " + env.DISCORD_BOT_TOKEN, "content-type": "application/json" },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  const raw = await response.text();
  let parsed = {};
  try { parsed = raw ? JSON.parse(raw) : {}; } catch { parsed = { message: raw }; }
  if (!response.ok) throw new Error("Discord API " + response.status + ": " + (parsed.message || raw));
  return parsed;
}
async function registerGuildCommand(env) {
  if (!env.DISCORD_BOT_TOKEN || !env.DISCORD_APPLICATION_ID || !env.DISCORD_GUILD_ID) {
    console.log("Set bot token, application ID, and guild ID before verifying the interaction URL.");
    return;
  }
  try {
    await discordRequest(env, "/applications/" + env.DISCORD_APPLICATION_ID + "/guilds/" + env.DISCORD_GUILD_ID + "/commands", "POST", {
      name: "gatealerts",
      description: "Choose which GATEs you want private alerts for",
      type: 1,
    });
    console.log("Registered /gatealerts in the configured server.");
  } catch (error) {
    console.error("Slash command registration failed:", String(error));
  }
}
async function getSubscription(env, userId) {
  return env.DB.prepare("SELECT user_id, events_json, paused FROM subscriptions WHERE user_id = ?").bind(userId).first();
}
function getSelected(row) {
  if (!row) return [];
  try {
    const list = JSON.parse(row.events_json || "[]");
    return Array.isArray(list) ? list.filter((v) => EVENTS.some((e) => e.value === v)) : [];
  } catch { return []; }
}
async function buildSettings(env, userId, notice = "") {
  const row = await getSubscription(env, userId);
  const selected = getSelected(row);
  const paused = row && Number(row.paused) === 1;
  let status = selected.length === 0
    ? "You are not subscribed yet. Choose one or more GATEs below."
    : paused
      ? "Your alerts are paused. Resume them whenever you're ready."
      : "You're subscribed to " + selected.length + " GATE event" + (selected.length === 1 ? "" : "s") + ". I'll DM you when one is coming up.";
  return {
    content: (notice ? notice + "\n\n" : "") + "🐰 **Flirtingway — private GATE alerts**\n" + status + "\n\nSelect the events you'd like to hear about. You can change these choices any time.",
    flags: EPHEMERAL,
    components: [
      { type: 1, components: [{
        type: 3, custom_id: "gatealerts:select", placeholder: "Choose your GATE events",
        min_values: 0, max_values: EVENTS.length,
        options: EVENTS.map((event) => ({
          label: event.name, value: event.value, emoji: { name: event.emoji },
          default: selected.includes(event.value),
        })),
      }]},
      { type: 1, components: [
        { type: 2, style: paused ? 3 : 2, label: paused ? "Resume alerts" : "Pause alerts", custom_id: "gatealerts:toggle", disabled: selected.length === 0 },
        { type: 2, style: 4, label: "Unsubscribe from all", custom_id: "gatealerts:unsubscribe", disabled: selected.length === 0 },
      ]},
    ],
  };
}
async function handleInteraction(interaction, env) {
  const userId = interaction.member?.user?.id || interaction.user?.id;
  if (!userId) return json({ type: 4, data: { content: "I couldn't identify your Discord account. Please try again.", flags: EPHEMERAL } });

  if (interaction.type === 2 && interaction.data?.name === "gatealerts") {
    return json({ type: 4, data: await buildSettings(env, userId) });
  }
  if (interaction.type !== 3) return json({ type: 4, data: { content: "I don't recognize that interaction.", flags: EPHEMERAL } });

  const customId = interaction.data?.custom_id || "";
  if (customId === "gatealerts:select") {
    const values = Array.isArray(interaction.data?.values) ? interaction.data.values : [];
    const valid = [...new Set(values)].filter((v) => EVENTS.some((e) => e.value === v));
    await env.DB.prepare(
      "INSERT INTO subscriptions (user_id, events_json, paused, updated_at) VALUES (?, ?, 0, CURRENT_TIMESTAMP) " +
      "ON CONFLICT(user_id) DO UPDATE SET events_json = excluded.events_json, updated_at = CURRENT_TIMESTAMP"
    ).bind(userId, JSON.stringify(valid)).run();
    return json({ type: 7, data: await buildSettings(env, userId, "Your GATE alert preferences have been saved!") });
  }
  if (customId === "gatealerts:toggle") {
    const row = await getSubscription(env, userId);
    if (!row || getSelected(row).length === 0) {
      return json({ type: 7, data: await buildSettings(env, userId, "Choose at least one event first.") });
    }
    const paused = Number(row.paused) === 1 ? 0 : 1;
    await env.DB.prepare("UPDATE subscriptions SET paused = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?").bind(paused, userId).run();
    return json({ type: 7, data: await buildSettings(env, userId, paused ? "Your GATE alerts are paused." : "Your GATE alerts are back on!") });
  }
  if (customId === "gatealerts:unsubscribe") {
    await env.DB.batch([
      env.DB.prepare("DELETE FROM subscriptions WHERE user_id = ?").bind(userId),
      env.DB.prepare("DELETE FROM deliveries WHERE user_id = ?").bind(userId),
    ]);
    return json({ type: 7, data: await buildSettings(env, userId, "You've unsubscribed from all GATE DMs.") });
  }
  return json({ type: 4, data: { content: "That control expired. Run /gatealerts again.", flags: EPHEMERAL } });
}
function constantTimeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let mismatch = 0;
  for (let i = 0; i < a.length; i++) mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return mismatch === 0;
}
async function notifySubscribers(request, env) {
  if (!env.SCHEDULER_SECRET) return json({ error: "Scheduler secret is not configured." }, 503);
  if (!constantTimeEqual(request.headers.get("authorization") || "", "Bearer " + env.SCHEDULER_SECRET)) return json({ error: "Unauthorized." }, 401);
  if (!env.DISCORD_BOT_TOKEN) return json({ error: "Discord bot token is not configured." }, 503);
  let payload;
  try { payload = await request.json(); } catch { return json({ error: "Expected JSON." }, 400); }
  const slotTs = Number(payload.slot_ts);
  const event = EVENTS.find((e) => e.name === payload.event_name);
  if (!event || !Number.isSafeInteger(slotTs) || slotTs <= 0) return json({ error: "Invalid event_name or slot_ts." }, 400);

  const result = await env.DB.prepare(
    "SELECT user_id FROM subscriptions WHERE paused = 0 " +
    "AND EXISTS (SELECT 1 FROM json_each(events_json) WHERE value = ?)"
  ).bind(event.value).all();
  const subscribers = result.results || [];
  let sent = 0, failed = 0, alreadySent = 0;
  const variant = typeof payload.variant === "string" ? payload.variant.slice(0, 120) : "";

  for (let offset = 0; offset < subscribers.length; offset += 5) {
    const group = subscribers.slice(offset, offset + 5);
    await Promise.all(group.map(async (subscriber) => {
      const claim = await env.DB.prepare(
        "INSERT OR IGNORE INTO deliveries (user_id, slot_ts, event_name, status) VALUES (?, ?, ?, 'pending')"
      ).bind(subscriber.user_id, slotTs, event.name).run();
      if (!claim.meta || claim.meta.changes === 0) { alreadySent++; return; }
      try {
        const channel = await discordRequest(env, "/users/@me/channels", "POST", { recipient_id: subscriber.user_id });
        const location = variant ? "\nLocation: **" + variant + "**" : "";
        await discordRequest(env, "/channels/" + channel.id + "/messages", "POST", {
          content: "🐰 **Flirtingway GATE Alert**\n\n" + event.emoji + " **" + event.name + "** starts <t:" + slotTs + ":R> (<t:" + slotTs + ":t>)!" + location +
            "\n\nYou're receiving this because you opted into this GATE. Manage your alerts any time with /gatealerts.",
          allowed_mentions: { parse: [] },
        });
        await env.DB.prepare("UPDATE deliveries SET status = 'sent', delivered_at = CURRENT_TIMESTAMP WHERE user_id = ? AND slot_ts = ?")
          .bind(subscriber.user_id, slotTs).run();
        sent++;
      } catch (error) {
        await env.DB.prepare("UPDATE deliveries SET status = 'failed', error_text = ?, delivered_at = CURRENT_TIMESTAMP WHERE user_id = ? AND slot_ts = ?")
          .bind(String(error).slice(0, 500), subscriber.user_id, slotTs).run();
        failed++;
        console.log("DM delivery failed:", String(error));
      }
    }));
  }
  return json({ ok: true, event: event.name, slot_ts: slotTs, subscribers: subscribers.length, sent, failed, already_sent: alreadySent });
}
async function handleDiscordRequest(request, env, ctx) {
  const body = await request.text();
  if (!await verifySignature(request, body, env.DISCORD_PUBLIC_KEY)) return json({ error: "Invalid Discord request signature." }, 401);
  let interaction;
  try { interaction = JSON.parse(body); } catch { return json({ error: "Invalid JSON." }, 400); }
  if (interaction.type === 1) {
    ctx.waitUntil(registerGuildCommand(env));
    return json({ type: 1 });
  }
  return handleInteraction(interaction, env);
}
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/health") return json({ ok: true, service: "Flirtingway GATE DM alerts" });
    if (request.method === "POST" && url.pathname === "/interactions") return handleDiscordRequest(request, env, ctx);
    if (request.method === "POST" && url.pathname === "/notify") return notifySubscribers(request, env);
    return json({ error: "Not found." }, 404);
  },
};
