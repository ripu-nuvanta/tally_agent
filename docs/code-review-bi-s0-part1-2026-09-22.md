# Code review — BI S0 probes, plan part 1 (v2 foundation + probes 0, 2, 1) — 2026-09-22

**Scope:** everything under `v2/` built by [`plans/2026-09-22-bi-s0-probes-plan.md`](plans/2026-09-22-bi-s0-probes-plan.md)
(Tasks 1–8): scaffold + isolation test, copied Tally read code (`v2/agent/tally/`), probe harness (`v2/probes/`),
probes 0, 2, 1. Spec: [`specs/2026-09-22-bi-s0-probes-design.md`](specs/2026-09-22-bi-s0-probes-design.md).
**No commits** (user's instruction) — `v2/` is untracked; reviews read full file contents from the working tree.

## Process
| Stage | Reviewer | Result |
|---|---|---|
| Tasks 1–3 (scaffold, copies, Decimal parsers) | task review | ✅ spec, approved; 3 minors deferred |
| Tasks 4–5 (harness core, context/runner/CLI) | task review | ✅ spec, approved; minors deferred |
| Tasks 6–8 (anchors + probes 0, 2, 1) | task review | 1 Important (plan-mandated, ruled), 1 gap fixed (Alt+F3 → Company menu Alt+K), re-review ADDRESSED |
| Whole `v2/` | final review (most capable model) | No Critical; 7 Important; "ready with fixes" |
| Final fix wave (F1–F7, M1–M12, M14) | scoped re-review | **All addressed, no new breakage** |

Tests: 50 → 93 → 107 → **146 passed**, also with `-W error`. `git status --porcelain`: nothing new outside `v2/` and `docs/`.

## Findings fixed in the final wave
| # | Finding | Fix |
|---|---|---|
| I-1 | Any non-guard exception (empty/odd Tally response, Ctrl-C) crashed the run and lost the part's evidence | Runner records BLOCKED "Harness error: …"; Ctrl-C records then stops; cleanup notes ("CLEANUP NEEDED in Tally") for UI changes in flight |
| I-2 | `--first`/`--all` never stopped (kept sending to a stuck Tally after a timeout; ran on after an anchors failure) and re-ran probe 0 | Ordered runs stop at the first non-CONFIRMED/DIFFERENT part, skip done parts unless `--rerun`; probes 1, 2 require probe 0 |
| I-3 | Probes couldn't see raw bytes / timing | `ctx.last_response`; probe 2 measures transport bytes |
| I-4 | Company guard ran only at part start | `ctx.check_company()` after reopen pauses; company named in mutation pauses |
| I-5 | Seed company has no "Bank Charges" → probe 1 would alter "Rent" and never revert it | Fallback tested (picks Rent); new revert step leaves company A as it was |
| I-6 | Licence/edition answers unvalidated; Educational tagging (§4.6) missing | Re-ask until valid; `educational_sensitive` probes tagged |
| I-7 | PARTIAL didn't list remaining parts | `remaining` stored and shown in `list` / report |
| minors | Probe 0 timeout → FAILED; guard regex missed attributes/`&#42;`; stale `.xml` after error; baseline in every sidecar; `sort_keys` crash; duplicate step names; mutation guard order; anchors after rename; connect-timeout message + proxy env; CLI tracebacks; relative-import gap in isolation test; header note; test file-handle leak | All fixed (M1–M12, M14) |

## Rulings (controller)
- Probe 0: a wrong company or anchor mismatch after the restore is BLOCKED (retry), not FAILED(Q29) — operator slips can't be
  told apart from a Wine restore failure; spec §7 amended.
- Found while planning: `tests/fixtures/*_live.xml` are the NUVANTA company, not the seed — never used as seed anchors (specs
  corrected); the current `parse_company_list` counts CMPINFO's `<COMPANY>0</COMPANY>` as a company named "0" (v2 copy fixed;
  **current code not changed** — noted for its own backlog).

## Still deferred (can't hurt a live run)
`timeout=0` treated as default; untested "candidates disagree" branch (probe 2); `sanitize_xml` hex refs; stale confirmed
request after a failed re-run; per-action ledger AlterID reads (probe 1); run-transcript logs and `fixtures/harness/`.

## Not run
- **Live Tally (tier B):** nothing has been run against TallyPrime yet — probes 0, 2, 1 are harness-tested only.
- **Tier C:** deferred (Q29).
