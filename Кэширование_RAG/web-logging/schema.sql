CREATE TABLE interaction_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  session TEXT NOT NULL,
  question_key TEXT NOT NULL,
  query TEXT NOT NULL,
  response TEXT NOT NULL,
  source TEXT NOT NULL,
  from_cache INTEGER NOT NULL,
  response_time_ms INTEGER NOT NULL,
  status TEXT NOT NULL
);
--> statement-breakpoint
CREATE INDEX lookup_answer ON interaction_log(session, question_key, id);
--> statement-breakpoint
CREATE INDEX expire_logs ON interaction_log(timestamp);
