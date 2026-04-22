"""MCP server tools - pure functions for testing."""

import asyncio
from datetime import UTC, datetime


def hello(name: str) -> dict[str, str]:
    """Returns a greeting message.

    Args:
        name: Name to greet.

    Returns:
        Dictionary with greeting message.
    """
    return {"message": f"Hello, {name}! Welcome to MCP."}


def echo(text: str) -> dict[str, str]:
    """Echoes back the input text with a timestamp.

    Args:
        text: Text to echo back.

    Returns:
        Dictionary with echoed text and ISO timestamp.
    """
    return {
        "echo": text,
        "timestamp": datetime.now(UTC).isoformat(),
    }


async def delayed_echo(text: str, delay: float = 1.0) -> dict[str, str]:
    """Echoes text after a delay (async example).

    Args:
        text: Text to echo back.
        delay: Seconds to wait before responding (default: 1.0).

    Returns:
        Dictionary with echoed text and actual delay.
    """
    await asyncio.sleep(delay)
    return {
        "echo": text,
        "delay_seconds": str(delay),
    }
