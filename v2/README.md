# v2 — BI Part 1 (syncing)

Built **beside** the current code. Specs: `docs/specs/2026-09-21-bi-part1-sync-design.md` (§5 "Code isolation (v2)")
and `docs/specs/2026-09-22-bi-s0-probes-design.md`. Status: `docs/plans/2026-09-22-bi-part1-tracker.md`.

## Isolation rules
- Nothing outside `v2/` (and `docs/`) is changed for Part 1.
- v2 never imports `backend`, `scripts` or `tests`. What it needs is **copied** into v2 and fixed there.
  Each copied file starts with `# Copied from: <path> @ <commit>`.
- `v2/agent/` never imports `v2.probes` (the agent ships with no write code).
- `v2/tests/test_isolation.py` enforces the import rules.

## Commands (run from the repo root)
- Tests: `uv run --project v2 pytest v2/tests -q`
- Probes: `uv run --project v2 python -m v2.probes list | run <id> | run --first | run --all | report`

## Live Tally on this Mac (tier B)
The repo README's `brew install --cask --no-quarantine wine-stable` no longer works: Homebrew disabled all Wine casks on
2026-09-01 (Gatekeeper) and removed `--no-quarantine`. What works (verified 2026-09-22, Wine 11.0, Apple Silicon + Rosetta):

    curl -fsSL -o wine.tar.xz https://github.com/Gcenx/macOS_Wine_builds/releases/download/11.0_1/wine-stable-11.0_1-osx64.tar.xz
    echo "b50dc50ec7f41d58b115a6b685d4d1315ba3c797bd3aa0f49213f2703cb82388  wine.tar.xz" | shasum -a 256 -c -
    tar -xJf wine.tar.xz && mv "Wine Stable.app" /Applications/ && xattr -cr "/Applications/Wine Stable.app"
    export PATH="/Applications/Wine Stable.app/Contents/Resources/wine/bin:$PATH"
    cd ~/.wine/drive_c/Program\ Files/TallyPrimeEditLog && wine tally.exe &
    curl http://localhost:9000        # → <RESPONSE>TallyPrime Server is Running</RESPONSE>

Probe company A's data folder: `C:\users\Public\TallyPrimeEditLog\s0probe` (= `~/.wine/drive_c/users/Public/TallyPrimeEditLog/s0probe`).
The seed backup is at `Z:\Users\nuvanta-mac-3\work\Tally prime\seed_data` inside Tally (Wine maps `/` to `Z:`).

## Automated runs (S0-D9, S0 spec §5.8)
- `uv run --project v2 python -m v2.probes reset-a` — stops the operator's TallyPrime, copies the pristine
  `seed_data/100003` into `s0probe`, starts Tally with `/DATA:… /LOAD:100003` and renames the company to
  "Bharat Traders Probe Copy". Also undoes anything a probe couldn't revert.
- `uv run --project v2 python -m v2.probes run --all --auto` (or `run <id> --auto`) — the operator performs every pause:
  edits via XML import (read back), open/close/backup/restore via Tally restarts.
- Watch for **`CLICK NEEDED`**: after every restart that loads a company, click "T: Continue In Educational Mode" on
  Tally's licence box (the operator waits up to 15 minutes).
- The operator stops only a TallyPrime it started on `s0probe` (`--stop-any-tally` overrides) and never edits
  `tally.ini` (it backs it up once as `tally.ini.before-s0`). Log: `v2/probes/results/logs/s0-auto-<date>.log`.
