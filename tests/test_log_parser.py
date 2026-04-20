"""Tests for the local JSONL log file parser."""
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.log_parser import parse_log_files


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with open(path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _days_ago(n: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=n)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def log_dir(tmp_path):
    return str(tmp_path)


async def test_missing_dir_returns_empty():
    result = await parse_log_files("/nonexistent/path/xyz")
    assert result["anthropic"]["today"]["total_tokens"] == 0
    assert result["openai"]["history"] == []


async def test_empty_dir_returns_empty(log_dir):
    result = await parse_log_files(log_dir)
    assert result["anthropic"]["today"]["total_tokens"] == 0
    assert result["openai"]["today"]["total_tokens"] == 0


async def test_single_anthropic_record_today(log_dir):
    _write_jsonl(Path(log_dir) / "app.jsonl", [
        {"timestamp": _today(), "provider": "anthropic", "model": "claude-sonnet-4-6",
         "input_tokens": 1000, "output_tokens": 500},
    ])
    result = await parse_log_files(log_dir)
    assert result["anthropic"]["today"]["input_tokens"] == 1000
    assert result["anthropic"]["today"]["output_tokens"] == 500
    assert result["anthropic"]["today"]["total_tokens"] == 1500


async def test_openai_and_anthropic_in_same_file(log_dir):
    _write_jsonl(Path(log_dir) / "mixed.jsonl", [
        {"timestamp": _today(), "provider": "anthropic", "input_tokens": 200, "output_tokens": 100},
        {"timestamp": _today(), "provider": "openai", "input_tokens": 300, "output_tokens": 150},
    ])
    result = await parse_log_files(log_dir)
    assert result["anthropic"]["today"]["total_tokens"] == 300
    assert result["openai"]["today"]["total_tokens"] == 450


async def test_history_record_not_in_today(log_dir):
    _write_jsonl(Path(log_dir) / "hist.jsonl", [
        {"timestamp": _days_ago(3), "provider": "anthropic", "input_tokens": 800, "output_tokens": 200},
    ])
    result = await parse_log_files(log_dir)
    assert result["anthropic"]["today"]["total_tokens"] == 0
    assert len(result["anthropic"]["history"]) == 1
    assert result["anthropic"]["history"][0]["input_tokens"] == 800


async def test_multiple_records_same_day_aggregated(log_dir):
    _write_jsonl(Path(log_dir) / "multi.jsonl", [
        {"timestamp": _today(), "provider": "openai", "input_tokens": 100, "output_tokens": 50},
        {"timestamp": _today(), "provider": "openai", "input_tokens": 200, "output_tokens": 75},
    ])
    result = await parse_log_files(log_dir)
    assert result["openai"]["today"]["input_tokens"] == 300
    assert result["openai"]["today"]["output_tokens"] == 125


async def test_malformed_line_skipped(log_dir):
    log_file = Path(log_dir) / "bad.jsonl"
    log_file.write_text(
        '{"timestamp": "' + _today() + '", "provider": "anthropic", "input_tokens": 500, "output_tokens": 200}\n'
        "NOT VALID JSON\n"
        '{"timestamp": "' + _today() + '", "provider": "anthropic", "input_tokens": 100, "output_tokens": 50}\n'
    )
    result = await parse_log_files(log_dir)
    assert result["anthropic"]["today"]["input_tokens"] == 600


async def test_unknown_provider_skipped(log_dir):
    _write_jsonl(Path(log_dir) / "unknown.jsonl", [
        {"timestamp": _today(), "provider": "gemini", "input_tokens": 999, "output_tokens": 999},
    ])
    result = await parse_log_files(log_dir)
    assert result["anthropic"]["today"]["total_tokens"] == 0
    assert result["openai"]["today"]["total_tokens"] == 0


async def test_record_older_than_30_days_excluded(log_dir):
    _write_jsonl(Path(log_dir) / "old.jsonl", [
        {"timestamp": _days_ago(31), "provider": "anthropic", "input_tokens": 9999, "output_tokens": 9999},
    ])
    result = await parse_log_files(log_dir)
    assert result["anthropic"]["today"]["total_tokens"] == 0
    assert result["anthropic"]["history"] == []


async def test_json_array_format(log_dir):
    """Supports files that contain a JSON array rather than JSONL."""
    records = [
        {"timestamp": _today(), "provider": "anthropic", "input_tokens": 400, "output_tokens": 100},
        {"timestamp": _today(), "provider": "anthropic", "input_tokens": 100, "output_tokens": 50},
    ]
    (Path(log_dir) / "array.json").write_text(json.dumps(records))
    result = await parse_log_files(log_dir)
    assert result["anthropic"]["today"]["input_tokens"] == 500


async def test_multiple_files_aggregated(log_dir):
    _write_jsonl(Path(log_dir) / "file1.jsonl", [
        {"timestamp": _today(), "provider": "anthropic", "input_tokens": 300, "output_tokens": 100},
    ])
    _write_jsonl(Path(log_dir) / "file2.jsonl", [
        {"timestamp": _today(), "provider": "anthropic", "input_tokens": 200, "output_tokens": 50},
    ])
    result = await parse_log_files(log_dir)
    assert result["anthropic"]["today"]["input_tokens"] == 500


async def test_history_sorted_by_date(log_dir):
    _write_jsonl(Path(log_dir) / "sorted.jsonl", [
        {"timestamp": _days_ago(5), "provider": "anthropic", "input_tokens": 100, "output_tokens": 10},
        {"timestamp": _days_ago(2), "provider": "anthropic", "input_tokens": 200, "output_tokens": 20},
        {"timestamp": _days_ago(8), "provider": "anthropic", "input_tokens": 50, "output_tokens": 5},
    ])
    result = await parse_log_files(log_dir)
    dates = [r["date"] for r in result["anthropic"]["history"]]
    assert dates == sorted(dates)
