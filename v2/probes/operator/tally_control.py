"""Stop and start TallyPrime under Wine on the s0probe data folder, and wait for it (S0 spec §5.8).

Process control goes through a ProcessRunner so tests never start Wine. The operator stops only a TallyPrime it can
recognise as its own — started with /DATA:…s0probe, or spawned by this operator — unless told `stop_any_tally`.
"""
from __future__ import annotations

import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

import httpx

from v2.agent.tally.envelopes import build_company_list
from v2.agent.tally.xml_utils import parse_company_list, sanitize_xml
from v2.probes.core import ProbeBlocked
from v2.probes.operator.config import DATA_MARKER, OperatorConfig

CLICK_NEEDED = "CLICK NEEDED: in TallyPrime click 'T: Continue In Educational Mode' on the licence box"
BUSY_REPEAT_S = 30.0
CLICK_REPEAT_S = 60.0
WRONG_COMPANY_LIMIT = 5


class OperatorError(ProbeBlocked):
    """The operator couldn't perform a step; the part is recorded BLOCKED with this message."""


@dataclass(frozen=True)
class TallyProcess:
    pid: int
    command: str


class ProcessRunner(Protocol):
    def list_tally(self) -> list[TallyProcess]: ...

    def spawn(self, argv: list[str], cwd: Path, log_path: Path) -> None: ...

    def terminate(self, pid: int) -> None: ...

    def kill(self, pid: int) -> None: ...

    def run(self, argv: list[str], timeout: float) -> str: ...

    def sleep(self, seconds: float) -> None: ...

    def now(self) -> float: ...


class SystemRunner:
    """The real ps / kill / Popen. Never used by tests."""

    def list_tally(self) -> list[TallyProcess]:
        out = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True, check=False).stdout
        found: list[TallyProcess] = []
        for line in out.splitlines():
            pid, _, command = line.strip().partition(" ")
            if pid.isdigit() and "tally.exe" in command.lower():
                found.append(TallyProcess(int(pid), command.strip()))
        return found

    def spawn(self, argv: list[str], cwd: Path, log_path: Path) -> None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "ab") as log:
            subprocess.Popen(argv, cwd=cwd, stdout=log, stderr=log, start_new_session=True)

    def terminate(self, pid: int) -> None:
        subprocess.run(["kill", "-TERM", str(pid)], check=False)

    def kill(self, pid: int) -> None:
        subprocess.run(["kill", "-KILL", str(pid)], check=False)

    def run(self, argv: list[str], timeout: float) -> str:
        try:
            done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""
        return done.stdout.strip()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def now(self) -> float:
        return time.monotonic()


