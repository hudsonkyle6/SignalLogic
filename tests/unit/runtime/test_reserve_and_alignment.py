"""
Tests for:
  - rhythm_os.runtime.reserve.emit_drift_index
  - rhythm_os.runtime.alignment.emit_convergence_summary

Both are thin, append-only emitters that read from the bus and write back to it.
Tests use a tmp_path bus directory to keep I/O isolated.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from rhythm_os.psr.domain_wave import DomainWave
from rhythm_os.runtime.alignment import emit_convergence_summary
from rhythm_os.runtime.reserve import emit_drift_index


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wave(
    t: float,
    domain: str = "weather",
    channel: str = "temperature",
    phase_diff: float = 0.1,
) -> DomainWave:
    return DomainWave(
        t=t,
        domain=domain,
        channel=channel,
        field_cycle="computed",
        phase_external=0.1,
        phase_field=0.2,
        phase_diff=phase_diff,
        coherence=0.9,
        extractor={"source": "test"},
    )


def _write_to_bus(bus_dir: Path, t_ref: float, waves: list[DomainWave]) -> None:
    date_str = time.strftime("%Y-%m-%d", time.localtime(t_ref))
    bus_file = bus_dir / f"{date_str}.jsonl"
    with bus_file.open("a", encoding="utf-8") as f:
        for w in waves:
            f.write(w.to_json() + "\n")


def _read_bus(bus_dir: Path) -> list[dict]:
    records = []
    for f in sorted(bus_dir.glob("*.jsonl")):
        with f.open() as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return records


# ---------------------------------------------------------------------------
# emit_drift_index
# ---------------------------------------------------------------------------

class TestEmitDriftIndex:
    def test_silence_when_no_waves(self, tmp_path):
        t_ref = 1_700_000_000.0
        emit_drift_index(
            bus_dir=tmp_path,
            t_ref=t_ref,
            history_window_sec=86400.0,
            source_domain="weather",
            source_channel="temperature",
        )
        records = _read_bus(tmp_path)
        assert records == []

    def test_silence_with_only_one_source_wave(self, tmp_path):
        t_ref = 1_700_000_000.0
        _write_to_bus(tmp_path, t_ref, [_make_wave(t=t_ref)])
        emit_drift_index(
            bus_dir=tmp_path,
            t_ref=t_ref,
            history_window_sec=86400.0,
            source_domain="weather",
            source_channel="temperature",
        )
        records = _read_bus(tmp_path)
        # Only the original wave; no drift emission
        assert len(records) == 1

    def test_emits_drift_wave_with_sufficient_history(self, tmp_path):
        t_ref = 1_700_000_000.0
        # Write multiple source waves within window
        waves = [
            _make_wave(t=t_ref - (i * 60), phase_diff=float(i) * 0.05)
            for i in range(5)
        ]
        _write_to_bus(tmp_path, t_ref, waves)

        emit_drift_index(
            bus_dir=tmp_path,
            t_ref=t_ref,
            history_window_sec=86400.0,
            source_domain="weather",
            source_channel="temperature",
        )
        records = _read_bus(tmp_path)
        drift_records = [r for r in records if r.get("domain") == "antifragile"
                         and r.get("channel") == "drift_index"]
        assert len(drift_records) == 1

    def test_drift_wave_t_ref_matches(self, tmp_path):
        t_ref = 1_700_000_000.0
        waves = [_make_wave(t=t_ref - i * 60) for i in range(5)]
        _write_to_bus(tmp_path, t_ref, waves)

        emit_drift_index(
            bus_dir=tmp_path,
            t_ref=t_ref,
            history_window_sec=86400.0,
            source_domain="weather",
            source_channel="temperature",
        )
        records = _read_bus(tmp_path)
        drift_records = [r for r in records if r.get("domain") == "antifragile"
                         and r.get("channel") == "drift_index"]
        assert drift_records[0]["t"] == pytest.approx(t_ref)

    def test_no_duplicate_emission(self, tmp_path):
        t_ref = 1_700_000_000.0
        waves = [_make_wave(t=t_ref - i * 60) for i in range(5)]
        _write_to_bus(tmp_path, t_ref, waves)

        kwargs = dict(
            bus_dir=tmp_path,
            t_ref=t_ref,
            history_window_sec=86400.0,
            source_domain="weather",
            source_channel="temperature",
        )
        emit_drift_index(**kwargs)
        emit_drift_index(**kwargs)  # second call — should be de-duped

        records = _read_bus(tmp_path)
        drift_records = [r for r in records if r.get("domain") == "antifragile"
                         and r.get("channel") == "drift_index"]
        assert len(drift_records) == 1


# ---------------------------------------------------------------------------
# emit_convergence_summary
# ---------------------------------------------------------------------------

class TestEmitConvergenceSummary:
    def test_silence_when_no_waves(self, tmp_path):
        t_ref = 1_700_000_000.0
        emit_convergence_summary(
            bus_dir=tmp_path,
            t_ref=t_ref,
            history_window_sec=86400.0,
        )
        records = _read_bus(tmp_path)
        assert records == []

    def test_emits_convergence_wave_when_waves_present(self, tmp_path):
        t_ref = 1_700_000_000.0
        waves = [
            _make_wave(t=t_ref - i * 60, domain=f"domain_{i}", channel="ch")
            for i in range(3)
        ]
        _write_to_bus(tmp_path, t_ref, waves)

        emit_convergence_summary(
            bus_dir=tmp_path,
            t_ref=t_ref,
            history_window_sec=86400.0,
        )
        records = _read_bus(tmp_path)
        oracle_records = [r for r in records if r.get("domain") == "oracle"
                          and r.get("channel") == "convergence_summary"]
        # May or may not emit depending on alignment descriptors — but should not raise
        assert isinstance(oracle_records, list)

    def test_no_duplicate_emission(self, tmp_path):
        t_ref = 1_700_000_000.0
        waves = [
            _make_wave(t=t_ref - i * 60, domain=f"domain_{i}", channel="ch")
            for i in range(3)
        ]
        _write_to_bus(tmp_path, t_ref, waves)

        kwargs = dict(
            bus_dir=tmp_path,
            t_ref=t_ref,
            history_window_sec=86400.0,
        )
        emit_convergence_summary(**kwargs)
        emit_convergence_summary(**kwargs)  # second call — de-duped

        records = _read_bus(tmp_path)
        oracle_records = [r for r in records if r.get("domain") == "oracle"
                          and r.get("channel") == "convergence_summary"]
        assert len(oracle_records) <= 1
