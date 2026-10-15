These token-only fixtures were extracted from the sealed 2026-10-15
rootless-closeout17 heterogeneous covariance run, native stages 002 (21 counters)
and 004 (5 counters). Only `event_msg / token_count / info` metadata is retained;
conversation messages, timestamps, paths, and thread identifiers are omitted.
`total_token_usage` is cumulative; `last_token_usage` is retained to exercise the
actual wire shape but is never added to that total. Final input/cached/output:
002 = 869474 / 798976 / 14761; 004 = 130660 / 84480 / 2921. These equal the original
terminal `usage.json` meters. No fixture invokes a model or contains scientific text.
