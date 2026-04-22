"""Tests for MCP server tools."""

import pytest

from my_mcp_server.tools import delayed_echo, echo, hello


class TestHello:
    """Tests for hello tool."""

    def test_returns_greeting(self):
        result = hello("World")
        assert result == {"message": "Hello, World! Welcome to MCP."}

    def test_with_different_name(self):
        result = hello("Alice")
        assert "Alice" in result["message"]

    def test_empty_name(self):
        result = hello("")
        assert result == {"message": "Hello, ! Welcome to MCP."}

    def test_with_fixture(self, sample_name):
        result = hello(sample_name)
        assert sample_name in result["message"]


class TestEcho:
    """Tests for echo tool."""

    def test_returns_text(self):
        result = echo("test message")
        assert result["echo"] == "test message"
        assert "timestamp" in result

    def test_timestamp_is_iso_format(self):
        result = echo("test")
        assert "T" in result["timestamp"]
        assert "+" in result["timestamp"] or "Z" in result["timestamp"]

    def test_empty_text(self):
        result = echo("")
        assert result["echo"] == ""


class TestDelayedEcho:
    """Tests for delayed_echo async tool."""

    @pytest.mark.asyncio
    async def test_returns_echo(self):
        result = await delayed_echo("async test", delay=0.01)
        assert result["echo"] == "async test"
        assert result["delay_seconds"] == "0.01"

    @pytest.mark.asyncio
    async def test_default_delay(self):
        result = await delayed_echo("test", delay=0.01)
        assert "delay_seconds" in result
