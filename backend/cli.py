"""Standalone persistence CLI — run via cron to capture data without the web server.

Usage:
    python -m backend.cli

Cron example (every 15 minutes):
    */15 * * * * cd /path/to/agentic_usage && .venv/bin/python -m backend.cli >> logs/cli.log 2>&1
"""
import asyncio
import os
from datetime import datetime, timezone


async def _run() -> None:
    from backend.config import settings
    import backend.db as db
    from backend.sources.claude_code_parser import parse_claude_code_sessions
    from backend.sources.claude_stats_cache import persist_stats_cache
    from backend.sources.codex_parser import parse_codex_sessions

    db.init(settings.db_path)
    today_str = datetime.now(timezone.utc).date().isoformat()
    print(f"[{today_str}] agentic-usage persist run")

    # Claude Code — supplement DB with stats-cache fill-ins first, then overwrite
    # with live JSONL data (higher fidelity) for dates it covers.
    claude_dir = os.path.expanduser(settings.claude_code_dir)
    await persist_stats_cache(claude_dir)

    result = await parse_claude_code_sessions(claude_dir)
    if result.get("configured") and result.get("today"):
        await db.persist_source("claude_code", today_str, result["today"], result.get("history", []))
        print(f"  [claude_code] persisted {today_str}")
    else:
        print(f"  [claude_code] skipped: {result.get('error') or 'not configured'}")

    # Codex
    codex_dir = os.path.expanduser(settings.codex_dir)
    result = await parse_codex_sessions(codex_dir)
    if result.get("configured") and result.get("today"):
        await db.persist_source("codex", today_str, result["today"], result.get("history", []))
        print(f"  [codex] persisted {today_str}")
    else:
        print(f"  [codex] skipped: {result.get('error') or 'not configured'}")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
