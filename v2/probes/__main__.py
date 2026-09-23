"""Runner CLI: python -m v2.probes {list,run,report,reset-a} (S0 spec §5.3, §5.8)."""
from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from datetime import date, datetime
from pathlib import Path

import httpx

from v2.agent.tally.client import TallyClient
from v2.probes.actions import Action
from v2.probes.capture import Capture
from v2.probes.companies import COMPANIES
from v2.probes.console import ConsoleIO, ProbeIO
from v2.probes.core import Outcome, ProbeBlocked
from v2.probes.operator.auto import AUTO_RUN_MODE, AutoOperator, build_auto_operator
from v2.probes.operator.tally_control import OperatorError
from v2.probes.registry import ALL_ORDER, FIRST_ORDER, PROBES, load_probe
from v2.probes.report import render_report
from v2.probes.results import ResultsStore
from v2.probes.runner import run_order, run_probe

V2_ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = V2_ROOT / "probes" / "results" / "results.json"
FIXTURES_DIR = V2_ROOT / "tests" / "fixtures" / "sync"
LOGS_DIR = V2_ROOT / "probes" / "results" / "logs"
DOCS_DIR = V2_ROOT.parent / "docs"
MAX_PROBE_ID = PROBES[-1].id
MANUAL_RUN_MODE = "manual (S0-D3): a person performs each pause at the Tally UI"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m v2.probes")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--results", type=Path, default=RESULTS_PATH)
    parser.add_argument("--fixtures", type=Path, default=FIXTURES_DIR)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    run = sub.add_parser("run")
    which = run.add_mutually_exclusive_group(required=True)
    which.add_argument("probe_id", nargs="?", type=int)
    which.add_argument("--first", action="store_true")
    which.add_argument("--all", action="store_true")
    run.add_argument("--company", choices=["A", "B", "C"])
    run.add_argument("--rerun", action="store_true")
    run.add_argument("--auto", action="store_true", help="the automated operator performs every pause (S0-D9)")
    run.add_argument("--stop-any-tally", action="store_true",
                     help="with --auto: the operator may stop a TallyPrime it didn't start")
    report = sub.add_parser("report")
    report.add_argument("--out", type=Path)
    reset = sub.add_parser("reset-a", help="fresh seed copy in s0probe, renamed to company A (S0 spec §5.8)")
    reset.add_argument("--stop-any-tally", action="store_true")
    return parser


def _status(store: ResultsStore, item) -> str:
    if item.deferred:
        return "⏭ deferred (Q29)"
    outcome = store.outcome(item.id)
    if outcome is None:
        return "not run" if item.module else "not built"
    if outcome is Outcome.PARTIAL:
        remaining = store.probe_entry(item.id).get("remaining") or []
        if remaining:
            return f"PARTIAL (remaining: {', '.join(remaining)})"
    return outcome.value


def _list(store: ResultsStore) -> int:
    for item in PROBES:
        print(f"{item.id:>2}  {item.name:<28} {item.companies:<5} {item.tier:<4} {_status(store, item)}")
    return 0


def _auto_log() -> Path:
    return LOGS_DIR / f"s0-auto-{date.today().isoformat()}.log"


async def _run(args, store: ResultsStore, transport: httpx.AsyncBaseTransport | None, io: ProbeIO) -> int:
    previous_handler = signal.signal(signal.SIGINT, signal.default_int_handler)
    try:
        client = TallyClient(args.host, args.port, transport=transport)
        capture = Capture(args.fixtures)
        try:
            if args.first or args.all:
                await run_order(FIRST_ORDER if args.first else ALL_ORDER, client=client, store=store, capture=capture,
                                io=io, rerun=args.rerun)
                return 0
            if not 0 <= args.probe_id <= MAX_PROBE_ID:
                print(f"No probe {args.probe_id} (probes are 0–{MAX_PROBE_ID}).")
                return 2
            probe = load_probe(args.probe_id)
            if probe is None:
                print(f"Probe {args.probe_id} is not built yet (S0 plan part 2 or 3).")
                return 2
            if args.company and args.company not in probe.parts:
                print(f"Probe {args.probe_id} has no part {args.company} (has {', '.join(sorted(probe.parts))}).")
                return 2
            labels = [args.company] if args.company else None
            if getattr(io, "run_mode", "manual") == "auto" and probe.guard:
                first = labels[0] if labels else next(iter(probe.parts))
                try:
                    io.wait(f"Open company {first}: {COMPANIES[first]!r}", Action("open_company", {"label": first}))
                except ProbeBlocked as exc:
                    print(f"Couldn't open company {first}: {exc}")
                    return 1
            await run_probe(probe, labels=labels, client=client, store=store, capture=capture, io=io)
            return 0
        finally:
            await client.close()
    finally:
        signal.signal(signal.SIGINT, previous_handler)


def _reset_a(args, store: ResultsStore, operator: AutoOperator | None) -> int:
    auto = operator or build_auto_operator(host=args.host, port=args.port, log_path=_auto_log(),
                                           stop_any_tally=args.stop_any_tally)
    try:
        auto.reset_company_a()
    except OperatorError as exc:
        print(f"reset-a failed: {exc}")
        return 1
    finally:
        if operator is None:
            auto.close()
    store.update_environment(company_a_reset_at=datetime.now().astimezone().isoformat(timespec="seconds"))
    print(f"Company A reset: a fresh copy of the seed company, renamed to {COMPANIES['A']!r}.")
    return 0


def main(argv: list[str] | None = None, *, transport: httpx.AsyncBaseTransport | None = None,
         io: ProbeIO | None = None, operator: AutoOperator | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run" and args.company and (args.first or args.all):
        parser.error("--company cannot be used with --first/--all")
    if args.command == "run" and args.auto and args.non_interactive:
        parser.error("--auto cannot be used with --non-interactive")
    store = ResultsStore(args.results)
    if args.command == "list":
        return _list(store)
    if args.command == "report":
        out = args.out or DOCS_DIR / f"bi-s0-probe-results-{date.today().isoformat()}.md"
        out.write_text(render_report(store, date.today().isoformat()), encoding="utf-8")
        print(f"Wrote {out}")
        return 0
    if args.command == "reset-a":
        return _reset_a(args, store, operator)
    if args.auto:
        auto = operator or build_auto_operator(host=args.host, port=args.port, log_path=_auto_log(),
                                               stop_any_tally=args.stop_any_tally)
        store.update_environment(run_mode=AUTO_RUN_MODE)
        try:
            return asyncio.run(_run(args, store, transport, auto))
        finally:
            if operator is None:
                auto.close()
    store.update_environment(run_mode=MANUAL_RUN_MODE)
    return asyncio.run(_run(args, store, transport, io or ConsoleIO(interactive=not args.non_interactive)))


if __name__ == "__main__":
    sys.exit(main())