class TallyControl:
    def __init__(self, config: OperatorConfig, runner: ProcessRunner, http: httpx.Client, say: Callable[[str], None],
                 *, stop_any_tally: bool = False):
        self.config = config
        self.runner = runner
        self.http = http
        self.say = say
        self.stop_any_tally = stop_any_tally
        self._own_pids: set[int] = set()

    # --- what is running ------------------------------------------------------------------------------------------
    def port_up(self) -> bool:
        try:
            return "Running" in self.http.get("/", timeout=httpx.Timeout(3.0, connect=3.0)).text
        except httpx.HTTPError:
            return False

    def company_names(self) -> list[str] | None:
        """Loaded companies, or None while Tally doesn't answer (starting, loading a company, stuck)."""
        try:
            response = self.http.post("/", content=build_company_list().encode("utf-8"),
                                      headers={"Content-Type": "text/xml; charset=utf-8"},
                                      timeout=httpx.Timeout(10.0, connect=3.0))
            response.raise_for_status()
            return parse_company_list(sanitize_xml(response.text))
        except (httpx.HTTPError, ET.ParseError):
            return None

    def _classify(self) -> tuple[list[TallyProcess], list[TallyProcess]]:
        own: list[TallyProcess] = []
        foreign: list[TallyProcess] = []
        for proc in self.runner.list_tally():
            if proc.pid in self._own_pids or DATA_MARKER in proc.command.lower():
                own.append(proc)
            else:
                foreign.append(proc)
        return own, foreign

    def own_tally_running(self) -> bool:
        own, foreign = self._classify()
        return bool(own) and not foreign

    # --- stop / start -----------------------------------------------------------------------------------------------
    def stop(self) -> None:
        own, foreign = self._classify()
        if foreign and not self.stop_any_tally:
            pids = ", ".join(str(p.pid) for p in foreign)
            raise OperatorError(f"A TallyPrime the operator didn't start is running (pid {pids}). Close it by hand, "
                                f"or pass --stop-any-tally; the operator only stops its own s0probe TallyPrime.")
        targets = own + foreign
        if not targets:
            if self.port_up():
                raise OperatorError("TallyPrime answers on 9000 but no tally.exe process was found — stop it by hand")
            return
        self.say(f"stopping TallyPrime (pid {', '.join(str(p.pid) for p in targets)})")
        for proc in targets:
            self.runner.terminate(proc.pid)
        if not self._wait(lambda: not self.runner.list_tally() and not self.port_up(), self.config.stop_wait_s):
            # Kill only the pids we were already authorised to stop — never a foreign TallyPrime that showed up
            # while we were waiting (that one is not ours to touch, stop_any_tally or not).
            target_pids = {proc.pid for proc in targets}
            for proc in self.runner.list_tally():
                if proc.pid in target_pids:
                    self.runner.kill(proc.pid)
            self.runner.sleep(2.0)
            still_own, _ = self._classify()      # post-condition: did our own TallyPrime actually stop?
            if still_own:
                raise OperatorError("TallyPrime didn't stop, even after kill -9")
        self._own_pids.clear()

    def start(self, load_label: str | None) -> None:
        if self.runner.list_tally():
            raise OperatorError("TallyPrime is already running; stop it first")
        self._backup_ini_once()
        argv = [str(self.config.wine_bin), "tally.exe", f"/DATA:{self.config.data_dir_windows}"]
        if load_label is not None:
            argv.append(f"/LOAD:{self.config.company_numbers[load_label]}")
        self.say("starting TallyPrime: " + " ".join(argv[1:]))
        try:
            self.runner.spawn(argv, self.config.tally_dir, self.config.wine_log)
        except OSError as exc:
            raise OperatorError(f"Can't start TallyPrime: {exc}") from exc

        def up() -> bool:
            self._own_pids.update(p.pid for p in self.runner.list_tally())   # nothing ran before the spawn
            return self.port_up()

        if not self._wait(up, self.config.start_wait_s):
            raise OperatorError(f"TallyPrime didn't answer on its port within {self.config.start_wait_s:.0f}s")

    def wait_for_companies(self, expected: list[str], *, click: bool) -> list[str]:
        """Poll the company list until it equals `expected`, riding out timeouts while a company loads.

        A non-empty, wrong company list for WRONG_COMPANY_LIMIT consecutive polls (once the XML server is actually
        answering) means the wrong company is open, not that Tally is still loading — fail fast instead of waiting out
        the whole click window. An empty list keeps waiting: that's the licence box (S0 spec §5.8).
        """
        limit = self.config.click_wait_s if click else self.config.start_wait_s
        deadline = self.runner.now() + limit
        told_at = busy_at = None
        wrong_streak = 0
        if click:
            self.say(f"{CLICK_NEEDED} (waiting up to {limit / 60:.0f} min for {expected})")
            told_at = self.runner.now()
        while True:
            names = self.company_names()
            if names == expected:
                if click:
                    self.say(f"companies open: {names}")
                return names
            now = self.runner.now()
            if names is None:
                wrong_streak = 0
                if busy_at is None or now - busy_at >= BUSY_REPEAT_S:
                    self.say("Tally busy (loading a company?) — still waiting")
                    busy_at = now
            elif names:
                wrong_streak += 1
                if wrong_streak >= WRONG_COMPANY_LIMIT:
                    raise OperatorError(f"Tally has {names} open, not {expected}; close it and open the right "
                                        "company by hand")
            else:
                wrong_streak = 0
            if click and told_at is not None and now - told_at >= CLICK_REPEAT_S:
                self.say(f"{CLICK_NEEDED} (still waiting for {expected}; Tally shows {names})")
                told_at = now
            if now >= deadline:
                raise OperatorError(f"Timed out waiting for {expected}; Tally shows {names}")
            self.runner.sleep(self.config.poll_s)

    def restart(self, load_label: str | None, expected: list[str]) -> list[str]:
        self.stop()
        self.start(load_label)
        return self.wait_for_companies(expected, click=load_label is not None)

    def ensure_running(self) -> None:
        if self.port_up():
            return
        if self.runner.list_tally():
            raise OperatorError("A TallyPrime process exists but its port doesn't answer — check Tally for a popup")
        self.start(None)
        self.wait_for_companies([], click=False)

    def wine_version(self) -> str:
        return self.runner.run([str(self.config.wine_bin), "--version"], timeout=15.0)

    # --- helpers ------------------------------------------------------------------------------------------------------
    def _wait(self, condition: Callable[[], bool], seconds: float) -> bool:
        deadline = self.runner.now() + seconds
        while True:
            if condition():
                return True
            if self.runner.now() >= deadline:
                return False
            self.runner.sleep(1.0)

    def _backup_ini_once(self) -> None:
        ini = self.config.tally_dir / "tally.ini"
        backup = self.config.tally_dir / "tally.ini.before-s0"
        if ini.exists() and not backup.exists():
            try:
                shutil.copy2(ini, backup)
            except OSError as exc:
                raise OperatorError(f"Can't back up tally.ini: {exc}") from exc
            self.say(f"backed up {ini.name} → {backup.name} (the operator never edits tally.ini)")
