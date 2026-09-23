import json
from datetime import datetime, timezone

import pytest

from v2.agent.tally.client import TallyResponse
from v2.probes.capture import TIMING_NOTE, Capture, fixture_name

SENT = datetime(2026, 9, 23, 10, 12, 3, tzinfo=timezone.utc)


def _save(capture, **overrides):
    kwargs = dict(probe_id=16, part="A", step="ledgers_asof_2025-10-31", company_name="Bharat Traders Probe Copy",
                  company_guid="g-1", request_xml="<ENVELOPE/>", sent_at=SENT,
                  environment={"licence": "licensed"})
    kwargs.update(overrides)
    return capture.save(**kwargs)


def test_fixture_name():
    assert fixture_name(1, "A", "counters_baseline") == "p01_A_counters_baseline.xml"
    with pytest.raises(ValueError):
        fixture_name(1, "A", "Bad Step")


def test_saves_raw_bytes_exactly_and_sidecar(tmp_path):
    raw = "<E>शर्मा&#4;</E>".encode("utf-8")
    name = _save(Capture(tmp_path), response=TallyResponse(text=raw.decode(), raw=raw, elapsed_ms=412))

    assert name == "p16_A_ledgers_asof_2025-10-31.xml"
    assert (tmp_path / name).read_bytes() == raw
    sidecar = json.loads((tmp_path / f"{name}.json").read_text(encoding="utf-8"))
    assert sidecar == {
        "probe": 16, "part": "A", "step": "ledgers_asof_2025-10-31",
        "company_name": "Bharat Traders Probe Copy", "company_guid": "g-1",
        "sent_at": "2026-09-23T10:12:03+00:00", "elapsed_ms": 412, "response_bytes": len(raw),
        "timing_note": TIMING_NOTE, "request_xml": "<ENVELOPE/>", "environment": {"licence": "licensed"},
    }


def test_error_writes_sidecar_only(tmp_path):
    name = _save(Capture(tmp_path), step="popup_read", error={"kind": "timeout", "message": "no answer"})
    assert not (tmp_path / name).exists()
    sidecar = json.loads((tmp_path / f"{name}.json").read_text(encoding="utf-8"))
    assert sidecar["error"] == {"kind": "timeout", "message": "no answer"}
    assert sidecar["elapsed_ms"] is None


def test_save_requires_exactly_one_of_response_or_error(tmp_path):
    capture = Capture(tmp_path)
    with pytest.raises(ValueError):
        _save(capture, step="neither")
    with pytest.raises(ValueError):
        _save(capture, step="both", response=TallyResponse(text="<E/>", raw=b"<E/>", elapsed_ms=1),
              error={"kind": "timeout", "message": "x"})


def test_error_deletes_stale_xml_from_an_earlier_run(tmp_path):
    capture = Capture(tmp_path)
    name = _save(capture, step="popup_read", response=TallyResponse(text="<E/>", raw=b"<E/>", elapsed_ms=1))
    assert (tmp_path / name).exists()
    _save(capture, step="popup_read", error={"kind": "timeout", "message": "no answer"})
    assert not (tmp_path / name).exists()
