"""Save every Tally response as a fixture plus a JSON sidecar (S0 spec §5.6)."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from v2.agent.tally.client import TallyResponse

TIMING_NOTE = "Wine — not representative"
_STEP = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")


def fixture_name(probe_id: int, part: str, step: str) -> str:
    if not _STEP.match(step):
        raise ValueError(f"Step name must match {_STEP.pattern}: {step!r}")
    return f"p{probe_id:02d}_{part}_{step}.xml"


class Capture:
    def __init__(self, fixtures_dir: Path):
        self.fixtures_dir = fixtures_dir

    def save(
        self,
        *,
        probe_id: int,
        part: str,
        step: str,
        company_name: str,
        company_guid: str | None,
        request_xml: str,
        sent_at: datetime,
        environment: dict[str, Any],
        response: TallyResponse | None = None,
        error: dict[str, str] | None = None,
    ) -> str:
        """Write the raw response bytes (if any) and the sidecar; return the fixture file name."""
        if (response is None) == (error is None):
            raise ValueError("Capture.save needs exactly one of response or error")
        name = fixture_name(probe_id, part, step)
        self.fixtures_dir.mkdir(parents=True, exist_ok=True)
        if response is not None:
            (self.fixtures_dir / name).write_bytes(response.raw)
        else:
            (self.fixtures_dir / name).unlink(missing_ok=True)
        sidecar: dict[str, Any] = {
            "probe": probe_id,
            "part": part,
            "step": step,
            "company_name": company_name,
            "company_guid": company_guid,
            "sent_at": sent_at.isoformat(timespec="seconds"),
            "elapsed_ms": response.elapsed_ms if response else None,
            "response_bytes": response.response_bytes if response else None,
            "timing_note": TIMING_NOTE,
            "request_xml": request_xml,
            "environment": environment,
        }
        if error is not None:
            sidecar["error"] = error
        (self.fixtures_dir / f"{name}.json").write_text(
            json.dumps(sidecar, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
        )
        return name
