CREATE TABLE IF NOT EXISTS subscriptions (
  user_id TEXT PRIMARY KEY,
  events_json TEXT NOT NULL DEFAULT '[]',
  paused INTEGER NOT NULL DEFAULT 0 CHECK (paused IN (0, 1)),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS subscriptions_paused_idx ON subscriptions (paused);

CREATE TABLE IF NOT EXISTS deliveries (
  user_id TEXT NOT NULL,
  slot_ts INTEGER NOT NULL,
  event_name TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('pending', 'sent', 'failed')),
  error_text TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  delivered_at TEXT,
  PRIMARY KEY (user_id, slot_ts)
);
CREATE INDEX IF NOT EXISTS deliveries_slot_idx ON deliveries (slot_ts, event_name);
