# Pipeline Audit — Changes Made

## 1. Naming — brought in line with `PREFIX Title Case Words.py`
Renamed (and updated `STC Pipeline Runner.py` to match):
- `rp2 site status pull.py` → `RP2 Site Status Pull.py`
- `rp4 gld to tlb.py` → `RP4 GLD to TLB.py`
- `STC date scrape.py` → `STC Date Scrape.py`
- `RP1 ESG Report DEV.py` → `RP1 ESG Report.py` (this was a "DEV" file running as your live
  production Stage 6 — worth double-checking there isn't a genuinely separate dev version
  you meant to keep around)
- `RP2 cm reports.py` → `RP2 CM Reports.py`
- `RP2 incidents.py` → `RP2 Incidents.py`
- `RP2 qset reports.py` → `RP2 QSET Reports.py`
- `RP2 site reports.py` → `RP2 Site Reports.py`
- `RP2 template label.py` → `RP2 Template Label.py`
- `RP2 user label.py` → `RP2 User Label.py`
- `RP3 esg to mc39.py` → `RP3 ESG to MC39.py`
- `RP3 mcl39.py` → `RP3 MCL39.py`
- `RP3 metric list.py` → `RP3 Metric List.py`
- `RP3 reporting logic.py` → `RP3 Reporting Logic.py`
- `STC JS0N Map and Clean.py` → `STC JSON Map and Clean.py` (typo: zero, not letter O)

`RP3 MCL39.py` and `RP3 ESG to MC39.py` are genuinely different scripts (not a
typo of each other) — left as two separate names, just correctly cased.

## 2. Moved to `archive/` (unreferenced by the pipeline runner)
These existed in the working folder but no `PIPELINE_STAGES` entry ever calls them.
Moved so the live folder only contains what actually runs:
- `RP1 Inspection Answers.py`
- `RP4 Site and User Data.py`
- `RP2 Annual Incident Data.py`
- `RP2 OCU Incident Report.py`
- `RP4 Weekly Incident Report.py`
- `STC JSON Map and Clean ARC.py` (also fixed the JS0N typo)
- `test.py`

**Worth checking**: if any of these are actually run manually/ad-hoc outside the
main pipeline, say so and I'll move them back with a note rather than leave them archived.

## 3. `STC Pipeline Runner.py`
Updated every `"script"` path and `RUN_*` toggle name to match the renamed files.
Verified programmatically: all 23 stages resolve to a file that exists.

## 4. `STC API IN.py` — the two real speed fixes
- **`store_batch_records()`**: previously read the *entire* existing output CSV
  back into memory and rewrote the whole file on every call — inside a loop that
  ran once per parent record. Now appends only the new rows (`mode='a'`), so
  each write is O(batch size), not O(file size). This was the single biggest
  slowdown in the pipeline and gets worse the larger the table gets.
- **Parent→child fetching**: child records were fetched one parent at a time,
  sequentially, with a 50ms sleep between each — almost all of that time is
  network wait. Extracted the per-parent fetch into `_fetch_children_for_parent()`
  and now run it across a small thread pool (`Child_Fetch_Workers`, default 8,
  configurable in `Global Settings`) for normal runs. All file writes still
  happen on the main thread afterwards, so there's no concurrent-write risk.
  `test_mode` intentionally stays on the old sequential path — it's small by
  design, and correctness there matters more than speed.

## 5. De-duplicated helpers → `_shared/report_utils.py`
`RP2 CM Reports.py`, `RP2 QSET Reports.py`, and `RP2 Site Reports.py` each carried
byte-identical copies of `load_site_lookup()`, `get_site_name()`, and
`clean_site_name_from_string()`. Verified they were truly identical (not just
similarly named) before moving them into one shared module all three now import.

**Deliberately NOT merged** — these looked like duplicates but turned out to have
different logic when checked line-by-line, so merging them would have silently
changed behaviour somewhere:
- `contains_template_category()` — the version in `RP2 CM Reports.py` checks
  against a single filter string; the versions in the other two check against a
  list of categories.
- `parse_date_robust()` — differs across all 4 files that define it (`RP1 ESG
  Report.py`, `RP3 ESG to MC39.py`, `RP3 MCL39.py`, `RP3 Metric List.py`).
- `clean_site_name()` (distinct from `clean_site_name_from_string`) — differs
  across all 4 files that define it, one of them substantially.

If any of these were *meant* to be the same function and have just drifted apart
over time, that's a judgement call only you can make safely — happy to diff them
side by side if you want to reconcile.

## 6. Pre-pull archive (added on request)
`STC Pipeline Runner.py` now snapshots the four data folders into their own
`\archive\<timestamp>\` subfolder before Stage 1 pulls anything:
- `Data\TNS\archive`
- `Data\SLV\archive`
- `Data\GLD\archive`
- `Data\REP\archive`

It's a copy, not a move — nothing in the working folders is ever deleted, and
the archive step never reads its own archive back in (so re-runs can't archive
an archive). Each run gets its own timestamped subfolder so today's snapshot
doesn't overwrite yesterday's. Controlled by `RUN_PRE_PULL_ARCHIVE` at the top
of the runner; if archiving fails for any of the four, the whole pipeline halts
before Stage 1 rather than pulling fresh data over files that didn't get
snapshotted. Tested against a mock folder structure, including a second
consecutive run to confirm no clobbering or self-archiving.

Note: `Data\BNZ` (used as an intermediate stage between TNS and SLV) wasn't in
your list of four, so it's untouched — say the word if that was meant to be
included too.

## 7. Fix for the DNS/slowness you just hit
Your log showed a `getaddrinfo failed` error and roughly 2–4 minutes per 20
parents even with the thread pool running — both traced back to the same root
cause in `_fetch_children_for_parent()`: it was opening a **brand new session
per parent** (fresh DNS lookup + TCP/TLS handshake, 775 times), and a single
failed request just silently dropped that parent's children with no retry.

Fixed both:
- **Persistent sessions**: each worker thread now creates one session and
  reuses it for every parent it processes, instead of open-close per parent.
  Confirmed with a test that two calls on the same thread return the exact
  same session object.
- **Automatic retries**: sessions now carry a `urllib3.Retry` adapter — up to
  4 attempts with backoff, covering connection failures (including DNS blips
  like the one you saw), timeouts, and 429/500/502/503/504 responses. Verified
  against a mock server that fails the first two attempts and succeeds on the
  third — the request now comes back with data instead of silently vanishing.
- `Child_Fetch_Workers` (still defaults to 8) stays configurable via
  `Global Settings` in your manifest if you want to dial concurrency up or down.

## 8. The real "multiple engines" fix
More threads alone was always going to hit a wall: past a certain point you're
not moving faster, you're just generating more 429s that retry into the same
ceiling. Two changes instead:

- **A shared rate limiter (`_RateLimiter`)** — a token-bucket, thread-safe,
  sitting inside `execute_request()`, which is the *one* place every HTTP
  call in the file passes through (parent fetch, child fetch, standalone
  endpoint, from any thread, from any chain). No matter how much concurrency
  gets added anywhere else, the actual request rate hitting the API is capped
  at `Requests_Per_Second` (Global Settings, default `8`). I couldn't find a
  publicly confirmed per-account rate limit for SafetyCulture's API in their
  docs, so 8 is a conservative starting point, not a verified ceiling — check
  the response headers on a real request (or your account's API docs/support)
  and raise it once you know your actual limit. Unit-tested: 20 concurrent
  threads hitting a 5/sec limiter took ~3s, not ~0s.
- **Chains and standalone endpoints now run concurrently too**, not one at a
  time. `Chain_Concurrency` (Global Settings, default `3`) controls how many
  parent-child chains / standalone endpoints run in parallel — each with its
  own 8-worker child pool underneath. That's up to 24 threads all hitting
  `execute_request()` at once in the worst case, but the shared limiter above
  is what actually governs the API-facing rate, so this is safe rather than
  reckless. Proved this with a mock server and a fake "3 chains × 8 workers"
  run: 60 requests came in at ~12/sec against a 10/sec limiter (small overshoot
  is just startup burst on a short run) — the ceiling held under real nested
  concurrency, it didn't multiply out of control.

Tune both settings once you've confirmed your account's real rate limit —
raising `Requests_Per_Second` to match it is the actual lever now, not adding
more workers on top of an already-saturated pipe.

## 9. Scripts folder path no longer hardcoded
`SCRIPTS_DIR` in `STC Pipeline Runner.py` was a hardcoded absolute path. Every
time the Scripts folder got moved, renamed, or re-extracted from a zip (e.g.
Windows appending `(2)`, `(3)`, etc.), the runner broke until someone edited
that line by hand. It now self-locates:

```python
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
```

This resolves to wherever `STC Pipeline Runner.py` itself is currently sitting
— tested by dropping a copy inside a folder literally named `Scripts_Audited
(3)\Scripts` and confirming it resolved correctly. The 23 stage scripts all
live alongside the runner, so this one change means you'll never need to hand-
edit a path here again, regardless of where the folder ends up.

Note: the four `Data\...` paths (TNS/SLV/GLD/REP/BNZ) are separate from the
Scripts folder and untouched by this — those still point at their existing
fixed location on your OneDrive.

## Not touched (flagged only, in case you want it done next)
- `STC Pipeline Runner.py` still launches all 23 stages as separate subprocesses,
  each paying fresh Python/pandas import cost and round-tripping CSVs to disk
  between stages. Real but secondary — say the word if you want this folded into
  fewer processes.
